"""logs -- the observers' shared readers of the Pilot's run logs and the mission list, and their lists of the
Navigator's query commands (refactor-candidates D7).

    runs/missions.json                      load_missions(), find_mission(label), epoch(), mission_window(m)
    runs/pilot/<nick>/decisions.jsonl       decisions(nick, t0, t1, keep)   (records' "t")
    runs/pilot/<nick>/events.jsonl          events(nick, t0, t1, keep)      (records' "epoch")
    runs/pilot/<nick>/state.jsonl           states(nick, t0, t1, keep)      (records' "epoch")

and the one damage attribution (refactor-candidates D8, the Advisor's definition of 2026-11-01, version 2.44.0):
hp_drops(recs), attack(text), damage_rows(recs, msgs) and damage(nick, t0, t1), used by damage_mix.py (sums by
category over a depth band) and scorecard.py's damage_by_monster (sums by monster over the mission).

Readers are generators of parsed records whose time is a number in [t0, t1]; lines that don't parse are skipped.
KEEP(line) is an optional cheap test on the raw text line before it is parsed: the logs are big (events.jsonl
~300 MB), so callers that want a few kinds say so here. Used by scorecard.py, notes.py and damage_mix.py; the
query lists by scorecard.py and watch.py. Reads only; no side effects at import (the monster rulebook that splits
melee blows is read at the first damage_rows call).
"""
import bisect
import collections
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "runs"))
INF = float("inf")


# --- the Navigator's query commands ---------------------------------------------------------------------------
# Commands that only look or talk, as opposed to orders that change what the Pilot does. Both lists also hold
# names Navigators really typed that aren't commands (help, news, inventory...): they classify real attempts.
# The two uses need different sets, so there are two:
QUERY_CORE = {"status", "journal", "gate", "monster", "inventory", "complain", "drainers", "say", "note", "options",
              "flags", "view", "orders", "events", "attention", "news", "map", "pack", "equip", "mission"}
# The scorecard's (group E: report -> action latency, order report age): the Advisor's definition
# (memos/2026-10-23-scorecard.md, Advisor/data/scorecard/scorecard.py, checked by `scorecard.py --check`). `plan`
# counts as a query here even with arguments. Changing this set changes the cards.
QUERY_CMDS = QUERY_CORE | {"floor", "help", "plan", "dump", "quote"}
# The viewer's (watch.py hides these from its feed; `plan` with no arguments is hidden there too, `plan ARGS` shown
# as an order). Also hides the read-only checks the scorecard counts as actions (wait, prep, why, gear, gearcmp,
# debt, ...) and shows `help`.
NAV_QUERIES = QUERY_CORE | {"wait", "prep", "why", "gear", "gearcmp", "debt", "rule", "viewmap", "navview",
                            "goalstate", "commands"}


# --- missions ----------------------------------------------------------------------------------------------------
def epoch(s):
    """A missions.json time ("YYYY-MM-DD HH:MM", local) -> epoch seconds."""
    return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M"))


def load_missions():
    return json.load(open(os.path.join(RUNS, "missions.json")))


def find_mission(label):
    """The last runs/missions.json row with this label, or None."""
    ms = [m for m in load_missions() if m.get("label") == label]
    return ms[-1] if ms else None


def mission_window(m):
    """(t0, t1) of a missions.json row: its start to its end (minute resolution), or to now if it is running."""
    return epoch(m["start"]), epoch(m["end"]) if m.get("end") else time.time()


# --- run logs ----------------------------------------------------------------------------------------------------
def run_dir(nick):
    return os.path.join(RUNS, "pilot", nick)


def read_jsonl(path, t0=-INF, t1=INF, tkey="t", keep=None):
    """Parsed records of a JSON-lines log whose TKEY is a number in [t0, t1]; KEEP(line) pre-filters lines.
    (Text mode: scanning events.jsonl for substrings was ~4x faster than in binary mode; the logs are ASCII.)"""
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if keep is not None and not keep(line):
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t = d.get(tkey)
            if isinstance(t, (int, float)) and t0 <= t <= t1:
                yield d


def decisions(nick, t0=-INF, t1=INF, keep=None):
    """runs/pilot/NICK/decisions.jsonl records with t0 <= t <= t1."""
    return read_jsonl(os.path.join(run_dir(nick), "decisions.jsonl"), t0, t1, "t", keep)


def events(nick, t0=-INF, t1=INF, keep=None):
    """runs/pilot/NICK/events.jsonl records with t0 <= epoch <= t1 (events also carry "t", the client's clock)."""
    return read_jsonl(os.path.join(run_dir(nick), "events.jsonl"), t0, t1, "epoch", keep)


def states(nick, t0=-INF, t1=INF, keep=None):
    """runs/pilot/NICK/state.jsonl records (status, inven, map snapshots) with t0 <= epoch <= t1. Status records carry
    `ind` (the indicators: stat5 is CHR) and, since 2026-11-01, `aware` (the kinds the flavour table knows) in the
    first record after a start and whenever it changed."""
    return read_jsonl(os.path.join(run_dir(nick), "state.jsonl"), t0, t1, "epoch", keep)


