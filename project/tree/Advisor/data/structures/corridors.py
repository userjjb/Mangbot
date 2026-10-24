#!/usr/bin/env python3
"""One-wide and two-wide straight corridor runs in the Pilot's level dumps (runs/pilot/<nick>/levels/*.txt).

A dump is a 66-row map (198 columns) after a one-line header "# <depth> ft, <date> <t0> - <t1>; structures: ...".
Glyphs: '#' and '%' walls (granite, mineral vein), ' ' unknown, anything else passable or an object/monster on floor
(doors '+' and "'" count as passable here).

A run is a maximal straight horizontal or vertical line of passable squares whose two side neighbours are walls at
every square (width 1), or which is exactly two passable squares wide between walls (width 2). Runs shorter than MIN
are ignored. Unknown squares break a run.

usage: corridors.py [--min 5] [--nick dive04] [FILES...]   writes corridors.csv (one row per run) and
       corridor_levels.csv (one row per dump: depth, structures, n1, longest1, n2, longest2) next to this script."""
import argparse, csv, glob, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
WALL = set("#%")


def load(path):
    with open(path) as f:
        head = f.readline().rstrip("\n")
        rows = [l.rstrip("\n").ljust(198) for l in f]
    return head, rows


def runs(rows, minlen):
    H, W = len(rows), max(len(r) for r in rows)
    g = lambda y, x: rows[y][x] if 0 <= y < H and 0 <= x < W else " "
    pas = lambda c: c not in WALL and c != " "
    out = []
    for horiz in (True, False):
        A, B = (H, W) if horiz else (W, H)
        for a in range(A):
            for width in (1, 2):
                b = 0
                while b < B:
                    def ok(bb):
                        y, x = (a, bb) if horiz else (bb, a)
                        dy, dx = (1, 0) if horiz else (0, 1)
                        cells = [g(y + i * dy, x + i * dx) for i in range(width)]
                        if not all(pas(c) for c in cells):
                            return False
                        return g(y - dy, x - dx) in WALL and g(y + width * dy, x + width * dx) in WALL
                    if ok(b):
                        s = b
                        while b < B and ok(b):
                            b += 1
                        if b - s >= minlen:
                            y, x = (a, s) if horiz else (s, a)
                            out.append(dict(width=width, dir="h" if horiz else "v", y=y, x=x, length=b - s))
                    else:
                        b += 1
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--min", type=int, default=5)
    ap.add_argument("--nick", default="dive04")
    ap.add_argument("files", nargs="*")
    o = ap.parse_args()
    files = o.files or sorted(glob.glob(f"/projectnb/jbrcs/mangband/runs/pilot/{o.nick}/levels/*.txt"))
    allr, lev = [], []
    for p in files:
        head, rows = load(p)
        m = re.match(r"# (\d+) ft.*structures: (.*)", head)
        rs = runs(rows, o.min)
        for r in rs:
            r["file"] = os.path.basename(p)
        allr += rs
        w1 = [r["length"] for r in rs if r["width"] == 1]
        w2 = [r["length"] for r in rs if r["width"] == 2]
        known = sum(c != " " for r in rows for c in r)
        lev.append(dict(file=os.path.basename(p), depth_ft=m.group(1) if m else "", structures=m.group(2) if m else "",
                        known_squares=known, n1=len(w1), longest1=max(w1, default=0), n2=len(w2), longest2=max(w2, default=0)))
    with open(os.path.join(HERE, "corridors.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["file", "width", "dir", "y", "x", "length"]); w.writeheader(); w.writerows(allr)
    with open(os.path.join(HERE, "corridor_levels.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(lev[0])); w.writeheader(); w.writerows(lev)
    print(len(files), "dumps;", sum(r["width"] == 1 for r in allr), "one-wide runs;", sum(r["width"] == 2 for r in allr), "two-wide runs")
