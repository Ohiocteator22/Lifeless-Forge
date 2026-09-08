# forge/smart_suggest.py
"""
Smart Suggest – analyzes files/folders and recommends the best compression algorithm.
"""

import os
import mimetypes
from typing import Dict, Any, Optional

from forge.utils import format_size

# Extended mapping of file extensions to content categories
TEXT_EXTS = {
    '.txt', '.log', '.json', '.xml', '.html', '.htm', '.css', '.js', '.md',
    '.csv', '.tsv', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.conf',
    '.py', '.java', '.c', '.cpp', '.h', '.hpp', '.go', '.rs', '.rb', '.php',
    '.sh', '.bash', '.zsh', '.fish', '.lua', '.pl', '.pm', '.r', '.swift',
    '.kt', '.scala', '.clj', '.elm', '.hs', '.lisp', '.cl', '.sql', '.rdf',
    '.ttl', '.n3', '.jsonld', '.rss', '.atom'
}

# Already compressed formats – recommend STORE
COMPRESSED_EXTS = {
    '.zip', '.7z', '.rar', '.gz', '.bz2', '.xz', '.zst', '.lz4', '.br',
    '.tgz', '.tbz2', '.txz', '.tzst', '.tlz4', '.tbr', '.tar', '.arj', '.lzh'
}

# Media formats – usually already compressed
MEDIA_EXTS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.avif', '.heic',
    '.mp4', '.webm', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.m4v',
    '.mp3', '.flac', '.wav', '.aac', '.ogg', '.opus', '.wma',
    '.pdf', '.epub', '.mobi', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.exe', '.dll', '.so', '.dylib', '.bin', '.img', '.iso'
}

def analyze_path(path: str) -> Dict[str, Any]:
    """
    Analyze a file or folder and return statistics.
    """
    if os.path.isdir(path):
        total_size = 0
        file_count = 0
        ext_counts = {}
        for root, dirs, files in os.walk(path):
            for f in files:
                file_count += 1
                full = os.path.join(root, f)
                try:
                    size = os.path.getsize(full)
                    total_size += size
                    ext = os.path.splitext(f)[1].lower()
                    ext_counts[ext] = ext_counts.get(ext, 0) + 1
                except (OSError, PermissionError):
                    pass
        return {
            "is_folder": True,
            "total_size": total_size,
            "file_count": file_count,
            "ext_counts": ext_counts,
        }
    else:
        ext = os.path.splitext(path)[1].lower()
        size = os.path.getsize(path)
        mime_type, _ = mimetypes.guess_type(path)
        return {
            "is_folder": False,
            "ext": ext,
            "size": size,
            "mime_type": mime_type,
        }


