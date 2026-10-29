#!/usr/bin/env python3
"""Danger-time option estimator (prototype v2): Monte Carlo rollouts of a fight against a GROUP, one batch per option.

An option is a short plan (first moves) continued by a base policy (the Pilot's emergency rules as of 10-25 incl. the four
fixes from memo 2026-10-25-estimator). Each option is played out N times from the same state with common random numbers
(rollout i uses seed i for every option); options rank by P(HP <= 10%), then the 10th-percentile end HP, then gold.
This is Bertsekas' rollout algorithm: with an accurate model the chosen option can't do worse than the base policy.

Time: one "block" = one player turn at normal speed (timers count blocks). Energy per block = extract_energy[speed]/1000
(char_extract_energy.csv) for the player (110 +10 hasted -10 slowed) and each monster. Geometry: one distance per monster
(Angband distance, moves); a monster action is: adjacent -> a spell (100/freq %) or a melee round (2 actions: recoil);
not adjacent -> a spell if it sees us and dist <= 18, else one step closer (no flow: straight walkers).

Mechanics (studies/2026-10-25-estimator E2, code-checked where marked there): cures heal 15 / 20-24 / 25-29 and cure
blind+confusion; Hero to-hit +12, max HP +10; Berserk to-hit +24, AC -10, max HP +30 (current HP rescaled); both stop fear;
scrolls refused when blind or confused (no turn spent); blind halves our hit chance; afraid: no melee; paralysed: no action;
slowed: -10 speed. Monster spells: BLIND 12+d4, CONF 4+d4, SCARE 4+d4, SLOW 4+d4, HOLD 4+d4 (saving throw; Free Action
stops HOLD/SLOW); blows: CONFUSE 3+d(rlev) no save, BLIND 10+d(rlev), TERRIFY 3+d(rlev) (save), PARALYZE 3+d(rlev) (FA,
save). Summons: count per spell type (melee2.c:1704-1975), level (depth + rlev)/2 + 5, drawn by rarity from the matching
races (no best-of-2 boost), placed 1-3 squares away.
Resists (26f): p flags res_acid/elec/fire/cold/pois (1/3), res_neth/chaos/shard/nexus/disen (x6/(d6+6)),
res_sound/conf (x5/(d6+6)), res_lite/dark (x4/(d6+6)), res_blind; unresisted conf/chaos/water confuse, lite/dark blind;
cause wounds / mind blast negated by a saving throw.
Placeholders: Phase landing (each monster ends 5-10 away; P_SEE_AFTER_PHASE), Teleport = escape, summon placement success
P_SUMMON_PLACE, our saving throw SAVE, erratic movers treated as straight, no walls/corridors except max_adj.

usage: options_sim.py [--n 300] [--scenario m30|a7|bullroarer|druid] [--hp 303] [--max-adj 8] [--stairs D]"""
import argparse, csv, functools, random, statistics, sys, time

sys.path.insert(0, "/projectnb/jbrcs/mangband/Advisor/data/rulebook")
from build_monsters import POWER, spell_dmg, ENERGY, dice as _dice  # noqa: E402

dice = functools.lru_cache(maxsize=None)(_dice)

MON = "/projectnb/jbrcs/mangband/Advisor/data/monsters/monsters.csv"
RACES = {r["name"]: r for r in csv.DictReader(open(MON))}

HEAL = dict(clw=(15, 15), csw=(20, 24), ccw=(25, 29))      # flat HP (use-obj.c:483-510)
FOOD = dict(clw=50, csw=100, ccw=100)                       # nourishment per potion (object.txt pval); optional p["food"]
FOOD_LEVEL = {"Weak": (500, 999), "Hungry": (1000, 1999), "Fed": (2000, 9999), "Full": (10000, 14999),
              "Gorged": (15000, 15000)}                     # mdefines.h PY_FOOD_*: the range behind each hunger level
PRICE = dict(clw=24, csw=50, ccw=150, phase=20, tele=250, staff=250, wor=200, speed=400, berserk=100, hero=35)
# E1's prices; Teleportation is not sold (scarcity price); a Staff of Teleportation charge ~ 2000 g / 8 charges;
# Speed = the kit's Black Market line (~383-450, cap 450; 643465e)
SAVE = 0.45                                                 # P(our saving throw): skill_sav ~40 + adj_wis at clvl 25
PHASE_DIST = (5, 10)
P_SEE_AFTER_PHASE = 0.5
P_SUMMON_PLACE = 0.6
P_AWAKE = 0.4          # a monster in view that hasn't attacked yet is hunting us (calib_move.py: non-adjacent monsters close at
                       # ~0.4 of the straight-walk rate while we stand still; no asleep flag in our logs)
HIT_SCALE = 1.10       # monster blows land 0.572 observed vs 0.518 modelled over 976 logged blows (calib_blows.py)
P_WAKE = 0.05          # OBSOLETE since 29o (kept for importers): sleepers now follow the server's rule, see wake_step
NOISE_FIGHT = 18       # effective noise in a fight, calibrated on the 21 replays (sim/real melee rounds 0.99); the code's cap
                       # while acting every turn is 29-30 (cmd1.c:2936 +29 an action, dungeon.c:1322 -2 a turn), an upper bound
