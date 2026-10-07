#!/usr/bin/env python3
"""Merge the Clerks' message tables into catalogue.csv and measure coverage of our logs.

Reads studies/2026-09-29-messages/scratch/M*_catalogue.csv. Checks every regex compiles.
Coverage: for each message in log_messages.csv (numbers normalised to '#'), try the regexes with
'#' turned back into a digit ('1'); report matched share by count and the top unmatched messages.
Writes catalogue.csv and coverage.csv (text, count, matched_event(s)).
"""
import csv, glob, os, re, collections
HERE = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.join(HERE, "../../studies/2026-09-29-messages/scratch")
cols = ["id", "file", "line", "text", "event", "audience", "pilot_relevance", "regex", "condition", "notes", "source"]
rows, bad = [], []
for p in sorted(glob.glob(os.path.join(STUDY, "M*_catalogue.csv"))):
    src = os.path.basename(p).split("_")[0]
    for r in csv.DictReader(open(p, encoding="utf-8", errors="replace")):
        r = {k: (r.get(k) or "").strip() for k in cols}
        r["source"] = src
        try:
            r["_re"] = re.compile(r["regex"]) if r["regex"] else None
        except re.error as e:
            bad.append((src, r["id"], r["regex"], str(e)))
            r["_re"] = None
        rows.append(r)
with open(os.path.join(HERE, "catalogue.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
    w.writeheader(); w.writerows(rows)
print(f"{len(rows)} catalogue rows from {len(set(r['source'] for r in rows))} tables; bad regexes: {len(bad)}")
for b in bad[:10]:
    print("  BAD", b)
ev = collections.Counter(r["event"].split(".")[0] for r in rows)
print("event families:", ev.most_common(20))
rel = collections.Counter(r["pilot_relevance"] for r in rows); print("relevance:", dict(rel))
logs = list(csv.DictReader(open(os.path.join(HERE, "log_messages.csv"))))
res = [r for r in rows if r["_re"] and r["audience"] != "others"]
# drop catch-all regexes: those matching nonsense or > 50% of distinct logged messages
probe = ["Zq xv wk.", "The quick brown fox."]
share = {id(r): sum(1 for l in logs if r["_re"].search(l["text"].replace("#", "1"))) / len(logs) for r in res}
broad = [r for r in res if any(r["_re"].search(x) for x in probe) or share[id(r)] > 0.5]
print(f"catch-all regexes dropped from coverage: {len(broad)}:", [(r['source'], r['event'], r['regex'][:40]) for r in broad][:8])
res = [r for r in res if r not in broad]
tot = sum(int(l["count"]) for l in logs); hit = 0; out = []
for l in logs:
    t = l["text"].replace("#", "1")
    evs = sorted({r["event"] for r in res if r["_re"].search(t)})
    if evs:
        hit += int(l["count"])
    out.append(dict(text=l["text"], count=l["count"], events="|".join(evs)))
with open(os.path.join(HERE, "coverage.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["text", "count", "events"]); w.writeheader(); w.writerows(out)
print(f"log coverage: {hit}/{tot} = {hit/tot:.1%} of messages; distinct matched "
      f"{sum(1 for o in out if o['events'])}/{len(out)}")
amb = [o for o in out if o["events"].count("|") >= 1]
print(f"ambiguous (matched by >1 event): {len(amb)}; e.g.", [(o['text'][:50], o['events'][:80]) for o in amb[:5]])
print("top unmatched:")
for o in [o for o in out if not o["events"]][:30]:
    print("  ", o["count"], o["text"][:100])
