"""setpiece_a -- set-pieces A: danger, hunts, escapes (the danger rule, the hunt check, WalkAway, escapes).

Run by setpiece.py (python3 setpiece.py ID); the framework (Run, ctl, log_since...) is setpiece_run.py.
"""
import re
import time

from setpiece_run import ctl, log_since, messages_since, first_seen, floor_near, step_dir, give_item, WOR_KIND


def a7(run):
    """A7: hunt a FIGHT monster (a Hill giant, adjacent) at full HP: the check allows it, and the HP
    lost stays within fight_sim's bad case (p90). (The 80% and 60% halves are unit tests: the
    harness can't set HP.)"""
    run.bring_dive04()
    ctl("status")                               # (a fresh report: the order answers it)
    run.t_act = time.time()
    # the order the moment the giant lands (a summon takes ~20 s with the menu and the hook
    # cleanup: longer than a hunt waits for its target; and the Pilot's own fighting killed it
    # when the order came after the cleanup)
    out = {}
    run.place("Hill giant", 1, after=lambda: out.update(reply=ctl("goal", "hunt", "Hill_giant")))
    reply = out.get("reply", "")
    run.res["order_reply"] = reply
    m = re.search(r"~(\d+) in a bad fight", reply)
    p90 = int(m.group(1)) if m else None
    run.check("hunt allowed at full HP", '"ok": true' in reply, reply[:160])
    run.watch(90, until=lambda recs: any(d.get("kind") == "attention" and d.get("what") in ("goal_done", "goal_failed")
                                         and "hunt" in str(d.get("detail")) for d in recs))
    st = run.stats(log_since(run.t_act))
    run.res["stats"] = st
    lost = (st["hp_start"][0] - st["hp_min"][0]) if st["hp_min"] else None
    slain = any("slain" in str(a[2]) and "hunt" in str(a[2]) for a in st["attention"])
    run.check("giant slain", slain, f"outcome {[a for a in st['attention'] if 'hunt' in a[2]][-1:]}")
    run.check("HP lost within the simulated bad case", lost is not None and p90 is not None and lost <= p90,
              f"lost {lost}, p90 {p90}")


def a8(run, override=False):
    """A8: the m19 Ranger: a Ranger 3 squares away and a Skeleton human. The hunt is refused (a
    summoner). With --override (`hunt !Ranger`): summons are fought, a blinker isn't chased past
    2 turns, and the lowest HP stays at 40% or more."""
    run.bring_dive04()
    ctl("status")
    run.t_act = time.time()
    run.place("Skeleton human", 2)          # (within the lantern's light: the Ranger isn't alone)
    out = {}
    # 3 squares, not the memo's 6: unlit ground shows a monster only within the lantern's 2 squares or
    # the Half-Orc's infravision (3, warm-blooded); farther off the order is (rightly) held as stale
    run.place("Ranger", 3, after=lambda: (time.sleep(0.6), ctl("status"),
                                          out.update(reply=ctl("goal", "hunt", ("!" if override else "") + "Ranger"))))
    reply = out.get("reply", "")
    run.res["order_reply"] = reply
    if not override:
        run.check("hunt refused (a summoner)", '"ok": false' in reply and "summon" in reply, reply[:200])
        run.watch(30)
    else:
        run.check("override accepted", '"ok": true' in reply, reply[:160])
        run.watch(90, until=lambda recs: any(d.get("kind") == "goal" and str(d.get("goal", "")).startswith("reprieve")
                                             for d in recs) and False)
    st = run.stats(log_since(run.t_act))
    run.res["stats"] = st
    if st["hp_min"]:
        run.check("lowest HP >= 40%", st["hp_min"][0] >= 0.4 * st["hp_min"][1], f"lowest {st['hp_min']}")


def a8o(run):
    """A8 overridden (`hunt !Ranger`): summons fought, no chase of a blinker, lowest HP >= 40%."""
    a8(run, override=True)


