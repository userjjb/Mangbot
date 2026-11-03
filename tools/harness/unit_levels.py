"""unit_levels -- unit cases: Bands and levels (stairs, quiet levels, exploring, structures).

Run by unit.py (python3 unit.py [NAME]); W, pilot() and the other shared fixtures are in fixtures.py.
"""
import collections

from fixtures import P, BYNAME, case, pilot, _Stub, _quiet_level


@case
def band_leave_finds_stairs():
    """The user (after m26, every trip ending in an escape recall): a band, no stairs known, HP full, nothing
    adjacent -> no Word of Recall at once: BandLeave reads Magic Mapping (no Door/Stair device), then flees to
    the stairs it shows. A second failure on the level, or HP low, still recalls."""
    def make(hp=265):
        p = pilot(hp=hp, pack=[("2 Scrolls of Word of Recall", 70), ("3 Scrolls of Magic Mapping", 70)])
        p.w.adjacent_monsters = lambda: []
        p.w.find = lambda chars: []
        p.w.in_dungeon, p.w.level_t = True, 5.0
        p.danger_why = lambda r: None
        p.recall_started = lambda now: False
        p.use_stair_location = lambda why: False
        p.busy_until, p.goal = 0.0, None
        p.set_goal = lambda g: setattr(p, "goal", g)
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append((line, why))
        p.w.listed_only = lambda: []
        p.flee_fail_t = 0
        p.phase_t, p.phase_hist = 0, collections.deque()
        p.w.tagged = lambda c, d: None
        return p
    p = make()
    p.flee_failed("flee (band: the trip leaves the level)")
    first = type(p.goal).__name__
    p.goal.tick(p)
    mm = [w for _, w in p.cmds]
    p.w.find = lambda chars: [(25, 25)]
    p.goal.t0 -= 5
    p.mover = type("M", (), {"go": lambda self, *a, **k: True, "active": True, "unknown": False, "path": [(1, 1)] * 5,
                             "tick": lambda self: "moving", "stop": lambda self: None})()
    p.w.standing_on = None
    r = p.goal.tick(p)
    second = p.goal.flee is not None
    q = make(hp=150)
    q.w.monsters = [(22, 20, BYNAME["cave orc"])]
    q.flee_failed("flee (band: the trip leaves the level)")
    recalled = any("word of recall" in w for _, w in q.cmds)
    ok = first == "BandLeave" and any("Magic Mapping" in w for w in mm) and second and recalled
    return ok, f"goal {first}; reads {mm}; fled to stairs {second}; at 57% HP recalled {recalled}"


@case
def stairs_beside_mold():
    """m25: a Brown mold (confuses: never fought) beside the only '>' at 300 ft; the step-away walked 6 squares
    back and the dive pressed '>' there, 2 minutes. Stairs a step away (or under us) beside a stationary monster
    harmless for a turn -> take them; a disenchanter, a drainer, a floating eye, or stairs far off -> not."""
    def check(name, goal=(15, 32), pos=(15, 32), dive=False):
        p = pilot()
        p.w.pos, p.w.level_t = pos, 5.0
        p.w.memory = {(15, 32): ">"}
        p.w.standing_on = ">" if pos == (15, 32) else "."
        p.mover = type("M", (), {"goals": None if dive else {goal}, "active": not dive})()
        p.still_goals = (None, set())
        p.goal = None
        if dive:                       # (on the stairs the mover has already stopped: the live M1 run)
            p.goal = P.Dive.__new__(P.Dive)
            p.goal.want = ">"
        return p.stairs_beside_still([(14, 32, BYNAME[name])])
    got = {
        "brown mold on '>'": check("brown mold"),
        "brown mold on '>', mover stopped, diving": check("brown mold", dive=True),
        "brown mold, '>' a step off": check("brown mold", pos=(15, 31)),
        "disenchanter mold": check("disenchanter mold"),
        "purple mushroom patch": check("purple mushroom patch"),
        "floating eye": check("floating eye"),
        "brown mold, goal not stairs": check("brown mold", goal=(15, 26), pos=(15, 25)),
    }
    want = {"brown mold on '>'": True, "brown mold on '>', mover stopped, diving": True,
            "brown mold, '>' a step off": True, "disenchanter mold": False,
            "purple mushroom patch": False, "floating eye": False, "brown mold, goal not stairs": False}
    return got == want, ", ".join(f"{k}: {'take' if v else 'step away'}" for k, v in got.items())


