"""stomach -- how much food the character holds (2.49.0, the user, 11-03: the stomach tracker, calibrated by the hunger
crossings). The client is sent only the hunger *level* (xtra1.c:241-270 prt_hunger), so the tracker keeps a range
[lo, hi] of the food, moved by the server's own rules and narrowed by what the level shows:

- **Levels** (xtra1.c:241-270, the same tests as set_food's, xtra2.c:1600-1660; mdefines.h:242-247): 0 under 500
  (PY_FOOD_FAINT), 1 Weak 500-999 (PY_FOOD_WEAK 1000), 2 Hungry 1000-1999 (PY_FOOD_ALERT 2000), 3 Fed 2000-9999
  (PY_FOOD_FULL 10000), 4 Full 10000-14999 (PY_FOOD_MAX 15000), 5 Gorged 15000 up; set_food caps the food at 0-20000
  (xtra2.c:1597).
- **Digestion** (dungeon.c:1111-1152, process_player_end): every `time * 10` game turns, `time` =
  level_speed(depth) / 1000 (xtra2.c:5109: level_speeds[depth] x 5, tables.c:2202) scaled by the player's time bubble
  (dungeon.c:1115). A food tick digests (extract_energy[pspeed] / 100) x 2 (tables.c:2171: 20 at normal speed, 40 at
  +10, 10 at -10), +30 with regeneration, -10 with slow digestion; 100 while Gorged. No digestion in town (depth 0) or
  on a special level unless Gorged (dungeon.c:1124-1127); the wilderness (depth < 0) digests. None for a ghost
  (dungeon.c:1122).
- **The tick clock**: the worn light burns one turn of fuel every `time` game turns (the same block, dungeon.c:1183 and
  1484-1492: not artifacts or Dwarven lanterns), so ten turns of a burning light's fuel are exactly one food tick --
  speed-ups, the HP bubble and the test server's freeze included. Without a burning light (none, permanent, out,
  refuelled or swapped) the game clock (`gnow`) stands in: the bottom of the range digests at `TURNS_PER_DMIN` ticks a
  dungeon minute (the Pilot's field-measured rate, the faster), the top at the slowest the server runs our time, one
  tick per `time` game turns at FPS 75 (mangband.cfg).
- **Meals** (use-obj.c): food adds its pval (use-obj.c:235; object.txt: a Ration 5000), a potion its pval too
  (use-obj.c:713: CLW 50, CSW and CCW 100, Healing 200 -- object.txt:2004-2052), a Scroll of Satisfy Hunger sets the
  food to PY_FOOD_MAX - 1 = 14999 (use-obj.c:943), Salt Water to PY_FOOD_STARVE - 1 = 99 (use-obj.c:265).
- **Crossings**: digestion takes one level down at a time, so the level falling by one (not just after a meal)
  pins the food just under the level's bottom: [bottom - one tick's digestion, bottom - 1] (Fed -> Hungry: 1980-1999 at
  normal speed). A meal moves both ends; a crossing up after a meal is the meal's arithmetic, clamped to the new
  level. Anything unexplained (a level change with no meal, a contradiction) re-widens the range to the level's bounds.

Pure: the Pilot feeds `update` the level, the game clock, the worn light's fuel, the depth, the speed and the
regeneration / slow-digestion flags, and `sent` the eat / quaff / read commands (confirmed by the pack count dropping).
`to_json` / `from_json` carry the range over a Pilot restart (rundir/stomach.json).
"""
import math

PY_FOOD_MAX = 15000                 # mdefines.h:242
SATISFY = PY_FOOD_MAX - 1           # use-obj.c:943
SALT_WATER = 100 - 1                # PY_FOOD_STARVE - 1, use-obj.c:265 (mdefines.h:247)
# the food each hunger level spans (xtra1.c:241-270; the cap, xtra2.c:1597)
BOUNDS = {0: (0, 499), 1: (500, 999), 2: (1000, 1999), 3: (2000, 9999), 4: (10000, 14999), 5: (15000, 20000)}
FPS = 75                            # game turns a second (mangband.cfg FPS)
TURNS_PER_DMIN = 215                # (town.py's: player turns a dungeon minute, the speed-ups included)
EXACT_SPAN = 250                    # a range this narrow is shown as exact (~half a dungeon minute of food)
MEAL_WAIT_S = 5.0                   # game seconds a sent meal waits for the pack to show it eaten
SETTLE_S = 2.0                      # game seconds after a meal in which a level change is the meal's
# tables.c:2171 extract_energy[200] (pspeed 110 = normal: 1000)
EXTRACT_ENERGY = (
    (100,) * 70 + (200,) * 17 + (300,) * 8 + (400,) * 5 +
    (500, 500, 500, 500, 600, 600, 700, 700, 800, 900) +
    tuple(range(1000, 3600, 100)) + (3600, 3600, 3700, 3700, 3800, 3800, 3900, 3900, 4000, 4000, 4000) +
    (4100,) * 3 + (4200,) * 3 + (4300,) * 3 + (4400,) * 4 + (4500,) * 5 + (4600,) * 5 + (4700,) * 5 + (4800,) * 5 +
    (4900,) * 20)
