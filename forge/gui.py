# forge/gui.py
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from .core import generate_zip, generate_batch, extract_zip
from .utils import format_size, parse_size_string

def launch_gui():
    # ... (your full GUI code)
