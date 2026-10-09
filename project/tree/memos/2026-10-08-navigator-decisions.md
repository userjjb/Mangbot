# Memo: how good are the Navigator's decisions? Missions 1–16 (Advisor → Architect, 2026-10-08)

**The user's choice** (study 4 of the open leads). **Audit trail:** `Advisor/studies/2026-10-08-navigator/`. Three Clerks applied one
rubric (`scratch/rubric.md`) to every journal line: N1 Dive03 missions 1–7 (106 decisions), N2 Dive04 missions 8–13 (71), N3 Dive04
missions 14–16 with the user's live comments (119). The per-decision CSVs are in `scratch/N{1,2,3}_decisions.csv`. Response latency
was measured by script (`Advisor/data/navigator/latency.py`). Claims the memo relies on were checked by the Advisor in logs and git (**[✓]**).

## 1. The short answer

- **It has got better.** Costly decisions: 15% of Dive03's, 13% for Dive04 missions 8–13, 10% for missions 14–16.
  Near-deaths and deaths: 9 → 2 → 2. The Clerks classified "good" differently (N3 counted 26 good answers to the user), so compare
  the costly and near-death columns, not the good ones.
- **It mostly follows doctrine. When it loses, it's usually because the doctrine was wrong or missing, or a single rule was ignored at the worst moment.**
  - Dive03: 50 decisions followed doctrine, 12 violated it, 43 had no rule.
  - Missions 14–16: 33 followed, 5 violated.
  - **Correction to earlier Advisor statements:** the four sales of unknown potions (09-28 to 10-03) and the Puce Potion test (10-07)
    *followed* the HANDBOOK of their day ("sell unknown potions and scrolls found early" since 2a3d488; "quaff-test when safe" from 771d141).
    The doctrine was the error. STATUS and the mission 13 replay called them lapses. They weren't.
- **The one deadly violation: mission 10.** 22a436d (09-29 22:04:50) added "don't explore 250 ft and deeper with only 2 Phase and
  1–2 potions" **[✓]**. The Navigator left town at 22:08 with 1 CLW, explored 250 ft for 20 min, and died to Mughash at 22:29.
- **Its numbers are often wrong. Its stories usually aren't.** Most false claims are sampled or estimated figures: HP lows, recall seconds, durations,
  monster counts. Before 10-07 the report had no clock, and it still sees HP only when it gets a report.

## 2. Where the gold and HP went (costliest decisions, all missions)

| when | what | cost | kind |
|---|---|---|---|
| 09-26 16:39 | sold Wormtongue's armour unseen (Soft Studded Leather of Resistance) | 17 g received, 19,834 to buy back | selling by label |
| 09-29 22:08–22:29 | left with 1 CLW, explored 250 ft; died to Mughash | all gear, half the exp | **violated 22a436d** |
| 09-27 (M4, M6, M7) | went to 600–800 ft against the HANDBOOK's "450–550 ft" lesson; M7 died at 750 ft | Dive03 (clvl 22) | depth discipline |
| 09-26 16:16–16:52 | stayed at 1000 ft to "save a WoR", then two trips without Boldness | ~1,400 g of potions/scrolls, 2 WoR, HP 31% and 23% | depth/escape |
| 10-08 16:01 | sold an unidentified Trident {good} (+3,+7) | 42 g received, 1,848 to buy back (and ~34/round as a weapon) | selling by label (rule existed) |
| 10-08 15:58 | `destroy Light all` | 14 CLW | ambiguous name (now fixed) |
| 10-07 23:00, 10-08 15:47–15:51 | dived or explored on beside stat drainers (Red jelly STR, Rot jelly CHR, Purple mushroom patch CON ×2) | Restore STR 468, CON 18 → 14 | drain-and-continue (rule only since 7d608cb) |
| 10-03 12:22 | sold 2 unknown Speed + 2 Heroism | ~320 g | doctrine of the day |
| 09-28 01:47 | 354 of 366 gold on enchant scrolls, no cures | thin stock for the mission | money priorities |

**Best decisions** (the patterns worth reinforcing):
- reading WoR within 5 s of a failed flee (Lagduf, 10-07);
- the discount buys (WoR at 59/63/117);
- identifying the Lance before selling it (391 g);
- fetching the Wand of Slow Monster on the user's nudge;
- leaving early for the climb home (no mission overran its budget);
- diagnosing the no-light recall failure by reading the scroll itself (which led to a516853).

## 3. Recurring patterns and what would fix them

1. **Supplies and depth discipline** (most of the deaths and near-deaths): thin cures or no WoR below 250 ft (09-29 ×2, 10-03, 10-08
   stage B with 1 CCW + 3 CSW), and depth beyond the current lesson (Dive03 M4/M6/M7). The Navigator writes the risk in its own
   journal ("cures thin") and goes anyway. **Fix (Pilot):** a pre-dive gate. `dive`/`recall` down refuses when stock is below the stage
   table's minimum (cures, Phase ≥ 4, WoR ≥ 1, or 2 when recalling down), unless `force` is given. The reply should say exactly what's missing. This turns the
   doctrine the Navigator already knows into a check it can't skip by accident.
