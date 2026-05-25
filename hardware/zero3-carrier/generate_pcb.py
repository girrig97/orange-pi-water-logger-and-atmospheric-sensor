from __future__ import annotations

import math
import sys
from pathlib import Path

import pcbnew

import generate_schematic


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "zero3-water-logger-carrier.kicad_pcb"
FP_ROOT = Path(r"C:\Program Files\KiCad\10.0\share\kicad\footprints")

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


def route_to_backbone(board: pcbnew.BOARD) -> None:
    pads_by_net: dict[str, list[pcbnew.PAD]] = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            net = pad.GetNetname()
            if not net:
                continue
            pads_by_net.setdefault(net, []).append(pad)

    multi_pin_nets = sorted((name, pads) for name, pads in pads_by_net.items() if len(pads) > 1)
    bus_start_y = 240.0
    bus_pitch = 2.2

    for net_index, (net_name, pads) in enumerate(multi_pin_nets):
        net = make_net(board, net_name)
        bus_y = bus_start_y + net_index * bus_pitch
        bus_points: list[pcbnew.VECTOR2I] = []

        for pad_index, pad in enumerate(pads):
            fp = pad.GetParentFootprint()
            left, top, right, bottom = bbox_mm(fp)
            center_x = (left + right) / 2
            center_y = (top + bottom) / 2
            pos = pad.GetPosition()
            px = pcbnew.ToMM(pos.x)
            py = pcbnew.ToMM(pos.y)

            route_left = px < center_x
            channel_x = (left - 3.0 - pad_index * 0.18) if route_left else (right + 3.0 + pad_index * 0.18)
            escape_y = (top - 3.0) if py < center_y else (bottom + 3.0)

            p0 = pos
            p1 = v(px, escape_y)
            p2 = v(channel_x, escape_y)
            p3 = v(channel_x, bus_y)

            add_track(board, net, p0, p1, pcbnew.F_Cu)
            add_track(board, net, p1, p2, pcbnew.F_Cu)
            add_track(board, net, p2, p3, pcbnew.F_Cu)
            add_via(board, net, p3)
            bus_points.append(p3)

        bus_points.sort(key=lambda point: point.x)
        for a, b in zip(bus_points, bus_points[1:]):
            add_track(board, net, a, b, pcbnew.B_Cu)


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
    for ref, x, y in [
        ("H1", 16, 16),
        ("H2", BOARD_W_MM - 16, 16),
        ("H3", BOARD_W_MM - 16, BOARD_H_MM - 16),
        ("H4", 16, BOARD_H_MM - 16),
    ]:
        hole = pcbnew.FootprintLoad(str(FP_ROOT / "MountingHole.pretty"), "MountingHole_3.2mm_M3")
        if hole is None:
            continue
        hole.SetReference(ref)
        hole.SetPosition(v(x, y))
        board.Add(hole)


def main() -> None:
    board = pcbnew.BOARD()
    board.SetTitleBlock(pcbnew.TITLE_BLOCK())
    title = board.GetTitleBlock()
    title.SetTitle("Orange Pi Zero 3 Water Logger Carrier")
    title.SetDate("2026-05-25")
    title.SetRevision("R1 generated routed draft")
    title.SetCompany("Water Logger")

    add_outline(board)
    add_mounting_holes(board)
    place_components(board)
    # The PCB is generated with real footprints and schematic nets assigned.
    # Do not auto-route here. A simple generated backbone can create unsafe
    # shorts around dense headers and IC pads; routing must be completed and
    # reviewed in KiCad before fabrication.

    pcbnew.SaveBoard(str(OUT), board)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"generate_pcb.py: {exc}", file=sys.stderr)
        raise
