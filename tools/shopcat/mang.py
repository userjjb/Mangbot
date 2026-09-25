"""Wrapper around `mangclient -mtool`: start it, send commands, wait for events.

The client prints one JSON event per line on stdout and reads one command per
line on stdin (see src/client/c-tool.c for the full list).
"""
import json
import os
import queue
import subprocess
import threading
import time


class ClientExited(RuntimeError):
    pass


class MangClient:
    def __init__(self, binary, libdir, nick, passfile, host="localhost", port=18346,
                 config=None, pktlog=None, cwd=None, log=None):
        args = [binary, "-mtool", "--libdir", libdir]
        if config:
            args += ["--config", config]
        if pktlog:
            args += ["--pktlog", pktlog]
        # --noprompt is implied by -mtool; SERVER PORT must come last.
        args += ["--passfile", passfile, "--nick", nick, host, str(port)]
        self.proc = subprocess.Popen(args, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1)
        self.events = queue.Queue()
        self.log = log            # optional callable(ev) for every event
        self.pos = None           # (y, x), absolute
        self.door_glyph = "0"
        threading.Thread(target=self._reader, daemon=True).start()

    # --- plumbing -------------------------------------------------------

    def _reader(self):
        for line in self.proc.stdout:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get("ev") == "pos":
                self.pos = (ev["y"], ev["x"])
            if self.log:
                self.log(ev)
            self.events.put(ev)
        self.events.put(None)

    def _get(self, timeout):
        ev = self.events.get(timeout=timeout)
        if ev is None:
            err = self.proc.stderr.read().strip()
            raise ClientExited(err or f"client exited with {self.proc.poll()}")
        return ev

    def send(self, cmd):
        if self.proc.poll() is not None:
            raise ClientExited(f"client exited with {self.proc.returncode}")
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()

    def wait(self, pred, timeout):
        """First event matching pred within timeout, else None. Others are returned too."""
        end = time.time() + timeout
        seen = []
        while True:
            left = end - time.time()
            if left <= 0:
                return None, seen
            try:
                ev = self._get(left)
            except queue.Empty:
                return None, seen
            if pred(ev):
                return ev, seen
            seen.append(ev)

    def collect(self, secs):
        """All events arriving within secs."""
        _, seen = self.wait(lambda e: False, secs)
        return seen

    def query(self, cmd, reply, timeout=10):
        self.send(cmd)
        ev, _ = self.wait(lambda e: e["ev"] in (reply, "error"), timeout)
        if ev is None or ev["ev"] == "error":
            raise RuntimeError(f"{cmd}: {ev and ev.get('text') or 'timeout'}")
        return ev

    # --- session --------------------------------------------------------

    def wait_ready(self, timeout=30, settle=1.5):
        ev, _ = self.wait(lambda e: e["ev"] == "ready", timeout)
        if ev is None:
            raise RuntimeError("no 'ready' event (login failed?)")
        self.door_glyph = ev.get("door", "0")
        # Inventory, indicators and the map arrive just after 'ready'
        self.collect(settle)
        return ev

    def quit(self):
        try:
            self.send("quit")
            self.proc.wait(10)
        except Exception:
            self.proc.kill()

    # --- queries --------------------------------------------------------

    def status(self):
        st = self.query("status", "status")
        if st["y"] >= 0:
            self.pos = (st["y"], st["x"])
        return st

    def map(self):
        return self.query("map", "map")["rows"]

    def inven(self):
        return self.query("inven", "inven")["items"]
