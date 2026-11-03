"""unit_orders -- unit cases: Orders, reports, rates, shadow.

Run by unit.py (python3 unit.py [NAME]); W, pilot() and the other shared fixtures are in fixtures.py.
"""
import collections
import json
import os

from fixtures import P, RACES, BYNAME, case, pilot, _quiet_level


@case
def f1_stale_order():
    """F1: a position order answering a report from a level since left is held; a hunt of a monster out of view
    with a report over 5 s old is held; a fresh one passes."""
    p = pilot()
    p.last_report = (7, P.gnow() - 17)
    p.report_state = {"level_t": 0.5, "hp": 1.0}
    a = p.stale_order("goal", ["goto", "30,40"])
    p.report_state = {"level_t": p.w.level_t, "hp": 1.0}
    b = p.stale_order("goal", ["hunt", "Brodda"])
    p.last_report = (8, P.gnow())
    c = p.stale_order("goal", ["hunt", "Brodda"])
    return bool(a) and "left" in a and bool(b) and c is None, f"{a!r} | {b!r} | {c!r}"


@case
def shadow_estimator_logs():
    """Shadow mode (the user, 10-25): an emergency decision hands its state to the Advisor's estimator in the
    background; the answer is logged as an `estimator` record with the rules' action, the choice, the compute time and
    whether it would have arrived in time (one player turn; before the Pilot's next action). The Pilot never waits."""
    import time as _t
    p = pilot(hp=140, worn=[("a Scimitar of Westernesse (2d5) (+9,+8) (+1)", 23, 130)],
              pack=[("5 Potions of Cure Critical Wounds", 75), ("11 Scrolls of Phase Door", 70),
                    ("2 Scrolls of Word of Recall", 70)],
              monsters=[(20, 21, BYNAME["uruk"]), (21, 21, BYNAME["uruk"]), (23, 23, BYNAME["black orc"])])
    p.w.hp = [140, 310]
    p.w.in_dungeon, p.w.depth, p.w.clvl = True, 12, 25
    p.w.find = lambda chars: []
    p.our_slowness = lambda: 1.0
    p.mover = type("M", (), {"in_corridor": lambda self: False})()
    logged = []
    p.log = lambda kind, **kw: logged.append((kind, kw))
    t0 = _t.time()
    started = p.shadow_decision("low HP: read Phase Door (Uruk, Uruk adjacent)")
    waited_s = round(_t.time() - t0, 3)
    for _ in range(60):
        _t.sleep(0.1)
        p.shadow_results()
        if any(k == "estimator" for k, _ in logged):
            break
    rec = next((kw for k, kw in logged if k == "estimator"), {})
    ok = started == "started" and waited_s < 0.2 and rec.get("choice") and rec.get("rules") == "phase" and \
        "in_time_turn" in rec and "before_next_act" in rec and not rec.get("error") and rec.get("policy_version")
    return ok, (f"submit took {waited_s} s; choice {rec.get('choice')!r} ({rec.get('why')}); rules {rec.get('rules')}; "
                f"compute {rec.get('compute_s')} s vs a turn of {rec.get('turn_s')} s: in time {rec.get('in_time_turn')}; "
                f"error {rec.get('error')}")


@case
def shadow_snapshot_total_plusses():
    """A3: the estimator's tohit/todam are totals (the Advisor's docs memo 10-28 §4) -- the weapon's plusses, a ring of
    Slaying's and the STR/DEX bonuses, as geareval.sim_player passes them -- not the weapon's own (+5,+7)."""
    import geareval as GE
    import shadow as SH

    def snap(worn):
        p = pilot(hp=140, worn=worn, monsters=[(20, 21, BYNAME["uruk"])])
        p.w.find = lambda chars: []
        p.our_slowness = lambda: 1.0
        p.mover = type("M", (), {"in_corridor": lambda self: False})()
        got = []
        sh = p.shadow_est = SH.Shadow()
        if not sh.sim:
            return None
        sh.submit = lambda s: got.append(s) or "started"
        p.shadow_decision("low HP: read Phase Door (Uruk adjacent)")
        return got[0]["p"] if got else None
    spear = ("a Spear (1d6) (+5,+7)", 22, 50)
    a, b = snap([spear]), snap([spear, ("a Ring of Slaying (+4,+6)", 45, 2)])
    if not a or not b:
        return False, "the estimator didn't load"
    t = GE.stat_table()
    si, di = GE.stat_index(58), GE.stat_index(28)          # (W: STR 18/40, DEX 18/10)
    td, th = 7 + t[si]["adj_str_td"], 5 + t[si]["adj_str_th"] + t[di]["adj_dex_th"]
    ok = (a["todam"], a["tohit"]) == (td, th) and (b["todam"], b["tohit"]) == (td + 6, th + 4) and \
        b["dice"] == "1d6" and b["blows"] >= 1
    return ok, f"spear: +{a['tohit']},+{a['todam']} (expected +{th},+{td}); with the ring: +{b['tohit']},+{b['todam']}"


