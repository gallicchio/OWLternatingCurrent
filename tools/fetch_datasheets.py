#!/usr/bin/env python3
"""Fetch every datasheet and drawing the design was checked against into
datasheets/ (which git ignores: they are copyrighted), with a pdftotext copy
of each in datasheets/txt/ for searching.

    python3 tools/fetch_datasheets.py          fetch what is missing
    python3 tools/fetch_datasheets.py --list   print the table, fetch nothing

The table below is the record of where each one came from.  Parts stocked by
JLCPCB are fetched through JLCPCB's file endpoint (keyed by the LCSC code),
because LCSC's own links refuse scripted downloads.
"""
import os, re, subprocess, sys, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "datasheets")
sys.path.insert(0, HERE)

UA = "Mozilla/5.0 (X11; Linux x86_64) GPiBridge-datasheets/1.0"

# (file name, source: a URL or an LCSC code, what it is)
SHEETS = [
    ("rp2350-datasheet.pdf", "https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf",
     "RP2350/RP2354 datasheet: QFN-60 pin table, GPIO electrical limits, bootrom, PIO"),
    ("hardware-design-with-rp2350.pdf", "https://datasheets.raspberrypi.com/rp2350/hardware-design-with-rp2350.pdf",
     "Raspberry Pi's minimal design: regulator layout, crystal, decoupling"),
    ("pico-2-datasheet.pdf", "https://datasheets.raspberrypi.com/pico/pico-2-datasheet.pdf",
     "Pico 2: the reference layout of the RP2350 regulator"),
    ("debug-connector-specification.pdf", "https://datasheets.raspberrypi.com/debug/debug-connector-specification.pdf",
     "Raspberry Pi 3-pin JST-SH debug connector"),
    ("sn75160b.pdf", "https://www.ti.com/lit/ds/symlink/sn75160b.pdf", "GPIB data transceiver"),
    ("sn75161b.pdf", "https://www.ti.com/lit/ds/symlink/sn75161b.pdf", "GPIB control transceiver"),
    ("PrologixGpibUsbManual-6.0.pdf", "https://prologix.biz/downloads/PrologixGpibUsbManual-6.0.pdf",
     "Prologix GPIB-USB manual: the '++' command set GPiBridge implements"),
    ("norcomp_111-024-113L001.pdf", "https://static.chipdip.ru/lib/343/DOC031343371.pdf",
     "NorComp 0.085 in ribbon male, DIP solder: the IEEE-488 plug's drawing"),
    ("lcom_CIB24BA.pdf", "https://www.farnell.com/datasheets/1445331.pdf",
     "L-com IEEE-488 bulkhead adapter: hood size of a male IEEE-488 connector"),
    ("XC6206P332MR_C5446.pdf", "C5446", "3.3 V LDO"),
    ("AO3401A_C15127.pdf", "C15127", "P-MOSFET, bus power switch"),
    ("2N7002_C8545.pdf", "C8545", "N-MOSFET, gate driver for the switch"),
    ("ABM8-272-T3_C20625731.pdf", "C20625731", "12 MHz crystal"),
    ("AOTA-B201610S3R3-101-T_C42411119.pdf", "C42411119", "3.3 uH polarity-marked inductor"),
    ("TYPE-C-31-M-12_C165948.pdf", "C165948", "USB-C receptacle"),
    ("BM03B-SRSS-TB_C160389.pdf", "C160389", "JST SH 3-pin, top entry: the debug connectors"),
    ("TS-1088-AR02016_C720477.pdf", "C720477", "BOOT button"),
    ("KT-0805G_C2297.pdf", "C2297", "green LED"),
    ("KT-0805Y_C2296.pdf", "C2296", "yellow LED"),
    ("NCD0805R1_C84256.pdf", "C84256", "red LED"),
    ("4D03WGJ0471T5E_C25510.pdf", "C25510", "470 R x 4 array"),
    ("4D03WGJ0103T5E_C29718.pdf", "C29718", "10 k x 4 array"),
]


def fetch_lcsc(code, path):
    import jlc_api
    part, _ = jlc_api.by_code(code)
    if part is None:
        return "not found at JLCPCB"
    urls = []
    if part.get("dataManualFileAccessId"):
        urls.append("https://jlcpcb.com/api/file/downloadByFileSystemAccessId/%s" % part["dataManualFileAccessId"])
    if part.get("dataManualUrl"):
        urls.append(part["dataManualUrl"])
    return fetch_urls(urls, path)


def fetch_urls(urls, path):
    err = "no URL"
    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": UA, "Accept": "*/*", "Referer": "https://jlcpcb.com/"})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read()
            if data[:4] == b"%PDF":
                open(path, "wb").write(data)
                return None
            err = "not a PDF from %s" % u[:60]
        except Exception as e:
            err = "%s: %s" % (u[:60], e)
    return err


def main():
    if "--list" in sys.argv:
        for name, src, what in SHEETS:
            print("%-40s %-12s %s" % (name, src if not src.startswith("http") else "url", what))
        return 0
    os.makedirs(os.path.join(OUT, "txt"), exist_ok=True)
    bad = 0
    for name, src, what in SHEETS:
        path = os.path.join(OUT, name)
        if not (os.path.exists(path) and os.path.getsize(path) > 5000):
            err = fetch_urls([src], path) if src.startswith("http") else fetch_lcsc(src, path)
            print("%-40s %s" % (name, "fetched" if err is None else "FAILED: " + err))
            bad += err is not None
        txt = os.path.join(OUT, "txt", re.sub(r"\.pdf$", ".txt", name))
        if os.path.exists(path) and not os.path.exists(txt):
            subprocess.run(["pdftotext", "-layout", path, txt], capture_output=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
