"""setpiece_mh -- set-pieces M: mission regressions; H: the hot swap.

Run by setpiece.py (python3 setpiece.py ID); the framework (Run, ctl, log_since...) is setpiece_run.py.
"""
import re
import subprocess
import time

from setpiece_run import (race_idx, ctl, pilot_view, log_since, messages_since, floor_near, find_floor_block, FREEZE,
                         HOTSWAP)


def m1(run, race="Brown mold"):
    """M1: a stationary monster beside the only known '>' (m25: a Brown mold, which confuses and so is never
    fought, beside the '>' at 300 ft; the step-away walked 6 squares back, the dive pressed '>' there, and it
    looped 2 minutes). A '>' painted 6 squares from Dive04, a Brown mold summoned beside it, `goal dive` one
    level down: Dive04 goes down those stairs within 45 s, pressing '>' nowhere else."""
    rows = run.dm.c.map()
    tl = find_floor_block(rows, 5, 9)            # (a room on Gandalf's map: he sees the whole level)
    if not tl:
        run.check("a site", False, "no 5 x 9 block of floor")
        return
    start, stairs, mold = (tl[0] + 2, tl[1] + 1), (tl[0] + 2, tl[1] + 7), (tl[0] + 1, tl[1] + 7)
    run.gandalf_to(stairs)
    run.dm.paint(7, [8])                         # the '>' (he steps north off it, onto the mold's square)
    name = run.dm.summon(race_idx(race), step=8, after=None)
    run.gandalf_to(start)
    v = run.bring_dive04()
    run.dm.walk(2, 3)                            # out of the way
    me = tuple(v["pos"])
    run.res["scene"] = {"dive04": me, "stairs": stairs, "mold": mold, "summoned": name}
    run.say(f"[{run.tag}] Dive04 at {me}, '>' at {stairs}, {name} at {mold}")
    time.sleep(2.0)
    run.t_act = time.time()
    run.res["order_reply"] = ctl("goal", "dive", str(run.depth + 50), role="architect")
    run.watch(45, until=lambda recs: any(d.get("depth") is not None and d["depth"] * 50 > run.depth for d in recs))
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    presses = [(round(d["t"] - run.t_act, 1), tuple(d["pos"])) for d in recs
               if d.get("kind") == "act" and d.get("cmd") == "custom >" and d.get("pos")]
    down = next((round(d["t"] - run.t_act, 1) for d in recs if d.get("depth") is not None and d["depth"] * 50 > run.depth),
                None)
    stray = [p for p in presses if p[1] not in (stairs, me)]   # (the first press on arrival probes the tile underfoot)
    run.check("down the painted '>' within 45 s", down is not None, f"at {down} s; presses {presses[:6]}")
    run.check("no '>' pressed off the stairs", not stray, f"{stray[:4]}")


def m2(run):
    """M2: a valuable beyond loot_radius (the user's m29 question: an unknown wand left 12 squares off). A forged
    Wand of Stinking Cloud dropped on floor Dive04 sees 13-20 squares away, a '>' painted 3 squares the other
    way, `goal dive` one level down: Dive04 fetches the wand first, then goes down, within 60 s."""
    rows = run.dm.c.map()
    tl = find_floor_block(rows, 3, 24) or find_floor_block(rows, 3, 18)
    if not tl:
        run.check("a site", False, "no 3 x 18 block of floor")
        return
    run.gandalf_to((tl[0] + 1, tl[1] + 2))
    v = run.bring_dive04()
    me = tuple(v["pos"])
    y0, x0 = v["y0"], v["x0"]
    seen = [(y0 + i, x0 + j) for i, row in enumerate(v["rows"]) for j, ch in enumerate(row) if ch == "."]
    far = [q for q in seen if 13 <= max(abs(q[0] - me[0]), abs(q[1] - me[1])) <= 20 and q[1] > me[1]]
    if not far:
        run.check("a site", False, f"no floor Dive04 sees 13-20 squares east of {me} (a dark room?)")
        return
    spot = min(far, key=lambda q: (abs(q[0] - me[0]), -q[1]))
    stairs = floor_near(v, me, 3, taken={spot})
    stairs = next((q for q in seen if q[1] <= me[1] - 2 and max(abs(q[0] - me[0]), abs(q[1] - me[1])) == 3), stairs)
    run.gandalf_to(stairs)
    run.dm.paint(7, [8])                         # the '>' (he steps north off it)
    run.gandalf_to(spot)
    name = run.dm.forge(290)                     # Wand of Stinking Cloud (identified)
    run.dm.drop_first(1)
    for _ in range(8):                           # out of the room, into the rock (a ghost)
        run.dm.walk(8)
    run.res["scene"] = {"dive04": me, "wand": spot, "stairs": stairs, "forged": name}
    run.say(f"[{run.tag}] Dive04 at {me}, {name} at {spot} ({max(abs(spot[0] - me[0]), abs(spot[1] - me[1]))} "
            f"away), '>' at {stairs}")
    time.sleep(2.0)
    run.t_act = time.time()
    run.res["order_reply"] = ctl("goal", "dive", str(run.depth + 50), role="architect")
    run.watch(60, until=lambda recs: any(d.get("depth") is not None and d["depth"] * 50 > run.depth for d in recs))
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    picked = next((round(d["t"] - run.t_act, 1) for d in recs if d.get("kind") == "act"
                   and "Stinking Cloud" in str(d.get("why")) and "pick up" in str(d.get("why"))), None)
    down = next((round(d["t"] - run.t_act, 1) for d in recs if d.get("depth") is not None and d["depth"] * 50 > run.depth),
                None)
    left = [d.get("items") for d in recs if d.get("kind") == "left_behind"]
    run.check("the wand fetched", picked is not None, f"picked up at {picked} s; left behind {left[:2]}")
    run.check("then down the '>' within 60 s", down is not None and (picked is None or down > picked), f"at {down} s")


