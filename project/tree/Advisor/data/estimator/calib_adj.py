#!/usr/bin/env python3
"""How many monsters attack us at once in real fights (replay files): per episode, distinct melee attackers per 2-block
window while any attacks, vs the crowd in view within 5 squares (mons_series). Sets the simulator's max_adj."""
import collections, glob, json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import options_sim as S  # noqa: E402
import replay as R  # noqa: E402
import calib_blows as C  # noqa: E402  (runs its report; quiet enough)

rows = []
for fn in sorted(glob.glob(f"{R.REPLAYS}/ep*.json"), key=lambda f: int(f.split("ep")[-1].split(".")[0])):
    ep = json.load(open(fn))
    f = R.bubble_factor(ep)
    ev = []
    for h in ep.get("hostile_msgs") or []:
        m = C.HIT.match(h["text"]) or C.MISS.match(h["text"])
        if m:
            ev.append((h["t"], m.group(1)))
    if not ev:
        continue
    ev.sort()
    t, t_end, att = ep["t0"], ep["t_end"], []
    while t < t_end:
        w = 2 * R.TICK_S / f(t)                                # a 2-block window in wall seconds
        names = collections.Counter(n for tt, n in ev if t <= tt < t + w)
        # distinct attackers: per race, at most the number of that race in view within 2 squares, at least 1
        k = 0
        near = collections.Counter()
        cur = [mm for tt, mm in ep.get("mons_series") or [] if tt <= t]
        if cur:
            py, px = ep["player"]["pos"]
            for tt, y, x in ep.get("pos_series") or []:
                if tt <= t:
                    py, px = y, x
            for y, x, n in cur[-1]:
                if S.adist(y - py, x - px) <= 2:
                    near[n] += 1
        for n, c in names.items():
            k += max(1, min(near.get(n, 1), c // 2 if c >= 4 else 1))
        if k:
            att.append(k)
        t += w
    crowd = [sum(1 for y, x, n in mm) for tt, mm in ep.get("mons_series") or [] if ep["t0"] <= tt <= t_end]
    rows.append((ep["idx"], round(statistics.mean(att), 2) if att else 0, max(att) if att else 0,
                 round(statistics.mean(crowd), 1) if crowd else 0, max(crowd) if crowd else 0))
print("\nidx, mean attackers (windows with any), max attackers, mean monsters in view, max in view")
for r in rows:
    print(r)
print("median of mean attackers:", statistics.median(r[1] for r in rows), " median max:", statistics.median(r[2] for r in rows))
