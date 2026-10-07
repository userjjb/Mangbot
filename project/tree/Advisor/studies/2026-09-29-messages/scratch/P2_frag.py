import csv,re
from P2_match import *
rows=list(csv.DictReader(open("/projectnb/jbrcs/mangband/Advisor/data/messages/log_messages.csv")))
def show(name,fn,lim=40):
    print("==",name)
    for r in rows:
        if fn(r["text"]): print(r["count"],r["text"])
show("HURT_OTHER all",lambda t:RE_HURT.search(t))
show("UNSEEN all",lambda t:RE_UNSEEN.match(t))
show("Unseen-ish (It/Something) not matched",lambda t:re.match(r"(It|Something|Someone) ",t) and not RE_UNSEEN.match(t))
show("attack-ish not RE_ATTACK: 'you.' ending",lambda t:re.search(r" you[.!]$",t) and not RE_ATTACK.search(t) and not t.startswith("You"))
show("breath/casts/shoot/spell",lambda t:re.search(r"breathes|casts|fires|shoots|conjures|throws|hurls|drains|magically|blinks|teleport|commands",t))
show("You... status",lambda t:re.match(r"You (are|feel|can|have been|resist|failed|cannot|can't)",t) and not t.startswith("You feel"))
show("You feel all",lambda t:t.startswith("You feel"))
show("You have all non-found",lambda t:t.startswith("You have ") and not t.startswith("You have slain"))
show("blind/paral/afraid/confus",lambda t:re.search(r"blind|paraly|afraid|confus|frighten|terrif|slow|stun|hungry|weak|faint|starv",t,re.I))
show("miss/hit others",lambda t:re.search(r" hit[!.]|missed|dodge|resist|unaffected",t))
show("dies/destroyed/flees",lambda t:re.search(r"dies|destroyed|flees|screams|shrugs|dead|disintegr|cries out",t))
show("stairs/level",lambda t:re.search(r"stair|level|trapdoor|fall|floor|teleport|recall|air about|tension",t,re.I))
