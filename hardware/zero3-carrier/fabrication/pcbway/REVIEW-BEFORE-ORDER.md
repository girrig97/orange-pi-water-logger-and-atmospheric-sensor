# Review Required Before Ordering

These Gerbers are an R1 draft produced by an automated workflow:

1. `generate_schematic.py` -> schematic + symbol library + pinout CSV
2. `generate_pcb.py` -> placement + dual-layer GND copper pours
3. `route_with_freerouting.py` -> Freerouting auto-routing of all 83 remaining
   signal/power nets

Validation that passed before export:

- `kicad-cli sch erc`: 0 violations
- `kicad-cli pcb drc --refill-zones`: 0 violations, 0 unconnected items

## Manual review items before clicking "Order"

1. **TPS54531 buck regulator layout.** The auto-router produced electrically
   correct traces but does not follow the TI reference layout. For a 5A buck
   supply this is the difference between "regulates well, low EMI" and
   "marginal, noisy, may not meet load". Re-route by hand in KiCad:
   - Short SW node loop between U2 pin PH, L1, D2, and CBOOT.
   - Tight CIN1/CIN2/CIN3 placement right at U2 VIN/GND.
   - Tight COUT1/COUT2 placement at L1 output.
   - Solid GND under U2 PowerPAD (EP) with thermal vias to the bottom pour.
   - Keep BUCK_FB away from BUCK_SW.

2. **AO4407A high-side switch layout.** Wide copper between FUSED_5V1 ->
   Q1 source pads and Q1 drain pads -> C1 -> OPI_5V_SW. Keep PWR_GATE
   short and away from BUCK_SW.

3. **CH224K PD sink pinout.** The schematic uses a placeholder pin map
   ("CH224K package pinouts vary between supplier drawings"). Confirm
   against the supplier datasheet of the actual part you order.

4. **Footprint matching.** Spot-check each footprint against the part you
   plan to assemble:
   - J14 USB-C receptacle (16-pin HRO TYPE-C-31-M-12)
   - U2 TPS54531DDA SOIC PowerPAD
   - Q1 AO4407A SOIC-8
   - L1 4.7uH inductor footprint
   - Terminal blocks (Phoenix MKDS-1.5-3-5.08 pitch)

5. **Visual Gerber inspection.** Open the Gerbers in an independent viewer
   (PCBWay's online previewer or `gerbv`) and check:
   - Board outline matches your enclosure.
   - Drill positions match pad positions.
   - Silkscreen labels are present beside every external connector.
   - No copper outside the board outline.
   - Solder mask openings match pads.

6. **Bench prototype first.** Order one or two boards, assemble them on
   the bench, and verify the buck regulator regulates at 5.1V under load
   before placing a quantity order.

## Auto-routing notes

Freerouting was invoked at `medium` effort (max 20 passes). Auto-router
output is deterministic given the same DSN input, so you can re-run
`python ../route_with_freerouting.py` to reproduce these Gerbers, or
`--effort thorough` for more optimization passes.

## File list

- `zero3-water-logger-carrier-F_Cu.gtl` - top copper
- `zero3-water-logger-carrier-B_Cu.gbl` - bottom copper
- `zero3-water-logger-carrier-F_Mask.gts` / `-B_Mask.gbs` - solder mask
- `zero3-water-logger-carrier-F_Silkscreen.gto` / `-B_Silkscreen.gbo` - silkscreen
- `zero3-water-logger-carrier-Edge_Cuts.gm1` - board outline
- `zero3-water-logger-carrier-job.gbrjob` - Gerber job file
- `zero3-water-logger-carrier.drl` - plated through-holes (Excellon)
- `zero3-water-logger-carrier-drl_map.pdf` - drill map (human reference)
- `zero3-water-logger-carrier-drill.rpt` - drill report
- `schematic.pdf` - schematic for cross-checking
