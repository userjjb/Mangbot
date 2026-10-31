"""unit -- the harness's U-kind set-pieces: the Pilot's decision code on constructed states, no server.

Restructure step 4 (the Advisor's set-piece memo: U = a unit test on a constructed state). Run after any
Pilot or rulebook change:

    python3 unit.py            # every case; exit status 1 if one fails
    python3 unit.py hunt       # the cases whose name contains "hunt"
"""
import collections
import json
import os
import random
import re
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pilot"))
import pilot as P                  # noqa: E402
import glyphs                      # noqa: E402
import itemvalue                   # noqa: E402

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
    p = P.Pilot.__new__(P.Pilot)
    p.w = w or W(**kw)
    p.orders = {"max_depth": 650, "rest_to": 1.0}
    p.deepest_ft = 650
    p.seen_drained = {"CON": (18, 18), "STR": (58, 68), "WIS": (9, 10), "CHR": (3, 5)}
    p.stores_seen, p.flavours, p.keep, p.ability_sources, p.inferred = {}, {}, set(), set(), set()
    p.aware_cache = (-1, set())
    p.unique_names = {r.name.lower() for r in RACES.values() if "UNIQUE" in r.flags}
    p.junk_kinds = {}
    p.req_role = "navigator"
    p.band_warned, p.band_warned_t = (None, 0), 0.0
    p.log = lambda *a, **k: None
    p.notes = []
    p.notify = lambda what, d=None, news=False, action=True: p.notes.append((what, d))
    p.ability_seen_t = 0
    p.emerg_times = []
    p.plan = None
    return p


PHASE = ("11 Scrolls of Phase Door", 70)


# --- hunts (A7's HP halves; A8's rule) ---------------------------------------------------------
@case
def hunt_hill_giant_by_hp():
    """A7: a Hill giant hunt: allowed at 100%; at 80% only with flee_hp 0.4 (with the default 0.5 the emergency
    rule escapes below 132 HP, and the average fight ends at ~125); refused at 60% either way. (The abort point
    is otherwise its worst 3 turns at our AC, ~100: the Advisor's emergency-threshold memo.)"""
    out = []
    for hp, flee in ((265, 0.5), (212, 0.5), (212, 0.4), (159, 0.4)):
        p = pilot(hp=hp, pack=[PHASE])
        p.orders["flee_hp"] = flee
        random.seed(1)          # (the duel simulator's 600 duels: 212/0.4 sits near the line, ~1 run in 20 flipped)
        out.append(p.hunt_refusal("Hill giant")[0] is None)
    return out == [True, False, True, False], f"allowed at 265/0.5, 212/0.5, 212/0.4, 159/0.4: {out}"


@case
def hunt_ranger_summoner():
    """A8: the Ranger hunt is refused with another monster in view, allowed alone at full HP with 5+ Phase."""
    other = [(22, 22, BYNAME["skeleton human"])]
    refused = pilot(pack=[PHASE], monsters=other).hunt_refusal("Ranger")[0]
    alone = pilot(pack=[PHASE]).hunt_refusal("Ranger")[0]
    no_phase = pilot(pack=[]).hunt_refusal("Ranger")[0]
    ok = bool(refused) and "summons" in refused and alone is None and bool(no_phase)
    return ok, f"with a skeleton: {bool(refused)}; alone: {alone is None}; without Phase: {bool(no_phase)}"


@case
def hunt_qualitative_vetoes():
    """Paralysers without Free Action and qualitative AVOID/LEAVE ratings refuse; strength-only ratings don't."""
    p = pilot(pack=[PHASE])
    res = {n: p.hunt_refusal(n)[0] is not None for n in ("Ghoul", "Carrion crawler", "Wormtongue, Agent of Saruman",
                                                         "Boldor, King of the Yeeks", "Brodda, the Easterling")}
    want = {"Ghoul": True, "Carrion crawler": True, "Wormtongue, Agent of Saruman": True,
            "Boldor, King of the Yeeks": True, "Brodda, the Easterling": False}
    return res == want, f"refused: {res}"


# --- items ------------------------------------------------------------------------------------
@case
def hunt_repeat_unique():
    """A unique this character has killed before is refused (a repeat kill gives no XP and no drop)."""
    p = pilot(pack=[PHASE])
    p._uk = {"brodda, the easterling"}
    a = p.hunt_refusal("Brodda, the Easterling")[0]
    p._uk = set()
    b = p.hunt_refusal("Brodda, the Easterling")[0]
    return bool(a) and "repeat kill" in a and b is None, f"killed before: {bool(a)}; never killed: {b is None}"


@case
def jewellery_unknown_plusses():
    """A known ring kind without its plusses is an estimate with P(cursed copy); with them it's known."""
    a, b = itemvalue.value("a Ring of Protection", 13), itemvalue.value("a Ring of Protection [+8]", 13)
    return (not a.known and a.p_cursed > 0.3 and b.known and b.value == 1300), \
        f"unknown {a.value} p_cursed {a.p_cursed:.2f}; known {b.value}"


@case
def bracketed_ego_valued():
    """m53: a Sabre (Holy Avenger) was valued ~2750 (the parser cut the name at the first bracket and lost the ego's
    20000); the shop paid 8721 (its owner's purse). Bracketed egos count now; a plain Sabre doesn't change."""
    a = itemvalue.value("a Sabre (Holy Avenger) (2d7) (+11,+7) [+2] (+1)", 14)
    b = itemvalue.value("a Sabre (2d7) (+11,+7)", 14)
    return a.ego == "(Holy Avenger)" and a.value > 20000 and b.value < 3000, f"Holy Avenger {a.value}, plain {b.value}"


@case
def unique_drop_feeling():
    """{good - Brodda, the Easterling} reads as a {good} feeling (unidentified)."""
    v = itemvalue.value("a Pair of Metal Shod Boots [6] {good - Brodda, the Easterling}", 13)
    return v.known is False and v.pseudo == "good", f"known={v.known} pseudo={v.pseudo}"


@case
def junk_kinds_from_rulebook():
    """The rulebook's junk kinds: 38 (the same as the retired kinds.csv's)."""
    p = pilot()
    p.flavour_file = "/nonexistent"
    p.load_flavours()
    n = sum(1 for v in p.junk_kinds.values() if v)
    return n == 38, f"{n} junk kinds"


@case
def shop_pay_by_owner():
    """Six real sales of 2026-10-23 predicted to the gold piece from value x the owner's pay%."""
    sys.path.insert(0, os.path.join(HERE, "..", "observe"))
    import shopmath
    sales = [("a Small Leather Shield [2,+0]", 18, "Kon-Dar the Ugly"), ("a Dagger (1d4) (+0,+0)", 5, "Ithyl-Mak the Beastly"),
             ("a Scroll of Door/Stair Location", 14, "Ludwig the Humble"), ("a Potion of Infravision", 8, "Ludwig the Humble"),
             ("2 Potions of Neutralize Poison", 62, "Ludwig the Humble"),
             ("a Wand of Stinking Cloud (13 charges)", 231, "Ariel the Sorceress")]
    bad = [n for n, got, o in sales if round(itemvalue.value(n, 8).value * itemvalue.value(n, 8).count *
                                              shopmath.factors(o, 3)[0] / 100) != got]
    return not bad, f"mispredicted: {bad}"


# --- the town kit -----------------------------------------------------------------------------
@case
def town_kit_tiers():
    """Dive04's pack after m23: WoR to 2 first, Restore CON before the kit's extras, the kit's CSW/Phase."""
    pack = [("3 Rations of Food", 80), ("3 Flasks of oil", 77), ("2 Potions of Cure Serious Wounds", 75),
            ("6 Potions of Cure Critical Wounds", 75), ("9 Scrolls of Phase Door", 70),
            ("a Scroll of Word of Recall {@R650}", 70), ("a Brass Lantern (with 6370 turns of light)", 39)]
    w = W(pack=pack, gold=637)
    w.depth, w.depth_ft, w.in_dungeon = 0, 0, False
    p = pilot(w)
    p.seen_drained = {"CON": (17, 18)}
    need = [(t, k, n) for t, k, s, n, c in p.town_needs(None, ())]
    # (no flasks: the lantern's 6370 turns and the 3 flasks reach 9000; rations: kit B's 3, had)
    want = [(1, "Word of Recall", 1), (3, "Restore Constitution", 1), (4, "Cure Serious Wounds", 2),
            (4, "Phase Door", 1), (4, "Heroism", 3), (4, "Potion of Speed", 2)]   # (Heroism since m41, Speed since)
    return need == want, f"{need}"


# --- the trip plan ----------------------------------------------------------------------------
@case
def trip_conditions_parse():
    """Conditions parse; unknown words and wrong value types are refused."""
    ok = P.TripPlan.parse_until("cures<4 or phase<5 or time>22:40 or band")
    bad = []
    for t in ("foo<3", "time>5", "band or bogus"):
        try:
            P.TripPlan.parse_until(t)
            bad.append(t)
        except ValueError:
            pass
    return len(ok) == 4 and not bad, f"parsed {len(ok)}; not refused: {bad}"


# --- abilities --------------------------------------------------------------------------------
@case
def ability_proofs():
    """'You are unaffected!' proves rBlind after a blinding spell, rNexus after TELE_LEVEL, Free Action after a
    paralysing touch; the sustain and hold-life messages prove themselves."""
    p = pilot()
    t = P.gnow()
    p.w.messages.extend([(t, "The Dark elven priest casts a spell, burning your eyes!"), (t + .1, "You are unaffected!"),
                         (t + 1, "The Gnome mage gestures at your feet."), (t + 1.1, "You are unaffected!"),
                         (t + 2, "The Ghoul touches you."), (t + 2.1, "You are unaffected!"),
                         (t + 3, "You feel weak for a moment, but the feeling passes."),
                         (t + 4, "You keep hold of your life force!")])
    p.watch_abilities()
    want = {"free_action", "hold_life", "resist_blind", "resist_nexus", "sustain_str"}
    return p.inferred == want, f"{sorted(p.inferred)}"


@case
def unique_drop_fetched():
    """C3's Pilot half: idle after a unique's kill, with an item 2 squares from where it died, the policy step
    fetches it (a quiet goto), once per square."""
    p = pilot()
    w = p.w
    w.memory = {(20, 20): ".", (21, 22): "|", (25, 30): "!"}
    w.flag = lambda k: False
    w.last_hit_t = 0
    p.goal, p.policy_t, p.busy_until, p.pending_use = None, 0, 0, None
    p.skipped_items = set()
    p.unique_drop = (w.level_t, (20, 20), P.gnow())
    class M:
        active = False
        def go(self, *a, **k): return True
        def stop(self): pass
    p.mover = M()
    got = []
    p.set_goal = lambda g: got.append(g)
    acted = p.policy_tick(P.gnow())
    again = p.policy_tick(P.gnow() + 4)
    names = [g.describe() for g in got]
    return acted and names[:1] == ["goto 21,22"] and len(names) == 1, f"goals {names}, second tick acted={again}"


class _Mover:
    active = False

    def __init__(self):
        self.went = []
        self.path = []

    def go(self, goals, **k):
        self.went.append(list(goals))
        return True

    def tick(self):
        return "moving"

    def stop(self):
        pass


@case
def loot_band_stops_looting():
    """C5: with a serious band flagged on this level in the last 90 s, no loot detour; without it, the item 5
    squares off is fetched."""
    def run(band):
        p = pilot()
        p.w.memory = {(20, 20): ".", (20, 25): "-"}
        p.orders["loot_radius"] = 10
        p.skipped_items = set()
        p.mover = _Mover()
        p.band_warned, p.band_warned_t = ((p.w.level_t, 6), P.gnow()) if band else ((None, 0), 0.0)
        state = {}
        return p.loot_step(state), p.mover.went
    with_band, without = run(True), run(False)
    return (with_band == (False, []) and without[0] and without[1] == [[(20, 25)]]), \
        f"band: {with_band}; no band: {without}"


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
def game_clock_from_fuel():
    """The time bubble's clock (world.py): resting with nothing in view, fuel falling 16 ticks/s (10x)
    sets the factor to ~10; a monster in view (fast_ok off) puts it back to the model's 1.0 at once; the
    HP bubble's model 0.2 applies when no speed-up can; a refuel isn't read as time; `waited` needs the
    wall time too."""
    import world as Wd
    out = {}
    try:
        Wd.set_time_factor(1.0)
        Wd.set_fast_ok(True)
        t0 = time.time()
        Wd.fuel_reading(5000, t0)                      # (the first value: when it was sent is unknown)
        for i in range(1, 5):
            Wd.fuel_reading(5000 - 16 * i, t0 + i)
        out["resting"] = round(Wd.time_factor(), 1)
        Wd.fuel_reading(7000, t0 + 5)                  # refuelled: no reading
        out["after_refuel"] = round(Wd.time_factor(), 1)
        Wd.set_fast_ok(False)
        out["monster_in_view"] = Wd.time_factor()
        Wd.set_time_factor(0.2)
        out["bubble"] = Wd.time_factor()
        Wd.set_time_factor(1.0)
        Wd.set_fast_ok(True)
        Wd._set_factor(10.0, time.time())
        g = Wd.gnow()
        time.sleep(0.02)
        out["waited_wall_floor"] = Wd.waited(g, 0.05)  # 0.2 game s, 0.02 wall s: not yet
        time.sleep(0.05)
        out["waited_after"] = Wd.waited(g, 0.05)
    finally:
        Wd.set_fast_ok(False)
        Wd.set_time_factor(1.0)
        Wd.fuel_reading(None)
    ok = (9.5 <= out["resting"] <= 10.5 and out["after_refuel"] == out["resting"] and out["monster_in_view"] == 1.0
          and out["bubble"] == 0.2 and out["waited_wall_floor"] is False and out["waited_after"] is True)
    return ok, f"{out}"


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
def town_kit_townfarms_when_broke():
    """The user (after m27, which ended broke): plan town short of a Word of Recall and its price townfarms the
    difference by day before buying; by night it saves the gold."""
    def run(day):
        p = pilot(gold=30, pack=[("a Scroll of Word of Recall", 70)])
        p.w.depth, p.w.in_dungeon, p.w.inven_dirty = 0, False, False
        p.w.is_day = lambda: day
        p.busy_until, p.pending_use = 0.0, None
        p.price_of = lambda kind, store=None: 242
        g = P.TownKit()
        g.stage, g.t = "buy", 0.0
        p.town_shopping = lambda kit, bl: ([], [])
        g.tick(p)
        return type(g.sub).__name__ if g.sub else None, g.done_log[-1:]
    day, night = run(True), run(False)
    return day[0] == "TownFarm" and night[0] is None and "night" in night[1][0], f"day: {day}; night: {night}"


@case
def crutch_devices_sold_on_test():
    """The user: on the test server mapping/detection devices are sold (a crutch the live server won't give us);
    with --live they're kept like any useful device. Magic Mapping scrolls (sold in shops) stay in the kit."""
    def count(live, name, tval):
        p = pilot(pack=[(name, tval)])
        p.live = live
        p.town_buyers = lambda it: (6, 100)
        return p.town_sell_count(p.w.items()[0])
    test = count(False, "a Rod of Enlightenment", 66)
    live = count(True, "a Rod of Enlightenment", 66)
    scroll = count(False, "3 Scrolls of Magic Mapping", 70)
    return test == 1 and live == 0 and scroll == 0, f"test sells {test}, live sells {live}, scrolls sold {scroll}"


