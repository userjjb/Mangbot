"""Usage: python3 replay_group.py RUNDIR (e.g. runs/pilot/dive03).
Replay the Borg group-danger tiers (memo 2026-09-28 §3.1) over a Pilot log.
Upper bound: counts every monster in view (monlist), not only those in reach."""
import json, csv, re, sys, bisect, collections
D = sys.argv[1]
rows = {r['name']: r for r in csv.DictReader(open('/projectnb/jbrcs/mangband/github/tools/pilot/danger_table.csv'))}
def score(name):
    r = rows.get(name)
    if not r or 'NEVER_MOVE' in r['tags']: return 0.0
    para = 200 if 'PARA_BLOW' in r['tags'] else 0
    return float(r['melee_max']) * float(r['speed_x']) + 150 * int(r['drain_blows']) + para
# decisions: (epoch, hp, depth, pos)
dec = []
for l in open(f'{D}/decisions.jsonl'):
    try: e = json.loads(l)
    except: continue
    if 'hp' in e and 't' in e and isinstance(e['t'], (int, float)) and e['t'] > 1e9:
        dec.append((e['t'], e['hp'], e.get('depth'), tuple(e.get('pos') or ())))
dec.sort(); dts = [d[0] for d in dec]
# events split in segments; align each segment by matching pos events with decision positions
segs, cur, prev = [], [], None
for l in open(f'{D}/events.jsonl'):
    try: e = json.loads(l)
    except: continue
    t = e.get('t')
    if t is None: continue
    if prev is not None and t < prev - 5:
        segs.append(cur); cur = []
    cur.append(e); prev = t
segs.append(cur)
pos_index = collections.defaultdict(list)
for t, hp, dep, pos in dec: pos_index[pos].append(t)
tiers = [(2.0, 'leave level'), (1.0, 'stairs/teleport'), (0.6, 'escape now'), (0.3, "don't approach")]
counts = collections.Counter(); fired = []
for seg in segs:
    # offset: most common (decision_t - event_t) over pos events with a unique-ish match
    votes = collections.Counter()
    for e in seg:
        if e.get('ev') == 'pos':
            for td in pos_index.get((e['y'], e['x']), [])[:50]:
                votes[round(td - e['t'])] += 1
    if not votes: continue
    off, v = votes.most_common(1)[0]
    if v < 20: continue
    last = None
    for e in seg:
        if e.get('ev') != 'monlist': continue
        t = e['t'] + off
        i = bisect.bisect_left(dts, t)
        if i >= len(dec) or abs(dts[i] - t) > 3: continue
        hp = dec[i][1][0]
        names = []
        for line in e['lines']:
            m = re.match(r"(.+?) \('.'\)/\('.'\):\[(\d+)\]", line)
            if m: names += [m.group(1)] * int(m.group(2))
        g = sum(score(n) for n in names)
        tier = next((lab for k, lab in tiers if hp > 0 and g > k * hp), None)
        if tier:
            counts[tier] += 1
            key = (tier, tuple(sorted(set(names))))
            if key != last:
                fired.append((t, hp, dec[i][2], round(g), tier, collections.Counter(names)))
            last = key
        else:
            last = None
print("monlist events by tier:", dict(counts))
import time
for t, hp, dep, g, tier, names in fired:
    if tier in ('leave level', 'stairs/teleport', 'escape now'):
        print(time.strftime('%m-%d %H:%M:%S', time.localtime(t)), f"dl{dep} hp{hp} group{g} {tier}:",
              ', '.join(f"{n}x{c}" if c > 1 else n for n, c in names.items())[:150])
