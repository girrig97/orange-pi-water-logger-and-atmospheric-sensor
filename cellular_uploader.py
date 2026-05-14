#!/usr/bin/env python3
"""
Quectel EC25-AU helper for the Orange Pi 5 Max cellular branch.

The EC25-AU should appear as USB serial ports on Linux when connected through a
WWAN USB adapter. The AT command port is often /dev/ttyUSB2, but this can vary.

Optional environment:
  EC25_AT_PORT=/dev/ttyUSB2
  EC25_BAUDRATE=115200
  CELLULAR_UPLOAD_URL=https://example.com/upload
"""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path

from water_logger import CSV_FILENAME_PREFIX, RECORDS_PATH


EC25_AT_PORT = os.environ.get("EC25_AT_PORT", "/dev/ttyUSB2")
EC25_BAUDRATE = int(os.environ.get("EC25_BAUDRATE", "115200"))
CELLULAR_UPLOAD_URL = os.environ.get("CELLULAR_UPLOAD_URL", "")


def weekly_csv_files() -> list[Path]:
    return sorted(RECORDS_PATH.glob(f"{CSV_FILENAME_PREFIX}_*_week_*.csv"))


def latest_csv_path() -> Path | None:
    files = weekly_csv_files()
    if not files:
        return None
    return files[-1]


def at_command(serial_port, command: str, wait_seconds: float = 0.5) -> str:
    serial_port.reset_input_buffer()
    serial_port.write((command + "\r").encode("ascii"))
    serial_port.flush()
    time.sleep(wait_seconds)
    return serial_port.read(serial_port.in_waiting or 1).decode("utf-8", errors="ignore").strip()


def modem_status() -> str:
    try:
        import serial
    except ImportError:
        return "pyserial_missing"

    try:
        with serial.Serial(EC25_AT_PORT, EC25_BAUDRATE, timeout=1) as serial_port:
            commands = ["AT", "AT+CPIN?", "AT+CSQ", "AT+COPS?", "AT+QNWINFO"]
            return "\n".join(f"{command}: {at_command(serial_port, command)}" for command in commands)
    except OSError as exc:
        return f"ec25_at_port_unavailable: {exc}"


def upload_latest() -> int:
    path = latest_csv_path()
    if path is None:
        print("No weekly CSV file found to upload.")
        return 1
    if not CELLULAR_UPLOAD_URL:
        print("CELLULAR_UPLOAD_URL is not set; skipping cellular upload.")
        return 0

    print(modem_status())
    result = subprocess.run(
        [
            "curl",
            "--fail",
            "--show-error",
            "--silent",
            "--connect-timeout",
            "30",
            "--max-time",
            "180",
            "-F",
            f"file=@{path}",
            CELLULAR_UPLOAD_URL,
        ],
        check=False,
    )
    if result.returncode == 0:
        print(f"Uploaded {path.name}")
    else:
        print(f"Upload failed for {path.name}")
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Check EC25-AU status or upload latest water CSV.")
    parser.add_argument("--status", action="store_true", help="Print EC25-AU AT command status.")
    parser.add_argument("--upload-latest", action="store_true", help="Upload newest weekly CSV with curl.")
    args = parser.parse_args()

    if args.upload_latest:
        return upload_latest()

    print(modem_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
