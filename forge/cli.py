# forge/cli.py
import argparse
import sys
import json
import os
import tempfile
import shutil
import time
from forge.core import generate_zip, generate_batch, extract_archive, print_stats, cli_info as core_info
from forge.utils import format_size, parse_size_string, get_progress_printer, format_time, normalize_format, normalize_algorithm

# ----------------------------------------------------------------------
# Validate CLI arguments for compatibility
# ----------------------------------------------------------------------

def validate_generate_args(args):
    """Raise ValueError if incompatible arguments are used."""
    # Encryption requires ZIP-based format
    if args.password and args.algo in ("lzma", "zstd"):
        raise ValueError("Encryption is not supported for LZMA or Zstandard compression.")
    # Office formats only work with DEFLATE
    if args.format in ("pptx", "docx", "xlsx") and args.algo != "deflate":
        raise ValueError(f"Office format '{args.format}' only supports DEFLATE compression.")
    # Store mode only valid with ZIP and DEFLATE
    if args.store and (args.format != "zip" or args.algo != "deflate"):
        raise ValueError("--store (no compression) is only valid with format=zip and algo=deflate.")
    # Legacy crypto only with ZIP
    if args.legacy and args.format != "zip":
        raise ValueError("--legacy (ZipCrypto) is only valid with format=zip.")
    # If source is provided, size is ignored – warn but not error
    if args.input and args.size is not None:
        # We can warn, but not error; it's harmless
        pass

def validate_batch_args(args):
    """Validate batch arguments."""
    if args.password and args.algo in ("lzma", "zstd"):
        raise ValueError("Encryption is not supported for LZMA or Zstandard compression in batch.")
    if args.format in ("pptx", "docx", "xlsx") and args.algo != "deflate":
        raise ValueError(f"Office format '{args.format}' only supports DEFLATE compression.")
    if args.store and (args.format != "zip" or args.algo != "deflate"):
        raise ValueError("--store is only valid with format=zip and algo=deflate in batch.")
    if args.legacy and args.format != "zip":
        raise ValueError("--legacy is only valid with format=zip in batch.")

def validate_compress_args(args):
    """Validate compress command arguments."""
    if args.password and args.algo in ("lzma", "zstd"):
        raise ValueError("Encryption is not supported for LZMA or Zstandard compression.")
    if args.store and args.algo != "deflate":
        raise ValueError("--store is only valid with algo=deflate.")
    if args.legacy and args.algo != "deflate":
        raise ValueError("--legacy is only valid with algo=deflate.")

# ----------------------------------------------------------------------
# CLI handler functions
# ----------------------------------------------------------------------

