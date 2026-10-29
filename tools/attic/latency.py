#!/usr/bin/env python3
"""latency -- how quickly the Navigator answers the Pilot and the user.

From runs/pilot/<nick>/decisions.jsonl, for a time window (a mission):
  alert -> contact : an attention event to the Navigator's next command of any kind
                     (how long until it woke and looked)
  alert -> order   : to its next order (goal, order, item or stairs command; not
                     status/journal/say/queries) within 120 s
  user -> reply    : a user_message to the Navigator's next `say`
  cadence          : gaps between consecutive Navigator commands

    python3 latency.py --nick dive04 --from "2026-10-17 00:59" --to "2026-10-17 01:35" [--label opus-m21]
    python3 latency.py --nick dive04 --mission "label,FROM,TO" [--mission ...]   # one row per mission
"""
import argparse
import json
import os
import statistics
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "runs"))

URGENT = {"danger_seen", "emergency", "emergency_loop", "unseen_attacker", "fight_going_badly", "stat_drained",
          "drainer", "thief", "breeders", "stuck", "lost", "pack_full", "interesting_item", "structure"}
NOT_ORDERS = {"status", "journal", "say", "monster", "drainers", "gate", "attention", "news", "map", "view",
              "viewmap", "navview", "note", "goalstate", "complain", "orders", "events", "inventory"}


def ts(s):
    return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M"))


def load(nick, t0, t1):
    out = []
    with open(os.path.join(RUNS, "pilot", nick.lower(), "decisions.jsonl")) as f:
        for line in f:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if t0 <= d.get("t", 0) <= t1:
                out.append(d)
    return out


def q(xs):
    if not xs:
        return "-"
    xs = sorted(xs)
    p90 = xs[min(len(xs) - 1, int(0.9 * len(xs)))]
    return f"n={len(xs):3d} median {statistics.median(xs):5.1f} s  p90 {p90:5.1f} s  max {xs[-1]:5.1f} s"


def measure(recs):
    cmds = [d for d in recs if d.get("kind") == "nav_cmd"]
    # (the trip plan's news is tagged source=plan since 2026-10-23: it didn't wake the Navigator)
    alerts = [d for d in recs if d.get("kind") == "attention" and d.get("what") in URGENT and d.get("source") != "plan"]
    users = [d for d in recs if d.get("kind") == "attention" and d.get("what") == "user_message"]
    contact, order, reply = [], [], []
    for a in alerts:
        nxt = next((c for c in cmds if c["t"] > a["t"]), None)
        if nxt and nxt["t"] - a["t"] < 600:
            contact.append(nxt["t"] - a["t"])
        o = next((c for c in cmds if c["t"] > a["t"] and c.get("cmd") not in NOT_ORDERS), None)
        if o and o["t"] - a["t"] < 120:
            order.append(o["t"] - a["t"])
    for u in users:
        s = next((c for c in cmds if c["t"] > u["t"] and c.get("cmd") == "say"), None)
        if s and s["t"] - u["t"] < 600:
            reply.append(s["t"] - u["t"])
    gaps = [b["t"] - a["t"] for a, b in zip(cmds, cmds[1:]) if b["t"] - a["t"] < 600]
    return {"alerts": len(alerts), "commands": len(cmds), "contact": contact, "order": order, "reply": reply,
            "gaps": gaps}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--nick", default="dive04")
    ap.add_argument("--from", dest="t0")
    ap.add_argument("--to", dest="t1")
    ap.add_argument("--label", default="")
    ap.add_argument("--mission", action="append", default=[], help="label,FROM,TO (repeatable)")
    a = ap.parse_args()
    rows = [m.split(",") for m in a.mission] or [[a.label or "window", a.t0, a.t1]]
    for label, f, t in rows:
        m = measure(load(a.nick, ts(f), ts(t)))
        mins = (ts(t) - ts(f)) / 60
        print(f"== {label}  ({f} - {t}, {mins:.0f} min): {m['alerts']} alerts, {m['commands']} Navigator commands "
              f"({m['commands'] / max(1, mins):.1f}/min)")
        print(f"   alert -> contact  {q(m['contact'])}")
        print(f"   alert -> order    {q(m['order'])}")
        print(f"   user  -> reply    {q(m['reply'])}")
        print(f"   command cadence   {q(m['gaps'])}")


if __name__ == "__main__":
    main()
