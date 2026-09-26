"""Unique map glyphs for monster races, so the map says *which* monster is where.

The client uploads our glyph table (`mangclient --visuals FILE`, lines
"r INDEX CHARCODE ATTR") and the server draws the map with it. The scheme:

- every race keeps its usual letter (the map stays readable) and gets a
  colour that no other race with that letter has;
- terrain only ever uses colours 1..15, so races whose letter is also a
  terrain or object glyph ('!', '?', '=', '.', '$', '~', ',' -- mimics and
  friends) only get colours 16..63 and can't be mistaken for terrain;
- colours stop at 63: the map stream can't carry bit 0x40;
- race 0 is the player's own '@' and is left alone.

With the game option avoid_other on, the server draws every monster exactly
like that (no random multi-hued colours, no "clear" monsters taking the
floor's look). Mimics posing as objects and hallucination still lie.

Names, levels and flags come from lib/edit/monster.txt. A live server might
use different data; the monster list (whose lines show the race name next to
our glyph) is the authority when they disagree -- see check_monlist().
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
EDIT = os.path.abspath(os.path.join(HERE, "..", "..", "lib", "edit"))

TERRAIN_ATTR_MAX = 15
ATTR_MAX = 63


class Race:
    __slots__ = ("idx", "name", "char", "color", "level", "flags", "spells", "blows", "speed", "hp",
                 "spell_freq")

    def __init__(self, idx, name):
        self.idx, self.name = idx, name
        self.char, self.color, self.level = "?", "w", 0
        self.flags, self.spells, self.blows = set(), set(), []
        self.speed, self.hp = 110, "1d1"
        self.spell_freq = 0     # casts 1 time in N (0 = no spells)

    @property
    def repeat_fearer(self):
        """Frightens you again and again: a terrifying touch, or scares often (the
        user: more trouble than they're worth; walk or phase away)."""
        return any("TERRIFY" in b for b in self.blows) or \
            ("SCARE" in self.spells and 0 < self.spell_freq <= 5)

    def __repr__(self):
        return f"Race({self.idx}, {self.name!r}, lvl {self.level})"


def load_races(path=None):
    """{idx: Race} from monster.txt (N: I: W: G: F: S: B: lines)."""
    races, cur = {}, None
    for line in open(path or os.path.join(EDIT, "monster.txt"), encoding="latin1"):
        line = line.rstrip("\n")
        if line.startswith("N:"):
            _, idx, name = line.split(":", 2)
            cur = races[int(idx)] = Race(int(idx), name)
        elif cur is None:
            continue
        elif line.startswith("G:"):
            parts = line.split(":")
            cur.char, cur.color = parts[1], parts[2] if len(parts) > 2 else "w"
        elif line.startswith("I:"):
            parts = line.split(":")
            cur.speed, cur.hp = int(parts[1]), parts[2]
        elif line.startswith("W:"):
            cur.level = int(line.split(":")[1])
        elif line.startswith("F:"):
            cur.flags.update(f.strip() for f in line[2:].split("|") if f.strip())
        elif line.startswith("S:"):
            for f in line[2:].split("|"):
                f = f.strip()
                if f.startswith("1_IN_"):
                    cur.spell_freq = int(f[5:])
                elif f:
                    cur.spells.add(f)
        elif line.startswith("B:"):
            cur.blows.append(line[2:])
    return races


def _glyph_chars(fname):
    out = set()
    for line in open(os.path.join(EDIT, fname), encoding="latin1"):
        if line.startswith("G:"):
            out.add(line.split(":")[1] or ":")
    return out


def reserved_chars():
    """Characters terrain or objects can show: races using them only get colours > 15."""
    return (_glyph_chars("terrain.txt") | _glyph_chars("object.txt") | _glyph_chars("flavor.txt")
            | set(" 0123456789@:"))


def assign(races, reserved=None):
    """{race idx: (char, attr)} -- unique pairs, see the module doc."""
    reserved = reserved_chars() if reserved is None else reserved
    by_char = {}
    for idx in sorted(races):
        if idx == 0:
            continue
        by_char.setdefault(races[idx].char, []).append(idx)
    table = {}
    spill = [c for c in map(chr, range(33, 127))
             if c not in reserved and c not in by_char and c not in "\"\\"]
    for ch, idxs in by_char.items():
        lo = TERRAIN_ATTR_MAX + 1 if ch in reserved else 1
        attrs = list(range(lo, ATTR_MAX + 1))
        for i, idx in enumerate(idxs):
            if i < len(attrs):
                table[idx] = (ch, attrs[i])
            else:
                # More races with this letter than colours: borrow an unused char
                k = i - len(attrs)
                table[idx] = (spill[k // ATTR_MAX], 1 + k % ATTR_MAX)
    return table


def write_visuals(path, table):
    with open(path, "w") as f:
        for idx, (ch, a) in sorted(table.items()):
            f.write(f"r {idx} {ord(ch)} {a}\n")


class Glyphs:
    """Decoder for one glyph table."""

    def __init__(self, races=None, table=None):
        self.races = races or load_races()
        self.table = table or assign(self.races)
        self.by_glyph = {(ch, a): idx for idx, (ch, a) in self.table.items()}
        self.by_name = {r.name: r for r in self.races.values()}
        self.mismatches = 0

    def monster_at(self, ch, attr):
        """Race at a map cell (char, attr int), or None."""
        idx = self.by_glyph.get((ch, attr))
        return self.races.get(idx) if idx is not None else None

    def monsters(self, rows, attrs, skip=None):
        """[(y, x, Race)] for every decodable monster on the map. attrs rows are
        the 'map' reply's strings (chr(48 + attr) per cell)."""
        out = []
        for y, (r, a) in enumerate(zip(rows, attrs)):
            for x, ch in enumerate(r):
                if ch == " ":
                    continue
                # Terrain never matches: its colours (<= 15) aren't in the
                # table for terrain/object characters
                race = self.by_glyph.get((ch, ord(a[x]) - 48))
                if race is not None and (y, x) != skip:
                    out.append((y, x, self.races[race]))
        return out

    RE_MONLIST = re.compile(r"^(.*) \('(.)'\)/\('(.)'\):\[(\d+)\]\s*$")

    def parse_monlist(self, lines):
        """[(name, count, our_char)] from a monlist event; players are skipped."""
        out = []
        for line in lines:
            m = self.RE_MONLIST.match(line)
            if m:
                out.append((m.group(1), int(m.group(4)), m.group(3)))
        return out

    def check_monlist(self, lines):
        """Names the server lists that our table would draw differently (data mismatch)."""
        bad = []
        for name, _n, ours in self.parse_monlist(lines):
            r = self.by_name.get(name)
            if r is None or self.table.get(r.idx, (None,))[0] != ours:
                bad.append(name)
        self.mismatches += len(bad)
        return bad


if __name__ == "__main__":
    import sys
    races = load_races()
    table = assign(races)
    out = sys.argv[1] if len(sys.argv) > 1 else "visuals.txt"
    write_visuals(out, table)
    spilled = [i for i, (c, a) in table.items() if c != races[i].char]
    print(f"{len(table)} races -> {out}; {len(set(table.values()))} distinct glyphs; "
          f"{len(spilled)} moved to another char")
