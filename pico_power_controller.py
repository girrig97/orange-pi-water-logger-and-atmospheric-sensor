"""
Raspberry Pi Pico / Pico W power timer for the Orange Pi water logger.

Normal mode:
  - Turns the Orange Pi on every 6 hours.
  - Gives it enough time to boot, log once, and shut itself down.
  - Then cuts power to save the USB power bank.

Download mode:
  - Press the button once to power the Orange Pi and keep it on.
  - Hold the button for 2 seconds to start Bluetooth pairing mode.
  - Download the CSV over Bluetooth or WiFi.
  - Hold the button for 10 seconds while awake to cut power, or let the timeout end it.

Run this with MicroPython on the Pico. The Orange Pi should run:
  python3 water_logger.py --once --shutdown-after
for scheduled logging.
"""

from machine import I2C, Pin, UART
import time


# Wiring
POWER_ENABLE_PIN = 15       # Pico GP15 -> 5V relay/MOS power-switch trigger
DOWNLOAD_BUTTON_PIN = 14    # Button between Pico GP14 and GND
STATUS_LED_PIN = 25         # Pico onboard LED
RTC_SDA_PIN = 4             # Pico GP4 -> DS3231 SDA
RTC_SCL_PIN = 5             # Pico GP5 -> DS3231 SCL
ORANGE_PI_READY_PIN = 13    # Optional: Orange Pi GPIO -> Pico GP13
PICO_UART_TX_PIN = 0        # Pico GP0 -> Orange Pi UART RX
PICO_UART_RX_PIN = 1        # Pico GP1 <- Orange Pi UART TX, required

# Timing
LOG_INTERVAL_SECONDS = 6 * 60 * 60
MIN_LOG_INTERVAL_SECONDS = 60 * 60
MAX_LOG_INTERVAL_SECONDS = 6 * 60 * 60
SCHEDULED_ON_SECONDS = 10 * 60
DOWNLOAD_TIMEOUT_SECONDS = 60 * 60
BUTTON_DEBOUNCE_MS = 80
BUTTON_HOLD_SECONDS = 2
MANUAL_POWER_OFF_HOLD_SECONDS = 10
PAIRING_HOLD_MS = BUTTON_HOLD_SECONDS * 1000
MANUAL_POWER_OFF_HOLD_MS = MANUAL_POWER_OFF_HOLD_SECONDS * 1000
DOWNLOAD_LED_BLINK_MS = 800
PAIRING_LED_BLINK_MS = 180

DS3231_ADDRESS = 0x68
MIN_VALID_YEAR = 2024


power_enable = Pin(POWER_ENABLE_PIN, Pin.OUT, value=0)
button = Pin(DOWNLOAD_BUTTON_PIN, Pin.IN, Pin.PULL_UP)
led = Pin(STATUS_LED_PIN, Pin.OUT, value=0)
orange_pi_ready = Pin(ORANGE_PI_READY_PIN, Pin.IN, Pin.PULL_DOWN)
i2c = I2C(0, sda=Pin(RTC_SDA_PIN), scl=Pin(RTC_SCL_PIN), freq=100000)
uart = UART(0, baudrate=9600, tx=Pin(PICO_UART_TX_PIN), rx=Pin(PICO_UART_RX_PIN))


def bcd_to_int(value):
    return ((value >> 4) * 10) + (value & 0x0F)


