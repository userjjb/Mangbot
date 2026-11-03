"""Command-equivalence matrix (E2, the command table): the real Pilot on fake.py's client and clock, one fresh Pilot
per case; each case sends one request the way daemon.py's Handler does (onto `requests`, answered by
handle_requests) and then runs two ticks. Every command name the old dispatcher tested (`c == "..."`,
`c in (...)`, `c in self.ACTIONS` / `self.DUNGEON_ITEM_CMDS`, read from NAMES_DIR's source with ast) must have
argument variants below, and so must every entry of the new tree's cmdtable.COMMANDS (if it has one).

    PYTHONHASHSEED=0 python3 cmdmatrix.py PILOT_DIR NAMES_DIR OUT.json [CMD ...]

Cases: each command x its argument variants (valid, bad, missing) x 6 roles (navigator; architect with the token;
architect with a wrong token; architect with none; user; no role at all) x 5 contexts (town idle; town with the
Navigator's goal running; dungeon idle with a fresh report; dungeon with a trip plan, a monster in view and a report
from a level since left; a ghost). Recorded per case: the reply, the commands sent (by the request; by the two
ticks), the notices, the decisions.jsonl records, the run files written and the Pilot's and World's attributes that
changed -- times normalised (the fake clock moves 1e-4 s per time() call, so an extra call shifts them). Compare
two OUT files with cmpmatrix.py. Run from a copy next to a rundir_template/ (see fake.py)."""
import ast
import hashlib
import json
import os
import queue
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake  # noqa: E402
from fake import item, Clock  # noqa: E402

pilot_dir, names_dir, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2]), sys.argv[3]
only = sys.argv[4:]
P = fake.load(pilot_dir)
import world as W  # noqa: E402
import glyphs  # noqa: E402

TREE = os.path.dirname(os.path.dirname(pilot_dir))
T0 = 1793653200.0
TOKEN = "tok-e2"
G = glyphs.Glyphs()
GLYPH = {}
for k, v in G.by_glyph.items():
    GLYPH.setdefault(G.races[v].name, k)


# --- the command names the old dispatcher knew ---------------------------------------------------------------

def old_names(d):
    """Every string the old do_request compared `c` with (and ACTIONS' / DUNGEON_ITEM_CMDS' keys)."""
    names, consts = set(), {}
    for f in ("pilot.py", "commands.py"):
        p = os.path.join(d, f)
        if not os.path.exists(p):
            continue
        tree = ast.parse(open(p).read())
        for cls in [s for s in ast.walk(tree) if isinstance(s, ast.ClassDef)]:
            for s in cls.body:
                if isinstance(s, ast.Assign) and isinstance(s.targets[0], ast.Name) and \
                        s.targets[0].id in ("ACTIONS", "DUNGEON_ITEM_CMDS"):
                    consts[s.targets[0].id] = ast.literal_eval(s.value)
            for fn in cls.body:
                if not (isinstance(fn, ast.FunctionDef) and fn.name == "do_request"):
                    continue
                for n in ast.walk(fn):
                    if isinstance(n, ast.Compare) and isinstance(n.left, ast.Name) and n.left.id == "c":
                        for op, rhs in zip(n.ops, n.comparators):
                            if isinstance(rhs, ast.Constant) and isinstance(rhs.value, str):
                                names.add(rhs.value)
                            elif isinstance(rhs, (ast.Tuple, ast.Set, ast.List)):
                                names |= {e.value for e in rhs.elts if isinstance(e, ast.Constant)}
                            elif isinstance(rhs, ast.Attribute) and rhs.attr in ("ACTIONS", "DUNGEON_ITEM_CMDS"):
                                names.add("<" + rhs.attr + ">")
    for k in ("ACTIONS", "DUNGEON_ITEM_CMDS"):
        if "<" + k + ">" in names:
            names.discard("<" + k + ">")
            names |= set(consts[k])
    return names


