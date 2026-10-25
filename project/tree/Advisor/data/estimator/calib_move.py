#!/usr/bin/env python3
"""Monster movement in real fights vs the simulator's 'every monster walks straight at us at its speed':
for consecutive mons records (0.3-3 s apart) a monster is matched to its nearest same-name position in the next record
(<= its possible moves + 1). For each match not adjacent at the start: observed change in distance to us per block vs the
model's -speed_x per block (closing until adjacent). Reports the share approaching, holding, receding, and the median
approach rate relative to the model, split by race flags (erratic RAND_25/50, NEVER_MOVE, others)."""
import collections, glob, json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import options_sim as S  # noqa: E402
import replay as R  # noqa: E402

stats = collections.defaultdict(lambda: dict(n=0, closer=0, same=0, farther=0, rate=[]))
for fn in glob.glob(f"{R.REPLAYS}/ep*.json"):
    ep = json.load(open(fn))
    f = R.bubble_factor(ep)
    pos = sorted(ep.get("pos_series") or [])
    def me(t):
        p = tuple(ep["player"]["pos"])
        for tt, y, x in pos:
            if tt <= t:
                p = (y, x)
            else:
                break
        return p
    ms = sorted((t, mm) for t, mm in ep.get("mons_series") or [] if ep["t0"] - 5 <= t <= ep["t_end"])
    for (ta, A), (tb, B) in zip(ms, ms[1:]):
        dt = tb - ta
        if not (0.3 <= dt <= 3):
            continue
        blocks = dt * f(ta) / R.TICK_S
        pa, pb = me(ta), me(tb)
        used = set()
        for y, x, n in A:
            r = S.RACES.get(n)
            if not r:
                continue
            sx = S.ENERGY.get(int(r["speed"]), 1000) / 1000
            cands = [(S.adist(y2 - y, x2 - x), i) for i, (y2, x2, n2) in enumerate(B) if n2 == n and i not in used]
            if not cands:
                continue
            d, i = min(cands)
            if d > sx * blocks + 1.5:
                continue
            used.add(i)
            da = S.adist(y - pa[0], x - pa[1]); db = S.adist(B[i][0] - pb[0], B[i][1] - pb[1])
            if da <= 1:
                continue
            fl = set(r["flags"].split("|"))
            cls = "never_move" if "NEVER_MOVE" in fl else "erratic" if fl & {"RAND_25", "RAND_50"} else "normal"
            cls += "/we_moved" if pa != pb else "/we_stood"
            others_adj = sum(1 for y3, x3, n3 in A if S.adist(y3 - pa[0], x3 - pa[1]) <= 1)
            if pa == pb and da == 2 and others_adj >= 2:
                cls += "/queued?"
            s = stats[cls]; s["n"] += 1
            s["closer" if db < da else "same" if db == da else "farther"] += 1
            model = min(sx * blocks, da - 1)
            if model > 0:
                s["rate"].append((da - db) / model)
for cls, s in stats.items():
    n = s["n"]
    print(f"{cls:10s} n={n:5d} closer {s['closer'] / n:.2f} same {s['same'] / n:.2f} farther {s['farther'] / n:.2f}"
          f"  observed/model closing: median {statistics.median(s['rate']):.2f} mean {statistics.mean(s['rate']):.2f}")