@case
def pack_full_makes_room():
    """C4: pack 23/23 with a worthless Potion of Water among kit items; a Wand of Stinking Cloud underfoot: the
    Pilot destroys the water to take the wand (and never destroys kit consumables)."""
    pack = [("a Potion of Water", 75)] + [(f"{n} Potions of Cure Critical Wounds", 75) for n in range(2, 24)]
    p = pilot(pack=pack)
    p.junk_kinds = {"Potion of Water": True}
    p.skipped_items, p.room_t, p.unique_drop = set(), 0.0, None
    p.w.items = lambda tval=None, name=None, equip=False: [i for i in p.w.inven if i["equip"] == equip
                                                           and (tval is None or i["tval"] == tval)]
    p.w.hunger = 3
    sent = []
    p.cmd = lambda line, why, hold=0.4: sent.append((line, why))
    p.c = type("C", (), {"send": lambda self, x: None})()
    took = p.pickup_room("a Wand of Stinking Cloud (12 charges)")
    destroyed = [x for x in sent if x[0].startswith("custom k")]
    return (not took and len(destroyed) == 1 and "Water" in destroyed[0][1]), f"sent {sent}"


@case
def c1_valuable_sale_refused():
    """C1: selling an {excellent} item, an ability source, or a known valuable is refused with the reason; the
    override (`!`) is the accepted-loss step, priced into the debt."""
    p = pilot()
    boots = {"name": "a Pair of Soft Leather Boots [2] {excellent}", "tval": 30, "number": 1, "item": 0}
    fa = {"name": "a Pair of Soft Leather Boots of Free Action [2,+4]", "tval": 30, "number": 1, "item": 1}
    a = p.value_refusal(boots, "sell")
    b = p.value_refusal(fa, "destroy")
    return bool(a) and bool(b) and "identify" in a.lower(), f"{a!r} | {b!r}"


@case
def c2_unknown_charges():
    """C2: a wand of a known kind without its charges shown is an estimate, and selling it is refused (identify)."""
    p = pilot()
    wand = {"name": "a Wand of Stinking Cloud", "tval": 65, "number": 1, "item": 0}
    v = p.iv(wand["name"])
    why = p.value_refusal(wand, "sell")
    return v.known is False and bool(why), f"known={v.known} value={v.value}; {why!r}"


@case
def c6_ambiguous_names():
    """C6: 'Light' is the Scroll of Light, not Cure Light Wounds; two different rings by a shared word refuse."""
    pack = [("14 Potions of Cure Light Wounds", 75), ("a Scroll of Light", 70), ("a Ring of Protection [+8]", 45),
            ("a Ring of Protection [+4]", 45), ("a Ring of Strength <+2>", 45)]
    p = pilot(pack=pack)
    light = p.item_index("Light", pack_only=True)
    try:
        p.item_index("Ring", pack_only=True)
        rings = "not refused"
    except ValueError as e:
        rings = "refused"
    return light == 1 and rings == "refused", f"'Light' -> {light}; 'Ring' {rings}"


@case
def c7_unknown_ring_not_worn():
    """C7: the Navigator's `wear` of an unknown ring (or a known kind without its plusses) is refused."""
    w = W(pack=[("a Bloodstone Ring", 45), ("a Ring of Protection", 45), ("a Ring of Protection [+8]", 45)])
    w.depth, w.depth_ft, w.in_dungeon = 0, 0, False
    p = pilot(w)
    p.dead, p.last_report, p.report_state = False, (0, 0.0), None
    out = []
    for name in ("Bloodstone_Ring", "a", "Ring_of_Protection_[+8]"):
        try:
            r = p.do_request({"cmd": "wear", "args": [name], "role": "navigator"})
        except Exception as e:
            r = {"ok": None, "error": repr(e)}
        out.append("isn't identified" in str(r.get("error", "")))
    return out[:2] == [True, True] and not out[2], f"refused: {out}"


@case
def c9_identify_good_first():
    """C9: a {good} weapon with unknown plusses is an identify candidate (worth more than twice a scroll)."""
    p = pilot(pack=[("a Trident (2d10) {good}", 22), ("a Dagger (1d4) {average}", 23)])
    cands = [it["name"] for _, it in p.identify_candidates(2 * 80)]
    return cands == ["a Trident (2d10) {good}"], f"{cands}"


@case
def e1_supply_gate():
    """E1: going down to 650 ft with 1 CLW, 2 Phase and 1 WoR is refused with what's missing."""
    p = pilot(pack=[("a Potion of Cure Light Wounds", 75), ("2 Scrolls of Phase Door", 70),
                    ("a Scroll of Word of Recall", 70)], worn=[("a Spear (1d6) (+5,+7)", 22, 50),
                                                              ("a Brass Lantern (with 9000 turns of light)", 39, 50)])
    gap = p.supply_gate(650, True)
    want = ("cure potions", "CSW+CCW", "Phase Door", "Word of Recall")
    return all(any(w_ in g for g in gap) for w_ in want), f"{gap}"


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
def loot_owed_and_valuables():
    """The user (m29 20:26): gold and an unknown wand left beside the path while a Baby black dragon was in view,
    never revisited. Passed up with a monster in view -> fetched once clear (12 away, beyond loot_radius 10);
    a wand 20 away fetched without being owed; a plain item 20 away not; a walk cut short is retried; a mold in
    view doesn't stop looting, nor a weak one (10+ levels below us: a Jackal); a Black orc or an Uruk does."""
    class Mover:
        def __init__(self):
            self.active, self.path, self.sent = False, [], []

        def go(self, goals, **k):
            g = list(goals)[0]
            self.sent.append(g)
            self.active, self.path = True, [g] * max(abs(g[0] - p.w.pos[0]), abs(g[1] - p.w.pos[1]))
            return True

        def tick(self):
            return "moving"

        def stop(self):
            self.active = False
    p = pilot()
    p.w.pos, p.w.level_t = (20, 20), 5.0
    p.orders.update(loot_radius=10, think_hp=0.65, pickup="all")
    p.band_warned, p.band_warned_t = (None, 0), 0.0
    p.skipped_items = set()
    p.mover = Mover()
    p.danger_why = lambda r, *a, **k: None
    p.w.memory = {(20, 21): "$", (21, 22): "-", (20, 40): "-", (40, 20): "|"}
    dragon = (19, 23, BYNAME["black orc"])     # (level 13 against our 22: blocks)
    st = {}
    p.w.monsters = [dragon]
    blocked = p.loot_step(st)
    owed = set(p.loot_mem["owed"])
    p.w.monsters = []
    p.w.pos = (20, 9)                     # walked on: the gold is 12 away now, the near wand 13
    first = p.loot_step(st), p.mover.sent[-1]
    p.w.monsters = [(20, 12, BYNAME["uruk"])]   # the walk is cut short: a monster comes
    p.loot_step(st)
    tries = p.loot_mem["tries"][(20, 21)]
    p.w.monsters = [(20, 8, BYNAME["brown mold"]), (20, 11, BYNAME["jackal"])]   # a mold, a weak monster 2 off
    again = p.loot_step(st), p.mover.sent[-1]
    p.mover.active = False
    st["looting"] = False
    p.loot_mem["done"] |= {(20, 21), (21, 22)}
    p.w.monsters = []
    p.w.pos = (20, 20)
    far = p.loot_step(st), p.mover.sent[-1]
    p.mover.active = False
    st["looting"] = False
    p.loot_mem["done"].add((20, 40))
    plain = p.loot_step(st)
    ok = not blocked and owed == {(20, 21), (21, 22)} and first == (True, (20, 21)) and tries == 1 and \
        again == (True, (20, 21)) and far == (True, (20, 40)) and plain is False
    return ok, (f"blocked {blocked}, owed {sorted(owed)}; clear: {first}; cut short: tries {tries}; mold in view: "
                f"{again} (with a Jackal 2 off); wand 20 off: {far}; plain item 20 off fetched: {plain}")


@case
def provisions_one_food_no_oil():
    """The user (10-25): food AND Satisfy Hunger, flasks by the handful. One food source (rations), eaten to Full
    in town; the lantern topped up to 9000 in town (flasks bought for it, then used); no oil carried. Near a
    trip's end the spare rations and flasks go first when loot needs room."""
    def make(pack, hunger=3, worn=None):
        p = pilot(pack=pack, worn=worn)
        p.w.depth, p.w.depth_ft, p.w.in_dungeon = 0, 0, False
        p.w.ind["hunger"] = [hunger]
        p.plan = None
        p.w.recall_pending = False
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(line)
        return p
    low = make([("3 Rations of Food", 80)], worn=[("a Brass Lantern (with 2000 turns of light)", 39, 50)])
    flasks = [(t, k, n) for t, k, s, n, c in low.town_needs("C", ()) if k == "Flask of oil"]
    full = make([("3 Rations of Food", 80)], worn=[("a Brass Lantern (with 12000 turns of light)", 39, 50)])
    none = [k for t, k, s, n, c in full.town_needs("C", ()) if k == "Flask of oil"]
    # the town step: fill the lantern first, then eat
    kit = P.TownKit("C")
    tw = make([("a Flask of oil", 77), ("3 Rations of Food", 80)], hunger=2,
              worn=[("a Brass Lantern (with 2000 turns of light)", 39, 50)])
    tw.provision_step(kit)
    first = tw.cmds[-1]
    tw.w.inven = [i for i in tw.w.inven if i["tval"] != 77]
    tw.w.inven[0]["name"] = "a Brass Lantern (with 9500 turns of light)"
    tw.provision_step(kit)
    second = tw.cmds[-1]
    tw.w.ind["hunger"] = [4]
    third = tw.provision_step(kit)
    # pack values and town sales
    pv = make([("3 Rations of Food", 80), ("2 Scrolls of Satisfy Hunger", 70), ("a Piece of Elvish Waybread", 80),
               ("2 Flasks of oil", 77)], worn=[("a Brass Lantern (with 12000 turns of light)", 39, 50)])
    it = {i["name"]: i for i in pv.w.inven if not i["equip"]}
    kept = pv.pack_value(it["3 Rations of Food"]) == float("inf")
    cheap = [n for n in ("2 Scrolls of Satisfy Hunger", "a Piece of Elvish Waybread", "2 Flasks of oil")
             if pv.pack_value(it[n]) < float("inf")]
    pv.w.recall_pending = True
    # (since 10-26 rations are never destroyed for room, near a trip's end too: m46-m47 ended trips short of food)
    spare = pv.pack_value(it["3 Rations of Food"]) == float("inf")
    sells = [n for n in it if pv.town_sell_count(it[n])]
    ok = flasks == [(2, "Flask of oil", 1)] and not none and first.startswith("custom F") and \
        second.startswith("eat") and third is False and kept and len(cheap) == 3 and spare and \
        "a Piece of Elvish Waybread" in sells and "2 Flasks of oil" in sells and "3 Rations of Food" not in sells
    return ok, (f"lantern 2000: buy {flasks}; 12000: {none}; town step: {first!r}, then {second!r}, then Full: "
                f"{third}; rations kept {kept}; worth their price: {cheap}; recall pending, rations kept for room: {spare}; "
                f"town sells {sells}")


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
def unseen_drainer_leaves():
    """m29, m30: a Moaning spirit (invisible, passes walls, +10, TOUCH:LOSE_DEX) drained DEX; nothing was in view
    so no drainer rule fired. A drain with nothing in view that drains (and no trap's dart) -> leave the level
    (the trip plan's drainer leave; without a plan, Flee to known stairs). A dart trap -> no leave."""
    def run(msg, monsters=()):
        p = pilot()
        p.w.in_dungeon, p.w.level_t = True, 5.0
        p.w.monsters = list(monsters)
        p.w.ind.update({f"stat{i}": [v, v] for i, v in enumerate((58, 5, 9, 28, 18, 3))})
        p.seen_drained, p.seen_blows = None, None
        p.drains_here = (None, 0)
        p.plan, p.goal = None, None
        p.w.find = lambda chars: [(30, 30)]
        p.w.adjacent_monsters = lambda: [m for m in p.w.monsters if p.w.dist(m[:2]) == 1]
        p.set_goal = lambda g: setattr(p, "goal", g)
        p.watch_character()                       # the baseline
        p.w.ind["stat3"] = [18, 28]               # DEX 18/10 -> 18
        p.w.messages.append((P.gnow(), msg))
        p.watch_character()
        return [w for w, _ in p.notes], type(p.goal).__name__
    ghost = run("It touches you.")
    dart = run("A small dart hits you!")
    frog = run("The Giant red frog bites you.", [(20, 21, BYNAME["giant red frog"])])
    ok = "drainer" in ghost[0] and ghost[1] == "Flee" and "drainer" not in dart[0] and dart[1] == "NoneType" and \
        "drainer" not in frog[0]
    return ok, f"unseen: {ghost}; dart trap: {dart}; a visible frog (its own rules): {frog}"


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
def town_makes_room_before_buying():
    """m30 06:34: plan town's Restore Dexterity buy failed twice on a full pack ("You cannot carry that many
    items"), silently. A buy of a kind not in the pack, with no slot free: sell the cheapest unprotected item (or
    destroy it if no shop buys it) first; with nothing to let go, say so."""
    filler = [(f"a Dagger (1d4) (+{k},+0)", 23) for k in range(20)] + [("3 Rations of Food", 80),
              ("9 Potions of Cure Critical Wounds", 75), ("3 Scrolls of Word of Recall", 70)]
    p = pilot(pack=filler)
    p.w.depth, p.w.depth_ft, p.w.in_dungeon = 0, 0, False
    p.cmds = []
    p.cmd = lambda line, why, hold=0.4: p.cmds.append(line)
    p.c = type("C", (), {"send": lambda self, x: None})()
    kit = P.TownKit("C")
    buys = [(3, "Restore Dexterity", 5, 1, None)]
    acted = p.town_make_room(kit, buys)
    how = type(kit.sub).__name__ if kit.sub else (p.cmds[-1] if p.cmds else None)
    roomy = pilot(pack=filler[:10])
    roomy.w.depth, roomy.w.in_dungeon = 0, False
    kit2 = P.TownKit("C")
    no_need = roomy.town_make_room(kit2, buys)
    ok = acted and how == "Shop" and "selling a Dagger" in " ".join(kit.done_log) and no_need is False
    return ok, f"full pack: acted {acted} by {how} ({kit.done_log}); 10 items: acted {no_need}"


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
def fear_cure_order():
    """The user (10-25): afraid and in danger, Heroism first; Boldness only without Heroism; Berserk last (the
    pack's own order decided before)."""
    def pick(pack):
        return (pilot(pack=pack).fear_cure() or {}).get("name")
    both = pick([("a Potion of Boldness", 75), ("a Potion of Berserk Strength", 75), ("2 Potions of Heroism", 75)])
    bold = pick([("a Potion of Berserk Strength", 75), ("a Potion of Boldness", 75)])
    last = pick([("a Potion of Berserk Strength", 75)])
    ok = both == "2 Potions of Heroism" and bold == "a Potion of Boldness" and last == "a Potion of Berserk Strength"
    return ok, f"all three: {both}; no Heroism: {bold}; only Berserk: {last}"


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
def ability_weapon_kept():
    """m33: the town weapon policy wielded a Main Gauche (~40 a round) over a Scimitar of Westernesse (~28: Free
    Action, See Invisible, +STR/DEX/CON), twice. A weapon that loses an ability isn't wielded; a plain upgrade is."""
    def run(worn, pack):
        p = pilot(worn=worn, pack=pack)
        p.w.depth, p.w.in_dungeon = 0, False
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(why)
        p.ARMOUR_SLOTS = {}
        p.upgrade_step()
        return p.cmds[-1] if p.cmds else None
    west = run([("a Scimitar of Westernesse (2d5) (+9,+8) (+1)", 23, 130)], [("a Main Gauche (1d5) (+0,+7)", 23)])
    plain = run([("a Dagger (1d4) (+0,+0)", 23, 12)], [("a Main Gauche (1d5) (+0,+7)", 23)])
    ok = west is None and plain and "Main Gauche" in plain
    return ok, f"Westernesse wielded: {west}; a plain Dagger wielded: {plain!r}"


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
    p.notify = lambda what, d=None, news=False, action=True: said.append((what, news))
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


