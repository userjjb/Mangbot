"""watch_mission.py [MAX_S] [--nick dive04] [--fresh] [--backlog S] -- wait for something the Architect should look at
during a mission; print it and exit (or after MAX_S seconds, default 1500: "quiet for N s").

Watches runs/pilot/NICK/decisions.jsonl, asks.jsonl and pilot.log: Navigator questions (NAV ASK), emergencies and
escapes (not plain trip recalls), deaths, stat drains, user messages, stuck plans, plan ends, the trip's "couldn't
leave" recall, gear evaluator swaps, Python errors in the Pilot (a traceback's exception line, not the control
socket's "Broken pipe" when a client hangs up; and "client exited"). Run it in the background (Bash
run_in_background) and restart it each time it exits with the same command line: it resumes where the last run
stopped reading (byte offsets kept in runs/pilot/NICK/watch_mission.state), so nothing between an exit and the
restart is lost. It starts at the file ends instead with --fresh, with no state file, or when the state is older
than --backlog seconds (default 3600: a new session, not a restart). Session 7 (the Architect, 10-26); A10 10-29."""
import argparse
import json
import os
import re
import sys
import time

RUNS = "/projectnb/jbrcs/mangband/runs/pilot"
NAMES = ("decisions.jsonl", "asks.jsonl", "pilot.log")
QUIET_STUCK = re.compile(r"hasn't moved from .* for 20 s")
# pilot.log: a traceback's last line names the exception (column 0); stack frames are indented
EXC_LINE = re.compile(r"^(?:[A-Za-z_]\w*\.)*\w*(?:Error|Exception)(?::|$)")
FRAME = re.compile(r'File "([^"]+)", line (\d+), in (\S+)')
HANGUP = re.compile(r"^(?:BrokenPipeError|ConnectionResetError)\b")   # a ctl.sock client went away: harmless

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("max_s", nargs="?", type=float, default=1500, help="give up after this many seconds (1500)")
ap.add_argument("--nick", default="dive04")
ap.add_argument("--fresh", action="store_true", help="start at the file ends (ignore the saved offsets)")
ap.add_argument("--backlog", type=float, default=3600, help="resume only if the state is at most this old (s)")
a = ap.parse_args()
RUN = os.path.join(RUNS, a.nick.lower())
STATE = os.path.join(RUN, "watch_mission.state")

try:
    state = json.load(open(STATE))
except (OSError, ValueError):
    state = None
age = time.time() - state.get("saved", 0) if state else None
resume = state is not None and not a.fresh and age <= a.backlog
if not resume:
    print("(starting at the file ends: " + ("--fresh" if a.fresh else "no saved offsets" if state is None else
                                            f"saved offsets are {age / 60:.0f} min old") + ")")
files = {}
for n in NAMES:
    f = open(os.path.join(RUN, n), "rb")
    st = os.fstat(f.fileno())
    old = (state or {}).get("files", {}).get(n) if resume else None
    if old and old.get("ino") == st.st_ino and old.get("pos", 0) <= st.st_size:
        f.seek(old["pos"])
    elif old:
        f.seek(0)                       # replaced or truncated since: all of it is new
    else:
        f.seek(0, 2)
    files[n] = f


def save():
    out = {"saved": time.time(), "files": {n: {"ino": os.fstat(f.fileno()).st_ino, "pos": f.tell()}
                                           for n, f in files.items()}}
    tmp = STATE + ".tmp"
    with open(tmp, "w") as g:
        json.dump(out, g)
    os.replace(tmp, STATE)


def new_lines(f):
    """Complete new lines only; a line still being written is left for the next poll."""
    out = []
    while True:
        pos = f.tell()
        raw = f.readline()
        if not raw:
            break
        if not raw.endswith(b"\n"):
            f.seek(pos)
            break
        out.append(raw.decode("utf-8", "replace"))
    return out


t0 = time.time()
hits = []
in_tb, where, req_errs = False, "", 0
while time.time() - t0 < a.max_s and not hits:
    for name, f in files.items():
        for line in new_lines(f):
            if name == "pilot.log":
                s = line.rstrip("\n")
                if s.startswith("Exception occurred during processing of request"):
                    req_errs += 1               # socketserver: a ctl.sock request's traceback follows
                elif s.startswith("Traceback (most recent call last)"):
                    in_tb = True
                elif s[:1] in (" ", "\t"):
                    m = FRAME.search(s)
                    if m and "/tools/" in m.group(1):
                        where = f"{os.path.basename(m.group(1))} line {m.group(2)} in {m.group(3)}"
                elif in_tb and (not s or s.startswith("During handling") or s.startswith("The above exception")):
                    pass
                elif in_tb or EXC_LINE.match(s):
                    if not (HANGUP.match(s) and (req_errs or where.endswith(" in handle"))):
                        hits.append(f"pilot.log: {s[:300]}" + (f" (at {where})" if where else ""))
                    in_tb, where, req_errs = False, "", max(req_errs - 1, 0)
                elif re.match(r"^\d\d:\d\d:\d\d client exited", s):
                    hits.append(f"pilot.log: {s[:300]}")
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
    save()
    if not hits:
        time.sleep(2)
print("\n".join(hits) if hits else f"quiet for {a.max_s:.0f} s")
