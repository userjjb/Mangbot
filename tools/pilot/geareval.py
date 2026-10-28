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
SHEET_FLAG = {"RES_CONF": "RES_CONFU", "RES_NETHER": "RES_NETHR", "RES_SHARDS": "RES_SHARD", "SEE_INV": "SEE_INVIS",
              "FREE_ACTION": "FREE_ACT"}


def label(f):
    """'RES_POIS' -> 'resist poison', 'SUST_STR' -> 'sustain STR', 'FREE_ACT' -> 'Free Action'."""
    if f in LABEL:
        return LABEL[f]
    el = {"POIS": "poison", "ELEC": "lightning", "CONF": "confusion", "CONFU": "confusion", "NETHR": "nether", "BLIND": "blindness", "SHARD": "shards",
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
        # the egos named in brackets: 'a Sabre (Holy Avenger) (2d7) ...' (the base name stops at the bracket)
        if self.kind and not self.ego and not self.art:
            m = re.search(r"\(([A-Za-z][A-Za-z' ]+)\)", n)
            if m:
                self.ego = next((e for e in egos().get(_norm(f"({m.group(1)})"), ()) if self.kind["tval"] in e["tvals"]),
                                None)
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


# ------------------------------------------------------------------ slays and brands
# (options_sim 2026-10-27k, the Advisor's slays memo: the multiplier applies to the dice only, the best one wins;
# cmd1.c tot_dam_aux)
SLAY_MULT = {"SLAY_EVIL": ("EVIL", 2), "SLAY_ANIMAL": ("ANIMAL", 2), "SLAY_UNDEAD": ("UNDEAD", 3),
             "SLAY_DEMON": ("DEMON", 3), "SLAY_ORC": ("ORC", 3), "SLAY_TROLL": ("TROLL", 3), "SLAY_GIANT": ("GIANT", 3),
             "SLAY_DRAGON": ("DRAGON", 3), "KILL_DRAGON": ("DRAGON", 5), "KILL_DEMON": ("DEMON", 5),
             "KILL_UNDEAD": ("UNDEAD", 5)}
BRAND_MULT = {"BRAND_ACID": "ACID", "BRAND_ELEC": "ELEC", "BRAND_FIRE": "FIRE", "BRAND_COLD": "COLD",
              "BRAND_POIS": "POIS"}
# the HP-weighted share of monsters with each race flag (the Advisor, scenarios.make, 3000 draws; flags overlap)
RACE_MIX = {750: {"EVIL": .65, "ORC": .27, "TROLL": .09, "GIANT": .05, "UNDEAD": .02, "DEMON": .04, "ANIMAL": .24,
                  "DRAGON": .04},
            1000: {"EVIL": .52, "ORC": .25, "TROLL": .05, "GIANT": .04, "UNDEAD": .02, "DEMON": .03, "ANIMAL": .37,
                   "DRAGON": .03}}


def weapon_mults(weapon):
    """({race flag: mult}, {element: mult}) of a weapon's slays and brands."""
    slays, brands = {}, {}
    for f in (weapon.flags if weapon else ()):
        if f in SLAY_MULT:
            race, m = SLAY_MULT[f]
            slays[race] = max(slays.get(race, 1), m)
        elif f in BRAND_MULT:
            brands[BRAND_MULT[f]] = 3
    return slays, brands


def mean_mult(slays, depth_ft):
    """The expected dice multiplier over the depth's monsters: 1 + the sum of share x (mult - 1), capped where the
    best multiplier would win (an approximation: the flags overlap -- undead and demons are evil)."""
    mix = RACE_MIX[750 if depth_ft < 875 else 1000]
    return 1 + min(sum(mix.get(r, 0) * (m - 1) for r, m in slays.items()), max([m - 1 for m in slays.values()] or [0]))


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

    def __init__(self, clvl, stats, mhp, ac, worn, flags=(), depth_ft=700, inv=None, pack_weight=0):
        self.clvl, self.depth_ft = clvl, depth_ft
        self.pack_weight = pack_weight          # (tenth-pounds carried in the pack: the weight limit's other half)
        self.worn = {s: list(v) for s, v in worn.items()}
        self.sheet = dict(stats=dict(stats), mhp=mhp, ac=ac)
        # (the Pilot's sheet names -> the game's flag names)
        self.sheet_flags = {SHEET_FLAG.get(f, f) for f in flags}
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
        # encumbrance (xtra1.c:2772): over half the weight limit (adj_str_wgt x 100 tenth-pounds), -1 speed a tenth
        limit = t[si]["adj_str_wgt"] * 100
        load = self.pack_weight + sum(i.weight for v in worn.values() for i in v)
        if load > limit // 2:
            speed -= (load - limit // 2) // (limit // 10)
        flags = self._flags(worn) | self.extra_flags
        slays, brands = weapon_mults(weapon)
        return dict(stats=st, blows=nb, dice=f"{dn}d{ds}", tohit=w_h + to_h, todam=w_d + to_d, dmg=round(dmg, 1),
                    ac=ac, mhp=mhp, speed=speed, flags=flags, slays=slays, brands=brands,
                    wweight=weapon.weight if weapon else 0)

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
    # (m48's close call at 750 ft, the Advisor's request: a Light hound pack -- blindness keeps scrolls unreadable, so
    # resist blindness/light is decisive there, which the random depth sets rarely draw)
    lh = [("Light hound", 2 + k % 5) for k in range(13)] + [("Warg", 3 + k % 4) for k in range(7)] + \
        [("Mirkwood spider", 4 + k % 3) for k in range(5)] + [("Druid", 6)]
    if all(n in S.RACES for n, _ in lh):
        out.append({"team": lh, "arrivals": [], "depth": 15, "ep": "m48-light-hounds"})
    return out


# ------------------------------------------------------------------ simulation
# the simulator's resist flags (options_sim 2026-10-26f) from the game's flag names (an immunity counts as the resist)
SIM_RES = {"RES_ACID": "res_acid", "RES_ELEC": "res_elec", "RES_FIRE": "res_fire", "RES_COLD": "res_cold",
           "IM_ACID": "res_acid", "IM_ELEC": "res_elec", "IM_FIRE": "res_fire", "IM_COLD": "res_cold",
           "RES_POIS": "res_pois", "RES_NETHR": "res_neth", "RES_CHAOS": "res_chaos", "RES_SHARD": "res_shard",
           "RES_NEXUS": "res_nexus", "RES_DISEN": "res_disen", "RES_SOUND": "res_sound", "RES_CONFU": "res_conf",
           "RES_LITE": "res_lite", "RES_DARK": "res_dark", "RES_BLIND": "res_blind"}
# what the Pilot's automatic swaps may never lose: the abilities that gate escapes and fights (the Advisor, 10-26: the
# elemental resists are simulated now and may be traded for a measured gain)
NO_LOSS = {"FREE_ACT", "SEE_INVIS", "RES_BLIND", "RES_CONFU", "HOLD_LIFE"}
# whether the automatic swaps may trade the other resists for a measured gain (10-26: a plain
# Metal Scale Mail [38,+5] beat the Leather of Resistance by ~21% in the simulation)
TRADE_RESISTS = False          # (the user, 10-26: option B -- automatic swaps keep every resist)
# resting: regenhp (dungeon.c:1245-1306) heals (mhp x 197 x 2 + 1442) / 65536 HP a block (one normal-speed player
# turn of game time) while resting. Fight and rest turns are both game time (the Advisor, 10-26: an earlier /4.5 for
# the time bubble mixed clocks and under-weighted HP lost -- the AC side of every comparison)


# Real time (the user, 10-26: score in wall time, as missions are scored in XP per dungeon minute): a fight block takes
# BLOCK_S at normal time; a resting block takes BLOCK_S / REST_SPEEDUP -- measured from 25 rests in m43-m47 (clvl
# 27-28): HP regained per wall second vs regenhp's rate at 1x, pooled 2.6x (median 2.2; ~8x when the time bubble
# applies, ~1x or less when a monster is in view or the rest is cut short)
BLOCK_S = 0.625
REST_SPEEDUP = 2.6


def rest_turns(hp_lost, mhp):
    """Blocks of resting to regain hp_lost."""
    return hp_lost / ((mhp * 394 + 1442) / 65536) if hp_lost > 0 else 0.0


def sim_player(d, ch, depth):
    """The simulator's player from derived numbers (full HP: a gear choice is made before the fight)."""
    S = _sim()
    inv = dict(ccw=0, csw=0, clw=0, phase=0, tele=0, staff=0, wor=1, speed=0, berserk=0, hero=0)
    inv.update(ch.inv)
    p = dict(hp=d["mhp"], mhp=d["mhp"], ac=d["ac"], clvl=ch.clvl, depth=depth, stairs=None,
             free_action="FREE_ACT" in d["flags"], save=S.SAVE, max_adj=3, blows=d["blows"], dice=d["dice"],
             tohit=d["tohit"], todam=d["todam"], inv=inv)
    for f in d["flags"]:
        if f in SIM_RES:
            p[SIM_RES[f]] = True
    # (options_sim 27k: slays and brands on the dice, criticals from the weapon's weight)
    if d.get("slays"):
        p["slays"] = dict(d["slays"])
    if d.get("brands"):
        p["brands"] = dict(d["brands"])
    if d.get("wweight"):
        p["weight"] = d["wweight"]
    return p


def simulate(ch, derived, scenarios, n=20, p_awake=None):
    """Rollouts of every scenario under the base policy, n seeds each, the same seeds for every option.
    Returns {option: [per-scenario totals {xp, turns, rest, spent, lows: [lowest HP / max], dead}]}.
    p_awake 1.0: every monster comes (a fight we take on: kill speed shows; at the simulator's 0.4 most turns are
    spent waiting)."""
    S = _sim()
    out = {}
    for name, d in derived.items():
        rows = []
        for k, sc in enumerate(scenarios):
            p = sim_player(d, ch, sc["depth"])
            if p_awake is not None:
                p["p_awake"] = p_awake
            row = dict(xp=0.0, turns=0, rest=0.0, spent=0.0, lows=[], dead=0)
            for i in range(n):
                r = S.rollout(p, sc["team"], [], seed=1000 * k + i, arrivals=sc.get("arrivals", ()))
                row["xp"] += r["xp"]
                row["turns"] += r["blocks"] + 1
                row["rest"] += rest_turns(d["mhp"] - max(0, r["end_hp"]), d["mhp"])
                row["spent"] += r["spent"]
                row["lows"].append(max(0, r["low"]) / d["mhp"])
                row["dead"] += r["dead"]
            rows.append(row)
        out[name] = rows
    return out


def summary(rows, xp_per_gold):
    """An option's metrics over a set's per-scenario rows. score = (XP - gold spent x XP-per-gold) per turn of fighting
    and resting back the HP lost (the Advisor, 10-26: AC and damage on one scale)."""
    lows = sorted(x for r in rows for x in r["lows"])
    runs = len(lows)
    xp, turns, rest = (sum(r[k] for r in rows) for k in ("xp", "turns", "rest"))
    spent = sum(r["spent"] for r in rows)
    wall_min = (turns + rest / REST_SPEEDUP) * BLOCK_S / 60
    return dict(runs=runs, score=(xp - spent * xp_per_gold) / max(1e-9, wall_min), turns=turns / runs,
                rest=rest / runs, xp=xp / runs, spent=spent / runs, p_near=sum(x <= NEAR_DEATH for x in lows) / runs,
                p_dead=sum(r["dead"] for r in rows) / runs, low_mean=statistics.fmean(lows),
                low_p10=lows[runs // 10], low_p5=lows[runs // 20], low_p1=lows[runs // 100])


def tail_interval(rows_a, rows_b, q=0.05, boots=300, seed=11):
    """The bootstrap 95% interval of B's q-quantile lowest HP less A's, resampling scenarios (paired: the same
    scenario indices for both)."""
    rng = random.Random(seed)
    k = len(rows_a)

    def quant(rows, idx):
        v = sorted(x for i in idx for x in rows[i]["lows"])
        return v[int(q * len(v))]
    d = []
    for _ in range(boots):
        idx = [rng.randrange(k) for _ in range(k)]
        d.append(quant(rows_b, idx) - quant(rows_a, idx))
    d.sort()
    return d[int(0.025 * boots)], d[int(0.975 * boots) - 1]


def paired_gain(rows_a, rows_b, xp_per_gold):
    """B's score less A's, and its standard error, paired by scenario (the same seeds; the delta method for a ratio of
    sums: SE from the scenario residuals)."""
    def tot(rows):
        return [(r["xp"] - r["spent"] * xp_per_gold, (r["turns"] + r["rest"] / REST_SPEEDUP) * BLOCK_S / 60)
                for r in rows]
    a, b = tot(rows_a), tot(rows_b)
    ta, tb = sum(t for _, t in a), sum(t for _, t in b)
    ra, rb = sum(x for x, _ in a) / ta, sum(x for x, _ in b) / tb
    tm = (ta + tb) / 2 / len(a)
    z = [((xb - rb * tbk) - (xa - ra * tak)) / tm for (xa, tak), (xb, tbk) in zip(a, b)]
    se = statistics.stdev(z) / len(z) ** 0.5 if len(z) > 1 else float("inf")
    return rb - ra, se


# ------------------------------------------------------------------ the evaluator
SCORE_SETS = ("met", "depth")              # where the score comes from (pooled)
SAFETY_SETS = ("hard", "depth", "deeper")  # where an option can be less safe


def _paired_gain_sets(sims, cur, k, xp_per_gold):
    rows_a = [r for s in SCORE_SETS if s in sims for r in sims[s][cur]]
    rows_b = [r for s in SCORE_SETS if s in sims for r in sims[s][k]]
    return paired_gain(rows_a, rows_b, xp_per_gold) if rows_a else (0.0, float("inf"))


def d_slower(derived, cur, k):
    return derived[k]["speed"] < derived[cur]["speed"]


def compare(ch, options, decisions=None, n=10, lo_ft=None, hi_ft=None, hard=True, depth_n=500, xp_per_gold=0.41,
            no_loss=False, skip=frozenset(), mix=None):
    """options: {label: loadout ({slot: [Item]})}, the first being the current one. Returns a report dict.
    Sets: met (the fights in the log at lo-hi ft, n seeds each), depth / deeper (the Advisor's scenarios.make at the
    depth and 100 ft deeper, boost 2 for auto_scum, depth_n each, one seed), hard (the 21 replays, n seeds).
    no_loss: an option losing one of NO_LOSS (Free Action, See Invisible, resist blindness/confusion, hold life) is
    ruled out -- the Pilot's automatic swaps; elemental resists are simulated and may be traded."""
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
        sets["met"] = (encounters(decisions, lo_ft, hi_ft), n, 1.0)
    if depth_n:
        try:
            if ADVISOR_SIM not in sys.path:
                sys.path.insert(0, ADVISOR_SIM)
            import scenarios as SC                 # noqa: E402
            for name, ft in (("depth", ch.depth_ft), ("deeper", ch.depth_ft + 100)):
                low = {u.lower() for u in skip}
                sc = SC.make(ft, depth_n, seed=7, boost=2,
                             skip=frozenset(r["name"] for r in SC.RACES.values() if r["name"].lower() in low))
                sets[name] = ([dict(x, depth=ft // 50) for x in sc], 1, 1.0)
        except Exception:                          # (no scenario generator: the other sets only)
            pass
    if hard:
        sets["hard"] = (hard_fights(), n, None)
    raw = {s: simulate(ch, derived, sc, n=nn, p_awake=pa) for s, (sc, nn, pa) in sets.items() if sc}
    sims = {s: {k: summary(rows, xp_per_gold) for k, rows in v.items()} for s, v in raw.items()}
    # the score: pooled over the score sets
    score = {}
    for k in options:
        rows = [r for s in SCORE_SETS if s in raw for r in raw[s][k]]
        score[k] = summary(rows, xp_per_gold)["score"] if rows else 0.0
    notes, gains = {}, {}
    for k in options:
        why = []
        if rules[k]["veto"]:
            why.append("loses " + ", ".join(rules[k]["veto"]))
        elif no_loss and set(rules[k]["lost"]) & (NO_LOSS if TRADE_RESISTS else set(rules[k]["lost"])):
            kept = sorted(set(rules[k]["lost"]) & NO_LOSS) if TRADE_RESISTS else rules[k]["lost"]
            why.append("loses " + ", ".join(label(f) for f in kept) + " (an automatic swap never does)")
        if k != cur and d_slower(derived, cur, k):
            why.append(f"slower (speed {derived[k]['speed']:+d} vs {derived[cur]['speed']:+d}: the weight limit; "
                       "the simulator doesn't model speed)")
        if k != cur:
            for s in SAFETY_SETS:
                if s not in sims:
                    continue
                a, b = sims[s][cur], sims[s][k]
                se = ((a["p_near"] * (1 - a["p_near"]) + b["p_near"] * (1 - b["p_near"])) / max(1, a["runs"])) ** 0.5
                if b["p_near"] - a["p_near"] > max(0.005, 2 * se):
                    why.append(f"less safe ({s}: near death {b['p_near']:.1%} vs {a['p_near']:.1%})")
                else:
                    # (the tail: the worst 5% of fights' lowest HP, B less A, with a bootstrap 95% interval over the
                    # scenarios -- the Advisor, 10-26: the data's own noise in place of fixed points)
                    lo, hi = tail_interval(raw[s][cur], raw[s][k])
                    if hi < 0:
                        why.append(f"less safe ({s}: the worst 5% of fights end at {b['low_p5']:.0%} HP vs "
                                   f"{a['low_p5']:.0%}; 95% interval {lo:+.1%} to {hi:+.1%})")
            gains[k] = _paired_gain_sets(raw, cur, k, xp_per_gold)
        notes[k] = why
    # the verdict: a change must beat the current gear by 3% and by 2 standard errors of the paired difference (the
    # Advisor, 10-26); ties within 1% go to the safer option (the hard fights' lowest HP, then AC)
    ok = [k for k in options if k == cur or (not notes[k] and gains[k][0] > max(0.03 * abs(score[cur]),
                                                                                 2 * gains[k][1]))]
    top = max(score[k] for k in ok)

    def safety(k):
        h = sims.get("hard", {}).get(k) or sims.get("deeper", {}).get(k)
        return (round(h["low_mean"], 2) if h else 0, derived[k]["ac"], k == cur)
    best = max((k for k in ok if score[k] >= top * 0.99), key=safety)
    mx, lvl, src = mix or (DEFAULT_MIX, DEFAULT_MELEE_LEVEL, "the default mix")
    return dict(options=list(options), derived=derived, rules=rules, sims=sims, score=score, notes=notes,
                gains=gains, best=best, sets={s: len(v[0]) for s, v in sets.items()},
                seconds=round(time.time() - t0, 1), check=ch.check(),
                ehp={k: round(ehp(d, mx, lvl)) for k, d in derived.items()}, ehp_src=src)


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
    res["unread"] = [it.name for it in candidates if not it.slot]
    res["swaps"] = swaps          # label -> (the item worn, the piece it replaces or None)
    return res


# ------------------------------------------------------------------ the loadout optimizer
OPT_SLOTS = ("weapon", "body", "cloak", "shield", "helm", "gloves", "boots", "amulet", "ring")


def _dominated(a, b, ch):
    """b is at least as good as a in its slot on every static count (AC, to-hit, to-dam, abilities, stat bonuses,
    speed, weight, price) -- a weapon by the damage it gives alone."""
    if not a.flags <= b.flags or any(b.stat_bonus().get(s, 0) < v for s, v in a.stat_bonus().items()):
        return False
    if a.slot == "weapon":
        da, db = ch.derive(ch.swap(a)), ch.derive(ch.swap(b))
        return db["dmg"] >= da["dmg"] and db["tohit"] >= da["tohit"] and b.ac + b.to_a >= a.ac + a.to_a
    return (b.ac + b.to_a >= a.ac + a.to_a and b.to_h >= a.to_h and b.to_d >= a.to_d and b.weight <= a.weight
            and getattr(b, "price", 0) <= getattr(a, "price", 0))


# ------------------------------------------------------------------ effective HP
# (the user, 10-28: "add the EHP column to gearcmp and loadout"). EHP = the HP an unarmoured, unresisted character
# would need to last as long: max HP x (damage taken with no AC and no resists) / (damage taken with this gear), over
# the damage mix the character actually took (observe/damage_mix.py -> runs/pilot/NICK/damage_mix.json)
DEFAULT_MIX = {"hurt": 0.51, "melee_other": 0.12, "fire": 0.13, "cold": 0.03, "lite": 0.016, "elec": 0.014,
               "pois": 0.009, "dark": 0.005, "shard": 0.003, "other": 0.16}   # (Dive04 at 700-800 ft, 10-24..10-28)
DEFAULT_MELEE_LEVEL = 13
# resists: the basic four and poison cut a third (immunity: nothing); the high resists x6/(d6+6), ~0.65 on average
EHP_RES = {"acid": (("RES_ACID", 1 / 3), ("IM_ACID", 0.0)), "elec": (("RES_ELEC", 1 / 3), ("IM_ELEC", 0.0)),
           "fire": (("RES_FIRE", 1 / 3), ("IM_FIRE", 0.0)), "cold": (("RES_COLD", 1 / 3), ("IM_COLD", 0.0)),
           "pois": (("RES_POIS", 1 / 3),), "lite": (("RES_LITE", 0.65),), "dark": (("RES_DARK", 0.65),),
           "shard": (("RES_SHARD", 0.65),), "nexus": (("RES_NEXUS", 0.65),), "sound": (("RES_SOUND", 0.65),),
           "nether": (("RES_NETHR", 0.65),), "chaos": (("RES_CHAOS", 0.65),), "disen": (("RES_DISEN", 0.65),)}


def hit_chance(ac, power, level):
    """melee1.c check_hit: 5% always hit, 5% always miss, else randint1(power + 3 x level) > 3/4 AC; blow power 60
    for HURT/SHATTER, 0-20 for the status blows (melee1.c:243-271)."""
    return 0.05 + 0.9 * max(0.0, 1 - 0.75 * ac / max(1, power + 3 * level))


def damage_factor(d, mix, level, armour=True):
    """The share of the mix's damage that gets through this gear (armour=False: no AC, no resists)."""
    ac = d["ac"] if armour else 0
    flags = d["flags"] if armour else set()
    f = 0.0
    for kind, share in mix.items():
        if kind == "hurt":
            f += share * hit_chance(ac, 60, level) * (1 - min(ac, 150) / 250)
        elif kind == "melee_other":
            f += share * hit_chance(ac, 8, level)
        elif kind in EHP_RES:
            f += share * min([m for flag, m in EHP_RES[kind] if flag in flags] or [1.0])
        else:
            f += share
    return f


def ehp(d, mix=None, level=None):
    mix, level = mix or DEFAULT_MIX, level or DEFAULT_MELEE_LEVEL
    return d["mhp"] * damage_factor(d, mix, level, armour=False) / max(1e-9, damage_factor(d, mix, level))


def load_mix(path):
    """(mix, melee level, source text) from a damage_mix.json, or the defaults."""
    try:
        m = json.load(open(path))
        if m.get("mix"):
            return m["mix"], m.get("melee_level") or DEFAULT_MELEE_LEVEL, \
                f"damage taken at {m['range'][0]}-{m['range'][1]} ft since {m['since']} ({m['hp_lost']} HP)"
    except (OSError, ValueError, KeyError):
        pass
    return DEFAULT_MIX, DEFAULT_MELEE_LEVEL, "the default mix (Dive04 at 700-800 ft, 10-24..10-28)"


def proxy(d, cur, depth_ft=750, mix=None):
    """A static guess of a loadout's worth, to choose which few go to the simulation (the Advisor's slays memo,
    10-27): kill speed (blows x (mean dice x the depth's mean slay multiplier + to-dam)), staying power (the user,
    10-28: effective HP over the damage mix taken -- AC, HP and resists on one scale; mix = (mix, melee level, ...)
    as load_mix gives), speed."""
    import math
    mx, lvl = (mix[0], mix[1]) if mix else (None, None)

    def dmg(x):
        dn, ds = (int(v) for v in x["dice"].split("d"))
        return x["blows"] * (dn * (ds + 1) / 2 * mean_mult(x.get("slays") or {}, depth_ft) + x["todam"])
    return (math.log(max(1e-9, dmg(d)) / max(1e-9, dmg(cur)))
            + 0.5 * math.log(ehp(d, mx, lvl) / max(1e-9, ehp(cur, mx, lvl)))
            + 0.1 * (d["speed"] - cur["speed"]))


def optimize(ch, pool, budget=0, max_sim=5, **kw):
    """The loadout optimizer (design_gear.md): gear choices across slots, e.g. a Sabre (Holy Avenger) in place of
    the Free Action axe, worth it only with Free Action from a ring. pool: candidate Items (pack wearables; shop
    stock with an `price` attribute, gold). Loadouts = the worn set with one or two slots changed (a ring pair
    counts as one slot), keeping every ability and resist worn now (Free Action, See Invisible ... and, as
    TRADE_RESISTS is off, the elemental ones) and costing at most `budget`; dominated items are pruned per slot.
    The static proxy picks max_sim of them; geareval.compare simulates those against the current gear (no_loss).
    Returns compare's report dict with `changes` {label: [(item worn, the piece it replaces, price)]}."""
    import itertools
    cur = ch.derive()
    keep = {f for f in cur["flags"] if f in NO_LOSS or f in REQUIRED or (not TRADE_RESISTS and f.startswith(("RES_", "IM_")))}
    by_slot = {s: [i for i in pool if i.slot == s] for s in OPT_SLOTS}
    for s in OPT_SLOTS:                   # (prune: a candidate no better than a worn piece or another candidate)
        rivals = by_slot[s] + list(ch.worn.get(s, ()))
        by_slot[s] = [a for a in by_slot[s] if not any(b is not a and _dominated(a, b, ch) and not _dominated(b, a, ch)
                                                      for b in rivals)]
    # one slot's changes: (new pieces for the slot, [(item, replaced)])
    moves = {}
    for s, cands in by_slot.items():
        on = list(ch.worn.get(s, ()))
        out = []
        if s == "ring":
            pieces = on + cands
            for pair in itertools.combinations(range(len(pieces)), min(2, len(pieces))):
                new = [pieces[j] for j in pair]
                if {id(x) for x in new} == {id(x) for x in on}:
                    continue
                gone = [x for x in on if all(x is not y for y in new)]
                added = [x for x in new if all(x is not y for y in on)]
                out.append((new, list(itertools.zip_longest(added, gone))))
        else:
            for c in cands:
                out.append(([c], [(c, on[0] if on else None)]))
        if out:
            moves[s] = out
    combos = [[(s, m)] for s, ms in moves.items() for m in ms]
    combos += [[(s1, m1), (s2, m2)] for (s1, ms1), (s2, ms2) in itertools.combinations(moves.items(), 2)
               for m1 in ms1 for m2 in ms2]
    scored = []
    for combo in combos:
        worn = {s: list(v) for s, v in ch.worn.items()}
        changes = []
        for s, (new, ch_) in combo:
            worn[s] = list(new)
            changes += ch_
        cost = sum(getattr(a, "price", 0) for a, _ in changes if a is not None)
        if cost > budget:
            continue
        d = ch.derive(worn)
        if not keep <= d["flags"] or d["speed"] < cur["speed"]:
            continue
        scored.append((proxy(d, cur, ch.depth_ft, kw.get("mix")), worn, changes, cost))
    scored.sort(key=lambda x: -x[0])
    options, changes = {"current": ch.worn}, {"current": []}
    for pr, worn, chg, cost in scored[:max_sim]:
        if pr <= 0:
            break
        lab = " + ".join(f"{a.name}" + (f" (buy {getattr(a, 'price')} g)" if getattr(a, "price", 0) else "")
                         + (f" for {b.name}" if b else "") for a, b in chg if a is not None) or \
            " + ".join(f"take off {b.name}" for _, b in chg)
        options[lab] = worn
        changes[lab] = [(a.name if a else None, b.name if b else None, getattr(a, "price", 0) if a else 0)
                        for a, b in chg]
    res = compare(ch, options, no_loss=True, **kw) if len(options) > 1 else \
        dict(options=["current"], best="current", derived={"current": cur}, score={"current": 0.0}, notes={},
             rules={}, sims={}, gains={}, sets={}, seconds=0.0, check=ch.check(),
             ehp={"current": round(ehp(cur, *(kw.get("mix") or (None, None, None))[:2]))}, ehp_src="")
    res["changes"] = changes
    res["searched"] = dict(loadouts=len(scored), candidates={s: len(v) for s, v in by_slot.items() if v})
    return res


def report(res):
    """The comparison as text."""
    lines = []
    if res.get("unread"):
        lines.append("not a wearable this game knows (left out): " + ", ".join(res["unread"]))
    if res["check"]:
        lines.append("model vs sheet (the model is off here): " + ", ".join(f"{k} {a} vs {b}" for k, a, b in
                                                                             res["check"]))
    for k in res["options"]:
        d, r = res["derived"][k], res["rules"][k]
        st = " ".join(f"{s} {fmt_stat(d['stats'][s])}" for s in ("STR", "DEX", "CON"))
        lines.append(f"{'*' if k == res['best'] else ' '} {k}")
        e, e0 = (res.get("ehp") or {}).get(k), (res.get("ehp") or {}).get(res["options"][0])
        lines.append(f"    {st} | blows {d['blows']} | ~{d['dmg']:.0f}/round | to-hit {d['tohit']} | AC {d['ac']} | "
                     f"HP {d['mhp']}" + (f" | EHP {e}" + (f" ({e / e0 - 1:+.1%})" if e0 and k != res["options"][0]
                                                          else "") if e else "")
                     + (f" | speed +{d['speed']}" if d["speed"] else ""))
        if r["lost"] or r["gained"]:
            lines.append("    abilities: " + (("+" + ", +".join(label(f) for f in r["gained"])) if r["gained"]
                                              else "") + (" " if r["gained"] and r["lost"] else "") +
                         (("-" + ", -".join(label(f) for f in r["lost"])) if r["lost"] else ""))
        for s, sim in res["sims"].items():
            m = sim[k]
            lines.append(f"    sim {s:6} ({res['sets'][s]} x {m['runs'] // max(1, res['sets'][s])}): "
                         f"{m['turns']:.1f} turns + {m['rest']:.1f} resting/fight, {m['score']:.0f} XP/min, "
                         f"lowest HP {m['low_mean']:.0%} (worst 5% {m['low_p5']:.0%}, 1% {m['low_p1']:.0%}), near death {m['p_near']:.1%}, "
                         f"consumables {m['spent']:.0f} g")
        cur = res["options"][0]
        if k != cur and res["score"][cur]:
            g, se = res["gains"][k]
            lines.append(f"    {res['score'][k]:.1f} vs {res['score'][cur]:.1f} XP per real minute: {g / res['score'][cur]:+.1%} "
                         f"(+/- {2 * se / res['score'][cur]:.1%} at 2 SE)")
        if res["notes"][k]:
            lines.append("    against: " + "; ".join(res["notes"][k]))
    if res.get("ehp"):
        lines.append(f"EHP = the HP an unarmoured, unresisted character would need to last as long, over "
                     f"{res.get('ehp_src')} (AC cuts melee hits and wounds; resists cut their element)")
    cur = res["options"][0]
    gain = res["score"][res["best"]] / res["score"][cur] - 1 if res["score"][cur] else 0
    lines.append(f"verdict: {res['best']}" + (" (keep what's worn)" if res["best"] == cur else
                                             f" ({gain:+.1%} XP per real minute of fighting and resting, net "
                                             "of consumables)") + f" -- {res['seconds']} s. score = (XP - gold spent "
                 f"x XP-per-gold) / real minutes (fight turns x {BLOCK_S} s + rest turns x {BLOCK_S} s / "
                 f"{REST_SPEEDUP}); a change needs +3% and 2 SE")
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
