# Study: estimator review, missions m61-m65 (2026-11-04)

**Goal:** tell the Architect and the user whether the shadow estimator's disagreements with the Pilot's rules are
real (rule changes worth making) or model artefacts (estimator fixes), now that missions have resumed.

Done by the Advisor directly (script work, no Clerks: all numbers come from the records and from re-running
options_sim on them).

- `scratch/estimator_records.jsonl`: every `estimator` record in decisions.jsonl, tagged with its mission.
- `scratch/table.py`: prints the records with their option tables (`tables_m63-65.txt`).
- Questions:
  1. Agree rates by trigger. 22 records in m63-m65 (policy 11-03p); m61 and m62 had no trigger.
  2. Why does the estimator disagree: bands, Speed, emergencies?
  3. The user's TODO: band XP ranking in set-piece A2L (phase > fight).
  4. The Architect's question: should the estimator model gear damage?
- Changes: options_sim 11-04q (optional acid_gold / disen_gold costs; replays unchanged 21/21).
- Memo: `../../../memos/2026-11-04-estimator-review.md`.
