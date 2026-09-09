# forge/gui/tab_single.py
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from forge.core import generate_zip, CompressionOptions
from forge.utils import format_size, format_time
from forge.smart_suggest import suggest_algorithm
from forge.gui.helpers import handle_drop

def build_tab_single(parent, root, dark_mode, has_dnd):
    """Build the Single Generate tab."""
    tab = ttk.Frame(parent)
    parent.add(tab, text="Single Generate")

    # Variables
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

    # ---- Input section ----
    ttk.Label(tab, text="Input (drag & drop or browse):").grid(
        row=row, column=0, padx=5, pady=5, sticky="w"
    )
    input_entry = ttk.Entry(tab, textvariable=input_path_var, width=40)
    input_entry.grid(row=row, column=1, padx=5, pady=5, sticky="ew")

    if has_dnd:
        input_entry.drop_target_register("DND_FILES")
        input_entry.dnd_bind('<<Drop>>', lambda e: handle_drop(e, input_path_var))

    def browse_input():
        if input_is_folder_var.get():
            folder = filedialog.askdirectory()
            if folder:
                input_path_var.set(folder)
        else:
            file = filedialog.askopenfilename()
            if file:
                input_path_var.set(file)

    ttk.Button(tab, text="Browse", command=browse_input).grid(
        row=row, column=2, padx=5, pady=5
    )
    row += 1

    ttk.Checkbutton(tab, text="Input is a Folder", variable=input_is_folder_var).grid(
        row=row, column=1, padx=5, pady=5, sticky="w"
    )
    row += 1

    # ---- Size slider ----
    ttk.Label(tab, text="Size (MB, if no input):").grid(
        row=row, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Scale(tab, from_=1, to=1000, orient="horizontal", variable=size_var).grid(
        row=row, column=1, padx=5, pady=5, sticky="ew"
    )
    ttk.Label(tab, textvariable=size_var).grid(
        row=row, column=2, padx=5, pady=5
    )
    row += 1

    # ---- Pattern ----
    ttk.Label(tab, text="Pattern (if no input):").grid(
        row=row, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab, textvariable=pattern_var, width=10).grid(
        row=row, column=1, padx=5, pady=5, sticky="w"
    )
    row += 1

    # ---- Format ----
    ttk.Label(tab, text="Format:").grid(
        row=row, column=0, padx=5, pady=5, sticky="w"
    )
    format_combo = ttk.Combobox(
        tab,
        textvariable=format_var,
        values=["zip", "pptx", "docx", "xlsx"],
        state="readonly"
    )
    format_combo.grid(row=row, column=1, padx=5, pady=5, sticky="w")
    row += 1

    # ---- Algorithm dropdown ----
    ttk.Label(tab, text="Algorithm:").grid(
        row=row, column=0, padx=5, pady=5, sticky="w"
    )
    algo_combo = ttk.Combobox(
        tab,
        textvariable=algo_var,
        values=["deflate", "lzma", "zstd", "lz4", "brotli"],
        state="readonly"
    )
    algo_combo.set("deflate")
    algo_combo.grid(row=row, column=1, padx=5, pady=5, sticky="w")
    row += 1

    # ---- Smart Suggest button (own row) ----
    def smart_suggest():
        path = input_path_var.get().strip()
        if not path:
            messagebox.showerror("Error", "Please select a file or folder first.")
            return
        if not os.path.exists(path):
            messagebox.showerror("Error", f"Path not found: {path}")
            return
        try:
            result = suggest_algorithm(path)
            algo_var.set(result["algorithm"])
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
        command=smart_suggest
    ).grid(row=row, column=1, padx=5, pady=5, sticky="w")
    row += 1

    # ---- Output ----
    ttk.Label(tab, text="Output:").grid(
        row=row, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab, textvariable=output_var, width=30).grid(
        row=row, column=1, padx=5, pady=5, sticky="ew"
    )
    ttk.Button(
        tab,
        text="Browse",
        command=lambda: output_var.set(
            filedialog.asksaveasfilename(defaultextension="." + format_var.get())
        )
    ).grid(row=row, column=2, padx=5, pady=5)
    row += 1

    # ---- Compression toggle ----
    compress_check = ttk.Checkbutton(
        tab,
        text="Use ZIP compression (Store vs DEFLATE)",
        variable=compress_var
    )
    compress_check.grid(row=row, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    row += 1

    def on_algo_change(event=None):
        if algo_var.get() in ("lzma", "zstd", "lz4", "brotli"):
            compress_check.config(state="disabled")
            compress_var.set(True)
        else:
            compress_check.config(state="normal")
    algo_combo.bind("<<ComboboxSelected>>", on_algo_change)
    on_algo_change()

    # ---- Password ----
    ttk.Label(tab, text="Password (ZIP only):").grid(
        row=row, column=0, padx=5, pady=5, sticky="w"
    )
    ttk.Entry(tab, textvariable=password_var, show="*", width=20).grid(
        row=row, column=1, padx=5, pady=5, sticky="w"
    )
    row += 1

    ttk.Checkbutton(tab, text="Legacy ZipCrypto (Windows native)", variable=legacy_var).grid(
        row=row, column=0, columnspan=3, padx=5, pady=5, sticky="w"
    )
    row += 1

    # ---- Log area ----
    log_single = tk.Text(tab, height=8, state="disabled", wrap="word")
    log_single.grid(row=row, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
    row += 1

    # ---- Progress bar ----
    progress_single = ttk.Progressbar(tab, orient="horizontal", length=400, mode="determinate")
    progress_single.grid(row=row, column=0, columnspan=3, padx=5, pady=5)
    row += 1

    # ---- Log helper ----
    def log_single_msg(msg: str):
        log_single.config(state="normal")
        log_single.insert("end", msg + "\n")
        log_single.see("end")
        log_single.config(state="disabled")

    # ---- Generation thread ----
    def generate_single_thread():
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

            def upd(cur: int, total: int):
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

    # ---- Generate button ----
    gen_btn = ttk.Button(
        tab,
        text="Generate",
        command=lambda: threading.Thread(target=generate_single_thread, daemon=True).start()
    )
    gen_btn.grid(row=row, column=0, columnspan=3, pady=10)

    # ---- Configure grid weights ----
    tab.grid_columnconfigure(1, weight=1)
    tab.grid_rowconfigure(row-2, weight=1)  # log area expands

    return tab
