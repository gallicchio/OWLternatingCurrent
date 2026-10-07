"""The board's identity, in one place: the schematic's title block, the
silkscreen, the release files and the firmware's version string read it.

The name, chosen by Jason on 2026-10-07, lives here and nowhere else.  DATE is the design date, written by the build into
the silkscreen; a release made before the board is ordered is a DRAFT.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAMILY = "OWLternatingCurrent"
NAME = "OWLternatingCurrent"          # its files' name
TITLE = "OWLternating Current"        # Jason, 2026-10-07 (Prompt 2)
TAGLINE = "a cute, physics-y Halloween board"
REV = "A"
DATE = "2026-10-07"
AUTHORS = "Jason Gallicchio and Claude"
URL = "github.com/gallicchio/OWLternatingCurrent"
LICENCE = "Hardware CERN-OHL-P-2.0, software MIT"

HW = os.path.join(ROOT, "hardware")
PCB = os.path.join(HW, NAME + ".kicad_pcb")
SCH = os.path.join(HW, NAME + ".kicad_sch")
CHECKS = os.path.join(HW, "checks")
NETLIST = os.path.join(CHECKS, "netlist.net")
RELEASE = os.path.join(ROOT, "mfg", "release")
IMAGE_PREFIX = ""
SCRATCH = os.path.join(ROOT, "build", NAME)

# Printed on the back with the "spell book" of the board's physics.  Jason supplies the
# name (QUESTIONS.md); until then the build prints the placeholder and stamps the release
# DRAFT.
FOR_NAME = None
