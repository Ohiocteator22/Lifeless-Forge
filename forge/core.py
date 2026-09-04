# forge/core.py
import zipfile
import os
import tempfile
import json
import lzma
import shutil
from pathlib import Path
from .utils import format_size, parse_size_string, get_progress_printer
from .templates import create_pptx_template, create_docx_template, create_xlsx_template

# =============================================================================
# Generation
# =============================================================================

def generate_zip(output, extracted_mb, pattern="A", compression=True, password=None,
                 progress_callback=None, legacy_crypto=False, fmt="zip", algo="deflate"):
    target_bytes = extracted_mb * 1024 * 1024
    chunk = (pattern * (1024 * 1024)).encode()

    # ---- 1. Create the temporary data file ----
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

    # ---- 2. LZMA (XZ) mode ----
    if algo == "lzma":
        if not output.lower().endswith(('.xz', '.lzma')):
            output = output.rsplit('.', 1)[0] + '.xz'
        # preset=9 = max compression
        with lzma.open(output, "w", preset=9) as f:
            with open(temp_name, "rb") as src:
                f.write(src.read())
        os.remove(temp_name)
        compressed_size = os.path.getsize(output)
        ratio = target_bytes / compressed_size if compressed_size else 0
        return {
            "output": output,
            "extracted_bytes": target_bytes,
            "compressed_bytes": compressed_size,
            "ratio": ratio,
            "format": "xz",
            "algo": "lzma",
        }

    # ---- 3. DEFLATE (ZIP / Office) mode ----
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
            shutil.move(temp_name, dummy_full)

            try:
                if password:
                    import pyzipper
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
    else:
        # Plain ZIP with a single file
        try:
            if password:
                import pyzipper
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
    return {
        "output": output,
        "extracted_bytes": target_bytes,
        "compressed_bytes": compressed_size,
        "ratio": ratio,
        "format": fmt,
        "algo": "deflate",
    }

def print_stats(stats):
    print("Created:", stats["output"])
    print("Format:", stats.get("format", "zip").upper())
    print("Algorithm:", stats.get("algo", "deflate").upper())
    print("Compressed size:", format_size(stats["compressed_bytes"]))
    print("Extracted size:", format_size(stats["extracted_bytes"]))
    print("Compression ratio:", f"{stats['ratio']:.2f}x")

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
        }
        params.update(task)
        size = params["size"]
        if isinstance(size, str):
            size = parse_size_string(size)
        params["size"] = size

        single_progress = None
        if progress_callback:
            try:
                from tqdm import tqdm
                pbar = tqdm(total=size, unit="MB", desc=os.path.basename(params["output"]), leave=False)
                def inner_update(current, total):
                    pbar.update(current - pbar.n)
                    if current >= total:
                        pbar.close()
                single_progress = inner_update
            except ImportError:
                single_progress = get_progress_printer(enable=True, total=size, label=f"Generating {os.path.basename(params['output'])}")

        stats = generate_zip(
            output=params["output"],
            extracted_mb=params["size"],
            pattern=params["pattern"],
            compression=params["compression"],
            password=params["password"],
            progress_callback=single_progress,
            legacy_crypto=params["legacy"],
            fmt=params.get("format", "zip"),
            algo=params.get("algo", "deflate"),
        )
        results.append(stats)
    return results

# =============================================================================
# Universal Extraction (new)
# =============================================================================

def extract_archive(archive, password=None, output_dir=None):
    """
    Universal decompressor:
    - .zip / .pptx / .docx / .xlsx → ZIP extraction (supports AES + legacy passwords)
    - .xz / .lzma → LZMA decompression
    """
    if not os.path.exists(archive):
        raise FileNotFoundError(f"Archive not found: {archive}")

    if output_dir is None:
        output_dir = os.path.splitext(archive)[0] + "_extracted"
    os.makedirs(output_dir, exist_ok=True)

    # ---- XZ / LZMA decompression ----
    if archive.lower().endswith(('.xz', '.lzma')):
        with lzma.open(archive, 'rb') as f_in:
            base = os.path.basename(archive)
            base = os.path.splitext(base)[0] + ".bin"
            out_path = os.path.join(output_dir, base)
            with open(out_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        return output_dir

    # ---- ZIP (and Office) decompression ----
    try:
        import pyzipper
        with pyzipper.AESZipFile(archive, 'r') as z:
            try:
                if password:
                    z.setpassword(password.encode())
                z.extractall(output_dir)
                return output_dir
            except RuntimeError as e:
                if "Bad password" in str(e) or "invalid password" in str(e).lower():
                    raise ValueError("Incorrect password")
                # Fallback to standard zipfile
                raise
    except (ImportError, zipfile.BadZipFile, RuntimeError):
        # Fallback to standard zipfile (supports ZipCrypto and unencrypted)
        with zipfile.ZipFile(archive, 'r') as z:
            if password:
                z.setpassword(password.encode())
            z.extractall(output_dir)
            return output_dir
    except Exception as e:
        # Last resort: try standard zipfile
        with zipfile.ZipFile(archive, 'r') as z:
            if password:
                z.setpassword(password.encode())
            z.extractall(output_dir)
            return output_dir

# =============================================================================
# CLI info (unchanged, but now also shows algorithm if present)
# =============================================================================

def cli_info(args):
    if not os.path.exists(args.zipfile):
        print(f"File not found: {args.zipfile}")
        return
    try:
        with zipfile.ZipFile(args.zipfile, 'r') as z:
            info = z.infolist()
            if not info:
                print("No files in archive.")
                return
            total_compressed = sum(f.compress_size for f in info)
            total_extracted = sum(f.file_size for f in info)
            ratio = total_extracted / total_compressed if total_compressed else 0
            print(f"Archive: {args.zipfile}")
            print(f"Files: {len(info)}")
            print(f"Total compressed size: {format_size(total_compressed)}")
            print(f"Total extracted size:  {format_size(total_extracted)}")
            print(f"Overall ratio: {ratio:.2f}x")
    except Exception as e:
        print(f"Error reading ZIP: {e}")
