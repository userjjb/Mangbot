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
import shutil
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
    env.pop("PILOT_TOKEN", None)
    if role:
        env["PILOT_ROLE"] = role
    if role == "architect":
        # (the Architect's token, refactor-candidates F3)
        env["PILOT_TOKEN"] = open(os.path.join(ROOT, "runs", "private", "architect.token")).read().strip()
    r = subprocess.run([sys.executable, os.path.join(HERE, "..", "pilot", "pilotctl.py"), "--nick", "dive04", *args],
                       capture_output=True, text=True, env=env, timeout=timeout)
    return (r.stdout + r.stderr).strip()


def pilot_view():
    """Dive04's position, depth and map (the viewer's query: no side effects)."""
    import socket
    s = socket.socket(socket.AF_UNIX)
    s.connect(os.path.join(RUN, "ctl.sock"))
    s.sendall((json.dumps({"cmd": "viewmap", "args": ["12", "30"]}) + "\n").encode())    # (read-only: no role)
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


def hp_now():
    """Dive04's [HP, max HP] from its last status line (state.jsonl)."""
    hp = None
    for d in _tail("state.jsonl", 2_000_000):
        if d.get("ev") == "status" and d.get("ind", {}).get("hp"):
            hp = d["ind"]["hp"][:2]
    return hp


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
                # (after a good restore, keep only the newest 5 timestamped snapshots -- 158, 55 MB, had piled up by
                # 10-29 -- in case a bad restore shows up later; named checkpoints such as dive04-pre-m43 never match)
                if out and out[0].startswith("restored "):
                    saves = os.path.join(ROOT, "runs", "setpieces", "saves")
                    stamped = sorted((re.search(r"(\d{8}-\d{6})$", d).group(1), d) for d in os.listdir(saves)
                                     if re.search(r"-\d{8}-\d{6}$", d))
                    for _, d in stamped[:-5]:
                        shutil.rmtree(os.path.join(saves, d), ignore_errors=True)

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


# --- forged props (the user allowed the forge, 2026-10-24: each use destroys Gandalf's pack slot a) -----
def give_item(run, kind, pval=None, want=None, timeout=40, ego=None, number=1):
    """Forge an item (identified), drop it beside Dive04 and have Dive04 fetch it. True once its name
    (`want`) shows in Dive04's pack."""
    v = pilot_view()
    me = tuple(v["pos"])
    spot = floor_near(v, me, 1)
    if not spot:
        raise RuntimeError(f"no floor square next to Dive04 at {me}")
    run.gandalf_to(spot)
    name = run.dm.forge(kind, ego=ego, pval=pval, number=number)
    if want is None and name:
        # (a flavour Dive04 may not know: "an Azurite Ring (+5) {for sale 500}" -> "Azurite Ring")
        want = re.sub(r"^(an?|the|\d+) ", "", re.sub(r" ?[({\[].*$", "", name))
    run.forged = want
    run.dm.drop_first(number)                        # (the whole stack: value=1 dropped one, the rest was lost)
    run.dm.walk(step_dir(me, spot) or 8)              # off it
    run.say(f"[{run.tag}] forged {name} at {spot}")
    ctl("goal", "fetch", f"{spot[0]},{spot[1]}", role="architect")
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(2)
        if want and want.lower() in ctl("status", "full", role="architect").split("Equipment:")[-1].lower():
            return True
    return False


