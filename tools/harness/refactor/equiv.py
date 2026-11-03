"""tick() equivalence: the real Pilot (its __init__, World and Mover) on a fake client through scripted game states,
recording every command sent, every notice and every log record. python3 equiv.py PILOT_DIR OUT.json [NAME...]
(run with PYTHONHASHSEED=0; compare the OUT files of the old and new trees).

64 states: the 33 of E1 step 4 (town, supplies, queries, plans) and 31 combat_* states of step 5 (groups, uniques,
unseen attackers, low HP with and without Phase/Teleport/Speed, fear with and without a cure, Speed/Berserk, thieves,
breeders, a drainer and a drain, traps, a corridor choke, hound packs, a walk to the stairs under attack, stairs
underfoot, molds, a summoner, a confusion lock, blind with two adjacent, slowed, engage, the emergency loop, no stairs).
35 combat_e3_* states (E3, the reflexes()/escape() split) for the branches those leave unreached: death and
resurrection, arrival into danger, the slow-caster exception, a summoner listed before the map shows it, fear on
arrival and kiting, molds by the goto's square and by the stairs, repeat fearers, town light, Satisfy Hunger, the
pickup cases, resting, the escape's out-of-combat rest/retreat, the caster kill and potions too weak: 99 states,
every line of the old reflexes and all but one of escape (refactor-candidates E3).
69 *_e5_* states (E5, the town goals' and the trip plan's ticks split): HouseBank (withdraw, deposit with the stash,
a Restore fetched or gone, buy and its four failures, a shut door, trapped inside, an unseen drop, a town house, odd
steps), Shop (sales refused/forced/quoted/by the Architect, overrides revoked, buys rich/poor/full/unlisted/silent, no
listing, walled in, stuck, thrown out), TownKit (each stage from a set-up kit: tavern fetch, upgrades, identify, broke
by day/night, make room, quaff/provision, restock wait, recharge/enchant, stash, deposit, finish) and TripPlan (each
phase and watchdog): 168 states; the four ticks' every line but a dead fall-through each (HouseBank all).
5 *_fix_* states (2.45.0, behaviour fixes: they differ from 2.44.x on purpose): no light to read Satisfy Hunger by,
then rest or pickup; the escape walk reaching its stairs with the threat out of view, and outliving its emergency;
a withdraw's fetched Restore struck off the house record at once: 173 states.
Schedule actions: req, ev, pos, depth, step (move with a pos event), hp, mons, ind, msg, ghost, fn (fn(p, c): set
up a goal, a plan or the Pilot's state). A state's `react=lambda: Server(...)` answers its commands (shop trades, the
house's pile and door: see Server).
Coverage: EQUIV_COVER=COV.json [EQUIV_COVER_FUNCS="reflexes escape"] records the lines (from each def) run per state
in the named functions (a bare name, a qualname such as TownKit.tick, or a pattern such as "TownKit.*");
covreport.py COV.json prints it per state; uncovered.py the lines no state reaches. Run from a copy next to a rundir_template/ (see
fake.py)."""
import fnmatch
import json
import os
import queue
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake  # noqa: E402
from fake import item, Clock  # noqa: E402

pilot_dir, out = os.path.abspath(sys.argv[1]), sys.argv[2]
only = sys.argv[3:]
P = fake.load(pilot_dir)
import world as W  # noqa: E402
import glyphs  # noqa: E402

TREE = os.path.dirname(os.path.dirname(pilot_dir))
G = glyphs.Glyphs()
GLYPH = {}
for k, v in G.by_glyph.items():
    GLYPH.setdefault(G.races[v].name, k)
T0 = 1793653200.0
TOKEN = "tok-e1s4"


def lantern(turns):
    return f"a Brass Lantern (with {turns} turns of light)"


def pack(rations=4, flasks=3, ccw=5, csw=4, clw=5, phase=12, wor=3, extra=(), heroism=3, speed=2, staff=1):
    rows = [(f"{rations} Rations of Food", 80, rations), (f"{flasks} Flasks of oil", 77, flasks),
            (f"{ccw} Potions of Cure Critical Wounds", 75, ccw), (f"{csw} Potions of Cure Serious Wounds", 75, csw),
            (f"{clw} Potions of Cure Light Wounds", 75, clw), (f"{heroism} Potions of Heroism", 75, heroism),
            (f"{speed} Potions of Speed", 75, speed), (f"{phase} Scrolls of Phase Door", 70, phase),
            (f"{wor} Scrolls of Word of Recall", 70, wor), ("a Staff of Teleportation (5 charges)", 55, staff)]
    rows += list(extra)
    rows = [r for r in rows if r[2]]
    return [item(i, n, tv, num) for i, (n, tv, num) in enumerate(rows)]


def worn(light=lantern(9000)):
    rows = [("a Scimitar of Westernesse (2d5) (+10,+12) [+0]", 23, 130), ("a Ring of Protection [+16]", 45, 1),
            ("an Amulet of Slow Digestion", 40, 3), ("Hard Studded Leather of Resistance (-1) [16,+12]", 37, 200),
            ("a Leather Shield [8,+5]", 34, 60), ("a Hard Leather Cap [2,+3]", 32, 15),
            ("a Set of Leather Gloves [1,+2]", 31, 10), ("a Pair of Leather Boots [2,+3]", 30, 20),
            ("a Cloak [1,+2]", 35, 10)]
    if light:
        rows.insert(1, (light, 39, 50))
    return [item(24 + i, n, tv, 1, wt, equip=True) for i, (n, tv, wt) in enumerate(rows)]


def mon(name, y, x):
    return (y, x, GLYPH[name])


def req(cmd, *args, arch=False):
    r = {"cmd": cmd, "args": list(args), "role": "architect" if arch else "navigator"}
    if arch:
        r["token"] = TOKEN
    return ("req", r)


def ev(e):
    return ("ev", e)


TOWN = dict(depth=0, pos=(20, 40), stairs={(16, 45): ">"}, extra={(30, 60): "5", (30, 20): "1", (12, 70): "4",
                                                                    (27, 89): "8"}, room=(0, 0, 65, 197))
STORES = {"5": {"ev": "store", "name": "Alchemist", "owner": "Mauser the Chemist (Half-Elf)",
                "items": [{"name": "a Potion of Cure Light Wounds", "price": 24, "number": 20},
                          {"name": "5 Scrolls of Word of Recall", "price": 210, "number": 5},
                          {"name": "a Potion of Restore Strength", "price": 480, "number": 1},
                          {"name": "Scrolls of Phase Door", "price": 23, "number": 20}]},
          "4": {"ev": "store", "name": "Temple", "owner": "Ludwig the Humble (Dwarf)",
                "items": [{"name": "Potions of Cure Critical Wounds", "price": 159, "number": 10},
                          {"name": "Potions of Cure Serious Wounds", "price": 60, "number": 10}]},
          "1": {"ev": "store", "name": "General store", "owner": "Bilbo the Friendly (Hobbit)",
                "items": [{"name": "Rations of Food", "price": 4, "number": 30},
                          {"name": "Flasks of oil", "price": 4, "number": 30}]}}
for _num, _st in STORES.items():
    _st.update(flag=0, num=len(_st["items"]))
    for _i, _it in enumerate(_st["items"]):
        _it.update(slot=_i, weight=5)
DUNGEON = dict(depth=6, pos=(20, 40), stairs={(10, 70): ">", (35, 10): "<"})

