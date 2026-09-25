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
import wild

STORE_PC = 2
FOOD_HUNGRY = 2       # hunger indicator: 0-1 weak, 2 hungry, 3 normal, 4 full, 5 gorged
TV_FOOD = 80
TV_LITE = 39
TV_FLASK = 77

RE_TURNS = re.compile(r"with (\d+) turns of light")


def light_turns(name):
    m = RE_TURNS.search(name)
    return int(m.group(1)) if m else None

# Worth another try later: someone inside, owner threw us out, owner left the
# door open, or no answer at all
RETRYABLE = ("locked", "ejected", "no_door", "none")

RE_COSTS = re.compile(r"This house costs (\d+) gold")
RE_ASK = re.compile(r"\bfor sale\s+(\d+)")
RE_INSCR = re.compile(r"\s*\{[^}]*\}\s*$")


class Danger(RuntimeError):
    """HP is low and not recovering -- stop before the character dies."""


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Cataloger:
    def __init__(self, client, out, examine=True, retries=2, retry_delay=30.0, verbose=True, nogo_file=None):
        self.c = client
        self.out = out
        self.examine = examine
        self.retries = retries
        self.retry_delay = retry_delay
        self.verbose = verbose
        self.depth = None
        self.world = None
        self.rest_below = 0.5     # rest when HP falls below this fraction
        self.next_light_check = 0.0
        self.refuel_below = 3000  # lantern turns; a flask adds 7500, the lantern holds 15000
        self.warned_oil = False
        self.warned_food = False
        self.hits_seen = 0
        self.no_go = {}           # depth -> tiles to stay out of (arenas)
        self.nogo_file = nogo_file  # remembered across runs
        if nogo_file and os.path.exists(nogo_file):
            with open(nogo_file) as f:
                self.no_go = {int(d): {tuple(t) for t in tiles} for d, tiles in json.load(f).items()}

    def say(self, *a):
        if self.verbose:
            print(*a, file=sys.stderr, flush=True)

    def write(self, rec):
        self.out.write(json.dumps(rec) + "\n")
        self.out.flush()

    # --- upkeep ---------------------------------------------------------

    def upkeep(self):
        """Eat if hungry; rest if hurt; stop if dead. Returns status."""
        st = self.c.status()
        self.depth = st["ind"].get("depth", [None])[0]
        self.world = wild.world_coords(self.depth) if self.depth is not None else None
        nav.extra_blocked = self.no_go.setdefault(self.depth, set())
        if self.c.in_arena:
            self.escape_arena()
            st = self.c.status()
        if st.get("ghost"):
            raise RuntimeError("character is dead (ghost) -- stopping")
        if time.time() >= self.next_light_check:
            self.light_up()
            self.next_light_check = time.time() + 20
        if self.c.hits != self.hits_seen:
            self.hits_seen = self.c.hits
            self.fight()
            st = self.c.status()
        hp, mhp = st["ind"].get("hp", [1, 1])[:2]
        if mhp and hp < self.rest_below * mhp:
            self.fight()
            self.rest(hp, mhp)
        hunger = st["ind"].get("hunger", [3])[0]
        if hunger <= FOOD_HUNGRY:
            food = [it for it in self.c.inven() if it["tval"] == TV_FOOD and not it["equip"]]
            if food:
                self.say(f"  eating {food[0]['name']} (hunger={hunger})")
                self.c.send(f"eat {food[0]['item']}")
                self.c.collect(1.0)
            elif hunger <= 1 and self.depth != 0:
                # Weak and nothing to eat; nobody digests in town, so stop out here
                raise Danger(f"weak from hunger (hunger={hunger}) and no food")
            elif not self.warned_food:
                self.say(f"  WARNING: hungry (hunger={hunger}) and no food")
                self.warned_food = True
        return st

    def light_up(self):
        """Keep a light burning: wield a lantern if we have one (else a torch),
        and refill the lantern from a flask of oil when it runs low."""
        inv = self.c.inven()
        if not inv:
            return
        worn = [it for it in inv if it["equip"] and it["tval"] == TV_LITE]
        pack_lanterns = [it for it in inv if not it["equip"] and it["tval"] == TV_LITE and "Lantern" in it["name"]]
        pack_torches = [it for it in inv if not it["equip"] and it["tval"] == TV_LITE and "Torch" in it["name"]]
        flasks = [it for it in inv if not it["equip"] and it["tval"] == TV_FLASK]

        if not worn or ("Lantern" not in worn[0]["name"] and pack_lanterns):
            pick = (pack_lanterns or pack_torches)
            if pick:
                self.say(f"  wielding {pick[0]['name']}")
                self.c.send(f"custom w item={pick[0]['item']}")
                self.c.collect(1.0)
            return

        turns = light_turns(worn[0]["name"])
        if "Lantern" in worn[0]["name"] and turns is not None and turns < self.refuel_below:
            if flasks:
                self.say(f"  refilling lantern ({turns} turns left, {flasks[0]['number']} flasks)")
                self.c.send(f"custom F item={flasks[0]['item']}")
                self.c.collect(1.0)
            elif not self.warned_oil:
                self.say(f"  WARNING: lantern at {turns} turns and no oil left")
                self.warned_oil = True
        elif "Torch" in worn[0]["name"] and turns is not None and turns < 500 and pack_torches:
            self.say(f"  swapping in a fresh torch ({turns} turns left)")
            self.c.send(f"custom w item={pack_torches[0]['item']}")
            self.c.collect(1.0)

    def escape_arena(self, tries=4):
        """Walk into the arena wall until we're let out, then keep away from it.
        (Bumping an arena wall from outside teleports you in; from inside,
        alone, it lets you out with a short teleport.)"""
        rows = self.c.map()
        y0, x0 = self.c.pos
        # The arena interior: everything reachable from here without crossing '#'
        inner, todo = {(y0, x0)}, [(y0, x0)]
        while todo and len(inner) < 2000:
            cy, cx = todo.pop()
            for ny, nx in nav.neighbours(cy, cx, len(rows), len(rows[0])):
                if (ny, nx) not in inner and rows[ny][nx] != "#" and nav.inside(ny, nx):
                    inner.add((ny, nx))
                    todo.append((ny, nx))
        if len(inner) >= 2000:
            # Not enclosed, so not an arena: don't go bumping walls
            self.say(f"  not shut in after all (open ground around {self.c.pos})")
            self.c.in_arena = False
            return
        ys = [p[0] for p in inner]
        xs = [p[1] for p in inner]
        # The arena itself: interior plus its wall ring. No wider margin -- near
        # a no-go zone goto() walks its own path tile by tile, so it never
        # bumps the wall, and a margin could shut us in right after leaving.
        box = {(y, x) for y in range(min(ys) - 1, max(ys) + 2) for x in range(min(xs) - 1, max(xs) + 2)}
        self.say(f"  in an arena ({min(ys)}-{max(ys)}, {min(xs)}-{max(xs)}); leaving")
        for _ in range(tries):
            rows = self.c.map()
            here = self.c.pos
            walls = [nb for nb in nav.neighbours(*here, len(rows), len(rows[0])) if rows[nb[0]][nb[1]] == "#"]
            if not walls:
                # Walk to the interior tile nearest a wall first
                edge = [p for p in inner if any(rows[n[0]][n[1]] == "#"
                                                 for n in nav.neighbours(*p, len(rows), len(rows[0])))]
                saved, nav.extra_blocked = nav.extra_blocked, set()
                try:
                    nav.goto(self.c, edge, rows=rows, deadline=time.time() + 30)
                except nav.Jumped:
                    pass
                finally:
                    nav.extra_blocked = saved
                continue
            self.c.send(f"walk {nav.direction(here, walls[0])}")
            self.c.collect(1.5)
            if not self.c.in_arena:
                break
        self.no_go.setdefault(self.depth, set()).update(box)
        nav.extra_blocked = self.no_go[self.depth]
        if self.nogo_file:
            with open(self.nogo_file, "w") as f:
                json.dump({str(d): sorted(t) for d, t in self.no_go.items()}, f)
        if self.c.in_arena:
            raise Danger("stuck in an arena")
        self.say(f"  out of the arena at {self.c.pos}")

    def supplies(self):
        """(rations of food, flasks of oil, gold)"""
        inv = self.c.inven()
        food = sum(it["number"] for it in inv if it["tval"] == TV_FOOD and not it["equip"])
        oil = sum(it["number"] for it in inv if it["tval"] == TV_FLASK and not it["equip"])
        return food, oil, self.c.status()["ind"]["gold"][0]

    def restock(self, want_food=10, want_oil=6):
        """In town: buy food and oil at the General Store ('1') with what gold we have."""
        food, oil, gold = self.supplies()
        if food >= want_food and oil >= want_oil:
            return
        rows = self.c.map()
        shop = [(y, x) for y, r in enumerate(rows) for x, ch in enumerate(r) if ch == "1"]
        if not shop or gold <= 0:
            return
        at = nav.goto(self.c, nav.stand_spots(rows, shop[0]))
        if at is None:
            self.say("  restock: can't reach the General Store")
            return
        store = None
        for _ in range(3):
            self.c.send(f"walk {nav.direction(self.c.pos, shop[0])}")
            store, _ = self.c.wait(lambda e: e["ev"] == "store", 3)
            if store:
                break
        if not store:
            self.say("  restock: the General Store didn't open")
            return
        bought = []
        for key, have, want in (("Ration", food, want_food), ("Flask", oil, want_oil)):
            item = next((it for it in store["items"] if key in it["name"]), None)
            if not item or have >= want or not item["price"]:
                continue
            n = min(want - have, item["number"], gold // item["price"])
            if n <= 0:
                continue
            self.c.send(f"custom p store item={item['slot']} value={n} entry={item['price'] * n}")
            self.c.collect(1.5)
            gold -= n * item["price"]
            bought.append(f"{n} x {key}")
            ev, _ = self.c.wait(lambda e: e["ev"] == "store", 1)
            store = ev or store
        self.c.send("leave")
        self.c.collect(0.5)
        food, oil, gold = self.supplies()
        self.say(f"  restocked ({', '.join(bought) or 'nothing affordable'}): "
                 f"{food} rations, {oil} flasks, {gold} gold left")

    def fight(self, rounds=12):
        """Attack monsters next to us (walking into a monster attacks it).
        Monsters are the letters on the map; other players are '@'."""
        for _ in range(rounds):
            rows = self.c.map()
            here = self.c.pos
            foes = [nb for nb in nav.neighbours(*here, len(rows), len(rows[0]))
                    if rows[nb[0]][nb[1]].isalpha()]
            if not foes:
                return
            self.c.send(f"walk {nav.direction(here, foes[0])}")
            self.c.collect(0.6)
            if self.c.pos != here:
                return            # it moved away and we stepped into its place

    def rest(self, hp, mhp, max_secs=180):
        """Rest ('R' toggles resting) until HP is back to 90%; give up if it keeps falling."""
        self.say(f"  resting (hp {hp}/{mhp})")
        start_hp, end = hp, time.time() + max_secs
        last_up, best = time.time(), hp
        self.c.send("custom R")
        while time.time() < end:
            self.c.collect(2.0)
            hp = self.c.status()["ind"]["hp"][0]
            if hp >= 0.9 * mhp:
                return
            if hp > best:
                best, last_up = hp, time.time()
            if hp < 0.3 * mhp and hp < start_hp:
                raise Danger(f"hp {hp}/{mhp} and falling -- something is attacking")
            if time.time() - last_up > 8:
                # Resting was interrupted (or never started): toggle it on again
                self.c.send("custom R")
                last_up = time.time()
        self.say(f"  still at hp {hp}/{mhp} after resting {max_secs}s")

    # --- one door -------------------------------------------------------

    def open_door(self, door, rows):
        """Go next to door and open it. Returns (kind, detail) where kind is
        shop | for_sale | locked | ejected | no_door | unreachable | none."""
        spots = nav.stand_spots(rows, door)
        if not spots:
            return "unreachable", None
        at = nav.goto(self.c, spots)
        if at is None and self.c.hits != self.hits_seen:
            self.upkeep()                 # interrupted by an attack: deal with it, try again
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
        rec = {"time": now(), "depth": self.depth, "world": list(self.world) if self.world else None,
               "level": wild.world_name(self.world) if self.world else None,
               "door_y": door[0], "door_x": door[1], "result": kind}
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
        self.say(f"{wild.world_name(self.world)} (depth {self.depth}): {len(doors)} house doors on the map")
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
            try:
                rec = self.visit(door, rows)
            except nav.Jumped as e:
                where = self.world
                self.upkeep()
                self.say(f"  door {door}: moved unexpectedly ({e})")
                if self.world != where:
                    raise            # a different level: let tour() re-plan
                rec = {"time": now(), "depth": self.depth, "world": list(self.world),
                       "level": wild.world_name(self.world), "door_y": door[0], "door_x": door[1],
                       "result": "none"}
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

    # --- the wilderness -------------------------------------------------

    def tour(self, targets, explore_secs, include_start=True, return_home=True, done=()):
        """Visit each target level (world coords), explore it, catalog it.
        Day or night -- at night the lantern shows the way and lit houses
        still show up at a distance."""
        self.upkeep()
        targets = list(targets)
        remaining = set(targets)
        if include_start:
            remaining.add(self.world)
        remaining -= set(done)
        boxed = {}
        if done:
            self.say("already done: " + ", ".join(wild.world_name(sq) for sq in sorted(done)))
        summary = {}
        while remaining:
            here = self.world
            try:
                if here == (0, 0):
                    self.restock()
                elif self.supplies()[0] <= 1 and self.supplies()[2] > 0:
                    self.say("  running out of food -- back to town to restock")
                    self.go_to((0, 0), [*targets, here])
                    continue
                if here in remaining:
                    self.say(f"== {wild.world_name(here)}")
                    if here != (0, 0):
                        wild.explore(self.c, explore_secs, say=self.say, check=self.upkeep)
                    for k, v in self.run().items():
                        summary[k] = summary.get(k, 0) + v
                    remaining.discard(here)
                    self.write({"time": now(), "depth": self.depth, "world": list(here),
                                "level": wild.world_name(here), "result": "level_done"})
                    continue
                route = wild.plan_tour(here, remaining, via=[*targets, *remaining])
                self.cross_to(route[1])
            except nav.Jumped as e:
                self.upkeep()
                self.say(f"  moved unexpectedly ({e}); now in {wild.world_name(self.world)} -- re-planning")
            except wild.Boxed as e:
                boxed[self.world] = boxed.get(self.world, 0) + 1
                if boxed[self.world] > 3:
                    raise Danger(f"repeatedly unable to move in {wild.world_name(self.world)}: {e}")
                self.say(f"  {e}; trying the arena way out")
                self.c.in_arena = True
                self.upkeep()
        if return_home:
            self.go_to((0, 0), targets)
        return summary

    def cross_to(self, sq):
        """Step into the neighbouring level sq."""
        here = self.world
        way = wild.step_dir(here, sq)
        self.say(f"  -> heading {way} to {wild.world_name(sq)}")
        depth = wild.cross(self.c, way)
        if depth is None:
            # Edge not reached yet: explore toward it and try once more
            wild.explore(self.c, 120, say=self.say, check=self.upkeep)
            depth = wild.cross(self.c, way)
        if depth is None:
            raise RuntimeError(f"could not leave {wild.world_name(here)} heading {way}")
        self.upkeep()
        if self.world != sq:
            self.say(f"  WARNING: arrived in {wild.world_name(self.world)}, expected {wild.world_name(sq)}")

    def go_to(self, sq, via):
        if self.world is None:
            self.upkeep()
        while self.world != sq:
            try:
                self.cross_to(wild.plan_tour(self.world, [sq], via=[*via, self.world])[1])
            except nav.Jumped:
                self.upkeep()


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
    ap.add_argument("--wilderness", action="store_true",
                    help="tour the 12 levels around town (2 out on the cardinals, 1 on the diagonals)")
    ap.add_argument("--explore-secs", type=float, default=480,
                    help="time limit for uncovering each wilderness level's map")
    ap.add_argument("--no-return", action="store_true", help="don't walk back to town at the end")
    ap.add_argument("--resume", action="store_true",
                    help="with --wilderness: skip levels that already have records in --out")
    ap.add_argument("--pktlog")
    ap.add_argument("--events", help="append every client event to this file (debug)")
    args = ap.parse_args()

    done = set()
    if args.resume and os.path.exists(args.out):
        with open(args.out) as f:
            done = {tuple(r["world"]) for r in map(json.loads, f) if r.get("result") == "level_done"}
    evlog = open(args.events, "a", buffering=1) if args.events else None
    client = MangClient(args.client, args.libdir, args.nick, args.passfile, args.host, args.port,
                        config=args.config, pktlog=args.pktlog, cwd=repo,
                        log=(lambda ev: evlog.write(json.dumps(ev) + "\n")) if evlog else None)
    try:
        client.wait_ready()
        with open(args.out, "a") as out:
            cat = Cataloger(client, out, examine=not args.no_examine, retries=args.retries,
                            retry_delay=args.retry_delay, nogo_file=args.out + ".nogo.json")
            if args.wilderness:
                summary = cat.tour(wild.DEFAULT_TARGETS, args.explore_secs, return_home=not args.no_return,
                                   done=done)
            else:
                summary = cat.run(args.max_doors, args.door)
        print(json.dumps({"summary": summary}), file=sys.stderr)
    except Danger as e:
        print(f"stopping: {e}", file=sys.stderr)
        sys.exit(2)
    except ClientExited as e:
        print(f"client exited: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        client.quit()
        if evlog:
            evlog.close()


if __name__ == "__main__":
    main()
