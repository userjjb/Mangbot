#!/usr/bin/env python3
"""Navigator response time per mission, from decisions.jsonl (study: Opus vs Sonnet Navigator, 2026-10-17).

Records used (Pilot logging since 2026-10-09 00:07):
- nav_cmd with wait_report=True: the status the Pilot builds when a `pilotctl wait` returns, i.e. the moment the
  Navigator receives a report. (The wait request itself is not logged.)
- nav_cmd with wait_report=False: every command the Navigator sends, as received.
- attention: Pilot news (each one ends a pending wait at once).
- user_note / nav_say: the user's live messages and the Navigator's replies.

Metrics (seconds):
  think   report received -> the Navigator's next command of any kind (status, journal, goal, ...), counted only
          when a command comes before the next report (otherwise the Navigator just waited again: "no-op cycle").
  act     report received -> first ACTION (goal, order, item use, stairs, stop, ...), same condition.
  alert   urgent attention (emergency, danger_*, fight_going_badly, flee_failed, unseen_attacker, stat_drained,
          low_supply, lost) -> first action after it. Pre-10-09 missions have no nav_cmd: there the action is the next
          Navigator-issued goal/act record (like latency.py), a weaker measure.
  burst   after the first command, the time until the Navigator's last command before its next report (its working time).
  reply   user message -> Navigator's say.
Usage: response.py [NICK]   (missions listed in MISSIONS below; add new ones there)"""
import bisect, json, statistics, sys
from datetime import datetime

NICK = sys.argv[1] if len(sys.argv) > 1 else "dive04"
MISSIONS = [  # name, start, end (local time; from the Navigator reports / next_steps.md). m16-m21 Opus; m22+ Sonnet (the user, 10-17)
    ("m16", "2026-10-08 15:31", "2026-10-08 16:09"),
    ("m17", "2026-10-16 13:57", "2026-10-16 14:41"),
    ("m18", "2026-10-16 18:46", "2026-10-16 19:27"),
    ("m19", "2026-10-16 22:14", "2026-10-16 22:56"),
    ("m20", "2026-10-16 23:41", "2026-10-17 00:19"),
    ("m21", "2026-10-17 00:47", "2026-10-17 01:36"),
]
QUERY = {"status", "journal", "gate", "monster", "inventory", "complain", "drainers", "say", "note", "options",
         "flags", "floor", "help", "plan", "dump", "quote", "view"}
URGENT = ("emergency", "danger", "fight_going_badly", "flee_failed", "unseen_attacker", "stat_drained",
          "low_supply", "lost", "breeders", "afraid")
PILOT_GOALS = ("flee", "recover", "town", "rest")

def ts(s): return datetime.strptime(s, "%Y-%m-%d %H:%M").timestamp()
def q(v, p):
    v = sorted(v); return v[min(len(v) - 1, int(p * (len(v) - 1) + 0.5))] if v else float("nan")
def fmt(v):
    return f"{len(v):4d}  {statistics.median(v):6.1f}  {q(v, .25):5.1f}-{q(v, .75):<5.1f} {q(v, .9):6.1f}" if v else "   0       -"

dec = [json.loads(l) for l in open(f"/projectnb/jbrcs/mangband/runs/pilot/{NICK}/decisions.jsonl")]
print("seconds: n, median, interquartile range, 90th percentile\n")
summary = {}
for name, a, b in MISSIONS:
    t0, t1 = ts(a), ts(b)
    d = [x for x in dec if t0 <= x["t"] <= t1]
    navc = [x for x in d if x["kind"] == "nav_cmd"]
    reports = [x["t"] for x in navc if x.get("wait_report")]
    cmds = [(x["t"], x["cmd"]) for x in navc if not x.get("wait_report")]
    acts = [t for t, c in cmds if c not in QUERY]
    has_cmd = bool(navc)
    think, act, burst, noop = [], [], [], 0
    for i, r in enumerate(reports):
        nxt = reports[i + 1] if i + 1 < len(reports) else t1
        inside = [t for t, c in cmds if r < t < nxt]
        if not inside:
            noop += 1; continue
        think.append(inside[0] - r)
        burst.append(inside[-1] - inside[0])
        ia = [t for t in acts if r < t < nxt]
        if ia: act.append(ia[0] - r)
    # alert -> action
    if has_cmd:
        order_t = sorted(acts)
    else:
        order_t = sorted(x["t"] for x in d if (x["kind"] == "goal" and x.get("goal") and
                         not str(x["goal"]).startswith(PILOT_GOALS)) or
                         (x["kind"] == "act" and str(x.get("why", "")).startswith("agent:")))
    alert = []
    for x in d:
        if x["kind"] == "attention" and str(x.get("what", "")).startswith(URGENT):
            j = bisect.bisect_right(order_t, x["t"])
            if j < len(order_t) and order_t[j] - x["t"] <= 300:
                alert.append(order_t[j] - x["t"])
    users = [x["t"] for x in d if x["kind"] == "user_note"]
    says = sorted(x["t"] for x in d if x["kind"] == "nav_say")
    reply = []
    for u in users:
        j = bisect.bisect_right(says, u)
        if j < len(says) and says[j] - u <= 300: reply.append(says[j] - u)
    cyc = [y - x for x, y in zip(reports, reports[1:])]
    summary[name] = (think, act, alert, reply)
    print(f"== {name} {a[5:]}-{b[11:]}: {len(reports)} reports, {len(cmds)} commands ({len(acts)} actions), "
          f"{noop} reports with no command before the next one" + ("" if has_cmd else "  [no nav_cmd logging]"))
    print(f"   think  (report -> any command)    {fmt(think)}")
    print(f"   act    (report -> first action)   {fmt(act)}")
    print(f"   burst  (first -> last command)    {fmt(burst)}")
    print(f"   alert  (urgent news -> action)    {fmt(alert)}")
    print(f"   reply  (user message -> say)      {fmt(reply)}")
    print(f"   report-to-report cycle            {fmt(cyc)}")
allv = lambda k: [v for s in summary.values() for v in s[k]]
print("\n== pooled")
for k, lab in enumerate(("think", "act", "alert", "reply")):
    print(f"   {lab:6s} {fmt(allv(k))}")
