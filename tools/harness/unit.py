"""unit -- the harness's U-kind set-pieces: the Pilot's decision code on constructed states, no server.

Restructure step 4 (the Advisor's set-piece memo: U = a unit test on a constructed state). Run after any
Pilot or rulebook change:

    python3 unit.py            # every case; exit status 1 if one fails
    python3 unit.py hunt       # the cases whose name contains "hunt"
"""
import collections
import json
import os
import re
import sys
import time

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

    @property
    def hp_frac(self):
        return self.hp[0] / self.hp[1]

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
    p.notify = lambda what, d=None, news=False: p.notes.append((what, d))
    p.ability_seen_t = 0
    p.emerg_times = []
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
def unique_drop_feeling():
    """{good - Brodda, the Easterling} reads as a {good} feeling (unidentified)."""
    v = itemvalue.value("a Pair of Metal Shod Boots [6] {good - Brodda, the Easterling}", 13)
    return v.known is False and v.pseudo == "good", f"known={v.known} pseudo={v.pseudo}"


@case
def junk_kinds_from_rulebook():
    """The rulebook's junk kinds are the 38 of the old kinds.csv."""
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
    """Dive04's pack after m23: WoR to 2 first, Restore CON before the kit's extras, the kit's CSW/Phase/flasks."""
    pack = [("3 Rations of Food", 80), ("3 Flasks of oil", 77), ("2 Potions of Cure Serious Wounds", 75),
            ("6 Potions of Cure Critical Wounds", 75), ("9 Scrolls of Phase Door", 70),
            ("a Scroll of Word of Recall {@R650}", 70), ("a Brass Lantern (with 6370 turns of light)", 39)]
    w = W(pack=pack, gold=637)
    w.depth, w.depth_ft, w.in_dungeon = 0, 0, False
    p = pilot(w)
    p.seen_drained = {"CON": (17, 18)}
    need = [(t, k, n) for t, k, s, n, c in p.town_needs(None, ())]
    want = [(1, "Word of Recall", 1), (3, "Restore Constitution", 1), (4, "Cure Serious Wounds", 2),
            (4, "Phase Door", 1), (4, "Flask of oil", 2), (4, "Ration of Food", 1)]   # (food 3 of kit B's 4)
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


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else ""
    fails = 0
    for f in CASES:
        if want and want not in f.__name__:
            continue
        try:
            ok, detail = f()
        except Exception as e:
            ok, detail = False, f"error {e!r}"
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'} {f.__name__}: {detail}")
    print(f"{len(CASES) - fails if not want else ''} passed, {fails} failed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
