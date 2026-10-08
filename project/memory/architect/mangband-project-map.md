---
name: mangband-project-map
description: Where everything about the MAngband project lives (project docs are the source of truth; memory only points)
metadata:
  type: reference
---
All substance is in `/projectnb/jbrcs/mangband/` (moved out of memory 2026-09-27):
- `next_steps.md`: **start with the "ARCHITECT HANDOFF" section** (state, operating rules, next steps).
- `operations.md`: environment, test server, characters (credentials in `runs/private/`), tool-mode client facts, verified server behaviour, live server, user decisions, tooling gotchas.
- `notes_players.md`: game knowledge (docs digest, observed human play, the user's advice).
- `design_pilot.md` + `github/tools/pilot/HANDBOOK.md`: Pilot architecture and features; `roles.md`; `memos/` (Advisor memos); `notes_merge.md` (protocol survey).

- `github/tools/observe/watch.py` (the user's live viewer + `!`/`?` notes), `notes.py` (notes with the play); `github/tools/snapshot.sh` + `github/project/` (whole-state snapshot for the public repo https://github.com/userjjb/Mangbot); how-tos in `operations.md`.

Critical, easy to forget: update the Pilot only with `tools/pilot/restart.sh NICK` (never pkill it mid-move: crashes the test server); `module load python3/3.12.4`; `rm` is `rm -i` in the Bash tool.

**Sync rule (user, 2026-09-27):** project docs hold the substance, memory only points to them. Whenever you change the project notes (add, rename or restructure a doc or section, change the handoff, add or retire a critical gotcha), check this memory in the same session and update any pointer, file or section name, or gotcha that no longer matches. Never leave substance only in memory; if you learn something, write it in the project docs first, then point to it.

**How to apply:** read the handoff first; at the end of every session, re-read these memory files against the docs you changed. Related: [[mangband-roles]]
