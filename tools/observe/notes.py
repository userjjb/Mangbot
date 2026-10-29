#!/usr/bin/env python3
"""notes -- the user's commentary, each note with the play around it.

For every note in runs/pilot/<nick>/commentary.jsonl, prints the moment's
snapshot (depth, HP, goal, monsters) and the Pilot's decisions in the
seconds before and after it (decisions.jsonl), so each comment can be
checked against what actually happened and each '?' question answered.

    python3 notes.py [--nick dive04] [--since HH:MM | --today | --mission LABEL] [--before 20] [--after 5]
                     [--questions]

--mission LABEL keeps the notes made during that mission (its start to end in runs/missions.json, to now if it
is still running); wrap.sh uses it with --questions.
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

SHOW = ("act", "attention", "goal", "goal_done", "goal_failed", "audit", "note", "nav_journal", "nav_say",
        "nav_complaint")


def hms(t):
    return time.strftime("%H:%M:%S", time.localtime(t))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nick", default="dive04")
    ap.add_argument("--since", help="HH:MM today")
    ap.add_argument("--today", action="store_true")
    ap.add_argument("--mission", help="only notes made during this mission (runs/missions.json)")
    ap.add_argument("--before", type=float, default=20)
    ap.add_argument("--after", type=float, default=5)
    ap.add_argument("--questions", action="store_true", help="only notes starting with '?'")
    a = ap.parse_args()
    d = os.path.join(RUNS, "pilot", a.nick.lower())
    notes = [json.loads(l) for l in open(os.path.join(d, "commentary.jsonl")) if l.strip()]
    start, end = 0.0, float("inf")
    if a.mission:
        ms = [m for m in json.load(open(os.path.join(RUNS, "missions.json"))) if m.get("label") == a.mission]
        if not ms:
            sys.exit(f"no mission {a.mission} in runs/missions.json")
        start = time.mktime(time.strptime(ms[-1]["start"], "%Y-%m-%d %H:%M"))
        if ms[-1].get("end"):        # (minute resolution; a minute of slack for questions typed during the wrap-up)
            end = time.mktime(time.strptime(ms[-1]["end"], "%Y-%m-%d %H:%M")) + 60
    elif a.since:
        hh, mm = map(int, a.since.split(":"))
        lt = time.localtime()
        start = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hh, mm, 0, 0, 0, -1))
    elif a.today:
        lt = time.localtime()
        start = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    notes = [n for n in notes if start <= n["t"] <= end and (not a.questions or n.get("question"))]
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
            if e["kind"] in ("nav_journal", "nav_say", "nav_complaint"):
                label = {"nav_journal": "NAV", "nav_say": "NAV says", "nav_complaint": "NAV lacks"}[e["kind"]]
                print(f"  {mark} {hms(e['t'])} {label:11} {e.get('text')}")
                continue
            print(f"  {mark} {hms(e['t'])} {e['kind']:11} {str(what)[:40]:40} {str(why)[:110]}")
        print()


if __name__ == "__main__":
    main()
