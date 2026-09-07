import pytest
import tempfile
from pathlib import Path

@pytest.fixture
def tmp_workdir():
    """Provide a temporary directory as Path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
