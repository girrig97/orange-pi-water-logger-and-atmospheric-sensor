#!/usr/bin/env python3
"""
Boot wrapper for Pico-powered Orange Pi logging.

Normal mode:
  - Log one reading.
  - Shut down.

Download mode:
  - Start Bluetooth record server before taking an extra download-mode reading.
  - Send settime from a phone, which logs a fresh row with corrected time.
  - After a successful Bluetooth download, remove DOWNLOAD_MODE and shut down.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from water_logger import DOWNLOAD_MODE_FILENAME, PICO_SERIAL_PORT, RECORDS_PATH, log_once


DOWNLOAD_REQUEST_SECONDS = 12


def shutdown() -> None:
    subprocess.run(["sync"], check=False)
    subprocess.run(["shutdown", "-h", "now"], check=False)


def pico_requested_download() -> bool:
    """Return True when the Pico button controller requests download mode."""
    try:
        import serial
    except ImportError:
        return False

    deadline = time.monotonic() + DOWNLOAD_REQUEST_SECONDS
    try:
        with serial.Serial(PICO_SERIAL_PORT, 9600, timeout=1) as serial_port:
            while time.monotonic() < deadline:
                line = serial_port.readline().decode("utf-8", errors="ignore").strip()
                if line == "DOWNLOAD_MODE=1":
                    return True
    except OSError:
        return False

    return False


def main() -> int:
    download_mode_path = RECORDS_PATH / DOWNLOAD_MODE_FILENAME

    if download_mode_path.exists() or pico_requested_download():
        RECORDS_PATH.mkdir(parents=True, exist_ok=True)
        download_mode_path.touch()
        server = Path(__file__).with_name("bluetooth_records_server.py")
        result = subprocess.run([sys.executable, str(server)], check=False)
        return result.returncode

    log_once()

    shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
