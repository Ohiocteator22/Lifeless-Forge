# forge/core.py
import zipfile
import os
import tempfile
import json
import lzma
import shutil
import tarfile
import time
from pathlib import Path
from forge.utils import format_size, parse_size_string, get_progress_printer, format_time
from forge.templates import create_pptx_template, create_docx_template, create_xlsx_template

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

# =============================================================================
# Helper: Get total size of a file/folder
# =============================================================================

def get_total_size(path):
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

def is_tar_file(filepath):
    """Check if the file is a tar archive by looking at magic bytes."""
    try:
        with open(filepath, 'rb') as f:
            # Tar magic is at offset 257: "ustar" (or "ustar\0") or "tar\0"
            f.seek(257)
            magic = f.read(6)
            return magic in (b'ustar\0', b'ustar ', b'tar\0')
    except:
        return False

# =============================================================================
# Generation
# =============================================================================

def generate_zip(output, extracted_mb=None, pattern="A", compression=True, password=None,
                 progress_callback=None, legacy_crypto=False, fmt="zip", algo="deflate",
                 source=None):
    start_time = time.time()

    if source is not None:
        if not os.path.exists(source):
            raise FileNotFoundError(f"Input source not found: {source}")
        if fmt in ("pptx", "docx", "xlsx") and os.path.isdir(source):
            raise ValueError(f"Office format '{fmt}' does not support folders.")
        target_bytes = get_total_size(source)
    else:
        if extracted_mb is None:
            raise ValueError("Either source or extracted_mb must be provided.")
        target_bytes = extracted_mb * 1024 * 1024
        chunk = (pattern * (1024 * 1024)).encode()
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            temp_name = tmp.name
            written = 0
            if progress_callback:
                progress_callback(0, extracted_mb)
            while written < target_bytes:
                remaining = target_bytes - written
                write_size = min(len(chunk), remaining)
                tmp.write(chunk[:write_size])
                written += write_size
                if progress_callback:
                    progress_callback(written // (1024*1024), extracted_mb)

    # ---- LZMA ----
    if algo == "lzma":
        if source is not None and os.path.isdir(source):
            if not output.lower().endswith(('.tar.xz', '.txz')):
                output = output.rsplit('.', 1)[0] + '.tar.xz'
            with tarfile.open(output, "w:xz", preset=9) as tar:
                tar.add(source, arcname=os.path.basename(source))
        else:
            if not output.lower().endswith(('.xz', '.lzma')):
                output = output.rsplit('.', 1)[0] + '.xz'
            if source is not None and os.path.isfile(source):
                with lzma.open(output, "w", preset=9) as f_out:
                    with open(source, "rb") as f_in:
                        shutil.copyfileobj(f_in, f_out)
            else:
                with lzma.open(output, "w", preset=9) as f:
                    with open(temp_name, "rb") as src:
                        f.write(src.read())
                os.remove(temp_name)
        compressed_size = os.path.getsize(output)
        ratio = target_bytes / compressed_size if compressed_size else 0
        elapsed = time.time() - start_time
        return {"output": output, "extracted_bytes": target_bytes,
                "compressed_bytes": compressed_size, "ratio": ratio,
                "format": "xz" if not (source and os.path.isdir(source)) else "tar.xz",
                "algo": "lzma", "time": elapsed}

    # ---- Zstd ----
    if algo == "zstd":
        if not HAS_ZSTD:
            raise ImportError("zstandard not installed. Please pip install zstandard")
        if source is not None and os.path.isdir(source):
            if not output.lower().endswith(('.tar.zst', '.tzst')):
                output = output.rsplit('.', 1)[0] + '.tar.zst'
            with tempfile.NamedTemporaryFile(delete=False, suffix='.tar') as tmp:
                temp_tar = tmp.name
            try:
                with tarfile.open(temp_tar, "w") as tar:
                    tar.add(source, arcname=os.path.basename(source))
                with open(temp_tar, "rb") as f_in:
                    with open(output, "wb") as f_out:
                        compressor = zstd.ZstdCompressor(level=3)
                        f_out.write(compressor.compress(f_in.read()))
            finally:
                if os.path.exists(temp_tar):
                    os.remove(temp_tar)
        else:
            if not output.lower().endswith(('.zst', '.zstd')):
                output = output.rsplit('.', 1)[0] + '.zst'
            if source is not None and os.path.isfile(source):
                with open(source, "rb") as f_in:
                    with open(output, "wb") as f_out:
                        compressor = zstd.ZstdCompressor(level=3)
                        f_out.write(compressor.compress(f_in.read()))
            else:
                with open(temp_name, "rb") as f_in:
                    with open(output, "wb") as f_out:
                        compressor = zstd.ZstdCompressor(level=3)
                        f_out.write(compressor.compress(f_in.read()))
                os.remove(temp_name)
        compressed_size = os.path.getsize(output)
        ratio = target_bytes / compressed_size if compressed_size else 0
        elapsed = time.time() - start_time
        return {"output": output, "extracted_bytes": target_bytes,
                "compressed_bytes": compressed_size, "ratio": ratio,
                "format": "zst" if not (source and os.path.isdir(source)) else "tar.zst",
                "algo": "zstd", "time": elapsed}

    # ---- DEFLATE (ZIP / Office) ----
    if fmt in ("pptx", "docx", "xlsx"):
        with tempfile.TemporaryDirectory() as tmpdir:
            if fmt == "pptx":
                create_pptx_template(tmpdir)
                dummy_path = "ppt/media/dummy.bin"
            elif fmt == "docx":
                create_docx_template(tmpdir)
                dummy_path = "word/media/dummy.bin"
            elif fmt == "xlsx":
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
            try:
                if password and HAS_PYZIPPER:
                    encrypt_method = pyzipper.WZ_AES if not legacy_crypto else pyzipper.WZ_ZIP
                    mode = zipfile.ZIP_DEFLATED if compression else zipfile.ZIP_STORED
                    with pyzipper.AESZipFile(output, "w", compression=mode, encryption=encrypt_method) as z:
                        z.setpassword(password.encode())
                        for root, _, files in os.walk(tmpdir):
                            for file in files:
                                full_path = os.path.join(root, file)
                                arcname = os.path.relpath(full_path, tmpdir)
                                z.write(full_path, arcname=arcname)
                else:
                    compress_type = zipfile.ZIP_DEFLATED if compression else zipfile.ZIP_STORED
                    with zipfile.ZipFile(output, "w", compression=compress_type) as z:
                        for root, _, files in os.walk(tmpdir):
                            for file in files:
                                full_path = os.path.join(root, file)
                                arcname = os.path.relpath(full_path, tmpdir)
                                z.write(full_path, arcname=arcname)
            except ImportError:
                compress_type = zipfile.ZIP_DEFLATED if compression else zipfile.ZIP_STORED
                with zipfile.ZipFile(output, "w", compression=compress_type) as z:
                    for root, _, files in os.walk(tmpdir):
                        for file in files:
                            full_path = os.path.join(root, file)
                            arcname = os.path.relpath(full_path, tmpdir)
                            z.write(full_path, arcname=arcname)
                if password:
                    print("Warning: pyzipper not installed, password ignored.")
        compressed_size = os.path.getsize(output)
        ratio = target_bytes / compressed_size if compressed_size else 0
        elapsed = time.time() - start_time
        return {"output": output, "extracted_bytes": target_bytes,
                "compressed_bytes": compressed_size, "ratio": ratio,
                "format": fmt, "algo": "deflate", "time": elapsed}

    # ---- Plain ZIP ----
    if source is not None:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED if compression else zipfile.ZIP_STORED) as z:
            if os.path.isfile(source):
                z.write(source, arcname=os.path.basename(source))
            else:
                for root, _, files in os.walk(source):
                    for file in files:
                        full_path = os.path.join(root, file)
                        arcname = os.path.relpath(full_path, os.path.dirname(source))
                        z.write(full_path, arcname=arcname)
    else:
        try:
            if password and HAS_PYZIPPER:
                encrypt_method = pyzipper.WZ_AES if not legacy_crypto else pyzipper.WZ_ZIP
                mode = zipfile.ZIP_DEFLATED if compression else zipfile.ZIP_STORED
                with pyzipper.AESZipFile(output, "w", compression=mode, encryption=encrypt_method) as z:
                    z.setpassword(password.encode())
                    z.write(temp_name, arcname="compression_test_data.bin")
            else:
                compress_type = zipfile.ZIP_DEFLATED if compression else zipfile.ZIP_STORED
                with zipfile.ZipFile(output, "w", compression=compress_type) as z:
                    z.write(temp_name, arcname="compression_test_data.bin")
        except ImportError:
            compress_type = zipfile.ZIP_DEFLATED if compression else zipfile.ZIP_STORED
            with zipfile.ZipFile(output, "w", compression=compress_type) as z:
                z.write(temp_name, arcname="compression_test_data.bin")
            if password:
                print("Warning: pyzipper not installed, password ignored.")
        os.remove(temp_name)
    compressed_size = os.path.getsize(output)
    ratio = target_bytes / compressed_size if compressed_size else 0
    elapsed = time.time() - start_time
    return {"output": output, "extracted_bytes": target_bytes,
            "compressed_bytes": compressed_size, "ratio": ratio,
            "format": "zip", "algo": "deflate", "time": elapsed}

