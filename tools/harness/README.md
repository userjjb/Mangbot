# The set-piece harness (restructure step 4)

Test cases from the Advisor's set-piece list (`memos/2026-10-24-setpieces.md` and its addendum), run three ways:

- **U: unit set-pieces** (`unit.py`): the Pilot's decision code on constructed states, no server. Run after every Pilot
  or rulebook change: `python3 unit.py` (exit status 1 if one fails; `python3 unit.py hunt` runs a subset). Covers: the
  hunt check at 100/80/60% HP (A7's halves the live harness can't stage), the summoner rule (A8), qualitative vetoes,
  jewellery expectations, unique-drop feelings, the rulebook's junk kinds, shop pay by owner (six real sales), the
  town kit's tiers, trip conditions, ability proofs.
- **L: live set-pieces** (`setpiece.py ID`): staged on the test server with the DM (Gandalf), played by Dive04's real
  Pilot, scored from its decision log. `python3 setpiece.py list`. Results: `runs/setpieces/ID-TIME.json` and a line
  in `runs/setpieces/results.md`.
- **R: replays**: since 2026-10-23 the Pilot logs its status, pack and map replies (thinned) to
  `runs/pilot/NICK/state.jsonl`, next to `events.jsonl`, so a mission's state at second T can be rebuilt. No replay
  runner yet.

## Live runs

Each run:
1. Snapshots Dive04: `charsave.sh save Dive04 TAG`. This parks the Pilot, waits out the server's orphan timeout, copies
   the savefile and the Pilot's state files, and starts the Pilot again.
2. Takes Gandalf to town and back down, so every run gets a fresh level.
3. Recalls Dive04 to Gandalf's depth, then pulls it to his square (the DM's Invoke).
4. Summons the cast where the scenario says. The scenario's order goes in the instant the monster lands; the
   Navigator role is used, so the order checks apply.
5. Scores the run, then restores Dive04. Dive04 keeps nothing from a set-piece, dying included.

| id | scene | pass when |
|---|---|---|
| A7 | Hill giant adjacent, full HP, `goal hunt Hill_giant` | the hunt is allowed, the giant is slain, HP lost ≤ fight_sim's p90 |
| A8 | Skeleton human at 2, Ranger at 3, `goal hunt Ranger` | refused (a summoner, not alone); lowest HP ≥ 40% |
| A8o | the same, `goal hunt !Ranger` | the override is accepted; lowest HP ≥ 40% |
| A8w | a Ranger 3 squares off, no orders | the Pilot walks away (no Word of Recall), HP ≥ 80% |
| A1 | a trip plan working the level; Black orcs and a Hill orc group 6-7 off | lowest HP ≥ 40%; ≤ 3 Phase Door |
| A2 | Ulwarth (a unique above our level) adjacent, no stairs known | Word of Recall within 2 s of first sight; lowest HP ≥ 40% |
| A2L | the same with Lugdush (no rule fired before the simulator danger rule) | the same |
| A6 | a Gnome mage (blinks, summons) adjacent | ≤ 3 Phase Door; Phase never runs out; lowest HP ≥ 40% |
| C3 | Ulfast adjacent, the Architect orders the hunt | slain; his drop picked up |
| A3 | a Sabre-tooth tiger (+10, alone) adjacent, then an Architect goto 12 off | the goto is held; no walking with it adjacent |
| B1 | a Purple mushroom patch 2 off, a goto past it | never adjacent; no stat drained |
| B2 | three Giant red ants (STR drainers) | at most 2 drains; the second acted on (leave, or kill the weak one) |
| B3 | a Brigand (steals, teleports) adjacent | slain; nothing stolen |
| D6 | `goal explore` 40 s | best 5-s window ≥ 3 tiles/s: passes since the mover uses server pathfind (4.2 best, 3.2 overall; was 1.4-1.6) |
| L1 | a Hill giant 5-8 off, in sight | boulders thrown, no HP lost (a rulebook claim from the code: confirmed live) |
| L2 | hurt, then `goal recall` resting out of sight | ~10x sooner than standing: **open** (the read came at full HP twice; standing took 17.9 and 20.4 s) |
| A9 | `plan trip 300-300 via=recall` from town, then Snaga and Black orcs summoned 8-9 squares off | Door/Stair Location within 5 s of arriving; no second Word of Recall while one is pending |

The memo's A7 is at 1250 ft and its A8 Ranger at 6 squares; here they're at 300 ft and 3 squares. The DM summons any race
at any depth. On unlit ground a monster is seen only within the lantern's 2 squares, or the Half-Orc's infravision of 3
for warm-blooded ones. Farther off, the order is rightly held as stale.

## Tools

- `dm.py`: drives Gandalf.
  - `DM().connect()`, `menu(keys)`, `summon(race_idx, step, after)`, `invoke(name)`, `players()`, `clear_hooks()`,
    `descend(n)`, `ascend(n)`.
  - How the DM menu works: `server/xtra2.c` `do_cmd_dungeon_master`. Summon line N is monster race N. The
    movement hook fires when Gandalf steps, and the summon lands on the square he left. **Always clear the hooks**:
    a hook left set summons on every step. `summon()` clears them and checks.
- The tool client gained `interactive TYPE`, `keys TEXT` and `special` (`src/client/c-tool.c`). With them a server
  screen (the DM menu, 13) stays open while keys are queued, and its redraws arrive as `special` events.
- `charsave.sh save|restore NICK TAG`: see the orphan rule below.

## The orphan rule (why a restore waits)

