import pickle,csv,json,collections
from common import *
rows=pickle.load(open('rows.pkl','rb'))
# labels: idx -> (class, outcome, verdict, better)
L={
0:("band (3-4 Black orc archers + breeding Silver mice)","recalled (WoR 14:13:02, yanked 14:13:18)","could_improve","WoR came 4 s after the first Phase, fine; the 3 CLW (15 HP each vs 7-16 HP/s loss, object.txt:2009) were net-zero waste. Phase + WoR then CCW only would save ~70-100g. Old (10-16) rules; minor."),
1:("one strong (Nighthawk, lvl 8, +10 speed)","killed it (hunt order 18:55:05)","could_improve","Navigator journal: Pilot kept walking (free hits from a fast flyer) 215->102 HP and spent 2 CLW + 1 Phase; 'hunt Nighthawk' killed it at once. Stand and fight a fast weak monster instead of walking/phasing."),
2:("status attacker (Wormtongue: blind, steals, teleports)","he stole 28 gold and teleported away","rules_fine","One CLW (24g). CLW also cures blindness."),
3:("band + unique (Ufthak, 11 Hill orcs, Black orcs, Snaga)","recalled (WoR 19:09:01, yanked 19:09:12)","rules_fine","4 Phase + 2 CSW + WoR while recall charged; stairs 41+ squares away. Reasonable."),
4:("ranged/summoner (Ranger, hunt ordered by Navigator at full HP)","recalled (WoR 22:24:49 at HP 96, yanked 22:24:58)","could_improve","HP 160->66 in 3 s (Ranger arrows + Copperhead + Black harpy). Pilot's WoR at 96 (44%) was right; the avoidable part was the Navigator's 'hunt Ranger' order against a lvl-20 archer/summoner (Pilot had already vetoed it once)."),
5:("status attacker (confusion) in a yeek swarm","kept fighting","unclear","1 CSW (50g) at 97% HP vs 8 harmless adjacent yeeks; CLW cures confusion too (24g) or fight on."),
6:("mixed crowd (13 Brown/Blue yeeks + Orfax)","killed Orfax, stayed","unclear","2 Phase 'group danger 93 vs 150' counted all 13 yeeks as full attackers; yeeks hit for ~5. Phases probably unnecessary, but HP did reach 44%."),
7:("band (Snaga x3, Uruk x2, Black orc, Kobold archers)","fought it out, rested","rules_fine","1 Phase + 1 CCW then melee; HP min 46%. Cheap."),
8:("mixed crowd/mob woken in Orfax's loot room (22 in view, 8 adjacent)","recalled (Pilot WoR 01:54:44 'last resort', Navigator Teleportation 01:54:46, yanked 01:54:49)","could_improve","6 Phase + 7 cures (4 CCW, 3 CLW) in 30 s with 5-8 monsters adjacent after each landing; min 61/241 (25%). Teleportation (Navigator had it) or WoR at the 01:54:34 'third emergency in 90 s' alert, ~10 s and ~5 Phase + 4 CCW earlier."),
9:("band (7 Novice paladins + 2 White wolves; afraid)","recalled (WoR 02:00:19, yanked 02:00:38)","unclear","Pilot read WoR at once (group danger 140 vs 134) then 5 Phase/2 CCW/1 CSW/1 CLW in 19 s; Navigator quaffed Heroism for the fear. Cheap monsters (paladins lvl ~8); fear cure first and fighting at a corridor is the alternative; cannot judge."),
10:("mixed crowd (Boldor + Master yeeks + Druid + centipede), blind/poison/fear","recalled (WoR 02:05:52, yanked 02:06:04)","rules_fine","WoR + 2 Phase + 4 cures; HP min 50%. Arrival-area crowd; fine."),
11:("band (6 White wolves + Clear hounds + Pseudo-dragon)","phased once, wolves lost us, rested","rules_fine","1 Phase (20g) at 159/246 then rest."),
12:("band + summoner (14 Hill orcs, Gnome mage, zombies)","recalled (Navigator read WoR 02:12:11, yanked 02:12:25) after 5 stair hops","could_improve","Ran out of Phase (6 used); Pilot did not read WoR; Navigator did 31 s after the episode began. WoR at the first 'no stairs known' (02:11:40) would have saved ~4 Phase + 2 cures."),
13:("status attacker (Dark elven priest: confusion)","kept fighting","rules_fine","1 CSW at 97% HP (CLW would do)."),
14:("arrival ambush (Orc captain, Half-orcs, Orc shamans, Novice paladin at 650 ft)","recalled (WoR 22:26:46, yanked 22:26:58)","rules_fine","WoR + 1 Phase + 1 CLW; min 47%."),
15:("band (Black orcs, Snaga, Orc shamans, Uruk at 600 ft)","recalled (WoR 12:27:09 at 235/265, yanked 12:27:28)","rules_fine","Only a WoR (200g); min 58% while it charged (19 s)."),
16:("band (5 Cave spiders + Novice priests), precaution","stairs > at 100% HP","rules_fine","Cost 0; level left."),
17:("status attacker (Novice mages: blind)","kept fighting","rules_fine","1 CSW at 95% HP (CLW would do)."),
18:("band (4 Novice rogues), precaution","stairs > at 100% HP","rules_fine","Cost 0; may be over-cautious for a clvl-22 warrior but free."),
19:("band (2 Snaga + bat), HP 65%","stairs <","rules_fine","Cost 0."),
20:("status attacker (4 Novice mages: blind, confused)","kept fighting","could_improve","2 CSW (100g) at >=95% HP; CLW (24g) cures both, or just melee on."),
21:("arrival ambush loop (Ibun, unique, 820 HP, 3x3d6 + disenchant)","left by stairs; Navigator stopped the plan 02:32:37","could_improve","23 round trips of < and > in 71 s; each '>' landed adjacent to Ibun (8+ times 'arrived next to Ibun'); HP min 63%, armour/Spear disenchanted (Navigator). No consumables, but the Pilot kept re-taking the same stair pair. After the 2nd arrival next to him: walk away on the upper level or choose another stair / WoR."),
22:("arrival ambush (Ibun again, 2 min later)","stairs <","rules_fine","Cost 0 (HP -31). Same Ibun trap as #21."),
23:("band (Cave spider + Hill orc), precaution","stairs < at 100% HP","rules_fine","Cost 0, loses the level."),
24:("band flag with 0 monsters in view, precaution","stairs < at 100% HP","rules_fine","Cost 0; trip 'band' condition."),
25:("summoned by a trap (smoke trap): Nar the Dwarf (450 HP unique) + Orc shaman + Giant salamander + Wolf + invisible WIS-drainer","recalled (WoR 02:57:34, yanked 02:57:51)","rules_fine","Pilot fought and killed 4 of 5 while at 158-270 HP; Phase x2 + 2 CSW + WoR. Speed (4 in pack) not used: the Speed-first rule is from 10-25. Min 43%."),
26:("band flag (Illusionist: paralyses, no Free Action), precaution","stairs < at 100% HP","rules_fine","Cost 0."),
27:("one strong (Umber hulk, confuses), precaution","stairs < at 97% HP","rules_fine","Cost 0."),
28:("mixed (Homunculus: paralyse touch, 2 Wolves, Large kobold)","recalled (WoR 03:10:44 at 270/270, yanked 03:11:03)","unclear","WoR (200g) at 100% HP vs 3 weak monsters, one with a paralysing touch and no Free Action. Alternatives: kill the Homunculus (8d8 HP) first / Phase. Not judgeable."),
29:("band (4 Energy hounds + Cave bear)","recalled (WoR 03:14:38 at 283/283, yanked 03:14:47)","unclear","WoR at full HP; min 77%. Fire/Energy hounds die in ~1 s each in m30 melee, so fighting on is plausible, but 3 adjacent breathers cost 66 HP in 5 s. This was the 2nd of 3 full-HP WoR escapes in 7 min that drained m26's WoR stock."),
30:("status attacker (Dark elven mage: blind)","kept fighting","rules_fine","1 CSW at 85% HP."),
31:("band (7 Novice paladins; afraid)","recalled (WoR 03:17:37 at 229/283, yanked 03:17:56)","could_improve","Pilot first said '5 monsters together but weak: fighting on', then afraid -> kiting -> WoR (200g). 5 Heroism in pack: cure fear (Heroism/Boldness) and melee the weak band instead of a 200g recall + lost trip."),
32:("summoners + mixed crowd (Boldor + Master yeeks, Bullroarer, Dark hounds, Orc/Kobold shamans, louse; blind/confused/poison/slow)","recalled (WoR read 03:22:28, stairs hop x4 at 51 HP, yanked 03:23:54)","could_improve","WORST: min 40/283 (14%). (a) 7 CCW + 4 CSW + 3 Phase actually consumed (message counts; 5 'resend (no effect seen)' commands executed as extra potions/scroll because command latency was 12-19 s); potion spam (CSW/CCW) while 'Full' -> 'You have gorged yourself' 3 times = slow (-10; Navigator: speed -20 with slow spell); (b) Speed first only at 03:22:21 by Navigator, 74 s in, and it was quaffed twice (2 Speed spent; first took effect 14 s after the command); (c) 'resend (no effect seen)' duplicated a Phase and a CCW; (d) first WoR 03:22:16 did not register, second 03:22:28; (e) 8 cures + 3 Phase were only net-positive for 1-2 turns each against 6-8 adjacent. Better: Speed at 03:21:40 (low HP), WoR at the first alert (03:21:05 'flee (band)'), no cures for blind/confusion with CSW/CCW, Phase then WoR, no duplicates."),
33:("band (6 Ogres + Crebain, 4 adjacent)","recalled (WoR 04:25:41 at 268/283, yanked 04:26:04)","unclear","HP 268->133 in 8 s with 4 ogres adjacent (-25 HP/s); 2 Phase + CCW + CSW while recall charged 23 s; 4 Speed unused (pre 10-25 rule). A Speed potion + Phase first is the plausible better order; cannot verify."),
34:("status attacker (Dark elven priest: confusion)","kept fighting","rules_fine","1 CSW at 78%."),
35:("status/paralysis attacker (Illusionist) precaution","stairs > at 100%","rules_fine","Cost 0."),
36:("band (4 Cave orcs, 4 Black orcs, Uruk, Snaga, Hill orc; 5 adjacent)","recalled (Navigator goal recall + WoR 05:31:14, yanked 05:32:07: 53 s)","unclear","WoR read at 152/288 as a trip command, then 3 Phase + 3 CSW while it charged (min 45%). 2 Speed unused (pre 10-25 rule). Fighting the weak orcs from a corridor is the alternative."),
37:("ranged/breath (Baby green dragon: poison breath)","killed it","could_improve","3 CCW (~450g) in 8 s to cure poison after each of 3 breaths, each cure a turn not attacking; dragon died 3 s after the last. Ignore poison and melee."),
38:("one strong (Stegocentipede, fast)","killed it, rested","rules_fine","No consumables; min 57%."),
39:("ranged/status (2 Light hounds: blindness breath)","kept fighting","rules_fine","1 CSW at 79% (CLW would do)."),
40:("ranged/status (3 Light hounds + Orc shaman: blindness)","kept fighting","could_improve","CLW + 2 CSW (~124g) over 10 s for blindness that the next breath re-applies, at >=73% HP vs 6d6-HP hounds: melee on."),
41:("mixed crowd + summoner (Druid summons animals; HOLD/paralysis, slow, blind, bolts; Umber hulk, Fire/Energy hounds, Wolves, Yeti, Griffon, harpy)","recalled (WoR read 06:43:49, yanked 06:44:21)","could_improve","See Q4. Root cause: Druid (78 HP, 1_IN_3 casts) never targeted; the 2nd Teleportation (06:43:41) re-landed beside the hounds; fire burned 3 WoR + Phase scrolls."),
42:("band (4 Ogres adjacent), full HP","recalled (WoR 07:46:45 at 269/303, yanked 07:46:49)","unclear","WoR at 89% HP; only -24 HP before the yank 4 s later (recall activated fast). 200g."),
43:("one strong (Nar the Dwarf, 450 HP) + blind/drain (Moaning spirit DEX drain at arrival)","recalled (WoR 08:10:14 'potions too weak', stairs < 08:10:21, yanked 08:10:25)","rules_fine","Speed first worked (08:09:49, HP 141); Phase, 2 CSW, 1 CCW, WoR; min 43%. Navigator wanted to go home anyway (DEX)."),
44:("status attacker (Dark elven priest, Novice priests: blind)","kept fighting","rules_fine","1 CSW at 86%."),
45:("status attacker (Dark elven priest: blind)","kept fighting","rules_fine","1 CSW at 75%."),
46:("band (6 Hill orcs), precaution","stairs > at 100%","rules_fine","Cost 0."),
}
PR=dict(Phase=20,CLW=24,CSW=50,CCW=150,**{'CCW(by hand)':150},Speed=75,Heroism=35,Boldness=20,Teleport=40,WoR=200,Berserk=60)
def gold(c):
    return sum(PR.get(k,0)*v for k,v in c.items() if k not in('stairs','quaff?','read'))
