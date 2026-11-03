"""unit_danger -- unit cases: Danger, emergency and escapes.

Run by unit.py (python3 unit.py [NAME]); W, pilot() and the other shared fixtures are in fixtures.py.
"""
import collections
import json
import os

from fixtures import P, RACES, BYNAME, case, W, pilot, PHASE, pilot_ast


@case
def a5_unseen_caster_news_above_80():
    """A5: "It gestures in shadow." from the dark, stairs known: news only at full HP; below 80%, it heads for the
    stairs (the old rule fled at any HP above think_hp)."""
    def run(hp):
        p = pilot(hp=hp)
        now = P.gnow()
        p.w.unseen, p.w.heard = (now, "It gestures in shadow."), (0, "")
        p.w.find = lambda chars: (25, 25)
        p.heard_warned, p.unseen_warned, p.goal = 0, 0, None
        p.orders.update(think_hp=0.5, unseen_hp="off")
        p.has_ability = lambda a: False
        p.hunt_ordered = lambda *a: False
        goals = []
        p.set_goal = goals.append
        p.unseen_tick(now)
        return [type(g).__name__ for g in goals], [w for w, _ in p.notes]
    full, hurt = run(265), run(190)
    return full == ([], ["unseen_attacker"]) and hurt[0] == ["Flee"], f"full HP: {full}; 72%: {hurt}"


@case
def emergency_speed_first_berserk_hard_fights():
    """The user (10-25): Speed at the start of an emergency, unless one turn from death -- then Teleportation (else
    Phase Door); Berserk at the start of a hard fight (a unique or a monster near our level adjacent), not for
    weak ones; haste tracked from the game's messages (the status has no indicator)."""
    def make(hp, adj, pack, msgs=()):
        p = pilot(hp=hp, pack=pack, monsters=adj)
        p.w.in_dungeon, p.w.standing_on, p.w.last_stairs_cmd = True, ".", None
        p.w.adjacent_monsters = lambda: [m for m in p.w.monsters if p.w.dist(m[:2]) == 1]
        p.w.tagged = lambda c, d: None
        p.w.damage_rate = lambda s: 5.0
        p.w.last_hit_t = P.gnow()
        p.emergency_loop = lambda now: False
        p.recall_started = lambda now: False
        p.phase_futile = lambda now: False
        p.phase_t, p.phase_hist, p.cure_t, p.recall_t = 0.0, collections.deque(), 0.0, 0.0
        p.mover = type("M", (), {"active": False, "stop": lambda self: None})()
        p.escaping_to_stairs = False
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(why)
        for t in msgs:
            p.w.messages.append((P.gnow(), t))
        return p
    pack = [("2 Potions of Speed", 75), ("11 Scrolls of Phase Door", 70), ("a Scroll of Teleportation", 70),
            ("a Potion of Berserk Strength", 75)]
    orc = [(20, 21, BYNAME["black orc"]), (21, 21, BYNAME["black orc"])]
    p = make(150, orc, pack)
    p.escape("low HP")
    first = p.cmds[-1]
    q = make(150, orc, pack, msgs=["You feel yourself moving faster!"])
    q.escape("low HP")
    hasted = q.cmds[-1]
    giant = [(20, 21, BYNAME["hill giant"])]
    r = make(20, giant, pack)
    r.escape("low HP")
    dying = r.cmds[-1]
    b = make(250, [(20, 21, BYNAME["ulfast, son of ulfang"])], pack)
    berserk = b.berserk_tick(P.gnow()) and "Berserk" in b.cmds[-1]
    weak = make(250, [(20, 21, BYNAME["jackal"])], pack).berserk_tick(P.gnow())
    ok = "Speed" in first and "Speed" not in hasted and "Teleportation" in dying and berserk and weak is False
    return ok, (f"emergency: {first!r}; already hasted: {hasted!r}; one turn from death: {dying!r}; Ulfast "
                f"adjacent, berserk: {berserk}; a Jackal: {weak}")


