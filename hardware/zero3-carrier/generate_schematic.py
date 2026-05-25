from __future__ import annotations

import uuid
from pathlib import Path


OUT = Path(__file__).with_name("zero3-water-logger-carrier.kicad_sch")
SYM_OUT = Path(__file__).with_name("water_logger_generated.kicad_sym")
SYM_TABLE_OUT = Path(__file__).with_name("sym-lib-table")
GRID = 2.54
PIN_SPACING = 2.54


def u() -> str:
    return str(uuid.uuid4())


def grid(value: float) -> float:
    return round(value / GRID) * GRID


def lib_id(ref: str) -> str:
    return f"WL:{ref}"


COMPONENTS = [
    {
        "ref": "J14",
        "value": "USB-C PD input",
        "footprint": "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12",
        "x": 25,
        "y": 35,
        "pins": [
            ("A4/B4/A9/B9", "VBUS", "USB_VBUS"),
            ("A1/B1/A12/B12", "GND", "GND"),
            ("A5", "CC1", "USB_CC1"),
            ("B5", "CC2", "USB_CC2"),
            ("SH", "SHIELD", "GND"),
        ],
    },
    {
        "ref": "D1",
        "value": "VBUS TVS",
        "footprint": "Diode_SMD:D_SMA",
        "x": 58,
        "y": 35,
        "pins": [("1", "K", "USB_VBUS"), ("2", "A", "GND")],
    },
    {
        "ref": "U1",
        "value": "CH224K PD sink 9V",
        "footprint": "Package_SO:SSOP-10_3.9x4.9mm_P1.00mm",
        "x": 88,
        "y": 35,
        "pins": [
            ("VBUS", "VBUS", "USB_VBUS"),
            ("CC1", "CC1", "USB_CC1"),
            ("CC2", "CC2", "USB_CC2"),
            ("GND", "GND", "GND"),
            ("VOUT", "VOUT", "PD_NEGOTIATED_VBUS"),
            ("CFG1", "CFG1", "PD_CFG"),
            ("CFG2", "CFG2", "PD_CFG"),
            ("CFG3", "CFG3", "PD_CFG"),
        ],
    },
    {
        "ref": "F1",
        "value": "3A-5A polyfuse",
        "footprint": "Fuse:Fuse_1206_3216Metric",
        "x": 125,
        "y": 35,
        "pins": [("1", "IN", "PD_NEGOTIATED_VBUS"), ("2", "OUT", "PD_FUSED")],
    },
    {
        "ref": "U2",
        "value": "TPS54531DDA 5A buck",
        "footprint": "Package_SO:TI_SO-PowerPAD-8",
        "x": 165,
        "y": 40,
        "pins": [
            ("VIN", "VIN", "PD_FUSED"),
            ("GND", "GND", "GND"),
            ("PH", "PH/SW", "BUCK_SW"),
            ("BOOT", "BOOT", "BUCK_BOOT"),
            ("VSENSE", "FB", "BUCK_FB"),
            ("COMP", "COMP", "BUCK_COMP"),
            ("SS", "SS", "BUCK_SS"),
            ("EN", "EN", "BUCK_EN"),
            ("PAD", "EP", "GND"),
        ],
    },
    {
        "ref": "L1",
        "value": "4.7uH >=6A",
        "footprint": "Inductor_SMD:L_10.4x10.4_H4.8",
        "x": 205,
        "y": 35,
        "pins": [("1", "SW", "BUCK_SW"), ("2", "OUT", "FUSED_5V1")],
    },
    {
        "ref": "D2",
        "value": "5A 40V Schottky",
        "footprint": "Diode_SMD:D_SMA",
        "x": 205,
        "y": 50,
        "pins": [("K", "K", "BUCK_SW"), ("A", "A", "GND")],
    },
    {
        "ref": "CIN1",
        "value": "4.7uF 50V",
        "footprint": "Capacitor_SMD:C_1206_3216Metric",
        "x": 145,
        "y": 70,
        "pins": [("1", "+", "PD_FUSED"), ("2", "-", "GND")],
    },
    {
        "ref": "CIN2",
        "value": "4.7uF 50V",
        "footprint": "Capacitor_SMD:C_1206_3216Metric",
        "x": 160,
        "y": 70,
        "pins": [("1", "+", "PD_FUSED"), ("2", "-", "GND")],
    },
    {
        "ref": "CBOOT",
        "value": "100nF",
        "footprint": "Capacitor_SMD:C_0603_1608Metric",
        "x": 185,
        "y": 70,
        "pins": [("1", "BOOT", "BUCK_BOOT"), ("2", "SW", "BUCK_SW")],
    },
    {
        "ref": "CSS",
        "value": "10nF",
        "footprint": "Capacitor_SMD:C_0603_1608Metric",
        "x": 200,
        "y": 70,
        "pins": [("1", "SS", "BUCK_SS"), ("2", "GND", "GND")],
    },
    {"ref": "REN1", "value": "665k", "footprint": "Resistor_SMD:R_0603_1608Metric", "x": 185, "y": 85, "pins": [("1", "VIN", "PD_FUSED"), ("2", "EN", "BUCK_EN")]},
    {"ref": "REN2", "value": "130k", "footprint": "Resistor_SMD:R_0603_1608Metric", "x": 200, "y": 85, "pins": [("1", "EN", "BUCK_EN"), ("2", "GND", "GND")]},
    {"ref": "RCOMP1", "value": "37.4k", "footprint": "Resistor_SMD:R_0603_1608Metric", "x": 215, "y": 85, "pins": [("1", "COMP", "BUCK_COMP"), ("2", "NODE", "BUCK_COMP_RC")]},
    {"ref": "CCOMP1", "value": "2200pF", "footprint": "Capacitor_SMD:C_0603_1608Metric", "x": 230, "y": 85, "pins": [("1", "NODE", "BUCK_COMP_RC"), ("2", "GND", "GND")]},
    {"ref": "CCOMP2", "value": "22pF", "footprint": "Capacitor_SMD:C_0603_1608Metric", "x": 245, "y": 85, "pins": [("1", "COMP", "BUCK_COMP"), ("2", "GND", "GND")]},
    {"ref": "CIN3", "value": "10nF 50V", "footprint": "Capacitor_SMD:C_0603_1608Metric", "x": 260, "y": 85, "pins": [("1", "+", "PD_FUSED"), ("2", "-", "GND")]},
    {
        "ref": "COUT1",
        "value": "47uF 10V",
        "footprint": "Capacitor_SMD:C_1210_3225Metric",
        "x": 230,
        "y": 35,
        "pins": [("1", "+", "FUSED_5V1"), ("2", "-", "GND")],
    },
    {
        "ref": "COUT2",
        "value": "47uF 10V",
        "footprint": "Capacitor_SMD:C_1210_3225Metric",
        "x": 245,
        "y": 35,
        "pins": [("1", "+", "FUSED_5V1"), ("2", "-", "GND")],
    },
    {
        "ref": "RFB1",
        "value": "10.2k 1%",
        "footprint": "Resistor_SMD:R_0603_1608Metric",
        "x": 230,
        "y": 58,
        "pins": [("1", "TOP", "FUSED_5V1"), ("2", "FB", "BUCK_FB")],
    },
    {
        "ref": "RFB2",
        "value": "1.96k 1%",
        "footprint": "Resistor_SMD:R_0603_1608Metric",
        "x": 245,
        "y": 58,
        "pins": [("1", "FB", "BUCK_FB"), ("2", "GND", "GND")],
    },
    {
        "ref": "Q1",
        "value": "AO4407A P-MOS high-side",
        "footprint": "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
        "x": 270,
        "y": 35,
        "pins": [("S", "SOURCE", "FUSED_5V1"), ("D", "DRAIN", "OPI_5V_SW"), ("G", "GATE", "PWR_GATE")],
    },
    {
        "ref": "Q2",
        "value": "2N7002",
        "footprint": "Package_TO_SOT_SMD:SOT-23",
        "x": 270,
        "y": 60,
        "pins": [("D", "DRAIN", "PWR_GATE"), ("S", "SOURCE", "GND"), ("G", "GATE", "Q2_GATE")],
    },
    {"ref": "R2", "value": "100k", "footprint": "Resistor_SMD:R_0603_1608Metric", "x": 290, "y": 45, "pins": [("1", "5V1", "FUSED_5V1"), ("2", "GATE", "PWR_GATE")]},
    {"ref": "R3", "value": "1k", "footprint": "Resistor_SMD:R_0603_1608Metric", "x": 290, "y": 60, "pins": [("1", "PICO", "PICO_GP15"), ("2", "Q2G", "Q2_GATE")]},
    {"ref": "R4", "value": "100k", "footprint": "Resistor_SMD:R_0603_1608Metric", "x": 290, "y": 72, "pins": [("1", "Q2G", "Q2_GATE"), ("2", "GND", "GND")]},
    {"ref": "C1", "value": "470uF-1000uF 10V", "footprint": "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", "x": 300, "y": 35, "pins": [("1", "+", "OPI_5V_SW"), ("2", "-", "GND")]},
    {
        "ref": "J1",
        "value": "Orange Pi Zero 3 26-pin",
        "footprint": "Connector_PinHeader_2.54mm:PinHeader_2x13_P2.54mm_Vertical",
        "x": 32,
        "y": 125,
        "pins": [
            ("1", "3V3", "OPI_3V3"), ("2", "5V", "OPI_5V_SW"), ("3", "SDA", "OPI_SDA"), ("4", "5V", "OPI_5V_SW"),
            ("5", "SCL", "OPI_SCL"), ("6", "GND", "GND"), ("7", "1WIRE", "OPI_1WIRE"), ("8", "TX", "UART_OPI_TX_PICO_RX"),
            ("9", "GND", "GND"), ("10", "RX", "UART_PICO_TX_OPI_RX"), ("11", "READY", "OPI_READY"), ("14", "GND", "GND"),
            ("17", "3V3", "OPI_3V3"), ("20", "GND", "GND"), ("25", "GND", "GND"),
        ],
    },
    {
        "ref": "J2",
        "value": "Raspberry Pi Pico socket",
        "footprint": "Module:RaspberryPi_Pico_Common_THT",
        "x": 82,
        "y": 125,
        "pins": [
            ("1", "GP0/TX", "UART_PICO_TX_OPI_RX"), ("2", "GP1/RX", "UART_OPI_TX_PICO_RX"), ("3", "GND", "GND"),
            ("6", "GP4", "PICO_GP4"), ("7", "GP5", "PICO_GP5"), ("8", "GND", "GND"), ("13", "GND", "GND"),
            ("17", "GP13", "OPI_READY"), ("18", "GND", "GND"), ("19", "GP14", "PICO_GP14"),
            ("20", "GP15", "PICO_GP15"), ("21", "GP16/LED", "PICO_LED_GP16"), ("23", "GND", "GND"),
            ("28", "GND", "GND"), ("33", "GND", "GND"), ("36", "3V3", "PICO_3V3"), ("38", "GND", "GND"),
            ("39", "VSYS", "FUSED_5V1"),
        ],
    },
    {
        "ref": "J3",
        "value": "ADS1115 #1 0x48",
        "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x09_P2.54mm_Vertical",
        "x": 135,
        "y": 120,
        "pins": [("1", "VDD", "OPI_3V3"), ("2", "GND", "GND"), ("3", "SDA", "OPI_SDA"), ("4", "SCL", "OPI_SCL"), ("5", "ADDR", "GND"), ("6", "A0", "PH_AIN"), ("7", "A1", "TDS_AIN"), ("8", "A2", "TURB_AIN"), ("9", "A3", "ORP_AIN")],
    },
    {
        "ref": "J4",
        "value": "ADS1115 #2 0x49",
        "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x09_P2.54mm_Vertical",
        "x": 170,
        "y": 120,
        "pins": [("1", "VDD", "OPI_3V3"), ("2", "GND", "GND"), ("3", "SDA", "OPI_SDA"), ("4", "SCL", "OPI_SCL"), ("5", "ADDR", "OPI_3V3"), ("6", "A0", "DO_AIN"), ("7", "A1", "NH4_AIN"), ("8", "A2", "SPARE_AIN2"), ("9", "A3", "SPARE_AIN3")],
    },
    {"ref": "J5", "value": "DS18B20 water temp", "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical", "x": 210, "y": 115, "pins": [("1", "VCC", "OPI_3V3"), ("2", "DATA", "OPI_1WIRE"), ("3", "GND", "GND")]},
    {"ref": "R1", "value": "4.7k", "footprint": "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal", "x": 210, "y": 133, "pins": [("1", "3V3", "OPI_3V3"), ("2", "DATA", "OPI_1WIRE")]},
    {"ref": "J6", "value": "BME280 air sensor", "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", "x": 245, "y": 115, "pins": [("1", "VCC", "OPI_3V3"), ("2", "GND", "GND"), ("3", "SDA", "OPI_SDA"), ("4", "SCL", "OPI_SCL")]},
    {"ref": "J7", "value": "DS3231 RTC", "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", "x": 280, "y": 115, "pins": [("1", "VCC", "PICO_3V3"), ("2", "GND", "GND"), ("3", "SDA", "PICO_GP4"), ("4", "SCL", "PICO_GP5")]},
    {"ref": "J15", "value": "Download button", "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", "x": 315, "y": 115, "pins": [("1", "NO", "PICO_GP14"), ("2", "C", "GND"), ("3", "LED+", "BUTTON_LED_A"), ("4", "LED-", "GND")]},
    {"ref": "R5", "value": "330R if 3.3V LED", "footprint": "Resistor_SMD:R_0603_1608Metric", "x": 315, "y": 133, "pins": [("1", "PICO", "PICO_LED_GP16"), ("2", "LED+", "BUTTON_LED_A")]},
    {"ref": "J16", "value": "Spare analog header", "footprint": "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", "x": 315, "y": 155, "pins": [("1", "3V3", "OPI_3V3"), ("2", "GND", "GND"), ("3", "AIN2", "SPARE_AIN2"), ("4", "AIN3", "SPARE_AIN3")]},
    {"ref": "J8", "value": "pH sensor", "footprint": "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal", "x": 30, "y": 190, "pins": [("1", "5V", "OPI_5V_SW"), ("2", "GND", "GND"), ("3", "AO", "PH_AIN")]},
    {"ref": "J9", "value": "TDS sensor", "footprint": "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal", "x": 70, "y": 190, "pins": [("1", "5V", "OPI_5V_SW"), ("2", "GND", "GND"), ("3", "AO", "TDS_AIN")]},
    {"ref": "J10", "value": "Turbidity sensor", "footprint": "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal", "x": 110, "y": 190, "pins": [("1", "5V", "OPI_5V_SW"), ("2", "GND", "GND"), ("3", "AO", "TURB_AIN")]},
    {"ref": "J11", "value": "ORP sensor", "footprint": "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal", "x": 150, "y": 190, "pins": [("1", "5V", "OPI_5V_SW"), ("2", "GND", "GND"), ("3", "AO", "ORP_AIN")]},
    {"ref": "J12", "value": "Dissolved oxygen", "footprint": "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal", "x": 190, "y": 190, "pins": [("1", "5V", "OPI_5V_SW"), ("2", "GND", "GND"), ("3", "AO", "DO_AIN")]},
    {"ref": "J13", "value": "NH4 ISE amp", "footprint": "TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-3-5.08_1x03_P5.08mm_Horizontal", "x": 230, "y": 190, "pins": [("1", "5V", "OPI_5V_SW"), ("2", "GND", "GND"), ("3", "AO", "NH4_AIN")]},
]


