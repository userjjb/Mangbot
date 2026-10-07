import json,csv,datetime,re
R='/projectnb/jbrcs/mangband/runs/pilot/'
def load(d):
    st=[]
    for l in open(R+d+'/decisions.jsonl'):
        j=json.loads(l)
        if j['kind']=='attention' and j['what']=='started': st.append(j['t'])
    ev=[(i,json.loads(l)) for i,l in enumerate(open(R+d+'/events.jsonl'),1)]
    n=1;p=-1
    for i,j in ev:
        if j['t']<p-1:n+=1
        p=j['t']
    st=st[len(st)-n:]
    seg=0;prev=-1;out=[]
    for i,j in ev:
        if j['t']<prev-1: seg+=1
        prev=j['t']
        if j['ev']=='message': out.append((i,st[seg]+j['t'],j['text']))
    return out
IDX={d:load(d) for d in ['dive01','dive03','dive04']}
def ep(s): return datetime.datetime.strptime('2026-'+s,'%Y-%m-%d %H:%M:%S').timestamp()
def line(d,t,text):
    for i,e,m in IDX[d]:
        if abs(e-ep(t))<=3 and text in m: return f'{d}/events.jsonl:{i}'
    return f'{d}/events.jsonl:?{t}'
# kinds
K={}
for r in csv.DictReader(open('/projectnb/jbrcs/mangband/Advisor/data/identify/kinds.csv')):
    K[(r['kind'],r['name'])]=r
def cost(tv,name): return int(K[(tv,name)]['cost'])
ROWS=[]
def row(mission,t,nick,lv,seen,true,fate,gold,pick_txt,sell_t,sell_txt,tv,aware='no',charges=0,shop=None,pct=None,note='',n=1):
    d=nick.lower()
    cites=[]
    if pick_txt and t: cites.append(line(d,t,pick_txt))
    if sell_t: cites.append(line(d,sell_t,sell_txt))
    est=''
    nm=re.sub(r'^(Potion|Scroll|Staff|Wand|Rod|Ring|Amulet)s? of ','',true or '')
    nm=re.sub(r'\s*[\(\{].*$','',nm); nm=re.sub(r' x\d$','',nm).strip()
    if nm and tv and (tv,nm) in K:
        c=cost(tv,nm)
        v=c*(1+charges/20) if tv in('wand','staff') else c
        if pct is not None: est=round(v*pct*n)
        if 'cursed' in (true or ''): est=0
    ROWS.append(dict(mission=mission,date_time=t or sell_t or '',nick=nick,depth_ft=('' if lv is None else lv*50),item_as_seen=seen,true_kind=true,fate=fate,gold_received=gold,source_cite='; '.join(cites) if cites else 'pre-log (first dive03 sale 09-25 20:56)',aware_at_find=aware,tval=tv,charges=charges or '',est_known_gold=est,note=note))