@case
def flee_maps_before_unexplored():
    """m31: stairs known (Door/Stair Location) but no known path; the flee went through unexplored squares, got
    stuck, and Word of Recall ended the trip with 4 Magic Mapping scrolls carried. Now: Magic Mapping first, once
    per level; with a known path, no scroll."""
    def run(mem):
        p = pilot(pack=[("4 Scrolls of Magic Mapping", 70)])
        p.live = True          # (2.48.0: on the test server the scroll is a crutch, never read -- mapping_scrolls_a_crutch_on_test)
        p.w.pos, p.w.level_t, p.w.depth, p.w.depth_ft, p.w.in_dungeon = (20, 20), 5.0, 13, 650, True
        p.w.memory = mem
        p.w.find = lambda chars: [q for q, ch in p.w.memory.items() if ch in chars]
        p.w.monsters, p.w.still_seen, p.w.avoid_zone, p.w.avoid_inside = [], {}, set(), False
        p.w.adjacent_monsters = lambda: []
        p.w.standing_on = "."
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(why)
        p.mover = type("M", (), {"go": lambda self, *a, **k: True, "active": True, "unknown": True, "path": [1] * 9,
                                 "tick": lambda self: "moving", "stop": lambda self: None})()
        P.Flee("band").tick(p)
        return p.cmds[-1] if p.cmds else None
    no_path = run({(20, 20): ".", (20, 36): ">"})
    path = run({**{(20, x): "." for x in range(20, 36)}, (20, 36): ">"})
    ok = no_path and "Magic Mapping" in no_path and path is None
    return ok, f"stairs 16 off, no known path: {no_path!r}; a known corridor: {path}"


@case
def estimator_memo_rules():
    """The Advisor's estimator memo (m17-m34 emergencies): never resend Word of Recall; a Navigator's second escape
    within 3 s refused; attack an adjacent status caster that dies in 2 rounds; Teleportation (staff too) over Phase
    against 4+ in the open; with 2+ adjacent no HP cure -- read an escape instead."""
    def make(hp, adj, pack, extra=()):
        p = pilot(hp=hp, pack=pack, monsters=list(adj) + list(extra),
                  worn=[("a Scimitar of Westernesse (2d5) (+9,+8) (+1)", 23, 130)])
        p.w.in_dungeon, p.w.standing_on, p.w.last_stairs_cmd = True, ".", None
        p.w.adjacent_monsters = lambda: [m for m in p.w.monsters if p.w.dist(m[:2]) == 1]
        p.w.tagged = lambda c, d: None
        p.w.damage_rate = lambda s: 5.0
        p.w.last_hit_t = P.gnow()
        p.emergency_loop = lambda now: False
        p.recall_started = lambda now: True             # (no last-resort recall here)
        p.phase_futile = lambda now: False
        p.phase_t, p.phase_hist, p.cure_t, p.recall_t, p.noescape_t = -99.0, collections.deque(), -99.0, -99.0, -99.0
        p.mover = type("M", (), {"active": False, "stop": lambda self: None, "in_corridor": lambda self: False})()
        p.escaping_to_stairs = False
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(line + " | " + why)
        return p
    pots = [("5 Potions of Cure Critical Wounds", 75), ("11 Scrolls of Phase Door", 70)]
    orc = BYNAME["cave orc"]
    # 1. a caster beside us that dies in 2 rounds: attacked
    a = make(200, [(20, 21, BYNAME["dark elven priest"]), (21, 21, orc)], pots)
    a.escape("low HP")
    caster = a.cmds[-1]
    # 2. 5 about in the open, a Staff of Teleportation: used instead of Phase
    b = make(200, [(20, 21, orc), (21, 21, orc)], pots + [("a Staff of Teleportation (10 charges)", 55)],
             extra=[(23, 23, orc), (22, 24, orc), (24, 20, orc)])
    b.escape("low HP")
    crowd = b.cmds[-1]
    # 2b. afraid with two adjacent (m41): the staff, not Phase Door
    b2 = make(150, [(20, 21, orc), (21, 21, orc)], pots + [("a Staff of Teleportation (10 charges)", 55)])
    b2.w.flag = lambda k: k == "afraid"
    b2.escape("low HP")
    afraid = b2.cmds[-1] if b2.cmds else ""
    # 3. two adjacent, phase rate-limited: no cure, Phase Door anyway (0.7 s rule)
    c = make(120, [(20, 21, orc), (21, 21, orc)], pots)
    c.phase_t = P.gnow() - 1.0
    c.escape("low HP")
    two = c.cmds[-1] if c.cmds else None
    # 4. a pending Word of Recall with no answer: not resent
    d = make(200, [], pots)
    d.c = type("C", (), {"sent": [], "send": lambda self, x: self.sent.append(x)})()
    d.dead, d.w.ghost = False, False
    d.notify = lambda *a, **k: None
    d.pending_use = {"line": "custom r item=3", "t": P.gnow() - 3.0, "core": "Word of Recall", "tries": 0, "why": "x"}
    d.verify_use()
    resent = list(d.c.sent)
    ok = "walk" in caster and "Dark elven priest" in caster and crowd.startswith("custom u") and \
        afraid.startswith("custom u") and "afraid" in afraid and \
        two and "Phase" in two and "quaff" not in two and resent == []
    return ok, f"caster: {caster!r}; crowd: {crowd!r}; two adjacent: {two!r}; recall resent: {resent}"


