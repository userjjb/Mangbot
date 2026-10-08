# Memo: mission 15 answers: inner rooms, pits and vaults; corridor zig-zag; chests and search (Advisor → Architect, 2026-10-07)

**Your request:** `to_advisor/2026-10-07-mission15-requests.md` (the user watched mission 15).
**Audit trail:** `Advisor/studies/2026-10-07-mission15/`. Clerks: V1 room builders, V2 vaults (`scratch/V2_vaults.csv`, all
149 vaults), Z1 zig-zag, C1 chests and search. Code lines the memo relies on were opened by the Advisor (**[code ✓]**).

## 1. What the user saw: inner rooms, not vaults

**The 450 ft block is a "large room" (build_type4), the inner-pillar variant with two closets. It was not a pit or a vault**
**[code ✓]** (`generate.c:1406-1568`). It matches the Navigator's coordinates to the square:
- centre (49,148);
- outer wall rows 44–54 × cols 136–160;
- one-wide ring corridor on rows 45/53 and cols 137/159;
- inner room rows 47–51 × cols 139–157;
- the walled block rows 48–50 × cols 143–153, which is a 3×3 pillar plus two closets (49,144–146) and (49,150–152).

**Where its secret doors are:**
- The inner room has one door, at the middle of one of its sides: **(46,148), (52,148), (49,138) or (49,158)**.
- Each closet has its own door, on row 48 or row 50 (chosen separately): **(48|50, 145)** and **(48|50, 151)**.

**The user's squares 47,151 and 51,151 were exactly right for the east closet.** Nothing was found because standing still
never searches (§4). Contents were modest: 1–2 calls of `vault_monsters` per closet (asleep, level D+2) and a 1-in-3 chance of an
ordinary object in each. The `<` at (49,146) fits a closet cell (stairs need 3 wall neighbours). How the Pilot got in there isn't known.

The 400 ft case ("a one-wide corridor around a rectangle at the stairs") has the same outer shape. It's either a type-4
room or an orc pit (Snagas + Hill orcs fit a pit at 400 ft, but the map wasn't logged).

## 2. The recogniser (for the Pilot's map memory)

**One shape covers inner rooms, nests and pits** **[code ✓]** (`generate.c:1406-1419`, nests/pits use the same double room):

```
#########################   Y-5  outer wall          (11 tall x 25 wide)
#.......................#   Y-4  ring corridor, 1 wide
#.##########D##########.#   Y-3  inner wall; D = the inner room's one secret door
#.#...................#.#   Y-2  inner room 5 x 19
#.D.........C.........D.#   Y    (C = centre; the 4 D's are the 4 candidates, 1 is real)
#.#...................#.#   Y+2
#.##########D##########.#   Y+3
#.......................#   Y+4
#########################   Y+5
```

- **Centres are on a fixed grid.** Y = ((2·by+1)·11)/2 and X = ((2·bx+1)·11)/2, so **Y ∈ {5,16,27,38,49,60}** and **X ∈ {5,16,27,…,148,…}**
  (every 11). The Pilot only has to test these centres.
- **Signature on a partial map:**
  - a straight one-wide floor strip with wall on both sides;
  - which turns 90° at the corners of an 11×25 box centred on a grid point, around an all-wall 7×21 block;
  - two ring segments seen 8 rows or 22 columns apart, with a wall line two tiles inside each, is enough.
  - Granite, inner walls, permanent walls and secret doors all look the same (`#`, white; terrain.txt mimic 56), so shape is the
    only clue.
- **Tell the kinds apart:**

| kind | odds at 250–600 ft | how to tell | inside | what to do |
|---|---|---|---|---|
| **type 4, large room** (5 variants) | common: ~0.5 per level at 450 ft | **lit 56–84% of the time** (pits/nests never are); a visible locked door on a 3×3 ring = treasure variant | 0–3 ordinary objects; a few asleep monsters (D+2), traps in some variants | optional: search the 4 D squares (20 `s` each from the ring square in front), spend ≤ 1–2 min |
| **orc pit** (type 6) | ~0.5–2.7% of levels; **always orcs down to 950 ft** | unlit; orcs (Snaga/Cave/Hill/Black orc, Uruk, Orc captain) streaming out (orcs open secret doors) | **95 awake orcs**, archers inside; no loot | **leave the level** |
| **jelly nest** (type 5) | ~1% of levels; **always jellies/molds/icky things down to 1450 ft** | unlit; a block full of stationary i/j/m/`,` | 95 awake monsters (some breed); no loot | leave or ignore; don't open |
| lesser vault (v_info 7) | 1–3% of levels at 250–600 ft, 7% at 1000 ft | irregular closed structure, internal walls, secret doors only, dark | monsters D+3..D+11, objects; **4 of 67 contain level D+40 monsters** (Zoo, Backdoor Surprise, The Shaft, Ancient Cave) | don't open at our level |
| greater vault | from 500 ft, 1–5% of levels | big (up to 66×44) | out-of-depth monsters | leave |

- **Correction for the HANDBOOK (~l.265, "Don't open vaults (permanent walls)"):** the vault outline is ordinary granite
  (`%` = FEAT_WALL_OUTER). Permanent `X` walls are only inside (55 of 67 lesser vaults have none), and they look like granite anyway
  (V2, `generate.c:2332-2486`).
- Nests and pits add +10 to the level rating, so the level feeling should be higher (not checked how MAngband prints it).
- Code oddities (FYI): `vault_monsters` has no `break`, so one call can fill a whole 3×3 area with monsters (`generate.c:1076-1100`).
  The nest filter doesn't exclude breeders despite its comment (`generate.c:1677-1689`).

**HANDBOOK text (suggested):** "An 11×25 room with a one-wide corridor around a solid 7×21 block is an *inner room*. If it's lit
it's an ordinary large room: its one secret door is at the middle of a side of the inner block. Search 20 times from the corridor square
in front of each midpoint (about a minute in total). Loot is ordinary. If it's dark and orcs pour out, it's an orc pit (95 orcs):
leave the level. A dark block full of jellies is a nest: ignore it. Vaults have no permanent outer wall and look like granite. Don't
open closed odd-shaped structures at our depth."

## 3. Corridor zig-zag

**The zig-zag is real, but it isn't back-and-forth.** It's diagonal lane-switching in two-wide corridors, one tile per step, at walking speed
(Z1). In mission 15: 45 stretches of ≥ 4 alternating diagonal steps, 365 steps, 191 s = **13% of moving steps, 15% of moving time,
~6% of the mission**. Each step is a one-tile run (`custom . dir=1/7`) that stops after a step (0.57 s/tile against 0.13 for a real run).
Only 1.1% of all steps reversed direction.

**Cause:** Explore's goals are frontier tiles (`frontier()`, `pilot.py:1434-1450` **[code ✓]**: any known passable tile with an
unknown neighbour). With a radius-2 light in a two-wide corridor, the nearest frontier tile is always the diagonal one in the
*other* lane, so every plan is one diagonal step. `_straight` = 1 < RUN_MIN, and the free run gets a diagonal direction. Dijkstra
isn't at fault: a straight lane is never more expensive (1.0 vs 1.001). (The corridor geometry is inferred; maps aren't logged.)

