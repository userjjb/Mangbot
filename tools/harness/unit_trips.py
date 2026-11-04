"""unit_trips -- unit cases: Trips, supplies, clocks.

Run by unit.py (python3 unit.py [NAME]); W, pilot() and the other shared fixtures are in fixtures.py.
"""
import time
import types

from fixtures import P, case, pilot, pilot_ast


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
def e1_supply_gate():
    """E1: going down to 650 ft with 1 CLW, 2 Phase and 1 WoR is refused with what's missing."""
    p = pilot(pack=[("a Potion of Cure Light Wounds", 75), ("2 Scrolls of Phase Door", 70),
                    ("a Scroll of Word of Recall", 70)], worn=[("a Spear (1d6) (+5,+7)", 22, 50),
                                                              ("a Brass Lantern (with 9000 turns of light)", 39, 50)])
    gap = p.supply_gate(650, True)
    want = ("cure potions", "CSW+CCW", "Phase Door", "Word of Recall")
    return all(any(w_ in g for g in gap) for w_ in want), f"{gap}"


@case
def provisions_one_food_no_oil():
    """The user (10-25): food AND Satisfy Hunger, flasks by the handful. One food source (rations), eaten to Full
    in town; the lantern filled in town (flasks bought for it, then used: 2.49.0, to full -- was to 9000; 2000 turns
    buys 2, 12000 one); no oil carried. Near a trip's end the spare rations and flasks go first when loot needs
    room; in town the flask the 12000-turn lantern doesn't need is sold."""
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
    one = [(t, k, n) for t, k, s, n, c in full.town_needs("C", ()) if k == "Flask of oil"]
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
    sold = pv.town_sell_count(it["2 Flasks of oil"])
    ok = flasks == [(2, "Flask of oil", 2)] and one == [(2, "Flask of oil", 1)] and sold == 1 and \
        first.startswith("custom F") and \
        second.startswith("eat") and third is False and kept and len(cheap) == 3 and spare and \
        "a Piece of Elvish Waybread" in sells and "2 Flasks of oil" in sells and "3 Rations of Food" not in sells
    return ok, (f"lantern 2000: buy {flasks}; 12000: {one} (of 2 carried, {sold} sold); town step: {first!r}, then "
                f"{second!r}, then Full: "
                f"{third}; rations kept {kept}; worth their price: {cheap}; recall pending, rations kept for room: {spare}; "
                f"town sells {sells}")


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
def supply_minutes_and_quiet_cap():
    """The user (10-28): the Navigator should know how long food and light last. Food (reserves counted, slow
    digestion halves it) and light (lantern + flasks) in dungeon minutes; a reminder under 15 and 5 minutes; a quiet
    wait capped at a quarter of what's left. (2.48.1: the stomach at the bottom of its level -- Fed 2000 -- not its
    middle: m61's "food ~23 dungeon min" stood still while Fed and ran out.)"""
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
    ok = abs(slow[0] - (2000 + 15000 - 1000) / 215) < 1 and abs(fast[0] - slow[0] / 2) < 1 and \
        abs(slow[1] - (2150 + 15000) / 215) < 1 and len(told) == 1 and "light" in told[0] and g.secs < 600
    return ok, f"slow digestion {slow[0]:.0f}/{slow[1]:.0f} min, normal {fast[0]:.0f}; told {told}; quiet {g.secs} s"


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
def food_warning_and_trip_rate():
    """m46-m47 Navigators: "Food 0" came with no warning, and they wanted XP a minute per trip. Now news once per trip
    when the pack holds no food in the dungeon, and the trip plan keeps its XP base (persisted for hot-swaps)."""
    p = pilot(pack=[("9 Potions of Cure Critical Wounds", 75)])
    p.c = object()
    p.w.ind["hunger"] = [3]
    p.plan = type("Pl", (), {"t0": 5.0})()
    p.supply_minutes = lambda: (60.0, None)       # (D14: the food notice is supply_watch's now, kind `supplies`)
    p.supply_watch()
    p.supply_watch()
    warned = [d for w, d in p.notes if w == "supplies"]
    tp = P.TripPlan(650, 750, P.TripPlan.parse_until("minutes>30"))
    ok = len(warned) == 1 and "no food" in warned[0] and "xp0" in P.TripPlan.STATE and getattr(tp, "xp0", None) is None
    return ok, f"warnings {warned}"


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
def supplies_one_kind_with_fields():
    """D14 (the Advisor agreed, 11-01): the supply notices are one kind, `supplies`, with fields supply (food|light;
    `what` is the record's kind) and level (low|out|recalling) on the attention event and its decisions.jsonl record;
    the old kinds low_supply and supply are gone (every `supplies` notify passes fields); food_watch is merged into
    supply_watch."""
    import ast
    import threading
    tree = pilot_ast()
    kinds = [(n.args[0].value, n) for n in ast.walk(tree) if isinstance(n, ast.Call) and
             getattr(n.func, "attr", None) == "notify" and n.args and isinstance(n.args[0], ast.Constant)]
    old = [k for k, _ in kinds if k in ("low_supply", "supply")]
    bare = [n.lineno for k, n in kinds if k == "supplies" and not any(x.arg == "fields" for x in n.keywords)]
    p = pilot(pack=[("9 Potions of Cure Critical Wounds", 75)])
    p.notify = P.Pilot.notify.__get__(p)
    p.held_t, p.goal, p.news, p.attention, p.att_cond = 0.0, None, [], [], threading.Condition()
    logs = []
    p.log = lambda kind, **k: logs.append(dict(k, kind=kind))
    p.light_warned_key, p.light_warned = None, 0.0
    p.warn_light("lantern out", "the lantern is out")
    p.w.ind["hunger"] = [3]
    p.supply_minutes = lambda: (4.0, 30.0)
    p.supply_watch()
    got = [(r.get("supply"), r.get("level")) for r in logs if r["kind"] == "attention"]
    evs = [(e.get("supply"), e.get("level")) for e in p.attention + p.news]
    ok = not old and not bare and not hasattr(P.Pilot, "food_watch") and \
        got == [("light", "out"), ("food", "out"), ("food", "low")] and sorted(evs) == sorted(got) and \
        all(r["what"] == "supplies" for r in logs) and all(e["what"] == "supplies" for e in p.attention + p.news)
    return ok, f"old kinds {old}; supplies without fields at {bare}; records {got}; events {evs}"


