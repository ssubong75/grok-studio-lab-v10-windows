#!/usr/bin/env python3
"""Launch Grok Studio without a visible console on Windows."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "grok_studio_data"
LOG_DIR = DATA_DIR / "logs"
LOG_FILE = LOG_DIR / "grok_studio.log"


def main() -> int:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ["GROK_STUDIO_DATA_DIR"] = str(DATA_DIR)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8", buffering=1) as log:
        sys.stdout = log
        sys.stderr = log
        try:
            from grok_studio import main as run_studio

            return run_studio(["--host", "127.0.0.1", "--port", "8765", "--open"])
        except Exception:
            traceback.print_exc(file=log)
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
