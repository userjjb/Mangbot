import csv
kinds={}
for r in csv.DictReader(open('/projectnb/jbrcs/mangband/Advisor/data/identify/kinds.csv')):
    if r['kind']=='potion': kinds[int(r['sval'])]=r
U='use-obj.c'
T='ticks = 1 normal-speed player turn = 0.6-0.77 s real (49-57 game turns at 75 FPS)'
d={
0:("Food +200 (pval); 'less thirsty'","HARMLESS","-","always (use-obj.c:246-252)"),
1:("Food +250","HARMLESS","-","always (use-obj.c:246-252)"),
2:("Food +400","HARMLESS","-","always (use-obj.c:246-252)"),
4:("Slow (-10 speed) for 16-40 ticks (stacks); food +50","NUISANCE","passes off","yes if not already slow (use-obj.c:255-259, set_slow notice xtra2.c:526)"),
5:("Food set to 99 (starving <100, faint <500), poison cured, paralysed 4 ticks (+existing; Free Action does NOT protect)","NUISANCE (needs food at once; faint risk)","eat food / Scroll of Satisfy Hunger; no digestion in town","always (use-obj.c:261-270)"),
6:("Poisoned +10-24 ticks, 1 HP/tick = 10-24 HP total","NUISANCE","passes off; CCW/Healing/Neutralize cure","yes unless resist/oppose poison (use-obj.c:272-282)"),
7:("Blind +100-199 ticks (about 65-150 s real); cannot read scrolls","NUISANCE (long)","CLW/CSW/CCW/Healing cure at once","yes unless resist blind (use-obj.c:284-294)"),
9:("Confused +15-34 ticks; food +50","NUISANCE","passes off; CSW/CCW cure; CLW -20","yes unless resist conf (use-obj.c:296-306)"),
11:("Paralysed 4-7 ticks (about 2.6-5.4 s real) unless Free Action; food +100","NUISANCE","passes off; Free Action prevents","yes only if no Free Action (use-obj.c:308-318)"),
13:("Lose exp/4 (25% of current exp) unless Hold Life or exp 0; may drop clvl","COSTLY","Restore Life Levels (Temple, base 400) or regain: gain_exp gives full exp while max_exp +10% so exp catches up (xtra2.c:1928-1940)","yes if exp>0 and no hold life (use-obj.c:320-329)"),
15:("10d10 dmg (10-100, avg 55); all 6 stats dec_stat(25, permanent): max AND cur drop (-2 each if <=18)","COSTLY (permanent; not LETHAL for 135 HP)","Restore potions restore cur only; max is lowered; only stat-gain potions raise","always (use-obj.c:331-343)"),
16:("STR cur -1 (<=18) or ~-5+ internal (18/xx), max kept; sustain STR blocks","COSTLY","Restore Strength (Alchemist 300); no level-up/time restore","yes if stat changed or sustained (spells2.c:271-308)"),
17:("INT drained as Weakness","COSTLY (low impact on warrior)","Restore Intelligence (Alchemist 300)","as 16"),
18:("WIS drained as Weakness","COSTLY (low impact)","Restore Wisdom (Alchemist 300)","as 16"),
19:("DEX drained as Weakness","COSTLY","Restore Dexterity (Alchemist 300)","as 16"),
20:("CON drained as Weakness (lowers max HP)","COSTLY","Restore Constitution (Alchemist 300)","as 16"),
21:("CHR drained as Weakness","COSTLY (CHR 4 may fall to 3)","Restore Charisma (Alchemist 300)","as 16"),
22:("50d20 dmg (50-1000, avg 525) + stun +75 + cut +5000 (3 HP/tick)","LETHAL","-","always (use-obj.c:381-390)"),
23:("5000 dmg","LETHAL","-","always (use-obj.c:392-398)"),
24:("Infravision +101-200 ticks","HARMLESS","-","yes if not active (use-obj.c:400-407)"),
25:("See invisible +13-24 ticks","HARMLESS","-","yes if not active (use-obj.c:409-416)"),
26:("Poison halved","HARMLESS","-","only if poisoned (use-obj.c:418-422)"),
27:("Poison cured","HARMLESS","-","only if poisoned (use-obj.c:424-428)"),
28:("Fear cured","HARMLESS","-","only if afraid (use-obj.c:430-434)"),
29:("+10 speed for 16-40 ticks (already fast: +5 ticks, no ident)","GOOD (wasted out of combat)","-","yes if not already fast (use-obj.c:436-447)"),
30:("Resist fire +11-20 ticks","HARMLESS","-","yes if not active (use-obj.c:449-456)"),
31:("Resist cold +11-20 ticks","HARMLESS","-","yes if not active (use-obj.c:458-465)"),
32:("Heal 10, cure fear, hero 26-50 ticks","GOOD","-","yes (hero timer starts) (use-obj.c:467-473)"),
33:("Heal 30, cure fear, berserk 26-50 ticks","GOOD","-","yes (use-obj.c:475-481)"),
34:("Heal 15, cure blind, cut -20, confusion -20; food +50","GOOD (wasted if full HP)","-","only if something changes: HP<max, or blind/cut/conf (use-obj.c:483-490)"),
35:("Heal 20-24, cure blind/conf/cut; food +100","GOOD","-","only if something changes (use-obj.c:492-499)"),
36:("Heal 25-29, cure blind/conf/poison/stun/cut; food +100","GOOD","-","only if something changes (use-obj.c:501-510)"),
37:("Heal 300, cure blind/conf/poison/stun/cut; food +200","GOOD","-","only if something changes (use-obj.c:512-521)"),
38:("Heal 1200 + same cures","GOOD","-","only if something changes (use-obj.c:523-532)"),
39:("Restore exp, all stats restored, cures all, heal 5000","GOOD","-","always (use-obj.c:534-558)"),
40:("Restore mana if csp<msp (warrior msp 0: nothing)","HARMLESS","-","NEVER for a warrior (use-obj.c:560-572)"),
41:("Restore drained exp (exp=max_exp)","GOOD if drained else HARMLESS","-","only if exp<max_exp (use-obj.c:574-578; spells2.c:485-503)"),
42:("Restore STR cur to max","HARMLESS","-","only if drained (use-obj.c:580-584)"),
43:("Restore INT","HARMLESS","-","only if drained"),
44:("Restore WIS","HARMLESS","-","only if drained"),
45:("Restore DEX","HARMLESS","-","only if drained"),
46:("Restore CON","HARMLESS","-","only if drained"),
47:("Restore CHR","HARMLESS","-","only if drained (use-obj.c:610-614)"),
48:("Restore then +1 STR (+1-2 below 18; about +1/6 to 1/3 of way to 18/100 above)","GOOD (permanent)","-","yes unless at 18/100 (use-obj.c:616-620; spells1.c:1089-1136)"),
49:("+INT","GOOD (little use)","-","as 48"),
50:("+WIS","GOOD (little use)","-","as 48"),
51:("+DEX","GOOD","-","as 48"),
52:("+CON","GOOD","-","as 48"),
53:("+CHR","GOOD (little use)","-","as 48"),
55:("+1 step to all six stats","GOOD","-","yes (use-obj.c:652-661)"),
56:("Maps/lights the level (wiz_lite)","GOOD","-","always (use-obj.c:663-669)"),
57:("wiz_lite, +INT +WIS, detect traps/doors/treasure/objects, identify_pack, self_knowledge","GOOD (identifies whole pack)","-","always (use-obj.c:671-687)"),
58:("Shows self-knowledge screen","HARMLESS","-","always (use-obj.c:689-696)"),
59:("Gain exp/2+10 (max 100000)","GOOD","-","yes if exp<PY_MAX_EXP (use-obj.c:698-708)"),
}
assert set(d)==set(kinds),(set(kinds)-set(d),set(d)-set(kinds))
with open('/projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-selling/scratch/P_potions.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['sval','potion','level','alloc','kind_cost','effect_out_of_combat','class','fix_cost','aware_on_quaff'])
    for s in sorted(d):
        k=kinds[s]; w.writerow([s,k['name'],k['level'],k['alloc'],k['cost'],*d[s]])
print('ok')
