"""geareval -- the gear evaluator: compare gear options A / B / C (the user, 2026-10-26).

An option is a loadout: the worn set with some slots changed. Each option is judged by components:

  1. rules     abilities the depth requires (Free Action, See Invisible): an option that loses one is vetoed.
  2. static    the numbers the game derives from the loadout, recomputed as the server does (xtra1.c calc_bonuses,
               calc_hitpoints, modify_stat_value): stats, blows, damage per round, to-hit, AC, max HP, speed,
               abilities and resists gained or lost.
  3. sim       the Advisor's fight simulator (options_sim.rollout, its base policy = the Pilot's rules) over two
               scenario sets, the same random numbers for every option: the fights Dive04 actually met at the
               depth (its decision log's `mons` records) and the 21 replayed emergencies (the Advisor's replay
               study). Kill speed, XP per turn, lowest HP, P(near death), consumables used.
  4. verdict   vetoes first, then safety (near-death rate in the hard set), then XP per turn net of consumables.

The item slot evaluator (`compare_slot`) builds one option per candidate for one slot (both ring slots for a ring).
Not built yet (design_gear.md): a loadout optimizer over combinations of slots (e.g. boots with resist nexus in
place of Free Action boots, with Free Action moved to another slot).

The simulator models paralysis, blindness, confusion, fear, slowing and AC, not elemental resists (a resist changes
the static and rules columns only), and no criticals: see design_gear.md for its limits.

usage: geareval.py --demo        (Dive04's Ring of Strength (+2) question, from the session-7 snapshot)
In the Pilot: `gearcmp ITEM [ITEM...]` (pilotctl) compares pack items or names against the worn slot."""
import csv
import functools
import json
import os
import random
import re
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "..", "..", "lib", "edit")
RULEBOOK = os.path.join(HERE, "..", "rulebook")
ADVISOR_SIM = "/projectnb/jbrcs/mangband/Advisor/data/estimator"
REPLAYS = "/projectnb/jbrcs/mangband/Advisor/studies/2026-10-25-replay/replays"

SLOT_OF_TVAL = {19: "bow", 20: "weapon", 21: "weapon", 22: "weapon", 23: "weapon", 30: "boots", 31: "gloves",
                32: "helm", 33: "helm", 34: "shield", 35: "cloak", 36: "body", 37: "body", 38: "body", 39: "light",
                40: "amulet", 45: "ring"}
WEAPON_TVALS = (20, 21, 22, 23)
STATS = ("STR", "INT", "WIS", "DEX", "CON", "CHR")
PVAL_FLAGS = set(STATS) | {"SPEED", "BLOWS", "STEALTH", "SEARCH", "INFRA", "TUNNEL"}
# abilities an option may not lose, from what depth (feet): Free Action (paralysers: Ghouls, Carrion crawlers,
# Homunculi), See Invisible (ghosts, Clear hounds; FIELD-NOTES "Dangers met at 600-700 ft")
REQUIRED = {"FREE_ACT": 0, "SEE_INVIS": 600}
LABEL = {"FREE_ACT": "Free Action", "SEE_INVIS": "See Invisible", "HOLD_LIFE": "hold life", "FEATHER": "feather fall",
         "TELEPATHY": "telepathy", "REGEN": "regeneration", "SLOW_DIGEST": "slow digestion"}
ABILITY_FLAGS = set(LABEL)


def label(f):
    """'RES_POIS' -> 'resist poison', 'SUST_STR' -> 'sustain STR', 'FREE_ACT' -> 'Free Action'."""
    if f in LABEL:
        return LABEL[f]
    el = {"POIS": "poison", "ELEC": "lightning", "CONF": "confusion", "BLIND": "blindness", "SHARD": "shards",
          "DISEN": "disenchantment", "LITE": "light", "DARK": "darkness"}
    m = re.match(r"(RES|IM|SUST)_(\w+)", f)
    if m:
        what = el.get(m.group(2), m.group(2).lower()) if m.group(1) != "SUST" else m.group(2)
        return {"RES": "resist ", "IM": "immune to ", "SUST": "sustain "}[m.group(1)] + what
    return f.lower()
WARRIOR = (6, 30, 5)          # max_attacks, min_weight (tenth lb), att_multiply (p_class.txt)
NEAR_DEATH = 0.10             # lowest HP at or under 10% of max: the simulator's "near death" (options_sim SAFE_NEAR)


