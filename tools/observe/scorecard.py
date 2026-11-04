#!/usr/bin/env python3
"""scorecard -- one card per mission, from the Pilot's logs only, to the Advisor's
definitions (memos/2026-10-23-scorecard.md; reference: Advisor/data/scorecard/scorecard.py).

Missions are listed in runs/missions.json (`pilotctl mission start/end` keeps it).

    python3 scorecard.py m23                 # one card (rescored, its JSON rewritten)
    python3 scorecard.py --table m23         # its table row only (what wrap.sh uses)
    python3 scorecard.py --all [--table]     # rescore every real mission (+ the sp-* set pieces with --sp), then the table
    python3 scorecard.py                     # the table of the cards already written (read only, no rescoring)
    python3 scorecard.py --json m23          # the numbers
    python3 scorecard.py --check             # compare with the Advisor's baseline CSV

Eight groups: A outcome, B efficiency (with a 17-category time budget), C safety, D value
lost, E Navigator, F Pilot health, G tokens (the Navigator's cost, from tokens.py), H the
estimator in shadow mode; plus damage taken by monster. Figures that are estimates say so
(docs/observe.md has every field). Cards are also written to runs/pilot/NICK/scorecards/LABEL.json.

Since 2026-11-01 (2.44.0; the Advisor's memo 2026-11-01-d-merges): damage by monster is logs.damage_rows, the same
attribution as damage_mix.py (D8), and lost items are valued as the Pilot values them -- itemvalue.value x
shopmath.pay_cut -- with what it knew at the event (D9): the kinds known (state.jsonl's `aware`; today's
runs/flavours.json for older logs, said in the card header), the dungeon level, the CHR and the shop owners then.
Compare value numbers only between cards made with the same code.
"""
import argparse
import bisect
import collections
import csv
import json
import os
import re
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import logs  # noqa: E402  (the shared log readers and query-command lists)
import shopmath  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "pilot"))
import itemvalue  # noqa: E402  (the Pilot's item values: read only)

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RUNS = os.path.join(ROOT, "runs")
REPO = os.path.join(ROOT, "github")
ADVISOR = os.path.join(ROOT, "Advisor", "data", "scorecard")

ESCALATION = {"emergency", "emergency_loop", "fight_going_badly", "danger_seen", "unseen_attacker", "stat_drained",
              "band"}
CURE_RE = re.compile(r"Cure (Light|Serious|Critical) Wounds|Healing")
IRREPLACEABLE = re.compile(r"Free Action|See Invisible|of Seeing|Telepathy|Hold Life|of Speed|Resistance|"
                           r"Resist (Fire|Cold|Acid|Lightning|Poison)|Regeneration", re.I)
URGENT_WOR = re.compile(r"low hp|flee|danger|emergency|monsters close|phasing|group|last resort|potions too")
DEFS = "2026-11-01 (2.44.0)"     # the damage (D8) and value (D9) definitions' date, in every card's header


# --- the game's tables --------------------------------------------------------
def _player_exp():
    src = open(os.path.join(REPO, "src", "server", "tables.c")).read()
    body = src[src.index("s32b player_exp[PY_MAX_LEVEL]"):]
    body = body[body.index("{") + 1:body.index("};")]
    return [int(v) for v in re.findall(r"(\d+)L?", body)]


PLAYER_EXP = _player_exp()
EXPFACT = 110          # Half-Orc (p_race.txt X:10:110); the Advisor's normalisation


def exp_to_reach(clvl):
    return 0 if clvl <= 1 else PLAYER_EXP[clvl - 2] * EXPFACT // 100


# --- what the Pilot knew then (D9: a card values items as the Pilot did when it decided) -----------
# the store screens' names -> the Pilot's store numbers (Pilot.STORE_NUM; shopmath.BUYERS uses them)
STORE_NUM = {"General store": 1, "Armoury": 2, "Weapon Smith": 3, "Temple": 4, "Alchemist": 5, "Magic Shop": 6,
             "Black Market": 7, "General Store": 1, "Weaponsmith": 3, "Alchemy shop": 5, "Magic-User store": 6,
             "Black market": 7}
KIND_WORD = re.compile(r"^(Potion|Scroll|Ring|Amulet|Wand|Staff|Rod) of ")


class Then:
    """The Pilot's knowledge over time, rebuilt from its logs: CHR (state.jsonl status records' ind stat5), the kinds
    its flavour table knew (their `aware`, logged since 2026-11-01; before that, today's runs/flavours.json), and
    the shop owners last seen (the store screens in events.jsonl: what its stores_seen / stores.json held)."""
    _cache = {}

    @classmethod
    def of(cls, nick):
        if nick not in cls._cache:
            cls._cache[nick] = cls(nick)
        return cls._cache[nick]

    def __init__(self, nick):
        self.chr_t, self.chr_v, self.aware_t, self.aware_v = [], [], [], []
        for d in logs.states(nick, keep=lambda l: l.startswith('{"ev": "status"')):
            st5 = (d.get("ind") or {}).get("stat5")
            if st5:
                self.chr_t.append(d["epoch"])
                self.chr_v.append(st5[0])
            if isinstance(d.get("aware"), list):
                self.aware_t.append(d["epoch"])
                self.aware_v.append(set(d["aware"]))
        self.own = collections.defaultdict(lambda: ([], []))
        for d in logs.events(nick, keep=lambda l: l.startswith('{"ev": "store"')):
            num = STORE_NUM.get(d.get("name"))
            if num and d.get("owner"):
                self.own[num][0].append(d["epoch"])
                self.own[num][1].append(d["owner"])
        try:
            fl = json.load(open(os.path.join(RUNS, "flavours.json")))
        except (OSError, ValueError):
            fl = {}
        # (as Pilot.aware_kinds: the kind names, lower case, without the type word)
        self.today = {KIND_WORD.sub("", f.get("kind", "")).lower() for f in fl.values()}

    @staticmethod
    def _at(ts, vs, t):
        i = bisect.bisect_right(ts, t) - 1
        return vs[i] if i >= 0 else None

    def chr(self, t):
        return self._at(self.chr_t, self.chr_v, t)

    def aware(self, t):
        """(the kinds known at t, True if from the log; else today's list and False)."""
        a = self._at(self.aware_t, self.aware_v, t)
        return (a, True) if a is not None else (self.today, False)

    def owners(self, t):
        return {num: o for num, (ts, os_) in self.own.items() for o in [self._at(ts, os_, t)] if o}


