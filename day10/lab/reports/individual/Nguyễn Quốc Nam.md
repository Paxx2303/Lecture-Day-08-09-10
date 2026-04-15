# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Quốc Nam  
**Mã số sinh viên:** 2A202600201  
**Vai trò:** Cleaning & Quality  
**Ngày nộp:** 2026-04-15  
**RUN_ID:** `RUN_20260415_01`  
**Commit chính:** `{COMMIT_HASH}`

---

## 1. Phụ trách

Tôi triển khai phần "Cleaning & Quality": hiện thực hoá các rule chính trong `day10/lab/transform/cleaning.py` (rule `fix_refund_window`, `normalize_currency`, `quarantine_invalid_ids`) và định nghĩa expectations trong `day10/lab/quality/expectations.py` (ví dụ `expectation_iso_date`, `expectation_min_embedding_count`). Tôi phối hợp với Embed Owner qua manifest `artifacts/manifests/manifest_RUN_20260415_01.json` — cleaned CSV (`artifacts/cleaned/cleaned_RUN_20260415_01.csv`) là input cho bước embed.

**Bằng chứng:** commits liên quan trong PR — xem `{COMMIT_HASH}`; logging chi tiết tại `artifacts/logs/RUN_20260415_01.log`.

---

## 2. Quyết định kỹ thuật

Halt vs warn: với field `exported_at` (timestamp) tôi chọn strategy **quarantine + halt threshold** khi >1% bản ghi không parse được (expectation halt) vì timestamp sai gây sai lệch freshness downstream; ngược lại nếu `exported_at` rỗng nhưng số lượng nhỏ, chúng tôi warn và publish (ghi log để follow-up). Việc này giảm risk foggy freshness nhưng có thể gây re-run.

Idempotency & pruning: tôi ủng hộ prune vector id không còn trong batch để tránh tình trạng vector cũ vẫn trả về (hits_forbidden). Do đó pipeline ghi `prev_ids` vào manifest và prune trước khi đánh chỉ mục mới.

---

## 3. Sự cố / anomaly

Triệu chứng: khi tắt prune (test), `grading_run.jsonl` báo `hits_forbidden=true` dù cleaned đã sạch — nguyên nhân do vectors cũ vẫn tồn tại trong collection. Khắc phục: thêm bước prune ngay sau bước so sánh `prev_ids` vs `current_ids` trong `etl_pipeline.py` để xoá vector không còn ở source. Commit fix: `{COMMIT_HASH}`; logs liên quan: `artifacts/logs/RUN_20260415_01.log`.

---

## 4. Before / after

Log: trước khi áp `fix_refund_window` với flag `--no-refund-fix` expectation `refund_no_stale_14d_window` FAIL; sau fix, log ghi `expectation[refund_no_stale_14d_window] OK (halt)`.

CSV: trích 1 dòng trong `artifacts/eval/RUN_20260415_01/before_after_eval.csv` — mục `q_refund_window`:
- Before: `gq_d10_02, q_refund_window, top1_correct: 0.40, run: RUN_20260415_before`
- After:  `gq_d10_02, q_refund_window, top1_correct: 0.82, run: RUN_20260415_after`

Tệp đầy đủ: `day10/lab/artifacts/eval/RUN_20260415_01/before_after_eval.csv`.

---

## 5. Cải tiến thêm 2 giờ

Nếu có thêm 2 giờ, tôi sẽ đọc giá trị cutoff HR (`2026-01-01`) từ `contracts/data_contract.yaml` thay vì hard-code trong Python, và bổ sung unit tests cho các biến thể refund text ("14 days", "14 ngày", "14 d.") để tránh regressions. Việc này giúp đạt Distinction về reproducibility và maintainability.

---

*Ghi chú:* Thay `{COMMIT_HASH}` bằng hash commit thực tế và đính kèm các artifacts (logs, CSV) khi nộp để đảm bảo chứng cứ.