# ------------------------------------------------------------------ game data
def _norm(name):
    """'& Pair~ of Metal Shod Boots' / 'Pair of Metal Shod Boots' -> 'pair of metal shod boots'."""
    return re.sub(r"\s+", " ", re.sub(r"[&~]", "", name)).strip().lower()


def _read_txt(path):
    """object.txt / ego_item.txt / artifact.txt -> [{N, I, W, P, C, F: set, T: [...]}]."""
    out, cur = [], None
    for line in open(path, encoding="latin-1"):
        line = line.rstrip("\n")
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, rest = line.split(":", 1)
        if k == "N":
            cur = {"N": rest.split(":", 1)[1], "F": set(), "T": []}
            out.append(cur)
        elif cur is None:
            continue
        elif k == "F":
            cur["F"] |= {f.strip() for f in rest.split("|") if f.strip()}
        elif k == "T":
            cur["T"].append([int(x) for x in rest.split(":")])
        elif k in ("I", "W", "P", "C", "X"):
            cur[k] = rest.split(":")
    return out


@functools.lru_cache(maxsize=None)
def kinds():
    """normalized kind name -> dict (wearables only). Jewellery as 'ring of strength' / 'amulet of resist lightning'."""
    out = {}
    for r in _read_txt(os.path.join(LIB, "object.txt")):
        if "I" not in r:
            continue
        tval = int(r["I"][0])
        if tval not in SLOT_OF_TVAL:
            continue
        p = r.get("P", ["0", "0d0", "0", "0", "0"])
        k = dict(tval=tval, sval=int(r["I"][1]), pval=int(r["I"][2]), weight=int(r["W"][2]) if "W" in r else 0,
                 ac=int(p[0]), dice=p[1], to_h=int(p[2]), to_d=int(p[3]), to_a=int(p[4]), flags=set(r["F"]),
                 name=r["N"])
        name = _norm(r["N"])
        if tval == 45:
            name = "ring of " + name
        elif tval == 40:
            name = "amulet of " + name
        out.setdefault(name, k)
    return out


@functools.lru_cache(maxsize=None)
def egos():
    """'of westernesse' -> [{flags, tvals}] (one name can be several egos: 'of Resistance' for body armour,
    shields, cloaks...)."""
    out = {}
    for r in _read_txt(os.path.join(LIB, "ego_item.txt")):
        out.setdefault(_norm(r["N"]), []).append(dict(flags=set(r["F"]), tvals={t[0] for t in r["T"]}, name=r["N"]))
    return out


@functools.lru_cache(maxsize=None)
def artifacts():
    out = {}
    for r in _read_txt(os.path.join(LIB, "artifact.txt")):
        if "I" not in r:
            continue
        p = r.get("P", ["0", "0d0", "0", "0", "0"])
        out[_norm(r["N"])] = dict(tval=int(r["I"][0]), sval=int(r["I"][1]), pval=int(r["I"][2]),
                                  weight=int(r["W"][2]) if "W" in r else 0, ac=int(p[0]), dice=p[1],
                                  to_h=int(p[2]), to_d=int(p[3]), to_a=int(p[4]), flags=set(r["F"]), name=r["N"])
    return out


@functools.lru_cache(maxsize=None)
def stat_table():
    """stat_ind -> {adj_str_td, adj_dex_th, ...} (rulebook char_stat_tables.csv, already less 128)."""
    return {int(r["stat_ind"]): {k: int(v) for k, v in r.items() if k.startswith("adj_")}
            for r in csv.DictReader(open(os.path.join(RULEBOOK, "char_stat_tables.csv")))}


@functools.lru_cache(maxsize=None)
def blows_table():
    return [[int(r[f"D{i}"]) for i in range(12)] for r in csv.DictReader(open(os.path.join(RULEBOOK,
                                                                                          "char_blows_table.csv")))]