# tables.c:2202 level_speeds[128]
LEVEL_SPEEDS = (
    (7500, 9000, 9100, 9200, 9300, 9400, 9500, 9600, 9700, 9800, 9900) + (10000,) * 5 +
    tuple(range(10100, 13600, 100)) + (13700, 13800, 13900, 14000, 14200, 14300, 14400, 14600, 14800) +
    tuple(range(15000, 20000, 200)) + (20000,) * 43)
assert len(EXTRACT_ENERGY) == 200 and EXTRACT_ENERGY[110] == 1000 and EXTRACT_ENERGY[120] == 2000
assert len(LEVEL_SPEEDS) == 128 and LEVEL_SPEEDS[10] == 9900 and LEVEL_SPEEDS[51] == 13700 and LEVEL_SPEEDS[84] == 19800
# a potion's food (object.txt pvals, use-obj.c:713), by the words of its name; an unknown flavour: 0 up to the most
POTION_FOOD = (("Slime Mold", 400), ("Apple Juice", 250), ("Water", 200), ("Healing", 200),
               ("Cure Critical Wounds", 100), ("Cure Serious Wounds", 100), ("Sleep", 100),
               ("Cure Light Wounds", 50), ("Confusion", 50), ("Slowness", 50))
POTION_FOOD_MAX = 400


def level_bounds(level):
    return BOUNDS.get(max(0, min(5, level)), BOUNDS[3])