def m3(run):
    """M3: an unseen stat drainer (m29, m30: a Moaning spirit -- invisible, passes walls, +10, TOUCH:LOSE_DEX).
    A '>' painted 6 squares from Dive04, a Moaning spirit summoned 2 squares off, no orders: once DEX is drained
    Dive04 leaves the level within 30 s (Dive04 is restored afterwards)."""
    rows = run.dm.c.map()
    tl = find_floor_block(rows, 5, 9)
    if not tl:
        run.check("a site", False, "no 5 x 9 block of floor")
        return
    start, stairs = (tl[0] + 2, tl[1] + 1), (tl[0] + 2, tl[1] + 7)
    run.gandalf_to(stairs)
    run.dm.paint(7, [8])                         # the '>'
    run.gandalf_to(start)
    v = run.bring_dive04()
    run.dm.walk(2, 3)
    time.sleep(1.5)
    run.t_act = time.time()
    run.place("Moaning spirit", 2)
    run.watch(90, until=lambda recs: any(d.get("depth") is not None and d["depth"] * 50 != run.depth for d in recs))
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    drained = next((round(d["t"] - run.t_act, 1) for d in recs if d.get("what") == "stat_drained"), None)
    left = next((round(d["t"] - run.t_act, 1) for d in recs if d.get("depth") is not None and d["depth"] * 50 != run.depth),
                None)
    run.res["scene"] = {"dive04": tuple(v["pos"]), "stairs": stairs}
    if drained is None:
        run.check("drained (the scene happened)", False, f"no drain in 90 s; left at {left}")
        return
    run.check("left within 30 s of the drain", left is not None and left - drained <= 30,
              f"drained at {drained} s, left at {left} s")


