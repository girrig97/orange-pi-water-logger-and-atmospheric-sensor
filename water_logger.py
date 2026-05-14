#!/usr/bin/env python3
"""
Orange Pi Zero 3 water-quality logger.

Every 6 hours this app appends one CSV row to the microSD card. It logs
raw sensor voltages, calibrated sensor values, and derived water-quality
calculations that can be computed from the available probes.
"""

from __future__ import annotations

import csv
import math
import os
import subprocess
import time
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


# Store records on the Orange Pi microSD card.
# If you copy the project to /home/orangepi/water-logger, weekly CSV files are
# kept in /home/orangepi/water-logger/records/.
PROJECT_PATH = Path(__file__).resolve().parent
RECORDS_PATH = PROJECT_PATH / "records"
CSV_FILENAME_PREFIX = "water_conditions"
DOWNLOAD_MODE_FILENAME = "DOWNLOAD_MODE"
PAIRING_MODE_FILENAME = "PAIRING_MODE"
NEXT_INTERVAL_FILENAME = "next_interval_seconds.txt"

# 6 hours, in seconds.
LOG_INTERVAL_SECONDS = 6 * 60 * 60
LOW_PRESSURE_INTERVAL_SECONDS = 60 * 60
LOW_PRESSURE_HPA = 1000.0
PICO_SERIAL_PORT = os.environ.get("PICO_SERIAL_PORT", "/dev/ttyS5")

# Taking several quick samples and averaging them reduces random ADC noise.
# Keep this modest for battery use.
SAMPLE_COUNT = 5
SAMPLE_DELAY_SECONDS = 0.2

# TDS-to-EC factor. 500 is common for hobby TDS meters, but calibrate yours.
TDS_FACTOR = 500.0

# Orange Pi Zero 3 26-pin header exposes I2C3 on physical pins 3 and 5.
I2C_BUS_NUMBER = 3

# ADS1115 addresses. Set ADS1115 #1 ADDR to GND for 0x48.
# Set ADS1115 #2 ADDR to 3.3V/VDD for 0x49.
ADS1115_1_ADDRESS = 0x48
ADS1115_2_ADDRESS = 0x49

# ADS1115 full-scale range. Use +/-4.096V, but never feed an ADS1115 input
# above its VDD. If powered from 3.3V, sensor outputs must stay within 0-3.3V.
ADS1115_FULL_SCALE_VOLTS = 4.096


@dataclass
class SensorVoltages:
    ph: float | None
    tds: float | None
    turbidity: float | None
    orp: float | None
    dissolved_oxygen: float | None
    ammonium_ise: float | None
    ph_status: str
    tds_status: str
    turbidity_status: str
    orp_status: str
    dissolved_oxygen_status: str
    ammonium_ise_status: str


@dataclass
class WaterReading:
    timestamp: str
    temperature_c: float | None
    temperature_status: str
    ph_voltage: float | None
    tds_voltage: float | None
    turbidity_voltage: float | None
    orp_voltage: float | None
    do_voltage: float | None
    ammonium_voltage: float | None
    ph_status: str
    tds_status: str
    turbidity_status: str
    orp_status: str
    dissolved_oxygen_status: str
    ammonium_ise_status: str
    ph: float | None
    tds_ppm: float | None
    ec_ms_cm: float | None
    salinity_ppt: float | None
    turbidity_ntu: float | None
    clarity_percent: float | None
    orp_mv: float | None
    dissolved_oxygen_mg_l: float | None
    dissolved_oxygen_percent: float | None
    ammonium_nh4_mg_l: float | None
    toxic_ammonia_nh3_mg_l: float | None
    ammonia_risk: str
    water_score: float | None
    water_condition: str
    air_temperature_c: float | None
    air_humidity_percent: float | None
    air_pressure_hpa: float | None
    air_sensor_status: str
    dew_point_c: float | None
    air_water_temp_difference_c: float | None
    next_interval_seconds: int


