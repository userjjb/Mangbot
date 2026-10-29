"""damage_mix -- where a character's damage comes from, for the gear evaluator's effective HP (the user, 10-28: "add
the EHP column to gearcmp and loadout").

Every HP drop in the decision log (records with "hp" and "depth") at LO-HI ft is split over the attack messages of
that moment (events.jsonl, the wall clock): melee blows by the monster's blows (its share of HURT blows -> "hurt",
which AC reduces twice -- hit chance and wounds, melee1.c --, the rest -> "melee_other": hit chance only), breaths,
bolts, balls and traps by element (a resist cuts them), arrows and magic missiles -> "other". A drop with no attack
message (poison, a cut, an unseen spell) is "other" too.

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
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pilot"))
import glyphs                      # noqa: E402

RUNS = os.path.join(HERE, "..", "..", "..", "runs", "pilot")
MELEE = re.compile(r"^(?:The (.+?)|It|Something) (hits|bites|claws|stings|touches|kicks|butts|crushes|engulfs|"
                   r"crawls on|spits on|gazes at|wails at|punches|grabs|drools on|releases spores|begs|insults|"
                   r"moans) you")
ELEMENTS = (("fire", r"fire|flames|burn"), ("cold", r"frost|cold|ice"), ("acid", r"acid"),
            ("elec", r"lightning|elec"), ("pois", r"poison|gas|stinking cloud"), ("lite", r"breathes light"),
            ("dark", r"darkness|breathes dark"), ("shard", r"shards"), ("nexus", r"nexus"), ("sound", r"sound"),
            ("nether", r"nether"), ("chaos", r"chaos"), ("disen", r"disenchant"))
RANGED = re.compile(r"^(?:(?:The .+?|It|Something) (breathes|casts|fires|hurls|spits)|You are hit by|"
                    r"You are enveloped|You are blasted|You are struck)")


def classify(text):
    """('hurt'|'melee', monster name or None) for a blow; (element|'other', None) for the rest; None if not an
    attack on us."""
    m = MELEE.match(text)
    if m:
        return "melee", m.group(1)
    if RANGED.match(text):
        if "fearful illusion" in text or "burning your eyes" in text or "confus" in text or "scare" in text:
            return None                     # (no damage: status spells)
        for el, pat in ELEMENTS:
            if re.search(pat, text):
                return el, None
        return "other", None
    return None


def mission_band(rundir, label, min_share=0.10):
    """(lo, hi, played) ft: the 100 ft band of the dungeon depths mission LABEL spent at least MIN_SHARE of its
    dungeon time at (each record weighted by the time to the next one, gaps capped at 60 s); None if the mission
    isn't in runs/missions.json or had no dungeon time."""
    ms = [m for m in json.load(open(os.path.join(RUNS, "..", "missions.json"))) if m.get("label") == label]
    if not ms:
        return None
    t0 = time.mktime(time.strptime(ms[-1]["start"], "%Y-%m-%d %H:%M"))
    t1 = time.mktime(time.strptime(ms[-1]["end"], "%Y-%m-%d %H:%M")) if ms[-1].get("end") else time.time()
    at, last = {}, None
    for line in open(os.path.join(rundir, "decisions.jsonl")):
        if '"depth": ' not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        t, d = r.get("t"), r.get("depth")
        if not isinstance(t, (int, float)) or not isinstance(d, int) or not t0 <= t <= t1:
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
    rundir = os.path.join(RUNS, a.nick)
    band = mission_band(rundir, a.mission) if a.mission else None
    if a.mission:
        print(f"{a.mission}: " + (f"played {band[2][0]}-{band[2][-1]} ft -> band {band[0]}-{band[1]} ft" if band else
                                  "no dungeon time found -> band 700-800 ft"), file=sys.stderr)
    a.lo = a.lo if a.lo is not None else band[0] if band else 700
    a.hi = a.hi if a.hi is not None else band[1] if band else 800
    since = time.time() - a.days * 86400
    races = {r.name.lower(): r for r in glyphs.load_rulebook(glyphs.load_races()).values()}

    # HP drops at the depth range: (t0, t1, amount)
    drops, last = [], None
    for line in open(os.path.join(rundir, "decisions.jsonl")):
        if '"hp": [' not in line or '"depth": ' not in line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("t", 0) < since or not r.get("hp"):
            continue
        cur = (r["t"], r["hp"][0], r["hp"][1], r.get("depth") or 0)
        if last and cur[2] == last[2] and cur[1] < last[1] and a.lo <= cur[3] * 50 <= a.hi and cur[0] - last[0] < 5:
            drops.append((last[0], cur[0], last[1] - cur[1]))
        last = cur

    # attack messages in the same period
    msgs = []
    with open(os.path.join(rundir, "events.jsonl"), "rb") as f:
        for raw in f:
            if b'"message"' not in raw[:30] or not (b"you" in raw or b"You" in raw or b"breathes" in raw
                                                   or b"casts" in raw or b"fires" in raw):
                continue
            try:
                e = json.loads(raw)
            except ValueError:
                continue
            if e.get("epoch", 0) < since:
                continue
            c = classify(e.get("text", ""))
            if c:
                msgs.append((e["epoch"], c))
    msgs.sort()

    import bisect
    times = [t for t, _ in msgs]
    mix, lv_w, lv_sum, total = {}, 0.0, 0.0, 0.0
    for t0, t1, amt in drops:
        i, j = bisect.bisect_left(times, t0 - 0.6), bisect.bisect_right(times, t1 + 0.2)
        here = [c for _, c in msgs[i:j]]
        total += amt
        if not here:
            mix["other"] = mix.get("other", 0) + amt
            continue
        share = amt / len(here)
        for kind, name in here:
            if kind == "melee":
                r = races.get((name or "").lower())
                blows = [b.split(":") for b in (r.blows if r else [])]
                hurt = sum(1 for b in blows if len(b) > 1 and b[1] in ("HURT", "SHATTER")) / len(blows) \
                    if blows else 0.7
                mix["hurt"] = mix.get("hurt", 0) + share * hurt
                mix["melee_other"] = mix.get("melee_other", 0) + share * (1 - hurt)
                if r:
                    lv_w += share
                    lv_sum += share * r.level
            else:
                mix[kind] = mix.get(kind, 0) + share
    out = {"mix": {k: round(v / total, 4) for k, v in sorted(mix.items(), key=lambda kv: -kv[1])} if total else {},
           "melee_level": round(lv_sum / lv_w, 1) if lv_w else None, "hp_lost": round(total), "drops": len(drops),
           "range": [a.lo, a.hi], "since": time.strftime("%Y-%m-%d %H:%M", time.localtime(since)),
           "made": time.strftime("%Y-%m-%d %H:%M")}
    json.dump(out, open(a.out or os.path.join(rundir, "damage_mix.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
