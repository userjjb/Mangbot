# Rubric for Navigator decisions (shared by N1-N3)

For each decision record (navigator.md line / nav_journal / goal or agent act in decisions.jsonl):
- type: depth | shopping | selling/identify | item test/use | equipment | flee/recall/escape | goal sequencing |
  pace/time budget | answer to user | other
- outcome: GOOD (clearly helped), NEUTRAL, COSTLY (gold/time/stat/HP lost; give the amount), NEAR-DEATH, DEATH
- doctrine: was there a HANDBOOK rule at that time (check `git -C /projectnb/jbrcs/mangband/github log -p --
  tools/pilot/HANDBOOK.md` for when a rule appeared)? FOLLOWED / VIOLATED / NO RULE
- accuracy: any factual claim in the journal or to the user (numbers, causes, monster stats, what the Pilot did) —
  check it against the logs/code: TRUE / FALSE (give the truth) / UNCHECKED
Count by type and outcome; list the 5 costliest decisions and every FALSE claim; list repeated violations.
Tag evidence [SEEN]/[INFERRED] as usual. Advisor memos already list some (selling unknown potions 4x, quaff-testing a
single Puce potion, Dagger vs Sabre, goto beside Brodda, Wormtongue HP 137 vs 250, recall "6 s" vs 9.7): confirm and extend.
