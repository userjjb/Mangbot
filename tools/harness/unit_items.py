"""unit_items -- unit cases: Item values and identification.

Run by unit.py (python3 unit.py [NAME]); W, pilot() and the other shared fixtures are in fixtures.py.
"""
import os
import re
import sys

from fixtures import HERE, P, BYNAME, case, W, pilot
import itemvalue                   # noqa: E402


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
def junk_one_rule():
    """D3 (the user, 11-01): one is_junk for the pack, the floor and the item list -- the union of the old lists (junk
    order as a whole word, harmful devices, rulebook junk kinds, junk flavours, Broken, autodestroy feelings), never a
    kept or @-inscribed item; for a warrior only the town's spellbooks (the dungeon-only books are loot); and
    auto_destroy destroys what it calls junk."""
    p = pilot(pack=[("a Wand of Clone Monster (5 charges)", 65), ("a Potion of Cure Light Wounds", 75)])
    p.orders.update(junk="Salt Water,Poison,Blindness,Slime Mold", autodestroy="worthless,cursed")
    p.junk_kinds = {"Potion of Water": True}
    p.flavours = {"Puce Potion": {"kind": "Potion of Salt Water", "junk": True}}
    p.w.ind["class_"] = "Warrior"
    names = ["a Potion of Salt Water", "a Staff of Haste Monsters", "a Potion of Water", "a Puce Potion",
             "a Broken Dagger (1d1)", "a Dagger (1d4) {worthless}", "3 Slime Molds",
             "a Book of Magic Spells [Magic for Beginners]", "a Holy Book of Prayers [Words of Wisdom]",
             "a Potion of Salt Water {@q1}", "a Dagger (1d4) {cursed, !k}",
             "a Ring of Resist Poison", "a Mushroom of Cure Blindness", "a Potion of Neutralize Poison",
             "a Book of Magic Spells [Resistances of Scarabtarices]", "a Holy Book of Prayers [Wrath of God]"]
    got = [n for n in names if p.is_junk(n)]
    want = names[:9]
    p.keep = {"salt water"}
    kept = p.is_junk("a Potion of Salt Water")
    p.busy_until, p.autodestroy_t = 0.0, 0.0
    p.sent, p.cmds = [], []
    p.c = type("C", (), {"send": lambda self, x: p.sent.append(x)})()
    p.cmd = lambda line, why, hold=0.4: p.cmds.append(line)
    p.auto_destroy(P.gnow())
    worth = itemvalue.value("a Book of Magic Spells [Resistances of Scarabtarices]").value
    ok = got == want and not kept and p.cmds == ["custom k item=0 value=1"] and worth == 10000
    return ok, f"junk: {got}; kept Salt Water junk: {kept}; auto_destroy: {p.cmds}; dungeon book value {worth}"


