"""unit_town -- unit cases: Shops and town.

Run by unit.py (python3 unit.py [NAME]); W, pilot() and the other shared fixtures are in fixtures.py.
"""
import os
import sys

from fixtures import HERE, P, case, W, pilot
import itemvalue                   # noqa: E402
import town_goals as TG            # noqa: E402


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


@case
def town_kit_tiers():
    """Dive04's pack after m23: WoR to 2 first, Restore CON before the kit's extras, the kit's CSW/Phase (and, 2.51.0,
    kit B's third Word of Recall)."""
    pack = [("3 Rations of Food", 80), ("3 Flasks of oil", 77), ("2 Potions of Cure Serious Wounds", 75),
            ("6 Potions of Cure Critical Wounds", 75), ("9 Scrolls of Phase Door", 70),
            ("a Scroll of Word of Recall {@R650}", 70), ("a Brass Lantern (with 6370 turns of light)", 39)]
    w = W(pack=pack, gold=637)
    w.depth, w.depth_ft, w.in_dungeon = 0, 0, False
    p = pilot(w)
    p.seen_drained = {"CON": (17, 18)}
    need = [(t, k, n) for t, k, s, n, c in p.town_needs(None, ())]
    # (no flasks: the lantern's 6370 turns and the 3 flasks reach 9000; rations: kit B's 3 had, a 4th without slow
    # digestion)
    want = [(1, "Word of Recall", 1), (3, "Restore Constitution", 1), (4, "Word of Recall", 1),
            (4, "Cure Serious Wounds", 2), (4, "Phase Door", 1), (4, "Ration of Food", 1), (4, "Heroism", 3),
            (4, "Potion of Speed", 2)]   # (Heroism since m41, Speed since; 2.51.0: kit B keeps a 3rd Word of Recall;
    # 2.65.0: a 4th ration without slow digestion -- rations_for_trip)
    return need == want, f"{need}"


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
    with --live they're kept like any useful device. Magic Mapping scrolls: 2.48.0 (the user) by the same rule, sold
    on the test server (mapping_scrolls_a_crutch_on_test), kept with --live."""
    def count(live, name, tval):
        p = pilot(pack=[(name, tval)])
        p.live = live
        p.town_buyers = lambda it: (6, 100)
        return p.town_sell_count(p.w.items()[0])
    test = count(False, "a Rod of Enlightenment", 66)
    live = count(True, "a Rod of Enlightenment", 66)
    scroll = count(True, "3 Scrolls of Magic Mapping", 70)
    return test == 1 and live == 0 and scroll == 0, f"test sells {test}, live sells {live}, live scrolls sold {scroll}"


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
def weapon_enchant_to_the_stopping_place():
    """2.46.0 (the user's option 2 on the Advisor's 11-03 memo): plan town buys and reads Enchant Weapon To-Dam/To-Hit
    for the wielded melee weapon by the armour's rule (the next point >= 50%, half the chance on an artifact). A
    Dagger (+5,+5) with the gold: 5 of each (1/.7 + 1/.6 + 1/.5 = 5.1 a plus), to-dam first when the gold is short
    (300 spare: one, 190 x 1.1 a scroll); at (+9,+9) (5%) none; an artifact at +0 half the chance (50%: 2 each), at +1
    none (49.5%); not unidentified, not the bow. The buy is one Alchemist visit, the read targets the weapon."""
    def make(weapon, gold=5000, tval=23, pack=()):
        p = pilot(worn=[(weapon, tval, 12)], gold=gold, pack=pack)
        p.stores_seen = {}
        p.town_reserve = lambda: 0
        p.orders["enchant_max"] = 25
        return p
    import types
    sent = []
    p = make("a Dagger (1d4) (+5,+5)")
    rich = p.enchant_buys(5000)
    poor = make("a Dagger (1d4) (+5,+5)").enchant_buys(300)
    high = make("a Dagger (1d4) (+9,+9)")
    art = make("the Dagger 'Narthanc' (1d4) (+0,+0)")
    art1 = make("the Dagger 'Narthanc' (1d4) (+1,+1)")
    unid = make("a Dagger (1d4) {good}")
    bow = make("a Sling (x2) (+5,+5)", tval=19)
    k = P.TownKit()
    r = k._buying_enchant(p, types.SimpleNamespace(w=p.w, now=0.0))
    shop = k.sub.buys if k.sub else None
    rd = make("a Dagger (1d4) (+5,+5)", pack=[("5 Scrolls of Enchant Weapon To-Hit", 70)])
    rd.cmd = lambda line, why="", hold=0: sent.append((line, why))
    k2 = P.TownKit()
    k2._buying_enchant(rd, types.SimpleNamespace(w=rd.w, now=0.0))
    note = p.town_extras_note()
    ok = rich == [("Enchant Weapon To-Dam", 5, 190), ("Enchant Weapon To-Hit", 5, 190)] and \
        poor == [("Enchant Weapon To-Dam", 1, 190)] and not high.weapon_enchant_plan() and not high.enchant_buys(5000) \
        and [round(c, 3) for _, _, c in art.weapon_enchant_plan()] == [0.5, 0.5] and \
        art.enchant_buys(5000) == [("Enchant Weapon To-Dam", 2, 190), ("Enchant Weapon To-Hit", 2, 190)] and \
        not art1.weapon_enchant_plan() and not unid.enchant_buys(5000) and not bow.enchant_buys(5000) and \
        r is None and k.sub.store == "5" and shop == [("Enchant Weapon To-Dam", 5, 285), ("Enchant Weapon To-Hit", 5, 285)] \
        and sent and sent[0][0] == "custom r item=0 dir=24" and "Enchant Weapon To-Dam" in note and \
        "Enchant Weapon To-Hit" in note and not k2.sub
    return ok, (f"rich {rich}; poor {poor}; +9 {high.enchant_buys(5000)}; artifact {art.weapon_enchant_plan()[:0]}"
                f"{[(kd, round(c, 3)) for _, kd, c in art.weapon_enchant_plan()]} buys {art.enchant_buys(5000)}; "
                f"artifact +1 {art1.weapon_enchant_plan()}; unidentified {unid.enchant_buys(5000)}; bow "
                f"{bow.enchant_buys(5000)}; kit {r} {shop} {k.done_log}; read {sent}; note {note}")


@case
def enchant_cap_shared_by_armour_and_weapon():
    """2.46.0: `order enchant_max` caps all the Scrolls of Enchant a visit buys, armour first. A cloak at -6 wants ~17
    (6 sure points, then 1/1 + 1/.99 + ... + 1/.5 to +8) and a Dagger (+5,+5) 5 + 5: at 25, 17 + 5 + 3; at 10, 10 of
    Enchant Armor; at 0 none, and no note."""
    def buys(cap):
        p = pilot(worn=[("a Dagger (1d4) (+5,+5)", 23, 12), ("a Shadow Cloak [6,-6]", 35, 10)])
        p.stores_seen = {}
        p.orders["enchant_max"] = cap
        return [(kd, n) for kd, n, _ in p.enchant_buys(10 ** 6)], p.town_extras_note()
    a, b, c = buys(25), buys(10), buys(0)
    ok = a[0] == [("Enchant Armor", 17), ("Enchant Weapon To-Dam", 5), ("Enchant Weapon To-Hit", 3)] and \
        b[0] == [("Enchant Armor", 10)] and c == ([], "") and "caps them all" in a[1]
    return ok, f"cap 25: {a}; cap 10: {b}; cap 0: {c}"


@case
def disenchant_value_by_what_the_pilot_buys():
    """2.46.0 (the user's option 2): a lost step plan town would buy back costs price / chance; any other step the
    plus's resale value (itemvalue with the plus one higher less as it is, x the pay cut: 100 x 0.3825 for a weapon
    here, 100 x 0.425 for armour) + its in-play value (DISEN_IN_PLAY: 0, not priced). Dagger (+5,+5) wielded: each plus
    5 -> 4, step 4->5 at 80%: 190/0.8 = 237.5 each, 475 in scrolls; the same as a bow (never bought): 2 x 38.25 = 76.5
    lost; (+10,+9): 9->10 (5%) lost, 7->8 (50%) bought (380); an artifact at +2: 1->2 (49.5%) lost, 0->1 (50%)
    bought (380); +8 armour with `order enchant_max=0`: nothing bought, 0.8 x 42.5 + 0.2 x 85 = 51 lost."""
    p = pilot()
    p.stores_seen = {}
    axe = "a Battle Axe of Westernesse (2d8) (+10,+9) (+1)"
    dag = p.disen_item_loss("a Dagger (1d4) (+5,+5)", "weapon")
    sling = p.disen_item_loss("a Sling (x2) (+5,+5)", "bow")
    step_hit = p.reenchant_cost("tohit", 9, 10, False, "weapon", axe)
    step_dam = p.reenchant_cost("todam", 7, 8, False, "weapon", axe)
    narth = p.reenchant_cost("todam", 0, 2, True, "weapon", "the Dagger 'Narthanc' (1d4) (+2,+2)")
    p.orders["enchant_max"] = 0
    cap0 = p.disen_item_loss("a Metal Cap [3,+8]", "helm")
    r = 100 * 0.3825 + p.DISEN_IN_PLAY

    def near(a, b):
        return abs(a - b) < 1e-6
    ok = near(dag[3][0], 475) and near(dag[3][1], 0) and near(sling[3][0], 0) and near(sling[3][1], 2 * r) and \
        near(step_hit[0], 0) and near(step_hit[1], r) and near(step_dam[0], 380) and near(step_dam[1], 0) and \
        near(narth[0], 380) and near(narth[1], r) and near(cap0[3][0], 0) and near(cap0[3][1], 51) and \
        p.DISEN_IN_PLAY == 0
    return ok, (f"dagger {dag}; sling {sling}; axe to-hit 9->10 {step_hit}, to-dam 7->8 {step_dam}; Narthanc 0->2 "
                f"{narth}; cap +8 at enchant_max=0 {cap0}")


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
        p.restore_item = lambda skip=(), stats=(): None
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
def buylist_counts_the_stash():
    """2.47.0 (the docs audit): `buy Restore_Dexterity:1` with one already in the house's stash buys none (plan town
    deposits every Restore, so the pack never held it and one was bought a visit); with none stashed, one."""
    def need(stashed):
        w = W(pack=[("a Scroll of Word of Recall", 70), ("a Scroll of Word of Recall", 70)], gold=5000)
        w.depth, w.depth_ft, w.in_dungeon = 0, 0, False
        p = pilot(w)
        p._house = {"items": {"3,4": "a Potion of Restore Dexterity"}} if stashed else {"items": {}}
        return [(t, k, n) for t, k, s, n, c in p.town_needs(None, [("Restore Dexterity", 1, None, 5)]) if t == 5]
    have, none = need(True), need(False)
    return have == [] and none == [(5, "Restore Dexterity", 1)], f"stashed: {have}; not: {none}"


# --- 2.48.0: the user's two principles for a weaker substitute (A fallback, B dungeon stopgap) and the Enchant /
# Recharging scrolls the kit would read (docs/pilot-items.md). The fixture's planned depth, 650 ft, is kit B.

def _town(p):
    p.w.depth, p.w.depth_ft, p.w.in_dungeon = 0, 0, False
    p.flavour_of = lambda it: None
    p.unknown_flavour = lambda it: False
    p.review_hold = lambda it: False
    p.gear_better = lambda it: False
    return p


def _dungeon(p, left, hunger=3):
    p.w.in_dungeon, p.w.hunger, p.w.flags = True, hunger, {}
    p.trip_minutes_left = lambda: left
    p.flavour_of = lambda it: None
    p.rates = {"buckets": []}
    return p


@case
def boldness_fallback_for_heroism():
    """A (2.48.0, the user): Boldness is Heroism's fallback. In town it's kept while Heroism is under the kit's target
    (kit B: 3) and sold once it's there; kit A (no Heroism) sells it. After the shops, Heroism still short (1 of 3):
    the Temple's Boldness for the shortfall less what's carried (3 - 1 - 1 = 1), once, at 1.5x its 8 gold; none when
    the Temple's listing this visit had no Boldness, or the gold the essentials leave doesn't stretch. In the dungeon
    a Boldness found while Heroism is short is a kit item (priceless for room, its price as loot); with Heroism at 3,
    loot."""
    import types
    def make(hero, kit=None, gold=1000, temple=("potion of boldnes", "potion of heroism")):
        p = _town(pilot(pack=[("2 Potions of Boldness", 75)] + ([(f"{hero} Potions of Heroism", 75)] if hero else []),
                        gold=gold))
        p.stores_seen = {4: {"owner": "Keldon the Wise (Dwarf)", "t": round(P.gnow()),
                             "prices": {k: (8 if "bold" in k else 43) for k in temple}}}
        p.town_reserve = lambda: 0
        if kit:
            p.goal = P.TownKit(kit)
        return p
    sells = {k: make(h, kit).town_sell_count(make(h, kit).w.items()[0]) for k, h, kit in
             (("hero1", 1, None), ("hero3", 3, None), ("kitA", 1, "A"))}

    def fallback(p):
        k = P.TownKit()
        k.t0 = P.gnow() - 5
        r = k._buying_fallback(p, types.SimpleNamespace(w=p.w, now=0.0))
        return (k.sub.store, k.sub.buys) if k.sub else r is not TG.NEXT
    one = make(1)
    one.w.items()[0]["number"], one.w.items()[0]["name"] = 1, "a Potion of Boldness"
    short = fallback(one)
    none_stocked = fallback(make(0, temple=("potion of heroism",)))
    broke = fallback(make(0, gold=5))
    at_target = fallback(make(3))
    d = _dungeon(make(1), 30)
    dv = d.pack_value(d.w.items()[0])
    loot = _dungeon(make(3), 30)
    lv = loot.pack_value(loot.w.items()[0])
    worth = d.kit_use_value("2 Potions of Boldness")
    ok = sells == {"hero1": 0, "hero3": 2, "kitA": 2} and short == ("4", [("Boldness", 1, 12)]) and \
        none_stocked is False and broke is False and at_target is False and dv == float("inf") and lv < 20 and \
        worth == 16
    return ok, (f"town sells {sells}; after the shops, Heroism 1/3 and 1 Boldness: {short}; no Boldness in the "
                f"Temple's listing: {none_stocked}; 5 gold: {broke}; Heroism 3/3: {at_target}; dungeon value, Heroism "
                f"short {dv}, at 3 {lv:.1f}; pickup worth {worth}")


@case
def satisfy_hunger_a_dungeon_stopgap():
    """B (2.48.0, the user): a Scroll of Satisfy Hunger is a stopgap for rations. In town it's sold (the General Store
    sells rations). In the dungeon, Hungry with no rations and 30 minutes to go, it's worth the dungeon time it covers,
    make-room and the weight shed may destroy none of it (destroy_count 0), and it isn't junk even on the junk order;
    with 3 rations and the trip ending in 2 minutes, it's worth its sale and may go."""
    t = _town(pilot(pack=[("a Scroll of Satisfy Hunger", 70)]))
    town = t.town_sell_count(t.w.items()[0])
    d = _dungeon(pilot(pack=[("2 Scrolls of Satisfy Hunger", 70)]), 30, hunger=2)
    d.orders["junk"] = "Satisfy Hunger"
    sc = d.w.items()[0]
    short = d.destroy_count(sc), round(d.pack_value(sc)), d.is_junk(sc), d.is_junk("a Scroll of Satisfy Hunger")
    f = _dungeon(pilot(pack=[("2 Scrolls of Satisfy Hunger", 70), ("3 Rations of Food", P.TV_FOOD)]), 2)
    sc = f.w.items()[0]
    fed = f.destroy_count(sc), round(f.pack_value(sc), 1)
    ok = town == 1 and short[0] == 0 and short[1] > 100 and short[2:] == (False, False) and fed[0] == 2 and fed[1] < 10
    return ok, f"town sells {town}; no rations, 30 min: (destroy, value, junk, floor junk) {short}; 3 rations, 2 min: {fed}"


