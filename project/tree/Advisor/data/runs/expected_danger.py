#!/usr/bin/env python3
"""Worst-case vs expected group danger per second, from decisions.jsonl `mons` records.

worst    = Σ over monsters within reach (dist <= 1 + speed_x) of melee_max × speed_x + 50 × drain_blows
           (the Pilot's rule since 7b592c5, drain weight 50).
expected = Σ over the same monsters of speed_x × Σ_blows P(hit) × E[damage], + 50 × P(hit) per drain blow,
           with the 1.5 formulas (melee1.c:105-127, 243-271, 504-516):
           P(hit) = 0.05 + 0.90 × max(0, i − ⌊3·AC/4⌋)/i,  i = power(effect) + 3 × monster level;
           HURT/SHATTER damage reduced by dam × min(AC,150)/250; others unreduced.
Usage: python3 expected_danger.py dive04 [AC ...]   → prints per-episode summaries; writes <nick>_expected.csv
"""
import csv, json, re, sys, datetime
nick = sys.argv[1] if len(sys.argv) > 1 else "dive04"
ACS = [int(a) for a in sys.argv[2:]] or [15, 20]
POWER = dict(HURT=60, POISON=5, UN_BONUS=20, UN_POWER=15, EAT_GOLD=5, EAT_ITEM=5, EAT_FOOD=5, EAT_LITE=5,
             ACID=0, ELEC=10, FIRE=10, COLD=10, BLIND=2, CONFUSE=10, TERRIFY=10, PARALYZE=2, LOSE_STR=0,
             LOSE_DEX=0, LOSE_CON=0, LOSE_INT=0, LOSE_WIS=0, LOSE_CHR=0, LOSE_ALL=2, SHATTER=60,
             EXP_10=5, EXP_20=5, EXP_40=5, EXP_80=5, HALLU=10)
M = {r["name"]: r for r in csv.DictReader(open("/projectnb/jbrcs/mangband/Advisor/data/monsters/monsters.csv"))}
T = {r["name"]: r for r in csv.DictReader(open("/projectnb/jbrcs/mangband/Advisor/data/monsters/danger_table.csv"))}
def dice(d):
    m = re.fullmatch(r"(\d+)d(\d+)", d or ""); return (int(m.group(1)), int(m.group(2))) if m else (0, 0)
def threat(name, ac):
    m, t = M.get(name), T.get(name)
    if not m: return None
    sx = float(t["speed_x"]) if t else max(1.0, (int(m["speed"]) - 100) / 10)
    lev = max(1, int(m["level"])); worst = 0.0; exp = 0.0
    for b in (m["blow1"], m["blow2"], m["blow3"], m["blow4"]):
        if not b: continue
        p = b.split(":"); eff = p[1] if len(p) > 1 and p[1] else ""; n, s = dice(p[2] if len(p) > 2 else "")
        drain = eff.startswith("LOSE_") or eff.startswith("EXP_")
        worst += n * s + (50 if drain else 0)
        if not eff: continue            # message-only blows (INSULT, MOAN…) never damage
        i = POWER.get(eff, 0) + 3 * lev
        ph = 0.05 + (0.90 * max(0, i - (3 * ac) // 4) / i if i > 0 else 0)
        avg = n * (s + 1) / 2
        if eff in ("HURT", "SHATTER"): avg -= avg * min(ac, 150) / 250
        exp += ph * (avg + (50 if drain else 0))
    return worst * sx, exp * sx, sx
rows = []
for l in open(f"/projectnb/jbrcs/mangband/runs/pilot/{nick}/decisions.jsonl"):
    r = json.loads(l)
    if r.get("kind") != "mons" or not r.get("pos") or not r.get("hp"): continue
    py, px = r["pos"]; hp = r["hp"][0]
    out = dict(t=r["t"], time=datetime.datetime.fromtimestamp(r["t"]).strftime("%H:%M:%S"), hp=hp, hpmax=r["hp"][1])
    near = []
    for ac in ACS:
        w = e = 0.0
        for y, x, name in r["monsters"]:
            th = threat(name, ac)
            if not th: continue
            d = max(abs(y - py), abs(x - px))
            if d <= 1 + th[2]:
                w += th[0]; e += th[1]
                if ac == ACS[0]: near.append(f"{name}@{d}")
        out[f"worst"] = round(w); out[f"exp_ac{ac}"] = round(e, 1)
    out["worst_ratio"] = round(out["worst"] / max(hp, 1), 2)
    for ac in ACS: out[f"exp_ratio_ac{ac}"] = round(out[f"exp_ac{ac}"] / max(hp, 1), 3)
    out["in_reach"] = "; ".join(near)
    out["in_view"] = "; ".join(f"{n}@{max(abs(y-py),abs(x-px))}" for y, x, n in r["monsters"])
    rows.append(out)
with open(f"/projectnb/jbrcs/mangband/Advisor/data/runs/{nick}_expected.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(f"{len(rows)} mons samples")
for r in rows:
    if r["worst_ratio"] >= 0.3 or any(k in r["in_view"] for k in ("Bullroarer", "Giant red frog", "Cave spider")):
        print(r["time"], f'hp {r["hp"]}/{r["hpmax"]}', "worst", r["worst"], r["worst_ratio"], "| exp",
              *(f'{r[f"exp_ac{a}"]}({r[f"exp_ratio_ac{a}"]})' for a in ACS), "| reach:", r["in_reach"][:60], "| view:", r["in_view"][:70])