D3A,D3M,D4A,D4M=0.45,0.47,0.40,0.30
# ---- Dive03 pre-log batch (09-25 20:55-20:58)
S='09-25 20:56:0'
row('pre','',  'Dive03',None,'Rhodonite Ring','Ring of Stupidity (-4) {cursed}','sold unknown (Magic shop)',21,None,'09-25 20:56:03','Selling a Rhodonite Ring','ring',pct=D3M,note='pickup not logged; known = cursed -> shop pays 0')
row('pre','','Dive03',None,'Golden Staff','Staff of Sleep Monsters','sold unknown (Magic shop)',33,None,'09-25 20:56:07','Selling a Golden Staff','staff',charges=10,pct=D3M,note='pickup not logged')
row('pre','','Dive03',None,'Balsa Staff','Staff of Detect Invisible','sold unknown (Magic shop)',33,None,'09-25 20:56:07','Selling a Balsa Staff','staff',charges=11,pct=D3M,note='pickup not logged')
row('pre','','Dive03',None,'Maple Staff','Staff of Cure Light Wounds','sold unknown (Magic shop)',33,None,'09-25 20:56:07','Selling a Maple Staff','staff',charges=11,pct=D3M,note='pickup not logged')
row('pre','','Dive03',None,'Lead Wand','Wand of Heal Monster','sold unknown (Magic shop)',24,None,'09-25 20:56:07','Selling a Lead Wand','wand',charges=17,pct=D3M,note='pickup not logged; cost 0 (monster-helping)')
row('pre','','Dive03',None,'Steel-Plated Wand','Wand of Confuse Monster','sold unknown (Magic shop)',24,None,'09-25 20:56:08','Selling a Steel-Plated Wand','wand',charges=17,pct=D3M,note='pickup not logged')
row('pre','','Dive03',None,'Copper-Plated Wand','Wand of Slow Monster','sold unknown (Magic shop)',24,None,'09-25 20:56:08','Selling a Copper-Plated Wand','wand',charges=13,pct=D3M,note='pickup not logged')
row('pre','09-25 20:58:19','Dive03',None,'(2nd) Ring of Stupidity (flavour now aware)','Ring of Stupidity','shop refused ("I don\'t want that!") then destroyed',0,None,None,'','ring',aware='yes',note='pickup not logged; 2nd copy after first sale made flavour aware')
row('pre','09-25 20:58:22','Dive03',None,'(2nd) Wand of Heal Monster (aware)','Wand of Heal Monster','shop refused then destroyed',0,None,None,'','wand',aware='yes',note='pickup not logged')
row('pre','09-25 20:58:31','Dive03',None,'Scroll titled "it mungrea a" {tried}','Scroll of Summon Monster','read-tested in town by agent (no visible effect, stayed unaware "{tried}")',0,None,None,'','scroll',note='pickup not logged; read 20:58:30 (events: You have no more Scrolls titled "it mungrea a" {tried})')
row('pre','09-25 20:58:39','Dive03',None,'Scroll titled "kliwex potri" {tried}','Scroll of Door/Stair Location','read-tested in town (no visible effect, "{tried}")',0,None,None,'','scroll',note='pickup not logged')
# ---- Dive03 pre-test 09-26 04:xx -> sold 15:16 (M1 start)
def d3(m,t,lv,seen,true,tv,sell_t,gold,sell_txt,pickt,shopp=D3A,fate='sold unknown (Alchemist)',charges=0,note='',n=1):
    row(m,t,'Dive03',lv,seen,true,fate,gold,pickt,sell_t,sell_txt,tv,charges=charges,pct=shopp,note=note,n=n)
