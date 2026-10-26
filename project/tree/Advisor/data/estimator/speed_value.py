"""Value of a Speed potion in 4 replay episodes: potions drunk per option, gain vs price (drinking at the start of a hard fight
vs the rules), and the value of carrying one at all (buying). Memo to_architect/2026-10-25-speed-slope.md."""
import sys, json, statistics
sys.path.insert(0, '/projectnb/jbrcs/mangband/Advisor/data/estimator')
import options_sim as S, replay as R
N = 200
orig_use = S.use
count = {"speed": 0}
def counting_use(st, item):
    ok = orig_use(st, item)
    if ok and item == "speed":
        count["speed"] += 1
    return ok
S.use = counting_use
names = {25: "m26 Nar (trap)", 32: "m26 crowd", 36: "m28 band", 43: "m32 Nar"}
for idx in (25, 32, 36, 43):
    ep = json.load(open(f"{R.REPLAYS}/ep{idx}.json")); p, team, arr = R.start_state(ep, S.DIVE04)
    # speed potions drunk per rollout, and XP/gold excluding speed, per option (price-independent parts)
    res = {}
    for o in ("rules", "speed"):
        drunk, xp, gold_ex = [], [], []
        for i in range(N):
            count["speed"] = 0
            S.PRICE["speed"] = 0
            r = S.rollout(p, team, S.OPTIONS[o], seed=i, arrivals=arr)
            drunk.append(count["speed"]); xp.append(r["xp"]); gold_ex.append(r["spent"])
        res[o] = (drunk, xp, gold_ex)
    d_r, d_s = statistics.mean(res["rules"][0]), statistics.mean(res["speed"][0])
    base = [(a - b) - (c - d) for a, b, c, d in zip(res["speed"][1], res["rules"][1], res["speed"][2], res["rules"][2])]
    extra = d_s - d_r
    g0 = statistics.mean(base)
    gains = {pr: round(g0 - extra * pr) for pr in (200, 383, 400, 800, 1200, 1600)}
    be = round(g0 / extra) if extra > 0 else None
    print(f"{names[idx]:16s} Speed drunk per rollout: rules {d_r:.2f}, speed-first {d_s:.2f} (extra {extra:.2f}); "
          f"gain at price 0: {g0:.0f}; gain by price {gains}; break-even {be} g (at XP_PER_GOLD 1; scales as 1/XP_PER_GOLD)")

print("\nBUYING: value of carrying Speed = (speed-first with Speed in the pack) - (rules with NO Speed), XP net of other gold;"
      " minus potions drunk x price")
for idx in (25, 32, 36, 43):
    ep = json.load(open(f"{R.REPLAYS}/ep{idx}.json")); p, team, arr = R.start_state(ep, S.DIVE04)
    p0 = dict(p); p0["inv"] = dict(p["inv"], speed=0)
    S.PRICE["speed"] = 0
    a, b, drunk = [], [], []
    for i in range(N):
        count["speed"] = 0
        ra = S.rollout(p, team, S.OPTIONS["speed"], seed=i, arrivals=arr); drunk.append(count["speed"])
        rb = S.rollout(p0, team, S.OPTIONS["rules"], seed=i, arrivals=arr)
        a.append(ra["xp"] - ra["spent"]); b.append(rb["xp"] - rb["spent"])
    g0 = statistics.mean(x - y for x, y in zip(a, b)); k = statistics.mean(drunk)
    nearA = None
    print(f"{names[idx]:16s} potions drunk {k:.2f}; value at price 0: {g0:.0f}; at 383: {g0 - k * 383:.0f}; "
          f"break-even {g0 / k:.0f} g")
