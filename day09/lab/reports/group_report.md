# Báo Cáo Nhóm — Lab Day 09: Multi-Agent Orchestration

**Tên nhóm:** Nguyễn Quốc Nam 
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Nguyễn Quốc Nam | Supervisor Owner | ___ |
| Nguyễn Quốc Nam | Worker Owner | ___ |
| Nguyễn Quốc Nam | MCP Owner | ___ |
| Nguyễn Quốc Nam | Trace & Docs Owner | ___ |

**Ngày nộp:** ___________  
**Repo:** ___________  
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Hướng dẫn nộp group report:**
> 
> - File này nộp tại: `reports/group_report.md`
> - Deadline: Được phép commit **sau 18:00** (xem SCORING.md)
> - Tập trung vào **quyết định kỹ thuật cấp nhóm** — không trùng lặp với individual reports
> - Phải có **bằng chứng từ code/trace** — không mô tả chung chung
> - Mỗi mục phải có ít nhất 1 ví dụ cụ thể từ code hoặc trace thực tế của nhóm

---

## 1. Kiến trúc nhóm đã xây dựng (150–200 từ)

> Mô tả ngắn gọn hệ thống nhóm: bao nhiêu workers, routing logic hoạt động thế nào,
> MCP tools nào được tích hợp. Dùng kết quả từ `docs/system_architecture.md`.

**Hệ thống tổng quan:**
Hệ thống Supervisor-Worker gồm 4 thành phần chính: (1) Supervisor trong `graph.py` phân tích câu hỏi và quyết định route, (2) Retrieval Worker truy xuất evidence từ ChromaDB, (3) Policy Tool Worker kiểm tra policy/exceptions và gọi MCP tools, (4) Synthesis Worker tổng hợp câu trả lời cuối bằng LLM. Toàn bộ pipeline điều khiển qua `AgentState` shared state với 18 fields.

**Routing logic cốt lõi:**
> Mô tả logic supervisor dùng để quyết định route (keyword matching, LLM classifier, rule-based, v.v.)

Supervisor dùng **keyword-based routing** với 3 danh sách từ khóa: `POLICY_KEYWORDS` (hoàn tiền, license, access, v.v.), `RETRIEVAL_PRIORITY_KEYWORDS` (SLA, ticket, escalation, P1, v.v.), và `RISK_KEYWORDS` (emergency, 2am, bypass, v.v.). Thứ tự ưu tiên: (1) unknown error code + risk → human_review, (2) SLA/ticket/escalation → retrieval_worker, (3) policy/refund/access → policy_tool_worker, (4) default → retrieval_worker.

**MCP tools đã tích hợp:**
> Liệt kê tools đã implement và 1 ví dụ trace có gọi MCP tool.

- `search_kb`: Semantic search trên ChromaDB, query + top_k → chunks, sources
- `get_ticket_info`: Tra cứu ticket từ mock database (P1-LATEST, IT-1234)
- `check_access_permission`: Kiểm tra quyền access level 1-3 theo SOP
- `create_ticket`: Tạo ticket mock mới (priority, title, description)

---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

> Chọn **1 quyết định thiết kế** mà nhóm thảo luận và đánh đổi nhiều nhất.
> Phải có: (a) vấn đề gặp phải, (b) các phương án cân nhắc, (c) lý do chọn phương án đã chọn.

**Quyết định:** Keyword-based routing trong Supervisor thay vì LLM-based classification

**Bối cảnh vấn đề:**
Cần quyết định câu hỏi user nên được route đến worker nào (retrieval/policy_tool/human_review). Nếu dùng LLM để classify, mỗi lần routing tốn ~800ms và chi phí API. Nếu dùng rule-based thì nhanh hơn nhưng có thể missedge cases.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Keyword-based routing | Nhanh (~5ms), không tốn API cost, dễ debug trace | Miss edge cases, cần maintain keyword lists |
| LLM classification | Hiểu context tốt hơn, linh hoạt | Chậm (~800ms), tốn chi phí, khó debug |
| Hybrid (keyword → LLM fallback) | Cân bằng speed và accuracy | Phức tạp hơn, 2 steps |

**Phương án đã chọn và lý do:**
Chọn **keyword-based routing** vì: (1) Đủ chính xác cho 5 categories trong lab, (2) Trace rõ ràng với route_reason chứa matched keywords, (3) Latency thấp cho phép test nhanh nhiều cases, (4) Dễ debug và modify trong lab mode.

**Bằng chứng từ trace/code:**
> Dẫn chứng cụ thể (VD: route_reason trong trace, đoạn code, v.v.)

```
# graph.py:125-216 - supervisor_node routing logic
route_reason = f"policy_keywords={policy_matched} override retrieval"
# Trace output:
# [supervisor] decision: route=policy_tool_worker | needs_tool=True | reason=policy_keywords=['hoàn tiền', 'flash sale']
```

---

## 3. Kết quả grading questions (150–200 từ)

> Sau khi chạy pipeline với grading_questions.json (public lúc 17:00):
> - Nhóm đạt bao nhiêu điểm raw?
> - Câu nào pipeline xử lý tốt nhất?
> - Câu nào pipeline fail hoặc gặp khó khăn?

**Tổng điểm raw ước tính:** 58 / 96

