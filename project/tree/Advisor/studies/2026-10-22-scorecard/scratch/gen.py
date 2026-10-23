import csv,sys
from common import *
from objcost import K
import sales2
rows_out=[]
def add(m,e,cat,item,rec,est,how,ev):
    short=max(0,round(est)-rec) if est is not None else ''
    rows_out.append([m,'%.1f'%e,hm(e),cat,item,rec,'' if est is None else round(est),short,how,ev])
# forced goals
forced=[]
for d in decisions():
    if d['kind']=='nav_cmd' and d['cmd']=='goal' and any(a.startswith('!') for a in d['args']):
        forced.append((d['t'],[a for a in d['args'] if a.startswith('!')]))
FORCED_ITEMS=('Potion of Infravision','Ring of Feather Falling','Rod of Trap Location','Lucerne Hammer of Venom','Staff of Perception','Staff of Door/Stair Location','Staff of Sleep Monsters','Rod of Light','Boots of Free Action')
def is_forced(e,item=''):
    if 'Feather Falling' in item and e>1792209000: return False
    return any(0<=e-t<=25 for t,_ in forced) and any(x in item for x in FORCED_ITEMS)
# a. sales
manual_est={'a Scroll of Light':15*.39,'a Potion of Salt Water':0,'a Set of Leather Gloves [1,+0]':None,'a Dagger (1d4) (+0,+0)':None,'a Scroll of Blessing':None,'a Hard Leather Cap [2,-2]':0,'a Potion of Sickliness':0}
for (mi,e,item,got,sn,own,A,S,V,exp,src) in sales2.rows:
    if exp is None:
        est=got if item in('a Set of Leather Gloves [1,+0]','a Dagger (1d4) (+0,+0)','a Scroll of Blessing') else None
        how='known cheap item; paid cost x S (no loss)'
    else:
        est=exp; how='true value V=%d (%s) x S=%d%% (owner %s, CHR3)'%(V,src,S,own)
    cat='a_sale'
    if est is not None and round(est)-got>=25: cat='a_sale_SHORT'
    if is_forced(e,item): how+='; FORCED with !'
    if item=='a Scroll of Teleportation': how+='; ESCAPE ITEM not sold in stores'; cat='a_sale_SHORT_irreplaceable'
    if 'Free Action' in item: cat='a_sale_SHORT_irreplaceable'
    add(mi,e,cat,item,got,est,how,'events.jsonl "You sold ..." %.0f (store %s %s)'%(e,sn,own))
# manual rows
def T(s):
    return time.mktime(time.strptime(s,'%Y-%m-%d %H:%M:%S'))