SCENARIOS = [
    # name, client kwargs (inven=pack+worn), schedule {tick: [actions]}, ticks, dt, template rundir
    ("town_idle", dict(TOWN), {}, 40, 0.5),
    ("town_weak_hunger", dict(TOWN, hunger=1), {}, 30, 0.4),
    ("town_dark_lantern", dict(TOWN, light=lantern(0)), {}, 30, 0.4),
    ("town_plan_town_short", dict(TOWN, gold=3000, wor=1, ccw=0, phase=2), {2: [req("plan", "town")]}, 80, 0.3),
    ("town_plan_town_full_pack", dict(TOWN, gold=2500, wor=1, extra_pack=[(f"a Potion of Junk{i}", 75, 1) for i in range(13)]),
     {2: [req("plan", "town")]}, 80, 0.3),
    ("town_queries", dict(TOWN, extra_pack=[("a Wand of Stinking Cloud (8 charges)", 65, 1),
                                            ("a Ring of Teleportation", 45, 1)]),
     {1: [req("price", "c")], 2: [req("price", "k")], 3: [req("house")], 4: [req("status")], 5: [req("prep")],
      6: [req("price", "Speed")], 7: [req("why")]}, 20, 0.5),
    ("town_store_alchemist", dict(TOWN, pos=(30, 62)),
     {2: [req("goal", "shop", "5", "buy", "Phase Door:3", "list")]}, 40, 0.4),
    ("town_plan_town_long", dict(TOWN, gold=1500, wor=1, ccw=1, rations=0, light=lantern(4000),
                                 extra_pack=[("a Wand of Stinking Cloud (8 charges)", 65, 1),
                                             ("2 Pieces of Elvish Waybread", 80, 2)]),
     {2: [req("plan", "town", arch=True)]}, 300, 0.4),
    ("town_plan_town_nohouse", dict(TOWN, nohouse=True, gold=1500, wor=1, ccw=1, rations=0, light=lantern(4000),
                                    extra_pack=[("a Wand of Stinking Cloud (8 charges)", 65, 1),
                                                ("2 Pieces of Elvish Waybread", 80, 2),
                                                ("a Staff of Detect Evil (0 charges)", 55, 1)]),
     {2: [req("plan", "town", arch=True)]}, 250, 0.4),
    ("town_stash_drained_arch", dict(TOWN, gold=2000), {2: [req("plan", "town", arch=True)]}, 60, 0.3),
    ("town_edge_walk", dict(TOWN, pos=(6, 40)),
     {3: [("pos", (1, 40))], 5: [ev({"ev": "level", "depth": -1}), ("depth", -1), ("pos", (64, 40))],
      7: [req("house")]}, 15, 0.5),
    ("town_no_files", dict(TOWN, template=False), {}, 20, 0.5),
    ("town_house_deposit", dict(TOWN, gold=5000), {2: [req("house", "deposit", arch=True)]}, 60, 0.3),
    ("dungeon_quiet", dict(DUNGEON), {}, 40, 0.5),
    ("dungeon_no_food", dict(DUNGEON, rations=0, hunger=2), {}, 30, 0.5),
    ("dungeon_food_low", dict(DUNGEON, rations=0, hunger=1), {}, 30, 0.5),
    ("dungeon_light_low", dict(DUNGEON, light=lantern(500), flasks=0), {}, 30, 0.5),
    ("dungeon_dark_lantern_flask", dict(DUNGEON, light=lantern(0)), {}, 30, 0.4),
    ("dungeon_torch", dict(DUNGEON, light="a Wooden Torch (with 1500 turns of light)", flasks=0,
                           extra_pack=[("2 Wooden Torches (with 2500 turns of light)", 39, 2)]), {}, 30, 0.5),
    ("dungeon_adjacent_orc", dict(DUNGEON, monsters=[mon("Cave orc", 20, 41)]), {}, 30, 0.3),
    ("dungeon_danger_in_view", dict(DUNGEON, depth=3, monsters=[mon("Young blue dragon", 20, 48)]), {}, 30, 0.3),
    ("dungeon_low_hp_adjacent", dict(DUNGEON, hp=(90, 358), monsters=[mon("Black orc", 20, 41),
                                                                     mon("Black orc", 21, 41)]), {}, 30, 0.3),
    ("dungeon_low_hp_alone", dict(DUNGEON, hp=(200, 358)), {}, 30, 0.5),
    ("dungeon_pack_in_view", dict(DUNGEON, monsters=[mon("Snaga", 12, 50 + i) for i in range(6)]), {}, 30, 0.3),
    ("dungeon_confused_adjacent", dict(DUNGEON, ind={"confused": [1]}, monsters=[mon("Cave orc", 20, 41)]), {}, 30, 0.3),
    ("dungeon_afraid_adjacent", dict(DUNGEON, ind={"afraid": [1]}, monsters=[mon("Wolf", 21, 40)]), {}, 30, 0.3),
    ("dungeon_poisoned_blind", dict(DUNGEON, ind={"poisoned": [1], "blind": [1]}, hp=(250, 358)), {}, 30, 0.4),
    ("dungeon_goal_explore", dict(DUNGEON), {2: [req("goal", "explore")]}, 60, 0.3),
    ("dungeon_plan_trip", dict(DUNGEON, depth=5), {2: [req("plan", "trip", "250-500", arch=True)]}, 60, 0.4),
    ("dungeon_recall_and_queries", dict(DUNGEON, wor=1),
     {2: [req("goal", "recall")], 4: [req("why")], 5: [req("prep")], 6: [req("status")], 7: [req("gate", "500")]},
     40, 0.4),
    ("dungeon_floor_item", dict(DUNGEON, floor="a Potion of Cure Light Wounds", extra_map={(20, 40): "!"}), {}, 30, 0.4),
    ("dungeon_recall_pending_full", dict(DUNGEON, hunger=4, rations=6, flasks=5),
     {1: [ev({"ev": "message", "text": "The air about you becomes charged..."})]}, 30, 0.5),
    ("dungeon_idle_long", dict(DUNGEON), {}, 30, 30.0),
]



# --- combat states (E1 step 5, combat.py): drive reflexes() and escape() down different branches --------------------
def sched(*parts):
    """Merge schedules {tick: [actions]}."""
    out = {}
    for p in parts:
        for t, acts in p.items():
            out.setdefault(t, []).extend(acts)
    return out


def hits(text, ticks, hp=None):
    """A message at each tick (`The Cave orc hits you.`), and HP falling to hp[i] at the same ticks."""
    out = {t: [("msg", text)] for t in ticks}
    for t, h in zip(ticks, hp or ()):
        out[t].append(("hp", h))
    return out


