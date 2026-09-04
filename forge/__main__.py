# forge/__main__.py
import sys
from .cli import setup_cli_parser
from .gui import launch_gui

def main():
    # If no arguments, launch GUI
    if len(sys.argv) == 1:
        launch_gui()
        return
    # If --gui present, launch GUI (even with other args)
    if "--gui" in sys.argv:
        launch_gui()
        return

    parser = setup_cli_parser()
    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
