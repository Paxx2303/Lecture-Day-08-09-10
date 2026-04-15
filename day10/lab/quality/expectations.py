# """
# Expectation suite đơn giản (không bắt buộc Great Expectations).
#
# Sinh viên có thể thay bằng GE / pydantic / custom — miễn là có halt có kiểm soát.
# """
#
# from __future__ import annotations
#
# import re
# from dataclasses import dataclass
# from typing import Any, Dict, List, Tuple
#
#
# @dataclass
# class ExpectationResult:
#     name: str
#     passed: bool
#     severity: str  # "warn" | "halt"
#     detail: str
#
#
# def run_expectations(cleaned_rows: List[Dict[str, Any]]) -> Tuple[List[ExpectationResult], bool]:
#     """
#     Trả về (results, should_halt).
#
#     should_halt = True nếu có bất kỳ expectation severity halt nào fail.
#     """
#     results: List[ExpectationResult] = []
#
#     # E1: có ít nhất 1 dòng sau clean
#     ok = len(cleaned_rows) >= 1
#     results.append(
#         ExpectationResult(
#             "min_one_row",
#             ok,
#             "halt",
#             f"cleaned_rows={len(cleaned_rows)}",
#         )
#     )
#
#     # E2: không doc_id rỗng
#     bad_doc = [r for r in cleaned_rows if not (r.get("doc_id") or "").strip()]
#     ok2 = len(bad_doc) == 0
#     results.append(
#         ExpectationResult(
#             "no_empty_doc_id",
#             ok2,
#             "halt",
#             f"empty_doc_id_count={len(bad_doc)}",
#         )
#     )
#
#     # E3: policy refund không được chứa cửa sổ sai 14 ngày (sau khi đã fix)
#     bad_refund = [
#         r
#         for r in cleaned_rows
#         if r.get("doc_id") == "policy_refund_v4"
#         and "14 ngày làm việc" in (r.get("chunk_text") or "")
#     ]
#     ok3 = len(bad_refund) == 0
#     results.append(
#         ExpectationResult(
#             "refund_no_stale_14d_window",
#             ok3,
#             "halt",
#             f"violations={len(bad_refund)}",
#         )
#     )
#
#     # E4: chunk_text đủ dài
#     short = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) < 8]
#     ok4 = len(short) == 0
#     results.append(
#         ExpectationResult(
#             "chunk_min_length_8",
#             ok4,
#             "warn",
#             f"short_chunks={len(short)}",
#         )
#     )
#
#     # E5: effective_date đúng định dạng ISO sau clean (phát hiện parser lỏng)
#     iso_bad = [
#         r
#         for r in cleaned_rows
#         if not re.match(r"^\d{4}-\d{2}-\d{2}$", (r.get("effective_date") or "").strip())
#     ]
#     ok5 = len(iso_bad) == 0
#     results.append(
#         ExpectationResult(
#             "effective_date_iso_yyyy_mm_dd",
#             ok5,
#             "halt",
#             f"non_iso_rows={len(iso_bad)}",
#         )
#     )
#
#     # E6: không còn marker phép năm cũ 10 ngày trên doc HR (conflict version sau clean)
#     bad_hr_annual = [
#         r
#         for r in cleaned_rows
#         if r.get("doc_id") == "hr_leave_policy"
#         and "10 ngày phép năm" in (r.get("chunk_text") or "")
#     ]
#     ok6 = len(bad_hr_annual) == 0
#     results.append(
#         ExpectationResult(
#             "hr_leave_no_stale_10d_annual",
#             ok6,
#             "halt",
#             f"violations={len(bad_hr_annual)}",
#         )
#     )
#
#     halt = any(not r.passed and r.severity == "halt" for r in results)
#     return results, halt
"""
quality/expectations.py
========================
Sprint 2: Expectation suite — kiểm tra chất lượng dữ liệu sau cleaning.

Mỗi expectation trả về ExpectationResult(name, passed, severity, detail).
  severity = "halt"  → pipeline dừng nếu fail (trừ khi --skip-validate)
  severity = "warn"  → log cảnh báo nhưng pipeline tiếp tục

Danh sách expectations:
  1. no_null_chunk_ids        [halt]  chunk_id không được rỗng
  2. no_empty_texts           [halt]  chunk_text không được rỗng
  3. min_record_count         [halt]  phải có ít nhất 1 record
  4. valid_effective_dates    [warn]  effective_date không phải "unknown"
  5. no_stale_refund_policy   [warn]  không còn cụm "14 ngày/14-day" sau khi fix
  6. chunk_id_unique          [halt]  chunk_id phải unique
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_REFUND_14_PATTERN = re.compile(
    r"\b14[\s\-]?(ngày|day|days|ngay)\b",
    flags=re.IGNORECASE,
)


# =================================================================
# Data class
# =================================================================

@dataclass
class ExpectationResult:
    name: str
    passed: bool
    severity: str          # "halt" | "warn"
    detail: str = ""


# =================================================================
# Public API
# =================================================================

def run_expectations(
    cleaned: list[dict[str, Any]],
) -> tuple[list[ExpectationResult], bool]:
    """
    Chạy toàn bộ expectation suite trên cleaned records.

    Returns:
        (results, halt)
        - results : list[ExpectationResult]
        - halt    : True nếu có ít nhất một expectation severity='halt' bị fail
    """
    results: list[ExpectationResult] = []

    results.append(_expect_min_record_count(cleaned))
    results.append(_expect_no_null_chunk_ids(cleaned))
    results.append(_expect_no_empty_texts(cleaned))
    results.append(_expect_chunk_id_unique(cleaned))
    results.append(_expect_valid_effective_dates(cleaned))
    results.append(_expect_no_stale_refund_policy(cleaned))

    halt = any(r.severity == "halt" and not r.passed for r in results)
    return results, halt


# =================================================================
# Individual expectations
# =================================================================

def _expect_min_record_count(rows: list[dict]) -> ExpectationResult:
    passed = len(rows) >= 1
    return ExpectationResult(
        name="min_record_count",
        passed=passed,
        severity="halt",
        detail=f"count={len(rows)}" if passed else f"FAIL: 0 records sau cleaning",
    )


def _expect_no_null_chunk_ids(rows: list[dict]) -> ExpectationResult:
    bad = [i for i, r in enumerate(rows) if not r.get("chunk_id", "").strip()]
    passed = len(bad) == 0
    return ExpectationResult(
        name="no_null_chunk_ids",
        passed=passed,
        severity="halt",
        detail=(
            f"all {len(rows)} chunk_ids present"
            if passed
            else f"FAIL: {len(bad)} rows thiếu chunk_id tại index {bad[:5]}"
        ),
    )


def _expect_no_empty_texts(rows: list[dict]) -> ExpectationResult:
    bad = [r.get("chunk_id", f"row_{i}") for i, r in enumerate(rows) if not r.get("chunk_text", "").strip()]
    passed = len(bad) == 0
    return ExpectationResult(
        name="no_empty_texts",
        passed=passed,
        severity="halt",
        detail=(
            f"all {len(rows)} chunk_texts non-empty"
            if passed
            else f"FAIL: {len(bad)} chunk_text rỗng — chunk_ids: {bad[:5]}"
        ),
    )


def _expect_chunk_id_unique(rows: list[dict]) -> ExpectationResult:
    ids = [r.get("chunk_id", "") for r in rows]
    seen: set[str] = set()
    dupes: list[str] = []
    for cid in ids:
        if cid in seen:
            dupes.append(cid)
        seen.add(cid)
    passed = len(dupes) == 0
    return ExpectationResult(
        name="chunk_id_unique",
        passed=passed,
        severity="halt",
        detail=(
            f"all {len(ids)} chunk_ids unique"
            if passed
            else f"FAIL: {len(dupes)} duplicates — {dupes[:5]}"
        ),
    )


def _expect_valid_effective_dates(rows: list[dict]) -> ExpectationResult:
    unknown = [r.get("chunk_id", f"row_{i}") for i, r in enumerate(rows) if r.get("effective_date") == "unknown"]
    passed = len(unknown) == 0
    return ExpectationResult(
        name="valid_effective_dates",
        passed=passed,
        severity="warn",
        detail=(
            f"all effective_dates parsed OK"
            if passed
            else f"WARN: {len(unknown)} records có effective_date='unknown' — {unknown[:5]}"
        ),
    )


def _expect_no_stale_refund_policy(rows: list[dict]) -> ExpectationResult:
    """Sau khi refund fix, không còn cụm '14 ngày/14-day' nào trong chunk_text."""
    stale = [
        r.get("chunk_id", f"row_{i}")
        for i, r in enumerate(rows)
        if _REFUND_14_PATTERN.search(r.get("chunk_text", ""))
    ]
    passed = len(stale) == 0
    return ExpectationResult(
        name="no_stale_refund_policy",
        passed=passed,
        severity="warn",
        detail=(
            "no stale '14-day' refund mentions found"
            if passed
            else (
                f"WARN: {len(stale)} chunks vẫn còn '14 ngày/14-day' "
                f"(pipeline chạy với --no-refund-fix?) — {stale[:5]}"
            )
        ),
    )