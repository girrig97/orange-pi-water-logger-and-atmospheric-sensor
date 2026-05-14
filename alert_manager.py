#!/usr/bin/env python3
"""
Freshwater alert and daily-status logic for the cellular branch.

Thresholds are conservative starter values for field alerts. Calibrate and tune
them for your creek, probes, and local freshwater ecology before relying on
them for decisions.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from water_logger import CSV_FILENAME_PREFIX, RECORDS_PATH


STATE_PATH = RECORDS_PATH / "cellular_alert_state.json"
SENSOR_STATUS_COLUMNS = [
    "temperature_status",
    "ph_status",
    "tds_status",
    "turbidity_status",
    "orp_status",
    "dissolved_oxygen_status",
    "ammonium_ise_status",
    "air_sensor_status",
]


def env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class AlertThresholds:
    ph_min: float = env_float("ALERT_PH_MIN", 6.5)
    ph_max: float = env_float("ALERT_PH_MAX", 9.0)
    do_min_mg_l: float = env_float("ALERT_DO_MIN_MG_L", 5.0)
    nh3_max_mg_l: float = env_float("ALERT_NH3_MAX_MG_L", 0.05)
    water_temp_min_c: float = env_float("ALERT_WATER_TEMP_MIN_C", 5.0)
    water_temp_max_c: float = env_float("ALERT_WATER_TEMP_MAX_C", 30.0)
    turbidity_max_ntu: float = env_float("ALERT_TURBIDITY_MAX_NTU", 50.0)
    tds_max_ppm: float = env_float("ALERT_TDS_MAX_PPM", 1000.0)
    pressure_drop_hpa_24h: float = env_float("ALERT_PRESSURE_DROP_HPA_24H", 6.0)
    temp_change_c_24h: float = env_float("ALERT_TEMP_CHANGE_C_24H", 2.0)
    alert_cooldown_seconds: int = env_int("ALERT_COOLDOWN_SECONDS", 6 * 60 * 60)
    daily_status_after_hour: int = env_int("DAILY_STATUS_AFTER_HOUR", 4)


def weekly_csv_files() -> list[Path]:
    return sorted(RECORDS_PATH.glob(f"{CSV_FILENAME_PREFIX}_*_week_*.csv"))


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def as_float(row: dict[str, str], key: str) -> float | None:
    value = row.get(key, "").strip()
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def read_rows(limit: int = 96) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in weekly_csv_files()[-4:]:
        with path.open("r", newline="", encoding="utf-8") as file:
            rows.extend(csv.DictReader(file))
    return rows[-limit:]


def load_state() -> dict[str, Any]:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"last_sms_alerts": {}, "last_daily_status_date": "", "sensor_baseline": {}}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def alert(key: str, severity: str, message: str) -> dict[str, str]:
    return {"key": key, "severity": severity, "message": message}


def sensor_baseline_from_initial_row(row: dict[str, str]) -> dict[str, bool]:
    baseline: dict[str, bool] = {}
    for key in SENSOR_STATUS_COLUMNS:
        status = row.get(key, "").strip()
        baseline[key] = status == "ok"
    return baseline


def get_sensor_baseline(rows: list[dict[str, str]], state: dict[str, Any]) -> dict[str, bool]:
    baseline = state.get("sensor_baseline")
    if isinstance(baseline, dict) and baseline:
        return {str(key): bool(value) for key, value in baseline.items()}
    if not rows:
        return {}
    baseline = sensor_baseline_from_initial_row(rows[0])
    state["sensor_baseline"] = baseline
    return baseline


def evaluate_latest(rows: list[dict[str, str]], thresholds: AlertThresholds, sensor_baseline: dict[str, bool]) -> list[dict[str, str]]:
    if not rows:
        return [alert("no_records", "warning", "No water logger records found yet.")]

    latest = rows[-1]
    alerts: list[dict[str, str]] = []

    ph = as_float(latest, "ph")
    if ph is not None and (ph < thresholds.ph_min or ph > thresholds.ph_max):
        alerts.append(alert("ph_unsafe", "critical", f"pH {ph:.2f} is outside {thresholds.ph_min:.1f}-{thresholds.ph_max:.1f}."))

    do_mg_l = as_float(latest, "dissolved_oxygen_mg_l")
    if do_mg_l is not None and do_mg_l < thresholds.do_min_mg_l:
        alerts.append(alert("do_low", "critical", f"Dissolved oxygen {do_mg_l:.2f} mg/L is below {thresholds.do_min_mg_l:.1f} mg/L."))

    nh3 = as_float(latest, "toxic_ammonia_nh3_mg_l")
    if nh3 is not None and nh3 >= thresholds.nh3_max_mg_l:
        alerts.append(alert("nh3_high", "critical", f"Toxic ammonia NH3 {nh3:.3f} mg/L is at/above {thresholds.nh3_max_mg_l:.3f} mg/L."))

    temp = as_float(latest, "temperature_c")
    if temp is not None and (temp < thresholds.water_temp_min_c or temp > thresholds.water_temp_max_c):
        alerts.append(alert("water_temp_unsafe", "warning", f"Water temperature {temp:.1f} C is outside {thresholds.water_temp_min_c:.1f}-{thresholds.water_temp_max_c:.1f} C."))

    turbidity = as_float(latest, "turbidity_ntu")
    if turbidity is not None and turbidity > thresholds.turbidity_max_ntu:
        alerts.append(alert("turbidity_high", "warning", f"Turbidity {turbidity:.1f} NTU is above {thresholds.turbidity_max_ntu:.1f} NTU."))

    tds = as_float(latest, "tds_ppm")
    if tds is not None and tds > thresholds.tds_max_ppm:
        alerts.append(alert("tds_high", "warning", f"TDS {tds:.0f} ppm is above {thresholds.tds_max_ppm:.0f} ppm."))

    for key in SENSOR_STATUS_COLUMNS:
        value = latest.get(key, "").strip()
        if sensor_baseline.get(key, False) and value and value != "ok":
            alerts.append(alert(f"sensor_{key}", "warning", f"{key} is {value}."))

    condition = latest.get("water_condition", "")
    if condition in {"poor", "critical"}:
        alerts.append(alert("water_condition", "critical", f"Overall water condition is {condition}."))

    ammonia_risk = latest.get("ammonia_risk", "")
    if ammonia_risk in {"high", "very_high"}:
        alerts.append(alert("ammonia_risk", "critical", f"Ammonia risk is {ammonia_risk}."))

    return alerts


def evaluate_trends(rows: list[dict[str, str]], thresholds: AlertThresholds) -> list[dict[str, str]]:
    if len(rows) < 2:
        return []

    latest = rows[-1]
    latest_time = parse_time(latest.get("timestamp", ""))
    if latest_time is None:
        return []

    window_start = latest_time - timedelta(hours=24)
    window_rows = [row for row in rows if (parse_time(row.get("timestamp", "")) or latest_time) >= window_start]
    alerts: list[dict[str, str]] = []

    latest_pressure = as_float(latest, "air_pressure_hpa")
    prior_pressures = [value for row in window_rows[:-1] if (value := as_float(row, "air_pressure_hpa")) is not None]
    if latest_pressure is not None and prior_pressures:
        pressure_drop = max(prior_pressures) - latest_pressure
        if pressure_drop >= thresholds.pressure_drop_hpa_24h:
            alerts.append(alert("pressure_drop", "warning", f"Barometric pressure dropped {pressure_drop:.1f} hPa in the last 24 hours."))

    latest_temp = as_float(latest, "temperature_c")
    prior_temps = [value for row in window_rows[:-1] if (value := as_float(row, "temperature_c")) is not None]
    if latest_temp is not None and prior_temps:
        average_temp = sum(prior_temps) / len(prior_temps)
        temp_change = latest_temp - average_temp
        if abs(temp_change) >= thresholds.temp_change_c_24h:
            alerts.append(alert("water_temp_change", "warning", f"Water temp changed {temp_change:+.1f} C versus the recent 24h average."))

    return alerts


def summary_text(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "No readings recorded yet."
    latest = rows[-1]
    return (
        f"Water logger status: {latest.get('timestamp', 'unknown time')}; "
        f"pH {latest.get('ph') or '--'}, "
        f"DO {latest.get('dissolved_oxygen_mg_l') or '--'} mg/L, "
        f"temp {latest.get('temperature_c') or '--'} C, "
        f"pressure {latest.get('air_pressure_hpa') or '--'} hPa, "
        f"condition {latest.get('water_condition') or '--'}."
    )


def should_send_daily_status(state: dict[str, Any], now: datetime, thresholds: AlertThresholds) -> bool:
    local_now = now.astimezone()
    if local_now.hour < thresholds.daily_status_after_hour:
        return False
    today = local_now.date().isoformat()
    if state.get("last_daily_status_date") == today:
        return False
    state["last_daily_status_date"] = today
    return True


def filter_alerts_for_sms(alerts: list[dict[str, str]], state: dict[str, Any], now: datetime, thresholds: AlertThresholds) -> list[dict[str, str]]:
    last_sms_alerts = state.setdefault("last_sms_alerts", {})
    allowed: list[dict[str, str]] = []
    now_epoch = int(now.timestamp())
    for item in alerts:
        key = item["key"]
        last_sent = int(last_sms_alerts.get(key, 0))
        if now_epoch - last_sent >= thresholds.alert_cooldown_seconds:
            last_sms_alerts[key] = now_epoch
            allowed.append(item)
    return allowed


def build_report() -> dict[str, Any]:
    thresholds = AlertThresholds()
    rows = read_rows()
    now = datetime.now(timezone.utc)
    state = load_state()
    sensor_baseline = get_sensor_baseline(rows, state)
    alerts = evaluate_latest(rows, thresholds, sensor_baseline) + evaluate_trends(rows, thresholds)
    sms_alerts = filter_alerts_for_sms(alerts, state, now, thresholds)
    daily_due = should_send_daily_status(state, now, thresholds)
    save_state(state)
    latest = rows[-1] if rows else {}
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "latest": latest,
        "summary": summary_text(rows),
        "alerts": alerts,
        "sms_alerts": sms_alerts,
        "daily_status_due": daily_due,
        "record_count_window": len(rows),
        "sensor_baseline": sensor_baseline,
    }


def main() -> int:
    print(json.dumps(build_report(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
