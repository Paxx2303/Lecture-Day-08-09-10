# System Architecture — Lab Day 09

**Nhóm:** ___________  
**Ngày:** ___________  
**Version:** 1.1 (Hoàn thiện)

---

## 1. Tổng quan kiến trúc

> Mô tả ngắn hệ thống của nhóm: chọn pattern gì, gồm những thành phần nào.

**Pattern đã chọn:** Supervisor-Worker  
**Lý do chọn pattern này (thay vì single agent):** Supervisor-Worker cho phép tách biệt rõ ràng giữa việc phân tích câu hỏi (routing), truy xuất dữ liệu (retrieval), kiểm tra chính sách (policy_tool), và tổng hợp câu trả lời (synthesis). Pattern này cung cấp khả năng debug tốt hơn, dễ dàng thêm worker mới, và quan sát được routing decision qua trace.

---

## 2. Sơ đồ Pipeline

> Vẽ sơ đồ pipeline dưới dạng text, Mermaid diagram, hoặc ASCII art.
> Yêu cầu tối thiểu: thể hiện rõ luồng từ input → supervisor → workers → output.

**Ví dụ (ASCII art):**
```
User Request
     │
     ▼
┌──────────────┐
│  Supervisor  │  ← route_reason, risk_high, needs_tool
└──────┬───────┘
       │
   [route_decision]
       │
  ┌────┴────────────────────┐
  │                         │
  ▼                         ▼
Retrieval Worker     Policy Tool Worker
  (evidence)           (policy check + MCP)
  │                         │
  └─────────┬───────────────┘
            │
            ▼
      Synthesis Worker
        (answer + cite)
            │
            ▼
         Output
```

**Sơ đồ thực tế của nhóm:**

```
User Request
      │
      ▼
┌────────────────────────────────────────────────────────────┐
│                     Supervisor (graph.py)                  │
│  - Phân tích task, quyết định route                        │
│  - Kiểm tra risk keywords & policy keywords               │
│  - Output: supervisor_route, route_reason, risk_high     │
└──────────────────────────────┬─────────────────────────────┘
                               │
                    [route_decision]
                               │
      ┌────────────────────────┼────────────────────────┐
      ▼                        ▼                        ▼
┌─────────────┐      ┌──────────────────┐      ┌─────────────┐
│  Retrieval │      │  Policy Tool     │      │ Human Review│
│  Worker    │      │  Worker          │      │ (HITL)      │
│ (retrieval)│      │ (policy_tool)    │      │             │
└──────┬──────┘      └────────┬─────────┘      └──────┬──────┘
       │                      │                        │
       └──────────────────────┼────────────────────────┘
                              ▼
┌────────────────────────────────────────────────────────────┐
│                Synthesis Worker (synthesis.py)              │
│  - Tổng hợp chunks + policy_result                        │
│  - Gọi LLM để generate final_answer                       │
│  - Output: final_answer, confidence, sources              │
└──────────────────────────────┬─────────────────────────────┘
                              ▼
                         Output
```

---

## 3. Vai trò từng thành phần

### Supervisor (`graph.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích câu hỏi đầu vào, quyết định route sang worker nào dựa trên keyword matching (policy_keywords, retrieval_priority_keywords, risk_keywords) |
| **Input** | task (câu hỏi từ user) |
| **Output** | supervisor_route, route_reason, risk_high, needs_tool |
| **Routing logic** | Ưu tiên: (1) unknown error + risk → human_review, (2) SLA/ticket/escalation → retrieval_worker, (3) policy/refund/access → policy_tool_worker, (4) default → retrieval_worker |
| **HITL condition** | Khi có unknown error code (ERR-XXXX) kết hợp với risk_keywords như "emergency", "2am", "ngoài giờ" |

### Retrieval Worker (`workers/retrieval.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Dense retrieval từ ChromaDB bằng semantic search (Sentence Transformers hoặc OpenAI embeddings) |
| **Embedding model** | all-MiniLM-L6-v2 (Sentence Transformers) ưu tiên, fallback OpenAI text-embedding-3-small |
| **Top-k** | 3 (default), có thể override qua retrieval_top_k trong state |
| **Stateless?** | Yes - mỗi lần gọi đều query ChromaDB trực tiếp, không giữ context giữa các lần |

### Policy Tool Worker (`workers/policy_tool.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **Nhiệm vụ** | Phân tích policy dựa trên task + retrieved chunks, phát hiện exceptions (Flash Sale, digital product, activated, access control) |
| **MCP tools gọi** | search_kb (khi không có chunks), get_ticket_info (khi task chứa ticket/p1/jira keywords) |
| **Exception cases xử lý** | Flash Sale exception, Digital product exception, Activated product exception, Access control exception |

### Synthesis Worker (`workers/synthesis.py`)

| Thuộc tính | Mô tả |
|-----------|-------|
| **LLM model** | gpt-4o-mini (OpenAI), fallback: Claude Haiku, Gemini |
| **Temperature** | 0.1 (low để giảm hallucination, tăng consistency) |
| **Grounding strategy** | CHỉ trả lời dựa trên context được cung cấp. Nếu không đủ info → abstain với message "Không đủ thông tin trong tài liệu nội bộ" |
| **Abstain condition** | Khi retrieved_chunks rỗng HOẶC answer chứa "không đủ thông tin" → confidence = 0.3 |

