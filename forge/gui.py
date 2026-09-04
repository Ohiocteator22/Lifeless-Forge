# forge/gui.py
import sys
import zipfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
from .core import generate_zip, generate_batch, extract_zip
from .utils import format_size, parse_size_string

def launch_gui():
    root = tk.Tk()
    root.title("Lifeless-Forge – Compression Tool")
    root.geometry("700x650")
    root.resizable(False, False)

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=5, pady=5)

    # ---- Tab 1: Single ----
    tab_single = ttk.Frame(nb)
    nb.add(tab_single, text="Single Generate")

    size_var = tk.IntVar(value=60)
    pattern_var = tk.StringVar(value="A")
    output_var = tk.StringVar(value="compression_demo.zip")
    compress_var = tk.BooleanVar(value=True)
    password_var = tk.StringVar(value="")
    legacy_var = tk.BooleanVar(value=False)
    format_var = tk.StringVar(value="zip")

    row=0
    ttk.Label(tab_single, text="Size (MB):").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    ttk.Scale(tab_single, from_=1, to=1000, orient="horizontal", variable=size_var).grid(row=row, column=1, padx=5, pady=5, sticky="ew")
    ttk.Label(tab_single, textvariable=size_var).grid(row=row, column=2, padx=5, pady=5)
    row+=1

    ttk.Label(tab_single, text="Pattern:").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_single, textvariable=pattern_var, width=10).grid(row=row, column=1, padx=5, pady=5, sticky="w")
    row+=1

    ttk.Label(tab_single, text="Format:").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    format_combo = ttk.Combobox(tab_single, textvariable=format_var, values=["zip", "pptx", "docx", "xlsx"], state="readonly")
    format_combo.grid(row=row, column=1, padx=5, pady=5, sticky="w")
    row+=1

    ttk.Label(tab_single, text="Output:").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_single, textvariable=output_var, width=30).grid(row=row, column=1, padx=5, pady=5, sticky="ew")
    ttk.Button(tab_single, text="Browse", command=lambda: output_var.set(filedialog.asksaveasfilename(defaultextension="."+format_var.get()))).grid(row=row, column=2, padx=5, pady=5)
    row+=1

    ttk.Checkbutton(tab_single, text="Use DEFLATE compression", variable=compress_var).grid(row=row, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    row+=1

    ttk.Label(tab_single, text="Password:").grid(row=row, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_single, textvariable=password_var, show="*", width=20).grid(row=row, column=1, padx=5, pady=5, sticky="w")
    row+=1

    ttk.Checkbutton(tab_single, text="Legacy ZipCrypto (Windows native)", variable=legacy_var).grid(row=row, column=0, columnspan=3, padx=5, pady=5, sticky="w")
    row+=1

    log_single = tk.Text(tab_single, height=8, state="disabled", wrap="word")
    log_single.grid(row=row, column=0, columnspan=3, padx=5, pady=5, sticky="nsew")
    row+=1

    progress_single = ttk.Progressbar(tab_single, orient="horizontal", length=400, mode="determinate")
    progress_single.grid(row=row, column=0, columnspan=3, padx=5, pady=5)
    row+=1

    def log_single_msg(msg):
        log_single.config(state="normal")
        log_single.insert("end", msg + "\n")
        log_single.see("end")
        log_single.config(state="disabled")

    def generate_single_thread():
        gen_btn.config(state="disabled")
        progress_single["value"] = 0
        log_single_msg("Starting generation...")
        try:
            def upd(cur, total):
                progress_single["value"] = (cur/total)*100
                root.update_idletasks()
            stats = generate_zip(
                output=output_var.get(),
                extracted_mb=size_var.get(),
                pattern=pattern_var.get(),
                compression=compress_var.get(),
                password=password_var.get() or None,
                progress_callback=upd,
                legacy_crypto=legacy_var.get(),
                fmt=format_var.get(),
            )
            log_single_msg(f"Created: {stats['output']} ({stats['format'].upper()})")
            log_single_msg(f"Compressed: {format_size(stats['compressed_bytes'])}")
            log_single_msg(f"Extracted:  {format_size(stats['extracted_bytes'])}")
            log_single_msg(f"Ratio: {stats['ratio']:.2f}x")
        except Exception as e:
            log_single_msg(f"Error: {e}")
        finally:
            gen_btn.config(state="normal")
            progress_single["value"] = 0

    gen_btn = ttk.Button(tab_single, text="Generate", command=lambda: threading.Thread(target=generate_single_thread, daemon=True).start())
    gen_btn.grid(row=row, column=0, columnspan=3, pady=10)

    tab_single.grid_columnconfigure(1, weight=1)
    tab_single.grid_rowconfigure(row-2, weight=1)

    # ---- Tab 2: Batch ----
    tab_batch = ttk.Frame(nb)
    nb.add(tab_batch, text="Batch Generate")

    batch_sizes_var = tk.StringVar(value="10, 50, 100, 500")
    batch_pattern_var = tk.StringVar(value="A")
    batch_format_var = tk.StringVar(value="zip")
    batch_output_pattern_var = tk.StringVar(value="batch_{size}.zip")
    batch_compress_var = tk.BooleanVar(value=True)
    batch_password_var = tk.StringVar(value="")
    batch_legacy_var = tk.BooleanVar(value=False)

    br=0
    ttk.Label(tab_batch, text="Sizes (comma-separated):").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_batch, textvariable=batch_sizes_var, width=30).grid(row=br, column=1, padx=5, pady=5, sticky="ew")
    br+=1

    ttk.Label(tab_batch, text="Pattern:").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_batch, textvariable=batch_pattern_var, width=10).grid(row=br, column=1, padx=5, pady=5, sticky="w")
    br+=1

    ttk.Label(tab_batch, text="Format:").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    ttk.Combobox(tab_batch, textvariable=batch_format_var, values=["zip", "pptx", "docx", "xlsx"], state="readonly").grid(row=br, column=1, padx=5, pady=5, sticky="w")
    br+=1

    ttk.Label(tab_batch, text="Output pattern:").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_batch, textvariable=batch_output_pattern_var, width=30).grid(row=br, column=1, padx=5, pady=5, sticky="ew")
    br+=1

    ttk.Checkbutton(tab_batch, text="Use DEFLATE compression", variable=batch_compress_var).grid(row=br, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    br+=1

    ttk.Label(tab_batch, text="Password:").grid(row=br, column=0, padx=5, pady=5, sticky="w")
    ttk.Entry(tab_batch, textvariable=batch_password_var, show="*", width=20).grid(row=br, column=1, padx=5, pady=5, sticky="w")
    br+=1

    ttk.Checkbutton(tab_batch, text="Legacy ZipCrypto", variable=batch_legacy_var).grid(row=br, column=0, columnspan=2, padx=5, pady=5, sticky="w")
    br+=1

    batch_log = tk.Text(tab_batch, height=8, state="disabled", wrap="word")
    batch_log.grid(row=br, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")
    br+=1

    batch_progress_bar = ttk.Progressbar(tab_batch, orient="horizontal", length=400, mode="determinate")
    batch_progress_bar.grid(row=br, column=0, columnspan=2, padx=5, pady=5)
    br+=1

    def log_batch_msg(msg):
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
            for s in size_strs:
                size_mb = parse_size_string(s)
                out_name = batch_output_pattern_var.get().replace("{size}", s).replace("{size_mb}", str(size_mb))
                tasks.append({
                    "size": size_mb,
                    "output": out_name,
                    "pattern": batch_pattern_var.get(),
                    "compression": batch_compress_var.get(),
                    "password": batch_password_var.get() or None,
                    "legacy": batch_legacy_var.get(),
                    "format": fmt,
                })
            if not tasks:
                log_batch_msg("No tasks defined.")
                return
            log_batch_msg(f"Total tasks: {len(tasks)}")
            def batch_progress(current, total, msg):
                batch_progress_bar["value"] = ((current+1) / total) * 100
                root.update_idletasks()
                log_batch_msg(f"[{current+1}/{total}] {msg}")
            results = generate_batch(tasks, progress_callback=batch_progress)
            log_batch_msg("\n=== Summary ===")
            for r in results:
                log_batch_msg(f"{os.path.basename(r['output'])} ({r['format'].upper()}): {format_size(r['extracted_bytes'])} → {format_size(r['compressed_bytes'])} (ratio {r['ratio']:.2f}x)")
        except Exception as e:
            log_batch_msg(f"Error: {e}")
        finally:
            batch_btn.config(state="normal")
            batch_progress_bar["value"] = 0

    batch_btn = ttk.Button(tab_batch, text="Generate Batch", command=lambda: threading.Thread(target=generate_batch_thread, daemon=True).start())
    batch_btn.grid(row=br, column=0, columnspan=2, pady=10)

    tab_batch.grid_columnconfigure(1, weight=1)
    tab_batch.grid_rowconfigure(br-2, weight=1)

    # ---- Tab 3: Extract / Info ----
    tab_extra = ttk.Frame(nb)
    nb.add(tab_extra, text="Extract / Info")

    def do_extract():
        archive = filedialog.askopenfilename(title="Select archive", filetypes=[("All archives", "*.zip *.pptx *.docx *.xlsx"), ("ZIP", "*.zip"), ("PPTX", "*.pptx"), ("DOCX", "*.docx"), ("XLSX", "*.xlsx")])
        if not archive: return
        pwd = simpledialog.askstring("Password", "Enter password:", show='*')
        if pwd is None: return
        try:
            out = extract_zip(archive, pwd)
            messagebox.showinfo("Success", f"Extracted to: {out}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def do_info():
        archive = filedialog.askopenfilename(title="Select archive", filetypes=[("All archives", "*.zip *.pptx *.docx *.xlsx")])
        if not archive: return
        try:
            with zipfile.ZipFile(archive, 'r') as z:
                info = z.infolist()
                total_compressed = sum(f.compress_size for f in info)
                total_extracted = sum(f.file_size for f in info)
                ratio = total_extracted / total_compressed if total_compressed else 0
                msg = (f"Archive: {os.path.basename(archive)}\n"
                       f"Files: {len(info)}\n"
                       f"Compressed: {format_size(total_compressed)}\n"
                       f"Extracted:  {format_size(total_extracted)}\n"
                       f"Ratio: {ratio:.2f}x")
                messagebox.showinfo("Archive Info", msg)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    ttk.Button(tab_extra, text="Extract Archive", command=do_extract).pack(pady=10)
    ttk.Button(tab_extra, text="Show Info", command=do_info).pack(pady=10)

    root.mainloop()