2. **Selling or destroying by label:** 5 gear errors in Dive03 and 3 since. Each new HANDBOOK rule covered only the last category
   (unique drops, then amulets, then {good}), never the general rule "compare with what you wear and identify before selling".
   The Pilot now guards {good}/{excellent}/unique drops, ambiguous names, and the Weapons line. **Remaining gap:** armour and jewellery against worn
   or empty slots. Suggest a report line `Better than worn: …; empty slots: …`.
3. **Acting on stale or sampled facts:**
   - Brodda's `goto` came from a report 17 s old (now held by the Pilot).
   - "Lowest seen 58" when the real low was 26; "single orc" when there were 12; "recall ~6 s" when it took 10; "45 s" when it took 11.
   
   **Fix (report fields):** `min HP since last report`, `monsters seen since last report` (with uniques), `seconds since the last
   level change/progress`, and the last recall's actual duration. The Navigator then quotes numbers instead of estimating them.
4. **Dead vs crashed:** in M7 the character died at 22:28:39 **[✓]**, the Pilot exited on death, and the Navigator reported "Pilot crash"
   after 35 retries over 12 min. **Fix:** write a last-words file or status ("dead: killed by an Uruk at 750 ft") before the Pilot exits, and
   tell the Navigator in its prompt that "Connection refused" right after an emergency usually means death.
5. **Persisting orders aren't visible:** Dive03's `think_hp 0.55` (set in M2) stayed for 5 missions, through two near-deaths. **Fix:** print
   non-default orders in the report header.
6. **Recall time is wrong in the HANDBOOK:** it says 15–35 s. Measured: 8–23 s (8 reads, mission 15; 9.7 s for Brodda, 10–11 s
   on 10-07). The code is 15–34 *player turns* at ~0.5–0.67 s each. Suggest "15–34 turns, about 8–23 s".
7. **Latency** (script): next order after `goal_done` median ~5 s (90th percentile 10–15 s). After emergencies and danger 15–28 s. After user messages,
   by commentary timing, median 7.2 s to the reply (N3; the script's 42–53 s counts the next *order*, not the reply). The Pilot handles
   emergencies itself, so latency mostly hurts when an order written for an old report lands on a new situation. That's what the
   Brodda `goto` hold now covers.

## 4. The user's live comments (missions 15–16)

46 `!` notes reached the Navigator. About 17 were corrections or tips, and **the user was right in ~15**: the zig-zag, the CSW on mold confusion,
interesting items beyond the loot radius, the Rot jelly, secret doors, "waiting won't search", identifying {good}, avoid zones, the Trident. The Navigator's
honest "I don't know" answers (on pathing and zig-zag) were good. Its invented numbers to the user (Wormtongue "~137 HP"; it's 250) weren't.
**Navigator WISH list (9 lines):** 7 have been implemented since (search, avoid, drainers, dead-end search, items beyond loot radius, by-name
safety, zig-zag). Still open: **killing rogues before they steal in townfarm** (~120 g lost in mission 15), and a **movement trace** in
`status`. Its "I have no run" wish rested on a false belief: the Pilot has run on straight stretches since e912370.

## 5. Suggested changes, by owner

**Pilot:**
1. Pre-dive supply gate (§3.1).
2. Report fields: min HP / monsters / uniques since the last report; time since progress; non-default orders; better-than-worn and empty slots.
3. Leave a "dead" status before exiting.
4. Townfarm: attack the town thieves on sight (EAT_GOLD/EAT_ITEM touchers: Filthy street urchin, Squint-eyed rogue, Scruffy looking hobbit; monster.txt N:1, 10, 61).

**Navigator prompt** (`.claude/agents/navigator.md`):
- Quote numbers from report fields; mark estimates "~est".
- Before any sell or destroy, use the letter and read the full name back.
- When a journal line says a supply or depth risk, either fix it now or write why not.
- "Connection refused" right after an emergency: assume the character died.

**HANDBOOK:**
- Recall time 8–23 s.
- The stage table's minimums as a checklist at the shop step.
- Drop the old money rule's legacy wording if any remains (unknown sales are now governed by the identify rules).

## 6. Contradictions with earlier Advisor memos

| memo | said | should say |
|---|---|---|
| STATUS (lead 3), mission-13 replay | unknown-potion sales and the Puce test were Navigator lapses "after the HANDBOOK warning" | they followed the doctrine of their day; the doctrine changed on 10-03 and 10-07 |
| mission-13 replay | "read the last WoR for an experiment" | the WoR was the only way home in 12 min; only the `stairs <` while it was pending was the experiment |

## 7. Coverage and gaps

- All 296 journal lines were classified. Outcome costs are estimates (gold at shop prices). Gold wasn't logged before 10-07, so N2 rebuilt it from store messages.
- The Navigator's final text reports and the exact arrival time of its commands aren't logged, so latency is measured to the next recorded order.
- The three Clerks used the same rubric but judged "good" and "neutral" with different strictness. The cross-period comparison uses the costly and near-death columns.
