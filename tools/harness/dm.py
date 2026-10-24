"""dm -- script the Dungeon Master (Gandalf) on the test server, for the set-piece harness.

Restructure step 4 (the Advisor's set-piece memo, 2026-10-24 §2). The tool client's `interactive 13`
opens the DM menu ('&'), `keys` sends keystrokes into it, and every redraw comes back as a
`special` event (c-tool.c). The menu (server/xtra2.c do_cmd_dungeon_master):
  pages by Ctrl-letter (^P Player, ^S Summon, ^B Build, ^L Level, ^F Forge, ^E Encounter);
  hooks x/a/z/v select a slot, RET assigns the selected line to it, DEL clears it;
  the movement hook (x) fires when the DM steps: the summon lands on the square he left;
  on the Player page, RET selects a player and 'I' invokes it: to the DM's square on the same
  level, else a recall to the DM's depth (y/n prompt).
Without a sort or filter, Summon line N is monster race N (master_fill_monsters).

    dm = DM(); dm.connect()
    dm.summon(184, step=4)          # a Hill giant where Gandalf stands; he steps west
    dm.paint(1, [6] * 5)            # floor on the 5 squares he walks off going east
    dm.invoke("Dive04")             # pull Dive04 to Gandalf
    dm.descend(6)                   # Gandalf (a ghost DM) takes '>' anywhere, one level a press
    dm.quit()
"""
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shopcat"))
from mang import MangClient            # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DM_MENU = 13                           # SPECIAL_FILE_MASTER (server/mdefines.h)
DIRS = {1: (1, -1), 2: (1, 0), 3: (1, 1), 4: (0, -1), 6: (0, 1), 7: (-1, -1), 8: (-1, 0), 9: (-1, 1)}


