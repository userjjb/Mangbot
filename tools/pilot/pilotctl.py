#!/usr/bin/env python3
"""pilotctl -- talk to a running pilot (see HANDBOOK.md).

    pilotctl.py [--nick NAME] status
    pilotctl.py goal dive 500 | goal explore [until=stairs] [radius=N] | goal goto Y,X|>|<|item
                | goal recall | goal rest | goal wait SECS
    pilotctl.py stop
    pilotctl.py order flee_hp=0.4 stop_on=unique,danger ...
    pilotctl.py wear|takeoff|quaff|read|eat|fuel|inspect LETTER
    pilotctl.py destroy|drop LETTER [COUNT]
    pilotctl.py inscribe LETTER TEXT...    | pickup | stairs [<|>]
    pilotctl.py wait [SECS]                # block until the pilot asks for attention
    pilotctl.py attention                  # pending attention events, without waiting
"""
import json
import os
import socket
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "runs"))


def call(sock, req, timeout):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(sock)
    s.sendall((json.dumps(req) + "\n").encode())
    buf = b""
    while not buf.endswith(b"\n"):
        d = s.recv(65536)
        if not d:
            break
        buf += d
    return json.loads(buf)


def main():
    argv = sys.argv[1:]
    nick = os.environ.get("PILOT_NICK", "dive01")
    if argv[:1] == ["--nick"]:
        nick, argv = argv[1], argv[2:]
    if not argv:
        print(__doc__)
        return
    sock = os.path.join(RUNS, "pilot", nick.lower(), "ctl.sock")
    cmd, args = argv[0], argv[1:]
    if cmd == "wait":
        t = float(args[0]) if args else 600
        out = call(sock, {"cmd": "wait-attention", "timeout": t}, t + 30)
        for ev in out.get("events", []):
            print(f"ATTENTION {ev['what']}: {ev.get('detail') or ''}  (goal: {ev.get('goal')})")
        if not out.get("events"):
            print("(no attention events)")
        if out.get("report"):
            print(out["report"])
        return
    out = call(sock, {"cmd": cmd, "args": args}, 40)
    if "report" in out:
        print(out["report"])
    elif "pack" in out:
        for line in out.get("said", []):
            print(line)
        print("Pack now: " + "; ".join(out["pack"]))
    elif "events" in out:
        for ev in out["events"]:
            print(f"ATTENTION {ev['what']}: {ev.get('detail') or ''}")
    else:
        print(json.dumps(out))


if __name__ == "__main__":
    main()