@case
def pay_cut_in_shopmath_and_aware():
    """D9 (11-01, for the scorecard): the owner-aware pay cut is shopmath.pay_cut with its inputs explicit (tval, CHR,
    the owners seen) and Pilot.pay_cut calls it -- the same results as the old in-Pilot rule; spellbooks now have
    buyers (Temple, Magic Shop). aware_kinds() is what iv passes to itemvalue (and what state.jsonl logs)."""
    sys.path.insert(0, os.path.join(HERE, "..", "observe"))
    import shopmath

    def old(tval, chr_v, seen):
        best = None
        for st in (P.Pilot.BUYERS.get(tval, ()) if tval is not None else (1, 2, 3, 4, 5, 6)):
            owner = (seen.get(st) or {}).get("owner")
            f = shopmath.factors(re.sub(r"\s*\(.*\)$", "", owner), chr_v) if owner else None
            if f:
                cut = f[0] / 100
            else:
                fs = [x for x in (shopmath.factors(o, chr_v) for o, (idx, _r, _g) in shopmath.OWNERS.items()
                                  if idx == st - 1) if x]
                cut = sum(x[0] for x in fs) / len(fs) / 100 if fs else None
            if cut is not None and (best is None or cut > best):
                best = cut
        return best if best is not None else P.SHOP_CUT
    owners = {}
    for o, (idx, _r, _g) in shopmath.OWNERS.items():
        owners.setdefault(idx + 1, o + " (Elf)")
    bad = []
    for seen in ({}, {st: {"owner": o} for st, o in owners.items()}):
        for chr_v in (3, 10, 18, 68):
            p = pilot()
            p.stores_seen, p.w.ind["stat5"] = seen, [chr_v]
            for tv in (None, 23, 37, 75, 70, 45, 66, 80, 99):
                if abs(p.pay_cut(tv) - old(tv, chr_v, seen)) > 1e-12:
                    bad.append((tv, chr_v, bool(seen)))
    p = pilot()
    p.flavours = {"Puce Potion": {"kind": "Potion of Cure Light Wounds"}, "Iron Ring": {"kind": "Ring of Protection"}}
    aware = p.aware_kinds()
    books = (p.pay_cut(90), p.pay_cut(91))
    ok = not bad and aware == {"cure light wounds", "protection"} and all(b != P.SHOP_CUT for b in books)
    return ok, f"differ: {bad}; aware {sorted(aware)}; book cuts {books}"


@case
def override_debt_counts_the_stack():
    """2.46.1 (the docs audit): `destroy !NAME all` / `drop !NAME N` charged one item's value to the Navigator's debt
    (iv's value is per item); now the number destroyed or dropped times it."""
    import os
    import tempfile

    def run(args):
        p = pilot(pack=[("3 Potions of Cure Critical Wounds", 75)])
        d = tempfile.mkdtemp()
        p.rundir = os.path.join(d, "pilot", "x")
        p.debt, p.debt_path = {}, os.path.join(d, "debt.json")
        p.log = lambda k, **kw: None
        p.cmd = lambda line, why, hold=0.4: None
        p.c = type("C", (), {"send": lambda s, line: None})()
        p.pack_now = lambda *a, **k: None
        p.dead, p.last_report, p.report_state = False, (0, 0.0), None
        p.do_request({"cmd": "destroy", "args": args, "role": "navigator"})
        return sum(e["gold"] for e in p.debt.get("entries", []))
    one, two, every = run(["!Cure_Critical_Wounds"]), run(["!Cure_Critical_Wounds", "2"]), \
        run(["!Cure_Critical_Wounds", "all"])
    return one > 0 and abs(two - 2 * one) <= 1 and abs(every - 3 * one) <= 1, f"1: {one}, 2: {two}, all: {every}"