def ring(name, n, cy=20, cx=40):
    """n monsters on the 8 squares around (cy, cx)."""
    sq = [(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]
    return [mon(name, cy + dy, cx + dx) for dy, dx in sq[:n]]


BERSERK = [("a Potion of Berserk Strength", 75, 1)]
TELE_SCROLLS = [("3 Scrolls of Teleportation", 70, 3)]
# a one-wide corridor west of the start (walls above and below x 26..34 on row 20), stone trolls coming from the east
CORRIDOR = {**{(19, x): "#" for x in range(26, 35)}, **{(21, x): "#" for x in range(26, 35)}}
COMBAT = [
    ("combat_group_adjacent", dict(DUNGEON, monsters=ring("Black orc", 3) + [mon("Black orc", 20, 44), mon("Black orc", 19, 45),
                                                                            mon("Black orc", 21, 45)]),
     hits("The Black orc hits you.", (3, 6, 9, 12), (340, 320, 300, 285)), 30, 0.3),
    ("combat_unique_in_view", dict(DUNGEON, monsters=[mon("Bert the Stone Troll", 20, 48)]), {}, 30, 0.3),
    ("combat_unique_adjacent_hard", dict(DUNGEON, monsters=[mon("Ulfast, Son of Ulfang", 20, 41)], extra_pack=BERSERK),
     hits("Ulfast, Son of Ulfang hits you.", (2, 5, 8), (340, 330, 320)), 30, 0.3),
    ("combat_unseen_attacker", dict(DUNGEON),
     hits("It hits you.", (2, 4, 6, 8, 10), (340, 320, 300, 280, 260)), 30, 0.3),
    ("combat_low_hp_phase_futile", dict(DUNGEON, hp=(150, 358), monsters=[mon("Cave orc", 20, 41)]),
     hits("The Cave orc hits you.", range(1, 60, 4)), 60, 0.3),
    ("combat_low_hp_no_phase_no_staff", dict(DUNGEON, hp=(160, 358), phase=0, staff=0, speed=0,
                                             monsters=[mon("Black orc", 20, 41)]),
     hits("The Black orc hits you.", range(1, 40, 3), [150 - 6 * i for i in range(14)]), 40, 0.3),
    ("combat_low_hp_crowd_teleport", dict(DUNGEON, hp=(150, 358), speed=0, extra_pack=TELE_SCROLLS,
                                          monsters=ring("Snaga", 2) + [mon("Snaga", 22, 43), mon("Snaga", 18, 43),
                                                                       mon("Snaga", 23, 40)]),
     hits("The Snaga hits you.", range(1, 30, 3)), 30, 0.3),
    ("combat_hp_collapse_recall", dict(DUNGEON, hp=(90, 358), speed=0, monsters=[mon("Hill orc", 20, 41)]),
     hits("The Hill orc hits you.", range(1, 30, 3)), 30, 0.3),
    ("combat_one_turn_from_death", dict(DUNGEON, hp=(40, 358), monsters=[mon("Ulfang the Black", 20, 41)]),
     hits("Ulfang the Black hits you.", range(1, 20, 3)), 20, 0.3),
    ("combat_afraid_cure", dict(DUNGEON, ind={"afraid": [1]}, monsters=ring("Cave orc", 2)),
     hits("The Cave orc hits you.", range(1, 30, 4)), 30, 0.3),
    ("combat_afraid_no_cure_rule", dict(DUNGEON, ind={"afraid": [1]}, heroism=0, monsters=ring("Cave orc", 2)),
     sched({1: [req("react", "afraid", "teleport")]}, hits("The Cave orc hits you.", range(2, 30, 4))), 30, 0.3),
    ("combat_afraid_no_cure_phase", dict(DUNGEON, ind={"afraid": [1]}, heroism=0, monsters=ring("Cave orc", 2)),
     hits("The Cave orc hits you.", range(1, 30, 4)), 30, 0.3),
    ("combat_thief_adjacent", dict(DUNGEON, monsters=[mon("Brigand", 20, 41), mon("Cave orc", 21, 41)]),
     hits("The Brigand touches you.", (2, 6)), 30, 0.3),
    ("combat_breeder_swarm", dict(DUNGEON, monsters=[mon("Giant black louse", 14 + i % 3, 44 + 2 * i) for i in range(9)]),
     {}, 30, 0.3),
    ("combat_drainer_stat_drain", dict(DUNGEON, monsters=[mon("Killer red beetle", 20, 45)]),
     {8: [("ind", ("stat0", [50, 68])), ("msg", "You feel very weak.")]}, 30, 0.3),
    ("combat_summon_trap_darts", dict(DUNGEON),
     {2: [("msg", "You are enveloped in a cloud of smoke!"),
          ("mons", ring("Black orc", 3))], 6: [("msg", "A small dart hits you!")],
      10: [("msg", "A small dart hits you!")]}, 30, 0.3),
    ("combat_trap_door", dict(DUNGEON),
     {2: [("msg", "You fall through a trap door!")], 3: [ev({"ev": "level", "depth": 7}), ("depth", 7)]}, 20, 0.4),
    ("combat_corridor_choke", dict(DUNGEON, extra=CORRIDOR,
                                   monsters=[mon("Stone troll", 20, 48), mon("Stone troll", 19, 49),
                                             mon("Stone troll", 21, 49), mon("Stone troll", 20, 50)]), {}, 40, 0.3),
    ("combat_hound_pack_dangerous", dict(DUNGEON, monsters=[mon("Vibration hound", 18 + i, 46 + i % 2) for i in range(5)]),
     {}, 30, 0.3),
    ("combat_hound_pack_breathers", dict(DUNGEON, ind={"level": [20, 20]}, hp=(200, 200),
                                         monsters=[mon("Fire hound", 17 + i, 45 + i % 2) for i in range(6)]),
     {}, 30, 0.3),
    ("combat_already_fleeing_to_stairs", dict(DUNGEON, hp=(150, 358), stairs={(20, 52): ">", (35, 10): "<"},
                                              monsters=[mon("Cave orc", 20, 37)]),
     hits("The Cave orc hits you.", range(0, 40, 2)), 40, 0.3),
    ("combat_stairs_underfoot", dict(DUNGEON, hp=(150, 358), pos=(34, 11),
                                     monsters=[mon("Hill orc", 33, 12), mon("Hill orc", 34, 13)]),
     sched({1: [("step", (35, 10))]}, hits("The Hill orc hits you.", (0, 2, 4))), 20, 0.3),
    ("combat_mold_adjacent", dict(DUNGEON, monsters=[mon("Disenchanter mold", 20, 41), mon("Floating eye", 21, 39)]),
     {}, 30, 0.3),
    ("combat_summoner_in_view", dict(DUNGEON, monsters=[mon("Ogre mage", 20, 49)]), {}, 30, 0.3),
    ("combat_confused_swarm", dict(DUNGEON, ind={"confused": [1]}, monsters=ring("Cave orc", 3)),
     sched(hits("The Cave orc hits you.", range(0, 45, 3)), {32: [("ind", ("confused", [0]))]}), 45, 0.3),
    ("combat_blind_two_adjacent_low_hp", dict(DUNGEON, ind={"blind": [1]}, hp=(150, 358), speed=0,
                                              monsters=ring("Black orc", 2)),
     hits("It hits you.", range(1, 30, 2), [150 - 5 * i for i in range(15)]), 30, 0.3),
    ("combat_slowed_adjacent", dict(DUNGEON, ind={"speed": [-10]}, monsters=[mon("Cave orc", 20, 41)]),
     hits("The Cave orc hits you.", range(1, 20, 3)), 20, 0.3),
    ("combat_engage_worthwhile", dict(DUNGEON, monsters=[mon("Hill giant", 20, 44)]), {2: [req("goal", "explore")]},
     40, 0.3),
    ("combat_emergency_loop", dict(DUNGEON, hp=(150, 358), speed=0, monsters=ring("Black orc", 2)),
     hits("The Black orc hits you.", range(0, 120, 3)), 120, 0.5),
    ("combat_flee_no_stairs", dict(DUNGEON, stairs={}, monsters=[mon("Bert the Stone Troll", 20, 52)]), {}, 40, 0.3),
    ("combat_band_no_stairs_locator", dict(DUNGEON, stairs={}, extra_pack=[("a Staff of Door/Stair Location (5 charges)",
                                                                             55, 1)],
                                           monsters=[mon("Black orc", 15 + i, 47 + i % 2) for i in range(6)]),
     {2: [req("goal", "leave")]}, 40, 0.3),
]
SCENARIOS += COMBAT


# --- E3 states (the reflexes()/escape() split): the branches the 64 states above leave unreached ------------------
def walk_west(n, t0=1, y=20, x=40):
    """n steps west from (y, x), one a tick from t0 (walked ground for the retreats)."""
    return {t0 + i: [("step", (y, x - 1 - i))] for i in range(n)}


def wobble(t0, t1, hi, lo, msg=None):
    """HP alternating hi/lo each tick (damage_rate counts the drops only), with a hit message at each drop."""
    out = {}
    for t in range(t0, t1):
        out[t] = [("hp", lo if (t - t0) % 2 else hi)] + ([("msg", msg)] if msg and (t - t0) % 2 else [])
    return out


SATISFY = [("a Scroll of Satisfy Hunger", 70, 1)]
LOOK = "You see a Potion of Cure Light Wounds."
FAR_STAIRS = {(35, 10): "<"}
COMBAT_E3 = [
    ("combat_e3_death_ghost_resurrect", dict(DUNGEON),
     {2: [("hp", 0)], 4: [("ghost", True)], 5: [req("goal", "resurrect")], 12: [("ghost", False), ("hp", 300)]},
     20, 0.3),
    ("combat_e3_emergency_mover_stop", dict(DUNGEON, stairs=FAR_STAIRS, ccw=0, csw=0, clw=0, speed=0,
                                            monsters=[mon("Cave orc", 20, 58)]),
     sched({1: [req("goal", "goto", "20", "75", arch=True)]},
           {6: [("hp", 160), ("msg", "The Cave orc hits you.")], 8: [("msg", "The Cave orc hits you.")]}), 14, 0.3),
    ("combat_e3_stairs_not_threatened", dict(DUNGEON, pos=(34, 11)),
     {1: [("step", (35, 10)), ("msg", "It hits you.")], 9: [("hp", 150)]}, 14, 0.3),
    ("combat_e3_escape_rest_alone", dict(DUNGEON),
     {1: [("msg", "It hits you.")], 13: [("hp", 150)]}, 18, 0.3),
    ("combat_e3_escape_retreat_in_view", dict(DUNGEON, hp=(150, 358), monsters=[mon("Cave orc", 20, 46)]),
     walk_west(4), 12, 0.3),
    ("combat_e3_group_stairs_underfoot", dict(DUNGEON, pos=(34, 11)),
     {1: [("step", (35, 10))], 2: [("mons", [mon("Hill giant", 33, 9), mon("Hill giant", 33, 11),
                                             mon("Hill giant", 36, 12), mon("Hill giant", 37, 9)])]}, 8, 0.3),
    ("combat_e3_stun_cure", dict(DUNGEON, ind={"stun": [2]}, monsters=[mon("Cave orc", 20, 41)]), {}, 8, 0.3),
    ("combat_e3_arrival_danger", dict(DUNGEON, pos=(34, 11)),
     {1: [ev({"ev": "level", "depth": 7}), ("depth", 7)], 2: [("step", (35, 10)), ("mons", [mon("Mind flayer", 31, 14)])]},
     8, 0.3),
    ("combat_e3_slow_caster_far_stairs", dict(DUNGEON, monsters=[mon("Mind flayer", 20, 49)]), {}, 12, 0.3),
    ("combat_e3_summoner_listed_only", dict(DUNGEON),
     {1: [ev({"ev": "monlist", "lines": ["Ogre mage ('O')/('O'):[1]"]})], 9: [("mons", [mon("Ogre mage", 20, 50)])]},
     16, 0.3),
    ("combat_e3_summoner_while_walking", dict(DUNGEON),
     {1: [req("goal", "goto", "35", "70", arch=True)], 4: [("mons", [mon("Ogre mage", 28, 66)])]}, 14, 0.3),
    ("combat_e3_unseen_flee", dict(DUNGEON, hp=(250, 358)),
     {2: [("msg", "It hits you."), ("hp", 240)]}, 8, 0.3),
    ("combat_e3_afraid_on_arrival", dict(DUNGEON, pos=(34, 11), ind={"afraid": [1]}),
     {1: [ev({"ev": "level", "depth": 7}), ("depth", 7)],
      2: [("step", (35, 10)), ("mons", [mon("Cave orc", 33, 12), mon("Cave orc", 32, 13)])]}, 6, 0.3),
    ("combat_e3_afraid_kite", dict(DUNGEON, ind={"afraid": [1]}),
     sched(walk_west(5), {6: [("step", (20, 36))], 7: [("step", (20, 37))], 8: [("step", (20, 38))],
                          9: [("mons", [mon("Cave orc", 20, 43)])]}), 18, 0.3),
    ("combat_e3_mold_blocks_goto", dict(DUNGEON, monsters=[mon("Grey mold", 19, 45)]),
     {1: [req("goal", "goto", "20", "46", arch=True)]}, 16, 0.3),
    ("combat_e3_mold_beside_stairs", dict(DUNGEON, stairs={(20, 46): ">", (35, 10): "<"},
                                          monsters=[mon("Grey mold", 21, 46)]),
     {1: [req("goal", "goto", ">", arch=True)]}, 16, 0.3),
    ("combat_e3_fearer_phase_retreat", dict(DUNGEON, speed=0, ind={"level": [28, 28]}),
     sched(walk_west(6), {7: [("step", (20, 35))], 8: [("mons", [mon("Troll priest", 20, 34)])]}), 22, 0.3),
    ("combat_e3_fearer_retreat", dict(DUNGEON, speed=0),
     sched(walk_west(6), {7: [("step", (20, 35))], 8: [("mons", [mon("Troll priest", 20, 31)])]}), 16, 0.3),
    ("combat_e3_town_light_off", dict(TOWN), {}, 70, 0.5),
    ("combat_e3_satisfy_hunger_dark", dict(TOWN, rations=0, hunger=1, light=None,
                                           extra_pack=[(lantern(9000), 39, 1)] + SATISFY), {}, 6, 0.4),
    ("combat_e3_satisfy_hunger_read", dict(DUNGEON, rations=0, hunger=1, extra_pack=SATISFY), {}, 8, 0.4),
    ("combat_e3_adjacent_resting_hurt", dict(DUNGEON, hp=(210, 358), ind={"state": [0, 0, 1]},
                                             monsters=[mon("Cave orc", 20, 41)]), {}, 8, 0.3),
    ("combat_e3_townfarm_thief", dict(TOWN, monsters=[mon("Filthy street urchin", 20, 41)]),
     {1: [req("goal", "townfarm", "100")]}, 8, 0.3),
    ("combat_e3_pickup_here", dict(DUNGEON, floor="a Potion of Cure Light Wounds", extra_map={(20, 40): "!"}),
     {2: [("msg", LOOK)]}, 8, 0.3),
    ("combat_e3_pickup_while_walking", dict(DUNGEON), {1: [req("goal", "goto", "20", "75", arch=True)],
                                                       5: [("msg", LOOK)]}, 10, 0.3),
    ("combat_e3_floor_junk", dict(DUNGEON, floor="a Potion of Salt Water", extra_map={(20, 40): "!"}),
     {2: [("msg", "You see a Potion of Salt Water.")]}, 8, 0.3),
    ("combat_e3_nopickup_then_skipped", dict(DUNGEON, floor="a Potion of Cure Light Wounds", extra_map={(20, 40): "!"}),
     {1: [req("order", "nopickup=Cure")], 3: [("msg", LOOK)]}, 8, 0.3),
    ("combat_e3_town_stash_item", dict(TOWN, floor="a Potion of Restore Strength", extra_map={(20, 40): "!"}),
     {2: [("msg", "You see a Potion of Restore Strength.")]}, 6, 0.3),
    ("combat_e3_fleeing_cheap_find", dict(DUNGEON, monsters=[mon("Bert the Stone Troll", 20, 48)]),
     {4: [("msg", LOOK)]}, 8, 0.3),
    ("combat_e3_pack_full_msg", dict(DUNGEON), {2: [("msg", "You have no room for a Potion of Cure Light Wounds.")]},
     6, 0.3),
    ("combat_e3_rest_stop_and_keep", dict(DUNGEON, hp=(340, 358), ind={"state": [0, 0, 1]}), {6: [("hp", 358)]},
     10, 0.3),
    ("combat_e3_kill_caster", dict(DUNGEON, hp=(150, 358), speed=0, monsters=[mon("Priest", 20, 41)]),
     hits("The Priest hits you.", range(1, 10, 2)), 10, 0.3),
    ("combat_e3_potions_too_weak_adjacent", dict(DUNGEON, hp=(96, 200), speed=0, wor=0, stairs=FAR_STAIRS,
                                                 monsters=[mon("Cave orc", 20, 41)]),
     wobble(1, 24, 98, 72, "The Cave orc hits you."), 24, 0.3),
    ("combat_e3_potions_too_weak_shot", dict(DUNGEON, hp=(96, 200), speed=0, wor=1, stairs=FAR_STAIRS,
                                             monsters=[mon("Cave orc", 20, 44)]),
     wobble(1, 20, 98, 72, "The Cave orc fires an arrow."), 20, 0.3),
    ("combat_e3_potions_too_weak_shot_no_recall", dict(DUNGEON, hp=(96, 200), speed=0, wor=0, stairs=FAR_STAIRS,
                                                       monsters=[mon("Cave orc", 20, 44)]),
     wobble(1, 20, 98, 72, "The Cave orc fires an arrow."), 20, 0.3),
]
SCENARIOS += COMBAT_E3



# --- E5 states (the town goals' and the trip plan's ticks split): Shop, HouseBank, TownKit, TripPlan -----------------
class Server:
    """A fake server's answers to the town goals' commands (opt-in: a state's `react=lambda: Server(...)`, called after
    each tick with the commands it sent). Shop: a buy or a sale gets its verdict message and a fresh listing (`relist`:
    with the item sold on it at that price; None: no listing after a sale); `refuse`: names the shop won't take;
    `sold_as`: {pack name: the kind a sale reveals}; `quote`: the gold a quote offers (None: no prompt); `full`: buys get
    "You cannot carry that many items."; `leave_after`: {answer number: the why of a store_leave sent after it}.
    House (its door, step_in, outside, depth): `pile` gold picked up on stepping in; a gold drop's message (`drop_shows`);
    `price` (the door's "This house costs N gold.", or "already owned" with owned=True, or nothing with price=None);
    `buy_ok` (the purchase takes the gold); `door_shut` (the doorway can't be entered); `trap_inside` (once the door is
    closed behind us, the doorway can't be entered from inside); `pickup` (what 'custom ,' picks up). `buy_listing`: a buy brings a fresh listing; `silent`: buys get no answer at all;
    `floor`: {square: item name} picked up on stepping there."""

    def __init__(self, relist=40, refuse=(), sold_as=None, quote=45, full=False, leave_after=None, house=None,
                 pile=0, drop_shows=True, price=None, owned=False, buy_ok=True, door_shut=False, trap_inside=False,
                 pickup=None, sale_price=30, buy_listing=True, silent=False, floor=None):
        self.relist, self.refuse, self.sold_as, self.quote, self.full = relist, refuse, sold_as or {}, quote, full
        self.leave_after, self.answers = dict(leave_after or {}), 0
        self.house, self.pile, self.drop_shows, self.price, self.owned = house, pile, drop_shows, price, owned
        self.buy_ok, self.door_shut, self.trap_inside, self.pickup = buy_ok, door_shut, trap_inside, pickup
        self.sale_price, self.closed_in = sale_price, False
        self.buy_listing, self.silent, self.floor = buy_listing, silent, dict(floor or {})

    @staticmethod
    def msg(c, text):
        c.log({"ev": "message", "text": text})

    @staticmethod
    def reslot(c):
        pk = [i for i in c.items if not i.get("equip")]
        for n, i in enumerate(pk):
            i["item"] = n

    def gold(self, c, d):
        c.ind["gold"] = [c.ind["gold"][0] + d]

    def __call__(self, p, c, t, sent):
        st = STORES.get(c.extra.get(c.pos)) if c.depth == 0 else None
        h = self.house
        for line in sent:
            m = re.match(r"^custom p store item=(\d+) value=(\d+) entry=(\d+)$", line)
            if m and st:
                it, n, cost = st["items"][int(m.group(1))], int(m.group(2)), int(m.group(3))
                if self.silent:
                    continue
                if self.full:
                    self.msg(c, "You cannot carry that many items.")
                elif cost > c.ind["gold"][0]:
                    self.msg(c, "You do not have enough gold for this item.")
                else:
                    self.gold(c, -cost)
                    base = re.sub(r"^(a|an|\d+) ", "", it["name"])
                    tv = 75 if "Potion" in base else 70 if "Scroll" in base else 80
                    c.items.insert(len([i for i in c.items if not i.get("equip")]),
                                   item(0, f"{n} {base}" if n > 1 else f"a {base}", tv, n))
                    self.reslot(c)
                    self.msg(c, f"You bought {it['name']} for {cost} gold.")
                if self.buy_listing:
                    self.answer(c, st, None)
                continue
            m = re.match(r"^custom s store item=(\d+) value=(\d+)$", line)
            if m and st:
                it = next((i for i in c.items if i["item"] == int(m.group(1)) and not i.get("equip")), None)
                if "confirm no" in sent:
                    if self.quote is not None:
                        c.log({"ev": "confirm", "prompt": f"Accept {self.quote} gold? [y/n]"})
                    continue
                if it is None or any(r in it["name"] for r in self.refuse):
                    self.msg(c, "I don't want that!")
                    self.answer(c, st, None)
                    continue
                sold = self.sold_as.get(it["name"], it["name"])
                c.items.remove(it)
                self.reslot(c)
                self.gold(c, self.sale_price)
                self.msg(c, f"You sold {sold} for {self.sale_price} gold.")
                self.answer(c, st, sold)
                continue
            if h and c.depth == h["depth"]:
                door = tuple(h["door"])
                if line.startswith("open ") and self.price is not None:
                    self.msg(c, "This house is already owned." if self.owned else f"This house costs {self.price} gold.")
                elif line.startswith("custom h ") and self.buy_ok:
                    self.gold(c, -self.price)
                elif line.startswith("custom $ value="):
                    amt = int(line.split("=")[1])
                    if self.drop_shows:
                        self.gold(c, -amt)
                        self.pile += amt
                        self.msg(c, f"You drop {amt} gold pieces.")
                elif line.startswith("custom c ") and c.pos == tuple(h["step_in"]):
                    self.closed_in = True
                elif line.startswith("custom d item="):
                    it = next((i for i in c.items if i["item"] == int(line.split("=")[1].split()[0])
                               and not i.get("equip")), None)
                    if it:
                        c.items.remove(it)
                        self.reslot(c)
                        self.msg(c, f"You drop {it['name']}.")
                elif line == "custom ," and self.pickup:
                    c.items.insert(0, item(0, self.pickup, 75))
                    self.reslot(c)
                    self.msg(c, f"You have {self.pickup} (a).")
                    self.pickup = None
        if c.pos in self.floor:                     # (an item lying there: picked up on stepping on it)
            name = self.floor.pop(c.pos)
            c.items.insert(0, item(0, name, 75))
            self.reslot(c)
            self.msg(c, f"You have {name} (a).")
        if h and c.depth == h["depth"]:
            door = tuple(h["door"])
            if c.pos == door and (self.door_shut or (self.trap_inside and self.closed_in)):
                back = tuple(h["outside"]) if self.door_shut else tuple(h["step_in"])
                c.pos = back
                c.log({"ev": "pos", "y": back[0], "x": back[1]})
            if c.pos == tuple(h["step_in"]) and self.pile:
                self.gold(c, self.pile)
                self.msg(c, f"You have found {self.pile} gold pieces worth of gold.")
                self.pile = 0

    def answer(self, c, st, sold):
        self.answers += 1
        if sold is None or self.relist is not None:
            listing = dict(st, items=[dict(i) for i in st["items"]])
            if sold is not None:
                listing["items"].append({"name": sold, "price": self.relist, "number": 1, "slot": len(st["items"]),
                                         "weight": 5})
            c.log(listing)
        if self.answers in self.leave_after:
            c.log({"ev": "store_leave", "why": self.leave_after[self.answers]})


def fn(f):
    return ("fn", f)


def goal(make, **attrs):
    """fn: set the goal make(P) (P: the pilot module) with these attributes."""
    def f(p, c):
        g = make(P)
        for k, v in attrs.items():
            setattr(g, k, v)
        p.set_goal(g)
    return fn(f)


# the wilderness tile north of town with Dive04's house (rundir_template house.json; the fake world's depth -1)
HOUSE = {"door": [60, 129], "step_in": [60, 128], "outside": [60, 130], "box": [59, 124, 61, 129], "depth": -1}
HOUSE_WALLS = {**{(y, x): "#" for y in range(59, 62) for x in range(124, 130)}, (60, 129): "0"}
WILD = dict(depth=-1, pos=(62, 132), stairs={}, extra=HOUSE_WALLS, room=(0, 0, 65, 197))
# a house on the town map (depth 0): walls 40-42 x 60-65, door 41,65
TOWN_HOUSE = {"area": 4, "door": [41, 65], "step_in": [41, 64], "outside": [41, 66], "box": [40, 60, 42, 65], "depth": 0}
TOWN_HOUSE_WALLS = {**{(y, x): "#" for y in range(40, 43) for x in range(60, 66)}, (41, 65): "0"}


def box(y, x):
    """walls on the 8 squares round (y, x)."""
    return {(y + dy, x + dx): "#" for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx}


def house_rec(p, **kw):
    """fn helper: change Dive04's house record (house.json `house`)."""
    p.house_state()["house"].update(kw)


def wild_server(**kw):
    return lambda: Server(house=HOUSE, **kw)


RS = "a Potion of Restore Strength"
STM = "a Wand of Stone to Mud (5 charges)"
HOUSEBANK_E5 = [
    ("town_e5_house_withdraw", dict(WILD, gold=500, react=wild_server(pile=19327)),
     {1: [req("house", "withdraw")]}, 90, 0.3),
    ("town_e5_house_deposit_stash", dict(WILD, gold=5000, react=wild_server(pile=19327),
                                         extra_pack=[(RS, 75, 1), (STM, 65, 1), ("a Potion of Restore Dexterity", 75, 1)]),
     {1: [req("house", "deposit", "200")]}, 110, 0.3),
    ("town_e5_house_withdraw_restore", dict(WILD, gold=500, react=wild_server(pile=19327, pickup=RS)),
     {1: [fn(lambda p, c: p.house_state()["items"].update({"60,125": RS})), req("house", "withdraw")]}, 70, 0.3),
    ("town_e5_house_withdraw_restore_gone", dict(WILD, gold=500, react=wild_server(pile=19327)),
     {1: [fn(lambda p, c: p.house_state()["items"].update({"60,125": RS})), req("house", "withdraw")]}, 70, 0.3),
    ("town_e5_house_buy", dict(WILD, gold=9000, react=wild_server(price=4000)),
     {1: [fn(lambda p, c: p.house_state().update(banked=0)),       # (an earlier house on record, emptied)
          goal(lambda P: P.HouseBank("buy", house=dict(HOUSE, cross={"town": [1, 130], "wild": [64, 130], "depth": -1})),
               role="architect")]}, 110, 0.3),
    ("town_e5_house_buy_owned", dict(WILD, nohouse=True, gold=9000, react=wild_server(price=0, owned=True)),
     {1: [goal(lambda P: P.HouseBank("buy", house=dict(HOUSE)))]}, 20, 0.3),
    ("town_e5_house_buy_no_price", dict(WILD, nohouse=True, gold=9000, react=wild_server()),
     {1: [goal(lambda P: P.HouseBank("buy", house=dict(HOUSE)))]}, 50, 0.3),
    ("town_e5_house_buy_too_dear", dict(WILD, nohouse=True, gold=3000, react=wild_server(price=4000)),
     {1: [goal(lambda P: P.HouseBank("buy", house=dict(HOUSE)))]}, 20, 0.3),
    ("town_e5_house_buy_not_through", dict(WILD, nohouse=True, gold=9000, react=wild_server(price=4000, buy_ok=False)),
     {1: [goal(lambda P: P.HouseBank("buy", house=dict(HOUSE)))]}, 80, 0.3),
    ("town_e5_house_door_shut", dict(WILD, gold=500, react=wild_server(pile=19327, door_shut=True)),
     {1: [req("house", "withdraw")]}, 60, 0.3),
    ("town_e5_house_trapped_inside", dict(WILD, gold=500, react=wild_server(pile=19327, trap_inside=True)),
     {1: [req("house", "withdraw")]}, 90, 0.3),
    ("town_e5_house_drop_unseen", dict(WILD, gold=5000, react=wild_server(pile=19327, drop_shows=False)),
     {1: [req("house", "deposit")]}, 90, 0.3),
    ("town_e5_house_in_town", dict(TOWN, pos=(44, 68), gold=5000, extra={**TOWN["extra"], **TOWN_HOUSE_WALLS},
                                   react=lambda: Server(house=TOWN_HOUSE, pile=0)),
     {1: [fn(lambda p, c: p.house_state().update(house=dict(TOWN_HOUSE), banked=0)), req("house", "deposit")]},
     70, 0.3),
    ("town_e5_house_odd_steps", dict(WILD, gold=500, extra={**HOUSE_WALLS, **box(64, 130), **box(50, 100)}),
     {1: [goal(lambda P: P.HouseBank("withdraw"), step="bogus")],
      3: [goal(lambda P: P.HouseBank("withdraw"), step="back")],
      5: [fn(lambda p, c: house_rec(p, outside=[50, 100])), req("house", "withdraw")]}, 10, 0.3),
    ("town_e5_house_town_edges", dict(TOWN, extra={**TOWN["extra"], **box(30, 100)}),
     {1: [goal(lambda P: P.HouseBank("withdraw"), step="closed")],
      6: [fn(lambda p, c: house_rec(p, cross={"town": [30, 100], "wild": [64, 130], "depth": -1})),
          req("house", "deposit")]}, 12, 0.3),
    ("town_e5_refusals_in_dungeon", dict(DUNGEON),
     {1: [goal(lambda P: P.Shop("5"))], 3: [goal(lambda P: P.HouseBank("deposit"))],
      5: [fn(lambda p, c: p.house_state().pop("house")), goal(lambda P: P.HouseBank("withdraw"))],
      7: [goal(lambda P: P.TownKit())]}, 10, 0.3),
]
SCENARIOS += HOUSEBANK_E5


def revoke_overrides(p, c):
    """fn: the user's file that suspends the Navigator's overrides of the value policy (items.override_allowed)."""
    d = os.path.join(os.path.dirname(os.path.dirname(p.rundir.rstrip("/"))), "private")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, os.path.basename(p.rundir.rstrip("/")) + ".overrides_revoked"), "w").write("test\n")


