import json,re
start=1790391618.2815259
targets=[62.328,115.933,126.358,167.09,303.274,319.165,335.592]
frames=[json.loads(l) for l in open('/projectnb/jbrcs/mangband/runs/observe/session3/screens.jsonl')]
ansi=re.compile(r'\x1b\[[0-9;]*m')
for t in targets:
    e=start+t
    f=min((x for x in frames if x['t']>=e), key=lambda x:x['t'])
    rows=[ansi.sub('',r) for r in f['rows']]
    hits=[r.strip() for r in rows if re.search(r'Lev \d|Town|\d+ ft|Wild',r)]
    print(t, round(f['t']-e,2), hits[:3])