@case
def refused_stairs_dont_end_explore():
    """m30 06:17-06:23: at 600 ft the dive refused the '>' back to the 650 ft level it had just fled, started an
    'explore until stairs', which ended at once on that same '>' -- 6 minutes of nothing, logged as nothing.
    The refused stairs no longer count as seen; another '>' does."""
    import mover as M
    class Wd:
        pos = (10, 10)
        in_dungeon, depth = True, 12
        monsters, still_seen, avoid_zone, avoid_inside = [], {}, set(), False
        def __init__(self, mem):
            self.memory = mem
        def find(self, chars):
            return [q for q, ch in self.memory.items() if ch in chars]
    floor = {(10, x): "." for x in range(5, 20)}
    d = P.Dive.__new__(P.Dive)
    d.bad_stairs, d.level_seen = {(7.0, (10, 12))}, 7.0
    e = P.Explore(until="stairs", skip=d.refused)
    only = e.stairs_seen(Wd({**floor, (10, 12): ">"}))
    other = e.stairs_seen(Wd({**floor, (10, 12): ">", (10, 18): ">"}))
    plain = P.Explore(until="stairs").stairs_seen(Wd({**floor, (10, 12): ">"}))
    ok = only is None and other == "stairs down seen" and plain == "stairs down seen"
    return ok, f"only the refused '>': {only}; another '>' too: {other}; no skip (as before): {plain}"


@case
def band_condition_only_while_live():
    """m30: the `band` condition fired 3 minutes after a beaten Novice warrior band, on a new level, when the plan
    resumed after the Navigator's goal. It holds while the band is live (warned in the last 20 s on this level, or
    3+ monsters still within 10); a band gone or beaten clears it."""
    p = pilot()
    p.w.level_t = 5.0
    tp = P.TripPlan(500, 650, P.TripPlan.parse_until("band or minutes>30"))
    tp.events["band"] = 1
    p.band_warned, p.band_warned_t = (5.0, 7), P.gnow()
    fresh = tp.holds(p)
    p.band_warned_t = P.gnow() - 60
    p.w.monsters = [(20, 22 + i, BYNAME["novice warrior"]) for i in range(4)]
    still = tp.holds(p)
    p.w.monsters = []
    beaten = tp.holds(p)
    tp.events["band"] = 1
    p.w.level_t = 6.0                     # left the level meanwhile
    moved = tp.holds(p)
    ok = fresh == "band" and still == "band" and beaten is None and moved is None and tp.events["band"] == 0
    return ok, f"just warned: {fresh}; 60 s on, 4 in view: {still}; beaten: {beaten}; on a new level: {moved}"


@case
def run_loop_walks():
    """m31: explore's free runs looped 157 times through a cave corridor (16,112 -> 16,111 -> 16,109 -> north,
    back round to 16,112). Two free runs from one square within a minute: walk from it instead."""
    import mover as M
    class C:
        def __init__(self):
            self.sent = []

        def send(self, x):
            self.sent.append(x)
    w = type("Wd", (), {"pos": (16, 109), "level_t": 3.0})()
    m = M.Mover.__new__(M.Mover)
    m.w, m.c, m.log = w, C(), lambda **k: None
    m.goals, m.path, m.running, m.free, m.run_hist = None, [], None, None, []
    m.stop = lambda: None
    first = m.run_loop()
    m.free_run(8)
    once = m.run_loop()
    m.free_run(8)
    twice = m.run_loop()
    w.pos = (16, 112)
    other = m.run_loop()
    w.level_t = 4.0
    w.pos = (16, 109)
    new_level = m.run_loop()
    ok = not first and not once and twice and not other and not new_level
    return ok, f"no runs: {first}; one: {once}; two: {twice}; another square: {other}; a new level: {new_level}"