AT5 = dict(TOWN, pos=(30, 62))          # beside the Alchemist (5)
SELLABLE = [("a Dagger (1d4) (+0,+0)", 23, 1), ("a Light Blue Potion", 75, 1), ("a Cutlass (1d7) {magical}", 23, 1),
            ("a Main Gauche (1d5)", 23, 1)]
SHOP_E5 = [
    ("town_e5_shop_sell_nav", dict(AT5, extra_pack=SELLABLE, react=lambda: Server()),
     {1: [req("goal", "shop", "5", "sell", "Nothing_like_it:1", "sell", "Light_Blue:1", "sell", "Cutlass:1",
              "sell", "!Dagger:1", "quote", "Main_Gauche:1")]}, 50, 0.3),
    ("town_e5_shop_sell_arch", dict(AT5, extra_pack=[("2 Gloopy Black Potions", 75, 2),
                                                     ("a Long Sword (2d5) {excellent}", 23, 1),
                                                     ("a Main Gauche (1d5)", 23, 1), ("a Dagger (1d4) (+0,+0)", 23, 1)],
                                    react=lambda: Server(sold_as={"2 Gloopy Black Potions": "a Potion of Sleep"},
                                                         quote=None)),
     {1: [req("goal", "shop", "5", "sell", "Gloopy:1", "sell", "Long_Sword:1", "quote", "Main_Gauche:1",
              "sell", "!Dagger:1", arch=True)]}, 60, 0.3),
    ("town_e5_shop_override_revoked", dict(AT5, extra_pack=SELLABLE, react=lambda: Server()),
     {1: [fn(revoke_overrides), req("goal", "shop", "5", "sell", "!Dagger:1")]}, 20, 0.3),
    ("town_e5_shop_sale_unlisted", dict(AT5, extra_pack=SELLABLE, react=lambda: Server(relist=None)),
     {1: [req("goal", "shop", "5", "sell", "!Dagger:1")]}, 40, 0.3),
    ("town_e5_shop_buys_rich", dict(AT5, gold=2000, react=lambda: Server()),
     {1: [req("goal", "shop", "5", "buy", "Speed:1", "buy", "Word_of_Recall:4@100", "buy", "Phase_Door:+30",
              "buy", "Potions_of_Cure_Light_Wounds:+1")]}, 50, 0.3),
    ("town_e5_shop_buys_poor", dict(AT5, gold=300, react=lambda: Server()),
     {1: [req("goal", "shop", "5", "buy", "Restore_Strength:1", "buy", "Phase_Door:+30")]}, 30, 0.3),
    ("town_e5_shop_cannot_carry", dict(AT5, gold=2000, react=lambda: Server(full=True)),
     {1: [req("goal", "shop", "5", "buy", "Phase_Door:+2")]}, 30, 0.3),
    ("town_e5_shop_no_listing", dict(TOWN, pos=(40, 32), extra={**TOWN["extra"], (40, 30): "2"}),
     {1: [req("goal", "shop", "2")]}, 40, 0.3),
    ("town_e5_shop_walled_in", dict(TOWN, extra={**TOWN["extra"], (45, 100): "7", **box(45, 100)}),
     {1: [req("goal", "shop", "7")]}, 6, 0.3),
    ("town_e5_shop_stuck", dict(TOWN, extra={**TOWN["extra"], **box(50, 150)}),
     {1: [req("goal", "shop", "1")], 4: [("step", (50, 150))]}, 30, 0.3),
    ("town_e5_shop_thrown_out", dict(AT5, gold=2000, react=lambda: Server(leave_after={1: "walk", 2: None})),
     {1: [req("goal", "shop", "5", "buy", "Phase_Door:+1", "buy", "Cure_Light:+1", "buy", "Phase_Door:+1")]},
     60, 0.3),
    ("town_e5_shop_no_relisting", dict(AT5, gold=2000, react=lambda: Server(buy_listing=False)),
     {1: [req("goal", "shop", "5", "buy", "Phase_Door:+30", "buy", "Speed:+1")]}, 40, 0.3),
    ("town_e5_shop_silent", dict(AT5, gold=2000, react=lambda: Server(silent=True)),
     {1: [req("goal", "shop", "5", "buy", "Phase_Door:+1")]}, 30, 0.3),
]
SCENARIOS += SHOP_E5


