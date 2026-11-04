"""unit_house -- unit cases: House bank and stash.

Run by unit.py (python3 unit.py [NAME]); W, pilot() and the other shared fixtures are in fixtures.py.
"""
import json
import os
import re

from fixtures import P, case, pilot
import town_goals as TG  # noqa: E402
from common import rec_name  # noqa: E402


@case
def tavern_stash_and_one_lantern():
    """The user (10-26): Restore potions and Wands of Stone to Mud (never aimed) stay in the tavern (8) during a
    mission -- deposited at the end of plan town, the matching Restore fetched for a drained stat instead of bought,
    stash kinds not picked up in town otherwise; and one lantern: a spare (not the fullest) is sold."""
    import tempfile
    p = pilot(pack=[("a Potion of Restore Dexterity", 75), ("2 Wands of Stone to Mud (21 charges)", 65),
                    ("a Brass Lantern (with 1977 turns of light)", 39), ("a Brass Lantern (with 14943 turns of light)", 39),
                    ("9 Potions of Cure Critical Wounds", 75)])
    p.rundir = tempfile.mkdtemp()
    p.w.depth, p.w.in_dungeon = 0, False
    p.w.memory = {(27, 89): "8", (27, 90): ".", (28, 90): "!"}
    p.flavour_of = lambda it: None
    stash = [i["name"] for i in p.w.items() if p.is_stash_item(i["name"])]
    ent = p.tavern_entrance()
    p.tavern_state().setdefault("items", {})["27,90"] = "a Potion of Restore Dexterity"     # (D10: house.json)
    p.seen_drained = {"DEX": (18, 38)}
    want_with = p.stash_wanted()
    p.w.inven = [i for i in p.w.inven if "Restore" not in i["name"]]
    want = p.stash_wanted()
    needs = [r[1] for r in p.town_needs(None, ())]
    lamps = {("1977" if "1977" in i["name"] else "14943"): p.town_sell_count(i) for i in p.w.items()
             if "Lantern" in i["name"]}
    ok = (stash == ["a Potion of Restore Dexterity", "2 Wands of Stone to Mud (21 charges)"] and ent == (27, 89)
          and want_with is None and want == "Restore Dexterity" and "Restore Dexterity" not in needs
          and lamps == {"1977": 1, "14943": 0})
    return ok, f"stash kinds {stash}; tavern {ent}; fetch {want!r}; buy list {needs}; lanterns sold {lamps}"


def _floor_sync(w, floor):
    """The client's floor reading for the square we stand on (2.50.0: the stash reads it): the item there, not gold."""
    n = floor.get(w.pos)
    w.floor = None if not n or n.startswith("$") else n
    w.floor_pos, w.floor_t = w.pos, P.gnow() + 10


# a piece of Dive04's town (10-27): the 1-square house at 37-39,155-157 (door 38,155) and a 4-square one
_TOWN = {37: "....###....#....#", 38: "....0.#....#..0.", 39: "....###....####.."}


def _town_memory():
    mem = {}
    for y, row in _TOWN.items():
        for i, ch in enumerate(row):
            mem[(y, 151 + i)] = ch
    for y in (36, 40):
        for x in range(151, 168):
            mem[(y, x)] = "."
    return mem


@case
def house_bank_round_trip():
    """The gold bank (the user, 10-27): the smallest house on the map is found (door 38,155, step in at 38,156, stand
    at 38,154); a deposit walks in, closes the door, drops all but the float, walks out and closes it; a withdraw picks
    the pile up by stepping in. Simulated server: walks move, the drop takes the gold and leaves a pile."""
    houses = P.town_houses(_town_memory())
    h = houses[0] if houses else {}
    import tempfile
    p = pilot(gold=20300)
    w = p.w
    w.depth, w.in_dungeon, w.memory, w.pos = 0, False, _town_memory(), (38, 154)
    p.rundir, p.busy_until = tempfile.mkdtemp(), 0
    p._house = {"house": {k: (list(v) if isinstance(v, tuple) else v) for k, v in h.items() if k != "inside"},
                "banked": 0}
    pile, sent = [0], []
    dirs = {1: (1, -1), 2: (1, 0), 3: (1, 1), 4: (0, -1), 6: (0, 1), 7: (-1, -1), 8: (-1, 0), 9: (-1, 1)}

    def cmd(line, why, hold=0.4):
        sent.append(line)
        m = re.match(r"walk (\d)", line)
        if m:
            dy, dx = dirs[int(m.group(1))]
            w.pos = (w.pos[0] + dy, w.pos[1] + dx)
            if w.pos == tuple(h["step_in"]) and pile[0]:
                w.ind["gold"][0] += pile[0]
                pile[0] = 0
        m = re.match(r"custom \$ value=(\d+)", line)
        if m:
            w.ind["gold"][0] -= int(m.group(1))
            pile[0] += int(m.group(1))
            w.messages.append((P.gnow(), f"You drop {m.group(1)} pieces of gold."))
    p.cmd = cmd
    p.mover = type("M", (), {"active": False, "go": lambda self, t: True, "tick": lambda self: "arrived",
                             "stop": lambda self: None})()
    p.town_reserve = lambda: 1000

    def run(g):
        for _ in range(60):
            g.t = -99.0
            r = g.tick(p)
            if r:
                return r
    a = run(P.HouseBank("deposit"))
    after_dep = (w.ind["gold"][0], pile[0], p.banked(), w.pos)
    b = run(P.HouseBank("withdraw"))
    after_wd = (w.ind["gold"][0], pile[0], p.banked(), w.pos)
    ok = h.get("door") == (38, 155) and h.get("outside") == (38, 154) and h.get("step_in") == (38, 156) and \
        a and a[0] == "done" and after_dep == (300, 20000, 20000, (38, 154)) and \
        b and b[0] == "done" and after_wd == (20300, 0, 0, (38, 154)) and "custom c dir=4" in sent and \
        "custom c dir=6" in sent
    return ok, f"house {h.get('door')}/{h.get('step_in')}/{h.get('outside')}; deposit {a} -> {after_dep}; " \
               f"withdraw {b} -> {after_wd}; sent {sent[:8]}"