@case
def flee_at_max_depth_teleports():
    """m38: two flees at 650 ft (max_depth) with only '>' known went to 700 ft; finding a '<' there took 10 minutes.
    Now: teleport away on the level (staff or scroll), once a minute; without one, '>' as before."""
    def run(pack):
        p = pilot(pack=pack)
        p.w.depth_ft, p.w.depth, p.w.standing_on = 650, 13, "."
        p.w.find = lambda chars: [] if chars == "<" else [(25, 25)]
        p.w.adjacent_monsters = lambda: []
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(line)
        p.take_stairs = lambda ch: p.cmds.append("stairs " + ch)
        p.mover = type("M", (), {"active": False, "path": [1] * 5, "unknown": False, "go": lambda self, g, unknown=False: True,
                                 "tick": lambda self: "moving", "stop": lambda self: None})()
        p.danger_why = lambda r: None
        g = P.Flee("band: the trip leaves the level")
        r = g.tick(p)
        r2 = P.Flee("again").tick(p)
        return r, r2, p.cmds
    staff = run([("a Staff of Teleportation (9 charges)", 55)])
    none = run([PHASE])
    ok = (staff[0] == ("done", "teleported away on this level (max_depth, no '<' known)") and staff[2][0].startswith("custom u")
          and staff[1] is None and none[0] is None)
    return ok, f"with the staff: {staff}; without: {none}"


@case
def speed_at_hard_fight_start_and_kit():
    """The user (10-25), on the Advisor's replays: a carried Potion of Speed is quaffed at the start of a hard fight
    (berserk_tick's test), not only in an emergency; kits B/C keep 2, bought at the Black Market under a 600-gold cap (450 until 10-26)."""
    def make(mons, pack):
        p = pilot(hp=300, pack=pack, monsters=mons)
        p.w.in_dungeon = True
        p.w.adjacent_monsters = lambda: [m for m in p.w.monsters if p.w.dist(m[:2]) == 1]
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(why)
        return p
    strong = next(r for r in sorted(RACES.values(), key=lambda r: (r.level, r.name)) if 22 <= r.level <= 30 and
                  "UNIQUE" not in r.flags and "NEVER_MOVE" not in r.flags)
    speed = [("2 Potions of Speed", 75)]
    a = make([(20, 21, strong)], speed)
    a.speed_start_tick(P.gnow())
    b = make([(20, 21, BYNAME["cave orc"])], speed)
    b.speed_start_tick(P.gnow())
    c = make([(20, 21, strong)], speed)
    c.buff_on = lambda k: k == "fast"
    c.speed_start_tick(P.gnow())
    # the kit: Speed at 383 bought; at 3000 over the cap
    k = pilot(pack=[], gold=20000)
    k.w.depth, k.w.depth_ft, k.w.in_dungeon = 0, 0, False
    k.stores_seen = {7: {"prices": {"potion of speed": 383}}}
    buys, _ = k.town_shopping("B", ())
    k.stores_seen = {7: {"prices": {"potion of speed": 3000}}}
    buys2, short2 = k.town_shopping("B", ())
    sp = [b_ for b_ in buys if b_[1] == "Potion of Speed"]
    sp2 = [b_ for b_ in buys2 if b_[1] == "Potion of Speed"]
    ok = (len(a.cmds) == 1 and "at the start" in a.cmds[0] and b.cmds == [] and c.cmds == []
          and sp and sp[0][2] == 7 and sp[0][3] == 2 and not sp2 and any("over 600" in x[0] for x in short2))
    return ok, f"{strong.name}: {a.cmds}; a Cave orc: {b.cmds}; hasted: {c.cmds}; kit at 383: {sp}; at 3000: {sp2}"