def give(name, tval, n=1):
    """fn: put an item into the pack (the fake client's), and have the Pilot re-read it."""
    def f(p, c):
        c.items.insert(len([i for i in c.items if not i.get("equip")]), item(0, name, tval, n))
        Server.reslot(c)
        p.w.inven_dirty = True
    return fn(f)


def kit(**attrs):
    """fn: a fresh TownKit (plan town) at a later stage: attrs set on it."""
    return goal(lambda P: P.TownKit(), **attrs)


BUYING = dict(stage="buying", queue=[], plan={})
BOOTS = [("a Pair of Leather Boots [2,+10]", 30, 1)]
UNKNOWN_RING = [("a Moonstone Ring", 45, 1)]
TOWNKIT_E5 = [
    ("town_e5_kit_fetch_tavern", dict(TOWN, pos=(25, 89), react=lambda: Server(floor={(28, 90): RS})),
     {1: [fn(lambda p, c: p.house_state()["tavern"].update(items={"28,90": RS})), kit(withdrawn=True)]}, 50, 0.3),
    ("town_e5_kit_upgrades", dict(TOWN, extra_pack=BOOTS),
     {1: [kit(withdrawn=True, fetched=True)], 5: [kit(stage="upgrade again")], 9: [kit(**BUYING)]}, 13, 0.3),
    ("town_e5_kit_upgrade_again_none", dict(TOWN),
     {1: [kit(stage="upgrade again", queue=[])]}, 8, 0.3),
    ("town_e5_kit_identify", dict(AT5, gold=2000, extra_pack=UNKNOWN_RING + [("3 Scrolls of Identify", 70, 3)]),
     {1: [kit(stage="identify")]}, 30, 0.3),
    ("town_e5_kit_identify_buy", dict(AT5, gold=2000, extra_pack=UNKNOWN_RING, react=lambda: Server()),
     {1: [kit(stage="identify")]}, 30, 0.3),
    ("town_e5_kit_broke_day", dict(TOWN, wor=1, gold=100), {1: [kit(stage="buy")]}, 10, 0.3),
    ("town_e5_kit_broke_night", dict(TOWN, wor=1, gold=100),
     {0: [("msg", "The sun has fallen.")], 1: [kit(stage="buy")]}, 10, 0.3),
    ("town_e5_kit_make_room", dict(AT5, gold=3000, ccw=0, extra_pack=[(f"a Potion of Junk{i}", 75, 1) for i in range(13)],
                                   react=lambda: Server()),
     {1: [kit(stage="buy")]}, 40, 0.3),
    ("town_e5_kit_quaff_provision", dict(AT5, gold=300, hunger=2, light=lantern(1000), extra_pack=[(RS, 75, 1)],
                                         react=lambda: Server()),
     {1: [kit(**BUYING)]}, 60, 0.3),
    ("town_e5_kit_restock_wait", dict(TOWN, gold=300), {1: [kit(**BUYING, done_log=["5: no Restore Strength in stock"])]},
     60, 1.0),
    ("town_e5_kit_recharge_enchant", dict(AT5, gold=300, staff=0,
                                          extra_pack=[("a Staff of Teleportation (0 charges)", 55, 1)],
                                          react=lambda: Server()),
     {1: [kit(**BUYING)], 4: [give("a Scroll of Recharging", 70)], 6: [kit(**BUYING)],
      9: [give("2 Scrolls of Enchant Armor", 70, 2)],
      10: [kit(**BUYING, recharged={"a Staff of Teleportation (0 charges)"})]}, 16, 0.3),
    ("town_e5_kit_stash_tavern", dict(TOWN, nohouse=True, extra_pack=[(RS, 75, 1)]),
     {1: [kit(**BUYING, enchant_bought=True, quaffed={RS})]}, 10, 0.3),
    ("town_e5_kit_deposit", dict(TOWN, gold=5000), {1: [kit(**BUYING, enchant_bought=True)]}, 10, 0.3),
    ("town_e5_kit_finish", dict(TOWN, gold=150), {1: [kit(**BUYING)]}, 10, 0.3),
    ("town_e5_kit_sell_again_done", dict(TOWN), {1: [kit(stage="sell again", queue=[])]}, 8, 0.3),
]
SCENARIOS += TOWNKIT_E5


