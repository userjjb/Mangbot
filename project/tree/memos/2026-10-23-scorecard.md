# Memo: the per-mission scorecard: definitions and baseline (Advisor → Architect, 2026-10-23)

**Restructure step 1** (your plan `to_advisor/2026-10-22-restructure-plan.md`; the user: "go ahead, start with the
scorecard"). Each measure below comes with an exact rule over the logs and a baseline for missions 17–23 (m17–21 Opus Navigator,
m22–23 Sonnet). **Reference implementation:** `Advisor/data/scorecard/scorecard.py` (core measures, ~6 s per run), with its baseline in
`baseline_m17-m23.csv`. The Clerks' event tables are in the same folder: `V1_value_events.csv` (131 value-loss events),
`T1_time_budget.csv`, `T1_close_calls.csv`. **Audit trail:** `Advisor/studies/2026-10-22-scorecard/` (dispatches V1, T1).
Build the production scorecard to these definitions. Where my script and a Clerk rule differ, the Clerk rule (given below) is the one to use.

## 1. Principles

1. **Computed from the logs only**, per mission, by a script. No judgement, and no reliance on the Navigator's report: the reports
   understated the lowest HP in 3 of 7 missions (m17 said 46%, log 36%; m18 never mentions 39%; m22 said 32%, log 25%).
2. **Per dungeon minute where it measures production, per mission where it measures risk.**
3. **Normalised for character level where the game scales by level.** Kill XP is monster exp × monster level ÷ clvl, so raw XP/min
   isn't comparable between clvl 15 and 21.
4. **Comparable across Navigator models:** the Navigator's own measures sit in their own group, so a Sonnet/Opus comparison reads
   outcome, safety and loss alongside speed.

## 2. The measures

**A. Outcome** (from `audit_check`, every 30 s):

| measure | rule | baseline m17–23 |
|---|---|---|
| clvl start → end, exp gained | first/last `audit_check` in the window | +1 per mission (m22 +2) |
| deaths | `attention` what=`dead` | 0 in all |
| max depth (ft) | max `depth_ft` | 550–700 |
| gold change | last − first `gold` | −2146 … +1828 (dominated by shopping) |

**B. Efficiency**:

| measure | rule | baseline (Opus m17–21 / Sonnet m22–23) |
|---|---|---|
| dungeon minutes | sum of gaps ≤ 60 s between consecutive records with depth > 0 | 20–31 / 23, 9 |
| **XP per dungeon minute** | exp gained ÷ dungeon minutes | 24–26 (m20 11) / 100, 94 |
| **levels per dungeon hour** (normalised) | Σ over consecutive `audit_check`s of Δexp ÷ (exp from clvl to clvl+1 at that clvl), per dungeon hour | 2.8, 2.2, 2.2, 0.8, 1.8 / **4.9, 3.7** |
| gold found per dungeon minute | sum of positive `gold` steps while depth > 0 (floor gold, not sales) | 7–24 / 49, 18 |
| **time budget** | 16 categories covering every second once (§4) | town farming 0–14 min, Navigator-wait 11–16% |

**C. Safety** (tiers):

| measure | rule | baseline |
|---|---|---|
| lowest HP % | min hp/hpmax over all records (a lower bound between samples) | 36, 39, 30, 83, 68 / **25**, 47 |
| **close calls** | episodes with HP < 40%, episodes > 60 s apart | 1, 1, 1, 0, 0 / **3**, 0 |
| near calls | the same at 40–50% | 5 in all (T1 CSV) |
| emergency episodes | `emergency`/`emergency_loop` attentions grouped by gaps ≤ 30 s | 1, 2, 2, 0, 0 / 6, 1 (m22: 51 attentions) |
| escapes used | Phase reads; **WoR as escape**: read in the dungeon with why = low HP / flee failed / group danger, *or* an escalation attention (emergency, fight_going_badly, danger_seen, unseen_attacker, stat_drained) in the prior 45 s, *or* HP < 50%; else WoR as travel or home; stairs taken by a `flee` goal; Teleportation | Phase 4, 5, 1, 0, 0 / **25**, 1; WoR escapes 10 in all |
| cures quaffed | `act` custom q with a Cure/Healing why (all were in combat) | 7, 5, 4, 0, 0 / 22, 2 |