@case
def lantern_filled_in_town():
    """2.49.0 (the user): `plan town` buys the Flasks of oil that fill the lantern and fills it to full after the buys
    (was: to 9000). FUEL_LAMP 15000, a flask 7500, the refill capped at the top (cmd3.c:1365-1374): 9050 turns buys 1
    flask and fills to 15000; 2000 buys 2 (9500, then 15000); a lantern within FILL_SLACK of full buys none. The sell
    rule agrees: at 9050 with 3 flasks carried, 2 are sold and 1 kept for the fill."""
    def make(turns, pack=()):
        p = pilot(pack=list(pack) + [("3 Rations of Food", 80)],
                  worn=[(f"a Brass Lantern (with {turns} turns of light)", P.TV_LITE, 50)])
        p.w.depth, p.w.depth_ft, p.w.in_dungeon = 0, 0, False
        p.w.ind["hunger"] = [3]
        p.plan, p.w.recall_pending = None, False
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(line)
        p.flavour_of = lambda it: None
        return p

    def fill(turns):
        """The buys, then provision_step to the end, the server's refill rule applied to each `custom F`."""
        p = make(turns)
        n = sum(r[3] for r in p.town_needs("C", ()) if r[1] == "Flask of oil")
        if n:
            p.w.inven.append({"item": 9, "name": f"{n} Flasks of oil" if n > 1 else "a Flask of oil", "tval": 77,
                              "weight": 10, "equip": False, "number": n})
        kit, fuels = P.TownKit("C"), [turns]
        for _ in range(5):
            p.cmds.clear()
            if not p.provision_step(kit) or not p.cmds[-1].startswith("custom F"):
                break
            fuels.append(min(p.FUEL_LAMP, fuels[-1] + p.FLASK_FUEL))         # (cmd3.c:1365-1374)
            lamp = next(i for i in p.w.inven if i["equip"] and i["tval"] == P.TV_LITE)
            lamp["name"] = f"a Brass Lantern (with {fuels[-1]} turns of light)"
            fl = next(i for i in p.w.inven if i["tval"] == 77)
            fl["number"] -= 1
            if not fl["number"]:
                p.w.inven.remove(fl)
        return n, fuels
    a, b, c = fill(9050), fill(2000), fill(14800)
    s = make(9050, pack=[("3 Flasks of oil", 77)])
    sold = s.town_sell_count(next(i for i in s.w.inven if i["tval"] == 77))
    ok = a == (1, [9050, 15000]) and b == (2, [2000, 9500, 15000]) and c == (0, [14800]) and sold == 2
    return ok, f"9050: {a}; 2000: {b}; 14800: {c} (flasks bought, the fuel after each fill); 9050 with 3: {sold} sold"


def _stomach(level=3, now=0.0, fuel=None, depth=6):
    st = P.Stomach(215)
    st.update(level, now, fuel=fuel, depth=depth)
    return st