def trip(lo, hi, until="cures<3 or phase<3 or minutes>45", then="recall", level_min=10, via=None, here=False,
         goal_=None, **attrs):
    """fn: a trip plan (TripPlan) installed as `plan trip` would, at a later phase: attrs set on it (a callable value
    is called with (p, now): times relative to the game clock); here: the level being worked is this one; goal_: a
    goal (make(P)) the plan set, else none (the goal running is dropped)."""
    def f(p, c):
        pl = P.TripPlan(lo, hi, P.TripPlan.parse_until(until), then, level_min, via)
        now = W.gnow()
        if here:
            pl.level = p.w.level_t
        for k, v in attrs.items():
            setattr(pl, k, v(p, now) if callable(v) else v)
        p.plan = pl
        p.set_goal(pl.mark(goal_(P)) if goal_ else None)        # (as request_trip: the goal running is dropped)
    return fn(f)


def ago(s):
    return lambda p, now: now - s


def escaped(p, c):
    """fn: the Pilot's last escape a moment ago (combat.log_escape's record)."""
    p.last_escape = (W.gnow(), "recall", "HP 90/358 beside a Black orc", [90, 358])


LEVEL = dict(phase="level", went_down=True)
YANKED = "You feel yourself yanked downwards!"
CHARGED = "The air about you becomes charged..."
SPECIAL = "You feel there is something special about this level."
TRIPPLAN_E5 = [
    ("plan_e5_down_stairs", dict(TOWN), {1: [trip(50, 150)]}, 6, 0.3),
    ("plan_e5_down_recall", dict(TOWN), {1: [trip(500, 700)]}, 6, 0.3),
    ("plan_e5_down_back_in_town", dict(TOWN), {1: [trip(250, 500, went_down=True)]}, 4, 0.3),
    ("plan_e5_down_wilderness", dict(WILD), {1: [trip(250, 500)]}, 6, 0.3),
    ("plan_e5_level_back_in_town", dict(TOWN), {1: [fn(escaped), trip(250, 500, **LEVEL)]}, 4, 0.3),
    ("plan_e5_level_out_of_range", dict(DUNGEON), {1: [trip(500, 700, **LEVEL)]}, 6, 0.3),
    ("plan_e5_level_recall_arrival", dict(DUNGEON, stairs={}, extra_pack=[("a Staff of Door/Stair Location (5 charges)",
                                                                            55, 1)]),
     {0: [ev({"ev": "level", "depth": 6}), ("msg", YANKED)], 1: [trip(250, 500, **LEVEL)]}, 8, 0.3),
    ("plan_e5_level_special", dict(DUNGEON, stairs={}),
     {0: [ev({"ev": "level", "depth": 6}), ("msg", SPECIAL)], 1: [trip(250, 500, **LEVEL)]}, 8, 0.3),
    ("plan_e5_level_resumed", dict(DUNGEON),
     {1: [trip(250, 500, **LEVEL, resume_lvl={"depth": 6, "age": 30.0, "done": None, "arrival": "stairs",
                                              "located": True, "special": False, "stairs_first": False, "fails": 0})]},
     6, 0.3),
    ("plan_e5_level_time_up", dict(DUNGEON),
     {1: [trip(250, 500, **LEVEL, here=True, level_t0=ago(700))],
      5: [trip(250, 500, **LEVEL, here=True, level_t0=ago(30), level_done="left: a band", fails=6)]}, 10, 0.3),
    ("plan_e5_explore_time_up", dict(DUNGEON),
     {1: [trip(250, 500, **LEVEL, here=True, level_t0=ago(700), goal_=lambda P: P.Explore())]}, 6, 0.3),
    ("plan_e5_leave_max", dict(DUNGEON),
     {1: [trip(250, 500, **LEVEL, here=True, level_t0=ago(400), level_done="left: a band",
               leave_since=lambda p, now: (p.w.level_t, now - 400), goal_=lambda P: P.Dive(350))]}, 6, 0.3),
    ("plan_e5_quiet_level", dict(DUNGEON),
     {1: [trip(250, 500, **LEVEL, here=True, level_t0=ago(240),
               xp_hist=lambda p, now: [(now - 200, 200000, p.w.level_t)], goal_=lambda P: P.Explore())]}, 6, 0.3),
    ("plan_e5_until_holds", dict(DUNGEON),
     {1: [trip(250, 500, until="cures<50", **LEVEL, here=True, level_t0=ago(30), goal_=lambda P: P.Explore())]},
     6, 0.3),
    ("plan_e5_escape_recall", dict(DUNGEON),
     {0: [("msg", CHARGED)], 1: [fn(escaped), trip(250, 500, **LEVEL, here=True, level_t0=ago(30),
                                                    goal_=lambda P: P.Explore())]}, 6, 0.3),
    ("plan_e5_home_climb_slow", dict(DUNGEON),
     {1: [trip(250, 500, phase="home", went_down=True, climb_t0=ago(200), goal_=lambda P: P.Dive(0))]}, 6, 0.3),
    ("plan_e5_home_failing", dict(DUNGEON), {1: [trip(250, 500, phase="home", went_down=True, fails=11)]}, 4, 0.3),
    ("plan_e5_home_then_town", dict(TOWN), {1: [trip(250, 500, then="town", phase="home", home_why="cures<3")]},
     6, 0.3),
    ("plan_e5_home_done", dict(TOWN), {1: [trip(250, 500, phase="home", home_why="cures<3")]}, 4, 0.3),
    ("plan_e5_home_wilderness", dict(WILD), {1: [trip(250, 500, phase="home")]}, 6, 0.3),
    ("plan_e5_home_near_town", dict(DUNGEON, depth=2), {1: [trip(250, 500, phase="home", went_down=True)]}, 6, 0.3),
    ("plan_e5_home_recall_pending", dict(DUNGEON),
     {0: [("msg", CHARGED)], 1: [trip(250, 500, phase="home")]}, 6, 0.3),
    ("plan_e5_home_no_recall", dict(DUNGEON, wor=0), {1: [trip(250, 500, phase="home", went_down=True)]}, 6, 0.3),
    ("plan_e5_town_phase_done", dict(TOWN), {1: [trip(250, 500, phase="town", home_why="cures<3")]}, 4, 0.3),
    ("plan_e5_paused", dict(DUNGEON), {1: [trip(250, 500, **LEVEL, paused=True)]}, 6, 0.3),
]
SCENARIOS += TRIPPLAN_E5