d3('pre-test','09-26 04:54:41',4,'Light Blue Potion','Potion of Heroism','potion','09-26 15:16:02',9,'Selling a Light Blue Potion','You have a Light Blue Potion',note='carried 11h to M1 start; sold M1')
d3('pre-test','09-26 04:55:09',5,'Clotted Red Potion','Potion of Clumsiness','potion','09-26 15:16:02',9,'Selling a Clotted Red Potion','You have a Clotted Red Potion')
d3('pre-test','09-26 04:56:54',8,'Yellow Speckled Potion','Potion of Infravision','potion','09-26 15:16:02',9,'Selling a Yellow Speckled Potion','You have a Yellow Speckled Potion')
d3('pre-test','09-26 04:57:10',8,'Blue Speckled Potion','Potion of Sleep','potion','09-26 15:16:03',9,'Selling a Blue Speckled Potion','You have a Blue Speckled Potion')
d3('pre-test','09-26 04:57:27',8,'Green Potion','Potion of Slowness','potion','09-26 15:16:03',9,'Selling a Green Potion','You have a Green Potion')
d3('M1','09-26 15:15:27',0,'Clear Potion (town floor)','Potion of Water','potion','09-26 15:16:03',9,'Selling a Clear Potion','You have a Clear Potion')
d3('M1','09-26 15:29:53',5,'Birch Staff','Staff of Darkness','staff','09-26 16:03:52',32,'Selling a Birch Staff','You have a Birch Staff',D3M,'sold unknown (Magic shop)',15,'known = cost 0 (bad staff)')
row('M1','09-26 15:31:45','Dive03',7,'Copper Wand','Wand of Haste Monster (by flavour)','seen on floor, pickup command logged but no "You have" message; not carried (not in later sales)',0,'You see a Copper Wand',None,'','wand',note='fate not confirmed')
d3('M1','09-26 15:32:14',7,'Red Speckled Potion','unknown (never identified)','potion',None,0,'',"You have a Red Speckled Potion",fate='destroyed by agent in a stale-letter batch (Navigator: pack cleanup mistake)',note='M1 15:36:02; true kind never learned')
d3('M1','09-26 15:33:53',8,'Red Potion','Potion of Resist Cold (by Dive04 sale 09-29)','potion',None,0,'',"You have a Red Potion",fate='destroyed by agent in a stale-letter batch (mistake)',note='M1 15:36:00; value ~12-14 known')
d3('M1','09-26 15:45:35',6,'Vermilion Potion','Potion of Detect Invisible','potion','09-26 16:03:46',9,'Selling a Vermilion Potion','You have a Vermilion Potion')
d3('M1','09-26 15:45:42',7,'Black Potion','Potion of Resist Heat','potion','09-26 16:03:47',9,'Selling a Black Potion','You have a Black Potion')
d3('M1','09-26 15:43:54',7,'Scroll titled "kliwex potri" {tried} (+1 more at 15:50:19, d6)','Scroll of Door/Stair Location x2','scroll','09-26 16:03:47',18,'Selling 2 Scrolls titled "kliwex potri"','You have a Scroll titled "kliwex potri"',note='2 scrolls, 18 total',n=2)
row('M1','09-26 15:49:38','Dive03',5,'Bubbling Potion','Potion of Neutralize Poison (by flavour)','left on floor: "You have no room"',0,'You have no room for a Bubbling Potion',None,'','potion')
row('M1','09-26 15:49:45','Dive03',6,'Iron Wand','unknown','left on floor: "You have no room"',0,'You have no room for an Iron Wand',None,'','wand')
d3('M1','09-26 15:50:47',5,'Runed Staff','Staff of Light','staff','09-26 16:03:52',32,'Selling a Runed Staff','You have a Runed Staff',D3M,'sold unknown (Magic shop)',11)
d3('M2','09-26 16:17:06',20,'Ruby Ring','Ring of Searching (-2) {cursed}','ring','09-26 16:22:22',20,'Selling a Ruby Ring','You have a Ruby Ring',D3M,'sold unknown (Magic shop)',note='known cursed -> 0')
d3('M2','09-26 16:25:52',13,'Icky Green Potion','Potion of Slime Mold Juice','potion','09-26 16:39:42',9,'Selling an Icky Green Potion','You have an Icky Green Potion')
d3('M2','09-26 16:31:54',13,'Mulberry Staff','Staff of Slow Monsters','staff','09-26 16:39:38',32,'Selling a Mulberry Staff','You have a Mulberry Staff',D3M,'sold unknown (Magic shop)',8)
d3('M2','09-26 16:42:26',13,'Copper-Plated Rod','Rod of Illumination','rod','09-26 16:50:35',42,'Selling a Copper-Plated Rod','You have a Copper-Plated Rod',D3M,'sold unknown (Magic shop)')
d3('M3','09-27 11:08:59',1,'Magenta Potion','Potion of Confusion','potion','09-27 11:56:51',9,'Selling a Magenta Potion','You have a Magenta Potion')
d3('M3','09-27 11:35:15',9,'Scroll titled "munger toxmung"','Scroll of Summon Undead','scroll','09-27 11:56:51',9,'Selling a Scroll titled "munger toxmung"','You have a Scroll titled "munger toxmung"')
d3('M3','09-27 11:38:02',9,'Rosewood Staff','Staff of Object Location','staff','09-27 11:56:41',33,'Selling a Rosewood Staff','You have a Rosewood Staff',D3M,'sold unknown (Magic shop)',20)
d3('M3','09-27 11:40:09',9,'Bubbling Potion','Potion of Neutralize Poison','potion','09-27 11:56:51',9,'Selling a Bubbling Potion','You have a Bubbling Potion')
d3('M3','09-27 11:40:36',9,'Copper Wand','Wand of Haste Monster','wand','09-27 11:56:40',24,'Selling a Copper Wand','You have a Copper Wand',D3M,'sold unknown (Magic shop)',9,'known cost 0')
d3('M3','09-27 11:55:49',10,'Molybdenum Rod','Rod of Light','rod','09-27 11:56:40',42,'Selling a Molybdenum Rod','You have a Molybdenum Rod',D3M,'sold unknown (Magic shop)')
d3('M4','09-27 12:07:32',12,'Corundum Ring','Ring of Feather Falling','ring','09-27 12:12:22',21,'Selling a Corundum Ring','You have a Corundum Ring',D3M,'sold unknown (Magic shop)')
d3('M4','09-27 12:15:06',12,'Redwood Staff','Staff of Door/Stair Location','staff','09-27 12:21:07',33,'Selling a Redwood Staff','You have a Redwood Staff',D3M,'sold unknown (Magic shop)',13,'Navigator later: "mistake, that staff is useful for stair-scumming"')
d3('M4','09-27 12:19:15',12,'Nickel-Plated Wand','Wand of Trap/Door Destruction','wand','09-27 12:21:07',24,'Selling a Nickel-Plated Wand','You have a Nickel-Plated Wand',D3M,'sold unknown (Magic shop)',8)
d3('M4','09-27 12:26:52',12,'Ivory Amulet','Amulet of Resist Lightning','amulet','09-27 12:39:45',21,'Selling an Ivory Amulet','You have an Ivory Amulet',D3M,'sold unknown (Magic shop)',note='Navigator: mistake, neck slot was empty; inspect did not identify')
d3('M4','09-27 12:35:38',12,'Scroll titled "skinej glenur"','Scroll of Remove Curse','scroll','09-27 12:39:51',9,'Selling a Scroll titled "skinej glenur"','You have a Scroll titled "skinej glenur"')
d3('M5','09-27 12:47:27',7,'Scroll titled "nelggar payjo"','Scroll of Trap Detection','scroll','09-27 13:05:19',9,'Selling a Scroll titled "nelggar payjo"','You have a Scroll titled "nelggar payjo"')
d3('M5','09-27 12:49:56',7,'Scroll titled "monwhon"','Scroll of Detect Invisible','scroll','09-27 13:05:19',9,'Selling a Scroll titled "monwhon"','You have a Scroll titled "monwhon"')
d3('M5','09-27 12:52:05',10,'Elm Staff','Staff of Trap Location','staff','09-27 13:04:55',33,'Selling an Elm Staff','You have an Elm Staff',D3M,'sold unknown (Magic shop)',9)
row('M5','09-27 12:54:28','Dive03',11,'Runed Rod','Rod of Trap Location','identified by found Scroll of Identify (read 13:03:00), then sold known (Magic shop)',47,'You have a Runed Rod','09-27 13:04:54','Selling a Rod of Trap Location','rod',pct=D3M,note='Identify was a free find; gain over unknown sale (42 for rods at base 90) was +5 only: cost 100 vs unaware base 90')
row('M6','09-27 13:36:40','Dive03',14,'Silver Amulet','unknown (never identified)','WORN 13:50:46 (neck slot empty), never identified; lost at death M7 22:29',0,'You have a Silver Amulet',None,'','amulet',note='no ill effect seen; true kind unknown')
row('M7','09-27 22:17:48','Dive03',15,'Amber Amulet','unknown (never identified)','carried unworn; lost at death 22:29',0,'You have an Amber Amulet',None,'','amulet')
# ---- Dive01
row('Dive01 test','09-25 22:00:55','Dive01',1,'Scroll titled "xtox ipta sour"','Scroll of Blessing (by Dive04 sale 09-28)','carried at end of log (22:03)',0,'You have a Scroll titled "xtox ipta sour"',None,'','scroll')
row('Dive01 test','09-25 22:01:54','Dive01',3,'Gold Wand','unknown (never identified)','carried at end of log (22:03)',0,'You have a Gold Wand',None,'','wand')
# ---- Dive04
def d4(m,t,lv,seen,true,tv,sell_t,gold,sell_txt,pickt,shopp=D4A,fate='sold unknown (Alchemist)',charges=0,note='',n=1):
    row(m,t,'Dive04',lv,seen,true,fate,gold,pickt,sell_t,sell_txt,tv,charges=charges,pct=shopp,note=note,n=n)