@case
def bands_by_expected_cost_weak_drainers_news():
    """The matrix (m30, m33, m34): the plan left levels for weak bands and weak drainers. A band is serious by the
    expected cost of fighting it one by one (> 50% HP), not the sum of maximum hits; in a corridor only 2 reach us.
    A weak drainer (10+... 5+ levels below, no faster, not unique) is news, not a reason to leave."""
    def make(corridor=False):
        p = pilot(hp=310, worn=[("a Scimitar of Westernesse (2d5) (+9,+8) (+1)", 23, 130)])
        p.w.hp = [310, 310]
        p.w.clvl = 25
        p.mover = type("M", (), {"in_corridor": lambda self: corridor})()
        p.our_slowness = lambda: 1.0
        return p
    def cost(names, corridor=False):
        return make(corridor).band_cost([BYNAME[n] for n in names])
    novice = cost(["novice warrior"] * 6 + ["swordsman"])
    orcs22 = cost(["cave orc"] * 4 + ["snaga"] * 3 + ["black orc"] * 3)
    hill = cost(["hill orc"] * 10)
    hill_c = cost(["hill orc"] * 10, corridor=True)
    p = make()
    p.w.in_dungeon, p.w.level_t = True, 3.0
    p.drainers_seen = set()
    p.w.monsters = [(20, 25, BYNAME["giant red frog"])]
    said = []
    p.notify = lambda what, d=None, news=False, action=True, fields=None: said.append((what, news))
    p.watch_drainers()
    frog = said[-1] if said else None
    ok = novice < 155 and orcs22 > 155 and hill > 155 and hill_c < hill / 2 and frog == ("drainer", True)
    return ok, (f"expected HP: Novice warriors {novice:.0f}, m22's orcs {orcs22:.0f}, 10 Hill orcs {hill:.0f} "
                f"(in a corridor {hill_c:.0f}); 50% of 310 = 155; frog notice (what, news): {frog}")


@case
def quiet_level_left():
    """The matrix: long stays on quiet levels (m33: 22 XP in its last 10 minutes on one 600 ft level). After 3
    minutes on a level, under 10 XP a minute over the last 3 -> the level is done; a busy level isn't."""
    p = pilot()
    p.w.level_t = 7.0
    tp = P.TripPlan(500, 650, P.TripPlan.parse_until("minutes>30"))
    tp.level, tp.level_t0 = 7.0, 0.0
    tp.xp_hist = [(0.0, 1000, 7.0), (10.0, 1005, 7.0)]
    p.w.ind["exp"] = [1012]
    quiet = tp.quiet(p, 200.0)
    tp.xp_hist = [(0.0, 1000, 7.0), (10.0, 1005, 7.0)]
    p.w.ind["exp"] = [1300]
    busy = tp.quiet(p, 200.0)
    early = tp.quiet(p, 100.0)
    ok = quiet and quiet.startswith("quiet") and busy is None and early is None
    return ok, f"12 XP in 3 min: {quiet!r}; 300 XP: {busy}; at 100 s: {early}"


def _dive_on_back_stairs(fled_ago, kept=False, live=True, login_level=False):
    """A dive up from 750 ft standing on the '<' it arrived by, fled_ago seconds after fleeing 700 ft: the stairs
    taken (or not), and the dive."""
    p = pilot()
    w = p.w
    w.depth, w.depth_ft, w.level_t, w.pos = 15, 750, P.gnow() - 300, (4, 150)
    w.standing_on, w.arrive_pos, w.arrived_by = "<", (4, 150), ">"
    w.find = lambda chars: [(4, 150)] if "<" in chars else []
    p.orders["max_depth"] = 750
    p.item_hold_until, p.dangers, p.interesting = 0, lambda: [], lambda: None
    p.loot_step = lambda st: False
    p.mover = type("M", (), {"active": False})()
    p.kept, p.scummed = ({14} if kept else set()), set()
    p.live = live
    p.fled_from = (14, P.gnow() - fled_ago, w.level_t, login_level)
    took = []
    p.take_stairs = took.append
    d = P.Dive(700)
    d.stop, d.level_seen, d.explore, d.probed = False, w.level_t, _Stub(), (w.level_t, w.pos)
    d.tick(p)
    return took, d, p


