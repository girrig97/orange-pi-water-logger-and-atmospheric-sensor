# Orange Pi Zero 3 Water Logger Carrier PCB

This KiCad project is the first-pass PCB carrier for the Orange Pi Zero 3
version of the water logger.

Status: **placement and pinout skeleton, not ready to order yet**.

The board is intended to act as a shield/carrier/interface board:

- Orange Pi Zero 3 connects through its 26-pin header.
- Raspberry Pi Pico plugs into 2 x 20 headers.
- DS3231, BME280, and ADS1115 boards can plug into module headers.
- Water sensors connect through labelled screw terminals or JST-style headers.
- A high-side 5V MOSFET/load-switch section is reserved for Orange Pi power.
- DS18B20 has a 4.7k pull-up footprint.

## Files

| File | Purpose |
| --- | --- |
| `zero3-water-logger-carrier.kicad_pro` | KiCad project |
| `zero3-water-logger-carrier.kicad_sch` | Placeholder schematic sheet |
| `zero3-water-logger-carrier.kicad_pcb` | Board outline and connector placement skeleton |
| `zero3-water-logger-carrier-pinout.csv` | Pin/net planning table |

## Current Placement

The R0 board file contains placement placeholders for:

- Orange Pi Zero 3 26-pin header.
- Raspberry Pi Pico 2 x 20 socket.
- ADS1115 #1 and #2 module headers.
- DS18B20, BME280, and DS3231 module headers.
- Six 3-pin analog sensor terminals: pH, TDS, turbidity, ORP, dissolved oxygen, and ammonium ISE amp.
- 4.7k DS18B20 pull-up resistor.
- Reserved 5-pin high-side 5V load-switch/MOSFET connector.

The footprints are intentionally generic through-hole placeholders until the
exact module header style, terminal-block pitch, and load-switch part are
chosen.

## Revision 1 Scope

The first PCB order should keep modules replaceable:

- Socket the Pico.
- Socket the ADS1115 modules.
- Socket the DS3231 module.
- Use external sensor boards for pH, TDS, turbidity, ORP, DO, and ammonium ISE.
- Keep the EC25 modem off this PCB.

Do not order until:

- The exact load-switch/MOSFET circuit is chosen.
- Terminal block pitch is chosen.
- The Zero 3 header clearance is checked against the actual board.
- The schematic ERC and PCB DRC pass.
- Gerbers are opened in an independent Gerber viewer.

## Recommended PCBWay Settings

- 2 layers.
- FR-4.
- 1.6mm thickness.
- 1oz copper minimum; 2oz preferred if switching Orange Pi current on-board.
- Green solder mask unless you prefer another colour.
- HASL lead-free or ENIG.
- Use conservative rules: 0.20mm trace/space for signals, much wider for 5V/GND.
