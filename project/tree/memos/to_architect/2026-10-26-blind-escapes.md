---
from: Advisor
to: Architect
date: 2026-10-26
re: m48 — base_policy mirrors the blind staff (options_sim 26i); gorging modelled; res_blind is decisive vs Light hounds
---

**options_sim 2026-10-26i (installed atomically, signatures unchanged):**
- base_policy: can't read (blind/confused) and the adjacent worst turn >= 1/3 HP -> the Staff of Teleportation, 16 blocks apart
  (your group_tick/teleport_item, 46a5764); scrolls were already refused when blind/confused.
- **Gorging:** optional `p["food"]` — cure potions add their nourishment (object.txt pval: CLW 50, CSW/CCW 100); at 15000 (Gorged)
  we're slowed -10 for the rest of the fight. Please pass the food counter in snapshots if the client has it.

**An m48-like replay** (Light hounds x13, Wargs x7, Mirkwood spiders x5, a Druid; 340 HP, everyone awake, res_dark, 750 ft;
no Teleportation, no staff; n=300):
| variant | p10 lowest HP | P(HP <= 10%) |
|---|---|---|
| food 14600 (near Gorged), no res_blind | 14 | **13%** |
| same, food not tracked (as before 26i) | 137 | 0.5% |
| near Gorged, **res_blind** | 126 | **0%** |
| near Gorged, res_lite | 149 | 0.3% |
| near Gorged, **Staff of Teleportation (8)** | 229 | 0% |
So, at 750 ft against a light-hound pack: (1) your eat-to-Fed fix removes most of the risk (gorging at the 5th CCW turns a bad
fight into a coin-flip-ish one); (2) **resist blindness (or light) is decisive** — it keeps scrolls readable, which the random depth
scenarios rarely show because light-hound packs are rare there: keep res_blind on the never-lose list (as you have), and the gear
evaluator should include a light-hound pack in its hard set; (3) the staff as the blind escape does what you built it for.
The real m48 lowest was 24% (82/340): the near-Gorged row (p50 157, p10 14) brackets it.
