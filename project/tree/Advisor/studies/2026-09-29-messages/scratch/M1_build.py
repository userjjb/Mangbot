import csv,re
SRC='/projectnb/jbrcs/mangband/github/src/server/'
D='/projectnb/jbrcs/mangband/Advisor/studies/2026-09-29-messages/scratch/'
src={}
def lines(f):
    if f not in src: src[f]=open(SRC+f,errors='replace').read().split('\n')
    return src[f]
PH={'<monster>':r'(?P<mon>.+?)','<his>':r'(?P<poss>his|her|its)','<item>':r'(?P<item>.+?)','<n>':r'(?P<n>\d+)',
    '<c>':r'(?P<c>[a-z])','<player>':r'(?P<player>.+?)','<name>':r'(?P<name>.+?)','<minions|kin>':r'(?:minions|kin)',
    '<One of y|Y>':r'(?:One of y|Y)','<insult>':r'(?:insults you!|insults your mother!|gives you the finger!|humiliates you!|defiles you!|dances around you!|makes obscene gestures!|moons you!!!)'}
def rx(text):
    parts=re.split('(<[^>]+>)',text)
    out=''
    for p in parts:
        if p in PH: out+=PH[p]
        else: out+=re.escape(p)
    return '^'+out+'$'
rows=[]
def add(id,file,line,text,event,aud,rel,cond,notes='',regex=None):
    rows.append(dict(id=id,file=file,line=line,text=text,event=event,audience=aud,pilot_relevance=rel,regex=regex or rx(text),condition=cond,notes=notes))
inp={int(r['id']):r for r in csv.DictReader(open(D+'M1_input.csv'))}
def L(i): return inp[i]['file'],int(inp[i]['line'])
def cite(i): f,l=L(i); return f'{f}:{l}'

# ---------- melee1.c explicit ----------
M='melee1.c'
def m(i,text,event,aud,rel,cond,notes=''): add(i,*L(i),text,event,aud,rel,cond+f' ({cite(i)})',notes)
m(420,'<monster> is repelled.','defense.protevil_repel','self','high','melee blow that would have hit; player has protection from evil, monster is EVIL, plr lev >= monster lev, randint0(100)+lev>50; blow skipped, no damage')
# 421 expanded
meth=[('HIT','hits you.',True),('TOUCH','touches you.',False),('PUNCH','punches you.',True),('KICK','kicks you.',True),('CLAW','claws you.',True),('BITE','bites you.',True),('STING','stings you.',False),('XXX1',"XXX1's you.",False),('BUTT','butts you.',True),('CRUSH','crushes you.',True),('ENGULF','engulfs you.',False),('XXX2',"XXX2's you.",False),('CRAWL','crawls on you.',False),('DROOL','drools on you.',False),('SPIT','spits on you.',False),('XXX3',"XXX3's on you.",False),('GAZE','gazes at you.',False),('WAIL','wails at you.',False),('SPORE','releases spores at you.',False),('XXX4',"projects XXX4's at you.",False),('BEG','begs you for money.',False),('XXX5',"XXX5's you.",False)]
cutstun={'HIT':'cut or stun (50/50)','PUNCH':'stun','KICK':'stun','CLAW':'cut','BITE':'cut','BUTT':'stun','CRUSH':'stun'}
lineno={'HIT':308,'TOUCH':316,'PUNCH':323,'KICK':331,'CLAW':339,'BITE':347,'STING':355,'XXX1':362,'BUTT':368,'CRUSH':376,'ENGULF':384,'XXX2':391,'CRAWL':397,'DROOL':404,'SPIT':411,'XXX3':418,'GAZE':424,'WAIL':431,'SPORE':438,'XXX4':445,'BEG':451,'XXX5':472}
for k,t,_ in meth:
    unused = k.startswith('XXX') or k=='PUNCH'
    ev='attack.melee.hit' if k not in ('BEG',) else 'attack.melee.harmless'
    n=f'RBM_{k} act string at melee1.c:{lineno[k]}; printed by melee1.c:480 for every landed blow. '
    if k in cutstun: n+=f'Method may add {cutstun[k]} (do_cut/do_stun, monster_critical) -> later set_cut/set_stun messages. '
    if unused: n+='No monster in lib/edit/monster.txt uses this method (B: lines), so effectively never seen. '
    n+='Printed whether or not the monster is visible: unseen attacker renders "It ...". Effect message(s) for the blow effect follow (see RBE rows).'
    add(f'421:{k}','melee1.c',480,'<monster> '+t,ev,'self','high' if k!='BEG' else 'low',f'blow lands (effect==0 or check_hit) with method RBM_{k}; not repelled (melee1.c:276-296,480)',n)
