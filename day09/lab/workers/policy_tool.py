"""
workers/policy_tool.py — Policy & Tool Worker
Sprint 2+3: Kiểm tra policy dựa vào context, gọi MCP tools khi cần.

Input (từ AgentState):
    - task: câu hỏi
    - retrieved_chunks: context từ retrieval_worker
    - needs_tool: True nếu supervisor quyết định cần tool call

Output (vào AgentState):
    - policy_result: {"policy_applies", "policy_name", "exceptions_found", "source", "rule"}
    - mcp_tools_used: list of tool calls đã thực hiện
    - worker_io_log: log

Gọi độc lập để test:
    python workers/policy_tool.py
"""

import os
import sys
from typing import Optional

# ── Sprint 2 fix: load .env từ gốc project khi chạy độc lập ─────────
try:
    from dotenv import load_dotenv
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(_root, ".env"))
except ImportError:
    pass

WORKER_NAME = "policy_tool_worker"


# ─────────────────────────────────────────────
# MCP Client — Sprint 3: Thay bằng real MCP call
# ─────────────────────────────────────────────

def _call_mcp_tool(tool_name: str, tool_input: dict) -> dict:
    """
    Gọi MCP tool qua mcp_server.dispatch_tool().
    Sprint 3: Thay bằng HTTP client nếu dùng server riêng.
    """
    from datetime import datetime

    try:
        # Thêm thư mục gốc vào sys.path để import mcp_server
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _root not in sys.path:
            sys.path.insert(0, _root)

        from mcp_server import dispatch_tool
        result = dispatch_tool(tool_name, tool_input)
        return {
            "tool":      tool_name,
            "input":     tool_input,
            "output":    result,
            "error":     None,
            "timestamp": datetime.now().isoformat(),
        }
    except ImportError:
        # mcp_server.py chưa có (Sprint 3) → return mock
        return {
            "tool":      tool_name,
            "input":     tool_input,
            "output":    None,
            "error":     {"code": "MCP_NOT_IMPLEMENTED", "reason": "mcp_server.py chưa có (Sprint 3)"},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {
            "tool":      tool_name,
            "input":     tool_input,
            "output":    None,
            "error":     {"code": "MCP_CALL_FAILED", "reason": str(e)},
            "timestamp": datetime.now().isoformat(),
        }


# ─────────────────────────────────────────────
# Policy Analysis Logic
# ─────────────────────────────────────────────

def analyze_policy(task: str, chunks: list) -> dict:
    """
    Phân tích policy dựa trên task + context chunks.

    Rule-based detection (Sprint 2).
    TODO Sprint 2+: Upgrade lên LLM-based analysis nếu cần.

    Returns:
        dict: policy_applies, policy_name, exceptions_found, source,
              policy_version_note, explanation
    """
    task_lower    = task.lower()
    context_text  = " ".join([c.get("text", "") for c in chunks]).lower()

    exceptions_found = []

    # ── Exception 1: Flash Sale ─────────────────────────────────────
    if "flash sale" in task_lower or "flash sale" in context_text:
        exceptions_found.append({
            "type":   "flash_sale_exception",
            "rule":   "Đơn hàng Flash Sale không được hoàn tiền (Điều 3, chính sách v4).",
            "source": "policy_refund_v4.txt",
        })

    # ── Exception 2: Digital product / License / Subscription ───────
    digital_keywords = ["license key", "license", "subscription", "kỹ thuật số"]
    if any(kw in task_lower for kw in digital_keywords):
        exceptions_found.append({
            "type":   "digital_product_exception",
            "rule":   "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền (Điều 3).",
            "source": "policy_refund_v4.txt",
        })

    # ── Exception 3: Activated / Used product ───────────────────────
    activated_keywords = ["đã kích hoạt", "đã đăng ký", "đã sử dụng"]
    if any(kw in task_lower for kw in activated_keywords):
        exceptions_found.append({
            "type":   "activated_exception",
            "rule":   "Sản phẩm đã kích hoạt hoặc đăng ký tài khoản không được hoàn tiền (Điều 3).",
            "source": "policy_refund_v4.txt",
        })

    # ── Exception 4: Access control / Contractor ────────────────────
    access_keywords = ["admin access", "level 3", "elevated access", "contractor", "nhà thầu"]
    if any(kw in task_lower for kw in access_keywords):
        exceptions_found.append({
            "type":   "access_control_exception",
            "rule":   "Cấp quyền Admin/Level 3 cho contractor cần phê duyệt từ IT Manager + Security (SOP v2).",
            "source": "access_control_sop.txt",
        })

    policy_applies = len(exceptions_found) == 0

    # ── Temporal scoping: policy version ────────────────────────────
    policy_name         = "refund_policy_v4"
    policy_version_note = ""
    if any(kw in task_lower for kw in ["31/01", "30/01", "trước 01/02"]):
        policy_version_note = (
            "Đơn hàng đặt trước 01/02/2026 áp dụng chính sách v3 "
            "(không có trong tài liệu hiện tại — cần escalate)."
        )

    sources = list({c.get("source", "unknown") for c in chunks if c})

    return {
        "policy_applies":     policy_applies,
        "policy_name":        policy_name,
        "exceptions_found":   exceptions_found,
        "source":             sources,
        "policy_version_note": policy_version_note,
        "explanation":        (
            f"Rule-based check: {len(exceptions_found)} exception(s) found. "
            "policy_applies=True có nghĩa hoàn tiền được chấp nhận theo điều kiện bình thường."
        ),
    }


# ─────────────────────────────────────────────
# Worker Entry Point
# ─────────────────────────────────────────────

def run(state: dict) -> dict:
    """
    Worker entry point — gọi từ graph.py.

    Args:
        state: AgentState dict

    Returns:
        Updated AgentState với policy_result và mcp_tools_used
    """
    task       = state.get("task", "")
    chunks     = state.get("retrieved_chunks", [])
    needs_tool = state.get("needs_tool", False)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("mcp_tools_used", [])

    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task":        task,
            "chunks_count": len(chunks),
            "needs_tool":  needs_tool,
        },
        "output": None,
        "error":  None,
    }

    try:
        # ── Step 1: Nếu không có chunks + cần tool → MCP search_kb ─
        if not chunks and needs_tool:
            mcp_result = _call_mcp_tool("search_kb", {"query": task, "top_k": 3})
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP search_kb")

            if mcp_result.get("output") and mcp_result["output"].get("chunks"):
                chunks = mcp_result["output"]["chunks"]
                state["retrieved_chunks"] = chunks

        # ── Step 2: Phân tích policy ─────────────────────────────────
        policy_result        = analyze_policy(task, chunks)
        state["policy_result"] = policy_result

        # ── Step 3: Nếu cần ticket info → MCP get_ticket_info ───────
        if needs_tool and any(kw in task.lower() for kw in ["ticket", "p1", "jira"]):
            mcp_result = _call_mcp_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP get_ticket_info")

        worker_io["output"] = {
            "policy_applies":  policy_result["policy_applies"],
            "exceptions_count": len(policy_result.get("exceptions_found", [])),
            "mcp_calls":       len(state["mcp_tools_used"]),
        }
        state["history"].append(
            f"[{WORKER_NAME}] policy_applies={policy_result['policy_applies']}, "
            f"exceptions={len(policy_result.get('exceptions_found', []))}, "
            f"mcp_calls={len(state['mcp_tools_used'])}"
        )

    except Exception as e:
        worker_io["error"]     = {"code": "POLICY_CHECK_FAILED", "reason": str(e)}
        state["policy_result"] = {"error": str(e)}
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("Policy Tool Worker — Standalone Test")
    print("=" * 55)

    test_cases = [
        {
            "name": "Flash Sale refund",
            "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
            "retrieved_chunks": [
                {"text": "Ngoại lệ: Đơn hàng Flash Sale không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.9}
            ],
        },
        {
            "name": "License key activated",
            "task": "Khách hàng muốn hoàn tiền license key đã kích hoạt.",
            "retrieved_chunks": [
                {"text": "Sản phẩm kỹ thuật số (license key, subscription) không được hoàn tiền.", "source": "policy_refund_v4.txt", "score": 0.88}
            ],
        },
        {
            "name": "Normal refund (no exception)",
            "task": "Khách hàng yêu cầu hoàn tiền trong 5 ngày, sản phẩm lỗi nhà sản xuất, chưa kích hoạt.",
            "retrieved_chunks": [
                {"text": "Yêu cầu trong 7 ngày làm việc, sản phẩm lỗi nhà sản xuất, chưa dùng.", "source": "policy_refund_v4.txt", "score": 0.85}
            ],
        },
        {
            "name": "Contractor Admin Access",
            "task": "Contractor cần Admin Access Level 3 để sửa P1 khẩn cấp.",
            "retrieved_chunks": [
                {"text": "Cấp quyền Level 3 yêu cầu phê duyệt IT Manager + Security.", "source": "access_control_sop.txt", "score": 0.87}
            ],
        },
    ]

    for tc in test_cases:
        print(f"\n▶ [{tc['name']}] {tc['task'][:65]}...")
        result = run(tc.copy())
        pr = result.get("policy_result", {})
        print(f"  policy_applies : {pr.get('policy_applies')}")
        exceptions = pr.get("exceptions_found", [])
        if exceptions:
            for ex in exceptions:
                print(f"  exception      : {ex['type']} — {ex['rule'][:60]}...")
        else:
            print(f"  exception      : none")
        if pr.get("policy_version_note"):
            print(f"  version_note   : {pr['policy_version_note'][:70]}...")
        print(f"  MCP calls      : {len(result.get('mcp_tools_used', []))}")

    print("\n✅ policy_tool_worker test done.")