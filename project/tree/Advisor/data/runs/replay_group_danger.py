#!/usr/bin/env python3
"""Replay the Borg-style (stationary monsters excluded) group-danger rule (Borg memo §3.1) over a Pilot run.

For every non-empty monlist event, group = Σ count × (melee_max × speed_x + 150 × drain_blows)
over the monsters *in view* (monlist has no distances, so this over-counts far monsters), divided by
the character's current HP at that moment (from decisions.jsonl). Writes <nick>_replay.csv.
Clock alignment: events.jsonl `t` restarts at each Pilot start; segment k is matched to the next
decisions 'started' record whose gap to the following start can hold the segment (greedy).
Usage: python3 replay_group_danger.py dive03
"""
import bisect, csv, json, os, re, sys
nick = sys.argv[1] if len(sys.argv) > 1 else "dive03"
RUN = f"/projectnb/jbrcs/mangband/runs/pilot/{nick}"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{nick}_replay.csv")
table = {r["name"]: r for r in csv.DictReader(open(
    "/projectnb/jbrcs/mangband/Advisor/data/monsters/danger_table.csv"))}
# levels > 40 aren't in danger_table: fall back to monsters.csv
allm = {r["name"]: r for r in csv.DictReader(open("/projectnb/jbrcs/mangband/Advisor/data/monsters/monsters.csv"))}

def mon_threat(name):
    r = table.get(name)
    if r and "NEVER_MOVE" in r["tags"].split("|"):
        return 0.0, int(r["danger"])   # stationary: only dangerous if you stand next to it
    if r:
        return float(r["melee_max"]) * float(r["speed_x"]) + 50 * int(r["drain_blows"]), int(r["danger"])
    m = allm.get(name)
    if m:
        return float(m["melee_max"]) * max(1.0, (int(m["speed"]) - 100) / 10), 5
    return None, None

dec = [json.loads(l) for l in open(f"{RUN}/decisions.jsonl") if l.strip()]
starts = [d["t"] for d in dec if d.get("kind") == "attention" and d.get("what") == "started"]
end = dec[-1]["t"]
hp_t = [d["t"] for d in dec if d.get("hp") and d["hp"][1] > 1]
hp_v = [d["hp"] for d in dec if d.get("hp") and d["hp"][1] > 1]
dep_v = [d.get("depth") for d in dec if d.get("hp") and d["hp"][1] > 1]

segs, prev = [], 1e18
events = [json.loads(l) for l in open(f"{RUN}/events.jsonl") if l.strip()]
for i, e in enumerate(events):
    if e["t"] < prev - 5:
        segs.append([i, None])
    segs[-1][1] = e["t"]
    prev = e["t"]
bounds = [s[0] for s in segs] + [len(events)]
si, offs = 0, []
for k, s in enumerate(segs):
    while si < len(starts):
        gap = (starts[si + 1] if si + 1 < len(starts) else end + 60) - starts[si]
        if s[1] <= gap + 5:
            break
        si += 1
    offs.append(starts[min(si, len(starts) - 1)])
    si += 1

pat = re.compile(r"^(.*?) \('.'\)/\('.'\):\[(\d+)\]")
rows, unknown = [], set()
for k in range(len(segs)):
    for e in events[bounds[k]:bounds[k + 1]]:
        if e["ev"] != "monlist":
            continue
        mons = []
        for line in e["lines"]:
            m = pat.match(line)
            if m:
                mons.append((m.group(1), int(m.group(2))))
        if not mons:
            continue
        ep = offs[k] + e["t"]
        j = bisect.bisect_right(hp_t, ep) - 1
        if j < 0 or ep - hp_t[j] > 30:
            continue
        hp, hpmax = hp_v[j]
        group, maxdanger = 0.0, 0
        for name, n in mons:
            th, dg = mon_threat(name)
            if th is None:
                unknown.add(name)
                continue
            group += n * th
            maxdanger = max(maxdanger, dg)
        rows.append(dict(epoch=round(ep, 1), depth=dep_v[j], hp=hp, hpmax=hpmax, group=round(group),
                         ratio=round(group / max(hp, 1), 2), max_table_danger=maxdanger,
                         monsters="; ".join(f"{n}x{c}" for n, c in mons)))
with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
print(f"{len(rows)} monlist samples -> {OUT}; unknown names: {sorted(unknown)[:10]}")
