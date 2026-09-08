# forge/core/extraction.py
import os
import tempfile
import tarfile
import lzma
import shutil
import logging
from forge.core.base import is_tar_file, CHUNK_SIZE
from forge.core.algorithms import deflate, lzma, zstd
from forge.core.safe_extract import safe_extract_tar
from forge.exceptions import ExtractionError, ConfigurationError

logger = logging.getLogger(__name__)

try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False

def extract_archive(archive: str, password: str = None, output_dir: str = None) -> str:
    if not os.path.exists(archive):
        raise FileNotFoundError(f"Archive not found: {archive}")
    if output_dir is None:
        output_dir = os.path.splitext(archive)[0] + "_extracted"
    os.makedirs(output_dir, exist_ok=True)

    logger.info(f"Extracting {archive} to {output_dir}")

    # ---- TAR (plain) ----
    if archive.lower().endswith('.tar'):
        with tarfile.open(archive, 'r') as tar:
            safe_extract_tar(tar, output_dir)
        return output_dir

    # ---- TAR.XZ / TXZ ----
    if archive.lower().endswith(('.tar.xz', '.txz')):
        with tarfile.open(archive, 'r:xz') as tar:
            safe_extract_tar(tar, output_dir)
        return output_dir

    # ---- TAR.ZST / TZST ----
    if archive.lower().endswith(('.tar.zst', '.tzst')):
        if not HAS_ZSTD:
            raise ConfigurationError("zstandard not installed.")
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar') as tmp:
            temp_tar = tmp.name
        try:
            with open(archive, "rb") as fin, open(temp_tar, "wb") as fout:
                decompressor = zstd.ZstdDecompressor()
                dobj = decompressor.decompressobj()
                while True:
                    chunk = fin.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    fout.write(dobj.decompress(chunk))
                fout.write(dobj.flush())
            with tarfile.open(temp_tar, "r") as tar:
                safe_extract_tar(tar, output_dir)
            return output_dir
        finally:
            if os.path.exists(temp_tar):
                os.remove(temp_tar)

    # ---- XZ / LZMA (maybe tar) ----
    if archive.lower().endswith(('.xz', '.lzma')):
        lzma.decompress_lzma(archive, output_dir)
        return output_dir

    # ---- ZST / ZSTD (maybe tar) ----
    if archive.lower().endswith(('.zst', '.zstd')):
        zstd.decompress_zstd(archive, output_dir)
        return output_dir

    # ---- ZIP / Office ----
    try:
        deflate.decompress_deflate(archive, password, output_dir)
        return output_dir
    except Exception as e:
        if "password" in str(e).lower() or "encrypt" in str(e).lower():
            raise ExtractionError(f"Failed to extract encrypted archive. Ensure the password is correct and pyzipper is installed for AES support.") from e
        raise ExtractionError(f"Extraction failed: {e}") from e
