#!/usr/bin/env python3
# forge_mono.py – Monolithic Lifeless-Forge (everything included)

import sys
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import zipfile
import tempfile
import json
import lzma
import shutil
import tarfile
import re
from pathlib import Path
import xml.etree.ElementTree as ET

# ---------- 3rd party imports (optional) ----------
try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False
    zstd = None

try:
    import sv_ttk
    HAS_SV_TTK = True
except ImportError:
    HAS_SV_TTK = False

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False
    TkinterDnD = None
    DND_FILES = None

try:
    import pyzipper
    HAS_PYZIPPER = True
except ImportError:
    HAS_PYZIPPER = False

# =============================================================================
# UTILITIES
# =============================================================================

def format_size(size):
    units = ["B", "KB", "MB", "GB"]
    for unit in units:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"

def parse_size_string(s):
    s = str(s).strip().upper()
    match = re.match(r"([\d.]+)\s*(?:([KMGT])B?)?", s)
    if not match:
        raise ValueError(f"Invalid size format: {s}")
    val = float(match.group(1))
    unit = match.group(2) or "M"
    multipliers = {"K": 1/1024, "M": 1, "G": 1024, "T": 1024*1024}
    return int(val * multipliers.get(unit, 1))

def get_progress_printer(enable=False, total=None, label="Writing"):
    if not enable:
        return lambda current, total: None
    try:
        from tqdm import tqdm
        pbar = tqdm(total=total, unit="MB", desc=label, leave=False)
        def update(current, total):
            pbar.update(current - pbar.n)
            if current >= total:
                pbar.close()
        return update
    except ImportError:
        last = [0]
        def update(current, total):
            percent = int(current / total * 100) if total else 0
            if percent - last[0] >= 10:
                print(f"{label}: {percent}%", end="\r")
                last[0] = percent
            if current >= total:
                print(f"{label}: 100%")
        return update

# =============================================================================
# CONFIG (dark mode persistence)
# =============================================================================

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".lifeless-forge")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def detect_system_theme():
    system = os.name
    if system == 'nt':  # Windows
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return value == 0
        except:
            return None
    elif system == 'posix':  # macOS/Linux
        try:
            import subprocess
            if sys.platform == 'darwin':
                result = subprocess.run(['defaults', 'read', '-g', 'AppleInterfaceStyle'],
                                        capture_output=True, text=True)
                if result.returncode == 0:
                    return "Dark" in result.stdout
        except:
            pass
        return None
    return None

# =============================================================================
# TEMPLATES (Office document builders)
# =============================================================================

