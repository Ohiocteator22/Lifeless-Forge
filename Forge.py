#!/usr/bin/env python3
"""
dec.py – ZIP compression demonstrator with CLI & GUI
Supports single/batch generation, extraction, info, and Office formats (PPTX, DOCX, XLSX).
"""

import zipfile
import os
import argparse
import tempfile
import sys
import json
import threading
import re
import io
from pathlib import Path
import xml.etree.ElementTree as ET

# =============================================================================
# Utilities
# =============================================================================

def format_size(size):
    units = ["B", "KB", "MB", "GB"]
    for unit in units:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


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


def parse_size_string(s):
    s = str(s).strip().upper()
    match = re.match(r"([\d.]+)\s*(?:([KMGT])B?)?", s)
    if not match:
        raise ValueError(f"Invalid size format: {s}")
    val = float(match.group(1))
    unit = match.group(2) or "M"
    multipliers = {"K": 1/1024, "M": 1, "G": 1024, "T": 1024*1024}
    return int(val * multipliers.get(unit, 1))


# =============================================================================
# Office template builders (FIXED)
# =============================================================================

def create_pptx_template(temp_dir, dummy_filename="media/dummy.bin"):
    """Create a minimal PPTX structure with a dummy file."""
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

    # Fixed namespace declarations using attrib dict
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

    return temp_dir


def create_docx_template(temp_dir, dummy_filename="word/media/dummy.bin"):
    """Minimal DOCX structure."""
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

    return temp_dir


def create_xlsx_template(temp_dir, dummy_filename="xl/media/dummy.bin"):
    """Minimal XLSX structure."""
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
    # FIX: use attrib dict for 'r:id'
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

    return temp_dir


# =============================================================================
# Core generation
# =============================================================================

def generate_zip(output, extracted_mb, pattern="A", compression=True, password=None,
                 progress_callback=None, legacy_crypto=False, fmt="zip"):
    target_bytes = extracted_mb * 1024 * 1024
    chunk = (pattern * (1024 * 1024)).encode()

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
        "format": fmt,
    }


def print_stats(stats):
    print("Created:", stats["output"])
    print("Format:", stats.get("format", "zip").upper())
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
        )
        results.append(stats)
    return results


# =============================================================================
# Extraction and info
# =============================================================================

def extract_zip(archive, password, output_dir=None):
    if not os.path.exists(archive):
        raise FileNotFoundError(f"Archive not found: {archive}")
    if output_dir is None:
        output_dir = os.path.splitext(archive)[0] + "_extracted"
    os.makedirs(output_dir, exist_ok=True)

    try:
        import pyzipper
        with pyzipper.AESZipFile(archive, 'r') as z:
            try:
                z.setpassword(password.encode())
                z.extractall(output_dir)
                return output_dir
            except RuntimeError as e:
                if "Bad password" in str(e) or "invalid password" in str(e).lower():
                    raise ValueError("Incorrect password")
                raise
    except (ImportError, zipfile.BadZipFile):
        with zipfile.ZipFile(archive, 'r') as z:
            z.setpassword(password.encode())
            z.extractall(output_dir)
            return output_dir
    except Exception:
        with zipfile.ZipFile(archive, 'r') as z:
            z.setpassword(password.encode())
            z.extractall(output_dir)
            return output_dir


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


# =============================================================================
# CLI
# =============================================================================

def cli_generate(args):
    progress = get_progress_printer(enable=not args.no_progress, total=args.size)
    stats = generate_zip(
        output=args.output,
        extracted_mb=args.size,
        pattern=args.pattern,
        compression=not args.store,
        password=args.password,
        progress_callback=progress,
        legacy_crypto=args.legacy,
        fmt=args.format,
    )
    print_stats(stats)
    if args.password and args.legacy:
        print("Note: Used legacy ZipCrypto (Windows native).")
    elif args.password:
        print("Note: Used AES-256 encryption (use 7-Zip or 'extract' command).")


def cli_batch(args):
    tasks = []
    if args.batch_config:
        with open(args.batch_config, 'r') as f:
            data = json.load(f)
            if isinstance(data, list):
                tasks = data
            else:
                tasks = [data]
    elif args.series:
        sizes = [s.strip() for s in args.series.split(',')]
        base_output = args.output_pattern or "batch_{size}.zip"
        fmt = args.format or "zip"
        for s in sizes:
            size_mb = parse_size_string(s)
            output_name = base_output.replace("{size}", str(s)).replace("{size_mb}", str(size_mb))
            tasks.append({
                "size": size_mb,
                "output": output_name,
                "pattern": args.pattern,
                "compression": not args.store,
                "password": args.password,
                "legacy": args.legacy,
                "format": fmt,
            })
    if not tasks:
        print("No tasks defined. Use --series or --batch-config.")
        return

    print(f"Batch: {len(tasks)} tasks")
    def batch_progress(current, total, msg):
        print(f"\rBatch progress: {current+1}/{total} - {msg}", end="")
        if current == total - 1:
            print()

    results = generate_batch(tasks, progress_callback=batch_progress)

    print("\n=== Batch Summary ===")
    for r in results:
        print(f"{os.path.basename(r['output'])} ({r.get('format','zip').upper()}): {format_size(r['extracted_bytes'])} → {format_size(r['compressed_bytes'])} (ratio {r['ratio']:.2f}x)")


