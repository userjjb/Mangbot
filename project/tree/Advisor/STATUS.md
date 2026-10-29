# Advisor status and handoff (updated 2026-10-24, session 4; the clock said 2026-10-23 — file dates follow the 10-24 series)

Read this first in a new Advisor chat, then `METHOD.md` before starting any study. Check
`../memos/to_advisor/` for unread memos (`.claude/hooks/inbox.sh unread ../memos/to_advisor`).

## State: the RESTRUCTURE (since 2026-10-22)

**No study is running.** The project is restructuring its autonomous player (the user's decision after mission 23):
restructure, not rewrite; keep Dive04; instruments first; mission-by-mission patching is frozen. The Architect works on git
branch `restructure` (tag `pre-restructure` = 767bf60 is the restore point). Plan: `../memos/to_advisor/2026-10-22-restructure-plan.md`;
step-2 design: `../restructure-step2.md` (read only). Basis: our `../memos/2026-10-19-starting-over.md`.

**Roles agreed:** the Advisor owns **the rulebook tables** and **the set-piece list**, and defined **the scorecard**; the
Architect builds everything else.

| step | what | Advisor's part | status |
|---|---|---|---|
| 1 | instruments | scorecard definitions + baseline m17–23 | **done** (`../memos/2026-10-23-scorecard.md`, `data/scorecard/`); the Architect built the production one (`github/tools/observe/scorecard.py --check`, `runs/missions.json`) and the new log records |
| 2 | who decides what | (inputs only) | Architect: 2.4 hunt checks built 10-24 (fight_sim p90 ≤ 60% HP, summoner and blinker rules; "don't quaff before closing in" put to the user); 2.1 item policy done (itemvalue.py from our tables, value refusals with a Navigator **debt**, Free-Action inference, pickup by value); 2.2 town kit next; 2.3/2.4 danger rules (will use `monsters.csv`) |
| 3 | the rulebook | **ours** | **release 1 + 2 done and synced; release 3 (drops + feelings value fix) + fight_sim.py synced 10-24** (sync.sh also copies fight_sim.py, build_monsters.py, data/monsters/monsters.csv → keep their paths stable; tell the Architect when they change) (`../memos/2026-10-24-rulebook-r3.md`); (`../memos/2026-10-24-rulebook.md`, `-rulebook-r2.md`; `data/rulebook/`, query `rule.py`; r2 synced 10-24, C8 rule fixed by the Architect); the Architect syncs it into the repo with `github/tools/rulebook/sync.sh` — **tell them whenever we rebuild** |
| 4 | harness / set-pieces | **ours: the list** | **harness built 10-23** (`github/tools/harness/`, results `runs/setpieces/results.md`): A1, A2, A2L, A6, A7, A8(o,w), A9 (summoned), C3 pass live; C8 unit-only. Proposed speed/AC-aware emergency threshold (`worst_3turns_acNN`, `to_architect/2026-10-24-emergency-threshold.md`); next A3, B1, C4, C5 List: `../memos/2026-10-24-setpieces.md` (41 cases + A7-A9 addenda) |
| 5 | missions again with scorecards | scorecard per mission; Opus vs Sonnet | **started**: m24 (Opus) reviewed (`../memos/2026-10-24-m24.md`); m25 (Opus, walked down, 10.9 XP/dmin) and m26 (Sonnet, 650 ft, 50.7 XP/min at 500-650 but low HP 14%) scored by the Architect; Pilot changed between them; target for next missions: > 58 XP/min at 500-650 ft, lowest HP >= 50% |

## Pending Advisor work (in order)

1. ~~Rulebook: drop expectations~~ **done** (r3: `drops.csv`, `drops_by_depth.csv`, `drop_object_by_level.csv`, `objgen.py`). Possible follow-ups:
   subtract already-found artifacts if the server log is kept; empirical drop counts need monster coordinates in the logs.
2. **Live checks of code-only rulebook claims**: proposed to the Architect as harness cases L1 (boulders: **confirmed live 10-23**), L2 (resting x10: FAILS in practice — unseen awake monsters count; constants.csv corrected 10-24), L3 (unaffected after HOLD: confirmed; BLIND half unseen) — `to_architect/2026-10-24-fleehp-live.md`; review the results. Originally: boulders do 0 damage; the low-HP time
   bubble is a constant 1/5; WoR counts down ~10× faster while resting out of sight; "You are unaffected!" pairing.
3. **Set-pieces:** the Architect stages and runs them (harness); my part: criteria, order, and reviewing `runs/setpieces/results.md` for each P1 case, in the agreed order A7, A8, A9 (m24 arrival replay), A1, A6, A2, C8, C3, then (A3, B1, C1,
   C4, C5, D3, F1). A7 also validates `fight_sim.py` (Hill giant p90 123 at Dive04's profile).
4. ~~veto_reason~~ **done** 10-24 (monsters.csv `veto_reason`/`veto_detail`; note `to_architect/2026-10-24-veto-reason.md`; awaiting re-sync). The Architect built the m24 arrival protocol, depth band in HANDBOOK, plan-news tagging.
4b. **Belief-state spec** (if the Architect wants it for step 2): fields, computation, expiry (see starting-over memo §3.4).
5. **Step 5:** run the scorecard on each new mission vs the m17–23 baseline; Opus vs Sonnet by depth band (m22–23 were Sonnet;
   `data/navigator/response.py` has the missions list; production `scorecard.py` reads `runs/missions.json` which records the model).
5a. **Estimator**: memo 10-25 + replay/calibration memo 10-25 (`2026-10-25-replay.md`); user: no freeze per decision; Architect adds
   the 4 rule fixes + 21x21 map windows in emergency records. **Shadow mode ON (10-25):** the Pilot imports
   `data/estimator/options_sim.py` LIVE (shadow.py -> choose(p, team, n=40)) — treat it as an interface: keep choose()'s signature,
   keep base_policy = pilot.py escape()/berserk_tick/fear_cure (POLICY_VERSION), edit via a copy + mv, and tell the Architect
   before changes. m35-m41 reviewed (19 records; disagreements were my zero staff price): now POLICY_VERSION 2026-10-25d, XP_PER_GOLD 1.0
   (THE USER'S DECISION — don't change), MIN_GAIN (approved by the user 10-28, scaled to 30 s of play) -> 17/19 agree. Hard-fight shadow live
   (trigger: hard_fight). options_sim now 25e (speed_start_tick mirrored, PRICE speed 400; XP_PER_GOLD rolling, set by the Pilot per snapshot). options_sim 26f: resists modelled (gear evaluator github/tools/pilot/geareval.py imports it too); scenarios.py for depth-native fights. options_sim now 28m (p["xp_per_gold"] per call; MIN_GAIN = max(50, 48 blocks x xp_rate_per_block) — user-approved 10-28; slays/brands/criticals optional; blind -> staff; optional food/gorging, food may be a FOOD_LEVEL range; per-member awake flag; optional xp_per_block time cost; band trigger in shadow mode, agree = actual action). geareval reviewed twice (rest in game time, bootstrap tail gate; resist trading = user decision).
   Speed value (speed-slope memo): drinking a carried one at the start pays (break-even 350-1600 g); buying pays on XP only below ~200-250 g at XP_PER_GOLD 1 (safety not counted). Script data/estimator/speed_value.py. Speed purchases: decisions.jsonl kind act, why "buy ... Potion of Speed", entry= total paid (3 at 383 by 10-26); BM prices in runs/pilot/dive04/stores.json (store 7). PRICE speed 400 ~ paid; revisit if the paid average moves. Review estimator records of new missions. (`to_architect/2026-10-25-shadow-review.md`); proposed running it at the start of hard fights.
5b. **m27** (Opus, kit forged to m26's start, Pilot after m26 fixes): first same-Pilot Opus vs Sonnet comparison; score it vs m26 when done.
   Arrival feelings now logged (`arrival_feeling` in decisions; `feeling:` in dump headers): later, measure P(pit/nest | special) on scummed levels.
5c. Next rulebook build: add constants.csv rows for Hero/Berserk (to_h +12/+24, AC -10, mhp +10/+30 rescaled, res_fear),
   cure amounts, no-flow movement, spell range 18 (from `studies/2026-10-25-estimator/scratch/E2/mechanics.csv`).
5d. When `looks` records exist (m48+): calibrate options_sim P_WAKE (sleeper wake rate near a fight; 5%/block guess) and
   re-check P_AWAKE against observed shares.
6. Housekeeping: the 09-29 shops memo assumed CHR 4 = Dive04's natural CHR; it is drained to 3 now (use `data/rulebook/shop_owners.csv`, CHR 3 columns, until restored).

## Architect schedule

- Session 8 = "The Architect's Vacation" (Haiku, helps the Navigator live, NO code changes; notes in ../VACATION-NOTES.md).
  Code requests wait for session 9. Avoid options_sim changes meanwhile (nobody to coordinate a Pilot restart); good time for
  data studies (P_WAKE from `looks`, band/hard-fight shadow records).

## Waiting on the user

- Nothing pending. The user decided (10-24): **auto_scum stays ON** (richer, more dangerous rerolled levels; my "off" declined).
  Consequence: depth_value.csv / rulebook level-generation numbers assume unscummed levels and understate OOD monsters per level. The user decided (10-24): missions run with `--hpwarn 5`; `flee_hp` stays 0.5 everywhere (my hunt-only 0.4 declined); the forge may be used.
- (Earlier: the low-HP time bubble: the user decided "after step 2" — then turn-based Pilot timers and an A/B of `--hpwarn 5` on set-pieces
  A1/A2; `to_advisor/2026-10-23-step22-town-kit.md`.)

## The rulebook (`data/rulebook/`, README there)

Generated by `build_all.sh` (jewellery → kinds → feelings (~5 min Monte Carlo) → monsters → shops); copied tables come from finished studies.
`kinds_by_level.csv` + `unknown_expect.csv` (unknown flavoured items by level), `jewellery.csv` (rings/amulets with plusses),
`feelings.csv` (pseudo-ID {good}/{excellent} per kind/level, P(irreplaceable ego)), `monsters.csv` (616 races: melee/turn by AC with recoil,
spells, breaths, tags, solo index), `abilities.csv` (messages proving abilities), `ego_flags.csv`, `constants.csv` (104 timing/odds),
`shop_owners.csv` (buy/pay % at any CHR), `shop_stock.csv`, `char_*.csv`, `structures.csv`, `vaults.csv`, `store_gear.csv`,
`danger_table_v1.csv` (old hand ratings). `rule.py monster|unknown|feeling|owner|const|room|fight`.

## Studies done (memos in `../memos/`; audit trails in `studies/<date>-<slug>/`)

| date | study | memo | data |
|---|---|---|---|
| 10-25 | estimator calibration on 21 replays (`studies/2026-10-25-replay/`) | `2026-10-25-replay.md` | `data/estimator/` |
| 10-25 | emergency option estimator (worth it? model, method, budget, validation; 47 episodes m17-m34) | `2026-10-25-estimator.md` | `data/estimator/` |
| 10-24 | structures (pits/nests/vaults from partial maps; m26 summon trap; auto_scum) | `2026-10-24-structures.md` | `data/structures/` |
| 09-26 | forum distillation (pre-fork) | `2026-09-26-forum-distillation.md` | `data/forum/` |
| 09-27 | danger table 0–1500 ft | `2026-09-27-danger-table.md` | `data/monsters/` |
| 09-28 | the Angband Borg | `2026-09-28-borg.md` | `data/borg/` |
| 09-28 | run post-mortem | `2026-09-28-run-postmortem.md` | `data/runs/` |
| 09-29 | message catalogue; shops; versions + forum rules; mission 9 replay | `2026-09-29-*.md`, `to_architect/2026-09-29-mission9-replay.md` | `data/messages/`, `data/shops/`, `data/versions/` |
| 10-03 | game-state survey | `2026-10-03-game-state.md` | study scratch |
| 10-07 | mission 13 audit + replay; identify & sell; warrior progression; running; mission 15 answers | `to_architect/2026-10-07-mission13-*.md`, `2026-10-07-*.md` | `data/runs/audit_stats.py`, `data/identify/`, `data/progression/` |
| 10-08 | missions 15–16 replay; Navigator decision quality; floor drops (answer only) | `to_architect/2026-10-08-missions15-16-replay.md`, `2026-10-08-navigator-decisions.md` | `data/navigator/`, `data/drops/` |
| 10-09 | "What I lacked" catch-up | `to_architect/2026-10-09-what-i-lacked.md` | |
| 10-17 | Navigator response time, Opus baseline m16–21 | (answer to the user) | `data/navigator/response.py`, `baseline_opus_m16-m21.txt` |
| 10-19 | starting over (sent 10-22) | `2026-10-19-starting-over.md` | |
| 10-23 | scorecard | `2026-10-23-scorecard.md` | `data/scorecard/` |
| 10-24 | rulebook r3: drops, value fix, town-kit answers | `2026-10-24-rulebook-r3.md` | `data/rulebook/` (D1, D2) |
| 10-24 | m24 (step 5 begins): recall arrival protocol, depth band 500-650, plan-news metrics | `2026-10-24-m24.md` | `data/scorecard/xp_by_depth.py`, `data/rulebook/depth_value.py` |
| 10-24 | hunt strictness (step 2.4): simulated p90 + summoner rule; set-pieces A7, A8 | `to_architect/2026-10-24-hunt-strictness.md` | `data/rulebook/fight_sim.py`, `fight_dive04.csv` |
| 10-24 | set-pieces; rulebook r1 + r2 | `2026-10-24-setpieces.md`, `2026-10-24-rulebook.md`, `2026-10-24-rulebook-r2.md` | `data/rulebook/` |

The user struck one lead (2026-10-07): the live fetch of Bug Reports / Technical Support. Don't propose it again.

## Facts a new chat tends to re-derive (verified; cite the memos)

- Server = upstream develop c97e873 (plays as 1.5.3). `monster.txt` unchanged since 2008.
- **Dive04** (10-22): Half-Orc Warrior clvl 22, 254 HP (265 after Restore CON 10-23), **CHR 3 (natural 4, Rot-jelly drain)** (shop % from `shop_owners.csv`), **no Free Action** (it had it m18–m23 from
  unidentified Boots of Free Action, force-sold for 3 gold in m23). Navigator: Opus to m21, Sonnet m22–23.
- Selling identifies (price set before the item is known): an UNIDENTIFIED item sells at its kind's base cost (`store.c:192`, object_value_base;
  unaware flavours 20-90; felt-cursed 0) — 55-72% of a normal drop's true value, 17-29% of a DROP_GOOD one; wearing never identifies; flavours are per server savefile.
- Blows = blows_table[adj_str_blow·5/max(30,wt)][adj_dex_blow] (matched 3,957 audit records). MONSTER_RECOIL is on: a monster melees once
  per two of its turns.
- Running = ×5 game time and resting ×10 ONLY with no awake monster in LOS, seen or not (`monsters_in_los`, xtra2.c:5116); after a fight there is
  usually one in the dark: L2 measured recall 15-16 s resting = standing. Current HP scales with max HP (xtra1.c:2024). Low-HP bubble:
  constant 1/5 below hitpoint_warn×10% (missions now run --hpwarn 5: HP ≤ 50%).
- Recall arrival: random floor square, pit/nest monsters awake; "something special about this level" = pit/nest/vault (or artifact) at <= 850 ft;
  stairs arrivals land on the staircase back; a 2nd WoR read cancels a pending one; no Deep Descent in 1.5. XP/min: 300-450 ft 8.5, 500-650 ft 58.
- **auto_scum is ON** (client `lib/user/options.prf`): at 500 ft+ fresh levels are rerolled until "special" or rating > 20 (generate.c:4275);
  0 of 38 informative arrivals at 500-700 ft were below "luck is turning", 14 special. At <= 850 ft a non-special, non-suppressed feeling
  proves no pit/nest/vault. dungeon_align is on: rooms centred at X in {16,49,82,115,148,181}, Y = 11k+5. Normal tunnels 2 wide; lit 11x25
  room never a pit/nest; at 500-1000 ft pits = orc, nests = jelly. m26's Nar group = summon trap (3-5 awake, Depth+5, uniques).
- Estimator calibration (10-25): monster hit x1.10 vs model; ~2 attackers at once (max 3); non-adjacent monsters close at
  ~0.4 of straight-walk (asleep/unnoticed); 1 block = 0.625 s wall (TICK_S), ~3.3 s in the bubble.
- Cures heal flat: CLW 15, CSW 20-24, CCW 25-29 (use-obj.c:483-510) — status cures, not heals, at 300 HP. No monster flow
  (MONSTER_FLOW compiled out): monsters walk straight at us; Phase helps only through a wall. Reading blocked by confusion/blind/dark.
  A 2nd WoR read cancels (the Pilot once resent one, m26 03:22). Commands take 4-19 s wall in the bubble. Time freeze live (10-25).
- Server pathfind = running (×5 time with nothing in LOS): explore could be 3-5× faster in wall time (set-piece D6, 10-23); queued after the time bubble.
- flee_hp: keep 0.5 (11 drops below 50% in m17-m24 fell on to a median 44%, 5 below 40%); 0.4 only inside a vetted solo hunt (proposed 10-24).
- A repeat kill of a unique gives no XP and no drop (xtra2.c 'cheeze'); Dive04 has killed Brodda, Bullroarer, Orfax, Wormtongue, Farmer Maggot.
- Hunt checks: `fight_sim.py` p90 (FIGHT-rated: none > 60% HP at Dive04's profile); summoners and blinkers are outside the duel model
  (m19 Ranger: duel p90 44, real 153 from summons + ranged phase). The `threats` column of monsters.csv is stale 09-27 text (boulder ~30).
- Boulders do 0 damage to players (live-confirmed, set-piece L1); BO_POIS and BR_MANA are empty; breaths use current HP.
- "You are unaffected!" = Free Action only after HOLD/SLOW/paralysis; after BLIND = rBlind; after TELE_LEVEL = rNexus.
  "You resist the effects!" = a save, so the player LACKS the resist. The `flags` query shows identified flags only.
- Rooms: inner-room centres on an 11-square grid, secret door at a side midpoint; pits/nests unlit; vault outlines are granite.
  Search 14% per adjacent square per `s`; standing still never searches. Chest traps fire on open unless disarmed.
- Floor drops: one object per square; a monster's drop needs an empty square within 2 or it's never created.
- Navigator reports understated the lowest HP in 3 of 7 missions: use the scorecard, not reports.
- Logging (since 10-09/10-23): `epoch` on every event, `pilot_start`, `nav_cmd` (+ `report_age`), `sale`, `itemlist`/`left_behind`, `escape`,
  `audit_check` state, `mission_start`/`mission_end` (with the Navigator model), monster health `track`. Still missing for replays: the
  Pilot's map memory and pack at second T.

## Tooling notes

- **Every rulebook release memo needs a "Schema changes" section** (renamed/added/redefined columns, or "None"): the Pilot's
  loaders fall back silently to old files/defaults. Tables the Pilot reads: monsters.csv (+veto_reason), monsters_raw.csv + fight_sim.py,
  kinds_by_level, jewellery, feelings, abilities, shop_owners, drops, constants, rule.py (`to_advisor/2026-10-23-step3.md`).

- **Inbox watcher:** `.claude/hooks/inbox.sh watch ../memos/to_advisor` (background) exits when a memo arrives; read, `mark-read`, restart.
  It can hit the background time limit: if so, check `inbox.sh unread` by hand. Send memos by writing `../memos/to_architect/.tmp-SLUG.md`
  then `mv` to `YYYY-MM-DD-SLUG.md`.
- `module load python3/3.12.4`. Clerks write only their dispatch and `studies/<study>/scratch/<id>/` (one subfolder each).
- Every memo and dispatch ends with "What I lacked" (the Architect's complaints channel, `runs/complaints.md`).
- Missions: `runs/missions.json` (label, start, end, Navigator model); reports in `runs/pilot/dive04/reports/`; level dumps in `levels/`.
