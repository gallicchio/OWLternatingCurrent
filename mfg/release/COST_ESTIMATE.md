# OWLternating Current rev A: cost estimate

Written by `mfg/make_release.py` on 2026-10-08.  Parts: JLCPCB's live prices and stock (their parts API, asked at the times in the table).  Assembly fees: JLCPCB's published list (jlcpcb.com/help/article/pcb-assembly-price, updated 2026-09-09).  The bare panels: an estimate with a range.

**The order:** 5 bare panels of 245.2 x 223.2 mm (547 cm2; all 6 boards on each), 4 layers, 1.6 mm, purple, ENIG, 1 oz inner copper; **2 of them assembled, on both sides** (Standard PCBA).

| item | how | cost |
|---|---|--:|
| bare panels | ESTIMATE, $44-175: GPiBridge's cart (2026-10-06, 4 layers, ENIG: $24.80 for 5 boards of 60 x 25.5 mm) for the fixed part, plus 2736 cm2 at $70.6-350 per m2 (JLCPCB's published 4-layer board charge, and five times it for a small order), plus up to $6 for each of the 5 further designs and $25 for 1 oz inner copper (neither is published); purple costs the same as green (JLCPCB) | $109.31 |
| assembly setup | Standard PCBA, both sides | $51.12 |
| stencils | one for each side | $16.42 |
| feeder loading | 67 distinct parts (BOM lines) x $1.53: Standard PCBA loads a feeder for every part, Basic and Extended alike | $102.51 |
| SMD joints | 800 pads a panel x 2 panels x $0.0016 | $2.56 |
| through-hole | $3.58 labour an order + 73 joints a panel x 2 x $0.0164 | $5.97 |
| panel of 6 designs | JLCPCB's fee for a panel with more than one design | $8.21 |
| packing | $0.50 + $0.00003 per cm2 | $0.53 |
| parts | 244 placements a panel on 67 BOM lines, for 2 panels with JLCPCB's attrition, at the price break for that quantity | $69.48 |
| **total before shipping and duty** | | **$366.11** |
| an assembled panel | the total over 2 | $183.06 |

The range on the bare panels moves the total from $300.38 to $431.84.  US duty, collected by JLCPCB under DDP at 35 % of the PCBs and the assembly (their tariff FAQ, 2026-09-09), adds about $128.14; shipping (UPS Express Saver DDP to California) is shown at checkout.

## Per-part fees: Basic, Preferred, Extended

| library | distinct parts | placements a panel |
|---|--:|--:|
| Basic | 29 | 144 |
| Preferred | 2 | 2 |
| **Extended** | **36** | 98 |

On Standard PCBA every distinct part costs the same $1.53 to load, Basic or Extended (Preferred parts are exempt only on Economic): $102.51.  On Economic PCBA, which purple 4-layer boards cannot have, the 36 Extended parts alone would cost $110.52 and Basic and Preferred nothing.  5 part(s) sit on both sides (C1525, C15849, C97946, C516136, C2897409); if JLCPCB loads them once a side, add $7.65.

The 36 distinct Extended parts: C160389 (BM03B-SRSS-TB(LF)(SN)), C160472 (LTST-S270KFKT), C165948 (TYPE-C-31-M-12), C167223 (FXL0630-100-M), C173431 (BZT52C10), C1855818 (DRV8874PWPR), C189961 (NS4150B), C20625731 (ABM8-272-T3), C25100 (0402WGF270JTCE), C266123 (DRV5055A4QDBZR), C2841482 (AO4407A), C2894988 (PZ254-2-08-W-8.5), C2897409 (PM254-2-08-Z-8.5), C2934295 (FRL1206FR500TS), C311983 (TPS54302DDCR), C364577 (LTR-303ALS-01), C3715882 (TMAG5273A2QDBVR), C381116 (DC-005-5A-2.0), C38732 (OPA2333AIDR), C41378174 (RP2354A), C42411119 (AOTA-B201610S3R3-101-T), C431540 (MSK12C02), C46550472 (MA35V470M10X13), C465729 (UCC27524DR), C516136 (HL-A-3528S7VC-S1-13HL), C516304 (HL-AF-5060S22OC-3-S1-THL), C51933300 (GL0603PU01), C530531 (GSPK2307P-8R1W), C5645 (74HC4051PW,118), C701961 (LP5036RJVR), C77069 (GRM21B5C1H223JA01L), C7835 (SN74LVC1G14DBVR), C910846 (BSMD2920-500-16V), C965800 (XL-1608UOC-06), C967633 (LSM6DS3TR-C), C97946 (GRM31C5C1H104JA01L).

## What to look at

