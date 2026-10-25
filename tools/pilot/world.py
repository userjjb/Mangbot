"""The pilot's picture of the game, kept up to date from client events.

Everything the rules need to decide with: position, depth, map (chars and
colours), monsters on the map (named, via glyphs.py), the server's monster and
item lists, indicators (HP, hunger, ...), inventory, recent messages, and
whether we are standing on a staircase (the map only ever shows '@' there).
"""
import collections
import os
import re
import threading
import time

from glyphs import Glyphs


# --- the game clock (the time bubble: the user, 2026-10-23, after restructure step 2) -------------
# The server runs each player's time at a factor (xtra2.c base_time_factor): 1/5 below
# hitpoint_warn x 10% HP, up to ~10x while resting or running with nothing in view. Every Pilot timer
# that means game time (holds for effects, cooldowns, damage per second, how long a monster has been
# out of view) runs on this clock; timers that mean the network (an ack, a step showing up, a window
# for a reply) compare wall time, `wall_since(t)`. Logs and displayed clock times stay on the wall
# clock (`wall_of`).
#
# The clock is measured where it can be, with no server change: a worn light (not an artifact)
# loses one turn of fuel per game tick of our bubble (dungeon.c process_player_end, "Burn some
# fuel": every `time` game turns, scaled by our time factor). The fuel shows in its name ("with
# 4514 turns of light"), which the server resends at every 100th turn and on a redraw (free: no
# game time; the Pilot asks for one every few seconds in the dungeon). At factor 1 a tick takes
# TICK_S seconds (m24's pack log: 1.6 ticks/s).
# The server speeds our time up only while we rest or run with nothing in view, and slows it to a
# constant 1/5 in the HP bubble. The speed-up needs no awake monster in line of sight, seen or not, so
# the model (`set_time_factor`, from our HP) leaves it out: 1, or 1/5 in the bubble (a clock running
# fast where the game doesn't would end game timers early). The fuel measures the real rate only while
# a speed-up can apply (`set_fast_ok`): a rate averaged over seconds would otherwise carry a run's 5x
# into the fight that ended it. (While resting, the server doesn't answer a redraw: a rest is measured
# when it ends.)
TICK_S = 0.625
STALE_S = 12.0                  # wall seconds without a fuel change before the model takes over again
_CLOCK = {"wall": time.time(), "game": time.time(), "factor": 1.0, "model": 1.0, "measured": 0.0,
          "fast_ok": False, "rate": None}
_HIST = collections.deque(maxlen=4000)      # (wall, game, factor from there on)
_HIST.append((_CLOCK["wall"], _CLOCK["game"], 1.0))
_FUEL = collections.deque(maxlen=16)        # (wall, fuel): the moments the light's fuel changed
_LOCK = threading.Lock()
# The test server's time freeze (the user, 10-25): while this file exists the server processes no game turns
# (net-server.c time_frozen, with $MANGBAND_FREEZE_FILE), so our game clock stops too. `tools/freeze.sh`, the
# viewer's F key. The live server has no such file: never frozen there.
FREEZE_FILE = os.environ.get("MANGBAND_FREEZE_FILE") or \
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "testserver", "FREEZE")
FROZEN_F = 1e-6
_FROZEN = {"t": 0.0, "on": False}


def frozen():
    """The test server's time is frozen (the file checked at most twice a second)."""
    now = time.time()
    if now - _FROZEN["t"] > 0.5:
        _FROZEN["t"], _FROZEN["on"] = now, os.path.exists(FREEZE_FILE)
    return _FROZEN["on"]


def _advance(now):
    _CLOCK["game"] += (now - _CLOCK["wall"]) * _CLOCK["factor"]
    _CLOCK["wall"] = now


def _set_factor(f, now):
    if _FROZEN["on"]:
        f = FROZEN_F
    _advance(now)
    if f != _CLOCK["factor"]:
        _CLOCK["factor"] = f
        _HIST.append((now, _CLOCK["game"], f))


