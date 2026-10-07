import re, csv, sys
I=re.I
RE_ATTACK = re.compile(r" (hits|bites|claws|stings|touches|kicks|butts|crushes|engulfs|crawls on|spits on|gazes at|wails at|punches|grabs|fires an arrow|casts a magic missile|points at you and curses|breathes|misses|releases spores at) you")
RE_UNSEEN = re.compile(r"^(It|Something) (hits|bites|claws|stings|touches|kicks|butts|crushes|engulfs|crawls on|spits on|gazes at|wails at|punches|grabs|breathes|casts|magically|mumbles|fires|points at you|commands you|drains|tries to|concentrates)")
RE_HURT = re.compile(r"trap|pit|impaled|graze|cut|bleed|poison|dart|You feel very sick|burn|freeze|acid|You are hit|starv|faint", I)
sw=lambda *p:(lambda t:t.startswith(p))
P=[ # name, kind, purpose, file, line, fn
("startswith 'You have '","substr","inven_dirty / pickup confirm","world.py",124,sw("You have ")),
("startswith 'You see '","substr","inven_dirty; pickup trigger","world.py",124,sw("You see ")),
("'no more' in","substr","inven_dirty","world.py",124,lambda t:"no more" in t),
("startswith 'You are wearing'","substr","inven_dirty","world.py",125,sw("You are wearing")),
("startswith 'You are wielding'","substr","inven_dirty","world.py",125,sw("You are wielding")),
("startswith 'Was wearing'","substr","inven_dirty","world.py",126,sw("Was wearing")),
("startswith 'You destroy'","substr","inven_dirty; standing_on cleared","world.py",126,sw("You destroy")),
("startswith 'You feel'","substr","inven_dirty (stat change)","world.py",127,sw("You feel")),
("'in your pack' in","substr","inven_dirty","world.py",127,lambda t:"in your pack" in t),
(r"You have .*\([a-w]\)\.$","regex","standing_on='.' after pickup","world.py",129,lambda t:bool(re.match(r"You have .*\([a-w]\)\.$",t))),
("RE_HURT_OTHER","regex","explained_t: HP loss not from monster","world.py",82,lambda t:bool(RE_HURT.search(t))),
("RE_UNSEEN","regex","unseen attacker -> Flee/notify","world.py",76,lambda t:bool(RE_UNSEEN.match(t))),
("startswith 'You hear a door burst open'","substr","heard warn","world.py",136,sw("You hear a door burst open")),
("RE_ATTACK","regex","hits_taken/last_hit_t","world.py",71,lambda t:bool(RE_ATTACK.search(t))),
(r"^You (hit|miss|have slain|have destroyed|smite|bite|claw)","regex","fight_t","world.py",141,lambda t:bool(re.match(r"You (hit|miss|have slain|have destroyed|smite|bite|claw)",t))),
(r"^(The|It) .* (dies|is destroyed|flees)","regex","fight_t","world.py",142,lambda t:bool(re.match(r"(The|It) .* (dies|is destroyed|flees)",t))),
("startswith 'I see no up staircase'","substr","clear standing_on","world.py",144,sw("I see no up staircase")),
("startswith 'I see no down staircase'","substr","clear standing_on","world.py",146,sw("I see no down staircase")),
("startswith 'The air about you becomes charged'","substr","recall_pending","world.py",149,sw("The air about you becomes charged")),
("startswith 'A tension leaves the air around you'","substr","recall cancelled","world.py",151,sw("A tension leaves the air around you")),
("'yanked upwards'/'yanked downwards' in","substr","recalled direction","world.py",154,lambda t:"yanked upwards" in t or "yanked downwards" in t),
("startswith 'You have removed the rubble'","substr","dig success","mover.py",222,sw("You have removed the rubble")),
("'impossible'/'cannot' in","substr","dig failure","mover.py",230,lambda t:"impossible" in t or "cannot" in t),
("'blocking your way' in","substr","bumped obstacle","mover.py",316,lambda t:"blocking your way" in t),
("'rubble' in","substr","bump = rubble","mover.py",319,lambda t:"rubble" in t),
("startswith 'You have slain'/'You have destroyed' (+target)","substr","Hunt done","pilot.py",536,sw("You have slain","You have destroyed")),
("startswith You sold/bought/I don't want/You do not have enough/You cannot carry/You have no room/That item","substr","store verdict","pilot.py",761,sw("You sold","You bought","I don't want","You do not have enough","You cannot carry","You have no room","That item")),
("'The air about you becomes charged' in","substr","pending_use done (read WoR)","pilot.py",965,lambda t:"The air about you becomes charged" in t),
("startswith 'You have no room for'","substr","pack_full notify","pilot.py",1296,sw("You have no room for")),
(r"commands you to return|magic missile|fires an arrow|fires a bolt|mumbles","regex","minor unseen attack (on cause)","pilot.py",1686,lambda t:bool(re.search(r"commands you to return|magic missile|fires an arrow|fires a bolt|mumbles",t))),
]
if __name__=="__main__":
    with open("P2_patterns.csv","w",newline="") as f:
        w=csv.writer(f); w.writerow("pattern,kind,purpose,file,line".split(","))
        for n,k,pu,fi,l,_ in P: w.writerow([n,k,pu,fi,l])
        w.writerow(["startswith ('You enter a maze','Looks like','You feel','You hear','You have found') [exclusion]","substr","noise filter in agent 'said'","pilot.py",2175])
    rows=list(csv.DictReader(open("/projectnb/jbrcs/mangband/Advisor/data/messages/log_messages.csv")))
    tot=sum(int(r["count"]) for r in rows); print("total msgs distinct",len(rows),"count",tot)
    top=rows[:300]; tc=sum(int(r["count"]) for r in top)
    m=[];u=[]
    for r in top:
        hit=[p[0] for p in P if p[5](r["text"])]
        (m if hit else u).append((r,hit))
    print("top300 count",tc,"matched",sum(int(r['count']) for r,_ in m),len(m))
    print("share all count matched top300/ total", sum(int(r['count']) for r,_ in m)/tc, sum(int(r['count']) for r,_ in m)/tot)
    # which patterns matter
    import collections
    c=collections.Counter()
    for r,h in m:
        for x in h: c[x]+=int(r['count'])
    for k,v in c.most_common(): print(v,k)
    print("--- UNMATCHED")
    for i,(r,_) in enumerate(u): print(r["count"],r["text"])
    print("--- MATCHED")
    for r,h in m: print(r["count"],r["text"],"=>",h[:3])
