"""fixtures -- what the unit cases share (unit.py runs them; the cases are in unit_<family>.py).

The Pilot's modules on the path (`P` is pilot.py), the monster races merged with the rulebook (RACES, BYNAME), the
@case registry (CASES, in definition order; unit.py runs it in its ORDER), `W` (a constructed world: Dive04 as of
2026-10-23), `pilot(w)` (a Pilot on it, Pilot.for_test, a fresh 1x game clock), PHASE, `pilot_ast()` (the Pilot's
code as one parsed module), the helpers more than one family uses (_Stub, _quiet_level), and the golden report
text (GOLDEN_REPORTS, render_reports: the case reports_match_golden and `unit.py --golden`). A helper only one family
uses lives in that family's file.
"""
import collections
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pilot"))
import pilot as P                  # noqa: E402
import glyphs                      # noqa: E402

RACES = glyphs.load_rulebook(glyphs.load_races())


BYNAME = {r.name.lower(): r for r in RACES.values()}


CASES = []


def case(f):
    CASES.append(f)
    return f


class G:
    races = RACES


class W:
    """A constructed world: Dive04 as of 2026-10-23 unless a case changes it."""
    depth = 6
    depth_ft = 300
    in_dungeon = True
    store = None
    store_t = 0
    inven_dirty = False
    level_t = 1.0
    pos = (20, 20)
    recall_pending = False

    def __init__(self, hp=265, pack=(), worn=None, monsters=(), gold=172):
        self.hp = [hp, 265]
        self.g = G()
        self.monsters = list(monsters)
        self.messages = collections.deque(maxlen=300)
        self.ind = {"armor": [56], "stat0": [58], "stat3": [28], "stat5": [3], "gold": [gold]}
        self.flags = {"free_act": 0, "res_blind": 0, "res_conf": 0, "res_nexus": 0, "hold_life": 0, "feather": 0}
        worn = worn if worn is not None else [("a Spear (1d6) (+5,+7)", 22, 50)]
        self.inven = [{"item": 24 + i, "name": n, "tval": t, "weight": wt, "number": 1, "equip": True}
                      for i, (n, t, wt) in enumerate(worn)]
        self.inven += [{"item": i, "name": n, "tval": t, "weight": 10, "equip": False,
                        "number": int(n.split()[0]) if n[0].isdigit() else 1} for i, (n, t) in enumerate(pack)]
        self.clvl = 22
        self.memory, self.still_seen, self.avoid_zone, self.avoid_inside = {}, {}, set(), False

    @property
    def hp_frac(self):
        return self.hp[0] / self.hp[1]

    @property
    def hunger(self):
        return self.ind.get("hunger", [3])[0]

    @hunger.setter
    def hunger(self, v):
        self.ind["hunger"] = [v]

    def items(self, *, tval=None, name=None, equip=False):
        return [i for i in self.inven if i["equip"] == equip and (tval is None or i["tval"] == tval)]

    def has(self, f):
        return bool(self.flags.get(f))

    def dist(self, q, r=None):
        a = r or self.pos
        return max(abs(q[0] - a[0]), abs(q[1] - a[1]))

    def flag(self, k):
        return False


def pilot(w=None, **kw):
    # (a case that leaves the game clock fast, slow or frozen made the 0.7-s Phase rule flaky -- game time 1 s ago read
    # as 0.46 wall s: every case starts with a fresh 1x clock, its segment history cleared)
    import world as _W
    with _W._LOCK:
        now = time.time()
        _W._CLOCK.update(wall=now, game=now, factor=1.0, model=1.0, measured=0.0, fast_ok=False, rate=None)
        _W._HIST.clear()
        _W._HIST.append((now, now, 1.0))
        _W._FUEL.clear()
    p = P.Pilot.for_test(w or W(**kw), orders={"max_depth": 650, "rest_to": 1.0}, deepest_ft=650,
                         seen_drained={"CON": (18, 18), "STR": (58, 68), "WIS": (9, 10), "CHR": (3, 5)},
                         unique_names={r.name.lower() for r in RACES.values() if "UNIQUE" in r.flags},
                         ability_seen_t=0)
    p.notes = []
    p.notify = lambda what, d=None, news=False, action=True, fields=None: p.notes.append((what, d))
    return p


PHASE = ("11 Scrolls of Phase Door", 70)


