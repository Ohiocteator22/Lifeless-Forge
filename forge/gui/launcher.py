# forge/gui/launcher.py
import sys
import os
import tkinter as tk
from tkinter import ttk

from forge.config import load_config, save_config, detect_system_theme
from forge.gui.theme import get_colors, apply_custom_colors
from forge.gui.tab_single import build_tab_single
from forge.gui.tab_batch import build_tab_batch
from forge.gui.tab_extract import build_tab_extract

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
    DND_FILES = None
    TkinterDnD = None


def launch_gui():
    """Launch the Tkinter GUI."""
    config = load_config()
    dark_mode_pref = config.get("dark_mode", None)
    if dark_mode_pref is None:
        dark_mode = detect_system_theme()
        if dark_mode is None:
            dark_mode = False
    else:
        dark_mode = dark_mode_pref

    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    root.title("Lifeless-Forge – Compression Tool")
    root.geometry("760x720")
    root.resizable(False, False)

    # Set icon
    try:
        icon_path = resource_path("app_icon.ico")
        root.iconbitmap(icon_path)
        root.iconbitmap(default=icon_path)
    except Exception:
        pass

    # Menu bar
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

    # Apply Sun Valley theme
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

    def toggle_dark_mode():
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

    # Notebook
    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=5, pady=5)

    # Build tabs – pass DND_FILES constant
    build_tab_single(nb, root, dark_mode, HAS_DND, DND_FILES)
    build_tab_batch(nb, root, dark_mode, HAS_DND, DND_FILES)
    build_tab_extract(nb, root, dark_mode, HAS_DND, DND_FILES)

    apply_custom_colors(root, get_colors(dark_mode))
    root.mainloop()


def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