def m5(run, n=30):
    """M5: a confusing breeder swarm (m55 at 800 ft: Hummerhorns kept Dive04 confused from 17:04 to 17:19; the dive
    waited for the confusion to wear off, two staff uses failed, the recall couldn't be read). A '>' painted 8 squares
    from Dive04, n Hummerhorns summoned 1-2 squares round it, `goal dive` one level down. Pass: confused (the scene
    happened); the Pilot cures a long confusion itself (CSW/CCW within 20 s of it starting, at most 4); down those
    stairs within 120 s; lowest HP >= 60%. (20 of them: 8 died to one blow each before a single bite.)"""
    rows = run.dm.c.map()
    tl = find_floor_block(rows, 5, 11)
    if not tl:
        run.check("a site", False, "no 5 x 11 block of floor")
        return
    start, stairs = (tl[0] + 2, tl[1] + 1), (tl[0] + 2, tl[1] + 9)
    run.gandalf_to(stairs)
    run.dm.paint(7, [8])                         # the '>'
    run.gandalf_to(start)
    v = run.bring_dive04()
    # (Hummerhorn bites rarely land at AC 76 -- power 10 + 3 x 16 vs 3/4 AC: ~6% -- so three runs were never
    # confused, and a forged Potion of Confusion is junk the Pilot destroys underfoot. Stage m55's state by AC instead:
    # the body armour, shield and Protection rings off (AC ~20: ~70% a bite); charsave restores the gear)
    ctl("order", "autowear=off", role="architect")      # (or the Pilot wears it all again at once)
    for slot in ("E", "G", "B", "C"):
        ctl("takeoff", slot, role="architect")
        time.sleep(1.2)
    run.res["ac"] = re.findall(r"AC (\d+)", ctl("gear", role="architect"))[:1]
    run.dm.walk(2, 3)
    time.sleep(1.5)
    for k in range(n):
        try:
            run.place("Hummerhorn", 1 + k % 3)
        except RuntimeError as e:
            run.res["notes"].append(str(e))
    # (m55's state: confused before the leave -- run 1 went down in 5.7 s, unbitten; with 8, all died to one blow
    # each before a bite. 20, and wait for the first confusion up to 45 s; auto-retaliate fights the swarm meanwhile)
    run.t_act = time.time()
    t_end = time.time() + 90
    while time.time() < t_end and not any(m.startswith("You are confused") for _, m in messages_since(run.t_act)):
        time.sleep(1.0)
    run.res["order_reply"] = ctl("goal", "dive", str(run.depth + 50), role="architect")
    run.watch(120, until=lambda recs: any(d.get("depth") is not None and d["depth"] * 50 > run.depth for d in recs))
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    msgs = messages_since(run.t_act)
    conf = next((round(t - run.t_act, 1) for t, m in msgs if m.startswith("You are confused")), None)
    cures = [(round(d["t"] - run.t_act, 1), str(d.get("why"))[:50]) for d in recs
             if d.get("kind") == "act" and str(d.get("why")).startswith("confused")]
    down = next((round(d["t"] - run.t_act, 1) for d in recs if d.get("depth") is not None and d["depth"] * 50 > run.depth),
                None)
    run.res["scene"] = {"dive04": tuple(v["pos"]), "stairs": stairs, "hummerhorns": n}
    if conf is None:
        run.check("confused (the scene happened)", False, f"never confused; down at {down} s")
        return
    run.check("a long confusion cured by the Pilot within 20 s", bool(cures) and cures[0][0] - conf <= 20,
              f"confused at {conf} s; cures {cures[:4]}")
    run.check("at most 4 cures", len(cures) <= 4, f"{len(cures)}")
    run.check("down the painted '>' within 120 s", down is not None, f"at {down} s")
    if st["hp_min"]:
        run.check("lowest HP >= 60%", st["hp_min"][0] >= 0.6 * st["hp_min"][1], f"lowest {st['hp_min']}")


def h1(run, recall=False):
    """H1: the hot swap (tools/pilot/hotswap.sh) mid-trip, in the dungeon: a trip plan working the level, a Cave orc
    3 squares off; freeze, swap the Pilot, and before the thaw the new Pilot must see Dive04 where it was, with the
    same HP and the orc where it was (resumed in memory, not reloaded); after the thaw the plan carries on. H1r: the
    same with a Word of Recall read just before: it still lands."""
    run.bring_dive04()
    run.place("Cave orc", 3)                     # (in view: a dark room shows only the lantern's 2 squares + infravision)
    run.dm.walk(2, 8)                              # Gandalf out of the way
    time.sleep(2)
    run.res["plan_reply"] = ctl("plan", "trip", f"{run.depth}-{run.depth}", "until", "minutes>10", "then", "recall",
                                role="architect")
    time.sleep(4)
    if recall:
        run.res["recall_reply"] = ctl("read", "Recall", role="architect")
        time.sleep(1.5)
    subprocess.run([FREEZE, "on"], capture_output=True)
    time.sleep(1.5)
    def live_hp():                               # (state.jsonl's thinned status can lag a regeneration tick)
        m = re.search(r"HP (\d+)/(\d+)", ctl("status", role="architect"))
        return [int(m.group(1)), int(m.group(2))] if m else None
    before, hp0, d0 = pilot_view(), live_hp(), run._depth()
    run.t_act = time.time()
    out = subprocess.run([HOTSWAP, "Dive04"], capture_output=True, text=True, timeout=240)
    swap_s = round(time.time() - run.t_act, 1)
    after, hp1, d1 = pilot_view(), live_hp(), run._depth()
    still = subprocess.run([FREEZE, "status"], capture_output=True, text=True).stdout.strip()
    run.res["swap"] = {"seconds": swap_s, "out": out.stdout.strip().splitlines()[-4:], "frozen_after": still}
    t_thaw = time.time()
    subprocess.run([FREEZE, "off"], capture_output=True)
    if recall:
        run.watch(60, until=lambda recs: any(d.get("depth") == 0 for d in recs))
    else:
        time.sleep(30)
    recs = log_since(run.t_act)
    run.res["stats"] = run.stats(recs)
    mons0 = sorted(tuple(m[:2]) for m in before.get("mons", []))
    mons1 = sorted(tuple(m[:2]) for m in after.get("mons", []))
    run.res["scene"] = {"pos": [before.get("pos"), after.get("pos")], "hp": [hp0, hp1], "depth": [d0, d1],
                        "mons": [mons0, mons1]}
    run.check("swapped while frozen", "FROZEN" in still, f"{swap_s} s; {run.res['swap']['out']}")
    run.check("resumed in place", after.get("pos") == before.get("pos") and d1 == d0 and hp1 == hp0,
              f"pos {before.get('pos')} -> {after.get('pos')}, depth {d0} -> {d1}, HP {hp0} -> {hp1}")
    if mons0 or mons1:
        run.check("nothing moved while frozen", mons0 == mons1, f"monsters {mons0} -> {mons1}")
    else:
        run.res["notes"].append("no monster in view at the freeze (killed first): the 'nothing moved' check n/a")
    resumed = any(d.get("kind") == "plan_resumed" for d in recs)
    acted = [round(d["t"] - t_thaw, 1) for d in recs if d["t"] > t_thaw and d.get("kind") in ("act", "move")]
    # (with a recall pending the Pilot rightly waits for it rather than acting: there the landing is the proof)
    run.check("the plan resumed" + ("" if recall else " and the Pilot acts after the thaw"),
              resumed and (recall or bool(acted)), f"plan_resumed {resumed}; first act {acted[:1]} s after the thaw")
    if recall:
        home = next((round(d["t"] - t_thaw, 1) for d in recs if d.get("depth") == 0 and d["t"] > t_thaw), None)
        run.check("the recall still landed", home is not None, f"in town {home} s after the thaw")


