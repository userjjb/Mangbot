import pickle,re,sys
from common import *
evs=pickle.load(open('evs.pkl','rb'))
hp=pickle.load(open('hp.pkl','rb'))
def hp_at(t):
    r=None
    for x in hp:
        if x[0]<=t:r=x
        else:break
    return r[1] if r else None
def dump(a,b,skipmelee=True):
    cnt=0;last=None
    for v in evs:
        if a<=v['epoch']<=b and v['ev']=='message':
            tx=v['text']
            if skipmelee and re.match(r'You (hit|miss|smite|bash|slash|pierce|bite)',tx):
                cnt+=1;continue
            if cnt:print(f"        ({cnt} own melee msgs)");cnt=0
            print(f"{hms(v['epoch'])}.{int(v['epoch']*10)%10} hp{hp_at(v['epoch'])} [{v['type']}] {tx}")
    if cnt:print(f"        ({cnt} own melee msgs)")
if __name__=='__main__':
    dump(eps_(sys.argv[1]),eps_(sys.argv[2]))
