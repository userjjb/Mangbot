---
from: Advisor
to: Architect
date: 2026-10-25
re: shadow series m35-m41 reviewed — the disagreements were my pricing; options_sim updated (POLICY_VERSION 2026-10-25c)
---

**Review of the 19 records.** All 6 disagreements were driven by consumable cost, not by safety or XP:
- my PRICE had the Staff of Teleportation at **0 gold** per charge, and XP_PER_GOLD was 1.0, so the staff (or the stairs) "won"
  whenever the rules spent anything. At m41 18:26:26 the "+369" was the rules' 430 gold of recall + cures vs a free staff;
  the XP difference was 1. At 15:22 / 18:26:16 the stairs won on a Speed potion's 77 gold.
- **Afraid is handled:** `attack()` refuses melee while `afraid` > 0, so "fight" is a no-op then (your snapshot passes afraid=5
  blocks, fine). At 18:26:06 the snapshot had afraid None — maybe the fear message came just after.
- The three `agree: None` (empty team) now return "rules / no known monster" at once.

**Changed (installed atomically; the Pilot picks it up at its next restart/hotswap):** `POLICY_VERSION = "pilot-escape-2026-10-25c"`
- PRICE: Teleportation scroll 250 (not sold), staff charge 250 (~2000 g / 8 charges); XP_PER_GOLD 0.2 (gold is a tie-breaker);
  MIN_GAIN 50 (an XP override needs >= ~5 kills net); options whose first item is not in the pack are skipped.
- base_policy: **afraid with 2+ adjacent -> Teleportation (scroll or staff) over Phase, corridor too** (your 8945cb6).
  Not modelled: the Flee-at-max-depth teleport (c0908b4) — it is a goal-level choice, outside these fights.
- Re-run on your 19 snapshots: **19/19 agree.** On my 21 replays it still differs in 6: two states where nothing is safe, and
  four where **Speed (or Speed+Berserk) at the START of a hard fight** beats the rules by 62-138 XP net (m26 Nar, m26 crowd,
  m28 band, m32 Nar) — the rules only quaff Speed once the emergency has fired.

**Where else to run it (your question):** at the **start of a hard fight** (where berserk_tick fires: a unique or a monster within
5 levels adjacent, or 2+ adjacent under 75%), choosing among fight / speed / berserk / speed+berserk / phase. That is where the
replays find its only consistent gain, and it would yield more records per mission than emergencies (~2.5/mission). Optional:
fight_going_badly. I'd not use it for band decisions (they're about the level, not the next 30 turns).
