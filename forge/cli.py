# forge/cli.py
import argparse
import sys
import json
import os
from forge.core import generate_zip, generate_batch, extract_archive, print_stats, cli_info as core_info
from forge.utils import format_size, parse_size_string, get_progress_printer

__all__ = ['setup_cli_parser', 'cli_generate', 'cli_batch', 'cli_extract']
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
        algo=args.algo,
        source=getattr(args, 'input', None),
    )
    print_stats(stats)
    if args.password:
        if args.legacy:
            print("Note: Used legacy ZipCrypto (Windows native).")
        else:
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
        print("No tasks defined. Use --series or --batch-config.")
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
        if isinstance(params["size"], str):
            params["size"] = parse_size_string(params["size"])
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

def setup_cli_parser():
    parser = argparse.ArgumentParser(
        description="Lifeless-Forge – Compression Tool",
        epilog="Use -h for more details on each subcommand."
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command to execute")

    # Generate subcommand
    gen = subparsers.add_parser("generate", help="Generate a single archive")
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

    # Batch subcommand
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

    # Extract subcommand
    ext = subparsers.add_parser("extract", help="Extract an archive")
    ext.add_argument("archive", help="Path to the archive to extract")
    ext.add_argument("-p", "--password", help="Password if the archive is encrypted (ZIP/Office)")
    ext.add_argument("-o", "--output-dir", help="Directory to extract to (default: <archive_name>_extracted)")
    ext.set_defaults(func=cli_extract)

    # Info subcommand
    info = subparsers.add_parser("info", help="Show archive statistics")
    info.add_argument("zipfile", help="Path to the archive")
    info.set_defaults(func=core_info)

    return parser
