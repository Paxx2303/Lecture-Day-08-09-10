# Kiến trúc pipeline — Lab Day 10

**Nhóm:** Nguyễn Quốc Nam  
**Cập nhật:** 2026-04-15  

---

## 1. Sơ đồ luồng (bắt buộc có 1 diagram: Mermaid / ASCII)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           ETL PIPELINE Day 10                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  INGEST (load_raw_csv)                                                     │
│  - Đọc data/raw/policy_export_dirty.csv                                    │
│  - Input: 10 raw records                                                   │
│  - Output: list[dict] raw rows                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  TRANSFORM (clean_rows)                                                    │
│  - Validate required fields (chunk_id, chunk_text)                        │
│  - Normalize dates (multiple formats → ISO YYYY-MM-DD)                     │
│  - Apply refund fix (14→7 days if apply_refund_window_fix=True)            │
│  - Quarantine rules: empty text, invalid date, unknown doc_id             │
│  - Input: 10 rows → Output: 9 cleaned + 1 quarantine                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                   ┌──────────────────┴──────────────────┐
                   ▼                                      ▼
         ┌─────────────────────┐              ┌─────────────────────┐
         │ artifacts/cleaned/ │              │ artifacts/quarantine/│
         │ cleaned_<run_id>.csv│              │ quarantine_<run_id>.csv│
         └─────────────────────┘              └─────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  QUALITY (run_expectations)                                                │
│  - 6 baseline expectations:                                                │
│    • min_record_count [halt]                                              │
│    • no_null_chunk_ids [halt]                                             │
│    • no_empty_texts [halt]                                                 │
│    • chunk_id_unique [halt]                                                │
│    • valid_effective_dates [warn]                                         │
│    • no_stale_refund_policy [warn]                                         │
│  - If any [halt] fail → pipeline exit 2 (unless --skip-validate)          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  EMBED (cmd_embed_internal)                                               │
│  - ChromaDB PersistentClient                                              │
│  - SentenceTransformer (all-MiniLM-L6-v2)                                 │
│  - Upsert: chunk_id as key (idempotent)                                   │
│  - Prune: xóa IDs không còn trong cleaned (index = publish boundary)     │
│  - Collection: day09_docs (same as Day 09)                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  MONITOR (check_manifest_freshness)                                       │
│  - Read artifacts/manifests/manifest_<run_id>.json                       │
│  - Check run_timestamp vs current time                                    │
│  - SLA: 24 hours (configurable via FRESHNESS_SLA_HOURS)                   │
│  - Output: PASS/WARN/FAIL + detail JSON                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
         ┌─────────────────────────────────────────┐
         │ artifacts/manifests/manifest_<run_id>.json│
         │ {run_id, raw_records, cleaned_records,  │
         │  quarantine_records, latest_exported_at, │
         │  chroma_path, chroma_collection}          │
         └─────────────────────────────────────────┘
```

---

## 2. Ranh giới trách nhiệm

| Thành phần | Input | Output | Owner nhóm |
|------------|-------|--------|--------------|
| Ingest | `data/raw/policy_export_dirty.csv` | list[dict] raw rows | Nguyễn Quốc Nam |
| Transform | raw rows | cleaned + quarantine CSVs | Nguyễn Quốc Nam |
| Quality | cleaned rows | Expectation results + PASS/FAIL/HALT | Nguyễn Quốc Nam |
| Embed | cleaned CSV | ChromaDB vectors | Nguyễn Quốc Nam |
| Monitor | manifest JSON | freshness status | Nguyễn Quốc Nam |

---

## 3. Idempotency & rerun

**Strategy:**
- **Upsert theo `chunk_id`**: Mỗi run gọi `col.upsert(ids=ids, ...)` với chunk_id là unique key
- **Prune stale IDs**: Sau upsert, xóa các IDs không còn trong cleaned run hiện tại:
  ```python
  prev_ids = set(col.get(include=[])["ids"])
  drop = sorted(prev_ids - set(ids))  # IDs có trong DB nhưng không có trong cleaned
  col.delete(ids=drop)
  ```
- **Rerun 2 lần**: Không duplicate vector — upsert ghi đè vector cũ, prune loại bỏ IDs thừa

**Verification:**
- Run `sprint1` → embed 9 records
- Run `sprint2` → embed 9 records (same IDs, same vectors)
- Run `inject-bad` → embed 9 records với stale refund (14 days) + prune unused IDs

---

## 4. Liên hệ Day 09

Pipeline Day 10 cung cấp vector data cho retrieval trong Day 09:
- **Same ChromaDB**: `chroma_db/` directory
- **Same Collection**: `day09_docs` (configurable via `CHROMA_COLLECTION`)
- **Index refresh**: Mỗi run xóa vectors cũ (prune) và upsert vectors mới
- **Data source**: Export CSV (`policy_export_dirty.csv`) được clean → embed

**Flow:**
```
Day 10: policy_export_dirty.csv → clean → embed → ChromaDB
Day 09: graph.py → retrieval_worker → ChromaDB (same collection)
```

---

## 5. Rủi ro đã biết

- **Unicode encoding error**: Freshness check print Unicode → encode error on Windows (cp1258)
- **Duplicate chunk_text**: rows 1-2 giữ lại cả 2 (baseline không detect duplicate text)
- **HR stale policy**: row 7 (10 ngày 2025) và row 8 (12 ngày 2026) đều được giữ lại — cần rule quarantine cho stale HR
- **Unknown doc_id**: row 9 có `legacy_catalog_xyz_zzz` không trong allowlist nhưng vẫn được giữ lại (baseline không có allowlist check)
