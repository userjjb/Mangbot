#!/usr/bin/env python3
"""watch -- watch a Pilot-driven character live and comment on its play.

The screen refreshes twice a second from the Pilot (character line, map
around @, monsters, supplies, news) next to a feed of the Pilot's own
actions with their reasons (decisions.jsonl). Type a note at the bottom and
press Enter: it's logged with a timestamp and a snapshot of the moment
(position, HP, goal, monsters, the Pilot's last actions) in
runs/pilot/<nick>/commentary.jsonl and in the Pilot's decision log, for
later cross-reference (tools/observe/notes.py). Start a note with '?' to ask
why the Pilot did something; the Architect answers those. Start it with '!'
to message the Navigator playing the character: it's woken at once, and its
answers show in the feed as NAVIGATOR: ... The Navigator's journal lines
(its reasoning, one per decision) show as NAV: ... (magenta) when written.

    python3 watch.py [--nick dive04]

Keys: type + Enter = note; Tab = the Navigator's view (exactly what it last
read from the Pilot, and how long ago) / back; Esc = clear the line; PgUp/PgDn = scroll the feed;
Ctrl-C = quit (the character keeps playing). Watching never sends a game
command.
"""
import argparse
import curses
import json
import os
import sys
import textwrap
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pilot"))
from pilotctl import call, RUNS      # noqa: E402

# Angband's 16 colours (attr index = position; monster.txt letters in LETTERS),
# as xterm-256 shades and as the nearest of the 8 basic colours (+ bold)
LETTERS = "dwsorgbuDWvyRGBU"
XTERM = [240, 231, 245, 208, 160, 34, 27, 130, 242, 252, 129, 226, 203, 82, 75, 179]
BASIC = [(curses.COLOR_BLACK, True), (curses.COLOR_WHITE, True), (curses.COLOR_WHITE, False),
         (curses.COLOR_YELLOW, False), (curses.COLOR_RED, False), (curses.COLOR_GREEN, False),
         (curses.COLOR_BLUE, False), (curses.COLOR_YELLOW, False), (curses.COLOR_BLACK, True),
         (curses.COLOR_WHITE, False), (curses.COLOR_MAGENTA, False), (curses.COLOR_YELLOW, True),
         (curses.COLOR_RED, True), (curses.COLOR_GREEN, True), (curses.COLOR_BLUE, True),
         (curses.COLOR_YELLOW, True)]
COL = {}                                # attr index -> curses attribute
FEED_COL = {}


def init_colours():
    if not curses.has_colors():
        return
    curses.start_color()
    try:
        curses.use_default_colors()
        bg = -1
    except curses.error:
        bg = curses.COLOR_BLACK
    rich = curses.COLORS >= 256
    for i in range(16):
        fg, bold = (XTERM[i], False) if rich else BASIC[i]
        curses.init_pair(i + 1, fg, bg)
        COL[i] = curses.color_pair(i + 1) | (curses.A_BOLD if bold else 0)
    for n, (k, c) in enumerate((("alert", curses.COLOR_RED), ("you", curses.COLOR_YELLOW),
                                 ("nav", curses.COLOR_CYAN), ("act", curses.COLOR_GREEN),
                                 ("journal", curses.COLOR_MAGENTA)), start=20):
        curses.init_pair(n, c, bg)
        FEED_COL[k] = curses.color_pair(n)


def draw_map(scr, y, width, top_h, vm):
    """The map crop with the game's colours; monsters in their monster.txt
    colour (our glyph table recodes their attrs), @ in white. Returns rows used."""
    rows, attrs = vm.get("rows", []), vm.get("attrs", [])
    y0, x0 = vm.get("y0", 0), vm.get("x0", 0)
    mons = {(m[0], m[1]): m[2] for m in vm.get("mons", [])}
    pos = tuple(vm.get("pos") or (-1, -1))
    used = 0
    for i, row in enumerate(rows):
        if y + used >= top_h:
            break
        my = y0 + i
        scr.addnstr(y + used, 0, f"  {my:2d}|", 6)
        for j, ch in enumerate(row[:max(0, width - 7)]):
            mx = x0 + j
            if (my, mx) == pos:
                a = COL.get(1, 0) | curses.A_BOLD
            elif (my, mx) in mons:
                a = COL.get(LETTERS.find(mons[(my, mx)]) if mons[(my, mx)] in LETTERS else 1, 0) | curses.A_BOLD
            else:
                ai = (ord(attrs[i][j]) - 48) if i < len(attrs) and j < len(attrs[i]) else 1
                a = COL.get(ai, 0) if 0 <= ai < 16 else 0
            try:
                scr.addstr(y + used, 6 + j, ch, a)
            except curses.error:
                pass
        used += 1
    return used


FEED_KINDS = ("act", "attention", "goal", "goal_done", "goal_failed", "user_note", "audit", "nav_say",
              "nav_complaint")


