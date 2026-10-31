# Changelog

What changed in the MAngband player (the tool client, the Pilot, and the tools around them), version by version,
newest first.

**Version numbers** are `major.minor.patch`. **Major** is the era: 0 = the tool client and the shop catalog, 1 = the
Pilot era, 2 = the restructure (from the first commit after the git tag `pre-restructure`). **Minor** goes up when a
release can make play differ (Pilot behaviour, the town kit, commands the Navigator uses, client/server changes that
affect play, item and gear policy); scorecards are comparable within one minor. **Patch** goes up when nothing in play
can change (docs, notes, observers and the scorecard, the harness, snapshots, memos).

A version is a group of consecutive commits: one working session, cut at the start of each mission whose code differed
from the previous mission's. **Versions before 2026-10-29 were assigned retroactively.** Git tags `vX.Y.Z` mark the
last commit of each version.

How to read an entry: `first..last` are short hashes, both included. A mission belongs to the version of the latest
commit before it started; "approx." means fixes were loaded (restart or hot-swap) while it ran. "History" means
`history/handoffs-s1-s9.md` (its section headings are quoted); "Part A/B" means `next_steps.md` "HANDOFF TO ARCHITECT
11". Mission reports (m17 on) are `runs/pilot/dive04/reports/<date>-mission<N>.md`; the Navigator journals are
`runs/pilot/dive03/navigator.md` (m1-m7) and `runs/pilot/dive04/navigator.md` (m8 on). Sessions are the Architect
chats; "session 1" covers the unnamed chats before the evening of 2026-09-27.

---

# 2.x: the restructure

From 2026-10-22: after mission 23 the user stopped patching mission by mission. Instruments came first, then plans
(`plan town`, `plan trip`), the Advisor's rulebook, the set-piece harness, scored missions, and gear tools.

## 2.42.0 -- 2026-10-31 (session 10, continued)
No missions yet. Details: `docs/pilot-items.md` (itemvalue, `pack_value`).
- **Mushrooms by expected value** (the user): an unknown mushroom is worth the average value of the mushroom kinds not
  yet identified (~80 gold with none known); a known one its kind's value (a Mushroom of Restoring 1000). Both were
  valued 0 before, and the Pilot kept every non-junk mushroom as priceless food; now they compete for pack room
  like any item.
- Doc: `destroy_count`'s "last other food" rule explained with an example.

