import csv
S='/projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-progression/scratch/'
st=list(csv.DictReader(open(S+'G1_stat_tables.csv')))
cons=[(11,'14'),(12,'15'),(13,'16'),(14,'17'),(15,'18/00'),(16,'18/10'),(17,'18/20'),(18,'18/30'),(19,'18/40'),(20,'18/50')]
with open(S+'G1_hp_expected.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['clvl','base_mean_hp(19+10*(L-1))','sd']+['hp_CON_'+c for _,c in cons])
    for L in range(1,51):
        b=19+10*(L-1); sd=(30.0*(L-1))**.5
        row=[L,b,round(sd,1)]
        for i,c in cons:
            bon=int(st[i]['adj_con_mhp'])
            row.append(b+bon*L//100)   # C int division; negative bonus not an issue here
        w.writerow(row)
with open(S+'G1_skills_by_clvl.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['clvl','skill_thn_before_stat(12+70+45*L/10)','skill_thb(-5+55+45L/10)','sav_before_wis(-3+18+10L/10)','dis_before_stats(-3+25+10L/10)','dev_before_int(-3+18+7L/10)','stl_final(-1+1+0+1)','srh(0+14)','fos(7+2)'])
    for L in range(1,51):
        w.writerow([L,12+70+45*L//10,-5+55+45*L//10,-3+18+10*L//10,-3+25+10*L//10,-3+18+7*L//10,1,14,9])
