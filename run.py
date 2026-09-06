# run.py
import sys
import os

# Add the current directory to sys.path so that 'forge' is found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from forge.__main__ import main

if __name__ == "__main__":
    main()
