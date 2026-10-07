#!/usr/bin/env python3
"""Episodes where the group-danger ratio crosses a tier, and what HP did in the next 60 s."""
import bisect, csv, json, sys, datetime
nick = sys.argv[1] if len(sys.argv) > 1 else "dive03"
rows = list(csv.DictReader(open(f"{nick}_replay.csv")))
dec = [json.loads(l) for l in open(f"/projectnb/jbrcs/mangband/runs/pilot/{nick}/decisions.jsonl") if l.strip()]
H = [(d["t"], d["hp"][0] / d["hp"][1]) for d in dec if d.get("hp") and d["hp"][1] > 1]
ht = [h[0] for h in H]
def min_hp_after(ep, win=60):
    i, j = bisect.bisect_left(ht, ep), bisect.bisect_right(ht, ep + win)
    return min((H[k][1] for k in range(i, j)), default=None)
# baseline: all 60-s windows' low points, and the "bad" moments (HP frac < 0.5)
for tier in (0.3, 0.6, 1.0):
    eps, last = [], -1e9
    for r in rows:
        ep = float(r["epoch"])
        if float(r["ratio"]) > tier:
            if ep - last > 60:
                eps.append([ep, float(r["ratio"]), r["monsters"], float(r["hp"]) / float(r["hpmax"])])
            else:
                eps[-1][1] = max(eps[-1][1], float(r["ratio"]))
            last = ep
    bad = [e for e in eps if (min_hp_after(e[0]) or 1) < 0.5]
    print(f"tier >{tier}: {len(eps)} episodes; followed by HP<50% within 60 s: {len(bad)}")
    if tier == 0.6:
        for e in eps:
            m = min_hp_after(e[0])
            print("  ", datetime.datetime.fromtimestamp(e[0]).strftime("%m-%d %H:%M"), f"ratio {e[1]:.2f}",
                  f"hp {e[3]:.2f} -> min {m if m is None else round(m,2)}", e[2][:80])
# the other direction: every drop below 50% HP — was a >0.6 sample seen in the 60 s before?
lows, lastlow = [], -1e9
for t, f in H:
    if f < 0.5 and t - lastlow > 120:
        lows.append(t)
    if f < 0.5:
        lastlow = t
rt = [float(r["epoch"]) for r in rows]
print(f"\nHP<50% episodes: {len(lows)}")
for t in lows:
    i, j = bisect.bisect_left(rt, t - 60), bisect.bisect_right(rt, t)
    mx = max((float(rows[k]["ratio"]) for k in range(i, j)), default=None)
    mons = rows[j - 1]["monsters"][:70] if j > i else "(no monlist sample in the 60 s before)"
    print("  ", datetime.datetime.fromtimestamp(t).strftime("%m-%d %H:%M:%S"), "max ratio before:", mx, "|", mons)
