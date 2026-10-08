"""Where every part goes, board by board: millimetres in the board's own frame
(gen/layout.py), x right, y down; rotation in degrees counter-clockwise (KiCad's); side
F (top) or B (bottom).

Parts are named by their role (hardware/checks/roles.json, written by the schematic
generator) or by their fixed reference, so renumbering a sheet moves nothing.

A footprint on the bottom is mirrored in y and then turned (KiCad 10 measured: a part
flipped with FLIP_DIRECTION_LEFT_RIGHT and set to 0 degrees has its pads at (x, -y)), so
a local offset (lx, ly) of a part at (x, y, rot, side) lands at rel(rot, side, lx, ly).

The base: the RP2354A's corner is GPiBridge's layout exactly (its gen/placement.py),
turned 90 degrees clockwise so that the USB-C faces the back edge, on top behind the
tree.  The scene (LEDs, coils, the antennas' pads, the socket, the jack, the speaker,
the switches) is on top where gen/layout.py puts it.  Everything else is underneath,
each block beside what it drives.
"""
import json, math, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
import layout as L
import mech as M

ROLES = json.load(open(os.path.join(ROOT, "hardware", "checks", "roles.json")))


def rel(rot, side, lx, ly):
    """A part-local offset turned and (on the bottom) mirrored onto the board."""
    if side == "B":
        ly = -ly
    a = math.radians(rot)
    return (lx * math.cos(a) + ly * math.sin(a), -lx * math.sin(a) + ly * math.cos(a))


class Board:
    def __init__(self, name):
        self.name, self.place = name, {}

    def put(self, who, x, y, rot=0, side="F"):
        ref = ROLES.get(who, who)
        assert ref not in self.place, "%s (%s) placed twice" % (who, ref)
        self.place[ref] = (round(x, 4), round(y, 4), rot % 360, side)
        return ref

    def near(self, who, ref, lx, ly, rot=0):
        """`who` at local offset (lx, ly) from part `ref`, on its side, turned with it."""
        x, y, r0, side = self.place[ROLES.get(ref, ref)]
        dx, dy = rel(r0, side, lx, ly)
        return self.put(who, x + dx, y + dy, (r0 + rot) % 360, side)


# ======================================================================================
# The base
# ======================================================================================
BASE = Board("base")
b = BASE

# ---- the RP2354A's corner, on top behind the tree: GPiBridge's coordinates, turned
G_U1 = (15.0, 10.0)                       # their U1, at 180 degrees


def gp(x, y, rot, who):
    dx, dy = x - G_U1[0], y - G_U1[1]
    return b.put(who, L.MCU[0] - dy, L.MCU[1] + dx, rot - 90, "F")