@case
def why_explains_the_last_escape():
    """The Navigators (m40-m42): "why did the Pilot recall?" -- `why [HH:MM[:SS]]` reads the decision log around the
    last escape (or a given time): HP over the window, monsters in view and adjacent, the timeline."""
    import tempfile
    p = pilot()
    p.rundir = tempfile.mkdtemp()
    t = __import__("time").time() - 30
    recs = [{"t": t - 20, "kind": "mons", "depth": 12, "pos": [10, 10], "hp": [300, 326],
             "monsters": [[10, 11, "Umber hulk"], [14, 14, "Priest"]]},
            {"t": t - 10, "kind": "attention", "depth": 12, "pos": [10, 10], "hp": [214, 326], "what": "fight_going_badly",
             "detail": "HP 214/336 fighting Umber hulk"},
            {"t": t - 2, "kind": "move", "depth": 12, "pos": [10, 10], "hp": [190, 326]},
            {"t": t, "kind": "escape", "depth": 12, "pos": [10, 10], "hp": [191, 326], "escape": "wor_escape",
             "trigger": "flee failed with monsters close: word of recall", "adjacent": ["Umber hulk"]},
            {"t": t + 4, "kind": "attention", "depth": 12, "pos": [10, 10], "hp": [151, 326], "what": "emergency",
             "detail": "low HP: quaffed a Potion of Cure Critical Wounds"}]
    with open(os.path.join(p.rundir, "decisions.jsonl"), "w") as f:
        f.write("\n".join(json.dumps(r) for r in [{"t": t - 999, "kind": "note"}] + recs) + "\n")
    text = p.why_info([])
    ok = ("600 ft" in text and "lowest 151" in text and "adjacent at some point: Umber hulk" in text
          and "ESCAPE (wor_escape): flee failed" in text and "move" not in text and "fight_going_badly" in text)
    return ok, text.replace("\n", " | ")[:400]


@case
def escape_landing_and_trapdoor_notes():
    """Session 8: a staff's teleport looked like "no change" and a scroll was read on top. The status header says
    ESCAPE LANDING until we move, then "escaped". m50: a trap door below max_depth is news."""
    p = pilot()
    p.escape_read_t, p.escape_from = P.gnow() - 1, ((20, 20), "a Staff of Teleportation")
    a = p.escape_line()
    p.w.pos = (40, 60)
    b = p.escape_line()
    q = pilot()
    q.orders["max_depth"] = 800
    q.trap_seen_t, q.traps_here = 0.0, (None, 0)
    q.w.depth_ft, q.w.level_t = 800, P.gnow() - 10
    q.w.messages.append((P.gnow() - 5, "You fall through a trap door!"))
    q.watch_traps()
    q.w.depth_ft, q.w.level_t = 850, P.gnow()
    q.watch_traps()
    news = [d for what, d in q.notes if what == "tactic"]
    ok = "ESCAPE LANDING" in a and "escaped" in b and "moved 40 squares" in b and len(news) == 1 and "850 ft" in news[0]
    return ok, f"{a!r} then {b!r}; trap door: {news}"


@case
def flee_replans_after_a_phase():
    """m59 18:44: a flee had a known path to stairs 21 off; a Phase Door landed Dive04 among unmapped squares; the
    replan used known squares only (the go allowed unexplored ones only when no known path existed at the start),
    failed, "stuck" -> Word of Recall. A replan now falls back to unexplored squares when the go allowed it."""
    import mover as M
    w = W()
    # a corridor 20,10..20,30 to stairs at 20,30, known; the landing at 24,20 is in unknown ground four rows off
    w.memory = {(20, x): "." for x in range(10, 31)}
    w.memory[(20, 30)] = ">"
    w.pos = (20, 10)
    w.bump_walls = {}
    sent = []
    c = type("C", (), {"send": lambda self, x: sent.append(x)})()
    try:
        m = M.Mover(c, w, log=lambda *a, **k: None)
    except TypeError:
        m = M.Mover(c, w)
    ok = m.go([(20, 30)], unknown=True)
    known_first = ok and not m.unknown
    w.pos = (24, 20)                         # (the phase)
    for y in range(21, 25):
        w.memory.pop((y, 20), None)
    st = m.tick()
    return known_first and st == "moving" and m.unknown, f"first plan known {known_first}; after the jump {st}, " \
                                                         f"through unexplored {m.unknown}"


