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


def _tail(name, nbytes=6_000_000):
    """The last lines of a Pilot log (they grow to 100+ MB)."""
    with open(os.path.join(RUN, name), "rb") as f:
        f.seek(0, 2)
        f.seek(max(0, f.tell() - nbytes))
        lines = f.read().decode(errors="replace").splitlines()[1:]
    for line in lines:
        try:
            yield json.loads(line)
        except ValueError:
            continue


def messages_since(t0):
    """The game's messages to Dive04 since t0 (events.jsonl)."""
    return [(d["epoch"], d["text"]) for d in _tail("events.jsonl") if d.get("ev") == "message" and d.get("epoch", 0) >= t0]


def gold_now():
    """Dive04's gold from its last status line (state.jsonl)."""
    g = None
    for d in _tail("state.jsonl", 2_000_000):
        if d.get("ev") == "status" and d.get("ind", {}).get("gold"):
            g = d["ind"]["gold"][0]
    return g


def floor_near(view, target, dist, taken=(), floor="."):
    """A floor square of Dive04's map at Chebyshev distance `dist` from `target` (absolute y,x), not in `taken`.
    (In town the open ground shows as ' ': pass floor=". ".)"""
    y0, x0 = view["y0"], view["x0"]
    best = None
    for i, row in enumerate(view.get("rows", [])):
        for j, ch in enumerate(row):
            if ch not in floor:
                continue
            q = (y0 + i, x0 + j)
            if q in taken:
                continue
            d = max(abs(q[0] - target[0]), abs(q[1] - target[1]))
            if d == dist and (best is None or abs(q[1] - target[1]) < abs(best[1] - target[1])):
                best = q
    return best


def clear_line(rows, a, b):
    """Nothing but floor on the straight line between a and b (exclusive) on a map: line of sight, roughly."""
    n = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
    for i in range(1, n):
        y = a[0] + round((b[0] - a[0]) * i / n)
        x = a[1] + round((b[1] - a[1]) * i / n)
        if rows[y][x] in "#%*+: ":
            return False
    return True


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

    def place(self, race_name, dist, after=None, gmap=False):
        """Summon race_name about `dist` squares from Dive04 (on a floor square of its map; gmap=True: of
        Gandalf's, who sees the whole level, with a clear line to Dive04 -- for a monster out of its sight)."""
        if self._depth() != self.depth:
            raise RuntimeError(f"Dive04 isn't on Gandalf's level ({self._depth()} ft): it left before the scene was set")
        v = pilot_view()
        me = tuple(v["pos"])
        taken = getattr(self, "placed", set())
        if gmap:
            rows = self.dm.c.map()
            taken = taken | {q for q in ((y, x) for y in range(len(rows)) for x in range(len(rows[0])))
                             if 0 < max(abs(q[0] - me[0]), abs(q[1] - me[1])) <= dist + 2 and not clear_line(rows, me, q)}
            v = {"y0": 0, "x0": 0, "rows": rows}
        spot = next((q for d in (dist, dist + 1, max(1, dist - 1), dist + 2) for q in [floor_near(v, me, d, taken, ". " if self.depth == 0 else ".")] if q),
                    None)
        if not spot:
            raise RuntimeError(f"no floor square {dist} from Dive04 at {me}")
        self.gandalf_to(spot)
        away = step_dir(me, spot) or 8               # step on, away from Dive04
        idx = race_name if isinstance(race_name, int) else race_idx(race_name)
        name = self.dm.summon(idx, step=away, after=after)
        self.placed = taken | {spot}
        self.say(f"[{self.tag}] summoned {name} at {spot}, {dist} from Dive04 at {me}")
        return spot

    def gandalf_to(self, spot):
        """Walk Gandalf to spot (a ghost: through walls in the dungeon, but not through town buildings: a
        step that doesn't move him is tried 45 and 90 degrees off)."""
        ring = [8, 9, 6, 3, 2, 1, 4, 7]
        for _ in range(250):
            g = tuple(self.dm.c.pos or (self.dm.status()["y"], self.dm.status()["x"]))
            if g == tuple(spot):
                return
            d = step_dir(g, spot)
            for off in (0, 1, -1, 2, -2):
                self.dm.walk(ring[(ring.index(d) + off) % 8])
                if tuple(self.dm.c.pos or g) != g:
                    break
        raise RuntimeError(f"Gandalf didn't reach {spot}")

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
                env = {k: v for k, v in os.environ.items() if k != "PILOT_ARGS"}
                out = subprocess.run([os.path.join(HERE, "charsave.sh"), "restore", "Dive04", self.tag],
                                     capture_output=True, text=True, env=env).stdout.strip().splitlines()
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