def pin_line(num: str, name: str, y: float) -> str:
    return f'''
			(pin passive line
				(at {-4 * GRID:.2f} {y:.2f} 180)
				(length 2.54)
				(name "{name}" (effects (font (size 1 1))))
				(number "{num}" (effects (font (size 1 1))))
			)'''


def lib_symbol(comp: dict) -> str:
    n = len(comp["pins"])
    height = max(5 * GRID, (n + 3) * PIN_SPACING)
    top = -height / 2
    bottom = height / 2
    first_pin_y = -((n - 1) * PIN_SPACING) / 2
    pins = "\n".join(pin_line(num, name, first_pin_y + i * PIN_SPACING) for i, (num, name, _net) in enumerate(comp["pins"]))
    return f'''
		(symbol "{lib_id(comp["ref"])}"
			(exclude_from_sim no)
			(in_bom yes)
			(on_board yes)
			(property "Reference" "{comp["ref"][0]}"
				(at {-3 * GRID:.2f} {top - GRID:.2f} 0)
				(effects (font (size 1.27 1.27)))
			)
			(property "Value" "{comp["value"]}"
				(at {-3 * GRID:.2f} {bottom + GRID:.2f} 0)
				(effects (font (size 1.27 1.27)))
			)
			(property "Footprint" "{comp["footprint"]}"
				(at 0 {bottom + 2 * GRID:.2f} 0)
				(hide yes)
				(effects (font (size 1.27 1.27)))
			)
			(property "Datasheet" ""
				(at 0 {bottom + 3 * GRID:.2f} 0)
				(hide yes)
				(effects (font (size 1.27 1.27)))
			)
			(rectangle
				(start {-4 * GRID:.2f} {top:.2f})
				(end {4 * GRID:.2f} {bottom:.2f})
				(stroke (width 0.254) (type default))
				(fill (type background))
			){pins}
		)'''