def pilot_ast():
    """The Pilot's code as one parsed module, for the cases that check every call of a kind (E1: pilot.py and the
    modules split out of it; line numbers are per file)."""
    import ast
    body = []
    for f in ("pilot.py", "goals.py", "town_goals.py", "plan.py", "report.py", "daemon.py", "common.py", "gear.py",
              "items.py", "town.py", "combat.py", "commands.py"):
        body += ast.parse(open(os.path.join(HERE, "..", "pilot", f)).read()).body
    return ast.Module(body=body, type_ignores=[])


class _Stub:
    """A goal stand-in that never ends."""
    name = "stub"

    def tick(self, p):
        return None


def _quiet_level():
    """A walked 11x21 room (rows 10-20, cols 10-30) with a corridor east from 15,31 into the unknown."""
    p = pilot()
    w = p.w
    w.memory = {(y, x): "." for y in range(10, 21) for x in range(10, 31)}
    for y in range(9, 22):
        w.memory[(y, 9)] = w.memory[(y, 31)] = "#"
    for x in range(9, 32):
        w.memory[(9, x)] = w.memory[(21, x)] = "#"
    for x in range(31, 40):
        w.memory[(15, x)] = "."
    w.walked = {q for q, ch in w.memory.items() if ch == "."}
    w.pos, w.clvl, w.last_hit_t, w.resting = (15, 36), 28, 0.0, False
    p.unreachable, p.busy_until = set(), 0
    return p


GOLDEN_REPORTS = os.path.join(HERE, "golden", "reports.txt")


def render_reports():
    """compact(), report() and compact_changes() of three constructed Pilots (in the dungeon with monsters; in town by
    day; resting, afraid, a recall pending), and the report mixin's own line builders, as one text. The clock is fixed
    (game and wall time T0, TZ=UTC), the version is "0.0.0" and random is seeded, so the text depends only on the
    code; the patched module globals are put back after."""
    import world as Wd
    T0 = 1_800_000_000.0
    mods = [m for m in list(sys.modules.values()) if os.path.dirname(os.path.abspath(getattr(m, "__file__", None)
                                                                                      or "/")) == P.HERE]
    saved = [(m, k, getattr(m, k)) for m in mods if m is not Wd for k in ("gnow", "VERSION") if hasattr(m, k)]
    tz, strftime, rstate = os.environ.get("TZ"), time.strftime, random.getstate()
    try:
        for m, k, v in saved:
            if k == "VERSION":
                setattr(m, k, "0.0.0")
            elif v is Wd.gnow:                         # (the modules' own `from world import gnow`)
                setattr(m, k, lambda: T0)
        os.environ["TZ"] = "UTC"
        time.tzset()
        time.strftime = lambda f, t=None: strftime(f, t if t is not None else time.localtime(T0))
        random.seed(0)
        return _render_reports(T0)
    finally:
        for m, k, v in saved:
            setattr(m, k, v)
        if tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = tz
        time.tzset()
        time.strftime = strftime
        random.setstate(rstate)


