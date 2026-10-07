#!/usr/bin/env python3
"""Parse MAngband 1.5 lib/edit/monster.txt into monsters.csv (one row per monster).

Usage: python3 parse_monsters.py [monster.txt] [out.csv]
Columns: see README.md. Blows are also given as blow1..blow4 (METHOD:EFFECT:DICE).
"""
import csv, re, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "/projectnb/jbrcs/mangband/github/lib/edit/monster.txt"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/projectnb/jbrcs/mangband/Advisor/data/monsters/monsters.csv"


def dice_avg_max(d):
    m = re.fullmatch(r"(\d+)d(\d+)", d or "")
    if not m:
        return "", ""
    n, s = int(m.group(1)), int(m.group(2))
    return n * (s + 1) / 2, n * s


def parse(path):
    mons, cur = [], None
    for lineno, raw in enumerate(open(path, encoding="latin-1"), 1):
        line = raw.rstrip("\n")
        if not line or line.startswith("#") or len(line) < 2 or line[1] != ":":
            continue
        tag, rest = line[0], line[2:]
        if tag == "N":
            idx, name = rest.split(":", 1)
            cur = dict(idx=int(idx), name=name, line=lineno, blows=[], spells=[], flags=[], desc=[],
                       spell_freq="")
            mons.append(cur)
        elif cur is None:
            continue
        elif tag == "G":
            cur["symbol"], cur["color"] = rest[0], rest[2:]
        elif tag == "I":
            sp, hp, vis, ac, alert = rest.split(":")
            cur.update(speed=int(sp), hp_dice=hp, vision=int(vis), ac=int(ac), alertness=int(alert))
        elif tag == "W":
            lev, rar, _unused, exp = rest.split(":")
            cur.update(level=int(lev), rarity=int(rar), exp=int(exp))
        elif tag == "B":
            parts = rest.split(":")
            parts += [""] * (3 - len(parts))
            cur["blows"].append(parts[:3])
        elif tag == "S":
            for tok in (t.strip() for t in rest.split("|")):
                if not tok:
                    continue
                if tok.startswith("1_IN_"):
                    cur["spell_freq"] = int(tok[5:])
                else:
                    cur["spells"].append(tok)
        elif tag == "F":
            cur["flags"] += [t.strip() for t in rest.split("|") if t.strip()]
        elif tag == "D":
            cur["desc"].append(rest)
    return [m for m in mons if m["idx"] != 0]


def main():
    mons = parse(SRC)
    cols = ["idx", "name", "symbol", "color", "level", "rarity", "speed", "hp_dice", "hp_avg", "hp_max",
            "vision", "ac", "alertness", "exp", "n_blows", "blow1", "blow2", "blow3", "blow4",
            "melee_max", "blow_effects", "spell_freq", "spells", "flags", "unique", "src_line", "desc"]
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for m in mons:
            avg, mx = dice_avg_max(m.get("hp_dice"))
            if "FORCE_MAXHP" in m["flags"] and mx != "":
                avg = mx
            blows = [":".join(b).rstrip(":") for b in m["blows"]]
            melee_max = sum(dice_avg_max(b[2])[1] or 0 for b in m["blows"])
            effects = sorted({b[1] for b in m["blows"] if b[1] and b[1] != "HURT"})
            w.writerow([m["idx"], m["name"], m.get("symbol", ""), m.get("color", ""), m.get("level", ""),
                        m.get("rarity", ""), m.get("speed", ""), m.get("hp_dice", ""), avg, mx,
                        m.get("vision", ""), m.get("ac", ""), m.get("alertness", ""), m.get("exp", ""),
                        len(blows), *(blows + [""] * 4)[:4], melee_max, "|".join(effects),
                        m["spell_freq"], "|".join(m["spells"]), "|".join(m["flags"]),
                        int("UNIQUE" in m["flags"]), m["line"], " ".join(d.strip() for d in m["desc"])])
    print(f"wrote {len(mons)} monsters to {OUT}")


if __name__ == "__main__":
    main()