# --- damage taken: one attribution (refactor-candidates D8; the Advisor's definition, memo 2026-11-01-d-merges) ---
# An HP drop is two consecutive records (with "hp" and "depth") less than 5 s apart with the same max HP (a max-HP
# change -- level-up, CON, Hero/Berserk -- isn't damage) and less HP in the second. Its HP is split evenly over the
# attack messages from 0.6 s (one game block, TICK_S 0.625) before its first record to 0.2 s after its last. Each
# message is classified and named once: melee by MELEE (the monster's blows split it: its share of HURT/SHATTER blows
# -> "hurt", which AC reduces twice -- hit chance and wounds, melee1.c --, the rest -> "melee_other"), ranged by
# RANGED + the element (a resist cuts it) or "other" (arrows, magic missiles), named by the monster when the message
# says "The X ..."; "It"/"Something" and the unnamed "You are hit by/enveloped/blasted/struck" -> "unseen". A drop
# with no attack message (poison, a cut, an unseen spell) -> category "other", monster "unattributed".
DROP_GAP_S, BEFORE_S, AFTER_S = 5.0, 0.6, 0.2
MELEE = re.compile(r"^(?:The (.+?)|It|Something) (hits|bites|claws|stings|touches|kicks|butts|crushes|engulfs|"
                   r"crawls on|spits on|gazes at|wails at|punches|grabs|drools on|releases spores|begs|insults|"
                   r"moans) you")
ELEMENTS = (("fire", r"fire|flames|burn"), ("cold", r"frost|cold|ice"), ("acid", r"acid"),
            ("elec", r"lightning|elec"), ("pois", r"poison|gas|stinking cloud"), ("lite", r"breathes light"),
            ("dark", r"darkness|breathes dark"), ("shard", r"shards"), ("nexus", r"nexus"), ("sound", r"sound"),
            ("nether", r"nether"), ("chaos", r"chaos"), ("disen", r"disenchant"))
RANGED = re.compile(r"^(?:(?:The (.+?)|It|Something) (?:breathes|casts|fires|hurls|spits)|You are hit by|"
                    r"You are enveloped|You are blasted|You are struck)")
MELEE_HURT_UNKNOWN = 0.7       # the HURT share of an unknown attacker's blows
Row = collections.namedtuple("Row", "t amount category monster depth drop")   # drop: the drop's index
_RACES = {}


def _races():
    """{monster name lower: glyphs Race} (the rulebook), read once."""
    if not _RACES:
        sys.path.insert(0, os.path.join(HERE, "..", "pilot"))
        import glyphs
        _RACES.update({r.name.lower(): r for r in glyphs.load_rulebook(glyphs.load_races()).values()})
    return _RACES


def attack(text):
    """An attack message on us -> (kind, monster): kind "melee" or an element or "other"; monster the name the
    message gives, or "unseen". None if it isn't an attack on us (or a status-only spell: no damage)."""
    m = MELEE.match(text)
    if m:
        return "melee", m.group(1) or "unseen"
    m = RANGED.match(text)
    if not m:
        return None
    if "fearful illusion" in text or "burning your eyes" in text or "confus" in text or "scare" in text:
        return None
    return next((el for el, pat in ELEMENTS if re.search(pat, text)), "other"), m.group(1) or "unseen"


def hp_drops(recs):
    """[(t first, t last, HP lost, depth of the last record)] from decision records in time order (those without an
    "hp" list or a "depth" are skipped, as damage_mix always did)."""
    out, last = [], None
    for r in recs:
        hp = r.get("hp")
        if not isinstance(hp, list) or len(hp) < 2 or "depth" not in r:
            continue
        cur = (r["t"], hp[0], hp[1], r.get("depth") or 0)
        if last and cur[2] == last[2] and cur[1] < last[1] and cur[0] - last[0] < DROP_GAP_S:
            out.append((last[0], cur[0], last[1] - cur[1], cur[3]))
        last = cur
    return out


def damage_rows(recs, msgs):
    """The HP lost in decision records RECS, attributed to the messages MSGS ([(epoch, text)], any order): Rows
    (t, amount, category, monster, depth, drop), one per (drop, message) -- a melee message gives two, its "hurt" and
    "melee_other" parts, when both are non-zero; a drop with no attack message one ("other", "unattributed"). The
    amounts of a drop's rows add up to its HP lost; depth is the drop's (dungeon level, ft/50)."""
    att = sorted((e, a) for e, txt in msgs for a in [attack(txt)] if a)
    times = [e for e, _ in att]
    races = _races() if any(a[0] == "melee" for _, a in att) else {}
    rows = []
    for n, (ta, tb, amt, depth) in enumerate(hp_drops(recs)):
        here = att[bisect.bisect_left(times, ta - BEFORE_S):bisect.bisect_right(times, tb + AFTER_S)]
        if not here:
            rows.append(Row(tb, amt, "other", "unattributed", depth, n))
            continue
        share = amt / len(here)
        for e, (kind, who) in here:
            if kind != "melee":
                rows.append(Row(e, share, kind, who, depth, n))
                continue
            r = races.get(who.lower())
            blows = [b.split(":") for b in (r.blows if r else [])]
            hurt = sum(1 for b in blows if len(b) > 1 and b[1] in ("HURT", "SHATTER")) / len(blows) if blows \
                else MELEE_HURT_UNKNOWN
            for cat, part in (("hurt", share * hurt), ("melee_other", share * (1 - hurt))):
                if part > 0:
                    rows.append(Row(e, part, cat, who, depth, n))
    return rows


def damage(nick, t0=-INF, t1=INF):
    """damage_rows for the HP drops in decisions.jsonl with t0 <= t <= t1, from the logs."""
    recs = decisions(nick, t0, t1, keep=lambda l: '"hp": [' in l and '"depth": ' in l)
    msgs = [(e["epoch"], e.get("text", "")) for e in events(
        nick, t0 - 1, t1 + 1, keep=lambda l: '"message"' in l[:30] and (
            "you" in l or "You" in l or "breathes" in l or "casts" in l or "fires" in l))]
    return damage_rows(recs, msgs)