@case
def house_bank_in_the_wilderness():
    """The user (10-27): a small house just outside town (practice for the live server, where town houses cost 5x).
    A deposit from town walks to the edge square it was reached by, off the edge into the house's tile, banks, and
    walks back into town by the same edge."""
    import tempfile
    houses = P.town_houses(_town_memory())
    h = dict({k: (list(v) if isinstance(v, tuple) else v) for k, v in houses[0].items() if k != "inside"},
             depth=-1, cross={"town": [1, 130], "wild": [64, 130], "depth": -1})
    p = pilot(gold=10300)
    w = p.w
    w.depth, w.in_dungeon, w.memory, w.pos = 0, False, _town_memory(), (1, 130)
    p.rundir, p.busy_until = tempfile.mkdtemp(), 0
    p._house = {"house": h, "banked": 0}
    dirs = {2: (1, 0), 4: (0, -1), 6: (0, 1), 8: (-1, 0)}
    sent = []

    def cmd(line, why, hold=0.4):
        sent.append(line)
        m = re.match(r"walk (\d)", line)
        if m:
            if w.depth == 0 and w.pos == (1, 130) and m.group(1) == "8":
                w.depth, w.pos = -1, (38, 154)          # (the scripted tile: the house's outside square)
                return
            if w.depth == -1 and w.pos == (64, 130) and m.group(1) == "2":
                w.depth, w.pos = 0, (1, 130)
                return
            dy, dx = dirs.get(int(m.group(1)), (0, 0))
            w.pos = (w.pos[0] + dy, w.pos[1] + dx)
        m = re.match(r"custom \$ value=(\d+)", line)
        if m:
            w.ind["gold"][0] -= int(m.group(1))
            w.messages.append((P.gnow(), f"You drop {m.group(1)} pieces of gold."))
    p.cmd = cmd

    class M:
        active = False
        def go(self, t):
            w.pos = tuple(t[0])          # (the scripted walk arrives at once)
            return True
        def tick(self):
            return "arrived"
        def stop(self):
            pass
    p.mover = M()
    g = P.HouseBank("deposit")
    r = None
    for _ in range(80):
        g.t = -99.0
        r = g.tick(p)
        if r:
            break
    ok = r and r[0] == "done" and w.depth == 0 and w.pos == (1, 130) and p.banked() == 10000 and \
        sent.count("walk 8") == 1 and sent.count("walk 2") == 1
    return ok, f"{r}; depth {w.depth} at {w.pos}; banked {p.banked()}; sent {sent}"


@case
def house_keeps_the_stash():
    """The user (10-27): the stash moves into the house (a town monster took a wand off the tavern floor). In the
    4-square house (door 60,129) a deposit drops each stash stack on its own square away from the gold's (60,128),
    the gold on 60,128; a withdraw with STR drained fetches the Restore Strength from its square, gold too."""
    import tempfile
    mem = {}
    for x in range(124, 130):
        mem[(59, x)] = mem[(61, x)] = "#"
    mem[(60, 124)], mem[(60, 129)] = "#", "0"
    for x in range(125, 129):
        mem[(60, x)] = "."
    for y in range(57, 64):
        for x in range(130, 134):
            mem[(y, x)] = "."
    hs = P.town_houses(mem)
    h = {k: (list(v) if isinstance(v, tuple) else v) for k, v in hs[0].items() if k != "inside"}
    p = pilot(gold=5300, pack=[("2 Wands of Stone to Mud (21 charges)", 65), ("a Potion of Restore Strength", 75)])
    w = p.w
    w.depth, w.in_dungeon, w.memory, w.pos = 0, False, mem, (60, 130)
    p.rundir, p.busy_until = tempfile.mkdtemp(), 0
    p._house = {"house": h, "banked": 0}
    floor = {}
    dirs = {4: (0, -1), 6: (0, 1)}

    def cmd(line, why, hold=0.4):
        m = re.match(r"walk (\d)", line)
        if m:
            dy, dx = dirs[int(m.group(1))]
            w.pos = (w.pos[0] + dy, w.pos[1] + dx)
            if "$" in floor.get(w.pos, ""):
                w.ind["gold"][0] += int(floor.pop(w.pos)[1:])
        m = re.match(r"custom d item=(\d+)", line)
        if m:
            it = next(i for i in w.inven if i["item"] == int(m.group(1)))
            w.inven.remove(it)
            floor[w.pos] = it["name"]
        m = re.match(r"custom \$ value=(\d+)", line)
        if m:
            w.ind["gold"][0] -= int(m.group(1))
            floor[w.pos] = "$" + m.group(1)
            w.messages.append((P.gnow(), f"You drop {m.group(1)} pieces of gold."))
        if line == "custom ,":
            n = floor.pop(w.pos)
            w.inven.append({"item": 30, "name": n, "tval": 75, "weight": 4, "number": 1, "equip": False})
    p.cmd = cmd
    p.mover = type("M", (), {"active": False, "go": lambda self, t: True, "tick": lambda self: "arrived",
                             "stop": lambda self: None})()

    def run(g):
        for _ in range(200):
            g.t = -99.0
            _floor_sync(w, floor)
            r = g.tick(p)
            if r:
                return r
    a = run(P.HouseBank("deposit"))
    dep = dict(floor)
    p.seen_drained = {"STR": (58, 68)}
    b = run(P.HouseBank("withdraw"))
    ok = a and b and dep.get((60, 128)) == "$5000" and sorted(v for k, v in dep.items() if k != (60, 128)) == \
        ["2 Wands of Stone to Mud (21 charges)", "a Potion of Restore Strength"] and \
        any("Restore Strength" in i["name"] for i in w.items()) and w.ind["gold"][0] == 5300 and \
        list(floor.values()) == ["2 Wands of Stone to Mud (21 charges)"] and w.pos == (60, 130)
    return ok, f"deposit {a}: floor {dep}; withdraw {b}: floor {floor}; pack {[i['name'] for i in w.items()]}"


@case
def tavern_stash_drops_inside():
    """10-27: the tavern stash dropped from the entrance (27,89), which holds no object; the wands landed on the
    street (27,88, 28,88) and townsfolk with TAKE_ITEM took them. The user: the inside is walkable. Now each stash
    stack goes on an empty square inside the room, the farthest from the door first."""
    import tempfile
    mem = {}
    for x in range(89, 95):
        mem[(26, x)] = mem[(29, x)] = "#"
    for y in (27, 28):
        mem[(y, 94)] = "#"
        for x in range(90, 94):
            mem[(y, x)] = "."
    mem[(27, 89)], mem[(28, 89)] = "8", "#"
    for y in range(25, 31):
        mem[(y, 88)] = "."
    p = pilot(pack=[("2 Wands of Stone to Mud (21 charges)", 65), ("a Potion of Restore Dexterity", 75)])
    w = p.w
    w.depth, w.in_dungeon, w.memory, w.pos = 0, False, mem, (27, 88)
    p.rundir, p.busy_until = tempfile.mkdtemp(), 0
    p._house = {"tavern": {"entrance": [27, 89]}}
    floor = {}

    def cmd(line, why, hold=0.4):
        m = re.match(r"custom d item=(\d+)", line)
        if m:
            it = next(i for i in w.inven if i["item"] == int(m.group(1)))
            w.inven.remove(it)
            floor[w.pos] = it["name"]
    p.cmd = cmd

    class M:
        active = False
        def go(self, t):
            w.pos = tuple(t[0])
            return True
        def tick(self):
            return "arrived"
    p.mover = M()
    g = P.StashDeposit()
    r = None
    for _ in range(60):
        g.t = -99.0
        _floor_sync(w, floor)
        r = g.tick(p)
        if r:
            break
    inside = all(26 < y < 29 and 89 < x < 94 for y, x in floor)
    ok = r and r[0] == "done" and len(floor) == 2 and inside and (28, 93) in floor
    return ok, f"{r}; dropped on {floor}"