d4('M8','09-28 01:37:44',1,'Scroll titled "xtox ipta sour"','Scroll of Blessing','scroll','09-28 02:06:34',9,'Selling a Scroll titled "xtox ipta sour"','You have a Scroll titled "xtox ipta sour"')
d4('M8','09-28 01:43:49',1,'Light Brown Potion','Potion of Apple Juice','potion','09-28 02:06:34',9,'Selling a Light Brown Potion','You have a Light Brown Potion')
d4('M8','09-28 01:49:43',1,'Scroll titled "mikoxy urmur i"','Scroll of Identify','scroll','09-28 02:06:35',9,'Selling a Scroll titled "mikoxy urmur i"','You have a Scroll titled "mikoxy urmur i"',note='sold an Identify scroll (buy price 81 at CHR 4)')
d4('M8','09-28 02:02:32',2,'Magenta Potion','Potion of Confusion','potion','09-28 02:06:34',9,'Selling a Magenta Potion','You have a Magenta Potion')
d4('M8','09-28 02:05:53',2,'Scroll titled "blaa marsef"','Scroll of Darkness','scroll','09-28 02:06:35',9,'Selling a Scroll titled "blaa marsef"','You have a Scroll titled "blaa marsef"')
d4('M9','09-29 21:37:17',2,'Metallic Blue Potion','Potion of Boldness','potion','09-29 21:55:07',9,'Selling a Metallic Blue Potion','You have a Metallic Blue Potion')
d4('M9','09-29 21:37:38',2,'Icky Green Potion','Potion of Slime Mold Juice','potion','09-29 21:55:07',9,'Selling an Icky Green Potion','You have an Icky Green Potion')
d4('M9','09-29 21:44:33',5,'Lead Wand','Wand of Heal Monster','wand','09-29 21:55:17',15,'Selling a Lead Wand','You have a Lead Wand',D4M,'sold unknown (Magic shop; Alchemist refused it)',10,'known cost 0 (Alchemist does not buy wands)')
d4('M10','09-29 22:10:44',3,'Violet Potion','unknown','potion',None,0,'','You have a Violet Potion',fate='lost at death 22:29 (pack emptied)')
d4('M10','09-29 22:15:37',5,'Copper Wand','Wand of Haste Monster (by flavour)','wand',None,0,'','You have a Copper Wand',fate='lost at death 22:29')
d4('M10','09-29 22:21:18',5,'Clear Potion','Potion of Water (by flavour)','potion',None,0,'','You have a Clear Potion',fate='lost at death 22:29')
d4('M10','09-29 22:24:20',5,'Cloudy Potion','Potion of Slow Poison (by flavour)','potion',None,0,'','You have a Cloudy Potion',fate='lost at death 22:29')
d4('M10','09-29 22:25:32',5,'Runed Staff','Staff of Light (by flavour)','staff',None,0,'','You have a Runed Staff',fate='lost at death 22:29')
d4('M10','09-29 22:28:05',5,'Gold Wand','unknown','wand',None,0,'','You have a Gold Wand',fate='lost at death 22:29')
d4('M11','09-29 22:37:59',2,'Rosewood Staff','Staff of Object Location (16 ch)','staff',None,0,'','You have a Rosewood Staff',fate='identified with a found Scroll of Identify (23:07:34); then not seen in any later sale or message (fate unknown)',charges=16)
d4('M11','09-29 22:38:27',2,'Scroll titled "monwhon" (3 found: 22:38, 22:59, 23:00)','Scroll of Detect Invisible x3','scroll','09-29 23:06:36',8,'Selling a Scroll titled "monwhon"','You have a Scroll titled "monwhon"',fate='1 sold unknown 8 (23:06); other 2 sold as known 12 total (10-03 12:19:46)',note='3 found; gold = first only')
d4('M11','09-29 22:46:19',2,'Scroll titled "heaks khonis"','Scroll of Light','scroll','09-29 23:06:37',8,'Selling a Scroll titled "heaks khonis"','You have a Scroll titled "heaks khonis"')
d4('M11','09-29 22:46:20',2,'Green Potion','Potion of Slowness','potion','09-29 23:06:36',8,'Selling a Green Potion','You have a Green Potion')
d4('M11','09-29 22:48:13',2,'Red Potion (2 found: 22:48, 23:03)','Potion of Resist Cold x2','potion','09-29 23:06:36',8,'Selling a Red Potion','You have a Red Potion',fate='1 sold unknown 8; 1 kept (now aware), no later record',note='gold = first only')
d4('M11','09-29 22:50:10',2,'Clear Potion (2 found: 22:50, 23:01)','Potion of Water x2','potion','09-29 23:06:36',8,'Selling a Clear Potion','You have a Clear Potion',fate='1 sold unknown 8; 2nd sold known 1 gold (10-03 12:19:33)',note='gold = first only')
d4('M11','09-29 22:59:23',2,'Blue Speckled Potion','Potion of Sleep','potion','10-03 12:19:32',8,'Selling a Blue Speckled Potion','You have a Blue Speckled Potion',note='carried 4 days; sold M12 start')
d4('M11','09-29 22:59:27',2,'Orange Speckled Potion (2 found: 22:59, 23:00)','Potion of Speed x2','potion','10-03 12:19:32',16,'Selling 2 Orange Speckled Potions','You have an Orange Speckled Potion',note='2 potions, 16 total; store resells at 121 each; handbook cites as the mistake',n=2)
d4('M11','09-29 23:01:24',2,'Light Blue Potion (2 found: 23:01, 23:02)','Potion of Heroism x2','potion','10-03 12:19:32',16,'Selling 2 Light Blue Potions','You have a Light Blue Potion',note='2 potions, 16 total',n=2)
d4('M11','09-29 23:02:06',3,'Cloudy Potion','Potion of Slow Poison','potion','10-03 12:19:32',8,'Selling a Cloudy Potion','You have a Cloudy Potion')
d4('M11','09-29 23:04:22',2,'Scroll titled "it mungrea a"','Scroll of Summon Monster','scroll','10-03 12:19:33',8,'Selling a Scroll titled "it mungrea a"','You have a Scroll titled "it mungrea a"',note='known cost 0 (bad scroll)')
d4('M12','10-03 12:26:59',4,'Vermilion Potion','Potion of Detect Invisible','potion','10-03 12:48:36',8,'Selling a Vermilion Potion','You have a Vermilion Potion')
d4('M12','10-03 12:33:51',5,'Maple Staff','Staff of Cure Light Wounds (7 ch)','staff',None,0,'','You have a Maple Staff',fate='identified with a bought Scroll of Identify (81 each, 12:48:47), KEPT',charges=7,note='Dive04 uses it as a heal')
d4('M12','10-03 12:41:05',5,'Bronze Wand','Wand of Magic Missile (15 ch)','wand','10-03 12:49:07',105,'Selling a Wand of Magic Missile','You have a Bronze Wand',D4M,'identified (bought Identify 81), then sold known (Magic shop)',15,'unknown sale would have paid ~15')
d4('M12','10-03 12:41:49',5,'Aluminum-Plated Wand','Wand of Stinking Cloud (10 ch)','wand','10-03 12:49:07',180,'Selling a Wand of Stinking Cloud','You have an Aluminum-Plated Wand',D4M,'identified (bought Identify 81), then sold known (Magic shop)',10,'unknown sale would have paid ~15')
d4('M12','10-03 12:42:10',5,'Scroll titled "ishx therbin"','Scroll of Satisfy Hunger','scroll','10-03 12:48:36',8,'Selling a Scroll titled "ishx therbin"','You have a Scroll titled "ishx therbin"')
row('M13 (running; data to 09:19)','10-07 09:14:06','Dive04',9,'Puce Potion','Potion of Weakness','QUAFF-TESTED by Navigator at 09:17:05 -> STR drained (blows 3->2)',0,'You have a Puce Potion','10-07 09:17:07','You have no more Potions of Weakness','potion',aware='no',note='HARM: stat_drained STR 18/10->18; Navigator calls it a mistake')
# aware but worth listing: sold/destroyed known-flavour finds
def aw(m,t,nick,lv,seen,true,tv,fate,gold,pick,sell_t=None,sell_txt='',charges=0,pct=None,note=''):
    row(m,t,nick,lv,seen,true,fate,gold,pick,sell_t,sell_txt,tv,aware='yes',charges=charges,pct=pct,note=note)
