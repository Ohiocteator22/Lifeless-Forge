# forge/cli.py
"""
Command-line interface for Lifeless-Forge.
"""

import argparse
import sys
import json
import os
import tempfile
import shutil
import time
import logging
from typing import List, Dict, Any

from forge.core import (
    generate_zip,
    generate_batch,
    extract_archive,
    print_stats,
    cli_info as core_info,
    CompressionOptions,
)
from forge.utils import (
    format_size,
    parse_size_string,
    get_progress_printer,
    format_time,
    normalize_format,
    normalize_algorithm,
)
from forge.benchmark import run_benchmark
from forge.exceptions import ForgeError

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Validation functions
# ----------------------------------------------------------------------
def validate_generate_args(args: argparse.Namespace) -> None:
    """Check for incompatible combinations in 'generate'."""
    if args.password and args.algo in ("lzma", "zstd", "lz4", "brotli"):
        raise ValueError(f"Encryption is not supported for {args.algo.upper()} compression.")
    if args.format in ("pptx", "docx", "xlsx") and args.algo != "deflate":
        raise ValueError(f"Office format '{args.format}' only supports DEFLATE compression.")
    if args.store and (args.format != "zip" or args.algo != "deflate"):
        raise ValueError("--store (no compression) is only valid with format=zip and algo=deflate.")
    if args.legacy and args.format != "zip":
        raise ValueError("--legacy (ZipCrypto) is only valid with format=zip.")


def validate_batch_args(args: argparse.Namespace) -> None:
    """Check for incompatible combinations in 'batch'."""
    if args.password and args.algo in ("lzma", "zstd", "lz4", "brotli"):
        raise ValueError(f"Encryption is not supported for {args.algo.upper()} compression in batch.")
    if args.format in ("pptx", "docx", "xlsx") and args.algo != "deflate":
        raise ValueError(f"Office format '{args.format}' only supports DEFLATE compression.")
    if args.store and (args.format != "zip" or args.algo != "deflate"):
        raise ValueError("--store is only valid with format=zip and algo=deflate in batch.")
    if args.legacy and args.format != "zip":
        raise ValueError("--legacy is only valid with format=zip in batch.")


def validate_compress_args(args: argparse.Namespace) -> None:
    """Check for incompatible combinations in 'compress'."""
    if args.password and args.algo in ("lzma", "zstd", "lz4", "brotli"):
        raise ValueError(f"Encryption is not supported for {args.algo.upper()} compression.")
    if args.store and args.algo != "deflate":
        raise ValueError("--store is only valid with algo=deflate.")
    if args.legacy and args.algo != "deflate":
        raise ValueError("--legacy is only valid with algo=deflate.")


