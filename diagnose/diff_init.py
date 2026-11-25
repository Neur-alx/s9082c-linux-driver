#!/usr/bin/env python3
"""
Phase 2b (offline Host): Diff Port-Kprobe-Trace gegen Blob-Init-Writes.

Input : /root/s9test/kprobe_init_trace.txt  (vom Capture-Skript)
        /tmp/opencode/s905x/blob_init_writes.tsv (Phase 2a)
Output: /tmp/opencode/s905x/init_diff_report.txt

Normalisierung:
  addr < 0x1000          -> addr + 0x4000   (logisch -> Offset)
  0x102500xx             -> 0x20xx          (SDIO-Local)
Ausblenden:
  FW-Download 0x5000..0x8fff
  bekannte RF3WIRE (0x48xx), PHY/AGC (0x4axx/0x4exx)
"""
import re, sys

TRACE = "/tmp/opencode/s905x/kprobe_init_trace.txt"
BLOB_TSV = "/tmp/opencode/s905x/blob_init_writes.tsv"
OUT = "/tmp/opencode/s905x/init_diff_report.txt"

def norm_addr(a):
    if a is None: return None
    if 0x10250000 <= a <= 0x102500ff:
        return 0x2000 | (a & 0xff)
    if a < 0x1000:
        return a + 0x4000
    return a

def filtered(a):
    if a is None: return True
    if 0x5000 <= a <= 0x8fff: return True       # FW
    if 0x4800 <= a <= 0x49ff: return True        # RF3WIRE (bekannt)
    if 0x4a00 <= a <= 0x4aff: return True        # PHY
    if 0x4e00 <= a <= 0x4eff: return True        # AGC
    return False

def load_blob():
    blob = {}  # addr -> set of values
    for l in open(BLOB_TSV):
        p = l.rstrip("\n").split("\t")
        if p[0] == "func": continue
        try:
            a = int(p[1], 0)
        except:
            continue
        try:
            v = int(p[3], 0)
        except:
            continue
        a = norm_addr(a)
        if filtered(a): continue
        blob.setdefault(a, set()).add(v & 0xffffffff)
    return blob

def parse_trace():
    """ Liest Kprobe-Trace: rtw_w8/w16/w32/sdio_wloc events. """
    port = {}  # addr -> list of (val, width)
    ev = re.compile(r'(rtw_w8|rtw_w16|rtw_w32|sdio_wloc):\s+.*addr=0x([0-9a-f]+).*val=0x([0-9a-f]+)')
    widthmap = {"rtw_w8":8,"rtw_w16":16,"rtw_w32":32,"sdio_wloc":"sdio"}
    for line in open(TRACE):
        m = ev.search(line)
        if not m: continue
        w = widthmap[m.group(1)]
        a = int(m.group(2), 16)
        v = int(m.group(3), 16)
        a = norm_addr(a)
        if filtered(a): continue
        port.setdefault(a, []).append((v & 0xffffffff, w))
    return port

def main():
    blob = load_blob()
    port = parse_trace()
    lines = []
    lines.append("=== INIT-DIFF REPORT ===")
    lines.append("Blob-Register (nicht gefiltert): %d" % len(blob))
    lines.append("Port-Register (nicht gefiltert): %d" % len(port))
    lines.append("")
    # 1) im Blob, aber NICHT im Port (fehlende Writes)
    missing = sorted(set(blob) - set(port))
    lines.append("=== FEHLENDE Writes (im Blob, nicht im Port) [%d] ===" % len(missing))
    for a in missing:
        lines.append("  0x%04x  blob_vals=%s" % (a, sorted(hex(x) for x in blob[a])))
    lines.append("")
    # 2) im Port, aber NICHT im Blob (zusaetzliche Writes)
    extra = sorted(set(port) - set(blob))
    lines.append("=== ZUSAETZLICHE Writes (im Port, nicht im Blob) [%d] ===" % len(extra))
    for a in extra:
        pv = sorted(set(hex(v) for v,w in port[a]))
        lines.append("  0x%04x  port_vals=%s" % (a, pv))
    lines.append("")
    # 3) Wert-Abweichung (Adresse in beiden, Wert nicht in Blob-Menge)
    lines.append("=== WERT-ABWEICHUNG (Port-Wert nicht in Blob) ===")
    nval = 0
    for a in sorted(set(blob) & set(port)):
        bvals = blob[a]
        for (v, w) in port[a]:
            if v not in bvals:
                lines.append("  0x%04x  port=0x%x (w=%s)  blob=%s" % (a, v, w, sorted(hex(x) for x in bvals)))
                nval += 1
    if nval == 0:
        lines.append("  (keine)")
    lines.append("")
    # 4) Schwerpunkt-Liste
    KEY = {0x40b0:"HIMR_88E",0x40b4:"HISR_88E(W1C)",0x40b8:"HIMRE_88E",0x4130:"FWIMR",
           0x4100:"CR",0x4608:"RCR",0x4102:"MSR",0x4421:"FWHW_TXQ+1",0x4422:"TXQ/BCN",
           0x4540:"BCN0",0x4550:"TBTT0",0x410c:"RXDMA",0x4280:"RXDMA",0x4281:"RXDMA",
           0x4605:"MAC",0x4040:"MAC",0x4026:"MAC",0x44c8:"MAC",0x44d0:"MAC"}
    lines.append("=== SCHWERPUNKT (Blob vs Port) ===")
    for a in sorted(KEY):
        b = sorted(hex(x) for x in blob.get(a, []))
        p = sorted(set(hex(v) for v,w in port.get(a, [])))
        mark = "OK" if (set(blob.get(a,set())) & set(v for v,w in port.get(a,[]))) else "DIFF"
        lines.append("  0x%04x %-14s blob=%s port=%s [%s]" % (a, KEY[a], b, p, mark))
    open(OUT, "w").write("\n".join(lines))
    print("\n".join(lines))
    print("\nReport:", OUT)

if __name__ == "__main__":
    main()