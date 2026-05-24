# PCB Carrier Design Brief

This project can use a custom PCB, but the safest first revision should be a
carrier/interface board, not a full custom Orange Pi replacement.

The Orange Pi, Pico, RTC, sensor modules, and modem should remain replaceable
modules connected by headers or screw terminals. This keeps the board easier to
assemble, repair, and revise after field testing.

## Recommended PCB Type

Build a **water-logger carrier PCB** with:

- Orange Pi header/cable connector.
- Raspberry Pi Pico socket or header.
- DS3231 RTC module socket.
- Two ADS1115 module sockets.
- High-side 5V MOSFET/load-switch circuit for Orange Pi power.
- 4.7k DS18B20 pull-up resistor.
- Screw terminals or JST connectors for sensors.
- Common ground and 3.3V distribution.
- UART link between Pico and Orange Pi.
- Optional Orange Pi ready/shutdown GPIO input to Pico GP13.

Do **not** solder the Orange Pi directly to the board on revision 1. Use headers
or a short ribbon cable so the same PCB can work with either:

- Orange Pi Zero 3 26-pin header.
- Orange Pi 5 Max enabled GPIO/I2C/UART header pins.

## Board Strategy

There are two practical approaches.

### Option A: Universal Interface Board

Use labelled screw terminals or 2.54mm headers for these Orange Pi signals:

| Signal | Purpose |
| --- | --- |
| 5V switched input to Orange Pi | Powers Orange Pi through Pico-controlled switch |
| Orange Pi GND | Common ground |
| Orange Pi 3.3V | Powers ADC/sensor logic if current budget allows |
| Orange Pi I2C SDA | ADS1115 and BME280 data |
| Orange Pi I2C SCL | ADS1115 and BME280 clock |
| Orange Pi UART TX | Sends interval/status data to Pico GP1/RX |
| Orange Pi UART RX | Receives Pico download/pairing requests from GP0/TX |
| Orange Pi DS18B20 GPIO | 1-Wire temperature data |
| Optional Orange Pi ready GPIO | Lets Pico cut power sooner after shutdown |

This is the best first revision because it avoids board-specific header mistakes.

### Option B: Dual-Footprint Board

Place both Orange Pi header footprints on the PCB:

- 26-pin Zero 3 footprint.
- 40-pin or chosen header footprint for Orange Pi 5 Max.

Only populate/connect one at a time. This is cleaner once pin assignments are
confirmed, but it is easier to get wrong before bench testing.

## Power Architecture

Recommended power path:

```text
USB power bank / 5V source
-> PCB 5V input fuse
-> Pico always-on 5V/VSYS
-> high-side MOSFET/load switch
-> switched 5V to Orange Pi
```

Requirements:

- 5V input rated at least 3A for Zero 3.
- 5V input rated 5A preferred for Orange Pi 5 Max.
- Use a high-side switch if possible. Avoid low-side switching for the final PCB.
- Use wide copper pours for 5V and GND.
- Add test pads for 5V input, switched 5V, 3.3V, GND, SDA, SCL, UART TX/RX.
- Add a fuse or resettable polyfuse at the 5V input.
- Add reverse-polarity protection if using screw terminals instead of USB.

Suggested switch parts/classes:

- Integrated high-side load switch rated 5A or higher.
- P-channel MOSFET high-side switch with gate driver/transistor.
- Automotive-style high-side switch module footprint if using a replaceable module.

Do not use a relay coil on the PCB unless power use is acceptable. A relay can
work, but a MOSFET/load switch is quieter and more efficient.

## Pico Connections

| Pico pin | PCB net |
| --- | --- |
| VSYS/5V | Always-on 5V from power input |
| GND | Common ground |
| GP15 | Power switch enable |
| GP14 | Momentary download/pairing button |
| GP4 | DS3231 SDA |
| GP5 | DS3231 SCL |
| GP0/TX | Orange Pi UART RX |
| GP1/RX | Orange Pi UART TX |
| GP13 | Optional Orange Pi ready/shutdown GPIO |
| GP25 or spare GPIO | Optional button LED output |

## Orange Pi Connections

Use labelled board-to-wire terminals or headers for:

| PCB net | Orange Pi function |
| --- | --- |
| OPI_5V_SW | Orange Pi 5V input |
| OPI_GND | Orange Pi ground |
| OPI_3V3 | Orange Pi 3.3V logic rail |
| OPI_SDA | Enabled I2C SDA |
| OPI_SCL | Enabled I2C SCL |
| OPI_UART_TX | Orange Pi TX to Pico RX |
| OPI_UART_RX | Orange Pi RX from Pico TX |
| OPI_1WIRE | DS18B20 data GPIO |
| OPI_READY | Optional shutdown/ready GPIO to Pico GP13 |

## Sensor / ADC Connections

Use two ADS1115 modules or footprints.

ADS1115 #1:

