"""Shared test fixtures."""
import shutil
from pathlib import Path
import pytest

@pytest.fixture(scope="function")
def test_log_dir(tmp_path):
    """Create a temporary directory for log files."""
    log_dir = tmp_path / "test_logs"
    log_dir.mkdir()
    yield log_dir
    # Cleanup
    shutil.rmtree(log_dir)
