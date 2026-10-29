# attic

Retired scripts and data, kept for reference; nothing imports them. Moved here in session 10 (2026-10-29,
docs/refactor-candidates.md group C).

| file | was | why retired |
|---|---|---|
| `replay_group.py` | `pilot/` | one-off script that tuned the group-danger rule against Dive03's logs (09-28); no caller |
| `danger_table.csv` | `pilot/` | the 09-27 hand danger table; the Pilot reads `rulebook/monsters.csv` (which merged it) and no longer falls back to this (C9). replay_group.py reads it by its old absolute path |
| `latency.py` | `observe/` | report-to-action latency per mission; no caller since m22; the scorecard's group E covers it |