@case
def clw_sold_in_kits_b_and_c():
    """B (2.48.0, the user): kits B and C heal with CSW and CCW, so plan town sells their Potions of Cure Light Wounds;
    kit A buys CLW and keeps them (`plan town kit=A`, or a planned depth under 500 ft); a buy list asking for CLW keeps
    them. In the dungeon CLW stays a kit consumable (priceless for room)."""
    def sold(kit=None, depth=650, buylist=()):
        p = _town(pilot(pack=[("5 Potions of Cure Light Wounds", 75)]))
        p.orders["max_depth"], p.deepest_ft = depth, depth
        if kit or buylist:
            p.goal = P.TownKit(kit, buylist)
        return p.town_sell_count(p.w.items()[0])
    got = {"B": sold(), "C": sold(depth=1200), "A by depth": sold(depth=300), "kit=A": sold("A"),
           "buy CLW": sold(buylist=[("Cure Light Wounds", 5, None, 4)])}
    d = _dungeon(pilot(pack=[("5 Potions of Cure Light Wounds", 75)]), 30)
    dv = d.pack_value(d.w.items()[0])
    ok = got == {"B": 5, "C": 5, "A by depth": 0, "kit=A": 0, "buy CLW": 0} and dv == float("inf")
    return ok, f"sold {got}; dungeon value {dv}"


