import re,csv,sys
S='/projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-progression/scratch/'
src=open('/projectnb/jbrcs/mangband/github/src/server/tables.c').read()
def arr(name):
    m=re.search(r'\b'+name+r'\[[^\]]*\]\s*=\s*\{(.*?)\n\};',src,re.S)
    body=m.group(1)
    out=[]
    for mm in re.finditer(r'([-+0-9 ]+?)\s*/\*\s*([^*]*?)\s*\*/\s*,?',body):
        expr=mm.group(1).strip(); lab=mm.group(2).strip()
        try: v=eval(expr)
        except: continue
        out.append((lab,v))
    return out
stat=['adj_str_td','adj_dex_th','adj_str_th','adj_str_blow','adj_dex_blow','adj_con_mhp','adj_wis_sav','adj_dex_dis','adj_int_dis','adj_int_dev','adj_str_hold','adj_dex_ta','adj_str_dig','adj_str_wgt','adj_dex_safe','adj_chr_gold']
tabs={}
for n in stat:
    a=arr(n); tabs[n]=a
    print(n,len(a))
# combined stat table
with open(S+'G1_stat_tables.csv','w',newline='') as f:
    w=csv.writer(f)
    w.writerow(['stat_ind','stat_label']+stat)
    for i in range(38):
        row=[i,tabs['adj_str_td'][i][0]]
        for n in stat:
            v=tabs[n][i][1]
            if n in('adj_str_td','adj_dex_th','adj_str_th','adj_dex_ta'): v-=128 if v>=100 else 0
            row.append(v)
        w.writerow(row)
bt=re.search(r'byte blows_table\[12\]\[12\]\s*=\s*\{(.*?)\n\};',src,re.S).group(1)
rows=re.findall(r'\{([^}]*)\}',bt)
with open(S+'G1_blows_table.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['P_index']+['D%d'%i for i in range(12)])
    for i,r in enumerate(rows): w.writerow([i]+[int(x) for x in r.split(',') if x.strip()])
pe=re.search(r's32b player_exp\[PY_MAX_LEVEL\]\s*=\s*\{(.*?)\n\};',src,re.S).group(1)
vals=[int(x) for x in re.findall(r'(\d+)L?,?',pe)]
print(len(vals))
fact=110
with open(S+'G1_player_exp.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['index','base_exp_to_leave_level_index+1','halforc_warrior_needed(base*110/100)','reach_clvl'])
    for i,v in enumerate(vals): w.writerow([i,v,v*fact//100,i+2])
ee=re.search(r'u16b extract_energy\[200\]\s*=\s*\{(.*?)\n\};',src,re.S).group(1)
ev=[int(x) for x in re.findall(r'\b(\d{3,4}),',ee+',')]
print(len(ev))
with open(S+'G1_extract_energy.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['speed_index','energy_per_game_turn'])
    for i,v in enumerate(ev): w.writerow([i,v])
ls=re.search(r'u16b level_speeds\[128\]\s*=\s*\{(.*?)\n\};',src,re.S).group(1)
lv=[int(x) for x in re.findall(r'\b(\d{4,5})\b',re.sub(r'/\*.*?\*/','',ls))]
print(len(lv))
with open(S+'G1_level_speeds.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['depth_level','level_speeds','level_speed()=x5 (energy threshold)'])
    for i,v in enumerate(lv): w.writerow([i,v,v*5])
