# forge/core.py
import zipfile
import os
import tempfile
import json
import lzma
import shutil
import tarfile
import time
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Callable, Union, Dict, Any, List, Tuple

from forge.utils import format_size, parse_size_string, get_progress_printer, format_time
from forge.templates import create_pptx_template, create_docx_template, create_xlsx_template
from forge.exceptions import GenerationError, ExtractionError, CompressionError, ConfigurationError

# Set up logger for this module
logger = logging.getLogger(__name__)

# Try to import zstandard
try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False
    zstd = None

# Try to import pyzipper
try:
    import pyzipper
    HAS_PYZIPPER = True
except ImportError:
    HAS_PYZIPPER = False

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
CHUNK_SIZE = 1024 * 1024          # 1 MiB
DEFAULT_MAX_SIZE_MB = 10 * 1024   # 10 GiB
MAX_SIZE_MB = int(os.environ.get("FORGE_MAX_SIZE_MB", DEFAULT_MAX_SIZE_MB))

# ----------------------------------------------------------------------
# Dataclass for compression options
# ----------------------------------------------------------------------
@dataclass
class CompressionOptions:
    """Options for archive generation."""
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

# =============================================================================
# Helper: Get total size of a file/folder
# =============================================================================

def get_total_size(path: str) -> int:
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total

# =============================================================================
# Helper: Check if a file is a tar archive
# =============================================================================

def is_tar_file(filepath: str) -> bool:
    """Check if the file is a tar archive by looking at magic bytes."""
    try:
        with open(filepath, 'rb') as f:
            f.seek(257)
            magic = f.read(6)
            return magic in (b'ustar\0', b'ustar ', b'tar\0')
    except:
        return False

# =============================================================================
# Safe ZIP extraction (prevents path traversal)
# =============================================================================

def safe_extract_zip(zip_ref: zipfile.ZipFile, output_dir: str) -> None:
    """
    Extract a zipfile safely, preventing path traversal attacks.

    Raises ExtractionError if a suspicious entry is detected.
    """
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    for member in zip_ref.infolist():
        filename = member.filename
        if os.path.isabs(filename) or filename.startswith('/') or filename.startswith('\\') or ':' in filename:
            raise ExtractionError(f"Absolute path not allowed: {filename}")

        target_path = os.path.join(output_dir, filename)
        target_path = os.path.normpath(target_path)

        if not target_path.startswith(os.path.abspath(output_dir) + os.sep):
            raise ExtractionError(f"Path traversal attempt: {filename}")

        if member.is_dir():
            os.makedirs(target_path, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, 'wb') as f:
                f.write(zip_ref.read(member))
    logger.debug(f"Extracted {len(zip_ref.infolist())} entries to {output_dir}")

# =============================================================================
# Safe TAR extraction (prevents path traversal, rejects symlinks/hardlinks)
# =============================================================================

def safe_extract_tar(tar_ref: tarfile.TarFile, output_dir: str) -> None:
    """
    Extract a tarfile safely.
    Raises ExtractionError for unsafe entries.
    """
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    for member in tar_ref.getmembers():
        if os.path.isabs(member.name) or member.name.startswith('/') or ':' in member.name:
            raise ExtractionError(f"Absolute path not allowed: {member.name}")
        target_path = os.path.join(output_dir, member.name)
        target_path = os.path.normpath(target_path)
        if not target_path.startswith(output_dir + os.sep):
            raise ExtractionError(f"Path traversal attempt: {member.name}")

        if member.islnk() or member.issym():
            raise ExtractionError(f"Symlink or hardlink not allowed: {member.name}")

        tar_ref.extract(member, output_dir, set_attrs=False)
    logger.debug(f"Extracted {len(tar_ref.getmembers())} members from tar to {output_dir}")

# =============================================================================
# Generation (with size validation, streaming, and logging)
# =============================================================================