# --- argument variants: valid, bad, missing (a third element: extra request fields) ------------------------------

ARGS = {
    "status": [[], ["full"], ([], {"since_wait": True})],
    "mission": [[], ["start", "m99", "navigator=opus", "effort=high"], ["end"], ["bogus"], ["end", "m98"]],
    "keep": [[], ["Ration"], ["-ration_of_food"]],
    "standing": [[], ["don't", "kill", "the", "jelly"], ["-1"], ["-9"]],
    "react": [[], ["leave", "Black_orc"], ["hunt", "Nosuch"], ["thieves", "kill"], ["bogus", "x"], ["-1"], ["clear"],
              ["afraid", "run"]],
    "review": [[], ["sell", "x"], ["wear"], ["keep", "Ring"]],
    "debt": [[]],
    "pack": [[]],
    "equip": [[]],
    "orders": [[]],
    "map": [[], ["5"], ["x"]],
    "view": [[], ["5", "20"], ["x"]],
    "navview": [[]],
    "avoid": [[], ["20,40"], ["20,40", "2"], ["Black_orc"], ["clear"]],
    "viewmap": [[], ["3", "5"]],
    "note": [["hello"], ["!wake", "up"], ["?a", "question"], []],
    "journal": [["a", "line"], []],
    "gate": [[], ["500"], ["500", "recall"], ["x"]],
    "complain": [[], ["the", "map", "lies"]],
    "say": [["hi"], []],
    "ask": [[], ["what", "now?"], ["quiet", "what", "now?"]],
    "answer": [[], ["1", "yes"], ["#2", "no"], ["x"]],
    "price": [[], ["a"], ["Phase"], ["zzz"]],
    "monster": [[], ["Black_orc"], ["zzz"]],
    "drainers": [[], ["STR"], ["CON", "20"]],
    "gear": [[]],
    "gearcmp": [[], ["k"], ["zzz"]],
    "house": [[], ["buy"], ["buy", "60,129"], ["deposit", "100"], ["withdraw"], ["bogus"]],
    "loadout": [[], ["shops"]],
    "why": [[], ["20:00"], ["bad"]],
    "prep": [[]],
    "goal": [[], ["goto", "20,41"], ["goto", ">"], ["fetch", "20,42"], ["fetch"], ["dive"], ["dive", "500", "force"],
             ["explore", "until=stairs"], ["explore", "radius=x"], ["hunt", "Black_orc"], ["hunt", "!Black_orc"],
             ["leave"], ["recall"], ["recall", "force"], ["rest"], ["wait", "3"], ["quiet"], ["quiet", "x"],
             ["search"], ["searchroom", "20,40"], ["searchroom"], ["shop", "5", "buy", "Phase_Door:3"], ["town"],
             ["townfarm"], ["townfarm", "100"], ["resurrect"], ["bogus"]],
    "plan": [[], ["town"], ["town", "kit=Z"], ["trip", "300-400"], ["trip", "300-400", "force"], ["trip", "x"],
             ["stop"], ["resume"], ["bogus"]],
    "stop": [[]],
    "order": [[], ["flee_hp=0.4"], ["flee_hp=x"], ["nokey=1"], ["flee_hp"], ["max_depth=2000"]],
    "wear": [[], ["k"], ["Free_Action"], ["Bloodstone"], ["Bloodstone", "force"], ["A"]],
    "takeoff": [["A"], ["b"], ["zzz"]],
    "quaff": [["Cure_Light_Wounds"], ["e"], ["zzz"]],
    "read": [["Phase_Door"], ["Word_of_Recall"], ["Word_of_Recall", "force"], ["Identify", "l"], ["l", "zz"],
             ["Phase_Door", "force"]],
    "eat": [["Ration_of_Food"], ["a"]],
    "fuel": [["Flask_of_oil"], ["b"]],
    "destroy": [["Junk"], ["!Free_Action"], ["Free_Action"], ["Cure_Light_Wounds", "2"], ["a", "all"], []],
    "drop": [["a"], ["!k", "all"]],
    "inspect": [["a"], ["zzz"]],
    "aim": [["Wand"], ["Wand", "4"]],
    "use": [["Staff"], ["Staff", "a"]],
    "zap": [["Rod"]],
    "wearall": [[]],
    "inscribe": [["a", "@R"], []],
    "search": [[], ["3"], ["x"]],
    "disarm": [[], ["2"]],
    "open": [["6"]],
    "pickup": [[]],
    "stairs": [[], [">"]],
    "option": [["a", "b"], []],
    "goalstate": [[]],
    "options": [[], ["auto"]],
    "dump": [[]],
    "raw": [["custom", "s"]],
    "attention": [[]],
    "quit": [[]],
    "park": [[]],
}
# names no dispatcher knows (and odd requests): the unknown-command path
UNKNOWN = {"help": [[]], "flags": [["x"]], "sell": [["a"]], "": [[]], None: [[]], "wait-attention": [[]],
           "STATUS": [[]], "goal ": [["dive"]]}
