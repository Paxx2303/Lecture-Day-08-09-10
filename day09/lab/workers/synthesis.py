"""
workers/synthesis.py — Synthesis Worker
Sprint 2: Tổng hợp câu trả lời từ retrieved_chunks và policy_result.

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: evidence từ retrieval_worker
    - policy_result: kết quả từ policy_tool_worker

Output (vào AgentState):
    - final_answer: câu trả lời cuối với citation
    - sources: danh sách nguồn tài liệu được cite
    - confidence: mức độ tin cậy (0.0 - 1.0)

Gọi độc lập để test:
    python workers/synthesis.py
"""

import os

# ── Sprint 2 fix: load .env từ gốc project khi chạy độc lập ─────────
try:
    from dotenv import load_dotenv
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(_root, ".env"))
except ImportError:
    pass

WORKER_NAME = "synthesis_worker"

SYSTEM_PROMPT = """Bạn là trợ lý IT Helpdesk nội bộ.

Quy tắc nghiêm ngặt:
1. CHỈ trả lời dựa vào context được cung cấp. KHÔNG dùng kiến thức ngoài.
2. Nếu context không đủ để trả lời → nói rõ "Không đủ thông tin trong tài liệu nội bộ".
3. Trích dẫn nguồn cuối mỗi câu quan trọng: [tên_file].
4. Trả lời súc tích, có cấu trúc. Không dài dòng.
5. Nếu có exceptions/ngoại lệ → nêu rõ ràng trước khi kết luận.
"""


def _call_llm(messages: list) -> str:
    """
    Gọi LLM để tổng hợp câu trả lời.

    Sprint 2 fix:
    - Expose lỗi thật thay vì nuốt im lặng
    - Thứ tự: OpenAI → Anthropic → Gemini → error message
    """
    last_error = None

    # ── Option A: OpenAI ─────────────────────────────────────────────
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            from openai import OpenAI
            client   = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model       = "gpt-4o-mini",
                messages    = messages,
                temperature = 0.1,
                max_tokens  = 500,
            )
            return response.choices[0].message.content
        except Exception as e:
            last_error = f"OpenAI: {e}"
            print(f"[synthesis] ⚠️  OpenAI failed: {e}")

    # ── Option B: Anthropic (claude-haiku) ──────────────────────────
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)

            # Tách system message ra khỏi messages list (Anthropic API khác OpenAI)
            system_content = ""
            user_messages  = []
            for m in messages:
                if m["role"] == "system":
                    system_content = m["content"]
                else:
                    user_messages.append(m)

            response = client.messages.create(
                model      = "claude-haiku-4-5-20251001",
                max_tokens = 500,
                system     = system_content,
                messages   = user_messages,
            )
            return response.content[0].text
        except Exception as e:
            last_error = f"Anthropic: {e}"
            print(f"[synthesis] ⚠️  Anthropic failed: {e}")

    # ── Option C: Gemini ─────────────────────────────────────────────
    google_key = os.getenv("GOOGLE_API_KEY")
    if google_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=google_key)
            model    = genai.GenerativeModel("gemini-1.5-flash")
            combined = "\n".join([m["content"] for m in messages])
            response = model.generate_content(combined)
            return response.text
        except Exception as e:
            last_error = f"Gemini: {e}"
            print(f"[synthesis] ⚠️  Gemini failed: {e}")

    # ── Không có key nào hoạt động ──────────────────────────────────
    if not any([openai_key, anthropic_key, google_key]):
        return (
            "[SYNTHESIS ERROR] Không tìm thấy API key nào.\n"
            "Cần ít nhất 1 trong: OPENAI_API_KEY / ANTHROPIC_API_KEY / GOOGLE_API_KEY trong .env"
        )

    return f"[SYNTHESIS ERROR] Tất cả LLM đều thất bại. Lỗi cuối: {last_error}"


def _build_context(chunks: list, policy_result: dict) -> str:
    """Xây dựng context string từ chunks và policy result."""
    parts = []

    if chunks:
        parts.append("=== TÀI LIỆU THAM KHẢO ===")
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "unknown")
            text   = chunk.get("text",   "")
            score  = chunk.get("score",   0)
            parts.append(f"[{i}] Nguồn: {source} (relevance: {score:.2f})\n{text}")

    if policy_result and policy_result.get("exceptions_found"):
        parts.append("\n=== POLICY EXCEPTIONS ===")
        for ex in policy_result["exceptions_found"]:
            parts.append(f"- {ex.get('rule', '')}")

    if policy_result and policy_result.get("policy_version_note"):
        parts.append(f"\n⚠️  Lưu ý phiên bản policy: {policy_result['policy_version_note']}")

    if not parts:
        return "(Không có context)"

    return "\n\n".join(parts)