- The bare panels are the least certain line ($43.58 to $175.04): read the price off JLCPCB's cart and put it in `PCB_QUOTE` in `mfg/make_release.py`
- Feeder loading is the largest assembly fee: $102.51 for 67 distinct parts.  Each part dropped or merged into another value saves $1.53
- **C42411119 AOTA-B201610S3R3-101-T** costs $9.06 for the order (32 x $0.28)
- **C25100 0402WGF270JTCE** costs $9.02 for the order (6941 x $0.00)
- **C1855818 DRV8874PWPR** costs $8.07 for the order (8 x $1.01)
- **C701961 LP5036RJVR** costs $5.09 for the order (4 x $1.27)
- **C967633 LSM6DS3TR-C** costs $3.03 for the order (2 x $1.52)
- **C516136 HL-A-3528S7VC-S1-13HL** costs $2.88 for the order (52 x $0.06)
- **C25100 0402WGF270JTCE**: 45633 in stock against 6941 for this order: order soon, or it may run out
- Not in the total: baking the moisture-sensitive parts before assembly (JLCPCB recommends it for MSL 3 and up, as the LGA-14 accelerometer is; about $7.50), shipping, and duty

## Parts (67 BOM lines)

| LCSC | part | per panel | ordered | library | unit | line | stock | left after | asked |
|---|---|--:|--:|---|--:|--:|--:|--:|---|
| C42411119 | AOTA-B201610S3R3-101-T (3.3uH) | 1 | 32 | Extended | $0.2830 | $9.06 | 347 | 315 | 2026-10-08 21:05 |
| C25100 | 0402WGF270JTCE (27) | 2 | 6941 | Extended | $0.0013 | $9.02 | 45,633 | 38,692 | 2026-10-08 21:05 |
| C1855818 | DRV8874PWPR (DRV8874) | 4 | 8 | Extended | $1.0082 | $8.07 | 27,586 | 27,578 | 2026-10-08 21:06 |
| C701961 | LP5036RJVR (LP5036) | 2 | 4 | Extended | $1.2733 | $5.09 | 16,757 | 16,753 | 2026-10-08 21:06 |
| C967633 | LSM6DS3TR-C (LSM6DS3TR-C) | 1 | 2 | Extended | $1.5156 | $3.03 | 27,676 | 27,674 | 2026-10-08 21:06 |
| C516136 | HL-A-3528S7VC-S1-13HL (violet) | 24 | 52 | Extended | $0.0553 | $2.88 | 68,094 | 68,042 | 2026-10-08 21:05 |
| C41378174 | RP2354A (RP2354A) | 1 | 2 | Extended | $1.2765 | $2.55 | 15,998 | 15,996 | 2026-10-08 21:06 |
| C15850 | CL21A106KAYNNNE (10u 25V) | 10 | 30 | Basic | $0.0687 | $2.06 | 4,577,372 | 4,577,342 | 2026-10-08 21:04 |
| C530531 | GSPK2307P-8R1W (8R 1W) | 1 | 2 | Extended | $0.9009 | $1.80 | 4,897 | 4,895 | 2026-10-08 21:05 |
| C38732 | OPA2333AIDR (OPA2333) | 1 | 2 | Extended | $0.7529 | $1.51 | 19,024 | 19,022 | 2026-10-08 21:06 |
| C465729 | UCC27524DR (UCC27524) | 2 | 4 | Extended | $0.3610 | $1.44 | 32,059 | 32,055 | 2026-10-08 21:06 |
| C266123 | DRV5055A4QDBZR (DRV5055A4) | 1 | 2 | Extended | $0.6944 | $1.39 | 8,734 | 8,732 | 2026-10-08 21:06 |
| C2897409 | PM254-2-08-Z-8.5 (TREE) | 2 | 4 | Extended | $0.3121 | $1.25 | 23,423 | 23,419 | 2026-10-08 21:05 |
| C20625731 | ABM8-272-T3 (12MHz) | 1 | 2 | Extended | $0.6196 | $1.24 | 9,889 | 9,887 | 2026-10-08 21:06 |
| C3715882 | TMAG5273A2QDBVR (TMAG5273A2) | 1 | 2 | Extended | $0.5789 | $1.16 | 17,919 | 17,917 | 2026-10-08 21:06 |
| C97946 | GRM31C5C1H104JA01L (100n C0G) | 2 | 6 | Extended | $0.1849 | $1.11 | 72,248 | 72,242 | 2026-10-08 21:05 |
| C160389 | BM03B-SRSS-TB(LF)(SN) (SWD/UART) | 2 | 4 | Extended | $0.2744 | $1.10 | 31,676 | 31,672 | 2026-10-08 21:05 |
| C364577 | LTR-303ALS-01 (LTR-303ALS) | 1 | 2 | Extended | $0.5432 | $1.09 | 15,840 | 15,838 | 2026-10-08 21:06 |
| C2894988 | PZ254-2-08-W-8.5 (BASE/PERCH) | 2 | 4 | Extended | $0.2614 | $1.05 | 2,443 | 2,439 | 2026-10-08 21:05 |
| C46550472 | MA35V470M10X13 (470u 35V) | 1 | 2 | Extended | $0.4472 | $0.89 | 74,803 | 74,801 | 2026-10-08 21:04 |
| C45783 | CL21A226MAQNNNE (22u 25V) | 2 | 4 | Basic | $0.2202 | $0.88 | 3,796,756 | 3,796,752 | 2026-10-08 21:04 |
| C14663 | CC0603KRX7R9BB104 (100n) | 24 | 58 | Basic | $0.0140 | $0.81 | 59,162,400 | 59,162,342 | 2026-10-08 21:04 |
| C5645 | 74HC4051PW,118 (74HC4051) | 1 | 2 | Extended | $0.3136 | $0.63 | 3,503 | 3,501 | 2026-10-08 21:06 |
| C189961 | NS4150B (NS4150B) | 1 | 4 | Extended | $0.1527 | $0.61 | 142,491 | 142,487 | 2026-10-08 21:06 |
| C311983 | TPS54302DDCR (TPS54302) | 1 | 2 | Extended | $0.3002 | $0.60 | 72,915 | 72,913 | 2026-10-08 21:06 |
| C77069 | GRM21B5C1H223JA01L (22n C0G) | 1 | 6 | Extended | $0.0958 | $0.57 | 58,678 | 58,672 | 2026-10-08 21:05 |
| C5446 | XC6206P332MR-G (XC6206 3.3V) | 1 | 4 | Basic | $0.1427 | $0.57 | 428,954 | 428,950 | 2026-10-08 21:06 |
| C381116 | DC-005-5A-2.0 (12V DC) | 1 | 2 | Extended | $0.2612 | $0.52 | 29,629 | 29,627 | 2026-10-08 21:05 |
| C7835 | SN74LVC1G14DBVR (74LVC1G14) | 2 | 8 | Extended | $0.0648 | $0.52 | 309,740 | 309,732 | 2026-10-08 21:06 |
| C15849 | CL10A105KB8NNNC (1u) | 10 | 30 | Basic | $0.0156 | $0.47 | 9,022,053 | 9,022,023 | 2026-10-08 21:05 |
| C160472 | LTST-S270KFKT (orange) | 2 | 12 | Extended | $0.0379 | $0.45 | 5,949 | 5,937 | 2026-10-08 21:05 |
| C51933300 | GL0603PU01 (purple) | 18 | 42 | Extended | $0.0101 | $0.42 | 17,280 | 17,238 | 2026-10-08 21:05 |
| C720477 | TS-1088-AR02016 (BOOT/SPELL) | 2 | 8 | Basic | $0.0524 | $0.42 | 733,185 | 733,177 | 2026-10-08 21:05 |
| C910846 | BSMD2920-500-16V (5A PTC) | 1 | 2 | Extended | $0.2054 | $0.41 | 28,185 | 28,183 | 2026-10-08 21:05 |
| C165948 | TYPE-C-31-M-12 (USB-C) | 1 | 2 | Extended | $0.1858 | $0.37 | 412,069 | 412,067 | 2026-10-08 21:05 |
| C19702 | CL10A106KP8NNNC (10u) | 1 | 12 | Basic | $0.0305 | $0.37 | 11,326,735 | 11,326,723 | 2026-10-08 21:05 |
| C431540 | MSK12C02 (SOUND) | 1 | 6 | Extended | $0.0566 | $0.34 | 187,738 | 187,732 | 2026-10-08 21:06 |
| C8598 | B5819W SL (B5819W) | 2 | 12 | Basic | $0.0280 | $0.34 | 423,021 | 423,009 | 2026-10-08 21:05 |
| C516304 | HL-AF-5060S22OC-3-S1-THL (orange x3) | 3 | 10 | Extended | $0.0308 | $0.31 | 19,641 | 19,631 | 2026-10-08 21:05 |
| C167223 | FXL0630-100-M (10uH) | 1 | 3 | Extended | $0.0900 | $0.27 | 216,382 | 216,379 | 2026-10-08 21:05 |
| C23733 | CL05A475MP5NRNC (4.7u) | 3 | 16 | Basic | $0.0166 | $0.27 | 2,182,824 | 2,182,808 | 2026-10-08 21:04 |
| C57112 | 0603B103K500NT (10n) | 7 | 24 | Basic | $0.0108 | $0.26 | 6,386,910 | 6,386,886 | 2026-10-08 21:05 |
| C2841482 | AO4407A (AO4407A) | 1 | 2 | Extended | $0.1293 | $0.26 | 106,124 | 106,122 | 2026-10-08 21:05 |
| C19077569 | SMBJ15A (SMBJ15A) | 1 | 4 | Preferred | $0.0501 | $0.20 | 12,470 | 12,466 | 2026-10-08 21:05 |
| C173431 | BZT52C10 (BZT52C10) | 1 | 12 | Extended | $0.0166 | $0.20 | 279,014 | 279,002 | 2026-10-08 21:05 |
| C965800 | XL-1608UOC-06 (orange) | 8 | 28 | Extended | $0.0071 | $0.20 | 386,824 | 386,796 | 2026-10-08 21:05 |
| C21122 | CL10B223KB8NNNC (22n) | 6 | 22 | Basic | $0.0083 | $0.18 | 822,795 | 822,773 | 2026-10-08 21:05 |
| C1644 | CL10C150JB8NNNC (15p) | 2 | 14 | Basic | $0.0114 | $0.16 | 998,761 | 998,747 | 2026-10-08 21:05 |
| C1525 | CL05B104KO5NNNC (100n) | 12 | 34 | Basic | $0.0045 | $0.15 | 20,656,988 | 20,656,954 | 2026-10-08 21:05 |
| C52923 | CL05A105KA5NQNC (1u) | 2 | 14 | Basic | $0.0107 | $0.15 | 8,196,351 | 8,196,337 | 2026-10-08 21:04 |
| C2934295 | FRL1206FR500TS (0.5) | 2 | 14 | Extended | $0.0084 | $0.12 | 598,838 | 598,824 | 2026-10-08 21:05 |
| C25803 | 0603WAF1003T5E (100k) | 10 | 30 | Basic | $0.0031 | $0.09 | 21,356,368 | 21,356,338 | 2026-10-08 21:05 |
| C21190 | 0603WAF1001T5E (1k) | 8 | 26 | Basic | $0.0026 | $0.07 | 20,106,889 | 20,106,863 | 2026-10-08 21:05 |
| C31850 | 0603WAF2202T5E (22k) | 2 | 14 | Basic | $0.0041 | $0.06 | 3,619,499 | 3,619,485 | 2026-10-08 21:05 |
| C1548 | 0402CG150J500NT (15p) | 2 | 14 | Basic | $0.0038 | $0.05 | 1,378,479 | 1,378,465 | 2026-10-08 21:05 |
| C25804 | 0603WAF1002T5E (10k) | 8 | 26 | Basic | $0.0018 | $0.05 | 27,805,098 | 27,805,072 | 2026-10-08 21:05 |
| C23140 | 0603WAF330JT5E (33) | 4 | 18 | Basic | $0.0025 | $0.04 | 5,436,982 | 5,436,964 | 2026-10-08 21:05 |
| C11702 | 0402WGF1001TCE (1k) | 2 | 14 | Basic | $0.0031 | $0.04 | 6,902,360 | 6,902,346 | 2026-10-08 21:05 |
| C4190 | 0603WAF2201T5E (2.2k) | 6 | 22 | Basic | $0.0018 | $0.04 | 7,354,267 | 7,354,245 | 2026-10-08 21:05 |
| C23162 | 0603WAF4701T5E (4.7k) | 2 | 14 | Basic | $0.0028 | $0.04 | 21,510,801 | 21,510,787 | 2026-10-08 21:05 |
| C22978 | 0603WAF3301T5E (3.3k) | 2 | 14 | Basic | $0.0026 | $0.04 | 5,483,095 | 5,483,081 | 2026-10-08 21:05 |
| C25905 | 0402WGF5101TCE (5.1k) | 2 | 14 | Basic | $0.0024 | $0.03 | 5,758,561 | 5,758,547 | 2026-10-08 21:05 |
| C22808 | 0603WAF1500T5E (150) | 4 | 18 | Basic | $0.0017 | $0.03 | 739,466 | 739,448 | 2026-10-08 21:05 |
| C23186 | 0603WAF5101T5E (5.1k) | 3 | 16 | Basic | $0.0015 | $0.02 | 24,901,212 | 24,901,196 | 2026-10-08 21:05 |
| C23147 | 0603WAF3602T5E (36k) | 1 | 12 | Preferred | $0.0018 | $0.02 | 342,309 | 342,297 | 2026-10-08 21:05 |
| C25076 | 0402WGF1000TCE (100) | 4 | 18 | Basic | $0.0012 | $0.02 | 3,845,058 | 3,845,040 | 2026-10-08 21:05 |
| C25105 | 0402WGF330JTCE (33) | 1 | 12 | Basic | $0.0012 | $0.01 | 1,784,548 | 1,784,536 | 2026-10-08 21:05 |

"ordered" is what JLCPCB charges for: the placements on 2 panels plus its attrition (`lossNumber`) or minimum purchase, at the price break for that quantity.  A Preferred part is an Extended part JLCPCB keeps on its machines.

