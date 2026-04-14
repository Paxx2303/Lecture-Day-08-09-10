# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Nguyễn Quốc Nam
**Vai trò trong nhóm:** Supervisor Owner / Worker Owner / MCP Owner / Trace & Docs Owner  
**Ngày nộp:** ___________  
**Độ dài yêu cầu:** 500–800 từ

---

> **Lưu ý quan trọng:**
> - Viết ở ngôi **"tôi"**, gắn với chi tiết thật của phần bạn làm
> - Phải có **bằng chứng cụ thể**: tên file, đoạn code, kết quả trace, hoặc commit
> - Nội dung phân tích phải khác hoàn toàn với các thành viên trong nhóm
> - Deadline: Được commit **sau 18:00** (xem SCORING.md)
> - Lưu file với tên: `reports/individual/[ten_ban].md` (VD: `nguyen_van_a.md`)

---

## 1. Tôi phụ trách phần nào? (100–150 từ)
 - Tôi làm hết

**Module/file tôi chịu trách nhiệm:**
- File chính: `graph.py` hoặc `workers/retrieval.py` hoặc `workers/policy_tool.py` hoặc `workers/synthesis.py` hoặc `mcp_server.py`
- Functions tôi implement: `[tên function cụ thể]`

**Cách công việc của tôi kết nối với phần của thành viên khác:**
Mô tả input/output contract với workers khác. Ví dụ: "Supervisor output: supervisor_route → route_decision input. Synthesis input: retrieved_chunks + policy_result."

**Bằng chứng (commit hash, file có comment tên bạn, v.v.):**
`[PASTE COMMIT HOẶC CODE RELEVANT]`

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

> Chọn **1 quyết định** bạn trực tiếp đề xuất hoặc implement trong phần mình phụ trách.
> Giải thích:
> - Quyết định là gì?
> - Các lựa chọn thay thế là gì?
> - Tại sao bạn chọn cách này?
> - Bằng chứng từ code/trace cho thấy quyết định này có effect gì?

**Quyết định:**
[MÔ TẢ QUYẾT ĐỊNH CỤ THỂ BẠN ĐÃ RA]

**Ví dụ:**
> "Tôi chọn dùng keyword-based routing trong supervisor_node thay vì gọi LLM để classify.
>  Lý do: keyword routing nhanh hơn (~5ms vs ~800ms) và đủ chính xác cho 5 categories.
>  Bằng chứng: trace gq01 route_reason='task contains P1 SLA keyword', latency=45ms."

**Lý do:**
[GIẢI THÍCH TẠI SAO CHỌN CÁCH NÀY]

**Trade-off đã chấp nhận:**
[NHỮNG TRADE-OFF/ĐÁNH ĐỔI CỦA QUYẾT ĐỊNH]

**Bằng chứng từ trace/code:**

```
[PASTE ĐOẠN CODE HOẶC TRACE RELEVANT VÀO ĐÂY]
```

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

> Mô tả 1 bug thực tế bạn gặp và sửa được trong lab hôm nay.
> Phải có: mô tả lỗi, symptom, root cause, cách sửa, và bằng chứng trước/sau.

**Lỗi:**
[MÔ TẢ LỖI CỤ THỂ]

**Symptom (pipeline làm gì sai?):**
[THORNG BÁO LỖI HOẶC OUTPUT SAI]

**Root cause (lỗi nằm ở đâu — indexing, routing, contract, worker logic?):**
[NGUYÊN NHÂN GỐC TÌM ĐƯỢC]

**Cách sửa:**
[CODE THAY ĐỔI HOẶC LOGIC SỬA]

**Bằng chứng trước/sau:**
> Dán trace/log/output trước khi sửa và sau khi sửa.

```
[OUTPUT TRƯỚC]
...
[OUTPUT SAU]
```

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

> Trả lời trung thực — không phải để khen ngợi bản thân.

**Tôi làm tốt nhất ở điểm nào?**
[ĐIỂM MẠNH CỦA BẠN]

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**
[ĐIỂM YẾU CẦN CẢI THIỆN]

**Nhóm phụ thuộc vào tôi ở đâu?** _(Phần nào của hệ thống bị block nếu tôi chưa xong?)_
[DEPENDENCIES TỪ NHÓM]

**Phần tôi phụ thuộc vào thành viên khác:** _(Tôi cần gì từ ai để tiếp tục được?)_
[DEPENDENCIES VỚI THÀNH VIÊN KHÁC]

---

## 6. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

> Nêu **đúng 1 cải tiến** với lý do có bằng chứng từ trace hoặc scorecard.
> Không phải "làm tốt hơn chung chung" — phải là:
> *"Tôi sẽ thử X vì trace của câu gq___ cho thấy Y."*

[ĐÚNG 1 CẢI TIẾN CỤ THỂ VỚI LÝ DO CÓ BẰNG CHỨNG]

Ví dụ: "Tôi sẽ build ChromaDB index đầy đủ vì gq01, gq05, gq08 đều abstain do retrieved_chunks=[]. File sla_p1_2026.txt và it_helpdesk_faq.txt chưa được index."

---

## Bảng tổng hợp điểm grading (tự điền sau khi chạy pipeline)

| Câu ID | Điểm  | Route | Workers | MCP | Confidence | Ghi chú |
|--------|-------|--------|---------|-----|------------|---------|
| gq01 | 8/10  | retrieval | 2 | 0 | 0.30 | Partial - thiếu data |
| gq02 | 9 /10 | policy_tool | 3 | 0 | 0.30 | Partial - đúng abstain version |
| gq03 | 10/10 | policy_tool | 3 | 1 | 0.20 | ✓ Đúng |
| gq04 | 6/6   | policy_tool | 3 | 0 | 0.22 | ✓ Đúng 110% |
| gq05 | 8/8   | retrieval | 2 | 0 | 0.30 | Abstain - thiếu data |
| gq06 | 8/8   | retrieval | 2 | 0 | 0.23 | ✓ Đúng |
| gq07 | 10/10 | retrieval | 2 | 0 | 0.30 | ✓ Đúng abstain |
| gq08 | 8/8   | retrieval | 2 | 0 | 0.30 | ✓ Đúng |
| gq09 | 13/16 | policy_tool | 3 | 1 | 0.30 | Partial - thiếu data |
| gq10 | 10/10 | policy_tool | 3 | 0 | 0.11 | ✓ Đúng Flash Sale exception |

**Tổng:** 58/96 điểm

---

*Lưu file này với tên: `reports/individual/[ten_ban].md`*  
*Ví dụ: `reports/individual/nguyen_van_a.md`*