for j,t in enumerate(["insults you!","insults your mother!","gives you the finger!","humiliates you!","defiles you!","dances around you!","makes obscene gestures!","moons you!!!"]):
    add(f'421:INSULT{j}','melee1.c',480,'<monster> '+t,'attack.melee.harmless','self','low','RBM_INSULT, desc_insult[%d] (melee1.c:134-144, 458-463)'%j,'harmless flavour; INSULT blows have no effect and 0 damage. Used by 5 monster blows in monster.txt.')
for j,t in enumerate(["seems sad about something.","asks if you have seen his dogs.","tells you to get off his land.","mumbles something about mushrooms."]):
    add(f'421:MOAN{j}','melee1.c',480,'<monster> '+t,'attack.melee.harmless','self','low','RBM_MOAN, desc_moan[%d] (melee1.c:151-157, 465-470)'%j,'harmless flavour (2 MOAN blows in monster.txt). NOTE "mumbles something about mushrooms." is NOT the blind spell text "<monster> mumbles." (regexes differ by the tail).')
m(422,'Energy drains from your pack!','item.drained_charges','self','medium','RBE_UN_POWER hit; a random pack slot (10 tries) holding a staff/wand with pval>0 is emptied (melee1.c:556-604); monster heals rlev*pval','wand/staff charges set to 0; damage message comes separately from take_hit')
m(423,'You quickly protect your money pouch!','item.stolen.saved','self','medium','RBE_EAT_GOLD hit, player not paralyzed and randint0(100) < adj_dex_safe+lev (melee1.c:617-627)','Monster may still blink away (2/3): "There is a puff of smoke!" follows')
m(424,'Nothing was stolen.','gold.stolen.none','self','medium','RBE_EAT_GOLD, save failed, computed gold<=0 (melee1.c:637-640)')
m(425,'Your purse feels lighter.','gold.stolen','self','high','RBE_EAT_GOLD save failed, gold>0 and player still has gold left (melee1.c:641-645); followed by "<n> coins were stolen!"; monster then blinks (blinked=2 -> "There is a puff of smoke!")')
m(426,'<n> coins were stolen!','gold.stolen','self','high','follows "Your purse feels lighter." when gold remains (melee1.c:644)','Message uses %ld number of coins. Format has no "gold"; matches "N coins were stolen!"')
m(427,'Your purse feels lighter.','gold.stolen','self','high','RBE_EAT_GOLD when the theft takes all gold (melee1.c:646-648); followed by "All of your coins were stolen!"','Same text as row 425; distinguish by the follow-up line.')
m(428,'All of your coins were stolen!','gold.stolen.all','self','high','RBE_EAT_GOLD took every coin (melee1.c:649)')
m(429,'You grab hold of your backpack!','item.stolen.saved','self','medium','RBE_EAT_ITEM hit, player not paralyzed and randint0(100)<adj_dex_safe+lev (melee1.c:670-686); monster blinks away anyway (blinked=2) -> "There is a puff of smoke!"')
# 430/431
add(430,'melee1.c',726,'Your <item> (<c>) was stolen!','item.stolen','self','high','RBE_EAT_ITEM hit, save failed, 10 random pack-slot tries; non-artifact item found (melee1.c:688-748)','Second alternate text "One of your <item> (<c>) was stolen!" when the stack had >1 (row 430:many). Item description is o_name with count 1 (mode 3). Monster blinks (puff of smoke) afterwards. Nothing printed if 10 tries all miss.',rx('Your <item> (<c>) was stolen!').replace('^Your','^Your') )
add('430:many','melee1.c',726,'One of your <item> (<c>) was stolen!','item.stolen','self','high','same, o_ptr->number>1 (melee1.c:727)','')
# regex for 430 should allow both
rows[-2]['regex']=r'^(?:One of y|Y)our (?P<item>.+?) \((?P<c>[a-z])\) was stolen!$'
rows[-1]['regex']=r'^One of your (?P<item>.+?) \((?P<c>[a-z])\) was stolen!$'
add(431,'melee1.c',777,'Your <item> (<c>) was eaten!','item.eaten','self','medium','RBE_EAT_FOOD hit; a random TV_FOOD pack item chosen in 10 tries (melee1.c:759-790)','Same "One of your ..." variant if stack>1.',r'^(?:One of y|Y)our (?P<item>.+?) \((?P<c>[a-z])\) was eaten!$')
m(432,'Your light dims.','light.drained','self','medium','RBE_EAT_LITE hit; light source has pval>0 and sval<SV_LITE_DWARVEN (i.e. torch/lantern-class), player not blind (melee1.c:801-815)','fuel reduced 250-500 turns; not shown when blind')
m(433,'You are covered in acid!','attack.melee.effect.acid','self','high','RBE_ACID hit; always printed before acid_dam (melee1.c:824-833)','Printed regardless of resist; acid_dam may then damage armour (see spells1.c:990) and print item-damage messages. Damage taken via take_hit.')
m(434,'You are struck by electricity!','attack.melee.effect.elec','self','high','RBE_ELEC hit, printed before elec_dam (melee1.c:841-850)','elec_dam may destroy rings/wands (item.destroyed msgs elsewhere)')
m(435,'You are enveloped in flames!','attack.melee.effect.fire','self','high','RBE_FIRE hit, printed before fire_dam (melee1.c:858-867)','fire_dam may burn scrolls/staffs/etc.')
m(436,'You are covered with frost!','attack.melee.effect.cold','self','high','RBE_COLD hit, printed before cold_dam (melee1.c:875-884)','cold_dam may shatter potions')
m(437,'You stand your ground!','resist.fear','self','high','RBE_TERRIFY hit and p_ptr->resist_fear (melee1.c:938-941)','SAME text as row 438 (saving throw); distinguish only by knowing your own protection from fear')
m(438,'You stand your ground!','resist.fear','self','high','RBE_TERRIFY hit, no resist_fear but randint0(100) < skill_sav (melee1.c:943-946)')
m(439,'You are unaffected!','resist.free_action','self','high','RBE_PARALYZE hit and p_ptr->free_act (melee1.c:968-971)','Free action: paralysis blocked. Other sources of "You are unaffected!": spells (blind/hold/slow/nexus)')
m(440,'You resist the effects!','resist.save','self','high','RBE_PARALYZE hit, no free_act, randint0(100)<skill_sav (melee1.c:973-976)','Same text is used for every saving-throw success (many spells). Paralysis did not start.')
for base,pct,name in [(441,95,'EXP_10'),(444,90,'EXP_20'),(447,75,'EXP_40'),(450,50,'EXP_80')]:
    m(base,'You keep hold of your life force!','exp.drain.resisted','self','high',f'RBE_{name} hit, hold_life and randint0(100)<{pct} (melee1.c:{L(base)[1]-2}-{L(base)[1]})','No experience lost this blow (damage from take_hit still applies)')
    m(base+1,'You feel your life slipping away!','exp.drain.partial','self','high',f'RBE_{name} hit, hold_life but the {100-pct}% roll failed: lose_exp(d/10) (melee1.c:{L(base+1)[1]})','Exp loss is 1/10 of full; see lose_exp() in xtra2.c:1915 for follow-up messages (not read here)')
    m(base+2,'You feel your life draining away!','exp.drain','self','high',f'RBE_{name} hit, no hold_life: lose_exp(d) full (melee1.c:{L(base+2)[1]})','d = damroll(N,6)+exp/100*MON_DRAIN_LIFE')
