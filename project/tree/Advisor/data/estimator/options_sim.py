#!/usr/bin/env python3
"""Prototype danger-time option estimator: Monte Carlo rollouts of a fight against a GROUP, one per option.

An option is a short plan (a first move plus a fixed continuation policy, the "base policy" = the Pilot's rules as of 10-25).
Each option is played out N times from the same state; options are ranked by P(death), then mean HP at the end, then
consumables spent (gold). This is Bertsekas' rollout algorithm: with an accurate model, choosing the best option and
continuing with the base policy can't do worse than the base policy alone.

Mechanics reused from fight_sim.py / build_monsters.py (player hit chance, monster blow hit chance, HURT reduction by AC,
MONSTER_RECOIL, breath at current HP, spell_dmg). Time: one "block" = one player turn at normal speed; energy per block =
extract_energy[speed]/1000 for the player and each monster (char_extract_energy.csv); Speed potion = +10 (2x energy).
Geometry is one number per monster: its distance in moves. Each monster action: adjacent -> spell (spell_pct) or melee
round (costs 2 actions, recoil); not adjacent -> ranged spell (spell_pct, if it can see us) or one step closer.

From E2 (studies/2026-10-25-estimator): cure amounts, Hero/Berserk to-hit/AC/mhp, confusion blocks scrolls (cured by potions),
confusion blows (no save), spells need range <= 18. STILL PLACEHOLDERS: Phase landing distance
relative to the crowd, P(a caster sees us after a Phase), Teleport follow-up risk, summons (ignored), erratic movers
(RAND_25/50 treated as straight), status effects (ignored), corridors (ignored: every monster can reach us).

usage: options_sim.py [--n 300] [--scenario m30|a7|bullroarer] [--hp 303]"""
import argparse, csv, os, random, statistics, sys, time

sys.path.insert(0, "/projectnb/jbrcs/mangband/Advisor/data/rulebook")
from build_monsters import POWER, spell_dmg, ENERGY, dice  # noqa: E402

MON = "/projectnb/jbrcs/mangband/Advisor/data/monsters/monsters.csv"
RACES = {r["name"]: r for r in csv.DictReader(open(MON))}

# --- placeholders (see docstring) ---
HEAL = dict(clw=(15, 15), csw=(20, 24), ccw=(25, 29))   # flat HP (use-obj.c:483-510); all three cure confusion (CLW partly)
PRICE = dict(clw=20, csw=40, ccw=100, phase=15, tele=40, wor=150, speed=75, berserk=100, hero=35)
PHASE_DIST = (5, 10)                          # new distance of each monster after our Phase Door
P_SEE_AFTER_PHASE = 0.5                       # chance a caster still has LOS after our Phase
RANGED = {"BR_", "BO_", "BA_", "ARROW", "MISSILE", "MIND_BLAST", "BRAIN_SMASH", "CAUSE"}


def is_ranged(sp):
    return any(sp.startswith(p) for p in RANGED)


