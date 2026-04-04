"""Tests for time-window utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ctxray.core.timeutil import TimeWindow, parse_period, sliding_windows


class TestParsePeriod:
    def test_days(self):
        assert parse_period("7d") == timedelta(days=7)

    def test_weeks(self):
        assert parse_period("4w") == timedelta(weeks=4)

    def test_months(self):
        assert parse_period("1m") == timedelta(days=30)

    def test_years(self):
        assert parse_period("1y") == timedelta(days=365)

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid period"):
            parse_period("abc")

    def test_whitespace_stripped(self):
        assert parse_period("  7d  ") == timedelta(days=7)

    def test_case_insensitive(self):
        assert parse_period("7D") == timedelta(days=7)


class TestSlidingWindows:
    def test_returns_correct_count(self):
        windows = sliding_windows(period="7d", count=4)
        assert len(windows) == 4

    def test_windows_are_chronological(self):
        windows = sliding_windows(period="7d", count=4)
        for i in range(len(windows) - 1):
            assert windows[i].end <= windows[i + 1].start or windows[i].end == windows[i + 1].start

    def test_windows_are_contiguous(self):
        anchor = datetime(2026, 3, 11, tzinfo=timezone.utc)
        windows = sliding_windows(period="7d", count=3, anchor=anchor)
        assert windows[0].end == windows[1].start
        assert windows[1].end == windows[2].start

    def test_last_window_ends_at_anchor(self):
        anchor = datetime(2026, 3, 11, tzinfo=timezone.utc)
        windows = sliding_windows(period="7d", count=3, anchor=anchor)
        assert windows[-1].end == anchor

    def test_window_duration_matches_period(self):
        windows = sliding_windows(period="7d", count=2)
        for w in windows:
            assert w.end - w.start == timedelta(days=7)

    def test_single_window(self):
        windows = sliding_windows(period="30d", count=1)
        assert len(windows) == 1

    def test_label_format(self):
        anchor = datetime(2026, 3, 11, tzinfo=timezone.utc)
        windows = sliding_windows(period="7d", count=1, anchor=anchor)
        assert "Mar" in windows[0].label

    def test_timewindow_dataclass(self):
        tw = TimeWindow(
            start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end=datetime(2026, 1, 8, tzinfo=timezone.utc),
            label="Jan 01 - Jan 08",
        )
        assert tw.start < tw.end
        assert tw.label == "Jan 01 - Jan 08"