class Valuer:
    """What a lost item was worth to the Pilot at the event: itemvalue.value(name, level, aware) x shopmath.pay_cut
    (tval, CHR, owners seen) x the count, as Pilot.iv and its pay cut value items (D9, 2026-11-01). The level is the
    dungeon level (ft/50) of the last decision record at or before the event; in town the deepest level of the mission
    so far, else 15 (the Pilot's 750 ft fallback). CHR from the state records, else the mission's last audit."""

    def __init__(self, then, recs, chr_fallback):
        self.then, self.chr_fallback = then, chr_fallback
        dr = [(d["t"], d.get("depth") or 0) for d in recs if "depth" in d]
        self.t = [t for t, _ in dr]
        deep, self.lv = 0, []
        for _, dp in dr:
            deep = max(deep, dp)
            self.lv.append(dp or deep or 15)
        self.used_today = self.used_logged = 0

    def __call__(self, name, t):
        i = bisect.bisect_right(self.t, t) - 1
        level = self.lv[i] if i >= 0 else 15
        aware, logged = self.then.aware(t)
        if logged:
            self.used_logged += 1
        else:
            self.used_today += 1
        it = itemvalue.value(name, level, aware)
        if not it.value:
            return 0
        chr_v = self.then.chr(t) or self.chr_fallback
        return round(it.value * shopmath.pay_cut(it.tval, chr_v, self.then.owners(t)) * max(1, it.count))

    def note(self):
        """How the kinds known were had, for the card header."""
        if not self.used_today:
            return "kinds known as logged" if self.used_logged else "kinds known: nothing to value"
        return "kinds known: today's runs/flavours.json (no `aware` in the log" + \
            (f" for {self.used_today} of {self.used_today + self.used_logged} items)" if self.used_logged else ")")


# --- loading ----------------------------------------------------------------------
def load(nick, t0, t1):
    """(decision records in [t0, t1], [(epoch, text)] of messages in [t0, t1], [(epoch, owner, [(name, price)])] of
    store listings in [t0, t1 + 60])."""
    recs = list(logs.decisions(nick, t0, t1))
    msgs, stores = [], []
    for d in logs.events(nick, t0, t1 + 60, keep=lambda l: '"epoch"' in l and ('"message"' in l or
                                                                                '"ev": "store"' in l)):
        e = d["epoch"]
        if d.get("ev") == "message" and e <= t1:
            msgs.append((e, d.get("text", "")))
        elif d.get("ev") == "store":
            stores.append((e, d.get("owner"), [(i.get("name", ""), i.get("price", 0)) for i in d.get("items", [])]))
    return recs, msgs, stores


def med(v):
    return round(statistics.median(v), 1) if v else None


def p90(v):
    v = sorted(v)
    return round(v[min(len(v) - 1, int(0.9 * len(v)))], 1) if v else None


def singular(t):
    return re.sub(r"\b(\w+?)(?:es|s)\b", r"\1", t)


def bare(name):
    n = re.sub(r"\s*\{[^}]*\}", "", name)
    return re.sub(r"^(an?|the|\d+) ", "", n.strip()).lower()


# --- the card -----------------------------------------------------------------------
# card() loads a mission's records once and asks one function per group for its part, in the card's key order
# (header, H, A, B, C, D, E, F, damage, alerts); G (tokens) is the mission's own `tokens`, in the header.
def card(m):
    nick = m["nick"]
    t0, t1 = logs.mission_window(m)       # (a running mission ends now)
    recs, msgs, stores = load(nick, t0, t1)
    att = [d for d in recs if d.get("kind") == "attention"]
    # (the trip plan's news, tagged source=plan since 2026-10-23, didn't wake the Navigator: counted
    # apart, the Advisor's veto-reason memo); deaths, emergencies and escalations come from acount (plan news excluded)
    acount = collections.Counter(d.get("what") for d in att if d.get("source") != "plan")
    plan_news = collections.Counter(d.get("what") for d in att if d.get("source") == "plan")
    aud = [d for d in recs if d.get("kind") == "audit_check"]
    c = {"label": m["label"], "nav_model": m.get("navigator"), "effort": m.get("effort"), "report": m.get("report"),
         "start": m["start"], "end": m.get("end") or "(running)", "minutes": round((t1 - t0) / 60, 1),
         "notes": m.get("notes", ""), "tokens": m.get("tokens"), "defs": DEFS}
    c["estimator"] = estimator_shadow(recs, att)
    c["A"] = outcome(acount, aud, recs)
    budget = time_budget(recs, msgs, t0, t1)
    c["B"] = efficiency(recs, aud, budget, c["A"].get("exp_gain", 0), t0, t1)
    gold_rates(c["A"], c["B"])
    c["C"] = safety(recs, msgs, att)
    c["D"], c["values_aware"] = value_lost(recs, msgs, stores, aud, Then.of(nick))
    c["E"] = navigator(recs, t1, c["minutes"])
    c["F"] = pilot_health(recs, aud, acount, budget, t0, t1)
    c.update(damage_taken(recs, msgs))
    c["alerts"] = dict(acount.most_common(12))
    c["plan_news"] = dict(plan_news.most_common(12))
    return c


