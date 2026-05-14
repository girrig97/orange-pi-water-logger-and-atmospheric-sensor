# Orange Pi 5 Max + Quectel EC25-AU Variant

This branch targets an Orange Pi 5 Max with a Quectel EC25-AU cellular modem.

## Important hardware note

The Orange Pi 5 Max has an M.2 M-key slot intended for NVMe/SATA storage. The Quectel EC25-AU M.2 modem is a WWAN-style module and should be connected through a compatible USB WWAN adapter, HAT, or carrier board, not directly into the Orange Pi 5 Max M-key storage slot.

Use the EC25-AU through USB. On Linux it should appear as several `/dev/ttyUSB*` ports after the correct USB serial drivers bind. The AT command port is commonly `/dev/ttyUSB2`, but confirm on your board.

## What changes in this branch

- `I2C_BUS_NUMBER` is now configurable by environment variable.
- `PICO_SERIAL_PORT` remains configurable by environment variable.
- `cellular_uploader.py` can check EC25-AU status with AT commands.
- `orange_pi_boot_wrapper.py` can optionally upload the newest weekly CSV before shutdown.
- `alert_manager.py` evaluates freshwater safety alerts, barometric pressure drops, water temperature changes, and daily status messages.

## Suggested Orange Pi 5 Max setup

Enable the I2C and UART overlays for the 40-pin header using the Orange Pi configuration tool or the official image overlay method.

Then find the actual bus names:

```bash
ls /dev/i2c-*
ls /dev/ttyS*
```

Scan for the two ADS1115 boards:

```bash
sudo i2cdetect -y 3
sudo i2cdetect -y 4
sudo i2cdetect -y 5
sudo i2cdetect -y 8
```

Use whichever bus shows `0x48` and `0x49`.

Example environment for an Orange Pi 5 Max install:

```bash
export I2C_BUS_NUMBER=5
export PICO_SERIAL_PORT=/dev/ttyS4
export EC25_AT_PORT=/dev/ttyUSB2
```

If your enabled header UART appears as another device, change `PICO_SERIAL_PORT`.

## EC25-AU modem check

Install the required packages:

```bash
sudo apt update
sudo apt install -y curl python3-serial modemmanager usb-modeswitch
```

Check that the modem appears:

```bash
lsusb
ls /dev/ttyUSB*
```

Check AT command status:

```bash
python3 cellular_uploader.py --status
```

Expected useful responses include:

```text
AT: OK
AT+CPIN?: READY
AT+CSQ: signal quality
AT+COPS?: network/operator
AT+QNWINFO: radio access technology and band
```

For server updates, the Orange Pi also needs an active data connection. One common approach is NetworkManager/ModemManager:

```bash
sudo mmcli -L
sudo nmcli c add type gsm ifname "*" con-name ec25 apn your.apn.here
sudo nmcli c up ec25
```

Use the APN from your SIM provider. SMS alerts can work over the modem AT port even when no HTTP upload URL is configured.

## Optional cellular upload

The logger still records to weekly CSV files first. Cellular upload is optional and disabled by default.

To upload the newest weekly CSV after each boot-time reading:

```bash
export CELLULAR_UPLOAD_ENABLED=1
export CELLULAR_UPLOAD_URL=https://your-server.example/upload
```

Then the boot wrapper will:

1. Take one reading.
2. Save it to the current weekly CSV.
3. Run `cellular_uploader.py --upload-latest`.
4. Shut the Orange Pi down.

If no upload URL is set, the uploader exits without blocking normal logging.

## SMS and server status reporting

This branch can send:

- A JSON status update to your server after each reading.
- A daily SMS status message.
- SMS alerts when freshwater readings look unsafe.
- SMS alerts for barometric pressure drops.
- SMS alerts for water temperature changes compared with the recent average.

Enable reporting:

```bash
export CELLULAR_REPORTING_ENABLED=1
export CELLULAR_STATUS_URL=https://your-server.example/water-logger/status
export ALERT_SMS_NUMBERS=+61400111222,+61400999888
```

Run manually for testing:

```bash
python3 cellular_uploader.py --report
```

The server receives JSON containing:

```text
generated_at
latest
summary
alerts
sms_alerts
daily_status_due
record_count_window
```

If `CELLULAR_STATUS_URL` is not set, server updates are skipped. If `ALERT_SMS_NUMBERS` is not set, SMS is skipped.

## Freshwater alert defaults

These are starter alert thresholds, not legal or scientific certification. Tune them for your creek and calibrate every probe.

| Environment variable | Default | Alert meaning |
| --- | ---: | --- |
| `ALERT_PH_MIN` | `6.5` | pH below this alerts |
| `ALERT_PH_MAX` | `9.0` | pH above this alerts |
| `ALERT_DO_MIN_MG_L` | `5.0` | dissolved oxygen below this alerts |
| `ALERT_NH3_MAX_MG_L` | `0.05` | toxic ammonia NH3 at/above this alerts |
| `ALERT_WATER_TEMP_MIN_C` | `5.0` | water temp below this alerts |
| `ALERT_WATER_TEMP_MAX_C` | `30.0` | water temp above this alerts |
| `ALERT_TURBIDITY_MAX_NTU` | `50.0` | turbidity above this alerts |
| `ALERT_TDS_MAX_PPM` | `1000.0` | TDS above this alerts |
| `ALERT_PRESSURE_DROP_HPA_24H` | `6.0` | pressure drop over recent 24h alerts |
| `ALERT_TEMP_CHANGE_C_24H` | `2.0` | water temp change versus recent 24h average alerts |
| `ALERT_COOLDOWN_SECONDS` | `21600` | same alert SMS cooldown, default 6 hours |

Sensor communication failures also generate warning alerts. That means if a sensor is damaged or disconnected, the logger still records what it can and the cellular branch can tell you which sensor failed.

## EC25-AU SMS notes

SMS is sent through AT commands on `EC25_AT_PORT`, usually `/dev/ttyUSB2`.

The helper uses:

```text
AT
AT+CMGF=1
AT+CMGS="+614..."
```

Make sure the SIM can send SMS, the antenna is attached, and the modem has network signal. Check with:

```bash
python3 cellular_uploader.py --status
```

If SMS fails, the logger still keeps the CSV data. Reporting failures do not delete readings.

## Power notes

The Orange Pi 5 Max uses more power than the Zero 3. Use a larger power bank or battery pack, and make sure the 5V relay/MOS switch can handle the startup current.

The EC25-AU can draw burst current during LTE transmit. Use a modem carrier board with stable power and a good antenna.

## Branch purpose

Keep this branch separate from `main` so the original Orange Pi Zero 3 version remains simple. Merge only the shared improvements you want in both versions.