@case
def disenchanter_beside_path_not_fought():
    """m33, m34: Disenchanter molds beside the path were meleed ("disenchants: killing it"); m33's shield lost +1. A
    disenchanter adjacent but not by the square we're heading for: no fight (step past); in the way: fought; by an
    item we're fetching (m37): the item is left."""
    def run(goal, glyph=None):
        p = pilot()
        p.w.pos, p.w.level_t, p.w.clvl = (20, 20), 5.0, 25
        if glyph:
            p.w.memory[goal] = glyph
            p.loot_mem = {"level": 5.0, "done": set()}
        p.mover = type("M", (), {"goals": {goal}, "active": True, "stop": lambda self: None})()
        p.still_goals, p.still_fighting = (None, set()), None
        p.orders["think_hp"] = 0.65
        p.notify = lambda *a, **k: None
        return p.still_fight_tick(P.gnow(), [(20, 21, BYNAME["disenchanter mold"])])
    beside = run((25, 10))
    blocking = run((20, 22))
    item = run((20, 22), "!")          # (m37: Boldor's drops beside a Disenchanter mold)
    return beside is False and blocking is True and item is False, \
        f"beside the path: fight {beside}; by the goal: fight {blocking}; an item by it: fight {item}"


@case
def flee_maps_before_unexplored():
    """m31: stairs known (Door/Stair Location) but no known path; the flee went through unexplored squares, got
    stuck, and Word of Recall ended the trip with 4 Magic Mapping scrolls carried. Now: Magic Mapping first, once
    per level; with a known path, no scroll."""
    def run(mem):
        p = pilot(pack=[("4 Scrolls of Magic Mapping", 70)])
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
def ability_armour_kept():
    """Same class as m33's weapon swap: the armour upgrade went by AC alone, so a plain Metal Scale Mail would have
    replaced the Hard Studded Leather of Resistance (four resists). Armour that loses an ability isn't worn; a plain
    upgrade over plain armour is."""
    def run(worn, pack):
        p = pilot(worn=worn, pack=pack)
        p.w.depth, p.w.in_dungeon = 0, False
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(why)
        p.weapon_table = lambda: []
        p.upgrade_step()
        return p.cmds[-1] if p.cmds else None
    res = run([("Hard Studded Leather of Resistance (-1) [7,+8]", 37, 100)], [("Metal Scale Mail (-2) [38,+0]", 37)])
    plain = run([("Soft Leather Armour [8,+0]", 36, 80)], [("Metal Scale Mail (-2) [38,+0]", 37)])
    ok = res is None and plain and "Metal Scale Mail" in plain
    return ok, f"over the Leather of Resistance: {res}; over plain leather: {plain!r}"


@case
def town_identifies_scrolls_in_hand():
    """m32 08:07: plan town replied "identified 0" (its threshold was twice a scroll's price), then the idle tactic
    (20 gold) read the leftover scroll on the Oak Staff the Navigator was about to identify. The plan now reads
    scrolls in hand at the idle threshold before it replies."""
    p = pilot(pack=[("a Scroll of Identify", 70), ("an Oak Staff", 55)],
              worn=[("a Spear (1d6) (+5,+7)", 22, 50), ("a Brass Lantern", 39, 50)])
    p.w.depth, p.w.depth_ft, p.w.in_dungeon = 0, 0, False
    p.busy_until, p.pending_use = 0.0, None
    p.price_of = lambda kind, store: 80
    p.unknown_flavour = lambda it: False
    staff = p.w.items()[1]
    p.identify_candidates = lambda minimum: [(50, staff)] if 50 >= minimum else []
    p.cmds = []
    p.cmd = lambda line, why, hold=0.4: p.cmds.append(why)
    kit = P.TownKit()
    kit.stage = "identify"
    kit.tick(p)
    ok = kit.identified == 1 and p.cmds == ["identify an Oak Staff (policy)"]
    return ok, f"identified {kit.identified}, commands {p.cmds}"


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
def gear_review_finds_free_slot():
    """The user (10-25): a between-mission gear step. Dive04 wears a Ring of Resist Cold and an Amulet of Resist
    Lightning while its Leather of Resistance gives both: two free slots; the Magic Shop's Ring of Protection [+9]
    goes in one. Plain armour with more AC never replaces a piece that gives an ability."""
    worn = [("a Scimitar of Westernesse (2d5) (+9,+8) (+1)", 23, 130), ("a Ring of Resist Cold", 45, 1),
            ("a Ring of Protection [+8]", 45, 1), ("an Amulet of Resist Lightning", 40, 3), ("a Brass Lantern", 39, 50),
            ("Hard Studded Leather of Resistance (-1) [7,+8]", 37, 100), ("a Shadow Cloak [6,+3]", 35, 10),
            ("an Orcish Shield [5,+4] (+1)", 34, 60), ("an Iron Helm [5,-3]", 32, 75), ("a Set of Gauntlets [2,-2]", 31, 25),
            ("a Pair of Metal Shod Boots [6,+2]", 30, 60)]
    p = pilot(worn=worn, gold=5455)
    p.w.inven = [dict(i, item=24 + (0 if k == 0 else k + 1)) for k, i in enumerate(p.w.inven)]   # (no bow: slot b)
    p.w.flags = {"res_acid": "g", "res_elec": "eg", "res_fire": "g", "res_cold": "cg", "see_invis": "a", "free_act": "a",
                 "res_dark": "h"}
    p.w.depth, p.w.in_dungeon = 0, False
    p.town_reserve = lambda: 500
    p.flavour_of = lambda it: None
    p.stores_seen = {6: {"prices": {"ring of protection [+9]": 2240, "amulet of slow digestion": 320}},
                     2: {"prices": {"metal brigandine armour (-3) [19,+0]": 1248, "large leather shield [4,+0]": 187,
                                    "pair of hard leather boot [3,+4]": 643}},
                     7: {"prices": {"large metal shield [5,+3]": 2775}}}
    text = p.gear_review()
    ok = ("c) a Ring of Resist Cold: res_cold also from g)" in text and "e) an Amulet of Resist Lightning" in text
          and "ring of protection [+9] for 2240 at the Magic Shop (6) [`buy 6/ring_of_protection_[+9]@2464`]: +9 AC"
          " (in the free slot)" in text
          and "brigandine" not in text and "missing, most wanted first: resist poison" in text)
    return ok, text.replace("\n", " | ")


@case
def speed_potion_over_junk_weapon():
    """m36 15:09: a Potion of Speed left on the floor, "pack full and nothing cheaper (~34)", with average Flails
    in the pack. Kit consumables found are worth their replacement cost: the Flail goes."""
    pack = [("a Flail (2d6) {average}", 21)] + [(f"{n} Potions of Cure Critical Wounds", 75) for n in range(2, 24)]
    p = pilot(pack=pack)
    p.skipped_items, p.room_t, p.unique_drop = set(), 0.0, None
    p.w.hunger = 3
    p.flavour_of = lambda it: None
    sent = []
    p.cmd = lambda line, why, hold=0.4: sent.append((line, why))
    p.c = type("C", (), {"send": lambda self, x: None})()
    took = p.pickup_room("a Potion of Speed")
    destroyed = [x for x in sent if x[0].startswith("custom k")]
    return (not took and len(destroyed) == 1 and "Flail" in destroyed[0][1]), f"sent {sent}"


@case
def better_ring_replaces_worn():
    """m36 15:26: plan town sold a Ring of Protection [+9] while the [+8] was worn. In town a bigger bonus of the
    same kind, or a ring that adds AC over one whose resist other gear gives, is worn (off first, then on)."""
    worn = [("a Ring of Protection [+8]", 45, 1), ("a Ring of Resist Cold", 45, 1),
            ("Hard Studded Leather of Resistance (-1) [7,+8]", 37, 100)]

    def make(pack, flags):
        p = pilot(worn=worn, pack=pack)
        p.w.inven = [dict(i, item={0: 26, 1: 27, 2: 30}[k]) if i["equip"] else i for k, i in enumerate(p.w.inven)]
        p.w.depth, p.w.in_dungeon = 0, False
        p.w.flags = flags
        p.flavour_of = lambda it: None
        p.weapon_table = lambda: []
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(why)
        return p
    a = make([("a Ring of Protection [+9]", 45)], {"res_cold": "d"})            # Resist Cold not redundant
    a.upgrade_step()
    b = make([("a Ring of Protection [+9]", 45)], {"res_cold": "dg"})           # the Leather gives cold too
    b.upgrade_step()
    c = make([("a Ring of Protection [+7]", 45)], {"res_cold": "d"})
    c.upgrade_step()
    ok = (a.cmds == ["take off a Ring of Protection [+8] for a Ring of Protection [+9]"]
          and b.cmds == ["take off a Ring of Resist Cold for a Ring of Protection [+9]"] and c.cmds == [])
    return ok, f"bigger bonus: {a.cmds}; redundant: {b.cmds}; smaller: {c.cmds}"


@case
def gear_line_keeps_ability_armour():
    """m37: 'better than worn' offered Metal Lamellar Armour [23] over the Hard Studded Leather of Resistance (four
    resists), by AC alone; the line now follows the upgrade step's rule. A disenchant message is news."""
    p = pilot(worn=[("Hard Studded Leather of Resistance (-1) [7,+8]", 37, 100), ("an Iron Helm [5,-1]", 32, 75)],
              pack=[("a Metal Lamellar Armour (-3) [23] {good}", 38), ("an Iron Helm [5,+2]", 32)])
    p.flavour_of = lambda it: None
    line = p.gear_line()
    q = pilot()
    q.gain_hist, q.w.hp_hist, q.hits, q.mons_mem = collections.deque(maxlen=80), [], collections.Counter(), {}
    q.belief_msg_t, q.kills_t = 0.0, 0.0
    q.w.messages.append((P.gnow(), "Your Shadow Cloak (h) was disenchanted!"))
    try:
        q.belief_tick(P.gnow())
    except Exception:
        pass
    news = [d for what, d in q.notes if what == "disenchanted"]
    ok = "Lamellar" not in line and "Iron Helm [5,+2]" in line and news == ["Shadow Cloak lost a plus (disenchanted)"]
    return ok, f"{line}; news {news}"


@case
def unique_drop_pushes_out_only_cheap():
    """m37: Boldor's drops took every slot by force (a Tulwar ~76 destroyed for a 4-gold Dagger). A unique's drop
    may push out only things worth under 50; otherwise it competes on value."""
    def run(cheap):
        pack = [cheap] + [(f"{n} Potions of Cure Critical Wounds", 75) for n in range(2, 24)]
        p = pilot(pack=pack)
        p.skipped_items, p.room_t = set(), 0.0
        p.unique_drop = (p.w.level_t, p.w.pos)
        p.w.hunger = 3
        p.flavour_of = lambda it: None
        sent = []
        p.cmd = lambda line, why, hold=0.4: sent.append(why)
        p.c = type("C", (), {"send": lambda self, x: None})()
        p.pickup_room("a Dagger (1d4)")
        return [x for x in sent if "destroy" in x]
    tulwar = run(("a Tulwar (2d4) {average}", 21))
    helm = run(("an Iron Helm [5,-3]", 32))
    return tulwar == [] and len(helm) == 1, f"over a Tulwar: {tulwar}; over a [5,-3] helm: {helm}"


@case
def room_eat_never_gorges():
    """m49: the make-room rule ate a Piece of Elvish Waybread (7500 food) while Fed, beside Wargs: Gorged, -10 speed.
    Food is eaten for room only if the top of the hunger level plus its food stays 1000 under Gorged: Waybread or a
    ration not when Fed; a ration when Hungry; Jerky (1500) when Fed."""
    def run(food, hunger):
        pack = [(food, P.TV_FOOD)] + [(f"{n} Potions of Cure Critical Wounds", 75) for n in range(2, 24)]
        p = pilot(pack=pack)
        p.skipped_items, p.room_t, p.unique_drop = set(), 0.0, None
        p.w.hunger = hunger
        p.flavour_of = lambda it: None
        sent = []
        p.cmd = lambda line, why, hold=0.4: sent.append(why)
        p.c = type("C", (), {"send": lambda self, x: None})()
        p.pickup_room("a Scroll of Enchant Weapon To-Dam")
        return any("make room: eat" in x for x in sent)
    got = [run("a Piece of Elvish Waybread", 3), run("a Ration of Food", 3), run("a Ration of Food", 2),
           run("a Strip of Beef Jerky", 3), run("a Piece of Elvish Waybread", 2)]
    return got == [False, False, True, True, True], \
        f"eaten (Waybread Fed, ration Fed, ration Hungry, Jerky Fed, Waybread Hungry): {got}"


@case
def theft_is_news():
    """m51, m53: Novice rogues stole 2617 and 2392 gold and nothing said so. The theft message is news, with the
    total; a stolen item too."""
    q = pilot()
    q.gain_hist, q.w.hp_hist, q.hits, q.mons_mem = collections.deque(maxlen=80), [], collections.Counter(), {}
    q.belief_msg_t, q.kills_t = 0.0, 0.0
    for t in ("2617 coins were stolen!", "2392 coins were stolen!", "Your Hard Studded Leather [7] {excellent} (u) "
              "was stolen!"):
        q.w.messages.append((P.gnow(), t))
    try:
        q.belief_tick(P.gnow())
    except Exception:
        pass
    news = [d for what, d in q.notes if what == "thief"]
    ok = len(news) == 3 and "5009 stolen" in news[1] and news[2].startswith("Hard Studded Leather [7] {excellent} stolen")
    return ok, f"news {news}"


