"""Entrypoint module for running tidy-downloads as `python3 -m tidy_downloads`."""

import sys
from .cli import main

if __name__ == "__main__":
    sys.exit(main())