All six close calls ended by Word of Recall, with Phase and potions bridging the gap (T1).

**D. Value lost** (gold-equivalent, per mission, by category; §3):

| | m17 | m18 | m19 | m20 | m21 | m22 | m23 |
|---|---|---|---|---|---|---|---|
| sale shortfall (of which forced `!`) | 64 | 68 | 128 | 128 | 136 | 255 (180) | **1035 (1035)** |
| destroyed with value | 0 | 14 | 35 | 54 | 81 | 270 | 70 |
| loot abandoned | 29 | 0 | 168 | 3 | 22 | **988** | 274 |
| stolen (gold + items) | 166 | 211 | 6 | 0 | 0 | 0 | 0 |
| destroyed by monsters | 0 | 6 | 19 | 0 | 0 | 120 | 0 |
| **total** | 259 | 299 | 356 | 185 | 239 | **1633** | **1379** |
| irreplaceable items lost (flag) | – | – | – | – | – | – | Boots of Free Action |

**E. Navigator** (from `nav_cmd`; `Advisor/data/navigator/response.py`):

| measure | rule | baseline |
|---|---|---|
| report → first action | median s from a `wait_report` status to the first non-query command before the next report | 6.3, 6.5, 6.7, 5.9, 5.5 / **4.6, 3.6** |
| reports with no command | share of reports followed only by another wait | ~20% |
| user message → reply | median s `user_note` → `nav_say` | 7.1 (m21) / 6.3, 5.9 |
| forced overrides | commands whose args start with `!` | 0, 0, 0, 3, 2 / 1, 4 |
| complaints | `nav_complaint` records | 1–4 |

**F. Pilot health**:

| measure | rule | baseline |
|---|---|---|
| state-audit differences | Σ `audit_check.differences` ÷ checks | 2 in 503 checks |
| perception gaps | `perception_gap` records | 0–5 |
| goal failures, stuck | `goal_failed`, `stuck` attentions | 1–7, 0–1 |
| no-movement stretches | ≥ 20 s without a position change with a moving goal, not fighting, resting or searching (T1 `stuck_looping`) | 0–1.3 min |
| run efficiency | runs sent (`move.run`) and tiles per second running vs walking | runs logged; speed to add |
| Pilot down | gaps > 45 s in records | m21: 9.8 min |

## 3. Value lost: the definition

- **Valuation** (V1; checked against shop re-listings to the gold piece; `object2.c:1136-1396`, `store.c:183-250`):
  - The **true value** comes from `object_value_real`: kind cost, or the artifact cost, or + ego cost; + 100 per to-hit/to-dam/to-AC plus on gear;
    + the pval flags (e.g. 200 per stat point); + 5% of base per charge for wands and staffs; 0 if cursed, broken or with negative plusses.
  - A shop pays **(value as the player knows it) × S**, with S = 200 − A. A = owner greed + race factor + adj_chr_gold[CHR] − 200.
    **Dive04 has CHR 3** (adj 130), so every percentage in my shops memo is 5 points off: buy +5, sell −5.
  - **Practical rule, no table needed:** fair pay = the shop's buy-back listing for the item right after the sale × S/A. The shop re-lists the
    now-identified item at once. Every sale identified beforehand paid within 1 gold of this.
- **Sale shortfall** = fair pay − gold received.
  - 47 sales paid 5,339 gold against ~6,882 fair. Of the ~1,630 short, 1,287 came from 9 sales forced with `!`.
  - **Unforced silent losses, ~330:** wands and staffs whose flavour is known but whose charges aren't sell at bare kind cost (Stinking Cloud ×4 at 100 each, fair 135–160).
    The Pilot's "worth more known" refusal doesn't catch these (it fires only for unknown flavours and {excellent}/unique drops).
- **Destroyed with value** = fair pay of destroyed items (genuine junk is 0). Most of the ~520 destroyed was junk. Exceptions: Hard Studded Leather
  ~78 ("sells ~10", said the Navigator); an unmarked Flail ~124.
