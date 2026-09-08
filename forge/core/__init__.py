# forge/core/__init__.py
"""
Core module – exports public API for compression, extraction, batch, info, and utilities.
"""

from .compression import generate_zip
from .extraction import extract_archive
from .batch import generate_batch
from .info import cli_info
from .base import CompressionOptions, get_total_size, CHUNK_SIZE, MAX_SIZE_MB
from forge.utils import format_size, format_time


def print_stats(stats: dict) -> None:
    """
    Pretty‑print compression statistics to stdout.
    """
    print("Created:", stats["output"])
    print("Format:", stats.get("format", "zip").upper())
    print("Algorithm:", stats.get("algo", "deflate").upper())
    print("Compressed size:", format_size(stats["compressed_bytes"]))
    print("Extracted size:", format_size(stats["extracted_bytes"]))
    print("Compression ratio:", f"{stats['ratio']:.2f}x")
    if "time" in stats:
        print("-" * 40)
        print("Time taken:", format_time(stats["time"]))


__all__ = [
    "generate_zip",
    "extract_archive",
    "generate_batch",
    "cli_info",
    "CompressionOptions",
    "get_total_size",
    "CHUNK_SIZE",
    "MAX_SIZE_MB",
    "print_stats",
]