def generate_zip(options: CompressionOptions) -> Dict[str, Any]:
    """Create an archive based on the given options."""
    start_time = time.time()
    logger.info(f"Starting generation: output={options.output}, format={options.fmt}, algo={options.algo}")

    # ----- Size validation -----
    if options.extracted_mb is not None:
        if not isinstance(options.extracted_mb, (int, float)) or options.extracted_mb <= 0:
            raise ConfigurationError(f"Invalid extracted_mb: {options.extracted_mb} (must be > 0)")
        if options.extracted_mb > MAX_SIZE_MB:
            raise ConfigurationError(
                f"Requested size ({options.extracted_mb} MB) exceeds maximum allowed ({MAX_SIZE_MB} MB). "
                "Set FORGE_MAX_SIZE_MB environment variable to increase."
            )

    # ----- Encryption validation -----
    if options.password is not None:
        if options.algo in ("lzma", "zstd"):
            raise ConfigurationError("Encryption is not supported for LZMA or Zstandard compression.")
        if not HAS_PYZIPPER:
            raise ConfigurationError(
                "pyzipper is required for encryption. Please install: pip install pyzipper"
            )

    # ----- Input validation -----
    source = options.source
    if source is not None:
        if not os.path.exists(source):
            raise FileNotFoundError(f"Input source not found: {source}")
        if options.fmt in ("pptx", "docx", "xlsx") and os.path.isdir(source):
            raise ConfigurationError(f"Office format '{options.fmt}' does not support folders.")
        target_bytes = get_total_size(source)
    else:
        if options.extracted_mb is None:
            raise ConfigurationError("Either source or extracted_mb must be provided.")
        target_bytes = options.extracted_mb * 1024 * 1024
        chunk = (options.pattern * (1024 * 1024)).encode()
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
                    options.progress_callback(written // (1024*1024), options.extracted_mb)
        logger.debug(f"Generated temporary file: {temp_name}")

    # ---- LZMA ----
    if options.algo == "lzma":
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
        compressed_size = os.path.getsize(options.output)
        ratio = target_bytes / compressed_size if compressed_size else 0
        elapsed = time.time() - start_time
        logger.info(f"LZMA compression finished in {elapsed:.2f}s, ratio {ratio:.2f}x")
        return {"output": options.output, "extracted_bytes": target_bytes,
                "compressed_bytes": compressed_size, "ratio": ratio,
                "format": "xz" if not (source and os.path.isdir(source)) else "tar.xz",
                "algo": "lzma", "time": elapsed}

    # ---- Zstd ----
    if options.algo == "zstd":
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
                # Stream compress the tar
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
                compressor = zstd.ZstdCompressor(level=3)
                cobj = compressor.compressobj()
                with open(source, "rb") as fin, open(options.output, "wb") as fout:
                    while True:
                        chunk = fin.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        fout.write(cobj.compress(chunk))
                    fout.write(cobj.flush())
            else:
                compressor = zstd.ZstdCompressor(level=3)
                cobj = compressor.compressobj()
                with open(temp_name, "rb") as fin, open(options.output, "wb") as fout:
                    while True:
                        chunk = fin.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        fout.write(cobj.compress(chunk))
                    fout.write(cobj.flush())
                os.remove(temp_name)
        compressed_size = os.path.getsize(options.output)
        ratio = target_bytes / compressed_size if compressed_size else 0
        elapsed = time.time() - start_time
        logger.info(f"Zstd compression finished in {elapsed:.2f}s, ratio {ratio:.2f}x")
        return {"output": options.output, "extracted_bytes": target_bytes,
                "compressed_bytes": compressed_size, "ratio": ratio,
                "format": "zst" if not (source and os.path.isdir(source)) else "tar.zst",
                "algo": "zstd", "time": elapsed}

    # ---- DEFLATE (ZIP / Office) ----
    if options.fmt in ("pptx", "docx", "xlsx"):
        with tempfile.TemporaryDirectory() as tmpdir:
            if options.fmt == "pptx":
                create_pptx_template(tmpdir)
                dummy_path = "ppt/media/dummy.bin"
            elif options.fmt == "docx":
                create_docx_template(tmpdir)
                dummy_path = "word/media/dummy.bin"
            elif options.fmt == "xlsx":
                create_xlsx_template(tmpdir)
                dummy_path = "xl/media/dummy.bin"
            else:
                dummy_path = "dummy.bin"
            dummy_full = Path(tmpdir) / dummy_path
            dummy_full.parent.mkdir(parents=True, exist_ok=True)
            if source is not None and os.path.isfile(source):
                shutil.copy2(source, dummy_full)
            else:
                shutil.move(temp_name, dummy_full)

            if options.password is not None:
                encrypt_method = pyzipper.WZ_AES if not options.legacy_crypto else pyzipper.WZ_ZIP
                mode = zipfile.ZIP_DEFLATED if options.compression else zipfile.ZIP_STORED
                with pyzipper.AESZipFile(options.output, "w", compression=mode, encryption=encrypt_method) as z:
                    z.setpassword(options.password.encode())
                    for root, _, files in os.walk(tmpdir):
                        for file in files:
                            full_path = os.path.join(root, file)
                            arcname = os.path.relpath(full_path, tmpdir)
                            z.write(full_path, arcname=arcname)
            else:
                compress_type = zipfile.ZIP_DEFLATED if options.compression else zipfile.ZIP_STORED
                with zipfile.ZipFile(options.output, "w", compression=compress_type) as z:
                    for root, _, files in os.walk(tmpdir):
                        for file in files:
                            full_path = os.path.join(root, file)
                            arcname = os.path.relpath(full_path, tmpdir)
                            z.write(full_path, arcname=arcname)

        compressed_size = os.path.getsize(options.output)
        ratio = target_bytes / compressed_size if compressed_size else 0
        elapsed = time.time() - start_time
        logger.info(f"Office ZIP creation finished in {elapsed:.2f}s")
        return {"output": options.output, "extracted_bytes": target_bytes,
                "compressed_bytes": compressed_size, "ratio": ratio,
                "format": options.fmt, "algo": "deflate", "time": elapsed}

    # ---- Plain ZIP ----
    if source is not None:
        if options.password is not None:
            encrypt_method = pyzipper.WZ_AES if not options.legacy_crypto else pyzipper.WZ_ZIP
            mode = zipfile.ZIP_DEFLATED if options.compression else zipfile.ZIP_STORED
            with pyzipper.AESZipFile(options.output, "w", compression=mode, encryption=encrypt_method) as z:
                z.setpassword(options.password.encode())
                if os.path.isfile(source):
                    z.write(source, arcname=os.path.basename(source))
                else:
                    for root, _, files in os.walk(source):
                        for file in files:
                            full_path = os.path.join(root, file)
                            arcname = os.path.relpath(full_path, os.path.dirname(source))
                            z.write(full_path, arcname=arcname)
        else:
            compress_type = zipfile.ZIP_DEFLATED if options.compression else zipfile.ZIP_STORED
            with zipfile.ZipFile(options.output, "w", compression=compress_type) as z:
                if os.path.isfile(source):
                    z.write(source, arcname=os.path.basename(source))
                else:
                    for root, _, files in os.walk(source):
                        for file in files:
                            full_path = os.path.join(root, file)
                            arcname = os.path.relpath(full_path, os.path.dirname(source))
                            z.write(full_path, arcname=arcname)
    else:
        if options.password is not None:
            encrypt_method = pyzipper.WZ_AES if not options.legacy_crypto else pyzipper.WZ_ZIP
            mode = zipfile.ZIP_DEFLATED if options.compression else zipfile.ZIP_STORED
            with pyzipper.AESZipFile(options.output, "w", compression=mode, encryption=encrypt_method) as z:
                z.setpassword(options.password.encode())
                z.write(temp_name, arcname="compression_test_data.bin")
        else:
            compress_type = zipfile.ZIP_DEFLATED if options.compression else zipfile.ZIP_STORED
            with zipfile.ZipFile(options.output, "w", compression=compress_type) as z:
                z.write(temp_name, arcname="compression_test_data.bin")
        os.remove(temp_name)

    compressed_size = os.path.getsize(options.output)
    ratio = target_bytes / compressed_size if compressed_size else 0
    elapsed = time.time() - start_time
    logger.info(f"ZIP compression finished in {elapsed:.2f}s")
    return {"output": options.output, "extracted_bytes": target_bytes,
            "compressed_bytes": compressed_size, "ratio": ratio,
            "format": "zip", "algo": "deflate", "time": elapsed}

# =============================================================================
# Stats Printer
# =============================================================================

def print_stats(stats: Dict[str, Any]) -> None:
    print("Created:", stats["output"])
    print("Format:", stats.get("format", "zip").upper())
    print("Algorithm:", stats.get("algo", "deflate").upper())
    print("Compressed size:", format_size(stats["compressed_bytes"]))
    print("Extracted size:", format_size(stats["extracted_bytes"]))
    print("Compression ratio:", f"{stats['ratio']:.2f}x")
    if "time" in stats:
        print("-" * 40)
        print("Time taken:", format_time(stats["time"]))

# =============================================================================
# Batch generation
# =============================================================================

def generate_batch(tasks: List[Dict[str, Any]], progress_callback: Optional[Callable[[int, int, str], None]] = None) -> List[Dict[str, Any]]:
    results = []
    total_tasks = len(tasks)
    for idx, task in enumerate(tasks):
        if progress_callback:
            progress_callback(idx, total_tasks, f"Task {idx+1}/{total_tasks}")

        params = {
            "output": f"batch_{idx+1}.zip",
            "size": 60,
            "pattern": "A",
            "compression": True,
            "password": None,
            "legacy": False,
            "format": "zip",
            "algo": "deflate",
            "source": None,
        }
        params.update(task)
        if isinstance(params["size"], str):
            params["size"] = parse_size_string(params["size"])

        opts = CompressionOptions(
            output=params["output"],
            extracted_mb=params["size"],
            pattern=params["pattern"],
            compression=params["compression"],
            password=params["password"],
            legacy_crypto=params["legacy"],
            fmt=params.get("format", "zip"),
            algo=params.get("algo", "deflate"),
            source=params.get("source"),
        )
        stats = generate_zip(opts)
        results.append(stats)
    return results

# =============================================================================
# Universal Extraction (with streaming decompression and safe extraction)
# =============================================================================

def extract_archive(archive: str, password: Optional[str] = None, output_dir: Optional[str] = None) -> str:
    if not os.path.exists(archive):
        raise FileNotFoundError(f"Archive not found: {archive}")
    if output_dir is None:
        output_dir = os.path.splitext(archive)[0] + "_extracted"
    os.makedirs(output_dir, exist_ok=True)

    logger.info(f"Extracting {archive} to {output_dir}")

    # ---- Plain .tar ----
    if archive.lower().endswith('.tar'):
        with tarfile.open(archive, 'r') as tar:
            safe_extract_tar(tar, output_dir)
        return output_dir

    # ---- .tar.xz / .txz ----
    if archive.lower().endswith(('.tar.xz', '.txz')):
        with tarfile.open(archive, 'r:xz') as tar:
            safe_extract_tar(tar, output_dir)
        return output_dir

    # ---- .tar.zst / .tzst ----
    if archive.lower().endswith(('.tar.zst', '.tzst')):
        if not HAS_ZSTD:
            raise ConfigurationError("zstandard not installed.")
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar') as tmp:
            temp_tar = tmp.name
        try:
            # Decompress streaming
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

    # ---- .xz / .lzma (might be tar) ----
    if archive.lower().endswith(('.xz', '.lzma')):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            temp_out = tmp.name
        try:
            with lzma.open(archive, 'rb') as f_in:
                with open(temp_out, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            if is_tar_file(temp_out):
                with tarfile.open(temp_out, 'r') as tar:
                    safe_extract_tar(tar, output_dir)
                return output_dir
            else:
                base = os.path.basename(archive)
                base = os.path.splitext(base)[0] + ".bin"
                out_path = os.path.join(output_dir, base)
                shutil.move(temp_out, out_path)
                return output_dir
        except lzma.LZMAError as e:
            raise ExtractionError(f"Failed to decompress XZ: {e}")
        finally:
            if os.path.exists(temp_out):
                os.remove(temp_out)

    # ---- .zst / .zstd (might be tar) ----
    if archive.lower().endswith(('.zst', '.zstd')):
        if not HAS_ZSTD:
            raise ConfigurationError("zstandard not installed.")
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            temp_out = tmp.name
        try:
            # Decompress streaming
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
                return output_dir
            else:
                base = os.path.basename(archive)
                base = os.path.splitext(base)[0] + ".bin"
                out_path = os.path.join(output_dir, base)
                shutil.move(temp_out, out_path)
                return output_dir
        except Exception as e:
            raise ExtractionError(f"Failed to decompress Zstd: {e}")
        finally:
            if os.path.exists(temp_out):
                os.remove(temp_out)

    # ---- ZIP / Office (with password support) ----
    try:
        if HAS_PYZIPPER:
            with pyzipper.AESZipFile(archive, 'r') as z:
                if password:
                    z.setpassword(password.encode())
                safe_extract_zip(z, output_dir)
                return output_dir
        else:
            with zipfile.ZipFile(archive, 'r') as z:
                if password:
                    z.setpassword(password.encode())
                safe_extract_zip(z, output_dir)
                return output_dir
    except Exception as e:
        if "password" in str(e).lower() or "encrypt" in str(e).lower():
            raise ExtractionError(f"Failed to extract encrypted archive. Ensure the password is correct and pyzipper is installed for AES support.") from e
        raise ExtractionError(f"Extraction failed: {e}") from e

# =============================================================================
# CLI info (unchanged)
# =============================================================================

def cli_info(args: Any) -> None:
    if not os.path.exists(args.zipfile):
        print(f"File not found: {args.zipfile}")
        return
    fname = args.zipfile.lower()
    if fname.endswith(('.xz', '.lzma', '.zst', '.zstd', '.tar.xz', '.txz', '.tar.zst', '.tzst')):
        size = os.path.getsize(args.zipfile)
        print(f"Archive: {args.zipfile}")
        print("Type:", "LZMA/XZ" if '.xz' in fname else "Zstandard")
        print(f"Compressed size: {format_size(size)}")
        print("(Detailed info not available)")
        return
    try:
        with zipfile.ZipFile(args.zipfile, 'r') as z:
            info = z.infolist()
            if not info:
                print("No files.")
                return
            total_compressed = sum(f.compress_size for f in info)
            total_extracted = sum(f.file_size for f in info)
            ratio = total_extracted / total_compressed if total_compressed else 0
            print(f"Archive: {args.zipfile}")
            print(f"Files: {len(info)}")
            print(f"Compressed: {format_size(total_compressed)}")
            print(f"Extracted:  {format_size(total_extracted)}")
            print(f"Ratio: {ratio:.2f}x")
    except Exception as e:
        print(f"Error: {e}")