# --- 2.45.0 states: the behaviour fixes the E3/E5 splits found (each differs from 2.44.x on purpose) ----------------
def drink(kind):
    """fn: the pack's `kind` gone (drunk)."""
    return fn(lambda p, c: c.items.__setitem__(slice(None), [i for i in c.items if kind not in i["name"]]))


FIX_245 = [
    # the hunger step with no light to read Satisfy Hunger by: rest (hurt, alone) and pickup now run (they didn't)
    ("combat_fix_hunger_dark_rest", dict(DUNGEON, rations=0, hunger=1, light=None, hp=(200, 358), extra_pack=SATISFY),
     {}, 12, 0.4),
    ("combat_fix_hunger_dark_pickup", dict(DUNGEON, rations=0, hunger=1, light=None, extra_pack=SATISFY,
                                           floor="a Potion of Cure Light Wounds", extra_map={(20, 40): "!"}),
     {1: [("msg", LOOK)]}, 10, 0.4),
    # the escape walk reaches its stairs with the orc out of view and the last hit 2-5 s ago: it takes them now
    ("combat_fix_escape_walk_arrives_unseen", dict(DUNGEON, hp=(150, 358), speed=0,
                                                   stairs={(20, 47): ">", (35, 10): "<"},
                                                   monsters=[mon("Cave orc", 20, 37)]),
     sched(hits("The Cave orc hits you.", (0,)), {3: [("mons", [])]}), 20, 0.3),
    # the same walk outliving its emergency (no hit for 5 s, nothing in view: escape() isn't called): it walks on and
    # takes the stairs (it stood still with the mover active, not resting)
    ("combat_fix_escape_walk_outlives_emergency", dict(DUNGEON, hp=(150, 358), speed=0,
                                                       stairs={(20, 50): ">", (35, 10): "<"},
                                                       monsters=[mon("Cave orc", 20, 37)]),
     sched(hits("The Cave orc hits you.", (0,)), {3: [("mons", [])]}), 45, 0.3),
    # a withdraw that fetches the Restore: off the record at once (`house` shows no stash; the next withdraw, the
    # potion drunk, makes no pick-ups on the empty square)
    ("town_fix_house_withdraw_restore_struck", dict(WILD, gold=500, react=wild_server(pile=19327, pickup=RS)),
     {1: [fn(lambda p, c: p.house_state()["items"].update({"60,125": RS})), req("house", "withdraw")],
      90: [req("house")], 91: [drink("Restore Strength")], 92: [req("house", "withdraw")]}, 200, 0.3),
]
SCENARIOS += FIX_245
COVER_FUNCS = set(os.environ.get("EQUIV_COVER_FUNCS", "reflexes escape").split())
COVER_PATTERNS = [f for f in COVER_FUNCS if "*" in f]
COVER_FILES = ("pilot.py", "combat.py", "town_goals.py", "plan.py")


