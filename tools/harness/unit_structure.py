"""unit_structure -- unit cases: Code structure: the refactor's tables and the golden report text.

Run by unit.py (python3 unit.py [NAME]); W, pilot() and the other shared fixtures are in fixtures.py.
"""
import os
import re

from fixtures import HERE, P, case, pilot, GOLDEN_REPORTS, render_reports
import cmdtable                    # noqa: E402


@case
def command_table_methods_exist():
    """E2: every command-table entry names a method Pilot has, taking what the entry's `call` passes (args, text,
    name, none, cmd, req), and every item_action entry has its key in Pilot.ACTIONS."""
    import inspect
    want = {"args": 1, "text": 1, "name": 1, "none": 0, "cmd": 2, "req": 2}
    bad = []
    for n, s in cmdtable.COMMANDS.items():
        f = getattr(P.Pilot, s.method, None)
        if not callable(f):
            bad.append(f"{n}: no Pilot.{s.method}")
            continue
        req = [x for x in list(inspect.signature(f).parameters.values())[1:] if x.default is inspect.Parameter.empty]
        if s.call not in want or len(req) != want[s.call]:
            bad.append(f"{n}: {s.method} takes {len(req)} arguments, call={s.call!r}")
        if s.method == "item_action" and n not in P.Pilot.ACTIONS:
            bad.append(f"{n}: not in ACTIONS")
    return not bad, f"{len(cmdtable.COMMANDS)} entries; " + ("; ".join(bad) if bad else "every method found")


@case
def command_table_fields_valid():
    """E2: each entry's roles are ANY or a non-empty subset of the known roles (with a refusal text for the others),
    `where`/`reply` take known values, sub-commands carry only known rules, and the tuples handle_requests and
    authenticate test are the table's (the viewer's polls, its read-only queries, the replies without user
    messages; the dungeon item commands)."""
    bad = []
    for n, s in cmdtable.COMMANDS.items():
        if s.roles != cmdtable.ANY and not (isinstance(s.roles, tuple) and s.roles and set(s.roles) <= set(cmdtable.ROLES)):
            bad.append(f"{n}: roles {s.roles!r}")
        if s.roles != cmdtable.ANY and not s.refusal:
            bad.append(f"{n}: no refusal text")
        if s.where not in ("any", "town", "town_target") or s.reply not in ("dict", "text") or s.group not in \
                cmdtable.GROUPS or not s.usage.split()[0] == n:
            bad.append(f"{n}: where {s.where!r} reply {s.reply!r} group {s.group!r} usage {s.usage!r}")
        for sub, rule in (s.subs or {}).items():
            if set(rule) - {"roles", "refusal", "dead"} or ("roles" in rule and not rule.get("refusal")):
                bad.append(f"{n} {sub}: {rule}")
    # (2.59.0: swapsafe, restart.sh's and hotswap.sh's poll, is a read-only query too)
    tuples = (set(P.Pilot.READ_ONLY_CMDS) == {"viewmap", "view", "navview", "goalstate", "swapsafe"} and
              set(cmdtable.POLLS) == {"viewmap", "view", "navview", "note", "goalstate", "mission", "swapsafe"} and
              set(cmdtable.NO_MESSAGES) == {"note", "say", "status"} and
              P.Pilot.DUNGEON_ITEM_CMDS == {"wear", "takeoff", "pickup", "fuel", "eat", "inscribe", "wearall"})
    return not bad and tuples, "; ".join(bad) or f"all valid; the request tuples as before: {tuples}"