| ADS1115 channel | Sensor |
| --- | --- |
| A0 | pH analog output |
| A1 | TDS analog output |
| A2 | Turbidity analog output |
| A3 | ORP analog output |

ADS1115 #2:

| ADS1115 channel | Sensor |
| --- | --- |
| A0 | Dissolved oxygen analog output |
| A1 | Ammonium ISE amplifier analog output |
| A2 | Spare |
| A3 | Spare |

Address setup:

| Module | ADDR connection | Address |
| --- | --- | --- |
| ADS1115 #1 | GND | `0x48` |
| ADS1115 #2 | VDD/3.3V | `0x49` |

Add silk labels beside every analog input. Sensor modules should connect by
screw terminals or locking connectors.

Important:

- ADS1115 VDD is 3.3V.
- Analog inputs must stay between 0V and 3.3V.
- Add optional divider footprints on each analog input for sensors that output
  up to 5V.
- Keep analog traces away from the MOSFET/load-switch power path.
- Add GND beside every sensor signal terminal.

## DS18B20 / BME280 / RTC

DS18B20:

- DATA to Orange Pi 1-Wire GPIO.
- 4.7k resistor from DATA to 3.3V.
- Connector pins: 3.3V, DATA, GND.

BME280:

- 3.3V, GND, SDA, SCL.
- Same I2C bus as ADS1115 modules.

DS3231:

- Connected to Pico I2C, not Orange Pi I2C.
- Pins: Pico 3V3, GND, GP4 SDA, GP5 SCL.

## Button / LED

Momentary button:

- `NO` to Pico GP14.
- `C` to GND.
- Leave `NC` unused.

Illuminated button LED:

- Use a spare Pico GPIO only if the LED is 3.3V compatible.
- Add series resistor footprint, for example 330 ohm.
- If the button LED is 5V/12V/24V type, use a transistor driver or leave the
  built-in LED disconnected.

## Recommended PCB Manufacturing Settings

For a service like PCBWay, use conservative rules instead of minimum rules:

- 2-layer PCB for revision 1.
- FR-4, 1.6mm thickness.
- 1oz copper minimum; 2oz copper preferred if switching Orange Pi power on board.
- HASL lead-free or ENIG finish.
- Minimum signal trace/space: 0.20mm or larger.
- Use wide pours/tracks for 5V and GND power.
- Finished drill holes matched to chosen terminals/headers.
- Large silkscreen labels on every connector.

PCBWay lists standard PCB capability down to very small trace/space values, but
they also recommend staying above about 6mil/0.15mm where possible to save cost
and improve yield. This design does not need fine-pitch routing, so use larger
rules.

Source: PCBWay capabilities page, https://www.pcbway.com/capabilities.html

## Board-Level Protection

Add these if space allows:

- Input fuse or resettable polyfuse.
- TVS diode on 5V input.
- Reverse-polarity protection for screw-terminal power input.
- Bulk capacitor near Orange Pi switched 5V output, for example 470uF-1000uF.
- 100nF decoupling near each module header.
- Optional I2C pull-up resistor footprints, marked DNP if modules already have pull-ups.
- Test pads for all power rails and communication lines.

## First Revision Scope

Revision 1 should prioritize reliability and debug access:

- Use through-hole headers/screw terminals.
- Use module sockets for Pico, RTC, ADS1115 boards, and BME280.
- Keep the Orange Pi connected by labelled cable/header rather than fixed SBC
  mounting.
- Include mounting holes.
- Include large connector labels.
- Include spare ADC channels and spare GPIO pads.

Do not integrate the EC25 modem on this PCB in revision 1. Keep the modem on its
own USB/Mini PCIe/M.2 carrier and power it from the Orange Pi side. Cellular
modems have burst current, RF layout, antenna, SIM, and certification concerns
that are better handled by an existing modem carrier.

## Open Decisions Before KiCad Layout

Confirm these before drawing the final schematic:

- Exact Orange Pi board for the first physical footprint: Zero 3, 5 Max, or
  universal terminals only.
- Exact MOSFET/load-switch part or module.
- Exact connector type: screw terminal, JST-XH, JST-PH, Dupont header, or mixed.
- Whether sensor modules are powered by switched 5V, always-on 5V, or Orange Pi 3.3V.
- Whether the button LED is 3.3V compatible.
- Enclosure size and mounting-hole locations.
- Whether PCB should carry high-current 5V directly or only control an external
  load-switch module.

## Deliverables Needed for PCBWay

Once laid out in KiCad, export:

- Gerber files.
- Drill files.
- Board outline.
- Pick/place file only if using PCB assembly.
- BOM only if using PCB assembly.
- Schematic PDF for review.
- PCB render/top-bottom images for checking connector labels.

Do not order until the schematic, net labels, and connector pinout have been
reviewed against the actual Orange Pi, Pico, sensor modules, and switch module
on the bench.
