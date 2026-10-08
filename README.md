# OWLternating Current

*By Jason Gallicchio, made with Claude. A cute, physics-y Halloween board set for a
six-year-old witch who wants to be an owl: owls, bats and a little witch on her broom
across a gold moon, in orange and purple light that fades but never blinks, with magnets
and coils doing things that look like magic.*

![The set, assembled: the base with its scene, the tree of owls standing in it, the perch on top with the printed owl, the bat floating underneath, and the owl and cat tokens on their perches](docs/images/3d_set.png)

*Rendered from the design files (KiCad and Blender, `tools/render_3d.py`). The boards have
not been made yet.*

**Status (2026-10-08):** designed, every net routed on all six boards, KiCad's DRC clean,
the JLCPCB release written (`mfg/release/`). Being reviewed before the first order
([`DESIGN_REVIEW.md`](DESIGN_REVIEW.md)).

## What it does

| feature | what you see | the physics |
|---|---|---|
| **Light show** | violet stars, orange pumpkins that flicker like candles, purple will-o'-wisps, owls whose eyes open at dusk | 49 LEDs on two LP5036 drivers, every change a fade; dusk and dawn from a light sensor |
| **Wireless familiars** | put the owl token or the cat token on its perch and its eyes light; each perch lights only its own animal | resonant inductive power: each perch drives its coil at its token's frequency (owl 142 kHz, cat 303 kHz) and finds it by the drop in its own supply current |
| **The pendulum bat** | a bat on a thread that never stops swinging, or circles the moon | three coils under the swing give it timed kicks; a 3-axis Hall sensor under the rest point times them |
| **The levitating bat** | the bat floats in the air under the owl's perch | a magnet in the printed owl holds the bat's magnet up; a 10 kHz loop on a Hall sensor and the perch's coil keeps it from falling or jumping up (Earnshaw's theorem says it cannot float on magnets alone) |
| **Theremin** | move a hand toward the gold moon and a note rises; toward the gold ghost and it gets louder | two relaxation oscillators whose capacitance includes your hand; a speaker a slide switch turns off |
| **The spell book** | the back of the base: the equations behind each trick | silkscreen |

![The side view: the tree, the perch and the owl, and the bat floating under the perch's coil](docs/images/3d_set_side.png)

## The boards

One 4-layer panel (JLCPCB, 1.6 mm, purple solder mask, ENIG), assembled by JLCPCB on both
sides, through-hole parts included. The six boards snap apart and plug together: the tree
stands in the base's socket, the perch sits on the tree.

| board | from above | from below | in perspective |
|---|---|---|---|
| **Base** (190 x 130 mm): the electronics underneath, the scene on top | <img src="docs/images/3d_base_top.png" width="260"> | <img src="docs/images/3d_base_bottom.png" width="260"> | <img src="docs/images/3d_base_persp.png" width="260"> |
| **Tree** (76 x 112 mm): the owls' eyes, stars, the second LED driver | <img src="docs/images/3d_tree_top.png" width="260"> | <img src="docs/images/3d_tree_bottom.png" width="260"> | <img src="docs/images/3d_tree_persp.png" width="260"> |
| **Perch**: the levitation coil, the Hall sensor in its middle | <img src="docs/images/3d_perch_top.png" width="260"> | <img src="docs/images/3d_perch_bottom.png" width="260"> | <img src="docs/images/3d_perch_persp.png" width="260"> |
| **Bat**: a receive coil round its magnet, LED eyes, no battery | <img src="docs/images/3d_bat_top.png" width="260"> | <img src="docs/images/3d_bat_bottom.png" width="260"> | <img src="docs/images/3d_bat_persp.png" width="260"> |
| **Owl token**: a coil, a tank capacitor, two LEDs | <img src="docs/images/3d_owl_token_top.png" width="260"> | <img src="docs/images/3d_owl_token_bottom.png" width="260"> | <img src="docs/images/3d_owl_token_persp.png" width="260"> |
| **Cat token** | <img src="docs/images/3d_cat_token_top.png" width="260"> | <img src="docs/images/3d_cat_token_bottom.png" width="260"> | <img src="docs/images/3d_cat_token_persp.png" width="260"> |

The panel as it comes from JLCPCB (245.2 x 223.2 mm), top and bottom:

<img src="docs/images/3d_panel_top.png" width="400"> <img src="docs/images/3d_panel_bottom.png" width="400">

## Making one

- [`ORDER_LIST.md`](ORDER_LIST.md): everything to buy (the boards, a 12 V adapter, two
  magnets, a little PLA and some thread) and what it costs (about $550 for five panels,
  two of them assembled).
- [`mfg/release/`](mfg/release/): the upload for JLCPCB, and `ORDER_SETTINGS.md`, which
  says what to choose on each line of their order page.
- [`print/README.md`](print/README.md): the owl, the bat's cap and four feet, on one plate,
  with one pause to drop in the magnets.
- [`firmware/README.md`](firmware/README.md): the RP2354A's firmware, flashed over USB-C.

## Building it from source

Everything is generated from scripts: nothing on the boards is drawn by hand in KiCad.

```
python3 build.py              # every step, about 40 minutes
python3 build.py board        # from one step on
python3 build.py --only drc   # one step
```

The steps: the KiCad library, the project and its rules, the schematics, ERC, the
netlist's checks, the art, the boards (placement, planned copper, routing, pours), DRC,
the JLCPCB release, and the pictures on this page. It needs KiCad 10, Blender 4.2 or later
and Python 3. The outputs (`hardware/`, `mfg/release/`, `docs/images/`) are committed, so
nothing has to be built to look at the design or to order it.

## What's where

| path | what |
|---|---|
| [`DESIGN_REVIEW.md`](DESIGN_REVIEW.md) | the design, subsystem by subsystem, with its numbers, its checks and its open questions |
| [`hardware/`](hardware/) | the KiCad project: schematics, the panel, the library, the checks' reports |
| [`gen/`](gen/) | the generators: parts, schematics, placement, art, coils, routing, the panel |
| [`mfg/`](mfg/) | the JLCPCB release and its checks |
| [`firmware/`](firmware/) | the firmware, with host tests against simulated physics |
| [`print/`](print/) | the 3D-printed parts (OpenSCAD, from the same numbers as the boards) |
| [`sim/physics/`](sim/physics/README.md) | magnetostatics and circuit simulations: wireless power, pendulum kicks, levitation |
| [`sim/antenna/`](sim/antenna/) | an openEMS study of character-shaped 2.4 GHz antennas, for a later revision |
| [`tools/`](tools/) | checks, renders, KiCad helpers |
| [`PLAN.md`](PLAN.md) | the ideas (41, with difficulty, cost and first-try odds), the choices, the schedule |
| [`CLAUDE_CODE_CHAT.md`](CLAUDE_CODE_CHAT.md) | the conversation that designed it, every prompt and response |
| [`research/`](research/) | the JLCPCB parts survey and the web research notes |

The first concept sketch, before anything was drawn:

<img src="docs/images/concept_v1.png" width="500">

Licence: hardware CERN-OHL-P-2.0, software MIT ([`LICENSE`](LICENSE)).
