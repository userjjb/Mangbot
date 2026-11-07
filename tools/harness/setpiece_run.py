"""setpiece_run -- the set-pieces' framework (setpiece.py runs them; the scenarios are in setpiece_<group>.py).

Paths (ROOT, RUN: Dive04's Pilot run directory, OUT: runs/setpieces), RACES/race_idx, pilotctl (`ctl`), the
viewer's query (`pilot_view`), the Pilot's logs (`log_since`, `_tail`, `messages_since`, `hp_now`, `gold_now`,
`first_seen`), map helpers (`floor_near`, `clear_line`, `step_dir`, `find_pocket`, `find_floor_block`), the `Run`
class (setup: the snapshot and the DM's staging; bring_dive04, place, gandalf_to, watch, stats, check; teardown,
finish), the forged props (`give_item`, `con_swap`), the hot swap's scripts (FREEZE, HOTSWAP), WOR_KIND (from
object.txt) and the depth rotation (`fresh_depth`).
"""
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
sys.path.insert(0, os.path.join(HERE, ".."))
import servers                          # noqa: E402
# MANGBOT_SERVER=sp: the set-piece server -- its copy of Dive04 (runs/sp/pilot/dive04), its results (runs/sp/setpieces)
RUN = os.path.join(servers.RUNS, "pilot", "dive04")
OUT = os.path.join(servers.RUNS, "setpieces")
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
                    saves = os.path.join(OUT, "saves")
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


def first_seen(recs, name, t0):
    for d in recs:
        if d.get("kind") == "mons" and any(m[2] == name for m in d.get("monsters", [])):
            return d["t"] - t0
    return None


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


def find_floor_blocks(rows, h, w, apart=30):
    """The top-lefts of h x w blocks of floor on Gandalf's map, at least `apart` squares from each other (one per
    room, roughly), in map order; [] if none."""
    out = []
    for y in range(2, len(rows) - h - 2):
        for x in range(2, len(rows[0]) - w - 2):
            if all(rows[y + i][x:x + w] == "." * w for i in range(h)) and \
                    all(max(abs(y - b[0]), abs(x - b[1])) >= apart for b in out):
                out.append((y, x))
    return out


def find_floor_block(rows, h, w):
    """The top-left of an h x w block of floor on Gandalf's map (a room), or None."""
    for y in range(2, len(rows) - h - 2):
        for x in range(2, len(rows[0]) - w - 2):
            if all(rows[y + i][x:x + w] == "." * w for i in range(h)):
                return (y, x)
    return None


FREEZE = os.path.join(HERE, "..", "freeze.sh")


HOTSWAP = os.path.join(HERE, "..", "pilot", "hotswap.sh")


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
