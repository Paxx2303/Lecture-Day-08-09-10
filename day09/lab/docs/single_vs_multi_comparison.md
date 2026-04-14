# Single Agent vs Multi-Agent Comparison — Lab Day 09

**Nhóm:** [Tên nhóm của bạn]  
**Ngày:** 14/04/2026

> So sánh Day 08 (Single-agent RAG) với Day 09 (Supervisor + Workers + MCP).

---

## 1. Metrics Comparison

| Metric                  | Day 08 (Single Agent) | Day 09 (Multi-Agent) | Delta          | Ghi chú |
|-------------------------|-----------------------|----------------------|----------------|---------|
| Avg confidence          | 0.72                  | 0.192                | -0.528         | Confidence giảm mạnh |
| Avg latency (ms)        | 1250                  | 8024                 | +6774          | Tăng đáng kể do multiple calls + model load |
| Abstain rate (%)        | 15%                   | ~12% (HITL rate)     | -3%            | HITL thay thế cho abstain |
| Multi-hop accuracy      | 35%                   | N/A (chưa đo chi tiết) | N/A          | Cần đo lại |
| Routing visibility      | ✗ Không có            | ✓ Có route_reason    | +100%          | Cải thiện lớn về debug |
| Debug time (estimate)   | 15–20 phút            | 4–7 phút             | -10 phút       | Dễ trace hơn nhiều |
| MCP / Tool extensibility| ✗ Không có            | ✓ Có                 | +100%          | Dễ thêm tool mới |

**Ghi chú:** Day 08 baseline lấy từ kết quả cũ. Day 09 lấy từ `eval_trace.py` run 15 questions.

---

## 2. Phân tích theo loại câu hỏi

### 2.1 Câu hỏi đơn giản (single-document)

| Nhận xét       | Day 08          | Day 09             |
|----------------|-----------------|--------------------|
| Accuracy       | Tốt             | Trung bình         |
| Latency        | Nhanh (~1.2s)   | Chậm (~5–8s)       |
| Observation    | Trả lời trực tiếp từ 1 chunk | Phải qua retrieval → synthesis, đôi khi confidence thấp |

**Kết luận:** Multi-agent **chưa cải thiện** cho câu hỏi đơn giản. Thậm chí chậm và confidence thấp hơn do overhead của supervisor + multiple workers.

---

### 2.2 Câu hỏi multi-hop (cross-document)

| Nhận xét          | Day 08       | Day 09                  |
|-------------------|--------------|-------------------------|
| Accuracy          | Thấp (35%)   | Trung bình              |
| Routing visible?  | ✗            | ✓ Có (policy_tool_worker) |
| Observation       | Dễ hallucinate | Có thể dùng MCP + policy check |

**Kết luận:** Multi-agent **có tiềm năng tốt hơn** ở câu multi-hop nhờ policy_tool_worker và MCP tools (search_kb, check_access_permission), nhưng hiện tại confidence vẫn thấp nên chưa phát huy hết lợi thế.

---

### 2.3 Câu hỏi cần abstain / xử lý exception

| Nhận xét            | Day 08       | Day 09                          |
|---------------------|--------------|---------------------------------|
| Abstain rate        | 15%          | 12% (HITL trigger)              |
| Hallucination cases | Cao          | Thấp hơn (có route_reason)      |
| Observation         | Hay trả lời sai | Trigger HITL khi unknown error code |

**Kết luận:** Day 09 xử lý tốt hơn nhờ cơ chế HITL (dù hiện đang auto-approve trong lab mode). Giảm nguy cơ hallucinate khi gặp lỗi lạ (ví dụ: ERR-403-AUTH).

---

## 3. Debuggability Analysis

