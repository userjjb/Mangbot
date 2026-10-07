import re,sys
unk=re.compile(r'(?:(?:a|an|\d+) )?((?:[A-Z][\w\'-]*(?: [A-Z][\w\'-]*)* (?:Potions?|Staffs?|Wands?|Rods?|Rings?|Amulets?))|(?:Scrolls? titled "[^"]+"(?: \{tried\})?))')
for d in sys.argv[1:]:
    print('=====',d)
    for ln,l in enumerate(open(d+'.tl'),1):
        l=l.rstrip()
        if ' MSG ' not in l: continue
        msg=l.split(' MSG ',1)[1]
        if ' of ' in msg.split('(')[0] and 'titled' not in msg: 
            if not re.search(r'(Potion|Staff|Wand|Rod|Ring|Amulet)s? \(',msg): pass
        m=unk.search(msg)
        if not m: continue
        if re.match(r'(You have|You see|Selling|You destroy|You have no room|You have no more|It picks|Examining|In your pack|You are wearing|Was wearing)',msg) or 'picks up' in msg:
            if ' of ' in msg and 'titled' not in msg: continue
            print(ln,l[:200])
