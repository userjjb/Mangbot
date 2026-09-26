#!/usr/bin/env python3
"""pilot -- plays a MAngband character second to second; an agent steers it.

Runs as a daemon that owns the client (mangclient -mtool). Each tick (~20/s)
it applies client events to its World, then acts on the first rule that
fires:

  1. dead/ghost                  -> stop
  2. emergency (HP < flee_hp)    -> stairs underfoot, else Phase Door, else a
                                    cure potion; then tell the agent
  3. arrival into danger         -> take the stairs straight back
  4. hungry                      -> eat (no food: recall)
  5. monster adjacent            -> stand still: the server's auto-retaliate
                                    fights (warn the agent below think_hp)
  6. hurt, nothing in view       -> rest
  7. the current goal            -> one step of it
  8. no goal                     -> safe idle; after idle_recall_s without
                                    the agent, read Word of Recall

The agent talks to it through pilotctl.py (a unix socket): status, goals,
orders, actions, and wait-attention (block until the pilot needs a decision).
See HANDBOOK.md for the player's view; design_pilot.md for the why.
"""
import argparse
import json
import os
import queue
import re
import socket
import socketserver
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shopcat"))

from mang import MangClient, ClientExited      # noqa: E402
import glyphs                                   # noqa: E402
from world import World                          # noqa: E402
from mover import Mover, direction               # noqa: E402

TV_SCROLL, TV_POTION, TV_FOOD, TV_FLASK, TV_LITE = 70, 75, 80, 77, 39
CURE_POTIONS = ("Cure Critical Wounds", "Cure Serious Wounds", "Cure Light Wounds", "Healing")

DEFAULT_ORDERS = {
    "flee_hp": 0.5,        # emergency below this HP fraction
    "think_hp": 0.65,      # tell the agent below this, while fighting
    "rest_below": 0.7,     # rest when nothing is in view and HP is below this
    "rest_to": 0.95,
    "arrival_pack": 4,     # this many monsters in view on arrival -> leave by the stairs
    "danger_level": 6,     # a monster this many levels above ours in view -> leave/avoid
    "idle_recall_s": 600,  # no goal and no agent contact for this long -> recall to town
                           # (long enough for a slow agent turn; 180 s fired mid-thought)
    "pickup": "all",       # all | none
    "stop_on": "unique,danger",  # what makes a dive stop and ask (also: items, pillared)
    "pillared": "explore",       # dive: explore pillared rooms for a '>' by itself (or: ask, ignore)
    "loot_radius": 10,           # dive: fetch items seen within this many squares (0 = off)
    "choke": "on",               # meet packs in a corridor, not in the open (the user's advice)
    "junk": "Salt Water,Blindness,Weakness,Sleep,Poison,Lose Memories,Confusion,Sickliness,"
            "Apple Juice,Slime Mold,Darkness,Aggravate Monster,Curse Weapon,Curse Armour,"
            "Summon Undead,Summon Monster,Treasure Detection,Detect Invisible",
                                 # items "of <these>" aren't picked up (unknown items still are)
    "max_depth": 0,              # feet; 0 = no limit. Dives stop there, explore refuses below it,
                                 # and after an emergency trip down the stairs we come back up
}


class Attention(Exception):
    pass


# --------------------------------------------------------------------------
# Goals: tick(pilot) -> None (still working) or (status, detail)
# --------------------------------------------------------------------------

class Goal:
    name = "goal"

    def describe(self):
        return self.name

    def tick(self, p):
        return ("done", None)


class Wait(Goal):
    def __init__(self, secs):
        self.until = time.time() + float(secs)
        self.name = f"wait {secs}"

    def tick(self, p):
        return None if time.time() < self.until else ("done", None)


class Goto(Goal):
    def __init__(self, target):
        self.target = target
        self.name = f"goto {target}"
        self.started = False

    def tick(self, p):
        w = p.w
        if not self.started:
            goals = p.resolve_target(self.target)
            if not goals:
                return ("failed", f"no such place: {self.target}")
            if w.pos in goals:
                return ("done", None)
            if not p.mover.go(goals):
                return ("failed", "no known path")
            self.started = True
        st = p.mover.tick()
        if st == "arrived":
            return ("done", None)
        if st == "stuck":
            return ("failed", "stuck")
        return None


class Explore(Goal):
    """Walk to the nearest frontier (known floor next to unknown) until none is
    left, or until stairs are seen (until='stairs')."""

    def __init__(self, until=None, radius=None):
        self.until = until
        self.radius = radius
        self.name = "explore" + (f" until {until}" if until else "") + (f" radius {radius}" if radius else "")
        self.center = None
        self.fails = 0
        self.target = None
        self.no_run_at = None
        self.run_from = None

    def tick(self, p):
        w = p.w
        if not w.in_dungeon:
            # On the surface the "frontier" runs off the level edge into the
            # wilderness (it once wandered from town to 2S 2E)
            return ("failed", "explore is for dungeon levels, not the town or wilderness")
        md = int(p.orders.get("max_depth", 0))
        if md and w.depth_ft > md and self.until not in ("stairs", "upstairs"):
            return ("failed", f"{w.depth_ft} ft is below max_depth {md}: go up first")
        if self.center is None:
            self.center = w.pos
        if self.until == "stairs" and w.find(">"):
            return ("done", "stairs down seen")
        if self.until == "upstairs" and w.find("<"):
            return ("done", "stairs up seen")
        if p.level_seen != w.level_t:
            p.level_seen = w.level_t
            p.unreachable = set()
            p.visited = set()
        if p.mover.active:
            was_free = p.mover.free is not None
            st = p.mover.tick()
            if st == "stuck" and was_free:
                self.no_run_at = self.run_from      # a run can't start here: walk
                st = "arrived"
            if st == "stuck":
                self.fails += 1
                # remember what we couldn't get to (and what blocked us)
                p.unreachable |= p.mover.avoid | ({self.target} if self.target else set())
            if st in ("moving",):
                return None
        # Where we've stood is explored: unknown squares next to it are unlit
        # rock our light didn't reach, not a way on (the explorer once "failed"
        # because the only frontier left was the square it stood on)
        p.visited.add(w.pos)
        frontier = [f for f in p.frontier(center=self.center if self.radius else None, radius=self.radius)
                    if f != w.pos and f not in p.visited]
        if not frontier:
            return ("done", "nothing left to explore")
        # (targets we failed to reach are dropped from the frontier, not avoided
        # as path squares: that once made walked corridors impassable)
        if self.fails > 10 or not p.mover.go(frontier):
            return ("failed", "frontier unreachable")
        self.target = p.mover.path[-1] if p.mover.path else None
        # In a corridor with nothing about: run along it the way the path
        # starts, and let the run follow the corridor (as the user explores)
        # Run instead of walking hop by hop: along corridors (the run follows
        # them), and across dark rooms, where the unknown is always just one
        # square away (60 of 71 explore plans were single steps)
        m = p.mover
        if m.path and not m._monster_near(5) and not self.radius and \
                (m.in_corridor() or len(m.path) <= 2) and self.no_run_at != w.pos:
            d = direction(w.pos, m.path[0])
            if d:
                self.run_from = w.pos
                m.free_run(d)
        return None


