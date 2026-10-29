#!/usr/bin/env python3
"""timeline -- turn a record.py session into one readable, time-ordered log.

Merges, on the pktlog clock (seconds since the client started):
  NOTE   the player's chat messages (their commentary)
  KEYS   keys typed, grouped into bursts
  >>     commands sent to the server (walk/run directions decoded)
  msg    messages from the server
  ==     sidebar changes read off the screen: depth, HP, level, gold

    python3 timeline.py runs/observe/session1 > timeline.txt
"""
import json
import os
import re
import sys

ANSI = re.compile(r"\x1b\[[0-9;]*m")
DIRNAME = {1: "SW", 2: "S", 3: "SE", 4: "W", 5: "-", 6: "E", 7: "NW", 8: "N", 9: "NE", 0: "-"}


def load(session):
    recs = [json.loads(l) for l in open(os.path.join(session, "pkt.jsonl"))]
    epoch = None
    for e in recs:
        m = re.search(r"epoch=([\d.]+)", e.get("note", ""))
        if m:
            epoch = float(m.group(1))
    return recs, epoch


def sidebar(rows):
    """Depth, HP, level, gold from a GCU screen (None where not found)."""
    txt = [ANSI.sub("", r) for r in rows]
    out = {}
    for r in txt:
        left = r[:19]
        m = re.match(r"Cur HP\s+(-?\d+)", left)
        if m:
            out["hp"] = int(m.group(1))
        m = re.match(r"Max HP\s+(\d+)", left)
        if m:
            out["mhp"] = int(m.group(1))
        m = re.match(r"LEVEL\s+(\d+)", left)
        if m:
            out["lev"] = int(m.group(1))
        m = re.match(r"AU\s+(\d+)", left)
        if m:
            out["au"] = int(m.group(1))
        m = re.search(r"\s(\d+) ft\s*$|\s(Town)\s*$|\s(\d+[NSEW](?:, \d+[NSEW])?)\s*$", r[:90])
        if m and len(r[:90].rstrip()) > 60:
            out["depth"] = next(g for g in m.groups() if g)
    return out


def decode_send(e):
    name, h = e["name"], e["hex"]
    b = bytes.fromhex(h)
    if name == "PKT_WALK" and len(b) >= 2:
        return f"walk {DIRNAME.get(b[1], b[1])}"
    if name == "CUSTOM:'.'" and len(b) >= 2:
        return f"run {DIRNAME.get(b[1], b[1])}"
    if name == "PKT_MESSAGE":
        return None
    if name.startswith("CUSTOM:"):
        return f"cmd {name[7:]} {h[2:]}"
    return name.replace("PKT_", "").lower()


def main():
    session = sys.argv[1]
    recs, epoch = load(session)
    events = []   # (t, kind, text)
    keybuf, keyt = [], None

    def flush_keys():
        nonlocal keybuf, keyt
        if keybuf:
            events.append((keyt, "KEYS", "".join(keybuf)))
        keybuf, keyt = [], None

    for e in recs:
        t = e["t"]
        if e["dir"] == "K":
            if keyt is not None and t - lastk > 1.5:
                flush_keys()
            if keyt is None:
                keyt = t
            k = e.get("key")
            if e.get("muted"):
                k = "*"
            elif k == "\x1b":
                k = "<ESC>"
            elif k == "\r":
                k = "<RET>"
            elif k == "\x08":
                k = "<BS>"
            elif k and ord(k) < 32:
                k = f"^{chr(ord(k) + 64)}"
            if not e.get("keymap"):
                keybuf.append(k or "")
            lastk = t
        elif e["dir"] == "S":
            if e["name"] == "PKT_KEEPALIVE":
                continue
            if e["name"] == "PKT_MESSAGE":
                events.append((t, "NOTE", e["txt"][1:-1]))
                continue
            d = decode_send(e)
            if d:
                events.append((t, ">>", d))
        elif e["dir"] == "R" and e["name"] == "PKT_MESSAGE":
            # %ud type, %S text
            txt = bytes.fromhex(e["hex"])[3:].split(b"\0")[0].decode("latin1")
            if txt.strip():
                events.append((t, "msg", txt))
    flush_keys()

    # Sidebar changes from the screen recording
    last = {}
    if epoch:
        for l in open(os.path.join(session, "screens.jsonl")):
            fr = json.loads(l)
            sb = sidebar(fr["rows"])
            ch = {k: v for k, v in sb.items() if last.get(k) != v}
            if ch:
                last.update(sb)
                if set(ch) - {"au"} or "au" in ch:
                    events.append((fr["t"] - epoch, "==", " ".join(f"{k}={v}" for k, v in sb.items())))

    events.sort(key=lambda x: x[0])
    # Collapse repeats of the same command/message
    out, prev, n = [], None, 0
    for t, kind, text in events:
        key = (kind, text)
        if key == prev and kind in (">>", "msg"):
            n += 1
            continue
        if n:
            out[-1] += f"  (x{n + 1})"
        n = 0
        prev = key
        out.append(f"{int(t // 60):02d}:{t % 60:05.2f} {kind:4s} {text}")
    if n:
        out[-1] += f"  (x{n + 1})"
    print("\n".join(out))


if __name__ == "__main__":
    main()
