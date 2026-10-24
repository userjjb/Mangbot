# Study 2026-10-24-structures: recognising pits, nests, vaults and special rooms before walking in

**Goal:** give the Architect signatures the Pilot can test on a *partial* map, plus monster mixes, that mean "a pit, nest,
vault or monster room is here", so the plan can prepare (or leave) before contact. Asked by the user via
`to_advisor/2026-10-24-m25-m26.md` (Nar + Orc shaman + Giant salamander + Wolf + Purple mushroom patch at 650 ft, m26).

**Questions**
1. For each room type (generate.c 1-8) and for tunnels/streamers: what does it look like from outside and from a partial map
   (wall glyphs, widths, rings, doors, lighting)? What's inside (monsters: level offset, awake/asleep; objects)?
2. How often does each appear per level at 300-1000 ft?
3. Are normal tunnels 2 wide in MAngband 1.5? Where do 1-wide passages come from (rings, vaults, others)?
4. Lesser/greater vaults allowed at these depths: external signatures (permanent walls? entrances? 1-wide mazes)?
5. Monster mixes: which sets of monsters seen together mean pit / nest / vault / type-3/4 inner-room monsters?
6. Our logs: on levels with long 1-wide runs or a recognised structure, what was there; what did m26's Nar level look like;
   how many of the 1-wide-run levels were unrecognised structures (false positives)?

**Script first:** `data/structures/corridors.py` -> corridors.csv, corridor_levels.csv (385 dumps): 24 levels with a 1-wide
straight run >= 5 squares (16 with >= 8, 7 with >= 12); all 7 recogniser-hit levels have one >= 10; four runs of exactly 21
(the type 4/5/6 ring, 23-wide room).

**Assignments (pass 1)**
| id | question | sources | status |
|---|---|---|---|
| S1 | Q1-3: room builders, tunnels, streamers, lighting, placement, frequencies; glyphs in the Pilot dumps | generate.c, Pilot glyphs/dump writer | launched |
| S2 | Q4-5: vault templates and pit/nest/vault monster mixes | vault.txt, generate.c 1838-2600, monsters.csv | launched |
| S3 | Q6: our logs | corridor_levels.csv, level dumps, events/decisions | launched |

**Pass log**
- pass 1 launched 2026-10-24.
- pass 1 done (S1, S2, S3). Memo ../memos/2026-10-24-structures.md; note to_architect/2026-10-24-structures.md. No pass 2.

## Retrospective
- The cheap corridor script framed all three briefs and S1 reproduced its counts exactly.
- Two Clerks independently found the summon trap (S2 from code + one log line, S3 from logs); the cross-check made it solid fast.
- The biggest finding (auto_scum ON) came from checking a surprising rate in a Clerk's table ("special" on 3 of 20 controls)
  against the code that assigns the feeling. Lesson: when a log rate disagrees with the generator model, look for a client
  option or server mode that changes generation before blaming the model.
- S1 and S2 disagreed on type-9 vaults; init1.c settled it (S2 right).