class DM:
    def __init__(self, nick="Gandalf", port=28346, say=print):
        self.nick, self.port, self.say = nick, port, say
        self.c = None
        self.screen = []

    def connect(self):
        priv = os.path.join(ROOT, "runs", "private")
        self.c = MangClient(os.path.join(ROOT, "github", "mangclient"), os.path.join(ROOT, "github", "lib"),
                            self.nick, os.path.join(priv, self.nick.lower() + ".pass"), "localhost", self.port,
                            config=os.path.join(priv, self.nick.lower() + ".mangrc"), cwd=os.path.join(ROOT, "github"))
        self.c.wait_ready(timeout=30, settle=2.0)
        return self

    def quit(self):
        if self.c:
            self.c.quit()
            self.c = None

    # --- the menu ---------------------------------------------------------------
    def _drain(self, secs):
        """Collect events for secs; keep the last special screen."""
        got = False
        for ev in self.c.collect(secs):
            if ev.get("ev") == "special":
                self.screen = ev["lines"]
                got = True
        return got

    def menu(self, keys, settle=0.25):
        """Open the DM menu, send keys one by one (waiting for each redraw), return the screen.
        The menu stays open: close() it."""
        self.c.send(f"interactive {DM_MENU}")
        self._drain(0.6)
        for k in self._split(keys):
            self.c.send("keys " + k)
            self._drain(settle)
        return self.screen

    def close(self):
        self.c.send("keys \\e")
        self._drain(0.4)

    @staticmethod
    def _split(keys):
        """'^Sx\\r' -> ['^S', 'x', '\\r'] (one key each, in the tool client's escapes)."""
        out, i = [], 0
        while i < len(keys):
            if keys[i] == "\\" and i + 1 < len(keys):
                n = 4 if keys[i + 1] == "x" else 2
                out.append(keys[i:i + n])
                i += n
            elif keys[i] == "^" and i + 1 < len(keys):
                out.append(keys[i:i + 2])
                i += 2
            else:
                out.append(keys[i])
                i += 1
        return out

    def hooks(self):
        """{'x': 'Summon Jackal' or None, ...} from the menu's hook panel."""
        out = {}
        for l in self.screen:
            for k, v in re.findall(r"\|\s+([xazv]): (.+?)\s*$", l):
                out[k] = None if v.strip() == "<none>" else v.strip()
        return out

    # --- actions ----------------------------------------------------------------
    def clear_hooks(self):
        """Clear every hook (a summon hook left set summons on every step)."""
        for k in "xazv":
            self.menu(k + "\\x7f", settle=0.35)
        left = {k: v for k, v in self.hooks().items() if v}
        self.close()
        if left:
            raise RuntimeError(f"DM hooks still set: {left}")

    def summon(self, race, step=4, after=None):
        """Place race (its index in monster.txt; awake, with its group) on Gandalf's square,
        then step in direction `step` so it appears there; `after()` runs at once (before the
        hook cleanup, which takes a few seconds). Clears the hook afterwards."""
        keys = "^Sx" + "3" * (race // 20) + "2" * (race % 20) + "\\r"
        self.menu(keys, settle=0.05)
        self._drain(0.8)
        h = self.hooks().get("x") or ""
        self.close()
        if "Summon" not in h:
            raise RuntimeError(f"summon hook not set (x: {h!r})")
        self.c.send(f"walk {step}")
        self.c.collect(0.4)
        if after:
            after()
        self.clear_hooks()
        return h.replace("Summon ", "")

    def paint(self, feat, steps):
        """Paint terrain `feat` (lib/edit/terrain.txt index: 1 floor, 48 secret door, 56 granite) on each
        square Gandalf leaves while he walks `steps` (directions; a ghost walks through rock). The
        Build page's line N is feature N. Clears the hook afterwards."""
        keys = "^Bx" + "3" * (feat // 20) + "2" * (feat % 20) + "\\r"
        self.menu(keys, settle=0.05)
        self._drain(0.8)
        h = self.hooks().get("x") or ""
        self.close()
        if "Build" not in h:
            raise RuntimeError(f"build hook not set (x: {h!r})")
        for d in steps:
            self.c.send(f"walk {d}")
            self.c.collect(0.3)
        self.clear_hooks()
        return h.replace("Build ", "")

    K_MAX = 531                 # (lib/edit/limits.txt M:K) the Forge list: kinds by index, then egos 1.. after them

    def forge(self, kind, ego=None, number=1, pval=None):
        """Forge an item into Gandalf's pack slot a: kind = object.txt index, ego = ego_item.txt index,
        pval = its <pval> (a ring's +N). It comes out identified."""
        def down(n):
            return "3" * (n // 20) + "2" * (n % 20)
        keys = "^F" + down(kind) + "\\r" + "n" + str(number) + "\\r"
        if pval is not None:
            keys += "p" + str(pval) + "\\r"
        if ego:
            keys += down(self.K_MAX + ego - 1 - kind) + "\\r"
        self.menu(keys, settle=0.05)
        self._drain(0.8)
        self.close()
        inv = self.c.inven()
        return inv[0]["name"] if inv else None

    def drop_first(self, number=1):
        """Drop pack item a (number of it: a forged stack) on Gandalf's square (a ghost DM with GHOST_BODY can)."""
        self.c.send(f"custom d item=0 value={number}")
        self.c.collect(1.0)

    def players(self):
        """Names on the Player page, in its order (Gandalf marked '@')."""
        self.menu("^P")
        names = [l.strip().lstrip("@ ").strip() for l in self.screen[1:]
                 if l.strip() and not re.search(r"\) |Quickbar|World", l)]
        self.close()
        return names

    def invoke(self, name):
        """Pull a player to Gandalf: teleported to his square on the same level, else recalled
        to his depth (answers the y/n prompt)."""
        names = self.players()
        if name not in names:
            raise RuntimeError(f"{name} not on the Player page ({names})")
        i = names.index(name)
        self.menu("^P" + "2" * i + "\\rI")
        prompt = " ".join(self.screen)
        if "[y/n]" in prompt:
            self.c.send("keys y")
            self._drain(0.6)
        self.close()

    def status(self):
        return self.c.status()

    def descend(self, levels):
        """Gandalf is a ghost DM: '>' works anywhere, one level per press."""
        for _ in range(levels):
            self.c.send("custom >")
            self.c.collect(1.5)

    def ascend(self, levels):
        for _ in range(levels):
            self.c.send("custom <")
            self.c.collect(1.5)

    def walk(self, d, n=1):
        for _ in range(n):
            self.c.send(f"walk {d}")
            self.c.collect(0.25)


if __name__ == "__main__":
    dm = DM().connect()
    try:
        print("players:", dm.players())
        dm.clear_hooks()
        print("hooks clear")
    finally:
        dm.quit()