ODD = [("list-cmd", ["x"], [])]          # a non-string cmd (never from pilotctl)

ROLES = [("navigator", {"role": "navigator"}), ("architect", {"role": "architect", "token": TOKEN}),
         ("arch_badtoken", {"role": "architect", "token": "wrong"}), ("arch_notoken", {"role": "architect"}),
         ("user", {"role": "user"}), ("norole", {})]


# --- the world ---------------------------------------------------------------------------------------------------

def lantern(turns):
    return f"a Brass Lantern (with {turns} turns of light)"


def pack():
    rows = [("4 Rations of Food", 80, 4), ("3 Flasks of oil", 77, 3), ("5 Potions of Cure Critical Wounds", 75, 5),
            ("4 Potions of Cure Serious Wounds", 75, 4), ("5 Potions of Cure Light Wounds", 75, 5),
            ("3 Potions of Heroism", 75, 3), ("2 Potions of Speed", 75, 2), ("12 Scrolls of Phase Door", 70, 12),
            ("3 Scrolls of Word of Recall", 70, 3), ("a Staff of Teleportation (5 charges)", 55, 1),
            ("a Ring of Free Action", 45, 1), ("2 Scrolls of Identify", 70, 2), ("a Bloodstone Ring", 45, 1),
            ("a Wand of Stinking Cloud (8 charges)", 65, 1), ("a Rod of Treasure Location", 66, 1),
            ("a Potion of Junk", 75, 1)]
    return [item(i, n, tv, num) for i, (n, tv, num) in enumerate(rows)]


def worn():
    rows = [("a Scimitar of Westernesse (2d5) (+10,+12) [+0]", 23, 130), (lantern(9000), 39, 50),
            ("a Ring of Protection [+16]", 45, 1), ("an Amulet of Slow Digestion", 40, 3),
            ("Hard Studded Leather of Resistance (-1) [16,+12]", 37, 200), ("a Leather Shield [8,+5]", 34, 60),
            ("a Hard Leather Cap [2,+3]", 32, 15), ("a Set of Leather Gloves [1,+2]", 31, 10),
            ("a Pair of Leather Boots [2,+3]", 30, 20), ("a Cloak [1,+2]", 35, 10)]
    return [item(24 + i, n, tv, 1, wt, equip=True) for i, (n, tv, wt) in enumerate(rows)]


class Client(fake.FakeClient):
    ghost = False

    def status(self):
        st = super().status()
        st["ghost"] = self.ghost
        return st


TOWN = dict(depth=0, pos=(20, 40), stairs={(16, 45): ">"}, extra={(30, 60): "5", (30, 20): "1", (12, 70): "4",
                                                                    (27, 89): "8"}, room=(0, 0, 65, 197))
DUNGEON = dict(depth=6, pos=(20, 40), stairs={(10, 70): ">", (35, 10): "<"})