**Câu pipeline xử lý tốt nhất:**
- ID: gq03 — Lý do tốt: Đúng 3 người phê duyệt (Line Manager, IT Admin, IT Security), IT Security là người phê duyệt cuối cùng
- ID: gq04 — Lý do tốt: Đúng 110% store credit  
- ID: gq06 — Lý do tốt: Đúng điều kiện probation period không được remote, tối đa 2 ngày/tuần, cần Team Lead phê duyệt
- ID: gq10 — Lý do tốt: Đúng Flash Sale exception không được hoàn tiền theo Điều 3 v4

**Câu pipeline fail hoặc partial:**
- ID: gq01 — Fail ở đâu: Abstain thay vì trích xuất đủ 3 kênh notification (Slack, email, PagerDuty) + escalation time + Senior Engineer  
  Root cause: ChromaDB không có data đầy đủ về SLA notification channels
- ID: gq05 — Fail ở đâu: Abstain thay vì nêu auto-escalate to Senior Engineer
  Root cause: Retrieval không lấy được evidence đầy đủ
- ID: gq08 — Fail ở đâu: Abstain thay vì trích xuất số ngày đổi mật khẩu + cảnh báo trước
  Root cause: it_helpdesk_faq.txt chưa được index vào ChromaDB
- ID: gq09 — Fail ở đâu: Partial - đề cập Level 2 bypass nhưng sai "Tech Lead" thay vì "Line Manager + IT Admin on-call"
  Root cause: Data access_control_sop.md chưa index đầy đủ

**Câu gq07 (abstain):**
Pipeline có abstain strategy: synthesis trả lời "Không đủ thông tin trong tài liệu nội bộ" khi retrieved_chunks rỗng, confidence = 0.3.

**Câu gq09 (multi-hop khó nhất):**
Multi-hop yêu cầu gọi sequential: retrieval_worker → policy_tool_worker → synthesis. Policy tool worker gọi MCP search_kb và get_ticket_info. Kết quả phụ thuộc vào ChromaDB có data và MCP server hoạt động.

---

## 4. So sánh Day 08 vs Day 09 — Điều nhóm quan sát được (150–200 từ)

> Dựa vào `docs/single_vs_multi_comparison.md` — trích kết quả thực tế.

**Metric thay đổi rõ nhất (có số liệu):**
- Routing distribution: 60% retrieval_worker, 40% policy_tool_worker (từ grading run)
- Confidence trung bình: 0.245 (thấp do nhiều abstain)
- Latency trung bình: ~6000ms/câu (cao hơn Day 08 ~1200ms do multi-step retrieval + policy)
- MCP usage rate: 2/10 = 20% (chỉ gq03 và gq09 dùng get_ticket_info)

**Điều nhóm bất ngờ nhất khi chuyển từ single sang multi-agent:**
Pipeline tự động abstain ("Không đủ thông tin") khi không tìm thấy evidence - đây là behavior đúng nhưng confidence thấp (0.3). Một số câu hỏi chứa keyword "emergency" route về policy_tool thay vì retrieval (gq09), đúng nhưng cần cross-doc.

**Trường hợp multi-agent KHÔNG giúp ích hoặc làm chậm hệ thống:**
- gq01, gq05, gq07, gq08: abstain dù có routing đúng (retrieval priority keywords) → Retrieval workers không có data trong ChromaDB, multi-agent overhead không cần thiết.
- gq09: multi-hop câu hỏi nhưng policy_tool chỉ lấy được partial info → vẫn cần improve data indexing.

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

> Đánh giá trung thực về quá trình làm việc nhóm.

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Nguyễn Quốc Nam | Supervisor + Routing logic (graph.py, supervisor_node) + Chạy grading | Sprint 1 |
| ___ | Retrieval Worker (workers/retrieval.py, ChromaDB integration) | Sprint 2 |
| ___ | Policy Tool Worker + MCP Server (workers/policy_tool.py, mcp_server.py) | Sprint 2-3 |
| ___ | Synthesis Worker (workers/synthesis.py, LLM integration) | Sprint 2 |

**Điều nhóm làm tốt:**
- Keyword-based routing hoạt động đúng cho phần lớn câu hỏi (gq03, gq04, gq06, gq10 đúng)
- Abstain strategy hoạt động tốt cho gq07 (anti-hallucination đúng)
- Pipeline không crash, chạy hết 10 câu trong ~77 giây

**Điều nhóm làm chưa tốt hoặc gặp vấn đề về phối hợp:**
- ChromaDB thiếu data: sla_p1_2026.txt, it_helpdesk_faq.txt, policy_refund_v4.txt chưa index đầy đủ
- Keyword lists cần manual update cho edge cases
- MCP server chạy local cần resolve import path

**Nếu làm lại, nhóm sẽ thay đổi gì trong cách tổ chức?**
Index đầy đủ tất cả documents (SLA, policy, FAQ, access control SOP) vào ChromaDB trước Sprint 2, không chờ Sprint 3. Thêm fallback route cho LLM-based classification khi keyword không match.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì? (50–100 từ)

> 1–2 cải tiến cụ thể với lý do có bằng chứng từ trace/scorecard.

1. **Thêm LLM-based routing fallback**: Khi keyword không match, gọi LLM classify thay vì default về retrieval. Bằng chứng: một số câu fail vì routing sai.
2. **Build ChromaDB data đầy đủ**: Index thêm policy documents, SLA docs, access control SOP để retrieval có evidence tốt hơn. Bằng chứng: nhiều câu gqXX có retrieved_chunks=[].
3. **Thêm retry logic cho MCP calls**: Khi MCP tool fail (timeout, connection error) không có retry, làm một số grading question fail.

---

*File này lưu tại: `reports/group_report.md`*  
*Commit sau 18:00 được phép theo SCORING.md*
