# forge/core/algorithms/lz4.py
"""
LZ4 compression – supports single files and folders (folders are tarred first).
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
    import lz4.frame
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False
    lz4 = None

logger = logging.getLogger(__name__)


def compress_lz4(options: CompressionOptions, temp_name: str, source: str, target_bytes: int) -> int:
    """
    Compress with LZ4 – if source is a folder, pack it into a tar archive first.
    Returns the size of the compressed file.
    """
    if not HAS_LZ4:
        raise ConfigurationError("lz4 not installed. Please pip install lz4")

    # ----- Folder input: create a tar and compress it --------------------
    if source is not None and os.path.isdir(source):
        if not options.output.lower().endswith(('.tar.lz4')):
            options.output = options.output.rsplit('.', 1)[0] + '.tar.lz4'
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar') as tmp:
            temp_tar = tmp.name
        try:
            # Create tar
            with tarfile.open(temp_tar, "w") as tar:
                tar.add(source, arcname=os.path.basename(source))
            # Compress tar with LZ4 frame streaming
            with open(temp_tar, "rb") as fin, open(options.output, "wb") as fout:
                compressor = lz4.frame.LZ4FrameCompressor()
                fout.write(compressor.begin())
                while True:
                    chunk = fin.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    fout.write(compressor.compress(chunk))
                fout.write(compressor.flush())
        finally:
            if os.path.exists(temp_tar):
                os.remove(temp_tar)

    # ----- Single file or generated data --------------------------------
    else:
        if not options.output.lower().endswith(('.lz4')):
            options.output = options.output.rsplit('.', 1)[0] + '.lz4'
        if source is not None and os.path.isfile(source):
            # Compress existing file
            with open(source, "rb") as fin, open(options.output, "wb") as fout:
                compressor = lz4.frame.LZ4FrameCompressor()
                fout.write(compressor.begin())
                while True:
                    chunk = fin.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    fout.write(compressor.compress(chunk))
                fout.write(compressor.flush())
        else:
            # Compress generated data from temporary file
            with open(temp_name, "rb") as fin, open(options.output, "wb") as fout:
                compressor = lz4.frame.LZ4FrameCompressor()
                fout.write(compressor.begin())
                while True:
                    chunk = fin.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    fout.write(compressor.compress(chunk))
                fout.write(compressor.flush())
            os.remove(temp_name)   # clean up temporary file

    return os.path.getsize(options.output)


def decompress_lz4(archive: str, output_dir: str) -> None:
    """
    Decompress a .lz4 or .tar.lz4 file.
    If the decompressed data is a tar archive, extract it; otherwise save as .bin.
    """
    if not HAS_LZ4:
        raise ConfigurationError("lz4 not installed.")

    from forge.core.safe_extract import safe_extract_tar

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        temp_out = tmp.name

    try:
        # Decompress LZ4 frame to temporary file
        with open(archive, "rb") as fin, open(temp_out, "wb") as fout:
            decompressor = lz4.frame.LZ4FrameDecompressor()
            while True:
                chunk = fin.read(CHUNK_SIZE)
                if not chunk:
                    break
                # decompress returns bytes
                fout.write(decompressor.decompress(chunk))
            # Note: LZ4FrameDecompressor doesn't have a flush() method;
            # the loop processes all data.

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
        raise ExtractionError(f"Failed to decompress LZ4: {e}") from e
    finally:
        if os.path.exists(temp_out):
            os.remove(temp_out)
