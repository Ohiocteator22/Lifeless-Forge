# forge/gui.py
"""
Graphical user interface for Lifeless-Forge using Tkinter.
Supports dark/light mode, drag‑and‑drop, and all features.
"""

import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import zipfile

# Import core modules
from forge.core import (
    generate_zip,
    generate_batch,
    extract_archive,
    CompressionOptions,
)
from forge.utils import format_size, parse_size_string, format_time
from forge.config import load_config, save_config, detect_system_theme

# Optional dependencies
try:
    import sv_ttk
    HAS_SV_TTK = True
except ImportError:
    HAS_SV_TTK = False

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False
    TkinterDnD = None
    DND_FILES = None


# ------------------------------------------------------------
# Helper functions for theming
# ------------------------------------------------------------
def get_colors(dark_mode: bool) -> dict:
    """Return a dictionary of colours for dark/light mode."""
    if dark_mode:
        return {
            "bg": "#1c1c1c",
            "fg": "#f0f0f0",
            "textbg": "#2d2d2d",
            "textfg": "#f0f0f0",
            "selectbg": "#3a3a3a",
        }
    else:
        return {
            "bg": "#f0f0f0",
            "fg": "#000000",
            "textbg": "#ffffff",
            "textfg": "#000000",
            "selectbg": "#cce8ff",
        }


def apply_custom_colors(root_widget: tk.Widget, colors: dict) -> None:
    """Recursively apply custom colours to standard widgets (non-ttk)."""
    stack = [root_widget]
    while stack:
        widget = stack.pop()
        if hasattr(widget, 'config'):
            try:
                widget.config(
                    bg=colors["textbg"],
                    fg=colors["textfg"],
                    insertbackground=colors["fg"],
                    selectbackground=colors["selectbg"],
                )
            except tk.TclError:
                pass
        stack.extend(widget.winfo_children())


