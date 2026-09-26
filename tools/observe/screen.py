#!/usr/bin/env python3
"""screen -- print what the player saw at a session time.

    python3 screen.py SESSION MM:SS[.s] [--cols N] [--after]

Times are on the pktlog clock (as in timeline.py). Prints the last screen
captured at or before that time (--after: the first one after it)."""
import argparse
import json
import os
import re

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("when", nargs="+")
    ap.add_argument("--cols", type=int, default=100)
    ap.add_argument("--after", action="store_true")
    a = ap.parse_args()
    epoch = None
    for l in open(os.path.join(a.session, "pkt.jsonl")):
        m = re.search(r"epoch=([\d.]+)", l)
        if m:
            epoch = float(m.group(1))
            break
    frames = [json.loads(l) for l in open(os.path.join(a.session, "screens.jsonl"))]
    for w in a.when:
        mm, ss = w.split(":")
        t = epoch + int(mm) * 60 + float(ss)
        if a.after:
            fr = next((f for f in frames if f["t"] > t), frames[-1])
        else:
            fr = max((f for f in frames if f["t"] <= t), key=lambda f: f["t"], default=frames[0])
        rel = fr["t"] - epoch
        print(f"===== {w} (frame at {int(rel // 60):02d}:{rel % 60:05.2f})")
        for r in fr["rows"]:
            r = ANSI.sub("", r)[:a.cols].rstrip()
            if r:
                print(r)


if __name__ == "__main__":
    main()
