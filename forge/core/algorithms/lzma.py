# forge/core/algorithms/lzma.py
import lzma
import tarfile
import os
import shutil
import tempfile
import logging
from typing import Dict, Any
from forge.core.base import CompressionOptions, is_tar_file
from forge.exceptions import ExtractionError, ConfigurationError

logger = logging.getLogger(__name__)

def compress_lzma(options: CompressionOptions, temp_name: str, source: str, target_bytes: int) -> Dict[str, Any]:
    if source is not None and os.path.isdir(source):
        if not options.output.lower().endswith(('.tar.xz', '.txz')):
            options.output = options.output.rsplit('.', 1)[0] + '.tar.xz'
        with tarfile.open(options.output, "w:xz", preset=9) as tar:
            tar.add(source, arcname=os.path.basename(source))
    else:
        if not options.output.lower().endswith(('.xz', '.lzma')):
            options.output = options.output.rsplit('.', 1)[0] + '.xz'
        if source is not None and os.path.isfile(source):
            with lzma.open(options.output, "w", preset=9) as f_out:
                with open(source, "rb") as f_in:
                    shutil.copyfileobj(f_in, f_out)
        else:
            with lzma.open(options.output, "w", preset=9) as f:
                with open(temp_name, "rb") as src:
                    shutil.copyfileobj(src, f)
            os.remove(temp_name)
    return os.path.getsize(options.output)

def decompress_lzma(archive: str, output_dir: str) -> None:
    from forge.core.safe_extract import safe_extract_tar
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        temp_out = tmp.name
    try:
        with lzma.open(archive, 'rb') as f_in:
            with open(temp_out, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        if is_tar_file(temp_out):
            with tarfile.open(temp_out, 'r') as tar:
                safe_extract_tar(tar, output_dir)
        else:
            base = os.path.basename(archive)
            base = os.path.splitext(base)[0] + ".bin"
            out_path = os.path.join(output_dir, base)
            shutil.move(temp_out, out_path)
    except lzma.LZMAError as e:
        raise ExtractionError(f"Failed to decompress XZ: {e}")
    finally:
        if os.path.exists(temp_out):
            os.remove(temp_out)