@case
def house_walk_stops_at_the_crossing():
    """m56: from town, the walk to the edge kept running on the house's tile (toward the town square's coordinates),
    passed the house's outside square, and the bank opened the door from 10 squares off. A level change stops the walk;
    reaching the outside square stops it too."""
    import tempfile
    h = {"door": [60, 129], "step_in": [60, 128], "outside": [60, 130], "box": [59, 124, 61, 129], "depth": -1,
         "cross": {"town": [1, 130], "wild": [64, 130], "depth": -1}}
    p = pilot()
    w = p.w
    w.depth, w.in_dungeon, w.pos, w.level_t = -1, False, (63, 130), P.gnow()
    p.rundir, p.busy_until, p._house = tempfile.mkdtemp(), 0, {"house": h, "banked": 0}
    stops = []
    p.mover = type("M", (), {"active": True, "go": lambda self, t: True, "tick": lambda self: "moving",
                             "stop": lambda self: stops.append(w.pos)})()
    p.cmd = lambda line, why, hold=0.4: None
    g = P.HouseBank("deposit")
    g.seen_level = w.level_t - 5            # (it started in town)
    g.t = -99.0
    g.tick(p)
    first = list(stops)
    w.pos = (60, 130)
    g.t = -99.0
    g.tick(p)
    ok = first == [(63, 130)] and stops[-1] == (60, 130) and g.step == "open"
    return ok, f"stops at {stops}; step {g.step}"


@case
def house_reply_with_and_without_a_house():
    """D10 (session 10): `house` with no argument answers with a house (door, banked, the stash in it) and without one
    (no house; the tavern stash) -- the first version answered "no house owned" or crashed."""
    out = []
    for st in ({"house": {"door": [60, 129], "price": 5455, "bought": "2026-10-27"}, "banked": 100, "t": "x",
                "items": {"60,125": "a Potion of Restore Charisma"}},
               {"tavern": {"entrance": [27, 89], "items": {"27,90": "a Wand of Stone to Mud"}}}):
        p = pilot()
        p.house_state = lambda st=st: st
        p.w.in_dungeon = True
        out.append(p.house_info([]).get("text", ""))
    return "door 60,129" in out[0] and "Restore Charisma" in out[0] and out[1].startswith("no house") and \
        "Stone to Mud" in out[1], f"{out}"


@case
def stash_in_house_json_only():
    """D10 (the user, 11-01): house.json is the stash's only record. An old stash.json (Dive04's) is retired on load:
    its tavern entrance moves into house.json `tavern`, the file is renamed (the notes stay there), nothing is lost;
    stash_has/stash_where read the house's items (while a house is owned), else the tavern's; a fetch strikes the
    item off."""
    import tempfile
    out = []
    for house in (True, False):
        p = pilot()
        p.rundir = tempfile.mkdtemp()
        hj = {"banked": 19327, "items": {"60,125": "a Potion of Restore Charisma"}}
        if house:
            hj["house"] = {"door": [60, 129], "box": [59, 124, 61, 129]}
        json.dump(hj, open(os.path.join(p.rundir, "house.json"), "w"))
        json.dump({"items": ["a Potion of Restore Charisma"] + ([] if house else ["a Potion of Restore Strength"]),
                   "entrance": [27, 89], "squares": [[27, 92]], "lost": ["2 Wands..."], "where": "house"},
                  open(os.path.join(p.rundir, "stash.json"), "w"))
        where = (p.stash_where("Restore Charisma"), p.stash_where("Restore Strength"))
        files = sorted(os.listdir(p.rundir))
        saved = json.load(open(os.path.join(p.rundir, "house.json")))
        retired = json.load(open(os.path.join(p.rundir, files[-1])))
        p.stash_take(where[0] or "tavern", "Restore Charisma")
        out.append((where, files[-1].startswith("stash.json.retired-"), saved.get("tavern"), retired.get("lost"),
                    p.stash_has("Restore Charisma")))
    ok = out[0] == (("house", None), True, {"entrance": [27, 89]}, ["2 Wands..."], False) and \
        out[1][0] == ("tavern", "tavern") and out[1][2]["items"] == {"27,92": "a Potion of Restore Charisma",
                                                                    "?1": "a Potion of Restore Strength"}
    return ok, f"with a house, without: {out}"


@case
def house_withdraw_strikes_the_fetched_item():
    """refactor-candidates E5 (2.45.0): a withdraw that fetched the Restore Strength left it on house.json `items` --
    the strike waited for "already in the pack", but stash_wanted only names a kind the pack lacks -- so `house` still
    listed it, and the next withdraw (STR drained again, the potion drunk) spent 5 pick-ups on the empty square and
    said "no Restore Strength after all". Now it is struck off the record as soon as the pack shows it."""
    import tempfile
    mem = {}
    for x in range(124, 130):
        mem[(59, x)] = mem[(61, x)] = "#"
    mem[(60, 124)], mem[(60, 129)] = "#", "0"
    for x in range(125, 129):
        mem[(60, x)] = "."
    for y in range(57, 64):
        for x in range(130, 134):
            mem[(y, x)] = "."
    hs = P.town_houses(mem)
    h = {k: (list(v) if isinstance(v, tuple) else v) for k, v in hs[0].items() if k != "inside"}
    p = pilot(gold=300)
    w = p.w
    w.depth, w.in_dungeon, w.memory, w.pos = 0, False, mem, (60, 130)
    p.rundir, p.busy_until = tempfile.mkdtemp(), 0
    p._house = {"house": h, "banked": 0, "items": {"60,125": "a Potion of Restore Strength"}}
    floor = {(60, 125): "a Potion of Restore Strength"}
    dirs = {4: (0, -1), 6: (0, 1)}
    sent = []

    def cmd(line, why, hold=0.4):
        sent.append(line)
        m = re.match(r"walk (\d)", line)
        if m:
            dy, dx = dirs[int(m.group(1))]
            w.pos = (w.pos[0] + dy, w.pos[1] + dx)
        if line == "custom ," and w.pos in floor:
            w.inven.append({"item": 30, "name": floor.pop(w.pos), "tval": 75, "weight": 4, "number": 1,
                            "equip": False})
    p.cmd = cmd
    p.mover = type("M", (), {"active": False, "go": lambda self, t: True, "tick": lambda self: "arrived",
                             "stop": lambda self: None})()

    def run(g):
        for _ in range(200):
            g.t = -99.0
            _floor_sync(w, floor)
            r = g.tick(p)
            if r:
                return r
    p.seen_drained = {"STR": (58, 68)}
    a = run(P.HouseBank("withdraw"))
    fetched = any("Restore Strength" in i["name"] for i in w.items())
    record, said = dict(p._house.get("items", {})), p.house_info([])["text"]
    w.inven = [i for i in w.inven if "Restore Strength" not in i["name"]]      # (drunk; STR drained again later)
    sent.clear()
    b = run(P.HouseBank("withdraw"))
    picks = sent.count("custom ,")
    ok = a and b and fetched and record == {} and "stash:" not in said and picks == 0 and \
        not any("after all" in str(d) for _, d in p.notes)
    return ok, f"withdraw {a}: fetched {fetched}, record {record}, `house`: {said!r}; the next withdraw {b}: " \
               f"{picks} pick-ups, notes {p.notes}"


