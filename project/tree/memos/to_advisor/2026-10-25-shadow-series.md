---
from: Architect
to: Advisor
date: 2026-10-25
re: shadow-mode series m35-m42 -- estimator records ready; two escape() changes for your base policy
---

**Data.** The user ran 8 missions of 45 minutes (m35-m42, Sonnet/Opus x medium/high rotating) with shadow mode on.
`runs/pilot/dive04/decisions.jsonl`, `kind == "estimator"` from t > 1792950000 (2026-10-25 14:10): **19 records
through m41** (m42 still running; it adds its own). Scorecard: `observe/scorecard.py --table m35 ... m42` (`est`
column). Mission reports: `runs/pilot/dive04/reports/2026-10-25-mission35.md` ... `mission41.md`.

**What I see (for your review, not conclusions):**
- 10 agree, 6 disagree, 3 `agree: None` (team empty: the monsters had left view by the cure that followed).
- Disagreements: the staff over the rules 4 times (15:39 two orcs; 16:33 Ufthak + gnome mages, SE 2; 18:26:06,
  18:26:19, 18:26:26 in m41's afraid fight), stairs twice (15:22 stairs 10 away; 18:26:16).
- **m41 18:25-18:26 is the case to replay:** Dive04 **afraid** (no Heroism left), a Half-orc, a Master yeek and a
  2-headed hydra adjacent, an unseen fear caster; the rules phased 3 times (156 -> 123 HP) and read Word of Recall;
  the estimator chose the staff each time (+81..+369 XP net vs rules). Does the simulator know a frightened warrior
  can't melee? If not, its "fight" option is wrong whenever the player is afraid.
- compute_s 0.01-0.57 s, all `in_time_turn: true`.
- Label fix: CSW/CLW cures are now labelled `cure` (were None; informational only -- `agree` compares the choice
  with "rules").

**escape()/flee changes since your POLICY_VERSION pilot-escape-2026-10-25b -- please bring base_policy in step:**
1. **Afraid with 2+ adjacent: Teleportation (staff or scroll) over Phase Door**, in a corridor too (commit 8945cb6;
   the existing rule was 4+ about in the open).
2. **Flee at max_depth with only '>' known: teleport on the level** (staff/scroll, once a minute) instead of '>'
   (c0908b4). Not in escape() itself but in the Flee goal.
3. Kits B/C now keep 3 Potions of Heroism (the fear cure).

**Yield:** ~2.5 estimates per 45-minute mission (emergencies are rare at 600-650 ft with this gear). If you want
more data, say where else the estimator should run (fight_going_badly? band decisions?) and I'll ask the user.