### Day 08 — Debug workflow
Khi answer sai → phải đọc toàn bộ monolithic RAG pipeline → đoán lỗi nằm ở retrieval hay generation.
Không có trace → khó biết bắt đầu từ đâu.
Thời gian ước tính: 15 phút
### Day 09 — Debug workflow
Khi answer sai → mở trace → xem supervisor_route + route_reason
→ Route sai? → sửa supervisor_node
→ Worker sai? → test retrieval_worker / policy_tool_worker độc lập
→ Synthesis sai? → kiểm tra prompt + sources
Thời gian ước tính: 4–7 phút


**Câu cụ thể nhóm đã debug:**  
Câu hỏi "ERR-403-AUTH là lỗi gì và cách xử lý?" → Supervisor trigger HITL vì unknown_error_code. Nhờ trace nên dễ dàng thấy vấn đề nằm ở routing logic (chưa xử lý tốt error code). Sau đó điều chỉnh rule để route sang policy_tool_worker hoặc human_review.

---

## 4. Extensibility Analysis

| Scenario                    | Day 08                          | Day 09                                      |
|-----------------------------|---------------------------------|---------------------------------------------|
| Thêm 1 tool/API mới         | Phải sửa toàn bộ prompt         | Thêm MCP tool + cập nhật routing rule       |
| Thêm 1 domain mới           | Sửa lớn pipeline                | Thêm worker mới hoặc mở rộng policy_worker  |
| Thay đổi retrieval strategy | Sửa trực tiếp trong code chính  | Chỉ sửa retrieval_worker                    |
| A/B test một phần           | Rất khó                         | Dễ — swap worker hoặc thay đổi route logic  |

**Nhận xét:**  
Multi-agent vượt trội hoàn toàn về khả năng mở rộng và bảo trì.

---

## 5. Cost & Latency Trade-off

| Scenario         | Day 08 calls | Day 09 calls          |
|------------------|--------------|-----------------------|
| Simple query     | 1 LLM call   | 2–3 LLM calls         |
| Complex query    | 1 LLM call   | 3–4 LLM calls + MCP   |
| MCP tool call    | N/A          | +1 tool call          |

**Nhận xét về cost-benefit:**  
Day 09 tốn nhiều token và thời gian hơn (latency tăng gấp 6–7 lần). Tuy nhiên đổi lại là **debuggability**, **traceability** và **extensibility** tốt hơn rất nhiều. Phù hợp khi hệ thống cần maintain lâu dài và thêm nhiều capability.

---

## 6. Kết luận

**Multi-agent tốt hơn single agent ở điểm nào?**

1. **Debuggability & Traceability** cực kỳ tốt nhờ trace chi tiết, route_reason và worker_io_log.
2. **Extensibility** cao — dễ thêm tool qua MCP và mở rộng worker mà không ảnh hưởng toàn hệ thống.
3. Xử lý exception và policy check rõ ràng hơn (nhờ policy_tool_worker + MCP).

**Multi-agent kém hơn hoặc không khác biệt ở điểm nào?**

1. **Confidence score** thấp hơn nhiều (0.192 so với 0.72) → supervisor routing chưa ổn định.
2. **Latency** cao hơn đáng kể do nhiều bước và load model lặp lại.
3. Với câu hỏi đơn giản thì overhead không đáng có.

**Khi nào KHÔNG nên dùng multi-agent?**

- Khi hệ thống chỉ xử lý câu hỏi đơn giản, cần tốc độ nhanh và chi phí thấp.
- Khi đội ngũ chưa quen với orchestration và tracing.
- Prototype giai đoạn đầu muốn nhanh.

**Nếu tiếp tục phát triển hệ thống này, nhóm sẽ thêm gì?**

1. Cải thiện prompt supervisor (thêm few-shot examples) để tăng confidence.
2. Cache embedding model và ChromaDB client để giảm latency.
3. Triển khai MCP client async đúng chuẩn trong policy_tool_worker.
4. Thêm evaluator worker để tự động tính confidence và quyết định HITL.
5. Xây dựng dashboard xem trace trực quan.

---
