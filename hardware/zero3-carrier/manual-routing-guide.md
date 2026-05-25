# Manual KiCad Routing Guide

This is a step-by-step guide for routing the carrier PCB by hand in the KiCad
PCB editor. Use it if you prefer not to run an external auto-router, or after
running `route_with_freerouting.py` to redo the safety-critical sections.

The starting state is the schematic-synced placement that
`generate_pcb.py` produces. ERC is clean, DRC is clean, GND copper pours are
already added on both layers, and 83 nets remain unconnected.

## What must be hand-routed regardless of any auto-router

The switching power supply and high-side switch sections do not tolerate
generic auto-routing. Even if you let Freerouting touch them, you must
re-route them by hand against the part datasheets before fabrication.

These nets:

| Net | Why it needs careful routing |
| --- | --- |
| `BUCK_SW` | Switching node. Keep the copper area as small as practical between U2 pin PH, L1, D2, and the bootstrap cap CBOOT. Large SW copper radiates EMI. |
| `PD_FUSED` | Buck input. Run wide, short, with CIN1/CIN2/CIN3 placed right at U2 pins. |
| `FUSED_5V1` | Buck output. Wide trace, low ESR caps COUT1/COUT2 at U2 output. Continues into the source of Q1. |
| `OPI_5V_SW` | Switched 5V to the Orange Pi. Wide. Tied to Q1 drain and C1 bulk capacitor. |
| `BUCK_FB` | Feedback. Run from VOUT side of RFB1 to U2 pin VSENSE, keep away from `BUCK_SW`. |
| `BUCK_BOOT`, `BUCK_COMP`, `BUCK_SS`, `BUCK_EN` | Small-signal compensation/start-up; route per TI datasheet. |
| `PWR_GATE`, `Q2_GATE` | High-side gate drive. Short tracks; keep `PWR_GATE` away from switching node. |
| `USB_VBUS`, `USB_CC1`, `USB_CC2`, `PD_CFG`, `PD_NEGOTIATED_VBUS` | PD front end. Follow CH224K supplier reference layout. |
| `GND` | Use the existing pour on both layers; add stitching vias near U1, U2, Q1, C1. |

References:

- TPS54531 datasheet, "Layout" section
  https://www.ti.com/lit/ds/symlink/tps54531.pdf
- CH224K supplier datasheet from your vendor.
- AO4407A PowerPak/SOIC-8 datasheet for thermal copper recommendation.

## Step-by-step

1. Open `zero3-water-logger-carrier.kicad_pro` in KiCad. Switch to the PCB
   editor (`Eeschema -> Open PCB Editor` or open the `.kicad_pcb` directly).
2. Press `Inspect -> Net Inspector` to see which nets are still unrouted.
3. Set the net classes if you have not already:
    - `Power`: width 1.2 mm minimum, including `FUSED_5V1`, `OPI_5V_SW`,
      `PD_FUSED`, `PD_NEGOTIATED_VBUS`, `USB_VBUS`.
    - `Default`: width 0.25 mm for signal nets.
    - Vias: 0.8 mm width / 0.4 mm drill.
4. Route the buck regulator section first:
    1. Place a short, fat `BUCK_SW` polygon between U2 PH/SW pin, L1 pin 1,
       and D2 cathode.
    2. Place CIN1, CIN2, CIN3 immediately adjacent to U2 VIN/GND.
    3. Place COUT1, COUT2 immediately adjacent to L1 output / U2 ground.
    4. Route VIN and 5V1 as wide as possible. Use both layers if needed.
    5. The U2 PowerPAD (EP) is GND. Drop several thermal vias under the pad
       into the bottom GND pour for heat dissipation.
5. Route the high-side switch around Q1 and Q2:
    1. Q1 source pads tie to `FUSED_5V1` with wide copper.
    2. Q1 drain pads tie to `OPI_5V_SW` with wide copper through C1.
    3. R2 (gate pull-up) and R3/R4 (gate drive) keep traces short.
6. Route the USB-C PD front end (U1, J14, D1, F1).
7. Route the signal nets:
    - I2C (`OPI_SDA`, `OPI_SCL`, `PICO_GP4`, `PICO_GP5`): keep both lines
      together, route in parallel where you can.
    - UART (`UART_OPI_TX_PICO_RX`, `UART_PICO_TX_OPI_RX`): short, parallel.
    - DS18B20 (`OPI_1WIRE`): single trace from OPi pin 7 to J5 and R1.
    - Sensor analog (`PH_AIN`, `TDS_AIN`, `TURB_AIN`, `ORP_AIN`, `DO_AIN`,
      `NH4_AIN`): keep away from the switching power supply area.
8. Route the optional `OPI_READY` and button/LED nets.
9. Add ground stitching vias on a roughly 10 mm grid across the board.
10. Add silkscreen labels next to each external connector (J5..J13, J15, J16).
11. Run DRC (`Inspect -> Design Rules Checker`) with "Refill zones before
    DRC" enabled. Iterate until both **violations** and **unconnected items**
    are zero.

## Final checks

Before exporting Gerbers, confirm:

- `python validate_design.py` exits with `all checks passed.`.
- Visually compare the front and back copper to the schematic.
- Use `View -> 3D Viewer` and inspect mechanical clearances.
- Confirm board outline matches your enclosure.

## Exporting Gerbers

From the repository root (Windows PowerShell):

```powershell
$kicad = "C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
$pcb   = "hardware\zero3-carrier\zero3-water-logger-carrier.kicad_pcb"
$sch   = "hardware\zero3-carrier\zero3-water-logger-carrier.kicad_sch"
$out   = "hardware\zero3-carrier\fabrication\pcbway"

& $kicad pcb export gerbers `
    --output $out `
    --layers F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts `
    $pcb

& $kicad pcb export drill `
    --output $out --format excellon --excellon-units mm `
    --generate-map --generate-report $pcb

& $kicad sch export pdf --output "$out\schematic.pdf" $sch
```

Zip the contents of `hardware\zero3-carrier\fabrication\pcbway\` and inspect
the Gerbers in an independent viewer (such as PCBWay's online previewer or
gerbv) before uploading.
