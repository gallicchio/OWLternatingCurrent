# Manufacturing review — Q7 (panel) and Q8 (CPL rotations)

Reviewer: KimiK3 sub-agent, 2026-10-08. Sources: `gen/panel.py`, `gen/layout.py`, `gen/mech.py`,
`mfg/jlc_rotation.py`, `mfg/make_release.py`, `mfg/footprint_check.py`, `tools/jlc_api.py`,
the built `hardware/OWLternatingCurrent.kicad_pcb` (2026-10-08 10:36, same minute as panel.py),
and the generated `mfg/release/` (2026-10-08 21:06). All geometry below was re-derived from the
code and cross-checked against the actual board file and gerbers, not taken from comments.
Panel frame used for coordinates: origin at the panel's top-left, y down (panel.py's frame).

---

## Q7 — the panel

### Findings

**1. MAJOR — A tab's mouse bites land inside the perch's left notch, a `CLEAN`-listed edge.
The clean-edge check is one-sided: it only vets the board the tab search started from, never
the board on the tab's far end.**
`gen/panel.py:110` (`if _clean_conflict(name, side, s, d): continue` — only `name`) and
`gen/panel.py:150-170` (`_clean_conflict` takes one board).
Evidence (built board, not just code): the tree↔perch tab at panel y=157.88 has bite rows at
x=119.55 (tree foot edge 119.4 + 0.15) and x=122.64. The perch's left edge is at x=121.8 with
a notch `OWL_NOTCH_Y=(-3,3)`, `OWL_NOTCH_D=1.0` deep (`gen/mech.py:34-35`) → notch void spans
panel y 154.8–160.8, bottom at x=122.8; the bite row sits 0.15 mm inside the notch bottom, and
the bites' y span (157.88 ± 1.75 = 156.13–159.63) lies entirely inside the notch.
`CLEAN["perch"]` (`panel.py:36-37`) lists exactly this edge (`("left", -5, 5)` → panel y
152.8–162.8); had the tab been found from the perch side it would have been rejected. It was
found from the tree side (`other="perch"`), whose own clean band does not cover y=157.88, so it
sailed through. The rejection of the perch-side duplicate does not remove the tree-side tab, so
the bug is independent of dict order. Consequence: after snapping, the notch's seating surface
(the printed owl-cap arms hook into it, mech.py:31-32) carries ~0.25–0.35 mm bite scallops on
every panel; the tab also fills a functional feature during assembly.
Fix: in `find_tabs`, when a candidate has `other is not None`, also run the clean check for
`other` — map the tab onto the other board: opposite outward direction, same lateral coordinate
(s + the nudge already applied), i.e. `_clean_conflict(other, opposite_side, s_other, -d)`,
where `opposite_side` is the side whose `DIRS` entry maps to `-d` on that board. Confidence: high
(tab verified in `hardware/OWLternatingCurrent.kicad_pcb`; notch geometry verified numerically).

