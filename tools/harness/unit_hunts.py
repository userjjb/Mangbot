"""unit_hunts -- unit cases: Hunt check and fight vetoes.

Run by unit.py (python3 unit.py [NAME]); W, pilot() and the other shared fixtures are in fixtures.py.
"""
import os
import random
import re
import types

from fixtures import P, RACES, BYNAME, case, pilot, PHASE


@case
def hunt_hill_giant_by_hp():
    """A7: a Hill giant hunt: allowed at 100% and at 80%; refused at 60% (the average fight, ~66 HP over ~8 turns,
    ends below the emergency rule's line). (The abort point is otherwise its worst 3 turns at our AC, ~100: the
    Advisor's emergency-threshold memo.) 2.45.0: fight_sim gets the derived to-hit/to-dam totals (the server's), not
    the weapon's own plusses, so fights are shorter: 80% with the default flee_hp 0.5 is now allowed (it ended at
    ~125 HP, below 132, with the understated damage; ~146 now)."""
    out = []
    for hp, flee in ((265, 0.5), (212, 0.5), (212, 0.4), (159, 0.4)):
        p = pilot(hp=hp, pack=[PHASE])
        p.orders["flee_hp"] = flee
        random.seed(1)          # (the duel simulator's 600 duels: 212/0.4 sits near the line, ~1 run in 20 flipped)
        out.append(p.hunt_refusal("Hill giant")[0] is None)
    return out == [True, True, True, False], f"allowed at 265/0.5, 212/0.5, 212/0.4, 159/0.4: {out}"


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
def weapon_numbers_by_geareval():
    """D6 (11-01): the weapon's dice and (+h,+d) are read by geareval.Item (weapon_damage, shadow.weapon_profile,
    fight_estimate, fight_sim) -- the same numbers as the old regexes for ordinary weapons, so the hunt checks don't
    change."""
    import shadow

    def old_damage(name, blows, mult=1):
        m = re.search(r"\((\d+)d(\d+)\)", name)
        if not m:
            return 0.0
        b = re.search(r"\([+-]\d+,([+-]\d+)\)", name)
        return (int(m.group(1)) * (int(m.group(2)) + 1) / 2 * mult + (int(b.group(1)) if b else 0)) * blows

    def old_profile(name, blows):
        d = re.search(r"\((\d+d\d+)\)", name or "")
        m = re.search(r"\(([+-]\d+),([+-]\d+)\)", name or "")
        return {"dice": d.group(1) if d else "1d4", "tohit": int(m.group(1)) if m else 0,
                "todam": int(m.group(2)) if m else 0, "blows": max(1, blows or 1)}
    names = ["a Spear (1d6) (+5,+7)", "a Dagger (1d4)", "a Scimitar of Westernesse (2d5) (+9,+8) (+1)",
             "a Lucerne Hammer of Venom (2d5) (-2,+3) {@w1}", "a Main Gauche (1d5) (+0,+0) {average}",
             "a Sabre (Holy Avenger) (2d7) (+12,+10) [+4] (+2)", "3 Daggers (1d4) (+1,+2)", ""]
    bad = [n for n in names if P.weapon_damage(n, 3) != old_damage(n, 3) or P.weapon_damage(n, 2, 3) !=
           old_damage(n, 2, 3) or shadow.weapon_profile(n, 2) != old_profile(n, 2)]
    p = pilot(hp=265, pack=[PHASE])
    random.seed(1)
    hunt = p.hunt_refusal("Hill giant")[0] is None
    est = p.fight_estimate(BYNAME["hill giant"])          # (its to-hit is the profile's tohit, compared above)
    return not bad and hunt and bool(est), \
        f"differ: {bad}; Hill giant hunt allowed: {hunt}; fight_estimate turns {est and round(est[0], 1)}"