@case
def weight_limit_sheds_cheap_heavy_loot():
    """m50: Bullroarer's weapons held the weight limit and a Staff of Trap Location was left. At the limit the cheapest
    item heavy enough is destroyed for loot worth 1.5x it (a Gnomish Shovel for the staff); a kit item never is."""
    def run(pack, weights):
        p = pilot(pack=pack)
        for it, wt in zip(p.w.items(), weights):
            it["weight"] = wt
        p.skipped_items, p.room_t, p.unique_drop = set(), 0.0, None
        p.flavour_of = lambda it: None
        p.weight_room = lambda: (20, 0)
        sent = []
        p.cmd = lambda line, why, hold=0.4: sent.append(why)
        p.c = type("C", (), {"send": lambda self, x: None})()
        p.pickup_room("a Staff of Trap Location (12 charges)")
        return sent
    shovel = run([("a Gnomish Shovel (1d2) (+0,+0) <+1>", 20), PHASE], [60, 10])
    kit = run([PHASE, ("3 Potions of Cure Critical Wounds", 75)], [10, 12])
    ok = len(shovel) == 1 and "Gnomish Shovel" in shovel[0] and kit == []
    return ok, f"with a shovel: {shovel}; kit only: {kit}"


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
def fullest_lantern_worn():
    """m39: '"0 turns" not in name' skipped the 13290-turn lantern (it ends in "0 turns"), the recall's light-on wore
    the 4383-turn one, and lantern_fuel (the max of all) hid it from the top-up; the worn one ran down to ~700 turns
    with the spare carried. The fullest is worn; a low worn lantern with no oil swaps to a fuller spare."""
    lamps = [("a Brass Lantern (with 4383 turns of light)", 39), ("a Brass Lantern (with 13290 turns of light)", 39)]
    p = pilot(pack=lamps)
    best = p.best_light()["name"]
    q = pilot(worn=[("a Brass Lantern (with 700 turns of light)", 39, 50)], pack=lamps[1:])
    q.light_t = q.busy_until = 0.0
    q.cmds = []
    q.cmd = lambda line, why, hold=0.4: q.cmds.append(why)
    q.keep_light(P.gnow())
    fuel = q.lantern_fuel()
    ok = "13290" in best and q.cmds and "swap to the fuller lantern" in q.cmds[0] and fuel == 700
    return ok, f"best {best}; low worn: {q.cmds}; fuel read {fuel}"


@case
def breeder_swarm_leaves():
    """m40: weak breeders (Giant fruit flies) were news once per level; they grew to 16 and boxed the Pilot in. At 8
    or more the notice comes again, not as news (the trip leaves on it)."""
    fly = next(r for r in RACES.values() if "MULTIPLY" in r.flags and r.level <= 10)
    p = pilot(monsters=[(20, 22 + k, fly) for k in range(3)])
    p.goal, p.breeder_level, p.w.clvl = None, None, 27
    notes = []
    p.notify = lambda what, d=None, news=False, action=True: notes.append((what, news))
    p.watch_breeders()
    p.w.monsters = [(20, 22 + k, fly) for k in range(9)]
    p.watch_breeders()
    p.watch_breeders()
    ok = notes == [("breeders", True), ("breeders", False)]
    return ok, f"{fly.name}: {notes}"


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
def floor_junk_destroyed_when_quiet():
    """The user (10-25): known junk underfoot (Salt Water...) is destroyed where it lies -- only when not in combat (no
    mobile monster in view, not hit for 5 s, HP fine, not fleeing/recalling) -- and left out of the Items line."""
    def make(mons=()):
        p = pilot(hp=265, monsters=list(mons))
        p.orders.update(junk="Salt Water,Weakness", autodestroy="worthless,cursed", think_hp=0.65)
        p.goal, p.busy_until = None, 0.0
        p.w.last_hit_t, p.w.recall_pending = 0.0, False
        p.flavour_of = lambda it: None
        p.sent, p.cmds = [], []
        p.c = type("C", (), {"send": lambda self, x: p.sent.append(x)})()
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(line)
        return p
    quiet = make()
    quiet.destroy_floor_junk("3 Potions of Salt Water", P.gnow())
    busy = make([(25, 25, BYNAME["cave orc"])])
    busy.destroy_floor_junk("a Potion of Salt Water", P.gnow())
    hit = make()
    hit.w.last_hit_t = P.gnow() - 2
    hit.destroy_floor_junk("a Potion of Salt Water", P.gnow())
    names = ["a Potion of Salt Water", "a Dagger {worthless}", "a Wand of Stinking Cloud", "a Broken Sword (1d2)"]
    kept = [n for n in names if not quiet.is_junk_name(n)]
    ok = quiet.cmds == ["custom k item=-11 value=3"] and "confirm yes" in quiet.sent and busy.cmds == [] and \
        hit.cmds == [] and kept == ["a Wand of Stinking Cloud"]
    return ok, f"quiet: {quiet.cmds}; an orc in view: {busy.cmds}; hit 2 s ago: {hit.cmds}; not junk: {kept}"


@case
def blind_cured_when_it_matters():
    """m43 23:20: blinded in a 10-monster band at 84% HP, nothing "near" can be seen blind -- it rested while unseen
    monsters bit it and the flee couldn't read. Blind is cured (cheapest first) when a band was warned in the last
    30 s, monsters were seen within 6 squares in the last 10 s, or an escape needs to read; not blind and alone."""
    def make(**kw):
        p = pilot(hp=274, pack=[("2 Potions of Cure Light Wounds", 75), ("5 Potions of Cure Critical Wounds", 75)])
        p.w.hp = [274, 326]
        p.w.in_dungeon = True
        p.w.flag = lambda k: k == "blind"
        p.w.adjacent_monsters = lambda: []
        p.w.last_hit_t = P.gnow() - 20
        p.w.damage_rate = lambda s: 0.0
        p.cure_t, p.goal = 0.0, None
        p.orders["think_hp"] = 0.65
        p.mons_mem = {}
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(why)
        for k, v in kw.items():
            setattr(p, k, v)
        return p
    band = make(band_warned=(1.0, 10), band_warned_t=P.gnow() - 5)
    band.status_tick(P.gnow(), [])
    seen = make(mons_mem={"Druid": {"level": 1.0, "pos": (22, 22), "n": 1, "t": P.gnow() - 3}})
    seen.status_tick(P.gnow(), [])
    alone = make()
    alone.status_tick(P.gnow(), [])
    # (m44: Light hounds re-blinding -- after 2 cures in 30 s it fights on blind)
    again = make(band_warned=(1.0, 10), band_warned_t=P.gnow() - 5, blind_cures=[P.gnow() - 10, P.gnow() - 4])
    again.status_tick(P.gnow(), [])
    ok = band.cmds and "Cure Light Wounds" in band.cmds[0] and seen.cmds and alone.cmds == [] and again.cmds == []
    return ok, f"band warned: {band.cmds}; a Druid seen 3 s ago: {seen.cmds}; alone: {alone.cmds}; 3rd in 30 s: " \
               f"{again.cmds}"


@case
def ask_price_and_buy_commas():
    """The user (m43): a live, rate-limited line from the Navigator to the Architect (`ask`, one per 5 min, 4 an hour;
    `answer` shows in the reports); `price` gives the Pilot's own valuation; buy specs split on commas outside [..]
    (m43's `[3,+6]` broke)."""
    import tempfile, re as _re
    p = pilot(pack=[("2 Staffs of Cure Light Wounds (21 charges)", 55)])
    p.rundir = tempfile.mkdtemp()
    p.req_role, p.ask_seq = "navigator", 0
    p.goal = None
    p.w.depth_ft = 700
    a1 = p.ask_architect("what are the Staffs of CLW worth?")
    a2 = p.ask_architect("again?")
    p.req_role = "architect"
    ans = p.answer_navigator(["1", "~218 each in town"])
    p.stores_seen = {}
    pr = p.price_info("Cure_Light")
    split = P.split_specs("2/pair_of_hard_leather_boot_[3,+6]@1050,Word_of_Recall:3")
    asks = open(os.path.join(p.rundir, "asks.jsonl")).read()
    ok = a1["ok"] and not a2["ok"] and "5 minutes" in a2["error"] and ans["ok"] and p.arch_answers and \
        "worth ~" in pr and "the policy:" in pr and split == ["2/pair_of_hard_leather_boot_[3,+6]@1050",
                                                              "Word_of_Recall:3"] and "Staffs of CLW" in asks
    return ok, f"ask: {a1.get('text', '')[:40]}; again: {a2.get('error', '')[:50]}; price: {pr.replace(chr(10), ' | ')}"


@case
def engage_nearby_monster_only_when_appropriate():
    """The user (m43): engage a nearby monster instead of walking on past it -- but never over the legit reasons not
    to (fleeing, a danger in view, low HP, a breeder). Exploring, a killable monster 4 steps off: engaged."""
    strong = next(r for r in sorted(RACES.values(), key=lambda r: (r.level, r.name)) if 15 <= r.level <= 25 and
                  "UNIQUE" not in r.flags and "NEVER_MOVE" not in r.flags and "MULTIPLY" not in r.flags)

    def make(goal, hp=300, mons=None, danger=None):
        p = pilot(hp=hp, monsters=mons if mons is not None else [(20, 24, strong)])
        p.w.hp = [hp, 326]
        p.w.in_dungeon, p.w.depth, p.w.clvl = True, 13, 27
        p.goal, p.plan = goal, None
        p.orders["think_hp"] = 0.65
        p.band_live = lambda: False
        p.our_slowness = lambda: 1.0
        p.w.recall_pending = False
        p.danger_why = lambda r: danger
        p.hunt_refusal = lambda name: (None, None)
        p.avoid_names = set()
        p.logs = []
        p.log = lambda kind, **kw: p.logs.append((kind, kw))
        p.mover = type("M", (), {"active": False, "path": [1, 2, 3], "go": lambda self, g, unknown=False: True,
                                 "tick": lambda self: "moving", "stop": lambda self: None})()
        return p
    explore = make(P.Explore())
    e = explore.engage_tick(P.gnow())
    flee = make(P.Flee("x"))
    f = flee.engage_tick(P.gnow())
    hurt = make(P.Explore(), hp=150)
    h = hurt.engage_tick(P.gnow())
    danger = make(P.Explore(), danger="breathes fire")
    d = danger.engage_tick(P.gnow())
    ok = e is True and explore.engage["target"] == strong.name and f is False and h is False and d is False
    return ok, f"{strong.name}: exploring {e}; fleeing {f}; at 46% HP {h}; a danger in view {d}"


@case
def trip_clock_condition_across_midnight():
    """m44: "time>00:26" set at 23:54 held at once (a string comparison: "23:54:41" > "00:26:00") and the trip came
    home on arrival. HH:MM is the next such moment after the plan started."""
    import time as _t
    pl = P.TripPlan.__new__(P.TripPlan)
    pl.t0 = P.gnow() - 60                    # (started a minute ago)
    now = _t.time()
    soon = _t.strftime("%H:%M", _t.localtime(now + 1800))     # 30 min from now (may be after midnight)
    past = _t.strftime("%H:%M", _t.localtime(now - 120))      # 2 min ago, before the start: tomorrow
    started_after = _t.strftime("%H:%M", _t.localtime(now - 30))
    t_soon, t_past = pl.clock_target(soon), pl.clock_target(past)
    ok = 1500 < t_soon - now < 1900 and t_past - now > 80000 and pl.clock_target(started_after) - now < 60
    return ok, f"{soon}: in {(t_soon - now) / 60:.0f} min; {past}: in {(t_past - now) / 3600:.1f} h"


@case
def tavern_stash_and_one_lantern():
    """The user (10-26): Restore potions and Wands of Stone to Mud (never aimed) stay in the tavern (8) during a
    mission -- deposited at the end of plan town, the matching Restore fetched for a drained stat instead of bought,
    stash kinds not picked up in town otherwise; and one lantern: a spare (not the fullest) is sold."""
    import tempfile
    p = pilot(pack=[("a Potion of Restore Dexterity", 75), ("2 Wands of Stone to Mud (21 charges)", 65),
                    ("a Brass Lantern (with 1977 turns of light)", 39), ("a Brass Lantern (with 14943 turns of light)", 39),
                    ("9 Potions of Cure Critical Wounds", 75)])
    p.rundir = tempfile.mkdtemp()
    p.w.depth, p.w.in_dungeon = 0, False
    p.w.memory = {(27, 89): "8", (27, 90): ".", (28, 90): "!"}
    p.flavour_of = lambda it: None
    stash = [i["name"] for i in p.w.items() if p.is_stash_item(i["name"])]
    ent = p.tavern_entrance()
    p.stash_add("a Potion of Restore Dexterity")
    p.seen_drained = {"DEX": (18, 38)}
    want_with = p.stash_wanted()
    p.w.inven = [i for i in p.w.inven if "Restore" not in i["name"]]
    want = p.stash_wanted()
    needs = [r[1] for r in p.town_needs(None, ())]
    lamps = {("1977" if "1977" in i["name"] else "14943"): p.town_sell_count(i) for i in p.w.items()
             if "Lantern" in i["name"]}
    ok = (stash == ["a Potion of Restore Dexterity", "2 Wands of Stone to Mud (21 charges)"] and ent == (27, 89)
          and want_with is None and want == "Restore Dexterity" and "Restore Dexterity" not in needs
          and lamps == {"1977": 1, "14943": 0})
    return ok, f"stash kinds {stash}; tavern {ent}; fetch {want!r}; buy list {needs}; lanterns sold {lamps}"


class _Stub:
    """A goal stand-in that never ends."""
    name = "stub"

    def tick(self, p):
        return None


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
def dive_loots_beside_its_path():
    """m49: leaving a breeders level, the dive walked past two gold piles beside its path to the stairs (it looted only
    before setting off). Walking, it now stops for loot within 3 squares, not for one 5 away, nor with a Stone troll
    in view."""
    def run(item_at, monsters=()):
        p = pilot(monsters=monsters)
        w = p.w
        w.depth, w.depth_ft, w.level_t, w.pos, w.clvl = 15, 750, P.gnow() - 300, (20, 20), 28
        w.standing_on, w.arrive_pos, w.arrived_by = None, (4, 150), ">"
        w.memory = {item_at: "$", (20, 40): ">"}
        w.find = lambda chars: [(20, 40)] if ">" in chars else []
        p.skipped_items, p.loot_mem = set(), {"level": w.level_t, "done": set(), "tries": collections.Counter(),
                                               "owed": set()}
        p.item_hold_until, p.dangers, p.interesting = 0, lambda: [], lambda: None
        p.danger_why = lambda r: None
        p.orders["loot_radius"], p.orders["pillared"], p.busy_until = 10, "no", 0
        p.orders["max_depth"] = 800
        p.loot_step = lambda st: looted.append(True) or True
        stopped, looted = [], []
        p.mover = type("M", (), {"active": True, "stop": lambda self: stopped.append(True) or setattr(self, "active", False),
                                 "tick": lambda self: "moving", "go": lambda self, t: True,
                                 "path": []})()
        p.kept, p.scummed, p.live, p.fled_from = set(), set(), False, None
        d = P.Dive(800)
        d.stop, d.level_seen, d.explore, d.probed = False, w.level_t, _Stub(), (w.level_t, w.pos)
        d.walking = True
        d.tick(p)
        return bool(stopped and looted)
    near, far = run((22, 21)), run((25, 21))
    troll = run((22, 21), monsters=[(30, 30, BYNAME["stone troll"])])
    return (near, far, troll) == (True, False, False), \
        f"stopped for loot 2 away {near}, 5 away {far}, a Stone troll in view {troll}"


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
def loadout_moves_free_action():
    """The loadout optimizer (m53's Holy Avenger Sabre, sold for losing Free Action): with a Ring of Free Action to
    buy, the Sabre + the ring in place of a Protection ring is searched; without the ring the Sabre never is (Free
    Action lost); a ring beyond the budget isn't either; a worse Protection ring is pruned."""
    import geareval as G
    worn = {}
    for n in G.DIVE04_WORN:
        it = G.Item(n)
        worn.setdefault(it.slot, []).append(it)
    ch = G.Character(28, {"STR": 88, "INT": 5, "WIS": 8, "DEX": 38, "CON": 38, "CHR": 4}, mhp=340, ac=76, worn=worn,
                     flags={"FREE_ACT", "SEE_INVIS", "RES_FIRE", "RES_COLD", "RES_ELEC", "RES_ACID", "RES_DARK"},
                     depth_ft=750)

    def run(with_ring, budget=5000):
        pool = [G.Item("a Sabre (Holy Avenger) (2d7) (+11,+7) [+2] (+1)"), G.Item("a Ring of Protection [+5]")]
        if with_ring:
            pool.append(G.Item("a Ring of Free Action"))
            pool[-1].price = 1500
        res = G.optimize(ch, pool, budget=budget, hard=False, depth_n=0)
        return [k for k in res["changes"] if k != "current"], res["searched"]
    a, sa = run(True)
    b, _ = run(False)
    c, _ = run(True, budget=1000)
    ok = any("Sabre" in k and "Free Action" in k for k in a) and not any("Sabre" in k for k in b + c) and \
        "ring" in sa["candidates"] and sa["candidates"]["ring"] == 1
    return ok, f"with the ring: {a}; without: {b}; under budget 1000: {c}; searched {sa}"


