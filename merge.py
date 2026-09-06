# merge.py
import os
import sys

# Order matters: utils, templates, config, core, cli, gui, __main__
modules = [
    "utils",
    "templates",
    "config",
    "core",
    "cli",
    "gui",
    "__main__",
]

output_file = "forge_all.py"

with open(output_file, "w") as out:
    out.write("# -*- coding: utf-8 -*-\n")
    out.write("# Auto‑generated from modular code – do not edit manually\n\n")
    
    # Add a shebang and imports that might be needed globally
    out.write("#!/usr/bin/env python3\n")
    out.write("import sys\nimport os\nimport threading\nimport tkinter as tk\n")
    out.write("from tkinter import ttk, filedialog, messagebox, simpledialog\n")
    out.write("import zipfile\nimport tempfile\nimport json\nimport lzma\n")
    out.write("import shutil\nimport tarfile\nimport re\nfrom pathlib import Path\n")
    out.write("import xml.etree.ElementTree as ET\n\n")
    out.write("# Optional imports with fallbacks\n")
    out.write("try:\n    import zstandard as zstd\n    HAS_ZSTD = True\nexcept ImportError:\n    HAS_ZSTD = False\n    zstd = None\n\n")
    out.write("try:\n    import sv_ttk\n    HAS_SV_TTK = True\nexcept ImportError:\n    HAS_SV_TTK = False\n\n")
    out.write("try:\n    from tkinterdnd2 import DND_FILES, TkinterDnD\n    HAS_DND = True\nexcept ImportError:\n    HAS_DND = False\n    TkinterDnD = None\n    DND_FILES = None\n\n")
    out.write("try:\n    import pyzipper\n    HAS_PYZIPPER = True\nexcept ImportError:\n    HAS_PYZIPPER = False\n\n")
    
    for mod in modules:
        src = os.path.join("forge", mod + ".py")
        if not os.path.exists(src):
            print(f"Warning: {src} not found, skipping.")
            continue
        out.write(f"# ---------- {mod}.py ----------\n")
        with open(src, "r") as f:
            content = f.read()
            # Remove the shebang line if present
            if content.startswith("#!"):
                content = content[content.index("\n")+1:]
            # Remove module‑level imports that we already added globally (optional)
            out.write(content)
            out.write("\n\n")

print(f"Merged {len(modules)} modules into {output_file}")
