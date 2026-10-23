# Study: the per-mission scorecard (restructure step 1; the user: "go ahead, start with the scorecard", 2026-10-22)

**Goal:** define what the scorecard measures and exactly how each number is computed from the logs, so the Architect can
build it (to_advisor/2026-10-22-restructure-plan.md), with a reference implementation and a baseline over missions 17-23
(m17-21 Opus Navigator, m22-23 Sonnet).

Missions (local time, from the Navigator reports): m17 10-16 13:57-14:40; m18 18:46-19:26; m19 22:14-22:55;
m20 23:41-00:18; m21 10-17 00:47-01:35; m22 01:45-02:15 (Sonnet); m23 10-22 22:15-22:30 (Sonnet, user-ended).

Metric groups (draft): outcome (XP, gold, clvl, depth, deaths), efficiency (per dungeon minute; time budget), safety
(close calls < 40% HP, lowest HP, escapes used, emergencies), consumption (potions/scrolls by kind, gold spent),
**value lost** (sold far below value, destroyed valuables, loot abandoned, forced overrides), Navigator (latency,
cadence, commands, overrides of Pilot refusals), Pilot health (audit error rate, run efficiency, stuck/loop events,
perception gaps).

| id | task | status |
|---|---|---|
| (Advisor) | core metrics script `data/scorecard/scorecard.py` | in progress |
| V1 | Clerk: value-lost events m17-23 + valuation method from object_value | launched |
| T1 | Clerk: time budget categories + close-call/escape definitions, validated against the reports | launched |
