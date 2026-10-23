# Memo: the set-piece list, test cases from missions 15–23 (Advisor → Architect, 2026-10-24)

**Restructure step 4 input** (you asked for it, and the user agreed, 2026-10-23). **Audit trail:** `Advisor/studies/2026-10-23-setpieces/`. Three Clerks:
F1 (missions 15–19: 40 incidents, `scratch/F1/F1_incidents.csv`), F2 (missions 20–23: 30 incidents, `scratch/F2/F2_incidents.csv`),
and S1 (what the test server can stage, and what a replay can rebuild). The 70 incidents are merged into **41 set-pieces**, each with
its source incidents, how it's staged, and a pass rule over the logs and scorecard (`memos/2026-10-23-scorecard.md`).

## 1. What the incident lists say

1. **One deadly pattern has no rule at all:** a mob in a corridor with the stairs far away (m17 14:11, 36% HP; m18 19:08, 39%; m22 01:50;
   m23 22:26). Every close call under 40% was ended by Word of Recall, read late.
2. **About half the fixes were never exercised in a later mission** (F1). The held `goto` against faster hitters (7e4f058) has never fired. The
   dead-end search (fb1c382) has never run. One fix failed again within 8 hours: the no-melee rule for stationary drainers (2765956, failed in m16).
   Missions are a poor test: the case must turn up by chance.
3. **The costliest losses were item handling, not combat.** These are the forced `!` sales (the Free Action boots for 3 gold, the Staff of Sleep Monsters),
   the unique drop skipped as bulky (Brodda's Scimitar), and junk filling the pack while valuables stayed on the floor (m22, ~1,260 gold).
4. **Dive04 had Free Action from m18 to m23 and nobody knew** **[✓]**:
   - "You are unaffected!" to HOLD spells at m18 19:08:21, m21 01:27:30–31, m22 01:48:06 and 02:05:46. The server prints that only when `free_act`
     is set (`melee2.c:1445-1448`).
   - The unidentified {excellent} Soft Leather Boots were Boots of Free Action [2,+4].
   - The Navigator recalled 6 min early in m21 on the false premise that it had no Free Action.
   - In m23 the boots were swapped out and force-sold (shop re-list 2,265).
   - **Dive04 has no Free Action now.**

## 2. What can be staged (S1)

- **Live staging:** only the DM character **Gandalf** (`DUNGEON_MASTER_NAME`). Through the `&` menu he can:
  - place any monster (always awake, with its group);
  - build any terrain (doors, locked or secret doors, rubble, traps, stairs, walls);
  - stamp any vault;
  - forge an item in his pack (pluses, ego) and drop it;
  - pull Dive04 to his square (or recall it to his depth, then pull);
  - make a level static, and export or import a level's terrain (monsters and objects aren't saved).
- **He can't:** set Dive04's HP, stats or pack, put an item on a chosen square except by dropping it, or use a fixed seed (`xtra2.c:5966-7322`, `save.c:690-800`).
- **Blocker 1:** the tool client answers every menu with ESC (`c-tool.c:351-358`). **A key-sending verb is needed** before Gandalf can be scripted.
- **Blocker 2 (replays):** `events.jsonl` skips the map, status and inventory replies (`pilot.py:4838-4841`). A replay can't rebuild the Pilot's map memory
  or pack at second T. Log those replies, or run with `--pktlog`, so every future mission is replayable.
- **Recipe for a reusable arena:** author a terrain file once (Level tab `E`/`I`, a text hex-row format) or a `vault.txt` entry. Then per run:
  import or stamp it, make the level static, pull Dive04 in, and summon the cast with hooks.

Kinds below: **L** = live set-piece with Gandalf; **R** = replay of a recorded window through the decision code (needs blocker 2 fixed for new
missions; old windows give position, HP, monsters and messages only); **U** = unit test of the decision code on a constructed state (no server).

## 3. The set-pieces

**Priority:** P1 = caused a close call, a death or an irreplaceable loss, and has no rule or an unexercised one. P2 = costly and recurring.
P3 = a regression guard for something fixed and exercised.

### A. Danger and escape