class ADS1115:
    """Tiny ADS1115 reader using Linux I2C.

    This avoids Raspberry-Pi-specific GPIO libraries and works well on Orange Pi
    once /dev/i2c-3 is enabled.
    """

    CONVERSION_REGISTER = 0x00
    CONFIG_REGISTER = 0x01

    CHANNEL_CONFIG = {
        0: 0x4000,
        1: 0x5000,
        2: 0x6000,
        3: 0x7000,
    }

    def __init__(self, bus_number: int, address: int) -> None:
        try:
            from smbus2 import SMBus
        except ImportError:
            try:
                from smbus import SMBus
            except ImportError as exc:
                raise RuntimeError(
                    "Install I2C support first: sudo apt install python3-smbus i2c-tools"
                ) from exc

        self.bus = SMBus(bus_number)
        self.address = address

    def read_voltage(self, channel: int) -> float:
        if channel not in self.CHANNEL_CONFIG:
            raise ValueError(f"ADS1115 channel must be 0-3, got {channel}")

        # Single-shot conversion, single-ended channel, +/-4.096V range,
        # 128 samples/sec, comparator disabled.
        config = (
            0x8000
            | self.CHANNEL_CONFIG[channel]
            | 0x0200
            | 0x0100
            | 0x0080
            | 0x0003
        )

        self.bus.write_i2c_block_data(
            self.address,
            self.CONFIG_REGISTER,
            [(config >> 8) & 0xFF, config & 0xFF],
        )
        time.sleep(0.01)

        data = self.bus.read_i2c_block_data(self.address, self.CONVERSION_REGISTER, 2)
        raw = (data[0] << 8) | data[1]
        if raw & 0x8000:
            raw -= 0x10000

        return raw * ADS1115_FULL_SCALE_VOLTS / 32768.0


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def read_bme280() -> dict[str, float | str | None]:
    """Read BME280 ambient air sensor from I2C3.

    Returns None values if the sensor/library is not available yet. Without a
    pressure reading, the logger uses the normal 6-hour interval.
    """
    try:
        from smbus2 import SMBus
    except ImportError:
        try:
            from smbus import SMBus
        except ImportError:
            return {
                "air_temperature_c": None,
                "air_humidity_percent": None,
                "air_pressure_hpa": None,
                "air_sensor_status": "i2c_library_missing",
            }

    try:
        import bme280
    except ImportError:
        return {
            "air_temperature_c": None,
            "air_humidity_percent": None,
            "air_pressure_hpa": None,
            "air_sensor_status": "bme280_library_missing",
        }

    for address in (0x76, 0x77):
        bus = None
        try:
            bus = SMBus(I2C_BUS_NUMBER)
            calibration = bme280.load_calibration_params(bus, address)
            data = bme280.sample(bus, address, calibration)
            return {
                "air_temperature_c": float(data.temperature),
                "air_humidity_percent": float(data.humidity),
                "air_pressure_hpa": float(data.pressure),
                "air_sensor_status": "ok",
            }
        except Exception:
            continue
        finally:
            if bus is not None and hasattr(bus, "close"):
                bus.close()

    return {
        "air_temperature_c": None,
        "air_humidity_percent": None,
        "air_pressure_hpa": None,
        "air_sensor_status": "bme280_not_found_or_not_responding",
    }


def dew_point_c(air_temperature_c: float | None, humidity_percent: float | None) -> float | None:
    if air_temperature_c is None or humidity_percent is None or humidity_percent <= 0:
        return None

    a = 17.27
    b = 237.7
    alpha = ((a * air_temperature_c) / (b + air_temperature_c)) + math.log(humidity_percent / 100.0)
    return (b * alpha) / (a - alpha)


def choose_next_interval_seconds(pressure_hpa: float | None) -> int:
    if pressure_hpa is not None and pressure_hpa < LOW_PRESSURE_HPA:
        return LOW_PRESSURE_INTERVAL_SECONDS
    return LOG_INTERVAL_SECONDS


