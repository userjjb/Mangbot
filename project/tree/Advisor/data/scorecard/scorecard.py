#!/usr/bin/env python3
"""Per-mission scorecard, reference implementation (Advisor, restructure step 1, 2026-10-22).

The Architect builds the production scorecard; this script is the specification by example and produces the baseline
(missions 17-23). Every number comes from runs/pilot/<nick>/decisions.jsonl and events.jsonl (`epoch` on every event since
2026-10-09). Definitions are in the SCORECARD dict below and in memos/2026-10-2x-scorecard.md.

usage: scorecard.py [--nick dive04] [--csv OUT] [MISSION ...]   (default: all in MISSIONS)
"""
import argparse, bisect, collections, csv, json, re, statistics, sys
from datetime import datetime

RUNS = "/projectnb/jbrcs/mangband/runs/pilot"
MISSIONS = {  # name: (start, end, navigator model) -- local time, from the Navigator reports
    "m17": ("2026-10-16 13:57", "2026-10-16 14:41", "opus"),
    "m18": ("2026-10-16 18:46", "2026-10-16 19:27", "opus"),
    "m19": ("2026-10-16 22:14", "2026-10-16 22:56", "opus"),
    "m20": ("2026-10-16 23:41", "2026-10-17 00:19", "opus"),
    "m21": ("2026-10-17 00:47", "2026-10-17 01:36", "opus"),
    "m22": ("2026-10-17 01:45", "2026-10-17 02:16", "sonnet"),
    "m23": ("2026-10-22 22:15", "2026-10-22 22:31", "sonnet"),
}
QUERY_CMDS = {"status", "journal", "gate", "monster", "inventory", "complain", "drainers", "say", "note", "options",
              "flags", "floor", "help", "plan", "dump", "quote", "view", "orders", "events", "attention", "news", "map"}
CLOSE_CALL = 0.40          # HP fraction
CURE_RE = re.compile(r"Cure (Light|Serious|Critical) Wounds|Healing")


EXP = {int(r["reach_clvl"]): int(r["halforc_warrior_needed(base*110/100)"]) for r in csv.DictReader(open(
    "/projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-progression/scratch/G1_player_exp.csv"))}  # exp to reach clvl
EXP[1] = 0


def ts(s): return datetime.strptime(s, "%Y-%m-%d %H:%M").timestamp()
def med(v): return round(statistics.median(v), 1) if v else None


def load(nick):
    dec = [json.loads(l) for l in open(f"{RUNS}/{nick}/decisions.jsonl")]
    ev = []
    for l in open(f"{RUNS}/{nick}/events.jsonl"):
        if '"epoch"' not in l:
            continue
        e = json.loads(l)
        if e.get("ev") in ("message", "level", "store", "pilot_start"):
            ev.append(e)
    return dec, ev


