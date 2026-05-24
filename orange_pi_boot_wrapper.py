#!/usr/bin/env python3
"""
Boot wrapper for Pico-powered Orange Pi logging.

Normal mode:
  - Log one reading.
  - Shut down.

Download/pairing mode:
  - Start Bluetooth record server before taking an extra download-mode reading.
  - Pairing mode also makes Bluetooth discoverable and pairable.
  - Send settime from a phone, which logs a fresh row with corrected time.
  - After a successful Bluetooth download, remove DOWNLOAD_MODE and shut down.
"""

from __future__ import annotations

import subprocess
import sys
import time
import os
from pathlib import Path

from water_logger import DOWNLOAD_MODE_FILENAME, PAIRING_MODE_FILENAME, PICO_SERIAL_PORT, RECORDS_PATH, log_once


DOWNLOAD_REQUEST_SECONDS = 3
CELLULAR_UPLOAD_ENABLED = os.environ.get("CELLULAR_UPLOAD_ENABLED", "0") == "1"
CELLULAR_REPORTING_ENABLED = os.environ.get("CELLULAR_REPORTING_ENABLED", "0") == "1"


def shutdown() -> None:
    subprocess.run(["sync"], check=False)
    subprocess.run(["shutdown", "-h", "now"], check=False)


def pico_requested_mode() -> str | None:
    """Return the mode requested by the Pico button controller."""
    try:
        import serial
    except ImportError:
        return None

    deadline = time.monotonic() + DOWNLOAD_REQUEST_SECONDS
    try:
        with serial.Serial(PICO_SERIAL_PORT, 9600, timeout=1) as serial_port:
            while time.monotonic() < deadline:
                line = serial_port.readline().decode("utf-8", errors="ignore").strip()
                if line == "DOWNLOAD_MODE=1":
                    return "download"
                if line == "PAIRING_MODE=1":
                    return "pairing"
    except OSError:
        return None

    return None


def main() -> int:
    download_mode_path = RECORDS_PATH / DOWNLOAD_MODE_FILENAME
    pairing_mode_path = RECORDS_PATH / PAIRING_MODE_FILENAME
    requested_mode = pico_requested_mode()

    if download_mode_path.exists() or pairing_mode_path.exists() or requested_mode:
        RECORDS_PATH.mkdir(parents=True, exist_ok=True)
        download_mode_path.touch()
        if requested_mode == "pairing":
            pairing_mode_path.touch()
        elif requested_mode == "download" and pairing_mode_path.exists():
            pairing_mode_path.unlink()
        server = Path(__file__).with_name("bluetooth_records_server.py")
        result = subprocess.run([sys.executable, str(server)], check=False)
        return result.returncode

    log_once()

    if CELLULAR_REPORTING_ENABLED:
        reporter = Path(__file__).with_name("cellular_uploader.py")
        subprocess.run([sys.executable, str(reporter), "--report"], check=False)

    if CELLULAR_UPLOAD_ENABLED:
        uploader = Path(__file__).with_name("cellular_uploader.py")
        subprocess.run([sys.executable, str(uploader), "--upload-latest"], check=False)

    shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
