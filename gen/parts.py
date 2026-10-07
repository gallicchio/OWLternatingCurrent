"""Every part on the panel, in one place.

The schematic takes symbols, footprints, values and LCSC codes from here; the
library (gen/library.py) is built from the symbols and footprints named here; the
BOM, the CPL and the checks read it.  A part's LCSC code must name exactly the
part described: the release compares each code's JLCPCB description with `match`
(every word must appear) before it writes anything (CLAUDE_PCB.md section 3: eight
codes typed from memory once named the wrong parts).

Fields:
  sym      symbol in the project library (LIB:...)
  fp       footprint in the project library
  fp_src   where gen/library.py gets the footprint: "stock:<KiCad lib>", "lcsc:<code>"
           (EasyEDA's land pattern via easyeda2kicad: JLCPCB's own drawing), "rpi"
           (Raspberry Pi's, from GPiBridge's extraction) or "gen" (gen/footprints.py)
  lcsc     LCSC/JLCPCB code, None for a part JLCPCB does not place (coils are copper)
  mpn      manufacturer part number
  value    what the schematic and silkscreen print
  match    words JLCPCB's description of `lcsc` must contain
  note     why this part (shown in the BOM)

Stock and prices were queried 2026-10-07 (research/jlc_parts_survey.md, and the
build's own queries, cached with their times in tools/jlc_cache.json).
"""

LIB = "OWL"


def P(sym, fp, fp_src, lcsc, mpn, value, match, note=""):
    return dict(sym=LIB + ":" + sym, fp=LIB + ":" + fp, fp_src=fp_src, lcsc=lcsc, mpn=mpn,
                value=value, match=match, note=note)


