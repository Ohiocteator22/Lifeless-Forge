import pytest
import os
from pathlib import Path
from forge.core import generate_zip, extract_archive

def test_roundtrip_zip(tmp_workdir):
    output = tmp_workdir / "test.zip"
    stats = generate_zip(output=str(output), extracted_mb=1, pattern="A", compression=True, algo="deflate", fmt="zip")
    extracted_dir = tmp_workdir / "extracted"
    extract_archive(str(output), output_dir=str(extracted_dir))
    assert (extracted_dir / "compression_test_data.bin").exists()

def test_roundtrip_zip_store(tmp_workdir):
    output = tmp_workdir / "test_store.zip"
    stats = generate_zip(output=str(output), extracted_mb=1, pattern="A", compression=False, algo="deflate", fmt="zip")
    extracted_dir = tmp_workdir / "extracted"
    extract_archive(str(output), output_dir=str(extracted_dir))
    assert (extracted_dir / "compression_test_data.bin").exists()

def test_roundtrip_pptx(tmp_workdir):
    output = tmp_workdir / "test.pptx"
    stats = generate_zip(output=str(output), extracted_mb=1, pattern="A", compression=True, algo="deflate", fmt="pptx")
    extracted_dir = tmp_workdir / "extracted"
    extract_archive(str(output), output_dir=str(extracted_dir))
    assert (extracted_dir / "ppt" / "presentation.xml").exists()
    assert (extracted_dir / "ppt" / "media" / "dummy.bin").exists()

def test_roundtrip_docx(tmp_workdir):
    output = tmp_workdir / "test.docx"
    stats = generate_zip(output=str(output), extracted_mb=1, pattern="A", compression=True, algo="deflate", fmt="docx")
    extracted_dir = tmp_workdir / "extracted"
    extract_archive(str(output), output_dir=str(extracted_dir))
    assert (extracted_dir / "word" / "document.xml").exists()

def test_roundtrip_xlsx(tmp_workdir):
    output = tmp_workdir / "test.xlsx"
    stats = generate_zip(output=str(output), extracted_mb=1, pattern="A", compression=True, algo="deflate", fmt="xlsx")
    extracted_dir = tmp_workdir / "extracted"
    extract_archive(str(output), output_dir=str(extracted_dir))
    assert (extracted_dir / "xl" / "workbook.xml").exists()

def test_roundtrip_lzma_single(tmp_workdir):
    output = tmp_workdir / "test.xz"
    stats = generate_zip(output=str(output), extracted_mb=1, pattern="A", compression=True, algo="lzma", fmt="zip")
    extracted_dir = tmp_workdir / "extracted"
    extract_archive(str(output), output_dir=str(extracted_dir))
    # Single file XZ extracts to .bin with basename of archive
    assert (extracted_dir / "test.bin").exists()

def test_roundtrip_lzma_folder(tmp_workdir):
    source = tmp_workdir / "source"
    source.mkdir()
    (source / "file1.txt").write_text("hello")
    (source / "file2.txt").write_text("world")
    output = tmp_workdir / "test.tar.xz"
    stats = generate_zip(output=str(output), source=str(source), algo="lzma", fmt="zip")
    extracted_dir = tmp_workdir / "extracted"
    extract_archive(str(output), output_dir=str(extracted_dir))
    assert (extracted_dir / "source" / "file1.txt").exists()
    assert (extracted_dir / "source" / "file2.txt").exists()

def test_roundtrip_zstd_single(tmp_workdir):
    output = tmp_workdir / "test.zst"
    stats = generate_zip(output=str(output), extracted_mb=1, pattern="A", compression=True, algo="zstd", fmt="zip")
    extracted_dir = tmp_workdir / "extracted"
    extract_archive(str(output), output_dir=str(extracted_dir))
    assert (extracted_dir / "test.bin").exists()

def test_roundtrip_zstd_folder(tmp_workdir):
    source = tmp_workdir / "source"
    source.mkdir()
    (source / "file1.txt").write_text("hello")
    (source / "file2.txt").write_text("world")
    output = tmp_workdir / "test.tar.zst"
    stats = generate_zip(output=str(output), source=str(source), algo="zstd", fmt="zip")
    extracted_dir = tmp_workdir / "extracted"
    extract_archive(str(output), output_dir=str(extracted_dir))
    assert (extracted_dir / "source" / "file1.txt").exists()
    assert (extracted_dir / "source" / "file2.txt").exists()

def test_edge_zero_byte(tmp_workdir):
    # Generate a 1 MB file (minimum positive)
    output = tmp_workdir / "small.zip"
    stats = generate_zip(output=str(output), extracted_mb=1, pattern="A", compression=True, algo="deflate", fmt="zip")
    extracted_dir = tmp_workdir / "extracted"
    extract_archive(str(output), output_dir=str(extracted_dir))
    assert (extracted_dir / "compression_test_data.bin").exists()