@case
def mushrooms_sold_in_town_but_restores():
    """2.48.0 (the user: sell them like other non-ration food, unless the town has no better source for what they do):
    a Mushroom of Cure Serious Wounds is sold (the kit's potions cure); a Mushroom of Restoring or Restore Strength is
    kept (the town sells that only as a ~490-gold Restore potion). In the dungeon a mushroom keeps its expected value
    (2.42.0), not priceless."""
    p = _town(pilot(pack=[("a Mushroom of Cure Serious Wounds", 80), ("2 Mushrooms of Restoring", 80),
                          ("a Mushroom of Restore Strength", 80)]))
    got = [p.town_sell_count(it) for it in p.w.items()]
    d = _dungeon(pilot(pack=[("a Mushroom of Cure Serious Wounds", 80)]), 30)
    d.review_state = lambda: {"items": {}}
    dv = d.pack_value(d.w.items()[0])
    return got == [1, 0, 0] and 0 < dv < float("inf"), f"sold {got}; dungeon value {dv:.0f}"


@case
def torches_the_lanterns_fallback():
    """A + B (2.48.0, the user): with a lantern with fuel worn (or carried), plan town sells the Wooden Torches; with no
    lantern they stay (the light). In the dungeon a torch beside a lantern at 2000 turns, no flasks and 60 minutes to
    go is kept (destroy_count 0, worth the light it covers); a full lantern and 2 minutes to go: worth its sale, may go.
    ("3 Wooden Torches" was worth 0 to itemvalue: the plural.)"""
    lantern = ("a Brass Lantern (with 7000 turns of light)", P.TV_LITE, 50)
    t = _town(pilot(worn=[lantern], pack=[("3 Wooden Torches (with 5000 turns of light)", P.TV_LITE)]))
    town = t.town_sell_count(t.w.items()[0])
    n = _town(pilot(worn=[], pack=[("3 Wooden Torches (with 5000 turns of light)", P.TV_LITE)]))
    nolamp = n.town_sell_count(n.w.items()[0])

    def dungeon(turns, left):
        d = _dungeon(pilot(worn=[("a Brass Lantern (with %d turns of light)" % turns, P.TV_LITE, 50)],
                           pack=[("3 Wooden Torches (with 5000 turns of light)", P.TV_LITE)]), left)
        it = d.w.items()[0]
        return d.destroy_count(it), round(d.pack_value(it), 1)
    short, fine = dungeon(2000, 60), dungeon(15000, 2)
    ok = town == 3 and nolamp == 0 and short[0] == 0 and short[1] > 50 and fine[0] == 3 and fine[1] < 10 and \
        itemvalue.value("3 Wooden Torches (with 5000 turns of light)").value == 2
    return ok, f"town sells {town} (no lantern: {nolamp}); dungeon, lantern 2000/60 min: {short}; 15000/2 min: {fine}"