@case
def command_table_help_lists_every_command():
    """E2: pilotctl's help (cmdtable.help_text, printed with no command, Pilot up or down) lists every command of the
    table and pilotctl's own (wait, rule), each at the start of a line, and pilotctl.py imports nothing of the
    Pilot's but the table (and tools/servers.py, the server table: 2.72.2)."""
    text = cmdtable.help_text()
    starts = {l.split()[0] for l in text.split("\n") if l.startswith("  ") and l.strip()}
    missing = sorted(n for n in set(cmdtable.COMMANDS) | set(cmdtable.LOCAL) if n not in starts)
    src = open(os.path.join(HERE, "..", "pilot", "pilotctl.py")).read()
    imports = sorted(set(re.findall(r"^\s*(?:import|from) (\w+)", src, re.M)))
    ok = not missing and imports == ["cmdtable", "json", "os", "servers", "socket", "subprocess", "sys", "time"]
    return ok, f"{len(text.splitlines())} lines; missing {missing or 'none'}; pilotctl imports {imports}"


@case
def command_table_architect_only_refused():
    """E2: an architect-only command (raw, stairs, goal goto, mission, answer) is refused for the Navigator (and for a
    claim that didn't authenticate, which runs as the Navigator's), with the same texts as before the table; the
    Architect's goes through. Nothing is sent to the game for the refused ones."""
    out = {}
    for role in ("navigator", "architect"):
        p = pilot()
        p.dead, p.last_report, p.report_state = False, (0, 0.0), None
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(line)
        p.log = lambda kind, **k: None
        p.take_stairs = lambda which: p.cmds.append(f"stairs {which}")
        for req in (["raw", "custom s"], ["stairs", ">"], ["mission", "bogus"], ["answer", "1", "yes"]):
            out[(role, req[0])] = (p.do_request({"cmd": req[0], "args": req[1:], "role": role}), list(p.cmds))
    nav = {k[1]: v for k, v in out.items() if k[0] == "navigator"}
    arch = {k[1]: v for k, v in out.items() if k[0] == "architect"}
    ok = not any(r["ok"] for r, _ in nav.values()) and not nav["answer"][1] and \
        nav["raw"][0]["error"].startswith("`raw` is the Pilot's now: use `goal leave`") and \
        nav["stairs"][0]["error"].startswith("`stairs` is the Pilot's now") and \
        nav["mission"][0]["error"] == "mission markers are the Architect's (refactor-candidates F4)" and \
        nav["answer"][0]["error"] == "answers come from the Architect" and \
        arch["raw"][0]["ok"] and arch["stairs"][0]["ok"] and arch["answer"][0]["ok"] and \
        arch["mission"][0]["error"].startswith("usage: mission start")
    return ok, "; ".join(f"{r} {c}: {v[0].get('error', 'ok')[:40]}" for (r, c), v in out.items())


@case
def control_commands_ghost_and_usage():
    """2.45.0: park/quit/option/dump are the Architect's (the Navigator could quit or park the Pilot); a ghost may
    park, stop, order and `plan stop` (restart.sh on a dead character waited 330 s and failed), and an unknown
    command to a ghost says `unknown command`; a bad or missing argument answers the usage, not a bare exception."""
    def fresh(dead=False):
        p = pilot()
        p.dead, p.last_report, p.report_state = dead, (0, 0.0), None
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(line)
        p.log = lambda kind, **k: None
        p.running = True
        p.mover = type("M", (), {"stop": lambda s: None, "active": False})()
        p.set_goal = lambda *a, **k: None        # (the dispatch is tested, not the methods)
        p.stop_resting = lambda *a, **k: None
        return p
    r = {}
    p = fresh()
    for c in ("park", "quit", "option", "dump"):
        r[("nav", c)] = p.do_request({"cmd": c, "args": ["a", "b"] if c == "option" else [], "role": "navigator"})
    r[("nav", "running")] = p.running
    g = fresh(dead=True)
    for c, a in (("park", []), ("stop", []), ("order", ["flee_hp=0.5"]), ("plan", ["stop"]), ("bogus", []),
                 ("goal", ["explore"])):
        r[("ghost", c)] = g.do_request({"cmd": c, "args": a, "role": "architect" if c == "park" else "navigator"})
    q = fresh()
    r[("bad", "search")] = q.do_request({"cmd": "search", "args": ["x"], "role": "navigator"})
    ok = all(not r[("nav", c)]["ok"] and "is the Architect's" in r[("nav", c)]["error"]
             for c in ("park", "quit", "option", "dump")) and r[("nav", "running")] and \
        all("dead" not in str(r[("ghost", c)].get("error", "")) for c in ("park", "stop", "order", "plan")) and \
        r[("ghost", "bogus")]["error"] == "unknown command bogus" and \
        "dead" in r[("ghost", "goal")]["error"] and \
        r[("bad", "search")]["error"].startswith("usage: search")
    return ok, "; ".join(f"{a} {b}: {str(v)[:70]}" for (a, b), v in r.items())