PARTS = {
    # --- chips -------------------------------------------------------------------------
    "RP2354A": P("RP2354A", "RP2350A_QFN-60_7x7mm_P0.4mm_RPi", "rpi", "C41378174", "RP2354A", "RP2354A",
                 ["RP2354A"], "RP2350 with 2 MB flash in the package; Raspberry Pi's layout, as on GPiBridge"),
    "LP5036": P("LP5036", "VQFN-46-1EP_5x6mm_P0.4mm_EP2.8x3.8mm_ThermalVias", "stock:Package_DFN_QFN", "C701961", "LP5036RJVR", "LP5036",
                ["LP5036"], "36 constant-current LED outputs, 12-bit PWM at 29 kHz: no visible flicker"),
    "DRV8874": P("DRV8874", "HTSSOP-16-1EP_4.4x5mm_P0.65mm_EP3.55x2.46mm_TI_PWP0016J", "gen", "C1855818", "DRV8874PWPR",
                 "DRV8874", ["DRV8874"], "12 V H-bridge, 6 A peak, current sense and limit built in; PWM to 100 kHz"),
    "UCC27524": P("UCC27524", "SOIC-8_3.9x4.9mm_P1.27mm", "stock:Package_SO", "C465729", "UCC27524DR", "UCC27524",
                  ["UCC27524"], "dual 5 A gate driver, 7 ns edges, used as one leg of a 5 V bridge at up to 330 kHz"),
    "AO4407A": P("Q_PMOS_SSSGDDDD", "SOIC-8_3.9x4.9mm_P1.27mm", "stock:Package_SO", "C2841482", "AO4407A", "AO4407A",
                 ["AO4407A"], "reverse-polarity switch on the 12 V input: 9.5 mOhm, so 4 A costs 0.15 W"),
    "BZT52C10": P("D_Zener", "D_SOD-123", "stock:Diode_SMD", "C173431", "BZT52C10", "BZT52C10",
                  ["BZT52C10"], "holds the AO4407A's gate within 10 V of its source"),
    "PTC5A": P("Polyfuse", "Fuse_2920_7451Metric", "stock:Fuse", "C910846", "BSMD2920-500-16V", "5A PTC",
               ["BSMD2920-500"], "resettable fuse: holds 5 A, trips at 10 A; a short never needs a new fuse"),
    "TPS54302": P("TPS54302", "SOT-23-6", "stock:Package_TO_SOT_SMD", "C311983", "TPS54302DDCR", "TPS54302",
                  ["TPS54302"], "12 V to 5 V, 3 A buck"),
    "XC6206": P("XC6206P332MR", "SOT-23", "stock:Package_TO_SOT_SMD", "C5446", "XC6206P332MR-G", "XC6206 3.3V",
                ["XC6206P332MR", "3.3V", "SOT-23"],
                "3.3 V LDO, 200 mA, stable with ceramic capacitors (an AMS1117 is not: it wants a 22 uF tantalum); "
                "Basic; the logic draws about 110 mA"),
    "NS4150B": P("NS4150B", "MSOP-8_3x3mm_P0.65mm", "stock:Package_SO", "C189961", "NS4150B", "NS4150B",
                 ["NS4150B"], "3 W class-D speaker amplifier, the theremin's voice"),
    "LSM6DS3": P("LSM6DS3TR_C", "Bosch_LGA-14_3x2.5mm_P0.5mm", "stock:Package_LGA", "C967633", "LSM6DS3TR-C",
                 "LSM6DS3TR-C", ["LSM6DS3TR-C"], "accelerometer + gyro: taps, tilt (the wisps roll downhill)"),
    "LTR303": P("LTR-303ALS-01", "Lite-On_LTR-303ALS-01", "stock:OptoDevice", "C364577", "LTR-303ALS-01",
                "LTR-303ALS", ["LTR-303ALS-01"], "ambient light: the owls wake at dusk"),
    "TMAG5273": P("TMAG5273", "SOT-23-6", "stock:Package_TO_SOT_SMD", "C3715882", "TMAG5273A2QDBVR", "TMAG5273A2",
                  ["TMAG5273A2"], "3-axis Hall sensor under the pendulum's swing: where is the bat?"),
    "DRV5055": P("DRV5055", "SOT-23", "stock:Package_TO_SOT_SMD", "C266123", "DRV5055A4QDBZR", "DRV5055A4",
                 ["DRV5055A4"], "linear Hall sensor at the levitation coil's centre, +-169 mT range"),
    "OPA2333": P("OPA2333", "SOIC-8_3.9x4.9mm_P1.27mm", "stock:Package_SO", "C38732", "OPA2333AIDR", "OPA2333",
                 ["OPA2333"], "zero-drift dual op-amp: x20.6 on the perch bridges' 0.5 R shunts (10 uV offset: "
                 "no dead zone at the firmware's low-duty sweep)"),
    "HC4051": P("74HC4051", "TSSOP-16_4.4x5mm_P0.65mm", "stock:Package_SO", "C5645", "74HC4051PW,118", "74HC4051",
                ["74HC4051"], "8:1 analog mux: the slow currents and rails into one ADC pin"),
    "LVC1G14": P("74LVC1G14", "SOT-23-5", "stock:Package_TO_SOT_SMD", "C7835", "SN74LVC1G14DBVR", "74LVC1G14",
                 ["SN74LVC1G14"], "Schmitt inverter: an RC oscillator whose C is a hand near an antenna (theremin)"),
    # --- clock, regulator parts, connectors, controls ---------------------------------------
    "Y12M": P("Crystal_GND24", "Crystal_SMD_3225-4Pin_3.2x2.5mm", "stock:Crystal", "C20625731", "ABM8-272-T3",
              "12MHz", ["ABM8-272-T3"], "the crystal Raspberry Pi specifies for the RP2350"),
    "L3U3": P("L", "L_Abracon_AOTA-B201610_RPi", "rpi", "C42411119", "AOTA-B201610S3R3-101-T", "3.3uH",
              ["AOTA-B201610S3R3-101-T"], "polarity-marked inductor for the RP2350's core regulator"),
    "L10U": P("L", "L_Changjiang_FXL0630", "stock:Inductor_SMD", "C167223", "FXL0630-100-M", "10uH",
              ["FXL0630-100-M"], "the buck's inductor: 10 uH, 4.5 A saturation"),
    "USBC": P("USB_C_Receptacle_USB2.0_16P", "USB_C_Receptacle_HRO_TYPE-C-31-M-12", "stock:Connector_USB",
              "C165948", "TYPE-C-31-M-12", "USB-C", ["TYPE-C-31-M-12"], "built right on the Lorenz board; datum known"),
    "JACK": P("Barrel_Jack_Switch", "BarrelJack_XKB_DC-005-5A-2.0_Horizontal", "gen", "C381116", "DC-005-5A-2.0", "12V DC",
              ["DC-005"], "5.5 x 2.1 mm barrel jack, 5 A, centre positive"),
    "JSTSH3": P("Conn_01x03", "JST_SH_BM03B-SRSS-TB_1x03-1MP_P1.00mm_Vertical", "stock:Connector_JST", "C160389",
                "BM03B-SRSS-TB(LF)(SN)", "SH 1x3", ["BM03B-SRSS-TB"], "Raspberry Pi debug connector"),
    "BUTTON": P("SW_Push", "SW_SPST_TS-1088-xR020", "stock:Button_Switch_SMD", "C720477", "TS-1088-AR02016", "button",
                ["TS-1088-AR02016"], "Basic part"),
    "SLIDE": P("SW_SPDT", "SW_SPDT_Shouhan_MSK12C02", "stock:Button_Switch_SMD", "C431540", "MSK12C02", "SOUND",
               ["MSK12C02"], "the sound switch: OFF holds the amplifier in shutdown, whatever the firmware does"),
    "SPEAKER": P("Speaker", "Speaker_GSPK2307P_D23mm_P10mm", "gen", "C530531", "GSPK2307P-8R1W",
                 "8R 1W", ["GSPK2307P"], "23 mm speaker with PCB pins, so JLCPCB solders it"),
    "SOCKET2x8": P("Conn_02x08_Odd_Even", "PinSocket_2x08_P2.54mm_Vertical", "stock:Connector_PinSocket_2.54mm", "C2897409",
                   "PM254-2-08-Z-8.5", "2x8 socket", ["PM254-2-08-Z"], "the tree (and the perch) plug in here"),
    "HEADER2x8RA": P("Conn_02x08_Odd_Even", "PinHeader_2x08_P2.54mm_Horizontal", "stock:Connector_PinHeader_2.54mm",
                     "C2894988", "PZ254-2-08-W-8.5", "2x8 right angle", ["PZ254-2-08-W"],
                     "the tree's plugs: pins point down into the base, up into the perch"),
    # --- power protection and bulk ----------------------------------------------------------
    "SMBJ15A": P("D_Zener", "D_SMB", "stock:Diode_SMD", "C19077569", "SMBJ15A", "SMBJ15A",
                 ["SMBJ15A"], "clamps hot-plug ringing on the 12 V input (Preferred part: no setup fee)"),
    "SS34": P("D_Schottky", "D_SMA", "stock:Diode_SMD", "C8678", "SS34", "SS34", ["SS34"], "Basic"),
    "B5819W": P("D_Schottky", "D_SOD-123", "stock:Diode_SMD", "C8598", "B5819W SL", "B5819W", ["B5819W"],
                "USB VBUS into the 5 V rail when there is no 12 V; Basic"),
    "C470U": P("C_Polarized", "CP_Elec_10x12.6", "stock:Capacitor_SMD", "C46550472",
               "MA35V470M10X13", "470u 35V", ["470uF", "35V"], "bulk on +12V: its ESR damps hot-plug ringing"),
    # --- LEDs (gen/leds.py says which goes where) -------------------------------------------
    "LED_ORANGE": P("LED", "LED_0603_1608Metric", "stock:LED_SMD", "C965800", "XL-1608UOC-06", "orange",
                    ["XL-1608UOC-06"], "pumpkin orange, 600-610 nm"),
    "LED_AMBER5050": P("LED_3die", "LED_RGB_5050-6", "stock:LED_SMD", "C516304", "HL-AF-5060S22OC-3-S1-THL",
                       "orange x3", ["HL-AF-5060S22OC"], "three orange dice in a 5050: the pumpkins' faces"),
    "LED_VIOLET": P("LED", "LED_Everlight-SMD3528_3.5x2.8mm_67-21ST", "stock:LED_SMD", "C516136",
                    "HL-A-3528S7VC-S1-13HL", "violet", ["HL-A-3528S7VC"], "400-410 nm: stars; charges glow, makes things fluoresce"),
    "LED_PURPLE": P("LED", "LED_0603_1608Metric", "stock:LED_SMD", "C51933300", "GL0603PU01", "purple",
                    ["GL0603PU01"], "phosphor purple you can see (the eye barely sees 405 nm)"),
    "LED_SIDE_ORANGE": P("LED", "LED_LiteOn_LTST-S270_SideView", "gen", "C160472", "LTST-S270KFKT", "orange side",
                         ["LTST-S270KFKT"], "side-view, so the floating bat's eyes shine forward"),
    # --- coils: copper, not parts (gen/footprints.py draws them) ------------------------------
    "COIL_PEND": dict(sym=LIB + ":Coil", fp=LIB + ":NetTie-2_SMD_Pad2.0mm", fp_src="stock:NetTie", lcsc=None,
                      mpn="PCB coil", value="31uH", match=[], note="4-layer spiral, copper"),
    "COIL_LEV": dict(sym=LIB + ":Coil", fp=LIB + ":NetTie-2_SMD_Pad2.0mm", fp_src="stock:NetTie", lcsc=None,
                     mpn="PCB coil", value="29uH", match=[], note="4-layer spiral, copper; the Hall sensor sits in its centre"),
    "COIL_PERCH": dict(sym=LIB + ":Coil", fp=LIB + ":NetTie-2_SMD_Pad2.0mm", fp_src="stock:NetTie", lcsc=None,
                       mpn="PCB coil", value="28uH", match=[], note="4-layer spiral, copper"),
    "COIL_TOKEN": dict(sym=LIB + ":Coil", fp=LIB + ":NetTie-2_SMD_Pad0.5mm", fp_src="stock:NetTie", lcsc=None,
                       mpn="PCB coil", value="11.5uH", match=[], note="4-layer spiral, copper"),
    "COIL_BAT": dict(sym=LIB + ":Coil", fp=LIB + ":NetTie-2_SMD_Pad0.5mm", fp_src="stock:NetTie", lcsc=None,
                     mpn="PCB coil", value="38uH", match=[], note="4-layer fine-pitch spiral, copper"),
    # --- bare pads, holes, flags (not placed by JLCPCB) ---------------------------------------
    "ANTENNA": dict(sym=LIB + ":Antenna", fp=LIB + ":TestPoint_Pad_D1.5mm", fp_src="stock:TestPoint", lcsc=None,
                    mpn="", value="antenna", match=[], note="the pad where a gold copper shape (the moon, the ghost) joins its oscillator"),
    "TP": dict(sym=LIB + ":TestPoint", fp=LIB + ":TestPoint_Pad_D1.5mm", fp_src="stock:TestPoint", lcsc=None,
               mpn="", value="", match=[], note="bare pad"),
    "FOOTHOLE": dict(sym=LIB + ":MountingHole", fp=LIB + ":MountingHole_3.2mm_M3", fp_src="stock:MountingHole",
                     lcsc=None, mpn="", value="", match=[], note="a printed foot snaps in here"),
    "PWR_FLAG": dict(sym=LIB + ":PWR_FLAG", fp=LIB + ":", fp_src=None, lcsc=None, mpn="", value="PWR_FLAG",
                     match=[], note="tells ERC where a rail is driven from"),
}