def estimator_shadow(recs, att):
    """H. shadow mode (2026-10-25): the estimator's answers beside the rules' emergency decisions."""
    est = [d for d in recs if d.get("kind") == "estimator"]
    cmp_ = [d for d in est if d.get("agree") is not None and d.get("trigger") != "hard_fight"]
    h = {"n": len(est), "compared": len(cmp_), "agree": sum(1 for d in cmp_ if d["agree"]),
         "in_time_turn": sum(1 for d in est if d.get("in_time_turn")),
         "before_next_act": sum(1 for d in est if d.get("before_next_act")),
         "skipped": sum(1 for d in att if d.get("what") == "emergency" and d.get("shadow") == "skipped"),
         "compute_max_s": max((d.get("compute_s") or 0 for d in est), default=None),
         "disagreements": [(d.get("rules"), d.get("choice"), (d.get("why") or "")[:80])
                           for d in cmp_ if not d["agree"]][:8]}
    # (since session 6 the estimator also runs at the start of hard fights: counted apart)
    hf = [d for d in est if d.get("agree") is not None and d.get("trigger") == "hard_fight"]
    h.update(hard_n=sum(1 for d in est if d.get("trigger") == "hard_fight"), hard_compared=len(hf),
             hard_agree=sum(1 for d in hf if d["agree"]),
             hard_choices=dict(collections.Counter(d.get("choice") for d in hf if not d["agree"])))
    return h


def stash_credit(recs):
    """(stored_value, debits) in these records (2.50.0, the user: storing a find instead of selling it deflated the
    mission's gold): the values of the fresh finds stored (`stash_store` fresh), and the credited values of stored
    finds withdrawn and sold (`stash_credit_sold`), subtracted so a find isn't counted twice."""
    stored = sum(int(d.get("value") or 0) for d in recs if d.get("kind") == "stash_store" and d.get("fresh"))
    debits = sum(int(d.get("credited_value") or 0) for d in recs if d.get("kind") == "stash_credit_sold")
    return stored, debits


def gold_rates(A, B):
    """B's gold change per dungeon minute, raw and adjusted (A's gold_change and gold_change_adj; 2.50.0). The table's
    $/dm stays gold_found_per_dmin (gold picked up in the dungeon: no sales, so storing doesn't move it); adj$/dm is the
    adjusted change."""
    dmin = B.get("dungeon_min")
    B["gold_change_per_dmin"] = round(A["gold_change"] / dmin, 1) if dmin and "gold_change" in A else None
    B["gold_change_adj_per_dmin"] = round(A["gold_change_adj"] / dmin, 1) if dmin and "gold_change_adj" in A else None


def outcome(acount, aud, recs=()):
    """A. deaths; from the first and last audits: clvl, exp gained, gold (house-held), the deepest audit; the stash's
    credit (2.50.0): stored_value, stash_debits and gold_change_adj = gold_change + stored_value - stash_debits."""
    a_ = {"deaths": acount.get("dead", 0)}
    if aud:
        a, b = aud[0], aud[-1]
        # (gold counts what the house holds: a deposit isn't a loss -- the gold bank, session 9)
        ga, gb = ((x.get("gold") or 0) + (x.get("banked") or 0) for x in (a, b))
        a_.update(clvl=[a.get("clvl"), b.get("clvl")], exp_gain=(b.get("exp") or [0])[0] - (a.get("exp") or [0])[0],
                  gold=[ga, gb], gold_change=gb - ga,
                  max_depth_ft=max(d.get("depth_ft") or 0 for d in aud))
        stored, debits = stash_credit(recs)
        a_.update(stored_value=stored, stash_debits=debits, gold_change_adj=gb - ga + stored - debits)
    return a_


def efficiency(recs, aud, budget, exp_gain, t0, t1):
    """B. dungeon and town minutes, exp, levels and gold found per dungeon time, the time budget, Navigator-wait."""
    dung = town = 0.0
    for p, q in zip(recs, recs[1:]):
        dt = q["t"] - p["t"]
        if dt > 60:
            continue
        if (p.get("depth") or 0) > 0:
            dung += dt
        else:
            town += dt
    dmin = dung / 60
    lv = gold_found = 0.0
    for p, q in zip(aud, aud[1:]):
        de = (q.get("exp") or [0])[0] - (p.get("exp") or [0])[0]
        cl = p.get("clvl") or 1
        if de > 0:
            lv += de / max(1, exp_to_reach(cl + 1) - exp_to_reach(cl))
        if (q.get("depth_ft") or 0) > 0 and (q.get("gold") or 0) > (p.get("gold") or 0):
            gold_found += q["gold"] - p["gold"]
    return {"dungeon_min": round(dmin, 1), "town_min": round(town / 60, 1),
            "exp_per_dmin": round(exp_gain / dmin, 1) if dmin else None,
            "levels_per_dhour": round(lv / (dung / 3600), 2) if dung else None,
            "gold_found": int(gold_found), "gold_found_per_dmin": round(gold_found / dmin, 1) if dmin else None,
            "time_budget_min": {k: round(v / 60, 1) for k, v in sorted(budget.items(), key=lambda kv: -kv[1])},
            "navigator_wait_pct": round(100 * (budget.get("no_goal_dungeon", 0) + budget.get("town_no_goal", 0))
                                        / max(1, t1 - t0))}


