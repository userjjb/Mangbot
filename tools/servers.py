"""servers -- the local MAngband servers the tools talk to, chosen by $MANGBOT_SERVER (session 13, 2026-11-07).

    local (default)  testserver/,  port 28346, runs root runs/        -- "the local server" (called "the test server"
                                                                         until 11-07): Dive04's own world, missions,
                                                                         the real character; plays like the live server
    debug            debugserver/, port 28350, runs root runs/debug/  -- "the debug server": copies of the local world
                                                                         (tools/server.sh clone), so a set-piece never
                                                                         touches the real character, its gold or its
                                                                         house; the server-side test features run here

Ports: a server also listens on its port + 1 (the console, net-server.c:448), so profiles' ports differ by 2 or more
(the debug server sat on 28347 at first: the local server's console took it and the debug server quietly moved on).

A runs root holds `pilot/<nick>/` (the Pilot's state), `setpieces/`, `missions.json`, `flavours.json` and `private/`
(runs/debug/private is a link to runs/private: the copies keep their passwords). Everything that reads a port, a
Pilot's state, the freeze file or a savefile goes through here (Python) or tools/servers.sh (shell: the same table).
Set MANGBOT_SERVER=debug in the environment of every command of a debug session (pilotctl, restart.sh, setpiece.py...).
"""
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

PROFILES = {     # (keep in step with tools/servers.sh)
    "local": {"port": 28346, "dir": "testserver", "runs": "runs"},
    "debug": {"port": 28350, "dir": "debugserver", "runs": "runs/debug"},
}


def name():
    n = os.environ.get("MANGBOT_SERVER") or "local"
    if n not in PROFILES:
        raise SystemExit(f"MANGBOT_SERVER={n!r}: unknown server (known: {', '.join(PROFILES)})")
    return n


def get(n=None):
    """The profile as absolute paths: name, port, dir (the server's directory), runs (the runs root), pilot
    (runs/pilot), freeze (dir/FREEZE), save (dir/save)."""
    n = n or name()
    p = PROFILES[n]
    d = os.path.join(ROOT, p["dir"])
    runs = os.path.join(ROOT, p["runs"])
    return {"name": n, "port": p["port"], "dir": d, "runs": runs, "pilot": os.path.join(runs, "pilot"),
            "freeze": os.path.join(d, "FREEZE"), "save": os.path.join(d, "save")}


PORT = get()["port"]
RUNS = get()["runs"]
FREEZE = get()["freeze"]
