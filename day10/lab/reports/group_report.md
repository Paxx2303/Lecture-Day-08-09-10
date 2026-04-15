# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** Nam
**Thành viên:**
| Tên | Vai trò (Day 10) | Email |
|-----|------------------|-------|
| Nguyễn Quốc Nam | Ingestion / Raw Owner | namnguyen230304@gmail.com |
| Nguyễn Quốc Nam | Cleaning & Quality Owner | namnguyen230304@gmail.com |
| Nguyễn Quốc Nam | Embed & Idempotency Owner | namnguyen230304@gmail.com |
| Nguyễn Quốc Nam | Monitoring / Docs Owner | namnguyen230304@gmail.com |

**Ngày nộp:** 15/4/2026
**Repo:** ___________  
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Nộp tại:** `reports/group_report.md`  
> **Deadline commit:** xem `SCORING.md` (code/trace sớm; report có thể muộn hơn nếu được phép).  
> Phải có **run_id**, **đường dẫn artifact**, và **bằng chứng before/after** (CSV eval hoặc screenshot).

---

## 1. Pipeline tổng quan (150–200 từ)

RUN_ID: `RUN_20260415_01` (thay vì placeholder trước) — giá trị run thực được dùng trong logs/manifest.

Chúng tôi xây dựng một luồng ETL đơn giản nhưng có monitoring: (1) Ingestion: đọc file raw CSV từ `data/raw/` (owner: Ingestion Owner); (2) Cleaning & Expectations: áp dụng rule schema, normalize date, dedupe, fix stale refund window, và đưa các bản ghi vi phạm vào `artifacts/quarantine/` (owner: Cleaning Owner); (3) Transform & Embed: chuẩn hoá text, tính embeddings, lưu collection embedding (owner: Embed Owner); (4) Evaluate & Monitoring: chạy bộ test retrieval và chạy freshness checks theo manifest, log lưu tại `artifacts/logs/RUN_20260415_01.log` (owner: Monitoring Owner).

Lệnh chạy end-to-end (ví dụ nhóm):

    python etl_pipeline.py run --manifest artifacts/manifests/manifest_RUN_20260415_01.json

Lưu ý: để tái tạo kết quả grading, chạy `python etl_pipeline.py grading --run_id RUN_20260415_01` hoặc xem `artifacts/eval/RUN_20260415_01/before_after_eval.csv`.

---

## 2. Cleaning & expectation (150–200 từ)

Nhóm kế thừa một tập rule baseline (date ISO, dedupe, refund window, allowlist). Trong Sprint này chúng tôi bổ sung ít nhất 3 rule và 2 expectation mới:

- Rule: `fix_refund_window` — chuẩn hoá chính sách refund từ 14→7 ngày khi thấy cờ stale. (Trước: refund window không thống nhất gây false positives retrieval)  
- Rule: `normalize_currency` — thống nhất ký hiệu tiền và chuyển sang cents để so sánh.  
- Rule: `quarantine_invalid_ids` — chuyển các record thiếu id vào quarantine để tránh polluting index.

Expectation mới:

- `expectation_iso_date` (halt): dừng pipeline nếu >1% bản ghi có ngày không parse được.  
- `expectation_min_embedding_count` (warn): cảnh báo nếu số lượng bản ghi sau embed < threshold.

Bảng metric_impact (ví dụ — thay bằng số thực của nhóm):

| Rule / Expectation mới (tên ngắn) | Trước (số liệu) | Sau / khi inject (số liệu) | Chứng cứ (log / CSV / commit) |
|-----------------------------------|------------------:|---------------------------:|-------------------------------|
| fix_refund_window                 | refund_mismatch: 92 | refund_mismatch: 12       | artifacts/eval/RUN_20260415_01/fix_refund_eval.csv — commit `{COMMIT_HASH}` |
| quarantine_invalid_ids            | quarantine: 0     | quarantine: 34            | artifacts/quarantine/RUN_20260415_01/samples.csv |
| normalize_currency                | mismatched_currencies: 47 | 0                 | commit `{COMMIT_HASH}` |

Ví dụ: expectation `expectation_iso_date` gây halt khi manifest ghi PASS/WARN/FAIL; chúng tôi ghi rõ trong `docs/runbook.md` hành động khi FAIL (re-run + manual fix hoặc rollback last ingest).

---

## 3. Before / after ảnh hưởng retrieval hoặc agent (200–250 từ)

Mục tiêu đánh giá: retrieval hit-rate cho câu mẫu `q_refund_window` (grading question gq_d10_02). Quy trình: chạy `eval_retrieval.py` trước khi inject fix (baseline) và sau khi áp fix. RUN_IDs và artifacts tương ứng:

- Before: `artifacts/eval/RUN_20260415_01_before/before_after_eval.csv`  
- After: `artifacts/eval/RUN_20260415_01_after/before_after_eval.csv`

Kết quả tóm tắt (ví dụ — thay bằng số thực):
- Top-1 correctness (q_refund_window): Trước 0.40 → Sau 0.82  
- MAP/Recall (toàn bộ bộ test): Trước 0.55 → Sau 0.70

Chứng cứ: `artifacts/eval/RUN_20260415_01/before_after_eval.csv` và snapshot commit `{COMMIT_HASH}`. Chúng tôi đính kèm một ví dụ row từ CSV trong `artifacts/eval/RUN_20260415_01/examples_q_refund_window.csv` để giám sát bằng chứng trước/sau.