@case
def rates_gold_found_not_shopping():
    """The Rates line counted purchases as gold (a town visit read as gold lost); gold found counts rises in the
    dungeon only, and the net change is shown beside it."""
    p = pilot(gold=1000)
    p.gain_hist = collections.deque(maxlen=80)
    p.w.hp_hist = []
    p.avoid_names, p.avoid_zones, p.standing = set(), {}, []
    t0 = P.gnow()
    steps = [(-200, True, 1000), (-190, True, 1300), (-170, False, 1300), (-150, False, 700), (-100, True, 750)]
    for dt, dun, g in steps:
        p.w.in_dungeon, p.w.ind["gold"] = dun, [g]
        p.track_gains(t0 + dt)
    p.w.in_dungeon = False
    line = next((l for l in p.belief_lines() if l.startswith("Rates:")), "")
    # XP on this level: a new level resets it
    q = pilot()
    q.gain_hist, q.w.hp_hist = collections.deque(maxlen=80), []
    q.avoid_names, q.avoid_zones, q.standing = set(), {}, []
    q.w.in_dungeon, q.w.ind["exp"] = True, [1000]
    q.drains_here = q.traps_here = (None, 0)
    q.searched, q.phase_hist, q.mons_mem, q.hits = set(), [], {}, {}
    q.weapon_table, q.fight_rows = (lambda: []), (lambda: {})
    q.track_gains(t0 - 300)
    q.w.ind["exp"] = [1300]
    q.track_gains(t0 - 120)
    q.w.level_t, q.w.ind["exp"] = 2.0, [1400]
    q.track_gains(t0 - 120)
    q.w.ind["exp"] = [1600]
    lvl = next((l for l in q.belief_lines() if l.startswith("Rates:")), "")
    ok = p.gold_found == 350 and "gold found +350 (net -250" in line and "this level: XP +200 in 2 min (100 a" in lvl
    return ok, f"found {p.gold_found}; {line} | {lvl}"


