# Web research notes: halloween1 (cute, physics-y Halloween PCB)

Researched 2026-10-07 (US Pacific) by Claude (Opus 5.5) with web search, WebFetch, `curl`
of primary pages, and the GitHub REST API. Every page below was read on **2026-10-07**;
where a page shows its own date ("last updated", publication date) that date is given
too. Prices and lead times move: re-check the live JLCPCB quote before ordering.
"My estimate" marks numbers I calculated rather than read. None of this is legal advice.

Not committed; this file lives in `research/` for the design work.

Contents: 1 JLCPCB facts · 2 Prior art · 3 Names · 4 Safety/regulatory · 5 Amazon parts

---

## 1. JLCPCB fab facts

### 1a. Solder-mask colours, with and without assembly

* **Rigid FR-4 capabilities** (https://jlcpcb.com/capabilities/pcb-capabilities): solder
  mask "Green, Purple, Red, Yellow, Blue, White, and Black" (LPI). No restriction by layer
  count is stated, so purple is offered on 4-layer.
  * Solder-mask bridge (minimum pad gap that keeps a mask dam): 1 oz copper 0.10 mm for
    green/red/yellow/blue/purple but 0.13 mm for black/white; **2 oz copper: 0.20 mm for
    any colour**. So on 2 oz outer layers, fine-pitch IC pads lose their mask dams.
* **PCBA capabilities** (https://jlcpcb.com/capabilities/pcb-assembly-capabilities):
  * *Standard PCBA*: 1-32 layers; PCB colour "No limit"; thickness, finish and stack-up
    unrestricted; single- or double-sided; 0201 minimum; 0.35 mm IC pitch; build time
    "≥ 4 days"; single boards 70 x 70 mm minimum (smaller boards are panelised with rails).
  * *Economic PCBA*: 2/4/6 layers, 0.8-1.6 mm, single-sided, "standard stack-up only",
    build "1-3 days", and colours limited to a table. The table's layer column renders
    client-side, so this grouping is my reading of the row order: **2-layer**: 0.8 mm
    green; 1.0/1.2 mm green or black; 1.6 mm green (HASL/ENIG), black (HASL),
    **blue/purple (HASL, 5-30 pcs)**, red/white (leaded HASL, 5-30 pcs). **4-layer**:
    green only (1.0/1.2/1.6 mm, HASL or ENIG). **6-layer**: 1.6 mm green ENIG.
  * => **Purple + 4-layer + assembly requires Standard PCBA.** A non-standard stack-up
    (needed for 2 oz inner copper, see 1b) also forces Standard PCBA.
* **Cost or extra time for colour**: JLC's blog "Solder Mask Colors..."
  (https://jlcpcb.com/blog/pcb-solder-mask-colors-performance, published 2026-05-18,
  updated 2026-06-16): "JLCPCB charges the same standard pricing for all seven solder
  mask colors ... on most orders", and green has "the fastest turnaround". A third-party
  summary in search results said purple "adds 1 to 2 days" because non-green panels are
  batched. I could not find that sentence on JLC's own pages, so treat +1-2 days as a
  risk, not a published rule. JLC's extra-charges article lists unusual combinations,
  e.g. "1 layer, 1.6, Red, HASL(with lead)", under "Orders with Special Process" that
  take "longer to accumulate" and may carry a surcharge shown at quote time
  (https://jlcpcb.com/help/article/in-what-cases-will-there-be-charged-extra, updated
  2026-09-09).
* **Matte black**: not offered. The EasyEDA/JLC forum answer (via search snippet,
  https://easyeda.com/forum/topic/Matte-black-soldermask-06523918727340fb9a0c27a7806ec749):
  JLC used to offer matte black, dropped it because it scratches easily, and their black
  is "not too matte or too glossy". PCBWay is the usual source for matte black or matte
  green.
* **Multi-colour (full-colour UV-printed) silkscreen**, useful for cute art
  (https://jlcpcb.com/help/article/how-to-design-multi-color-silkscreen-using-easyeda,
  updated 2026-09-09; https://jlcpcb.com/resources/multicolor-silkscreen-pcb):
  2 or 4 layers, **white mask only, 1 oz outer copper only, ENIG 1u**, 1200 dpi, "one
  additional day", "starting at just $6.71". The colour artwork must come from
  EasyEDA's colour-silkscreen export, not plain Gerbers. With JLC SMT the panel must have
  edge rails "otherwise, the color silkscreen will not be printed". **It cannot be
  combined with purple mask or 2 oz outer copper.**

### 1b. 2 oz copper on a 4-layer board

* Capabilities page: finished outer copper "2-layer: 1 oz / 2 oz / 2.5 oz / 3.5 oz /
  4.5oz; **Multi-layer: 1 oz / 2 oz**". Finished inner copper "**0.5 oz / 1 oz / 2 oz**
  ... 0.5 oz by default".
* Copper-weight article (https://jlcpcb.com/help/article/jlcpcb-copper-weight, updated
  2026-09-09): heavier inner copper "availability depends on total layers and overall
  thickness". An older order-page FAQ (quoted in search snippets; the page now returns
  404) said "1 oz and 2 oz inner copper weight is only available for 4 layer boards ...
  2 oz inner copper weight is only available for 1.6 mm with **JLC3313 stackup and 2 oz
  outer copper**". Expect 2 oz inner copper to force a specific stack-up. That changes
  the impedance of any 2.4 GHz antenna feed, so recompute with JLC's impedance
  calculator.
* **Minimum track/space at 2 oz**: capabilities page 2-layer 0.16/0.16 mm (6.5 mil),
  **multilayer 0.15/0.15 mm (6 mil)**. The copper-weight article says "2oz, any layer
  FR4: 0.16 mm (6.5 mil)", and an older FAQ said > 8 mil. **Design at ≥ 0.2/0.2 mm.**
  Other 2 oz rules: PTH annular ring ≥ 0.254 mm; mask bridge 0.20 mm (above). Trace
  coils (1 oz): 0.15/0.15 mm minimum under mask, 0.25/0.25 mm unmasked (ENIG only).
  Multilayer 1 oz minimum is 0.09/0.09 mm.
* **Extra cost**: not published; only the live quote shows it. JLC's cost blog
  (https://jlcpcb.com/blog/custom-pcb-cost, via search) says 2 oz "will incur extra raw
  material and processing surcharges". Context: JLC raised FR-4 and other substrate
  prices from 2026-06-26 because of copper-clad laminate costs
  (https://jlcpcb.com/news/jlcpcb-pcb-pricing-notice, 2026-06-13), then removed volume
  surcharges on 1/2/4-layer FR-4 on 2026-08-03
  (https://jlcpcb.com/news/jlcpcb-fr4-pcb-price-adjustment-august2026). The quote API
  needs a logged-in session, so I could not price it. Prior-art data point: the North
  Pole Circuit card (section 2a) paid "~$90 for 5 populated boards" (4-layer, 1 oz inner,
  2024).

### 1c. Lead time and shipping to California

* **JLC holiday**: factories were closed **Sep 25, Sep 27 and Oct 1-4, 2026; normal
  production resumed Oct 5, 2026**, and JLC warned lead times "immediately following
  the holiday period may be slightly longer"
  (https://jlcpcb.com/news/jlcpcb-september-october-2026-holiday-schedule, 2026-09-30).
  Unrelated: 6+ layer lead times were stretched in August 2026 and restored on 2026-08-26
  (https://jlcpcb.com/news/multilayer-pcb-lead-time-update-august-2026). 4-layer was
  unaffected.
* **Bare-board build time**
  (https://jlcpcb.com/help/article/pcb-fabrication-services-and-production-time, updated
  2026-09-09; ≤ 100 x 100 mm, 1.6 mm, 1 oz, HASL, green): 1-2 layer 24 h (5 pcs);
  **4-layer 2-5 days (≤ 50 pcs)**, 8 days (> 50 pcs); 6-layer 6-7 days. Non-standard
  options (2 oz, purple, ENIG, special stack-up) can add time.
* **PCBA**:
  * PCBA FAQ (https://jlcpcb.com/help/article/pcb-assembly-faqs, 2026-09-09): "Assembly
    turn-time begins immediately after the PCB turn-time and 90% of PCB assembly orders
    can be finished within 24 hours, 48 hours at most."
  * Capabilities page: Economic PCBA "1-3 days", Standard PCBA "≥ 4 days".
  * SMT lead-time guide (https://jlcpcb.com/help/article/smt-service-lead-time-overview,
    2026-09-09):
    * PCBA orders get "complimentary 24-hour PCB fabrication by default". Check that the
      option appears for this 4-layer spec at order time.
    * SMT expedite costs "USD 47.83 per day". JLC's example: a standard 5-6 day SMT lead
      time becomes about 4-5 days with 1 day of expedite.
    * Footprints for parts not in JLC's library: "typically completed within 48 hours".
    * While an order sits in "Pending" (an engineering question) the clock stops, so
      answer DFM and part-orientation emails quickly.
  * Hand/wave-soldered through-hole parts: "SMT assembly service time + 1 more day".
  * **Parts not in stock**: "Global sourcing via trusted distributors (lead time: 9-15
    days)" (https://jlcpcb.com/pcb-assembly). => **Use only parts JLC/LCSC have in
    stock.**
* **Shipping to North America**
  (https://jlcpcb.com/help/article/Shipping-Methods-and-Delivery-Time, updated
  2026-09-09). The table is an image; it is "based on 90% of our history orders" and
  given in business days:

  | Service | North America (business days) |
  |---|---|
  | DHL Express Priority (DDP) | 3-5 |
  | DHL Express Worldwide | 3-5 |
  | DHL Express Economy | 4-5 |
  | UPS Worldwide Express | 4-5 |
  | UPS Express Saver | 4-5 |
  | FedEx International Priority / Priority Saver / Packet | 4-7 |
  | Global Direct Line Saver | 8-10 |
  | Global Standard Direct Line | 8-10 |
  | Economical Global Direct Line | 10-12 |

  US individuals must ship DDP. JLC's tariff page lists the DDP choices as "DHL Express
  Priority (DDP)", "FedEx International Priority (DDP)" and "UPS Express Saver (DDP)",
  and says non-DDP DHL/FedEx Express are "restricted to corporate customers only" (note
  of 2025-04, https://jlcpcb.com/news/logistics-update-us-china-tariff).
* **Latest safe order date for delivery by Fri 2026-10-30** (my estimate, built from the
  numbers above):

  | Scenario | Order/DFM | 4-layer PCB | Standard SMT | Ship (DHL/UPS DDP) | Total | Order by |
  |---|---|---|---|---|---|---|
  | Pessimistic | 1 d | 5 d | 6 d | 5 bd ≈ 7 d | ~19 d | **Sun Oct 11** |
  | Typical | 1 d | 2-3 d | 4-5 d | 4 bd ≈ 6 d | ~14 d | **Fri Oct 16** |
  | Aggressive (24 h PCB + 2-3 days SMT expedite) | 0.5 d | 1 d | 2-3 d | 3 bd ≈ 4-5 d | ~9-10 d | Tue Oct 20 (gamble) |

  Recommendation: **submit by Mon Oct 12-Wed Oct 14** with DHL Express Priority DDP,
  in-stock parts only, and fast answers to engineering questions. Anything needing
  global-sourced parts (+9-15 days) had to be ordered by about Oct 5.

### 1d. US import duty and tariffs (status in early October 2026)

* JLCPCB "U.S. Tariff Policy FAQ" (https://jlcpcb.com/help/article/us-tariff-policy-faq,
  **last updated 2026-09-09**):
  * IEEPA "fentanyl" additional tariff: 20% -> 10% (2025-11-11) -> **0 (2026-02-24)**.
  * IEEPA reciprocal tariff: 125% -> 10% -> **0 (2026-02-24)**. Background: on
    2026-02-20 the Supreme Court held 6-3 in *Learning Resources, Inc. v. Trump* that
    IEEPA does not authorise tariffs
    (https://www.mltaikins.com/insights/u-s-supreme-court-strikes-down-emergency-tariffs-what-learning-resources-inc-v-trump-means-for-canada/).
  * "Provisional Tariff: 10% (effective Feb 24, 2026 - Jul 24, 2026)", i.e. the Section
    122 global surcharge (150-day statutory limit).
  * "122 Tariff: 12.5% (New, effective July 24, 2026) (Official 122 Tariff is set at
    12.5% but JLC Tariff is set at 10%)". This is actually the new **Section 301
    "forced-labor" action**. USTR's final action, effective 12:01 a.m. ET
    **2026-07-24**, imposes "12.5 percent tariffs on products of China, except as
    provided in Annex I and Annex II, Part A". It stacks on other duties ("the duty
    provided in the applicable subheading + 12.5%"). Section 232 goods and listed
    semiconductor articles are exempt. Sources: USTR notice
    https://ustr.gov/sites/default/files/files/Press/Releases/2026/FLIP%20301%20Investigation%20Final%20Action%20FRN%207-23-26%20FINAL.pdf;
    Federal Register 2026-15181 (2026-07-28)
    https://www.federalregister.gov/documents/2026/07/28/2026-15181/notice-of-actions-in-section-301-investigations-of-acts-policies-and-practices-of-various-economies;
    C.H. Robinson advisory
    https://www.chrobinson.com/en-us/resources/insights-and-advisories/client-advisories/2026q3/07-24-26-client-advisory-new-section-301-forced-labor-tariffs-now-in-effect/.
  * Legacy Section 301 (the 2018-19 China lists): 25%. Section 232: 50%, on
    steel/aluminium/copper-alloy products only. Regular MFN duty 0-7.5% depending on HS
    code. JLC quotes a total of "About 35%~92.5%".
  * JLC says its PCBA cannot use the IC/semiconductor HS-code exemptions: "JLCPCB's
    PCBA products are not integrated circuits".
* **What JLC actually charges** (https://jlcpcb.com/news/logistics-update-us-china-tariff,
  update of 2026-03-17): DDP pre-collected rate **PCB 35%, SMT (PCBA) 35%**; stencil
  90%; 3D-printed resin/nylon/PLA etc. 40%; CNC plastics including PMMA 40%; CNC
  aluminium 90%. The 35-90% rates are flat averages: "we will not refund or charge the
  difference". Individuals must ship DDP; companies may choose CPT and pay the duty
  themselves.
* **De minimis is still suspended** (since 2025-05-02 for China, 2025-08-29 for all
  countries). The Court of International Trade upheld the suspension on 2026-08-13
  (https://www.alvarezandmarsal.com/thought-leadership/uscit-upholds-ieepa-suspension-of-de-minimis-treatment-in-axle-of-dearborn;
  https://www.supplychaindive.com/news/de-minimis-status-supreme-court-trump/812785/).
  JLC orders do not travel by post, so order value does not change the rate.
* => **Budget about 35% of (boards + assembly + parts) as duty, prepaid at checkout**,
  plus any California sales tax JLC collects
  (https://jlcpcb.com/help/article/About-US-State-Sales-and-Use-Taxes exists; I did not
  read it).

### 1e. Acrylic and 3D prints from the JLC group

* **JLC3DP** (https://jlc3dp.com/): SLA resin from $0.30, build **2 days**; MJF nylon 3
  days; FDM (ABS, ASA, PLA, PA12-CF, TPU) 3 days; SLS nylon 3 days; full-colour resin
  (WJP) 4 days; binder-jet 316L 5 days. Resins listed: Grey, Black, JLC Black, 9600, X,
  LEDO 6060, CBY, Imagine Black, 8228, **8001 (transparent or translucent)**,
  full-colour.
  * 8001 resin (https://jlc3dp.com/help/article/photosensitive-8001-resin, updated
    2025-04-16): "Color: Transparent, Translucent"; build 72 h; ±0.2 mm; wall > 0.8 mm;
    heat-deflection temperature 53 °C. Transparent parts are sanded and "oil sprayed" by
    default; translucent parts are not sanded. "Not suitable for ... strong sunlight, and
    UV light environments" (relevant if violet/UV LEDs shine on it).
  * **No glow-in-the-dark material** appears in JLC3DP's material list. Print glow parts
    at home (strontium-aluminate PLA, section 5) or use a service that stocks glow resin
    (e.g. Liqcreate Hazard Glow, an SLA/DLP glow resin, https://all3dp.com/4/liqcreate-hazard-glow-in-the-dark-resin/).
  * JLC3DP cut prices on 2026-07-24 (PLA-P -18%, full-colour resin -11%)
    (https://jlc3dp.com/news/materials-finishing-pricing-update-july2026).
* **Laser-cut acrylic**: JLC has no acrylic laser-cutting service. **JLCCNC** CNC-mills
  PMMA (acrylic) and polycarbonate, "lead time from 3 business days", from $1/part
  (https://jlccnc.com/; https://jlccnc.com/blog/acrylic-and-pmma-cnc-machining). JLCCNC's
  sheet-metal service laser-cuts metal only (from $0.40, 2 days). JLC argues CNC edges
  are clearer than laser-cut edges. For edge-lit panels, ask for polished edges (flame or
  vapour polish).
* Tariff pre-collection on these: 3D-printed plastics 40%, CNC plastics 40%. JLC3DP and
  JLCCNC observed the same Sept/Oct holiday closures.

---

## 2. Prior art (links, one-line takeaways, numbers)

### 2a. PCB-coil motors and magnet movers

| Project / source (date) | Takeaway and numbers |
|---|---|
| Carl Bugeja PCB motor, IEEE Spectrum "How to print an electric motor" (2018-08-24) https://spectrum.ieee.org/how-to-print-an-electric-motor | Axial-flux, 16 mm across, 6 coils, 4 layers, **40 turns/coil**, wye connection, 3D-printed rotor with magnets; runs on 3.5-7 V; **~250 mA at 5 V, board ~70 °C**; static torque **0.9 g·cm**, almost doubled by a ferrite sheet behind the coils. (Another write-up of a different revision: 5 V, 0.7 A, 60 °C.) |
| Carl Bugeja MotorCell (Hackaday 2024-12-17) https://hackaday.com/tag/motorcell | Open-source PCB BLDC sold as a product; **~37,000 rpm**; 20 motors ran a month, >1.6 billion revolutions each, no wear seen; low torque. Uses a sensorless 3-phase fan driver (BD67173NUX, per circuitdigest). |
| Carl Bugeja linear PCB motor (OSH Park blog 2018-06-13) https://blog.oshpark.com/2018/06/13/pcbs-as-linear-motors/ | 12 coils, **5/5 mil trace/space, 140 turns**, N52 magnet in a 3D-printed slider; "low-torque linear motion". |
| Carl Bugeja Flexar flexible-PCB actuator (Tindie blog 2018-12) https://blog.tindie.com/2018/12/flexible-pcb-actuator/ | Fingertip-sized flex-PCB spiral coil flaps against a fixed NdFeB magnet; tiny force (haptics, flapping). |
| **North Pole Circuit**, Janky Jingle Crew (Hackaday 2024-12-20; GitHub https://github.com/Janky-Jingle-Crew/NorthPoleCircuit) | **Closest precedent: a holiday card PCB where a 3D-printed sleigh and reindeer with magnets are driven along PCB traces.** Two phase tracks driven with 90°-shifted sines (micro-stepping) plus a guard-rail trace that centres the magnets on curves. 4-layer, **1 oz inner copper** "to reduce phase resistance". **5 V USB-C, 500 mA total while moving**, DRV8833 drivers, CH32V003 MCUs. **Magnets 2 x 1 mm N42/N52**, press-fit and glued. Stack-up advice: minimise L1-L2 prepreg for a stronger field (JLC041611-7628 0.21 mm, which allows Economic PCBA, vs -3313 0.092 mm, which needs Standard PCBA). 50 cards built and assembled by JLC for about $8 each, but "~$90 for 5 populated boards". |
| Jeff McBride, Gauss Speedway (2022-11) https://jeffmcbride.net/gauss-speedway/ | The design North Pole Circuit copied. 4-layer; **phase ≈ 5 Ω, guard rail < 1 Ω**; 16 current steps per cycle; 2 x 1 mm disc magnets; tracks drawn with his KiCad plugin *curvycad* (https://github.com/mcbridejc/curvycad). |
| Kevin Lynagh, PCB stepper research log (2021-12-24) https://kevinlynagh.com/pcb-stepper/ | 2-layer 0.8 mm JLC boards; 1 mm-pitch coils measured 8-9 Ω, 2 mm-pitch coils 3.5 Ω. A **1 mm N52 magnet needed ~200 mA**; a 5-magnet carrier needed ~170 mA; coils on the far side of 0.8 mm FR-4 needed **600 mA vs 150 mA** for top-side coils, so he concluded 4-layer with coils near the surface. PWM above ~50 kHz starved the current (56 mA at 260 kHz vs 360 mA at 5 kHz, because of coil inductance and driver). Also summarises SRI microrobots (5 x 5 arrays of 1.4 x 1.4 x 0.4 mm N52; 0.25-0.7 A coil currents) and Vlček 2020 (200-500 mA to move a 1 x 0.5 mm disc). He could not get his pyrolytic graphite to levitate magnets. |
| Moritz v. Sivers, Magnetic Kinetic Art Display (Hackaday 2023-03-08; hackaday.io project 189880) https://hackaday.com/2023/03/08/moving-magnet-draws-stylish-shapes-on-flexible-film/ | Flex PCB with X coils on the top layer and Y coils on the bottom; drags a **2 mm magnet** under magnetic viewing film to draw shapes; 2 x TB6612FNG; coils take "up to two amperes" and get hot. |
| KTU, PCB-based planar actuation drive https://epubl.ktu.edu/object/elaba:132107906 (via search) | 2-D array of 4 mm flat coils (0.1/0.1 mm, 35 µm Cu); 0.6 mT (1 layer) / 0.9 mT (2 layers); untethered magnet mover with payload **~1.5 g pulsed, ~1 g continuous**; 101 mm/s linear, 125 rpm rotation. |
| Vikrant, Dadkhah, Moheimani, arXiv:2402.13436 (2024, rev. 2025) https://arxiv.org/abs/2402.13436 | Planar electromagnetic actuator scaling: shrinking coil pitch 10x raises force per volume ~100x and stiffness ~1000x. Use fine pitch with small magnets. |
| Miniatur Wunderland F1 track https://www.miniatur-wunderland.com/discover-wunderland/technologies/formel-1/ | Industrial-scale PCB "maglev" racing: 22 m track, 24 track boards, 90 drive + 90 location boards, 1,080 MCUs, 5,700 position and 2,800 temperature sensors; each car carries a Halbach array of "over 20 permanent magnets". |
| U. Waterloo thesis, maglev planar motor https://uwspace.uwaterloo.ca/handle/10012/20268 | Square coil arrays under a 2-D Halbach-array mover, with force/torque models (background for a "floating familiar"). |
| Rolling by a rotating field: NTNU "Development of rolling magnetic microrobots" https://scholar.lib.ntnu.edu.tw/en/publications/development-of-rolling-magnetic-microrobots-2/ ; Utah (Abbott) rotating-dipole work, e.g. US8803643B2 "Control of magnetically actuated tools in any position using a rotating magnetic source" https://patents.google.com/patent/US8803643 | A magnetised sphere follows a field rotating in a vertical plane and rolls: reported **2 rev/s -> 1.4 mm/s** for sub-mm spheres. With no slip, v = 2πfR (my estimate: a 10 mm sphere at 1 rev/s rolls ~31 mm/s). Two crossed coils driven in quadrature under a table do this. Related classic demo: a hollow aluminium ball spinning over a shaded-pole (quadrature) field, an eddy-current "induction motor" (UMN 5K20.50, https://spademos.umn.edu/5K20.50). |

### 2b. Magnetic pendulum "kickers" and chaotic pendulums

* **One coil as both sensor and driver** is the classic approach. Seiko-era patents
  US4866564A / US4868709A ("Electromagnetic drive circuit",
  https://patents.google.com/patent/US4866564A/en) use the coil's induced voltage from
  the passing magnet, a comparator against a reference, and a pulse generator that fires
  a drive pulse at the induced-voltage peak for "stable amplitude".
* **Microcontroller version** (M. Nealon, EOSC, https://www.mnealon.eosc.edu/PendulumPage4.htm):
  coil of **1480 turns of 34 AWG (222 ft, 58.9 Ω)** on a sewing-machine bobbin; NdFeB
  ring magnet 3/8" diameter x 1/2" on the rod, **~1 mm above the coil**; PICAXE 18M2
  reads the same coil with its ADC and then drives it through a Darlington; 12 V supply;
  drive pulse ~350 ms at **~35 mA** for a 2 s-period pendulum.
* MSP430 variant (allaboutcircuits thread
  https://forum.allaboutcircuits.com/threads/electromagnetic-pendulum-pulse-movement-2.205924/,
  via search): same coil feeds the comparator; a 32 kHz crystal measures the period and
  the pulse width trims the rate; estimated 3-4 months on 4 D cells.
* **Chaotic three-magnet pendulum** (magnet bob over three base magnets on an equilateral
  triangle, fractal basins of attraction): Chalkdust
  https://chalkdustmagazine.com/features/the-magnetic-pendulum/; CU Boulder demo
  https://physicslabs.colorado.edu/demos/oscillations-and-waves/oscillations/non-linear-systems/magnetic-pendulum/;
  "Basins of Attraction: A Dynamical Zoo" https://arxiv.org/pdf/2504.01580. A commercial
  variant, the "Wildwood pendulum", puts a ferromagnetic bob on a flexible shaft over one
  electromagnet plus five permanent magnets (via search). Idea for us: a PCB coil under
  the base can both read the bob (back-EMF) and kick it, while the LEDs show which basin
  won.

### 2c. Hall-sensor levitation and floating lamps

* **Attractive (hanging) levitation, analog** (ART TEC kit, after Nuts & Volts Sept 2003;
  PDF via U. Utah ECE 3510, https://my.ece.utah.edu/~ece3510/LevitationKIT.pdf): linear
  Hall sensor (Honeywell SS490/SS495A) taped to the core bottom; MIC502 fan-PWM chip as
  the controller at ~10 kHz; LMD18201 H-bridge (3 A, 24 V max). Electromagnet: any 12 V
  solenoid ≥ 8 Ω with "at least 12oz pull at 1/4"" (the author used a 32 Ω solenoid
  with a 5/16" bolt as core). Magnets 3/8" x 1/8" NdFeB. The "sweet spot" is ~1/2" below
  the coil. Idle draw < 50 mA, and current stays low when levitating stably. Tuning the
  payload mass is fiddly: "The range of viable weights is fairly small".
* **SparkFun "Magnetic Levitation"** (Alex the Giant,
  https://learn.sparkfun.com/tutorials/magnetic-levitation/all): SS496B Hall, LM358
  comparator, MOSFET, a 1 mH power inductor as electromagnet; **~80 mA at 12 V while
  levitating**; magnets ~0.5" x 0.1"; levitation window **2-3 cm** (about 1 cm with
  wireless-power parts added).
  * Its WPT add-on is a cautionary tale: ~80 kHz, primary 25 turns of 30 AWG (1"),
    secondary 100 turns. LED got **136 mW while the circuit drew 10.6 W: 2.5% link
    efficiency, 1.3% overall**.
* **Digital PID versions** (Arduino + 49E Hall + 12 V 25 mm electromagnet): common, with
  "a couple of mm" gaps and fiddly tuning. UPC thesis 2023
  https://upcommons.upc.edu/entities/publication/52199ded-e9ac-4e8c-bd82-63f2ccd9c919/full
  reports PID tuning trouble from nonlinearity and Hall-sensor pickup of the coil's own
  field.
* **Repulsive levitation modules (moon lamps etc.)**: a large ring magnet in the base
  repels a ring magnet in the float; 4 air-core coils plus 2-4 linear Hall sensors
  stabilise X/Y (JSAEM paper https://www.jstage.jst.go.jp/article/jsaem/26/1/26_238/_article).
  * Listing specs (Amazon, summarised by search): **500 g module: ~26 mm gap unloaded,
    20 mm at 100 g, 9 mm at 500 g; 12 V 2 A adapter; ~1-2 W average (~0.2 A)**
    (https://www.amazon.com/Magnetic-Levitation-Module-Floater-Supply/dp/B0HF3VF9RB).
  * 1 kg module 18-25 mm. Bambu Lab kit: 200 g, 12 V 2 A, built-in LED
    (https://3djake.com/bambu-lab/magnetic-levitation-kit).
  * The dedicated levitation WPT module: 12 V transmitter, 48 mm OD / 30 mm ID coils,
    claims "max effective distance 80 mm"
    (https://www.amazon.com/Magnetic-levitation-dedicated-wireless-charging/dp/B077CMYNTS).
  * Erich Styger's moon lamp (https://mcuoneclipse.com/2019/07/06/diy-wireless-magnetic-levitating-moon-lamp/,
    2019-07-06): 500 g module; WPT receiver coil kept ~5 mm from the transmit coil.
    Elektor snail lamp (2024-08-15): keep the receiver coil off the magnet's axis or the
    magnet degrades charging.
  * Patent snippets ("Lighting fixture with a levitation function",
    https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12601466): lamp
    holders levitate 5-20 mm; coil spacing < 2 cm.
  * Flyte levitating bulb: inductively powered, max 60 lm
    (https://www.hongkiat.com/blog/flyte-levitating-lightbulb/).

### 2d. Small inductive/resonant wireless power to LEDs with PCB coils

* **Standards' bands**: Qi BPP ~87/100-205 kHz with coils typically ~5 mm apart (Qi
  summaries via search: https://itwissen.info/en/Qi-standard-122731.html,
  https://ib-lenhardt.com/jp/kb/qi-wireless-charging); **NFC Forum WLC: 13.56
  MHz, up to 1 W over ≤ 2 cm** (https://appleinsider.com/articles/20/05/05/apple-sponsored-nfc-forum-adopts-wireless-charging-spec-amid-bilateral-iphone-charging-rumors);
  AirFuel Resonant: 6.78 MHz, multi-device, "several inches".
* **Off-the-shelf maker modules**:
  * XKT-510 + T3168 pair: 12 V in, 5 V 600 mA out, "1-20 mm", 30 µH transmit coil
    (datasheet via https://www.robotsepeti.com/Data/EditorFiles/ya/pololu/elecfreaks-EF03090-XKT-510.pdf).
  * Adafruit 5140 "Small Inductive Coil and 10 Wireless LED Kit": 70 mm transmit coil,
    5 V, "sensing distance 0-80 mm", 16 x 12 x 2.5 mm LED receivers, $14.95
    (https://www.adafruit.com/product/5140).
  * Hackaday "Wireless LEDs Aren't Really Magic" (2021-11-29, https://hackaday.com/tag/wireless-led/):
    "The transmitter sends 217 kHz into a 2.2 mH inductor. A capacitor resonates the
    coil and drives the attached LED."
* **PCB spiral-coil data from papers**:
  * Mutashar et al. 2014 (https://pmc.ncbi.nlm.nih.gov/articles/PMC4168449): 13.56 MHz;
    transmit coil 56 mm OD, 30 turns, 0.5 mm traces (4.92 µH, Q 190, Rogers 4350);
    receive coil 11.6 mm, 8 turns (1 µH, Q 53); **6 mm gap: 80% link efficiency** with
    an ideal source, **45% with their PA**; k = 0.087; maximum 22 mm in air.
  * Pon et al., BEEI 2019 (https://journal.beei.org/index.php/EEI/article/view/1593):
    dual-band printed spiral resonators, **72.3% at 6.78 MHz and 74.0% at 13.56 MHz
    across 30 mm**; > 50% simulated out to 38 mm.
  * Rule of thumb from these: **at 5-20 mm, resonant PCB-coil links reach 70-80%
    coil-to-coil when coils are ≥ 2-3x the gap and high-Q (MHz)**. Simple hard-switched
    kHz links are often in single digits (SparkFun: 1.3%).
* **Open-source designs**: thin. GitHub (searched 2026-10-07) has only student-scale
  repos (e.g. jairnarvaez/Simultaneous-wpt-nfc; sofiamonty/toothbrush-charger-pcb in
  KiCad; intisharalam/WPT_Designer, a class-DE/E calculator). Plan on designing our own
  link (class-D/E at 6.78 MHz, or a Qi-like 100-200 kHz half-bridge) and measuring it
  with a NanoVNA.
* **FCC note** (also section 4c): KDB 680106 says WPT above 9 kHz is an intentional
  radiator under Part 15 and/or Part 18. No FCC inquiry is needed when "the power
  transfer frequency is below 1 MHz", output is "≤ 15 watts" per coil, the client device
  sits in contact, and fields at ≥ 20 cm are < 50% of MPE
  (https://www.element.com/resources/articles/wireless-power-transfer-and-wireless-charging,
  2025-08-20). Only matters if the design is marketed.

### 2e. Diamagnetic graphite levitation and light-driven motion

* **Kobayashi & Abe, "Optical Motion Control of Maglev Graphite"**, JACS 134, 20593-20596
  (2012), DOI 10.1021/ja310365k (phys.org, 2012-12-27,
  https://phys.org/news/2012-12-magnetically-levitating-graphite-laser.html): a 3 mm
  pyrolytic-graphite disk over alternating NdFeB magnets is pushed by light because
  heating lowers its diamagnetic susceptibility. The disk spins "**over 200 rpm**" in
  focused sunlight.
* **Replication warns against the light-driven idea**: Ewall-Wice et al. (USNA), IEEE
  Trans. Magn. 2019 (https://usna.edu/MNEDept/_files/documents/brownell_files/Ewall-Wice_TMAG_2019.pdf):
  * They summarise Kobayashi & Abe as using "a **405 nm, 300 mW** laser" on a 150 µm x 3
    mm disk, reaching 45 mm/s. In their replication with a 405 nm 500 mW engraver diode,
    "the airflow from the cooling fan attached to the heat sink housing was the primary
    reason for the displacement". With the airflow blocked, "no displacement was
    observed".
  * Real photothermal motion needed **300-500 mW at 975 nm** on 25 µm flexible graphite
    sheet (ΔT ≈ 10 °C) and **2 W at 458/488 nm** on a 140 µm sanded plate (ΔT ≈ 30 °C),
    giving 7.7 and 18 mm/s. Magnet array: 12 x 6 of 6.35 mm NdFeB, 0.5 T at the surface.
  * => **Tens of mW from LEDs will not move graphite; lasers that would are Class 3B/4.
    Not for a 6-year-old's toy.**
* Theory: Fujimoto & Koshino, Phys. Rev. B (2019), arXiv:1904.09741
  (https://arxiv.org/abs/1904.09741). ΔT = 10 K across a 10 mm square of 25 µm graphite
  gives ~2 x 10⁻³ mg-force (4 mm/s²) at 300 K. Room-temperature levitation height peaks
  at ~0.65 mm for 25 µm disks.
* Typical static gap: Romagnoli et al., APL 122, 094102 (2023), arXiv:2211.08764. A 10 x
  10 x 0.77 mm plate (79-147 mg) over a 2 x 2 checkerboard of 12.7 mm N52 cubes floats
  with its centre 1.46 mm above the magnets (**about 1.1 mm air gap**); resonances 17 Hz
  vertical, 4 Hz lateral.
* Kevin Lynagh (2021) could not get his graphite to levitate small magnets. Buy
  known-good material such as K&J's PG1 (section 5).
* A passive floating graphite flake over a magnet checkerboard is still a lovely static
  exhibit, but the magnets must be captive (section 4a).

### 2f. Halloween and art PCBs for inspiration

* Spooky Pumpkin Badge (Arnov Sharma) https://www.hackster.io/Arnov_Sharma_makes/spoooky-pumpkin-badge-2abe0e:
  LEDs on the back shine through FR-4 via mask openings; astable multivibrator.
* Hackaday 2023 Halloween Hackfest flickering pumpkin pin https://hackaday.com/tag/pumpkin-pin;
  Tindie "Halloween ghost pin badge" (2023-09) https://blog.tindie.com/2023/09/halloween-ghost-pin-badge/;
  PCBWay shared pumpkin PCB (NE555, KiCad + FreeCAD outline)
  https://www.pcbway.com/project/shareproject/Halloween_pumpkin_PCB_36fa00f3.html.
* **Backlit FR-4**: bare FR-4 is translucent where copper, mask and silk are all removed.
  Hackaday's "Backlit PCB Panel As Wall Art" uses copper-fill art with translucent gaps
  as the diffuser. A hackaday.io log (project 167113, via search snippet; the page would
  not load) found FR-4 absorbs strongly, so light spreads only **~15 mm** even with
  copper pours as reflectors. Put LEDs close to each glowing area.
  * Leiton makes true transparent PCBs (~55% transmittance, diffuse)
    https://www.leiton.de/transparent-pcb.html.
* **Edge-lit acrylic**: Solarbotics' two-layer engraved acrylic pendants (Hackaday
  2017-07-28, https://hackaday.com/2017/07/28/edge-lit-pendants-show-two-layers-are-better-than-one/).
  Light is trapped by total internal reflection (~42° critical angle) and escapes at
  engraved marks. Engraved acrylic slotted into a PCB edge with side-emitting LEDs is a
  common trick. Good for an owl/bat/witch silhouette that glows orange/purple.
* JLC multi-colour silkscreen (1a) suits cute full-colour artwork, but only with a white
  board.
* The North Pole Circuit (2a) is the best "holiday art PCB + real physics" precedent to
  cite and beat.

---

## 3. Names

GitHub REST API repo search (by name, description, README) and web searches, 2026-10-07;
trademark checks on Trademarkia (fuzzy search). This is a quick look, not a legal
clearance search.

| Name | GitHub | Web / products | Trademark (Trademarkia) | Verdict |
|---|---|---|---|---|
| **Faraday's Familiar** | 0 hits ("faraday's familiar", "faradays familiar", "faraday familiar" in name) | Nothing but Michael Faraday biography | No mark combining FARADAY + FAMILIAR (many FARADAY marks in classes 9, 42 etc.) | **Free** (FAMILIAR-alone caveat below) |
| **Spooky Action / Spooky Action at a Distance** | 21 repos named spooky-action and 21 with the phrase in name/description: mostly software. Hardware: `jmc1228/SpookyActionProject` (MIT Museum "Entangled Particles" prototype, 2016, Eagle) and `ozgb/ghost-lamps` (2023 ESP32 colour-synced lamps described as "Spooky action at a distance!") | Ubiquitous Einstein phrase; also a 2015 book title (George Musser) | No exact mark seen. Related live marks: **ACTION AT A DISTANCE** (S. L. Nelson, class 9) and **SPOOKY2** (Nanjing Clean Energy, class 9: electronic coils / RF generators) | **Usable but crowded and generic**; poor for search and identity |
| **Maxwell's Witch** | 0 | Only unrelated novels (e.g. "Maxwell's Curse") | No MAXWELL + WITCH mark | **Free** |
| **Owlternating Current** | 0 | 0 web hits | **0 results** | **Free** |
| **Hoot Induction** | 0 | 0 (only HR "induction" pages) | No exact mark (many HOOT marks, e.g. "HOOT OWL HOOT" board game, class 28) | **Free** |
| **Lenz Lantern** | 0 | Only "lens lantern" (lighthouse lamp) and "LED Lenser" | No exact mark (LENZ marks exist, incl. Lenz Technology class 9) | **Free** |
| **Jack-o'-Lenz** | 0 (one unrelated text hit) | 0 | None seen | **Free** |
| **Boo-ard** | No exact; "booard" names 22 unrelated repos (e.g. a task manager) | Used for Halloween snack-board puns ("BOO-cuterie" boards) | **0 results for BOOARD** | **Free**, but weak |
| **Familiar** (alone) | Nothing relevant | **Familiar Machines & Magic** (Colin Angle, iRobot co-founder) launched robot pets called **"Familiars"** in May 2026 (https://www.robotics247.com/article/roomba-inventor-and-irobot-co-founder-colin-angle-introduces-familiar-machines-magic) | **FAMILIAR, live/pending, Familiar Machines & Magic Inc., filed 2024-10-29, classes 9/10/42 (AI-enabled zoomorphic robots)**; FAMILIAR (Familiar, Ltd.) children's clothing, class 25; an abandoned FAMILIAR plush-toy filing (class 28) | **Avoid as a bare name**; fine inside a phrase like "Faraday's Familiar" |

* **github.com/gallicchio/halloween1, /halloween2026, /halloween**: API returns 404 for
  all three (absent, or private). gallicchio has 7 public repos (ai_unleashes_chaos,
  basicSDR, gnuradio-pulsar-dispersion, icepi-zero-dac-adc, learnSDR, OpticsLab2021,
  RFSoC4x2play).
* My ranking for a distinctive, searchable, cute name: **Owlternating Current**, **Faraday's
  Familiar**, **Maxwell's Witch**, **Hoot Induction**, **Jack-o'-Lenz** are all
  unencumbered. "Spooky Action" is cute but crowded; avoid bare "Familiar".

---

## 4. Safety and regulatory (children's electronic toy)

### 4a. Small powerful magnets

* **16 CFR part 1262 (Safety Standard for Magnets)**: in force for products made after
  2022-10-21. Each loose or separable magnet that fits in the small-parts cylinder must
  have a **flux index < 50 kG²·mm²**. It covers products for "entertainment, jewelry ...
  mental stimulation, stress relief". "**Toys that are subject to the requirements of 16
  CFR part 1250, which incorporates by reference ASTM F963, are exempt**" (they are
  covered by F963 instead). CPSC: "loose" and "separable" are not defined; "firms should
  certainly exercise due diligence". Sources:
  https://www.cpsc.gov/Business--Manufacturing/Business-Education/Business-Guidance/Magnets;
  https://www.cpsc.gov/FAQ/Magnets-FAQs; definitions
  https://www.law.cornell.edu/cfr/text/16/1262.2.
* **ASTM F963 §4.38 Magnets** (toys for children under 14; mandatory via 16 CFR 1250;
  third-party testing required per the CPSC F963 chart,
  https://www.cpsc.gov/Business--Manufacturing/Business-Education/Toy-Safety/ASTM-F-963-Chart).
  As summarised in CPSC's 2022 final-rule briefing
  (https://www.cpsc.gov/s3fs-public/2022-08-17-Final-Rule-Safety-Standards-for-Magnets.pdf):
  * A "**hazardous magnet**" is small (fits entirely in the small-parts cylinder) **and**
    has flux index **≥ 50 kG²·mm²**. A "**hazardous magnetic component**" is any small
    part with an attached or embedded magnet of flux index ≥ 50.
  * Flux index = (maximum surface flux density in kG)² x (cross-sectional area in mm²),
    measured per F963 §8.25.1-8.25.3.
  * Toys may not contain a loose as-received hazardous magnet or component, "**and may
    not liberate**" one after use-and-abuse testing: "**soaking under water, cycling
    attachment and detachment, drop testing, torque testing, tension testing, impact
    testing, and compression testing**".
  * "Magnetic/electrical experimental sets" for ages 8+ need only warnings. That does not
    apply to a 6-year-old's toy.
  * Per search summaries of F963, magnets "used in motors, relays, and other applications
    where magnetic properties are not part of the play pattern" are exempt. **Ours ARE
    the play pattern**, so the rule applies.
* **Small-parts cylinder**: 16 CFR 1501.4, Figure 1. It approximates the fully expanded
  throat of a child under three; it is 1.25 in (31.7 mm) in diameter, 1.0-2.25 in
  (25.4-57.1 mm) deep (dimensions from the CFR figure as commonly quoted; the LII text
  shows only the figure). Any 10 x 3, 12 x 3, 15 x 5 mm disc or ≤ 30 mm sphere fits.
* **Use-and-abuse forces for ages 3-8** (16 CFR 1500.53,
  https://www.law.cornell.edu/cfr/text/16/1500.53):
  * drop: "four times from a height of 3 feet" onto vinyl tile over concrete;
  * torque: 4 in·lbf (0.45 N·m);
  * tension: 15 lbf (67 N);
  * compression: 30 lbf (133 N);
  * flexure: 60°/120° arcs, 30 cycles.
* **Flux-index estimates** (my calculation: centre-of-face field of a disc,
  B = (Br/2)·L/√(L² + R²) with N52 Br = 1.44 T; sphere pole field = (2/3)·Br; idealised
  upper estimates):

  | Magnet | Estimated flux index (kG²·mm²) | Over the 50 limit? |
  |---|---|---|
  | 1 x 1 mm disc | ~33 | No |
  | 2 x 1 mm disc | ~81 | **Yes** |
  | 10 x 3 mm disc | ~1,100 | **Yes** |
  | 12 x 3 mm disc | ~1,200 | **Yes** |
  | 15 x 5 mm disc | ~2,800 | **Yes** |
  | 5 mm sphere | ~1,800 | **Yes** |
  | 10 mm sphere | ~7,200 | **Yes** |

  => **Every NdFeB magnet we would use is a "hazardous magnet" if it can get out.**
* **What "fully encapsulated so it cannot be liberated" means in practice**: the magnet
  sits inside a part that is itself **not** a small part (does not fit the cylinder),
  e.g. a ≥ 32 mm 3D-printed owl or bat body. It must stay captive after soaking, the 3 ft
  drops, 4 in·lbf torque, 15 lbf pull and 30 lbf squeeze. Practical design choices:
  * captive pockets that are printed over (pause-and-insert) or closed with a
    solvent-welded or screwed cap, not a press-fit or glued-on face;
  * no thin walls a child can split, and no seams the magnet can be prised through;
  * a magnet-carrying puck must never break into pieces that fit the cylinder.

  For the gift, test by hand at those forces. Bare magnets "on the board" for a
  6-year-old are a no-go: magnet ingestion causes intestinal perforation.
* **Mains-powered toys**: 16 CFR 1505 covers children's articles powered from 120 V
  branch circuits, but its definition excludes "components which are powered by circuits
  of 30 volts r.m.s. (42.4 volts peak) or less"
  (https://www.law.cornell.edu/cfr/text/16/1505.1). A listed external 12 V adapter keeps
  the toy side out of most of it. Its surface-temperature limits are still a good target
  for anything a child touches: e.g. plastics 60-85 °C, metals 50-65 °C, by surface class
  (https://www.law.cornell.edu/cfr/text/16/1505.7). With 60 W available, fuse or
  current-limit each coil.

### 4b. Blue, violet and UV LED photobiological safety (IEC 62471)

* **IEC/EN 62471 Table 6.1, emission limits for continuous-wave lamps** (from the EN
  62471:2008 text, https://www.lisungroup.com/wp-content/uploads/2020/02/EN62471-2008-Standard-Free-Download.pdf).
  Non-general-lighting sources (such as indicator LEDs) are assessed **at 200 mm**.

  | Hazard | Exempt | RG1 (low) | RG2 (moderate) |
  |---|---|---|---|
  | Actinic UV, E_S (S(λ)-weighted) | 0.001 W/m² | 0.003 | 0.03 |
  | Near-UV (UV-A) eye, E_UVA | **10 W/m²** | 33 | 100 |
  | Blue light, L_B | 100 W/m²/sr | 10,000 | 4,000,000 |
  | Blue light, small source (α < 0.011 rad), E_B | 1.0 W/m² | 1.0 | 400 |

  Weighting factors: actinic S(395 nm) = 0.000036, S(400 nm) = 0.000030; blue-light
  B(395) = 0.05, B(400) = 0.10, B(405) = 0.20 (B peaks ~435-440 nm). UV-A limit: "For
  exposure times greater than 1000 s ... E_UVA shall not exceed 10 W/m²".
* **Datasheet examples**:
  * Würth WL-SUMW 15335339AA350, a 395 nm emitter of **800-1300 mW, 130°**, is labelled
    "**IEC-62471 [Risk Group 1]**"
    (https://www.we-online.com/components/products/datasheet/15335339AA350.pdf).
  * Würth's 140 mW WL-SUTW 395 nm part carries only the "avoid direct eye and skin
    exposure" warning.
  * A reseller lists Nichia NCSU275 (365-405 nm, 370 mW, 120°) as **Risk Group 3**
    (https://www.ledrise.eu/leds/nichia-smd-led-uv-ncsu275-405nm-370mw-at-500ma-185w-emitter.html).
  * So classifications vary with beam and method, and makers label UV parts
    conservatively.
* **Indicator-scale estimate** (mine). A 30 mW, 405 nm, roughly Lambertian LED gives
  E ≈ 0.24 W/m² at 200 mm:
  * E_B ≈ 0.05 W/m² against the 1.0 limit;
  * for a 395 nm part, E_UVA ≈ 0.24 W/m² against the 10 W/m² limit;
  * so **exempt at the standard 200 mm distance**.
  * Irradiance scales as 1/d². At 20 mm the same LED gives ~24 W/m² UV-A, above the
    1000-s exempt limit and in RG1 territory. A narrow 30° lens multiplies on-axis
    values ~5-10x.
* Practical rules for a kid's toy:
  * keep violet/UV LEDs at a few mA behind diffusers and pointed at the scene (e.g. to
    charge glow-in-the-dark parts), not at the viewer;
  * no "UV flashlight" mode;
  * remember 395 nm looks dim (low photopic response), so the blink/aversion reflex does
    not protect;
  * 405 nm is the safer choice. 8001 resin and many plastics yellow under UV.
* The EU toy standard EN 62115:2020 (Annex E) applies the IEC 62471 LED limits to toys
  (https://evs.ee/en/evs-en-iec-62115-2020). That is what a commercial toy would be held
  to. US toy rules have no LED-specific limit.

### 4c. FCC Part 15 for a home-built WiFi device

* **47 CFR 15.23 Home-built devices** (https://www.law.cornell.edu/cfr/text/47/15.23):
  "(a) Equipment authorization is not required for devices that are **not marketed, are
  not constructed from a kit, and are built in quantities of five or less for personal
  use**." "(b) It is recognized that the individual builder of home-built equipment may
  not possess the means to perform the measurements for determining compliance ... The
  builder is expected to employ good engineering practices to meet the specified
  technical standards to the greatest extent practicable. The provisions of §15.5 apply
  to this equipment." §15.5 means: no harmful interference, and stop operating if it
  causes some.
* **Kit** (§15.3): "Any number of electronic parts, usually provided with a schematic
  diagram or printed circuit board, which, when assembled in accordance with
  instructions, results in a device subject to the regulations in this part". Selling
  or distributing kits, even a board plus parts, is marketing a kit, which needs
  authorization.
* **Marketing** (§2.803(a), https://www.law.cornell.edu/cfr/text/47/2.803): "sale or
  lease, or offering for sale or lease, including advertising for sale or lease, or
  importation, shipment, or distribution for the purpose of selling or leasing".
* **Modules and antennas** (§15.212, https://www.law.cornell.edu/cfr/text/47/15.212):
  "All single or split modular transmitters are approved with an antenna", which must be
  "permanently attached or employ a 'unique' antenna coupler". A custom bat- or
  owl-shaped trace antenna on an ESP32 chip or module is outside the module's grant
  (needs a permissive change or new certification if marketed). For our ≤ 5 personal
  units §15.23 covers it, but we should still meet §15.247 power and antenna-gain limits
  by design.
* **If the design is published open source**: publishing files is not "marketing". Each
  builder who makes ≤ 5 for personal use, not from a kit, is under §15.23 themselves.
  The obligations change if anyone **sells** boards, kits or finished units: then
  certification (or SDoC for the unintentional-radiator parts) applies to the seller.
  Using an unmodified pre-certified module with its approved antenna keeps that path
  simple. Put a README note to that effect.
* **Wireless power** also falls under FCC rules if marketed (see 2d, KDB 680106:
  < 1 MHz, ≤ 15 W per coil, contact use and ≥ 20 cm fields < 50% MPE mean no FCC
  inquiry is needed).
* General: CPSC children's-product rules (CPC certificate, third-party testing, tracking
  labels) attach to products made or sold in commerce, not a one-off gift. If boards are
  ever sold for children, F963 §4.38 magnet testing and small-parts testing need a
  CPSC-accepted lab.

---

## 5. Amazon availability (representative listings and prices)

Amazon blocked automated price reads (the "To discuss automated access" page;
WebFetch got titles but no prices), so links are Amazon listings found by search on
2026-10-07, and **prices come from search snippets or the named non-Amazon retailer**.
Check the live Amazon price before ordering.

| Item | Representative Amazon listings | Price seen (source) |
|---|---|---|
| **12 V 5 A (60 W), UL, 5.5 x 2.1 mm** | Geekworm PSU60 "UL Listed" https://www.amazon.com/dp/B0BDF89DCB ; AOYADAISU "UL Listed" https://www.amazon.com/dp/B0CG5XGP3W and https://www.amazon.com/dp/B0C464B3MH ; PryEU 60 W UL (12 tips) https://www.amazon.com/dp/B07BGZQXKW ; Meiyue 60 W UL https://www.amazon.com/dp/B0BPSQ84TT ; DEMASLED "UL Certified" https://www.amazon.com/dp/B00HQ0IYAU (search said currently unavailable) | Geekworm 12 V 5 A **$15.51** (search snippet); Geekworm's own store https://geekworm.com/products/psu60. Typical $13-20. |
| **12 V 3 A (36 W), UL, 5.5 x 2.1 / 2.5 mm** | PryEU 36 W UL https://www.amazon.com/dp/B086SQLRBP ; MIXGOO 12 V 3 A [UL Listed], 2.1 and 2.5 tips https://www.amazon.com/dp/B095XD1TD2 ; Tonton 36 W UL/FCC https://www.amazon.com/dp/B0CJ2TDWQT ; ANVISION 12 V 3 A https://www.amazon.com/dp/B01C010YJI ; ALITOVE 3 A (2.5 and 2.1) https://www.amazon.com/dp/B07VQGHSWY | Elsewhere: Parts Express **$6.97**, Arcade Renovations **$9.99**, Walmart $23.99 (search snippets). Amazon typically ~$9-14. |
| **USB-C PD charger with 12 V and/or 15 V** | Amazon Basics 65 W one-port GaN (PD 5/9/12/15/20 V, **non-PPS**) https://www.amazon.com/dp/B087MD5MYH ; Seyas 65 W (5/9/12/15/20 V, PPS) https://www.amazon.com/dp/B08SK5469W ; Powerland 65 W dual-C (PPS) https://www.amazon.com/dp/B0BM8LPJ77 ; Baseus 65 W 4-port https://www.amazon.com/dp/B0B9WJ6VHN | Amazon Basics 65 W **$10.99 on sale (list $22.99)**, Slickdeals 2026-02-26 (https://slickdeals.net/f/19254304-amazon-basics-65w-one-port-gan-usb-c-wall-charger-w-power-delivery-white-11-free-s-h-for-prime-members). **Design note**: PD fixed voltages are 5/9/15/20 V and **12 V is optional**, so many chargers (e.g. some Apple bricks) lack it. A 15 V contract is the more universal choice. |
| **N52 discs 10 x 3 mm** | AplysiaTech N52 D10x3 60-pack https://www.amazon.com/clp/B0GF7RLFXR ; AplysiaTech N52 3/8" x 1/8" 50-pack (black epoxy) https://www.amazon.com/clp/B0GRTMPKH7 ; MAGNEZMATIC 10x3 countersunk N52 36-pack (search) | Elsewhere: Magnet Baron 50 pcs **$25.99**; Total Element 50-pack **$27.26**; JC Magnetics $0.54 ea at 50+ (search snippets). |
| **N52 12 x 3 mm** | "N52 Magnets 12mm x 3mm 40 Pack" (search result); Zoprima N52 discs 12 pcs https://www.amazon.com/dp/B0BGCDZYGY | ~$10-15 for 20-40 pcs (typical; no snippet price). |
| **N52 15 x 5 mm** | Search found no exact 15 x 5 listing (10 x 5 mm N52 https://www.amazon.com/dp/B0CZV1B83Q). Specialty shops stock 15 x 5. | n/a |
| **N52 spheres** | Bunting N52 spheres https://www.amazon.com/dp/B0H9L4KFTT ; Applied Magnets sphere store https://www.amazon.com/stores/AppliedMagnets/SphereBall_NeodymiumMagnets/page/E8ED8BF0-073C-4CE6-BA58-0B3FAE88D11C ; "N52 0.625" sphere 8-pack" (search) | Elsewhere: Magnet Baron 10 mm N52 spheres **4 for $9.99** (search snippet). |
| **Glow-in-the-dark PLA (strontium aluminate)** | SUNLU glow PLA (green/orange/blue/yellow/white) https://www.amazon.com/dp/B0C4LV6TRR , orange-glow https://www.amazon.com/dp/B0GR4YW65D ; AMOLEN glow blue https://www.amazon.com/dp/B07GQTFLSY ; Everyglow https://www.amazon.com/dp/B09KLP1QXT ; FILL-3D https://www.amazon.com/dp/B0FXC8CZ69 | SUNLU on Amazon **~$23.45 (≈$21.16 with Subscribe & Save)**, SUNLU store $19.99 sale (search snippet). Listings rarely name the phosphor; strontium aluminate is the usual long-glow (green/aqua) type. Glow PLA is abrasive, so use a hardened or 0.6 mm nozzle. |
| **Pyrolytic graphite** | 10 x 10 x 0.3 mm plate https://www.amazon.com/clp/B0F1JZ4PZ3 ; TBQATNTS 10 x 10 x 1 mm https://www.amazon.com/dp/B0GTTS8RKB ; levitation demo kit https://www.amazon.com/dp/B00EAXPJB8 ; "Pyrolytic Graphite Magnetic Levitation Experiment" https://www.amazon.com/dp/B0DCNPX8FZ | Known-good elsewhere: K&J Magnetics PG1 32 x 16 x 0.75 mm **$7.20**, 25 x 25 x 1 mm $11.40 (https://www.kjmagnetics.com/products/pyrolytic-graphite); Apex kit $39.99. Lynagh's bad experience argues for K&J. |
| **12 V iron-core electromagnets** | P20/15 (2.5 kg / 25 N, "12 V 0.25 A, 3 W", M3) e.g. 5-pack https://www.amazon.com/dp/B0G3GY11L7 , TOMSHIELE 20 x 15 mm 25 N https://www.amazon.com/dp/B0CTC53LQ6 , Heschen HS-P20x15 https://www.amazon.com/dp/B078KBJNFC ; P25/20 ("12 V 0.33 A, 4 W, 5 kg", some listed 8 kg/80 N, M4) https://www.amazon.com/dp/B0DGXY8F42 , https://www.amazon.com/dp/B0F2Z7P6C9 | eBay P20/15 **~$10-12 each** (search snippets); several Amazon pages showed "No featured offers". |
| **Magnetic viewing film** | CMS Magnetics 4" x 6" green https://www.amazon.com/dp/B0B6KZZZCM ; CMS 12" x 12" https://us.amazon.com/clp/B000UV6ZR6 ; Luganni 3" x 4" https://www.amazon.com/dp/B07CGMG1JL | CMS 4x6 **~$9.99-14.59**, 6x6 ~$13-14 (search snippets: Walmart/other sellers). |
| **NanoVNA** | NanoVNA-H4 (SEESII, AURSINC, Nooelec bundle) https://www.amazon.com/dp/B085CFHTBM , https://www.amazon.com/dp/B07T6LXNTV , https://www.amazon.com/dp/B08FD4Q49R ; NanoVNA-F V3 1 MHz-6 GHz https://www.amazon.com/dp/B0CCTC88RX | H4: Radioddity **$92.99**, Nooelec $134.95, eBay ~$79-92 (search snippets). The F V3 or a LiteVNA covers 2.4 GHz for the trace antenna; the H4 tops out at 1.5 GHz but suits WPT coils (MHz). |

Extra listing, not requested but relevant: "Magnetic Levitation Module 500 g with LED
and power supply" https://www.amazon.com/dp/B0HF3VF9RB and the dedicated levitation
wireless-power module https://www.amazon.com/dp/B077CMYNTS (section 2c).
