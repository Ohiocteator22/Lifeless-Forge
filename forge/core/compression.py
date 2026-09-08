# forge/core/compression.py
"""
Dispatcher for compression – calls the appropriate algorithm module.
"""

import os
import tempfile
import time
import logging
from typing import Dict, Any

from forge.core.base import CompressionOptions, get_total_size, MAX_SIZE_MB
from forge.core.algorithms import deflate, lzma, zstd, lz4, brotli
from forge.exceptions import ConfigurationError

logger = logging.getLogger(__name__)


def generate_zip(options: CompressionOptions) -> Dict[str, Any]:
    """
    Main entry point for creating an archive.
    Validates options, generates temporary data if needed,
    then dispatches to the algorithm‑specific compressor.
    """
    start_time = time.time()
    logger.info(f"Starting generation: output={options.output}, format={options.fmt}, algo={options.algo}")

    # ----- 1. Size validation ----------------------------------------------
    if options.extracted_mb is not None:
        if not isinstance(options.extracted_mb, (int, float)) or options.extracted_mb <= 0:
            raise ConfigurationError(f"Invalid extracted_mb: {options.extracted_mb} (must be > 0)")
        if options.extracted_mb > MAX_SIZE_MB:
            raise ConfigurationError(
                f"Requested size ({options.extracted_mb} MB) exceeds maximum allowed ({MAX_SIZE_MB} MB). "
                "Set FORGE_MAX_SIZE_MB environment variable to increase."
            )

    # ----- 2. Encryption validation ---------------------------------------
    if options.password is not None:
        # Encryption is only supported for DEFLATE (ZIP) – not for LZMA, Zstd, LZ4
        if options.algo in ("lzma", "zstd", "lz4", "brotli"):
            raise ConfigurationError(
                f"Encryption is not supported for {options.algo.upper()} compression."
            )
        # Verify pyzipper is installed
        try:
            import pyzipper
        except ImportError:
            raise ConfigurationError(
                "pyzipper is required for encryption. Please install: pip install pyzipper"
            )

    # ----- 3. Input handling ---------------------------------------------
    source = options.source
    if source is not None:
        # Real file/folder input
        if not os.path.exists(source):
            raise FileNotFoundError(f"Input source not found: {source}")
        if options.fmt in ("pptx", "docx", "xlsx") and os.path.isdir(source):
            raise ConfigurationError(f"Office format '{options.fmt}' does not support folders.")
        target_bytes = get_total_size(source)
        temp_name = None   # no temporary file needed
    else:
        # Generate test data from pattern
        if options.extracted_mb is None:
            raise ConfigurationError("Either source or extracted_mb must be provided.")
        target_bytes = options.extracted_mb * 1024 * 1024
        chunk = (options.pattern * (1024 * 1024)).encode()   # 1 MB chunk
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            temp_name = tmp.name
            written = 0
            if options.progress_callback:
                options.progress_callback(0, options.extracted_mb)
            while written < target_bytes:
                remaining = target_bytes - written
                write_size = min(len(chunk), remaining)
                tmp.write(chunk[:write_size])
                written += write_size
                if options.progress_callback:
                    progress_mb = written // (1024 * 1024)
                    options.progress_callback(progress_mb, options.extracted_mb)
        logger.debug(f"Generated temporary file: {temp_name}")

    # ----- 4. Dispatch to algorithm ----------------------------------------
    if options.algo == "deflate":
        compressed_size = deflate.compress_deflate(options, temp_name, source, target_bytes)
        format_name = options.fmt if options.fmt != "zip" else "zip"
        algo_name = "deflate"
    elif options.algo == "lzma":
        compressed_size = lzma.compress_lzma(options, temp_name, source, target_bytes)
        format_name = "xz" if not (source and os.path.isdir(source)) else "tar.xz"
        algo_name = "lzma"
    elif options.algo == "zstd":
        compressed_size = zstd.compress_zstd(options, temp_name, source, target_bytes)
        format_name = "zst" if not (source and os.path.isdir(source)) else "tar.zst"
        algo_name = "zstd"
    elif options.algo == "lz4":
        compressed_size = lz4.compress_lz4(options, temp_name, source, target_bytes)
        format_name = "lz4" if not (source and os.path.isdir(source)) else "tar.lz4"
        algo_name = "lz4"
    elif options.algo == "brotli":
    compressed_size = brotli.compress_brotli(options, temp_name, source, target_bytes)
    format_name = "br" if not (source and os.path.isdir(source)) else "tar.br"
    algo_name = "brotli"
    else:
        raise ConfigurationError(f"Unsupported algorithm: {options.algo}")

    # ----- 5. Compute stats and return ------------------------------------
    ratio = target_bytes / compressed_size if compressed_size else 0
    elapsed = time.time() - start_time
    logger.info(f"{algo_name.upper()} compression finished in {elapsed:.2f}s, ratio {ratio:.2f}x")

    return {
        "output": options.output,
        "extracted_bytes": target_bytes,
        "compressed_bytes": compressed_size,
        "ratio": ratio,
        "format": format_name,
        "algo": algo_name,
        "time": elapsed,
    }
