import csv,collections
rows=list(csv.DictReader(open('/projectnb/jbrcs/mangband/Advisor/data/monsters/monsters.csv')))
lv=collections.defaultdict(list)
for r in rows:
    for s in r['spells'].split('|'):
        if s: lv[s].append(int(r['level']))
M='melee2.c:'
def br(el,div,cap,eff,res,sav,line,flag):
    return (flag,'breath',f'm_hp/{div}',cap,el,eff,res,sav,f'{M}{line}; spells1.c project_p 3498+')
R=[]
A=R.append
A(('SHRIEK','innate','none (aggravate)','',  '', 'wake all monsters within 40 of player; monsters in LOS set to base speed+10 permanently','','', M+'566-574; spells2.c:3313-3360'))
for n,d in ((1,'1d6'),(2,'3d6'),(3,'5d6'),(4,'7d6')):
    A((f'ARROW_{n}','bolt (GF_ARROW)',d,'', 'arrow','none','nothing (no AC, no resist)','none (no save)',f'{M}{590+n*10}; spells1.c:3665'))
def B(flag,el,div,cap,eff,res,sav,line): A(br(el,div,cap,eff,res,sav,line,flag))
B('BR_ACID','acid',3,1600,'inventory damage (inv=1/2/3 items for dam<30/<60/else); armour piece -1 AC may halve dmg','resist_acid:(d+2)/3; oppose_acid: again (d+2)/3 (stack 1/9); immune: 0','none','634-645; spells1.c:990')
B('BR_ELEC','elec',3,1600,'inventory damage (set_elec_destroy)','resist/oppose elec each (d+2)/3; immune 0','none','647-658; spells1.c:1015')
B('BR_FIRE','fire',3,1600,'inventory damage (set_fire_destroy)','resist/oppose fire each (d+2)/3; immune 0','none','660-671; spells1.c:1039')
B('BR_COLD','cold',3,1600,'inventory damage (set_cold_destroy)','resist/oppose cold each (d+2)/3; immune 0','none','673-684; spells1.c:1061')
B('BR_POIS','pois',3,800,'poisoned += randint0(dam)+10 unless resist_pois or oppose_pois','resist_pois/oppose_pois each (d+2)/3','none','686-697; spells1.c:3640')
B('BR_NETH','nether',6,550,'exp drain: not hold_life: 200+(exp/100)*2; hold_life: 75% block else 200+(exp/1000)*2','resist_neth: d*6/(1d6+6) and no exp drain','none','699-710; spells1.c:3682')
B('BR_LITE','light',6,400,'blind += randint1(5)+2 if not already blind and not resist_blind','resist_lite: d*4/(1d6+6), no blind','none','712-723; spells1.c:3846')
B('BR_DARK','dark',6,400,'blind += randint1(5)+2 if not already blind and not resist_blind','resist_dark: d*4/(1d6+6), no blind','none','725-736; spells1.c:3860')
B('BR_CONF','confusion',6,400,'confused += randint1(20)+10','resist_conf: d*5/(1d6+6), no confusion','none','738-749; spells1.c:3787')
B('BR_SOUN','sound',6,500,'stun += randint1(dam>90?35:dam/3+5)','resist_sound: d*5/(1d6+6), no stun','none','751-762; spells1.c:3772')
B('BR_CHAO','chaos',6,500,'confused += randint0(20)+10 (unless rConf/rChaos); hallucinate += randint1(10) unless rChaos; exp drain unless rNether/rChaos: 5000+(exp/100)*2 (hold_life 75% block else 500+(exp/1000)*2)','resist_chaos: d*6/(1d6+6) and blocks all three effects; rConf blocks confusion; rNether blocks exp drain','none','764-775; spells1.c:3723')
B('BR_DISE','disenchant',6,500,'apply_disenchant: random one of 8 equip slots loses a plus','resist_disen: d*6/(1d6+6), no disenchant','none','777-788; spells1.c:3801,1303')
B('BR_NEXU','nexus',6,400,'apply_nexus 1d7: 1-3 teleport(200); 4-5 teleport player TO breather; 6 teleport-level (save); 7 swap two stats (save)','resist_nexus: d*6/(1d6+6), no effect','skill_sav only vs outcomes 6 and 7','790-801; spells1.c:3815,1400')
B('BR_TIME','time',3,150,'1d10: 1-5 lose_exp(100+(exp/100)*2); 6-9 one random stat_cur*3/4 (min 3); 10 all six stats*3/4','none (no resist, no hold_life check)','none','803-813; spells1.c:3874')
B('BR_INER','inertia',6,200,'slow += randint0(4)+4','none (free action does NOT help)','none','815-825; spells1.c:3839')
B('BR_GRAV','gravity',3,200,'slow += randint0(4)+4; teleport(5) if randint1(127)>plev; stun += randint1(dam>90?35:dam/3+5) unless rSound','rSound blocks stun only; nothing reduces dmg','none','827-837; spells1.c:3918')
B('BR_SHAR','shards',6,500,'cut += dam (unless resist_shard)','resist_shard: d*6/(1d6+6), no cut','none','839-850; spells1.c:3758')
B('BR_PLAS','plasma',6,150,'stun += randint1(dam>40?35:dam*3/4+5) unless rSound','nothing reduces dmg; rSound blocks stun','none','852-862; spells1.c:3671')
B('BR_WALL','force',6,200,'stun += randint1(20) unless rSound','nothing reduces dmg; rSound blocks stun','none','864-874; spells1.c:3829')
A(('BR_MANA','breath','NO-OP (case empty)','','mana','none','','',M+'876-881 ("XXX XXX XXX"); no monster.txt entry uses it'))
A(('BOULDER','bolt (GF_BOULDER)','damroll(1+level/7,12)','','boulder','NONE: project_p has no GF_BOULDER case -> default dam=0 (no take_hit)','n/a','n/a',M+'901-908; spells1.c:3613-4093 (no case), 4086-4092 default; mdefines.h:1891'))
BA='ball r2 (r3 if POWERFUL)'
def Ba(flag,el,f,line,eff='',res='',sav='none'): A((flag,BA,f,'',el,eff,res,sav,f'{M}{line}'))
Ba('BA_ACID','acid','randint1(rlev*3)+15','913-923','as BR_ACID','as BR_ACID')
Ba('BA_ELEC','elec','randint1(rlev*3/2)+8','925-935','as BR_ELEC','as BR_ELEC')
Ba('BA_FIRE','fire','randint1(rlev*7/2)+10','937-947','as BR_FIRE','as BR_FIRE')
Ba('BA_COLD','cold','randint1(rlev*3/2)+10','949-959','as BR_COLD','as BR_COLD')
Ba('BA_POIS','pois','damroll(12,2)','961-971','as BR_POIS','as BR_POIS')
Ba('BA_NETH','nether','50+damroll(10,10)+rlev','973-983','as BR_NETH','as BR_NETH')
Ba('BA_WATE','water','randint1(rlev*5/2)+50','985-1000','stun += randint1(40) unless rSound; confused += randint1(5)+5 unless rConf','rSound/rConf block effects only; dmg unreduced')
Ba('BA_MANA','mana','rlev*5+damroll(10,10)','1002-1011','none','none (pure dmg)')
Ba('BA_DARK','dark','rlev*5+damroll(10,10)','1013-1023','blind += randint1(5)+2 unless rBlind','resist_dark d*4/(1d6+6)')
A(('DRAIN_MANA','spell','no damage; r1=randint1(rlev)/2+1 mana drained, monster heals 6*r1 if hurt','','mana','csp-=r1 (nothing if csp==0)','none','none',M+'1025-1081'))
A(('MIND_BLAST','spell','damroll(8,8)','','psionic','confused += randint0(4)+4 unless rConf','none','skill_sav% -> no effect',M+'1083-1111'))
A(('BRAIN_SMASH','spell','damroll(12,15)','','psionic','blind 8+randint0(8) unless rBlind; confuse randint0(4)+4 unless rConf; paralyse randint0(4)+4 unless free_act; slow randint0(4)+4 ALWAYS (no FA check)','none (each effect has its own resist)','skill_sav% -> whole spell fails',M+'1113-1149'))
for n,d,x in ((1,'damroll(3,8)',''),(2,'damroll(8,8)',''),(3,'damroll(10,15)',''),(4,'damroll(15,15)','cut += damroll(10,10)')):
    A((f'CAUSE_{n}','spell',d,'','wound',x,'none','skill_sav% -> no effect',f'{M}{1151+(n-1)*18}'))
