"""logs -- the observers' shared readers of the Pilot's run logs and the mission list, and their lists of the
Navigator's query commands (refactor-candidates D7).

    runs/missions.json                      load_missions(), find_mission(label), epoch(), mission_window(m)
    runs/pilot/<nick>/decisions.jsonl       decisions(nick, t0, t1, keep)   (records' "t")
    runs/pilot/<nick>/events.jsonl          events(nick, t0, t1, keep)      (records' "epoch")

Readers are generators of parsed records whose time is a number in [t0, t1]; lines that don't parse are skipped.
KEEP(line) is an optional cheap test on the raw text line before it is parsed: the logs are big (events.jsonl
~300 MB), so callers that want a few kinds say so here. Used by scorecard.py, notes.py and damage_mix.py; the
query lists by scorecard.py and watch.py. Reads only; no side effects at import.
"""
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "runs"))
INF = float("inf")


# --- the Navigator's query commands ---------------------------------------------------------------------------
# Commands that only look or talk, as opposed to orders that change what the Pilot does. Both lists also hold
# names Navigators really typed that aren't commands (help, news, inventory...): they classify real attempts.
# The two uses need different sets, so there are two:
QUERY_CORE = {"status", "journal", "gate", "monster", "inventory", "complain", "drainers", "say", "note", "options",
              "flags", "view", "orders", "events", "attention", "news", "map", "pack", "equip", "mission"}
# The scorecard's (group E: report -> action latency, order report age): the Advisor's definition
# (memos/2026-10-23-scorecard.md, Advisor/data/scorecard/scorecard.py, checked by `scorecard.py --check`). `plan`
# counts as a query here even with arguments. Changing this set changes the cards.
QUERY_CMDS = QUERY_CORE | {"floor", "help", "plan", "dump", "quote"}
# The viewer's (watch.py hides these from its feed; `plan` with no arguments is hidden there too, `plan ARGS` shown
# as an order). Also hides the read-only checks the scorecard counts as actions (wait, prep, why, gear, gearcmp,
# debt, ...) and shows `help`.
NAV_QUERIES = QUERY_CORE | {"wait", "prep", "why", "gear", "gearcmp", "debt", "rule", "viewmap", "navview",
                            "goalstate", "commands"}


# --- missions ----------------------------------------------------------------------------------------------------
def epoch(s):
    """A missions.json time ("YYYY-MM-DD HH:MM", local) -> epoch seconds."""
    return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M"))


def load_missions():
    return json.load(open(os.path.join(RUNS, "missions.json")))


def find_mission(label):
    """The last runs/missions.json row with this label, or None."""
    ms = [m for m in load_missions() if m.get("label") == label]
    return ms[-1] if ms else None


def mission_window(m):
    """(t0, t1) of a missions.json row: its start to its end (minute resolution), or to now if it is running."""
    return epoch(m["start"]), epoch(m["end"]) if m.get("end") else time.time()


# --- run logs ----------------------------------------------------------------------------------------------------
def run_dir(nick):
    return os.path.join(RUNS, "pilot", nick)


def read_jsonl(path, t0=-INF, t1=INF, tkey="t", keep=None):
    """Parsed records of a JSON-lines log whose TKEY is a number in [t0, t1]; KEEP(line) pre-filters lines.
    (Text mode: scanning events.jsonl for substrings was ~4x faster than in binary mode; the logs are ASCII.)"""
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if keep is not None and not keep(line):
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t = d.get(tkey)
            if isinstance(t, (int, float)) and t0 <= t <= t1:
                yield d


def decisions(nick, t0=-INF, t1=INF, keep=None):
    """runs/pilot/NICK/decisions.jsonl records with t0 <= t <= t1."""
    return read_jsonl(os.path.join(run_dir(nick), "decisions.jsonl"), t0, t1, "t", keep)


def events(nick, t0=-INF, t1=INF, keep=None):
    """runs/pilot/NICK/events.jsonl records with t0 <= epoch <= t1 (events also carry "t", the client's clock)."""
    return read_jsonl(os.path.join(run_dir(nick), "events.jsonl"), t0, t1, "epoch", keep)