@case
def hard_fight_shadow_once_per_fight():
    """The user (10-25): the estimator also runs at the start of a hard fight (berserk_tick's test), choosing among
    fight / speed / berserk / speed+berserk / phase; once per fight (a new set of adjacent monsters, not within 60 s of
    the same set nor 20 s of the last). The rules' label: berserk when berserk_tick would quaff, else fight. Logged as
    an estimator record with trigger hard_fight. Never acts."""
    import time as _t
    def make(pack, mons):
        p = pilot(hp=300, worn=[("a Scimitar of Westernesse (2d5) (+9,+8) (+1)", 23, 130)], pack=pack, monsters=mons)
        p.w.hp = [300, 326]
        p.w.in_dungeon, p.w.depth, p.w.clvl = True, 12, 27
        p.w.find = lambda chars: []
        p.w.adjacent_monsters = lambda: [m for m in p.w.monsters if p.w.dist(m[:2]) == 1]
        p.our_slowness = lambda: 1.0
        p.mover = type("M", (), {"in_corridor": lambda self: False})()
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(line)
        p.logged = []
        p.log = lambda kind, **kw: p.logged.append((kind, kw))
        return p
    kit = [("5 Potions of Cure Critical Wounds", 75), ("11 Scrolls of Phase Door", 70), ("2 Potions of Speed", 75),
           ("a Potion of Berserk Strength", 75)]
    ogre = next(r for r in sorted(RACES.values(), key=lambda r: (r.level, r.name)) if 22 <= r.level <= 30 and
                "UNIQUE" not in r.flags and "NEVER_MOVE" not in r.flags)
    a = make(kit, [(20, 21, ogre)])
    first = a.hard_fight_shadow(P.gnow())
    again = a.hard_fight_shadow(P.gnow() + 5)
    for _ in range(80):
        _t.sleep(0.1)
        a.shadow_results()
        if any(k == "estimator" for k, _ in a.logged):
            break
    rec = next((kw for k, kw in a.logged if k == "estimator"), {})
    weak = make(kit, [(20, 21, BYNAME["cave orc"])])
    none = weak.hard_fight_shadow(P.gnow())
    ok = (first == "started" and again is None and none is None and a.cmds == [] and rec.get("trigger") == "hard_fight"
          and rec.get("rules") == "speed+berserk" and rec.get("options") == list(P.Pilot.HARD_FIGHT_OPTIONS)
          and rec.get("choice") and not rec.get("error"))
    return ok, (f"{ogre.name}: {first}, 5 s later {again}; a Cave orc: {none}; record: trigger {rec.get('trigger')}, rules "
                f"{rec.get('rules')}, choice {rec.get('choice')!r} ({rec.get('why')}), {rec.get('compute_s')} s, "
                f"error {rec.get('error')}")


@case
def xp_per_gold_rolling():
    """The user (10-25): XP_PER_GOLD from recent play -- XP earned per gold earned (found + sold), 10-minute buckets,
    the last 30 with any gain, seeded with the shadow series (0.41) and fading out as real buckets fill. The
    estimator gets it with every snapshot."""
    import tempfile
    p = pilot()
    p.rundir = tempfile.mkdtemp()
    p.gain_hist = collections.deque(maxlen=80)
    seed = p.xp_per_gold()
    t = P.gnow()
    p.w.in_dungeon = True
    for k in range(31):                     # 30 buckets of 100 XP and 100 gold found: the seed is gone
        p.w.ind["exp"], p.w.ind["gold"] = [1000 + 100 * k], [1000 + 100 * k]
        p.track_gains(t + 600 * k)
    full = p.xp_per_gold()
    saved = json.load(open(os.path.join(p.rundir, "rates.json")))["buckets"]
    ok = abs(seed - 0.409) < 0.01 and abs(full - 1.0) < 0.01 and len(saved) == 30
    return ok, f"seed only: {seed}; after 30 buckets of 100 XP / 100 gold: {full}; buckets saved {len(saved)}"


@case
def prep_report_sections():
    """The user (10-25): a planning step at a mission's start -- `prep` gathers the character, the gear review, the
    town forecast, affordable shop stock (no crutch devices on the test server), XP by depth and the XP-per-gold rate."""
    import tempfile
    p = pilot(gold=18000)
    p.rundir = tempfile.mkdtemp()
    json.dump({"buckets": [], "depth": {"600": [2131, 4081], "650": [8969, 9931]}}, open(os.path.join(p.rundir,
                                                                                                    "rates.json"), "w"))
    p.w.depth, p.w.depth_ft, p.w.in_dungeon = 0, 0, False
    p.compact = lambda snapshot=False: "Dive04 L27 HP 326/326\nSTR ...\nCures CCW 25 | Escapes Phase 21\nAlso: ..."
    p.flavour_of = lambda it: None
    p.standing = []
    p.stores_seen = {7: {"t": 0, "prices": {"potion of speed": 383, "staff of enlightenment (6 charg)": 1507}},
                     6: {"t": 0, "prices": {"staff of teleportation (7 charg avg)": 4185}}}
    text = p.prep_info()
    ok = ("== Gear review" in text and "would buy now" in text and "650 ft 54 XP/min over 166 min" in text
          and "staff of teleportation" in text and "enlightenment" not in text and "XP per gold" in text
          and "Cures CCW 25" in text)
    return ok, text.replace("\n", " | ")[:500]


