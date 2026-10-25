#!/usr/bin/env python3
"""pilotctl -- talk to a running pilot (see HANDBOOK.md).

    pilotctl.py [--nick NAME] status
    pilotctl.py goal dive 500 [force] | goal explore [until=stairs] [radius=N] | goal goto Y,X|>|<|item [force]
                | goal recall [force] | goal rest | goal wait SECS
                | goal shop N [list] [buy NAME:N[@MAX] (have N) | NAME:+N (N more)] [sell NAME:N] [quote NAME]
                | goal search | goal searchroom Y,X
    pilotctl.py stop
    pilotctl.py order flee_hp=0.4 stop_on=unique,danger ...
    pilotctl.py wear|takeoff|quaff|read|eat|fuel|inspect LETTER
    pilotctl.py destroy|drop LETTER [COUNT]
    pilotctl.py inscribe LETTER TEXT...    | pickup | stairs [<|>]
    pilotctl.py wait [SECS] [--brief]      # block until the pilot asks for attention
                                           # (--brief: status lines, monsters, stairs, news only)
    pilotctl.py attention                  # pending attention events, without waiting
    pilotctl.py monster NAME               # this server's data for a monster + the pilot's verdict
    pilotctl.py mission start LABEL navigator=MODEL [effort=L] [notes=..] | mission end   # (the Architect) mission markers
    pilotctl.py status [full]              # the compact report (full: everything, the long form)
    pilotctl.py pack | equip | orders      # one part of the full report (pack with letters, ...)
    pilotctl.py map [R]                    # the map within R squares of @ (default 15)
    pilotctl.py drainers [STAT] [MAXLEVEL]  # monsters whose blows drain a stat (default STR/DEX/CON, to clvl+10)
    pilotctl.py say TEXT...                # answer the user (shown in their viewer, logged)
    pilotctl.py search [N]                 # search the squares around you N times (default 15)
    pilotctl.py disarm|open [DIR]          # a chest/trap/door in DIR (5 = underfoot)
    pilotctl.py journal "situation | decision | why"   # your journal line, stamped with time/depth/HP
    pilotctl.py avoid Y,X [R] | avoid NAME | avoid clear | avoid   # no-go zones the paths route around
    pilotctl.py gate FEET [recall]         # the supply gate: what's missing for going down to FEET
    pilotctl.py plan town [kit=A|B|C|none] [buy [STORE/]NAME[:N][@MAX],...]   # the whole town visit, by policy
    pilotctl.py plan trip LO-HI [until "COND or ..."] [then recall|town] [level_min=N] [force]   # a whole trip
    pilotctl.py plan | plan stop | plan resume   # the plan now / end it / end your goal, hand back to the plan
    pilotctl.py standing [TEXT | -N]       # standing instructions shown in every report (add / remove / list)
    pilotctl.py rule [monster|drop|fight|feeling|unknown|owner|const|object|room] ...   # query the rulebook
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
              "Since the last report", "Progress:",
              # the compact report's lines
              "Cures", "Here:", "Monsters:", "News:", "Since last (")


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
    if cmd == "rule":
        # the rulebook (the Advisor's tables, synced into tools/rulebook): no Pilot needed
        import subprocess
        rule = os.path.join(HERE, "..", "rulebook", "rule.py")
        subprocess.run([sys.executable, rule] + args)
        return
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
        # (PILOT_ROLE=architect marks the Architect's and the harness's own calls;
        # the Navigator's are refused some things in the dungeon: restructure step 2)
        out = call(sock, {"cmd": cmd, "args": args, "role": os.environ.get("PILOT_ROLE", "navigator")}, 40)
    except (ConnectionError, FileNotFoundError, json.JSONDecodeError, OSError) as e:
        if cmd == "complain" and args:
            # the Pilot is down, which is often what there is to complain about
            # (mission 21: a 10-minute server crash, nothing could be filed)
            import time
            with open(os.path.join(RUNS, "complaints.md"), "a") as f:
                f.write(f"- {time.strftime('%Y-%m-%d %H:%M:%S')} {nick.lower()} (Navigator, Pilot down): "
                        f"{' '.join(args)}\n")
            print("(Pilot not answering; the complaint was written to runs/complaints.md directly)")
            return
        print(f"(Pilot not answering: {e.__class__.__name__}; it may be restarting -- wait 20 s and retry)")
        return
    if out.get("user_messages"):
        print("USER MESSAGE(S) NOT YET ANSWERED (reply with say): " + " | ".join(out["user_messages"]))
    if "report" in out:
        print(out["report"])
    elif "pack" in out:
        if out.get("did"):
            print("DONE: " + out["did"] + (f" -- {out['note']}" if out.get("note") else ""))
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
