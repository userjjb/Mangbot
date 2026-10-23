"""itemvalue -- what an item is worth, from the server's data and its object_value_real().

The rulebook's first table (restructure step 2.1; the Advisor's starting-over memo §3.2):
the Pilot's item policy and the scorecard both read it, so nobody quotes a value from memory.

value(name) reads an item's display name ("a Pair of Soft Leather Boots of Free Action [2,+4]",
"5 Potions of Cure Light Wounds", "a Wand of Stinking Cloud (12 charges)") and returns an Item
with .value (gold, as object2.c object_value_real computes it: kind cost, or artifact cost, +
ego cost, + pval flags, + 100 per to-hit/to-dam/to-AC plus, + 5% per charge; 0 when cursed,
broken or minus-plussed), .known (False for unidentified flavours and pseudo-ID'd gear, whose
value is then an expectation), and .irreplaceable (what it gives can't be bought back easily).
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
EDIT = os.path.join(HERE, "..", "..", "lib", "edit")

TV = {"shot": 16, "arrow": 17, "bolt": 18, "bow": 19, "digging": 20, "hafted": 21, "polearm": 22, "sword": 23,
      "boots": 30, "gloves": 31, "helm": 32, "crown": 33, "shield": 34, "cloak": 35, "soft": 36, "hard": 37,
      "dragon": 38, "light": 39, "amulet": 40, "ring": 45, "staff": 55, "wand": 65, "rod": 66, "scroll": 70,
      "potion": 75, "flask": 77, "food": 80}
WEAPONS = {19, 20, 21, 22, 23}
ARMOUR = {30, 31, 32, 33, 34, 35, 36, 37, 38}
AMMO = {16, 17, 18}
PVAL_GEAR = WEAPONS | ARMOUR | AMMO | {39, 40, 45}
FLAVOURED = {"Potion": 75, "Scroll": 70, "Ring": 45, "Amulet": 40, "Wand": 65, "Staff": 55, "Rod": 66}
PVAL_COST = {"STR": 200, "INT": 200, "WIS": 200, "DEX": 200, "CON": 200, "CHR": 200, "STEALTH": 100,
             "SEARCH": 100, "INFRA": 50, "TUNNEL": 50, "BLOWS": 2000}
SPEED_COST = {40: 25000, 45: 50000}       # amulets, rings; everything else 100000 per +1
IRREPLACEABLE_FLAGS = {"FREE_ACT", "SEE_INVIS", "RES_POIS", "RES_BLIND", "RES_CONF", "HOLD_LIFE", "SPEED",
                       "TELEPATHY", "REGEN", "RES_ACID", "RES_ELEC", "RES_FIRE", "RES_COLD"}
# Expected values for what isn't known yet (estimates until the Advisor's rulebook tables, step 3):
# an unknown flavour by type (the identify memo: 87-750), and pseudo-ID'd gear over its kind's cost
UNKNOWN_FLAVOUR = {75: 100, 70: 100, 45: 500, 40: 500, 65: 300, 55: 300, 66: 800}
PSEUDO_BONUS = {"average": 0, "good": 500, "excellent": 2500, "special": 10000, "magical": 500,
                "worthless": None, "cursed": None, "broken": None, "terrible": None}


def _norm(n):
    n = re.sub(r"&\s*", "", n)
    n = re.sub(r"~", "", n)
    return re.sub(r"\s+", " ", n).strip()


def _read(path):
    """Entries of an edit file: [{'N': name, 'I': [...], 'W': [...], 'F': set(), 'D': ...}]."""
    out, cur = [], None
    for line in open(os.path.join(EDIT, path), errors="replace"):
        line = line.rstrip("\n")
        if line.startswith("N:"):
            cur = {"N": _norm(line.split(":", 2)[2]), "F": set()}
            out.append(cur)
        elif cur is not None and len(line) > 2 and line[1] == ":":
            k, v = line[0], line[2:]
            if k == "F":
                cur["F"] |= {f.strip() for f in v.split("|") if f.strip()}
            elif k in "IWX":
                cur[k] = [int(x) if re.fullmatch(r"-?\d+", x.strip()) else x for x in v.split(":")]
            elif k == "P":
                cur["P"] = v.split(":")
            elif k == "T":
                cur.setdefault("T", []).append(int(v.split(":")[0]))
    return out


KINDS = [k for k in _read("object.txt") if "I" in k and "W" in k]
EGOS = {}
for _e in _read("ego_item.txt"):
    if "W" in _e:
        EGOS.setdefault(_e["N"], []).append(_e)      # (two "of Venom": weapons, ammunition)
ARTIFACTS = {a["N"]: a for a in _read("artifact.txt") if "W" in a}
_BY_TV_NAME = {(k["I"][0], k["N"].lower()): k for k in KINDS}
# gear kinds by base name, longest first ("Hard Studded Leather" before "Studded Leather")
_GEAR = sorted(((k["N"].lower(), k) for k in KINDS if k["I"][0] in PVAL_GEAR | {77, 80}),
               key=lambda kv: -len(kv[0]))


class Item:
    __slots__ = ("name", "kind", "tval", "count", "value", "known", "ego", "artifact", "flags", "irreplaceable",
                 "pseudo", "estimate")

    def __repr__(self):
        return (f"Item({self.name!r}: value {self.value}{' (estimate)' if self.estimate else ''}, "
                f"known={self.known}, irreplaceable={self.irreplaceable})")


def _plural_free(s):
    s = re.sub(r"\b(Potion|Scroll|Ring|Amulet|Wand|Rod|Flask|Ration|Pair|Set)s\b", r"\1", s)
    return re.sub(r"\bStaves\b", "Staff", s)


def value(name):
    """An Item for a display name (one of a stack; .count has the stack size)."""
    it = Item()
    it.name, it.kind, it.tval, it.ego, it.artifact, it.flags = name, None, None, None, None, set()
    it.known, it.estimate, it.irreplaceable, it.value = True, False, False, 0
    raw = name.strip()
    m = re.match(r"(\d+) ", raw)
    it.count = int(m.group(1)) if m else 1
    tags = re.findall(r"\{([^}]*)\}", raw)
    pseudo = next((t.split(",")[0].strip() for t in tags if t.split(",")[0].strip() in PSEUDO_BONUS), None)
    it.pseudo = pseudo
    n = re.sub(r"\s*\{[^}]*\}", "", raw)
    n = re.sub(r"^(an?|the|\d+) ", "", n)
    charges = re.search(r"\((\d+) charges?\)", n)
    hd = re.search(r"\(([+-]\d+),([+-]\d+)\)", n)                 # (to-hit, to-dam)
    ac = re.search(r"\[(\d+)(?:,([+-]\d+))?\]", n)                 # [base AC, to-AC]
    ac_only = re.search(r"\[([+-]\d+)\]", n)                       # rings of protection [+8]
    pv = re.search(r"<([+-]\d+)>|\(([+-]\d+)\)(?!\s*\()", n)       # <+5> or a lone (+2)
    dice = re.search(r"\((\d+)d(\d+)\)", n)
    core = _plural_free(re.sub(r"\s*[\[(<].*$", "", n)).strip()
    if re.search(r"\b(cursed|broken|worthless|terrible)\b", " ".join(tags), re.I) or core.startswith("Broken "):
        it.value = 0
        return it
    # flavoured kinds: "Potion of X"; unknown flavours: "Bloodstone Ring", "Scroll titled ..."
    fm = re.match(r"(Potion|Scroll|Ring|Amulet|Wand|Staff|Rod) of (.+)", core)
    if fm:
        it.tval = FLAVOURED[fm.group(1)]
        k = _BY_TV_NAME.get((it.tval, fm.group(2).lower()))
        if not k:
            return it
        it.kind = k["N"]
        it.flags = set(k["F"])
        val = k["W"][3]
    elif re.match(r".+ (Potion|Ring|Amulet|Wand|Staff|Rod)$", core) or core.startswith("Scroll titled"):
        tv = FLAVOURED.get(core.split()[-1], 70)
        it.tval, it.known, it.estimate = tv, False, True
        it.value = UNKNOWN_FLAVOUR.get(tv, 100)
        return it
    else:
        low = core.lower()
        hit = next(((kn, k) for kn, k in _GEAR if low == kn or low.startswith(kn + " ")), None)
        if not hit:
            return it
        kn, k = hit
        it.kind, it.tval = k["N"], k["I"][0]
        it.flags = set(k["F"])
        val = k["W"][3]
        rest = core[len(kn):].strip()
        if rest:
            if rest in EGOS:
                e = next((x for x in EGOS[rest] if it.tval in x.get("T", [])), EGOS[rest][0])
                it.ego, it.flags = rest, it.flags | e["F"]
                val += e["W"][3]
            elif rest.lstrip("of ").strip() in ARTIFACTS or rest in ARTIFACTS:
                a = ARTIFACTS.get(rest) or ARTIFACTS.get(rest.lstrip("of ").strip())
                it.artifact, it.flags, val = rest, it.flags | a["F"], a["W"][3]
    if not val:
        it.value = 0
        return it
    # pval flags (stats, speed, blows ...) on gear and jewellery. On armour and weapons a
    # lone "(-1)" is the to-hit (Hard Studded Leather (-1) [7,+9]), so only <+N> counts there
    hit_only = 0
    if it.tval in ARMOUR | WEAPONS:
        lone = re.search(r"\(([+-]\d+)\)(?!\s*\()", n) if not hd else None
        hit_only = int(lone.group(1)) if lone else 0
        pv = re.search(r"<([+-]\d+)>", n)
    p = int(pv.group(1) or (pv.group(2) if pv.lastindex and pv.lastindex > 1 else 0) or 0) \
        if pv and it.tval in PVAL_GEAR else 0
    if p < 0 and it.tval in PVAL_GEAR:
        it.value = 0
        return it
    if p:
        for f, cost in PVAL_COST.items():
            if f in it.flags:
                val += p * cost
        if "SPEED" in it.flags:
            val += p * SPEED_COST.get(it.tval, 100000)
    th, td = (int(hd.group(1)), int(hd.group(2))) if hd else (hit_only, 0)
    ta = int(ac.group(2)) if ac and ac.group(2) else (int(ac_only.group(1)) if ac_only else 0)
    if it.tval in (65, 55) and charges:
        val += (val // 20) * int(charges.group(1)) // max(1, it.count)
    elif it.tval in (40, 45):
        if ta < 0 or th < 0 or td < 0:
            it.value = 0
            return it
        val += (th + td + ta) * 100
    elif it.tval in ARMOUR:
        if ta < 0:
            it.value = 0
            return it
        val += (th + td + ta) * 100
    elif it.tval in WEAPONS:
        if th + td < 0:
            it.value = 0
            return it
        val += (th + td + ta) * 100
        k = _BY_TV_NAME.get((it.tval, it.kind.lower())) if it.kind else None
        if dice and k and k.get("P"):
            kd = re.match(r"(\d+)d(\d+)", k["P"][1] or "")
            if kd and int(dice.group(1)) > int(kd.group(1)) and int(dice.group(2)) == int(kd.group(2)):
                val += (int(dice.group(1)) - int(kd.group(1))) * int(dice.group(2)) * 100
    elif it.tval in AMMO:
        val += (th + td) * 5
    # what isn't known yet: pseudo-ID'd gear (no plusses shown), unknown charges
    if it.tval in WEAPONS | ARMOUR and not hd and not (ac and ac.group(2)) and pseudo and not it.ego:
        bonus = PSEUDO_BONUS.get(pseudo)
        if bonus is None:
            it.value = 0
            return it
        if bonus:
            val += bonus
            it.known, it.estimate = False, True
    if it.tval in (65, 55) and not charges:
        it.known, it.estimate = False, True
        val += (val // 20) * 5               # charges unknown: ~5 expected
    it.value = val
    it.irreplaceable = bool(it.flags & IRREPLACEABLE_FLAGS) and it.tval in PVAL_GEAR
    return it


if __name__ == "__main__":
    import sys
    for n in sys.argv[1:] or ["a Pair of Soft Leather Boots of Free Action [2,+4]", "a Spear (1d6) (+5,+7)",
                              "Hard Studded Leather of Resistance (-1) [7,+9]", "a Ring of Protection [+8]",
                              "5 Potions of Cure Light Wounds", "a Wand of Stinking Cloud (12 charges)",
                              "a Lucerne Hammer of Venom (2d5) (+2,+3)", "a Bloodstone Ring", "a Scimitar (2d5)",
                              "a Pair of Soft Leather Boots [2] {excellent}", "a Ring of Speed <+5>",
                              "a Staff of Door/Stair Location", "a Robe [2] {good}", "a Flask of oil"]:
        print(value(n))
