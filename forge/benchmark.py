# forge/benchmark.py
import os
import tempfile
import time
import json
from typing import Dict, Any, Optional
from forge.core import generate_zip, extract_archive, CompressionOptions
from forge.utils import format_size, format_time

def run_benchmark(size_mb: int = 10, pattern: str = "A", json_output: bool = False) -> Optional[str]:
    """
    Run compression/decompression benchmarks for all supported algorithms.
    Returns JSON string if json_output is True, else prints a table and returns None.
    """
    # Create a temporary file of the requested size
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        temp_name = tmp.name
        chunk = (pattern * (1024 * 1024)).encode()  # 1 MB chunk
        written = 0
        target_bytes = size_mb * 1024 * 1024
        while written < target_bytes:
            remaining = target_bytes - written
            write_size = min(len(chunk), remaining)
            tmp.write(chunk[:write_size])
            written += write_size
        tmp.flush()

    results = []
    algorithms = ["deflate", "lzma", "zstd"]
    formats = ["zip", "xz", "zst"]  # mapping for output extension

    for algo in algorithms:
        # Determine output extension based on algo
        ext = {"deflate": ".zip", "lzma": ".xz", "zstd": ".zst"}[algo]
        output = tempfile.NamedTemporaryFile(suffix=ext, delete=False).name

        # Compression
        start = time.perf_counter()
        opts = CompressionOptions(
            output=output,
            source=temp_name,
            algo=algo,
            fmt="zip",  # not used for LZMA/Zstd but needed
            compression=True,  # always compress
        )
        try:
            stats = generate_zip(opts)
        except Exception as e:
            # If dependency missing, skip
            results.append({
                "algorithm": algo,
                "error": str(e),
                "status": "skipped"
            })
            continue
        compress_time = time.perf_counter() - start

        # Decompression
        start = time.perf_counter()
        extract_dir = tempfile.mkdtemp()
        try:
            extract_archive(output, output_dir=extract_dir)
        except Exception as e:
            # Extraction failed, but we still record compression stats
            decompress_time = None
            status = "extract_failed"
        else:
            decompress_time = time.perf_counter() - start
            status = "ok"

        # Gather results
        result = {
            "algorithm": algo,
            "status": status,
            "input_size": stats["extracted_bytes"],
            "compressed_size": stats["compressed_bytes"],
            "ratio": stats["ratio"],
            "compress_time": compress_time,
            "decompress_time": decompress_time,
            "compress_throughput": stats["extracted_bytes"] / compress_time if compress_time else 0,
            "decompress_throughput": stats["extracted_bytes"] / decompress_time if decompress_time else 0,
        }
        results.append(result)

        # Cleanup
        os.unlink(output)
        os.unlink(temp_name)
        if os.path.exists(extract_dir):
            import shutil
            shutil.rmtree(extract_dir)

    if json_output:
        return json.dumps(results, indent=2)

    # Print table
    print("\n" + "=" * 80)
    print(f"Benchmark results for {size_mb} MB test data (pattern: '{pattern}')")
    print("=" * 80)
    print(f"{'Algorithm':<10} {'Ratio':<10} {'Compress (s)':<15} {'Decompress (s)':<15} {'C. Throughput (MB/s)':<20} {'D. Throughput (MB/s)':<20}")
    print("-" * 80)
    for r in results:
        if r.get("error"):
            print(f"{r['algorithm']:<10} {'ERROR':<10} {r['error']}")
            continue
        ct = r["compress_throughput"] / (1024*1024) if r["compress_throughput"] else 0
        dt = r["decompress_throughput"] / (1024*1024) if r["decompress_throughput"] else 0
        print(f"{r['algorithm']:<10} {r['ratio']:<10.2f} {r['compress_time']:<15.3f} {r['decompress_time']:<15.3f} {ct:<20.2f} {dt:<20.2f}")
    print("=" * 80)
    return None