def safety(recs, msgs, att):
    """C. the lowest HP, close and near calls, emergency episodes, escapes and cures, recalls landed."""
    hp = [(d["t"], d["hp"][0] / d["hp"][1], d["hp"][0], d["hp"][1]) for d in recs
          if isinstance(d.get("hp"), list) and len(d["hp"]) > 1 and d["hp"][1] >= 20 and d["hp"][0] > 0]

    def episodes(lo, hi, gap=60):
        n, last = 0, -1e9
        for t, f, *_ in hp:
            if lo <= f < hi:
                if t - last > gap:
                    n += 1
                last = t
        return n
    low = min(hp, key=lambda h: h[1]) if hp else None
    em = sorted(d["t"] for d in att if d.get("what") in ("emergency", "emergency_loop"))
    em_ep = sum(1 for i, t in enumerate(em) if i == 0 or t - em[i - 1] > 30)
    esc = collections.Counter()
    esc_t = [d["t"] for d in att if d.get("what") in ESCALATION]
    goal_now = None
    for d in recs:
        if d.get("kind") == "goal":
            goal_now = str(d.get("goal") or "")
        if d.get("kind") != "act":
            continue
        cmd, why = str(d.get("cmd", "")), str(d.get("why", ""))
        lw = why.lower()
        deep = (d.get("depth") or 0) > 0
        if cmd.startswith("custom r"):
            if "phase door" in lw:
                esc["phase"] += 1
            elif "recall" in lw:
                hpf = d["hp"][0] / d["hp"][1] if isinstance(d.get("hp"), list) and d["hp"][1] else 1
                urgent = URGENT_WOR.search(lw) or any(0 <= d["t"] - t <= 45 for t in esc_t) or hpf < 0.5
                esc["wor_escape" if urgent and deep else "wor_travel"] += 1
            elif "teleport" in lw:
                esc["teleport"] += 1
        elif re.match(r"custom [<>]$", cmd) and goal_now and goal_now.startswith(("flee", "recover")):
            esc["stairs_flee"] += 1
        if cmd.startswith("custom q") and CURE_RE.search(why):
            esc["cures"] += 1
    return {"lowest_hp": [low[2], low[3], round(100 * low[1]), time.strftime("%H:%M:%S", time.localtime(low[0]))]
            if low else None,
            "close_calls_lt40": episodes(0, 0.40), "near_calls_40_50": episodes(0.40, 0.50),
            "emergency_episodes": em_ep, "emergency_alerts": len(em),
            "phase": esc["phase"], "wor_escape": esc["wor_escape"], "wor_travel": esc["wor_travel"],
            "stairs_flee": esc["stairs_flee"], "teleport": esc["teleport"], "cures_quaffed": esc["cures"],
            "escape_records": sum(1 for d in recs if d.get("kind") == "escape") or None,
            "recalls_landed": sum(1 for _, t in msgs if "yanked" in t)}


def navigator(recs, t1, minutes):
    """E. reports and commands, report-to-action latency, silent reports, replies to the user, overrides, complaints,
    report size and the orders' report age. `minutes` is the card's (rounded) mission length."""
    nc = [d for d in recs if d.get("kind") == "nav_cmd"]
    reports = [d["t"] for d in nc if d.get("wait_report")]
    cmds = [(d["t"], d.get("cmd"), d.get("args") or []) for d in nc if not d.get("wait_report")]
    acts = [t for t, cm, _ in cmds if cm not in logs.QUERY_CMDS]
    lat, silent = [], 0
    for i, r in enumerate(reports):
        nxt = reports[i + 1] if i + 1 < len(reports) else t1
        ia = [t for t in acts if r < t < nxt]
        if ia:
            lat.append(ia[0] - r)
        elif not any(r < t < nxt for t, _, _ in cmds):
            silent += 1
    users = sorted(d["t"] for d in recs if d.get("kind") == "user_note" and str(d.get("note", "")).startswith("!"))
    says = sorted(d["t"] for d in recs if d.get("kind") == "nav_say")
    rep = [says[j] - u for u in users for j in [bisect.bisect_right(says, u)] if j < len(says) and says[j] - u < 300]
    ages = [d["report_age"] for d in nc if d.get("report_age") is not None and d.get("cmd") not in logs.QUERY_CMDS]
    reps = [d for d in recs if d.get("kind") == "report"]
    return {"reports": len(reports), "commands": len(cmds), "commands_per_min": round(len(cmds) / max(1, minutes), 1),
            "report_to_action_med_s": med(lat), "report_to_action_p90_s": p90(lat),
            "reports_without_command_pct": round(100 * silent / len(reports)) if reports else None,
            "user_messages": len(users), "user_reply_med_s": med(rep),
            "forced_overrides": sum(1 for _, _, args in cmds for s in args if isinstance(s, str) and "!" in s[:2]),
            "complaints": sum(1 for d in recs if d.get("kind") == "nav_complaint"),
            "report_chars": sum(d.get("chars", 0) for d in reps) or None,
            "order_report_age_med_s": med(ages), "order_report_age_p90_s": p90(ages)}


def pilot_health(recs, aud, acount, budget, t0, t1):
    """F. audit differences, perception gaps, failed goals, stuck, runs sent, time the Pilot was down, server
    crashes."""
    gaps = [q["t"] - p["t"] for p, q in zip(recs, recs[1:]) if q["t"] - p["t"] > 45]
    moves = [d for d in recs if d.get("kind") == "move"]
    return {"audit_diffs": sum(d.get("differences") or 0 for d in aud), "audit_checks": len(aud),
            "perception_gaps": sum(1 for d in recs if d.get("kind") == "perception_gap"),
            "goal_failed": acount.get("goal_failed", 0), "stuck": acount.get("stuck", 0),
            "stuck_looping_min": round(budget.get("stuck_looping", 0) / 60, 1),
            "runs_sent": sum(1 for d in moves if d.get("run")),
            "pilot_down_min": round(sum(gaps) / 60, 1), "server_crashes": len(server_crashes(t0, t1))}


