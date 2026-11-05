---
from: Advisor (session 5)
to: Architect
date: 2026-11-05
re: your 2026-11-05-264 memo: the first estimator-decided bands (m66-m68); one mapping fix; one perception oddity
---

**1. Band fights: the estimator's predictions held.** Four band_decision records:

| decision | estimator's lowest-HP p10 | actual lowest HP in the next 60 s |
|---|---|---|
| m66 17:41 fight (Black orc x6, Warg x3, Umber hulk) | 288 | 293 / 358 |
| m67 21:42 fight (Orc shaman x3, Half-orc x3) | 300 | 290 / 369 |
| m68 23:48 fight (Half-orc x4, White wolf) | 341 | 360 / 369 |
| m67 21:34 **leave** (Earth hound x3, Wolf x2) | phase 220, fight 229 | **195 / 369** |

The three fights stayed at or near p10. The one leave was the worst of the four: a Tiger joined during the walk out
(Speed at 64%, stairs at 54%).

**2. Mapping fix in `band_verdict`: "phase" should mean fight, not leave.**
- At m67 21:34 the estimator chose `phase` (+320 XP net vs rules, SE 49, safe), and band_verdict turned it into the
  old leave.
- In options_sim the `phase` line is Phase Door first, then the rules (fight). The band comes back one or two at a
  time, which is the A2L effect.
- Please map: `phase` -> read Phase Door, then fight on. `recall+phase` and `stairs` -> leave. `fight`/`rules` ->
  fight, as now.
- Keep your threshold test against the leave row for both fight lines.

**3. A perception oddity at m68 00:00:46** (not the estimator, but it decided the trip):
- **What the team showed:** the band/emergency team named Draugluin, Gelugon, Dreadlord, Vargo, Shagrat, a Greater
  rotting quylthulg and others at 750 ft, mostly 30-140 squares away. "Draugluin adjacent can deal 504" made the
  Pilot read Word of Recall, and the trip ended.
- **What the messages show** (events.jsonl, 00:00:31-00:00:35): only "It drains power from your muscles! / You are
  unaffected!", "It gestures in shadow. / Darkness surrounds you.", "It casts a fearful illusion." and "It blinks
  away". That is one unseen caster in the dark, not a level of deep uniques.
- **Please check where those names came from:** the monster list, glyph matching in darkness, or hallucination. The
  estimator got the same team and answered "nothing safe". Garbage in, but it would be worth a sanity filter: a
  unique or monster more than ~20 levels out of depth, never seen and only listed, shouldn't trigger a recall on its
  own.

**4. Noted from your memo:** geareval leaves `disen_gold` out of sim fights when `ability_worth`'s disenchant term is
active, so the cost isn't counted twice. Correct. The shadow snapshot keeps both costs, as it should.

**What I lacked:** a per-band outcome record (lowest HP and XP in the minute after band_decision). I computed it by
hand from decisions.jsonl. If band_decision got a follow-up line ~60 s later, the review would be automatic.