def gnow():
    with _LOCK:
        now = time.time()
        was = _FROZEN["on"]
        if frozen() != was:
            _set_factor(_CLOCK["model"], now)      # (frozen: FROZEN_F; thawed: the model again)
        if _CLOCK["measured"] and now - _CLOCK["measured"] > STALE_S:
            _CLOCK["measured"] = 0.0
            _set_factor(_CLOCK["model"], now)
        _advance(now)
        return _CLOCK["game"]


def set_time_factor(f):
    """The model's factor (the HP bubble, from our HP each tick). It applies at once."""
    with _LOCK:
        _CLOCK["model"] = f
        if not (_CLOCK["fast_ok"] and _CLOCK["measured"]):
            _set_factor(f, time.time())


def set_fast_ok(ok):
    """Whether the server may be speeding our time up (resting or running, nothing in view, not in the
    HP bubble). A change starts a new measurement and goes back to the model's factor at once."""
    with _LOCK:
        if ok != _CLOCK["fast_ok"]:
            now = time.time()
            _CLOCK["fast_ok"] = ok
            _CLOCK["measured"] = 0.0
            _FUEL.clear()               # (its next change starts the count)
            _set_factor(_CLOCK["model"], now)


def measured_rate():
    """The last fuel-measured rate (game seconds per wall second), whatever the mode: for the log."""
    return _CLOCK["rate"]


def time_factor():
    return _CLOCK["factor"]


def model_factor():
    return _CLOCK["model"]


def fuel_reading(fuel, now=None):
    """The worn light's fuel as the client shows it (None: no light that burns). Only a change is a
    measurement: the client's copy changes when the server sends it."""
    with _LOCK:
        now = now or time.time()
        if fuel is None:
            _FUEL.clear()
            _CLOCK["fuel_seen"] = None
            return
        if fuel == _CLOCK.get("fuel_seen"):
            return
        first = _CLOCK.get("fuel_seen") is None
        _CLOCK["fuel_seen"] = fuel
        if first:
            return                      # (when it was really sent is unknown)
        if _FUEL and (fuel > _FUEL[-1][1] or _FUEL[-1][1] - fuel > 30 * (now - _FUEL[-1][0]) + 3):
            _FUEL.clear()               # refuelled, another light, or a gap we can't read
        _FUEL.append((now, fuel))
        # the rate over the changes of the last ~12 s (one interval is +-1 tick)
        pts = [q for q in _FUEL if now - q[0] <= STALE_S]
        if len(pts) < 2 or pts[-1][0] - pts[0][0] < 1.5:
            return
        (w0, f0), (w1, f1) = pts[0], pts[-1]
        rate = (f0 - f1) * TICK_S / (w1 - w0)
        _CLOCK["rate"] = rate
        if _CLOCK["fast_ok"]:
            _set_factor(min(20.0, max(0.05, rate)), now)
            _CLOCK["measured"] = now


def wall_at(g):
    """The wall time at which the game clock read g (from the clock's history)."""
    with _LOCK:
        _advance(time.time())
        for w, g0, f in reversed(_HIST):
            if g0 <= g:
                return w + (g - g0) / f
        w, g0, f = _HIST[0]
        return w - (g0 - g)


def wall_since(g):
    """Wall seconds since the game clock read g: for timers that mean the network, not the game."""
    return time.time() - wall_at(g)


def waited(t, s):
    """At least s seconds since game time t on both clocks: for a wait on the server (a step, a run, a
    read showing up), which needs its game turns and its round trip."""
    return gnow() - t > s and wall_since(t) > s


def ghold(s):
    """A game-clock span lasting at least s wall seconds at the current factor (for deadlines on the
    network: `busy_until = gnow() + ghold(0.4)`)."""
    return s * max(1.0, _CLOCK["factor"])


def wall_of(g):
    """A game-clock time as wall time (for display)."""
    return wall_at(g)


def _lt(g):
    return time.localtime(wall_of(g))


LIGHT_FUEL = re.compile(r"\(with (\d+) turns of light\)")