@case
def stomach_pinned_by_hunger_crossings():
    """2.49.0 (the user): the stomach tracker. The server digests a food tick every 10 turns of a burning light's fuel
    (dungeon.c:1111-1152, 1183-1492): 20 food at normal speed, 10 with slow digestion, 40 at +10 speed (tables.c:2171);
    none in town unless Gorged (100). A Fed -> Hungry crossing pins the food just under 2000; then 2 dungeon minutes
    (430 turns of fuel: 43 ticks) digest 860, 430 slowly, 1720 hasted; a ration eaten (the pack shows one fewer) adds
    5000 and the indicator's rise to Fed is the meal's; a Scroll of Satisfy Hunger sets 14999 (use-obj.c:943). Without
    a light the clock widens the range (the bottom at 215 turns a dungeon minute, the top at the server's slowest). An
    unexplained rise re-widens to the level's bounds."""
    def _up(st, *a, **k):
        k.setdefault("depth", 6)
        return st.update(*a, **k)
    out = {}
    st = _stomach(3, 0.0, fuel=9000)
    _up(st, 2, 1.0, fuel=8990)                       # (1 tick of fuel; the indicator falls: pinned)
    out["pin"] = (st.lo, st.hi, st.exact(2))
    for name, kw in (("normal", {}), ("slow", {"slow": True}), ("speed", {"speed": 10})):
        s2 = _stomach(3, 0.0, fuel=9000)
        s2.lo = s2.hi = 6000
        _up(s2, 3, 120.0, fuel=9000 - 430, **kw)        # (2 dungeon minutes of fuel)
        out[name] = (6000 - s2.lo, 6000 - s2.hi)
    # a ration: sent (3 in the pack), the indicator rises before the pack shows it; then the pack
    pack = {"Ration of Food": 3}
    st.sent("Ration of Food", 3, ("add", 5000, 5000), 2.0)
    _up(st, 3, 2.5, fuel=8990, count_of=pack.get)    # (rise, meal unconfirmed: waits)
    waited = (st.level, st.lo)
    pack["Ration of Food"] = 2
    _up(st, 3, 3.0, fuel=8990, count_of=pack.get)
    _up(st, 3, 6.0, fuel=8990, count_of=pack.get)
    out["ration"] = (waited, st.lo, st.hi, st.exact(3))
    st.sent("Scroll of Satisfy Hunger", 1, ("set", 14999), 7.0)
    _up(st, 4, 7.5, fuel=8990, count_of=lambda k: 0)
    _up(st, 4, 10.0, fuel=8990, count_of=lambda k: 0)
    out["satisfy"] = (st.lo, st.hi)
    town = _stomach(3, 0.0, fuel=9000, depth=0)
    town.lo = town.hi = 5000
    town.update(3, 600.0, fuel=9000 - 960, depth=0)
    gorged = _stomach(5, 0.0, fuel=9000, depth=0)
    gorged.lo = gorged.hi = 16000
    gorged.update(5, 60.0, fuel=9000 - 100, depth=0)
    out["town"] = (town.lo, gorged.lo)
    clock = _stomach(3, 0.0)
    clock.lo = clock.hi = 6000
    _up(clock, 3, 60.0)                               # (no light: 1 game minute)
    out["clock"] = (round(6000 - clock.lo), round(6000 - clock.hi))
    _up(clock, 4, 61.0)                               # (a rise with no meal)
    out["unexplained"] = (clock.lo, clock.hi, clock.how)
    ok = out["pin"] == (1980, 1999, True) and out["normal"] == (860, 860) and out["slow"] == (430, 430) and \
        out["speed"] == (1720, 1720) and out["ration"] == ((2, 1980), 6980, 6999, True) and \
        out["satisfy"] == (14999, 14999) and out["town"] == (5000, 15000) and out["clock"] == (430, 191) and \
        out["unexplained"] == (10000, 14999, "unknown")
    return ok, f"{out}"


