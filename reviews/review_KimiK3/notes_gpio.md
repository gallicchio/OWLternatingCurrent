# Review 6: the RP2354A GPIO binding (`gen/assign.py`, `gen/assignment.json`)

Reviewer copy/scripts in this directory (original tree untouched):

- `check_gpio.py` — static checker: `gen/assignment.json` vs the datasheet constraints
  vs `firmware/src/board_pins.h` vs `firmware/boards/owlternating.h`. **44/44 pass.**
- `recount.py` — re-runs the copy's `gen/assign.py` with `crossings`/`bind_gpio`
  wrapped, captures the ring geometry (`capture.json`), recounts crossings with an
  independent implementation.
- `relaxed_search.py` — same cost model as `bind_gpio`, but bridges/audio may also use
  GPIO16-29 where the slice map allows; writes `improved.json`.
- `validate_improved.py` — datasheet-constraint check of `improved.json`. **All pass.**
- `restricted_scan.py` — enumerates the whole restricted space and computes the true
  (min-over-cuts) crossing count for the 720 best candidates; writes `restricted_best.json`.

Datasheet facts verified against `datasheets/RP2354A.pdf` (= RP2350 datasheet, release 8,
build 80d627281ed5, 01/10/2026): GPIO Bank 0 function table (§1.2.3) and the QFN-60
pinout figure (§1.2.1).

## Headline numbers (all re-derived, not trusting the claims)

| binding | true crossings | fixed-cut metric (what the search scores) |
|---|---|---|
| hand-written `pins.py` DEFAULT | **132** (claim: 132 ✓) | — |
| shipped `assignment.json` | **84** (claim: 84 ✓) | 98 |
| best found, shipped rules (PWM on GPIO0-15 only) | **76** (`restricted_best.json`) | 106 |
| best found, PWM allowed on 16-25 but kept off ADC pins 26-29 | **63** | 68 |
| best found, fully datasheet-legal (`improved.json`) | **48** | 55 |

"True crossings" = min over every cut of both circles of the out-of-order pair count,
same definition as `assign.py:crossings()`; my independent implementation agrees with
theirs on the shipped binding (84) and on DEFAULT (132).

## Findings

### 1. MAJOR — the search does not minimize the metric it reports

`gen/assign.py:427-437` (`bind_gpio`): the objective is the inversion count with both
circles cut open at one fixed place (`pc`, `ac` from `_cut`, the widest gap, "west
side"), plus squared travel. But `gen/assign.py:316` (`crossings()`, used for the
report and the "84") takes the min over *every* cut of both circles. For the shipped
binding these disagree: fixed-cut = 98, true = 84. The search therefore never sees the
quantity being minimized, and it is optimizing with the wrong rotation:

- Within the search's *own restricted* constraint set, the fixed-cut minimum really is
  98 (I enumerated the space: histogram floor is 98, 4 configs; the shipped binding is
  one of them — so the search is a correct optimum of its proxy).
- But a restricted-space binding with fixed-cut 106 — which the search scored *worse*
  and discarded — has a true crossing count of **76 < 84** (validated: all PWM/ADC/
  I2C0/UART0/mux constraints hold; the tick slice would move from 0 to 2, which is only
  a `#define` in `board_pins.h`).

Evidence: `review_KimiK3/restricted_scan.py` output; mechanism confirmed by
`relaxed_search.py` reproducing their exact result (98 / cost 20376.2) when restricted.

Fix: score candidates with the cyclic min-cut count instead of the fixed-cut count.
The repo already contains exactly that algorithm — `cyclic_crossings()`
(`gen/assign.py:386-407`, O(n) per rotation) — but it is **dead code, never called**.
Wiring it into `score()` (at least as a final re-ranking of the best few hundred
candidates) would have found ≤ 76 with no constraint changes.

Confidence: high (numbers reproduced twice; scorer cross-validated against theirs).

### 2. MINOR — the "bridges and audio only on GPIO0-15" rule is a design choice, not hardware, and it costs crossings