S35=.35
man=[
# destroys (m, time, item, est, how)
(17,'2026-10-16 14:10:39','You destroy a Pair of Hard Leather Boots [3] {worthless}',0,'worthless'),
(17,'2026-10-16 14:23:36','You destroy a Cloak [1] {cursed}',0,'cursed=0'),
(17,'2026-10-16 14:35:45','You destroy a Rodent Skeleton',0,'junk'),
(18,'2026-10-16 18:48:52','You destroy a Wand of Heal Monster',0,'cost 0'),
(18,'2026-10-16 18:54:13','You destroy Soft Studded Leather [5] {average}',14,'cost 35 x 0.4'),
(19,'2026-10-16 22:20:53','You destroy a Filthy Rag [1] {average}',0,'cost 0'),
(19,'2026-10-16 22:32:20','You destroy 2 Potions of Slowness',0,'cost 0'),
(19,'2026-10-16 22:32:43','You destroy a Cutlass (1d7) {average}',34,'cost 85 x 0.4'),
(19,'2026-10-16 22:32:49','You destroy a Cloak [1,+0]',1,'cost 3'),
(19,'2026-10-16 22:32:53','You destroy a Ring of Teleportation {cursed}',0,'cursed=0 (autodestroy)'),
(20,'2026-10-16 23:45:41','You destroy a Ring of Teleportation {cursed}',0,'cursed=0 (autodestroy)'),
(20,'2026-10-16 23:46:06','You destroy 20 Rounded Pebbles (1d2) {average}',20,'38 pebbles sold for 38 earlier (1 each)'),
(20,'2026-10-17 00:05:27','You destroy a Cutlass (1d7) {average}',34,'cost 85 x 0.4'),
(20,'2026-10-17 00:05:28','You destroy a Black Mushroom',0,'~0'),
(20,'2026-10-17 00:07:41','You destroy a Wrinkled Mushroom',0,'~0'),
(20,'2026-10-17 00:08:23','You destroy Soft Leather Armour [4] {cursed}',0,'cursed=0 (autodestroy)'),
(20,'2026-10-17 00:12:12','You destroy a Clotted Red Potion (=Clumsiness)',0,'worthless'),
(20,'2026-10-17 00:14:26','You destroy a Potion of Water',0,'0'),
(21,'2026-10-17 00:59:42','You destroy a Small Metal Shield [3,-1]',0,'negative to_a = worthless; shop said "I don\'t want that!"'),
(21,'2026-10-17 01:04:32','You destroy a Human Skeleton',0,'junk'),
(21,'2026-10-17 01:09:58','You destroy a Potion of Water',0,'0'),
(21,'2026-10-17 01:11:52','You destroy a Wand of Heal Monster',0,'cost 0'),
(21,'2026-10-17 01:20:52','You destroy a Scroll titled "munger toxmung" (=Summon Undead)',0,'worthless'),
(21,'2026-10-17 01:20:53','You destroy a Robe [2]',2,'cost 4'),
(21,'2026-10-17 01:21:15','You destroy Hard Studded Leather [7] {average}',78,'cost 200 x S 0.39 (Navigator said "sells ~10": wrong)'),
(21,'2026-10-17 01:31:27','You destroy a Set of Leather Gloves [1] {average}',1,'cost 3'),
(22,'2026-10-17 01:50:31','You destroy a Ring of Teleportation {cursed}',0,'cursed=0'),
(22,'2026-10-17 01:50:46','You destroy a Rod of Trap Location',33,'known cost 100 x S 0.25-0.40 (shop paid 23 unknown / 25 known at Luthien)'),
(22,'2026-10-17 01:51:28','You destroy a Short Bow (x2)',17,'cost 50 x 0.35 (unknown plusses)'),
(22,'2026-10-17 01:52:37','You destroy an Awl-Pike (1d8) {cursed}',0,'cursed=0'),
(22,'2026-10-17 01:52:42','You destroy a Metal Cap [3] {average}',12,'cost 30 x 0.4'),
(22,'2026-10-17 01:54:03','You destroy a Flail (2d6) [runes unknown, no feeling]',124,'cost 353 x 0.35 base; a similar unmarked Awl-Pike turned out (+2,+4) and sold 310'),
(22,'2026-10-17 01:54:49','You destroy a Pair of Hard Leather Boots [3] {cursed}',0,'cursed=0'),
(22,'2026-10-17 02:01:20','You destroy an Amulet of Teleportation {cursed}',0,'cursed=0'),
(22,'2026-10-17 02:01:20','You destroy a Long Bow (x3) {average}',42,'cost 120 x 0.35'),
(22,'2026-10-17 02:03:20','You destroy an Elm Staff [flavour unknown]',28,'MINIMUM: unaware staff sells 70 x 0.4; true value unknown (staffs 200-2000 cost)'),
(22,'2026-10-17 02:03:21','You destroy a Furry Mushroom',0,'~0'),
(22,'2026-10-17 02:03:22','You destroy a Grey Mushroom',0,'~0'),
(22,'2026-10-17 02:07:38','You destroy a Brass Lantern (with 4012 turns of light)',14,'cost 35 x 0.4 (General store paid 15 for 4831 turns)'),
(22,'2026-10-17 02:14:30','You destroy a Ring of Protection {uncursed} (cursed copy, negative; shop would not buy)',0,'shop "no offer"; real cost was the Remove Curse scroll 119 + wasted Identify (mistake, see nav_journal 02:13:44)'),
(23,'2026-10-22 22:25:50','You destroy a Pair of Soft Leather Boots [2] {good}',70,'LOW CONFIDENCE: cost 7 + 100/AC plus (unknown +1..+3) x S 0.39 = 42-120; plusses unknown'),
(23,'2026-10-22 22:27:42','You destroy a Potion of Water',0,'0'),
(23,'2026-10-22 22:27:43','You destroy a Furry Mushroom',0,'~0'),
(23,'2026-10-22 22:27:44','You destroy a Black Mushroom',0,'~0'),
]
for m,t,item,est,how in man:
    add(m,T(t),'b_destroy',item,0,est,how,'events.jsonl message; decisions act custom k')
