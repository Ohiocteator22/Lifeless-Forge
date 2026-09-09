# forge/gui/theme.py
import tkinter as tk

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