# =============================================================================
# Stats Printer
# =============================================================================

def print_stats(stats):
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

def generate_batch(tasks, progress_callback=None):
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

        stats = generate_zip(
            output=params["output"],
            extracted_mb=params["size"],
            pattern=params["pattern"],
            compression=params["compression"],
            password=params["password"],
            progress_callback=None,
            legacy_crypto=params["legacy"],
            fmt=params.get("format", "zip"),
            algo=params.get("algo", "deflate"),
            source=params.get("source"),
        )
        results.append(stats)
    return results

# =============================================================================
# Universal Extraction (improved with tar detection)
# =============================================================================

def extract_archive(archive, password=None, output_dir=None):
    if not os.path.exists(archive):
        raise FileNotFoundError(f"Archive not found: {archive}")
    if output_dir is None:
        output_dir = os.path.splitext(archive)[0] + "_extracted"
    os.makedirs(output_dir, exist_ok=True)

    # ---- Plain .tar ----
    if archive.lower().endswith('.tar'):
        with tarfile.open(archive, 'r') as tar:
            tar.extractall(output_dir)
        return output_dir

    # ---- .tar.xz / .txz ----
    if archive.lower().endswith(('.tar.xz', '.txz')):
        with tarfile.open(archive, 'r:xz') as tar:
            tar.extractall(output_dir)
        return output_dir

    # ---- .tar.zst / .tzst ----
    if archive.lower().endswith(('.tar.zst', '.tzst')):
        if not HAS_ZSTD:
            raise ImportError("zstandard not installed.")
        # Decompress to temp tar, then extract
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tar') as tmp:
            temp_tar = tmp.name
        try:
            with open(archive, "rb") as f_in:
                with open(temp_tar, "wb") as f_out:
                    decompressor = zstd.ZstdDecompressor()
                    f_out.write(decompressor.decompress(f_in.read()))
            with tarfile.open(temp_tar, "r") as tar:
                tar.extractall(output_dir)
            return output_dir
        finally:
            if os.path.exists(temp_tar):
                os.remove(temp_tar)

    # ---- .xz / .lzma (might be tar) ----
    if archive.lower().endswith(('.xz', '.lzma')):
        # Decompress to a temporary file first
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            temp_out = tmp.name
        try:
            with lzma.open(archive, 'rb') as f_in:
                with open(temp_out, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            # Check if it's a tar archive
            if is_tar_file(temp_out):
                with tarfile.open(temp_out, 'r') as tar:
                    tar.extractall(output_dir)
                return output_dir
            else:
                # Not tar – copy as a single file
                base = os.path.basename(archive)
                base = os.path.splitext(base)[0] + ".bin"
                out_path = os.path.join(output_dir, base)
                shutil.move(temp_out, out_path)
                return output_dir
        except lzma.LZMAError as e:
            raise ValueError(f"Failed to decompress XZ: {e}")
        finally:
            if os.path.exists(temp_out):
                os.remove(temp_out)

    # ---- .zst / .zstd (might be tar) ----
    if archive.lower().endswith(('.zst', '.zstd')):
        if not HAS_ZSTD:
            raise ImportError("zstandard not installed.")
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            temp_out = tmp.name
        try:
            with open(archive, "rb") as f_in:
                with open(temp_out, "wb") as f_out:
                    decompressor = zstd.ZstdDecompressor()
                    f_out.write(decompressor.decompress(f_in.read()))
            if is_tar_file(temp_out):
                with tarfile.open(temp_out, 'r') as tar:
                    tar.extractall(output_dir)
                return output_dir
            else:
                base = os.path.basename(archive)
                base = os.path.splitext(base)[0] + ".bin"
                out_path = os.path.join(output_dir, base)
                shutil.move(temp_out, out_path)
                return output_dir
        except Exception as e:
            raise ValueError(f"Failed to decompress Zstd: {e}")
        finally:
            if os.path.exists(temp_out):
                os.remove(temp_out)

    # ---- ZIP / Office (with password support) ----
    try:
        if HAS_PYZIPPER:
            with pyzipper.AESZipFile(archive, 'r') as z:
                if password:
                    z.setpassword(password.encode())
                z.extractall(output_dir)
                return output_dir
    except:
        pass
    # Fallback to standard zipfile
    with zipfile.ZipFile(archive, 'r') as z:
        if password:
            z.setpassword(password.encode())
        z.extractall(output_dir)
        return output_dir

# =============================================================================
# CLI info (unchanged)
# =============================================================================

def cli_info(args):
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
