"""daemon -- the Pilot's process (refactor-candidates E1; docs/pilot-core.md, Process model): main() (the options,
startup, the run loop) and the control socket (Server, a Handler thread per connection).

Started as `python3 pilot.py --nick NICK --port PORT` (restart.sh, hotswap.sh, charsave.sh; pgrep finds it so):
pilot.py's __main__ calls main() here.
"""
import argparse
import json
import os
import queue
import socketserver
import sys
import threading
import time

import glyphs
import pilot
from pilot import Pilot, HERE, VERSION
from world import gnow
sys.path.insert(0, os.path.join(HERE, "..", "client"))
from mang import MangClient, ClientExited      # noqa: E402
sys.path.insert(0, os.path.join(HERE, ".."))
import servers                                   # noqa: E402  ($MANGBOT_SERVER: local or debug)

# --help's description, as before E1 (pilot's docstring line 1 is blank: none)
DESCRIPTION = pilot.__doc__.split("\n")[1]


ARCH_TOKEN_FILE = "architect.token"


def architect_token(priv):
    """The Architect's token (runs/private/architect.token, made on first use, mode 600): a request claiming the
    architect role must carry it (refactor-candidates F3). The Navigator runs as the same Unix user, so this isn't
    security: it stops a bare PILOT_ROLE=architect, and a claim without it is refused and reported."""
    import secrets
    path = os.path.join(priv, ARCH_TOKEN_FILE)
    if not os.path.exists(path):
        os.makedirs(priv, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_hex(16) + "\n")
    return open(path).read().strip()


# --------------------------------------------------------------------------
# control socket
# --------------------------------------------------------------------------

