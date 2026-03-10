"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_path():
    """Return the path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"