def int_to_bcd(value):
    return ((value // 10) << 4) | (value % 10)


def now_seconds():
    """Return DS3231 date/time as seconds since 2000-01-01.

    This is enough for interval timing and avoids needing full timezone logic on
    the Pico. Set the DS3231 once with set_rtc_time().
    """
    try:
        data = i2c.readfrom_mem(DS3231_ADDRESS, 0x00, 7)
        second = bcd_to_int(data[0] & 0x7F)
        minute = bcd_to_int(data[1] & 0x7F)
        hour = bcd_to_int(data[2] & 0x3F)
        day = bcd_to_int(data[4] & 0x3F)
        month = bcd_to_int(data[5] & 0x1F)
        year = 2000 + bcd_to_int(data[6])
        if year < MIN_VALID_YEAR:
            raise ValueError("DS3231 time is not set")
        return time.mktime((year, month, day, hour, minute, second, 0, 0))
    except Exception:
        return time.ticks_ms() // 1000


def set_rtc_time(year, month, day, hour, minute, second):
    """Set DS3231 time. Call once from the MicroPython REPL if needed."""
    data = bytes(
        [
            int_to_bcd(second),
            int_to_bcd(minute),
            int_to_bcd(hour),
            int_to_bcd(1),
            int_to_bcd(day),
            int_to_bcd(month),
            int_to_bcd(year - 2000),
        ]
    )
    i2c.writeto_mem(DS3231_ADDRESS, 0x00, data)


def rtc_time_valid():
    try:
        data = i2c.readfrom_mem(DS3231_ADDRESS, 0x06, 1)
        return 2000 + bcd_to_int(data[0]) >= MIN_VALID_YEAR
    except Exception:
        return False


def orange_pi_on():
    power_enable.value(1)
    led.value(1)


def orange_pi_off():
    power_enable.value(0)
    led.value(0)


def error_blink(count=6):
    for _ in range(count):
        led.value(1)
        time.sleep_ms(120)
        led.value(0)
        time.sleep_ms(120)


def button_pressed():
    if button.value() == 1:
        return False
    time.sleep_ms(BUTTON_DEBOUNCE_MS)
    return button.value() == 0


def wait_for_button_release():
    while button.value() == 0:
        time.sleep_ms(50)


def read_button_action():
    pressed_at = time.ticks_ms()
    while button.value() == 0:
        if time.ticks_diff(time.ticks_ms(), pressed_at) >= PAIRING_HOLD_MS:
            wait_for_button_release()
            return "pairing"
        time.sleep_ms(50)
    return "download"


def held_button_exit_requested():
    pressed_at = time.ticks_ms()
    while button.value() == 0:
        if time.ticks_diff(time.ticks_ms(), pressed_at) >= MANUAL_POWER_OFF_HOLD_MS:
            wait_for_button_release()
            return True
        time.sleep_ms(50)
    return False


def run_download_mode(pairing=False):
    orange_pi_on()
    started_at = now_seconds()
    blink_at = time.ticks_ms()
    announce_at = time.ticks_ms()
    led_state = True
    uart_message = "PAIRING_MODE=1\n" if pairing else "DOWNLOAD_MODE=1\n"
    blink_interval_ms = PAIRING_LED_BLINK_MS if pairing else DOWNLOAD_LED_BLINK_MS

    while now_seconds() - started_at < DOWNLOAD_TIMEOUT_SECONDS:
        if time.ticks_diff(time.ticks_ms(), announce_at) > 2000:
            announce_at = time.ticks_ms()
            uart.write(uart_message)

        if time.ticks_diff(time.ticks_ms(), blink_at) > blink_interval_ms:
            blink_at = time.ticks_ms()
            led_state = not led_state
            led.value(led_state)

        if button_pressed() and held_button_exit_requested():
            break

        time.sleep(1)

    # Give Linux a chance to finish writes if you shut it down before the long
    # button press. Avoid using this as the normal way to turn off a running Pi.
    time.sleep(5)
    orange_pi_off()


def run_scheduled_log():
    orange_pi_on()
    started_at = now_seconds()
    next_interval = None

    while now_seconds() - started_at < SCHEDULED_ON_SECONDS:
        if uart.any():
            try:
                line = uart.readline()
                if line:
                    message = line.decode("utf-8").strip()
                    if message.startswith("NEXT_INTERVAL="):
                        value = int(message.split("=", 1)[1])
                        next_interval = max(
                            MIN_LOG_INTERVAL_SECONDS,
                            min(MAX_LOG_INTERVAL_SECONDS, value),
                        )
            except Exception:
                pass

        # Optional: if you wire an Orange Pi GPIO to this pin and set it high at
        # shutdown, the Pico can cut power sooner. Otherwise it waits 10 minutes.
        if orange_pi_ready.value() == 1:
            time.sleep(10)
            break
        if button_pressed() and held_button_exit_requested():
            break
        time.sleep(2)

    if next_interval is None:
        # Required UART interval was not received. Retry in 1 hour so the fault
        # is easier to catch during field checks and low-pressure mode is not
        # missed for a full 6-hour cycle.
        next_interval = MIN_LOG_INTERVAL_SECONDS
        error_blink(20)

    orange_pi_off()
    return next_interval


def main():
    if not rtc_time_valid():
        error_blink(12)
    next_log_at = now_seconds()
    orange_pi_off()

    while True:
        current_time = now_seconds()

        if button_pressed():
            action = read_button_action()
            run_download_mode(pairing=(action == "pairing"))
            next_log_at = now_seconds() + LOG_INTERVAL_SECONDS

        if current_time >= next_log_at:
            next_interval = run_scheduled_log()
            next_log_at = now_seconds() + next_interval

        time.sleep(2)


main()