m(453,'<monster> misses you.','attack.melee.miss','self','medium','blow fails check_hit; method is one of HIT,TOUCH,PUNCH,KICK,CLAW,BITE,STING,XXX1,BUTT,CRUSH,ENGULF,XXX2 AND monster is visible (melee1.c:1296-1323)','NO miss message for unseen monsters or for CRAWL/DROOL/SPIT/GAZE/WAIL/SPORE/BEG/INSULT/MOAN blows (silent miss). So an unseen attacker that misses is invisible in the log.')
m(454,'There is a puff of smoke!','monster.thief.teleport','self','high','after all blows, blinked==2 (EAT_GOLD stolen or saved-with-2/3, EAT_ITEM stolen/saved): monster teleported MAX_SIGHT*2+5 away (melee1.c:1346-1351)','Thief is gone; confirms theft attempt finished')
m(455,'<monster> blinks away.','monster.blink','self','medium','blinked==1: RBE_PARALYZE succeeded from a level-1 monster (level-1 monsters whose paralyze blow succeeds) (melee1.c:984-985,1352-1355)','Same text as spell RF6_BLINK (melee2.c:1578)')

# ---------- melee2.c automated ----------
def spelltag(f,l):
    ls=lines(f)
    for i in range(l-1,0,-1):
        mm=re.search(r'/\* (RF\d_\w+) \*/',ls[i])
        if mm: return mm.group(1)