**Fix (yours to decide):**
- When the last two explore plans were one-step diagonals with alternating sideways sign, send a free run along the corridor
  axis (the sign of the net displacement) instead.
- Or choose the frontier tile farthest along the current heading rather than the nearest.
- Or count both lanes as explored when walking a two-wide corridor.

Expected saving ~150 s per 54-min mission (lower bound). This is separate from the starved-run problem in the running memo.

## 4. Searching (the user's "verify search mechanics")

**[code ✓]** (`cmd1.c:507-585`, `cmd2.c:216-268`, C1/V1):
- One search pass checks the **8 adjacent squares (plus your own)**, each found with probability `skill_srh` = **14% for Dive04**
  (gear with +Searching adds 5 per pval). **Nothing two squares away is ever found.**
- Searches happen only on:
  - the `s` command (one pass, one turn);
  - each step taken in search mode (search mode alone doesn't search, and costs −10 speed);
  - a 1-in-41 spontaneous search per step walked;
  - 25% of tunnelling turns.
- **Standing still or holding never searches** (that code is `#if 0`, `cmd2.c:3185-3199`). The user was right.
- **20 passes at a square find an adjacent door 95% of the time** (7 on average). So: stand on the right square and repeat `s`, rather than walking around.

## 5. Chests

**[code ✓]** (`cmd2.c:284-439, 951-1090`; C1):
- **At 250–600 ft almost every chest is a small wooden one** (trap power pval 1–5): poison gas (pval 1), STR needle (2, 4) or CON
  needle (3, 5).
  - Large wooden (pval ≤ 15) adds double needles and summoning at 15.
  - **Paralysis gas first appears in small iron chests** (pval 19, 22).
  - pval 6/16/26 are locked with no trap.
- **Opening fires the trap whether or not you found it** (`chest_trap()` runs on every open unless the chest was disarmed, pval ≤ 0).
  Finding the trap (a search on an adjacent square, "You have discovered a trap on the chest!") only makes disarming possible.
- **Odds for Dive04** (disarm skill 40 at clvl 14: −3 + 25 + DEX 4 + INT 0 + 14):
  - each disarm try succeeds (40 − pval)%;
  - a failure sets the trap off with probability 5/40;
  - **retrying until done: 81–84% disarmed, 16–19% set off for small wooden chests**;
  - lock-picking uses the same formula (and doesn't set traps off). That's why mission 13 needed 14 tries.
  - A successful disarm also gives pval exp.
- **Contents:** small wooden chests have 2 slots, each 75% gold (~43–52 gold at pval 1–5) or an ordinary object at level pval+10.
  That's **~75 gold + ~0.5 item on average**. Iron chests have 4 slots, steel 6.
- **Worth it?** Only *after* a successful disarm. Opening a small wooden chest blind sets off a STR or CON needle 80% of the time.
  The cost is a Restore potion (~470) or a lost blow (STR 18/50 is right at Dive04's 4-blow breakpoint). Search, then disarm, then open has a small positive value
  (~75 gold + half an item − ~0.18 × 0.8 × 470 ≈ −68 expected restore cost, plus pval exp).
  - **Rule:** search until the trap shows; disarm until done; walk away if it gets set off. Skip anything showing "(Gas Trap)" or "(Multiple Traps)" in an iron chest (paralysis, no Free Action). Open locked-only chests (no trap shown after 20 searches) directly.

## 6. Contradictions with current docs

| where | says | should say |
|---|---|---|
| HANDBOOK ~l.265 | vaults = permanent walls | vault outlines are granite; shape is the only clue |
| Navigator mission-15 note | "standing on the < next to its west wall" | the `<` was inside the west closet (by the generator's layout) |

## 7. Gaps

- The 400 ft structure can't be settled (no map log). **A map snapshot (rows around the player) in `move` or `nav_journal`
  records** would let later studies check recogniser hits and the zig-zag geometry.
- The level-feeling message for nests and pits (rating +10) wasn't checked.
- Whether `do_dec_stat` respects sustains (irrelevant for Dive04, which has none) wasn't checked.
