#!/usr/bin/env python3
"""Calibrate options_sim.py on logged emergencies (replay files, studies/2026-10-25-replay/replays/ep<idx>.json).

For each episode:
  forced   the LOGGED actions replayed at their game time (each action's effect time, else its send time, converted to
           blocks); between actions we auto-retaliate on an adjacent monster (dungeon.c auto-retaliate), as the game does.
           Logged arrivals enter at their time; logged summons are NOT injected (the simulator's own summons stand in).
           The simulated HP path is compared with the logged one: HP lost from t0 to the logged lowest point, and lowest HP.
  rules    the base policy from the same start (what the current rules would do in this model).
  options  the estimator's ranking from the start state.
Clock: one block = TICK_S wall seconds x 1/time_factor (world.py TICK_S = 0.625
MAX_ADJ = 3            # real fights: ~2 attackers at once, max 3 (calib_adj.py), whatever the open squares; the bubble's factor 0.2 -> 3.1 s).

usage: replay.py [--n 200] [IDX ...]      -> replay_calibration.csv next to this script, and a table on stdout"""
import argparse, csv, glob, json, os, re, statistics, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import options_sim as S  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPLAYS = "/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-replay/replays"
TICK_S = 0.625
MAX_ADJ = 3            # real fights: ~2 attackers at once, max 3 (calib_adj.py), whatever the open squares
ITEM = dict(phase="phase", tele="tele", staff_tele="staff", wor="wor", ccw="ccw", csw="csw", clw="clw", speed="speed",
            berserk="berserk", hero="hero")


def blocks_between(ep, t_a, t_b):
    """Game blocks elapsed between wall times t_a < t_b (bubble_factor: 0.2 in the HP bubble from m25, else 1)."""
    factor_at = bubble_factor(ep)
    n, t, step = 0.0, t_a, 0.25
    while t < t_b:
        n += min(step, t_b - t) * factor_at(t) / TICK_S
        t += step
    return n


def start_state(ep, base):
    pl = ep["player"]
    p = dict(base)
    p.update(blows=3, dice="1d6", todam=7, tohit=5, ac=56)    # Dive04's Spear (1d6) (+5,+7) profile (10-23); m32 used a Scimitar
    p["hp"], p["mhp"] = pl["hp"], pl["mhp"] or base["mhp"]
    if pl.get("clvl"):
        p["clvl"] = pl["clvl"]
    if pl.get("ac"):
        p["ac"] = pl["ac"]
    p["depth"] = ep["depth_ft"] // 50
    p["max_adj"] = MAX_ADJ
    p["free_action"] = bool(pl.get("free_action"))
    st = pl.get("status") or {}
    for k in ("slow", "fast", "hero", "berserk", "blind", "confused", "afraid", "paralyzed"):
        if st.get(k):
            p[k] = 5
    if ep.get("inventory"):                                   # only what the log shows
        inv = {k: 0 for k in base["inv"]}
        for k, v in ep["inventory"].items():
            if k in ITEM:
                inv[ITEM[k]] = v or 0
    else:                                                     # unknown: a conservative kit of that era
        inv = dict(base["inv"], tele=0, staff=0, speed=0, berserk=0, hero=0, wor=1)
    p["inv"] = inv
    y0, x0 = pl["pos"]
    team = [(m["name"], max(1, S.adist(m["y"] - y0, m["x"] - x0))) for m in ep["monsters_t0"] if m["name"] in S.RACES]
    arrivals = []
    for a in ep.get("arrivals") or []:
        if a["name"] in S.RACES and a["t"] > ep["t0"]:
            d = a.get("dist") or 5
            arrivals.append((int(blocks_between(ep, ep["t0"], a["t"])), a["name"], max(1, d)))
    return p, team, arrivals


