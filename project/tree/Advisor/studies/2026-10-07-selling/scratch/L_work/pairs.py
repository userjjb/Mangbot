import re,sys,json
unk=re.compile(r'^Selling (?:(?:a|an|\d+) )?((?:[A-Z][\w\'-]*(?: [A-Z][\w\'-]*)* (?:Potions?|Staffs?|Wands?|Rods?|Rings?|Amulets?))|(?:Scrolls? titled "[^"]+"(?: \{tried\})?)) \((\w)\)')
for d in ['dive03','dive04']:
    L=open(d+'.tl').read().split('\n')
    for i,l in enumerate(L):
        if ' MSG ' not in l: continue
        msg=l.split(' MSG ',1)[1]
        m=unk.match(msg)
        if m:
            res=None
            for k in range(i+1,i+10):
                if ' MSG You sold' in L[k]:
                    res=L[k].split(' MSG ',1)[1];break
                if "I don't want" in L[k]: res=L[k].split(' MSG ',1)[1];break
            print(d,l[:14],l.split()[2],'|',msg[:70],'=>',res)
