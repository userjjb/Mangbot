"""town_goals -- the town goals (refactor-candidates E1; docs/goals-and-plans.md): Town (back from the wilderness),
TownFarm, Shop, StashDeposit/StashFetch, HouseBank and TownKit (the town visit), with the map helpers they share with
the Pilot (edge_of, town_houses). pilot.py imports them all back (P.TownKit, P.town_houses, ...).
"""
import os
import re
import sys
import time

from common import HERE, TV_SCROLL, TV_LITE, flavour_key, kind_key, bare_name, singular
from world import gnow, waited, light_turns
from mover import direction, MAX_HGT, MAX_WID
from goals import Goal, Wait
if os.path.join(HERE, "..", "observe") not in sys.path:     # (shopmath, as pilot.py loads it)
    sys.path.insert(0, os.path.join(HERE, "..", "observe"))
import shopmath                                  # noqa: E402


EDGE_DIR = {"E": 6, "W": 4, "N": 8, "S": 2}


def edge_of(pos):
    """The map edge a surface position is on (where walking out leaves the
    sector), or None."""
    if not pos:
        return None
    y, x = pos
    if x >= MAX_WID - 3:
        return "E"
    if x <= 2:
        return "W"
    if y <= 2:
        return "N"
    if y >= MAX_HGT - 3:
        return "S"
    return None


class Town(Goal):
    """From the wilderness back to town: leave each sector by the edge we came
    in through (a stack of arrival edges; mission 13 ran off the town map at
    night and no goal could walk back)."""
    name = "town"

    def __init__(self):
        self.step_t = 0.0

    def tick(self, p):
        w = p.w
        if w.depth == 0:
            return ("done", "in town")
        if w.in_dungeon:
            return ("failed", "in the dungeon: use goal dive 0 or goal recall")
        edge = p.wild_trail[-1] if p.wild_trail else edge_of(w.arrive_pos or w.pos)
        if edge is None:
            return ("failed", "don't know which edge leads back: read Word of Recall")
        d = EDGE_DIR[edge]
        if edge_of(w.pos) == edge:
            if waited(self.step_t, 0.8):
                self.step_t = gnow()
                p.mover.stop()
                p.cmd(f"walk {d}", f"town: step off the {edge} edge", hold=0.5)
            return None
        line = [(y, MAX_WID - 2) for y in range(2, MAX_HGT - 2)] if edge == "E" else \
            [(y, 1) for y in range(2, MAX_HGT - 2)] if edge == "W" else \
            [(1, x) for x in range(2, MAX_WID - 2)] if edge == "N" else \
            [(MAX_HGT - 2, x) for x in range(2, MAX_WID - 2)]
        if not p.mover.active and not p.mover.go(line):
            return ("failed", f"no path to the {edge} edge")
        p.mover.tick()
        return None