@case
def reflex_escape_step_lists():
    """E3 (session 11): reflexes() and escape() run one method per step, in the order of REFLEX_STEPS and
    ESCAPE_STEPS. Every name in the two lists is a method of Pilot taking (self, ctx), none twice; reflexes and
    escape still exist as the entry points; and the five names the Advisor's estimator mirrors (escape, group_tick,
    speed_start_tick, berserk_tick, fear_cure) are still Pilot's, with their signatures."""
    import inspect
    bad = []
    for lst in ("REFLEX_STEPS", "ESCAPE_STEPS"):
        names = getattr(P.Pilot, lst, None)
        if not names:
            bad.append(f"no Pilot.{lst}")
            continue
        if len(set(names)) != len(names):
            bad.append(f"{lst} names a step twice")
        for n in names:
            f = getattr(P.Pilot, n, None)
            if not callable(f) or list(inspect.signature(f).parameters) != ["self", "ctx"]:
                bad.append(f"{lst}: {n} is not a step method (self, ctx)")
    want = {"reflexes": ["self"], "escape": ["self", "why"], "group_tick": ["self", "now"],
            "speed_start_tick": ["self", "now"], "berserk_tick": ["self", "now"], "fear_cure": ["self"]}
    for n, params in want.items():
        f = getattr(P.Pilot, n, None)
        if not callable(f) or list(inspect.signature(f).parameters) != params:
            bad.append(f"Pilot.{n} missing or not ({', '.join(params)})")
    return not bad, "; ".join(bad) or (f"{len(P.Pilot.REFLEX_STEPS)} reflex steps, {len(P.Pilot.ESCAPE_STEPS)} escape "
                                       "steps, all methods; the mirrored names kept")