def light_fuel(inven):
    """The fuel of the worn light, or None (no light worn, or one that doesn't burn: artifacts,
    Dwarven lanterns don't show turns)."""
    for it in inven or ():
        if it.get("equip") and it.get("tval") == 39:
            m = LIGHT_FUEL.search(it.get("name", ""))
            return int(m.group(1)) if m else None
    return None


FT_PER_LEVEL = 50

# Terrain the map can show under nothing else (for remembering what's under '@')
TERRAIN = set("#%.'+<>^;:*=~ 12345678")
STAIRS = "<>"


class World:
    def __init__(self, client, glyphs=None):
        self.c = client
        self.g = glyphs or Glyphs()
        self._q = collections.deque()          # events from the reader thread
        self.lock = threading.Lock()
        self.pos = None
        self.depth = None
        self.level_t = 0.0                     # when we arrived on this level
        self.arrived_by = None                 # '>' '<' 'recall' 'other'
        self.rows, self.attrs = None, None
        self.map_t = 0.0
        self.map_pos = None                    # position when the map was taken
        self.memory = {}                       # (y, x) -> terrain char seen there (this level)
        self.monsters = []                     # [(y, x, Race)]
        self.still_seen = {}                   # (y, x) -> Race: stationary monsters seen on this level
        self.monlist = []                      # [(name, count, our char)]
        self.itemlist = []                     # item list lines
        self.ind = {}
        self.status_t = 0.0
        self.ghost = False
        self.inven = []
        self.inven_t = 0.0
        self.inven_dirty = True
        self.messages = collections.deque(maxlen=300)  # (t, text) (60 lost a hunt's kill in fight spam)
        self.standing_on = None                # '<' '>' or a terrain char, if known
        self.last_stairs_cmd = None            # ('<'|'>', t) sent, awaiting the level change
        self.hits_taken = 0                    # "... hits you" style messages
        self.last_hit_t = 0.0
        self.explained_t = 0.0                # last trap/cut/poison message (HP loss that isn't a monster)
        self.monster_seen_t = 0.0             # last map with a monster on it
        self.fight_t = 0.0                     # last time we hit, missed or killed something
        self.need_redraw = False               # ask the server for a full resync (tool verb 'redraw')
        self.arrive_pos = None                 # first position on the current level
        self.daytime = None                    # from "The sun has risen/fallen" (None: not seen yet)
        self.avoid_zone = set()                # squares the planner won't enter (the Navigator's avoid zones)
        self.avoid_inside = False              # we stand inside one (its squares then only cost more)
        self.flags, self.flags_t = None, 0.0    # {flag: slots granting it} from the resist grid
        self.floor, self.floor_t = None, 0.0    # the item under us (tool query 'floor')
        self.losses = []                       # (t, message): items/gold lost or destroyed
        self.unseen = (0.0, "")                # last message from an unseen monster acting on us
        self.heard = (0.0, "")                 # last "You hear a door burst open!"
        self.hp_hist = collections.deque(maxlen=40)   # (t, hp), one per status poll
        self.pos_t = 0.0
        self.in_dungeon = None                 # see _level_kind(): the depth byte alone can't tell
        self.walked = set()                    # squares walked on this level
        self.bump_walls = {}                   # walls learned by bumping: (y, x) -> what memory had
        self.last_confirm = (0.0, "", None)    # the last yes/no prompt (a shop's "Accept N gold?")
        self.recalled = None                   # 'down'/'up' from the recall message, until the level changes
        self.recall_cancelled = False          # set on "A tension leaves"; the pilot reports and clears it
        self.recall_pending_t = 0.0
        self.recall_pending = False            # a Word of Recall is active ("becomes charged" until "yanked" or "A tension leaves")
        self.store = None                      # last store listing while inside a store
        self.store_t = 0.0
        client.log = self._on_event            # every event, from the reader thread

    # --- events ---------------------------------------------------------

    def _on_event(self, ev):
        self._q.append(ev)

    RE_ATTACK = re.compile(r" (hits|bites|claws|stings|touches|kicks|butts|crushes|engulfs|crawls on|spits on|"
                           r"gazes at|wails at|punches|grabs|fires an arrow|casts a magic missile|"
                           r"points at you and curses|breathes|misses|releases spores at) you")

    # Visible monsters' ranged attacks have no "you" in the message ("The Kobold
    # archer fires an arrow!", "The Dark hound breathes darkness."): the Advisor's
    # message study found RE_ATTACK never matched them, so HP lost to them read
    # as an unseen attacker
    RE_RANGED = re.compile(r"^The .+ (fires an? \w+|breathes \w+|casts an? (magic missile|stinking cloud|"
                           r"fearful illusion|spell, burning your eyes|[a-z ]*(bolt|ball)))")

    # An unseen monster acting on us (monster2.c names it "it"/"something")
    # (the Advisor's message catalogue, 2026-09-29: added the ~20 real unseen
    # attacks it missed -- Brain Smash, Hold, boulders, storms...; dropped
    # "concentrates", which is the monster healing or hasting itself)
    RE_UNSEEN = re.compile(r"^(It|Something) (hits|bites|claws|stings|touches|kicks|butts|crushes|engulfs|"
                           r"crawls on|spits on|gazes at|wails at|punches|grabs|breathes|casts|magically|"
                           r"mumbles|fires|points at you|commands you|drains|tries to|drools on you|"
                           r"releases spores|hurls|makes a strange noise|invokes|gestures|looks deep|"
                           r"gazes deep|stares deep|creates a mesmerising|screams|draws psychic|"
                           r"makes a high pitched shriek|teleports you|makes you)")

    # HP loss that isn't a monster (mission 5: a graze and a spiked pit read as
    # an unseen attacker)
    # Anchored (the catalogue: the old substring form matched "Your light is
    # growing faint", "Cutlass", "pitched shriek"; it missed earthquakes and hunger)
    RE_HURT_OTHER = re.compile(r"^(You found a trap|You fall into|You are impaled|You have been given|"
                               r"You have been stunned|You have been (hit|burned)|A small dart|"
                               r"You are (poisoned|enveloped|hit|bashed|crushed|severely crushed|getting weak)|"
                               r"You feel very sick|You faint|You are covered in|You are burned|You are frozen|"
                               r"You are struck|Your .* (burns|melts|freezes)|You bleed|You are bleeding|"
                               r"Oops|You starve)")

    def drain(self):
        """Apply queued events. Returns the list applied (for the pilot's triggers)."""
        out = []
        while self._q:
            ev = self._q.popleft()
            out.append(ev)
            k = ev.get("ev")
            if k == "pos":
                new = (ev["y"], ev["x"])
                if self.pos and new != self.pos:
                    # Stepped: what's under us now is whatever the map showed there
                    self.standing_on = self.memory.get(new)
                    self.store = None
                self.pos = new
                self.pos_t = gnow()
                if self.arrive_pos is None:
                    self.arrive_pos = new          # where we came onto this level
                self.walked.add(new)           # squares we've been on (safe retreat ground)
            elif k == "confirm":
                self.last_confirm = (gnow(), ev.get("prompt", ""), ev.get("answer"))
            elif k == "level":
                old = self.depth
                self.depth = ev["depth"]
                self.level_t = gnow()
                self.memory = {}
                self.walked = set()
                self.bump_walls = {}
                self.arrive_pos = None
                self.rows = None
                self.monsters, self.itemlist = [], []
                self.still_seen = {}
                sc = self.last_stairs_cmd
                if sc and gnow() - sc[1] < 5 and old is not None:
                    # Connected stairs: '>' leaves you on an up staircase and vice versa
                    self.arrived_by = sc[0]
                    self.standing_on = "<" if sc[0] == ">" else ">"
                else:
                    self.arrived_by = "other"
                    self.standing_on = None
                self.in_dungeon = self._level_kind(old, sc)
                self.recalled = None
                # (not recall_pending: the server's countdown keeps running across
                # a level change by stairs, and a second read would cancel it --
                # the game-state survey; cleared when the recall happens)
                self.last_stairs_cmd = None
            elif k == "message":
                t = ev["text"]
                self.messages.append((gnow(), t))
                km = re.match(r"You have (?:slain|destroyed|killed) (?:the )?(.+?)\.$", t)
                if km and self.still_seen:
                    dead = [q for q, r in self.still_seen.items() if r.name.lower() == km.group(1).lower()]
                    if dead and self.pos:
                        self.still_seen.pop(min(dead, key=self.dist))
                if t.startswith("You have ") or t.startswith("You see ") or "no more" in t \
                        or t.startswith("You are wearing") or t.startswith("You are wielding") \
                        or t.startswith("Was wearing") or t.startswith("You destroy") \
                        or t.startswith("You feel") or "in your pack" in t:
                    self.inven_dirty = True
                if (re.match(r"You have .*\([a-w]\)\.$", t) or t.startswith("You destroy")) and \
                        self.standing_on and self.standing_on not in TERRAIN and self.depth:
                    self.standing_on = "."    # the item underfoot is gone (report showed it after pickup)
                if t.startswith("You have found ") and " gold" in t and self.pos:
                    # gold is taken on stepping in; the report kept "Standing on: $"
                    # and the Navigator picked up again (mission 18)
                    self.standing_on = "."
                    if self.memory.get(self.pos) == "$":
                        self.memory[self.pos] = "."
                if self.RE_HURT_OTHER.search(t):
                    self.explained_t = gnow()
                if self.RE_UNSEEN.match(t):
                    self.unseen = (gnow(), t)
                elif t.startswith("You hear a door burst open"):
                    self.heard = (gnow(), t)
                if self.RE_ATTACK.search(t) or self.RE_RANGED.match(t):
                    self.hits_taken += 1
                    self.last_hit_t = gnow()
                if re.match(r"You (hit|miss|have slain|have destroyed|have killed|smite|bite|claw)", t) or \
                        re.match(r"(The|It) .* (dies|is destroyed|flees)", t):
                    self.fight_t = gnow()
                # Things that change the pack or purse behind our back (the survey:
                # mission 10's lost gold was Smeagol): resync and tell the agent
                # (+ "was eaten!": an invisible food-eater took 3 food in mission 19, unreported)
                if re.search(r"was destroyed!|was stolen|was eaten!|stole |Your pack overflows|Your purse feels lighter|"
                             r"You have no room for|destroyed!$", t):
                    self.inven_dirty = True
                    self.status_t = 0
                    self.need_redraw = True
                    self.losses.append((gnow(), t))
                if t.startswith("The sun has risen"):
                    self.daytime = True
                elif t.startswith("The sun has fallen"):
                    self.daytime = False
                if t.startswith("I see no up staircase"):
                    self.standing_on = None if self.standing_on == "<" else self.standing_on
                if t.startswith("I see no down staircase"):
                    self.standing_on = None if self.standing_on == ">" else self.standing_on
                # A second read cancels the first (server spells2.c:1191-1199)
                if t.startswith("The air about you becomes charged"):
                    self.recall_pending = True
                    self.recall_pending_t = gnow()
                if t.startswith("A tension leaves the air around you"):
                    self.recall_pending = False
                    self.recall_cancelled = True
                if "yanked upwards" in t or "yanked downwards" in t:
                    self.recall_pending = False
                    self.last_stairs_cmd = None
                    self.recalled = "down" if "downwards" in t else "up"
            elif k == "store":
                self.store, self.store_t = ev, gnow()
            elif k == "store_leave":
                self.store = None
                # (set when the client saw our own non-store command close it)
                self.store_left_why = ev.get("why")
            elif k == "monlist":
                self.monlist = self.g.parse_monlist(ev["lines"])
            elif k == "itemlist":
                self.itemlist = [l for l in ev["lines"] if l.strip()]
        return out

    def _level_kind(self, old_depth, stairs):
        """Dungeon or surface after a level change. The depth indicator is one
        signed byte, so far wilderness squares (index < -127) show up as
        positive depths: judge by how we got here instead."""
        d = self.depth
        if d == 0:
            return False                       # town
        if d < 0:
            return False                       # wilderness (index still in range)
        if self.recalled == "down" or (stairs and stairs[0] == ">"):
            return True
        if stairs and stairs[0] == "<":
            return True                        # up a dungeon staircase, not to town
        if self.in_dungeon is None:
            return True                        # logged in down here
        return self.in_dungeon                 # trapdoor/teleport level stay; walking an edge stays surface

    # --- queries ----------------------------------------------------------

    def refresh(self, map_every=0.5, status_every=0.3, inven_every=10.0):
        now = gnow()
        # (polling our own client: wall time -- on the game clock the HP bubble polled every 2.5 s)
        if self.rows is None or self.pos != self.map_pos or wall_since(self.map_t) > map_every:
            self.refresh_map()
        if wall_since(self.status_t) > status_every:
            st = self.c.status()
            self.ind = st["ind"]
            if "hp" in self.ind:
                self.hp_hist.append((now, self.ind["hp"][0]))
            self.ghost = st.get("ghost", False)
            if st["y"] >= 0:
                self.pos = (st["y"], st["x"])
            self.status_t = now
            if self.depth is None:
                self.depth = self.ind.get("depth", [0])[0]
            if self.in_dungeon is None and self.depth is not None:
                self.in_dungeon = self.depth > 0
        if self.inven_dirty or wall_since(self.inven_t) > inven_every:
            equip_before = [i["name"] for i in self.inven if i["equip"]] if self.inven else None
            self.inven = self.c.inven()
            fuel_reading(light_fuel(self.inven))
            self.inven_t = now
            self.inven_dirty = False
            if equip_before != [i["name"] for i in self.inven if i["equip"]]:
                self.flags_t = 0              # equipment changed: re-read the resist grid
        # The resist/ability grid and the floor item, straight from the client
        # (the game-state survey: facts, not guesses from item names)
        if now - self.flags_t > 10:
            self.flags_t = now
            try:
                self.flags = self.c.query("flags", "flags")["flags"]
            except Exception:
                pass
        if now - self.floor_t > 1.0:
            self.floor_t = now
            try:
                fl = self.c.query("floor", "floor")
                self.floor = fl["name"] or None
            except Exception:
                pass

    def refresh_map(self):
        m = self.c.query("map", "map")
        self.rows, self.attrs = m["rows"], m["attrs"]
        self.map_t = gnow()
        self.map_pos = self.pos
        self.monsters = self.g.monsters(self.rows, self.attrs, skip=self.pos)
        # (a monster that never moves stays where it was seen, in view or not: m26 walked next to a Radiation eye
        # out of the lantern's reach, and its gaze drained STR)
        for y, x, r in self.monsters:
            if "NEVER_MOVE" in getattr(r, "flags", ()):
                self.still_seen[(y, x)] = r
        if self.monsters:
            self.monster_seen_t = self.map_t
        mon_at = {(y, x) for y, x, _ in self.monsters}
        for y, r in enumerate(self.rows):
            for x, ch in enumerate(r):
                if ch in TERRAIN and ch != " " and (y, x) not in mon_at:
                    self.memory[(y, x)] = ch
                elif ch not in TERRAIN and ch != "@" and (y, x) not in mon_at:
                    self.memory[(y, x)] = ch       # an object lying on the floor
        # A monster stands on open ground unless it walks through walls: a
        # corridor seen only with monsters in it stayed blank, and a flee found
        # "no known path" past it (mission 17, 650 ft)
        for y, x, r in self.monsters:
            if (y, x) not in self.memory and not ({"PASS_WALL", "KILL_WALL"} & r.flags):
                self.memory[(y, x)] = "."

    # --- derived ----------------------------------------------------------

    @property
    def hp(self):
        return self.ind.get("hp", [0, 1])[:2]

    @property
    def hp_frac(self):
        hp, mhp = self.hp
        return hp / mhp if mhp else 1.0

    def damage_rate(self, window=3.0):
        """HP lost per second over the last `window` seconds (drops only:
        heals in between don't hide the damage coming in)."""
        now = gnow()
        pts = [(t, h) for t, h in self.hp_hist if now - t <= window]
        lost = sum(max(0, a[1] - b[1]) for a, b in zip(pts, pts[1:]))
        return lost / window

    @property
    def depth_ft(self):
        return (self.depth or 0) * FT_PER_LEVEL

    @property
    def hunger(self):
        return self.ind.get("hunger", [3])[0]

    @property
    def resting(self):
        return bool(self.ind.get("state", [0, 0, 0])[2])

    def has(self, flag):
        """True/False from the character sheet's grid (e.g. 'free_act',
        'see_invis', 'res_conf'), or None while it hasn't been read."""
        if not self.flags:
            return None
        return bool(self.flags.get(flag))

    def listed_only(self):
        """Races the server's monster list names that the map decode doesn't
        show (mission 4's Yellow mold): present, position unknown."""
        seen = {r.name for *_, r in self.monsters}
        out = []
        for name, _n, _ch in self.monlist or []:
            r = self.g.by_name.get(name)
            if r is not None and name not in seen:
                out.append(r)
        return out

    def is_day(self):
        """Day or night in town: the sun messages, else how much of the town
        floor is drawn (the whole town is lit by day). None in the dungeon."""
        if self.depth != 0:
            return None
        if self.daytime is not None:
            return self.daytime
        if not self.rows:
            return None
        lit = sum(r.count(".") for r in self.rows)
        return lit > 1500

    @property
    def clvl(self):
        """The current character level. The server's 'level' indicator is
        (max level ever, current level) (xtra1.c:166): after an experience
        loss (resurrection halves it) the first value stays high, and the
        pilot used it everywhere (mission 11: 10 instead of 8)."""
        lv = self.ind.get("level", [1])
        return lv[1] if len(lv) > 1 else lv[0]

    def flag(self, name):
        return bool(self.ind.get(name, [0])[0])

    def dist(self, a, b=None):
        b = b or self.pos
        return max(abs(a[0] - b[0]), abs(a[1] - b[1]))

    def adjacent_monsters(self):
        return [m for m in self.monsters if self.dist(m[:2]) == 1]

    def find(self, chars):
        """Remembered tiles showing any of chars."""
        return [p for p, ch in self.memory.items() if ch in chars]

    def items(self, *, tval=None, name=None, equip=False):
        # A fresh copy for every decision (a local query to our own client,
        # cheap): a cached pack let a stale letter read the wrong item
        if wall_since(self.inven_t) > 0.25 and getattr(self, "c", None) is not None:
            try:
                self.inven = self.c.inven()
                fuel_reading(light_fuel(self.inven))
                self.inven_t = gnow()
                self.inven_dirty = False
            except Exception:
                pass
        out = []
        for it in self.inven:
            if it["equip"] != equip:
                continue
            if tval is not None and it["tval"] not in (tval if isinstance(tval, (set, tuple, list)) else (tval,)):
                continue
            if name and name.lower() not in it["name"].lower():
                continue
            out.append(it)
        return out

    def tagged(self, cmd, digit):
        """Inventory item inscribed @<cmd><digit> (or @<digit>), like the client's item tags."""
        for it in self.inven:
            m = re.search(r"\{([^}]*)\}", it["name"])
            if not m:
                continue
            tags = m.group(1)
            if f"@{cmd}{digit}" in tags:
                return it
        for it in self.inven:
            m = re.search(r"\{([^}]*)\}", it["name"])
            if m and re.search(rf"@{digit}(?!\d)", m.group(1)):
                return it
        return None

    def recent(self, secs):
        now = gnow()
        return [t for (ts, t) in self.messages if now - ts <= secs]
