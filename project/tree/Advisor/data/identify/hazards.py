#!/usr/bin/env python3
"""Odds that ONE unknown item of a tval, found at object level L, is of each hazard class when used
or worn by our warrior (classes from study 2026-10-07-selling dispatches P and D, code-checked).
Rings/amulets: kinds that can roll a cursed (negative) version do so with prob (1-f)f, f=(L+10)%
(apply_magic, object2.c ~3187-3235). Also prints the Staff of Teleportation / Perception device-fail
chance by clvl (cmd6.c:477-501: chance = skill - level; <3 -> 1/(4-chance) becomes 3; fail if
randint1(chance) < 3); warrior skill_dev = -3 (Half-Orc) + 18 + adj_int_dev (0..1) + 7*clvl/10."""
import collections, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dist import level_dist, kinds as KINDS, FLAV

CLASS = {
    "potion": {"Death": "LETHAL", "Detonations": "LETHAL", "Ruination": "PERMANENT stat loss",
               "Weakness": "drain STR/DEX/CON", "Clumsiness": "drain STR/DEX/CON", "Sickliness": "drain STR/DEX/CON",
               "Stupidity": "drain INT/WIS/CHR", "Naivety": "drain INT/WIS/CHR", "Ugliness": "drain INT/WIS/CHR",
               "Lose Memories": "exp -25%", "Sleep": "nuisance", "Blindness": "nuisance", "Confusion": "nuisance",
               "Poison": "nuisance", "Slowness": "nuisance", "Salt Water": "nuisance (eat at once)"},
    "scroll": {"Summon Monster": "DANGEROUS (summons/aggravate)", "Summon Undead": "DANGEROUS (summons/aggravate)",
               "Aggravate Monster": "DANGEROUS (summons/aggravate)", "Curse Weapon": "wrecks worn gear",
               "Curse Armor": "wrecks worn gear", "Trap Creation": "nuisance", "Darkness": "nuisance",
               "Teleport Level": "nuisance", "*Destruction*": "nuisance", "Acquirement": "JACKPOT (sell it!)",
               "*Acquirement*": "JACKPOT (sell it!)"},
    "staff": {"Summoning": "DANGEROUS (summons/aggravate)", "Haste Monsters": "DANGEROUS if monsters in view",
              "Darkness": "nuisance", "Slowness": "nuisance"},
    "wand": {"Heal Monster": "helps the monster", "Haste Monster": "helps the monster",
             "Clone Monster": "helps the monster", "Polymorph": "helps the monster"},
    "rod": {},
    "ring": {k: "CURSED, sticks" for k in ("Teleportation", "Weakness", "Stupidity", "Aggravate Monster", "Woe")},
    "amulet": {k: "CURSED, sticks" for k in ("Teleportation", "DOOM")},
}
MAYBE_CURSED = {"ring": {"Searching", "Protection", "Damage", "Accuracy", "Slaying", "Strength", "Dexterity",
                         "Constitution", "Intelligence", "Speed"},
                "amulet": {"Wisdom", "Charisma", "Searching", "Infravision", "Speed"}}

levels = [int(a) for a in sys.argv[1:]] or [2, 5, 10, 15, 20, 25, 30]
for tn in ("potion", "scroll", "staff", "wand", "ring", "amulet"):
    tv = [k for k, v in FLAV.items() if v == tn][0]
    table = collections.defaultdict(dict)
    for L in levels:
        d = level_dist(L)
        ks = {k: p for k, p in d.items() if KINDS[k].get("tval") == tv}
        tot = sum(ks.values())
        f = min(L + 10, 75) / 100      # f1 in apply_magic is capped at 75 (assumed, as in 3.0)
        for k, p in ks.items():
            name = KINDS[k]["name"]
            c = CLASS[tn].get(name)
            if c:
                table[c][L] = table[c].get(L, 0) + p / tot
            elif name in MAYBE_CURSED.get(tn, ()):
                table["CURSED, sticks"][L] = table["CURSED, sticks"].get(L, 0) + p / tot * (1 - f) * f
        if tn == "potion":
            table["bad, any"][L] = sum(table[c].get(L, 0) for c in table if c != "bad, any")
    print(f"\n{tn}: % of unknown {tn}s by class, at object level " + " ".join(f"{L:>6d}" for L in levels))
    for c, row in sorted(table.items()):
        print(f"  {c:34s}" + " ".join(f"{100*row.get(L,0):6.2f}" for L in levels))

print("\ndevice fail % for a Half-Orc warrior (INT adj 0 / +1):")
def fail(skill, lev):
    ch = skill - min(lev, 50)
    if ch >= 3:
        return 2 / ch
    p_raise = 1 / (3 - ch + 1) if ch < 3 else 0
    return (1 - p_raise) + p_raise * 2 / 3
for name, lev in (("Perception", 10), ("Teleportation", 20), ("Speed / Earthquakes", 40)):
    print(f"  Staff of {name:18s} (lvl {lev}): " + "  ".join(
        f"clvl {cl}: {100*fail(-3+18+0+7*cl//10, lev):.0f}/{100*fail(-3+18+1+7*cl//10, lev):.0f}"
        for cl in (10, 15, 20, 25, 30, 35)))