def damage_taken(recs, msgs):
    """damage taken, by monster: logs.damage_rows (D8, damage_mix's attribution) summed over the mission; the top 8
    named attackers plus `unseen` and `unattributed`, and all the HP lost. ({damage_by_monster, damage_hp_lost})"""
    dmg = collections.Counter()
    for r in logs.damage_rows(recs, msgs):
        dmg[r.monster] += r.amount
    unnamed = ("unseen", "unattributed")
    return {"damage_by_monster": {k: round(v) for k, v in [kv for kv in dmg.most_common() if kv[0] not in unnamed][:8]
                                  + [(k, dmg[k]) for k in unnamed if k in dmg]},
            "damage_hp_lost": round(sum(dmg.values()))}


def time_budget(recs, msgs, t0, t1):
    """Seconds per category, each second once (the Advisor's T1 rules; the fighting
    window is fixed at 5 s)."""
    pts = sorted(recs, key=lambda d: d["t"])
    times = [d["t"] for d in pts]
    combat = sorted(e for e, t in msgs if re.match(r"You (hit|miss|have slain|have killed|smite)|The .+ (hits|bites|"
                                                   r"claws|misses|touches|stings|crushes) you", t))
    yanked = sorted(e for e, t in msgs if "yanked" in t)
    goal, goals, resting = None, [], []
    rest_on = None
    em, phase_t, wor_t = [], [], []
    for d in pts:
        k = d.get("kind")
        if k == "goal":
            goal = str(d.get("goal") or "")
        elif k == "attention" and d.get("what") in ("goal_done", "goal_failed", "dead"):
            goal = None
        elif k == "attention" and d.get("what") in ("emergency", "emergency_loop"):
            em.append(d["t"])
        elif k == "act":
            cmd, why = str(d.get("cmd", "")), str(d.get("why", "")).lower()
            if cmd == "rest":
                rest_on = d["t"]
            elif rest_on is not None:
                resting.append((rest_on, d["t"]))
                rest_on = None
            if cmd.startswith("custom r") and "phase door" in why:
                phase_t.append(d["t"])
            if cmd.startswith("custom r") and "recall" in why and (d.get("depth") or 0) > 0 and URGENT_WOR.search(why):
                wor_t.append(d["t"])
        elif k == "move" and rest_on is not None:
            resting.append((rest_on, d["t"]))
            rest_on = None
        goals.append(goal)
    if rest_on is not None:
        resting.append((rest_on, t1))
    last_goal_t = max((pts[i]["t"] for i, g in enumerate(goals) if g), default=t0)
    pos_t = [d["t"] for d in pts if d.get("pos")]
    pos_v = [tuple(d["pos"]) for d in pts if d.get("pos")]
    rest_s = [a for a, _ in resting]

    def recent(ts, s, w):
        j = bisect.bisect_right(ts, s)
        return j > 0 and s - ts[j - 1] <= w

    def resting_at(s):
        j = bisect.bisect_right(rest_s, s) - 1
        return j >= 0 and resting[j][0] <= s <= resting[j][1]

    def wor_open(s):
        j = bisect.bisect_right(wor_t, s) - 1
        if j < 0:
            return False
        k = bisect.bisect_left(yanked, wor_t[j])
        return not (k < len(yanked) and yanked[k] <= s) and s - wor_t[j] < 40

    def still_20(s):
        j = bisect.bisect_right(pos_t, s) - 1
        if j < 0:
            return False
        k = bisect.bisect_left(pos_t, s - 20)
        return pos_t[j] - pos_t[k] >= 15 and len(set(pos_v[k:j + 1])) == 1

    out = collections.Counter()
    for s in range(int(t0), int(t1)):
        i = bisect.bisect_right(times, s) - 1
        if i < 0:
            continue
        nxt = times[i + 1] if i + 1 < len(times) else t1
        if nxt - times[i] > 45:
            out["pilot_down"] += 1
            continue
        d, g = pts[i], goals[i] or ""
        if (d.get("depth") or 0) > 0:
            if g.startswith("flee") or recent(em, s, 10) or recent(phase_t, s, 5) or wor_open(s):
                cat = "escaping"
            elif recent(combat, s, 5) or g.startswith("hunt"):
                cat = "fighting"
            elif resting_at(s):
                cat = "resting"
            elif g.startswith(("search", "searchroom")):
                cat = "searching_doors"
            elif g and not g.startswith(("rest", "wait", "recall")) and still_20(s):
                cat = "stuck_looping"
            elif g.startswith("recall"):
                cat = "recall_wait"
            elif g.startswith("dive"):
                cat = "travel_dive"
            elif g.startswith("goto"):
                cat = "travel_goto"
            elif g.startswith("explore"):
                cat = "exploring"
            elif g:
                cat = "dungeon_other"
            else:
                cat = "no_goal_dungeon"
        else:
            if resting_at(s):
                cat = "resting"
            elif g.startswith("shop"):
                cat = "town_shopping"
            elif g.startswith("townfarm"):
                cat = "town_farming"
            elif g.startswith("recall"):
                cat = "recall_wait"
            elif g:
                cat = "town_other"
            else:
                cat = "town_idle_end" if s > last_goal_t else "town_no_goal"
        out[cat] += 1
    return out


