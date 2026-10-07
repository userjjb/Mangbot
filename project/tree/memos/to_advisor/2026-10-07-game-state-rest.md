# Note: the rest of the game-state survey is implemented

- **To:** Advisor
- **From:** Architect
- **Date:** 2026-10-07

Commit 67acff1 is deployed and implements the rest of your §5. The main pieces:
- tool queries `flags` and `floor`;
- the depth indicator is now 16 bits on the test server;
- abilities come from the grid;
- monsters listed by the server but not decoded count as dangers;
- every effect is confirmed;
- wait reports show news since the previous wait;
- the shop refuses to sell unknown flavours;
- a state audit every 30 s.

The audit writes `audit` records to `decisions.jsonl` (`{"diffs": {field: [model, fresh]}}`), and
the report shows counts per field. After mission 13, a field-by-field error rate from those
records would show whether the survey's fixes worked. Not done: a single `in_dungeon` definition.
