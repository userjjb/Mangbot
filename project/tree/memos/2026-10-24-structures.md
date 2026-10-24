# Memo: recognising pits, nests and vaults before walking in; m26's Nar was a summon trap; auto_scum is on (Advisor → Architect, 2026-10-24)

This answers the user's question in `to_advisor/2026-10-24-m25-m26.md`. The audit trail is in `Advisor/studies/2026-10-24-structures/`.

**How this was made:**
- **Script first.** `data/structures/corridors.py` finds 1-wide and 2-wide straight corridor runs in all 385 Dive04 level dumps. Its outputs are `corridors.csv` and `corridor_levels.csv`.
- **Three Clerks:**
  - **S1** read the room, tunnel and streamer code in generate.c, simulated room frequencies, and worked out the dump glyphs.
  - **S2** covered the vault templates (all 149, counted by script) and the pit and nest monster hooks, with Monte Carlo shares.
  - **S3** went through our 24 dumps with a 1-wide run plus 20 control levels, and reconstructed m26's Nar contact, the m24 pit and the m21 nest.
- **What I checked myself:** every claim below marked [code ✓] or [log ✓]. Finding 4 is my own, found while checking S3's feeling data.

## 1. m26: Nar's group came from a summon trap, not a pit or vault [log ✓ code ✓]

- **The log.** The monster list was empty at 02:57:12. On the next step came "You found a trap!" and "You are enveloped in a cloud of smoke!" (events.jsonl 1082980-93). In the same instant the list showed Giant salamander, Purple mushroom patch, Orc shaman and Nar, all adjacent and all attacking.
- **What the trap does** (`cmd1.c:1049-1059`): it calls `summon_specific(Depth, py, px, Depth, 0)` 2+1d3 times, so it brings 3-5 monsters.
- **What it can bring** (`monster2.c:2552-2589`):
  - any race up to level Depth+5, which is 18 at 650 ft;
  - **uniques included**;
  - **placed awake**, with their groups.
- **Why no structure fits.** Nar has no FRIENDS or ESCORT flag (S2), and no pit or nest hook allows a unique. The Wolf was a separate fight, killed 2 s earlier.
- **The room nearby was not the source.** It was a real 11x25 room, recognised 17 s after arrival and never opened. But the level's feeling was "very good", not "special", so by §4 it held no pit, nest or vault.
- **How common it is.** Our logs have 24 trap finds in total: 15 fire, 5 dart, **2 summon** (10-23 09:20 and m26), 1 teleport and 1 trap door.

**Pilot rule.** Treat "You are enveloped in a cloud of smoke!" as an instant emergency: 3-5 awake monsters adjacent, possibly a unique. **Phase first, then decide.** Running the hunt check on each arrival comes after the Phase.
A set-piece would test it cheaply: walk onto a known summon trap at 500 ft. A Staff of Trap Location (Magic shop) isn't worth it at 2 hits in about 30 missions.

## 2. What a partial map can tell [code ✓ for geometry; S1 sim for frequencies]

**Normal tunnels are 2 wide** (`WIDE_CORRIDORS`). The second square is dug only into plain granite (`generate.c:2797`), so a tunnel turns 1-wide wherever it runs beside a room wall.
**The user's "one-wide hallway" is real but noisy:**

| 1-wide straight run in a dump | dumps | real room ring | other |
|---|---|---|---|
| ≥ 8 squares | 16 | 9 | 7 tunnel pieces (beside room walls, door stubs, map edge) |
| ≥ 20 squares | 3 | 3 | 0 |

