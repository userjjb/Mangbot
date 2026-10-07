# Study: shops and economy for a CHR 4 Half-Orc Warrior (backlog topic 6; Architect request 2026-09-29)

- **Status:** DONE 2026-09-29 (memo in ../../../memos/; note to_architect/2026-09-29-shops-and-messages.md).
  the user pre-approved running the next studies). Runs in parallel with the message catalogue.
- **Goal:** a shopping list per depth band (0–500, 500–1000, 1000–1500 ft) for ~150 / ~500 / ~2000
  gold: what to buy where, what to carry, what to sell; with stock odds, CHR-4 prices, sell values,
  discounts, and light-fuel burn (town included) in real minutes.

## Assignments (pass 1)
| id | question | status |
|---|---|---|
| S1 | store stock: store_table (init2.c), store.c maintenance/turnover, always-stocked items, black market, real-time turnover | launched |
| S2 | prices: object.txt costs, store.c price formula, CHR adj, owners (shop_own.txt), races, discounts/sales, sell fraction | launched |
| S3 | light and food burn: fuel per game turn, town vs dungeon, turns per real second by depth, torch/lantern/oil capacity | launched |
| S4 | our runs: what was bought/sold and at what price (events store/message logs), mission notes, HANDBOOK advice, forum shopping advice | launched |
| X4 | Advisor: price table at CHR 4 by script from S2's formula; shopping lists | Advisor |

## Retrospective (2026-09-29)
- Formula-and-inputs from Clerks, table by script: S2's formula reproduced observed prices, so
  the computed table is trustworthy. S4 (our own logs) was the most practical source (routing bug,
  stock seen, money wasted); keep a "what did our runs actually do" Clerk in every applied study.
