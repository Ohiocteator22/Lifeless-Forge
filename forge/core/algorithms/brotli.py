# forge/core/algorithms/brotli.py
"""
Brotli compression – supports single files and folders (folders are tarred first).
Brotli is file‑specific (good for text, small files), but works with tar for folders.
"""

import os
import shutil
import tempfile
import tarfile
import logging
from typing import Dict, Any
from forge.core.base import CompressionOptions, CHUNK_SIZE, is_tar_file
from forge.exceptions import ConfigurationError, ExtractionError

try:
    import brotli
    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False
    brotli = None

logger = logging.getLogger(__name__)


def compress_brotli(options: CompressionOptions, temp_name: str, source: str, target_bytes: int) -> int:
    """
    Compress with Brotli – if source is a folder, pack it into a tar archive first.
    Uses quality level 4 (default) – adjustable later.
    """
    if not HAS_BROTLI:
        raise ConfigurationError("brotli not installed. Please pip install brotli")

    # ----- Folder input: create a tar and compress it --------------------
    if source is not None and os.path.isdir(source):
        if not options.output.lower().endswith(('.tar.br')):
            options.output = options.output.rsplit('.', 1)[0] + '.tar.br'
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar') as tmp:
            temp_tar = tmp.name
        try:
            with tarfile.open(temp_tar, "w") as tar:
                tar.add(source, arcname=os.path.basename(source))
            # Brotli streaming compression
            compressor = brotli.Compressor(quality=4)  # quality 0-11
            with open(temp_tar, "rb") as fin, open(options.output, "wb") as fout:
                while True:
                    chunk = fin.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    fout.write(compressor.process(chunk))
                fout.write(compressor.finish())
        finally:
            if os.path.exists(temp_tar):
                os.remove(temp_tar)

    # ----- Single file or generated data --------------------------------
    else:
        if not options.output.lower().endswith(('.br')):
            options.output = options.output.rsplit('.', 1)[0] + '.br'
        if source is not None and os.path.isfile(source):
            with open(source, "rb") as fin, open(options.output, "wb") as fout:
                compressor = brotli.Compressor(quality=4)
                while True:
                    chunk = fin.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    fout.write(compressor.process(chunk))
                fout.write(compressor.finish())
        else:
            with open(temp_name, "rb") as fin, open(options.output, "wb") as fout:
                compressor = brotli.Compressor(quality=4)
                while True:
                    chunk = fin.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    fout.write(compressor.process(chunk))
                fout.write(compressor.finish())
            os.remove(temp_name)   # clean up temporary file

    return os.path.getsize(options.output)


def decompress_brotli(archive: str, output_dir: str) -> None:
    """
    Decompress a .br or .tar.br file.
    If the decompressed data is a tar archive, extract it; otherwise save as .bin.
    """
    if not HAS_BROTLI:
        raise ConfigurationError("brotli not installed.")

    from forge.core.safe_extract import safe_extract_tar

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        temp_out = tmp.name

    try:
        # Decompress Brotli to temporary file
        with open(archive, "rb") as fin, open(temp_out, "wb") as fout:
            decompressor = brotli.Decompressor()
            while True:
                chunk = fin.read(CHUNK_SIZE)
                if not chunk:
                    break
                fout.write(decompressor.process(chunk))
            # process returns all; no need for flush

        # Check if the decompressed data is a tar archive
        if is_tar_file(temp_out):
            with tarfile.open(temp_out, 'r') as tar:
                safe_extract_tar(tar, output_dir)
        else:
            # Not a tar – treat as a single binary file
            base = os.path.basename(archive)
            base = os.path.splitext(base)[0] + ".bin"
            out_path = os.path.join(output_dir, base)
            shutil.move(temp_out, out_path)

    except Exception as e:
        raise ExtractionError(f"Failed to decompress Brotli: {e}") from e
    finally:
        if os.path.exists(temp_out):
            os.remove(temp_out)
