#!/usr/bin/env python3
"""Drive Freerouting against the carrier PCB.

Workflow:
  1. Export the current PCB to a Specctra DSN file via `kicad-cli pcb export specctra`.
  2. Download `freerouting.jar` (release pinned below) if it is not already cached.
  3. Run Freerouting headlessly to produce an SES routing session file.
  4. Import the SES back into the PCB and save.
  5. Re-fill zones and run DRC.

Usage:
    python route_with_freerouting.py [--effort fast|medium|thorough]

The Freerouting JAR is fetched from the freerouting/freerouting GitHub release
the first time the script runs and cached under ~/.cache/freerouting/. Use the
`FREEROUTING_JAR` environment variable to point at a copy you already have.

Important: Freerouting is a general-purpose auto-router. It does not understand
switching-supply layout rules. After routing, you still must open the PCB in
KiCad and manually re-route the TPS54531 buck regulator section per the TI
reference layout (short SW loop, tight input caps, large GND polygon, thermal
copper for the PowerPAD), and check the high-side MOSFET switch around Q1.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PCB = ROOT / "zero3-water-logger-carrier.kicad_pcb"
DSN = ROOT / "zero3-water-logger-carrier.dsn"
SES = ROOT / "zero3-water-logger-carrier.ses"

FREEROUTING_VERSION = "2.2.4"
FREEROUTING_URL = (
    f"https://github.com/freerouting/freerouting/releases/download/"
    f"v{FREEROUTING_VERSION}/freerouting-{FREEROUTING_VERSION}.jar"
)


def find_kicad_cli() -> str:
    """Locate kicad-cli on Windows, macOS, or Linux."""
    candidates = [
        r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe",
        r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
        "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
        "/usr/bin/kicad-cli",
        "/usr/local/bin/kicad-cli",
    ]
    on_path = shutil.which("kicad-cli")
    if on_path:
        return on_path
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    sys.exit("error: kicad-cli not found. Install KiCad 9+ or add it to PATH.")


def find_java() -> str:
    """Locate a Java 17+ runtime."""
    on_path = shutil.which("java")
    if on_path:
        return on_path
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidate = Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")
        if candidate.exists():
            return str(candidate)
    sys.exit("error: java not found. Install a JRE 17+ or set JAVA_HOME.")


def ensure_freerouting_jar() -> Path:
    """Return a path to freerouting.jar, downloading it if necessary."""
    env_jar = os.environ.get("FREEROUTING_JAR")
    if env_jar:
        return Path(env_jar)
    cache_dir = Path.home() / ".cache" / "freerouting"
    cache_dir.mkdir(parents=True, exist_ok=True)
    jar = cache_dir / f"freerouting-{FREEROUTING_VERSION}.jar"
    if jar.exists():
        return jar
    print(f"Downloading {FREEROUTING_URL} ...")
    urllib.request.urlretrieve(FREEROUTING_URL, jar)
    print(f"Saved to {jar} ({jar.stat().st_size} bytes)")
    return jar


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--effort",
        choices=("fast", "medium", "thorough"),
        default="medium",
        help="Routing effort (passes Freerouting --postroute / --passes settings).",
    )
    args = parser.parse_args()

    kicad_cli = find_kicad_cli()
    java = find_java()
    jar = ensure_freerouting_jar()

    print(f"Exporting Specctra DSN from {PCB.name} ...")
    subprocess.check_call(
        [kicad_cli, "pcb", "export", "specctra", "--output", str(DSN), str(PCB)]
    )

    passes = {"fast": "5", "medium": "20", "thorough": "100"}[args.effort]
    print(f"Running Freerouting (effort={args.effort}, max {passes} passes) ...")
    subprocess.check_call(
        [
            java,
            "-jar",
            str(jar),
            "-de", str(DSN),
            "-do", str(SES),
            "-mp", passes,
            "-im",  # idle mode = exit after routing
        ]
    )

    print(f"Importing {SES.name} back into {PCB.name} ...")
    subprocess.check_call(
        [kicad_cli, "pcb", "import", "specctra", "--input", str(SES), str(PCB)]
    )

    print("Refilling zones and running DRC ...")
    subprocess.check_call(
        [
            kicad_cli, "pcb", "drc",
            "--refill-zones", "--save-board",
            str(PCB),
        ]
    )

    print()
    print("Routing pass complete. Open the PCB in KiCad to review.")
    print("REQUIRED MANUAL STEP: re-route the TPS54531 buck regulator section")
    print("(U2, L1, D2, CIN1-3, COUT1-2, CBOOT, CSS, RFB1/2, REN1/2, RCOMP1,")
    print("CCOMP1/2) per the TI reference layout, and the high-side switch")
    print("around Q1/Q2 before exporting Gerbers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