def _render_reports(T0):
    B = BYNAME
    mons = [(21, 21, B["cave spider"]), (22, 23, B["cave spider"]), (25, 20, B["grip, farmer maggot's dog"]),
            (30, 30, B["hill orc"])]
    out = []
    for variant in range(3):
        p = pilot(pack=[PHASE, ("3 Potions of Cure Light Wounds", 75), ("a Dagger (1d4) (+2,+3) {good}", 23),
                        ("a Broad Sword of Slay Orc (2d5)", 23), ("a Main Gauche of Burning (1d5) (+4,+5)", 23)],
                  monsters=mons if variant != 1 else [])
        w = p.w
        w.is_day = lambda: True
        w.resting = variant == 2
        w.standing_on, w.floor, w.arrived_by = "floor", ("a Flask of oil" if variant else None), "stairs"
        w.memory = {(18, 18): "<", (24, 25): ">", (22, 22): "$", (23, 22): "!", (40, 40): "+"}
        w.memory[P.structures.door_spots(30, 40)[0][0]] = "+"
        w.rows = ["#" * 60 for _ in range(50)]
        w.itemlist = ["Items:", "a) a Flask of oil", "b) 3 Potions of Cure Light Wounds"]
        w.find = lambda g: [q for q, v in w.memory.items() if v in g]
        w.recent = lambda n: ["You hit it.", "It bites you."]
        w.flag = lambda k: k in (("afraid", "cut") if variant == 2 else ())
        w.ind.update({"hist_name_": "Dive04", "race_": "Human", "class_": "Warrior", "level": [22, 23],
                      "speed": [3], "skills2": [3], "stat1": [10], "stat2": [12], "stat4": [18 + 50]})
        w.recall_pending, w.recall_pending_t = variant == 2, T0 - 5
        w.level_t = T0 - 300
        w.in_dungeon = variant != 1
        w.depth = 6 if variant != 1 else 0
        p.goal = None
        p.unanswered = [(T0 - 20, "hello")] if variant == 0 else []
        p.arch_answers = []
        p.news = [{"t": T0 - k * 30, "what": "tactic", "detail": f"thing {k}"} for k in range(15)]
        p.since = {"t": T0 - 100, "min_hp": (100, 265, T0 - 50), "mons": {"Cave spider": 3,
                   "Grip, Farmer Maggot's Dog": 1}, "uniques": {"Grip, Farmer Maggot's Dog"}} if variant != 1 else None
        p.exp_t = T0 - 70
        p.goal_t = T0 - 10
        p.audit_runs, p.audit_counts = 4, ({"hp": 2} if variant else {})
        p.orders = dict(P.DEFAULT_ORDERS, max_depth=650, think_hp=0.55)
        p.banked = lambda: 0
        p.is_asleep = lambda y, x: y == 21
        p.danger_why = lambda r: "breathes" if r.name == "Hill orc" else None
        p.is_junk_name = lambda n: False
        p.resolve_target = lambda k: [(22, 22), (23, 22)]
        p.structures_here = lambda: [(30, 40, {"kind": "inner room", "sure": True}),
                                     (10, 10, {"kind": "vault", "sure": False})]
        p.searched = {(w.level_t, r) for _, r in P.structures.door_spots(10, 10)} if variant == 2 else set()
        p.weapon_table = lambda: [("a Spear (1d6) (+5,+7)", 3, 20.0, True),
                                  ("a Dagger (1d4) (+2,+3) {good}", 4, 9.0, False),
                                  ("a Broad Sword of Slay Orc (2d5)", 2, 14.0, False),
                                  ("a Main Gauche of Burning (1d5) (+4,+5)", 3, 18.0, False),
                                  ("a Tulwar (2d4) {magical}", 2, 11.0, False)]
        p.show = lambda i: i["name"]
        p.short = lambda n: n[:60]
        p.mover = None
        # the line builders themselves (below, compact() and report() get stubs for them)
        for name, call in (("escape_line", lambda: p.escape_line()), ("supply_lines", lambda: p.supply_lines()),
                           ("belief_lines", lambda: p.belief_lines()), ("gear_line", lambda: p.gear_line()),
                           ("since_lines", lambda: p.since_lines(False)),
                           ("structures_line", lambda: p.structures_line(full=True)),
                           ("unanswered_line", lambda: p.unanswered_line()), ("conditions", lambda: p.conditions()),
                           ("monster_groups", lambda: p.monster_groups())):
            out.append(f"--- variant {variant} {name}: {call()!r}")
        p.escape_line = lambda: " · esc"
        p.supply_lines = lambda: ["Cures X"]
        p.belief_lines = lambda: ["Belief Y"]
        p.compact_changes = lambda snapshot=False: ["CHANGES"]
        p.gear_line = lambda: "Gear: fine"
        p.movement_line = lambda: "Moves: here"
        for ns in (None, T0 - 200):
            p.since = dict(p.since) if p.since else None
            out.append(f"--- variant {variant} news_since {ns} compact")
            out.append(p.compact(news_since=ns))
            out.append(repr(getattr(p, "since", None)))
            p.since = {"t": T0 - 100, "min_hp": (100, 265, T0 - 50), "mons": {"Cave spider": 3}, "uniques": set()} \
                if variant != 1 else None
            out.append("--- report")
            out.append(p.report(news_since=ns))
            out.append(repr(getattr(p, "since", None)))
        del p.compact_changes                          # (compact_changes for real: the weapons line)
        p.compact_prev = None
        out.append(repr(P.Pilot.compact_changes(p, snapshot=True)))
    return "\n".join(out) + "\n"