def create_pptx_template(temp_dir):
    (Path(temp_dir) / "ppt" / "media").mkdir(parents=True, exist_ok=True)
    (Path(temp_dir) / "ppt" / "_rels").mkdir(parents=True, exist_ok=True)
    (Path(temp_dir) / "ppt" / "slides").mkdir(parents=True, exist_ok=True)
    (Path(temp_dir) / "_rels").mkdir(parents=True, exist_ok=True)

    ct = ET.Element("Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types")
    ET.SubElement(ct, "Default", Extension="xml", ContentType="application/xml")
    ET.SubElement(ct, "Default", Extension="bin", ContentType="application/vnd.ms-office.dummy")
    ET.SubElement(ct, "Override", PartName="/ppt/presentation.xml", ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml")
    ET.SubElement(ct, "Override", PartName="/ppt/slides/slide1.xml", ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml")
    ET.SubElement(ct, "Override", PartName="/ppt/media/dummy.bin", ContentType="application/vnd.ms-office.dummy")
    (Path(temp_dir) / "[Content_Types].xml").write_text(ET.tostring(ct, encoding="unicode", xml_declaration=True))

    rels = ET.Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
    ET.SubElement(rels, "Relationship", Id="rId1", Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", Target="ppt/presentation.xml")
    (Path(temp_dir) / "_rels" / ".rels").write_text(ET.tostring(rels, encoding="unicode", xml_declaration=True))

    pres = ET.Element("presentation", attrib={
        "xmlns": "http://schemas.openxmlformats.org/presentationml/2006/main",
        "xmlns:r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    })
    sldIdLst = ET.SubElement(pres, "sldIdLst")
    ET.SubElement(sldIdLst, "sldId", attrib={"Id": "256", "r:id": "rId1"})
    (Path(temp_dir) / "ppt" / "presentation.xml").write_text(ET.tostring(pres, encoding="unicode", xml_declaration=True))

    rels2 = ET.Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
    ET.SubElement(rels2, "Relationship", Id="rId1", Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide", Target="slides/slide1.xml")
    (Path(temp_dir) / "ppt" / "_rels" / "presentation.xml.rels").write_text(ET.tostring(rels2, encoding="unicode", xml_declaration=True))

    slide = ET.Element("slide", xmlns="http://schemas.openxmlformats.org/presentationml/2006/main")
    cSld = ET.SubElement(slide, "cSld")
    spTree = ET.SubElement(cSld, "spTree")
    nvGrpSpPr = ET.SubElement(spTree, "nvGrpSpPr")
    ET.SubElement(nvGrpSpPr, "cNvPr", id="1", name="")
    ET.SubElement(nvGrpSpPr, "cNvGrpSpPr")
    ET.SubElement(nvGrpSpPr, "nvPr")
    ET.SubElement(spTree, "grpSpPr")
    sp = ET.SubElement(spTree, "sp")
    nvSpPr = ET.SubElement(sp, "nvSpPr")
    ET.SubElement(nvSpPr, "cNvPr", id="2", name="Dummy")
    ET.SubElement(nvSpPr, "cNvSpPr")
    ET.SubElement(nvSpPr, "nvPr")
    spPr = ET.SubElement(sp, "spPr")
    xfrm = ET.SubElement(spPr, "xfrm")
    ET.SubElement(xfrm, "off", x="0", y="0")
    ET.SubElement(xfrm, "ext", cx="0", cy="0")
    ET.SubElement(sp, "txBody")
    (Path(temp_dir) / "ppt" / "slides" / "slide1.xml").write_text(ET.tostring(slide, encoding="unicode", xml_declaration=True))

def create_docx_template(temp_dir):
    (Path(temp_dir) / "word").mkdir(parents=True, exist_ok=True)
    (Path(temp_dir) / "word" / "_rels").mkdir(parents=True, exist_ok=True)
    (Path(temp_dir) / "_rels").mkdir(parents=True, exist_ok=True)

    ct = ET.Element("Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types")
    ET.SubElement(ct, "Default", Extension="xml", ContentType="application/xml")
    ET.SubElement(ct, "Default", Extension="bin", ContentType="application/vnd.ms-office.dummy")
    ET.SubElement(ct, "Override", PartName="/word/document.xml", ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml")
    (Path(temp_dir) / "[Content_Types].xml").write_text(ET.tostring(ct, encoding="unicode", xml_declaration=True))

    rels = ET.Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
    ET.SubElement(rels, "Relationship", Id="rId1", Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", Target="word/document.xml")
    (Path(temp_dir) / "_rels" / ".rels").write_text(ET.tostring(rels, encoding="unicode", xml_declaration=True))

    doc = ET.Element("document", xmlns="http://schemas.openxmlformats.org/wordprocessingml/2006/main")
    body = ET.SubElement(doc, "body")
    p = ET.SubElement(body, "p")
    r = ET.SubElement(p, "r")
    ET.SubElement(r, "t").text = "Dummy content"
    (Path(temp_dir) / "word" / "document.xml").write_text(ET.tostring(doc, encoding="unicode", xml_declaration=True))

def create_xlsx_template(temp_dir):
    (Path(temp_dir) / "xl" / "worksheets").mkdir(parents=True, exist_ok=True)
    (Path(temp_dir) / "xl" / "_rels").mkdir(parents=True, exist_ok=True)
    (Path(temp_dir) / "_rels").mkdir(parents=True, exist_ok=True)

    ct = ET.Element("Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types")
    ET.SubElement(ct, "Default", Extension="xml", ContentType="application/xml")
    ET.SubElement(ct, "Default", Extension="bin", ContentType="application/vnd.ms-office.dummy")
    ET.SubElement(ct, "Override", PartName="/xl/workbook.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")
    ET.SubElement(ct, "Override", PartName="/xl/worksheets/sheet1.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
    (Path(temp_dir) / "[Content_Types].xml").write_text(ET.tostring(ct, encoding="unicode", xml_declaration=True))

    rels = ET.Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
    ET.SubElement(rels, "Relationship", Id="rId1", Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", Target="xl/workbook.xml")
    (Path(temp_dir) / "_rels" / ".rels").write_text(ET.tostring(rels, encoding="unicode", xml_declaration=True))

    wb = ET.Element("workbook", xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main")
    sheets = ET.SubElement(wb, "sheets")
    ET.SubElement(sheets, "sheet", attrib={"name": "Sheet1", "sheetId": "1", "r:id": "rId1"})
    (Path(temp_dir) / "xl" / "workbook.xml").write_text(ET.tostring(wb, encoding="unicode", xml_declaration=True))

    wb_rels = ET.Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
    ET.SubElement(wb_rels, "Relationship", Id="rId1", Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet", Target="worksheets/sheet1.xml")
    (Path(temp_dir) / "xl" / "_rels" / "workbook.xml.rels").write_text(ET.tostring(wb_rels, encoding="unicode", xml_declaration=True))

    sheet = ET.Element("worksheet", xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main")
    sheetData = ET.SubElement(sheet, "sheetData")
    row = ET.SubElement(sheetData, "row", r="1")
    cell = ET.SubElement(row, "c", r="A1")
    ET.SubElement(cell, "v").text = "1"
    (Path(temp_dir) / "xl" / "worksheets" / "sheet1.xml").write_text(ET.tostring(sheet, encoding="unicode", xml_declaration=True))

# =============================================================================
# CORE: Compression & Extraction
# =============================================================================

def get_total_size(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    return total

def generate_zip(output, extracted_mb=None, pattern="A", compression=True, password=None,
                 progress_callback=None, legacy_crypto=False, fmt="zip", algo="deflate",
                 source=None):
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
        return {"output": output, "extracted_bytes": target_bytes,
                "compressed_bytes": compressed_size, "ratio": ratio,
                "format": "xz" if not (source and os.path.isdir(source)) else "tar.xz",
                "algo": "lzma"}

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
        return {"output": output, "extracted_bytes": target_bytes,
                "compressed_bytes": compressed_size, "ratio": ratio,
                "format": "zst" if not (source and os.path.isdir(source)) else "tar.zst",
                "algo": "zstd"}

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
        return {"output": output, "extracted_bytes": target_bytes,
                "compressed_bytes": compressed_size, "ratio": ratio,
                "format": fmt, "algo": "deflate"}

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
    return {"output": output, "extracted_bytes": target_bytes,
            "compressed_bytes": compressed_size, "ratio": ratio,
            "format": "zip", "algo": "deflate"}

def extract_archive(archive, password=None, output_dir=None):
    if not os.path.exists(archive):
        raise FileNotFoundError(f"Archive not found: {archive}")
    if output_dir is None:
        output_dir = os.path.splitext(archive)[0] + "_extracted"
    os.makedirs(output_dir, exist_ok=True)

    # ---- XZ ----
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
            raise ValueError(f"Failed to decompress XZ: {e}")
    if archive.lower().endswith(('.tar.xz', '.txz')):
        with tarfile.open(archive, 'r:xz') as tar:
            tar.extractall(output_dir)
        return output_dir

    # ---- Zstd ----
    if archive.lower().endswith(('.zst', '.zstd')):
        if not HAS_ZSTD:
            raise ImportError("zstandard not installed.")
        if archive.lower().endswith(('.tar.zst', '.tzst')):
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
        else:
            base = os.path.basename(archive)
            base = os.path.splitext(base)[0] + ".bin"
            out_path = os.path.join(output_dir, base)
            with open(archive, "rb") as f_in:
                with open(out_path, "wb") as f_out:
                    decompressor = zstd.ZstdDecompressor()
                    f_out.write(decompressor.decompress(f_in.read()))
            return output_dir

    # ---- ZIP ----
    try:
        if HAS_PYZIPPER:
            with pyzipper.AESZipFile(archive, 'r') as z:
                if password:
                    z.setpassword(password.encode())
                z.extractall(output_dir)
                return output_dir
    except:
        pass
    # Fallback
    with zipfile.ZipFile(archive, 'r') as z:
        if password:
            z.setpassword(password.encode())
        z.extractall(output_dir)
        return output_dir

def print_stats(stats):
    print("Created:", stats["output"])
    print("Format:", stats.get("format", "zip").upper())
    print("Algorithm:", stats.get("algo", "deflate").upper())
    print("Compressed size:", format_size(stats["compressed_bytes"]))
    print("Extracted size:", format_size(stats["extracted_bytes"]))
    print("Compression ratio:", f"{stats['ratio']:.2f}x")

# =============================================================================
# CLI
# =============================================================================

def cli_generate(args):
    progress = get_progress_printer(enable=not getattr(args, 'no_progress', False), total=args.size)
    stats = generate_zip(
        output=args.output,
        extracted_mb=args.size,
        pattern=args.pattern,
        compression=not args.store,
        password=args.password,
        progress_callback=progress,
        legacy_crypto=args.legacy,
        fmt=args.format,
        algo=args.algo,
        source=args.input,
    )
    print_stats(stats)
    if args.password and args.legacy:
        print("Note: Used legacy ZipCrypto (Windows native).")
    elif args.password:
        print("Note: Used AES-256 encryption.")

def cli_batch(args):
    tasks = []
    if args.batch_config:
        with open(args.batch_config, 'r') as f:
            data = json.load(f)
            tasks = data if isinstance(data, list) else [data]
    elif args.series:
        sizes = [s.strip() for s in args.series.split(',')]
        base_output = args.output_pattern or "batch_{size}.zip"
        fmt = args.format or "zip"
        algo = args.algo or "deflate"
        for s in sizes:
            size_mb = parse_size_string(s)
            output_name = base_output.replace("{size}", str(s)).replace("{size_mb}", str(size_mb))
            task = {
                "size": size_mb,
                "output": output_name,
                "pattern": args.pattern,
                "compression": not args.store,
                "password": args.password,
                "legacy": args.legacy,
                "format": fmt,
                "algo": algo,
            }
            if args.input:
                task["source"] = args.input
            tasks.append(task)
    if not tasks:
        print("No tasks defined.")
        return
    print(f"Batch: {len(tasks)} tasks")
    def batch_progress(current, total, msg):
        print(f"\rBatch progress: {current+1}/{total} - {msg}", end="")
        if current == total - 1:
            print()
    results = []
    for idx, task in enumerate(tasks):
        batch_progress(idx, len(tasks), f"Task {idx+1}")
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
    print("\n=== Batch Summary ===")
    for r in results:
        print(f"{os.path.basename(r['output'])} ({r['format'].upper()}, {r['algo'].upper()}): {format_size(r['extracted_bytes'])} → {format_size(r['compressed_bytes'])} (ratio {r['ratio']:.2f}x)")

def cli_extract(args):
    try:
        out_dir = extract_archive(args.archive, args.password, args.output_dir)
        print(f"Extracted to: {out_dir}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

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

# =============================================================================
# GUI
# =============================================================================

# Color helpers
def get_colors(dark_mode):
    if dark_mode:
        return {"bg": "#1c1c1c", "fg": "#f0f0f0", "textbg": "#2d2d2d", "textfg": "#f0f0f0", "selectbg": "#3a3a3a"}
    else:
        return {"bg": "#f0f0f0", "fg": "#000000", "textbg": "#ffffff", "textfg": "#000000", "selectbg": "#cce8ff"}

def apply_custom_colors(root_widget, colors):
    stack = [root_widget]
    while stack:
        widget = stack.pop()
        if hasattr(widget, 'config'):
            try:
                widget.config(bg=colors["textbg"], fg=colors["textfg"],
                              insertbackground=colors["fg"], selectbackground=colors["selectbg"])
            except tk.TclError:
                pass
        stack.extend(widget.winfo_children())

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def launch_gui():
    config = load_config()
    dark_mode_pref = config.get("dark_mode", None)
    if dark_mode_pref is None:
        dark_mode = detect_system_theme()
        if dark_mode is None:
            dark_mode = False
    else:
        dark_mode = dark_mode_pref

    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    root.title("Lifeless-Forge – Compression Tool")
    root.geometry("760x720")
    root.resizable(False, False)
    try:
        root.iconbitmap(resource_path("app_icon.ico"))
    except:
        pass

    # Menu
    menubar = tk.Menu(root)
    view_menu = tk.Menu(menubar, tearoff=0)
    dark_mode_var = tk.BooleanVar(value=dark_mode)
    def toggle_dark_mode():
        nonlocal dark_mode
        dark_mode = not dark_mode
        dark_mode_var.set(dark_mode)
        if HAS_SV_TTK:
            sv_ttk.set_theme("dark" if dark_mode else "light")
        colors = get_colors(dark_mode)
        root.configure(bg=colors["bg"])
        apply_custom_colors(root, colors)
        config["dark_mode"] = dark_mode
        save_config(config)
    view_menu.add_checkbutton(label="Dark Mode", variable=dark_mode_var, command=toggle_dark_mode)
    menubar.add_cascade(label="View", menu=view_menu)
    root.config(menu=menubar)

    if HAS_SV_TTK:
        sv_ttk.set_theme("dark" if dark_mode else "light")
    else:
        style = ttk.Style()
        style.theme_use('clam')
    colors = get_colors(dark_mode)
    root.configure(bg=colors["bg"])

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=5, pady=5)

    # ---- Tab 1: Single ----
    tab_single = ttk.Frame(nb)
    nb.add(tab_single, text="Single Generate")
    size_var = tk.IntVar(value=60)
    pattern_var = tk.StringVar(value="A")
    output_var = tk.StringVar(value="compression_demo.zip")
    compress_var = tk.BooleanVar(value=True)
    password_var = tk.StringVar(value="")
    legacy_var = tk.BooleanVar(value=False)
    format_var = tk.StringVar(value="zip")
    algo_var = tk.StringVar(value="deflate")
    input_path_var = tk.StringVar(value="")
    input_is_folder_var = tk.BooleanVar(value=False)

    row = 0
    ttk.Label(tab_single, text="Input (drag & drop or browse):").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    input_entry = ttk.Entry(tab_single, textvariable=input_path_var, width=40)
    input_entry.grid(row=row, column=1, padx=5, pady=5, sticky="ew")
    if HAS_DND:
        input_entry.drop_target_register(DND_FILES)
        input_entry.dnd_bind('<<Drop>>', lambda e: input_path_var.set(e.data.strip('{}').split()[0] if e.data else ''))
    def browse_input():
        if input_is_folder_var.get():
            folder = filedialog.askdirectory()
            if folder: input_path_var.set(folder)
        else:
            file = filedialog.askopenfilename()
            if file: input_path_var.set(file)
    ttk.Button(tab_single, text="Browse", command=browse_input).grid(row=row, column=2, padx=5, pady=5)
    row += 1
    ttk.Checkbutton(tab_single, text="Input is a Folder", variable=input_is_folder_var).grid(row=row, column=1, padx=5, pady=5, sticky="w")
    row += 1

    ttk.Label(tab_single, text="Size (MB, if no input):").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    ttk.Scale(tab_single, from_=1, to=1000, orient="horizontal", variable=size_var).grid(row=row, column=1, padx=5, pady=5, sticky="ew")
    ttk.Label(tab_single, textvariable=size_var).grid(row=row, column=2, padx=5, pady=5)
    row += 1

    ttk.Label(tab_single, text="Pattern (if no input):").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_single, textvariable=pattern_var, width=10).grid(row=row, column=1, padx=5, pady=5, sticky="w")
    row += 1

    ttk.Label(tab_single, text="Format:").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    format_combo = ttk.Combobox(tab_single, textvariable=format_var, values=["zip", "pptx", "docx", "xlsx"], state="readonly")
    format_combo.grid(row=row, column=1, padx=5, pady=5, sticky="w")
    row += 1

    ttk.Label(tab_single, text="Algorithm:").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    algo_combo = ttk.Combobox(tab_single, textvariable=algo_var, values=["deflate", "lzma", "zstd"], state="readonly")
    algo_combo.set("deflate")
    algo_combo.grid(row=row, column=1, padx=5, pady=5, sticky="w")
    row += 1

    ttk.Label(tab_single, text="Output:").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_single, textvariable=output_var, width=30).grid(row=row, column=1, padx=5, pady=5, sticky="ew")
    ttk.Button(tab_single, text="Browse", command=lambda: output_var.set(filedialog.asksaveasfilename(defaultextension="."+format_var.get()))).grid(row=row, column=2, padx=5, pady=5)
    row += 1

    compress_check = ttk.Checkbutton(tab_single, text="Use ZIP compression (Store vs DEFLATE)", variable=compress_var)
    compress_check.grid(row=row, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    row += 1

    def on_algo_change(event):
        if algo_var.get() in ("lzma", "zstd"):
            compress_check.config(state="disabled")
            compress_var.set(True)
        else:
            compress_check.config(state="normal")
    algo_combo.bind("<<ComboboxSelected>>", on_algo_change)
    on_algo_change(None)

    ttk.Label(tab_single, text="Password (ZIP only):").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_single, textvariable=password_var, show="*", width=20).grid(row=row, column=1, padx=5, pady=5, sticky="w")
    row += 1

    ttk.Checkbutton(tab_single, text="Legacy ZipCrypto (Windows native)", variable=legacy_var).grid(row=row, column=0, columnspan=3, padx=5, pady=5, sticky="w")
    row += 1

    log_single = tk.Text(tab_single, height=8, state="disabled", wrap="word")
    log_single.grid(row=row, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
    row += 1

    progress_single = ttk.Progressbar(tab_single, orient="horizontal", length=400, mode="determinate")
    progress_single.grid(row=row, column=0, columnspan=3, padx=5, pady=5)
    row += 1

    def log_single_msg(msg):
        log_single.config(state="normal")
        log_single.insert("end", msg + "\n")
        log_single.see("end")
        log_single.config(state="disabled")

    def generate_single_thread():
        gen_btn.config(state="disabled")
        progress_single["value"] = 0
        log_single_msg("Starting generation...")
        try:
            source = input_path_var.get().strip()
            if source and os.path.exists(source):
                log_single_msg(f"Using input: {source}")
                size_mb = None
            else:
                source = None
                size_mb = size_var.get()
                log_single_msg(f"Generating pattern ({size_mb} MB)")
            def upd(cur, total):
                if total:
                    progress_single["value"] = (cur/total)*100
                root.update_idletasks()
            stats = generate_zip(
                output=output_var.get(),
                extracted_mb=size_mb,
                pattern=pattern_var.get(),
                compression=compress_var.get(),
                password=password_var.get() or None,
                progress_callback=upd,
                legacy_crypto=legacy_var.get(),
                fmt=format_var.get(),
                algo=algo_var.get(),
                source=source,
            )
            log_single_msg(f"Created: {stats['output']} ({stats['format'].upper()})")
            log_single_msg(f"Algorithm: {stats['algo'].upper()}")
            log_single_msg(f"Compressed: {format_size(stats['compressed_bytes'])}")
            log_single_msg(f"Extracted:  {format_size(stats['extracted_bytes'])}")
            log_single_msg(f"Ratio: {stats['ratio']:.2f}x")
        except Exception as e:
            log_single_msg(f"Error: {e}")
        finally:
            gen_btn.config(state="normal")
            progress_single["value"] = 0

    gen_btn = ttk.Button(tab_single, text="Generate", command=lambda: threading.Thread(target=generate_single_thread, daemon=True).start())
    gen_btn.grid(row=row, column=0, columnspan=3, pady=10)

    tab_single.grid_columnconfigure(1, weight=1)
    tab_single.grid_rowconfigure(row-2, weight=1)

    # ---- Tab 2: Batch ----
    tab_batch = ttk.Frame(nb)
    nb.add(tab_batch, text="Batch Generate")
    batch_sizes_var = tk.StringVar(value="10, 50, 100, 500")
    batch_pattern_var = tk.StringVar(value="A")
    batch_format_var = tk.StringVar(value="zip")
    batch_algo_var = tk.StringVar(value="deflate")
    batch_output_pattern_var = tk.StringVar(value="batch_{size}.zip")
    batch_compress_var = tk.BooleanVar(value=True)
    batch_password_var = tk.StringVar(value="")
    batch_legacy_var = tk.BooleanVar(value=False)
    batch_input_path_var = tk.StringVar(value="")
    batch_input_is_folder_var = tk.BooleanVar(value=False)

    br=0
    ttk.Label(tab_batch, text="Input (drag & drop or browse, optional):").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    batch_input_entry = ttk.Entry(tab_batch, textvariable=batch_input_path_var, width=40)
    batch_input_entry.grid(row=br, column=1, padx=5, pady=5, sticky="ew")
    if HAS_DND:
        batch_input_entry.drop_target_register(DND_FILES)
        batch_input_entry.dnd_bind('<<Drop>>', lambda e: batch_input_path_var.set(e.data.strip('{}').split()[0] if e.data else ''))
    def batch_browse_input():
        if batch_input_is_folder_var.get():
            folder = filedialog.askdirectory()
            if folder: batch_input_path_var.set(folder)
        else:
            file = filedialog.askopenfilename()
            if file: batch_input_path_var.set(file)
    ttk.Button(tab_batch, text="Browse", command=batch_browse_input).grid(row=br, column=2, padx=5, pady=5)
    br += 1
    ttk.Checkbutton(tab_batch, text="Input is a Folder", variable=batch_input_is_folder_var).grid(row=br, column=1, padx=5, pady=5, sticky="w")
    br += 1

    ttk.Label(tab_batch, text="Sizes (comma-separated, ignored if input set):").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_batch, textvariable=batch_sizes_var, width=30).grid(row=br, column=1, padx=5, pady=5, sticky="ew")
    br += 1

    ttk.Label(tab_batch, text="Pattern (if no input):").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_batch, textvariable=batch_pattern_var, width=10).grid(row=br, column=1, padx=5, pady=5, sticky="w")
    br += 1

    ttk.Label(tab_batch, text="Format:").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    ttk.Combobox(tab_batch, textvariable=batch_format_var, values=["zip", "pptx", "docx", "xlsx"], state="readonly").grid(row=br, column=1, padx=5, pady=5, sticky="w")
    br += 1

    ttk.Label(tab_batch, text="Algorithm:").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    batch_algo_combo = ttk.Combobox(tab_batch, textvariable=batch_algo_var, values=["deflate", "lzma", "zstd"], state="readonly")
    batch_algo_combo.set("deflate")
    batch_algo_combo.grid(row=br, column=1, padx=5, pady=5, sticky="w")
    br += 1

    ttk.Label(tab_batch, text="Output pattern:").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_batch, textvariable=batch_output_pattern_var, width=30).grid(row=br, column=1, padx=5, pady=5, sticky="ew")
    br += 1

    batch_compress_check = ttk.Checkbutton(tab_batch, text="Use ZIP compression (Store vs DEFLATE)", variable=batch_compress_var)
    batch_compress_check.grid(row=br, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    br += 1

    def on_batch_algo_change(event):
        if batch_algo_var.get() in ("lzma", "zstd"):
            batch_compress_check.config(state="disabled")
            batch_compress_var.set(True)
        else:
            batch_compress_check.config(state="normal")
    batch_algo_combo.bind("<<ComboboxSelected>>", on_batch_algo_change)
    on_batch_algo_change(None)

    ttk.Label(tab_batch, text="Password (ZIP only):").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_batch, textvariable=batch_password_var, show="*", width=20).grid(row=br, column=1, padx=5, pady=5, sticky="w")
    br += 1

    ttk.Checkbutton(tab_batch, text="Legacy ZipCrypto", variable=batch_legacy_var).grid(row=br, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    br += 1

    batch_log = tk.Text(tab_batch, height=8, state="disabled", wrap="word")
    batch_log.grid(row=br, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
    br += 1

    batch_progress_bar = ttk.Progressbar(tab_batch, orient="horizontal", length=400, mode="determinate")
    batch_progress_bar.grid(row=br, column=0, columnspan=2, padx=5, pady=5)
    br += 1

    def log_batch_msg(msg):
        batch_log.config(state="normal")
        batch_log.insert("end", msg + "\n")
        batch_log.see("end")
        batch_log.config(state="disabled")

    def generate_batch_thread():
        batch_btn.config(state="disabled")
        batch_progress_bar["value"] = 0
        log_batch_msg("Starting batch generation...")
        try:
            size_strs = [s.strip() for s in batch_sizes_var.get().split(',') if s.strip()]
            tasks = []
            fmt = batch_format_var.get()
            algo = batch_algo_var.get()
            source = batch_input_path_var.get().strip()
            if source and not os.path.exists(source):
                raise ValueError(f"Input source not found: {source}")
            for s in size_strs:
                size_mb = parse_size_string(s)
                out_name = batch_output_pattern_var.get().replace("{size}", s).replace("{size_mb}", str(size_mb))
                task = {
                    "size": size_mb,
                    "output": out_name,
                    "pattern": batch_pattern_var.get(),
                    "compression": batch_compress_var.get(),
                    "password": batch_password_var.get() or None,
                    "legacy": batch_legacy_var.get(),
                    "format": fmt,
                    "algo": algo,
                }
                if source:
                    task["source"] = source
                tasks.append(task)
            if not tasks:
                log_batch_msg("No tasks defined.")
                return
            log_batch_msg(f"Total tasks: {len(tasks)}")
            def batch_progress(current, total, msg):
                batch_progress_bar["value"] = ((current+1) / total) * 100
                root.update_idletasks()
                log_batch_msg(f"[{current+1}/{total}] {msg}")
            # We'll re-use the batch logic from core
            results = []
            for idx, task in enumerate(tasks):
                batch_progress(idx, len(tasks), f"Task {idx+1}")
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
            log_batch_msg("\n=== Summary ===")
            for r in results:
                log_batch_msg(f"{os.path.basename(r['output'])} ({r['format'].upper()}, {r['algo'].upper()}): {format_size(r['extracted_bytes'])} → {format_size(r['compressed_bytes'])} (ratio {r['ratio']:.2f}x)")
        except Exception as e:
            log_batch_msg(f"Error: {e}")
        finally:
            batch_btn.config(state="normal")
            batch_progress_bar["value"] = 0

    batch_btn = ttk.Button(tab_batch, text="Generate Batch", command=lambda: threading.Thread(target=generate_batch_thread, daemon=True).start())
    batch_btn.grid(row=br, column=0, columnspan=2, pady=10)

    tab_batch.grid_columnconfigure(1, weight=1)
    tab_batch.grid_rowconfigure(br-2, weight=1)

    # ---- Tab 3: Extract / Info ----
    tab_extra = ttk.Frame(nb)
    nb.add(tab_extra, text="Extract / Info")

    def do_extract():
        archive = filedialog.askopenfilename(title="Select archive",
            filetypes=[("All archives", "*.zip *.xz *.lzma *.tar.xz *.txz *.zst *.zstd *.tar.zst *.tzst *.pptx *.docx *.xlsx"),
                       ("ZIP", "*.zip"), ("XZ", "*.xz"), ("Zstd", "*.zst"), ("TAR.XZ", "*.tar.xz"), ("TAR.ZST", "*.tar.zst")])
        if not archive: return
        if archive.lower().endswith(('.zip', '.pptx', '.docx', '.xlsx')):
            pwd = simpledialog.askstring("Password", "Enter password (if needed):", show='*')
            if pwd is None: return
        else:
            pwd = None
        try:
            out = extract_archive(archive, pwd)
            messagebox.showinfo("Success", f"Extracted to: {out}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def do_info():
        archive = filedialog.askopenfilename(title="Select archive",
            filetypes=[("All archives", "*.zip *.pptx *.docx *.xlsx *.xz *.lzma *.tar.xz *.txz *.zst *.zstd *.tar.zst *.tzst")])
        if not archive: return
        try:
            if archive.lower().endswith(('.xz', '.lzma', '.zst', '.zstd', '.tar.xz', '.txz', '.tar.zst', '.tzst')):
                size = os.path.getsize(archive)
                msg = f"Archive: {os.path.basename(archive)}\nType: LZMA or Zstd\nCompressed size: {format_size(size)}"
                messagebox.showinfo("Archive Info", msg)
                return
            with zipfile.ZipFile(archive, 'r') as z:
                info = z.infolist()
                total_compressed = sum(f.compress_size for f in info)
                total_extracted = sum(f.file_size for f in info)
                ratio = total_extracted / total_compressed if total_compressed else 0
                msg = (f"Archive: {os.path.basename(archive)}\n"
                       f"Files: {len(info)}\n"
                       f"Compressed: {format_size(total_compressed)}\n"
                       f"Extracted:  {format_size(total_extracted)}\n"
                       f"Ratio: {ratio:.2f}x")
                messagebox.showinfo("Archive Info", msg)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    ttk.Button(tab_extra, text="Extract Archive", command=do_extract).pack(pady=10)
    ttk.Button(tab_extra, text="Show Info", command=do_info).pack(pady=10)

    apply_custom_colors(root, get_colors(dark_mode))
    root.mainloop()

# =============================================================================
# MAIN ENTRY
# =============================================================================

def main():
    import argparse
    if len(sys.argv) == 1:
        launch_gui()
        return
    if "--gui" in sys.argv:
        launch_gui()
        return
    parser = argparse.ArgumentParser(description="Lifeless-Forge – Compression Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate
    gen = subparsers.add_parser("generate")
    gen.add_argument("-s", "--size", type=int, default=60)
    gen.add_argument("-i", "--input", help="Input file/folder")
    gen.add_argument("-o", "--output", default="compression_demo.zip")
    gen.add_argument("-p", "--pattern", default="A")
    gen.add_argument("--format", choices=["zip", "pptx", "docx", "xlsx"], default="zip")
    gen.add_argument("--algo", choices=["deflate", "lzma", "zstd"], default="deflate")
    gen.add_argument("--store", action="store_true")
    gen.add_argument("--password")
    gen.add_argument("--legacy", action="store_true")
    gen.add_argument("--no-progress", action="store_true")
    gen.set_defaults(func=cli_generate)

    # batch
    batch = subparsers.add_parser("batch")
    batch.add_argument("--series")
    batch.add_argument("--batch-config")
    batch.add_argument("-i", "--input")
    batch.add_argument("-o", "--output-pattern")
    batch.add_argument("-p", "--pattern", default="A")
    batch.add_argument("--format", choices=["zip", "pptx", "docx", "xlsx"], default="zip")
    batch.add_argument("--algo", choices=["deflate", "lzma", "zstd"], default="deflate")
    batch.add_argument("--store", action="store_true")
    batch.add_argument("--password")
    batch.add_argument("--legacy", action="store_true")
    batch.set_defaults(func=cli_batch)

    # extract
    ext = subparsers.add_parser("extract")
    ext.add_argument("archive")
    ext.add_argument("-p", "--password")
    ext.add_argument("-o", "--output-dir")
    ext.set_defaults(func=cli_extract)

    # info
    info = subparsers.add_parser("info")
    info.add_argument("zipfile")
    info.set_defaults(func=cli_info)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