def reset_world_clock():
    t = Clock.t
    W._CLOCK.update(wall=t, game=t, factor=1.0, model=1.0, measured=0.0, fast_ok=False, rate=None)
    W._HIST.clear()
    W._HIST.append((t, t, 1.0))
    W._FUEL.clear()
    W._FROZEN.update(t=0.0, on=False)


def tick(p, c, n=1, dt=0.3):
    sent, errs = [], []
    for _ in range(n):
        c.sent = []
        try:
            p.tick()
        except Exception as e:
            errs.append(repr(e))
        sent += c.sent
        fake.advance(dt)
    return sent, errs


def arch(p, cmd, *args):
    q = queue.Queue()
    p.requests.put(({"cmd": cmd, "args": list(args), "role": "architect", "token": TOKEN}, q))
    p.handle_requests()
    return q.get_nowait()


def setup(ctx):
    """A fresh Pilot in context ctx, after a few ticks."""
    Clock.t = T0
    random.seed(12345)
    reset_world_clock()
    rundir = fake.fresh_rundir(os.path.join(fake.S, "cmrun", "runs", "pilot", "dive04"), True)
    kw = dict(TOWN if ctx.startswith("town") else DUNGEON)
    if ctx == "dungeon_busy":
        kw["monsters"] = [(20, 52, GLYPH["Black orc"])]
    c = Client(inven=pack() + worn(), **kw)
    p = P.Pilot(c, rundir)
    p.arch_token = TOKEN
    fake.no_shadow(p)
    tick(p, c, 3)
    if ctx == "town_goal":
        g = P.Wait(60)
        g.role, g.by_navigator = "navigator", True
        p.set_goal(g)
        tick(p, c, 2)
    elif ctx == "dungeon_idle":
        arch(p, "status")                 # (a fresh report: positional orders pass the stale check)
        p.report_state = dict(p.report_state)
    elif ctx == "dungeon_busy":
        arch(p, "plan", "trip", "300-350")
        tick(p, c, 3)
        arch(p, "status")
        p.report_state = dict(p.report_state, level_t=-1.0)    # (that report's level has since been left)
        fake.advance(10)
        tick(p, c, 1)
    elif ctx == "dead":
        c.ghost = True
        c.ind["hp"] = [0, 358]
        tick(p, c, 2)
    return p, c, rundir


CONTEXTS = ("town_idle", "town_goal", "dungeon_idle", "dungeon_busy", "dead")

TIME = re.compile(r"\b179365\d{4}(?:\.\d+)?\b")       # the fake clock's wall/game times (T0 +- ~1 hour)
HMS = re.compile(r"\b(?:20|21):\d\d:\d\d\b")


def norm(v):
    s = v if isinstance(v, str) else json.dumps(v, sort_keys=True, default=repr)
    s = re.sub(r" at 0x[0-9a-f]+", " at 0x?", s)
    s = s.replace(TREE, "<TREE>")
    s = TIME.sub("<T>", s)
    return s


def norm_rec(line):
    try:
        d = json.loads(line)
    except ValueError:
        return norm(line)
    d.pop("t", None)
    return norm(d)


def state(p):
    out = {}
    for pre, obj in (("p.", p), ("w.", p.w)):
        for k, v in vars(obj).items():
            if k in ("dlog", "requests", "att_cond", "c", "w"):
                continue
            try:
                r = norm(repr(v))
            except Exception as e:
                r = f"<repr failed {e!r}>"
            out[pre + k] = r
    return out


def files(rundir):
    base = os.path.dirname(os.path.dirname(rundir))
    res = {}
    for root, _, fs in os.walk(base):
        for f in sorted(fs):
            path = os.path.join(root, f)
            rel = os.path.relpath(path, base)
            if f == "decisions.jsonl" or f.endswith(".log"):
                continue
            try:
                res[rel] = norm(open(path).read())
            except UnicodeDecodeError:
                res[rel] = os.path.getsize(path)
    return res