@case
def mapping_scrolls_a_crutch_on_test():
    """2.48.0 (the user): a Scroll of Magic Mapping is a crutch on the test server, as the mapping devices: sold in town,
    not a kit item (loot in the dungeon: its sale value, no kit pickup worth), and never read by the flee; with --live
    it's the kit's (kept, priceless, read). Deep Descent (travel) stays a kit scroll on the test server."""
    def run(live):
        p = _town(pilot(pack=[("3 Scrolls of Magic Mapping", 70), ("a Scroll of Deep Descent", 70)]))
        p.live = live
        p.town_buyers = lambda it: [5]
        sold = [p.town_sell_count(it) for it in p.w.items()]
        d = _dungeon(pilot(pack=[("4 Scrolls of Magic Mapping", 70)]), 30)
        d.live = live
        d.review_state = lambda: {"items": {}}
        value = d.pack_value(d.w.items()[0])
        worth = d.kit_use_value("a Scroll of Magic Mapping")
        d.w.pos, d.w.level_t, d.w.depth, d.w.depth_ft = (20, 20), 5.0, 13, 650
        d.w.memory = {(20, 20): ".", (20, 36): ">"}
        d.w.find = lambda chars: [q for q, ch in d.w.memory.items() if ch in chars]
        d.w.monsters, d.w.still_seen, d.w.avoid_zone, d.w.avoid_inside = [], {}, set(), False
        d.w.adjacent_monsters = lambda: []
        d.w.standing_on = "."
        d.cmds = []
        d.cmd = lambda line, why, hold=0.4: d.cmds.append(why)
        d.mover = type("M", (), {"go": lambda self, *a, **k: True, "active": True, "unknown": True, "path": [1] * 9,
                                 "tick": lambda self: "moving", "stop": lambda self: None})()
        P.Flee("band").tick(d)
        read = any("Magic Mapping" in c for c in d.cmds)
        return sold, value, worth, read
    test, live = run(False), run(True)
    ok = test[0] == [3, 0] and test[1] < 100 and test[2] == 0 and test[3] is False and \
        live[0] == [0, 0] and live[1] == float("inf") and live[2] > 0 and live[3] is True
    return ok, f"test server (sold, value, worth, read): {test}; live: {live}"


