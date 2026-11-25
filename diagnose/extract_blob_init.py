#!/usr/bin/env python3
"""
Phase 2a (offline): Extrahiere aus 9082xs_obj.o rekursiv alle Register-Writes,
die von _hal_init_tll9083xs aus aufgerufen werden (inkl. tilk_fw_iol-Zweig,
PowerOn_9082XS_Init, Interrupt9082XSdio_init, SdioAggregationSetting_init,
BeaconParameters_init, TxBeacon_Stop, _TxBeacon_Resume).

Ergebnis: /tmp/opencode/s905x/blob_init_writes.tsv
Spalten: func  addr  width  value  raw_addr  note

Die bereits verifizierten Bloecke (92 RF, 284 PHY, 130 AGC) werden markiert
(note=KNOWN_RF/PHY/AGC), aber NICHT ausgeblendet (damit man sie sieht).
"""
import subprocess, re, sys, os

BLOB = "/home/alx/s905x-tvbox/sdcard-build-backup/alexelec_9082xs/9082xs_obj.o"
OBJDUMP = "aarch64-linux-gnu-objdump"
OUT = "/tmp/opencode/s905x/blob_init_writes.tsv"
ROOT = "_hal_init_tll9083xs"

# Write-Funktionen -> (Breite, Name)
WRITE_FUNCS = {
    "_tilk_wr8": 8,
    "tilk_wr8": 8,
    "_tilk_wr16": 16,
    "tilk_wr16": 16,
    "_tilk_wr32": 32,
    "tilk_wr32": 32,
    "_sdio_write_loc": "sdio",
    "sdio_write_loc": "sdio",
    "TDB_4Byte_Write": 32,
    "TDB_BBRegSet": "bbset",
    "tilk_hwreg_set": "hwreg",
}

def disasm():
    out = subprocess.run([OBJDUMP, "-dr", BLOB], capture_output=True, text=True).stdout
    return out

def parse_functions(dis):
    """ Zerlegt Disassembly in {funcname: [lines]} anhand Symbol-Labels. """
    funcs = {}
    cur = None
    for line in dis.splitlines():
        m = re.match(r'^([0-9a-f]+) <([^>]+)>:', line)
        if m:
            cur = m.group(2)
            # normalize: strip module suffix like [9082xs]
            cur = re.sub(r'\s*\[.*\]$', '', cur)
            funcs[cur] = []
            continue
        if cur is not None:
            funcs[cur].append(line)
    return funcs

def find_calls(lines):
    """ Findet alle bl-Aufrufe in einem Funktionsblock. Rueckgabe: [(target, ...)]. """
    calls = []
    for line in lines:
        m = re.search(r'\bbl\s+[0-9a-f]+ <([^>]+)>', line)
        if m:
            tgt = re.sub(r'\s*\[.*\]$', '', m.group(1))
            calls.append(tgt)
    return calls

def build_callgraph(funcs):
    cg = {}
    for name, lines in funcs.items():
        cg[name] = find_calls(lines)
    return cg

def reachable(cg, root):
    seen = set()
    stack = [root]
    order = []
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        order.append(n)
        for c in cg.get(n, []):
            if c not in seen:
                stack.append(c)
    return seen, order

# --- Register-Write-Extraktion pro Funktion ---
# Wir parsen den Instruktionsstrom und verfolgen mov/movk-Paare, die w2/w3 (bzw. w1/w2) laden,
# gefolgt von einem bl <write_func>. Das ist ein einfacher, robuster Heuristik-Parser.