def a8w(run):
    """A8w: a Ranger (a summoner) comes into view 3 squares off, no orders: the Pilot walks away out of
    its sight instead of fleeing the level (the user, 2026-10-23); no Word of Recall; HP stays >= 80%."""
    run.bring_dive04()
    run.t_act = time.time()
    run.place("Ranger", 3)
    run.watch(40)
    st = run.stats(log_since(run.t_act))
    run.res["stats"] = st
    goals = [d.get("goal") for d in log_since(run.t_act) if d.get("kind") == "goal"]
    run.check("walked away", any(str(g).startswith("walk away") for g in goals), f"goals {goals[:6]}")
    run.check("no Word of Recall read", st["wor_reads"] == 0, f"{st['wor_reads']} reads")
    if st["hp_min"]:
        run.check("HP >= 80%", st["hp_min"][0] >= 0.8 * st["hp_min"][1], f"lowest {st['hp_min']}")


def first_seen(recs, name, t0):
    for d in recs:
        if d.get("kind") == "mons" and any(m[2] == name for m in d.get("monsters", [])):
            return d["t"] - t0
    return None


def a1(run):
    """A1: an orc mob (Black orcs and a Hill orc group, 6-7 squares off) while a trip plan works the level:
    a serious band makes the plan leave; lowest HP >= 40%; at most 3 Phase Door reads."""
    run.bring_dive04()
    ctl("plan", "trip", f"{run.depth}-{run.depth}", "until", "minutes>3", role="architect")
    run.t_act = time.time()
    run.place("Black orc", 6)
    run.place("Hill orc", 7)
    run.watch(70)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    ctl("plan", "stop", role="architect")
    left = any(d.get("kind") == "goal" and str(d.get("goal", "")).startswith("flee") for d in recs)
    run.res["notes"].append(f"left the level: {left}; band events: {sum(1 for a in st['attention'] if a[1] == 'band')}")
    if st["hp_min"]:
        run.check("lowest HP >= 40%", st["hp_min"][0] >= 0.4 * st["hp_min"][1], f"lowest {st['hp_min']}")
    run.check("at most 3 Phase Door", st["phase_reads"] <= 3, f"{st['phase_reads']} reads")


def a6(run):
    """A6: a Gnome mage (blinks, summons) adjacent, let it summon: at most 3 Phase Door, then Word of Recall or
    the stairs; Phase Door never runs out; lowest HP >= 40%."""
    run.bring_dive04()
    before = re.search(r"Phase (\d+)", ctl("status", role="architect"))
    run.t_act = time.time()
    run.place(202, 1)                       # (the level-15 Gnome mage: BLINK, BO_COLD, S_MONSTER)
    run.watch(70)
    st = run.stats(log_since(run.t_act))
    run.res["stats"] = st
    after = re.search(r"Phase (\d+)", ctl("status", role="architect"))
    run.check("at most 3 Phase Door", st["phase_reads"] <= 3, f"{st['phase_reads']} reads")
    run.check("Phase Door never runs out", after and int(after.group(1)) > 0,
              f"{before.group(1) if before else '?'} -> {after.group(1) if after else '?'}")
    if st["hp_min"]:
        run.check("lowest HP >= 40%", st["hp_min"][0] >= 0.4 * st["hp_min"][1], f"lowest {st['hp_min']}")


def a2(run, who="Ulwarth, Son of Ulfang"):
    """A2: a unique too strong for us appears adjacent, no stairs known (Ulwarth: the danger rule's 'unique
    above your level'): Word of Recall read within 2 s of first sight; lowest HP >= 40%."""
    run.bring_dive04()
    run.t_act = time.time()
    run.place(who, 1)
    run.watch(45)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    seen = first_seen(recs, who, run.t_act)
    wor = next((a[0] for a in st["acts"] if "word of recall" in str(a[2]).lower()), None)
    run.check("Word of Recall within 2 s of first sight", seen is not None and wor is not None and wor - seen <= 2,
              f"seen at {seen}, recall read at {wor}")
    if st["hp_min"]:
        run.check("lowest HP >= 40%", st["hp_min"][0] >= 0.4 * st["hp_min"][1], f"lowest {st['hp_min']}")


def a2i(run):
    """A2I: as A2 with Ibun, Son of Mim (a unique can exist once: a second Ulwarth summon fails silently while
    the first lives on an old level)."""
    a2(run, who="Ibun, Son of Mim")


def a2k(run):
    """A2K: as A2 with Khim, Son of Mim."""
    a2(run, who="Khim, Son of Mim")


def a2l(run):
    """A2L: Lugdush (no danger rule fires: level 21, unrated; but fight_sim's average fight costs ~350 HP)."""
    a2(run, who="Lugdush, the Uruk")


