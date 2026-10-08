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
import collections
import csv
import math
import json
import os
import queue
import random
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
from mover import Mover, direction, passable, plan, MAX_HGT, MAX_WID   # noqa: E402

TV_SCROLL, TV_POTION, TV_FOOD, TV_FLASK, TV_LITE = 70, 75, 80, 77, 39
CURE_POTIONS = ("Cure Critical Wounds", "Cure Serious Wounds", "Cure Light Wounds", "Healing")
# HP each potion heals (server use-obj.c:483-540; CSW 20-24, CCW 25-29). Longest
# names first, so "*Healing*" isn't read as "Healing".
HEALS = (("*Healing*", 1200), ("Cure Critical Wounds", 25), ("Cure Serious Wounds", 20),
         ("Cure Light Wounds", 15), ("Healing", 300), ("of Life", 5000))


# Items whose use the pilot verifies and resends (not unknown scrolls: a
# resend could read a second one)
USE_VERIFY = ("Phase Door", "Word of Recall", "Teleport", "Cure Light Wounds", "Cure Serious Wounds",
              "Cure Critical Wounds", "Healing", "Boldness", "Heroism", "Berserk", "Cure Poison",
              "Neutralize Poison")


# Blows per round, as the server computes them (xtra1.c ~2950, tables.c;
# warrior p_class A:6:30:5). Stat values as the indicators send them: 3..18,
# then 18 + xx for 18/xx.
ADJ_STR_BLOW = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 20, 30, 40, 50, 60, 70, 80, 90, 100,
                110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230, 240]
ADJ_DEX_BLOW = [0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 4, 4, 5, 6, 7, 8, 9, 10,
                11, 12, 14, 16, 18, 20, 20, 20]
ADJ_STR_HOLD = [4, 5, 6, 7, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 30, 35, 40, 45, 50, 55, 60, 65,
                70, 80, 80, 80, 80, 80, 90, 90, 90, 90, 90, 100, 100, 100]
BLOWS_TABLE = [
    [1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3], [1, 1, 1, 1, 2, 2, 3, 3, 3, 4, 4, 4],
    [1, 1, 2, 2, 3, 3, 4, 4, 4, 5, 5, 5], [1, 2, 2, 3, 3, 4, 4, 4, 5, 5, 5, 5],
    [1, 2, 2, 3, 3, 4, 4, 5, 5, 5, 5, 5], [2, 2, 3, 3, 4, 4, 5, 5, 5, 5, 5, 6],
    [2, 2, 3, 3, 4, 4, 5, 5, 5, 5, 5, 6], [2, 3, 3, 4, 4, 4, 5, 5, 5, 5, 5, 6],
    [3, 3, 3, 4, 4, 4, 5, 5, 5, 5, 6, 6], [3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6],
    [3, 3, 4, 4, 4, 4, 5, 5, 5, 6, 6, 6], [3, 3, 4, 4, 4, 4, 5, 5, 6, 6, 6, 6]]
WARRIOR = (6, 30, 5)          # max_attacks, min_weight (tenth lb), att_multiply
TV_WEAPONS = (20, 21, 22, 23)


