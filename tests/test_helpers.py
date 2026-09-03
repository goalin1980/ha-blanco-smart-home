"""Tests for dependency-free BLANCO data helpers."""

from __future__ import annotations

import importlib.util
import unittest
from datetime import UTC, datetime
from enum import IntEnum
from pathlib import Path

HELPERS_PATH = (
    Path(__file__).parents[1] / "custom_components" / "blanco_smart_home" / "helpers.py"
)
SPEC = importlib.util.spec_from_file_location("blanco_helpers", HELPERS_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("Could not load BLANCO helpers")
helpers = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helpers)


class WaterType(IntEnum):
    """Small stand-in for the API client's enum."""

    STILL = 1
    HOT = 4


class StatsRangeTests(unittest.TestCase):
    """Verify timezone-aware BLANCO statistics ranges."""

    def test_berlin_summer_offset_and_boundaries(self) -> None:
        now = datetime(2026, 7, 15, 10, 30, tzinfo=UTC)
        ranges = helpers.compute_stats_ranges(now, "Europe/Berlin")

        self.assertEqual([item["lod"] for item in ranges], [1, 2, 3, 4])
        self.assertTrue(all(item["utc_offset"] == 2.0 for item in ranges))
        self.assertEqual(
            datetime.fromtimestamp(ranges[0]["from"] / 1000, tz=UTC),
            datetime(2026, 7, 14, 22, 0, tzinfo=UTC),
        )

    def test_fractional_timezone_offset_is_preserved(self) -> None:
        ranges = helpers.compute_stats_ranges(
            datetime(2026, 1, 15, 12, tzinfo=UTC), "Asia/Kolkata"
        )
        self.assertTrue(all(item["utc_offset"] == 5.5 for item in ranges))

    def test_unknown_timezone_falls_back_to_utc(self) -> None:
        ranges = helpers.compute_stats_ranges(
            datetime(2026, 1, 15, 12, tzinfo=UTC), "Invalid/TimeZone"
        )
        self.assertTrue(all(item["utc_offset"] == 0.0 for item in ranges))


class StatsExtractionTests(unittest.TestCase):
    """Verify aggregate extraction and response ordering."""

    def test_milliliters_are_converted_to_liters(self) -> None:
        self.assertEqual(
            helpers.extract_stat_liters(
                [{"par": "disp_wtr_amt", "val": 2575}], "disp_wtr_amt"
            ),
            2.575,
        )

    def test_bool_and_distribution_are_not_numeric_totals(self) -> None:
        self.assertIsNone(
            helpers.extract_stat_liters(
                [{"par": "disp_wtr_amt", "val": True}], "disp_wtr_amt"
            )
        )
        self.assertIsNone(
            helpers.extract_stat_liters(
                [{"par": "disp_wtr_amt", "val": [1, 2]}], "disp_wtr_amt"
            )
        )

    def test_lod_maps_an_unordered_response(self) -> None:
        ranges = [
            {
                "range": {"lod": 4},
                "total": [{"par": "disp_wtr_amt", "val": 9000}],
            },
            {
                "range": {"lod": 1},
                "total": [{"par": "disp_wtr_amt", "val": 1000}],
            },
        ]
        totals = helpers.extract_period_totals(ranges, "disp_wtr_amt")
        self.assertEqual(totals["today"], 1.0)
        self.assertEqual(totals["year"], 9.0)
        self.assertIsNone(totals["week"])


class ActionTests(unittest.TestCase):
    """Verify recent-action normalization."""

    def test_newest_dispense_is_selected(self) -> None:
        result = helpers.summarize_latest_dispense(
            [
                {"evt_ts": 1000, "disp_wtr_amt": 125, "tap_state": WaterType.STILL},
                {"evt_ts": 3000, "disp_wtr_amt": 250, "tap_state": WaterType.HOT},
                {"evt_ts": 4000, "disp_wtr_amt": None, "tap_state": WaterType.STILL},
            ]
        )
        self.assertEqual(result["last_dispense_ml"], 250)
        self.assertEqual(result["last_dispense_ts"], 3000)
        self.assertEqual(result["last_water_type"], "hot")

    def test_no_dispense_returns_unknown_values(self) -> None:
        result = helpers.summarize_latest_dispense([])
        self.assertEqual(
            result,
            {
                "last_dispense_ml": None,
                "last_dispense_ts": None,
                "last_water_type": None,
            },
        )


class ConversionTests(unittest.TestCase):
    """Verify defensive API conversions."""

    def test_boolean_strings(self) -> None:
        self.assertIs(helpers.api_bool("false"), False)
        self.assertIs(helpers.api_bool("TRUE"), True)
        self.assertIsNone(helpers.api_bool("unknown"))

    def test_invalid_timestamp_returns_none(self) -> None:
        self.assertIsNone(helpers.timestamp_from_milliseconds("not-a-number"))


if __name__ == "__main__":
    unittest.main()