@case
def escape_stairs_flag_ends_with_its_walk():
    """refactor-candidates A1: `escaping_to_stairs` means the mover's current walk is escape()'s walk to stairs. It was
    never reset: after one escape walk, an emergency ticked any later walk (Explore) as an escape and took whatever
    stairs it reached, and the reflex no longer stopped the mover. Now arrival, a new go() or a new level ends it."""
    p = pilot(hp=100, monsters=[(20, 24, BYNAME["cave orc"])])
    w = p.w
    w.ghost, w.standing_on, w.last_stairs_cmd, w.last_hit_t = False, ".", None, P.gnow()
    w.adjacent_monsters = lambda: []
    w.tagged = lambda c, d: None
    w.damage_rate = lambda s: 5.0
    w.find = lambda chars: [(20, 30)]
    p.dead, p.busy_until, p.orders["flee_hp"] = False, 0.0, 0.5
    p.worst_3turns = lambda races: 0.0
    p.emergency_loop = lambda now: False
    p.recall_started = lambda now: True
    p.phase_futile = lambda now: False
    p.kill_caster_step = lambda adj, why: False
    p.teleport_item = lambda: None
    p.phase_t, p.phase_hist, p.cure_t, p.recall_t, p.noescape_t = -99.0, collections.deque(), -99.0, -99.0, -99.0
    p.cmd = lambda line, why, hold=0.4: None
    m = P.Mover(None, w)
    m._plan = lambda: bool(setattr(m, "path", [(0, 0)])) or True
    ticks = []
    m.tick = lambda: ticks.append(sorted(m.goals)) or "moving"
    p.mover = m
    p.escaping_to_stairs = False
    p.reflexes()                                    # 1. out of melee, stairs 10 away: the escape walk starts
    started = p.escaping_to_stairs and ticks == [[(20, 30)]]
    m.goals = None                                  # 2. it arrives (Mover.tick clears goals)
    after_arrival = p.escaping_to_stairs
    m.go([(5, 5)])                                  # 3. an Explore walk on the reused mover
    explore_flag = p.escaping_to_stairs
    p.reflexes()                                    # the emergency again: not ticked as an escape; stopped
    explore_ticked, stopped = len(ticks) > 1, not m.active
    m.go([(20, 30)])                                # 4. an escape walk, then a new level
    p.escaping_to_stairs = True
    w.level_t = 2.0
    new_level = p.escaping_to_stairs
    ok = started and not after_arrival and not explore_flag and not explore_ticked and stopped and not new_level
    return ok, f"escape walk started {started}; flag after arrival {after_arrival}, on an Explore walk {explore_flag}, " \
               f"Explore walk ticked as an escape {explore_ticked}, reflex stopped it {stopped}; after a new level " \
               f"{new_level}"


@case
def emergency_loop_counts_actions_only():
    """A4 (session 10): emergency notices that report no action (waiting/fighting on, attacking a caster first)
    don't count towards the emergency loop's three in 90 s; a Phase Door notice does."""
    import threading
    p = pilot()
    p.held_t, p.goal, p.escalation_t, p.news = 0.0, None, 0.0, []
    p.shadow_decision = lambda *a, **k: None
    p.att_cond, p.attention = threading.Condition(), []
    P.Pilot.notify(p, "emergency", "low HP: waiting to use Phase Door again, fighting on", action=False)
    P.Pilot.notify(p, "emergency", "low HP: attacking Dark elven priest first", action=False)
    n_wait = len(p.emerg_times)
    P.Pilot.notify(p, "emergency", "low HP: read Phase Door (Cave orc adjacent)", action=True)
    return (n_wait, len(p.emerg_times), len(p.attention)) == (0, 1, 3), \
        f"after 2 non-actions: {n_wait}; after a phase: {len(p.emerg_times)}; notices {len(p.attention)}"


@case
def emergency_notices_say_if_action():
    """A4 (session 10): every `emergency` notice in the Pilot's code says whether it reports an escape action (action=True or
    False), so a new non-action notice can't count towards the emergency loop by default."""
    import ast
    tree = pilot_ast()
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "notify"
             and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == "emergency"]
    bad = [n.lineno for n in calls if not any(k.arg == "action" for k in n.keywords)]
    return bool(calls) and not bad, f"{len(calls)} emergency notices; without action=: {bad}"