def stat_index(v):
    return max(0, min(37, v - 3 if v <= 18 else 15 + (v - 18) // 10))


def weapon_blows(weight, str_v, dex_v, cls=WARRIOR):
    """Blows per round with a weapon of `weight` tenth-pounds."""
    si, di = stat_index(str_v), stat_index(dex_v)
    if weight // 10 > ADJ_STR_HOLD[si]:
        return 1                                   # too heavy to wield properly
    div = max(weight, cls[1])
    s_i = min(11, ADJ_STR_BLOW[si] * cls[2] // div)
    d_i = min(11, ADJ_DEX_BLOW[di])
    return max(1, min(cls[0], BLOWS_TABLE[s_i][d_i]))


def weapon_damage(name, blows):
    """Average damage per round: (dice average + to-dam) x blows."""
    m = re.search(r"\((\d+)d(\d+)\)", name)
    if not m:
        return 0.0
    dice = int(m.group(1)) * (int(m.group(2)) + 1) / 2
    b = re.search(r"\([+-]\d+,([+-]\d+)\)", name)
    return (dice + (int(b.group(1)) if b else 0)) * blows


def flavour_key(name):
    """'2 Puce Potions {tried}' -> 'Puce Potion' (the flavour table's key)."""
    n = re.sub(r"\{.*?\}", "", name).strip()
    n = re.sub(r"^(a|an|the|\d+) ", "", n)
    n = re.sub(r"(Potion|Scroll|Wand|Staff|Rod|Ring|Amulet|Mushroom)s\b", r"\1", n)
    return re.sub(r"\s*\(.*?\)", "", n).strip()


def kind_key(name):
    """'a Potion of Weakness' / '3 Wands of Magic Missile (10 charges)' -> 'Potion of Weakness'."""
    n = re.sub(r"\{.*?\}|\(.*?\)|\[.*?\]", "", name).strip()
    n = re.sub(r"^(a|an|\d+) ", "", n)
    n = re.sub(r"(Potion|Scroll|Wand|Staff|Rod|Ring|Amulet|Mushroom)s\b", r"\1", n)
    return re.sub(r"\s+[-+]\d+.*$", "", n).strip()


def one_of(name):
    """'2 Potions of Boldness' -> 'a Potion of Boldness' (what one use takes;
    mission 6's news said 'quaffed 2 Potions' when 1 was left)."""
    return re.sub(r"^\d+ (\S+?)s of ", r"a \1 of ", name)


def recall_level(name):
    """The dungeon level a Word of Recall read in town takes us to, from its
    inscription, as the server reads it (spells2.c:1153): the *last* @R wins;
    a number divisible by 50 is feet, anything else a level number. None when
    there's no valid @R (the server then uses the deepest level ever reached,
    and so does a value deeper than that). The forum: a typo ('@r') recalled
    a player onto Morgoth."""
    level = None
    for m in re.finditer(r"@R(-?\d*)", name):
        n = int(m.group(1)) if m.group(1) not in ("", "-") else 0
        level = n // 50 if n % 50 == 0 else n
    return level or None


def choke_tier(mem, pos):
    """How well a square limits a pack's access (lower is better), None for
    open ground. Corridors here are two wide (WIDE_CORRIDORS; doors come in
    pairs; Advisor memo A5), so a square with <= 2 open neighbours (dead end,
    one-wide tunnel) is rare: 0 = that, 1 = <= 3 (a corner or the end of a
    two-wide corridor), 2 = a straight two-wide corridor (<= 5 neighbours and
    <= 10 open squares in the 5x5 around; a room's edge has 14)."""
    y, x = pos
    def is_open(p):
        return mem.get(p, " ") not in "#%*: "
    near = sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy or dx) and is_open((y + dy, x + dx)))
    if near <= 2:
        return 0
    if near <= 3:
        return 1
    area = sum(1 for dy in range(-2, 3) for dx in range(-2, 3) if (dy or dx) and is_open((y + dy, x + dx)))
    return 2 if near <= 5 and area <= 10 else None


def heal_of(name):
    return next((hp for n, hp in HEALS if n in name), 0)

# What each potion cures (Advisor memo, Erratum: server use-obj.c:483-545).
# Only CCW and better cure stun and poison; CLW only reduces confusion.
# Cheapest first.
STATUS_CURES = {
    "stun": ("Cure Critical Wounds", "Healing", "*Healing*", "of Life"),
    "poisoned": ("Cure Poison", "Neutralize Poison", "Cure Critical Wounds", "Healing", "*Healing*", "of Life"),
    "confused": ("Cure Serious Wounds", "Cure Critical Wounds", "Healing", "*Healing*", "of Life"),
    "blind": ("Cure Light Wounds", "Cure Serious Wounds", "Cure Critical Wounds", "Healing", "*Healing*",
              "of Life"),
}

DEFAULT_ORDERS = {
    "flee_hp": 0.5,        # emergency below this HP fraction
    "think_hp": 0.65,      # tell the agent below this, while fighting
    "rest_below": 0.7,     # rest when nothing is in view and HP is below this
    "rest_to": 0.95,
    "arrival_pack": 4,     # this many monsters in view on arrival -> leave by the stairs
    "danger_level": 6,     # a monster this many levels above ours in view -> leave/avoid
    "free_action": "no",   # yes once the character has Free Action: paralysers stop counting as danger
    "resist_blind": "no",  # yes once worn: monsters that blind with their blows stop counting as danger
    "resist_conf": "no",   # the same for confusing blows
    "unseen_hp": "on",     # off: don't treat HP loss with nothing in view as an unseen attacker
    "idle_recall_s": 600,  # no goal and no agent contact for this long -> recall to town
                           # (long enough for a slow agent turn; 180 s fired mid-thought)
    "pickup": "all",       # all | none
    "stop_on": "unique,danger",  # what makes a dive stop and ask (also: items, pillared)
    "pillared": "explore",       # dive: explore pillared rooms for a '>' by itself (or: ask, ignore)
    "loot_radius": 10,           # dive: fetch items seen within this many squares (0 = off)
    "choke": "on",               # meet packs in a corridor, not in the open (the user's advice)
    "autodestroy": "worthless,cursed",   # pseudo-ID feelings whose items get destroyed (add 'average')
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
        self.arrived_t = None

    def tick(self, p):
        w = p.w
        if self.arrived_t:
            # An item underfoot is picked up ~0.6 s after arriving: report after
            # that, or the Navigator sees it still on the floor (mission 5)
            if any(ts > self.arrived_t and t.startswith(("You have ", "You have no room")) for ts, t in w.messages) \
                    or time.time() - self.arrived_t > 1.5:
                w.inven_dirty = True
                return ("done", None)
            return None
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
            if any(time.time() - ts < 1.0 and t.startswith("You see ") and "no items" not in t
                   for ts, t in w.messages):
                self.arrived_t = time.time()
                return None
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
        self.loot = {}

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
        # (only stairs we can reach: a Phase Door once left us in a pocket cut
        # off from a known '<', and this ended at once -- the Advisor's mission 9
        # replay)
        if self.until == "stairs" and w.find(">") and plan(w, w.find(">")):
            return ("done", "stairs down seen")
        if self.until == "upstairs" and w.find("<") and plan(w, w.find("<")):
            return ("done", "stairs up seen")
        if p.level_seen != w.level_t:
            p.level_seen = w.level_t
            p.unreachable = set()
            p.visited = set()
        if not p.mover.active or self.loot.get("looting"):
            if p.loot_step(self.loot):
                return None
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
        # On a climb, scumming by a '>' costs two level changes and goes one
        # deeper: only a close one, never below max_depth (mission 11: at 50 ft
        # on the way to town it walked 15 squares to a '>' and went to 100 ft)
        md = int(p.orders.get("max_depth", 0))
        climbing = want == "<"
        scum_ok = not climbing or not md or w.depth_ft + 50 <= md
        # Scum: back the way we came on the staircase we're on, then again
        if w.standing_on == other and scum_ok:
            return self._stairs(p, other)
        # No stairs under us: explore until we see some (either kind)
        self.expire_bad(w)
        ups = [u for u in w.find(other) if (w.level_t, u) not in self.bad_stairs
               and scum_ok and (not climbing or w.dist(u) <= 8)]
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
            if self.prev is not None:
                p.resume_after = self.prev
            return ("done", f"healed; back up from {w.depth_ft} ft (max_depth {md})")
        if self.prev is not None:
            p.resume_after = self.prev
        return ("done", f"healed at {w.depth_ft} ft" + (f"; resuming '{self.prev.describe()}'" if self.prev else ""))


class Flee(Goal):
    """Get away from something too dangerous: to the nearest known stairs and
    take them."""

    def __init__(self, why):
        self.name = f"flee ({why})"
        self.started = False
        self.took = None

    def tick(self, p):
        w = p.w
        if self.took:
            # Report once the new level is in (the report showed the old depth
            # and stairs right after "left by the stairs", mission 4)
            if w.level_t != self.took[0]:
                return ("done", f"left by the stairs; now at {w.depth_ft} ft")
            if time.time() - self.took[1] > 5:
                return ("done", "took the stairs, but no level change seen")
            if time.time() - self.took[1] > 1.5 and len(self.took) == 2 and w.standing_on in ("<", ">"):
                p.take_stairs(w.standing_on)      # a stairs command right after arriving can be ignored
                self.took = self.took + (True,)
            return None
        # At or below max_depth, go up if an up staircase is known (mission 4:
        # flights kept taking '>' past max_depth)
        md = int(p.orders.get("max_depth", 0))
        ok = "<" if md and w.depth_ft >= md and w.find("<") else "<>"
        if w.standing_on and w.standing_on in ok:     # (None in "<>" crashed a flee, mission 6)
            p.take_stairs(w.standing_on)
            self.took = (w.level_t, time.time())
            return None
        stairs = w.find(ok)
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
        self.inscribed = 0           # tries at inscribing @R
        self.inscribe_t = 0.0
        self.light_t = 0.0

    def tick(self, p):
        w = p.w
        if self.start_depth is None:
            self.start_depth = w.depth
        # Done only when the recall itself happened ("yanked" clears the pending
        # flag): taking stairs while it's pending is not arriving (mission 13)
        if self.read_t and w.depth != self.start_depth and not w.recall_pending:
            return ("done", f"arrived at {w.depth_ft} ft")
        if self.read_t is None:
            it = next((i for i in w.items(tval=TV_SCROLL) if "Word of Recall" in i["name"]), None)
            if not it:
                return ("failed", "no Word of Recall")
            # From town, recall goes to the deepest level ever reached -- which
            # can be below max_depth (it took Dive03 back to 1000 ft, where it had
            # died). Inscribe @R<feet> first: the recall depth (inscription guide).
            # Check what the server will read from it, not a substring
            # ("@R7500" contains "@R750"; a later @R overrides an earlier one).
            md = int(p.orders.get("max_depth", 0)) // 50 * 50
            if w.depth == 0 and md and recall_level(it["name"]) != md // 50:
                if time.time() - self.inscribe_t < 2.5:
                    return None           # (wait for the pack to show the new inscription)
                if self.inscribed >= 3:
                    return ("failed", f"couldn't inscribe @R{md} on the Word of Recall "
                                      f"(it reads '{it['name']}'): not reading it")
                self.inscribed += 1
                self.inscribe_t = time.time()
                p.cmd(f"custom {{ item={it['item']} entry=@R{md}", f"recall depth {md} ft", hold=1.0)
                w.inven_dirty = True
                return None
            # No light, no reading (mission 13: at night in town the light was off
            # for idling, and the read failed with "You have no light to read by")
            if not any(i["tval"] == TV_LITE for i in w.items(equip=True)):
                lite = next((i for i in w.items(tval=TV_LITE) if "0 turns" not in i["name"]), None)
                if lite and time.time() - self.light_t > 2:
                    self.light_t = time.time()
                    p.light_t = time.time() + 30      # (town_light: don't take it off again)
                    p.cmd(f"custom w item={lite['item']}", "light on to read Word of Recall", hold=0.8)
                    return None
            if p.recall_started(time.time()):
                # Already under way (e.g. the last-resort recall): a second read would cancel it
                p.log("note", text="recall already under way: not reading another")
                self.read_t = time.time()
                return None
            p.cmd(f"custom r item={it['item']}", f"read {it['name']}")
            self.read_t = p.recall_t = time.time()
            return None
        if time.time() - self.read_t > (120 if w.recall_pending else 60):
            # say why, if the game did (e.g. "You have no light to read by.")
            why = next((t for ts, t in reversed(w.messages) if ts >= self.read_t and t.startswith(
                ("You have no light", "You can't see", "You are too confused", "You cannot read",
                 "A tension leaves"))), None)
            return ("failed", "recall didn't happen" + (f": the game said '{why}'" if why else ""))
        return None


class Resurrect(Goal):
    """A ghost floats up: '<' works anywhere for a ghost (cmd2.c:37), one
    level per press; in town, walking onto the Temple's entrance ('4')
    resurrects (cmd1.c:2047). It costs half the experience for good."""
    name = "resurrect"

    def __init__(self):
        self.up_t = 0.0

    def tick(self, p):
        w = p.w
        if not w.ghost:
            return ("done", "resurrected")
        if w.depth:
            # (a stairs command too soon after arriving is ignored: retry)
            if time.time() - w.level_t > 1.2 and time.time() - self.up_t > 1.5:
                self.up_t = time.time()
                p.take_stairs("<")
            return None
        door = w.find("4")
        if not door:
            return ("failed", "the Temple (4) isn't on the map")
        if w.dist(door[0]) == 1:
            p.cmd(f"walk {direction(w.pos, door[0])}", "walk onto the Temple entrance", hold=1.0)
            return None
        if not p.mover.active and not p.mover.go([door[0]]):
            return ("failed", "can't reach the Temple")
        p.mover.tick()
        return None


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
            if time.time() - self.step_t > 0.8:
                self.step_t = time.time()
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
        self.target_gold, self.end = int(gold), time.time() + 60 * float(minutes)
        self.name = f"townfarm to {self.target_gold} gold"
        self.light_t = self.wander_t = 0.0
        self.chasing = None
        self.sweep = []

    def tick(self, p):
        w = p.w
        if w.depth != 0:
            return ("failed", "townfarm is for the town")
        gold = w.ind.get("gold", [0])[0]
        if gold >= self.target_gold:
            return ("done", f"{gold} gold")
        if time.time() > self.end:
            return ("done", f"time's up at {gold} gold")
        # light, to see them at night (a dead or dying torch counts as none:
        # mission 14 stood 2 min in the dark with a lantern in the pack)
        worn = next((i for i in w.items(equip=True) if i["tval"] == TV_LITE), None)
        wt = re.search(r"with (\d+) turns", worn["name"]) if worn else None
        if (not worn or (wt and int(wt.group(1)) < 100)) and time.time() - self.light_t > 5:
            def left(i):
                t = re.search(r"with (\d+) turns", i["name"])
                return int(t.group(1)) if t else (1 if "Lantern" in i["name"] else 0)
            lite = max((i for i in w.items(tval=TV_LITE) if left(i) > 0), key=left, default=None)
            if lite:
                self.light_t = time.time()
                p.light_t = time.time() + 30
                p.cmd(f"custom w item={lite['item']}", "townfarm: light on", hold=0.8)
                return None
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
            y, x, r = min(prey, key=lambda m: w.dist(m[:2]))
            if w.dist((y, x)) <= 1:
                p.mover.stop()
                return None                      # adjacent: auto-retaliate fights
            near = [(y + dy, x + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
            if not p.mover.active or self.chasing != (y, x):
                self.chasing = (y, x)
                p.mover.go(near)
            p.mover.tick()
            return None
        # nobody worth it in view: sweep the town in a zig-zag (the user: few
        # townspeople are visible from the streets by the shops), rows ~7 apart
        st = p.mover.tick() if p.mover.active else "idle"
        if st in ("arrived", "idle", "stuck") or time.time() - self.wander_t > 40:
            self.wander_t = time.time()
            if not self.sweep:
                self.sweep = self.sweep_points(w)
            while self.sweep:
                wy, wx = self.sweep.pop(0)
                cand = [q for q, ch in w.memory.items() if ch == "." and abs(q[0] - wy) <= 3
                        and abs(q[1] - wx) <= 6 and w.dist(q) > 4]
                if cand and p.mover.go([min(cand, key=lambda q: abs(q[0] - wy) + abs(q[1] - wx))]):
                    break
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
                m = re.match(r"You sold (.+?) for \d+ gold", verdict or "")
                if m and getattr(self, "selling_flavour", None):
                    p.learn_flavour(self.selling_flavour, kind_key(m.group(1)), "sold in a shop")
                    self.selling_flavour = None
                self.pending = None
                w.status_t = 0            # re-read gold before the next purchase
                w.inven_dirty = True
                return None
            if not w.store:
                return ("failed", "thrown out of the store")
            if self.list_stock:
                # (mission 8 guessed names one shop trip at a time)
                self.list_stock = False
                self.done_log.append("stock: " + "; ".join(
                    f"{i['name']} {i['price']}" for i in w.store["items"]))
            if self.sells:
                idx, n = self.sells.pop(0)
                force = isinstance(idx, str) and idx.startswith("!")
                if force:
                    idx = idx[1:]
                if isinstance(idx, str):
                    # By name, resolved now (identifying items re-sorts the pack)
                    it = next((i for i in w.items() if idx.lower() in i["name"].lower()), None)
                    if not it:
                        self.done_log.append(f"no {idx} to sell")
                        return None
                    idx = it["item"]
                    w.inven_dirty = True
                else:
                    it = next((i for i in w.items() if i["item"] == idx), None)
                why_not = p.unknown_sell_refusal(it, n) if it and not force else None
                if why_not:
                    # (mission 12 sold 2 Potions of Speed and 2 of Heroism for 8 each)
                    self.done_log.append(f"NOT sold ({why_not}; sell !NAME to force): {it['name']}")
                    return None
                # selling an unknown flavour identifies it (store.c): learn the kind
                self.selling_flavour = flavour_key(it["name"]) if it and p.unknown_flavour(it) else None
                if it and not force and p.probably_special(it["name"]):
                    # Wormtongue's armour was sold unseen for 17 gold: it was Soft
                    # Studded Leather of Resistance (buyback 19834)
                    self.done_log.append(f"NOT sold (probably special, inspect it first; sell !NAME to force): "
                                         f"{it['name']}")
                    return None
                p.c.send("confirm yes")
                p.cmd(f"custom s store item={idx} value={n}", f"sell {idx}x{n}", hold=0.2)
                self.last = f"sell {chr(97 + idx)} x{n}"
                self.pending = time.time()
                return None
            if self.buys:
                name, n, cap = (self.buys.pop(0) + (None,))[:3]
                # The cheapest match: the first one can be an expensive enchanted
                # piece (bought a Cloak [1,+4] for 592 instead of a plain one)
                matches = [i for i in w.store["items"] if name.lower() in i["name"].lower()]
                it = min(matches, key=lambda i: i["price"]) if matches else None
                if not it:
                    self.done_log.append(f"no {name} in stock")
                    return None
                if cap is not None and it["price"] > cap:
                    # (mission 8: 'buy To-Dam:3' spent 302 of 366 gold)
                    self.done_log.append(f"NOT bought: {it['name']} costs {it['price']}, over your cap {cap}")
                    return None
                gold = w.ind.get("gold", [0])[0]
                n = min(n, it["number"], gold // max(1, it["price"]))
                if n <= 0:
                    self.done_log.append(f"can't afford {it['name']} ({it['price']} each, the cheapest in stock)")
                    return None
                p.cmd(f"custom p store item={it['slot']} value={n} entry={it['price'] * n}",
                      f"buy {it['name']} x{n}", hold=0.2)
                self.last = f"buy {it['name']} x{n} at {it['price']} each"
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
        self.recent_acts = collections.deque(maxlen=40)   # for the observer's note snapshots
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
        self.emerg_times = []
        self.loop_warned = 0.0
        self.retreating = False
        self.fearers_seen = set()
        self.unique_names = None
        self.fear_t = 0.0
        self.skipped_items = set()     # (level, square) of junk we chose to leave
        self.resume_after = None
        self.autodestroy_t = 0.0
        self.parking = None
        self.light_t = self.light_warned = 0.0
        # Where the town's '>' is (remembered across runs: the town never changes)
        self.town_file = os.path.join(os.path.dirname(rundir.rstrip("/")), "town.json")
        # Server-wide flavour table and this character's deepest level
        self.flavour_file = os.path.join(os.path.dirname(rundir.rstrip("/")), "..", "flavours.json")
        self.load_flavours()
        self.deepest_file = os.path.join(rundir, "deepest.json")
        try:
            with open(self.deepest_file) as f:
                self.deepest_ft = json.load(f)["ft"]
        except (OSError, ValueError, KeyError):
            self.deepest_ft = 0
        self.town_stairs = None
        if os.path.exists(self.town_file):
            with open(self.town_file) as f:
                self.town_stairs = json.load(f).get("stairs")
        self.recall_t = 0.0
        self.sidestep_t = 0.0
        self.unseen_warned = self.heard_warned = 0.0
        self.pos_hist = collections.deque()
        self.gaps_logged = set()
        self.gap_since = {}
        self.stuck_t = 0.0
        self.flee_t = 0.0
        self.wear_queue = False
        self.breeder_level = None
        self.choke_state = None
        self.choke_t = self.choke_done_t = 0.0
        self.seen_drained = None
        self.dead = False
        self.pending_use = None               # a read/quaff to verify (verify_use)
        self.held_t = 0.0
        self.expects = []                     # actions waiting for their effect (verify_effects)
        self.news_wait_t = 0.0                # news shown by wait reports up to here
        self.audit_t, self.audit_runs, self.audit_counts = 0.0, 0, {}
        self.wild_trail, self.trail_level = [], None
        self.eat_t = 0.0
        self.flavour_watch = None
        self.weapons_t, self.weapon_tips = 0.0, set()
        self.found_t = time.time()
        self.effect_failures = 0
        self.redraw_t, self.redraw_level = 0.0, None
        self.group_warned = None
        self.mons_log_t = 0.0
        self.drains_here = (None, 0)          # (level, stat drains seen on it)
        self.still_goals = (None, set())      # (level, mover goals) before a stationary-monster fight
        self.still_fighting = None            # (level, position) of the stationary monster we're killing
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
        if kind in ("act", "attention", "goal", "goal_done", "goal_failed", "note"):
            self.recent_acts.append({"t": rec["t"], "kind": kind,
                                     "what": kw.get("cmd") or kw.get("what") or kw.get("goal") or kw.get("text"),
                                     "why": kw.get("why") or kw.get("detail")})
        self.dlog.write(json.dumps(rec) + "\n")

    # Events that don't need a decision (the pilot already acted): shown in
    # the next report instead of waking the agent
    NEWS = {"danger_avoided", "started", "tactic", "resumed"}

    def notify(self, what, detail=None, news=False):
        if what in ("emergency", "tactic") and time.time() - self.held_t < 0.05 and detail and \
                any(k in detail for k in ("quaffed", "read ", "phase")):
            # the action this reports was held, not sent (mission 10 reported 3
            # CLW quaffs with 1 CLW in the pack)
            self.log("note", text=f"not reported (held): {detail}")
            return
        ev = {"t": round(time.time(), 3), "what": what, "detail": detail,
              "goal": self.goal.describe() if self.goal else None}
        if what == "emergency":
            self.emerg_times.append(time.time())
        self.log("attention", what=what, detail=detail)
        if what in self.NEWS or news:
            self.news.append(ev)
            self.news = self.news[-20:]
            return
        with self.att_cond:
            self.attention.append(ev)
            self.att_cond.notify_all()

    # --- low-level actions ---------------------------------------------------

    def cmd(self, line, why, hold=0.4):
        # One read/quaff of ours at a time: until the last one is confirmed its
        # stack can still shrink and shift the pack letters (mission 9 read
        # "item=7" as Word of Recall 5 s after a potion stack ran out, then
        # read the real one as "item=5")
        if self.pending_use and re.match(r"custom [rq] item=", line) and not why.startswith("agent:"):
            self.log("note", text=f"held (a read/quaff is still unconfirmed): {why}")
            self.busy_until = time.time() + 0.3
            self.held_t = time.time()     # notify() drops the caller's "quaffed ..." report
            # (callers set their rate-limit clock before calling: undo it, so
            # this is retried as soon as the last use is confirmed)
            if "recall" in why.lower():
                self.recall_t = 0.0
            elif "phase" in why.lower():
                self.phase_t = 0.0
            else:
                self.cure_t = 0.0
            return
        self.c.send(line)
        self.last_action = (time.time(), line, why)
        self.busy_until = time.time() + hold
        self.log("act", cmd=line, why=why)
        self.expect_effect(line, why)
        if re.match(r"custom [qruazE] item=", line):
            self.watch_flavours()
        # Verify the pilot's own escapes and cures by their effect (post-mortem
        # memo §4.2: both Dive03 deaths were escapes that never ran)
        m = re.match(r"custom [rq] item=(\d+)$", line)
        if m and not why.startswith("agent:") and self.w.in_dungeon:
            it = next((i for i in self.w.items() if i["item"] == int(m.group(1))), None)
            core = next((c for c in USE_VERIFY if it and c in it["name"]), None)
            if core:
                self.pending_use = {"line": line, "t": time.time(), "core": core, "tries": 0, "why": why}
                self.mover.hold_clear_until = time.time() + 3.0

    # Commands whose effect shows in the pack, the equipment or the level
    # (the game-state survey, rule 3: an action is done when its signal comes)
    EFFECTS = (
        (re.compile(r"custom [wt] item="), "equip"),
        (re.compile(r"custom [kdEF] item=|eat \d|custom ,"), "pack"),
        (re.compile(r"custom [<>]$"), "level"),
    )

    def effect_sig(self, kind):
        w = self.w
        if kind == "level":
            return w.level_t
        return tuple((i["name"], i["number"]) for i in w.items(equip=(kind == "equip")))

    def expect_effect(self, line, why):
        if why.startswith("agent:"):
            return                          # the agent gets its own answer (do_request)
        for rx, kind in self.EFFECTS:
            if rx.match(line):
                self.expects.append({"kind": kind, "t": time.time(), "why": why,
                                     "sig": self.effect_sig(kind)})
                return

    def pack_kinds(self):
        """{(tval, name)} of the pack, names without counts/inscriptions."""
        return {(i["tval"], kind_key(i["name"]) if " of " in i["name"] else flavour_key(i["name"]))
                for i in self.w.items() if i["tval"] in self.FLAVOURED or
                (i["tval"] == TV_FOOD and "Mushroom" in i["name"])}

    def watch_flavours(self):
        self.flavour_watch = {"t": time.time(), "before": self.pack_kinds(),
                              "unknown": {(i["tval"], flavour_key(i["name"])) for i in self.w.items()
                                          if self.unknown_flavour(i)}}

    def learn_flavours_tick(self, now):
        """After a read/quaff/use/aim/zap (incl. Identify): an unknown flavour
        that disappeared while a known kind of the same type appeared is that
        kind (the Advisor's flavour-messages memo: names drop the flavour once
        it's aware, so diff the pack)."""
        fw = self.flavour_watch
        if not fw or now - fw["t"] < 1.0:
            return
        self.flavour_watch = None
        after = self.pack_kinds()
        gone = {k for k in fw["unknown"] if k not in after}
        new = {k for k in after - fw["before"]}
        said = [t for ts, t in self.w.messages if ts >= fw["t"] - 0.05]
        for t in said:                          # a stack used up: "You have no more Potions of X."
            m = re.match(r"You have no more (.+?)\.?$", t)
            if m and " of " in m.group(1):
                k = kind_key(m.group(1))
                tv = next((tv for tv, _ in gone), None)
                if tv is not None:
                    new.add((tv, k))
        for tv in {t for t, _ in gone}:
            g = [n for t, n in gone if t == tv]
            n = [k for t, k in new if t == tv and " of " in k]
            if len(g) == 1 and len(n) == 1:
                self.learn_flavour(g[0], n[0], "identified or used")

    def verify_effects(self):
        """Report actions whose effect never showed (3 s), instead of
        letting them pass as done."""
        now = time.time()
        keep = []
        for e in self.expects:
            if self.effect_sig(e["kind"]) != e["sig"]:
                continue                    # confirmed
            if now - e["t"] < 3.0:
                keep.append(e)
                continue
            self.log("note", text=f"effect_failed ({e['kind']} unchanged after 3 s): {e['why']}")
            self.effect_failures += 1
            if e["kind"] != "level":      # (stairs are retried by the goals themselves)
                self.notify("tactic", f"no effect seen: {e['why']}")
        self.expects = keep

    def audit_tick(self, now):
        """The state audit (the game-state survey, 'measurement'): every 30 s
        compare the pilot's model with a fresh query, log each difference by
        field ('audit' records in decisions.jsonl), count them, and resync
        (redraw) when anything differs; in town also every 2 minutes."""
        w = self.w
        if w.depth == 0 and now - self.redraw_t > 120:
            w.need_redraw = True
        if now - self.audit_t < 30 or w.store or now < self.busy_until:
            return
        self.audit_t = now
        model = {"pack": [(i["name"], i["number"]) for i in w.inven if not i["equip"]],
                 "equip": [i["name"] for i in w.inven if i["equip"]],
                 "hp": list(w.hp), "gold": w.ind.get("gold", [None])[0],
                 "depth": w.depth, "pos": w.pos, "hunger": w.hunger}
        try:
            st = self.c.status()
            inv = self.c.inven()
        except Exception:
            return
        fresh = {"pack": [(i["name"], i["number"]) for i in inv if not i["equip"]],
                 "equip": [i["name"] for i in inv if i["equip"]],
                 "hp": st["ind"].get("hp", [0, 1])[:2], "gold": st["ind"].get("gold", [None])[0],
                 "depth": st["ind"].get("depth", [None])[0],
                 "pos": (st["y"], st["x"]) if st["y"] >= 0 else w.pos,
                 "hunger": st["ind"].get("hunger", [w.hunger])[0]}
        # (hp only out of melee: in a fight it's a timing race -- the Advisor's
        # mission 13 audit memo)
        diffs = {k: (model[k], fresh[k]) for k in model if model[k] != fresh[k] and
                 not (k == "hp" and (abs(model[k][0] - fresh[k][0]) <= 3 or w.adjacent_monsters()))}
        self.audit_runs += 1
        self.log("audit_check", n=self.audit_runs, differences=len(diffs),
                 exp=st["ind"].get("exp"), clvl=w.clvl, depth_ft=w.depth_ft,   # (exp: for XP-rate studies)
                 stats={n: st["ind"].get(f"stat{i}") for i, n in enumerate(self.STAT_NAMES)},
                 blows=st["ind"].get("skills2", [None])[0], ac=st["ind"].get("armor"),
                 gold=st["ind"].get("gold", [None])[0])
        for k in diffs:
            self.audit_counts[k] = self.audit_counts.get(k, 0) + 1
        if diffs:
            self.log("audit", diffs={k: [str(a)[:200], str(b)[:200]] for k, (a, b) in diffs.items()})
            w.need_redraw = True
            w.inven, w.inven_t = inv, now          # the fresh copy wins

    def verify_use(self):
        """A pending read/quaff: done when the server says what's left ("You
        have 9 Scrolls of Phase Door (j)." / "You have no more ...") or a
        recall starts; resent (twice at most) if nothing within 2.5 s."""
        p, now = self.pending_use, time.time()
        if not p:
            return
        if self.dead or self.w.ghost:
            self.pending_use = None           # (mission 10 kept resending after death)
            return
        said = [t for ts, t in self.w.messages if ts >= p["t"] - 0.05]
        if any(t.startswith("You have") and p["core"] in t for t in said) or \
                any("The air about you becomes charged" in t for t in said):
            self.pending_use = None
            self.w.inven_dirty = True          # re-read the pack now, before the next use
            self.w.refresh()
            return
        if now - p["t"] < 2.5:
            return
        if p["tries"] >= 2 or not self.w.in_dungeon:
            self.pending_use = None
            self.notify("tactic", f"'{p['why']}' still shows no effect after 2 resends: giving up on it")
            return
        p["tries"] += 1
        p["t"] = now
        self.mover.hold_clear_until = now + 3.0
        self.c.send(p["line"])
        self.log("act", cmd=p["line"], why=f"resend (no effect seen): {p['why']}")
        self.notify("tactic", f"'{p['why']}' showed no effect: resent it")

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
            # not the square we're on, nor items the junk filter left lying (a
            # 'goto item' ended at once, standing on a junk item it wouldn't take)
            return [p for p, ch in w.memory.items() if ch not in "#%.'+<>^;:*=~ 12345678"
                    and p != w.pos and (w.level_t, p) not in self.skipped_items]
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

    def danger_why(self, r, pack_breath=0):
        """Why monster race r is too dangerous to fight now, or None."""
        lev = self.w.clvl
        hp = self.w.hp[0]
        o = self.orders
        if r.level >= lev + o["danger_level"]:
            return f"lvl {r.level}"
        if "UNIQUE" in r.flags and r.level > lev:
            return f"unique, lvl {r.level}"
        # The Advisor's danger table (memo 2026-09-27 §3): 5 = leave on sight;
        # 4 = lethal until we've outgrown it by about 8 levels
        if r.danger == 5:
            return "rated 5: leave on sight"
        if r.danger == 4 and lev < r.level + 8:
            return f"rated 4: lethal until clvl {r.level + 8}"
        # A fast unique near our level: we can't walk away from it (mission 9:
        # Bullroarer, +10, cost 93 -> 51 HP while the pilot backed away)
        sx = r.speed_x if r.speed_x is not None else max(1.0, (r.speed - 100) / 10)
        if "UNIQUE" in r.flags and sx >= 2 and r.level >= lev - 8 and r.per_turn >= max(hp, 1) / 8:
            return f"fast unique (x{sx:.0f} speed)"
        # A capital D is an ancient dragon (level 40+), always out of depth here
        if r.char == "D":
            return "ancient dragon"
        # Fast heavy melee (Azog, Beorn, the chieftains passed every other rule)
        if r.per_turn >= max(hp, 1) / 3 and "NEVER_MOVE" not in r.flags:
            return f"melee ~{r.per_turn:.0f} per turn"
        # Engage a breather only if two of its breaths can't kill us (Advisor
        # memo, Addendum 2 item 8); a pack of breathers (hounds) breathes together
        if r.max_breath and 2 * r.max_breath >= hp:
            return f"breathes up to {r.max_breath}"
        if r.max_breath and pack_breath >= hp:
            return f"its pack breathes up to {pack_breath} in all"
        # (a paralysing blow whose to-hit can't beat our armour lands only on the
        # 5% floor, e.g. a floating eye: memo §3.7; Hold spells still count)
        ac = self.w.ind.get("armor", [0])[0]
        weak_blow = "HOLD" not in r.spells and 0 < r.paralyse_blow_power <= ac * 3 / 4
        if r.paralyser and not self.has_ability("free_action") and r.level >= lev - 10 and not weak_blow:
            return "paralyses (no Free Action)"
        if "BRAIN_SMASH" in r.spells and not all(self.has_ability(k) for k in
                                                   ("free_action", "resist_blind", "resist_conf")):
            return "Brain Smash (needs Free Action + resist blindness + resist confusion)"
        # Blinding/confusing blows get no saving throw (memo §1.3). Stationary
        # ones are only stepped away from (and never fought, still_fight_tick).
        nosave = {e for e in r.no_save_blows
                  if not self.has_ability("resist_blind" if e == "BLIND" else "resist_conf")}
        if nosave and "NEVER_MOVE" not in r.flags and r.level >= lev - 10:
            return ("blinds" if "BLIND" in nosave else "confuses") + " with its blows (no save)"
        # Summons land next to us and stay after the summoner dies (memo §1.2)
        if r.summoner and r.level >= lev - 5:
            return "summons"
        return None

    def dangers(self):
        mons = self.w.monsters
        pack_breath = sum(r.max_breath for *_, r in mons)
        return [r for _, _, r in mons if self.danger_why(r, pack_breath)]

    def danger_text(self, r):
        pack_breath = sum(x.max_breath for *_, x in self.w.monsters)
        return f"{r.name} ({self.danger_why(r, pack_breath) or f'lvl {r.level}'})"

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
        if self.dead and not w.ghost and w.hp[0] > 0:
            self.dead = False                 # resurrected
        if w.ghost or w.hp[0] <= 0 and w.hp[1] > 0 and w.ind:
            if not self.dead:
                # Stay up to tell the Navigator (mission 7: the pilot exited at
                # death, and the Navigator only got "Connection refused")
                self.dead = True
                self.mover.stop()
                self.goal = None
                self.notify("dead", "the character died (now a ghost): 'goal resurrect' floats it up to town "
                                    "and resurrects it at the Temple (halves the experience for good)")
            if w.ghost and isinstance(self.goal, Resurrect):
                return False
            return True
        if now < self.busy_until:
            return True
        if w.store and isinstance(self.goal, Shop):
            return False          # any command would leave the store
        mons_near = [m for m in w.monsters if w.dist(m[:2]) <= 7]
        # 2. Emergency
        # Never fall through to the goal here, even when escape() has nothing
        # usable this instant: in mission 7 the explore goal kept re-planning
        # (the mover sends 'clear' and queues walks), which wiped every queued
        # Phase Door, potion and Word of Recall, and the walks took the turns.
        # Dive03 died at 750 ft without one of them being read.
        if w.hp_frac < o["flee_hp"] and (mons_near or now - w.last_hit_t < 5):
            if not self.escape("low HP") and self.mover.active and not self.escaping_to_stairs:
                self.mover.stop()
            return True
        # 2'. Group danger (the Borg's rule, Advisor memo 2026-09-28 §3.1)
        if self.group_tick(now):
            return True
        # 2a. Status cures, in combat only (out of combat, rest it off: the
        # user). Stun can become a knock-out; blind or confused can't read.
        if self.status_tick(now, mons_near):
            return True
        # 3. Arrival into danger (connected stairs: the way back is underfoot)
        # A stairs command gets no answer at all if it comes too soon after the
        # level change (seen: '<' 0.7 s after arriving was ignored), so retry
        # after 1.2 s while still on the stairs
        stairs_pending = w.last_stairs_cmd and now - w.last_stairs_cmd[1] < 1.2
        if now - w.level_t < 6 and w.standing_on in ("<", ">") and not stairs_pending:
            danger = self.dangers()
            # A pack only counts if its members are within 5 levels of ours (a
            # pack of jackals is XP for a level-11 warrior, not a threat)
            lev = w.clvl
            threats = [m for m in mons_near if m[2].level >= lev - 5]
            if len(threats) >= o["arrival_pack"] or (danger and "danger" in o["stop_on"]):
                why = f"arrived next to {len(threats)} monsters ({threats[0][2].name if threats else ''})" + \
                    (f" incl. {self.danger_text(danger[0])}" if danger else "")
                self.take_stairs(w.standing_on)
                self.notify("danger_avoided", why)
                return True
        # 3a. Something far above our level in view: leave before it reaches us
        # (not only on arrival -- Dive03 met Stone trolls while exploring)
        near_danger = [r for y, x, r in w.monsters if w.dist((y, x)) <= 12 and r in self.dangers()]
        # (and one the server's monster list names but the map decode misses:
        # present, position unknown -- the game-state survey, rule 4)
        near_danger += [r for r in w.listed_only() if self.danger_why(r)]
        if near_danger and not isinstance(self.goal, (Flee, Recover)) and now - self.flee_t > 10 \
                and "danger" in o["stop_on"]:
            self.flee_t = now
            prev = self.goal.describe() if self.goal else None
            self.set_goal(Flee(near_danger[0].name))
            self.notify("danger_seen", f"{self.danger_text(near_danger[0])} in view"
                                       f"{' while ' + prev if prev else ''}: heading for the stairs")
            return True
        # 3a'. Something we can't see is attacking (an invisible monster, or one
        # out of sight): we can't fight it, so leave (Advisor memo, Addendum 2
        # item 3). Also HP falling with nothing in view and nothing else to
        # explain it.
        if self.unseen_tick(now):
            return True
        # 3b. A pack coming at us in the open: back into a corridor so they
        # trickle into melee one at a time ("retreat behind a turn")
        # (never while fleeing: mission 10 backed into a corridor twice instead
        # of walking to the stairs away from Mughash, and died there)
        if o.get("choke") == "on" and not w.adjacent_monsters() and w.standing_on not in ("<", ">") \
                and not isinstance(self.goal, (Flee, Recover, Recall)):
            if self.choke_tick(now):
                return True
        # 3b'. Afraid (a warrior can't melee). The user: if not in danger, don't
        # spend consumables -- kite over cleared ground until it wears off; only
        # in danger cure it (Boldness/Heroism/Berserk) or phase away.
        if w.flag("afraid") and mons_near:
            danger = w.hp_frac < o["think_hp"] or bool(self.dangers())
            # (just arrived: no walked ground to kite over -- the stairs underfoot
            # are the cheapest way out)
            if not w.walked - {w.pos} and w.standing_on in ("<", ">") and len(mons_near) >= 2:
                self.take_stairs(w.standing_on)
                self.notify("tactic", "afraid on arrival among monsters: took the stairs back")
                return True
            if not danger and self.retreat_step(mons_near):
                if now - self.fear_t > 20:
                    self.fear_t = now
                    self.notify("tactic", "afraid: kiting over cleared ground until it wears off")
                return True
            if now - self.fear_t > 3:
                self.fear_t = now
                pot = next((i for i in w.items(tval=TV_POTION)
                            if any(n in i["name"] for n in ("Boldness", "Heroism", "Berserk"))), None)
                if pot:
                    self.cmd(f"custom q item={pot['item']}", f"afraid and in danger: quaff {pot['name']}", hold=0.6)
                    self.notify("tactic", f"afraid and in danger: quaffed {one_of(pot['name'])}")
                    return True
                pd = next((i for i in w.items(tval=TV_SCROLL) if "Phase Door" in i["name"]), None)
                if pd and w.adjacent_monsters() and not w.flag("blind") and not w.flag("confused"):
                    self.cmd(f"custom r item={pd['item']}", "afraid: phase door away", hold=0.6)
                    self.notify("afraid", "afraid (can't melee) and cornered: phased away")
                    return True
        # 3b''. Monsters that frighten you again and again: not worth it. Walk
        # away over cleared ground (phase if it's dangerous and next to us), and
        # tell the Navigator once per level.
        # Monsters that never move (molds, jellies, mushroom patches, floating
        # eyes) only matter next to us, and there auto-retaliate fights them: a
        # poison-mold cluster killed a forum player, a death mold disenchants, a
        # floating eye paralyses. Step away quietly (no event), unless the
        # Navigator is hunting that very monster.
        hunting = self.goal.target if isinstance(self.goal, Hunt) else None
        still = [m for m in w.adjacent_monsters() if "NEVER_MOVE" in m[2].flags
                 and not (hunting and hunting in m[2].name.lower())]
        if still and self.still_fight_tick(now, still):
            return True
        if still and (self.retreat_step(still, reach=6) or self.sidestep(still)):
            return True
        fearers = [m for m in mons_near if m[2].repeat_fearer and "NEVER_MOVE" not in m[2].flags]
        if fearers and not isinstance(self.goal, (Flee, Recall)):
            f = fearers[0][2]
            if (w.level_t, f.name) not in self.fearers_seen:
                self.fearers_seen.add((w.level_t, f.name))
                self.notify("fearer", f"{f.name} (lvl {f.level}) keeps frightening: moving away from it; "
                                      "consider leaving the level")
            dangerous = f.level >= w.clvl - 2
            if dangerous and w.adjacent_monsters() and now - self.phase_t > 2.5:
                pd = next((i for i in w.items(tval=TV_SCROLL) if "Phase Door" in i["name"]), None)
                if pd and not w.flag("blind") and not w.flag("confused"):
                    self.phase_t = now
                    self.cmd(f"custom r item={pd['item']}", f"phase away from {f.name}", hold=0.6)
                    return True
            if self.retreat_step(fearers):
                return True
        # 3c. Light
        if self.town_light(now):
            return True
        if not w.adjacent_monsters() and self.keep_light(now):
            return True
        # 4. Hunger
        # (not just "nothing on the map this instant": mission 9 ate a ration
        # with Bullroarer a step out of view)
        if w.hunger <= 2 and not w.monsters and now - w.monster_seen_t > 5 and now - w.last_hit_t > 5:
            food = w.items(tval=TV_FOOD)
            # one meal, then wait for the hunger indicator to catch up (mission 13
            # ate 2 rations in a row: 3 -> 1, "Full", no news)
            if food and now - self.eat_t > 10:
                self.eat_t = now
                self.cmd(f"eat {food[0]['item']}", f"hungry ({w.hunger})", hold=1.0)
                self.notify("tactic", f"hungry: ate {one_of(food[0]['name'])}")
                return True
            if food:
                return False
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
            if w.ind.get("class_") == "Warrior":
                junk += ["book of magic spells", "holy book of prayers"]   # can't read them
            if seen and (any(f"of {j}" in seen[-1][1].lower() or seen[-1][1].lower().rstrip(".").endswith(j)
                             or j.startswith("book") and j in seen[-1][1].lower() or
                             j.startswith("holy book") and j in seen[-1][1].lower() for j in junk)
                         or " Broken " in seen[-1][1]):
                seen = []         # known junk: leave it (it filled the pack on the way down)
                self.skipped_items.add((w.level_t, w.pos))
            if seen and seen[-1][0] > self.picked_t and w.pos == self.seen_pos(seen[-1][0]):
                self.picked_t = now
                if self.mover.active:
                    self.mover.requeue()   # steps queued ahead ran first: the pickup landed a square later
                # (it waits for energy after the step: ~0.6 s at normal speed)
                self.cmd("custom ,", f"pick up: {seen[-1][1][8:]}", hold=0.8)   # "Stay" picks up; "g" did nothing
                return True
        full = [t for ts, t in w.messages if now - ts < 3 and t.startswith("You have no room for")]
        if full and now - self.full_warned > 30:
            self.full_warned = now
            self.notify("pack_full", full[-1])
        if not w.monsters and not w.store and self.auto_destroy(now):
            return True
        # 6. Rest when hurt and alone
        if w.hp_frac < o["rest_below"] and not w.monsters and not isinstance(self.goal, (Recall,)):
            if not self.mover.active or isinstance(self.goal, Dive):
                self.mover.stop()
                self.start_resting()
                return True
        if w.resting and (w.hp_frac >= o["rest_to"] or w.monsters) and not isinstance(self.goal, RestGoal):
            self.stop_resting()
            return True
        if w.resting and not w.monsters:
            # keep resting to rest_to (the Advisor's mission 13 replay: the rest
            # ended once HP passed rest_below and the explorer walked off at 76%)
            return True
        return False

    def emergency_loop(self, now):
        """Three emergency actions within 90 s: phasing and drinking isn't
        working (HP stuck around 50%, monsters always in view): leave by stairs
        if some are known, else tell the Navigator."""
        self.emerg_times = [t for t in self.emerg_times if now - t < 90]
        if len(self.emerg_times) < 3 or now - self.loop_warned < 60:
            return False
        self.loop_warned = now
        stairs = [p for p in self.w.find("<>") if self.w.dist(p) <= 30]
        if stairs and not isinstance(self.goal, Flee):
            prev = self.goal
            self.set_goal(Flee("emergency loop"))
            self.resume_after = prev
            self.notify("tactic", "third emergency in 90 s: leaving by the stairs")
            return True
        self.notify("emergency_loop", "third emergency in 90 s and no stairs known nearby: "
                                      "consider Word of Recall or leaving this area")
        return False

    def escape(self, why):
        """Emergency: stairs underfoot > out of combat, rest (never potions)
        > (in melee) Phase Door > (not in melee) walk to nearby stairs, else
        a cure potion. Rate-limited: Phase Door
        again and again doesn't shake a pack (it burned 10 scrolls in 10 s)."""
        w = self.w
        now = time.time()
        if w.last_stairs_cmd and now - w.last_stairs_cmd[1] < 1.2:
            return True           # already on our way (retried after 1.2 s)
        if self.emergency_loop(now):
            return True
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
        # Out of combat, potions and scrolls are a waste: rest instead (the
        # user). In combat = something next to us, hit in the last 3 s (ranged
        # attacks count), or HP falling with a monster in view (not poison or
        # a cut on its own).
        rate = w.damage_rate(3.0)
        in_combat = adj or now - w.last_hit_t <= 3 or (rate > 0 and w.monsters)
        if not in_combat and \
                not (self.mover.active and self.escaping_to_stairs):
            if not w.monsters:
                self.start_resting()
                return True
            # something in view but not fighting (asleep, slow): back off over
            # walked ground, out of its sight, and rest there
            return self.retreat_step([m for m in w.monsters if w.dist(m[:2]) <= 7] or w.monsters)
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
            # (a new move sends 'clear', which would drop a read or quaff still
            # waiting in the server's queue for our next turn)
            used_recently = now - max(self.phase_t, self.cure_t, self.recall_t) < 2.0
            if stairs and not self.mover.active and not used_recently:
                if self.mover.go(stairs):
                    self.escaping_to_stairs = True
                    self.notify("emergency", f"{why}: heading for the stairs {min(w.dist(p) for p in stairs)} away")
            if self.mover.active and self.escaping_to_stairs:
                st = self.mover.tick()
                if st == "arrived" and w.standing_on in ("<", ">"):
                    self.take_stairs(w.standing_on)
                return True
        if now - self.cure_t > 1.5:
            # Heal or escape, by numbers (Advisor memo P3: quaffing CLW while
            # taking 100+ a turn is the commonest fatal mistake). A potion must
            # out-heal what comes in before the next one can land (~1.5 s, plus
            # the turn auto-retaliate eats). Weakest adequate first (Cure Serious
            # went first and was gone when it mattered, mission 2); when HP is
            # collapsing, at least 10% of max HP.
            need = max(rate * 2.0, 0.1 * w.hp[1] if w.hp_frac < 0.3 else 0)
            pots = sorted(((heal_of(i["name"]), i) for i in w.items(tval=TV_POTION) if heal_of(i["name"])),
                          key=lambda p: p[0])
            good = [p for p in pots if p[0] > need]
            pick = good[0] if good else None
            dire = rate > 0 and w.hp[0] < rate * 8      # dead in under ~8 s at this rate
            if pots and not good and not dire:
                pick = pots[-1]          # slow damage: the biggest potion still helps
            elif pots and not good:
                # Every potion is too small for this damage: escape instead
                if now - self.noescape_t > 10:
                    self.noescape_t = now
                    self.notify("emergency", f"{why}: losing ~{rate:.0f} HP/s, more than the best potion heals "
                                             f"({pots[-1][0]}): escaping instead")
                if adj and pd and can_read and now - self.phase_t > 0.7:
                    self.phase_t = now
                    self.cmd(f"custom r item={pd['item']}", f"{why}: phase door (potions too weak)", hold=0.6)
                    return True
                wor = next((i for i in w.items(tval=TV_SCROLL) if "Word of Recall" in i["name"]), None)
                if wor and can_read and w.in_dungeon and not self.recall_started(now):
                    self.recall_t = now
                    self.cmd(f"custom r item={wor['item']}", f"{why}: word of recall (potions too weak)", hold=0.5)
                    self.notify("emergency", f"{why}: read Word of Recall (potions too weak for the damage)")
                    return True
                if not adj:
                    pick = pots[-1]      # shot at, nothing to hit back: any HP helps
            if pick:
                pot = pick[1]
                self.cure_t = now
                self.cmd(f"custom q item={pot['item']}", f"{why}: quaff {pot['name']}", hold=0.6)
                self.notify("emergency", f"{why}: quaffed {one_of(pot['name'])}" + (f" (losing ~{rate:.0f} HP/s)" if rate else ""))
                return True
        if now - self.noescape_t > 10:
            self.noescape_t = now
            left = [n for n, ok in (("Phase Door", pd), ("cure potions", any(
                    any(c in i["name"] for c in CURE_POTIONS) for i in w.items(tval=TV_POTION)))) if ok]
            self.notify("emergency", f"{why}: " + (f"waiting to use {', '.join(left)} again, fighting on"
                                                   if left else "nothing left to escape with, fighting on"))
        return False

    def watch_perception(self):
        """Log when the server's monster list names something our map decode
        doesn't show (mission 4: a Yellow mold hit us while the pilot saw
        nothing). Once per level and name, with the map around us."""
        w = self.w
        if not w.monlist or not w.rows or not w.pos:
            return
        seen = {r.name for *_, r in w.monsters}
        now = time.time()
        for name, n, ch in w.monlist:
            if name in seen:
                self.gap_since.pop(name, None)
                continue
            # (the monster list and the map arrive separately: only a gap that
            # lasts counts)
            if now - self.gap_since.setdefault(name, now) < 1.5 or (w.level_t, name) in self.gaps_logged:
                continue
            self.gaps_logged.add((w.level_t, name))
            y, x = w.pos
            crop = [(r[max(0, x - 12):x + 13], a[max(0, x - 12):x + 13])
                    for r, a in zip(w.rows[max(0, y - 6):y + 7], w.attrs[max(0, y - 6):y + 7])]
            self.log("perception_gap", name=name, count=n, our_char=ch, pos=w.pos,
                     map_age=round(time.time() - w.map_t, 2), crop=crop,
                     monsters=[(my, mx, r.name) for my, mx, r in w.monsters])

    def watch_progress(self):
        """A goal that goes nowhere: at most 10 different squares in 2 minutes
        while not fighting (mission 3 circled a '>' for 10 minutes, and no
        event woke the Navigator). Clear the server queue, restart the move,
        and say so."""
        w, now = self.w, time.time()
        if w.pos:
            self.pos_hist.append((now, w.pos, w.depth))
        while self.pos_hist and now - self.pos_hist[0][0] > 120:
            self.pos_hist.popleft()
        idle_goal = isinstance(self.goal, (Wait, RestGoal, Search, Recall, Recover, Shop)) or self.goal is None
        # (a fight in the window doesn't count: mission 6 fired this in a
        # corridor fight with a wolf pack)
        fighting = now - max(w.last_hit_t, w.fight_t) < 120
        if idle_goal or fighting or w.adjacent_monsters() or w.resting or now - self.stuck_t < 120 or \
                not self.pos_hist or now - self.pos_hist[0][0] < 110 or \
                len({(p, d) for _, p, d in self.pos_hist}) > 10:
            return
        self.stuck_t = now
        self.c.send("clear")
        self.mover.stop()
        self.notify("stuck", f"'{self.goal.describe()}' has gone nowhere for 2 minutes "
                             f"(around {w.pos}): cleared the command queue and restarted the move. "
                             "If it happens again, give another goal")

    ABILITY_FLAGS = {"free_action": "free_act", "resist_blind": "res_blind", "resist_conf": "res_conf",
                     "see_invisible": "see_invis"}

    def has_ability(self, order):
        """Free Action, a resist...: from the character sheet's grid (tool
        query 'flags') once read, else from the order of the same name."""
        known = self.w.has(self.ABILITY_FLAGS.get(order, order)) if hasattr(self.w, "has") else None
        if known is not None:
            return known
        return self.orders.get(order) == "yes"

    def weapon_table(self):
        """[(name, blows, damage per round, wielded?)] for the wielded weapon and
        every weapon in the pack, at the current STR/DEX (the Advisor's
        progression memo: mission 13 fought 17 min with a Dagger while
        carrying a Sabre)."""
        ind = self.w.ind
        st, dx = ind.get("stat0", [0])[0], ind.get("stat3", [0])[0]
        if not st or not dx:
            return []
        out = []
        for eq in (True, False):
            for i in self.w.items(equip=eq):
                if i["tval"] in TV_WEAPONS:
                    wt = i["weight"] // max(1, i.get("number", 1))
                    b = weapon_blows(wt, st, dx)
                    out.append((i["name"], b, weapon_damage(i["name"], b), eq))
        return out

    def watch_weapons(self):
        """News when a carried weapon beats the wielded one by > 20% per round."""
        wt = self.weapon_table()
        cur = next((d for n, b, d, eq in wt if eq), 0)
        for n, b, d, eq in wt:
            if not eq and d > cur * 1.2 and d > 0 and n not in self.weapon_tips:
                self.weapon_tips.add(n)
                self.notify("tactic", f"{n} would do ~{d:.0f} per round ({b} blows) vs ~{cur:.0f} now: wield it")

    def user_note(self, text):
        """The user's commentary while watching (tools/observe/watch.py or
        pilotctl note): logged with a snapshot of the moment, in the
        decision log (kind user_note) and in commentary.jsonl, so it can be
        cross-referenced with the play. A note starting with '?' is a
        question for the Architect."""
        w = self.w
        recent = list(self.recent_acts)[-8:]
        rec = {"t": round(time.time(), 3), "note": text, "question": text.startswith("?"),
               "depth_ft": w.depth_ft, "pos": w.pos, "hp": list(w.hp), "clvl": w.clvl,
               "goal": self.goal.describe() if self.goal else None,
               "last_action": list(self.last_action) if self.last_action else None,
               "monsters": [(y, x, r.name) for y, x, r in w.monsters][:12],
               "standing_on": w.standing_on, "recent": recent}
        self.log("user_note", **{k: v for k, v in rec.items() if k != "t"})
        if text.startswith("!"):
            # a message for the Navigator: an attention event wakes its wait
            self.notify("user_message", text[1:].strip())
        with open(os.path.join(self.rundir, "commentary.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
        return f"noted at {time.strftime('%H:%M:%S')} ({w.depth_ft} ft, HP {w.hp[0]}/{w.hp[1]}, " \
               f"goal {rec['goal']})"

    def monster_info(self, name):
        """This server's facts about a monster (monster.txt + the Advisor's
        danger table) and what the pilot makes of it now (post-mortem memo §5:
        the Navigator used Vanilla lore, which differs here)."""
        q = name.lower()
        found = [r for r in self.w.g.races.values() if q in r.name.lower()]
        if not found:
            return f"no monster matching '{name}'"
        exact = [r for r in found if r.name.lower() == q]
        out = []
        for r in (exact or found)[:6]:
            mx, drains = r.worst_melee
            why = self.danger_why(r)
            flags = sorted(f for f in r.flags if f in ("UNIQUE", "NEVER_MOVE", "MULTIPLY", "INVISIBLE",
                                                       "PASS_WALL", "KILL_WALL", "FRIENDS", "EMPTY_MIND"))
            out.append(f"{r.name} ({r.char}): lvl {r.level} ({r.level * 50} ft), speed {r.speed - 110:+d}, "
                       f"HP {r.hp}; blows {', '.join(r.blows) or 'none'}; "
                       f"spells 1 in {r.spell_freq}: {', '.join(sorted(r.spells))}" if r.spells else
                       f"{r.name} ({r.char}): lvl {r.level} ({r.level * 50} ft), speed {r.speed - 110:+d}, "
                       f"HP {r.hp}; blows {', '.join(r.blows) or 'none'}; no spells")
            out[-1] += (f"; flags {', '.join(flags) or '-'}; max breath {r.max_breath}; "
                        f"melee per turn ~{r.per_turn:.0f} (worst {mx * (r.speed_x or 1):.0f}, drain blows {drains})"
                        f"; Advisor rating {r.danger if r.danger is not None else '?'}/5"
                        f"; for you now: {'DANGER: ' + why if why else 'no danger rule fires'}")
        more = len(exact or found) - 6
        return "\n".join(out) + (f"\n(+{more} more)" if more > 0 else "")

    def group_danger(self):
        """Worst-case melee of everything that can reach us this turn, the
        Borg's way: max dice x speed, +150 per stat/exp-drain blow, +200 for a
        paralysing blow without Free Action. Monsters that never move don't
        count (they only matter next to us, and we step away). Drain weight 50
        (the Advisor's run post-mortem replay; the Borg uses 150). Replayed
        over Dive03's logs, 0.3x fired 5-14 s before every drop below 50% HP,
        0.6x only 1-5 s before."""
        w = self.w
        lev = w.clvl
        ac = w.ind.get("armor", [0])[0]
        total, who = 0.0, []
        for y, x, r in w.monsters:
            if "NEVER_MOVE" in r.flags:
                continue
            sx = r.speed_x if r.speed_x is not None else max(1.0, (r.speed - 100) / 10)
            if w.dist((y, x)) > 1 + math.ceil(sx):
                continue
            mx, drains = r.worst_melee
            # (no drain term: the Advisor's mission 9 replay found it alone put a
            # lone Giant red frog at 0.6x; drains have their own rule, the second
            # drain on a level -> leave)
            g = mx * sx
            if r.paralyse_blow_power > ac * 3 / 4 and not self.has_ability("free_action"):
                g += 200
            if g:
                total += g
                who.append(r.name)
        return total, who

    def group_tick(self, now):
        """Tiers against current HP (Borg memo, tuned by the post-mortem memo):
        > 0.3x: disengage (just arrived: the stairs back; not yet in melee:
        back away); > 0.6x: the stairs underfoot; Phase Door only once HP is
        below think_hp; > 1.0x: leave the level by the nearest stairs, Phase
        Door when adjacent (every 10 s at most), and with no stairs known start
        Word of Recall now (it takes 15-34 player turns)."""
        w = self.w
        if not w.in_dungeon or not w.monsters:
            return False
        g, who = self.group_danger()
        hp = max(w.hp[0], 1)
        # Floor from the HP actually being lost (mission 9: a Cave spider swarm
        # took 77 -> 35 HP with one spider in view, and the sum stayed at 0.23x)
        lost = w.damage_rate(3.0) * 3.0
        if lost > g:
            g, who = lost, who + ["(HP falling ~%.0f/s)" % w.damage_rate(3.0)]
        if g <= 0.3 * hp:
            return False
        names = ", ".join(f"{n} x{c}" if c > 1 else n for n, c in collections.Counter(who).items())
        stairs_pending = w.last_stairs_cmd and now - w.last_stairs_cmd[1] < 1.2
        on_stairs = w.standing_on in ("<", ">") and not stairs_pending
        if g <= 0.6 * hp:
            if now - w.level_t < 6 and on_stairs:
                self.take_stairs(w.standing_on)
                self.notify("danger_avoided", f"arrived next to {names} (worst-case melee {g:.0f} vs HP {hp}): "
                                              "took the stairs back")
                return True
            fast = any((r.speed_x or 1) > 1 for y, x, r in w.monsters if "NEVER_MOVE" not in r.flags
                       and w.dist((y, x)) <= 6)
            if not w.adjacent_monsters() and not fast and isinstance(self.goal, (Explore, Hunt, Goto, Dive)):
                if self.group_warned != (w.level_t, names):
                    self.group_warned = (w.level_t, names)
                    self.notify("tactic", f"{names} can deal {g:.0f} at worst (HP {hp}): backing away, "
                                          "not walking into them")
                return self.retreat_step([m for m in w.monsters if "NEVER_MOVE" not in m[2].flags])
            return False
        if on_stairs:
            self.take_stairs(w.standing_on)
            self.notify("danger_avoided", f"{names} can deal {g:.0f} (HP {hp}): took the stairs underfoot")
            return True
        if g > hp and not isinstance(self.goal, (Flee, Recall, Recover)) and w.find("<>") \
                and now - self.flee_t > 10:
            self.flee_t = now
            prev = self.goal.describe() if self.goal else None
            self.set_goal(Flee("a dangerous group"))
            self.notify("danger_seen", f"group danger: {names} can deal {g:.0f} per turn at worst, HP {hp}"
                                       f"{' while ' + prev if prev else ''}: leaving the level")
        can_read = not w.flag("blind") and not w.flag("confused")
        far = not any(w.dist(q) <= 25 for q in w.find("<>"))   # (mission 14: stairs 66 away)
        if g > hp and far and can_read and not self.recall_started(now):
            wor = next((i for i in w.items(tval=TV_SCROLL) if "Word of Recall" in i["name"]), None)
            if wor:
                self.recall_t = now
                self.cmd(f"custom r item={wor['item']}", f"group danger {g:.0f} vs HP {hp}: word of recall",
                         hold=0.5)
                self.notify("emergency", f"{names} can deal {g:.0f} (HP {hp}) and no stairs are known: "
                                         "read Word of Recall now (it takes 15-35 s)")
                return True
        # Phase only when it's really going badly: at 0.6-1.0x only once HP is
        # already below think_hp, and at most every 10 s (mission 9: a lone
        # Giant red frog, 58 worst-case vs 97 HP, cost 4 Phase Doors at full HP)
        pd = w.tagged("r", 1) or next((i for i in w.items(tval=TV_SCROLL) if "Phase Door" in i["name"]), None)
        hurting = g > hp or w.hp_frac < self.orders["think_hp"]
        if w.adjacent_monsters() and pd and can_read and hurting and now - self.phase_t > 10:
            self.phase_t = now
            self.cmd(f"custom r item={pd['item']}", f"group danger {g:.0f} vs HP {hp}: phase door", hold=0.6)
            self.notify("tactic", f"{names} can deal {g:.0f} (HP {hp}): phased away")
            return True
        return False

    def still_fight_tick(self, now, still):
        """A stationary monster next to us that blocks the way (sits by the
        square the mover is heading for) or disenchants: kill it if it's weak,
        by standing still (auto-retaliate). Mission 6 stalled a step from the
        only '>' beside a Disenchanter eye, stepping away and back while its
        gaze disenchanted the weapon and armour. A disenchanter too strong to
        kill: leave the level, never path around it."""
        w = self.w
        lev = w.clvl
        goals = self.mover.goals if self.mover.active and self.mover.goals else set()
        if goals:
            self.still_goals = (w.level_t, set(goals))
        elif self.still_goals[0] == w.level_t:
            goals = self.still_goals[1]       # (the mover was stopped for the fight)

        def disenchants(r):
            return any("UN_BONUS" in b or "DISENCHANT" in b for b in r.blows)

        def killable(r):
            paralyses = any(b.split(":")[1:2] == ["PARALYZE"] for b in r.blows)
            nosave = {e for e in r.no_save_blows
                      if not self.has_ability("resist_blind" if e == "BLIND" else "resist_conf")}
            return r.level <= lev and not (paralyses and not self.has_ability("free_action")) \
                and not nosave

        targets = [m for m in still if disenchants(m[2]) or any(w.dist(g, m[:2]) <= 1 for g in goals)]
        fight = [m for m in targets if killable(m[2])]
        if fight and (w.hp_frac >= self.orders["think_hp"] or self.still_fighting == (w.level_t, fight[0][:2])):
            m = fight[0]
            self.mover.stop()
            if self.still_fighting != (w.level_t, m[:2]):
                self.still_fighting = (w.level_t, m[:2])
                why = "disenchants" if disenchants(m[2]) else "blocks the way"
                self.notify("tactic", f"{m[2].name} (lvl {m[2].level}, never moves) {why}: killing it")
            return True
        bad = [m for m in targets if disenchants(m[2]) and not killable(m[2])]
        if bad and not isinstance(self.goal, (Flee, Recall, Recover)):
            prev = self.goal.describe() if self.goal else None
            self.set_goal(Flee(bad[0][2].name))
            self.notify("danger_seen", f"{bad[0][2].name} (lvl {bad[0][2].level}) disenchants and is too strong "
                                       f"to kill{' while ' + prev if prev else ''}: heading for the stairs")
            return True
        return False

    def status_tick(self, now, mons_near):
        """Quaff the cheapest potion that cures a dangerous status in a fight
        (Advisor memo P4 + Erratum): stun at once, blind/confused when
        something is near, poison only when HP is also getting low."""
        w = self.w
        if not w.in_dungeon or now - self.cure_t <= 1.5:
            return False
        in_combat = w.adjacent_monsters() or now - w.last_hit_t <= 3
        if not in_combat:
            return False
        want = []
        if w.flag("stun"):
            want.append("stun")
        if mons_near and w.flag("confused"):
            want.append("confused")
        if mons_near and w.flag("blind"):
            want.append("blind")
        if w.flag("poisoned") and w.hp_frac < self.orders["think_hp"]:
            want.append("poisoned")
        pots = list(w.items(tval=TV_POTION))
        for status in want:
            for cure in STATUS_CURES[status]:
                pot = next((i for i in pots if cure in i["name"]
                            and not (cure == "Healing" and "*Healing*" in i["name"])), None)
                if pot:
                    self.cure_t = now
                    self.cmd(f"custom q item={pot['item']}", f"{status} in combat: quaff {pot['name']}", hold=0.6)
                    self.notify("tactic", f"{status} in combat: quaffed {one_of(pot['name'])}")
                    return True
            if now - getattr(self, "nocure_t", 0) > 20:
                self.nocure_t = now
                self.notify("tactic", f"{status} in combat and no potion cures it "
                                      f"(needs {' / '.join(STATUS_CURES[status][:2])})")
        return False

    def unseen_tick(self, now):
        w = self.w
        if not w.in_dungeon or w.flag("blind"):
            return False          # (blind, everything is "it": fight on)
        if now - w.heard[0] < 2 and w.heard[0] > self.heard_warned:
            self.heard_warned = w.heard[0]
            self.notify("unseen_attacker", "heard a door burst open: something is coming; be ready to leave")
        cause = None
        if now - w.unseen[0] < 3:
            cause = w.unseen[1]
        elif self.orders.get("unseen_hp") == "on" and now - w.monster_seen_t > 4 and \
                now - w.last_hit_t > 4 and w.hp[0] < w.hp[1] and w.damage_rate(3.0) >= max(2.0, 0.01 * w.hp[1]) \
                and not w.flag("poisoned") and not w.flag("cut") and w.hunger > 1 and now - w.level_t > 4 \
                and now - w.explained_t > 10:
            # HP falling steadily although nothing has been in view -- or hit us
            # by name ("The Yellow mold ...") -- for 4 s: the fight's own damage
            # stays in the 3-s window after a kill, which fired this after nearly
            # every kill in mission 4
            cause = f"losing HP ({w.damage_rate(3.0):.0f}/s) with nothing in view"
        if not cause or isinstance(self.goal, (Flee, Recall, Recover)) or now - self.unseen_warned < 20:
            return False
        self.unseen_warned = now
        # Minor, at good HP: teleport-to ("It commands you to return": Tengu,
        # blink dogs), a magic missile or an arrow from the dark. Mission 6 fled
        # levels over these; tell the Navigator and carry on.
        if re.search(r"commands you to return|magic missile|fires an arrow|fires a bolt|mumbles", cause) \
                and w.hp_frac >= self.orders["think_hp"]:
            self.notify("unseen_attacker", f"'{cause}': minor attack from something unseen; carrying on "
                                           f"(HP {w.hp_frac:.0%})", news=True)
            return False
        prev = self.goal.describe() if self.goal else None
        if w.find("<>"):
            self.set_goal(Flee("unseen attacker"))
            self.notify("unseen_attacker", f"'{cause}': something unseen is attacking"
                                           f"{' while ' + prev if prev else ''}; heading for the stairs")
        else:
            self.notify("unseen_attacker", f"'{cause}': something unseen is attacking and no stairs are known: "
                                           "consider Word of Recall or Phase Door")
        return True

    def sidestep(self, threats):
        """One step to a free square next to none of threats (stationary
        monsters: one square away is enough). Returns True if a step was sent."""
        w = self.w
        now = time.time()
        if now - self.sidestep_t < 0.8:
            return True               # the last step is still on its way
        occupied = {m[:2] for m in w.monsters}
        cands = [(w.pos[0] + dy, w.pos[1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
        cands = [t for t in cands if passable(w.memory.get(t, " ")) and t not in occupied
                 and all(w.dist(t, m[:2]) > 1 for m in threats)]
        if not cands:
            return False
        # prefer ground we've walked (known safe), then fewer monsters next to it
        best = min(cands, key=lambda t: (t not in w.walked,
                                         sum(1 for m in w.monsters if w.dist(t, m[:2]) <= 1)))
        self.sidestep_t = now
        self.cmd(f"walk {direction(w.pos, best)}", f"step away from {threats[0][2].name}", hold=0.3)
        return True

    def retreat_step(self, threats, reach=15):
        """Move away from threats over ground we've already walked this level
        (the user: kiting into unknown areas piles on more monsters). Returns
        True while retreating."""
        w = self.w
        if self.mover.active and self.retreating:
            st = self.mover.tick()
            if st == "moving":
                return True
            self.retreating = False
        if not threats or not w.pos:
            return False
        def far(t):
            return min(w.dist(t, m[:2]) for m in threats)
        here = far(w.pos)
        cands = [t for t in w.walked if w.dist(t) <= reach and far(t) >= max(here + 2, 4)]
        if not cands:
            return False
        best = max(cands, key=lambda t: (far(t), -w.dist(t)))
        if self.mover.go([best]):
            self.retreating = True
            return True
        return False

    FLAVOURED = {75, 70, 65, 55, 66, 45, 40}     # potion, scroll, wand, staff, rod, ring, amulet

    # --- the flavour table (the Advisor's identify-and-sell memo, 2026-10-07):
    # flavours are fixed per server, so what any character learns holds for all

    def load_flavours(self):
        try:
            with open(self.flavour_file) as f:
                self.flavours = json.load(f)
        except (OSError, ValueError):
            self.flavours = {}
        self.junk_kinds = {}
        try:
            tv = {"potion": "Potion", "scroll": "Scroll", "wand": "Wand", "staff": "Staff", "rod": "Rod",
                  "ring": "Ring", "amulet": "Amulet"}
            for k in csv.DictReader(open(os.path.join(HERE, "kinds.csv"))):
                self.junk_kinds[f"{tv.get(k['kind'], k['kind'])} of {k['name']}"] = \
                    k["sell_known"] in ("0-0", "0") or "CURSE" in k["flags"]
        except OSError:
            pass

    def learn_flavour(self, flavour, kind, how):
        if not flavour or not kind or " of " not in kind or self.flavours.get(flavour, {}).get("kind") == kind:
            return
        self.flavours[flavour] = {"kind": kind, "junk": self.junk_kinds.get(kind, False), "source": how}
        try:
            cur = {}
            if os.path.exists(self.flavour_file):
                with open(self.flavour_file) as f:
                    cur = json.load(f)
            cur[flavour] = self.flavours[flavour]
            with open(self.flavour_file, "w") as f:
                json.dump(cur, f, indent=1, sort_keys=True)
        except OSError:
            pass
        self.notify("tactic", f"learned: {flavour} = {kind}" + (" (junk)" if self.flavours[flavour]["junk"] else ""))

    def flavour_of(self, it):
        return self.flavours.get(flavour_key(it["name"])) if self.unknown_flavour(it) else None

    def show(self, it):
        """An item's name, with the flavour table's kind for an unknown flavour."""
        f = self.flavour_of(it)
        return it["name"] + (f" (= {f['kind']}{', junk' if f['junk'] else ''}; not aware)" if f else "")

    def unknown_sell_refusal(self, it, n):
        """Why not to sell this unknown item now, or None (the memo's §4.4):
        junk per the table -> sell (the shop refuses it once known); one of a
        stack -> sell (a free identification of the flavour); a potion or
        scroll while we've never been below 1000 ft -> sell (Identify costs
        more than it earns); devices and jewellery -> Identify first."""
        if not self.unknown_flavour(it):
            return None
        f = self.flavour_of(it)
        if f and f["junk"]:
            return None
        if f:
            return f"it's {f['kind']}: worth more known, use or Identify it"
        if it.get("number", 1) >= 2 and n == 1:
            return None
        if it["tval"] in (75, 70, TV_FOOD) and self.deepest_ft < 1000:
            return None
        if it["tval"] in (75, 70, TV_FOOD):
            return "an unknown potion/scroll found below 1000 ft: Identify it (expected value 87-750)"
        return "an unknown wand/staff/rod/ring/amulet: Identify it first (worth 50-700 known)"

    def unknown_flavour(self, it):
        """An unidentified flavoured item ('a Blue Speckled Potion', 'a Copper
        Wand', 'a Blue Mushroom'): it sells at its plain base value, whatever it is."""
        if it.get("tval") == TV_FOOD:
            return "Mushroom" in it["name"] and " of " not in it["name"]
        return it.get("tval") in self.FLAVOURED and " of " not in it["name"]

    def probably_special(self, name):
        """A unique's drop (inscribed with its name) or an {excellent}/{special}
        feeling: worth inspecting (or identifying) before selling."""
        m = re.search(r"\{([^}]*)\}", name)
        tags = m.group(1).lower() if m else ""
        if any(f in tags for f in ("excellent", "special", "artifact")):
            return True
        if not self.unique_names:
            self.unique_names = {r.name.lower() for r in self.w.g.races.values() if "UNIQUE" in r.flags}
        return any(u in tags for u in self.unique_names)

    def loot_step(self, state):
        """Fetch items seen within loot_radius (dive and explore share this).
        state: a dict kept by the goal ({'looted': set, 'looting': bool, 'level': t}).
        Returns True while fetching."""
        w = self.w
        lr = int(self.orders.get("loot_radius", 0))
        if state.get("level") != w.level_t:
            state.update(level=w.level_t, looted=set(), looting=False)
        if not lr or w.monsters:
            state["looting"] = False
            return False
        if state["looting"]:
            st = self.mover.tick()
            if st == "moving":
                return True
            state["looting"] = False
            return False
        items = [t for t in self.resolve_target("item") if w.dist(t) <= lr and t not in state["looted"]]
        if items and not self.mover.active:
            tgt = min(items, key=w.dist)
            state["looted"].add(tgt)
            if self.mover.go([tgt]):
                state["looting"] = True
                return True
        return False

    def recall_started(self, now):
        """A Word of Recall is already under way: the server said so ("becomes
        charged", until the level changes or it's cancelled), or we read one in
        the last few seconds and the message hasn't arrived yet. Reading another
        would cancel it."""
        return self.w.recall_pending or now - self.recall_t < 5

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
            if self.resume_after is not None:
                # An emergency interrupted this goal: carry on with it (the
                # Navigator had to re-send its climb after every stair hop)
                self.goal, self.resume_after = self.resume_after, None
                self.log("goal", goal=self.goal.describe(), why="resumed after recovering")
                self.news.append({"t": round(time.time(), 3), "what": "resumed",
                                  "detail": f"{g}: {detail}; resumed '{self.goal.describe()}'", "goal": None})
                return True
            self.notify({"done": "goal_done", "failed": "goal_failed"}.get(status, status),
                        f"{g}: {detail}" if detail else g)
            if status == "failed" and g.startswith("flee"):
                self.flee_failed()
        return True

    def flee_failed(self):
        """A flee that can't reach the stairs, with monsters close: don't go
        idle among them (mission 14: Lagduf's pack, stairs 66 away, the
        Navigator had to read Word of Recall itself) -- start a recall and
        phase out of reach while it charges."""
        w, now = self.w, time.time()
        near = [m for m in w.monsters if w.dist(m[:2]) <= 5]
        if not w.in_dungeon or not near or w.flag("blind") or w.flag("confused"):
            return
        if not self.recall_started(now):
            wor = next((i for i in w.items(tval=TV_SCROLL) if "Word of Recall" in i["name"]), None)
            if wor:
                self.recall_t = now
                self.cmd(f"custom r item={wor['item']}", "flee failed with monsters close: word of recall", hold=0.5)
                self.notify("emergency", f"couldn't reach the stairs with {len(near)} monsters close: read Word of "
                                         "Recall (15-34 turns); phasing while it charges")
                return
        pd = w.tagged("r", 1) or next((i for i in w.items(tval=TV_SCROLL) if "Phase Door" in i["name"]), None)
        if pd and w.adjacent_monsters() and now - self.phase_t > 2.5:
            self.phase_t = now
            self.cmd(f"custom r item={pd['item']}", "flee failed, monsters adjacent: phase door", hold=0.6)

    def idle(self):
        w = self.w
        if w.in_dungeon and not self.idle_recalled and \
                time.time() - self.last_agent > self.orders["idle_recall_s"]:
            self.idle_recalled = True
            self.notify("idle_recall", "no word from the agent: recalling to town")
            self.set_goal(Recall())

    def choke_tick(self, now):
        w = self.w
        lev = w.clvl
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
        if len(pack) < 3 or choke_tier(w.memory, w.pos) is not None or now - self.choke_done_t < 15:
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
            tier = choke_tier(mem, (y, x))
            if tier is not None:
                cands.append((tier, (y, x)))
        if not cands:
            self.choke_done_t = now
            return False
        best = min(t for t, _ in cands)
        cands = [c for t, c in cands if t == best]
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
            # Weak ones (Blue worm masses at clvl 19) are only news: they wake
            # the Navigator for nothing (mission 3)
            lev = w.clvl
            weak = all(r.level <= lev - 10 for r in br) and len(br) < 8
            self.notify("breeders", f"{len(br)} breeding monsters in view ({br[0].name}): leave this level "
                                    "(stairs, or recall)" + (" if they get in the way" if weak else ""), news=weak)

    def town_light(self, now):
        """In town with nothing to do, take the light off: resting in town
        burns fuel ~10x faster (time runs at 1000% while resting, xtra2.c;
        the Advisor's shops memo), which is how Dive04's torches all died.
        keep_light wields it again in the dungeon."""
        w = self.w
        if w.depth != 0 or w.store or now < self.busy_until or now < self.light_t:
            return False
        idle = self.goal is None or isinstance(self.goal, (Wait, RestGoal))
        worn = next((i for i in w.items(equip=True) if i["tval"] == TV_LITE), None)
        if idle and worn and now - self.last_agent > 20:
            self.light_t = now + 5
            self.cmd(f"custom t item={worn['item']}", "in town and idle: light off (it burns while resting)",
                     hold=0.6)
            return True
        return False

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
            # only a light with more left (burnt-out spares were swapped ~2100
            # times while Dive04 idled in town); a lantern in the pack counts
            def left(i):
                t = re.search(r"with (\d+) turns", i["name"])
                return int(t.group(1)) if t else 0
            torch = max((i for i in w.items(tval=TV_LITE) if left(i) > turns),
                        key=left, default=None)
            if torch:
                self.cmd(f"custom w item={torch['item']}", f"fresh torch ({turns} turns left)", hold=0.6)
                return True
            if now - self.light_warned > 120:
                self.light_warned = now
                self.notify("low_supply", f"torch at {turns} turns and no fresher torch: buy torches or a lantern")
        elif not worn and w.depth != 0:
            def light_left(i):
                t = re.search(r"with (\d+) turns", i["name"])
                return int(t.group(1)) if t else (1 if "Lantern" in i["name"] else 0)
            spare = max((i for i in w.items(tval=TV_LITE) if light_left(i) > 0), key=light_left, default=None)
            if spare:
                self.cmd(f"custom w item={spare['item']}", "wield a light", hold=0.6)
                return True
            if now - self.light_warned > 120:
                self.light_warned = now
                self.notify("low_supply", "no light source")
        return False

    def auto_destroy(self, now):
        """Destroy pack items whose pseudo-ID feeling is on the autodestroy list
        (the Navigator was cleaning the pack by hand every few minutes)."""
        w = self.w
        feelings = [f.strip() for f in self.orders.get("autodestroy", "").split(",") if f.strip()]
        if not feelings or now < self.busy_until or now - self.autodestroy_t < 2 or w.inven_dirty:
            return False
        for it in w.items():
            m = re.search(r"\{([^}]*)\}", it["name"])
            if m and any(re.search(rf"\b{re.escape(f)}\b", m.group(1)) for f in feelings) \
                    and "@" not in m.group(1) and "!" not in m.group(1):
                self.autodestroy_t = now
                self.c.send("confirm yes")
                self.cmd(f"custom k item={it['item']} value={it['number']}", f"autodestroy {it['name']}", hold=0.6)
                w.inven_dirty = True
                return True
        return False

    STAT_NAMES = ("STR", "INT", "WIS", "DEX", "CON", "CHR")

    def watch_character(self):
        """Tell the agent when a stat gets drained or the blows change (the
        user lost a blow to a DEX-draining invisible monster)."""
        ind = self.w.ind
        if not ind:
            return
        # Per stat (current, top); a drain lowers current with top unchanged
        # (an equipment change moves both). Missions 5 and 6: a second drain of
        # an already drained stat (DEX 15 -> 14) said nothing when this only
        # compared which stats were drained.
        drained = {n: tuple(ind[f"stat{i}"][:2]) for i, n in enumerate(self.STAT_NAMES)
                   if len(ind.get(f"stat{i}", [])) >= 2}
        blows = ind.get("skills2", [None])[0]
        if self.seen_drained is not None:
            new = [n for n, (cur, top) in drained.items() if n in self.seen_drained
                   and cur < self.seen_drained[n][0] and top == self.seen_drained[n][1]]
            if new:
                full = {"STR": "Strength", "INT": "Intelligence", "WIS": "Wisdom", "DEX": "Dexterity",
                        "CON": "Constitution", "CHR": "Charisma"}
                self.notify("stat_drained", f"{', '.join(new)} drained (blows {blows}); levels don't restore it: "
                            + ", ".join(f"Potion of Restore {full[n]}" for n in new)
                            + " at the Alchemist (5), ~470 each (the Temple doesn't sell them)")
                # Second drain on this level from something in view: leave
                # (Borg memo §3.2; mission 7's scorpion drained STR three times)
                w = self.w
                if w.monsters and w.in_dungeon:
                    n = self.drains_here[1] + 1 if self.drains_here[0] == w.level_t else 1
                    self.drains_here = (w.level_t, n)
                    if n >= 2 and w.find("<>") and not isinstance(self.goal, (Flee, Recall, Recover)):
                        prev = self.goal.describe() if self.goal else None
                        self.set_goal(Flee("stat drain"))
                        self.notify("danger_seen", f"drained twice on this level ({', '.join(new)}) with "
                                                   f"{', '.join(sorted({r.name for *_, r in w.monsters}))} in view"
                                                   f"{' while ' + prev if prev else ''}: leaving the level")
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

        def light_left(i):
            t = re.search(r"with (\d+) turns", i["name"])
            return int(t.group(1)) if t else 0
        # (the best light first: mission 12 put on a 403-turn torch with a
        # full lantern in the pack)
        for it in sorted(w.items(), key=lambda i: -light_left(i) if i["tval"] == TV_LITE else 0):
            if it["tval"] == TV_LITE and light_left(it) == 0:
                continue
            if it["tval"] in (40, 45) and self.unknown_flavour(it):
                continue            # unknown jewellery: 19-58% cursed, sticks, never identifies (Advisor)
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
        # (never during a pending recall: a logout reset its depth once, and
        # Dive03 landed at 1000 ft instead of the @R750 it had asked for)
        safe = not near and w.hp_frac >= 0.7 and not w.store and \
            not (w.last_stairs_cmd and time.time() - w.last_stairs_cmd[1] < 3) and \
            not self.recall_started(time.time()) and not isinstance(self.goal, Recall)
        if safe or time.time() - self.parking > 300:
            self.notify("parked", "logging out for a Pilot update; back in a minute -- "
                                  "re-issue your goal when you see 'started'"
                        + ("" if safe else " (parked after 5 min without a safe moment)"))
            self.c.send("clear")      # empty our server-side command queue first
            with self.att_cond:
                self.att_cond.wait(1.5)   # let a waiting Navigator collect the event
            self.running = False

    def tick(self):
        self.w.drain()
        self.w.refresh()
        self.note_town_stairs()
        if self.wear_queue:
            self.wear_step()
        self.verify_use()
        self.verify_effects()
        self.learn_flavours_tick(time.time())
        w, now = self.w, time.time()
        # Full resync from the server after a level change or a loss (the
        # game-state survey, 2026-10-03: the client's copy is right, ours drifts)
        if (w.need_redraw or self.redraw_level != w.level_t) and now - self.redraw_t > 2:
            self.redraw_t, self.redraw_level = now, w.level_t
            w.need_redraw = False
            self.c.send("redraw")
            w.inven_dirty = True
            w.status_t = 0
        for ts, t in w.messages:
            if ts > self.found_t:
                m = re.match(r"You have (.+) \([a-w]\)\.$", t)
                if m and (self.probably_special(m.group(1)) or re.search(r"\{(good|excellent|special|magical)",
                                                                       m.group(1))):
                    # (mission 14: Farmer Maggot's Lance came into the pack unannounced; it sold for 391)
                    self.notify("found", f"picked up {m.group(1)}: identify it before selling (`sell !NAME`)",
                                news=True)
        self.found_t = now
        while w.losses:
            t, text = w.losses.pop(0)
            self.notify("lost", text, news=True)
        self.audit_tick(now)
        # The wilderness trail: the edge we came in by, per sector (Town goal)
        if self.trail_level != w.level_t and w.arrive_pos is not None:
            self.trail_level = w.level_t
            if w.in_dungeon and (w.depth_ft or 0) > self.deepest_ft:
                self.deepest_ft = w.depth_ft
                try:
                    with open(self.deepest_file, "w") as f:
                        json.dump({"ft": self.deepest_ft}, f)
                except OSError:
                    pass
            if w.depth == 0 or w.in_dungeon:
                self.wild_trail = []
            elif isinstance(self.goal, Town) and self.wild_trail:
                self.wild_trail.pop()             # retracing: one sector closer
            elif edge_of(w.arrive_pos):
                self.wild_trail.append(edge_of(w.arrive_pos))
                if len(self.wild_trail) == 1:
                    self.notify("left_town", f"walked off the town map into the wilderness ({w.depth_ft} ft); "
                                             "'goal town' walks back")
        if w.in_dungeon and w.monsters and now - self.mons_log_t >= 1.0:
            # a steady record for replays (post-mortem memo §4.6: an 86 s gap
            # before the mission-7 death)
            self.mons_log_t = now
            self.log("mons", monsters=[(y, x, r.name) for y, x, r in w.monsters])
        self.watch_character()
        if now - self.weapons_t > 10:
            self.weapons_t = now
            self.watch_weapons()
        self.watch_breeders()
        self.watch_progress()
        self.watch_perception()
        if self.w.recall_cancelled:
            self.w.recall_cancelled = False
            self.notify("recall_cancelled", "a Word of Recall was cancelled (a second one was read): no recall is pending now")
        self.handle_requests()
        if not self.running:
            return
        if self.reflexes():
            return
        if self.parking and not isinstance(self.goal, Recall):
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
            if req.get("since_wait"):
                # a wait report: the news since the previous wait (the survey)
                since, self.news_wait_t = self.news_wait_t, time.time()
                return {"ok": True, "report": self.report(news_since=since)}
            return {"ok": True, "report": self.report()}
        if c == "view":
            # (the observer's viewer: a bigger map, no side effects)
            rows = int(args[0]) if args else 11
            cols = int(args[1]) if len(args) > 1 else 33
            return {"ok": True, "report": self.report(rows=rows, cols=cols, news_since=time.time() - 600)}
        if c == "viewmap":
            # (the observer's colour map: chars + attrs around @; monsters with
            # their monster.txt colour, since our glyph table recodes them)
            w = self.w
            rows_n = int(args[0]) if args else 11
            cols_n = int(args[1]) if len(args) > 1 else 33
            if not w.rows or not w.pos:
                return {"ok": True, "rows": [], "attrs": []}
            y0, x0 = max(0, w.pos[0] - rows_n), max(0, w.pos[1] - cols_n)
            y1, x1 = min(len(w.rows), w.pos[0] + rows_n + 1), w.pos[1] + cols_n + 1
            return {"ok": True, "y0": y0, "x0": x0, "pos": w.pos,
                    "rows": [r[x0:x1] for r in w.rows[y0:y1]],
                    "attrs": [a[x0:x1] for a in w.attrs[y0:y1]] if w.attrs else [],
                    "mons": [[y, x, r.color] for y, x, r in w.monsters]}
        if c == "note":
            return {"ok": True, "text": self.user_note(" ".join(args))}
        if c == "say":
            # the Navigator answering the user (shown in the observer's viewer)
            text = " ".join(args)
            self.log("nav_say", text=text)
            with open(os.path.join(self.rundir, "commentary.jsonl"), "a") as f:
                f.write(json.dumps({"t": round(time.time(), 3), "who": "navigator", "note": text}) + "\n")
            return {"ok": True, "text": "said"}
        if c == "monster":
            return {"ok": True, "text": self.monster_info(" ".join(args).replace("_", " "))}
        if self.dead and c not in ("attention", "quit", "orders", "events", "news", "map", "inventory",
                                   "note", "view", "say", "viewmap") and \
                not (c == "goal" and args[:1] == ["resurrect"]):
            return {"ok": False, "error": "the character is dead (a ghost): only 'goal resurrect' works"}
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
            out = {"ok": True, "orders": self.orders}
            md = int(self.orders.get("max_depth", 0) or 0)
            if md:
                # the Borg's warrior gate (the Advisor's progression memo):
                # clvl x 50 ft to 1000 ft, then (clvl - 5) x 50; never past 1000 ft without FA
                lev = self.w.clvl
                gate = lev * 50 if lev <= 20 else max(1000, (lev - 5) * 50)
                warn = []
                if md > gate:
                    warn.append(f"max_depth {md} ft is deeper than the gate for clvl {lev} ({gate} ft)")
                if md > 1000 and not self.has_ability("free_action"):
                    warn.append("below 1000 ft without Free Action")
                if warn:
                    out["note"] = "careful: " + "; ".join(warn) + " (HANDBOOK stage table)"
            return out
        if c in self.ACTIONS:
            key = self.ACTIONS[c]
            if not args:
                return {"ok": False, "error": f"usage: {c} ITEMLETTER"}
            try:
                if c in ("destroy", "drop", "quaff", "read", "eat", "fuel") and not \
                        (len(args[0]) == 1 or args[0].isdigit()):
                    # by name: only the pack (a name that matched nothing there once
                    # fell through to the equipment -- "You destroy (nothing)")
                    name = args[0].replace("_", " ").lower()
                    it = next((i for i in self.w.items() if name in i["name"].lower()), None)
                    if it is None:
                        return {"ok": False, "error": f"nothing in the pack matches '{args[0]}'"}
                    item = it["item"]
                else:
                    item = self.item_index(args[0], equip=(c == "takeoff"))
            except ValueError as e:
                return {"ok": False, "error": str(e)}
            extra = ""
            if c == "read" and "Word of Recall" in next((i["name"] for i in self.w.inven if i["item"] == item), "") \
                    and self.recall_started(time.time()) and "force" not in args[1:]:
                return {"ok": False, "error": "a recall is already under way: reading another cancels it "
                                              "(add 'force' to cancel it on purpose)"}
            iname = next((i["name"] for i in self.w.inven if i["item"] == item), "")
            if c == "read" and "Word of Recall" in iname and self.w.depth == 0 and recall_level(iname) is None \
                    and "force" not in args[1:]:
                return {"ok": False, "error": f"'{iname}' has no valid @R inscription: it would recall to the "
                                              "deepest level ever reached. Inscribe it (inscribe ITEM @R<feet>), "
                                              "use goal recall (it inscribes max_depth), or add 'force'"}
            if c in ("destroy", "drop"):
                n = args[1] if len(args) > 1 else "1"
                if n == "all":
                    it = next((i for i in self.w.inven if i["item"] == item), None)
                    n = it["number"] if it else 1
                extra = f" value={n}"
                if c == "destroy":
                    self.c.send("confirm yes")
            if c in ("aim",):
                extra = f" dir={args[1] if len(args) > 1 else 5}"
            if c == "read" and len(args) > 1 and args[1] != "force":
                # A scroll that works on another item (Identify, Enchant...): the
                # client sends that item in the direction byte (COMMAND_SECOND_DIR);
                # without it the server picked the first pack item
                try:
                    target = self.item_index(args[1], equip=True)
                except ValueError as e:
                    return {"ok": False, "error": str(e)}
                extra = f" dir={target}"
            t0 = time.time()
            before = (self.effect_sig("pack"), self.effect_sig("equip"))
            self.cmd(f"custom {key} item={item}{extra}", f"agent: {c} {args}")
            pack = self.pack_now()
            noise = ("You enter a maze", "Looks like", "You feel", "You hear", "You have found")
            said = [t for ts, t in self.w.messages if ts >= t0 and not t.startswith(noise)]
            out = {"ok": True, "said": said[-4:], "pack": pack}
            if c != "inspect" and (self.effect_sig("pack"), self.effect_sig("equip")) == before:
                # (the game-state survey: never report as done what didn't happen)
                out["note"] = "no change in the pack or equipment yet: it may not have happened"
            return out
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
            if not isinstance(self.goal, Recall):
                self.set_goal(None)       # a pending recall is allowed to finish first
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
            md = int(self.orders.get("max_depth", 0))
            if md and g.target_ft > md:
                # say so (a 'dive 700' was silently capped by max_depth 650)
                self.set_goal(g)
                return {"ok": True, "goal": g.describe(),
                        "note": f"capped at max_depth {md} ft (order max_depth=... to change)"}
        elif name == "explore":
            kw = dict(a.split("=", 1) for a in rest if "=" in a)
            g = Explore(until=kw.get("until"), radius=int(kw["radius"]) if "radius" in kw else None)
        elif name == "goto":
            g = Goto(" ".join(rest))
        elif name == "shop":
            # goal shop STORE [buy NAME:N]... [sell LETTER:N]...
            list_stock = "list" in rest[1:]
            rest = [a for i_, a in enumerate(rest) if not (i_ and a == "list")]
            buys, sells, i = [], [], 1
            while i < len(rest):
                kind, spec = rest[i], rest[i + 1] if i + 1 < len(rest) else ""
                what, _, n = spec.rpartition(":")
                what, n = (what, n) if what else (spec, "1")
                n, _, cap = n.partition("@")        # NAME:COUNT@MAXPRICE (each)
                n = int(n)
                if kind == "buy":
                    buys.append((what.replace("_", " "), n, int(cap) if cap else None))
                elif kind == "sell":
                    key = what.replace("_", " ")
                    sells.append((self.item_index(key) if len(key) == 1 else key, n))   # '!NAME' forces
                i += 2
            g = Shop(rest[0], buys, sells, list_stock=list_stock)
        elif name == "search":
            g = Search()
        elif name == "hunt":
            g = Hunt(" ".join(rest).replace("_", " "))   # 'hunt Black_ogre', like shop names
        elif name == "recall":
            g = Recall()
        elif name == "town":
            g = Town()
        elif name == "townfarm":
            if not rest:
                return {"ok": False, "error": "usage: goal townfarm GOLD [MINUTES]"}
            g = TownFarm(rest[0], rest[1] if len(rest) > 1 else 10)
        elif name == "resurrect":
            g = Resurrect()
        elif name == "rest":
            g = RestGoal()
        elif name == "wait":
            g = Wait(rest[0] if rest else 5)
        else:
            return {"ok": False, "error": f"unknown goal {name}"}
        self.set_goal(g)
        return {"ok": True, "goal": g.describe()}

    # --- the situation report ------------------------------------------------

    def report(self, rows=11, cols=33, news_since=None):
        w = self.w
        ind = w.ind
        lines = []
        stats = " ".join(f"{s}:{v[0] if v[0] <= 18 else '18/%02d' % (v[0] - 18)}"
                         for s, v in zip(("STR", "INT", "WIS", "DEX", "CON", "CHR"),
                                         (ind.get(f"stat{i}", [0]) for i in range(6))))
        lines.append(f"{ind.get('hist_name_', '?')} the {ind.get('race_', '?')} {ind.get('class_', '?')}, "
                     f"level {w.clvl}" + (f" (max {ind['level'][0]})" if len(ind.get('level', [])) > 1 and ind['level'][0] != w.clvl else "") + f", HP {w.hp[0]}/{w.hp[1]}, "
                     f"{'Town' if not w.depth else str(w.depth_ft) + ' ft'}, gold {ind.get('gold', [0])[0]}, "
                     f"blows {ind.get('skills2', ['?'])[0]}, speed {ind.get('speed', [0])[0]}")
        cond = [k for k in ("blind", "confused", "afraid", "poisoned", "cut", "stun") if w.flag(k)]
        hunger = {0: "Weak", 1: "Weak", 2: "Hungry", 3: "Fed", 4: "Full", 5: "Gorged"}.get(w.hunger, w.hunger)
        lines.append(f"{stats}  | {hunger}" + (f" | {', '.join(cond)}" if cond else "")
                     + (" | resting" if w.resting else ""))
        lines.append(f"Standing on: {w.standing_on or 'floor/unknown'}"
                     f"{' (item: ' + w.floor + ')' if w.floor else ''}"
                     f"{' (arrived by ' + w.arrived_by + ')' if w.arrived_by else ''}"
                     f" | goal: {self.goal.describe() if self.goal else 'none (idle)'}")
        lines.append("Equipment: " + "; ".join(i["name"] for i in w.items(equip=True)))
        lines.append("Pack: " + "; ".join(f"{chr(97 + i['item'])}) {self.show(i)}" for i in w.items()))
        if w.rows and w.pos:
            y0, x0 = w.pos
            # Every row, numbered, and the column range: blank rows used to be
            # dropped, so line numbers didn't match rows (mission 13)
            lines.append(f"Map (you are @ at {y0},{x0}; columns {max(0, x0 - cols)}-{x0 + cols}; "
                         "each line starts with its row):")
            for y in range(max(0, y0 - rows), min(len(w.rows), y0 + rows + 1)):
                seg = w.rows[y][max(0, x0 - cols):x0 + cols + 1]
                lines.append(f"  {y:2d}|" + seg.rstrip())
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
        near_items = sorted(self.resolve_target("item"), key=w.dist)[:8] if w.pos else []
        if near_items:
            lines.append("Item squares nearby (glyph at y,x, distance): " + ", ".join(
                f"{w.memory.get(p, '?')} at {p[0]},{p[1]} ({w.dist(p)})" for p in near_items)
                + "  -- 'goal goto Y,X' then 'pickup'")
        stairs = w.find("<>")
        if stairs:
            near = sorted(stairs, key=w.dist)[:4]
            lines.append("Known stairs: " + ", ".join(f"{w.memory[p]} at {p[0]},{p[1]} ({w.dist(p)} away)"
                                                     for p in near))
        # Consumables at a glance (also in --brief: the Navigator decided
        # without the pack, the game-state survey)
        cons = [self.show(i) for i in w.items(tval=(TV_POTION, TV_SCROLL, TV_FOOD, TV_FLASK, 55, 65, 66, 40, 45))]
        drained = [n for n, (cur, top) in (self.seen_drained or {}).items() if cur < top]
        lines.append("Supplies: " + ("; ".join(cons) or "none")
                     + (f" | RECALL PENDING (read {time.time() - w.recall_pending_t:.0f} s ago; it takes "
                        "15-34 turns)" if w.recall_pending else "")
                     + f" | max_depth {self.orders.get('max_depth')}"
                     + (f" | drained: {', '.join(drained)}" if drained else ""))
        wt = self.weapon_table()
        if wt:
            lines.append("Weapons (blows, avg damage per round at your STR/DEX): " + "; ".join(
                f"{'WIELDED ' if eq else ''}{n} {b} blows ~{d:.0f}" for n, b, d, eq in wt))
        if w.flags:
            # from the character sheet's grid (tool query 'flags'): facts, not guesses
            ab = [k for k, v in w.flags.items() if v and k not in ("stealth", "search", "infra", "tunnel")]
            lines.append("Abilities: " + (", ".join(ab) if ab else "none"))
        if self.audit_runs:
            lines.append(f"State audit: {self.audit_runs} checks"
                         + ("; differences: " + ", ".join(f"{k} {n}" for k, n in self.audit_counts.items())
                            if self.audit_counts else ", no differences"))
        # News of the last 10 minutes, every time (status calls used to clear it)
        recent = [e for e in self.news if (e["t"] > news_since if news_since is not None
                                           else time.time() - e["t"] < 600)][-12:]
        if recent:
            lines.append("Since last report: " + " | ".join(
                f"{time.strftime('%H:%M:%S', time.localtime(e['t']))} {e['what']}: {e['detail']}" for e in recent))
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
            if pilot.running:        # (a quiet timeout gets one too: mission 3 missed a stall)
                reply = queue.Queue()
                pilot.requests.put(({"cmd": "status", "since_wait": True}, reply))
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
    # --hpwarn 0: no time bubble slowdown at low HP for now. The pilot's timers
    # (holds, step timeouts, potion/phase spacing) are wall-clock, and at 30%
    # HP time runs at 30%: in mission 7 re-plans fired between our turns.
    client = MangClient(args.client, args.libdir, nick,
                        args.passfile or os.path.join(priv, nick.lower() + ".pass"),
                        args.host, args.port, config=args.config or os.path.join(priv, nick.lower() + ".mangrc"),
                        cwd=repo, pktlog=args.pktlog, extra_args=["--visuals", visuals, "--hpwarn", "0"])
    say = lambda *a: print(time.strftime("%H:%M:%S"), *a, file=sys.stderr, flush=True)
    pilot = None
    try:
        ready = client.wait_ready()
        say(f"in the game as {nick}: {ready}")
        pilot = Pilot(client, rundir, say=say)
        orig = pilot.w._on_event
        bulky = {"map", "status", "inven", "options", "commands"}   # query replies
        pilot.w.c.log = lambda ev: (orig(ev), ev.get("ev") in bulky or evlog.write(json.dumps(ev) + "\n"))
        # disturb_near/disturb_panel: the server stops a run the moment a monster
        # in view moves, or at a sector edge (faster than our polling at run
        # speed; the Advisor's running memo). disturb_move stays as the user plays.
        for opt in ("avoid_other", "stack_force_costs", "disturb_near", "disturb_panel"):
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
        if pilot is not None and pilot.dead:
            # keep answering status/attention so the Navigator learns of the death
            pilot.running = True
            while pilot.running:
                pilot.handle_requests()
                time.sleep(0.2)
            say("pilot stopping (dead)")
        sys.exit(1)
    finally:
        client.quit()


if __name__ == "__main__":
    main()