# ----------------------------------------------------------------------
# CLI handlers
# ----------------------------------------------------------------------
def cli_generate(args: argparse.Namespace) -> None:
    """Handle 'forge generate'."""
    args.format = normalize_format(args.format)
    args.algo = normalize_algorithm(args.algo)
    validate_generate_args(args)

    progress = get_progress_printer(enable=not args.no_progress, total=args.size)
    try:
        opts = CompressionOptions(
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
        stats = generate_zip(opts)
        print_stats(stats)
        if args.password:
            if args.legacy:
                print("Note: Used legacy ZipCrypto (Windows native).")
            else:
                print("Note: Used AES-256 encryption.")
    except ForgeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cli_batch(args: argparse.Namespace) -> None:
    """Handle 'forge batch'."""
    args.format = normalize_format(args.format)
    args.algo = normalize_algorithm(args.algo)
    validate_batch_args(args)

    tasks: List[Dict[str, Any]] = []

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

    def batch_progress(current: int, total: int, msg: str) -> None:
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
            opts = CompressionOptions(
                output=params["output"],
                extracted_mb=params["size"],
                pattern=params["pattern"],
                compression=params["compression"],
                password=params["password"],
                legacy_crypto=params["legacy"],
                fmt=params.get("format", "zip"),
                algo=params.get("algo", "deflate"),
                source=params.get("source"),
            )
            stats = generate_zip(opts)
            results.append(stats)
        except ForgeError as e:
            print(f"\nError in task {idx+1}: {e}", file=sys.stderr)
            sys.exit(1)

    print("\n=== Batch Summary ===")
    for r in results:
        print(f"{os.path.basename(r['output'])} ({r['format'].upper()}, {r['algo'].upper()}): "
              f"{format_size(r['extracted_bytes'])} → {format_size(r['compressed_bytes'])} "
              f"(ratio {r['ratio']:.2f}x)")


def cli_extract(args: argparse.Namespace) -> None:
    """Handle 'forge extract'."""
    start = time.time()
    try:
        out_dir = extract_archive(args.archive, args.password, args.output_dir)
        elapsed = time.time() - start
        print(f"Extracted to: {out_dir}")
        print("-" * 40)
        print(f"Time taken: {format_time(elapsed)}")
    except ForgeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cli_compress(args: argparse.Namespace) -> None:
    """Handle 'forge compress' (multiple files/folders)."""
    args.algo = normalize_algorithm(args.algo)
    validate_compress_args(args)

    sources = args.input
    output = args.output

    # Single folder – compress directly
    if len(sources) == 1 and os.path.isdir(sources[0]):
        source = sources[0]
        try:
            opts = CompressionOptions(
                output=output,
                extracted_mb=None,
                pattern="",
                compression=not args.store,
                password=args.password,
                legacy_crypto=args.legacy,
                fmt="zip",
                algo=args.algo,
                source=source,
            )
            stats = generate_zip(opts)
            print_stats(stats)
        except ForgeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    # Multiple sources: copy everything to a temp dir and compress as a folder
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
            opts = CompressionOptions(
                output=output,
                extracted_mb=None,
                pattern="",
                compression=not args.store,
                password=args.password,
                legacy_crypto=args.legacy,
                fmt="zip",
                algo=args.algo,
                source=tmpdir,
            )
            stats = generate_zip(opts)
            print_stats(stats)
        except ForgeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


def cli_benchmark(args: argparse.Namespace) -> None:
    """Handle 'forge benchmark'."""
    try:
        result = run_benchmark(size_mb=args.size, pattern=args.pattern, json_output=args.json)
        if args.json:
            print(result)
    except Exception as e:
        print(f"Benchmark failed: {e}", file=sys.stderr)
        sys.exit(1)


# ----------------------------------------------------------------------
# Parser setup
# ----------------------------------------------------------------------
def setup_cli_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        description="Lifeless-Forge – Compression Tool",
        epilog="Use -h for more details on each subcommand."
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command to execute")

    # --- Generate --------------------------------------------------------
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
    gen.add_argument("--algo", choices=["deflate", "lzma", "zstd", "lz4"], default="deflate",
                     help="Compression algorithm: deflate (ZIP), lzma (XZ), zstd (Zstandard), lz4")
    gen.add_argument("--store", action="store_true",
                     help="Disable compression (store only – ZIP format only)")
    gen.add_argument("--password", help="Encryption password (ZIP only)")
    gen.add_argument("--legacy", action="store_true",
                     help="Use legacy ZipCrypto (Windows native) instead of AES-256")
    gen.add_argument("--no-progress", action="store_true",
                     help="Disable progress bar")
    gen.set_defaults(func=cli_generate)

    # --- Batch -----------------------------------------------------------
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
    batch.add_argument("--algo", choices=["deflate", "lzma", "zstd", "lz4"], default="deflate",
                       help="Compression algorithm for all tasks")
    batch.add_argument("--store", action="store_true",
                       help="Disable compression (store only – ZIP format only)")
    batch.add_argument("--password", help="Encryption password for all tasks (ZIP only)")
    batch.add_argument("--legacy", action="store_true",
                       help="Use legacy ZipCrypto (Windows native) for all tasks")
    batch.set_defaults(func=cli_batch)

    # --- Extract ---------------------------------------------------------
    ext = subparsers.add_parser("extract", help="Extract an archive")
    ext.add_argument("archive", help="Path to the archive to extract")
    ext.add_argument("-p", "--password", help="Password if the archive is encrypted (ZIP/Office)")
    ext.add_argument("-o", "--output-dir", help="Directory to extract to (default: <archive_name>_extracted)")
    ext.set_defaults(func=cli_extract)

    # --- Info ------------------------------------------------------------
    info = subparsers.add_parser("info", help="Show archive statistics")
    info.add_argument("zipfile", help="Path to the archive")
    info.set_defaults(func=core_info)

    # --- Compress --------------------------------------------------------
    comp = subparsers.add_parser("compress", help="Compress multiple files/folders into a single archive")
    comp.add_argument("-i", "--input", nargs="+", required=True,
                      help="Input files/folders (can specify multiple)")
    comp.add_argument("-o", "--output", required=True,
                      help="Output archive filename (extension determines format)")
    comp.add_argument("--algo", choices=["deflate", "lzma", "zstd", "lz4"], default="deflate",
                      help="Compression algorithm")
    comp.add_argument("--store", action="store_true",
                      help="Store without compression (ZIP only)")
    comp.add_argument("--password", help="Encryption password (ZIP only)")
    comp.add_argument("--legacy", action="store_true",
                      help="Use legacy ZipCrypto (ZIP only)")
    comp.add_argument("--no-progress", action="store_true",
                      help="Disable progress bar")
    comp.set_defaults(func=cli_compress)

    # --- Benchmark -------------------------------------------------------
    bench = subparsers.add_parser("benchmark", help="Run compression benchmarks for all algorithms")
    bench.add_argument("--size", type=int, default=10, help="Test data size in MB (default: 10)")
    bench.add_argument("--pattern", default="A", help="Character pattern for test data (default: 'A')")
    bench.add_argument("--json", action="store_true", help="Output results as JSON")
    bench.set_defaults(func=cli_benchmark)

    return parser