| id | scenario | from (incidents) | kind | setup | pass when | P |
|---|---|---|---|---|---|---|
| A1 | **Mob in a corridor, stairs far** | m17 14:11, m18 19:08, m22 01:50, m23 22:26 | L | 2-wide corridor, stairs ≥ 40 away; summon 3 Black orcs + a Hill orc group 5–8 squares away; Dive04 full HP | escape (WoR, then Phase to bridge) decided while HP ≥ 60%; lowest HP ≥ 40%; no looting toward the mob | P1 |
| A2 | **Unique adjacent on arrival, no stairs known** | m15 Brodda (17%), Dive03 M2 1000 ft | L | static level, no stairs in the known map; pull Dive04 in; summon Brodda adjacent | WoR read ≤ 2 s from first sight (listed or decoded); Phase when HP < 2 × worst round; lowest ≥ 40% | P1 |
| A3 | **Fast hitter during a Navigator goto** | m18 Nighthawk (215 → 101) | L/U | summon a Nighthawk (+10) adjacent, then order `goto` 30 squares away | the goto is held (the "goto held" tactic fires); no walking with it adjacent | P1 (never exercised) |
| A4 | **Slow ranged caster unique** | m15 Wormtongue ×2, m18 | L | Wormtongue 6 squares away, stairs 12 and 40 away | no flee walk > 8 squares in his line of sight; hunt or stand (melee ~6/round, he has 250 HP) | P2 |
| A5 | **Unseen caster or curse at full HP** | m20 Novice priest ×2, m21 Illusionist HOLD, m18 perception gap, m17 shriek | L | an invisible or out-of-light caster casting curse, hold or shriek | news only; no level change while HP > 80%; never down past `max_depth` | P2 |
| A6 | **Summoner brings a band** | m22 Gnome mage → 11 Hill orcs (02:11:34–02:12:40; the user flagged 02:12:21 "this fight will be helpful to study": 8 Phase, stairs back and forth), Orfax yeeks | L | Gnome mage adjacent; let it summon | ≤ 3 Phase reads, then WoR or stairs; Phase stock never 0 | P1 |
| A7 | **Fear casters** | m22 Novice paladins ×7 (31%) | L | a Novice paladin group | Boldness/Heroism quaffed, or escape, before HP < 50% | P2 |
| A8 | **Blind and confused in melee** | m15 23:18, m16 15:42 | L | Bloodshot eye + Novice mages | cure without visible monsters when HP falls; no explore moves while blind or confused | P3 (fixed 9089ae2) |
| A9 | **No cure wasted** | m15 mold CSW, m16 CLW+CSW at full HP | U | confused next to a stationary mold at 99% HP | no potion; step away | P3 |
| A10 | **Arrive in town at low HP** | m22 02:00 (Phase ×2 against a drunk) | L | recall into town at 40% HP next to harmless townspeople | no emergency, no Phase; rest or buy cures | P3 |
| A11 | **Unique fled, then returns** | m15 Brodda "flees in terror" | L | wound a unique to fear, wait | it's kept as a threat out of view (belief state); no relaxing until it's dead or the level is left | P2 |

### B. Drainers, thieves, traps

| id | scenario | from | kind | setup | pass when | P |
|---|---|---|---|---|---|---|
| B1 | **Stationary drainer beside the path** | m16 Purple mushroom patch (CON ×2), Rot jelly (CHR ×4), m15 Red jelly "blocking the way" | L | patch beside a 1-wide corridor that's the only route; jelly in a doorway | never adjacent; another route, or wait; no melee; 0 drains | P1 (failed once after its fix) |
| B2 | **Mobile drainers** | m18 scorpion, m19 ant + frog + scorpion (3 drains in a minute) | L | a Giant red ant group at 600 ft | leave or avoid after the 1st drain; "drained twice on this level → leave" | P2 |
| B3 | **Thief, item stolen** | m21 Brigand (armour of Resistance), m18 Speed potion | L | Brigand adjacent, a valuable in the pack | kill it before it touches if possible, else hunt it and recover | P2 |
| B4 | **Town thieves during townfarm** | m15, m17, m18, m19 (~300 gold) | L | day town, urchins and a Scruffy hobbit | thieves attacked on sight; gold lost ≤ 0 | P2 |
| B5 | **Invisible toucher** | m15, m19 (food eaten, WIS drained) | L | an invisible Poltergeist/ghost | "eaten"/"drained" news; leave the level | P3 |
| B6 | **Trap cluster** | m22 3 traps in 30 s (STR, CON drained) | L | a corridor with 3 built traps, one found | path round known traps; search where traps cluster | P2 |

### C. Items and value (mostly U/R: the Pilot owns these in step 2)

| id | scenario | from | kind | setup | pass when | P |
|---|---|---|---|---|---|---|
| C1 | **Forced sale of a valuable** | m23 FA boots (3 gold), Staff of Sleep Monsters, Rod of Light; m21–22 staffs | U/L | `sell !X` on {excellent}/known-valuable/unknown-charge items | refused, or needs an explicit accepted-loss step showing fair pay vs offer | P1 |
| C2 | **Unknown charges / unknown plusses** | m17–19 Stinking Cloud ×4, Wand of Light, Awl-Pike | U | sell an aware wand with unknown charges | Identify first, or refuse; shortfall 0 | P2 |
| C3 | **Unique drop** | m23 Brodda's Scimitar | L | kill a unique (summoned) that drops a weapon; pack 20/23 | picked up regardless of bulk (drop junk first); never left on a level | P1 |
| C4 | **Pack full, valuables on the floor** | m16 15:58, m20, m22 loot room (~1,260) | L | pack 23/23 with junk; ring, wand, staff on the floor | destroy or drop junk by value, pick up valuables; value abandoned = 0 | P1 |
| C5 | **Loot while a band forms** | m22 01:50, m23 22:26 | L | items 10 squares away toward an approaching orc group | `band` event stops looting; fight at a choke or leave | P1 |
| C6 | **Ambiguous names and letters** | m16 `destroy Light all` (14 CLW), m22 twin-stack Identify | U | packs with "Light"/"Cure Light", twin rings | refused or resolved by whole word; the right item only | P3 |
| C7 | **Unknown jewellery** | m22 wore an unidentified cursed ring | U | `wear` an unknown ring | refused without Identify | P3 |
| C8 | **Ability detection** | m18–m23 Free Action unknown | L | forge Boots of Free Action, unidentified, wear them; summon an Illusionist | "You are unaffected!" → the Pilot infers Free Action, shows it in Abilities, and marks the boots keep-and-identify | P1 |
| C9 | **Identify before deciding** | m16 Trident {good} (42 vs 1,848) | U | {good} weapon in town with an Identify scroll | identified, compared with the wielded weapon (blows × damage), kept if better | P3 |

