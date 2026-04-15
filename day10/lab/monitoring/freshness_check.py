# """
# Kiểm tra freshness từ manifest pipeline (SLA đơn giản theo giờ).
#
# Sinh viên mở rộng: đọc watermark DB, so sánh với clock batch, v.v.
# """
#
# from __future__ import annotations
#
# import json
# from datetime import datetime, timezone
# from pathlib import Path
# from typing import Any, Dict, Tuple
#
#
# def parse_iso(ts: str) -> datetime | None:
#     if not ts:
#         return None
#     try:
#         # Cho phép "2026-04-10T08:00:00" không có timezone
#         if ts.endswith("Z"):
#             return datetime.fromisoformat(ts.replace("Z", "+00:00"))
#         dt = datetime.fromisoformat(ts)
#         if dt.tzinfo is None:
#             dt = dt.replace(tzinfo=timezone.utc)
#         return dt
#     except ValueError:
#         return None
#
#
# def check_manifest_freshness(
#     manifest_path: Path,
#     *,
#     sla_hours: float = 24.0,
#     now: datetime | None = None,
# ) -> Tuple[str, Dict[str, Any]]:
#     """
#     Trả về ("PASS" | "WARN" | "FAIL", detail dict).
#
#     Đọc trường `latest_exported_at` hoặc max exported_at trong cleaned summary.
#     """
#     now = now or datetime.now(timezone.utc)
#     if not manifest_path.is_file():
#         return "FAIL", {"reason": "manifest_missing", "path": str(manifest_path)}
#
#     data: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
#     ts_raw = data.get("latest_exported_at") or data.get("run_timestamp")
#     dt = parse_iso(str(ts_raw)) if ts_raw else None
#     if dt is None:
#         return "WARN", {"reason": "no_timestamp_in_manifest", "manifest": data}
#
#     age_hours = (now - dt).total_seconds() / 3600.0
#     detail = {
#         "latest_exported_at": ts_raw,
#         "age_hours": round(age_hours, 3),
#         "sla_hours": sla_hours,
#     }
#     if age_hours <= sla_hours:
#         return "PASS", detail
#     return "FAIL", {**detail, "reason": "freshness_sla_exceeded"}

"""
monitoring/freshness_check.py
==============================
Sprint 2: Kiểm tra SLA freshness dựa trên manifest JSON.

Logic:
  - Đọc manifest['latest_exported_at']
  - So sánh với thời điểm hiện tại (UTC)
  - Trả về status:
      "OK"   → tuổi dữ liệu < sla_hours
      "WARN" → sla_hours ≤ tuổi < sla_hours * 2
      "FAIL" → tuổi ≥ sla_hours * 2  hoặc không parse được timestamp
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def check_manifest_freshness(
    manifest_path: Path | str,
    *,
    sla_hours: float = 24.0,
) -> tuple[str, dict[str, Any]]:
    """
    Đọc manifest JSON và kiểm tra freshness của dữ liệu.

    Args:
        manifest_path : đường dẫn tới file manifest JSON
        sla_hours     : ngưỡng SLA (giờ), mặc định 24h

    Returns:
        (status, detail_dict)
        status  : "OK" | "WARN" | "FAIL"
        detail  : dict chứa thông tin chi tiết để log
    """
    manifest_path = Path(manifest_path)

    # --- Đọc manifest ---
    if not manifest_path.is_file():
        return "FAIL", {
            "error": f"manifest not found: {manifest_path}",
            "sla_hours": sla_hours,
        }

    try:
        with manifest_path.open(encoding="utf-8") as f:
            manifest: dict = json.load(f)
    except json.JSONDecodeError as exc:
        return "FAIL", {"error": f"invalid JSON: {exc}", "sla_hours": sla_hours}

    # --- Lấy timestamp ---
    latest_exported = manifest.get("latest_exported_at", "")
    if not latest_exported:
        return "FAIL", {
            "error": "latest_exported_at missing or empty in manifest",
            "sla_hours": sla_hours,
            "manifest_run_id": manifest.get("run_id", "?"),
        }

    # --- Parse timestamp (ISO-8601 với hoặc không có timezone) ---
    try:
        exported_dt = _parse_iso(latest_exported)
    except ValueError as exc:
        return "FAIL", {
            "error": f"cannot parse latest_exported_at={latest_exported!r}: {exc}",
            "sla_hours": sla_hours,
        }

    now_utc = datetime.now(timezone.utc)
    # Đảm bảo cả hai cùng timezone-aware
    if exported_dt.tzinfo is None:
        exported_dt = exported_dt.replace(tzinfo=timezone.utc)

    age_hours = (now_utc - exported_dt).total_seconds() / 3600.0
    age_str = _fmt_age(age_hours)

    detail: dict[str, Any] = {
        "latest_exported_at": latest_exported,
        "checked_at": now_utc.isoformat(),
        "age_hours": round(age_hours, 2),
        "age_human": age_str,
        "sla_hours": sla_hours,
        "run_id": manifest.get("run_id", "?"),
        "cleaned_records": manifest.get("cleaned_records"),
        "quarantine_records": manifest.get("quarantine_records"),
    }

    if age_hours < sla_hours:
        status = "OK"
    elif age_hours < sla_hours * 2:
        status = "WARN"
        detail["warning"] = f"Dữ liệu cũ hơn SLA ({age_str} > {sla_hours}h)"
    else:
        status = "FAIL"
        detail["error"] = f"Dữ liệu quá cũ ({age_str} > {sla_hours * 2}h — 2× SLA)"

    return status, detail


# =================================================================
# Private helpers
# =================================================================

def _parse_iso(ts: str) -> datetime:
    """Parse ISO-8601 string, hỗ trợ cả 'Z' suffix và offset."""
    ts = ts.strip()
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def _fmt_age(hours: float) -> str:
    """Chuyển số giờ thành chuỗi dễ đọc."""
    if hours < 1:
        return f"{hours * 60:.0f}m"
    if hours < 48:
        return f"{hours:.1f}h"
    return f"{hours / 24:.1f}d"
