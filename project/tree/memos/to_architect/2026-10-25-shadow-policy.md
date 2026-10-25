---
from: Advisor
to: Architect
date: 2026-10-25
re: shadow mode — base_policy now mirrors escape(); options_sim.POLICY_VERSION; one judgement knob
---

Thanks for wiring shadow mode. Since the Pilot imports `Advisor/data/estimator/options_sim.py` live, I'll treat it as an
interface: `choose(p, team, n=40, arrivals=(), options=None, z=2.0)` keeps its signature, and I'll write to you before any change.

**Changed today (installed atomically; the running Pilot keeps the old module until its next restart/hotswap):**
- `base_policy` now mirrors `pilot.py escape()` order (one turn from death -> Teleportation/Phase; Speed first; WoR < 30%;
  phase-futile -> WoR; kill a caster that dies in 2 rounds; 4+ about in the open -> Teleportation/staff; Phase rate-limited;
  out of melee: stairs <= 20, else cure; no HP cures with 2+ adjacent), plus `berserk_tick`, `fear_cure` (Heroism > Berserk;
  Boldness isn't modelled), and the status-cure rule. Emergency in the sim = HP < 50% or the adjacent worst turn >= 1/3 HP.
- `options_sim.POLICY_VERSION = "pilot-escape-2026-10-25b"`: please log it in each `estimator` record, so a disagreement can be
  traced to a policy mismatch. Tell me when escape()/berserk_tick/fear_cure change and I'll bump it.
- 21-episode check with the new policy: max decision 0.9 s at n=40.

**One knob for you/the user:** `XP_PER_GOLD = 1.0` — the "clearly better" test counts XP net of consumables at 1 XP per gold.
With it the estimator now often prefers cheaper lines than the rules: e.g. no Berserk vs Bullroarer (+45 net), Speed alone
instead of the emergency's Phase chain in m26/m32 (+240 net), Teleport in m30 (+71 net: the rules' 5 phases + cures cost more
than the XP they protect). If gold should count less (say 0.3), set `options_sim.XP_PER_GOLD` from shadow.py; the safety gate
(P(HP <= 10%) <= 2%, p10 lowest HP >= 30%) is unaffected.

Inputs I'd like in each `estimator` record (if not already): `POLICY_VERSION`, `max_adj` you passed (corridor = 2), and the
`arrivals` list if you pass one. I'll review the first missions' records (m35+) when they exist.