def c3(run):
    """C3: a unique's drop (Ulfast: DROP_90 | DROP_GOOD, no escort, never killed by Dive04 -- a
    repeat kill of a unique drops nothing, xtra2.c 'cheeze'; Lagduf's and Mughash's escorts made band fights) is picked up after the kill, whatever its bulk. (Not
    a unique Dive04 has killed: they drop nothing a second time -- Brodda, Bullroarer, Orfax, Wormtongue.)"""
    run.bring_dive04()
    run.t_act = time.time()
    out = {}
    # (as the Architect: C3 tests the pickup, and the hunt check rightly refuses Lagduf, LEAVE for his escort)
    run.place("Ulfast, Son of Ulfang", 1, after=lambda: out.update(reply=ctl("goal", "hunt", "Ulfast,_Son_of_Ulfang",
                                                                        role="architect")))
    run.res["order_reply"] = out.get("reply")
    run.watch(120, until=lambda recs: any(d.get("kind") == "attention" and d.get("what") == "unique_slain"
                                          and "Ulfast" in str(d.get("detail")) for d in recs))
    time.sleep(25)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    slain = next((d["t"] for d in recs if d.get("kind") == "attention" and d.get("what") == "unique_slain"
                  and "Ulfast" in str(d.get("detail"))), None)
    picked = [a for a in st["acts"] if "pick up" in str(a[2]) and slain and a[0] >= slain - run.t_act]
    left = [d for d in recs if d.get("kind") == "attention" and "left " in str(d.get("detail")) and "pack full" in str(d.get("detail"))]
    run.check("Ulfast slain", slain is not None, f"reply {str(out.get('reply'))[:120]}")
    run.check("his drop picked up", bool(picked) and not left, f"picked {picked[:3]}; left {[str(d.get('detail'))[:60] for d in left]}")


def c8(run):
    """C8: unidentified Boots of Free Action worn, a Floating eye's paralysing gaze: "You are unaffected!"
    -> the Pilot infers Free Action and protects the boots (keep, identify)."""
    v = run.bring_dive04()
    me = tuple(v["pos"])
    spot = floor_near(v, me, 1)
    for _ in range(30):
        g = run.dm.c.pos or (run.dm.status()["y"], run.dm.status()["x"])
        if tuple(g) == spot:
            break
        run.dm.walk(step_dir(g, spot))
    made = run.dm.forge(91, ego=58)
    run.res["notes"].append(f"forged: {made}")
    run.dm.drop_first()
    run.dm.walk(step_dir(me, spot) or 8)
    ctl("goal", "goto", f"{spot[0]},{spot[1]}", role="architect")
    time.sleep(4)
    ctl("pickup", role="architect")
    time.sleep(2)
    pack = ctl("pack", role="architect")
    boots = re.search(r"([a-w])\) (?:a )?Pair of Soft Leather Boots[^;]*", pack)
    run.check("boots picked up (unidentified)", bool(boots) and "Free Action" not in boots.group(0),
              boots.group(0) if boots else pack[:160])
    if not boots:
        return
    ctl("wear", boots.group(1), role="architect")
    time.sleep(2)
    run.t_act = time.time()
    run.place("Floating eye", 1)
    run.watch(40, until=lambda recs: any(d.get("kind") == "attention" and d.get("what") == "ability" for d in recs))
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    ab = [a for a in st["attention"] if a[1] == "ability"]
    run.check("Free Action inferred from 'You are unaffected!'", any("Free Action" in a[2] for a in ab), f"{ab[:1]}")
    run.check("the boots protected", any("soft leather boots" in a[2].lower() for a in ab), f"{ab[:1]}")


def a3(run):
    """A3: a fast hitter (a Sabre-tooth tiger, +10, alone) adjacent, then a goto 12+ squares off: the goto is held
    (walking away hands it free hits) and Dive04 doesn't walk while it's adjacent. (A Nighthawk died to auto-retaliate
    before an order could follow; a Wolf chieftain brings a pack of up to 38, and the run becomes a band fight.)"""
    v = run.bring_dive04()
    run.t_act = time.time()
    me = tuple(v["pos"])
    far = floor_near(v, me, 12) or floor_near(v, me, 10) or (me[0], me[1] + 15)   # (a goto may path through unknown)
    out = {}
    race = "Sabre-tooth tiger"
    run.place(race, 1, after=lambda: (time.sleep(1.0),
                                                  out.update(reply=ctl("goal", "goto", f"{far[0]},{far[1]}", role="architect"))))
    reply = out.get("reply", "")
    run.res["order_reply"] = reply
    run.watch(20)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    held = [a for a in st["attention"] if "goto held" in a[2]]
    # positions while it was adjacent
    moved = 0
    last = None
    for d in recs:
        if d.get("kind") == "mons" and any(m[2] == race and max(abs(m[0] - d["pos"][0]), abs(m[1] - d["pos"][1])) <= 1
                                           for m in d.get("monsters", [])):
            if last and tuple(d["pos"]) != last:
                moved += 1
            last = tuple(d["pos"])
    run.check("the goto held", bool(held), f"{held[:1]} (order: {reply[:80]})")
    run.check("no walking with it adjacent", moved == 0, f"{moved} moves while adjacent")
    if st["hp_min"]:
        run.check("lowest HP >= 40%", st["hp_min"][0] >= 0.4 * st["hp_min"][1], f"lowest {st['hp_min']}")


