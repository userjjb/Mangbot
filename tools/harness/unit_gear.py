"""unit_gear -- unit cases: Gear (evaluator, loadout, review).

Run by unit.py (python3 unit.py [NAME]); W, pilot() and the other shared fixtures are in fixtures.py.
"""
import collections
import os

from fixtures import P, case, pilot


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
def rings_of_damage_and_accuracy():
    """A13 (session 10): a lone (+n) on a Ring of Damage/Accuracy is its to-dam/to-hit (object1.c), not a pval;
    a Ring of Strength's (+3) stays a pval."""
    import geareval
    got = [(i.to_h, i.to_d, i.pval) for i in (geareval.Item(n, tval=45) for n in (
        "a Ring of Damage (+6)", "a Ring of Accuracy (+8)", "a Ring of Strength (+3)"))]
    return got == [(0, 6, 0), (8, 0, 0), (0, 0, 3)], f"{got}"


@case
def better_ac_by_geareval():
    """D13 (the user, 11-01): "better AC than worn" (gear_line, the gear review's shop ideas, upgrade_step step 3) is
    the gear evaluator's verdict -- more AC, every ability and resist kept, no >5% EHP loss -- and a plain AC
    comparison only for a piece geareval can't read. A Metal Scale Mail [38,+5] doesn't replace the Hard Studded
    Leather of Resistance; a Leather Shield [8,+9] replaces the [8,+2]; an unreadable piece goes by its AC."""
    worn = [("a Spear (1d6) (+5,+7)", 22, 50), ("Hard Studded Leather of Resistance (-1) [7,+9]", 37, 200),
            ("a Leather Shield [8,+2]", 34, 60)]
    p = pilot(pack=[("a Metal Scale Mail [38,+5]", 37), ("a Leather Shield [8,+9]", 34)], worn=worn)
    p.w.ind.update({"stat1": [10], "stat2": [10], "stat4": [18]})
    on = {tv: [i for i in p.w.items(equip=True) if i["tval"] == tv] for tv in (34, 37)}
    mail = p.ac_better("a Metal Scale Mail [38,+5]", on[37], 37, 250)[0]
    shield = p.ac_better("a Leather Shield [8,+9]", on[34], 34, 60)[0]
    odd = p.ac_better("a Glittering Buckler [12,+0]", on[34], 34, 60)[0]
    line = p.gear_line()
    ok = not mail and shield and odd and "Leather Shield [8,+9] (AC 17 vs 10 worn)" in line and "Metal" not in line
    return ok, f"mail {mail}, shield {shield}, unreadable {odd}; {line}"


def _m67_character():
    """Dive04 as in m67 (clvl 30: a warrior's own resist fear, CF_BRAVERY_30; the grid's '@'), an Amulet of Slow
    Digestion worn, the ability terms from the seed rates."""
    import geareval as GE
    worn = {}
    for n in GE.DIVE04_WORN:
        it = GE.Item(n)
        worn.setdefault(it.slot, []).append(it)
    worn["amulet"] = [GE.Item("an Amulet of Slow Digestion")]
    ch = GE.Character(30, {"STR": 88, "INT": 5, "WIS": 8, "DEX": 38, "CON": 38, "CHR": 4}, mhp=340, ac=76, worn=worn,
                      flags={"FREE_ACT", "SEE_INVIS", "RES_FIRE", "RES_COLD", "RES_ELEC", "RES_ACID", "RES_DARK",
                             "RES_FEAR", "SLOW_DIGEST"}, depth_ft=750, inv=dict(ccw=20, phase=18, wor=2),
                      intrinsic={"RES_DARK", "RES_FEAR"})
    ch.xp_per_dmin = 44.5
    ch.ability_worth = GE.ability_worth(ch, None, None, 0.41, ch.xp_per_dmin, None)
    return GE, ch


@case
def gear_abilities_valued_m67():
    """2.64.0, m67: `gearcmp Weaponmastery` put an Amulet of Weaponmastery (+2,+2) (+1) (STR, sustain STR/CON, Free
    Action, resist fear and disenchantment) only +3.9% over Slow Digestion -- the abilities the simulator doesn't play
    counted for nothing. Now each is a term (XP per dungeon minute from the log's rates: disenchantments x the cost to
    put a plus back, drains x a Restore + the damage lost, ...) added to the score; the diff names what the loadout
    has anyway (resist fear: the clvl-30 warrior's own; Free Action: the weapon's) -- no term for those. The amulet
    comes out clearly ahead: the terms add over 8% to the simulated gain."""
    GE, ch = _m67_character()
    res = GE.compare_slot(ch, [GE.Item("an Amulet of Weaponmastery (+2,+2) (+1)")], hard=False, depth_n=60, n=3)
    k = res["options"][1]
    r = res["rules"][k]
    terms = {f: x for f, x, _ in r["terms"]}
    text = GE.report(res)
    share = res["ability_adj"][k] / res["sim_score"]["current"]
    ok = res["best"] == k and set(r["gained"]) == {"RES_DISEN", "SUST_STR", "SUST_CON"} and \
        r["lost"] == ["SLOW_DIGEST"] and ("RES_FEAR", "yourself") in r["redundant"] and \
        ("FREE_ACT", "weapon") in r["redundant"] and "RES_FEAR" not in terms and terms["RES_DISEN"] > 1 and \
        terms["SUST_STR"] > 1 and -0.1 < terms["SLOW_DIGEST"] < 0 and share > 0.08 and \
        "resist fear (yourself)" in text and "resist disenchantment: +" in text and "+ abilities +" in text
    return ok, f"terms {terms}; abilities {share:+.1%} of the score; redundant {r['redundant']}; best {res['best']}"


