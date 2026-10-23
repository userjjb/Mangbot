import json,re,csv,collections
U=set(open('uniques.txt').read().split('\n'))
base='/projectnb/jbrcs/mangband/runs/pilot/'
gold=[];kills=[];insc=[]
for f in ('dive04','dive03'):
    depth=None;start=0
    for l in open(base+f+'/events.jsonl'):
        if '"level"' in l or 'gold pieces' in l or 'slain' in l or 'destroyed' in l or '{' in l or 'pilot_start' in l:
            try:d=json.loads(l)
            except: continue
        else: continue
        ev=d.get('ev')
        if ev=='pilot_start': start+=1; continue
        if ev=='level': depth=d['depth'];continue
        txt=d.get('text') if ev=='message' else d.get('name') if ev=='floor' else ' | '.join(d.get('lines',[])) if ev=='itemlist' else None
        if not txt: continue
        key=(f,start,d['t'],ev)
        m=re.search(r'You have found (\d+) gold pieces worth of (\w+)',txt)
        if m and ev=='message': gold.append((depth,m.group(2),int(m.group(1)),f,start,d['t']))
        m=re.search(r'You have (?:slain|destroyed) (.*?)\.$',txt)
        if m and ev=='message':
            n=m.group(1)
            if n in U or n.replace('the ','',1) in U: kills.append((n,depth,f,start,d['t']))
        for b in re.findall(r'\{([^}]*)\}',txt):
            if b in U: insc.append((b,depth,txt,ev,f,start,d['t']))
import pickle;pickle.dump((gold,kills,insc),open('x.pkl','wb'))
print(len(gold),len(kills),len(insc))