gp(15.0, 10.0, 180, "U4")
gp(13.0, 17.2, 180, "L2")                 # their L1: rpi(2.0, -7.2, 0)
gp(13.0, 15.55, 180, "decap:50")          # their C7, VREG_FB
gp(13.0, 14.61, 180, "decap:49")          # their C6, VREG_VIN
gp(10.8, 15.05, 90, "decap:46")           # their C9, VREG_AVDD
gp(10.8, 16.9, 90, "rp:r33")              # their R3
gp(15.1, 17.4, 90, "usb:r_dm")            # their R1
gp(16.15, 17.4, 90, "usb:r_dp")           # their R2
gp(17.2, 17.4, 270, "decap:54")           # their C19, QSPI_IOVDD
gp(18.25, 17.4, 270, "decap:53")          # their C20, USB_OTP_VDD
gp(11.4, 4.4, 180, "decap:30")            # their C16
gp(9.9, 10.15, 180, "decap:38")            # their C17
# their C12 sat in front of pins 40-43, which GPiBridge left unused; here they are the
# ADC inputs: DVDD pin 39's capacitor goes underneath, under the chip's north edge, a short
# bottom-layer line from Raspberry Pi's 1.1 V via; their C21 moves 0.15 mm toward the
# corner, so GPIO26-29 leave through one 1.6 mm gap in the capacitor row
b.put("decap:39", L.MCU[0] - 1.6, L.MCU[1] - 2.3, 0, "B")
gp(9.9, 12.55, 180, "decap:44")           # their C21
gp(9.9, 13.45, 180, "decap:45")           # their C18
# (this column 0.35 mm further from the chip than GPiBridge's, out of GPIO0's way;
# gen/routes.py steps pin 1's line across to it)
gp(19.6, 13.63, 270, "decap:1")           # their C13
gp(20.65, 13.63, 270, "decap:11")         # their C14
gp(21.7, 13.63, 270, "decap:20")          # their C15
gp(22.75, 13.63, 270, "decap:6")          # their C10
gp(18.6, 2.35, 90, "decap:23")            # their C11
gp(22.3, 10.8, 0, "tp:1v1")               # their TP3
gp(14.95, 2.2, 90, "Y1")
gp(17.3, 3.3, 270, "xtal:c_in")           # their C4
gp(11.55, 2.2, 90, "xtal:c_out")          # their C5
gp(12.6, 2.2, 270, "xtal:r")              # their R6
gp(2.45, 20.0, 270, "J2")                 # USB-C, its face 1.2 mm past the back edge
gp(9.1, 17.95, 0, "usb:r_cc1")            # their R4
gp(9.4, 21.05, 0, "usb:r_cc2")            # their R5
gp(9.1, 15.9, 90, "usb:c_vbus")           # their C1
gp(12.0, 23.4, 180, "U2")                 # their U4, the XC6206
gp(9.4, 23.55, 270, "ldo:cin")            # their C2
gp(14.7, 23.4, 270, "ldo:cout")           # their C3
gp(13.0, 20.6, 0, "tp:vbus")              # their TP1
gp(16.4, 22.45, 0, "tp:3v3")              # their TP2
gp(21.0, 23.0, 180, "SW1")                # BOOT
gp(18.7, 20.1, 90, "boot:r")              # their R10
# ours, beside it: VSYS's two diodes left of the regulator, the debug connectors on the
# back edge to the right of the USB-C
b.put("D3", 85.0, 15.0, 90)
b.put("D4", 85.0, 8.0, 90)
b.put("tp:vsys", 85.0, 20.5)
b.put("J4", 124.0, 3.4, 180)              # SWD
b.near("swd:r_clk", "J4", -1.0, -5.2, 90)
b.near("swd:r_dio", "J4", 1.0, -5.2, 90)
b.put("J5", 134.0, 3.4, 180)              # UART
b.near("uart:r_rx", "J5", -1.0, -5.2, 90)
b.near("uart:r_tx", "J5", 1.0, -5.2, 90)

# ---- the scene, on top -----------------------------------------------------------------
b.put("J3", L.TREE_SOCKET[0] - 8.89, L.TREE_SOCKET[1] - 1.27, 90)     # the tree's socket
# Each coil (gen/coils.py) has its two terminals at its own +y: turned by 90 - phi, they
# point along phi (degrees from +x toward +y) on the board.  The pendulum coils' point
# outward from the swing's rest point (toward their bridges, away from the Hall sensor
# between them); the perches' toward their bridges, between their ring LEDs.
def coil_rot(phi):
    return round((90.0 - phi) % 360, 1)


for ref in ("L3", "L4", "L5"):
    b.put(ref, *L.pend_coil(ref), rot=coil_rot(L.PEND_COILS[ref]))
for ref, (cx, cy), drv in (("L6", L.OWL_PERCH, (63.0, 92.0)), ("L7", L.CAT_PERCH, (178.0, 66.0))):
    b.put(ref, cx, cy, rot=coil_rot(math.degrees(math.atan2(drv[1] - cy, drv[0] - cx))))
b.put("J1", L.JACK[0], L.JACK[1], 270)                                   # plug from behind
b.put("LS1", *L.SPEAKER)
b.put("SW3", L.SOUND_SWITCH[0], L.SOUND_SWITCH[1], 0)
b.put("SW2", L.SPELL_BUTTON[0], L.SPELL_BUTTON[1], 0)
b.put("U16", *L.LIGHT_SENSOR)
b.put("C1", 166.0, 9.0, 0)                                               # 470 uF, 12.6 mm tall
# the antennas' pads where gen/art.py puts them (inside each shape, at its edge toward
# its oscillator: hardware/art.json), else on the shape's right-hand edge
def antenna_pad(net, fallback):
    try:
        art = json.load(open(os.path.join(ROOT, "hardware", "art.json")))
        return tuple(next(a["pad"] for a in art["antennas"] if a["net"] == net))
    except (OSError, StopIteration, KeyError, ValueError):
        return fallback


b.put("AE1", *antenna_pad("MOON", (L.MOON[0] + L.MOON[2] - 3.0, L.MOON[1])))
b.put("AE2", *antenna_pad("GHOST", (L.GHOST[0] + L.GHOST[2] - 3.0, L.GHOST[1])))
for k, (x, y) in enumerate(L.FEET):
    b.put("H%d" % (k + 1), x, y)

