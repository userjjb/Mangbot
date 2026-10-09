#!/usr/bin/env python3
"""Navigator response latency: for each 'attention' record (Pilot news) in decisions.jsonl, seconds until the next
Navigator-issued order: a 'goal' record (goals are set by the Navigator, except the Pilot's own flee/recover goals) or an
'act' whose 'why' starts with 'agent:'. Gaps over 600 s are dropped (idle/off time). Also: idle time after goal_done/
goal_failed (the Pilot without a goal). Usage: latency.py NICK [START_EPOCH END_EPOCH]"""
import json, sys, statistics, collections
nick = sys.argv[1]; t0 = float(sys.argv[2]) if len(sys.argv) > 2 else 0; t1 = float(sys.argv[3]) if len(sys.argv) > 3 else 1e12
dec = [json.loads(l) for l in open(f"/projectnb/jbrcs/mangband/runs/pilot/{nick}/decisions.jsonl")]
dec = [d for d in dec if t0 <= d["t"] <= t1]
PILOT_GOALS = ("flee", "recover", "town", "rest")
def nav_order(d):
    if d["kind"] == "goal":
        g = str(d.get("goal") or "")
        return bool(g) and not g.startswith(PILOT_GOALS)
    return d["kind"] == "act" and str(d.get("why", "")).startswith("agent:")
orders = [d["t"] for d in dec if nav_order(d)]
import bisect
lat = collections.defaultdict(list)
for d in dec:
    if d["kind"] != "attention": continue
    i = bisect.bisect_right(orders, d["t"])
    if i < len(orders) and orders[i] - d["t"] <= 600:
        lat[d.get("what")].append(orders[i] - d["t"])
print(f"{nick}: {len(orders)} Navigator orders")
print(f"{'event':24s} {'n':>5s} {'median s':>9s} {'p90 s':>7s}")
for k, v in sorted(lat.items(), key=lambda x: -len(x[1]))[:16]:
    v.sort(); print(f"{str(k):24s} {len(v):5d} {statistics.median(v):9.1f} {v[int(0.9*(len(v)-1))]:7.1f}")
