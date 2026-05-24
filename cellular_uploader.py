#!/usr/bin/env python3
"""
Quectel EC25-AU helper for the Orange Pi 5 Max cellular branch.

The EC25-AU should appear as USB serial ports on Linux when connected through a
WWAN USB adapter. The AT command port is often /dev/ttyUSB2, but this can vary.

Optional environment:
  EC25_AT_PORT=/dev/ttyUSB2
  EC25_BAUDRATE=115200
  CELLULAR_UPLOAD_URL=https://example.com/upload
  CELLULAR_STATUS_URL=https://example.com/status
  ALERT_SMS_NUMBERS=+61400111222,+61400999888
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

from alert_manager import build_report
from cellular_config import get_sms_numbers
from water_logger import CSV_FILENAME_PREFIX, RECORDS_PATH


EC25_AT_PORT = os.environ.get("EC25_AT_PORT", "/dev/ttyUSB2")
EC25_BAUDRATE = int(os.environ.get("EC25_BAUDRATE", "115200"))
CELLULAR_UPLOAD_URL = os.environ.get("CELLULAR_UPLOAD_URL", "")
CELLULAR_STATUS_URL = os.environ.get("CELLULAR_STATUS_URL", "")


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


def send_sms(number: str, message: str) -> str:
    try:
        import serial
    except ImportError:
        return "pyserial_missing"

    try:
        with serial.Serial(EC25_AT_PORT, EC25_BAUDRATE, timeout=2) as serial_port:
            at_command(serial_port, "AT")
            at_command(serial_port, "AT+CMGF=1")
            serial_port.write((f'AT+CMGS="{number}"\r').encode("ascii"))
            serial_port.flush()
            time.sleep(0.5)
            serial_port.write(message[:1500].encode("utf-8", errors="ignore") + b"\x1a")
            serial_port.flush()
            time.sleep(5)
            return serial_port.read(serial_port.in_waiting or 1).decode("utf-8", errors="ignore").strip()
    except OSError as exc:
        return f"ec25_sms_failed: {exc}"


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


def network_generation(qnwinfo_response: str, csq_value: int | None) -> str:
    text = qnwinfo_response.upper()
    if "LTE" in text:
        return "4G"
    if any(token in text for token in ("WCDMA", "UMTS", "HSPA", "CDMA", "EVDO")):
        return "3G"
    if any(token in text for token in ("GSM", "GPRS", "EDGE")):
        return "2G"
    if csq_value is None or csq_value == 99 or csq_value <= 0:
        return "no signal"
    return "signal, network type unknown"


def parse_csq(csq_response: str) -> tuple[int | None, int | None, int | None]:
    match = re.search(r"\+CSQ:\s*(\d+),", csq_response)
    if not match:
        return None, None, None
    csq = int(match.group(1))
    if csq == 99:
        return csq, None, None
    dbm = -113 + (2 * csq)
    percent = max(0, min(100, round(csq / 31 * 100)))
    return csq, dbm, percent


def modem_signal_report() -> dict[str, str | int | None]:
    try:
        import serial
    except ImportError:
        return {"network": "unknown", "signal": "pyserial_missing", "csq": None, "dbm": None, "percent": None, "operator": "--", "raw": "pyserial_missing"}

    try:
        with serial.Serial(EC25_AT_PORT, EC25_BAUDRATE, timeout=1) as serial_port:
            at_command(serial_port, "AT")
            csq_response = at_command(serial_port, "AT+CSQ")
            qnwinfo_response = at_command(serial_port, "AT+QNWINFO")
            cops_response = at_command(serial_port, "AT+COPS?")
    except OSError as exc:
        return {"network": "no signal", "signal": f"ec25_at_port_unavailable: {exc}", "csq": None, "dbm": None, "percent": None, "operator": "--", "raw": str(exc)}

    csq, dbm, percent = parse_csq(csq_response)
    network = network_generation(qnwinfo_response, csq)
    signal = "no signal" if percent is None else f"{percent}% ({dbm} dBm)"
    return {
        "network": network,
        "signal": signal,
        "csq": csq,
        "dbm": dbm,
        "percent": percent,
        "operator": cops_response,
        "raw": qnwinfo_response,
    }


def modem_signal_text() -> str:
    report = modem_signal_report()
    return (
        f"Network: {report['network']}\n"
        f"Cell signal: {report['signal']}\n"
        f"CSQ: {report['csq'] if report['csq'] is not None else '--'}\n"
        f"Operator: {report.get('operator') or '--'}\n"
        f"Radio info: {report.get('raw') or '--'}\n"
    )


def send_test_sms() -> int:
    numbers = get_sms_numbers()
    if not numbers:
        print("No alert SMS numbers configured.")
        return 1
    failures = 0
    message = "Water logger test SMS: cellular alert service is working."
    for number in numbers:
        result = send_sms(number, message)
        print(f"Test SMS to {number}: {result}")
        if "ERROR" in result or "failed" in result or "missing" in result:
            failures += 1
    return 1 if failures else 0


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


def post_status(report: dict) -> int:
    if not CELLULAR_STATUS_URL:
        print("CELLULAR_STATUS_URL is not set; skipping server status update.")
        return 0
    payload = json.dumps(report).encode("utf-8")
    request = urllib.request.Request(
        CELLULAR_STATUS_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "orange-pi-water-logger/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            print(f"Server status update HTTP {response.status}")
            return 0 if 200 <= response.status < 300 else 1
    except OSError as exc:
        print(f"Server status update failed: {exc}")
        return 1


def send_sms_reports(report: dict) -> int:
    alert_sms_numbers = get_sms_numbers()
    if not alert_sms_numbers:
        print("ALERT_SMS_NUMBERS is not set; skipping SMS.")
        return 0

    messages: list[str] = []
    if report.get("daily_status_due"):
        messages.append("Daily " + report["summary"])
    for item in report.get("sms_alerts", []):
        messages.append(f"{item['severity'].upper()}: {item['message']}")

    if not messages:
        print("No daily status or unsent alerts due for SMS.")
        return 0

    failures = 0
    for number in alert_sms_numbers:
        for message in messages:
            result = send_sms(number, message)
            print(f"SMS to {number}: {result}")
            if "ERROR" in result or "failed" in result or "missing" in result:
                failures += 1
    return 1 if failures else 0


def report_status() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    server_result = post_status(report)
    sms_result = send_sms_reports(report)
    return 1 if server_result or sms_result else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Check EC25-AU status or upload latest water CSV.")
    parser.add_argument("--status", action="store_true", help="Print EC25-AU AT command status.")
    parser.add_argument("--signal", action="store_true", help="Print parsed EC25-AU signal status.")
    parser.add_argument("--test-sms", action="store_true", help="Send a test SMS to configured alert recipients.")
    parser.add_argument("--upload-latest", action="store_true", help="Upload newest weekly CSV with curl.")
    parser.add_argument("--report", action="store_true", help="Post server status and send due SMS alerts.")
    args = parser.parse_args()

    if args.upload_latest:
        return upload_latest()
    if args.report:
        return report_status()
    if args.signal:
        print(modem_signal_text())
        return 0
    if args.test_sms:
        return send_test_sms()

    print(modem_status())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
