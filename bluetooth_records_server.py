#!/usr/bin/env python3
"""
Bluetooth serial server for water log downloads.

Commands from a Bluetooth serial terminal:
  status    - show file and download mode state
  latest    - send latest CSV row
  download  - send newest weekly CSV, remove DOWNLOAD_MODE, sync, and shut down
  download all - send all weekly CSVs, remove DOWNLOAD_MODE, sync, and shut down
  resume    - remove DOWNLOAD_MODE, sync, and shut down without download
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from water_logger import CSV_FILENAME_PREFIX, DOWNLOAD_MODE_FILENAME, RECORDS_PATH


SERVICE_NAME = "OrangePi Water Records"
SERVER_TIMEOUT_SECONDS = 60 * 60


def weekly_csv_files() -> list[Path]:
    return sorted(RECORDS_PATH.glob(f"{CSV_FILENAME_PREFIX}_*_week_*.csv"))


def latest_csv_path() -> Path | None:
    files = weekly_csv_files()
    if not files:
        return None
    return files[-1]


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
    path = latest_csv_path()
    if path is None:
        return "No CSV file found yet.\n"

    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        return "CSV exists, but no readings are recorded yet.\n"

    return f"File: {path.name}\n" + lines[0] + "\n" + lines[-1] + "\n"


def read_latest_csv() -> str:
    path = latest_csv_path()
    if path is None:
        return "No CSV file found yet.\n"
    return f"FILE {path.name}\n" + path.read_text(encoding="utf-8")


def read_all_csvs() -> str:
    files = weekly_csv_files()
    if not files:
        return "No CSV files found yet.\n"
    parts = []
    for path in files:
        parts.append(f"FILE {path.name}\n{path.read_text(encoding='utf-8')}")
    return "\n\n".join(parts)


def send_text(client, text: str) -> None:
    client.send(text.encode("utf-8"))


def handle_command(client, command: str) -> bool:
    command = command.strip().lower()

    if command == "status":
        files = weekly_csv_files()
        latest = files[-1].name if files else "none"
        total_size = sum(path.stat().st_size for path in files)
        marker_state = "yes" if download_mode_path().exists() else "no"
        send_text(
            client,
            (
                f"Weekly files: {len(files)}\n"
                f"Latest file: {latest}\n"
                f"Total bytes: {total_size}\n"
                f"Download mode: {marker_state}\n"
            ),
        )
        return True

    if command == "latest":
        send_text(client, "BEGIN LATEST\n")
        send_text(client, read_latest_row())
        send_text(client, "END LATEST\n")
        return True

    if command == "download":
        send_text(client, "BEGIN CSV\n")
        send_text(client, read_latest_csv())
        send_text(client, "\nEND CSV\n")
        send_text(client, "Download complete. Resuming normal timed logging.\n")
        remove_download_marker()
        shutdown()
        return False

    if command == "download all":
        send_text(client, "BEGIN ALL CSV\n")
        send_text(client, read_all_csvs())
        send_text(client, "\nEND ALL CSV\n")
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
        send_text(client, "Commands: status, latest, download, download all, resume\n")
        return True

    send_text(client, "Unknown command. Try: status, latest, download, download all, resume\n")
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
    send_text(client, "Orange Pi water records ready. Commands: status, latest, download, download all, resume\n")

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
