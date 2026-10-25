#!/usr/bin/env python3
"""The estimator's choice at the start of each logged episode (replay files) vs the rules, with the decision time.
Uses replay.start_state (calibrated: max_adj 3, P_AWAKE 0.4) and options_sim.evaluate with common random numbers.
usage: replay_options.py [--n 100]   -> replay_options.csv"""
import argparse, csv, glob, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import options_sim as S  # noqa: E402
import replay as R  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=100); o = ap.parse_args()
rows = []
for fn in sorted(glob.glob(f"{R.REPLAYS}/ep*.json"), key=lambda f: int(f.split("ep")[-1].split(".")[0])):
    ep = json.load(open(fn))
    p, team, arrivals = R.start_state(ep, S.DIVE04)
    if not team:
        continue
    t0 = time.time()
    res = S.evaluate(p, team, o.n, arrivals=arrivals)
    dt = time.time() - t0
    best = res[0]; rules = next(r for r in res if r["option"] == "rules")
    rows.append(dict(idx=ep["idx"], mission=ep["mission"], hp0=p["hp"], mhp=p["mhp"], monsters=len(team) + len(arrivals),
                     inv="".join(f"{k}{v} " for k, v in p["inv"].items() if v),
                     best=best["option"], best_safe=best["safe"], best_near=best["p_near_death"], best_low10=best["low_p10"],
                     best_xp=best["xp"], best_gold=best["gold"],
                     rules_safe=rules["safe"], rules_near=rules["p_near_death"], rules_low10=rules["low_p10"], rules_xp=rules["xp"],
                     rules_gold=rules["gold"],
                     second=res[1]["option"], seconds=round(dt, 2)))
    print(rows[-1])
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "replay_options.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
