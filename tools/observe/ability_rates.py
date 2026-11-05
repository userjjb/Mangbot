"""ability_rates -- how often the character meets what the abilities the simulator doesn't play would stop, per hour in
the dungeon, for the gear evaluator's ability terms (2.64.0: m67's `gearcmp` put an Amulet of Weaponmastery only +3.9%
over Slow Digestion -- its resist disenchantment and sustains counted for nothing).

From the message log (events.jsonl) and the decision log (decisions.jsonl) over the last --days (default 30: a few
events an hour need the hours; or a mission's window): the dungeon hours (decision records at depth > 0, gaps capped at 60 s), and

  fear      "You are terrified!" episodes, "You are too afraid to attack" (a melee turn lost each), the seconds afraid
            (to "You feel bolder now.", capped at 60 s), the potions quaffed for it ("afraid and in danger: quaffed")
  blind     "You are blind!" episodes and the potions quaffed for it ("blind in combat: quaffed")
  confused  "You are confused!" episodes and the potions quaffed for it ("confused in combat: quaffed")
  paralysed "You are paralyzed!"
  disenchanted  "Your X (c) was disenchanted!" (a plus taken; "resists disenchantment" counted apart)
  drained   "You feel very weak/stupid/naive/clumsy/sickly/ugly." per stat (spells2.c dec_stat; "for a moment, but
            the feeling passes" = sustained, counted apart)
  life      "You feel your life draining away!" (hold life: "slipping away", "You keep hold of your life force!")
  food      "hungry: ate X"
  unseen    HP lost to attackers it couldn't see (logs.damage, monster "unseen": what See Invisible would show)

    python3 ability_rates.py [--nick dive04] [--days 30] [--mission LABEL] [--out FILE]

writes runs/pilot/NICK/ability_rates.json: {"dungeon_h", "counts": {...}, "per_hour": {...}, "cures": {what:
{potion: n}}, "drained": {stat: n}, "sustained": {stat: n}, "since", "made"}. wrap.sh refreshes it per mission; the
Pilot (gear.py ability_worth) falls back to geareval.ABILITY_RATES_SEED without it."""
import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import logs                        # noqa: E402

STAT_OF = {"weak": "STR", "stupid": "INT", "naive": "WIS", "clumsy": "DEX", "sickly": "CON", "ugly": "CHR"}
MSG = [("fear", re.compile(r"^You are terrified!")), ("fear_end", re.compile(r"^You feel bolder now")),
       ("too_afraid", re.compile(r"^You are too afraid to attack")),
       ("blind", re.compile(r"^You are blind!")), ("confused", re.compile(r"^You are confused!")),
       ("paralysed", re.compile(r"^You are paraly[sz]ed!")),
       ("disenchanted", re.compile(r"^Your .+ \(\w\) (was|were) disenchanted!")),
       ("disen_resisted", re.compile(r"^Your .+ \(\w\) resists? disenchantment!")),
       ("sustained", re.compile(r"^You feel (\w+) for a moment, but the feeling passes")),
       ("drained", re.compile(r"^You feel very (weak|stupid|naive|clumsy|sickly|ugly)\.")),
       ("life", re.compile(r"^You feel your life draining away!")),
       ("life_held", re.compile(r"^You feel your life slipping away!|^You keep hold of your life force!"))]
KEYS = ("terrified", "bolder", "too afraid", "are blind", "are confused", "paraly", "disenchant", "feeling passes",
        "You feel very ", "your life", "life force")
CURE = re.compile(r"^(afraid and in danger|blind in combat|confused in combat): quaffed (?:an? |\d+ )?(.+?)(?: \{.*)?$")
CURE_OF = {"afraid and in danger": "fear", "blind in combat": "blind", "confused in combat": "confused"}
AFRAID_CAP_S = 60


def dungeon_seconds(nick, t0, t1):
    """Seconds in the dungeon: decision records at depth > 0, each weighted by the time to the next (gaps capped at
    60 s, as damage_mix.mission_band)."""
    total, last = 0.0, None
    for r in logs.decisions(nick, t0, t1, keep=lambda l: '"depth": ' in l):
        t, d = r["t"], r.get("depth")
        if not isinstance(d, int):
            continue
        if last and last[1] > 0:
            total += min(t - last[0], 60)
        last = (t, d)
    return total


def potion(name):
    """'Potions of Heroism' / 'Potion of Cure Serious Wounds' -> 'Heroism' / 'Cure Serious Wounds'."""
    return re.sub(r"^(Potions?|Scrolls?|Mushrooms?) of ", "", name).strip()


def measure(nick, t0, t1):
    counts = {k: 0 for k, _ in MSG}
    counts.update(food=0, afraid_s=0.0)
    drained, sustained, cures = {}, {}, {}
    afraid_since = None
    for e in logs.events(nick, t0, t1, keep=lambda l: '"message"' in l and any(k in l for k in KEYS)):
        text = e.get("text") or ""
        for k, rx in MSG:
            m = rx.match(text)
            if not m:
                continue
            counts[k] += 1
            if k == "drained":
                s = STAT_OF[m.group(1)]
                drained[s] = drained.get(s, 0) + 1
            elif k == "sustained" and m.group(1) in STAT_OF:
                s = STAT_OF[m.group(1)]
                sustained[s] = sustained.get(s, 0) + 1
            elif k == "fear":
                afraid_since = e["epoch"]
            elif k == "fear_end" and afraid_since is not None:
                counts["afraid_s"] += min(AFRAID_CAP_S, e["epoch"] - afraid_since)
                afraid_since = None
            break
    for r in logs.decisions(nick, t0, t1, keep=lambda l: "quaffed" in l or "hungry: ate" in l):
        det = r.get("detail") or ""
        if det.startswith("hungry: ate"):
            counts["food"] += 1
            continue
        m = CURE.match(det)
        if m:
            what = CURE_OF[m.group(1)]
            cures.setdefault(what, {})
            p = potion(m.group(2))
            cures[what][p] = cures[what].get(p, 0) + 1
    try:
        counts["unseen_hp"] = round(sum(r.amount for r in logs.damage(nick, t0, t1) if r.monster == "unseen"))
    except Exception:                  # (the damage attribution needs the rulebook)
        counts["unseen_hp"] = 0
    counts["afraid_s"] = round(counts["afraid_s"])
    return counts, drained, sustained, cures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nick", default="dive04")
    ap.add_argument("--days", type=float, default=30)
    ap.add_argument("--mission", help="this mission's window instead of --days")
    ap.add_argument("--out", help="write here instead of runs/pilot/NICK/ability_rates.json")
    a = ap.parse_args()
    t1 = time.time()
    t0 = t1 - a.days * 86400
    if a.mission:
        m = logs.find_mission(a.mission)
        if m:
            t0, t1 = logs.mission_window(m)
    secs = dungeon_seconds(a.nick, t0, t1)
    counts, drained, sustained, cures = measure(a.nick, t0, t1)
    h = secs / 3600
    out = {"dungeon_h": round(h, 2), "counts": counts,
           "per_hour": {k: round(v / h, 3) for k, v in counts.items()} if h > 0 else {},
           "drained": drained, "sustained": sustained, "cures": cures,
           "since": time.strftime("%Y-%m-%d %H:%M", time.localtime(t0)), "made": time.strftime("%Y-%m-%d %H:%M")}
    json.dump(out, open(a.out or os.path.join(logs.run_dir(a.nick), "ability_rates.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
