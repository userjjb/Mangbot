# Study: danger table for 0–1500 ft (the first Clerk trial)

- **Status:** DONE 2026-09-27. Memo `../../../memos/2026-09-27-danger-table.md`; data
  `../../data/monsters/danger_table.csv`. No pass 3 needed.
- **Backlog item:** #1 in `../../../memos/2026-09-27-advisor-study-topics.md`.
- **Method:** `../../METHOD.md`. This is the first real use of Clerks, so watch how they behave and write
  a retrospective at the end.

## Goal (what the Architect will do with it)

A verified, name-keyed table of every monster the throwaway Half-Orc Warrior can meet at 0–1500 ft
(dungeon levels 0–30), plus the out-of-depth ones that vaults put there. For each monster, give a
recommended response (fight / avoid / leave the level) and the resist or item that neutralises it.
The table feeds the Pilot's danger list and the HANDBOOK.

## Questions

1. For each monster at levels 0–30: its threat profile: speed, HP, melee blows and their effects,
   spells and breaths (with frequency), flags (summoner, paralyzer, blinder or confuser, invisible,
   pass-wall or kill-wall, empty mind (invisible to ESP), breeder, never-move, groups or friends,
   unique).
2. Which features make a monster lethal to a low-level warrior? Rank them, with evidence from the
   mechanics (damage formulas in the 1.5 code).
3. What should the response be for each monster (fight / avoid / leave), and at what clvl or gear does
   that change?
4. Which out-of-depth monsters (levels 31–40, sometimes more) appear in shallow vaults, and how can
   they be recognised?
5. Where does the table agree or disagree with the forum memo's named dangers (Grip and Fang, Novice
   p's, Mughash, Wormtongue, Bullroarer, Orfax, Grishnákh, Azog, Shagrat, Gorlim, drolems, hounds by
   type, Mystics, Q's, molds, jellies, Elder aranea, acidic cytoplasm...)?

## Sources

- Primary: `/projectnb/jbrcs/mangband/github/lib/edit/monster.txt` (9285 lines). By level: 0 → 14,
  1–10 → 145, 11–20 → 99, 21–30 → 93, 31–40 → 122, 41+ → 143.
- Code for meaning and damage: `github/src/server/` (monster spells in `melee2.c`, blows in
  `melee1.c`, flag definitions in `github/src/common/defines.h` / `mdefines.h`, parsing in `init1.c`).
- Secondary: `../../../memos/2026-09-26-forum-distillation.md` and its appendix folder, and the forum
  corpus in `../../data/forum/corpus/`.

## Assignments (draft, adjust at start)

**Pass 1:**
- **A1 (legend + damage):** what every `monster.txt` field and flag means in 1.5; spell and breath
  damage formulas (breath = HP/x with caps, bolts, blows); which effects a Free Action, See Invisible,
  resist or ESP blocks. Output: a legend dispatch that the other Clerks get as input.
- **A2 (extraction):** a script that parses `monster.txt` into
  `Advisor/data/monsters/monsters.csv`, one row per monster with every field, plus a README. It's
  mechanical, but a Clerk checks it against 10 random entries. (It could run in parallel with A1.)

**Pass 2** (needs A1's legend; give each Clerk its band's rows from the CSV):
- **B1:** levels 0–10 (159 monsters). Threat profile and response for each.
- **B2:** levels 11–20 (99). Same.
- **B3:** levels 21–30 (93). Same.
- **B4:** levels 31–40 (122), the out-of-depth and vault threats: which ones are lethal on sight,
  and how to recognise them (glyph and colour, flags).
- **C1 (cross-check):** the forum memo's named dangers against the table and the code, and where
  they disagree.

**Pass 3:** as needed (contradictions, leads).

## Output

- The memo `../../../memos/<date>-danger-table.md`: a headline ranking of danger features, the
  table (or a pointer to `Advisor/data/monsters/danger_table.csv` plus the top ~40 in the memo),
  recommended Pilot rules and HANDBOOK text, and contradictions with the current docs.
- Data in `Advisor/data/monsters/`.

## Things to check at the start

- Is the `clerk` agent type available? It needs a session started in `Advisor/`. If not, restart.
- Read `../../../memos/to_advisor/` for any suggestions from the Architect.

## Decisions

- 2026-09-27: A2 (parser) done by the Advisor, not a Clerk: Clerks may write only their dispatch, and
  the job is mechanical. Result: `Advisor/data/monsters/monsters.csv` + `parse_monsters.py` + README;
  616 rows, band counts match; 4 random rows checked against raw entries.
- 2026-09-27: added **A3** (how out-of-depth monsters are generated: get_mon_num boost, vaults, pits,
  summons, wilderness, level persistence). B4 and question 4 need it.

## Pass log

- **Pass 1** (2026-09-27): A1 (legend + damage) and A3 (OOD mechanics) launched as Clerks in parallel;
  A2 done by the Advisor. Pass 2 (B1–B4, C1) waits for A1 (and A3 for B4).
  A1 returned: good; key claims verified (see synthesis.md).
- **Pass 2** (2026-09-27): B1, B2, B3, C1 launched in parallel (shared rules in briefs/B_common.md;
  band inputs scratch/B*_input.csv; outputs scratch/B*_table.csv + dispatches). B4 waits for A3.
  All of B1–B4 and C1 returned 2026-09-27; merged into data/monsters/danger_table.csv (synthesis.md).
  A3 returned: good (synthesis.md). B4 launched with A3 findings in its brief.

## Retrospective (2026-09-27)

**What worked**
- Seven Clerks (A1, A3, B1–B4, C1), ~1.1M subagent tokens in all, ~10–16 min each, all in parallel
  within a pass. Every Clerk answered its brief, covered its sources, and cited `path:line`. They
  found real things the Advisor didn't know: stacking paralysis (via A1's table), no-save status
  blows (B2), Brain Smash vs FA (B3), the floating eye's to-hit (B1), deliberate duplicate names (C1),
  the orc-pit ceiling (B4).
- A shared rules file (`briefs/B_common.md`) with verified facts, the character profile and one
  danger scale kept four band Clerks consistent; the Advisor's red-flag scan found only 5 ratings to
  change out of 473.
- Structured CSV output from Clerks (plus a dispatch) made merging trivial and made computed checks
  possible.
- Putting the verified facts in the brief ("use these") stopped Clerks from re-deriving or
  contradicting them.

**What went wrong / to change**
- Clerk arithmetic is the weak spot: breath from max vs average HP (Chimaera), "all blows hit"
  per-turn figures, a missed racial resist (Pseudo-dragon's dark breath). → Compute numbers by script
  (breath, speed, melee) and give them to Clerks as input columns; ask Clerks for judgement, not maths.
- The Advisor also erred once (forgot FORCE_MAXHP when "correcting" B1). → Check numbers with the
  same script, never by hand.
- Clerks answered "already known" items outside their band as contradictions ("Wormtongue isn't in
  my input"). → In briefs, give each band only the "already known" claims for its own band.
- One factual slip in C1 ("hounds have no melee blows") came from reading summary columns. → Brief
  line: "open the raw entry before making a claim about a specific monster's blows or spells".
- "Already known" lists written from memory contained deliberate and accidental errors (unique
  depths); Clerks caught them, which is good, but it cost words. Fine as a test; keep them short.
- Clerks can't write data files outside their dispatch, so the parser (A2) was done by the Advisor.
  Allowing scratch CSVs worked well: keep that.

**Changes to make in METHOD.md / clerk.md:** add "numbers by script, judgement by Clerk"; add the
raw-entry rule to clerk.md; allow a scratch CSV output as standard for table studies.