## 2.41.0 -- 2026-10-31 (session 10, continued)
No missions yet. Details: `docs/pilot-items.md` (`pack_value`, make room), `next_steps.md` Part B.
- **Rations and oil by need** (the user's own play): in the dungeon, food and flasks that last until the expected
  recall plus 5 dungeon minutes (40 minutes when no trip end is known) are needed and worth the dungeon time they buy
  (gold + XP per minute from the Pilot's rates); the rest is spare, worth its sale price, and goes for worthy loot.
  Rations were never destroyed before.
- Pack full: the Pilot eats (if it won't Gorge) and fills the lantern from any stack before destroying anything.
- The town kit is unchanged (eats to Fed, the user).

## 2.40.0 -- 2026-10-29 (session 10, continued)
No missions yet. Details: `docs/refactor-candidates.md` "A2".
- An empty `autodestroy` order no longer stops the destroying of `junk`-order kinds and harmful devices (A16).
- Make-room values: junk food, flasks and lights (e.g. a junk mushroom) are worth 0, not priceless (A17).
- A worn torch's turns count as light left; only a light that shows no turns is permanent (A19).
- The emergency loop's alert says "already fleeing to the stairs" instead of "no stairs known" when it is (A21).
- `order`: every KEY=VALUE is checked before any is applied; a bad one changes nothing and gets a usage error (A22,
  F5).

## 2.39.0 -- 2026-10-29 (session 10, continued)
No missions yet. Details: `docs/refactor-candidates.md` "A2" (bugs found by the doc verification).
- Auto-destroy never destroys a kept item, in its pseudo-ID pass too (A15).
- `plan trip ... until`: `wor<=1` is refused (it held as soon as the trip recalled down); `wor<1` is allowed (A18).
- The hunger reflex no longer skips pickup, auto-destroy, engage and rest while it waits for a meal to show (A20).
- A failed override hunt never counts as slain, so its fight debt is charged (A23).
- Scorecard: `commands_per_min` counts commands only, not wait reports (A24, the Advisor's definition); all real
  missions rescored.

## 2.38.0 -- 2026-10-29 (session 10, continued)
No missions yet. Details: `next_steps.md` Part B, `docs/refactor-candidates.md` (A2, B, review follow-ups).
- The emergency loop's count: every `emergency` notice states whether it reports an escape action (a unit case
  checks it), and one method counts them (A4 follow-up; same behaviour).
- Gear evaluation's "met" fights: the last 3 days of the log, doubled until 20 fights (was the last 24 MB; A7
  follow-up). Gear verdicts can differ: hence a minor version.
- Set-pieces keep the newest 5 snapshots (C12 follow-up).
- Navigator-facing docs fixed (B1-B3, B5-B8): HANDBOOK (`goal shop N sell`, the stash in the house, eats to Fed, all
  eight trip events), FIELD-NOTES, BRIEF-TEMPLATE (gear and stats are fill-in fields), pilotctl's help, navigator.md.
- Every `docs/` file verified against the code (ten agents, ~100 doc fixes); suspected code bugs listed as A15-A25.
  `docs/survey-notes/` to `history/`; the per-version checklist in docs/process.md; live-deploy-todo.md: pin the
  Advisor's simulator.

## 2.37.1 -- 2026-10-29 (session 10, continued)
No missions yet. Details: `docs/refactor-candidates.md` (B4, C3, C4, C14), `next_steps.md` TODO.
- HANDBOOK-reference fixed (B4): `goal leave` / `goal fetch` instead of the refused `goal goto` / `stairs`; the four
  missing orders (`autowear`, `enchant_max`, `band_frac`, `nopickup`); the real emergency trigger and escape order.
- The human-play study tools moved to `tools/observe/study/` (C3; the user will record play again).
- The shop-tour tool is kept for the live catalog (C4); `live-deploy-todo.md` started (the live deployment checklist).
- Shrinking HANDBOOK-reference (C14) deferred to an A/B test (missions before vs after).

## 2.37.0 -- 2026-10-29 (session 10, continued)
No missions yet. Details: `docs/refactor-candidates.md` (items marked "done (session 10)"), Part B.
- **Versions start** (the user's decision): `github/VERSION`, this changelog (2.36.0 and older assigned retroactively),
  git tags `vX.Y.Z`; the Pilot shows `Pilot vX.Y.Z` in `status full` and its `started` notice, and `mission start`
  records `version` in `runs/missions.json` and the `mission_start` record.
- Play fixes approved by the user: the emergency loop counts escape actions only, not "fighting on"/"attacking X
  first" notices (A4); `order pickup=none` makes no loot walks (A5); gear evaluation's "met" fights come from the
  last ~day of the log (A7); Rings of Damage/Accuracy count as to-dam/to-hit (A13); shadow snapshots carry slays,
  brands and weapon weight (A14). pilotctl prints each note once (A12).
- Cleanup (group C): `replay_group.py`, `danger_table.csv`, `latency.py` to `tools/attic/`; the danger-table and
  kinds.csv fallbacks removed (the rulebook files must exist); dead code in `do_request`, `choke_tick`, watch.py;
  set-pieces delete their snapshots after a good restore (156 old ones, 55 MB, deleted); `testserver/` crash files and
  the pre-freeze binary deleted; old handoffs and retired notes moved to `history/`. Unit cases 117 -> 120.

## 2.36.0 -- 2026-10-29 (session 10)
Commits `dd2200d..d745962`. No missions. Details: Part B; `docs/refactor-candidates.md`.
- Bug fixes from the refactor list, approved by the user: the escape-to-stairs state is tied to its walk and level
  (A1); flavour learning matches the item type (A2); shadow snapshots pass total to-hit/to-dam (A3); one auto-swap loss
  rule for gear compare and optimize (A6); the damage mix uses the mission's depth band (A8).
- Observer fixes: the scorecard rescores only what is asked (A9); `watch_mission` resumes from saved offsets (A10);
  `wrap.sh` and `notes.py` filter to the mission; `review wear` says what happens (A11).
- Handoff 11 Part B; the Advisor's reply on slays/brands in shadow snapshots (A14, awaiting the user).

## 2.35.1 -- 2026-10-29 (session 10)
Commits `acb6263`. No missions. Details: Part B; `docs/README.md`.
- The Documentation: `docs/README.md` (the big picture), `docs/CONDENSED.md`, ten component files.
- `docs/refactor-candidates.md`: what to refactor, remove or split, in one list.

## 2.35.0 -- 2026-10-28 (session 9)
Commits `86f74eb..d53ba3b`. No missions. Details: Part A; reports m58-m60.
- The confusion clock resets between confusions (m60 read "confused for 1773 s").
- Flee after a phase: the replan may use unexplored squares, a jump off the path drops the old blocked squares, and
  Flee replans twice before "stuck" (m59 read Word of Recall with stairs 21 squares away).
- Reports for m58-m60 and the model comparison; FIELD-NOTES for 700-800 ft; the handoffs for sessions 10 and 11.
- Shadow records carry `xp_per_gold`.

## 2.34.0 -- 2026-10-28 (session 9)
Commits `7de6e6b`. Missions: m59 (Sonnet medium), m60 (Haiku medium), 30 min each. Details: Part A; reports m59, m60.
- `plan town` announces enchanting and recharging; `order enchant_max` caps enchanting.
- Worn items leave the review queue; a react rule isn't added twice.

## 2.33.0 -- 2026-10-28 (session 9)
Commits `87d31a0..ed47b6d`. Missions: m58 (Opus medium). Details: Part A; reports m56-m58.
- Item commands wait for the pack after a stack empties (m57: Berserk by a stale letter drank a CLW). In-place actions
  aren't "stuck". Empty staffs and wands are sold; the keep list matches plural stacks; no pickups mid-flee under 500
  gold. New trip condition `dmin` (minutes in the dungeon).
- `ask quiet TEXT`: the Navigator waits quietly until the Architect answers. HANDBOOK: "when to stop and think".
- Supplies counted in dungeon minutes (food with reserves, light with flasks) in status and `plan town`, with alerts
  under 15 and 5 minutes; quiet waits are capped at a quarter of it.
- `plan town` recharges empty useful staffs and wands (risk 15% or less) instead of selling them, enchants worn armour
  while the next point is at least 50% likely, and waits up to 4 x 35 s for a restock of a critical item.

## 2.32.0 -- 2026-10-28 (session 9)
Commits `e38c6b6..f0c4a98`. Missions: m57 (Sonnet medium, approx.). Details: Part A; reports m56, m57.
- `plan town` carries on while its house step is on the wilderness tile (the m56 Navigator's request).
- House trips stop walking on a level change (m56 crossed the edge and opened the door from 10 squares away).
- Recall's act says one scroll was read.

## 2.31.0 -- 2026-10-28 (session 9)
Commits `30a9f87..6194f74`. Missions: m56 (Opus medium). Details: Part A; `design_gear.md`.
- EHP (effective HP over the damage mix actually taken) in `gearcmp`, `loadout` and the optimizer. `gearcmp` rules out
  options with more than 5% less EHP than the worn gear.
- Confusion is checked every tick; the cured moment is used to teleport away from 3+ adjacent monsters. React hunts
  resume the goal they interrupted.
- `order autowear=off`. The M5 set-piece (a confusing breeder swarm), built but not reliably stageable.
- Handoff 10 and the user's four new TODOs.

## 2.30.0 -- 2026-10-27 (session 9)
Commits `c50b1bf..47d820c`. No missions (its first commits were made while m55 ran). Details: Part A; `operations.md`
"Houses"; `design_gear.md`.
- The loadout optimizer: `pilotctl loadout [shops]` tries one or two slot changes that keep every ability and resist.
  Slays, brands and weapon weight enter the fight simulation.
- The gold bank: the Pilot deposits and withdraws gold in a house it owns; `plan town` withdraws first and deposits last
  (float 300). The town house was sold for a cheaper wilderness house north of town.
- The stash (Restore potions, Stone to Mud wands) moves into the wilderness house. The tavern stash now drops inside the
  room: wands dropped at the entrance had been carried off by townspeople.
- m55 fixes: an unseen monster's missile counts as a hit; Recall while blind or confused quaffs a cure first; a
  confusion lock is cured with CSW/CCW.

## 2.29.0 -- 2026-10-27 (session 9)
Commits `d939b59..98f95d9`. Missions: m55 (Haiku low, approx.). Details: Part A; `history/VACATION-NOTES.md` "Session 9
triage"; report m55.
- Fixes from the vacation notes: thefts are news; eating to make room never gorges; the dive loots beside its path.
- Bracketed egos are valued (Holy Avenger, Defender...: m53's Sabre ~2750 became ~22750 gold).
- At the weight limit, shed the cheapest heavy item for loot worth 1.5 times it.
- `goal quiet [SECS]`: walk to a quiet spot and rest until a monster moves or hits.
- Escape status: ESCAPE LANDING, then "escaped" or FAILED. A trap door below `max_depth` is news.

## 2.28.1 -- 2026-10-27 (session 8)
Commits `c16d10c`. No missions. Details: history "HANDOFF TO ARCHITECT 9"; `history/VACATION-NOTES.md`.
- Snapshot of the vacation session (a Haiku Architect helping the Navigator, no code changes): reports m49-m54,
  FIELD-NOTES, VACATION-NOTES.

## 2.28.0 -- 2026-10-26 (session 7)
Commits `25caf39..56bfd20`. Missions: m49-m54 (Haiku low, run in session 8). Details: history "ARCHITECT HANDOFF
2026-10-26, session 7" and "HANDOFF TO ARCHITECT 8"; reports m48-m54.
- Pinned by breeders while leaving a level: one teleport per level.
- Blind escapes: use a staff when a scroll can't be read; see refused reads at once; eat to Fed (m48's close call, 24%).
- Shadow records: the asleep flag per monster, the band-leave decision under a trip plan, a food estimate.
- Set-up for sessions 8 and 9: the unlimited `ask` switch, the brief template, the mission monitor.

## 2.27.0 -- 2026-10-26 (session 7)
Commits `042f5e2..b1e401c`. Missions: m48 (Haiku low). Details: history session 7; reports m47, m48.
- `react`: standing orders the Pilot carries out at once (leave NAME, hunt NAME on sight, kill thieves, teleport when
  afraid).
- The review queue: notable identified gear waits for the Navigator (`review sell|keep|wear`); sold after 2 town visits.
- Destroy and drop allowed in the dungeon (value refusal and debt); `order nopickup=`, `order band_frac`; a "this trip"
  XP rate.
- The client's `look N` gives a per-monster asleep flag. Shadow agreement is judged by the action taken.
- The gear evaluator scores in XP per real minute.

## 2.26.0 -- 2026-10-26 (session 7)
Commits `a7cbbbc..c11a16d`. Missions: m47 (Haiku low, approx.). Details: history session 7; reports m46, m47.
- The drain notice names a Restore in the stash (m46 planned to buy one).
- Never destroy the last food; leave heavy loot that would slow us; kit items know their shop in `plan town`.

## 2.25.0 -- 2026-10-26 (session 7)
Commits `5aba4e6..6a59b0e`. Missions: m46 (Haiku low; `a7cbbbc` hot-swapped in at 18:09). Details: history session 7;
`design_gear.md`; report m46.
- Leaving levels: the stairs back to a fled level are held; a finished level not left within 5 minutes means Word of
  Recall home. Plan, level and mission state survive restarts and hot-swaps.
- The gear evaluator (`gearcmp`): compares gear by rules, a model of the server's bonus calculation and simulated
  fights; reviewed twice by the Advisor. Trading away resists stays off (the user).
- The fled-stairs hold applies only on `--live`; the Speed potion cap is 600 gold.

## 2.24.0 -- 2026-10-26 (session 6)
Commits `d2cbd5e..07cb762`. No missions. Details: history "ARCHITECT HANDOFF 2026-10-26, end of session 6".
- The tavern stash: Restore potions and Stone to Mud wands stay in the tavern during missions; one lantern carried.
- `observe/wrap.sh`, the per-mission wrap-up.

## 2.23.1 -- 2026-10-26 (session 6)
Commits `9379c19`. No missions. Details: history session 6.
- FIELD-NOTES from m43-m45 (the 750 ft trial, a stuck dive, Rings of Strength).

## 2.23.0 -- 2026-10-26 (session 6)
Commits `075d3ad..37d5601`. Missions: m45 (Haiku low; `37d5601` hot-swapped in at 00:33). Details: history
"ARCHITECT HANDOFF 2026-10-25, session 6"; reports m44, m45.
- `price` uses the last-seen shop price only for the same item type.
- Trip condition `time>HH:MM` means the next HH:MM after the plan started (m44's held at once across midnight).
- Floor junk destroyed once per sighting; blindness cures capped at 2 in 30 s (Light hounds cost 16 CLW).

## 2.22.0 -- 2026-10-25 (session 6)
Commits `a654037..da5d277`. Missions: m44 (Haiku low). Details: history session 6; reports m43, m44.
- Who acted: every act and goal is tagged by Pilot, plan, Navigator or Architect; the viewer shows the tags.
- Floor junk destroyed where it lies, out of combat.
- m43 fixes: unfelt gear valued by the server's odds; staffs aren't kit; Restore at a quiet moment; engage nearby
  monsters; `ask`, `answer` and `price` commands.

## 2.21.0 -- 2026-10-25 (session 6)
Commits `797053b..3e2feaf`. Missions: m43 (Haiku low, the first Haiku trial; `a654037` hot-swapped in at 23:29).
Details: history session 6; report m43.
- Speed: Speed potions in kits B and C (Black Market, cap 450) and quaffed at the start of hard fights; a rolling
  XP-per-gold rate. Shadow mode at the start of hard fights.
- Navigator tools `why` and `prep`; `FIELD-NOTES.md`, lessons for Navigators.
- A `max_depth` 750 trial (the user). Gear review ideas carry the exact buy line.

## 2.20.0 -- 2026-10-25 (session 6)
Commits `8945cb6`. Missions: m42 (Sonnet high). Details: history session 6; `2026-10-25-shadow-series-m35-m42.md`.
- Afraid with 2+ monsters adjacent: teleport, not phase. Heroism (the fear cure) in kits B and C.

## 2.19.0 -- 2026-10-25 (session 6)
Commits `7bb2285`. Missions: m41 (Opus medium). Details: history session 6; reports m40, m41.
- Recall to one level above the band's top; a breeder swarm (8+) means leave the level; status shows an unlit light.

## 2.18.0 -- 2026-10-25 (session 6)
Commits `03d09a5..1ba35ef`. Missions: m40 (Opus high). Details: history session 6; reports m38-m40.
- The dive maps stairs when the kind it wants isn't known (m38: 10 minutes on a `>` looking for a `<`).
- The fullest lantern is worn; a low worn lantern swaps for a fuller spare.

## 2.17.0 -- 2026-10-25 (session 6)
Commits `b7abd7a..c0908b4`. Missions: m39 (Sonnet medium). Details: history session 6; reports m37-m39.
- A unique's drop pushes out only items under 50 gold (m37 destroyed a Tulwar and an Amulet for cheap drops).
- Flee at `max_depth` with only `>` known: teleport on the level.

## 2.16.0 -- 2026-10-25 (session 6)
Commits `0bebdab`. Missions: m38 (Sonnet high). Details: history session 6; report m37.
- Items beside a disenchanter are left; `plan town` wears what it bought; ability armour kept; disenchant news.

## 2.15.0 -- 2026-10-25 (session 6)
Commits `2b3be4f..33185de`. Missions: m37 (Opus medium). Details: history session 6; report m36.
- Kit consumables found in the dungeon are worth their replacement cost; better jewellery replaces a worn piece in
  town (m36 had sold a Ring of Protection [+12] with a ring slot empty).

## 2.14.0 -- 2026-10-25 (session 6)
Commits `0e68053..a61821f`. Missions: m36 (Opus high). Details: history "ARCHITECT HANDOFF 2026-10-25, session 6";
report m35.
- `gear`: a read-only gear review, the first part of the user's between-mission gear step.
- `plan town` reads scrolls in hand before replying; the forecast names the shop; Rates show gold found vs net and XP a
  minute on this level.
- HANDBOOK: time margins, the observed recall delay (~15 s), TIME FROZEN.

## 2.13.0 -- 2026-10-25 (session 5)
Commits `11e6e61..4bcd70a`. Missions: m35 (Sonnet medium, first of the shadow series; run in session 6). Details:
history "ARCHITECT HANDOFF 2026-10-25 (session 5)"; `2026-10-25-matrix-m31-m34.md`.
- Bands judged by the expected cost of fighting them one at a time; weak drainers are news; quiet levels are left;
  disenchanters fought only when in the way; a flee with no known path reads Magic Mapping.
- Hot swap tested in the dungeon; a pending recall survives a Pilot restart.
- The Advisor's estimator rules: no resent recall or teleport, one escape in flight, kill a quick caster, teleport
  rather than phase in a crowd, no HP cure with 2+ adjacent.
- Shadow mode: the Advisor's estimator runs beside every emergency decision and logs what it would have done.
- Armour upgrades never lose an ability or resist.

## 2.12.0 -- 2026-10-25 (session 5)
Commits `afbad20..6f21b79`. Missions: m34 (Sonnet high, baseline matrix 4/4). Details: history session 5; report m34.
- `hotswap.sh`: freeze time, swap the Pilot, thaw (not yet tested).
- Never wield a weapon that loses an ability the wielded one gives; artifacts are never swapped away.

## 2.11.0 -- 2026-10-25 (session 5)
Commits `55dfce5..aa2052f`. Missions: m33 (Opus medium, baseline matrix 3/4). Details: history session 5; report m33.
- Fear cures in order: Heroism, then Boldness, then Berserk.
- Walk instead of running from a square two runs started from (the cave-run loop).
- The test server freezes game time while `testserver/FREEZE` exists; the Pilot holds commands meanwhile.

## 2.10.0 -- 2026-10-25 (session 5)
Commits `115228d..5e3cdd5`. Missions: m31 (Sonnet medium), m32 (Opus high): baseline matrix 1-2. Details: history
session 5; reports m30-m32.
- Provisions: one food source, no oil carried; `plan town` eats to Full and fills the lantern.
- The m30 stall fixed; a goal stuck twice ends; leave the level after a stat drain by an unseen monster.
- `plan town` makes pack room before buying; `plan resume`; item commands reply DONE with what was used.
- Emergencies quaff Speed first; Berserk in hard fights; Boldness is sold.

## 2.9.0 -- 2026-10-25 (session 5)
Commits `603813f..4054c1a`. Missions: m30 (Sonnet high). Details: history "ARCHITECT HANDOFF 2026-10-24" (session 5's
details) and session 5; report m30.
- Take stairs beside a harmless stationary monster (the mold fix).
- The Navigator's tokens recorded and priced per mission (`tokens.py`; scorecard per dungeon hour and per 1000 XP).
- Loot passed up while monsters were in view is fetched later; devices and jewellery within 30 squares.

## 2.8.0 -- 2026-10-24 (session 4)
Commits `37cbfac..b3f5618`. Missions: m29 (Opus high, run in session 5). Details: history "ARCHITECT HANDOFF
2026-10-24"; reports m28, m29.
- Identified junk is destroyed automatically (Haste/Clone/Heal Monster devices).
- The end-of-session-4 handoff.

## 2.7.0 -- 2026-10-24 (session 4)
Commits `3d0b375..58bfee7`. Missions: m28 (Sonnet medium). Details: history 2026-10-24; reports m27, m28.
- `buy NAME:N` means "have N"; `plan town` saves gold for a Word of Recall and townfarms by day when short of one;
  unknown devices sold when broke.
- No test-server crutches: a stair-finding Rod of Enlightenment zap was added and reverted (the user sold the rod);
  `pilot.py --live`; on the test server, mapping and detection devices are sold.

## 2.6.0 -- 2026-10-24 (session 4)
Commits `0846cbf..b5f2ee4`. Missions: m27 (Opus high). Details: history 2026-10-24; reports m26, m27.
- Flee and leave: far stairs with a dangerous monster within 2 squares turn at once into Recall plus Phase Door.
- A band with no stairs known: locate stairs or walk out of sight before reading Recall.
- Satisfy Hunger only when Weak, the kit buys rations; an upgrade pass after town Identify; slowness scales group
  danger; a Speed potion when slowed.
- Stationary monsters remembered on the level (drain zones); a summon trap means Phase Door at once.

## 2.5.0 -- 2026-10-24 (session 4)
Commits `d0e4e53..e4cfc4e`. Missions: m26 (Sonnet medium). Details: history 2026-10-24; report m25.
- Explore runs with a radius; no stair-scumming on a level the server keeps; no going straight back to a fled level.
- Two crash fixes; stacking pickups need no free slot; spare lights and surplus food can make room; multi-word item
  names; identified plain unique drops are sold.

## 2.4.0 -- 2026-10-24 (session 4)
Commits `e7fd425..70155ef`. Missions: m25 (Opus high, the first scored mission; approx.). Details: history 2026-10-24;
report m25.
- The game clock is measured from the worn light's fuel; the server's time-factor rule is the model.
- Missions run with `--hpwarn 5` by default (time slows at low HP).
- Harness: forged items, set-pieces L2 and L3 (Free Action against HOLD confirmed live).

## 2.3.0 -- 2026-10-23 (session 4)
Commits `8f640ab..c09773f`. Set-pieces only, no numbered missions. Details: history 2026-10-24 ("step 4", "batch 5");
`github/tools/harness/README`.
- Step 4, the set-piece harness: `dm.py` drives a DM character to summon and place monsters; `charsave.sh` snapshots;
  `setpiece.py` and `unit.py`.
- Credentials and savefiles removed from the public snapshot.
- Fixes found by set-pieces: walk away from a distant summoner; the worst melee in 3 turns at our AC drives the
  emergency rule and hunt checks; repeat-kill uniques refused; unknown jewellery not worn until identified.
- The time bubble: a game clock for every Pilot timer; `--hpwarn N`.
- The mover uses server pathfind for long legs with nothing in view (1.4 to 3.2 tiles/s); unseen attackers above
  80% HP are news only.

## 2.2.0 -- 2026-10-23 (session 4)
Commits `c77e80d..85ea684`. No missions. Details: history 2026-10-24; report m24.
- The viewer trimmed (the user); equipment and pack on F2/F3.
- m24 fixes: bands judged by strength, dark inner rooms avoided, `plan trip via=stairs|recall`; the Advisor's arrival
  protocol (find the stairs first).
- Step 3: the Pilot runs on the rulebook (monster ratings, junk kinds, jewellery expectations, per-owner shop pay);
  `monster NAME` shows the hunt verdict; `pilotctl rule`.

## 2.1.0 -- 2026-10-23 (session 4)
Commits `c48c6fa..cfe84ab`. Missions: m24 (Opus high, the first mission on plans). Details: history 2026-10-24;
`history/restructure-step2.md`; report m24.
- Step 2.2, `plan town`: the town visit by policy (sell, identify what pays, buy by tier: Recall, the supply gate's
  minimums, Restore, kit A/B/C, the Navigator's list).
- Step 2.3, `plan trip`: the Navigator states a trip (depth band, when to come home) and the Pilot runs it.
- Step 2.4, order checks: hunts vetted by the rulebook and the Advisor's duel simulator; overridden hunts go into a
  fight debt; `goal fetch`, `goal leave`.
- Step 2.5: the belief state in the report. Step 2.6: a ~110-line Navigator HANDBOOK; `goto`, `stairs` and `raw`
  refused to the Navigator.

## 2.0.0 -- 2026-10-23 (session 3)
Commits `afbbdc7..af5ddb4`. No missions. Details: history 2026-10-24; `restructure.md`.
- Instruments: the per-mission scorecard (`scorecard.py`, `runs/missions.json`) to the Advisor's definitions; numbered
  Navigator reports.
- Step 2.1: item values from the server source (`itemvalue.py`); the Navigator can override a value refusal with `!`,
  which goes into a hidden debt; a keep list; pickups by value.
- The Advisor's rulebook synced into `tools/rulebook` (unknown flavours, pseudo-ID feelings); Free Action inferred
  from game messages.

---

# 1.x: the Pilot era

From 2026-09-25: a Python Pilot plays second to second and a Navigator agent steers it through `pilotctl`. Each
mission's report drove the next fixes. Characters: Dive03 (m1-m7, died for good in m7), then Dive04 (m8 on).

## 1.26.0 -- 2026-10-22 (session 3)
Commits `b62a02b..767bf60` (tag `pre-restructure`). Missions: m23 (Sonnet medium; the user ended it). Details: history
"ARCHITECT HANDOFF 2026-10-08" and 2026-10-24; reports m22, m23.
- A compact Navigator report (0.4-1.4 KB instead of ~5 KB; a 19x19 map; gear changes only).
- m22 fixes: a band event, recall after futile phasing, bulky pickups need free slots, paths around traps.

## 1.25.0 -- 2026-10-17 (session 3)
Commits `bb56313..9e7e221`. Missions: m22 (Sonnet medium, the first Sonnet Navigator). Details: history 2026-10-08;
reports m21, m22.
- Test server and client: no store purchase or sale outside a store (m21's server crash); the client tracks silent
  store exits.
- m21 fixes: a thief event and thieves hit first, `unique_slain`, brand damage in the Weapons line.
- `latency.py`: Navigator response times per mission.

## 1.24.0 -- 2026-10-17 (session 3)
Commits `2d0a2f2`. Missions: m21 (Opus high; approx.: the store fixes went in after the server crash at 00:48).
Details: history 2026-10-08; reports m20, m21.
- m20 fixes: weak visible casters aren't unseen attackers; door bursts are news; a per-spot room search report; shop
  buys the remainder.

## 1.23.0 -- 2026-10-16 (session 3)
Commits `7bb2edd`. Missions: m20 (Opus high). Details: history 2026-10-08; report m19.
- m19 fixes: refused runs fall back to walking; a 20 s stuck alert; a drainer event and query; weak adjacent drainers
  killed; townfarm stops when dry.

## 1.22.0 -- 2026-10-16 (session 3)
Commits `7e4f058`. Missions: m19 (Opus high). Details: history 2026-10-08; report m18.
- m18 fixes: plural shop names; goto holds against faster hitters; lone unknown scrolls read, not sold; the dive uses
  Door/Stair Location.

## 1.21.0 -- 2026-10-16 (session 3)
Commits `506c4f1..f519491`. Missions: m18 (Opus high). Details: history 2026-10-08; report m17.
- m17 fixes: flee and goto path through unseen squares; climbs never go down; fuel bought in town.
- Viewer polls no longer count as Navigator activity (the lantern had burned 7300 turns idle in town).

## 1.20.0 -- 2026-10-16 (session 3)
Commits `fb1c382..278df42`. Missions: m17 (Opus high). Details: history 2026-10-08; report m17.
- Explore digs rubble and searches dead ends before calling a level done.
- `pilotctl complain` (the complaints channel); the supply gate on dives and recalls; a richer report.
- Avoid zones; a recogniser for inner rooms, pits and nests (`structures.py`); each level's map saved on leaving.
- The supply gate counts a light in the pack (every dive from town had been refused).

## 1.19.1 -- 2026-10-08 (session 2)
Commits `5d193f7..c9e2304`. No missions. Details: history "ARCHITECT HANDOFF 2026-10-08".
- Handoff and project snapshots (`tools/snapshot.sh`); the GitHub README.

## 1.19.0 -- 2026-10-08 (session 2)
Commits `7d608cb`. No missions. Details: history "ARCHITECT HANDOFF 2026-09-29" (mission 16 fixes).
- m16 fixes: stationary drainers never meleed or stood beside; ambiguous item names refused ("destroy Light all" had
  destroyed 14 CLW); {good} items not sold unidentified; `avoid` zones by square or name.
- Viewer: Tab shows the Navigator's view.

## 1.18.0 -- 2026-10-07 (session 2)
Commits `2765956..7c16bc5`. Missions: m16. Details: history 2026-09-29; `memos/to_architect/2026-10-08-missions15-16-replay.md`.
- m15 fixes and the Navigator's wishes; explore runs along two-wide corridors instead of zig-zagging.
- The stuck watchdog counts from the goal's start; day/night in the report.

## 1.17.0 -- 2026-10-07 (session 2)
Commits `e912370..00bda25`. Missions: m15 (the user watched live). Details: history 2026-09-29.
- The mover runs per the Advisor's running memo; m14 fixes.
- The viewer in the game's colours with the Navigator's journal; the time in every report; `pilotctl journal`.

## 1.16.0 -- 2026-10-07 (session 2)
Commits `a516853..aed11d2`. Missions: m14. Details: history 2026-09-29; `memos/to_architect/2026-10-07-mission13-*.md`.
- m13 fixes (wilderness, recall at night, double eating); the audit logs every check.
- Flavours: a flavour table, unknown-item sell rules, flavours learned from Identify.
- Observers: `watch.py` (live view and commentary), `notes.py`; the user can message the Navigator live.
- Blows and damage per weapon; drained stats name the Restore; `goal townfarm` (gold from townspeople).

## 1.15.0 -- 2026-10-07 (session 2)
Commits `771d141..67acff1`. Missions: m13. Details: history 2026-09-29; `memos/2026-10-03-game-state.md`.
- The Advisor's game-state survey: a full redraw after level changes and losses; a fresh inventory per decision.
- Tool-mode `flags` and `floor` queries; Free Action and resists read from the character sheet.
- Actions wait for their effect and say "no effect seen"; a state audit every 30 s.

## 1.14.0 -- 2026-09-29 (session 2)
Commits `72ec098`. Missions: m12 (2026-10-03). Details: history 2026-09-29.
- The current character level, not the max; climbs scum only by a close `>` within `max_depth`.

## 1.13.0 -- 2026-09-29 (session 2)
Commits `df69d21`. Missions: m11. Details: history 2026-09-29.
- Fixes after m10, where Dive04 died at 250 ft; the Advisor's m9 replay.

## 1.12.0 -- 2026-09-29 (session 2)
Commits `7160211..67bfe1a`. Missions: m10. Details: history 2026-09-29.
- Message patterns from the Advisor's catalogue; the light off when idle in town.
- Group danger phases only when hurt; every shop buy fixed; one read or quaff at a time until confirmed.

## 1.11.0 -- 2026-09-29 (session 2)
Commits `f477dda..0090192`. Missions: m9 (approx.: `7160211` and `e2e741f` loaded ~21:50). Details: history
"2026-09-27, late evening" and 2026-09-29.
- Group danger (the Borg's rule, from the Advisor); escapes verified and resent.
- Torches swapped only for one with more light (burnt-out spares had been swapped ~2100 times).
- `goal shop N list`, `buy NAME:N@MAX` price caps, `monster NAME`; visible ranged attacks count as hits.
- HANDBOOK: the user's outfitting advice.

## 1.10.0 -- 2026-09-27 (session 2)
Commits `04ac768..63ef06b`. Missions: m8 (Dive04's first mission, clvl 1). Details: history "2026-09-27, late evening".
- Check the `@R` recall inscription the server will read; choke points in two-wide corridors.
- The emergency never falls through to the goal; the Pilot stays up after a death; `goal resurrect` (untested).
- The Advisor's danger table and rules.

## 1.9.0 -- 2026-09-27 (session 2)
Commits `6274e8b`. Missions: m7 (Dive03 died at 750 ft, gone for good). Details: history "2026-09-27, late evening".
- Tool mode logs in under a neutral name and slows time at low HP (the time bubble).
- Status cures in fights (stun, confusion, blindness, poison); weak stationary blockers are killed.

## 1.8.0 -- 2026-09-27 (session 1)
Commits `b034b0e..32cf9f2`. No missions. Details: history "2026-09-27, afternoon".
- m6 fixes: a Flee crash; HANDBOOK notes on disenchanters and teleport-to.

## 1.7.0 -- 2026-09-27 (session 1)
Commits `f1c0579`. Missions: m6 (700-800 ft). Details: history "2026-09-27, afternoon".
- m5 fixes: a graze or a spiked pit no longer reads as an unseen attacker; brief perception gaps ignored.

## 1.6.0 -- 2026-09-27 (session 1)
Commits `5847bbf`. Missions: m5. Details: history "2026-09-27, afternoon".
- m4 fixes: fewer unseen-attacker false alarms; Flee prefers up stairs; the mover digs rubble; perception gaps logged.

## 1.5.0 -- 2026-09-27 (session 1)
Commits `f0a23a1..415e0d2`. Missions: m4. Details: history "2026-09-27, afternoon".
- A pending recall tracked from server messages; heal or escape by numbers (potion table and damage rate); rest
  instead of potions out of combat.
- A danger model from `monster.txt` (breathers, hound packs, paralysers, summoners); leave on unseen attackers.
- m3 fixes: the mover clears queued steps (it circled a `>` for 10 minutes); a `stuck` event.

## 1.4.0 -- 2026-09-27 (session 1)
Commits `2992c70..699ca87`. Missions: m3 (approx.: `f0a23a1`-`fea3910` went in during it). Details: history "Status
2026-09-26" and "2026-09-27, afternoon".
- Read a scroll on a chosen item; resume the goal after an emergency; never park during a recall.
- Fear: Boldness, Heroism or Berserk, else phase away; kite when afraid (the user's advice).
- Explore fetches nearby items; probable specials are not sold; m2 fixes.
- Tool mode `clear` command (empty the server's command queue).

## 1.3.0 -- 2026-09-26 (session 1)
Commits `14de204..c8c78c4`. Missions: m2 (approx.: more fixes went in during it). Details: history "Status
2026-09-26"; `runs/pilot/dive03/navigator.md`.
- m1 fixes: Recall respects `max_depth`; the dive can climb; item actions by name with a fresh pack.
- `park` (log out at a safe moment) and `restart.sh` for updates.
- `destroy`/`drop` N or all; autodestroy by pseudo-ID feeling.

## 1.2.0 -- 2026-09-26 (session 1)
Commits `1ee16c4..3e9c407`. Missions: m1 (approx.: `14de204`-`5f61f1b` went in during it). Details: history "Status
2026-09-26".
- Tool mode minimap query (the true wilderness position); `wearall`; the shop buys the cheapest match.
- Emergency fixes after Dive03's death at 1000 ft: rest on the stairs after an escape, flee from a monster far above
  our level, Recall as the last resort, a `max_depth` order.
- Town stairs remembered; light kept burning; unreachable stairs retried.

## 1.1.0 -- 2026-09-25 (session 1)
Commits `68d581c..2a3d488`. No numbered missions. Details: history "Status 2026-09-26"; `design_pilot.md`.
- Fixes from the first agent-driven dive (Dive03, town to 600 ft): Phase Door rationed, pickup works, shop sells by
  name, `goal hunt`.
- Running (2.2 to 5.5 tiles/s across town), exploring that doesn't get stuck, secret-door search.
- Breeder warnings, drained stats reported, no exploring on the surface. HANDBOOK: the user's money rules.

## 1.0.0 -- 2026-09-25 (session 1)
Commits `e726f47..68bf4a2`. No numbered missions (the first agent-driven dive ran on it). Details: history "Status
2026-09-26"; `design_pilot.md`.
- The first Pilot: world model, mover, reflexes, goals and the `pilotctl` control CLI (`tools/pilot/`).
- `HANDBOOK.md` for the playing agent; stair-scumming; a shop goal.

---

# 0.x: the tool client and the shop catalog

2026-09-24 to 09-25: a headless MAngband client that programs can drive, and `shopcat`, which walks the town and the
wilderness and catalogs the player shops on the live server.

## 0.4.0 -- 2026-09-25 (session 1)
Commits `04b8e89..e01a367`. No missions. Details: history "Phase 0: throwaway character factory".
- Character factory: `--birth` without menus, `suicide NICK`, `newchar.py`.
- Recording a human playing (`tools/observe/record.py`, `timeline.py`, `screen.py`); passwords kept out of logs.
- Tool-mode events and commands for a player: level, confirm, monster and item lists, map colours, options, rest
  (`pilot/glyphs.py` decodes monsters from the map).

## 0.3.0 -- 2026-09-25 (session 1)
Commits `6ec6f8b..d682520`. No missions. Details: history "MAngband tool client — state of play and next steps".
- shopcat fixes after review; `--list-servers` from the metaserver; buys a lantern when needed.
- Running along long straight stretches.

## 0.2.0 -- 2026-09-24 (session 1)
Commits `e2e51fe..468b717`. No missions. Details: history "MAngband tool client — state of play and next steps".
- `shopcat`: catalogs the player shops through the tool client, touring the 12 wilderness levels around town.
- Survival on the way: food and oil restocks, keeping out of wilderness arenas, fighting back.
- Our own pathing, tile by tile near level borders; logs and fences block movement.

## 0.1.0 -- 2026-09-24 (session 1)
Commits `6963c00..74903ae`. No missions. Details: history "MAngband tool client — state of play and next steps".
- Pristine MAngband 1.5.3 sources.
- The tool client: a packet logger, non-interactive login, headless tool mode (`-mtool`) with a command channel,
  position tracking and the full-level map.