def run_case(ctx, cmd, args, extra, role_fields):
    p, c, rundir = setup(ctx)
    before = state(p)
    files0 = files(rundir)
    nd = sum(1 for _ in open(os.path.join(rundir, "decisions.jsonl")))
    na, nn = len(p.attention), len(p.news)
    req = {"cmd": cmd, "args": list(args), **role_fields, **extra}
    if cmd is None:
        req.pop("cmd")
    q = queue.Queue()
    c.sent = []
    p.requests.put((req, q))
    try:
        p.handle_requests()
        err = None
    except Exception as e:                      # (handle_requests catches do_request's errors: this is its own)
        err = repr(e)
    sent_req = list(c.sent)
    try:
        reply = q.get_nowait()
    except queue.Empty:
        reply = "(no reply)"
    att_req = p.attention[na:]
    sent_ticks, tick_errs = tick(p, c, 2)
    after = state(p)
    p.dlog.close()
    recs = [norm_rec(l.rstrip("\n")) for l in list(open(os.path.join(rundir, "decisions.jsonl")))[nd:]]
    files1 = files(rundir)
    changed = {k: v[:400] + ("" if len(v) <= 400 else " #" + hashlib.md5(v.encode()).hexdigest()[:12])
               for k, v in after.items() if before.get(k) != v}
    return {"reply": norm(reply), "handle_error": err, "sent": sent_req, "sent_ticks": sent_ticks,
            "tick_errors": tick_errs, "attention_by_request": norm(att_req), "attention": norm(p.attention[na:]),
            "news": norm(p.news[nn:]), "decisions": recs,
            "files": {k: v for k, v in files1.items() if files0.get(k) != v},
            "goal": norm(p.goal.describe()) if p.goal else None, "goal_class": type(p.goal).__name__,
            "goal_role": getattr(p.goal, "role", None), "plan": norm(getattr(p.plan, "text", None)),
            "plan_paused": getattr(p.plan, "paused", None), "changed": changed}


def main():
    known = old_names(names_dir)
    missing = sorted(known - set(ARGS))
    extra_args = sorted(set(ARGS) - known)
    print(f"{len(known)} command names in {names_dir}'s dispatcher; without argument variants here: "
          f"{missing or 'none'}; variants for names it doesn't know: {extra_args or 'none'}")
    try:
        import cmdtable
        tab = set(cmdtable.COMMANDS)
        print(f"this tree's cmdtable: {len(tab)} commands; not in the old dispatcher: {sorted(tab - known) or 'none'}; "
              f"old names not in the table: {sorted(known - tab) or 'none'}")
        if tab != known:
            sys.exit("the table and the old dispatcher's names differ")
    except ImportError:
        print("this tree has no cmdtable (the old dispatcher)")
    if missing:
        sys.exit("give every command argument variants")
    cases = [(n, v) for n in ARGS for v in ARGS[n]] + [(n, v) for n in UNKNOWN for v in UNKNOWN[n]]
    cases = [(n, v[0], v[1]) if isinstance(v, tuple) else (n, v, {}) for n, v in cases]
    cases += [(cmd, a, {}) for _, cmd, a in ODD]
    if only:
        cases = [x for x in cases if str(x[0]) in only]
    res = {}
    for ctx in CONTEXTS:
        for cmd, args, extra in cases:
            for rname, rf in ROLES:
                key = f"{ctx} | {rname} | {json.dumps(cmd)} {json.dumps(args)}" + (f" {json.dumps(extra)}" if extra else "")
                res[key] = run_case(ctx, cmd, args, extra, rf)
        print(f"{ctx}: {len(cases) * len(ROLES)} cases", flush=True)
    json.dump(res, open(out, "w"), indent=0, sort_keys=True)
    print(f"{len(res)} cases ({len(cases)} requests x {len(ROLES)} roles x {len(CONTEXTS)} contexts) -> {out}")


main()
