# Fabrication Readiness

Status: **not ready to upload to PCBWay yet**.

The current KiCad schematic passes ERC, and the PCB has been updated to a
schematic-synced placement/net-assignment draft. It is not an orderable
electrical design yet. Do not upload Gerbers for manufacture until the items
below are complete.

## Current State

- Board outline, assigned footprints, and schematic nets exist.
- KiCad PCB DRC reports zero violations, but 136 unconnected items remain.
- KiCad schematic ERC passes.
- USB-C PD, buck regulator, and MOSFET switch parts are captured in the R1
  schematic draft.
- Pinout CSV includes planned nets for USB-C PD, buck regulator, and high-side
  MOSFET switching.
- `generate_pcb.py` can regenerate the current PCB placement/net-assignment
  draft from the same component plan as the schematic.

## Required Before Gerber Upload

1. Review the R1 schematic draft against the selected part datasheets.
2. Verify CH224K strap pins for a fixed 9V PD request.
3. Verify TPS54531DDA support parts and values against the datasheet/reference
   design.
4. Verify all footprints in the schematic, especially USB-C, CH224K, TPS54531,
   AO4407A, and terminal blocks.
5. Complete PCB routing from the existing schematic-synced placement.
6. Route the PD/buck power section with wide copper and regulator datasheet
   layout rules.
7. Route all low-current control and sensor nets.
8. Run PCB DRC and schematic ERC with zero errors and zero unconnected items.
9. Open the generated Gerbers in a separate Gerber viewer and inspect:
    - board outline,
    - drill holes,
    - USB-C footprint,
    - regulator footprint,
    - MOSFET footprint,
    - connector labels,
    - mounting holes,
    - copper clearances,
    - polarity marks.

## Recommended Upload Package

Once the design is actually routed and passes checks, export:

- Front copper
- Back copper
- Front solder mask
- Back solder mask
- Front silkscreen
- Back silkscreen if used
- Edge cuts
- Excellon drill files
- Gerber job file
- Schematic PDF for review
- BOM and position files only if using PCB assembly

## KiCad CLI Export Commands

Run from the repository root:

```powershell
$kicad = "C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"
$pcb = "hardware\zero3-carrier\zero3-water-logger-carrier.kicad_pcb"
$sch = "hardware\zero3-carrier\zero3-water-logger-carrier.kicad_sch"
$out = "hardware\zero3-carrier\fabrication\pcbway"

& $kicad sch erc $sch
& $kicad pcb drc $pcb
& $kicad pcb export gerbers --output $out --layers F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts $pcb
& $kicad pcb export drill --output $out --format excellon --excellon-units mm --generate-map --generate-report $pcb
& $kicad sch export pdf --output "$out\schematic.pdf" $sch
```

Zip the contents of `hardware\zero3-carrier\fabrication\pcbway` after visual
Gerber inspection.

## Why No Gerber ZIP Is Committed Yet

An upload ZIP would currently manufacture an unrouted placement draft. The
PD/buck/MOSFET schematic exists and the PCB has been updated from that net plan,
but the copper routing is not complete. Uploading the current board would waste
money and create false confidence.
