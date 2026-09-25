#!/usr/bin/env python3
"""record -- record a human playing the normal client, for study.

Starts the interactive (GCU) client inside a private tmux server
(`tmux -L mang`, so the player's own tmux sessions are untouched) and records:

  OUT/pkt.jsonl      every packet, plus every key the client consumed
                     (client --pktlog; key records have "dir": "K")
  OUT/screens.jsonl  a screen snapshot whenever the screen changes:
                     {"t": epoch, "rows": [...]} (colours as ANSI escapes)
  OUT/meta.json      what was run, when, terminal size

The player attaches from any shell on the same host:

    tmux -L mang attach -t play        (detach: Ctrl-b d; the game keeps going)

Recording stops when the client exits (Ctrl-X in game saves and quits).

    python3 record.py --host localhost --port 28346 [--out DIR] [--nick NAME]
"""
import argparse
import json
import os
import subprocess
import sys
import time

SOCK = "mang"
SESSION = "play"


def tmux(*args, check=True):
    return subprocess.run(["tmux", "-L", SOCK, *args], check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def alive():
    return tmux("has-session", "-t", SESSION, check=False).returncode == 0


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "..", ".."))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=18346)
    ap.add_argument("--nick", help="pre-fill the character name (the client still asks for the password)")
    ap.add_argument("--out", help="output directory (default: runs/observe/<time>)")
    ap.add_argument("--config", help="client config file (default: OUT/mangrc, fresh)")
    ap.add_argument("--interval", type=float, default=0.2, help="screen poll interval, s")
    ap.add_argument("--size", default="200x60", help="initial window size before anyone attaches")
    args = ap.parse_args()

    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = os.path.abspath(args.out or os.path.join(repo, "..", "runs", "observe", stamp))
    # Private: the logs hold chat, the character name and the player's keys
    os.makedirs(out, mode=0o700, exist_ok=True)
    os.chmod(out, 0o700)
    config = args.config or os.path.join(out, "mangrc")
    if not os.path.exists(config):
        with open(config, "w") as f:
            f.write(f"[MAngband]\nLibDir {os.path.join(repo, 'lib')}/\n")
            if args.nick:
                f.write(f"nick {args.nick}\n")

    if alive():
        sys.exit(f"tmux -L {SOCK} session '{SESSION}' already exists; attach or kill it first")

    client = [os.path.join(repo, "mangclient"), "-mgcu", "--config", config,
              "--pktlog", os.path.join(out, "pkt.jsonl"), args.host, str(args.port)]
    w, h = args.size.split("x")
    tmux("new-session", "-d", "-s", SESSION, "-x", w, "-y", h, "-c", repo, " ".join(client))
    # A lone ESC shouldn't wait half a second to be told apart from a key sequence
    tmux("set-option", "-s", "escape-time", "10")
    tmux("set-option", "-t", SESSION, "remain-on-exit", "off")

    meta = {"start": time.time(), "cmd": client, "host": args.host, "port": args.port, "out": out}
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(f"recording to {out}\nattach with:  tmux -L {SOCK} attach -t {SESSION}", flush=True)

    last, frames = None, 0
    with open(os.path.join(out, "screens.jsonl"), "a") as sf:
        while alive():
            r = tmux("capture-pane", "-p", "-e", "-t", SESSION, check=False)
            if r.returncode != 0:
                break
            size = tmux("display-message", "-p", "-t", SESSION, "#{pane_width}x#{pane_height}",
                        check=False).stdout.strip()
            if r.stdout != last:
                last = r.stdout
                frames += 1
                sf.write(json.dumps({"t": round(time.time(), 3), "size": size,
                                     "rows": r.stdout.split("\n")}) + "\n")
                sf.flush()
            time.sleep(args.interval)
    meta["end"] = time.time()
    meta["frames"] = frames
    with open(os.path.join(out, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(f"session ended; {frames} screens recorded in {out}")


if __name__ == "__main__":
    main()