def norm(v):
    s = json.dumps(v, sort_keys=True, default=repr) if not isinstance(v, str) else v
    s = re.sub(r" at 0x[0-9a-f]+", " at 0x?", s)
    return s.replace(TREE, "<TREE>")


def reset_world_clock():
    t = Clock.t
    W._CLOCK.update(wall=t, game=t, factor=1.0, model=1.0, measured=0.0, fast_ok=False, rate=None)
    W._HIST.clear()
    W._HIST.append((t, t, 1.0))
    W._FUEL.clear()
    W._FROZEN.update(t=0.0, on=False)


COVER = {} if os.environ.get("EQUIV_COVER") else None    # {scenario: {func: set(lines from the def)}}
_cov = None


def cover_key(co):
    """The name a code object's lines are recorded under: its qualname (TownKit.tick) when EQUIV_COVER_FUNCS names it
    or a pattern matches it (TownKit.*), else its bare name (reflexes) when that is named; None: not recorded."""
    if co.co_qualname in COVER_FUNCS or any(fnmatch.fnmatchcase(co.co_qualname, f) for f in COVER_PATTERNS):
        return co.co_qualname
    return co.co_name if co.co_name in COVER_FUNCS else None


def tracer(frame, event, arg):
    co = frame.f_code
    key = cover_key(co) if os.path.basename(co.co_filename) in COVER_FILES else None
    if key:
        lines = _cov.setdefault(key, set())

        def local(f, ev, a):
            if ev == "line":
                lines.add(f.f_lineno - co.co_firstlineno)
            return local
        return local
    return None


def run(name, kw, schedule, ticks, dt):
    kw = dict(kw)
    template = kw.pop("template", True)
    nohouse = kw.pop("nohouse", False)
    light = kw.pop("light", lantern(9000))
    pk = {k: kw.pop(k) for k in ("rations", "flasks", "ccw", "csw", "clw", "phase", "wor", "heroism", "speed", "staff")
          if k in kw}
    extra_pack = kw.pop("extra_pack", [])
    extra_map = kw.pop("extra_map", {})
    react = kw.pop("react", None)
    if react is not None:
        react = react()                 # (a fresh fake server per run)
    Clock.t = T0
    random.seed(12345)
    reset_world_clock()
    rundir = fake.fresh_rundir(os.path.join(fake.S, "eqrun", "runs", "pilot", "dive04"), template)
    if nohouse:
        hj = json.load(open(os.path.join(rundir, "house.json")))
        hj.pop("house"), hj.pop("banked")
        json.dump(hj, open(os.path.join(rundir, "house.json"), "w"), indent=1)
    kw.setdefault("extra", {})
    kw["extra"] = {**kw["extra"], **extra_map}
    c = fake.FakeClient(inven=pack(extra=extra_pack, **pk) + worn(light), **kw)
    p = P.Pilot(c, rundir)
    town_extra = dict(c.extra)
    p.arch_token = TOKEN
    fake.no_shadow(p)
    global _cov
    _cov = COVER.setdefault(name, {}) if COVER is not None else None
    rec = {"ticks": [], "replies": []}
    na = nn = 0
    replies = []
    for t in range(ticks):
        for kind, a in schedule.get(t, ()):
            if kind == "req":
                q = queue.Queue()
                p.requests.put((dict(a), q))
                replies.append((t, a, q))
            elif kind == "ev":
                c.log(dict(a))
            elif kind == "pos":
                c.pos = a
            elif kind == "depth":
                c.depth = a
                c.ind["depth"] = [a]
            elif kind == "step":                # (moved by the game: the pos event too, so World sees what's underfoot)
                c.pos = a
                c.log({"ev": "pos", "y": a[0], "x": a[1]})
            elif kind == "hp":
                c.ind["hp"] = [a, c.ind["hp"][1]]
            elif kind == "mons":
                c.monsters = list(a)
            elif kind == "ind":
                c.ind[a[0]] = list(a[1])
            elif kind == "ghost":
                c.ghost = a
            elif kind == "msg":
                c.log({"ev": "message", "text": a})
            elif kind == "fn":                  # (E5: set up a goal, a plan or the Pilot's state directly)
                a(p, c)
        c.sent = []
        err = None
        if COVER is not None:
            sys.settrace(tracer)
        try:
            p.tick()
        except Exception as e:                 # (recorded: both trees must fail alike)
            err = repr(e)
        finally:
            if COVER is not None:
                sys.settrace(None)
        att = p.attention[na:]
        news = p.news[nn:]
        na, nn = len(p.attention), len(p.news)
        rec["ticks"].append({"t": t, "sent": list(c.sent), "attention": norm(att), "news": norm(news), "error": err,
                             "goal": p.goal.describe() if p.goal else None,
                             "plan": getattr(p.plan, "text", None), "pos": list(c.pos)})
        # (moves: the fake world follows the Mover's walk commands one square, so goals make progress)
        y0, x0, y1, x1 = c.room
        for line in c.sent:
            if line == "leave" and c.log:
                c.log({"ev": "store_leave", "why": "leave"})
            m = re.match(r"^walk (\d)$|^custom [.] dir=(\d)$", line)
            mp = re.match(r"^pathfind (\d+) (\d+)$", line)
            if m:
                d = int(m.group(1) or m.group(2))
                dy, dx = {1: (1, -1), 2: (1, 0), 3: (1, 1), 4: (0, -1), 6: (0, 1), 7: (-1, -1), 8: (-1, 0),
                          9: (-1, 1)}.get(d, (0, 0))
                new = (c.pos[0] + dy, c.pos[1] + dx)
            elif mp:
                new = (int(mp.group(1)), int(mp.group(2)))
            else:
                continue
            if c.depth == -1 and new[0] >= 65 and line.startswith("walk"):
                c.depth, c.ind["depth"] = 0, [0]
                c.extra = dict(town_extra)
                c.pos = (1, new[1])
                c.log({"ev": "level", "depth": 0})
                c.log({"ev": "pos", "y": 1, "x": new[1]})
                break
            if c.depth == 0 and new[0] <= 0 and line.startswith("walk"):
                # (off the town's north edge: the wilderness tile with the house, its door '0' at 60,129)
                c.depth, c.ind["depth"] = -1, [-1]
                c.extra = {(y, x): "#" for y in range(59, 62) for x in range(124, 130)}
                c.extra[(60, 129)] = "0"
                c.pos = (64, new[1])
                c.log({"ev": "level", "depth": -1})
                c.log({"ev": "pos", "y": 64, "x": new[1]})
                break
            if y0 < new[0] < y1 and x0 < new[1] < x1:
                c.pos = new
                c.log({"ev": "pos", "y": new[0], "x": new[1]})
                st = STORES.get(c.extra.get(new))
                if st and c.depth == 0:
                    c.log(dict(st))
        if react is not None:
            react(p, c, t, rec["ticks"][-1]["sent"])
        fake.advance(dt)
    for t, a, q in replies:
        try:
            rec["replies"].append([t, a["cmd"], a["args"], norm(q.get_nowait())])
        except queue.Empty:
            rec["replies"].append([t, a["cmd"], a["args"], "(no reply)"])
    p.dlog.close()
    rec["decisions"] = [norm(l.rstrip("\n")) for l in open(os.path.join(rundir, "decisions.jsonl"))]
    files = {}
    for root, _, fs in os.walk(os.path.dirname(os.path.dirname(rundir))):
        for f in sorted(fs):
            path = os.path.join(root, f)
            rel = os.path.relpath(path, os.path.dirname(os.path.dirname(rundir)))
            if f.endswith(".json"):
                files[rel] = norm(open(path).read())
            else:
                files[rel] = os.path.getsize(path)
    rec["files"] = files
    rec["sent_total"] = sum(len(x["sent"]) for x in rec["ticks"])
    return rec


res = {}
for name, kw, schedule, ticks, dt in SCENARIOS:
    if only and name not in only:
        continue
    res[name] = run(name, kw, schedule, ticks, dt)
    r = res[name]
    errs = sum(1 for x in r["ticks"] if x["error"])
    print(f"{name:32s} sent {r['sent_total']:4d}  decisions {len(r['decisions']):4d}  "
          f"notices {sum(x['attention'] != '[]' for x in r['ticks']):3d}  errors {errs}  "
          f"goal {r['ticks'][-1]['goal']}")
json.dump(res, open(out, "w"), indent=1, sort_keys=True)
if COVER is not None:
    json.dump({n: {f: sorted(ls) for f, ls in c.items()} for n, c in COVER.items()},
              open(os.environ["EQUIV_COVER"], "w"), indent=0, sort_keys=True)
