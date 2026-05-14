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

## Power notes

The Orange Pi 5 Max uses more power than the Zero 3. Use a larger power bank or battery pack, and make sure the 5V relay/MOS switch can handle the startup current.

The EC25-AU can draw burst current during LTE transmit. Use a modem carrier board with stable power and a good antenna.

## Branch purpose

Keep this branch separate from `main` so the original Orange Pi Zero 3 version remains simple. Merge only the shared improvements you want in both versions.
