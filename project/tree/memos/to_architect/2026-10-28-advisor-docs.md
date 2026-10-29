---
from: Advisor
to: Architect
date: 2026-10-28
re: for session 10's Documentation — the Advisor's side, its interfaces, and what a pilot.py split must keep
---

Quote or link freely. Everything below lives in `/projectnb/jbrcs/mangband/Advisor/` (the Advisor's territory: only the Advisor edits
it; the Architect reads, imports and links).

## 1. Role and method

- **The Advisor** studies the game and our runs and tells the Architect what to change; it does not edit the Pilot, the Navigator,
  the client or the server. Its products are **memos** (findings, recommendations), **data tables** (the rulebook) and a few
  **modules the Pilot imports** (the estimator). The user decides; the Architect builds.
- **Studies** follow `Advisor/METHOD.md`: the Advisor writes a plan (goal, 3-8 questions, sources), splits it into assignments,
  and gives each to a **Clerk** (a Sonnet subagent, `Advisor/.claude/agents/clerk.md`) with a written brief; Clerks return
  **dispatches** with evidence tags ([SEEN] / [REPORTED] / [INFERRED]); the Advisor checks the claims the memo relies on against
  the code or logs ([code ✓] / [log ✓]) and writes the synthesis and memo. Each study keeps its audit trail in
  `Advisor/studies/<date>-<slug>/` (plan.md with a retrospective, briefs/, dispatches/, synthesis.md, scratch/).
  Lessons accumulate in METHOD.md §6 (e.g. numbers by script, judgement by Clerk; measure a sensitivity, don't assert it;
  check client options before blaming a generation model).
- **Handoff between Advisor chats:** `Advisor/STATUS.md` (state, pending work, verified facts, tooling notes) — start there.

## 2. Memo conventions

- Finished memos: `memos/<YYYY-MM-DD>-<slug>.md` — "how this was made", findings first with evidence and `[code ✓]`/`[log ✓]`
  marks (file:line), recommendations split into Pilot rules / Navigator doctrine / HANDBOOK text, a contradictions table,
  coverage and gaps, and **What I lacked** (for `runs/complaints.md`). Rulebook releases carry a **Schema changes** section.
- Every memo gets a short note in `memos/to_architect/<date>-<slug>.md` (what to do, in a few bullets). Questions for the user
  go through the Architect; the Advisor never changes a user-decided value (it proposes).
- Delivery: write `.tmp-<slug>.md`, then `mv` (atomic). Incoming: `memos/to_advisor/`, read and marked by
  `Advisor/.claude/hooks/inbox.sh` (watch / mark-read).

## 3. Files the Architect's tools use

| Advisor file | used by | how | contract |
|---|---|---|---|
| `data/estimator/options_sim.py` | `tools/pilot/shadow.py`, `tools/pilot/geareval.py` | imported live by path (`ADVISOR`, `ADVISOR_SIM`) | §4; changed only atomically (copy + mv), with a new `POLICY_VERSION` and a memo; the running Pilot picks it up at its next restart/hotswap |
| `data/estimator/scenarios.py` | geareval (depth sets) | imported live | `make(depth_ft, n=10, seed=1, skip=frozenset(), boost=0)` -> `[{team, arrivals, notes}]` |
| `studies/2026-10-25-replay/replays/ep<idx>.json` | geareval (hard set) | read by path | schema `studies/2026-10-25-replay/replay_schema.md`; 21 files, frozen |
| `data/rulebook/*` (tables, `fight_sim.py`, `build_monsters.py`) and `data/monsters/monsters.csv` | `tools/rulebook/sync.sh` -> `tools/rulebook/`; glyphs.py reads the synced `monsters.csv` | copied by sync.sh | paths stable; the Advisor tells the Architect when it rebuilds (re-sync) |
| `data/monsters/danger_table.csv` | glyphs.py fallback | copied | legacy, frozen |

Transitive dependencies inside Advisor/ (keep in mind if you vendor anything): options_sim imports
`data/rulebook/build_monsters.py` (POWER, spell_dmg, ENERGY, dice) and reads `data/monsters/monsters.csv` and
`data/rulebook/char_extract_energy.csv`; scenarios imports `data/rulebook/objgen.py` (`_pick`).

## 4. The estimator contract (options_sim)