@case
def gear_ability_terms_from_rates():
    """2.64.0: the ability terms from a rates file (observe/ability_rates.py): resist fear = the time afraid + the
    potions quaffed for it; resist disenchantment = plusses taken x the cost to put one back (the Pilot's disen_loss);
    sustains = drains x the Restore (+ the damage a STR drain costs for DRAINED_H); none of it for an ability every
    option has; the Pilot's ability_worth falls back to the seed rates without the file."""
    import geareval as GE
    GE_, ch = _m67_character()
    rates = {"dungeon_h": 10, "counts": {"fear": 20, "afraid_s": 600, "disenchanted": 5, "food": 10},
             "drained": {"STR": 5}, "cures": {"fear": {"Heroism": 10}}}
    w = GE.ability_worth(ch, rates, {"Heroism": 60}, 0.5, 50.0, 400)
    fear = w["RES_FEAR"]
    # fear: 60 s afraid an hour = 1 min of 60 at 50 XP/min (0.83) + 1 Heroism an hour, 60 g x 0.5 / 60 (0.5)
    ok_fear = abs(fear["xpm"] - (50 / 60 + 0.5)) < 0.01 and "2.0 fear episodes/hour" in fear["text"]
    ok_dis = abs(w["RES_DISEN"]["xpm"] - 0.5 * 400 * 0.5 / 60) < 0.01
    s = w["SUST_STR"]
    ok_str = s["gold_h"] == 0.5 * 490 and s["min_h"] > 0 and w["SUST_DEX"]["xpm"] == 0
    lose = GE.ability_terms(ch, {"SUST_STR", "RES_FEAR"}, {"RES_FEAR"})
    same = GE.ability_terms(ch, {"RES_FEAR"}, {"RES_FEAR"})
    p = pilot()
    p.w.clvl = 30
    p.w.flags = {"free_act": "a", "res_fear": "@"}
    pc = p.gear_character()
    ok_p = "RES_FEAR" in pc.intrinsic and "RES_DISEN" in pc.ability_worth and "seed" in pc.ability_src and \
        pc.xp_per_dmin > 0
    ok = ok_fear and ok_dis and ok_str and [f for f, _, _ in lose] == ["SUST_STR"] and lose[0][1] < 0 and not same \
        and ok_p
    return ok, f"fear {fear}; disen {w['RES_DISEN']['xpm']}; STR {s}; losing sustain STR {lose}; the Pilot: " \
               f"intrinsic {pc.intrinsic}, {pc.ability_src}, {pc.xp_per_dmin} XP/dmin"


@case
def geareval_flag_names():
    """2.64.0: every ability and resist the character sheet's grid shows (c-tool.c's flag names) has its F: name in
    the game's object/ego/artifact files and a label in the gear diff (the grid's perm_lite is LITE: 'permanent
    light'); every RES_/IM_/SUST_ flag in those files is an ability the diff shows; an intrinsic flag ('@') is kept by
    a loadout that takes off the piece also giving it."""
    import geareval as GE
    grid = ("res_acid res_elec res_fire res_cold res_pois res_fear res_lite res_dark res_blind res_conf res_sound "
            "res_shard res_nexus res_nether res_chaos res_disen slow_digest feather perm_lite regen telepathy "
            "see_invis free_act hold_life").split()
    fl = set()
    for f in ("object.txt", "ego_item.txt", "artifact.txt"):
        for line in open(os.path.join(GE.LIB, f)):
            if line.startswith("F:"):
                fl |= {x.strip() for x in line[2:].split("|") if x.strip()}
    names = {g: GE.SHEET_FLAG.get(g.upper(), g.upper()) for g in grid}
    unknown = [g for g, n in names.items() if n not in fl]
    unlabelled = [n for n in names.values() if n not in GE.LABEL and not GE.label(n).startswith(("resist ", "immune "))]
    res = {f for f in fl if f.startswith(("RES_", "IM_", "SUST_"))}
    fake = GE.Item("Ring of Protection [+12]")
    fake.flags = res | {"LITE"}
    not_shown = sorted((res | {"LITE"}) - fake.abilities())
    worn = {"amulet": [GE.Item("an Amulet of Weaponmastery (+2,+2) (+1)")]}
    ch = GE.Character(30, {"STR": 98, "INT": 5, "WIS": 8, "DEX": 38, "CON": 38, "CHR": 4}, mhp=340, ac=10, worn=worn,
                      flags={"RES_FEAR", "RES_DISEN", "FREE_ACT"}, intrinsic={"RES_FEAR"})
    off = ch.derive({})
    ok = not unknown and not unlabelled and not not_shown and "RES_FEAR" in off["flags"] and \
        "RES_DISEN" not in off["flags"]
    return ok, f"grid names not in the files: {unknown}; unlabelled: {unlabelled}; not in the diff: {not_shown}; " \
               f"amulet off: resist fear kept {'RES_FEAR' in off['flags']}"
