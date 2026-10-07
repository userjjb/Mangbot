# Study: identification and selling strategy (2026-10-07, user request)

## Goal

Give the Architect (Pilot rules, Navigator doctrine, HANDBOOK text) one coherent policy for unknown
items, covering use-ID versus Identify versus selling unknown, that maximises gold and keeps the character safe.

## The user's claims to verify

1. Quaffing unidentified potions out of combat is usually safe.
2. Reading unidentified scrolls and using unknown staffs is sometimes dangerous (e.g. summoning).
3. Most items sell for much more identified than it costs to identify them.
4. A Staff of Perception plus Recharging scrolls is usually cheaper than Identify scrolls.

## Questions

Q1. What does each unknown potion do out of combat to a warrior at 0–1500 ft (clvl 10–30, 135–300
    HP, no Free Action, Half-Orc: resists dark)? What can kill and what costs money (stat drain,
    exp)? How likely is each at a given depth (allocation + out-of-depth boost)?
Q2. The same for scrolls, staffs, wands, rods, rings and amulets (use / aim / wear). Do curses stick?
Q3. How does an item become aware or known (use, Identify, sell, buy, pseudo-ID)? What does each
    one change about the sale price?
Q4. What does identifying cost by each route (Identify scroll, Staff of Perception + Recharging,
    *Identify*, selling unknown), counting stock availability and the risk that a recharge fails?
Q5. What is an unknown item worth on average by tval and depth, unknown versus known (sale price),
    so that we can say when identifying pays?
Q6. What did our missions actually do with unknown items, and what did that cost?
Q7. What do MAngband players advise (forum)?

## Sources

- Code: `github/src/server/` (object2.c, store.c, use-obj.c / cmd6.c, spells1/2.c, xtra1/2.c),
  `github/lib/edit/object.txt`. These are primary.
- Script: `Advisor/data/identify/kinds.py` → `kinds.csv` (all 249 flavoured kinds: level, alloc,
  cost, sell unknown/known at our owners). `dist.py` (to do): kind probabilities by depth.
- Forum corpus `Advisor/data/forum/corpus/` (secondary).
- Our logs: `runs/pilot/dive0{1..4}/` (observation); the shops study's `S4_trades.csv`.

## Facts already established (Advisor, before the Clerks)

- **[code ✓]** Unaware value by tval: potion and scroll 20, staff 70, wand 50, rod 90, ring and amulet 45
  (`object2.c:1075-1112`). Aware but not known: the kind's cost. Known: the real value (wands and staffs
  get +cost/20 per charge, `object2.c:1253-1257`; cursed or broken = 0) (`object2.c:1362-1400`).
  **So for flavoured items, learning the flavour (aware) already gets the template price.**
- **[code ✓]** `get_obj_num` (`object2.c:646-770`): a 1-in-20 level boost `1 + L*128/randint1(128)`,
  then best-of-2 (50%) or best-of-3 (10%) by allocation level. Each `A:` entry adds 100/rarity.
- Identify: cost 50 (Alchemist, 4 stock entries, ~78–81 to buy). Recharging: cost 200, level 40
  (Alchemist, 1 entry). Staff of Perception: cost 400, level 10 (Magic shop, 2 entries).
  object.txt says recharge adds 2+1d(60/(lvl+2)+1) charges, fails 1 in (160−lvl−10×charges)/15.

## Assignments (pass 1)

| id | question | sources | status |
|---|---|---|---|
| P | Q1 potions: effects, harm, aware-on-quaff, stat/exp recovery | use-obj.c/cmd6.c, xtra2.c, object.txt | done |
| D | Q2 scrolls, staffs, wands, rods, rings, amulets: harm, aware-on-use, curses | same + spells | done |
| E | Q3+Q4 ID mechanics and costs: Identify, Perception, Recharging, store sell/buy awareness, purse, pseudo-ID | object1/2.c, store.c, spells2.c, dungeon.c | done |
| F | Q7 forum advice | forum corpus | done |
| L | Q6 our missions + current Pilot rules | runs/pilot, pilot.py, HANDBOOK, S4_trades.csv | done |
| (Advisor) | Q5 by script | dist.py + kinds.csv | done (dist.py, value.py, hazards.py) |

## Pass log

- Pass 1 (2026-10-07): five Clerks launched in parallel; the Advisor writes dist.py meanwhile.
- Pass 1 results: all five dispatches in; Advisor verified the cited lines the memo uses (synthesis.md).
  No second pass needed: the claims are answered; gaps listed in the memo §6.
- Memo: `../memos/2026-10-07-identify-and-sell.md`; note `../memos/to_architect/2026-10-07-identify-and-sell.md`.

## Retrospective

- Scripts first worked well again: kinds.py + dist.py were done before the Clerks and gave the depth odds
  no Clerk could compute. value.py/hazards.py turned the Clerks' mechanics into the memo's tables.
- Splitting by tval (P potions, D the rest) plus mechanics (E) plus forum (F) plus our logs (L) had no
  overlaps and one useful cross-check (E and D both derived device skill 22).
- Clerk errors caught: F read object.txt `P:` damage dice as charges, and doubted the sale rate (cap at
  100 only binds at high CHR). Lesson: give Clerks the object.txt line format, and the full price formula, in the brief.
- L (logs) was again the most practical: it found the server-wide flavour table and a false Navigator claim.
- Dispatches ran 5–40% over cap; acceptable for mechanics-heavy topics.
