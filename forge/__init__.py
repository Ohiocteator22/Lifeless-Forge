# forge/__init__.py
__version__ = "1.1.6"
__all__ = ["cli", "gui", "core", "templates", "utils", "config"]

# Explicitly import submodules to make PyInstaller see them
from . import cli
from . import gui
from . import core
from . import templates
from . import utils
from . import config
