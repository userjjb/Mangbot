"""shadow -- the Advisor's danger-time option estimator in shadow mode (the user, 2026-10-25).

At each emergency decision the Pilot takes, a snapshot of the fight goes to a background thread that runs the
Advisor's `options_sim.choose` (Advisor/data/estimator, memos 2026-10-25-estimator and -replay); the Pilot never waits
for it and never acts on it. The answer comes back on a queue and is logged as an `estimator` record beside the rules'
action: what the rules did, what the estimator would choose and why, whether they agree, how long it took, and whether
it would have arrived in time -- within one player turn (wall seconds at the current time factor), and before the
Pilot's next action. One estimate at a time; a decision while one is running is logged as skipped.
"""
import queue
import re
import sys
import threading
import time

ADVISOR = "/projectnb/jbrcs/mangband/Advisor/data/estimator"
N = 40              # rollouts per option (the Advisor: median 0.39 s, max 1.3 s on the 21 replayed episodes)
MAX_ADJ = 3         # calibrated (calib_adj.py): ~2 attackers at once in real fights, max 3
TURN_S = 0.625      # wall seconds per player turn at normal speed and time factor 1 (world.TICK_S)

# the rules' action, from the emergency notice, as the estimator's option names
RULES_AS = ((r"Teleportation|teleport", "teleport"), (r"Staff of Teleport", "staff"), (r"Word of Recall", "recall+phase"),
            (r"Phase Door", "phase"), (r"Speed", "speed"), (r"Berserk", "berserk"), (r"Cure Critical", "ccw"),
            (r"Cure (Serious|Light)", "cure"),     # (not an estimator option: CSW/CLW; m36's record said None)
            (r"stairs", "stairs"), (r"attacking|fighting on", "fight"))


def rules_option(detail):
    for rx, name in RULES_AS:
        if re.search(rx, detail or "", re.I):
            return name
    return None


class Shadow:
    def __init__(self):
        self.sim = None
        self.error = None
        try:
            sys.path.insert(0, ADVISOR)
            import options_sim                     # noqa: E402
            self.sim = options_sim
        except Exception as e:                     # (no estimator: shadow mode off, said once in the log)
            self.error = repr(e)
        self.busy = threading.Event()
        self.results = queue.Queue()

    def submit(self, snap):
        """Start an estimate for this decision, unless one is running. Returns 'started', 'skipped' or 'off'."""
        if not self.sim:
            return "off"
        if self.busy.is_set():
            return "skipped"
        self.busy.set()
        threading.Thread(target=self._run, args=(snap,), daemon=True).start()
        return "started"

    def _run(self, snap):
        t0 = time.time()
        try:
            team = [(n, d) for n, d in snap["team"] if n in self.sim.RACES]
            choice, why, table = self.sim.choose(snap["p"], team, n=N)
            out = {"choice": choice, "why": why, "table": table[:6], "team": team}
        except Exception as e:
            out = {"error": repr(e)}
        out["compute_s"] = round(time.time() - t0, 3)
        out["snap"] = {k: v for k, v in snap.items() if k != "p"}
        out["p"] = {k: v for k, v in snap["p"].items() if k != "inv"}
        out["inv"] = snap["p"].get("inv")
        out["done_wall"] = time.time()
        self.results.put(out)
        self.busy.clear()


def weapon_profile(name, blows):
    """dice, to-hit, to-dam from 'a Scimitar of Westernesse (2d5) (+9,+8) (+1)'."""
    d = re.search(r"\((\d+d\d+)\)", name or "")
    m = re.search(r"\(([+-]\d+),([+-]\d+)\)", name or "")
    return {"dice": d.group(1) if d else "1d4", "tohit": int(m.group(1)) if m else 0,
            "todam": int(m.group(2)) if m else 0, "blows": max(1, blows or 1)}