def _estimate_confidence(chunks: list, answer: str, policy_result: dict) -> float:
    """
    Ước tính confidence dựa vào:
    - Số lượng và quality của chunks
    - Có exceptions không
    - Answer có abstain không
    """
    if not chunks:
        return 0.1   # Không có evidence → low confidence

    if "[SYNTHESIS ERROR]" in answer:
        return 0.1   # LLM failed

    if "Không đủ thông tin" in answer or "không có trong tài liệu" in answer.lower():
        return 0.3   # Abstain → moderate-low

    avg_score = sum(c.get("score", 0) for c in chunks) / len(chunks)

    # Penalty nếu có exceptions (phức tạp hơn)
    exception_penalty = 0.05 * len(policy_result.get("exceptions_found", []))

    confidence = min(0.95, avg_score - exception_penalty)
    return round(max(0.1, confidence), 2)


def synthesize(task: str, chunks: list, policy_result: dict) -> dict:
    """
    Tổng hợp câu trả lời từ chunks và policy context.

    Returns:
        {"answer": str, "sources": list, "confidence": float}
    """
    context = _build_context(chunks, policy_result)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Câu hỏi: {task}\n\n"
                f"{context}\n\n"
                f"Hãy trả lời câu hỏi dựa vào tài liệu trên."
            ),
        },
    ]

    answer     = _call_llm(messages)
    sources    = list({c.get("source", "unknown") for c in chunks})
    confidence = _estimate_confidence(chunks, answer, policy_result)

    return {
        "answer":     answer,
        "sources":    sources,
        "confidence": confidence,
    }


def run(state: dict) -> dict:
    """Worker entry point — gọi từ graph.py."""
    task          = state.get("task", "")
    chunks        = state.get("retrieved_chunks", [])
    policy_result = state.get("policy_result", {})

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task":         task,
            "chunks_count": len(chunks),
            "has_policy":   bool(policy_result),
        },
        "output": None,
        "error":  None,
    }

    try:
        result = synthesize(task, chunks, policy_result)
        state["final_answer"] = result["answer"]
        state["sources"]      = result["sources"]
        state["confidence"]   = result["confidence"]

        worker_io["output"] = {
            "answer_length": len(result["answer"]),
            "sources":       result["sources"],
            "confidence":    result["confidence"],
        }
        state["history"].append(
            f"[{WORKER_NAME}] answer generated, confidence={result['confidence']}, "
            f"sources={result['sources']}"
        )

    except Exception as e:
        worker_io["error"]    = {"code": "SYNTHESIS_FAILED", "reason": str(e)}
        state["final_answer"] = f"SYNTHESIS_ERROR: {e}"
        state["confidence"]   = 0.0
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("Synthesis Worker — Standalone Test")
    print("=" * 55)

    # Kiểm tra API keys
    keys_found = []
    for k in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"]:
        if os.getenv(k):
            keys_found.append(k)
    print(f"API keys loaded: {keys_found if keys_found else '❌ NONE — kiểm tra .env'}\n")

    # Test 1: SLA query
    test_state = {
        "task": "SLA ticket P1 là bao lâu?",
        "retrieved_chunks": [
            {
                "text": (
                    "Ticket P1: Phản hồi ban đầu 15 phút kể từ khi ticket được tạo. "
                    "Xử lý và khắc phục 4 giờ. Escalation: tự động escalate lên Senior Engineer "
                    "nếu không có phản hồi trong 10 phút."
                ),
                "source": "sla_p1_2026.txt",
                "score":  0.92,
            }
        ],
        "policy_result": {},
    }
    result = run(test_state.copy())
    print(f"▶ Test 1 — SLA query")
    print(f"  Answer    : {result['final_answer'][:200]}")
    print(f"  Sources   : {result['sources']}")
    print(f"  Confidence: {result['confidence']}")

    # Test 2: Exception case
    print()
    test_state2 = {
        "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì lỗi nhà sản xuất.",
        "retrieved_chunks": [
            {
                "text":   "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền theo Điều 3 chính sách v4.",
                "source": "policy_refund_v4.txt",
                "score":  0.88,
            }
        ],
        "policy_result": {
            "policy_applies": False,
            "exceptions_found": [
                {"type": "flash_sale_exception", "rule": "Flash Sale không được hoàn tiền."}
            ],
        },
    }
    result2 = run(test_state2.copy())
    print(f"▶ Test 2 — Flash Sale exception")
    print(f"  Answer    : {result2['final_answer'][:200]}")
    print(f"  Confidence: {result2['confidence']}")

    # Test 3: No context (abstain case)
    print()
    test_state3 = {
        "task": "Câu hỏi không có trong tài liệu nội bộ.",
        "retrieved_chunks": [],
        "policy_result": {},
    }
    result3 = run(test_state3.copy())
    print(f"▶ Test 3 — No context (abstain)")
    print(f"  Answer    : {result3['final_answer'][:200]}")
    print(f"  Confidence: {result3['confidence']}")

    print("\n✅ synthesis_worker test done.")