def con_swap(run, pval=5):
    """The Advisor's way to leave Dive04 short of max HP, alone (batch4-reply): wear a Ring of Constitution
    +pval, rest to full, take it off (HP capped at the lower max), put it on again. Returns [HP, max]."""
    if not give_item(run, 134, pval=pval):
        raise RuntimeError(f"the Ring of Constitution ({run.forged}) wasn't picked up")
    ring = run.forged
    ctl("wear", ring, role="architect")
    time.sleep(2)
    ctl("goal", "rest", role="architect")
    t0 = time.time()
    while time.time() - t0 < 60:
        time.sleep(2)
        hp = hp_now()
        if hp and hp[0] >= hp[1]:
            break
    full = hp_now()
    ctl("takeoff", ring, role="architect")
    time.sleep(2)
    ctl("wear", ring, role="architect")
    time.sleep(2.5)
    hp = hp_now()
    run.res["con_swap"] = {"pval": pval, "full": full, "after": hp}
    run.say(f"[{run.tag}] CON swap: full {full} -> {hp}")
    return hp


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
    if " WoR 0" in ctl("status", role="architect") or " WoR 1 " in ctl("status", role="architect"):
        # (the trip plan wants 2: Gandalf comes up to town with 3, then goes back down)
        run.dm.ascend(run.depth // 50)
        give_item(run, WOR_KIND, number=3, want="Word of Recall")
        run.dm.descend(run.depth // 50)
        time.sleep(1)
    rep = ctl("plan", "trip", f"{run.depth}-{run.depth}", "via=recall", "until", "minutes>3", "force", role="architect")
    run.res["plan_reply"] = rep[:300]
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
    run.place(race, 1, after=lambda: (time.sleep(0.3),
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


def l2g(run):
    """L2 with Gandalf off the level (no shared time bubble)."""
    l2(run, gandalf_away=True)


def a2f(run, who="Dark elven lord"):
    """A2f: a dangerous caster at range (a Dark elven lord, rated 4: bolts, blinds, confuses) 8 squares off
    with a clear line, no stairs known: Word of Recall read within 2 s of the danger rule firing (A2I's Ibun
    at 12 squares got 7 s of free casts: the escape waited for him to come within 5)."""
    run.bring_dive04()
    run.t_act = time.time()
    run.place(who, 8, gmap=True)
    run.watch(40)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    danger = next((a[0] for a in st["attention"] if a[1] == "danger_seen"), None)
    wor = next((a[0] for a in st["acts"] if "word of recall" in str(a[2]).lower()), None)
    run.check("danger seen", danger is not None, f"at {danger}")
    run.check("Word of Recall within 2 s of it", danger is not None and wor is not None and wor - danger <= 2,
              f"danger at {danger}, recall read at {wor}")
    if st["hp_min"]:
        run.check("lowest HP >= 60%", st["hp_min"][0] >= 0.6 * st["hp_min"][1], f"lowest {st['hp_min']}")


def l3(run):
    """L3 (a rulebook claim, abilities.csv): with Boots of Free Action worn (forged: identified), an
    Illusionist (HOLD, BLIND, CONF; fast, blinks) 3 squares off. Expect "You are unaffected!" after a HOLD
    spell, and not after BLIND (Dive04 has no rBlind): the message pairing the Pilot's ability inference
    reads."""
    run.bring_dive04()
    if not give_item(run, 91, ego=58, want="Free Action") and "Free Action" not in ctl("status", "full", role="architect"):
        run.check("boots picked up", False, "")
        return
    ctl("wear", "Free Action", role="architect")
    time.sleep(2.5)
    eq = ctl("status", "full", role="architect").split("Equipment:")[-1].split("\n")[0]
    run.check("boots worn", "Free Action" in eq, eq[:160])
    run.t_act = time.time()
    run.place("Illusionist", 3, gmap=True)
    run.watch(45)
    msgs = [m for _, m in messages_since(run.t_act)]
    run.res["messages"] = msgs[:80]
    pairs = [(a, b) for a, b in zip(msgs, msgs[1:]) if "Illusionist" in a or a.startswith("It ")]
    hold = [(a, b) for a, b in pairs if re.search(r"stares deep|gazes deep|looks deep|paraly", a, re.I)]
    blind = [(a, b) for a, b in pairs if re.search(r"burning your eyes|blind", a, re.I)]
    run.res["hold_pairs"], run.res["blind_pairs"] = hold, blind
    run.check("a HOLD cast seen", bool(hold), f"{len(hold)}")
    run.check("unaffected after HOLD", bool(hold) and all("unaffected" in b for _, b in hold), f"{hold[:2]}")
    run.check("not unaffected after BLIND (no rBlind)", not any("unaffected" in b for _, b in blind),
              f"{blind[:2]}")
    recs = log_since(run.t_act)
    ab = [d.get("detail") for d in recs if d.get("kind") == "attention" and d.get("what") == "ability"]
    run.res["ability_news"] = ab[:3]


def l3b(run):
    """L3b (the session-7 todo: L3's rBlind half, unseen because the Illusionist died first): a Metal Cap of Seeing
    (resist blindness, See Invisible; forged: identified) worn, two Illusionists (HOLD, BLIND, CONF; fast, blink) 5
    squares off with a clear line. Expect "You are unaffected!" after each BLIND cast (the message pairing the Pilot's
    ability inference reads), and never blinded."""
    run.bring_dive04()
    if not give_item(run, 95, ego=30, pval=2, want="Seeing") and "Seeing" not in ctl("status", "full", role="architect"):
        run.check("cap picked up", False, "")
        return
    ctl("wear", "Seeing", role="architect")
    time.sleep(2.5)
    eq = ctl("status", "full", role="architect").split("Equipment:")[-1].split("\n")[0]
    run.check("cap worn", "Seeing" in eq, eq[:160])
    run.t_act = time.time()
    run.place("Illusionist", 5, gmap=True)
    run.place("Illusionist", 5, gmap=True)
    run.watch(60)
    msgs = [m for _, m in messages_since(run.t_act)]
    run.res["messages"] = msgs[:100]
    pairs = [(a, b) for a, b in zip(msgs, msgs[1:]) if "Illusionist" in a or a.startswith("It ")]
    blind = [(a, b) for a, b in pairs if re.search(r"burning your eyes|casts a spell, burning", a, re.I)]
    run.res["blind_pairs"] = blind
    run.check("a BLIND cast seen", bool(blind), f"{len(blind)}")
    run.check("unaffected after BLIND (rBlind)", bool(blind) and all("unaffected" in b for _, b in blind), f"{blind[:2]}")
    run.check("never blinded", not any(re.search(r"You are blind", m) for m in msgs), "")


def a7f(run):
    """A7f (the memo's first A7): fear casters. A Novice paladin group (SCARE, CAUSE_1; m22 lost 31% to seven)
    6 squares off. Passes when, once Dive04 is afraid ("too afraid to attack"), a Boldness or Heroism is quaffed
    (or the level left) within 5 s, and the lowest HP stays at 50% or more."""
    run.bring_dive04()
    run.t_act = time.time()
    run.place(118, 6, gmap=True)            # Novice paladin, the lvl 8 one (70 is a lvl 4 namesake); 6 off with a
    #                                         clear line: they cast on the way (at 3 they died before casting)
    run.watch(60)
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    msgs = messages_since(run.t_act)
    afraid = next((t for t, m in msgs if re.search(r"too afraid|You are terrified|You are scared", m)), None)
    cured = next((d["t"] for d in recs if d.get("kind") == "act" and afraid and d["t"] >= afraid - 0.5 and
                  re.search(r"Boldness|Heroism|Berserk|recall|stairs|phase", str(d.get("why")), re.I)), None)
    run.res["afraid_at"] = round(afraid - run.t_act, 1) if afraid else None
    run.check("fear answered within 5 s", afraid is None or (cured is not None and cured - afraid <= 5),
              f"afraid at {run.res['afraid_at']}, answered {round(cured - afraid, 1) if cured and afraid else None} s later")
    if st["hp_min"]:
        run.check("lowest HP >= 50%", st["hp_min"][0] >= 0.5 * st["hp_min"][1], f"lowest {st['hp_min']}")


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


def l2(run, gandalf_away=False):
    """L2 (a rulebook claim): Word of Recall comes ~10x sooner while resting out of sight. Dive04 fights a
    Sabre-tooth tiger (A3: 40-50 HP lost) and the moment it's dead gets `goal recall` (which rests while it
    charges when hurt and alone), vs. the time a recall takes standing (15-34 player turns, ~10-23 s; 17.9
    and 20.4 s measured). (The Advisor's CON-ring swap can't hurt here: MAngband scales HP with max HP,
    xtra1.c calc_hitpoints. Cave and Black orcs left HP full by the time they were gone.)"""
    run.bring_dive04()
    t0 = time.time()
    run.place("Sabre-tooth tiger", 1)
    dead = None
    for _ in range(60):
        time.sleep(0.5)
        dead = next((t for t, m in messages_since(t0) if "slain the Sabre-tooth" in m), None)
        if dead:
            break
    hp = hp_now()
    run.res["hp_after_fight"] = hp
    if not dead or not hp or hp[0] >= hp[1]:
        run.check("hurt and alone after the fight", False, f"tiger slain {dead is not None}, HP {hp}")
        return
    if gandalf_away:
        run.dm.ascend(1)                     # (off the level: no shared time bubble)
    # a fuel reading every second (a redraw is free): the recall counts down on the same tick as the fuel
    import threading
    stop = threading.Event()

    def sample():
        while not stop.is_set():
            ctl("raw", "redraw", role="architect")
            stop.wait(1.0)
    threading.Thread(target=sample, daemon=True).start()
    st_now = ctl("status", role="architect")
    t_read = time.time()
    run.t_act = t_read
    ctl("goal", "recall", role="architect")
    t_yank = None
    for _ in range(60):
        time.sleep(0.5)
        yank = [t for t, m in messages_since(t_read) if "yanked upwards" in m]
        if yank:
            t_yank = yank[0]
            break
    recs = log_since(t_read)
    rested = any(d.get("kind") == "act" and d.get("cmd") == "rest" for d in recs)
    secs = (t_yank - t_read) if t_yank else None
    run.res["notes"].append(f"status at the read: {st_now.splitlines()[0][:80]}; rested {rested}; {secs}")
    stop.set()
    factors = [(round(d["t"] - t_read, 1), d.get("factor"), d.get("measured")) for d in recs if d.get("kind") == "time_factor"]
    run.res["time_factors"] = factors[:20]
    fuel = []
    for e in _tail("state.jsonl", 3_000_000):
        if e.get("ev") == "inven" and t_read - 2 < e["epoch"] < t_read + 40:
            for it in e["items"]:
                m = re.search(r"with (\d+) turns of light", it["name"])
                if m and it.get("equip"):
                    fuel.append((round(e["epoch"] - t_read, 1), int(m.group(1))))
        if e.get("ev") == "status" and t_read - 2 < e["epoch"] < t_read + 40:
            fuel.append((round(e["epoch"] - t_read, 1), "rest" if e["ind"].get("state", [0, 0, 0])[2] else "-",
                         e["ind"].get("hp", [0])[0]))
    run.res["fuel"] = fuel
    run.say(f"[{run.tag}] fuel/rest/HP after the read: {fuel}")
    run.check("recalled", t_yank is not None, f"{secs} s")
    run.check("rested while it charged", rested, "")
    run.check("about 10x sooner than standing (< 5 s)", secs is not None and secs < 5, f"{secs and round(secs, 1)} s")


def m1(run, race="Brown mold"):
    """M1: a stationary monster beside the only known '>' (m25: a Brown mold, which confuses and so is never
    fought, beside the '>' at 300 ft; the step-away walked 6 squares back, the dive pressed '>' there, and it
    looped 2 minutes). A '>' painted 6 squares from Dive04, a Brown mold summoned beside it, `goal dive` one
    level down: Dive04 goes down those stairs within 45 s, pressing '>' nowhere else."""
    rows = run.dm.c.map()
    tl = find_floor_block(rows, 5, 9)            # (a room on Gandalf's map: he sees the whole level)
    if not tl:
        run.check("a site", False, "no 5 x 9 block of floor")
        return
    start, stairs, mold = (tl[0] + 2, tl[1] + 1), (tl[0] + 2, tl[1] + 7), (tl[0] + 1, tl[1] + 7)
    run.gandalf_to(stairs)
    run.dm.paint(7, [8])                         # the '>' (he steps north off it, onto the mold's square)
    name = run.dm.summon(race_idx(race), step=8, after=None)
    run.gandalf_to(start)
    v = run.bring_dive04()
    run.dm.walk(2, 3)                            # out of the way
    me = tuple(v["pos"])
    run.res["scene"] = {"dive04": me, "stairs": stairs, "mold": mold, "summoned": name}
    run.say(f"[{run.tag}] Dive04 at {me}, '>' at {stairs}, {name} at {mold}")
    time.sleep(2.0)
    run.t_act = time.time()
    run.res["order_reply"] = ctl("goal", "dive", str(run.depth + 50), role="architect")
    run.watch(45, until=lambda recs: any(d.get("depth") is not None and d["depth"] * 50 > run.depth for d in recs))
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    presses = [(round(d["t"] - run.t_act, 1), tuple(d["pos"])) for d in recs
               if d.get("kind") == "act" and d.get("cmd") == "custom >" and d.get("pos")]
    down = next((round(d["t"] - run.t_act, 1) for d in recs if d.get("depth") is not None and d["depth"] * 50 > run.depth),
                None)
    stray = [p for p in presses if p[1] not in (stairs, me)]   # (the first press on arrival probes the tile underfoot)
    run.check("down the painted '>' within 45 s", down is not None, f"at {down} s; presses {presses[:6]}")
    run.check("no '>' pressed off the stairs", not stray, f"{stray[:4]}")


def m2(run):
    """M2: a valuable beyond loot_radius (the user's m29 question: an unknown wand left 12 squares off). A forged
    Wand of Stinking Cloud dropped on floor Dive04 sees 13-20 squares away, a '>' painted 3 squares the other
    way, `goal dive` one level down: Dive04 fetches the wand first, then goes down, within 60 s."""
    rows = run.dm.c.map()
    tl = find_floor_block(rows, 3, 24) or find_floor_block(rows, 3, 18)
    if not tl:
        run.check("a site", False, "no 3 x 18 block of floor")
        return
    run.gandalf_to((tl[0] + 1, tl[1] + 2))
    v = run.bring_dive04()
    me = tuple(v["pos"])
    y0, x0 = v["y0"], v["x0"]
    seen = [(y0 + i, x0 + j) for i, row in enumerate(v["rows"]) for j, ch in enumerate(row) if ch == "."]
    far = [q for q in seen if 13 <= max(abs(q[0] - me[0]), abs(q[1] - me[1])) <= 20 and q[1] > me[1]]
    if not far:
        run.check("a site", False, f"no floor Dive04 sees 13-20 squares east of {me} (a dark room?)")
        return
    spot = min(far, key=lambda q: (abs(q[0] - me[0]), -q[1]))
    stairs = floor_near(v, me, 3, taken={spot})
    stairs = next((q for q in seen if q[1] <= me[1] - 2 and max(abs(q[0] - me[0]), abs(q[1] - me[1])) == 3), stairs)
    run.gandalf_to(stairs)
    run.dm.paint(7, [8])                         # the '>' (he steps north off it)
    run.gandalf_to(spot)
    name = run.dm.forge(290)                     # Wand of Stinking Cloud (identified)
    run.dm.drop_first(1)
    for _ in range(8):                           # out of the room, into the rock (a ghost)
        run.dm.walk(8)
    run.res["scene"] = {"dive04": me, "wand": spot, "stairs": stairs, "forged": name}
    run.say(f"[{run.tag}] Dive04 at {me}, {name} at {spot} ({max(abs(spot[0] - me[0]), abs(spot[1] - me[1]))} "
            f"away), '>' at {stairs}")
    time.sleep(2.0)
    run.t_act = time.time()
    run.res["order_reply"] = ctl("goal", "dive", str(run.depth + 50), role="architect")
    run.watch(60, until=lambda recs: any(d.get("depth") is not None and d["depth"] * 50 > run.depth for d in recs))
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    picked = next((round(d["t"] - run.t_act, 1) for d in recs if d.get("kind") == "act"
                   and "Stinking Cloud" in str(d.get("why")) and "pick up" in str(d.get("why"))), None)
    down = next((round(d["t"] - run.t_act, 1) for d in recs if d.get("depth") is not None and d["depth"] * 50 > run.depth),
                None)
    left = [d.get("items") for d in recs if d.get("kind") == "left_behind"]
    run.check("the wand fetched", picked is not None, f"picked up at {picked} s; left behind {left[:2]}")
    run.check("then down the '>' within 60 s", down is not None and (picked is None or down > picked), f"at {down} s")


def m3(run):
    """M3: an unseen stat drainer (m29, m30: a Moaning spirit -- invisible, passes walls, +10, TOUCH:LOSE_DEX).
    A '>' painted 6 squares from Dive04, a Moaning spirit summoned 2 squares off, no orders: once DEX is drained
    Dive04 leaves the level within 30 s (Dive04 is restored afterwards)."""
    rows = run.dm.c.map()
    tl = find_floor_block(rows, 5, 9)
    if not tl:
        run.check("a site", False, "no 5 x 9 block of floor")
        return
    start, stairs = (tl[0] + 2, tl[1] + 1), (tl[0] + 2, tl[1] + 7)
    run.gandalf_to(stairs)
    run.dm.paint(7, [8])                         # the '>'
    run.gandalf_to(start)
    v = run.bring_dive04()
    run.dm.walk(2, 3)
    time.sleep(1.5)
    run.t_act = time.time()
    run.place("Moaning spirit", 2)
    run.watch(90, until=lambda recs: any(d.get("depth") is not None and d["depth"] * 50 != run.depth for d in recs))
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    drained = next((round(d["t"] - run.t_act, 1) for d in recs if d.get("what") == "stat_drained"), None)
    left = next((round(d["t"] - run.t_act, 1) for d in recs if d.get("depth") is not None and d["depth"] * 50 != run.depth),
                None)
    run.res["scene"] = {"dive04": tuple(v["pos"]), "stairs": stairs}
    if drained is None:
        run.check("drained (the scene happened)", False, f"no drain in 90 s; left at {left}")
        return
    run.check("left within 30 s of the drain", left is not None and left - drained <= 30,
              f"drained at {drained} s, left at {left} s")


def m5(run, n=30):
    """M5: a confusing breeder swarm (m55 at 800 ft: Hummerhorns kept Dive04 confused from 17:04 to 17:19; the dive
    waited for the confusion to wear off, two staff uses failed, the recall couldn't be read). A '>' painted 8 squares
    from Dive04, n Hummerhorns summoned 1-2 squares round it, `goal dive` one level down. Pass: confused (the scene
    happened); the Pilot cures a long confusion itself (CSW/CCW within 20 s of it starting, at most 4); down those
    stairs within 120 s; lowest HP >= 60%. (20 of them: 8 died to one blow each before a single bite.)"""
    rows = run.dm.c.map()
    tl = find_floor_block(rows, 5, 11)
    if not tl:
        run.check("a site", False, "no 5 x 11 block of floor")
        return
    start, stairs = (tl[0] + 2, tl[1] + 1), (tl[0] + 2, tl[1] + 9)
    run.gandalf_to(stairs)
    run.dm.paint(7, [8])                         # the '>'
    run.gandalf_to(start)
    v = run.bring_dive04()
    # (Hummerhorn bites rarely land at AC 76 -- power 10 + 3 x 16 vs 3/4 AC: ~6% -- so three runs were never
    # confused, and a forged Potion of Confusion is junk the Pilot destroys underfoot. Stage m55's state by AC instead:
    # the body armour, shield and Protection rings off (AC ~20: ~70% a bite); charsave restores the gear)
    ctl("order", "autowear=off", role="architect")      # (or the Pilot wears it all again at once)
    for slot in ("E", "G", "B", "C"):
        ctl("takeoff", slot, role="architect")
        time.sleep(1.2)
    run.res["ac"] = re.findall(r"AC (\d+)", ctl("gear", role="architect"))[:1]
    run.dm.walk(2, 3)
    time.sleep(1.5)
    for k in range(n):
        try:
            run.place("Hummerhorn", 1 + k % 3)
        except RuntimeError as e:
            run.res["notes"].append(str(e))
    # (m55's state: confused before the leave -- run 1 went down in 5.7 s, unbitten; with 8, all died to one blow
    # each before a bite. 20, and wait for the first confusion up to 45 s; auto-retaliate fights the swarm meanwhile)
    run.t_act = time.time()
    t_end = time.time() + 90
    while time.time() < t_end and not any(m.startswith("You are confused") for _, m in messages_since(run.t_act)):
        time.sleep(1.0)
    run.res["order_reply"] = ctl("goal", "dive", str(run.depth + 50), role="architect")
    run.watch(120, until=lambda recs: any(d.get("depth") is not None and d["depth"] * 50 > run.depth for d in recs))
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    msgs = messages_since(run.t_act)
    conf = next((round(t - run.t_act, 1) for t, m in msgs if m.startswith("You are confused")), None)
    cures = [(round(d["t"] - run.t_act, 1), str(d.get("why"))[:50]) for d in recs
             if d.get("kind") == "act" and str(d.get("why")).startswith("confused")]
    down = next((round(d["t"] - run.t_act, 1) for d in recs if d.get("depth") is not None and d["depth"] * 50 > run.depth),
                None)
    run.res["scene"] = {"dive04": tuple(v["pos"]), "stairs": stairs, "hummerhorns": n}
    if conf is None:
        run.check("confused (the scene happened)", False, f"never confused; down at {down} s")
        return
    run.check("a long confusion cured by the Pilot within 20 s", bool(cures) and cures[0][0] - conf <= 20,
              f"confused at {conf} s; cures {cures[:4]}")
    run.check("at most 4 cures", len(cures) <= 4, f"{len(cures)}")
    run.check("down the painted '>' within 120 s", down is not None, f"at {down} s")
    if st["hp_min"]:
        run.check("lowest HP >= 60%", st["hp_min"][0] >= 0.6 * st["hp_min"][1], f"lowest {st['hp_min']}")


FREEZE = os.path.join(HERE, "..", "freeze.sh")
HOTSWAP = os.path.join(HERE, "..", "pilot", "hotswap.sh")


def h1(run, recall=False):
    """H1: the hot swap (tools/pilot/hotswap.sh) mid-trip, in the dungeon: a trip plan working the level, a Cave orc
    3 squares off; freeze, swap the Pilot, and before the thaw the new Pilot must see Dive04 where it was, with the
    same HP and the orc where it was (resumed in memory, not reloaded); after the thaw the plan carries on. H1r: the
    same with a Word of Recall read just before: it still lands."""
    run.bring_dive04()
    run.place("Cave orc", 3)                     # (in view: a dark room shows only the lantern's 2 squares + infravision)
    run.dm.walk(2, 8)                              # Gandalf out of the way
    time.sleep(2)
    run.res["plan_reply"] = ctl("plan", "trip", f"{run.depth}-{run.depth}", "until", "minutes>10", "then", "recall",
                                role="architect")
    time.sleep(4)
    if recall:
        run.res["recall_reply"] = ctl("read", "Recall", role="architect")
        time.sleep(1.5)
    subprocess.run([FREEZE, "on"], capture_output=True)
    time.sleep(1.5)
    def live_hp():                               # (state.jsonl's thinned status can lag a regeneration tick)
        m = re.search(r"HP (\d+)/(\d+)", ctl("status", role="architect"))
        return [int(m.group(1)), int(m.group(2))] if m else None
    before, hp0, d0 = pilot_view(), live_hp(), run._depth()
    run.t_act = time.time()
    out = subprocess.run([HOTSWAP, "Dive04"], capture_output=True, text=True, timeout=240)
    swap_s = round(time.time() - run.t_act, 1)
    after, hp1, d1 = pilot_view(), live_hp(), run._depth()
    still = subprocess.run([FREEZE, "status"], capture_output=True, text=True).stdout.strip()
    run.res["swap"] = {"seconds": swap_s, "out": out.stdout.strip().splitlines()[-4:], "frozen_after": still}
    t_thaw = time.time()
    subprocess.run([FREEZE, "off"], capture_output=True)
    if recall:
        run.watch(60, until=lambda recs: any(d.get("depth") == 0 for d in recs))
    else:
        time.sleep(30)
    recs = log_since(run.t_act)
    run.res["stats"] = run.stats(recs)
    mons0 = sorted(tuple(m[:2]) for m in before.get("mons", []))
    mons1 = sorted(tuple(m[:2]) for m in after.get("mons", []))
    run.res["scene"] = {"pos": [before.get("pos"), after.get("pos")], "hp": [hp0, hp1], "depth": [d0, d1],
                        "mons": [mons0, mons1]}
    run.check("swapped while frozen", "FROZEN" in still, f"{swap_s} s; {run.res['swap']['out']}")
    run.check("resumed in place", after.get("pos") == before.get("pos") and d1 == d0 and hp1 == hp0,
              f"pos {before.get('pos')} -> {after.get('pos')}, depth {d0} -> {d1}, HP {hp0} -> {hp1}")
    if mons0 or mons1:
        run.check("nothing moved while frozen", mons0 == mons1, f"monsters {mons0} -> {mons1}")
    else:
        run.res["notes"].append("no monster in view at the freeze (killed first): the 'nothing moved' check n/a")
    resumed = any(d.get("kind") == "plan_resumed" for d in recs)
    acted = [round(d["t"] - t_thaw, 1) for d in recs if d["t"] > t_thaw and d.get("kind") in ("act", "move")]
    # (with a recall pending the Pilot rightly waits for it rather than acting: there the landing is the proof)
    run.check("the plan resumed" + ("" if recall else " and the Pilot acts after the thaw"),
              resumed and (recall or bool(acted)), f"plan_resumed {resumed}; first act {acted[:1]} s after the thaw")
    if recall:
        home = next((round(d["t"] - t_thaw, 1) for d in recs if d.get("depth") == 0 and d["t"] > t_thaw), None)
        run.check("the recall still landed", home is not None, f"in town {home} s after the thaw")


def h1r(run):
    """H1r: H1 with a Word of Recall read just before the swap."""
    h1(run, recall=True)


def m4(run):
    """M4: a crowd in the open (m30 06:43: hounds, a Druid, an Umber hulk...; the Advisor's estimator memo rules).
    An Umber hulk, Fire and Energy hounds, two Uruks and a Dark elven priest summoned 1-2 squares round Dive04 in a
    room (Dive04 beat four Uruks and a priest without an emergency): no HP cure with 2+ adjacent; an
    escape read with 4+ about is a teleport, not Phase Door; lowest HP >= 40%."""
    rows = run.dm.c.map()
    tl = find_floor_block(rows, 7, 11)
    if not tl:
        run.check("a site", False, "no 7 x 11 block of floor")
        return
    run.gandalf_to((tl[0] + 3, tl[1] + 5))
    run.bring_dive04()
    run.dm.walk(8, 2)
    time.sleep(1.5)
    run.t_act = time.time()
    for race, d in (("Umber hulk", 1), ("Fire hound", 1), ("Fire hound", 2), ("Energy hound", 2), ("Uruk", 1),
                    ("Uruk", 2), ("Dark elven priest", 2)):
        try:
            run.place(race, d)
        except RuntimeError as e:
            run.res["notes"].append(str(e))
    run.dm.walk(8, 6)
    run.watch(60, until=lambda recs: any(d.get("depth") is not None and d["depth"] * 50 != run.depth for d in recs))
    recs = log_since(run.t_act)
    st = run.stats(recs)
    run.res["stats"] = st
    adj_n, near_n, bad_cures, phases_in_crowd, teles = 0, 0, [], [], []
    for d in recs:
        if d.get("kind") == "mons" and d.get("pos"):
            p = d["pos"]
            ds = [max(abs(m[0] - p[0]), abs(m[1] - p[1])) for m in d.get("monsters", [])]
            adj_n, near_n = sum(1 for x in ds if x == 1), sum(1 for x in ds if x <= 5)
        if d.get("kind") == "act":
            why = str(d.get("why"))
            t = round(d["t"] - run.t_act, 1)
            if "quaff" in why and "Cure" in why and "blind" not in why and "confused" not in why and adj_n >= 2:
                bad_cures.append((t, adj_n, why[:60]))
            if "phase door" in why.lower() and near_n >= 4 and "agent" not in why:
                phases_in_crowd.append((t, near_n))
            if "teleport" in why.lower():
                teles.append(t)
    run.check("no HP cure with 2+ adjacent", not bad_cures, f"{bad_cures[:3]}")
    run.check("teleport, not Phase Door, with 4+ about", not phases_in_crowd, f"phases with 4+ near: "
              f"{phases_in_crowd[:3]}; teleports at {teles[:3]}")
    if st["hp_min"]:
        run.check("lowest HP >= 40%", st["hp_min"][0] >= 0.4 * st["hp_min"][1], f"lowest {st['hp_min']}")


SETPIECES = {"M5": m5, "M4": m4, "H1": h1, "H1r": h1r, "M1": m1, "M2": m2, "M3": m3, "L3": l3, "L3b": l3b, "A2f": a2f, "L2g": l2g, "A7f": a7f, "A5": a5, "A5s": a5s, "A4": a4, "B6": b6, "B4": b4, "B4w": b4w, "D3": d3, "A2I": a2i, "A2K": a2k, "B2": b2, "B3": b3, "D6": d6, "L1": l1, "L2": l2, "A3": a3, "B1": b1, "C8": c8, "A1": a1, "A2": a2, "A2L": a2l, "A6": a6, "A7": a7, "A8": a8, "A8o": a8o, "A8w": a8w, "A9": a9,
             "C3": c3}


TOWN = {"B4", "B4w"}
WOR_KIND = None              # set below from object.txt                # set in town


def _kind(name):
    import re as _re
    for line in open(os.path.join(HERE, "..", "..", "lib", "edit", "object.txt")):
        m = _re.match(r"N:(\d+):(.+)$", line.strip())
        if m and m.group(2) == name:
            return int(m.group(1))
    return None


WOR_KIND = _kind("Word of Recall")


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
    ap.add_argument("--hpwarn", type=int, default=None,
                    help="run the Pilot with --hpwarn N (default: the Pilot's, 5; 0 = no time bubble, for an A/B)")
    a = ap.parse_args()
    if a.sid == "list":
        for k, f in SETPIECES.items():
            print(k, "-", (f.__doc__ or "").strip().splitlines()[0])
        return
    depth = 0 if a.sid in TOWN else (a.depth or fresh_depth())
    if a.hpwarn is not None:
        os.environ["PILOT_ARGS"] = f"--hpwarn {a.hpwarn}"    # (charsave's save starts the Pilot with it)
    run = Run(a.sid + (f"-hw{a.hpwarn}" if a.hpwarn is not None else ""), depth, a.keep)
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