def parse_writes(funcname, lines):
    """ Extrahiert (addr, width, value) Writes aus Bewegungen vor write-calls. """
    writes = []
    # Register-Tracking: w1=addr, w2=val/mask, w3=val
    reg = {}  # regname -> int value (nur was wir verfolgen)
    for line in lines:
        # mov wN, #imm
        m = re.search(r'\bmov\s+(w\d+), #(0x[0-9a-f]+|\d+)', line)
        if m:
            reg[m.group(1)] = int(m.group(2), 0)
            continue
        # movk wN, #imm, lsl #16
        m = re.search(r'\bmovk\s+(w\d+), #(0x[0-9a-f]+|\d+), lsl #16', line)
        if m:
            v = int(m.group(2), 0) << 16
            reg[m.group(1)] = (reg.get(m.group(1), 0) & 0xffff) | v
            continue
        # bl <write_func>
        m = re.search(r'\bbl\s+[0-9a-f]+ <([^>]+)>', line)
        if m:
            tgt = re.sub(r'\s*\[.*\]$', '', m.group(1))
            if tgt in WRITE_FUNCS:
                w = WRITE_FUNCS[tgt]
                addr = reg.get("w1")
                v2 = reg.get("w2")
                v3 = reg.get("w3")
                if w == 8 and addr is not None and v2 is not None:
                    writes.append((funcname, addr, 8, v2 & 0xff, addr, ""))
                elif w == 16 and addr is not None and v2 is not None:
                    writes.append((funcname, addr, 16, v2 & 0xffff, addr, ""))
                elif w == 32 and addr is not None and v2 is not None:
                    writes.append((funcname, addr, 32, v2 & 0xffffffff, addr, ""))
                elif w == "sdio" and addr is not None and v2 is not None:
                    writes.append((funcname, addr, "sdio", v2 & 0xffffffff, addr, ""))
                elif w == "bbset" and addr is not None and v3 is not None:
                    # TDB_BBRegSet(addr, mask=w2, val=w3)
                    writes.append((funcname, addr, "bbset", v3 & 0xffffffff, addr, "mask=0x%08x" % (v2 & 0xffffffff if v2 else 0)))
                elif w == "hwreg" and v2 is not None:
                    # tilk_hwreg_set(x0=adapter, w1=hwreg_id, x2=val) -> kein direkter addr
                    writes.append((funcname, "hwreg#%d" % (addr or 0), "hwreg", v2 & 0xffffffff, addr, ""))
            # register state nach call verwerfen (caller-saved)
            reg = {}
            continue
        # andere Instruktionen: bei movz/movn etc. state invalidieren
        if re.search(r'\b(movz|movn|ldr|ldp|add|sub|and|orr)\b', line):
            # vorsichtig: nur invalidate wenn Ziel ein w-Register ist, das wir tracken
            mm = re.search(r'\b(?:movz|movn|ldr|add|sub|and|orr)\s+(w\d+)', line)
            if mm and mm.group(1) not in ("w1", "w2", "w3"):
                pass
    return writes

def classify(addr, width):
    if not isinstance(addr, int):
        return ""
    # RF 0x4000-0x49ff (rf3wire offset 0x4840 etc) -> known RF
    if 0x4000 <= addr <= 0x49ff:
        return "KNOWN_RF"
    # PHY/AGC-Bereich 0x4a00-0x4fff und 0x4e00-0x4eff -> known PHY/AGC
    if 0x4a00 <= addr <= 0x4fff:
        return "KNOWN_PHYAGC"
    return ""

def main():
    dis = disasm()
    funcs = parse_functions(dis)
    cg = build_callgraph(funcs)
    seen, order = reachable(cg, ROOT)
    # nur die tatsaechlich erreichbaren Init-Funktionen
    rows = []
    for fn in order:
        if fn not in funcs:
            continue
        for (f, addr, width, val, raw, note) in parse_writes(fn, funcs[fn]):
            cls = classify(addr, width)
            fullnote = note if not cls else (cls + (" " + note if note else ""))
            rows.append((f, addr, width, val, raw, fullnote))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as fh:
        fh.write("func\taddr\twidth\tvalue\traw_addr\tnote\n")
        for r in rows:
            fh.write("%s\t%s\t%s\t0x%x\t%s\t%s\n" % (r[0], r[1], r[2], r[3], r[4], r[5]))
    # Report
    print("Erreichbare Init-Funktionen vom Root:", len(seen))
    print("Schreibzugriffe gesamt:", len(rows))
    # Highlight-Liste
    hi = [r for r in rows if any(k in str(r[1]) for k in ["0x40b0","0x40b4","0x40b8","0x4130","0x4421","0x4422","0x4540","0x4550","0x455","0x410c","0x4280","0x4605","0x4026"]) or "hwreg" in str(r[2])]
    print("\n=== HIGHLIGHT (IOL/HISR/MAC/Beacon/SDIO-Local) ===")
    for r in hi[:60]:
        print("  %-24s addr=%-8s w=%-6s val=0x%x %s" % (r[0], r[1], r[2], r[3], r[5]))
    print("\nTSV geschrieben:", OUT)

if __name__ == "__main__":
    main()