def forced_actor(ep):
    sched = []
    for a in ep.get("actions") or []:
        w = a.get("what")
        t = a.get("t_effect") or a.get("t")
        if t is None or t < ep["t0"] or w in (None, "walk", "run", "rest", "other", "melee"):
            continue
        if w == "stairs":
            w = "take_stairs"
        elif w in ITEM:
            w = ITEM[w]
        else:
            continue
        sched.append((blocks_between(ep, ep["t0"], t), w))
    sched.sort()
    ours = sorted(blocks_between(ep, ep["t0"], m["t"]) for m in ep.get("melee_by_us") or [] if m["t"] >= ep["t0"])

    def act(st, plan):
        if sched and sched[0][0] <= st.block + 1:
            _, w = sched.pop(0)
            if w == "take_stairs":
                st.escaped = "stairs"
            else:
                S.use(st, w)
            return
        b = st.block
        if any(b - 0.5 <= u <= b + 1.5 for u in ours):     # we attacked around now in the log
            S.attack(st)
    return act, sched


def logged(ep):
    hs = [(t, h) for t, h, *_ in ep.get("hp_series") or [] if t >= ep["t0"]]
    if not hs:
        return None
    t_low, low = min(hs, key=lambda x: x[1])
    return dict(low=low, t_low=t_low, blocks_to_low=blocks_between(ep, ep["t0"], t_low),
                blocks_total=blocks_between(ep, ep["t0"], ep["t_end"]))


def run(ep, n):
    p, team, arrivals = start_state(ep, S.DIVE04)
    lg = logged(ep)
    if not team or not lg:
        return None
    horizon = max(5, int(lg["blocks_total"]) + 2)
    lows, at_low = [], []
    for i in range(n):
        act, _ = forced_actor(ep)
        r = S.rollout(p, team, [], seed=i, horizon=horizon, arrivals=arrivals, trace=True, actor=act)
        path = r["path"] or [p["hp"]]
        lows.append(min(path + [r["end_hp"]]))
        k = min(len(path) - 1, int(lg["blocks_to_low"]))
        at_low.append(path[k] if path else p["hp"])
    rules = [S.rollout(p, team, [], seed=i, horizon=horizon, arrivals=arrivals) for i in range(n)]
    return dict(idx=ep["idx"], mission=ep["mission"], hp0=p["hp"], mhp=p["mhp"], n_t0=len(team), n_arr=len(arrivals),
                blocks_total=round(lg["blocks_total"], 1), real_low=lg["low"], real_loss=p["hp"] - lg["low"],
                sim_loss_at_t_low_mean=round(p["hp"] - statistics.mean(at_low)),
                sim_low_p10=S.q(lows, 0.1), sim_low_p50=S.q(lows, 0.5), sim_low_p90=S.q(lows, 0.9),
                rules_low_p50=S.q([r["low"] for r in rules], 0.5),
                rules_near_death=round(sum(r["dead"] or r["low"] <= 0.1 * p["mhp"] for r in rules) / n, 3))


# ---------------- level 1: the damage model alone, on the logged geometry ----------------
def bubble_factor(ep):
    """Game-time factor at wall time t: 0.2 in the HP bubble (missions m25+, HP <= 50%), else 1.0. The logged
    time_factor can carry a stale measured rate (a rest's 9x) into a fight, so it is not used."""
    m = int(ep["mission"].lstrip("m"))
    hs = sorted((t, h, mh) for t, h, mh, *_ in [(*x, 0)[:3] if len(x) < 3 else x for x in ep.get("hp_series") or []])
    def f(t):
        if m < 25:
            return 1.0
        h = mh = None
        for tt, hh, mm in hs:
            if tt <= t:
                h, mh = hh, mm or ep["player"]["mhp"]
            else:
                break
        return 0.2 if h is not None and mh and h <= 0.5 * mh else 1.0
    return f


def per_block(r, ac, hp_frac=1.0):
    """Expected (melee-or-spell damage per block when adjacent, spell damage per block at range) of race row r."""
    m = S.Mon(r, 1, ac, S.random.Random(0))
    sx, pct = m.sx, m.pct
    melee = 0.0
    for eff, n, s, ph in m.blows:
        d = n * (s + 1) / 2
        if eff in ("HURT", "SHATTER"):
            d -= d * min(ac, 150) / 250
        melee += ph * d
    hp = (m.hpmax if "FORCE_MAXHP" in m.flags else int(float(r["hp_avg"]))) * hp_frac
    sp = [S.spell_dmg(x, m.rl, int(hp))[0] for x in m.spells] if m.spells else []
    spell = sum(sp) / len(sp) if sp else 0.0
    if "NEVER_BLOW" in m.flags or not m.blows:
        adj_rate = sx * pct * spell
    else:
        adj_rate = sx * (pct * spell + (1 - pct) * melee) / (pct + 2 * (1 - pct))
    return adj_rate, sx * pct * spell


