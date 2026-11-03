"""plan -- the trip plan, TripPlan (refactor-candidates E1; docs/goals-and-plans.md): `plan trip LO-HI ...`, the
Navigator's intent run by the Pilot, phase by phase (down, level by level, home), and split_specs (buy specs). The
Pilot drives it (plan_tick, request_trip, request_plan); pilot.py imports both back (P.TripPlan, P.split_specs).
"""
import collections
import json
import os
import re
import time
import types

from common import TV_SCROLL, TV_POTION, plural, one_of
from world import gnow
from goals import Wait, Explore, Dive, Recover, Flee, Recall
from town_goals import Town, TownKit, NEXT


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
        # (created on the way: refactor-candidates E5 declares them, with the values their reads assumed)
        self.xp0 = None              # the trip's XP base (the report's rate for this trip)
        self.climb_t0 = None         # home: when the climb began (3 minutes, then Word of Recall)
        self.dungeon_t0 = None       # when the trip first reached the dungeon (dmin)
        self.swarm_tele = None       # the level a breeder swarm was teleported away from
        self.clock_targets = {}      # time>HH:MM: the moment each HH:MM stands for
        self.xp_hist = []            # (t, exp, level_t) every 5 s: the quiet rule

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
                "free": lambda: p.PACK_SLOTS - len(w.items()), "levels": lambda: self.levels,
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
            if g is None or g.by_plan:
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

    # One method per step (refactor-candidates E5), in this order: the watchdogs, then the phases -- each phase step
    # tests its own phase, and down falls through to level on reaching the dungeon. Each takes the per-call ctx (w,
    # now) and returns NEXT to go on, or what tick() returns. docs/goals-and-plans.md, the trip plan.
    TRIP_STEPS = (
        "_trip_xp0",             # the trip's XP base
        "_trip_paused",          # paused for the Navigator's goal
        "_trip_recall_pending",  # a recall under way: wait for it (an escape recall: home)
        "_trip_until",           # a condition holds: home
        "_trip_climb_watch",     # home: no way up in 3 minutes: Word of Recall instead
        "_trip_level_time",      # level_min minutes on this level: done
        "_trip_leave_max",       # a done level that won't let us go: home after LEAVE_MAX
        "_trip_quiet",           # a quiet level: done
        "_trip_goal_running",    # a goal running: nothing more this tick
        "_phase_down",           # down: Word of Recall or the stairs (in the dungeon: level, this tick)
        "_phase_level",          # level: explore it, or the next one
        "_phase_home",           # home: Word of Recall or the stairs; then town (the town kit) or done
        "_phase_town",           # town: the town kit ran, done
    )

    def tick(self, p):
        """Called when no goal is running (and every 2 s under a plan goal, for the
        conditions). Returns (status, detail) when the plan ends."""
        ctx = types.SimpleNamespace(w=p.w, now=gnow())
        for name in self.TRIP_STEPS:
            r = getattr(self, name)(p, ctx)
            if r is not NEXT:
                return r
        return None

    def _trip_xp0(self, p, ctx):
        """The trip's XP base (the report's "this trip" rate: m47's Navigator wanted XP a minute per trip)."""
        w = ctx.w
        # (the trip's XP base, for the report's "this trip" rate: m47's Navigator wanted XP a minute per trip)
        if self.xp0 is None and (w.ind.get("exp") or [None])[0] is not None:
            self.xp0 = w.ind["exp"][0]
        return NEXT

    def _trip_paused(self, p, ctx):
        """Paused for the Navigator's own goal: LEAVE_MAX counts again from a resume."""
        if self.paused:
            self.leave_since = None     # (the Navigator's own goal: LEAVE_MAX counts again from a resume)
            return None
        return NEXT

    def _trip_recall_pending(self, p, ctx):
        """A recall under way (the Pilot's escape, or the plan's own): wait for it, don't start a new dive meanwhile;
        an escape's recall ends the trip (home)."""
        w = ctx.w
        if w.in_dungeon and w.recall_pending and self.phase in ("down", "level", "home") and self.went_down:
            # a recall is under way (the Pilot's escape, or the plan's own): wait for it, don't
            # start a new dive meanwhile (m24: a dive walked the pit's ring while it charged)
            if self.phase != "home":
                # (with the escape's trigger: m42's Navigator couldn't tell why its trip ended at 19:19)
                le = p.last_escape
                why = f": {le[2]} (HP {le[3][0]}/{le[3][1]})" if le and gnow() - le[0] < 60 else ""
                self.phase, self.home_why = "home", f"the Pilot's escape recall{why}"
                p.notify("plan", f"trip: a recall is under way (the Pilot's escape{why}): coming home -- "
                                 "`why` for the details", news=True)
            if p.goal is not None and p.goal.by_plan and isinstance(p.goal, (Dive, Explore)):
                p.set_goal(None)
            if p.goal is None:
                self.step = "waiting for the recall"
                p.set_goal(self.mark(Wait(3)))
            return None
        return NEXT

    def _trip_until(self, p, ctx):
        """Down or on a level in the dungeon: a condition holds (holds): home."""
        w = ctx.w
        if self.phase in ("down", "level") and w.in_dungeon:
            why = self.holds(p)
            if why:
                self.phase, self.home_why = "home", why
                p.notify("plan", f"trip: coming home ({why})", news=True)
                if p.goal is not None and p.goal.by_plan and \
                        not isinstance(p.goal, (Flee, Recover, Recall)):
                    p.set_goal(None)
        return NEXT

    def _trip_climb_watch(self, p, ctx):
        """home: no way up found in 3 minutes of climbing: Word of Recall instead."""
        w, now = ctx.w, ctx.now
        if self.phase == "home" and isinstance(p.goal, Dive) and p.goal.by_plan and \
                now - (self.climb_t0 or now) > 180 and self.value(p, "wor") >= 1 and \
                not w.recall_pending:
            p.notify("plan", "trip: no way up found in 3 minutes: reading Word of Recall instead", news=True)
            p.set_goal(None)          # (the next tick reads it)
        return NEXT

    def _trip_level_time(self, p, ctx):
        """level: level_min minutes on this level (under its exploration): done."""
        w, now = ctx.w, ctx.now
        if self.phase == "level" and isinstance(p.goal, Explore) and p.goal.by_plan and \
                self.level == w.level_t and not self.level_done and now - self.level_t0 > 60 * self.level_min:
            self.level_done = f"{self.level_min:g} minutes on it"
            p.set_goal(None)
        return NEXT

    def _trip_leave_max(self, p, ctx):
        """level: a done level that won't let us go: home after LEAVE_MAX."""
        w, now = ctx.w, ctx.now
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
                if p.goal is not None and p.goal.by_plan and \
                        not isinstance(p.goal, (Flee, Recover, Recall)):
                    p.set_goal(None)
        return NEXT

    def _trip_quiet(self, p, ctx):
        """level: a quiet level (quiet: XP a minute over QUIET_MIN) ends its exploration."""
        w, now = ctx.w, ctx.now
        quiet = self.quiet(p, now)
        if self.phase == "level" and isinstance(p.goal, Explore) and p.goal.by_plan and \
                self.level == w.level_t and not self.level_done and quiet:
            self.level_done = quiet
            p.set_goal(None)
        return NEXT

    def _trip_goal_running(self, p, ctx):
        """A goal running: nothing more this tick (the steps below pick the next goal)."""
        if p.goal is not None:
            return None
        return NEXT

    def _phase_down(self, p, ctx):
        """down: from town, Word of Recall to the planned depth or the stairs near town; from the wilderness, town
        first; in the dungeon, on to level (this tick)."""
        w = ctx.w
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
        return NEXT

    def _phase_level(self, p, ctx):
        """level: within LO-HI, the arrival protocol, then explore this level until it's done or level_min minutes
        pass; then the next level (next_dive)."""
        w, now = ctx.w, ctx.now
        if self.phase == "level":
            if w.depth == 0:
                le = p.last_escape
                lo = p.last_goal_order
                why = f": the Pilot's escape at HP {le[3][0]}/{le[3][1]}, {le[2]}" if le and gnow() - le[0] < 120 else ""
                if lo and gnow() - lo[0] < 120 and str(lo[1]).startswith("recall"):
                    # (2.48.1, m61: the Navigator's `goal recall` was reported as "the Pilot's escape")
                    why = ": " + ("your" if lo[2] != "architect" else "the Architect's") + " `goal recall`"
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
        return NEXT

    def _phase_home(self, p, ctx):
        """home: Word of Recall, or the stairs near town or without one; in town, the town kit (then town) or done."""
        w, now = ctx.w, ctx.now
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
            self.climb_t0 = self.climb_t0 or now
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
        return NEXT

    def _phase_town(self, p, ctx):
        """town: the town kit ran: done."""
        now = ctx.now
        if self.phase == "town":
            return ("done", f"home ({self.home_why}) and the town kit run; {plural(self.levels, 'level')} in "
                            f"{(now - self.t0) / 60:.0f} min")
        return NEXT

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