class Mon:
    __slots__ = ("r", "hp", "hpmax", "dist", "energy", "sx", "pct", "spells", "blows", "rl", "ac", "flags", "seen")

    def __init__(self, r, dist, ac_player):
        self.r = r
        self.flags = set(r["flags"].split("|")) if r["flags"] else set()
        n, s = dice(r["hp_dice"])
        self.hpmax = n * s if "FORCE_MAXHP" in self.flags else sum(random.randint(1, s) for _ in range(n))
        self.hp = self.hpmax
        self.dist = dist
        self.energy = random.random()
        self.sx = ENERGY.get(int(r["speed"]), 1000) / 1000
        f = int(r["spell_freq"]) if r["spell_freq"] else 0
        self.pct = (100 // f) / 100 if f else 0.0
        self.spells = [s for s in r["spells"].split("|") if s] if r["spells"] else []
        self.rl = max(1, int(r["level"]))
        self.ac = int(r["ac"])
        self.seen = True
        self.blows = []
        for b in (r["blow1"], r["blow2"], r["blow3"], r["blow4"]):
            if not b:
                continue
            p = b.split(":")
            eff = p[1] if len(p) > 1 else ""
            if not eff:
                continue
            bn, bs = dice(p[2] if len(p) > 2 else "")
            i = POWER.get(eff, 0) + 3 * self.rl
            self.blows.append((eff, bn, bs, 0.05 + 0.90 * max(0, i - (3 * ac_player) // 4) / i))


class State:
    def __init__(self, p, mons):
        self.p = dict(p)
        self.inv = dict(p["inv"])
        self.mons = mons
        self.fast = p.get("fast", 0)
        self.berserk = p.get("berserk", 0)
        self.hero = p.get("hero", 0)
        self.recall = p.get("recall")          # blocks left, or None
        self.stairs = p.get("stairs")          # moves to stairs, or None
        self.spent = 0
        self.escaped = None
        self.lowest = p["hp"]
        self.confused = p.get("confused", 0)


def roll(n, s):
    return sum(random.randint(1, s) for _ in range(n)) if n and s else 0


# ---------------- player actions ----------------
def attack(st):
    adj = [m for m in st.mons if m.dist <= 1]
    if not adj:
        return False
    m = min(adj, key=lambda m: m.hp)                       # quickest kill first
    p = st.p
    tohit = p["tohit"] + (24 if st.berserk else 0) + (12 if st.hero else 0)   # xtra1.c:2709-2722
    chance = 82 + 45 * p["clvl"] // 10 + 3 * tohit
    pn, ps = dice(p["dice"])
    for _ in range(p["blows"]):
        k = random.randrange(100)
        hit = k < 5 if k < 10 else random.randrange(chance) >= m.ac * 3 // 4
        if hit:
            m.hp -= roll(pn, ps) + p["todam"]
    if m.hp <= 0:
        st.mons.remove(m)
    return True


def use(st, item):
    if st.inv.get(item, 0) <= 0:
        return False
    st.inv[item] -= 1
    st.spent += PRICE[item]
    p = st.p
    if item in ("phase", "tele", "wor") and st.confused:
        st.inv[item] += 1                                     # "You are too confused!": refused, no turn spent
        st.spent -= PRICE[item]
        return False
    if item in HEAL:
        p["hp"] = min(p["mhp"], p["hp"] + random.randint(*HEAL[item]))
        st.confused = 0
    elif item == "speed":
        st.fast = random.randint(1, 25) + 15
    elif item == "berserk":                                   # heal 30, then mhp +30 with chp rescaled (xtra1.c:2019)
        p["hp"] = min(p["mhp"], p["hp"] + 30)
        if not st.berserk:
            p["hp"] = p["hp"] * (p["mhp"] + 30) // p["mhp"]; p["mhp"] += 30; p["ac"] -= 10
        st.berserk = random.randint(1, 25) + 25
    elif item == "hero":
        p["hp"] = min(p["mhp"], p["hp"] + 10)
        if not st.hero:
            p["hp"] = p["hp"] * (p["mhp"] + 10) // p["mhp"]; p["mhp"] += 10
        st.hero = random.randint(1, 25) + 25
    elif item == "phase":
        for m in st.mons:
            m.dist = random.randint(*PHASE_DIST)
            m.seen = random.random() < P_SEE_AFTER_PHASE
        if st.stairs is not None:
            st.stairs = max(1, st.stairs + random.randint(-10, 10))
    elif item == "tele":
        st.escaped = "teleport"
    elif item == "wor":
        st.recall = None if st.recall is not None else random.randint(15, 34)   # a 2nd read cancels
    return True


def base_policy(st):
    """The Pilot's emergency rules, simplified: cure below 50%, phase when the adjacent worst turn could kill,
    Speed first when in a hard fight, otherwise fight (or wait for them to come)."""
    p = st.p
    adj = [m for m in st.mons if m.dist <= 1]
    worst = sum(sum(n * s for _, n, s, _ in m.blows) for m in adj)
    if adj and worst >= 0.9 * p["hp"]:
        if use(st, "tele") or use(st, "phase"):
            return
    if p["hp"] < 0.5 * p["mhp"]:
        for c in ("ccw", "csw", "clw"):
            if use(st, c):
                return
    if adj and not st.fast and len(adj) >= 2 and use(st, "speed"):
        return
    if st.stairs is not None and st.stairs <= 1 and p["hp"] < 0.5 * p["mhp"]:
        st.escaped = "stairs"
        return
    if not attack(st):
        pass                                                 # wait: they come to us


OPTIONS = {
    "rules":        [],
    "fight":        ["fight"],
    "speed":        ["speed"],
    "berserk":      ["berserk"],
    "speed+berserk": ["speed", "berserk"],
    "ccw":          ["ccw"],
    "phase":        ["phase"],
    "phase+ccw":    ["phase", "ccw"],
    "teleport":     ["tele"],
    "recall+phase": ["wor", "phase"],
    "stairs":       ["stairs"],
}


def player_act(st, plan):
    if plan:
        a = plan.pop(0)
        if a == "fight":
            attack(st)
            return
        if a == "stairs":
            if st.stairs is None:
                base_policy(st)
                return
            st.stairs -= 1                                    # a step toward the stairs; monsters follow
            for m in st.mons:
                if m.dist > 1:
                    m.dist = max(1, m.dist)                   # adjacent ones stay adjacent (they follow)
            if st.stairs <= 0:
                st.escaped = "stairs"
            else:
                plan.insert(0, "stairs")
            return
        if not use(st, a):
            base_policy(st)
        return
    base_policy(st)


# ---------------- monsters ----------------
def monster_act(st, m):
    p = st.p
    if m.dist <= 1:
        if m.spells and random.random() < m.pct:
            cast(st, m, random.choice(m.spells))
            return 1
        if m.blows and "NEVER_BLOW" not in m.flags:
            for eff, n, s, ph in m.blows:
                if random.random() < ph:
                    d = roll(n, s)
                    if eff in ("HURT", "SHATTER"):
                        d -= d * min(p["ac"], 150) // 250
                    elif eff == "CONFUSE" and not p.get("res_conf"):
                        st.confused += 3 + random.randint(1, m.rl)
                    p["hp"] -= d
            return 2                                          # MONSTER_RECOIL
        return 1
    if m.spells and m.seen and m.dist <= 18 and random.random() < m.pct:
        sp = random.choice(m.spells)
        if is_ranged(sp) or sp in ("BLINK", "HEAL", "TPORT", "HASTE"):
            cast(st, m, sp)
            return 1
    if "NEVER_MOVE" not in m.flags:
        if m.dist == 2 and sum(1 for o in st.mons if o.dist <= 1) >= st.p.get("max_adj", 8):
            return 1                                          # no free square next to us: wait behind
        m.dist -= 1
        if m.dist <= 1:
            m.seen = True
    return 1


def cast(st, m, sp):
    if sp == "BLINK":
        m.dist = max(m.dist, random.randint(2, 10))
    elif sp == "HEAL":
        m.hp = min(m.hpmax, m.hp + 6 * m.rl)
    elif sp in ("TPORT", "TELE_SELF"):
        st.mons.remove(m) if m in st.mons else None
    elif sp == "HASTE":
        m.sx = min(m.sx * 2, 3.0)
    else:
        st.p["hp"] -= spell_dmg(sp, m.rl, m.hp)[0] if not sp.startswith("BR_") else spell_dmg(sp, m.rl, m.hp)[0]


# ---------------- rollout ----------------
def rollout(p, team, option, horizon=40):
    """team: list of (race name, distance). Returns (dead, end_hp, spent, escaped, turns)."""
    mons = [Mon(RACES[n], d, p["ac"]) for n, d in team]
    cap = p.get("max_adj", 8)
    for m in sorted(mons, key=lambda m: m.dist)[cap:]:
        m.dist = max(m.dist, 2)
    st = State(p, mons)
    plan = list(OPTIONS[option])
    pe = 0.0
    for blk in range(horizon):
        pe += 2.0 if st.fast else 1.0
        while pe >= 1 and st.escaped is None:
            pe -= 1
            player_act(st, plan)
        if st.escaped or not st.mons:
            break
        for m in list(st.mons):
            m.energy += m.sx
            while m.energy >= 1 and m in st.mons:
                m.energy -= monster_act(st, m)
            if st.p["hp"] <= 0:
                return True, st.p["hp"], st.spent, None, blk
        st.lowest = min(st.lowest, st.p["hp"])
        if st.berserk == 1:
            st.p["ac"] += 10
        for t in ("fast", "berserk", "hero", "confused"):
            setattr(st, t, max(0, getattr(st, t) - 1))
        if st.recall is not None:
            st.recall -= 1
            if st.recall <= 0:
                st.escaped = "recall"
    return False, st.p["hp"], st.spent, st.escaped or ("cleared" if not st.mons else None), blk


def evaluate(p, team, n=300, options=None):
    out = []
    for o in options or OPTIONS:
        res = [rollout(p, team, o) for _ in range(n)]
        dead = sum(r[0] for r in res) / n
        hp = statistics.mean(max(0, r[1]) for r in res)
        spent = statistics.mean(r[2] for r in res)
        unresolved = sum(r[3] is None and not r[0] for r in res) / n
        out.append(dict(option=o, p_death=round(dead, 3), mean_end_hp=round(hp), gold=round(spent),
                        unresolved=round(unresolved, 2)))
    out.sort(key=lambda r: (r["p_death"], -r["mean_end_hp"], r["gold"]))
    return out


DIVE04 = dict(hp=303, mhp=333, ac=60, clvl=25, blows=3, dice="4d4", todam=10, tohit=8, stairs=None,
              inv=dict(ccw=5, csw=2, clw=0, phase=10, tele=2, wor=2, speed=2, berserk=2, hero=2))
SCENARIOS = {
    # m30 06:43, 650 ft (from the Architect's memo; distances guessed)
    "m30": [("Umber hulk", 1), ("Fire hound", 1), ("Fire hound", 2), ("Energy hound", 2), ("Energy hound", 3),
            ("Wolf", 1), ("Griffon", 3), ("Yeti", 4), ("Druid", 5), ("Copperhead snake", 2), ("Black harpy", 3)],
    "a7": [("Hill giant", 1)],
    "bullroarer": [("Bullroarer the Hobbit", 1)],
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--scenario", default="m30")
    ap.add_argument("--hp", type=int)
    ap.add_argument("--stairs", type=int)
    ap.add_argument("--max-adj", type=int, default=8, help="squares next to us a monster can stand on (corridor 2, room 8)")
    o = ap.parse_args()
    random.seed(1)
    p = dict(DIVE04)
    if o.hp:
        p["hp"] = o.hp
    if o.stairs is not None:
        p["stairs"] = o.stairs
    p["max_adj"] = o.max_adj
    t0 = time.time()
    rows = evaluate(p, SCENARIOS[o.scenario], o.n)
    dt = time.time() - t0
    for r in rows:
        print(r)
    print(f"{len(rows)} options x {o.n} rollouts in {dt:.2f} s ({1000 * dt / len(rows) / o.n:.2f} ms per rollout)")