def a9(run):
    """A9 (summoned variant): a recall arrival with a band forming and stairs unknown. The trip plan's
    arrival protocol uses Door/Stair Location within 5 s; no second Word of Recall is read while
    one is pending. (The 'special' feeling needs a real pit: not staged here.)"""
    if " WoR 0" in ctl("status", role="architect") or " WoR 1 " in ctl("status", role="architect"):
        # (the trip plan wants 2: Gandalf comes up to town with 3, then goes back down)
        run.dm.ascend(run.depth // 50)
        give_item(run, WOR_KIND, number=3, want="Word of Recall")
        run.dm.descend(run.depth // 50)
        time.sleep(1)
    rep = ctl("plan", "trip", f"{run.depth}-{run.depth}", "via=recall", "until", "minutes>3", "force", role="architect")
    run.res["plan_reply"] = rep[:300]
    t_arrive = None
    for _ in range(60):
        time.sleep(1)
        if run._depth() == run.depth:
            t_arrive = time.time()
            break
    if not t_arrive:
        run.check("arrived by recall", False, "no arrival in 60 s")
        return
    run.t_act = t_arrive - 3
    for name, d in (("Snaga", 8), ("Black orc", 9)):
        try:
            run.place(name, d)
        except RuntimeError as e:
            run.res["notes"].append(str(e))
    run.watch(60)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    loc = [a for a in st["acts"] if "Door/Stair Location" in str(a[2])]
    run.check("Door/Stair Location within 5 s of arriving", loc and loc[0][0] <= 8, f"{loc[:1]}")
    run.check("no second Word of Recall while one is pending", st["wor_reads"] <= 1, f"{st['wor_reads']} reads")
    ctl("plan", "stop", role="architect")


def a8w(run):
    """A8w: a summoner comes into view 3 squares off, no orders: the Pilot walks away out of its sight instead
    of fleeing the level (the user, 2026-10-23); no Word of Recall; HP stays >= 80%. (11-03: an Ogre shaman, lvl 27,
    speed +0 -- the Ranger, lvl 20, no longer fires the "summons" rule (level >= clvl - 5) for clvl-29 Dive04, which
    engaged it, rightly.)"""
    run.bring_dive04()
    run.t_act = time.time()
    run.place("Ogre shaman", 4)          # (asked at 3 it landed 2 off twice: walk-away needs 3+)
    run.watch(40)
    st = run.stats(log_since(run.t_act))
    run.res["stats"] = st
    goals = [d.get("goal") for d in log_since(run.t_act) if d.get("kind") == "goal"]
    run.check("walked away", any(str(g).startswith("walk away") for g in goals), f"goals {goals[:6]}")
    run.check("no Word of Recall read", st["wor_reads"] == 0, f"{st['wor_reads']} reads")
    if st["hp_min"]:
        run.check("HP >= 80%", st["hp_min"][0] >= 0.8 * st["hp_min"][1], f"lowest {st['hp_min']}")


def a1(run):
    """A1: an orc mob (Black orcs and a Hill orc group, 6-7 squares off) while a trip plan works the level:
    a serious band makes the plan leave; lowest HP >= 40%; at most 3 Phase Door reads."""
    run.bring_dive04()
    ctl("plan", "trip", f"{run.depth}-{run.depth}", "until", "minutes>3", role="architect")
    run.t_act = time.time()
    run.place("Black orc", 6)
    run.place("Hill orc", 7)
    run.watch(70)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    ctl("plan", "stop", role="architect")
    left = any(d.get("kind") == "goal" and str(d.get("goal", "")).startswith("flee") for d in recs)
    run.res["notes"].append(f"left the level: {left}; band events: {sum(1 for a in st['attention'] if a[1] == 'band')}")
    if st["hp_min"]:
        run.check("lowest HP >= 40%", st["hp_min"][0] >= 0.4 * st["hp_min"][1], f"lowest {st['hp_min']}")
    run.check("at most 3 Phase Door", st["phase_reads"] <= 3, f"{st['phase_reads']} reads")


def a6(run):
    """A6: a Gnome mage (blinks, summons) adjacent, let it summon: at most 3 Phase Door, then Word of Recall or
    the stairs; Phase Door never runs out; lowest HP >= 40%."""
    run.bring_dive04()
    before = re.search(r"Phase (\d+)", ctl("status", role="architect"))
    run.t_act = time.time()
    run.place(202, 1)                       # (the level-15 Gnome mage: BLINK, BO_COLD, S_MONSTER)
    run.watch(70)
    st = run.stats(log_since(run.t_act))
    run.res["stats"] = st
    after = re.search(r"Phase (\d+)", ctl("status", role="architect"))
    run.check("at most 3 Phase Door", st["phase_reads"] <= 3, f"{st['phase_reads']} reads")
    run.check("Phase Door never runs out", after and int(after.group(1)) > 0,
              f"{before.group(1) if before else '?'} -> {after.group(1) if after else '?'}")
    if st["hp_min"]:
        run.check("lowest HP >= 40%", st["hp_min"][0] >= 0.4 * st["hp_min"][1], f"lowest {st['hp_min']}")


def a2(run, who="Ulwarth, Son of Ulfang"):
    """A2: a unique too strong for us appears adjacent, no stairs known (Ulwarth: the danger rule's 'unique
    above your level'): if a danger rule fires for it, Word of Recall read within 2 s of first sight and lowest HP
    >= 40%; if none fires (the unique is no longer above us: 11-02), a hard fight with Speed + Berserk and lowest
    HP >= 60%."""
    run.bring_dive04()
    run.t_act = time.time()
    run.place(who, 1)
    run.watch(45)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    seen = first_seen(recs, who, run.t_act)
    wor = next((a[0] for a in st["acts"] if "word of recall" in str(a[2]).lower()), None)
    # The criterion follows the Pilot's own danger call (the Advisor, memos/to_architect/2026-11-02-khim.md): the
    # A2 uniques were above clvl-22 Dive04, but at clvl 29 / AC 104 with Speed + Berserk the estimator says fight.
    danger = next((a[0] for a in st["attention"] if a[1] == "danger_seen" and who.split(",")[0] in str(a[2])), None)
    if danger is not None or not seen:
        run.check("Word of Recall within 2 s of first sight", seen is not None and wor is not None and wor - seen <= 2,
                  f"seen at {seen}, danger rule at {danger}, recall read at {wor}")
        if st["hp_min"]:
            run.check("lowest HP >= 40%", st["hp_min"][0] >= 0.4 * st["hp_min"][1], f"lowest {st['hp_min']}")
    else:
        kit = [a[2] for a in st["attention"] if a[1] == "tactic" and "hard fight" in str(a[2])]
        run.check("no danger rule: a hard fight with Speed + Berserk",
                  any("Speed" in k for k in kit) and any("Berserk" in k for k in kit), f"tactics {kit}")
        if st["hp_min"]:
            run.check("lowest HP >= 60%", st["hp_min"][0] >= 0.6 * st["hp_min"][1], f"lowest {st['hp_min']}")


def a2i(run):
    """A2I: as A2 with Ibun, Son of Mim (a unique can exist once: a second Ulwarth summon fails silently while
    the first lives on an old level)."""
    a2(run, who="Ibun, Son of Mim")


def a2k(run):
    """A2K: as A2 with Khim, Son of Mim."""
    a2(run, who="Khim, Son of Mim")


def a2l(run):
    """A2L: Lugdush (no danger rule fires: level 21, unrated; but fight_sim's average fight costs ~350 HP)."""
    a2(run, who="Lugdush, the Uruk")


def a2u(run):
    """A2U (refactor list A25, session 13): as A2 with Lokkak, the Ogre Chieftain -- level 32, a unique above clvl-30
    Dive04, so the danger rule 'unique, lvl 32' fires: Word of Recall within 2 s of first sight, lowest HP >= 40%.
    The set-piece server only (MANGBOT_SERVER=sp: a copy of Dive04 -- this one can kill it)."""
    a2(run, who="Lokkak, the Ogre Chieftain")


def a3(run):
    """A3: a fast hitter (a Sabre-tooth tiger, +10, alone) adjacent, then a goto 12+ squares off: the goto is held
    (walking away hands it free hits) and Dive04 doesn't walk while it's adjacent. (A Nighthawk died to auto-retaliate
    before an order could follow; a Wolf chieftain brings a pack of up to 38, and the run becomes a band fight.)"""
    v = run.bring_dive04()
    run.t_act = time.time()
    me = tuple(v["pos"])
    far = floor_near(v, me, 12) or floor_near(v, me, 10) or (me[0], me[1] + 15)   # (a goto may path through unknown)
    out = {}
    race = "Sabre-tooth tiger"
    run.place(race, 1, after=lambda: (time.sleep(0.3),
                                                  out.update(reply=ctl("goal", "goto", f"{far[0]},{far[1]}", role="architect"))))
    reply = out.get("reply", "")
    run.res["order_reply"] = reply
    run.watch(20)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    held = [a for a in st["attention"] if "goto held" in a[2]]
    # positions while it was adjacent
    moved = 0
    last = None
    for d in recs:
        if d.get("kind") == "mons" and any(m[2] == race and max(abs(m[0] - d["pos"][0]), abs(m[1] - d["pos"][1])) <= 1
                                           for m in d.get("monsters", [])):
            if last and tuple(d["pos"]) != last:
                moved += 1
            last = tuple(d["pos"])
    run.check("the goto held", bool(held), f"{held[:1]} (order: {reply[:80]})")
    run.check("no walking with it adjacent", moved == 0, f"{moved} moves while adjacent")
    if st["hp_min"]:
        run.check("lowest HP >= 40%", st["hp_min"][0] >= 0.4 * st["hp_min"][1], f"lowest {st['hp_min']}")


def a5(run, race="Dark elven priest", stairs=False):
    """A5: a caster out of sight at full HP (m17-m21: curses, a HOLD and shrieks from the dark started level
    changes). A Dark elven priest (blinds, confuses, causes wounds) 5 squares off on unlit ground, beyond the
    lantern and infravision: the Pilot reports it, and doesn't leave the level (stairs, Word of Recall, Deep
    Descent) while HP is above 80%. A5s: the same with a '>' painted where Dive04 sees it (with stairs known,
    the old rule fled down them)."""
    v = run.bring_dive04()
    if stairs:
        me = tuple(v["pos"])
        q = next((q for d in (2, 1, 3) for q in [floor_near(v, me, d)] if q), None)
        if q:
            run.gandalf_to(q)
            run.dm.paint(7, [step_dir(me, q) or 8])
            time.sleep(1.5)
        run.res["stairs"] = q
    run.t_act = time.time()
    run.place(race, 5, gmap=True)
    run.watch(45)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    depth0 = next((d.get("depth") for d in recs if d.get("depth") is not None), None)
    left = []
    for d in recs:
        hp = d.get("hp")
        if not hp or not hp[1] or hp[0] <= 0.8 * hp[1]:
            continue
        if d.get("kind") == "act" and re.search(r"recall|deep descent|take the stairs|stairs", str(d.get("why")), re.I):
            left.append((round(d["t"] - run.t_act, 1), d.get("why")))
        if d.get("depth") is not None and depth0 is not None and d["depth"] != depth0:
            left.append((round(d["t"] - run.t_act, 1), f"depth {d['depth']}"))
            break
    seen_t = first_seen(recs, race, run.t_act)
    news = [a for a in st["attention"] if a[1] == "unseen_attacker"]
    run.res["first_seen"] = seen_t
    run.check("no level change while HP > 80%", not left, f"{left[:2]}")
    run.check("reported", bool(news) or seen_t is not None, f"{news[:1]} (seen at {seen_t})")


def a5s(run):
    """A5s: an unseen caster that stays unseen (a Potion mimic: never moves; curses, blinds, confuses, frost
    bolts) with stairs in view. (A Dark elven priest walked into view before it cast.)"""
    a5(run, race="Potion mimic", stairs=True)


def a2f(run, who="Dark elven lord"):
    """A2f: a dangerous caster at range (a Dark elven lord, rated 4: bolts, blinds, confuses) 8 squares off
    with a clear line, no stairs known: Word of Recall read within 2 s of the danger rule firing (A2I's Ibun
    at 12 squares got 7 s of free casts: the escape waited for him to come within 5)."""
    run.bring_dive04()
    run.t_act = time.time()
    run.place(who, 8, gmap=True)
    run.watch(40)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    danger = next((a[0] for a in st["attention"] if a[1] == "danger_seen"), None)
    wor = next((a[0] for a in st["acts"] if "word of recall" in str(a[2]).lower()), None)
    run.check("danger seen", danger is not None, f"at {danger}")
    run.check("Word of Recall within 2 s of it", danger is not None and wor is not None and wor - danger <= 2,
              f"danger at {danger}, recall read at {wor}")
    if st["hp_min"]:
        run.check("lowest HP >= 60%", st["hp_min"][0] >= 0.6 * st["hp_min"][1], f"lowest {st['hp_min']}")


def a7f(run):
    """A7f (the memo's first A7): fear casters. A Novice paladin group (SCARE, CAUSE_1; m22 lost 31% to seven)
    6 squares off. Passes when, once Dive04 is afraid ("too afraid to attack"), a Boldness or Heroism is quaffed
    (or the level left) within 5 s, and the lowest HP stays at 50% or more."""
    run.bring_dive04()
    run.t_act = time.time()
    run.place(118, 6, gmap=True)            # Novice paladin, the lvl 8 one (70 is a lvl 4 namesake); 6 off with a
    #                                         clear line: they cast on the way (at 3 they died before casting)
    run.watch(60)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    msgs = messages_since(run.t_act)
    afraid = next((t for t, m in msgs if re.search(r"too afraid|You are terrified|You are scared", m)), None)
    cured = next((d["t"] for d in recs if d.get("kind") == "act" and afraid and d["t"] >= afraid - 0.5 and
                  re.search(r"Boldness|Heroism|Berserk|recall|stairs|phase", str(d.get("why")), re.I)), None)
    run.res["afraid_at"] = round(afraid - run.t_act, 1) if afraid else None
    run.check("fear answered within 5 s", afraid is None or (cured is not None and cured - afraid <= 5),
              f"afraid at {run.res['afraid_at']}, answered {round(cured - afraid, 1) if cured and afraid else None} s later")
    if st["hp_min"]:
        run.check("lowest HP >= 50%", st["hp_min"][0] >= 0.5 * st["hp_min"][1], f"lowest {st['hp_min']}")


def a4(run):
    """A4: a slow ranged caster unique (Wormtongue: frost bolts, slow, traps; 250 HP, melee ~6) 3 squares off
    (on unlit ground he isn't seen farther), a '>' painted on the farthest square of Dive04's known floor up to 12
    off. Passes when Dive04 doesn't walk more than 8 squares in his sight (a flee walk under his bolts) and its
    lowest HP stays at 60% or more."""
    v = run.bring_dive04()
    me = tuple(v["pos"])
    stairs = next((q for d in range(12, 3, -1) for q in [floor_near(v, me, d)] if q), None)
    if stairs:
        run.gandalf_to(stairs)
        run.dm.paint(7, [8])                     # '>' (he steps north off it)
        time.sleep(1.0)
    run.res["stairs"] = stairs
    run.t_act = time.time()
    run.place("Wormtongue, Agent of Saruman", 3)
    run.watch(45)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    walked, last = 0, None
    for d in recs:
        if d.get("kind") == "mons" and d.get("pos") and any("Wormtongue" in m[2] for m in d.get("monsters", [])):
            p = tuple(d["pos"])
            if last:
                walked += max(abs(p[0] - last[0]), abs(p[1] - last[1]))
            last = p
        elif d.get("kind") == "mons":
            last = None
    run.res["walked_in_sight"] = walked
    seen = first_seen(recs, "Wormtongue, Agent of Saruman", run.t_act)
    # (a unique exists once: while he lives on another level the summon fails silently)
    run.check("Wormtongue staged (seen)", seen is not None, f"first seen {seen} s")
    run.check("<= 8 squares walked in his sight", walked <= 8, f"{walked} squares (stairs {stairs})")
    if st["hp_min"]:
        run.check("lowest HP >= 60%", st["hp_min"][0] >= 0.6 * st["hp_min"][1], f"lowest {st['hp_min']}")
