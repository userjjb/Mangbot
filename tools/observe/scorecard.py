#!/usr/bin/env python3
"""scorecard -- one card per mission, from the Pilot's logs, so regressions show the
next morning rather than three weeks later (the Advisor's starting-over memo, 2026-10-19).

Missions are listed in runs/missions.json (label, nick, start, end, navigator, report).

    python3 scorecard.py m23                 # one card
    python3 scorecard.py --all               # every card, then a comparison table
    python3 scorecard.py --table             # the comparison table only
    python3 scorecard.py --json m23          # the numbers as JSON

Sources: decisions.jsonl (audit checks every 30 s: exp, gold, clvl, depth; every action
with its reason; alerts; Navigator commands; user notes), events.jsonl (game messages
with wall-clock epochs), testserver/gdb_run.log (server crashes). Everything is computed
from what was logged; where a figure is an estimate, the card says so.
"""
import argparse
import collections
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from latency import measure  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RUNS = os.path.join(ROOT, "runs")

CONSUMABLE_RE = re.compile(r"(?:Potions? of|Scrolls? of) ([A-Z][\w']*(?: [A-Za-z][\w']*)*)")


def epoch(s):
    return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M"))


def load_missions():
    with open(os.path.join(RUNS, "missions.json")) as f:
        return json.load(f)


def decisions(nick, t0, t1):
    out = []
    with open(os.path.join(RUNS, "pilot", nick, "decisions.jsonl")) as f:
        for line in f:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if t0 <= d.get("t", 0) <= t1:
                out.append(d)
    return out


def messages(nick, t0, t1):
    """(epoch, text) of every game message in the window. events.jsonl is large:
    a cheap substring test before parsing."""
    out = []
    with open(os.path.join(RUNS, "pilot", nick, "events.jsonl")) as f:
        for line in f:
            if '"message"' not in line or '"epoch"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            e = d.get("epoch", 0)
            if t0 <= e <= t1 and d.get("ev") == "message":
                out.append((e, d.get("text", "")))
    return out


def store_listings(nick, t0, t1):
    """(epoch, [(name, price)]) of store listings: what a sold item was then offered at."""
    out = []
    with open(os.path.join(RUNS, "pilot", nick, "events.jsonl")) as f:
        for line in f:
            if '"ev": "store"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            e = d.get("epoch", 0)
            if t0 <= e <= t1:
                out.append((e, [(i.get("name", ""), i.get("price", 0)) for i in d.get("items", [])]))
    return out


def server_crashes(t0, t1):
    """SIGSEGVs in testserver/gdb_run.log, timed by the server line before them."""
    path = os.path.join(ROOT, "testserver", "gdb_run.log")
    out, last = [], None
    if not os.path.exists(path):
        return out
    with open(path, errors="replace") as f:
        for line in f:
            m = re.match(r"(\d{6}) (\d{6}) ", line)
            if m:
                try:
                    last = time.mktime(time.strptime(m.group(1) + m.group(2), "%d%m%y%H%M%S"))
                except ValueError:
                    pass
            elif "SIGSEGV" in line and last and t0 <= last <= t1:
                out.append(last)
    return out


def bare(name):
    n = re.sub(r"\s*\{[^}]*\}", "", name)
    n = re.sub(r"^(an?|the|\d+) ", "", n.strip())
    return n