@case
def emergency_loop_says_already_fleeing():
    """A21 (session 10): the third emergency in 90 s while already fleeing to known stairs says so (it used to say
    "no stairs known nearby")."""
    p = pilot()
    now = P.gnow()
    p.emerg_times, p.loop_warned = [now - 5, now - 3, now - 1], 0.0
    p.w.find = lambda chars: [(20, 22)]
    p.w.dist = lambda q: 2
    p.goal = P.Flee("test")
    r = p.emergency_loop(now)
    said = [d for w_, d in p.notes if w_ == "emergency_loop"]
    return r is False and said and "already fleeing" in said[0], f"{r}, {said}"


@case
def hunger_without_a_light_lets_the_later_steps_run():
    """refactor-candidates E3 (2.45.0): Weak, no food, a Scroll of Satisfy Hunger and no light to read it by: the hunger
    step returned wear_light's False, which ended reflexes() there, so pickup, auto-destroy and rest never ran (A20's
    kind of early stop). Now a light put on ends the call; with none to put on the steps below run (here: hurt and
    alone, rest)."""
    import types
    import combat

    def run(light):
        p = pilot(hp=100, pack=[("a Scroll of Satisfy Hunger", 70)] +
                  ([("a Wooden Torch (with 2500 turns of light)", 39)] if light else []))
        w = p.w
        w.hunger, w.monster_seen_t, w.last_hit_t, w.resting = 1, -99.0, -99.0, False
        w.flag = lambda k: False
        w.adjacent_monsters = lambda: []
        p.goal, p.busy_until, p.eat_t = None, 0.0, -99.0
        p.orders.update(rest_below=0.6, pickup="all")
        sent = []
        p.cmd = lambda line, why, hold=0.4: sent.append(line)
        p.mover = type("M", (), {"active": False, "stop": lambda self: None})()
        p.auto_destroy = lambda now: False
        p.engage_tick = lambda now: False
        ctx = types.SimpleNamespace(w=w, o=p.orders, now=P.gnow(), mons_near=[])
        steps = P.Pilot.REFLEX_STEPS
        for name in steps[steps.index("_reflex_hunger"):]:
            r = getattr(p, name)(ctx)
            if r is not combat.NEXT:
                return name, r, sent
        return None, False, sent
    lit, dark = run(True), run(False)
    ok = lit[:2] == ("_reflex_hunger", True) and lit[2] and lit[2][0].startswith("custom w ") and \
        dark == ("_reflex_rest", True, ["rest"])
    return ok, f"a torch in the pack: {lit}; no light: {dark}"


@case
def escape_walk_takes_the_stairs_it_reaches():
    """refactor-candidates E3 (2.45.0): escape()'s walk to stairs (step 12) was to take them on arrival, but step 3
    returned first: on stairs with nothing in view and no hit for 2 s it did nothing, so the walk took its stairs only
    while still threatened. Now stairs reached by the escape walk are taken (then Recover); stairs underfoot with no
    escape walk (just arrived by stairs) still aren't, which stops the bouncing (m26)."""
    def run(walk):
        p = pilot(hp=100)
        w = p.w
        w.ghost, w.standing_on, w.last_stairs_cmd, w.last_hit_t = False, ">", None, P.gnow() - 3.0
        p.dead, p.busy_until, p.goal = False, 0.0, None
        p.emergency_loop = lambda now: False
        sent = []
        p.cmd = lambda line, why, hold=0.4: sent.append(line)
        m = P.Mover(None, w)
        m._plan = lambda: bool(setattr(m, "path", [w.pos])) or True
        p.mover = m
        if walk:
            m.go([w.pos])
            p.escaping_to_stairs = True
        r = p.escape("low HP")
        return r, sent, type(p.goal).__name__
    walked, arrived = run(True), run(False)
    ok = walked == (True, ["custom >"], "Recover") and arrived == (False, [], "NoneType")
    return ok, f"reached by the escape walk: {walked}; arrived by stairs: {arrived}"