`gen/assign.py:360` (`v += ... + (g >= 16)`) and `:363` (`au >= 16`) forbid PWM above
GPIO15. The datasheet table shows PWM0 A/B … PWM6 A/B again on GPIO16-29 (slice
( n>>1 )&7 repeats every 16 GPIOs; PWM exists even on GPIO26-29), and `gen/pins.py`'s
own header comment states this correctly. The firmware needs 7 PWM slices (6 bridges +
audio) plus slice 0 as the tick (`firmware/src/rt.c:140-158,475-477`), i.e. 8 of 8 —
so the restriction is not forced by slice count, only by pins.

Relaxing it (my `relaxed_search.py`, same framework and cost model otherwise):

- fully legal: **48 crossings** (FAM2 → GPIO24/25 = slice 4, AUDIO → GPIO26 = PWM5 A,
  tick stays on slice 0; `improved.json`, constraint-validated);
- keeping PWM off the ADC corner 26-29 entirely (analog hygiene): **63 crossings**
  (only FAM2 moves to 24/25, audio to GPIO18).

Caveat that may justify the rule: the relaxed winner puts 100+ kHz bridge PWM on
package pins 36/37 and audio PWM on pin 40, directly beside HALL/LEV_IPROPI on pins
41/42 — the two signals feeding the 10 kHz levitation loop. Keeping PWM off 26-29 is
defensible; keeping it off 16-23 is harder to justify on those grounds. Note the
*shipped* binding already puts a (slowly toggling) digital MUX_S2 on GPIO26.

Fix: if crossings matter more than the risk, allow bridge pairs on GPIO16-25 and audio
on any free slice's A below GPIO26. If not, add a one-line rationale to
`gen/pins.py`/`DESIGN_REVIEW.md` so the rule reads as deliberate.

Confidence: high that the hardware allows it (datasheet table); medium that 48/63
route better in practice (crossing count is a proxy; noise trade-off is a judgment call).

### 3. NIT — `crossings_before` in `assignment.json` is a fixed point, not a "before"

`gen/assign.py` main: `now` is read from `hardware/checks/netlist.net`, which already
carries the previous run's binding, so every chip reports `X -> X` (U4: `84 -> 84`).
The "132 -> 84" in DESIGN_REVIEW.md §4 is only reconstructable against `pins.py`
DEFAULT (I verified: 132). Also, re-running in the copy reproduces the GPIO binding
exactly but the U11 (mux) cost changes 194.4 -> 198.9, i.e. the stored report is
marginally stale w.r.t. the current netlist/placement (no binding change, no impact).

Fix: none needed functionally; optionally snapshot `crossings_before` from the DEFAULT
tables, or regenerate `assignment.json` before ordering so the report is current.

Confidence: high.

### 4. NIT — stale comment in the SDK board header

`firmware/boards/owlternating.h:10` says "UART0 on GPIO12/13" and `:15` "I2C0 on
GPIO16/17", but the defines (updated by regex in `gen/firmware_pins.py:board_header`)
are TX/RX = 16/17 and SDA/SCL = 20/21. The regex updates the numbers, not the prose.

Fix: generate the comments from the same values.

Confidence: high.

### 5. NIT — doc/implementation drift in `gen/assign.py`

- `:26` module docstring says "a simulated annealing over valid assignments"; the
  implementation (`:414`) is an exhaustive search. No annealing exists.
- `cyclic_crossings` (`:386-407`) is never called (see finding 1 — it is also the fix).

Confidence: high.

### 6. INFORMATIONAL — RUN pin unconnected

Netlist: `unconnected-(U4-RUN-Pad26)`. RUN has an internal pull-up and the design has
BOOT (QSPI_SS) and SPELL buttons only, per DESIGN_REVIEW §4 — consistent, just noting
there is no reset button. Out of scope for this question.

## Checked and found right

1. **PWM slice math.** Datasheet table: GPIO16 = PWM0 A, GPIO20 = PWM2 A, GPIO24 =
   PWM4 A, GPIO28 = PWM6 A → slice = (n>>1)&7, channel = n&1, period 16. `pins.py`'s
   "GPIO16-29 reuse PWM slices 0-6" is exactly right, and `_what()` uses
   `(g >> 1) & 7`. No wraparound bug: `violations()` uses `g // 2` but only after
   enforcing g < 16, where they coincide. All seven `PWM_SLICE_*` defines in
   `board_pins.h` match (GPIO>>1)&7 of the assigned pins.
