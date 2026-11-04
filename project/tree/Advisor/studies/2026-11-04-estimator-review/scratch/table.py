"""Print each estimator record of the given missions with its full option table."""
import json, sys, time
want = set(sys.argv[1:]) or {"m63", "m64", "m65"}
for l in open("estimator_records.jsonl"):
    r = json.loads(l)
    if r["mission"] not in want:
        continue
    print(f"{r['mission']} {time.strftime('%H:%M:%S', time.localtime(r['t']))} d{r['depth']} hp{r['hp']} {r['trigger']} "
          f"rules={r['rules']} choice={r['choice']} agree={r['agree']} xpg={r.get('xp_per_gold')} | {r['why'][:80]}")
    print("   detail:", (r.get("rules_detail") or "")[:150])
    print("   team:", ", ".join(f"{t[0]}@{t[1]}{'' if len(t) < 4 or t[3] is None else ('a' if t[3] else 's')}" for t in r["team"][:12]),
          f"(+{len(r['team']) - 12})" if len(r["team"]) > 12 else "")
    for x in r.get("table") or []:
        print(f"     {x['option']:15s} safe={x['safe']!s:5s} near={x['p_near_death']:<5} low10={x['low_p10']:<6} xp={x['xp']:<4} "
              f"dxp={x.get('dxp')!s:6s} se={x.get('se')!s:5s} gold={x['gold']}")
