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
answers show in the feed as NAVIGATOR: ...

    python3 watch.py [--nick dive04]

Keys: type + Enter = note; Esc = clear the line; PgUp/PgDn = scroll the feed;
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

FEED_KINDS = ("act", "attention", "goal", "goal_done", "goal_failed", "user_note", "audit", "nav_say")


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


def draw(scr, sock, feed, buf, msg, scroll):
    scr.erase()
    H, W = scr.getmaxyx()
    side = W >= 150                     # feed beside the map when wide enough
    left_w = min(W, 82) if side else W
    map_rows = max(4, (H - 10) // 2 if side else (H - 14) // 3)
    try:
        # (the report shows rows y0-N..y0+N and columns x0-M..x0+M)
        out = call(sock, {"cmd": "view", "args": [str(max(3, map_rows // 2)), str((left_w - 8) // 2)]}, 3)
        report = out.get("report", "(no report)")
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
        if l.startswith(("Equipment:", "Pack:", "Recent messages:", "Orders:", "Items seen:",
                         "Item squares", "Known stairs:")):
            continue
        keep.append(l)
    y = 0
    top_h = H - 2 if side else max(6, (H * 3) // 5)
    for l in keep:
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
        attr = curses.A_BOLD if k in ("attention", "goal_failed") else 0
        if k in ("user_note", "nav_say"):
            attr = curses.A_REVERSE
        scr.addnstr(fy + 1 + i, fx, f"{t:8} {piece}", fw, attr)
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
    curses.curs_set(1)
    scr.nodelay(True)
    scr.keypad(True)
    buf, msg, scroll, last = "", ("type a note + Enter;  '!' = message the Navigator now;  "
                                  "'?' = a question for the Architect"), 0, 0.0
    while True:
        now = time.time()
        if now - last >= 0.5:
            feed.poll()
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
