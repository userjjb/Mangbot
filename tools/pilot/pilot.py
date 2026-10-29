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
import functools
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
try:
    # the code's version (major.minor.patch, CHANGELOG.md; minor = play can differ, patch = it can't): read once at
    # startup, so it names the code this Pilot runs
    VERSION = open(os.path.join(HERE, "..", "..", "VERSION")).read().strip()
except OSError:
    VERSION = "?"
sys.path.insert(0, os.path.join(HERE, "..", "shopcat"))

from mang import MangClient, ClientExited      # noqa: E402
import glyphs                                   # noqa: E402
from world import (World, gnow, set_time_factor, time_factor, model_factor, wall_of, wall_since, waited,  # noqa: E402
                   ghold, light_fuel, set_fast_ok, measured_rate, _lt, frozen)
import structures                                # noqa: E402
import shadow                                    # noqa: E402
import geareval                                  # noqa: E402
import itemvalue                                 # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "observe"))
import shopmath                                  # noqa: E402
from mover import Mover, direction, passable, plan, drain_zone_of, MAX_HGT, MAX_WID   # noqa: E402

TV_SCROLL, TV_POTION, TV_FOOD, TV_FLASK, TV_LITE = 70, 75, 80, 77, 39
PY_FOOD_MAX = 15000          # Gorged (-10 speed) from here (mdefines.h)
SHOP_CUT = 0.38   # what a shop pays Dive04 of an item's value at CHR 3 (shopmath: 34-43%; Black Market 10%)
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


# Brand egos: x3 on the dice against monsters that don't resist the element
# (mission 21 compared a Lucerne Hammer of Venom at ~18 a round, brand ignored)
BRANDS = {"Venom": "poison", "Burning": "fire", "Flame": "fire", "Freezing": "cold", "Frost": "cold",
          "Melting": "acid", "Lightning": "lightning"}


def weapon_brand(name):
    """(element, multiplier) for a brand ego, else None."""
    m = re.search(r"\bof (\*?)(" + "|".join(BRANDS) + r")\b", name)
    return (BRANDS[m.group(2)], 3) if m else None


def weapon_damage(name, blows, mult=1):
    """Average damage per round: (dice average + to-dam) x blows."""
    m = re.search(r"\((\d+)d(\d+)\)", name)
    if not m:
        return 0.0
    dice = int(m.group(1)) * (int(m.group(2)) + 1) / 2 * mult
    b = re.search(r"\([+-]\d+,([+-]\d+)\)", name)
    return (dice + (int(b.group(1)) if b else 0)) * blows


def shadow_agree(choice, actual, table):
    """(agree, the actual action's row) for an estimator answer: the estimator chose the action the Pilot took; or it
    kept its copy of the rules ("rules") and the action the Pilot took (when the table has a row for it) is safe and
    within noise of the best row (2 SE, at least 10 XP net of gold)."""
    rows = {t.get("option"): t for t in table or ()}
    row = rows.get(actual) if actual != "rules" else None
    if choice == actual:
        return True, row
    if choice == "rules":
        if row is None:
            return True, None
        best = max((t.get("dxp", 0) for t in rows.values() if t.get("safe")), default=0)
        return bool(row.get("safe")) and row.get("dxp", 0) >= best - max(10, 2 * (row.get("se") or 0)), row
    return False, row


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


def type_word(name):
    """'Amber Amulet' / 'Scroll titled "foo"' / 'Potion of Speed' -> 'Amulet' / 'Scroll' / 'Potion' (None if
    none): a flavour and the kind it's paired with must agree on it (refactor-candidates A2)."""
    n = re.sub(r'"[^"]*"', "", name).split(" of ")[0]
    m = re.search(r"\b(Potion|Scroll|Wand|Staff|Rod|Ring|Amulet|Mushroom)s?\b", n)
    return m.group(1) if m else None


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
    "autowear": "on",      # off: the Pilot doesn't wear, wield or swap gear by itself (upgrade_step)
    "enchant_max": 25,     # Scrolls of Enchant Armor plan town may buy a visit (0: none) -- m58: 25 for 5025 gold, unasked
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
    "band_frac": 0.5,            # a band is serious (leave) when fighting it all costs more than this x HP
    "nopickup": "",              # comma list of name parts never picked up (the Navigator's per-trip junk list)
    "max_depth": 0,              # feet; 0 = no limit. Dives stop there, explore refuses below it,
                                 # and after an emergency trip down the stairs we come back up
}


class Attention(Exception):
    pass


# --------------------------------------------------------------------------
# Goals: tick(pilot) -> None (still working) or (status, detail)
# --------------------------------------------------------------------------

def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


class Goal:
    name = "goal"

    def describe(self):
        return self.name

    def tick(self, p):
        return ("done", None)


class Wait(Goal):
    def __init__(self, secs):
        self.until = gnow() + float(secs)
        self.name = f"wait {secs}"

    def tick(self, p):
        return None if gnow() < self.until else ("done", None)


class Goto(Goal):
    def __init__(self, target, force=False):
        self.target = target
        self.force = force
        self.name = f"goto {target}" + (" force" if force else "")
        self.started = False
        self.arrived_t = None
        self.held_warned = False

    def tick(self, p):
        w = p.w
        # Walking away from a dangerous monster next to us hands it free hits
        # (mission 15: a goto written for an older report walked two steps
        # beside Brodda): hold and let auto-retaliate fight, unless forced
        bad = [r for *_, r in w.adjacent_monsters() if p.danger_why(r)] if w.in_dungeon and not self.force else []
        # ... and anything faster than us that is hitting us: it keeps up and
        # hits every step (mission 18: a Nighthawk took 215 -> 102 HP over 25 s
        # of a goto; a 'hunt' killed it in seconds)
        if not bad and w.in_dungeon and not self.force and gnow() - w.last_hit_t < 2:
            mine = 110 + int(w.ind.get("speed", [0])[0] or 0)
            bad = [r for *_, r in w.adjacent_monsters() if r.speed > mine and "NEVER_MOVE" not in r.flags]
        if bad:
            if p.mover.active:
                p.mover.stop()
                self.started = False
            if not self.held_warned:
                self.held_warned = True
                p.notify("tactic", f"goto held: {bad[0].name} is adjacent (walking away gives it free hits); "
                                   "it fights on. `goal leave` or `goal recall` to get away")
            return None
        self.held_warned = False
        if self.arrived_t:
            # An item underfoot is picked up ~0.6 s after arriving: report after
            # that, or the Navigator sees it still on the floor (mission 5)
            if any(ts > self.arrived_t and t.startswith(("You have ", "You have no room")) for ts, t in w.messages) \
                    or waited(self.arrived_t, 1.5):
                w.inven_dirty = True
                return ("done", None)
            return None
        if not self.started:
            goals = p.resolve_target(self.target)
            if not goals:
                return ("failed", f"no such place: {self.target}")
            if w.pos in goals:
                return ("done", None)
            if not p.mover.go(goals, unknown=True):
                return ("failed", "no known path, nor one through unexplored squares")
            if p.mover.unknown:
                p.notify("tactic", "goto: no known path; trying one through unexplored squares", news=True)
            self.started = True
        st = p.mover.tick()
        if st == "arrived":
            if any(gnow() - ts < 1.0 and t.startswith("You see ") and "no items" not in t
                   for ts, t in w.messages):
                self.arrived_t = gnow()
                return None
            return ("done", None)
        if st == "stuck":
            return ("failed", "stuck")
        return None


class Explore(Goal):
    """Walk to the nearest frontier (known floor next to unknown) until none is
    left, or until stairs are seen (until='stairs')."""

    def __init__(self, until=None, radius=None, skip=None):
        self.until = until
        self.radius = radius
        self.skip = skip            # () -> stairs squares that don't count as seen (a dive's refused ones)
        self.name = "explore" + (f" until {until}" if until else "") + (f" radius {radius}" if radius else "")
        self.center = None
        self.fails = 0
        self.target = None
        self.no_run_at = None
        self.run_from = None
        self.last_diag = None
        self.loot = {}
        self.search = None
        self.searched_n = 0
        self.retried = False

    def stairs_seen(self, w):
        """'stairs down seen' / 'stairs up seen' when the stairs `until` asks for are known and reachable,
        not counting those in skip()."""
        skip = self.skip() if self.skip else set()
        want = {"stairs": ">", "upstairs": "<"}.get(self.until)
        found = [q for q in w.find(want) if q not in skip] if want else []
        if found and plan(w, found):
            return "stairs down seen" if want == ">" else "stairs up seen"
        return None

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
        # (not stairs the dive refused: m30 stalled 6 minutes at 600 ft, this ending at once on the '>' it had
        # just refused as the way back to a fled level, and the dive starting it again, with nothing logged)
        seen = self.stairs_seen(w)
        if seen:
            return ("done", seen)
        if p.level_seen != w.level_t:
            p.level_seen = w.level_t
            p.unreachable = set()
            p.visited = set()
        if self.search:
            r = self.search.tick(p)
            if r is None:
                return None
            self.searched_n += self.search.done_n
            self.search = None
            if r[0] == "failed":
                return ("done", f"nothing left to explore (searched {plural(self.searched_n, 'dead end')})")
            # a secret door showed up: explore on through it (what was unreachable may not be now)
            p.unreachable = set()
            self.fails = 0
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
        zone = drain_zone_of(w) | w.avoid_zone   # (never explore beside a drainer, nor into an avoid zone)
        frontier = [f for f in p.frontier(center=self.center if self.radius else None, radius=self.radius)
                    if f != w.pos and f not in p.visited and f not in zone]
        if not frontier:
            # Rubble next to unknown ground is a way on (the user: corridors never
            # dead-end, at worst there's a 1-thick wall of rubble): dig through
            frontier = [f for f in p.frontier(center=self.center if self.radius else None,
                                              radius=self.radius, rubble=True)
                        if f != w.pos and f not in p.visited]
        if not frontier:
            # Corridor dead ends hide secret doors (the user, mission 16: a 500 ft
            # level "explored" in 40 s, and a 550 ft dead end with a door): search
            # those we haven't yet before calling the level done
            if not self.radius and Search.dead_ends(w, strict=True, skip=p.searched):
                self.search = Search(tries=15, strict=True)
                return None
            rooms = [f"{st['kind']} at {Y},{X}" for Y, X, st in p.structures_here()
                     if st["kind"] in ("large room", "inner room")
                     and not all((w.level_t, r) in p.searched for _, r in structures.door_spots(Y, X))
                     and not p.room_door(Y, X)]
            return ("done", "nothing left to explore" +
                    (f" (searched {plural(self.searched_n, 'dead end')})" if self.searched_n else "") +
                    (f"; not opened: {', '.join(rooms)} ('goal searchroom Y,X')" if rooms else ""))
        # (targets we failed to reach are dropped from the frontier, not avoided
        # as path squares: that once made walked corridors impassable)
        if self.fails > 10 or not p.mover.go(frontier):
            if p.mover.forget_bump_walls() or (self.fails > 10 and p.unreachable and not self.retried):
                # (go() already retried without bump walls; after many fails,
                # forget what failed once: monsters in the way move on)
                p.unreachable = set()
                self.fails = 0
                self.retried = True
                return None
            # Walled in with known ground out of reach (a teleport or a trap door into a pocket): its dead
            # ends may hide the way out (set-piece D3)
            if not self.radius and Search.dead_ends(w, strict=True, skip=p.searched):
                self.search = Search(tries=15, strict=True)
                return None
            return ("failed", "frontier unreachable")
        self.target = p.mover.path[-1] if p.mover.path else None
        # In a corridor with nothing about: run along it the way the path
        # starts, and let the run follow the corridor (as the user explores)
        # Run instead of walking hop by hop: along corridors (the run follows
        # them), and across dark rooms, where the unknown is always just one
        # square away (60 of 71 explore plans were single steps)
        # (also with a radius -- the dive's pillared-room explore: a radius limits which frontier is chosen,
        # not how we get there; without runs it zig-zagged diagonally down two-wide corridors, m25, the user)
        m = p.mover
        if m.path and not m._monster_near(5) and \
                (m.in_corridor() or len(m.path) <= 2) and self.no_run_at != w.pos and not m.run_loop(w.pos):
            d = direction(w.pos, m.path[0])
            # Two-wide corridors: the nearest frontier is always in the other lane,
            # so plans alternate diagonals (9, 7, 9...) and each diagonal run is a
            # single step at walking speed (the Advisor's mission 15 answers: ~6%
            # of the mission). After two alternating diagonals, run along the axis.
            vert, hor = {7: 8, 9: 8, 1: 2, 3: 2}, {7: 4, 1: 4, 9: 6, 3: 6}
            if d in vert and self.last_diag in vert and self.last_diag != d:
                if vert[d] == vert[self.last_diag]:
                    d = vert[d]
                elif hor[d] == hor[self.last_diag]:
                    d = hor[d]
            self.last_diag = d if d in vert else None
            if d:
                self.run_from = w.pos
                m.free_run(d)
        return None


class Dive(Goal):
    """Stair-scum down to target_ft (the user's way to dive): on arrival, if a
    '>' is known and reachable, take it; else go back up and down for a fresh
    level. Not on stairs and none known: explore until some are seen."""

    FLED_HOLD = 120         # seconds the stairs back to a level just fled are refused

    def __init__(self, target_ft, scum=False):
        self.target_ft = int(target_ft)
        self.scum = scum         # a climb may go down a '>' for a fresh level
        self.name = f"dive {self.target_ft}ft"
        self.start_ft = None
        self.level_seen = None
        self.pending = None      # stairs command sent at time t
        self.walking = False
        self.explore = None
        self.reported = set()
        self.probed = None
        self.loot = {}              # (the shared loot step's state)
        self.pillared_done = False
        self.need_search = False
        self.stuck = 0
        self.explore_fails = 0
        self.bad_stairs = set()     # (level, tile) of stairs we couldn't reach
        self.bad_t = {}
        self.bad_cleared = 0
        self.located = None         # level we used Door/Stair Location on

    def locate_stairs(self, p):
        """No stairs known on a fresh level: use a Staff (or zap a Rod) of
        Door/Stair Location once (mission 18 explored 9 min at 550 ft for a '>'
        with one in the pack, unknown to the character). True if used."""
        w = p.w
        if self.located == w.level_t:
            return False
        if p.use_stair_location("dive: no stairs known"):
            self.located = w.level_t
            return True
        return False

    def tick(self, p):
        w = p.w
        # an interesting item was just reported: pause so the Navigator can fetch
        # it (mission 16: the dive took the stairs before its goto arrived)
        if gnow() < p.item_hold_until and not p.dangers():
            return None
        md = int(p.orders.get("max_depth", 0))
        if md and self.target_ft > md:
            self.target_ft = md
            self.name = f"dive {md}ft (max_depth)"
        up = self.target_ft < self.start_ft if self.start_ft is not None else False
        if self.start_ft is None:
            self.start_ft = w.depth_ft
            up = self.target_ft < self.start_ft
        want, other = ("<", ">") if up else (">", "<")
        self.want = want             # (the stationary-monster check asks: take these stairs beside a mold)
        if (not up and w.depth_ft >= self.target_ft) or (up and w.depth_ft <= self.target_ft):
            return ("done", f"reached {w.depth_ft} ft")
        if self.pending and w.level_t < self.pending and not waited(self.pending, 3):
            return None           # waiting for the level change
        self.pending = None
        # leaving town: the light on before the stairs, as Recall does before reading (the user:
        # a couple of turns of light, and nobody has to check it)
        if w.depth == 0 and not up and not any(i["tval"] == TV_LITE for i in w.items(equip=True)) and \
                gnow() - getattr(self, "light_t", 0) > 2:
            self.light_t = gnow()
            if p.wear_light("going down"):
                return None
        if not waited(w.level_t, 0.6):
            return None           # let the new level's map arrive
        if w.level_t != self.level_seen:
            self.level_seen = w.level_t
            self.walking = False
            self.explore = None
            self.pillared_done = False
            why = p.interesting() if getattr(self, "stop", True) else None
            if why:
                return ("interesting", why)
        # Standing orders that save asking the agent: loot what's close...
        # (the shared loot step: what's close, what was passed up while monsters were in view, valuables)
        # (m49, leaving a breeders level: two gold piles beside the path to the stairs were walked past -- the user:
        # "money walked by for no reason". The walk loots only before it sets off; now it stops for loot within
        # LOOT_PATH_R, and walks on after)
        if self.walking and not self.loot.get("looting") and p.loot_beside():
            p.mover.stop()
            self.walking = False
        if not self.walking and (not p.mover.active or self.loot.get("looting")) and p.loot_step(self.loot):
            return None
        # ... and explore a pillared room for a '>' (the user: they often hold stairs)
        if p.orders.get("pillared") == "explore" and not self.pillared_done and not w.find(want) \
                and p.pillared():
            if self.explore is None:
                self.explore = Explore(until="upstairs" if want == "<" else "stairs", radius=15, skip=self.refused)
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
        # Just fled from the level these stairs lead to, arriving here: not straight back (find another)
        fl = getattr(p, "fled_from", None)
        # (not when the way back is the way up to max_depth: m27 fled down to 700 ft past max_depth 650 and this kept
        # it there 4 minutes)
        md_now = int(p.orders.get("max_depth", 0))
        # (for FLED_HOLD only, longer on a level the server keeps: m45 refused the only '<' 4.5 minutes after fleeing
        # a band and spent 10 minutes in a Giant flea swarm looking for another; the level behind it is a fresh one.
        # On the test server -- one player, so a level is freed when we leave it -- no hold at all (the user, 10-26),
        # unless the level is kept: one we've seen the server keep (p.kept), or the one we logged in on (our own
        # previous logout made it static). Operations.md, Level persistence)
        kept = fl and (fl[0] in getattr(p, "kept", ()) or (len(fl) > 3 and fl[3]))
        hold = 300 if kept else self.FLED_HOLD if getattr(p, "live", False) else 0
        back = fl and fl[2] == w.level_t and fl[0] == w.depth + (-1 if up else 1) and not waited(fl[1], hold) and \
            not (up and md_now and w.depth_ft > md_now)
        if back and w.standing_on == want and (w.level_t, w.pos) not in self.bad_stairs:
            self.bad_stairs.add((w.level_t, w.pos))
            self.bad_t[(w.level_t, w.pos)] = fl[1] + hold - 15       # (expire_bad frees it when the hold ends)
            p.notify("tactic", f"not taking these stairs back to {fl[0] * 50} ft, which we just fled: looking for "
                               "other stairs", news=True)
        if w.standing_on == want and (w.level_t, w.pos) not in self.bad_stairs:
            return self._stairs(p, want)
        downs = [d for d in downs if (w.level_t, d) not in self.bad_stairs]
        if downs and not self.walking:
            if p.mover.go(downs):
                self.walking = True
            else:
                self.mark_bad(w, downs)
        if self.walking:
            st = p.mover.tick()
            # (on the stairs only: a step-away retargets the shared mover, and its "arrived" pressed '>' 6
            # squares from them, m25)
            if st in ("arrived", "idle") and w.pos in downs:
                self.walking = False
                return self._stairs(p, want)
            if st == "arrived":
                self.walking = False
                return None
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
        # deeper: never, unless asked ('goal dive FEET scum'), then only a close
        # one and never below max_depth (mission 11: at 50 ft on the way to town
        # it walked 15 squares to a '>' and went to 100 ft; mission 17: a climb
        # to town went down from 100 to 150 ft with the budget nearly spent)
        md = int(p.orders.get("max_depth", 0))
        climbing = want == "<"
        scum_ok = not climbing or (self.scum and (not md or w.depth_ft + 50 <= md))
        # Scum: back the way we came on the staircase we're on, then again -- unless this level is one the
        # server keeps (arrived on the very square we scummed from before: m25 took '<' and '>' between
        # 250 and 300 ft ~150 times in 4 minutes, landing on 33,24 each time): then explore it for a '>'
        # (kept on the Pilot: the trip plan starts a fresh Dive goal for each leg)
        if not hasattr(p, "scummed"):
            p.scummed, p.kept = set(), set()
        self.scummed, self.kept = p.scummed, p.kept
        here = (w.depth, w.arrive_pos)
        if w.standing_on == other and scum_ok and w.arrive_pos and here in self.scummed and w.depth not in self.kept:
            self.kept.add(w.depth)
            p.notify("tactic", f"{w.depth_ft} ft is a level the server keeps (back on {w.arrive_pos[0]},"
                               f"{w.arrive_pos[1]} after scumming): exploring it for a '{want}' instead", news=True)
        if w.standing_on == other and scum_ok and w.depth not in self.kept:
            if w.arrive_pos:
                self.scummed.add(here)
            return self._stairs(p, other)
        # No stairs of the kind we want known: a Door/Stair Location device maps them (m38 arrived at 700 ft on a '>'
        # and explored ~10 minutes for a '<' with the rod in the pack: "no stairs at all" never held)
        if w.depth and not w.find(want) and waited(w.level_t, 1.0) and not w.monsters and self.locate_stairs(p):
            return None
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
                Explore(until="upstairs" if want == "<" else "stairs", skip=self.refused)
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
        if r and str(r[1]).startswith("nothing left to explore") and w.find("<>") and self.bad_stairs:
            # Stairs are known but were marked unreachable (e.g. planned before
            # the map had loaded): try them again, a few times
            self.bad_cleared += 1
            if self.bad_cleared > 3:
                return ("failed", "stairs known but unreachable, nothing left to explore")
            self.bad_stairs = set()
            self.explore = None
            return None
        if r and str(r[1]).startswith("nothing left to explore") and not w.find("<>"):
            # Walled in: look for secret doors, then explore again
            self.need_search = True
        if r:
            self.explore = None
        return None

    def refused(self):
        """Stairs on this level the dive won't take (unreachable, or the way back to a level just fled)."""
        return {q for lt, q in self.bad_stairs if lt == self.level_seen}

    def mark_bad(self, w, tiles):
        now = gnow()
        for t in tiles:
            self.bad_stairs.add((w.level_t, t))
            self.bad_t[(w.level_t, t)] = now

    def expire_bad(self, w):
        """Unreachable stairs get another try after 15 s (the map fills in)."""
        now = gnow()
        for k in [k for k, t in self.bad_t.items() if now - t > 15]:
            self.bad_stairs.discard(k)
            del self.bad_t[k]

    def _stairs(self, p, which):
        p.take_stairs(which)
        self.pending = gnow()
        return None


class Search(Goal):
    """Look for secret doors: stand at each dead end (and corridor ends) and
    search a few times -- the user's doc lore: dead ends, lone doors,
    corridor ends. Done when a new door/opening shows up (explore again).
    strict=True: true corridor dead ends only (explore's own pass)."""

    def __init__(self, tries=8, strict=False, spots=None):
        self.name = "search dead ends"
        self.tries = tries
        self.strict = strict
        self.fixed = spots            # given squares (an inner room's 4 door spots) instead of dead ends
        self.spot = None
        self.searching = 0
        self.known = None
        self.done_n = 0
        self.spots_log = []           # (spot, searches; 0 = couldn't reach it)

    @staticmethod
    def door_count(w):
        return sum(1 for ch in w.memory.values() if ch in "+'")

    @staticmethod
    def dead_ends(w, strict=False, skip=()):
        mem = w.memory

        def is_open(y, x):
            return mem.get((y, x), " ") not in "#%*: 12345678"

        out = []
        for (y, x), ch in mem.items():
            if ch in "#%*: +12345678" or (w.level_t, (y, x)) in skip:
                continue
            nbs = [(dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                   if (dy or dx) and is_open(y + dy, x + dx)]
            if not strict:
                # Few open squares around: a dead end, the end of a (two-wide)
                # corridor, or a room corner -- where secret doors tend to be
                if len(nbs) <= 3:
                    out.append((y, x))
                continue
            # A corridor's end: one way out (one wide, or two side by side), or the end of a two-wide
            # one -- an L of three with the diagonal, and no room around (a room
            # corner has the same L but 9 open squares within 2)
            if len(nbs) <= 1:
                out.append((y, x))
            elif len(nbs) == 2:
                # a nub past a corridor's turn: both ways out on one side, side by
                # side (a plain bend's two touch only diagonally)
                (ay, ax), (by, bx) = nbs
                if abs(ay - by) + abs(ax - bx) == 1:
                    out.append((y, x))
            elif len(nbs) == 3:
                diag = [d for d in nbs if d[0] and d[1]]
                if len(diag) == 1 and {(diag[0][0], 0), (0, diag[0][1])} <= set(nbs) and \
                        sum(is_open(y + dy, x + dx) for dy in range(-2, 3) for dx in range(-2, 3)) <= 6:
                    out.append((y, x))
        return out

    def tick(self, p):
        w = p.w
        if self.known is None:
            self.known = len(p.frontier())
            self.doors = self.door_count(w)
        # (a door counts too: one into ground already known adds no frontier)
        if len(p.frontier()) > self.known or self.door_count(w) > self.doors:
            return ("done", "found a way on" + self.summary())
        if self.searching:
            if gnow() < p.busy_until:
                return None
            self.searching -= 1
            # (one a player turn, ~0.65 s: sent faster they queue on the server, and the move after the
            # last one waited behind them -- set-piece D3)
            p.cmd("custom s", "search for secret doors", hold=0.65)
            if not self.searching:
                p.searched.add((w.level_t, self.spot))
                self.done_n += 1
                self.spots_log.append((self.spot, self.tries))
                self.spot = None
            return None
        if p.mover.active:
            st = p.mover.tick()
            if st == "moving":
                return None
            if st == "arrived" and w.pos == self.spot:
                self.searching = self.tries
                return None
        if self.spot:
            # couldn't get there: don't try it again on this level
            p.searched.add((w.level_t, self.spot))
            self.spots_log.append((self.spot, 0))
        # the nearest dead end not searched yet (it zig-zagged by distance from
        # where the search began)
        if self.fixed is not None:
            spots = sorted((q for q in self.fixed if (w.level_t, q) not in p.searched), key=w.dist)
        else:
            spots = sorted(self.dead_ends(w, self.strict, p.searched), key=w.dist)
        if not spots:
            return ("failed", ("searched every spot, nothing found" if self.fixed is not None else
                               "searched every dead end, nothing found") + self.summary())
        self.spot = spots[0]
        if w.pos == self.spot:
            self.searching = self.tries
        elif not p.mover.go([self.spot]):
            p.searched.add((w.level_t, self.spot))
            self.spots_log.append((self.spot, 0))
            self.spot = None
        return None

    def summary(self):
        """Where it searched, how often (the Navigator couldn't tell whether a
        26 s searchroom had really searched 4 x 20, mission 20), including the
        spot it was at when the way on appeared (mission 21 listed only one)."""
        log = list(self.spots_log)
        if self.spot and (self.spot, 0) not in log:
            log.append((self.spot, self.tries - self.searching if self.searching else 0))
        done = [f"{q[0]},{q[1]} x{n}" for q, n in log if n]
        here = [f"{q[0]},{q[1]} (on the way)" for q, n in log if not n and q == self.spot]
        log = [(q, n) for q, n in log if not (not n and q == self.spot)]
        unreached = [f"{q[0]},{q[1]}" for q, n in log if not n]
        if not done and not unreached and not here:
            return ""
        return f" (searched: {', '.join(done + here) or 'none'}" + \
            (f"; couldn't reach: {', '.join(unreached)}" if unreached else "") + ")"


class Hunt(Goal):
    """Go and fight a monster by name: walk next to it, then stand still (the
    server's auto-retaliate does the hitting). Done when it's slain; failed
    when it's been out of sight for lost_s."""

    def __init__(self, name, lost_s=15):
        self.target = name.lower()
        self.name = f"hunt {name}"
        self.lost_s = lost_s
        self.last_seen = gnow()
        self.goal_tile = None
        self.t0 = gnow()

    def tick(self, p):
        w = p.w
        # every message since the hunt began: while others are adjacent this
        # goal isn't ticked, and a 3-s window missed the kill (mission 21:
        # "lost sight of it" for a slain Brigand)
        if any(ts >= self.t0 and (t.startswith("You have slain") or t.startswith("You have destroyed"))
               and self.target in t.lower() for ts, t in w.messages):
            return ("done", "slain")
        mons = [(y, x, r) for y, x, r in w.monsters if self.target in r.name.lower()]
        # Killed while we couldn't see it (blind, or it was invisible): the game
        # says "You have killed it." (the message catalogue)
        if not mons and gnow() - self.last_seen < 3 and \
                any(t.startswith("You have killed it") for t in w.recent(3)):
            return ("done", "killed (unseen at the end)")
        if not mons:
            if gnow() - self.last_seen > self.lost_s:
                return ("failed", "lost sight of it")
            return None
        self.last_seen = gnow()
        y, x, r = min(mons, key=lambda m: w.dist(m[:2]))
        # a blinker with bolts (the Advisor's hunt-strictness memo §4.3): after "X blinks away",
        # close in at once; if that takes more than ~2 turns, give up and let the escape rules
        # take over (m19: the Ranger blinked, then four bolts in 3 s while we stood)
        blink = next((ts for ts, t in w.messages if ts >= self.t0 and "blinks" in t and self.target in t.lower()), None)
        if blink and blink > getattr(self, "blink_seen", 0):
            self.blink_seen = blink
        if getattr(self, "blink_seen", 0) and w.dist((y, x)) > 1 and gnow() - self.blink_seen > 2.5:
            return ("failed", f"{r.name} blinked away and couldn't be reached in 2 turns: hunt given up "
                              "(a blinker with bolts wins at range)")
        if w.dist((y, x)) <= 1:
            self.blink_seen = 0
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


class Reprieve(Goal):
    """A blinker got away (a hunt given up): take the reprieve. The user (2026-10-23): rest
    is free; resources only in a turn-sensitive situation. Mortal danger near -> leave by the
    stairs while we can. Something still in view -> step out of its sight over walked ground
    (spending nothing). Nothing in view -> rest to full. Done when healed, or after 2 minutes."""

    def __init__(self, who):
        self.who = who
        self.name = f"reprieve (rest while {who} is away)"
        self.t0 = gnow()

    def tick(self, p):
        w = p.w
        if not w.in_dungeon:
            return ("done", "not in the dungeon")
        total, _ = p.group_danger()
        if p.dangers() or total >= 0.6 * max(1, w.hp[0]):
            p.stop_resting()
            p.set_goal(Flee(f"mortal danger near after {self.who} blinked away: leaving while we can"))
            return None
        if w.hp_frac >= p.orders["rest_to"]:
            p.stop_resting()
            return ("done", f"healed ({w.hp[0]}/{w.hp[1]}) while {self.who} stayed away")
        if gnow() - self.t0 > 120:
            p.stop_resting()
            return ("done", "2 minutes: carrying on")
        if w.monsters:
            p.stop_resting()
            # out of its sight, over ground already walked (no new monsters woken)
            if not p.retreat_step([m for m in w.monsters], reach=20):
                return None      # (nowhere better: hold; the fight reflexes still apply)
            return None
        p.start_resting()
        return None


class BandLeave(Goal):
    """The trip leaves a level for a band, no stairs known, HP high, nothing on us: find stairs instead of
    reading Word of Recall at once (m26 ended every trip in an escape recall, ~970 gold of scrolls in 25
    minutes; the user, 2026-10-24). Door/Stair Location, else Magic Mapping, then flee to what it shows;
    with neither, walk out of the band's sight. A second failure on the level recalls (flee_failed)."""

    def __init__(self, names):
        self.names = set(names)
        self.name = "flee (band: locating stairs)"
        self.t0 = None
        self.flee = None

    def tick(self, p):
        w = p.w
        if self.flee:
            return self.flee.tick(p)
        if self.t0 is None:
            used = p.use_stair_location("band, no stairs known")
            if not used:
                mm = next((i for i in w.items(tval=TV_SCROLL) if "Magic Mapping" in i["name"]), None)
                if mm and not w.flag("blind") and not w.flag("confused") and gnow() >= p.busy_until:
                    p.cmd(f"custom r item={mm['item']}", "band, no stairs known: Magic Mapping", hold=0.8)
                    used = True
            if not used:
                p.set_goal(WalkAway(self.names))
                p.notify("tactic", "a band and no stairs known: walking out of its sight instead of reading Word of "
                                   "Recall", news=True)
                return None
            self.t0 = gnow()
            return None
        if not waited(self.t0, 1.5):
            return None
        if not w.find("<>"):
            return ("failed", "located nothing: no stairs known")
        p.notify("tactic", "a band and no stairs known: found stairs, leaving by them instead of Word of Recall",
                 news=True)
        self.flee = Flee("band: the trip leaves the level")
        self.flee.name = "flee (band: to the stairs located)"
        return self.flee.tick(p)


class WalkAway(Goal):
    """A summoner just came into view, not adjacent and no faster than us: walk out of its sight
    over ground already walked, then keep away (an avoid zone where it was). The user (2026-10-23,
    the set-piece A8o, where the danger rule read Word of Recall at full HP): if we first saw it
    by walking into line of sight, just walk away; other action only if something prevents walking
    away safely. Fails (the flee and its escapes take over) when it comes adjacent, its summons
    arrive, HP falls below half, or there's nowhere to walk."""

    def __init__(self, names):
        self.names = set(names)
        self.name = f"walk away from {', '.join(sorted(self.names))}"
        self.t0 = gnow()
        self.last = {}
        self.stuck_t = None

    def tick(self, p):
        w, now = p.w, gnow()
        seen = [(y, x, r) for y, x, r in w.monsters if r.name in self.names]
        for y, x, r in seen:
            self.last[r.name] = (y, x)
        if w.hp_frac < 0.5:
            return ("failed", "HP below half")
        if any(w.dist((y, x)) <= 1 for y, x, _ in seen):
            return ("failed", "it reached us")
        if any(ts >= self.t0 and "summons" in t for ts, t in w.messages):
            return ("failed", "it summoned")
        if not seen and all(w.dist(q) >= 6 for q in self.last.values()):
            for name, (y, x) in self.last.items():
                p.avoid_zones.setdefault(w.level_t, []).append((y, x, 7))
            return ("done", "out of its sight; avoid zone set where it was")
        if now - self.t0 > 30:
            return ("failed", "30 s and still in its sight")
        if p.retreat_step([m for m in seen] or [(q[0], q[1], None) for q in self.last.values()], reach=20):
            self.stuck_t = None
            return None
        self.stuck_t = self.stuck_t or now
        if now - self.stuck_t > 3:
            return ("failed", "nowhere to walk away to")
        return None


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
                # (where it came out: a dive mustn't take this staircase straight back -- the level may be one
                # the server keeps, with the danger beside the arrival: m25 looped into Ibun at 450 ft)
                # (and whether the level fled is one the server keeps: we logged in on it)
                p.fled_from = (getattr(self, "from_depth", None), gnow(), w.level_t,
                               self.took[0] == p.__dict__.get("first_level_t"))
                return ("done", f"left by the stairs; now at {w.depth_ft} ft")
            if waited(self.took[1], 5):
                return ("done", "took the stairs, but no level change seen")
            if waited(self.took[1], 1.5) and len(self.took) == 2 and w.standing_on in ("<", ">"):
                p.take_stairs(w.standing_on)      # a stairs command right after arriving can be ignored
                self.took = self.took + (True,)
            return None
        # At or below max_depth, go up if an up staircase is known (mission 4:
        # flights kept taking '>' past max_depth)
        md = int(p.orders.get("max_depth", 0))
        # With only '>' known there, teleport away on this level instead (m38: two flees at 650 ft took '>' to 700
        # ft, and finding a '<' there took 10 minutes); '>' only without a teleport, or one used in the last minute
        if md and w.depth_ft >= md and not w.find("<") and not self.started:
            t = p.teleport_item()
            if t and not w.flag("blind") and (t[0] == "u" or not w.flag("confused")) and \
                    gnow() - getattr(p, "flee_tele_t", -99.0) > 60:
                p.flee_tele_t = gnow()
                p.cmd(f"custom {t[0]} item={t[1]['item']}", f"flee at {w.depth_ft} ft (max_depth), only '>' known: "
                                                            f"{t[1]['name']}", hold=0.8)
                p.notify("tactic", f"flee at max_depth with only '>' known: teleported ({one_of(t[1]['name'])}) "
                                   "rather than going deeper", news=True)
                return ("done", "teleported away on this level (max_depth, no '<' known)")
        ok = "<" if md and w.depth_ft >= md and w.find("<") else "<>"
        if w.standing_on and w.standing_on in ok:     # (None in "<>" crashed a flee, mission 6)
            p.take_stairs(w.standing_on)
            self.took = (w.level_t, gnow())
            self.from_depth = w.depth
            return None
        stairs = w.find(ok)
        if not stairs:
            return ("failed", "no stairs known")
        # Stairs known but no known way to them (Door/Stair Location shows stairs, not corridors): Magic Mapping
        # first, once per level. m31: an Ogre band, stairs 16 away, the flee went through unexplored squares, got
        # stuck, and a Word of Recall ended the trip -- with 4 Magic Mapping scrolls in the pack
        if not self.started and getattr(self, "mapped", None) != w.level_t and not plan(w, stairs) and \
                not w.flag("blind") and not w.flag("confused") and not w.adjacent_monsters():
            mm = next((i for i in w.items(tval=TV_SCROLL) if "Magic Mapping" in i["name"]), None)
            if mm:
                self.mapped = w.level_t
                p.cmd(f"custom r item={mm['item']}", "flee: no known way to the stairs: read Magic Mapping", hold=0.8)
                p.notify("tactic", "flee: stairs known but no known way to them: read Magic Mapping", news=True)
                return None
        if not self.started or not p.mover.active:
            if not p.mover.go(stairs, unknown=True):
                return ("failed", "no path to stairs, nor one through unexplored squares")
            # Far stairs with the danger already on us: walking hands it free hits all the way (m26: Nar
            # adjacent, stairs 75-81 steps off through unexplored squares; 22 s and ~150 HP before the
            # recall). Fail now: the flee-failed escape reads Word of Recall and phases while it charges.
            # (the length of the path, or -- not planned yet -- the distance to the nearest stairs: "through
            # unexplored" alone read Word of Recall with stairs 0 steps away, m26)
            close = [r.name for y, x, r in w.monsters if w.dist((y, x)) <= 2 and p.danger_why(r)]
            steps = len(p.mover.path) or min(w.dist(q) for q in stairs)
            if close and steps > 15:
                p.mover.stop()
                return ("failed", f"stairs {steps} steps away{' through unexplored squares' if p.mover.unknown else ''}"
                                  f" with {close[0]} beside us")
            if p.mover.unknown:
                p.notify("tactic", "flee: no known path to the stairs; trying one through unexplored squares",
                         news=True)
            self.started = True
        st = p.mover.tick()
        if st == "stuck":
            # (m59: "stuck" 4 s after a phase moved us, then Word of Recall: plan again from here, twice, first)
            self.regone = getattr(self, "regone", 0) + 1
            if self.regone <= 2 and p.mover.go(stairs, unknown=True):
                return None
            return ("failed", "stuck on the way to the stairs")
        return None


class Recall(Goal):
    name = "recall"

    def __init__(self, depth_ft=None):
        self.depth_ft = depth_ft     # (from town: the recall depth to inscribe; else max_depth)
        if depth_ft:
            self.name = f"recall to {depth_ft} ft"
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
            md = int(self.depth_ft or p.orders.get("max_depth", 0)) // 50 * 50
            if w.depth == 0 and md and recall_level(it["name"]) != md // 50:
                if not waited(self.inscribe_t, 2.5):
                    return None           # (wait for the pack to show the new inscription)
                if self.inscribed >= 3:
                    return ("failed", f"couldn't inscribe @R{md} on the Word of Recall "
                                      f"(it reads '{it['name']}'): not reading it")
                self.inscribed += 1
                self.inscribe_t = gnow()
                p.cmd(f"custom {{ item={it['item']} entry=@R{md}", f"recall depth {md} ft", hold=1.0)
                w.inven_dirty = True
                return None
            # No light, no reading (mission 13: at night in town the light was off
            # for idling, and the read failed with "You have no light to read by")
            if not any(i["tval"] == TV_LITE for i in w.items(equip=True)):
                # (the fullest: '"0 turns" not in' skipped m39's 13290-turn lantern -- it ends in "0 turns" -- and
                # lit the 4383-turn one, which ran low mid-trip)
                lite = p.best_light()
                if lite and waited(self.light_t, 2):
                    self.light_t = gnow()
                    p.light_t = gnow() + 30      # (town_light: don't take it off again)
                    p.cmd(f"custom w item={lite['item']}", "light on to read Word of Recall", hold=0.8)
                    return None
            if p.recall_started(gnow()):
                # Already under way (e.g. the last-resort recall): a second read would cancel it
                p.log("note", text="recall already under way: not reading another")
                self.read_t = gnow()
                return None
            # Blind or confused, the scroll can't be read (m55: a `goal recall` sat 4 minutes confused by
            # Hummerhorns until the Navigator quaffed a CSW): the cheapest cure first (use-obj.c: Cure Light Wounds
            # ends blindness, Serious and Critical end both), then read
            if w.flag("blind") or w.flag("confused"):
                if waited(getattr(self, "cure_t", 0), 3):
                    kinds = (["Cure Light"] if not w.flag("confused") else []) + ["Cure Serious", "Cure Critical"]
                    pot = next((i for k in kinds for i in w.items(tval=TV_POTION) if k in i["name"]), None)
                    self.cure_t = gnow()
                    if pot:
                        p.cmd(f"custom q item={pot['item']}", f"recall: {'confused' if w.flag('confused') else 'blind'}"
                                                              f", can't read: quaff {pot['name']}", hold=0.8)
                    elif not getattr(self, "told", False):
                        self.told = True
                        p.notify("tactic", "recall: blind or confused and no cure for it: waiting to be able to read",
                                 news=True)
                return None
            # (m56: "read 2 Scrolls of Word of Recall" read as two reads; one scroll of the stack is read)
            p.cmd(f"custom r item={it['item']}", f"read a Word of Recall ({it['number']} in the pack)")
            self.read_t = p.recall_t = gnow()
            return None
        # while it charges, rest when hurt and nothing is in view: free healing, and time runs 10x
        # while resting, so the recall comes ~10x sooner in real time (the rulebook's constants:
        # recall_seconds; the server ends a rest at full HP)
        if w.recall_pending and not w.monsters and w.hp[0] < w.hp[1] and not w.resting and \
                gnow() - self.read_t > 1 and gnow() - getattr(self, "rest_t", 0) > 3:
            self.rest_t = gnow()
            p.start_resting()
        if gnow() - self.read_t > (120 if w.recall_pending else 60):
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
            if waited(w.level_t, 1.2) and waited(self.up_t, 1.5):
                self.up_t = gnow()
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
        wt = re.search(r"with (\d+) turns", worn["name"]) if worn else None
        if (not worn or (wt and int(wt.group(1)) < 100)) and waited(self.light_t, 5):
            def left(i):
                t = re.search(r"with (\d+) turns", i["name"])
                return int(t.group(1)) if t else (1 if "Lantern" in i["name"] else 0)
            lite = max((i for i in w.items(tval=TV_LITE) if left(i) > 0), key=left, default=None)
            if lite:
                self.light_t = gnow()
                p.light_t = gnow() + 30
                p.cmd(f"custom w item={lite['item']}", "townfarm: light on", hold=0.8)
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
                key = re.sub(r"^(an?|\d+) ", "", re.sub(r"\s*\{[^}]*\}", "", sp["sold_as"])).lower()
                relist = next((i["price"] for i in (w.store or {}).get("items", [])
                               if re.sub(r"^(an?|\d+) ", "", re.sub(r"\s*\{[^}]*\}", "", i["name"])).lower() == key),
                              None) if w.store_t > sp["t"] else None
                p.log("sale", **{k: v for k, v in sp.items() if k != "t"}, relist=relist)
                if sp.get("forced") and getattr(self, "role", "navigator") != "architect":
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
                    why_not = p.value_refusal(it, "sell", getattr(self, "role", None))
                    if why_not:
                        why_not += "; `sell !NAME` overrides, and adds the value lost to your debt"
                if force and getattr(self, "role", "navigator") != "architect" and not p.override_allowed():
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
    2026-10-26: "leave the potions in the tavern during a mission"; the wands were never aimed). Walk onto the
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
        used = {tuple(q) for q in p.stash_state().get("squares", [])}
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
        p.stash_state().setdefault("squares", []).append(list(target))
        p.cmd(f"custom d item={it['item']} value={it['number']}", f"stash in the tavern: {it['name']}", hold=0.8)
        p.stash_add(it["name"])
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
            p.stash_remove(self.kind)
            sq = p.stash_state().get("squares", [])
            if list(w.pos) in sq:
                sq.remove(list(w.pos))           # (the square is free for the next stash drop)
                p.stash_save()
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
                p.stash_remove(self.kind)
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
    and bank gold"). An owned town house keeps what's dropped in it (saved with the server; monsters can't enter or
    take floor gold; cmd2.c, melee2.c). One pile on the square inside the door (gold piles never merge, and a drop
    with no free square vanishes -- object2.c): stepping in picks the whole bank up, then a deposit drops all but
    `keep` back on that square with the door closed. mode: 'buy' (open the door: "This house costs N gold."; buy
    with 'h' if we can spare it, then deposit), 'deposit' or 'withdraw'."""

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
                p.stash_add(it["name"])
                p.house_save()
                return True
            if it and not getattr(self, "full_told", False):
                self.full_told = True
                p.notify("tactic", f"house: no free square for {it['name']} (one stack a square): kept in the pack",
                         news=True)
        if self.mode == "withdraw":
            kind = p.stash_wanted()
            key = next((k for k, n in slots.items() if kind and kind in n), None)
            if key:
                q = tuple(int(v) for v in key.split(","))
                if any(kind in i["name"] for i in w.items()):
                    del slots[key]
                    p.stash_remove(kind)
                    p.fetching = None
                    p.house_save()
                    return True
                if w.pos != q:
                    return walk_to(q)
                self.picks = getattr(self, "picks", 0) + 1
                if self.picks > 4:
                    del slots[key]                 # (not there after all)
                    p.stash_remove(kind)
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
    essential item out of stock gets one more look after 40 s (stock turns over
    every ~33 s)."""

    RESTOCK_WAITS = 4          # critical items out of stock: up to 4 waits of 35 s for the shops to restock

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
            if p.house_state().get("house") and (p.banked() or p.stash_wanted()):
                self.sub = HouseBank("withdraw")   # (and the stash kind a drained stat wants)
                return None
        # a drained stat whose Restore waits in the tavern: fetch it first (bought only if it isn't there)
        if self.stage == "upgrade" and not getattr(self, "fetched", False):
            kind = p.stash_wanted() if not p.house_state().get("items") else None   # (the house's: fetched above)
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
            # leave town fed and fuelled: no food is digested in town (dungeon.c), so eat rations to Full here,
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
                sc = next((i for i in w.items(tval=TV_SCROLL) if "Recharging" in i["name"]), None)
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
                sc = next((i for i in w.items(tval=TV_SCROLL) if "Enchant Armor" in i["name"]), None)
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


class TripPlan:
    """plan trip LO-HI [until COND] [then recall|town] [level_min=N] (restructure step 2.3):
    the Navigator's intent, run by the Pilot. Down (Word of Recall to the planned depth, or the
    stairs near town), then level by level within LO-HI: explore each (fights, loot and the
    item policy as usual) until it's done or `level_min` minutes pass, then the next level
    (down while above HI, up one at HI). Bad levels are left at once: a band (stairs), a pit or
    nest, breeders, a drainer of STR/DEX/CON, a fearer, trap-laden. When a condition holds it
    comes home (Word of Recall, else the stairs), and with `then town` runs the town kit.
    It sits above the goals: the Pilot's reflexes (flee, recover) replace a goal without ending
    the plan, and a goal the Navigator gives pauses it until that goal ends."""
    VARS = ("cures", "ccw", "csw", "clw", "phase", "wor", "food", "hp", "minutes", "dmin", "time", "clvl", "gold",
            "free", "levels")
    EVENTS = ("band", "drained", "emergency", "emergency_loop", "danger", "pack_full", "unique_slain",
              "unseen_attacker")
    LEAVE_ON = {"band": "a band", "breeders": "breeders", "drainer": "a stat drainer", "fearer": "a fearer",
                "structure": "a pit or nest"}

    def __init__(self, lo, hi, until, then="recall", level_min=10, via=None):
        self.lo, self.hi, self.then, self.level_min, self.via = lo, hi, then, level_min, via
        self.conds = until
        self.until_text = " or ".join(c[0] for c in until)
        self.text = f"trip {lo}-{hi} until \"{' or '.join(c[0] for c in until)}\" then {then}"
        self.t0 = gnow()
        self.phase = "down"
        self.level = None           # level_t of the level being worked
        self.level_t0 = 0.0
        self.level_done = None      # why this level is finished (then: the next level)
        self.levels = 0
        self.events = collections.Counter()
        self.paused, self.pause_goal = False, None
        self.arrival, self.located, self.stairs_first, self.special = None, False, False, False
        self.resume_lvl = None      # (load: the level a restart interrupted)
        self.leave_since = None     # (level_t, when this level was done): the LEAVE_MAX watchdog
        self.step = "starting"
        self.fails = 0
        self.home_why = None
        self.went_down = False
        self.town = None

    @staticmethod
    def parse_until(text):
        """'cures<4 or phase<5 or time>22:40 or band' -> [(term, var, op, value)], or raises ValueError."""
        out = []
        for term in [t.strip() for t in re.split(r"\s+or\s+|,", text) if t.strip()]:
            m = re.fullmatch(r"(\w+)\s*(<=|>=|<|>|=)\s*(\d+(?::\d\d)?)", term)
            if m:
                var, op, val = m.groups()
                if var not in TripPlan.VARS:
                    raise ValueError(f"unknown quantity {var!r} (known: {', '.join(TripPlan.VARS)})")
                if (var == "time") != (":" in val):
                    raise ValueError(f"{term!r}: time takes HH:MM, the others numbers")
                out.append((term, var, op, val))
            elif term in TripPlan.EVENTS:
                out.append((term, term, None, None))
            else:
                raise ValueError(f"can't read {term!r} (VAR<N, VAR>N, time>HH:MM, or an event: "
                                 f"{', '.join(TripPlan.EVENTS)})")
        return out

    def value(self, p, var):
        w = p.w
        if w.in_dungeon and not self.__dict__.get("dungeon_t0"):
            self.dungeon_t0 = gnow()
            p.notify("plan", f"trip: down at {w.depth_ft} ft with {p.supply_text()}", news=True)

        def n(word, tv=TV_POTION):
            return sum(i["number"] for i in w.items(tval=tv) if word in i["name"])
        if var == "cures":
            return n("Cure Light Wounds") + n("Cure Serious Wounds") + n("Cure Critical Wounds")
        return {"ccw": lambda: n("Cure Critical Wounds"), "csw": lambda: n("Cure Serious Wounds"),
                "clw": lambda: n("Cure Light Wounds"), "phase": lambda: n("Phase Door", TV_SCROLL),
                "wor": lambda: n("Word of Recall", TV_SCROLL), "food": lambda: p.kit_count("Ration of Food"),
                "hp": lambda: round(100 * w.hp_frac), "minutes": lambda: (gnow() - self.t0) / 60,
                # (m57: `minutes>30` counted the town visit and the recall down; dmin = minutes since the trip first
                # reached the dungeon)
                "dmin": lambda: (gnow() - self.__dict__["dungeon_t0"]) / 60 if self.__dict__.get("dungeon_t0") else 0,
                "clvl": lambda: w.clvl, "gold": lambda: w.ind.get("gold", [0])[0],
                "free": lambda: 23 - len(w.items()), "levels": lambda: self.levels,
                "time": lambda: time.strftime("%H:%M:%S")}[var]()

    def clock_target(self, hhmm):
        """The epoch of the first HH:MM at or after the plan's start (wall clock; across midnight too)."""
        cache = self.__dict__.setdefault("clock_targets", {})
        if hhmm not in cache:
            start = time.time() - (gnow() - self.t0)
            lt = time.localtime(start)
            h, m = map(int, hhmm.split(":")[:2])
            t = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))
            if t < start - 60:
                t += 86400
            cache[hhmm] = t
        return cache[hhmm]

    def holds(self, p):
        """The first condition that holds, or None. Two always apply: no Word of Recall
        left, and 90 minutes (the plan runs unattended)."""
        for term, var, op, val in self.conds + [("no Word of Recall left", "wor", "<", "1"),
                                                ("90 minutes", "minutes", ">", "90")]:
            if op is None:
                # (a band holds only while it's live: m30's Novice warrior band was beaten, and the trip went home
                # 3 minutes later on a new level when the plan resumed. A band gone or beaten clears the count)
                if var == "band" and self.events[var] and not p.band_live():
                    self.events[var] = 0
                if self.events[var]:
                    return term
                continue
            if var == "wor" and not self.went_down:
                continue             # (the trip's own Word of Recall isn't read yet)
            v = self.value(p, var)
            # (time to the second: "time>02:41" holds from 02:41:01 -- as minutes it waited until 02:42, m25)
            x = val + ":00" if var == "time" else int(val)
            if var == "time":
                # as a moment, not a string: the next HH:MM after the plan started (m44's "time>00:26" set at 23:54
                # held at once -- "23:54:41" > "00:26:00" -- and the trip came home on arrival)
                v, x = time.time(), self.clock_target(val)
            if (op == "<" and v < x) or (op == ">" and v > x) or (op == "<=" and v <= x) or \
                    (op == ">=" and v >= x) or (op == "=" and v == x):
                return term
        return None

    def describe(self):
        return f"{self.text} ({(gnow() - self.t0) / 60:.0f} min, {plural(self.levels, 'level')}: " \
               f"{'paused for your goal' if self.paused else self.step})"

    def on_event(self, p, what, detail, news):
        """Every notify passes here: count the events the conditions name, and leave a bad level."""
        w = p.w
        self.events[{"danger_seen": "danger", "stat_drained": "drained"}.get(what, what)] += 1
        if self.paused or not w.in_dungeon or self.phase != "level":
            return
        # (pinned by a breeder swarm while leaving: m45 at 750 ft, Giant fleas, 13 minutes; m48 at 750 ft, Giant white
        # lice, 5 minutes to LEAVE_MAX's recall. The first stuck notice on such a level: one teleport away from the
        # swarm, then the dive goes on to the stairs)
        if what == "stuck" and self.level == w.level_t and "breeders" in str(self.level_done or "") and \
                self.__dict__.get("swarm_tele") != w.level_t:
            tp = p.teleport_item()
            if tp and (tp[0] == "u" or not (w.flag("blind") or w.flag("confused"))):
                self.swarm_tele = w.level_t
                p.cmd(f"custom {tp[0]} item={tp[1]['item']}", "trip: pinned by breeders while leaving: teleport away",
                      hold=0.8)
                p.notify("plan", f"trip: pinned by breeders while leaving {w.depth_ft} ft: teleported "
                                 f"({one_of(tp[1]['name'])}), on to the stairs", news=True)
                return
        if what == "band" and "band" in [c[1] for c in self.conds]:
            return                  # (the condition brings it home instead)
        why = self.LEAVE_ON.get(what) if not news else None
        if what == "drainer" and news:
            why = None
        if what == "tactic" and "trap-laden" in (detail or ""):
            why = "trap-laden"
        if why and self.level == w.level_t and not self.level_done:
            self.level_done = f"left: {why}"
            g = p.goal
            if g is None or getattr(g, "by_plan", False):
                if what == "band":
                    p.set_goal(self.mark(Flee("band: the trip leaves the level")))
                else:
                    p.set_goal(self.mark(self.next_dive(p)))
                p.notify("plan", f"trip: leaving {w.depth_ft} ft ({why})", news=True)

    STATE = ("lo", "hi", "then", "level_min", "t0", "phase", "levels", "went_down", "home_why", "until_text", "via",
             "xp0", "dungeon_t0")

    def save(self, p):
        st = {k: getattr(self, k, None) for k in self.STATE}
        # this level's state: a restart or hot-swap lands on the same level under a new level_t, and m45's hot-swap
        # lost the special level's "find stairs first" (it explored the 700 ft pit level instead)
        w = p.w
        if w.in_dungeon and self.phase == "level" and self.level == w.level_t:
            st["lvl"] = {"depth": w.depth, "age": round(gnow() - self.level_t0, 1), "done": self.level_done,
                         "arrival": self.arrival, "located": self.located, "special": self.special,
                         "stairs_first": self.stairs_first, "fails": self.fails}
        try:
            json.dump(st, open(os.path.join(p.rundir, "plan.json"), "w"))
        except OSError:
            pass

    @classmethod
    def load(cls, p):
        """The plan a restart interrupted (restart.sh parks the Pilot mid-trip), or None."""
        try:
            st = json.load(open(os.path.join(p.rundir, "plan.json")))
        except (OSError, ValueError):
            return None
        if not st or gnow() - st["t0"] > 90 * 60:
            return None
        pl = cls(st["lo"], st["hi"], cls.parse_until(st["until_text"]), st["then"], st["level_min"], st.get("via"))
        for k in ("t0", "phase", "levels", "went_down", "home_why", "dungeon_t0"):
            setattr(pl, k, st[k])
        pl.xp0 = st.get("xp0")
        pl.resume_lvl = st.get("lvl")
        return pl

    def stairs_down(self, p):
        """Down by the stairs (not Word of Recall): when asked (via=stairs), or when the trip is
        near town (to 150 ft) or the character has never been to 250 ft."""
        if self.via:
            return self.via == "stairs"
        want = min(self.hi, max(self.lo, p.deepest_ft or 0))
        return want <= 150 or (p.deepest_ft or 0) < 250

    def mark(self, g):
        g.by_plan = True
        g.role = "pilot"
        return g

    def next_dive(self, p):
        d = p.w.depth_ft
        if d < self.hi:
            g = Dive(d + 50)
        else:
            g = Dive(d - 50)       # (at the bottom of the range: up one for a fresh level)
        g.stop = False
        return g

    def tick(self, p):
        """Called when no goal is running (and every 2 s under a plan goal, for the
        conditions). Returns (status, detail) when the plan ends."""
        w, now = p.w, gnow()
        # (the trip's XP base, for the report's "this trip" rate: m47's Navigator wanted XP a minute per trip)
        if getattr(self, "xp0", None) is None and (w.ind.get("exp") or [None])[0] is not None:
            self.xp0 = w.ind["exp"][0]
        if self.paused:
            self.leave_since = None     # (the Navigator's own goal: LEAVE_MAX counts again from a resume)
            return None
        if w.in_dungeon and w.recall_pending and self.phase in ("down", "level", "home") and self.went_down:
            # a recall is under way (the Pilot's escape, or the plan's own): wait for it, don't
            # start a new dive meanwhile (m24: a dive walked the pit's ring while it charged)
            if self.phase != "home":
                # (with the escape's trigger: m42's Navigator couldn't tell why its trip ended at 19:19)
                le = getattr(p, "last_escape", None)
                why = f": {le[2]} (HP {le[3][0]}/{le[3][1]})" if le and gnow() - le[0] < 60 else ""
                self.phase, self.home_why = "home", f"the Pilot's escape recall{why}"
                p.notify("plan", f"trip: a recall is under way (the Pilot's escape{why}): coming home -- "
                                 "`why` for the details", news=True)
            if p.goal is not None and getattr(p.goal, "by_plan", False) and isinstance(p.goal, (Dive, Explore)):
                p.set_goal(None)
            if p.goal is None:
                self.step = "waiting for the recall"
                p.set_goal(self.mark(Wait(3)))
            return None
        if self.phase in ("down", "level") and w.in_dungeon:
            why = self.holds(p)
            if why:
                self.phase, self.home_why = "home", why
                p.notify("plan", f"trip: coming home ({why})", news=True)
                if p.goal is not None and getattr(p.goal, "by_plan", False) and \
                        not isinstance(p.goal, (Flee, Recover, Recall)):
                    p.set_goal(None)
        if self.phase == "home" and isinstance(p.goal, Dive) and getattr(p.goal, "by_plan", False) and \
                now - (getattr(self, "climb_t0", None) or now) > 180 and self.value(p, "wor") >= 1 and \
                not w.recall_pending:
            p.notify("plan", "trip: no way up found in 3 minutes: reading Word of Recall instead", news=True)
            p.set_goal(None)          # (the next tick reads it)
        if self.phase == "level" and isinstance(p.goal, Explore) and getattr(p.goal, "by_plan", False) and \
                self.level == w.level_t and not self.level_done and now - self.level_t0 > 60 * self.level_min:
            self.level_done = f"{self.level_min:g} minutes on it"
            p.set_goal(None)
        # a level that won't let us go: recall home after LEAVE_MAX (m45: 13 minutes leaving 750 ft -- the only '<'
        # led back to the level just fled, and a Giant flea swarm pinned the dive; the stuck watchdog doesn't count
        # time spent fighting, and the quiet rule only cuts an exploration short)
        if self.phase == "level" and w.in_dungeon and self.level == w.level_t and self.level_done:
            if not self.leave_since or self.leave_since[0] != w.level_t:
                self.leave_since = (w.level_t, now)
            elif now - self.leave_since[1] > self.LEAVE_MAX and self.value(p, "wor") >= 1 and not w.recall_pending:
                self.phase = "home"
                self.home_why = f"couldn't leave {w.depth_ft} ft in {self.LEAVE_MAX / 60:g} minutes ({self.level_done})"
                p.notify("plan", f"trip: coming home ({self.home_why})", news=True)
                if p.goal is not None and getattr(p.goal, "by_plan", False) and \
                        not isinstance(p.goal, (Flee, Recover, Recall)):
                    p.set_goal(None)
        quiet = self.quiet(p, now)
        if self.phase == "level" and isinstance(p.goal, Explore) and getattr(p.goal, "by_plan", False) and \
                self.level == w.level_t and not self.level_done and quiet:
            self.level_done = quiet
            p.set_goal(None)
        if p.goal is not None:
            return None
        if self.phase == "down":
            if w.depth == 0:
                if self.went_down:
                    return ("done", "back in town before the trip began (a recall by the Pilot's own rules?)")
                want = min(self.hi, max(self.lo, p.deepest_ft or 0))
                # one level above HI when the range allows: there both '<' and '>' lead somewhere useful (m40 landed
                # at 650 = max_depth on an orc pit with only '>' known and spent ~10 minutes finding a '<')
                if want == self.hi and self.hi - 50 >= self.lo:
                    want = self.hi - 50
                if self.stairs_down(p):
                    self.step = f"down by the stairs to {self.lo} ft"
                    g = Dive(self.lo)
                    g.stop = False
                    p.set_goal(self.mark(g))
                else:
                    self.step = f"recall down to {min(want, p.deepest_ft)} ft"
                    p.set_goal(self.mark(Recall(depth_ft=min(want, p.deepest_ft))))
                return None
            if not w.in_dungeon:
                self.step = "back to town from the wilderness"
                p.set_goal(self.mark(Town()))
                return None
            self.went_down = True
            self.phase = "level"
        if self.phase == "level":
            if w.depth == 0:
                le = getattr(p, "last_escape", None)
                why = f": the Pilot's escape at HP {le[3][0]}/{le[3][1]}, {le[2]}" if le and gnow() - le[0] < 120 else ""
                return ("done", f"back in town (not by the plan's recall{why}); {plural(self.levels, 'level')} done -- "
                                "`why` for the details")
            d = w.depth_ft
            if d < self.lo or d > self.hi:
                self.step = f"to {self.lo if d < self.lo else self.hi} ft"
                g = Dive(self.lo if d < self.lo else self.hi)
                g.stop = False
                p.set_goal(self.mark(g))
                return None
            rl, self.resume_lvl = self.resume_lvl, None
            if self.level != w.level_t and rl and rl["depth"] == w.depth:
                # the level a restart interrupted (the same level: the character stayed in the world)
                self.level, self.level_t0, self.level_done = w.level_t, now - rl["age"], rl["done"]
                self.arrival, self.located, self.special = rl["arrival"], rl["located"], rl["special"]
                self.stairs_first, self.fails = rl["stairs_first"], rl["fails"]
            if self.level != w.level_t:
                self.level, self.level_t0, self.level_done = w.level_t, now, None
                self.levels += 1
                self.fails = 0
                self.arrival = "recall" if any(abs(ts - w.level_t) < 5 and "yanked" in t for ts, t in w.messages) \
                    else w.arrived_by
                self.located = self.stairs_first = self.special = False
            # the arrival protocol (the Advisor's m24 memo: the orc-pit level said "something special"
            # on arrival, and the Pilot explored 92 s without zapping Door/Stair Location): after a
            # recall, or on a special feeling, map the stairs first and find a way out before exploring
            special = self.special = self.special or \
                any(ts >= w.level_t - 1 and "something special about this level" in t for ts, t in w.messages)
            if (self.arrival == "recall" or special) and not self.located:
                self.located = True
                if not w.find("<>") and p.use_stair_location("trip: " + ("recall arrival" if self.arrival == "recall"
                                                                         else "a special level")):
                    self.step = "mapping the stairs (arrival protocol)"
                    return None
            # (each time the plan picks a goal, not once: after a fight, a `plan resume` or a restart it went back to
            # plain exploring)
            if special and not w.find("<>") and self.level_done is None:
                if not self.stairs_first:
                    self.stairs_first = True
                    p.notify("plan", f"trip: {d} ft feels special (a pit, nest or vault): finding stairs before "
                                     "exploring", news=True)
                self.step = f"finding stairs first ({d} ft feels special: a pit, nest or vault)"
                p.set_goal(self.mark(Explore(until="stairs")))
                return None
            if self.level_done is None and now - self.level_t0 > 60 * self.level_min:
                self.level_done = f"{self.level_min:g} minutes on it"
            if self.level_done:
                self.step = f"next level ({self.level_done})"
                self.fails += 1
                if self.fails > 6:
                    self.phase, self.home_why = "home", f"can't leave {d} ft (no stairs found)"
                    return None
                p.set_goal(self.mark(self.next_dive(p)))
                return None
            self.step = f"exploring {d} ft"
            p.set_goal(self.mark(Explore()))
            return None
        if self.phase == "home":
            if self.fails > 10:
                return ("failed", f"couldn't get home ({self.home_why}): the recall or the climb kept failing")
            if w.depth == 0:
                if self.then == "town":
                    self.phase = "town"
                    self.step = "the town kit"
                    p.set_goal(self.mark(TownKit()))
                    return None
                return ("done", f"home ({self.home_why}); {plural(self.levels, 'level')} in "
                                f"{(now - self.t0) / 60:.0f} min")
            if not w.in_dungeon:
                p.set_goal(self.mark(Town()))
                return None
            self.climb_t0 = getattr(self, "climb_t0", None) or now
            if w.depth_ft <= 150 and not w.recall_pending and (now - self.climb_t0 < 180 or self.value(p, "wor") < 1):
                self.step = "climbing home (near town: the stairs save a Word of Recall)"
                g = Dive(0)
                g.stop = False
                p.set_goal(self.mark(g))
            elif self.value(p, "wor") >= 1 and not w.recall_pending:
                self.step = "recalling home"
                p.set_goal(self.mark(Recall()))
            elif w.recall_pending:
                self.step = "waiting for the recall"
                p.set_goal(self.mark(Wait(3)))
            else:
                self.step = "climbing home (no Word of Recall)"
                g = Dive(0)
                g.stop = False
                p.set_goal(self.mark(g))
            return None
        if self.phase == "town":
            return ("done", f"home ({self.home_why}) and the town kit run; {plural(self.levels, 'level')} in "
                            f"{(now - self.t0) / 60:.0f} min")
        return None

    LEAVE_MAX = 300                       # seconds to find a way off a finished level before recalling home
    QUIET_MIN, QUIET_XP = 3.0, 10.0       # a level that earned under 10 XP a minute over 3 minutes is left

    def quiet(self, p, now):
        """'quiet: N XP in 3 minutes' when this level has earned under QUIET_XP a minute over the last QUIET_MIN
        minutes (after at least that long on it), else None. The matrix: m33 spent its last 10 minutes on one 600 ft
        level for 22 XP; m34 had 4-minute stretches without a kill (good missions: 50-70 XP a minute)."""
        w = p.w
        exp = (w.ind.get("exp") or [0])[0]
        hist = self.__dict__.setdefault("xp_hist", [])
        if not hist or hist[-1][2] != w.level_t or now - hist[-1][0] >= 5:
            hist.append((now, exp, w.level_t))
        del hist[:max(0, len(hist) - 200)]
        if self.level != w.level_t or now - self.level_t0 < 60 * self.QUIET_MIN or w.monsters:
            return None
        old = [(t, e) for t, e, lt in hist if lt == w.level_t and now - t >= 60 * self.QUIET_MIN]
        if not old:
            return None
        gained = exp - old[-1][1]
        if gained < self.QUIET_XP * self.QUIET_MIN:
            return f"quiet: {gained} XP in {self.QUIET_MIN:g} minutes"
        return None

    def goal_ended(self, p, g, status, detail):
        """A plan goal finished: the level is done when its exploration is."""
        if isinstance(g, Explore) and self.phase == "level" and self.level == p.w.level_t:
            self.level_done = detail or status
        if isinstance(g, (Dive, Recall)) and status == "failed":
            self.fails += 1
            if self.fails > 6 and self.phase != "home":
                self.phase, self.home_why = "home", f"stuck: {detail}"


def split_specs(a):
    """Buy specs split on commas outside [..] and (..): `[3,+6]` is part of a name (m43)."""
    return [x.strip() for x in re.split(r",(?![^\[(]*[\])])", a) if x.strip()]


def singular(t):
    """Plural endings dropped, for name matching ("Flask of oil" finds
    "99 Flasks of oil": missions 17-18)."""
    return re.sub(r"\b(\w+?)(?:es|s)\b", r"\1", t.lower())


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


class QuietWait(Goal):
    """`goal quiet [SECS]` (the user, 10-27): time for the Navigator to think, plan, survey the map or sort the pack.
    The plan (or the goal it replaced) is paused; the Pilot walks to a quiet spot on ground already walked (a room,
    away from unexplored squares and doors: quiet_spot), rests there if hurt, and waits. It wakes when a monster that
    moves comes into view or something hits us (the fight reflexes defend as always), or when the time is up; then
    what it paused carries on, and the Navigator is told. In town it just waits (townspeople don't wake it)."""

    quiet = True                 # (its end is reported by itself, as an alert)

    def __init__(self, secs=120, prev=None):
        self.secs = int(min(600, max(10, float(secs))))
        self.name = f"quiet wait {self.secs}s"
        self.t0 = gnow()
        self.prev = prev
        self.spot = None
        self.walking = False

    def end(self, p, why):
        p.stop_resting()
        if self.prev is not None:
            p.resume_after = self.prev
            if p.plan and p.plan.pause_goal is self:
                p.plan.pause_goal = self.prev     # (the plan waits for the goal we paused, as before)
        then = (f"resuming '{self.prev.describe()}'" if self.prev is not None else
                "the trip plan carries on" if p.plan and p.plan.paused else "your move")
        p.notify("quiet_end", f"quiet wait: {why} after {gnow() - self.t0:.0f} s; {then}")
        return ("done", why)

    def tick(self, p):
        w = p.w
        hit = gnow() - w.last_hit_t < 2
        mob = [r for _, _, r in w.monsters if "NEVER_MOVE" not in r.flags] if w.in_dungeon else []
        if mob or hit:
            return self.end(p, "woke: " + (f"{mob[0].name} came into view" if mob else "something hit us"))
        aid = getattr(self, "wait_answer", None)
        if aid is not None:
            ans = [a for a in p.__dict__.get("arch_answers", []) if a[1] == aid and a[0] >= self.t0]
            if ans and not ans[-1][2].lower().startswith("more"):
                return self.end(p, f"the Architect answered #{aid}")
        if gnow() - self.t0 >= self.secs:
            return self.end(p, f"{self.secs} s are up")
        if w.in_dungeon and self.spot is None and w.pos:
            # (the user, 10-28: cap the wait by the food and light left -- at most a quarter of either; resting runs
            # the game clock ~10x)
            food, light = p.supply_minutes()
            left = min(m for m in (food, light) if m is not None) if light is not None else food
            cap = max(10, int(0.25 * 60 * left))
            if cap < self.secs:
                p.notify("tactic", f"quiet wait: {cap} s, not {self.secs} ({p.supply_text()})", news=True)
                self.secs = cap
            self.spot = p.quiet_spot() or w.pos
            if self.spot != w.pos and p.mover.go([self.spot]):
                self.walking = True
                p.notify("tactic", f"quiet wait: walking to a quiet spot at {self.spot[0]},{self.spot[1]} "
                                   f"({w.dist(self.spot)} away)", news=True)
        if self.walking:
            if p.mover.tick() == "moving":
                return None
            self.walking = False          # (arrived, or stuck: wait where we are)
        if w.hp_frac < p.orders["rest_to"]:
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
        self.last_agent = gnow()
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
        self.drainers_seen = set()     # (level_t, race name) drainer warnings given
        self.inferred = set()          # abilities seen in play (watch_abilities)
        self.unique_drop = None        # (level_t, pos, t) of the last unique killed
        self.aware_cache = (-1, set())
        self.policy_t = 0.0
        self.room_t = 0.0
        self.ability_sources = set()   # unidentified worn items that may give them
        # what each shop's owner is and what it charged (the town kit's prices and routing)
        self.stores_file = os.path.join(rundir, "stores.json")
        try:
            self.stores_seen = {int(k): v for k, v in json.load(open(self.stores_file)).items()}
        except (OSError, ValueError):
            self.stores_seen = {}
        self.stores_noted_t = 0.0
        self.ability_seen_t = gnow()
        self.debt_path = os.path.join(rundir, "navigator_debt.json")
        try:
            self.debt = json.load(open(self.debt_path))
        except (OSError, ValueError):
            self.debt = {"entries": []}
        try:
            self.keep = set(json.load(open(os.path.join(rundir, "keep.json"))))
        except (OSError, ValueError):
            self.keep = set()
        self.report_seq, self.last_report = 0, (0, 0.0)   # Navigator reports: number, time of the last
        self.hp_min_since = None       # lowest HP since the last audit_check
        self.escalation_t = 0.0        # last emergency-type alert (escape records)
        self.items_level, self.items_last, self.items_depth = None, [], 0   # this level's floor items (itemlist)
        self.equip_letters_lower = False  # item_index: a lowercase letter is an equipment letter (takeoff)
        self.phase_hist = collections.deque()   # emergency Phase Door times (futility check)
        self.traps_here, self.trap_seen_t = (None, 0), gnow()
        self.band_warned = (None, 0)   # (level_t, size) of the last band warning
        self.band_warned_t = 0.0
        self.thieves_seen = set()      # (level_t, race name) thief warnings given
        self.thief_hit_t = 0.0
        self.kills_t = gnow()     # messages scanned for unique kills
        self.item_pending = []         # (due, level_t, name): interesting_item alerts held 2.5 s
        self.unique_names = None
        self.fear_t = 0.0
        self.skipped_items = set()     # (level, square) of junk we chose to leave
        self.resume_after = None
        self.plan, self.plan_t = None, 0.0      # the Navigator's intent (plan trip), run by the Pilot
        # the belief state (step 2.5; the Advisor's starting-over memo §3.4): what the report
        # can't show from one snapshot
        self.mons_mem = {}           # name -> {"level": level_t, "pos", "n", "t", "danger", "unique"}
        self.hits = collections.Counter()      # (level_t, name) -> hits landed since it was last slain
        self.belief_msg_t = 0.0
        self.gain_hist = collections.deque(maxlen=80)    # (t, exp, gold) every 15 s
        try:
            self.standing = json.load(open(os.path.join(rundir, "standing.json")))
        except (OSError, ValueError):
            self.standing = []
        self.plan = TripPlan.load(self)           # (a restart mid-trip carries on with it)
        self.load_mission()                       # (and a mission with its label)
        if self.plan:
            self.log("plan_resumed", plan=self.plan.text, phase=self.plan.phase)
        self.autodestroy_t = 0.0
        self.parking = None
        self.light_t = self.light_warned = 0.0
        self.light_warned_key = None
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
        self.flee_fail_t = 0.0
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
        self.id_target = None
        self.weapons_t, self.weapon_tips = 0.0, set()
        self.found_t = gnow()
        self.unanswered = []                  # user messages the Navigator hasn't answered (say)
        self.nav_view, self.nav_view_events = (0.0, [], ""), []   # what the Navigator last read
        self.avoid_zones, self.avoid_names = {}, set()           # the Navigator's no-go zones
        self.structs, self.struct_t = {}, 0.0      # (level, (Y, X)) -> inner room / pit / nest found
        self.item_hold_until = 0.0            # a dive pauses after interesting_item
        self.far_seen = set()                 # (level, item) valuables seen beyond loot_radius
        self.effect_failures = 0
        self.redraw_t, self.redraw_level = 0.0, None
        self.factor_logged, self.rate_logged, self.factor_log_t = 1.0, None, 0.0
        self.group_warned = None
        self.mons_log_t = 0.0
        self.drains_here = (None, 0)          # (level, stat drains seen on it)
        self.still_goals = (None, set())      # (level, mover goals) before a stationary-monster fight
        self.still_fighting = None            # (level, position) of the stationary monster we're killing
        self.seen_blows = None
        self.unreachable = set()       # frontier tiles we failed to reach (this level)
        self.visited = set()           # squares we've stood on while exploring (not frontier)
        self.searched = set()          # (level, square) dead ends searched for secret doors
        self.level_seen = None
        self.phase_t = self.cure_t = self.noescape_t = 0.0
        self.escaping_to_stairs = False
        self.full_warned = 0.0
        self.running = True

    # --- logging / attention -------------------------------------------------

    def crop(self, rows=5, cols=15):
        """A small map snapshot around us, for the log (the Advisor: so
        situations can be checked afterwards)."""
        w = self.w
        if not w.rows or not w.pos:
            return None
        y, x = w.pos
        return [r[max(0, x - cols):x + cols + 1] for r in w.rows[max(0, y - rows):y + rows + 1]]

    def log(self, kind, **kw):
        rec = {"t": round(time.time(), 3), "kind": kind, "depth": self.w.depth, "pos": self.w.pos,
               "hp": self.w.hp, **kw}
        if kind in ("attention", "nav_journal", "user_note") and "crop" not in rec:
            rec["crop"] = self.crop()
        if kind in ("act", "attention", "goal", "goal_done", "goal_failed", "note"):
            self.recent_acts.append({"t": rec["t"], "kind": kind,
                                     "what": kw.get("cmd") or kw.get("what") or kw.get("goal") or kw.get("text"),
                                     "why": kw.get("why") or kw.get("detail")})
        self.dlog.write(json.dumps(rec) + "\n")

    # Events that don't need a decision (the pilot already acted): shown in
    # the next report instead of waking the agent
    NEWS = {"danger_avoided", "started", "tactic", "resumed", "plan"}
    # while a trip plan runs, these are news: the plan acts on them itself
    PLAN_QUIET = {"goal_done", "goal_failed", "interesting", "danger_seen", "band", "structure", "breeders", "drainer",
                  "fearer", "stuck", "interesting_item", "unique_slain", "pack_full", "thief", "unseen_attacker",
                  "fight_going_badly", "emergency"}

    def notify(self, what, detail=None, news=False, action=True):
        """action=False: an emergency notice that reports no escape action (waiting, fighting on, attacking a caster
        first): it doesn't count towards the emergency loop's three in 90 s (refactor-candidates A4)."""
        if what in ("emergency", "emergency_loop", "danger_seen", "danger_avoided", "fight_going_badly",
                    "unseen_attacker", "band", "stat_drained"):
            self.escalation_t = gnow()      # (escape records: stairs taken in an emergency)
        if what in ("emergency", "tactic") and gnow() - self.held_t < 0.05 and detail and \
                any(k in detail for k in ("quaffed", "read ", "phase")):
            # the action this reports was held, not sent (mission 10 reported 3
            # CLW quaffs with 1 CLW in the pack)
            self.log("note", text=f"not reported (held): {detail}")
            return
        ev = {"t": round(gnow(), 3), "what": what, "detail": detail,
              "goal": self.goal.describe() if self.goal else None}
        if what == "emergency" and action:
            self.emerg_times.append(gnow())
        source = None
        news_asked = news             # (before the plan turns its events into news: the band shadow's test)
        if self.plan and what not in ("plan", "plan_done", "plan_failed"):
            self.plan.on_event(self, what, detail, news or what in self.NEWS)
            if not self.plan.paused and what in self.PLAN_QUIET:
                news, source = True, "plan"   # (the plan handles these: the Navigator reads them as news)
        if what == "plan":
            source = "plan"
        extra = {"source": source} if source else {}
        if what == "emergency" and self.w.in_dungeon:
            extra["shadow"] = self.shadow_decision(detail)
        # (news_asked: under a trip plan every band notice became news first, and no band record was ever made -- m48)
        if what == "band" and self.w.in_dungeon and not news_asked:
            sh_band = self.band_shadow(detail)
            if sh_band:
                extra["shadow"] = sh_band
        if what in ("emergency", "emergency_loop"):
            # (the Advisor's estimator memo: the remembered map around @, 21x21, and the monsters, for replays)
            w = self.w
            if w.pos:
                y, x = w.pos
                extra["map21"] = ["".join(w.memory.get((yy, xx), " ") for xx in range(x - 10, x + 11))
                                  for yy in range(y - 10, y + 11)]
                extra["map_at"] = [y - 10, x - 10]
                extra["mons"] = [(my, mx, r.name) for my, mx, r in w.monsters]
        self.log("attention", what=what, detail=detail, **extra)
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
        # (m57 12:04: a Potion of Speed, the last of its stack, then 1 s later "quaff item=3" for Berserk -- the
        # letters had shifted and it drank a Cure Light Wounds; the Berserk "showed no effect" and was resent twice.
        # No item command until the pack has come back since the last one, 3 s at most)
        item_cmd = re.match(r"custom [qrEuzaF] item=", line) and not why.startswith("agent:")
        lt = self.__dict__.get("item_cmd_t", 0.0)
        stale = item_cmd and lt and self.w.inven_t < lt and gnow() - lt < 3
        if (self.pending_use and re.match(r"custom [rq] item=", line) and not why.startswith("agent:")) or stale:
            self.log("note", text=f"held ({'the pack has not come back since the last item command' if stale else 'a read/quaff is still unconfirmed'}): {why}")
            self.busy_until = gnow() + ghold(0.3)
            self.held_t = gnow()     # notify() drops the caller's "quaffed ..." report
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
        if item_cmd:
            self.item_cmd_t = gnow()
            self.w.inven_dirty = True        # (the next refresh fetches the pack: the hold above lasts ~0.3 s)
        self.last_action = (gnow(), line, why)
        self.busy_until = gnow() + ghold(hold)
        self.__dict__.setdefault("act_walls", collections.deque(maxlen=50)).append(time.time())
        mr = re.match(r"custom [ru] item=(\d+)", line)
        if mr:
            iu = next((i for i in self.w.items() if i["item"] == int(mr.group(1))), None)
            if iu and re.search(r"Teleport|Phase Door", iu["name"]):
                self.escape_read_t = gnow()
                self.escape_from = (self.w.pos, one_of(iu["name"]))    # (the status line's ESCAPE LANDING)
        self.log("act", cmd=line, why=why, by=self.__dict__.get("acting", "pilot"))
        self.log_escape(line, why)
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
                self.pending_use = {"line": line, "t": gnow(), "core": core, "tries": 0, "why": why}
                self.mover.hold_clear_until = gnow() + ghold(3.0)

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
                self.expects.append({"kind": kind, "t": gnow(), "why": why,
                                     "sig": self.effect_sig(kind)})
                return

    def pack_kinds(self):
        """{(tval, name)} of the pack, names without counts/inscriptions."""
        return {(i["tval"], kind_key(i["name"]) if " of " in i["name"] else flavour_key(i["name"]))
                for i in self.w.items() if i["tval"] in self.FLAVOURED or
                (i["tval"] == TV_FOOD and "Mushroom" in i["name"])}

    def watch_flavours(self):
        self.flavour_watch = {"t": gnow(), "before": self.pack_kinds(),
                              "unknown": {(i["tval"], flavour_key(i["name"])) for i in self.w.items()
                                          if self.unknown_flavour(i)}}

    def learn_flavours_tick(self, now):
        """After a read/quaff/use/aim/zap (incl. Identify): an unknown flavour
        that disappeared while a known kind of the same type appeared is that
        kind (the Advisor's flavour-messages memo: names drop the flavour once
        it's aware, so diff the pack)."""
        it = self.id_target
        if it:
            for ts, t in self.w.messages:
                m = re.match(r"^(?:In your pack|You are wearing|You are wielding|On your [^:]+|In your quiver): "
                             r"(.+?) \(([a-z])\)\.?$", t)
                if ts >= it["t"] and m and " of " in m.group(1) and it["letter"] in (None, m.group(2)):
                    self.learn_flavour(it["flavour"], kind_key(m.group(1)), "identified")
                    self.id_target = None
                    break
            if self.id_target and waited(it["t"], 5):
                self.id_target = None
        fw = self.flavour_watch
        if not fw or not waited(fw["t"], 1.0):
            return
        self.flavour_watch = None
        after = self.pack_kinds()
        gone = {k for k in fw["unknown"] if k not in after}
        new = {k for k in after - fw["before"]}
        said = [t for ts, t in self.w.messages if ts >= fw["t"] - 0.05]
        for j, t in enumerate(said):            # a stack used up: "You have no more Potions of X."
            m = re.match(r"You have no more (.+?)\.?$", t)
            # (not one destroyed, dropped or sold: mission 16's autodestroyed
            # Ring of Teleportation spoiled the Beryl Ring read next to it)
            if j and said[j - 1].startswith(("You destroy", "You drop", "You sold", "You have no room")):
                continue
            if m and " of " in m.group(1):
                k = kind_key(m.group(1))
                # (only an unknown of the same type: any vanished unknown made "Amber Amulet" = Scroll of Identify)
                tv = next((tv for tv, g in gone if type_word(g) == type_word(k)), None)
                if tv is not None and (tv, k) not in fw["before"]:
                    new.add((tv, k))
        for tv in {t for t, _ in gone}:
            g = [n for t, n in gone if t == tv]
            n = [k for t, k in new if t == tv and " of " in k]
            if len(g) == 1 and len(n) == 1:
                self.learn_flavour(g[0], n[0], "identified or used")

    def verify_effects(self):
        """Report actions whose effect never showed (3 s), instead of
        letting them pass as done."""
        now = gnow()
        keep = []
        for e in self.expects:
            if self.effect_sig(e["kind"]) != e["sig"]:
                continue                    # confirmed
            if not waited(e["t"], 3.0):
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
        # (a burning light's turns tick down between the two reads: "14402" vs
        # "14400 turns" was mission 17's only difference)
        def unlit(v):
            return re.sub(r"with \d+ turns", "with N turns", repr(v))
        diffs = {k: (model[k], fresh[k]) for k in model if model[k] != fresh[k] and
                 not (k == "hp" and (abs(model[k][0] - fresh[k][0]) <= 3 or w.adjacent_monsters())) and
                 not (k in ("pack", "equip") and unlit(model[k]) == unlit(fresh[k]))}
        self.audit_runs += 1
        self.log("audit_check", n=self.audit_runs, differences=len(diffs),
                 exp=st["ind"].get("exp"), clvl=w.clvl, depth_ft=w.depth_ft,   # (exp: for XP-rate studies)
                 stats={n: st["ind"].get(f"stat{i}") for i, n in enumerate(self.STAT_NAMES)},
                 blows=st["ind"].get("skills2", [None])[0], ac=st["ind"].get("armor"),
                 gold=st["ind"].get("gold", [None])[0], banked=self.banked(),
                 # per-check state (the Advisor's scorecard memo §5.4)
                 resting=bool(w.resting), in_combat=bool(w.adjacent_monsters() or gnow() - w.last_hit_t < 5),
                 recall_pending=bool(w.recall_pending), goal=self.goal.describe() if self.goal else None,
                 hp_min=self.hp_min_since)
        self.hp_min_since = None
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
        p, now = self.pending_use, gnow()
        if not p:
            return
        if self.dead or self.w.ghost:
            self.pending_use = None           # (mission 10 kept resending after death)
            return
        said = [t for ts, t in self.w.messages if ts >= p["t"] - 0.05]
        # (the server refused the read -- blind, confused, no light: m48's Word of Recall at 21:32:54 was refused 1 s
        # later, "You can't see anything.", and the Pilot waited 8 s for it and wouldn't try again. Now: done at once,
        # the escape timers reset, and teleport_item turns to the staff for 10 s)
        if any(t.startswith(("You can't see anything", "You are too confused", "You have no light to read"))
               for t in said):
            self.pending_use = None
            self.read_failed_t = gnow()
            self.escape_read_t = -99.0
            self.recall_t = 0.0
            self.notify("tactic", f"'{p['why']}': the read was refused ({next(t for t in said if t.startswith(('You ca', 'You are too', 'You have no l')))}): "
                                  "the next escape uses a staff or a cure first")
            return
        if any(t.startswith("You have") and p["core"] in t for t in said) or \
                any("The air about you becomes charged" in t for t in said):
            self.pending_use = None
            self.w.inven_dirty = True          # re-read the pack now, before the next use
            self.w.refresh()
            return
        # Never resent: a second Word of Recall cancels the first, a second Teleportation lands somewhere else (the
        # Advisor's estimator memo: m26 resent a recall that had gone through). Wait longer for the answer, then give
        # up on it -- the next decision sees whether it happened
        if p["core"] in ("Word of Recall", "Teleport"):
            if waited(p["t"], 8.0):
                self.pending_use = None
                self.notify("tactic", f"'{p['why']}': no answer seen in 8 s; not resending it (a second read would "
                                      "cancel or double it)")
            return
        if not waited(p["t"], 2.5):
            return
        if p["tries"] >= 2 or not self.w.in_dungeon:
            self.pending_use = None
            self.notify("tactic", f"'{p['why']}' still shows no effect after 2 resends: giving up on it")
            return
        p["tries"] += 1
        p["t"] = now
        self.mover.hold_clear_until = now + ghold(3.0)
        self.c.send(p["line"])
        self.log("act", cmd=p["line"], why=f"resend (no effect seen): {p['why']}")
        self.notify("tactic", f"'{p['why']}' showed no effect: resent it")

    ESCAPE_WHY = re.compile(r"low HP|flee|danger|emergency|monsters close|phasing|group|potions too weak|"
                            r"last resort|unseen|afraid|cornered", re.I)

    def log_escape(self, line, why):
        """An `escape` record for every escape sent (the Advisor's scorecard memo
        §5.3): kind, trigger, HP. Its result shows in the records after it."""
        w = self.w
        kind = None
        m = re.match(r"custom r item=(\d+)", line)
        if m:
            it = next((i for i in w.items() if i["item"] == int(m.group(1))), None)
            name = it["name"] if it else why
            if "Phase Door" in name or "phase door" in why.lower():
                kind = "phase"
            elif "Word of Recall" in name or "word of recall" in why.lower():
                kind = "wor_escape" if (w.in_dungeon and (self.ESCAPE_WHY.search(why) or w.hp_frac < 0.5)) \
                    else "wor_travel"
            elif "Teleport" in name:
                kind = "teleport"
        elif re.match(r"custom [<>]$", line) and (isinstance(self.goal, (Flee, Recover)) or self.ESCAPE_WHY.search(why)
                                                    or gnow() - self.escalation_t < 10):
            kind = "stairs"
        if kind:
            self.last_escape = (gnow(), kind, why[:120], list(w.hp[:2]))
            self.log("escape", escape=kind, trigger=why[:120], hp=w.hp[:2],
                     adjacent=[r.name for *_, r in w.adjacent_monsters()][:6],
                     goal=self.goal.describe() if self.goal else None)

    def take_stairs(self, which):
        self.mover.stop()
        self.w.last_stairs_cmd = (which, gnow())
        self.cmd(f"custom {which}", f"stairs {which}", hold=0.3)

    def confusion_lock(self):
        """Confused 8 s on end with the goal waiting or monsters adjacent: cure it (m55: 27 Hummerhorns at 800 ft
        kept Dive04 confused from 17:04 to 17:19 -- the dive waited "for it to wear off", two staff uses failed
        (confusion halves device skill), the recall couldn't be read; the Navigator quaffed CCW/CSW by hand). The
        cheapest that ends it (Cure Serious, then Critical: use-obj.c), at most every 8 s; in the clear window the
        goal (or the breeders' teleport, a read) acts."""
        w, now = self.w, gnow()
        if not w.flag("confused"):
            self.conf_since = None
            return False
        self.conf_since = self.__dict__.get("conf_since") or now
        if now - self.conf_since < 8 or not waited(self.__dict__.get("conf_cure_t", 0.0), 8) or now < self.busy_until:
            return False
        pot = next((i for k in ("Cure Serious", "Cure Critical") for i in w.items(tval=TV_POTION) if k in i["name"]),
                   None)
        n = self.__dict__.setdefault("conf_cures", {})
        if not pot or n.get(w.level_t, 0) >= 4:          # (a swarm re-confuses: at most 4 cures a level)
            return False
        n[w.level_t] = n.get(w.level_t, 0) + 1
        self.conf_cure_t = now
        self.cmd(f"custom q item={pot['item']}", f"confused {now - self.conf_since:.0f} s: quaff {pot['name']}",
                 hold=0.6)
        self.notify("tactic", f"confused for {now - self.conf_since:.0f} s"
                              + (f" with {len(w.adjacent_monsters())} adjacent" if w.adjacent_monsters() else "")
                              + f": quaffed {one_of(pot['name'])} to act again", news=True)
        return True

    def confusion_window(self):
        """Just cured of a confusion lock, with 3+ monsters adjacent: teleport away in the clear second before the next
        bite (M5, 10-28: 26 Hummerhorns re-confused Dive04 within a second of each of 4 cures; the m55 Navigator's
        way out was a cure and an immediate read). The goal carries on from the landing, unconfused."""
        w, now = self.w, gnow()
        t = self.__dict__.get("conf_cure_t", 0.0)
        if not (w.in_dungeon and 0.3 < now - t < 4 and not w.flag("confused") and now >= self.busy_until) or \
                self.__dict__.get("conf_tele_t", 0.0) >= t or len(w.adjacent_monsters()) < 3:
            return False
        tp = self.teleport_item()
        if not tp:
            return False
        self.conf_tele_t = now
        self.cmd(f"custom {tp[0]} item={tp[1]['item']}", f"clear for a moment among {len(w.adjacent_monsters())}: "
                                                          f"teleport away ({one_of(tp[1]['name'])})", hold=0.8)
        self.notify("tactic", f"cured, with {len(w.adjacent_monsters())} adjacent: teleported away before the next "
                              "bite", news=True)
        return True

    def escape_line(self):
        """The status header's escape marker (session 8: a staff's teleport showed "no change", then landed; a scroll
        read on top was refused, and nobody could tell which escape was still landing)."""
        t, (pos, name) = getattr(self, "escape_read_t", -99.0), getattr(self, "escape_from", (None, None))
        age = gnow() - t
        if not name or age > 6:
            return ""
        # (m55: both staff uses failed confused -- "You failed to use the staff properly" -- and the line said LANDING)
        if any(ts >= t - 0.3 and t_.startswith(("You failed to use", "You have no charges", "You can't see",
                                                  "You are too confused")) for ts, t_ in self.w.messages):
            return f" · escape FAILED ({name}, {age:.0f} s ago: the game refused it)"
        if self.w.pos == pos and age <= 3:
            return f" · ESCAPE LANDING ({name}, {age:.0f} s ago: don't repeat it yet)"
        if self.w.pos != pos and pos and self.w.pos:
            return f" · escaped ({name}, {age:.0f} s ago: moved {self.w.dist(pos)} squares)"
        return ""

    def start_resting(self):
        if not self.w.resting and gnow() > self.busy_until:
            self.cmd("rest", "rest", hold=1.0)
            self.w.status_t = 0

    def stop_resting(self):
        if self.w.resting:
            self.cmd("rest", "stop resting", hold=0.5)
            self.w.status_t = 0

    # --- perception helpers --------------------------------------------------

    def frontier(self, center=None, radius=None, rubble=False):
        """Known open squares next to unknown ones (rubble=True: rubble squares
        next to unknown ones instead, a way on by digging)."""
        mem = self.w.memory
        out = []
        for (y, x), ch in mem.items():
            if rubble != (ch == ":"):
                continue
            if ch in "#%* " or ch in "12345678" or (y, x) in self.unreachable:
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
            # ('=' and '~' are terrain only on the surface: in the dungeon they're
            # rings, amulets, chests and lights -- mission 16's rings were missing)
            skip = "#%.'+<>^;:* 12345678" + ("" if w.in_dungeon else "=~")
            return [p for p, ch in w.memory.items() if ch not in skip
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
        # (a rating the rulebook marks as about strength alone is the duel simulator's to judge, below:
        # Ulfast fled on sight as "rated 4" while the hunt check allowed him -- the set-piece harness)
        strength_only = getattr(r, "veto_reason", None) == "strength"
        if r.danger == 5 and not strength_only:
            return "rated 5: leave on sight"
        if r.danger == 4 and lev < r.level + 8 and not strength_only:
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
        # A fight we'd lose on average, by the Advisor's duel simulator (the set-piece harness: Lugdush, lvl
        # 21 and unrated, fired no rule though a fight costs ~350 HP of 265)
        sim = self.sim_loss(r) if r.level >= lev - 3 and "NEVER_MOVE" not in r.flags else None
        if sim and sim > 0.8 * max(1, self.w.hp[0]):
            return f"a fight costs ~{sim:.0f} HP on average (the duel simulator)"
        # Summons land next to us and stay after the summoner dies (memo §1.2)
        if r.summoner and r.level >= lev - 5:
            return "summons"
        return None

    def worst_3turns(self, races):
        """The rulebook's worst melee in the next 3 player turns at our AC (worst_3turns_acNN: the AC
        reduction of HURT blows, recoil, speed), summed over the monsters, with a caster's spell_max if
        higher; the old 2.5 raw worst rounds when a race has no row."""
        rows = self.fight_rows()
        ac = (self.w.ind.get("armor") or [0])[0] or 0
        col = min((20, 40, 60), key=lambda a: abs(a - ac))
        total = 0.0
        for r in races:
            row = rows.get(getattr(r, "idx", None)) or {}
            if row.get(f"worst_3turns_ac{col}"):
                v = float(row[f"worst_3turns_ac{col}"])
                if r.spells:
                    v = max(v, float(row.get("spell_max") or 0))
            else:
                v = 2.5 * (r.worst_melee[0] or 0) * (r.speed_x or 1)
            total += v
        return total * self.our_slowness()      # (three of our turns are longer when we're slowed: m26)

    def sim_loss(self, r):
        """fight_sim's mean HP lost dueling r at our current profile, cached by race, level,
        weapon, AC and HP to the nearest 10% (300 duels, ~0.05 s for a new key)."""
        w = self.w
        wt = [x for x in self.weapon_table() if x[3]]
        key = (getattr(r, "idx", None), w.clvl, wt[0][0] if wt else None, (w.ind.get("armor") or [0])[0],
               round(w.hp_frac * 10))
        cache = self.__dict__.setdefault("_sim_cache", {})
        if key not in cache:
            sm = self.fight_sim(r, n=300)
            cache[key] = sm["loss_mean"] if sm else None
        return cache[key]

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
        now = gnow()
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
        # (and HP within 2.5 worst-case rounds of one adjacent monster: Brodda
        # took 151 -> 27 in five rounds of 48 before flee_hp fired at 58 --
        # the Advisor's missions 15-16 replay, change 3)
        # (the Advisor's emergency-threshold memo, rulebook r4: the worst melee of the adjacent monsters in
        # the next 3 player turns, against our AC and at their attack rate -- not 2.5 raw worst rounds,
        # which broke off a vetted Ulfast hunt at 145 HP and under-counted fast monsters)
        worst = self.worst_3turns([r for *_, r in w.adjacent_monsters()])
        hard = worst > 0 and w.hp[0] <= worst and w.hp_frac < 0.9
        if (w.hp_frac < o["flee_hp"] or hard) and (mons_near or now - w.last_hit_t < 5):
            why = "low HP" if w.hp_frac < o["flee_hp"] else f"HP {w.hp[0]} within 3 turns of the worst ({worst:.0f})"
            if not self.escape(why) and self.mover.active and not self.escaping_to_stairs:
                self.mover.stop()
            return True
        # 2'. Group danger (the Borg's rule, Advisor memo 2026-09-28 §3.1)
        if self.group_tick(now):
            return True
        # 2a. Status cures, in combat only (out of combat, rest it off: the
        # user). Stun can become a knock-out; blind or confused can't read.
        self.hard_fight_shadow(now)          # (never acts: the estimator's view of the fight's start)
        if self.speed_start_tick(now):
            return True
        if self.berserk_tick(now):
            return True
        if self.status_tick(now, mons_near):
            return True
        # 3. Arrival into danger (connected stairs: the way back is underfoot)
        # A stairs command gets no answer at all if it comes too soon after the
        # level change (seen: '<' 0.7 s after arriving was ignored), so retry
        # after 1.2 s while still on the stairs
        stairs_pending = w.last_stairs_cmd and not waited(w.last_stairs_cmd[1], 1.2)
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
        # A slow caster with weak melee and the stairs far away: fleeing just
        # gives it free casts on the way (mission 15: Wormtongue, ~6 melee per
        # turn, the stairs 70-80 away, twice; the user: stand and fight; the
        # Advisor's replay: even a '>' 12 away gave ~18 s of free casts)
        stairs_d = min((w.dist(q) for q in w.find("<>")), default=999)
        # (weak by the worst case too: mission 19's Ranger, ~25 a turn and 40 at
        # worst, passed the average test and the Navigator hunted it: 220 -> 67)
        if near_danger and stairs_d > 8 and all(
                (r.speed_x or 1) <= 1 and r.per_turn < w.hp[0] / 8 and (r.worst_melee[0] or 0) < w.hp[0] / 8
                and r.spells for r in near_danger):
            if now - self.flee_t > 30:
                self.flee_t = now
                r0 = near_danger[0]
                self.notify("danger_seen", f"{self.danger_text(r0)} in view, stairs {stairs_d} away: NOT fleeing "
                                           f"(no faster than you, melee ~{r0.per_turn:.0f} a turn, "
                                           f"{r0.worst_melee[0]:.0f} at worst; its danger is spells, and a long walk "
                                           "gives it free casts). Fight it (goal hunt) or recall")
            near_danger = []
        if near_danger and now - self.flee_t <= 10 and self.flee_fail_t >= self.flee_t and \
                not isinstance(self.goal, Recall) and not self.recall_started(now):
            # the flee failed (no stairs): flee_t mustn't block the Word of
            # Recall / Phase Door fallback for 10 s (the Advisor's replay)
            self.flee_failed()
            if self.recall_started(now):
                return True
        # a summoner just seen, not adjacent and no faster than us: walk away out of its sight (the
        # user, 2026-10-23); the flee below only when walking away isn't safe or has failed here
        # (a summoner the server's list names before the map shows it -- A8w fled 1 s before the
        # decode: wait up to 1.5 s for its position, then decide)
        if near_danger and w.hp_frac >= 0.5 and all(self.danger_why(r) == "summons" for r in near_danger) and \
                any(r.name not in {q.name for *_, q in w.monsters} for r in near_danger) and \
                not isinstance(self.goal, (Flee, Recover, Recall, WalkAway)):
            self.summoner_hold_t = getattr(self, "summoner_hold_t", 0) if now - getattr(self, "summoner_hold_t", 0) < 5 \
                else now
            if now - self.summoner_hold_t < 1.5:
                return False
        if near_danger and not isinstance(self.goal, (Flee, Recover, Recall, WalkAway)) and now - self.flee_t > 10 \
                and "danger" in o["stop_on"] and not self.hunt_ordered(now, near_danger[0].name) \
                and self.walk_away_ok(near_danger):
            self.flee_t = now
            names = sorted({r.name for r in near_danger})
            if self.goal is not None and not isinstance(self.goal, WalkAway):
                self.resume_after = self.goal
            self.set_goal(WalkAway(names))
            self.notify("tactic", f"{', '.join(names)} (summons) in view, not adjacent: walking away out of its "
                                  "sight instead of fleeing the level", news=True)
            return True
        if near_danger and not isinstance(self.goal, (Flee, Recover, WalkAway)) and now - self.flee_t > 10 \
                and "danger" in o["stop_on"] and not self.hunt_ordered(now, near_danger[0].name):
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
        # 3a''. A summon trap ("You are enveloped in a cloud of smoke!", cmd1.c 1049): 3-5 awake monsters from 5 levels
        # deeper, uniques allowed, appear around us -- m26's Nar group (the Advisor's structures memo). Phase Door at
        # once, before they act; the danger rules take it from there
        smoke = [ts for ts, t in w.messages if t.startswith("You are enveloped in a cloud of smoke") and now - ts < 2]
        if smoke and w.in_dungeon and max(smoke) > getattr(self, "smoke_t", 0) and not w.flag("blind") \
                and not w.flag("confused"):
            self.smoke_t = max(smoke)
            pd = w.tagged("r", 1) or next((i for i in w.items(tval=TV_SCROLL) if "Phase Door" in i["name"]), None)
            if pd:
                self.phase_t = now
                self.phase_hist.append(now)
                self.cmd(f"custom r item={pd['item']}", "summon trap: phase door before they act", hold=0.6)
                self.notify("emergency", "a summon trap (monsters from 5 levels deeper appear around us): phased away "
                                         "at once")
                return True
        # 3a'. Slowed to half speed or worse with something on us: a Potion of Speed (m26: Gorged and slowed to
        # -20 among six monsters; the Architect quaffed one by hand)
        if self.our_slowness() >= 2 and (w.adjacent_monsters() or now - w.last_hit_t < 2) and \
                waited(getattr(self, "speed_t", 0), 40) and not self.buff_on("fast"):    # (a potion lasts ~20-45 turns)
            pot = next((i for i in w.items(tval=TV_POTION) if "Speed" in i["name"]), None)
            if pot:
                self.speed_t = now
                self.cmd(f"custom q item={pot['item']}", f"slowed ({(w.ind.get('speed') or [0])[0]}) in a fight: "
                                                         f"quaff {pot['name']}", hold=0.6)
                self.notify("tactic", f"slowed to {(w.ind.get('speed') or [0])[0]} with monsters on us: quaffed "
                                      f"{one_of(pot['name'])}")
                return True
        # 3b'. Afraid (a warrior can't melee). The user: if not in danger, don't
        # spend consumables -- kite over cleared ground until it wears off; only
        # in danger cure it (Boldness/Heroism/Berserk) or phase away.
        if w.flag("afraid") and mons_near:
            # (or hit by several while we can't hit back: m26 kited, afraid, among a yeek band and a Dark hound
            # until the Navigator quaffed Heroism by hand)
            danger = w.hp_frac < o["think_hp"] or bool(self.dangers()) or len(w.adjacent_monsters()) >= 2 or \
                w.damage_rate(3.0) > 0.02 * max(1, w.hp[1])
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
                pot = self.fear_cure()
                if pot:
                    self.cmd(f"custom q item={pot['item']}", f"afraid and in danger: quaff {pot['name']}", hold=0.6)
                    self.notify("tactic", f"afraid and in danger: quaffed {one_of(pot['name'])}")
                    return True
                tp = self.teleport_item() if self.has_rule("afraid", "teleport") else None
                if tp and w.adjacent_monsters() and (tp[0] == "u" or not (w.flag("blind") or w.flag("confused"))):
                    self.cmd(f"custom {tp[0]} item={tp[1]['item']}", "afraid, no cure: teleport (the Navigator's rule)",
                             hold=0.6)
                    self.notify("rule", f"afraid with no fear cure: teleported ({one_of(tp[1]['name'])}) -- your "
                                        "`react afraid teleport`")
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
        if still and self.stairs_beside_still(still):
            still = []
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
                    self.phase_hist.append(now)
                    self.cmd(f"custom r item={pd['item']}", f"phase away from {f.name}", hold=0.6)
                    return True
            if self.retreat_step(fearers):
                return True
        # 3c. Light
        if self.town_light(now):
            return True
        # (no light at all in the dungeon: wield one even with a monster adjacent -- the set-piece
        # harness's A7 fought a Hill giant in the dark after an unexpected recall)
        unlit = w.depth != 0 and not any(i["tval"] == TV_LITE for i in w.items(equip=True))
        if (not w.adjacent_monsters() or unlit) and self.keep_light(now):
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
            # no food: a Scroll of Satisfy Hunger (the town kit counts them as food; the reflex
            # didn't read them, and Dive04 went Weak with four in the pack: the set-piece harness)
            # (only when Weak: it fills to just under Gorged (use-obj.c, PY_FOOD_MAX - 1), so the next potion
            # makes you Gorged, -10 speed -- m26 read it Hungry at 03:20 and fought the yeek band Gorged)
            sat = next((i for i in w.items(tval=TV_SCROLL) if "Satisfy Hunger" in i["name"]), None)
            if sat and w.hunger <= 1 and now - self.eat_t > 10 and not w.flag("blind") and not w.flag("confused"):
                if not any(i["tval"] == TV_LITE for i in w.items(equip=True)):
                    return self.wear_light("a light to read Satisfy Hunger by")
                self.eat_t = now
                self.cmd(f"custom r item={sat['item']}", f"hungry ({w.hunger}), no food: read Satisfy Hunger", hold=1.0)
                self.notify("tactic", "hungry and no food: read a Scroll of Satisfy Hunger")
                return True
            if sat:
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
            # townfarm hits an adjacent thief itself (auto-retaliate picks its own
            # target: mission 18 killed 7 urchins and a dog while one stole 67)
            if isinstance(self.goal, TownFarm) and any(any("EAT_" in b for b in r.blows) for *_, r in adj):
                return False
            # In the dungeon too: with others adjacent, hit the thief first
            # (mission 21: a Brigand took an {excellent} armour from the pack)
            thieves = [m for m in adj if any(b.split(":")[1:2] in (["EAT_ITEM"], ["EAT_GOLD"]) for b in m[2].blows)]
            if thieves and len(adj) > 1 and w.depth and waited(self.thief_hit_t, 0.35) and \
                    not isinstance(self.goal, (Flee, Recall)):
                t = min(thieves, key=lambda m: not any("EAT_ITEM" in b for b in m[2].blows))
                self.thief_hit_t = now
                self.c.send("clear")
                self.cmd(f"walk {direction(w.pos, t[:2])}", f"hit the {t[2].name} first (a thief)", hold=0.2)
                return True
            return not isinstance(self.goal, (Goto, Flee))
        # Pick up what we're standing on ("You see a ..." right after a step)
        if o["pickup"] == "all" and not adj and not w.store:
            seen = [(ts, t) for ts, t in w.messages if now - ts < 3 and t.startswith("You see ")
                    and "no items" not in t]
            if seen and self.is_junk_name(seen[-1][1][8:].rstrip(".")):
                # known junk: leave it (it filled the pack on the way down) -- or, at a quiet moment, destroy it
                # where it lies (the user, 10-25: less clutter on the map and in the report's Items line). Once per
                # sighting: the message stays "recent" 3 s, and m44 stepped on while engaging an Ogre and sent the
                # destroy again on 3 empty squares ("There's nothing on the floor")
                done = self.__dict__.setdefault("junk_msgs_done", set())
                if (w.level_t, w.pos) not in self.skipped_items and seen[-1][0] not in done:
                    done.add(seen[-1][0])
                    self.destroy_floor_junk(seen[-1][1][8:].rstrip("."), now)
                seen = []
                self.skipped_items.add((w.level_t, w.pos))
            if seen and (w.level_t, w.pos) in self.skipped_items:
                seen = []         # junk we left, or what the Navigator dropped here
            if seen and not w.in_dungeon and self.is_stash_item(seen[-1][1]) and \
                    not (self.__dict__.get("fetching") and self.fetching in seen[-1][1]):
                seen = []         # (the tavern stash stays there: the user, 10-26)
            # By value (restructure step 2.1; the Advisor's set-pieces C3, C4): a unique's
            # drop always; with the pack full, swap the cheapest non-kit item for a
            # better find; otherwise leave it and say so. (The bulky-gear rule this
            # replaces lost Brodda's Scimitar in mission 23.)
            # (m55 17:00:14: a Scroll of Light picked up mid-flee from a Black orc band. Fleeing with monsters in view,
            # only a find worth over 500 is worth the turn)
            if seen and isinstance(self.goal, (Flee, BandLeave, WalkAway)) and w.monsters and \
                    self.iv(seen[-1][1][8:].rstrip(".")).value < 500:
                seen = []
            if seen and not self.pickup_room(seen[-1][1][8:].rstrip(".")):
                seen = []
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
        # 5b. A monster worth killing a few steps off: go and fight it, then carry on (the user, m43)
        if self.engage_tick(now):
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

    ENGAGE_STEPS = 7          # how far a detour to fight may go (path steps)
    ENGAGE_GIVE_UP_S = 20

    def engage_tick(self, now):
        """The user (m43): "The char often is near enemies but doesn't engage them ... it could kill the monster and
        then run after" -- "and this mustn't override legit reasons not to engage (kiting, fleeing...)". A mobile
        monster a few steps off that the hunt check allows: walk to it and let auto-retaliate fight (section 5),
        then the goal carries on. Only while exploring or diving, HP at least think_hp, not blind/confused/afraid/
        slowed, no live band, no dangerous monster or summoner in view, not a breeder, not on the avoid list, not
        while the plan is leaving the level for a reason. The escapes, the group/choke rules and the walk-away run
        earlier in the reflexes, so they still win. Gives up after ENGAGE_GIVE_UP_S."""
        w = self.w
        st = self.__dict__.setdefault("engage", {"target": None, "t0": 0.0, "replan_t": 0.0, "dropped": set()})
        g = self.goal
        leaving = self.plan is not None and str(getattr(self.plan, "level_done", "") or "").startswith("left")
        ok = (w.in_dungeon and w.depth and w.pos and (g is None or isinstance(g, (Explore, Dive))) and not leaving
              and w.hp_frac >= self.orders.get("think_hp", 0.65) and not self.band_live()
              and not any(w.flag(k) for k in ("blind", "confused", "afraid")) and self.our_slowness() <= 1
              and not w.recall_pending)
        mons = [m for m in w.monsters if "NEVER_MOVE" not in m[2].flags]
        if ok and any(self.danger_why(m[2]) for m in mons):
            ok = False                               # (a danger in view: the flee/walk-away rules decide)
        if not ok:
            if st["target"]:
                st["target"] = None
                self.mover.stop()
            return False
        tgt = st["target"]
        if tgt:
            cur = next((m for m in mons if m[2].name == tgt), None)
            if cur is None or now - st["t0"] > self.ENGAGE_GIVE_UP_S:
                st["target"] = None                  # (killed, gone, or not reached: carry on)
                if cur is not None:
                    st["dropped"].add((w.level_t, tgt))
                self.mover.stop()
                return False
        else:
            cands = []
            for y, x, r in mons:
                if w.dist((y, x)) < 2 or w.dist((y, x)) > self.ENGAGE_STEPS or "MULTIPLY" in r.flags or \
                        (w.level_t, r.name) in st["dropped"] or any(n in r.name.lower() for n in self.avoid_names):
                    continue
                if r.level < w.clvl - 20:
                    continue                         # (no XP worth the detour)
                cache = self.__dict__.setdefault("engage_ok", {})
                key = (w.level_t, r.name)
                if key not in cache:
                    try:
                        cache[key] = self.hunt_refusal(r.name)[0] is None
                    except Exception:
                        cache[key] = False
                if cache[key]:
                    cands.append((w.dist((y, x)), y, x, r))
            if not cands:
                return False
            d, y, x, r = min(cands, key=lambda c: c[0])
            st.update(target=r.name, t0=now, replan_t=0.0)
            self.log("act", cmd="engage", why=f"engage {r.name} (L{r.level}, {d} away) on the way", by="pilot")
            tgt = r.name
        cur = next(m for m in mons if m[2].name == tgt)
        if now - st["replan_t"] > 1.5 or not self.mover.active:
            st["replan_t"] = now
            near = [(cur[0] + dy, cur[1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
            if not self.mover.go(near) or len(self.mover.path) > self.ENGAGE_STEPS + 2:
                self.mover.stop()
                st["dropped"].add((w.level_t, tgt))
                st["target"] = None
                return False
        self.mover.tick()
        return True

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

    def hunt_ordered(self, now, what):
        """The Navigator ordered this hunt in the last 2 minutes: the automatic
        'dangerous monster' and 'unseen attacker' flees don't replace it (mission
        22: hunts ordered on a danger alert were overridden by the flee).
        Emergencies and the 1x group-danger exit still apply."""
        g = self.goal
        if not (isinstance(g, Hunt) and getattr(g, "by_navigator", False) and now - self.goal_t < 120):
            return False
        if getattr(g, "kept_warned", None) != what:
            g.kept_warned = what
            self.notify("tactic", f"hunting {g.target} as ordered: not fleeing from {what} (emergency escapes "
                                  "still apply)", news=True)
        return True

    def walk_away_ok(self, rs):
        """True if every danger in view is only a summoner, seen on the map, 3+ squares off, no
        faster than us, nothing has been summoned yet, HP is at half or more, and walking away
        hasn't already failed on this level."""
        w = self.w
        if w.hp_frac < 0.5 or self.__dict__.setdefault("walkaway_failed", set()) & {w.level_t}:
            return False
        if any(t for ts, t in w.messages if gnow() - ts < 10 and "summons" in t):
            return False
        mine = 110 + int(w.ind.get("speed", [0])[0] or 0)
        pos = {r.name: (y, x) for y, x, r in w.monsters}
        return all(self.danger_why(r) == "summons" and r.name in pos and w.dist(pos[r.name]) >= 3 and r.speed <= mine
                   for r in rs)

    def phase_futile(self, now):
        """3 Phase Doors in the last 20 s: the monsters keep reaching us."""
        while self.phase_hist and now - self.phase_hist[0] > 20:
            self.phase_hist.popleft()
        return len(self.phase_hist) >= 3

    @property
    def escaping_to_stairs(self):
        """The mover's current walk is escape()'s walk to stairs. Tied to that walk (Mover.walk_id) on this level:
        arriving, a stop, any later go() (Explore etc. reuse the mover) or a new level ends it. (It was a plain flag
        never reset: after the first escape walk every walk was ticked as one, and the emergency reflex stopped
        stopping the mover -- refactor-candidates A1.)"""
        tag = getattr(self, "_escape_walk", None)
        return tag is not None and bool(self.mover.active) and \
            tag == (getattr(self.mover, "walk_id", None), self.w.level_t)

    @escaping_to_stairs.setter
    def escaping_to_stairs(self, on):
        self._escape_walk = (getattr(self.mover, "walk_id", None), self.w.level_t) if on else None

    def escape(self, why):
        """Emergency: stairs underfoot > out of combat, rest (never potions)
        > (in melee) Phase Door > (not in melee) walk to nearby stairs, else
        a cure potion. Rate-limited: Phase Door
        again and again doesn't shake a pack (it burned 10 scrolls in 10 s)."""
        w = self.w
        now = gnow()
        if w.last_stairs_cmd and not waited(w.last_stairs_cmd[1], 1.2):
            return True           # already on our way (retried after 1.2 s)
        if self.emergency_loop(now):
            return True
        # (only with something here: arriving by stairs you stand on stairs again, and m26 bounced 650 <-> 600
        # ft four times in 12 s at 18% HP with a recall pending and nothing in view)
        threatened = bool(w.monsters) or now - w.last_hit_t < 2
        if w.standing_on in ("<", ">") and not threatened:
            return False
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
        # One turn from death (the adjacent monsters' worst turn at our AC is about our HP): get out now --
        # Teleportation, else Phase Door, rate limit or not. Otherwise Speed first, at the start of an emergency:
        # +10 doubles our turns against everything here (the user, 10-25; m30's crowd took 303 -> 115 in ~70 s)
        one_turn = bool(adj) and self.worst_3turns([r for *_, r in adj]) / 3 >= 0.9 * w.hp[0]
        if one_turn and can_read:
            tele = next((i for i in w.items(tval=TV_SCROLL) if "Teleportation" in i["name"]), None)
            if tele or pd:
                use = tele or pd
                if not tele:
                    self.phase_t = now
                    self.phase_hist.append(now)
                self.cmd(f"custom r item={use['item']}", f"{why}: one turn from death: {use['name']}", hold=0.6)
                self.notify("emergency", f"{why}: one turn from death ({', '.join(sorted({r.name for *_, r in adj}))} "
                                         f"adjacent): read {one_of(use['name'])}")
                return True
        sp = next((i for i in w.items(tval=TV_POTION) if "Speed" in i["name"]), None)
        if sp and not one_turn and not self.buff_on("fast") and waited(getattr(self, "speed_t", 0), 20):
            self.speed_t = now
            self.cmd(f"custom q item={sp['item']}", f"{why}: quaff {sp['name']} (an emergency: speed first)", hold=0.6)
            self.notify("emergency", f"{why}: quaffed {one_of(sp['name'])} first")
            return True
        # Last resort, started early because it takes 15-34 turns (8-23 s): Word of Recall
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
        # Phasing that isn't working: 3 in 20 s and they're still on us (mission
        # 22 read 10 in ~20 s, twice). Start the recall, keep one or two Phase
        # Doors for when HP is really low
        if adj and pd and can_read and self.phase_futile(now) and w.hp_frac >= 0.2:
            if not self.recall_started(now) and w.in_dungeon:
                wor = next((i for i in w.items(tval=TV_SCROLL) if "Word of Recall" in i["name"]), None)
                if wor:
                    self.recall_t = now
                    self.cmd(f"custom r item={wor['item']}", f"{why}: phasing isn't shaking them: word of recall",
                             hold=0.5)
                    self.notify("emergency", f"{why}: 3 Phase Doors in 20 s and they're still adjacent: read Word "
                                             "of Recall; Phase Door now only below 20% HP")
                    return True
            pd = None
        # A summoner or status caster beside us that dies in two rounds: kill it first (the Advisor's estimator
        # memo: m30's Druid paralysed, blinded three times and summoned three times, and was never attacked)
        if self.kill_caster_step(adj, why):
            return True
        # Four or more about in the open: Teleportation, not Phase Door (no monster flow in this build: they walk
        # straight back unless a wall intervenes; 4 of m30's 5 phases landed 6-7 squares from contact)
        crowd = [m for m in w.monsters if "NEVER_MOVE" not in m[2].flags and w.dist(m[:2]) <= 5]
        tele = self.teleport_item()
        # (afraid with 2+ adjacent: we can't hit back, and a phase lands within reach again -- m41 phased 3 times
        # with a Half-orc, a Master yeek and a 2-headed hydra on it, 156 -> 123 HP, then read Word of Recall)
        pinned = w.flag("afraid") and len(adj) >= 2
        if adj and tele and ((len(crowd) >= 4 and not self.mover.in_corridor()) or pinned) and \
                (can_read or tele[0] == "u") and waited(self.phase_t, 2.0):
            self.phase_t = now
            what = "afraid with " + plural(len(adj), "monster") + " adjacent" if pinned else \
                f"{len(crowd)} about in the open"
            self.cmd(f"custom {tele[0]} item={tele[1]['item']}", f"{why}: teleport ({what})", hold=0.6)
            self.notify("emergency", f"{why}: {what}: {one_of(tele[1]['name'])}")
            return True
        if adj and pd and can_read and (waited(self.phase_t, 2.5) or (collapsing and waited(self.phase_t, 0.7))):
            self.phase_t = now
            self.phase_hist.append(now)
            self.cmd(f"custom r item={pd['item']}", f"{why}: phase door", hold=0.6)
            self.notify("emergency", f"{why}: read Phase Door ({', '.join(sorted({r.name for *_, r in adj}))} adjacent)")
            return True
        if not adj:
            # Out of melee: make for stairs if some are close, else heal
            stairs = [p for p in w.find("<>") if w.dist(p) <= 20]
            # (a new move sends 'clear', which would drop a read or quaff still
            # waiting in the server's queue for our next turn)
            used_recently = not waited(max(self.phase_t, self.cure_t, self.recall_t), 2.0)
            if stairs and not self.mover.active and not used_recently:
                if self.mover.go(stairs):
                    self.escaping_to_stairs = True
                    self.notify("emergency", f"{why}: heading for the stairs {min(w.dist(p) for p in stairs)} away")
            if self.mover.active and self.escaping_to_stairs:
                st = self.mover.tick()
                if st == "arrived" and w.standing_on in ("<", ">"):
                    self.take_stairs(w.standing_on)
                return True
        if waited(self.cure_t, 1.5):
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
                                             f"({pots[-1][0]}): escaping instead", action=False)
                if adj and pd and can_read and waited(self.phase_t, 0.7):
                    self.phase_t = now
                    self.phase_hist.append(now)
                    self.emerg_times.append(now)     # (this phase sends no notice of its own)
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
            # Two or more beside us: an HP cure (a flat 15-29 HP, use-obj.c) is outpaced -- read an escape instead;
            # blind or confused, cure that first so the next turn can read (the Advisor's estimator memo)
            if pick and len(adj) >= 2:
                if not can_read:
                    st = "blind" if w.flag("blind") else "confused"
                    cure = next((i for c in STATUS_CURES[st] for i in w.items(tval=TV_POTION) if c in i["name"]
                                 and not (c == "Healing" and "*Healing*" in i["name"])), None)
                    if cure:
                        self.cure_t = now
                        self.cmd(f"custom q item={cure['item']}", f"{why}: {st} with {len(adj)} adjacent: quaff "
                                                                   f"{cure['name']} to read an escape next", hold=0.6)
                        self.notify("emergency", f"{why}: {st} with {len(adj)} adjacent: quaffed {one_of(cure['name'])} "
                                                 "so the next turn can read")
                        return True
                else:
                    esc = tele if tele and len(crowd) >= 4 else (("r", pd) if pd else tele)
                    if esc and waited(self.phase_t, 0.7):
                        self.phase_t = now
                        if "Phase" in esc[1]["name"]:
                            self.phase_hist.append(now)
                        self.cmd(f"custom {esc[0]} item={esc[1]['item']}", f"{why}: {len(adj)} adjacent: "
                                                                            f"{esc[1]['name']} rather than a cure", hold=0.6)
                        self.notify("emergency", f"{why}: {len(adj)} adjacent, a cure would be outpaced: read "
                                                 f"{one_of(esc[1]['name'])}")
                        return True
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
                                                   if left else "nothing left to escape with, fighting on"), action=False)
        return False

    def watch_perception(self):
        """Log when the server's monster list names something our map decode
        doesn't show (mission 4: a Yellow mold hit us while the pilot saw
        nothing). Once per level and name, with the map around us."""
        w = self.w
        if not w.monlist or not w.rows or not w.pos:
            return
        seen = {r.name for *_, r in w.monsters}
        now = gnow()
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
                     map_age=round(gnow() - w.map_t, 2), crop=crop,
                     monsters=[(my, mx, r.name) for my, mx, r in w.monsters])

    def room_door(self, Y, X):
        """An inner room's door, if the map shows one at any of its 4 places."""
        return next((d for d, _ in structures.door_spots(Y, X) if self.w.memory.get(d) in ("+", "'")), None)

    def watch_band(self):
        """A band gathering: 5+ mobile monsters within 10 squares that aren't
        trivial, or their worst-case melee together over half our HP. Warn once
        per level (again if it grows by half): leave while it's cheap (mission 22
        fetched loot in Orfax's room while an orc band assembled; HP 78/241, all
        10 Phase Door and 5 CCW later)."""
        w = self.w
        if not w.in_dungeon:
            return
        # (not trivial: 6+ worst-case melee a turn; by level it missed an orc band
        # of Hill, Cave and Snaga orcs, all well below clvl 21)
        near = [(y, x, r) for y, x, r in w.monsters if "NEVER_MOVE" not in r.flags and w.dist((y, x)) <= 10
                and (r.worst_melee[0] or 0) * (r.speed_x or 1) >= 6]
        worst = sum((r.worst_melee[0] or 0) * (r.speed_x or 1) for *_, r in near)
        if len(near) < 5 and worst < 0.4 * max(w.hp[1], 1):
            return
        # serious only when together they could take 30% of current HP in a turn, or one of them
        # is dangerous (the user, m24: 5-8 Novice rogues or Snaga at clvl 22 / 265 HP made the trip
        # leave four levels and a Word of Recall on the floor); weaker ones are fought, and looted
        # (since m34: by the expected cost of fighting them one by one, not the sum of every member's maximum hit:
        # m30's Novice warriors x6 + Swordsman and m34's Hill orcs counted as bands at 30% that way. 50% of HP
        # expected, or a dangerous member)
        cost = self.band_cost([r for *_, r in near])
        serious = cost > float(self.orders.get("band_frac", 0.5)) * max(w.hp[0], 1) or \
            any(self.danger_why(r) for *_, r in near)
        if not serious:
            if getattr(self, "weak_band_said", None) != w.level_t:
                self.weak_band_said = w.level_t
                self.notify("tactic", f"{len(near)} monsters together but weak (~{cost:.0f} HP expected to fight them "
                                      f"all, vs HP {w.hp[0]}): fighting on", news=True)
            return
        lt, size = self.band_warned
        if lt == w.level_t and len(near) < size * 1.5:
            return
        self.band_warned = (w.level_t, len(near))
        self.band_warned_t = gnow()
        names = ", ".join(f"{n} ×{c}" if c > 1 else n
                          for n, c in collections.Counter(r.name for *_, r in near).most_common(6))
        stairs = min((w.dist(q) for q in w.find("<>")), default=None)
        self.notify("band", f"a band within 10 squares: {names} ({len(near)} monsters, ~{cost:.0f} HP expected to fight "
                            f"them all, HP {w.hp[0]}): leave now while it's cheap -- "
                            + (f"stairs {stairs} away" if stairs is not None else "no stairs known: read Word of Recall")
                            + "; don't stop for loot")

    def teleport_item(self):
        """('r', a Scroll of Teleportation) or ('u', a Staff of Teleportation with charges), or None. Blind, confused
        or just refused a read: the staff first (a scroll can't be read blind, cmd6.c:275 -- m48: 13 Light hounds
        re-blinded Dive04 within a second of each cure, and two escape reads failed; the staff works blind)."""
        w = self.w
        sc = next((i for i in w.items(tval=TV_SCROLL) if "Teleportation" in i["name"]), None)
        st = next((i for i in w.items(tval=55) if "Teleportation" in i["name"] and
                   not re.search(r"\(0 charges\)", i["name"])), None)
        unreadable = w.flag("blind") or w.flag("confused") or gnow() - self.__dict__.get("read_failed_t", -99.0) < 10
        if st and (unreadable or not sc):
            return ("u", st)
        if sc and not unreadable:
            return ("r", sc)
        return ("u", st) if st else None

    STATUS_SPELLS = ("BLIND", "CONF", "HOLD", "SLOW", "SCARE", "FORGET", "DRAIN_MANA", "TELE_TO", "TELE_LEVEL")

    def kill_caster_step(self, adj, why):
        """Attack an adjacent summoner or status caster (blind, confuse, hold, slow, scare...) that our blows kill in
        two rounds (rulebook hp vs the wielded weapon's damage). True if the attack was sent."""
        w = self.w
        if not adj or not waited(getattr(self, "caster_t", -99.0), 0.6):
            return False
        rows = self.fight_rows()
        wt = [x for x in self.weapon_table() if x[3]]
        dmg = wt[0][2] if wt else 0
        if not dmg:
            return False
        best = None
        for y, x, r in adj:
            if not (r.summoner or any(s in self.STATUS_SPELLS for s in r.spells)):
                continue
            hp = float((rows.get(getattr(r, "idx", None)) or {}).get("hp") or 0)
            if hp and hp <= 2 * dmg and (best is None or hp < best[0]):
                best = (hp, y, x, r)
        if not best:
            return False
        _, y, x, r = best
        self.caster_t = gnow()
        self.cmd(f"walk {direction(w.pos, (y, x))}", f"{why}: attack {r.name} first (a caster, dies in 2 rounds)",
                 hold=0.4)
        if not getattr(self, "caster_said", None) == (w.level_t, r.name):
            self.caster_said = (w.level_t, r.name)
            self.notify("emergency", f"{why}: attacking {r.name} first (summons or casts blind/confuse/hold; ~{best[0]:.0f} "
                                     f"HP, two rounds)", action=False)
        return True

    def shadow_decision(self, detail, options=None, trigger="emergency", rules=None, extra_p=None):
        """Shadow mode (the user, 10-25): hand this decision's state to the Advisor's estimator in the background
        (shadow.py): an emergency (all options), or the start of a hard fight (hard_fight_shadow: its own options).
        Never waits, never acts on it. Returns 'started', 'skipped' (one running) or 'off'."""
        sh = self.__dict__.get("shadow_est")
        if sh is None:
            sh = self.shadow_est = shadow.Shadow()
            if sh.error:
                self.log("note", text=f"shadow mode off: the estimator didn't load ({sh.error})")
        if not sh.sim:
            return "off"
        w = self.w
        wt = [x for x in self.weapon_table() if x[3]]
        prof = shadow.weapon_profile(wt[0][0] if wt else "", wt[0][1] if wt else 1)
        # (A3: the estimator's tohit/todam are totals -- the weapon's plus rings, gloves and other gear and the STR/DEX
        # bonuses, the Advisor's docs memo 10-28 §4 -- from the gear evaluator's model, as geareval.sim_player passes)
        try:
            d = self.gear_character().derive()
            prof.update(tohit=d["tohit"], todam=d["todam"])
            # (A14, the Advisor's memo 2026-10-29-s10-reply: slays, brands and the weapon's weight, as sim_player)
            prof.update({k: dict(d[k]) for k in ("slays", "brands") if d.get(k)})
            if d.get("wweight"):
                prof["weight"] = d["wweight"]
        except Exception as e:                     # (the weapon's own numbers then; said once in the log)
            if not self.__dict__.get("shadow_gear_said"):
                self.shadow_gear_said = True
                self.log("note", text=f"shadow mode: the gear model failed, the weapon's own (+h,+d) passed ({e!r})")

        def n(word, tv):
            return sum(i["number"] for i in w.items(tval=tv) if word in i["name"])
        staff = next((i for i in w.items(tval=55) if "Teleportation" in i["name"]), None)
        m = re.search(r"\((\d+) charges?\)", staff["name"]) if staff else None
        stairs = min((sh.sim.adist(q[0] - w.pos[0], q[1] - w.pos[1]) for q in w.find("<>")), default=None) \
            if w.pos else None
        p = dict(hp=w.hp[0], mhp=w.hp[1], ac=(w.ind.get("armor") or [0])[0] or 0, clvl=w.clvl,
                 depth=w.depth or 1, stairs=stairs, free_action=bool(self.has_ability("free_action")),
                 # (the sheet's resists, as the simulator's flags: options_sim 26f models them; m47's Dark hounds'
                 # darkness breath was simulated at full damage on a Half-Orc)
                 **{geareval.SIM_RES[f]: True for f in
                    ({geareval.SHEET_FLAG.get(k.upper(), k.upper()) for k, on in (w.flags or {}).items() if on}
                     & set(geareval.SIM_RES))},
                 save=sh.sim.SAVE, max_adj=2 if self.mover.in_corridor() else shadow.MAX_ADJ, **prof,
                 inv=dict(ccw=n("Cure Critical", TV_POTION), csw=n("Cure Serious", TV_POTION),
                          clw=n("Cure Light", TV_POTION), phase=n("Phase Door", TV_SCROLL),
                          tele=n("Teleportation", TV_SCROLL), staff=int(m.group(1)) if m else 0,
                          wor=n("Word of Recall", TV_SCROLL), speed=n("Speed", TV_POTION),
                          berserk=n("Berserk", TV_POTION), hero=n("Heroism", TV_POTION)))
        for k, on in (("fast", self.buff_on("fast")), ("hero", self.buff_on("hero")), ("berserk", self.buff_on("shero")),
                      ("blind", w.flag("blind")), ("confused", w.flag("confused")), ("afraid", w.flag("afraid")),
                      ("slow", self.our_slowness() > 1)):
            if on:
                p[k] = 5
        if w.recall_pending:
            p["recall"] = max(1, int(25 - (gnow() - w.recall_pending_t) / shadow.TURN_S))
        # (the asleep flags the `look` answers give: the share awake among the looked-at monsters not adjacent, for
        # the simulator's p_awake -- its 0.4 stood in for this; the Advisor's top data gap)
        looked = [self.is_asleep(y, x) for y, x, _ in w.monsters if w.pos and w.dist((y, x)) > 1]
        looked = [z for z in looked if z is not None]
        if looked:
            p["p_awake"] = round(sum(1 for z in looked if not z) / len(looked), 2)
            p["asleep_seen"] = sum(1 for z in looked if z)
        # (the food counter for options_sim's gorging: the client gives the hunger level only, so the level's range,
        # drawn per rollout -- options_sim 26j's FOOD_LEVEL; gorging is a threshold, the Advisor: a midpoint hid the risk)
        lvl = {0: "Weak", 1: "Weak", 2: "Hungry", 3: "Fed", 4: "Full", 5: "Gorged"}.get(w.hunger, "Fed")
        fl = getattr(sh.sim, "FOOD_LEVEL", None)
        p["food"] = fl[lvl] if fl and lvl in fl else {"Weak": 750, "Hungry": 1500, "Fed": 6000, "Full": 12500,
                                                      "Gorged": 15000}[lvl]
        # (options_sim 28l, the Advisor's MIN_GAIN memo 10-28: the XP-override floor is max(50, 30 s of play) at this
        # rate; unlike xp_per_block it charges no time cost, so it goes in every snapshot, emergencies too)
        dr = (self.rate_state().get("depth") or {}).get(str(w.depth_ft))
        p["xp_rate_per_block"] = round(dr[0] / (dr[1] / 60) / 96, 3) if dr and dr[1] > 300 else 0
        p.update(extra_p or {})
        # (name, distance, hp_frac, awake): options_sim 26h takes the asleep flag per member (the `look` answers; None =
        # unknown, the p_awake share then 0.4 stand in) -- the Advisor: 7 Wargs, six at 4 squares, ~11 HP lost if
        # known asleep, ~55 awake, ~23 unknown
        team = [(r.name, max(1, sh.sim.adist(y - w.pos[0], x - w.pos[1])), None,
                 None if self.is_asleep(y, x) is None else not self.is_asleep(y, x))
                for y, x, r in w.monsters] if w.pos else []
        # (and what the server's list names but the map doesn't show yet, 3 squares off: A2K's first emergency had
        # Khim in the list only, and the estimator played an empty fight)
        team += [(r.name, 3) for r in (w.listed_only() if hasattr(w, "listed_only") else [])]
        snap = {"p": p, "team": team, "rules": rules or shadow.rules_option(detail), "rules_detail": (detail or "")[:160],
                "wall": time.time(), "factor": time_factor(), "speed": (w.ind.get("speed") or [0])[0] or 0,
                "options": list(options) if options else None, "trigger": trigger, "xp_per_gold": self.xp_per_gold()}
        return sh.submit(snap)

    def shadow_results(self):
        """Log the estimator's answers (the main thread writes the log): with whether it would have arrived in time --
        within one player turn at the time factor of the decision, and before the Pilot's next action."""
        sh = self.__dict__.get("shadow_est")
        if not sh:
            return
        while not sh.results.empty():
            r = sh.results.get()
            snap = r.get("snap") or {}
            sp = snap.get("speed", 0)
            energy = 1.0 + max(-0.5, min(1.0, sp / 10.0))          # (roughly: +10 doubles our turns)
            turn_s = shadow.TURN_S / max(0.05, snap.get("factor") or 1.0) / energy
            nxt = next((t for t in self.__dict__.get("act_walls", ()) if t > snap.get("wall", 0) + 0.05), None)
            in_turn = r.get("compute_s", 99) <= turn_s
            before_next = nxt is None or r.get("done_wall", 0) <= nxt
            # (no monster the estimator knows: nothing to compare -- agree is None). The estimator's "rules" row is
            # its copy of the Pilot's rules, which can act differently from the Pilot (m47: its copy fought the Wargs
            # where the Pilot read Word of Recall, the table's worst row at -102 XP, and "agree" was logged). So
            # when the Pilot's actual action has its own row, "rules" agrees only if that row is safe and within noise
            # of the best (2 SE, at least 10 XP).
            agree, actual_row = shadow_agree(r.get("choice"), snap.get("rules"), r.get("table"))
            if not r.get("team"):
                agree = None
            self.log("estimator", trigger=snap.get("trigger", "emergency"), options=snap.get("options"),
                     xp_per_gold=snap.get("xp_per_gold"),
                     rules=snap.get("rules"), rules_detail=snap.get("rules_detail"),
                     choice=r.get("choice"), why=r.get("why"), agree=agree, actual_row=actual_row,
                     compute_s=r.get("compute_s"), turn_s=round(turn_s, 2), in_time_turn=in_turn,
                     before_next_act=before_next, next_act_after_s=round(nxt - snap["wall"], 2) if nxt else None,
                     team=r.get("team"), p=r.get("p"), inv=r.get("inv"), table=r.get("table"), error=r.get("error"),
                     policy_version=getattr(sh.sim, "POLICY_VERSION", None), max_adj=(r.get("p") or {}).get("max_adj"),
                     arrivals=[])

    def recall_memory(self):
        """A pending Word of Recall survives a Pilot restart in the game but not in our memory (the client only says
        "becomes charged" once): kept in runs/pilot/NICK/recall.json, restored at start when the depth still matches.
        The hot-swap set-piece H1r: the new Pilot's plan read a second scroll, which cancelled the pending one."""
        w = self.w
        path = os.path.join(self.rundir, "recall.json")
        if not getattr(self, "recall_restored", False):
            if w.depth is None:
                return
            self.recall_restored = True
            try:
                st = json.load(open(path))
            except (OSError, ValueError):
                st = None
            if st and st.get("pending") and st.get("depth") == w.depth and time.time() - st.get("t", 0) < 600 and \
                    not w.recall_pending:
                w.recall_pending, w.recall_pending_t = True, gnow()
                self.notify("tactic", "a Word of Recall read before the restart is still pending: not reading another",
                            news=True)
        now_st = (w.recall_pending, w.depth)
        if now_st != getattr(self, "recall_saved", None):
            self.recall_saved = now_st
            try:
                json.dump({"pending": w.recall_pending, "depth": w.depth, "t": time.time()}, open(path, "w"))
            except OSError:
                pass

    def band_cost(self, races):
        """Expected HP lost fighting these monsters one at a time, the quickest kills first: while each dies, those
        still alive hit for their expected melee at our AC (rulebook melee_exp_acNN a monster turn, x their speed),
        at most 8 at once in a room, 2 in a corridor. Our damage: the wielded weapon's per round."""
        rows = self.fight_rows()
        ac = (self.w.ind.get("armor") or [0])[0] or 0
        col = min((20, 40, 60), key=lambda a: abs(a - ac))
        wt = [x for x in self.weapon_table() if x[3]]
        dmg = max(1.0, wt[0][2] if wt else 10.0)
        cap = 2 if self.mover.in_corridor() else 8

        def stats(r):
            row = rows.get(getattr(r, "idx", None)) or {}
            hp = float(row.get("hp") or 0) or 10.0
            hit = float(row.get(f"melee_exp_ac{col}") or 0) * (r.speed_x or 1) if row else \
                0.5 * (r.worst_melee[0] or 0) * (r.speed_x or 1)
            return hp, hit
        alive = sorted((stats(r) for r in races), key=lambda s: s[0])
        total = 0.0
        while alive:
            t = max(1.0, alive[0][0] / dmg)
            total += t * sum(sorted((h for _, h in alive), reverse=True)[:cap])
            alive.pop(0)
        return total * self.our_slowness()

    def band_live(self):
        """A band warned on this level in the last 20 s, or 3+ of its kind of monsters still within 10."""
        w = self.w
        if self.band_warned[0] != w.level_t:
            return False
        if gnow() - self.band_warned_t < 20:
            return True
        return sum(1 for y, x, r in w.monsters if "NEVER_MOVE" not in r.flags and w.dist((y, x)) <= 10) >= 3

    def watch_traps(self):
        """Three traps sprung on one level: say so (mission 22: dart traps
        drained STR and CON on one level while explore walked on)."""
        w = self.w
        if not w.in_dungeon:
            return
        for ts, t in w.messages:
            if ts > self.trap_seen_t and re.match(r"(You found a trap|You fall into|A small dart|You are enveloped|"
                                                  r"You are impaled|A pit|You fall through)", t):
                n = self.traps_here[1] + 1 if self.traps_here[0] == w.level_t else 1
                self.traps_here = (w.level_t, n)
                if n == 3:
                    self.notify("tactic", "3 traps sprung on this level: it's trap-laden; leave it (stairs or a "
                                          "fresh level) rather than explore on", news=True)
                if t.startswith("You fall through"):
                    self.trapdoor = (ts, w.depth_ft)
        self.trap_seen_t = max([self.trap_seen_t] + [ts for ts, _ in w.messages])
        # (m50: a trap door dropped us to 850 ft, below max_depth 800; the climb back took ~4.5 minutes and only the
        # depth column showed it. Say so, and log it for the mission's record)
        td = self.__dict__.get("trapdoor")
        if td and w.level_t > td[0]:
            self.trapdoor = None
            md = int(self.orders.get("max_depth", 0))
            self.log("trapdoor", from_ft=td[1], to_ft=w.depth_ft, max_depth=md)
            if md and w.depth_ft > md:
                self.notify("tactic", f"a trap door dropped us from {td[1]} to {w.depth_ft} ft, below max_depth {md}: "
                                      "climbing back (deeper monsters until then)", news=True)

    def watch_thieves(self):
        """A thief in view in the dungeon: say so once per level, before it
        touches (mission 21: a Brigand stole an {excellent} armour and the
        Navigator only heard of it from the loss)."""
        w = self.w
        if not w.in_dungeon:
            return
        for y, x, r in w.monsters:
            kinds = {b.split(":")[1] for b in r.blows if b.split(":")[1:2] in (["EAT_ITEM"], ["EAT_GOLD"])}
            if not kinds or (w.level_t, r.name) in self.thieves_seen:
                continue
            self.thieves_seen.add((w.level_t, r.name))
            what = "items from your pack" if "EAT_ITEM" in kinds else "gold"
            self.notify("thief", f"{r.name} (lvl {r.level}, {w.dist((y, x))} away) steals {what} with a touch, then "
                                 f"teleports: kill it before it reaches you (`goal hunt {r.name.replace(' ', '_')}`), "
                                 "or keep away", news="EAT_ITEM" not in kinds)

    def watch_kills(self):
        """A unique slain: say so (its drop is worth picking up). Mission 21:
        Wormtongue died during explore and nobody noticed until his hammer."""
        w = self.w
        if not self.unique_names:
            self.unique_names = {r.name.lower() for r in w.g.races.values() if "UNIQUE" in r.flags}
        for ts, t in w.messages:
            if ts <= self.kills_t:
                continue
            m = re.match(r"You have (?:slain|destroyed) (.+?)\.$", t)
            if m and m.group(1).lower() in self.unique_names:
                self.unique_drop = (w.level_t, w.pos, ts)     # its drop is always picked up
                uk = self.uniques_killed()
                if m.group(1).lower() not in uk:
                    uk.add(m.group(1).lower())
                    try:
                        json.dump(sorted(uk), open(os.path.join(self.rundir, "uniques_killed.json"), "w"), indent=1)
                    except OSError:
                        pass
                self.notify("unique_slain", f"{m.group(1)} slain at {w.pos[0]},{w.pos[1]}: uniques drop good items "
                                            "(look at 'Item squares' around there)")
        self.kills_t = max([self.kills_t] + [ts for ts, _ in w.messages])

    # --- the belief state (restructure step 2.5) ---------------------------------
    def belief_tick(self, now):
        w = self.w
        for y, x, r in w.monsters:
            m = self.mons_mem.get(r.name)
            if not m or m["level"] != w.level_t or now - m["t"] > 1:
                n = sum(1 for *_, q in w.monsters if q.name == r.name)
                self.mons_mem[r.name] = {"level": w.level_t, "pos": (y, x), "n": n, "t": now,
                                         "danger": bool(self.danger_why(r)), "unique": "UNIQUE" in r.flags}
            else:
                m["t"] = now
                if w.dist((y, x)) < w.dist(m["pos"]):
                    m["pos"] = (y, x)
        for ts, t in w.messages:
            if ts <= self.belief_msg_t:
                continue
            m = re.match(r"You (?:hit|smite|bite|claw|bash) (?:the )?(.+?)[.!]$", t)
            if m:
                self.hits[(w.level_t, m.group(1).lower())] += 1
            # gold from sales, for the rolling XP-per-gold rate (rate_tick)
            m = re.match(r"You sold .+? for (\d+) gold", t)
            if m:
                self.gold_sold = self.__dict__.get("gold_sold", 0) + int(m.group(1))
            # (m37: the cloak and the new helm lost +1 each to a Disenchanter mold; nothing in the news)
            m = re.match(r"Your (.+?) \(.\) (?:was|were) disenchanted!", t)
            if m:
                self.notify("disenchanted", f"{m.group(1)} lost a plus (disenchanted)", news=True)
            # (m51, m53: Novice rogues took 2617 and 2392 gold, ~10% of the purse a touch, and nothing said so; the
            # session-8 Architect called both losses "unexplained")
            m = re.match(r"(\d+) coins were stolen!", t) or re.match(r"Your (.+?) \(.\) (?:was|were) stolen!", t)
            if m:
                gold = m.group(1).isdigit()
                if gold:
                    self.gold_stolen = self.__dict__.get("gold_stolen", 0) + int(m.group(1))
                self.notify("thief", f"{m.group(1) + ' gold' if gold else m.group(1)} stolen by a touch"
                                     + (f" ({self.gold_stolen} stolen since the Pilot started)" if gold else ""),
                            news=True)
            m = re.match(r"You have (?:slain|destroyed|killed) (?:the )?(.+?)[.!]$", t)
            if m:
                k = m.group(1).lower()
                self.hits.pop((w.level_t, k), None)
                mm = next((v for n, v in self.mons_mem.items() if n.lower() == k), None)
                if mm:
                    mm["n"] -= 1
                    if mm["n"] <= 0:
                        self.mons_mem = {n: v for n, v in self.mons_mem.items() if v is not mm}
        self.belief_msg_t = max([self.belief_msg_t] + [ts for ts, _ in w.messages])
        self.track_gains(now)

    def track_gains(self, now):
        # gold found: rises in the dungeon only (the Rates line counted purchases and sales; the scorecard's
        # gold_found, the same way)
        w = self.w
        g = w.ind.get("gold", [0])[0]
        if w.in_dungeon and g > self.__dict__.get("gold_last", g):
            self.gold_found = self.__dict__.get("gold_found", 0) + g - self.gold_last
        self.gold_last = g
        xp = (w.ind.get("exp") or [0])[0]
        dxp = max(0, xp - self.__dict__.get("xp_last", xp))
        if dxp:
            self.xp_gained = self.__dict__.get("xp_gained", 0) + dxp
        self.xp_last = xp
        # XP and minutes by depth (for `prep`: where the XP has been), kept with the rates
        last = self.__dict__.get("depth_t")
        if w.in_dungeon and w.depth_ft:
            if last is not None and now - last < 5:
                d = self.rate_state().setdefault("depth", {}).setdefault(str(w.depth_ft), [0, 0])
                d[0] += dxp
                d[1] = round(d[1] + now - last, 1)
            self.depth_t = now
        else:
            self.depth_t = None
        self.rate_tick(now)
        # XP since arriving on this level (the Navigators' "stay or leave": m31-m34 asked for a per-level rate)
        lb = self.__dict__.get("level_base")
        if w.in_dungeon and (not lb or lb[2] != w.level_t):
            self.level_base = (now, (w.ind.get("exp") or [0])[0], w.level_t)
        if not self.gain_hist or now - self.gain_hist[-1][0] >= 15:
            self.gain_hist.append((now, (w.ind.get("exp") or [0])[0], g, self.__dict__.get("gold_found", 0)))
            self.save_mission()
            self.food_watch()

    def food_watch(self):
        """News once per trip when the pack holds no food in the dungeon (m46's Navigator found "Food 0" with no
        warning; the cause, make-room destroying rations, is fixed, but eating the last one isn't)."""
        w = self.w
        if not w.in_dungeon or not hasattr(self, "c"):
            return
        n = self.kit_count("Ration of Food")
        key = getattr(self.plan, "t0", None) or w.level_t
        if n == 0 and self.__dict__.get("food_warned") != key:
            self.food_warned = key
            self.notify("supply", f"no food left in the pack (hunger: {('Weak', 'Weak', 'Hungry', 'Fed', 'Full')[min(4, max(0, w.hunger))]}): "
                                  "`plan town` buys rations; a Full character lasts ~20 dungeon minutes", news=True)

    def save_mission(self):
        """The running mission (label, its start and the totals so far) in mission.json: a restart or hot-swap
        carries it on (m44/m45: the swap lost the label, so `mission end` needed it by name)."""
        mb = getattr(self, "mission_base", None)
        if not (mb and getattr(self, "mission_label", None)):
            return
        try:
            json.dump({"label": self.mission_label, "age": round(gnow() - mb[0], 1), "exp": mb[1], "gold": mb[2],
                       "found": self.__dict__.get("gold_found", 0) - (mb[3] if len(mb) > 3 else 0)},
                      open(os.path.join(self.rundir, "mission.json"), "w"))
        except OSError:
            pass

    def load_mission(self):
        try:
            path = os.path.join(self.rundir, "mission.json")
            if time.time() - os.path.getmtime(path) > 1800:
                return          # (a mission nobody ended, long ago)
            ms = json.load(open(path))
            # (gold_found starts at 0 in a new process: the base goes negative by what was found before)
            self.mission_label = ms["label"]
            self.mission_base = (gnow() - ms["age"], ms["exp"], ms["gold"],
                                 self.__dict__.get("gold_found", 0) - ms["found"])
        except (OSError, ValueError, KeyError, TypeError):
            pass

    # the rolling exchange rate between XP and gold (the user, 10-25: "the real limiting factor is time"): XP earned per
    # gold earned (found + sold) over the recent play, in 10-minute buckets, the last RATE_WINDOW with any gain; seeded
    # with the shadow series m35-m42 (14190 XP, 12900 found, 21794 sold over 319 min: 0.41), which fades out as real
    # buckets fill the window. Used by the estimator (shadow mode) and shown by `gear`.
    RATE_BUCKET_S = 600
    RATE_WINDOW = 30
    RATE_SEED = (14190, 12900 + 21794)
    RATE_CLAMP = (0.1, 3.0)

    def rate_state(self):
        st = self.__dict__.get("rates")
        if st is None:
            try:
                st = json.load(open(os.path.join(self.rundir, "rates.json")))
            except (OSError, ValueError, AttributeError):
                st = {}
            st.setdefault("buckets", [])
            self.rates = st
        return st

    def rate_tick(self, now):
        cur = (self.__dict__.get("xp_gained", 0), self.__dict__.get("gold_found", 0) + self.__dict__.get("gold_sold", 0))
        op = self.__dict__.get("rate_open")
        if op is None or now - op[0] >= self.RATE_BUCKET_S:
            if op is not None:
                d = [c - b for c, b in zip(cur, op[1])]
                if any(d):
                    st = self.rate_state()
                    st["buckets"] = (st["buckets"] + [[round(time.time()), d[0], d[1]]])[-self.RATE_WINDOW:]
                    try:
                        json.dump(st, open(os.path.join(self.rundir, "rates.json"), "w"))
                    except (OSError, AttributeError):
                        pass
            self.rate_open = (now, cur)

    def xp_per_gold(self):
        """XP per gold from recent play: the buckets, plus the seed weighted by the window's unfilled share."""
        b = self.rate_state()["buckets"]
        seed_w = max(0.0, 1 - len(b) / self.RATE_WINDOW)
        xp = sum(x[1] for x in b) + seed_w * self.RATE_SEED[0]
        gold = sum(x[2] for x in b) + seed_w * self.RATE_SEED[1]
        lo, hi = self.RATE_CLAMP
        return round(min(hi, max(lo, xp / gold)), 3) if gold > 0 else 1.0

    def belief_lines(self):
        """The report's belief-state lines: threats out of view, the fight so far, rates,
        counts on this level, standing instructions."""
        w, now = self.w, gnow()
        out = []
        if w.in_dungeon:
            in_view = {r.name for *_, r in w.monsters}
            gone = sorted(((n, m) for n, m in self.mons_mem.items() if m["level"] == w.level_t and n not in in_view
                           and now - m["t"] < 120), key=lambda nm: (not nm[1]["unique"], not nm[1]["danger"],
                                                                   now - nm[1]["t"]))
            if gone:
                out.append("Out of view (this level, last 2 min): " + "; ".join(
                    f"{n}{' ×%d' % m['n'] if m['n'] > 1 else ''}"
                    + (" (UNIQUE)" if m["unique"] else "") + (" (DANGER)" if m["danger"] else "")
                    + f" {now - m['t']:.0f} s ago at {m['pos'][0]},{m['pos'][1]} ({w.dist(m['pos'])} away)"
                    for n, m in gone[:5]))
            wt = [x for x in self.weapon_table() if x[3]]
            per_hit = wt[0][2] / max(1, wt[0][1]) if wt else 0
            rows = self.fight_rows()
            fights = []
            for name in sorted(in_view):
                k = self.hits.get((w.level_t, name.lower()), 0)
                if not k:
                    continue
                race = next((r for *_, r in w.monsters if r.name == name), None)
                row = rows.get(getattr(race, "idx", None)) or {}
                hp = row.get("hp")
                fights.append(f"{name}: {plural(k, 'hit')}, ~{k * per_hit:.0f} dealt" + (f" of ~{hp} HP" if hp else ""))
            tr = w.ind.get("track") or [0, 0]
            if fights:
                out.append("Fight so far: " + "; ".join(fights) +
                           (f" (the tracked monster's health bar: {10 * tr[1]}%)" if len(tr) > 1 and tr[1] else ""))
        # rates: HP lost recently, XP and gold per 10 minutes
        hh = [(t, hp) for t, hp in getattr(w, "hp_hist", []) if now - t <= 10]
        bits = []
        if hh and hh[0][1] - w.hp[0] > 0.05 * max(1, w.hp[1]):
            bits.append(f"HP -{hh[0][1] - w.hp[0]} in the last {now - hh[0][0]:.0f} s")
        found = self.__dict__.get("gold_found", 0)
        old = next((h for h in self.gain_hist if now - h[0] <= 600), None)
        if old and now - old[0] > 60:
            de = (w.ind.get("exp") or [0])[0] - old[1]
            dg = w.ind.get("gold", [0])[0] - old[2]
            bits.append(f"XP {de:+d}, gold found {found - old[3]:+d} (net {dg:+d}, with shopping) in the last "
                        f"{(now - old[0]) / 60:.0f} min")
        lb = self.__dict__.get("level_base")
        if w.in_dungeon and lb and lb[2] == w.level_t and now - lb[0] >= 60:
            de = (w.ind.get("exp") or [0])[0] - lb[1]
            bits.append(f"this level: XP {de:+d} in {(now - lb[0]) / 60:.0f} min ({de / ((now - lb[0]) / 60):.0f} a minute)")
        pl = self.plan
        if pl and getattr(pl, "xp0", None) is not None and now - pl.t0 >= 60:
            de = (w.ind.get("exp") or [0])[0] - pl.xp0
            bits.append(f"this trip: XP {de:+d} in {(now - pl.t0) / 60:.0f} min ({de / ((now - pl.t0) / 60):.0f} a minute)")
        mb = getattr(self, "mission_base", None)
        if mb and getattr(self, "mission_label", None):
            bits.append(f"this mission: XP {(w.ind.get('exp') or [0])[0] - mb[1]:+d}, gold found "
                        f"{found - (mb[3] if len(mb) > 3 else 0):+d} (net {w.ind.get('gold', [0])[0] - mb[2]:+d}) "
                        f"in {(now - mb[0]) / 60:.0f} min")
        if bits:
            out.append("Rates: " + "; ".join(bits))
        if w.in_dungeon:
            cnt = []
            if self.drains_here[0] == w.level_t and self.drains_here[1]:
                cnt.append(plural(self.drains_here[1], "drain"))
            if self.traps_here[0] == w.level_t and self.traps_here[1]:
                cnt.append(plural(self.traps_here[1], "trap") + " sprung")
            ns = sum(1 for lt, _ in self.searched if lt == w.level_t)
            if ns:
                cnt.append(f"{plural(ns, 'spot')} searched")
            ph = sum(1 for t in self.phase_hist if now - t < 90)
            em = sum(1 for t in self.emerg_times if now - t < 90)
            recent = ([plural(em, "emergency")] if em else []) + ([plural(ph, "Phase Door")] if ph else [])
            if cnt or recent:
                out.append("Counts: " + (f"this level {', '.join(cnt)}" if cnt else "") +
                           ("; " if cnt and recent else "") + (f"last 90 s {', '.join(recent)}" if recent else ""))
        st = [f"keep {', '.join(sorted(self.keep))}"] if self.keep else []
        if self.avoid_names:
            st.append(f"avoid {', '.join(sorted(self.avoid_names))}")
        if self.avoid_zones.get(w.level_t):
            st.append(f"{plural(len(self.avoid_zones[w.level_t]), 'avoid zone')} here")
        st += [f"\"{x['text']}\" ({x['by']})" for x in self.standing]
        st += [f"react {x['kind']} {x['arg']}" for x in self.rules()]
        nop = str(self.orders.get("nopickup", "")).strip()
        if nop:
            st.append(f"never pick up {nop}")
        if st:
            out.append("Standing: " + "; ".join(st))
        rv = self.review_state()["items"]
        if rv:
            # (m55: the Navigator missed that undecided items are sold after 2 town visits -- the Boots of Stability)
            tv = self.review_state()["town_visits"]

            def left(v):
                k = 2 - (tv - v["visit"])
                return "SOLD at this town visit if undecided" if k <= 0 else \
                    "sold at the next town visit if undecided" if k == 1 else \
                    "sold at the second town visit from now if undecided"
            out.append(f"Review ({len(rv)}, `review sell|keep|wear NAME`): " + "; ".join(
                f"{n} ({v['why']}; {left(v)})" for n, v in rv.items()))
        return out

    def numbered(self, rep, kind):
        """Number each report the Navigator gets and log it (id, kind, size), so
        every later command can say which report it answered and how old that
        was (the Advisor's starting-over memo: orders went stale on the way)."""
        self.report_seq += 1
        self.last_report = (self.report_seq, gnow())
        # what the report showed, for the stale-order check (step 2.4)
        self.report_state = {"level_t": self.w.level_t, "hp": self.w.hp_frac}
        self.log("report", id=self.report_seq, report_kind=kind, chars=len(rep))
        first, _, rest = rep.partition("\n")
        return f"{first} · r{self.report_seq}" + ("\n" + rest if rest else "")

    def drainers_info(self, args):
        """`drainers [STAT] [MAXLEVEL]`: monsters whose blows drain a stat, by
        native level (the Navigator's mission 19 wish: the ant and the frog
        drained STR unflagged). Default: STR/DEX/CON, up to clvl + 10."""
        stats = {a.upper() for a in args if a.upper() in self.STAT_NAMES}
        lv = next((int(a) for a in args if a.isdigit()), self.w.clvl + 10)
        want = stats or {"STR", "DEX", "CON"}
        rows = sorted((r.level, r.name, sorted(r.drained_stats & want), "NEVER_MOVE" in r.flags, r.speed)
                      for r in self.w.g.races.values() if r.drained_stats & want and r.level <= lv)
        if not rows:
            return f"no monster up to level {lv} drains {', '.join(sorted(want))}"
        return f"monsters up to level {lv} ({lv * 50} ft) that drain {', '.join(sorted(want))}:\n" + "\n".join(
            f"  lvl {l:2d} ({l * 50} ft) {n}: {', '.join(st)}" + (" (stationary)" if still else "") +
            (f" (speed +{sp - 110})" if sp > 110 else "") for l, n, st, still, sp in rows)

    def watch_drainers(self):
        """A mobile monster in view whose blows drain a stat: say so once per
        level (mission 19: a Giant red ant and frog, rated 1/5, took STR 18/40
        -> 18/10 and a blow; nothing had flagged them)."""
        w = self.w
        if not w.in_dungeon:
            return
        mine = 110 + int(w.ind.get("speed", [0])[0] or 0)
        for _, _, r in w.monsters:
            stats = r.drained_stats
            if not stats or "NEVER_MOVE" in r.flags or (w.level_t, r.name) in self.drainers_seen:
                continue
            self.drainers_seen.add((w.level_t, r.name))
            key = stats & {"STR", "DEX", "CON"}          # blows and HP: what a warrior can't spare
            weak = r.level <= w.clvl - 5 and r.speed <= mine and "UNIQUE" not in r.flags
            if weak:
                advice = "weak and no faster than you: kill it fast, don't walk away from it"
            else:
                advice = f"`avoid {r.name.replace(' ', '_')}`, or leave the level"
            # (a weak one is news, not a reason for the trip plan to leave the level: m33 left 650 ft for a Giant red
            # frog, m34's Navigator thought the same of others; it's fought when it comes)
            self.notify("drainer", f"{r.name} (lvl {r.level}) drains {', '.join(sorted(stats))} with its blows: "
                                   f"{advice}", news=not key or weak)

    def watch_progress(self):
        """A goal that goes nowhere: at most 10 different squares in 2 minutes
        while not fighting (mission 3 circled a '>' for 10 minutes, and no
        event woke the Navigator). Clear the server queue, restart the move,
        and say so."""
        w, now = self.w, gnow()
        if w.pos:
            self.pos_hist.append((now, w.pos, w.depth))
        while self.pos_hist and now - self.pos_hist[0][0] > 120:
            self.pos_hist.popleft()
        idle_goal = isinstance(self.goal, (Wait, RestGoal, Search, Recall, Recover, Shop)) or self.goal is None
        # Quick check: the mover is "moving" but we've stood on one square for
        # 20 s (mission 19: a flee resent a refused run for a minute, no alert)
        # (picking a lock or digging is progress: mission 20 fired this at a door)
        working = any(now - ts < 3 and t.startswith(("You failed to pick", "You have picked", "You tunnel",
                                                      "You dig", "You have removed", "You failed to make",
                                                      "This seems to be permanent", "The door "))
                      for ts, t in w.messages)
        # (acting in place is progress too: m57 12:20, plan town reading 7 Identify scrolls at the Alchemist for 20 s)
        la = self.__dict__.get("last_action")
        working = working or bool(la and now - la[0] < 4 and not str(la[1]).startswith(("walk", "pathfind", "run")))
        if not idle_goal and self.mover.active and not w.adjacent_monsters() and not w.resting and not working and \
                now - self.stuck_t > 60 and now - getattr(self, "goal_t", 0) > 20:
            recent = [q for t, q, d in self.pos_hist if now - t <= 20]
            if len(recent) >= 15 and len(set(recent)) == 1 and now - self.pos_hist[0][0] >= 20:
                self.stuck_t = now
                self.c.send("clear")
                self.mover.stop()
                self.notify("stuck", f"'{self.goal.describe()}' hasn't moved from {w.pos} for 20 s: cleared the "
                                     "command queue and restarted the move. If it happens again, give another goal")
                return
        if now - getattr(self, "goal_t", 0) < 110:
            return      # (the demo mission: 'stuck' 3 s into a goal, counting the idle time before it)
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
        # the second time for the same goal, end it: restarting the move can't fix a goal whose own logic loops
        # (m30: a dive at 600 ft went nowhere for 6 minutes, restarted twice; the trip plan then moves on)
        if getattr(self.goal, "stuck_once", False):
            self.goal.abort = f"went nowhere for 4 minutes (around {w.pos})"
            self.notify("stuck", f"'{self.goal.describe()}' has gone nowhere for 4 minutes (around {w.pos}): "
                                 "ending it", news=bool(self.plan))
            return
        self.goal.stuck_once = True
        self.notify("stuck", f"'{self.goal.describe()}' has gone nowhere for 2 minutes "
                             f"(around {w.pos}): cleared the command queue and restarted the move. "
                             "If it happens again, the goal ends")

    ABILITY_FLAGS = {"free_action": "free_act", "resist_blind": "res_blind", "resist_conf": "res_conf",
                     "see_invisible": "see_invis", "resist_nexus": "res_nexus", "hold_life": "hold_life",
                     "feather_fall": "feather"}

    def has_ability(self, order):
        """Free Action, a resist...: from the character sheet's grid (tool
        query 'flags') once read, else from the order of the same name."""
        if order in self.inferred:
            return True           # seen in play ("You are unaffected!"), not on the sheet
        known = self.w.has(self.ABILITY_FLAGS.get(order, order)) if hasattr(self.w, "has") else None
        if known is not None:
            return known
        return self.orders.get(order) == "yes"

    # --- the value policy and the Navigator's debt (restructure step 2.1) -------
    def value_refusal(self, it, action, role=None):
        """Why the Navigator shouldn't sell/destroy/drop this item, or None. The
        Pilot's own policy never does these; the Navigator may override with `!`,
        and the value lost is added to its debt (the user's decision)."""
        if (role or getattr(self, "req_role", "navigator")) in ("architect", "pilot") or not it:
            return None
        name = it["name"]
        if self.is_kept(name):
            return "you said keep it (`keep -NAME` releases it)"
        if self.ability_sources and self.iv(name).known is False and \
                any(s == re.sub(r"^(an?|\d+) ", "", re.sub(r"\s*\{[^}]*\}", "", name)).lower() for s in self.ability_sources):
            return (f"it may be what gives you {', '.join(sorted(self.inferred))} (seen in play, not identified): "
                    "identify it first")
        junk = (self.flavour_of(it) or {}).get("junk") or re.search(r"\{(cursed|worthless|broken|terrible)", name)
        if junk:
            return None
        iv = self.iv(name)
        fair = round(iv.value * self.pay_cut(iv.tval))
        if not iv.known and iv.p_irreplaceable >= 0.2:
            return (f"unidentified, and {iv.p_irreplaceable:.0%} of these carry an ego you can't buy back (Free "
                    "Action, resists...): identify it first")
        if not iv.known and fair >= 30:
            return (f"unidentified: identified it would sell for ~{fair} (an estimate; this sale would pay its bare "
                    "kind price); identify it first (a Scroll of Identify costs ~40-80)")
        if action in ("destroy", "drop") and iv.irreplaceable:
            return "it gives an ability or resist you can't easily buy back"
        if action in ("destroy", "drop") and fair >= 20:
            return f"a shop pays ~{fair} for it: sell it instead"
        return None

    def pay_cut(self, tval=None):
        """What a shop pays of an item's value (restructure step 3: shopmath and the owners, not one
        38% for everything): the best of the shops that buy this kind of item, by the owner we
        last saw there, else the average owner of that shop, at the current CHR. SHOP_CUT when
        nothing is known."""
        chr_v = (self.w.ind.get("stat5") or [3])[0] if self.w.ind else 3
        stores = self.BUYERS.get(tval, ()) if tval is not None else (1, 2, 3, 4, 5, 6)
        key = (tval, chr_v, tuple(sorted((k, (v or {}).get("owner")) for k, v in getattr(self, "stores_seen", {}).items())))
        cache = self.__dict__.setdefault("_pay_cache", {})
        if key in cache:
            return cache[key]
        best = None
        for st in stores:
            owner = (getattr(self, "stores_seen", {}).get(st) or {}).get("owner")
            f = shopmath.factors(re.sub(r"\s*\(.*\)$", "", owner), chr_v) if owner else None
            if f:
                cut = f[0] / 100         # (the shop's buying adjust: its pay, % of value)
            else:
                fs = [shopmath.factors(o, chr_v) for o, (idx, _r, _g) in shopmath.OWNERS.items() if idx == st - 1]
                fs = [x for x in fs if x]
                cut = sum(x[0] for x in fs) / len(fs) / 100 if fs else None
            if cut is not None and (best is None or cut > best):
                best = cut
        cache[key] = best if best is not None else SHOP_CUT
        return cache[key]

    def iv(self, name):
        """itemvalue.value with the depth items now come from (for expectations) and
        the kinds already known (the flavour table)."""
        level = max(1, (self.w.depth_ft or getattr(self, "deepest_ft", 0) or 750) // 50)
        if self.aware_cache[0] != len(self.flavours):
            self.aware_cache = (len(self.flavours), {re.sub(r"^(Potion|Scroll|Ring|Amulet|Wand|Staff|Rod) of ", "",
                                                            f.get("kind", "")).lower() for f in self.flavours.values()})
        return itemvalue.value(name, level, self.aware_cache[1])

    def is_kept(self, name):
        b = re.sub(r"^(an?|\d+) ", "", re.sub(r"\s*\{[^}]*\}", "", name)).lower()
        # (singular too: "staff of teleportation" on the keep list missed "2 Staffs of Teleportation")
        return any(k in b or k in singular(b) for k in self.keep)

    def debt_total(self):
        return sum(e.get("gold", 0) for e in self.debt.get("entries", []))

    def add_debt(self, gold, what, why):
        if gold <= 0:
            return
        self.debt.setdefault("entries", []).append({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "gold": int(gold),
                                                    "what": what, "why": why})
        json.dump(self.debt, open(self.debt_path, "w"), indent=1)
        self.log("navigator_debt", gold=int(gold), what=what, why=why, total=self.debt_total())

    def override_allowed(self, kind="item"):
        """Overrides stay allowed until the user or the Architect revokes them. The
        limit is a judgement, not a number (the user: hidden, so we keep leeway
        and the Navigator can't tell how close it is): revoked = the file
        runs/private/NICK.overrides_revoked exists (its text says why); for hunts,
        NICK.hunt_overrides_revoked."""
        path = os.path.join(os.path.dirname(os.path.dirname(self.rundir.rstrip("/"))), "private",
                            os.path.basename(self.rundir.rstrip("/")) +
                            (".hunt_overrides_revoked" if kind == "hunt" else ".overrides_revoked"))
        return not os.path.exists(path)

    def fight_debt_total(self):
        return sum(e.get("hp", 0) for e in self.debt.get("fight_entries", []))

    def settle_hunt(self, g, status, detail):
        """Judge a hunt the Navigator ordered over the Pilot's refusal (the user, 2026-10-23:
        it may override, and if it was wrong the cost goes into a fight debt kept apart
        from the item debt). Wrong = not slain, or HP fell below half, or an emergency
        escape fired during it. The debt is the HP it cost (start to lowest)."""
        ov, w = g.overridden, self.w
        g.overridden = None
        lost = max(0, ov["hp0"] - ov["hp_min"])
        emerg = len(self.emerg_times) - ov["emerg0"]
        slain = status == "done" and "slain" in str(detail) or "killed" in str(detail)
        wrong = not slain or ov["hp_min"] < 0.5 * max(1, w.hp[1]) or emerg > 0
        self.log("hunt_override_end", target=g.target, status=status, detail=detail, hp_lost=lost,
                 hp_min=ov["hp_min"], emergencies=emerg, wrong=wrong)
        if not wrong or not lost:
            self.notify("tactic", f"your override hunt of {g.target}: {detail or status}, {lost} HP lost; the "
                                  "Pilot's refusal was too cautious this time (no debt)", news=True)
            return
        self.debt.setdefault("fight_entries", []).append(
            {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "hp": int(lost), "what": f"hunt {g.target}",
             "why": f"{detail or status}; lowest HP {ov['hp_min']}" + (f", {emerg} emergencies" if emerg else "") +
                    f" (refused because: {ov['why'][:120]})"})
        json.dump(self.debt, open(self.debt_path, "w"), indent=1)
        self.log("navigator_fight_debt", hp=int(lost), what=g.target, total=self.fight_debt_total())
        self.notify("tactic", f"your override hunt of {g.target} went wrong ({detail or status}, {lost} HP lost"
                              f"{', an emergency escape' if emerg else ''}): {lost} added to your fight debt", news=True)

    KIT_KINDS = ("Cure Light Wounds", "Cure Serious Wounds", "Cure Critical Wounds", "Healing", "Phase Door",
                 "Word of Recall", "Teleport", "Identify", "Magic Mapping", "Speed", "Heroism", "Berserk",
                 "Restore", "Deep Descent", "Resist Poison")    # (not Boldness: Heroism does all it does, the user)
    # what a kit consumable found in the dungeon is worth to us: what replacing it costs (the Alchemist's price
    # last seen, else these; Speed, Healing and Berserk only at the Black Market). m36 left a Potion of Speed,
    # "pack full and nothing cheaper (~34)", with no Speed in the pack and junk weapons in it
    KIT_USE = {"Speed": 600, "Healing": 1500, "Berserk": 500, "Teleport": 150, "Heroism": 60, "Magic Mapping": 65,
               "Deep Descent": 100, "Resist Poison": 100, "Restore": 480}

    def is_kit_item(self, it):
        """A kit consumable: a potion or scroll of a kit kind. (Not a staff or wand with the same words: m43 kept two
        Staffs of Cure Light Wounds as if they were the potions -- the user: "2 staffs of cure light wounds?")"""
        return it["tval"] in (TV_POTION, TV_SCROLL) and any(k in it["name"] for k in self.KIT_KINDS)

    def kit_use_value(self, name):
        """Replacement cost of a kit consumable (potion or scroll), else 0."""
        kind = next((k for k in self.KIT_KINDS if k in name), None)
        if not kind or not re.search(r"\b(Potions?|Scrolls?) of\b", name):
            return 0
        m = re.match(r"(\d+) ", name)
        n = int(m.group(1)) if m else 1
        full = next((k for k in self.KIT_ITEMS if k in name), None)
        price = (self.price_of(full, self.KIT_ITEMS[full][1]) if full else None) or self.KIT_USE.get(kind, 0)
        return price * n

    def pack_value(self, it):
        """An item's worth to the pack, for making room: kit consumables, kept items,
        possible ability sources and the light count as priceless."""
        n = it["name"]
        # A spare light beyond the first, and food beyond 5 meals (Satisfy Hunger counts), are worth what they
        # sell for: m25 kept 2 spare lanterns and a ration while it destroyed a Rod of Trap Location and a
        # Staff of Object Location to make room
        if it["tval"] == TV_LITE:
            spares = sorted((i for i in self.w.items() if i["tval"] == TV_LITE), key=lambda i: -self.iv(i["name"]).value)
            if spares and spares[0]["item"] != it["item"]:
                return self.iv(n).value * self.pay_cut(TV_LITE)
        # One food source, rations (eaten blind or confused; a Scroll of Satisfy Hunger fills to just under
        # Gorged): other food, flasks beyond what the lantern needs, and near a trip's end the spare rations
        # and flasks are worth what they sell for (the user, 10-25: food, oil and potions fill the pack)
        if it["tval"] == TV_FOOD and "Mushroom" not in n and ("Ration" not in n or self.provisions_spare()):
            # (never the last meal: m46 destroyed all 3 rations near a trip's end for a ~30-gold rod, and the Navigator
            # found "Food 0" -- a ration stack goes down to one, the last food item is priceless)
            if self.destroy_count(it) == 0:
                return float("inf")
            return self.iv(n).value * self.pay_cut(TV_FOOD) * self.destroy_count(it)
        if it["tval"] == TV_FLASK and ((self.lantern_fuel() or 0) >= self.FUEL_TOPUP or self.provisions_spare()):
            return self.iv(n).value * self.pay_cut(TV_FLASK) * it["number"]
        if it["tval"] in (TV_FOOD, TV_FLASK, TV_LITE) or self.is_kit_item(it) or self.is_kept(n) or \
                re.sub(r"^(an?|\d+) ", "", re.sub(r"\s*\{[^}]*\}", "", n)).lower() in self.ability_sources:
            return float("inf")
        if (self.flavour_of(it) or {}).get("junk") or re.search(r"\{(cursed|worthless|broken|terrible)", n):
            return 0
        if n in self.review_state()["items"]:
            return float("inf")            # (waiting for the Navigator's review)
        iv = self.iv(n)
        return iv.value * self.pay_cut(iv.tval) * max(1, iv.count)

    UNIQUE_DROP_BUMP = 50

    def destroy_count(self, it):
        """How many of this pack item a make-room may destroy: all, except food -- rations never (one slot, cheap; the
        town visit sells extras), other food not the last of it."""
        if it["tval"] == TV_FOOD and "Ration" in it["name"]:
            return 0          # (rations: never -- m47 cut 3 to 1 for a Staff of CLW and the Navigator bought food)
        if it["tval"] == TV_FOOD and "Mushroom" not in it["name"]:
            others = sum(i["number"] for i in self.w.items() if i["tval"] == TV_FOOD and "Mushroom" not in i["name"]
                         and i["item"] != it["item"])
            return it["number"] if others else it["number"] - 1
        return it["number"]

    def weight_room(self):
        """Tenth-pounds the pack can still take before the weight limit slows us (xtra1.c:2772: over half of
        adj_str_wgt x 100), and the current speed lost to weight."""
        w = self.w
        t = geareval.stat_table()
        limit = t[geareval.stat_index((w.ind.get("stat0") or [18])[0])]["adj_str_wgt"] * 100
        load = sum(i["weight"] for i in w.items() + w.items(equip=True))
        slow = (load - limit // 2) // (limit // 10) if load > limit // 2 else 0
        return limit // 2 - load, slow

    # the top of each hunger level (the client sends only the level: Weak, Hungry, Fed, Full) and the food in each
    # kind we may eat (object.txt pvals; mushrooms 500)
    FOOD_TOP = {0: 1000, 1: 1000, 2: 2000, 3: 10000, 4: PY_FOOD_MAX}
    FOOD_VALUES = (("Ration", 5000), ("Biscuit", 500), ("Jerky", 1500), ("Slime Mold", 3000), ("Waybread", 7500),
                   ("Ale", 500), ("Wine", 1000), ("Potato", 1500), ("Cabbage", 1500), ("Carrot", 500), ("Beet", 750),
                   ("Squash", 2000), ("Corn", 1500))

    @classmethod
    def food_value(cls, name):
        return next((v for k, v in cls.FOOD_VALUES if k in name), 500)

    HEAVY_LOOT_MIN = 300      # gold: below this, loot that would slow us is left
    def is_junk_name(self, name):
        """Known junk by name: the junk order (Salt Water, Weakness...), spellbooks for a warrior, Broken items, and
        flavours the flavour table marks junk though the character doesn't know them (mission 21: an unknown Summon
        Undead took the slot freed for an {excellent} armour)."""
        n = name.lower().rstrip(".")
        junk = [j.strip().lower() for j in self.orders.get("junk", "").split(",") if j.strip()]
        if self.w.ind.get("class_") == "Warrior":
            junk += ["book of magic spells", "holy book of prayers"]   # can't read them
        feel = [f.strip() for f in self.orders.get("autodestroy", "").split(",") if f.strip()]
        return any(f"of {j}" in n or n.endswith(j) or (j.startswith(("book", "holy book")) and j in n) for j in junk) \
            or " broken " in f" {n} " or any("{" + f in n for f in feel) \
            or bool((self.flavours.get(flavour_key(name)) or {}).get("junk"))

    def quiet_moment(self, now):
        """Not in combat (the user, 10-25: floor junk is destroyed only then): no awake mobile monster in view, not
        hit in the last 5 s, HP at least think_hp, not blind or confused, and not fleeing, recalling or recovering."""
        w = self.w
        mobile = [m for m in w.monsters if "NEVER_MOVE" not in m[2].flags]
        return not mobile and now - getattr(w, "last_hit_t", 0) > 5 and w.hp_frac >= self.orders.get("think_hp", 0.65) \
            and not isinstance(self.goal, (Flee, Recall, Recover)) and not w.recall_pending and not w.flag("blind") \
            and not w.flag("confused")

    def destroy_floor_junk(self, name, now):
        """Destroy the junk underfoot (k with the floor index -11, as the client sends it: any negative item is the floor, cmd3.c do_cmd_destroy) at a quiet moment.
        One try per square (the caller marks it skipped); True if sent."""
        if not self.quiet_moment(now) or now < self.busy_until:
            return False
        m = re.match(r"(\d+) ", name)
        n = int(m.group(1)) if m else 1
        self.c.send("confirm yes")
        self.cmd(f"custom k item=-11 value={n}", f"destroy junk on the floor: {name}", hold=0.6)   # (FLOOR_INDEX, as the client)
        return True

    def pickup_room(self, name):
        """True if the item underfoot should be picked up now (destroying something
        cheaper first when the pack is full); False to leave it (with news)."""
        w, now = self.w, gnow()
        # (the Navigator's never-pick-up list, `order nopickup=Lance,Pike`: dungeon pack control, the user 10-26)
        nop = [x.strip().lower() for x in str(self.orders.get("nopickup", "")).split(",") if x.strip()]
        if any(x in name.lower() for x in nop):
            self.skipped_items.add((w.level_t, w.pos))
            return False
        iv = self.iv(name)
        worth = max(iv.value * self.pay_cut(iv.tval) * max(1, iv.count), self.kit_use_value(name))
        ud = self.unique_drop
        unique = bool(ud and ud[0] == w.level_t and w.dist(ud[1]) <= 3)
        if not unique and iv.known and worth < 1 and not iv.irreplaceable:
            if (w.level_t, w.pos) not in self.skipped_items:
                self.skipped_items.add((w.level_t, w.pos))
            return False                         # worthless: leave it
        # (too heavy: m46 carried six weapons for sale and went speed -1. Loot that would take us past the weight limit's
        # slow-down line is left unless it's worth HEAVY_LOOT_MIN or can't be replaced)
        wt = geareval.Item(name).weight * max(1, iv.count) if iv.tval in geareval.SLOT_OF_TVAL else \
            50 * max(1, iv.count) if iv.tval == 55 else 0          # (staffs: 5 lb each, m47's pack sat on the line)
        if wt and not unique and not iv.irreplaceable and worth < self.HEAVY_LOOT_MIN:
            room, _ = self.weight_room()
            # (m50: Bullroarer's Dagger, Cutlass, Gnomish Shovel and Lucerne Hammer sat at the weight limit and a
            # Staff of Trap Location was left. As for a full pack: shed the cheapest thing heavy enough, if this is
            # worth 1.5x it)
            shed = sorted(((self.pack_value(i), i) for i in w.items() if self.destroy_count(i) > 0
                           and i["weight"] * self.destroy_count(i) // max(1, i["number"]) >= wt - room),
                          key=lambda vi: vi[0]) if wt > room else []
            if shed and worth > 1.5 * shed[0][0] + 5:
                if now - self.room_t > 1.5:
                    v, it = shed[0]
                    self.room_t = now
                    self.c.send("confirm yes")
                    self.cmd(f"custom k item={it['item']} value={self.destroy_count(it)}",
                             f"make weight room: destroy {it['name']} (~{v:.0f}) for {name} (~{worth:.0f})", hold=0.6)
                    self.notify("tactic", f"at the weight limit: destroyed {it['name']} (~{v:.0f} gold) to take {name} "
                                          f"(~{worth:.0f})", news=True)
                return False                     # (picked up on the next look, once there's room)
            if wt > room:
                self.skipped_items.add((w.level_t, w.pos))
                # (once per item and level: m47 said "left a Battle Axe" 9 times walking past it)
                said = self.__dict__.setdefault("left_news", set())
                if (w.level_t, name) not in said:
                    said.add((w.level_t, name))
                    self.notify("tactic", f"left {name} (~{worth:.0f}): {wt / 10:.0f} lb would slow you (the weight "
                                          f"limit; {max(0, room) / 10:.0f} lb to spare)", news=True)
                return False
        free = 23 - len(w.items())
        if free >= 1:
            return True
        # one that stacks with what we carry needs no slot (m25 left a Potion of Heroism 7 times, "pack full",
        # with 6 in the pack)
        key = self.kind_key_of(name)
        if any(self.kind_key_of(i["name"]) == key for i in w.items()):
            return True
        # Use something up before destroying anything (the user, mission 21: a robe and
        # a scroll were destroyed with a flask of oil in the pack that could have
        # filled the lantern): a lone flask into the lantern, a lone ration eaten
        if now - self.room_t > 1.5:
            lamp = next((i for i in w.items(equip=True) if i["tval"] == TV_LITE and "Lantern" in i["name"]), None)
            lt = re.search(r"with (\d+) turns", lamp["name"]) if lamp else None
            flask = next((i for i in w.items() if i["tval"] == TV_FLASK and i["number"] == 1), None)
            food = next((i for i in w.items() if i["tval"] == TV_FOOD and i["number"] == 1
                         and "Mushroom" not in i["name"]), None)
            if flask and lt and int(lt.group(1)) < 14000:
                self.room_t = now
                self.cmd(f"custom F item={flask['item']}", f"make room: fuel the lantern with the last flask for {name}",
                         hold=0.6)
                return False
            # (m49: a Piece of Elvish Waybread, 7500 food, eaten for room while Fed beside Wargs and a Black ogre: Gorged,
            # -10 speed. Eaten only if the top of our hunger level plus the food stays a potion margin under Gorged)
            if food and self.FOOD_TOP.get(w.hunger, PY_FOOD_MAX) + self.food_value(food["name"]) < PY_FOOD_MAX - 1000:
                self.room_t = now
                self.cmd(f"custom E item={food['item']}", f"make room: eat {food['name']} for {name}", hold=0.6)
                return False
        cand = sorted(((self.pack_value(i), i) for i in w.items()), key=lambda vi: vi[0])
        cand = [(v, i) for v, i in cand if self.destroy_count(i) > 0]
        cheapest = cand[0] if cand else None
        # (a unique's drop is "good" but unknown: it may push out only cheap things. m37 destroyed a Tulwar (~76)
        # for Boldor's 4-gold Dagger, and an Amulet of Infravision (~86) for boots it then destroyed for a Katana)
        if cheapest and cheapest[0] < float("inf") and ((unique and cheapest[0] < self.UNIQUE_DROP_BUMP)
                                                         or worth > 1.5 * cheapest[0] + 5):
            if now - self.room_t > 1.5:
                self.room_t = now
                self.c.send("confirm yes")
                self.cmd(f"custom k item={cheapest[1]['item']} value={self.destroy_count(cheapest[1])}",
                         f"make room: destroy {cheapest[1]['name']} (~{cheapest[0]:.0f}) for {name} (~{worth:.0f})",
                         hold=0.6)
                self.notify("tactic", f"pack full: destroyed {cheapest[1]['name']} (~{cheapest[0]:.0f} gold) to take "
                                      f"{name} (~{worth:.0f}{', a unique drop' if unique else ''})", news=True)
            return False                         # (picked up on the next look, once there's room)
        if (w.level_t, w.pos) not in self.skipped_items:
            self.skipped_items.add((w.level_t, w.pos))
            # (once per item and level: m25 said "left a Rapier" 5 times and "left a Potion of Heroism" 7)
            if not hasattr(self, "left_news"):
                self.left_news = set()
            if (w.level_t, name) not in self.left_news:
                self.left_news.add((w.level_t, name))
                self.notify("tactic", f"left {name} (~{worth:.0f}): pack full and nothing cheaper to make room with",
                            news=True)
        return False

    ARMOUR_SLOTS = {30: "boots", 31: "gloves", 32: "helm", 33: "helm", 34: "shield", 35: "cloak", 36: "body",
                    37: "body", 38: "body"}

    def policy_tick(self, now):
        """The Pilot's own item work at safe moments (restructure step 2.1): identify
        what's worth it, wield a better weapon, wear better armour and good
        jewellery in empty slots. True if it acted."""
        w = self.w
        if now - self.policy_t < 3 or now < self.busy_until or w.store or self.pending_use or w.monsters or \
                now - w.last_hit_t < 8 or w.hp_frac < 0.5 or isinstance(self.goal, (Flee, Recall, Recover, Shop, TownKit)) or \
                w.flag("blind") or w.flag("confused"):
            return False
        self.policy_t = now
        # 0. a drained STR/DEX/CON with its Restore in the pack: drink it now, the fight over (never mid-fight: m42's
        # Navigator quaffed one next to the Giant red ant and was drained again, ~480 gold lost) -- the reason a
        # spare Restore is carried at all (the user, m43: "why bring the restore potions?")
        if w.in_dungeon and self.quiet_moment(now):
            pot = self.restore_potion()
            if pot and any(f"Restore {v}" in pot["name"] for v in self.STAT_FULL.values()):   # (not CHR: town does it)
                self.cmd(f"custom q item={pot['item']}", f"restore a drained stat now the fight is over: quaff "
                                                         f"{pot['name']}", hold=0.8)
                self.notify("tactic", f"quaffed {one_of(pot['name'])}: the drain is undone, the fight over", news=True)
                return True
        # 0a. a unique's drop: the items within 3 squares of where it died (the set-piece C3: Mughash's drop
        # was left -- looting runs only inside explore and dive, and a hunt ends idle)
        ud = getattr(self, "unique_drop", None)
        if self.goal is None and not self.mover.active and ud and ud[0] == w.level_t and now - ud[2] < 300 and w.pos:
            fetched = self.__dict__.setdefault("drop_fetched", set())
            drops = [q for q in self.resolve_target("item") if max(abs(q[0] - ud[1][0]), abs(q[1] - ud[1][1])) <= 3
                     and (w.level_t, q) not in fetched and w.memory.get(q, ".") not in "0123456789"]
            if drops:
                q = min(drops, key=w.dist)
                fetched.add((w.level_t, q))   # (one visit per square; not skipped_items, which the pickup reads as junk)
                g = Goto(f"{q[0]},{q[1]}")
                g.quiet = True
                self.set_goal(g)
                self.notify("tactic", f"fetching the unique's drop at {q[0]},{q[1]}", news=True)
                return True
        # 0. gold lying within 10 squares while idle (the user, mission 23: the Pilot
        # left the gold beside it in town; the Navigator needed seven gotos)
        if self.goal is None and not self.mover.active and w.pos:
            gold = [q for q, ch in w.memory.items() if ch == "$" and 0 < w.dist(q) <= 10
                    and (w.level_t, q) not in self.skipped_items]
            if gold and self.mover.go([min(gold, key=w.dist)]):
                g = Goto(f"{min(gold, key=w.dist)[0]},{min(gold, key=w.dist)[1]}")
                g.quiet = True
                self.set_goal(g)
                self.notify("tactic", f"picking up the gold {min(w.dist(q) for q in gold)} squares away", news=True)
                return True

        return self.identify_step(now) or self.upgrade_step()

    def identify_step(self, now, minimum=20):
        """Read Identify (or use Perception) on the most valuable unknown worth at
        least `minimum` gold sold (ability sources first). True if it acted."""
        pack = self.w.items()
        # 1. identify the most valuable unknown (ability sources and likely egos first)
        scroll = next((i for i in pack if i["tval"] == TV_SCROLL and "Identify" in i["name"]), None)
        staff = next((i for i in pack if i["tval"] == 55 and "Perception" in i["name"]
                      and not re.search(r"\(0 charges\)", i["name"])), None)
        if scroll or staff:
            # (three tries per item: at night in town a read without a light failed
            # twenty times in a row, "You have no light to read by")
            tries = self.__dict__.setdefault("id_tries", {})
            cands = [(pr, it) for pr, it in self.identify_candidates(minimum) if tries.get(it["name"], 0) < 3]
            if cands:
                _, it = max(cands, key=lambda pc: pc[0])
                tool = scroll or staff
                if tool is scroll and not any(i["tval"] == TV_LITE for i in self.w.items(equip=True)):
                    return self.wear_light("a light to read Identify by") and "light"
                tries[it["name"]] = tries.get(it["name"], 0) + 1
                if self.unknown_flavour(it):
                    self.id_target = {"t": now, "flavour": flavour_key(it["name"]),
                                      "letter": None if it["equip"] else chr(97 + it["item"])}
                self.cmd(f"custom {'r' if tool is scroll else 'u'} item={tool['item']} dir={it['item']}",
                         f"identify {it['name']} (policy)", hold=1.0)
                self.notify("tactic", f"identifying {it['name']} (the most valuable unknown)", news=True)
                return True
        return False

    def upgrade_step(self):
        """Wield a better weapon, wear better armour, put good jewellery into
        empty slots: one change per call. True if it acted. `order autowear=off` pauses it (an item kept off on
        purpose; the M5 set-piece stages a low AC)."""
        if str(self.orders.get("autowear", "on")) == "off":
            return False
        w = self.w
        pack, worn = w.items(), w.items(equip=True)

        def bare(n):
            return re.sub(r"^(an?|\d+) ", "", re.sub(r"\s*\{[^}]*\}", "", n)).lower()

        def cursedish(n):
            return re.search(r"\{(cursed|worthless|broken|terrible)", n)
        # 2. a better weapon (plain damage; a brand counts half, as not every monster is affected)
        wt = self.weapon_table()
        if wt:
            def eff(n, b, d):
                br = weapon_brand(n)
                return d + 0.5 * (weapon_damage(n, b, br[1]) - d) if br else d
            cur = max((eff(n, b, d) for n, b, d, eq in wt if eq), default=0)
            # (never for a weapon that loses an ability the wielded one gives: m33 swapped a Scimitar of Westernesse,
            # Free Action and See Invisible, for a Main Gauche doing ~40 vs ~28, and again 2 s after the Navigator
            # put it back. Artifacts are never swapped away: their abilities aren't in the ego table)
            on = next((n for n, b, d, eq in wt if eq), None)
            keep_ab = self.weapon_abilities(on) if on else set()
            best = max(((eff(n, b, d), n) for n, b, d, eq in wt if not eq and not cursedish(n)
                        and keep_ab <= self.weapon_abilities(n)), default=None)
            if on and self.is_artifact(on):
                best = None
            if best and best[0] > cur * 1.2 and best[0] > 0:
                it = next((i for i in pack if i["name"] == best[1]), None)
                if it:
                    self.cmd(f"custom w item={it['item']}", f"wield {it['name']} (~{best[0]:.0f}/round vs ~{cur:.0f})",
                             hold=0.8)
                    self.notify("tactic", f"wielded {it['name']}: ~{best[0]:.0f} a round vs ~{cur:.0f}", news=True)
                    return True
        # 3. better armour, slot by slot (by AC; known not cursed; plusses or a feeling known)
        for it in pack:
            slot = self.ARMOUR_SLOTS.get(it["tval"])
            if not slot or cursedish(it["name"]):
                continue
            if not (re.search(r"\[\d+,[+-]\d+\]", it["name"]) or re.search(r"\{(average|good|excellent)", it["name"])):
                continue                  # (no feeling yet: it might be cursed)
            on = [i for i in worn if self.ARMOUR_SLOTS.get(i["tval"]) == slot]
            ac_new = self.armour_ac(it["name"]) or 0
            ac_on = min((self.armour_ac(i["name"]) or 0) for i in on) if on else -1
            # (never for armour that loses an ability or resist the worn piece gives -- the ego table, as for weapons --
            # nor over a worn artifact: by AC alone a plain mail would have replaced the Hard Studded Leather of
            # Resistance and its four resists)
            if on and (self.is_artifact(on[0]["name"]) or
                       not self.weapon_abilities(on[0]["name"]) <= self.weapon_abilities(it["name"])):
                continue
            if ac_new > ac_on and not (on and bare(on[0]["name"]) in self.ability_sources):
                self.cmd(f"custom w item={it['item']}", f"wear {it['name']} (AC {ac_new} vs {ac_on})", hold=0.8)
                self.notify("tactic", f"wore {it['name']} (AC {ac_new} vs {max(ac_on, 0)})", news=True)
                return True
        # 4. good jewellery into an empty ring or amulet slot (identified only)
        swap = self.__dict__.get("jewel_swap")
        for tv, k in ((45, 2), (40, 1)):
            if sum(1 for i in worn if i["tval"] == tv) >= k:
                continue
            cand = [i for i in pack if i["tval"] == tv and self.iv(i["name"]).known and
                    self.iv(i["name"]).value > 0 and not (self.flavour_of(i) or {}).get("junk")]
            if cand:
                it = next((i for i in cand if i["name"] == swap), None) or \
                    max(cand, key=lambda i: self.iv(i["name"]).value)
                self.jewel_swap = None
                self.cmd(f"custom w item={it['item']}", f"put on {it['name']} (an empty slot)", hold=0.8)
                self.notify("tactic", f"put on {it['name']} (the slot was empty)", news=True)
                return True
        # 5. in town: better jewellery over a worn piece (m36 sold a Ring of Protection [+9] while wearing the [+8]):
        # the same kind with a bigger bonus, or anything that adds an ability or AC over a piece whose abilities
        # another worn piece already gives. Off first; step 4 then puts the new one on.
        if not w.depth and not w.in_dungeon:
            have = {f for f, sl in (w.flags or {}).items() if sl}
            spare = [r[0] for r in self.redundant_worn()]

            def bonus(n):
                m = re.search(r"\[\+(\d+)\]", n)
                return int(m.group(1)) if m else 0

            def kind(n):
                return re.sub(r"\s*\[[^]]*\]|\s*\{[^}]*\}|^(an?|\d+) ", "", n)
            for it in pack:
                if it["tval"] not in (40, 45) or not self.iv(it["name"]).known or cursedish(it["name"]) or \
                        (self.flavour_of(it) or {}).get("junk"):
                    continue
                # (a redundant piece goes first: swapping the [+8] would lose 8 AC that the free slot keeps)
                for on in sorted((i for i in worn if i["tval"] == it["tval"]), key=lambda i: i not in spare):
                    same = kind(on["name"]) == kind(it["name"]) and bonus(it["name"]) > bonus(on["name"])
                    adds = on in spare and (self.jewel_gives(it["name"]) - have or bonus(it["name"]))
                    if (same or adds) and not self.is_artifact(on["name"]):
                        self.jewel_swap = it["name"]
                        self.cmd(f"custom t item={on['item']}", f"take off {on['name']} for {it['name']}", hold=0.8)
                        self.notify("tactic", f"took off {on['name']} to wear {it['name']} ("
                                              + ("a bigger bonus" if same else "its abilities are given by other gear")
                                              + ")", news=True)
                        return True
        # 6. in town: the gear evaluator's choice among the identified wearables in the pack (simulated fights, never
        # losing Free Action, See Invisible, resist blindness/confusion or hold life; the user, 10-26). A ring over a worn
        # one: off first, step 4 puts it on.
        if not w.depth and not w.in_dungeon and not self.__dict__.get("gear_swapped_t", 0) > gnow() - 30:
            for it in pack:
                got = self.gear_better(it)
                if not got:
                    continue
                label, (_, old) = got
                on = next((i for i in worn if i["name"] == old), None) if old else None
                self.gear_swapped_t = gnow()
                if it["tval"] in (40, 45) and on is not None:
                    self.jewel_swap = it["name"]
                    self.cmd(f"custom t item={on['item']}", f"take off {on['name']} for {it['name']} (gear evaluator)",
                             hold=0.8)
                else:
                    self.cmd(f"custom w item={it['item']}", f"wear {it['name']} (gear evaluator)", hold=0.8)
                self.notify("tactic", f"gear evaluator: {label} (simulated fights; `gearcmp` for the table)", news=True)
                return True
        return False

    # what proves an ability in play (the rulebook's abilities.csv, restructure step 3): (ability,
    # the message, the line just before it that must match, a line before that rules it out)
    ABILITY_PROOFS = (
        ("free_action", r"You are unaffected", r"stares deep into your eyes|drains power from your muscles|mumbles\.$|"
                                               r"touches you|gazes (at )?you", r"burning your eyes|gestures at your feet|"
                                                                              r"mumbles strangely"),
        ("resist_blind", r"You are unaffected", r"burning your eyes", None),
        ("resist_nexus", r"You are unaffected", r"gestures at your feet|mumbles strangely", None),
        ("hold_life", r"You keep hold of your life force", None, None),
        ("sustain_str", r"You feel weak for a moment, but the feeling passes", None, None),
        ("sustain_int", r"You feel stupid for a moment, but the feeling passes", None, None),
        ("sustain_wis", r"You feel naive for a moment, but the feeling passes", None, None),
        ("sustain_dex", r"You feel clumsy for a moment, but the feeling passes", None, None),
        ("sustain_con", r"You feel sickly for a moment, but the feeling passes", None, None),
        ("sustain_chr", r"You feel ugly for a moment, but the feeling passes", None, None),
        ("feather_fall", r"You float gently", None, None),
    )
    ABILITY_LABEL = {"free_action": "Free Action", "resist_blind": "resist blindness", "resist_nexus": "resist nexus",
                     "hold_life": "hold life", "feather_fall": "feather fall"}

    def watch_abilities(self):
        """Abilities shown by the game's answers rather than the sheet: "You are
        unaffected!" just after a paralysing attack is Free Action (the Advisor's
        set-piece C8: Dive04 had it from m18 to m23 from unidentified boots, sold
        for 3 gold in m23), and the other proofs in the rulebook's abilities.csv
        (ABILITY_PROOFS). The unidentified worn items become its likely source."""
        w = self.w
        msgs = list(w.messages)
        for i, (ts, t) in enumerate(msgs):
            if ts <= self.ability_seen_t:
                continue
            before = [m for tt, m in msgs[max(0, i - 4):i] if ts - tt < 3]
            last = before[-1] if before else ""
            for ab, msg, need, veto in self.ABILITY_PROOFS:
                if not re.match(msg, t) or ab in self.inferred or self.has_ability(ab):
                    continue
                # (only the line just before counts: the same "unaffected" follows BLIND, HOLD and
                # TELE_LEVEL, and proves a different ability for each)
                if (need and not re.search(need, last)) or (veto and re.search(veto, last)):
                    continue
                self.inferred.add(ab)
                src = [re.sub(r"^(an?|\d+) ", "", re.sub(r"\s*\{[^}]*\}", "", i2["name"])).lower()
                       for i2 in w.items(equip=True) if self.iv(i2["name"]).known is False
                       or re.search(r"\{(good|excellent|special|magical)", i2["name"])]
                self.ability_sources |= set(src)
                label = self.ABILITY_LABEL.get(ab) or f"sustain {ab[8:].upper()}"
                self.notify("ability", f"you have {label} (\"{t}\"" + (f" after \"{last}\"" if need else "") +
                                       "), though no known item gives it: it's one of your unidentified worn items ("
                                       + (", ".join(src) or "none found") + "). The Pilot won't sell or drop those; "
                                       "identify them")
        self.ability_seen_t = max([self.ability_seen_t] + [ts for ts, _ in msgs])

    WEAPON_ABILITY_FLAGS = {"FREE_ACT", "SEE_INVIS", "HOLD_LIFE", "TELEPATHY", "FEATHER", "REGEN", "SLOW_DIGEST", "SPEED",
                     "STR", "DEX", "CON", "BLOWS", "LITE"}

    def weapon_abilities(self, name):
        """What a weapon (or armour) gives beyond damage and AC, from the rulebook's ego table (ego_flags.csv): Free
        Action, See Invisible, resists, sustains, stats... An unknown ego or a plain item: nothing."""
        if not hasattr(self, "_ego_flags"):
            try:
                self._ego_flags = {r["name"]: set(r["flags"].split()) for r in csv.DictReader(
                    open(os.path.join(HERE, "..", "rulebook", "ego_flags.csv")))}
            except OSError:
                self._ego_flags = {}
        for ego, flags in self._ego_flags.items():
            if ego and re.search(rf"\b{re.escape(ego)}\b", name or ""):
                return {f for f in flags if f in self.WEAPON_ABILITY_FLAGS or f.startswith(("RES_", "SUST_", "IM_"))}
        return set()

    @staticmethod
    def is_artifact(name):
        """A named artifact ('Dagger 'Narthanc'', 'the Phial of Galadriel'): its abilities aren't in the ego table."""
        return bool(re.search(r"'\w|\bthe \w+ of [A-Z]", name or ""))

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
            self.unanswered.append((gnow(), text[1:].strip()))
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
            # HP as a number: FORCE_MAXHP (all uniques) always has the maximum
            # (the Navigator told the user Wormtongue had ~137, the dice average;
            # he has 250 -- the Advisor's missions 15-16 replay)
            hn, _, hm = str(r.hp).partition("d")
            try:
                hp_txt = (f"{r.hp} = {int(hn) * int(hm)} (always the maximum)" if "FORCE_MAXHP" in r.flags
                          else f"{r.hp} (~{int(hn) * (int(hm) + 1) // 2} on average)") if hm else str(r.hp)
            except ValueError:
                hp_txt = str(r.hp)
            out.append(f"{r.name} ({r.char}): lvl {r.level} ({r.level * 50} ft), speed {r.speed - 110:+d}, "
                       f"HP {hp_txt}; blows {', '.join(r.blows) or 'none'}; "
                       f"spells 1 in {r.spell_freq}: {', '.join(sorted(r.spells))}" if r.spells else
                       f"{r.name} ({r.char}): lvl {r.level} ({r.level * 50} ft), speed {r.speed - 110:+d}, "
                       f"HP {hp_txt}; blows {', '.join(r.blows) or 'none'}; no spells")
            out[-1] += (f"; flags {', '.join(flags) or '-'}; max breath {r.max_breath}; "
                        f"melee per turn ~{r.per_turn:.0f} (worst {mx * (r.speed_x or 1):.0f}, drain blows {drains})"
                        f"; Advisor rating {r.danger if r.danger is not None else '?'}/5"
                        f"; for you now: {'DANGER: ' + why if why else 'no danger rule fires'}")
            # the rulebook (restructure step 3): the hunt check's verdict and what a kill drops
            refusal, est = self.hunt_refusal(r.name)
            out[-1] += f"; hunt check: {'REFUSED: ' + refusal if refusal else 'allowed (' + (est or '?') + ')'}"
            d = self.drop_row(r)
            if d:
                out[-1] += (f"; a kill drops ~{float(d['e_gold']):.0f} gold and ~{float(d['e_items']):.1f} items worth "
                            f"~{float(d['e_item_value_cap']):.0f} (P(ego) {float(d['p_excellent_any']):.0%}, "
                            f"P(artifact) {float(d['p_artifact_any']):.0%})")
        more = len(exact or found) - 6
        return "\n".join(out) + (f"\n(+{more} more)" if more > 0 else "")

    def uniques_killed(self):
        """Uniques this character has killed (runs/pilot/NICK/uniques_killed.json, kept by watch_kills;
        seeded from the logs): a repeat kill drops nothing and gives no XP."""
        if not hasattr(self, "_uk"):
            try:
                self._uk = set(json.load(open(os.path.join(self.rundir, "uniques_killed.json"))))
            except (OSError, ValueError, AttributeError):
                self._uk = set()
        return self._uk

    def drop_row(self, race):
        """The rulebook's drops.csv row for a monster (at its native depth), or None."""
        if not hasattr(self, "_drops"):
            try:
                self._drops = {r["idx"]: r for r in csv.DictReader(open(os.path.join(HERE, "..", "rulebook", "drops.csv")))}
            except OSError:
                self._drops = {}
        return self._drops.get(str(getattr(race, "idx", "")))

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
        slow = self.our_slowness()
        for y, x, r in w.monsters:
            if "NEVER_MOVE" in r.flags:
                continue
            sx = (r.speed_x if r.speed_x is not None else max(1.0, (r.speed - 100) / 10)) * slow
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

    # tables.c extract_energy, by speed (normal = 0): energy per game turn
    ENERGY = {-30: 200, -29: 200, -28: 200, -27: 200, -26: 200, -25: 200, -24: 200, -23: 300, -22: 300, -21: 300,
              -20: 300, -19: 300, -18: 300, -17: 300, -16: 300, -15: 400, -14: 400, -13: 400, -12: 400, -11: 400,
              -10: 500, -9: 500, -8: 500, -7: 500, -6: 600, -5: 600, -4: 700, -3: 700, -2: 800, -1: 900, 0: 1000}

    def our_slowness(self):
        """How many times faster than normal monsters act against us: 1 at normal speed or faster, 2 at -10,
        3.3 at -20 (m26: Gorged and slowed, six weak monsters adjacent took 270 -> 41 HP while no danger rule
        fired, the rules assuming our normal speed)."""
        sp = int((self.w.ind.get("speed") or [0])[0] or 0)
        if sp >= 0:
            return 1.0
        return 1000 / self.ENERGY.get(max(-30, sp), 200)

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
        stairs_pending = w.last_stairs_cmd and not waited(w.last_stairs_cmd[1], 1.2)
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
                                         "read Word of Recall now (it takes 8-23 s)")
                return True
        # Blind or confused (no scroll can be read) with the group's worst above our HP: the staff, which works blind
        # (m48: 13 Light hounds, 7 Wargs, 5 Mirkwood spiders; blind for 40 s, HP 340 -> 82, no read got through)
        if g > hp and not can_read and w.adjacent_monsters() and now - self.__dict__.get("blind_tele_t", -99.0) > 10:
            tp = self.teleport_item()
            if tp and tp[0] == "u":
                self.blind_tele_t = now
                self.cmd(f"custom u item={tp[1]['item']}", f"group danger {g:.0f} vs HP {hp}, can't read: staff of "
                                                           "teleportation", hold=0.6)
                self.notify("emergency", f"{names} can deal {g:.0f} (HP {hp}) and you can't read (blind or confused): "
                                         "used the Staff of Teleportation")
                return True
        # Phase only when it's really going badly: at 0.6-1.0x only once HP is
        # already below think_hp, and at most every 10 s (mission 9: a lone
        # Giant red frog, 58 worst-case vs 97 HP, cost 4 Phase Doors at full HP)
        pd = w.tagged("r", 1) or next((i for i in w.items(tval=TV_SCROLL) if "Phase Door" in i["name"]), None)
        hurting = g > hp or w.hp_frac < self.orders["think_hp"]
        if w.adjacent_monsters() and pd and can_read and hurting and now - self.phase_t > 10:
            self.phase_t = now
            self.phase_hist.append(now)
            self.cmd(f"custom r item={pd['item']}", f"group danger {g:.0f} vs HP {hp}: phase door", hold=0.6)
            self.notify("tactic", f"{names} can deal {g:.0f} (HP {hp}): phased away")
            return True
        return False

    def stairs_beside_still(self, still):
        """The stairs we're walking to are a step away (or under us) and the
        stationary monsters beside us are harmless for a turn: take them, don't
        step away. m25: a Brown mold (confuses, so never fought) beside the only
        '>' at 300 ft; the step-away walked 6 squares back and the dive pressed
        '>' there, for 2 minutes. Confusion doesn't stop the stairs (cmd2.c)."""
        w = self.w
        goals = {g for g in (self.mover.goals or ()) if isinstance(g, tuple)} if self.mover.active else set()
        if not goals and self.still_goals[0] == w.level_t:
            goals = self.still_goals[1]
        # (on the stairs the mover has already stopped: ask the goal -- M1 looped on with the mover check alone)
        g = self.goal
        want = getattr(g, "want", None) if isinstance(g, Dive) else "<>" if isinstance(g, Flee) else None
        if want and w.standing_on in ("<", ">") and w.standing_on in want:
            goals = set(goals) | {w.pos}

        def stairs(g):
            return w.memory.get(g) in ("<", ">") or (g == w.pos and w.standing_on in ("<", ">"))

        if not any(w.dist(g) <= 1 and stairs(g) for g in goals):
            return False

        def harmless(r):
            bad = ("PARALYZE", "UN_BONUS", "DISENCHANT")
            return not r.drains and not any(b.split(":")[1:2] and b.split(":")[1] in bad for b in r.blows) \
                and r.per_turn < 0.25 * max(1, w.hp[0])

        return all(harmless(m[2]) for m in still)

    def still_fight_tick(self, now, still):
        """A stationary monster next to us that blocks the way (sits by the
        square the mover is heading for): kill it if it's weak, by standing
        still (auto-retaliate). Mission 6 stalled a step from the only '>'
        beside a Disenchanter eye, stepping away and back while its gaze
        disenchanted the weapon and armour. A disenchanter in the way too strong
        to kill: leave the level. One beside the path, not in the way, is
        stepped away from like any other (m33, m34)."""
        w = self.w
        lev = w.clvl
        # (squares only: a free run's goals are {"free-run"} -- a crash in m25)
        goals = {g for g in (self.mover.goals or ()) if isinstance(g, tuple)} if self.mover.active else set()
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
            drains = r.drains or r.worst_melee[1] > 0   # (Red jelly STR, mission 15; Rot jelly CHR, 16)
            return r.level <= lev and not (paralyses and not self.has_ability("free_action")) \
                and not nosave and not drains

        # (only when it blocks the way, disenchanters too: m33 and m34 meleed Disenchanter molds beside the path, and
        # m33's shield lost +1 -- a mold can't follow, so stepping on past it costs nothing)
        targets = [m for m in still if any(w.dist(g, m[:2]) <= 1 for g in goals)]
        # (an item beside a disenchanter isn't worth the enchantment: m37 meleed a Disenchanter mold to reach Boldor's
        # drops, and the cloak and the new helm lost +1 each. The item is left; stairs and the way on still count)
        loot = self.__dict__.get("loot_mem") or {}
        for m in [m for m in targets if disenchants(m[2])]:
            items = [g for g in goals if w.dist(g, m[:2]) <= 1 and w.memory.get(g, " ") not in ".#%'+<>^:; "]
            if items and len(items) == len(goals):
                if loot.get("level") == w.level_t:
                    loot["done"] |= set(items)
                self.mover.stop()
                self.still_goals = (w.level_t, set())
                targets.remove(m)
                self.notify("tactic", f"left the item at {items[0][0]},{items[0][1]}: it lies beside a {m[2].name}, "
                                      "which would disenchant our gear", news=True)
        fight = [m for m in targets if killable(m[2])]
        if any(m[2].drains for m in still):
            fight = []      # (mission 16: killing a Green mold put it next to a Purple mushroom patch)
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

    BUFF_MSGS = {"fast": ("You feel yourself moving faster!", "You feel yourself slow down."),
                 "hero": ("You feel like a hero!", "The heroism wears off."),
                 "shero": ("You feel like a killing machine!", "You feel less Berserk.")}

    def buff_on(self, buff):
        """A timed effect (fast, hero, shero) on now, from the game's start and end messages (the status
        reply has no indicator for them: `flag("fast")` was always False)."""
        on, off = self.BUFF_MSGS[buff]
        last = False
        for _, t in self.w.messages:
            if t.startswith(on):
                last = True
            elif t.startswith(off):
                last = False
        return last

    # --- the per-monster asleep flag (the user, 10-26; the estimator's top data gap, memo 2026-10-25-replay) ---
    LOOK_EVERY = 5.0

    def look_tick(self, now):
        """Ask the server's targeting about the visible monsters (the client's `look N`: 'kill' mode cycles the
        monsters in line of sight, each described "A Warg (unhurt, asleep)"), when the set in view has changed, at
        most every LOOK_EVERY seconds; not with a monster adjacent or while resting. Then read the answers."""
        w = self.w
        self.read_looks()
        if not w.in_dungeon or not w.monsters or w.adjacent_monsters() or w.resting or \
                now - self.__dict__.get("look_t", -99.0) < self.LOOK_EVERY:
            return
        key = (w.level_t, frozenset((y, x) for y, x, _ in w.monsters))
        if key == self.__dict__.get("look_key"):
            return
        self.look_key, self.look_t = key, now
        self.c.send(f"look {min(12, len(w.monsters))}")

    def read_looks(self):
        """The `target` answers since the last read -> self.asleep {(y, x): (t, name, asleep)}: by position when a
        visible monster stands there, else by name (the nearest of that name not yet placed)."""
        w = self.w
        new = [t for t in w.targets if t[0] > self.__dict__.get("looks_read_t", 0.0)]
        if not new:
            return
        self.looks_read_t = new[-1][0]
        sl = self.__dict__.setdefault("asleep", {})
        mons = {(y, x): r for y, x, r in w.monsters}
        placed = set()
        for t, y, x, text in new:
            m = re.match(r"(?:an?|the) (.+?) \(([^)]*)\)", text, re.I)
            if not m:
                continue
            name, cond = m.group(1), m.group(2)
            q = (y, x) if (y, x) in mons and mons[(y, x)].name.lower() == name.lower() else next(
                (p for p in sorted(mons, key=w.dist) if mons[p].name.lower() == name.lower() and p not in placed), None)
            if q:
                placed.add(q)
                sl[q] = (t, mons[q].name, "asleep" in cond)
        for q in [q for q in sl if q not in mons]:
            del sl[q]                  # (moved or gone: unknown again)
        # (for the first live checks: are the answers' screen positions the map's?)
        self.log("looks", n=len(new), placed=len(placed), by_pos=sum(1 for _, y, x, _ in new if (y, x) in mons),
                 asleep=sorted(f"{v[1]}@{q[0]},{q[1]}" for q, v in sl.items() if v[2])[:12],
                 sample=[(y, x, tx[:60]) for _, y, x, tx in new[:3]])

    def is_asleep(self, y, x):
        v = self.__dict__.get("asleep", {}).get((y, x))
        return v[2] if v and gnow() - v[0] < 60 else None

    # --- the Navigator's executable standing orders (the user, 10-26: "decide in advance, act at Pilot speed") ---
    RULE_KINDS = {"leave": "leave the level when NAME is in view",
                  "hunt": "hunt NAME on sight (the hunt checks apply, as for `goal hunt NAME`)",
                  "thieves": "kill: hunt a thief (steals gold or items) in view within 6 squares",
                  "afraid": "teleport: afraid with no Heroism/Boldness/Berserk and monsters adjacent -> teleport"}

    def rules(self):
        if "nav_rules" not in self.__dict__:
            try:
                self.nav_rules = json.load(open(os.path.join(self.rundir, "rules.json")))
            except (OSError, ValueError, AttributeError):
                self.nav_rules = []
        return self.nav_rules

    def save_rules(self):
        try:
            json.dump(self.rules(), open(os.path.join(self.rundir, "rules.json"), "w"), indent=1)
        except (OSError, AttributeError):
            pass

    def has_rule(self, kind, arg=None):
        return any(r["kind"] == kind and (arg is None or r["arg"] == arg) for r in self.rules())

    def rule_tick(self, now):
        """Run the Navigator's reactions (`react`): leave the level when NAME is in view; hunt NAME on sight; kill thieves.
        True if it acted. (`react afraid teleport` runs in the fear handling.)"""
        w = self.w
        if not w.in_dungeon or not w.monsters or not self.rules() or isinstance(self.goal, (Flee, Recall, Recover)):
            return False
        done = self.__dict__.setdefault("rules_done", {})
        names = {r.name.lower(): (y, x, r) for y, x, r in w.monsters}
        for rl in self.rules():
            arg = rl["arg"]
            if rl["kind"] == "leave" and arg in names and done.get(("leave", arg)) != w.level_t:
                done[("leave", arg)] = w.level_t
                pl = self.plan
                if pl and pl.phase == "level" and pl.level == w.level_t and not pl.paused:
                    pl.level_done = f"your rule: leave when {names[arg][2].name} is seen"
                    self.set_goal(pl.mark(pl.next_dive(self)))
                else:
                    self.set_goal(Flee(f"your rule: {names[arg][2].name} seen"))
                self.notify("rule", f"{names[arg][2].name} seen: leaving the level (your `react leave`)", news=True)
                return True
            target = None
            if rl["kind"] == "hunt" and arg in names:
                target = names[arg][2]
            if rl["kind"] == "thieves" and arg == "kill":
                th = [(w.dist((y, x)), r) for y, x, r in w.monsters
                      if any(b.split(":")[1:2] in (["EAT_ITEM"], ["EAT_GOLD"]) for b in r.blows) and w.dist((y, x)) <= 6]
                if th and not any(self.danger_why(r) for _, r in th):
                    target = min(th, key=lambda t: t[0])[1]
            if target is not None and not isinstance(self.goal, Hunt) and \
                    now - done.get(("hunt", target.name, w.level_t), -99.0) > 30:
                done[("hunt", target.name, w.level_t)] = now
                role = self.req_role
                # (M5, 10-28: a Scruffy looking hobbit's hunt replaced a `goal dive` and the dive was lost when it
                # ended. A plan resumes by itself; a plain goal comes back after the hunt)
                prev = self.goal if self.goal is not None and not getattr(self.goal, "by_plan", False) else None
                try:
                    out = self.do_request({"cmd": "goal", "args": ["hunt", target.name.replace(" ", "_")],
                                           "role": "navigator"})
                finally:
                    self.req_role = role
                if out.get("ok") and prev is not None:
                    self.resume_after = prev
                self.notify("rule", f"{target.name} in view: " + ("hunting it" if out.get("ok") else
                                                                 f"no hunt ({out.get('error', '')[:120]})")
                            + f" (your `react {rl['kind']}`)", news=True)
                return bool(out.get("ok"))
        return False

    # --- the item-review queue (the user, 10-26: route judgement calls to the Navigator before they're irreversible) ---
    REVIEW_MIN_VALUE = 1000

    def review_state(self):
        if "review" not in self.__dict__:
            try:
                self.review = json.load(open(os.path.join(self.rundir, "review.json")))
            except (OSError, ValueError, AttributeError):
                self.review = {}
            self.review.setdefault("items", {})
            self.review.setdefault("decided", {})
            self.review.setdefault("town_visits", 0)
        # (m58: a Ring of Protection [+16] worn since m57 was still listed "SOLD at this town visit if undecided": what's
        # worn leaves the queue)
        worn = {i["name"] for i in (self.w.items(equip=True) if getattr(self, "w", None) else [])}
        for n in [n for n in self.review["items"] if n in worn]:
            del self.review["items"][n]
        return self.review

    def review_save(self):
        try:
            json.dump(self.review_state(), open(os.path.join(self.rundir, "review.json"), "w"), indent=1)
        except (OSError, AttributeError):
            pass

    def review_hold(self, it):
        """True while this identified wearable waits for the Navigator's word instead of being sold: it gives an ability
        or resist, or it's an artifact, or worth REVIEW_MIN_VALUE+ -- and the gear evaluator wouldn't wear it. Two town
        visits undecided: the policy sells it (news)."""
        name = it["name"]
        st = self.review_state()
        dec = st["decided"].get(name)
        if dec:
            return dec != "sell"
        if it["tval"] not in geareval.SLOT_OF_TVAL or it["tval"] == TV_LITE:
            return False
        gi = geareval.Item(name, it["tval"])
        iv = self.iv(name)
        why = "an artifact" if self.is_artifact(name) else \
            f"gives {', '.join(geareval.label(f) for f in sorted(gi.abilities()))}" if gi.abilities() else \
            f"worth ~{iv.value}" if iv.value >= self.REVIEW_MIN_VALUE else None
        if not why or not iv.known:
            return False
        q = st["items"].get(name)
        if q is None:
            st["items"][name] = {"why": why, "visit": st["town_visits"], "t": time.strftime("%Y-%m-%d %H:%M")}
            self.review_save()
            self.notify("review", f"held for your decision: {name} ({why}). `gearcmp {name.replace(' ', '_')[:30]}` "
                                  "compares it; `review sell|keep|wear NAME`. Undecided after 2 town visits, the "
                                  "policy sells it", news=True)
            return True
        if st["town_visits"] - q["visit"] >= 2:
            st["decided"][name] = "sell"
            st["items"].pop(name, None)
            self.review_save()
            self.notify("review", f"{name}: undecided for 2 town visits, the policy sells it", news=True)
            return False
        return True

    def fear_cure(self):
        """The potion to quaff when afraid and in danger: Heroism first (it does all Boldness does, plus to-hit and
        HP), Boldness only without it, Berserk last (kept for hard fights) -- the user, 10-25; it was the pack's
        order before."""
        pots = self.w.items(tval=TV_POTION)
        return next((i for n in ("Heroism", "Boldness", "Berserk") for i in pots if n in i["name"]), None)

    def hard_fight(self):
        """The adjacent mobile monsters and whether the fight is hard (berserk_tick's test): a unique, or a monster
        within 5 levels of ours, adjacent; or two or more adjacent and HP under 75%."""
        w = self.w
        adj = [r for *_, r in w.adjacent_monsters() if "NEVER_MOVE" not in r.flags]
        hard = any("UNIQUE" in r.flags or r.level >= w.clvl - 5 for r in adj) or (len(adj) >= 2 and w.hp_frac < 0.75)
        return adj, bool(adj) and hard

    HARD_FIGHT_OPTIONS = ("fight", "speed", "berserk", "speed+berserk", "phase")
    BAND_OPTIONS = ("fight", "stairs", "recall+phase", "phase")

    def band_shadow(self, detail):
        """Shadow mode at a band's leave decision (the user, 10-26, after m47: 9 Wargs, ~197 HP to fight them all vs
        333, fled to stairs 28 steps off, stuck, recalled -- shadow mode only ran once the flee had failed). The rules'
        action: the stairs when known, else Word of Recall. Once per band and level (20 s apart). Never acts."""
        w, now = self.w, gnow()
        key = (w.level_t, frozenset(r.name for *_, r in w.monsters))
        seen = self.__dict__.setdefault("band_shadow_seen", {})
        if now - seen.get(key, -99.0) < 60 or now - self.__dict__.get("band_shadow_t", -99.0) < 20:
            return None
        seen[key], self.band_shadow_t = now, now
        rules = "stairs" if w.find("<>") else "recall+phase"
        # (time is part of the trade: options_sim 26g charges each line xp_per_block for its blocks and the rest to
        # recover -- the Advisor: our XP per dungeon minute at this depth / 96 blocks a minute)
        d = (self.rate_state().get("depth") or {}).get(str(w.depth_ft))
        xpb = round(d[0] / (d[1] / 60) / 96, 3) if d and d[1] > 300 else 0
        return self.shadow_decision(f"band: rules {rules} ({detail[:100]})", options=self.BAND_OPTIONS,
                                    trigger="band", rules=rules, extra_p={"xp_per_block": xpb})

    def hard_fight_shadow(self, now):
        """Shadow mode at the start of a hard fight (the user, 10-25, on the Advisor's shadow-review memo: its replays'
        one consistent gain was Speed or Speed+Berserk quaffed at the start of hard fights, which the rules only quaff
        in an emergency). Once per fight: a new set of adjacent monsters on this level, not within 60 s of the same set,
        nor 20 s of the last. The rules' choice here is Berserk when berserk_tick would quaff it, else fighting on.
        Never acts."""
        w = self.w
        if not w.in_dungeon or not w.pos:
            return None
        adj, hard = self.hard_fight()
        if not hard:
            return None
        key = (w.level_t, frozenset(r.name for r in adj))
        seen = self.__dict__.setdefault("hard_fight_seen", {})
        if now - seen.get(key, -99.0) < 60 or now - self.__dict__.get("hard_fight_t", -99.0) < 20:
            return None
        seen[key], self.hard_fight_t = now, now
        pot = any("Berserk" in i["name"] for i in w.items(tval=TV_POTION))
        berserk = pot and not self.buff_on("shero") and waited(getattr(self, "berserk_t", 0), 30)
        fast = any("of Speed" in i["name"] for i in w.items(tval=TV_POTION)) and not self.buff_on("fast") and \
            waited(getattr(self, "speed_start_t", 0), 30)
        label = "speed+berserk" if fast and berserk else "speed" if fast else "berserk" if berserk else "fight"
        names = ", ".join(sorted({r.name for r in adj}))
        return self.shadow_decision(f"hard fight with {names}: rules {label}", options=self.HARD_FIGHT_OPTIONS,
                                    trigger="hard_fight", rules=label)

    def speed_start_tick(self, now):
        """A Potion of Speed at the start of a hard fight (the user, 10-25, on the Advisor's replays: drunk at the
        start rather than when the emergency fires, it beat the rules in 3 of 4 hard fights -- the gain is mostly
        timing, the same potion drunk earlier). Same test as Berserk (hard_fight); not when already hasted."""
        w = self.w
        if not w.in_dungeon or self.buff_on("fast") or not waited(getattr(self, "speed_start_t", 0), 30):
            return False
        adj, hard = self.hard_fight()
        pot = next((i for i in w.items(tval=TV_POTION) if "Potion" in i["name"] and "of Speed" in i["name"]), None)
        if not (hard and pot):
            return False
        self.speed_start_t = now
        names = ", ".join(sorted({r.name for r in adj}))
        self.cmd(f"custom q item={pot['item']}", f"a hard fight ({names}): quaff {pot['name']} at the start", hold=0.6)
        self.notify("tactic", f"a hard fight with {names}: quaffed {one_of(pot['name'])} at the start", news=True)
        return True

    def berserk_tick(self, now):
        """A Potion of Berserk Strength at the start of a hard melee fight (the user, 10-25: carried, never used):
        +30 max HP and 30 healed, +24 to-hit, no fear, -10 AC for 25-50 turns (use-obj.c, xtra1.c). Hard: a
        unique, or a monster within 5 levels of ours, adjacent; or two or more adjacent and HP under 75%."""
        w = self.w
        if not w.in_dungeon or self.buff_on("shero") or not waited(getattr(self, "berserk_t", 0), 30):
            return False
        adj, hard = self.hard_fight()
        pot = next((i for i in w.items(tval=TV_POTION) if "Berserk" in i["name"]), None)
        if not (adj and hard and pot):
            return False
        self.berserk_t = now
        self.cmd(f"custom q item={pot['item']}", f"a hard fight ({', '.join(sorted({r.name for r in adj}))}): quaff "
                                                 f"{pot['name']}", hold=0.6)
        self.notify("tactic", f"a hard fight with {', '.join(sorted({r.name for r in adj}))}: quaffed "
                              f"{one_of(pot['name'])} (+to-hit, +30 HP, no fear)", news=True)
        return True

    def status_tick(self, now, mons_near):
        """Quaff the cheapest potion that cures a dangerous status in a fight
        (Advisor memo P4 + Erratum): stun at once, blind/confused when
        something is near, poison only when HP is also getting low."""
        w = self.w
        if not w.in_dungeon or not waited(self.cure_t, 1.5):
            return False
        in_combat = w.adjacent_monsters() or now - w.last_hit_t <= 3
        if not in_combat and not w.flag("blind"):     # (blind: the triggers below decide -- m43)
            return False
        want = []
        mobile_near = [m for m in mons_near if "NEVER_MOVE" not in m[2].flags]
        # (a mold can't follow: step away and let it wear off -- mission 15, the user)
        # Only when it matters (mission 16 spent a CCW on a stun at 167/180 and
        # CLW/CSW on blindness/confusion at 99% against level-6 Novice mages):
        # low HP, a heavy stun, or a monster near our level
        threat = w.hp_frac < self.orders["think_hp"] or any(m[2].level >= w.clvl - 5 for m in mobile_near)
        if w.flag("stun") and (threat or w.ind.get("stun", [0])[0] >= 2):
            want.append("stun")
        # Blind or confused and still being hit: cure whatever we can see (mission
        # 15: blind + confused 9 s with nothing in view, HP 160 -> 86, no cure)
        # (unseen means unseen: the set-piece C3 spent 4 CSW and 2 CCW in 18 s curing confusion from Kobold
        # shamans at 84-93% HP, because any hits counted here; the user: spend only when it matters)
        # (and blind, everything is unseen: m25 drank 2 CSW at 100% HP against a Novice mage's magic missiles,
        # ~1% of HP a second. Only when it matters: low HP, hurt and still being hit, or heavy damage)
        rate = w.damage_rate(3.0)
        hit_unseen = not mobile_near and now - w.last_hit_t <= 3 and (
            w.hp_frac < self.orders["think_hp"] or (w.hp_frac < 0.8 and rate > 0.01 * w.hp[1]) or
            rate > 0.04 * w.hp[1])
        if (mobile_near and threat or hit_unseen) and w.flag("confused"):
            want.append("confused")
        # (and blind in a fight we were in a moment ago, or while an escape needs to read: m43 23:20, blinded in a
        # 10-monster band at 84% HP -- no monster "near" can be seen blind, so it rested three times while unseen
        # things bit it, and the flee couldn't read its Magic Mapping. The user: "doesn't a cure potion fix that?")
        mm = self.__dict__.get("mons_mem") or {}
        seen_close = any(now - m["t"] < 10 and m.get("level") == w.level_t and w.pos and m.get("pos") and
                         w.dist(m["pos"]) <= 6 for m in mm.values())
        band_recent = self.band_warned[0] == w.level_t and now - self.band_warned_t < 30
        must_read = isinstance(self.goal, (Flee, Recall, Recover))
        # (but not again and again: m44's Light hounds re-blinded it with their breath and 16 CLW went in one fight.
        # After 2 blind cures in 30 s, fight on blind -- auto-retaliate needs no sight -- unless an escape must read or
        # HP is low)
        bc = [t for t in self.__dict__.setdefault("blind_cures", []) if now - t < 30]
        self.blind_cures = bc
        spent = len(bc) >= 2 and not must_read and w.hp_frac >= self.orders["think_hp"]
        if w.flag("blind") and not spent and (mobile_near and threat or hit_unseen or seen_close or band_recent
                                                or must_read):
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
                    if status == "blind":
                        self.blind_cures.append(now)
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
            # news, not an alert: it woke the Navigator five times in mission 20
            # with nothing to do
            self.notify("unseen_attacker", "heard a door burst open: something is coming; be ready to leave",
                        news=True)
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
        # A shriek (a Shrieker mushroom patch) does no damage: it wakes and
        # hastens monsters nearby (mission 17 left a 100 ft level over one)
        if "shriek" in cause:
            self.notify("unseen_attacker", f"'{cause}': a shrieker (no damage; it wakes monsters nearby); "
                                           "carrying on", news=True)
            return False
        # A weak caster we can see (in the dark the game still says "It ..."):
        # mission 20 fled down a '>' twice from Novice priests 3 squares away
        casters = [r for y, x, r in w.monsters if r.spells and w.dist((y, x)) <= 10 and r.level <= w.clvl - 5
                   and "UNIQUE" not in r.flags]
        if casters and not cause.startswith("losing HP") and w.hp_frac >= self.orders["think_hp"]:
            self.notify("unseen_attacker", f"'{cause}': probably the {casters[0].name} (lvl {casters[0].level}) in "
                                           f"view; carrying on (HP {w.hp_frac:.0%})", news=True)
            return False
        if re.search(r"commands you to return|magic missile|fires an arrow|fires a bolt|mumbles|"
                     r"points at you and curses|casts a fearful illusion", cause) \
                and w.hp_frac >= self.orders["think_hp"]:
            self.notify("unseen_attacker", f"'{cause}': minor attack from something unseen; carrying on "
                                           f"(HP {w.hp_frac:.0%})", news=True)
            return False
        prev = self.goal.describe() if self.goal else None
        # a gaze may be a paralysing spell: deadly without Free Action, where a
        # walk to far stairs is worse than a recall (mission 21's "stares deep")
        para = re.search(r"stares deep|gazes deep|looks deep|gazes at", cause) and \
            not self.has_ability("free_action")
        hint = " (it may be paralysis and you have no Free Action: if the stairs are far, read Word of Recall)" \
            if para else ""
        # Above 80% HP: news only (the Advisor's A5: curses, darkness and confusion from the dark changed
        # levels at full HP in m17-m21; set-piece A5's Dark elven priest). A paralysing gaze still leaves.
        if w.hp_frac > 0.8 and not para:
            self.notify("unseen_attacker", f"'{cause}': something unseen is casting at you; carrying on at HP "
                                           f"{w.hp_frac:.0%} (it leaves below 80%)", news=True)
            return False
        if self.hunt_ordered(gnow(), "an unseen attacker"):
            return False
        if w.find("<>"):
            self.set_goal(Flee("unseen attacker"))
            self.notify("unseen_attacker", f"'{cause}': something unseen is attacking"
                                           f"{' while ' + prev if prev else ''}; heading for the stairs{hint}")
        else:
            self.notify("unseen_attacker", f"'{cause}': something unseen is attacking and no stairs are known: "
                                           "consider Word of Recall or Phase Door")
        return True

    def sidestep(self, threats):
        """One step to a free square next to none of threats (stationary
        monsters: one square away is enough). Returns True if a step was sent."""
        w = self.w
        now = gnow()
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

    def quiet_spot(self, reach=30):
        """A square to wait on (QuietWait): one we've walked this level, inside a room (7+ of its 8 neighbours open
        floor), 4+ from any unexplored square and 3+ from a door; the most sheltered (far from the unknown) of the
        near ones. None if there's no such square within reach."""
        w = self.w
        front = self.frontier()
        doors = [q for q, ch in w.memory.items() if ch in "+'"]

        def room(t):
            return sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy or dx)
                       and w.memory.get((t[0] + dy, t[1] + dx)) == ".") >= 7

        def far(t, qs):
            return min((w.dist(t, q) for q in qs), default=99)

        cands = [t for t in w.walked if w.dist(t) <= reach and w.memory.get(t) == "." and room(t)]
        cands = [(min(far(t, front), 10), t) for t in cands if far(t, doors) >= 3]
        cands = [(f, t) for f, t in cands if f >= 4]
        if not cands:
            return None
        return max(cands, key=lambda ft: (ft[0] - w.dist(ft[1]) / 3, -w.dist(ft[1])))[1]

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
        tv = {"potion": "Potion", "scroll": "Scroll", "wand": "Wand", "staff": "Staff", "rod": "Rod",
              "ring": "Ring", "amulet": "Amulet"}
        # the rulebook (restructure step 3): a kind is junk when it's worthless at every level, or
        # worth at most a gold piece (Water, Apple Juice): 38 kinds. The file must exist (the old kinds.csv
        # fallback went in session 10, C10)
        rows = {}
        for r in csv.DictReader(open(os.path.join(HERE, "..", "rulebook", "kinds_by_level.csv"))):
            rows.setdefault(f"{tv.get(r['tval'], r['tval'])} of {r['kind']}", []).append(r)
        for name, rs in rows.items():
            self.junk_kinds[name] = all(float(r["worthless"] or 0) >= 1 or float(r["value"] or 0) <= 1 for r in rs)

    def learn_flavour(self, flavour, kind, how):
        if not flavour or not kind or " of " not in kind or self.flavours.get(flavour, {}).get("kind") == kind:
            return
        if type_word(flavour) != type_word(kind):
            self.log("note", text=f"flavour pairing refused (type mismatch): {flavour} = {kind} ({how})")
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
        if it["tval"] == TV_SCROLL:
            # Reading one costs nothing and teaches the flavour; selling a lone
            # one for ~8 threw away a Teleportation (mission 18). The curse
            # scrolls are native to 2500 ft, so at our depths a read is safe
            return ("a lone unknown scroll: read it to learn it (`read L`, in town or somewhere quiet; "
                    "Teleportation, Teleport Level and Magic Mapping are worth keeping)")
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
        # {good} weapons/armour whose pluses aren't known yet (mission 16: a Trident
        # {good} sold for 42 was (+3,+7), resold at 1848; Identify costs ~83)
        known = re.search(r"\([+-]\d+,[+-]\d+\)|\[\d+,[+-]\d+\]", name)
        if "good" in tags and not known:
            return True
        # identified, with no ego or artifact name: an ordinary item, whoever dropped it (m25: Mughash's
        # Broad Sword (+4,+6) and Battle Axe (+1,+5) were refused as "probably special" after Identify)
        bare = re.sub(r"\s*\{[^}]*\}", "", name)
        if known and " of " not in bare and "'" not in bare and not re.search(r"\b(the|of)\b [A-Z]", bare):
            return False
        if not self.unique_names:
            self.unique_names = {r.name.lower() for r in self.w.g.races.values() if "UNIQUE" in r.flags}
        return any(u in tags for u in self.unique_names)

    LOOT_OWED_R = 25          # items passed up while monsters were in view: fetched once it's clear, this far
    LOOT_VALUABLE_R = 30      # devices and jewellery: the Pilot fetches them itself, this far
    VALUABLE_GLYPHS = "-_=\""   # wand/rod, staff, ring, amulet

    def loot_step(self, state):
        """Fetch items (dive and explore share this): those within loot_radius; those passed up while
        monsters were in view, within LOOT_OWED_R once it's clear; devices and jewellery within
        LOOT_VALUABLE_R. An item counts as done once we've stood on it (the pickup policy decides) or after
        3 interrupted walks. The user (m29): gold and an unknown wand left beside the path while a Baby black
        dragon was in view, never revisited (12 squares off, beyond loot_radius 10); a walk cut short was
        never retried (the square was marked looted when the walk began); the interesting-item notice waited
        for a `goal fetch` nobody sent under a trip plan.
        state: the goal's dict ({'looting': bool, 'target': square, 'level': t}). True while fetching."""
        w = self.w
        lr = int(self.orders.get("loot_radius", 0))
        mem = self.__dict__.setdefault("loot_mem", {})
        if mem.get("level") != w.level_t:
            mem.clear()
            mem.update(level=w.level_t, done=set(), tries=collections.Counter(), owed=set())
        if state.get("level") != w.level_t:
            state.update(level=w.level_t, looting=False, target=None)
        if not lr or self.orders.get("pickup", "all") != "all":
            # (order pickup=none: no walks to loot either; it used to walk there and leave it -- refactor-candidates A5)
            if state.get("looting"):
                state["looting"] = False
                self.mover.stop()
            return False
        items = [t for t in self.resolve_target("item") if t not in mem["done"]]
        # (no detours while a band is about: the Advisor's set-piece C5, mission 22's loot room. A band out of
        # view now may be round the corner. Molds don't count: the planner keeps clear of them; nor do weak
        # monsters, 10+ levels below us and not dangerous: auto-retaliate kills them if they come. The set-piece
        # M2: a Cave lizard 16 squares off held a wand back for good; a Jackal pack cut the walk short and the
        # dive left without it)
        if self.loot_blocked():
            mem["owed"] |= {t for t in items if w.dist(t) <= lr}
            if state.get("looting"):
                state["looting"] = False
                mem["tries"][state["target"]] += 1
                self.mover.stop()
            return False
        if state.get("looting"):
            st = self.mover.tick()
            if st == "moving":
                return True
            tgt = state["target"]
            state["looting"] = False
            if w.pos == tgt or st == "arrived":
                mem["done"].add(tgt)
            else:
                mem["tries"][tgt] += 1
            # (on to the next, or the same again: handing back here let the dive head for the stairs -- M2, a
            # Rock lizard's fight stopped the walk 2 squares from the wand)
        if self.mover.active:
            return False
        for t in [t for t in items if mem["tries"][t] >= 3]:
            mem["done"].add(t)
        items = [t for t in items if t not in mem["done"]]
        valuable = {t for t in items if w.memory.get(t) in self.VALUABLE_GLYPHS and w.dist(t) <= self.LOOT_VALUABLE_R}
        owed = {t for t in items if t in mem["owed"] and w.dist(t) <= self.LOOT_OWED_R}
        cands = {t for t in items if w.dist(t) <= lr} | owed | valuable
        if not cands:
            return False
        tgt = min(cands, key=w.dist)
        if not self.mover.go([tgt]):
            mem["done"].add(tgt)
            return False
        # (a wall between: a walk far longer than the distance isn't worth it)
        reach = self.LOOT_VALUABLE_R if tgt in valuable else self.LOOT_OWED_R if tgt in owed else lr
        if len(self.mover.path) > reach * 3 // 2:
            self.mover.stop()
            mem["done"].add(tgt)
            return False
        state.update(looting=True, target=tgt)
        return True

    def loot_blocked(self):
        """No detours for loot now (loot_step's test): a band about, a mobile monster that matters, low HP, blind or
        confused."""
        w = self.w
        band = self.band_warned[0] == w.level_t and gnow() - self.band_warned_t < 90
        mobile = [m for m in w.monsters if "NEVER_MOVE" not in m[2].flags
                  and (m[2].level > w.clvl - 10 or self.danger_why(m[2]))]
        return bool(mobile or band or w.hp_frac < self.orders.get("think_hp", 0.65) or w.flag("blind")
                    or w.flag("confused"))

    LOOT_PATH_R = 3           # walking to the stairs: a detour this far for loot beside the path
    def loot_beside(self):
        """An item not yet looted within LOOT_PATH_R, and nothing against a detour (the dive walking to the stairs,
        which otherwise loots only before it sets off)."""
        mem = self.__dict__.get("loot_mem") or {}
        if mem.get("level") != self.w.level_t or not int(self.orders.get("loot_radius", 0)):
            return False
        return any(self.w.dist(t) <= self.LOOT_PATH_R for t in self.resolve_target("item")
                   if t not in mem["done"]) and not self.loot_blocked()

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
        old = self.goal
        if old is not None and getattr(old, "overridden", None) and old is not goal:
            self.settle_hunt(old, "replaced", goal.describe() if goal else "stopped")
        self.mover.stop()
        # (a goal set while handling the Navigator's or the Architect's request is theirs: goal_origin reads it)
        if goal is not None and getattr(goal, "role", None) is None and self.__dict__.get("acting") in ("nav", "arch"):
            goal.role = "navigator" if self.acting == "nav" else "architect"
        self.goal = goal
        self.goal_t = gnow()             # (watch_progress counts from here)
        self.idle_recalled = False
        self.log("goal", goal=goal.describe() if goal else None, by=self.__dict__.get("acting", "pilot"))

    def step_goal(self):
        if not self.goal:
            return False
        if self.w.in_dungeon and (self.w.flag("blind") or self.w.flag("confused")) and \
                isinstance(self.goal, (Explore, Search, Dive)):
            # steps go astray and we can't see (mission 15 kept sending explore
            # moves into walls): wait it out (fights and cures still run)
            if self.mover.active:
                self.mover.stop()
            return True
        try:
            r = ("failed", self.goal.abort) if getattr(self.goal, "abort", None) else self.goal.tick(self)
        except Exception as e:           # a goal bug must not kill the pilot
            r = ("failed", f"error: {e!r}")
        if r:
            status, detail = r
            g = self.goal.describe()
            quiet = getattr(self.goal, "quiet", False)     # the Pilot's own small goals: news only
            self.goal_ending = self.goal
            self.goal = None
            self.mover.stop()
            if self.resume_after is not None:
                # An emergency interrupted this goal: carry on with it (the
                # Navigator had to re-send its climb after every stair hop)
                self.goal, self.resume_after = self.resume_after, None
                self.log("goal", goal=self.goal.describe(), why="resumed after recovering")
                self.news.append({"t": round(gnow(), 3), "what": "resumed",
                                  "detail": f"{g}: {detail}; resumed '{self.goal.describe()}'", "goal": None})
                return True
            ended = self.goal_ending
            if getattr(ended, "overridden", None):
                self.settle_hunt(ended, status, detail)
            if isinstance(ended, WalkAway) and status == "failed":
                self.__dict__.setdefault("walkaway_failed", set()).add(self.w.level_t)
                self.flee_t = 0.0             # (the danger flee may act at once)
            if isinstance(ended, Hunt) and status == "failed" and "blinked away" in str(detail) and self.w.in_dungeon:
                self.notify({"done": "goal_done", "failed": "goal_failed"}[status], f"{g}: {detail}", news=quiet)
                self.goal = Reprieve(ended.target)
                self.goal_t = gnow()
                if self.plan and self.plan.paused and ended is self.plan.pause_goal:
                    self.plan.pause_goal = self.goal      # (the plan waits for the reprieve too)
                self.log("goal", goal=self.goal.describe(), why="a blinker got away: rest is free (the user)")
                return True
            if self.plan:
                if getattr(ended, "by_plan", False):
                    self.plan.goal_ended(self, ended, status, detail)
                    quiet = True
                elif self.plan.paused and ended is self.plan.pause_goal:
                    self.plan.paused = False
                    self.notify("plan", f"your goal ended ({g}: {detail}); the trip plan carries on")
            self.notify({"done": "goal_done", "failed": "goal_failed"}.get(status, status),
                        f"{g}: {detail}" if detail else g, news=quiet)
            if status == "failed" and g.startswith(("flee", "leave")):    # (m26's `goal leave` got stuck too)
                self.flee_failed(g)
        return True

    def flee_failed(self, goal=None):
        """A flee that can't reach the stairs, with monsters close: don't go
        idle among them (mission 14: Lagduf's pack, stairs 66 away, the
        Navigator had to read Word of Recall itself) -- start a recall and
        phase out of reach while it charges. A planned leave for a band at high HP with nothing on us
        first looks for stairs (BandLeave), once per level."""
        w, now = self.w, gnow()
        self.flee_fail_t = now
        soft = self.__dict__.setdefault("band_soft_levels", set())
        if goal and "band" in goal and w.in_dungeon and w.level_t not in soft and w.hp_frac >= 0.8 and \
                not w.adjacent_monsters() and not any(self.danger_why(r) for *_, r in w.monsters) and \
                not self.recall_started(now):
            soft.add(w.level_t)
            names = sorted({r.name for y, x, r in w.monsters if w.dist((y, x)) <= 10}) or ["the band"]
            self.set_goal(BandLeave(names))
            return
        # (decoded or only listed by the server, as danger_seen counts them:
        # mission 15's Brodda was listed 0.1 s before the map decode, so this
        # saw nothing and no Word of Recall was read at full HP)
        # (a dangerous one counts at any range: set-piece A2I's Ibun cast fire bolts and Slow from 12-13
        # squares for 7 s while this waited for him to come within 5)
        near = [m for m in w.monsters if w.dist(m[:2]) <= 5 or self.danger_why(m[2])] + \
            [(None, None, r) for r in w.listed_only() if self.danger_why(r)]
        if not w.in_dungeon or not near or w.flag("blind") or w.flag("confused"):
            return
        if not self.recall_started(now):
            wor = next((i for i in w.items(tval=TV_SCROLL) if "Word of Recall" in i["name"]), None)
            if wor:
                self.recall_t = now
                self.cmd(f"custom r item={wor['item']}", "flee failed with monsters close: word of recall", hold=0.5)
                self.notify("emergency", f"couldn't reach the stairs with {len(near)} monsters close: read Word of "
                                         "Recall (8-23 s); phasing while it charges")
                return
        pd = w.tagged("r", 1) or next((i for i in w.items(tval=TV_SCROLL) if "Phase Door" in i["name"]), None)
        if pd and w.adjacent_monsters() and now - self.phase_t > 2.5:
            self.phase_t = now
            self.phase_hist.append(now)
            self.cmd(f"custom r item={pd['item']}", "flee failed, monsters adjacent: phase door", hold=0.6)

    def idle(self):
        w = self.w
        if self.plan and not self.plan.paused:
            return                 # (the plan is the standing instruction; it has its own 90-minute cap)
        if w.in_dungeon and not self.idle_recalled and \
                gnow() - self.last_agent > self.orders["idle_recall_s"]:
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
            if w.dist((y, x)) > 10 or ch in "#%*: 12345678":
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
        # (again when weak ones swarm: m40's Giant fruit flies grew to 16 after a news-only notice, boxed the Pilot in
        # and made it stuck; the trip only leaves on a notice that isn't news)
        swarm = len(br) >= 8 and self.breeder_level == w.level_t and getattr(self, "breeder_weak", False)
        if (len(br) >= 3 and self.breeder_level != w.level_t) or swarm:
            self.breeder_level = w.level_t
            if isinstance(self.goal, Dive):
                return            # a dive is leaving this level anyway
            # Weak ones (Blue worm masses at clvl 19) are only news: they wake
            # the Navigator for nothing (mission 3)
            lev = w.clvl
            weak = all(r.level <= lev - 10 for r in br) and len(br) < 8
            self.breeder_weak = weak
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
        worn = next((i for i in w.items(equip=True) if i["tval"] == TV_LITE), None)
        unlit = not worn and w.depth != 0 and now - getattr(self, "unlit_try_t", 0) > 1.5
        if (now < self.light_t and not unlit) or now < self.busy_until or w.store:
            return False
        if unlit:
            self.unlit_try_t = now           # (in the dungeon without a light: at once, not after the 5-60 s wait)
        self.light_t = now + 5
        m = re.search(r"with (\d+) turns", worn["name"]) if worn else None
        turns = int(m.group(1)) if m else None
        if worn and "Lantern" in worn["name"] and turns is not None and turns < 3000:
            flask = next((i for i in w.items(tval=TV_FLASK)), None)
            if flask:
                self.cmd(f"custom F item={flask['item']}", f"refill lantern ({turns} turns left)", hold=0.6)
                return True
            # a fuller lantern in the pack (m39 ran its worn one down to ~700 turns with a 13290-turn spare carried)
            spare = self.best_light()
            if spare and self.light_left(spare) > turns + 1000:
                self.cmd(f"custom w item={spare['item']}", f"swap to the fuller lantern ({turns} turns left on the "
                                                           f"worn one)", hold=0.6)
                self.notify("tactic", f"lantern at {turns} turns: swapped to the spare ({self.light_left(spare)} turns)",
                            news=True)
                return True
            self.warn_light("lantern out" if turns == 0 else "lantern low",
                            f"lantern at {turns} turns and no flasks of oil")
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
            self.warn_light("torch out" if turns == 0 else "torch low",
                            f"torch at {turns} turns and no fresher torch: buy torches or a lantern")
        elif not worn and w.depth != 0:
            spare = self.best_light()
            if spare:
                self.cmd(f"custom w item={spare['item']}", "wield a light", hold=0.6)
                return True
            self.warn_light("no light", "no light source")
        return False

    def use_stair_location(self, why):
        """Use a Staff or zap a Rod of Door/Stair Location (an unknown flavour too, when the
        flavour table knows it). True if it acted."""
        w = self.w
        if gnow() < self.busy_until or w.flag("blind") or w.flag("confused"):
            return False
        for it in w.items():
            kind = it["name"] if " of " in it["name"] else (self.flavour_of(it) or {}).get("kind", "")
            if it["tval"] in (55, 66) and "Door/Stair Location" in kind and "(0 charges)" not in it["name"] \
                    and "charging" not in it["name"]:
                self.cmd(f"custom {'u' if it['tval'] == 55 else 'z'} item={it['item']}",
                         f"{why}: Door/Stair Location", hold=0.8)
                return True
        return False

    @staticmethod
    def light_left(i):
        t = re.search(r"with (\d+) turns", i["name"])
        return int(t.group(1)) if t else (1 if "Lantern" in i["name"] else 0)

    def best_light(self):
        """The light in the pack with the most fuel left (not a burnt-out one), or None."""
        return max((i for i in self.w.items(tval=TV_LITE) if self.light_left(i) > 0), key=self.light_left, default=None)

    def wear_light(self, why):
        """Put the best light in the pack on (reading needs one: the Pilot takes it
        off in town). True if it acted."""
        lite = self.best_light()
        if not lite:
            return False
        self.light_t = gnow() + 60         # (town_light leaves it on meanwhile)
        self.cmd(f"custom w item={lite['item']}", f"light on: {why}", hold=0.8)
        return True

    def warn_light(self, key, text):
        """A light warning once per state (low -> out), again after 10 min; in
        town it's news, not an alert (Dive04 raised 573 'lantern at 0 turns'
        alerts, one every 2 min while it idled in town: the post-mortem's §4.7)."""
        now = gnow()
        if key == self.light_warned_key and now - self.light_warned < 600:
            return
        self.light_warned, self.light_warned_key = now, key
        self.notify("low_supply", text, news=not self.w.in_dungeon)

    JUNK_DEVICES = ("Haste Monsters", "Clone Monster", "Heal Monster")

    def auto_destroy(self, now):
        """Destroy pack items whose pseudo-ID feeling is on the autodestroy list
        (the Navigator was cleaning the pack by hand every few minutes)."""
        w = self.w
        feelings = [f.strip() for f in self.orders.get("autodestroy", "").split(",") if f.strip()]
        if not feelings or now < self.busy_until or now - self.autodestroy_t < 2 or w.inven_dirty:
            return False
        # identified junk too -- a kind on the `junk` list, or a harmful device (m28 kept a Staff of Haste Monsters
        # and a Scroll of Aggravate Monster after Identify)
        junk = [j.strip() for j in self.orders.get("junk", "").split(",") if j.strip()] + list(self.JUNK_DEVICES)
        for it in w.items():
            n = it["name"]
            if it["tval"] in (55, 65, 66, 70, 75) and " of " in n and not self.is_kept(n) and \
                    any(re.search(rf"\bof {re.escape(j)}\b", n) for j in junk) and "@" not in n:
                self.autodestroy_t = now
                self.c.send("confirm yes")
                self.cmd(f"custom k item={it['item']} value={it['number']}", f"autodestroy junk {n}", hold=0.6)
                w.inven_dirty = True
                return True
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
                # (the tavern stash first: m46's Navigator read "at the Alchemist" and planned to buy one, with a
                # Restore Dexterity waiting in the tavern)
                def where(n):
                    k = f"Restore {full[n]}"
                    if self.stash_has(k):
                        return f"Potion of {k}: one is in the tavern stash -- `plan town` fetches it, don't buy one"
                    return f"Potion of {k} at the Alchemist (5), ~470 (the Temple doesn't sell them)"
                self.notify("stat_drained", f"{', '.join(new)} drained (blows {blows}); levels don't restore it: "
                            + "; ".join(where(n) for n in new))
                # Second drain on this level from something in view: leave
                # (Borg memo §3.2; mission 7's scorpion drained STR three times)
                w = self.w
                # Drained by something we can't see (not a trap's dart): leave at once. m29 and m30 lost DEX to a
                # Moaning spirit (invisible, passes walls, +10 speed, TOUCH:LOSE_DEX; "It wails at you", "It
                # touches you"): it can't be fought or walked away from, and each drain costs a ~470 potion
                now = gnow()
                trap = any(now - ts < 4 and re.search(r"dart|trap|rune", t, re.I) for ts, t in w.messages)
                seen = any(r.drains or r.worst_melee[1] > 0 for *_, r in w.monsters)
                if w.in_dungeon and not trap and not seen and set(new) & {"STR", "DEX", "CON"}:
                    self.notify("drainer", f"an unseen monster drained {', '.join(new)} (invisible: a Moaning spirit or "
                                           "a Quasit at these depths): leaving the level", news=False)
                    if not self.plan and w.find("<>") and not isinstance(self.goal, (Flee, Recall, Recover)):
                        self.set_goal(Flee("an unseen stat drainer"))
                elif w.monsters and w.in_dungeon:
                    n = self.drains_here[1] + 1 if self.drains_here[0] == w.level_t else 1
                    self.drains_here = (w.level_t, n)
                    mine = 110 + int(w.ind.get("speed", [0])[0] or 0)
                    weak = [r for *_, r in w.adjacent_monsters() if r.drains and "NEVER_MOVE" not in r.flags
                            and "UNIQUE" not in r.flags and r.level <= w.clvl - 5 and r.speed <= mine]
                    if n >= 2 and weak and not isinstance(self.goal, (Flee, Recall, Recover, Hunt)):
                        # A weak drainer beside us: walking away hands it more bites
                        # (mission 19: the flee bumped walls while a Giant red frog
                        # drained STR again; one round of 'hunt' killed it)
                        self.set_goal(Hunt(weak[0].name))
                        self.notify("tactic", f"drained twice on this level by {weak[0].name} (lvl {weak[0].level}, "
                                              "no faster than you) adjacent: killing it rather than walking away")
                    elif n >= 2 and w.find("<>") and not isinstance(self.goal, (Flee, Recall, Recover, Hunt)):
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
        if gnow() < self.busy_until or w.inven_dirty:
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
            not (w.last_stairs_cmd and gnow() - w.last_stairs_cmd[1] < 3) and \
            not self.recall_started(gnow()) and not isinstance(self.goal, Recall)
        if safe or gnow() - self.parking > 300:
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
        self.note_edge_cross()
        # (the M5 set-piece, 10-28: confused 40 s among 26 Hummerhorns with no goal, and nothing happened -- the check
        # lived in step_goal, which returns at once without a goal)
        if not self.w.flag("confused"):
            self.conf_since = None        # (m60: "confused for 1773 s" -- the clock ran on between confusions)
        elif self.w.in_dungeon and (self.w.adjacent_monsters() or self.goal) and self.confusion_lock():
            return
        if self.confusion_window():
            return
        self.supply_watch()
        # the game clock (world.py). The server's rule (xtra2.c base_time_factor, time_factor): 1 in town;
        # 10x resting and 5x running with no awake monster in line of sight -- seen or not
        # (monsters_in_los), so after a fight in the dark it's often 1x (set-piece L2: a 6-s rest at 1x);
        # else 1/5 at or below hitpoint_warn x 10% HP. The model takes the 1/5 (exact, and what matters in
        # a fight) and 1x for resting and running: a clock running fast where the game doesn't would end
        # game timers early (a recall "overdue" and read again cancels it). Only the fuel's measured rate
        # raises it, while resting or running with nothing in view.
        hw = getattr(self, "hpwarn", 0)
        w, m = self.w, self.mover
        hp = w.hp
        slow = hw and hp[1] > 1 and hp[0] * 100 // max(1, hp[1]) <= hw * 10
        # (running: a run under way and the position changing -- the mover's run state also covers the
        # wait for the first step and the stop, and the fuel measured 2-4x over it, not 5x)
        running = (m.running is not None or m.free is not None) and wall_since(w.pos_t) < 0.4
        fast_ok = bool(w.in_dungeon and (w.resting or running) and not w.monsters)
        # (hurt and resting out of sight: 10x or, with an unseen monster awake in sight, 1/5: the lower)
        model = 1.0 if not w.in_dungeon else 0.2 if slow else 1.0
        set_fast_ok(fast_ok)
        if model != model_factor():
            set_time_factor(model)
        # (logged on a new measurement, or a change of the model's factor at most every 5 s: runs
        # start and stop every second or two)
        f, r = time_factor(), measured_rate()
        if r != self.rate_logged or (abs(f - self.factor_logged) > 0.3 * max(f, self.factor_logged)
                                     and wall_since(self.factor_log_t) > 5):
            self.factor_logged, self.rate_logged, self.factor_log_t = f, r, gnow()
            self.log("time_factor", factor=round(f, 2), hp=hp[:2], model=model, measured=r and round(r, 2))
        # fuel readings (a redraw: free, and the server resends the pack): every 2 s while the clock may
        # run fast, every 10 s otherwise (to check the model's 1.0 in the log)
        if self.w.in_dungeon and light_fuel(self.w.inven) is not None and \
                wall_since(self.redraw_t) > (2 if fast_ok else 10):
            self.w.need_redraw = True
        self.note_town_stairs()
        if self.wear_queue:
            self.wear_step()
        self.verify_use()
        self.verify_effects()
        self.learn_flavours_tick(gnow())
        self.track_since()
        w, now = self.w, gnow()
        if w.hp[1] > 1 and (self.hp_min_since is None or w.hp[0] < self.hp_min_since[0]):
            self.hp_min_since = [w.hp[0], w.hp[1]]
        ov = getattr(self.goal, "overridden", None) or getattr(self.resume_after, "overridden", None)
        if ov and w.hp[0] < ov["hp_min"]:
            ov["hp_min"] = w.hp[0]
        # 2. floor items with full names, and what a level was left with (the
        # Advisor's scorecard memo §5.2: abandoned loot had to be reconstructed)
        names = [l.strip()[2:].strip() for l in (w.itemlist or [])[1:]]
        if w.level_t != self.items_level:
            if self.items_level is not None and self.items_last and self.items_depth:
                self.log("left_behind", items=self.items_last, left_depth_ft=self.items_depth)
            self.items_level, self.items_last, self.items_depth = w.level_t, [], w.depth_ft
        if names != self.items_last and w.in_dungeon:
            self.items_last = names
            self.log("itemlist", items=names, depth_ft=w.depth_ft)
        # Full resync from the server after a level change or a loss (the
        # game-state survey, 2026-10-03: the client's copy is right, ours drifts)
        # Never inside a store, nor during a shop goal: the server's redraw
        # silently closes the store (net-game.c recv_redraw sets store_num = -1,
        # no store_leave), and a purchase after that reads store[-1] -- it
        # crashed the test server in mission 21 and would crash a live one
        shopping = w.store is not None or isinstance(self.goal, Shop) or now - getattr(w, "store_t", 0) < 3
        if (w.need_redraw or self.redraw_level != w.level_t) and wall_since(self.redraw_t) > 2 and not shopping:
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
        if w.in_dungeon and w.itemlist:
            for line in w.itemlist[1:]:
                name = line.strip()[2:].strip()
                junk = [j.strip().lower() for j in self.orders.get("junk", "").split(",") if j.strip()]
                known_junk = "{cursed" in name or any(j in name.lower() for j in junk) or \
                    self.junk_kinds.get(kind_key(name)) or (self.flavours.get(flavour_key(name)) or {}).get("junk")
                if re.search(r"\b(Wand|Staff|Rod|Ring|Amulet)\b|\{(excellent|special)", name) and \
                        not known_junk and (w.level_t, name) not in self.far_seen:
                    self.far_seen.add((w.level_t, name))
                    # (mission 15: the user spotted a Wand of Slow Monster 33 squares
                    # away, outside loot_radius; it sold for 210). Held 2.5 s: often
                    # the pilot is already stepping onto it (mission 18's amulet was in
                    # the pack before the Navigator could look)
                    self.item_pending.append((now + 2.5, w.level_t, name, line.strip()[:1], now))
        for pend in list(self.item_pending):
            due, lt, name, glyph, first = pend
            if now < due:
                continue
            self.item_pending.remove(pend)
            bare = re.sub(r"^(an?|the|\d+) ", "", name.lower())
            if lt != w.level_t or any(bare in i["name"].lower() for i in w.items() + w.items(equip=True)):
                continue
            # one like it within loot_radius: the pilot fetches it itself; wait
            # up to 10 s (mission 20's Quartz Ring came in 4 s after the alert)
            lr = int(self.orders.get("loot_radius", 0))
            if lr and now - first < 10 and self.orders.get("pickup") == "all" and \
                    any(ch == glyph and w.dist(q) <= lr for q, ch in w.memory.items()):
                self.item_pending.append((now + 1.5, lt, name, glyph, first))
                continue
            # (the squares in the notice itself: m27's Navigator needed a `status full` for each fetch)
            sq = sorted((q for q, ch in w.memory.items() if ch == glyph), key=w.dist)[:3]
            where = ", ".join(f"{q[0]},{q[1]} ({w.dist(q)} away)" for q in sq) or "see 'Item squares' in `status full`"
            # devices and jewellery this close: the loot step fetches them once it's clear (m29: nobody did)
            if lr and self.orders.get("pickup") == "all" and glyph in self.VALUABLE_GLYPHS and sq and \
                    w.dist(sq[0]) <= self.LOOT_VALUABLE_R:
                self.notify("interesting_item", f"{name} seen on this level at {where}: fetching it once the "
                                                 "area is clear", news=True)
                continue
            if not self.plan:
                self.item_hold_until = now + 20   # (a dive pauses so you can fetch it)
            self.notify("interesting_item", f"{name} seen on this level (devices and jewellery sell for 50-700 once "
                                             f"known): a '{glyph}' at {where}; `goal fetch Y,X`"
                                             + ("" if self.plan else ". A dive pauses 20 s for it"))
        while w.losses:
            t, text = w.losses.pop(0)
            self.notify("lost", text, news=True)
        self.audit_tick(now)
        self.structures_tick(now)
        # the Navigator's avoid zones, as squares the planner won't enter
        zone = set()
        for y0, x0, r in self.avoid_zones.get(w.level_t, []):
            zone |= {(y0 + dy, x0 + dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1)}
        for y0, x0, rc in w.monsters:
            if any(n in rc.name.lower() for n in self.avoid_names):
                zone |= {(y0 + dy, x0 + dx) for dy in range(-3, 4) for dx in range(-3, 4)}
        w.avoid_inside = w.pos in zone
        w.avoid_zone = zone - {w.pos}
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
                # (not for the bank's own trip to the house tile: m57 read it as the Pilot wandering off)
                banking = isinstance(self.goal, HouseBank) or isinstance(getattr(self.goal, "sub", None), HouseBank)
                if len(self.wild_trail) == 1 and not banking:
                    self.notify("left_town", f"walked off the town map into the wilderness ({w.depth_ft} ft); "
                                             "'goal town' walks back")
        if w.in_dungeon and w.monsters and now - self.mons_log_t >= 1.0:
            # a steady record for replays (post-mortem memo §4.6: an 86 s gap
            # before the mission-7 death)
            self.mons_log_t = now
            # + the server's health bar of the tracked monster (indicator "track":
            # colour, length in tenths; xtra1.c health_redraw) and the monster we
            # last hit, which is usually the tracked one (the Advisor, 10-09: no
            # monster HP in the logs, so nobody could tell how close Brodda was)
            hit = next((m.group(1) for ts, t in reversed(w.messages) if now - ts < 5
                        for m in [re.match(r"You (?:hit|smite|bite|claw|miss) (?:the )?(.+?)[.!]$", t)] if m), None)
            self.log("mons", monsters=[(y, x, r.name) for y, x, r in w.monsters],
                     track=w.ind.get("track"), fighting=hit)
        self.belief_tick(now)
        self.watch_character()
        if now - self.weapons_t > 10:
            self.weapons_t = now
            self.watch_weapons()
        self.watch_breeders()
        self.watch_drainers()
        self.watch_thieves()
        self.watch_kills()
        self.watch_band()
        self.watch_traps()
        self.watch_abilities()
        self.watch_progress()
        self.watch_perception()
        if self.w.recall_cancelled:
            self.w.recall_cancelled = False
            self.notify("recall_cancelled", "a Word of Recall was cancelled (a second one was read): no recall is pending now")
        self.recall_memory()
        self.shadow_results()
        self.handle_requests()
        if not self.running:
            return
        # The test server's time freeze: nothing happens in the game, so act on nothing (commands sent now would
        # queue and run on stale reasons when it thaws); requests are still answered
        if frozen():
            if not getattr(self, "frozen_said", False):
                self.frozen_said = True
                self.mover.stop()
                self.notify("time_frozen", "time is frozen on the test server: the Pilot holds until it's thawed")
            return
        if getattr(self, "frozen_said", False):
            self.frozen_said = False
            self.notify("time_frozen", "time flows again: the Pilot carries on", news=True)
        # who each action is for (the user, 10-25: "when does the Navigator act vs the Pilot?"): stamped as `by` on
        # every act and goal record and shown in the viewer -- pilot (reflexes, policy, idle), plan (the Navigator's
        # plan town / plan trip, run by the Pilot), nav (a goal the Navigator gave directly), arch (the Architect)
        self.acting = "pilot"
        if self.reflexes():
            return
        if self.parking and not isinstance(self.goal, Recall):
            self.park_tick()
            return
        if self.rule_tick(gnow()):        # the Navigator's executable standing orders (`react`)
            return
        self.look_tick(gnow())            # (never acts: asks the server which monsters are asleep)
        if self.policy_tick(gnow()):      # the Pilot's own item work, at safe moments
            return
        self.acting = self.goal_origin(self.goal)
        if self.step_goal():
            self.acting = "plan"
            self.plan_tick(now, False)
            return
        self.acting = "plan"
        if self.plan_tick(now, True):
            return
        self.acting = "pilot"
        self.idle()

    def goal_origin(self, g):
        """Who a goal acts for: the plan's goals and the Navigator's plan town -> plan; another goal the Navigator or
        the Architect gave -> nav / arch; the Pilot's own (flee, recover, recall by reflex...) -> pilot."""
        if g is None:
            return "pilot"
        if getattr(g, "by_plan", False) or isinstance(g, TownKit):
            return "plan"
        role = getattr(g, "role", None)
        return {"navigator": "nav", "architect": "arch"}.get(role, "pilot")

    # --- control requests (from the socket thread) ---------------------------

    def handle_requests(self):
        while True:
            try:
                req, reply = self.requests.get_nowait()
            except queue.Empty:
                return
            if req.get("cmd") not in ("viewmap", "view", "navview", "note", "goalstate", "mission"):
                # (only the Navigator's own commands count as activity: the viewer's
                # twice-a-second polls kept town_light from ever taking the lantern
                # off, and idling in town burned 7300 turns + 3 flasks, 2026-10-16)
                self.last_agent = gnow()
                # the Navigator's commands as received (latency studies could only
                # see the next recorded order: the Advisor)
                rid, rt = self.last_report
                self.log("nav_cmd", cmd=req.get("cmd"), args=req.get("args", [])[:12], role=req.get("role", "navigator"),
                         wait_report=bool(req.get("since_wait")), after_report=rid,
                         report_age=round(gnow() - rt, 1) if rt else None)
            self.acting = "arch" if req.get("role") == "architect" else "nav"
            try:
                out = self.do_request(req)
            except Exception as e:
                out = {"ok": False, "error": repr(e)}
            self.acting = "pilot"
            if self.unanswered and isinstance(out, dict) and req.get("cmd") not in ("note", "say", "status"):
                # on every answer, not only wait/status (mission 16: 'Pause 1 sec'
                # was seen 35 s late, during chest commands)
                out["user_messages"] = [f"{time.strftime('%H:%M:%S', _lt(t))} {m}"
                                        for t, m in self.unanswered]
            reply.put(out)

    def service_notes(self):
        """Take the user's notes out of the request queue now, from inside a
        long agent command (search 20, chest work, pack re-reads): they queued
        behind it. True if one came in."""
        with self.requests.mutex:
            notes = [r for r in self.requests.queue if r[0].get("cmd") == "note"]
            for r in notes:
                self.requests.queue.remove(r)
        for req, reply in notes:
            try:
                out = self.do_request(req)
            except Exception as e:
                out = {"ok": False, "error": repr(e)}
            reply.put(out)
        return bool(notes)

    ACTIONS = {"wear": "w", "takeoff": "t", "quaff": "q", "read": "r", "eat": "E", "fuel": "F",
               "destroy": "k", "drop": "d", "inspect": "I", "aim": "a", "use": "u", "zap": "z"}

    def item_index(self, letter, equip=False, pack_only=False):
        """Inventory letter (a, b, ...) as in the report, or part of an item's
        name (spaces as '_'; resolved now, so it can't go stale) -> item index."""
        if len(letter) == 1 and letter.isalpha():
            # Equipment letters: A, B, ... in the order `equip` lists it (and
            # lowercase for takeoff, which only works on equipment); mission 22
            # couldn't take off or inspect a worn ring by letter
            if letter.isupper() or (equip and pack_only is False and self.equip_letters_lower):
                eq = self.w.items(equip=True)
                k = ord(letter.lower()) - ord("a")
                if not 0 <= k < len(eq):
                    raise ValueError(f"no equipment item {letter} (`equip` lists them)")
                return eq[k]["item"]
            return ord(letter) - ord("a")
        if letter.isdigit():
            return int(letter)
        name = letter.replace("_", " ").lower()
        pool = self.w.items() if pack_only else \
            self.w.items(equip=True) + self.w.items() if equip else self.w.items() + self.w.items(equip=True)
        hits = [i for i in pool if name in i["name"].lower()]
        if not hits:
            # "Flask of oil" for "4 Flasks of oil" (mission 17)
            hits = [i for i in pool if singular(name) in singular(i["name"])]
        if not hits:
            raise ValueError(f"nothing in the pack matches '{letter}'" if pack_only else f"no item matching '{letter}'")
        if len(hits) > 1:
            # whole-word matches first ("Light" = the Scroll of Light, not Cure
            # Light Wounds: mission 16 destroyed 14 CLW that way)
            words = [i for i in hits if re.search(r"\b" + re.escape(name) + r"\b", i["name"].lower())
                     and not re.search(r"\w " + re.escape(name) + r" \w", i["name"].lower())]
            if len(words) == 1:
                return words[0]["item"]
            # two stacks of the same unknown kind (they don't merge while their
            # hidden pluses differ: mission 22's two Bloodstone Rings): the first
            same = {re.sub(r"^(an?|\d+) ", "", i["name"]) for i in hits}
            if len(same) == 1:
                return hits[0]["item"]
            raise ValueError(f"'{letter}' matches {len(hits)} items: " + "; ".join(
                f"{chr(97 + i['item'])}) {i['name']}" for i in hits) + ": use the letter or a longer name")
        return hits[0]["item"]

    def pack_now(self, wait=0.7):
        """Re-read the pack right after an action (the report lagged behind a
        batch of destroys, and the Navigator then acted on stale letters)."""
        self.c.collect(wait)
        self.service_notes()
        self.w.drain()
        self.w.inven = self.c.inven()
        self.w.inven_t = gnow()
        self.w.inven_dirty = False
        return [f"{chr(97 + i['item'])}) {i['name']}" for i in self.w.items()]

    # In the dungeon the Pilot handles items itself (restructure step 2, the user's
    # hybrid: item commands for the Navigator in town only, between trips)
    # (destroy and drop are allowed in the dungeon since 10-26 -- dungeon pack control, the user: the pack fills ~10
    # minutes into a trip; the value refusals and the debt rules apply as in town)
    DUNGEON_ITEM_CMDS = {"wear", "takeoff", "pickup", "fuel", "eat", "inscribe", "wearall"}

    def do_request(self, req):
        c = req.get("cmd")
        args = req.get("args", [])
        self.req_role = req.get("role", "navigator")
        if self.req_role != "architect" and self.w.in_dungeon and (
                c in self.DUNGEON_ITEM_CMDS or
                (c in ("read", "use") and len(args) > 1 and args[1] != "force")):      # identify-type reads
            return {"ok": False, "error": f"in the dungeon the Pilot handles items itself (pickup, identify, "
                                          f"wear upgrades, fuel, eat): `{c}` is for town, between trips. You may "
                                          "`destroy`/`drop` junk, and `order nopickup=NAME,...` keeps kinds out. To "
                                          "protect an item from its policy use `keep NAME`"}
        if self.req_role != "architect" and (c in ("raw", "stairs") or (c == "goal" and args[:1] == ["goto"])):
            # the new toolset (restructure step 2.6): movement is the Pilot's; the Navigator
            # gives intents (`goal leave` for the stairs, `goal fetch Y,X` for an item)
            return {"ok": False, "error": f"`{c}{' goto' if c == 'goal' else ''}` is the Pilot's now: use `goal leave` "
                                          "(this level, by the nearest stairs), `goal fetch Y,X` (one item), "
                                          "`plan trip ...` or `goal dive FEET`"}
        if self.req_role != "architect":
            held = self.stale_order(c, args)
            if held:
                self.log("order_held", cmd=c, args=args[:6], why=held)
                return {"ok": False, "error": f"order held: {held}"}
        if c == "status":
            full = "full" in args
            if req.get("since_wait"):
                # a wait report: the news since the previous wait (the survey)
                since, self.news_wait_t = self.news_wait_t, gnow()
                rep = self.numbered(self.compact(news_since=since), "wait")
                self.nav_view = (time.time(), self.nav_view_events, rep)
                return {"ok": True, "report": rep}
            rep = self.numbered(self.report() if full else self.compact(snapshot=True), "full" if full else "status")
            self.nav_view = (time.time(), [], rep)
            return {"ok": True, "report": rep}
        if c == "mission":
            # mission_start / mission_end markers with the Navigator's model (the
            # Advisor's scorecard memo §5.5); also kept in runs/missions.json
            if not args or args[0] not in ("start", "end"):
                return {"ok": False, "error": "usage: mission start LABEL [navigator=MODEL] [effort=LEVEL] [notes=TEXT] | "
                                              "mission end [LABEL]"}
            kv = dict(a.split("=", 1) for a in args[1:] if "=" in a)
            label = next((a for a in args[1:] if "=" not in a), None) or getattr(self, "mission_label", None)
            if not label:
                return {"ok": False, "error": "which mission? (mission start LABEL ...)"}
            path = os.path.join(os.path.dirname(os.path.dirname(self.rundir.rstrip("/"))), "missions.json")
            try:
                ms = json.load(open(path))
            except (OSError, ValueError):
                ms = []
            nick = os.path.basename(self.rundir.rstrip("/"))
            stamp = time.strftime("%Y-%m-%d %H:%M")
            if args[0] == "start":
                self.mission_label = label
                # (the report's mission total: m25's Navigator had only the 10-minute rates)
                self.mission_base = (gnow(), (self.w.ind.get("exp") or [0])[0], self.w.ind.get("gold", [0])[0],
                                     self.__dict__.get("gold_found", 0))
                self.save_mission()
                self.log("mission_start", label=label, version=VERSION, **kv)
                ms = [m for m in ms if m.get("label") != label] + [
                    {"label": label, "nick": nick, "start": stamp, "end": None, "navigator": kv.get("navigator"),
                     "effort": kv.get("effort"), "report": "compact", "notes": kv.get("notes", ""),
                     "version": VERSION}]
            else:
                self.log("mission_end", label=label, **kv)
                for m in ms:
                    if m.get("label") == label:
                        m["end"] = time.strftime("%Y-%m-%d %H:%M", _lt(gnow() + 59))
                self.mission_label = None
                try:
                    os.remove(os.path.join(self.rundir, "mission.json"))
                except OSError:
                    pass
            with open(path, "w") as f:
                json.dump(ms, f, indent=1)
            return {"ok": True, "text": f"mission {args[0]}: {label} at {stamp}"}
        if c == "keep":
            # protect an item from the value policy and from the Navigator's own
            # sells/destroys (`keep -NAME` releases; `keep` lists)
            if not args:
                return {"ok": True, "text": "kept: " + (", ".join(sorted(self.keep)) or "nothing")}
            name = " ".join(args).replace("_", " ").lower()
            if name.startswith("-"):
                self.keep.discard(name[1:].strip())
            else:
                self.keep.add(name.strip())
            json.dump(sorted(self.keep), open(os.path.join(self.rundir, "keep.json"), "w"))
            return {"ok": True, "text": "kept: " + (", ".join(sorted(self.keep)) or "nothing")}
        if c == "standing":
            # standing instructions shown in every report (the Advisor's belief-state table:
            # "don't kill the Rot jelly"); `standing -N` removes one, `standing` lists them
            if args and re.fullmatch(r"-\d+", args[0]):
                i = int(args[0][1:]) - 1
                if not 0 <= i < len(self.standing):
                    return {"ok": False, "error": f"no standing instruction {i + 1}"}
                gone = self.standing.pop(i)
            elif args:
                self.standing.append({"text": " ".join(args), "by": self.req_role,
                                      "t": time.strftime("%Y-%m-%d %H:%M")})
            json.dump(self.standing, open(os.path.join(self.rundir, "standing.json"), "w"), indent=1)
            return {"ok": True, "text": "standing: " + ("; ".join(f"{i + 1}. {x['text']} ({x['by']})"
                                                                for i, x in enumerate(self.standing)) or "none")}
        if c == "react":
            # executable standing orders (the user, 10-26): `react KIND ARG`, `react -N`, `react clear`, `react`
            # (not `rule`: pilotctl answers that one itself, the Advisor's rulebook)
            rl = self.rules()
            if args and args[0] == "clear":
                rl.clear()
            elif args and re.fullmatch(r"-\d+", args[0]):
                i = int(args[0][1:]) - 1
                if not 0 <= i < len(rl):
                    return {"ok": False, "error": f"no reaction {i + 1}"}
                rl.pop(i)
            elif args:
                kind, arg = args[0], " ".join(args[1:]).replace("_", " ").lower().strip()
                if kind not in self.RULE_KINDS or not arg:
                    return {"ok": False, "error": "usage: react leave NAME | react hunt NAME | react thieves kill | "
                                                  "react afraid teleport | react -N | react clear. " +
                                                  "; ".join(f"{k}: {v}" for k, v in self.RULE_KINDS.items())}
                if kind in ("leave", "hunt") and not any(r.name.lower() == arg for r in self.w.g.races.values()):
                    return {"ok": False, "error": f"no monster named {arg!r} (use the name `monster` shows)"}
                if (kind, arg) in {("thieves", "kill"), ("afraid", "teleport")} or kind in ("leave", "hunt"):
                    # (m58: `react thieves kill` listed three times -- the same reaction isn't added twice)
                    if not any(r["kind"] == kind and r["arg"] == arg for r in rl):
                        rl.append({"kind": kind, "arg": arg, "by": self.req_role, "t": time.strftime("%Y-%m-%d %H:%M")})
                else:
                    return {"ok": False, "error": f"react {kind} takes: " + self.RULE_KINDS[kind]}
            self.save_rules()
            return {"ok": True, "text": "reactions: " + ("; ".join(f"{i + 1}. {r['kind']} {r['arg']} ({r['by']})"
                                                               for i, r in enumerate(rl)) or "none")}
        if c == "review":
            # the item-review queue (the user, 10-26): items held for the Navigator's word before they're sold
            st = self.review_state()
            if not args:
                return {"ok": True, "text": "review: " + ("; ".join(f"{n} ({v['why']})" for n, v in st["items"].items())
                                                          or "nothing held")}
            if args[0] not in ("sell", "keep", "wear") or len(args) < 2:
                return {"ok": False, "error": "usage: review | review sell|keep|wear NAME"}
            frag = " ".join(args[1:]).replace("_", " ").lower()
            name = next((n for n in st["items"] if frag in n.lower()), None)
            if not name:
                return {"ok": False, "error": f"nothing held matches {frag!r}: " + ", ".join(st["items"])}
            st["items"].pop(name)
            st["decided"][name] = "sell" if args[0] == "sell" else "keep"
            self.review_save()
            if args[0] == "keep":
                self.keep.add(re.sub(r"^(an?|\d+) ", "", re.sub(r"\s*\{[^}]*\}", "", name)).lower())
                json.dump(sorted(self.keep), open(os.path.join(self.rundir, "keep.json"), "w"))
            if args[0] == "wear":
                # (recorded as keep; worn now only in town -- `wear` is for town, between trips: DUNGEON_ITEM_CMDS. It
                # said "-> wear" and in the dungeon wore nothing: refactor-candidates A11)
                it = next((i for i in self.w.items() if i["name"] == name), None)
                if self.w.in_dungeon:
                    return {"ok": True, "text": f"review: {name} -> kept, NOT worn: in the dungeon the Pilot handles "
                                                f"items itself. `wear` it in town, between trips"}
                if not it:
                    return {"ok": True, "text": f"review: {name} -> kept, NOT worn: it isn't in the pack"}
                self.cmd(f"custom w item={it['item']}", f"wear {name} (your review)", hold=0.8)
                return {"ok": True, "text": f"review: {name} -> kept; wearing it now"}
            return {"ok": True, "text": f"review: {name} -> {args[0]}"}
        if c == "debt":
            e = self.debt.get("entries", [])
            fe = self.debt.get("fight_entries", [])
            return {"ok": True, "text": f"Navigator debt: {self.debt_total()} gold of value lost over the Pilot's value "
                                        f"policy ({len(e)} entries)" + "".join(f"\n  {x['t']} {x['gold']}: {x['what']} "
                                                                                f"({x['why']})" for x in e[-8:]) +
                                        f"\nFight debt: {self.fight_debt_total()} HP lost in hunts ordered over the "
                                        f"Pilot's refusal that went wrong ({len(fe)} entries)" +
                                        "".join(f"\n  {x['t']} {x['hp']} HP: {x['what']} ({x['why']})" for x in fe[-8:])}
        if c == "pack":
            return {"ok": True, "text": "Pack: " + "; ".join(f"{chr(97 + i['item'])}) {self.short(self.show(i))}"
                                                           for i in self.w.items())}
        if c == "equip":
            return {"ok": True, "text": "Equipment (use these letters, capitals, in item commands): " + "; ".join(
                f"{chr(65 + k)}) {self.short(i['name'])}" for k, i in enumerate(self.w.items(equip=True)))
                    + "\n" + self.gear_line()}
        if c == "orders":
            return {"ok": True, "text": "Orders: " + ", ".join(f"{k}={v}" for k, v in self.orders.items())}
        if c == "map":
            w = self.w
            r = int(args[0]) if args and args[0].isdigit() else 15
            if not (w.rows and w.pos):
                return {"ok": False, "error": "no map yet"}
            y0, x0 = w.pos
            ys = range(max(0, y0 - r), min(len(w.rows), y0 + r + 1))
            xa = max(0, x0 - r)
            return {"ok": True, "text": f"Map (@ {y0},{x0}; rows {ys[0]}-{ys[-1]}, cols {xa}-{x0 + r}):\n"
                    + "\n".join(f"{y:2d}|" + w.rows[y][xa:x0 + r + 1].rstrip() for y in ys)}
        if c == "view":
            # (the observer's viewer: a bigger map, no side effects)
            rows = int(args[0]) if args else 11
            cols = int(args[1]) if len(args) > 1 else 33
            return {"ok": True, "report": self.report(rows=rows, cols=cols, news_since=gnow() - 600)}
        if c == "navview":
            # what the Navigator last saw (the user's "Navigator's view" panel)
            return {"ok": True, "t": self.nav_view[0], "events": self.nav_view[1], "report": self.nav_view[2]}
        if c == "avoid":
            # the Navigator's no-go zones (the user, mission 16): 'avoid Y,X [R]'
            # (this level), 'avoid NAME' (keep 3 squares from that monster, all
            # levels), 'avoid clear', 'avoid' to list
            w = self.w
            if args[:1] == ["clear"]:
                self.avoid_zones, self.avoid_names = {}, set()
                return {"ok": True, "text": "avoid zones cleared"}
            if args:
                m = re.match(r"^(\d+)[ ,](\d+)$", args[0])
                if m:
                    r = int(args[1]) if len(args) > 1 else 3
                    self.avoid_zones.setdefault(w.level_t, []).append((int(m.group(1)), int(m.group(2)), r))
                else:
                    self.avoid_names.add(" ".join(args).replace("_", " ").lower())
            here = self.avoid_zones.get(w.level_t, [])
            return {"ok": True, "text": "avoiding: " + "; ".join([f"{y},{x} r{r}" for y, x, r in here]
                                                                 + sorted(self.avoid_names)) if here or self.avoid_names
                    else "no avoid zones"}
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
        if c == "journal":
            # the Navigator's journal line, stamped with the real time, depth
            # and HP (its own times were guesses), appended to navigator.md and
            # logged here, so the viewer and notes.py show it in sequence
            w = self.w
            where = "town" if not w.depth else f"{w.depth_ft}ft"
            line = f"- {time.strftime('%H:%M:%S')} {where} {round(100 * w.hp_frac)}% | " + " ".join(args)
            with open(os.path.join(self.rundir, "navigator.md"), "a") as f:
                f.write(line + "\n")
            self.log("nav_journal", text=line[2:])
            return {"ok": True, "text": "journaled: " + line[2:]}
        if c == "gate":
            # the supply gate as a check: 'gate FEET [recall]'
            try:
                ft = int(args[0])
            except (IndexError, ValueError):
                return {"ok": False, "error": "usage: gate FEET [recall]"}
            gap = self.supply_gate(ft, "recall" in args[1:])
            return {"ok": True, "text": f"supplies for {ft} ft: " + ("OK" if not gap else "missing " + "; ".join(gap))}
        if c == "complain":
            # what the Navigator lacks or what gets in its way (not its own
            # mistakes): the user's complaints channel. 14 missions without a
            # clock never reached the user because they were filed as slips.
            w = self.w
            text = " ".join(args).strip()
            if not text:
                return {"ok": False, "error": "usage: complain TEXT (what you lacked / what got in your way)"}
            where = "town" if not w.depth else f"{w.depth_ft}ft"
            nick = os.path.basename(self.rundir.rstrip("/"))
            line = f"- {time.strftime('%Y-%m-%d %H:%M:%S')} {nick} {where} (Navigator): {text}"
            # runs/complaints.md (rundir is runs/pilot/<nick>)
            path = os.path.join(os.path.dirname(os.path.dirname(self.rundir.rstrip("/"))), "complaints.md")
            new = not os.path.exists(path)
            with open(path, "a") as f:
                if new:
                    f.write("# Complaints: what the agents lacked or what got in their way\n\n"
                            "Appended by `pilotctl complain` (Navigators) and by hand (Advisor, Clerks). The\n"
                            "Architect reviews this after every mission and relays recurring or unfixable ones\n"
                            "to the user.\n\n")
                f.write(line + "\n")
            self.log("nav_complaint", text=text)
            return {"ok": True, "text": "complaint logged (runs/complaints.md); the Architect reviews it after the mission"}
        if c == "say":
            # the Navigator answering the user (shown in the observer's viewer)
            text = " ".join(args)
            self.log("nav_say", text=text)
            self.unanswered = []                  # (answered)
            with open(os.path.join(self.rundir, "commentary.jsonl"), "a") as f:
                f.write(json.dumps({"t": round(time.time(), 3), "who": "navigator", "note": text}) + "\n")
            return {"ok": True, "text": "said"}
        if c == "ask":
            return self.ask_architect(" ".join(args))
        if c == "answer":
            return self.answer_navigator(args)
        if c == "price":
            return {"ok": True, "text": self.price_info(" ".join(args))}
        if c == "monster":
            return {"ok": True, "text": self.monster_info(" ".join(args).replace("_", " "))}
        if c == "drainers":
            return {"ok": True, "text": self.drainers_info(args)}
        if c == "gear":
            return {"ok": True, "text": self.gear_review()}
        if c == "gearcmp":
            # the item slot evaluator (geareval.py): each named pack item (letter or name) or item name against the
            # worn slot; no argument: every identified wearable in the pack
            if self.w.in_dungeon and self.w.monsters:
                return {"ok": False, "error": "gearcmp runs ~1-3 s of simulation: not with monsters in view -- "
                                              "`goal quiet` first (it waits somewhere clear), then gearcmp"}
            pack = self.w.items()
            items = []
            for a in args or []:
                a2 = a.replace("_", " ")
                if len(a2) == 1 and a2.islower():
                    try:
                        idx = self.item_index(a2)
                    except ValueError as e:
                        return {"ok": False, "error": str(e)}
                    it = next((i for i in pack if i["item"] == idx), None)
                else:
                    it = next((i for i in pack if a2.lower() in i["name"].lower()), None) or a2
                if it:
                    items.append(it)
            if not args:
                items = [i for i in pack if i["tval"] in geareval.SLOT_OF_TVAL and i["tval"] != TV_LITE and
                         self.iv(i["name"]).known]
            if not items:
                return {"ok": True, "text": "nothing to compare (name pack items by letter or name, or an item name)"}
            try:
                res = self.gear_eval(items, n=20)
            except Exception as e:
                return {"ok": False, "error": f"gear evaluator failed: {e!r}"}
            return {"ok": True, "text": geareval.report(res)}
        if c == "house":
            return self.house_info(args)
        if c == "loadout":
            # the loadout optimizer (geareval.optimize): changes across slots, e.g. a better weapon without Free
            # Action, with Free Action from a ring. `loadout shops` adds the shops' stock as last seen, within the gold
            # the essentials leave
            if self.w.in_dungeon and self.w.monsters:
                return {"ok": False, "error": "loadout runs ~2-5 s of simulation: not with monsters in view -- "
                                              "`goal quiet` first (it waits somewhere clear), then loadout"}
            return {"ok": True, "text": self.loadout_info(shops="shops" in args)}
        if c == "why":
            return {"ok": True, "text": self.why_info(args)}
        if c == "prep":
            return {"ok": True, "text": self.prep_info()}
        if self.dead and c not in ("attention", "quit", "orders", "map", "note", "view", "say", "viewmap",
                                   "journal") and \
                not (c == "goal" and args[:1] == ["resurrect"]):
            return {"ok": False, "error": "the character is dead (a ghost): only 'goal resurrect' works"}
        if c == "goal":
            return self.request_goal(args)
        if c == "plan":
            return self.request_plan(args)
        if c == "stop":
            self.set_goal(None)
            self.stop_resting()
            if self.plan:
                self.log("plan_end", plan=self.plan.text, status="stopped")
                self.plan = None
                self.clear_plan_file()
                return {"ok": True, "note": "the trip plan is stopped too"}
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
            # `destroy !NAME`: over the value policy (counted in the Navigator's debt)
            forced_cmd = args[0].startswith("!") and len(args[0]) > 1
            if forced_cmd:
                args = [args[0][1:]] + list(args[1:])
            # a name of several words: `destroy Ration of Food` sent "of" as the count (m25: "You destroy no
            # more Rations"); only a trailing number, `all` or `force` modifies
            if c in ("destroy", "drop", "quaff", "eat", "fuel", "wear", "takeoff") and len(args) > 1:
                args, tail = list(args), []
                while len(args) > 1 and (args[-1].isdigit() or args[-1] in ("all", "force")):
                    tail.insert(0, args.pop())
                args = [" ".join(args)] + tail
            if c == "fuel" and not any(i["tval"] == TV_LITE for i in self.w.items(equip=True)):
                # The Pilot takes the lantern off when idle in town ("You are not
                # wielding a light", mission 17): put it on first, then find the
                # flask again (the letters shift when the lantern leaves the pack)
                lan = next((i for i in self.w.items(tval=TV_LITE) if "Lantern" in i["name"]), None)
                if not lan:
                    return {"ok": False, "error": "no lantern worn or in the pack to fuel"}
                try:
                    was = next(i["name"] for i in self.w.items() if i["item"] == self.item_index(args[0], pack_only=True))
                except (ValueError, StopIteration) as e:
                    return {"ok": False, "error": str(e) or f"no item '{args[0]}'"}
                self.cmd(f"custom w item={lan['item']}", "agent: fuel: wear the lantern first", hold=0.6)
                self.pack_now(1.0)
                again = next((i for i in self.w.items() if i["name"] == was), None)
                if not again:
                    return {"ok": False, "error": f"wore the lantern, but can't find '{was}' in the pack now"}
                args = [chr(97 + again["item"])] + list(args[1:])
            try:
                if c in ("destroy", "drop", "quaff", "read", "eat", "fuel") and not \
                        (len(args[0]) == 1 or args[0].isdigit()):
                    # by name: only the pack (a name that matched nothing there once
                    # fell through to the equipment -- "You destroy (nothing)"), and
                    # through item_index's ambiguity check (the Advisor's mission 16
                    # replay: this branch still took the first substring match)
                    item = self.item_index(args[0], pack_only=True)
                else:
                    self.equip_letters_lower = c == "takeoff"
                    try:
                        item = self.item_index(args[0], equip=(c == "takeoff"))
                    finally:
                        self.equip_letters_lower = False
            except ValueError as e:
                return {"ok": False, "error": str(e)}
            extra = ""
            iname0 = next((i["name"] for i in self.w.inven if i["item"] == item), "")
            if c in ("read", "use") and re.search(r"Teleport|Phase Door", iname0) and "force" not in args[1:] and \
                    not waited(getattr(self, "escape_read_t", -99.0), 3.0):
                # (m30: the Navigator read a second Teleportation 2 s after the first landed, back beside the hounds)
                return {"ok": False, "error": "an escape was read less than 3 s ago and may still be landing: look "
                                              "again (`status`), or add 'force'"}
            if c == "read" and "Word of Recall" in iname0 \
                    and self.recall_started(gnow()) and "force" not in args[1:]:
                return {"ok": False, "error": "a recall is already under way: reading another cancels it "
                                              "(add 'force' to cancel it on purpose)"}
            iname = next((i["name"] for i in self.w.inven if i["item"] == item), "")
            if c == "read" and "Word of Recall" in iname and self.w.depth == 0 and recall_level(iname) is None \
                    and "force" not in args[1:]:
                return {"ok": False, "error": f"'{iname}' has no valid @R inscription: it would recall to the "
                                              "deepest level ever reached. Inscribe it (inscribe ITEM @R<feet>), "
                                              "use goal recall (it inscribes max_depth), or add 'force'"}
            if c == "wear" and self.req_role != "architect" and "force" not in args[1:]:
                # unknown jewellery: 19-58% of unknown rings are cursed, a cursed one can't come off, and
                # wearing it doesn't identify it (m22 wore a cursed ring; the Advisor's set-piece C7)
                itw = next((i for i in self.w.inven if i["item"] == item), None)
                if itw and itw["tval"] in (40, 45) and (self.unknown_flavour(itw) or self.iv(itw["name"]).known is False):
                    return {"ok": False, "error": f"'{itw['name']}' isn't identified: unknown jewellery is often cursed "
                                                  "(and a cursed ring or amulet can't be taken off). Identify it first "
                                                  "(`plan town` does), or add 'force'"}
            if c in ("destroy", "drop"):
                it0 = next((i for i in self.w.inven if i["item"] == item), None)
                why = self.value_refusal(it0, c) if not forced_cmd else None
                if why:
                    return {"ok": False, "error": f"not {c}ed: {why}. `{c} !NAME` overrides, and adds the value "
                                                  "lost to your debt"}
                if forced_cmd and self.req_role != "architect":
                    if not self.override_allowed():
                        return {"ok": False, "error": f"not {c}ed: your freedom to override the Pilot's value policy "
                                                      f"is suspended (debt {self.debt_total()} gold)"}
                    if self.value_refusal(it0, c):
                        self.add_debt(round(self.iv(it0["name"]).value * self.pay_cut(self.iv(it0["name"]).tval)), it0["name"],
                                      f"{c}ed with ! over the value policy")
                n = args[1] if len(args) > 1 else "1"
                if n == "all":
                    it = next((i for i in self.w.inven if i["item"] == item), None)
                    n = it["number"] if it else 1
                extra = f" value={n}"
                if c == "destroy":
                    self.c.send("confirm yes")
                else:
                    # what we drop stays dropped: auto-pickup and looting skip
                    # this square (pickup=all re-picked dropped items, mission 9)
                    self.skipped_items.add((self.w.level_t, self.w.pos))
            if c in ("aim",):
                extra = f" dir={args[1] if len(args) > 1 else 5}"
            # (a staff that works on an item -- Perception -- takes it the same way:
            # tables.c gives 'u' the same scheme as 'r'; mission 21 identified the
            # flask in slot a twice)
            if c in ("read", "use") and len(args) > 1 and args[1] != "force":
                # A scroll that works on another item (Identify, Enchant...): the
                # client sends that item in the direction byte (COMMAND_SECOND_DIR);
                # without it the server picked the first pack item
                try:
                    target = self.item_index(args[1], equip=True)
                except ValueError as e:
                    return {"ok": False, "error": str(e)}
                extra = f" dir={target}"
                tit = next((i for i in self.w.items() + self.w.items(equip=True) if i["item"] == target), None)
                if tit and self.unknown_flavour(tit):
                    # learn from the server's answer, "In your pack: a Ring of X (q)."
                    # (the pack diff missed a cursed ring autodestroyed at once and
                    # a second Identify read straight after, mission 16)
                    self.id_target = {"t": gnow(), "flavour": flavour_key(tit["name"]),
                                      "letter": None if tit["equip"] else chr(97 + target)}
            t0 = gnow()
            before = (self.effect_sig("pack"), self.effect_sig("equip"))
            it_before = next((i for i in self.w.inven if i["item"] == item), None)
            pos_before = self.w.pos
            self.cmd(f"custom {key} item={item}{extra}", f"agent: {c} {args}")
            pack = self.pack_now()
            # (mission 20: a destroy's reply showed the pack before it landed, and
            # the retry found "nothing matches"): give it up to ~2 s more
            for _ in range(3):
                if c == "inspect" or (self.effect_sig("pack"), self.effect_sig("equip")) != before:
                    break
                pack = self.pack_now(0.6)
            noise = ("You enter a maze", "Looks like", "You feel", "You hear", "You have found")
            said = [t for ts, t in self.w.messages if ts >= t0 and not t.startswith(noise)]
            # (say what was done first: m30's `read Teleportation` worked, but the reply was the pack, and the
            # Navigator read the second scroll by letter 9 s later)
            did = f"{c} {it_before['name'] if it_before else args[0]}"
            if it_before and not it_before.get("equip"):
                kind = re.sub(r"^(an?|\d+) ", "", re.sub(r"\s*\{[^}]*\}", "", it_before["name"]))
                now_n = sum(i["number"] for i in self.w.items() if singular(kind) in singular(i["name"]))
                did += f" ({it_before['number']} -> {now_n} left)"
            if pos_before and self.w.pos and self.w.pos != pos_before:
                did += f"; moved {pos_before} -> {self.w.pos} ({self.w.dist(pos_before)} squares)"
            out = {"ok": True, "did": did, "said": said[-4:], "pack": pack}
            if c in ("use", "aim", "zap") and said:
                pass          # a device's effect is what the game said (an unknown staff shows no charges)
            elif c in ("read", "use") and re.search(r"Teleport|Phase Door", iname0) and \
                    (self.effect_sig("pack"), self.effect_sig("equip")) == before:
                out["note"] = "an escape: its landing can take ~2 s; the status line shows ESCAPE LANDING until we move"
            elif c != "inspect" and (self.effect_sig("pack"), self.effect_sig("equip")) == before:
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
        if c == "search":
            # search the 8 squares around us N times (each search is a turn and
            # finds a given secret door/trap ~14% of the time for Dive04: 15 ~ 90%).
            # Standing still doesn't search (mission 15, the user; cmd1.c search())
            n = max(1, min(40, int(args[0]) if args else 15))
            t0 = gnow()
            for _ in range(n):
                self.c.send("custom s")
            # (the server runs them one a player turn, ~0.65 s, so a move sent sooner waits behind them;
            # busy for longer would hold the emergency reflexes too)
            self.busy_until = gnow() + 0.15 * n
            # wait for the searches to run (one a turn), stop early on a find
            # (mission 16: the reply said "nothing found" while the game had said
            # "You have found a secret door" a few seconds later)
            end = gnow() + min(25.0, 0.7 * n + 1.0)
            found = []
            heard = False
            while gnow() < end and not found:
                self.c.collect(0.5)
                self.w.drain()
                found = [t for ts, t in self.w.messages if ts >= t0 and ("found" in t or "discovered" in t)]
                if self.service_notes() and self.unanswered:
                    heard = True             # the user spoke: answer now (the searches still run)
                    break
            return {"ok": True, "text": f"searched {n} times here: " + ("; ".join(found) if found else
                    "stopped waiting for the result: a user message came in" if heard else "nothing found")}
        if c in ("disarm", "open"):
            # a chest (or door/trap) in direction DIR (5 = the square you stand on):
            # search first to find a chest's trap, disarm it, then open
            d = args[0] if args else "5"
            t0 = gnow()
            self.cmd(f"custom {'D' if c == 'disarm' else 'o'} dir={d}", f"agent: {c} {d}")
            self.c.collect(1.0)
            self.service_notes()
            said = [t for ts, t in self.w.messages if ts >= t0]
            return {"ok": True, "said": said[-4:], "pack": self.pack_now(0.3)}
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
                    "standing_on": self.w.standing_on, "busy": self.busy_until - gnow()}
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
            self.parking = gnow()
            return {"ok": True, "note": "will log out when safe"}
        return {"ok": False, "error": f"unknown command {c}"}

    # The stage table's minimums (HANDBOOK; the Advisor's warrior-progression
    # memo): (from ft, CLW+CSW+CCW, CSW+CCW, CCW, Phase Door)
    SUPPLY_STAGES = ((250, 5, 0, 0, 4), (500, 5, 5, 0, 5), (750, 4, 4, 4, 8))

    def supply_gate(self, target_ft, recall_down):
        """What's missing for going down to target_ft (the Advisor's Navigator-
        decisions memo §3.1: most deaths and near-deaths went down with thin
        cures or no Word of Recall, the risk written in the journal). [] = OK."""
        w = self.w
        if target_ft < 250:
            return []
        def n(word):
            return sum(i["number"] for i in w.items() if word in i["name"])
        clw, csw, ccw = n("Cure Light Wounds"), n("Cure Serious Wounds"), n("Cure Critical Wounds")
        phase, wor = n("Phase Door"), n("Word of Recall")
        stage = max((st for st in self.SUPPLY_STAGES if target_ft >= st[0]), key=lambda st: st[0])
        _, cures, serious, critical, ph = stage
        missing = []
        if clw + csw + ccw < cures:
            missing.append(f"cure potions {clw + csw + ccw}/{cures}")
        if serious and csw + ccw < serious and ccw < 3:
            missing.append(f"CSW+CCW {csw + ccw}/{serious} (or 3 CCW)")
        if critical and ccw < critical:
            missing.append(f"CCW {ccw}/{critical}")
        if phase < ph:
            missing.append(f"Phase Door {phase}/{ph}")
        need_wor = 2 if recall_down else 1
        if wor < need_wor:
            missing.append(f"Word of Recall {wor}/{need_wor}" + (" (one to go, one to come home)" if recall_down else ""))
        # the worn light, or one in the pack (the Pilot takes the lantern off in town)
        def turns(i):
            m = re.search(r"with (\d+) turns", i["name"])
            return int(m.group(1)) if m else 10 ** 6          # no count shown: permanent
        lights = [i for i in w.items(equip=True) if i["tval"] == TV_LITE] + list(w.items(tval=TV_LITE))
        best = max(lights, key=turns, default=None)
        flask = any(i["tval"] == TV_FLASK for i in w.items())
        if not best:
            missing.append("light: none")
        elif turns(best) < 1000 and not (flask and "Lantern" in best["name"]):
            missing.append(f"light: {turns(best)} turns left and no flask" if "Lantern" in best["name"]
                           else f"light: {turns(best)} turns left")
        return missing

    # --- the town kit (restructure step 2.2) ----------------------------------
    STORE_NUM = {"General store": 1, "Armoury": 2, "Weapon Smith": 3, "Temple": 4, "Alchemist": 5,
                 "Magic Shop": 6, "Black Market": 7,
                 # (the rulebook's shop_stock.csv names)
                 "General Store": 1, "Weaponsmith": 3, "Alchemy shop": 5, "Magic-User store": 6, "Black market": 7}
    # (`plan town`'s forecast said "2 Word of Recall at 5", which read like a price)
    STORE_LABEL = {1: "General Store", 2: "Armoury", 3: "Weaponsmith", 4: "Temple", 5: "Alchemist", 6: "Magic Shop",
                   7: "Black Market"}
    # who buys what (store.c store_will_buy), best first; never the Black Market (it pays a third)
    BUYERS = {80: (1,), 39: (1,), 77: (1,), 16: (1, 3), 17: (1, 3), 18: (1, 3), 20: (3, 1), 35: (2, 1),
              30: (2,), 31: (2,), 32: (2,), 33: (2,), 34: (2,), 36: (2,), 37: (2,), 38: (2,),
              19: (3,), 21: (3, 4), 22: (3,), 23: (3,), 75: (5, 4, 6), 70: (5, 4, 6),
              40: (6,), 45: (6,), 55: (6,), 65: (6,), 66: (6,)}
    # kit kinds: (tval, the store that sells them, a price guess before we've seen one)
    KIT_ITEMS = {"Word of Recall": (70, 5, 250), "Cure Critical Wounds": (75, 4, 160),
                 "Cure Serious Wounds": (75, 4, 65), "Cure Light Wounds": (75, 4, 25), "Phase Door": (70, 5, 25),
                 "Identify": (70, 5, 80), "Flask of oil": (77, 1, 5), "Ration of Food": (80, 1, 5),
                 "Restore Strength": (75, 5, 490), "Restore Dexterity": (75, 5, 490),
                 "Restore Constitution": (75, 5, 490), "Restore Charisma": (75, 5, 490),
                 # (the only fear cure kept since Boldness went, the user 10-25; m41 ran out and phased 3 times
                 # afraid with three on it)
                 "Heroism": (75, 4, 55),
                 # (the user, 10-25: Speed drunk at the start of hard fights; only the Black Market sells it, ~383 in
                 # m40; the Advisor's replays: it pays below ~500-600 gold at the rolling XP-per-gold rate)
                 "Potion of Speed": (75, 7, 400)}
    # hard price caps for kit lines (else 1.5x the price last seen): Black Market stock is sometimes far dearer
    KIT_CAP = {"Potion of Speed": 600}     # (450 until 10-26: the user raised it)
    # stock levels per stage (the Advisor's shops memo §3 and the Borg minimums):
    # A to 500 ft, B to 1000 ft, C deeper. No flasks: the town visit tops the lantern up instead (the user,
    # 10-25: oil, food and potions nobody uses fill the pack). Rations: one stack, eaten to Full before a trip
    KITS = {"A": {"Word of Recall": 2, "Cure Light Wounds": 5, "Phase Door": 5, "Ration of Food": 3},
            "B": {"Word of Recall": 2, "Cure Critical Wounds": 4, "Cure Serious Wounds": 4, "Phase Door": 10,
                  "Ration of Food": 3, "Heroism": 3, "Potion of Speed": 2},
            "C": {"Word of Recall": 2, "Cure Critical Wounds": 6, "Cure Serious Wounds": 4, "Phase Door": 12,
                  "Ration of Food": 3, "Heroism": 3, "Potion of Speed": 2},
            "none": {}}
    # The lantern leaves town with this much fuel: a full lantern (15000) burned ~7500 in ~35 dungeon minutes
    # (m29-m30), and a trip ends within 30; a flask adds 7500 (object.txt; FUEL_LAMP 15000, mdefines.h)
    FUEL_TOPUP, FLASK_FUEL = 9000, 7500
    # devices never sold by the kit (the Advisor's rulebook-r3 memo: escapes, travel, detection and
    # mapping, Perception, Stone to Mud, healing)
    USEFUL_DEVICES = ("Teleport", "Recall", "Deep Descent", "Detect", "Door/Stair Location", "Mapping", "Enlightenment",
                      "Perception", "Stone to Mud", "Cure Serious", "Cure Critical", "Curing", "Healing")
    # (only Door/Stair Location of the Location devices: the trip plan uses it on arrival. Treasure and Object
    # Location were never used in 30 missions and held two slots -- the user, 10-25: the pack fills up)
    # (not Cure Light Wounds: ~15-20 HP a charge at 270 HP, a turn each, a pack slot -- the user, m25)
    STAT_FULL = {"STR": "Strength", "DEX": "Dexterity", "CON": "Constitution"}
    RECHARGE_MAX_FAIL = 0.15
    # (the user, 10-28: undo disenchantment with Scrolls of Enchant Armour, "consult the chance of enchantment failure
    # to find a reasonable stopping place". spells2.c enchant(): +1 to-AC succeeds with 1 - table[to_a]/1000 (always
    # below +0, never past +15, halved on artifacts); a failure wastes only the scroll. The table's knee: up to +7 a
    # point costs <= 2 scrolls on average, +8 -> +9 3.3, +9 -> +10 20 -- so enchant while the next point is >= 50%)
    ENCHANT_TABLE = (0, 10, 50, 100, 200, 300, 400, 500, 700, 950, 990, 992, 995, 997, 999, 1000)
    ENCHANT_MIN_CHANCE = 0.5

    def enchant_chance(self, it):
        """The chance a Scroll of Enchant Armour adds +1 to this worn armour piece, or None (no [ac,+a] shown)."""
        m = re.search(r"\[(\d+),([+-]\d+)\]", it["name"])
        if not m or it["tval"] not in self.ARMOUR_SLOTS:
            return None
        to_a = int(m.group(2))
        c = 1.0 if to_a < 0 else 0.0 if to_a > 15 else 1 - self.ENCHANT_TABLE[to_a] / 1000
        return c * (0.5 if self.is_artifact(it["name"]) else 1.0)

    def enchant_plan(self):
        """(worn armour piece, chance) worth a Scroll of Enchant Armour now, the likeliest first."""
        out = [(it, self.enchant_chance(it)) for it in self.w.items(equip=True)]
        return sorted(((it, c) for it, c in out if c is not None and c >= self.ENCHANT_MIN_CHANCE), key=lambda x: -x[1])

    def town_extras_note(self):
        """What plan town may spend beyond the kit and the list (m58: 5025 gold of Enchant Armor, never announced)."""
        bits = []
        n = min(int(round(self.enchant_scrolls_wanted())), int(self.orders.get("enchant_max", 25)))
        if n and self.enchant_plan():
            pr = self.price_of("Enchant Armor", 5) or 190
            bits.append(f"up to {n} Scrolls of Enchant Armor (~{n * pr} gold; `order enchant_max=N` caps it, 0 skips)")
        if self.recharge_wanted():
            bits.append("Scrolls of Recharging for " + ", ".join(i["name"] for i in self.recharge_wanted()))
        return ("; also, as stock allows: " + "; ".join(bits)) if bits else ""

    def enchant_scrolls_wanted(self):
        """Expected scrolls to bring every worn piece to the stopping place (sum of 1/chance per point)."""
        n = 0.0
        for it in self.w.items(equip=True):
            m = re.search(r"\[(\d+),([+-]\d+)\]", it["name"])
            if not m or it["tval"] not in self.ARMOUR_SLOTS:
                continue
            k = 0.5 if self.is_artifact(it["name"]) else 1.0
            for to_a in range(int(m.group(2)), 16):
                c = (1.0 if to_a < 0 else 1 - self.ENCHANT_TABLE[to_a] / 1000) * k
                if c < self.ENCHANT_MIN_CHANCE:
                    break
                n += 1 / c
        return n

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def device_level(kind):
        """object.txt level of a staff or wand kind ('Perception' -> 10), or None."""
        for r in geareval._read_txt(os.path.join(geareval.LIB, "object.txt")):
            if r.get("N") == kind and "I" in r and r["I"][0] in ("55", "65") and "W" in r:
                return int(r["W"][0])
        return None

    def recharge_fail(self, it):
        """The chance a Scroll of Recharging destroys this staff/wand (spells2.c recharge_aux, strength 60, no
        SAFE_RECHARGE: 1 in (160 - level - 10 x charges per item) / 15), or None for a kind we don't know."""
        m = re.search(r"(Staff|Staffs|Wand|Wands) of (.+?) \((\d+) charges?\)", it["name"])
        if not m:
            return None
        lev = self.device_level(m.group(2))
        if lev is None:
            return None
        i = (160 - lev - 10 * (int(m.group(3)) // max(1, it["number"]))) // 15
        return 1.0 if i <= 1 else 1.0 / i

    def recharge_wanted(self):
        """Useful staffs and wands at 0-1 charges per item that a Scroll of Recharging would refill with at most
        RECHARGE_MAX_FAIL risk of destroying them (the user, 10-28: "hopefully it doesn't sell it, but rather it
        recharges it": a Staff of Perception refills 3-8 charges for one ~200-gold scroll, 1 in 10 lost)."""
        out = []
        for it in self.w.items():
            m = re.search(r"\((\d+) charges?\)", it["name"])
            if it["tval"] not in (55, 65) or not m or int(m.group(1)) // max(1, it["number"]) > 1 or \
                    not any(d in it["name"] for d in self.USEFUL_DEVICES):
                continue
            f = self.recharge_fail(it)
            if f is not None and f <= self.RECHARGE_MAX_FAIL:
                out.append(it)
        return out

    def note_store(self):
        """Remember the shop we're in: its owner and the cheapest price per kind."""
        st = self.w.store
        if not st or self.w.store_t <= self.stores_noted_t:
            return
        self.stores_noted_t = self.w.store_t
        num = self.STORE_NUM.get(st.get("name"))
        if not num:
            return
        prices = {}
        for i in st.get("items", []):
            k = self.kind_key_of(i["name"])
            prices[k] = min(prices.get(k, i["price"]), i["price"])
        self.stores_seen[num] = {"owner": st.get("owner"), "t": round(gnow()), "prices": prices}
        try:
            json.dump(self.stores_seen, open(self.stores_file, "w"), indent=1)
        except OSError:
            pass

    @staticmethod
    def kind_key_of(name):
        return singular(re.sub(r"^(an?|\d+) ", "", re.sub(r"\s*\{[^}]*\}", "", name)).strip())

    def price_of(self, kind, store):
        """What `kind` cost at `store` last time we looked (the cheapest line), else a guess."""
        key = singular(kind)
        seen = [v for k, v in (self.stores_seen.get(store) or {}).get("prices", {}).items() if key in k]
        if seen:
            return min(seen)
        return self.KIT_ITEMS.get(kind, (0, 0, None))[2]

    def lantern_fuel(self):
        """Turns of fuel in the lantern (worn, else the best in the pack), or None without one."""
        def fuels(items):
            return [int(m.group(1)) for i in items if "Lantern" in i["name"]
                    for m in [re.search(r"with (\d+) turns", i["name"])] if m]
        worn = fuels(self.w.items(equip=True))      # (not the max of all: a full spare hid a half-empty worn one, m39)
        pack = fuels(self.w.items())
        return worn[0] if worn else max(pack) if pack else None

    def trip_minutes_left(self):
        """How soon this trip should end, in minutes, or None if nobody knows: a Word of Recall under way;
        else the trip plan's time conditions (minutes>N, time>HH:MM) and its 90-minute cap."""
        if self.w.recall_pending:
            return 0.5
        tp = self.plan
        if not tp:
            return None
        left = [90 - (gnow() - tp.t0) / 60]
        for _, var, op, val in tp.conds:
            if var == "minutes" and op in (">", ">="):
                left.append(float(val) - (gnow() - tp.t0) / 60)
            elif var == "time" and op in (">", ">="):
                hh, mm = map(int, val.split(":"))
                lt = time.localtime()
                d = (hh * 60 + mm) - (lt.tm_hour * 60 + lt.tm_min + lt.tm_sec / 60)
                left.append(d + 1440 if d < -720 else d)
        return max(0.0, min(left))

    def provisions_spare(self):
        """Near a trip's end, the spare rations and flasks are no longer needed (the user, 10-25: eat, refill,
        and the rest frees pack slots): Word of Recall under way, or the trip ending within 3 minutes, or
        within 20 while Full (Full is 10000+ food, ~22 dungeon minutes before Hungry; the lantern leaves town
        with 9000+ turns)."""
        left = self.trip_minutes_left()
        return left is not None and (left <= 3 or (left <= 20 and self.w.hunger >= 4))

    def kit_count(self, kind):
        pack = self.w.items()
        if kind == "Ration of Food":
            # (rations only: a Scroll of Satisfy Hunger fills you to just under Gorged, and the next potion
            # tips you over -- speed -10 in m26's worst fight. The scroll is for when you're Weak)
            return sum(i["number"] for i in pack if i["tval"] == TV_FOOD and "Mushroom" not in i["name"])
        tv = self.KIT_ITEMS.get(kind, (None,))[0]
        key = singular(kind)
        n = sum(i["number"] for i in pack if (tv is None or i["tval"] == tv) and key in singular(i["name"]))
        if kind == "Identify":
            # a Staff of Perception's charges count as Identify scrolls
            n += sum(int(m.group(1)) for i in pack if i["tval"] == 55 and "Perception" in i["name"]
                     for m in [re.search(r"\((\d+) charges?\)", i["name"])] if m)
        return n

    def planned_depth(self):
        md = int(self.orders.get("max_depth", 0) or 0)
        deepest = getattr(self, "deepest_ft", 0) or 0
        return min(md, deepest) if md and deepest else (md or deepest)

    def town_buyers(self, it):
        """The shops that buy this item, the best payer first (by owners seen)."""
        stores = self.BUYERS.get(it["tval"], ())
        chr_v = (self.w.ind.get("stat5") or [3])[0]

        def pay(st):
            owner = (self.stores_seen.get(st) or {}).get("owner")
            f = shopmath.factors(re.sub(r"\s*\(.*\)$", "", owner or ""), chr_v) if owner else None
            return -(f[0] if f else 0)
        return sorted(stores, key=lambda st: (pay(st), stores.index(st)))

    # Devices that map or detect for us, and so would hide what exploring by hand gets wrong: on the test server
    # they're sold like loot (the user, 2026-10-24: "too much of a crutch ... in the live server we won't have the
    # rod"); with --live they're kept like any useful device
    CRUTCH_DEVICES = ("Enlightenment", "Detection", "Magic Mapping")

    def is_crutch(self, it):
        return not getattr(self, "live", False) and it["tval"] in (55, 65, 66) and \
            any(k in it["name"] for k in self.CRUTCH_DEVICES)

    def town_sell_count(self, it):
        """How many of this pack item the town kit sells (0: keep it)."""
        name = it["name"]
        if self.is_crutch(it) and not it.get("equip") and self.town_buyers(it):
            return it["number"]
        # (food other than rations, and flasks the lantern doesn't need, are sold: one food source, no oil)
        spare = (it["tval"] == TV_FOOD and "Ration" not in name and "Mushroom" not in name) or \
            (it["tval"] == TV_FLASK and (self.lantern_fuel() or 0) >= self.FUEL_TOPUP)
        # (one lantern is enough -- the user, 10-26: "why two lanterns?" -- the fullest is kept, worn or in the pack;
        # a spare is sold)
        if it["tval"] == TV_LITE and "Lantern" in name and not it.get("equip"):
            others = [i for i in self.w.items(equip=True) + self.w.items() if i["tval"] == TV_LITE and
                      "Lantern" in i["name"] and i["item"] != it["item"]]
            spare = any(self.light_left(o) >= self.light_left(it) for o in others)
        # (a staff doing what a carried rod does is spare: m43 carried a Staff of Door/Stair Location beside the Rod)
        rod_dup = it["tval"] == 55 and any(i["tval"] == 66 and re.sub(r".*\bof ", "", re.sub(r"\s*\(.*", "", i["name"]))
                                           in name for i in self.w.items())
        if it.get("equip") or (it["tval"] in (TV_FOOD, TV_FLASK, TV_LITE) and not spare) or \
                self.is_kit_item(it) \
                or (it["tval"] in (55, 65, 66) and any(d in name for d in self.USEFUL_DEVICES) and not rod_dup
                    and not (it["tval"] in (55, 65) and re.search(r"\(0 charges\)", name)
                             and not any("Recharging" in i["name"] for i in self.w.items())
                             and not any(r["item"] == it["item"] for r in self.recharge_wanted()))) \
                or self.is_kept(name) or \
                re.sub(r"^(an?|\d+) ", "", re.sub(r"\s*\{[^}]*\}", "", name)).lower() in self.ability_sources:
            return 0
        if not self.town_buyers(it) or re.search(r"\{(cursed|worthless|broken|terrible)", name):
            return 0
        if self.unknown_flavour(it):
            # (broke for a Word of Recall: unknown wands, staffs and rods sell anyway -- m27 had nothing to sell but
            # unknown devices and no gold for Identify; jewellery stays)
            if self.unknown_sell_refusal(it, 1) and not (it["tval"] in (55, 65, 66) and self.broke_for_recall()):
                return 0
            f = self.flavour_of(it)
            # one of an unknown stack: the sale teaches the flavour (the rest next pass)
            return it["number"] if (f and f["junk"]) or it["number"] == 1 else 1
        if self.probably_special(name) or self.value_refusal(it, "sell", "navigator"):
            return 0                    # (identify first)
        # (the gear evaluator would wear it: m45 sold a Ring of Strength (+2) right after identifying it, unjudged)
        if self.gear_better(it):
            return 0
        # (a judgement call: held for the Navigator's review)
        if self.review_hold(it):
            return 0
        iv = self.iv(name)
        if iv.kind is None or iv.value <= 0 or iv.value * self.pay_cut(iv.tval) < 1:
            return 0
        return it["number"]

    PACK_SLOTS = 23

    def town_make_room(self, kit, buys):
        """Free the pack slots the buys need (kinds not in the pack yet): sell the cheapest item the policy doesn't
        protect where a shop buys it, else destroy it. One item per call (letters shift). True if it acted."""
        w = self.w
        new = {kind for _, kind, _, n, _ in buys if n > 0 and self.kit_count(kind) == 0}
        free = self.PACK_SLOTS - len(w.items())
        if len(new) <= free:
            return False
        tries = kit.__dict__.setdefault("room_tries", 0)
        cand = sorted(((self.pack_value(i), i) for i in w.items()), key=lambda vi: vi[0])
        cand = [(v, i) for v, i in cand if v < float("inf")]
        if not cand or tries >= 6:
            if not kit.__dict__.get("room_said"):
                kit.room_said = True
                kit.done_log.append(f"pack full: no room for {', '.join(sorted(new))} (nothing the policy lets go)")
            return False
        kit.room_tries = tries + 1
        v, it = cand[0]
        store = (self.town_buyers(it) or [None])[0]
        if store and v >= 1:
            kit.sub = Shop(store, sells=[(it["item"], it["number"])])
            kit.sub.role = "pilot"
            kit.done_log.append(f"room for {', '.join(sorted(new))}: selling {it['name']}")
        else:
            self.c.send("confirm yes")
            self.cmd(f"custom k item={it['item']} value={self.destroy_count(it)}", f"town kit: make room, destroy {it['name']}",
                     hold=0.6)
            kit.done_log.append(f"room for {', '.join(sorted(new))}: destroyed {it['name']}")
        return True

    def provision_step(self, kit):
        """The town visit's last step: fill the lantern from the flasks bought for it (worn: it refuels the
        light in hand), then eat rations until Fed (at most 3) -- not Full: a ration is 5000 food, Full starts at 10000
        and Gorged (-10 speed) at 15000, so a Full character is a few potions from Gorged (m48: the 5th Cure Critical in
        a blind fight). The Pilot eats its ration in the dungeon when Hungry. True if it acted."""
        w = self.w
        fuel = self.lantern_fuel()
        # the fuller lantern on first (m39 left town with 4383 turns worn and 13290 in the pack)
        spare = self.best_light()
        if fuel is not None and spare and self.light_left(spare) > fuel + 1000 and \
                any(i["tval"] == TV_LITE for i in w.items(equip=True)) and not kit.__dict__.get("swapped"):
            kit.swapped = True
            self.cmd(f"custom w item={spare['item']}", f"town kit: wear the fuller lantern ({self.light_left(spare)} "
                                                       f"turns vs {fuel})", hold=0.8)
            return True
        flask = next((i for i in w.items(tval=TV_FLASK)), None)
        if fuel is not None and fuel < self.FUEL_TOPUP and flask and kit.__dict__.get("fuelled", 0) < 3:
            worn = next((i for i in w.items(equip=True) if i["tval"] == TV_LITE), None)
            if not worn or "Lantern" not in worn["name"]:
                return self.wear_light("town kit: the lantern on to refuel it")
            kit.fuelled = kit.__dict__.get("fuelled", 0) + 1
            self.cmd(f"custom F item={flask['item']}", f"town kit: fill the lantern ({fuel} turns)", hold=0.8)
            kit.done_log.append(f"filled the lantern ({fuel} turns)")
            return True
        ration = next((i for i in w.items(tval=TV_FOOD) if "Ration" in i["name"]), None)
        if ration and w.hunger <= 2 and kit.__dict__.get("ate", 0) < 3:
            kit.ate = kit.__dict__.get("ate", 0) + 1
            self.cmd(f"eat {ration['item']}", "town kit: eat to Fed before the trip", hold=1.0)
            if kit.ate == 1:
                kit.done_log.append("ate to Fed")
            return True
        return False

    def broke_for_recall(self):
        """In town with fewer than 2 Words of Recall and not the gold for the next one."""
        return not self.w.in_dungeon and self.kit_count("Word of Recall") < 2 and \
            self.w.ind.get("gold", [0])[0] < (self.price_of("Word of Recall", 5) or 250)

    def town_sell_stores(self):
        return sorted({self.town_buyers(i)[0] for i in self.w.items() if self.town_sell_count(i)})

    def town_sells(self, store):
        """[(pack index, count)] to sell at `store` now."""
        return [(i["item"], n) for i in self.w.items() for n in [self.town_sell_count(i)]
                if n and self.town_buyers(i)[0] == store]

    def identify_candidates(self, minimum):
        out = []
        for it in self.w.items() + self.w.items(equip=True):
            name = it["name"]
            if (self.flavour_of(it) or {}).get("junk") or re.search(r"\{(cursed|worthless|broken|terrible)", name):
                continue
            iv = self.iv(name)
            if iv.known is not False:
                continue
            bare = re.sub(r"^(an?|\d+) ", "", re.sub(r"\s*\{[^}]*\}", "", name)).lower()
            prio = float("inf") if bare in self.ability_sources or iv.p_irreplaceable >= 0.2 else iv.value * self.pay_cut(iv.tval)
            if prio >= minimum:
                out.append((prio, it))
        return out

    def town_identify_wanted(self):
        # worth a scroll when its expected value sold is at least twice the scroll's price (likely
        # egos and ability sources always count; m24 bought 3 for 189 of 718 gold, partly for a
        # Staff of Detect Invisible)
        return len(self.identify_candidates(2 * (self.price_of("Identify", 5) or 80)))

    def town_needs(self, kit, buylist):
        """The shopping list by priority tier, before gold: [[tier, kind, store, n, cap]].
        1: Words of Recall to 2; 2: the supply gate's minimums for the planned depth;
        3: Restore for a drained STR/DEX/CON; 4: the kit; 5: the Navigator's buy list."""
        want = self.planned_depth()
        kit = kit or ("A" if want < 500 else "B" if want < 1000 else "C")
        plan = []

        def planned(kind):
            return self.kit_count(kind) + sum(r[3] for r in plan if r[1] == kind)

        def add(tier, kind, target):
            n = target - planned(kind)
            if n > 0:
                plan.append([tier, kind, self.KIT_ITEMS[kind][1], n, self.KIT_CAP.get(kind)])
        add(1, "Word of Recall", 2)
        if want >= 250:
            _, cures, serious, critical, ph = max((st for st in self.SUPPLY_STAGES if want >= st[0]),
                                                  key=lambda st: st[0])
            add(2, "Cure Critical Wounds", critical)
            ccw = planned("Cure Critical Wounds")
            if serious and ccw < 3:
                add(2, "Cure Serious Wounds", serious - ccw)
            total = sum(planned(k) for k in ("Cure Light Wounds", "Cure Serious Wounds", "Cure Critical Wounds"))
            if total < cures:
                k = "Cure Serious Wounds" if want >= 500 else "Cure Light Wounds"
                add(2, k, planned(k) + cures - total)
            add(2, "Phase Door", ph)
        fuel = self.lantern_fuel()
        if fuel is not None and fuel < self.FUEL_TOPUP:
            add(2, "Flask of oil", -(-(self.FUEL_TOPUP - fuel) // self.FLASK_FUEL))
        for stat, (cur, top) in (self.seen_drained or {}).items():
            if stat in self.STAT_FULL and cur < top:
                if not self.stash_has(f"Restore {self.STAT_FULL[stat]}"):     # (fetched from the tavern instead)
                    add(3, f"Restore {self.STAT_FULL[stat]}", 1)
        for kind, n in self.KITS.get(kit, {}).items():
            add(4, kind, n)
        # NAME:N means "have N" (m26's "Word of Recall:3" bought 3 more, to 5)
        for name, n, cap, store in buylist:
            more = n - planned(name)
            if more > 0:
                plan.append([5, name, store, more, cap])
        # 6. Restore Charisma last: Dive04's natural CHR is 4, so it gives 3 -> 4, ~125 gold a
        # mission in prices (the Advisor's rulebook-r3 memo: pays back in ~4 missions)
        # (only with gold to spare: m26 spent 498 of its last 759 on it)
        cur, top = (self.seen_drained or {}).get("CHR", (0, 0))
        if cur < top and not any(r[1] == "Restore Charisma" for r in plan) and self.w.ind.get("gold", [0])[0] >= 3000:
            add(6, "Restore Charisma", 1)
        return plan

    def restore_potion(self, skip=()):
        """A Potion of Restore <stat> in the pack for a drained STR/DEX/CON, or None."""
        full = dict(self.STAT_FULL, CHR="Charisma")
        for stat, (cur, top) in (self.seen_drained or {}).items():
            if stat in full and cur < top:
                pot = next((i for i in self.w.items(tval=TV_POTION) if f"Restore {full[stat]}" in i["name"]
                            and i["name"] not in skip), None)
                if pot:
                    return pot
        return None

    def town_reserve(self):
        """The gold tiers 1-2 (recall and the gate's minimums) need."""
        return sum(n * (self.price_of(k, st) or 0) for t, k, st, n, _ in self.town_needs(None, ()) if t <= 2)

    def town_shopping(self, kit, buylist):
        """(buys, short): what the gold buys, in priority order, as [(tier, kind, store, n,
        cap)], and [(kind, n)] it can't. Essentials (tiers 1-3) have no price cap;
        the kit's own lines are capped at 1.5x the price last seen."""
        left = self.w.ind.get("gold", [0])[0]
        buys, short = [], []
        for tier, kind, store, n, cap in self.town_needs(kit, buylist):
            price = self.price_of(kind, store) or cap
            if not price:
                buys.append((tier, kind, store, n, cap))      # (unknown price: the cap decides)
                continue
            if cap and price > cap:
                short.append((f"{kind} (over {cap})", n))     # (the shop asks more than the line is worth)
                continue
            k = min(n, left // price)
            if k:
                buys.append((tier, kind, store, k, cap if cap else (round(price * 1.5) if tier == 4 else None)))
                left -= k * price
            if k < n:
                short.append((kind, n - k))
                # Word of Recall short of 2 and unaffordable: the gold waits for it -- nothing else but food (m27
                # spent 62 of 71 gold on a CSW with WoR at 1)
                if tier == 1 and kind == "Word of Recall":
                    for t2, k2, s2, n2, c2 in self.town_needs(kit, buylist):
                        if k2 == "Ration of Food":
                            pr = self.price_of(k2, s2) or 4
                            m = min(n2, left // pr)
                            if m:
                                buys.append((t2, k2, s2, m, c2))
                    short.append(("(saving for Word of Recall)", 0))
                    return buys, short
        return buys, short

    def buy_store(self, name):
        """The store that stocks `name` (the rulebook's stock table, or a listing we saw)."""
        key = singular(re.sub(r"^(Potions?|Scrolls?|Rings?|Amulets?|Wands?|Staffs?|Staves|Rods?) of ", "", name.strip()))
        for r in self.stock_table():
            if key in singular(re.sub(r"[&~]", "", r["item_name"]).strip()) or \
                    singular(re.sub(r"[&~]", "", r["item_name"]).strip()) in key:
                return self.STORE_NUM.get(r["store"])
        for st, v in self.stores_seen.items():
            if st != 7 and any(key in k for k in v.get("prices", {})):
                return st
        return None

    def stock_table(self):
        if not hasattr(self, "_stock"):
            try:
                self._stock = list(csv.DictReader(open(os.path.join(HERE, "..", "rulebook", "shop_stock.csv"))))
            except OSError:
                self._stock = []
        return self._stock

    def plan_tick(self, now, idle):
        """Run the trip plan: when no goal is running, its next step; every 2 s under
        a goal, its conditions. True if it acted."""
        pl = self.plan
        if not pl or (not idle and now - self.plan_t < 2):
            return False
        self.plan_t = now
        try:
            r = pl.tick(self)
        except Exception as e:             # a plan bug must not kill the pilot
            r = ("failed", f"error: {e!r}")
        pl.save(self) if not r else self.clear_plan_file()
        if r:
            self.plan = None
            self.log("plan_end", plan=pl.text, status=r[0], detail=r[1], levels=pl.levels,
                     minutes=round((now - pl.t0) / 60, 1))
            self.notify("plan_done" if r[0] == "done" else "plan_failed", f"{pl.text}: {r[1]}")
        return idle and self.goal is not None

    def clear_plan_file(self):
        try:
            os.remove(os.path.join(self.rundir, "plan.json"))
        except OSError:
            pass

    PLAN_USAGE = ("usage: plan trip LO-HI [until \"COND or COND...\"] [then recall|town] [level_min=N] [via=stairs|recall] "
                  "[force] | "
                  "plan town [kit=A|B|C|none] [buy [STORE/]NAME[:N][@MAX],...] | plan stop | plan resume | plan")

    def request_trip(self, args):
        w = self.w
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", args[0]) if args else None
        if not m:
            return {"ok": False, "error": self.PLAN_USAGE}
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        if lo > hi or lo % 50 or hi % 50 or lo < 50:
            return {"ok": False, "error": f"{args[0]}: a depth range in feet, multiples of 50, e.g. 600-700"}
        md = int(self.orders.get("max_depth", 0) or 0)
        if md and hi > md:
            return {"ok": False, "error": f"{hi} ft is below max_depth {md}: `order max_depth={hi}` first "
                                          "(going deeper is your standing order to give)"}
        until, then, level_min, force, via, i = None, "recall", 10, False, None, 1
        while i < len(args):
            a = args[i]
            if a == "until":
                j = i + 1
                while j < len(args) and args[j] not in ("then", "force") and \
                        not args[j].startswith(("level_min=", "via=")):
                    j += 1
                until, i = " ".join(args[i + 1:j]), j
                continue
            if a == "then" and i + 1 < len(args):
                then, i = args[i + 1], i + 2
                if then not in ("recall", "town"):
                    return {"ok": False, "error": "then recall (stop in town) or then town (and run the town kit)"}
                continue
            if a.startswith("level_min="):
                level_min = float(a.split("=", 1)[1])
            elif a.startswith("via="):
                via = a.split("=", 1)[1]
                if via not in ("stairs", "recall"):
                    return {"ok": False, "error": "via=stairs (walk down: one Word of Recall is enough, for coming "
                                                  "home) or via=recall (two: one to go, one to come home)"}
            elif a == "force":
                force = True
            else:
                return {"ok": False, "error": f"can't read {a!r}; " + self.PLAN_USAGE}
            i += 1
        try:
            conds = TripPlan.parse_until(until or "cures<3 or phase<3 or minutes>45")
        except ValueError as e:
            return {"ok": False, "error": f"until: {e}"}
        bad = [c[0] for c in conds if c[1] == "wor" and c[2] in ("<", "<=") and int(c[3]) - (c[2] == "<=") >= 1]
        if bad:
            return {"ok": False, "error": f"until {bad[0]}: that holds as soon as the trip has recalled down (one "
                                          "Word of Recall goes on the way down); coming home with none left is "
                                          "built in"}
        plan = TripPlan(lo, hi, conds, then, level_min, via)
        if w.depth == 0 and not force:
            want = min(hi, max(lo, self.deepest_ft or 0))
            down_by_recall = not plan.stairs_down(self)
            gap = self.supply_gate(want, down_by_recall)
            if gap:
                return {"ok": False, "error": f"supply gate for {want} ft "
                                              f"({'down by Word of Recall: 2 needed' if down_by_recall else 'down by the stairs: 1 Word of Recall for coming home'}): "
                                              f"missing {'; '.join(gap)}. `plan town` first"
                                              + ("" if via else ", or `via=stairs`") + ", or add 'force'"}
        self.plan = plan
        self.set_goal(None)
        self.log("plan_start", plan=self.plan.text, role=self.req_role)
        return {"ok": True, "plan": self.plan.text + (" (down by the stairs)" if self.plan.stairs_down(self) and w.depth == 0
                                                     else " (down by Word of Recall)" if w.depth == 0 else ""),
                "note": "the Pilot runs it; `wait` wakes you when it ends (plan_done) and for what it can't "
                        "handle (user messages, stat drains, emergency loops). Bands, pits, breeders and the "
                        "like are news: it leaves the level itself. A goal you give pauses the plan until it "
                        "ends (`plan resume` ends your goal and hands back); `plan stop` ends it"}

    def request_plan(self, args):
        """plan trip ... | plan town [kit=A|B|C|none] [buy [STORE/]NAME[:N][@CAP][,...]]... | plan stop | plan resume |
        plan"""
        if not args:
            return {"ok": True, "text": f"plan: {self.plan.describe()}" if self.plan else "no plan"}
        if args[0] == "stop":
            if not self.plan:
                return {"ok": True, "text": "no plan"}
            self.log("plan_end", plan=self.plan.text, status="stopped")
            self.plan = None
            self.clear_plan_file()
            return {"ok": True, "text": "plan stopped (the current goal runs on; `stop` stops it)"}
        if args[0] == "resume":
            # (m30: the Navigator's `goal explore` paused the plan for 7 minutes on a quiet level, with no way to
            # hand control back short of the goal ending)
            if not self.plan:
                return {"ok": True, "text": "no plan"}
            if not self.plan.paused:
                return {"ok": True, "text": f"the plan isn't paused: {self.plan.describe()}"}
            ended = self.goal.describe() if self.goal else None
            self.set_goal(None)
            self.plan.paused, self.plan.pause_goal = False, None
            self.log("plan_resumed", plan=self.plan.text, ended=ended)
            return {"ok": True, "text": f"plan resumed{' (ended ' + repr(ended) + ')' if ended else ''}: "
                                        f"{self.plan.describe()}"}
        if args[0] == "trip":
            return self.request_trip(args[1:])
        if args[0] != "town":
            return {"ok": False, "error": self.PLAN_USAGE}
        if self.w.depth:
            return {"ok": False, "error": "plan town is for the town (recall home first)"}
        kit, buylist, specs, i = None, [], [], 1
        while i < len(args):
            a = args[i]
            if a.startswith("kit="):
                kit = a[4:]
                if kit not in self.KITS:
                    return {"ok": False, "error": f"kit={kit}: A (to 500 ft), B (to 1000 ft), C (deeper) or none"}
            elif a == "buy":
                pass
            else:
                # (not inside [..] or (..): m43's `2/pair_of_hard_leather_boot_[3,+6]@1050`, the line `gear` printed,
                # split into "boot_[3" and "+6]")
                specs += split_specs(a)
            i += 1
        for sp in specs:
            m = re.fullmatch(r"(?:([1-7])/)?([^:@]+)(?::(\d+))?(?:@(\d+))?", sp)
            if not m:
                return {"ok": False, "error": f"can't read the buy item {sp!r}: [STORE/]NAME[:COUNT][@MAXPRICE]"}
            name = m.group(2).replace("_", " ").strip()
            store = int(m.group(1)) if m.group(1) else self.buy_store(name)
            # (a kit line knows its shop: m46's Navigator was told to "name the shop" for a Potion of Speed)
            if not store:
                store = next((v[1] for k, v in self.KIT_ITEMS.items() if k.lower() == name.lower()), None)
            if not store:
                return {"ok": False, "error": f"no shop's stock table has {name!r}: name the shop (e.g. 7/{m.group(2)}"
                                              " for the Black Market, which charges 3x)"}
            buylist.append((name, int(m.group(3) or 1), int(m.group(4)) if m.group(4) else None, store))
        g = TownKit(kit, buylist)
        g.by_navigator = self.req_role != "architect"
        g.role = self.req_role
        self.set_goal(g)
        buys, short = self.town_shopping(kit, buylist)
        return {"ok": True, "goal": g.describe(),
                "note": "will buy (by the prices last seen): " + (", ".join(f"{n} {k} at the {self.STORE_LABEL.get(st, st)} ({st})"
                                                                           for _, k, st, n, _ in buys)
                                                                 or "nothing") +
                        (("; can't afford yet: " + ", ".join(f"{n} {k}" for k, n in short)) if short else "") +
                        self.town_extras_note() + " (selling first may change this)"}

    # --- order checks (restructure step 2.4) ------------------------------------
    def fight_rows(self):
        if not hasattr(self, "_fight_rows"):
            try:
                self._fight_rows = {int(r["idx"]): r for r in csv.DictReader(
                    open(os.path.join(HERE, "..", "rulebook", "monsters.csv")))}
            except OSError:
                self._fight_rows = {}
        return self._fight_rows

    def fight_estimate(self, race):
        """(turns to kill it, HP it takes meanwhile, the pessimistic HP, its worst breath, its
        row) by the rulebook's fight rule (rule.py fight: hit chance from skill and to-hit
        against 3/4 of its AC, its expected melee per player turn at our AC, spells and
        ranged attacks), or None. Pessimistic: twice the turns (blinks, heals, misses) with
        its spells at their maximum: the m19 Ranger rates ~27 expected, ~196 pessimistic,
        and took 153."""
        row = self.fight_rows().get(getattr(race, "idx", None))
        wt = [x for x in self.weapon_table() if x[3]]
        if not row or not wt:
            return None
        name, blows, dpr, _ = wt[0]
        th = re.search(r"\(([+-]\d+),[+-]\d+\)", name)
        chance = 82 + 45 * self.w.clvl // 10 + 3 * (int(th.group(1)) if th else 0)
        ph = 0.05 + 0.90 * max(0.0, 1 - (int(row["ac"]) * 3 // 4) / chance)
        per_turn = max(0.1, ph * dpr)
        turns = int(row["hp"]) / per_turn
        ac = self.w.ind.get("armor", [0])[0] or 0
        col = min((20, 40, 60), key=lambda a: abs(a - ac))
        melee, sp = float(row[f"melee_turn_ac{col}"]), float(row["spell_pct"] or 0)
        taken = turns * (melee * (1 - sp) + float(row["range_turn"] or 0))
        worst = 2 * turns * (melee + sp * float(row["spell_max"] or 0) + float(row["range_turn"] or 0))
        return turns, taken, worst, float(row["breath_max"] or 0), row

    def fight_sim(self, race, n=600):
        """The Advisor's fight_sim.summary at our live profile, or None (tools/rulebook/fight_sim.py,
        synced from Advisor/data/rulebook; ~0.1 s for 600 duels)."""
        try:
            if not hasattr(self, "_sim"):
                sys.path.insert(0, os.path.join(HERE, "..", "rulebook"))
                import fight_sim
                self._sim = (fight_sim, {r["idx"]: r for r in csv.DictReader(
                    open(os.path.join(HERE, "..", "rulebook", "monsters_raw.csv")))})
            mod, rows = self._sim
            row = rows.get(str(getattr(race, "idx", "")))
            wt = [x for x in self.weapon_table() if x[3]]
            if not row or not wt:
                return None
            name, blows = wt[0][0], wt[0][1]
            d = re.search(r"\((\d+d\d+)\)", name)
            hd = re.search(r"\(([+-]\d+),([+-]\d+)\)", name)
            import argparse
            o = argparse.Namespace(clvl=self.w.clvl, blows=blows, dice=d.group(1) if d else "1d4",
                                   todam=int(hd.group(2)) if hd else 0, tohit=int(hd.group(1)) if hd else 0,
                                   ac=self.w.ind.get("armor", [0])[0] or 0, hp=max(1, self.w.hp[0]), n=n)
            return mod.summary(row, o)
        except Exception as e:             # (a rulebook problem must not break the check)
            self.log("note", text=f"fight_sim failed: {e!r}")
            return None

    def hunt_refusal(self, name):
        """Why the Pilot won't take this hunt now, or None (and the estimate it used)."""
        w = self.w
        key = name.lower()
        seen = [r for *_, r in w.monsters if key in r.name.lower()]
        race = seen[0] if seen else next((r for r in w.g.races.values() if r.name.lower() == key), None) or \
            next((r for r in w.g.races.values() if key in r.name.lower()), None)
        if not race:
            return None, "no monster by that name in this game's data"
        if "UNIQUE" in race.flags and race.name.lower() in self.uniques_killed():
            return (f"you've killed {race.name} before: a repeat kill gives no XP and no drop (the server's "
                    "'cheeze' rule), so there's nothing to hunt it for"), None
        if race.paralyser and not self.has_ability("free_action"):
            return (f"{race.name} paralyses (a blow or Hold Person) and you have no Free Action: a paralysed "
                    "warrior is hit until dead. Only with Free Action"), None
        est = self.fight_estimate(race)
        if not est:
            return None, f"no fight estimate for {race.name}"
        turns, taken, worst, breath, row = est
        hp = max(1, w.hp[0])
        sim = self.fight_sim(race)
        if sim:
            # the Advisor's duel simulator (hunt-strictness memo, 2026-10-24): the 90th percentile of
            # the HP lost, at our live profile, replaces "twice the turns"
            turns, taken, worst = sim["turns_mean"], sim["loss_mean"], sim["loss_p90"]
        info = (f"{race.name}: ~{turns:.0f} turns to kill, ~{taken:.0f} HP lost on average, ~{worst:.0f} in a bad "
                f"fight (1 in 10; you have {w.hp[0]})")
        # a fight the Pilot's own emergency rule would break off on average: it phases away once HP is
        # within 2.5 worst rounds of the monster (or below flee_hp), so a hunt whose average loss ends
        # there is lost (the set-piece harness's C3: Ulfast, ~118 on average, broken off at 145 HP)
        abort = max(self.worst_3turns([race]), float(self.orders.get("flee_hp", 0.5)) * w.hp[1])
        if hp - taken < abort:
            return (f"{info}: on average it ends below {abort:.0f} HP, where the Pilot's emergency rule breaks a "
                    "fight off (its worst 3 turns, or flee_hp); rest to full or come back stronger", info)
        if row.get("response") in ("AVOID", "LEAVE") and row.get("veto_reason", "qualitative") != "strength":
            # (the Advisor's m24 memo: ratings given for strength alone are the simulator's to judge;
            # its veto_reason column says which, from its next rulebook build)
            return (f"the Advisor's rating for {race.name} is {row['response']}", info)
        if worst > 0.6 * hp:
            return (f"{info}: a bad fight would cost more than 60% of your HP. Rest to full first, or come back "
                    "stronger", info)
        # summoners: once summons arrive the fight is a band (the m19 Ranger: a cheap duel, then
        # S_ANIMAL and bolts cost 153 HP). Only a clear win, at high HP, alone, with escapes
        if any(sp.startswith("S_") for sp in race.spells):
            others = sum(1 for *_, r in w.monsters if r.name != race.name)
            phase = sum(i["number"] for i in w.items(tval=TV_SCROLL) if "Phase Door" in i["name"])
            if worst > 0.3 * hp or w.hp_frac < 0.8 or others or phase < 5:
                return (f"{race.name} summons help: hunt it only when a bad fight costs under 30% of your HP, you're "
                        f"at 80%+ HP, nothing else is in view and you carry 5+ Phase Door ({info})", info)
        if breath > 0.6 * hp:
            return (f"{race.name} breathes up to {breath:.0f} (you have {w.hp[0]}): one breath could take "
                    f"60% of your HP", info)
        band_lt = (getattr(self, "band_warned", (None, 0)) or (None, 0))[0]
        if band_lt == w.level_t and gnow() - getattr(self, "band_warned_t", 0) < 120 and \
                sum(1 for *_, r in w.monsters if "NEVER_MOVE" not in r.flags) >= 5:
            return (f"a band is about (flagged {gnow() - self.band_warned_t:.0f} s ago): leave first", info)
        return None, info

    def stale_order(self, c, args):
        """An order whose premise is gone since the report it answers (the Advisor's
        starting-over memo: a goto written for a 17-s-old report walked beside Brodda).
        Returns the reason to hold it, or None."""
        st = getattr(self, "report_state", None)
        rid, rt = self.last_report
        if not st or not rid:
            return None
        w, age = self.w, gnow() - rt
        positional = (c == "goal" and args[:1] and args[0] in ("goto", "fetch", "searchroom", "hunt") and
                      not (args[0] == "goto" and len(args) > 1 and args[1] in ("<", ">"))) or \
                     (c == "avoid" and args and re.match(r"\d+,\d+$", args[0]))
        if not positional:
            return None
        if st["level_t"] != w.level_t:
            return (f"your order answers report r{rid} ({age:.0f} s ago), from a level you've since left (now "
                    f"{w.depth_ft} ft): positions and monsters there are gone. Look again (`status`) and re-issue")
        if c == "goal" and args[0] == "hunt" and age > 5:
            key = " ".join(args[1:]).replace("_", " ").lower()
            if key and not any(key in r.name.lower() for *_, r in w.monsters):
                return (f"{key} isn't in view now (your order answers report r{rid}, {age:.0f} s ago). "
                        "Re-issue when it is")
        if c == "goal" and args[0] in ("goto", "fetch") and age > 5 and st["hp"] - w.hp_frac > 0.25:
            return (f"HP fell from {st['hp']:.0%} to {w.hp_frac:.0%} since report r{rid} ({age:.0f} s ago): a "
                    "detour then may not be one now. Look again and re-issue")
        return None

    def request_goal(self, args):
        if not args:
            return {"ok": False, "error": "usage: goal NAME [ARGS]"}
        # Unread attention events belong to what came before: move them to the
        # news, so the next 'wait' answers about this goal
        with self.att_cond:
            self.news += self.attention
            self.attention = []
        name, rest = args[0], args[1:]
        force = "force" in rest
        scum = name == "dive" and "scum" in rest
        rest = [a for a in rest if a not in ("force", "scum")] if name in ("dive", "recall") else rest
        if name == "dive":
            g = Dive(rest[0] if rest else (self.w.depth_ft + 50), scum=scum)
            md = int(self.orders.get("max_depth", 0))
            want = min(g.target_ft, md) if md else g.target_ft
            gap = self.supply_gate(want, False) if want > self.w.depth_ft and not force else []
            if gap:
                return {"ok": False, "error": f"supply gate for {want} ft: missing {'; '.join(gap)} "
                                              "(the stage table). Restock, or add 'force' to go anyway"}
            if md and g.target_ft > md:
                # say so (a 'dive 700' was silently capped by max_depth 650)
                self.set_goal(g)
                return {"ok": True, "goal": g.describe(),
                        "note": f"capped at max_depth {md} ft (order max_depth=... to change)"}
        elif name == "explore":
            kw = dict(a.split("=", 1) for a in rest if "=" in a)
            g = Explore(until=kw.get("until"), radius=int(kw["radius"]) if "radius" in kw else None)
        elif name == "goto":
            force = "force" in rest
            g = Goto(" ".join(x for x in rest if x != "force"), force=force)
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
                plus = n.startswith("+")
                n = int(n.lstrip("+"))
                if kind == "buy":
                    # NAME:N means "have N", as in plan town (m27: `buy Phase_Door:11` bought 9 more on top of 11,
                    # 171 of 179 gold); `buy NAME:+N` buys N more
                    name = what.replace("_", " ")
                    if not plus:
                        key = singular(name.lower())
                        have = sum(it["number"] for it in self.w.items() if key in singular(it["name"].lower()))
                        n = n - have
                    if n > 0:
                        buys.append((name, n, int(cap) if cap else None))
                elif kind in ("sell", "quote"):
                    key = what.replace("_", " ")
                    # quote: offer it and decline, to see the price (the Navigator's wish)
                    sells.append((self.item_index(key) if len(key) == 1 else key, n) +
                                 (("quote",) if kind == "quote" else ()))   # '!NAME' forces a sale
                i += 2
            g = Shop(rest[0], buys, sells, list_stock=list_stock)
        elif name == "search":
            g = Search()
        elif name == "searchroom":
            m = re.match(r"^(\d+)[ ,](\d+)$", " ".join(rest[:2]) if len(rest) > 1 else (rest[0] if rest else ""))
            if not m:
                return {"ok": False, "error": "usage: goal searchroom Y,X (an inner room's centre, from the report)"}
            Y, X = int(m.group(1)), int(m.group(2))
            # its door already in view: nothing to search for (mission 20 searched
            # 26 s beside an open door at 27,39)
            open_d = [self.room_door(Y, X)] if self.room_door(Y, X) else []
            if open_d:
                return {"ok": False, "error": f"the inner room at {Y},{X} already shows its door at "
                                              f"{open_d[0][0]},{open_d[0][1]}: `goal explore` goes in "
                                              "(a closed door opens on a bump)"}
            g = Search(tries=20, spots=[r for _, r in structures.door_spots(Y, X)])
            g.name = f"searchroom {Y},{X}"
        elif name == "hunt":
            target = " ".join(rest).replace("_", " ")    # 'hunt Black_ogre', like shop names
            force = target.startswith("!")
            target = target.lstrip("!").strip()
            why, info = self.hunt_refusal(target)
            if why and self.req_role != "architect" and not force:
                self.log("order_refused", order=f"hunt {target}", why=why)
                return {"ok": False, "error": f"hunt refused: {why}. `goal hunt !NAME` overrides; if the fight goes "
                                              "wrong, the HP it costs goes into your fight debt"}
            if why and force and self.req_role != "architect" and not self.override_allowed("hunt"):
                return {"ok": False, "error": f"hunt refused: {why}. Your freedom to override the Pilot's fight "
                                              f"checks is suspended (fight debt {self.fight_debt_total()} HP)"}
            g = Hunt(target)
            g.estimate = info
            if why and force and self.req_role != "architect":
                # an override: judged when the hunt ends (the user, 2026-10-23: a separate debt)
                w = self.w
                g.overridden = {"why": why, "hp0": w.hp[0], "hp_min": w.hp[0], "t0": gnow(),
                                "emerg0": len(self.emerg_times)}
                self.log("hunt_override", target=target, why=why, hp=w.hp[0])
        elif name == "fetch":
            # one item detour (the design's `fetch Y,X`): not with a band or danger about
            m = re.match(r"^(\d+)[ ,](\d+)$", " ".join(rest[:2]) if len(rest) > 1 else (rest[0] if rest else ""))
            if not m:
                return {"ok": False, "error": "usage: goal fetch Y,X (an item's square, from the report)"}
            if self.req_role != "architect" and self.w.in_dungeon:
                band_lt = (getattr(self, "band_warned", (None, 0)) or (None, 0))[0]
                if band_lt == self.w.level_t and gnow() - getattr(self, "band_warned_t", 0) < 120:
                    return {"ok": False, "error": "fetch refused: a band was flagged on this level in the last 2 "
                                                  "minutes; loot isn't worth it now (mission 22). Leave or fight first"}
                if self.dangers():
                    return {"ok": False, "error": "fetch refused: a dangerous monster is in view ("
                                                  + ", ".join(sorted({r.name for r in self.dangers()})[:3]) + ")"}
            g = Goto(f"{m.group(1)},{m.group(2)}")
            g.name = f"fetch {m.group(1)},{m.group(2)}"
        elif name == "leave":
            if not self.w.in_dungeon:
                return {"ok": False, "error": "leave is for dungeon levels"}
            g = Flee("you said: leave this level")
            g.name = "leave (this level)"
        elif name == "recall":
            g = Recall()
            if self.w.depth == 0 and not force:
                md = int(self.orders.get("max_depth", 0))
                deepest = getattr(self, "deepest_ft", 0) or 0
                want = min(md, deepest) if md and deepest else (md or deepest)
                gap = self.supply_gate(want, True) if want else []
                if gap:
                    return {"ok": False, "error": f"supply gate for recalling down to ~{want} ft: missing "
                                                  f"{'; '.join(gap)} (the stage table). Restock, or "
                                                  "'goal recall force' to go anyway"}
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
        elif name == "quiet":
            try:
                secs = float(rest[0]) if rest else 120
            except ValueError:
                return {"ok": False, "error": "usage: goal quiet [SECS] (10-600, default 120)"}
            mob = sorted({r.name for _, _, r in self.w.monsters if "NEVER_MOVE" not in r.flags}) \
                if self.w.in_dungeon else []
            if mob:
                return {"ok": False, "error": f"not quiet: {', '.join(mob[:3])} in view (it would wake at once). "
                                              "Deal with it, or `goal leave`"}
            # (the goal it replaces carries on after; a plan's own goal comes back with the plan)
            prev = self.goal if self.goal is not None and not getattr(self.goal, "by_plan", False) and \
                not isinstance(self.goal, QuietWait) else None
            g = QuietWait(secs, prev)
        else:
            return {"ok": False, "error": f"unknown goal {name}"}
        g.by_navigator = self.req_role != "architect"
        g.role = self.req_role
        self.set_goal(g)
        if getattr(g, "estimate", None) and not self.plan:
            return {"ok": True, "goal": g.describe(), "note": g.estimate}
        if self.plan:
            # your goal first; the plan carries on when it ends (`plan stop` ends the plan)
            self.plan.paused, self.plan.pause_goal = True, g
            return {"ok": True, "goal": g.describe(), "note": "the trip plan is paused until this goal ends"}
        return {"ok": True, "goal": g.describe()}

    # --- the situation report ------------------------------------------------

    # --- since the last report (the Advisor's Navigator-decisions memo §3.3:
    # it reported "lowest seen 58" when the low was 26, "single orc" for 12)

    # --- inner rooms, pits and nests (structures.py; the Advisor's spec,
    # memos/2026-10-07-mission15-answers.md §2: the user asked whether the
    # Pilot could recognise vaults and pits from a partial map)

    ADVICE = {
        "large room": "a lit large room: its one secret door is at the middle of a side of the inner block; "
                      "'goal searchroom {Y},{X}' searches the 4 spots (20 each, about a minute). Loot is ordinary "
                      "(0-3 objects, a few sleeping monsters)",
        "inner room": "a dark inner room: most likely a large room (dark ones are common), but pits and nests "
                      "(95 awake monsters) look the same and are never lit. Open it only ready to leave: "
                      "'goal searchroom {Y},{X}'",
        "orc pit": "an ORC PIT (95 awake orcs, archers inside, no loot): leave the level. Avoid zone set",
        "nest": "a NEST (jellies, molds, icky things; some breed; no loot): don't open it. Avoid zone set",
    }

    def structures_tick(self, now):
        w = self.w
        if now - self.struct_t < 2.0:
            return
        self.struct_t = now
        self.save_level_map(now)
        if not w.in_dungeon or not w.memory:
            return
        for Y, X, ev in structures.scan(w.memory):
            key = (w.level_t, (Y, X))
            st = self.structs.get(key)
            if st is None:
                # lit rooms come into view all at once (pits and nests never are)
                st = self.structs[key] = {"t": now, "lit": ev["ring_known"] >= 0.75 * ev["ring_total"],
                                          "kind": None, "sure": False}
            st["sure"] = st["sure"] or ev["sure"]
            kind = structures.classify(Y, X, ev, w.monsters, st["lit"])
            if kind == st["kind"] or (st["kind"] in ("orc pit", "nest") or "pit" in str(st["kind"])):
                continue                          # (a pit stays a pit when its orcs have left)
            st["kind"] = kind
            advice = self.ADVICE.get(kind, self.ADVICE["orc pit"]).format(Y=Y, X=X)
            where = f"{kind} centred {Y},{X} ({Y - 5}-{Y + 5}, {X - 12}-{X + 12})" + ("" if st["sure"] else ", likely")
            if "pit" in kind or kind == "nest" or kind == "inner room":
                # (a dark inner room too: pits look the same until they open, and its ring
                # is a one-wide corridor where they surround you: m24 at 600 ft, an orc pit)
                if not any(abs(y0 - Y) <= 1 and abs(x0 - X) <= 1
                           for y0, x0, _ in self.avoid_zones.get(w.level_t, [])):
                    for dx in (-7, 0, 7):
                        self.avoid_zones.setdefault(w.level_t, []).append((Y, X + dx, 6))
                if kind == "inner room":
                    self.notify("structure", f"{where}: {advice}. Avoid zone set on it and its ring (a pit looks "
                                             "the same from outside); `avoid clear` to go in", news=True)
                else:
                    self.notify("structure", f"{where}: {advice}")
            else:
                self.notify("structure", f"{where}: {advice}", news=True)

    def save_level_map(self, now):
        """Each dungeon level's remembered map, written when we leave it, to
        runs/pilot/<nick>/levels/ (only 11x31 crops were logged, so the
        recogniser couldn't be checked against real levels afterwards)."""
        w = self.w
        # the level this Pilot logged in on (None: in town): the previous Pilot's logout left it "static" on the
        # server, kept after we leave it (operations.md, Level persistence) -- Dive.FLED_HOLD's test-server edge case
        if "first_level_t" not in self.__dict__ and w.depth is not None and w.level_t:
            self.first_level_t = w.level_t if w.in_dungeon else None
        # the arrival feeling, logged per level (the Advisor's structures memo: at <= 850 ft any pit, nest or
        # vault forces "special"; another feeling proves there is none)
        if w.in_dungeon and getattr(self, "feeling_level", None) != w.level_t and waited(w.level_t, 3):
            self.feeling_level = w.level_t
            fl = next((t for ts, t in w.messages if ts >= w.level_t - 0.5 and re.search(
                r"special about this level|feeling|Looks like any other level|Omens of death|murderous|"
                r"terribly dangerous|nervous|bad feeling|quiet, peaceful|safe|Luck is turning|lucky", t)), None)
            self.level_feeling = fl
            self.log("arrival_feeling", depth_ft=w.depth_ft, feeling=fl, arrived_by=w.arrived_by)
        snap = getattr(self, "map_snap", None)
        if snap and snap["level"] != w.level_t:
            try:
                d = os.path.join(self.rundir, "levels")
                os.makedirs(d, exist_ok=True)
                mem = snap["mem"]
                rows = ["".join(mem.get((y, x), " ") for x in range(MAX_WID)).rstrip() for y in range(MAX_HGT)]
                found = [f"{st['kind']} {Y},{X}" for (lv, (Y, X)), st in self.structs.items() if lv == snap["level"]]
                with open(os.path.join(d, time.strftime("%Y%m%d-%H%M%S", _lt(snap["t0"]))
                                       + f"-{snap['ft']}ft.txt"), "w") as f:
                    f.write(f"# {snap['ft']} ft, {time.strftime('%Y-%m-%d %H:%M:%S', _lt(snap['t0']))} - "
                            f"{time.strftime('%H:%M:%S', _lt(snap['t']))}; structures: "
                            f"{', '.join(found) or 'none'}; feeling: {snap.get('feeling') or 'none'}\n"
                            + "\n".join(rows) + "\n")
            except OSError:
                pass
            snap = None
        if w.in_dungeon and w.memory:
            self.map_snap = {"level": w.level_t, "mem": dict(w.memory), "ft": w.depth_ft,
                             "t0": snap["t0"] if snap else now, "t": now,
                             "feeling": getattr(self, "level_feeling", None)
                             if getattr(self, "feeling_level", None) == w.level_t else None}
        else:
            self.map_snap = None

    def structures_here(self):
        w = self.w
        return [(Y, X, st) for (lv, (Y, X)), st in self.structs.items() if lv == w.level_t and st["kind"]]

    def track_since(self):
        w, now = self.w, gnow()
        sn = getattr(self, "since", None)
        if sn is None:
            sn = self.since = {"t": now, "min_hp": None, "mons": {}, "uniques": set()}
        if w.hp[1] > 1 and (sn["min_hp"] is None or w.hp[0] < sn["min_hp"][0]):
            sn["min_hp"] = (w.hp[0], w.hp[1], now)
        counts = {}
        for *_, r in w.monsters:
            counts[r.name] = counts.get(r.name, 0) + 1
        for n, k in counts.items():
            sn["mons"][n] = max(sn["mons"].get(n, 0), k)
        sn["uniques"] |= {r.name for *_, r in w.monsters if "UNIQUE" in r.flags}
        exp = (w.ind.get("exp") or [0])[0]
        if exp != getattr(self, "exp_seen", None):
            if getattr(self, "exp_seen", None) is not None and exp > self.exp_seen:
                self.exp_t = now
            self.exp_seen = exp

    def since_lines(self, reset):
        sn = getattr(self, "since", None)
        if not sn:
            return []
        now = gnow()
        out = []
        lo = sn["min_hp"]
        mons = sorted(sn["mons"].items(), key=lambda kv: -kv[1])
        out.append(f"Since the last report ({now - sn['t']:.0f} s): lowest HP "
                   + (f"{lo[0]}/{lo[1]} at {time.strftime('%H:%M:%S', _lt(lo[2]))}" if lo else "?")
                   + "; monsters seen (most at once): " + (", ".join(f"{n} x{k}" for n, k in mons[:12]) or "none")
                   + (f"; UNIQUES: {', '.join(sorted(sn['uniques']))}" if sn["uniques"] else ""))
        xt = getattr(self, "exp_t", None)
        w = self.w
        out.append("Progress: " + (f"last XP gain {self.ago(now - xt)} ago" if xt else "no XP gain seen yet")
                   + (f"; on this level {self.ago(now - w.level_t)}" if w.level_t else "")
                   + (f"; goal '{self.goal.describe()}' for {self.ago(now - getattr(self, 'goal_t', now))}"
                      if self.goal else ""))
        if reset:
            self.since = {"t": now, "min_hp": (w.hp[0], w.hp[1], now) if w.hp[1] > 1 else None,
                          "mons": {}, "uniques": set()}
        return out

    def movement_line(self, window=60, step=8):
        """Where we've been in the last minute, a point every ~8 s (the
        Navigator's wish: it couldn't see what the Pilot's moves had been)."""
        now = gnow()
        pts = [(t, p, d) for t, p, d in self.pos_hist if now - t <= window]
        if not pts:
            return None
        out, last_t, last_p = [], None, None
        for t, p, d in pts:
            if (last_t is None or t - last_t >= step) and p != last_p:
                out.append(f"{time.strftime('%H:%M:%S', _lt(t))} {p[0]},{p[1]}")
                last_t, last_p = t, p
        if pts[-1][1] != last_p:
            out.append(f"now {pts[-1][1][0]},{pts[-1][1][1]}")
        n = len({p for _, p, _ in pts})
        return f"Movement (last {window} s, {n} different squares): " + " -> ".join(out)

    @staticmethod
    def ago(secs):
        secs = int(max(0, secs))
        return f"{secs // 60}m{secs % 60:02d}s" if secs >= 60 else f"{secs}s"

    SLOTS = (("weapon", (20, 21, 22, 23), 1), ("bow", (19,), 1), ("ring", (45,), 2), ("amulet", (40,), 1),
             ("light", (39,), 1), ("body armour", (36, 37, 38), 1), ("cloak", (35,), 1), ("shield", (34,), 1),
             ("helm", (32, 33), 1), ("gloves", (31,), 1), ("boots", (30,), 1))

    @staticmethod
    def armour_ac(name):
        m = re.search(r"\[(\d+)(?:,([+-]\d+))?\]", name)
        return int(m.group(1)) + int(m.group(2) or 0) if m else None

    def gear_line(self):
        """Empty slots, and pack items better than what's worn (the Advisor's
        memo §3.2: armour and jewellery against worn or empty slots)."""
        w = self.w
        worn, pack = w.items(equip=True), w.items()
        empty, better = [], []
        for slot, tvals, k in self.SLOTS:
            on = [i for i in worn if i["tval"] in tvals]
            cand = [i for i in pack if i["tval"] in tvals and not re.search(r"\{(cursed|worthless|broken|terrible)", i["name"])
                    and not (self.flavour_of(i) or {}).get("junk")]
            if len(on) < k:
                if slot == "light" and cand and not w.depth:
                    continue          # (off in town to save fuel; worn again before leaving it)
                empty.append(slot + (f" (you carry {cand[0]['name']})" if cand else ""))
            elif slot not in ("weapon", "bow", "ring", "amulet", "light"):
                ac_on = min((self.armour_ac(i["name"]) or 0) for i in on)
                # (as the upgrade step: never over a piece whose abilities the other lacks, nor over an artifact --
                # m37's line offered Metal Lamellar [23] over the Leather of Resistance)
                if self.is_artifact(on[0]["name"]):
                    continue
                cand = [i for i in cand if self.weapon_abilities(on[0]["name"]) <= self.weapon_abilities(i["name"])]
                for i in cand:
                    ac = self.armour_ac(i["name"])
                    if ac is not None and ac > ac_on:
                        better.append(f"{chr(97 + i['item'])}) {i['name']} (AC {ac} vs {ac_on} worn)")
        return ("Gear: empty slots: " + (", ".join(empty) or "none")
                + ("; better than worn: " + "; ".join(better) if better else ""))

    # --- the gear review (the user, 10-25: a between-mission gear step; read-only) ------------------------------
    # what the abilities are worth to a warrior at 500-1000 ft, best first (the Advisor's memos: paralysis, poison
    # breath, blindness and confusion stop a melee character; hold life and the base four resists next)
    GEAR_WANTED = (("free_act", "Free Action"), ("see_invis", "See Invisible"), ("res_pois", "resist poison"),
                   ("res_blind", "resist blindness"), ("res_conf", "resist confusion"), ("hold_life", "hold life"),
                   ("res_fire", "resist fire"), ("res_cold", "resist cold"), ("res_elec", "resist lightning"),
                   ("res_acid", "resist acid"), ("res_fear", "resist fear"), ("res_nexus", "resist nexus"),
                   ("res_sound", "resist sound"), ("res_shard", "resist shards"), ("res_nether", "resist nether"),
                   ("res_dark", "resist darkness"), ("res_lite", "resist light"), ("slow_digest", "slow digestion"),
                   ("regen", "regeneration"), ("telepathy", "telepathy"), ("speed", "speed"))
    EQUIP_LETTER = "abcdefghijkl"           # the flags grid's columns: weapon, bow, 2 rings, amulet, light, body...
    # jewellery by what it gives (shop names are lower case and cut: "ring of protection [+9]")
    JEWEL_FLAGS = (("free action", "free_act"), ("see invisible", "see_invis"), ("resist poison", "res_pois"),
                   ("resist fire and cold", "res_fire res_cold"), ("resist fire", "res_fire"),
                   ("resist cold", "res_cold"), ("resist lightning", "res_elec"), ("resist acid", "res_acid"),
                   ("slow digestion", "slow_digest"), ("feather fall", "feather"), ("hold life", "hold_life"),
                   ("regeneration", "regen"), ("esp", "telepathy"), ("telepathy", "telepathy"))
    SHOP_SLOT = (("shield", "shield"), ("cap", "helm"), ("helm", "helm"), ("crown", "helm"), ("glov", "gloves"),
                 ("gauntlet", "gloves"), ("cesti", "gloves"), ("boot", "boots"), ("cloak", "cloak"),
                 ("armour", "body armour"), ("mail", "body armour"), ("leather", "body armour"),
                 ("robe", "body armour"), ("rob ", "body armour"))

    def jewel_gives(self, name):
        n = name.lower()
        out = set()
        for key, fl in self.JEWEL_FLAGS:
            if key in n:
                out |= set(fl.split())
                if key == "resist fire and cold":
                    break
        return out

    WHY_KINDS = ("emergency", "emergency_loop", "stat_drained", "danger_seen", "band", "fight_going_badly",
                 "unseen_attacker", "thief", "drainer", "fearer", "unique_slain", "lost", "disenchanted")
    WHY_SKIP = ("move", "mons", "itemlist", "time_factor", "report", "audit_check", "audit", "state",
                "perception_gap", "options", "estimator")

    def why_info(self, args):
        """`why [HH:MM[:SS]]` (the Navigators, m40-m42: "why did the Pilot recall?"): what the Pilot saw and did around
        a moment -- by default the last escape, emergency or end of a trip -- from its decision log: HP over the window,
        the monsters in view and adjacent, and the timeline of attention events, actions, goals and escapes."""
        path = os.path.join(self.rundir, "decisions.jsonl")
        try:
            size = os.path.getsize(path)
            with open(path, "rb") as f:
                f.seek(max(0, size - 8_000_000))     # (~the last 8 hours)
                lines = f.read().decode("utf-8", "replace").splitlines()[1:]
        except OSError as e:
            return f"no decision log ({e})"
        recs = []
        for l in lines:
            try:
                recs.append(json.loads(l))
            except ValueError:
                pass
        if not recs:
            return "the decision log is empty"
        if args:
            m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", args[0])
            if not m:
                return "usage: why [HH:MM[:SS]] (today; default: the last escape, emergency or trip end)"
            lt = time.localtime()
            t = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, int(m.group(1)), int(m.group(2)),
                             int(m.group(3) or 0), 0, 0, -1))
        else:
            notable = [d for d in recs if d.get("kind") in ("escape", "plan_end", "goal_failed")
                       or (d.get("kind") == "attention" and d.get("what") in ("emergency", "emergency_loop"))]
            if not notable:
                return "nothing notable in the recent log: give a time (why HH:MM:SS)"
            t = notable[-1]["t"]
        win = [d for d in recs if t - 40 <= d.get("t", 0) <= t + 8]
        if not win:
            return f"nothing in the log around {time.strftime('%H:%M:%S', time.localtime(t))}"

        def hm(x):
            return time.strftime("%H:%M:%S", time.localtime(x))
        hp = [(d["t"], d["hp"]) for d in win if d.get("hp") and d["hp"][1]]
        lo = min(hp, key=lambda x: x[1][0]) if hp else None
        dft = next((d.get("depth") for d in reversed(win) if d.get("t", 0) <= t and d.get("depth") is not None), None)
        out = [f"Around {hm(t)} ({'town' if not dft else f'{dft * 50} ft'}), 40 s before to 8 s after:"]
        if hp:
            out.append(f"HP {hp[0][1][0]}/{hp[0][1][1]} at {hm(hp[0][0])} -> lowest {lo[1][0]} at {hm(lo[0])} -> "
                       f"{hp[-1][1][0]} at {hm(hp[-1][0])}")
        seen, adj = [], []
        for d in win:
            if d.get("kind") == "mons" and d.get("pos"):
                for y, x, n in d.get("monsters") or []:
                    if n not in seen:
                        seen.append(n)
                    if max(abs(y - d["pos"][0]), abs(x - d["pos"][1])) <= 1 and n not in adj:
                        adj.append(n)
        if seen:
            out.append("In view: " + ", ".join(seen[:12]) + (f"; adjacent at some point: {', '.join(adj[:8])}" if adj else ""))
        out.append("Timeline:")
        for d in win:
            k = d.get("kind")
            if k in self.WHY_SKIP or (k == "act" and str(d.get("cmd", "")).startswith(("walk", "custom . "))):
                continue
            if k == "attention":
                text = f"{d.get('what')}: {d.get('detail')}"
            elif k == "act":
                text = f"act{' [' + d['by'] + ']' if d.get('by') else ''}: {d.get('why') or d.get('cmd')}"
            elif k == "nav_cmd":
                if d.get("cmd") in ("status", "wait", "prep", "why", "gear", "gearcmp", "loadout", "pack", "say", "journal",
                                   "complain"):
                    continue
                text = f"{'ARCH' if d.get('role') == 'architect' else 'NAV'}> {d.get('cmd')} {' '.join(map(str, d.get('args') or []))}"
            elif k == "escape":
                text = f"ESCAPE ({d.get('escape')}): {d.get('trigger')}" + \
                    (f" -- adjacent {', '.join(d['adjacent'])}" if d.get("adjacent") else "")
            elif k in ("goal", "goal_done", "goal_failed"):
                text = f"{k}{' [' + d['by'] + ']' if d.get('by') else ''}: {d.get('goal') or ''} {d.get('detail') or ''}".strip()
            elif k in ("plan_end", "plan_start"):
                text = f"{k}: {d.get('plan')} -- {d.get('detail') or d.get('status') or ''}"
            else:
                text = f"{k}: " + str({x: v for x, v in d.items() if x not in ("t", "kind", "depth", "pos", "hp", "crop")})[:160]
            out.append(f"  {hm(d['t'])} {d['hp'][0] if d.get('hp') else '?'} HP  {text[:170]}")
        return "\n".join(out[:60])

    def prep_info(self):
        """`prep` (the user, 10-25: a planning step at a mission's start): everything a mission plan needs in one
        report -- the character, the gear review, what `plan town` would buy now, notable shop stock, where the XP
        has come from by depth, the XP-per-gold rate, standing orders, and the field notes to read."""
        w = self.w
        gold = w.ind.get("gold", [0])[0]
        out = ["PREP -- read this, then FIELD-NOTES.md, then plan the mission (town visit, trips, conditions).", ""]
        rep = self.compact(snapshot=True).split("\n")
        out += ["== Character"] + [l for l in rep[:6] if not l.startswith(("Here:", "Monsters:"))]
        out += ["", "== Gear review (`gear`)"] + self.gear_review().split("\n")
        try:
            buys, short = self.town_shopping(None, ())
            out += ["", "== `plan town` would buy now (by the prices last seen): " +
                    (", ".join(f"{n} {k} at the {self.STORE_LABEL.get(st, st)}" for _, k, st, n, _ in buys) or "nothing")
                    + ("; short: " + ", ".join(f"{n} {k}" for k, n in short) if short else "")]
        except Exception as e:                       # (a forecast problem must not hide the rest)
            out += ["", f"== `plan town` forecast unavailable ({e!r})"]
        notable = []
        now_wall = time.time()
        for st in (7, 6, 5):
            seen = self.stores_seen.get(st) or {}
            age = (now_wall - seen.get("t", now_wall)) / 60 if seen.get("t") else None
            for name, price in sorted((seen.get("prices") or {}).items(), key=lambda kv: -kv[1]):
                # (no mapping/detection devices on the test server: the user's no-crutch rule)
                if price <= max(0, gold - self.town_reserve()) and re.match(r"(potion|scroll|ring|amulet|staff|rod|wand) of",
                                                                              name) and price >= 150 and \
                        (getattr(self, "live", False) or not any(c.lower() in name for c in self.CRUTCH_DEVICES)):
                    notable.append(f"{name} {price} ({st}" + (f", seen {age:.0f} min ago" if age is not None else "") + ")")
        out += ["", "== Shop stock you could afford (Black Market 7, Magic 6, Alchemist 5; prices last seen): " +
                ("; ".join(notable[:12]) if notable else "nothing notable")]
        dep = self.rate_state().get("depth") or {}
        rows = sorted(((int(k), v[0], v[1] / 60) for k, v in dep.items() if v[1] >= 60), key=lambda r: r[0])
        out += ["", "== XP by depth (recent play): " + ("; ".join(
            f"{ft} ft {xp / mins:.0f} XP/min over {mins:.0f} min" for ft, xp, mins in rows) or "no record yet")
            + f"  [max_depth {self.orders.get('max_depth')}]"]
        r = self.xp_per_gold()
        out += [f"== XP per gold (recent play) {r}: 1000 gold is worth ~{1000 * r:.0f} XP of playing time"]
        st_ = [f"keep {', '.join(sorted(self.keep))}"] if self.keep else []
        st_ += [f"\"{x['text']}\" ({x['by']})" for x in self.standing]
        out += ["== Standing: " + ("; ".join(st_) or "none")]
        out += ["", "Then: `plan town [buy ...]`, `plan trip LO-HI until \"...\" then town`. Note your plan in the journal."]
        return "\n".join(out)

    # the Navigator's live line to the Architect (the user, m43: "the Navigator should be able to ask questions and
    # escalate issues to the Architect live during a mission. We don't want the Navigator to spam this though")
    ASK_GAP_S = 300            # one question every 5 minutes
    ASK_PER_HOUR = 4

    def ask_architect(self, text):
        text = text.strip()
        # `ask quiet TEXT` (the user, 10-28: the Navigator's quiet wait for "an extended conversation with the
        # Architect"): the question goes, and the Pilot waits somewhere quiet until the answer comes
        quiet = text.split()[:1] == ["quiet"]
        if quiet:
            text = text[len("quiet"):].strip()
        if not text:
            return {"ok": False, "error": "usage: ask [quiet] TEXT (a question or an escalation for the Architect)"}
        now = time.time()
        asks = [a for a in self.__dict__.setdefault("asks_sent", []) if now - a < 3600]
        self.asks_sent = asks
        # (the file runs/pilot/NICK/ask_unlimited lifts the limits: the user, 10-26, for "The Architect's Vacation"
        # session, when the Architect answers live all session; delete it to restore them)
        unlimited = os.path.exists(os.path.join(self.rundir, "ask_unlimited"))
        if asks and now - asks[-1] < self.ASK_GAP_S and not unlimited:
            return {"ok": False, "error": f"one question every {self.ASK_GAP_S // 60} minutes: next after "
                                          f"{time.strftime('%H:%M', time.localtime(asks[-1] + self.ASK_GAP_S))}; "
                                          "`complain` for what isn't urgent"}
        if len(asks) >= self.ASK_PER_HOUR and not unlimited:
            return {"ok": False, "error": f"{self.ASK_PER_HOUR} questions in the last hour: use `complain` (read "
                                          "after the mission)"}
        asks.append(now)
        aid = self.__dict__.get("ask_seq", 0) + 1
        self.ask_seq = aid
        rec = {"t": round(now, 1), "id": aid, "text": text, "depth_ft": self.w.depth_ft, "hp": list(self.w.hp[:2]),
               "goal": self.goal.describe() if self.goal else None}
        try:
            with open(os.path.join(self.rundir, "asks.jsonl"), "a") as f:
                f.write(json.dumps(rec) + "\n")
        except OSError as e:
            return {"ok": False, "error": f"couldn't send it ({e})"}
        self.log("nav_ask", id=aid, text=text, quiet=quiet)
        if quiet:
            out = self.request_goal(["quiet", "600"])
            if out.get("ok") and isinstance(self.goal, QuietWait):
                self.goal.wait_answer = aid
                self.goal.name = f"quiet wait for the Architect's answer (#{aid})"
                return {"ok": True, "text": f"asked the Architect (#{aid}); waiting somewhere quiet for the answer "
                                            "(10 minutes at most; a monster that moves or a hit ends it, and what it "
                                            "paused carries on)"}
            return {"ok": True, "text": f"asked the Architect (#{aid}); no quiet wait ({out.get('error', '?')}): carry "
                                        "on, the answer comes as ARCHITECT ANSWER in your reports"}
        return {"ok": True, "text": f"asked the Architect (#{aid}). The answer comes as ARCHITECT ANSWER in your "
                                    "reports (usually within a few minutes): carry on meanwhile, don't wait for it"}

    def answer_navigator(self, args):
        if self.req_role != "architect":
            return {"ok": False, "error": "answers come from the Architect"}
        if not args or not args[0].lstrip("#").isdigit():
            return {"ok": False, "error": "usage: answer ID TEXT"}
        aid, text = int(args[0].lstrip("#")), " ".join(args[1:])
        self.__dict__.setdefault("arch_answers", []).append((gnow(), aid, text))
        self.log("arch_answer", id=aid, text=text)
        self.notify("architect_answer", f"#{aid}: {text}")
        return {"ok": True, "text": f"answer #{aid} sent"}

    def price_info(self, what):
        """`price NAME|LETTER` (the user, m43: "so the Pilot knows item values, but you have no way to check?"): the
        Pilot's own valuation of a pack or worn item -- value, what a shop pays and which, the last price seen, and
        what the policy will do with it."""
        if not what:
            return "usage: price NAME|LETTER (a pack or worn item)"
        try:
            idx = self.item_index(what.strip().replace(" ", "_"))
        except ValueError as e:
            return str(e)
        it = next((i for i in self.w.items() + self.w.items(equip=True) if i["item"] == idx), None)
        if not it:
            return f"no item {what}"
        iv = self.iv(it["name"])
        cut = self.pay_cut(iv.tval)
        buyers = self.town_buyers(it) if not it.get("equip") else []
        n = max(1, iv.count or it.get("number", 1))
        # (the same type too: a Staff of Cure Light Wounds isn't the potion's 24 gold)
        word = (re.search(r"\b(Potion|Scroll|Staff|Staffs|Wand|Rod|Ring|Amulet)\b", it["name"]) or [None, ""])[1].lower()
        word = word[:-1] if word.endswith("s") and word != "staffs" else ("staff" if word == "staffs" else word)
        seen = [(st, p) for st, sv in self.stores_seen.items() for k, p in (sv.get("prices") or {}).items()
                if iv.kind and singular(iv.kind).lower() in k and (not word or k.startswith(word))]
        out = [f"{it['name']}: worth ~{iv.value} each ({'an estimate' if iv.estimate else 'known'}"
               + (f", P(irreplaceable) {iv.p_irreplaceable:.2f}" if iv.p_irreplaceable else "") + ")",
               f"a shop pays ~{iv.value * cut:.0f} each ({cut:.0%} of value)" + (f" at the "
               f"{self.STORE_LABEL.get(buyers[0], buyers[0])} ({buyers[0]})" if buyers else " -- no shop buys it")
               + (f"; x{n} = ~{iv.value * cut * n:.0f}" if n > 1 else "")]
        if seen:
            st, p = min(seen, key=lambda sp: sp[1])
            out.append(f"last seen for sale: {p} at the {self.STORE_LABEL.get(st, st)} ({st})")
        pol = "worn" if it.get("equip") else "kept (kit/kept/useful)" if not self.town_sell_count(it) else \
            "sold by plan town"
        out.append(f"the policy: {pol}")
        return "\n".join(out)

    # --- the tavern stash (the user, 10-26) --------------------------------------------------------------------
    def is_stash_item(self, name):
        # (stat restores only: a Potion of Restore Mana went into the stash in m48 -- useless to a warrior)
        return bool(re.search(r"Potions? of Restore (Strength|Intelligence|Wisdom|Dexterity|Constitution|Charisma)",
                              name)) or ("Stone to Mud" in name and "Wand" in name)

    def stash_state(self):
        st = self.__dict__.get("stash")
        if st is None:
            try:
                st = json.load(open(os.path.join(self.rundir, "stash.json")))
            except (OSError, ValueError, AttributeError):
                st = {}
            st.setdefault("items", [])
            self.stash = st
        return st

    def stash_save(self):
        try:
            json.dump(self.stash_state(), open(os.path.join(self.rundir, "stash.json"), "w"), indent=1)
        except (OSError, AttributeError):
            pass

    def stash_add(self, name):
        self.stash_state()["items"].append(name)
        self.stash_save()

    def stash_remove(self, kind):
        st = self.stash_state()
        hit = next((n for n in st["items"] if kind in n), None)
        if hit:
            st["items"].remove(hit)
            self.stash_save()

    def stash_has(self, kind):
        return any(kind in n for n in self.stash_state()["items"])

    BANK_FLOAT = 300           # gold carried out of town when a house holds the rest (no use for it in the dungeon)

    # (the user, 10-28: "is the Navigator made aware of how much time until we are Starving or without light?")
    # The lantern burns a turn of fuel a player turn, ~215 a dungeon minute with the resting/running speed-ups
    # (FIELD-NOTES: 15000 -> 7500 in ~35 dungeon minutes, m29-m30). Food: 20 a food tick every 10 player turns at
    # normal speed, 10 with slow digestion (dungeon.c:1129-1147), none in town -- 1 or 2 a player turn, so on the same
    # clock. Food runs from the hunger level's middle (the client sends the level only) down to Weak (1000).
    TURNS_PER_DMIN = 215
    FOOD_MID = {0: 750, 1: 750, 2: 1500, 3: 6000, 4: 12500, 5: 15000}

    def supply_minutes(self):
        """(food, light): dungeon minutes left counting the reserves (rations and other food; flasks), or None for a
        light that needs no fuel."""
        w = self.w
        per_turn = 1.0 if (w.flags or {}).get("slow_digest") else 2.0
        reserve = sum(self.food_value(i["name"]) * i["number"] for i in w.items(tval=TV_FOOD)
                      if "Mushroom" not in i["name"])
        food = max(0.0, self.FOOD_MID.get(w.hunger, 6000) + reserve - 1000) / (per_turn * self.TURNS_PER_DMIN)
        fuel = self.lantern_fuel()
        if fuel is None:
            light = None if any(i["tval"] == TV_LITE for i in w.items(equip=True)) else 0.0
        else:
            flasks = sum(i["number"] for i in w.items(tval=TV_FLASK))
            light = (fuel + flasks * self.FLASK_FUEL) / self.TURNS_PER_DMIN
        return food, light

    def supply_text(self):
        food, light = self.supply_minutes()
        return f"food ~{food:.0f} dungeon min, light ~{light:.0f}" if light is not None else \
            f"food ~{food:.0f} dungeon min, light permanent"

    def supply_watch(self):
        """In the dungeon: tell the Navigator once when food or light (reserves counted) falls under 15, then 5,
        dungeon minutes."""
        w = self.w
        if not w.in_dungeon:
            return
        food, light = self.supply_minutes()
        told = self.__dict__.setdefault("supply_told", set())
        for what, m, how in (("food", food, "rations"), ("light", light, "flasks of oil")):
            if m is None:
                continue
            new = [th for th in (15, 5) if m < th and (what, th) not in told]
            if new:
                told.update((what, th) for th in new)     # (both crossed at once: one notice)
                self.notify("supplies", f"{what}: ~{m:.0f} dungeon minutes left with the {how} carried -- plan to "
                                        f"be home before then (`goal recall`)")
            if m >= 20:
                told.discard((what, 15))
                told.discard((what, 5))

    @staticmethod
    def edge_dir(pos):
        """The direction that walks off the map edge from this square (MAX_HGT 66, MAX_WID 198), else None."""
        y, x = pos
        return 8 if y <= 1 else 2 if y >= MAX_HGT - 2 else 4 if x <= 1 else 6 if x >= MAX_WID - 2 else None

    def note_edge_cross(self):
        """The last walk off the town's edge into a wilderness tile: {town square, wilderness square, depth} -- the
        way a wilderness house is reached (the user, 10-27: a small house just outside town, for the live server)."""
        w = self.w
        last = self.__dict__.get("surface_last")
        if w.pos and w.depth is not None and w.depth <= 0 and not w.in_dungeon:
            if last and last[0] == 0 and w.depth < 0 and self.edge_dir(last[1]):
                self.edge_cross = {"town": list(last[1]), "wild": list(w.pos), "depth": w.depth}
            self.surface_last = (w.depth, w.pos)
        else:
            self.surface_last = None

    def house_state(self):
        if not hasattr(self, "_house"):
            try:
                self._house = json.load(open(os.path.join(self.rundir, "house.json")))
            except (OSError, ValueError):
                self._house = {}
        return self._house

    def house_save(self):
        try:
            with open(os.path.join(self.rundir, "house.json"), "w") as f:
                json.dump(self.house_state(), f, indent=1)
        except OSError:
            pass

    def banked(self):
        return int(self.house_state().get("banked", 0)) if self.house_state().get("house") else 0

    def house_info(self, args):
        """`house` (state), `house buy [Y,X]` (the Architect: the smallest house, or the one with that door),
        `house deposit [KEEP]`, `house withdraw`."""
        st = self.house_state()
        sub = args[0] if args else ""
        if not sub:
            h = st.get("house")
            if not h:
                houses = town_houses(self.w.memory) if not self.w.in_dungeon else []
                return {"ok": True, "text": "no house owned" + (f"; the smallest on the map: {houses[0]['area']} square(s), "
                                                               f"door {houses[0]['door']}" if houses else "")}
            return {"ok": True, "text": f"house: door {h['door'][0]},{h['door'][1]}, bought {h.get('bought')} for "
                                        f"{h.get('price')}; {st.get('banked', 0)} gold banked (as of {st.get('t')}); "
                                        f"{self.w.ind.get('gold', [0])[0]} carried"}
        if self.w.in_dungeon:
            return {"ok": False, "error": "the house is in town or the tile beside it"}
        if sub == "buy":
            if self.req_role != "architect":
                return {"ok": False, "error": "buying a house is the Architect's decision"}
            if st.get("house") and st.get("banked"):
                return {"ok": False, "error": f"the house at {st['house']['door']} holds {st['banked']} gold: "
                                              "`house withdraw` first"}
            houses = town_houses(self.w.memory)
            if len(args) > 1:
                m = re.match(r"^(\d+)[ ,](\d+)$", " ".join(args[1:3]))
                houses = [h for h in houses if m and h["door"] == (int(m.group(1)), int(m.group(2)))]
            if not houses:
                return {"ok": False, "error": "no such house on the town map (walls '#' round a door '0')"}
            hh = {k: (list(v) if isinstance(v, tuple) else v) for k, v in houses[0].items() if k != "inside"}
            if self.w.depth:
                # (a wilderness tile: remember how we came, the way back to it)
                cr = self.__dict__.get("edge_cross")
                if not cr or cr["depth"] != self.w.depth:
                    return {"ok": False, "error": "walk here from town (off the town's edge) before buying, so the "
                                                  "Pilot knows the way"}
                hh.update(depth=self.w.depth, cross=cr)
            g = HouseBank("buy", house=hh)
        elif sub in ("deposit", "withdraw"):
            if not st.get("house"):
                return {"ok": False, "error": "no house owned"}
            keep = int(args[1]) if sub == "deposit" and len(args) > 1 and args[1].isdigit() else None
            g = HouseBank(sub, keep=keep)
        else:
            return {"ok": False, "error": "usage: house [buy [Y,X] | deposit [KEEP] | withdraw]"}
        g.by_navigator = self.req_role != "architect"
        self.set_goal(g)
        return {"ok": True, "goal": g.describe()}

    def tavern_entrance(self):
        """The tavern's '8' on the town map (remembered in stash.json)."""
        st = self.stash_state()
        if not st.get("entrance") and not self.w.depth:
            q = next((q for q, ch in self.w.memory.items() if ch == "8"), None)
            if q:
                st["entrance"] = list(q)
                self.stash_save()
        return tuple(st["entrance"]) if st.get("entrance") else None

    def stash_wanted(self):
        """The Restore kind a drained STR/DEX/CON needs, if the pack lacks it and the tavern has it."""
        for stat, (cur, top) in (self.seen_drained or {}).items():
            if stat in self.STAT_FULL and cur < top:
                kind = f"Restore {self.STAT_FULL[stat]}"
                if not any(kind in i["name"] for i in self.w.items()) and self.stash_has(kind):
                    return kind
        return None

    def redundant_worn(self):
        """[(item, flags, other slot letters)]: worn rings and amulets with no AC or pluses whose every ability
        another worn piece gives too (Dive04's Ring of Resist Cold beside its Leather of Resistance)."""
        flags = self.w.flags or {}
        out = []
        for it in self.w.items(equip=True):
            L = self.EQUIP_LETTER[it["item"] - 24] if 24 <= it["item"] < 24 + len(self.EQUIP_LETTER) else "?"
            gives = [f for f, sl in flags.items() if L in (sl or "")]
            if it["tval"] in (40, 45) and gives and all((flags.get(f) or "").replace(L, "") for f in gives) \
                    and not re.search(r"\[[+-]?\d+|\([+-]\d+", it["name"]):
                out.append((it, gives, sorted({c for f in gives for c in (flags.get(f) or "") if c != L})))
        return out

    def gear_character(self):
        """The character for the gear evaluator (geareval.py): the sheet's stats, HP and AC, the worn gear (with each
        piece's weight from the inventory), the sheet's abilities, the consumables the simulator uses."""
        w = self.w
        worn = {}
        for i in w.items(equip=True):
            it = geareval.Item(i["name"], i["tval"], i["weight"] // max(1, i.get("number", 1)))
            if it.slot:
                worn.setdefault(it.slot, []).append(it)
        stats = {n: (w.ind.get(f"stat{k}") or [3])[0] for k, n in enumerate(self.STAT_NAMES)}
        flags = {("SEE_INVIS" if f == "see_invis" else f.upper()) for f, on in (w.flags or {}).items() if on}

        def n(word, tv):
            return sum(i["number"] for i in w.items(tval=tv) if word in i["name"])
        staff = next((i for i in w.items(tval=55) if "Teleportation" in i["name"]), None)
        m = re.search(r"\((\d+) charges?\)", staff["name"]) if staff else None
        inv = dict(ccw=n("Cure Critical", TV_POTION), csw=n("Cure Serious", TV_POTION), clw=n("Cure Light", TV_POTION),
                   phase=n("Phase Door", TV_SCROLL), tele=n("Teleportation", TV_SCROLL), staff=int(m.group(1)) if m else 0,
                   wor=n("Word of Recall", TV_SCROLL), speed=n("Speed", TV_POTION), berserk=n("Berserk", TV_POTION),
                   hero=n("Heroism", TV_POTION))
        depth = int(self.orders.get("max_depth", 0)) or (self.deepest_ft or 500)
        return geareval.Character(w.clvl, stats, w.hp[1], (w.ind.get("armor") or [0])[0] or 0, worn, flags=flags,
                                  depth_ft=depth, inv=inv, pack_weight=sum(i["weight"] for i in w.items()))

    def gear_eval(self, items, n=10, no_loss=False):
        """The item slot evaluator on these pack items (or names): geareval.compare_slot. Cached per item and gear."""
        ch = self.gear_character()
        cands = [geareval.Item(i["name"], i["tval"], i["weight"] // max(1, i.get("number", 1))) if isinstance(i, dict)
                 else geareval.Item(i) for i in items]
        key = (tuple(c.name for c in cands), tuple(sorted(i.name for v in ch.worn.values() for i in v)),
               tuple(sorted(ch.sheet["stats"].items())), ch.clvl, ch.depth_ft, no_loss, n)
        cache = self.__dict__.setdefault("gear_eval_cache", {})
        if key not in cache:
            try:
                killed = set(json.load(open(os.path.join(self.rundir, "uniques_killed.json"))))
            except (OSError, ValueError):
                killed = set()
            cache[key] = geareval.compare_slot(ch, cands, n=n, no_loss=no_loss, skip=killed,
                                               decisions=os.path.join(self.rundir, "decisions.jsonl"),
                                               xp_per_gold=self.xp_per_gold(),
                                               mix=geareval.load_mix(os.path.join(self.rundir, "damage_mix.json")))
        return cache[key]

    def loadout_info(self, shops=False):
        """`loadout [shops]`: the optimizer's best few loadouts from the pack (and shop stock) against what's worn."""
        w = self.w
        ch = self.gear_character()
        pool = [geareval.Item(i["name"], i["tval"], i["weight"] // max(1, i.get("number", 1))) for i in w.items()
                if i["tval"] in geareval.SLOT_OF_TVAL and i["tval"] not in (TV_LITE, 19) and self.iv(i["name"]).known
                and not re.search(r"\{(cursed|worthless|broken|terrible)", i["name"])]
        budget = 0
        if shops:
            budget = max(0, w.ind.get("gold", [0])[0] - self.town_reserve())
            for store, st in sorted(self.stores_seen.items()):
                for name, price in (st.get("prices") or {}).items():
                    it = geareval.Item(name)
                    if it.slot and it.slot not in ("light", "bow") and price <= budget:
                        it.price, it.store = price, store
                        pool.append(it)
        try:
            killed = set(json.load(open(os.path.join(self.rundir, "uniques_killed.json"))))
        except (OSError, ValueError):
            killed = set()
        try:
            res = geareval.optimize(ch, pool, budget=budget, n=10, skip=killed,
                                    decisions=os.path.join(self.rundir, "decisions.jsonl"),
                                    xp_per_gold=self.xp_per_gold(),
                                    mix=geareval.load_mix(os.path.join(self.rundir, "damage_mix.json")))
        except Exception as e:
            return f"loadout optimizer failed: {e!r}"
        head = (f"loadout: {res['searched']['loadouts']} loadouts of one or two slot changes searched (pack"
                + (f" + shop stock within {budget} gold" if shops else "") + "; every ability and resist worn is kept; "
                "the best few simulated). Slays, brands and criticals aren't simulated.")
        if len(res["options"]) == 1:
            return head + "\nnothing to try: no loadout keeps your abilities and resists and looks better on paper"
        out = [head, geareval.report(res)]
        if res["best"] != "current":
            out.append("to do: " + "; ".join((f"buy {a} ({p} g), then " if p else "") + f"wear {a}"
                                             for a, _, p in res["changes"][res["best"]] if a))
        return "\n".join(out)

    def gear_better(self, it):
        """(the evaluator's chosen option, (item, replaced)) when wearing this identified pack item beats what's worn
        (town only: a run takes ~2-3 s; never one that loses Free Action, See Invisible, resist blindness or
        confusion, hold life -- geareval.NO_LOSS), else None."""
        w = self.w
        if w.depth or w.in_dungeon or it.get("equip") or it["tval"] not in geareval.SLOT_OF_TVAL or \
                it["tval"] == TV_LITE or re.search(r"\{(cursed|worthless|broken|terrible)", it["name"]) or \
                not self.iv(it["name"]).known or (self.flavour_of(it) or {}).get("junk"):
            return None
        try:
            # (nothing it could improve -- damage, AC, HP, speed, an ability -- no simulation: most loot)
            ch = self.gear_character()
            gi = geareval.Item(it["name"], it["tval"], it["weight"] // max(1, it.get("number", 1)))
            cur = ch.derive()
            if not gi.slot or not any(
                    (d["dmg"] > cur["dmg"] or d["ac"] > cur["ac"] or d["mhp"] > cur["mhp"] or d["speed"] > cur["speed"]
                     or d["flags"] - cur["flags"])
                    for d in (ch.derive(ch.swap(gi, j)) for j in range(2 if gi.slot == "ring" else 1))):
                return None
            res = self.gear_eval([it], no_loss=True)
        except Exception as e:                 # (the evaluator must not stop the town visit)
            self.log("note", text=f"gear evaluator failed on {it['name']}: {e!r}")
            return None
        if res["best"] == "current":
            return None
        self.log("gear_eval", item=it["name"], best=res["best"], score={k: round(v, 3) for k, v in res["score"].items()})
        return res["best"], res["swaps"][res["best"]]

    def gear_review(self):
        """Gear as a whole, for the between-mission step: abilities had and missing, worn pieces whose abilities
        another piece already gives (a free slot), pack items better than worn, and shop stock (as last seen) that
        would improve a slot within the gold the essentials leave. Read-only: it changes nothing."""
        w = self.w
        worn, pack = w.items(equip=True), w.items()
        flags = w.flags or {}
        gold = w.ind.get("gold", [0])[0]
        spare = gold - self.town_reserve()
        r = self.xp_per_gold()
        out = [f"Gold {gold} ({max(0, spare)} beyond the essentials' reserve); AC {(w.ind.get('armor') or [0])[0]}; "
               f"XP per gold (recent play) {r}: 1000 gold costs ~{1000 * r:.0f} XP of playing time"]
        have = [lab for f, lab in self.GEAR_WANTED if flags.get(f)]
        miss = [lab for f, lab in self.GEAR_WANTED if not flags.get(f)]
        out.append("Abilities: " + (", ".join(have) or "none") + " | missing, most wanted first: " +
                   (", ".join(miss[:8]) or "none"))

        def letter(it):
            return self.EQUIP_LETTER[it["item"] - 24] if 24 <= it["item"] < 24 + len(self.EQUIP_LETTER) else "?"
        # worn pieces whose every ability is given by another piece too, and no AC or pluses of their own
        free = [(it, f"{letter(it)}) {it['name']}: {', '.join(gives)} also from {', '.join(o + ')' for o in others)}")
                for it, gives, others in self.redundant_worn()]
        if free:
            out.append("Redundant (the slot is free for something else): " + "; ".join(t for _, t in free))
        # the pack, against what's worn
        gl = self.gear_line()
        out.append(gl)
        # shops, as last seen
        ideas = []
        worn_ac = {}
        for slot, tvals, k in self.SLOTS:
            on = [i for i in worn if i["tval"] in tvals]
            worn_ac[slot] = (min((self.armour_ac(i["name"]) or 0) for i in on) if len(on) >= k else -1,
                             any(letter(i) in "".join(str(v or "") for v in flags.values()) for i in on), on)
        free_tv = {it["tval"] for it, _ in free}
        for store, st in sorted(self.stores_seen.items()):
            mult = 1
            for name, price in (st.get("prices") or {}).items():
                if price > max(0, spare):
                    continue
                # (with the exact buy line: m41 bought "set_of_leather_gloves" and got the plain [1,+0] for 5 gold,
                # not the [1,+5] suggested -- the cheapest line of a name is taken)
                lab = f"{name} for {price} at the {self.STORE_LABEL.get(store, store)} ({store}) " \
                      f"[`buy {store}/{name.replace(' ', '_')}@{int(price * 1.1)}`]"
                if name.startswith(("ring of", "amulet of")):
                    tv = 45 if name.startswith("ring") else 40
                    gives = self.jewel_gives(name) - {f for f, sl in flags.items() if sl}
                    pr = re.search(r"protection \[\+(\d+)\]", name)
                    slot_free = tv in free_tv or sum(1 for i in worn if i["tval"] == tv) < (2 if tv == 45 else 1)
                    if slot_free and (gives or pr):
                        ideas.append(lab + (f": {', '.join(sorted(gives))}" if gives else f": +{pr.group(1)} AC")
                                     + " (in the free slot)")
                    elif gives & {"free_act", "see_invis", "res_pois", "hold_life"}:
                        ideas.append(lab + f": {', '.join(sorted(gives))} (needs a slot)")
                    continue
                slot = next((sl for key, sl in self.SHOP_SLOT if key in name), None)
                ac = self.armour_ac(name)
                if not slot or ac is None or slot not in worn_ac:
                    continue
                ac_on, gives_flags, on = worn_ac[slot]
                if gives_flags or (on and self.is_artifact(on[0]["name"])):
                    continue              # (the worn piece gives an ability: AC alone isn't worth losing it)
                if ac > ac_on + 2:
                    ideas.append(lab + f": AC {ac} vs {max(ac_on, 0)} worn ({slot})")
        out.append("Shop ideas (prices last seen): " + ("; ".join(ideas[:8]) if ideas else "none within the gold"))
        # stats and standing restores
        drained = [n for i, n in enumerate(self.STAT_NAMES) if len(w.ind.get(f"stat{i}", [])) >= 2
                   and w.ind[f"stat{i}"][0] < w.ind[f"stat{i}"][1]]
        if drained:
            out.append("Drained: " + ", ".join(drained) + " (Restore at the Alchemist ~" +
                       f"{self.price_of('Restore Strength', 5) or 480}; STR and DEX set the blows, CON the HP)")
        if not any(i["tval"] == 19 for i in worn):
            out.append("Bow slot empty (the Pilot doesn't shoot: a launcher is only worth it for its abilities)")
        return "\n".join(out)

    # ---- the compact report (what the Navigator reads after every wait) ----
    # The full report() ran to ~5 KB (the pack twice, every order, a 23 x 67 map
    # even in town); the Navigator read it 100+ times a mission. This one keeps
    # what decisions turn on and shows the rest only when it changes; `status
    # full` gives the old one (the user, 2026-10-22).
    CURE_ABBR = {"Cure Critical Wounds": "CCW", "Cure Serious Wounds": "CSW", "Cure Light Wounds": "CLW"}
    ESCAPE_ABBR = {"Phase Door": "Phase", "Word of Recall": "WoR", "Teleportation": "Tele",
                   "Teleport Level": "TeleLevel", "Deep Descent": "DeepDescent"}

    @staticmethod
    def short(name):
        """'5 Potions of Heroism {75% off}' -> '5 Potions of Heroism' ('a '/'an ' dropped)."""
        n = re.sub(r"\s*\{\d+% off\}", "", name)
        return re.sub(r"^(a|an) ", "", n)

    @staticmethod
    def kind_of(name):
        """'3 Potions of Cure Critical Wounds {25% off}' -> 'Cure Critical Wounds'."""
        m = re.search(r"(?:Potions?|Scrolls?|Rations?|Flasks?) of ([^{(]+)", name)
        return m.group(1).strip() if m else None

    def supply_lines(self):
        w = self.w
        cures, esc, other, devices = {}, {}, {}, []
        food = flasks = 0
        for i in w.items():
            n, k = i["number"], self.kind_of(i["name"])
            if i["tval"] in (TV_POTION, TV_SCROLL) and k:
                if k in self.CURE_ABBR:
                    cures[self.CURE_ABBR[k]] = cures.get(self.CURE_ABBR[k], 0) + n
                elif k in self.ESCAPE_ABBR:
                    esc[self.ESCAPE_ABBR[k]] = esc.get(self.ESCAPE_ABBR[k], 0) + n
                elif k == "Satisfy Hunger":
                    food += n
                else:
                    other[k] = other.get(k, 0) + n
            elif i["tval"] == TV_FOOD and "Mushroom" not in i["name"]:
                food += n
            elif i["tval"] == TV_FLASK:
                flasks += n
            elif i["tval"] in (55, 65, 66):
                f = self.flavour_of(i)
                devices.append(self.short(i["name"]) + (f" (= {f['kind']})" if f else ""))
        for d in devices:
            m = re.match(r"(Staff|Rod|Wand) of Cure Light Wounds \((\d+) charges\)", d)
            if m:
                cures["staff CLW"] = int(m.group(2))
        worn_lite = next((i for i in w.items(equip=True) if i["tval"] == TV_LITE), None)
        lite = worn_lite or self.best_light()
        lt = re.search(r"with (\d+) turns", lite["name"]) if lite else None
        # (m40: "Light 408" while no light was worn and the fuller lantern sat in the pack)
        light = ("none" if not lite else (lt.group(1) if lt else "permanent")) + \
            ("" if worn_lite or not lite else " (off, in the pack)") + \
            (f" +{flasks} flask{'s' if flasks != 1 else ''}" if flasks else "")
        out = ["Cures " + (" · ".join(f"{k} {v}" for k, v in cures.items()) or "NONE")
               + " | Escapes " + " · ".join(f"{k} {esc.get(k, 0)}" for k in ("Phase", "WoR"))
               + "".join(f" · {k} {v}" for k, v in esc.items() if k not in ("Phase", "WoR"))
               + f" | Food {food} | Light {light}" + (f" ({self.supply_text()})" if w.in_dungeon or not w.depth else "")
               + (f" | RECALL PENDING ({gnow() - w.recall_pending_t:.0f} s; 8-23 s)" if w.recall_pending else "")]
        extra = [f"{k} {v}" for k, v in other.items()] + [d for d in devices if "Cure Light Wounds" not in d]
        if extra:
            out.append("Also: " + " · ".join(extra))
        return out

    def compact(self, news_since=None, map_r=9, snapshot=False):
        w, ind, now = self.w, self.w.ind, gnow()
        lines = []
        where = ("Town (" + {True: "day", False: "night", None: "day/night?"}[w.is_day()] + ")") if not w.depth \
            else f"{w.depth_ft} ft"
        lines.append(f"{ind.get('hist_name_', '?')} L{w.clvl} HP {w.hp[0]}/{w.hp[1]} · {where} · "
                     f"{ind.get('gold', [0])[0]}g" + (f" (+{self.banked()} banked)" if self.banked() else "")
                     + f" · max {self.orders.get('max_depth')}ft · "
                     f"{time.strftime('%H:%M:%S')} · goal: {self.goal.describe() if self.goal else 'none'}"
                     + (" · TIME FROZEN (test server: nothing moves until it's thawed)" if frozen() else "")
                     + self.escape_line())
        if self.plan:
            lines.append("Plan: " + self.plan.describe())
        aa = [a for a in self.__dict__.get("arch_answers", []) if gnow() - a[0] < 600]
        if aa:
            lines.append("ARCHITECT ANSWER(S): " + " | ".join(f"#{i} {time.strftime('%H:%M:%S', _lt(t))} {m}"
                                                               for t, i, m in aa))
        if self.unanswered:
            lines.append("USER MESSAGE(S) NOT YET ANSWERED (reply with say): " + " | ".join(
                f"{time.strftime('%H:%M:%S', _lt(t))} {m}" for t, m in self.unanswered))
        drained = {n for n, (cur, top) in (self.seen_drained or {}).items() if cur < top}
        stats = " ".join(f"{s} {v[0] if v[0] <= 18 else '18/%02d' % (v[0] - 18)}{'↓' if s in drained else ''}"
                         for s, v in zip(self.STAT_NAMES, (ind.get(f"stat{i}", [0]) for i in range(6))))
        cond = [k for k in ("blind", "confused", "afraid", "poisoned", "cut", "stun") if w.flag(k)]
        hunger = {0: "Weak", 1: "Weak", 2: "Hungry", 3: "Fed", 4: "Full", 5: "Gorged"}.get(w.hunger, w.hunger)
        wt = self.weapon_table()
        wield = next(((n, b, d) for n, b, d, eq in wt if eq), None) if wt else None
        spd = int(ind.get("speed", [0])[0] or 0)
        lines.append(f"{stats} · {hunger}" + (f" · {', '.join(cond).upper()}" if cond else "")
                     + (" · resting" if w.resting else "") + (f" · speed {spd:+d}" if spd else "")
                     + (f" · {re.sub(r' [(].*', '', self.short(wield[0]))} {wield[1]} blows ~{wield[2]:.0f}"
                        if wield else ""))
        lines += self.supply_lines()
        here = (w.standing_on or "unknown (under @)") + \
            (f" (item: {w.floor})" if w.floor else "") + (f" (arrived by {w.arrived_by})" if w.arrived_by else "")
        stairs = sorted(w.find("<>"), key=w.dist)[:3]
        lines.append(f"Here: {here}" + (" | Stairs " + ", ".join(f"{w.memory[q]} {q[0]},{q[1]} ({w.dist(q)})"
                                                                  for q in stairs) if stairs else " | no stairs known"))
        if w.monsters:
            seen = {}
            for y, x, r in w.monsters:
                seen.setdefault(r.name, []).append((y, x, r))
            parts = []
            for n, v in sorted(seen.items(), key=lambda kv: min(w.dist(m[:2]) for m in kv[1])):
                r = v[0][2]
                ds = sorted(w.dist(m[:2]) for m in v)
                zz = sum(1 for y, x, _ in v if self.is_asleep(y, x))
                why = self.danger_why(r)
                parts.append(f"{n}{' ×%d' % len(v) if len(v) > 1 else ''} (L{r.level}"
                             + (", UNIQUE" if "UNIQUE" in r.flags else "")
                             + f", {ds[0]}{'-%d' % ds[-1] if len(ds) > 1 and ds[-1] != ds[0] else ''} away"
                             + ((", asleep" if zz == len(v) else f", {zz} asleep") if zz else "")
                             + (f", DANGER: {why[:60]}" if why else "") + ")")
            lines.append("Monsters: " + "; ".join(parts))
        else:
            lines.append("Monsters: none")
        # items: the server's list (names) and the squares near us ($ grouped)
        names = [l.strip()[2:].strip() for l in (w.itemlist or [])[1:]]
        # (known junk left out: the user, 10-25 -- the Pilot destroys it when it passes over it at a quiet moment)
        names = [n for n in names if not self.is_junk_name(n)]
        sq = sorted((q for q in self.resolve_target("item") if w.memory.get(q, "?") not in "0123456789"),
                    key=w.dist)[:10] if w.pos else []          # (not shop and house doors)
        gold = [q for q in sq if w.memory.get(q) == "$"]
        rest = [q for q in sq if w.memory.get(q) != "$"][:6]
        gd = sorted(map(w.dist, gold))
        # (the nearest pile's square: m49's Navigator guessed one from the map for `goal fetch`)
        bits = ([f"$ ×{len(gold)} ({gd[0]}" + (f"-{gd[-1]}" if gd[-1] != gd[0] else "")
                 + f"; nearest {gold[0][0]},{gold[0][1]})"] if gold else []) + \
            [f"{w.memory.get(q, '?')} {q[0]},{q[1]} ({w.dist(q)})" for q in rest]
        if names or bits:
            lines.append("Items: " + (", ".join(names[:8]) or "-") + (" | near: " + ", ".join(bits) if bits else ""))
        # the map: dungeon only, a square crop (distance is the same in every
        # direction: radius 9 shows everything within 9 moves)
        if w.depth and w.rows and w.pos:
            y0, x0 = w.pos
            ys = range(max(0, y0 - map_r), min(len(w.rows), y0 + map_r + 1))
            xa, xb = max(0, x0 - map_r), x0 + map_r + 1
            lines.append(f"Map (@ {y0},{x0}; rows {ys[0]}-{ys[-1]}, cols {xa}-{xb - 1}):")
            lines += [f"{y:2d}|" + w.rows[y][xa:xb].rstrip() for y in ys]
        sts = self.structures_here() if w.in_dungeon else []
        if sts:
            lines.append("Structures: " + "; ".join(
                f"{st['kind']} {Y},{X}" + ("" if st["sure"] else " (likely)") +
                (f", door {self.room_door(Y, X)[0]},{self.room_door(Y, X)[1]}" if self.room_door(Y, X) else
                 ", searched" if all((w.level_t, r) in self.searched for _, r in structures.door_spots(Y, X)) else "")
                for Y, X, st in sts))
        lines += self.belief_lines()
        recent = [e for e in self.news if (e["t"] > news_since if news_since is not None
                                           else now - e["t"] < 600)][-8:]
        if recent:
            lines.append("News: " + " | ".join(
                f"{time.strftime('%H:%M:%S', _lt(e['t']))} {e['what']}: {e['detail']}" for e in recent))
        if w.depth and (w.monsters or w.hp[0] < w.hp[1]):
            msgs = w.recent(10)[-6:]
            if msgs:
                lines.append("Msgs: " + " | ".join(msgs))
        sn = getattr(self, "since", None)
        if sn:
            lo = sn["min_hp"]
            mons = sorted(sn["mons"].items(), key=lambda kv: -kv[1])
            bits = []
            if lo and lo[0] < lo[1]:
                bits.append(f"low HP {lo[0]}/{lo[1]} at {time.strftime('%H:%M:%S', _lt(lo[2]))}")
            if mons:
                bits.append("seen " + ", ".join(f"{n} ×{k}" if k > 1 else n for n, k in mons[:8]))
            if sn["uniques"]:
                bits.append("UNIQUES " + ", ".join(sorted(sn["uniques"])))
            if bits:
                lines.append(f"Since last ({self.ago(now - sn['t'])}): " + "; ".join(bits))
            if news_since is not None:
                self.since = {"t": now, "min_hp": (w.hp[0], w.hp[1], now) if w.hp[1] > 1 else None,
                              "mons": {}, "uniques": set()}
        if w.depth:
            xt = getattr(self, "exp_t", None)
            lines.append("Progress: " + (f"XP {self.ago(now - xt)} ago" if xt else "no XP yet")
                         + (f" · level {self.ago(now - w.level_t)}" if w.level_t else "")
                         + (f" · goal {self.ago(now - getattr(self, 'goal_t', now))}" if self.goal else ""))
        lines += self.compact_changes(snapshot)
        return "\n".join(lines)

    def compact_changes(self, snapshot=False):
        """What changed since the Navigator's last report: equipment, the
        non-consumables in the pack (with letters), weapons, abilities, empty
        slots, changed orders, audit differences. All of it on an explicit
        `status` (snapshot) and the first time; a wait report gets changes only
        (90 of mission 22's 113 reports came with waits)."""
        w = self.w
        cons = (TV_POTION, TV_SCROLL, TV_FOOD, TV_FLASK)
        now = {
            "Equip": [f"{chr(65 + k)}) {self.short(i['name'])}" for k, i in enumerate(w.items(equip=True))],
            "Pack (not consumables)": [f"{chr(97 + i['item'])}) {self.short(self.show(i))}" for i in w.items()
                                       if i["tval"] not in cons and i["tval"] not in (55, 65, 66)],
            "Weapons": [f"{'WIELDED ' if eq else ''}{self.short(n)} {b} blows ~{d:.0f}"
                        + (f" (~{weapon_damage(n, b, weapon_brand(n)[1]):.0f} vs not resisting {weapon_brand(n)[0]})"
                           if weapon_brand(n) else "")
                        + (" (pluses unknown: identify it)" if re.search(r"\{(good|excellent|special|magical)", n)
                           and not re.search(r"\([+-]\d+,", n) else "")
                        for n, b, d, eq in self.weapon_table()],     # (always the wielded one: with
            # the others sold in town the list went empty and the report said "Weapons: none", m27/m29/m31)
            "Abilities": [k for k, v in (w.flags or {}).items() if v and k not in ("stealth", "search", "infra", "tunnel")],
            "Gear": [self.gear_line()[len("Gear: "):]],
            "Orders changed": [f"{k}={v}" for k, v in self.orders.items()
                               if k in DEFAULT_ORDERS and str(v) != str(DEFAULT_ORDERS[k])],
            "Audit differences": [f"{k} {n}" for k, n in self.audit_counts.items()],
        }
        prev = None if snapshot else getattr(self, "compact_prev", None)
        self.compact_prev = now
        # (a burning lantern's turns and a staff's charges change all the time:
        # not a change worth a line)
        def norm(v):
            return [re.sub(r"\(with \d+ turns of light\)|\(\d+ charges?\)", "", t).strip() for t in v]
        out = []
        for k, v in now.items():
            if prev is None:
                if v:
                    out.append(f"{k}: " + "; ".join(v))
                continue
            if norm(v) == norm(prev.get(k, [])):
                continue
            if k in ("Equip", "Pack (not consumables)"):
                # (both carry letters now, which shift: compare the names)
                strip = lambda t: norm([t.split(") ", 1)[-1]])[0]
                old = {strip(t) for t in prev.get(k, [])}
                new = {strip(t) for t in v}
                ch = [f"+{t}" for t in v if strip(t) not in old] + [f"-{t}" for t in sorted(old - new)]
                if ch:
                    out.append(f"{k} changed: " + "; ".join(ch))
            else:
                out.append(f"{k}: " + ("; ".join(v) or "none"))
        if prev is None and not getattr(self, "compact_hinted", False):
            self.compact_hinted = True
            out.append("(this is the compact report: `status full` for everything; `pack`, `equip`, `orders`, "
                       "`map [R]` for one part)")
        return out

    def report(self, rows=11, cols=33, news_since=None):
        w = self.w
        ind = w.ind
        lines = []
        stats = " ".join(f"{s}:{v[0] if v[0] <= 18 else '18/%02d' % (v[0] - 18)}"
                         for s, v in zip(("STR", "INT", "WIS", "DEX", "CON", "CHR"),
                                         (ind.get(f"stat{i}", [0]) for i in range(6))))
        lines.append(f"{ind.get('hist_name_', '?')} the {ind.get('race_', '?')} {ind.get('class_', '?')}, "
                     f"level {w.clvl}" + (f" (max {ind['level'][0]})" if len(ind.get('level', [])) > 1 and ind['level'][0] != w.clvl else "") + f", HP {w.hp[0]}/{w.hp[1]}, "
                     f"{('Town (' + {True: 'day', False: 'night', None: 'day/night?'}[w.is_day()] + ')') if not w.depth else str(w.depth_ft) + ' ft'}, gold {ind.get('gold', [0])[0]}, "
                     f"blows {ind.get('skills2', ['?'])[0]}, speed {ind.get('speed', [0])[0]}"
                     f" | now {time.strftime('%H:%M:%S')} | Pilot v{VERSION}")   # (the Navigator has no clock of its own)
        cond = [k for k in ("blind", "confused", "afraid", "poisoned", "cut", "stun") if w.flag(k)]
        hunger = {0: "Weak", 1: "Weak", 2: "Hungry", 3: "Fed", 4: "Full", 5: "Gorged"}.get(w.hunger, w.hunger)
        lines.append(f"{stats}  | {hunger}" + (f" | {', '.join(cond)}" if cond else "")
                     + (" | resting" if w.resting else ""))
        # (after a login the map shows @ over whatever is there: mission 21 stood
        # on a '<' reported as floor/unknown)
        lines.append(f"Standing on: {w.standing_on or 'unknown (the map shows @ over it until you step off)'}"
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
                + "  -- `goal fetch Y,X`")
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
                     + (f" | RECALL PENDING (read {gnow() - w.recall_pending_t:.0f} s ago; it takes "
                        "15-34 turns, 8-23 s)" if w.recall_pending else "")
                     + f" | max_depth {self.orders.get('max_depth')}"
                     + (f" | drained: {', '.join(drained)}" if drained else ""))
        if self.unanswered:
            # (mission 15: a message sent before the Navigator's first wait was
            # only seen 4 minutes later in the news)
            lines.insert(1, "USER MESSAGE(S) NOT YET ANSWERED (reply with say): " + " | ".join(
                f"{time.strftime('%H:%M:%S', _lt(t))} {m}" for t, m in self.unanswered))
        wt = self.weapon_table()
        if wt:
            lines.append("Weapons (blows, avg damage per round at your STR/DEX): " + "; ".join(
                f"{'WIELDED ' if eq else ''}{n} {b} blows ~{d:.0f}"
                + (f" (~{weapon_damage(n, b, weapon_brand(n)[1]):.0f} vs monsters not resisting "
                   f"{weapon_brand(n)[0]})" if weapon_brand(n) else "")
                + (" (+ x2-3 vs its slain race)" if re.search(r"\bof \*?Slay ", n) else "")
                + (" (pluses unknown: identify it, it may be much better)"
                   if re.search(r"\{(good|excellent|special|magical)", n) and not re.search(r"\([+-]\d+,", n) else "")
                for n, b, d, eq in wt))
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
                                           else gnow() - e["t"] < 600)][-12:]
        if recent:
            lines.append("Since last report: " + " | ".join(
                f"{time.strftime('%H:%M:%S', _lt(e['t']))} {e['what']}: {e['detail']}" for e in recent))
        lines.append("Recent messages: " + " | ".join(w.recent(30)[-12:]))
        here = self.structures_here() if w.in_dungeon else []
        if here:
            lines.append("Structures: " + "; ".join(
                f"{st['kind']} centred {Y},{X}" + ("" if st["sure"] else " (likely)") +
                (f" - door at {self.room_door(Y, X)[0]},{self.room_door(Y, X)[1]}" if self.room_door(Y, X) else
                 " - searched" if all((w.level_t, r) in self.searched for _, r in structures.door_spots(Y, X)) else "")
                for Y, X, st in here))
        lines += self.since_lines(reset=news_since is not None)
        mv = self.movement_line()
        if mv:
            lines.append(mv)
        lines.append(self.gear_line())
        changed = [f"{k}={v} (default {DEFAULT_ORDERS[k]})" for k, v in self.orders.items()
                   if k in DEFAULT_ORDERS and str(v) != str(DEFAULT_ORDERS[k])]
        # (Dive03 kept think_hp 0.55 for five missions without noticing)
        lines.append("Orders changed from the defaults: " + ("; ".join(changed) if changed else "none"))
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
            end = gnow() + timeout
            with pilot.att_cond:
                while not pilot.attention and gnow() < end and pilot.running:
                    pilot.att_cond.wait(min(1.0, max(0.01, end - gnow())))
                evs, pilot.attention = pilot.attention, []
            pilot.last_agent = gnow()
            out = {"ok": True, "events": evs}
            pilot.nav_view_events = [f"ATTENTION {e['what']}: {e.get('detail') or ''}" for e in evs]
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
        try:
            self.wfile.write((json.dumps(out) + "\n").encode())
        except BrokenPipeError:
            pass          # (the client gave up waiting -- pilotctl's timeout: nothing to tell it)


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
    ap.add_argument("--live", action="store_true",
                    help="live-server behaviour (default: test server). Test: mapping/detection devices are sold, not "
                         "kept (the user: no crutches the live server won't give us)")
    ap.add_argument("--hpwarn", type=int, default=5,
                    help="hitpoint_warn 0-9: below N x 10%% HP the server slows our time bubble to 1/5; the "
                         "Pilot's timers follow on its game clock (default 5, the user 2026-10-24; 0 = off)")
    args = ap.parse_args()

    nick = args.nick
    priv = os.path.join(runs, "private")
    rundir = args.rundir or os.path.join(runs, "pilot", nick.lower())
    os.makedirs(rundir, exist_ok=True)
    visuals = os.path.join(rundir, "visuals.txt")
    glyphs.write_visuals(visuals, glyphs.assign(glyphs.load_races()))
    evlog = open(os.path.join(rundir, "events.jsonl"), "a", buffering=1)
    # --hpwarn N: below N x 10% HP the server runs our time bubble at 1/5. Since 2026-10-23 the
    # Pilot's timers are on a game clock that follows it (world.gnow); before, they were
    # wall-clock, and at low HP re-plans fired between our turns (mission 7), so it ran with 0.
    # Missions run with 5 since 2026-10-24 (the user).
    client = MangClient(args.client, args.libdir, nick,
                        args.passfile or os.path.join(priv, nick.lower() + ".pass"),
                        args.host, args.port, config=args.config or os.path.join(priv, nick.lower() + ".mangrc"),
                        cwd=repo, pktlog=args.pktlog, extra_args=["--visuals", visuals, "--hpwarn", str(args.hpwarn)])
    say = lambda *a: print(time.strftime("%H:%M:%S"), *a, file=sys.stderr, flush=True)
    pilot = None
    try:
        ready = client.wait_ready()
        say(f"in the game as {nick}: {ready}")
        pilot = Pilot(client, rundir, say=say)
        pilot.hpwarn = args.hpwarn
        pilot.live = args.live
        pilot.log("options", hpwarn=args.hpwarn, live=args.live)
        orig = pilot.w._on_event
        bulky = {"map", "status", "inven", "options", "commands"}   # query replies
        # every event carries the wall clock too ('t' restarts at 0 with each
        # Pilot process: ~12 log Clerks had to align segments by hand)
        evlog.write(json.dumps({"ev": "pilot_start", "t": 0.0, "epoch": round(time.time(), 3), "nick": nick}) + "\n")
        # the query replies go to state.jsonl, thinned (the Advisor's set-piece memo, blocker 2: a
        # replay couldn't rebuild the map or the pack at second T): status every 2 s when it changes,
        # the pack whenever it changes, the map's changed rows every 10 s
        statelog = open(os.path.join(rundir, "state.jsonl"), "a", buffering=1)
        last = {"status": [0.0, None], "inven": [0.0, None], "map": [0.0, None]}

        def log_state(ev):
            # 'epoch' is the wall clock like events.jsonl's; the throttle stays on the game clock (session 8: logging
            # gnow put state.jsonl ~3 minutes behind after freezes, and a theft was searched for in the wrong minutes)
            k, now, wall = ev.get("ev"), gnow(), time.time()
            if k not in last or now - last[k][0] < {"status": 2.0, "inven": 0.0, "map": 10.0}[k]:
                return
            if k == "status":
                body = {"y": ev.get("y"), "x": ev.get("x"), "ind": ev.get("ind")}
            elif k == "inven":
                body = {"items": ev.get("items")}
            else:
                rows = ev.get("rows") or []
                prev = last[k][1] or []
                body = {"rows": {i: r for i, r in enumerate(rows) if i >= len(prev) or prev[i] != r},
                        "n": len(rows)}
                if not body["rows"]:
                    last[k][0] = now
                    return
                last[k] = [now, rows]
                statelog.write(json.dumps({"ev": k, "epoch": round(wall, 3), **body}) + "\n")
                return
            if body == last[k][1]:
                return
            last[k] = [now, body]
            statelog.write(json.dumps({"ev": k, "epoch": round(wall, 3), **body}) + "\n")

        pilot.w.c.log = lambda ev: (orig(ev), log_state(ev) if ev.get("ev") in bulky else
                                    evlog.write(json.dumps({**ev, "epoch": round(time.time(), 3)}) + "\n"))
        # disturb_near/disturb_panel: the server stops a run the moment a monster
        # in view moves, or at a sector edge (faster than our polling at run
        # speed; the Advisor's running memo). disturb_move stays as the user plays.
        for opt in ("avoid_other", "stack_force_costs", "disturb_near", "disturb_panel"):
            client.send(f"option {opt} yes")
        try:
            # the character's options, once per login (the Advisor couldn't read them from the logs)
            pilot.log("options", options=client.query("options", "options"))
        except Exception as e:
            pilot.log("note", text=f"options query failed: {e!r}")
        sock = os.path.join(rundir, "ctl.sock")
        if os.path.exists(sock):
            os.unlink(sock)
        srv = Server(sock, Handler)
        srv.pilot = pilot
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        say(f"control socket {sock}")
        pilot.notify("started", f"in the game at {pilot.w.depth} (depth), Pilot v{VERSION}")
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
