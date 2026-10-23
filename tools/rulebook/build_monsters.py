#!/usr/bin/env python3
"""Rulebook table T3: every monster race (levels 0-99), with damage numbers a policy can use.

Writes monsters.csv. Columns (all damage before the player's resists unless noted):
  hp            FORCE_MAXHP -> maximum roll, else the average (monster2.c:1913-1919)
  speed_x       actions per normal-speed player turn = extract_energy[speed] / 1000 (uniques exact; others +-1 index)
  melee_max     sum of the blows' maximum dice (one round)
  melee_exp_acNN expected damage of one melee round vs player AC NN: P(hit) = .05 + .90*max(0,(i-3ac/4)/i),
                i = power(effect) + 3*level; HURT/SHATTER reduced by dmg*min(ac,150)/250 (melee1.c:106-127, 243-271)
  melee_turn_acNN expected melee damage per PLAYER turn adjacent = melee_exp x speed_x / 2 (MONSTER_RECOIL: after a
                melee round the monster pays its energy twice, melee2.c:3035-3044; option on for Dive04)
  spell_pct     chance to cast per action when it has line of fire = floor(100/x) for 1_IN_x (melee2.c:459-483)
  spell_mean    mean damage of one cast: uniform over all its spell flags (non-damaging ones count 0) (melee2.c:522-559)
  spell_max     the worst single cast (breaths at full HP)
  breath_max    worst breath at full HP (hp/3 or hp/6, capped; uses CURRENT hp: a wounded breather breathes less)
  range_turn    expected spell damage per player turn at range = speed_x x spell_pct x spell_mean
  tags          PARALYZE (melee), HOLD/SLOW/BLIND/CONF/SCARE (spells, saving throw / Free Action), DRAIN_<stat>, EXP_DRAIN,
                STEAL_GOLD/STEAL_ITEM, SUMMON(...), TELE_TO, TELE_LEVEL, INVISIBLE, NEVER_MOVE, MULTIPLY, PASS_WALL,
                KILL_WALL, FRIENDS/ESCORT, UNIQUE, SMART, POWERFUL
  turns_to_kill_250  player turns for this monster alone to do 250 damage adjacent at AC 40 (melee + spells mix:
                each action casts with spell_pct, else melees), a crude solo-danger index
  rating, response, threats, neutraliser   the Advisor's hand ratings (danger table, levels <= 40), where present; the
                `threats` text is the 2026-09-27 hand text (it predates the K2 corrections: e.g. BOULDER does 0, not ~30)
  melee_max_acNN  worst melee round vs player AC NN (HURT/SHATTER blows reduced by AC, others not)
  worst_3turns_acNN  worst melee damage within the next 3 player turns adjacent: melee_max_acNN x ceil(3 x speed_x / 2)
                (a melee round costs the monster 2 actions, MONSTER_RECOIL); for an emergency threshold (spells/breaths apart)
  veto_reason   for AVOID/LEAVE: "qualitative" (veto_detail lists the tags a duel can't price) or "strength" (let fight_sim decide)
Corrections vs the 2026-09-27 danger table (K2): BOULDER does no damage to players (project_p has no GF_BOULDER case,
spells1.c:3540-4092: default dam=0); BO_POIS and BR_MANA are empty cases; DARKNESS does no damage or blindness.
"""
import csv, math, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
MON = "/projectnb/jbrcs/mangband/Advisor/data/monsters/monsters.csv"
ENERGY = {int(r["speed_index"]): int(r["energy_per_game_turn"]) for r in csv.DictReader(open(os.path.join(HERE, "char_extract_energy.csv")))}
HAND = {r["name"]: r for r in csv.DictReader(open(os.path.join(HERE, "danger_table_v1.csv")))}
POWER = dict(HURT=60, SHATTER=60, UN_BONUS=20, UN_POWER=15, ELEC=10, FIRE=10, COLD=10, CONFUSE=10, TERRIFY=10, HALLU=10,
             POISON=5, EAT_GOLD=5, EAT_ITEM=5, EAT_FOOD=5, EAT_LITE=5, EXP_10=5, EXP_20=5, EXP_40=5, EXP_80=5,
             BLIND=2, PARALYZE=2, LOSE_ALL=2, ACID=0, LOSE_STR=0, LOSE_DEX=0, LOSE_CON=0, LOSE_INT=0, LOSE_WIS=0, LOSE_CHR=0)
