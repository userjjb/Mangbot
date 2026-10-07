import re,sys,json
tv=re.compile(r'(Potion|Scroll|Staff|Staffs|Wand|Rod|Ring|Amulet)s?\b')
out=[]
for d in ['dive01','dive03','dive04']:
    L=open(d+'.tl').read().split('\n')
    for i,l in enumerate(L):
        if ' MSG You have ' not in l and ' MSG You have no room' not in l: continue
        msg=l.split(' MSG ',1)[1]
        m=re.match(r'You have (no room for )?((?:a|an|\d+) .*?)(?: \((\w)\))?\.$',msg)
        if not m: continue
        name=m.group(2)
        if not re.search(r'\b(Potions?|Scrolls?|Staffs?|Wands?|Rods?|Rings?|Amulets?)\b',name): continue
        if 'Flask' in name: continue
        # preceded by a "You see" in the previous 8 lines?
        seen=any((' MSG You see ' in L[k]) for k in range(max(0,i-8),i))
        if not seen: continue
        out.append((d,l[:14],l.split()[2],('NOROOM ' if m.group(1) else '')+name))
for o in out: print(*o,sep=' | ')