def card(m):
    nick = m["nick"]
    t0, t1 = epoch(m["start"]), epoch(m["end"])
    recs = decisions(nick, t0, t1)
    msgs = messages(nick, t0, t1)
    c = {"label": m["label"], "nav_model": m.get("navigator"), "report": m.get("report"),
         "start": m["start"], "end": m["end"], "minutes": round((t1 - t0) / 60, 1), "notes": m.get("notes", "")}

    # --- time in the dungeon (depth > 0 on each record, weighted by the gap to the next)
    timed = sorted((d["t"], d.get("depth") or 0) for d in recs if "depth" in d)
    dmin = sum(b[0] - a[0] for a, b in zip(timed, timed[1:]) if a[1] and b[0] - a[0] < 60) / 60
    c["dungeon_minutes"] = round(dmin, 1)

    # --- progress, from the audit checks
    aud = [d for d in recs if d.get("kind") == "audit_check"]
    if aud:
        a, b = aud[0], aud[-1]
        c["clvl"] = [a.get("clvl"), b.get("clvl")]
        c["exp"] = [(a.get("exp") or [0])[0], (b.get("exp") or [0])[0]]
        c["gold"] = [a.get("gold"), b.get("gold")]
        c["deepest_ft"] = max(d.get("depth_ft") or 0 for d in aud)
        c["audit_checks"] = len(aud)
        c["audit_differences"] = sum(d.get("differences") or 0 for d in aud)
    xp = (c["exp"][1] - c["exp"][0]) if "exp" in c else 0
    c["xp_gained"] = xp
    c["xp_per_dungeon_min"] = round(xp / dmin, 1) if dmin else None

    # --- gold flows, from the game's messages
    flows = collections.Counter()
    sales = []
    for e, t in msgs:
        mm = re.match(r"You have found (\d+) gold", t)
        if mm:
            flows["found"] += int(mm.group(1))
        mm = re.match(r"You sold (.+?) for (\d+) gold", t)
        if mm:
            flows["sold"] += int(mm.group(2))
            sales.append((e, mm.group(1), int(mm.group(2))))
        mm = re.match(r"You bought (.+?) for (\d+) gold", t)
        if mm:
            flows["bought"] += int(mm.group(2))
        mm = re.match(r"(\d+) coins were stolen", t)
        if mm:
            flows["stolen"] += int(mm.group(1))
    c["gold_flows"] = dict(flows)
    c["found_per_dungeon_min"] = round(flows["found"] / dmin, 1) if dmin else None

    # --- value lost (an estimate): an item sold, then offered by a store for 10x+ what we got
    later = store_listings(nick, t0, t1 + 1800)
    lost = []
    for e, name, got in sales:
        key = bare(name).lower()
        offers = [p for te, items in later if te >= e for n, p in items if bare(n).lower() == key]
        if offers and min(offers) >= 10 * max(got, 1):
            lost.append({"item": bare(name), "sold_for": got, "store_asks": min(offers)})
    forced = [d for d in recs if d.get("kind") == "nav_cmd" and d.get("cmd") == "goal" and
              (d.get("args") or [None])[0] == "shop" and any(str(a).startswith(("sell", "!")) or "!" in str(a)
                                                                for a in d.get("args", [])[1:])
              and any("!" in str(a) for a in d.get("args", []))]
    c["value_lost"] = {"resold_10x": lost, "forced_sales": len(forced),
                       "items_lost": [d.get("detail") for d in recs if d.get("kind") == "attention"
                                      and d.get("what") == "lost"],
                       "left_on_floor": [d.get("detail") for d in recs if d.get("kind") == "attention"
                                         and d.get("what") == "tactic" and str(d.get("detail", "")).startswith("left ")]}

    # --- safety
    # (max HP under 20 is a placeholder logged before the indicators arrive, e.g.
    # while reconnecting after mission 21's server crash, not a real reading)
    hps = [(d["t"], d["hp"][0], d["hp"][1]) for d in recs if isinstance(d.get("hp"), list) and len(d["hp"]) >= 2
           and d["hp"][1] >= 20]
    if hps:
        lo = min(hps, key=lambda h: h[1] / h[2])
        c["lowest_hp"] = [lo[1], lo[2], time.strftime("%H:%M:%S", time.localtime(lo[0]))]
    close, last = 0, -1e9
    for t, hp, mx in hps:
        if hp < 0.4 * mx:
            if t - last > 30:
                close += 1
            last = t
    c["close_calls_below_40pct"] = close
    att = collections.Counter(d.get("what") for d in recs if d.get("kind") == "attention")
    c["alerts"] = dict(att.most_common())
    c["deaths"] = att.get("dead", 0)
    c["recalls"] = sum(1 for e, t in msgs if "yanked" in t)
    c["level_changes"] = len({d["t"] // 1 for d in recs if d.get("kind") == "goal_done"}) or None

    # --- consumables used (from the Pilot's action log: its own and the Navigator's item commands)
    used = collections.Counter()
    for d in recs:
        if d.get("kind") != "act":
            continue
        cmd, why = str(d.get("cmd", "")), str(d.get("why", ""))
        if not re.match(r"custom [qr] ", cmd):
            continue
        k = CONSUMABLE_RE.search(why)
        if k:
            used[k.group(1)] += 1
        elif "phase door" in why.lower():
            used["Phase Door"] += 1
        elif "word of recall" in why.lower():
            used["Word of Recall"] += 1
        elif why.startswith("agent: "):
            arg = re.search(r"\['([^']+)'", why)
            used[(arg.group(1).replace("_", " ") if arg else "?") + " (by name/letter)"] += 1
    c["consumables_used"] = dict(used.most_common())

    # --- the Navigator
    lat = measure(recs)
    def med(xs):
        xs = sorted(xs)
        return round(xs[len(xs) // 2], 1) if xs else None
    def p90(xs):
        xs = sorted(xs)
        return round(xs[min(len(xs) - 1, int(0.9 * len(xs)))], 1) if xs else None
    navc = collections.Counter(d.get("cmd") for d in recs if d.get("kind") == "nav_cmd")
    c["navigator"] = {"commands": sum(navc.values()), "per_min": round(sum(navc.values()) / max(1, c["minutes"]), 1),
                      "alert_to_order_median": med(lat["order"]), "alert_to_order_p90": p90(lat["order"]),
                      "user_to_reply_median": med(lat["reply"]), "user_messages": att.get("user_message", 0),
                      "user_notes": sum(1 for d in recs if d.get("kind") == "user_note"),
                      "full_reports": sum(1 for d in recs if d.get("kind") == "nav_cmd" and d.get("cmd") == "status"
                                          and "full" in (d.get("args") or [])),
                      "complaints": att.get("nav_complaint", 0) + sum(1 for d in recs if d.get("kind") == "nav_complaint")}
    # reports read and how stale the report behind each order was (logged since 2026-10-22)
    reps = [d for d in recs if d.get("kind") == "report"]
    ages = [d["report_age"] for d in recs if d.get("kind") == "nav_cmd" and d.get("report_age") is not None
            and d.get("cmd") not in ("status", "journal", "say", "pack", "equip", "orders", "map", "monster",
                                     "drainers", "gate", "complain")]
    c["navigator"].update({"reports": len(reps) or None, "report_chars": sum(d.get("chars", 0) for d in reps) or None,
                           "order_report_age_median": med(ages), "order_report_age_p90": p90(ages)})

    # --- the Pilot
    gf = collections.Counter(str(d.get("detail", ""))[:60] for d in recs if d.get("kind") == "attention"
                             and d.get("what") == "goal_failed")
    moves = [d for d in recs if d.get("kind") == "move"]
    c["pilot"] = {"stuck": att.get("stuck", 0), "goal_failed": dict(gf.most_common(5)),
                  "runs": sum(1 for d in moves if d.get("run")), "move_records": len(moves),
                  "server_crashes": len(server_crashes(t0, t1))}
    return c


def show(c):
    g = c.get("gold", [None, None])
    fl = c["gold_flows"]
    nv, pl, vl = c["navigator"], c["pilot"], c["value_lost"]
    lines = [
        f"=== {c['label']}  {c['start']} - {c['end'][11:]} ({c['minutes']} min, {c['dungeon_minutes']} in the dungeon)"
        f"  Navigator {c.get('nav_model')}, {c.get('report')} report",
    ]
    lines += [
        f"  {c['notes']}" if c["notes"] else "",
        f"  progress  clvl {c.get('clvl')}  XP +{c['xp_gained']} ({c['xp_per_dungeon_min']}/dungeon min)  "
        f"deepest {c.get('deepest_ft')} ft",
        f"  gold      {g[0]} -> {g[1]}  found {fl.get('found', 0)} ({c['found_per_dungeon_min']}/dungeon min)  "
        f"sold {fl.get('sold', 0)}  bought {fl.get('bought', 0)}  stolen {fl.get('stolen', 0)}",
        f"  safety    lowest HP {c.get('lowest_hp')}  close calls (<40%) {c['close_calls_below_40pct']}  "
        f"deaths {c['deaths']}  recalls {c['recalls']}",
        f"  used      " + (", ".join(f"{k} {v}" for k, v in c["consumables_used"].items()) or "nothing"),
        f"  value     sold, then offered by a store at 10x+: " + (", ".join(f"{x['item']} (sold {x['sold_for']}, store asks {x['store_asks']})"
                                              for x in vl["resold_10x"]) or "none")
        + f"; forced sales {vl['forced_sales']}; lost {len(vl['items_lost'])}; left on the floor {len(vl['left_on_floor'])}",
        f"  navigator {nv['commands']} commands ({nv['per_min']}/min); alert->order median {nv['alert_to_order_median']} s, "
        f"p90 {nv['alert_to_order_p90']} s; user messages {nv['user_messages']}, reply median {nv['user_to_reply_median']} s",
        (f"  reports   {nv['reports']} read, {nv['report_chars']} characters; orders came "
         f"{nv['order_report_age_median']} s (median) / {nv['order_report_age_p90']} s (p90) after their report\n"
         if nv.get("reports") else "") +
        f"  pilot     stuck {pl['stuck']}; goal_failed {sum(pl['goal_failed'].values())}; audit "
        f"{c.get('audit_differences')}/{c.get('audit_checks')} differences; server crashes {pl['server_crashes']}",
        f"  alerts    " + ", ".join(f"{k} {v}" for k, v in list(c["alerts"].items())[:10]),
    ]
    return "\n".join(l for l in lines if l)


def table(cards):
    cols = [("mission", lambda c: c["label"]), ("nav", lambda c: c.get("nav_model") or "?"),
            ("min", lambda c: c["minutes"]), ("dng", lambda c: c["dungeon_minutes"]),
            ("XP/dm", lambda c: c["xp_per_dungeon_min"]), ("$found/dm", lambda c: c["found_per_dungeon_min"]),
            ("gold", lambda c: f"{c.get('gold', [0, 0])[0]}->{c.get('gold', [0, 0])[1]}"),
            ("lowHP%", lambda c: round(100 * c["lowest_hp"][0] / c["lowest_hp"][1]) if c.get("lowest_hp") else None),
            ("close", lambda c: c["close_calls_below_40pct"]), ("recalls", lambda c: c["recalls"]),
            # (what the stores then asked for items we sold at a tenth of that or less;
            # the real loss is a fraction of it: an identified sale fetches less than
            # the asking price -- the Advisor is asked for the formula)
            ("resold@", lambda c: sum(x["store_asks"] for x in c["value_lost"]["resold_10x"])),
            ("a->o med", lambda c: c["navigator"]["alert_to_order_median"]),
            ("a->o p90", lambda c: c["navigator"]["alert_to_order_p90"]),
            ("cmd/min", lambda c: c["navigator"]["per_min"])]
    rows = [[str(f(c)) for _, f in cols] for c in cards]
    w = [max(len(h), *(len(r[i]) for r in rows)) for i, (h, _) in enumerate(cols)]
    out = ["  ".join(h.ljust(w[i]) for i, (h, _) in enumerate(cols))]
    out += ["  ".join(r[i].ljust(w[i]) for i in range(len(cols))) for r in rows]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("labels", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    ms = load_missions()
    pick = ms if (a.all or a.table or not a.labels) else [m for m in ms if m["label"] in a.labels]
    cards = []
    for m in pick:
        c = card(m)
        c["nav_model"] = m.get("navigator")
        cards.append(c)
        out_dir = os.path.join(RUNS, "pilot", m["nick"], "scorecards")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, m["label"] + ".json"), "w") as f:
            json.dump(c, f, indent=1)
    if a.json:
        print(json.dumps(cards, indent=1))
        return
    if not a.table:
        for c in cards:
            print(show(c))
            print()
    if a.table or a.all or len(cards) > 1:
        print(table(cards))


if __name__ == "__main__":
    main()