### D. Movement and exploration

| id | scenario | from | kind | setup | pass when | P |
|---|---|---|---|---|---|---|
| D1 | **Unseen corridor after a Phase** | m17 650 ft "no known path" | L/R | a corridor the map never saw; phase past it | a path is found (fallback through unseen squares); flee reaches the stairs | P3 (506c4f1) |
| D2 | **Frozen flee** | m19 22:16 (65 s still) | R | flee path through unexplored squares | no stretch ≥ 20 s without movement | P3 |
| D3 | **Explore ends early / dead-end secret door** | m16 500 ft, 550 ft 42,110 | L | built level: dead end with a secret door leading to the rest | dead ends searched (15×) before "nothing left" | P1 (never exercised) |
| D4 | **Inner room and searchroom** | m15 450 ft (49,148), m20 27,49 | L | stamp a type-4 inner room with closets (or build it) | recogniser fires; searchroom finds the door ≤ 2 min | P2 |
| D5 | **Two-wide corridor** | m15 zig-zag | L | 2-wide corridor, explore | runs along the axis; no alternating diagonals | P3 (b26c14a) |
| D6 | **Runs in dungeon and town** | running memo (82% starved), m21 townfarm walking | L | straight 20-tile corridor; town at night | run tiles/s ≥ 3 in the dungeon; town runs ≥ 3 from the edge; never off the map | P2 |
| D7 | **Finding `>` on a big level** | m18 9 min at 550 ft | L | large static level, `>` far away | dive reaches it in ≤ 3 min (Magic Mapping if carried) | P3 |
| D8 | **Climb never goes down** | m17 `dive 0` took `>` | U | climb goal on a `>` | never descends | P3 |
| D9 | **Stuck detector** | m20 lock-picking false alarm, m13 shop loop | U/L | lock-pick a locked door; a goal that oscillates | no false stuck; the loop is detected ≤ 60 s | P3 |
| D10 | **Starting items underfoot / gold beside you** | m23 22:15 | L | gold and items on adjacent squares in town | picked up ≤ 10 s | P3 |

### E. Town, supplies, server

| id | scenario | from | kind | setup | pass when | P |
|---|---|---|---|---|---|---|
| E1 | **Supply gate** | m10 death (1 CLW at 250 ft); Dive03 | U | stock below the stage minimum, order a dive | refused with what's missing unless forced | P3 |
| E2 | **Light at mission start** | m16–m18 lantern at 0 turns | L | empty lantern, no flasks, in town | flasks bought and fuelled before leaving town | P3 |
| E3 | **Store index crash** | m21 00:48 segfault | L | the redraw-while-in-store sequence | no crash (server fix bb56313) | P3 |

### F. Navigator contract (step 2)

| id | scenario | from | kind | setup | pass when | P |
|---|---|---|---|---|---|---|
| F1 | **Stale order** | m15 Brodda `goto` (17 s old), m23 "going back" to a gone level | U | an order whose `report_age` is older than a level change or a new adjacent threat | rejected or held, with the reason | P1 |
| F2 | **Report accuracy** | m17, m18, m22 lowest HP understated | R | replay a mission's windows | the report's "since last report" lowest HP equals the log minimum | P2 |

## 4. Suggested order

1. **The two enablers:** a key-sending verb for Gandalf, and logging the map, status and inventory replies (or `--pktlog`).
2. **The P1 set:** A1, A2, A3, A6, B1, C1, C3, C4, C5, C8, D3, F1. Twelve cases covering every close call and every irreplaceable loss in m15–23.
   Most need new rules (A1, A6, C8, F1) or a rule that has never fired (A3, D3).
3. **Then the P2 set, and the P3 set as regression guards.** Run the whole suite before every mission once step 2's decision changes land.

## 5. Contradictions with current docs

| where | says | should say |
|---|---|---|
| my briefs, memos, HANDBOOK-style notes | Dive04 has no Free Action | it had it m18–m23 (unidentified boots); it has none since the m23 sale |
| m17 report | lowest HP 46%; 63+12 gold stolen | 36%; 63+46 |
| m18 report | no theft by Wormtongue; low ~112 | a 41-gold theft; low 84/215 (39%) |

## 6. What I lacked

- No time-correct map for replays (the exit dump is one frame), and no pack snapshots.
- m15–16 events have no `epoch`.
- No way to script the DM.
- The Clerks couldn't test any staging live: S1's table is from code only.
- The Brodda Scimitar's and the {good} boots' values remain ranges.