2. **ADC pins = exactly GPIO26-29** (QFN-60 figure: GPIO26_ADC0 pin 40 … GPIO29_ADC3
   pin 43; "four or eight ADC inputs depending on package", 4 on the A). HALL/LEV_IPROPI/
   MUX_OUT on 27/28/29; `ADC_CH_*` defines match (ADC1/2/3). ✓
3. **I2C0 and UART0 pin sets.** `assign.py:347-348`:
   I2C0 = (4k, 4k+1) for k=0..7, i.e. SDA ∈ {0,4,8,12,16,20,24,28}, SCL = SDA+1 —
   matches the datasheet table *including* 24/25 (the review prompt's list omitted
   24/25; the code is right). UART0 = {(0,1),(12,13),(16,17),(28,29)} — exact match.
   Assigned (20,21) and (16,17) are both legal. ✓
4. **No double assignment / full coverage.** The 30 nets land on GPIO0-29 exactly once
   each; `board_pins.h` `PIN_*` values equal `assignment.json` for all 30 nets;
   `owlternating.h` defines match. ✓
5. **Mux selects consecutive**: 24, 25, 26, and `MUX_SEL_SHIFT 24` / `MUX_SEL_MASK
   7<<24` agree. ✓ (GPIO26 as a digital output is legal; it is the spare ADC pin.)
6. **PIO pins**: the datasheet table shows PIO0/PIO1/PIO2 on every GPIO 0-29, so
   THEREMIN_PITCH (GPIO0) and THEREMIN_VOL (GPIO9) are valid PIO inputs. ✓
7. **Special pins.** `symbols.py` `_FIXED`: USB_DP/DM = 52/51, XIN/XOUT = 21/22,
   SWCLK/SWDIO = 24/25, RUN = 26 — all match the QFN-60 figure; the symbol asserts
   pins 1-61 are each used exactly once. In the netlist, QSPI_SD0-3/SCLK (55-59) are
   explicitly unconnected (correct: in-package flash on the RP2354A — verified) and
   QSPI_SS (60) is on its own net for BOOTSEL. No GPIO net touches any special pad. ✓
8. **QFN-60 GPIO pin numbers** in `symbols.py:GPIO_PIN` match the datasheet figure
   (GPIO0-15 → 2-5,7-10,12-19; GPIO16-19 → 27,28,29,31; GPIO20-25 → 32-37;
   GPIO26-29 → 40-43). ✓
9. **Crossing counter is not buggy**: my independent implementation of the
   min-over-cuts count agrees with `crossings()` on both the shipped binding (84) and
   DEFAULT (132). The TIE=0.6 mm rule is applied consistently in both.
10. **The search is a correct optimum of its own (restricted, fixed-cut) objective** —
    my enumeration of that space reproduces exactly its answer (98 / cost 20376.2). The
    problem is the objective, not the search (finding 1).
11. RP2350-E9 characterization in `pins.py` (erratum hits pull-downs; external
    resistors used instead; BUTTON's internal pull-up is safe) matches the erratum. ✓

## Could not check / limits

- **Global optimality.** Both my searches keep `bind_gpio`'s framework (bridge groups
  bound in arrival order, singles filled in arrival order, ADC/I2C/UART/mux enumerated).
  A fully general matcher might beat 48. Conversely the restricted-space scan computed
  true counts only for the 720 candidates with fixed-cut ≤ 118, so 76 is a found upper
  bound on the restricted-space minimum, not a proven minimum.
- **The LED/mux "before" numbers** (115 -> 0, 42 -> 0, 6 -> 0 in DESIGN_REVIEW §4) are
  unrecoverable from the current tree (the netlist is the assignment's fixed point);
  only the RP2354A's 132 could be re-derived (via `pins.py` DEFAULT).
- **Whether PWM on GPIO24-26 would measurably degrade the ADC readings** (finding 2's
  caveat) — a layout/measurement question, not answerable from the sources.
- Whether crossings-at-the-ring is the right proxy for actual route quality (vias,
  layer changes) — taken as given from the review question.
