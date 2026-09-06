
"""
Lifeless-Forge – A ZIP compression tool with high-ratio compression,
password protection, batch generation, and Office formats.
"""


__version__ = "1.2.0"
__author__ = "Lifeless"
from .core import generate_zip, generate_batch, extract_archive
from .utils import format_size, parse_size_string
from .templates import create_pptx_template, create_docx_template, create_xlsx_template
from .config import load_config, save_config, detect_system_theme  # new
