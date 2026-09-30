"""The pilot's picture of the game, kept up to date from client events.

Everything the rules need to decide with: position, depth, map (chars and
colours), monsters on the map (named, via glyphs.py), the server's monster and
item lists, indicators (HP, hunger, ...), inventory, recent messages, and
whether we are standing on a staircase (the map only ever shows '@' there).
"""
import collections
import re
import threading
import time

from glyphs import Glyphs

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
        self.monlist = []                      # [(name, count, our char)]
        self.itemlist = []                     # item list lines
        self.ind = {}
        self.status_t = 0.0
        self.ghost = False
        self.inven = []
        self.inven_t = 0.0
        self.inven_dirty = True
        self.messages = collections.deque(maxlen=60)   # (t, text)
        self.standing_on = None                # '<' '>' or a terrain char, if known
        self.last_stairs_cmd = None            # ('<'|'>', t) sent, awaiting the level change
        self.hits_taken = 0                    # "... hits you" style messages
        self.last_hit_t = 0.0
        self.explained_t = 0.0                # last trap/cut/poison message (HP loss that isn't a monster)
        self.monster_seen_t = 0.0             # last map with a monster on it
        self.fight_t = 0.0                     # last time we hit, missed or killed something
        self.unseen = (0.0, "")                # last message from an unseen monster acting on us
        self.heard = (0.0, "")                 # last "You hear a door burst open!"
        self.hp_hist = collections.deque(maxlen=40)   # (t, hp), one per status poll
        self.pos_t = 0.0
        self.in_dungeon = None                 # see _level_kind(): the depth byte alone can't tell
        self.walked = set()                    # squares walked on this level
        self.recalled = None                   # 'down'/'up' from the recall message, until the level changes
        self.recall_cancelled = False          # set on "A tension leaves"; the pilot reports and clears it
        self.recall_pending = False            # a Word of Recall is active ("becomes charged" until the level changes)
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
                self.pos_t = time.time()
                self.walked.add(new)           # squares we've been on (safe retreat ground)
            elif k == "level":
                old = self.depth
                self.depth = ev["depth"]
                self.level_t = time.time()
                self.memory = {}
                self.walked = set()
                self.rows = None
                self.monsters, self.itemlist = [], []
                sc = self.last_stairs_cmd
                if sc and time.time() - sc[1] < 5 and old is not None:
                    # Connected stairs: '>' leaves you on an up staircase and vice versa
                    self.arrived_by = sc[0]
                    self.standing_on = "<" if sc[0] == ">" else ">"
                else:
                    self.arrived_by = "other"
                    self.standing_on = None
                self.in_dungeon = self._level_kind(old, sc)
                self.recalled = None
                self.recall_pending = False
                self.last_stairs_cmd = None
            elif k == "message":
                t = ev["text"]
                self.messages.append((time.time(), t))
                if t.startswith("You have ") or t.startswith("You see ") or "no more" in t \
                        or t.startswith("You are wearing") or t.startswith("You are wielding") \
                        or t.startswith("Was wearing") or t.startswith("You destroy") \
                        or t.startswith("You feel") or "in your pack" in t:
                    self.inven_dirty = True
                if (re.match(r"You have .*\([a-w]\)\.$", t) or t.startswith("You destroy")) and \
                        self.standing_on and self.standing_on not in TERRAIN and self.depth:
                    self.standing_on = "."    # the item underfoot is gone (report showed it after pickup)
                if self.RE_HURT_OTHER.search(t):
                    self.explained_t = time.time()
                if self.RE_UNSEEN.match(t):
                    self.unseen = (time.time(), t)
                elif t.startswith("You hear a door burst open"):
                    self.heard = (time.time(), t)
                if self.RE_ATTACK.search(t) or self.RE_RANGED.match(t):
                    self.hits_taken += 1
                    self.last_hit_t = time.time()
                if re.match(r"You (hit|miss|have slain|have destroyed|smite|bite|claw)", t) or \
                        re.match(r"(The|It) .* (dies|is destroyed|flees)", t):
                    self.fight_t = time.time()
                if t.startswith("I see no up staircase"):
                    self.standing_on = None if self.standing_on == "<" else self.standing_on
                if t.startswith("I see no down staircase"):
                    self.standing_on = None if self.standing_on == ">" else self.standing_on
                # A second read cancels the first (server spells2.c:1191-1199)
                if t.startswith("The air about you becomes charged"):
                    self.recall_pending = True
                if t.startswith("A tension leaves the air around you"):
                    self.recall_pending = False
                    self.recall_cancelled = True
                if "yanked upwards" in t or "yanked downwards" in t:
                    self.last_stairs_cmd = None
                    self.recalled = "down" if "downwards" in t else "up"
            elif k == "store":
                self.store, self.store_t = ev, time.time()
            elif k == "store_leave":
                self.store = None
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
        now = time.time()
        if self.rows is None or self.pos != self.map_pos or now - self.map_t > map_every:
            self.refresh_map()
        if now - self.status_t > status_every:
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
        if self.inven_dirty or now - self.inven_t > inven_every:
            self.inven = self.c.inven()
            self.inven_t = now
            self.inven_dirty = False

    def refresh_map(self):
        m = self.c.query("map", "map")
        self.rows, self.attrs = m["rows"], m["attrs"]
        self.map_t = time.time()
        self.map_pos = self.pos
        self.monsters = self.g.monsters(self.rows, self.attrs, skip=self.pos)
        if self.monsters:
            self.monster_seen_t = self.map_t
        mon_at = {(y, x) for y, x, _ in self.monsters}
        for y, r in enumerate(self.rows):
            for x, ch in enumerate(r):
                if ch in TERRAIN and ch != " " and (y, x) not in mon_at:
                    self.memory[(y, x)] = ch
                elif ch not in TERRAIN and ch != "@" and (y, x) not in mon_at:
                    self.memory[(y, x)] = ch       # an object lying on the floor

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
        now = time.time()
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
        now = time.time()
        return [t for (ts, t) in self.messages if now - ts <= secs]
