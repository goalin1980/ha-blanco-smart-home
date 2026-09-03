"""Pure helpers for BLANCO API data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Values used by the BLANCO API for the requested level of detail.
_RANGE_DAY = 1
_RANGE_WEEK = 2
_RANGE_MONTH = 3
_RANGE_YEAR = 4

HISTORY_KEYS: tuple[str, ...] = ("today", "week", "month", "year")
_LOD_TO_PERIOD: dict[int, str] = {
    _RANGE_DAY: "today",
    _RANGE_WEEK: "week",
    _RANGE_MONTH: "month",
    _RANGE_YEAR: "year",
}


def compute_stats_ranges(now_utc: datetime, time_zone: str) -> list[dict[str, Any]]:
    """Build today/week/month/year ranges expected by the BLANCO stats API."""
    try:
        zone = ZoneInfo(time_zone)
    except ZoneInfoNotFoundError:
        zone = UTC

    local_now = now_utc.astimezone(zone)
    offset = local_now.utcoffset()
    utc_offset_hours = offset.total_seconds() / 3600 if offset else 0.0

    today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=local_now.weekday())
    month_start = today_start.replace(day=1)
    year_start = today_start.replace(month=1, day=1)
    now_ms = int(now_utc.timestamp() * 1000)

    def descriptor(start: datetime, lod: int) -> dict[str, Any]:
        return {
            "from": int(start.timestamp() * 1000),
            "to": now_ms,
            "utc_offset": utc_offset_hours,
            "lod": lod,
            "iso_week": True,
        }

    return [
        descriptor(today_start, _RANGE_DAY),
        descriptor(week_start, _RANGE_WEEK),
        descriptor(month_start, _RANGE_MONTH),
        descriptor(year_start, _RANGE_YEAR),
    ]


def extract_stat_liters(total: list[dict[str, Any]], parameter: str) -> float | None:
    """Extract a numeric millilitre total from an API result and return litres."""
    for item in total:
        if item.get("par") != parameter:
            continue
        value = item.get("val")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return round(float(value) / 1000.0, 3)
        return None
    return None


def extract_period_totals(
    ranges: list[dict[str, Any]], parameter: str
) -> dict[str, float | None]:
    """Map possibly unordered stats ranges to named periods."""
    totals: dict[str, float | None] = {key: None for key in HISTORY_KEYS}
    for index, range_result in enumerate(ranges):
        range_info = range_result.get("range") or {}
        key = _LOD_TO_PERIOD.get(range_info.get("lod"))
        if key is None and index < len(HISTORY_KEYS):
            key = HISTORY_KEYS[index]
        if key is not None:
            totals[key] = extract_stat_liters(
                range_result.get("total") or [], parameter
            )
    return totals


def summarize_latest_dispense(actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the newest water-dispensing event from a normalized actions list."""
    candidates = [
        action
        for action in actions
        if action.get("disp_wtr_amt") is not None and action.get("evt_ts") is not None
    ]
    if not candidates:
        return {
            "last_dispense_ml": None,
            "last_dispense_ts": None,
            "last_water_type": None,
        }

    latest = max(candidates, key=lambda action: int(action["evt_ts"]))
    tap_state = latest.get("tap_state")
    tap_name = getattr(tap_state, "name", None)
    if tap_name is None and tap_state is not None:
        tap_name = str(tap_state)

    return {
        "last_dispense_ml": latest.get("disp_wtr_amt"),
        "last_dispense_ts": latest.get("evt_ts"),
        "last_water_type": tap_name.lower() if tap_name else None,
    }


def timestamp_from_milliseconds(value: Any) -> datetime | None:
    """Convert a Unix millisecond value into a UTC datetime."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def api_bool(value: Any) -> bool | None:
    """Convert API boolean representations without treating 'false' as true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return None
