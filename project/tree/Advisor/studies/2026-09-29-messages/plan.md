# Study: catalogue of server messages (backlog topic 4)

- **Status:** DONE 2026-09-29 (memo in ../../../memos/; note to_architect/2026-09-29-shops-and-messages.md).
- **Goal:** a verified catalogue of every player-facing message the MAngband 1.5 server can send,
  grouped by meaning (event), with a Python regex for each, so the Pilot's message classifier can
  recognise damage, status changes, drains, escape success/failure, summons, deaths, level changes
  etc. from text alone; plus the gaps between it and what the Pilot matches today.
- **Data:** `Advisor/data/messages/` — `extract_messages.py` → `server_messages.csv` (1352 calls);
  `log_messages.py` → `log_messages.csv` (1826 distinct messages seen in our runs, 18489 total).

## Assignments (pass 1)
| id | files | calls | status |
|---|---|---|---|
| M1 | melee1.c, melee2.c, monster1.c, monster2.c (monster attacks, spells, summons) | 279 | launched |
| M2 | spells1.c, spells2.c, xtra1.c, xtra2.c (effects, status on/off, drains, resists, exp) | 333 | launched |
| M3 | use-obj.c, x-spell.c, cmd5.c, cmd6.c, object1.c, object2.c, store.c (item use, shops) | 311 | launched |
| M4 | cmd1.c–cmd4.c (movement, doors, traps, stairs, pickup, commands) | 304 | launched |
| M5 | dungeon.c, util.c, party.c, files.c, generate.c, net-server.c, … (world, hunger, light, death) | 125 | launched |
| P2 | the Pilot's current message patterns, and their coverage of log_messages.csv | — | launched |
| X2 | Advisor: merge into catalogue.csv; coverage of log messages by catalogue regexes | — | Advisor |

## Pass log
- Pass 1 (2026-09-29): M1–M5 and P2 launched.

## Retrospective (2026-09-29)
- Script extraction first (1352 calls) + per-file-group Clerks with one event vocabulary worked:
  5 CSVs merged with zero bad regexes; coverage of our logs 18486/18489. The merge found 5
  catch-all regexes — test coverage with a nonsense probe.
- Clerks raised a false alarm (repeat packets) that one code read in the client settled: cheap to
  check the consumer side of any protocol claim.
