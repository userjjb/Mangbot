"""unit_house -- unit cases: House bank and stash.

Run by unit.py (python3 unit.py [NAME]); W, pilot() and the other shared fixtures are in fixtures.py.
"""
import json
import os
import re

from fixtures import P, case, pilot


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
        for _ in range(80):
            g.t = -99.0
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
    for _ in range(30):
        g.t = -99.0
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
        for _ in range(80):
            g.t = -99.0
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
