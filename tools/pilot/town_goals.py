"""town_goals -- the town goals (refactor-candidates E1; docs/goals-and-plans.md): Town (back from the wilderness),
TownFarm, Shop, StashDeposit/StashFetch, HouseBank and TownKit (the town visit), with the map helpers they share with
the Pilot (edge_of, town_houses). pilot.py imports them all back (P.TownKit, P.town_houses, ...).
"""
import os
import re
import sys
import time
import types

from common import HERE, TV_SCROLL, TV_LITE, TV_FOOD, flavour_key, kind_key, bare_name, singular, rec_name, \
    world_xy
from world import gnow, waited, light_turns
from mover import direction, MAX_HGT, MAX_WID
from goals import Goal, Wait
if os.path.join(HERE, "..", "observe") not in sys.path:     # (shopmath, as pilot.py loads it)
    sys.path.insert(0, os.path.join(HERE, "..", "observe"))
import shopmath                                  # noqa: E402


# a step of a split tick that didn't end it: go on to the next (Shop.TRADE_STEPS, HouseBank.TICK_STEPS,
# TownKit.KIT_STEPS / BUYING_STEPS, plan.TripPlan.TRIP_STEPS; refactor-candidates E5)
NEXT = object()

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
    night and no goal could walk back). 2.59.0 (the user: "look at our position relative to town on the overworld map
    and head accordingly"; m66: after a hot-swap, inside the house on the tile north of town, it failed "don't know
    which edge leads back" ~130 times): without the trail, the sector's world offset from its level number
    (common.world_xy, the server's world_index inverted) says which edge -- west/east until x is 0, then south/north
    until y is 0 -- recomputed after each crossing; inside the owned house, out by its door first (house.json)."""
    name = "town"

    def __init__(self):
        self.step_t = 0.0

    def leave_house(self, p):
        """Inside the owned house (house.json): to the square inside the door, open it, out through it. True while
        acting."""
        h = p.house_state().get("house") or {}
        w = p.w
        door, inside, outside = (tuple(h[k]) if h.get(k) else None for k in ("door", "step_in", "outside"))
        if not (door and inside and outside) or not waited(self.step_t, 0.8):
            return True
        self.step_t = gnow()
        if w.pos == door:
            p.cmd(f"walk {direction(w.pos, outside)}", "town: out of the house", hold=0.5)
        elif w.pos == inside:
            if w.memory.get(door) == "'":
                p.cmd(f"walk {direction(w.pos, door)}", "town: into the house's doorway", hold=0.5)
            else:
                p.cmd(f"open {direction(w.pos, door)}", "town: open the house's door", hold=0.5)
        else:
            dy, dx = (inside[0] > w.pos[0]) - (inside[0] < w.pos[0]), (inside[1] > w.pos[1]) - (inside[1] < w.pos[1])
            p.cmd(f"walk {direction(w.pos, (w.pos[0] + dy, w.pos[1] + dx))}", "town: to the house's door", hold=0.5)
        return True

    @staticmethod
    def edge_home(depth):
        """The edge of this wilderness sector toward town by its world offset: W/E while x isn't 0, then S/N."""
        xy = world_xy(depth)
        if not xy or xy == (0, 0):
            return None
        x, y = xy
        if x:
            return "W" if x > 0 else "E"
        return "S" if y > 0 else "N"

    def tick(self, p):
        w = p.w
        if w.depth == 0:
            return ("done", "in town")
        if w.in_dungeon:
            return ("failed", "in the dungeon: use goal dive 0 or goal recall")
        if p.in_house():
            return self.leave_house(p) and None
        edge = p.wild_trail[-1] if p.wild_trail else (self.edge_home(w.depth) or edge_of(w.arrive_pos or w.pos))
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
        # (created on the way: refactor-candidates E5 declares them, with the values their reads assumed)
        self.sale_pending = None     # the last sale's record, until its re-listing comes (the scorecard)
        self.quoting = None          # the item a quote is waiting on
        self.sale_ctx = None         # the sale under way: what was known before it
        self.selling_flavour = None  # the unknown flavour being sold (its kind is learnt from the sale)
        self.reentered = 0           # walked back in after our own command closed the store (twice at most)
        self.need_fresh = 0          # when a purchase left a remainder: wait for the listing after it

    # One method per state (refactor-candidates E5): walk to the door, wait for the listing, trade. Each takes the
    # per-call ctx (w) and returns what tick() returns.
    STATES = {"walk": "_walk", "enter": "_enter", "trade": "_trade"}
    # The trade, one step a tick: each returns NEXT to go on, or what tick() returns (the first to act ends it).
    TRADE_STEPS = (
        "_trade_record",     # the last sale's record, once its re-listing is in (the scorecard memo)
        "_trade_quote",      # a quote's answer: the offer, declined
        "_trade_answer",     # a sale's or a purchase's answer
        "_trade_left",       # out of the store: back in if our own command closed it, else thrown out
        "_trade_list",       # the stock listed (list)
        "_trade_sell",       # the next sale or quote
        "_trade_fresh",      # a purchase's remainder: wait for the listing after it
        "_trade_buy",        # the next purchase
        "_trade_leave",      # all done: leave
    )

    def tick(self, p):
        ctx = types.SimpleNamespace(w=p.w)
        w = ctx.w
        if w.depth:
            return ("failed", "not in town")
        state = self.STATES.get(self.state)
        return getattr(self, state)(p, ctx) if state else None

    def _walk(self, p, ctx):
        """walk: to a square beside the door, then into it (the listing: enter)."""
        w = ctx.w
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

    def _enter(self, p, ctx):
        """enter: the listing came (trade), or not in 4 s (walk again)."""
        w = ctx.w
        if w.store and w.store_t >= self.t:
            self.state = "trade"
            return None
        if waited(self.t, 4):
            self.state = "walk"
        return None

    def _trade(self, p, ctx):
        """trade: the store's listing noted, then TRADE_STEPS in order."""
        p.note_store()
        for name in self.TRADE_STEPS:
            r = getattr(self, name)(p, ctx)
            if r is not NEXT:
                return r

    def _trade_record(self, p, ctx):
        """The last sale's record (the Advisor's scorecard memo §5.1), once the next listing shows its re-listing
        price (or 3 s pass); a forced sale's lost value goes on the Navigator's debt."""
        w = ctx.w
        sp = self.sale_pending
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
        return NEXT

    def _trade_quote(self, p, ctx):
        """A quote's answer: the shop's offer (declined), or none in 4 s."""
        w = ctx.w
        if self.pending and self.quoting:
            ts, prompt, _ = w.last_confirm
            m = re.search(r"Accept (\d+) gold", prompt) if ts >= self.pending else None
            if m is None and not waited(self.pending, 4):
                return None
            self.done_log.append(f"quote: {self.quoting}: {m.group(1)} gold (not sold)" if m else
                                 f"quote: {self.quoting}: no offer (the shop doesn't buy it?)")
            self.pending, self.quoting = None, None
            return None
        return NEXT

    def _trade_answer(self, p, ctx):
        """A sale's or a purchase's answer: its message, or 4 s; the scorecard's sale record and a sold flavour's
        kind."""
        w = ctx.w
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
            if ms and self.sale_ctx:
                # the scorecard's sale record: the re-listing comes with the next
                # store listing (the Advisor's scorecard memo §5.1)
                self.sale_ctx.update(sold_as=ms.group(1), received=int(ms.group(2)), t=gnow())
                self.sale_pending = self.sale_ctx
            self.sale_ctx = None
            m = re.match(r"You sold (.+?) for \d+ gold", verdict or "")
            if m and self.selling_flavour:
                p.learn_flavour(self.selling_flavour, kind_key(m.group(1)), "sold in a shop")
                self.selling_flavour = None
            self.pending = None
            w.status_t = 0            # re-read gold before the next purchase
            w.inven_dirty = True
            return None
        return NEXT

    def _trade_left(self, p, ctx):
        """Out of the store: our own non-store command closed it (walk back in, twice at most), else the shopkeeper
        threw us out."""
        w = ctx.w
        if not w.store:
            # Our own non-store command closed it on the server (the client
            # reports that as store_leave with a 'why'): walk back in, twice
            # at most; anything else is the shopkeeper's doing
            if getattr(w, "store_left_why", None) and self.reentered < 2:
                self.reentered = self.reentered + 1
                w.store_left_why = None
                self.state = "walk"
                return None
            return ("failed", "thrown out of the store")
        return NEXT

    def _trade_list(self, p, ctx):
        """list: the stock, into the result."""
        w = ctx.w
        if self.list_stock:
            # (mission 8 guessed names one shop trip at a time)
            self.list_stock = False
            self.done_log.append("stock: " + "; ".join(
                f"{i['name']} {i['price']}" for i in w.store["items"]))
        return NEXT

    def _trade_sell(self, p, ctx):
        """The next sale (or quote): by letter or by name (resolved now), unless the value policy, an unknown flavour
        or a special feeling says no (`!NAME` forces it, on the Navigator's debt)."""
        w = ctx.w
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
        return NEXT

    def _trade_fresh(self, p, ctx):
        """A purchase's remainder at the next price: wait for the listing after the purchase."""
        w = ctx.w
        if self.buys and not waited(self.need_fresh, 3) and \
                w.store_t < self.need_fresh:
            return None       # (a remainder: wait for the listing after the last purchase)
        return NEXT

    def _trade_buy(self, p, ctx):
        """The next purchase: the cheapest match, within the cap and the gold; a stack that runs out leaves a
        remainder."""
        w = ctx.w
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
        return NEXT

    def _trade_leave(self, p, ctx):
        """All done: the last sale's re-listing first, then leave."""
        w = ctx.w
        if self.sale_pending:
            return None       # (the last sale's re-listing first: the sale record)
        p.cmd("leave", "leave store", hold=0.3)
        w.store = None
        return ("done", "; ".join(self.done_log) or "nothing to do")


class StashDeposit(Goal):
    """Leave the stash kinds (Restore potions, Wands of Stone to Mud) in the tavern (8) for the mission (the user,
    2026-10-26: "leave the potions in the tavern during a mission"; the wands were never aimed; recorded in house.json
    `tavern`, refactor-candidates D10). Walk onto the
    entrance; each drop lands on a floor square of the tavern room (drop_near: a shop entrance takes no object).
    Town objects aren't wiped (depth 0 is skipped), but on a live server another player could take them, and a full
    object list compacts objects anywhere. **Dropped from the entrance, a drop can land on the street outside**
    (10-27: the wands went to 27,88 and 28,88 and townsfolk with TAKE_ITEM took them): with a house, HouseBank keeps
    the stash instead, and this goal takes only what the full house leaves (2.50.0: TownKit's overflow step)."""
    name = "stash in the tavern"

    def __init__(self):
        self.t = 0.0
        self.tries = 0
        self.dropped = []
        self.arrive = None           # (square, game time) we reached the target: a floor reading after it counts
        self.pending = None          # (square, record, game time) of a drop not yet seen underfoot (2.50.0)

    def tick(self, p):
        w, now = p.w, gnow()
        ent = p.tavern_entrance()
        if not ent:
            return ("done", "no tavern seen on the town map: nothing stashed")
        tav = p.tavern_state().setdefault("items", {})
        if self.pending:
            # (2.50.0: recorded once the floor underfoot shows it; scattered elsewhere -- an occupied square, as in the
            # house on 11-04 -- it is recorded as somewhere in the room, and StashFetch searches the room anyway)
            q, rec, t0 = self.pending
            ok, name = p.floor_here(t0 + 0.3) if w.pos == q else (True, None)
            if not ok:
                return None
            self.pending = None
            key = f"{q[0]},{q[1]}"
            if not p.same_item(rec["name"], name):
                if any(p.same_item(rec["name"], i["name"]) for i in w.items()):
                    # (the drop didn't happen: counted -- 3 of them, or the server's refusal, give it up this visit)
                    p.drop_failed(rec["name"], t0)
                    return None
                key = next(f"?{n}" for n in range(len(tav) + 1) if f"?{n}" not in tav)
                p.notify("tactic", f"tavern: dropped {rec['name']} at {q[0]},{q[1]} but it isn't there (scattered): "
                                   "recorded as somewhere in the room", news=True)
            tav[key] = rec
            p.stash_commit(rec, "tavern")
            p.house_save()
            self.dropped.append(rec["name"])
            return None
        items = [i for i in w.items() if p.stash_to_drop(i)]
        if not items:
            return ("done", "stashed " + ", ".join(self.dropped) if self.dropped else "nothing to stash")
        # Inside the room, on an empty square (the user, 10-27: the inside is walkable). Dropped from the entrance,
        # which takes no object, the wands landed on the street and townsfolk with TAKE_ITEM took them
        room = next((h for h in town_houses(w.memory, door="8") if h["door"] == tuple(ent)), None)
        used = {tuple(int(v) for v in k.split(",")) for k in p.tavern_state().get("items", {}) if "," in k}
        free = [q for q in (room["inside"] if room else []) if q not in used and q != tuple(ent)
                and w.memory.get(q) == "."]
        if not free:
            return ("failed", "no empty square seen inside the tavern room: not dropping at the door"
                    + (f" (stashed {', '.join(self.dropped)})" if self.dropped else ""))
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
        # (2.50.0: drop only on a square the floor reading shows bare; an item already there is adopted)
        if self.arrive is None or self.arrive[0] != target:
            self.arrive = (target, now)
            return None
        ok, name = p.floor_here(self.arrive[1] + 0.3)
        if not ok:
            return None
        if name:
            tav[f"{target[0]},{target[1]}"] = p.stash_found(name, "tavern")
            p.house_save()
            return None
        it = max(items, key=lambda i: p.iv(i["name"]).value * i["number"])     # (the most valuable first)
        self.t = now
        p.cmd(f"custom d item={it['item']} value={it['number']}", f"stash in the tavern: {it['name']}", hold=0.8)
        self.pending = (target, p.stash_rec(it, "tavern", commit=False), now)
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
        self.arrive = None           # (square, game time) we reached the target: a floor reading after it counts

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
            # (2.50.0: a square of the room walked is read, and its record set right -- a recorded item not there is
            # struck, an item there the record lacks adopted; the pickup reflex takes only the one being fetched)
            q = self.target
            if self.arrive is None or self.arrive[0] != q:
                self.arrive = (q, gnow())
                return None
            ok, name = p.floor_here(self.arrive[1] + 0.3)
            if not ok and gnow() - self.arrive[1] < 3:
                return None
            room = next((h for h in town_houses(w.memory, door="8") if h["door"] == tuple(ent)), None)
            if ok and room and q in room["inside"] and not (name and self.kind in name):
                tav = p.tavern_state().setdefault("items", {})
                key = f"{q[0]},{q[1]}"
                if key in tav and not p.same_item(rec_name(tav[key]), name):
                    p.stash_take("tavern", rec_name(tav[key]), q, lost=True)
                if name and key not in tav:
                    tav[key] = p.stash_found(name, "tavern")
                    p.house_save()
            self.visited.add(q)
            self.target = None
            return None                      # (a tick for the pickup reflex)
        if self.target is None or not p.mover.active:
            cands = [q for q, ch in w.memory.items() if w.dist(q, tuple(ent)) <= 4 and q not in self.visited
                     and ch not in "#%8+'" and not ch.isdigit()]
            if not cands:
                p.fetching = None
                p.stash_take("tavern", self.kind, lost=True)
                return ("failed", f"no {self.kind} left in the tavern")
            # (item glyphs first: '!' potions, '-' wands; 2.50.0: weapons, armour, jewellery, lights for a backup)
            self.target = min(cands, key=lambda q: (w.memory.get(q) not in "!-?|\\/()[]=\"~_{}", w.dist(q)))
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

    def __init__(self, mode, keep=None, house=None, fetch=()):
        self.mode, self.keep, self.house = mode, keep, house
        self.fetch = list(fetch)     # withdraw: stored items to bring out by name (2.50.0: stash_fetch_list, `house
        #                              withdraw ITEM`), after the Restore a drained stat wants
        self.name = {"buy": "buy a house", "deposit": "bank gold in the house",
                     "withdraw": "take gold from the house"}[mode]
        self.step, self.t, self.tries, self.price = "go", 0.0, 0, None
        self.gold0 = None
        # (created on the way: refactor-candidates E5 declares them, with the values their reads assumed)
        self.full_told = False       # item_step: told once that the house had no free square
        self.picks = 0               # item_step: pick-ups tried on a stash square
        self.fetch_at = None         # item_step: (kind, square, count carried before) of the stash item being fetched,
        #                              struck once the pack holds one more
        self.last_step = None        # the step the tries count for
        self.seen_level = None       # the level last seen (a new one stops the walk: m56)
        self.items_done = False      # inside: the stash moved (item_step)
        # (2.50.0, the live check of 11-04: the record and the floor disagreed -- a second Restore Charisma on a square
        # the record called free; the Scimitar scattered from it, and `,` there took the potion. Reconcile first)
        self.seen = {}               # item_step: interior square -> the item read there (None: bare floor)
        self.reconciled = False      # item_step: every interior square but the gold's read and the record rebuilt
        self.arrive = None           # item_step: (square, game time) we reached it (a floor reading after counts)
        self.pending = {}            # item_step: square -> the record of an item dropped there, not yet seen on it
        self.rechecks = 0            # item_step: re-reconciles after a floor that didn't match (2 at most)
        self.pick_snap = None        # item_step: (square, kind, pack names) before a pick-up (a wrong pick goes back)

    def read_square(self, p, q):
        """At q: (True, the item there or None) once a floor reading taken after we arrived; (False, None) before."""
        if self.arrive is None or self.arrive[0] != q:
            self.arrive = (q, gnow())
            return False, None
        return p.floor_here(self.arrive[1] + 0.3)

    def rebuild(self, p, slots):
        """The house's `items` from what the reconcile saw: a recorded item not on its square is struck (stash_take,
        lost); an item there that the record lacks is adopted (stash_found) -- or, dropped by us and scattered, its
        pending record moves there (committed)."""
        for q, name in sorted(self.seen.items()):
            key = f"{q[0]},{q[1]}"
            rec = slots.get(key)
            if rec is not None and p.same_item(rec_name(rec), name):
                continue
            if rec is not None:
                p.stash_take("house", rec_name(rec), q, lost=True)
            if name:
                pend = next((k for k, r in self.pending.items() if p.same_item(rec_name(r), name)), None)
                if pend is not None:
                    slots[key] = self.pending.pop(pend)
                    p.stash_commit(slots[key], "house")
                else:
                    slots[key] = p.stash_found(name, "house")
        for q, rec in self.pending.items():          # (dropped, not seen in the house: said, not recorded)
            if not any(p.same_item(rec_name(rec), i["name"]) for i in p.w.items()):
                p.notify("tactic", f"house: dropped {rec_name(rec)} at {q[0]},{q[1]} but it wasn't seen on any "
                                   "square inside -- check the house", news=True)
        self.pending = {}
        p.house_save()

    def item_step(self, p, h, inside):
        """Inside, door closed: the stash (the user, 10-27: "move the stash into the wilderness house" -- at 18:10 a
        town monster took a Wand of Stone to Mud off the tavern floor). One stack a square on the interior squares
        other than the gold's; house.json `items` maps square -> record. 2.50.0: first the **reconcile** -- each of
        those squares is walked and its floor read, and the record rebuilt from what lies there (rebuild). A deposit
        drops the stash items carried, the most valuable first, only on a square read empty, and records it once the
        floor shows it there (else re-reconciles to find where it went; what doesn't fit goes to the tavern room,
        TownKit's overflow); a withdraw fetches the kind a drained stat wants (stash_wanted), then the items named
        in `fetch`, pressing `,` only when the floor underfoot names the item (else re-reconciles), each struck off
        the record once the pack holds one more; a wrong item picked up is dropped back. Then back to the gold's
        square. True while acting."""
        w = p.w
        st = p.house_state()
        slots = st.setdefault("items", {})
        y1, x1, y2, x2 = h["box"]
        interior = [(y, x) for y in range(y1 + 1, y2) for x in range(x1 + 1, x2)]
        others = [q for q in interior if q != inside]

        def walk_to(q):
            dy, dx = (q[0] > w.pos[0]) - (q[0] < w.pos[0]), (q[1] > w.pos[1]) - (q[1] < w.pos[1])
            p.cmd(f"walk {direction(w.pos, (w.pos[0] + dy, w.pos[1] + dx))}", f"house: to {q[0]},{q[1]}", hold=0.6)
            return True

        def carried(kind):
            return sum(i["number"] for i in w.items() if kind in i["name"])

        def recheck():
            self.reconciled, self.seen, self.arrive = False, {}, None
            self.rechecks += 1
            return True
        # the reconcile: read every square, then rebuild the record from the floor
        if not self.reconciled:
            todo = [q for q in others if q not in self.seen]
            if todo:
                q = min(todo, key=lambda q: (w.dist(q), q))
                if w.pos != q:
                    return walk_to(q)
                ok, name = self.read_square(p, q)
                if ok:
                    self.seen[q] = name
                return True
            self.reconciled = True
            self.rebuild(p, slots)
        if self.mode == "deposit":
            # a drop waiting to be seen underfoot
            for q, rec in list(self.pending.items()):
                if w.pos != q:
                    return walk_to(q)
                ok, name = self.read_square(p, q)
                if not ok:
                    return True
                refused = any(ts >= self.arrive[1] - 0.5 and "can not drop this here" in t.lower()
                              for ts, t in w.messages)
                if p.same_item(rec_name(rec), name):
                    slots[f"{q[0]},{q[1]}"] = self.pending.pop(q)
                    p.stash_commit(slots[f"{q[0]},{q[1]}"], "house")
                    self.seen[q] = name
                    p.house_save()
                elif not refused and self.rechecks < 2:
                    return recheck()             # (it went elsewhere: the next reconcile finds it)
                else:
                    self.pending.pop(q)
                    # (2.53.0: refused by the server, or still not seen: a failed drop -- 3 of them, or a refusal,
                    # and the item is kept in the pack this visit; m63's Phial looped ~600 times)
                    if refused or any(p.same_item(rec_name(rec), i["name"]) for i in w.items()):
                        p.drop_failed(rec_name(rec), self.arrive[1])
            items = [i for i in w.items() if p.stash_to_drop(i)]
            it = max(items, key=lambda i: p.iv(i["name"]).value * i["number"]) if items else None
            free = [q for q in others if self.seen.get(q) is None and f"{q[0]},{q[1]}" not in slots
                    and q not in self.pending]
            if it and free and not self.pending:
                q = max(free, key=lambda q: (w.dist(q, inside), q))     # (the far squares first)
                if w.pos != q:
                    return walk_to(q)
                p.cmd(f"custom d item={it['item']} value={it['number']}", f"house: stash {it['name']}", hold=0.8)
                self.pending[q] = p.stash_rec(it, "house", commit=False)   # (recorded once seen underfoot)
                self.arrive = (q, gnow())
                p.review_state()["items"].pop(it["name"], None)    # (stored: not waiting for a review any more)
                return True
            if it and not self.pending and not getattr(self, "full_told", False):
                self.full_told = True
                p.notify("tactic", f"house: no free square for {it['name']} (one stack a square): the tavern room "
                                   "takes it (plan town), else it stays in the pack", news=True)
        if self.mode == "withdraw":
            got = self.fetch_at
            if got and carried(got[0]) > got[2]:
                # picked up: off the house's record at once (stash_wanted names only a kind the pack lacks, so the
                # strike that waited for "already in the pack" never ran, and the record kept it until a later
                # withdraw spent 4 pick-ups on the empty square -- refactor-candidates E5)
                self.fetch_at = None
                p.fetching = None
                self.pick_snap = None
                p.stash_take("house", got[0], got[1])
                self.seen[got[1]] = None
                if got[0] in self.fetch:
                    self.fetch.remove(got[0])
            snap = self.pick_snap
            if snap and w.pos == snap[0]:
                # a pick-up that took something else: drop it back where it lay
                new = [i for i in w.items() if i["name"] not in snap[2] and snap[1] not in i["name"]]
                if new:
                    self.pick_snap = None
                    p.cmd(f"custom d item={new[0]['item']} value={new[0]['number']}",
                          f"house: put back {new[0]['name']} (not the {snap[1]})", hold=0.8)
                    return recheck()
            kind = p.stash_wanted("house")
            key = next((k for k, n in slots.items() if kind and kind in rec_name(n)), None)
            if not key:
                # (2.50.0: the named items -- a backup to wear or to sell, `house withdraw ITEM`)
                for name in list(self.fetch):
                    key = next((k for k, n in slots.items() if rec_name(n) == name), None) or \
                        next((k for k, n in slots.items() if name in rec_name(n)), None)
                    if key:
                        kind = name
                        break
                    self.fetch.remove(name)          # (not in the house: nothing to fetch)
            if key:
                q = tuple(int(v) for v in key.split(","))
                if not self.fetch_at or self.fetch_at[:2] != (kind, q):
                    self.fetch_at = (kind, q, carried(kind))
                    self.picks = 0
                if w.pos != q:
                    return walk_to(q)
                ok, name = self.read_square(p, q)
                if not ok:
                    return True
                if not name or kind not in name:
                    # (the floor holds something else, or nothing: never press `,` -- read the house again)
                    if self.rechecks < 2:
                        return recheck()
                    p.stash_take("house", rec_name(slots[key]), q, lost=True)
                    self.fetch_at = None
                    if kind in self.fetch:
                        self.fetch.remove(kind)
                    return True
                self.picks = getattr(self, "picks", 0) + 1
                if self.picks > 4:
                    p.stash_take("house", rec_name(slots[key]), q, lost=True)     # (not there after all)
                    self.fetch_at = None
                    if kind in self.fetch:
                        self.fetch.remove(kind)
                    return True
                p.fetching = kind
                self.pick_snap = (q, kind, [i["name"] for i in w.items()])
                p.cmd("custom ,", f"house: pick up the {kind}", hold=0.8)
                self.arrive = (q, gnow())
                return True
        if w.pos != inside:
            return walk_to(inside)
        p.fetching = None
        return False

    # One method per step (refactor-candidates E5), in this order; each takes the per-call ctx (w, now; the values the
    # steps share, set by the step that computes them) and returns NEXT to go on, or what tick() returns.
    TICK_STEPS = (
        "_bank_house",       # the house on record and where we are (ctx.h, hd, door, inside, outside); 1 s a step
        "_bank_cross",       # a wilderness house: off the town's edge to its tile (ctx.cross)
        "_bank_back",        # step back: from the house's tile into town
        "_bank_home",        # step home: back in town, done
        "_bank_turn",        # (not a step: ctx.gold, ctx.said -- the messages since the last step -- the tries)
        "_bank_door",        # the step at the house (STEPS)
    )
    # the steps at the house, one method each (_bank_door dispatches on self.step)
    STEPS = {"go": "_step_go", "open": "_step_open", "bought": "_step_bought", "in1": "_step_in1",
             "in2": "_step_in2", "inside": "_step_inside", "dropped": "_step_dropped", "out0": "_step_out0",
             "out1": "_step_out1", "closed": "_step_closed"}

    def tick(self, p):
        ctx = types.SimpleNamespace(w=p.w, now=gnow())
        for name in self.TICK_STEPS:
            r = getattr(self, name)(p, ctx)
            if r is not NEXT:
                return r

    def _bank_house(self, p, ctx):
        """The house on record (or the one being bought), and that we're in town or on its tile; one step a second,
        with nothing busy and the pack read."""
        w, now = ctx.w, ctx.now
        h = ctx.h = self.house or p.house_state().get("house")
        if not h:
            return ("failed", "no house owned (`house buy`)")
        hd = ctx.hd = int(h.get("depth", 0))
        if w.in_dungeon or (w.depth not in (0, hd)):
            return ("failed", "the house is in town or the tile beside it: go to town first")
        ctx.door, ctx.inside, ctx.outside = tuple(h["door"]), tuple(h["step_in"]), tuple(h["outside"])
        if not waited(self.t, 1.0) or now < p.busy_until or w.inven_dirty:
            return None
        return NEXT

    def _bank_cross(self, p, ctx):
        """A wilderness house: from town, walk off the town's edge where we did when it was found (closed, and back in
        town: home)."""
        w, now, h, hd = ctx.w, ctx.now, ctx.h, ctx.hd
        # a wilderness house: walk off the town's edge where we did when it was found, and back the same way
        cross = ctx.cross = h.get("cross")
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
        return NEXT

    def _bank_back(self, p, ctx):
        """back: from the house's tile, the same way back into town."""
        w, now, cross = ctx.w, ctx.now, ctx.cross
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
        return NEXT

    def _bank_home(self, p, ctx):
        """home: back in town, done."""
        w = ctx.w
        if self.step == "home":
            st = p.house_state()
            return ("done", f"{self.name}: {st.get('banked', 0)} gold in the house, {w.ind.get('gold', [0])[0]} carried")
        return NEXT

    def _bank_turn(self, p, ctx):
        """(Not a step: what the steps at the house share.) ctx.gold, ctx.said (the messages since the last step); a
        new step's tries start at 0; a new level stops the walk."""
        w, now = ctx.w, ctx.now
        ctx.gold = w.ind.get("gold", [0])[0]
        ctx.said = [t for ts, t in w.messages if ts >= self.t - 1.0]
        self.t = now
        if self.step != self.last_step:
            self.last_step, self.tries = self.step, 0
        # (m56: from town, the walk to the edge was still running after the crossing, toward the town square's
        # coordinates on the new tile; it ran through the house's outside square, the bank took that for arrival and
        # opened the door from 10 squares off -- "the door didn't open". A new level stops the walk)
        if w.level_t != self.seen_level:
            self.seen_level = w.level_t
            p.mover.stop()
        return NEXT

    def _bank_door(self, p, ctx):
        """The step at the house (STEPS), or a failure for a step that isn't one."""
        step = self.STEPS.get(self.step)
        if step:
            return getattr(self, step)(p, ctx)
        return ("failed", f"unknown step {self.step}")

    def _step_go(self, p, ctx):
        """go: to the open square outside the door."""
        w, now, door, outside, gold = ctx.w, ctx.now, ctx.door, ctx.outside, ctx.gold
        if w.pos == outside:
            p.mover.stop()
            self.step = "open"
            self.gold_out, self.banked0, self.gold_picks = gold, p.banked(), 0
            return None
        if not p.mover.active:
            self.tries += 1
            if self.tries > 3 or not p.mover.go([outside]):
                return ("failed", f"couldn't reach the house door at {door[0]},{door[1]}")
        p.mover.tick()
        self.t = now - 1.0
        return None

    def _step_open(self, p, ctx):
        """open: open the door (buy: its price first, then buy it if we can spare it)."""
        w, door, gold, said = ctx.w, ctx.door, ctx.gold, ctx.said
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

    def _step_bought(self, p, ctx):
        """bought: the gold gone -- the house on record; then in, to deposit (the door stays open)."""
        h, door, gold, said = ctx.h, ctx.door, ctx.gold, ctx.said
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

    def _step_in1(self, p, ctx):
        """in1: into the doorway (opening the door again every third try)."""
        w, door, said = ctx.w, ctx.door, ctx.said
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

    def _step_in2(self, p, ctx):
        """in2: onto the square inside (the bank's pile is picked up), then close the door behind us."""
        w, door, inside, gold = ctx.w, ctx.door, ctx.inside, ctx.gold
        if w.pos == inside:
            self.gold0 = gold
            self.inside_t = gnow()       # (2.52.0: the floor reading of the gold's square must come after this)
            p.cmd(f"custom c dir={direction(inside, door)}", "house: close the door behind us", hold=0.8)
            self.step = "inside"
            return None
        p.cmd(f"walk {direction(w.pos, inside)}", "house: step inside (the pile is picked up)", hold=0.8)
        return None

    def _step_inside(self, p, ctx):
        """inside: the pile picked up (else nothing is dropped); the stash (item_step); a deposit drops all but
        `keep`."""
        h, inside, gold = ctx.h, ctx.inside, ctx.gold
        st = p.house_state()
        # (stepping in takes the pile. If it didn't, a second drop would find no free square and vanish)
        if self.banked0 and gold < self.gold_out + 0.9 * self.banked0:
            # (2.52.0, m63: the record can be stale -- the bank's pile was taken outside HouseBank, by the idle gold
            # fetch, and the record still said banked, so every deposit refused and 25k went to the dungeon. Read the
            # gold's square: bare -> the record was stale, bank from the purse; gold still there -> pick it up first;
            # anything else, or no reading in 4 s -> refuse as before: a drop with no free square would vanish)
            read, name = p.floor_here(getattr(self, "inside_t", 0) + 0.3)
            if not read and not waited(getattr(self, "inside_t", 0), 4):
                return None
            if read and name is None:
                p.notify("tactic", f"house: the bank's {self.banked0} gold isn't on its square -- the record was stale "
                                   f"(carrying {gold}); banking from the purse", news=True)
                p.log("bank_stale", banked=self.banked0, purse=gold)
                self.banked0 = 0
            elif read and name and "gold" in name.lower() and getattr(self, "gold_picks", 0) < 3:
                self.gold_picks = getattr(self, "gold_picks", 0) + 1
                p.cmd("custom ,", "house: pick up the bank's pile", hold=1.0)
                return None
            else:
                p.notify("tactic", f"house: the bank's {self.banked0} gold wasn't picked up on the way in (carrying "
                                   f"{gold}; underfoot: {name if read else 'not read'}); nothing dropped -- check the "
                                   "house square", news=True)
                self.mode = "withdraw"
                self.step = "out0"
                return None
        st["banked"] = 0
        p.house_save()
        if not self.items_done:
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

    def _step_dropped(self, p, ctx):
        """dropped: the drop seen (its message, or the gold gone): the bank on record."""
        gold, said = ctx.gold, ctx.said
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

    def _step_out0(self, p, ctx):
        """out0: open the door to leave."""
        w, door = ctx.w, ctx.door
        p.cmd(f"open {direction(w.pos, door)}", "house: open the door to leave", hold=0.8)
        self.step = "out1"
        return None

    def _step_out1(self, p, ctx):
        """out1: out through the doorway, then close the door."""
        w, door, inside, outside, said = ctx.w, ctx.door, ctx.inside, ctx.outside, ctx.said
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

    def _step_closed(self, p, ctx):
        """closed: on record; a wilderness house: back to town, else done."""
        hd, gold = ctx.hd, ctx.gold
        st = p.house_state()
        p.log("bank", banked=st.get("banked", 0), purse=gold)
        if hd:
            self.step = "back"
            return None
        return ("done", f"{self.name}: {st.get('banked', 0)} gold in the house, {gold} carried")


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
        # (created on the way: refactor-candidates E5 declares them, with the values their reads assumed)
        self.withdrawn = False       # upgrade: the bank's gold taken (HouseBank withdraw)
        self.fetched = False         # upgrade: the Restore a drained stat wants fetched from the tavern
        self.last_sell = None        # the store of the last sale (one of an unknown stack taught: sell the rest)
        self.id_bought = False       # identify: Identify scrolls bought
        self.farmed = False          # buy: townfarmed for the Word of Recall (or decided not to, at night)
        self.short = []              # buy: what the gold doesn't buy [(kind, n)] (finish reports it)
        self.quaffed = set()         # buying: the Restore potions drunk
        self.restock_waits = 0       # buying: waits for new stock (RESTOCK_WAITS at most)
        self.fallback_bought = False  # buying: the fallbacks for a kit kind still short looked for (2.48.0: Boldness)
        self.t0 = gnow()             # (when the visit began: a store listing seen since is this visit's stock)
        self.recharged = set()       # buying: the devices recharged
        self.recharge_bought = False  # buying: Scrolls of Recharging bought
        self.enchanted = 0           # buying: Scrolls of Enchant Armor / Weapon read
        self.enchant_bought = False  # buying: Scrolls of Enchant Armor / Weapon bought (one visit)
        self.stashed = False         # buying: the stash taken to the tavern (no house)
        self.deposited = False       # buying: the gold (and the stash) into the house
        self.overflowed = False      # buying: what the full house left taken to the tavern room (2.50.0)
        self.fetch_tried = set()     # upgrade: stored items fetched from the tavern (2.50.0: backups to wear or sell)
        self.full_told = set()       # buying: the stash items told "no room" (stash_full) this visit (2.50.0)

    # One method per step (refactor-candidates E5), in this order: the visit's stages run in sequence -- a stage that
    # finishes sets the next and the next step runs in the same tick. Each takes the per-call ctx (w, now) and returns
    # NEXT to go on, or what tick() returns. docs/goals-and-plans.md, the town visit.
    KIT_STEPS = (
        "_kit_where",            # in town (or on the house's tile, banking)
        "_kit_count",            # the first tick: the visit counted, the supplies told
        "_kit_sub",              # a sub-goal running (a Shop, HouseBank, StashFetch, TownFarm or Wait): its result
        "_kit_settle",           # 1 s a step, nothing busy, the pack read
        "_kit_withdraw",         # upgrade: the bank's gold (a stash Restore, backups to wear or sell) out of the house
        "_kit_fetch",            # upgrade: a Restore (a backup to wear or sell) waiting in the tavern
        "_kit_upgrade",          # upgrade: wear/wield what the policy prefers; then sell
        "_kit_upgrade_again",    # upgrade again (after Identify); then sell again
        "_kit_sell",             # sell / sell again: one shop a tick; then identify / buy
        "_kit_identify",         # identify: read Identify, or buy it; then upgrade again / buy
        "_kit_buy",              # buy: townfarm when broke; the shopping list, room in the pack; then buying
        "_kit_buying",           # buying: the shops, then BUYING_STEPS, then finish
    )
    # the buying stage, after the shops: one method per step, in this order (the last: finish)
    BUYING_STEPS = (
        "_buying_shop",          # the next shop of the plan
        "_buying_upgrade",       # wear what was bought
        "_buying_quaff",         # drink a Restore bought for a drained stat
        "_buying_provision",     # fed and fuelled (provision_step)
        "_buying_restock",       # an essential out of stock: wait 35 s for new stock (RESTOCK_WAITS)
        "_buying_fallback",      # a kit kind still short (Heroism): its fallback for the shortfall (Boldness)
        "_buying_recharge",      # recharge an empty useful staff or wand (or buy the scroll)
        "_buying_enchant",       # enchant worn armour and the wielded weapon back up (or buy the scrolls)
        "_buying_stash",         # no house: the stash kinds to the tavern
        "_buying_deposit",       # a house: the gold (and the stash) into it
        "_buying_overflow",      # the house full: the stash it left to the tavern room (2.50.0)
        "_buying_stash_full",    # no room anywhere: kept in the pack, the Navigator told to `ask` (2.50.0)
    )

    def tick(self, p):
        ctx = types.SimpleNamespace(w=p.w, now=gnow())
        for name in self.KIT_STEPS:
            r = getattr(self, name)(p, ctx)
            if r is not NEXT:
                return r
        return None

    def _kit_where(self, p, ctx):
        """Plan town is for the town (the house's tile too, while banking there)."""
        w = ctx.w
        # (m56: the house step walks to the wilderness tile, depth -1, and this check killed the visit there -- the
        # Opus Navigator's first `ask`)
        if w.in_dungeon or (w.depth and not isinstance(self.sub, HouseBank)):
            return ("failed", "plan town is for the town")
        return NEXT

    def _kit_count(self, p, ctx):
        """The first tick: the visit counted (the review queue) and the supplies told."""
        if not self.counted:
            self.counted = True
            p.drop_fails, p.drop_told = {}, set()     # (2.53.0: a new visit tries the stash drops again)
            p.review_state()["town_visits"] += 1
            p.review_save()
            p.notify("tactic", f"plan town: came back with {p.supply_text()} (reserves counted)", news=True)
        return NEXT

    def _kit_sub(self, p, ctx):
        """A sub-goal running: tick it; when it ends, its result into the log (sold, bought)."""
        now = ctx.now
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
        return NEXT

    def _kit_settle(self, p, ctx):
        """The pack and gold settle after each step: 1 s, nothing busy, the pack read."""
        w, now = ctx.w, ctx.now
        if not waited(self.t, 1.0) or now < p.busy_until or w.inven_dirty or p.pending_use:
            return None             # (the pack and gold settle after each step)
        return NEXT

    def _kit_withdraw(self, p, ctx):
        """upgrade: the bank first (HouseBank withdraw, and the stash kind a drained stat wants; 2.50.0: a stored
        backup the gear policy would wear, and one a carried backup outclasses -- stash_fetch_list)."""
        # the bank first: the shopping needs the gold (HouseBank)
        if self.stage == "upgrade" and not self.withdrawn:
            self.withdrawn = True
            if p.house_state().get("house"):
                fetch = p.stash_fetch_list("house")
                if p.banked() or p.stash_wanted("house") or fetch:
                    self.sub = HouseBank("withdraw", fetch=[n for n, _ in fetch])
                    self.done_log += [f"from the house: {n} ({why})" for n, why in fetch]
                    return None
        return NEXT

    def _kit_fetch(self, p, ctx):
        """upgrade: a drained stat's Restore waiting in the tavern (StashFetch)."""
        # a drained stat whose Restore waits in the tavern: fetch it first (bought only if it isn't there)
        if self.stage == "upgrade" and not self.fetched:
            kind = p.stash_wanted("tavern")              # (the house's: fetched above)
            if kind:
                self.sub = StashFetch(kind)
                return None
            # (2.50.0: a backup in the tavern room to wear or to sell -- stash_fetch_list; each tried once)
            for name, why in p.stash_fetch_list("tavern"):
                if name not in self.fetch_tried:
                    self.fetch_tried.add(name)
                    self.sub = StashFetch(name)
                    self.done_log.append(f"from the tavern: {name} ({why})")
                    return None
            self.fetched = True
        return NEXT

    def _kit_upgrade(self, p, ctx):
        """upgrade: wear/wield what the policy prefers before anything is sold; then sell."""
        now = ctx.now
        if self.stage == "upgrade":
            # (2.55.0: a stat-gain potion carried is drunk first)
            if p.quaff_gain("plan town"):
                self.t = now + 1.0
                return None
            # (2.50.0: the last finds of the mission marked with its label before anything is stored)
            if p.inscribe_finds():
                self.t = now
                return None
            # wear/wield what the policy prefers before anything is sold
            if p.upgrade_step():
                self.t = now
                return None
            self.stage, self.queue = "sell", p.town_sell_stores()
        return NEXT

    def _kit_upgrade_again(self, p, ctx):
        """upgrade again: what Identify revealed may be worth wearing; then sell again."""
        now = ctx.now
        if self.stage == "upgrade again":
            # what Identify revealed may be worth wearing (m26 identified a Ring of Protection [+12] and sold it
            # with a ring slot empty)
            if p.upgrade_step():
                self.t = now
                return None
            self.stage = "sell again"
        return NEXT

    def _kit_sell(self, p, ctx):
        """sell / sell again: a Shop for the next store that buys something (one of an unknown stack sold: the rest at
        the same shop); then identify (sell) or buy (sell again)."""
        if self.stage in ("sell", "sell again"):
            last = self.last_sell
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
        return NEXT

    def _kit_identify(self, p, ctx):
        """identify: read Identify on the unknowns worth it, or buy the scrolls (within the gold the essentials
        leave); then upgrade again (something identified) or buy."""
        w, now = ctx.w, ctx.now
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
            if n > 0 and not self.id_bought:
                self.id_bought = True
                self.sub = Shop(5, buys=[("Identify", n, round(p.price_of("Identify", 5) * 1.5))])
                self.sub.role = "pilot"
                return None
            self.stage = "upgrade again" if self.identified else "buy"
            self.queue = p.town_sell_stores() if self.identified else []
            return None
        return NEXT

    def _kit_buy(self, p, ctx):
        """buy: short of a Word of Recall and its gold, townfarm by day; then the shopping list by priority, room in
        the pack first, one Shop per store (buying)."""
        w, now = ctx.w, ctx.now
        if self.stage == "buy":
            # Short of a Word of Recall and the gold for it, by day: townfarm the difference first (the user,
            # 2026-10-24: m27 ended broke; townfarm made ~120 gold a minute by day in m14, little at night)
            if not self.queue and p.broke_for_recall() and not self.farmed:
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
        return NEXT

    def _kit_buying(self, p, ctx):
        """buying: the plan's shops one by one, then BUYING_STEPS in order; when none acts, finish."""
        if self.stage == "buying":
            for name in self.BUYING_STEPS:
                r = getattr(self, name)(p, ctx)
                if r is not NEXT:
                    return r
            return self.finish(p)
        return NEXT

    def _buying_shop(self, p, ctx):
        """The next store of the plan (a Shop with its buys)."""
        if self.queue:
            st = self.queue.pop(0)
            self.sub = Shop(st, buys=self.plan[st])
            self.sub.role = "pilot"
            return None
        return NEXT

    def _buying_upgrade(self, p, ctx):
        """Wear what was bought (m37: the Iron Helm the Navigator's buy list got stayed in the pack)."""
        now = ctx.now
        # wear what was bought (m37: the Iron Helm the Navigator's buy list got stayed in the pack)
        if p.upgrade_step():
            self.t = now
            return None
        return NEXT

    def _buying_quaff(self, p, ctx):
        """Drink the Restore bought for a drained stat (once each); 2.50.0: or eat the restore mushroom carried that
        covers it (restore_item: the cheapest; town_needs bought no potion for it)."""
        now = ctx.now
        # drink the Restore bought for a drained stat (once each)
        it = p.restore_item(self.quaffed)
        if it:
            food = it["tval"] == TV_FOOD
            self.quaffed.add(it["name"])
            p.cmd(f"custom {'E' if food else 'q'} item={it['item']}",
                  f"town kit: {'eat' if food else 'quaff'} {it['name']}", hold=0.8)
            self.done_log.append(f"{'ate' if food else 'quaffed'} {it['name']}")
            self.t = now + 1.0
            return None
        return NEXT

    def _buying_provision(self, p, ctx):
        """Leave town fed and fuelled (provision_step)."""
        now = ctx.now
        # leave town fed and fuelled: no food is digested in town (dungeon.c), so eat rations to Fed here,
        # and top the lantern up (the user, 10-25: no oil and one food stack in the pack)
        if p.provision_step(self):
            self.t = now + 1.5
            return None
        return NEXT

    def _buying_restock(self, p, ctx):
        """An essential still missing because the shop had none: wait 35 s for new stock and look again
        (RESTOCK_WAITS)."""
        w = ctx.w
        # an essential still missing because the shop had none: wait for new stock and look again (the user, 10-28:
        # shops restock every ~30 s -- wait for what's critical). Critical: the supply gate's minimums for the
        # planned depth, and a Restore for a drained STR/DEX/CON (blows, HP); up to RESTOCK_WAITS x 35 s
        gap = p.supply_gate(p.planned_depth(), True)
        gap += [f"Restore {p.STAT_FULL[st]}" for st, (cur, top) in (p.seen_drained or {}).items()
                if st in p.STAT_FULL and cur < top
                and not any(f"Restore {p.STAT_FULL[st]}" in i["name"] for i in w.items())
                and not p.stash_has(f"Restore {p.STAT_FULL[st]}") and not p.restore_for(st)]
        waits = self.restock_waits
        # (an essential the shops were out of: not a fallback the Temple was out of, 2.48.0)
        out = [re.sub("|".join(f"no {fb} in stock" for fb in p.FALLBACKS), "", ln) for ln in self.done_log]
        if gap and waits < self.RESTOCK_WAITS and any("in stock" in ln for ln in out):
            self.restock_waits = waits + 1
            self.stage = "buy"
            self.sub = Wait(35)
            self.done_log.append(f"still missing {'; '.join(gap)}: waiting 35 s for new stock "
                                 f"({self.restock_waits}/{self.RESTOCK_WAITS})")
            return None
        return NEXT

    def _buying_fallback(self, p, ctx):
        """A kit kind still short of the kit's target after the shops and the restock waits (Heroism: none in stock,
        over the cap, or not the gold): its fallback for the shortfall (Boldness, at the Temple), once, within the gold
        the essentials leave (fallback_buys; 2.48.0, the user: a weaker substitute is bought only while the better kit
        item is short)."""
        w = ctx.w
        if not self.fallback_bought:
            self.fallback_bought = True
            buys = p.fallback_buys(w.ind.get("gold", [0])[0] - p.town_reserve(), since=self.t0)
            if buys:
                st = buys[0][1]
                self.sub = Shop(st, buys=[(kind, n, cap) for kind, s_, n, cap in buys if s_ == st])
                self.sub.role = "pilot"      # (as the kit's other Shops; a buy-only visit reads no role)
                self.done_log.append("; ".join(f"{p.FALLBACKS[kind]} short ({p.kit_count(p.FALLBACKS[kind])}/"
                                               f"{p.kit_target(p.FALLBACKS[kind])}): {n} {kind} for it"
                                               for kind, s_, n, cap in buys if s_ == st))
                return None
        return NEXT

    def _buying_recharge(self, p, ctx):
        """Recharge an empty useful staff or wand, or buy the Scroll of Recharging."""
        now = ctx.now
        # recharge an empty useful staff or wand (a Scroll of Recharging from the Alchemist; the user, 10-28)
        tried = self.recharged
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
            if not self.recharge_bought:
                self.recharge_bought = True
                self.sub = Shop(5, buys=[("Recharging", len(todo),
                                          round((p.price_of("Recharging", 5) or 250) * 1.5))])
                self.sub.role = "pilot"          # (as the kit's other Shops; a buy-only visit reads no role)
                return None
        return NEXT

    def _buying_enchant(self, p, ctx):
        """Enchant worn armour (enchant_plan) and the wielded weapon's to-dam and to-hit (weapon_enchant_plan, 2.46.0)
        back up while the next point is >= 50%, one read a tick; or buy the scrolls, once (enchant_buys: one Alchemist
        visit, `order enchant_max` for them all)."""
        w, now = ctx.w, ctx.now
        # enchant worn armour back up (disenchantment), while the next point is >= 50% (enchant_plan)
        plan = p.enchant_plan()
        if plan:
            sc = p.find_item("Enchant Armor", TV_SCROLL)
            if sc:
                it, c = plan[0]
                p.cmd(f"custom r item={sc['item']} dir={it['item']}", f"town kit: enchant {it['name']} ({c:.0%})",
                      hold=1.0)
                self.enchanted = self.enchanted + 1
                self.t = now + 1.0
                return None
        # the wielded weapon the same way: the scroll read with the weapon as its item (dir=, as the armour's)
        wplan = p.weapon_enchant_plan()
        for it, kind, c in wplan:
            sc = p.find_item(kind, TV_SCROLL)
            if sc:
                p.cmd(f"custom r item={sc['item']} dir={it['item']}",
                      f"town kit: enchant {it['name']} {kind.split()[-1].lower()} ({c:.0%})", hold=1.0)
                self.enchanted = self.enchanted + 1
                self.t = now + 1.0
                return None
        if (plan or wplan) and not self.enchant_bought:
            self.enchant_bought = True
            buys = p.enchant_buys(w.ind.get("gold", [0])[0] - p.town_reserve())
            if buys:
                self.sub = Shop(5, buys=[(kind, n, round(price * 1.5)) for kind, n, price in buys])
                self.sub.role = "pilot"      # (as the kit's other Shops; a buy-only visit reads no role)
                arm = [f"Enchant Armor x{n} for {len(plan)} piece(s)" for kind, n, _ in buys if kind == "Enchant Armor"]
                wpn = [f"{kind} x{n}" for kind, n, _ in buys if kind != "Enchant Armor"]
                self.done_log.append("; ".join(arm + ([", ".join(wpn) + f" for {wplan[0][0]['name']}"] if wpn else [])))
                return None
        return NEXT

    def _buying_stash(self, p, ctx):
        """No house: the stash kinds go to the tavern for the mission (StashDeposit)."""
        w = ctx.w
        # last: the stash kinds go to the tavern for the mission (Restore potions, Stone to Mud wands)
        if not self.stashed and not p.house_state().get("house") and \
                any(p.stash_to_drop(i) for i in w.items()):
            self.stashed = True
            self.sub = StashDeposit()
            return None
        return NEXT

    def _buying_deposit(self, p, ctx):
        """A house: the gold (and the stash) into it, last of all (HouseBank deposit)."""
        w = ctx.w
        # and last of all, the gold into the house: the dungeon has no use for it, its thieves do
        # (2.50.0: for the stash only while the house has a free square -- else the tavern room takes it, below)
        if not self.deposited and p.house_state().get("house") and \
                (w.ind.get("gold", [0])[0] > p.BANK_FLOAT + 500 or
                 (any(p.stash_to_drop(i) for i in w.items()) and p.stash_room()["house"])):
            self.deposited = True
            self.sub = HouseBank("deposit")
            return None
        return NEXT

    def _buying_overflow(self, p, ctx):
        """2.50.0 (the user): the house full, the stash it left goes inside the tavern room (StashDeposit: farthest
        from the door first, never from the entrance), recorded in house.json `tavern.items`."""
        w = ctx.w
        if not self.overflowed and p.house_state().get("house") and p.stash_room()["house"] == 0 and \
                any(p.stash_to_drop(i) for i in w.items()):
            self.overflowed = True
            if p.stash_room()["tavern"]:
                self.sub = StashDeposit()
                self.done_log.append("the house is full: the stash's overflow to the tavern room")
                return None
        return NEXT

    def _buying_stash_full(self, p, ctx):
        """2.50.0 (the user): a stash item still carried with no free square in the house (or no house) nor in the
        tavern room: it stays in the pack (never sold) and the Navigator is told, once a visit per item, to `ask` the
        Architect about storage (another house: their decision, never bought by the policy). A `stash_full` notice."""
        w = ctx.w
        room = p.stash_room()
        if room["house"] or room["tavern"] is None or room["tavern"]:
            return NEXT
        left = [i["name"] for i in w.items() if p.stash_to_drop(i) and i["name"] not in self.full_told]
        if left:
            self.full_told.update(left)
            whys = [f"{n} ({p.stash_reason(i) or 'stash'})" for n in left
                    for i in [next(x for x in w.items() if x["name"] == n)]]
            where = ("the house's squares are all used and " if p.house_state().get("house") else "no house, and ")
            p.notify("stash_full", f"no room to store {'; '.join(whys)}: {where}no free square is seen in the tavern "
                                   "room -- kept in the pack (never sold). `ask` the Architect about storage (another "
                                   "house?)", fields={"items": left})
            self.done_log.append(f"no room to store {', '.join(left)}: the Navigator told")
        return NEXT

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
        # (2.53.0, m63: plan town ended with ~26k gold carried and its reply didn't say the bank step had failed)
        gold = w.ind.get("gold", [0])[0]
        bank = ""
        if p.house_state().get("house") and gold > p.BANK_FLOAT + 500:
            why = next((ln for ln in self.done_log if "house" in ln and ("fail" in ln or "couldn't" in ln
                                                                          or "wasn't" in ln)), None)
            bank = f"BANK: {gold} gold still carried -- `house deposit`" + (f" ({why})" if why else
                                                                           " (the bank step didn't run)")
            p.notify("bank", f"plan town left {gold} gold in the purse: {bank}")
        p.log("town_kit", sold=self.sold, bought=self.bought, identified=self.identified,
              gold=gold, short=short, gap=gap, bank_left=bool(bank))
        return ("done", (bank + "; " if bank else "") + head + tail + ("; not afforded: " + ", ".join(short) if short else "") +
                (" | " + " | ".join(self.done_log) if self.done_log else ""))