class TownFarm(Goal):
    """In town: kill townspeople who drop gold until gold reaches a target
    (the user, 2026-10-07: when a purchase is a little short, this is faster
    than a short dive, and it saves the Word of Recall a dive would burn)."""
    TARGETS = ("Singing, happy drunk", "Aimless-looking merchant", "Squint-eyed rogue",
               "Mean-looking mercenary", "Battle-scarred veteran")

    def __init__(self, gold, minutes=10):
        self.target_gold, self.end = int(gold), gnow() + 60 * float(minutes)
        self.name = f"townfarm to {self.target_gold} gold"
        self.light_t = self.wander_t = 0.0
        self.chasing = None
        self.sweep = []
        self.check = None

    def tick(self, p):
        w = p.w
        if w.depth != 0:
            return ("failed", "townfarm is for the town")
        gold = w.ind.get("gold", [0])[0]
        if gold >= self.target_gold:
            return ("done", f"{gold} gold")
        # say so when it isn't working (the demo: 2.5 min at 0 gold, at night)
        if self.check is None:
            self.check = (gnow(), gold)
        elif gnow() - self.check[0] > 120:
            if gold <= self.check[1]:
                # done, not just a warning: townspeople thin out after ~3 min and
                # come back slowly (missions 18-19 farmed 4 more minutes for nothing)
                return ("done", f"stopped at {gold} gold: no gold in 2 minutes "
                                f"({'night: few townspeople' if w.is_day() is False else 'the townspeople have thinned out'}); "
                                "selling spare items may be faster, or try again later")
            self.check = (gnow(), gold)
        if gnow() > self.end:
            return ("done", f"time's up at {gold} gold")
        # light, to see them at night (a dead or dying torch counts as none:
        # mission 14 stood 2 min in the dark with a lantern in the pack)
        worn = next((i for i in w.items(equip=True) if i["tval"] == TV_LITE), None)
        wt = light_turns(worn["name"]) if worn else None
        if (not worn or (wt is not None and wt < 100)) and waited(self.light_t, 5):
            if p.wear_light("townfarm"):
                self.light_t = gnow()
                return None
        # Thieves first, on sight (the Advisor's Navigator-decisions memo: ~120
        # gold stolen by urchins and rogues in mission 15's townfarm): anything
        # with a stealing touch within 8 squares
        thieves = [(y, x, r) for y, x, r in w.monsters if any("EAT_" in b for b in r.blows) and w.dist((y, x)) <= 8]
        if thieves:
            # item thieves (rogues: a Phase Door, mission 19) before gold ones (urchins)
            return self.chase(p, min(thieves, key=lambda m: (w.dist(m[:2]) > 1,
                                                            not any("EAT_ITEM" in b for b in m[2].blows),
                                                            w.dist(m[:2]))))
        # gold lying around (a kill's drop): walk over it (pickup takes it)
        coins = [q for q, ch in w.memory.items() if ch == "$" and w.dist(q) <= 15]
        if coins:
            if w.pos in coins:
                w.memory[w.pos] = "."            # (stepping on it picked it up)
                return None
            if not p.mover.active or p.mover.goals != set(coins):
                p.mover.go(coins)
            p.mover.tick()
            return None
        prey = [(y, x, r) for y, x, r in w.monsters if r.name in self.TARGETS]
        if prey:
            return self.chase(p, min(prey, key=lambda m: w.dist(m[:2])))
        # nobody worth it in view: sweep the town in a zig-zag (the user: few
        # townspeople are visible from the streets by the shops), rows ~7 apart
        st = p.mover.tick() if p.mover.active else "idle"
        if st in ("arrived", "idle", "stuck") or gnow() - self.wander_t > 40:
            self.wander_t = gnow()
            if not self.sweep:
                self.sweep = self.sweep_points(w)
            while self.sweep:
                wy, wx = self.sweep.pop(0)
                cand = [q for q, ch in w.memory.items() if ch == "." and abs(q[0] - wy) <= 3
                        and abs(q[1] - wx) <= 6 and w.dist(q) > 4]
                if cand and p.mover.go([min(cand, key=lambda q: abs(q[0] - wy) + abs(q[1] - wx))]):
                    break
        return None

    def chase(self, p, mon):
        w = p.w
        y, x, r = mon
        if w.dist((y, x)) <= 1:
            p.mover.stop()
            if any("EAT_" in b for b in r.blows) and waited(getattr(self, "hit_t", 0), 0.35):
                # a thief: hit it ourselves -- auto-retaliate picks its own target,
                # and in a crowd it killed idiots and beggars while an urchin
                # beside us stole twice (mission 17). Clear first: a walk queued
                # for a thief already dead moved us instead (mission 19)
                self.hit_t = gnow()
                p.c.send("clear")
                p.cmd(f"walk {direction(w.pos, (y, x))}", f"townfarm: hit the {r.name} first (a thief)", hold=0.2)
            return None                      # adjacent: auto-retaliate fights
        near = [(y + dy, x + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
        if not p.mover.active or self.chasing != (y, x):
            self.chasing = (y, x)
            p.mover.go(near)
        p.mover.tick()
        return None

    @staticmethod
    def sweep_points(w):
        """Waypoints for a boustrophedon over the known town: across each row
        band, alternating direction, starting with the band nearest us."""
        floor = [q for q, ch in w.memory.items() if ch == "." and 2 < q[0] < MAX_HGT - 3 and 2 < q[1] < MAX_WID - 3]
        if not floor:
            return []
        y0, y1 = min(q[0] for q in floor), max(q[0] for q in floor)
        x0, x1 = min(q[1] for q in floor), max(q[1] for q in floor)
        rows = list(range(y0 + 2, y1 + 1, 7)) or [y0]
        start = min(range(len(rows)), key=lambda i: abs(rows[i] - (w.pos or (y0, x0))[0]))
        rows = rows[start:] + rows[:start]
        pts = []
        for i, yy in enumerate(rows):
            xs = list(range(x0 + 4, x1 - 3, 20)) + [x1 - 4]
            pts += [(yy, xx) for xx in (xs if i % 2 == 0 else xs[::-1])]
        return pts


class Shop(Goal):
    """In town: walk into store N, sell and buy, leave.
    sells: [(item index, count)]; buys: [(name substring, count)]."""

    def __init__(self, store, buys=(), sells=(), list_stock=False):
        self.store = str(store)
        self.list_stock = list_stock
        # Sell from the end of the pack first: selling shifts the letters after it
        # (names are resolved when their turn comes)
        self.buys = list(buys)
        self.sells = sorted([s for s in sells if isinstance(s[0], int)], reverse=True) + \
            [s for s in sells if isinstance(s[0], str)]
        self.name = f"shop {store}" + "".join(f" buy {b[0]}:{b[1]}" + (f"@{b[2]}" if len(b) > 2 and b[2] else "") for b in buys) + \
            "".join(f" {'quote' if s[2:] else 'sell'} {chr(97 + s[0]) if isinstance(s[0], int) else s[0]}:{s[1]}"
                    for s in sells)
        self.state = "walk"
        self.t = 0.0
        self.done_log = []
        self.pending = None

    def tick(self, p):
        w = p.w
        if w.depth:
            return ("failed", "not in town")
        if self.state == "walk":
            door = w.find(self.store)
            if not door:
                return ("failed", f"store {self.store} not on the map")
            # Next to the door; unseen ground counts (at night the floor isn't drawn)
            spots = [(door[0][0] + dy, door[0][1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                     if (dy or dx) and w.memory.get((door[0][0] + dy, door[0][1] + dx), " ") not in "#%*=012345678"]
            if w.pos in spots:
                p.cmd(f"walk {direction(w.pos, door[0])}", f"enter store {self.store}", hold=0.3)
                self.state, self.t = "enter", gnow()
                return None
            if not p.mover.active and not p.mover.go(spots):
                return ("failed", "can't reach the store")
            if p.mover.tick() == "stuck":
                return ("failed", "stuck on the way to the store")
            return None
        if self.state == "enter":
            if w.store and w.store_t >= self.t:
                self.state = "trade"
                return None
            if waited(self.t, 4):
                self.state = "walk"
            return None
        if self.state == "trade":
            p.note_store()
            sp = getattr(self, "sale_pending", None)
            if sp and (w.store_t > sp["t"] or waited(sp["t"], 3)):
                key = bare_name(sp["sold_as"]).lower()
                relist = next((i["price"] for i in (w.store or {}).get("items", [])
                               if bare_name(i["name"]).lower() == key),
                              None) if w.store_t > sp["t"] else None
                p.log("sale", **{k: v for k, v in sp.items() if k != "t"}, relist=relist)
                if sp.get("forced") and self.role != "architect":
                    chr_v = (p.w.ind.get("stat5") or [3])[0]
                    fair = shopmath.fair_pay(relist, sp.get("owner"), chr_v)
                    if fair is None:
                        fair = round(p.iv(sp["sold_as"]).value * p.pay_cut(p.iv(sp["sold_as"]).tval))   # (p: self is the Shop goal)
                    p.add_debt(fair - sp.get("received", 0), sp["sold_as"], "sold with ! over the value policy")
                self.sale_pending = None
            if self.pending and getattr(self, "quoting", None):
                ts, prompt, _ = w.last_confirm
                m = re.search(r"Accept (\d+) gold", prompt) if ts >= self.pending else None
                if m is None and not waited(self.pending, 4):
                    return None
                self.done_log.append(f"quote: {self.quoting}: {m.group(1)} gold (not sold)" if m else
                                     f"quote: {self.quoting}: no offer (the shop doesn't buy it?)")
                self.pending, self.quoting = None, None
                return None
            if self.pending:
                # The server's answer: a refreshed listing and/or a message
                said = [t for ts, t in w.messages if ts >= self.pending]
                verdict = next((t for t in said if t.startswith(("You sold", "You bought", "I don't want",
                                                                 "You do not have enough", "You cannot carry",
                                                                 "You have no room", "That item"))), None)
                if verdict is None and w.store_t < self.pending and not waited(self.pending, 4):
                    return None   # still waiting
                self.done_log.append(verdict or f"{self.last} (no answer)")
                ms = re.match(r"You sold (.+?) for (\d+) gold", verdict or "")
                if ms and getattr(self, "sale_ctx", None):
                    # the scorecard's sale record: the re-listing comes with the next
                    # store listing (the Advisor's scorecard memo §5.1)
                    self.sale_ctx.update(sold_as=ms.group(1), received=int(ms.group(2)), t=gnow())
                    self.sale_pending = self.sale_ctx
                self.sale_ctx = None
                m = re.match(r"You sold (.+?) for \d+ gold", verdict or "")
                if m and getattr(self, "selling_flavour", None):
                    p.learn_flavour(self.selling_flavour, kind_key(m.group(1)), "sold in a shop")
                    self.selling_flavour = None
                self.pending = None
                w.status_t = 0            # re-read gold before the next purchase
                w.inven_dirty = True
                return None
            if not w.store:
                # Our own non-store command closed it on the server (the client
                # reports that as store_leave with a 'why'): walk back in, twice
                # at most; anything else is the shopkeeper's doing
                if getattr(w, "store_left_why", None) and getattr(self, "reentered", 0) < 2:
                    self.reentered = getattr(self, "reentered", 0) + 1
                    w.store_left_why = None
                    self.state = "walk"
                    return None
                return ("failed", "thrown out of the store")
            if self.list_stock:
                # (mission 8 guessed names one shop trip at a time)
                self.list_stock = False
                self.done_log.append("stock: " + "; ".join(
                    f"{i['name']} {i['price']}" for i in w.store["items"]))
            if self.sells:
                idx, n, *quote = self.sells.pop(0)
                force = isinstance(idx, str) and idx.startswith("!")
                if force:
                    idx = idx[1:]
                if isinstance(idx, str):
                    # By name, resolved now (identifying items re-sorts the pack),
                    # with the whole-word/ambiguity check (not the first substring)
                    try:
                        idx = p.item_index(idx.replace(" ", "_"), pack_only=True)
                    except ValueError as e:
                        self.done_log.append(f"not sold: {e}")
                        return None
                    w.inven_dirty = True
                it = next((i for i in w.items() if i["item"] == idx), None)
                if quote:
                    p.c.send("confirm no")       # (disarm a 'yes' left over: the prompt gets 'no')
                    p.cmd(f"custom s store item={idx} value=1", f"quote {idx}", hold=0.2)
                    self.quoting = it["name"] if it else chr(97 + idx)
                    self.pending = gnow()
                    return None
                why_not = p.unknown_sell_refusal(it, n) if it and not force else None
                if not why_not and it and not force:
                    why_not = p.value_refusal(it, "sell", self.role)
                    if why_not:
                        why_not += "; `sell !NAME` overrides, and adds the value lost to your debt"
                if force and self.role != "architect" and not p.override_allowed():
                    self.done_log.append(f"NOT sold: your freedom to override the Pilot's value policy is "
                                         f"suspended (debt {p.debt_total()} gold): {it['name'] if it else idx}")
                    return None
                if why_not:
                    # (mission 12 sold 2 Potions of Speed and 2 of Heroism for 8 each)
                    self.done_log.append(f"NOT sold ({why_not}; sell !NAME to force): {it['name']}")
                    return None
                # selling an unknown flavour identifies it (store.c): learn the kind
                self.selling_flavour = flavour_key(it["name"]) if it and p.unknown_flavour(it) else None
                self.sale_ctx = {"name_before": it["name"] if it else None, "count": n, "forced": force,
                                 "flavour_aware": not p.unknown_flavour(it) if it else None,
                                 "pluses_known": bool(re.search(r"\([+-]\d+,[+-]\d+\)|\[\d+,[+-]\d+\]|<[+-]\d+>|"
                                                                r"\(\d+ charges?\)|\bof\b", it["name"])) if it else None,
                                 "store": self.store, "owner": (w.store or {}).get("owner")}
                if it and not force and p.probably_special(it["name"]):
                    # Wormtongue's armour was sold unseen for 17 gold: it was Soft
                    # Studded Leather of Resistance (buyback 19834)
                    self.done_log.append(f"NOT sold (probably special, inspect it first; sell !NAME to force): "
                                         f"{it['name']}")
                    return None
                p.c.send("confirm yes")
                p.cmd(f"custom s store item={idx} value={n}", f"sell {idx}x{n}", hold=0.2)
                self.last = f"sell {chr(97 + idx)} x{n}"
                self.pending = gnow()
                return None
            if self.buys and not waited(getattr(self, "need_fresh", 0), 3) and \
                    w.store_t < getattr(self, "need_fresh", 0):
                return None       # (a remainder: wait for the listing after the last purchase)
            if self.buys:
                name, n, cap = (self.buys.pop(0) + (None,))[:3]
                # The cheapest match: the first one can be an expensive enchanted
                # piece (bought a Cloak [1,+4] for 592 instead of a plain one)
                matches = [i for i in w.store["items"] if name.lower() in i["name"].lower()] or \
                    [i for i in w.store["items"] if singular(name) in singular(i["name"])]
                it = min(matches, key=lambda i: i["price"]) if matches else None
                if not it:
                    self.done_log.append(f"no {name} in stock")
                    return None
                if cap is not None and it["price"] > cap:
                    # (mission 8: 'buy To-Dam:3' spent 302 of 366 gold)
                    self.done_log.append(f"NOT bought: {it['name']} costs {it['price']}, over your cap {cap}")
                    return None
                gold = w.ind.get("gold", [0])[0]
                wanted, afford = n, gold // max(1, it["price"])
                n = min(n, it["number"], afford)
                if n <= 0:
                    self.done_log.append(f"can't afford {it['name']} ({it['price']} each, the cheapest in stock)")
                    return None
                if n < wanted:
                    if it["number"] < wanted and afford > it["number"]:
                        # the cheap stack ran out: the rest at the next price, within
                        # the cap (mission 20 asked for 2 Identify and got 1, silently)
                        self.buys.insert(0, (name, wanted - n, cap))
                        self.need_fresh = gnow()
                    else:
                        self.done_log.append(f"only {n} of {wanted} {name}: that's all the gold allows")
                p.cmd(f"custom p store item={it['slot']} value={n} entry={it['price'] * n}",
                      f"buy {it['name']} x{n}", hold=0.2)
                self.last = f"buy {it['name']} x{n} at {it['price']} each"
                self.pending = gnow()
                return None
            if getattr(self, "sale_pending", None):
                return None       # (the last sale's re-listing first: the sale record)
            p.cmd("leave", "leave store", hold=0.3)
            w.store = None
            return ("done", "; ".join(self.done_log) or "nothing to do")
        return None


class StashDeposit(Goal):
    """Leave the stash kinds (Restore potions, Wands of Stone to Mud) in the tavern (8) for the mission (the user,
    2026-10-26: "leave the potions in the tavern during a mission"; the wands were never aimed; recorded in house.json
    `tavern`, refactor-candidates D10). Walk onto the
    entrance; each drop lands on a floor square of the tavern room (drop_near: a shop entrance takes no object).
    Town objects aren't wiped (depth 0 is skipped), but on a live server another player could take them, and a full
    object list compacts objects anywhere. **Dropped from the entrance, a drop can land on the street outside**
    (10-27: the wands went to 27,88 and 28,88 and townsfolk with TAKE_ITEM took them): with a house, HouseBank keeps
    the stash instead (TownKit skips this goal)."""
    name = "stash in the tavern"

    def __init__(self):
        self.t = 0.0
        self.tries = 0
        self.dropped = []

    def tick(self, p):
        w, now = p.w, gnow()
        ent = p.tavern_entrance()
        if not ent:
            return ("done", "no tavern seen on the town map: nothing stashed")
        items = [i for i in w.items() if p.is_stash_item(i["name"])]
        if not items:
            return ("done", "stashed " + ", ".join(self.dropped) if self.dropped else "nothing to stash")
        # Inside the room, on an empty square (the user, 10-27: the inside is walkable). Dropped from the entrance,
        # which takes no object, the wands landed on the street and townsfolk with TAKE_ITEM took them
        room = next((h for h in town_houses(w.memory, door="8") if h["door"] == tuple(ent)), None)
        used = {tuple(int(v) for v in k.split(",")) for k in p.tavern_state().get("items", {}) if "," in k}
        free = [q for q in (room["inside"] if room else []) if q not in used and w.memory.get(q) == "."]
        if not free:
            return ("failed", "no empty square seen inside the tavern room: not dropping at the door")
        target = max(free, key=lambda q: (w.dist(q, tuple(ent)), q))
        if w.pos != target:
            if not p.mover.active:
                self.tries += 1
                if self.tries > 4 or not p.mover.go([target]):
                    return ("failed", f"couldn't reach {target[0]},{target[1]} in the tavern")
            p.mover.tick()
            return None
        if not waited(self.t, 1.0) or now < p.busy_until or w.inven_dirty:
            return None
        it = items[0]
        self.t = now
        p.cmd(f"custom d item={it['item']} value={it['number']}", f"stash in the tavern: {it['name']}", hold=0.8)
        p.tavern_state().setdefault("items", {})[f"{target[0]},{target[1]}"] = it["name"]
        p.house_save()
        self.dropped.append(it["name"])
        return None


class StashFetch(Goal):
    """Fetch one stash kind from the tavern room (a Restore for a drained stat): walk its squares, nearest first,
    until the pack holds it; the pickup reflex takes only what's being fetched."""
    def __init__(self, kind):
        self.kind = kind
        self.name = f"fetch {kind} from the tavern"
        self.visited = set()
        self.target = None
        self.lit = False

    def tick(self, p):
        w = p.w
        if any(self.kind in i["name"] for i in w.items()):
            p.fetching = None
            p.stash_take("tavern", self.kind, w.pos)     # (its square is free for the next stash drop)
            return ("done", f"fetched {self.kind} from the tavern")
        ent = p.tavern_entrance()
        if not ent:
            p.fetching = None
            return ("failed", "no tavern seen on the town map")
        p.fetching = self.kind
        if not self.lit and not any(i["tval"] == TV_LITE for i in w.items(equip=True)):
            self.lit = True                  # (to see the floor items at night)
            if p.wear_light("the tavern floor"):
                return None
        if self.target and w.pos == self.target:
            self.visited.add(self.target)
            self.target = None
            return None                      # (a tick for the pickup reflex)
        if self.target is None or not p.mover.active:
            cands = [q for q, ch in w.memory.items() if w.dist(q, tuple(ent)) <= 4 and q not in self.visited
                     and ch not in "#%8+'" and not ch.isdigit()]
            if not cands:
                p.fetching = None
                p.stash_take("tavern", self.kind)
                return ("failed", f"no {self.kind} left in the tavern")
            # (item glyphs first: '!' potions, '-' wands)
            self.target = min(cands, key=lambda q: (w.memory.get(q) not in "!-?", w.dist(q)))
            if not p.mover.go([self.target]):
                self.visited.add(self.target)
                self.target = None
                return None
        p.mover.tick()
        return None


def town_houses(memory, door="0"):
    """The houses on a town map (the Pilot's memory: walls '#', house doors '0'): rectangles of wall with a door,
    as [{area, door, inside, outside, box}], smallest first. inside: the interior squares; outside: the open square
    across the door from the interior (where we stand to open it)."""
    g = memory.get
    seen, out = set(), []
    for (y, x), ch in sorted(memory.items()):
        wall = "#" + door
        if ch not in wall or (y, x) in seen or g((y - 1, x), " ") in wall or g((y, x - 1), " ") in wall:
            continue
        x2, y2 = x, y
        while g((y, x2 + 1), " ") in wall:
            x2 += 1
        while g((y2 + 1, x), " ") in wall:
            y2 += 1
        if x2 - x < 2 or y2 - y < 2:
            continue
        border = {(y, i) for i in range(x, x2 + 1)} | {(y2, i) for i in range(x, x2 + 1)} | \
            {(j, x) for j in range(y, y2 + 1)} | {(j, x2) for j in range(y, y2 + 1)}
        if not all(g(q, " ") in wall for q in border):
            continue
        seen |= border
        doors = sorted(q for q in border if g(q) == door)
        if len(doors) != 1:
            continue
        dy, dx = doors[0]
        inside = [(j, i) for j in range(y + 1, y2) for i in range(x + 1, x2)]
        # (the door's outward neighbour: across from the interior)
        oy = dy - 1 if dy == y else dy + 1 if dy == y2 else dy
        ox = dx - 1 if dx == x else dx + 1 if dx == x2 else dx
        inn = (dy + (1 if dy == y else -1 if dy == y2 else 0), dx + (1 if dx == x else -1 if dx == x2 else 0))
        # (the street outside may be unmapped at night: anything but a wall or a shop)
        if inn not in inside or g((oy, ox), " ") in "#%0123456789":
            continue
        out.append(dict(area=len(inside), door=(dy, dx), inside=inside, step_in=inn, outside=(oy, ox),
                        box=(y, x, y2, x2)))
    return sorted(out, key=lambda h: (h["area"], h["door"]))


class HouseBank(Goal):
    """The gold bank (the user, 10-27: thieves took ~11,200 gold in five touches, ~10% of the purse each; "buy a house
    and bank gold"). An owned house (Dive04's: the wilderness house north of town, depth -1) keeps what's dropped in
    it (saved with the server; monsters can't enter or take floor gold; cmd2.c, melee2.c). One pile on the square
    inside the door (gold piles never merge, and a drop with no free square vanishes -- object2.c): stepping in picks
    the whole bank up, then a deposit drops all but `keep` back on that square with the door closed. mode: 'buy'
    (open the door: "This house costs N gold."; buy with 'h' if we can spare it, then deposit), 'deposit' or
    'withdraw'."""

    def __init__(self, mode, keep=None, house=None):
        self.mode, self.keep, self.house = mode, keep, house
        self.name = {"buy": "buy a house", "deposit": "bank gold in the house",
                     "withdraw": "take gold from the house"}[mode]
        self.step, self.t, self.tries, self.price = "go", 0.0, 0, None
        self.gold0 = None

    def item_step(self, p, h, inside):
        """Inside, door closed: the stash (the user, 10-27: "move the stash into the wilderness house" -- at 18:10 a
        town monster took a Wand of Stone to Mud off the tavern floor). One stack a square on the interior squares
        other than the gold's; house.json `items` maps square -> name. A deposit drops the stash kinds carried; a
        withdraw fetches the kind a drained stat wants (stash_wanted). Then back to the gold's square. True while
        acting."""
        w = p.w
        st = p.house_state()
        slots = st.setdefault("items", {})
        y1, x1, y2, x2 = h["box"]
        interior = [(y, x) for y in range(y1 + 1, y2) for x in range(x1 + 1, x2)]
        free = [q for q in interior if q != inside and f"{q[0]},{q[1]}" not in slots]

        def walk_to(q):
            dy, dx = (q[0] > w.pos[0]) - (q[0] < w.pos[0]), (q[1] > w.pos[1]) - (q[1] < w.pos[1])
            p.cmd(f"walk {direction(w.pos, (w.pos[0] + dy, w.pos[1] + dx))}", f"house: to {q[0]},{q[1]}", hold=0.6)
            return True
        if self.mode == "deposit":
            it = next((i for i in w.items() if p.is_stash_item(i["name"])), None)
            if it and free:
                q = max(free, key=lambda q: w.dist(q, inside))      # (the far squares first)
                if w.pos != q:
                    return walk_to(q)
                p.cmd(f"custom d item={it['item']} value={it['number']}", f"house: stash {it['name']}", hold=0.8)
                slots[f"{q[0]},{q[1]}"] = it["name"]
                p.house_save()
                return True
            if it and not getattr(self, "full_told", False):
                self.full_told = True
                p.notify("tactic", f"house: no free square for {it['name']} (one stack a square): kept in the pack",
                         news=True)
        if self.mode == "withdraw":
            kind = p.stash_wanted("house")
            key = next((k for k, n in slots.items() if kind and kind in n), None)
            if key:
                q = tuple(int(v) for v in key.split(","))
                if any(kind in i["name"] for i in w.items()):
                    del slots[key]
                    p.fetching = None
                    p.house_save()
                    return True
                if w.pos != q:
                    return walk_to(q)
                self.picks = getattr(self, "picks", 0) + 1
                if self.picks > 4:
                    del slots[key]                 # (not there after all)
                    p.house_save()
                    p.notify("tactic", f"house: no {kind} on {key} after all", news=True)
                    return True
                p.fetching = kind
                p.cmd("custom ,", f"house: pick up the {kind}", hold=0.8)
                return True
        if w.pos != inside:
            return walk_to(inside)
        p.fetching = None
        return False

    def tick(self, p):
        w, now = p.w, gnow()
        h = self.house or p.house_state().get("house")
        if not h:
            return ("failed", "no house owned (`house buy`)")
        hd = int(h.get("depth", 0))
        if w.in_dungeon or (w.depth not in (0, hd)):
            return ("failed", "the house is in town or the tile beside it: go to town first")
        door, inside, outside = tuple(h["door"]), tuple(h["step_in"]), tuple(h["outside"])
        if not waited(self.t, 1.0) or now < p.busy_until or w.inven_dirty:
            return None
        # a wilderness house: walk off the town's edge where we did when it was found, and back the same way
        cross = h.get("cross")
        if hd and self.step not in ("back", "home"):
            if w.depth == 0:
                if self.step == "closed":
                    self.step = "home"            # (back in town: done below)
                else:
                    tc = tuple(cross["town"])
                    if w.pos != tc:
                        if not p.mover.active and not p.mover.go([tc]):
                            return ("failed", f"no way to the town edge at {tc[0]},{tc[1]}")
                        p.mover.tick()
                        self.t = now - 1.0
                        return None
                    self.t = now
                    p.cmd(f"walk {p.edge_dir(tc)}", "house: off the town's edge to the house's tile", hold=1.5)
                    return None
        if self.step == "back":
            if w.depth == 0:
                self.step = "home"
                return None
            wc = tuple(cross["wild"])
            if w.pos != wc:
                if not p.mover.active and not p.mover.go([wc]):
                    return ("failed", f"no way back to the edge at {wc[0]},{wc[1]}")
                p.mover.tick()
                self.t = now - 1.0
                return None
            self.t = now
            p.cmd(f"walk {p.edge_dir(wc)}", "house: back into town", hold=1.5)
            return None
        if self.step == "home":
            st = p.house_state()
            return ("done", f"{self.name}: {st.get('banked', 0)} gold in the house, {w.ind.get('gold', [0])[0]} carried")
        gold = w.ind.get("gold", [0])[0]
        said = [t for ts, t in w.messages if ts >= self.t - 1.0]
        self.t = now
        if self.step != getattr(self, "last_step", None):
            self.last_step, self.tries = self.step, 0
        # (m56: from town, the walk to the edge was still running after the crossing, toward the town square's
        # coordinates on the new tile; it ran through the house's outside square, the bank took that for arrival and
        # opened the door from 10 squares off -- "the door didn't open". A new level stops the walk)
        if w.level_t != getattr(self, "seen_level", None):
            self.seen_level = w.level_t
            p.mover.stop()
        if self.step == "go":
            if w.pos == outside:
                p.mover.stop()
                self.step = "open"
                self.gold_out, self.banked0 = gold, p.banked()
                return None
            if not p.mover.active:
                self.tries += 1
                if self.tries > 3 or not p.mover.go([outside]):
                    return ("failed", f"couldn't reach the house door at {door[0]},{door[1]}")
            p.mover.tick()
            self.t = now - 1.0
            return None
        if self.step == "open":
            if self.mode == "buy" and self.price is None:
                m = next((re.search(r"This house costs (\d+) gold", t) for t in said if "This house costs" in t), None)
                if m:
                    self.price = int(m.group(1))
                elif any("already owned" in t for t in said):
                    return ("failed", "that house is already owned")
                elif self.tries < 6:
                    self.tries += 1
                    p.cmd(f"open {direction(w.pos, door)}", "house: open the door (its price)", hold=0.8)
                    return None
                else:
                    return ("failed", "the door gave no price")
                spare = gold - p.town_reserve()
                if self.price > spare:
                    return ("failed", f"the house costs {self.price}; {spare} gold to spare beyond the reserve")
                self.gold0 = gold
                p.c.send("confirm yes")
                p.cmd(f"custom h dir={direction(w.pos, door)}", f"house: buy it for {self.price}", hold=1.0)
                self.step = "bought"
                return None
            p.cmd(f"open {direction(w.pos, door)}", "house: open the door", hold=0.8)
            self.step = "in1"
            return None
        if self.step == "bought":
            if gold > self.gold0 - self.price:
                self.tries += 1
                if self.tries > 12:
                    return ("failed", "the purchase didn't go through: " + "; ".join(said[-3:]))
                return None
            st = p.house_state()
            if st.get("house"):
                st.setdefault("old_houses", []).append(st["house"])   # (an earlier house: kept on record)
            st["house"] = dict(h, price=self.price, bought=time.strftime("%Y-%m-%d %H:%M"))
            st["banked"] = 0
            p.house_save()
            p.notify("tactic", f"bought the house at {door[0]},{door[1]} for {self.price} gold", news=True)
            self.mode, self.step = "deposit", "in1"      # (the door stays open after a purchase)
            return None
        if self.step == "in1":
            if w.pos == door:
                self.step = "in2"
                return None
            self.tries += 1
            if self.tries > 8:
                return ("failed", "the door didn't open: " + "; ".join(said[-3:]))
            if self.tries % 3 == 0:
                p.cmd(f"open {direction(w.pos, door)}", "house: open the door again", hold=0.8)
            else:
                p.cmd(f"walk {direction(w.pos, door)}", "house: into the doorway", hold=0.6)
            return None
        if self.step == "in2":
            if w.pos == inside:
                self.gold0 = gold
                p.cmd(f"custom c dir={direction(inside, door)}", "house: close the door behind us", hold=0.8)
                self.step = "inside"
                return None
            p.cmd(f"walk {direction(w.pos, inside)}", "house: step inside (the pile is picked up)", hold=0.8)
            return None
        if self.step == "inside":
            st = p.house_state()
            # (stepping in takes the pile. If it didn't, a second drop would find no free square and vanish)
            if self.banked0 and gold < self.gold_out + 0.9 * self.banked0:
                p.notify("tactic", f"house: the bank's {self.banked0} gold wasn't picked up on the way in (carrying "
                                   f"{gold}); nothing dropped -- check the house square", news=True)
                self.mode = "withdraw"
                self.step = "out0"
                return None
            st["banked"] = 0
            p.house_save()
            if not getattr(self, "items_done", False):
                if self.item_step(p, h, inside):
                    return None
                self.items_done = True
            if self.mode == "deposit":
                keep = int(self.keep if self.keep is not None else p.BANK_FLOAT)
                amt = gold - keep
                if amt > 0:
                    p.cmd(f"custom $ value={amt}", f"house: bank {amt} gold (keep {keep})", hold=1.0)
                    self.amt = amt
                    self.step = "dropped"
                    p.house_save()
                    return None
            p.house_save()
            self.step = "out0"
            return None
        if self.step == "dropped":
            if any(t.startswith("You drop") and "gold" in t for t in said) or gold <= self.gold0 - self.amt:
                st = p.house_state()
                st["banked"] = self.amt
                st["t"] = time.strftime("%Y-%m-%d %H:%M")
                p.house_save()
                p.log("bank", banked=self.amt, purse=gold)
                self.step = "out0"
                return None
            self.tries += 1
            if self.tries > 10:
                return ("failed", "the drop didn't show: " + "; ".join(said[-3:]))
            return None
        if self.step == "out0":
            p.cmd(f"open {direction(w.pos, door)}", "house: open the door to leave", hold=0.8)
            self.step = "out1"
            return None
        if self.step == "out1":
            if w.pos == outside:
                p.cmd(f"custom c dir={direction(outside, door)}", "house: close the door", hold=0.8)
                self.step = "closed"
                return None
            nxt = door if w.pos == inside else outside
            self.tries += 1
            if self.tries > 12:
                return ("failed", "couldn't leave the house: " + "; ".join(said[-3:]))
            if self.tries % 4 == 0 and w.pos == inside:
                p.cmd(f"open {direction(w.pos, door)}", "house: open the door again", hold=0.8)
            else:
                p.cmd(f"walk {direction(w.pos, nxt)}", "house: out", hold=0.6)
            return None
        if self.step == "closed":
            st = p.house_state()
            p.log("bank", banked=st.get("banked", 0), purse=gold)
            if hd:
                self.step = "back"
                return None
            return ("done", f"{self.name}: {st.get('banked', 0)} gold in the house, {gold} carried")
        return ("failed", f"unknown step {self.step}")


class TownKit(Goal):
    """plan town (restructure step 2.2): the Pilot's whole town visit, by policy.
    Sell what the policy sells, at the shop that pays (store.c store_will_buy);
    buy Identify for the unknowns worth it, read them, sell what they turn out to
    be; then buy by priority: two Words of Recall, the supply gate's minimums for
    the planned depth, Restore for a drained STR/DEX/CON, the kit's stock levels,
    and last the Navigator's buy list. Each shop is visited once per stage; an
    essential item out of stock gets up to 4 waits of 35 s (RESTOCK_WAITS) for
    the shops to restock (stock turns over every ~33 s)."""

    RESTOCK_WAITS = 4          # critical items out of stock: up to 4 waits of 35 s for the shops to restock
    # set by the Pilot's town_make_room and provision_step (E6: class level, like Goal's)
    room_tries = 0             # items sold or destroyed to make room for the buys (6 at most)
    room_said = None           # "pack full: no room" logged
    swapped = None             # the fuller lantern put on
    fuelled = 0                # lantern fills (3 at most)
    ate = 0                    # rations eaten to Fed (3 at most)

    def __init__(self, kit=None, buylist=()):
        self.kit, self.buylist = kit, list(buylist)
        self.counted = False           # (the review queue's town-visit count, on the first tick)
        self.name = "plan town" + (f" kit={kit}" if kit else "") + \
            "".join(f" buy {s_}/{n}:{c}" + (f"@{cap}" if cap else "") for n, c, cap, s_ in self.buylist)
        self.stage = "upgrade"
        self.queue = []          # store numbers still to visit in this stage
        self.sub = None
        self.t = 0.0
        self.retried = False
        self.done_log = []
        self.sold = self.bought = 0
        self.identified = 0
        self.again = set()

    def tick(self, p):
        w, now = p.w, gnow()
        # (m56: the house step walks to the wilderness tile, depth -1, and this check killed the visit there -- the
        # Opus Navigator's first `ask`)
        if w.in_dungeon or (w.depth and not isinstance(self.sub, HouseBank)):
            return ("failed", "plan town is for the town")
        if not self.counted:
            self.counted = True
            p.review_state()["town_visits"] += 1
            p.review_save()
            p.notify("tactic", f"plan town: came back with {p.supply_text()} (reserves counted)", news=True)
        if self.sub:
            r = self.sub.tick(p)
            if r is None:
                return None
            what = getattr(self.sub, "store", "wait")
            if r[1] and r[1] != "nothing to do":
                self.done_log.append(f"{what}: {r[1]}" if what != "wait" else r[1])
            self.sold += sum(int(m) for m in re.findall(r"You sold .+? for (\d+) gold", r[1] or ""))
            self.bought += sum(int(m) for m in re.findall(r"You bought .+? for (\d+) gold", r[1] or ""))
            self.sub, self.t = None, now
            return None
        if not waited(self.t, 1.0) or now < p.busy_until or w.inven_dirty or p.pending_use:
            return None             # (the pack and gold settle after each step)
        # the bank first: the shopping needs the gold (HouseBank)
        if self.stage == "upgrade" and not getattr(self, "withdrawn", False):
            self.withdrawn = True
            if p.house_state().get("house") and (p.banked() or p.stash_wanted("house")):
                self.sub = HouseBank("withdraw")   # (and the stash kind a drained stat wants)
                return None
        # a drained stat whose Restore waits in the tavern: fetch it first (bought only if it isn't there)
        if self.stage == "upgrade" and not getattr(self, "fetched", False):
            kind = p.stash_wanted("tavern")              # (the house's: fetched above)
            if kind:
                self.sub = StashFetch(kind)
                return None
            self.fetched = True
        if self.stage == "upgrade":
            # wear/wield what the policy prefers before anything is sold
            if p.upgrade_step():
                self.t = now
                return None
            self.stage, self.queue = "sell", p.town_sell_stores()
        if self.stage == "upgrade again":
            # what Identify revealed may be worth wearing (m26 identified a Ring of Protection [+12] and sold it
            # with a ring slot empty)
            if p.upgrade_step():
                self.t = now
                return None
            self.stage = "sell again"
        if self.stage in ("sell", "sell again"):
            last = getattr(self, "last_sell", None)
            if last and last not in self.again and p.town_sells(last):
                # one of an unknown stack sold taught the flavour: the rest, same shop
                self.again.add(last)
                self.queue.insert(0, last)
            self.last_sell = None
            while self.queue:
                store = self.queue.pop(0)
                sells = p.town_sells(store)
                if sells:
                    self.sub = Shop(store, sells=sells)
                    self.sub.role = "pilot"
                    self.last_sell = store
                    return None
            if self.stage == "sell again":
                self.stage = "buy"
            else:
                self.stage = "identify"
        if self.stage == "identify":
            # an Identify scroll for each unknown worth more than one, within the gold
            # that the essentials leave (m24: 3 scrolls when poor). Scrolls in hand are read at the idle
            # tactic's threshold, here: m32's plan replied "identified 0" and the idle tactic then read the
            # leftover scroll on the Oak Staff the Navigator was about to identify
            r = p.identify_step(now)
            if r:
                self.identified += r is True        # ("light": it put the lantern on first)
                self.t = now + 1.0
                return None
            want = p.town_identify_wanted()
            have = p.kit_count("Identify")
            spare = w.ind.get("gold", [0])[0] - p.town_reserve()
            n = min(want - have, spare // max(1, p.price_of("Identify", 5)))
            if n > 0 and not getattr(self, "id_bought", False):
                self.id_bought = True
                self.sub = Shop(5, buys=[("Identify", n, round(p.price_of("Identify", 5) * 1.5))])
                self.sub.role = "pilot"
                return None
            self.stage = "upgrade again" if self.identified else "buy"
            self.queue = p.town_sell_stores() if self.identified else []
            return None
        if self.stage == "buy":
            # Short of a Word of Recall and the gold for it, by day: townfarm the difference first (the user,
            # 2026-10-24: m27 ended broke; townfarm made ~120 gold a minute by day in m14, little at night)
            if not self.queue and p.broke_for_recall() and not getattr(self, "farmed", False):
                self.farmed = True
                if w.is_day():
                    gold = w.ind.get("gold", [0])[0]
                    need = (p.price_of("Word of Recall", 5) or 250) * (2 - p.kit_count("Word of Recall")) + 20
                    self.sub = TownFarm(gold + need, minutes=5)
                    self.done_log.append(f"short of Word of Recall: townfarm to {gold + need} gold")
                    return None
                self.done_log.append("short of Word of Recall, and it's night (townfarm earns little): saving the gold")
            if not self.queue:
                buys, short = p.town_shopping(self.kit, self.buylist)
                self.short = short
                # room first: a buy into a full pack fails ("You cannot carry that many items": m30 lost its Restore
                # Dexterity twice that way, silently)
                if p.town_make_room(self, buys):
                    self.t = now + 1.0
                    return None
                order = []
                for tier, kind, store, n, cap in sorted(buys, key=lambda b: b[0]):
                    if store not in order:
                        order.append(store)
                self.plan = {st: [(k, n, cap) for _, k, s_, n, cap in buys if s_ == st] for st in order}
                self.queue = order
                self.stage = "buying"
            return None
        if self.stage == "buying":
            if self.queue:
                st = self.queue.pop(0)
                self.sub = Shop(st, buys=self.plan[st])
                self.sub.role = "pilot"
                return None
            # wear what was bought (m37: the Iron Helm the Navigator's buy list got stayed in the pack)
            if p.upgrade_step():
                self.t = now
                return None
            # drink the Restore bought for a drained stat (once each)
            pot = p.restore_potion(self.__dict__.setdefault("quaffed", set()))
            if pot:
                self.quaffed.add(pot["name"])
                p.cmd(f"custom q item={pot['item']}", f"town kit: quaff {pot['name']}", hold=0.8)
                self.done_log.append(f"quaffed {pot['name']}")
                self.t = now + 1.0
                return None
            # leave town fed and fuelled: no food is digested in town (dungeon.c), so eat rations to Fed here,
            # and top the lantern up (the user, 10-25: no oil and one food stack in the pack)
            if p.provision_step(self):
                self.t = now + 1.5
                return None
            # an essential still missing because the shop had none: wait for new stock and look again (the user, 10-28:
            # shops restock every ~30 s -- wait for what's critical). Critical: the supply gate's minimums for the
            # planned depth, and a Restore for a drained STR/DEX/CON (blows, HP); up to RESTOCK_WAITS x 35 s
            gap = p.supply_gate(p.planned_depth(), True)
            gap += [f"Restore {p.STAT_FULL[st]}" for st, (cur, top) in (p.seen_drained or {}).items()
                    if st in p.STAT_FULL and cur < top
                    and not any(f"Restore {p.STAT_FULL[st]}" in i["name"] for i in w.items())
                    and not p.stash_has(f"Restore {p.STAT_FULL[st]}")]
            waits = self.__dict__.get("restock_waits", 0)
            if gap and waits < self.RESTOCK_WAITS and any("in stock" in l for l in self.done_log):
                self.restock_waits = waits + 1
                self.stage = "buy"
                self.sub = Wait(35)
                self.done_log.append(f"still missing {'; '.join(gap)}: waiting 35 s for new stock "
                                     f"({self.restock_waits}/{self.RESTOCK_WAITS})")
                return None
            # recharge an empty useful staff or wand (a Scroll of Recharging from the Alchemist; the user, 10-28)
            tried = self.__dict__.setdefault("recharged", set())
            todo = [d for d in p.recharge_wanted() if d["name"] not in tried]
            dev = todo[0] if todo else None
            if dev:
                sc = p.find_item("Recharging", TV_SCROLL)
                if sc:
                    tried.add(dev["name"])
                    p.cmd(f"custom r item={sc['item']} dir={dev['item']}",
                          f"town kit: recharge {dev['name']} ({p.recharge_fail(dev):.0%} risk)", hold=1.0)
                    self.done_log.append(f"recharged {dev['name']}")
                    self.t = now + 1.0
                    return None
                if not getattr(self, "recharge_bought", False):
                    self.recharge_bought = True
                    self.sub = Shop(5, buys=[("Recharging", len(todo),
                                              round((p.price_of("Recharging", 5) or 250) * 1.5))])
                    return None
            # enchant worn armour back up (disenchantment), while the next point is >= 50% (enchant_plan)
            plan = p.enchant_plan()
            if plan:
                sc = p.find_item("Enchant Armor", TV_SCROLL)
                if sc:
                    it, c = plan[0]
                    p.cmd(f"custom r item={sc['item']} dir={it['item']}", f"town kit: enchant {it['name']} ({c:.0%})",
                          hold=1.0)
                    self.enchanted = self.__dict__.get("enchanted", 0) + 1
                    self.t = now + 1.0
                    return None
                if not getattr(self, "enchant_bought", False):
                    self.enchant_bought = True
                    price = p.price_of("Enchant Armor", 5) or 190
                    spare = w.ind.get("gold", [0])[0] - p.town_reserve()
                    n = min(int(round(p.enchant_scrolls_wanted())), max(0, spare // max(1, int(price * 1.1))),
                            int(p.orders.get("enchant_max", 25)))
                    if n > 0:
                        self.sub = Shop(5, buys=[("Enchant Armor", n, round(price * 1.5))])
                        self.done_log.append(f"Enchant Armor x{n} for {len(plan)} piece(s)")
                        return None
            # last: the stash kinds go to the tavern for the mission (Restore potions, Stone to Mud wands)
            if not getattr(self, "stashed", False) and not p.house_state().get("house") and \
                    any(p.is_stash_item(i["name"]) for i in w.items()):
                self.stashed = True
                self.sub = StashDeposit()
                return None
            # and last of all, the gold into the house: the dungeon has no use for it, its thieves do
            if not getattr(self, "deposited", False) and p.house_state().get("house") and \
                    (w.ind.get("gold", [0])[0] > p.BANK_FLOAT + 500 or any(p.is_stash_item(i["name"])
                                                                         for i in w.items())):
                self.deposited = True
                self.sub = HouseBank("deposit")
                return None
            return self.finish(p)
        return None

    def finish(self, p):
        w = p.w
        want = p.planned_depth()
        gap = p.supply_gate(want, True) if want else []
        short = [f"{n} {k}" for k, n in getattr(self, "short", []) if n > 0]
        head = (f"sold for {self.sold}, bought for {self.bought}, identified {self.identified}; "
                f"gold now {w.ind.get('gold', [0])[0]}" + (f" (+{p.banked()} in the house)" if p.banked() else "")
                + f"; leaving with {p.supply_text()}")
        tail = (f"; supplies for recalling to {want} ft: " + ("OK" if not gap else "MISSING " + "; ".join(gap))) \
            if want else ""
        p.log("town_kit", sold=self.sold, bought=self.bought, identified=self.identified,
              gold=w.ind.get("gold", [0])[0], short=short, gap=gap)
        return ("done", head + tail + ("; not afforded: " + ", ".join(short) if short else "") +
                (" | " + " | ".join(self.done_log) if self.done_log else ""))