aw('M3','09-27 11:09:04','Dive03',1,'Scroll of Object Detection','Scroll of Object Detection','scroll','sold known (Alchemist)',7,'You have a Scroll of Object Detection','09-27 11:56:52','Selling a Scroll of Object Detection')
aw('M4','09-27 12:17:01','Dive03',12,'Scroll of Magic Mapping','Scroll of Magic Mapping','scroll','sold known (Alchemist)',18,'You have a Scroll of Magic Mapping','09-27 12:39:51','Selling a Scroll of Magic Mapping')
aw('M4','09-27 12:18:15','Dive03',12,'Ring of Teleportation {cursed}','Ring of Teleportation','ring','autodestroyed (cursed)',0,'You have a Ring of Teleportation')
aw('M6','09-27 13:37:58','Dive03',14,'Staff of Object Location','Staff of Object Location','staff','sold known at M7 start (22:16:10), 16 ch',94,'You have a Staff of Object Location','09-27 22:16:10','Selling a Staff of Object Location',16,note='compare: unknown 20-ch staff of same kind sold 33 at 47%; here 94 (magic shop pct ~26% that evening?)')
aw('M12','10-03 12:33:02','Dive04',4,'Wand of Heal Monster','Wand of Heal Monster','wand','destroyed by agent (shop pays 0)',0,'You have a Wand of Heal Monster')
aw('M13','10-07 09:08:17','Dive04',9,'Staff of Object Location','Staff of Object Location','staff','carried at end of data',0,'You have a Staff of Object Location')
for r in ROWS:
    pass
cols=['mission','date_time','nick','depth_ft','item_as_seen','true_kind','fate','gold_received','source_cite','aware_at_find','tval','charges','est_known_gold','note']
with open('/projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-selling/scratch/L_items.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader()
    for r in ROWS: w.writerow(r)
print(len(ROWS))
