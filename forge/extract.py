# forge/extract.py
import os
import zipfile
import tarfile
import logging
from forge.exceptions import ExtractionError

logger = logging.getLogger(__name__)

def safe_extract_zip(zip_ref: zipfile.ZipFile, output_dir: str) -> None:
    """Extract a zipfile safely, preventing path traversal attacks."""
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

def safe_extract_tar(tar_ref: tarfile.TarFile, output_dir: str) -> None:
    """Extract a tarfile safely."""
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