def placed_symbol(comp: dict) -> str:
    x = grid(comp["x"])
    y = grid(comp["y"])
    pins = "\n".join(f'''
		(pin "{num}" (uuid "{u()}"))''' for num, _name, _net in comp["pins"])
    return f'''
	(symbol
		(lib_id "{lib_id(comp["ref"])}")
		(at {x:.2f} {y:.2f} 0)
		(unit 1)
		(exclude_from_sim no)
		(in_bom yes)
		(on_board yes)
		(dnp no)
		(uuid "{u()}")
		(property "Reference" "{comp["ref"]}"
			(at {x - 3 * GRID:.2f} {y - 4 * GRID:.2f} 0)
			(effects (font (size 1.27 1.27)))
		)
		(property "Value" "{comp["value"]}"
			(at {x - 3 * GRID:.2f} {y + 4 * GRID:.2f} 0)
			(effects (font (size 1.27 1.27)))
		)
		(property "Footprint" "{comp["footprint"]}"
			(at {x:.2f} {y + 5 * GRID:.2f} 0)
			(hide yes)
			(effects (font (size 1.27 1.27)))
		)
		(property "Datasheet" ""
			(at {x:.2f} {y + 6 * GRID:.2f} 0)
			(hide yes)
			(effects (font (size 1.27 1.27)))
		){pins}
		(instances
			(project "zero3-water-logger-carrier"
				(path "/{u()}" (reference "{comp["ref"]}") (unit 1))
			)
		)
	)'''