### MCP Server (`mcp_server.py`)

| Tool | Input | Output |
|------|-------|--------|
| search_kb | query (str), top_k (int, default 3) | {"chunks": list, "sources": list, "total_found": int} |
| get_ticket_info | ticket_id (str) | {"ticket_id", "priority", "status", "assignee", "sla_deadline", ...} |
| check_access_permission | access_level (int 1-3), requester_role (str), is_emergency (bool) | {"can_grant": bool, "required_approvers": list, "emergency_override": bool} |
| create_ticket | priority (str P1-P4), title (str), description (str) | {"ticket_id": str, "url": str, "created_at": str} |

---

## 4. Shared State Schema

> Liệt kê các fields trong AgentState và ý nghĩa của từng field.

| Field | Type | Mô tả | Ai đọc/ghi |
|-------|------|-------|-----------|
| task | str | Câu hỏi đầu vào từ user | supervisor đọc |
| supervisor_route | str | Worker được chọn (retrieval_worker/policy_tool_worker/human_review) | supervisor ghi, route_decision đọc |
| route_reason | str | Lý do route chi tiết (matched keywords) | supervisor ghi |
| risk_high | bool | True → cần HITL hoặc có risk cao | supervisor ghi, human_review đọc |
| needs_tool | bool | True → cần gọi external tool qua MCP | supervisor ghi, policy_tool đọc |
| hitl_triggered | bool | True → đã pause cho human review | human_review ghi, synthesis đọc |
| retrieved_chunks | list | Evidence từ retrieval_worker (list of {"text", "source", "score", "metadata"}) | retrieval ghi, synthesis đọc |
| retrieved_sources | list | Danh sách nguồn tài liệu (deduplicated) | retrieval ghi, synthesis đọc |
| policy_result | dict | Kết quả kiểm tra policy ({policy_applies, exceptions_found, policy_name, ...}) | policy_tool ghi, synthesis đọc |
| mcp_tools_used | list | Danh sách MCP tools đã gọi (mỗi entry là {tool, input, output, error, timestamp}) | policy_tool ghi |
| final_answer | str | Câu trả lời tổng hợp cuối cùng | synthesis ghi |
| sources | list | Danh sách sources được cite trong final_answer | synthesis ghi |
| confidence | float | Mức tin cậy (0.0 - 1.0), tính dựa trên chunk scores + exception penalty | synthesis ghi |
| history | list | Log các bước đã thực hiện (trace) | tất cả nodes ghi |
| workers_called | list | Danh sách workers đã được gọi trong pipeline | graph ghi |
| latency_ms | int | Thời gian xử lý toàn pipeline (milliseconds) | graph ghi |
| run_id | str | ID unique của mỗi run (format: run_YYYYMMDD_HHMMSS_fff) | make_initial_state ghi |
| timestamp | str | Thời điểm bắt đầu chạy (ISO format) | make_initial_state ghi |
| worker_io_logs | list | Log input/output của từng worker để debug | workers ghi |

---

## 5. Lý do chọn Supervisor-Worker so với Single Agent (Day 08)

| Tiêu chí | Single Agent (Day 08) | Supervisor-Worker (Day 09) |
|----------|----------------------|--------------------------|
| Debug khi sai | Khó — không rõ lỗi ở đâu trong prompt | Dễ hơn — test từng worker độc lập, trace rõ ràng qua history |
| Thêm capability mới | Phải sửa toàn prompt LLM | Thêm worker/MCP tool riêng, không ảnh hưởng worker khác |
| Routing visibility | Không có — LLM tự quyết định | Có route_reason + supervisor_route trong trace |
| Latency | Thấp hơn (1 LLM call) | Cao hơn (nhiều workers + potential MCP calls) |
| Complexity | Đơn giản, ít code | Phức tạp hơn, cần quản lý state + routing |

**Nhóm điền thêm quan sát từ thực tế lab:**
Supervisor-Worker phù hợp với các task có logic rõ ràng (policy check, ticket lookup). Single agent phù hợp với task open-ended không cần structured output. Trong lab, pattern này cho phép dễ dàng thay thế từng worker (placeholder → thực) mà không ảnh hưởng toàn hệ thống.

---

## 6. Giới hạn và điểm cần cải tiến

> Nhóm mô tả những điểm hạn chế của kiến trúc hiện tại.

1. **Keyword-based routing còn thô sơ** — Cần nâng cấp lên LLM-based routing để xử lý các edge cases phức tạp hơn.
2. **Chưa có parallel execution** — Các workers chạy tuần tự (retrieval → policy_tool → synthesis), có thể tối ưu bằng parallel execution cho một số task.
3. **HITL chưa tích hợp UI** — Human review node chỉ log và auto-approve trong lab mode, cần giao diện thực để human xác nhận.
4. **Retry logic chưa có** — Khi worker thất bại (MCP call failed, ChromaDB timeout) không có cơ chế retry tự động.
5. **State không có persistence** — Mỗi run tạo state mới, không lưu lại context giữa các lần chạy (cần Redis hoặc DB nếu muốn session-based).