class Dive(Goal):
    """Stair-scum down to target_ft (the user's way to dive): on arrival, if a
    '>' is known and reachable, take it; else go back up and down for a fresh
    level. Not on stairs and none known: explore until some are seen."""

    def __init__(self, target_ft):
        self.target_ft = int(target_ft)
        self.name = f"dive {self.target_ft}ft"
        self.start_ft = None
        self.level_seen = None
        self.pending = None      # stairs command sent at time t
        self.walking = False
        self.explore = None
        self.reported = set()
        self.probed = None
        self.looted = set()
        self.looting = False
        self.pillared_done = False
        self.need_search = False
        self.stuck = 0
        self.explore_fails = 0
        self.bad_stairs = set()     # (level, tile) of stairs we couldn't reach
        self.bad_t = {}
        self.bad_cleared = 0

    def tick(self, p):
        w = p.w
        md = int(p.orders.get("max_depth", 0))
        if md and self.target_ft > md:
            self.target_ft = md
            self.name = f"dive {md}ft (max_depth)"
        up = self.target_ft < self.start_ft if self.start_ft is not None else False
        if self.start_ft is None:
            self.start_ft = w.depth_ft
            up = self.target_ft < self.start_ft
        want, other = ("<", ">") if up else (">", "<")
        if (not up and w.depth_ft >= self.target_ft) or (up and w.depth_ft <= self.target_ft):
            return ("done", f"reached {w.depth_ft} ft")
        if self.pending and w.level_t < self.pending and time.time() - self.pending < 3:
            return None           # waiting for the level change
        self.pending = None
        if time.time() - w.level_t < 0.6:
            return None           # let the new level's map arrive
        if w.level_t != self.level_seen:
            self.level_seen = w.level_t
            self.walking = False
            self.explore = None
            self.looted = set()
            self.pillared_done = False
            why = p.interesting()
            if why:
                return ("interesting", why)
        # Standing orders that save asking the agent: loot what's close...
        lr = int(p.orders.get("loot_radius", 0))
        if lr and not self.walking and not w.monsters:
            items = [t for t in p.resolve_target("item") if w.dist(t) <= lr and t not in self.looted]
            if items and not p.mover.active:
                tgt = min(items, key=w.dist)
                self.looted.add(tgt)
                if p.mover.go([tgt]):
                    self.looting = True
            if getattr(self, "looting", False):
                st = p.mover.tick()
                if st == "moving":
                    return None
                self.looting = False
        # ... and explore a pillared room for a '>' (the user: they often hold stairs)
        if p.orders.get("pillared") == "explore" and not self.pillared_done and not w.find(want) \
                and p.pillared():
            if self.explore is None:
                self.explore = Explore(until="upstairs" if want == "<" else "stairs", radius=15)
            r = self.explore.tick(p)
            if r is None:
                return None
            self.explore = None
            self.pillared_done = True
        # Nothing known about the tile underfoot (e.g. just logged in): try '>'
        # once here -- at worst "I see no down staircase here."
        if w.standing_on is None and self.probed != (w.level_t, w.pos) and not self.walking:
            self.probed = (w.level_t, w.pos)
            return self._stairs(p, want)
        # A '>' we know about? (in town: also where we saw it before -- the town
        # never changes, and its staircase isn't lit at night)
        downs = w.find(want)
        if not downs and w.depth == 0 and p.town_stairs and not up:
            downs = [tuple(p.town_stairs)]
            w.memory.setdefault(downs[0], ">")
        if w.standing_on == want:
            return self._stairs(p, want)
        downs = [d for d in downs if (w.level_t, d) not in self.bad_stairs]
        if downs and not self.walking:
            if p.mover.go(downs):
                self.walking = True
            else:
                self.mark_bad(w, downs)
        if self.walking:
            st = p.mover.tick()
            if st == "arrived" or (st == "idle" and w.pos in downs):
                self.walking = False
                return self._stairs(p, want)
            if st == "idle":
                # the mover was stopped (a fight): walk on next tick
                self.walking = False
                return None
            if st == "stuck":
                self.walking = False
                self.stuck += 1
                if self.stuck < 5:
                    return None
            else:
                return None
        # Scum: back the way we came on the staircase we're on, then again
        if w.standing_on == other:
            return self._stairs(p, other)
        # No stairs under us: explore until we see some (either kind)
        self.expire_bad(w)
        ups = [u for u in w.find(other) if (w.level_t, u) not in self.bad_stairs]
        if ups and (self.explore is None or not isinstance(self.explore, Explore) or not p.mover.active):
            if not p.mover.active and not p.mover.go(ups):
                # no path to any of them (it spun here re-planning 20x a second)
                self.mark_bad(w, ups)
            else:
                st = p.mover.tick()
                if st == "arrived" and w.standing_on == other:
                    return self._stairs(p, other)
                if st in ("moving", "idle"):
                    return None
                if st == "stuck":
                    self.mark_bad(w, ups)
        if self.explore is None:
            self.explore = Search() if self.need_search else \
                Explore(until="upstairs" if want == "<" else "stairs")
        r = self.explore.tick(p)
        if isinstance(self.explore, Search):
            if r and r[0] == "failed":
                return ("failed", "no stairs: explored and searched every dead end")
            if r:
                self.explore = None
                self.need_search = False
            return None
        if r and r[0] == "failed":
            # Often transient (monsters in the way): forget what failed, try again
            self.explore_fails += 1
            if self.explore_fails < 4:
                p.unreachable = set()
                self.explore = None
                return None
            return ("failed", "no stairs found: " + r[1])
        if r and r[1] == "nothing left to explore" and w.find("<>") and self.bad_stairs:
            # Stairs are known but were marked unreachable (e.g. planned before
            # the map had loaded): try them again, a few times
            self.bad_cleared += 1
            if self.bad_cleared > 3:
                return ("failed", "stairs known but unreachable, nothing left to explore")
            self.bad_stairs = set()
            self.explore = None
            return None
        if r and r[1] == "nothing left to explore" and not w.find("<>"):
            # Walled in: look for secret doors, then explore again
            self.need_search = True
        if r:
            self.explore = None
        return None

    def mark_bad(self, w, tiles):
        now = time.time()
        for t in tiles:
            self.bad_stairs.add((w.level_t, t))
            self.bad_t[(w.level_t, t)] = now

    def expire_bad(self, w):
        """Unreachable stairs get another try after 15 s (the map fills in)."""
        now = time.time()
        for k in [k for k, t in self.bad_t.items() if now - t > 15]:
            self.bad_stairs.discard(k)
            del self.bad_t[k]

    def _stairs(self, p, which):
        p.take_stairs(which)
        self.pending = time.time()
        return None


class Search(Goal):
    """Look for secret doors: stand at each dead end (and corridor ends) and
    search a few times -- the user's doc lore: dead ends, lone doors,
    corridor ends. Done when a new door/opening shows up (explore again)."""

    def __init__(self, tries=8):
        self.name = "search dead ends"
        self.tries = tries
        self.spots = None
        self.searching = 0
        self.known = None

    def dead_ends(self, w):
        mem = w.memory
        out = []
        for (y, x), ch in mem.items():
            if ch in "#%*: +12345678":
                continue
            # Few open squares around: a dead end, the end of a (two-wide)
            # corridor, or a room corner -- where secret doors tend to be
            n = sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                    if (dy or dx) and mem.get((y + dy, x + dx), " ") not in "#%*: ")
            if n <= 3:
                out.append((y, x))
        return out

    def tick(self, p):
        w = p.w
        if self.known is None:
            self.known = len(p.frontier())
            self.spots = sorted(self.dead_ends(w), key=w.dist)
        if len(p.frontier()) > self.known:
            return ("done", "found a way on")
        if self.searching:
            if time.time() < p.busy_until:
                return None
            self.searching -= 1
            p.cmd("custom s", "search for secret doors", hold=0.45)
            return None
        if p.mover.active:
            st = p.mover.tick()
            if st == "moving":
                return None
            if st == "arrived":
                self.searching = self.tries
                return None
        if not self.spots:
            return ("failed", "searched every dead end, nothing found")
        spot = self.spots.pop(0)
        if w.pos == spot:
            self.searching = self.tries
        elif not p.mover.go([spot]):
            return None
        return None


