# OWLternating Current: what to order

Everything the build needs, beyond what you already have (a 3D printer and PLA, a USB-C
cable, scissors). Five things, three of them small; nothing depends on anything else, so
order them all on the same day.

| # | what | from | how many | about |
|---|---|---|---|--:|
| 1 | **The boards, assembled** (both sides, all six boards on one panel, all but three connectors) | JLCPCB, uploading `mfg/release/` | 5 panels, 2 of them assembled | $356 + shipping + duty (~$125) |
| 2 | **12 V power adapter**, 5.5 x 2.1 mm barrel, centre positive | Pololu #1468, "Wall Power Adapter: 12VDC, 5A, 5.5x2.1mm Barrel Jack, Center-Positive" | 1 | $20 |
| 3 | **Magnets**: neodymium discs, 10 mm x 2 mm, grade N52, magnetised through the thickness (axially) | AMF Magnets USA, "Neodymium Disc - 10mm x 2mm \| N52", product code 20053A | 10 (the build uses 2; the rest are spares for a reprint) | $27 |
| 4 | **PLA filament**, any colour | what you have | 13 g | |
| 5 | **Thread for the pendulum**: clear nylon monofilament (fishing line, 4-8 lb, about 0.2-0.3 mm) or black sewing thread | what you have | 30 cm | |
| 1a | **Three connectors to solder at home** (`mfg/release/hand_solder_bom.csv`): 2 x PZ254-2-08-W-8.5 right-angle 2x8 headers (LCSC C2894988) and 1 x PM254-2-08-Z-8.5 2x8 socket (C2897409) | LCSC, in the JLCPCB order | 2 + 1 (buy 4 + 2: a spare set) | $2 |
| 6 | **A drop of cyanoacrylate glue** for the bat's cap | what you have | | |

## 1. The boards (JLCPCB)

`mfg/release/FABRICATION_NOTES.txt` walks down JLCPCB's order form field by field, in the
form's own order, with every line that is not their default marked `>>`. In short: 4
layers, 1.6 mm, purple, ENIG, 1 oz copper inside and out, stack-up JLC041611-7628, "Panel
by Customer" with 6 different designs; Standard PCBA on both sides, parts by customer.
Upload the gerbers zip, then `OWLternatingCurrent_bom.csv` and
`OWLternatingCurrent_cpl_jlcpcb_upload.csv` (not the `_cpl_kicad_native.csv` beside it).
`PLACEMENT_CHECKS.txt` lists the parts whose rotation or position to look at in JLCPCB's
placement preview, on both sides, before you confirm.

**Ordered 2026-10-09** (rev A, commit 4949a73's files): 5 panels, 2 assembled, with
those settings; JLCPCB's free upgrade of tented vias to plugged was taken. In the
placement preview SW3 (the slide switch) sat a little south of its pads and was nudged
north by eye; the next release's checks carry that reading.

JLCPCB solders everything but three connectors: the speaker, the barrel jack, the slide
switch and the base's socket included. The tree's two right-angle headers (J101, J102)
and the perch's socket (J201) are left off, because the headers' pins would hang out past
the tree's edges over the panel's rail and over the perch while the panel goes through
the line, and all three are through-hole parts on the panel's second side
(`mfg/release/hand_solder_bom.csv`). Buy them from LCSC with the same order (row 1a) and
solder them after the boards are snapped apart: 48 joints, ten minutes. Pin 1 of each is
marked on the silkscreen; the headers go on the tree's back, pins pointing out past the
foot and past the top; the socket goes on the perch's underside.

The panel snaps apart at the mouse bites by hand (bend each board gently along its row of
little holes). **Then sand every snapped edge smooth** (an emery board, a file) and wipe
the boards: snapped FR4 leaves glass-fibre nubs that cut and splinter, and the tokens and
the bat are handled by a child.

The back of the base and of the tree reads "for a young owl". To print a name there
instead, set `FOR_NAME` in `gen/board_info.py` and run `python3 build.py board` (about
20 minutes) before uploading.

## 2. The power adapter

Any 12 V adapter of **3 A or more** with a **5.5 x 2.1 mm** centre-positive barrel plug
works; the Pololu one is UL-listed, 5 A, and has a three-prong cord. Not 5.5 x 2.5 mm: that
plug fits the jack loosely and may not make contact.

The board's brain also runs from USB-C alone, so a computer is enough to program it; the
lights, the sound and the coils need the adapter (they run from its 12 V and the 4.8 V
the board makes from it).

## 3. The magnets

Two go into the 3D prints, one in the owl and one in the bat's cap (`print/README.md`
explains the one pause in the print where they drop in). They must be **N52, 10.0 x
2.0 mm, axially magnetised**: the levitation is computed for that magnet's strength and the
prints' pockets are drawn for that size. N35 magnets of the same size are a sixth weaker;
the bat would float lower, or not at all. Any seller's 10 x 2 mm N52 discs will do if the
AMF ones are out of stock.

**They are a swallowing hazard.** A 10 x 2 mm N52 disc is a "hazardous magnet" in the toy
rules (its flux index is ten times the limit), and the bat's cap, which holds one, is
small enough to swallow if it comes off. So: the prints seal both magnets in during the
print (no magnet is ever loose), the owl is too big to swallow, and the bat's cap is
**glued to the bat** once it has clicked on (a drop of cyanoacrylate at each hook,
`print/README.md`), so it cannot be pried off. Keep the eight spare magnets where a child
cannot get them.

## 4. Filament

About 13 g of PLA for one plate: the owl, the bat's cap, and the four feet (they snap into
the base's corner holes and lift it 6 mm, so the through-hole pins underneath don't
scratch the table). Purple or black looks right; any colour works. Print settings, the
pause, and how to drop the magnets in are in `print/README.md`.

## 5. The thread

For the pendulum (the bat swinging over the three coils instead of floating):

1. Make a bridle on the bat: pass about 10 cm of thread under the cap's head arm and
   under its tail arm (each arm stands 1.6 mm off the board) and tie the two ends
   together above the dome, so the bat hangs level from the knot.
2. Thread the rest through the 1.2 mm hole at the front of the perch, with a knot on top
   bigger than the hole, so that **the bat's underside hangs about 7 mm above the base**:
   about 117 mm of thread from the perch's underside to the bridle's knot.

Clear fishing line makes the bat look as if it flies on its own.

## What it costs

| | |
|---|--:|
| JLCPCB, 5 panels with 2 assembled (estimate; `mfg/release/COST_ESTIMATE.md`) | $356 |
| US duty, collected by JLCPCB (DDP) | ~$125 |
| shipping (UPS Express Saver DDP) | at checkout, ~$30-40 |
| adapter, magnets, the three connectors | ~$49 |
| **total** | **~$565** |

The second assembled panel is a spare (a second owl and a second set of boards); the three
bare panels are JLCPCB's minimum order.

## Timing

JLCPCB: 4-layer boards 2-5 days, assembly at least 4 more, shipping 4-5 business days.
Ordering by about October 14 leaves margin for October 31.
