# Orange Pi Zero 3 Water Logger Carrier PCB

This KiCad project is the first-pass PCB carrier for the Orange Pi Zero 3
version of the water logger.

Status: **ERC-clean schematic and schematic-synced PCB placement draft, not ready to order yet**.

The board is intended to act as a shield/carrier/interface board:

- Orange Pi Zero 3 connects through its 26-pin header.
- Raspberry Pi Pico plugs into 2 x 20 headers.
- DS3231, BME280, and ADS1115 boards can plug into module headers.
- Water sensors connect through labelled screw terminals or JST-style headers.
- An integrated high-side 5V MOSFET/load-switch section switches Orange Pi power.
- DS18B20 has a 4.7k pull-up footprint.

## Files

| File | Purpose |
| --- | --- |
| `zero3-water-logger-carrier.kicad_pro` | KiCad project |
| `zero3-water-logger-carrier.kicad_sch` | R1 schematic draft with PD, buck, switch, Pico, Orange Pi, ADC, sensor, RTC, and ambient headers |
| `zero3-water-logger-carrier.kicad_pcb` | Board outline, assigned footprints, schematic nets, and placement draft |
| `water_logger_generated.kicad_sym` | Local generated KiCad symbol library used by the schematic |
| `sym-lib-table` | Project symbol-library table for the generated `WL` library |
| `zero3-water-logger-carrier-pinout.csv` | Pin/net planning table |
| `selected-parts-bom.csv` | Selected revision-1 PD/buck/MOSFET parts and values |
| `fabrication-readiness.md` | PCBWay/Gerber readiness checklist |
| `generate_schematic.py` | Regenerates the KiCad schematic draft from the selected net plan |
| `generate_pcb.py` | Regenerates the KiCad PCB placement/net-assignment draft from the selected net plan |

Current schematic check: `kicad-cli sch erc` reports **0 violations**. Current
PCB DRC reports **0 violations** and **136 unconnected items**. That means the
board has no detected clearance/short errors in its placement state, but it is
still unrouted and is not orderable.

## Current Placement

The R1 board file contains schematic-synced footprints and net assignments for:

- Orange Pi Zero 3 26-pin header.
- Raspberry Pi Pico 2 x 20 socket.
- ADS1115 #1 and #2 module headers.
- DS18B20, BME280, and DS3231 module headers.
- Six 3-pin analog sensor terminals: pH, TDS, turbidity, ORP, dissolved oxygen, and ammonium ISE amp.
- Download button header with switch contacts and optional LED terminals.
- Spare analog header for the unused ADS1115 #2 A2/A3 channels.
- 4.7k DS18B20 pull-up resistor.
- Integrated USB-C PD input, TPS54531 buck regulator, and high-side 5V MOSFET
  switch section.

The PCB is intentionally left unrouted. Route and review the power section in
KiCad before generating Gerbers. The CH224K package/pin mapping must be checked
against the exact part datasheet before assembly.

## Integrated 5V Switch

The board now plans for an on-board high-side 5V switch instead of an external
relay/MOSFET module.

Power path:

```text
USB-C PD input -> PD sink controller -> negotiated 9V rail
                -> buck regulator -> protected 5.1V rail
                                  -> Pico always-on VSYS/5V
                                  -> P-channel MOSFET -> switched 5V rail
```

Control path:

```text
Pico GP15 -> gate-driver transistor/MOSFET -> P-channel MOSFET gate
```

Default state is off. The P-channel MOSFET gate is pulled up to fused 5V. When
Pico GP15 goes high, the small gate-driver device pulls the P-channel gate low
and enables switched 5V to the Orange Pi.

Planned parts:

| Ref | Function | Requirement |
| --- | --- | --- |
| `J14` | USB-C PD input | USB-C 16-pin receptacle, HRO TYPE-C-31-M-12 class |
| `U1` | USB-C PD sink controller | CH224K, strapped for fixed 9V request |
| `D1` | VBUS TVS diode | USB/PD-rated input surge protection |
| `F1` | Input protection | Resettable fuse/polyfuse on negotiated PD input rail |
| `U2` | Buck regulator | TPS54531DDA 5A buck regulator |
| `L1` | Buck inductor | 4.7uH shielded inductor rated at least 6A |
| `D2` | Buck catch diode | CDBC540-G or equivalent 5A/40V Schottky |
| `CIN1`, `CIN2` | Buck/input capacitors | 4.7uF 50V X7R near `U2` |
| `CIN3` | Buck high-frequency bypass | 10nF 50V near `U2` |
| `COUT1`, `COUT2` | 5.1V output capacitors | 47uF low-ESR output capacitors |
| `RFB1`, `RFB2` | Buck feedback divider | TPS54531 example values: 10.2k / 1.96k |
| `REN1`, `REN2` | Buck enable divider | TPS54531 8V minimum input example values: 665k / 130k |
| `RCOMP1`, `CCOMP1`, `CCOMP2` | Buck compensation | TPS54531 example compensation network |
| `Q1` | High-side switch | AO4407A P-channel MOSFET, SOIC-8 |
| `Q2` | Gate driver | 2N7002 N-MOSFET, SOT-23, driven by Pico GP15 |
| `R2` | Gate pull-up | 100k from Q1 gate to fused 5V, keeps switch off |
| `R3` | Gate drive resistor | 1k between Pico GP15 and Q2 gate/base |
| `R4` | Driver pulldown | 100k from Q2 gate/base to GND |
| `C1` | Switched rail bulk cap | 470uF-1000uF, voltage rating at least 10V |

One USB-C port can power both boards. The Pico is connected to the protected
5.1V rail before the MOSFET so it stays awake. The Orange Pi Zero 3 is connected
only to the switched 5V rail after Q1 so the Pico can turn it off between logs.

Use a USB-C PD power bank or charger that can provide at least 30W. The target
PD profile is `9V 3A` or better, feeding a 5.1V buck rail. The TPS54531 design
uses an 8V minimum input example, so non-PD 5V fallback is not supported by this
revision.

Before ordering, verify the exact `J14`, `U1`, `U2`, `Q1`, and `Q2` pinouts
against the chosen footprints. PD controllers, buck regulators, USB-C
connectors, and MOSFET pin order are not universal.

## Revision 1 Scope

The first PCB order should keep modules replaceable:

- Socket the Pico.
- Socket the ADS1115 modules.
- Socket the DS3231 module.
- Use external sensor boards for pH, TDS, turbidity, ORP, DO, and ammonium ISE.
- Keep the EC25 modem off this PCB.

Do not order until:

- Schematic symbols and PCB footprints for the selected PD/buck/MOSFET parts
  are placed and reviewed.
- Terminal block pitch is chosen.
- The Zero 3 header clearance is checked against the actual board.
- The schematic ERC and PCB DRC pass.
- PCB DRC reports zero unconnected items after routing.
- Gerbers are opened in an independent Gerber viewer.

## Recommended PCBWay Settings

- 2 layers.
- FR-4.
- 1.6mm thickness.
- 1oz copper minimum; 2oz preferred if switching Orange Pi current on-board.
- Green solder mask unless you prefer another colour.
- HASL lead-free or ENIG.
- Use conservative rules: 0.20mm trace/space for signals, much wider for 5V/GND.