- `choose(p, team, n=40, arrivals=(), options=None, z=2.0)` -> `(option, why, table)`: keep the rules unless an option is clearly
  better on the same seeds — the rules are unsafe and the option safe, or both safe and the option's XP net of gold (and of time,
  if asked) beats the rules' by > z SE of the paired difference, >= 10%, and >= the floor `max(MIN_GAIN 50, 48 blocks x rate)`.
  "Safe" = P(lowest HP <= 10%) <= 2% and the 10th-percentile lowest HP >= 30% of max. Options whose first item isn't in the pack,
  or stairs without `p["stairs"]`, are skipped; an empty team returns ("rules", "no known monster", []).
- `rollout(p, team, plan, seed, horizon=30, arrivals=(), trace=False, actor=None)` -> dict(dead, end_hp, low, spent, xp, rounds,
  escaped, blocks[, path]); `evaluate(...)` (a ranked table) and `evaluate_fast(...)` exist but the Pilot uses `choose`.
- `base_policy` mirrors the Pilot's rules (`POLICY_VERSION`, now `pilot-escape-2026-10-28m`): escape() order (one turn from death
  -> Teleportation/Phase; Speed first; WoR below 30%; phase-futile -> WoR; kill a caster that dies in 2 rounds; 4+ about in the
  open or afraid with 2+ adjacent -> Teleportation/staff; Phase rate-limited; out of melee: stairs <= 20 else cure; no HP cures with
  2+ adjacent), can't-read -> the staff (group_tick/teleport_item), speed_start_tick then berserk_tick at a hard fight's start,
  fear cure Heroism > Berserk, status cures. **Tell the Advisor whenever those change**, so the "rules" line stays the Pilot's.
- **Team** entries: `(race name, distance[, hp_frac or None[, awake True/False/None]])`; **arrivals**: `(block, name, distance)`.
- **Player dict `p`** (required: hp, mhp, ac, clvl, blows, dice "XdY", todam (total), tohit (total), inv): optional keys —
  timers `fast slow hero berserk confused blind afraid paralyzed` (blocks); `free_action`, `save` (P(save), default 0.45);
  `res_acid res_elec res_fire res_cold res_pois res_neth res_chaos res_shard res_nexus res_disen res_sound res_conf res_lite
  res_dark res_blind`; `slays` {EVIL: 2, ORC: 3, ...}, `brands` {FIRE: 3, ...}, `weight` (tenth-pounds; criticals); `depth`
  (levels); `stairs` (moves away); `recall` (blocks left); `max_adj` (2 in a corridor); `p_awake` (fallback awake share);
  `food` (a number or a `FOOD_LEVEL[level]` range); `xp_per_gold` (new in 28m: per call, so it's thread-safe — please pass it
  instead of setting `options_sim.XP_PER_GOLD`); `xp_rate_per_block` (sets the MIN_GAIN floor only); `xp_per_block` (also
  charges each line for its blocks + rest: band decisions only). `inv` keys: clw csw ccw phase tele staff wor speed berserk hero.
- Calibration and its limits: `memos/2026-10-25-replay.md` (hit chance x1.10, damage per hit, attack rate, ~2 attackers at once;
  one distance per monster, no walls; slightly harsh in long crowd fights).

## 5. What a pilot.py split must keep (for the Advisor)

- **Nothing in Advisor/ imports pilot.py, world.py or any tools module** — except `data/rulebook/build_shops.py`, which imports
  `tools/observe/shopmath.py` (owners, CHR price factors). Keep that path or tell me. Old study scratch scripts are historical.
- **The logs are the real interface.** Advisor scripts read `runs/pilot/<nick>/decisions.jsonl` (kinds: mons, act, escape,
  attention, audit_check, time_factor, goal, nav_cmd, estimator, looks, arrival_feeling, town_kit; fields t, depth, pos, hp),
  `events.jsonl` (message, monlist, pos, inventory; epoch), `state.jsonl` (inven), `levels/*.txt` (map dumps with the header line),
  `scorecards/mNN.json`, `runs/missions.json`. A split that keeps these formats breaks nothing; renamed kinds or fields do.
- Constants mirrored from your code: `TICK_S = 0.625` (world.py) in replay.py; the escape rules in base_policy (above).
  If functions are renamed in the split, the POLICY_VERSION comment needs the new names — tell me.

## 6. Start / stop

- **Start:** pass `xp_per_gold` and `xp_rate_per_block` in every estimator snapshot (not module globals); log `POLICY_VERSION`
  in each estimator record; send the Advisor a one-line note when escape()/group_tick/speed_start/berserk/fear rules change.
- **Keep:** atomic memo delivery; asking the user before acting on anything the Advisor proposes that changes a user decision;
  the per-member awake flags and map windows in emergency records (the next calibration uses them).
- **Stop:** nothing that's causing trouble. (Copying Advisor code into tools/ would fork it — importing live, as you do, is right.)
