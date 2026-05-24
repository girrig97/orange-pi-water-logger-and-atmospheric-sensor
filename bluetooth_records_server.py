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
  live      - stream unsaved live readings every 5 seconds
  stop      - stop live streaming
  sms       - show alert SMS recipient numbers
  setsms numbers - set alert SMS recipients, comma separated
  clearsms  - clear alert SMS recipients
  resetbaseline - clear sensor failure baseline after repair/reconfiguration
  signal    - show EC25-AU network generation and signal level
  testsms   - send a test SMS to configured alert recipients
  download  - send newest weekly CSV, remove DOWNLOAD_MODE, sync, and shut down
  download all - send all weekly CSVs, remove DOWNLOAD_MODE, sync, and shut down
  resume    - remove DOWNLOAD_MODE, sync, and shut down without download
"""

from __future__ import annotations

import subprocess
import csv
import time
from datetime import datetime, timezone
from pathlib import Path

from cellular_config import get_sms_numbers, set_sms_numbers, sms_numbers_text
from cellular_uploader import modem_signal_text, send_test_sms
from water_logger import CSV_FILENAME_PREFIX, DOWNLOAD_MODE_FILENAME, PAIRING_MODE_FILENAME, RECORDS_PATH, collect_reading, log_once


SERVICE_NAME = "OrangePi Water Records"
SERVER_TIMEOUT_SECONDS = 60 * 60
LIVE_INTERVAL_SECONDS = 5


def weekly_csv_files() -> list[Path]:
    return sorted(RECORDS_PATH.glob(f"{CSV_FILENAME_PREFIX}_*_week_*.csv"))


def latest_csv_path() -> Path | None:
    files = weekly_csv_files()
    if not files:
        return None
    return files[-1]


def download_mode_path() -> Path:
    return RECORDS_PATH / DOWNLOAD_MODE_FILENAME


def pairing_mode_path() -> Path:
    return RECORDS_PATH / PAIRING_MODE_FILENAME


def remove_mode_markers() -> None:
    for marker in (download_mode_path(), pairing_mode_path()):
        if marker.exists():
            marker.unlink()


def bluetoothctl(*args: str) -> None:
    try:
        subprocess.run(["bluetoothctl", *args], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        pass


def set_pairing_window(enabled: bool) -> None:
    state = "on" if enabled else "off"
    bluetoothctl("power", "on")
    if enabled:
        bluetoothctl("agent", "NoInputNoOutput")
        bluetoothctl("default-agent")
        bluetoothctl("pairable-timeout", "0")
        bluetoothctl("discoverable-timeout", "0")
    bluetoothctl("pairable", state)
    bluetoothctl("discoverable", state)


def shutdown() -> None:
    subprocess.run(["sync"], check=False)
    subprocess.run(["shutdown", "-h", "now"], check=False)


def finish_client_transfer(client) -> None:
    try:
        client.shutdown(1)
    except Exception:
        pass
    time.sleep(2)


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


def live_reading_text() -> str:
    reading = collect_reading()

    def value_or_dash(value) -> str:
        return "--" if value is None else str(value)

    return (
        "LIVE "
        f"time={reading.timestamp}, "
        f"water_temp_c={value_or_dash(reading.temperature_c)}, "
        f"ph={value_or_dash(reading.ph)}, "
        f"tds_ppm={value_or_dash(reading.tds_ppm)}, "
        f"ec_ms_cm={value_or_dash(reading.ec_ms_cm)}, "
        f"turbidity_ntu={value_or_dash(reading.turbidity_ntu)}, "
        f"orp_mv={value_or_dash(reading.orp_mv)}, "
        f"do_mg_l={value_or_dash(reading.dissolved_oxygen_mg_l)}, "
        f"nh4_mg_l={value_or_dash(reading.ammonium_nh4_mg_l)}, "
        f"nh3_mg_l={value_or_dash(reading.toxic_ammonia_nh3_mg_l)}, "
        f"air_temp_c={value_or_dash(reading.air_temperature_c)}, "
        f"humidity_percent={value_or_dash(reading.air_humidity_percent)}, "
        f"pressure_hpa={value_or_dash(reading.air_pressure_hpa)}, "
        f"condition={reading.water_condition}"
        "\n"
    )


def handle_command(client, command: str) -> str:
    raw_command = command.strip()
    command = raw_command.lower()

    if command == "status":
        files = weekly_csv_files()
        latest = files[-1].name if files else "none"
        total_size = sum(path.stat().st_size for path in files)
        marker_state = "yes" if download_mode_path().exists() else "no"
        pairing_state = "yes" if pairing_mode_path().exists() else "no"
        send_text(
            client,
            (
                f"Weekly files: {len(files)}\n"
                f"Latest file: {latest}\n"
                f"Total bytes: {total_size}\n"
                f"Download mode: {marker_state}\n"
                f"Pairing mode: {pairing_state}\n"
                f"Alert SMS numbers: {sms_numbers_text()}\n"
                f"Orange Pi UTC time: {current_time_text()}\n"
            ),
        )
        return "continue"

    if command == "latest":
        send_text(client, "BEGIN LATEST\n")
        send_text(client, read_latest_row())
        send_text(client, "END LATEST\n")
        return "continue"

    if command == "summary":
        send_text(client, "BEGIN SUMMARY\n")
        send_text(client, read_summary())
        send_text(client, "END SUMMARY\n")
        return "continue"

    if command == "times":
        send_text(client, "BEGIN TIMES\n")
        send_text(client, read_times_text())
        send_text(client, "END TIMES\n")
        return "continue"

    if command.startswith("settime "):
        try:
            utc_time = set_system_time(raw_command.split(" ", 1)[1])
            send_text(client, f"Time set. Orange Pi UTC time: {utc_time}\n")
            send_text(client, log_fresh_reading())
        except Exception as exc:
            send_text(client, f"Time sync failed: {exc}\n")
        return "continue"

    if command == "log":
        try:
            send_text(client, log_fresh_reading())
        except Exception as exc:
            send_text(client, f"Log failed: {exc}\n")
        return "continue"

    if command == "download":
        send_text(client, "BEGIN CSV\n")
        send_text(client, read_latest_csv())
        send_text(client, "\nEND CSV\n")
        send_text(client, "Download complete. Resuming normal timed logging.\n")
        remove_mode_markers()
        set_pairing_window(False)
        finish_client_transfer(client)
        shutdown()
        return "shutdown"

    if command == "download all":
        send_text(client, "BEGIN ALL CSV\n")
        send_text(client, read_all_csvs())
        send_text(client, "\nEND ALL CSV\n")
        send_text(client, "Download complete. Resuming normal timed logging.\n")
        remove_mode_markers()
        set_pairing_window(False)
        finish_client_transfer(client)
        shutdown()
        return "shutdown"

    if command == "resume":
        send_text(client, "Download/pairing mode cleared. Resuming normal timed logging.\n")
        remove_mode_markers()
        set_pairing_window(False)
        finish_client_transfer(client)
        shutdown()
        return "shutdown"

    if command == "live":
        send_text(client, "BEGIN LIVE\n")
        send_text(client, live_reading_text())
        return "live"

    if command == "stop":
        send_text(client, "END LIVE\n")
        return "continue"

    if command == "sms":
        send_text(client, f"Alert SMS numbers: {sms_numbers_text()}\n")
        return "continue"

    if command == "clearsms":
        set_sms_numbers("")
        send_text(client, "Alert SMS numbers cleared.\n")
        return "continue"

    if command == "setsms" or command.startswith("setsms "):
        try:
            numbers_text = raw_command.split(" ", 1)[1] if " " in raw_command else ""
            numbers = set_sms_numbers(numbers_text)
            if numbers:
                send_text(client, "Alert SMS numbers saved: " + ",".join(numbers) + "\n")
            else:
                send_text(client, "Alert SMS numbers cleared.\n")
        except ValueError as exc:
            send_text(client, f"Could not save SMS numbers: {exc}\n")
        return "continue"

    if command == "resetbaseline":
        state_path = RECORDS_PATH / "cellular_alert_state.json"
        try:
            if state_path.exists():
                state_path.unlink()
            send_text(client, "Sensor baseline reset. The next report will rebuild it from recent ok rows.\n")
        except OSError as exc:
            send_text(client, f"Could not reset sensor baseline: {exc}\n")
        return "continue"

    if command == "signal":
        send_text(client, "BEGIN SIGNAL\n")
        send_text(client, modem_signal_text())
        send_text(client, "END SIGNAL\n")
        return "continue"

    if command == "testsms":
        result = send_test_sms()
        if result == 0:
            send_text(client, "Test SMS sent to configured alert recipients.\n")
        else:
            send_text(client, "Test SMS failed or no alert recipients are configured.\n")
        return "continue"

    if command in {"help", "?"}:
        send_text(client, "Commands: status, summary, times, latest, settime <iso>, log, live, stop, sms, setsms <numbers>, clearsms, resetbaseline, signal, testsms, download, download all, resume\n")
        return "continue"

    send_text(client, "Unknown command. Try: status, summary, times, latest, settime <iso>, log, live, stop, sms, setsms <numbers>, clearsms, resetbaseline, signal, testsms, download, download all, resume\n")
    return "continue"


def main() -> int:
    try:
        import bluetooth
    except ImportError:
        print("Bluetooth Python package missing. Install python3-bluez or PyBluez.")
        return 1

    pairing_requested = pairing_mode_path().exists()
    set_pairing_window(pairing_requested)

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
    if pairing_requested:
        print("Bluetooth pairing mode enabled: adapter is discoverable and pairable.")

    try:
        client, address = server.accept()
    except Exception as exc:
        if "timed out" not in str(exc).lower() and "timeout" not in str(exc).lower():
            raise
        print("Bluetooth download timeout reached; staying in download mode.")
        server.close()
        return 0

    print(f"Bluetooth client connected: {address}")
    if pairing_requested:
        send_text(client, "Pairing mode active. Bluetooth is discoverable and pairable.\n")
    send_text(client, "Orange Pi water records ready. Commands: status, summary, times, latest, settime <iso>, log, live, stop, sms, setsms <numbers>, clearsms, resetbaseline, signal, testsms, download, download all, resume\n")

    live_mode = False
    client.settimeout(1)
    last_live_at = 0.0

    while True:
        try:
            data = client.recv(1024)
        except Exception as exc:
            if "timed out" in str(exc).lower() or "timeout" in str(exc).lower():
                data = None
            else:
                break

        if data == b"":
            break

        if data:
            command = data.decode("utf-8", errors="ignore")
            result = handle_command(client, command)
            if result == "shutdown":
                break
            live_mode = result == "live"

        if live_mode:
            now = datetime.now(timezone.utc).timestamp()
            if now - last_live_at >= LIVE_INTERVAL_SECONDS:
                send_text(client, live_reading_text())
                last_live_at = now

    client.close()
    server.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