def value_lost(recs, msgs, stores, aud, then):
    """(gold-equivalent losses by category (the Advisor's §3), how the kinds known were had). Sales: fair pay = the
    shop's re-listing x buy/sell adjust (shopmath, exact from the source); other items: what the Pilot valued them at
    then (Valuer: itemvalue x pay cut, D9; an estimate, flagged ~)."""
    chr_v = 3
    if aud and aud[-1].get("stats"):
        chr_v = (aud[-1]["stats"].get("CHR") or [3])[0]
    worth = Valuer(then, recs, chr_v)
    sale_recs = [d for d in recs if d.get("kind") == "sale"]
    forced_t = [d["t"] for d in recs if d.get("kind") == "nav_cmd" and d.get("cmd") == "goal" and
                (d.get("args") or [None])[0] == "shop" and any("!" in str(a) for a in d.get("args", []))]
    sales = []
    if sale_recs:
        for d in sale_recs:
            sales.append({"item": d.get("sold_as"), "received": d.get("received"),
                          "fair": shopmath.fair_pay(d.get("relist"), d.get("owner"), chr_v),
                          "forced": bool(d.get("forced"))})
    else:
        for e, t in msgs:
            mm = re.match(r"You sold (.+?) for (\d+) gold", t)
            if not mm:
                continue
            # the listing right after the sale (one comes 0.5 s before it, without the item);
            # names compared singular and without counts: a potion merges into a stack
            key = singular(bare(mm.group(1)))
            st = next(((o, items) for te, o, items in stores if e - 0.1 <= te <= e + 8
                       and any(singular(bare(n)) == key for n, _ in items)), None)
            relist = next((p for n, p in st[1] if singular(bare(n)) == key), None) if st else None
            sales.append({"item": mm.group(1), "received": int(mm.group(2)),
                          "fair": shopmath.fair_pay(relist, st[0], chr_v) if st else None,
                          "forced": any(0 <= e - f <= 60 for f in forced_t)})
    short = [dict(s, shortfall=s["fair"] - s["received"]) for s in sales
             if s["fair"] is not None and s["fair"] > s["received"] + 1]
    # (each lost item with its time, to value it as of then)
    destroyed_t = [(e, mm.group(1)) for e, t in msgs for mm in [re.match(r"You destroy (.+?)\.$", t)] if mm]
    by_monster_t = [(e, mm.group(1)) for e, t in msgs for mm in [re.match(r"(?:One of your |Your )(.+?) (?:\([a-w]\) )?"
                                                                          r"was destroyed!", t)] if mm]
    stolen_gold = sum(int(mm.group(1)) for _, t in msgs for mm in [re.match(r"(\d+) coins were stolen", t)] if mm)
    stolen_t = [(e, mm.group(1)) for e, t in msgs for mm in [re.match(r"(?:One of your |Your )(.+?) (?:\([a-w]\) )?"
                                                                      r"was stolen", t)] if mm]
    left_t = [(d["t"], i) for d in recs if d.get("kind") == "left_behind" for i in d.get("items", [])]
    left_t += [(d["t"], re.sub(r"^left (.+?) \(pack.*", r"\1", str(d.get("detail")))) for d in recs
               if d.get("kind") == "attention" and d.get("what") == "tactic" and str(d.get("detail", "")).startswith("left ")]
    # items an interesting_item alert named that never came into the pack (for missions
    # before the left_behind records; the Clerks also used the journal)
    if not any(d.get("kind") == "left_behind" for d in recs):
        got = " ".join(t for _, t in msgs if t.startswith("You have "))
        for d in recs:
            if d.get("kind") == "attention" and d.get("what") == "interesting_item":
                nm = re.sub(r" seen on this level.*", "", str(d.get("detail", "")))
                if nm and singular(bare(nm)) not in singular(got.lower()):
                    left_t.append((d["t"], nm))
    destroyed, by_monster, stolen_items, left = ([n for _, n in x] for x in (destroyed_t, by_monster_t, stolen_t, left_t))
    irreplaceable = sorted({n for n in [s["item"] or "" for s in sales] + destroyed + stolen_items + left
                            if IRREPLACEABLE.search(n)})
    v = {"sale_shortfall": sum(s["shortfall"] for s in short),
         "sale_shortfall_forced": sum(s["shortfall"] for s in short if s["forced"]),
         "destroyed_est": sum(worth(n, t) for t, n in destroyed_t),
         "loot_abandoned_est": sum(worth(n, t) for t, n in left_t),
         "stolen": stolen_gold + sum(worth(n, t) for t, n in stolen_t),
         "destroyed_by_monsters_est": sum(worth(n, t) for t, n in by_monster_t)}
    v["total"] = sum(v[k] for k in ("sale_shortfall", "destroyed_est", "loot_abandoned_est", "stolen",
                                    "destroyed_by_monsters_est"))
    v.update({"sales": len(sales), "sales_valued": sum(1 for s in sales if s["fair"] is not None),
              "worst_sales": sorted(({"item": s["item"], "got": s["received"], "fair": s["fair"], "forced": s["forced"]}
                                     for s in short), key=lambda s: s["got"] - s["fair"])[:5],
              "left_behind": left[:10], "irreplaceable": irreplaceable})
    return v, worth.note()


def server_crashes(t0, t1):
    path = os.path.join(ROOT, "testserver", "gdb_run.log")
    out, last = [], None
    if not os.path.exists(path):
        return out
    for line in open(path, errors="replace"):
        m = re.match(r"(\d{6}) (\d{6}) ", line)
        if m:
            try:
                last = time.mktime(time.strptime(m.group(1) + m.group(2), "%d%m%y%H%M%S"))
            except ValueError:
                pass
        elif "SIGSEGV" in line and last and t0 <= last <= t1:
            out.append(last)
    return out


