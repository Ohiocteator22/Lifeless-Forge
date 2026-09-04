# forge/cli.py
from .utils import format_size, parse_size_string, get_progress_printer
import argparse
import sys
import json
from .core import generate_zip, generate_batch, extract_zip, cli_info as core_info, print_stats
from .utils import parse_size_string, get_progress_printer

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
                "algo": args.algo,
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
    gen.add_argument("--algo", choices=["deflate", "lzma"], default="deflate",
                 help="Compression algorithm: deflate (ZIP) or lzma (XZ)")
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
    batch.add_argument("--algo", choices=["deflate", "lzma"], default="deflate",
                   help="Algorithm for all tasks (when using --series)")
    batch.set_defaults(func=cli_batch)

    ext = subparsers.add_parser("extract", help="Extract a password-protected archive")
    ext.add_argument("archive", help="Path to archive")
    ext.add_argument("-p", "--password", required=True, help="Password")
    ext.add_argument("-o", "--output-dir", help="Output directory")
    ext.set_defaults(func=cli_extract)

    info = subparsers.add_parser("info", help="Show archive stats")
    info.add_argument("zipfile", help="Path to archive")
    info.set_defaults(func=core_info)

    return parser
