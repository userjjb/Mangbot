import json,collections,sys
def recs(s):
    for l in open(f'/projectnb/jbrcs/mangband/runs/observe/session{s}/pkt.jsonl'):
        d=json.loads(l)
        if d.get('dir')=='R' and 'id' in d: yield d
def sb(b): return b-256 if b>127 else b
for s in (1,2,3):
    print('session',s)
    seen=collections.OrderedDict()
    for d in recs(s):
        n=d['name']
        if n in('IND:depth','IND:level','IND:exp','IND:hp','IND:state','IND:speed','IND:hunger','IND:gold'):
            h=bytes.fromhex(d['hex'])
            seen.setdefault(n,[]).append((d['t'],h[1:].hex()))
    for n,v in seen.items():
        print(n,len(v),v[:6], v[-3:])