class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        pilot = self.server.pilot
        line = self.rfile.readline()
        if not line:
            return
        req = json.loads(line)
        if req.get("cmd") == "wait-attention":
            timeout = float(req.get("timeout", 600))
            end = gnow() + timeout
            with pilot.att_cond:
                while not pilot.attention and gnow() < end and pilot.running:
                    pilot.att_cond.wait(min(1.0, max(0.01, end - gnow())))
                evs, pilot.attention = pilot.attention, []
            pilot.last_agent = gnow()
            out = {"ok": True, "events": evs}
            pilot.nav_view_events = [f"ATTENTION {e['what']}: {e.get('detail') or ''}" for e in evs]
            if pilot.running:        # (a quiet timeout gets one too: mission 3 missed a stall)
                reply = queue.Queue()
                pilot.requests.put(({"cmd": "status", "since_wait": True}, reply))
                try:
                    out["report"] = reply.get(timeout=10)["report"]
                except queue.Empty:
                    pass
        else:
            reply = queue.Queue()
            pilot.requests.put((req, reply))
            try:
                out = reply.get(timeout=30)
            except queue.Empty:
                out = {"ok": False, "error": "pilot busy"}
        try:
            self.wfile.write((json.dumps(out) + "\n").encode())
        except BrokenPipeError:
            pass          # (the client gave up waiting -- pilotctl's timeout: nothing to tell it)


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main():
    repo = os.path.abspath(os.path.join(HERE, "..", ".."))
    runs = servers.RUNS                  # runs/ (local) or runs/debug/ (the debug server)
    ap = argparse.ArgumentParser(description=DESCRIPTION)
    ap.add_argument("--nick", required=True)
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=servers.PORT,
                    help="default: $MANGBOT_SERVER's (28346, the local server; debug: 28350); the live server (18346) "
                         "needs --live too")
    ap.add_argument("--passfile")
    ap.add_argument("--config")
    ap.add_argument("--rundir", help="default runs/pilot/<nick> (MANGBOT_SERVER=debug: runs/debug/pilot/<nick>)")
    ap.add_argument("--client", default=os.path.join(repo, "mangclient"))
    ap.add_argument("--libdir", default=os.path.join(repo, "lib"))
    ap.add_argument("--pktlog")
    ap.add_argument("--live", action="store_true",
                    help="live-server behaviour (default: test server). Test: mapping/detection devices are sold, not "
                         "kept (the user: no crutches the live server won't give us)")
    ap.add_argument("--hpwarn", type=int, default=5,
                    help="hitpoint_warn 0-9: below N x 10%% HP the server slows our time bubble to 1/5; the "
                         "Pilot's timers follow on its game clock (default 5, the user 2026-10-24; 0 = off)")
    args = ap.parse_args()
    # (refactor-candidates F1: the default was 18346, the live server; now the live port must be meant)
    if args.port == 18346 and not args.live:
        sys.exit("port 18346 is the live server: add --live (live-server behaviour) if that is meant")

    nick = args.nick
    priv = os.path.join(runs, "private")
    arch_token = architect_token(priv)
    rundir = args.rundir or os.path.join(runs, "pilot", nick.lower())
    os.makedirs(rundir, exist_ok=True)
    visuals = os.path.join(rundir, "visuals.txt")
    glyphs.write_visuals(visuals, glyphs.assign(glyphs.load_races()))
    evlog = open(os.path.join(rundir, "events.jsonl"), "a", buffering=1)
    # --hpwarn N: below N x 10% HP the server runs our time bubble at 1/5. Since 2026-10-23 the
    # Pilot's timers are on a game clock that follows it (world.gnow); before, they were
    # wall-clock, and at low HP re-plans fired between our turns (mission 7), so it ran with 0.
    # Missions run with 5 since 2026-10-24 (the user).
    client = MangClient(args.client, args.libdir, nick,
                        args.passfile or os.path.join(priv, nick.lower() + ".pass"),
                        args.host, args.port, config=args.config or os.path.join(priv, nick.lower() + ".mangrc"),
                        cwd=repo, pktlog=args.pktlog, extra_args=["--visuals", visuals, "--hpwarn", str(args.hpwarn)])
    say = lambda *a: print(time.strftime("%H:%M:%S"), *a, file=sys.stderr, flush=True)
    pilot = None
    try:
        ready = client.wait_ready()
        say(f"in the game as {nick}: {ready}")
        pilot = Pilot(client, rundir, say=say)
        pilot.arch_token = arch_token
        pilot.hpwarn = args.hpwarn
        pilot.live = args.live
        pilot.log("options", hpwarn=args.hpwarn, live=args.live)
        orig = pilot.w._on_event
        bulky = {"map", "status", "inven", "options", "commands"}   # query replies
        # every event carries the wall clock too ('t' restarts at 0 with each
        # Pilot process: ~12 log Clerks had to align segments by hand)
        evlog.write(json.dumps({"ev": "pilot_start", "t": 0.0, "epoch": round(time.time(), 3), "nick": nick}) + "\n")
        # the query replies go to state.jsonl, thinned (the Advisor's set-piece memo, blocker 2: a
        # replay couldn't rebuild the map or the pack at second T): status every 2 s when it changes,
        # the pack whenever it changes, the map's changed rows every 10 s
        statelog = open(os.path.join(rundir, "state.jsonl"), "a", buffering=1)
        last = {"status": [0.0, None], "inven": [0.0, None], "map": [0.0, None]}
        last_aware = [None]

        def log_state(ev):
            # 'epoch' is the wall clock like events.jsonl's; the throttle stays on the game clock (session 8: logging
            # gnow put state.jsonl ~3 minutes behind after freezes, and a theft was searched for in the wrong minutes)
            k, now, wall = ev.get("ev"), gnow(), time.time()
            if k not in last or now - last[k][0] < {"status": 2.0, "inven": 0.0, "map": 10.0}[k]:
                return
            if k == "status":
                body = {"y": ev.get("y"), "x": ev.get("x"), "ind": ev.get("ind")}
                # the kinds known (D9, for the scorecard's values as of then): in a status record when they changed
                # since the last one, so always in the first after a start
                try:
                    aware = sorted(pilot.aware_kinds())
                except RuntimeError:              # (the table changed under us: the next record has it)
                    aware = last_aware[0]
                if aware != last_aware[0]:
                    last_aware[0] = aware
                    last[k] = [now, body]
                    statelog.write(json.dumps({"ev": k, "epoch": round(wall, 3), **body, "aware": aware}) + "\n")
                    return
            elif k == "inven":
                body = {"items": ev.get("items")}
            else:
                rows = ev.get("rows") or []
                prev = last[k][1] or []
                body = {"rows": {i: r for i, r in enumerate(rows) if i >= len(prev) or prev[i] != r},
                        "n": len(rows)}
                if not body["rows"]:
                    last[k][0] = now
                    return
                last[k] = [now, rows]
                statelog.write(json.dumps({"ev": k, "epoch": round(wall, 3), **body}) + "\n")
                return
            if body == last[k][1]:
                return
            last[k] = [now, body]
            statelog.write(json.dumps({"ev": k, "epoch": round(wall, 3), **body}) + "\n")

        pilot.w.c.log = lambda ev: (orig(ev), log_state(ev) if ev.get("ev") in bulky else
                                    evlog.write(json.dumps({**ev, "epoch": round(time.time(), 3)}) + "\n"))
        # disturb_near/disturb_panel: the server stops a run the moment a monster
        # in view moves, or at a sector edge (faster than our polling at run
        # speed; the Advisor's running memo). disturb_move stays as the user plays.
        for opt in ("avoid_other", "stack_force_costs", "disturb_near", "disturb_panel"):
            client.send(f"option {opt} yes")
        try:
            # the character's options, once per login (the Advisor couldn't read them from the logs)
            pilot.log("options", options=client.query("options", "options"))
        except Exception as e:
            pilot.log("note", text=f"options query failed: {e!r}")
        sock = os.path.join(rundir, "ctl.sock")
        if os.path.exists(sock):
            os.unlink(sock)
        srv = Server(sock, Handler)
        srv.pilot = pilot
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        say(f"control socket {sock}")
        pilot.notify("started", f"in the game at {pilot.w.depth} (depth), Pilot v{VERSION}")
        while pilot.running:
            pilot.safe_tick()             # (2.64.0: no step's exception ends the Pilot; the game link's still does)
            client.collect(0.05)          # drain the client's own queue; paces the loop
        say("pilot stopping")
    except ClientExited as e:
        say(f"client exited: {e}")
        if pilot is not None and pilot.dead:
            # keep answering status/attention so the Navigator learns of the death
            pilot.running = True
            while pilot.running:
                pilot.handle_requests()
                time.sleep(0.2)
            say("pilot stopping (dead)")
        sys.exit(1)
    finally:
        client.quit()
