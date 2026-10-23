#!/usr/bin/env python3
"""Monte Carlo of one melee duel: the player stands and fights one monster adjacent until it dies (or teleports away).

Gives the DISTRIBUTION of HP lost (mean, median, 90th, 95th percentile) and of turns, so a hunt check can use a real
percentile instead of "twice the expected turns". Same mechanics as monsters.csv (build_monsters.py), with dice rolled:
  player     per turn all blows; hit = 5% auto-hit / 5% auto-miss, else randint0(chance) >= 3/4 x monster AC with
             chance = 82 + 45*clvl//10 + 3*tohit (Half-Orc warrior skill_thn; cmd1.c, xtra1.c); damage = weapon dice +
             todam per hit (no criticals: slightly pessimistic)
  monster    hp rolled (hp_dice; FORCE_MAXHP = max); energy speed_x per player turn; each action casts with spell_pct
             (one spell, uniform over its list; damage as spell_dmg, breaths at CURRENT hp), else a melee round;
             MONSTER_RECOIL: a melee round costs two actions (melee2.c:3035-3044); blows hit with
             .05+.90*max(0,i-3ac/4)/i, i = power(effect)+3*level; HURT/SHATTER reduced by dmg*min(ac,150)/250
  BLINK      the monster steps away: 2 player turns with no player attacks; meanwhile it casts (spell_pct) or closes
  HEAL       +6 x level HP (capped at max)      TPORT/TELE_SELF: the fight ends (the monster escapes)
Ignored: status effects (paralysis etc. are separate hunt rules), fear/fleeing, summons, the player's criticals and
regeneration, other monsters.

usage: fight_sim.py MONSTER [--clvl 22 --blows 3 --dice 1d6 --todam 7 --tohit 5 --ac 56 --hp 265 --n 4000]"""
import argparse, csv, os, random, re, statistics
from build_monsters import POWER, spell_dmg, ENERGY, dice

HERE = os.path.dirname(os.path.abspath(__file__))
MON = "/projectnb/jbrcs/mangband/Advisor/data/monsters/monsters.csv"


def roll(n, s):
    return sum(random.randint(1, s) for _ in range(n)) if n and s else 0


def duel(m, o):
    flags = set(m["flags"].split("|")) if m["flags"] else set()
    spells = [s for s in m["spells"].split("|") if s] if m["spells"] else []
    rl = max(1, int(m["level"])); mac = int(m["ac"])
    hn, hs = dice(m["hp_dice"])
    hpmax = hn * hs if "FORCE_MAXHP" in flags else roll(hn, hs)
    hp = hpmax
    sx = ENERGY.get(int(m["speed"]), 1000) / 1000
    freq = int(m["spell_freq"]) if m["spell_freq"] else 0
    pct = (100 // freq) / 100 if freq else 0.0
    blows = []
    for b in (m["blow1"], m["blow2"], m["blow3"], m["blow4"]):
        if not b: continue
        p = b.split(":"); eff = p[1] if len(p) > 1 else ""
        if not eff: continue
        n, s = dice(p[2] if len(p) > 2 else ""); i = POWER.get(eff, 0) + 3 * rl
        blows.append((eff, n, s, 0.05 + 0.90 * max(0, i - (3 * o.ac) // 4) / i))
    chance = 82 + 45 * o.clvl // 10 + 3 * o.tohit
    pn, ps = dice(o.dice)
    lost, turns, energy, away, escaped = 0, 0, 0.0, 0, False
    while hp > 0 and turns < 500:
        turns += 1
        if away:
            away -= 1
        else:                                            # the player's blows
            for _ in range(o.blows):
                k = random.randrange(100)
                hit = k < 5 if k < 10 else random.randrange(chance) >= mac * 3 // 4
                if hit: hp -= roll(pn, ps) + o.todam
            if hp <= 0: break
        energy += sx
        while energy >= 1:
            energy -= 1
            if spells and random.random() < pct:
                sp = random.choice(spells)
                if sp == "BLINK": away = 2
                elif sp == "HEAL": hp = min(hpmax, hp + 6 * rl)
                elif sp in ("TPORT", "TELE_SELF"): escaped = True
                else: lost += spell_dmg(sp, rl, hp)[0]
            elif away:
                away = max(0, away - 1)                  # it closes in instead of casting
            elif blows and "NEVER_BLOW" not in flags:
                for eff, n, s, ph in blows:
                    if random.random() < ph:
                        d = roll(n, s)
                        if eff in ("HURT", "SHATTER"): d -= d * min(o.ac, 150) // 250
                        lost += d
                energy -= 1                              # MONSTER_RECOIL
            if escaped: break
        if escaped: break
    return lost, turns, escaped


def summary(m, o):
    res = [duel(m, o) for _ in range(o.n)]
    L = sorted(r[0] for r in res); T = sorted(r[1] for r in res); q = lambda a, f: a[min(len(a) - 1, int(f * len(a)))]
    return dict(name=m["name"], level=m["level"], loss_mean=round(statistics.mean(L)), loss_p50=q(L, .5), loss_p90=q(L, .9),
                loss_p95=q(L, .95), turns_mean=round(statistics.mean(T), 1), turns_p90=q(T, .9),
                p_escaped=round(sum(r[2] for r in res) / len(res), 3),
                p90_pct_hp=round(100 * q(L, .9) / o.hp))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("name")
    for a, d in (("clvl", 22), ("blows", 3), ("todam", 7), ("tohit", 5), ("ac", 56), ("hp", 265), ("n", 4000)):
        ap.add_argument("--" + a, type=int, default=d)
    ap.add_argument("--dice", default="1d6")
    o = ap.parse_args(); random.seed(1)
    for m in csv.DictReader(open(MON)):
        if o.name.lower() in m["name"].lower():
            print(summary(m, o))