class Hunt(Goal):
    """Go and fight a monster by name: walk next to it, then stand still (the
    server's auto-retaliate does the hitting). Done when it's slain; failed
    when it's been out of sight for lost_s."""

    def __init__(self, name, lost_s=15):
        self.target = name.lower()
        self.name = f"hunt {name}"
        self.lost_s = lost_s
        self.last_seen = time.time()
        self.goal_tile = None

    def tick(self, p):
        w = p.w
        if any(t.startswith("You have slain") and self.target in t.lower() or
               t.startswith("You have destroyed") and self.target in t.lower() for t in w.recent(3)):
            return ("done", "slain")
        mons = [(y, x, r) for y, x, r in w.monsters if self.target in r.name.lower()]
        if not mons:
            if time.time() - self.last_seen > self.lost_s:
                return ("failed", "lost sight of it")
            return None
        self.last_seen = time.time()
        y, x, r = min(mons, key=lambda m: w.dist(m[:2]))
        if w.dist((y, x)) <= 1:
            p.mover.stop()
            return None           # adjacent: auto-retaliate fights
        near = [(y + dy, x + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
        if not p.mover.active or self.goal_tile != (y, x):
            self.goal_tile = (y, x)
            p.mover.go(near)
        p.mover.tick()
        return None


class Recover(Goal):
    """After an emergency escape by the stairs: rest on the staircase, take it
    again if threatened (the arrival rule), and once healed go back up if we
    came down past max_depth -- rather than carrying on at the new depth
    (Dive03 kept exploring at 1000 ft after fleeing down and died there)."""

    def __init__(self, came_by, prev_goal=None):
        self.came_by = came_by
        self.name = f"recover (fled by {came_by})"
        self.prev = prev_goal
        self.level = None

    def tick(self, p):
        w = p.w
        if self.level is None:
            self.level = w.level_t
        md = int(p.orders.get("max_depth", 0))
        too_deep = md and w.depth_ft > md
        if w.hp_frac < p.orders["rest_to"]:
            if not w.monsters:
                p.start_resting()
            return None
        if too_deep and w.standing_on == "<":
            p.take_stairs("<")
            return ("done", f"healed; back up from {w.depth_ft} ft (max_depth {md})")
        return ("done", f"healed at {w.depth_ft} ft")


class Flee(Goal):
    """Get away from something too dangerous: to the nearest known stairs and
    take them."""

    def __init__(self, why):
        self.name = f"flee ({why})"
        self.started = False

    def tick(self, p):
        w = p.w
        if w.standing_on in ("<", ">"):
            p.take_stairs(w.standing_on)
            return ("done", "left by the stairs")
        stairs = w.find("<>")
        if not stairs:
            return ("failed", "no stairs known")
        if not self.started or not p.mover.active:
            if not p.mover.go(stairs):
                return ("failed", "no path to stairs")
            self.started = True
        st = p.mover.tick()
        if st == "stuck":
            return ("failed", "stuck on the way to the stairs")
        return None


class Recall(Goal):
    name = "recall"

    def __init__(self):
        self.read_t = None
        self.start_depth = None
        self.inscribed = False

    def tick(self, p):
        w = p.w
        if self.start_depth is None:
            self.start_depth = w.depth
        if self.read_t and w.depth != self.start_depth:
            return ("done", f"arrived at {w.depth_ft} ft")
        if self.read_t is None:
            it = next((i for i in w.items(tval=TV_SCROLL) if "Word of Recall" in i["name"]), None)
            if not it:
                return ("failed", "no Word of Recall")
            # From town, recall goes to the deepest level ever reached -- which
            # can be below max_depth (it took Dive03 back to 1000 ft, where it had
            # died). Inscribe @R<feet> first: the recall depth (inscription guide).
            md = int(p.orders.get("max_depth", 0))
            if w.depth == 0 and md and f"@R{md}" not in it["name"]:
                if not self.inscribed:
                    self.inscribed = True
                    p.cmd(f"custom {{ item={it['item']} entry=@R{md}", f"recall depth {md} ft", hold=1.0)
                    w.inven_dirty = True
                    return None
            p.cmd(f"custom r item={it['item']}", f"read {it['name']}")
            self.read_t = time.time()
            return None
        if time.time() - self.read_t > 60:
            return ("failed", "recall didn't happen")
        return None


class Shop(Goal):
    """In town: walk into store N, sell and buy, leave.
    sells: [(item index, count)]; buys: [(name substring, count)]."""

    def __init__(self, store, buys=(), sells=()):
        self.store = str(store)
        # Sell from the end of the pack first: selling shifts the letters after it
        # (names are resolved when their turn comes)
        self.buys = list(buys)
        self.sells = sorted([s for s in sells if isinstance(s[0], int)], reverse=True) + \
            [s for s in sells if isinstance(s[0], str)]
        self.name = f"shop {store}" + "".join(f" buy {n}:{c}" for n, c in buys) + \
            "".join(f" sell {chr(97 + i) if isinstance(i, int) else i}:{c}" for i, c in sells)
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
                self.state, self.t = "enter", time.time()
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
            if time.time() - self.t > 4:
                self.state = "walk"
            return None
        if self.state == "trade":
            if self.pending:
                # The server's answer: a refreshed listing and/or a message
                said = [t for ts, t in w.messages if ts >= self.pending]
                verdict = next((t for t in said if t.startswith(("You sold", "You bought", "I don't want",
                                                                 "You do not have enough", "You cannot carry",
                                                                 "You have no room", "That item"))), None)
                if verdict is None and w.store_t < self.pending and time.time() - self.pending < 4:
                    return None   # still waiting
                self.done_log.append(verdict or f"{self.last} (no answer)")
                self.pending = None
                w.status_t = 0            # re-read gold before the next purchase
                w.inven_dirty = True
                return None
            if not w.store:
                return ("failed", "thrown out of the store")
            if self.sells:
                idx, n = self.sells.pop(0)
                if isinstance(idx, str):
                    # By name, resolved now (identifying items re-sorts the pack)
                    it = next((i for i in w.items() if idx.lower() in i["name"].lower()), None)
                    if not it:
                        self.done_log.append(f"no {idx} to sell")
                        return None
                    idx = it["item"]
                    w.inven_dirty = True
                p.c.send("confirm yes")
                p.cmd(f"custom s store item={idx} value={n}", f"sell {idx}x{n}", hold=0.2)
                self.last = f"sell {chr(97 + idx)} x{n}"
                self.pending = time.time()
                return None
            if self.buys:
                name, n = self.buys.pop(0)
                # The cheapest match: the first one can be an expensive enchanted
                # piece (bought a Cloak [1,+4] for 592 instead of a plain one)
                matches = [i for i in w.store["items"] if name.lower() in i["name"].lower()]
                it = min(matches, key=lambda i: i["price"]) if matches else None
                if not it:
                    self.done_log.append(f"no {name} in stock")
                    return None
                gold = w.ind.get("gold", [0])[0]
                n = min(n, it["number"], gold // max(1, it["price"]))
                if n <= 0:
                    self.done_log.append(f"can't afford {it['name']} ({it['price']})")
                    return None
                p.cmd(f"custom p store item={it['slot']} value={n} entry={it['price'] * n}",
                      f"buy {it['name']} x{n}", hold=0.2)
                self.last = f"buy {it['name']} x{n}"
                self.pending = time.time()
                return None
            p.cmd("leave", "leave store", hold=0.3)
            w.store = None
            return ("done", "; ".join(self.done_log) or "nothing to do")
        return None


class RestGoal(Goal):
    name = "rest"

    def tick(self, p):
        w = p.w
        if w.hp_frac >= p.orders["rest_to"] and w.ind.get("sp", [0, 0])[0] >= w.ind.get("sp", [0, 0])[1]:
            p.stop_resting()
            return ("done", None)
        if w.monsters:
            return ("failed", "monsters in view")
        p.start_resting()
        return None


# --------------------------------------------------------------------------

class Pilot:
    def __init__(self, client, rundir, orders=None, say=print):
        self.c = client
        self.w = World(client)
        self.mover = Mover(client, self.w, log=lambda *a, **k: self.log("move", **k))
        self.rundir = rundir
        os.makedirs(rundir, exist_ok=True)
        # Standing orders persist across restarts
        self.orders_file = os.path.join(rundir, "orders.json")
        saved = {}
        if os.path.exists(self.orders_file):
            with open(self.orders_file) as f:
                saved = {k: v for k, v in json.load(f).items() if k in DEFAULT_ORDERS}
        self.orders = dict(DEFAULT_ORDERS, **saved, **(orders or {}))
        self.dlog = open(os.path.join(rundir, "decisions.jsonl"), "a", buffering=1)
        self.say = say
        self.goal = None
        self.requests = queue.Queue()
        self.attention = []            # pending attention events (for wait-attention)
        self.news = []                 # informational events since the last report
        self.att_cond = threading.Condition()
        self.last_agent = time.time()
        self.busy_until = 0.0
        self.idle_recalled = False
        self.last_action = None
        self.emergency_t = 0.0
        self.think_warned = 0.0
        self.picked_t = 0.0
        self.parking = None
        self.light_t = self.light_warned = 0.0
        # Where the town's '>' is (remembered across runs: the town never changes)
        self.town_file = os.path.join(os.path.dirname(rundir.rstrip("/")), "town.json")
        self.town_stairs = None
        if os.path.exists(self.town_file):
            with open(self.town_file) as f:
                self.town_stairs = json.load(f).get("stairs")
        self.recall_t = 0.0
        self.flee_t = 0.0
        self.wear_queue = False
        self.breeder_level = None
        self.choke_state = None
        self.choke_t = self.choke_done_t = 0.0
        self.seen_drained = None
        self.seen_blows = None
        self.unreachable = set()       # frontier tiles we failed to reach (this level)
        self.visited = set()           # squares we've stood on while exploring (not frontier)
        self.level_seen = None
        self.phase_t = self.cure_t = self.noescape_t = 0.0
        self.escaping_to_stairs = False
        self.full_warned = 0.0
        self.running = True

    # --- logging / attention -------------------------------------------------

    def log(self, kind, **kw):
        rec = {"t": round(time.time(), 3), "kind": kind, "depth": self.w.depth, "pos": self.w.pos,
               "hp": self.w.hp, **kw}
        self.dlog.write(json.dumps(rec) + "\n")

    # Events that don't need a decision (the pilot already acted): shown in
    # the next report instead of waking the agent
    NEWS = {"danger_avoided", "started", "tactic"}

    def notify(self, what, detail=None):
        ev = {"t": round(time.time(), 3), "what": what, "detail": detail,
              "goal": self.goal.describe() if self.goal else None}
        self.log("attention", what=what, detail=detail)
        if what in self.NEWS:
            self.news.append(ev)
            self.news = self.news[-20:]
            return
        with self.att_cond:
            self.attention.append(ev)
            self.att_cond.notify_all()

    # --- low-level actions ---------------------------------------------------

    def cmd(self, line, why, hold=0.4):
        self.c.send(line)
        self.last_action = (time.time(), line, why)
        self.busy_until = time.time() + hold
        self.log("act", cmd=line, why=why)

    def take_stairs(self, which):
        self.mover.stop()
        self.w.last_stairs_cmd = (which, time.time())
        self.cmd(f"custom {which}", f"stairs {which}", hold=0.3)

    def start_resting(self):
        if not self.w.resting and time.time() > self.busy_until:
            self.cmd("rest", "rest", hold=1.0)
            self.w.status_t = 0

    def stop_resting(self):
        if self.w.resting:
            self.cmd("rest", "stop resting", hold=0.5)
            self.w.status_t = 0

    # --- perception helpers --------------------------------------------------

    def frontier(self, center=None, radius=None):
        mem = self.w.memory
        out = []
        for (y, x), ch in mem.items():
            if ch in "#%*: " or ch in "12345678" or (y, x) in self.unreachable:
                continue
            if center and radius and max(abs(y - center[0]), abs(x - center[1])) > radius:
                continue
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if (y + dy, x + dx) not in mem and 0 < y + dy < 65 and 0 < x + dx < 197:
                        out.append((y, x))
                        break
                else:
                    continue
                break
        return out

    def resolve_target(self, t):
        w = self.w
        if t in ("<", ">", "stairs"):
            return w.find("<>" if t == "stairs" else t)
        if t == "item":
            return [p for p, ch in w.memory.items() if ch not in "#%.'+<>^;:*=~ 12345678"]
        m = re.match(r"^(\d+)[ ,](\d+)$", str(t))
        if m:
            return [(int(m.group(1)), int(m.group(2)))]
        return []

    def pillared(self):
        """A pillared room near us (the user: these often hold stairs)."""
        w = self.w
        if not w.rows or not w.pos:
            return False
        y0, x0 = w.pos
        for y in range(max(1, y0 - 8), min(65, y0 + 9)):
            row = w.rows[y][max(0, x0 - 25):x0 + 26]
            if re.search(r"(#\.){4}", row) or re.search(r"(\.#){4}", row):
                return True
        return False

    def dangers(self):
        lev = self.w.ind.get("level", [1])[0]
        dl = self.orders["danger_level"]
        return [r for _, _, r in self.w.monsters if r.level >= lev + dl or "UNIQUE" in r.flags and r.level > lev]

    def interesting(self):
        so = set(self.orders["stop_on"].split(","))
        w = self.w
        why = []
        if "unique" in so:
            u = sorted({r.name for _, _, r in w.monsters if "UNIQUE" in r.flags})
            if u:
                why.append("unique: " + ", ".join(u))
        if "items" in so and w.itemlist and not w.itemlist[0].startswith("You see no"):
            why.append("items: " + "; ".join(l.strip() for l in w.itemlist[:6]))
        if "pillared" in so and self.pillared():
            why.append("pillared room (often holds stairs)")
        return "; ".join(why)

    # --- the rules -----------------------------------------------------------

    def reflexes(self):
        w, o = self.w, self.orders
        now = time.time()
        if w.ghost or w.hp[0] <= 0 and w.hp[1] > 0 and w.ind:
            if self.running:
                self.notify("dead", "the character died")
                self.running = False
            return True
        if now < self.busy_until:
            return True
        if w.store and isinstance(self.goal, Shop):
            return False          # any command would leave the store
        mons_near = [m for m in w.monsters if w.dist(m[:2]) <= 7]
        # 2. Emergency
        if w.hp_frac < o["flee_hp"] and (mons_near or now - w.last_hit_t < 5):
            return self.escape("low HP")
        # 3. Arrival into danger (connected stairs: the way back is underfoot)
        # A stairs command gets no answer at all if it comes too soon after the
        # level change (seen: '<' 0.7 s after arriving was ignored), so retry
        # after 1.2 s while still on the stairs
        stairs_pending = w.last_stairs_cmd and now - w.last_stairs_cmd[1] < 1.2
        if now - w.level_t < 6 and w.standing_on in ("<", ">") and not stairs_pending:
            danger = self.dangers()
            # A pack only counts if its members are within 5 levels of ours (a
            # pack of jackals is XP for a level-11 warrior, not a threat)
            lev = w.ind.get("level", [1])[0]
            threats = [m for m in mons_near if m[2].level >= lev - 5]
            if len(threats) >= o["arrival_pack"] or (danger and "danger" in o["stop_on"]):
                why = f"arrived next to {len(threats)} monsters ({threats[0][2].name if threats else ''})" + \
                    (f" incl. {danger[0].name} (lvl {danger[0].level})" if danger else "")
                self.take_stairs(w.standing_on)
                self.notify("danger_avoided", why)
                return True
        # 3a. Something far above our level in view: leave before it reaches us
        # (not only on arrival -- Dive03 met Stone trolls while exploring)
        near_danger = [r for y, x, r in w.monsters if w.dist((y, x)) <= 12 and r in self.dangers()]
        if near_danger and not isinstance(self.goal, (Flee, Recover)) and now - self.flee_t > 10 \
                and "danger" in o["stop_on"]:
            self.flee_t = now
            prev = self.goal.describe() if self.goal else None
            self.set_goal(Flee(near_danger[0].name))
            self.notify("danger_seen", f"{near_danger[0].name} (lvl {near_danger[0].level}) in view"
                                       f"{' while ' + prev if prev else ''}: heading for the stairs")
            return True
        # 3b. A pack coming at us in the open: back into a corridor so they
        # trickle into melee one at a time ("retreat behind a turn")
        if o.get("choke") == "on" and not w.adjacent_monsters() and w.standing_on not in ("<", ">"):
            if self.choke_tick(now):
                return True
        # 3c. Light
        if not w.adjacent_monsters() and self.keep_light(now):
            return True
        # 4. Hunger
        if w.hunger <= 2 and not w.monsters:
            food = w.items(tval=TV_FOOD)
            if food:
                self.cmd(f"eat {food[0]['item']}", f"hungry ({w.hunger})", hold=1.0)
                return True
            if w.hunger <= 1 and not isinstance(self.goal, Recall) and w.depth:
                self.notify("low_supply", "weak from hunger and no food: recalling")
                self.set_goal(Recall())
        # 5. Adjacent monster: let the server's auto-retaliate fight
        adj = w.adjacent_monsters()
        if adj:
            if self.mover.active and not isinstance(self.goal, (Goto, Flee)):
                self.mover.stop()
            if w.resting:
                self.stop_resting()
            if w.hp_frac < o["think_hp"] and now - self.think_warned > 10:
                self.think_warned = now
                self.notify("fight_going_badly",
                            f"HP {w.hp[0]}/{w.hp[1]} fighting {', '.join(sorted({r.name for *_, r in adj}))}")
            return not isinstance(self.goal, (Goto, Flee))
        # Pick up what we're standing on ("You see a ..." right after a step)
        if o["pickup"] == "all" and not adj and not w.store:
            seen = [(ts, t) for ts, t in w.messages if now - ts < 3 and t.startswith("You see ")
                    and "no items" not in t]
            junk = [j.strip().lower() for j in o.get("junk", "").split(",") if j.strip()]
            if seen and any(f"of {j}" in seen[-1][1].lower() or seen[-1][1].lower().rstrip(".").endswith(j)
                            for j in junk):
                seen = []         # known junk: leave it (it filled the pack on the way down)
            if seen and seen[-1][0] > self.picked_t and w.pos == self.seen_pos(seen[-1][0]):
                self.picked_t = now
                self.cmd("custom ,", f"pick up: {seen[-1][1][8:]}", hold=0.4)   # "Stay" picks up; "g" did nothing
                return True
        full = [t for ts, t in w.messages if now - ts < 3 and t.startswith("You have no room for")]
        if full and now - self.full_warned > 30:
            self.full_warned = now
            self.notify("pack_full", full[-1])
        # 6. Rest when hurt and alone
        if w.hp_frac < o["rest_below"] and not w.monsters and not isinstance(self.goal, (Recall,)):
            if not self.mover.active or isinstance(self.goal, Dive):
                self.mover.stop()
                self.start_resting()
                return True
        if w.resting and (w.hp_frac >= o["rest_to"] or w.monsters) and not isinstance(self.goal, RestGoal):
            self.stop_resting()
            return True
        return False

    def escape(self, why):
        """Emergency: stairs underfoot > (in melee) Phase Door > (not in melee)
        walk to nearby stairs, else a cure potion. Rate-limited: Phase Door
        again and again doesn't shake a pack (it burned 10 scrolls in 10 s)."""
        w = self.w
        now = time.time()
        if w.last_stairs_cmd and now - w.last_stairs_cmd[1] < 1.2:
            return True           # already on our way (retried after 1.2 s)
        if w.standing_on in ("<", ">"):
            which = w.standing_on
            self.take_stairs(which)
            self.notify("emergency", f"{why}: took the stairs underfoot ({which})")
            # then heal on the other side instead of carrying on with the goal
            if not isinstance(self.goal, Recover):
                self.goal = Recover(which, self.goal)
                self.log("goal", goal=self.goal.describe())
            return True
        adj = w.adjacent_monsters()
        can_read = not w.flag("blind") and not w.flag("confused")
        pd = w.tagged("r", 1) or next((i for i in w.items(tval=TV_SCROLL) if "Phase Door" in i["name"]), None)
        # Last resort, started early because it takes 15-35 s: Word of Recall
        if w.hp_frac < 0.3 and can_read and not self.recall_started(now):
            wor = next((i for i in w.items(tval=TV_SCROLL) if "Word of Recall" in i["name"]), None)
            if wor and w.in_dungeon:
                self.recall_t = now
                self.cmd(f"custom r item={wor['item']}", f"{why}: word of recall (last resort)", hold=0.5)
                self.notify("emergency", f"{why}: read Word of Recall as a last resort")
                return True
        # Rate-limited (repeated phasing doesn't shake a pack), except when HP
        # is collapsing with something next to us
        collapsing = w.hp_frac < 0.35
        if adj and pd and can_read and (now - self.phase_t > 2.5 or (collapsing and now - self.phase_t > 0.7)):
            self.phase_t = now
            self.cmd(f"custom r item={pd['item']}", f"{why}: phase door", hold=0.6)
            self.notify("emergency", f"{why}: read Phase Door ({', '.join(sorted({r.name for *_, r in adj}))} adjacent)")
            return True
        if not adj:
            # Out of melee: make for stairs if some are close, else heal
            stairs = [p for p in w.find("<>") if w.dist(p) <= 20]
            if stairs and not self.mover.active:
                if self.mover.go(stairs):
                    self.escaping_to_stairs = True
                    self.notify("emergency", f"{why}: heading for the stairs {min(w.dist(p) for p in stairs)} away")
            if self.mover.active and self.escaping_to_stairs:
                st = self.mover.tick()
                if st == "arrived" and w.standing_on in ("<", ">"):
                    self.take_stairs(w.standing_on)
                return True
        if now - self.cure_t > 1.5:
            for name in CURE_POTIONS:
                pot = next((i for i in w.items(tval=TV_POTION) if name in i["name"]), None)
                if pot:
                    self.cure_t = now
                    self.cmd(f"custom q item={pot['item']}", f"{why}: quaff {name}", hold=0.6)
                    self.notify("emergency", f"{why}: quaffed {name}")
                    return True
        if now - self.noescape_t > 10:
            self.noescape_t = now
            left = [n for n, ok in (("Phase Door", pd), ("cure potions", any(
                    any(c in i["name"] for c in CURE_POTIONS) for i in w.items(tval=TV_POTION)))) if ok]
            self.notify("emergency", f"{why}: " + (f"waiting to use {', '.join(left)} again, fighting on"
                                                   if left else "nothing left to escape with, fighting on"))
        return False

    def recall_started(self, now):
        """A Word of Recall is already under way (read recently, or the message)."""
        if now - self.recall_t < 40:
            return True
        return any("air about you becomes charged" in t for t in self.w.recent(40))

    def seen_pos(self, t):
        """Where we were at time t (for 'You see' messages): the position then."""
        return self.w.pos if self.w.pos_t <= t + 0.5 else None

    def set_goal(self, goal):
        self.mover.stop()
        self.goal = goal
        self.idle_recalled = False
        self.log("goal", goal=goal.describe() if goal else None)

    def step_goal(self):
        if not self.goal:
            return False
        try:
            r = self.goal.tick(self)
        except Exception as e:           # a goal bug must not kill the pilot
            r = ("failed", f"error: {e!r}")
        if r:
            status, detail = r
            g = self.goal.describe()
            self.goal = None
            self.mover.stop()
            self.notify({"done": "goal_done", "failed": "goal_failed"}.get(status, status),
                        f"{g}: {detail}" if detail else g)
        return True

    def idle(self):
        w = self.w
        if w.in_dungeon and not self.idle_recalled and \
                time.time() - self.last_agent > self.orders["idle_recall_s"]:
            self.idle_recalled = True
            self.notify("idle_recall", "no word from the agent: recalling to town")
            self.set_goal(Recall())

    def choke_tick(self, now):
        w = self.w
        lev = w.ind.get("level", [1])[0]
        pack = [m for m in w.monsters if w.dist(m[:2]) <= 10 and m[2].level >= lev - 5]
        if self.choke_state == "going":
            st = self.mover.tick()
            if st == "moving":
                return True
            self.choke_state = "holding"
            self.choke_t = now
            self.log("act", cmd="-", why=f"holding the corridor at {w.pos}")
            return True
        if self.choke_state == "holding":
            if not pack or now - self.choke_t > 25:
                self.choke_state = None
                return False
            return True           # stand; auto-retaliate greets them one by one
        if len(pack) < 3 or self.mover.in_corridor() or now - self.choke_done_t < 15:
            return False
        # A corridor square within 10 steps, further from the pack than we are
        cy = sum(m[0] for m in pack) / len(pack)
        cx = sum(m[1] for m in pack) / len(pack)
        d_now = max(abs(w.pos[0] - cy), abs(w.pos[1] - cx))
        mem = w.memory
        cands = []
        for (y, x), ch in mem.items():
            if w.dist((y, x)) > 10 or ch in "#%*: 12345678" or ch in "<>" and False:
                continue
            if max(abs(y - cy), abs(x - cx)) <= d_now:
                continue
            open_ = sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                        if (dy or dx) and mem.get((y + dy, x + dx), " ") not in "#%*: ")
            if open_ <= 2:
                cands.append((y, x))
        if not cands:
            self.choke_done_t = now
            return False
        if self.mover.go(cands):
            self.choke_state = "going"
            self.choke_done_t = now
            self.notify("tactic", f"{len(pack)} monsters coming ({pack[0][2].name}): backing into a corridor")
            return True
        self.choke_done_t = now
        return False

    def watch_breeders(self):
        """Breeders (lice, worms...) multiply without end and block every path:
        tell the agent once per level that it's time to leave."""
        w = self.w
        br = [r for *_, r in w.monsters if "MULTIPLY" in r.flags]
        if len(br) >= 3 and self.breeder_level != w.level_t:
            self.breeder_level = w.level_t
            if isinstance(self.goal, Dive):
                return            # a dive is leaving this level anyway
            self.notify("breeders", f"{len(br)} breeding monsters in view ({br[0].name}): leave this level "
                                    "(stairs, or recall)")

    def keep_light(self, now):
        """Refill the lantern (or swap torches) before the light goes out --
        Dive03 explored in the dark for minutes after "Your light has gone
        out!", which is why nothing around it ever showed up on the map."""
        w = self.w
        if now < self.light_t or now < self.busy_until or w.store:
            return False
        self.light_t = now + 5
        worn = next((i for i in w.items(equip=True) if i["tval"] == TV_LITE), None)
        m = re.search(r"with (\d+) turns", worn["name"]) if worn else None
        turns = int(m.group(1)) if m else None
        if worn and "Lantern" in worn["name"] and turns is not None and turns < 3000:
            flask = next((i for i in w.items(tval=TV_FLASK)), None)
            if flask:
                self.cmd(f"custom F item={flask['item']}", f"refill lantern ({turns} turns left)", hold=0.6)
                return True
            if now - self.light_warned > 120:
                self.light_warned = now
                self.notify("low_supply", f"lantern at {turns} turns and no flasks of oil")
        elif worn and "Torch" in worn["name"] and turns is not None and turns < 500:
            torch = next((i for i in w.items(tval=TV_LITE) if "Torch" in i["name"]), None)
            if torch:
                self.cmd(f"custom w item={torch['item']}", f"fresh torch ({turns} turns left)", hold=0.6)
                return True
        elif not worn:
            spare = next((i for i in w.items(tval=TV_LITE)), None)
            if spare:
                self.cmd(f"custom w item={spare['item']}", "wield a light", hold=0.6)
                return True
            if now - self.light_warned > 120:
                self.light_warned = now
                self.notify("low_supply", "no light source")
        return False

    STAT_NAMES = ("STR", "INT", "WIS", "DEX", "CON", "CHR")

    def watch_character(self):
        """Tell the agent when a stat gets drained or the blows change (the
        user lost a blow to a DEX-draining invisible monster)."""
        ind = self.w.ind
        if not ind:
            return
        drained = tuple(n for i, n in enumerate(self.STAT_NAMES)
                        if len(ind.get(f"stat{i}", [])) >= 2 and ind[f"stat{i}"][0] < ind[f"stat{i}"][1])
        blows = ind.get("skills2", [None])[0]
        if self.seen_drained is not None and drained != self.seen_drained:
            new = [d for d in drained if d not in self.seen_drained]
            if new:
                self.notify("stat_drained", f"{', '.join(new)} drained (blows {blows}); restore at the Alchemist/Temple")
        if self.seen_blows is not None and blows is not None and blows != self.seen_blows:
            self.notify("blows_changed", f"blows per round {self.seen_blows} -> {blows}")
        self.seen_drained, self.seen_blows = drained, blows

    WEAR_TVALS = {21: "weapon", 22: "weapon", 23: "weapon", 19: "bow", 39: "light", 30: "boots", 31: "gloves",
                  32: "helm", 33: "helm", 34: "shield", 35: "cloak", 36: "body", 37: "body", 38: "body",
                  40: "amulet"}

    def wear_step(self):
        """One item per call (letters shift after each): wear what fills an empty slot."""
        w = self.w
        if time.time() < self.busy_until or w.inven_dirty:
            return
        worn = {self.WEAR_TVALS.get(i["tval"]) for i in w.items(equip=True)}
        for it in w.items():
            kind = self.WEAR_TVALS.get(it["tval"])
            if kind and kind not in worn:
                self.cmd(f"custom w item={it['item']}", f"wear {it['name']}", hold=0.8)
                w.inven_dirty = True
                return
        self.wear_queue = False

    def note_town_stairs(self):
        w = self.w
        if w.depth == 0 and not self.town_stairs:
            st = w.find(">")
            if st:
                self.town_stairs = list(st[0])
                with open(self.town_file, "w") as f:
                    json.dump({"stairs": self.town_stairs}, f)

    def park_tick(self):
        """Parking: log out once it's safe (restarting mid-fight is dangerous)."""
        w = self.w
        near = [m for m in w.monsters if w.dist(m[:2]) <= 15]
        safe = not near and w.hp_frac >= 0.7 and not w.store and \
            not (w.last_stairs_cmd and time.time() - w.last_stairs_cmd[1] < 3)
        if safe or time.time() - self.parking > 300:
            self.notify("parked", "logging out for a Pilot update; back in a minute -- "
                                  "re-issue your goal when you see 'started'"
                        + ("" if safe else " (parked after 5 min without a safe moment)"))
            with self.att_cond:
                self.att_cond.wait(1.5)   # let a waiting Navigator collect the event
            self.running = False

    def tick(self):
        self.w.drain()
        self.w.refresh()
        self.note_town_stairs()
        if self.wear_queue:
            self.wear_step()
        self.watch_character()
        self.watch_breeders()
        self.handle_requests()
        if not self.running:
            return
        if self.reflexes():
            return
        if self.parking:
            self.park_tick()
            return
        if self.step_goal():
            return
        self.idle()

    # --- control requests (from the socket thread) ---------------------------

    def handle_requests(self):
        while True:
            try:
                req, reply = self.requests.get_nowait()
            except queue.Empty:
                return
            self.last_agent = time.time()
            try:
                out = self.do_request(req)
            except Exception as e:
                out = {"ok": False, "error": repr(e)}
            reply.put(out)

    ACTIONS = {"wear": "w", "takeoff": "t", "quaff": "q", "read": "r", "eat": "E", "fuel": "F",
               "destroy": "k", "drop": "d", "inspect": "I", "aim": "a", "use": "u", "zap": "z"}

    def item_index(self, letter, equip=False):
        """Inventory letter (a, b, ...) as in the report, or part of an item's
        name (spaces as '_'; resolved now, so it can't go stale) -> item index."""
        if len(letter) == 1 and letter.isalpha():
            return ord(letter) - ord("a")
        if letter.isdigit():
            return int(letter)
        name = letter.replace("_", " ").lower()
        pool = self.w.items(equip=True) + self.w.items() if equip else self.w.items() + self.w.items(equip=True)
        it = next((i for i in pool if name in i["name"].lower()), None)
        if it is None:
            raise ValueError(f"no item matching '{letter}'")
        return it["item"]

    def pack_now(self, wait=0.7):
        """Re-read the pack right after an action (the report lagged behind a
        batch of destroys, and the Navigator then acted on stale letters)."""
        self.c.collect(wait)
        self.w.drain()
        self.w.inven = self.c.inven()
        self.w.inven_t = time.time()
        self.w.inven_dirty = False
        return [f"{chr(97 + i['item'])}) {i['name']}" for i in self.w.items()]

    def do_request(self, req):
        c = req.get("cmd")
        args = req.get("args", [])
        if c == "status":
            return {"ok": True, "report": self.report()}
        if c == "goal":
            return self.request_goal(args)
        if c == "stop":
            self.set_goal(None)
            self.stop_resting()
            return {"ok": True}
        if c == "order":
            for kv in args:
                k, v = kv.split("=", 1)
                if k not in self.orders:
                    return {"ok": False, "error": f"no order {k}"}
                cur = self.orders[k]
                self.orders[k] = type(cur)(v) if not isinstance(cur, str) else v
            with open(self.orders_file, "w") as f:
                json.dump(self.orders, f)
            return {"ok": True, "orders": self.orders}
        if c in self.ACTIONS:
            key = self.ACTIONS[c]
            if not args:
                return {"ok": False, "error": f"usage: {c} ITEMLETTER"}
            try:
                item = self.item_index(args[0], equip=(c == "takeoff"))
            except ValueError as e:
                return {"ok": False, "error": str(e)}
            extra = ""
            if c in ("destroy", "drop"):
                extra = f" value={args[1] if len(args) > 1 else 1}"
                if c == "destroy":
                    self.c.send("confirm yes")
            if c in ("aim",):
                extra = f" dir={args[1] if len(args) > 1 else 5}"
            t0 = time.time()
            self.cmd(f"custom {key} item={item}{extra}", f"agent: {c} {args}")
            pack = self.pack_now()
            said = [t for ts, t in self.w.messages if ts >= t0]
            return {"ok": True, "said": said[-4:], "pack": pack}
        if c == "wearall":
            # Put on every weapon/armour/light in the pack whose slot is empty
            self.wear_queue = True
            return {"ok": True}
        if c == "inscribe":
            try:
                item = self.item_index(args[0])
            except ValueError as e:
                return {"ok": False, "error": str(e)}
            self.cmd(f"custom {{ item={item} entry={' '.join(args[1:])}", f"agent: inscribe {args}")
            return {"ok": True, "pack": self.pack_now()}
        if c == "pickup":
            self.cmd("custom ,", "agent: pickup")
            return {"ok": True}
        if c == "stairs":
            self.take_stairs(args[0] if args else (self.w.standing_on or ">"))
            return {"ok": True}
        if c == "option":
            self.c.send(f"option {args[0]} {args[1]}")
            return {"ok": True}
        if c == "goalstate":
            g = self.goal
            st = {k: (repr(v)[:120]) for k, v in (vars(g).items() if g else [])}
            if g and getattr(g, "explore", None) is not None:
                st["explore_state"] = {k: repr(v)[:80] for k, v in vars(g.explore).items()}
            return {"ok": True, "goal": g.describe() if g else None, "state": st,
                    "mover": {"active": self.mover.active, "path": len(self.mover.path),
                              "free": self.mover.free is not None, "running": self.mover.running is not None},
                    "standing_on": self.w.standing_on, "busy": self.busy_until - time.time()}
        if c == "options":
            opts = self.c.query("options", "options")["list"]
            return {"ok": True, "options": {k: v for k, v in opts.items() if not args or any(a in k for a in args)}}
        if c == "dump":
            path = os.path.join(self.rundir, "world_dump.json")
            with open(path, "w") as f:
                json.dump({"pos": self.w.pos, "depth": self.w.depth, "rows": self.w.rows,
                           "memory": [[y, x, ch] for (y, x), ch in self.w.memory.items()],
                           "monsters": [[y, x, r.idx] for y, x, r in self.w.monsters]}, f)
            return {"ok": True, "file": path}
        if c == "plan":
            # debug: path from here to Y,X on the remembered map
            from mover import plan as _plan
            goals = self.resolve_target(" ".join(args))
            path = _plan(self.w, goals) if goals else None
            around = {f"{dy},{dx}": self.w.memory.get((self.w.pos[0] + dy, self.w.pos[1] + dx), " ")
                      for dy in (-1, 0, 1) for dx in (-1, 0, 1)}
            return {"ok": True, "goals": goals, "path": path, "pos": self.w.pos, "around": around,
                    "depth": self.w.depth, "memory": len(self.w.memory)}
        if c == "raw":
            self.cmd(" ".join(args), "agent: raw")
            return {"ok": True}
        if c == "attention":
            with self.att_cond:
                evs, self.attention = self.attention, []
            return {"ok": True, "events": evs}
        if c == "quit":
            self.running = False
            return {"ok": True}
        if c == "park":
            # Log out at the next safe moment (for a Pilot update): the goal is
            # dropped now, the logout waits until nothing is close and HP is OK
            self.set_goal(None)
            self.parking = time.time()
            return {"ok": True, "note": "will log out when safe"}
        return {"ok": False, "error": f"unknown command {c}"}

    def request_goal(self, args):
        if not args:
            return {"ok": False, "error": "usage: goal NAME [ARGS]"}
        # Unread attention events belong to what came before: move them to the
        # news, so the next 'wait' answers about this goal
        with self.att_cond:
            self.news += self.attention
            self.attention = []
        name, rest = args[0], args[1:]
        if name == "dive":
            g = Dive(rest[0] if rest else (self.w.depth_ft + 50))
        elif name == "explore":
            kw = dict(a.split("=", 1) for a in rest if "=" in a)
            g = Explore(until=kw.get("until"), radius=int(kw["radius"]) if "radius" in kw else None)
        elif name == "goto":
            g = Goto(" ".join(rest))
        elif name == "shop":
            # goal shop STORE [buy NAME:N]... [sell LETTER:N]...
            buys, sells, i = [], [], 1
            while i < len(rest):
                kind, spec = rest[i], rest[i + 1] if i + 1 < len(rest) else ""
                what, _, n = spec.rpartition(":")
                what, n = (what, int(n)) if what else (spec, 1)
                if kind == "buy":
                    buys.append((what.replace("_", " "), n))
                elif kind == "sell":
                    key = what.replace("_", " ")
                    sells.append((self.item_index(key) if len(key) == 1 else key, n))
                i += 2
            g = Shop(rest[0], buys, sells)
        elif name == "search":
            g = Search()
        elif name == "hunt":
            g = Hunt(" ".join(rest).replace("_", " "))   # 'hunt Black_ogre', like shop names
        elif name == "recall":
            g = Recall()
        elif name == "rest":
            g = RestGoal()
        elif name == "wait":
            g = Wait(rest[0] if rest else 5)
        else:
            return {"ok": False, "error": f"unknown goal {name}"}
        self.set_goal(g)
        return {"ok": True, "goal": g.describe()}

    # --- the situation report ------------------------------------------------

    def report(self, rows=11, cols=33):
        w = self.w
        ind = w.ind
        lines = []
        stats = " ".join(f"{s}:{v[0] if v[0] <= 18 else '18/%02d' % (v[0] - 18)}"
                         for s, v in zip(("STR", "INT", "WIS", "DEX", "CON", "CHR"),
                                         (ind.get(f"stat{i}", [0]) for i in range(6))))
        lines.append(f"{ind.get('hist_name_', '?')} the {ind.get('race_', '?')} {ind.get('class_', '?')}, "
                     f"level {ind.get('level', ['?'])[0]}, HP {w.hp[0]}/{w.hp[1]}, "
                     f"{'Town' if not w.depth else str(w.depth_ft) + ' ft'}, gold {ind.get('gold', [0])[0]}, "
                     f"blows {ind.get('skills2', ['?'])[0]}, speed {ind.get('speed', [0])[0]}")
        cond = [k for k in ("blind", "confused", "afraid", "poisoned", "cut", "stun") if w.flag(k)]
        hunger = {0: "Weak", 1: "Weak", 2: "Hungry", 3: "Fed", 4: "Full", 5: "Gorged"}.get(w.hunger, w.hunger)
        lines.append(f"{stats}  | {hunger}" + (f" | {', '.join(cond)}" if cond else "")
                     + (" | resting" if w.resting else ""))
        lines.append(f"Standing on: {w.standing_on or 'floor/unknown'}"
                     f"{' (arrived by ' + w.arrived_by + ')' if w.arrived_by else ''}"
                     f" | goal: {self.goal.describe() if self.goal else 'none (idle)'}")
        lines.append("Equipment: " + "; ".join(i["name"] for i in w.items(equip=True)))
        lines.append("Pack: " + "; ".join(f"{chr(97 + i['item'])}) {i['name']}" for i in w.items()))
        if w.rows and w.pos:
            y0, x0 = w.pos
            lines.append(f"Map (you are @ at {y0},{x0}; rows {max(0, y0 - rows)}-{y0 + rows}):")
            for y in range(max(0, y0 - rows), min(len(w.rows), y0 + rows + 1)):
                seg = w.rows[y][max(0, x0 - cols):x0 + cols + 1]
                if seg.strip():
                    lines.append("  " + seg.rstrip())
        if w.monsters:
            seen = {}
            for y, x, r in w.monsters:
                seen.setdefault(r.name, []).append((y, x, r))
            lines.append("Monsters in view: " + "; ".join(
                f"{n} x{len(v)} (lvl {v[0][2].level}{', UNIQUE' if 'UNIQUE' in v[0][2].flags else ''}) "
                f"nearest {min(w.dist(m[:2]) for m in v)} away" for n, v in seen.items()))
        else:
            lines.append("Monsters in view: none")
        lines.append("Items seen: " + ("; ".join(l.strip() for l in w.itemlist) if w.itemlist else "?"))
        stairs = w.find("<>")
        if stairs:
            near = sorted(stairs, key=w.dist)[:4]
            lines.append("Known stairs: " + ", ".join(f"{w.memory[p]} at {p[0]},{p[1]} ({w.dist(p)} away)"
                                                     for p in near))
        if self.news:
            lines.append("Since last report: " + " | ".join(
                f"{time.strftime('%H:%M:%S', time.localtime(e['t']))} {e['what']}: {e['detail']}" for e in self.news))
            self.news = []
        lines.append("Recent messages: " + " | ".join(w.recent(30)[-12:]))
        lines.append("Orders: " + ", ".join(f"{k}={v}" for k, v in self.orders.items()))
        return "\n".join(lines)


# --------------------------------------------------------------------------
# control socket
# --------------------------------------------------------------------------

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        pilot = self.server.pilot
        line = self.rfile.readline()
        if not line:
            return
        req = json.loads(line)
        if req.get("cmd") == "wait-attention":
            timeout = float(req.get("timeout", 600))
            end = time.time() + timeout
            with pilot.att_cond:
                while not pilot.attention and time.time() < end and pilot.running:
                    pilot.att_cond.wait(min(1.0, max(0.01, end - time.time())))
                evs, pilot.attention = pilot.attention, []
            pilot.last_agent = time.time()
            out = {"ok": True, "events": evs}
            if evs:
                reply = queue.Queue()
                pilot.requests.put(({"cmd": "status"}, reply))
                try:
                    out["report"] = reply.get(timeout=10)["report"]
                except queue.Empty:
                    pass
        else:
            reply = queue.Queue()
            pilot.requests.put((req, reply))
            try:
                out = reply.get(timeout=30)
            except queue.Empty:
                out = {"ok": False, "error": "pilot busy"}
        self.wfile.write((json.dumps(out) + "\n").encode())


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main():
    repo = os.path.abspath(os.path.join(HERE, "..", ".."))
    runs = os.path.abspath(os.path.join(repo, "..", "runs"))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--nick", required=True)
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=18346)
    ap.add_argument("--passfile")
    ap.add_argument("--config")
    ap.add_argument("--rundir", help="default runs/pilot/<nick>")
    ap.add_argument("--client", default=os.path.join(repo, "mangclient"))
    ap.add_argument("--libdir", default=os.path.join(repo, "lib"))
    ap.add_argument("--pktlog")
    args = ap.parse_args()

    nick = args.nick
    priv = os.path.join(runs, "private")
    rundir = args.rundir or os.path.join(runs, "pilot", nick.lower())
    os.makedirs(rundir, exist_ok=True)
    visuals = os.path.join(rundir, "visuals.txt")
    glyphs.write_visuals(visuals, glyphs.assign(glyphs.load_races()))
    evlog = open(os.path.join(rundir, "events.jsonl"), "a", buffering=1)
    client = MangClient(args.client, args.libdir, nick,
                        args.passfile or os.path.join(priv, nick.lower() + ".pass"),
                        args.host, args.port, config=args.config or os.path.join(priv, nick.lower() + ".mangrc"),
                        cwd=repo, pktlog=args.pktlog, extra_args=["--visuals", visuals])
    say = lambda *a: print(time.strftime("%H:%M:%S"), *a, file=sys.stderr, flush=True)
    try:
        ready = client.wait_ready()
        say(f"in the game as {nick}: {ready}")
        pilot = Pilot(client, rundir, say=say)
        orig = pilot.w._on_event
        bulky = {"map", "status", "inven", "options", "commands"}   # query replies
        pilot.w.c.log = lambda ev: (orig(ev), ev.get("ev") in bulky or evlog.write(json.dumps(ev) + "\n"))
        for opt in ("avoid_other", "stack_force_costs"):
            client.send(f"option {opt} yes")
        sock = os.path.join(rundir, "ctl.sock")
        if os.path.exists(sock):
            os.unlink(sock)
        srv = Server(sock, Handler)
        srv.pilot = pilot
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        say(f"control socket {sock}")
        pilot.notify("started", f"in the game at {pilot.w.depth} (depth)")
        while pilot.running:
            pilot.tick()
            client.collect(0.05)          # drain the client's own queue; paces the loop
        say("pilot stopping")
    except ClientExited as e:
        say(f"client exited: {e}")
        sys.exit(1)
    finally:
        client.quit()


if __name__ == "__main__":
    main()
