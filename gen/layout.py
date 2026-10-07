"""The floor plan: where everything sits on each board of the panel.

The one source of truth for the board generator (gen/board.py, gen/placement.py), the
art (gen/art.py), the coils (gen/coils.py) and the 3D prints (print/, through
gen/mech.py).  Millimetres; each board's own frame: origin at its top-left corner as
drawn in KiCad, x right, y down.  On the base, "top" (F.Cu) is the scene the child
looks at, and y grows toward the viewer: the back edge (y = 0) carries the plugs, the
front edge (y = BASE_H) faces her.

Sides.  Every board is assembled on both sides, so that the top is the scene and
nothing else: on the base, the LEDs, the coils, the moon and the ghost (the theremin's
antennas, bare gold copper), the tree's socket, the jack, USB, the speaker and the two
switches are on top; the electronics are underneath, with the spell book (the board's
physics, in silkscreen) and her name.  On the tree, the LEDs face the room and its
LED driver hides on the back.  The perch carries its parts underneath (the owl clips
on top); the tokens carry theirs on top (they lie flat on their perches).

Coils and antennas are keep-outs on every layer: no part, track or plane under a coil
(it would be a shorted turn, or take its field) or under an antenna (a plane under the
moon would add 300 pF and drown a hand's half picofarad).
"""
import math

# ======================================================================================
# The base
# ======================================================================================
BASE_W, BASE_H, BASE_R = 190.0, 130.0, 6.0       # corner radius

# the tree stands in J3; its board is parallel to the front edge, J3's long axis along x
TREE_SOCKET = (105.0, 40.0)                      # J3's centre (the tree's plane runs through it)

# the perch reaches forward from the top of the tree: the levitating bat floats under its
# coil, and the pendulum's thread hangs from its front, so the pendulum's rest point is
# this far in front of the tree's plane (gen/mech.py: the perch's socket at y = +32 in
# its own frame, the coil at 0, the thread hole at -15.5)
PERCH_SOCKET_Y = 32.0
BAT_AHEAD = PERCH_SOCKET_Y                       # 32 mm in front of the tree
THREAD_AHEAD = PERCH_SOCKET_Y + 15.5             # 47.5 mm
PEND_REST = (TREE_SOCKET[0], TREE_SOCKET[1] + THREAD_AHEAD)
# three pendulum coils round the rest point: 18 mm out (30 mm coils: centres 31.2 mm
# apart, just clear of each other), one in front, two behind at the sides
PEND_R = 18.0
PEND_COILS = {"L3": 90.0, "L4": 210.0, "L5": 330.0}          # degrees, 90 = toward the viewer
COIL_R = 15.0                                    # every base coil (gen/parts.py COILS r_out)
COIL_KEEPOUT = 0.3                               # beyond r_out, on every layer (courtyard r_out + 0.25):
                                                 # the TMAG5273 between the pendulum coils needs the room


def pend_coil(ref):
    a = math.radians(PEND_COILS[ref])
    return (PEND_REST[0] + PEND_R * math.cos(a), PEND_REST[1] + PEND_R * math.sin(a))


# the familiars' perches: a coil, its three ring LEDs 120 degrees apart, and the drawn
# circle the token sits in
OWL_PERCH = (38.0, 88.0)
CAT_PERCH = (166.0, 86.0)
RING_R = 19.0                                    # the ring LEDs' circle round each perch
RING_ANGLES = (90.0, 210.0, 330.0)
PERCH_ART_R = 21.0                               # the token's circle, silkscreen

# the theremin's two antennas: bare (ENIG gold) copper shapes, no copper under them on
# any layer
MOON = (36.0, 34.0, 21.0)                        # centre x, y, radius: the pitch antenna
GHOST = (22.0, 112.0, 11.0)                      # centre x, y, half-height: the volume antenna
ANTENNA_KEEPOUT = 3.0                            # beyond the shape, on every layer

# the three pumpkins (5050 orange LEDs behind their faces), along the front
PUMPKINS = [(62.0, 118.0, 9.0), (80.0, 121.0, 7.0), (140.0, 120.0, 8.0)]   # x, y, size

# the hill along the front, with the six wisps on it, left to right
WISPS = [(48.0, 106.0), (68.0, 102.0), (84.0, 99.0), (128.0, 99.0), (146.0, 103.0), (178.0, 108.0)]

# the stars: twelve on a shallow arc across the open band between the tree and the
# pendulum (the quantum ghost walks it, STAR0 at the left), four more scattered in the sky
# (the moon's side and behind; behind the tree itself sit the RP2354A and its parts)
STAR_ARC = dict(cx=107.0, cy=160.0, r=105.0, a0=245.0, a1=295.0)    # degrees, on the arc
STARX = [(68.0, 10.0), (128.0, 10.0), (72.0, 44.0), (182.0, 62.0)]


def star_arc():
    a = STAR_ARC
    pts = []
    for i in range(12):
        t = math.radians(a["a0"] + (a["a1"] - a["a0"]) * i / 11.0)
        pts.append((a["cx"] + a["r"] * math.cos(t), a["cy"] + a["r"] * math.sin(t)))
    return pts


