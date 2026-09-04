# forge/utils.py
import re

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
