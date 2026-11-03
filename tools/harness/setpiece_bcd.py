"""setpiece_bcd -- set-pieces B: hazards (molds, drainers, thieves, traps); C: items and uniques; D: movement.

Run by setpiece.py (python3 setpiece.py ID); the framework (Run, ctl, log_since...) is setpiece_run.py.
"""
import json
import os
import re
import time

from setpiece_run import (RUN, ctl, pilot_view, log_since, messages_since, gold_now, floor_near, step_dir,
                         find_pocket, find_floor_block)


def c3(run):
    """C3: a unique's drop (Ulfast: DROP_90 | DROP_GOOD, no escort, never killed by Dive04 -- a
    repeat kill of a unique drops nothing, xtra2.c 'cheeze'; Lagduf's and Mughash's escorts made band fights) is picked up after the kill, whatever its bulk. (Not
    a unique Dive04 has killed: they drop nothing a second time -- Brodda, Bullroarer, Orfax, Wormtongue.)"""
    run.bring_dive04()
    run.t_act = time.time()
    out = {}
    # (as the Architect: C3 tests the pickup, and the hunt check rightly refuses Lagduf, LEAVE for his escort)
    run.place("Ulfast, Son of Ulfang", 1, after=lambda: out.update(reply=ctl("goal", "hunt", "Ulfast,_Son_of_Ulfang",
                                                                        role="architect")))
    run.res["order_reply"] = out.get("reply")
    run.watch(120, until=lambda recs: any(d.get("kind") == "attention" and d.get("what") == "unique_slain"
                                          and "Ulfast" in str(d.get("detail")) for d in recs))
    time.sleep(25)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    slain = next((d["t"] for d in recs if d.get("kind") == "attention" and d.get("what") == "unique_slain"
                  and "Ulfast" in str(d.get("detail"))), None)
    picked = [a for a in st["acts"] if "pick up" in str(a[2]) and slain and a[0] >= slain - run.t_act]
    left = [d for d in recs if d.get("kind") == "attention" and "left " in str(d.get("detail")) and "pack full" in str(d.get("detail"))]
    run.check("Ulfast slain", slain is not None, f"reply {str(out.get('reply'))[:120]}")
    run.check("his drop picked up", bool(picked) and not left, f"picked {picked[:3]}; left {[str(d.get('detail'))[:60] for d in left]}")


def c8(run):
    """C8: unidentified Boots of Free Action worn, a Floating eye's paralysing gaze: "You are unaffected!"
    -> the Pilot infers Free Action and protects the boots (keep, identify)."""
    v = run.bring_dive04()
    me = tuple(v["pos"])
    spot = floor_near(v, me, 1)
    for _ in range(30):
        g = run.dm.c.pos or (run.dm.status()["y"], run.dm.status()["x"])
        if tuple(g) == spot:
            break
        run.dm.walk(step_dir(g, spot))
    made = run.dm.forge(91, ego=58)
    run.res["notes"].append(f"forged: {made}")
    run.dm.drop_first()
    run.dm.walk(step_dir(me, spot) or 8)
    ctl("goal", "goto", f"{spot[0]},{spot[1]}", role="architect")
    time.sleep(4)
    ctl("pickup", role="architect")
    time.sleep(2)
    pack = ctl("pack", role="architect")
    boots = re.search(r"([a-w])\) (?:a )?Pair of Soft Leather Boots[^;]*", pack)
    run.check("boots picked up (unidentified)", bool(boots) and "Free Action" not in boots.group(0),
              boots.group(0) if boots else pack[:160])
    if not boots:
        return
    ctl("wear", boots.group(1), role="architect")
    time.sleep(2)
    run.t_act = time.time()
    run.place("Floating eye", 1)
    run.watch(40, until=lambda recs: any(d.get("kind") == "attention" and d.get("what") == "ability" for d in recs))
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    ab = [a for a in st["attention"] if a[1] == "ability"]
    run.check("Free Action inferred from 'You are unaffected!'", any("Free Action" in a[2] for a in ab), f"{ab[:1]}")
    run.check("the boots protected", any("soft leather boots" in a[2].lower() for a in ab), f"{ab[:1]}")