@case
def stomach_through_the_pilot():
    """2.49.0: the Pilot's side of the tracker -- the hunger indicator and the worn lantern's fuel each tick
    (stomach_tick), the meal from its own `eat` command once the pack shows one fewer ration (stomach_sent), the
    status text `food ~N` once pinned (`>=N` before), the eat-for-room check on the tracker's top (a ration eaten for
    room at a pinned 3500 -- the level's top, 10000, refused it), and the tracker's range saved to rundir/stomach.json
    and carried over a restart."""
    import tempfile
    import items as I
    clock = [1000.0]
    real = I.gnow
    I.gnow = lambda: clock[0]
    try:
        p = pilot(pack=[("3 Rations of Food", P.TV_FOOD), ("a Strip of Beef Jerky", P.TV_FOOD)] +
                  [(f"{n} Potions of Cure Critical Wounds", 75) for n in range(2, 24)],
                  worn=[("a Spear (1d6) (+5,+7)", 22, 50), ("a Brass Lantern (with 9000 turns of light)", P.TV_LITE, 50)])
        p.rundir = tempfile.mkdtemp()
        p.w.ind["hunger"] = [3]
        p.flavour_of = lambda it: None
        lamp = next(i for i in p.w.inven if i["tval"] == P.TV_LITE)
        p.stomach_tick(clock[0])
        before = p.supply_text()
        clock[0] += 1
        lamp["name"] = "a Brass Lantern (with 8990 turns of light)"
        p.w.ind["hunger"] = [2]
        p.stomach_tick(clock[0])
        pinned = (p.food_now(), p.food_top(), p.supply_text())
        # the Jerky (1500): sent, then the pack and the indicator show it
        p.c = types.SimpleNamespace(send=lambda *a: None)
        jerky = next(i for i in p.w.inven if "Jerky" in i["name"])
        p.stomach_sent(f"eat {jerky['item']}")
        p.w.inven.remove(jerky)
        clock[0] += 1
        p.w.ind["hunger"] = [3]
        p.stomach_tick(clock[0])
        clock[0] += 3
        p.stomach_tick(clock[0])
        fed = (p.food_now(), p.food_top())
        # pack full: a ration eaten for room at the pinned 3480-3499 (3499 + 5000 < 14000), refused at the level's top
        p.skipped_items, p.room_t, p.unique_drop = set(), 0.0, None
        sent = []
        p.cmd = lambda line, why, hold=0.4: sent.append(why)
        p.pickup_room("a Scroll of Enchant Weapon To-Dam")
        room = any("make room: eat" in x for x in sent)
        q = pilot(pack=[(i["name"], i["tval"]) for i in p.w.items()])
        q.w.ind["hunger"] = [3]
        q.flavour_of, q.skipped_items, q.room_t, q.unique_drop = (lambda it: None), set(), 0.0, None
        sent2 = []
        q.cmd = lambda line, why, hold=0.4: sent2.append(why)
        q.c = p.c
        q.pickup_room("a Scroll of Enchant Weapon To-Dam")
        room_unknown = any("make room: eat" in x for x in sent2)
        # a restart: the saved range, the bottom digested for the wall time since (none: just now)
        p.stomach_saved_t = 0.0
        p.stomach_tick(clock[0])
        r = pilot()
        r.w.ind["hunger"] = [3]
        import json as _j
        import os as _o
        r.stomach.from_json(_j.load(open(_o.path.join(p.rundir, "stomach.json"))))
        r.stomach_tick(clock[0])
        carried = (round(r.food_now()), r.food_top())
    finally:
        I.gnow = real
        import shutil
        shutil.rmtree(p.rundir, ignore_errors=True)
    ok = before.startswith("food >=41 ") and pinned[:2] == (1980, 1999) and pinned[2].startswith("food ~41 ") and \
        fed == (3480, 3499) and room and not room_unknown and carried[1] == 3499 and 3470 <= carried[0] <= 3480
    return ok, (f"before: {before!r}; pinned: {pinned}; after the Jerky: {fed}; eaten for room: pinned {room}, "
                f"unknown {room_unknown}; after a restart: {carried}")


@case
def rations_kept_by_a_pinned_stomach():
    """2.49.0 (the user's rations by need, made precise): make-room may destroy the rations the horizon doesn't need
    (the trip's 20 minutes left + SUPPLY_MARGIN_DMIN 5 = 25 dungeon minutes, 430 food a minute). Hungry and pinned at
    1980: the stomach covers (1980 - 1000) / 430 = 2.3 minutes, so ceil((25 x 430 - 980) / 5000) = 2 of 4 rations are
    needed, 2 spare; unpinned (the level's bottom, 1000) 3 are needed. Fed and pinned at 6980 (a ration after the pin):
    1 needed, 3 spare; unpinned (2000) 2."""
    def setup(level, lo=None):
        p = pilot(pack=[("4 Rations of Food", P.TV_FOOD)])
        p.w.in_dungeon, p.w.ind["hunger"], p.w.flags = True, [level], {}
        p.trip_minutes_left = lambda: 20
        p.flavour_of = lambda it: None
        p.rates = {"buckets": []}
        if lo is not None:
            p.stomach.level, p.stomach.lo, p.stomach.hi = level, lo, lo + 19
        return p.supply_spare(p.w.items()[0])[0]
    got = (setup(2, 1980), setup(2), setup(3, 6980), setup(3))
    import math
    want = 4 - math.ceil((25 * 430 - 980) / 5000)
    return got == (want, 1, 3, 2) and want == 2, f"spare (Hungry pinned, unpinned, Fed pinned, unpinned): {got}"