# c. loot abandoned
c=[
(17,'2026-10-16 14:35:39','No room: Set of Leather Gloves [1]',3,'cost 3'),
(17,'2026-10-16 14:36:33','No room: Scroll of Light',6,'cost 15 x 0.39'),
(17,'2026-10-16 14:36:46','No room: Pair of Soft Leather Boots [2] (x2 events)',3,'cost 7 x 0.4'),
(19,'2026-10-16 22:32:13','No room: Scroll "nelggar payjo" (unknown)',8,'unaware scroll base 20 x 0.4; true value unknown'),
(20,'2026-10-17 00:04:59','No room: Clotted Red Potion (=Clumsiness)',0,'worthless'),
(20,'2026-10-17 00:12:00','No room: Set of Leather Gloves [1] (x2)',3,'cost 3'),
(21,'2026-10-17 01:12:21','No room: Scroll of Holy Chant',16,'cost 40 x 0.39'),
(21,'2026-10-17 01:18:31','No room: Scroll of Light',6,'cost 15 x 0.39'),
(22,'2026-10-17 01:50:41','No room: Wand of Slow Monster (never picked up later)',175,'cost 500 x 0.35 unknown charges; ~250 if charges known (500+25*~10)'),
(22,'2026-10-17 02:03:11','No room: Hard Leather Cap [2]',5,'cost 12 x 0.4'),
(22,'2026-10-17 02:07:27','No room: Dagger (1d4)',4,'cost ~10 x 0.4'),
(22,'2026-10-17 01:48:11','Seen, never picked up (pack full of junk): Ring of Resist Fire',88,'cost 250 x 0.35 (Inglorian paid 100 for a known one)'),
(22,'2026-10-17 01:48:24','Seen, never picked up: Ring of Slow Digestion (x1-2)',88,'cost 250 x 0.35 each; (shop paid 63 at Luthien)'),
(22,'2026-10-17 01:48:25','Seen, never picked up: Wand of Light',108,'cost 200 + 10/charge (~11) x 0.35'),
(22,'2026-10-17 01:48:40','Seen, never picked up: Staff of Perception',224,'cost 400 + 20/charge (~12) x 0.35 (160 if sold unidentified)'),
(22,'2026-10-17 01:48:33','Seen, never picked up: Birch Staff (flavour unknown)',25,'MINIMUM: unaware staff 70 x 0.35; true unknown'),
(22,'2026-10-17 02:02:35','Seen, never picked up: Oak Staff (flavour unknown)',25,'MINIMUM unaware staff'),
(22,'2026-10-17 02:11:39','Seen, never picked up: Balsa Staff (flavour unknown)',25,'MINIMUM unaware staff'),
(22,'2026-10-17 02:05:30','Seen, never picked up: Ring of Resist Cold',88,'cost 250 x 0.35'),
(22,'2026-10-17 02:05:56','Seen, never picked up: Wand of Wonder',133,'cost 250 + 12.5/charge (~11) x 0.35'),
(19,'2026-10-16 22:17:56','Seen, never picked up: Staff of Light',90,'cost 250 + 12/charge x 0.35 (rough)'),
(19,'2026-10-16 22:30:04','Seen, never picked up: Wand of Light (x2 frames)',70,'cost 200 x 0.35 base'),
(17,'2026-10-16 14:10:34','Seen, not picked up: Zinc Wand (flavour unknown)',17,'MINIMUM unaware wand 50 x 0.35'),
(23,'2026-10-22 22:20:27','Left on floor (bulky rule): Metal Cap [3]',12,'cost 30 x 0.4'),
(23,'2026-10-22 22:24:49','LOST in flee: Scimitar (2d5) {Brodda, the Easterling} unique drop (user: "likely good or excellent")',262,'LOW CONFIDENCE: if like the (+2,+3) Lucerne Hammer: (250+500) x 0.35; floor 250 x 0.35 = 88'),
]
for m,t,item,est,how in c:
    add(m,T(t),'c_abandoned',item,0,est,how,'decisions attention (lost/pack_full/interesting_item/tactic) + events itemlist/messages')