BO='bolt (stops at first monster/player)'
def Bo(flag,el,f,line,eff='',res=''): A((flag,BO,f,'',el,eff,res,'none',f'{M}{line}'))
Bo('BO_ACID','acid','damroll(7,8)+rlev/3','1224-1234','as BR_ACID','as BR_ACID')
Bo('BO_ELEC','elec','damroll(4,8)+rlev/3','1236-1246','as BR_ELEC','as BR_ELEC')
Bo('BO_FIRE','fire','damroll(9,8)+rlev/3','1248-1258','as BR_FIRE','as BR_FIRE')
Bo('BO_COLD','cold','damroll(6,8)+rlev/3','1260-1270','as BR_COLD','as BR_COLD')
A(('BO_POIS','bolt','NO-OP (case empty)','','pois','none','','',M+'1272-1277; no monster.txt entry uses it'))
Bo('BO_NETH','nether','30+damroll(5,5)+rlev*3/2','1279-1289','as BR_NETH','as BR_NETH')
Bo('BO_WATE','water','damroll(10,10)+rlev','1291-1300','as BA_WATE','rSound/rConf block effects only')
Bo('BO_MANA','mana','randint1(rlev*7/2)+50','1302-1311','none','none')
Bo('BO_PLAS','plasma','10+damroll(8,7)+rlev','1313-1322','stun as BR_PLAS','rSound blocks stun only')
Bo('BO_ICEE','ice','damroll(6,6)+rlev','1324-1334','cold_dam (inventory dmg) + cut damroll(5,8) unless rShard + stun randint1(15) unless rSound','resist/oppose cold on dmg; rShard/rSound on effects')
Bo('MISSILE','missile','damroll(2,6)+rlev/3','1336-1345','none','none')
A(('SCARE','spell','none','','','afraid += randint0(4)+4','resist_fear','skill_sav%',M+'1347-1369'))
A(('BLIND','spell','none','','','set_blind(12+randint0(4)) (SET, not add)','resist_blind','skill_sav%',M+'1371-1392'))
A(('CONF','spell','none','','','confused += randint0(4)+4','resist_conf','skill_sav%',M+'1394-1415'))
A(('SLOW','spell','none','','','slow += randint0(4)+4','free_act','skill_sav%',M+'1417-1437'))
A(('HOLD','spell','none','','','paralysed += randint0(4)+4','free_act','skill_sav%',M+'1439-1460'))
A(('HASTE','self','none','','','mspeed+=10 if <base+10; else +2 if <base+20 (cumulative, never decays)','','',M+'1464-1492'))
A(('HEAL','self','hp += rlev*6 (to maxhp); clears fear; no-op at full HP','','','','','',M+'1500-1566'))
A(('BLINK','self','none','','','teleport_away(m,10): lands 5-10 grids away','','',M+'1574-1581; spells1.c:75'))
A(('TPORT','self','none','','','teleport_away(m,45): lands 22-45 grids away','','',M+'1583-1590'))
A(('TELE_TO','spell','none','','','teleport_player_to(monster pos): player lands adjacent to caster','NONE','NONE (no save, no FA)',M+'1604-1612; spells1.c:286'))
A(('TELE_AWAY','spell','none','','','teleport_player(100): player lands 50-100 grids away','NONE','NONE',M+'1614-1626; spells1.c:167'))
A(('TELE_LEVEL','spell','none','','','teleport_player_level: 50% down/up (always down in town; ironman/arena: nothing); up if at MAX_DEPTH-1 or quest level','resist_nexus','skill_sav%',M+'1628-1649; spells1.c:365'))
A(('DARKNESS','spell','none','','','unlite_area(0,3): darkens room/grids radius 3; self-projected so NO damage and NO blind to player','none needed','',M+'1657-1666; spells2.c:4562; spells1.c:3540'))
A(('TRAPS','spell','none','','','trap_creation: place_trap on naked floor grids in radius 1 (player grid itself excluded: occupied)','none','none (no save)',M+'1668-1678; spells2.c:4919; spells1.c:1894'))
A(('FORGET','spell','none','','','lose_all_info: unsets known/felt flags on inventory items w/o ID_MENTAL, forgets map (wiz_dark)','none','skill_sav%',M+'1680-1696; spells2.c:1064'))
S={'S_KIN':(6,'same display char as caster, non-unique','SUMMON_KIN',1716),
'S_HI_DEMON':(8,"'U' (uniques allowed)",'SUMMON_HI_DEMON',1734),
'S_MONSTER':(1,'any monster (uniques allowed)','0',1752),
'S_MONSTERS':(8,'any monster (uniques allowed)','0',1767),
'S_ANIMAL':(6,'RF3_ANIMAL non-unique','SUMMON_ANIMAL',1782),
'S_SPIDER':(6,"'S' non-unique",'SUMMON_SPIDER',1797),
'S_HOUND':(6,"'C' or 'Z' non-unique",'SUMMON_HOUND',1812),
'S_HYDRA':(6,"'M' non-unique",'SUMMON_HYDRA',1827),
'S_ANGEL':(1,"'A' non-unique",'SUMMON_ANGEL',1842),
'S_DEMON':(1,'RF3_DEMON non-unique','SUMMON_DEMON',1857),
'S_UNDEAD':(1,'RF3_UNDEAD non-unique','SUMMON_UNDEAD',1872),
'S_DRAGON':(1,'RF3_DRAGON non-unique','SUMMON_DRAGON',1887),
'S_HI_UNDEAD':(8,"'L','V','W' (uniques allowed)",'SUMMON_HI_UNDEAD',1902),
'S_HI_DRAGON':(8,"'D' (uniques allowed)",'SUMMON_HI_DRAGON',1920),
'S_WRAITH':(16,"8x 'W' UNIQUE + 8x 'L/V/W'",'SUMMON_WRAITH+HI_UNDEAD',1938),
'S_UNIQUE':(16,"8x any UNIQUE + 8x 'L/V/W'",'SUMMON_UNIQUE+HI_UNDEAD',1960)}
for f,(n,k,t,l) in S.items():
    A((f,'summon',f'{n} attempts of summon_specific(Depth,player_y,player_x,rlev,{t}): kinds={k}','', 'summons','monsters placed AWAKE within 1-2 grids of the PLAYER; level target (Depth+rlev)/2+5; FRIENDS/ESCORT species arrive as groups','none','none',f'{M}{l}; monster2.c:2552-2594'))
out='/projectnb/jbrcs/mangband/Advisor/studies/2026-10-23-rulebook/scratch/K2/K2_spells.csv'
with open(out,'w',newline='') as f:
    w=csv.writer(f); w.writerow(['flag','kind','damage_formula','cap','element','side_effects','resisted_by','saved_by','cite','n_monsters_lv0_70','min_level','max_level'])
    for r in R:
        v=lv.get(r[0],[]); v70=[x for x in v if x<=70]
        cap=r[3]
        if r[0].startswith('BR_') and cap=='' and 'NO-OP' not in r[2]: pass
        w.writerow(list(r)+[len(v70),min(v) if v else '',max(v) if v else ''])
print(len(R))