@case
def actions_say_who():
    """The user (10-25): "when does the Navigator act vs the Pilot?" -- every act and goal record carries `by`: pilot
    (reflexes, policy, idle), plan (the plan's goals and plan town), nav (a goal or item command the Navigator gave),
    arch (the Architect); a goal set while handling a request is marked as that requester's."""
    p = pilot()
    recs = []
    p.log = lambda kind, **kw: recs.append((kind, kw))
    p.mover = type("M", (), {"stop": lambda self: None})()
    p.c = type("C", (), {"send": lambda self, x: None})()
    p.pending_use, p.busy_until = None, 0.0
    p.log_escape = p.expect_effect = lambda *a: None
    p.watch_flavours = lambda: None
    p.goal = None
    p.acting = "nav"
    g = P.Goal()
    p.set_goal(g)                                   # a goal the Navigator gave
    nav_goal = P.Pilot.goal_origin(p, g)
    p.acting = "pilot"
    reflex = P.Goal()
    p.set_goal(reflex)                              # a reflex's goal (flee, recover...)
    kit = P.TownKit()
    kit.role = "navigator"
    planned = P.Goal()
    planned.by_plan = True
    p.acting = "plan"
    p.cmd("custom r item=3", "trip: read Word of Recall", hold=0.1)
    origins = (nav_goal, P.Pilot.goal_origin(p, reflex), P.Pilot.goal_origin(p, kit), P.Pilot.goal_origin(p, planned))
    acts = [kw.get("by") for k, kw in recs if k == "act"]
    goals = [kw.get("by") for k, kw in recs if k == "goal"]
    ok = origins == ("nav", "pilot", "plan", "plan") and acts == ["plan"] and goals == ["nav", "pilot"]
    return ok, f"origins (nav goal, reflex, plan town, plan goal): {origins}; act by {acts}; goals by {goals}"


@case
def item_commands_wait_for_the_pack():
    """m57: Speed (the last of its stack) then Berserk 1 s later by a stale letter -- a Cure Light Wounds was drunk and
    the Berserk "showed no effect" twice. A second item command waits until the pack has come back (3 s at most);
    the first marks the pack dirty so it comes back at once."""
    p = pilot(pack=[("a Potion of Speed", 75), ("a Potion of Berserk Strength", 75)])
    sent = []
    p.c = type("C", (), {"send": lambda self, x: sent.append(x)})()
    p.pending_use, p.log, p.held_t = None, (lambda *a, **k: None), 0.0
    p.expect_effect = p.log_escape = p.watch_flavours = lambda *a, **k: None
    p.w.inven_t = P.gnow() - 5
    p.cmd("custom q item=0", "speed")
    dirty = p.w.inven_dirty
    p.cmd("custom q item=1", "berserk")
    held = list(sent)
    p.w.inven_t = P.gnow() + 0.01            # (the pack came back)
    p.cmd("custom q item=0", "berserk again")
    ok = held == ["custom q item=0"] and dirty and sent == ["custom q item=0", "custom q item=0"]
    return ok, f"sent {sent}; pack marked dirty {dirty}"


@case
def ask_quiet_waits_for_the_answer():
    """The user (10-28): the Navigator's quiet wait for a conversation with the Architect. `ask quiet TEXT` asks and
    starts a quiet wait that ends on the answer; an answer starting "more" keeps it (a back-and-forth)."""
    import tempfile
    p = _quiet_level()
    p.rundir, p.plan, p.goal, p.req_role, p.resume_after = tempfile.mkdtemp(), None, None, "navigator", None
    p.set_goal = lambda g: setattr(p, "goal", g)
    p.mover = type("M", (), {"active": False, "go": lambda self, t: True, "tick": lambda self: "arrived",
                             "stop": lambda self: None})()
    p.cmd = lambda line, why, hold=0.4: None
    p.dangers = lambda: []
    import threading
    p.att_cond, p.attention, p.news = threading.Condition(), [], []
    out = p.ask_architect("quiet should I take the Lance or the Pike?")
    g = p.goal
    p.arch_answers = [(P.gnow(), 1, "more: which slot is free?")]
    r1 = g.tick(p)
    p.arch_answers.append((P.gnow(), 1, "the Pike: lighter"))
    r2 = g.tick(p)
    ok = out["ok"] and isinstance(g, P.QuietWait) and g.wait_answer == 1 and r1 is None and r2 and r2[0] == "done"
    return ok, f"{out.get('text', out)[:70]}; after 'more': {r1}; after the answer: {r2}"