# a piece of Dive04's town (10-27): the 1-square house at 37-39,155-157 (door 38,155) and a 4-square one
_TOWN = {37: "....###....#....#", 38: "....0.#....#..0.", 39: "....###....####.."}


def _town_memory():
    mem = {}
    for y, row in _TOWN.items():
        for i, ch in enumerate(row):
            mem[(y, 151 + i)] = ch
    for y in (36, 40):
        for x in range(151, 168):
            mem[(y, x)] = "."
    return mem


@case
def house_bank_round_trip():
    """The gold bank (the user, 10-27): the smallest house on the map is found (door 38,155, step in at 38,156, stand
    at 38,154); a deposit walks in, closes the door, drops all but the float, walks out and closes it; a withdraw picks
    the pile up by stepping in. Simulated server: walks move, the drop takes the gold and leaves a pile."""
    houses = P.town_houses(_town_memory())
    h = houses[0] if houses else {}
    import tempfile
    p = pilot(gold=20300)
    w = p.w
    w.depth, w.in_dungeon, w.memory, w.pos = 0, False, _town_memory(), (38, 154)
    p.rundir, p.busy_until = tempfile.mkdtemp(), 0
    p._house = {"house": {k: (list(v) if isinstance(v, tuple) else v) for k, v in h.items() if k != "inside"},
                "banked": 0}
    pile, sent = [0], []
    dirs = {1: (1, -1), 2: (1, 0), 3: (1, 1), 4: (0, -1), 6: (0, 1), 7: (-1, -1), 8: (-1, 0), 9: (-1, 1)}

    def cmd(line, why, hold=0.4):
        sent.append(line)
        m = re.match(r"walk (\d)", line)
        if m:
            dy, dx = dirs[int(m.group(1))]
            w.pos = (w.pos[0] + dy, w.pos[1] + dx)
            if w.pos == tuple(h["step_in"]) and pile[0]:
                w.ind["gold"][0] += pile[0]
                pile[0] = 0
        m = re.match(r"custom \$ value=(\d+)", line)
        if m:
            w.ind["gold"][0] -= int(m.group(1))
            pile[0] += int(m.group(1))
            w.messages.append((P.gnow(), f"You drop {m.group(1)} pieces of gold."))
    p.cmd = cmd
    p.mover = type("M", (), {"active": False, "go": lambda self, t: True, "tick": lambda self: "arrived",
                             "stop": lambda self: None})()
    p.town_reserve = lambda: 1000

    def run(g):
        for _ in range(60):
            g.t = -99.0
            r = g.tick(p)
            if r:
                return r
    a = run(P.HouseBank("deposit"))
    after_dep = (w.ind["gold"][0], pile[0], p.banked(), w.pos)
    b = run(P.HouseBank("withdraw"))
    after_wd = (w.ind["gold"][0], pile[0], p.banked(), w.pos)
    ok = h.get("door") == (38, 155) and h.get("outside") == (38, 154) and h.get("step_in") == (38, 156) and \
        a and a[0] == "done" and after_dep == (300, 20000, 20000, (38, 154)) and \
        b and b[0] == "done" and after_wd == (20300, 0, 0, (38, 154)) and "custom c dir=4" in sent and \
        "custom c dir=6" in sent
    return ok, f"house {h.get('door')}/{h.get('step_in')}/{h.get('outside')}; deposit {a} -> {after_dep}; " \
               f"withdraw {b} -> {after_wd}; sent {sent[:8]}"


@case
def recall_cures_confusion_first():
    """m55: `goal recall` sat 4 minutes, confused by Hummerhorns, the read refused; the Navigator quaffed a CSW. Now
    the recall quaffs the cheapest cure first: confused -> Cure Serious (CLW doesn't end it); blind only -> CLW."""
    def run(state):
        p = pilot(pack=[("2 Scrolls of Word of Recall", 70), ("3 Potions of Cure Light Wounds", 75),
                        ("3 Potions of Cure Serious Wounds", 75), ("a Brass Lantern", P.TV_LITE)])
        p.w.inven[0]["equip"] = True
        p.w.inven[0]["tval"] = P.TV_LITE
        p.w.flag = lambda k: k == state
        p.w.recall_pending = False
        p.recall_t = 0.0
        sent = []
        p.cmd = lambda line, why, hold=0.4: sent.append(why)
        g = P.Recall()
        g.tick(p)
        return sent
    conf, blind, clear = run("confused"), run("blind"), run(None)
    ok = len(conf) == 1 and "Cure Serious" in conf[0] and len(blind) == 1 and "Cure Light" in blind[0] and \
        len(clear) == 1 and clear[0].startswith("read ")
    return ok, f"confused: {conf}; blind: {blind}; clear: {clear}"


@case
def confusion_lock_is_cured():
    """m55: Hummerhorns kept Dive04 confused for 15 minutes; the dive waited for it to wear off. After 8 s confused
    with monsters adjacent the Pilot quaffs Cure Serious (not before 8 s, not again within 8 s, at most 4 a level);
    an escape the game refused shows as FAILED, not LANDING."""
    p = pilot(pack=[("3 Potions of Cure Serious Wounds", 75), ("3 Potions of Cure Critical Wounds", 75)],
              monsters=[(20, 21, BYNAME["hummerhorn"])])
    p.w.flag = lambda k: k == "confused"
    p.w.adjacent_monsters = lambda: [(20, 21, BYNAME["hummerhorn"])]
    p.busy_until = 0
    sent = []
    p.cmd = lambda line, why, hold=0.4: sent.append(why)
    first = p.confusion_lock()
    p.conf_since -= 9
    second = p.confusion_lock()
    third = p.confusion_lock()
    p.escape_read_t, p.escape_from = P.gnow() - 1, ((20, 20), "a Staff of Teleportation")
    p.w.messages.append((P.gnow() - 0.5, "You failed to use the staff properly."))
    line = p.escape_line()
    ok = (first, second, third) == (False, True, False) and len(sent) == 1 and "Cure Serious" in sent[0] and \
        "FAILED" in line
    return ok, f"{first}, {second}, {third}: {sent}; {line!r}"


@case
def house_bank_in_the_wilderness():
    """The user (10-27): a small house just outside town (practice for the live server, where town houses cost 5x).
    A deposit from town walks to the edge square it was reached by, off the edge into the house's tile, banks, and
    walks back into town by the same edge."""
    import tempfile
    houses = P.town_houses(_town_memory())
    h = dict({k: (list(v) if isinstance(v, tuple) else v) for k, v in houses[0].items() if k != "inside"},
             depth=-1, cross={"town": [1, 130], "wild": [64, 130], "depth": -1})
    p = pilot(gold=10300)
    w = p.w
    w.depth, w.in_dungeon, w.memory, w.pos = 0, False, _town_memory(), (1, 130)
    p.rundir, p.busy_until = tempfile.mkdtemp(), 0
    p._house = {"house": h, "banked": 0}
    dirs = {2: (1, 0), 4: (0, -1), 6: (0, 1), 8: (-1, 0)}
    sent = []

    def cmd(line, why, hold=0.4):
        sent.append(line)
        m = re.match(r"walk (\d)", line)
        if m:
            if w.depth == 0 and w.pos == (1, 130) and m.group(1) == "8":
                w.depth, w.pos = -1, (38, 154)          # (the scripted tile: the house's outside square)
                return
            if w.depth == -1 and w.pos == (64, 130) and m.group(1) == "2":
                w.depth, w.pos = 0, (1, 130)
                return
            dy, dx = dirs.get(int(m.group(1)), (0, 0))
            w.pos = (w.pos[0] + dy, w.pos[1] + dx)
        m = re.match(r"custom \$ value=(\d+)", line)
        if m:
            w.ind["gold"][0] -= int(m.group(1))
            w.messages.append((P.gnow(), f"You drop {m.group(1)} pieces of gold."))
    p.cmd = cmd

    class M:
        active = False
        def go(self, t):
            w.pos = tuple(t[0])          # (the scripted walk arrives at once)
            return True
        def tick(self):
            return "arrived"
        def stop(self):
            pass
    p.mover = M()
    g = P.HouseBank("deposit")
    r = None
    for _ in range(80):
        g.t = -99.0
        r = g.tick(p)
        if r:
            break
    ok = r and r[0] == "done" and w.depth == 0 and w.pos == (1, 130) and p.banked() == 10000 and \
        sent.count("walk 8") == 1 and sent.count("walk 2") == 1
    return ok, f"{r}; depth {w.depth} at {w.pos}; banked {p.banked()}; sent {sent}"


@case
def house_keeps_the_stash():
    """The user (10-27): the stash moves into the house (a town monster took a wand off the tavern floor). In the
    4-square house (door 60,129) a deposit drops each stash stack on its own square away from the gold's (60,128),
    the gold on 60,128; a withdraw with STR drained fetches the Restore Strength from its square, gold too."""
    import tempfile
    mem = {}
    for x in range(124, 130):
        mem[(59, x)] = mem[(61, x)] = "#"
    mem[(60, 124)], mem[(60, 129)] = "#", "0"
    for x in range(125, 129):
        mem[(60, x)] = "."
    for y in range(57, 64):
        for x in range(130, 134):
            mem[(y, x)] = "."
    hs = P.town_houses(mem)
    h = {k: (list(v) if isinstance(v, tuple) else v) for k, v in hs[0].items() if k != "inside"}
    p = pilot(gold=5300, pack=[("2 Wands of Stone to Mud (21 charges)", 65), ("a Potion of Restore Strength", 75)])
    w = p.w
    w.depth, w.in_dungeon, w.memory, w.pos = 0, False, mem, (60, 130)
    p.rundir, p.busy_until = tempfile.mkdtemp(), 0
    p._house, p.stash = {"house": h, "banked": 0}, {"items": []}
    p.stash_save = lambda: None
    floor = {}
    dirs = {4: (0, -1), 6: (0, 1)}

    def cmd(line, why, hold=0.4):
        m = re.match(r"walk (\d)", line)
        if m:
            dy, dx = dirs[int(m.group(1))]
            w.pos = (w.pos[0] + dy, w.pos[1] + dx)
            if "$" in floor.get(w.pos, ""):
                w.ind["gold"][0] += int(floor.pop(w.pos)[1:])
        m = re.match(r"custom d item=(\d+)", line)
        if m:
            it = next(i for i in w.inven if i["item"] == int(m.group(1)))
            w.inven.remove(it)
            floor[w.pos] = it["name"]
        m = re.match(r"custom \$ value=(\d+)", line)
        if m:
            w.ind["gold"][0] -= int(m.group(1))
            floor[w.pos] = "$" + m.group(1)
            w.messages.append((P.gnow(), f"You drop {m.group(1)} pieces of gold."))
        if line == "custom ,":
            n = floor.pop(w.pos)
            w.inven.append({"item": 30, "name": n, "tval": 75, "weight": 4, "number": 1, "equip": False})
    p.cmd = cmd
    p.mover = type("M", (), {"active": False, "go": lambda self, t: True, "tick": lambda self: "arrived",
                             "stop": lambda self: None})()

    def run(g):
        for _ in range(80):
            g.t = -99.0
            r = g.tick(p)
            if r:
                return r
    a = run(P.HouseBank("deposit"))
    dep = dict(floor)
    p.seen_drained = {"STR": (58, 68)}
    b = run(P.HouseBank("withdraw"))
    ok = a and b and dep.get((60, 128)) == "$5000" and sorted(v for k, v in dep.items() if k != (60, 128)) == \
        ["2 Wands of Stone to Mud (21 charges)", "a Potion of Restore Strength"] and \
        any("Restore Strength" in i["name"] for i in w.items()) and w.ind["gold"][0] == 5300 and \
        list(floor.values()) == ["2 Wands of Stone to Mud (21 charges)"] and w.pos == (60, 130)
    return ok, f"deposit {a}: floor {dep}; withdraw {b}: floor {floor}; pack {[i['name'] for i in w.items()]}"


@case
def tavern_stash_drops_inside():
    """10-27: the tavern stash dropped from the entrance (27,89), which holds no object; the wands landed on the
    street (27,88, 28,88) and townsfolk with TAKE_ITEM took them. The user: the inside is walkable. Now each stash
    stack goes on an empty square inside the room, the farthest from the door first."""
    import tempfile
    mem = {}
    for x in range(89, 95):
        mem[(26, x)] = mem[(29, x)] = "#"
    for y in (27, 28):
        mem[(y, 94)] = "#"
        for x in range(90, 94):
            mem[(y, x)] = "."
    mem[(27, 89)], mem[(28, 89)] = "8", "#"
    for y in range(25, 31):
        mem[(y, 88)] = "."
    p = pilot(pack=[("2 Wands of Stone to Mud (21 charges)", 65), ("a Potion of Restore Dexterity", 75)])
    w = p.w
    w.depth, w.in_dungeon, w.memory, w.pos = 0, False, mem, (27, 88)
    p.rundir, p.busy_until = tempfile.mkdtemp(), 0
    p.stash = {"items": [], "entrance": [27, 89]}
    p.stash_save = lambda: None
    floor = {}

    def cmd(line, why, hold=0.4):
        m = re.match(r"custom d item=(\d+)", line)
        if m:
            it = next(i for i in w.inven if i["item"] == int(m.group(1)))
            w.inven.remove(it)
            floor[w.pos] = it["name"]
    p.cmd = cmd

    class M:
        active = False
        def go(self, t):
            w.pos = tuple(t[0])
            return True
        def tick(self):
            return "arrived"
    p.mover = M()
    g = P.StashDeposit()
    r = None
    for _ in range(30):
        g.t = -99.0
        r = g.tick(p)
        if r:
            break
    inside = all(26 < y < 29 and 89 < x < 94 for y, x in floor)
    ok = r and r[0] == "done" and len(floor) == 2 and inside and (28, 93) in floor
    return ok, f"{r}; dropped on {floor}"


@case
def ehp_counts_ac_hp_and_resists():
    """The user's EHP column (10-28): EHP = max HP x (damage with no AC/resists) / (damage with this gear), over the
    damage mix taken. More HP scales it exactly; AC helps only the melee share (status blows mostly miss already at AC
    76 vs level-13 attackers); a fire resist helps only the fire share; a mix of pure fire makes AC worthless."""
    import geareval as G
    base = dict(mhp=358, ac=76, flags={"RES_FIRE"})
    e0 = G.ehp(base)
    con = G.ehp(dict(base, mhp=416)) / e0 - 1
    ac = G.ehp(dict(base, ac=87)) / e0 - 1
    nofire = G.ehp(dict(base, flags=set())) / e0 - 1
    fire_only = {"fire": 1.0}
    ac_fire = G.ehp(dict(base, ac=150), fire_only, 13) / G.ehp(base, fire_only, 13) - 1
    ok = abs(con - 58 / 358) < 0.002 and 0.04 < ac < 0.15 and nofire < -0.05 and abs(ac_fire) < 1e-9
    return ok, f"EHP {e0:.0f}; +58 HP {con:+.1%}, +11 AC {ac:+.1%}, no fire resist {nofire:+.1%}, AC vs pure fire {ac_fire:+.1%}"


