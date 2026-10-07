"""The board's identity, in one place: the schematic's title block, the
silkscreen, the release files and the firmware's version string read it.

The name is a working name until Jason chooses one (PLAN.md section 6); change
it here and nowhere else.  DATE is the design date, written by the build into
the silkscreen; a release made before the board is ordered is a DRAFT.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAMILY = "halloween1"
NAME = "halloween1"                   # its files' name (working name)
TITLE = "Hocus Flux"                  # what it calls itself (proposed in PLAN.md §6, not yet chosen)
TAGLINE = "a cute, physics-y Halloween board"
REV = "A"
DATE = "2026-10-07"
AUTHORS = "Jason Gallicchio and Claude"
URL = "github.com/gallicchio/halloween1"   # until the name is chosen
LICENCE = "Hardware CERN-OHL-P-2.0, software MIT"

HW = os.path.join(ROOT, "hardware")
PCB = os.path.join(HW, NAME + ".kicad_pcb")
SCH = os.path.join(HW, NAME + ".kicad_sch")
CHECKS = os.path.join(HW, "checks")
NETLIST = os.path.join(CHECKS, "netlist.net")
RELEASE = os.path.join(ROOT, "mfg", "release")
IMAGE_PREFIX = ""
SCRATCH = os.path.join(ROOT, "build", NAME)
