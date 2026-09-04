# forge/cli.py
import argparse
import sys
import json
from .core import generate_zip, generate_batch, extract_zip, cli_info as core_info
from .utils import parse_size_string, get_progress_printer

def cli_generate(args):
    # ...

def cli_batch(args):
    # ...

def cli_extract(args):
    # ...

def cli_info(args):
    # or just call core_info

def setup_cli_parser():
    # ...
