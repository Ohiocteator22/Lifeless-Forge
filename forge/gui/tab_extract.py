# forge/gui/tab_extract.py
import os
import threading
import zipfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from forge.core import extract_archive
from forge.utils import format_size
from forge.gui.helpers import handle_drop

def build_tab_extract(parent, root, dark_mode, has_dnd, dnd_files):
    tab = ttk.Frame(parent)
    parent.add(tab, text="Extract / Info")

    extract_path_var = tk.StringVar()
    extract_password_var = tk.StringVar()
    extract_output_var = tk.StringVar()

    er = 0

    # ---- Archive path (drag‑and‑drop) ----
    ttk.Label(tab, text="Archive (drag & drop or browse):").grid(
        row=er, column=0, padx=5, pady=5, sticky="w"
    )
    extract_entry = ttk.Entry(tab, textvariable=extract_path_var, width=50)
    extract_entry.grid(row=er, column=1, padx=5, pady=5, sticky="ew")

    if has_dnd and dnd_files:
        extract_entry.drop_target_register(dnd_files)
        extract_entry.dnd_bind('<<Drop>>', lambda e: handle_drop(e, extract_path_var))

    def browse_extract_file():
        archive = filedialog.askopenfilename(
            title="Select archive",
            filetypes=[
                ("All archives", "*.zip *.xz *.lzma *.tar.xz *.txz *.zst *.zstd *.tar.zst *.tzst *.lz4 *.tar.lz4 *.br *.tar.br *.pptx *.docx *.xlsx"),
                ("ZIP files", "*.zip"),
                ("XZ files", "*.xz *.lzma"),
                ("TAR.XZ files", "*.tar.xz *.txz"),
                ("Zstandard", "*.zst *.zstd *.tar.zst *.tzst"),
                ("LZ4 files", "*.lz4 *.tar.lz4"),
                ("Brotli files", "*.br *.tar.br"),
                ("PPTX files", "*.pptx"),
                ("DOCX files", "*.docx"),
                ("XLSX files", "*.xlsx")
            ]
        )
        if archive:
            extract_path_var.set(archive)

    ttk.Button(tab, text="Browse", command=browse_extract_file).grid(
        row=er, column=2, padx=5, pady=5
    )
    er += 1

    # ---- Password ----
    ttk.Label(tab, text="Password (if needed):").grid(
        row=er, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab, textvariable=extract_password_var, show="*", width=30).grid(
        row=er, column=1, padx=5, pady=5, sticky="w"
    )
    er += 1

    # ---- Output directory ----
    ttk.Label(tab, text="Extract to:").grid(
        row=er, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab, textvariable=extract_output_var, width=40).grid(
        row=er, column=1, padx=5, pady=5, sticky="ew"
    )

    def browse_output_dir():
        dir_path = filedialog.askdirectory()
        if dir_path:
            extract_output_var.set(dir_path)

    ttk.Button(tab, text="Browse", command=browse_output_dir).grid(
        row=er, column=2, padx=5, pady=5
    )
    er += 1

    # ---- Buttons ----
    btn_frame = ttk.Frame(tab)
    btn_frame.grid(row=er, column=0, columnspan=3, pady=10)

    def do_extract_thread():
        archive = extract_path_var.get().strip()
        if not archive:
            root.after(0, lambda: messagebox.showerror("Error", "Please select an archive."))
            return
        if not os.path.exists(archive):
            root.after(0, lambda: messagebox.showerror("Error", f"Archive not found: {archive}"))
            return

        password = extract_password_var.get() or None
        output_dir = extract_output_var.get().strip()
        if not output_dir:
            output_dir = os.path.splitext(archive)[0] + "_extracted"
            extract_output_var.set(output_dir)

        try:
            out = extract_archive(archive, password, output_dir)
            root.after(0, lambda: messagebox.showinfo("Success", f"Extracted to: {out}"))
        except Exception as e:
            root.after(0, lambda e=e: messagebox.showerror("Extraction Error", str(e)))

    def do_extract():
        threading.Thread(target=do_extract_thread, daemon=True).start()

    def do_info_thread():
        archive = extract_path_var.get().strip()
        if not archive:
            root.after(0, lambda: messagebox.showerror("Error", "Please select an archive."))
            return
        if not os.path.exists(archive):
            root.after(0, lambda: messagebox.showerror("Error", f"Archive not found: {archive}"))
            return

        try:
            if archive.lower().endswith(('.xz', '.lzma', '.zst', '.zstd', '.tar.xz', '.txz', '.tar.zst', '.tzst', '.lz4', '.tar.lz4', '.br', '.tar.br')):
                size = os.path.getsize(archive)
                msg = f"Archive: {os.path.basename(archive)}\nType: LZMA, Zstd, LZ4, or Brotli\nCompressed size: {format_size(size)}"
                root.after(0, lambda: messagebox.showinfo("Archive Info", msg))
                return

            with zipfile.ZipFile(archive, 'r') as z:
                info = z.infolist()
                if not info:
                    root.after(0, lambda: messagebox.showinfo("Archive Info", "Archive is empty."))
                    return
                total_compressed = sum(f.compress_size for f in info)
                total_extracted = sum(f.file_size for f in info)
                ratio = total_extracted / total_compressed if total_compressed else 0
                msg = (
                    f"Archive: {os.path.basename(archive)}\n"
                    f"Files: {len(info)}\n"
                    f"Compressed: {format_size(total_compressed)}\n"
                    f"Extracted:  {format_size(total_extracted)}\n"
                    f"Ratio: {ratio:.2f}x"
                )
                root.after(0, lambda: messagebox.showinfo("Archive Info", msg))
        except Exception as e:
            root.after(0, lambda e=e: messagebox.showerror("Info Error", str(e)))

    def do_info():
        threading.Thread(target=do_info_thread, daemon=True).start()

    ttk.Button(btn_frame, text="Extract Archive", command=do_extract).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Show Info", command=do_info).pack(side=tk.LEFT, padx=5)

    tab.grid_columnconfigure(1, weight=1)
    return tab
