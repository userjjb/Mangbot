#!/usr/bin/env python3
"""scribe -- a messenger character, so Claude can answer the user in game.

Logs in a character (created with --birth if needed) that stays in town, and
sends every line written to FIFO as a private chat message to --to (the
user's character). Long lines are split into chat-sized pieces (a chat line
holds 59 characters, including the "Name: " prefix).

Only for the local server, at the user's request: the tool's characters
otherwise never chat.

    python3 scribe.py --to Dive03 --port 28346 &
    echo "hello from Claude" > runs/observe/scribe.fifo
"""
import argparse
import os
import sys
import textwrap
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shopcat"))
from mang import MangClient      # noqa: E402
from newchar import private_files, DEFAULT_BIRTH   # noqa: E402

MAX_CHAT = 59


def main():
    repo = os.path.abspath(os.path.join(HERE, "..", ".."))
    runs = os.path.abspath(os.path.join(repo, "..", "runs"))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--nick", default="Scribe")
    ap.add_argument("--to", required=True, help="character to whisper to")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=28346)
    ap.add_argument("--fifo", default=os.path.join(runs, "observe", "scribe.fifo"))
    args = ap.parse_args()

    passfile, config = private_files(os.path.join(runs, "private"), args.nick)
    c = MangClient(os.path.join(repo, "mangclient"), os.path.join(repo, "lib"), args.nick, passfile,
                   args.host, args.port, config=config, cwd=repo, birth=DEFAULT_BIRTH)
    c.wait_ready()
    if not os.path.exists(args.fifo):
        os.mkfifo(args.fifo, 0o600)
    prefix = f"{args.to}: "
    print(f"{args.nick} ready; write lines to {args.fifo}", flush=True)

    def pump():
        while True:
            c.collect(1.0)       # keep the client's queue drained

    threading.Thread(target=pump, daemon=True).start()
    while True:
        with open(args.fifo) as f:          # blocks until a writer opens it
            for line in f:
                line = line.strip()
                if not line:
                    continue
                for piece in textwrap.wrap(line, MAX_CHAT - len(prefix)):
                    c.send(f"chat {prefix}{piece}")
                    time.sleep(0.4)


if __name__ == "__main__":
    main()
