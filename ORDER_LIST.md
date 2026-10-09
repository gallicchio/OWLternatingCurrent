# OWLternating Current: what to order

Everything the build needs, beyond what you already have (a 3D printer and PLA, a USB-C
cable, scissors). Five things, three of them small; nothing depends on anything else, so
order them all on the same day.

| # | what | from | how many | about |
|---|---|---|---|--:|
| 1 | **The boards, assembled** (both sides, all six boards on one panel) | JLCPCB, uploading `mfg/release/` | 5 panels, 2 of them assembled | $366 + shipping + duty (~$128) |
| 2 | **12 V power adapter**, 5.5 x 2.1 mm barrel, centre positive | Pololu #1468, "Wall Power Adapter: 12VDC, 5A, 5.5x2.1mm Barrel Jack, Center-Positive" | 1 | $20 |
| 3 | **Magnets**: neodymium discs, 10 mm x 2 mm, grade N52, magnetised through the thickness (axially) | AMF Magnets USA, "Neodymium Disc - 10mm x 2mm \| N52", product code 20053A | 10 (the build uses 2; the rest are spares for a reprint) | $27 |
| 4 | **PLA filament**, any colour | what you have | 13 g | |
| 5 | **Thread for the pendulum**: clear nylon monofilament (fishing line, 4-8 lb, about 0.2-0.3 mm) or black sewing thread | what you have | 30 cm | |

## 1. The boards (JLCPCB)

`mfg/release/ORDER_SETTINGS.md` says what to choose on each line of the order page, in the
order the page asks, and why. In short: 4 layers, 1.6 mm, purple, ENIG, 1 oz copper inside
and out, "Panel by Customer" with 6 different designs; Standard PCBA on both sides, parts
by customer. Upload the gerbers zip, then `BOM_JLCPCB.csv` and
`OWLternatingCurrent_cpl_jlcpcb_upload.csv` (not the `_cpl_kicad_native.csv` beside it).
`PLACEMENT_CHECKS.txt` lists the parts whose rotation to look at in JLCPCB's placement
preview, on both sides, before you confirm.

JLCPCB solders everything, through-hole parts included: the speaker, the barrel jack, the
slide switch, the tree's two headers and the two sockets. Nothing on the boards needs a
soldering iron.

The panel snaps apart at the mouse bites by hand (bend each board gently along its row of
little holes; a file or sandpaper smooths the nubs).

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
| JLCPCB, 5 panels with 2 assembled (estimate; `mfg/release/COST_ESTIMATE.md`) | $366 |
| US duty, collected by JLCPCB (DDP) | ~$128 |
| shipping (UPS Express Saver DDP) | at checkout, ~$30-40 |
| adapter and magnets | ~$47 |
| **total** | **~$575** |

The second assembled panel is a spare (a second owl and a second set of boards); the three
bare panels are JLCPCB's minimum order.

## Timing

JLCPCB: 4-layer boards 2-5 days, assembly at least 4 more, shipping 4-5 business days.
Ordering by about October 14 leaves margin for October 31.