# ------------------------------------------------------------------ items
class Item:
    """A worn or candidate item, from its name as the client shows it (and its tval when known)."""

    def __init__(self, name, tval=None, weight=None):
        self.name = name
        n = re.sub(r"\s*\{[^}]*\}", "", name).strip()
        n = re.sub(r"^(an?|the|\d+)\s+", "", n)
        self.known = not re.search(r"\{(good|excellent|special|magical|unknown)", name) or "[" in name or "(+" in name
        # the base name: before the first ( or [
        base = re.split(r"\s+[\(\[]", n, 1)[0].strip()
        self.art = None
        self.kind = None
        self.ego = None
        arts = artifacts()
        q = re.search(r"'([^']+)'", base)
        if q:
            self.art = arts.get(_norm(f"'{q.group(1)}'"))
        # ('the Amulet of Ingwe': an "of X" artifact always shows with "the"; 'a Battle Axe of Westernesse' is an ego)
        if not self.art and re.match(r"the\s", name.strip(), re.I):
            for an, a in arts.items():
                if an.startswith("of ") and base.lower().endswith(an) and (tval is None or a["tval"] == tval):
                    self.art = a
                    break
        kn = kinds()
        low = _norm(base)
        if low in kn and (tval is None or kn[low]["tval"] == tval):
            self.kind = kn[low]
        else:
            # 'battle axe of westernesse' -> kind 'battle axe' + ego 'of westernesse'
            words = low.split()
            for i in range(len(words) - 1, 0, -1):
                k = kn.get(" ".join(words[:i]))
                if k and (tval is None or k["tval"] == tval):
                    self.kind = k
                    self.ego = next((e for e in egos().get(" ".join(words[i:]), ()) if k["tval"] in e["tvals"]),
                                    None)
                    break
        src = self.art or self.kind or {}
        self.tval = tval or src.get("tval")
        self.slot = SLOT_OF_TVAL.get(self.tval)
        self.weight = weight if weight is not None else src.get("weight", 0)
        self.flags = set((self.kind or {}).get("flags", ())) | set((self.ego or {}).get("flags", ())) | \
            set((self.art or {}).get("flags", ()))
        # the numbers shown: (XdY) (+h,+d) [ac,+a] (+pval); armour may show (+h) before its [..]
        self.dice = (src.get("dice") or "0d0")
        m = re.search(r"\((\d+d\d+)\)", n)
        if m:
            self.dice = m.group(1)
        self.to_h, self.to_d = src.get("to_h", 0), src.get("to_d", 0)
        self.ac, self.to_a = src.get("ac", 0), src.get("to_a", 0)
        self.pval = src.get("pval", 0) if self.art else 0      # (a kind's pval is a lantern's fuel, a ring's 0)
        m = re.search(r"\(([+-]\d+),([+-]\d+)\)", n)
        if m:
            self.to_h, self.to_d = int(m.group(1)), int(m.group(2))
        m = re.search(r"\[(\d+),([+-]\d+)\]", n)
        if m:
            self.ac, self.to_a = int(m.group(1)), int(m.group(2))
        else:
            m = re.search(r"\[([+-]\d+)\]", n)
            if m:
                self.to_a = int(m.group(1))
            else:
                m = re.search(r"\[(\d+)\]", n)
                if m:
                    self.ac = int(m.group(1))
        # single (+n) groups: before the [..] on armour = to-hit; otherwise (after dice/(h,d)/[..]) = pval
        cut = n.find("[")
        for m in re.finditer(r"\(([+-]\d+)\)", n):
            if self.tval and self.tval not in WEAPON_TVALS and self.tval not in (19, 40, 45) and cut > 0 and \
                    m.start() < cut:
                self.to_h = int(m.group(1))
            else:
                self.pval = int(m.group(1))

    def stat_bonus(self):
        return {s: self.pval for s in STATS if s in self.flags} if self.pval else {}

    def abilities(self):
        return {f for f in self.flags if f in ABILITY_FLAGS or f.startswith(("RES_", "IM_", "SUST_"))}

    def __repr__(self):
        return f"Item({self.name!r}, {self.slot})"