@case
def mission_label_survives_restart():
    """m44/m45: a hot-swap lost the mission label (`mission end` needed it by name) and the mission's totals. They
    live in mission.json now, and a new Pilot picks them up."""
    import tempfile
    p = pilot()
    p.rundir = tempfile.mkdtemp()
    p.w.ind["exp"] = [5000]
    p.mission_label, p.mission_base, p.gold_found = "m99", (P.gnow() - 600, 4000, 100, 50), 350
    p.save_mission()
    q = pilot()
    q.rundir = p.rundir
    q.load_mission()
    q.gold_found = 20                     # (found since the restart)
    found = q.gold_found - q.mission_base[3]
    age = P.gnow() - q.mission_base[0]
    ok = q.mission_label == "m99" and q.mission_base[1:3] == (4000, 100) and found == 320 and 595 < age < 610
    return ok, f"label {q.mission_label}, base {q.mission_base[1:3]}, found {found}, {age:.0f} s in"


@case
def shadow_agrees_by_the_action_taken():
    """m47: at the Wargs the estimator kept "rules" (its copy fought) while the Pilot read Word of Recall -- the table's
    worst row, -102 XP -- and "agree" was logged. Now "rules" agrees only if the Pilot's own row is safe and within
    noise of the best; a band's leave decision is shadowed too (once per band), with the resists passed."""
    table = [{"option": "rules", "safe": True, "dxp": 0.0, "se": 0.0}, {"option": "fight", "safe": True, "dxp": 0.0},
             {"option": "phase", "safe": True, "dxp": -6.0, "se": 3.5},
             {"option": "ccw", "safe": True, "dxp": -12.5, "se": 3.5},
             {"option": "recall+phase", "safe": True, "dxp": -101.8, "se": 3.7}]
    a1, row = P.shadow_agree("rules", "recall+phase", table)
    a2, _ = P.shadow_agree("rules", "phase", table)
    a3, _ = P.shadow_agree("rules", "cure", table)         # (no row for it: can't tell, agree)
    a5, _ = P.shadow_agree("rules", "ccw", table)          # (-12.5: beyond 10 XP and 2 SE)
    a4, _ = P.shadow_agree("fight", "recall+phase", table)
    warg = BYNAME["warg"]
    p = pilot(monsters=[(20, 22 + k, warg) for k in range(9)])
    p.w.find = lambda chars: [(30, 30)]
    calls = []
    p.rate_state = lambda: {"depth": {"300": [5300, 6000]}}
    p.shadow_decision = lambda detail, options=None, trigger="emergency", rules=None, extra_p=None: calls.append((trigger, rules,
                                                                                                    options)) or "started"
    # (through notify, with a trip plan running: m48's plan turned every band notice into news first and none was
    # shadowed)
    p.plan = type("Pl", (), {"paused": False, "on_event": lambda *a: None})()
    p.goal, p.notes, p.events_seen, p.news = None, [], [], collections.deque(maxlen=50)
    try:
        P.Pilot.notify(p, "band", "a band within 10 squares: Warg x9")
    except Exception:
        pass                  # (the rest of notify needs a live Pilot: the shadow request comes first)
    via_notify = [c for c in calls if c[0] == "band"]
    calls.clear()
    p.band_shadow_seen, p.band_shadow_t = {}, -99.0
    r1 = p.band_shadow("a band within 10 squares: Warg x9")
    r2 = p.band_shadow("a band within 10 squares: Warg x9")
    ok = a1 is False and row["dxp"] == -101.8 and a2 is True and a3 is True and a4 is False and a5 is False and \
        r1 == "started" and \
        r2 is None and calls == [("band", "stairs", P.Pilot.BAND_OPTIONS)] and len(via_notify) == 1
    return ok, f"recall row: {a1}; phase: {a2}; no row: {a3}; other choice: {a4}; band: {calls}, again {r2}; " \
               f"via notify {via_notify}"