@case
def proxy_counts_resists_by_ehp():
    """The user (10-28): EHP feeds the optimizer's proxy. A Ring of Resist Fire for a Protection ring (-10 AC) ranks
    as a gain against the measured mix (13% fire) for a character without fire resistance, and as a loss against a
    melee-only mix."""
    import geareval as G
    worn = {}
    for n in ["Battle Axe of Westernesse (2d8) (+10,+9) (+1)", "Ring of Protection [+12]", "Ring of Protection [+10]",
              "Metal Scale Mail [38,+5]", "Shadow Cloak [6,+2]", "Orcish Shield [5,+4]", "Metal Cap [3,+4]"]:
        it = G.Item(n)
        worn.setdefault(it.slot, []).append(it)
    ch = G.Character(29, {"STR": 88, "INT": 5, "WIS": 8, "DEX": 38, "CON": 38, "CHR": 4}, mhp=358, ac=90, worn=worn,
                     flags={"FREE_ACT", "SEE_INVIS"}, depth_ft=750)
    cur = ch.derive()
    d = ch.derive(ch.swap(G.Item("a Ring of Resist Fire"), 1))
    fire = G.proxy(d, cur, 750, (G.DEFAULT_MIX, 13))
    melee = G.proxy(d, cur, 750, ({"hurt": 1.0}, 13))
    return fire > 0 > melee, f"proxy with the measured mix {fire:+.3f}, melee only {melee:+.3f}"


@case
def ehp_gate_and_tie_break():
    """The user (10-28): EHP in the verdict. A ring that adds damage but gives up a Protection ring's AC enough to cut
    EHP >5% is ruled out ("less staying power"); a smaller EHP cut isn't."""
    GE, ch = _dive04_character()
    res = GE.compare_slot(ch, [GE.Item("Ring of Damage (+0,+6)")], hard=False, depth_n=0)
    cut = {k: v for k, v in res["notes"].items() if any("staying power" in x for x in v)}
    e = res["ehp"]
    drops = {k: e[k] / e["current"] - 1 for k in e if k != "current"}
    ok = all((drops[k] < -GE.EHP_GATE) == (k in cut) for k in drops)
    return ok, f"EHP drops {', '.join(f'{v:+.1%}' for v in drops.values())}; ruled out by EHP: {len(cut)}"


@case
def plan_town_survives_the_house_tile():
    """m56 (the Opus Navigator's ask): plan town failed "plan town is for the town" once its HouseBank step walked to
    the house's wilderness tile (depth -1). Under a HouseBank step it carries on; elsewhere off town it still fails."""
    p = pilot()
    p.w.depth, p.w.in_dungeon = -1, False
    k = P.TownKit()
    k.counted = True
    k.sub = type("HB", (P.HouseBank,), {"tick": lambda self, p: None})("withdraw")
    a = k.tick(p)
    k.sub = None
    b = k.tick(p)
    return a is None and b and b[0] == "failed", f"under the house step: {a}; without it: {b}"


@case
def house_walk_stops_at_the_crossing():
    """m56: from town, the walk to the edge kept running on the house's tile (toward the town square's coordinates),
    passed the house's outside square, and the bank opened the door from 10 squares off. A level change stops the walk;
    reaching the outside square stops it too."""
    import tempfile
    h = {"door": [60, 129], "step_in": [60, 128], "outside": [60, 130], "box": [59, 124, 61, 129], "depth": -1,
         "cross": {"town": [1, 130], "wild": [64, 130], "depth": -1}}
    p = pilot()
    w = p.w
    w.depth, w.in_dungeon, w.pos, w.level_t = -1, False, (63, 130), P.gnow()
    p.rundir, p.busy_until, p._house = tempfile.mkdtemp(), 0, {"house": h, "banked": 0}
    stops = []
    p.mover = type("M", (), {"active": True, "go": lambda self, t: True, "tick": lambda self: "moving",
                             "stop": lambda self: stops.append(w.pos)})()
    p.cmd = lambda line, why, hold=0.4: None
    g = P.HouseBank("deposit")
    g.seen_level = w.level_t - 5            # (it started in town)
    g.t = -99.0
    g.tick(p)
    first = list(stops)
    w.pos = (60, 130)
    g.t = -99.0
    g.tick(p)
    ok = first == [(63, 130)] and stops[-1] == (60, 130) and g.step == "open"
    return ok, f"stops at {stops}; step {g.step}"


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
def trip_dmin_counts_dungeon_minutes():
    """m57: `minutes>30` counted the town visit and the recall down, and ended the trip early. `dmin` counts from the
    trip's first moment in the dungeon (0 in town)."""
    p = pilot()
    tp = P.TripPlan(700, 800, P.TripPlan.parse_until("dmin>20"))
    tp.t0 -= 600
    p.w.in_dungeon = False
    town = tp.value(p, "dmin")
    p.w.in_dungeon = True
    tp.value(p, "minutes")
    tp.dungeon_t0 -= 21 * 60
    later = tp.value(p, "dmin")
    ok = town == 0 and 20.9 < later < 21.1 and tp.value(p, "minutes") > 9.9
    return ok, f"in town {town}; 21 min after arriving {later:.1f}; minutes {tp.value(p, 'minutes'):.1f}"


@case
def empty_devices_recharged_or_sold():
    """m56: an empty Staff of Perception was carried all mission. The user (10-28): recharge it rather than sell it. An
    empty useful staff is kept when a Scroll of Recharging would refill it at <=15% risk of destroying it (Perception,
    level 10: 1 in 10; the town kit then recharges it), sold when the risk is higher (Healing, level 70: 1 in 6); the
    keep list matches plural stacks ("staff of teleportation" vs "2 Staffs of Teleportation")."""
    p = pilot(pack=[("a Staff of Perception (0 charges)", 55), ("a Staff of Healing (0 charges)", 55),
                    ("2 Staffs of Teleportation (0 charges)", 55)])
    p.keep = {"staff of teleportation"}
    p.flavour_of = lambda it: None
    p.town_buyers = lambda it: [5]
    p.unknown_flavour = lambda it: False
    got = [p.town_sell_count(it) for it in p.w.items()]
    want = [i["name"] for i in p.recharge_wanted()]
    risk = round(p.recharge_fail(p.w.items()[0]), 3)
    return got == [0, 1, 0] and want[:1] == ["a Staff of Perception (0 charges)"] and risk == 0.1, \
        f"sell counts {got}; recharge {want}; Perception risk {risk}"


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
def supply_minutes_and_quiet_cap():
    """The user (10-28): the Navigator should know how long food and light last. Food (reserves counted, slow
    digestion halves it) and light (lantern + flasks) in dungeon minutes; a reminder under 15 and 5 minutes; a quiet
    wait capped at a quarter of what's left."""
    p = pilot(pack=[("3 Rations of Food", P.TV_FOOD), ("2 Flasks of oil", P.TV_FLASK)],
              worn=[("a Spear (1d6) (+5,+7)", 22, 50), ("a Brass Lantern (with 2150 turns of light)", P.TV_LITE, 50)])
    p.w.hunger = 3
    for it in p.w.items():
        if it["tval"] == P.TV_FLASK:
            it["number"] = 2
    p.w.flags["slow_digest"] = 1
    slow = p.supply_minutes()
    p.w.flags["slow_digest"] = 0
    fast = p.supply_minutes()
    p.supply_told = set()
    p.w.items = lambda **k: [i for i in p.w.inven if i["equip"] == k.get("equip", False)
                             and (k.get("tval") is None or i["tval"] == k["tval"]) and i["tval"] != P.TV_FLASK]
    for it in p.w.inven:
        if it["tval"] == P.TV_LITE:
            it["name"] = "a Brass Lantern (with 900 turns of light)"
    p.supply_watch()
    told = [d for what, d in p.notes if what == "supplies"]
    g = P.QuietWait(600)
    p.mover = type("M", (), {"active": False, "go": lambda self, t: False, "tick": lambda self: "arrived",
                             "stop": lambda self: None})()
    p.quiet_spot, p.w.last_hit_t, p.w.pos, p.cmd = (lambda: None), 0.0, (20, 20), (lambda *a, **k: None)
    g.tick(p)
    ok = abs(slow[0] - (6000 + 15000 - 1000) / 215) < 1 and abs(fast[0] - slow[0] / 2) < 1 and \
        abs(slow[1] - (2150 + 15000) / 215) < 1 and len(told) == 1 and "light" in told[0] and g.secs < 600
    return ok, f"slow digestion {slow[0]:.0f}/{slow[1]:.0f} min, normal {fast[0]:.0f}; told {told}; quiet {g.secs} s"


@case
def enchant_armour_to_the_stopping_place():
    """The user (10-28): undo disenchantment, stopping where the failure chance says. spells2.c: +1 succeeds with
    1 - table[to_a]/1000 (always below +0); enchant while the next point is >= 50% (+7 -> +8 is the last), the likeliest
    first; the scrolls wanted = the expected count to get every piece there."""
    p = pilot(worn=[("a Shadow Cloak [6,-6]", 35, 10), ("a Set of Gauntlets [2,-1]", 31, 25),
                    ("a Metal Cap [3,+2]", 32, 20), ("a Pair of Hard Leather Boots of Stability [3,+7]", 30, 40),
                    ("Hard Studded Leather of Resistance (-1) [7,+8]", 37, 100)])
    p.is_artifact = lambda n: False
    ch = {it["name"]: p.enchant_chance(it) for it in p.w.items(equip=True)}
    plan = [it["name"] for it, c in p.enchant_plan()]
    n = p.enchant_scrolls_wanted()
    # cloak -6..+7: 6 sure points to +0, then +0..+7 = 1/1 + 1/.99 + 1/.95 + 1/.9 + 1/.8 + 1/.7 + 1/.6 + 1/.5
    tail = sum(1 / (1 - t / 1000) for t in p.ENCHANT_TABLE[:8])
    want = (6 + tail) + (1 + tail) + sum(1 / (1 - t / 1000) for t in p.ENCHANT_TABLE[2:8]) + 2.0
    ok = ch["a Shadow Cloak [6,-6]"] == 1.0 and abs(ch["a Pair of Hard Leather Boots of Stability [3,+7]"] - 0.5) < 1e-9 \
        and abs(ch["Hard Studded Leather of Resistance (-1) [7,+8]"] - 0.3) < 1e-9 and \
        "Hard Studded Leather of Resistance (-1) [7,+8]" not in plan and plan[-1].startswith("a Pair of Hard Leather") \
        and abs(n - want) < 0.01
    return ok, f"chances {ch}; plan {plan}; scrolls wanted {n:.1f} (expected {want:.1f})"


@case
def town_waits_for_restock():
    """The user (10-28): shops restock every ~30 s -- wait for what's critically needed. A supply-gate essential missing
    because the shop was out (or a Restore for a drained STR/DEX/CON): up to 4 waits of 35 s, then it goes on; nothing
    missing: no wait."""
    def run(gap, drained=False):
        p = pilot()
        p.seen_drained = {"STR": (58, 68)} if drained else {}
        p.w.depth, p.w.in_dungeon = 0, False
        p.upgrade_step = lambda: False
        p.restore_potion = lambda skip=(): None
        p.provision_step = lambda k: False
        p.supply_gate = lambda depth, recall: list(gap)
        p.planned_depth = lambda: 750
        p.recharge_wanted = lambda: []
        p.enchant_plan = lambda: []
        p.house_state = lambda: {}
        p.stash_has = lambda k: False
        p.busy_until, p.pending_use = 0, None
        k = P.TownKit()
        k.counted, k.withdrawn, k.fetched = True, True, True
        k.done_log = ["5: no Word of Recall in stock"]
        waits = 0
        for _ in range(8):
            k.stage, k.queue, k.sub, k.t = "buying", [], None, -99.0
            k.tick(p)
            if isinstance(k.sub, P.Wait):
                waits += 1
            elif k.sub is None:
                break
        return waits
    missing, fine, restore = run(["Word of Recall x2"]), run([]), run([], drained=True)
    return (missing, fine, restore) == (4, 0, 4), \
        f"waits with WoR missing {missing}; with nothing missing {fine}; STR drained, no Restore {restore}"


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


def _trip_on_level(p, tp):
    p.goal = None
    p.set_goal = lambda g: setattr(p, "goal", g)
    p.use_stair_location = lambda why: False
    p.band_live = lambda: False
    p.w.find = lambda chars: []
    p.w.arrived_by = ">"
    tp.tick(p)
    return p.goal


@case
def trip_level_state_survives_restart():
    """m45 00:33: a hot-swap on a 700 ft level that felt special (an orc pit) lost "find stairs first" -- the new Pilot
    saw a new level_t, no feeling message, and explored the pit. plan.json now keeps this level's state; a restart on
    the same depth carries on with it (stairs first again; not one more level; its time on it kept)."""
    import tempfile
    p = pilot(pack=[("2 Scrolls of Word of Recall", 70), ("9 Potions of Cure Critical Wounds", 75)])
    p.rundir = tempfile.mkdtemp()
    p.w.depth, p.w.depth_ft, p.w.level_t = 14, 700, P.gnow() - 20
    p.w.messages.append((p.w.level_t + 1, "You feel there is something special about this level."))
    tp = P.TripPlan(650, 750, P.TripPlan.parse_until("minutes>60"))
    tp.phase, tp.went_down, tp.levels = "level", True, 2
    g1 = _trip_on_level(p, tp)
    tp.level_t0 -= 90
    tp.save(p)
    p.w.level_t = P.gnow() - 2                   # (the new process: the same level, a new level_t, no messages)
    p.w.messages.clear()
    tp2 = P.TripPlan.load(p)
    g2 = _trip_on_level(p, tp2)
    on = round(P.gnow() - tp2.level_t0)
    ok = isinstance(g1, P.Explore) and g1.until == "stairs" and isinstance(g2, P.Explore) and g2.until == "stairs" \
        and tp2.levels == 3 and 85 <= on <= 95
    return ok, f"before: {g1 and g1.describe()}; after the restart: {g2 and g2.describe()}, levels {tp2.levels}, " \
               f"{on} s on the level"


@case
def trip_recalls_when_a_level_wont_let_go():
    """m45: 13 minutes trying to leave 750 ft (breeders) -- the stuck watchdog doesn't count fighting, and the quiet
    rule only shortens explorations. After LEAVE_MAX on a finished level the trip recalls home; not while the
    Navigator's own goal has the plan paused."""
    p = pilot(pack=[("2 Scrolls of Word of Recall", 70)])
    p.w.depth, p.w.depth_ft, p.w.level_t = 15, 750, P.gnow() - 600
    tp = P.TripPlan(650, 750, P.TripPlan.parse_until("minutes>60"))
    tp.phase, tp.went_down, tp.levels = "level", True, 3
    tp.level, tp.level_t0, tp.level_done = p.w.level_t, P.gnow() - 500, "left: breeders"
    p.goal = tp.mark(P.Dive(700))
    p.set_goal = lambda g: setattr(p, "goal", g)
    p.band_live = lambda: False
    tp.tick(p)
    first = tp.phase
    tp.leave_since = (p.w.level_t, P.gnow() - tp.LEAVE_MAX - 5)
    tp.paused = True
    tp.tick(p)
    paused = tp.phase
    tp.paused = False
    tp.tick(p)
    resumed = tp.phase
    tp.leave_since = (p.w.level_t, P.gnow() - tp.LEAVE_MAX - 5)
    tp.tick(p)
    ok = first == paused == resumed == "level" and tp.phase == "home" and "couldn't leave 750 ft" in tp.home_why
    return ok, f"phases {first}/{paused}/{resumed} -> {tp.phase}: {tp.home_why}"


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


