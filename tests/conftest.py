"""Shared test fixtures."""
from __future__ import annotations

import pytest
from pathlib import Path


@pytest.fixture
def fixtures_path():
    """Return the path to the test fixtures directory."""
    return Path(__file__).parent / "fixtures"
