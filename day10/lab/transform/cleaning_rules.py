# """
# Cleaning rules — raw export → cleaned rows + quarantine.
#
# Baseline gồm các failure mode mở rộng (allowlist doc_id, parse ngày, HR stale version).
# Sinh viên thêm ≥3 rule mới: mỗi rule phải ghi `metric_impact` (xem README — chống trivial).
# """
#
# from __future__ import annotations
#
# import csv
# import hashlib
# import re
# from pathlib import Path
# from typing import Any, Dict, List, Tuple
#
# # Khớp export hợp lệ trong lab (mở rộng khi nhóm thêm doc mới — phải đồng bộ contract).
# ALLOWED_DOC_IDS = frozenset(
#     {
#         "policy_refund_v4",
#         "sla_p1_2026",
#         "it_helpdesk_faq",
#         "hr_leave_policy",
#     }
# )
#
# _ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# _DMY_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
#
#
# def _norm_text(s: str) -> str:
#     return " ".join((s or "").strip().split()).lower()
#
#
# def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int) -> str:
#     h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode("utf-8")).hexdigest()[:16]
#     return f"{doc_id}_{seq}_{h}"
#
#
# def _normalize_effective_date(raw: str) -> Tuple[str, str]:
#     """
#     Trả về (iso_date, error_reason).
#     iso_date rỗng nếu không parse được.
#     """
#     s = (raw or "").strip()
#     if not s:
#         return "", "empty_effective_date"
#     if _ISO_DATE.match(s):
#         return s, ""
#     m = _DMY_SLASH.match(s)
#     if m:
#         dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
#         return f"{yyyy}-{mm}-{dd}", ""
#     return "", "invalid_effective_date_format"
#
#
# def load_raw_csv(path: Path) -> List[Dict[str, str]]:
#     rows: List[Dict[str, str]] = []
#     with path.open(encoding="utf-8", newline="") as f:
#         reader = csv.DictReader(f)
#         for r in reader:
#             rows.append({k: (v or "").strip() for k, v in r.items()})
#     return rows
#
#
# def clean_rows(
#     rows: List[Dict[str, str]],
#     *,
#     apply_refund_window_fix: bool = True,
# ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
#     """
#     Trả về (cleaned, quarantine).
#
#     Baseline (mở rộng theo narrative Day 10):
#     1) Quarantine: doc_id không thuộc allowlist (export lạ / catalog sai).
#     2) Chuẩn hoá effective_date sang YYYY-MM-DD; quarantine nếu không parse được.
#     3) Quarantine: chunk hr_leave_policy có effective_date < 2026-01-01 (bản HR cũ / conflict version).
#     4) Quarantine: chunk_text rỗng hoặc effective_date rỗng sau chuẩn hoá.
#     5) Loại trùng nội dung chunk_text (giữ bản đầu).
#     6) Fix stale refund: policy_refund_v4 chứa '14 ngày làm việc' → 7 ngày.
#     """
#     quarantine: List[Dict[str, Any]] = []
#     seen_text: set[str] = set()
#     cleaned: List[Dict[str, Any]] = []
#     seq = 0
#
#     for raw in rows:
#         doc_id = raw.get("doc_id", "")
#         text = raw.get("chunk_text", "")
#         eff_raw = raw.get("effective_date", "")
#         exported_at = raw.get("exported_at", "")
#
#         if doc_id not in ALLOWED_DOC_IDS:
#             quarantine.append({**raw, "reason": "unknown_doc_id"})
#             continue
#
#         eff_norm, eff_err = _normalize_effective_date(eff_raw)
#         if eff_err == "empty_effective_date":
#             quarantine.append({**raw, "reason": "missing_effective_date"})
#             continue
#         if eff_err == "invalid_effective_date_format":
#             quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
#             continue
#
#         if doc_id == "hr_leave_policy" and eff_norm < "2026-01-01":
#             quarantine.append(
#                 {
#                     **raw,
#                     "reason": "stale_hr_policy_effective_date",
#                     "effective_date_normalized": eff_norm,
#                 }
#             )
#             continue
#
#         if not text:
#             quarantine.append({**raw, "reason": "missing_chunk_text"})
#             continue
#
#         key = _norm_text(text)
#         if key in seen_text:
#             quarantine.append({**raw, "reason": "duplicate_chunk_text"})
#             continue
#         seen_text.add(key)
#
#         fixed_text = text
#         if apply_refund_window_fix and doc_id == "policy_refund_v4":
#             if "14 ngày làm việc" in fixed_text:
#                 fixed_text = fixed_text.replace(
#                     "14 ngày làm việc",
#                     "7 ngày làm việc",
#                 )
#                 fixed_text += " [cleaned: stale_refund_window]"
#
#         seq += 1
#         cleaned.append(
#             {
#                 "chunk_id": _stable_chunk_id(doc_id, fixed_text, seq),
#                 "doc_id": doc_id,
#                 "chunk_text": fixed_text,
#                 "effective_date": eff_norm,
#                 "exported_at": exported_at or "",
#             }
#         )
#
#     return cleaned, quarantine
#
#
# def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
#     path.parent.mkdir(parents=True, exist_ok=True)
#     if not rows:
#         path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8")
#         return
#     fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
#     with path.open("w", encoding="utf-8", newline="") as f:
#         w = csv.DictWriter(f, fieldnames=fieldnames)
#         w.writeheader()
#         for r in rows:
#             w.writerow({k: r.get(k, "") for k in fieldnames})
#
#
# def write_quarantine_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
#     path.parent.mkdir(parents=True, exist_ok=True)
#     if not rows:
#         path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8")
#         return
#     keys: List[str] = []
#     seen_k: set[str] = set()
#     for r in rows:
#         for k in r.keys():
#             if k not in seen_k:
#                 seen_k.add(k)
#                 keys.append(k)
#     with path.open("w", encoding="utf-8", newline="") as f:
#         w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", restval="")
#         w.writeheader()
#         for r in rows:
#             w.writerow(r)
"""
transform/cleaning_rules.py
============================
Sprint 1-2: Schema mapping, data cleaning, quarantine separation.

Rules áp dụng theo thứ tự:
  1. Drop rows thiếu chunk_id hoặc chunk_text rỗng            → quarantine
  2. Normalize effective_date → ISO-8601 date string          → giữ lại, gán "unknown" nếu lỗi
  3. Strip whitespace toàn bộ string fields
  4. [Optional] Refund window fix: thay "14 ngày/14-day" → "7 ngày/7-day" trong chunk_text
"""

