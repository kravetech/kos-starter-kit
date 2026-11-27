#!/usr/bin/env python3
"""Install or update a KOS Community vault using a verified release."""
import sys
from pathlib import Path

if __name__ == "__main__":
    if sys.version_info < (3, 10):
        sys.exit("Community guided setup requires Python 3.10 or newer.")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(Path(__file__).resolve().parent / "installer"))
    from setup_flow import main

    sys.exit(main())