def feed_line(e):
    t = time.strftime("%H:%M:%S", time.localtime(e["t"]))
    k = e["kind"]
    if k == "act":
        txt = f"{e.get('why') or ''}  [{e.get('cmd')}]"
    elif k == "attention":
        txt = f"{e.get('what')}: {e.get('detail') or ''}"
    elif k == "user_note":
        txt = f"YOU: {e.get('note')}"
    elif k == "nav_say":
        txt = f"NAVIGATOR: {e.get('text')}"
    elif k == "nav_complaint":
        txt = f"NAVIGATOR LACKS: {e.get('text')}"
    elif k == "attention" and e.get("what") == "user_message":
        txt = "(sent to the Navigator)"
    elif k == "audit":
        txt = f"audit difference: {', '.join(e.get('diffs', {}))}"
    else:
        txt = f"{k}: {e.get('goal') or e.get('detail') or ''}"
    return t, k, txt


class Feed:
    """Tail of decisions.jsonl (the kinds worth showing)."""

    def __init__(self, path):
        self.path, self.lines, self.pos = path, [], 0
        if os.path.exists(path):
            size = os.path.getsize(path)
            self.pos = max(0, size - 200000)
        self.poll(skip_partial=True)

    def poll(self, skip_partial=False):
        if not os.path.exists(self.path):
            return
        with open(self.path) as f:
            f.seek(self.pos)
            if skip_partial and self.pos:
                f.readline()
            for line in f:
                if not line.endswith("\n"):
                    break
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("kind") in FEED_KINDS:
                    self.lines.append(feed_line(e))
            self.pos = f.tell()
        self.lines = self.lines[-500:]


class Journal:
    """New lines of the Navigator's journal (navigator.md), shown in the feed
    as NAV: ... at the moment they're written (its own clock times have
    sometimes been guesses)."""

    def __init__(self, path, feed, backlog=4):
        self.path, self.feed = path, feed
        self.pos = os.path.getsize(path) if os.path.exists(path) else 0
        if backlog and os.path.exists(path):
            with open(path) as f:
                old = [l.rstrip("\n") for l in f if l.startswith("- ")][-backlog:]
            for l in old:
                feed.lines.append(("(earlier)", "nav_journal", "NAV: " + l[2:]))

    def poll(self):
        if not os.path.exists(self.path):
            return
        size = os.path.getsize(self.path)
        if size < self.pos:
            self.pos = 0                       # rewritten
        with open(self.path) as f:
            f.seek(self.pos)
            chunk = f.read()
        if not chunk.endswith("\n"):
            chunk = chunk[:chunk.rfind("\n") + 1]
        self.pos += len(chunk.encode())
        for l in chunk.splitlines():
            l = l.strip()
            if l:
                self.feed.lines.append((time.strftime("%H:%M:%S"), "nav_journal",
                                        "NAV: " + (l[2:] if l.startswith("- ") else l)))


MODE = {"nav": False}            # Tab: the live game view / what the Navigator last read


