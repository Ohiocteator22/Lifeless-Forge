# forge/core/algorithms/lz4.py
import os
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
    if not HAS_LZ4:
        raise ConfigurationError("lz4 not installed. Please pip install lz4")

    if source is not None and os.path.isdir(source):
        if not options.output.lower().endswith(('.tar.lz4')):
            options.output = options.output.rsplit('.', 1)[0] + '.tar.lz4'
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar') as tmp:
            temp_tar = tmp.name
        try:
            with tarfile.open(temp_tar, "w") as tar:
                tar.add(source, arcname=os.path.basename(source))
            # LZ4 frame streaming
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
    else:
        if not options.output.lower().endswith(('.lz4')):
            options.output = options.output.rsplit('.', 1)[0] + '.lz4'
        if source is not None and os.path.isfile(source):
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
            with open(temp_name, "rb") as fin, open(options.output, "wb") as fout:
                compressor = lz4.frame.LZ4FrameCompressor()
                fout.write(compressor.begin())
                while True:
                    chunk = fin.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    fout.write(compressor.compress(chunk))
                fout.write(compressor.flush())
            os.remove(temp_name)
    return os.path.getsize(options.output)

def decompress_lz4(archive: str, output_dir: str) -> None:
    if not HAS_LZ4:
        raise ConfigurationError("lz4 not installed.")
    from forge.core.safe_extract import safe_extract_tar
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        temp_out = tmp.name
    try:
        with open(archive, "rb") as fin, open(temp_out, "wb") as fout:
            decompressor = lz4.frame.LZ4FrameDecompressor()
            while True:
                chunk = fin.read(CHUNK_SIZE)
                if not chunk:
                    break
                # decompress returns bytes; if chunk is incomplete, it may return None? Actually it returns bytes.
                fout.write(decompressor.decompress(chunk))
            # LZ4FrameDecompressor may have a flush method? We'll just use the decompress loop.
        if is_tar_file(temp_out):
            with tarfile.open(temp_out, 'r') as tar:
                safe_extract_tar(tar, output_dir)
        else:
            base = os.path.basename(archive)
            base = os.path.splitext(base)[0] + ".bin"
            out_path = os.path.join(output_dir, base)
            shutil.move(temp_out, out_path)
    except Exception as e:
        raise ExtractionError(f"Failed to decompress LZ4: {e}")
    finally:
        if os.path.exists(temp_out):
            os.remove(temp_out)
