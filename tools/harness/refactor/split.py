"""E1 split helper: move methods and class constants of class Pilot (verbatim chunks: each statement with the blank
lines and comments above it) from pilot.py into a mixin class in a new module, and module-level statements of
pilot.py (MOVE_TOP) into that module's top level; pilot.py imports the module's names back. Used for step 4
(town.py, TownMixin) and step 5 (combat.py, CombatMixin); for the next step edit TARGET, MIXIN, MOVE, MOVE_TOP,
HEADER and BASES.

    python3 split.py PILOT_DIR            # writes PILOT_DIR/<TARGET>.py, rewrites PILOT_DIR/pilot.py

A name defined by more than one statement of the class (a property and its setter) moves only if all of them do.
"""
import ast
import os
import re
import sys
import textwrap

TARGET, MIXIN = "combat", "CombatMixin"
BASES = ("ReportMixin, GearMixin, ItemsMixin, TownMixin", "ReportMixin, GearMixin, ItemsMixin, TownMixin, CombatMixin")

# module-level statements of pilot.py that move to the top of TARGET (helpers and tables only the moved methods use)
MOVE_TOP = """
CURE_POTIONS HEALS choke_tier heal_of STATUS_CURES
""".split()

MOVE = """
ESCAPE_WHY log_escape
confusion_lock confusion_window
danger_why worst_3turns sim_loss dangers danger_text
reflexes ENGAGE_STEPS ENGAGE_GIVE_UP_S engage_tick count_escape emergency_loop hunt_ordered walk_away_ok phase_futile
escaping_to_stairs escape
watch_perception watch_band teleport_item STATUS_SPELLS kill_caster_step band_cost band_live watch_traps
watch_thieves watch_kills
watch_drainers watch_progress
ABILITY_FLAGS has_ability
group_danger ENERGY our_slowness group_tick stairs_beside_still still_fight_tick BUFF_MSGS buff_on
RULE_KINDS rules save_rules has_rule rule_tick
fear_cure hard_fight speed_start_tick berserk_tick status_tick unseen_tick sidestep retreat_step quiet_spot
seen_pos
flee_failed choke_tick watch_breeders use_stair_location watch_character
""".split()

HEADER = '''"""combat -- the Pilot's combat and survival side, as a mixin of Pilot (refactor-candidates E1; docs/pilot-combat.md):
the reflexes (reflexes, in priority order) and the emergency escape (escape, with its helpers emergency_loop,
phase_futile, escaping_to_stairs, kill_caster_step, teleport_item, use_stair_location, log_escape, count_escape),
what counts as dangerous (danger_why, worst_3turns, sim_loss, dangers, has_ability), the fight rules
(engage_tick, group_danger/group_tick, still_fight_tick, status_tick, unseen_tick, choke_tick with choke_tier,
confusion_lock/confusion_window, speed_start_tick, berserk_tick, hard_fight, fear_cure, buff_on, our_slowness), the
movement helpers (sidestep, retreat_step, quiet_spot), flee_failed, the Navigator's react rules (rules, rule_tick)
and the watches (watch_band/band_cost/band_live, watch_character, watch_drainers, watch_thieves, watch_traps,
watch_breeders, watch_kills, watch_perception, watch_progress). The Advisor's estimator mirrors escape, group_tick,
speed_start_tick, berserk_tick and fear_cure by name (Advisor/data/estimator/options_sim.py POLICY_VERSION): they
stay Pilot's, as every method here does -- they read and write the Pilot's state through self; pilot.py imports
this module's names back (P.heal_of, P.choke_tier, P.STATUS_CURES, ...).
"""
import collections
import json
import math
import os
import re

from common import TV_SCROLL, TV_POTION, TV_FOOD, TV_LITE, plural, one_of
from world import gnow, waited
from mover import direction, passable
from goals import (Wait, Goto, Explore, Dive, Search, Hunt, Recover, BandLeave, WalkAway, Flee, Recall,
                   Resurrect, RestGoal)
from town_goals import TownFarm, Shop


'''

CLASS_HEADER = f'''

class {MIXIN}:
    """Pilot's combat and survival methods (`class Pilot(ReportMixin, GearMixin, ItemsMixin, TownMixin,
    CombatMixin)`: every name stays on Pilot)."""
'''


def names_of(stmt):
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [stmt.name]
    if isinstance(stmt, ast.Assign):
        out = []
        for t in stmt.targets:
            out += [n.id for n in ast.walk(t) if isinstance(n, ast.Name)]
        return out
    if isinstance(stmt, ast.AnnAssign):
        return [stmt.target.id]
    return []


def chunks_of(body, first_start):
    """(start, end, names) per statement: from the line after the previous statement's end to this one's end
    (1-based, inclusive); the first starts at first_start."""
    prev_end = first_start - 1
    out = []
    for s in body:
        out.append((prev_end + 1, s.end_lineno, names_of(s)))
        prev_end = s.end_lineno
    return out