def draw(scr, sock, feed, buf, msg, scroll):
    scr.erase()
    H, W = scr.getmaxyx()
    side = W >= 150                     # feed beside the map when wide enough
    left_w = min(W, 82) if side else W
    map_rows = max(4, (H - 10) // 2 if side else (H - 14) // 3)
    margs = [str(max(3, map_rows // 2)), str((left_w - 8) // 2)]
    vm = {}
    try:
        # (the report shows rows y0-N..y0+N and columns x0-M..x0+M)
        if MODE["nav"]:
            nv = call(sock, {"cmd": "navview"}, 3)
            age = time.time() - nv.get("t", 0) if nv.get("t") else None
            report = (f"NAVIGATOR'S VIEW: what it last read, {age:.0f} s ago (Tab: back to the game)\n"
                      if age is not None else "NAVIGATOR'S VIEW: nothing read yet (Tab: back)\n") + \
                "\n".join(nv.get("events", [])) + ("\n" if nv.get("events") else "") + (nv.get("report") or "")
        else:
            out = call(sock, {"cmd": "view", "args": margs}, 3)
            report = out.get("report", "(no report)")
            vm = call(sock, {"cmd": "viewmap", "args": margs}, 3) if COL else {}
    except Exception as e:                      # Pilot restarting, or dead and gone
        report = f"(Pilot not answering: {e.__class__.__name__}; retrying)"
    lines = report.split("\n")
    keep = []
    in_map = False
    for l in lines:
        if l.startswith("Map ("):
            in_map = True
            keep.append(l)
            continue
        if in_map and l.startswith("  "):
            keep.append(l)
            continue
        in_map = False
        if not MODE["nav"] and l.startswith(("Equipment:", "Pack:", "Recent messages:", "Orders:", "Items seen:",
                                             "Item squares", "Known stairs:")):
            continue
        keep.append(l)
    y = 0
    top_h = H - 2 if side else max(6, (H * 3) // 5)
    drawn_map = False
    for l in keep:
        if vm.get("rows") and (l.startswith("Map (") or (l.startswith("  ") and drawn_map)):
            if l.startswith("Map ("):
                scr.addnstr(y, 0, l, left_w - 1)
                y += 1
                y += draw_map(scr, y, left_w - 1, top_h, vm)
                drawn_map = True
            continue
        for piece in (textwrap.wrap(l, left_w - 1, subsequent_indent="   ") if not l.startswith("  ")
                      else [l[:left_w - 1]]):
            if y >= top_h:
                break
            attr = curses.A_BOLD if l.startswith(("Dive", "Monsters", "Since last")) else 0
            if "@" in piece and l.startswith("  "):
                attr = 0
            scr.addnstr(y, 0, piece, left_w - 1, attr)
            y += 1
    # the feed
    if side:
        fx, fy, fw, fh = left_w + 1, 0, W - left_w - 2, H - 2
        for yy in range(fh):
            scr.addch(yy, left_w, curses.ACS_VLINE)
    else:
        fx, fy, fw, fh = 0, top_h, W - 1, H - top_h - 2
        scr.hline(fy, 0, curses.ACS_HLINE, W - 1)
        fy, fh = fy + 1, fh - 1
    scr.addnstr(fy, fx, "Pilot actions (newest last; PgUp/PgDn scroll)", fw, curses.A_BOLD)
    rows = []
    for t, k, txt in feed.lines:
        for i, piece in enumerate(textwrap.wrap(txt, max(10, fw - 10)) or [""]):
            rows.append((t if i == 0 else "", k, piece))
    end = len(rows) - scroll
    shown = rows[max(0, end - (fh - 1)):max(0, end)]
    for i, (t, k, piece) in enumerate(shown):
        attr = (FEED_COL.get("alert", 0) | curses.A_BOLD) if k in ("attention", "goal_failed") else \
            FEED_COL.get("act", 0) if k == "act" else 0
        if k == "user_note":
            attr = FEED_COL.get("you", 0) | curses.A_REVERSE
        if k == "nav_say":
            attr = FEED_COL.get("nav", 0) | curses.A_REVERSE
        if k == "nav_complaint":
            attr = FEED_COL.get("alert", 0) | curses.A_REVERSE
        if k == "nav_journal":
            attr = FEED_COL.get("journal", 0)
        scr.addnstr(fy + 1 + i, fx, f"{t:9} {piece}", fw, attr)
    # the note line
    scr.hline(H - 2, 0, curses.ACS_HLINE, W - 1)
    if msg:
        scr.addnstr(H - 2, 2, f" {msg} ", W - 4)
    prompt = "note> "
    scr.addnstr(H - 1, 0, prompt + buf[-(W - len(prompt) - 1):], W - 1)
    scr.move(H - 1, min(W - 1, len(prompt) + len(buf)))
    scr.refresh()


def main(scr, args):
    sock = os.path.join(RUNS, "pilot", args.nick.lower(), "ctl.sock")
    feed = Feed(os.path.join(RUNS, "pilot", args.nick.lower(), "decisions.jsonl"))
    journal = Journal(os.path.join(RUNS, "pilot", args.nick.lower(), "navigator.md"), feed)
    curses.curs_set(1)
    init_colours()
    scr.nodelay(True)
    scr.keypad(True)
    buf, msg, scroll, last = "", ("type a note + Enter;  '!' = message the Navigator now;  "
                                  "'?' = a question for the Architect"), 0, 0.0
    while True:
        now = time.time()
        if now - last >= 0.5:
            feed.poll()
            journal.poll()
            draw(scr, sock, feed, buf, msg, scroll)
            last = now
        try:
            ch = scr.get_wch()
        except curses.error:
            time.sleep(0.03)
            continue
        if ch in ("\n", "\r", curses.KEY_ENTER):
            if buf.strip():
                try:
                    msg = call(sock, {"cmd": "note", "args": [buf.strip()]}, 5).get("text", "noted")
                except Exception as e:
                    # the Pilot is down: keep the note anyway
                    with open(os.path.join(RUNS, "pilot", args.nick.lower(), "commentary.jsonl"), "a") as f:
                        f.write(json.dumps({"t": round(time.time(), 3), "note": buf.strip(),
                                            "question": buf.strip().startswith("?"),
                                            "pilot_down": e.__class__.__name__}) + "\n")
                    msg = "noted (Pilot not answering: saved without a snapshot)"
                buf = ""
        elif ch == "\t":
            MODE["nav"] = not MODE["nav"]
            msg = "Navigator's view (what it last read)" if MODE["nav"] else "game view"
        elif ch == "\x1b":
            buf = ""
        elif ch in (curses.KEY_BACKSPACE, "\x7f", "\b"):
            buf = buf[:-1]
        elif ch == curses.KEY_PPAGE:
            scroll += 10
        elif ch == curses.KEY_NPAGE:
            scroll = max(0, scroll - 10)
        elif ch == curses.KEY_RESIZE:
            pass
        elif isinstance(ch, str) and ch.isprintable():
            buf += ch
        last = 0.0                      # redraw now (typing feels live)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--nick", default="dive04")
    a = ap.parse_args()
    try:
        curses.wrapper(main, a)
    except KeyboardInterrupt:
        pass
