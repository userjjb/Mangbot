# Synthesis: mission 24 study

## X1 XP by depth (data/scorecard/xp_by_depth.py -> xp_by_depth.csv), m17-m24, Dive04 clvl 15-22
| band | minutes | exp | exp/min | lowest HP |
|---|---|---|---|---|
| town | 102.5 | (119, recall-boundary noise) | — | 42% (m22, arrived low) |
| 50-250 | 20.0 | 10 | 0.5 | 100% |
| 300-450 | 56.5 | 479 | 8.5 | 72% |
| 500-650 | 70.7 | 4124 | 58.3 | 41% (m22) |
| 700+ | 36.0 | 1524 | 42.3 | 27% (m22) |
m24: 26.5 of 28.5 dungeon min at 300-450 (6.3/min); 1.5 min at 600 gave 310 exp. Town = 36% of all mission minutes.

## X2 depth model (data/rulebook/depth_value.py -> depth_value.csv), clvl 22, fight_dive04 profile
XP per allowed kill: 300 ft 2.1, 400 4.0, 500 6.2, 600 8.4, 650 10.3, 750 15.9, 1000 27.0, 1250 35.6, 1500 64.4.
HP lost per allowed kill scales with it: XP per HP ~4.6-6.6, flat from 400 ft to 1500 ft. Share of monsters refused ~14-19%.
P(level holds a LEAVE or p90>100% race, of ~18 placed) 2% at 300, 43% at 400, 50-60% 500-650, ~40% 700-1150, 60-72% 1200-1500.
=> deeper is not costlier per XP in HP; the limits are severe-threat levels (escape capacity: WoR stock, stairs) and arrival risk.

## Stale hand ratings (fight_dive04 p90 <= 30% HP but AVOID/LEAVE), 31 races <= level 20
Strength-only reasons now obsolete: Brodda (LEAVE, p90 24%, drop ~2.2k). Escort uniques (Mughash, Lagduf, Grishnakh, Golfimbul):
band rule covers. Qualitative ones stay (paralysis, drains, breeders, invisible, TELE_TO, summoners: Orfax, Boldor, Druid, Evil eye...).
Wormtongue (p90 17%, drop ~9.7k): SLOW without FA + HEAL + frost bolts — Navigator override case, killed in m21.
