# forge/core/algorithms/zstd.py
import os
import tempfile
import tarfile
import logging
from typing import Dict, Any
from forge.core.base import CompressionOptions, CHUNK_SIZE, is_tar_file
from forge.exceptions import ConfigurationError, ExtractionError

try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False
    zstd = None

logger = logging.getLogger(__name__)

def compress_zstd(options: CompressionOptions, temp_name: str, source: str, target_bytes: int) -> int:
    if not HAS_ZSTD:
        raise ConfigurationError("zstandard not installed. Please pip install zstandard")

    if source is not None and os.path.isdir(source):
        if not options.output.lower().endswith(('.tar.zst', '.tzst')):
            options.output = options.output.rsplit('.', 1)[0] + '.tar.zst'
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar') as tmp:
            temp_tar = tmp.name
        try:
            with tarfile.open(temp_tar, "w") as tar:
                tar.add(source, arcname=os.path.basename(source))
            compressor = zstd.ZstdCompressor(level=3)
            cobj = compressor.compressobj()
            with open(temp_tar, "rb") as fin, open(options.output, "wb") as fout:
                while True:
                    chunk = fin.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    fout.write(cobj.compress(chunk))
                fout.write(cobj.flush())
        finally:
            if os.path.exists(temp_tar):
                os.remove(temp_tar)
    else:
        if not options.output.lower().endswith(('.zst', '.zstd')):
            options.output = options.output.rsplit('.', 1)[0] + '.zst'
        if source is not None and os.path.isfile(source):
            with open(source, "rb") as fin, open(options.output, "wb") as fout:
                compressor = zstd.ZstdCompressor(level=3)
                cobj = compressor.compressobj()
                while True:
                    chunk = fin.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    fout.write(cobj.compress(chunk))
                fout.write(cobj.flush())
        else:
            with open(temp_name, "rb") as fin, open(options.output, "wb") as fout:
                compressor = zstd.ZstdCompressor(level=3)
                cobj = compressor.compressobj()
                while True:
                    chunk = fin.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    fout.write(cobj.compress(chunk))
                fout.write(cobj.flush())
            os.remove(temp_name)
    return os.path.getsize(options.output)

def decompress_zstd(archive: str, output_dir: str) -> None:
    if not HAS_ZSTD:
        raise ConfigurationError("zstandard not installed.")
    from forge.core.safe_extract import safe_extract_tar
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        temp_out = tmp.name
    try:
        with open(archive, "rb") as fin, open(temp_out, "wb") as fout:
            decompressor = zstd.ZstdDecompressor()
            dobj = decompressor.decompressobj()
            while True:
                chunk = fin.read(CHUNK_SIZE)
                if not chunk:
                    break
                fout.write(dobj.decompress(chunk))
            fout.write(dobj.flush())
        if is_tar_file(temp_out):
            with tarfile.open(temp_out, 'r') as tar:
                safe_extract_tar(tar, output_dir)
        else:
            base = os.path.basename(archive)
            base = os.path.splitext(base)[0] + ".bin"
            out_path = os.path.join(output_dir, base)
            shutil.move(temp_out, out_path)
    except Exception as e:
        raise ExtractionError(f"Failed to decompress Zstd: {e}")
    finally:
        if os.path.exists(temp_out):
            os.remove(temp_out)