# --- output -------------------------------------------------------------------------
def show(c):
    A, B, C, D, E, F = (c.get(k, {}) for k in "ABCDEF")
    tb = ", ".join(f"{k} {v}" for k, v in list(B["time_budget_min"].items())[:8])
    lo = C.get("lowest_hp")
    out = [f"=== {c['label']}  {c['start']} - {c['end'][-5:]}  ({c['minutes']} min)  Navigator {c['nav_model']}"
           + (f" ({c['effort']})" if c.get("effort") else "") + f", {c['report']} report",
           (f"  (damage D8 and item values D9 as of {c['defs']}; item values with {c.get('values_aware')})"
            if c.get("defs") else None),
           f"  {c['notes']}" if c["notes"] else None,
           (f"  A outcome    clvl {A['clvl']}, exp +{A['exp_gain']}, gold {A['gold']} ({A['gold_change']:+d}"
            + (f"; {A['gold_change_adj']:+d} with {A['stored_value']} stored, {A['stash_debits']} debited"
               if A.get("stored_value") or A.get("stash_debits") else "") + "), "
            f"deepest {A['max_depth_ft']} ft, deaths {A['deaths']}") if "clvl" in A else "  A outcome    -",
           f"  B efficiency {B['dungeon_min']} dungeon min; {B['exp_per_dmin']} exp/dmin; {B['levels_per_dhour']} "
           f"levels/dungeon h; gold found {B['gold_found']} ({B['gold_found_per_dmin']}/dmin); Navigator-wait "
           f"{B['navigator_wait_pct']}%",
           f"               time (min): {tb}",
           (f"  C safety     lowest HP {lo[0]}/{lo[1]} ({lo[2]}%) at {lo[3]}; close calls {C['close_calls_lt40']}, "
            f"near {C['near_calls_40_50']}; emergency episodes {C['emergency_episodes']}; Phase {C['phase']}, WoR "
            f"escape {C['wor_escape']}, WoR travel {C['wor_travel']}, stairs flee {C['stairs_flee']}, teleport "
            f"{C['teleport']}; cures {C['cures_quaffed']}") if lo else "  C safety     -",
           f"  D value lost {D['total']} (sale shortfall {D['sale_shortfall']}, forced {D['sale_shortfall_forced']}; "
           f"destroyed ~{D['destroyed_est']}; abandoned ~{D['loot_abandoned_est']}; stolen {D['stolen']}; by monsters "
           f"~{D['destroyed_by_monsters_est']})  [{D['sales_valued']}/{D['sales']} sales valued; ~ = itemvalue x pay cut, as of then]",
           ("               IRREPLACEABLE: " + ", ".join(D["irreplaceable"])) if D["irreplaceable"] else None,
           ("               worst sales: " + "; ".join(f"{s['item']} {s['got']} vs fair {s['fair']}"
                                                     + (" (forced)" if s["forced"] else "") for s in D["worst_sales"][:3]))
           if D["worst_sales"] else None,
           f"  E navigator  {E['reports']} reports, {E['commands']} commands ({E['commands_per_min']}/min); "
           f"report->action {E['report_to_action_med_s']} s (p90 {E['report_to_action_p90_s']}); "
           f"{E['reports_without_command_pct']}% reports without a command; user msgs {E['user_messages']}, reply "
           f"{E['user_reply_med_s']} s; forced {E['forced_overrides']}; complaints {E['complaints']}"
           + (f"; {E['report_chars']} report chars; orders {E['order_report_age_med_s']} s after their report"
              if E.get("report_chars") else ""),
           f"  F pilot      audit {F['audit_diffs']}/{F['audit_checks']}; goal_failed {F['goal_failed']}, stuck "
           f"{F['stuck']}, no-movement {F['stuck_looping_min']} min; runs {F['runs_sent']}; down {F['pilot_down_min']} "
           f"min; server crashes {F['server_crashes']}",
           "  damage by    " + (", ".join(f"{k} {v}" for k, v in c["damage_by_monster"].items()) or "-")
           + (f" (of {c['damage_hp_lost']} HP lost)" if c.get("damage_hp_lost") else ""),
           (lambda e: f"  H estimator  shadow: {e['n']} estimates ({e['skipped']} skipped while busy), {e['agree']}/"
                      f"{e['compared']} agree with the rules; in time: {e['in_time_turn']} within a turn, "
                      f"{e['before_next_act']} before the next action; slowest {e['compute_max_s']} s"
                      + (f"; hard-fight starts {e['hard_agree']}/{e['hard_compared']} agree"
                         + (f" (else {e['hard_choices']})" if e.get("hard_choices") else "") if e.get("hard_n") else "")
                      + ("; disagreed: " + "; ".join(f"{a} -> {b} ({w})" for a, b, w in e["disagreements"][:3])
                         if e["disagreements"] else "") if e and e["n"] else None)(c.get("estimator")),
           (lambda t: f"  G tokens     Navigator {t['turns']} turns; output {t['output'] if t['output'] is not None else 'not logged'}, cache read {t['cache_read']}, "
                      f"cache write {t['cache_write']}, input {t['input']}; ${t.get('usd')} at list prices (tokens.py)" if t else
                      "  G tokens     - (run tokens.py LABEL)")(c.get("tokens"))]
    return "\n".join(l for l in out if l)