def digest_rate(speed=0, regen=False, slow=False, gorged=False):
    """Food a food tick digests (dungeon.c:1132-1151): speed is the indicator's (pspeed - 110)."""
    if gorged:
        return 100
    ps = max(0, min(199, 110 + int(speed or 0)))
    return (EXTRACT_ENERGY[ps] // 100) * 2 + (30 if regen else 0) - (10 if slow else 0)


def slow_ticks_per_s(depth):
    """The fewest light ticks a game second the server runs: one per `time` = level_speed(depth) / 1000 game turns
    (xtra2.c:5109-5113, dungeon.c:1112) at FPS, our time bubble at 1 (the game clock already counts the 1/5)."""
    d = max(0, min(127, depth or 0))
    return FPS / max(1, LEVEL_SPEEDS[d] * 5 // 1000)


def meal_effect(tval, name, food_value, unknown=False):
    """What eating/quaffing/reading this does to the stomach: ('add', lo, hi), ('set', v), or None. food_value(name):
    a food's pval (items.py FOOD_VALUES, object.txt)."""
    if tval == 80:
        v = food_value(name)
        return ("add", v, v)
    if tval == 75:
        if "Salt Water" in name:
            return ("set", SALT_WATER)
        if unknown:
            return ("add", 0, POTION_FOOD_MAX)
        v = next((v for k, v in POTION_FOOD if k in name), 0)
        return ("add", v, v) if v else None
    if tval == 70 and "Satisfy Hunger" in name:
        return ("set", SATISFY)
    return None


class Stomach:
    def __init__(self, turns_per_dmin=TURNS_PER_DMIN):
        self.tpd = turns_per_dmin
        self.level = None           # the hunger level the range is for (None: nothing seen yet)
        self.lo = self.hi = None
        self.how = "unknown"        # what set the range last: unknown, pinned, meal, satisfy, restart...
        self.t = None               # the game clock at the last update
        self.fuel = None            # the worn light's fuel then (the tick clock)
        self.frac = 0.0             # light ticks not yet a whole food tick (exact clock)
        self.pending = []           # meals sent: [{key, count, effect, t, name}]
        self.settle = -1.0          # game time until which a level change is the last meal's
        self.saved = None           # a range carried over a restart, used on the first update (from_json)

    # --- reading it ---------------------------------------------------------------------------------------
    def range(self, level):
        """(lo, hi) at this hunger level: the tracker's range when it is for this level, else the level's bounds."""
        if self.level == level and self.lo is not None:
            return self.lo, self.hi
        return level_bounds(level)

    def exact(self, level):
        lo, hi = self.range(level)
        return self.level == level and hi - lo <= EXACT_SPAN

    def widen(self, level, how="unknown"):
        self.level = level
        self.lo, self.hi = level_bounds(level)
        self.how = how

    # --- the meals ----------------------------------------------------------------------------------------
    def sent(self, key, count, effect, now, name=""):
        """An eat/quaff/read of `key` (count of that kind in the pack now) was sent: applied once the count drops."""
        if effect:
            self.pending.append({"key": key, "count": count, "effect": effect, "t": now, "name": name})

    def _apply(self, effect):
        if effect[0] == "set":
            self.lo = self.hi = effect[1]
        else:
            self.lo, self.hi = self.lo + effect[1], self.hi + effect[2]
        self.lo, self.hi = max(0, min(20000, self.lo)), max(0, min(20000, self.hi))     # (xtra2.c:1597)

    # --- the clock ----------------------------------------------------------------------------------------
    def _ticks(self, now, fuel, depth):
        """Food ticks since the last update: (for lo: the most, for hi: the fewest)."""
        dt = max(0.0, now - self.t) if self.t is not None else 0.0
        prev = self.fuel
        self.t, self.fuel = now, fuel
        # (a burning light: its fuel counts the ticks -- a drop no faster than ~30 a second, as world.fuel_reading
        # reads it; a rise is a refuel or another light: the clock for that span)
        if prev is not None and fuel is not None and fuel > 1 and prev > 1 and 0 <= prev - fuel <= 30 * dt + 3:
            n = (prev - fuel) / 10 + self.frac
            whole = math.floor(n)
            self.frac = n - whole
            return whole, whole
        self.frac = 0.0
        return dt * self.tpd / 60 / 10, dt * slow_ticks_per_s(depth) / 10

    # --- the update ---------------------------------------------------------------------------------------
    def update(self, level, now, fuel=None, depth=0, speed=0, regen=False, slow=False, count_of=None,
               special=False, ghost=False, wall=None):
        """One look at the indicator. Returns the events worth a log record: [{what, ...}]."""
        out = []
        if level is None:
            return out
        if self.level is None:
            self.widen(level)
            self.t, self.fuel = now, fuel
            if self.saved:
                out += self._restore(level, depth, wall, digest_rate(speed, regen, slow, level == 5))
            return out
        old = self.level
        # 1. digestion since the last look, at the old level's rate (dungeon.c:1119-1152)
        many, few = self._ticks(now, fuel, depth)
        gorged = old == 5
        digests = not ghost and (gorged or (depth != 0 and not special))
        rate = digest_rate(speed, regen, slow, gorged)
        if digests and (many or few):
            self.lo -= many * rate
            self.hi -= few * rate
        # 2. a meal sent: eaten once the pack shows one fewer of the kind
        meal = False
        for m in list(self.pending):
            have = count_of(m["key"]) if count_of else m["count"]
            if have < m["count"]:
                self.pending.remove(m)
                for o in self.pending:            # (two of the same kind sent: the next one waits for one fewer)
                    if o["key"] == m["key"]:
                        o["count"] -= 1
                self._apply(m["effect"])
                self.settle = now + SETTLE_S
                self.how = "satisfy" if m["effect"] == ("set", SATISFY) else "meal"
                meal = True
                out.append({"what": "meal", "item": m["name"], "effect": list(m["effect"]), "lo": self.lo,
                            "hi": self.hi})
            elif now - m["t"] > MEAL_WAIT_S:
                self.pending.remove(m)
        # (the level moved up while a meal is still unconfirmed: wait for the pack before reading it)
        if level != old and self.pending and not meal:
            return out
        # 3. the level moved
        if level != old:
            if now < self.settle:
                self.level = level                # (the meal's: its arithmetic, clamped below)
            elif level == old - 1 and digests:
                # (just under the old level's bottom: by at most the ticks since the last look)
                b = level_bounds(old)[0]
                self.lo, self.hi = b - rate * max(1, math.ceil(many)), b - 1
                self.level, self.how = level, "pinned"
                out.append({"what": "pinned", "from": old, "to": level, "lo": self.lo, "hi": self.hi})
            else:
                self.widen(level)
                out.append({"what": "unexplained", "from": old, "to": level})
        # 4. the level's bounds (not while a meal settles: the indicator may lag the pack)
        if now >= self.settle:
            blo, bhi = level_bounds(level)
            lo, hi = max(self.lo, blo), min(self.hi, bhi)
            if lo > hi:
                out.append({"what": "contradiction", "level": level, "lo": self.lo, "hi": self.hi})
                self.widen(level)
            else:
                self.lo, self.hi = lo, hi
        return out

    # --- a restart ----------------------------------------------------------------------------------------
    def to_json(self, wall, depth):
        return {"level": self.level, "lo": self.lo, "hi": self.hi, "how": self.how, "wall": wall, "depth": depth}

    def from_json(self, d):
        self.saved = d if isinstance(d, dict) and d.get("lo") is not None else None

    def _restore(self, level, depth, wall, rate):
        """The range saved by the last Pilot, if for this level: the bottom digested at the fast rate for the wall
        time since (the character stays in the world while the Pilot restarts, hotswap.sh), the top not at all (it
        may have been out of the world); then the level's bounds."""
        d, self.saved = self.saved, None
        if d.get("level") != level or wall is None:
            return [{"what": "restart", "kept": False}]
        age = max(0.0, wall - float(d.get("wall") or 0))
        if age > 3600:
            return [{"what": "restart", "kept": False}]
        lo, hi = float(d["lo"]), float(d["hi"])
        if level == 5 or (d.get("depth") or 0) != 0:
            lo -= age * self.tpd / 60 / 10 * rate
        blo, bhi = level_bounds(level)
        lo, hi = max(lo, blo), min(hi, bhi)
        if lo > hi:
            return [{"what": "restart", "kept": False}]
        self.lo, self.hi, self.how = lo, hi, "restart"
        return [{"what": "restart", "kept": True, "lo": lo, "hi": hi, "age": round(age)}]