# --- 2.50.0 (the user, 11-04): the stash holds the best backup for each worn slot and the store list; the house first,
# the tavern room when it's full, else a stash_full notice; each record carries its value and whether it was a fresh
# find (credited to the mission)

_DIVE04_WORN = [("a Battle Axe of Westernesse (2d8) (+10,+9) (+1)", 22, 170), ("a Ring of Protection [+16]", 45, 2),
                ("a Ring of Protection [+12]", 45, 2), ("an Amulet of Slow Digestion", 40, 3),
                ("Hard Studded Leather of Resistance (-1) [7,+8]", 36, 110), ("a Shadow Cloak [6,+8]", 35, 5),
                ("an Orcish Shield [5,+8] (+1)", 34, 100), ("a Metal Cap [3,+8]", 32, 20),
                ("a Set of Gauntlets [2,+8]", 31, 25), ("a Pair of Hard Leather Boots of Stability [3,+8]", 30, 40)]


def _dive04_town(pack, worn=None, **kw):
    """Dive04's 11-02 gear (clvl 29, the Battle Axe of Westernesse: Free Action, See Invisible) in town."""
    p = pilot(hp=358, worn=_DIVE04_WORN if worn is None else worn, pack=pack, **kw)
    w = p.w
    w.clvl = 29
    w.ind.update({"armor": [104], "stat0": [88], "stat3": [38]})
    w.flags.update(free_act=1)
    w.depth, w.depth_ft, w.in_dungeon = 0, 0, False
    p.flavour_of = lambda it: None
    p.unknown_flavour = lambda it: False
    p.review_hold = lambda it: False
    p.gear_better = lambda it: None
    return p


@case
def stash_backups_for_worn_slots():
    """2.50.0 (the user): an unworn, unbuyable (ego/artifact), identified wearable worth 200+ that is the best backup for
    its worn slot is stored, never sold. Beside the wielded Battle Axe of Westernesse (Free Action, See Invisible) the
    Scimitar of Westernesse is the weapon backup ("a backup for the weapon slot (Free Action, See Invisible)") and a
    Main Gauche of Slay Evil is not (sold); an ability carrier beats a harder hitter (a Dagger of Westernesse over a
    Trident of Venom); the store wins over the keep list; a stored backup a carried one outclasses is fetched to sell,
    and with the axe gone (nothing wielded) the stored Scimitar is fetched to wear."""
    p = _dive04_town([("a Scimitar of Westernesse (2d5) (+9,+8) (+1)", 23), ("a Main Gauche of Slay Evil (1d5) (+3,+4)", 23)])
    p.keep = {"scimitar of westernesse"}
    sc, mg = p.w.items()
    rules = (p.town_rule(sc), p.town_rule(mg))
    sells = (p.town_sell_count(sc), p.town_sell_count(mg))
    stash = (p.is_stash_item(sc["name"]), p.is_stash_item(mg["name"]))
    d = _dive04_town([("a Trident of Venom (1d8) (+13,+4)", 22), ("a Dagger of Westernesse (1d4) (+1,+1) (+1)", 23)])
    carrier = d.stash_backups()["best"].get("weapon", (None, None))[1]
    o = _dive04_town([("a Scimitar of Westernesse (2d5) (+9,+8) (+1)", 23)])
    o._house = {"house": {"door": [60, 129], "box": [59, 124, 61, 129], "step_in": [60, 128]},
                "items": {"60,125": "a Dagger of Westernesse (1d4) (+1,+1) (+1)"}}
    outclassed = o.stash_fetch_list("house")
    s = _dive04_town([], worn=_DIVE04_WORN[1:])
    s._house = {"house": {"door": [60, 129], "box": [59, 124, 61, 129], "step_in": [60, 128]},
                "items": {"60,125": {"name": "a Scimitar of Westernesse (2d5) (+9,+8) (+1)", "value": 8000}}}
    to_wear = s.stash_fetch_list("house")
    ok = rules == (("keep", "a backup for the weapon slot (Free Action, See Invisible)"), None) and sells[0] == 0 and \
        sells[1] == 1 and stash == (True, False) and carrier == "a Dagger of Westernesse (1d4) (+1,+1) (+1)" and \
        [n for n, _ in outclassed] == ["a Dagger of Westernesse (1d4) (+1,+1) (+1)"] and "to sell" in outclassed[0][1] \
        and [n for n, _ in to_wear] == ["a Scimitar of Westernesse (2d5) (+9,+8) (+1)"] and "to wear" in to_wear[0][1]
    return ok, (f"rules {rules}; sold {sells}; stash {stash}; Trident vs Dagger of Westernesse: {carrier}; stored dagger "
                f"vs carried Scimitar: {outclassed}; axe gone: {to_wear}")


@case
def store_list_matches_and_command():
    """2.50.0 (the user): rundir/store.json, lower-case name parts matched as keep.json is (singular too): "scroll of
    deep descent" takes 2 Scrolls of Deep Descent, which plan town keeps ("on the store list"). `store` lists for all;
    `store add/del NAME` are the Architect's (the Navigator is refused)."""
    import tempfile
    p = _dive04_town([("2 Scrolls of Deep Descent", 70), ("a Scroll of Light", 70)])
    p.rundir = tempfile.mkdtemp()
    nav_add = p.do_request({"cmd": "store", "args": ["add", "scroll_of_deep_descent"], "role": "navigator"})
    arch_add = p.do_request({"cmd": "store", "args": ["add", "Scroll_of_Deep_Descent"], "role": "architect"})
    listing = p.do_request({"cmd": "store", "args": [], "role": "navigator"})
    dd, light = p.w.items()
    rule = p.town_rule(dd)
    match = (p.on_store_list(dd["name"]), p.on_store_list(light["name"]))
    saved = json.load(open(os.path.join(p.rundir, "store.json")))
    gone = p.do_request({"cmd": "store", "args": ["del", "scroll of deep descent"], "role": "architect"})
    ok = not nav_add["ok"] and arch_add["ok"] and "scroll of deep descent" in listing["text"] and \
        rule == ("keep", "on the store list") and match == (True, False) \
        and saved == ["scroll of deep descent"] and gone["ok"] and not p.store_list
    return ok, f"navigator add {nav_add}; architect add {arch_add}; list {listing}; rule {rule}; del {gone}"


def _tavern_room(mem):
    """The tavern (entrance 27,89) and its room: 27-28 x 90-93 (8 squares)."""
    for x in range(89, 95):
        mem[(26, x)] = mem[(29, x)] = "#"
    for y in (27, 28):
        mem[(y, 94)] = "#"
        for x in range(90, 94):
            mem[(y, x)] = "."
    mem[(27, 89)], mem[(28, 89)] = "8", "#"
    return mem