def read_temperature_c() -> tuple[float | None, str]:
    """Read DS18B20 temperature from Linux 1-Wire.

    On the Orange Pi this usually appears under /sys/bus/w1/devices/ after
    1-Wire support is enabled. Returns None if no DS18B20 is found yet.
    """
    try:
        devices = list(Path("/sys/bus/w1/devices").glob("28-*"))
    except OSError:
        return None, "onewire_path_unavailable"

    if not devices:
        return None, "ds18b20_not_found"

    try:
        data = (devices[0] / "w1_slave").read_text(encoding="utf-8").strip()
    except OSError:
        return None, "ds18b20_read_failed"

    if "YES" not in data:
        return None, "ds18b20_crc_failed"

    marker = "t="
    if marker in data:
        return int(data.split(marker, 1)[1]) / 1000.0, "ok"

    return None, "ds18b20_temperature_missing"


def read_sensor_voltages(ads1: ADS1115 | None = None, ads2: ADS1115 | None = None) -> SensorVoltages:
    """Read analog voltages from ADC boards.

    Wiring layout:
      ADS1115 #1: A0 pH, A1 TDS, A2 turbidity, A3 ORP
      ADS1115 #2: A0 dissolved oxygen, A1 ammonium ISE
    """
    ads1_status = "ok"
    ads2_status = "ok"

    if ads1 is None:
        try:
            ads1 = ADS1115(I2C_BUS_NUMBER, ADS1115_1_ADDRESS)
        except Exception:
            ads1 = None
            ads1_status = "ads1115_0x48_not_found_or_i2c_failed"
    if ads2 is None:
        try:
            ads2 = ADS1115(I2C_BUS_NUMBER, ADS1115_2_ADDRESS)
        except Exception:
            ads2 = None
            ads2_status = "ads1115_0x49_not_found_or_i2c_failed"

    def read_channel(
        ads: ADS1115 | None,
        address: int,
        channel: int,
        adc_status: str,
    ) -> tuple[float | None, str]:
        if ads is None:
            return None, adc_status
        try:
            return ads.read_voltage(channel), "ok"
        except Exception:
            return None, f"ads1115_0x{address:02x}_channel_{channel}_read_failed"

    ph, ph_status = read_channel(ads1, ADS1115_1_ADDRESS, 0, ads1_status)
    tds, tds_status = read_channel(ads1, ADS1115_1_ADDRESS, 1, ads1_status)
    turbidity, turbidity_status = read_channel(ads1, ADS1115_1_ADDRESS, 2, ads1_status)
    orp, orp_status = read_channel(ads1, ADS1115_1_ADDRESS, 3, ads1_status)
    dissolved_oxygen, dissolved_oxygen_status = read_channel(ads2, ADS1115_2_ADDRESS, 0, ads2_status)
    ammonium_ise, ammonium_ise_status = read_channel(ads2, ADS1115_2_ADDRESS, 1, ads2_status)

    return SensorVoltages(
        ph=ph,
        tds=tds,
        turbidity=turbidity,
        orp=orp,
        dissolved_oxygen=dissolved_oxygen,
        ammonium_ise=ammonium_ise,
        ph_status=ph_status,
        tds_status=tds_status,
        turbidity_status=turbidity_status,
        orp_status=orp_status,
        dissolved_oxygen_status=dissolved_oxygen_status,
        ammonium_ise_status=ammonium_ise_status,
    )


def read_average_sensor_voltages() -> SensorVoltages:
    try:
        ads1 = ADS1115(I2C_BUS_NUMBER, ADS1115_1_ADDRESS)
    except Exception:
        ads1 = None
    try:
        ads2 = ADS1115(I2C_BUS_NUMBER, ADS1115_2_ADDRESS)
    except Exception:
        ads2 = None

    samples = []
    for sample_index in range(SAMPLE_COUNT):
        samples.append(read_sensor_voltages(ads1, ads2))
        if sample_index < SAMPLE_COUNT - 1 and SAMPLE_DELAY_SECONDS:
            time.sleep(SAMPLE_DELAY_SECONDS)

    def average(sensor_name: str) -> float | None:
        values = [getattr(sample, sensor_name) for sample in samples]
        values = [value for value in values if value is not None]
        if not values:
            return None
        return sum(values) / len(values)

    def combined_status(status_name: str) -> str:
        statuses = [getattr(sample, status_name) for sample in samples]
        if all(status == "ok" for status in statuses):
            return "ok"
        failed = [status for status in statuses if status != "ok"]
        if len(failed) == len(statuses):
            return failed[0]
        return "partial_read_failure"

    return SensorVoltages(
        ph=average("ph"),
        tds=average("tds"),
        turbidity=average("turbidity"),
        orp=average("orp"),
        dissolved_oxygen=average("dissolved_oxygen"),
        ammonium_ise=average("ammonium_ise"),
        ph_status=combined_status("ph_status"),
        tds_status=combined_status("tds_status"),
        turbidity_status=combined_status("turbidity_status"),
        orp_status=combined_status("orp_status"),
        dissolved_oxygen_status=combined_status("dissolved_oxygen_status"),
        ammonium_ise_status=combined_status("ammonium_ise_status"),
    )


