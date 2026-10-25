#!/usr/bin/env python3
"""Decompose the melee model against logged messages (replay files): per monster race, (a) observed hit rate of its blows
vs the model's p_hit at our AC, (b) predicted damage from the logged HITS (mean dice, HURT reduced by AC) + logged spells,
compared with the real HP loss + heals, (c) melee rounds per block while it was swinging vs the model's rate.
A round = consecutive melee messages from one monster at one timestamp; message i of a round = blow i.

usage: calib_blows.py [--ac 56]"""
import argparse, collections, glob, json, os, re, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import options_sim as S  # noqa: E402
import replay as R  # noqa: E402

HIT = re.compile(r"^(?:The )?(.+?) (hits|bites|claws|stings|touches|kicks|butts|crushes|engulfs|crawls on|gazes at|"
                 r"wails at|spits on|drools on|begs|insults) you")
MISS = re.compile(r"^(?:The )?(.+?) misses you")
CAST = re.compile(r"^(?:The )?(.+?) (breathes|casts|fires|mumbles|points|gestures)(.*)")

ap = argparse.ArgumentParser(); ap.add_argument("--ac", type=int, default=56); o = ap.parse_args()
per_race = collections.defaultdict(lambda: dict(hits=0, misses=0, p_model=[], rounds=[], dmg=0.0))
ep_rows = []
for fn in sorted(glob.glob(f"{R.REPLAYS}/ep*.json"), key=lambda f: int(f.split("ep")[-1].split(".")[0])):
    ep = json.load(open(fn))
    hs = [(t, h) for t, h, *_ in ep.get("hp_series") or [] if t >= ep["t0"]]
    t_low, low = min(hs, key=lambda x: x[1])
    ac = ep["player"].get("ac") or o.ac
    rounds = collections.OrderedDict()
    pred = 0.0
    unseen = 0
    for h in ep.get("hostile_msgs") or []:
        if not (ep["t0"] <= h["t"] <= t_low):
            continue
        tx = h["text"]
        mh, mm = HIT.match(tx), MISS.match(tx)
        if mh or mm:
            name = (mh or mm).group(1)
            if name in ("It", "Something"):
                unseen += 1
                continue
            rounds.setdefault((name, round(h["t"], 1)), []).append(bool(mh))
            continue
        mc = CAST.match(tx)
        if mc and mc.group(1) in S.RACES:
            r = S.RACES[mc.group(1)]
            sp = [x for x in r["spells"].split("|") if x.startswith(S.RANGED)] if r["spells"] else []
            if sp and mc.group(2) in ("breathes", "casts", "fires"):
                m = S.Mon(r, 1, ac, S.random.Random(0))
                pred += sum(S.spell_dmg(x, m.rl, int(float(r["hp_avg"])))[0] for x in sp) / len(sp)
    for (name, t), seq in rounds.items():
        r = S.RACES.get(name)
        if not r:
            continue
        m = S.Mon(r, 1, ac, S.random.Random(0))
        d = per_race[name]
        for i, hit in enumerate(seq):
            if i >= len(m.blows):
                break
            eff, n, s, ph = m.blows[i]
            d["p_model"].append(ph)
            if hit:
                d["hits"] += 1
                dm = n * (s + 1) / 2
                if eff in ("HURT", "SHATTER"):
                    dm -= dm * min(ac, 150) / 250
                pred += dm; d["dmg"] += dm
            else:
                d["misses"] += 1
        d["rounds"].append(t)
    heal = sum(R.HEALS.get(a.get("what"), 0) for a in ep.get("actions") or []
               if ep["t0"] <= (a.get("t_effect") or a.get("t") or 0) <= t_low)
    real = ep["player"]["hp"] - low + heal
    ep_rows.append(dict(idx=ep["idx"], real_loss_plus_heals=real, pred_from_messages=round(pred), unseen_msgs=unseen,
                        ratio=round(real / pred, 2) if pred else None))
for r in ep_rows:
    print(r)
rs = [r["ratio"] for r in ep_rows if r["ratio"]]
print("episodes: real/pred median", statistics.median(rs), "IQR", sorted(rs)[len(rs) // 4], sorted(rs)[3 * len(rs) // 4])
H = sum(d["hits"] for d in per_race.values()); M = sum(d["misses"] for d in per_race.values())
P = [p for d in per_race.values() for p in d["p_model"]]
print(f"blows: observed hit rate {H / (H + M):.3f} (n={H + M}); model mean p_hit {statistics.mean(P):.3f}")
for name, d in sorted(per_race.items(), key=lambda kv: -(kv[1]["hits"] + kv[1]["misses"]))[:15]:
    n = d["hits"] + d["misses"]
    print(f"  {name:24s} blows {n:4d} hit {d['hits'] / n:.2f} model {statistics.mean(d['p_model']):.2f}")

# (c) round interval while swinging continuously: blocks between consecutive rounds of the same race (gap < 4 s wall)
iv = collections.defaultdict(list)
for fn in glob.glob(f"{R.REPLAYS}/ep*.json"):
    ep = json.load(open(fn))
    f = R.bubble_factor(ep)
    ts = collections.defaultdict(list)
    for h in ep.get("hostile_msgs") or []:
        m = HIT.match(h["text"]) or MISS.match(h["text"])
        if m and m.group(1) in S.RACES:
            t = round(h["t"], 1)
            if not ts[m.group(1)] or t - ts[m.group(1)][-1] > 0.15:
                ts[m.group(1)].append(t)
    for name, tl in ts.items():
        for a, b in zip(tl, tl[1:]):
            if b - a < 4:
                iv[name].append((b - a) * f(a) / R.TICK_S)
print("\nround interval in blocks (median, n) vs model 2/speed_x (recoil), for races with >= 6 intervals:")
allr = []
for name, v in sorted(iv.items(), key=lambda kv: -len(kv[1])):
    if len(v) < 6:
        continue
    sx = S.ENERGY.get(int(S.RACES[name]["speed"]), 1000) / 1000
    med = statistics.median(v); allr.append(med / (2 / sx))
    print(f"  {name:24s} n={len(v):3d} median {med:.2f} blocks  model {2 / sx:.2f}  ratio {med / (2 / sx):.2f}")
print("median ratio observed/model interval:", round(statistics.median(allr), 2))