def suggest_algorithm(path: str) -> Dict[str, Any]:
    """
    Recommend the best compression algorithm for the given file/folder.
    Returns a dict with keys: algorithm, reason, expected_ratio, speed, command_example.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Path not found: {path}")

    # Analyze the path
    stats = analyze_path(path)

    # Folder handling
    if stats["is_folder"]:
        size = stats["total_size"]
        file_count = stats["file_count"]
        # If folder contains mostly text files, suggest Brotli? But folder usually mixed.
        # Count text extensions vs others.
        ext_counts = stats["ext_counts"]
        text_files = sum(count for ext, count in ext_counts.items() if ext in TEXT_EXTS)
        total_files = file_count
        if total_files == 0:
            return {
                "algorithm": "deflate",
                "reason": "Folder is empty or contains only empty files. Use STORE (no compression).",
                "expected_ratio": "~1×",
                "speed": "Instant",
                "command_example": f"forge compress -i \"{path}\" -o archive.zip --algo deflate --store"
            }
        text_ratio = text_files / total_files

        # Heuristics for folder
        if size > 500 * 1024 * 1024:  # >500 MB
            if text_ratio > 0.5:
                return {
                    "algorithm": "zstd",
                    "reason": "Large folder with many text files. Zstd offers great compression with speed.",
                    "expected_ratio": "10–100×",
                    "speed": "Fast",
                    "command_example": f"forge compress -i \"{path}\" -o archive.tar.zst --algo zstd"
                }
            else:
                return {
                    "algorithm": "lz4",
                    "reason": "Large folder with mixed content. LZ4 provides fast compression and decent ratios.",
                    "expected_ratio": "2–20×",
                    "speed": "Lightning fast",
                    "command_example": f"forge compress -i \"{path}\" -o archive.tar.lz4 --algo lz4"
                }
        else:
            # Small to medium folder
            if text_ratio > 0.7:
                return {
                    "algorithm": "brotli",
                    "reason": "Folder contains mostly text files. Brotli excels at text compression.",
                    "expected_ratio": "50–10,000×",
                    "speed": "Fast",
                    "command_example": f"forge compress -i \"{path}\" -o archive.tar.br --algo brotli"
                }
            else:
                return {
                    "algorithm": "zstd",
                    "reason": "Mixed content folder. Zstd provides the best balance of speed and ratio.",
                    "expected_ratio": "5–100×",
                    "speed": "Fast",
                    "command_example": f"forge compress -i \"{path}\" -o archive.tar.zst --algo zstd"
                }

    # Single file handling
    ext = stats["ext"]
    size = stats["size"]

    # Already compressed formats → STORE
    if ext in COMPRESSED_EXTS:
        return {
            "algorithm": "deflate",
            "reason": "File is already compressed. Use STORE (no compression) to avoid wasting time.",
            "expected_ratio": "~1×",
            "speed": "Instant",
            "command_example": f"forge generate -i \"{path}\" -o \"{path}.store\" --algo deflate --store"
        }

    # Media files – usually already compressed, but we can still try LZMA for minimal gains
    if ext in MEDIA_EXTS:
        return {
            "algorithm": "lzma",
            "reason": "Media files are often already compressed. LZMA may achieve small additional savings.",
            "expected_ratio": "1–5×",
            "speed": "Slow",
            "command_example": f"forge generate -i \"{path}\" -o \"{path}.xz\" --algo lzma"
        }

    # Text files → Brotli
    if ext in TEXT_EXTS:
        return {
            "algorithm": "brotli",
            "reason": "Text files compress extremely well with Brotli.",
            "expected_ratio": "10,000–20,000×" if size > 1024*1024 else "100–10,000×",
            "speed": "Fast",
            "command_example": f"forge generate -i \"{path}\" -o \"{path}.br\" --algo brotli"
        }

    # Large binary files (>=100 MB)
    if size > 100 * 1024 * 1024:
        return {
            "algorithm": "lz4",
            "reason": "Large file – LZ4 offers the fastest compression with good ratios.",
            "expected_ratio": "2–10×",
            "speed": "Lightning fast",
            "command_example": f"forge generate -i \"{path}\" -o \"{path}.lz4\" --algo lz4"
        }

    # Small binary / unknown → Zstd (balanced)
    return {
        "algorithm": "zstd",
        "reason": "Zstd offers an excellent balance of speed and compression ratio for most files.",
        "expected_ratio": "2–100×",
        "speed": "Fast",
        "command_example": f"forge generate -i \"{path}\" -o \"{path}.zst\" --algo zstd"
    }


def print_suggestion(result: Dict[str, Any], path: str) -> None:
    """Pretty‑print the suggestion to stdout."""
    print(f"\n📊 Analyzed: {path}")
    size = os.path.getsize(path) if os.path.isfile(path) else None
    if size is not None:
        print(f"   Size: {format_size(size)}")
    elif os.path.isdir(path):
        total = sum(os.path.getsize(os.path.join(root, f)) for root, _, files in os.walk(path) for f in files)
        print(f"   Size: {format_size(total)} (folder)")
    print(f"💡 Best algorithm: {result['algorithm'].upper()}")
    print(f"   Reason: {result['reason']}")
    print(f"   Expected ratio: {result['expected_ratio']}")
    print(f"   Speed: {result['speed']}")
    print(f"   Command: {result['command_example']}")