@case
def enchant_and_recharge_scrolls_kept_to_read():
    """2.48.0 (the user): before selling a Scroll of Enchant or Recharging, check whether the kit would read it. A
    Dagger (+5,+5) wielded: the 2 To-Dam scrolls are kept (the town kit reads them before buying: 5 wanted - 2 carried =
    3 bought), the Enchant Armor nothing would use is sold; a Scroll of Recharging with an empty Staff of Perception is
    kept, without one sold. At (+9,+9) the To-Dam scrolls are sold. Kept ones are priceless for room in town, worth
    their price in the dungeon."""
    def make(weapon="a Dagger (1d4) (+5,+5)", staff=True):
        p = _town(pilot(worn=[(weapon, 23, 12)], gold=5000,
                        pack=[("2 Scrolls of Enchant Weapon To-Dam", 70), ("a Scroll of Enchant Armor", 70),
                              ("a Scroll of Recharging", 70)] +
                        ([("a Staff of Perception (0 charges)", 55)] if staff else [])))
        p.stores_seen = {}
        p.is_artifact = lambda n: False
        p.orders["enchant_max"] = 25
        return p
    p = make()
    got = [p.town_sell_count(it) for it in p.w.items()[:3]]
    buys = p.enchant_buys(10 ** 6)
    room = p.pack_value(p.w.items()[0])
    q = make("a Dagger (1d4) (+9,+9)", staff=False)
    high = [q.town_sell_count(it) for it in q.w.items()[:3]]
    p.w.in_dungeon = True
    dv = p.pack_value(p.w.items()[0])
    ok = got == [0, 1, 0] and buys[:1] == [("Enchant Weapon To-Dam", 3, 190)] and room == float("inf") and \
        high == [2, 1, 1] and dv == 380
    return ok, f"sold (To-Dam, Armor, Recharging) {got}; buys {buys}; town room value {room}; (+9,+9), no staff: " \
               f"{high}; dungeon value {dv}"


@case
def word_of_recall_three_in_kits_b_and_c():
    """2.51.0 (the user after m62: the trip-end visit restocked Word of Recall to 2 and the Navigator asked for 3):
    kits B and C keep 3 Words of Recall, kit A 2; every plan town restocks to it (a trip's `then town` too: TownKit()
    takes the planned depth's kit). Tier 1 still buys the essential 2 first."""
    def need(depth, kit=None):
        w = W(pack=[("a Scroll of Word of Recall", 70)], gold=5000)
        w.depth, w.depth_ft, w.in_dungeon = 0, 0, False
        p = pilot(w)
        p.orders["max_depth"], p.deepest_ft = depth, depth
        return [(t, n) for t, k, s, n, c in p.town_needs(kit, ()) if k == "Word of Recall"]
    got = {"B (650 ft)": need(650), "C (1100 ft)": need(1100), "A (300 ft)": need(300), "kit=A at 650": need(650, "A")}
    ok = got == {"B (650 ft)": [(1, 1), (4, 1)], "C (1100 ft)": [(1, 1), (4, 1)], "A (300 ft)": [(1, 1)],
                 "kit=A at 650": [(1, 1)]}
    return ok, f"{got}"


