"""unit_town -- unit cases: Shops and town.

Run by unit.py (python3 unit.py [NAME]); W, pilot() and the other shared fixtures are in fixtures.py.
"""
import os
import sys

from fixtures import HERE, P, case, W, pilot
import itemvalue                   # noqa: E402


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
