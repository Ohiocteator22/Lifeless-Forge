# forge/core/batch.py
from typing import List, Dict, Any, Optional, Callable
from forge.core.compression import generate_zip
from forge.core.base import CompressionOptions
from forge.utils import parse_size_string

def generate_batch(tasks: List[Dict[str, Any]], progress_callback: Optional[Callable[[int, int, str], None]] = None) -> List[Dict[str, Any]]:
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
            "algo": "deflate",
            "source": None,
        }
        params.update(task)
        if isinstance(params["size"], str):
            params["size"] = parse_size_string(params["size"])

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
    return results