def _dive04_character():
    import geareval as GE
    worn = {}
    for n in GE.DIVE04_WORN:
        it = GE.Item(n)
        worn.setdefault(it.slot, []).append(it)
    return GE, GE.Character(28, {"STR": 88, "INT": 5, "WIS": 8, "DEX": 38, "CON": 38, "CHR": 4}, mhp=340, ac=76,
                            worn=worn, flags={"FREE_ACT", "SEE_INVIS", "RES_FIRE", "RES_COLD", "RES_ELEC", "RES_ACID",
                                              "RES_DARK"}, depth_ft=750, inv=dict(ccw=20, phase=18, wor=2))


@case
def gear_items_parsed_from_names():
    """The gear evaluator reads items from the names the client shows, with the game's data files: kind, ego or
    artifact, dice, plusses, AC, pval, abilities (the Battle Axe of Westernesse once read as an artifact)."""
    import geareval as GE
    ax = GE.Item("Battle Axe of Westernesse (2d8) (+10,+9) (+1)")
    arm = GE.Item("Hard Studded Leather of Resistance (-1) [7,+8]")
    ring = GE.Item("Ring of Protection [+12]")
    st = GE.Item("Ring of Strength (+2)")
    ing = GE.Item("the Amulet of Ingwe")
    lamp = GE.Item("Brass Lantern (with 14943 turns of light)")
    ok = (ax.slot == "weapon" and ax.weight == 170 and (ax.to_h, ax.to_d, ax.pval) == (10, 9, 1) and
          ax.abilities() == {"FREE_ACT", "SEE_INVIS"} and ax.stat_bonus() == {"STR": 1, "DEX": 1, "CON": 1} and
          arm.slot == "body" and (arm.ac, arm.to_a, arm.to_h) == (7, 8, -1) and
          arm.abilities() == {"RES_ACID", "RES_ELEC", "RES_FIRE", "RES_COLD"} and ring.to_a == 12 and
          st.stat_bonus() == {"STR": 2} and ing.art and "FREE_ACT" in ing.abilities() and lamp.pval == 0)
    return ok, f"axe {ax.weight} {ax.abilities()} {ax.stat_bonus()}; armour {arm.ac},{arm.to_a},{arm.to_h} " \
               f"{sorted(arm.abilities())}; Ingwe {bool(ing.art)}"


@case
def gear_model_matches_dive04_sheet():
    """Dive04's sheet (10-26: STR 18/70, 2 blows, AC 76, 340 HP) from its worn gear; a Ring of Strength (+2) makes
    STR 18/90 and still 2 blows with the 17 lb axe (the m45 question: the Protection ring's 10-12 AC is worth more)."""
    GE, ch = _dive04_character()
    d = ch.derive()
    d2 = ch.derive(ch.swap(GE.Item("Ring of Strength (+2)"), 1))
    ok = ch.check() == [] and d["blows"] == 2 and d["ac"] == 76 and d["mhp"] == 340 and \
        d2["stats"]["STR"] == 108 and d2["blows"] == 2 and d2["ac"] == 66 and d2["dmg"] > d["dmg"]
    return ok, f"check {ch.check()}; now blows {d['blows']} ~{d['dmg']}/round AC {d['ac']}; with STR+2: " \
               f"STR {d2['stats']['STR']} blows {d2['blows']} ~{d2['dmg']}/round AC {d2['ac']}"


@case
def gear_evaluator_no_loss_rules():
    """The Pilot's automatic swaps never lose Free Action, See Invisible, resist blindness/confusion or hold life
    (geareval.NO_LOSS); other resists only with TRADE_RESISTS (off until the user decides: they're simulated since
    options_sim 26f). A plain axe that loses Free Action is vetoed in any case (REQUIRED). With no simulation sets the
    verdict keeps the current gear (no measured gain). With resists traded, the plain mail is still ruled out: it cuts
    EHP by 6% (the EHP gate, the user 10-28: the lost fire resist outweighs 28 AC against the damage taken)."""
    GE, ch = _dive04_character()
    mail_it = GE.Item("Metal Scale Mail [38,+5]")
    res = GE.compare_slot(ch, [mail_it], hard=False, depth_n=0, no_loss=True)      # (TRADE_RESISTS off: the default)
    GE.TRADE_RESISTS = True
    try:
        res_t = GE.compare_slot(ch, [mail_it], hard=False, depth_n=0, no_loss=True)
    finally:
        GE.TRADE_RESISTS = False
    res2 = GE.compare_slot(ch, [GE.Item("Battle Axe (2d8) (+20,+20)")], hard=False, depth_n=0)
    mail = res["options"][1]
    ok = res["best"] == "current" and any("resist acid" in x for x in res["notes"][mail]) and \
        len(res_t["notes"][mail]) == 1 and "EHP" in res_t["notes"][mail][0] and res2["best"] == "current" and \
        any("Free Action" in x for x in res2["notes"][res2["options"][1]])
    return ok, f"mail: {res['notes'][mail]}; trading resists: {res_t['notes'][mail]}; " \
               f"plain axe: {res2['notes'][res2['options'][1]]}"


@case
def gear_optimizer_same_loss_rule_as_verdict():
    """A6: the optimizer proposes only loadouts the verdict's no_loss rule allows (one predicate, auto_swap_losses):
    a Ring of Slaying in place of the Ring of Strength loses its sustain and looks better on paper, but isn't
    simulated; in place of a Ring of Protection it is (no sustain lost)."""
    GE, ch = _dive04_character()
    strength = GE.Item("Ring of Strength (+2)")
    ch.worn["ring"] = [ch.worn["ring"][0], strength]
    slaying = GE.Item("a Ring of Slaying (+4,+6)")
    bad = ch.swap(slaying, 1)                                   # (for the Ring of Strength: loses SUST_STR)
    bad_proxy = GE.proxy(ch.derive(bad), ch.derive(), ch.depth_ft)
    res = GE.optimize(ch, [slaying], hard=False, depth_n=0)
    labels = res["options"][1:]
    never = [k for k in labels if any("automatic swap never does" in x for x in res["notes"][k])]
    ok = bad_proxy > 0 and GE.auto_swap_losses(ch.derive()["flags"], ch.derive(bad)["flags"]) == ["SUST_STR"] and \
        not never and labels and not any("for Ring of Strength" in k for k in labels) and \
        any("for Ring of Protection" in k for k in labels)
    return ok, f"the swap for Strength: proxy {bad_proxy:+.3f}; simulated: {labels}; ruled out for a loss: {never}"


@case
def gear_score_rests_and_paired_error():
    """The score counts the turns to rest back the HP lost (regenhp, resting x2, game time: ~2 HP a block at 340 HP); the paired standard
    error of a difference is 0 for identical options."""
    import geareval as GE
    rt = GE.rest_turns(100, 340)
    rows = [dict(xp=10.0 * k, turns=5 + k, rest=1.0, spent=0.0, lows=[0.9], dead=0) for k in range(1, 6)]
    g, se = GE.paired_gain(rows, rows, 0.41)
    # encumbrance: STR 18/70 carries 300 lb (adj_str_wgt 30 x 100 tenth-pounds); over 150 lb, -1 speed per 30 lb
    GE2, ch = _dive04_character()
    worn_wt = sum(i.weight for v in ch.worn.values() for i in v)
    ch.pack_weight = 1750 - worn_wt          # (175 lb carried: under the next 30 lb step; the mail adds 14 lb)
    heavy = ch.derive(ch.swap(GE.Item("Metal Scale Mail [38,+5]")))
    res = GE.compare_slot(ch, [GE.Item("Metal Scale Mail [38,+5]")], hard=False, depth_n=0)
    slow = any("slower" in x for x in res["notes"][res["options"][1]])
    ok = 45 < rt < 52 and g == 0 and se == 0 and ch.derive()["speed"] == 0 and heavy["speed"] < 0 and slow
    return ok, f"100 HP of 340: {rt:.1f} turns; identical options: gain {g}, SE {se}; 175 lb carried: speed " \
               f"{ch.derive()['speed']}, with a 25 lb mail {heavy['speed']} (ruled out: {slow})"


@case
def rations_by_need_and_heavy_loot_left():
    """Rations by need (the user, 10-31; was "never destroyed", after m46/m47): Fed with the trip ending in 2 minutes,
    all 3 are spare (worth their sale price); Hungry with 60 minutes to go, all are needed and worth the dungeon time
    they buy. And m46's six weapons (speed -1): loot that would cross the weight limit's slow-down line (weapons,
    armour, staffs) is left unless worth 300+ gold."""
    p = pilot(pack=[("3 Rations of Food", P.TV_FOOD), ("a Rod of Trap Location", 66)])
    p.w.in_dungeon, p.w.hunger, p.w.flags = True, 3, {}
    p.trip_minutes_left = lambda: 2
    p.flavour_of = lambda it: None
    p.rates = {"buckets": []}
    rations = p.w.items()[0]
    n3, v3 = p.destroy_count(rations), p.pack_value(rations)
    p.w.hunger = 2
    p.trip_minutes_left = lambda: 60
    n_need, v_need = p.destroy_count(rations), p.pack_value(rations)
    # the weight limit: STR 18/70 (88) carries 150 lb before slowing
    q = pilot(pack=[("a Lucerne Hammer (2d5)", 22)])
    q.w.ind["stat0"] = [88]
    for i in q.w.inven:
        i["weight"] = 1450 if not i["equip"] else 0    # (145 lb carried)
    room, slow = q.weight_room()
    q.unique_drop, q.skipped_items, q.room_t = None, set(), 0.0
    took_heavy = q.pickup_room("a Lucerne Hammer (2d5)")
    q.w.pos = (20, 21)
    q.pickup_room("a Lucerne Hammer (2d5)")          # (walking past it: said once per level, m47 said it 9 times)
    said = sum(1 for n in q.notes if "Lucerne" in str(n[1]))
    took_light = q.pickup_room("a Potion of Cure Critical Wounds")
    for i in q.w.inven:
        i["weight"] = 1460 if not i["equip"] else 0    # (146 lb: 4 lb to spare, a 5 lb staff crosses the line)
    took_staff = q.pickup_room("a Staff of Light")
    for i in q.w.inven:
        i["weight"] = 1450 if not i["equip"] else 0
    ok = n3 == 3 and v3 < 10 and n_need == 3 and v_need > 1000 and took_staff is False and room == 50 and slow == 0 and took_heavy is False and took_light is True and said == 1
    return ok, f"3 rations, Fed, 2 min left: destroy {n3} (~{v3:.0f}); Hungry, 60 min left: {n_need} (~{v_need:.0f}); " \
               f"a staff taken {took_staff}; 145 lb carried: {room / 10:.0f} lb to spare, " \
               f"a Lucerne Hammer taken {took_heavy}, a potion {took_light}"


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


@case
def food_warning_and_trip_rate():
    """m46-m47 Navigators: "Food 0" came with no warning, and they wanted XP a minute per trip. Now news once per trip
    when the pack holds no food in the dungeon, and the trip plan keeps its XP base (persisted for hot-swaps)."""
    p = pilot(pack=[("9 Potions of Cure Critical Wounds", 75)])
    p.c = object()
    p.w.ind["hunger"] = [3]
    p.plan = type("Pl", (), {"t0": 5.0})()
    p.food_watch()
    p.food_watch()
    warned = [d for w, d in p.notes if w == "supply"]
    tp = P.TripPlan(650, 750, P.TripPlan.parse_until("minutes>30"))
    ok = len(warned) == 1 and "no food" in warned[0] and "xp0" in P.TripPlan.STATE and getattr(tp, "xp0", None) is None
    return ok, f"warnings {warned}"


@case
def navigator_rules_review_and_nopickup():
    """The user (10-26, the Navigator empowerment list): executable standing orders (`rule leave NAME` acts at Pilot
    speed; `rule thieves kill` hunts a thief in view), the item-review queue (an identified wearable with an ability is
    held, not sold, until the Navigator decides; released after 2 town visits), and `order nopickup=`."""
    import tempfile
    warg, rogue = BYNAME["warg"], BYNAME["novice rogue"]
    p = pilot(monsters=[(20, 25, warg)])
    p.rundir = tempfile.mkdtemp()
    p.goal, p.plan = None, None
    p.set_goal = lambda g: setattr(p, "goal", g)
    p.nav_rules = [{"kind": "leave", "arg": "warg", "by": "navigator"}]
    acted = p.rule_tick(100.0)
    left = isinstance(p.goal, P.Flee)
    again = p.rule_tick(101.0)
    q = pilot(monsters=[(20, 24, rogue)])
    q.rundir, q.goal, q.plan = p.rundir, None, None
    q.nav_rules = [{"kind": "thieves", "arg": "kill", "by": "navigator"}]
    q.danger_why = lambda r: None
    asked = []
    q.do_request = lambda req: asked.append(req["args"]) or {"ok": True}
    hunted = q.rule_tick(100.0)
    r = pilot(pack=[("an Amulet of Resist Lightning", 40)])
    r.rundir = tempfile.mkdtemp()
    amu = r.w.items()[0]
    held = r.review_hold(amu)
    r.review_state()["town_visits"] += 2
    released = r.review_hold(amu)
    r.orders["nopickup"] = "Lance,Pike"
    r.unique_drop, r.skipped_items, r.room_t = None, set(), 0.0
    lance = r.pickup_room("a Lance (2d8)")
    ok = acted and left and not again and hunted and asked == [["hunt", "Novice_rogue"]] and held is True and \
        released is False and lance is False
    return ok, f"leave: {acted}/{left}, again {again}; thief hunt {asked}; review held {held}, after 2 visits " \
               f"{released}; Lance picked up {lance}"