@case
def restore_mushrooms_for_drains():
    """2.50.0 (the user): a drained STR/DEX/CON is restored at a safe moment (no monster in view) by the cheapest
    covering item -- a known restore mushroom (use-obj.c: Restore Strength -> STR, Restore Constitution -> CON,
    Restoring -> all six) is eaten (`custom E`) before a ~480-gold potion; never one that could gorge us; never for
    INT/WIS/CHR (town's). In town, tier 3 buys no Restore Strength a carried mushroom covers; with DEX drained and
    only a Restore Strength mushroom, none is used and the potion is bought. The stat_drained text names the mushroom."""
    def make(pack, drained, monsters=()):
        p = pilot(hp=300, pack=pack, monsters=list(monsters))
        w = p.w
        w.monster_seen_t, w.last_hit_t = -99.0, -99.0
        w.flag = lambda k: False
        w.find = lambda g: []
        w.adjacent_monsters = lambda: []
        p.seen_drained = drained
        p.goal, p.busy_until, p.eat_t, p.policy_t = None, 0.0, -99.0, -99.0
        p.sent = []
        p.cmd = lambda line, why, hold=0.4: p.sent.append(line)
        p.flavour_of = lambda it: None
        return p
    STR = {"STR": (58, 68), "DEX": (28, 28), "CON": (18, 18)}
    shroom = ("a Mushroom of Restore Strength", 80)
    a = make([shroom], STR)
    a.policy_tick(P.gnow())
    both = make([("a Potion of Restore Strength", 75), shroom], STR)
    pick = both.restore_item()["name"]
    full = make([shroom], STR)
    full.food_top = lambda: 14000
    gorge = full.restore_item()
    dex = make([shroom], {"DEX": (18, 28)})
    dex_use = dex.restore_item()
    town = make([shroom], STR)
    town.w.depth, town.w.depth_ft, town.w.in_dungeon = 0, 0, False
    needs = [k for t, k, *_ in town.town_needs(None, ()) if t == 3]
    dex.w.depth, dex.w.depth_ft, dex.w.in_dungeon = 0, 0, False
    dex_needs = [k for t, k, *_ in dex.town_needs(None, ()) if t == 3]
    orc = make([shroom], STR, monsters=[(22, 26, BYNAME["cave orc"])])
    orc.policy_tick(P.gnow())
    chr_ = make([("a Mushroom of Restoring", 80)], {"CHR": (3, 5)})
    chr_use = chr_.restore_item(stats=("STR", "DEX", "CON"))
    w = make([shroom], {"STR": (68, 68)})
    w.w.ind["stat0"] = [58, 68]
    for i in range(1, 6):
        w.w.ind[f"stat{i}"] = [18, 18]
    w.seen_drained = {n: (68 if n == "STR" else 18, 68 if n == "STR" else 18) for n in w.STAT_NAMES}
    w.w.ind["skills2"] = [3]
    w.seen_blows = 3
    w.watch_character()
    text = next((d for k, d in w.notes if k == "stat_drained"), "")
    ok = a.sent == ["custom E item=0"] and pick == "a Mushroom of Restore Strength" and gorge is None and \
        dex_use is None and needs == [] and dex_needs == ["Restore Dexterity"] and orc.sent == [] and \
        chr_use is None and "Mushroom of Restore Strength in the pack" in text and "eats" in text
    return ok, (f"STR drained, mushroom: {a.sent}; potion + mushroom: {pick}; nearly gorged: {gorge}; DEX drained: "
                f"{dex_use}; town tier 3 with the mushroom {needs}, DEX {dex_needs}; orc in view {orc.sent}; CHR "
                f"{chr_use}; alert {text!r}")


@case
def make_room_news_counts_what_went():
    """2.51.0 (m62 09:24): make-room destroyed 2 of 3 rations (value=2) and the news said "destroyed 3 Rations of Food",
    with the food left counted before the pack update. Now it names the count destroyed and kept, and the supply text
    leaves out what went; the supplies alert waits while an eat or destroy is fresh or a meal is unconfirmed."""
    p = pilot(pack=[("3 Rations of Food", 80)])
    it = p.w.items()[0]
    text = p.destroyed_text(it, 2), p.destroyed_text(it, 3)
    p.w.hunger = 3
    p.w.flags = {}
    food_all, food_one = p.supply_minutes()[0], p.supply_minutes({it["item"]: 2})[0]
    p.last_action = (P.gnow(), "custom k item=0 value=2", "make room")
    p.w.inven_dirty = False
    p.trip_minutes_left = lambda: 30
    p.plan = None
    p.food_warned = None
    p.supply_told = set()
    p.w.inven = []                       # (the pack shows the rations gone, the destroy just sent)
    p.supply_watch()
    quiet = list(p.notes)
    p.last_action = (P.gnow() - 10, "custom k item=0 value=2", "make room")
    p.supply_watch()
    later = [w for w, _ in p.notes]
    ok = text == ("2 of 3 Rations of Food (1 kept)", "3 Rations of Food") and \
        round(food_all - food_one) == round(2 * 5000 / (2 * p.TURNS_PER_DMIN)) and quiet == [] and "supplies" in later
    return ok, f"news {text}; food {food_all:.0f} -> {food_one:.0f} min; within 3 s {quiet}; later {later}"