@case
def plan_sent_during_plan_town_is_queued():
    """2.53.0 (the user after m63: a `plan trip` 6 s into plan town cut its house visit short): a Navigator's
    `plan trip` or `goal ...` sent while plan town runs is queued -- "queued after plan town (it is at: <stage>)" --
    shown by `plan`, dropped by `stop`; once plan town is over it starts (news). The Architect's go through. plan
    town's summary says plainly when gold is left in the purse with a house owned ("BANK: N gold still carried --
    `house deposit`") and raises a `bank` alert."""
    def make():
        p = pilot(gold=300)
        p.w.depth, p.w.depth_ft, p.w.in_dungeon, p.w.resting = 0, 0, False, False
        p.mover = type("M", (), {"active": False, "stop": lambda self: None})()
        p.stop_resting = lambda: None
        k = P.TownKit()
        k.stage = "buying"
        p.goal = k
        return p, k
    p, k = make()
    q = p.do_request({"cmd": "plan", "args": ["trip", "700-800", "then", "town"], "role": "navigator"})
    shown = p.do_request({"cmd": "plan", "args": [], "role": "navigator"})["text"]
    p.do_request({"cmd": "stop", "args": [], "role": "navigator"})
    dropped = p.queued
    p, k = make()
    q2 = p.do_request({"cmd": "goal", "args": ["wait", "5"], "role": "navigator"})
    early = p.queue_tick()
    p.goal = None                           # (plan town's goal_done)
    started = p.queue_tick()
    goal = p.goal.describe() if p.goal else None
    news = [d for k_, d in p.notes if k_ == "queued"]
    a, _ = make()
    arch = a.do_request({"cmd": "goal", "args": ["wait", "5"], "role": "architect"})
    # the bank line
    b, kit = make()
    b.w.ind["gold"] = [26000]
    b._house = {"house": {"door": [60, 129]}, "banked": 0}
    b.supply_gate = lambda depth, recall: []
    kit.done_log = ["house: failed (the bank's 25444 gold wasn't picked up on the way in)"]
    r = kit.finish(b)
    bank = [d for k_, d in b.notes if k_ == "bank"]
    ok = q.get("queued") and "queued after plan town (it is at: buying)" in q["text"] and \
        "queued after plan town" in shown and "plan trip" not in str(p.queued) and dropped is None and \
        q2.get("queued") and early is False and started is True and goal and goal.startswith("wait") and news and \
        "started" in news[0] and not arch.get("queued") and \
        r[1].startswith("BANK: 26000 gold still carried -- `house deposit` (house: failed") and bank
    return ok, f"queued {q}; plan {shown!r}; after stop {dropped}; goal queued {q2}, started {started} -> {goal}, " \
               f"news {news}; architect {arch}; finish {r[1][:120]!r}; bank alert {bank}"


@case
def unknowns_identified_before_sale():
    """2.55.0 (the user after m64: plan town sold an unknown Pungent Potion for 9 gold -- a Potion of Strength,
    relisted at 12,560 -- "identify everything other than weapon/armor with a pseudo-ID already"): an unknown flavour,
    unknown jewellery/devices and unfelt weapons/armour are kept until identified, and all count for plan town's
    Identify scrolls whatever their value (unfelt weapons not in the dungeon: pseudo-ID feels them free); a felt
    {average} sword sells as before. A known stat-gain potion is never sold and is drunk (plan town's upgrade stage,
    a safe moment)."""
    p = _town(pilot(pack=[("a Pungent Potion", 75), ("a Cutlass (1d7)", 23), ("a Long Sword (2d5) {average}", 23),
                          ("a Ring of Protection", 45)], gold=2000))
    p.unknown_flavour = P.Pilot.unknown_flavour.__get__(p)
    p.flavours = {}
    pot, cut, sword, ring = p.w.items()
    sells = {i["name"]: p.town_sell_count(i) for i in p.w.items()}
    rules = p.town_rule(pot)
    cands = sorted(i["name"] for _, i in p.identify_candidates(2 * 80))
    wanted = p.town_identify_wanted()
    p.w.in_dungeon = True
    dcands = sorted(i["name"] for _, i in p.identify_candidates(20))
    p.w.in_dungeon = False
    g = _town(pilot(pack=[("a Potion of Strength", 75), ("a Potion of Restore Strength", 75),
                          ("a Potion of Enlightenment", 75)]))
    gains = [g.gain_potion(i) for i in g.w.items()]
    gsell = g.town_sell_count(g.w.items()[0])
    sent = []
    g.cmd = lambda line, why, hold=0.4: sent.append(line)
    g.pending_use, g.busy_until = None, 0
    drank = g.quaff_gain("plan town")
    ok = sells == {"a Pungent Potion": 0, "a Cutlass (1d7)": 0, "a Long Sword (2d5) {average}": 1,
                   "a Ring of Protection": 0} and rules[0] == "keep" and "identified before" in rules[1] and \
        cands == ["a Cutlass (1d7)", "a Pungent Potion", "a Ring of Protection"] and wanted == 3 and \
        dcands == ["a Pungent Potion", "a Ring of Protection"] and gains == [True, False, False] and gsell == 0 and \
        drank and sent == ["custom q item=0"]
    return ok, (f"sells {sells}; rule {rules}; town candidates {cands} ({wanted} wanted); dungeon {dcands}; gain "
                f"potions {gains}, Strength sold {gsell}, drunk {drank} {sent}")