# ------------------------------------------------------------------ the character
def stat_index(v):
    return max(0, min(37, v - 3 if v <= 18 else 15 + (v - 18) // 10))


def modify_stat_value(value, amount):
    """xtra1.c modify_stat_value: +1 is +1 below 18, +10 (18/10) above."""
    for _ in range(max(0, amount)):
        value = value + 1 if value < 18 else value + 10
    for _ in range(max(0, -amount)):
        if value >= 18 + 10:
            value -= 10
        elif value > 18:
            value = 18
        elif value > 3:
            value -= 1
    return value


def blows(weight, str_v, dex_v, extra=0, cls=WARRIOR):
    """xtra1.c: blows with a weapon of `weight` tenth-pounds at these stat values."""
    t = stat_table()
    si, di = stat_index(str_v), stat_index(dex_v)
    if weight // 10 > t[si]["adj_str_hold"]:
        return 1
    div = max(weight, cls[1])
    p = min(11, t[si]["adj_str_blow"] * cls[2] // div)
    d = min(11, t[di]["adj_dex_blow"])
    return max(1, min(cls[0], blows_table()[p][d])) + extra


class Character:
    """The character as the sheet shows it with its worn gear, and what any other loadout would give.

    stats: {'STR': value as used (18/70 = 88), ...}; mhp, ac: the sheet's totals; worn: {slot: [Item]}.
    The gear-free parts (stat_cur, player_hp, the base AC and to-hit) are backed out of the sheet once."""

    def __init__(self, clvl, stats, mhp, ac, worn, flags=(), depth_ft=700, inv=None):
        self.clvl, self.depth_ft = clvl, depth_ft
        self.worn = {s: list(v) for s, v in worn.items()}
        self.sheet = dict(stats=dict(stats), mhp=mhp, ac=ac)
        self.sheet_flags = set(flags)
        self.inv = dict(inv or {})
        bonus = self._stat_bonus(self.worn)
        self.stat_cur = {s: modify_stat_value(v, -bonus.get(s, 0)) for s, v in stats.items()}
        t = stat_table()
        con_i = stat_index(stats["CON"])
        self.player_hp = mhp - t[con_i]["adj_con_mhp"] * clvl // 100
        gear_ac = sum(i.ac + i.to_a for v in self.worn.values() for i in v)
        self.ac_other = ac - gear_ac - t[stat_index(stats["DEX"])]["adj_dex_ta"]     # (spells, timed effects)
        self.extra_flags = self.sheet_flags - self._flags(self.worn)                 # (race: Half-Orc resist dark)

    @staticmethod
    def _stat_bonus(worn):
        out = {}
        for v in worn.values():
            for i in v:
                for s, b in i.stat_bonus().items():
                    out[s] = out.get(s, 0) + b
        return out

    @staticmethod
    def _flags(worn):
        return set().union(*[i.abilities() for v in worn.values() for i in v]) if worn else set()

    def derive(self, worn=None):
        """The numbers a loadout gives (worn: {slot: [Item]}; default the current one)."""
        worn = self.worn if worn is None else worn
        t = stat_table()
        bonus = self._stat_bonus(worn)
        st = {s: modify_stat_value(v, bonus.get(s, 0)) for s, v in self.stat_cur.items()}
        si, di, ci = stat_index(st["STR"]), stat_index(st["DEX"]), stat_index(st["CON"])
        weapon = (worn.get("weapon") or [None])[0]
        extra = sum(i.pval for v in worn.values() for i in v if "BLOWS" in i.flags)
        nb = blows(weapon.weight, st["STR"], st["DEX"], extra) if weapon else 1
        others = [i for s, v in worn.items() if s not in ("weapon", "bow") for i in v]
        to_h = sum(i.to_h for i in others) + t[di]["adj_dex_th"] + t[si]["adj_str_th"]
        to_d = sum(i.to_d for i in others) + t[si]["adj_str_td"]
        w_h, w_d = (weapon.to_h, weapon.to_d) if weapon else (0, 0)
        dn, ds = (int(x) for x in (weapon.dice if weapon else "1d1").split("d"))
        dmg = nb * (dn * (ds + 1) / 2 + w_d + to_d)
        ac = sum(i.ac + i.to_a for v in worn.values() for i in v) + t[di]["adj_dex_ta"] + self.ac_other
        mhp = max(self.clvl + 1, self.player_hp + t[ci]["adj_con_mhp"] * self.clvl // 100)
        speed = sum(i.pval for v in worn.values() for i in v if "SPEED" in i.flags)
        flags = self._flags(worn) | self.extra_flags
        return dict(stats=st, blows=nb, dice=f"{dn}d{ds}", tohit=w_h + to_h, todam=w_d + to_d, dmg=round(dmg, 1),
                    ac=ac, mhp=mhp, speed=speed, flags=flags)

    def check(self):
        """The model against the sheet: (field, model, sheet) where they differ."""
        d = self.derive()
        out = []
        for k in ("ac", "mhp"):
            if d[k] != self.sheet[k]:
                out.append((k, d[k], self.sheet[k]))
        for s, v in self.sheet["stats"].items():
            if d["stats"][s] != v:
                out.append((s, d["stats"][s], v))
        return out

    def swap(self, item, slot_index=0):
        """The loadout with `item` worn in its slot (in place of the piece at slot_index for rings)."""
        worn = {s: list(v) for s, v in self.worn.items()}
        v = worn.setdefault(item.slot, [])
        if item.slot == "ring" and len(v) < 2:
            v.append(item)
        elif v:
            v[min(slot_index, len(v) - 1)] = item
        else:
            v.append(item)
        return worn


# ------------------------------------------------------------------ scenarios
def _sim():
    if ADVISOR_SIM not in sys.path:
        sys.path.insert(0, ADVISOR_SIM)
    import options_sim                              # noqa: E402
    return options_sim


def encounters(decisions, lo_ft, hi_ft, n=40, radius=7, since=None, seed=1):
    """The fights Dive04 met at lo-hi ft: `mons` records with a monster within 3 squares, the monsters within
    `radius` (distance as the simulator measures it), at most one record per 30 s; n of them, spread over the log."""
    S = _sim()
    out, last = [], 0.0
    for line in open(decisions):
        if '"kind": "mons"' not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if since and r["t"] < since or not r.get("pos") or r["t"] - last < 30:
            continue
        d = (r.get("depth") or 0) * 50
        if not lo_ft <= d <= hi_ft:
            continue
        y0, x0 = r["pos"]
        team = [(nm, max(1, S.adist(y - y0, x - x0))) for y, x, nm in r["monsters"] if nm in S.RACES]
        team = [m for m in team if m[1] <= radius]
        if not team or min(m[1] for m in team) > 3:
            continue
        last = r["t"]
        out.append({"team": team[:12], "depth": d // 50, "t": r["t"]})
    if len(out) > n:
        out = random.Random(seed).sample(out, n)
    return out


def hard_fights():
    """The 21 replayed emergencies (the Advisor's replay study): their teams and arrivals, at full HP."""
    S = _sim()
    out = []
    try:
        names = sorted(os.listdir(REPLAYS))
    except OSError:
        return out
    for f in names:
        try:
            ep = json.load(open(os.path.join(REPLAYS, f)))
        except (OSError, ValueError):
            continue
        y0, x0 = ep["player"]["pos"]
        team = [(m["name"], max(1, S.adist(m["y"] - y0, m["x"] - x0))) for m in ep["monsters_t0"]
                if m["name"] in S.RACES]
        arr = []
        for a in ep.get("arrivals") or []:
            if a["name"] in S.RACES and a["t"] > ep["t0"]:
                arr.append((int((a["t"] - ep["t0"]) / 0.625), a["name"], max(1, a.get("dist") or 5)))
        if team:
            out.append({"team": team, "arrivals": arr, "depth": ep["depth_ft"] // 50, "ep": f})
    return out


# ------------------------------------------------------------------ simulation
def sim_player(d, ch, depth):
    """The simulator's player from derived numbers (full HP: a gear choice is made before the fight)."""
    S = _sim()
    inv = dict(ccw=0, csw=0, clw=0, phase=0, tele=0, staff=0, wor=1, speed=0, berserk=0, hero=0)
    inv.update(ch.inv)
    return dict(hp=d["mhp"], mhp=d["mhp"], ac=d["ac"], clvl=ch.clvl, depth=depth, stairs=None,
                free_action="FREE_ACT" in d["flags"], res_blind="RES_BLIND" in d["flags"],
                res_conf="RES_CONF" in d["flags"], save=S.SAVE, max_adj=3, blows=d["blows"], dice=d["dice"],
                tohit=d["tohit"], todam=d["todam"], inv=inv)


def simulate(ch, derived, scenarios, n=20, p_awake=None):
    """Rollouts of every scenario under the base policy, n seeds each; per option: the metrics. p_awake 1.0: every
    monster comes (a fight we take on: kill speed shows; at the simulator's 0.4 most turns are spent waiting)."""
    S = _sim()
    out = {}
    for name, d in derived.items():
        lows, near, blocks, xp, spent, cleared, dead = [], 0, [], 0.0, 0.0, 0, 0
        for k, sc in enumerate(scenarios):
            p = sim_player(d, ch, sc["depth"])
            if p_awake is not None:
                p["p_awake"] = p_awake
            for i in range(n):
                r = S.rollout(p, sc["team"], [], seed=1000 * k + i, arrivals=sc.get("arrivals", ()))
                frac = r["low"] / d["mhp"]
                lows.append(frac)
                near += frac <= NEAR_DEATH
                dead += r["dead"]
                blocks.append(r["blocks"] + 1)
                xp += r["xp"]
                spent += r["spent"]
                cleared += r["escaped"] == "cleared"
        runs = len(scenarios) * n
        out[name] = dict(runs=runs, p_near=near / runs, p_dead=dead / runs, low_mean=statistics.fmean(lows),
                         low_p10=sorted(lows)[runs // 10], turns=statistics.fmean(blocks), xp_turn=xp / sum(blocks),
                         spent=spent / runs, cleared=cleared / runs)
    return out


# ------------------------------------------------------------------ the evaluator
def compare(ch, options, decisions=None, n=20, lo_ft=None, hi_ft=None, hard=True, xp_per_gold=0.41, no_loss=False):
    """options: {label: loadout ({slot: [Item]})}, the first being the current one. Returns a report dict.
    no_loss: an option that loses any ability or resist is ruled out (the Pilot's automatic swaps: the simulator
    doesn't model elemental resists, so losing one would look free)."""
    lo_ft = lo_ft or max(50, ch.depth_ft - 100)
    hi_ft = hi_ft or ch.depth_ft
    t0 = time.time()
    derived = {k: ch.derive(v) for k, v in options.items()}
    cur = next(iter(derived))
    rules = {}
    for k, d in derived.items():
        lost = derived[cur]["flags"] - d["flags"]
        gained = d["flags"] - derived[cur]["flags"]
        veto = sorted(label(f) for f in lost if f in REQUIRED and ch.depth_ft >= REQUIRED[f])
        rules[k] = dict(lost=sorted(lost), gained=sorted(gained), veto=veto)
    sets = {}
    if decisions:
        sets["met"] = encounters(decisions, lo_ft, hi_ft)
    if hard:
        sets["hard"] = hard_fights()
    sims = {s: simulate(ch, derived, sc, n=n, p_awake=1.0 if s == "met" else None) for s, sc in sets.items() if sc}
    # verdict: vetoes; then safety in the hard fights (a worse near-death rate by more than noise); then XP per turn
    # net of consumables in the fights met (XP_PER_GOLD converts the gold spent)
    score, notes = {}, {}
    for k in options:
        why = []
        if rules[k]["veto"]:
            why.append("loses " + ", ".join(rules[k]["veto"]))
        elif no_loss and rules[k]["lost"]:
            why.append("loses " + ", ".join(label(f) for f in rules[k]["lost"]) + " (an automatic swap never does)")
        if "hard" in sims and k != cur:
            a, b = sims["hard"][cur], sims["hard"][k]
            se = ((a["p_near"] * (1 - a["p_near"]) + b["p_near"] * (1 - b["p_near"])) / max(1, a["runs"])) ** 0.5
            if b["p_near"] - a["p_near"] > max(0.01, 2 * se):
                why.append(f"less safe in the hard fights (near death {b['p_near']:.1%} vs {a['p_near']:.1%})")
        m = sims.get("met", sims.get("hard"))
        score[k] = (m[k]["xp_turn"] - m[k]["spent"] * xp_per_gold / max(1e-9, m[k]["turns"])) if m else 0.0
        notes[k] = why
    ok = [k for k in options if not notes[k]]
    # (ties within 1% go to the safer option: lowest HP in the hard fights, then AC -- swapping the Ring of Protection
    # [+10] rather than the [+12] for the same kill speed)
    top = max((score[k] for k in ok), default=0)

    def safety(k):
        h = sims.get("hard", {}).get(k)
        return (round(h["low_mean"], 2) if h else 0, derived[k]["ac"], k == cur)
    best = max((k for k in ok if score[k] >= top * 0.99), key=safety) if ok else cur
    # (a change must beat the current gear by more than 3% to be worth a swap: the simulation's noise)
    if best != cur and score[best] < score[cur] * 1.03:
        best = cur
    return dict(options=list(options), derived=derived, rules=rules, sims=sims, score=score, notes=notes,
                best=best, sets={s: len(v) for s, v in sets.items()}, seconds=round(time.time() - t0, 1),
                check=ch.check())


def compare_slot(ch, candidates, **kw):
    """The item slot evaluator: the current gear against each candidate in its slot (each ring slot for a ring)."""
    options, swaps = {"current": ch.worn}, {"current": None}
    for it in candidates:
        if not it.slot:
            continue
        on = ch.worn.get(it.slot) or []
        if it.slot == "ring" and len(on) == 2:
            for j, r in enumerate(on):
                options[f"{it.name} for {r.name}"] = ch.swap(it, j)
                swaps[f"{it.name} for {r.name}"] = (it.name, r.name)
        else:
            k = f"{it.name}" + (f" for {on[0].name}" if on else " (empty slot)")
            options[k] = ch.swap(it)
            swaps[k] = (it.name, on[0].name if on else None)
    res = compare(ch, options, **kw)
    res["swaps"] = swaps          # label -> (the item worn, the piece it replaces or None)
    return res


def report(res):
    """The comparison as text."""
    lines = []
    if res["check"]:
        lines.append("model vs sheet (the model is off here): " + ", ".join(f"{k} {a} vs {b}" for k, a, b in
                                                                             res["check"]))
    for k in res["options"]:
        d, r = res["derived"][k], res["rules"][k]
        st = " ".join(f"{s} {fmt_stat(d['stats'][s])}" for s in ("STR", "DEX", "CON"))
        lines.append(f"{'*' if k == res['best'] else ' '} {k}")
        lines.append(f"    {st} | blows {d['blows']} | ~{d['dmg']:.0f}/round | to-hit {d['tohit']} | AC {d['ac']} | "
                     f"HP {d['mhp']}" + (f" | speed +{d['speed']}" if d["speed"] else ""))
        if r["lost"] or r["gained"]:
            lines.append("    abilities: " + (("+" + ", +".join(label(f) for f in r["gained"])) if r["gained"]
                                              else "") + (" " if r["gained"] and r["lost"] else "") +
                         (("-" + ", -".join(label(f) for f in r["lost"])) if r["lost"] else ""))
        for s, sim in res["sims"].items():
            m = sim[k]
            lines.append(f"    sim {s:4} ({res['sets'][s]} fights x {m['runs'] // max(1, res['sets'][s])}): "
                         f"{m['turns']:.1f} turns/fight, XP/turn {m['xp_turn']:.2f}, lowest HP {m['low_mean']:.0%} "
                         f"(p10 {m['low_p10']:.0%}), near death {m['p_near']:.1%}, consumables {m['spent']:.0f} g")
        if res["notes"][k]:
            lines.append("    against: " + "; ".join(res["notes"][k]))
    cur = res["options"][0]
    gain = res["score"][res["best"]] / res["score"][cur] - 1 if res["score"][cur] else 0
    lines.append(f"verdict: {res['best']}" + (" (keep what's worn)" if res["best"] == cur else
                                             f" ({gain:+.0%} XP per turn net of consumables)") +
                 f" -- {res['seconds']} s")
    return "\n".join(lines)


def fmt_stat(v):
    return str(v) if v <= 18 else ("18/" + str(v - 18) if v < 18 + 100 else f"18/{v - 18}")


# ------------------------------------------------------------------ demo: the Ring of Strength question (m45)
DIVE04_WORN = ["Battle Axe of Westernesse (2d8) (+10,+9) (+1)", "Ring of Protection [+12]", "Ring of Protection [+10]",
               "Amulet of Resist Lightning", "Hard Studded Leather of Resistance (-1) [7,+8]", "Shadow Cloak [6,+2]",
               "Orcish Shield [5,+4]", "Metal Cap [3,+4]", "Set of Gauntlets [2,+5]",
               "Pair of Metal Shod Boots [6,+0]", "Brass Lantern"]


def demo(args):
    worn = {}
    for n in DIVE04_WORN:
        it = Item(n)
        worn.setdefault(it.slot, []).append(it)
    ch = Character(28, {"STR": 88, "INT": 5, "WIS": 8, "DEX": 38, "CON": 38, "CHR": 4}, mhp=340, ac=76, worn=worn,
                   flags={"FREE_ACT", "SEE_INVIS", "RES_FIRE", "RES_COLD", "RES_ELEC", "RES_ACID", "RES_DARK"},
                   depth_ft=750, inv=dict(ccw=20, csw=4, phase=18, wor=2, staff=6, hero=3))
    cands = [Item(n) for n in args.items] or [Item("Ring of Strength (+2)")]
    dec = "/projectnb/jbrcs/mangband/runs/pilot/dive04/decisions.jsonl"
    res = compare_slot(ch, cands, decisions=dec if os.path.exists(dec) else None, n=args.n)
    print(report(res))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("items", nargs="*")
    a = ap.parse_args()
    demo(a)
