# forge/core/__init__.py
from .compression import generate_zip
from .extraction import extract_archive
from .batch import generate_batch
from .info import cli_info
from .base import CompressionOptions, get_total_size, CHUNK_SIZE, MAX_SIZE_MB
from . import algorithms

__all__ = [
    "generate_zip",
    "extract_archive",
    "generate_batch",
    "cli_info",
    "CompressionOptions",
    "get_total_size",
    "CHUNK_SIZE",
    "MAX_SIZE_MB",
    "algorithms",
]
