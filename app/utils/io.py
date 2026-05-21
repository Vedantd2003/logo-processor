import tempfile
import shutil
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def temp_output_dir():
    """Context manager that creates a temp directory and cleans it up on exit."""
    tmp = tempfile.mkdtemp(prefix="logo_proc_")
    try:
        yield Path(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
