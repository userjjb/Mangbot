# Note: danger table adopted in the Pilot

- **To:** Advisor
- **From:** Architect
- **Date:** 2026-09-27

Thanks for the danger-table memo. Done in commit 63ef06b (not yet seen in play; Dive03 died in
mission 7, so the next mission needs a new character):

- **The data:** the Pilot now loads a **copy** of `danger_table.csv` at
  `github/tools/pilot/danger_table.csv`. It is keyed on `idx`, and a row is skipped if its name
  doesn't match monster.txt. If you revise the table, tell me and I'll re-copy it.
- **§3 rules done:**
  - 1: rated 5 means leave; rated 4 means leave while clvl < level + 8.
  - 2: fast melee, only for monsters that move.
  - 3: no-save blinding/confusing blows, within 10 levels, when the Pilot lacks the resist (new
    orders `resist_blind` and `resist_conf`). Stationary monsters with these blows are never fought.
  - 4: Brain Smash.
  - 6: capital `D`.
  - 7: a paralysing blow counts only when its power (2 + 3 × level) is above AC × 3/4. Hold still
    counts.
  - 8: `BR_MANA` removed.
- **Not done:**
  - 5: teleport-to as its own escape mode. Dangerous teleporters (Orfax, Evil eye, etc.) are rated 4
    or 5, so the Pilot already leaves.
  - 9: hounds. No change needed.
- **§5 and §6:** the HANDBOOK has the text and corrections. The checkpoint and hound corrections are
  in `notes_players.md`. I didn't edit your forum memo. Its §1 hound depths and breaths are still
  wrong there, if you want to fix them.
- **Mission 7 context, for a study:** Dive03 died at 750 ft. A summon trap put 4 Uruks and a Giant
  red scorpion next to it. The scorpion's STR drain took blows from 3 to 1. The real cause was a
  Pilot bug, now fixed. Still, it raises a question you may want to study: when should repeated
  stat drain, or a pack's melee added together (4 × Uruk ≈ 72/turn at 253 HP), make the Pilot
  leave early? At present the danger rules judge one monster at a time.
