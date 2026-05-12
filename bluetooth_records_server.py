#!/usr/bin/env python3
"""
Bluetooth serial server for water log downloads.

Commands from a Bluetooth serial terminal:
  status    - show file and download mode state
  latest    - send latest CSV row
  download  - send full CSV, remove DOWNLOAD_MODE, sync, and shut down
  resume    - remove DOWNLOAD_MODE, sync, and shut down without download
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from water_logger import CSV_FILENAME, DOWNLOAD_MODE_FILENAME, RECORDS_PATH


SERVICE_NAME = "OrangePi Water Records"
SERVER_TIMEOUT_SECONDS = 60 * 60


def csv_path() -> Path:
    return RECORDS_PATH / CSV_FILENAME


def download_mode_path() -> Path:
    return RECORDS_PATH / DOWNLOAD_MODE_FILENAME


def remove_download_marker() -> None:
    marker = download_mode_path()
    if marker.exists():
        marker.unlink()


def shutdown() -> None:
    subprocess.run(["sync"], check=False)
    subprocess.run(["shutdown", "-h", "now"], check=False)


def read_latest_row() -> str:
    path = csv_path()
    if not path.exists():
        return "No CSV file found yet.\n"

    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        return "CSV exists, but no readings are recorded yet.\n"

    return lines[0] + "\n" + lines[-1] + "\n"


def read_full_csv() -> str:
    path = csv_path()
    if not path.exists():
        return "No CSV file found yet.\n"
    return path.read_text(encoding="utf-8")


def send_text(client, text: str) -> None:
    client.send(text.encode("utf-8"))


def handle_command(client, command: str) -> bool:
    command = command.strip().lower()

    if command == "status":
        path = csv_path()
        size = path.stat().st_size if path.exists() else 0
        marker_state = "yes" if download_mode_path().exists() else "no"
        send_text(
            client,
            f"CSV: {path}\nSize bytes: {size}\nDownload mode: {marker_state}\n",
        )
        return True

    if command == "latest":
        send_text(client, "BEGIN LATEST\n")
        send_text(client, read_latest_row())
        send_text(client, "END LATEST\n")
        return True

    if command == "download":
        send_text(client, "BEGIN CSV\n")
        send_text(client, read_full_csv())
        send_text(client, "\nEND CSV\n")
        send_text(client, "Download complete. Resuming normal timed logging.\n")
        remove_download_marker()
        shutdown()
        return False

    if command == "resume":
        send_text(client, "Download mode cleared. Resuming normal timed logging.\n")
        remove_download_marker()
        shutdown()
        return False

    if command in {"help", "?"}:
        send_text(client, "Commands: status, latest, download, resume\n")
        return True

    send_text(client, "Unknown command. Try: status, latest, download, resume\n")
    return True


def main() -> int:
    try:
        import bluetooth
    except ImportError:
        print("Bluetooth Python package missing. Install python3-bluez or PyBluez.")
        return 1

    server = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    server.bind(("", bluetooth.PORT_ANY))
    server.listen(1)
    server.settimeout(SERVER_TIMEOUT_SECONDS)
    port = server.getsockname()[1]

    bluetooth.advertise_service(
        server,
        SERVICE_NAME,
        service_classes=[bluetooth.SERIAL_PORT_CLASS],
        profiles=[bluetooth.SERIAL_PORT_PROFILE],
    )

    print(f"Bluetooth record server listening on RFCOMM channel {port}")

    try:
        client, address = server.accept()
    except Exception as exc:
        if "timed out" not in str(exc).lower() and "timeout" not in str(exc).lower():
            raise
        print("Bluetooth download timeout reached; staying in download mode.")
        server.close()
        return 0

    print(f"Bluetooth client connected: {address}")
    send_text(client, "Orange Pi water records ready. Commands: status, latest, download, resume\n")

    keep_running = True
    while keep_running:
        data = client.recv(1024)
        if not data:
            break
        command = data.decode("utf-8", errors="ignore")
        keep_running = handle_command(client, command)

    client.close()
    server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