@case
def escape_walk_outlives_its_emergency():
    """2.45.0: escape() runs only while the emergency holds (a monster within 7, or a hit in the last 5 s); its walk to
    stairs that outlived it was ticked by nobody: the mover stayed active, the rest step wouldn't rest, and the
    character stood still at 42% HP. Now the rest step (after the steps that handle a monster) keeps the walk going
    and takes the stairs on arrival (escape step 3). It can't loop: a walk that ends (stuck, stopped), another walk
    or a new level ends it, and the step rests as before."""
    import types

    def run(case):
        p = pilot(hp=100)
        w = p.w
        w.ghost, w.standing_on, w.last_stairs_cmd, w.last_hit_t, w.resting = False, ".", None, P.gnow() - 30, False
        p.dead, p.busy_until, p.goal = False, 0.0, None
        p.orders.update(rest_below=0.7)
        sent, ticks = [], []
        p.cmd = lambda line, why, hold=0.4: sent.append(line)
        m = P.Mover(None, w)
        m._plan = lambda: bool(setattr(m, "path", [(20, 30)])) or True
        m.tick = lambda: ticks.append(1) or "moving"
        p.mover = m
        m.go([(20, 30)])
        p.escaping_to_stairs = True
        if case == "stairs":
            w.standing_on = ">"
        elif case == "stuck":
            m.goals = None                     # (Mover.tick stopped it: blocked)
        elif case == "other walk":
            m.go([(5, 5)])                     # (a retreat, an engage...)
        elif case == "new level":
            w.level_t = 2.0
        r = p._reflex_rest(types.SimpleNamespace(w=w, o=p.orders, now=P.gnow()))
        return r is True, len(ticks), sent, type(p.goal).__name__
    out = {c: run(c) for c in ("walking", "stairs", "stuck", "other walk", "new level")}
    ok = out["walking"] == (True, 1, [], "NoneType") and out["stairs"] == (True, 0, ["custom >"], "Recover") and \
        out["stuck"] == (True, 0, ["rest"], "NoneType") and out["other walk"][:3] == (False, 0, []) and \
        out["new level"][:3] == (False, 0, [])
    return ok, f"{out}"


@case
def hungry_waits_for_a_safe_moment_weak_eats_now():
    """2.45.2 (the user): Hungry isn't an emergency -- policy_tick eats at a safe moment, the reflex doesn't (not with a
    monster in view, nor after the fight). Weak eats in the reflex even with a monster in view (it used to wait 5 s
    with none), unless one is adjacent; fainting (0) eats even then."""
    import types
    import combat
    orc = (22, 26, BYNAME["cave orc"])

    def make(hunger, monsters=(), adjacent=False):
        p = pilot(hp=300, pack=[("3 Rations of Food", 80)], monsters=list(monsters))
        w = p.w
        w.hunger, w.monster_seen_t, w.last_hit_t = hunger, (P.gnow() if monsters else -99.0), -99.0
        w.flag = lambda k: False
        w.adjacent_monsters = (lambda: [orc]) if adjacent else (lambda: [])
        p.goal, p.busy_until, p.eat_t, p.policy_t = None, 0.0, -99.0, -99.0
        p.sent = []
        p.cmd = lambda line, why, hold=0.4: p.sent.append(line)
        p.notify = lambda *a, **k: None
        return p

    def reflex(p):
        ctx = types.SimpleNamespace(w=p.w, o=p.orders, now=P.gnow(), mons_near=[])
        return p._reflex_hunger(ctx) is not combat.NEXT and any(s.startswith("eat ") for s in p.sent)
    r = {"hungry, orc in view: reflex": reflex(make(2, [orc])),
         "hungry, alone: reflex": reflex(make(2)),
         "weak, orc in view: reflex": reflex(make(1, [orc])),
         "weak, orc adjacent: reflex": reflex(make(1, [orc], adjacent=True)),
         "fainting, orc adjacent: reflex": reflex(make(0, [orc], adjacent=True))}
    q = make(2)
    r["hungry, alone: policy_tick"] = bool(q.policy_tick(P.gnow())) and any(s.startswith("eat ") for s in q.sent)
    q = make(2, [orc])
    r["hungry, orc in view: policy_tick"] = bool(q.policy_tick(P.gnow())) and any(s.startswith("eat ") for s in q.sent)
    want = {"hungry, orc in view: reflex": False, "hungry, alone: reflex": False, "weak, orc in view: reflex": True,
            "weak, orc adjacent: reflex": False, "fainting, orc adjacent: reflex": True,
            "hungry, alone: policy_tick": True, "hungry, orc in view: policy_tick": False}
    return r == want, "; ".join(f"{k}: {v}" for k, v in r.items())