@case
def felt_good_gear_identified_average_sold():
    """2.55.0, the user's correction: gear felt {good}, {excellent} or {special} is identified before selling too
    (whatever its value); only {average}, {worthless}, {cursed}, {broken} gear goes by its feeling. A {good} Cutlass
    is kept and counted for Identify (in the dungeon too); an {average} one sells as is."""
    p = _town(pilot(pack=[("a Cutlass (1d7) {good}", 23), ("a Cutlass (1d7) {average}", 23)], gold=2000))
    good, avg = p.w.items()
    sells = (p.town_sell_count(good), p.town_sell_count(avg))
    must = (p.must_identify(good), p.must_identify(avg))
    cands = [i["name"] for _, i in p.identify_candidates(10 ** 6)]
    p.w.in_dungeon = True
    dcands = [i["name"] for _, i in p.identify_candidates(10 ** 6)]
    ok = sells == (0, 1) and must == (True, False) and cands == ["a Cutlass (1d7) {good}"] and \
        dcands == ["a Cutlass (1d7) {good}"]
    return ok, f"sold (good, average) {sells}; must identify {must}; town candidates {cands}; dungeon {dcands}"


@case
def caps_from_the_normal_price_not_a_sale():
    """2.56.0 (the user after m65: one Potion of Cure Serious Wounds bought at 50% off for 31, then the rest refused --
    "cap 46" = 1.5 x the sale price -- with the normal price 63): the shop listing's discounted lines count at their
    undiscounted price ({50% off} 31 -> 62), so caps (1.5x) and forecasts rest on the normal price; the Shop still
    buys the cheapest line within the cap."""
    import tempfile
    p = pilot(gold=20000, pack=[("5 Potions of Cure Critical Wounds", 75)])
    p.w.depth, p.w.depth_ft, p.w.in_dungeon = 0, 0, False
    p.stores_file = os.path.join(tempfile.mkdtemp(), "stores.json")
    p.w.store = {"name": "Temple", "owner": "Keldon", "items": [
        {"name": "a Potion of Cure Serious Wounds {50% off}", "price": 31},
        {"name": "5 Potions of Cure Serious Wounds", "price": 63}]}
    p.w.store_t, p.stores_noted_t = 5.0, 0.0
    p.note_store()
    price = p.price_of("Cure Serious Wounds", 4)
    buys, short = p.town_shopping("B", [])
    csw = [b for b in buys if b[1] == "Cure Serious Wounds"]
    norm = (P.Pilot.normal_price("a Potion of Heroism {75% off}", 11), P.Pilot.normal_price("a Potion of Heroism", 43))
    kit_cap = [b[4] for b in csw if b[0] == 4]
    ok = price == 62 and kit_cap == [93] and norm == (44, 43)
    return ok, f"price recorded {price}; CSW lines {csw}; short {short}; normal prices {norm}"


@case
def navigator_clarity_losses_and_plan_town():
    """2.56.0 (the Navigator after m65): an item destroyed by an attack is News naming what, how many and by what
    ('destroyed: one of Potions of Heroism -- by "The Fire hound breathes fire."'); a `plan town` sent while plan town
    runs is queued for a second visit (the Navigator) or answered "plan town is already running" (the Architect), and
    on the house's wilderness tile the answer is "walk back into town", never "recall home first"."""
    p = pilot()
    now = P.gnow()
    p.w.messages.extend([(now - 1, "The Fire hound breathes fire."),
                         (now, "One of your Potions of Heroism (f) was destroyed!")])
    p.w.losses = [(now, "One of your Potions of Heroism (f) was destroyed!")]
    p.report_losses()
    lost = [d for k, d in p.notes if k == "lost"]
    q = pilot(gold=300)
    q.w.depth, q.w.depth_ft, q.w.in_dungeon, q.w.resting = -1, 0, False, False
    q.mover = type("M", (), {"active": False, "stop": lambda self: None})()
    k = P.TownKit()
    k.stage = "upgrade"
    q.goal = k
    nav = q.do_request({"cmd": "plan", "args": ["town", "buy", "Word_of_Recall:3"], "role": "navigator"})
    arch = q.do_request({"cmd": "plan", "args": ["town"], "role": "architect"})
    q.goal = None
    tile = q.do_request({"cmd": "plan", "args": ["town"], "role": "architect"})
    ok = lost and lost[0].startswith('destroyed: one of Potions of Heroism -- by "The Fire hound breathes fire."') \
        and nav.get("queued") and "already running" in arch.get("error", "") and \
        "walk back into town" in tile.get("error", "") and "recall" not in tile.get("error", "")
    return ok, f"lost {lost}; navigator {nav}; architect {arch}; on the tile {tile}"