@case
def fled_stairs_refused_two_minutes_only():
    """m45: fled a band at 700 ft down to 750 ft; 4.5 minutes later the trip's dive up refused the only '<' (back to
    the level fled: held 5 minutes, then never on that level) and spent 10 minutes in a Giant flea swarm looking for
    another. Live server: the hold is 2 minutes (5 on a level the server keeps), and the refusal expires with it. Test
    server (the user, 10-26: one player, no saved levels): no hold, unless the level is kept -- seen kept, or the one
    this Pilot logged in on (our own logout made it static)."""
    took_early, d, p = _dive_on_back_stairs(30)
    key = (p.w.level_t, (4, 150))
    expires = d.bad_t.get(key, 0) - p.fled_from[1]
    took_late, _, _ = _dive_on_back_stairs(130)
    took_kept, _, _ = _dive_on_back_stairs(130, kept=True)
    took_test, _, _ = _dive_on_back_stairs(30, live=False)
    took_test_login, _, _ = _dive_on_back_stairs(30, live=False, login_level=True)
    ok = took_early == [] and key in d.bad_stairs and abs(expires - 105) < 1 and took_late == ["<"] and \
        took_kept == [] and took_test == ["<"] and took_test_login == []
    return ok, f"live, 30 s after: took {took_early} (refusal ends {expires + 15:.0f} s after the flee); " \
               f"130 s after: took {took_late}; on a kept level: {took_kept}; test server 30 s after: {took_test}, " \
               f"on the login level: {took_test_login}"


@case
def quiet_wait_finds_a_spot_and_wakes():
    """The user's 'quiet wait' (10-27): from a corridor into the unknown, the Pilot walks into the walked room (away
    from the unexplored corridor end), waits; a monster that moves wakes it and the goal it paused resumes; a mold
    doesn't; the time running out ends it too."""
    p = _quiet_level()
    spot = p.quiet_spot()
    went = []
    p.mover = type("M", (), {"active": False, "go": lambda self, t: went.append(t) or True,
                             "tick": lambda self: "arrived", "stop": lambda self: None})()
    p.cmd = lambda line, why, hold=0.4: None
    prev = P.Explore() if hasattr(P, "Explore") else None
    g = P.QuietWait(60, prev)
    r1 = g.tick(p)
    p.w.monsters = [(12, 12, BYNAME["disenchanter mold"])]
    r2 = g.tick(p)
    p.w.monsters = [(12, 12, BYNAME["stone troll"])]
    r3 = g.tick(p)
    woke = [d for what, d in p.notes if what == "quiet_end"]
    q = _quiet_level()
    q.mover = p.mover
    q.cmd = p.cmd
    g2 = P.QuietWait(10)
    g2.t0 -= 11
    r4 = g2.tick(q)
    ok = spot is not None and spot[1] <= 26 and went == [[spot]] and r1 is None and r2 is None and \
        r3 and r3[0] == "done" and p.resume_after is prev and woke and "Stone troll" in woke[0] and \
        r4 == ("done", "10 s are up")
    return ok, f"spot {spot}; went {went}; ticks {r1}, {r2}, {r3}, timeout {r4}; told {woke}"


@case
def structures_on_the_aligned_lattice():
    """dungeon_align (our client sends it on): rooms sit on block columns 1, 4, 7... so a double room's centre is at X =
    16, 49, ..., 181 (the Advisor's structures memo). A drawn double room at (16, 49) is found; the same shape at
    (16, 27) -- a centre only the unaligned grid has -- isn't (fewer false pits)."""
    import structures as ST

    def room(Y, X):
        mem = {}
        for y in range(Y - 5, Y + 6):
            for x in range(X - 12, X + 13):
                edge = y in (Y - 5, Y + 5) or x in (X - 12, X + 12)
                ring = y in (Y - 4, Y + 4) or x in (X - 11, X + 11)
                inner_wall = (y in (Y - 3, Y + 3) and X - 10 <= x <= X + 10) or \
                    (x in (X - 10, X + 10) and Y - 3 <= y <= Y + 3)
                mem[(y, x)] = "#" if edge else "." if ring else "#" if inner_wall else " "
        return mem
    on = [(Y, X) for Y, X, ev in ST.scan(room(16, 49))]
    off = [(Y, X) for Y, X, ev in ST.scan(room(16, 27))]
    ok = ST.ALIGNED and (16, 49) in on and (16, 27) not in off
    return ok, f"room at 16,49 -> {on}; at 16,27 -> {off}"