def pick(chunks, want, where):
    moved, seen = [], set()
    for a, b, ns in chunks:
        hit = [n for n in ns if n in want]
        if hit:
            if len(hit) != len(ns):
                sys.exit(f"{where}: partial statement {ns}")
            moved.append((a, b, ns))
            seen.update(ns)
    missing = set(want) - seen
    if missing:
        sys.exit(f"{where}: not found: {sorted(missing)}")
    # a moved name also defined by a statement that stays (a later one would have won)
    stay = {n for a, b, ns in chunks if (a, b, ns) not in moved for n in ns}
    split = seen & stay
    if split:
        sys.exit(f"{where}: defined both in moved and unmoved statements: {split}")
    return moved


def main(d):
    path = os.path.join(d, "pilot.py")
    src = open(path).read()
    lines = src.splitlines(keepends=True)
    tree = ast.parse(src)
    cls = next(s for s in tree.body if isinstance(s, ast.ClassDef) and s.name == "Pilot")
    moved = pick(chunks_of(cls.body, cls.body[0].lineno), MOVE, "class Pilot")
    top_i = tree.body.index(cls)
    top = pick(chunks_of(tree.body[1:top_i], tree.body[0].end_lineno + 1), MOVE_TOP, "pilot.py top level")
    drop = set()
    for a, b, ns in moved + top:
        drop.update(range(a, b + 1))
    top_src = "".join("".join(lines[a - 1:b]) for a, b, ns in top)
    body = "".join("".join(lines[a - 1:b]) for a, b, ns in moved)
    out = HEADER + top_src + CLASS_HEADER + body
    if not out.endswith("\n"):
        out += "\n"
    newp = "".join(l for i, l in enumerate(lines, 1) if i not in drop)
    old_hdr, new_hdr = f"class Pilot({BASES[0]}):", f"class Pilot({BASES[1]}):"
    assert newp.count(old_hdr) == 1
    newp = newp.replace(old_hdr, new_hdr)
    top_names = [n for *_, ns in top for n in ns]
    # import the mixin and the moved top-level names back, after the last mixin's import
    anchor = "from town import TownMixin                       # noqa: E402\n"
    assert newp.count(anchor) == 1
    newp = newp.replace(anchor, anchor + f"from {TARGET} import " + ", ".join([MIXIN] + top_names) + "   # noqa: E402\n")
    # names pilot.py imports and no longer uses itself (they moved out with their users): kept, in REEXPORTED, when a
    # tool reads them through the module (P.TV_FOOD in unit.py) or they are the moved top-level names (P.heal_of,
    # ...); otherwise dropped from the import (as step 4 dropped functools, bad_inscription, light_turns)
    def loads(t):
        return {n.id for n in ast.walk(t) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    def imported(t):
        out = []
        for s in t.body:
            if isinstance(s, (ast.Import, ast.ImportFrom)):
                out += [(a.asname or a.name).split(".")[0] for a in s.names]
        return out
    rest = ast.parse(newp)
    unused = [n for n in imported(rest) if n in loads(tree) and n not in loads(rest) and n != MIXIN]
    used_by_tools = set()
    tools = os.path.dirname(os.path.abspath(d))
    for root, _, fs in os.walk(tools):
        for f in fs:
            if f.endswith(".py") and "attic" not in root and os.path.join(root, f) != path:
                txt = open(os.path.join(root, f)).read()
                used_by_tools |= {n for n in unused if re.search(rf"\b(P|pilot)\.{n}\b", txt)}
    keep = [n for n in unused if n in used_by_tools or n in top_names]
    drop_names = [n for n in unused if n not in keep]
    for n in drop_names:
        st = next(x for x in rest.body if isinstance(x, (ast.Import, ast.ImportFrom)) and
                  n in [(a.asname or a.name).split(".")[0] for a in x.names])
        nl = newp.splitlines(keepends=True)
        a, b = st.lineno - 1, st.end_lineno
        txt = "".join(nl[a:b])
        if len(st.names) == 1:
            txt = ""
        else:
            txt2 = re.sub(rf"(?<=[(\s]){n}, ", "", txt, count=1)
            if txt2 == txt:
                txt2 = re.sub(rf", {n}\b", "", txt, count=1)
            assert txt2 != txt, (n, txt)
            txt = txt2
        newp = "".join(nl[:a]) + txt + "".join(nl[b:])
        rest = ast.parse(newp)
    if drop_names:
        print(f"dropped from pilot.py's imports (no longer used there, nor read as P.NAME by a tool): {' '.join(drop_names)}")
    if keep:
        old_re = newp[newp.index("REEXPORTED = ("):]
        old_re = old_re[:old_re.index(")\n") + 1]
        new_re = textwrap.fill(old_re[:-1].replace("\n", " ") + ", " + ", ".join(keep) + ")", width=120,
                               subsequent_indent=" " * 14, break_on_hyphens=False)
        print(f"added to REEXPORTED: {' '.join(keep)}")
        newp = newp.replace(old_re, new_re)
    open(os.path.join(d, f"{TARGET}.py"), "w").write(out)
    open(path, "w").write(newp)
    print(f"moved {len(top)} top-level statements: {' '.join(top_names)}")
    print(f"moved {len(moved)} class statements ({len(drop)} lines in all): {' '.join(n for *_, ns in moved for n in ns)}")
    print(f"pilot.py {len(lines)} -> {len(newp.splitlines())} lines; {TARGET}.py {len(out.splitlines())} lines")


if __name__ == "__main__":
    main(sys.argv[1])