def estimate_ph(voltage: float | None) -> float | None:
    if voltage is None:
        return None
    # Placeholder only. Calibrate with pH 4, 7, and 10 buffer solutions.
    ph7_voltage = 2.50
    slope_ph_per_volt = -5.70
    return 7.0 + ((voltage - ph7_voltage) * slope_ph_per_volt)


def estimate_tds_ppm(voltage: float | None, temperature_c: float | None) -> float | None:
    if voltage is None:
        return None
    # Gravity-style TDS polynomial with temperature compensation.
    temp = 25.0 if temperature_c is None else temperature_c
    compensation = 1.0 + 0.02 * (temp - 25.0)
    compensated_voltage = voltage / compensation
    tds = (
        133.42 * compensated_voltage**3
        - 255.86 * compensated_voltage**2
        + 857.39 * compensated_voltage
    ) * 0.5
    return max(tds, 0.0)


def estimate_turbidity_ntu(voltage: float | None) -> float | None:
    if voltage is None:
        return None
    # Common hobby-sensor approximation. Calibrate with your module.
    ntu = -1120.4 * voltage**2 + 5742.3 * voltage - 4352.9
    return max(ntu, 0.0)


def estimate_orp_mv(voltage: float | None) -> float | None:
    if voltage is None:
        return None
    # Placeholder only. Calibrate with known ORP solution.
    neutral_voltage = 2.50
    return (voltage - neutral_voltage) * 1000.0


def do_saturation_mg_l(temperature_c: float | None) -> float:
    # Freshwater oxygen saturation at sea level, approximated by interpolation.
    temp = 25.0 if temperature_c is None else clamp(temperature_c, 0.0, 40.0)
    table = {
        0.0: 14.62,
        5.0: 12.80,
        10.0: 11.29,
        15.0: 10.08,
        20.0: 9.09,
        25.0: 8.26,
        30.0: 7.56,
        35.0: 6.95,
        40.0: 6.41,
    }
    points = sorted(table)
    for low, high in zip(points, points[1:]):
        if low <= temp <= high:
            fraction = (temp - low) / (high - low)
            return table[low] + ((table[high] - table[low]) * fraction)
    return table[25.0]


def estimate_dissolved_oxygen_mg_l(voltage: float | None, temperature_c: float | None) -> float | None:
    if voltage is None:
        return None
    # Placeholder calibration. Replace with your Gravity DO calibration voltage.
    calibration_voltage_in_air_saturated_water = 1.60
    return max(
        0.0,
        voltage / calibration_voltage_in_air_saturated_water * do_saturation_mg_l(temperature_c),
    )


def estimate_ammonium_nh4_mg_l(voltage: float | None, temperature_c: float | None) -> float | None:
    if voltage is None:
        return None
    # Placeholder ISE conversion. This requires a proper ISE amplifier and
    # calibration solution. Tune these after calibration.
    electrode_mv = voltage * 1000.0
    calibration_mv = 1500.0
    calibration_mg_l = 10.0
    temp = 25.0 if temperature_c is None else temperature_c
    slope_mv_per_decade = 59.16 * ((temp + 273.15) / 298.15)

    log_concentration = (
        (electrode_mv - calibration_mv) / slope_mv_per_decade
        + math.log10(calibration_mg_l)
    )
    return max(0.0, 10**log_concentration)


