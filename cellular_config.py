#!/usr/bin/env python3
"""Persistent cellular settings shared by Bluetooth and reporting helpers."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from water_logger import RECORDS_PATH


CONFIG_PATH = RECORDS_PATH / "cellular_config.json"
PHONE_PATTERN = re.compile(r"^\+?[0-9][0-9\s().-]{5,24}$")


def normalize_sms_numbers(raw_numbers: str | list[str]) -> list[str]:
    if isinstance(raw_numbers, str):
        parts = raw_numbers.replace(";", ",").replace("\n", ",").split(",")
    else:
        parts = raw_numbers

    numbers: list[str] = []
    for part in parts:
        number = part.strip()
        if not number:
            continue
        compact = re.sub(r"[\s().-]", "", number)
        if not PHONE_PATTERN.match(number) or len(compact.lstrip("+")) < 6:
            raise ValueError(f"Invalid phone number: {number}")
        if compact not in numbers:
            numbers.append(compact)
    return numbers


def read_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")


def get_sms_numbers() -> list[str]:
    env_numbers = os.environ.get("ALERT_SMS_NUMBERS", "").strip()
    if env_numbers:
        return normalize_sms_numbers(env_numbers)
    config = read_config()
    return normalize_sms_numbers(config.get("alert_sms_numbers", []))


def set_sms_numbers(raw_numbers: str | list[str]) -> list[str]:
    numbers = normalize_sms_numbers(raw_numbers)
    config = read_config()
    config["alert_sms_numbers"] = numbers
    write_config(config)
    return numbers


def sms_numbers_text() -> str:
    numbers = get_sms_numbers()
    return ",".join(numbers) if numbers else "none"
