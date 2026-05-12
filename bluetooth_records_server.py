#!/usr/bin/env python3
"""
Bluetooth serial server for water log downloads.

Commands from a Bluetooth serial terminal:
  status    - show file and download mode state
  summary   - show file count and total record count
  times     - list all recorded timestamps
  latest    - send latest CSV row
  settime ISO-8601 - set Orange Pi system time, then log a fresh reading
  log       - log one fresh reading using current Orange Pi time
  download  - send newest weekly CSV, remove DOWNLOAD_MODE, sync, and shut down
  download all - send all weekly CSVs, remove DOWNLOAD_MODE, sync, and shut down
  resume    - remove DOWNLOAD_MODE, sync, and shut down without download
"""

from __future__ import annotations

import subprocess
import csv
from datetime import datetime, timezone
from pathlib import Path

from water_logger import CSV_FILENAME_PREFIX, DOWNLOAD_MODE_FILENAME, RECORDS_PATH, log_once


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


def current_time_text() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def set_system_time(time_text: str) -> str:
    normalized = time_text.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        new_time = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("Use ISO time like 2026-05-12T14:30:00+10:00") from exc

    if new_time.tzinfo is None:
        raise ValueError("Include timezone offset, for example +10:00")

    epoch_seconds = int(new_time.timestamp())
    subprocess.run(["date", "-u", "-s", f"@{epoch_seconds}"], check=True)
    subprocess.run(["hwclock", "-w"], check=False)
    return datetime.fromtimestamp(epoch_seconds, timezone.utc).isoformat(timespec="seconds")


def log_fresh_reading() -> str:
    path = log_once()
    return f"Logged fresh reading to {path.name}\n"


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


def read_record_times() -> list[str]:
    timestamps = []
    for path in weekly_csv_files():
        with path.open("r", newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                timestamp = row.get("timestamp")
                if timestamp:
                    timestamps.append(timestamp)
    return timestamps


def read_summary() -> str:
    files = weekly_csv_files()
    timestamps = read_record_times()
    latest = timestamps[-1] if timestamps else "none"
    return (
        f"Weekly files: {len(files)}\n"
        f"Total records: {len(timestamps)}\n"
        f"Latest record: {latest}\n"
    )


def read_times_text() -> str:
    timestamps = read_record_times()
    if not timestamps:
        return "No records found yet.\n"
    return "\n".join(timestamps) + "\n"


def send_text(client, text: str) -> None:
    client.send(text.encode("utf-8"))


def handle_command(client, command: str) -> bool:
    raw_command = command.strip()
    command = raw_command.lower()

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
                f"Orange Pi UTC time: {current_time_text()}\n"
            ),
        )
        return True

    if command == "latest":
        send_text(client, "BEGIN LATEST\n")
        send_text(client, read_latest_row())
        send_text(client, "END LATEST\n")
        return True

    if command == "summary":
        send_text(client, "BEGIN SUMMARY\n")
        send_text(client, read_summary())
        send_text(client, "END SUMMARY\n")
        return True

    if command == "times":
        send_text(client, "BEGIN TIMES\n")
        send_text(client, read_times_text())
        send_text(client, "END TIMES\n")
        return True

    if command.startswith("settime "):
        try:
            utc_time = set_system_time(raw_command.split(" ", 1)[1])
            send_text(client, f"Time set. Orange Pi UTC time: {utc_time}\n")
            send_text(client, log_fresh_reading())
        except Exception as exc:
            send_text(client, f"Time sync failed: {exc}\n")
        return True

    if command == "log":
        try:
            send_text(client, log_fresh_reading())
        except Exception as exc:
            send_text(client, f"Log failed: {exc}\n")
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
        send_text(client, "Commands: status, summary, times, latest, settime <iso>, log, download, download all, resume\n")
        return True

    send_text(client, "Unknown command. Try: status, summary, times, latest, settime <iso>, log, download, download all, resume\n")
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
    send_text(client, "Orange Pi water records ready. Commands: status, summary, times, latest, settime <iso>, log, download, download all, resume\n")

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
