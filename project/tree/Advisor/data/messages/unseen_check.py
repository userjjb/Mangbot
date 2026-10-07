#!/usr/bin/env python3
"""Test the Pilot's RE_UNSEEN / RE_HURT_OTHER / RE_ATTACK (copied from world.py, 2026-09-29)
against the catalogue and the logged messages. Writes unseen_check.csv."""
import csv, re
RE_ATTACK = re.compile(r" (hits|bites|claws|stings|touches|kicks|butts|crushes|engulfs|crawls on|spits on|"
                       r"gazes at|wails at|punches|grabs|fires an arrow|casts a magic missile|"
                       r"points at you and curses|breathes|misses|releases spores at) you")
RE_UNSEEN = re.compile(r"^(It|Something) (hits|bites|claws|stings|touches|kicks|butts|crushes|engulfs|"
                       r"crawls on|spits on|gazes at|wails at|punches|grabs|breathes|casts|magically|"
                       r"mumbles|fires|points at you|commands you|drains|tries to|concentrates)")
RE_HURT_OTHER = re.compile(r"trap|pit|impaled|graze|cut|bleed|poison|dart|You feel very sick|"
                           r"burn|freeze|acid|You are hit|starv|faint", re.I)
cat = list(csv.DictReader(open("catalogue.csv")))
def render(t):  # catalogue text with placeholders -> a sample the regexes can see
    return (t.replace("<monster>", "It").replace("<Monster>", "It").replace("<mon>", "It")
             .replace("<item>", "Potion").replace("<n>", "3"))
rows = []
for r in cat:
    t = r["text"]
    if not t or r["audience"] == "others":
        continue
    unseen_form = t.startswith(("It ", "Something ", "<monster>", "<Monster>", "<mon>"))
    s = render(t)
    rows.append(dict(event=r["event"], text=t, relevance=r["pilot_relevance"], unseen_form=unseen_form,
                     RE_UNSEEN=bool(RE_UNSEEN.search(s)), RE_ATTACK=bool(RE_ATTACK.search(s)),
                     RE_HURT_OTHER=bool(RE_HURT_OTHER.search(s)), src=f'{r["file"]}:{r["line"]}'))
with open("unseen_check.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
fam = lambda e: e.split(".")[0]
# 1. monster actions on the player that could come from an unseen monster, missed by RE_UNSEEN
acts = [r for r in rows if r["unseen_form"] and fam(r["event"]) in ("attack", "spell", "summon", "escape", "status", "item", "gold", "stat", "exp")]
miss = [r for r in acts if not r["RE_UNSEEN"]]
print(f"monster-on-player texts in <monster>/It form: {len(acts)}; not matched by RE_UNSEEN: {len(miss)}")
for r in sorted(miss, key=lambda r: r["event"])[:45]:
    print("  MISS", r["event"], "|", r["text"][:80], "|", r["src"])
# 2. RE_UNSEEN matches that aren't attacks on us
fp = [r for r in rows if r["RE_UNSEEN"] and fam(r["event"]) not in ("attack", "spell", "summon", "stat", "exp", "gold", "item")]
print(f"\nRE_UNSEEN matches outside attack/spell families: {len(fp)}")
for r in fp[:15]:
    print("  FP?", r["event"], "|", r["text"][:80])
# 3. non-monster HP loss in the catalogue vs RE_HURT_OTHER
hurt = [r for r in rows if fam(r["event"]) in ("trap", "damage", "hunger") or r["event"].startswith(("status.poisoned", "status.cut", "status.stun"))]
print(f"\nnon-monster HP-loss candidates: {len(hurt)}; not matched by RE_HURT_OTHER: {sum(1 for r in hurt if not r['RE_HURT_OTHER'])}")
for r in [r for r in hurt if not r["RE_HURT_OTHER"]][:25]:
    print("  MISS", r["event"], "|", r["text"][:80])
# 4. RE_HURT_OTHER false matches in the logs
logs = list(csv.DictReader(open("log_messages.csv")))
fp2 = [l for l in logs if RE_HURT_OTHER.search(l["text"]) and not re.search(r"trap|dart|pit\b|pits|impal|bleed|poisoned|You feel very sick|starv|faint from|burn|freez|acid|You are hit", l["text"], re.I)]
print(f"\nRE_HURT_OTHER matches in logs that aren't HP loss (heuristic): {len(fp2)}")
for l in fp2[:15]:
    print("  ", l["count"], l["text"][:90])