@case
def disenchant_cost_in_the_hunt_check():
    """2.45.0 (the Advisor's Khim memo, 11-02): Khim's 4th blow is UN_BONUS. The hunt check counts the enchantment its
    landed blows take (apply_disenchant: 1 of 8 slots, a weapon -1/-1, armour -1 to-AC, +1 more with 20% above +5,
    artifacts resist 60%), at Dive04's 11-02 gear (clvl 29, AC 104): nonzero, in the `monster` text beside the drop and
    in the `hunt` log record; none with resist disenchantment; nothing for a monster without UN_BONUS."""
    worn = [("a Battle Axe of Westernesse (2d8) (+10,+9) (+1)", 22, 170), ("a Ring of Protection [+16]", 45, 2),
            ("a Ring of Protection [+12]", 45, 2), ("an Amulet of Slow Digestion", 40, 3),
            ("Hard Studded Leather of Resistance (-1) [7,+8]", 36, 110), ("a Shadow Cloak [6,+8]", 35, 5),
            ("an Orcish Shield [5,+8] (+1)", 34, 100), ("a Metal Cap [3,+8]", 32, 20),
            ("a Set of Gauntlets [2,+8]", 31, 25), ("a Pair of Hard Leather Boots of Stability [3,+8]", 30, 40)]

    def make(res_disen=False):
        p = pilot(hp=358, worn=worn, pack=[PHASE])
        p.orders = dict(P.DEFAULT_ORDERS, max_depth=750)
        p.w.hp, p.w.clvl = [358, 358], 29
        p.w.ind.update({"armor": [104], "stat0": [88], "stat3": [38]})
        p.w.flags.update(free_act=1, res_disen=int(res_disen))
        return p
    random.seed(1)
    p = make()
    text = p.monster_info("Khim, Son of Mim")
    dc = p.last_hunt.get("disen") or {}
    p.logs = []
    p.log = lambda kind, **kw: p.logs.append((kind, kw))
    p.mover = type("M", (), {"active": False, "stop": lambda self: None})()
    out = p.do_request({"cmd": "goal", "args": ["hunt", "Khim,_Son_of_Mim"], "role": "architect"})
    rec = next((kw for k, kw in p.logs if k == "hunt"), {})
    random.seed(1)
    r = make(True)
    rtext = r.monster_info("Khim, Son of Mim")
    rdc = r.last_hunt.get("disen") or {}
    giant = p.monster_info("Hill giant")
    # one disenchantment on one item: +8 armour loses 1.2 plusses (120 gold), +5 one, +0 none; an artifact 40% of it;
    # plusses not shown: the flat estimate
    loss = {n: p.disen_item_loss(n, False)[:2] for n in ("a Metal Cap [3,+8]", "a Metal Cap [3,+5]", "a Metal Cap [3,+0]",
                                                         "a Metal Cap [3]")}
    art = p.disen_item_loss("the Cloak 'Colluin' [1,+15]", False)
    want = {"a Metal Cap [3,+8]": (120.0, True), "a Metal Cap [3,+5]": (100.0, True), "a Metal Cap [3,+0]": (0.0, True),
            "a Metal Cap [3]": (100.0, False)}
    ok = (dc.get("gold", 0) > 0 and dc.get("n", 0) > 0 and dc.get("per_hit") == 120 and abs(dc["p_hit"] - 0.187) < 0.001
          and "disenchants expected" in text and text.index("a kill drops") < text.index("disenchants expected")
          and rec.get("disen_gold", 0) > 0 and rec.get("est_by") == "fight_sim" and "disenchants expected" in (out.get("note") or "")
          and rdc.get("resisted") and rdc.get("gold") == 0 and "you resist disenchantment" in rtext
          and "disenchant" not in giant and loss == want and art[2] and abs(art[0] - 0.4 * 120) < 1e-9)
    return ok, (f"Khim: {dc.get('hits')} hits, {dc.get('n')} disenchants, {dc.get('gold')} gold ({dc.get('per_hit')} a "
                f"hit, p_hit {dc.get('p_hit')}); hunt record {rec}; resisted {rdc.get('resisted')} gold "
                f"{rdc.get('gold')}; item losses {loss}; artifact {art}")


@case
def disenchant_refused_when_more_than_the_kill():
    """2.45.1 (the user): the hunt check refuses a disenchanter whose expected enchantment loss is more than a kill
    brings (the drop's expected value + its XP, exp * level / clvl, at the recent XP per gold); Khim at Dive04's gear
    is allowed (~300 gold against a ~2,555 drop); with no drop and XP valued low, refused; with resist
    disenchantment, never."""
    worn = [("a Battle Axe of Westernesse (2d8) (+10,+9) (+1)", 22, 170),
            ("Hard Studded Leather of Resistance (-1) [7,+8]", 36, 110), ("a Shadow Cloak [6,+8]", 35, 5),
            ("an Orcish Shield [5,+8] (+1)", 34, 100), ("a Metal Cap [3,+8]", 32, 20),
            ("a Set of Gauntlets [2,+8]", 31, 25), ("a Pair of Hard Leather Boots of Stability [3,+8]", 30, 40)]

    def make(res_disen=False, poor=False):
        random.seed(1)
        p = pilot(hp=358, worn=worn, pack=[PHASE])
        p.orders = dict(P.DEFAULT_ORDERS, max_depth=750)
        p.w.hp, p.w.clvl = [358, 358], 29
        p.w.ind.update({"armor": [104], "stat0": [88], "stat3": [38]})
        p.w.flags.update(free_act=1, res_disen=int(res_disen))
        if poor:
            p.drop_row = lambda race: {"e_gold": "0", "e_item_value_cap": "0"}
            p.xp_per_gold = lambda: 10.0
        return p
    rich = make().hunt_refusal("Khim, Son of Mim")[0]
    poor = make(poor=True).hunt_refusal("Khim, Son of Mim")[0]
    resist = make(True, poor=True).hunt_refusal("Khim, Son of Mim")[0]
    ok = rich is None and bool(poor) and "more than a kill brings" in poor and resist is None
    return ok, f"rich: {rich}; poor: {(poor or '')[:110]}; resisted: {resist}"