A dropped connection doesn't remove a character from the world. It stays there, orphaned and vulnerable, until it has
been idle 15 s, or at once in town (`net-server.c` `player_drop`; the idle timer in `dungeon.c`). Only then is it saved
and freed (`player_leave`). **A login before that resumes the character in memory and ignores the savefile.** The
savefile's time proves nothing: the server also saves every player, orphans too, every few minutes. So `charsave.sh`
waits 20 s after the logout.

The first harness runs restored nothing for this reason, and Dive04 carried their effects over, costing a Word of
Recall and a ration. It was then restored properly from the first snapshot.

## Found by the harness (fixed)

- **Light:** with no light worn in the dungeon after an unexpected recall, the light keeper waited (5-60 s, and never
  with a monster adjacent). A7 fought a Hill giant in the dark. Now it wields one at once.
- **Hunger:** Satisfy Hunger scrolls weren't eaten. The town kit counts them as food, so with the ration gone Dive04
  went Weak and recalled "for lack of food" with four in the pack. Now the reflex reads one.
- **A7 staging:** the Pilot's own fighting kills a monster summoned beside it in the seconds before an order, and a
  summon (menu and hook cleanup) takes longer than a hunt waits for its target. Orders now go in the instant the
  monster lands.

## Staging facts (learned the hard way)

- **A repeat kill of a unique drops nothing and gives no XP** (`xtra2.c` 'cheeze'): use uniques the character
  hasn't killed. Dive04 has killed Brodda, Bullroarer, Orfax, Wormtongue and Farmer Maggot. A restore resets
  `r_killed`, since it lives in the savefile.
- **The DM's summons come with their escorts.** Lagduf brought 27 orcs, Mughash 24 Kobold shamans and a Wolf chieftain
  38 wolves, so the run turns into a band fight. A3 now uses a Sabre-tooth tiger (+10, no escort).
- **Going up to town and back doesn't free a level:** the server keeps empty levels a while, with any monster left on
  them (a leftover Ibun spoiled an A3 run). Runs rotate over 300-650 ft (`runs/setpieces/depths.json`), the least recently used first.
- **The Forge's items come out identified:** C8 (detecting Free Action from unidentified boots) can't be staged with
  it. The unit test `ability_proofs` covers the inference.
- **The Forge writes into Gandalf's pack slot a,** destroying whatever was there.

## Found by the batch of 2026-10-23 (fixed)

- **Lugdush and Ugluk triggered no danger rule,** yet the duel simulator expects ~350-440 HP lost. New danger
  reason: the simulator's average loss is over 80% of current HP (A2L passes on it).
- **Strength-only ratings:** the danger rule fled Ulfast as "rated 4" while the hunt check allowed him. A rating the
  rulebook marks as strength-only is now left to the simulator in both.
- **Hunts the emergency rule would break off:** the hunt check refuses a fight whose average loss ends below 2.5 of
  the monster's worst rounds (or `flee_hp`): Ulfast at 265 HP, and the Hill giant from 80%.
- **Confusion cured on every hit:** C3 spent 4 CSW and 2 CCW against Kobold shamans at 84-93% HP. The "being hit
  unseen" test counted visible attackers. Now it counts only unseen ones.
- **A unique's drop wasn't fetched** after a hunt (looting runs only in explore and dive). The policy step now
  fetches the items within 3 squares of the kill. Its first version marked the squares in the pickup's junk set
  and so never picked them up (C3's last FAIL).

## From the Advisor's emergency-threshold memo (rulebook r4)

- **The emergency rule's worst-case** is now the adjacent monsters' worst melee in the next 3 player turns at our AC
  (`worst_3turns_acNN`, a caster's `spell_max` if higher), summed. It was 2.5 raw worst rounds. The hunt check uses
  the same abort point. Ulfast's is 96, the Hill giant's 100 (was 150 and 160), a Nighthawk's 30 (was 25).
- **`flee_hp`** (0.5 by default) is the other abort point: from 80% HP a Hill giant fight ends on average below it,
  so that hunt is refused unless `flee_hp` is 0.4 (unit `hunt_hill_giant_by_hp`).
- **A unique this character has killed is refused as a hunt** (no XP, no drop):
  `runs/pilot/NICK/uniques_killed.json`, kept from the slain messages and seeded with Dive04's five.
- **Unit tests for C4 and C5**, which live staging would need many forged items for (each forge destroys a stack in
  Gandalf's pack): `pack_full_makes_room`, `loot_band_stops_looting`.

## D6: walking was capped at ~1.5 tiles/s; server runs aren't (fixed 2026-10-23)

Each step costs a player turn (~0.65 s at normal speed), so step-by-step walking can't beat ~1.5 tiles/s. The server's
time factor runs **5x** while the player is running with nothing in line of sight (xtra2.c `base_time_factor`,
RUNNING_FACTOR), and **its pathfind counts as running** (cmd1.c sets `running` for `running_withpathfind`). The mover
now sends `pathfind Y X` (mover.py `path_run`) for a leg of 4+ steps with no monster in view, aiming up to 20 steps
along its own path, and stops it like a free run. A square where a pathfind didn't move us isn't tried again. D6: best
5-s window 4.2 tiles/s, 3.2 overall (1.4 before). Regressions A3, A9 and the unit tests still pass.

## Observed, then changed (the user)

- A8o showed the danger rule fleeing a summoner on sight, and with no stairs known reading Word of Recall at full HP. The
  user: walk away if we just walked into its sight; other action only if walking away isn't safe. Now the `WalkAway`
  goal (A8w). A summoner the server's list names before the map shows it gets 1.5 s for its position (A8w's first run
  fled from the list alone). Walking away needs walked ground: after a recall or teleport arrival there is none, so the
  existing escapes apply.