# the LEDs: each on its spot, turned so its cathode faces where its line comes from
for i, (x, y) in enumerate(L.star_arc()):
    b.put("led:STAR%d" % i, x, y, 0)
for i, (x, y) in enumerate(L.STARX):
    b.put("led:STARX%d" % i, x, y, 0)
for i, (x, y, _) in enumerate(L.PUMPKINS):
    b.put("led:PUMPKIN%d" % i, x, y, 0)
for i, (x, y) in enumerate(L.WISPS):
    b.put("led:WISP%d" % i, x, y, 0)
for who, (cx, cy) in (("OWLRING", L.OWL_PERCH), ("CATRING", L.CAT_PERCH)):
    for i, a in enumerate(L.RING_ANGLES):
        t = math.radians(a)
        b.put("led:%s%d" % (who, i), cx + L.RING_R * math.cos(t), cy + L.RING_R * math.sin(t), (90 - a) % 360)

# ---- underneath ----------------------------------------------------------------------
# (bottom parts are mirrored in y before they turn: Board.near takes offsets in the part's
# own frame, so the same tile works on either side)
# power: the jack's centre pin straight down through F1 and Q1 (drain up, source down) to
# the 12 V hub under them (gen/routes.py pours it), where the clamp, a bulk capacitor and
# the test point sit; Q1's gate network to the west; then the buck in the corner
b.put("F1", 152.35, 20.5, 270, "B")      # pad 1 up, under the jack's centre pin
b.put("Q1", 152.35, 30.0, 90, "B")       # drain (5-8) up, source (1-3) down, gate at its west end
b.put("R1", 147.5, 29.5, 90, "B")        # gate pull-down: pad 1 (gate) down
b.put("D1", 147.5, 34.0, 90, "B")        # gate clamp: anode (gate) up, cathode in the hub
b.put("D2", 158.5, 35.0, 0, "B")         # cathode (pad 1) west, in the hub
b.put("C2", 150.5, 40.0, 270, "B")       # pad 1 up, in the hub
b.put("TP1", 155.5, 38.5, 0, "B")
# the buck turned so that GND, SW and VIN (pins 1-3) face east: the input capacitors
# beside VIN, SW straight across to the inductor, the boot capacitor over GND to SW,
# the dividers on the signal side (west and south)
b.put("U1", 172.0, 18.0, 180, "B")
b.put("L1", 182.5, 23.0, 270, "B")       # pad 1 (SW) up
b.put("buck:cin_hf", 174.6, 20.4, 0, "B")
b.put("buck:cin", 174.8, 23.0, 0, "B")
b.put("buck:en_top", 166.0, 23.5, 90, "B")
b.put("buck:en_bot", 168.0, 26.5, 90, "B")
b.put("buck:boot", 174.6, 15.6, 0, "B")
b.put("buck:fb_top", 175.5, 27.5, 0, "B")
b.put("buck:fb_bot", 171.5, 27.5, 0, "B")
b.put("buck:cout1", 181.5, 29.5, 270, "B")     # under the inductor's output pad, pad 1 up
b.put("buck:cout2", 183.5, 29.5, 270, "B")
b.put("tp:5v", 180.0, 14.0, 0, "B")
# the pulls on the RP2354A's lines, under its corner
for k, who in enumerate(("drv:pd_sleep", "drv:pu_fault", "fam:pd_en", "i2c:pu_scl", "i2c:pu_sda")):
    b.put(who, 117.0 + 2.0 * k, 32.0, 90, "B")

# the LED driver, centrally under the star arc
b.put("U3", 92.0, 50.0, 0, "B")
b.near("u3:cvcc", "U3", -1.0, -5.6, 90)
b.near("u3:cvcc_hf", "U3", 1.0, -5.6, 90)
b.near("u3:cvcap", "U3", 5.4, 2.6, 90)
b.near("u3:riref", "U3", 5.4, 5.6, 90)
b.put("U15", 79.0, 50.0, 0, "B")                    # the IMU
b.near("u15:cvdd", "U15", -3.6, -1.6, 90)
b.near("u15:cvddio", "U15", -3.6, 1.6, 90)
b.near("u16:cvdd", "U16", 3.2, 0.0, 90)
b.put("U17", L.PEND_REST[0], L.PEND_REST[1], 0, "B")    # under the pendulum's rest point
b.put("u17:cvcc", L.PEND_REST[0], L.PEND_REST[1] - 21.0, 0, "B")

