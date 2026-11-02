"""damage_mix -- where a character's damage comes from, for the gear evaluator's effective HP (the user, 10-28: "add
the EHP column to gearcmp and loadout").

Every HP drop in the decision log (records with "hp" and "depth") at LO-HI ft is split over the attack messages of
that moment (events.jsonl, the wall clock): melee blows by the monster's blows (its share of HURT blows -> "hurt",
which AC reduces twice -- hit chance and wounds, melee1.c --, the rest -> "melee_other": hit chance only), breaths,
bolts, balls and traps by element (a resist cuts them), arrows and magic missiles -> "other". A drop with no attack
message (poison, a cut, an unseen spell) is "other" too. The attribution is logs.damage (D8, 2026-11-01, 2.44.0: one
definition with the scorecard's damage_by_monster, which sums the same rows by monster).

    python3 damage_mix.py [--nick dive04] [--mission LABEL] [--lo 700] [--hi 800] [--days 4] [--out FILE]

--mission LABEL takes the band from that mission's play (runs/missions.json window): the dungeon depths where it
spent at least 10% of its dungeon time, widened to whole 100 ft (750 -> 700-800, 800 -> 800-900, 700-850 -> 700-900).
wrap.sh passes it, so the EHP mix follows the character down. --lo/--hi override; with neither, or a mission with
no dungeon time, the band is 700-800 ft.

writes runs/pilot/NICK/damage_mix.json: {"mix": {category: share of HP lost}, "melee_level": mean level of the
melee attackers (weighted by damage), "hp_lost", "drops", "range", "since"}."""
import argparse
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import logs                        # noqa: E402  (the shared readers and the damage attribution, D8)

def mission_band(nick, label, min_share=0.10):
    """(lo, hi, played) ft: the 100 ft band of the dungeon depths mission LABEL spent at least MIN_SHARE of its
    dungeon time at (each record weighted by the time to the next one, gaps capped at 60 s); None if the mission
    isn't in runs/missions.json or had no dungeon time."""
    m = logs.find_mission(label)
    if not m:
        return None
    t0, t1 = logs.mission_window(m)
    at, last = {}, None
    for r in logs.decisions(nick, t0, t1, keep=lambda l: '"depth": ' in l):
        t, d = r["t"], r.get("depth")
        if not isinstance(d, int):
            continue
        if last and last[1] > 0:
            at[last[1]] = at.get(last[1], 0) + min(t - last[0], 60)
        last = (t, d)
    total = sum(at.values())
    played = sorted(d * 50 for d, s in at.items() if total and s >= min_share * total)
    if not played:
        return None
    lo, hi = played[0] // 100 * 100, math.ceil(played[-1] / 100) * 100
    return lo, max(hi, lo + 100), played


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nick", default="dive04")
    ap.add_argument("--mission", help="take the depth band from this mission's play (wrap.sh)")
    ap.add_argument("--lo", type=int)
    ap.add_argument("--hi", type=int)
    ap.add_argument("--days", type=float, default=4)
    ap.add_argument("--out", help="write here instead of runs/pilot/NICK/damage_mix.json")
    a = ap.parse_args()
    rundir = logs.run_dir(a.nick)
    band = mission_band(a.nick, a.mission) if a.mission else None
    if a.mission:
        print(f"{a.mission}: " + (f"played {band[2][0]}-{band[2][-1]} ft -> band {band[0]}-{band[1]} ft" if band else
                                  "no dungeon time found -> band 700-800 ft"), file=sys.stderr)
    a.lo = a.lo if a.lo is not None else band[0] if band else 700
    a.hi = a.hi if a.hi is not None else band[1] if band else 800
    since = time.time() - a.days * 86400

    # the HP drops at the depth range, attributed (logs.damage: one row per drop and attack message)
    rows = [r for r in logs.damage(a.nick, since) if a.lo <= r.depth * 50 <= a.hi]
    races = logs._races()
    mix, lv_w, lv_sum = {}, 0.0, 0.0
    for r in rows:
        mix[r.category] = mix.get(r.category, 0) + r.amount
        if r.category in ("hurt", "melee_other") and r.monster.lower() in races:
            lv_w += r.amount
            lv_sum += r.amount * races[r.monster.lower()].level
    total = sum(mix.values())
    drops = len({r.drop for r in rows})
    out = {"mix": {k: round(v / total, 4) for k, v in sorted(mix.items(), key=lambda kv: -kv[1])} if total else {},
           "melee_level": round(lv_sum / lv_w, 1) if lv_w else None, "hp_lost": round(total), "drops": drops,
           "range": [a.lo, a.hi], "since": time.strftime("%Y-%m-%d %H:%M", time.localtime(since)),
           "made": time.strftime("%Y-%m-%d %H:%M")}
    json.dump(out, open(a.out or os.path.join(rundir, "damage_mix.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
