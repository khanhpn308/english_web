"""Pytest configuration and shared fixtures for backend tests."""

import sys
from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    """Return the repository root directory."""
    return Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def python_version_info() -> tuple[int, int]:
    """Return major and minor Python version."""
    return sys.version_info.major, sys.version_info.minor