TABLE = [("mission", lambda c: c["label"]), ("nav", lambda c: c["nav_model"]), ("min", lambda c: c["minutes"]),
         ("dmin", lambda c: c["B"]["dungeon_min"]), ("lv/dh", lambda c: c["B"]["levels_per_dhour"]),
         ("exp/dm", lambda c: c["B"]["exp_per_dmin"]), ("$/dm", lambda c: c["B"]["gold_found_per_dmin"]),
         ("low%", lambda c: (c["C"].get("lowest_hp") or [0, 0, None])[2]), ("close", lambda c: c["C"]["close_calls_lt40"]),
         ("near", lambda c: c["C"]["near_calls_40_50"]), ("phase", lambda c: c["C"]["phase"]),
         ("woresc", lambda c: c["C"]["wor_escape"]), ("cures", lambda c: c["C"]["cures_quaffed"]),
         ("lost", lambda c: c["D"]["total"]), ("forced$", lambda c: c["D"]["sale_shortfall_forced"]),
         ("r->a", lambda c: c["E"]["report_to_action_med_s"]), ("reply", lambda c: c["E"]["user_reply_med_s"]),
         ("wait%", lambda c: c["B"]["navigator_wait_pct"]),
         ("est", lambda c: f"{c['estimator']['agree']}/{c['estimator']['compared']}" if (c.get("estimator") or {}).get("n")
          else None),
         ("estHF", lambda c: f"{c['estimator']['hard_agree']}/{c['estimator']['hard_compared']}"
          if (c.get("estimator") or {}).get("hard_n") else None),
         ("usd", lambda c: _usd(c)),
         ("usd/dh", lambda c: _per(_usd(c), c["B"]["dungeon_min"] / 60)),
         ("usd/kxp", lambda c: _per(_usd(c), c["A"].get("exp_gain", 0) / 1000)),
         ("gold/usd", lambda c: _per(c["B"].get("gold_found"), _usd(c), 0)),
         ("adj$/dm", lambda c: c["B"].get("gold_change_adj_per_dmin"))]      # (2.50.0: last, so older readers' columns hold)


def _usd(c):
    """The Navigator's cost at API list prices (tokens.py), or None."""
    return (c.get("tokens") or {}).get("usd")


def _per(a, b, nd=2):
    return round(a / b, nd) if a is not None and b else None


def table(cards):
    rows = [[str(f(c)) for _, f in TABLE] for c in cards]
    w = [max(len(h), *(len(r[i]) for r in rows)) for i, (h, _) in enumerate(TABLE)]
    return "\n".join(["  ".join(h.ljust(w[i]) for i, (h, _) in enumerate(TABLE))] +
                     ["  ".join(r[i].ljust(w[i]) for i in range(len(TABLE))) for r in rows])


def check(cards):
    """Ours against the Advisor's baseline CSV (same definitions)."""
    base = {r["mission"]: r for r in csv.DictReader(open(os.path.join(ADVISOR, "baseline_m17-m23.csv")))}
    pairs = [("dungeon_min", lambda c: c["B"]["dungeon_min"]), ("exp_per_dmin", lambda c: c["B"]["exp_per_dmin"]),
             ("levels_per_dhour", lambda c: c["B"]["levels_per_dhour"]),
             ("gold_found_per_dmin", lambda c: c["B"]["gold_found_per_dmin"]),
             ("lowest_hp_pct", lambda c: (c["C"].get("lowest_hp") or [0, 0, None])[2]),
             ("close_calls", lambda c: c["C"]["close_calls_lt40"]), ("escapes_phase", lambda c: c["C"]["phase"]),
             ("recall_escape", lambda c: c["C"]["wor_escape"]), ("cures_quaffed", lambda c: c["C"]["cures_quaffed"]),
             ("nav_report_to_action_med_s", lambda c: c["E"]["report_to_action_med_s"])]
    print("metric (ours/Advisor's)      " + "".join(f"{c['label']:>13s}" for c in cards))
    for k, f in pairs:
        print(f"{k:29s}" + "".join(f"{str(f(c))}/{base.get(c['label'], {}).get(k, '')}".rjust(13) for c in cards))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("labels", nargs="*", help="missions to score (their cards are rewritten); a set piece (sp-*) "
                    "only when named")
    ap.add_argument("--all", action="store_true", help="rescore every real mission and rewrite its card (sp-* only "
                    "with --sp)")
    ap.add_argument("--sp", action="store_true", help="include the set-piece sp-* missions (--all or no labels)")
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    missions = logs.load_missions()
    cards = []
    if a.labels or a.all:
        pick = [m for m in missions if m["label"] in a.labels] if a.labels else \
            [m for m in missions if a.sp or not m["label"].startswith("sp-")]
        for x in sorted(set(a.labels) - {m["label"] for m in pick}):
            print(f"no mission {x} in runs/missions.json", file=sys.stderr)
        for m in pick:
            c = card(m)
            cards.append(c)
            out_dir = os.path.join(RUNS, "pilot", m["nick"], "scorecards")
            os.makedirs(out_dir, exist_ok=True)
            json.dump(c, open(os.path.join(out_dir, m["label"] + ".json"), "w"), indent=1)
    else:
        # no labels and no --all: the cards already written, read only (nothing is rescored), as a table
        a.table = True
        missing = []
        for m in missions:
            if m["label"].startswith("sp-") and not a.sp:
                continue
            f = os.path.join(RUNS, "pilot", m["nick"], "scorecards", m["label"] + ".json")
            if os.path.exists(f):
                cards.append(json.load(open(f)))
            else:
                missing.append(m["label"])
        if missing:
            print(f"(no card yet for {', '.join(missing)}: scorecard.py LABEL or --all writes them)", file=sys.stderr)
    if a.json:
        print(json.dumps(cards, indent=1))
    elif a.check:
        check(cards)
    else:
        if not a.table:
            for c in cards:
                print(show(c) + "\n")
        if a.table or len(cards) > 1:
            print(table(cards))


if __name__ == "__main__":
    main()