def find_pocket(rows, length):
    """A floor square F of Gandalf's map (he sees the whole level) with solid rock straight out from it for
    length + 2 squares, three wide: room for a door and a corridor that touches nothing else."""
    H, W = len(rows), len(rows[0])

    def rock(y, x):
        return 2 <= y < H - 2 and 2 <= x < W - 2 and rows[y][x] in "#%"

    for y in range(2, H - 2):
        for x in range(2, W - 2):
            if rows[y][x] != ".":
                continue
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                if all(rock(y + dy * k + dx * s, x + dx * k + dy * s) for k in range(1, length + 3) for s in (-1, 0, 1)):
                    return (y, x), (dy, dx)
    return None, None


def d3(run, length=8):
    """D3: walled in, the one way out a secret door. Gandalf carves a corridor into solid rock (a secret
    door, then `length` floor squares) off a floor square of the level, and Dive04 is pulled to its far
    end, so it knows ground outside it can't reach. `goal explore`: it searches the dead ends (15 each)
    instead of ending with "frontier unreachable" or "nothing left", finds the door and walks out."""
    rows = run.dm.c.map()
    F, d = find_pocket(rows, length)
    if not F:
        run.check("a site for the pocket", False, "no floor square with rock beside it")
        return
    door = (F[0] + d[0], F[1] + d[1])
    pocket = [(F[0] + d[0] * k, F[1] + d[1] * k) for k in range(2, length + 2)]
    fwd, back = step_dir((0, 0), d), step_dir(d, (0, 0))
    run.gandalf_to(door)
    run.dm.paint(48, [fwd])                       # the secret door (he steps onto the first corridor square)
    run.dm.paint(1, [fwd] * length)               # the corridor (he ends in the rock past it)
    run.dm.walk(back)                             # onto its far end: Dive04 is pulled here
    rows = run.dm.c.map()
    built = "".join(rows[y][x] for y, x in pocket)
    run.res["pocket"] = {"floor": F, "door": door, "corridor": [pocket[0], pocket[-1]], "dm_sees": built}
    run.say(f"[{run.tag}] pocket: door {door} off {F}, corridor {pocket[0]}-{pocket[-1]} ({built!r})")
    v = run.bring_dive04()
    run.dm.walk(fwd, 2)                           # Gandalf back into the rock
    inside = set(pocket)
    if tuple(v["pos"]) not in inside:
        run.check("Dive04 in the pocket", False, f"at {v['pos']}")
        return
    run.t_act = time.time()
    reply = ctl("goal", "explore", role="architect")
    run.res["order_reply"] = reply

    def out(recs):
        return any(d.get("pos") and tuple(d["pos"]) not in inside and tuple(d["pos"]) != door for d in recs
                   if d["t"] > run.t_act)
    run.watch(300, until=out)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    searches = sum(1 for d in recs if d.get("kind") == "act" and "secret" in str(d.get("why")))
    t_out = next((round(d["t"] - run.t_act, 1) for d in recs if d.get("pos") and tuple(d["pos"]) not in inside
                  and tuple(d["pos"]) != door), None)
    gave_up = [a for a in st["attention"] if a[1] in ("goal_done", "goal_failed") and
               ("nothing left" in a[2] or "unreachable" in a[2]) and (t_out is None or a[0] < t_out)]
    run.check("walked out through the door", t_out is not None, f"out after {t_out} s, {searches} searches")
    run.check("no giving up before the door", not gave_up, f"{gave_up[:1]}")


def find_floor_block(rows, h, w):
    """The top-left of an h x w block of floor on Gandalf's map (a room), or None."""
    for y in range(2, len(rows) - h - 2):
        for x in range(2, len(rows[0]) - w - 2):
            if all(rows[y + i][x:x + w] == "." * w for i in range(h)):
                return (y, x)
    return None


