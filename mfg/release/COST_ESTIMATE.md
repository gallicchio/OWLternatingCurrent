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
| parts | 244 placements a panel on 67 BOM lines, for 2 panels with JLCPCB's attrition, at the price break for that quantity | $51.73 |
| **total before shipping and duty** | | **$348.37** |
| an assembled panel | the total over 2 | $174.18 |

The range on the bare panels moves the total from $282.64 to $414.09.  US duty, collected by JLCPCB under DDP at 35 % of the PCBs and the assembly (their tariff FAQ, 2026-09-09), adds about $121.93; shipping (UPS Express Saver DDP to California) is shown at checkout.

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
- **C1855818 DRV8874PWPR** costs $8.06 for the order (8 x $1.01)
- **C701961 LP5036RJVR** costs $5.09 for the order (4 x $1.27)
- **C967633 LSM6DS3TR-C** costs $3.03 for the order (2 x $1.52)
- **C516136 HL-A-3528S7VC-S1-13HL** costs $2.88 for the order (52 x $0.06)
- **C41378174 RP2354A** costs $2.55 for the order (2 x $1.28)
- Not in the total: baking the moisture-sensitive parts before assembly (JLCPCB recommends it for MSL 3 and up, as the LGA-14 accelerometer is; about $7.50), shipping, and duty

## Parts (67 BOM lines)