**2. MINOR — Same one-sided hole lets a second tree↔perch tab sit inside the tree's own
header-pin protection band; no physical collision, but the intended protection silently failed.**
The tab at panel y=190.6 (rows x=119.55 and x=121.65) lies inside the tree's `CLEAN["tree"]
("down", 24, 52)` band = panel y 163.8–191.8, plus the design's own ±(TAB_W/2+0.5) margin →
161.8–193.8 (`panel.py:34-35`, `_clean_conflict` margin at `panel.py:169`). Found from the perch
side, so never tested against it. It is ~2 mm clear of J101's actual pins (pin band ends at panel
y≈187.0; the header's F.CrtYd ends at ≈188.5; bites start at 189.1), which is why the courtyard
check (`panel.py:133-147`, verified working — see "checked and found right") legitimately passed
it. So: latent protection failure, harmless outcome this time. Same fix as finding 1.
Confidence: high.

**3. MAJOR (process risk) — The tree's right-angle header pins overhang the panel's structure:
J102's pins end 1.4 mm from the panel edge over the left rail; J101's pins reach 3.6 mm over the
perch board.**
Geometry verified from `gen/layout.py:163` + the 6 mm pin reach: J102 (tree top edge → panel
left, x=7.4) pins span panel x=1.4–7.4, i.e. under the solid 5 mm rail (x=0–5) and ending 1.4 mm
from the panel outline. J101 (tree foot, panel x=119.4) pins span x=119.4–125.4; the perch
occupies x≥121.8 → 3.6 mm of pin over the perch's left strip, over panel y≈168.9–186.7.
Assessment: (a) These are THT parts (C2894988), which JLCPCB hand-solders after both SMT reflows
(ORDER_SETTINGS.md even budgets "+1 for through-hole parts"), so there is no reflow conflict with
the perch's SMT parts — the "perch region has pins hanging over it" worry is a handling/fixturing
worry, not a reflow one. (b) The pins run below the panel plane, so they lie against the bottom
face of the rail / the perch's bottom face at best zero clearance; insertion sweep grazes the
perch's edge. Any exposed copper on the perch bottom there is under soldermask (checked: J201,
the only bottom part on the perch, sits at panel (147.7, 188.5), well clear), so shorting risk is
low. (c) Pin tips 1.4 mm from the panel edge are inside any component-to-edge clearance a
fixture/clamp wants, and bent pins here are pins that must later plug into the base. Expect a
JLCPCB DFM/engineering query on a fully-assembled order; plausible outcomes range from "accepted
with a note" to "we cannot place these".
Fix options: mark J101/J102 (and arguably J201/J3) as customer-supplied/hand-soldered (the boards
are designed to plug together at home anyway — soldering four 2x8 headers at home removes the
whole risk class); or move the tree ≥5 mm right and accept the pins over the slot only; or widen
the panel. At minimum, keep "Confirm Production file: Yes" and ask JLCPCB about the overhang in
the PCB Remark before paying. Confidence: geometry high; JLCPCB's reaction medium (their
component-to-panel-edge rules for hand-soldered THT are not published precisely enough to call
this a certain rejection).

**4. MAJOR (process risk) — All three panel fiducials are top-side only on a both-sides
assembly.**
`Fiducial_1mm_Mask2mm.kicad_mod`: single pad `(layers "F.Cu" "F.Mask")`. PLACEMENT_CHECKS.txt
confirms "FID1/2/3 (F.Cu …)". The bottom pass — which places the finest parts on the panel
(VQFN-46 0.4 mm pitch U3/U101, LGA-14 U15, all bottom) — has no fiducials visible once the panel
is flipped. JLCPCB's edge-rail/fiducial guidance (cited in `make_release.py:588-591`) contemplates
fiducials per assembled side; expect an engineering query or reduced bottom-side placement
accuracy via tooling-hole alignment.
Fix: give the fiducial footprint the mirrored B.Cu/B.Mask pad (or place three more on the bottom
at the same spots — a 1 mm dot inside a 2 mm mask opening on both sides is standard).
Confidence: medium that JLCPCB raises it; high that the bottom side currently has no fiducial.

**5. MINOR — The bat is held by only 2 tabs, both on its head edge.**
Observed tabs: rows at (168.6, 137.55/139.79) and (190.53, 137.55/139.66) — both base↔bat-head.
The wing/tail edges are too curved for the STRAIGHT=0.4 mm test (`panel.py:26,191`), so nothing
else attaches. 2 tabs × ~1.25 mm of residual web on a 48×25 mm board through two reflows is the
panel's highest premature-break risk. The bat's own notches (panel x 179.5–184.9) are clear of
both tabs. Fix (optional): accept it, or widen GAP locally / add a frame tab on the tail side.
Confidence: high on the geometry, low-medium on it actually breaking.

**6. NIT — Mouse-bite web is 0.25 mm.** `BITE_D=0.5`, `BITE_PITCH=0.75` (`panel.py:22-23`) →
0.25 mm between holes. Inside the range the code cites (0.5–0.8 mm holes, 0.2–0.3 mm apart,
`panel.py:22`), but below the common 0.3–0.5 mm web practice; combined with finding 5 it makes
the panel a little fragile. Hole centres 0.15 mm outside the edge (`BITE_OUT`) → holes intrude
0.1 mm into the board, leaving ~0.2 mm to the 0.3 mm copper keep-back — self-consistent.
Confidence: high (values read from code; NPTH drill shows exactly 140 × 0.5 mm holes).

**7. NIT — Base↔bat tab at panel x=190.53 clears the sound-switch keep-out by only 0.63 mm.**
`CLEAN["base"] ("down", 164, 181)` → panel x 171.4–188.4; the tab's bite span is x 189.03–192.03.
Within the design's own margin rule (would pass even from the base side, by 0.13 mm), but tight
against a lever that must stay clean. Worth one nudge (−3 mm) of margin. Confidence: high.

**8. NIT — Dead parameter / unchecked interior holes.** `find_tabs(edges, holes_of=None, ...)`
(`panel.py:88`) never uses `holes_of`: the boards' own cut-outs are not considered in tab
placement. Harmless today (no interior hole is near any tab), but the signature promises a check
that does not exist. Confidence: high.

**9. NIT — `features()` computes the fiducial mask opening but never tests it.**
`make_release.py:617`: `good_fid` checks copper diameter (1 mm) and edge distance only; the
2 mm opening is computed (`make_release.py:601`) yet unused in the pass criteria. Values are
correct anyway (1 mm copper, 0.5 mm mask margin → 2.0 mm opening, verified in the footprint).
Confidence: high.

### Q7 answers in brief
1. Courtyards: yes, enforced (all footprints' F/B courtyard polygons are sampled at 30 points per
   tab, `panel.py:133-147`, call at `panel.py:246`). Clean edges: enforced for the originating
   board only — see findings 1–2. Curved/tree-shaped edges: the STRAIGHT (0.4 mm over 3 mm) and
   edge-near-bbox (0.8 mm, `panel.py:188-189`) tests push tabs onto near-straight spots; the
   tree-edge frame tabs land in shallow (≤0.61 mm) recesses, so remnants end up recessed, not
   protruding — good. Token-circle curvature (sagitta ≈0.06 mm over 3 mm) passes, as intended.
2. 0.5 mm holes at 0.75 mm pitch → 0.25 mm web: matches the code's cited JLCPCB range, thin vs
   common practice (finding 6). 4 holes per 3 mm tab, 23 tabs, 140 holes — all confirmed in the
   drill file.
3. Panel 245.2×223.2 mm confirmed exactly (Edge.Cuts gerber box = (0,0)–(245.2,223.2), sharing
   the CPL/drill origin). Within the stated 250×250. Rails exactly 5.0 mm (the cited minimum).
   Fiducials: 3, asymmetric (missing bottom-right), 3.85 mm from the edge (≥3.35 required), on
   the rail — all confirmed in the board file. Tooling: 4 × 2.0 mm NPTH, 2.5 mm from top/bottom
   edges, 5 mm from left/right — inside solid frame material, confirmed.
4. Header overhang: finding 3 — real, expect a DFM query; not a reflow conflict for the perch.
5. Clean-edge claims: USB mouth, barrel jack, switch lever, bat notches, thread hole — all
   verified clear in the built board (nearest approach 0.63 mm, finding 7). Perch notches:
   VIOLATED (finding 1). So the claim "tabs avoid edges that must be clean" is true except where
   the protected edge belongs to the board on the far side of a tab.

---

## Q8 — CPL rotations

### Findings

**10. No defect — the transform is correct and is cross-gated three ways.**
(a) Frame: gerbers and drill use `--use-drill-file-origin` (`make_release.py:641-646`), the CPL
uses `to_cpl` = (x−ox, oy−y) → y-up from the same origin (`make_release.py:454-457`);
`pos_export_check` (`make_release.py:557-575`) diffs every row of the native CPL against KiCad's
own `pcb export pos` output (±0.002 mm / ±0.01°), and `gerber_box` vs the board outline in the CPL
frame (±0.05 mm, `make_release.py:1229-1234`) — both gates passed (the release exists).
So "X not negated, y-up from the drill/place origin" is verified by construction, not by faith.
(b) Bottom side: KiCad stores a bottom footprint y-mirrored with angle θ in the top-view frame;
JLCPCB views the bottom flipped left-to-right. Algebra: with M_x the left-right mirror,
M_x·Rot(R) = Rot(−R)·M_x, and KiCad's flip = Rot(180)·M_x; equating the two placements gives
R = 180 − θ + corr with corr = −c where JLCPCB's drawing = ours turned by c. That is exactly
`cpl_rotation` (`jlc_rotation.py:247-264`): flip the NATIVE angle first, then add the library
correction. The ordering is the one the U5/U10 evidence demands (they carry +270 footprint
corrections and were seen right). A KiCad-sense subtlety is handled correctly: footprint_check's
fit rotation is math-CCW (y-up) while kicad_turn is screen-CCW (y-down), which is exactly why a
fit of d degrees predicts 360−d (`make_release.py:492`); verified against the read anchor
C882412 (their pin-1 SW vs ours NW → fit d=90 → correction 270 ✓ matches the preview reading).
(c) Empirical: BOTTOM_FLIP's 10 readings re-pass (`python3 mfg/jlc_rotation.py` in the copy:
"10 of 10 bottom-side readings still satisfied"); 180−θ is provably the unique map of the form
c−θ or θ+c fitting them (θ+c fails on D10/D11/D13; −θ fails on D7/D8/D12).
The `bottom_storage` gate (`make_release.py:372-390`) rejects x-mirrored bottom footprints, which
is the one silent assumption the whole rule rests on — good.
Residual honesty: the flip convention is anchored on previews of other boards (Icepi Zero/GPSDO
diodes) plus read parts; the in-repo `simulate()` check is self-consistent by construction (it
uses the same left-to-right-flip model it tests), so it catches regressions, not a wrong
convention. That convention is exactly what "Confirm Parts Placement: Yes" is for, and
PLACEMENT_CHECKS.txt operationalizes it. Confidence: high.

**11. MINOR (known and managed) — Bottom-side polarity predictions are untested in a preview.**
LEDs are top (scene side) except D201/D202 (violet 3528, bottom, on the base); the diodes split:
D1 (BZT52C10, SOD-123) and D2 (SMBJ15A, SMB) bottom; D3/D4 (B5819W, SOD-123) top. Two-pad parts
can't be fitted by pin number, so their corrections (all 0) were read by eye off JLCPCB's drawing
PNGs and marked "predicted" (`jlc_rotation.py:190-207`); the code itself says the prediction
method "is untested on the bottom side". The prediction IS applied consistently across sides —
`predictions()` (`make_release.py:478-505`) computes both top and bottom (mirrored) fits and
refuses to predict when they disagree, and the correction is added after the flip on both sides.
A 180-error here is a reversed diode/LED — the most expensive kind of wrong. PLACEMENT_CHECKS.txt
lists each with what to look for; keep the preview step mandatory. Confidence: high that the
pipeline is consistent; the by-eye mark readings themselves are the soft spot (medium).

**12. Spot-checks of the actual CPL — all sane.** (`mfg/release/OWLternatingCurrent_cpl_*.csv`,
diffed row by row):
- J2 USB-C (C165948): top, 180→180, correction 0 ("built" on two prior boards), datum shift
  (0, −1.572) mm — exactly the documented C165948 origin offset toward the pad row. ✓
- U4 RP2354A QFN-60: top 90→90, correction 0 ("read", pin-1 dot verified on 61 pads). ✓
- U12/U13 SOT-23-5 bottom: native 0 → flip 180 + correction 180 = 0 ✓ (the "sure" 180 reading).
- U1 TPS54302 SOT-23-6 bottom: 180 → 270 via runtime prediction (fit turned 90 → predict 270). ✓
- D2 SMB bottom 0→180; D1 SOD-123 bottom 90→90 (fixed point of 180−θ) ✓.
- D5/D6/D30 RGB-5050 top: 0→90 via runtime prediction (fit 270 → predict 90), listed in
  PLACEMENT_CHECKS as not-yet-seen ✓.
- J101 bottom native 0 → (180−0)+90 = 270; J102 180 → 0+90 = 90 — the predicted 90 for the
  right-angle header applied after the flip ✓. J3 top 90+90=180, J201 bottom (180−90)+90=180 ✓.
- Datum shifts on J3/J101/J102/J201 are exactly (±1.270, ±8.890) mm = half the 2×08 pattern
  extents (0.5×2.54, 3.5×2.54) — a pin-1-origin vs pattern-centre-origin difference, geometrically
  exact, applied only when the fit residual ≤0.15 mm (`datum_shift`, `make_release.py:467-475`;
  the 8.9 mm size looks alarming but is precisely the connector's half-length). ✓
- 30 chips pass the pin-for-pin placement simulation on both sides (PLACEMENT_CHECKS.txt).

**13. Cost estimate (~$366.11) — arithmetic verified; one oddity explained.**
109.31 (panels, mid of an honest $43.58–175.04 model — recomputed: fixed $24.26 from the
GPiBridge cart + $70.6–350/m² × 0.2736 m² + allowances ✓) + 51.12 setup + 16.42 stencils +
102.51 feeders (67 × $1.53) + 2.56 SMD joints (800×2×0.0016) + 5.97 THT (73 joints/panel
verified against the BOM footprints: 3+4+16+16+16+16+2) + 8.21 designs + 0.53 packing + 69.48
parts = 366.11 ✓. Stock gate passed for every code at generation (parts_report,
`make_release.py:299-322`, uses JLCPCB's live `stockCount` vs `order_qty = max(need+lossNumber,
minPurchaseNum)`). Oddity: C25100 (27 Ω 0402) orders **6941 pieces for 4 placements** ($9.02) —
verified against the cached API record (`tools/jlc_cache.json`: `minPurchaseNum: 6941,
lossNumber: 12`), so it is JLCPCB's data, not a script bug; it is also (correctly) the only part
flagged "thin stock/order soon". Consider a Basic 27 Ω 0402 to dodge the minimum. Nothing else
implausible: the both-sides feeder caveat (+$7.65 if loaded per side) and the baking fee are
disclosed. Confidence: high.

### Checked and found right
- Tab/hole/fiducial/tooling counts and positions in the built board and drill file match the
  design claims (23 tabs = 12 board-to-board + 11 frame; 140 × 0.5 mm bites; 3 fiducials at
  (12,3.85)/(233.2,3.85)/(12,219.35); 4 × 2 mm tooling holes on the rails).
- Panel outline in the gerber is exactly 245.2×223.2 mm in the CPL frame; aux origin (50, 273.2).
- Courtyard rejection works: the tree's two frame tabs (y=157.88, 197.12) clear J102's pin band
  (163.8–191.8 with margin) as intended; `_in_courtyard` samples both bite rows with tolerances.
- USB mouth (panel x 93.4–111.4), barrel jack (150.4–168.4), switch lever (171.4–188.4), bat
  notches (179.5–184.9), perch thread hole (x 133.8–143.8): every nearby tab verified clear.
- Dedup of board-to-board tabs (4 mm endpoint match, `panel.py:122-131`) is consistent with the
  observed tab set.
- The full rotation pipeline (finding 10): frame, flip, correction order, prediction sign, and
  the three independent gates (pos-export diff, placement simulation, gerber-box check).
- BOM is one line per LCSC code; the release's own gates (stock, MPN match, HOLE/LAND, DRC) all
  passed for the generated release.

### Could not check
- JLCPCB's current live page for the 250×250 mm assembled-panel limit and their actual tolerance
  for parts overhanging the panel edge / hanging under the rails (offline; treated as process
  risk, finding 3).
- JLCPCB's hard requirement for bottom-side fiducials on a customer panel (finding 4 is a risk
  call, not a verified rule violation).
- The 3D height at which the PZ254 header's bent pins run below the panel plane (2D footprint
  carries no z) — i.e. whether J101's pins merely graze or truly press the perch's bottom face.
- The by-eye polarity-mark readings of JLCPCB's drawing PNGs for the 0603/3528/side-view LEDs,
  SOD-123/SMB diodes, 470 µF cap and speaker (the drawings were not re-fetched; the method and
  its top-side calibration are verified, finding 11).
- Whether JLCPCB loads a both-sides part's feeder once or twice (the estimate discloses ±$7.65).