@case
def town_plan_step_tables():
    """E5 (session 11): the town goals' and the trip plan's ticks run one method per step, state or phase. Every name
    in Shop.STATES / TRADE_STEPS, HouseBank.TICK_STEPS / STEPS, TownKit.KIT_STEPS / BUYING_STEPS and
    TripPlan.TRIP_STEPS is a method of its class taking (self, p, ctx), none twice; the dispatches' keys are the
    states/steps the goals set (Shop: walk, enter, trade; HouseBank: go .. closed, with back and home before them);
    and the flags E5 declares start at the values their lazy reads assumed."""
    import inspect
    bad, n = [], 0
    tables = {P.Shop: ("STATES", "TRADE_STEPS"), P.HouseBank: ("TICK_STEPS", "STEPS"),
              P.TownKit: ("KIT_STEPS", "BUYING_STEPS"), P.TripPlan: ("TRIP_STEPS",)}
    for cls, lists in tables.items():
        for lst in lists:
            t = getattr(cls, lst, None)
            names = list(t.values()) if isinstance(t, dict) else list(t or ())
            if not names:
                bad.append(f"no {cls.__name__}.{lst}")
            if len(set(names)) != len(names):
                bad.append(f"{cls.__name__}.{lst} names a step twice")
            for m in names:
                f = getattr(cls, m, None)
                n += 1
                if not callable(f) or list(inspect.signature(f).parameters) != ["self", "p", "ctx"]:
                    bad.append(f"{cls.__name__}.{lst}: {m} is not a step method (self, p, ctx)")
    if set(P.Shop.STATES) != {"walk", "enter", "trade"}:
        bad.append(f"Shop.STATES: {sorted(P.Shop.STATES)}")
    if set(P.HouseBank.STEPS) != {"go", "open", "bought", "in1", "in2", "inside", "dropped", "out0", "out1", "closed"}:
        bad.append(f"HouseBank.STEPS: {sorted(P.HouseBank.STEPS)}")
    want = {P.Shop: dict(sale_pending=None, quoting=None, sale_ctx=None, selling_flavour=None, reentered=0,
                         need_fresh=0),
            P.HouseBank: dict(full_told=False, picks=0, last_step=None, seen_level=None, items_done=False),
            P.TownKit: dict(withdrawn=False, fetched=False, last_sell=None, id_bought=False, farmed=False, short=[],
                            quaffed=set(), restock_waits=0, recharged=set(), recharge_bought=False, enchanted=0,
                            enchant_bought=False, stashed=False, deposited=False, fallback_bought=False),
            P.TripPlan: dict(xp0=None, climb_t0=None, dungeon_t0=None, swarm_tele=None, clock_targets={}, xp_hist=[])}
    made = {P.Shop: P.Shop("5"), P.HouseBank: P.HouseBank("deposit"), P.TownKit: P.TownKit(),
            P.TripPlan: P.TripPlan(250, 500, P.TripPlan.parse_until("cures<3"))}
    for cls, flags in want.items():
        for k, v in flags.items():
            if made[cls].__dict__.get(k, "(missing)") != v:
                bad.append(f"{cls.__name__}.{k} = {made[cls].__dict__.get(k, '(missing)')!r}, not {v!r}")
    return not bad, "; ".join(bad) or f"{n} step methods named, all (self, p, ctx); the declared flags' defaults"


@case
def reports_match_golden():
    """E1 (session 11): the report text -- compact() (`status`), report() (`status full`), compact_changes() and the
    report mixin's line builders -- on a fixed fixture (render_reports) is the text in harness/golden/reports.txt,
    line for line, so moving code between modules can't drop or change a line unseen (step 1's first cut dropped three
    `return`s and every other case passed). When the report text changes on purpose, check the diff and regenerate
    the file from tools/:

        python3 harness/unit.py --golden
    """
    got = render_reports().splitlines()
    want = open(GOLDEN_REPORTS).read().splitlines()
    for i, (g, x) in enumerate(zip(got, want)):
        if g != x:
            return False, f"line {i + 1} differs: golden {x!r}, now {g!r}"
    if len(got) != len(want):
        return False, f"{len(got)} lines, golden {len(want)}: first extra line {(got + want)[min(len(got), len(want))]!r}"
    return True, f"{len(got)} lines as the golden file"


@case
def ghost_park_logs_out():
    """2.46.1: a ghost's `park` (allowed since 2.45.0) was accepted but never logged out -- the death reflex returned
    first and act_tick's park check never ran, so restart.sh on a dead character still waited 330 s and failed. Now
    the death step lets a pending park through and park_tick logs out at once (a ghost has nothing to be safe from)."""
    p = pilot()
    p.w.ghost, p.dead, p.goal = True, True, None
    p.w.hp = [0, 300]
    p.mover = type("M", (), {"stop": lambda s: None, "active": False})()
    p.notify = lambda *a, **k: None
    p.c = type("C", (), {"send": lambda s, line: None})()
    p.running, p.parking = True, P.gnow()
    import threading
    p.att_cond = threading.Condition()
    p.att_cond.wait = lambda t=None: None
    r = p.reflexes()
    if not r:
        p.park_tick()
    return (r is False and p.running is False), f"reflexes -> {r}; running after park_tick: {p.running}"