ACS = (20, 40, 60)
# veto_reason (rulebook r4): an AVOID/LEAVE hand rating is "qualitative" when the monster has one of these (a duel model can't
# price them: incapacitation, drains, theft, summons, teleport-to, breeding, invisibility, groups), else "strength" (the rating
# was about damage for a weaker character; let fight_sim decide at the live profile)
VETO_QUAL = {"PARALYZE", "CONFUSE_BLOW", "BLIND_BLOW", "TERRIFY_BLOW", "EXP_DRAIN", "STEAL_GOLD", "STEAL_ITEM", "HOLD", "SLOW",
             "BLIND", "CONF", "SCARE", "TELE_TO", "TELE_LEVEL", "FORGET", "BRAIN_SMASH", "MULTIPLY", "INVISIBLE", "PASS_WALL",
             "FRIENDS", "ESCORT", "ESCORTS"}


def dice(d):
    m = re.fullmatch(r"(\d+)d(\d+)", d or "")
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def u(n):        # randint1(n): mean, max
    return ((n + 1) / 2, n) if n > 0 else (0, 0)


def dr(n, s):    # damroll(n,s)
    return (n * (s + 1) / 2, n * s)


def spell_dmg(flag, rl, hp):
    """(mean, max) damage of one cast of `flag` by a monster of level rl with hp; breaths at that hp."""
    B3 = dict(BR_ACID=1600, BR_ELEC=1600, BR_FIRE=1600, BR_COLD=1600, BR_POIS=800, BR_TIME=150, BR_GRAV=200)
    B6 = dict(BR_NETH=550, BR_LITE=400, BR_DARK=400, BR_CONF=400, BR_SOUN=500, BR_CHAO=500, BR_DISE=500, BR_NEXU=400,
              BR_INER=200, BR_SHAR=500, BR_PLAS=150, BR_WALL=200)
    if flag in B3: v = min(hp // 3, B3[flag]); return v, v
    if flag in B6: v = min(hp // 6, B6[flag]); return v, v
    a = lambda m1, m2: (m1[0] + m2[0], m1[1] + m2[1])
    k = {"ARROW_1": dr(1, 6), "ARROW_2": dr(3, 6), "ARROW_3": dr(5, 6), "ARROW_4": dr(7, 6),
         "BA_ACID": a(u(rl * 3), (15, 15)), "BA_ELEC": a(u(rl * 3 // 2), (8, 8)), "BA_FIRE": a(u(rl * 7 // 2), (10, 10)),
         "BA_COLD": a(u(rl * 3 // 2), (10, 10)), "BA_POIS": dr(12, 2), "BA_NETH": a(dr(10, 10), (50 + rl, 50 + rl)),
         "BA_WATE": a(u(rl * 5 // 2), (50, 50)), "BA_MANA": a(dr(10, 10), (rl * 5, rl * 5)),
         "BA_DARK": a(dr(10, 10), (rl * 5, rl * 5)), "MIND_BLAST": dr(8, 8), "BRAIN_SMASH": dr(12, 15),
         "CAUSE_1": dr(3, 8), "CAUSE_2": dr(8, 8), "CAUSE_3": dr(10, 15), "CAUSE_4": dr(15, 15),
         "BO_ACID": a(dr(7, 8), (rl // 3, rl // 3)), "BO_ELEC": a(dr(4, 8), (rl // 3, rl // 3)),
         "BO_FIRE": a(dr(9, 8), (rl // 3, rl // 3)), "BO_COLD": a(dr(6, 8), (rl // 3, rl // 3)),
         "BO_NETH": a(dr(5, 5), (30 + rl * 3 // 2, 30 + rl * 3 // 2)), "BO_WATE": a(dr(10, 10), (rl, rl)),
         "BO_MANA": a(u(rl * 7 // 2), (50, 50)), "BO_PLAS": a(dr(8, 7), (10 + rl, 10 + rl)),
         "BO_ICEE": a(dr(6, 6), (rl, rl)), "MISSILE": a(dr(2, 6), (rl // 3, rl // 3))}
    return k.get(flag, (0, 0))     # everything else (BOULDER, BO_POIS, status, summons, movement) deals no damage


if __name__ == "__main__":
    rows = []
    for m in csv.DictReader(open(MON)):
        lev = int(m["level"]); rl = max(1, lev)
        flags = set(m["flags"].split("|")) if m["flags"] else set()
        spells = [s for s in m["spells"].split("|") if s] if m["spells"] else []
        hp = int(float(m["hp_max"] if "FORCE_MAXHP" in flags else m["hp_avg"]))
        sx = ENERGY.get(int(m["speed"]), 1000) / 1000
        ac_m = {ac: 0.0 for ac in ACS}; mmax = 0; tags = set(); mmax_ac = {ac: 0 for ac in ACS}
        for b in (m["blow1"], m["blow2"], m["blow3"], m["blow4"]):
            if not b: continue
            p = b.split(":"); eff = p[1] if len(p) > 1 else ""; n, s = dice(p[2] if len(p) > 2 else "")
            mmax += n * s
            for ac in ACS:
                mmax_ac[ac] += n * s - (n * s * min(ac, 150) // 250 if eff in ("HURT", "SHATTER") else 0)
            if eff == "PARALYZE": tags.add("PARALYZE")
            if eff.startswith("LOSE_"): tags.add("DRAIN_" + eff[5:])
            if eff.startswith("EXP_"): tags.add("EXP_DRAIN")
            if eff == "EAT_GOLD": tags.add("STEAL_GOLD")
            if eff == "EAT_ITEM": tags.add("STEAL_ITEM")
            if eff in ("CONFUSE", "BLIND", "TERRIFY"): tags.add(eff + "_BLOW")
            if not eff: continue
            i = POWER.get(eff, 0) + 3 * rl
            for ac in ACS:
                ph = 0.05 + 0.90 * max(0, i - (3 * ac) // 4) / i
                avg = n * (s + 1) / 2
                if eff in ("HURT", "SHATTER"): avg -= avg * min(ac, 150) / 250
                ac_m[ac] += ph * avg
        freq = int(m["spell_freq"]) if m["spell_freq"] else 0
        pct = (100 // freq) / 100 if freq else 0.0
        dmgs = [spell_dmg(s, rl, hp) for s in spells]
        smean = sum(d[0] for d in dmgs) / len(dmgs) if dmgs else 0.0
        smax = max((d[1] for d in dmgs), default=0)
        bmax = max((spell_dmg(s, rl, hp)[1] for s in spells if s.startswith("BR_")), default=0)
        for s in spells:
            if s in ("HOLD", "SLOW", "BLIND", "CONF", "SCARE", "TELE_TO", "TELE_LEVEL", "TELE_AWAY", "FORGET", "TRAPS"): tags.add(s)
            if s.startswith("S_"): tags.add("SUMMON(" + s[2:] + ")")
            if s == "BRAIN_SMASH": tags.add("BRAIN_SMASH")
        for f in ("INVISIBLE", "NEVER_MOVE", "NEVER_BLOW", "MULTIPLY", "PASS_WALL", "KILL_WALL", "FRIENDS", "ESCORT", "ESCORTS",
                  "UNIQUE", "SMART", "POWERFUL", "OPEN_DOOR"):
            if f in flags: tags.add(f)
        turn40 = (sx * (1 - pct) * ac_m[40] / 2 if "NEVER_BLOW" not in flags else 0) + sx * pct * smean
        h = HAND.get(m["name"], {})
        qual = sorted(t for t in tags if t in VETO_QUAL or t.startswith(("DRAIN_", "SUMMON(")))
        veto = ("qualitative" if qual else "strength") if h.get("response") in ("AVOID", "LEAVE") else ""
        rows.append(dict(idx=m["idx"], name=m["name"], symbol=m["symbol"], color=m["color"], level=lev, depth_ft=lev * 50,
                         speed=int(m["speed"]) - 110, speed_x=round(sx, 2), hp=hp, ac=m["ac"], exp=m["exp"],
                         melee_max=mmax, **{f"melee_exp_ac{ac}": round(ac_m[ac], 1) for ac in ACS},
                         **{f"melee_turn_ac{ac}": round(ac_m[ac] * sx / 2, 1) for ac in ACS},
                         spell_pct=round(pct, 2), spell_mean=round(smean, 1), spell_max=smax, breath_max=bmax,
                         range_turn=round(sx * pct * smean, 1), tags="|".join(sorted(tags)),
                         turns_to_kill_250=round(250 / turn40, 1) if turn40 > 0 else "",
                         rating=h.get("danger", ""), response=h.get("response", ""), threats=h.get("threats", ""),
                         neutraliser=h.get("neutraliser", ""), spells=m["spells"],
                         veto_reason=veto, veto_detail="|".join(qual) if veto else "",
                         **{f"melee_max_ac{ac}": mmax_ac[ac] for ac in ACS},
                         **{f"worst_3turns_ac{ac}": (mmax_ac[ac] * math.ceil(3 * sx / 2) if "NEVER_BLOW" not in flags else 0)
                            for ac in ACS}))
    with open(os.path.join(HERE, "monsters.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(len(rows), "monsters")
