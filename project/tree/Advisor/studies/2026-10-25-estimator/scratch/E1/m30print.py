import pickle,sys,re
from common import *
rows=pickle.load(open('m30rows.pkl','rb'))
def pr(a,b):
    t0=eps_('2026-10-25 '+a[:8])+float('0'+a[8:]);t1=eps_('2026-10-25 '+b[:8])+float('0'+b[8:])
    lastp=None
    for t,k,x in rows:
        if not(t0<=t<=t1):continue
        if k=='P':
            if x!=lastp:print(f"{hms(t)}.{int(t*10)%10} pos {x}");lastp=x
            continue
        if k=='M':
            pos,h,ms=x
            s=' '.join(f"{m[2][:10]}({m[0]-pos[0]},{m[1]-pos[1]})" for m in ms)
            print(f"{hms(t)}.{int(t*10)%10} MONS hp{h} @{pos}: {s}");continue
        if k=='V':continue
        if k=='m' and re.match(r'You (hit|miss)',x):continue
        print(f"{hms(t)}.{int(t*10)%10} {k} {x}")
pr(sys.argv[1],sys.argv[2])
