#!/usr/bin/env python3
"""notes -- the user's commentary, each note with the play around it.

For every note in runs/pilot/<nick>/commentary.jsonl, prints the moment's
snapshot (depth, HP, goal, monsters) and the Pilot's decisions in the
seconds before and after it (decisions.jsonl), so each comment can be
checked against what actually happened and each '?' question answered.

    python3 notes.py [--nick dive04] [--since HH:MM | --today] [--before 20] [--after 5]
                     [--questions]
"""
import argparse
import bisect
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pilot"))
from pilotctl import RUNS      # noqa: E402

SHOW = ("act", "attention", "goal", "goal_done", "goal_failed", "audit", "note")


def hms(t):
    return time.strftime("%H:%M:%S", time.localtime(t))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nick", default="dive04")
    ap.add_argument("--since", help="HH:MM today")
    ap.add_argument("--today", action="store_true")
    ap.add_argument("--before", type=float, default=20)
    ap.add_argument("--after", type=float, default=5)
    ap.add_argument("--questions", action="store_true", help="only notes starting with '?'")
    a = ap.parse_args()
    d = os.path.join(RUNS, "pilot", a.nick.lower())
    notes = [json.loads(l) for l in open(os.path.join(d, "commentary.jsonl")) if l.strip()]
    start = 0.0
    if a.since:
        hh, mm = map(int, a.since.split(":"))
        lt = time.localtime()
        start = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hh, mm, 0, 0, 0, -1))
    elif a.today:
        lt = time.localtime()
        start = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    notes = [n for n in notes if n["t"] >= start and (not a.questions or n.get("question"))]
    if not notes:
        print("no notes")
        return
    lo = notes[0]["t"] - a.before
    hi = notes[-1]["t"] + a.after
    recs = []
    for l in open(os.path.join(d, "decisions.jsonl")):
        try:
            e = json.loads(l)
        except ValueError:
            continue
        t = e.get("t")
        if isinstance(t, (int, float)) and lo <= t <= hi and e.get("kind") in SHOW:
            recs.append(e)
    ts = [e["t"] for e in recs]
    for n in notes:
        q = "NAVIGATOR" if n.get("who") == "navigator" else "QUESTION" if n.get("question") else \
            "TO NAVIGATOR" if n["note"].startswith("!") else "note"
        print(f"=== {hms(n['t'])} {q}: {n['note']}")
        if "depth_ft" in n:
            print(f"    at {n.get('depth_ft')} ft {n.get('pos')}, HP {n.get('hp')}, clvl {n.get('clvl')}, "
                  f"goal {n.get('goal')}, on {n.get('standing_on')}")
            if n.get("monsters"):
                print("    monsters: " + ", ".join(f"{m[2]} {m[0]},{m[1]}" for m in n["monsters"]))
        i, j = bisect.bisect_left(ts, n["t"] - a.before), bisect.bisect_right(ts, n["t"] + a.after)
        for e in recs[i:j]:
            mark = ">>" if e["t"] > n["t"] else "  "
            what = e.get("cmd") or e.get("what") or e.get("goal") or e.get("text") or ""
            why = e.get("why") or e.get("detail") or ""
            if e["kind"] == "audit":
                what, why = "audit", ", ".join(e.get("diffs", {}))
            print(f"  {mark} {hms(e['t'])} {e['kind']:11} {str(what)[:40]:40} {str(why)[:110]}")
        print()


if __name__ == "__main__":
    main()
