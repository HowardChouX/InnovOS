"""
Tests for app/utils.py — utility functions.
"""

import pytest

from app.utils import utc_iso


class TestUtcIso:
    """utc_iso() — appends UTC timezone to naive datetime strings."""

    def test_none_input_returns_none(self):
        assert utc_iso(None) is None

    def test_empty_string_returns_none(self):
        assert utc_iso("") is None

    def test_naive_datetime_appends_utc(self):
        result = utc_iso("2024-01-15 10:30:00")
        assert result == "2024-01-15 10:30:00+00:00"

    def test_datetime_with_plus_unchanged(self):
        """If the string already contains '+', return as-is."""
        result = utc_iso("2024-01-15T10:30:00+05:00")
        assert result == "2024-01-15T10:30:00+05:00"

    def test_datetime_with_z_unchanged(self):
        """If the string ends with 'Z', return as-is."""
        result = utc_iso("2024-01-15T10:30:00Z")
        assert result == "2024-01-15T10:30:00Z"

    def test_iso_format_no_tz(self):
        result = utc_iso("2024-06-23T14:30:00")
        assert result == "2024-06-23T14:30:00+00:00"

    def test_date_only_no_tz(self):
        """A date-only string (no time) still has +00:00 appended."""
        result = utc_iso("2024-01-15")
        assert result == "2024-01-15+00:00"

    def test_whitespace_string_returns_whitespace_plus(self):
        """Whitespace is not empty, so +00:00 gets appended."""
        result = utc_iso("   ")
        assert result == "   +00:00"
