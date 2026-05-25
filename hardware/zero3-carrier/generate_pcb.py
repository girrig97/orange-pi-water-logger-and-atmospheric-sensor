from __future__ import annotations

import datetime
import math
import os
import sys
from pathlib import Path

import pcbnew

import generate_schematic


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "zero3-water-logger-carrier.kicad_pcb"


def resolve_footprint_root() -> Path:
    """Find the KiCad system footprints directory.

    Honours $KICAD_FOOTPRINT_DIR if set, then falls back to the common install
    locations on Windows, macOS, and Linux. Fails with a clear error if none of
    them exist instead of silently producing an unrouted board.
    """
    env = os.environ.get("KICAD_FOOTPRINT_DIR")
    if env:
        return Path(env)
    candidates = [
        Path(r"C:\Program Files\KiCad\10.0\share\kicad\footprints"),
        Path(r"C:\Program Files\KiCad\9.0\share\kicad\footprints"),
        Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"),
        Path("/usr/share/kicad/footprints"),
        Path("/usr/local/share/kicad/footprints"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError(
        "Could not locate the KiCad footprint library. Set KICAD_FOOTPRINT_DIR "
        "to your KiCad installation's `share/kicad/footprints` directory."
    )


FP_ROOT = resolve_footprint_root()
TODAY = datetime.date.today().isoformat()

BOARD_W_MM = 360
BOARD_H_MM = 330
MARGIN_MM = 8
SIGNAL_WIDTH_MM = 0.25
POWER_WIDTH_MM = 1.2
VIA_WIDTH_MM = 0.8
VIA_DRILL_MM = 0.4


def mm(value: float) -> int:
    return pcbnew.FromMM(value)


def v(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(mm(x), mm(y))


def net_width(net: str) -> int:
    if net in {"GND", "FUSED_5V1", "OPI_5V_SW", "PD_FUSED", "PD_NEGOTIATED_VBUS", "USB_VBUS"}:
        return mm(POWER_WIDTH_MM)
    return mm(SIGNAL_WIDTH_MM)


def make_net(board: pcbnew.BOARD, name: str) -> pcbnew.NETINFO_ITEM:
    existing = board.FindNet(name)
    if existing:
        return existing
    net = pcbnew.NETINFO_ITEM(board, name)
    board.Add(net)
    return net


def pad_map_for(ref: str, symbol_pins: list[tuple[str, str, str]]) -> dict[str, str]:
    by_number = {pin: net for pin, _name, net in symbol_pins}

    if ref == "J14":
        return {
            "A4": "USB_VBUS", "B4": "USB_VBUS", "A9": "USB_VBUS", "B9": "USB_VBUS",
            "A1": "GND", "B1": "GND", "A12": "GND", "B12": "GND", "SH": "GND",
            "A5": "USB_CC1", "B5": "USB_CC2",
        }

    # CH224K package pinouts vary between supplier drawings. This revision keeps
    # the mapping explicit so it is easy to correct after confirming the exact
    # part datasheet used for assembly.
    if ref == "U1":
        return {
            "1": "USB_VBUS",
            "2": "PD_CFG",
            "3": "PD_CFG",
            "4": "PD_CFG",
            "5": "GND",
            "6": "USB_CC2",
            "7": "USB_CC1",
            "8": "PD_NEGOTIATED_VBUS",
            "9": "GND",
            "10": "GND",
        }

    if ref == "U2":
        return {
            "1": "BUCK_BOOT",
            "2": "PD_FUSED",
            "3": "BUCK_EN",
            "4": "BUCK_SS",
            "5": "BUCK_FB",
            "6": "BUCK_COMP",
            "7": "GND",
            "8": "BUCK_SW",
            "9": "GND",
        }

    if ref == "Q1":
        return {
            "1": "FUSED_5V1", "2": "FUSED_5V1", "3": "FUSED_5V1",
            "4": "PWR_GATE",
            "5": "OPI_5V_SW", "6": "OPI_5V_SW", "7": "OPI_5V_SW", "8": "OPI_5V_SW",
        }

    if ref == "Q2":
        return {"1": "Q2_GATE", "2": "GND", "3": "PWR_GATE"}

    if ref in {"D2"}:
        return {"1": "BUCK_SW", "2": "GND"}

    return by_number


def load_footprint(comp: dict) -> pcbnew.FOOTPRINT:
    lib, name = comp["footprint"].split(":", 1)
    footprint = pcbnew.FootprintLoad(str(FP_ROOT / f"{lib}.pretty"), name)
    if footprint is None:
        raise RuntimeError(f"Could not load footprint {comp['footprint']} for {comp['ref']}")
    footprint.SetReference(comp["ref"])
    footprint.SetValue(comp["value"])
    return footprint


def place_components(board: pcbnew.BOARD) -> dict[str, pcbnew.FOOTPRINT]:
    footprints: dict[str, pcbnew.FOOTPRINT] = {}
    for comp in generate_schematic.COMPONENTS:
        footprint = load_footprint(comp)
        footprint.SetPosition(v(float(comp["x"]) + 15, float(comp["y"]) + 12))
        footprint.SetOrientationDegrees(90 if comp["ref"].startswith("J") and comp["ref"] not in {"J14"} else 0)
        board.Add(footprint)
        footprints[comp["ref"]] = footprint

        mapping = pad_map_for(comp["ref"], comp["pins"])
        for pad in footprint.Pads():
            net_name = mapping.get(pad.GetNumber())
            if net_name is None:
                continue
            pad.SetNet(make_net(board, net_name))
    return footprints


def add_track(board: pcbnew.BOARD, net: pcbnew.NETINFO_ITEM, start: pcbnew.VECTOR2I, end: pcbnew.VECTOR2I, layer: int) -> None:
    if start == end:
        return
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(start)
    track.SetEnd(end)
    track.SetLayer(layer)
    track.SetWidth(net_width(net.GetNetname()))
    track.SetNet(net)
    board.Add(track)


def add_via(board: pcbnew.BOARD, net: pcbnew.NETINFO_ITEM, pos: pcbnew.VECTOR2I) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(pos)
    via.SetWidth(mm(VIA_WIDTH_MM))
    via.SetDrill(mm(VIA_DRILL_MM))
    via.SetNet(net)
    board.Add(via)


def bbox_mm(fp: pcbnew.FOOTPRINT) -> tuple[float, float, float, float]:
    box = fp.GetBoundingBox()
    return (
        pcbnew.ToMM(box.GetLeft()),
        pcbnew.ToMM(box.GetTop()),
        pcbnew.ToMM(box.GetRight()),
        pcbnew.ToMM(box.GetBottom()),
    )


def add_outline(board: pcbnew.BOARD) -> None:
    points = [
        (MARGIN_MM, MARGIN_MM, BOARD_W_MM - MARGIN_MM, MARGIN_MM),
        (BOARD_W_MM - MARGIN_MM, MARGIN_MM, BOARD_W_MM - MARGIN_MM, BOARD_H_MM - MARGIN_MM),
        (BOARD_W_MM - MARGIN_MM, BOARD_H_MM - MARGIN_MM, MARGIN_MM, BOARD_H_MM - MARGIN_MM),
        (MARGIN_MM, BOARD_H_MM - MARGIN_MM, MARGIN_MM, MARGIN_MM),
    ]
    for x1, y1, x2, y2 in points:
        shape = pcbnew.PCB_SHAPE(board)
        shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
        shape.SetLayer(pcbnew.Edge_Cuts)
        shape.SetStart(v(x1, y1))
        shape.SetEnd(v(x2, y2))
        shape.SetWidth(mm(0.1))
        board.Add(shape)


def add_mounting_holes(board: pcbnew.BOARD) -> None:
    missing = False
    for ref, x, y in [
        ("H1", 16, 16),
        ("H2", BOARD_W_MM - 16, 16),
        ("H3", BOARD_W_MM - 16, BOARD_H_MM - 16),
        ("H4", 16, BOARD_H_MM - 16),
    ]:
        hole = pcbnew.FootprintLoad(str(FP_ROOT / "MountingHole.pretty"), "MountingHole_3.2mm_M3")
        if hole is None:
            missing = True
            continue
        hole.SetReference(ref)
        hole.SetPosition(v(x, y))
        board.Add(hole)
    if missing:
        print(
            "warning: MountingHole_3.2mm_M3 footprint not found; some holes were skipped.",
            file=sys.stderr,
        )


def main() -> None:
    board = pcbnew.BOARD()
    board.SetTitleBlock(pcbnew.TITLE_BLOCK())
    title = board.GetTitleBlock()
    title.SetTitle("Orange Pi Zero 3 Water Logger Carrier")
    title.SetDate(TODAY)
    title.SetRevision("R1 generated placement")
    title.SetCompany("Water Logger")

    add_outline(board)
    add_mounting_holes(board)
    place_components(board)
    add_ground_pours(board)
    # The PCB is generated with real footprints and schematic nets assigned.
    # Signal/power copper traces are NOT auto-generated here. Auto-routing
    # happens outside this script via the bundled Freerouting workflow
    # (route_with_freerouting.py). Switching power supply nets must still be
    # reviewed against the TPS54531 reference layout before order.

    pcbnew.SaveBoard(str(OUT), board)


def add_ground_pours(board: pcbnew.BOARD) -> None:
    """Add filled GND copper zones on both layers.

    Almost every PCB benefits from ground pours over both copper layers: it
    shortens the return path for every signal, gives the buck regulator's
    PowerPAD thermal copper to spread into, and reduces EMI. Pours are safe
    to generate from a script because they are net-aware (only fill in GND
    regions) and they are clipped automatically by KiCad against other nets'
    pads/tracks.
    """
    gnd_net = make_net(board, "GND")
    outline_clearance = 0.5  # mm inset from board edge for the pour boundary
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        zone = pcbnew.ZONE(board)
        zone.SetNet(gnd_net)
        zone.SetLayer(layer)
        zone.SetIsRuleArea(False)
        zone.SetAssignedPriority(0)
        zone.SetLocalClearance(mm(0.2))
        zone.SetMinThickness(mm(0.25))
        # Solid connection (full copper to GND pads) instead of thermal relief.
        # Thermal reliefs help hand-soldering through-hole pads, but several SMD
        # pads on the USB-C and IC packages are too close to the board edge for
        # the required two thermal spokes to fit, which produced starved-thermal
        # DRC violations. Solid copper also gives the buck regulator a stronger
        # ground return.
        zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        outline = pcbnew.SHAPE_POLY_SET()
        outline.NewOutline()
        margin = MARGIN_MM + outline_clearance
        for x, y in [
            (margin, margin),
            (BOARD_W_MM - margin, margin),
            (BOARD_W_MM - margin, BOARD_H_MM - margin),
            (margin, BOARD_H_MM - margin),
        ]:
            outline.Append(mm(x), mm(y))
        zone.AddPolygon(outline.Outline(0))
        board.Add(zone)
    # Zones are added unfilled; KiCad fills them when the board is opened or
    # when `kicad-cli pcb drc --refill-zones` runs. Calling ZONE_FILLER from a
    # freshly built BOARD that has not been saved/reloaded can segfault on
    # KiCad 10.0, so we skip the in-process fill here.


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"generate_pcb.py: {exc}", file=sys.stderr)
        raise
