"""setpiece_l -- set-pieces L: rulebook claims checked live.

Run by setpiece.py (python3 setpiece.py ID); the framework (Run, ctl, log_since...) is setpiece_run.py.
"""
import json
import os
import re
import time

from setpiece_run import RUN, ctl, log_since, _tail, messages_since, hp_now, give_item


def l2g(run):
    """L2 with Gandalf off the level (no shared time bubble)."""
    l2(run, gandalf_away=True)


def l3(run):
    """L3 (a rulebook claim, abilities.csv): with Boots of Free Action worn (forged: identified), an
    Illusionist (HOLD, BLIND, CONF; fast, blinks) 3 squares off. Expect "You are unaffected!" after a HOLD
    spell, and not after BLIND (Dive04 has no rBlind): the message pairing the Pilot's ability inference
    reads."""
    run.bring_dive04()
    if not give_item(run, 91, ego=58, want="Free Action") and "Free Action" not in ctl("status", "full", role="architect"):
        run.check("boots picked up", False, "")
        return
    ctl("wear", "Free Action", role="architect")
    time.sleep(2.5)
    eq = ctl("status", "full", role="architect").split("Equipment:")[-1].split("\n")[0]
    run.check("boots worn", "Free Action" in eq, eq[:160])
    run.t_act = time.time()
    run.place("Illusionist", 3, gmap=True)
    run.watch(45)
    msgs = [m for _, m in messages_since(run.t_act)]
    run.res["messages"] = msgs[:80]
    pairs = [(a, b) for a, b in zip(msgs, msgs[1:]) if "Illusionist" in a or a.startswith("It ")]
    hold = [(a, b) for a, b in pairs if re.search(r"stares deep|gazes deep|looks deep|paraly", a, re.I)]
    blind = [(a, b) for a, b in pairs if re.search(r"burning your eyes|blind", a, re.I)]
    run.res["hold_pairs"], run.res["blind_pairs"] = hold, blind
    run.check("a HOLD cast seen", bool(hold), f"{len(hold)}")
    run.check("unaffected after HOLD", bool(hold) and all("unaffected" in b for _, b in hold), f"{hold[:2]}")
    run.check("not unaffected after BLIND (no rBlind)", not any("unaffected" in b for _, b in blind),
              f"{blind[:2]}")
    recs = log_since(run.t_act)
    ab = [d.get("detail") for d in recs if d.get("kind") == "attention" and d.get("what") == "ability"]
    run.res["ability_news"] = ab[:3]


def l3b(run):
    """L3b (the session-7 todo: L3's rBlind half, unseen because the Illusionist died first): a Metal Cap of Seeing
    (resist blindness, See Invisible; forged: identified) worn, two Illusionists (HOLD, BLIND, CONF; fast, blink) 5
    squares off with a clear line. Expect "You are unaffected!" after each BLIND cast (the message pairing the Pilot's
    ability inference reads), and never blinded."""
    run.bring_dive04()
    if not give_item(run, 95, ego=30, pval=2, want="Seeing") and "Seeing" not in ctl("status", "full", role="architect"):
        run.check("cap picked up", False, "")
        return
    ctl("wear", "Seeing", role="architect")
    time.sleep(2.5)
    eq = ctl("status", "full", role="architect").split("Equipment:")[-1].split("\n")[0]
    run.check("cap worn", "Seeing" in eq, eq[:160])
    run.t_act = time.time()
    run.place("Illusionist", 5, gmap=True)
    run.place("Illusionist", 5, gmap=True)
    run.watch(60)
    msgs = [m for _, m in messages_since(run.t_act)]
    run.res["messages"] = msgs[:100]
    pairs = [(a, b) for a, b in zip(msgs, msgs[1:]) if "Illusionist" in a or a.startswith("It ")]
    blind = [(a, b) for a, b in pairs if re.search(r"burning your eyes|casts a spell, burning", a, re.I)]
    run.res["blind_pairs"] = blind
    run.check("a BLIND cast seen", bool(blind), f"{len(blind)}")
    run.check("unaffected after BLIND (rBlind)", bool(blind) and all("unaffected" in b for _, b in blind), f"{blind[:2]}")
    run.check("never blinded", not any(re.search(r"You are blind", m) for m in msgs), "")