from __future__ import annotations

import csv
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# -----------------------------------------------------------------
# Schema: tên cột mong muốn sau khi map từ raw CSV
# -----------------------------------------------------------------
REQUIRED_FIELDS = ("chunk_id", "chunk_text")
OUTPUT_FIELDS = (
    "chunk_id",
    "doc_id",
    "chunk_text",
    "effective_date",
    "exported_at",
    "refund_window_days",
    "_quarantine_reason",
)

# Các pattern ngày phổ biến để parse
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%d %b %Y",
    "%d %B %Y",
)

# Allowlist doc_ids trong hệ thống (Sprint 2)
ALLOWED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
    }
)

# Refund window: thay thế cụm "14 ngày" / "14-day" → "7 ngày" / "7-day"
_REFUND_PATTERN = re.compile(
    r"\b14[\s\-]?(ngày|day|days|ngay)\b",
    flags=re.IGNORECASE,
)


# =================================================================
# Public API
# =================================================================


def load_raw_csv(path: Path) -> list[dict[str, Any]]:
    """
    Đọc CSV raw, trả về list[dict].
    Tự bỏ qua BOM nếu có (encoding='utf-8-sig').
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Raw CSV không tìm thấy: {path}")

    rows: list[dict] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Strip toàn bộ key/value ngay khi đọc vào
            clean = {
                k.strip(): (v.strip() if isinstance(v, str) else v)
                for k, v in row.items()
            }
            rows.append(clean)
    return rows


def clean_rows(
    rows: list[dict],
    *,
    apply_refund_window_fix: bool = True,
) -> tuple[list[dict], list[dict]]:
    """
    Áp dụng toàn bộ cleaning rules.

    Returns:
        (cleaned, quarantine)
        - cleaned   : records hợp lệ, đã transform
        - quarantine: records bị loại kèm cột _quarantine_reason
    """
    cleaned: list[dict] = []
    quarantine: list[dict] = []

    for raw in rows:
        row = deepcopy(raw)
        reason = _validate_required(row)
        if reason:
            row["_quarantine_reason"] = reason
            quarantine.append(row)
            continue

        # Normalize fields
        row = _normalize_dates(row)
        row = _normalize_strings(row)

        if apply_refund_window_fix:
            row = _apply_refund_fix(row)

        # Đảm bảo các cột output tồn tại
        for field in OUTPUT_FIELDS:
            row.setdefault(field, "")

        cleaned.append(row)

    return cleaned, quarantine


def write_cleaned_csv(path: Path, rows: list[dict]) -> None:
    """Ghi cleaned records ra CSV, bao gồm cột processed_at."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    # Thêm processed_at nếu chưa có
    ts = datetime.now(timezone.utc).isoformat()
    for r in rows:
        r.setdefault("processed_at", ts)

    # Giữ thứ tự cột cố định + bất kỳ cột extra nào
    base_cols = [
        "chunk_id",
        "doc_id",
        "chunk_text",
        "effective_date",
        "exported_at",
        "refund_window_days",
        "processed_at",
    ]
    extra = [k for k in rows[0].keys() if k not in base_cols and not k.startswith("_")]
    fieldnames = base_cols + extra

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_quarantine_csv(path: Path, rows: list[dict]) -> None:
    """Ghi quarantine records ra CSV kèm lý do loại bỏ."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    all_keys: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r:
            if k not in seen:
                all_keys.append(k)
                seen.add(k)
    # Đẩy _quarantine_reason ra cuối
    if "_quarantine_reason" in all_keys:
        all_keys.remove("_quarantine_reason")
    all_keys.append("_quarantine_reason")

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# =================================================================
# Private helpers
# =================================================================


def _validate_required(row: dict) -> str:
    """Trả về chuỗi lý do nếu row không hợp lệ, rỗng nếu OK."""
    if not row.get("chunk_id", "").strip():
        return "missing_chunk_id"
    if not row.get("chunk_text", "").strip():
        return "empty_chunk_text"
    return ""


def _normalize_dates(row: dict) -> dict:
    """
    Cố parse effective_date sang YYYY-MM-DD.
    Nếu không parse được → gán "unknown", ghi _date_parse_warn.
    """
    raw_date = row.get("effective_date", "").strip()
    if not raw_date:
        row["effective_date"] = "unknown"
        return row

    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(raw_date, fmt)
            row["effective_date"] = dt.strftime("%Y-%m-%d")
            return row
        except ValueError:
            continue

    # Không parse được
    row["_date_parse_warn"] = f"unparseable_date:{raw_date!r}"
    row["effective_date"] = "unknown"
    return row


def _normalize_strings(row: dict) -> dict:
    """Strip whitespace tất cả string fields."""
    return {k: v.strip() if isinstance(v, str) else v for k, v in row.items()}


def _apply_refund_fix(row: dict) -> dict:
    """
    Sprint 2 fix: thay cụm '14 ngày/14-day' → '7 ngày/7-day' trong chunk_text.
    Ghi lại cờ _refund_fix_applied nếu có thay đổi.
    """
    text: str = row.get("chunk_text", "")

    def _replacer(m: re.Match) -> str:
        unit = m.group(1)
        # Giữ nguyên dấu cách hoặc gạch ngang
        sep = m.group(0)[2]  # ký tự giữa '14' và unit
        if sep.isalpha():
            sep = " "
        return f"7{sep}{unit}"

    new_text, n = _REFUND_PATTERN.subn(_replacer, text)
    if n:
        row["chunk_text"] = new_text
        row["_refund_fix_applied"] = str(n)
        # Cập nhật cột metadata
        row["refund_window_days"] = "7"
    return row
