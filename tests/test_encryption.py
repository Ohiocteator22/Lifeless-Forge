import pytest
import os
from pathlib import Path
from forge.core import generate_zip, extract_archive
import forge.core

def test_encryption_correct_password(tmp_workdir):
    output = tmp_workdir / "encrypted.zip"
    stats = generate_zip(output=str(output), extracted_mb=1, pattern="A", password="secret", algo="deflate", fmt="zip")
    extracted_dir = tmp_workdir / "extracted"
    extract_archive(str(output), password="secret", output_dir=str(extracted_dir))
    assert (extracted_dir / "compression_test_data.bin").exists()

def test_encryption_wrong_password(tmp_workdir):
    output = tmp_workdir / "encrypted.zip"
    stats = generate_zip(output=str(output), extracted_mb=1, pattern="A", password="secret", algo="deflate", fmt="zip")
    extracted_dir = tmp_workdir / "extracted"
    with pytest.raises(Exception):  # May raise RuntimeError or ValueError
        extract_archive(str(output), password="wrong", output_dir=str(extracted_dir))

def test_encryption_legacy(tmp_workdir):
    output = tmp_workdir / "encrypted_legacy.zip"
    stats = generate_zip(output=str(output), extracted_mb=1, pattern="A", password="secret", legacy_crypto=True, algo="deflate", fmt="zip")
    extracted_dir = tmp_workdir / "extracted"
    extract_archive(str(output), password="secret", output_dir=str(extracted_dir))
    assert (extracted_dir / "compression_test_data.bin").exists()

def test_encryption_missing_pyzipper(monkeypatch, tmp_workdir):
    # If pyzipper is installed, we skip this test.
    if forge.core.HAS_PYZIPPER:
        pytest.skip("pyzipper is installed, cannot test missing dependency")
    # Without pyzipper, generating with password should raise ImportError
    with pytest.raises(ImportError):
        generate_zip(output=str(tmp_workdir / "fail.zip"), extracted_mb=1, pattern="A", password="secret", algo="deflate", fmt="zip")
