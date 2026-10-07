#!/usr/bin/env python3
"""Count the game messages seen in our Pilot runs (events.jsonl 'message' events, all characters).
Normalises numbers to '#'. Writes log_messages.csv: text, count, type(s), characters."""
import csv, glob, json, os, re, collections
cnt, types, who = collections.Counter(), collections.defaultdict(set), collections.defaultdict(set)
for path in glob.glob("/projectnb/jbrcs/mangband/runs/pilot/*/events.jsonl"):
    nick = path.split("/")[-2]
    for l in open(path):
        if '"message"' not in l:
            continue
        try:
            r = json.loads(l)
        except Exception:
            continue
        if r.get("ev") != "message":
            continue
        t = re.sub(r"\d+", "#", r.get("text", "")).strip()
        if not t:
            continue
        cnt[t] += 1; types[t].add(r.get("type")); who[t].add(nick)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log_messages.csv")
with open(out, "w", newline="") as f:
    w = csv.writer(f); w.writerow(["text", "count", "types", "characters"])
    for t, c in cnt.most_common():
        w.writerow([t, c, "|".join(map(str, sorted(types[t], key=str))), "|".join(sorted(who[t]))])
print(len(cnt), "distinct normalised messages,", sum(cnt.values()), "total ->", out)