@case
def house_full_overflows_to_the_tavern_then_asks():
    """2.50.0 (the user): with the house's 3 squares used, the deposit doesn't go for the stash; the overflow goes
    inside the tavern room (StashDeposit); with the tavern room full too, the item stays in the pack (never sold) and
    a stash_full notice tells the Navigator to `ask` the Architect -- once a visit per item."""
    import types
    p = _dive04_town([("a Scimitar of Westernesse (2d5) (+9,+8) (+1)", 23)], gold=500)
    p.w.memory = _tavern_room({})
    full = {f"60,{x}": f"a Potion of Restore {s}" for x, s in ((125, "Charisma"), (126, "Wisdom"), (127, "Intelligence"))}
    p._house = {"house": {"door": [60, 129], "box": [59, 124, 61, 129], "step_in": [60, 128], "depth": -1},
                "items": full, "tavern": {"entrance": [27, 89], "items": {}}}
    p.house_save = lambda: None
    ctx = types.SimpleNamespace(w=p.w, now=0.0)
    k = P.TownKit()
    room = p.stash_room()
    dep = k._buying_deposit(p, ctx)
    over = k._buying_overflow(p, ctx)
    sub = type(k.sub).__name__
    k.sub = None
    p.tavern_state()["items"] = {f"{y},{x}": "a Flask of oil" for y in (27, 28) for x in range(90, 94)}
    k2 = P.TownKit()
    k2._buying_overflow(p, ctx)
    sub2 = k2.sub
    k2._buying_stash_full(p, ctx)
    k2._buying_stash_full(p, ctx)
    told = [d for what, d in p.notes if what == "stash_full"]
    sold = p.town_sell_count(p.w.items()[0])
    ok = room == {"house": 0, "tavern": 8} and dep is TG.NEXT and over is None and sub == "StashDeposit" and \
        sub2 is None and len(told) == 1 and "`ask` the Architect" in told[0] and "Scimitar" in told[0] and sold == 0
    return ok, f"room {room}; deposit step {dep}; overflow {sub}; tavern full: overflow {sub2}, notices {told}; sold {sold}"


@case
def stash_records_fresh_and_credited():
    """2.50.0 (the user): each stash record carries its value (x pay_cut), when, fresh, and the mission credited. A find
    picked up in the running mission is fresh -- also once identified (a Dagger {excellent} picked up, stored as the
    Dagger of Westernesse: matched by its base kind); one owned before (no pickup record: Dive04's Scimitar) is not.
    `stash_store` and `stash_take` are logged; a credited item withdrawn and sold logs `stash_credit_sold` (debited);
    withdrawn and worn, no debit. Old plain-name records still read. The scorecard adds the fresh stored values and
    subtracts the debits: gold_change_adj."""
    import tempfile
    import scorecard
    p = _dive04_town([("a Dagger of Westernesse (1d4) (+1,+1) (+1)", 23),
                      ("a Scimitar of Westernesse (2d5) (+9,+8) (+1)", 23)])
    p.rundir = tempfile.mkdtemp()
    logs = []
    p.log = lambda kind, **kw: logs.append((kind, kw))
    p.mission_label = "m70"
    p.note_acquired("a Dagger (1d4) {excellent}")
    dg, sc = p.w.items()
    r_dg, r_sc = p.stash_rec(dg, "house"), p.stash_rec(sc, "tavern")
    p._house = {"house": {"door": [60, 129], "box": [59, 124, 61, 129], "step_in": [60, 128]},
                "items": {"60,125": r_dg, "60,126": "a Potion of Restore Charisma"}, "tavern": {"items": {"27,90": r_sc}}}
    names = p.stash_places()
    p.stash_take("house", "Dagger of Westernesse")
    p.stash_take("tavern", "Scimitar")
    p.stash_credit_sold(dg["name"], 7000)
    p.stash_credit_sold(sc["name"], 7000)
    kinds = [k for k, _ in logs]
    store = [kw for k, kw in logs if k == "stash_store"]
    take = [kw for k, kw in logs if k == "stash_take"]
    sold = [kw for k, kw in logs if k == "stash_credit_sold"]
    # worn after the withdrawal: no debit
    p.acq_state()["credits"]["dagger of westernesse (1d4) (+1,+1) (+1)"] = {"value": 100, "mission": "m70"}
    p.stash_credit_worn("a Dagger of Westernesse (1d4) (+1,+1) (+1)")
    n0 = len(logs)
    p.stash_credit_sold(dg["name"], 7000)
    aud = [{"gold": 1000, "banked": 0, "exp": [0], "clvl": 29, "depth_ft": 0},
           {"gold": 900, "banked": 0, "exp": [10], "clvl": 29, "depth_ft": 0}]
    recs = [{"kind": "stash_store", "value": 7500, "fresh": True}, {"kind": "stash_store", "value": 9000, "fresh": False},
            {"kind": "stash_credit_sold", "credited_value": 2000}]
    A = scorecard.outcome({}, aud, recs)
    ok = r_dg["fresh"] and r_dg["mission"] == "m70" and r_dg["value"] > 1000 and not r_sc["fresh"] and \
        r_sc["mission"] is None and names["house"]["60,126"] == "a Potion of Restore Charisma" and \
        store[0]["fresh"] and take[0]["credited_value"] == r_dg["value"] and take[1]["credited_value"] == 0 and \
        len(sold) == 1 and sold[0]["credited_value"] == r_dg["value"] and p.gold_debited == r_dg["value"] and \
        p.gold_stored == r_dg["value"] and len(logs) == n0 and \
        (A["gold_change"], A["stored_value"], A["stash_debits"], A["gold_change_adj"]) == (-100, 7500, 2000, 5400)
    return ok, (f"dagger {r_dg}; scimitar {r_sc}; logs {kinds}; takes {take}; sold {sold}; scorecard A {A}")


def _house_sim(p, floor, scatter=None):
    """Dive04's 4-square house (door 60,129, the gold's square 60,128) on the town map, and a server for it: walks
    move, `custom d` drops onto the square underfoot -- or, `scatter` {from: to}, where the server's drop_near puts it
    (object2.c:3963: one object a grid) -- `custom ,` takes what lies underfoot, the gold pile is picked up on 60,128."""
    mem = {}
    for x in range(124, 130):
        mem[(59, x)] = mem[(61, x)] = "#"
    mem[(60, 124)], mem[(60, 129)] = "#", "0"
    for x in range(125, 129):
        mem[(60, x)] = "."
    for y in range(57, 64):
        for x in range(130, 134):
            mem[(y, x)] = "."
    h = {k: (list(v) if isinstance(v, tuple) else v) for k, v in P.town_houses(mem)[0].items() if k != "inside"}
    w = p.w
    w.memory, w.pos = mem, (60, 130)
    p.busy_until = 0
    p._house = {"house": h, "banked": 0, "items": {}}
    p.house_save = lambda: None
    sent, logs = [], []
    p.log = lambda kind, **kw: logs.append((kind, kw))
    dirs = {4: (0, -1), 6: (0, 1)}
    scatter = dict(scatter or {})

    def cmd(line, why, hold=0.4):
        sent.append((w.pos, line))
        m = re.match(r"walk (\d)", line)
        if m:
            dy, dx = dirs[int(m.group(1))]
            w.pos = (w.pos[0] + dy, w.pos[1] + dx)
        m = re.match(r"custom d item=(\d+)", line)
        if m:
            it = next(i for i in w.inven if i["item"] == int(m.group(1)))
            w.inven.remove(it)
            floor[scatter.pop(w.pos, w.pos)] = it["name"]
        if line == "custom ," and w.pos in floor:
            w.inven.append({"item": 30, "name": floor.pop(w.pos), "tval": 23, "weight": 4, "number": 1,
                            "equip": False})
    p.cmd = cmd
    p.mover = type("M", (), {"active": False, "go": lambda self, t: True, "tick": lambda self: "arrived",
                             "stop": lambda self: None})()

    def run(g):
        for _ in range(300):
            g.t = -99.0
            _floor_sync(w, floor)
            r = g.tick(p)
            if r:
                return r
    return run, sent, logs


