"""Mechanical numbers shared by the board generator and the 3D-print generator.

One source of truth: the printed owl, the bat's cap and the feet are drawn from
these, and so are the boards they clip onto, so the prints fit the boards by
construction.  Millimetres.  Board coordinates: x right, y down (KiCad), origin
at each board's own reference point named below.

The physics behind the magnet heights is in sim/physics/levitation_onemagnet.py.
"""

# --- the one magnet Jason buys ---------------------------------------------------
MAGNET_D = 10.0          # N52 NdFeB disc, axially magnetised
MAGNET_T = 2.0
POCKET_D = 10.35         # printed pocket: PLA prints holes ~0.15-0.2 mm small
POCKET_T = 2.25

# --- boards --------------------------------------------------------------------------
PCB_T = 1.6              # every board on the panel (JLC04161H stack-up)
COPPER_TO_SURFACE = 0.05 # top copper to the top of the solder mask, roughly

# --- the perch (horizontal, plugs onto the tree's top header) ------------------------
# Origin: the levitation coil's centre.  The board runs from the coil (front, -y,
# toward the viewer) back to the socket over the tree (+y).
PERCH_W = 34.0           # across (x), wider than the coil
PERCH_FRONT = -18.0      # y of the front edge (the owl slides on from here)
PERCH_BACK = 38.0        # y of the back edge, behind the socket
COIL_R_OUT = 15.0        # the levitation coil (4 layers)
COIL_R_IN = 3.0
COIL_TURNS = 12          # per layer, 0.6 mm track at 1 mm pitch
# The owl: a U-channel that slides onto the perch from the front edge, gripping the
# board's two side edges, stopped by a key in a notch, with the bias magnet in its
# body.  The magnet's bottom face sits OWL_LIFT above the perch's top copper.
OWL_LIFT = 14.0
OWL_NOTCH_W = 3.0        # notch in the perch's front edge, centred on x = 0
OWL_NOTCH_D = 2.0
OWL_CHANNEL_GAP = PCB_T + 0.25     # slot the board slides into
# A 1.2 mm hole for the pendulum's thread, in front of the coil (the bat hangs from it
# when it swings instead of floating).
THREAD_HOLE = (0.0, PERCH_FRONT + 2.5)
THREAD_HOLE_D = 1.2

# --- the bat (horizontal while floating; flies in the +y direction... toward the
# viewer is -y) ---------------------------------------------------------------------------
# Origin: the magnet's axis.  Its receive coil (4 layers, fine pitch) surrounds it.
BAT_SPAN = 48.0          # wingtip to wingtip (x)
BAT_HEAD_Y = -13.0       # front edge of the head (toward the viewer)
BAT_TAIL_Y = 12.0        # back edge of the body
RX_R_OUT = 11.0
RX_R_IN = 7.0
# The cap: a dome over the magnet whose two arms reach the head and tail edges and
# hook under them (no holes through the coil).  The magnet sits on the bat's top
# surface, centred, inside the dome.
CAP_ARM_W = 5.0          # arm width where it hooks the edge
CAP_HOOK = 0.8           # how far each hook reaches under the board

# --- the base ------------------------------------------------------------------------
BASE_W = 170.0
BASE_H = 120.0
FOOT_HOLE_D = 3.2        # the printed feet snap into these
FOOT_INSET = 5.0         # hole centres from the board's corners (x and y)
FOOT_HEIGHT = 6.0        # clears the through-hole pins (about 2 mm) with room