# d: forced overrides are flagged inside a_sale rows; extra mistake costs
add(22,T('2026-10-17 02:13:44'),'d_forced_other','Wore unidentified Bloodstone Ring (cursed Ring of Protection) after Identify letter mixup',0,119+61,'Remove Curse 119 + a wasted Identify (~61): cost of Navigator mistake, not a sale','nav_journal 02:13:44; events bought Remove Curse for 119')
# e: thefts
th=[(17,'2026-10-16 14:00:19',35,'urchin'),(17,'2026-10-16 14:00:23',22,'urchin'),(17,'2026-10-16 14:11:02',63,'hobbit'),(17,'2026-10-16 14:11:41',46,'hobbit'),(18,'2026-10-16 19:02:03',28,'Wormtongue touch'),(18,'2026-10-16 19:08:23',41,'Wormtongue touch'),(18,'2026-10-16 19:18:37',67,'urchin')]
for m,t,g,who in th:
    add(m,T(t),'e_stolen_gold','%d gold stolen by %s'%(g,who),0,g,'face value','events.jsonl "N coins were stolen!"')
for m,t,item,est,how in [
 (18,'2026-10-16 18:52:23','One of your Potion of Speed stolen by Brigand',75,'cost 75 (shop value); USE value much higher (+10 speed)'),
 (19,'2026-10-16 22:47:38','One Scroll of Phase Door {75% off} stolen (Squint-eyed rogue)',6,'paid ~6'),
 (21,'2026-10-17 01:18:42','Hard Studded Leather [7] {excellent} stolen by Brigand (RECOVERED after killing thief)',0,'recovered 01:20:54; true item = Hard Studded Leather of Resistance (-1) [7,+9]; no loss'),
 (18,'2026-10-16 18:55:51','One Scroll of Phase Door {75% off} destroyed by attack',6,'paid ~6'),
 (19,'2026-10-16 22:24:49','One Potion of Heroism {75% off} destroyed by attack',9,'paid ~9'),
 (22,'2026-10-17 02:12:02','One Potion of Cure Critical Wounds {25% off} destroyed by attack',120,'paid ~120 (shop 159-160 full)'),
 (19,'2026-10-16 22:16:04','Food eaten by unseen monster: Elvish Waybread, Ration, Wrinkled Mushroom',10,'~10'),
]:
    add(m,T(t),'e_stolen_item' if 'stolen' in item else 'e_destroyed_by_monster',item,0,est,how,'events.jsonl message')
rows_out.sort(key=lambda r:(r[0],float(r[1])))
with open('V1_value_events.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow('mission,epoch,time,category,item,received,est_value,shortfall,how_valued,evidence'.split(',')); w.writerows(rows_out)
import collections
tot=collections.defaultdict(lambda:[0,0,0])
for r in rows_out:
    k=r[3]; tot[k][0]+=1; tot[k][1]+= (r[6] or 0) if r[6]!='' else 0; tot[k][2]+= r[7] if r[7]!='' else 0
for k,v in sorted(tot.items()): print(k,v)
bymis=collections.defaultdict(float)
for r in rows_out:
    if r[3].startswith(('a_sale_SHORT','c_','e_stolen_gold')) or r[3]=='d_forced_other': bymis[r[0]]+= (r[7] if r[3].startswith('a_') else r[6]) 
print(dict(bymis))
