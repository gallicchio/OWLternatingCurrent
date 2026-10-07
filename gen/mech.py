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
PERCH_FRONT = -18.0      # y of the front edge (toward the viewer)
PERCH_BACK = 38.0        # y of the back edge, behind the socket
COIL_R_OUT = 15.0        # the levitation coil: three layers (F.Cu, In1, In2; B.Cu stays free
COIL_R_IN = 4.0          # for the Hall sensor's lines), about 14 turns each of 0.5 mm track
COIL_TURNS = 14          # (gen/parts.py COILS["COIL_LEV"], drawn by gen/coils.py)
# The owl holds the bias magnet: its body stands over the coil's centre, and two
# springy arms snap round the perch's side edges into notches that fix it in y.
# The magnet's bottom face sits OWL_LIFT above the perch's top copper.
OWL_LIFT = 14.0
OWL_NOTCH_Y = (-3.0, 3.0)    # notches in both side edges (x = +-PERCH_W/2), this long
OWL_NOTCH_D = 1.0            # and this deep
OWL_HOOK = 0.8               # how far each arm's hook reaches under the board
OWL_KEEPOUT = 2.0            # copper- and part-free band inside each side edge near the notches
# A 1.2 mm hole for the pendulum's thread, in front of the coil (the bat hangs from it
# when it swings instead of floating): clear of the coil's keep-out (r 15.3) by 0.7 mm,
# 0.8 mm of board in front of it.
THREAD_HOLE = (0.0, -16.6)
THREAD_HOLE_D = 1.2

# --- the bat (horizontal while it floats; its head points toward the viewer, -y) --
# Origin: the magnet's axis.  Its receive coil (4 layers, fine pitch) surrounds it.
BAT_SPAN = 48.0          # wingtip to wingtip (x)
# The head and tail edges carry a notch at x = 0, BAT_NOTCH_W wide and BAT_NOTCH_D deep,
# where the cap's drops sit: it pins the cap sideways (print/README.md, designer notes).
# BAT_HEAD_Y and BAT_TAIL_Y are the notch bottoms, where the cap hooks; the board's
# edges are BAT_NOTCH_D beyond them.
BAT_NOTCH_W = 5.4
BAT_NOTCH_D = 0.5
BAT_HEAD_Y = -12.5       # the head notch's bottom (the head edge is at -13.0, toward the viewer)
BAT_TAIL_Y = 11.5        # the tail notch's bottom (the tail edge is at +12.0)
RX_R_OUT = 11.0
RX_R_IN = 7.0
# The cap: a dome over the magnet whose two arms reach the head and tail edges and
# hook under them (no holes through the coil).  The magnet sits on the bat's top
# surface, centred, inside the dome.
CAP_ARM_W = 5.0          # arm width where it hooks the edge
CAP_HOOK = 0.8           # how far each hook reaches under the board

# --- the base (gen/layout.py has its size, 190 x 130 mm) ------------------------------
FOOT_HOLE_D = 3.2        # the printed feet snap into these
FOOT_INSET = 6.0         # hole centres from the board's corners (x and y): gen/layout.py's
FOOT_HEIGHT = 6.0        # clears the through-hole pins (about 2 mm) with room
