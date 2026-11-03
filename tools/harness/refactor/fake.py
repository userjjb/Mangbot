"""A deterministic world for running the real Pilot without a server (E1 step 4 checks): a fake clock (time.time,
sleep, localtime, strftime...), a fake MangClient serving status/inven/map/flags/floor, and helpers to build maps.

import fake (before pilot!), then fake.load(PILOT_DIR) -> the pilot module.
"""
import copy
import os
import random
import shutil
import sys
import time
import types

S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(S, "rundir_template")


class Clock:
    t = 1793653200.0              # 2026-11-02 ~ 20:00 local


def _time():
    Clock.t += 1e-4
    return Clock.t


def _sleep(s):
    Clock.t += max(0.0, s)


_real_localtime, _real_strftime = time.localtime, time.strftime


def _localtime(secs=None):
    return _real_localtime(Clock.t if secs is None else secs)


def _strftime(fmt, t=None):
    return _real_strftime(fmt, _localtime() if t is None else t)


time.time = _time
time.monotonic = _time
time.perf_counter = _time
time.sleep = _sleep
time.localtime = _localtime
time.strftime = _strftime
os.environ["MANGBAND_FREEZE_FILE"] = os.path.join(S, "no-such-freeze-file")


def advance(s):
    Clock.t += s


P = None


def load(pilot_dir):
    global P
    random.seed(12345)
    sys.path.insert(0, pilot_dir)
    os.chdir(pilot_dir)
    import pilot
    P = pilot
    return pilot


H, WID = 66, 198


def room_map(pos, depth, stairs=(), extra=None, room=(5, 5, 40, 80)):
    """rows: a lit room of '.' walled by '#' (y0, x0, y1, x1), '@' at pos, stairs {(y, x): ch}, extra {(y, x): ch}."""
    g = [[" "] * WID for _ in range(H)]
    y0, x0, y1, x1 = room
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            g[y][x] = "#" if y in (y0, y1) or x in (x0, x1) else "."
    for q, ch in dict(stairs).items():
        g[q[0]][q[1]] = ch
    for q, ch in (extra or {}).items():
        g[q[0]][q[1]] = ch
    g[pos[0]][pos[1]] = "@"
    return ["".join(r) for r in g]


class FakeClient:
    """What World and Pilot call on a MangClient: send, status, inven, query (map/flags/floor), collect."""

    def __init__(self, pos=(20, 40), depth=0, hp=(358, 358), gold=300, hunger=3, inven=(), flags=None,
                 monsters=(), stairs=(), extra=None, ind=None, floor=None, room=(5, 5, 40, 80)):
        self.log = None
        self.sent = []
        self.door_glyph = "0"
        self.pos = pos
        self.depth = depth
        self.monsters = list(monsters)      # [(y, x, (ch, attr))]
        self.stairs, self.extra, self.room = dict(stairs), dict(extra or {}), room
        self.ind = {"hp": list(hp), "gold": [gold], "hunger": [hunger], "armor": [56, 0], "depth": [depth],
                    "level": [30, 30], "exp": [200000, 200000], "speed": [0], "state": [0, 0, 0],
                    "stat0": [58, 68], "stat1": [10], "stat2": [9, 10], "stat3": [28], "stat4": [18], "stat5": [3, 5],
                    "sp": [0, 0], "class_": [0]}
        self.ind.update(ind or {})
        self.items = [dict(it) for it in inven]
        self.flags = flags if flags is not None else {"free_act": "a", "see_invis": "a", "res_blind": "", "res_conf": "",
                                                       "res_pois": "", "hold_life": "", "feather": "",
                                                       "slow_digest": "d", "res_fire": "e", "res_cold": "e"}
        self.floor = floor

    def send(self, cmd):
        self.sent.append(cmd)

    def collect(self, secs):
        advance(secs)
        return []

    def status(self):
        return {"ev": "status", "ind": copy.deepcopy(self.ind), "ghost": False, "y": self.pos[0], "x": self.pos[1]}

    def inven(self):
        return copy.deepcopy(self.items)

    def query(self, cmd, reply, timeout=10):
        self.sent.append(f"?{cmd}")
        if cmd == "map":
            extra = dict(self.extra)
            attrs = [["0"] * WID for _ in range(H)]
            for y, x, (ch, a) in self.monsters:
                extra[(y, x)] = ch
                attrs[y][x] = chr(48 + a)
            rows = room_map(self.pos, self.depth, self.stairs, extra, self.room)
            return {"ev": "map", "rows": rows, "attrs": ["".join(r) for r in attrs]}
        if cmd == "flags":
            return {"ev": "flags", "flags": dict(self.flags)}
        if cmd == "floor":
            return {"ev": "floor", "name": self.floor}
        raise RuntimeError(f"{cmd}: timeout")


def item(slot, name, tval, number=1, weight=10, equip=False):
    return {"item": slot, "name": name, "tval": tval, "weight": weight, "number": number, "equip": equip}


def fresh_rundir(path, template=True):
    if os.path.exists(path):
        shutil.rmtree(path)
    parent = os.path.dirname(path)
    if os.path.exists(os.path.dirname(parent)):
        shutil.rmtree(os.path.dirname(parent))      # (runs/: town.json and flavours.json too)
    os.makedirs(path)
    if template:
        shutil.copytree(os.path.join(TEMPLATE, "dive04"), path, dirs_exist_ok=True)
        for f in ("town.json",):
            shutil.copy(os.path.join(TEMPLATE, f), os.path.join(parent, f))
        shutil.copy(os.path.join(TEMPLATE, "flavours.json"), os.path.join(os.path.dirname(parent), "flavours.json"))
    return path


def no_shadow(p):
    import queue
    p.shadow_est = types.SimpleNamespace(sim=None, error=None, results=queue.Queue())