@case
def house_reconcile_rebuilds_the_record():
    """The live check of 11-04: the house held two Potions of Restore Charisma (60,125 and 60,126), house.json knew
    one. Now a visit inside first reads every square but the gold's and rebuilds the record from the floor: an item
    the record lacks is adopted (stash_found, not fresh), a recorded one not there is struck (stash_take, lost)."""
    p = _dive04_town([], gold=300)
    floor = {(60, 125): "a Potion of Restore Charisma", (60, 127): "a Potion of Restore Wisdom"}
    run, sent, logs = _house_sim(p, floor)
    p._house["items"] = {"60,126": "a Potion of Restore Charisma", "60,127": "a Potion of Restore Charisma"}
    r = run(P.HouseBank("withdraw"))
    items = {k: rec_name(v) for k, v in p._house["items"].items()}
    found = [kw["item"] for k, kw in logs if k == "stash_found"]
    lost = [kw["item"] for k, kw in logs if k == "stash_take" and kw["lost"]]
    ok = r and r[0] == "done" and items == {"60,125": "a Potion of Restore Charisma",
                                             "60,127": "a Potion of Restore Wisdom"} and \
        sorted(found) == ["a Potion of Restore Charisma", "a Potion of Restore Wisdom"] and len(lost) == 2 and \
        not any(line == "custom ," for _, line in sent)
    return ok, f"{r}; record {items}; found {found}; struck {lost}"


@case
def house_deposit_only_on_a_bare_square():
    """The live check of 11-04: `house deposit` dropped the Scimitar on 60,125, which held an unrecorded potion; the
    server scattered it to 60,127 and the record said 125. Now the drop goes only on a square read bare (60,127, the
    one left), and is recorded once seen underfoot; a drop the server scattered anyway (simulated) is found by a
    second reading of the house and recorded where it lies."""
    sc = "a Scimitar of Westernesse (2d5) (+9,+8) (+1)"
    p = _dive04_town([(sc, 23)], gold=300)
    floor = {(60, 125): "a Potion of Restore Charisma", (60, 126): "a Potion of Restore Charisma"}
    run, sent, logs = _house_sim(p, floor)
    p._house["items"] = {"60,126": "a Potion of Restore Charisma"}
    r = run(P.HouseBank("deposit"))
    items = {k: rec_name(v) for k, v in p._house["items"].items()}
    drops = [pos for pos, line in sent if line.startswith("custom d")]
    q = _dive04_town([(sc, 23)], gold=300)
    qfloor = {}
    run2, sent2, logs2 = _house_sim(q, qfloor, scatter={(60, 125): (60, 127)})
    r2 = run2(P.HouseBank("deposit"))
    items2 = {k: rec_name(v) for k, v in q._house["items"].items()}
    stored2 = [kw["item"] for k, kw in logs2 if k == "stash_store"]
    ok = r and r[0] == "done" and drops == [(60, 127)] and items.get("60,127") == sc and floor[(60, 127)] == sc and \
        items.get("60,125") == "a Potion of Restore Charisma" and r2 and r2[0] == "done" and \
        items2 == {"60,127": sc} and qfloor == {(60, 127): sc} and stored2 == [sc]
    return ok, f"{r}: drops at {drops}, record {items}; scattered: {r2}, record {items2}, floor {qfloor}, logs {stored2}"


@case
def house_never_picks_up_the_wrong_item():
    """The live check of 11-04: `house withdraw scimitar` pressed `,` on 60,125 (the record's square), took the
    potion lying there, and the pickup reflex took the Scimitar from 60,127 on the way out. Now `,` is pressed only
    when the floor underfoot names the item: the record is read again and the Scimitar fetched from 60,127; the potion
    stays (adopted on 60,125). Inside the house the pickup reflex takes nothing but the fetch target (in_house)."""
    sc = "a Scimitar of Westernesse (2d5) (+9,+8) (+1)"
    p = _dive04_town([], gold=300)
    floor = {(60, 125): "a Potion of Restore Charisma", (60, 127): sc}
    run, sent, logs = _house_sim(p, floor)
    p._house["items"] = {"60,125": sc}
    r = run(P.HouseBank("withdraw", fetch=[sc]))
    picks = [pos for pos, line in sent if line == "custom ,"]
    items = {k: rec_name(v) for k, v in p._house["items"].items()}
    p.w.pos = (60, 126)
    inside = p.in_house()
    p.w.pos = (60, 130)
    outside = p.in_house()
    ok = r and r[0] == "done" and picks == [(60, 127)] and [i["name"] for i in p.w.items()] == [sc] and \
        floor == {(60, 125): "a Potion of Restore Charisma"} and items == {"60,125": "a Potion of Restore Charisma"} \
        and inside and not outside
    return ok, f"{r}: picked up at {picks}; pack {[i['name'] for i in p.w.items()]}; floor {floor}; record {items}; " \
               f"in_house inside {inside}, outside {outside}"


