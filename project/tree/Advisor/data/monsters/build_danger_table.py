#!/usr/bin/env python3
"""Build danger_table.csv: monsters.csv + the Clerks' ratings (danger-table study, B1-B4)
+ columns computed from the 1.5 code + the Advisor's overrides (advisor_overrides.csv).

Computed columns (formulas from github/src/server, verified 2026-09-27):
  speed_x      actions per normal-speed player turn (tables.c:2169 extract_energy / 1000)
  melee_avg    average damage per monster turn if every blow hits (dice only)
  melee_max    maximum damage per monster turn (every blow hits for its max roll; the Borg's measure)
  drain_blows  number of stat-drain (LOSE_*) or experience-drain (EXP_*) blows
  breath       each breath as NAME=avg/max, from avg and max HP (melee2.c:634-872: hp/3 or hp/6, capped)
  breath_avg_max  the largest breath average
  tags         PARA_BLOW, BLIND_BLOW, CONF_BLOW (no save), HOLD, BRAIN, SUMMON, TELE_TO, INVIS,
               EMPTY_MIND, BREEDER, PACK (FRIENDS/ESCORT), UNIQUE, NEVER_MOVE, PASS_WALL, KILL_WALL
"""
import csv, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.join(HERE, "../../studies/2026-09-27-danger-table/scratch")
BREATH = {"ACID": (3, 1600), "ELEC": (3, 1600), "FIRE": (3, 1600), "COLD": (3, 1600), "POIS": (3, 800),
          "NETH": (6, 550), "LITE": (6, 400), "DARK": (6, 400), "CONF": (6, 400), "SOUN": (6, 500),
          "CHAO": (6, 500), "DISE": (6, 500), "NEXU": (6, 400), "TIME": (3, 150), "INER": (6, 200),
          "GRAV": (3, 200), "SHAR": (6, 500), "PLAS": (6, 150), "WALL": (6, 200)}
ENERGY = [100] * 60 + [100] * 10 + [200] * 17 + [300] * 8 + [400] * 5 + \
         [500, 500, 500, 500, 600, 600, 700, 700, 800, 900] + list(range(1000, 3000, 100)) + \
         [3000, 3100, 3200, 3300, 3400, 3500, 3600, 3600, 3700, 3700]


def dice(d):
    m = re.fullmatch(r"(\d+)d(\d+)", d or "")
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def computed(r):
    flags, spells = set(r["flags"].split("|")), set(r["spells"].split("|"))
    blows = [b.split(":") for b in (r["blow1"], r["blow2"], r["blow3"], r["blow4"]) if b]
    melee = sum(n * (s + 1) / 2 for n, s in (dice(b[2]) if len(b) > 2 else (0, 0) for b in blows))
    melee_max = sum(n * s for n, s in (dice(b[2]) if len(b) > 2 else (0, 0) for b in blows))
    drains = sum(1 for b in blows if len(b) > 1 and (b[1].startswith("LOSE_") or b[1].startswith("EXP_")))
    sp = int(r["speed"])
    speed_x = ENERGY[sp] / 1000 if sp < len(ENERGY) else 3.7
    hp_avg, hp_max = float(r["hp_avg"] or 0), float(r["hp_max"] or 0)
    br, best = [], 0
    for s in sorted(spells):
        if s.startswith("BR_") and s[3:] in BREATH:
            div, cap = BREATH[s[3:]]
            a, m = min(int(hp_avg) // div, cap), min(int(hp_max) // div, cap)
            br.append(f"{s[3:]}={a}/{m}")
            best = max(best, a)
    effects = {b[1] for b in blows if len(b) > 1}
    tags = []
    for cond, t in [("PARALYZE" in effects, "PARA_BLOW"), ("BLIND" in effects, "BLIND_BLOW"),
                    ("CONFUSE" in effects, "CONF_BLOW"), ("HOLD" in spells, "HOLD"),
                    ("BRAIN_SMASH" in spells, "BRAIN"), (any(s.startswith("S_") for s in spells), "SUMMON"),
                    ("TELE_TO" in spells, "TELE_TO"), ("INVISIBLE" in flags, "INVIS"),
                    ("EMPTY_MIND" in flags, "EMPTY_MIND"), ("MULTIPLY" in flags, "BREEDER"),
                    (bool(flags & {"FRIENDS", "ESCORT", "ESCORTS"}), "PACK"), ("UNIQUE" in flags, "UNIQUE"),
                    ("NEVER_MOVE" in flags, "NEVER_MOVE"), ("PASS_WALL" in flags, "PASS_WALL"),
                    ("KILL_WALL" in flags, "KILL_WALL")]:
        if cond:
            tags.append(t)
    return dict(speed_x=speed_x, melee_avg=round(melee, 1), melee_max=melee_max, drain_blows=drains, breath=" ".join(br), breath_avg_max=best,
                tags="|".join(tags))


def main():
    mons = {r["idx"]: r for r in csv.DictReader(open(os.path.join(HERE, "monsters.csv")))}
    clerk = {}
    for b in ("B1", "B2", "B3", "B4"):
        p = os.path.join(STUDY, f"{b}_table.csv")
        if os.path.exists(p):
            for r in csv.DictReader(open(p)):
                r["band"] = b
                clerk[r["idx"]] = r
    over = {}
    p = os.path.join(HERE, "advisor_overrides.csv")
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            over[r["idx"]] = r
    cols = ["idx", "name", "level", "depth_ft", "symbol", "color", "danger", "response", "threats",
            "neutraliser", "safe_when", "notes", "clerk_danger", "clerk_response", "advisor_note", "band",
            "speed", "speed_x", "hp_dice", "hp_avg", "melee_avg", "melee_max", "drain_blows", "breath", "breath_avg_max", "spell_freq",
            "spells", "tags", "src_line"]
    out = []
    for idx, m in mons.items():
        if int(m["level"]) > 40:
            continue
        c, o = clerk.get(idx, {}), over.get(idx, {})
        row = dict(idx=idx, name=m["name"], level=m["level"], depth_ft=int(m["level"]) * 50,
                   symbol=m["symbol"], color=m["color"], band=c.get("band", ""),
                   clerk_danger=c.get("danger", ""), clerk_response=c.get("response", ""),
                   speed=m["speed"], hp_dice=m["hp_dice"], hp_avg=m["hp_avg"], spell_freq=m["spell_freq"],
                   spells=m["spells"], src_line=m["src_line"], advisor_note=o.get("advisor_note", ""))
        for k in ("danger", "response", "threats", "neutraliser", "safe_when", "notes"):
            row[k] = o.get(k) or c.get(k, "")
        row.update(computed(m))
        out.append(row)
    out.sort(key=lambda r: (int(r["level"]), int(r["idx"])))
    with open(os.path.join(HERE, "danger_table.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    print(f"wrote {len(out)} rows; clerk-rated {sum(1 for r in out if r['clerk_danger'])}; overrides {len(over)}")


if __name__ == "__main__":
    main()