def guard(f,l):
    ls=lines(f); g=[]
    for i in range(l-2,max(l-8,0),-1):
        s=ls[i].strip()
        if s.startswith(('if','else','} else')): 
            g.append(s)
            if s.startswith('if') and not s.startswith('else'): break
        if s.startswith('case ') : break
    return ' / '.join(reversed(g))
def thisline(f,l): return lines(f)[l-1].strip()
E={ 'ACID':'acid','ELEC':'lightning','FIRE':'fire','COLD':'frost','POIS':'poison','NETH':'nether','LITE':'light','DARK':'darkness','CONF':'confusion','SOUN':'sound','CHAO':'chaos','DISE':'disenchantment','NEXU':'nexus','TIME':'time','INER':'inertia','GRAV':'gravity','SHAR':'shards','PLAS':'plasma','WALL':'force','MANA':'mana','WATE':'water','ICEE':'ice'}
def conv(fmt):
    return fmt.replace('%^s','<monster>').replace('%s','<his>')
SAVE={'You resist the effects!':('resist.save','saving throw succeeded (randint0(100) < skill_sav)'),
      'You are unaffected!':('resist.immune','immunity (free_act / resist_blind / resist_nexus per spell)'),
      'You refuse to be frightened.':('resist.fear','resist_fear or saving throw'),
      'You disbelieve the feeble spell.':('resist.confuse','resist_conf or saving throw')}
