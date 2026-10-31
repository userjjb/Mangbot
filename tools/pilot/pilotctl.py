#!/usr/bin/env python3
"""pilotctl -- talk to a running Pilot: one command per call, the reply printed.

    pilotctl.py --nick NICK COMMAND [ARGS...]      e.g. status, wait 240, plan town, plan trip 700-800 until "...",
                                                   goal leave, journal "...", say TEXT, complain TEXT

The commands: the Navigator's are in HANDBOOK.md (every goal, order, event and report line: HANDBOOK-reference.md);
every command, who may use it and what it refuses: docs/commands.md (/projectnb/jbrcs/mangband/docs/).
`wait [SECS] [--brief]` blocks until the Pilot asks for attention; `rule ...` queries the rulebook (no Pilot needed).
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
    nick = os.environ.get("PILOT_NICK")
    if argv[:1] == ["--nick"]:
        nick, argv = argv[1], argv[2:]
    if not argv:
        print(__doc__)
        return
    if not nick:
        # (refactor-candidates F2: the default was dive01, long dead) the one Pilot whose socket answers
        live = []
        for d in sorted(os.listdir(os.path.join(RUNS, "pilot"))):
            sp = os.path.join(RUNS, "pilot", d, "ctl.sock")
            if os.path.exists(sp):
                try:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.settimeout(1)
                    s.connect(sp)
                    s.close()
                    live.append(d)
                except OSError:
                    pass
        if len(live) != 1:
            print("which Pilot? " + (f"{len(live)} are running ({', '.join(live)})" if live else "none is running")
                  + ": give --nick NAME")
            return
        nick = live[0]
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
        req = {"cmd": cmd, "args": args, "role": os.environ.get("PILOT_ROLE", "navigator")}
        if os.environ.get("PILOT_TOKEN"):
            req["token"] = os.environ["PILOT_TOKEN"]
        out = call(sock, req, 40)
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
    note_said = False       # (each note printed once: refactor-candidates A12)
    if "report" in out:
        print(out["report"])
    elif "pack" in out:
        if out.get("did"):
            print("DONE: " + out["did"] + (f" -- {out['note']}" if out.get("note") else ""))
            note_said = True
        for line in out.get("said", []):
            print(line)
        print("Pack now: " + "; ".join(out["pack"]))
    elif "text" in out:
        print(out["text"])
    elif "events" in out:
        for ev in out["events"]:
            print(f"ATTENTION {ev['what']}: {ev.get('detail') or ''}")
    else:
        print(json.dumps({k: v for k, v in out.items() if k != "note"}))
    if out.get("note") and not note_said:
        print("NOTE: " + out["note"])


if __name__ == "__main__":
    main()