def score(name, dec, ev):
    a, b, model = MISSIONS[name]
    t0, t1 = ts(a), ts(b)
    d = [x for x in dec if t0 <= x["t"] <= t1]
    msgs = [(e["epoch"], e.get("text", "")) for e in ev if t0 <= e["epoch"] <= t1 and e.get("ev") == "message"]
    ac = [x for x in d if x["kind"] == "audit_check"]
    out = {"mission": name, "model": model, "minutes": round((t1 - t0) / 60, 1)}

    # --- outcome
    if ac:
        out.update(clvl_start=ac[0]["clvl"], clvl_end=ac[-1]["clvl"], exp_gain=ac[-1]["exp"][0] - ac[0]["exp"][0],
                   gold_start=ac[0]["gold"], gold_end=ac[-1]["gold"], gold_change=ac[-1]["gold"] - ac[0]["gold"],
                   max_depth_ft=max(x.get("depth_ft") or 0 for x in ac))
    out["deaths"] = sum(1 for x in d if x["kind"] == "attention" and x.get("what") == "dead")

    # --- time: dungeon minutes from records' depth (gaps > 60 s not counted)
    dung = town = 0.0
    for p, q in zip(d, d[1:]):
        dt = q["t"] - p["t"]
        if dt > 60:
            continue
        if (p.get("depth") or 0) > 0: dung += dt
        else: town += dt
    out["dungeon_min"] = round(dung / 60, 1); out["town_min"] = round(town / 60, 1)
    if dung:
        out["exp_per_dmin"] = round(out.get("exp_gain", 0) / (dung / 60), 1)
        # gold found in the dungeon: sum of positive gold steps while in the dungeon (sales happen in town)
        g = 0
        for p, q in zip(ac, ac[1:]):
            if (q.get("depth_ft") or 0) > 0 and q["gold"] > p["gold"]:
                g += q["gold"] - p["gold"]
        lv = 0.0                         # fraction of a level gained, at the clvl of the moment (level-normalised)
        for p, q in zip(ac, ac[1:]):
            de = q["exp"][0] - p["exp"][0]
            if de > 0:
                c = p["clvl"]; lv += de / max(1, EXP.get(c + 1, 10**9) - EXP.get(c, 0))
        out["levels_per_dhour"] = round(lv / (dung / 3600), 2)
        out["gold_found"] = g; out["gold_found_per_dmin"] = round(g / (dung / 60), 1)

    # --- safety
    hp = [(x["t"], x["hp"][0] / x["hp"][1]) for x in d if x.get("hp") and x["hp"][1] > 1 and x["hp"][0] > 0]
    out["lowest_hp_pct"] = round(100 * min(h for _, h in hp)) if hp else None
    cc, last = 0, -1e9
    for t, h in hp:                      # a close call = an episode below 40%, episodes > 60 s apart
        if h < CLOSE_CALL:
            if t - last > 60: cc += 1
            last = t
    out["close_calls"] = cc
    att = collections.Counter(x.get("what") for x in d if x["kind"] == "attention")
    out["emergencies"] = att["emergency"] + att["emergency_loop"]
    out["danger_seen"] = att["danger_seen"]; out["flee_failed"] = att.get("flee_failed", 0)

    # --- consumption (game messages are the ground truth for what was used)
    # Pilot/Navigator item commands (act records); a read/quaff that failed or was held is still counted (upper bound)
    read = collections.Counter(); quaff = collections.Counter()
    acts = [x for x in d if x["kind"] == "act"]
    for x in acts:
        why = str(x.get("why", ""))
        if x.get("cmd", "").startswith("custom r"):
            low = why.lower()
            if "phase door" in low: read["phase"] += 1
            elif "word of recall" in low or "recall" in low and why.startswith("agent: read"):
                urgent = any(k in low for k in ("low hp", "flee", "danger", "emergency", "monsters close"))
                read["recall_escape" if urgent else "recall_travel"] += 1
        if x.get("cmd", "").startswith("custom q"):
            m = CURE_RE.search(why)
            quaff[m.group(0) if m else "other"] += 1
    out["escapes_phase"] = read["phase"]; out["recall_escape"] = read["recall_escape"]
    out["recall_travel"] = read["recall_travel"]
    out["cures_quaffed"] = sum(v for k, v in quaff.items() if k != "other")
    spent = sum(int(m.group(1)) for _, t in msgs for m in [re.search(r"You bought .* for (\d+) gold", t)] if m)
    sold = sum(int(m.group(1)) for _, t in msgs for m in [re.search(r"You sold .* for (\d+) gold", t)] if m)
    out["gold_spent"] = spent; out["gold_sold"] = sold
    out["gold_stolen"] = sum(int(m.group(1)) for _, t in msgs for m in [re.search(r"(\d+) coins were stolen", t)] if m)
    out["items_stolen"] = sum(1 for _, t in msgs if re.search(r"^One of your .* was stolen|^Your .* was stolen", t))

    # --- Navigator
    nc = [x for x in d if x["kind"] == "nav_cmd"]
    reports = [x["t"] for x in nc if x.get("wait_report")]
    cmds = [(x["t"], x["cmd"], x.get("args", [])) for x in nc if not x.get("wait_report")]
    acts_t = [t for t, c, _ in cmds if c not in QUERY_CMDS]
    act_lat = []
    for i, r in enumerate(reports):
        nxt = reports[i + 1] if i + 1 < len(reports) else t1
        ia = [t for t in acts_t if r < t < nxt]
        if ia: act_lat.append(ia[0] - r)
    out["nav_reports"] = len(reports); out["nav_commands"] = len(cmds)
    out["nav_report_to_action_med_s"] = med(act_lat)
    out["nav_forced"] = sum(1 for _, c, args in cmds for s in args if isinstance(s, str) and s.startswith("!"))
    users = [x["t"] for x in d if x["kind"] == "user_note"]
    says = sorted(x["t"] for x in d if x["kind"] == "nav_say")
    rep = [says[j] - u for u in users for j in [bisect.bisect_right(says, u)] if j < len(says) and says[j] - u < 300]
    out["user_notes"] = len(users); out["user_reply_med_s"] = med(rep)
    out["nav_complaints"] = sum(1 for x in d if x["kind"] == "nav_complaint")

    # --- Pilot health
    out["audit_checks"] = len(ac); out["audit_diffs"] = sum(x.get("differences", 0) for x in ac)
    out["stuck"] = att["stuck"]; out["perception_gaps"] = sum(1 for x in d if x["kind"] == "perception_gap")
    out["goal_failed"] = att["goal_failed"]
    runs = [x for x in d if x["kind"] == "move" and x.get("run")]
    out["runs_sent"] = len(runs)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nick", default="dive04"); ap.add_argument("--csv"); ap.add_argument("missions", nargs="*")
    o = ap.parse_args()
    dec, ev = load(o.nick)
    rows = [score(m, dec, ev) for m in (o.missions or MISSIONS)]
    keys = list(dict.fromkeys(k for r in rows for k in r))
    if o.csv:
        with open(o.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
    print(f"{'metric':28s}" + "".join(f"{r['mission']:>9s}" for r in rows))
    for k in keys[1:]:
        print(f"{k:28s}" + "".join(f"{str(r.get(k, '')):>9s}" for r in rows))


if __name__ == "__main__":
    main()
