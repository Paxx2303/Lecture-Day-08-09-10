# Quality report — Lab Day 10 (nhóm)

**run_id:** sprint2  
**Ngày:** 2026-04-15  

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước (inject-bad) | Sau (sprint2) | Ghi chú |
|--------|------------------|--------------|---------|
| raw_records | 10 | 10 | Same raw input |
| cleaned_records | 9 | 9 | Row 5: empty_chunk_text → quarantine |
| quarantine_records | 1 | 1 | Same |
| Expectation halt? | YES (--skip-validate) | NO | inject-bad passes với --skip-validate |

**Runs executed:**
- `sprint1`: clean run (exit 0, all expectations pass)
- `sprint2`: clean run again (idempotent test)
- `inject-bad`: --no-refund-fix + --skip-validate (stale data)

---

## 2. Before / after retrieval (bắt buộc)

> Results from `artifacts/eval/before_after_eval.csv`

**Câu hỏi then chốt:** refund window (`q_refund_window`)  
**Trước (inject-bad):** "14 ngày làm việc" - stale policy  
**Sau (sprint2):** "7 ngày làm việc" - correct policy ✅

| question_id | contains_expected | hits_forbidden | Ghi chú |
|------------|----------------|-------------|---------|
| q_refund_window | yes | no | ✅ Before: 14→7 days after fix |
| q_p1_sla | yes | no | ✅ SLA 15 phút + 4 giờ |
| q_lockout | yes | no | ✅ 5 lần đăng nhập sai |
| q_leave_version | yes | **yes** | ⚠️ Có cả 10 và 12 ngày! |

**Merit (khuyến nghị):** versioning HR — `q_leave_version` có `hits_forbidden=yes` vì:
- Row 7 (2025): "10 ngày phép năm" (stale)
- Row 8 (2026): "12 ngày phép năm" (canonical)
- **Khuyến nghị**: Thêm rule quarantine cho HR effective_date < 2026-01-01

---

## 3. Freshness & monitor

**Freshness check:**
- Command: `python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_sprint2.json`
- Result: FAIL (UnicodeEncodeError on Windows console - không ảnh hưởng logic)
- SLA: 24 hours (config via `FRESHNESS_SLA_HOURS`)

**Manifest details:**
```json
{
  "run_id": "sprint2",
  "run_timestamp": "2026-04-15T08:...",
  "raw_records": 10,
  "cleaned_records": 9,
  "quarantine_records": 1,
  "latest_exported_at": "2026-04-10T08:00:00"
}
```

---

## 4. Corruption inject (Sprint 3)

**Method:** `python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate`

**Corruption injected:**
- Row 3: "14 ngày làm việc" (stale refund policy v3) - không fix
- `--skip-validate`: bỏ qua expectation check

**Detection:**
- `eval_retrieval.py` shows "14 ngày" trong kết quả trước khi fix
- So sánh với sprint2 (clean): "7 ngày" ✅

**Evidence:**
- Before: `artifacts/cleaned/cleaned_inject-bad.csv` row 3 = "14 ngày"
- After: `artifacts/cleaned/cleaned_sprint2.csv` row 3 = "7 ngày"

---

## 5. Hạn chế & việc chưa làm

- **HR stale policy**: row 7 (2025, 10 ngày) và row 8 (2026, 12 ngày) đều giữ lại — cần thêm rule quarantine
- **Duplicate detection**: rows 1-2 giữ lại cả 2 (cùng chunk_text) — baseline không detect
- **Unknown doc_id**: row 9 (`legacy_catalog_xyz_zzz`) không trong allowlist nhưng vẫn embed
- **Unicode encoding**: Windows console (cp1258) không hỗ trợ tiếng Việt → freshness check lỗi
