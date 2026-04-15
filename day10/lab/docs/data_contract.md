# Data contract — Lab Day 10

> Bắt đầu từ `contracts/data_contract.yaml` — mở rộng và đồng bộ file này.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn                   | Phương thức ingest | Failure mode chính | Metric / alert |
|-------------------------|-------------------|-------------------|----------------|
| policy_export_dirty.csv | CSV ingest từ data/raw/ | Duplicate chunk_id (row 1-2), empty chunk_text (row 5), invalid date format (row 10: DD/MM/YYYY), stale refund 14→7 window (row 3), HR stale policy 10→12 ngày (row 7 vs 8) | quarantine_records count, raw_records count |
| access_control_sop.txt  | Manual copy từ data/docs/ | Legacy mapping | doc_id allowlist |
| hr_leave_policy.txt     | Manual copy từ data/docs/ | Version conflict: 2025 (10 ngày) vs 2026 (12 ngày) | stale_hr_policy_effective_date |
| sla_p1_2026.txt         | Manual copy từ data/docs/ | Standard formatting | doc_id allowlist |
| policy_refund_v4.txt   | Manual copy từ data/docs/ | Stale window 14 ngày → 7 ngày | _refund_fix_applied flag |

**Source map details (Sprint 1):**
- Nguồn chính: `data/raw/policy_export_dirty.csv` — export từ hệ thống policy DB
- Backup sources: Các .txt files trong `data/docs/` (kế thừa từ Day 09)
- Failure modes đã xác định:
  1. **Duplicate**: rows 1-2 có cùng chunk_text
  2. **Empty data**: row 5 có chunk_text rỗng
  3. **Invalid date**: row 10 có effective_date = "01/02/2026" (DD/MM/YYYY không chuẩn)
  4. **Stale refund**: row 3 có "14 ngày làm việc" (bản cũ v3)
  5. **HR conflict**: row 7 = 10 ngày (2025), row 8 = 12 ngày (2026) — conflict version |


---

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| chunk_id | string | Có | Stable ID generated from doc_id + chunk_text hash |
| doc_id | string | Có | Allowlist: policy_refund_v4, sla_p1_2026, it_helpdesk_faq, hr_leave_policy |
| chunk_text | string | Có | Nội dung chunk sau cleaning (đã strip, đã fix refund nếu có) |
| effective_date | date | Có | ISO-8601 format YYYY-MM-DD hoặc "unknown" |
| exported_at | datetime | Không | Thời điểm export gốc |
| refund_window_days | string | Không | Metadata: "7" sau fix, "" hoặc "14" nếu chưa fix |
| processed_at | string | Không | Timestamp khi clean (UTC) |
| _quarantine_reason | string | Không | (Chỉ trong quarantine file) |

**Schema mapping:**
- Input CSV: `chunk_id,doc_id,chunk_text,effective_date,exported_at`
- Output cleaned CSV: Thêm `refund_window_days`, `processed_at`
- Output quarantine CSV: Thêm `_quarantine_reason`

---

## 3. Quy tắc quarantine vs drop

> Record bị flag đi đâu? Ai approve merge lại?

**Quarantine rules (transform/cleaning_rules.py):**

| Reason | Trigger condition | Action |
|--------|-------------------|--------|
| missing_chunk_id | chunk_id rỗng hoặc null | Quarantine |
| empty_chunk_text | chunk_text rỗng | Quarantine |
| missing_effective_date | effective_date rỗng sau normalize | Quarantine + gán "unknown" |
| invalid_effective_date_format | Không parse được date format nào | Quarantine + gán "unknown" + _date_parse_warn |
| unknown_doc_id | doc_id không trong allowlist | Quarantine |
| stale_hr_policy | hr_leave_policy có effective_date < 2026-01-01 | Quarantine (bản cũ 2025) |
| duplicate_chunk_text | Trùng nội dung chunk_text | Quarantine (giữ bản đầu tiên) |

**Quarantine workflow:**
1. Records được ghi vào `artifacts/quarantine/quarantine_<run_id>.csv`
2. Có `_quarantine_reason` column ghi rõ lý do
3. Không được embed vào ChromaDB
4. Cần manual review nếu muốn merge back

**Drop rules (implicit):**
- Records pass tất cả validation → cleaned CSV → embed
- Không có "drop" category — tất cả reject vào quarantine

---

## 4. Phiên bản & canonical

> Source of truth cho policy refund: file nào / version nào?

**Canonical sources:**

| Policy | Source of truth | Version | Effective date |
|--------|-----------------|---------|----------------|
| Refund policy | policy_refund_v4.txt | v4 | 2026-02-01 |
| SLA P1 | sla_p1_2026.txt | 2026 | 2026-02-01 |
| IT Helpdesk FAQ | it_helpdesk_faq.txt | 2026 | 2026-02-01 |
| HR Leave | hr_leave_policy.txt | 2026 | 2026-02-01 |
| Access Control | access_control_sop.txt | SOP v2 | 2026-02-01 |

**Version conflict resolution:**
- **Refund policy**: Luôn dùng v4 (7 ngày) — bản v3 (14 ngày) phải được fix qua `_apply_refund_fix()`
- **HR Leave**: Lấy bản 2026 (12 ngày) làm canonical — bản 2025 (10 ngày) quarantine
- **Date format**: Luôn chuẩn hoá về ISO-8601 (YYYY-MM-DD)

**Audit trail:**
- Mỗi run có `run_id` trong manifest
- Cleaned CSV có `processed_at` timestamp
- Quarantine CSV có `_quarantine_reason` + `_refund_fix_applied` flags