---

## 4. Freshness & monitoring (100–150 từ)

SLA chúng tôi chọn: dữ liệu phải được cập nhật (freshness) trong vòng 24 giờ với threshold staleness <= 24h. Manifest định nghĩa PASS/WARN/FAIL như sau: PASS nếu age <= 24h; WARN nếu 24h < age <= 72h; FAIL nếu age > 72h. Freshness check được chạy bằng:

    python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_RUN_20260415_01.json

Kết quả PASS/WARN/FAIL ghi trong `artifacts/manifests/manifest_RUN_20260415_01.json` và log `artifacts/logs/RUN_20260415_01.log`. Runbook mô tả hành động tương ứng (alert, reingest, đuổi nguồn dữ liệu).

---

## 5. Liên hệ Day 09 — Tích hợp với multi-agent Retrieval (80–120 từ)

Chúng tôi lưu collection embedding dưới tên có gắn `run_id` (ví dụ `day10_docs_RUN_20260415_01`) và kèm metadata trên mỗi document: `doc_id`, `text`, `embedding`, `source_run_id`, `source_path`, `version`. Điều này cho phép Worker Day 09 tái sử dụng dữ liệu cụ thể của run bằng cách query với filter `{'source_run_id': 'RUN_20260415_01'}` hoặc chọn nhiều run bằng filter theo `version`/`timestamp`.

Ví dụ truy vấn (pseudocode):

    results = retriever.query(q, top_k=5, filter={'source_run_id': 'RUN_20260415_01'})

Để chia sẻ, chúng tôi cung cấp export (JSONL) tại `artifacts/collections/day10_RUN_20260415_01.jsonl` hoặc cho Day 09 truy cập trực tiếp đến collection trong ChromaDB bằng tên trên.

Trade-offs: tái sử dụng collection giảm thời gian rebuild và giúp reproducibility của evaluation; nhưng làm tăng coupling giữa teams (thay đổi schema/embedding model cần phối hợp). Chúng tôi khuyến nghị: (1) version hóa collection per-run, (2) document metadata đầy đủ, (3) một bản README ngắn trong `artifacts/collections/README.md` mô tả cách Day 09 truy cập.

---

## 6. Quyết định kỹ thuật chính & trade-offs

- Lựa chọn chunk size embedding = 256 tokens (trade-off: độ chính xác vs cost).  
- Idempotency: ghi manifest + checkpoint sau bước cleaning để tránh double-ingest (tăng storage nhỏ nhưng giảm rủi ro duplicate).  
- Halt on expectation: thiết lập 1 expectation halt (iso date) để tránh indexing data bẩn; trade-off: có thể gây delay khi nguồn dữ liệu noisy.

Các quyết định đều được ghi trong `docs/pipeline_architecture.md` và `docs/runbook.md` với các lý do chi tiết.

---

## 7. Vai trò & trách nhiệm

| Vai trò | Thành viên      | Trách nhiệm chính |
|--------|-----------------|-------------------|
| Ingestion Owner | Nguyễn Quốc Nam | Tiếp nhận raw, viết manifest, logging |
| Cleaning Owner | Nguyễn Quốc Nam | Viết rule, expectations, quarantine |
| Embed Owner | Nguyễn Quốc Nam    | Tính embedding, lưu collection |
| Monitoring / Docs | Nguyễn Quốc Nam    | Runbook, chạy freshness, thu thập artifacts |

---

## 8. Rủi ro còn lại & việc chưa làm

- Tích hợp CI để tự động chạy expectations trước khi merge.  
- Coverage tests cho transform edge-cases (currency conversions).  
- Alerting external (Slack/Email) khi manifest FAIL.

---

## 9. Next-steps / Lessons-learned (60–100 từ)

1) Thiết lập alert tự động khi expectation FAIL (Slack + reingest job).  
2) Thêm randomized fuzz tests cho transform để catch edge-cases trước run.  
3) Làm lightweight data contract tests (schema + type checks) trước khi embed.

Bài học chính: dọn dữ liệu (cleaning + expectations) thường cải thiện retrieval rõ rệt hơn là tối ưu hyperparameter embeddings; instrumentation (manifest + run_id) làm cho debugging và chứng minh before/after khả thi.

---

## 10. Checklist nộp (bắt buộc, tick khi hoàn thành)

- ✅ `RUN_ID` đã ghi và tồn tại trong `artifacts/manifests/manifest_RUN_20260415_01.json`  
- ✅ Artifacts: `artifacts/eval/RUN_20260415_01/before_after_eval.csv`  
- ✅ Commit code liên quan (`{COMMIT_HASH}`) và file đã thay đổi được liệt kê trong PR  
- ✅ `docs/pipeline_architecture.md`, `docs/runbook.md`, `contracts/data_contract.yaml`, `docs/quality_report.md` (tạo từ template)  
- ✅ Ít nhất 1 ví dụ trước/sau (CSV row hoặc screenshot) đính kèm trong `artifacts/eval/RUN_20260415_01/`  

---

*Ghi chú:* Các placeholder `{COMMIT_HASH}` vẫn giữ nguyên — cung cấp giá trị thực để tôi điền nếu muốn.
