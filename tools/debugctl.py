"""debugctl -- the debug server's test commands (session 13, 2026-11-07; patches/0006, src/server/dbgcmd.c).

    MANGBOT_SERVER=debug python3 debugctl.py place Dive04 Lokkak,_the_Ogre_Chieftain rel=0,1 awake force
    MANGBOT_SERVER=debug python3 debugctl.py truth Dive04            # -> debugserver/truth.json, then printed summary

Speaks the server's remote console (port + 1; the password is the server's CONSOLE_PASSWORD) and sends `dbg ...`. The
server refuses unless it was started with MANGBAND_DEBUG_COMMANDS=1 (tools/server.sh does that for the debug server
only). Commands (all act on NICK's level; positions at=Y,X or rel=DY,DX; names with '_' for spaces, any case):

    place NICK RACE [at=|rel=] [awake|sleep=N] [hp=N] [force]       one monster (force: uniques alive/dead/killed)
    item NICK KIND [at=|rel=] [ego=E] [number=N] [pval=N] [tohit=N] [todam=N] [toac=N] [lev=N] [known]
    terrain NICK FEAT [at=|rel=] [to=Y2,X2]                          a square or a rectangle
    player NICK KEY=N ...   hp sp food gold exp lev confused blind poisoned afraid paralyzed image fast slow stun cut
    teleport NICK at=Y,X|rel=DY,DX
    depth NICK DEPTH
    clear NICK monsters|objects|all
    truth NICK [FILE]       the level as JSON (players, monsters with hp/sleep/seen, objects with true kind/ego and
                            NICK's description, the map, what NICK remembers) -- for the tools, never for the Pilot

As a library: `Debug().cmd("place", "Dive04", ...)` returns the reply line (raises DebugError on "error ..."), and
`Debug().truth("Dive04")` returns the parsed JSON.
"""
import json
import os
import re
import socket
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import servers                                   # noqa: E402


class DebugError(Exception):
    pass


def console_password(server_dir):
    for line in open(os.path.join(server_dir, "mangband.cfg")):
        m = re.match(r'\s*CONSOLE_PASSWORD\s*=\s*"?([^"\n]*)"?', line)
        if m:
            return m.group(1).strip()
    raise DebugError("no CONSOLE_PASSWORD in mangband.cfg")


class Debug:
    def __init__(self, profile=None, timeout=10.0):
        self.p = servers.get(profile)
        self.timeout = timeout

    def _talk(self, line):
        s = socket.create_connection(("127.0.0.1", self.p["port"] + 1), timeout=self.timeout)
        try:
            f = s.makefile("rwb", buffering=0)
            f.write((console_password(self.p["dir"]) + "\n").encode())
            for _ in range(5):          # (a "Connected" greeting comes first)
                first = f.readline().decode(errors="replace").strip()
                if first in ("Authenticated", "Invalid password", ""):
                    break
            if first != "Authenticated":
                raise DebugError(f"console login: {first or 'no answer'}")
            f.write((line + "\n").encode())
            return f.readline().decode(errors="replace").strip()
        finally:
            s.close()

    def cmd(self, *words):
        reply = self._talk("dbg " + " ".join(str(w) for w in words))
        if not reply.startswith("ok"):
            raise DebugError(reply or "no reply")
        return reply

    def truth(self, nick, name="truth.json"):
        """NICK's level as the server knows it (written by the server into its directory, then read)."""
        self.cmd("truth", nick, name)
        return json.load(open(os.path.join(self.p["dir"], name)))


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    d = Debug()
    try:
        reply = d.cmd(*argv)
    except (DebugError, OSError) as e:
        print(f"error: {e}")
        return 1
    print(reply)
    if argv[0] == "truth":
        t = json.load(open(os.path.join(d.p["dir"], argv[2] if len(argv) > 2 else "truth.json")))
        for m in t["monsters"]:
            print(f"  monster {m['race']} at {m['y']},{m['x']} hp {m['hp']}/{m['maxhp']} sleep {m['sleep']}"
                  f"{' SEEN' if m['seen'] else ''}")
        for o in t["objects"]:
            print(f"  object {o['as_seen']} ({o['kind']}{', ' + o['ego'] if o['ego'] else ''}) at {o['y']},{o['x']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