for i in sorted(inp):
    r=inp[i]
    if r['file']!='melee2.c' or i>=659: continue
    f,l=L(i); fmt=r['format']; tag=spelltag(f,l) or ''
    short=tag.split('_',1)[1] if tag else ''
    text=conv(fmt)
    g=guard(f,l)
    cond=f'{tag} case; {g or "unconditional in case"} ({f}:{l})'
    aud='self'; rel='high'; note=''
    t=text
    if t in SAVE:
        ev,why=SAVE[t]; cond=f'{tag}: {why}; {g} ({f}:{l})'
        if t=='You resist the effects!': ev='resist.save'
        if t=='You are unaffected!':
            ev={'RF5_BLIND':'resist.blind','RF5_SLOW':'resist.free_action','RF5_HOLD':'resist.free_action','RF6_TELE_LEVEL':'resist.nexus'}.get(tag,'resist.immune')
        if t=='You refuse to be frightened.' : ev='resist.fear'
        note='Same text as other spells'' saves; only the preceding cast message identifies the spell.'
    elif t=='<monster> mumbles.':
        ev='attack.spell.unknown'; note='BLIND variant (p_ptr->blind) shared by ~45 spells/summons (%s here); says nothing about which spell. Damage/effect messages follow if any.'%tag
    elif 'mumbles' in t or 'strange noise' in t or 'grunt' in t or t=='<monster> breathes.':
        if 'strange noise' in t: ev='attack.ranged.unseen'
        elif t=='<monster> breathes.': ev='attack.breath.unknown'
        elif 'grunt' in t: ev='attack.ranged.unseen'
        else: ev='attack.spell.'+short.lower()
        note='BLIND variant (p_ptr->blind).'
        if 'grunt' in t: note+=' Format has a stray m_name arg; text has no monster name.'
    elif tag.startswith('RF4_BR_') : ev='attack.breath.'+E.get(short[3:],short[3:].lower()).replace('lightning','elec')
    elif tag.startswith('RF4_ARROW'): ev='attack.ranged.arrow' if tag in('RF4_ARROW_1','RF4_ARROW_2') else 'attack.ranged.missile'
    elif tag=='RF4_BOULDER': ev='attack.ranged.boulder'
    elif tag=='RF4_SHRIEK': ev='attack.spell.shriek'; note='aggravate_monsters(): wakes/hastes nearby monsters'
    elif tag.startswith('RF5_BA_'): ev='attack.spell.ball.'+E.get(short[3:],short[3:].lower()).replace('lightning','elec')
    elif tag.startswith('RF5_BO_'): ev='attack.spell.bolt.'+E.get(short[3:],short[3:].lower()).replace('lightning','elec')
    elif tag.startswith('RF6_S_'):
        if 'hear' in t: ev='summon.heard'; note='only when player blind AND count>0 (monsters actually created); this is the ONLY confirmation of a summon while blind'
        else: ev='summon.'+short[2:].lower(); note='summons happen around the PLAYER (x=p_ptr->px); spell result not verified by the message (count may be 0)'
    else: ev='attack.spell.'+short.lower()
    # per-text overrides
    if t=='<monster> makes a high pitched shriek.': pass
    if 'appears healthier' in t: ev='monster.heal'; rel='medium'; note='monster healed by draining your mana (seen only)'
    elif 'draws psychic energy' in t: ev='attack.spell.drain_mana'; cond=f'RF5_DRAIN_MANA: player csp>0 ({f}:{l})'; note='message shown whether or not blind (no blind branch) ; only when csp>0'
    elif 'focusing on your mind' in t: ev='attack.spell.'+short.lower(); note='"!seen" variant: printed when player blind OR monster not visible'
    elif 'blasted by psionic' in t: ev='attack.spell.%s.hit'%short.lower(); cond=f'{tag}: saving throw failed; followed by take_hit (%s), then confusion (mind blast) or blind+confuse+paralyze+slow (brain smash, each subject to resist/free_act) ({f}:{l})'%('8d8' if short=='MIND_BLAST' else '12d15'); note='confirms the psi damage landed; see status messages that follow'
    elif 'Your memories fade' in t: ev='status.forget'; cond=f'RF6_FORGET: save failed and lose_all_info() true ({f}:{l})'
    elif 'looks REALLY healthy' in t or 'sounds REALLY healthy' in t or 'looks healthier' in t or 'sounds healthier' in t: ev='monster.heal'; rel='medium'; note='"looks" = seen, "sounds" = not seen (blind/invisible)'
    elif 'recovers' in t: ev='monster.recover_courage'; rel='medium'
    elif 'starts moving faster' in t: ev='monster.haste'; rel='medium'; note='no blind branch: printed even when blind; first check mspeed<base+10 (+10 speed) else <base+20 (+2)'
    elif 'concentrates on' in t: ev='monster.haste' if 'body' in t else 'monster.heal'; rel='medium'
    elif t=='<monster> blinks away.': ev='monster.blink'; rel='medium'; note='no blind branch; printed even if blind ("It blinks away."). Same text as thief blink melee1.c:1354'
    elif t=='<monster> teleports away.': ev='monster.teleport'; rel='medium'; note='no blind branch'
    elif 'commands you to return' in t: ev='escape.teleport_to.forced'; note='RF6_TELE_TO: teleport_player_to(); no blind branch. Player is pulled next to the monster.'
    elif 'teleports you away' in t: ev='escape.teleport.forced'; note='RF6_TELE_AWAY: teleport_player(100); no blind branch; others see "<mon> teleports <player> away."'
    elif 'gestures at your feet' in t or 'mumbles strangely' in t: ev='attack.spell.tele_level'; note+=' If save fails, teleport_player_level() -> level change messages elsewhere.'
    elif 'gestures in shadow' in t: ev='attack.spell.darkness'; note='unlite_area(0,3): darkens room, may blind (message "You are blind!"?) if not resist - check spells2.c:4562'
    elif 'cackles evilly' in t: ev='attack.spell.traps'; note='trap_creation(): traps appear around player'
    elif 'tries to blank your mind' in t: ev='attack.spell.forget'; note='no blind branch'
    elif 'drains power from your muscles' in t: ev='attack.spell.slow'; note='no blind branch; save/free_act may follow'
    elif 'whirlpool' in t: ev='attack.spell.ball.water'; note='second line after "gestures fluidly"/"mumbles"; others see "<Player> is engulfed in a whirlpool." (msg_format_monster line 992)'; aud='self'
    elif 'fires an arrow' in t or 'fires a missile' in t: note='visible variant. bolt(); damage via take_hit; arrow can miss/be dodged (check_hit in spells) - see M-files for that'
    if 'mumbles, and you hear scary' in t or 'scary noises' in t: ev='attack.spell.scare'
    if 'puzzling noises' in t: ev='attack.spell.conf'
    if 'mumbles powerfully' in t: ev='attack.spell.mana_or_dark_storm'; note='BLIND variant for BA_MANA and BA_DARK'
    if 'mumbles loudly' in t: ev='attack.spell.cause_3'
    if 'DIE' in t: ev='attack.spell.cause_4'
    if 'incanting terribly' in t: ev='attack.spell.cause_3'
    if 'points at you and curses horribly' in t: ev='attack.spell.cause_2'
    elif 'points at you and curses.' in t: ev='attack.spell.cause_1'
    add(i,f,l,t,ev,aud,rel,cond,note,rx(t) if 'minions' not in fmt else None)