@case
def confusion_window_teleports():
    """M5 (10-28): each cure bought ~1 s before the next Hummerhorn bite. Cured (0.3-4 s ago), clear, 3+ adjacent: the
    staff (or a scroll) teleports us away, once a cure; not with fewer adjacent, not while still confused."""
    def run(adj, confused=False, ago=1.0):
        p = pilot(pack=[("a Staff of Teleportation (12 charges)", 55)])
        p.w.adjacent_monsters = lambda: [(20, 21, BYNAME["hummerhorn"])] * adj
        p.w.flag = lambda k: confused and k == "confused"
        p.busy_until, p.conf_cure_t = 0, P.gnow() - ago
        sent = []
        p.cmd = lambda line, why, hold=0.4: sent.append(line)
        first = p.confusion_window()
        again = p.confusion_window()
        return first, again, sent
    a, b, c = run(5), run(2), run(5, confused=True)
    ok = a[0] and not a[1] and a[2] == ["custom u item=0"] and not b[0] and not c[0]
    return ok, f"5 adjacent {a}; 2 adjacent {b[0]}; still confused {c[0]}"


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
def asleep_flags_from_look_answers():
    """The per-monster asleep flag (the user, 10-26): the client's `look N` answers ("A Warg (unhurt, asleep) [r,...]"
    at the monster's screen square) mark monsters asleep or awake, by position, else by name; the report says so."""
    warg, wolf = BYNAME["warg"], BYNAME["wolf"]
    p = pilot(monsters=[(20, 25, warg), (22, 26, wolf), (18, 30, warg)])
    p.log = lambda *a, **k: None
    p.w.targets = [(P.gnow(), 20, 25, "A Warg (unhurt, asleep) [r,t,p,o,+,-,<dir>]"),
                   (P.gnow(), 99, 99, "A Wolf (unhurt) [r,t,p,o,+,-,<dir>]"),
                   (P.gnow(), 18, 30, "A Warg (somewhat wounded, asleep, afraid) [r,...]")]
    p.read_looks()
    flags = (p.is_asleep(20, 25), p.is_asleep(22, 26), p.is_asleep(18, 30))
    ok = flags == (True, False, True)
    return ok, f"asleep flags {flags}"


@case
def breeder_swarm_pin_teleports_once():
    """m45 (fleas) and m48 (lice): a dive leaving a breeder level got pinned in the swarm (stuck notices) until
    LEAVE_MAX's recall. Now the first stuck notice on such a level reads/uses a teleport, once per level."""
    p = pilot(pack=[("a Staff of Teleportation (6 charges)", 55)])
    p.w.level_t = 7.0
    tp = P.TripPlan(700, 800, P.TripPlan.parse_until("minutes>30"))
    tp.phase, tp.level, tp.level_done = "level", 7.0, "left: breeders"
    sent = []
    p.cmd = lambda c, why, hold=0: sent.append(c)
    tp.on_event(p, "stuck", "'dive 800ft' hasn't moved", False)
    tp.on_event(p, "stuck", "'dive 800ft' hasn't moved", False)
    tp2 = P.TripPlan(700, 800, P.TripPlan.parse_until("minutes>30"))
    tp2.phase, tp2.level, tp2.level_done = "level", 7.0, "left: a band"
    tp2.on_event(p, "stuck", "x", False)
    ok = sent == ["custom u item=0"]
    return ok, f"sent {sent}"


@case
def blind_escape_uses_the_staff_and_sees_refused_reads():
    """m48 (750 ft, 13 Light hounds re-blinding): a Word of Recall read 0.14 s before the blinding was refused ("You
    can't see anything.") and the Pilot waited 8 s and wouldn't retry; a Teleportation scroll later failed the same way;
    the Staff of Teleportation (usable blind) only came when the Navigator forced it. Now: blind -> the staff; a refused
    read is seen at once, the escape timers reset, and the staff is preferred for 10 s."""
    p = pilot(pack=[("a Scroll of Teleportation", 70), ("a Staff of Teleportation (5 charges)", 55)])
    p.w.flag = lambda k: False
    seeing = p.teleport_item()
    p.w.flag = lambda k: k == "blind"
    blind = p.teleport_item()
    p.w.flag = lambda k: False
    p.pending_use = {"t": P.gnow() - 1, "core": "Word of Recall", "why": "group danger", "tries": 0}
    p.dead, p.w.ghost = False, False
    p.escape_read_t, p.recall_t = P.gnow() - 1, P.gnow() - 1
    p.w.messages.append((P.gnow() - 0.5, "You can't see anything."))
    p.verify_use()
    after = p.teleport_item()
    ok = seeing[0] == "r" and blind[0] == "u" and p.pending_use is None and p.escape_read_t < 0 and \
        p.recall_t == 0.0 and after[0] == "u" and any("refused" in str(d) for _, d in p.notes)
    return ok, f"seeing: {seeing[0]}; blind: {blind[0]}; after a refused read: {after[0]}; pending {p.pending_use}"


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
def flavour_no_more_matches_type():
    """refactor-candidates A2: "You have no more Scrolls of Identify." paired with a vanished unknown amulet
    (runs/flavours.json: "Amber Amulet" = "Scroll of Identify"). Only an unknown of X's type pairs; learn_flavour
    refuses a flavour and kind whose type words differ."""
    import tempfile

    def run(unknown, said):
        p = pilot()
        p.flavour_file = os.path.join(tempfile.mkdtemp(), "flavours.json")
        p.id_target = None
        p.flavour_watch = {"t": P.gnow() - 2, "before": {unknown}, "unknown": {unknown}}
        p.w.messages.append((P.gnow(), said))
        p.learn_flavours_tick(P.gnow())
        return p.flavours
    amulet = run((40, "Amber Amulet"), "You have no more Scrolls of Identify.")
    scroll = run((70, 'Scroll titled "foo bar"'), "You have no more Scrolls of Light.")
    q = pilot()
    q.flavour_file = os.path.join(tempfile.mkdtemp(), "flavours.json")
    q.learn_flavour("Amber Amulet", "Scroll of Identify", "test")
    ok = amulet == {} and scroll.get('Scroll titled "foo bar"', {}).get("kind") == "Scroll of Light" and \
        q.flavours == {}
    return ok, f"amulet + no more Identify: {amulet}; scroll + no more Light: {scroll}; direct mismatch: {q.flavours}"


@case
def review_wear_says_what_happens():
    """refactor-candidates A11: `review wear NAME` in the dungeon is kept, not worn (`wear` is for town), and the reply
    says so; in town it's worn now."""
    import tempfile
    out = []
    for dungeon in (True, False):
        name = "a Ring of Protection [+10]"
        p = pilot(pack=[(name, 45)])
        p.w.in_dungeon = dungeon
        p.rundir = tempfile.mkdtemp()
        p.stale_order = lambda c, a: None
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(line)
        p.review_state()["items"][name] = {"why": "test", "visit": 0, "t": ""}
        r = p.do_request({"cmd": "review", "args": ["wear", "protection"]})
        out.append((r.get("text", r.get("error")), p.review_state()["decided"].get(name), p.cmds))
    (dt, dd, dc), (tt, td, tc) = out
    ok = "NOT worn" in dt and dd == "keep" and dc == [] and "wearing it now" in tt and td == "keep" and \
        tc == ["custom w item=0"]
    return ok, f"dungeon: {dt!r} {dd} {dc}; town: {tt!r} {td} {tc}"


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
    """A4 (session 10): every `emergency` notice in pilot.py says whether it reports an escape action (action=True or
    False), so a new non-action notice can't count towards the emergency loop by default."""
    import ast
    tree = ast.parse(open(os.path.join(HERE, "..", "pilot", "pilot.py")).read())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "notify"
             and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == "emergency"]
    bad = [n.lineno for n in calls if not any(k.arg == "action" for k in n.keywords)]
    return bool(calls) and not bad, f"{len(calls)} emergency notices; without action=: {bad}"


@case
def autodestroy_spares_kept_items():
    """A15 (session 10): the pseudo-ID pass of auto_destroy never destroys an item on the keep list; an unkept
    {cursed} item still goes."""
    def run(keep):
        p = pilot(pack=[("a Dagger (1d4) {cursed}", 23)])
        p.orders.update(autodestroy="cursed,worthless", junk="")
        p.keep = set(keep)
        p.busy_until, p.autodestroy_t = 0.0, -99.0
        p.c = types.SimpleNamespace(send=lambda *a: None)
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(line)
        p.auto_destroy(P.gnow())
        return p.cmds
    kept, unkept = run({"dagger"}), run(set())
    return kept == [] and len(unkept) == 1 and unkept[0].startswith("custom k"), f"kept: {kept}; not kept: {unkept}"


@case
def trip_until_wor_guard():
    """A18 (session 10): `until` refuses wor<2 and wor<=1 (they hold with the one Word of Recall kept for coming
    home) and lets wor<1 and wor<=0 through."""
    out = {}
    for cond in ("wor<2", "wor<=1", "wor<1", "wor<=0"):
        p = pilot()
        try:
            r = p.request_trip(["500-650", "until", cond])
        except Exception:            # (past the guard, the fixture lacks the plan's state: not refused here)
            r = {}
        out[cond] = "holds as soon as" in str(r.get("error", ""))
    return out == {"wor<2": True, "wor<=1": True, "wor<1": False, "wor<=0": False}, f"refused: {out}"


@case
def failed_hunt_never_counts_as_slain():
    """A23 (session 10): a hunt that failed with "killed" in its detail is wrong (fight debt), not slain."""
    import tempfile
    p = pilot(hp=100)
    p.w.hp = [100, 300]
    p.debt, p.debt_path = {}, os.path.join(tempfile.mkdtemp(), "debt.json")
    p.fight_debt_total = lambda: sum(e["hp"] for e in p.debt.get("fight_entries", []))
    g = types.SimpleNamespace(target="Grip", overridden={"hp0": 300, "hp_min": 100, "emerg0": 0, "why": "test"})
    P.Pilot.settle_hunt(p, g, "failed", "killed by nothing: it fled")
    return len(p.debt.get("fight_entries", [])) == 1, f"fight entries: {p.debt.get('fight_entries')}"


@case
def autodestroy_junk_kinds_without_feelings():
    """A16 (session 10): `order autodestroy=` (empty) turns off only the pseudo-ID pass; a kind on the junk order is
    still destroyed."""
    p = pilot(pack=[("a Potion of Salt Water", 75), ("a Dagger (1d4) {cursed}", 23)])
    p.orders.update(autodestroy="", junk="Salt Water")
    p.keep, p.busy_until, p.autodestroy_t = set(), 0.0, -99.0
    p.c = types.SimpleNamespace(send=lambda *a: None)
    p.cmds = []
    p.cmd = lambda line, why, hold=0.4: p.cmds.append((line, why))
    first = p.auto_destroy(P.gnow()), list(p.cmds)
    p.w.inven = [i for i in p.w.inven if "Salt" not in i["name"]]
    p.w.inven_dirty, p.autodestroy_t, p.cmds = False, -99.0, []
    second = p.auto_destroy(P.gnow()), list(p.cmds)
    return first[0] and "Salt Water" in first[1][0][1] and second == (False, []), f"{first}; then {second}"


@case
def mushrooms_by_expected_value():
    """A17 + the user (10-31): a mushroom the flavour table knows as junk is worth 0; an unknown one is worth the
    average value of the mushroom kinds not yet known (x the shop pay cut), less once valuable kinds are known; a known
    Mushroom of Restoring its kind's value. None is priceless as food."""
    p = pilot()
    junk = {"item": 0, "name": "a Black Spotted Mushroom", "tval": 80, "number": 1, "equip": False}
    unknown = {"item": 1, "name": "a Grey Mushroom", "tval": 80, "number": 1, "equip": False}
    known = {"item": 2, "name": "a Mushroom of Restoring", "tval": 80, "number": 1, "equip": False}
    p.flavour_of = lambda it: {"junk": True} if "Black" in it["name"] else None
    p.is_kit_item = lambda it: False
    p.ability_sources = set()
    p.review_state = lambda: {"items": {}}
    vj, vu, vk = p.pack_value(junk), p.pack_value(unknown), p.pack_value(known)
    p.flavours = {"Pink Mushroom": {"kind": "Mushroom of Restoring"}}
    vu2 = p.pack_value(unknown)
    return vj == 0 and 0 < vu < float("inf") and vu2 < vu and vk > vu, \
        f"junk {vj}, unknown {vu:.0f} (Restoring known: {vu2:.0f}), Restoring {vk:.0f}"


@case
def torch_light_is_not_permanent():
    """A19 (session 10): a worn Wooden Torch counts its turns (and spare torches'), an artifact light is permanent."""
    def light(worn, pack=()):
        p = pilot(worn=[worn], pack=list(pack))
        p.w.hunger, p.w.flags = 3, {}
        return p.supply_minutes()[1]
    torch = light(("a Wooden Torch (with 2150 turns) (1 turn)", 39, 30),
                  [("a Wooden Torch (with 5000 turns)", 39)])
    art = light(("the Phial of Galadriel", 39, 10))
    return torch is not None and abs(torch - 7150 / P.Pilot.TURNS_PER_DMIN) < 0.01 and art is None, \
        f"torch {torch}, artifact {art}"


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
def oil_by_need_and_fuel_before_destroying():
    """Oil by need (the user, 10-31): a full lantern and the trip ending soon: 3 flasks are spare; a lantern at 2000
    turns and 60 minutes to go: two flasks are needed (~56 dungeon minutes short), one is spare. Pack full: the lantern is
    filled from a stack of flasks before anything is destroyed (once it can take a whole flask)."""
    def setup(turns, left):
        p = pilot(worn=[("a Brass Lantern (with %d turns) (7 turns)" % turns, P.TV_LITE, 50)],
                  pack=[("3 Flasks of oil", P.TV_FLASK)] + [("a Scroll of Light", 70)] * 22)
        p.w.in_dungeon, p.w.hunger, p.w.flags = True, 3, {}
        p.trip_minutes_left = lambda: left
        p.flavour_of = lambda it: None
        p.rates = {"buckets": []}
        return p
    p = setup(15000, 2)
    flasks = p.w.items()[0]
    full = p.destroy_count(flasks), round(p.pack_value(flasks))
    p = setup(2000, 60)
    flasks = p.w.items()[0]
    low = p.destroy_count(flasks), round(p.pack_value(flasks))
    p.unique_drop, p.skipped_items, p.room_t = None, set(), 0.0
    p.c = types.SimpleNamespace(send=lambda *a: None)
    p.cmds = []
    p.cmd = lambda line, why, hold=0.4: p.cmds.append(line)
    p.pickup_room("a Wand of Stone to Mud (5 charges)")
    return full[0] == 3 and full[1] < 50 and low[0] == 1 and low[1] < 50 and p.cmds[:1] == ["custom F item=0"], \
        f"full lantern, 2 min: destroy {full}; 2000 turns, 60 min: destroy {low}; pack full: {p.cmds[:1]}"


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


@case
def pickup_none_no_loot_walks():
    """A5 (session 10): order pickup=none: loot_step makes no walk to the item 5 squares off (pickup=all does)."""
    def run(pickup):
        p = pilot()
        p.w.memory = {(20, 20): ".", (20, 25): "-"}
        p.orders.update(loot_radius=10, pickup=pickup)
        p.skipped_items = set()
        p.mover = _Mover()
        return p.loot_step({}), p.mover.went
    none, all_ = run("none"), run("all")
    return none == (False, []) and all_[0] and all_[1] == [[(20, 25)]], f"none: {none}; all: {all_}"


@case
def rings_of_damage_and_accuracy():
    """A13 (session 10): a lone (+n) on a Ring of Damage/Accuracy is its to-dam/to-hit (object1.c), not a pval;
    a Ring of Strength's (+3) stays a pval."""
    import geareval
    got = [(i.to_h, i.to_d, i.pval) for i in (geareval.Item(n, tval=45) for n in (
        "a Ring of Damage (+6)", "a Ring of Accuracy (+8)", "a Ring of Strength (+3)"))]
    return got == [(0, 6, 0), (8, 0, 0), (0, 0, 3)], f"{got}"


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else ""
    fails = ran = 0
    for f in CASES:
        if want and want not in f.__name__:
            continue
        ran += 1
        try:
            ok, detail = f()
        except Exception as e:
            ok, detail = False, f"error {e!r}"
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'} {f.__name__}: {detail}")
    print(f"{ran - fails} passed, {fails} failed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