# what the child touches and the plugs: on top.  The RP2354A's corner of the board (its
# USB and debug plugs) is behind the tree, where the tree hides it from the front.
MCU = (105.0, 15.0)                              # U4, on top, behind the tree
JACK = (150.0, 10.15)                            # J1: plug from the back edge
USB = (95.0, 2.45)                               # J2: plug from the back edge (GPiBridge's USB layout)
SPEAKER = (176.0, 36.0)                          # LS1, 23 mm
SOUND_SWITCH = (183.0, 118.0)                    # SW3, its lever at the right edge
SPELL_BUTTON = (168.0, 121.0)                    # SW2
LIGHT_SENSOR = (150.0, 26.0)                     # U16 looks at the room
BOOT_BUTTON_BOTTOM = (60.0, 30.0)                # SW1, underneath

# the feet (printed, gen/mech.py): holes at the corners
FOOT_INSET = 6.0
FEET = [(FOOT_INSET, FOOT_INSET), (BASE_W - FOOT_INSET, FOOT_INSET), (FOOT_INSET, BASE_H - FOOT_INSET),
        (BASE_W - FOOT_INSET, BASE_H - FOOT_INSET)]

# the electronics underneath, by block (centres; B.Cu, seen from the top)
BLOCKS = {
    "power": (40.0, 62.0),          # F1, Q1, D2, U1, L1, the 12 V bulk (C1 stays on top: it is tall)
    "mcu": (75.0, 35.0),            # U4, its supply parts, the crystal, USB and debug
    "leds": (95.0, 60.0),           # U3 and its parts
    "drv": (140.0, 40.0),           # U5-U8 with their current sense
    "mux": (120.0, 60.0),           # U11, U18, the dividers
    "audio": (165.0, 60.0),         # U14 and its filter, under the speaker's side
    "theremin": (60.0, 75.0),       # U12, U13 near the moon and the ghost
    "sensors": (PEND_REST[0], PEND_REST[1]),   # U17 under the pendulum's rest point; U15
    "owl_bridge": (OWL_PERCH[0] + 28.0, OWL_PERCH[1] - 8.0),
    "cat_bridge": (CAT_PERCH[0] - 28.0, CAT_PERCH[1] - 30.0),
}

# ======================================================================================
# The tree (stands in J3; its front faces the room)
# ======================================================================================
TREE_W, TREE_H = 76.0, 112.0
TREE_BASE_PLUG = (TREE_W / 2, TREE_H)            # J101's pins come out of the bottom edge here
TREE_TOP_PLUG = (TREE_W / 2, 0.0)                # J102's out of the top edge
OWLS = [(18.0, 52.0), (58.0, 38.0), (40.0, 80.0)]   # owls A, B, C: centre of each owl's face
OWL_EYE_SPACING = 7.0                            # between an owl's two eye LEDs
TREE_STARS = [(10.0, 20.0), (66.0, 14.0), (30.0, 30.0), (12.0, 70.0), (66.0, 66.0), (52.0, 96.0)]
TREE_WISPS = [(22.0, 96.0), (60.0, 86.0), (8.0, 40.0), (70.0, 30.0)]

# ======================================================================================
# The perch (horizontal on top of the tree; gen/mech.py has its shared numbers)
# ======================================================================================
PERCH_W, PERCH_FRONT, PERCH_BACK = 34.0, -18.0, 38.0     # the coil's centre is (0, 0)

# ======================================================================================
# The bat and the two tokens
# ======================================================================================
import mech as _M
BAT_SPAN = _M.BAT_SPAN                                   # the magnet's axis is (0, 0)
BAT_HEAD_Y = _M.BAT_HEAD_Y - _M.BAT_NOTCH_D              # the head edge (-13.0)
BAT_TAIL_Y = _M.BAT_TAIL_Y + _M.BAT_NOTCH_D              # the tail edge (+12.0)
BAT_NOTCH_W, BAT_NOTCH_D = _M.BAT_NOTCH_W, _M.BAT_NOTCH_D   # notches at x = 0 in both edges
TOKEN_R = 19.0                                           # each token: an owl or a cat, 38 mm

# ======================================================================================
# The panel: every board, with mouse-bite tabs, on one 4-layer panel (JLCPCB standard
# PCBA: purple mask on 4 layers needs it, and it sets a 70 x 70 mm minimum, which the
# small boards meet only together)
# ======================================================================================
RAIL = 5.0                                       # the panel's frame
GAP = 2.4                                        # routed slot between boards (mouse bites bridge it)
PANEL_OFFSETS = {                                # where each board's origin sits in the panel
    "base": (RAIL + GAP, RAIL + GAP),
    "tree": (RAIL + GAP + BASE_W + GAP, RAIL + GAP),
    "perch": (RAIL + GAP + BASE_W + GAP + TREE_W + GAP + PERCH_W / 2, RAIL + GAP - PERCH_FRONT),
    "bat": (RAIL + GAP + BASE_W + GAP + TREE_W / 2, RAIL + GAP + TREE_H + GAP - BAT_HEAD_Y),
    "owl_token": (RAIL + GAP + BASE_W + GAP + TREE_W + GAP + TOKEN_R, RAIL + GAP + (PERCH_BACK - PERCH_FRONT) + GAP + TOKEN_R),
    "cat_token": (RAIL + GAP + BASE_W + GAP + TREE_W + GAP + TOKEN_R, RAIL + GAP + (PERCH_BACK - PERCH_FRONT) + GAP + 2 * TOKEN_R + GAP + TOKEN_R),
}