def ammonia_nh3_fraction(ph: float | None, temperature_c: float | None) -> float | None:
    if ph is None:
        return None
    temp = 25.0 if temperature_c is None else temperature_c
    pka = 0.09018 + (2729.92 / (temp + 273.15))
    return 1.0 / (1.0 + 10 ** (pka - ph))


def ammonia_risk(nh3_mg_l: float | None) -> str:
    if nh3_mg_l is None:
        return "unknown"
    if nh3_mg_l < 0.02:
        return "low"
    if nh3_mg_l < 0.05:
        return "caution"
    if nh3_mg_l < 0.10:
        return "danger"
    return "critical"


def water_quality_score(
    ph: float | None,
    tds_ppm: float | None,
    turbidity_ntu: float | None,
    temperature_c: float | None,
    do_mg_l: float | None,
    nh3_mg_l: float | None,
) -> float | None:
    values = [ph, tds_ppm, turbidity_ntu, temperature_c, do_mg_l, nh3_mg_l]
    if any(value is None for value in values):
        return None

    score = 100.0

    if ph < 6.5:
        score -= (6.5 - ph) * 15.0
    elif ph > 8.5:
        score -= (ph - 8.5) * 15.0

    if tds_ppm > 500.0:
        score -= (tds_ppm - 500.0) * 0.04

    if turbidity_ntu > 5.0:
        score -= (turbidity_ntu - 5.0) * 2.0

    if temperature_c < 5.0:
        score -= (5.0 - temperature_c) * 2.0
    elif temperature_c > 30.0:
        score -= (temperature_c - 30.0) * 2.0

    if do_mg_l < 5.0:
        score -= (5.0 - do_mg_l) * 12.0

    if nh3_mg_l > 0.02:
        score -= (nh3_mg_l - 0.02) * 700.0

    return round(clamp(score, 0.0, 100.0), 2)


