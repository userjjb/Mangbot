#!/usr/bin/env python3
"""shopcat -- catalog MAngband player shops on the current level.

Drives `mangclient -mtool`: finds closed house doors on the map, walks next
to each, opens it, and records the stock of every player shop (optionally
examining each item for its full name, description and asking price).

Output is JSON lines, one record per door visit (see README.md).
"""
import argparse
import json
import os
import re
import sys
import time
from collections import deque

from mang import MangClient, ClientExited
import nav

STORE_PC = 2
FOOD_HUNGRY = 2       # hunger indicator: 0-1 weak, 2 hungry, 3 normal, 4 full, 5 gorged
TV_FOOD = 80

# Worth another try later: someone inside, owner threw us out, owner left the
# door open, or no answer at all
RETRYABLE = ("locked", "ejected", "no_door", "none")

RE_COSTS = re.compile(r"This house costs (\d+) gold")
RE_ASK = re.compile(r"\bfor sale\s+(\d+)")
RE_INSCR = re.compile(r"\s*\{[^}]*\}\s*$")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Cataloger:
    def __init__(self, client, out, examine=True, retries=2, retry_delay=30.0, verbose=True):
        self.c = client
        self.out = out
        self.examine = examine
        self.retries = retries
        self.retry_delay = retry_delay
        self.verbose = verbose
        self.depth = None

    def say(self, *a):
        if self.verbose:
            print(*a, file=sys.stderr, flush=True)

    def write(self, rec):
        self.out.write(json.dumps(rec) + "\n")
        self.out.flush()

    # --- upkeep ---------------------------------------------------------

    def upkeep(self):
        """Eat if hungry; stop if dead. Returns status."""
        st = self.c.status()
        self.depth = st["ind"].get("depth", [None])[0]
        if st.get("ghost"):
            raise RuntimeError("character is dead (ghost) -- stopping")
        hunger = st["ind"].get("hunger", [3])[0]
        if hunger <= FOOD_HUNGRY:
            food = [it for it in self.c.inven() if it["tval"] == TV_FOOD and not it["equip"]]
            if food:
                self.say(f"  eating {food[0]['name']} (hunger={hunger})")
                self.c.send(f"eat {food[0]['item']}")
                self.c.collect(1.0)
            else:
                self.say(f"  WARNING: hungry (hunger={hunger}) and no food")
        return st

    # --- one door -------------------------------------------------------

    def open_door(self, door, rows):
        """Go next to door and open it. Returns (kind, detail) where kind is
        shop | for_sale | locked | ejected | no_door | unreachable | none."""
        spots = nav.stand_spots(rows, door)
        if not spots:
            return "unreachable", None
        at = nav.goto(self.c, spots)
        if at is None:
            return "unreachable", None
        self.c.collect(0.3)
        self.c.send(f"open {nav.direction(at, door)}")
        end = time.time() + 4
        while time.time() < end:
            ev, _ = self.c.wait(lambda e: e["ev"] in ("store", "message"), end - time.time())
            if ev is None:
                break
            if ev["ev"] == "store":
                return ("shop" if ev["flag"] & STORE_PC else "other_store"), ev
            text = ev["text"]
            m = RE_COSTS.search(text)
            if m:
                return "for_sale", int(m.group(1))
            if "doors are locked" in text:
                return "locked", None
            if "nothing there to open" in text:
                return "no_door", None
        return "none", None

    def read_shop(self, store):
        """Record the listing (+ examine each slot). Returns (items, complete)."""
        items = []
        for it in store["items"]:
            items.append({
                "slot": it["slot"], "name": it["name"], "count": it["number"],
                "price_each": it["price"], "weight_each": it["weight"] / 10.0,
                "ga": it["ga"], "gc": chr(it["gc"]) if 32 <= it["gc"] < 127 else it["gc"],
                "attr": it["attr"],
            })
        complete = len(items) == store["num"]
        if self.examine:
            for item in items:
                self.c.send(f"examine {item['slot']}")
                ev, seen = self.c.wait(lambda e: e["ev"] in ("popup", "store_leave"), 5)
                if ev is None or ev["ev"] == "store_leave" or any(e["ev"] == "store_leave" for e in seen):
                    complete = False
                    break
                header = ev["header"]
                m = RE_ASK.search(header)
                item["full_name"] = RE_INSCR.sub("", header)
                item["ask_price"] = int(m.group(1)) if m else None
                item["examine_text"] = " ".join(l.strip() for l in ev["lines"] if l.strip())
        self.c.send("leave")
        self.c.collect(0.3)
        return items, complete

    def visit(self, door, rows):
        kind, detail = self.open_door(door, rows)
        rec = {"time": now(), "depth": self.depth, "door_y": door[0], "door_x": door[1], "result": kind}
        if kind == "shop":
            items, complete = self.read_shop(detail)
            rec.update(store_name=detail["name"], owner=detail["owner"], flag=detail["flag"],
                       num_items=detail["num"], complete=complete, items=items)
            if not complete:
                rec["result"] = kind = "ejected"
        elif kind == "for_sale":
            rec["house_price"] = detail
        elif kind == "other_store":
            self.c.send("leave")
            rec.update(store_name=detail["name"], owner=detail["owner"], flag=detail["flag"])
        return rec

    # --- the level ------------------------------------------------------

    def run(self, max_doors=None, only=None):
        self.upkeep()
        rows = self.c.map()
        g = self.c.door_glyph
        doors = [(y, x) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch == g]
        self.say(f"depth {self.depth}: {len(doors)} house doors on the map")
        if only:
            missing = [d for d in only if d not in doors]
            if missing:
                self.say(f"  not closed house doors on the map, skipping: {missing}")
            doors = [d for d in only if d in doors]

        # Visit in nearest-neighbour order from our position
        order, pos = [], self.c.pos
        left = set(doors)
        while left:
            nxt = min(left, key=lambda d: max(abs(d[0] - pos[0]), abs(d[1] - pos[1])))
            order.append(nxt)
            left.discard(nxt)
            pos = nxt
        if max_doors:
            order = order[:max_doors]

        queue = deque((d, 0, 0.0) for d in order)     # (door, tries, not_before)
        summary = {}
        while queue:
            # Next door that's due; if none is, wait for the earliest
            due = [q for q in queue if q[2] <= time.time()]
            if not due:
                wake = min(q[2] for q in queue)
                self.say(f"  waiting {wake - time.time():.0f}s before retrying")
                while time.time() < wake:
                    self.c.collect(min(5.0, max(0.1, wake - time.time())))
                continue
            item = due[0]
            queue.remove(item)
            door, tries, _ = item
            self.upkeep()
            rec = self.visit(door, rows)
            rec["attempt"] = tries + 1
            self.write(rec)
            kind = rec["result"]
            extra = (f" '{rec['store_name']}' by {rec['owner']}, {len(rec['items'])} items"
                     if kind == "shop" else f" ({rec['house_price']} gold)" if kind == "for_sale" else "")
            self.say(f"  door {door}: {kind}{extra}")
            if kind in RETRYABLE and tries < self.retries:
                queue.append((door, tries + 1, time.time() + self.retry_delay))
            else:
                summary[kind] = summary.get(kind, 0) + 1
            rows = self.c.map()   # the map fills in as we explore
        return summary


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "..", ".."))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--nick", required=True)
    ap.add_argument("--passfile", required=True, help="file whose first line is the password")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=18346)
    ap.add_argument("--client", default=os.path.join(repo, "mangclient"))
    ap.add_argument("--libdir", default=os.path.join(repo, "lib"))
    ap.add_argument("--config", help="client config file (default: client's own)")
    ap.add_argument("--out", default="catalog.jsonl", help="append records here")
    ap.add_argument("--no-examine", action="store_true", help="only record the listing")
    ap.add_argument("--max-doors", type=int)
    ap.add_argument("--door", action="append", metavar="Y,X",
                    type=lambda s: tuple(int(v) for v in s.split(",")),
                    help="only visit this door (repeatable)")
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--retry-delay", type=float, default=30.0, help="seconds before revisiting a door")
    ap.add_argument("--pktlog")
    ap.add_argument("--events", help="append every client event to this file (debug)")
    args = ap.parse_args()

    evlog = open(args.events, "a", buffering=1) if args.events else None
    client = MangClient(args.client, args.libdir, args.nick, args.passfile, args.host, args.port,
                        config=args.config, pktlog=args.pktlog, cwd=repo,
                        log=(lambda ev: evlog.write(json.dumps(ev) + "\n")) if evlog else None)
    try:
        client.wait_ready()
        with open(args.out, "a") as out:
            summary = Cataloger(client, out, examine=not args.no_examine, retries=args.retries,
                                retry_delay=args.retry_delay).run(args.max_doors, args.door)
        print(json.dumps({"summary": summary}), file=sys.stderr)
    except ClientExited as e:
        print(f"client exited: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        client.quit()
        if evlog:
            evlog.close()


if __name__ == "__main__":
    main()
