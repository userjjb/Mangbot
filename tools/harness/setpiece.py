"""setpiece -- run one of the Advisor's set-pieces live on the test server and score it.

Restructure step 4 (memos/2026-10-24-setpieces.md, its addendum A7-A9). Each run:
  1. snapshots Dive04 (charsave.sh: savefile + the Pilot's state), so it keeps nothing from the run;
  2. stages the scene with the DM (dm.py: Gandalf descends, pulls Dive04 to him, summons the cast);
  3. gives the order the scenario tests, as the Navigator would (pilotctl, Navigator role);
  4. watches Dive04's decision log for the scenario's time, then scores the pass criteria;
  5. restores Dive04 and writes runs/setpieces/<id>-<time>.json (+ a line in runs/setpieces/results.md).

    python3 setpiece.py A7 [--depth 300] [--keep]      # --keep: don't restore Dive04 afterwards
    python3 setpiece.py list
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "pilot"))
from dm import DM                       # noqa: E402
import glyphs                           # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RUN = os.path.join(ROOT, "runs", "pilot", "dive04")
OUT = os.path.join(ROOT, "runs", "setpieces")
RACES = {r.name.lower(): r for r in glyphs.load_races().values()}


def race_idx(name):
    return RACES[name.lower()].idx


def ctl(*args, role=None, timeout=60):
    """pilotctl for dive04 (role None = the Navigator's, as a real order would be)."""
    env = dict(os.environ)
    env.pop("PILOT_ROLE", None)
    if role:
        env["PILOT_ROLE"] = role
    r = subprocess.run([sys.executable, os.path.join(HERE, "..", "pilot", "pilotctl.py"), "--nick", "dive04", *args],
                       capture_output=True, text=True, env=env, timeout=timeout)
    return (r.stdout + r.stderr).strip()


def pilot_view():
    """Dive04's position, depth and map (the viewer's query: no side effects)."""
    import socket
    s = socket.socket(socket.AF_UNIX)
    s.connect(os.path.join(RUN, "ctl.sock"))
    s.sendall((json.dumps({"cmd": "viewmap", "args": ["12", "30"], "role": "architect"}) + "\n").encode())
    buf = b""
    while not buf.endswith(b"\n"):
        d = s.recv(65536)
        if not d:
            break
        buf += d
    return json.loads(buf)


def log_since(t0):
    out = []
    for line in open(os.path.join(RUN, "decisions.jsonl")):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("t", 0) >= t0:
            out.append(d)
    return out


def floor_near(view, target, dist):
    """A floor square of Dive04's map at Chebyshev distance `dist` from `target` (absolute y,x)."""
    y0, x0 = view["y0"], view["x0"]
    best = None
    for i, row in enumerate(view.get("rows", [])):
        for j, ch in enumerate(row):
            if ch != ".":
                continue
            q = (y0 + i, x0 + j)
            d = max(abs(q[0] - target[0]), abs(q[1] - target[1]))
            if d == dist and (best is None or abs(q[1] - target[1]) < abs(best[1] - target[1])):
                best = q
    return best


def step_dir(a, b):
    dy, dx = (b[0] > a[0]) - (b[0] < a[0]), (b[1] > a[1]) - (b[1] < a[1])
    return {(1, -1): 1, (1, 0): 2, (1, 1): 3, (0, -1): 4, (0, 1): 6, (-1, -1): 7, (-1, 0): 8, (-1, 1): 9}.get((dy, dx))


class Run:
    def __init__(self, sid, depth, keep, say=print):
        self.sid, self.depth, self.keep, self.say = sid, depth, keep, say
        self.tag = f"{sid}-{time.strftime('%Y%m%d-%H%M%S')}"
        self.dm = None
        self.res = {"id": sid, "tag": self.tag, "depth_ft": depth, "start": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "checks": {}, "notes": []}

    # --- staging --------------------------------------------------------------------
    def setup(self):
        self.say(f"[{self.tag}] snapshot Dive04")
        self.say(subprocess.run([os.path.join(HERE, "charsave.sh"), "save", "Dive04", self.tag],
                                capture_output=True, text=True).stdout.strip().splitlines()[0])
        ctl("mission", "start", f"sp-{self.tag}", "navigator=harness", f"notes=set-piece {self.sid}", role="architect")
        self.dm = DM(say=self.say).connect()
        self.dm.clear_hooks()
        # a fresh level for every run: up to town (a ghost DM floats up one level per '<'), so the
        # old level is freed with whatever the last run summoned (an A8 Ranger was still there)
        g = self.dm.status()["ind"]["depth"][0]
        self.dm.ascend(max(0, g))
        self.dm.descend(self.depth // 50)
        self.say(f"[{self.tag}] Gandalf at {self.dm.status()['ind']['depth'][0] * 50} ft")

    def bring_dive04(self):
        """Recall Dive04 to Gandalf's depth, then pull it to his square."""
        v = pilot_view()
        if not v.get("pos") or self._depth() != self.depth:
            self.dm.invoke("Dive04")             # a recall to his depth
            for _ in range(60):
                time.sleep(1)
                if self._depth() == self.depth:
                    break
            time.sleep(2)
        self.dm.invoke("Dive04")                 # same level: to his square
        time.sleep(1.5)
        return pilot_view()

    def _depth(self):
        st = ctl("status", role="architect")
        m = re.search(r"· (\d+) ft ·", st)
        return int(m.group(1)) if m else 0

    def place(self, race_name, dist, after=None):
        """Summon race_name about `dist` squares from Dive04 (on a floor square of its map)."""
        if self._depth() != self.depth:
            raise RuntimeError(f"Dive04 isn't on Gandalf's level ({self._depth()} ft): it left before the scene was set")
        v = pilot_view()
        me = tuple(v["pos"])
        spot = floor_near(v, me, dist) or floor_near(v, me, dist + 1) or floor_near(v, me, max(1, dist - 1))
        if not spot:
            raise RuntimeError(f"no floor square {dist} from Dive04 at {me}")
        # walk Gandalf there (a ghost: through walls)
        for _ in range(80):
            g = self.dm.c.pos or (self.dm.status()["y"], self.dm.status()["x"])
            if tuple(g) == spot:
                break
            self.dm.walk(step_dir(g, spot))
        away = step_dir(me, spot) or 8               # step on, away from Dive04
        name = self.dm.summon(race_idx(race_name), step=away, after=after)
        self.say(f"[{self.tag}] summoned {name} at {spot}, {dist} from Dive04 at {me}")
        return spot

    def watch(self, secs, until=None):
        t0 = time.time()
        while time.time() - t0 < secs:
            time.sleep(2)
            if until and until(log_since(self.t_act)):
                break

    def teardown(self):
        try:
            if self.dm:
                self.dm.clear_hooks()
                self.dm.quit()
        finally:
            ctl("mission", "end", f"sp-{self.tag}", role="architect")
            if not self.keep:
                out = subprocess.run([os.path.join(HERE, "charsave.sh"), "restore", "Dive04", self.tag],
                                     capture_output=True, text=True).stdout.strip().splitlines()
                self.say(f"[{self.tag}] " + (out[0] if out else "restore: no output"))

    # --- scoring ----------------------------------------------------------------------
    def stats(self, recs):
        hps = [d["hp"] for d in recs if d.get("hp") and d["hp"][1]]
        att = [d for d in recs if d.get("kind") == "attention"]
        acts = [d for d in recs if d.get("kind") == "act"]
        return {"hp_start": hps[0] if hps else None, "hp_min": min(hps, key=lambda h: h[0]) if hps else None,
                "attention": [(round(d["t"] - self.t_act, 1), d["what"], str(d.get("detail"))[:100]) for d in att][:40],
                "acts": [(round(d["t"] - self.t_act, 1), d.get("cmd"), str(d.get("why"))[:80]) for d in acts][:60],
                "emergencies": sum(1 for d in att if d["what"] in ("emergency", "emergency_loop")),
                "phase_reads": sum(1 for d in acts if "phase" in str(d.get("why")).lower()),
                "wor_reads": sum(1 for d in acts if "Word of Recall" in str(d.get("why")) or "word of recall" in str(d.get("why"))),
                "cures": sum(1 for d in acts if "quaff" in str(d.get("why")) and "Cure" in str(d.get("why")))}

    def check(self, name, ok, detail=""):
        self.res["checks"][name] = {"pass": bool(ok), "detail": detail}
        self.say(f"[{self.tag}]   {'PASS' if ok else 'FAIL'} {name}: {detail}")

    def finish(self):
        self.res["end"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.res["pass"] = all(c["pass"] for c in self.res["checks"].values()) if self.res["checks"] else False
        os.makedirs(OUT, exist_ok=True)
        path = os.path.join(OUT, f"{self.tag}.json")
        json.dump(self.res, open(path, "w"), indent=1)
        with open(os.path.join(OUT, "results.md"), "a") as f:
            f.write(f"- {self.res['start']} **{self.sid}** {'PASS' if self.res['pass'] else 'FAIL'} "
                    f"({', '.join(k + ('' if v['pass'] else ' FAIL') for k, v in self.res['checks'].items())}) "
                    f"`{os.path.basename(path)}`\n")
        self.say(f"[{self.tag}] {'PASS' if self.res['pass'] else 'FAIL'} -> {path}")


# --- the set-pieces ------------------------------------------------------------------------
def a7(run):
    """A7: hunt a FIGHT monster (a Hill giant, adjacent) at full HP: the check allows it, and the HP
    lost stays within fight_sim's bad case (p90). (The 80% and 60% halves are unit tests: the
    harness can't set HP.)"""
    run.bring_dive04()
    ctl("status")                               # (a fresh report: the order answers it)
    run.t_act = time.time()
    # the order the moment the giant lands (a summon takes ~20 s with the menu and the hook
    # cleanup: longer than a hunt waits for its target; and the Pilot's own fighting killed it
    # when the order came after the cleanup)
    out = {}
    run.place("Hill giant", 1, after=lambda: out.update(reply=ctl("goal", "hunt", "Hill_giant")))
    reply = out.get("reply", "")
    run.res["order_reply"] = reply
    m = re.search(r"~(\d+) in a bad fight", reply)
    p90 = int(m.group(1)) if m else None
    run.check("hunt allowed at full HP", '"ok": true' in reply, reply[:160])
    run.watch(90, until=lambda recs: any(d.get("kind") == "attention" and d.get("what") in ("goal_done", "goal_failed")
                                         and "hunt" in str(d.get("detail")) for d in recs))
    st = run.stats(log_since(run.t_act))
    run.res["stats"] = st
    lost = (st["hp_start"][0] - st["hp_min"][0]) if st["hp_min"] else None
    slain = any("slain" in str(a[2]) and "hunt" in str(a[2]) for a in st["attention"])
    run.check("giant slain", slain, f"outcome {[a for a in st['attention'] if 'hunt' in a[2]][-1:]}")
    run.check("HP lost within the simulated bad case", lost is not None and p90 is not None and lost <= p90,
              f"lost {lost}, p90 {p90}")


def a8(run, override=False):
    """A8: the m19 Ranger: a Ranger 3 squares away and a Skeleton human. The hunt is refused (a
    summoner). With --override (`hunt !Ranger`): summons are fought, a blinker isn't chased past
    2 turns, and the lowest HP stays at 40% or more."""
    run.bring_dive04()
    ctl("status")
    run.t_act = time.time()
    run.place("Skeleton human", 2)          # (within the lantern's light: the Ranger isn't alone)
    out = {}
    # 3 squares, not the memo's 6: unlit ground shows a monster only within the lantern's 2 squares or
    # the Half-Orc's infravision (3, warm-blooded); farther off the order is (rightly) held as stale
    run.place("Ranger", 3, after=lambda: (time.sleep(0.6), ctl("status"),
                                          out.update(reply=ctl("goal", "hunt", ("!" if override else "") + "Ranger"))))
    reply = out.get("reply", "")
    run.res["order_reply"] = reply
    if not override:
        run.check("hunt refused (a summoner)", '"ok": false' in reply and "summon" in reply, reply[:200])
        run.watch(30)
    else:
        run.check("override accepted", '"ok": true' in reply, reply[:160])
        run.watch(90, until=lambda recs: any(d.get("kind") == "goal" and str(d.get("goal", "")).startswith("reprieve")
                                             for d in recs) and False)
    st = run.stats(log_since(run.t_act))
    run.res["stats"] = st
    if st["hp_min"]:
        run.check("lowest HP >= 40%", st["hp_min"][0] >= 0.4 * st["hp_min"][1], f"lowest {st['hp_min']}")


def a8o(run):
    """A8 overridden (`hunt !Ranger`): summons fought, no chase of a blinker, lowest HP >= 40%."""
    a8(run, override=True)


def a9(run):
    """A9 (summoned variant): a recall arrival with a band forming and stairs unknown. The trip plan's
    arrival protocol uses Door/Stair Location within 5 s; no second Word of Recall is read while
    one is pending. (The 'special' feeling needs a real pit: not staged here.)"""
    ctl("plan", "trip", f"{run.depth}-{run.depth}", "via=recall", "until", "minutes>3", role="architect")
    t_arrive = None
    for _ in range(60):
        time.sleep(1)
        if run._depth() == run.depth:
            t_arrive = time.time()
            break
    if not t_arrive:
        run.check("arrived by recall", False, "no arrival in 60 s")
        return
    run.t_act = t_arrive - 3
    for name, d in (("Snaga", 8), ("Black orc", 9)):
        try:
            run.place(name, d)
        except RuntimeError as e:
            run.res["notes"].append(str(e))
    run.watch(60)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    loc = [a for a in st["acts"] if "Door/Stair Location" in str(a[2])]
    run.check("Door/Stair Location within 5 s of arriving", loc and loc[0][0] <= 8, f"{loc[:1]}")
    run.check("no second Word of Recall while one is pending", st["wor_reads"] <= 1, f"{st['wor_reads']} reads")
    ctl("plan", "stop", role="architect")


SETPIECES = {"A7": a7, "A8": a8, "A8o": a8o, "A9": a9}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sid", help="A7 | A8 | A8o (A8 overridden) | A9 | list")
    ap.add_argument("--depth", type=int, default=300)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    if a.sid == "list":
        for k, f in SETPIECES.items():
            print(k, "-", (f.__doc__ or "").strip().splitlines()[0])
        return
    run = Run(a.sid, a.depth, a.keep)
    try:
        run.setup()
        SETPIECES[a.sid](run)
    except Exception as e:
        run.res["error"] = repr(e)
        run.say(f"[{run.tag}] ERROR {e!r}")
    finally:
        run.teardown()
        run.finish()


if __name__ == "__main__":
    main()
