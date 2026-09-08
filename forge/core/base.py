# forge/core/base.py
import os
from dataclasses import dataclass
from typing import Optional, Callable

CHUNK_SIZE = 1024 * 1024          # 1 MiB
DEFAULT_MAX_SIZE_MB = 10 * 1024   # 10 GiB
MAX_SIZE_MB = int(os.environ.get("FORGE_MAX_SIZE_MB", DEFAULT_MAX_SIZE_MB))

@dataclass
class CompressionOptions:
    output: str
    extracted_mb: Optional[int] = None
    pattern: str = "A"
    compression: bool = True
    password: Optional[str] = None
    progress_callback: Optional[Callable[[int, int], None]] = None
    legacy_crypto: bool = False
    fmt: str = "zip"
    algo: str = "deflate"
    source: Optional[str] = None

def get_total_size(path: str) -> int:
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total

def is_tar_file(filepath: str) -> bool:
    """Check if the file is a tar archive by looking at magic bytes."""
    try:
        with open(filepath, 'rb') as f:
            f.seek(257)
            magic = f.read(6)
            return magic in (b'ustar\0', b'ustar ', b'tar\0')
    except:
        return False