# the coil bridges: the levitation bridge by the tree's socket, each pendulum bridge
# beside its coil.  The tile, in the HTSSOP's own frame: its top row (y -2.85) is PGND 9,
# OUT2 10, VM 11, VCP 12, CPH 13, CPL 14, GND 15, PMODE 16 from right to left; its bottom
# row (y +2.85) IN1 1 ... OUT1 8 from left to right.
DRV = {"tile0": ("U8", 126.0, 52.0, 0), "tile1": ("U5", 79.0, 110.0, 0),
       "tile2": ("U6", 64.0, 70.0, 0), "tile3": ("U7", 143.5, 78.0, 90)}
for tile, (ref, x, y, rot) in DRV.items():
    b.put(ref, x, y, rot, "B")
    b.near(tile + ":ccp", ref, -0.65, -5.4, 0)
    b.near(tile + ":cvcp", ref, 1.9, -7.2, 0)
    b.near(tile + ":cvm", ref, 4.6, -3.4, 90)
    b.near(tile + ":cvm_bulk", ref, 6.6, -3.4, 90)
    b.near(tile + ":ripropi", ref, 0.975, 5.8, 90)
    b.near(tile + ":rf", ref, 2.7, 5.8, 90)
    b.near(tile + ":cf", ref, 4.4, 5.8, 90)

# the mux and its dividers, then the perch-current amplifier, between the levitation
# bridge and the audio
b.put("U11", 141.0, 50.0, 0, "B")
b.near("mux:cvcc", "U11", 0.0, -4.4, 0)
for k, name in enumerate(("V12_SENSE", "V5_SENSE", "VBUS_SENSE")):
    b.put("div:%s:top" % name, 136.0 + 2.5 * k, 57.5, 90, "B")
    b.put("div:%s:bot" % name, 136.0 + 2.5 * k, 61.5, 90, "B")
b.put("U18", 151.0, 62.0, 0, "B")
b.near("u18:cvcc", "U18", 0.0, -4.4, 0)

# the audio amplifier by the speaker, its filter in two rows to its left
b.put("U14", 171.0, 48.0, 0, "B")
b.near("audio:cvcc", "U14", -1.2, -3.8, 0)
b.near("audio:cvcc_bulk", "U14", 2.4, -3.9, 0)
for k, who in enumerate(("audio:r1", "audio:c1", "audio:r2", "audio:c2", "audio:cinp", "audio:rinp")):
    b.put(who, 153.0 + 2.2 * k, 44.0, 90, "B")
for k, who in enumerate(("audio:rinn", "audio:cinn", "audio:cbyp", "audio:rctrl", "audio:rctrl_pd")):
    b.put(who, 155.0 + 2.2 * k, 51.0, 90, "B")
b.put("spell:r", 160.0, 116.0, 0, "B")

# the perch bridges, each beside its perch
BR = {1: ("U9", 63.0, 92.0, 0), 2: ("U10", 178.0, 66.0, 0)}
for k, (ref, x, y, rot) in BR.items():
    b.put(ref, x, y, rot, "B")
    b.near("br%d:cvdd" % k, ref, -1.0, -4.4, 90)
    b.near("br%d:cvdd_hf" % k, ref, 1.0, -4.4, 90)
    b.near("br%d:cblock" % k, ref, 5.8, -0.8, 90)
    b.near("br%d:rshunt" % k, ref, -2.6, 4.6, 0)
    b.near("br%d:rf" % k, ref, 2.2, 4.6, 0)
    b.near("br%d:cf" % k, ref, 2.2, 6.6, 0)
    b.near("br%d:rgain_f" % k, ref, -2.6, 6.8, 0)
    b.near("br%d:rgain_g" % k, ref, -2.6, 8.8, 0)

# the theremin's oscillators, each by its antenna's pad
for name, (x, y) in (("PITCH", (64.0, 38.0)), ("VOL", (42.0, 116.0))):
    u = "U12" if name == "PITCH" else "U13"
    b.put(u, x, y, 0, "B")
    b.near("osc_%s:cvcc" % name, u, -1.0, -3.6, 0)
    b.near("osc_%s:rout" % name, u, 3.8, 0.0, 90)
    b.near("osc_%s:rf" % name, u, 0.0, 3.6, 0)
    b.near("osc_%s:ct" % name, u, -3.8, 0.0, 90)