def l1(run):
    """L1 (a rulebook claim): a Hill giant's boulders do 0 damage to the player (project_p has no GF_BOULDER)."""
    run.bring_dive04()
    run.t_act = time.time()
    ctl("order", "flee_hp=0.3", role="architect")
    for d in (8, 7, 6, 5):
        try:
            run.place("Hill giant", d)
            break
        except RuntimeError:
            continue
    run.watch(60)
    ctl("order", "flee_hp=0.5", role="architect")
    msgs = [json.loads(l) for l in open(os.path.join(RUN, "events.jsonl")) if '"message"' in l and "boulder" in l.lower()]
    msgs = [m for m in msgs if m.get("epoch", 0) >= run.t_act]
    hp = [(d["t"], d["hp"][0]) for d in log_since(run.t_act) if d.get("hp")]
    hits = []
    for m in msgs:
        before = [h for t, h in hp if t <= m["epoch"]][-1:] or [None]
        after = [h for t, h in hp if m["epoch"] < t <= m["epoch"] + 0.6][:1] or [None]
        hits.append((m["text"][:60], before[0], after[0]))
    run.res["notes"].append(f"boulders: {hits}")
    run.check("a boulder was thrown", bool(msgs), f"{len(msgs)} boulder messages")
    run.check("no HP lost to boulders", all(b is None or a is None or a >= b for _, b, a in hits), f"{hits[:4]}")


def l2(run, gandalf_away=False):
    """L2 (a rulebook claim): Word of Recall comes ~10x sooner while resting out of sight. Dive04 fights a
    Sabre-tooth tiger (A3: 40-50 HP lost) and the moment it's dead gets `goal recall` (which rests while it
    charges when hurt and alone), vs. the time a recall takes standing (15-34 player turns, ~10-23 s; 17.9
    and 20.4 s measured). (The Advisor's CON-ring swap can't hurt here: MAngband scales HP with max HP,
    xtra1.c calc_hitpoints. Cave and Black orcs left HP full by the time they were gone.)"""
    run.bring_dive04()
    t0 = time.time()
    run.place("Sabre-tooth tiger", 1)
    dead = None
    for _ in range(60):
        time.sleep(0.5)
        dead = next((t for t, m in messages_since(t0) if "slain the Sabre-tooth" in m), None)
        if dead:
            break
    hp = hp_now()
    run.res["hp_after_fight"] = hp
    if not dead or not hp or hp[0] >= hp[1]:
        run.check("hurt and alone after the fight", False, f"tiger slain {dead is not None}, HP {hp}")
        return
    if gandalf_away:
        run.dm.ascend(1)                     # (off the level: no shared time bubble)
    # a fuel reading every second (a redraw is free): the recall counts down on the same tick as the fuel
    import threading
    stop = threading.Event()

    def sample():
        while not stop.is_set():
            ctl("raw", "redraw", role="architect")
            stop.wait(1.0)
    threading.Thread(target=sample, daemon=True).start()
    st_now = ctl("status", role="architect")
    t_read = time.time()
    run.t_act = t_read
    ctl("goal", "recall", role="architect")
    t_yank = None
    for _ in range(60):
        time.sleep(0.5)
        yank = [t for t, m in messages_since(t_read) if "yanked upwards" in m]
        if yank:
            t_yank = yank[0]
            break
    recs = log_since(t_read)
    rested = any(d.get("kind") == "act" and d.get("cmd") == "rest" for d in recs)
    secs = (t_yank - t_read) if t_yank else None
    run.res["notes"].append(f"status at the read: {st_now.splitlines()[0][:80]}; rested {rested}; {secs}")
    stop.set()
    factors = [(round(d["t"] - t_read, 1), d.get("factor"), d.get("measured")) for d in recs if d.get("kind") == "time_factor"]
    run.res["time_factors"] = factors[:20]
    fuel = []
    for e in _tail("state.jsonl", 3_000_000):
        if e.get("ev") == "inven" and t_read - 2 < e["epoch"] < t_read + 40:
            for it in e["items"]:
                m = re.search(r"with (\d+) turns of light", it["name"])
                if m and it.get("equip"):
                    fuel.append((round(e["epoch"] - t_read, 1), int(m.group(1))))
        if e.get("ev") == "status" and t_read - 2 < e["epoch"] < t_read + 40:
            fuel.append((round(e["epoch"] - t_read, 1), "rest" if e["ind"].get("state", [0, 0, 0])[2] else "-",
                         e["ind"].get("hp", [0])[0]))
    run.res["fuel"] = fuel
    run.say(f"[{run.tag}] fuel/rest/HP after the read: {fuel}")
    run.check("recalled", t_yank is not None, f"{secs} s")
    run.check("rested while it charged", rested, "")
    run.check("about 10x sooner than standing (< 5 s)", secs is not None and secs < 5, f"{secs and round(secs, 1)} s")