# fix row 612 & minions text
for rw in rows:
    if str(rw['id'])=='612':
        rw['text']='<monster> magically summons <his> <minions|kin>.'; rw['event']='summon.kin'
        rw['regex']=rx(rw['text']); rw['notes']='"minions" if summoner is UNIQUE else "kin" (melee2.c:1710-1712); summons same-letter monsters'
    if str(rw['id'])=='584': rw['notes']+=' (uses msg_format with no args; text unchanged)'
# extra other-audience rows
def ex(id,f,l,text,ev,aud,rel,cond,notes='',regex=None): add(id,f,l,text,ev,aud,rel,cond,notes,regex)
ex('X992','melee2.c',992,'<player> is engulfed in a whirlpool.','attack.spell.ball.water','others','low','RF5_BA_WATE cast at another player: msg_format_monster to nearby players (melee2.c:992-996)','Not in input CSV (call name msg_format_monster). fmt args = target name.')
ex('X1620','melee2.c',1620,'<monster> teleports <player> away.','escape.teleport.forced','others','low','RF6_TELE_AWAY seen by other nearby players (melee2.c:1620-1623)','Not in input CSV. Unseen: "It teleports <player> away."')
ex('X2946','melee2.c',2946,'You hear door burst open!','door.burst','others','low','monster bashes a door open; other nearby players get this (melee2.c:2946-2948)','Not in input CSV. NOTE missing "a": self version (row 663) reads "You hear a door burst open!"',r'^You hear door burst open!$')
ex('X3198','melee2.c',3198,'<monster> tries to pick up <item>, but fails.','monster.pickup.fail','others','low','RF2_TAKE_ITEM monster cannot take artifact/slayed item; no message if unseen (fmt_inv NULL) (melee2.c:3198-3202)','Not in input CSV.')
ex('X3215','melee2.c',3215,'<monster> picks up <item>.','monster.pickup','others','low','RF2_TAKE_ITEM monster picks up item (melee2.c:3215-3219)','Not in input CSV.')
ex('X3243','melee2.c',3243,'<monster> crushes <item>.','monster.crush_item','others','low','KILL_ITEM monster destroys item on floor (melee2.c:3243-3246)','Not in input CSV.')

