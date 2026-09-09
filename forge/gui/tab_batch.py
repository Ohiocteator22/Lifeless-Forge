# forge/gui/tab_batch.py
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from forge.core import generate_batch, CompressionOptions
from forge.utils import format_size, format_time, parse_size_string
from forge.smart_suggest import suggest_algorithm
from forge.gui.helpers import handle_drop

def build_tab_batch(parent, root, dark_mode, has_dnd, dnd_files):
    tab = ttk.Frame(parent)
    parent.add(tab, text="Batch Generate")

    # Variables
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

    # ---- Input ----
    ttk.Label(tab, text="Input (drag & drop or browse, optional):").grid(
        row=br, column=0, padx=5, pady=5, sticky="w"
    )
    batch_input_entry = ttk.Entry(tab, textvariable=batch_input_path_var, width=40)
    batch_input_entry.grid(row=br, column=1, padx=5, pady=5, sticky="ew")

    if has_dnd and dnd_files:
        batch_input_entry.drop_target_register(dnd_files)
        batch_input_entry.dnd_bind('<<Drop>>', lambda e: handle_drop(e, batch_input_path_var))

    def batch_browse_input():
        if batch_input_is_folder_var.get():
            folder = filedialog.askdirectory()
            if folder:
                batch_input_path_var.set(folder)
        else:
            file = filedialog.askopenfilename()
            if file:
                batch_input_path_var.set(file)

    ttk.Button(tab, text="Browse", command=batch_browse_input).grid(
        row=br, column=2, padx=5, pady=5
    )
    br += 1

    ttk.Checkbutton(tab, text="Input is a Folder", variable=batch_input_is_folder_var).grid(
        row=br, column=1, padx=5, pady=5, sticky="w"
    )
    br += 1

    # ---- Sizes ----
    ttk.Label(tab, text="Sizes (comma-separated, ignored if input set):").grid(
        row=br, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab, textvariable=batch_sizes_var, width=30).grid(
        row=br, column=1, padx=5, pady=5, sticky="ew"
    )
    br += 1

    # ---- Pattern ----
    ttk.Label(tab, text="Pattern (if no input):").grid(
        row=br, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab, textvariable=batch_pattern_var, width=10).grid(
        row=br, column=1, padx=5, pady=5, sticky="w"
    )
    br += 1

    # ---- Format ----
    ttk.Label(tab, text="Format:").grid(
        row=br, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Combobox(
        tab,
        textvariable=batch_format_var,
        values=["zip", "pptx", "docx", "xlsx"],
        state="readonly"
    ).grid(row=br, column=1, padx=5, pady=5, sticky="w")
    br += 1

    # ---- Algorithm dropdown ----
    ttk.Label(tab, text="Algorithm:").grid(
        row=br, column=0, padx=5, pady=5, sticky="w"
    )
    batch_algo_combo = ttk.Combobox(
        tab,
        textvariable=batch_algo_var,
        values=["deflate", "lzma", "zstd", "lz4", "brotli"],
        state="readonly"
    )
    batch_algo_combo.set("deflate")
    batch_algo_combo.grid(row=br, column=1, padx=5, pady=5, sticky="w")
    br += 1

    # ---- Smart Suggest button ----
    def smart_suggest_batch():
        path = batch_input_path_var.get().strip()
        if not path:
            messagebox.showerror("Error", "Please select a file or folder first.")
            return
        if not os.path.exists(path):
            messagebox.showerror("Error", f"Path not found: {path}")
            return
        try:
            result = suggest_algorithm(path)
            batch_algo_var.set(result["algorithm"])
            msg = (
                f"💡 Suggested: {result['algorithm'].upper()}\n"
                f"Reason: {result['reason']}\n"
                f"Expected ratio: {result['expected_ratio']}\n"
                f"Speed: {result['speed']}"
            )
            messagebox.showinfo("Smart Suggest", msg)
        except Exception as e:
            messagebox.showerror("Smart Suggest Error", str(e))

    ttk.Button(
        tab,
        text="🤖 Smart Suggest",
        command=smart_suggest_batch
    ).grid(row=br, column=1, padx=5, pady=5, sticky="w")
    br += 1

    # ---- Output pattern ----
    ttk.Label(tab, text="Output pattern:").grid(
        row=br, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab, textvariable=batch_output_pattern_var, width=30).grid(
        row=br, column=1, padx=5, pady=5, sticky="ew"
    )
    br += 1

    # ---- Compression toggle ----
    batch_compress_check = ttk.Checkbutton(
        tab,
        text="Use ZIP compression (Store vs DEFLATE)",
        variable=batch_compress_var
    )
    batch_compress_check.grid(row=br, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    br += 1

    def on_batch_algo_change(event=None):
        if batch_algo_var.get() in ("lzma", "zstd", "lz4", "brotli"):
            batch_compress_check.config(state="disabled")
            batch_compress_var.set(True)
        else:
            batch_compress_check.config(state="normal")
    batch_algo_combo.bind("<<ComboboxSelected>>", on_batch_algo_change)
    on_batch_algo_change()

    # ---- Password ----
    ttk.Label(tab, text="Password (ZIP only):").grid(
        row=br, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab, textvariable=batch_password_var, show="*", width=20).grid(
        row=br, column=1, padx=5, pady=5, sticky="w"
    )
    br += 1

    ttk.Checkbutton(tab, text="Legacy ZipCrypto", variable=batch_legacy_var).grid(
        row=br, column=0, columnspan=2, padx=5, pady=5, sticky="w"
    )
    br += 1

    # ---- Log area ----
    batch_log = tk.Text(tab, height=8, state="disabled", wrap="word")
    batch_log.grid(row=br, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
    br += 1

    # ---- Progress bar ----
    batch_progress_bar = ttk.Progressbar(tab, orient="horizontal", length=400, mode="determinate")
    batch_progress_bar.grid(row=br, column=0, columnspan=2, padx=5, pady=5)
    br += 1

    def log_batch_msg(msg: str):
        batch_log.config(state="normal")
        batch_log.insert("end", msg + "\n")
        batch_log.see("end")
        batch_log.config(state="disabled")

    def generate_batch_thread():
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

            def batch_progress(current: int, total: int, msg: str):
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

    batch_btn = ttk.Button(
        tab,
        text="Generate Batch",
        command=lambda: threading.Thread(target=generate_batch_thread, daemon=True).start()
    )
    batch_btn.grid(row=br, column=0, columnspan=2, pady=10)

    tab.grid_columnconfigure(1, weight=1)
    tab.grid_rowconfigure(br-2, weight=1)

    return tab
