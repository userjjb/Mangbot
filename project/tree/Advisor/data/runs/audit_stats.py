#!/usr/bin/env python3
"""State-audit error rates for one mission (pilot 67acff1+).

The pilot compares its model with a fresh status/inven query every 30 s (not in a shop, not busy)
and writes an `audit` record to decisions.jsonl only when a field differs. The number of checks
is printed in the report ("State audit: N checks"); pass it with --checks, or the script estimates it
from the time the pilot was logging (wall time / 30 s).

usage: audit_stats.py NICK START [END] [--checks N]   (START/END like 2026-10-07T08:49)
"""
import argparse, collections, datetime, json

ap = argparse.ArgumentParser()
ap.add_argument("nick"); ap.add_argument("start"); ap.add_argument("end", nargs="?")
ap.add_argument("--checks", type=int)
a = ap.parse_args()
t0 = datetime.datetime.fromisoformat(a.start).timestamp()
t1 = datetime.datetime.fromisoformat(a.end).timestamp() if a.end else 1e12
dec = [json.loads(l) for l in open(f"/projectnb/jbrcs/mangband/runs/pilot/{a.nick}/decisions.jsonl") if l.strip()]
dec = [d for d in dec if t0 <= d["t"] <= t1]
if not dec:
    raise SystemExit("no decisions in that window")
hm = lambda t: datetime.datetime.fromtimestamp(t).strftime("%H:%M:%S")

# time with decision records at most 30 s apart (the pilot acting), split town / dungeon
active = collections.Counter()
for p, q in zip(dec, dec[1:]):
    dt = q["t"] - p["t"]
    if dt <= 30:
        active["town" if p.get("depth") == 0 else "dungeon"] += dt
print(f"window {hm(dec[0]['t'])}-{hm(dec[-1]['t'])}, {len(dec)} records; "
      f"active {sum(active.values())/60:.1f} min (town {active['town']/60:.1f}, dungeon {active['dungeon']/60:.1f})")
wall = dec[-1]["t"] - dec[0]["t"]   # audit_tick runs every loop, logged or not
checks = a.checks or round(wall / 30)
print(f"checks: {checks} ({'from the report' if a.checks else 'estimated from wall time / 30 s, upper bound: shop and busy time not excluded'})")

aud = [d for d in dec if d["kind"] == "audit"]
by = collections.Counter(k for d in aud for k in d["diffs"])
print(f"audit records: {len(aud)} ({len(aud)/max(checks,1):.1%} of checks)")
for k, n in by.most_common():
    print(f"  {k:6s} {n:4d}  {n/max(checks,1):.1%}")

# persistence: does the same field differ again at the next audit (redraw didn't fix it)?
again = collections.Counter()
for p, q in zip(aud, aud[1:]):
    if q["t"] - p["t"] < 45:
        for k in p["diffs"]:
            if k in q["diffs"]:
                again[k] += 1
if again:
    print("same field differs at the next check (within 45 s):", dict(again))

print("\nrecords:")
for d in aud:
    where = "town" if d.get("depth") == 0 else f"{d.get('depth')}"
    for k, (m, f) in d["diffs"].items():
        print(f"  {hm(d['t'])} d={where:>4} {k:6s} model={m[:90]!s}\n{'':26s}fresh={f[:90]!s}")
