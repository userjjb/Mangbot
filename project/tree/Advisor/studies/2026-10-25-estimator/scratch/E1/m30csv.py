import pickle,re,csv,collections
from common import *
rows=pickle.load(open('m30rows.pkl','rb'))
A=eps_('2026-10-25 06:42:55');B=eps_('2026-10-25 06:44:30')
pos=None;hp=None;mons=None;mons_t=None
sec=collections.OrderedDict()
def S(t):
    k=int(t)
    if k not in sec:sec[k]=dict(msgs=collections.Counter(),acts=[],npos=[],spells=[],notes=[],hp=None,pos=None,mons=None)
    return sec[k]
HITRE=re.compile(r'^(The |)(?P<who>[A-Z][A-Za-z\-\', ]+?) (hits|bites|claws|butts|crushes|gazes|stings|kicks|misses|touches|engulfs|crawls on|spits on) you')
for t,k,x in rows:
    if t<A-5 or t>B+5:continue
    s=S(t)
    if k=='V':pos=x[0];hp=x[1]
    if k=='P':pos=x;s['npos'].append(x)
    if k=='M':
        pos=x[0];hp=x[1];mons=x[2];s['mons']=x[2]
    if k=='A':
        s['acts'].append(x.split('  [')[0]);m=re.search(r'\[hp(\d+)\]',x)
        if m:hp=int(m.group(1))
    if k=='E':s['acts'].append('ESC '+x[:60])
    if k=='N' and not x.startswith('status'):s['acts'].append('NAV '+x)
    if k=='K' and x.startswith(('custom r','custom q','rest','walk','custom .')):s['acts'].append('cmd:'+x) if x.startswith(('custom r','custom q')) else None
    if k=='m':
        m=HITRE.match(x)
        if re.match(r'You (hit|miss)',x):s['msgs']['own melee']+=1
        elif m:
            who=m.group('who');kind=m.group(3)
            s['msgs'][f"{who}:{'miss' if kind=='misses' else 'hit'}"]+=1
        elif re.search(r'breathes|casts|mumbles|summons|drains|paralyzed|blind|confused|struck by|enveloped|hit by|destroyed|slain|killed|You have \d+ |You have a |You have no more|much better|speed up|moving slower|starts moving faster|blinks|teleports|yanked|charged|LOW HIT|resist',x):
            s['notes'].append(x[:70])
    if k=='T' and x.split(':')[0] in('emergency','tactic','fight_going_badly','emergency_loop','danger_seen','lost'):s['notes'].append('[Pilot] '+x[:90])
    if k=='F':s['notes'].append(f'[time factor {x}]')
    if k=='G':s['notes'].append('[goal] '+x)
out=[]
lastpos=None;lasthp=None;lastm=None;lastmt=0
mons_hist=[]
# carry forward hp, pos, mons per second
cur_hp=None;cur_pos=None;cur_m=None
# initial from earlier rows
for t,k,x in rows:
    if t>=A:break
    if k=='M':cur_pos=x[0];cur_hp=x[1];cur_m=x[2]
    if k=='V':cur_pos=x[0];cur_hp=x[1]
    if k=='P':cur_pos=x
for sec_t in range(int(A),int(B)+1):
    s=sec.get(sec_t)
    if s:
        # hp: min of A hp within? use last known
        pass
    # recompute: scan rows within this second for hp/pos/mons
    out_row=None
    cur_acts=[];cur_msgs=collections.Counter();cur_notes=[]
    if s:
        cur_acts=s['acts'];cur_msgs=s['msgs'];cur_notes=s['notes']
    # update state from rows in this second
    for t,k,x in rows:
        pass
    out.append((sec_t,s))
# state tracking pass
state={}
timeline=[]
ri=0
rows_sorted=rows
idx=0
cur_hp=None;cur_pos=None;cur_m=None;cur_m_t=None
rows_by_sec=collections.defaultdict(list)
for t,k,x in rows:rows_by_sec[int(t)].append((t,k,x))
for sec_t in range(int(A)-30,int(B)+1):
    for t,k,x in rows_by_sec.get(sec_t,[]):
        if k=='M':cur_pos=x[0];cur_hp=x[1];cur_m=x[2];cur_m_t=t
        if k=='V':cur_pos=x[0];cur_hp=x[1]
        if k=='P':cur_pos=x
        if k=='A':
            m=re.search(r'\[hp(\d+)\]',x)
            if m:cur_hp=int(m.group(1))
    if sec_t<int(A):continue
    s=sec.get(sec_t)
    adj=[];nview=None;near=None
    if cur_m is not None and cur_pos is not None and cur_m_t is not None and sec_t-cur_m_t<=3:
        adj=[m[2] for m in cur_m if max(abs(m[0]-cur_pos[0]),abs(m[1]-cur_pos[1]))<=1]
        nview=len(cur_m)
        near=min([max(abs(m[0]-cur_pos[0]),abs(m[1]-cur_pos[1])) for m in cur_m],default=None)
    elif cur_m_t is not None and sec_t-cur_m_t>3:
        nview=0 if False else None
    timeline.append([hms(sec_t),sec_t,cur_hp,f"{cur_pos[0]},{cur_pos[1]}" if cur_pos else '',
        ' ; '.join(s['acts']) if s else '',
        ' ; '.join(f"{k} x{v}" for k,v in (s['msgs'].items() if s else [])),
        ' ; '.join(s['notes']) if s else '',
        ','.join(sorted(collections.Counter(adj).keys())) if adj else '', len(adj), nview, near])
with open('m30_0643.csv','w',newline='') as f:
    w=csv.writer(f)
    w.writerow(['time','epoch_s','hp_of_303','pos_y,x','our_actions','hits_misses_on_us (monster:outcome xN)','other_messages_and_pilot_notes','adjacent_monster_names (last monster list <=3s old)','n_adjacent','n_in_view','nearest_monster_dist'])
    for r in timeline:w.writerow(r)
print(len(timeline))
