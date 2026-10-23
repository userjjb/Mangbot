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

## Observed, then changed (the user)

- A8o showed the danger rule fleeing a summoner on sight, and with no stairs known reading Word of Recall at full HP. The
  user: walk away if we just walked into its sight; other action only if walking away isn't safe. Now the `WalkAway`
  goal (A8w). A summoner the server's list names before the map shows it gets 1.5 s for its position (A8w's first run
  fled from the list alone). Walking away needs walked ground: after a recall or teleport arrival there is none, so the
  existing escapes apply.