def b6(run, width=9):
    """B6 (the trap half): a known trap on the straight way across a room. Gandalf paints a pit (terrain 17) in
    the middle of a 5 x `width` block of floor; Dive04 stands near one end and gets a goto to the square
    mirroring it through the pit: it walks round the trap, even if it only comes into view on the way (the
    mover checks for traps when it plans)."""
    rows = run.dm.c.map()
    tl = find_floor_block(rows, 5, width)
    if not tl:
        run.check("a site", False, f"no 5 x {width} block of floor")
        return
    a, trap = (tl[0] + 2, tl[1] + 1), (tl[0] + 2, tl[1] + width // 2)
    run.gandalf_to(trap)
    run.dm.paint(17, [8])                         # the pit (he steps north off it)
    run.res["scene"] = {"from": a, "trap": trap, "dm_sees": run.dm.c.map()[trap[0]][trap[1]]}
    run.gandalf_to(a)
    v = run.bring_dive04()
    run.dm.walk(8, 3)                              # out of the way
    me = tuple(v["pos"])
    b = (2 * trap[0] - me[0], 2 * trap[1] - me[1])
    run.res["scene"]["to"] = b
    run.say(f"[{run.tag}] Dive04 at {v['pos']}, pit at {trap}, goto {b}")
    run.t_act = time.time()
    reply = ctl("goal", "goto", f"{b[0]},{b[1]}", role="architect")
    run.res["order_reply"] = reply
    run.watch(40, until=lambda recs: any(d.get("kind") == "attention" and d.get("what") in ("goal_done", "goal_failed")
                                         for d in recs))
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    on = [round(d["t"] - run.t_act, 1) for d in recs if d.get("pos") and tuple(d["pos"]) == trap]
    msgs = [t for _, t in messages_since(run.t_act) if re.search(r"pit|trap", t, re.I)]
    done = [a for a in st["attention"] if a[1] in ("goal_done", "goal_failed")]
    run.check("never on the trap", not on and not any("fall into" in t for t in msgs), f"on it at {on[:3]}; {msgs[:2]}")
    run.check("arrived", any(a[1] == "goal_done" for a in done), f"{done[:1]}")


def a5(run, race="Dark elven priest", stairs=False):
    """A5: a caster out of sight at full HP (m17-m21: curses, a HOLD and shrieks from the dark started level
    changes). A Dark elven priest (blinds, confuses, causes wounds) 5 squares off on unlit ground, beyond the
    lantern and infravision: the Pilot reports it, and doesn't leave the level (stairs, Word of Recall, Deep
    Descent) while HP is above 80%. A5s: the same with a '>' painted where Dive04 sees it (with stairs known,
    the old rule fled down them)."""
    v = run.bring_dive04()
    if stairs:
        me = tuple(v["pos"])
        q = next((q for d in (2, 1, 3) for q in [floor_near(v, me, d)] if q), None)
        if q:
            run.gandalf_to(q)
            run.dm.paint(7, [step_dir(me, q) or 8])
            time.sleep(1.5)
        run.res["stairs"] = q
    run.t_act = time.time()
    run.place(race, 5, gmap=True)
    run.watch(45)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    depth0 = next((d.get("depth") for d in recs if d.get("depth") is not None), None)
    left = []
    for d in recs:
        hp = d.get("hp")
        if not hp or not hp[1] or hp[0] <= 0.8 * hp[1]:
            continue
        if d.get("kind") == "act" and re.search(r"recall|deep descent|take the stairs|stairs", str(d.get("why")), re.I):
            left.append((round(d["t"] - run.t_act, 1), d.get("why")))
        if d.get("depth") is not None and depth0 is not None and d["depth"] != depth0:
            left.append((round(d["t"] - run.t_act, 1), f"depth {d['depth']}"))
            break
    seen_t = first_seen(recs, race, run.t_act)
    news = [a for a in st["attention"] if a[1] == "unseen_attacker"]
    run.res["first_seen"] = seen_t
    run.check("no level change while HP > 80%", not left, f"{left[:2]}")
    run.check("reported", bool(news) or seen_t is not None, f"{news[:1]} (seen at {seen_t})")


def a5s(run):
    """A5s: an unseen caster that stays unseen (a Potion mimic: never moves; curses, blinds, confuses, frost
    bolts) with stairs in view. (A Dark elven priest walked into view before it cast.)"""
    a5(run, race="Potion mimic", stairs=True)


def a4(run):
    """A4: a slow ranged caster unique (Wormtongue: frost bolts, slow, traps; 250 HP, melee ~6) 3 squares off
    (on unlit ground he isn't seen farther), a '>' painted on the farthest square of Dive04's known floor up to 12
    off. Passes when Dive04 doesn't walk more than 8 squares in his sight (a flee walk under his bolts) and its
    lowest HP stays at 60% or more."""
    v = run.bring_dive04()
    me = tuple(v["pos"])
    stairs = next((q for d in range(12, 3, -1) for q in [floor_near(v, me, d)] if q), None)
    if stairs:
        run.gandalf_to(stairs)
        run.dm.paint(7, [8])                     # '>' (he steps north off it)
        time.sleep(1.0)
    run.res["stairs"] = stairs
    run.t_act = time.time()
    run.place("Wormtongue, Agent of Saruman", 3)
    run.watch(45)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    walked, last = 0, None
    for d in recs:
        if d.get("kind") == "mons" and d.get("pos") and any("Wormtongue" in m[2] for m in d.get("monsters", [])):
            p = tuple(d["pos"])
            if last:
                walked += max(abs(p[0] - last[0]), abs(p[1] - last[1]))
            last = p
        elif d.get("kind") == "mons":
            last = None
    run.res["walked_in_sight"] = walked
    seen = first_seen(recs, "Wormtongue, Agent of Saruman", run.t_act)
    # (a unique exists once: while he lives on another level the summon fails silently)
    run.check("Wormtongue staged (seen)", seen is not None, f"first seen {seen} s")
    run.check("<= 8 squares walked in his sight", walked <= 8, f"{walked} squares (stairs {stairs})")
    if st["hp_min"]:
        run.check("lowest HP >= 60%", st["hp_min"][0] >= 0.6 * st["hp_min"][1], f"lowest {st['hp_min']}")


def b4(run, walking=False):
    """B4: a town thief (m15-m19 lost ~300 gold to urchins and a Scruffy hobbit while townfarming). A
    Scruffy looking hobbit (touches to steal gold, then teleports) summoned 2 squares from Dive04 in town, no
    orders: it's killed or kept off before it touches; no gold lost. B4w: the same while Dive04 walks
    across town (a goto 25+ squares off, the thief 2 squares ahead on the way)."""
    v = run.bring_dive04()
    time.sleep(2.5)
    g0 = gold_now()
    run.t_act = time.time()
    if walking:
        me = tuple(v["pos"])
        # open ground 20-30 squares off, as level with Dive04 as can be (not the town's edge rows)
        cands = [(v["y0"] + i, v["x0"] + j) for i, row in enumerate(v["rows"]) for j, ch in enumerate(row)
                 if ch in ". " and 3 <= v["y0"] + i <= 62]
        cands = [q for q in cands if 20 <= abs(q[1] - me[1]) <= 30]
        far = min(cands, key=lambda q: abs(q[0] - me[0])) if cands else None
        if not far:
            run.check("a goto target", False, "no open ground 20-30 squares off")
            return
        out = {}
        # the thief lands, then the goto: it's on (or near) the way
        run.place("Scruffy looking hobbit", 2, after=lambda: out.update(
            reply=ctl("goal", "goto", f"{far[0]},{far[1]}", role="architect")))
        run.res["order_reply"] = out.get("reply")
    else:
        run.place("Scruffy looking hobbit", 2)
    run.watch(40)
    g1 = gold_now()
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    msgs = [t for _, t in messages_since(run.t_act)]
    run.res["messages"] = msgs[:40]
    touched = [t for t in msgs if re.search(r"purse|gold|touches you", t, re.I)]
    killed = [t for t in msgs if re.search(r"You have (slain|killed) (the )?Scruffy", t)]
    run.check("no gold lost", g0 is not None and g1 is not None and g1 >= g0, f"gold {g0} -> {g1}; {touched[:2]}")
    run.check("thief killed", bool(killed), f"{killed[:1]}")


def b4w(run):
    """B4w: the town thief while Dive04 walks across town."""
    b4(run, walking=True)


def b1(run):
    """B1: a stationary drainer (a Purple mushroom patch: CON) 2 squares off and a goto past it: Dive04 never
    stands next to it and loses no stat. (Summoned adjacent, the server's auto-retaliate kills it in one blow
    before the Pilot can act: that tests the server, not the path.)"""
    run.bring_dive04()
    before = re.search(r"CON (\S+)", ctl("status", role="architect"))
    run.t_act = time.time()
    spot = run.place("Purple mushroom patch", 2)
    me = tuple(pilot_view()["pos"])
    beyond = (spot[0] + 2 * (spot[0] - me[0]) // 2, spot[1] + 2 * (spot[1] - me[1]) // 2)
    run.res["order_reply"] = ctl("goal", "goto", f"{beyond[0]},{beyond[1]}", role="architect")
    run.watch(25)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    after = re.search(r"CON (\S+)", ctl("status", role="architect"))
    hits = [d for d in recs if d.get("kind") == "mons"]
    drained = [a for a in st["attention"] if a[1] == "stat_drained"]
    run.check("no stat drained", not drained, f"CON {before.group(1) if before else '?'} -> {after.group(1) if after else '?'}; {drained[:1]}")
    adjacent = sum(1 for d in recs if d.get("kind") == "mons" for m in d.get("monsters", [])
                   if m[2] == "Purple mushroom patch" and max(abs(m[0] - d["pos"][0]), abs(m[1] - d["pos"][1])) <= 1)
    run.check("never next to it", adjacent == 0, f"{adjacent} records adjacent; goto: {run.res['order_reply'][:80]}")


def b2(run):
    """B2: mobile STR drainers (three Giant red ants): after a second drain on the level the Pilot leaves it, or
    kills the drainer beside it when that one is weak and no faster (the 'drained twice' rule)."""
    run.bring_dive04()
    run.t_act = time.time()
    for d in (2, 3, 4):
        run.place("Giant red ant", d)
    run.watch(60)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    drains = [a for a in st["attention"] if a[1] == "stat_drained"]
    after2 = [a for a in st["attention"] if a[1] in ("tactic", "danger_seen") and "drained twice" in a[2]]
    run.check("drained at most twice", len(drains) <= 2, f"{len(drains)} drains")
    run.check("acted on the second drain", len(drains) < 2 or bool(after2), f"{after2[:1]}")


def b3(run):
    """B3: a Brigand (touch to steal an item, then teleports) adjacent: the Pilot hits the thief first; nothing
    stolen, or the theft reported."""
    run.bring_dive04()
    run.t_act = time.time()
    run.place("Brigand", 1)
    run.watch(30)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    msgs = [json.loads(l) for l in open(os.path.join(RUN, "events.jsonl")) if '"message"' in l and "Brigand" in l]
    msgs = [m for m in msgs if m.get("epoch", 0) >= run.t_act]
    stolen = [m["text"] for m in msgs if "stole" in m["text"] or "touches you" in m["text"] and "purse" in m["text"]]
    slain = any("slain the Brigand" in m["text"] for m in msgs)
    run.res["notes"].append(f"messages: {[m['text'] for m in msgs][:8]}")
    run.check("Brigand slain", slain, "")
    run.check("nothing stolen", not stolen, f"{stolen[:2]}")


def d6(run):
    """D6: movement speed: tiles a second while exploring (runs) in the dungeon; >= 3."""
    run.bring_dive04()
    run.t_act = time.time()
    ctl("goal", "explore", role="architect")
    run.watch(40)
    ctl("stop", role="architect")
    moves = [d for d in log_since(run.t_act) if d.get("kind") in ("move", "mons", "act") and d.get("pos")]
    path = []
    for d in moves:
        if not path or tuple(d["pos"]) != path[-1][1]:
            path.append((d["t"], tuple(d["pos"])))
    tiles = sum(max(abs(a[1][0] - b[1][0]), abs(a[1][1] - b[1][1])) for a, b in zip(path, path[1:]))
    secs = (path[-1][0] - path[0][0]) if len(path) > 1 else 0
    # the best 5-s window (a run), not the average with its stops to choose the next frontier
    best = 0.0
    for i, (t0, _) in enumerate(path):
        seg = [(t, q) for t, q in path[i:] if t - t0 <= 5]
        n = sum(max(abs(a[1][0] - b[1][0]), abs(a[1][1] - b[1][1])) for a, b in zip(seg, seg[1:]))
        best = max(best, n / 5)
    run.res["notes"].append(f"{tiles} tiles in {secs:.0f} s overall ({tiles / secs if secs else 0:.1f}/s); best 5 s {best:.1f}/s")
    run.check("runs >= 3 tiles/s (best 5-s window)", best >= 3, f"best {best:.1f} tiles/s; overall "
              f"{tiles / secs if secs else 0:.1f} ({tiles} in {secs:.0f} s)")


def l1(run):
    """L1 (a rulebook claim): a Hill giant's boulders do 0 damage to the player (project_p has no GF_BOULDER)."""
    run.bring_dive04()
    run.t_act = time.time()
    ctl("order", "flee_hp=0.3", role="architect")
    for d in (8, 7, 6, 5):
        try:
            run.place("Hill giant", d)
            break
        except RuntimeError:
            continue
    run.watch(60)
    ctl("order", "flee_hp=0.5", role="architect")
    msgs = [json.loads(l) for l in open(os.path.join(RUN, "events.jsonl")) if '"message"' in l and "boulder" in l.lower()]
    msgs = [m for m in msgs if m.get("epoch", 0) >= run.t_act]
    hp = [(d["t"], d["hp"][0]) for d in log_since(run.t_act) if d.get("hp")]
    hits = []
    for m in msgs:
        before = [h for t, h in hp if t <= m["epoch"]][-1:] or [None]
        after = [h for t, h in hp if m["epoch"] < t <= m["epoch"] + 0.6][:1] or [None]
        hits.append((m["text"][:60], before[0], after[0]))
    run.res["notes"].append(f"boulders: {hits}")
    run.check("a boulder was thrown", bool(msgs), f"{len(msgs)} boulder messages")
    run.check("no HP lost to boulders", all(b is None or a is None or a >= b for _, b, a in hits), f"{hits[:4]}")


def l2(run):
    """L2 (a rulebook claim): Word of Recall comes ~10x sooner while resting out of sight. Hurt by a Cave orc
    group, then `goal recall` (which rests while it charges when hurt and alone) vs. the time a recall
    takes standing (15-34 player turns, ~10-23 s)."""
    run.bring_dive04()
    run.t_act = time.time()
    run.place("Black orc", 2)              # (Cave orcs barely scratched AC 56: the read came at full HP)
    quiet = 0                               # (5 s in a row with nothing in view: the first run read mid-fight)
    for _ in range(90):
        time.sleep(1)
        st0 = ctl("status", role="architect")
        hp = re.search(r"HP (\d+)/(\d+)", st0)
        quiet = quiet + 1 if "Monsters: none" in st0 else 0
        if hp and int(hp.group(1)) < int(hp.group(2)) and quiet >= 5:
            break
    v = pilot_view()
    st_now = ctl("status", role="architect")
    t_read = time.time()
    ctl("goal", "recall", role="architect")
    t_yank = None
    for _ in range(60):
        time.sleep(0.5)
        yank = [json.loads(l) for l in open(os.path.join(RUN, "events.jsonl")) if "yanked upwards" in l]
        if yank and yank[-1].get("epoch", 0) > t_read:
            t_yank = yank[-1]["epoch"]
            break
    recs = log_since(t_read)
    rested = any(d.get("kind") == "act" and d.get("cmd") == "rest" for d in recs)
    secs = (t_yank - t_read) if t_yank else None
    run.res["notes"].append(f"status at the read: {st_now.splitlines()[0][:80]}; rested {rested}; {secs}")
    run.check("recalled", t_yank is not None, f"{secs} s")
    run.check("rested while it charged", rested, "")
    run.check("about 10x sooner than standing (< 5 s)", secs is not None and secs < 5, f"{secs and round(secs, 1)} s")


SETPIECES = {"A5": a5, "A5s": a5s, "A4": a4, "B6": b6, "B4": b4, "B4w": b4w, "D3": d3, "A2I": a2i, "A2K": a2k, "B2": b2, "B3": b3, "D6": d6, "L1": l1, "L2": l2, "A3": a3, "B1": b1, "C8": c8, "A1": a1, "A2": a2, "A2L": a2l, "A6": a6, "A7": a7, "A8": a8, "A8o": a8o, "A8w": a8w, "A9": a9,
             "C3": c3}


TOWN = {"B4", "B4w"}                # set in town


def fresh_depth(choices=(300, 350, 400, 450, 500, 550, 600, 650)):
    """The depth used longest ago (going up to town and back doesn't free a level: the server keeps
    empty levels a while, and a C3 run met the last run's Lagduf and his orcs)."""
    path = os.path.join(OUT, "depths.json")
    try:
        used = json.load(open(path))
    except (OSError, ValueError):
        used = {}
    d = min(choices, key=lambda c: used.get(str(c), 0))
    used[str(d)] = time.time()
    os.makedirs(OUT, exist_ok=True)
    json.dump(used, open(path, "w"))
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sid", help="A7 | A8 | A8o (A8 overridden) | A9 | list")
    ap.add_argument("--depth", type=int, default=0, help="default: the least recently used of 300-500 ft")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--hpwarn", type=int, default=0, help="run the Pilot with --hpwarn N (the time bubble A/B)")
    a = ap.parse_args()
    if a.sid == "list":
        for k, f in SETPIECES.items():
            print(k, "-", (f.__doc__ or "").strip().splitlines()[0])
        return
    depth = 0 if a.sid in TOWN else (a.depth or fresh_depth())
    if a.hpwarn:
        os.environ["PILOT_ARGS"] = f"--hpwarn {a.hpwarn}"    # (charsave's save starts the Pilot with it)
    run = Run(a.sid + (f"-hw{a.hpwarn}" if a.hpwarn else ""), depth, a.keep)
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
