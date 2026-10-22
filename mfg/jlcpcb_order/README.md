# JLCPCB's questions about the rev A order

## 2026-10-22: C1's polarity (SMT order 13544840A_Y19, SMT026100964723)

JLCPCB's engineer asked before production:

> Since we are not so sure about the polarities of the components C1 are correct or not.
> Could you please kindly check if the polarities and placements of the SMD components are
> correct in the below 2D picture? Is it okay to proceed with production?

With it came the two placement snapshots here (`*SMT_Snapshot.Top*.png`,
`*SMT_Snapshot.Bottom*.png`).

**The answer: correct, proceed** (Jason, the same day).
- C1 is the 470 uF 35 V polymer capacitor on +12V (MA35V470M10X13, C46550472,
  `CP_Elec_10x12.6`), at the top right of the base board beside the 12 V jack J1, at
  rotation 0.
- On the board file, pad 1 (+, net +12V) is the left pad, at (-4.35, 0), and pad 2
  (-, GND) is the right one.
- In the top snapshot, JLCPCB's red '+' and the can's bevelled corners are on the left
  pad and their '-' is on the right one, so the polarity matches.
- `mfg/jlc_rotation.py` now records this part's correction of 0 as "read" (it had been
  "predicted").