# ---------- process_monster ----------
def p(i,t,ev,rel,cond,notes=''): add(i,*L(i),t,ev,'self',rel,cond+f' ({cite(i)})',notes)
p(659,'<monster> wakes up.','monster.wake','medium','sleeping monster wakes and is visible (melee2.c:2540-2551)')
p(660,'<monster> is no longer stunned.','monster.stun.off','low','visible monster stun timer ends (melee2.c:2590-2600)')
p(661,'<monster> is no longer confused.','monster.confuse.off','low','visible monster confusion ends (melee2.c:2630-2640)')
p(662,'<monster> recovers <his> courage.','monster.recover_courage','medium','visible monster fear timer ends (melee2.c:2660-2675)','Same text as heal-spell version (melee2.c:1562)')
p(663,'You hear a door burst open!','door.burst','medium','monster bashes door open (RF2_BASH_DOOR) (melee2.c:2945); other players get the version without "a"','An unseen monster is coming; also shown when door out of view (msg_print goes to p_ptr regardless)')
p(664,'The rune of protection is broken!','glyph.broken','medium','monster breaks glyph of warding on grid ny,nx marked (CAVE_MARK) for that player (melee2.c:2990-3000; sent to every player on the level who has the grid marked)','audience: every player at this depth with the grid in memory, not only p_ptr')
rows[-1]['audience']='others'
p(665,'<monster> turns to fight!','monster.fear.off','medium','frightened visible monster is cornered (!do_turn && !do_move && monfear) (melee2.c:3319-3336)')
# dead code
for i,t,n in [(666,'(empty)','screen_text_out body is in #if 0; monster1.c:1466 never executes'),(667,'Deep Unique (<name>).','commented out (cheat_hear) at monster2.c:1857'),(668,'Deep Monster (<name>).','commented out at monster2.c:1867'),(669,'Unique (<name>).','commented out at monster2.c:1878')]:
    add(i,*L(i),t,'dead_code','none','none','never executes: '+n,'Dead code: the msg_* call is inside a /* comment */ or #if 0. Pilot should ignore.','^$(?!)')
# pain
pain={}
def pn(i,t,cls,rng): 
    add(i,*L(i),t,'monster.pain','self','medium',f'message_pain(): {cls}; monster hp% after hit in {rng} (monster2.c:{L(i)[1]}). Sent for any dam>0 that did not kill, from melee/missile/spell damage, even if monster unseen (name "It")','')
pn(670,'<monster> is unharmed.','all classes: dam==0','damage 0')
cls=[('jelly/mold/vortex/Q (d_char in "jmvQ")',['barely notices.','flinches.','squelches.','quivers in pain.','writhes about.','writhes in agony.','jerks limply.']),
     ('C and Z (dogs, hounds)',['shrugs off the attack.','snarls with pain.','yelps in pain.','howls in pain.','howls in agony.','writhes in agony.','yelps feebly.']),
     ('d_char in "FIKMRSXabclqrst"',['ignores the attack.','grunts with pain.','squeals in pain.','shrieks in pain.','shrieks in agony.','writhes in agony.','cries out feebly.']),
     ('all other monsters',['shrugs off the attack.','grunts with pain.','cries out in pain.','screams in pain.','screams in agony.','writhes in agony.','cries out feebly.'])]
rng=['>95%','76-95%','51-75%','36-50%','21-35%','11-20%','<=10%']
idn=671
for c,ts in cls:
    for t,rg in zip(ts,rng):
        pn(idn,'<monster> '+t,c,rg); idn+=1
assert idn==699
# write
for rw in rows:
    re.compile(rw['regex'])
cols='id,file,line,text,event,audience,pilot_relevance,regex,condition,notes'.split(',')
with open(D+'M1_catalogue.csv','w',newline='') as fh:
    w=csv.DictWriter(fh,fieldnames=cols); w.writeheader()
    for rw in rows: w.writerow(rw)
print(len(rows))
ids={str(r['id']).split(':')[0] for r in rows}
print([i for i in inp if str(i) not in ids])
from collections import Counter
print(Counter(r['event'] for r in rows).most_common())