Real rings often show short runs, because doors and 2-wide tunnel entries break them (the Nar room's ring showed only 6-7). A raw run length is a weak test. **Use the geometry instead:**

1. **Rooms sit on a lattice.** `dungeon_align` is on (`lib/user/options.prf`), so rooms of types 1-6 are centred at Y ∈ {5,16,27,38,49,60} and X ∈ {16,49,82,115,148,181}.
   - All 7 structures the Pilot has flagged sit on it [log ✓].
   - `structures.py` scans every 11th X. It needs only these 6.
2. **Pits, nests and type-4 "large rooms" share one shape:**
   - outer wall 11x25 centred on a lattice point;
   - a 1-wide ring corridor (rows Y±4 are 21 squares between walls; columns X±11);
   - inner wall at Y±3 and X±10;
   - interior 5x19.
   A 1-wide run on row Y±4 or column X±11 of a lattice point is the ring. Merge runs across doors and gaps.
3. **Lit or dark settles most cases** [code ✓ `generate.c:1412`; nests and pits are always dark]:
   - **A lit 11x25 room is never a pit or nest.**
   - At 650 ft a level has about 0.39 type-4 rooms but only about 0.04 pits or nests.
   - **A dark one is a pit or nest about 17% of the time**, at every depth from 500 to 1000 ft.
   - §4's feeling refines this further.
4. **Type-4 interiors hold more than the comments say.** `vault_monsters` has no `break` (`generate.c:1084-1097`, [code ✓]), so each call fills up to 9 nearby squares. These monsters are asleep, at Depth+2, with groups.
   - 4.1 (empty inner room): about 6.
   - 4.4 (checkerboard): about 7-8, plus traps and 3 items.
   - 4.5 (four small rooms; 4 secret doors, *off*-centre): about 21.
   - 4.2 and 4.3 (treasure cell, pillars): 0-2.
   - These are counts by S1's simulation, without groups. A dark type-4 room is a sleeping-monster room, so it is XP, not a pit warning.
5. **The user's other two signatures:**
   - **"A 2-wide ring":** the generator has none. Rings are 1-wide, and 2-wide runs are ordinary tunnels.
   - **"Rows of `#%` walls":** `%` is a mineral vein. Veins are random streamers that cross granite and room walls diagonally (`build_streamer`). They are not a structure sign.
6. **What the dump can't show** (`world.py` keeps only the character, not its colour):
   - granite, inner, outer and permanent walls are all `#`;
   - secret doors also look like `#`;
   - so a vault's rim can't be told from granite.
   - At 650 ft vaults are rare in any case: about 1.3% of levels have a lesser vault and almost none a greater one (before §4's selection).

## 3. Monster mixes [code ✓ hooks and wake state; S2 Monte Carlo]

**What is possible at 500-1000 ft:**
- **Pits are orc pits.** A troll pit is possible only at 1000 ft, 1 time in 20.
- **Nests are jelly nests:** `j m i ,`, including mushroom patches.
- Animal and undead nests, and giant, dragon and demon pits, are impossible above 1500 ft.

**Signatures:**

| seen together | means |
|---|---|
| a unique in the group | **not** a pit or nest (both hooks refuse uniques) |
| many awake `o`, Snaga and Cave orcs first, Black orcs and Uruks further in, arrows | orc pit. The 44 weakest orcs sit on the outer band and the strongest at the centre. Orcs open the secret door |
| stationary `j m i ,` of levels 1-23 | jelly nest: walk past it. A Shambling mound shrieks |
| **all awake at first sight** | pit, nest or summon. Their monsters are placed awake; vault and room monsters asleep (`generate.c:2436-2475`) |
| a sleeping mixed crowd in a compact walled area | a type-4 room (Depth+2) or a vault (`&` Depth+5, `@` +11, `8` +40) |
| 3-5 mixed monsters appearing adjacent at once, after a trap message | summon trap (§1) |

Being out of depth alone doesn't mark a lesser vault: most `&` and `,` monsters are in depth (S2). What marks one is the count in a compact walled area, sleep, and for greater vaults a few monsters 10+ levels deep.
The awake test needs **an asleep/awake flag in monlist**, which we still don't have (see "What I lacked").

## 4. auto_scum is ON, and it chooses our levels [code ✓ log ✓]: please decide with the user

**The setting.** `github/lib/user/options.prf:38` has `Y:auto_scum`, and the client preloads that file (`c-birth.c:125`).

**What it does** (`generate.c:4275-4299`). When the player who generates a level has auto_scum, the server regenerates the level up to 100 times until:
- at 500 ft and deeper (Depth ≥ 10): its feeling is **"special" or rating > 20** (feeling ≤ 7);
- at Depth 5-9: rating > 10;
- shallower: rating > 0.

It doesn't apply when the feeling is suppressed ("Looks like any other level": you generated a level less than about 13 s earlier).

**What raises the rating:**
- out-of-depth monsters: +(level − Depth) each, and twice that for uniques, so **each member of an out-of-depth group counts**;
- egos and out-of-depth items;
- a vault's rating;
- +10 per pit or nest.

**Our logs** (all Dive04 arrivals, matched to the feeling message within 4 s):

| depth | arrivals | suppressed | special | very good / good | strangely lucky | luck turning | weaker (8-10) |
|---|---|---|---|---|---|---|---|
| 500-700 ft | 81 (29 unmatched) | 14 | **14** | 7 | 7 | 10 | **0** |
| 300-450 ft | 407 (229 unmatched) | 147 | 7 | 3 | 3 | 5 | 13 (all "like the look", allowed there) |

Not one fresh level at 500 ft or deeper fell below "luck is turning", which matches the rule exactly. **14 of the 38 informative arrivals at 500-700 ft were "special" (37%).** Without scumming the expected share is about 5% (S1: pit or nest 3.8% plus lesser vault 1.4% at 650 ft). The rest were levels with rating > 20, meaning out-of-depth monsters or good items.

**What this means:**
- **The feeling now tells us more than any map signature.**
  - At ≤ 850 ft, a pit, nest or vault always forces "special" [code ✓ `generate.c:1960, 2271, 2519, 2559`].
  - An artifact on the floor also forces it.
  - So any other feeling, except the suppressed "Looks like any other level", **proves there is no pit, nest or vault on this level**.
  - On a "special" level at 500-700 ft, a dark 11x25 room is a pit or nest far more often than 17%. I can't give the number without logs of which structure each special level held.
- **Every non-special fresh level at 500 ft or deeper has, by construction, about 20+ levels' worth of out-of-depth monsters, or good items.**
  - That may be part of m22's "mob levels" and of out-of-depth uniques like Nar being common. I haven't checked this.
  - It also means `depth_value.csv` (which assumes unscummed levels) understates danger, and XP, per level.

**Recommendation:**
1. **Pilot:** record the arrival feeling as a level field, `feeling: 0-10`.
   - Feeling 1 ("special"): set the "pit/nest/vault likely" flag: stairs first (the m24 protocol), and avoid dark 11x25 rooms.
   - Feelings 2-7: label any 11x25 room "type-4 room: sleeping monsters at Depth+2". It is not a pit warning.
2. **The user's call:** whether to turn `auto_scum` **off** for Dive04 (`X:auto_scum` in the Pilot's client pref, or `=` options in game).
   - **Off:** levels as the rulebook models them, about 5% special, fewer out-of-depth groups, and stair-scumming still gives fresh levels.
   - **On:** about 7× more pits, nests and vaults, and out-of-depth monsters by design. That means more XP per kill and more loot, but more bad arrivals.
   - **For a throwaway warrior without Free Action, I'd turn it off.** A mission or two each way, compared on XP/min and lowest HP, would settle it.

## Contradictions with current docs

| doc / belief | finding |
|---|---|
| user: "Pit" for Nar's group (m26) | summon trap (§1) |
| pit/inner room "one secret door at the middle of a side" | true for pits, nests and 4.1-4.4; **4.5 has four doors, off-centre** |
| type-4 inner rooms hold 1-4 monsters (code comments) | about 6 / 7-8 / 21 (no `break` in `vault_monsters`) |
| rulebook and depth_value assume plain level generation | auto_scum keeps only rating > 20 or special levels at 500 ft and deeper (§4) |
| generate.c comments: nests and pits by fixed depths | code: `randint1(Depth)` thresholds, so orc pits and jelly nests only, down to 950 ft |
| Pilot ADVICE "nest (jellies, molds, icky things; some breed; no loot)" | correct; at our depths nests are only jelly nests |

## Coverage and gaps

- **Covered:** all room builders, tunnels and streamers; every vault template (by script); all pit and nest hooks; all 385 dumps (by script); 44 levels classified by hand; three reconstructions.
- **Not live-tested:**
  - S2 found that 22 of the 149 vault templates have a sealed rim (permanent rock behind the outer wall), so tunnels can't reach inside. That comes from the code only, not from a running level.
  - The share of "special" levels at 650 ft that hold a pit or nest, as opposed to a vault or an artifact.
- The feeling counts have 29 unmatched arrivals at 500-700 ft, where a feeling message came more than 4 s after the arrival message, or none came at all.

## What I lacked

- **No asleep/awake flag in monlist.** "All awake at first sight" is the best mix signature, and it can only be inferred from attack messages.
- **No map timeline.** There is one dump per level, written at the end, so I couldn't measure how many seconds before contact a ring became visible. `state.jsonl` map events are viewport snapshots.
- **No colours in the map memory.** World stores characters only, so the Pilot can't see a vein's colour. Wall kinds and secret doors are `#` on the server's side anyway.
- **The arrival feeling isn't a structured field.** I matched message text to arrival messages within 4 s, and 29 of 81 at 500-700 ft didn't match.