def water_condition(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score >= 90:
        return "excellent"
    if score >= 75:
        return "good"
    if score >= 50:
        return "poor"
    return "bad"


def collect_reading() -> WaterReading:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    temperature_c, temperature_status = read_temperature_c()
    air = read_bme280()
    voltages = read_average_sensor_voltages()

    ph = estimate_ph(voltages.ph)
    tds_ppm = estimate_tds_ppm(voltages.tds, temperature_c)
    ec_ms_cm = None if tds_ppm is None else tds_ppm / TDS_FACTOR
    salinity_ppt = None if tds_ppm is None else tds_ppm / 1000.0
    turbidity_ntu = estimate_turbidity_ntu(voltages.turbidity)
    clarity_percent = None if turbidity_ntu is None else clamp(100.0 - (turbidity_ntu * 2.0), 0.0, 100.0)
    orp_mv = estimate_orp_mv(voltages.orp)
    do_mg_l = estimate_dissolved_oxygen_mg_l(voltages.dissolved_oxygen, temperature_c)
    do_percent = None if do_mg_l is None else do_mg_l / do_saturation_mg_l(temperature_c) * 100.0
    ammonium_nh4_mg_l = estimate_ammonium_nh4_mg_l(voltages.ammonium_ise, temperature_c)
    nh3_fraction = ammonia_nh3_fraction(ph, temperature_c)
    nh3_mg_l = (
        None
        if ammonium_nh4_mg_l is None or nh3_fraction is None
        else ammonium_nh4_mg_l * nh3_fraction
    )
    score = water_quality_score(ph, tds_ppm, turbidity_ntu, temperature_c, do_mg_l, nh3_mg_l)
    dew_point = dew_point_c(air["air_temperature_c"], air["air_humidity_percent"])
    air_water_difference = (
        None
        if air["air_temperature_c"] is None or temperature_c is None
        else air["air_temperature_c"] - temperature_c
    )
    next_interval = choose_next_interval_seconds(air["air_pressure_hpa"])

    return WaterReading(
        timestamp=timestamp,
        temperature_c=temperature_c,
        temperature_status=temperature_status,
        ph_voltage=voltages.ph,
        tds_voltage=voltages.tds,
        turbidity_voltage=voltages.turbidity,
        orp_voltage=voltages.orp,
        do_voltage=voltages.dissolved_oxygen,
        ammonium_voltage=voltages.ammonium_ise,
        ph_status=voltages.ph_status,
        tds_status=voltages.tds_status,
        turbidity_status=voltages.turbidity_status,
        orp_status=voltages.orp_status,
        dissolved_oxygen_status=voltages.dissolved_oxygen_status,
        ammonium_ise_status=voltages.ammonium_ise_status,
        ph=ph,
        tds_ppm=tds_ppm,
        ec_ms_cm=ec_ms_cm,
        salinity_ppt=salinity_ppt,
        turbidity_ntu=turbidity_ntu,
        clarity_percent=clarity_percent,
        orp_mv=orp_mv,
        dissolved_oxygen_mg_l=do_mg_l,
        dissolved_oxygen_percent=do_percent,
        ammonium_nh4_mg_l=ammonium_nh4_mg_l,
        toxic_ammonia_nh3_mg_l=nh3_mg_l,
        ammonia_risk=ammonia_risk(nh3_mg_l),
        water_score=score,
        water_condition=water_condition(score),
        air_temperature_c=air["air_temperature_c"],
        air_humidity_percent=air["air_humidity_percent"],
        air_pressure_hpa=air["air_pressure_hpa"],
        air_sensor_status=str(air["air_sensor_status"]),
        dew_point_c=dew_point,
        air_water_temp_difference_c=air_water_difference,
        next_interval_seconds=next_interval,
    )


def append_reading(csv_path: Path, reading: WaterReading) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()
    row = reading.__dict__

    with csv_path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(row.keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def weekly_csv_path(timestamp: datetime | None = None) -> Path:
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    year, week, _ = timestamp.isocalendar()
    return RECORDS_PATH / f"{CSV_FILENAME_PREFIX}_{year}_week_{week:02d}.csv"


def send_next_interval_to_pico(next_interval_seconds: int) -> None:
    """Tell the Pico when to wake the Orange Pi next.

    Required wiring: Orange Pi UART TX to Pico GP1/RX, with common GND.
    """
    try:
        import serial

        with serial.Serial(PICO_SERIAL_PORT, 9600, timeout=1) as serial_port:
            serial_port.write(f"NEXT_INTERVAL={next_interval_seconds}\n".encode("utf-8"))
    except ImportError as exc:
        raise RuntimeError("Install pyserial first: pip3 install pyserial") from exc
    except OSError as exc:
        raise RuntimeError(
            f"Could not open Pico UART link at {PICO_SERIAL_PORT}. "
            "Enable the Orange Pi UART or set PICO_SERIAL_PORT."
        ) from exc


def log_once(csv_path: Path | None = None) -> Path:
    reading = collect_reading()
    if csv_path is None:
        csv_path = weekly_csv_path()
    append_reading(csv_path, reading)
    (csv_path.parent / NEXT_INTERVAL_FILENAME).write_text(
        str(reading.next_interval_seconds),
        encoding="utf-8",
    )
    send_next_interval_to_pico(reading.next_interval_seconds)
    print(f"Logged water reading to {csv_path}")
    return csv_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Log water-quality readings to microSD CSV.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Take one reading, save it, and exit. Best for systemd timers and low power.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=LOG_INTERVAL_SECONDS,
        help="Seconds between readings when running continuously.",
    )
    parser.add_argument(
        "--shutdown-after",
        action="store_true",
        help="Shut down the Orange Pi after logging once. Use with timed power hardware.",
    )
    args = parser.parse_args()

    download_mode_path = RECORDS_PATH / DOWNLOAD_MODE_FILENAME
    pairing_mode_path = RECORDS_PATH / PAIRING_MODE_FILENAME

    if args.once:
        log_once()
        if args.shutdown_after and not download_mode_path.exists() and not pairing_mode_path.exists():
            subprocess.run(["sync"], check=False)
            subprocess.run(["shutdown", "-h", "now"], check=False)
        elif download_mode_path.exists() or pairing_mode_path.exists():
            print("Download or pairing mode marker found; staying on.")
        return

    while True:
        log_once()
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