out=[]
for i,r in enumerate(rows):
    c=L[i]
    cons=dict(r['cons']);
    if 'quaff?' in cons: cons['CCW(by hand)']=cons.get('CCW(by hand)',0)+cons.pop('quaff?')
    if i==32: cons={'CSW':4,'CCW':7,'Phase':3,'Speed':2,'Heroism':1,'WoR':1,'stairs':4}  # from 'You have N ...' messages (resends executed as extra reads/quaffs)
    r['cons']=cons
    out.append(dict(idx=i,mission=r['mission'],start=r['start'],depth_ft=r['depth_ft'],hp_start=r['hp_start'],hp_start_pct=r['hp_start_pct'],hp_min=f"{r['hp_min']}/{r['hp_max']}",hp_min_pct=r['hp_min_pct'],min_time=r['min_time'],duration_s=r['dur_s'],
        monsters_max_count_in_view=r['monsters'],adjacent_at_min=r['adj_at_min'],max_adjacent=r['max_adjacent'],status_msgs=json.dumps(r['status']),
        actions_in_order=r['actions'],consumables=json.dumps(cons),gold_est=gold(cons),danger_class=c[0],outcome=c[1],verdict=c[2],better_option=c[3]))
with open('episodes.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(out[0].keys()));w.writeheader();w.writerows(out)
pickle.dump(out,open('out.pkl','wb'))
# tallies
import statistics
bym=collections.defaultdict(list)
for o in out:bym[o['mission']].append(o)
dm={}
for m in range(17,35):
    d=json.load(open(f'/projectnb/jbrcs/mangband/runs/pilot/dive04/scorecards/m{m}.json'));dm[f'm{m}']=d['B']['dungeon_min']
print('mission n  strict(<60%) <40% <50% dungeon_min eps/dhour gold')
tot=collections.Counter();totg=0
for m in sorted(dm,key=lambda x:int(x[1:])):
    es=bym.get(m,[]);st=[e for e in es if e['hp_min_pct']<60];
    g=sum(e['gold_est'] for e in es)
    cc=collections.Counter()
    for e in es:
        for k,v in json.loads(e['consumables']).items():cc[k]+=v
    tot.update(cc);totg+=g
    print(m,len(es),len(st),sum(1 for e in es if e['hp_min_pct']<40),sum(1 for e in es if e['hp_min_pct']<50),dm[m],round(len(es)/(dm[m]/60),1) if dm[m] else '',g,dict(cc))
print(tot,totg)
print(collections.Counter(o['verdict'] for o in out))
print('strict',sum(1 for o in out if o['hp_min_pct']<60),'cure/escape-only(>=60)',sum(1 for o in out if o['hp_min_pct']>=60))
print('total dungeon min',sum(dm.values()))
