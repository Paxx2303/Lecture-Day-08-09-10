# Routing Decisions Log — Lab Day 09

**Nhóm:** [Tên nhóm của bạn]  
**Ngày:** 14/04/2026

> Ghi lại ít nhất 3 quyết định routing thực tế từ trace (`artifacts/traces/`).

---

## Routing Decision #1

**Task đầu vào:**
> "Ticket P1 lúc 2am — escalation xảy ra thế nào và ai nhận thông báo?"

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `task contains P1 and escalation keyword → ưu tiên retrieval_worker`  
**MCP tools được gọi:** Không (hoặc search_kb nếu có)  
**Workers called sequence:** `retrieval_worker → synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): Ticket P1-LATEST đã escalated, notifications gửi qua Slack, email và PagerDuty.
- confidence: 0.27
- Correct routing? **Yes**

**Nhận xét:**  
Routing hợp lý vì câu hỏi tập trung vào thông tin ticket và SLA. Tuy nhiên confidence chỉ 0.27 cho thấy supervisor chưa tự tin cao.

---

## Routing Decision #2

**Task đầu vào:**
> "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — policy nào áp dụng?"

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `task contains "hoàn tiền", "refund", "Flash Sale" → policy_tool_worker`  
**MCP tools được gọi:** `search_kb` (refund policy flash sale)  
**Workers called sequence:** `retrieval_worker → policy_tool_worker → synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): Flash Sale + sản phẩm kỹ thuật số thường không hoàn tiền trừ lỗi kỹ thuật được chứng minh.
- confidence: 0.30
- Correct routing? **Yes**

**Nhận xét:**  
Routing đúng và thể hiện được lợi ích của policy_tool_worker + MCP. Đây là trường hợp cần kiểm tra exception policy.

---

## Routing Decision #3

**Task đầu vào:**
> "Contractor cần Admin Access (Level 3) để khắc phục sự cố P1 đang xảy ra — quy trình tạm thời là gì?"

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `task contains "Admin Access", "Level 3", "emergency", "contractor" → policy_tool_worker`  
**MCP tools được gọi:** `check_access_permission` (access_level=3, is_emergency=True)  
**Workers called sequence:** `retrieval_worker → policy_tool_worker → synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): Level 3 không hỗ trợ emergency bypass. Phải có approval từ Line Manager + IT Admin + IT Security.
- confidence: 0.27
- Correct routing? **Yes**

**Nhận xét:**  
Routing rất phù hợp. MCP tool `check_access_permission` giúp trả về rule chính xác từ access_control_sop.

---

## Routing Decision #4 (bonus — trường hợp HITL)

**Task đầu vào:**
> "ERR-403-AUTH là lỗi gì và cách xử lý?"

**Worker được chọn:** `retrieval_worker` (sau khi auto-approve HITL)  
**Route reason:** `unknown_error_code + risk_high → human review required → Auto-approving (lab mode) → continue with retrieval`  
**MCP tools được gọi:** Không  
**Workers called sequence:** `retrieval_worker → synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): [Answer từ retrieval về lỗi auth]
- confidence: 0.30
- Correct routing? **Partial** (HITL đã được trigger)

**Nhận xét:** Đây là trường hợp routing khó nhất. Supervisor phát hiện unknown error code nên trigger HITL. Trong lab mode hệ thống tự approve và fallback retrieval. Nhóm nên cải tiến prompt supervisor để nhận diện error code tốt hơn hoặc route sang policy_tool/human_review sớm hơn.

---

## Tổng kết

### Routing Distribution

| Worker              | Số câu được route | % tổng |
|---------------------|-------------------|--------|
| retrieval_worker    | 71                | 52%    |
| policy_tool_worker  | 65                | 47%    |
| human_review        | ~0 (chỉ HITL)     | ~1%    |

### Routing Accuracy

- Câu route đúng: **13 / 15** (ước tính dựa trên keyword và kết quả)
- Câu route sai / không tối ưu: **2** (câu hỏi mơ hồ + error code → trigger HITL)
- Câu trigger HITL: **1** (trong 15 câu chạy) → theo trace tổng thể là 12%

### Lesson Learned về Routing

1. Keyword-based routing hoạt động khá tốt với các câu chứa "P1", "refund", "hoàn tiền", "Level 3", "emergency", nhưng confidence trung bình rất thấp (~0.19–0.30). Supervisor cần prompt tốt hơn hoặc dùng LLM classifier mạnh hơn.
2. MCP integration (search_kb + check_access_permission) giúp policy_tool_worker mạnh và traceable rõ ràng. Nên ưu tiên dùng MCP thay vì truy cập ChromaDB trực tiếp trong worker.

### Route Reason Quality

Các `route_reason` hiện tại khá dễ hiểu (ví dụ: chứa keyword cụ thể hoặc "unknown_error_code_detected").  
**Cải tiến đề xuất:**  
- Thêm confidence score của chính supervisor vào route_reason.  
- Liệt kê rõ keywords đã match và rule được kích hoạt.  
- Khi confidence < 0.4 → tự động trigger HITL hoặc fallback an toàn hơn.

---

**Ghi chú:**  
- Confidence trung bình toàn bộ run chỉ **0.192** → đây là điểm yếu lớn nhất hiện tại của supervisor. Nhóm nên tập trung tinh chỉnh prompt routing và thêm ví dụ few-shot tốt hơn.  
- Latency trung bình ~8 giây do load Sentence Transformers nhiều lần → có thể cache embedding model để tối ưu.