RANGED = ("BR_", "BO_", "BA_", "ARROW", "MISSILE", "MIND_BLAST", "BRAIN_SMASH", "CAUSE")
STATUS_SPELLS = {"BLIND", "CONF", "SCARE", "SLOW", "HOLD"}
SUMMON_COUNT = dict(S_KIN=6, S_MONSTER=1, S_MONSTERS=8, S_ANIMAL=6, S_ANIMALS=6, S_SPIDER=6, S_HOUND=6, S_HYDRA=6,
                    S_ANGEL=1, S_DEMON=1, S_UNDEAD=1, S_DRAGON=1, S_HI_DEMON=8, S_HI_UNDEAD=8, S_HI_DRAGON=8,
                    S_WRAITH=16, S_UNIQUE=16)


def adist(dy, dx):
    dy, dx = abs(dy), abs(dx)
    return max(dy, dx) + min(dy, dx) // 2


@functools.lru_cache(maxsize=None)
def summon_pool(kind, level, symbol):
    out = []
    for r in RACES.values():
        lv, ra = int(r["level"]), int(r["rarity"] or 0)
        if lv <= 0 or lv > level or ra <= 0:
            continue
        fl = set(r["flags"].split("|"))
        if ("UNIQUE" in fl) != (kind == "S_UNIQUE"):
            continue
        ok = {"S_KIN": r["symbol"] == symbol, "S_ANIMAL": "ANIMAL" in fl, "S_ANIMALS": "ANIMAL" in fl,
              "S_SPIDER": r["symbol"] == "S", "S_HOUND": r["symbol"] == "Z", "S_HYDRA": r["symbol"] == "M",
              "S_UNDEAD": "UNDEAD" in fl, "S_HI_UNDEAD": "UNDEAD" in fl, "S_DEMON": "DEMON" in fl,
              "S_HI_DEMON": "DEMON" in fl, "S_DRAGON": "DRAGON" in fl, "S_HI_DRAGON": "DRAGON" in fl,
              "S_WRAITH": r["symbol"] == "W", "S_ANGEL": r["symbol"] == "A"}.get(kind, True)
        if ok:
            out.append((r["name"], 100 // ra))
    return tuple(out)


class Mon:
    __slots__ = ("r", "name", "hp", "hpmax", "dist", "energy", "sx", "pct", "spells", "blows", "rl", "ac", "flags",
                 "seen", "unique", "caster", "melee_max", "awake", "csleep")

    def __init__(self, r, dist, ac_player, rng, hp_frac=1.0):
        self.r, self.name = r, r["name"]
        self.flags = set(r["flags"].split("|")) if r["flags"] else set()
        n, s = dice(r["hp_dice"])
        self.hpmax = n * s if "FORCE_MAXHP" in self.flags else roll(rng, n, s)
        self.hp = max(1, int(self.hpmax * hp_frac))
        self.dist = dist
        self.energy = rng.random()
        self.sx = ENERGY.get(int(r["speed"]), 1000) / 1000
        f = int(r["spell_freq"]) if r["spell_freq"] else 0
        self.pct = (100 // f) / 100 if f else 0.0
        self.spells = [s for s in r["spells"].split("|") if s] if r["spells"] else []
        self.rl = max(1, int(r["level"]))
        self.ac = int(r["ac"])
        self.seen = True
        self.awake = True
        self.csleep = 0
        self.unique = "UNIQUE" in self.flags
        self.caster = any(s.startswith("S_") or s in STATUS_SPELLS for s in self.spells)
        self.blows, self.melee_max = [], 0
        for b in (r["blow1"], r["blow2"], r["blow3"], r["blow4"]):
            if not b:
                continue
            p = b.split(":")
            eff = p[1] if len(p) > 1 else ""
            if not eff:
                continue
            bn, bs = dice(p[2] if len(p) > 2 else "")
            i = POWER.get(eff, 0) + 3 * self.rl
            self.blows.append((eff, bn, bs, min(0.95, HIT_SCALE * (0.05 + 0.90 * max(0, i - (3 * ac_player) // 4) / i))))
            self.melee_max += bn * bs


class State:
    TIMERS = ("fast", "slow", "hero", "berserk", "confused", "blind", "afraid", "paralyzed")

    def __init__(self, p, mons, rng):
        self.p = dict(p)
        if isinstance(self.p.get("food"), (tuple, list)):     # a hunger level's range: draw this rollout's counter
            self.p["food"] = rng.uniform(*self.p["food"])
        self.inv = dict(p["inv"])
        self.mons = mons
        self.rng = rng
        for t in self.TIMERS:
            setattr(self, t, p.get(t, 0))
        self.recall = p.get("recall")
        self.stairs = p.get("stairs")
        self.spent = 0
        self.escaped = None
        self.lowest = p["hp"]
        self.block = 0
        self.xp = 0.0
        self.rounds = 0


def roll(rng, n, s):
    """Sum of n s-sided dice; n > 4 by the normal approximation (clipped), else exactly."""
    if not n or not s:
        return 0
    if n > 4:
        v = round(rng.gauss(n * (s + 1) / 2, (n * (s * s - 1) / 12) ** 0.5))
        return min(n * s, max(n, v))
    r = rng.random
    return sum(int(r() * s) + 1 for _ in range(n))


def saves(st):
    return st.rng.random() < st.p.get("save", SAVE)


# ---------------- player ----------------
def slay_mult(p, m):
    """tot_dam_aux (cmd1.c:183-500): the best multiplier for this monster -- p["slays"] {race flag: mult}, e.g. {"EVIL": 2,
    "UNDEAD": 3, "ORC": 3}, and p["brands"] {element: 3}, void against the monster's IM_<element>."""
    mult = 1
    for flag, k in (p.get("slays") or {}).items():
        if flag in m.flags and k > mult:
            mult = k
    for el, k in (p.get("brands") or {}).items():
        if ("IM_" + el) not in m.flags and k > mult:
            mult = k
    return mult


def crit_mean_factor(p):
    """critical_norm (cmd1.c:119): chance (weight + 5 x to-hit + 3 x clvl)/5000, then by weight + d650: x2+5 / x2+10 / x3+15 /
    x3+20 / x3.5+25. Returns (chance, [(cum_prob, mult, add)]) or None without p["weight"] (tenth-pounds)."""
    w = p.get("weight")
    if not w:
        return None
    chance = min(1.0, (w + 5 * p["tohit"] + 3 * p["clvl"]) / 5000)
    bands = [(400, 2, 5), (700, 2, 10), (900, 3, 15), (1300, 3, 20), (10 ** 9, 3.5, 25)]
    out, prev = [], 0
    for top, mu, add in bands:
        hi = min(650, max(0, top - w - 1))
        pr = max(0, hi - prev) / 650
        prev = max(prev, hi)
        if pr > 0:
            out.append((pr, mu, add))
    return chance, out


def hit_damage(st, m, rng):
    """One blow that hit: dice x slay, maybe a critical (on the multiplied dice), + to-dam (cmd1.c:1464-1481)."""
    p = st.p
    pn, ps = dice(p["dice"])
    d = roll(rng, pn, ps) * slay_mult(p, m)
    cr = p.get("_crit")
    if cr is None:
        cr = p["_crit"] = crit_mean_factor(p) or False
    if cr and rng.random() < cr[0]:
        x = rng.random()
        for pr, mu, add in cr[1]:
            if x < pr:
                d = int(d * mu) + add
                break
            x -= pr
    return d + p["todam"]


def our_damage_per_turn(st, m):
    p = st.p
    tohit = p["tohit"] + (24 if st.berserk else 0) + (12 if st.hero else 0)
    chance = 82 + 45 * p["clvl"] // 10 + 3 * tohit
    if st.blind:
        chance = (chance + 1) // 2
    ph = 0.05 + 0.90 * max(0, chance - m.ac * 3 // 4) / chance
    pn, ps = dice(p["dice"])
    return p["blows"] * ph * (pn * (ps + 1) / 2 * slay_mult(p, m) + p["todam"])


def pick_target(st, adj):
    """Fix 3 (10-25): a summoner/status caster that dies in <= 2 turns first; else the quickest kill."""
    casters = [m for m in adj if m.caster and m.hp <= 2 * our_damage_per_turn(st, m)]
    if casters:
        return min(casters, key=lambda m: m.hp)
    return min(adj, key=lambda m: m.hp)


def attack(st, target=None):
    if st.afraid:
        return False
    adj = [m for m in st.mons if m.dist <= 1]
    if not adj:
        return False
    m = target if target in adj else pick_target(st, adj)
    p, rng = st.p, st.rng
    tohit = p["tohit"] + (24 if st.berserk else 0) + (12 if st.hero else 0)
    chance = 82 + 45 * p["clvl"] // 10 + 3 * tohit
    if st.blind:
        chance = (chance + 1) // 2
    pn, ps = dice(p["dice"])
    for _ in range(p["blows"]):
        k = rng.random()
        hit = k < 0.05 if k < 0.10 else rng.random() * chance >= m.ac * 3 // 4
        if hit:
            m.hp -= hit_damage(st, m, rng)
    if m.hp <= 0:
        st.mons.remove(m)
        st.xp += int(m.r["exp"]) * m.rl / st.p["clvl"]
    return True


def use(st, item):
    if st.inv.get(item, 0) <= 0:
        return False
    if item in ("phase", "tele", "wor") and (st.confused or st.blind):
        return False                                          # refused before energy is spent
    p, rng = st.p, st.rng
    st.inv[item] -= 1
    st.spent += PRICE[item]
    if item in HEAL:
        p["hp"] = min(p["mhp"], p["hp"] + rng.randint(*HEAL[item]))
        st.confused = st.blind = 0
        if p.get("food") is not None:                         # potions nourish (object.txt pval); Gorged at 15000: -10 speed
            p["food"] += FOOD.get(item, 0)
            if p["food"] >= 15000:
                st.slow = max(st.slow, 1000)
    elif item == "speed":
        st.fast = st.fast + 5 if st.fast else rng.randint(1, 25) + 15
    elif item == "berserk":
        p["hp"] = min(p["mhp"], p["hp"] + 30)
        if not st.berserk:
            p["hp"] = p["hp"] * (p["mhp"] + 30) // p["mhp"]; p["mhp"] += 30; p["ac"] -= 10
        st.berserk = rng.randint(1, 25) + 25
        st.afraid = 0
    elif item == "hero":
        p["hp"] = min(p["mhp"], p["hp"] + 10)
        if not st.hero:
            p["hp"] = p["hp"] * (p["mhp"] + 10) // p["mhp"]; p["mhp"] += 10
        st.hero = rng.randint(1, 25) + 25
        st.afraid = 0
    elif item == "phase":
        for m in st.mons:
            m.dist = rng.randint(*PHASE_DIST)
            m.seen = rng.random() < P_SEE_AFTER_PHASE
        if st.stairs is not None:
            st.stairs = max(1, st.stairs + rng.randint(-10, 10))
    elif item in ("tele", "staff"):
        if item == "staff" and rng.random() > (0.04 if st.confused else 0.85):
            return True                                       # a failed use costs the turn
        st.escaped = "teleport"
    elif item == "wor":
        st.recall = None if st.recall is not None else rng.randint(15, 34)   # a 2nd read cancels
    return True


def escape_move(st, crowd):
    """Fix 4: Teleport over Phase against 4+ near us; staff if the scroll is out."""
    order = ("tele", "staff", "phase") if crowd >= 4 else ("phase", "tele", "staff")
    return any(use(st, it) for it in order)


POLICY_VERSION = "pilot-escape-2026-10-29o"   # mirrors github/tools/pilot/pilot.py escape(), berserk_tick, fear_cure, status_tick
CONF_LOCK_BLOCKS = 4   # the Pilot's 8 s of confusion with monsters adjacent, as player actions (~3 s a block in the HP bubble)


def worst_turn(st, adj):
    """The adjacent monsters' worst melee in one of our turns (Pilot: worst_3turns / 3): max blows x their rounds per turn."""
    return sum(m.melee_max * max(1.0, m.sx / speed_energy(st) / 2) for m in adj)


def base_policy(st):
    """The Pilot's rules (POLICY_VERSION). Emergency = HP < 50% or the adjacent worst turn >= 1/3 of HP:
    Optional p["food"] (a number, or a (lo, hi) range drawn per rollout -- the client only knows the level: Weak 1000-2000,
    Hungry... use FOOD_LEVEL[level]): cure potions add their nourishment; at 15000 (Gorged) we are slowed -10 for the rest of the fight.
    Can't read (blind/confused) with the adjacent worst turn >= 1/3 HP: the Staff of Teleportation, 16 blocks apart (46a5764).
    Hard-fight start (berserk_tick's test): speed_start_tick (Speed if not hasted), then berserk_tick.
    escape() order: one turn from death -> Teleportation, else Phase; Speed first; Word of Recall below 30% HP; phasing
    futile (3 phases, still adjacent) -> recall; kill a summoner/status caster that dies in 2 rounds; 4+ about (not
    stationary, within 5) in the open -> Teleportation/staff; Phase; out of melee: stairs within 20, else cure (none with
    2+ adjacent). Outside emergencies: status cure (blind/confused, CLW first) when threatened; fear cure (Heroism >
    Berserk) when afraid with something adjacent; Berserk at the start of a hard melee; else fight."""
    p = st.p
    adj = [m for m in st.mons if m.dist <= 1]
    can_read = not st.blind and not st.confused
    worst = worst_turn(st, adj)
    emergency = p["hp"] < 0.5 * p["mhp"] or (adj and 3 * worst >= p["hp"])
    # confusion lock (Pilot.confusion_lock / confusion_window, session 9): confused for CONF_LOCK_BLOCKS actions with something
    # adjacent -> CSW, else CCW (at most 4 a level, 4 blocks apart); in the clear turn after, 3+ adjacent -> teleport
    st.conf_n = getattr(st, "conf_n", 0) + 1 if st.confused else 0
    if st.confused and adj and st.conf_n >= CONF_LOCK_BLOCKS and getattr(st, "lock_cures", 0) < 4 and \
            st.block - getattr(st, "lock_at", -99) >= 4 and (use(st, "csw") or use(st, "ccw")):
        st.lock_cures, st.lock_at, st.conf_n = getattr(st, "lock_cures", 0) + 1, st.block, 0
        return
    if st.block - getattr(st, "lock_at", -99) <= 1 and len(adj) >= 3 and \
            ((can_read and use(st, "tele")) or use(st, "staff")):
        return
    if adj and not can_read and worst >= p["hp"] / 3 and st.block - getattr(st, "staff_at", -99) >= 16 and use(st, "staff"):
        st.staff_at = st.block                                # group_tick / teleport_item (46a5764): can't read -> the staff
        return
    if emergency:
        if st.stairs is not None and st.stairs <= 0:
            st.escaped = "stairs"
            return
        one_turn = bool(adj) and worst >= 0.9 * p["hp"]
        if one_turn and can_read and (use(st, "tele") or use(st, "phase")):
            st.last_phase = st.block
            return
        if not one_turn and not st.fast and st.block - getattr(st, "speed_at", -99) >= 30 and use(st, "speed"):
            st.speed_at = st.block
            return
        if p["hp"] < 0.3 * p["mhp"] and not can_read and st.recall is None and st.inv.get("wor", 0) > 0:
            for c in (("csw", "ccw") if st.confused else ("clw", "csw", "ccw")):   # recall blind/confused: cure, then read
                if use(st, c):
                    return
        if p["hp"] < 0.3 * p["mhp"] and can_read and st.recall is None and use(st, "wor"):
            return
        phases = [b for b in getattr(st, "phase_hist", []) if st.block - b <= 30]
        if adj and len(phases) >= 3 and p["hp"] >= 0.2 * p["mhp"] and st.recall is None and can_read and use(st, "wor"):
            return
        casters = [m for m in adj if m.caster and m.hp <= 2 * our_damage_per_turn(st, m)]
        if casters and not st.afraid and attack(st, min(casters, key=lambda m: m.hp)):
            return
        crowd = sum(1 for m in st.mons if m.dist <= 5 and "NEVER_MOVE" not in m.flags)
        in_corridor = p.get("max_adj", 8) <= 2
        if st.afraid and len(adj) >= 2 and ((can_read and use(st, "tele")) or use(st, "staff")):
            return                                            # afraid, 2+ adjacent: teleport, corridor too (8945cb6)
        if adj and crowd >= 4 and not in_corridor and (
                (can_read and use(st, "tele")) or use(st, "staff")):
            return
        collapsing = p["hp"] < 0.35 * p["mhp"]
        if adj and can_read and (st.block - getattr(st, "last_phase", -99) >= 4 or collapsing) and use(st, "phase"):
            st.last_phase = st.block
            st.phase_hist = phases + [st.block]
            return
        if not adj:
            if st.stairs is not None and st.stairs <= 20:
                st.stairs -= 1
                if st.stairs <= 0:
                    st.escaped = "stairs"
                return
            for c in ("ccw", "csw", "clw"):
                if use(st, c):
                    return
            return
        if len(adj) <= 1:
            for c in ("ccw", "csw", "clw"):
                if use(st, c):
                    return
    threatened = adj and (p["hp"] < 0.5 * p["mhp"] or any(m.rl >= p["clvl"] - 5 for m in adj))
    if (st.blind or st.confused) and threatened:
        for c in (("csw", "ccw") if st.confused else ("clw", "csw", "ccw")):   # CLW for blindness only (session 9)
            if use(st, c):
                return
    if st.afraid and adj:
        for c in ("hero", "berserk"):
            if use(st, c):
                return
    hard = adj and (any(m.unique or m.rl >= p["clvl"] - 5 for m in adj if "NEVER_MOVE" not in m.flags)
                    or (len(adj) >= 2 and p["hp"] < 0.75 * p["mhp"]))
    if hard and not st.fast and st.block - getattr(st, "speed_at", -99) >= 48 and use(st, "speed"):
        st.speed_at = st.block                                # speed_start_tick (643465e): Speed, then Berserk; 30 s apart
        return
    if adj and not st.berserk and st.block - getattr(st, "berserk_at", -99) >= 30 and (
            any(m.unique or m.rl >= p["clvl"] - 5 for m in adj if "NEVER_MOVE" not in m.flags)
            or (len(adj) >= 2 and p["hp"] < 0.75 * p["mhp"])) and use(st, "berserk"):
        st.berserk_at = st.block
        return
    attack(st)


OPTIONS = {
    "rules": [], "fight": ["fight"], "speed": ["speed"], "berserk": ["berserk"], "speed+berserk": ["speed", "berserk"],
    "ccw": ["ccw"], "phase": ["phase"], "phase+ccw": ["phase", "ccw"], "teleport": ["tele"], "staff": ["staff"],
    "recall+phase": ["wor", "phase"], "stairs": ["stairs"],
}


def player_act(st, plan):
    if plan:
        a = plan.pop(0)
        if a == "fight":
            attack(st)
            return
        if a in ("melee", "walk", "rest", "other", "run", "boldness"):
            if a == "melee":
                attack(st)
            return
        if a == "take_stairs":                                # replay: we took stairs here
            st.escaped = "stairs"
            return
        if a == "stairs":
            if st.stairs is None:
                base_policy(st)
                return
            st.stairs -= 1
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
def fall_asleep(m, rng):
    """monster2.c:1981: csleep = 2 x alertness + randint1(10 x alertness); alertness 0 never sleeps."""
    v = int(m.r.get("alertness") or 0)
    if v <= 0:
        m.awake = True
        return
    m.awake = False
    m.csleep = 2 * v + rng.randint(1, 10 * v)


def wake_step(st, m):
    """melee2.c:2498-2540, 3484-3501: each turn of a sleeper, it notices our noise if randint0(1024)^3 <= 2^min(30, noise),
    then loses 100/distance sleep (1 at 50+ squares); awake at 0. p["noise"]: NOISE_FIGHT while we act every turn; 0 if idle
    (then a 1% chance a turn of 2^(30 - stealth), not modelled)."""
    n = st.p.get("noise", NOISE_FIGHT)
    q = min(1.0, (2.0 ** min(30, n)) ** (1 / 3) / 1024) if n > 0 else 0.0
    if q and st.rng.random() < q:
        m.csleep -= 100 // max(1, m.dist) if m.dist < 50 else 1
        if m.csleep <= 0:
            m.awake = True


def monster_act(st, m):
    p, rng = st.p, st.rng
    if not m.awake:
        wake_step(st, m)
        return 1
    if m.dist <= 1:
        if m.spells and rng.random() < m.pct:
            cast(st, m, rng.choice(m.spells))
            return 1
        if m.blows and "NEVER_BLOW" not in m.flags:
            st.rounds += 1
            for eff, n, s, ph in m.blows:
                if rng.random() < ph:
                    d = roll(rng, n, s)
                    if eff in ("HURT", "SHATTER"):
                        d -= d * min(p["ac"], 150) // 250
                    elif eff in ("ACID", "ELEC", "FIRE", "COLD"):
                        d = resisted(st, eff.lower(), d)          # melee1.c -> acid/elec/fire/cold_dam
                    elif eff == "CONFUSE" and not p.get("res_conf"):
                        st.confused += 3 + rng.randint(1, m.rl)
                    elif eff == "BLIND" and not p.get("res_blind"):
                        st.blind += 10 + rng.randint(1, m.rl)
                    elif eff == "TERRIFY" and not (st.hero or st.berserk or saves(st)):
                        st.afraid += 3 + rng.randint(1, m.rl)
                    elif eff == "PARALYZE" and not (p.get("free_action") or saves(st)):
                        st.paralyzed += 3 + rng.randint(1, m.rl)
                    p["hp"] -= d
            return 2                                          # MONSTER_RECOIL
        return 1
    if m.spells and m.seen and m.dist <= 18 and rng.random() < m.pct:
        cast(st, m, rng.choice(m.spells))
        return 1
    if "NEVER_MOVE" not in m.flags:
        if m.dist == 2 and sum(1 for o in st.mons if o.dist <= 1) >= p.get("max_adj", 8):
            return 1
        m.dist -= 1
        if m.dist <= 3:
            m.seen = True
    return 1


# ---------------- resists (spells1.c project_p, acid/elec/fire/cold_dam; melee2.c cause/mind blast) ----------------
ELEMENT = {"ACID": "acid", "ELEC": "elec", "FIRE": "fire", "COLD": "cold", "ICEE": "cold", "POIS": "pois", "NETH": "neth",
           "CONF": "conf", "SOUN": "sound", "SHAR": "shard", "NEXU": "nexus", "DARK": "dark", "LITE": "lite",
           "CHAO": "chaos", "DISE": "disen", "WATE": "water", "PLAS": "plasma", "INER": "inertia", "MANA": "mana",
           "GRAV": "gravity", "TIME": "time", "WALL": "force"}
RES_THIRD = ("acid", "elec", "fire", "cold", "pois")                 # (dam + 2) / 3 with resist (also elemental blows)
RES_RAND = dict(neth=6, chaos=6, shard=6, nexus=6, disen=6, sound=5, conf=5, lite=4, dark=4)   # dam * k / (d6 + 6)
SAVE_DMG = ("CAUSE_1", "CAUSE_2", "CAUSE_3", "CAUSE_4", "MIND_BLAST", "BRAIN_SMASH")      # a saving throw negates them


def resisted(st, element, dam):
    """Damage after our resist to `element` (p flags res_<element>), plus the unresisted side effects we model:
    confusion (conf, chaos, water), blindness (lite, dark; res_blind stops it)."""
    p, rng = st.p, st.rng
    if element in RES_THIRD:
        return (dam + 2) // 3 if p.get("res_" + element) else dam
    if element in RES_RAND and p.get("res_" + element):
        return dam * RES_RAND[element] // (rng.randint(1, 6) + 6)
    if element in ("conf", "water") or (element == "chaos" and not p.get("res_chaos")):
        if not p.get("res_conf"):
            st.confused += rng.randint(1, 20) + 10 if element != "water" else rng.randint(1, 5) + 5
    if element in ("lite", "dark") and not p.get("res_blind") and not st.blind:
        st.blind = rng.randint(1, 5) + 2
    return dam


def cast(st, m, sp):
    p, rng = st.p, st.rng
    if sp == "BLINK":
        m.dist = max(m.dist, rng.randint(2, 10))
    elif sp == "HEAL":
        m.hp = min(m.hpmax, m.hp + 6 * m.rl)
    elif sp in ("TPORT", "TELE_SELF"):
        if m in st.mons:
            st.mons.remove(m)
    elif sp == "TELE_TO":
        m.dist = 1
    elif sp == "HASTE":
        m.sx = min(m.sx * 2, 3.0)
    elif sp == "BLIND":
        if not (p.get("res_blind") or saves(st)):
            st.blind = max(st.blind, 12 + rng.randint(0, 3))
    elif sp == "CONF":
        if not (p.get("res_conf") or saves(st)):
            st.confused += 4 + rng.randint(0, 3)
    elif sp == "SCARE":
        if not (st.hero or st.berserk or saves(st)):
            st.afraid += 4 + rng.randint(0, 3)
    elif sp == "SLOW":
        if not (p.get("free_action") or saves(st)):
            st.slow += 4 + rng.randint(0, 3)
    elif sp == "HOLD":
        if not (p.get("free_action") or saves(st)):
            st.paralyzed += 4 + rng.randint(0, 3)
    elif sp.startswith("S_"):
        lev = (p.get("depth", 13) + m.rl) // 2 + 5
        pool = summon_pool(sp, lev, m.r["symbol"])
        if pool:
            names, w = zip(*pool)
            for _ in range(SUMMON_COUNT.get(sp, 1)):
                if rng.random() < P_SUMMON_PLACE:
                    st.mons.append(Mon(RACES[rng.choices(names, w)[0]], rng.randint(1, 3), p["ac"], rng))
    elif sp in SAVE_DMG:
        if not saves(st):
            p["hp"] -= spell_dmg(sp, m.rl, m.hp)[0]
            if sp in ("MIND_BLAST", "BRAIN_SMASH") and not p.get("res_conf"):
                st.confused += 4 + rng.randint(0, 3)
    elif sp.startswith(RANGED):
        d = spell_dmg(sp, m.rl, m.hp)[0]
        el = ELEMENT.get(sp.split("_", 1)[1]) if "_" in sp else None
        p["hp"] -= resisted(st, el, d) if el else d


# ---------------- rollout ----------------
def speed_energy(st):
    return ENERGY.get(110 + 10 * bool(st.fast) - 10 * bool(st.slow), 1000) / 1000


def rollout(p, team, plan, seed, horizon=30, arrivals=(), trace=False, actor=None):
    """Optional player keys: slays {flag: mult}, brands {element: mult}, weight (tenth-pounds: criticals).
    team: [(name, dist[, hp_frac[, awake]])] (hp_frac None = full; awake True/False from the Pilot's look, None = unknown ->
    p_awake); plan: list of first moves; arrivals: [(block, name, dist)].
    Returns dict(dead, end_hp, low, spent, escaped, blocks[, path])."""
    rng = random.Random(seed)
    mons = [Mon(RACES[t[0]], t[1], p["ac"], rng, t[2] if len(t) > 2 and t[2] is not None else 1.0) for t in team]
    for t, m in zip(team, mons):
        known = t[3] if len(t) > 3 else None                  # the Pilot's look: True awake, False asleep, None unknown
        if known is not None:
            if not known and m.dist > 1:
                fall_asleep(m, rng)
        elif m.dist > 1 and rng.random() > p.get("p_awake", P_AWAKE):
            fall_asleep(m, rng)
    cap = p.get("max_adj", 8)
    for m in sorted(mons, key=lambda m: m.dist)[cap:]:
        m.dist = max(m.dist, 2)
    st = State(p, mons, rng)
    plan = list(plan)
    arr = sorted(arrivals)
    pe, path = 0.0, []
    for blk in range(horizon):
        st.block = blk
        while arr and arr[0][0] <= blk:
            _, n, d = arr.pop(0)
            m = Mon(RACES[n], d, st.p["ac"], rng)
            if d > 1 and rng.random() >= p.get("p_awake", P_AWAKE):
                fall_asleep(m, rng)
            st.mons.append(m)
        if st.paralyzed:
            pe = 0.0
        else:
            pe += speed_energy(st)
            while pe >= 1 and st.escaped is None:
                pe -= 1
                (actor or player_act)(st, plan)
        if st.escaped or (not st.mons and not arr):
            break
        for m in list(st.mons):
            m.energy += m.sx
            while m.energy >= 1 and m in st.mons:
                m.energy -= monster_act(st, m)
            if st.p["hp"] <= 0:
                return dict(dead=True, end_hp=st.p["hp"], low=st.p["hp"], spent=st.spent, escaped=None, blocks=blk,
                            xp=st.xp, rounds=st.rounds, path=path + [st.p["hp"]] if trace else None)
        st.lowest = min(st.lowest, st.p["hp"])
        if trace:
            path.append(st.p["hp"])
        for t in State.TIMERS:
            v = getattr(st, t)
            if v:
                setattr(st, t, v - 1)
                if t == "berserk" and v == 1:
                    st.p["ac"] += 10
        if st.recall is not None:
            st.recall -= 1
            if st.recall <= 0:
                st.escaped = "recall"
    return dict(dead=False, end_hp=st.p["hp"], low=st.lowest, spent=st.spent, xp=st.xp, rounds=st.rounds,
                escaped=st.escaped or ("cleared" if not st.mons else None), blocks=blk, path=path if trace else None)


def q(a, f):
    a = sorted(a)
    return a[min(len(a) - 1, int(f * len(a)))]


SAFE_NEAR = 0.02       # an option is safe if P(lowest HP <= 10%) <= 2% ...
SAFE_LOW_P10 = 0.30    # ... and its 10th-percentile lowest HP is >= 30% of max
MIN_GAIN = 50          # ... and by at least this much (XP net of gold) to override the rules on XP -- or 30 s of play,
MIN_GAIN_BLOCKS = 48   # whichever is more: 48 blocks x p["xp_rate_per_block"] (else xp_per_block) (the user via the Architect, 10-28)
XP_PER_GOLD = 1.0      # FALLBACK only: the Pilot sets options_sim.XP_PER_GOLD per snapshot (rolling XP/gold, 643465e);
                       # replays should use the estimator record's xp_per_gold


def evaluate(p, team, n=200, options=None, arrivals=()):
    """Rank: safe options first (SAFE_NEAR, SAFE_LOW_P10), by expected XP then gold; unsafe ones after, by P(near death)."""
    out = []
    for o in options or OPTIONS:
        if o == "stairs" and p.get("stairs") is None or o == "staff" and not p["inv"].get("staff"):
            continue
        res = [rollout(p, team, OPTIONS[o], seed=i, arrivals=arrivals) for i in range(n)]
        near = sum(r["dead"] or r["low"] <= 0.1 * p["mhp"] for r in res) / n
        low10 = q([r["low"] for r in res], 0.1)
        out.append(dict(option=o, safe=near <= SAFE_NEAR and low10 >= SAFE_LOW_P10 * p["mhp"],
                        p_near_death=round(near, 3), p_death=round(sum(r["dead"] for r in res) / n, 3), low_p10=low10,
                        xp=round(statistics.mean(r["xp"] for r in res)),
                        end_hp_p10=q([max(0, r["end_hp"]) for r in res], 0.1),
                        end_hp_mean=round(statistics.mean(max(0, r["end_hp"]) for r in res)),
                        gold=round(statistics.mean(r["spent"] for r in res)),
                        unresolved=round(sum(r["escaped"] is None and not r["dead"] for r in res) / n, 2)))
    out.sort(key=lambda r: (not r["safe"], -r["xp"] if r["safe"] else r["p_near_death"], r["gold"]))
    return out


DIVE04 = dict(hp=303, mhp=333, ac=60, clvl=25, blows=3, dice="4d4", todam=10, tohit=8, depth=13, stairs=None,
              free_action=True, save=SAVE,
              inv=dict(ccw=5, csw=2, clw=2, phase=10, tele=2, staff=0, wor=2, speed=2, berserk=2, hero=2))
SCENARIOS = {
    "m30": [("Umber hulk", 1), ("Fire hound", 1), ("Fire hound", 2), ("Energy hound", 2), ("Energy hound", 3),
            ("Wolf", 1), ("Griffon", 3), ("Yeti", 4), ("Druid", 2), ("Copperhead snake", 2), ("Black harpy", 3)],
    "druid": [("Druid", 1), ("Wolf", 1), ("Wolf", 2)],
    "a7": [("Hill giant", 1)],
    "bullroarer": [("Bullroarer the Hobbit", 1)],
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--scenario", default="m30")
    ap.add_argument("--hp", type=int)
    ap.add_argument("--stairs", type=int)
    ap.add_argument("--max-adj", type=int, default=8)
    ap.add_argument("--no-fa", action="store_true", help="without Free Action (m30 had none)")
    o = ap.parse_args()
    p = dict(DIVE04)
    if o.hp:
        p["hp"] = o.hp
    if o.stairs is not None:
        p["stairs"] = o.stairs
    if o.no_fa:
        p["free_action"] = False
    p["max_adj"] = o.max_adj
    t0 = time.time()
    rows = evaluate(p, SCENARIOS[o.scenario], o.n)
    dt = time.time() - t0
    for r in rows:
        print(r)
    print(f"{len(rows)} options x {o.n} rollouts in {dt:.2f} s ({1000 * dt / len(rows) / o.n:.2f} ms per rollout)")


def evaluate_fast(p, team, budget_s=0.5, arrivals=(), n1=30, keep=4, options=None):
    """Successive halving within a wall-time budget: n1 rollouts for every applicable option, then the best `keep` (by
    evaluate's ranking) get more rollouts (same seeds continued) until the budget is spent. Returns the ranked list."""
    t0 = time.time()
    opts = [o for o in (options or OPTIONS) if not (o == "stairs" and p.get("stairs") is None)
            and not (o == "staff" and not p["inv"].get("staff"))]
    first = evaluate(p, team, n1, opts, arrivals)
    per = (time.time() - t0) / max(1, len(opts) * n1)
    top = [r["option"] for r in first[:keep]]
    n2 = int(max(0.0, budget_s - (time.time() - t0)) / max(per, 1e-6) / len(top))
    if n2 < 10:
        return first
    return evaluate(p, team, n1 + n2, top, arrivals) + first[keep:]


def choose(p, team, n=100, arrivals=(), options=None, z=2.0):
    """The decision: keep the rules unless another option is clearly better on the same seeds (paired, common random
    numbers): (a) the rules are unsafe and the option is safe, or (b) both are safe and the option's XP net of gold
    (XP_PER_GOLD) beats the rules' by more than z standard errors of the paired difference and by >= 10%.
    Optional p["xp_per_block"]: the XP a game turn earns elsewhere (e.g. the rolling rate); each line is then charged for the
    blocks it takes (fight or walk out + resting back the HP lost), which matters for fight-vs-leave (band) decisions.
    Returns (option, why, table)."""
    if not team:
        return "rules", "no known monster", []
    inv = p.get("inv") or {}
    opts = [o for o in (options or OPTIONS) if not (o == "stairs" and p.get("stairs") is None)
            and not (OPTIONS[o] and OPTIONS[o][0] in PRICE and inv.get(OPTIONS[o][0], 0) <= 0)]
    if "rules" not in opts:
        opts = ["rules"] + opts
    res = {o: [rollout(p, team, OPTIONS[o], seed=i, arrivals=arrivals) for i in range(n)] for o in opts}

    def summary(rs):
        near = sum(r["dead"] or r["low"] <= 0.1 * p["mhp"] for r in rs) / n
        low10 = q([r["low"] for r in rs], 0.1)
        return near, low10, near <= SAFE_NEAR and low10 >= SAFE_LOW_P10 * p["mhp"]
    xpg = p.get("xp_per_gold", XP_PER_GOLD)   # per call (thread-safe); the module value is the fallback
    xpb = p.get("xp_per_block", 0.0)          # opportunity cost of time (0 = off): the rolling XP per game turn elsewhere
    regen = (p["mhp"] * 394 + 1442) / 65536    # HP regained per resting block (dungeon.c:1245-1306)

    def time_used(r):
        """Blocks this line takes: the fight (or the walk out) plus resting back the HP it cost."""
        return r["blocks"] + 1 + max(0, p["hp"] - max(0, r["end_hp"])) / regen
    rate = p.get("xp_rate_per_block", xpb)  # the play rate (XP per game turn) for the floor; doesn't switch on the time cost
    min_gain = max(MIN_GAIN, MIN_GAIN_BLOCKS * rate)
    base = res["rules"]
    bn, bl, bsafe = summary(base)
    table, best, why = [], "rules", "rules (no option clearly better)"
    best_gain = 0.0
    for o, rs in res.items():
        nn, ll, safe = summary(rs)
        d = [(a["xp"] - b["xp"]) - xpg * (a["spent"] - b["spent"]) - xpb * (time_used(a) - time_used(b))
             for a, b in zip(rs, base)]
        mean = statistics.mean(d); se = statistics.stdev(d) / n ** 0.5 if n > 1 else 0.0
        table.append(dict(option=o, safe=safe, p_near_death=round(nn, 3), low_p10=ll,
                          xp=round(statistics.mean(r["xp"] for r in rs)), dxp=round(mean, 1), se=round(se, 1),
                          gold=round(statistics.mean(r["spent"] for r in rs))))
        if o == "rules":
            continue
        if not bsafe and safe and (best == "rules" or nn < best_gain):
            best, why, best_gain = o, f"rules unsafe (P near death {bn:.2f}); {o} safe ({nn:.2f})", nn
        elif bsafe and safe and best_gain >= 0 and mean > z * se and mean >= max(min_gain, 0.10 * statistics.mean(
                r["xp"] for r in base)) and mean > best_gain:
            best, why, best_gain = o, f"+{mean:.0f} XP net of gold vs rules (SE {se:.0f}), both safe", mean
    if not bsafe and best == "rules":
        safest = min(table, key=lambda r: (r["p_near_death"], -r["low_p10"]))
        best, why = safest["option"], f"nothing safe; least risky (P near death {safest['p_near_death']:.2f})"
    return best, why, sorted(table, key=lambda r: (not r["safe"], -r["xp"]))