@case
def react_hunt_resumes_the_goal():
    """M5 (10-28): `react thieves kill` hunted a Scruffy looking hobbit during a `goal dive`, and the dive was lost when
    the hunt ended. Now the interrupted goal (not a plan's: the plan resumes itself) comes back after the hunt."""
    import tempfile
    q = pilot(monsters=[(20, 24, BYNAME["novice rogue"])])
    q.rundir, q.plan, q.resume_after = tempfile.mkdtemp(), None, None
    dive = P.Dive(500)
    q.goal = dive
    q.nav_rules = [{"kind": "thieves", "arg": "kill", "by": "navigator"}]
    q.danger_why = lambda r: None
    q.do_request = lambda req: (setattr(q, "goal", P.Hunt("Novice rogue")), {"ok": True})[1]
    hunted = q.rule_tick(100.0)
    ok = hunted and isinstance(q.goal, P.Hunt) and q.resume_after is dive
    return ok, f"hunting {type(q.goal).__name__}; resumes {q.resume_after and q.resume_after.describe()}"


@case
def ask_limits_lifted_by_the_flag_file():
    """The user (10-26, "The Architect's Vacation"): the file ask_unlimited in the run directory lifts `ask`'s limits
    (one every 5 minutes, 4 an hour); without it they hold."""
    import tempfile
    p = pilot()
    p.rundir = tempfile.mkdtemp()
    p.goal = None
    p.w.depth_ft = 750
    r1, r2 = p.ask_architect("one?"), p.ask_architect("two?")
    open(os.path.join(p.rundir, "ask_unlimited"), "w").close()
    r3 = p.ask_architect("three?")
    ok = r1["ok"] and not r2["ok"] and r3["ok"]
    return ok, f"limited: {r1['ok']}, {r2['ok']}; with the flag: {r3['ok']}"


@case
def order_all_or_nothing():
    """A22 (session 10): `order a=1 b=bad` changes nothing and says why; a good order is applied and saved."""
    import tempfile
    p = pilot()
    p.orders.update(flee_hp=0.5, loot_radius=10)
    p.orders_file = os.path.join(tempfile.mkdtemp(), "orders.json")
    p.stale_order = lambda c, a: None
    p.dead = False
    bad = p.do_request({"cmd": "order", "args": ["flee_hp=0.4", "loot_radius=far"]})
    kept = p.orders["flee_hp"]
    good = p.do_request({"cmd": "order", "args": ["flee_hp=0.4"]})
    saved = json.load(open(p.orders_file))["flee_hp"] if os.path.exists(p.orders_file) else None
    return (not bad["ok"] and "nothing changed" in bad["error"] and kept == 0.5 and good.get("ok") and saved == 0.4), \
        f"bad: {bad}; flee_hp then {kept}; good saved {saved}"


@case
def architect_role_needs_the_token():
    """F3/F4 (session 10): a request claiming the architect role without the token runs as the Navigator's (logged and
    reported; the viewer's read-only queries quietly); with the token it is the Architect's. `mission` is the
    Architect's only."""
    p = pilot()
    p.arch_token = "secret"
    logs = []
    p.log = lambda kind, **k: logs.append(kind)
    bare = p.authenticate({"cmd": "goal", "args": ["recall"], "role": "architect"})
    view = p.authenticate({"cmd": "viewmap", "args": [], "role": "architect"})
    good = p.authenticate({"cmd": "goal", "args": ["recall"], "role": "architect", "token": "secret"})
    p.dead, p.last_report = False, (0, 0.0)
    p.req_role = "navigator"
    refused = p.do_request({"cmd": "mission", "args": ["start", "m99"], "role": "navigator"})
    ok = bare["role"] == "navigator" and view["role"] == "navigator" and good["role"] == "architect" and \
        logs.count("role_refused") == 1 and [w for w, _ in p.notes] == ["role_refused"] and not refused["ok"]
    return ok, f"bare {bare['role']}, viewer {view['role']}, token {good['role']}; logs {logs}; mission: {refused}"
