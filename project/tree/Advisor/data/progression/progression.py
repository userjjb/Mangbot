#!/usr/bin/env python3
"""Warrior progression numbers for Dive04 (Half-Orc Warrior), from the tables Clerk G1 extracted
(study 2026-10-07-progression, scratch/G1_*.csv; code lines in dispatch G1) and the gear list from G3.

blows: P = adj_str_blow[STR]*5 // max(30, weight), cap 11; D = adj_dex_blow[DEX], cap 11;
       blows = min(6, blows_table[P][D]) (xtra1.c:2950-2985; heavy if adj_str_hold < weight/10 -> 1 blow).
damage/blow = dice mean + adj_str_td[STR] + weapon to_d (crits ~2-3%, ignored) (cmd1.c:1460-1485).
hit chance = 0.05 + 0.90 * max(0, 1 - (3*AC//4)/chance), chance = skill_thn + 3*(to_h)
       skill_thn = 82 + 45*clvl//10; to_h = adj_dex_th + adj_str_th + weapon to_h (cmd1.c:51-70).
exp to reach clvl N = player_exp[N-2]*110//100; HP mean = 19 + 10*(clvl-1) + adj_con_mhp*clvl//100.
device fail: chance = (-3+18+adj_int_dev+7*clvl//10) - level; fail = 2/chance (chance >= 3).
Borg depth gate (warrior, not "risky"): clvl >= dl up to dl20; clvl >= dl+5 for dl21-38 (dispatch G2).
Usage: progression.py   (prints three tables)"""
import csv, os
SC = "/projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-progression/scratch"
T = {int(r["stat_ind"]): r for r in csv.DictReader(open(os.path.join(SC, "G1_stat_tables.csv")))}
BT = [[int(r[f"D{d}"]) for d in range(12)] for r in csv.DictReader(open(os.path.join(SC, "G1_blows_table.csv")))]
EXP = {int(r["reach_clvl"]): int(r["halforc_warrior_needed(base*110/100)"])
       for r in csv.DictReader(open(os.path.join(SC, "G1_player_exp.csv")))}
IND = {"18": 15, "18/10": 16, "18/20": 17, "18/30": 18, "18/40": 19, "18/50": 20, "18/70": 22, "18/100": 25, "17": 14, "16": 13}

def a(stat, col): return int(T[IND[stat]][col])

def blows(STR, DEX, wt):
    if a(STR, "adj_str_hold") < wt // 10:
        return 1
    P = min(11, a(STR, "adj_str_blow") * 5 // max(30, wt))
    D = min(11, a(DEX, "adj_dex_blow"))
    return min(6, BT[P][D])

def dice_mean(d):
    n, s = map(int, d.split("d")); return n * (s + 1) / 2

def p_hit(clvl, STR, DEX, ac, wto_h=0):
    chance = 82 + 45 * clvl // 10 + 3 * (a(DEX, "adj_dex_th") + a(STR, "adj_str_th") + wto_h)
    return 0.05 + 0.90 * max(0.0, 1 - (3 * ac // 4) / chance)

gear = [r for r in csv.DictReader(open(os.path.join(SC, "G3_gear.csv")))
        if r["kind"] in ("weapon", "melee", "hafted") or r["tval"] in ("TV_SWORD", "TV_HAFTED", "TV_POLEARM")]
seen, weapons = set(), []
for r in gear:
    name = r["notes"].split(" lvl")[0] if r["notes"] else r["sval"]
    key = (r["sval"], r["tval"])
    if key in seen or not r["dice"]:
        continue
    seen.add(key)
    weapons.append((name, r["dice"], int(r["weight"]), r["buy_min"], r["buy_max"], r["store"]))

print("== Melee per turn vs a monster of AC 30, clvl 11, DEX 18/10 (weight in lb) ==")
print(f"{'weapon':18s} {'dice':5s} {'lb':>4s} {'price':>9s} | STR 18: blows dmg/turn | STR 18/50: blows dmg/turn | +4 to-dam @18/50")
rows = []
for name, d, wt, lo, hi, st in weapons:
    out = []
    for STR in ("18", "18/50"):
        b = blows(STR, "18/10", wt)
        dpb = dice_mean(d) + a(STR, "adj_str_td")
        out.append((b, b * dpb * p_hit(11, STR, "18/10", 30)))
    b50 = out[1][0]
    plus4 = b50 * (dice_mean(d) + a("18/50", "adj_str_td") + 4) * p_hit(11, "18/50", "18/10", 30)
    rows.append((out[1][1], name, d, wt, lo, hi, out, plus4))
for dmg, name, d, wt, lo, hi, out, plus4 in sorted(rows, reverse=True):
    print(f"{name:18s} {d:5s} {wt/10:4.1f} {lo:>4s}-{hi:<4s} | {out[0][0]:5d} {out[0][1]:8.1f}  | {out[1][0]:9d} {out[1][1]:8.1f}  | {plus4:6.1f}")

print("\n== By clvl (CON 18, WIS 10, INT 5; HP is the mean of the random rolls, sd ~5.5*sqrt(clvl)) ==")
print("clvl  exp_to_reach  HP_mean  to-hit_chance  save%  StaffTele_fail%  Borg_max_ft")
for cl in range(10, 36):
    hp = 19 + 10 * (cl - 1) + a("18", "adj_con_mhp") * cl // 100
    ch = 82 + 45 * cl // 10
    sav = -3 + 18 + int(T[7]["adj_wis_sav"]) + 10 * cl // 10
    dev = -3 + 18 + 0 + 7 * cl // 10 - 20
    fail = 2 / dev if dev >= 3 else (1 - 1 / (4 - dev)) + (1 / (4 - dev)) * 2 / 3
    dl = cl if cl <= 20 else min(38, cl - 5) if cl >= 26 else 20
    print(f"{cl:4d} {EXP.get(cl, 0):12d} {hp:8d} {ch:13d} {sav:6d} {100*fail:15.0f} {dl*50:11d}")

# == Time to level (dungeon minutes), following the Borg depth gate ==
# Measured XP/min (study G4, kills only): Dive03 23/min at 250-500 ft (clvl ~13), 41/min at 500-750 ft
# (clvl ~19), 155/min at 750-1000 ft (clvl ~20, 15 min with 35 escapes: halved here to 75 as sustainable).
# Kill XP = mexp*mlevel/clvl, so a rate measured at clvl c0 scales by c0/clvl. Beyond 1000 ft: no data.
REF = [(500, 23, 13), (750, 41, 19), (1000, 75, 20)]
def rate(depth_ft, cl):
    for top, r, c0 in REF:
        if depth_ft <= top:
            return r * c0 / cl
    return None
print("\n== Projected dungeon minutes per level (Borg depth gate; Dive04 starts clvl 11 with 610 exp) ==")
print("clvl  depth_ft  XP/min  minutes  cumulative_h")
exp, cum = 610, 0.0
for cl in range(11, 26):
    dl = cl if cl <= 20 else 20
    r = rate(dl * 50, cl)
    need = EXP[cl + 1] - exp
    if r is None:
        print(f"{cl:4d} {dl*50:9d}   no data beyond 1000 ft"); break
    m = need / r; cum += m / 60; exp = EXP[cl + 1]
    print(f"{cl:4d} {dl*50:9d} {r:7.1f} {m:8.0f} {cum:12.1f}")
