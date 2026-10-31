---
name: mangband-advisor-memos
description: Where the Advisor's memos are (memos/, memos/to_architect, memos/to_advisor; list them, don't log them here) and the forum-scraping lessons worth keeping
metadata:
  type: reference
---
The Advisor's memos are files, not memory: `/projectnb/jbrcs/mangband/memos/` (studies, dated `YYYY-MM-DD-slug.md`),
`memos/to_architect/` (to me; the inbox watcher announces new ones) and `memos/to_advisor/` (mine). `ls -t` them for
the latest; docs/process.md describes the conventions, and the Advisor's own STATUS.md (Advisor/) its current work.
This file used to log each memo by hand and stopped at 10-26: don't restart that log (refactor-candidates B15).

Lessons from the 09-26/27 forum distillation (`memos/2026-09-26-forum-distillation.md`) still worth knowing:
- Forum scraping facts: mangband.org/forum was down all day (502). The Wayback Machine allows about 12 requests/min (faster → connection refused for a while). Many Aug–Oct 2025 captures return HTTP 500. Some pages exist only as print-view captures. The 2026 topic-count growth is spam. Watch out: `pkill -f`/`pgrep -f` match the invoking shell, so use a pidfile.
- Verified in 1.5 code: hounds are cleared only on down or recall arrival (dungeon.c:2211); summons are placed around the player; a level persists while occupied; a dungeon disconnect lingers ~16 s; also time bubbles (hitpoint_warn, xtra2.c:5164), 2-wide corridors (WIDE_CORRIDORS), ESC sends PKT_CLEAR to clear the queue, and a second WoR cancels the first; no_ghost "brave" option exists, but the user decided (2026-09-26) to keep ghosts ON because it mirrors live servers.

**Why:** a memo log in memory goes stale and duplicates memos/. **How to apply:** look in memos/ for any memo; keep
only durable lessons here. Related: [[mangband-roles]], [[mangband-project-map]]
