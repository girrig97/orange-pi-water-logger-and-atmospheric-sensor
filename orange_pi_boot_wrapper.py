#!/usr/bin/env python3
"""
Boot wrapper for Pico-powered Orange Pi logging.

Normal mode:
  - Log one reading.
  - Shut down.

Download mode:
  - Log one reading.
  - Start Bluetooth record server.
  - After a successful Bluetooth download, remove DOWNLOAD_MODE and shut down.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from water_logger import CSV_FILENAME, DOWNLOAD_MODE_FILENAME, RECORDS_PATH, log_once


def shutdown() -> None:
    subprocess.run(["sync"], check=False)
    subprocess.run(["shutdown", "-h", "now"], check=False)


def main() -> int:
    csv_path = RECORDS_PATH / CSV_FILENAME
    download_mode_path = RECORDS_PATH / DOWNLOAD_MODE_FILENAME

    log_once(csv_path)

    if not download_mode_path.exists():
        shutdown()
        return 0

    server = Path(__file__).with_name("bluetooth_records_server.py")
    result = subprocess.run([sys.executable, str(server)], check=False)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
