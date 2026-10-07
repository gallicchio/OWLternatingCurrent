# OWLternating Current rev A: JLCPCB order settings (DRAFT)

**DRAFT:** gen/board_info.py FOR_NAME (her name, printed on the back) is not set yet, so the board carries a placeholder (QUESTIONS.md).  Order once the build no longer says DRAFT.

**NOT READY TO ORDER:** this is the board-free half of the release (--bom-only): the board is not finished, so there are no gerbers and no CPL yet; the numbers below that come from the board are gen/layout.py's plan.

Written by `mfg/make_release.py` on 2026-10-07.  On jlcpcb.com, **Order now**, upload `OWLternatingCurrent_gerbers.zip`, then choose, in the order the page asks:

## The PCB

| field | choose | why |
|---|---|---|
| Base Material | FR-4 | |
| Layers | 4 | the coils' four spirals; a ground plane under the MCU and the drivers |
| Dimensions | 323.6 x 154.2 mm | the panel's outline, read from the board file's Edge.Cuts (planned) |
| PCB Qty | 5 | JLCPCB's minimum; each one is a whole panel of 6 boards |
| Product Type | Industrial/Consumer electronics | |
| Different Design | 6 (type it in: the buttons stop at 4) | base, tree, perch, bat, owl token and cat token on one panel; with Panel by Customer, JLCPCB takes up to 10 |
| Delivery Format | Panel by Customer | the panel is ours: rails, tabs and mouse bites are in the gerbers.  If the page asks for columns and rows, 1 x 1: one panel of six different boards, nothing repeated |
| PCB Thickness | 1.6 mm | the JLC04161H-7628 stack-up; the 3D prints (gen/mech.py) are drawn for 1.6 |
| PCB Color | Purple | Halloween.  Purple on 4 layers rules out Economic PCBA, hence Standard below |
| Silkscreen | White | |
| Material Type | FR4-Standard TG 135-140 | the 4-layer default; nothing here runs hot enough to need more |
| Surface Finish | ENIG | the moon and the ghost (the theremin's antennas) are bare gold copper; lead-free for a child's hands; flat pads for the 0.4 mm QFNs |
| Outer Copper Weight | 1 oz | 5 A in pours is enough at 1 oz (PLAN.md section 4) |
| Inner Copper Weight | 1 oz | halves the coils' inner-layer resistance (3.35 to 2.2 ohm): a third less heat (PLAN.md section 4) |
| Impedance Control / Layer Stackup | Yes, JLC04161H-7628 | the stack-up gen/project.py's rules and the coils' physics assume (if the page pairs 1 oz inner copper with a different 7628 stack-up, take that one; no line on this board needs a controlled impedance) |
| Via Covering | Tented | the default; the exposed pads' thermal vias wick a little solder, as Raspberry Pi's layout intends (GPiBridge, built this way) |
| Min via hole size/diameter | the default | no board yet |
| Board Outline Tolerance | +-0.2mm (Regular) | |
| Confirm Production file | Yes | free: JLCPCB shows the panel as they will make it before production; check the outline, the slots between the boards and the six designs |
| Mark on PCB | Remove Mark | nothing on the art.  JLCPCB has added no order number by default since May 2026 and asks that "JLCJLCJLCJLC" not be put on the silkscreen (help: How to mark on PCB, 2026-05-22) |
| Electrical Test | Flying Probe Fully Test | |
| Gold Fingers / Castellated Holes / Edge Plating | No | |
| PCB Remark | "Customer panel of 6 different designs joined by mouse bites; keep the rails on; parts on both sides." | |
| anything else | the default | |

## PCB Assembly

| field | choose | why |
|---|---|---|
| PCB Assembly | on | |
| PCBA Type | Standard | purple on 4 layers is Standard only; Standard also does both sides |
| Assembly Side | Both Sides | the scene on top; the electronics underneath (gen/layout.py) |
| PCBA Qty | 2 | of the 5 panels; the other 3 are bare spares |
| Tooling holes | (from the board) | Added by Customer if the panel's rails carry tooling holes, else Added by JLCPCB |
| Edge Rails/Fiducials | (from the board) | Added by Customer if the rails carry three fiducials, else Added by JLCPCB |
| Confirm Parts Placement | Yes | free.  Some rotations are predicted, not yet seen: PLACEMENT_CHECKS.txt says what to look at, on both sides |
| Parts Selection | by Customer | every part has its LCSC code in the BOM |
| Stencil / Fixture Storage | No | $4.93 each, for a re-order |
| Bake Components | Yes | JLCPCB recommends it for moisture-sensitive parts (MSL 3 and up: the LGA-14 accelerometer, the QFNs); about $7.50 |
| Depanel / remove rails | No | JLCPCB ships assembled panels with their rails on; the boards snap out at the mouse bites at home |
| anything else | the default | |

Then upload `BOM_JLCPCB.csv` and `CPL_JLCPCB.csv` (not `CPL_KiCad_native.csv`).  Every BOM line carries its LCSC code; nothing should be left unmatched.  In the placement preview, go through `PLACEMENT_CHECKS.txt` on both sides before confirming.

**Shipping:** UPS Express Saver (DDP) or DHL Express Priority (DDP): a US individual must ship DDP, and JLCPCB collects the duty (about 35 % of the PCBs and assembly).  Lead time: 4-layer PCBs 2-5 days, Standard assembly at least 4 more (+1 for through-hole parts), then 4-5 business days in the post.

## Numbers behind the choices

- Panel 323.6 x 154.2 mm (planned); smallest track (from the board); vias: from the board.
- Assembly: 244 placements a panel on 67 BOM lines (36 Extended), 800 SMD pads and 73 through-hole joints a panel (from the library's footprints); top and bottom.
- Estimate: $343.28 before shipping and duty (COST_ESTIMATE.md).
- **The panel is 323.6 mm long.** JLCPCB recommends at most 250 x 250 mm for an assembled panel and accepts larger at the customer's risk (warping through two reflows).  Expect them to ask.

Sources (read 2026-10-07): jlcpcb.com/help/article/pcb-assembly-price (2026-09-09), /capabilities/pcb-assembly-capabilities, /help/article/How-to-mark-on-PCB (2026-05-22), /help/article/how-to-add-edge-rails-fiducials-for-pcb-assembly-order, /help/article/Instructions-for-ordering, /help/article/us-tariff-policy-faq (2026-09-09).  The 4-layer fields' places on the page come from a 2024 printout of it and from others' 4-layer orders; the page itself is drawn by JavaScript.