# ======================================================================================
# The tree: LEDs on its front (F), its LED driver behind (B).  The two right-angle
# headers' bodies end at the board's edges, their pins out past them; the pins' first
# column sits HEADER_BODY_FACE back from the edge.
# ======================================================================================
HEADER_BODY_FACE = 6.58          # PinHeader_2x08_P2.54mm_Horizontal: pin column to the body's far face
TREE = Board("tree")
t = TREE
# (on the back, turned 270: the pins point down and run toward +x from pin 1; turned 90
# for the top header: up, and toward -x)
t.put("J101", L.TREE_BASE_PLUG[0] - 8.89, L.TREE_H - HEADER_BODY_FACE, 270, "B")   # pins down into the base
t.put("J102", L.TREE_TOP_PLUG[0] + 8.89, HEADER_BODY_FACE, 90, "B")                 # pins up into the perch
t.put("U101", L.TREE_W / 2, 62.0, 0, "B")
t.near("u101:cvcc", "U101", -1.0, -5.6, 90)
t.near("u101:cvcc_hf", "U101", 1.0, -5.6, 90)
t.near("u101:cvcap", "U101", 5.0, 3.0, 90)
t.near("u101:riref", "U101", 5.0, 6.0, 90)
t.put("tree:c5v", L.TREE_W / 2 + 14.0, L.TREE_H - 16.0, 90, "B")
for k, owl in enumerate("ABC"):
    cx, cy = L.OWLS[k]
    t.put("led:OWL%s_L" % owl, cx - L.OWL_EYE_SPACING / 2, cy, 0)
    t.put("led:OWL%s_R" % owl, cx + L.OWL_EYE_SPACING / 2, cy, 0)
for i, (x, y) in enumerate(L.TREE_STARS):
    t.put("led:TSTAR%d" % i, x, y, 0)
for i, (x, y) in enumerate(L.TREE_WISPS):
    t.put("led:TWISP%d" % i, x, y, 0)

# ======================================================================================
# The perch: everything underneath (the printed owl covers the top), the coil at (0, 0)
# ======================================================================================
PERCH = Board("perch")
p_ = PERCH
p_.put("L201", 0.0, 0.0)
p_.put("J201", 8.89, L.PERCH_SOCKET_Y - 1.27, 90, "B")      # underneath: its pins run toward -x
p_.put("U201", 0.0, 0.0, 0, "B")                       # in the coil's hole, under the bat
p_.put("perch:rhall", 0.0, 19.0, 90, "B")
p_.put("perch:chall", 2.0, 19.0, 90, "B")
p_.put("perch:cvcc", -2.0, 19.0, 90, "B")
p_.put("perch:c5v", 9.0, 22.0, 90, "B")
p_.put("led:PERCH_DOWN0", -13.5, -14.0, 0, "B")       # the front corners, shining down on the bat
p_.put("led:PERCH_DOWN1", 13.5, -14.0, 0, "B")

# ======================================================================================
# The bat: the coil round the magnet (0, 0); the eyes on top at the head's edge, looking
# forward; the tank capacitor and the resistor underneath
# ======================================================================================
BAT = Board("bat")
bt = BAT
bt.put("L301", 0.0, 0.0, rot=270)          # terminals toward the left wing and C301 (the head and
                                           # tail edges are only 1 mm beyond the coil)
bt.put("bat:led1", -4.6, L.BAT_HEAD_Y + 0.9, 0)
bt.put("bat:led2", 4.6, L.BAT_HEAD_Y + 0.9, 0)
bt.put("bat:ctank", -15.5, 0.0, 90, "B")
bt.put("bat:r1", 15.0, -1.5, 90, "B")
bt.put("bat:r2", 15.0, 1.5, 90, "B")

# ======================================================================================
# The tokens: everything on top (they lie flat), the coil at the centre, the parts in a
# patch below it
# ======================================================================================
TOKENS = {}
for who in ("owl", "cat"):
    tk = Board(who + "_token")
    tk.put("L401" if who == "owl" else "L501", 0.0, 0.0)
    tk.put("%s:ctank" % who, 0.0, 14.8, 0)
    tk.put("%s:r1" % who, -4.6, 14.3, 90)
    tk.put("%s:r2" % who, 4.6, 14.3, 90)
    tk.put("%s:led1" % who, -2.0, 17.2, 0)
    tk.put("%s:led2" % who, 2.0, 17.2, 0)
    TOKENS[who] = tk

BOARDS = {"base": BASE, "tree": TREE, "perch": PERCH, "bat": BAT, "owl_token": TOKENS["owl"],
          "cat_token": TOKENS["cat"]}


def board_of(ref):
    """Which board a reference belongs to, by its number (base 1-99, tree 101+...)."""
    import re
    n = int(re.match(r"[A-Z]+(\d+)", ref).group(1))
    return {0: "base", 1: "tree", 2: "perch", 3: "bat", 4: "owl_token", 5: "cat_token"}[n // 100]