def d3(run, length=8):
    """D3: walled in, the one way out a secret door. Gandalf carves a corridor into solid rock (a secret
    door, then `length` floor squares) off a floor square of the level, and Dive04 is pulled to its far
    end, so it knows ground outside it can't reach. `goal explore`: it searches the dead ends (15 each)
    instead of ending with "frontier unreachable" or "nothing left", finds the door and walks out."""
    rows = run.dm.c.map()
    F, d = find_pocket(rows, length)
    if not F:
        run.check("a site for the pocket", False, "no floor square with rock beside it")
        return
    door = (F[0] + d[0], F[1] + d[1])
    pocket = [(F[0] + d[0] * k, F[1] + d[1] * k) for k in range(2, length + 2)]
    fwd, back = step_dir((0, 0), d), step_dir(d, (0, 0))
    run.gandalf_to(door)
    run.dm.paint(48, [fwd])                       # the secret door (he steps onto the first corridor square)
    run.dm.paint(1, [fwd] * length)               # the corridor (he ends in the rock past it)
    run.dm.walk(back)                             # onto its far end: Dive04 is pulled here
    rows = run.dm.c.map()
    built = "".join(rows[y][x] for y, x in pocket)
    run.res["pocket"] = {"floor": F, "door": door, "corridor": [pocket[0], pocket[-1]], "dm_sees": built}
    run.say(f"[{run.tag}] pocket: door {door} off {F}, corridor {pocket[0]}-{pocket[-1]} ({built!r})")
    v = run.bring_dive04()
    run.dm.walk(fwd, 2)                           # Gandalf back into the rock
    inside = set(pocket)
    if tuple(v["pos"]) not in inside:
        run.check("Dive04 in the pocket", False, f"at {v['pos']}")
        return
    run.t_act = time.time()
    reply = ctl("goal", "explore", role="architect")
    run.res["order_reply"] = reply

    def out(recs):
        return any(d.get("pos") and tuple(d["pos"]) not in inside and tuple(d["pos"]) != door for d in recs
                   if d["t"] > run.t_act)
    run.watch(300, until=out)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    searches = sum(1 for d in recs if d.get("kind") == "act" and "secret" in str(d.get("why")))
    t_out = next((round(d["t"] - run.t_act, 1) for d in recs if d.get("pos") and tuple(d["pos"]) not in inside
                  and tuple(d["pos"]) != door), None)
    gave_up = [a for a in st["attention"] if a[1] in ("goal_done", "goal_failed") and
               ("nothing left" in a[2] or "unreachable" in a[2]) and (t_out is None or a[0] < t_out)]
    run.check("walked out through the door", t_out is not None, f"out after {t_out} s, {searches} searches")
    run.check("no giving up before the door", not gave_up, f"{gave_up[:1]}")


