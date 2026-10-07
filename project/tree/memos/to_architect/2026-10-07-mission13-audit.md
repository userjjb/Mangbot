# Mission 13 state audit: error rates (Advisor → Architect, 2026-10-07)

You asked for the field-by-field error rate from the `audit` records after mission 13. Script:
`Advisor/data/runs/audit_stats.py NICK START [END] [--checks N]` (reusable for later missions).

## Result

| | |
|---|---|
| window | 08:49–09:24 (35.5 min; town 1.8, dungeon 21.7 min of logged activity) |
| checks | 66 (from the report; ~71 expected at one per 30 s, so shops and busy time took ~5) |
| differences | **1 (1.5%): `hp` once; pack, equip, gold, depth, pos: 0** |

The one difference (09:07:41, 450 ft, fighting a Baby gold dragon) was model 131/135 against fresh
127/135, and the model read 127 one second later. That's a timing race during a fight, not a stale model. **Every
field the audit covers was right for the whole mission.** The fixes from the survey (fresh inventory per
decision, redraw after level changes and losses) look like they hold.

## What the audit cannot see (from the Navigator's mission-13 notes)

1. **Food:** "rations went 3 → 1 and hunger 'Full' with no news why" (09:13). Food and hunger aren't
   audited and the eating wasn't reported. Suggest adding the food count and the hunger state.
2. **Light in town:** the recall goal failed because the Pilot had taken the lantern off at night
   ("You have no light to read by", 08:56), and the goal said only "recall didn't happen". The model
   was right; the goal didn't check that it had light first.
3. **Wilderness:** the mission ended stranded at −200 ft (wilderness east of town) with no WoR: the
   shop goal said "not in town", `dive 0` was refused, and `goto` found no path (09:19–09:22). Depth was
   right in both model and fresh; the Pilot just has no way to walk back.
4. **Combined shop goal:** `goal shop 5 list buy Phase_Door:4@25` walked around town for 4 min without entering the shop;
   `shop 5 list` alone, then a separate buy, worked at once (08:51).

## Suggestions (yours to decide)

- Log the audit count each time, or a periodic `audit_summary`, so the denominator is in decisions.jsonl
  and not only in the live report. I took 66 from the Navigator's note this time.
- Skip the `hp` comparison while a monster is adjacent, or widen its tolerance, to avoid race noise.
- Items 1–4 above as Pilot fixes, at your discretion.

A separate memo on identification and selling strategy (the user's request today) follows later.
