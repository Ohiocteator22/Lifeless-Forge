# forge/__main__.py
import sys
from forge.cli import setup_cli_parser
from forge.gui import launch_gui

def main():
    if len(sys.argv) == 1:
        launch_gui()
        return
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
