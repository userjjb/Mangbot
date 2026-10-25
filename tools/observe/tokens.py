"""tokens -- the Navigator's token usage for a mission, recorded in runs/missions.json (the user, 2026-10-25).

Read from the Navigator's own transcript (Claude Code keeps one per subagent under
~/.claude/projects/*/*/subagents/), found by its mission prompt ("Mission NN for character", or "for Dive04" in m17-m23). Each API turn is
counted once (a turn's usage repeats on every content block, early copies partial: the largest is kept). Only the Navigator's tokens: the Pilot is code,
and the Architect's own tokens aren't in it.

    python3 tokens.py m29                  # after `pilotctl mission end`
    python3 tokens.py m29 --transcript F   # name the transcript yourself
    python3 tokens.py --all                # every mission with a findable transcript and no tokens yet
"""
import argparse
import glob
import json
import os
import re
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "..", "..", "..", "runs")
MISSIONS = os.path.join(RUNS, "missions.json")
TRANSCRIPTS = os.path.expanduser("~/.claude/projects/*/*/subagents/*.jsonl")


def find_transcript(m):
    """The newest subagent transcript whose prompt opens 'Mission NN for character' and that was written
    after the mission started."""
    num = re.sub(r"\D", "", m["label"])
    if not num:
        return None
    t0 = time.mktime(time.strptime(m["start"], "%Y-%m-%d %H:%M")) - 600
    pat = re.compile(rf"Mission {num} for (character|Dive04|\*\*)")      # (m17-m23 said "for Dive04")
    hits = []
    for f in glob.glob(TRANSCRIPTS):
        if os.path.getmtime(f) < t0:
            continue
        with open(f) as fh:
            head = fh.read(20000)
        if pat.search(head):
            hits.append(f)
    return max(hits, key=os.path.getmtime) if hits else None


def usage(path):
    """Summed over API turns. A turn's usage is written with each of its content blocks, and the early copies
    can be partial (output counted so far): the largest value of each field per turn is kept."""
    per, final = {}, set()
    models, efforts = {}, {}
    fields = {"input": "input_tokens", "output": "output_tokens", "cache_read": "cache_read_input_tokens",
              "cache_write": "cache_creation_input_tokens"}
    for line in open(path):
        try:
            o = json.loads(line)
        except ValueError:
            continue
        msg = o.get("message")
        u = msg.get("usage") if isinstance(msg, dict) else None
        if not u:
            continue
        mid = msg.get("id") or id(o)
        if mid not in per:
            per[mid] = dict.fromkeys(fields, 0)
            models[msg.get("model")] = models.get(msg.get("model"), 0) + 1
            e = o.get("effort")
            if e is None:
                m = re.search(r'"effort":"(\w+)"', line)
                e = m.group(1) if m else None
            if e:
                efforts[e] = efforts.get(e, 0) + 1
        for k, f in fields.items():
            per[mid][k] = max(per[mid][k], u.get(f) or 0)
        if msg.get("stop_reason"):
            final.add(mid)
    tot = {k: sum(t[k] for t in per.values()) for k in fields}
    # (transcripts up to m23 mostly lack a turn's final usage: their output counts only the first streamed
    # tokens, ~8 a turn. Input and cache are set at a turn's start, so they hold)
    if len(final) < len(per) / 2:
        tot["output"] = None
    return {"turns": len(per), **tot, "final_usage_turns": len(final),
            "model": max(models, key=models.get) if models else None,
            "effort": max(efforts, key=efforts.get) if efforts else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("labels", nargs="*")
    ap.add_argument("--transcript")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    ms = json.load(open(MISSIONS))
    pick = [m for m in ms if m["label"] in a.labels] if a.labels else \
        [m for m in ms if a.all and not m.get("tokens") and re.fullmatch(r"m\d+", m["label"])]
    for m in pick:
        path = a.transcript or find_transcript(m)
        if not path:
            print(f"{m['label']}: no Navigator transcript found")
            continue
        u = usage(path)
        m["tokens"] = {k: u[k] for k in ("turns", "input", "output", "cache_read", "cache_write", "model",
                                         "final_usage_turns")}
        m["tokens"]["transcript"] = os.path.basename(path)
        if not m.get("effort") and u["effort"]:
            m["effort"] = u["effort"]
        print(f"{m['label']}: {m['tokens']['turns']} turns, out {u['output']}, cache read {u['cache_read']}, "
              f"cache write {u['cache_write']}, in {u['input']} ({u['model']}, effort {u['effort']})")
    if pick:
        # (re-read before writing: the Pilot appends mission markers to the same file)
        cur = json.load(open(MISSIONS))
        by = {m["label"]: m for m in pick if m.get("tokens")}
        for m in cur:
            if m["label"] in by:
                m["tokens"] = by[m["label"]]["tokens"]
                m["effort"] = m.get("effort") or by[m["label"]].get("effort")
        json.dump(cur, open(MISSIONS, "w"), indent=1)


if __name__ == "__main__":
    main()
