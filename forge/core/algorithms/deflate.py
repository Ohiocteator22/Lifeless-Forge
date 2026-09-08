# forge/core/algorithms/deflate.py
import zipfile
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any
from forge.core.base import CompressionOptions
from forge.templates import create_pptx_template, create_docx_template, create_xlsx_template
from forge.exceptions import ConfigurationError
import logging

logger = logging.getLogger(__name__)

try:
    import pyzipper
    HAS_PYZIPPER = True
except ImportError:
    HAS_PYZIPPER = False

def compress_deflate(options: CompressionOptions, temp_name: str, source: str, target_bytes: int) -> Dict[str, Any]:
    """Compress using DEFLATE (ZIP) – also handles Office formats."""
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
                if not HAS_PYZIPPER:
                    raise ConfigurationError("pyzipper required for encryption")
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
    else:
        # Plain ZIP
        if source is not None:
            if options.password is not None:
                if not HAS_PYZIPPER:
                    raise ConfigurationError("pyzipper required for encryption")
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
                if not HAS_PYZIPPER:
                    raise ConfigurationError("pyzipper required for encryption")
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
    return compressed_size

def decompress_deflate(archive: str, password: str, output_dir: str) -> None:
    from forge.core.safe_extract import safe_extract_zip
    try:
        if HAS_PYZIPPER:
            with pyzipper.AESZipFile(archive, 'r') as z:
                if password:
                    z.setpassword(password.encode())
                safe_extract_zip(z, output_dir)
        else:
            with zipfile.ZipFile(archive, 'r') as z:
                if password:
                    z.setpassword(password.encode())
                safe_extract_zip(z, output_dir)
    except Exception as e:
        raise