| LCSC | part | per panel | ordered | library | unit | line | stock | left after | asked |
|---|---|--:|--:|---|--:|--:|--:|--:|---|
| C1855818 | DRV8874PWPR (DRV8874) | 4 | 8 | Extended | $1.0080 | $8.06 | 28,928 | 28,920 | 2026-10-07 11:19 |
| C701961 | LP5036RJVR (LP5036) | 2 | 4 | Extended | $1.2729 | $5.09 | 16,987 | 16,983 | 2026-10-07 11:18 |
| C967633 | LSM6DS3TR-C (LSM6DS3TR-C) | 1 | 2 | Extended | $1.5152 | $3.03 | 29,432 | 29,430 | 2026-10-07 11:21 |
| C516136 | HL-A-3528S7VC-S1-13HL (violet) | 24 | 52 | Extended | $0.0553 | $2.88 | 68,094 | 68,042 | 2026-10-07 11:18 |
| C41378174 | RP2354A (RP2354A) | 1 | 2 | Extended | $1.2762 | $2.55 | 16,231 | 16,229 | 2026-10-07 11:19 |
| C15850 | CL21A106KAYNNNE (10u 25V) | 10 | 30 | Basic | $0.0651 | $1.95 | 4,801,207 | 4,801,177 | 2026-10-07 13:12 |
| C530531 | GSPK2307P-8R1W (8R 1W) | 1 | 2 | Extended | $0.9007 | $1.80 | 5,014 | 5,012 | 2026-10-07 14:37 |
| C38732 | OPA2333AIDR (OPA2333) | 1 | 2 | Extended | $0.7527 | $1.51 | 19,075 | 19,073 | 2026-10-07 14:37 |
| C465729 | UCC27524DR (UCC27524) | 2 | 4 | Extended | $0.3609 | $1.44 | 61,699 | 61,695 | 2026-10-07 14:37 |
| C266123 | DRV5055A4QDBZR (DRV5055A4) | 1 | 2 | Extended | $0.6942 | $1.39 | 9,334 | 9,332 | 2026-10-07 11:21 |
| C2897409 | PM254-2-08-Z-8.5 (TREE) | 2 | 4 | Extended | $0.3120 | $1.25 | 23,440 | 23,436 | 2026-10-07 13:59 |
| C20625731 | ABM8-272-T3 (12MHz) | 1 | 2 | Extended | $0.6194 | $1.24 | 10,462 | 10,460 | 2026-10-07 11:19 |
| C3715882 | TMAG5273A2QDBVR (TMAG5273A2) | 1 | 2 | Extended | $0.5788 | $1.16 | 18,024 | 18,022 | 2026-10-07 11:21 |
| C97946 | GRM31C5C1H104JA01L (100n C0G) | 2 | 6 | Extended | $0.1849 | $1.11 | 84,312 | 84,306 | 2026-10-07 11:22 |
| C160389 | BM03B-SRSS-TB(LF)(SN) (SWD/UART) | 2 | 4 | Extended | $0.2743 | $1.10 | 32,191 | 32,187 | 2026-10-07 14:36 |
| C364577 | LTR-303ALS-01 (LTR-303ALS) | 1 | 2 | Extended | $0.5430 | $1.09 | 15,880 | 15,878 | 2026-10-07 11:21 |
| C2894988 | PZ254-2-08-W-8.5 (BASE/PERCH) | 2 | 4 | Extended | $0.2613 | $1.05 | 2,443 | 2,439 | 2026-10-07 13:59 |
| C46550472 | MA35V470M10X13 (470u 35V) | 1 | 2 | Extended | $0.4471 | $0.89 | 74,832 | 74,830 | 2026-10-07 11:20 |
| C45783 | CL21A226MAQNNNE (22u 25V) | 2 | 4 | Basic | $0.2202 | $0.88 | 3,924,702 | 3,924,698 | 2026-10-07 14:37 |
| C14663 | CC0603KRX7R9BB104 (100n) | 24 | 58 | Basic | $0.0123 | $0.71 | 59,907,749 | 59,907,691 | 2026-10-07 14:36 |
| C5645 | 74HC4051PW,118 (74HC4051) | 1 | 2 | Extended | $0.3135 | $0.63 | 20,088 | 20,086 | 2026-10-07 14:37 |
| C189961 | NS4150B (NS4150B) | 1 | 4 | Extended | $0.1527 | $0.61 | 144,374 | 144,370 | 2026-10-07 14:36 |
| C311983 | TPS54302DDCR (TPS54302) | 1 | 2 | Extended | $0.3001 | $0.60 | 78,316 | 78,314 | 2026-10-07 11:21 |
| C77069 | GRM21B5C1H223JA01L (22n C0G) | 1 | 6 | Extended | $0.0958 | $0.57 | 63,091 | 63,085 | 2026-10-07 14:37 |
| C5446 | XC6206P332MR-G (XC6206 3.3V) | 1 | 4 | Basic | $0.1426 | $0.57 | 461,428 | 461,424 | 2026-10-07 13:12 |
| C42411119 | AOTA-B201610S3R3-101-T (3.3uH) | 1 | 2 | Extended | $0.2829 | $0.57 | 667 | 665 | 2026-10-07 11:19 |
| C381116 | DC-005-5A-2.0 (12V DC) | 1 | 2 | Extended | $0.2611 | $0.52 | 30,504 | 30,502 | 2026-10-07 11:20 |
| C7835 | SN74LVC1G14DBVR (74LVC1G14) | 2 | 8 | Extended | $0.0648 | $0.52 | 312,113 | 312,105 | 2026-10-07 14:28 |
| C160472 | LTST-S270KFKT (orange) | 2 | 12 | Extended | $0.0379 | $0.45 | 5,962 | 5,950 | 2026-10-07 14:36 |
| C15849 | CL10A105KB8NNNC (1u) | 10 | 30 | Basic | $0.0144 | $0.43 | 6,974,190 | 6,974,160 | 2026-10-07 13:12 |
| C51933300 | GL0603PU01 (purple) | 18 | 42 | Extended | $0.0100 | $0.42 | 18,511 | 18,469 | 2026-10-07 11:18 |
| C720477 | TS-1088-AR02016 (BOOT/SPELL) | 2 | 8 | Basic | $0.0522 | $0.42 | 762,952 | 762,944 | 2026-10-07 14:37 |
| C910846 | BSMD2920-500-16V (5A PTC) | 1 | 2 | Extended | $0.2054 | $0.41 | 28,193 | 28,191 | 2026-10-07 14:37 |
| C19702 | CL10A106KP8NNNC (10u) | 1 | 12 | Basic | $0.0319 | $0.38 | 9,800,763 | 9,800,751 | 2026-10-07 14:44 |
| C165948 | TYPE-C-31-M-12 (USB-C) | 1 | 2 | Extended | $0.1857 | $0.37 | 417,782 | 417,780 | 2026-10-07 11:22 |
| C431540 | MSK12C02 (SOUND) | 1 | 6 | Extended | $0.0566 | $0.34 | 190,728 | 190,722 | 2026-10-07 14:37 |
| C8598 | B5819W SL (B5819W) | 2 | 12 | Basic | $0.0280 | $0.34 | 453,537 | 453,525 | 2026-10-07 11:22 |
| C516304 | HL-AF-5060S22OC-3-S1-THL (orange x3) | 3 | 10 | Extended | $0.0308 | $0.31 | 19,795 | 19,785 | 2026-10-07 11:17 |
| C167223 | FXL0630-100-M (10uH) | 1 | 3 | Extended | $0.0899 | $0.27 | 221,953 | 221,950 | 2026-10-07 11:21 |
| C23733 | CL05A475MP5NRNC (4.7u) | 3 | 16 | Basic | $0.0166 | $0.27 | 2,343,331 | 2,343,315 | 2026-10-07 14:37 |
| C57112 | 0603B103K500NT (10n) | 7 | 24 | Basic | $0.0108 | $0.26 | 6,560,204 | 6,560,180 | 2026-10-07 14:37 |
| C2841482 | AO4407A (AO4407A) | 1 | 2 | Extended | $0.1293 | $0.26 | 106,457 | 106,455 | 2026-10-07 11:20 |
| C19077569 | SMBJ15A (SMBJ15A) | 1 | 4 | Preferred | $0.0501 | $0.20 | 7,969 | 7,965 | 2026-10-07 11:20 |
| C173431 | BZT52C10 (BZT52C10) | 1 | 12 | Extended | $0.0166 | $0.20 | 279,894 | 279,882 | 2026-10-07 14:36 |
| C965800 | XL-1608UOC-06 (orange) | 8 | 28 | Extended | $0.0071 | $0.20 | 398,998 | 398,970 | 2026-10-07 11:17 |
| C21122 | CL10B223KB8NNNC (22n) | 6 | 22 | Basic | $0.0083 | $0.18 | 857,306 | 857,284 | 2026-10-07 13:12 |
| C1644 | CL10C150JB8NNNC (15p) | 2 | 14 | Basic | $0.0113 | $0.16 | 1,018,758 | 1,018,744 | 2026-10-07 14:36 |
| C1525 | CL05B104KO5NNNC (100n) | 12 | 34 | Basic | $0.0045 | $0.15 | 22,191,896 | 22,191,862 | 2026-10-07 14:44 |
| C52923 | CL05A105KA5NQNC (1u) | 2 | 14 | Basic | $0.0107 | $0.15 | 8,386,229 | 8,386,215 | 2026-10-07 14:44 |
| C2934295 | FRL1206FR500TS (0.5) | 2 | 14 | Extended | $0.0084 | $0.12 | 594,593 | 594,579 | 2026-10-07 14:37 |
| C25803 | 0603WAF1003T5E (100k) | 10 | 30 | Basic | $0.0031 | $0.09 | 21,878,157 | 21,878,127 | 2026-10-07 13:12 |
| C21190 | 0603WAF1001T5E (1k) | 8 | 26 | Basic | $0.0026 | $0.07 | 21,131,901 | 21,131,875 | 2026-10-07 14:36 |
| C31850 | 0603WAF2202T5E (22k) | 2 | 14 | Basic | $0.0041 | $0.06 | 3,666,920 | 3,666,906 | 2026-10-07 14:37 |
| C1548 | 0402CG150J500NT (15p) | 2 | 14 | Basic | $0.0038 | $0.05 | 1,410,519 | 1,410,505 | 2026-10-07 14:44 |
| C25804 | 0603WAF1002T5E (10k) | 8 | 26 | Basic | $0.0018 | $0.05 | 29,335,219 | 29,335,193 | 2026-10-07 13:12 |
| C23140 | 0603WAF330JT5E (33) | 4 | 18 | Basic | $0.0025 | $0.04 | 5,529,008 | 5,528,990 | 2026-10-07 14:37 |
| C4190 | 0603WAF2201T5E (2.2k) | 6 | 22 | Basic | $0.0018 | $0.04 | 7,448,395 | 7,448,373 | 2026-10-07 13:12 |
| C23162 | 0603WAF4701T5E (4.7k) | 2 | 14 | Basic | $0.0028 | $0.04 | 22,075,440 | 22,075,426 | 2026-10-07 14:37 |
| C22978 | 0603WAF3301T5E (3.3k) | 2 | 14 | Basic | $0.0026 | $0.04 | 5,608,984 | 5,608,970 | 2026-10-07 13:12 |
| C25905 | 0402WGF5101TCE (5.1k) | 2 | 14 | Basic | $0.0024 | $0.03 | 5,918,534 | 5,918,520 | 2026-10-07 14:44 |
| C22808 | 0603WAF1500T5E (150) | 4 | 18 | Basic | $0.0017 | $0.03 | 849,756 | 849,738 | 2026-10-07 14:36 |
| C25100 | 0402WGF270JTCE (27) | 2 | 16 | Extended | $0.0019 | $0.03 | 52,169 | 52,153 | 2026-10-07 14:44 |
| C11702 | 0402WGF1001TCE (1k) | 2 | 14 | Basic | $0.0018 | $0.03 | 7,468,163 | 7,468,149 | 2026-10-07 14:45 |
| C23186 | 0603WAF5101T5E (5.1k) | 3 | 16 | Basic | $0.0015 | $0.02 | 25,160,743 | 25,160,727 | 2026-10-07 13:12 |
| C23147 | 0603WAF3602T5E (36k) | 1 | 12 | Preferred | $0.0018 | $0.02 | 343,749 | 343,737 | 2026-10-07 13:28 |
| C25076 | 0402WGF1000TCE (100) | 4 | 18 | Basic | $0.0012 | $0.02 | 4,017,859 | 4,017,841 | 2026-10-07 14:45 |
| C25105 | 0402WGF330JTCE (33) | 1 | 12 | Basic | $0.0012 | $0.01 | 1,920,787 | 1,920,775 | 2026-10-07 14:37 |

"ordered" is what JLCPCB charges for: the placements on 2 panels plus its attrition (`lossNumber`) or minimum purchase, at the price break for that quantity.  A Preferred part is an Extended part JLCPCB keeps on its machines.

