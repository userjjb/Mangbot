import sys; sys.path.insert(0,'.')
from t1c import *
import pickle
allm=pickle.load(open('msgs.pkl','rb'))
from budget import COMBAT_PLAYER,COMBAT_MON,ESC_TRIG
def kind_of(d):
    c,w=d['cmd'],d['why']
    if not re.match(r'custom [qrzua] ',c): return None
    wl=w.lower()
    if 'phase door' in wl: return 'phase'
    if 'word of recall' in wl or "['word_of_recall']" in wl: return 'wor'
    if 'teleportation' in wl: return 'teleport_scroll'
    m=re.search(r'Cure (Light|Serious|Critical) Wounds',w)
    if m: return 'c'+m.group(1)[0]
    if "Cure_Critical" in w: return 'cC'
    if 'Heroism' in w or 'Boldness' in w or 'Bold' in w: return 'heroism_boldness'
    return None
rows={}
for L in LABELS:
    R=recs(L); a,b=win(L)
    cm=[e for e,t,ty in allm[L] if (COMBAT_PLAYER.search(t) or COMBAT_MON.search(t))]
    import bisect
    cm.sort()
    def incombat(t):
        i=bisect.bisect_right(cm,t)-1
        return i>=0 and t-cm[i]<=5
    attn=[(d['t'],d['what']) for d in R if d['kind']=='attention']
    yanks=[e for e,t,ty in allm[L] if 'yanked upwards' in t]
    C=collections.Counter()
    wl=[]
    for d in R:
        if d['kind']!='act': continue
        k=kind_of(d)
        if not k: continue
        src='nav' if d['why'].startswith('agent') else 'pilot'
        if k=='phase':
            C['phase_'+('lowHP' if d['why'].startswith('low HP') else 'groupdanger' if d['why'].startswith('group') else 'other')]+=1
            C['phase_incombat' if incombat(d['t']) else 'phase_outcombat']+=1
        elif k in('cL','cS','cC'):
            C[k+'_'+('incombat' if (incombat(d['t']) or 'combat' in d['why'] or d['why'].startswith('low HP')) else 'out')]+=1
            C[k+'_'+src]+=1
        elif k=='teleport_scroll': C['teleport_scroll']+=1
        elif k=='heroism_boldness': C['hero_bold']+=1
        elif k=='wor':
            dep=d.get('depth') or 0
            hard=bool(re.match(r'low HP|flee failed|group danger',d['why']))
            trig=[w for tt,w in attn if d['t']-45<=tt<=d['t'] and w in ESC_TRIG]
            hpf=d['hp'][0]/max(1,d['hp'][1])
            if dep==0: kk='wor_travel_down'
            elif hard: kk='wor_escape_pilot'
            elif trig or hpf<0.5: kk='wor_escape_navordered'
            else: kk='wor_planned_home'
            C[kk]+=1
            wl.append((hhmmss(d['t']),dep,kk,src,d['why'][:50],round(hpf,2),trig[:3]))
    # messages
    C['msg_phase_uses']=sum(1 for e,t,ty in allm[L] if re.match(r'You have (\d+|a|no more) Scrolls? of Phase Door( \{[^}]*\})?( \([a-z]\))?\.$',t) or re.match(r'You have no more Scrolls of Phase Door',t))
    C['msg_wor_charged']=sum(1 for e,t,ty in allm[L] if 'air about you becomes charged' in t)
    C['msg_yank_up']=len(yanks); C['msg_yank_down']=sum(1 for e,t,ty in allm[L] if 'yanked downwards' in t)
    # flee goals
    for d in R:
        if d['kind']=='goal' and d.get('goal','') and d['goal'].startswith('flee'):
            C['flee_goals']+=1
        if d['kind']=='attention' and d['what']=='goal_done' and d['detail'].startswith('flee'): C['flee_done_by_stairs']+=1
        if d['kind']=='attention' and d['what']=='goal_failed' and d['detail'].startswith('flee'): C['flee_failed']+=1
        if d['kind']=='attention' and d['what']=='emergency' and 'took the stairs underfoot' in d['detail']: C['emerg_stairs_underfoot']+=1
        if d['kind']=='attention' and d['what']=='emergency': C['emergency_attn']+=1
        if d['kind']=='attention' and d['what']=='emergency_loop': C['emergency_loop']+=1
    rows[L]=(C,wl)
    print(L,dict(sorted(C.items())))
    for w in wl: print('    ',w)
pickle.dump(rows,open('cons.pkl','wb'))