def cli_generate(args):
    # Normalize values
    args.format = normalize_format(args.format)
    args.algo = normalize_algorithm(args.algo)
    # Validate
    validate_generate_args(args)

    progress = get_progress_printer(enable=not args.no_progress, total=args.size)
    try:
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
            source=getattr(args, 'input', None),
        )
        print_stats(stats)
        if args.password:
            if args.legacy:
                print("Note: Used legacy ZipCrypto (Windows native).")
            else:
                print("Note: Used AES-256 encryption.")
    except (ValueError, ImportError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def cli_batch(args):
    # Normalize values
    args.format = normalize_format(args.format)
    args.algo = normalize_algorithm(args.algo)
    validate_batch_args(args)

    tasks = []
    if args.batch_config:
        try:
            with open(args.batch_config, 'r') as f:
                data = json.load(f)
                tasks = data if isinstance(data, list) else [data]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error reading batch config: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.series:
        sizes = [s.strip() for s in args.series.split(',') if s.strip()]
        base_output = args.output_pattern or "batch_{size}.zip"
        fmt = args.format or "zip"
        algo = args.algo or "deflate"
        for s in sizes:
            try:
                size_mb = parse_size_string(s)
            except ValueError as e:
                print(f"Error parsing size '{s}': {e}", file=sys.stderr)
                sys.exit(1)
            output_name = base_output.replace("{size}", s).replace("{size_mb}", str(size_mb))
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
    else:
        print("No tasks defined. Use --series or --batch-config.", file=sys.stderr)
        sys.exit(1)

    if not tasks:
        print("No tasks defined.", file=sys.stderr)
        sys.exit(1)

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
        if isinstance(params["size"], str):
            try:
                params["size"] = parse_size_string(params["size"])
            except ValueError as e:
                print(f"Error parsing size in task {idx+1}: {e}", file=sys.stderr)
                sys.exit(1)

        try:
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
        except Exception as e:
            print(f"\nError in task {idx+1}: {e}", file=sys.stderr)
            sys.exit(1)

    print("\n=== Batch Summary ===")
    for r in results:
        print(f"{os.path.basename(r['output'])} ({r['format'].upper()}, {r['algo'].upper()}): {format_size(r['extracted_bytes'])} → {format_size(r['compressed_bytes'])} (ratio {r['ratio']:.2f}x)")

def cli_extract(args):
    start = time.time()
    try:
        out_dir = extract_archive(args.archive, args.password, args.output_dir)
        elapsed = time.time() - start
        print(f"Extracted to: {out_dir}")
        print("-" * 40)
        print(f"Time taken: {format_time(elapsed)}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def cli_compress(args):
    # Normalize
    args.algo = normalize_algorithm(args.algo)
    validate_compress_args(args)

    sources = args.input
    output = args.output

    if len(sources) == 1 and os.path.isdir(sources[0]):
        source = sources[0]
        try:
            stats = generate_zip(
                output=output,
                extracted_mb=None,
                pattern="",
                compression=not args.store,
                password=args.password,
                progress_callback=None,
                legacy_crypto=args.legacy,
                fmt="zip",  # always ZIP for compress command
                algo=args.algo,
                source=source,
            )
            print_stats(stats)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        for src in sources:
            if not os.path.exists(src):
                print(f"Warning: {src} not found, skipping.", file=sys.stderr)
                continue
            dest = os.path.join(tmpdir, os.path.basename(src))
            if os.path.isdir(src):
                shutil.copytree(src, dest)
            else:
                shutil.copy2(src, dest)
        try:
            stats = generate_zip(
                output=output,
                extracted_mb=None,
                pattern="",
                compression=not args.store,
                password=args.password,
                progress_callback=None,
                legacy_crypto=args.legacy,
                fmt="zip",
                algo=args.algo,
                source=tmpdir,
            )
            print_stats(stats)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

# ----------------------------------------------------------------------
# Parser setup
# ----------------------------------------------------------------------

def setup_cli_parser():
    parser = argparse.ArgumentParser(
        description="Lifeless-Forge – Compression Tool",
        epilog="Use -h for more details on each subcommand."
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command to execute")

    # Generate
    gen = subparsers.add_parser("generate", help="Generate a single archive (pattern or single input)")
    gen.add_argument("-s", "--size", type=int, default=60,
                     help="Extracted size in MB (ignored if --input is used)")
    gen.add_argument("-i", "--input", help="Input file or folder to compress (overrides pattern)")
    gen.add_argument("-o", "--output", default="compression_demo.zip",
                     help="Output filename (extension may be adjusted based on format/algo)")
    gen.add_argument("-p", "--pattern", default="A",
                     help="Character pattern (used only if no --input)")
    gen.add_argument("--format", choices=["zip", "pptx", "docx", "xlsx"], default="zip",
                     help="Output format (ZIP or Office document)")
    gen.add_argument("--algo", choices=["deflate", "lzma", "zstd"], default="deflate",
                     help="Compression algorithm: deflate (ZIP), lzma (XZ), zstd (Zstandard)")
    gen.add_argument("--store", action="store_true",
                     help="Disable compression (store only – ZIP format only)")
    gen.add_argument("--password", help="Encryption password (ZIP only)")
    gen.add_argument("--legacy", action="store_true",
                     help="Use legacy ZipCrypto (Windows native) instead of AES-256")
    gen.add_argument("--no-progress", action="store_true",
                     help="Disable progress bar")
    gen.set_defaults(func=cli_generate)

    # Batch
    batch = subparsers.add_parser("batch", help="Generate multiple archives")
    batch.add_argument("--series", help="Comma-separated sizes (e.g., '10, 50, 1GB')")
    batch.add_argument("--batch-config", help="JSON file with a list of task objects")
    batch.add_argument("-i", "--input", help="Input file/folder to use for all tasks (overrides pattern)")
    batch.add_argument("-o", "--output-pattern", default="batch_{size}.zip",
                       help="Pattern with {size} placeholder (e.g., 'archive_{size}.zip')")
    batch.add_argument("-p", "--pattern", default="A",
                       help="Pattern for generated data (if no --input)")
    batch.add_argument("--format", choices=["zip", "pptx", "docx", "xlsx"], default="zip",
                       help="Output format for all tasks")
    batch.add_argument("--algo", choices=["deflate", "lzma", "zstd"], default="deflate",
                       help="Compression algorithm for all tasks")
    batch.add_argument("--store", action="store_true",
                       help="Disable compression (store only – ZIP format only)")
    batch.add_argument("--password", help="Encryption password for all tasks (ZIP only)")
    batch.add_argument("--legacy", action="store_true",
                       help="Use legacy ZipCrypto (Windows native) for all tasks")
    batch.set_defaults(func=cli_batch)

    # Extract
    ext = subparsers.add_parser("extract", help="Extract an archive")
    ext.add_argument("archive", help="Path to the archive to extract")
    ext.add_argument("-p", "--password", help="Password if the archive is encrypted (ZIP/Office)")
    ext.add_argument("-o", "--output-dir", help="Directory to extract to (default: <archive_name>_extracted)")
    ext.set_defaults(func=cli_extract)

    # Info
    info = subparsers.add_parser("info", help="Show archive statistics")
    info.add_argument("zipfile", help="Path to the archive")
    info.set_defaults(func=core_info)

    # Compress (context menu)
    comp = subparsers.add_parser("compress", help="Compress multiple files/folders into a single archive")
    comp.add_argument("-i", "--input", nargs="+", required=True,
                      help="Input files/folders (can specify multiple)")
    comp.add_argument("-o", "--output", required=True,
                      help="Output archive filename (extension determines format)")
    comp.add_argument("--algo", choices=["deflate", "lzma", "zstd"], default="deflate",
                      help="Compression algorithm")
    comp.add_argument("--store", action="store_true",
                      help="Store without compression (ZIP only)")
    comp.add_argument("--password", help="Encryption password (ZIP only)")
    comp.add_argument("--legacy", action="store_true",
                      help="Use legacy ZipCrypto (ZIP only)")
    comp.add_argument("--no-progress", action="store_true",
                      help="Disable progress bar")
    comp.set_defaults(func=cli_compress)

    return parser