def h1r(run):
    """H1r: H1 with a Word of Recall read just before the swap."""
    h1(run, recall=True)


def m4(run):
    """M4: a crowd in the open (m30 06:43: hounds, a Druid, an Umber hulk...; the Advisor's estimator memo rules).
    An Umber hulk, Fire and Energy hounds, two Uruks and a Dark elven priest summoned 1-2 squares round Dive04 in a
    room (Dive04 beat four Uruks and a priest without an emergency): no HP cure with 2+ adjacent; an
    escape read with 4+ about is a teleport, not Phase Door; lowest HP >= 40%."""
    rows = run.dm.c.map()
    tl = find_floor_block(rows, 7, 11)
    if not tl:
        run.check("a site", False, "no 7 x 11 block of floor")
        return
    run.gandalf_to((tl[0] + 3, tl[1] + 5))
    run.bring_dive04()
    run.dm.walk(8, 2)
    time.sleep(1.5)
    run.t_act = time.time()
    for race, d in (("Umber hulk", 1), ("Fire hound", 1), ("Fire hound", 2), ("Energy hound", 2), ("Uruk", 1),
                    ("Uruk", 2), ("Dark elven priest", 2)):
        try:
            run.place(race, d)
        except RuntimeError as e:
            run.res["notes"].append(str(e))
    run.dm.walk(8, 6)
    run.watch(60, until=lambda recs: any(d.get("depth") is not None and d["depth"] * 50 != run.depth for d in recs))
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    adj_n, near_n, bad_cures, phases_in_crowd, teles = 0, 0, [], [], []
    for d in recs:
        if d.get("kind") == "mons" and d.get("pos"):
            p = d["pos"]
            ds = [max(abs(m[0] - p[0]), abs(m[1] - p[1])) for m in d.get("monsters", [])]
            adj_n, near_n = sum(1 for x in ds if x == 1), sum(1 for x in ds if x <= 5)
        if d.get("kind") == "act":
            why = str(d.get("why"))
            t = round(d["t"] - run.t_act, 1)
            if "quaff" in why and "Cure" in why and "blind" not in why and "confused" not in why and adj_n >= 2:
                bad_cures.append((t, adj_n, why[:60]))
            if "phase door" in why.lower() and near_n >= 4 and "agent" not in why:
                phases_in_crowd.append((t, near_n))
            if "teleport" in why.lower():
                teles.append(t)
    run.check("no HP cure with 2+ adjacent", not bad_cures, f"{bad_cures[:3]}")
    run.check("teleport, not Phase Door, with 4+ about", not phases_in_crowd, f"phases with 4+ near: "
              f"{phases_in_crowd[:3]}; teleports at {teles[:3]}")
    if st["hp_min"]:
        run.check("lowest HP >= 40%", st["hp_min"][0] >= 0.4 * st["hp_min"][1], f"lowest {st['hp_min']}")