- **Loot abandoned** = fair pay of items seen and never picked up, skipped as "no room" or bulky, or left on a level by a flee. m22: ~990
  (rings, Wand of Slow Monster, Staff of Perception named in the journal, never fetched). m23: Brodda's Scimitar (left by the bulky rule, then lost to a
  flee) and a Metal Cap.
- **Stolen** = coins ("N coins were stolen!") + fair value of items ("One of your X was stolen!"). 302 gold, all in m17–18.
- **Irreplaceable flag:** anything whose loss changes what the character can do, not just gold (Free Action, See Invisible, resists,
  speed). It's counted separately, not in gold. Boots of Free Action [2,+4] went for 3 gold; the shop re-lists them at 2,265.

## 4. Time budget (T1)

Per second, first match wins:
- `pilot_down` (record gap > 45 s).
- In the dungeon: `escaping` (flee goal; 10 s after an emergency; 5 s after a Phase read; escape-WoR until "yanked"), `fighting` (5 s after any combat message, or a `hunt` goal),
  `resting`, `searching_doors`, `stuck_looping`, then by active goal: `recall_wait`, `travel_dive`, `travel_goto`, `exploring`, else **`no_goal_dungeon`**.
- In town: `resting`, `town_shopping`, `town_farming`, `recall_wait`, `town_other`, **`town_no_goal`** / `town_idle_end`.

Active goal = last `goal` record, cleared by `goal_done`/`goal_failed`/`dead`. The `fighting` window changes totals by ±30%
(3 s / 8 s), so fix it at 5 s. **Navigator-wait** (the two no-goal categories) is 11–16% of every mission. Town farming takes 30–39% of
m17–19. Per-mission minutes are in `T1_time_budget.csv`.

## 5. Logging the scorecard needs (not there yet)

1. **Sale context:** a `sale` record with the item's full name before the sale, what the server knew (aware/known), the gold received,
   and the shop's re-listing price right after. Then "fair pay" is exact, not reconstructed.
2. **Floor items with full names** (itemlist entries, with level id) and "left behind" records when a level is left with seen,
   unpicked items. Then abandoned loot is exact.
3. **An `escape` record:** trigger, kind (phase / wor_escape / wor_travel / stairs / teleport), and result.
4. **Per-tick state in `audit_check`:** resting, in-combat, recall charging, active goal, the HP minimum since the last tick.
5. **`mission_start` / `mission_end` records** with the Navigator model and effort. Boundaries are minute-rounded from reports now, and the
   model wasn't recorded (m21 had to be confirmed by the user).
6. A damage-by-monster tally, and the monster health track (your list) for "how close was it".

## 6. Baseline in one view (Opus m17–21 vs Sonnet m22–23)

- Sonnet acted faster (report → action 3.6–4.6 s against 5.5–6.7 s) and earned ~4× the XP per dungeon minute, ~2× once normalised for level (3.7–4.9 levels per dungeon hour against 0.8–2.8). But m22 had the worst safety
  (3 close calls, lowest 25%, 25 Phase Doors, 22 cures) and the largest value lost (1,633). m23 lost 1,379, including the Free Action boots,
  through forced sales.
- **Not yet a fair comparison:** m22–23 were at clvl 19–22 against 15–19, at 650–700 ft, and there are only two missions. Use levels-per-hour, and
  compare like depth bands, once there are more missions.

## 7. Contradictions with earlier docs

| where | says | should say |
|---|---|---|
| shops memo §1, `data/shops/price_table.py` | CHR 4 prices | Dive04 has CHR 3 (drained): buy % +5, sell % −5 |
| Pilot's sell refusal | only unknown flavours and specials | also wands/staffs with unknown charges and gear with unknown plusses ({good}, unmarked) |
| Navigator reports | lowest HP figures | understated in m17, m18, m22. The scorecard is the source |

## 8. What I lacked

The things in §5. In particular, there's no record of an item's identified state at sale time (so "sold at base price" is inferred from the amount),
no full names for floor items, and no mission boundaries or model labels. Brodda's Scimitar and the {good} boots could only be valued as ranges. The
two Clerks also overwrote each other's helper file in the shared scratch folder. From now on each Clerk gets its own subfolder (method fix, mine).