@case
def finds_marked_with_the_mission_label():
    """2.50.0 (the user, 11-04): during a mission a find that could be stored -- a single wearable -- is inscribed with
    the mission's label (`{m62}`; a feeling kept: `{excellent - m62}`, the server's own format, which Identify keeps),
    never over the Navigator's tags nor on a stackable or a potion; with no mission, nothing. At store time an item
    inscribed with the running mission's label is fresh, one with another mission's is not, and an unlabelled one
    (a Navigator-inscribed item) falls back to the pickup record. The name helpers ignore the label."""
    import tempfile
    import itemvalue
    from common import bare_name, bad_inscription
    sc = "a Scimitar of Westernesse (2d5) (+9,+8) (+1)"
    p = _dive04_town([("a Dagger (1d4)", 23), ("a Main Gauche (1d5) {excellent}", 23), ("a Spear (1d6) {@w1}", 22),
                      ("a Potion of Restore Strength", 75), ("2 Wooden Torches (with 5000 turns of light)", 39),
                      ("a Pair of Leather Boots (1d1) {tried}", 30)])
    p.rundir = tempfile.mkdtemp()
    p.mission_label = "m62"
    labels = [p.inscribe_label(i) for i in p.w.items()]
    p.mission_label = None
    none = [p.inscribe_label(i) for i in p.w.items()]
    p.mission_label = "m62"
    sent = []
    p.cmd = lambda line, why, hold=0.4: sent.append(line)
    p.note_acquired("a Dagger (1d4)")
    p.w.inven_dirty = False
    acted = p.inscribe_finds()
    # freshness at store time
    p.note_acquired("a Spear (1d6) {@w1}")
    fresh = {n: p.acquired_fresh(n)[0] for n in (f"{sc} {{m62}}", f"{sc} {{excellent - m62}}", f"{sc} {{m61}}",
                                                    "a Spear (1d6) {@w1}", sc)}
    # the name helpers
    p.keep = {"scimitar of westernesse"}
    mg = "a Main Gauche of Slay Evil (1d5) (+3,+4) {excellent - m62}"
    helpers = (p.is_kept(f"{sc} {{m62}}"), bad_inscription(f"{sc} {{m62}}"), bare_name(f"{sc} {{excellent - m62}}"),
               p.same_item(f"{sc} {{m62}}", sc), p.probably_special(mg),
               p.probably_special("a Main Gauche (1d5) {excellent - m62}"),
               itemvalue.value(mg).value == itemvalue.value("a Main Gauche of Slay Evil (1d5) (+3,+4)").value)
    t = _dive04_town([(f"{sc} {{m62}}", 23), (mg, 23)])
    rules = [t.town_rule(i) for i in t.w.items()]
    sold = t.town_sell_count(t.w.items()[1])
    ok = labels == ["m62", "excellent - m62", None, None, None, "m62"] and none == [None] * 6 and acted and \
        sent == ["custom { item=0 entry=m62"] and \
        fresh == {f"{sc} {{m62}}": True, f"{sc} {{excellent - m62}}": True, f"{sc} {{m61}}": False,
                  "a Spear (1d6) {@w1}": True, sc: False} and \
        helpers == (True, False, "Scimitar of Westernesse (2d5) (+9,+8) (+1)", True, False, True, True) and \
        rules[0] == ("keep", "a backup for the weapon slot (Free Action, See Invisible)") and rules[1] is None and \
        sold == 1
    return ok, (f"labels {labels}; no mission {none}; inscribe {acted} {sent}; fresh {fresh}; helpers {helpers}; "
                f"town rules {rules}; the Main Gauche sold {sold}")


@case
def backups_must_be_worth_it():
    """2.51.0 (the user after m62: a Ring of Slow Digestion, ~75 at sale, the amulet already giving slow digestion,
    took a tavern square): a backup is worth 1000+ at sale (value x pay_cut) or gives an ability the other worn gear
    doesn't. The Scimitar of Westernesse (~8000 at sale) stays the weapon backup; the Ring of Slow Digestion is no
    backup; a Ring of Free Action is one only when nothing else worn gives Free Action. The stored Ring of Slow
    Digestion {m62} (credited to m62) is fetched at the next plan town to be sold -- past the review queue -- and its
    sale debits the credit."""
    sc = "a Scimitar of Westernesse (2d5) (+9,+8) (+1)"
    p = _dive04_town([(sc, 23), ("a Ring of Slow Digestion {m62}", 45), ("a Ring of Free Action", 45)])
    rules = {i["name"]: p.town_rule(i) for i in p.w.items()}
    plain = [("a Spear (1d6) (+5,+7)", 22, 50)] + _DIVE04_WORN[1:]
    q = _dive04_town([("a Ring of Free Action", 45)], worn=plain)
    q.w.flags.update(free_act=0)
    fa = q.town_rule(q.w.items()[0])
    t = _dive04_town([])
    logs = []
    t.log = lambda kind, **kw: logs.append((kind, kw))
    t.house_save = lambda: None
    t._house = {"house": {"door": [60, 129], "box": [59, 124, 61, 129], "step_in": [60, 128]},
                "items": {"60,125": {"name": sc, "value": 8000, "fresh": False, "mission": None}},
                "tavern": {"entrance": [27, 89], "items": {"27,93": {"name": "a Ring of Slow Digestion {m62}",
                                                                      "value": 95, "fresh": True, "mission": "m62"}}}}
    fetch = t.stash_fetch_list("tavern")
    house = t.stash_fetch_list("house")
    t.stash_take("tavern", "Ring of Slow Digestion", (27, 93))
    t.w.inven.append({"item": 0, "name": "a Ring of Slow Digestion {m62}", "tval": 45, "weight": 1, "number": 1,
                      "equip": False})
    t.review_hold = P.Pilot.review_hold.__get__(t)
    held = t.review_hold(t.w.items()[0])
    t.stash_credit_sold("a Ring of Slow Digestion {m62}", 90)
    sold = [kw for k, kw in logs if k == "stash_credit_sold"]
    ok = rules[sc] == ("keep", "a backup for the weapon slot (Free Action, See Invisible)") and \
        rules["a Ring of Slow Digestion {m62}"] is None and rules["a Ring of Free Action"] is None and \
        fa == ("keep", "a backup for the ring slot (Free Action)") and \
        [n for n, _ in fetch] == ["a Ring of Slow Digestion {m62}"] and fetch[0][1].endswith("to sell") and \
        house == [] and not held and len(sold) == 1 and sold[0]["credited_value"] == 95
    return ok, f"rules {rules}; FA ring with no FA worn {fa}; tavern fetch {fetch}; house {house}; review held {held}; " \
               f"debit {sold}"


def _stale_bank(floor_gold):
    """m63 (2.52.0): the house record says 25444 banked but the pile is gone (the idle gold fetch took it; the purse
    holds it). A deposit reads the gold's square: bare -> banks from the purse; still gold -> picks it up first."""
    import tempfile
    houses = P.town_houses(_town_memory())
    h = dict({k: (list(v) if isinstance(v, tuple) else v) for k, v in houses[0].items() if k != "inside"},
             depth=-1, cross={"town": [1, 130], "wild": [64, 130], "depth": -1})
    p = pilot(gold=25974 if not floor_gold else 530)
    w = p.w
    w.depth, w.in_dungeon, w.memory, w.pos = 0, False, _town_memory(), (1, 130)
    p.rundir, p.busy_until = tempfile.mkdtemp(), 0
    p._house = {"house": h, "banked": 25444}
    inside = tuple(h["step_in"]) if h.get("step_in") else None
    floor = {inside: "gold"} if floor_gold else {}
    dirs = {1: (1, -1), 2: (1, 0), 3: (1, 1), 4: (0, -1), 6: (0, 1), 7: (-1, -1), 8: (-1, 0), 9: (-1, 1)}
    sent = []

    def cmd(line, why, hold=0.4):
        sent.append(line)
        m = re.match(r"walk (\d)", line)
        if m:
            if w.depth == 0 and w.pos == (1, 130) and m.group(1) == "8":
                w.depth, w.pos = -1, (38, 154)
            elif w.depth == -1 and w.pos == (64, 130) and m.group(1) == "2":
                w.depth, w.pos = 0, (1, 130)
            else:
                dy, dx = dirs.get(int(m.group(1)), (0, 0))
                w.pos = (w.pos[0] + dy, w.pos[1] + dx)
        if line == "custom ," and floor.get(w.pos) == "gold":
            del floor[w.pos]
            w.ind["gold"][0] += 25444
        m = re.match(r"custom \$ value=(\d+)", line)
        if m:
            w.ind["gold"][0] -= int(m.group(1))
            w.messages.append((P.gnow(), f"You drop {m.group(1)} pieces of gold."))
        _floor_sync(w, {k: ("$gold" if v == "gold" else v) for k, v in floor.items()})
        if floor.get(w.pos) == "gold":
            w.floor = "gold"
    p.cmd = cmd

    class M:
        active = False
        def go(self, t):
            w.pos = tuple(t[0])
            return True
        def tick(self):
            return "arrived"
        def stop(self):
            pass
    p.mover = M()
    g = P.HouseBank("deposit")
    r = None
    for _ in range(120):
        g.t = -99.0
        r = g.tick(p)
        if r:
            break
    return r, p, sent


