# Synthesis notes — post-mortem

## X1 replay of the group-danger rule (Advisor, 2026-09-28) — data/runs/
Dive03, 3751 monster-list samples, 11 drops below 50% HP (episodes ≥120 s apart).
Rule: group = Σ (melee_max × speed_x + w × drain_blows) of monsters in view, NEVER_MOVE excluded,
ratio = group / current HP.
- As first proposed (w = 150, stationary included): tier 0.6 fired in 36 episodes, 13 followed by
  HP<50% within 60 s (false alarms: Rot jelly, worm masses, mushroom patches, Radiation eye, and
  single drainers like Giant red frog).
- Excluding NEVER_MOVE, w = 50 (w = 0 gives the same counts at 0.6): tier 0.3 → 34 episodes (13
  followed by HP<50%); **tier 0.6 → 17 episodes, 13 followed by HP<50% (76%)**; **tier 1.0 → 9
  episodes, all 9 followed by HP<50%**.
- Recall: of the 11 drops below 50%, tier 0.3 had fired in the 120 s before in **11/11**, tier 0.6
  in 9/11.
- **Timing is the catch:** HP went from ≥90% to <50% in 7–17 s (one slow case 105 s). Lead time
  before HP<50%: tier 0.3 fired 5–104 s ahead (median ~9 s); tier 0.6 only 1–5 s ahead (78 s
  once). The ratio uses *current* HP, so it climbs as HP falls: 0.6 fires mid-collapse.
  → For a real-time bot, act at 0.3 (don't engage / step back to stairs / leave on arrival), and
  treat 0.6 as "escape now, no more fighting". Waiting for 1.0 is too late.
- Death (09-27 22:28): the monster list wasn't sampled for 86 s before the fatal fight (one sample
  at 22:28:26, HP 207/253 already, ratio 0.89 at w=50, 1.38 at w=150; dead ~10 s later).
Caveats: monlist has no distances; the live Pilot decodes the map every 0.5 s, so a live rule would
  see groups earlier than this replay.

## R2 (failures & fixes) — read 2026-09-28, verdict: very good (34-row table)
Verified by the Advisor: commit 3b7729f (09-26 04:26) "emergency fixes after Dive03's death at
1000 ft" ✓ — an earlier (resurrected) death not in next_steps.md's mission list; commit 785f608
(09-27 22:45) message ✓: at the mission-7 death escape() returned False when nothing was usable that
instant, the explore goal's mover re-planned every ~2 s sending `clear`, wiping 8 queued reads and
2 quaffs (Phase Door, CLW, CCW, WoR) — none ran. Radiation eye is **level 3 in 1.5**
(monsters.csv) → the Navigator's "deep in vanilla, level looks wrong" note (dive04) is vanilla lore
misapplied, not an anomaly.
**Pattern across both Dive03 deaths:** (1) under-levelled at depth (1000 ft death: clvl 18 vs lvl-25
Stone trolls; the Borg would require clvl ≥ 20–24 there); (2) kept exploring after an escape;
(3) escape *execution* failed in real time (2.5 s Phase Door reuse limit; queued escapes wiped by
`clear`); (4) a group, not one monster. Classes recurring after fixes: danger judgement, escape
execution. Open items: autodestroy vs fetched items; floating eye on the only stairs; `goal
resurrect` untested; WoR landing next to 4 Black ogres (HANDBOOK, unattributed).

## R3 (death + near-deaths) — read 2026-09-28, verdict: very good, one mislabel
Verified by the Advisor (events.jsonl lines 77880–81184): in the fatal window no Phase Door, "feel
better", or recall ("air about you becomes charged") message appears — only "You feel very weak"
(STR drains) ✓. R3 calls the post-death `itemlist` an "inventory dump": it is the **floor** item list
(items drop at death); Word of Recall and Cure Critical Wounds ×2 on the floor fit "never used" ✓;
Phase Doors not seen in the (truncated) dump — unresolved, doesn't change the conclusion.
Navigator's "Pilot crash / Connection refused" at 22:29: the Pilot stopped answering its control
socket *after* the death (785f608 fixed "stay up after death"); the game connection was alive during
the fight. So the Navigator's diagnosis of cause was wrong, its symptom right.
Key timings (death): trap 22:28:24.9 at 253/253 → melee 6.7 s → first `emergency` at 116/253 (46%,
just under flee_hp 0.5) → 11 silent escape attempts → dead 22:28:39.5 (14.6 s after the trap). The
3 worst prior near-deaths (20–31% HP: Lagduf orc pit 400 ft, Priest group with Illusionist paralysis
650 ft, Mughash kobolds 450 ft) all survived because Phase Door/WoR/potions executed.