def b6(run, width=9):
    """B6 (the trap half): a known trap on the straight way across a room. Gandalf paints a pit (terrain 17) in
    the middle of a 5 x `width` block of floor; Dive04 stands near one end and gets a goto to the square
    mirroring it through the pit: it walks round the trap, even if it only comes into view on the way (the
    mover checks for traps when it plans)."""
    rows = run.dm.c.map()
    tl = find_floor_block(rows, 5, width)
    if not tl:
        run.check("a site", False, f"no 5 x {width} block of floor")
        return
    a, trap = (tl[0] + 2, tl[1] + 1), (tl[0] + 2, tl[1] + width // 2)
    run.gandalf_to(trap)
    run.dm.paint(17, [8])                         # the pit (he steps north off it)
    run.res["scene"] = {"from": a, "trap": trap, "dm_sees": run.dm.c.map()[trap[0]][trap[1]]}
    run.gandalf_to(a)
    v = run.bring_dive04()
    run.dm.walk(8, 3)                              # out of the way
    me = tuple(v["pos"])
    b = (2 * trap[0] - me[0], 2 * trap[1] - me[1])
    run.res["scene"]["to"] = b
    run.say(f"[{run.tag}] Dive04 at {v['pos']}, pit at {trap}, goto {b}")
    run.t_act = time.time()
    reply = ctl("goal", "goto", f"{b[0]},{b[1]}", role="architect")
    run.res["order_reply"] = reply
    run.watch(40, until=lambda recs: any(d.get("kind") == "attention" and d.get("what") in ("goal_done", "goal_failed")
                                         for d in recs))
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    on = [round(d["t"] - run.t_act, 1) for d in recs if d.get("pos") and tuple(d["pos"]) == trap]
    msgs = [t for _, t in messages_since(run.t_act) if re.search(r"pit|trap", t, re.I)]
    done = [a for a in st["attention"] if a[1] in ("goal_done", "goal_failed")]
    run.check("never on the trap", not on and not any("fall into" in t for t in msgs), f"on it at {on[:3]}; {msgs[:2]}")
    run.check("arrived", any(a[1] == "goal_done" for a in done), f"{done[:1]}")


def b4(run, walking=False):
    """B4: a town thief (m15-m19 lost ~300 gold to urchins and a Scruffy hobbit while townfarming). A
    Scruffy looking hobbit (touches to steal gold, then teleports) summoned 2 squares from Dive04 in town, no
    orders: it's killed or kept off before it touches; no gold lost. B4w: the same while Dive04 walks
    across town (a goto 25+ squares off, the thief 2 squares ahead on the way)."""
    v = run.bring_dive04()
    time.sleep(2.5)
    g0 = gold_now()
    run.t_act = time.time()
    if walking:
        me = tuple(v["pos"])
        # open ground 20-30 squares off, as level with Dive04 as can be (not the town's edge rows)
        cands = [(v["y0"] + i, v["x0"] + j) for i, row in enumerate(v["rows"]) for j, ch in enumerate(row)
                 if ch in ". " and 3 <= v["y0"] + i <= 62]
        cands = [q for q in cands if 20 <= abs(q[1] - me[1]) <= 30]
        far = min(cands, key=lambda q: abs(q[0] - me[0])) if cands else None
        if not far:
            run.check("a goto target", False, "no open ground 20-30 squares off")
            return
        out = {}
        # the thief lands, then the goto: it's on (or near) the way
        run.place("Scruffy looking hobbit", 2, after=lambda: out.update(
            reply=ctl("goal", "goto", f"{far[0]},{far[1]}", role="architect")))
        run.res["order_reply"] = out.get("reply")
    else:
        run.place("Scruffy looking hobbit", 2)
    run.watch(40)
    g1 = gold_now()
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    msgs = [t for _, t in messages_since(run.t_act)]
    run.res["messages"] = msgs[:40]
    touched = [t for t in msgs if re.search(r"purse|gold|touches you", t, re.I)]
    killed = [t for t in msgs if re.search(r"You have (slain|killed) (the )?Scruffy", t)]
    run.check("no gold lost", g0 is not None and g1 is not None and g1 >= g0, f"gold {g0} -> {g1}; {touched[:2]}")
    run.check("thief killed", bool(killed), f"{killed[:1]}")


def b4w(run):
    """B4w: the town thief while Dive04 walks across town."""
    b4(run, walking=True)


def b1(run):
    """B1: a stationary drainer (a Purple mushroom patch: CON) 2 squares off and a goto past it: Dive04 never
    stands next to it and loses no stat. (Summoned adjacent, the server's auto-retaliate kills it in one blow
    before the Pilot can act: that tests the server, not the path.)"""
    run.bring_dive04()
    before = re.search(r"CON (\S+)", ctl("status", role="architect"))
    run.t_act = time.time()
    spot = run.place("Purple mushroom patch", 2)
    me = tuple(pilot_view()["pos"])
    beyond = (spot[0] + 2 * (spot[0] - me[0]) // 2, spot[1] + 2 * (spot[1] - me[1]) // 2)
    run.res["order_reply"] = ctl("goal", "goto", f"{beyond[0]},{beyond[1]}", role="architect")
    run.watch(25)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    after = re.search(r"CON (\S+)", ctl("status", role="architect"))
    hits = [d for d in recs if d.get("kind") == "mons"]
    drained = [a for a in st["attention"] if a[1] == "stat_drained"]
    run.check("no stat drained", not drained, f"CON {before.group(1) if before else '?'} -> {after.group(1) if after else '?'}; {drained[:1]}")
    adjacent = sum(1 for d in recs if d.get("kind") == "mons" for m in d.get("monsters", [])
                   if m[2] == "Purple mushroom patch" and max(abs(m[0] - d["pos"][0]), abs(m[1] - d["pos"][1])) <= 1)
    run.check("never next to it", adjacent == 0, f"{adjacent} records adjacent; goto: {run.res['order_reply'][:80]}")


def b2(run):
    """B2: mobile STR drainers (three Giant red ants): after a second drain on the level the Pilot leaves it, or
    kills the drainer beside it when that one is weak and no faster (the 'drained twice' rule)."""
    run.bring_dive04()
    run.t_act = time.time()
    for d in (2, 3, 4):
        run.place("Giant red ant", d)
    run.watch(60)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    drains = [a for a in st["attention"] if a[1] == "stat_drained"]
    after2 = [a for a in st["attention"] if a[1] in ("tactic", "danger_seen") and "drained twice" in a[2]]
    run.check("drained at most twice", len(drains) <= 2, f"{len(drains)} drains")
    run.check("acted on the second drain", len(drains) < 2 or bool(after2), f"{after2[:1]}")


def b3(run):
    """B3: a Brigand (touch to steal an item, then teleports) adjacent: the Pilot hits the thief first; nothing
    stolen, or the theft reported."""
    run.bring_dive04()
    run.t_act = time.time()
    run.place("Brigand", 1)
    run.watch(30)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    msgs = [json.loads(l) for l in open(os.path.join(RUN, "events.jsonl")) if '"message"' in l and "Brigand" in l]
    msgs = [m for m in msgs if m.get("epoch", 0) >= run.t_act]
    stolen = [m["text"] for m in msgs if "stole" in m["text"] or "touches you" in m["text"] and "purse" in m["text"]]
    slain = any("slain the Brigand" in m["text"] for m in msgs)
    run.res["notes"].append(f"messages: {[m['text'] for m in msgs][:8]}")
    run.check("Brigand slain", slain, "")
    run.check("nothing stolen", not stolen, f"{stolen[:2]}")


def d6(run):
    """D6: movement speed: tiles a second while exploring (runs) in the dungeon; >= 3."""
    run.bring_dive04()
    run.t_act = time.time()
    ctl("goal", "explore", role="architect")
    run.watch(40)
    ctl("stop", role="architect")
    moves = [d for d in log_since(run.t_act) if d.get("kind") in ("move", "mons", "act") and d.get("pos")]
    path = []
    for d in moves:
        if not path or tuple(d["pos"]) != path[-1][1]:
            path.append((d["t"], tuple(d["pos"])))
    tiles = sum(max(abs(a[1][0] - b[1][0]), abs(a[1][1] - b[1][1])) for a, b in zip(path, path[1:]))
    secs = (path[-1][0] - path[0][0]) if len(path) > 1 else 0
    # the best 5-s window (a run), not the average with its stops to choose the next frontier
    best = 0.0
    for i, (t0, _) in enumerate(path):
        seg = [(t, q) for t, q in path[i:] if t - t0 <= 5]
        n = sum(max(abs(a[1][0] - b[1][0]), abs(a[1][1] - b[1][1])) for a, b in zip(seg, seg[1:]))
        best = max(best, n / 5)
    run.res["notes"].append(f"{tiles} tiles in {secs:.0f} s overall ({tiles / secs if secs else 0:.1f}/s); best 5 s {best:.1f}/s")
    run.check("runs >= 3 tiles/s (best 5-s window)", best >= 3, f"best {best:.1f} tiles/s; overall "
              f"{tiles / secs if secs else 0:.1f} ({tiles} in {secs:.0f} s)")