@case
def stale_bank_record_recovers():
    """m63 (2.52.0): the record said 25444 banked with the pile in the purse, so every deposit refused ("wasn't
    picked up") and the gold went to the dungeon twice. Now the gold's square is read: bare -> the record was stale,
    the purse is banked (keep 300); gold there -> `,` picks it up, then the deposit; and the idle gold fetch never
    targets a square inside the house."""
    r1, p1, s1 = _stale_bank(False)
    r2, p2, s2 = _stale_bank(True)
    stale = any(what == "tactic" and "record was stale" in d for what, d in p1.notes)
    h = p1.house_state()["house"]
    y1, x1, y2, x2 = h["box"]
    inside_sq = ((y1 + y2) // 2, (x1 + x2) // 2)
    p1.w.depth, p1.w.in_dungeon = -1, False
    in_house = p1.house_square(inside_sq)
    outside = p1.house_square((y1 - 1, x1))
    p1.w.depth = 0
    town = p1.house_square(inside_sq)
    ok = r1 and r1[0] == "done" and p1.banked() == 25674 and stale and \
        r2 and r2[0] == "done" and "custom ," in s2 and p2.banked() == 25674 and in_house and not outside and not town
    return ok, (f"bare: {r1}, banked {p1.banked()}, stale news {stale}; gold there: {r2}, banked {p2.banked()}, "
                f"',' sent {'custom ,' in s2}; house_square inside {in_house}, outside {outside}, from town {town}")


@case
def refused_drops_end_the_stash_step():
    """2.53.0 (m63 11:11-11:14: "You can not drop this here." ~600 times for the Phial -- a true artifact can't be
    dropped above its depth, object2.c inven_drop_okay): artifacts are never stash items; and any drop the server
    refuses ends that item's stashing for the visit at once (news), any 3 drops that didn't happen too -- in the house
    (HouseBank) and in the tavern room (StashDeposit). The Phial in the pack is kept, never sold by the policy."""
    p = _dive04_town([("a Potion of Restore Strength", 75)], gold=300)
    floor = {}
    run, sent, logs = _house_sim(p, floor)
    sim = p.cmd

    def refuse(line, why, hold=0.4):
        if line.startswith("custom d"):
            sent.append((p.w.pos, line))
            p.w.messages.append((P.gnow(), "You can not drop this here."))
            return
        sim(line, why, hold)
    p.cmd = refuse
    r = run(P.HouseBank("deposit"))
    drops = [line for _, line in sent if line.startswith("custom d")]
    told = [d for k, d in p.notes if k == "tactic" and "not stashed this visit" in str(d)]
    # the tavern room: drops that just don't happen (no message) -- 3, then given up
    t = _dive04_town([("a Potion of Restore Strength", 75)])
    t.w.memory = _tavern_room({})
    t.w.pos = (27, 88)
    t._house = {"tavern": {"entrance": [27, 89], "items": {}}}
    t.house_save = lambda: None
    tsent = []
    t.cmd = lambda line, why, hold=0.4: tsent.append(line)

    class M:
        active = False
        def go(self, tg):
            t.w.pos = tuple(tg[0])
            return True
        def tick(self):
            return "arrived"
    t.mover = M()
    g = P.StashDeposit()
    tr = None
    for _ in range(80):
        g.t = -99.0
        _floor_sync(t.w, {})
        tr = g.tick(t)
        if tr:
            break
    phial = _dive04_town([("a Phial {m63}", 39)])
    ph = phial.w.items()[0]
    ok = r and r[0] == "done" and len(drops) == 1 and told and tr and tr[0] == "done" and \
        sum(1 for line in tsent if line.startswith("custom d")) == 3 and not phial.is_stash_item(ph["name"]) and \
        phial.town_rule(ph)[0] == "keep" and "artifact" in phial.town_rule(ph)[1] and phial.town_sell_count(ph) == 0
    return ok, f"house: {r}, drops {drops}, news {told}; tavern: {tr}, drops {tsent}; Phial rule {phial.town_rule(ph)}"


@case
def a_permanent_light_beats_the_lantern():
    """2.53.0 (the user, m63: the Phial sat in the pack as "a backup for the light slot"; the gear evaluator ties it
    with the Brass Lantern): a light needing no fuel with a radius at least the worn one's (the Phial: an artifact,
    radius 3, xtra1.c calc_torch) beats a fuelled one (the lantern: 2). The upgrade step wields it (at a safe moment in
    the dungeon too); then no oil is needed: no flasks to buy, the lantern and the flasks are sold in town, the supply
    line says "light permanent"."""
    lantern = ("a Brass Lantern (with 9000 turns of light)", 39, 50)
    d = _dive04_town([("a Phial {m63}", 39)], worn=_DIVE04_WORN + [lantern])
    d.w.in_dungeon, d.w.depth, d.w.depth_ft = True, 16, 800
    sent = []
    d.cmd = lambda line, why, hold=0.4: sent.append(line)
    d.gear_swapped_t = P.gnow()
    acted = d.upgrade_step()
    ph, ln = d.w.items()[0], d.w.items(equip=True)[-1]
    better = (d.light_better(ph, ln), d.light_better(ln, ph))
    t = _dive04_town([lantern[:2], ("3 Flasks of oil", 77)], worn=_DIVE04_WORN + [("a Phial {m63}", 39, 10)])
    t.w.hunger = 3
    t.w.flags = {}
    sells = [t.town_sell_count(i) for i in t.w.items()]
    ok = acted and sent == [f"custom w item={ph['item']}"] and better == (True, False) and \
        t.lantern_fuel() is None and t.flasks_to_fill() == 0 and "light permanent" in t.supply_text() and \
        sells == [1, 3]
    return ok, f"upgrade {acted} {sent}; better {better}; town: fuel {t.lantern_fuel()}, flasks {t.flasks_to_fill()}, " \
               f"{t.supply_text()!r}, sells {sells}"
