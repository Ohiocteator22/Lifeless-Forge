# forge/core.py
import zipfile
import os
import tempfile
import json
import lzma
import shutil
import tarfile
from pathlib import Path
from .utils import format_size, parse_size_string, get_progress_printer
from .templates import create_pptx_template, create_docx_template, create_xlsx_template

# =============================================================================
# Helper: Get total size of a file/folder
# =============================================================================

def get_total_size(path):
    """Return total size in bytes of a file or folder."""
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total

# =============================================================================
# Generation
# =============================================================================

def generate_zip(output, extracted_mb=None, pattern="A", compression=True, password=None,
                 progress_callback=None, legacy_crypto=False, fmt="zip", algo="deflate",
                 source=None):
    """
    Generate a compressed archive.
    If source is provided, compress that file/folder.
    Otherwise, generate synthetic pattern of size extracted_mb MB.
    """
    # ---- 1. Determine input source ----
    if source is not None:
        if not os.path.exists(source):
            raise FileNotFoundError(f"Input source not found: {source}")
        # For Office formats, we only support a single file (not folder)
        if fmt in ("pptx", "docx", "xlsx") and os.path.isdir(source):
            raise ValueError(f"Office format '{fmt}' does not support folders. Please provide a single file.")
        # Compute target size for progress
        target_bytes = get_total_size(source)
        # We'll use source as the data source, no pattern needed
        use_pattern = False
    else:
        if extracted_mb is None:
            raise ValueError("Either source or extracted_mb must be provided.")
        target_bytes = extracted_mb * 1024 * 1024
        use_pattern = True
        chunk = (pattern * (1024 * 1024)).encode()

    # ---- 2. LZMA (XZ) mode ----
    if algo == "lzma":
        # For folders, we create a .tar.xz; for files, direct .xz
        if source is not None and os.path.isdir(source):
            # Create .tar.xz
            if not output.lower().endswith(('.tar.xz', '.txz')):
                output = output.rsplit('.', 1)[0] + '.tar.xz'
            with tarfile.open(output, "w:xz", preset=9) as tar:
                tar.add(source, arcname=os.path.basename(source))
            compressed_size = os.path.getsize(output)
            ratio = target_bytes / compressed_size if compressed_size else 0
            return {
                "output": output,
                "extracted_bytes": target_bytes,
                "compressed_bytes": compressed_size,
                "ratio": ratio,
                "format": "tar.xz",
                "algo": "lzma",
            }
        else:
            # Single file or pattern
            if not output.lower().endswith(('.xz', '.lzma')):
                output = output.rsplit('.', 1)[0] + '.xz'
            if source is not None and os.path.isfile(source):
                # Compress the file directly with lzma
                with lzma.open(output, "w", preset=9) as f_out:
                    with open(source, "rb") as f_in:
                        shutil.copyfileobj(f_in, f_out)
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
            else:
                # Generate pattern data and compress with lzma
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
    # For Office formats, we embed the source or pattern into the Office structure
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

            # Write data to dummy file
            if source is not None and os.path.isfile(source):
                # Copy the input file into the dummy location
                shutil.copy2(source, dummy_full)
            else:
                # Generate pattern data
                with open(dummy_full, "wb") as f:
                    written = 0
                    if progress_callback:
                        progress_callback(0, extracted_mb)
                    while written < target_bytes:
                        remaining = target_bytes - written
                        write_size = min(len(chunk), remaining)
                        f.write(chunk[:write_size])
                        written += write_size
                        if progress_callback:
                            progress_callback(written // (1024*1024), extracted_mb)

            # Zip the folder
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

    # ---- 4. Plain ZIP ----
    # Create a ZIP archive with the source or pattern
    if source is not None:
        # Source is a file or folder
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED if compression else zipfile.ZIP_STORED) as z:
            if os.path.isfile(source):
                z.write(source, arcname=os.path.basename(source))
            else:
                # Add folder recursively
                for root, _, files in os.walk(source):
                    for file in files:
                        full_path = os.path.join(root, file)
                        arcname = os.path.relpath(full_path, os.path.dirname(source))
                        z.write(full_path, arcname=arcname)
        compressed_size = os.path.getsize(output)
        ratio = target_bytes / compressed_size if compressed_size else 0
        return {
            "output": output,
            "extracted_bytes": target_bytes,
            "compressed_bytes": compressed_size,
            "ratio": ratio,
            "format": "zip",
            "algo": "deflate",
        }
    else:
        # Pattern generation
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
            "format": "zip",
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
            "source": None,
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
                total_bytes = get_total_size(params["source"]) if params["source"] else size * 1024 * 1024
                pbar = tqdm(total=total_bytes, unit="B", desc=os.path.basename(params["output"]), leave=False)
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
            source=params.get("source"),
        )
        results.append(stats)
    return results

# =============================================================================
# Universal Extraction (unchanged)
# =============================================================================

def extract_archive(archive, password=None, output_dir=None):
    if not os.path.exists(archive):
        raise FileNotFoundError(f"Archive not found: {archive}")

    if output_dir is None:
        output_dir = os.path.splitext(archive)[0] + "_extracted"
    os.makedirs(output_dir, exist_ok=True)

    # ---- XZ / LZMA decompression ----
    if archive.lower().endswith(('.xz', '.lzma')):
        try:
            with lzma.open(archive, 'rb') as f_in:
                base = os.path.basename(archive)
                base = os.path.splitext(base)[0] + ".bin"
                out_path = os.path.join(output_dir, base)
                with open(out_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            return output_dir
        except lzma.LZMAError as e:
            raise ValueError(f"Failed to decompress XZ file (corrupt?): {e}")

    # ---- .tar.xz decompression ----
    if archive.lower().endswith(('.tar.xz', '.txz')):
        with tarfile.open(archive, 'r:xz') as tar:
            tar.extractall(output_dir)
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
                raise
    except (ImportError, zipfile.BadZipFile, RuntimeError):
        with zipfile.ZipFile(archive, 'r') as z:
            if password:
                z.setpassword(password.encode())
            z.extractall(output_dir)
            return output_dir
    except Exception as e:
        with zipfile.ZipFile(archive, 'r') as z:
            if password:
                z.setpassword(password.encode())
            z.extractall(output_dir)
            return output_dir

# =============================================================================
# CLI info (with support for .tar.xz)
# =============================================================================

def cli_info(args):
    if not os.path.exists(args.zipfile):
        print(f"File not found: {args.zipfile}")
        return
    fname = args.zipfile.lower()
    if fname.endswith(('.xz', '.lzma')):
        size = os.path.getsize(args.zipfile)
        print(f"Archive: {args.zipfile}")
        print("Type: LZMA/XZ")
        print(f"Compressed size: {format_size(size)}")
        print("(Info for XZ files is limited)")
        return
    if fname.endswith(('.tar.xz', '.txz')):
        size = os.path.getsize(args.zipfile)
        print(f"Archive: {args.zipfile}")
        print("Type: TAR.XZ (LZMA)")
        print(f"Compressed size: {format_size(size)}")
        print("(Info for TAR.XZ files is limited)")
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