def cli_extract(args):
    try:
        out_dir = extract_zip(args.archive, args.password, args.output_dir)
        print(f"Extracted to: {out_dir}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def setup_cli_parser():
    parser = argparse.ArgumentParser(description="ZIP compression demonstrator")
    subparsers = parser.add_subparsers(dest="command", required=True, help="Subcommands")

    gen = subparsers.add_parser("generate", help="Generate a single archive")
    gen.add_argument("-s", "--size", type=int, default=60, help="Extracted size in MB")
    gen.add_argument("-o", "--output", default="compression_demo.zip", help="Output filename")
    gen.add_argument("-p", "--pattern", default="A", help="Character pattern")
    gen.add_argument("--format", choices=["zip", "pptx", "docx", "xlsx"], default="zip", help="Output format")
    gen.add_argument("--store", action="store_true", help="Use no compression")
    gen.add_argument("--password", help="Password for encryption")
    gen.add_argument("--legacy", action="store_true", help="Use legacy ZipCrypto")
    gen.add_argument("--no-progress", action="store_true", help="Disable progress bar")
    gen.set_defaults(func=cli_generate)

    batch = subparsers.add_parser("batch", help="Generate multiple archives")
    batch.add_argument("--series", help="Comma-separated sizes")
    batch.add_argument("--batch-config", help="JSON file with task list")
    batch.add_argument("-o", "--output-pattern", help="Pattern with {size} placeholder")
    batch.add_argument("-p", "--pattern", default="A", help="Character pattern (for --series)")
    batch.add_argument("--format", choices=["zip", "pptx", "docx", "xlsx"], default="zip", help="Format (for --series)")
    batch.add_argument("--store", action="store_true", help="No compression (for --series)")
    batch.add_argument("--password", help="Password (for --series)")
    batch.add_argument("--legacy", action="store_true", help="Legacy encryption (for --series)")
    batch.set_defaults(func=cli_batch)

    ext = subparsers.add_parser("extract", help="Extract a password-protected archive")
    ext.add_argument("archive", help="Path to archive")
    ext.add_argument("-p", "--password", required=True, help="Password")
    ext.add_argument("-o", "--output-dir", help="Output directory")
    ext.set_defaults(func=cli_extract)

    info = subparsers.add_parser("info", help="Show archive stats")
    info.add_argument("zipfile", help="Path to archive")
    info.set_defaults(func=cli_info)

    return parser


# =============================================================================
# GUI
# =============================================================================

def launch_gui():
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox, simpledialog
    except ImportError:
        print("Tkinter not available. Install python3-tk or use CLI.")
        sys.exit(1)

    root = tk.Tk()
    root.title("ZIP Compression Demonstrator")
    root.geometry("700x650")
    root.resizable(False, False)

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

    row=0
    ttk.Label(tab_single, text="Size (MB):").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    ttk.Scale(tab_single, from_=1, to=1000, orient="horizontal", variable=size_var).grid(row=row, column=1, padx=5, pady=5, sticky="ew")
    ttk.Label(tab_single, textvariable=size_var).grid(row=row, column=2, padx=5, pady=5)
    row+=1

    ttk.Label(tab_single, text="Pattern:").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_single, textvariable=pattern_var, width=10).grid(row=row, column=1, padx=5, pady=5, sticky="w")
    row+=1

    ttk.Label(tab_single, text="Format:").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    format_combo = ttk.Combobox(tab_single, textvariable=format_var, values=["zip", "pptx", "docx", "xlsx"], state="readonly")
    format_combo.grid(row=row, column=1, padx=5, pady=5, sticky="w")
    row+=1

    ttk.Label(tab_single, text="Output:").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_single, textvariable=output_var, width=30).grid(row=row, column=1, padx=5, pady=5, sticky="ew")
    ttk.Button(tab_single, text="Browse", command=lambda: output_var.set(filedialog.asksaveasfilename(defaultextension="."+format_var.get()))).grid(row=row, column=2, padx=5, pady=5)
    row+=1

    ttk.Checkbutton(tab_single, text="Use DEFLATE compression", variable=compress_var).grid(row=row, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    row+=1

    ttk.Label(tab_single, text="Password:").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_single, textvariable=password_var, show="*", width=20).grid(row=row, column=1, padx=5, pady=5, sticky="w")
    row+=1

    ttk.Checkbutton(tab_single, text="Legacy ZipCrypto (Windows native)", variable=legacy_var).grid(row=row, column=0, columnspan=3, padx=5, pady=5, sticky="w")
    row+=1

    log_single = tk.Text(tab_single, height=8, state="disabled", wrap="word")
    log_single.grid(row=row, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
    row+=1

    progress_single = ttk.Progressbar(tab_single, orient="horizontal", length=400, mode="determinate")
    progress_single.grid(row=row, column=0, columnspan=3, padx=5, pady=5)
    row+=1

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
            def upd(cur, total):
                progress_single["value"] = (cur/total)*100
                root.update_idletasks()
            stats = generate_zip(
                output=output_var.get(),
                extracted_mb=size_var.get(),
                pattern=pattern_var.get(),
                compression=compress_var.get(),
                password=password_var.get() or None,
                progress_callback=upd,
                legacy_crypto=legacy_var.get(),
                fmt=format_var.get(),
            )
            log_single_msg(f"Created: {stats['output']} ({stats['format'].upper()})")
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
    batch_output_pattern_var = tk.StringVar(value="batch_{size}.zip")
    batch_compress_var = tk.BooleanVar(value=True)
    batch_password_var = tk.StringVar(value="")
    batch_legacy_var = tk.BooleanVar(value=False)

    br=0
    ttk.Label(tab_batch, text="Sizes (comma-separated):").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_batch, textvariable=batch_sizes_var, width=30).grid(row=br, column=1, padx=5, pady=5, sticky="ew")
    br+=1

    ttk.Label(tab_batch, text="Pattern:").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_batch, textvariable=batch_pattern_var, width=10).grid(row=br, column=1, padx=5, pady=5, sticky="w")
    br+=1

    ttk.Label(tab_batch, text="Format:").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    ttk.Combobox(tab_batch, textvariable=batch_format_var, values=["zip", "pptx", "docx", "xlsx"], state="readonly").grid(row=br, column=1, padx=5, pady=5, sticky="w")
    br+=1

    ttk.Label(tab_batch, text="Output pattern:").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_batch, textvariable=batch_output_pattern_var, width=30).grid(row=br, column=1, padx=5, pady=5, sticky="ew")
    br+=1

    ttk.Checkbutton(tab_batch, text="Use DEFLATE compression", variable=batch_compress_var).grid(row=br, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    br+=1

    ttk.Label(tab_batch, text="Password:").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_batch, textvariable=batch_password_var, show="*", width=20).grid(row=br, column=1, padx=5, pady=5, sticky="w")
    br+=1

    ttk.Checkbutton(tab_batch, text="Legacy ZipCrypto", variable=batch_legacy_var).grid(row=br, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    br+=1

    batch_log = tk.Text(tab_batch, height=8, state="disabled", wrap="word")
    batch_log.grid(row=br, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
    br+=1

    batch_progress_bar = ttk.Progressbar(tab_batch, orient="horizontal", length=400, mode="determinate")
    batch_progress_bar.grid(row=br, column=0, columnspan=2, padx=5, pady=5)
    br+=1

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
            for s in size_strs:
                size_mb = parse_size_string(s)
                out_name = batch_output_pattern_var.get().replace("{size}", s).replace("{size_mb}", str(size_mb))
                tasks.append({
                    "size": size_mb,
                    "output": out_name,
                    "pattern": batch_pattern_var.get(),
                    "compression": batch_compress_var.get(),
                    "password": batch_password_var.get() or None,
                    "legacy": batch_legacy_var.get(),
                    "format": fmt,
                })
            if not tasks:
                log_batch_msg("No tasks defined.")
                return
            log_batch_msg(f"Total tasks: {len(tasks)}")
            def batch_progress(current, total, msg):
                batch_progress_bar["value"] = ((current+1) / total) * 100
                root.update_idletasks()
                log_batch_msg(f"[{current+1}/{total}] {msg}")
            results = generate_batch(tasks, progress_callback=batch_progress)
            log_batch_msg("\n=== Summary ===")
            for r in results:
                log_batch_msg(f"{os.path.basename(r['output'])} ({r['format'].upper()}): {format_size(r['extracted_bytes'])} → {format_size(r['compressed_bytes'])} (ratio {r['ratio']:.2f}x)")
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
        archive = filedialog.askopenfilename(title="Select archive", filetypes=[("All archives", "*.zip *.pptx *.docx *.xlsx"), ("ZIP", "*.zip"), ("PPTX", "*.pptx"), ("DOCX", "*.docx"), ("XLSX", "*.xlsx")])
        if not archive: return
        pwd = simpledialog.askstring("Password", "Enter password:", show='*')
        if pwd is None: return
        try:
            out = extract_zip(archive, pwd)
            messagebox.showinfo("Success", f"Extracted to: {out}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def do_info():
        archive = filedialog.askopenfilename(title="Select archive", filetypes=[("All archives", "*.zip *.pptx *.docx *.xlsx")])
        if not archive: return
        try:
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

    root.mainloop()


# =============================================================================
# Main
# =============================================================================

def main():
    # If no arguments at all, launch GUI
    if len(sys.argv) == 1:
        launch_gui()
        return

    # If --gui is present, launch GUI (even if other args exist)
    if "--gui" in sys.argv:
        launch_gui()
        return

    parser = setup_cli_parser()
    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()