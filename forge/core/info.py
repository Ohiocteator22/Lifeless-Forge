# forge/core/info.py
import os
import zipfile
from forge.utils import format_size

def cli_info(args) -> None:
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
