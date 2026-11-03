"""tick() equivalence: the real Pilot (its __init__, World and Mover) on a fake client through scripted game states,
recording every command sent, every notice and every log record. python3 equiv.py PILOT_DIR OUT.json [NAME...]
(run with PYTHONHASHSEED=0; compare the OUT files of the old and new trees).

64 states: the 33 of E1 step 4 (town, supplies, queries, plans) and 31 combat_* states of step 5 (groups, uniques,
unseen attackers, low HP with and without Phase/Teleport/Speed, fear with and without a cure, Speed/Berserk, thieves,
breeders, a drainer and a drain, traps, a corridor choke, hound packs, a walk to the stairs under attack, stairs
underfoot, molds, a summoner, a confusion lock, blind with two adjacent, slowed, engage, the emergency loop, no stairs).
Schedule actions: req, ev, pos, depth, step (move with a pos event), hp, mons, ind, msg.
Coverage: EQUIV_COVER=COV.json [EQUIV_COVER_FUNCS="reflexes escape"] records the lines (from each def) run per state
in the named functions; covreport.py COV.json prints it per state. Run from a copy next to a rundir_template/ (see
fake.py)."""
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
COVER_FUNCS = set(os.environ.get("EQUIV_COVER_FUNCS", "reflexes escape").split())


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


def tracer(frame, event, arg):
    co = frame.f_code
    if co.co_name in COVER_FUNCS and os.path.basename(co.co_filename) in ("pilot.py", "combat.py"):
        lines = _cov.setdefault(co.co_name, set())

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
            elif kind == "msg":
                c.log({"ev": "message", "text": a})
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