def passive(kind, value, size, lcsc, mpn, match, note="", sym=None):
    sym = sym or {"R": "R", "C": "C"}[kind]
    fp, src = {("R", "0603"): ("R_0603_1608Metric", "stock:Resistor_SMD"),
               ("C", "0603"): ("C_0603_1608Metric", "stock:Capacitor_SMD"),
               ("C", "0805"): ("C_0805_2012Metric", "stock:Capacitor_SMD"),
               ("C", "1206"): ("C_1206_3216Metric", "stock:Capacitor_SMD"),
               ("R", "1206"): ("R_1206_3216Metric", "stock:Resistor_SMD"),
               ("C", "0402RPi"): ("C_0402_RPi", "rpi"), ("C", "0402RPiWide"): ("C_0402_RPi_wide", "rpi"),
               ("R", "0402RPi"): ("R_0402_RPi", "rpi")}[(kind, size)]
    return P(sym, fp, src, lcsc, mpn, value, match, note)


PARTS.update({
    # capacitors (Basic unless said)
    "C100N": passive("C", "100n", "0603", "C14663", "CC0603KRX7R9BB104", ["100nF", "0603"]),
    "C10N": passive("C", "10n", "0603", "C57112", "0603B103K500NT", ["10nF", "0603"]),
    "C22N": passive("C", "22n", "0603", "C21122", "CL10B223KB8NNNC", ["22nF", "50V", "0603"],
                    "the DRV8874's charge-pump flying capacitor: 22 nF, VM-rated (datasheet)"),
    "C2N2": passive("C", "2.2n", "0603", "C1604", "0603B222K500NT", ["2.2nF", "0603"]),
    "C15P": passive("C", "15p", "0603", "C1644", "CL10C150JB8NNNC", ["15pF", "C0G", "0603"]),
    "C1U": passive("C", "1u", "0603", "C15849", "CL10A105KB8NNNC", ["1uF", "0603"]),
    "C4U7": passive("C", "4.7u", "0603", "C19666", "CL10A475KO8NNNC", ["4.7uF", "0603"]),
    "C10U": passive("C", "10u 25V", "0805", "C15850", "CL21A106KAYNNNE", ["10uF", "25V", "0805"]),
    "C22U": passive("C", "22u 25V", "0805", "C45783", "CL21A226MAQNNNE", ["22uF", "25V", "0805"]),
    # resonant tanks: C0G (Extended), one value per resonance
    "C100N_C0G": passive("C", "100n C0G", "1206", "C97946", "GRM31C5C1H104JA01L", ["100nF", "C0G", "1206"],
                         "owl token's tank: 148 kHz with its 11.5 uH coil"),
    "C22N_C0G": passive("C", "22n C0G", "0805", "C77069", "GRM21B5C1H223JA01L", ["22nF", "C0G", "0805"],
                        "cat token's tank: 316 kHz"),
    "C68N_C0G": passive("C", "68n C0G", "1206", "C77084", "GRM31C5C1H683JA01L", ["68nF", "C0G", "1206"],
                        "the bat's tank: 90 kHz"),
    # Raspberry Pi's own footprints for the core regulator's parts (layout copied exactly)
    "C4U7_RPI_WIDE": passive("C", "4.7u", "0402RPiWide", "C23733", "CL05A475MP5NRNC", ["4.7uF", "0402"]),
    "C4U7_RPI": passive("C", "4.7u", "0402RPi", "C23733", "CL05A475MP5NRNC", ["4.7uF", "0402"]),
    "R33_RPI": passive("R", "33", "0402RPi", "C25105", "0402WGF330JTCE", ["33Ω", "0402"]),
    # resistors (Basic unless said)
    "R0": passive("R", "0", "0603", "C21189", "0603WAF0000T5E", ["0Ω", "0603"]),
    "R100": passive("R", "100", "0603", "C22775", "0603WAF1000T5E", ["100Ω", "0603"],
                    "debug connectors: 100 R in each line, as on GPiBridge"),
    "R27": passive("R", "27", "0603", "C25190", "0603WAF270JT5E", ["27Ω", "0603"], "USB series (Preferred)"),
    "R33": passive("R", "33", "0603", "C23140", "0603WAF330JT5E", ["33Ω", "0603"]),
    "R150": passive("R", "150", "0603", "C22808", "0603WAF1500T5E", ["150Ω", "0603"]),
    "R330": passive("R", "330", "0603", "C23138", "0603WAF3300T5E", ["330Ω", "0603"]),
    "R1K": passive("R", "1k", "0603", "C21190", "0603WAF1001T5E", ["1kΩ", "0603"]),
    "R2K2": passive("R", "2.2k", "0603", "C4190", "0603WAF2201T5E", ["2.2kΩ", "0603"]),
    "R3K3": passive("R", "3.3k", "0603", "C22978", "0603WAF3301T5E", ["3.3kΩ", "0603"],
                    "LP5036 IREF: 105 x 0.7 V / 3.3k = 22 mA per output at most, under every LED's 30 mA"),
    "R4K7": passive("R", "4.7k", "0603", "C23162", "0603WAF4701T5E", ["4.7kΩ", "0603"]),
    "R5K1": passive("R", "5.1k", "0603", "C23186", "0603WAF5101T5E", ["5.1kΩ", "0603"]),
    "R10K": passive("R", "10k", "0603", "C25804", "0603WAF1002T5E", ["10kΩ", "0603"]),
    "R36K": passive("R", "36k", "0603", "C23147", "0603WAF3602T5E", ["36kΩ", "0603"],
                    "buck feedback with 5.1k: 0.596 V x (1 + 36/5.1) = 4.80 V (Preferred: no setup fee); "
                    "4.8 V keeps the NS4150B well under its 5.25 V absolute maximum"),
    "R22K": passive("R", "22k", "0603", "C31850", "0603WAF2202T5E", ["22kΩ", "0603"]),
    "R100K": passive("R", "100k", "0603", "C25803", "0603WAF1003T5E", ["100kΩ", "0603"]),
    "R1M": passive("R", "1M", "0603", "C22935", "0603WAF1004T5E", ["1MΩ", "0603"]),
    "R0R5": passive("R", "0.5", "1206", "C2934295", "FRL1206FR500TS", ["500mΩ", "1206"],
                    "perch current sense: 0.24 A max makes 0.12 V"),
})

# The spiral of each coil (gen/coils.py), keyed like the coil parts above.  Radii and
# pitch in mm; the physics behind each is in sim/physics/.
COILS = {
    "COIL_PEND": dict(r_out=15.0, r_in=3.0, turns=12, width=0.6, layers=4),
    "COIL_LEV": dict(r_out=15.0, r_in=4.0, turns=11, width=0.6, layers=4),
    "COIL_PERCH": dict(r_out=15.0, r_in=5.0, turns=10, width=0.6, layers=4),
    "COIL_TOKEN": dict(r_out=11.5, r_in=4.5, turns=7, width=0.6, layers=4),
    "COIL_BAT": dict(r_out=11.0, r_in=7.0, turns=10, width=0.2, layers=4),
}
