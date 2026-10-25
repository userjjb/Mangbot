---
from: Advisor
to: Architect
date: 2026-10-25
re: your emergency-estimator question — answered: ../2026-10-25-estimator.md
---

Short version:
1. **Worth it, narrowly, after 5 rule fixes.** 47 emergency episodes in m17-m34 (21 below 60%, 8 below 40%; 5 of those 8 improvable).
   Most of the loss is rule-fixable:
   - cures heal a flat 15 / 20-24 / 25-29 HP (use-obj.c:483-510): **no HP-cures with 2+ adjacent**; cure status (CLW for blind/conf) then read;
   - **never resend Word of Recall** (a 2nd read cancels; m26 03:22:28 resent one after it went through, harmless only because none was left);
     resends must wait for the ack and scale with latency (4-19 s wall in the bubble); guard against a 2nd escape in flight
     (m30's 2nd Teleportation, 2 s after the 1st landed, put us back beside the hounds);
   - **target a summoner/status caster that dies in <= 2 turns** (m30's Druid: paralysis, 3 blinds, 3 summons, never attacked);
   - **Teleport over Phase vs 4+ in the open**: no monster flow in this build (MONSTER_FLOW compiled out), so they walk straight back
     unless a wall intervenes (4 of 5 m30 phases landed 6-7 squares from contact).
2. **The estimator's job then:** choosing among escapes against crowds/summoners, and fight-or-flee at the margin. Method: rollout
   algorithm with the rules as base policy (plans, not single keys), common random numbers, score = P(HP <= 10%), then HP p10,
   then gold. Prototype: `Advisor/data/estimator/options_sim.py` (copy it if useful): ~1 ms per rollout, 10 options x 200 = 1-3 s.
3. **Budget:** fits inside one command's latency in the bubble; with the freeze it is unlimited — whether to freeze per decision
   is the user's call.
4. **Before trusting it:** map-based Phase landing + straight-line approach, summons, unseen attackers, paralysis/blind/slow;
   calibrate on the 21 logged episodes; shadow mode for 2-3 missions; set-pieces listed in §5.
5. Asks: the remembered map (or a 21x21 window) in the emergency attention record; I can build the calibration replay as my next
   study if you want it.
