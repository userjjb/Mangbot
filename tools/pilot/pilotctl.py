#!/usr/bin/env python3
"""pilotctl -- talk to a running pilot (see HANDBOOK.md).

    pilotctl.py [--nick NAME] status
    pilotctl.py goal dive 500 [force] | goal explore [until=stairs] [radius=N] | goal goto Y,X|>|<|item [force]
                | goal recall [force] | goal rest | goal wait SECS
                | goal shop N [list] [buy NAME:N[@MAX]] [sell NAME:N] [quote NAME]
    pilotctl.py stop
    pilotctl.py order flee_hp=0.4 stop_on=unique,danger ...
    pilotctl.py wear|takeoff|quaff|read|eat|fuel|inspect LETTER
    pilotctl.py destroy|drop LETTER [COUNT]
    pilotctl.py inscribe LETTER TEXT...    | pickup | stairs [<|>]
    pilotctl.py wait [SECS] [--brief]      # block until the pilot asks for attention
                                           # (--brief: status lines, monsters, stairs, news only)
    pilotctl.py attention                  # pending attention events, without waiting
    pilotctl.py monster NAME               # this server's data for a monster + the pilot's verdict
    pilotctl.py say TEXT...                # answer the user (shown in their viewer, logged)
    pilotctl.py search [N]                 # search the squares around you N times (default 15)
    pilotctl.py disarm|open [DIR]          # a chest/trap/door in DIR (5 = underfoot)
    pilotctl.py journal "situation | decision | why"   # your journal line, stamped with time/depth/HP
    pilotctl.py avoid Y,X [R] | avoid NAME | avoid clear | avoid   # no-go zones the paths route around
    pilotctl.py gate FEET [recall]         # the supply gate: what's missing for going down to FEET
    pilotctl.py complain TEXT...           # what you lacked / what got in your way (not your mistakes)
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


BRIEF_KEEP = ("USER MESSAGE", "Standing on:", "Supplies:", "Monsters in view:", "Known stairs:", "Since last report:",
              "Since the last report", "Progress:")


def brief_report(report):
    """The first two lines (character, stats) and the few lines that change
    decisions; the map, equipment, pack, messages and orders are left out
    (use `status` when you need them)."""
    lines = report.split("\n")
    return "\n".join(lines[:2] + [l for l in lines[2:] if l.startswith(BRIEF_KEEP)])


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
        brief = "--brief" in args
        args = [a for a in args if a != "--brief"]
        t = float(args[0]) if args else 600
        try:
            out = call(sock, {"cmd": "wait-attention", "timeout": t}, t + 30)
        except (ConnectionError, FileNotFoundError, json.JSONDecodeError, OSError) as e:
            # the Pilot was restarted (parked for an update) while we waited
            print(f"(Pilot not answering: {e.__class__.__name__}; it may be restarting -- "
                  "wait 20 s and try again, then re-issue your goal)")
            return
        for ev in out.get("events", []):
            print(f"ATTENTION {ev['what']}: {ev.get('detail') or ''}  (goal: {ev.get('goal')})")
        if not out.get("events"):
            print("(no attention events)")
        if out.get("report"):
            # a quiet timeout: the short form (progress check), unless there's news
            print(brief_report(out["report"]) if brief or not out.get("events") else out["report"])
        return
    try:
        out = call(sock, {"cmd": cmd, "args": args}, 40)
    except (ConnectionError, FileNotFoundError, json.JSONDecodeError, OSError) as e:
        print(f"(Pilot not answering: {e.__class__.__name__}; it may be restarting -- wait 20 s and retry)")
        return
    if out.get("user_messages"):
        print("USER MESSAGE(S) NOT YET ANSWERED (reply with say): " + " | ".join(out["user_messages"]))
    if "report" in out:
        print(out["report"])
    elif "pack" in out:
        for line in out.get("said", []):
            print(line)
        print("Pack now: " + "; ".join(out["pack"]))
    elif "text" in out:
        print(out["text"])
    elif "events" in out:
        for ev in out["events"]:
            print(f"ATTENTION {ev['what']}: {ev.get('detail') or ''}")
    else:
        print(json.dumps(out))
    if out.get("note"):
        print("NOTE: " + out["note"])


if __name__ == "__main__":
    main()
