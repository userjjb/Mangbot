# To the Advisor: a new reflex, equipment damage (2.57.0, 2026-11-04, the Architect, session 12)

m65 12:52 at 750 ft: a Water hound pack breathed acid 31 times (26 unseen); Dive04 resists acid, so HP barely moved and
the unseen-attacker rule kept it there while 21 "Your X is damaged!" took 22 points of armour (Shadow Cloak +8 -> +0,
Gauntlets/Cap/Boots +8 -> +4). Restoring it cost ~5,000 gold of Enchant Armor on 11-04 14:43.

2.57.0 (the user's decision) adds `_reflex_gear_damage` in combat.py, right after the unseen-attacker reflex: 2 equipment
damage events (acid minus_ac "is damaged!", or "was disenchanted!") within 10 s, or 300+ gold of restore cost within 30 s,
is danger -> hunt the source if it is in view and dies within 6 turns (fight_sim), else leave (stairs within 20, then
Teleportation, Phase (not vs unseen), Recall); an unseen breather always means leave. The cost of an event is the town
kit's repair (scroll price / chance at the plus after the hit), else the plus's resale value. `monster NAME` shows
"GEAR: acid damages armour / disenchants gear".

It is NOT in escape()/group_tick()/speed_start_tick()/berserk_tick()/fear_cure(), the functions options_sim mirrors.
Whether the estimator should model gear damage (acid/disenchant breathers as a cost, and this leave) is yours to judge.
Report: runs/pilot/dive04/reports/2026-11-04-mission65.md. Session 12 so far: m62-m65 (Sonnet medium) 79.5 / 58.7 /
78.0 / 75.7 XP/dmin on 2.50-2.55.
