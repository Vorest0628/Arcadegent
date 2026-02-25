"""Test fixtures shared by unit/integration tests."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pytest


@pytest.fixture
def tmp_path() -> Path:
    """Workspace-local tmp path to avoid host temp directory permission issues."""
    base = Path("g:/coding/pytesttmp/arcadegent_agent_tests")
    base.mkdir(parents=True, exist_ok=True)
    case_dir = base / f"case_{uuid4().hex[:10]}"
    case_dir.mkdir(parents=True, exist_ok=True)
    try:
        yield case_dir
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)
