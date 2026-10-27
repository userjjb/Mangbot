"""watch_mission.py [MAX_S] -- wait for something the Architect should look at during a mission; print it and exit
(or after MAX_S seconds, default 1500: "quiet for N s").

Watches decisions.jsonl (new lines only), asks.jsonl and pilot.log from their current ends: Navigator questions (NAV
ASK), emergencies and escapes (not plain trip recalls), deaths, stat drains, user messages, stuck plans, plan ends,
the trip's "couldn't leave" recall, gear evaluator swaps, Python errors in the Pilot. Run it in the background (Bash
run_in_background) and restart it each time it exits. Session 7 (the Architect, 10-26)."""
import json
import os
import re
import sys
import time

RUN = "/projectnb/jbrcs/mangband/runs/pilot/dive04"
MAX_S = float(sys.argv[1]) if len(sys.argv) > 1 else 1500
QUIET_STUCK = re.compile(r"hasn't moved from .* for 20 s")


def opener(name):
    f = open(os.path.join(RUN, name))
    f.seek(0, 2)
    return f


files = {n: opener(n) for n in ("decisions.jsonl", "asks.jsonl", "pilot.log")}
t0 = time.time()
hits = []
while time.time() - t0 < MAX_S and not hits:
    for name, f in files.items():
        for line in f.readlines():
            if name == "pilot.log":
                if "Traceback" in line or "Error" in line or "error:" in line:
                    hits.append(f"pilot.log: {line.strip()[:300]}")
                continue
            if name == "asks.jsonl":
                hits.append(f"NAV ASK: {line.strip()[:400]}")
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            k = r.get("kind")
            what = r.get("what")
            det = str(r.get("detail") or r.get("text") or "")
            ts = time.strftime("%H:%M:%S", time.localtime(r.get("t", 0)))
            if (k == "escape" and r.get("escape") != "wor_travel") or k == "gear_eval" or k == "plan_end" or \
                    (k == "attention" and what in ("emergency", "emergency_loop", "dead", "died", "plan_failed",
                                                   "stat_drained", "user_message")) or \
                    (k == "attention" and what == "stuck" and not QUIET_STUCK.search(det)) or \
                    (k == "attention" and "couldn't leave" in det) or \
                    (k == "note" and ("error" in det.lower() or "failed" in det.lower() and "effect_failed" not in det)):
                hits.append(f"{ts} {k} {what or ''}: {json.dumps({x: y for x, y in r.items() if x not in ('map', 'crop', 't')})[:500]}")
    if not hits:
        time.sleep(2)
print("\n".join(hits) if hits else f"quiet for {MAX_S:.0f} s")
