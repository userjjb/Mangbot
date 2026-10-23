#!/usr/bin/env python3
"""XP and risk by depth, per mission, from the Pilot's 30-second audit_check records (decisions.jsonl: t, depth, hp, exp).

Each interval between consecutive checks (gap < 120 s) is credited to the earlier check's depth: minutes there, exp gained
(exp[0] difference; drains/restores show as negative/positive jumps), lowest HP% seen. Town (depth 0) is listed apart.
Bands: 50-250, 300-450, 500-650, 700+ ft.

usage: xp_by_depth.py [MISSION ...]   (default: all in runs/missions.json); writes xp_by_depth.csv next to this script."""
import csv, collections, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = "/projectnb/jbrcs/mangband/runs"
BANDS = [(0, 0, "town"), (1, 5, "50-250"), (6, 9, "300-450"), (10, 13, "500-650"), (14, 99, "700+")]


def band(d):
    return next(n for lo, hi, n in BANDS if lo <= d <= hi)


def epoch(s):
    return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M"))


missions = json.load(open(f"{RUNS}/missions.json"))
want = set(sys.argv[1:])
checks = collections.defaultdict(list)
for line in open(f"{RUNS}/pilot/dive04/decisions.jsonl"):
    if '"audit_check"' not in line:
        continue
    r = json.loads(line)
    if "exp" in r and r.get("hp"):
        checks["dive04"].append(r)
rows = []
for m in missions:
    if want and m["label"] not in want:
        continue
    t0, t1 = epoch(m["start"]), epoch(m["end"]) + 60
    cs = [c for c in checks[m["nick"]] if t0 <= c["t"] <= t1]
    agg = collections.defaultdict(lambda: dict(minutes=0.0, exp=0, low=101.0, levels=set()))
    for a, b in zip(cs, cs[1:]):
        dt = b["t"] - a["t"]
        if dt > 120:
            continue
        g = agg[band(a["depth"])]
        g["minutes"] += dt / 60
        de = b["exp"][0] - a["exp"][0]
        if abs(de) < 5000:
            g["exp"] += de
        g["low"] = min(g["low"], 100 * a["hp"][0] / a["hp"][1], 100 * b["hp"][0] / b["hp"][1])
        g["levels"].add(a["depth"])
    for _, _, n in BANDS:
        if n in agg and agg[n]["minutes"] > 0.5:
            g = agg[n]
            rows.append(dict(mission=m["label"], navigator=m.get("navigator"), band=n, minutes=round(g["minutes"], 1),
                             exp=g["exp"], exp_per_min=round(g["exp"] / g["minutes"], 1), lowest_hp_pct=round(g["low"]),
                             clvl=cs[0].get("clvl") if cs else "", depths=" ".join(str(d * 50) for d in sorted(g["levels"]))))
with open(os.path.join(HERE, "xp_by_depth.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
tot = collections.defaultdict(lambda: [0.0, 0, 101])
for r in rows:
    t = tot[r["band"]]; t[0] += r["minutes"]; t[1] += r["exp"]; t[2] = min(t[2], r["lowest_hp_pct"])
for r in rows:
    print(r)
print("\nall missions by band: minutes, exp, exp/min, lowest HP%")
for _, _, n in BANDS:
    if n in tot:
        m_, e, lo = tot[n]; print(f"  {n:8s} {m_:6.1f} min {e:6d} exp {e / m_ if m_ else 0:6.1f}/min  low {lo}%")