# ------------------------------------------------------------
# Main GUI launcher
# ------------------------------------------------------------
def launch_gui() -> None:
    """Launch the Tkinter GUI."""
    # ----- Load config and determine theme -------------------------------
    config = load_config()
    dark_mode_pref = config.get("dark_mode", None)
    if dark_mode_pref is None:
        dark_mode = detect_system_theme()
        if dark_mode is None:
            dark_mode = False
    else:
        dark_mode = dark_mode_pref

    # ----- Create root window -------------------------------------------
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    root.title("Lifeless-Forge – Compression Tool")
    root.geometry("760x720")
    root.resizable(False, False)
    try:
        root.iconbitmap(resource_path("app_icon.ico"))
    except:
        pass

    # ----- Menu bar -----------------------------------------------------
    menubar = tk.Menu(root)
    view_menu = tk.Menu(menubar, tearoff=0)

    dark_mode_var = tk.BooleanVar(value=dark_mode)
    view_menu.add_checkbutton(
        label="Dark Mode",
        variable=dark_mode_var,
        command=lambda: toggle_dark_mode()
    )
    menubar.add_cascade(label="View", menu=view_menu)
    root.config(menu=menubar)

    # ----- Apply Sun Valley theme ----------------------------------------
    if HAS_SV_TTK:
        if dark_mode:
            sv_ttk.set_theme("dark")
        else:
            sv_ttk.set_theme("light")
    else:
        style = ttk.Style()
        style.theme_use('clam')

    # ----- Custom colours ------------------------------------------------
    colors = get_colors(dark_mode)
    root.configure(bg=colors["bg"])

    # ----- Theme toggle function ----------------------------------------
    def toggle_dark_mode() -> None:
        nonlocal dark_mode
        dark_mode = not dark_mode
        dark_mode_var.set(dark_mode)

        if HAS_SV_TTK:
            if dark_mode:
                sv_ttk.set_theme("dark")
            else:
                sv_ttk.set_theme("light")
        else:
            style = ttk.Style()
            style.theme_use('clam')

        colors = get_colors(dark_mode)
        root.configure(bg=colors["bg"])
        apply_custom_colors(root, colors)

        config["dark_mode"] = dark_mode
        save_config(config)

    # ----- Notebook (tabs) ----------------------------------------------
    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=5, pady=5)

    # ================================================================
    # TAB 1: SINGLE GENERATE
    # ================================================================
    tab_single = ttk.Frame(nb)
    nb.add(tab_single, text="Single Generate")

    # --- Variables for tab_single ---
    size_var = tk.IntVar(value=60)
    pattern_var = tk.StringVar(value="A")
    output_var = tk.StringVar(value="compression_demo.zip")
    compress_var = tk.BooleanVar(value=True)
    password_var = tk.StringVar(value="")
    legacy_var = tk.BooleanVar(value=False)
    format_var = tk.StringVar(value="zip")
    algo_var = tk.StringVar(value="deflate")
    input_path_var = tk.StringVar(value="")
    input_is_folder_var = tk.BooleanVar(value=False)

    row = 0

    # --- Input section ---
    ttk.Label(tab_single, text="Input (drag & drop or browse):").grid(
        row=row, column=0, padx=5, pady=5, sticky="w"
    )
    input_entry = ttk.Entry(tab_single, textvariable=input_path_var, width=40)
    input_entry.grid(row=row, column=1, padx=5, pady=5, sticky="ew")

    if HAS_DND:
        input_entry.drop_target_register(DND_FILES)
        input_entry.dnd_bind('<<Drop>>', lambda e: handle_drop(e, input_path_var))

    def browse_input() -> None:
        if input_is_folder_var.get():
            folder = filedialog.askdirectory()
            if folder:
                input_path_var.set(folder)
        else:
            file = filedialog.askopenfilename()
            if file:
                input_path_var.set(file)

    ttk.Button(tab_single, text="Browse", command=browse_input).grid(
        row=row, column=2, padx=5, pady=5
    )
    row += 1

    ttk.Checkbutton(tab_single, text="Input is a Folder", variable=input_is_folder_var).grid(
        row=row, column=1, padx=5, pady=5, sticky="w"
    )
    row += 1

    # --- Size slider ---
    ttk.Label(tab_single, text="Size (MB, if no input):").grid(
        row=row, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Scale(tab_single, from_=1, to=1000, orient="horizontal", variable=size_var).grid(
        row=row, column=1, padx=5, pady=5, sticky="ew"
    )
    ttk.Label(tab_single, textvariable=size_var).grid(
        row=row, column=2, padx=5, pady=5
    )
    row += 1

    # --- Pattern ---
    ttk.Label(tab_single, text="Pattern (if no input):").grid(
        row=row, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab_single, textvariable=pattern_var, width=10).grid(
        row=row, column=1, padx=5, pady=5, sticky="w"
    )
    row += 1

    # --- Format ---
    ttk.Label(tab_single, text="Format:").grid(
        row=row, column=0, padx=5, pady=5, sticky="w"
    )
    format_combo = ttk.Combobox(
        tab_single,
        textvariable=format_var,
        values=["zip", "pptx", "docx", "xlsx"],
        state="readonly"
    )
    format_combo.grid(row=row, column=1, padx=5, pady=5, sticky="w")
    row += 1

    # --- Algorithm ---
    ttk.Label(tab_single, text="Algorithm:").grid(
        row=row, column=0, padx=5, pady=5, sticky="w"
    )
    algo_combo = ttk.Combobox(
        tab_single,
        textvariable=algo_var,
        values=["deflate", "lzma", "zstd", "lz4", "brotli"],
        state="readonly"
    )
    algo_combo.set("deflate")
    algo_combo.grid(row=row, column=1, padx=5, pady=5, sticky="w")
    row += 1

    # --- Output ---
    ttk.Label(tab_single, text="Output:").grid(
        row=row, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab_single, textvariable=output_var, width=30).grid(
        row=row, column=1, padx=5, pady=5, sticky="ew"
    )
    ttk.Button(
        tab_single,
        text="Browse",
        command=lambda: output_var.set(
            filedialog.asksaveasfilename(defaultextension="." + format_var.get())
        )
    ).grid(row=row, column=2, padx=5, pady=5)
    row += 1

    # --- Compression toggle ---
    compress_check = ttk.Checkbutton(
        tab_single,
        text="Use ZIP compression (Store vs DEFLATE)",
        variable=compress_var
    )
    compress_check.grid(row=row, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    row += 1

    # Disable compression checkbox for algorithms that don't support "store"
    def on_algo_change(event=None) -> None:
        if algo_var.get() in ("lzma", "zstd", "lz4", "brotli"):
            compress_check.config(state="disabled")
            compress_var.set(True)
        else:
            compress_check.config(state="normal")
    algo_combo.bind("<<ComboboxSelected>>", on_algo_change)
    on_algo_change()

    # --- Password ---
    ttk.Label(tab_single, text="Password (ZIP only):").grid(
        row=row, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab_single, textvariable=password_var, show="*", width=20).grid(
        row=row, column=1, padx=5, pady=5, sticky="w"
    )
    row += 1

    ttk.Checkbutton(tab_single, text="Legacy ZipCrypto (Windows native)", variable=legacy_var).grid(
        row=row, column=0, columnspan=3, padx=5, pady=5, sticky="w"
    )
    row += 1

    # --- Log area ---
    log_single = tk.Text(tab_single, height=8, state="disabled", wrap="word")
    log_single.grid(row=row, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
    row += 1

    # --- Progress bar ---
    progress_single = ttk.Progressbar(tab_single, orient="horizontal", length=400, mode="determinate")
    progress_single.grid(row=row, column=0, columnspan=3, padx=5, pady=5)
    row += 1

    # --- Log helper ---
    def log_single_msg(msg: str) -> None:
        log_single.config(state="normal")
        log_single.insert("end", msg + "\n")
        log_single.see("end")
        log_single.config(state="disabled")

    # --- Drag‑and‑drop handler ---
    def handle_drop(event, var) -> None:
        raw = event.data
        if raw.startswith('{') and raw.endswith('}'):
            raw = raw[1:-1]
        paths = [p.strip('{}') for p in raw.split() if p.strip()]
        if paths:
            var.set(paths[0])

    # --- Generation thread ---
    def generate_single_thread() -> None:
        gen_btn.config(state="disabled")
        progress_single["value"] = 0
        log_single_msg("Starting generation...")
        try:
            source = input_path_var.get().strip()
            if source and os.path.exists(source):
                log_single_msg(f"Using input: {source}")
                size_mb = None
            else:
                source = None
                size_mb = size_var.get()
                log_single_msg(f"Generating pattern ({size_mb} MB)")

            def upd(cur: int, total: int) -> None:
                if total:
                    progress_single["value"] = (cur / total) * 100
                root.update_idletasks()

            opts = CompressionOptions(
                output=output_var.get(),
                extracted_mb=size_mb,
                pattern=pattern_var.get(),
                compression=compress_var.get(),
                password=password_var.get() or None,
                progress_callback=upd,
                legacy_crypto=legacy_var.get(),
                fmt=format_var.get(),
                algo=algo_var.get(),
                source=source,
            )
            stats = generate_zip(opts)
            log_single_msg(f"Created: {stats['output']} ({stats['format'].upper()})")
            log_single_msg(f"Algorithm: {stats['algo'].upper()}")
            log_single_msg(f"Compressed: {format_size(stats['compressed_bytes'])}")
            log_single_msg(f"Extracted:  {format_size(stats['extracted_bytes'])}")
            log_single_msg(f"Ratio: {stats['ratio']:.2f}x")
            if "time" in stats:
                log_single_msg(f"Time taken: {format_time(stats['time'])}")
        except Exception as e:
            log_single_msg(f"Error: {e}")
            messagebox.showerror("Generation Error", str(e))
        finally:
            gen_btn.config(state="normal")
            progress_single["value"] = 0

    # --- Generate button ---
    gen_btn = ttk.Button(
        tab_single,
        text="Generate",
        command=lambda: threading.Thread(target=generate_single_thread, daemon=True).start()
    )
    gen_btn.grid(row=row, column=0, columnspan=3, pady=10)

    tab_single.grid_columnconfigure(1, weight=1)
    tab_single.grid_rowconfigure(row-2, weight=1)  # log area expands

    # ================================================================
    # TAB 2: BATCH GENERATE
    # ================================================================
    tab_batch = ttk.Frame(nb)
    nb.add(tab_batch, text="Batch Generate")

    # --- Variables for batch ---
    batch_sizes_var = tk.StringVar(value="10, 50, 100, 500")
    batch_pattern_var = tk.StringVar(value="A")
    batch_format_var = tk.StringVar(value="zip")
    batch_algo_var = tk.StringVar(value="deflate")
    batch_output_pattern_var = tk.StringVar(value="batch_{size}.zip")
    batch_compress_var = tk.BooleanVar(value=True)
    batch_password_var = tk.StringVar(value="")
    batch_legacy_var = tk.BooleanVar(value=False)
    batch_input_path_var = tk.StringVar(value="")
    batch_input_is_folder_var = tk.BooleanVar(value=False)

    br = 0

    # --- Input (optional) ---
    ttk.Label(tab_batch, text="Input (drag & drop or browse, optional):").grid(
        row=br, column=0, padx=5, pady=5, sticky="w"
    )
    batch_input_entry = ttk.Entry(tab_batch, textvariable=batch_input_path_var, width=40)
    batch_input_entry.grid(row=br, column=1, padx=5, pady=5, sticky="ew")

    if HAS_DND:
        batch_input_entry.drop_target_register(DND_FILES)
        batch_input_entry.dnd_bind('<<Drop>>', lambda e: handle_drop(e, batch_input_path_var))

    def batch_browse_input() -> None:
        if batch_input_is_folder_var.get():
            folder = filedialog.askdirectory()
            if folder:
                batch_input_path_var.set(folder)
        else:
            file = filedialog.askopenfilename()
            if file:
                batch_input_path_var.set(file)

    ttk.Button(tab_batch, text="Browse", command=batch_browse_input).grid(
        row=br, column=2, padx=5, pady=5
    )
    br += 1

    ttk.Checkbutton(tab_batch, text="Input is a Folder", variable=batch_input_is_folder_var).grid(
        row=br, column=1, padx=5, pady=5, sticky="w"
    )
    br += 1

    # --- Sizes ---
    ttk.Label(tab_batch, text="Sizes (comma-separated, ignored if input set):").grid(
        row=br, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab_batch, textvariable=batch_sizes_var, width=30).grid(
        row=br, column=1, padx=5, pady=5, sticky="ew"
    )
    br += 1

    # --- Pattern ---
    ttk.Label(tab_batch, text="Pattern (if no input):").grid(
        row=br, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab_batch, textvariable=batch_pattern_var, width=10).grid(
        row=br, column=1, padx=5, pady=5, sticky="w"
    )
    br += 1

    # --- Format ---
    ttk.Label(tab_batch, text="Format:").grid(
        row=br, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Combobox(
        tab_batch,
        textvariable=batch_format_var,
        values=["zip", "pptx", "docx", "xlsx"],
        state="readonly"
    ).grid(row=br, column=1, padx=5, pady=5, sticky="w")
    br += 1

    # --- Algorithm ---
    ttk.Label(tab_batch, text="Algorithm:").grid(
        row=br, column=0, padx=5, pady=5, sticky="w"
    )
    batch_algo_combo = ttk.Combobox(
        tab_batch,
        textvariable=batch_algo_var,
        values=["deflate", "lzma", "zstd", "lz4", "brotli"],
        state="readonly"
    )
    batch_algo_combo.set("deflate")
    batch_algo_combo.grid(row=br, column=1, padx=5, pady=5, sticky="w")
    br += 1

    # --- Output pattern ---
    ttk.Label(tab_batch, text="Output pattern:").grid(
        row=br, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab_batch, textvariable=batch_output_pattern_var, width=30).grid(
        row=br, column=1, padx=5, pady=5, sticky="ew"
    )
    br += 1

    # --- Compression toggle ---
    batch_compress_check = ttk.Checkbutton(
        tab_batch,
        text="Use ZIP compression (Store vs DEFLATE)",
        variable=batch_compress_var
    )
    batch_compress_check.grid(row=br, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    br += 1

    def on_batch_algo_change(event=None) -> None:
        if batch_algo_var.get() in ("lzma", "zstd", "lz4", "brotli"):
            batch_compress_check.config(state="disabled")
            batch_compress_var.set(True)
        else:
            batch_compress_check.config(state="normal")
    batch_algo_combo.bind("<<ComboboxSelected>>", on_batch_algo_change)
    on_batch_algo_change()

    # --- Password ---
    ttk.Label(tab_batch, text="Password (ZIP only):").grid(
        row=br, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab_batch, textvariable=batch_password_var, show="*", width=20).grid(
        row=br, column=1, padx=5, pady=5, sticky="w"
    )
    br += 1

    ttk.Checkbutton(tab_batch, text="Legacy ZipCrypto", variable=batch_legacy_var).grid(
        row=br, column=0, columnspan=2, padx=5, pady=5, sticky="w"
    )
    br += 1

    # --- Log area ---
    batch_log = tk.Text(tab_batch, height=8, state="disabled", wrap="word")
    batch_log.grid(row=br, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
    br += 1

    # --- Progress bar ---
    batch_progress_bar = ttk.Progressbar(tab_batch, orient="horizontal", length=400, mode="determinate")
    batch_progress_bar.grid(row=br, column=0, columnspan=2, padx=5, pady=5)
    br += 1

    def log_batch_msg(msg: str) -> None:
        batch_log.config(state="normal")
        batch_log.insert("end", msg + "\n")
        batch_log.see("end")
        batch_log.config(state="disabled")

    # --- Batch generation thread ---
    def generate_batch_thread() -> None:
        batch_btn.config(state="disabled")
        batch_progress_bar["value"] = 0
        log_batch_msg("Starting batch generation...")
        try:
            size_strs = [s.strip() for s in batch_sizes_var.get().split(',') if s.strip()]
            tasks = []
            fmt = batch_format_var.get()
            algo = batch_algo_var.get()
            source = batch_input_path_var.get().strip()
            if source and not os.path.exists(source):
                raise ValueError(f"Input source not found: {source}")
            for s in size_strs:
                size_mb = parse_size_string(s)
                out_name = batch_output_pattern_var.get().replace("{size}", s).replace("{size_mb}", str(size_mb))
                task = {
                    "size": size_mb,
                    "output": out_name,
                    "pattern": batch_pattern_var.get(),
                    "compression": batch_compress_var.get(),
                    "password": batch_password_var.get() or None,
                    "legacy": batch_legacy_var.get(),
                    "format": fmt,
                    "algo": algo,
                }
                if source:
                    task["source"] = source
                tasks.append(task)
            if not tasks:
                log_batch_msg("No tasks defined.")
                return
            log_batch_msg(f"Total tasks: {len(tasks)}")

            def batch_progress(current: int, total: int, msg: str) -> None:
                batch_progress_bar["value"] = ((current + 1) / total) * 100
                root.update_idletasks()
                log_batch_msg(f"[{current+1}/{total}] {msg}")

            results = generate_batch(tasks, progress_callback=batch_progress)
            log_batch_msg("\n=== Summary ===")
            for r in results:
                msg = (
                    f"{os.path.basename(r['output'])} ({r['format'].upper()}, {r['algo'].upper()}): "
                    f"{format_size(r['extracted_bytes'])} → {format_size(r['compressed_bytes'])} "
                    f"(ratio {r['ratio']:.2f}x)"
                )
                if "time" in r:
                    msg += f" | Time: {format_time(r['time'])}"
                log_batch_msg(msg)
        except Exception as e:
            log_batch_msg(f"Error: {e}")
            messagebox.showerror("Batch Error", str(e))
        finally:
            batch_btn.config(state="normal")
            batch_progress_bar["value"] = 0

    # --- Generate batch button ---
    batch_btn = ttk.Button(
        tab_batch,
        text="Generate Batch",
        command=lambda: threading.Thread(target=generate_batch_thread, daemon=True).start()
    )
    batch_btn.grid(row=br, column=0, columnspan=2, pady=10)

    tab_batch.grid_columnconfigure(1, weight=1)
    tab_batch.grid_rowconfigure(br-2, weight=1)


    # ================================================================
    # TAB 3: EXTRACT / INFO (with drag‑and‑drop)
    # ================================================================
    tab_extra = ttk.Frame(nb)
    nb.add(tab_extra, text="Extract / Info")

    # --- Variables for extract tab ---
    extract_path_var = tk.StringVar()
    extract_password_var = tk.StringVar()
    extract_output_var = tk.StringVar()

    er = 0

    # --- Archive path (drag‑and‑drop enabled) ---
    ttk.Label(tab_extra, text="Archive (drag & drop or browse):").grid(
        row=er, column=0, padx=5, pady=5, sticky="w"
    )
    extract_entry = ttk.Entry(tab_extra, textvariable=extract_path_var, width=50)
    extract_entry.grid(row=er, column=1, padx=5, pady=5, sticky="ew")

    if HAS_DND:
        extract_entry.drop_target_register(DND_FILES)
        extract_entry.dnd_bind('<<Drop>>', lambda e: handle_drop(e, extract_path_var))

    def browse_extract_file() -> None:
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

    ttk.Button(tab_extra, text="Browse", command=browse_extract_file).grid(
        row=er, column=2, padx=5, pady=5
    )
    er += 1

    # --- Password ---
    ttk.Label(tab_extra, text="Password (if needed):").grid(
        row=er, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab_extra, textvariable=extract_password_var, show="*", width=30).grid(
        row=er, column=1, padx=5, pady=5, sticky="w"
    )
    er += 1

    # --- Output directory ---
    ttk.Label(tab_extra, text="Extract to:").grid(
        row=er, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab_extra, textvariable=extract_output_var, width=40).grid(
        row=er, column=1, padx=5, pady=5, sticky="ew"
    )

    def browse_output_dir() -> None:
        dir_path = filedialog.askdirectory()
        if dir_path:
            extract_output_var.set(dir_path)

    ttk.Button(tab_extra, text="Browse", command=browse_output_dir).grid(
        row=er, column=2, padx=5, pady=5
    )
    er += 1

    # --- Buttons ---
    btn_frame = ttk.Frame(tab_extra)
    btn_frame.grid(row=er, column=0, columnspan=3, pady=10)

    def do_extract_thread() -> None:
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
            # Bind e as default argument to avoid late-binding issue
            root.after(0, lambda e=e: messagebox.showerror("Extraction Error", str(e)))

    def do_extract() -> None:
        threading.Thread(target=do_extract_thread, daemon=True).start()

    def do_info_thread() -> None:
        archive = extract_path_var.get().strip()
        if not archive:
            root.after(0, lambda: messagebox.showerror("Error", "Please select an archive."))
            return
        if not os.path.exists(archive):
            root.after(0, lambda: messagebox.showerror("Error", f"Archive not found: {archive}"))
            return

        try:
            # Check for non‑ZIP archives (LZMA, Zstd, LZ4, Brotli, TAR)
            if archive.lower().endswith(('.xz', '.lzma', '.zst', '.zstd', '.tar.xz', '.txz', '.tar.zst', '.tzst', '.lz4', '.tar.lz4', '.br', '.tar.br')):
                size = os.path.getsize(archive)
                msg = f"Archive: {os.path.basename(archive)}\nType: LZMA, Zstd, LZ4, or Brotli\nCompressed size: {format_size(size)}"
                root.after(0, lambda: messagebox.showinfo("Archive Info", msg))
                return

            # ZIP / Office
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
            # Bind e as default argument to avoid late-binding issue
            root.after(0, lambda e=e: messagebox.showerror("Info Error", str(e)))

    def do_info() -> None:
        threading.Thread(target=do_info_thread, daemon=True).start()

    ttk.Button(btn_frame, text="Extract Archive", command=do_extract).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Show Info", command=do_info).pack(side=tk.LEFT, padx=5)

    # ------------------------------------------------------------
    # Apply custom colours and start main loop
    # ------------------------------------------------------------
    apply_custom_colors(root, get_colors(dark_mode))
    root.mainloop()


# ------------------------------------------------------------
# Utility to resolve resource path (for PyInstaller)
# ------------------------------------------------------------
def resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