MELEE_RE = re.compile(r"^(?:The |Your )?(.+?) (?:hits|bites|claws|stings|touches|kicks|butts|crushes|engulfs|crawls on|"
                      r"gazes at|wails at|spits on|drools on|begs|insults|misses) you")
HEALS = dict(ccw=27, csw=22, clw=15, berserk=30, hero=10)


def level1(ep, ac=56):
    f = bubble_factor(ep)
    y0, x0 = ep["player"]["pos"]
    pos = sorted(ep.get("pos_series") or [])
    def where(t):
        p = (y0, x0)
        for tt, y, x in pos:
            if tt <= t:
                p = (y, x)
            else:
                break
        return p
    ms = sorted((t, mm) for t, mm in ep.get("mons_series") or [] if t >= ep["t0"] - 10)
    hs = [(t, h) for t, h, *_ in ep.get("hp_series") or [] if t >= ep["t0"]]
    if not ms or not hs:
        return None
    t_low, low = min(hs, key=lambda x: x[1])
    hp0 = ep["player"]["hp"]
    melee_at = {}                                             # name -> times of its melee messages ("The X bites you.")
    for h in ep.get("hostile_msgs") or []:
        mm = MELEE_RE.match(h["text"])
        if mm:
            melee_at.setdefault(mm.group(1), []).append(h["t"])
    loss, t, step = 0.0, ep["t0"], 0.25
    k = 0
    cur = []
    adj_blocks = 0.0
    while t < t_low:
        while k < len(ms) and ms[k][0] <= t:
            cur = ms[k][1]; k += 1
        py, px = where(t)
        blocks = step * f(t) / TICK_S
        swinging = {n for n, ts in melee_at.items() if any(t - 1.5 <= u <= t for u in ts)}
        seen = set()
        for y, x, name in list(cur) + [(py, px, n) for n in swinging if n not in {c[2] for c in cur}]:
            r = S.RACES.get(name)
            if not r or (name, y, x) in seen:
                continue
            seen.add((name, y, x))
            d = 1 if name in swinging else S.adist(y - py, x - px)
            a, rng = per_block(r, ac)
            if d <= 1:
                loss += a * blocks; adj_blocks += blocks
            elif d <= 18:
                loss += rng * blocks
        t += step
    heal = sum(HEALS.get(a.get("what"), 0) for a in ep.get("actions") or []
               if ep["t0"] <= (a.get("t_effect") or a.get("t") or 0) <= t_low)
    return dict(idx=ep["idx"], mission=ep["mission"], real_loss=hp0 - low, pred_loss=round(loss), heals=heal,
                pred_low=round(hp0 - loss + heal), real_low=low, ratio=round((hp0 - low + heal) / loss, 2) if loss else None,
                adj_blocks=round(adj_blocks, 1), unseen_hits=len(ep.get("unseen_hits") or []))


def level1_all():
    rows = []
    for fn in sorted(glob.glob(f"{REPLAYS}/ep*.json"), key=lambda f: int(f.split("ep")[-1].split(".")[0])):
        r = level1(json.load(open(fn)))
        if r:
            rows.append(r); print(r)
    rs = [r["ratio"] for r in rows if r["ratio"]]
    print("observed (loss + heals) / predicted loss: median", statistics.median(rs), "range", min(rs), max(rs))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("idx", nargs="*")
    o = ap.parse_args()
    files = sorted(glob.glob(f"{REPLAYS}/ep*.json"), key=lambda f: int(f.split("ep")[-1].split(".")[0]))
    rows = []
    for f in files:
        ep = json.load(open(f))
        if o.idx and str(ep["idx"]) not in o.idx:
            continue
        r = run(ep, o.n)
        if r:
            rows.append(r)
            print(r)
    if rows:
        with open(os.path.join(HERE, "replay_calibration.csv"), "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
        inside = sum(r["sim_low_p10"] <= r["real_low"] <= r["sim_low_p90"] for r in rows)
        print(f"\n{len(rows)} episodes; real lowest HP inside the simulated p10-p90 band in {inside}")