@case
def review_decided_in_the_same_visit():
    """2.63.0 (the user: "We shouldn't defer deciding to sell gear multiple dungeon visits. It should be decided while
    we are in town the first time"): plan town raises the held items at its start as one `review` alert (the default,
    why, a gearcmp hint); the Navigator answers during the visit; at the visit's last step before banking, after at
    least 60 s from the alert (a Wait; the shops ran meanwhile), anything undecided gets the default -- sold there. A
    `review keep` during the visit keeps it."""
    def make(answer=None):
        import tempfile
        p = pilot(pack=[("an Amulet of Resist Lightning", 40)], gold=500)
        p.rundir = tempfile.mkdtemp()
        p.w.depth, p.w.depth_ft, p.w.in_dungeon = 0, 0, False
        p.flavour_of = lambda it: None
        p.unknown_flavour = lambda it: False
        p.gear_better = lambda it: None
        p.house_state = lambda: {}
        k = P.TownKit()
        p.goal = k
        k._kit_count(p, None)
        alert = next((d for w_, d in p.notes if w_ == "review"), "")
        if answer:
            p.do_request({"cmd": "review", "args": [answer, "amulet"], "role": "navigator"})
        ctx = types.SimpleNamespace(w=p.w, now=P.gnow())
        first = k._buying_review(p, ctx)
        waited = type(k.sub).__name__ if k.sub else None
        k.sub = None
        k._buying_review(p, ctx)
        k._buying_review(p, ctx)
        shop = (k.sub.store, k.sub.sells) if k.sub else None
        return alert, first, waited, shop, p.review_state()["decided"].get("an Amulet of Resist Lightning")
    import types
    alert, first, waited, shop, dec = make()
    kept = make("keep")
    ok = "decide these now" in alert and "default: sell" in alert and "gearcmp" in alert and first is None and \
        waited == "Wait" and shop and shop[1] == [(0, 1)] and dec == "sell" and kept[3] is None and kept[4] == "keep"
    return ok, f"alert {alert[:120]!r}; first {first}, {waited}; then sold at {shop} ({dec}); kept: {kept[3:]} "


@case
def debt_waive_and_floor_price():
    """2.63.0: `debt waive N|all [REASON]` (the Architect's) strikes an item-debt entry, keeping it as waived (who,
    when, why) and logging debt_waived; the Navigator is refused. `price NAME` values an item on the floor (the item
    list, its glyph's square) at this depth -- m67's Navigator couldn't price unidentified boots in a vault."""
    import tempfile
    p = pilot()
    p.debt_path = os.path.join(tempfile.mkdtemp(), "navigator_debt.json")
    p.debt = {"entries": [{"t": "x", "gold": 276, "what": "a Lead-Filled Mace", "why": "destroy"},
                          {"t": "y", "gold": 40, "what": "a Dagger", "why": "sell"}]}
    nav = p.do_request({"cmd": "debt", "args": ["waive", "1"], "role": "navigator"})
    arch = p.do_request({"cmd": "debt", "args": ["waive", "1", "the", "user", "waived", "it"], "role": "architect"})
    listing = p.do_request({"cmd": "debt", "args": [], "role": "navigator"})["text"]
    q = pilot()
    q.w.itemlist = ["Items:", "] a Pair of Hard Leather Boots", "! a Potion of Cure Light Wounds"]
    q.w.memory = {(30, 40): "]"}
    q.w.floor = None
    q.vaults = {}
    price = q.price_info("boots")
    ok = not nav["ok"] and arch["ok"] and p.debt_total() == 40 and p.debt["waived"][0]["waived_why"] == \
        "the user waived it" and "#1" in listing and "on the floor at 30,40" in price and "unfelt" in price
    return ok, f"navigator {nav}; architect {arch}; listing {listing!r}; price {price!r}"


@case
def rations_by_digestion_and_the_last_kept():
    """2.65.0 (m68, the first trips without the Amulet of Slow Digestion): plan town's rations follow the worn gear's
    digestion -- 4 without slow digestion (a trip of unknown length, 45 dungeon minutes, at ~11.6 a ration), the
    kit's 3 with it; in the dungeon make-room keeps the last ration (m68 00:11 destroyed all 4 for a Staff of Trap
    Location, the trip 8 minutes from its end) and values it at the minutes it gives."""
    p = pilot(pack=[("4 Rations of Food", 80)])
    p.w.depth, p.w.in_dungeon = 0, False
    fast = p.rations_for_trip(3)
    p.w.flags = dict(p.w.flags, slow_digest="e")
    slow = p.rations_for_trip(3)
    p.w.flags = dict(p.w.flags, slow_digest="")
    d = pilot(pack=[("4 Rations of Food", 80)])
    d.w.depth, d.w.in_dungeon = 15, True
    d.trip_minutes_left = lambda: 8.0
    d.food_now = lambda: 9990
    rat = d.w.items()[0]
    spare4 = d.supply_spare(rat)
    one = pilot(pack=[("a Ration of Food", 80)])
    one.w.depth, one.w.in_dungeon = 15, True
    one.trip_minutes_left = lambda: 8.0
    one.food_now = lambda: 9990
    spare1 = one.supply_spare(one.w.items()[0])
    ok = fast == 4 and slow == 3 and spare4[0] == 3 and spare1[0] == 0 and spare1[1] > 10
    return ok, f"rations without/with slow digestion {fast}/{slow}; 4 carried, 8 min left: spare {spare4}; one: {spare1}"
