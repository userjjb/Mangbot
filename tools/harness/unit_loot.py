"""unit_loot -- unit cases: Looting, pack room, destroying.

Run by unit.py (python3 unit.py [NAME]); W, pilot() and the other shared fixtures are in fixtures.py.
"""
import collections
import types

from fixtures import P, BYNAME, case, pilot, PHASE, _Stub


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
    kept = [n for n in names if not quiet.is_junk(n)]
    ok = quiet.cmds == ["custom k item=-11 value=3"] and "confirm yes" in quiet.sent and busy.cmds == [] and \
        hit.cmds == [] and kept == ["a Wand of Stinking Cloud"]
    return ok, f"quiet: {quiet.cmds}; an orc in view: {busy.cmds}; hit 2 s ago: {hit.cmds}; not junk: {kept}"


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


@case
def rations_by_need_and_heavy_loot_left():
    """Rations by need (the user, 10-31; was "never destroyed", after m46/m47): Fed with the trip ending in 2 minutes,
    2 of 3 are spare (worth their sale price) -- since 2.48.1 the stomach counts at the bottom of its level (Fed: 2000),
    so one is kept for the horizon's margin (m61: the middle of Fed emptied the pack and food ran out 5 minutes later); Hungry with 60 minutes to go, all are needed and worth the dungeon time
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
    ok = n3 == 2 and v3 < 10 and n_need == 3 and v_need > 1000 and took_staff is False and room == 50 and slow == 0 and took_heavy is False and took_light is True and said == 1
    return ok, f"3 rations, Fed, 2 min left: destroy {n3} (~{v3:.0f}); Hungry, 60 min left: {n_need} (~{v_need:.0f}); " \
               f"a staff taken {took_staff}; 145 lb carried: {room / 10:.0f} lb to spare, " \
               f"a Lucerne Hammer taken {took_heavy}, a potion {took_light}"


@case
def navigator_rules_review_and_nopickup():
    """The user (10-26, the Navigator empowerment list): executable standing orders (`rule leave NAME` acts at Pilot
    speed; `rule thieves kill` hunts a thief in view), the item-review queue (an identified wearable with an ability is
    held, not sold, until the Navigator decides; 2.63.0: at the town visit's end undecided items get the default, sold),
    and `order nopickup=`."""
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
    held_later = r.review_hold(amu)        # (2.63.0: held until the town visit's end, not for 2 visits)
    r.review_closing = True                # (plan town's last step: the default)
    released = r.review_hold(amu)
    r.review_closing = False
    r.orders["nopickup"] = "Lance,Pike"
    r.unique_drop, r.skipped_items, r.room_t = None, set(), 0.0
    lance = r.pickup_room("a Lance (2d8)")
    ok = acted and left and not again and hunted and asked == [["hunt", "Novice_rogue"]] and held is True and \
        held_later is True and released is False and lance is False
    return ok, f"leave: {acted}/{left}, again {again}; thief hunt {asked}; review held {held}, at the visit's end " \
               f"{released}; Lance picked up {lance}"


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
def far_fetch_kit_and_valuable_potions():
    """2.51.0 (the user after m62: a Potion of Speed in view 3 minutes at 750 ft, a Scroll of Teleportation 6 at 800 ft,
    neither fetched): potions and scrolls seen on the level map are fetched like devices and jewellery (within
    LOOT_VALUABLE_R 30, once the area is clear) when they are kit items or worth 200+. A Potion of Speed, a Scroll of
    Teleportation, a Potion of Restore Strength, Cure Light Wounds: kit items; a Potion of Restore Mana: not the kit's
    (a warrior can't use it) but worth ~350; a Scroll of Light: no; a Potion of Salt Water (junk): no. The '!' 25 squares off is walked to; a '?'
    whose wanted scroll has left the item list is not."""
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
    worth = {n: p.far_fetch_worth(n) for n in ("a Potion of Speed", "a Scroll of Teleportation",
                                                 "a Potion of Restore Strength", "a Potion of Restore Mana",
                                                 "a Scroll of Light", "a Potion of Salt Water",
                                                 "3 Potions of Cure Light Wounds")}
    w = p.w
    w.pos, w.level_t = (20, 20), 5.0
    w.itemlist = ["Items:", "! a Potion of Speed", "? a Scroll of Light"]
    w.messages.clear()
    w.losses = []
    p.found_t = P.gnow()
    p.orders.update(loot_radius=10, think_hp=0.65, pickup="all")
    p.band_warned, p.band_warned_t = (None, 0), 0.0
    p.skipped_items = set()
    p.mover = Mover()
    p.danger_why = lambda r, *a, **k: None
    w.memory = {(20, 45): "!", (20, 44): "?"}
    p.resolve_target = lambda k: [q for q, ch in w.memory.items() if ch in "!?"]
    p.watch_items(P.gnow())
    wanted = dict(p.far_wanted)
    went = p.loot_step({}), list(p.mover.sent)
    ok = worth["a Potion of Speed"] and worth["a Scroll of Teleportation"] and worth["a Potion of Restore Strength"] \
        and worth["a Potion of Restore Mana"] == "worth ~350" and not worth["a Scroll of Light"] and \
        not worth["a Potion of Salt Water"] and worth["3 Potions of Cure Light Wounds"] and \
        wanted == {(5.0, "!"): {"a Potion of Speed"}} and went == (True, [(20, 45)])
    return ok, f"worth {worth}; wanted {wanted}; loot step {went}"


@case
def m67_small_fixes():
    """2.62.0, m67's small fixes: news names a flavour the table knows ("a Rhodonite Ring (= Ring of Stupidity,
    junk)"); a floor destroy is checked by the floor and the "You destroy" message, not the pack, and sent only standing
    still on the square; a Brass Lantern is junk while a light needing no fuel is worn; no food, oil or kit consumable
    is destroyed for a find under 100 gold; no supplies alert before the stomach tracker has a level (just after a
    restart); "light off" in town once per idle period."""
    import time as _t
    p = pilot(worn=[("a Spear (1d6) (+5,+7)", 22, 50), ("a Phial {m63}", 39, 10)])
    p.flavours = {"Rhodonite Ring": {"kind": "Ring of Stupidity", "junk": True}}
    named = p.named("a Rhodonite Ring")
    junk = (p.is_junk("a Brass Lantern (with 7500 turns of light)"), p.is_junk("a Wooden Torch (with 2500 turns of light)"))
    p.w.floor = "a Ring of Aggravate Monster"
    sig0 = p.effect_sig("floor")
    p.w.floor = None
    p.w.messages.append((P.gnow(), "You destroy a Ring of Aggravate Monster."))
    sig1 = p.effect_sig("floor")
    p.mover = type("M", (), {"active": True})()
    p.w.monsters, p.w.last_hit_t = [], -99.0
    moving = p.destroy_floor_junk("a Ring of Aggravate Monster", P.gnow())
    # make-room: 3 rations and a cheap find
    q = pilot(pack=[("3 Rations of Food", 80)] + [(f"a Dagger (1d4) (+9,+{k})", 23) for k in range(22)])
    q.w.monsters, q.w.last_hit_t = [], -99.0
    q.mover = type("M", (), {"active": False})()
    q.trip_minutes_left = lambda: 2          # (the rations are spare: the old rule would destroy them)
    q.room_t, q.sent = -99.0, []
    q.cmd = lambda line, why, hold=0.4: q.sent.append(why)
    q.c = type("C", (), {"send": lambda self, x: None})()
    q.food_top = lambda: 14800               # (too full to eat for room)
    q.pickup_room("a Brass Lantern (with 7500 turns of light)")
    ration_gone = any("Ration" in s for s in q.sent)
    # supplies alert before the tracker has a level
    s = pilot(pack=[])
    s.w.in_dungeon, s.w.flags = True, {}
    s.trip_minutes_left = lambda: 30
    s.plan, s.food_warned, s.supply_told = None, None, set()
    s.stomach.level = None
    s.supply_watch()
    quiet = [k for k, _ in s.notes]
    # light off once per idle period
    t = pilot(worn=[("a Brass Lantern (with 7500 turns of light)", 39, 50)])
    t.w.depth, t.w.in_dungeon, t.w.store = 0, False, None
    t.goal, t.last_agent, t.busy_until, t.light_t = None, P.gnow() - 60, 0.0, 0.0
    t.sent = []
    t.cmd = lambda line, why, hold=0.4: t.sent.append(line)
    a = t.town_light(P.gnow())
    t.light_t = 0.0
    b = t.town_light(P.gnow() + 6)
    ok = named == "a Rhodonite Ring (= Ring of Stupidity, junk)" and junk == (True, True) and sig0 != sig1 and \
        moving is False and not ration_gone and quiet == [] and a is True and b is False and len(t.sent) == 1
    return ok, (f"named {named!r}; lantern/torch junk beside the Phial {junk}; floor sig changed {sig0 != sig1}; "
                f"destroy while moving {moving}; rations destroyed for a lantern {ration_gone} ({q.sent}); supplies "
                f"before the tracker {quiet}; light off {a}, {b} ({t.sent})")


@case
def unfelt_gear_waits_for_its_feeling():
    """2.69.0, the user after m69 ("Churning weapons is fine if we wait for the pseudo-ID first"): an unfelt weapon or
    armour piece in the pack isn't destroyed or dropped for room until it has its pseudo-ID feeling (~13 s of dungeon
    time on average for a clvl-30 warrior), at most FEELING_WAIT_S (3 minutes) after it was first seen; the find is
    left, with news "kept waiting for its feeling". A felt {average} one goes for an unfelt find worth more by
    expectation, as in m69 09:54 (a Lance {average} ~92 for a Lance ~210)."""
    def make(pack_lance, age=0.0):
        p = pilot(pack=[(pack_lance, 22)])
        p.w.depth, p.w.depth_ft, p.w.in_dungeon = 15, 750, True
        lance = p.w.items()[0]
        lance["weight"] = 300
        p.weight_room = lambda: (100, None)
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(line)
        p.c = types.SimpleNamespace(send=lambda line: None)
        p.room_t = 0.0
        p.track_unfelt()
        if age:
            p.unfelt_since = {k: P.gnow() - age for k in p.unfelt_since}
        took = p.pickup_room("a Lance (2d8)")
        return p, took
    unfelt, t1 = make("a Lance (2d8) {m69}")
    felt, t2 = make("a Lance (2d8) {average - m69}")
    old, _ = make("a Lance (2d8) {m69}", age=200)
    news = [d for k, d in unfelt.notes if k == "tactic"]
    ok = not t1 and not unfelt.cmds and news and "kept waiting for its feeling" in news[0] and \
        felt.cmds and felt.cmds[0].startswith("custom k item=0") and \
        unfelt.awaiting_feeling(unfelt.w.items()[0]) and not old.awaiting_feeling(old.w.items()[0]) and \
        not felt.awaiting_feeling(felt.w.items()[0])
    return ok, (f"unfelt Lance in the pack: took {t1}, cmds {unfelt.cmds}, news {news[:1]}; felt {{average}}: "
                f"{felt.cmds}; after 200 s unfelt: protected {old.awaiting_feeling(old.w.items()[0])}")


@case
def gear_far_fetched_for_its_sale():
    """2.72.0, the user after m71 13:11 ("the point isn't just to find another weapon, but also to make gold"): a
    Beaked Axe (2d6) seen ~42 squares off at 750 ft, ~652 by expectation unfelt (~247 at a shop), was never fetched --
    far fetch took devices, jewellery and potions/scrolls only. Now a weapon or armour piece a shop would pay
    GEAR_FETCH_MIN (150) for by expectation is fetched like them (`interesting_item` "fetching it once the area is
    clear"), from as far as its sale pays (~247 -> the 60-square cap); a felt {average} one for its sale alone; not a
    cheap Dagger (~125), a cursed piece, or one the weight limit would leave."""
    axe = "Beaked Axe (2d6)"
    p = pilot(hp=369)
    w = p.w
    w.depth, w.depth_ft, w.in_dungeon = 15, 750, True
    w.pos = (20, 20)
    w.memory = {(20, 62): "/"}
    w.itemlist = ["Items:", f"/ {axe}"]
    p.weight_room = lambda: (2000, 0)
    p.orders["loot_radius"], p.orders["pickup"] = 10, "all"
    p.plan = object()
    p.report_losses = lambda: None
    now = P.gnow()
    p.watch_items(now)
    p.watch_items(now + 3)
    news = [d for k, d in p.notes if k == "interesting_item"]
    reach = p.far_reach_of((20, 62))
    worth = {n: p.gear_fetch_worth(n) for n in ("Dagger (1d4)", "a Beaked Axe (2d6) {average}",
                                                 "a Beaked Axe (2d6) {cursed}")}
    p.weight_room = lambda: (100, 0)
    heavy = p.gear_fetch_worth(axe)
    ok = news and "fetching it once the area is clear" in news[0] and "20,62 (42 away)" in news[0] and \
        reach >= 42 and axe in p.far_wanted.get((w.level_t, "/"), ()) and worth["Dagger (1d4)"] is None and \
        worth["a Beaked Axe (2d6) {average}"] and worth["a Beaked Axe (2d6) {cursed}"] is None and heavy is None
    return ok, f"news {news}; reach {reach}; worth {worth}; at the weight limit {heavy}"
