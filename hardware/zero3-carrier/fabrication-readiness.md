# Fabrication Readiness

Status: **Gerbers exported and ready to inspect; do not order until the
switching power supply layout has been reviewed.**

ERC and DRC are clean. All 83 signal/power nets have been routed by
Freerouting on top of the schematic-synced placement. The Gerber upload
package is in `fabrication/pcbway/` and zipped as
`fabrication/zero3-water-logger-carrier-R1.zip`. The review checklist that
must be cleared before ordering is in `fabrication/pcbway/REVIEW-BEFORE-ORDER.md`.

## Current State

- Board outline, assigned footprints, and schematic nets exist.
- GND copper pour on both layers, solid pad connection (no thermal-relief
  starvation against tight USB-C SMD pads). The pour brings the pre-routing
  unconnected-pad count down from 136 to **83**.
- KiCad PCB DRC reports **zero violations**.
- KiCad schematic ERC passes.
- USB-C PD, buck regulator, and MOSFET switch parts are captured in the R1
  schematic draft.
- Pinout CSV is generated from the same `COMPONENTS` table the schematic
  uses, so the published pinout cannot drift from actual net assignments.
- `generate_pcb.py` can regenerate the current PCB placement/net-assignment
  draft from the same component plan as the schematic and resolves the KiCad
  footprint library on Windows, macOS, and Linux (honours
  `KICAD_FOOTPRINT_DIR`).
- `validate_design.py` bundles ERC + DRC + CSV format checks behind a single
  pre-commit gate.
- `route_with_freerouting.py` is a one-command auto-router workflow (exports
  DSN, fetches and runs Freerouting, imports SES, refills zones, re-runs DRC).
- `manual-routing-guide.md` walks the per-section routing if you prefer to
  route by hand in KiCad GUI.

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

## Routing Workflow

The PCB is intentionally left unrouted by `generate_pcb.py` (apart from the
GND pour). Two safe paths finish the copper. Either way, run
`python validate_design.py` until zero unconnected items remain before
exporting Gerbers — see `manual-routing-guide.md` for the export commands.

1. **Auto-route signal nets, hand-route the power section.** Run

       python route_with_freerouting.py --effort medium

   This exports the DSN, fetches a pinned Freerouting JAR, routes the signal
   nets, imports the SES, refills the GND pour, and re-runs DRC. After it
   finishes, open the PCB in KiCad and **manually re-route the TPS54531 buck
   regulator section and the high-side MOSFET switch** against the TI
   reference layout. Auto-routers do not respect switching-supply layout
   rules.

2. **Route entirely by hand in KiCad GUI.** Follow `manual-routing-guide.md`.
   The buck regulator and high-side switch are routed first per their
   datasheets, then digital signals, then ground stitching vias.

## Gerber ZIP Available

The current Gerber upload package is committed at
`fabrication/zero3-water-logger-carrier-R1.zip` (~170 KB). Contents:

- F.Cu, B.Cu, F.Mask, B.Mask, F.Silkscreen, B.Silkscreen, Edge.Cuts gerbers
- Excellon drill file + drill map PDF + drill report
- Gerber job file (.gbrjob)
- Schematic PDF
- `REVIEW-BEFORE-ORDER.md` listing the manual review items

Auto-router output is electrically correct (DRC clean) but does not respect
switching-supply layout rules. Re-route the TPS54531 buck regulator and the
high-side MOSFET switch by hand in KiCad before ordering. See
`REVIEW-BEFORE-ORDER.md` and `manual-routing-guide.md`.