def labels_for(comp: dict) -> str:
    n = len(comp["pins"])
    x = grid(comp["x"])
    y0 = grid(comp["y"])
    first_pin_y = -((n - 1) * PIN_SPACING) / 2
    out = []
    for i, (_num, _name, net) in enumerate(comp["pins"]):
        # KiCad symbol-local Y is inverted when placed on the schematic sheet.
        y = y0 - (first_pin_y + i * PIN_SPACING)
        x_pin = x - 4 * GRID
        out.append(f'''
	(label "{net}"
		(at {x_pin:.2f} {y:.2f} 180)
		(effects (font (size 1.0 1.0)) (justify right bottom))
		(uuid "{u()}")
	)''')
    return "\n".join(out)


def text_note(txt: str, x: float, y: float) -> str:
    return f'''
	(text "{txt}"
		(exclude_from_sim no)
		(at {x:.2f} {y:.2f} 0)
		(effects (font (size 1.5 1.5)))
		(uuid "{u()}")
	)'''


def main() -> None:
    lib = "\n".join(lib_symbol(c) for c in COMPONENTS)
    syms = "\n".join(placed_symbol(c) for c in COMPONENTS)
    labels = "\n".join(labels_for(c) for c in COMPONENTS)
    notes = "\n".join([
        text_note("USB-C PD front end: CH224K requests 9V, TPS54531 generates protected 5.1V.", 20, 15),
        text_note("Pico is always-on from FUSED_5V1. Orange Pi and wet-side sensor 5V are switched by Q1.", 20, 22),
        text_note("Buck regulator PCB layout must follow TPS54531 datasheet: short SW loop, thermal copper, tight input caps.", 20, 235),
        text_note("Verify CH224K strap pins and all package pinouts against supplier datasheets before PCB order.", 20, 243),
    ])
    content = f'''(kicad_sch
	(version 20260306)
	(generator "eeschema")
	(generator_version "10.0")
	(uuid "{u()}")
	(paper "A3")
	(title_block
		(title "Orange Pi Zero 3 Water Logger Carrier")
		(date "2026-05-25")
		(rev "R1 schematic draft")
		(company "Water Logger")
		(comment 1 "USB-C PD, buck regulator, Pico controller, Orange Pi header, ADCs, sensors, and RTC.")
		(comment 2 "Review selected IC pinouts and buck layout before PCB manufacture.")
	)
	(lib_symbols{lib}
	)
{notes}
{labels}
{syms}
	(sheet_instances
		(path "/" (page "1"))
	)
)'''
    OUT.write_text(content, encoding="utf-8")
    SYM_OUT.write_text(
        f'''(kicad_symbol_lib
	(version 20241209)
	(generator "generate_schematic.py")
	(generator_version "1")
{lib}
)''',
        encoding="utf-8",
    )
    SYM_TABLE_OUT.write_text(
        '''(sym_lib_table
  (lib (name "WL")(type "KiCad")(uri "${KIPRJMOD}/water_logger_generated.kicad_sym")(options "")(descr "Generated water logger schematic symbols"))
)
''',
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
