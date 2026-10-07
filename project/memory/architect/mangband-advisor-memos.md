---
name: mangband-advisor-memos
description: Advisor memos written so far (memos/ dir) and how the forum was scraped (archive.org only, rate limits, broken Aug-2025 captures)
metadata:
  type: project
---
- 2026-09-26: `memos/2026-09-26-forum-distillation.md` (COMPLETE: Strategy, YASD, King Lounge, part of New Player + General Discussion addendum). Appendices with every finding and a post URL are in `memos/2026-09-26-forum/`. General IDs above about 2250 are spam. About 140 topics (mostly New Player) have only broken archive copies, so retry if the site returns.
- Forum scraping facts: mangband.org/forum was down all day (502). The Wayback Machine allows about 12 requests/min (faster → connection refused for a while). Many Aug–Oct 2025 captures return HTTP 500. Some pages exist only as print-view captures. The 2026 topic-count growth is spam. Watch out: `pkill -f`/`pgrep -f` match the invoking shell, so use a pidfile.
- Verified in 1.5 code: hounds are cleared only on down or recall arrival (dungeon.c:2211); summons are placed around the player; a level persists while occupied; a dungeon disconnect lingers ~16 s; also time bubbles (hitpoint_warn, xtra2.c:5164), 2-wide corridors (WIDE_CORRIDORS), ESC sends PKT_CLEAR to clear the queue, and a second WoR cancels the first; no_ghost "brave" option exists, but the user decided (2026-09-26) to keep ghosts ON because it mirrors live servers.

**Why:** the Architect acts on these memos; later Advisor sessions extend them. **How to apply:** start any follow-up forum work from the memo's Addendum D list. Related: [[mangband-roles]]
- 2026-09-27: the site came back but is flaky (~3/4 of requests 502, 20–40 s per page). A polite live fetch of the 143 archive-missing topics was running from the scratchpad (`live/livefetch.py`, 15 s gap, backoff). The memo got "Addendum 2 (interim)" from the first 21 topics; its notes are in `memos/2026-09-26-forum/live_batch1.md`. New Player Support (87 topics) was still pending. Don't put the user's email in the User-Agent.
- Full forum text is kept in `Advisor/data/forum/` (moved there from runs/forum, which was deleted 2026-09-27) (README there): raw/archive vs raw/live, with manifests and provenance-tagged corpus/*.txt built by build_corpus.py. Scratchpads get wiped when the session changes nodes, so keep valuable downloads in the project.
- 2026-09-27 13:40: the Advisor session is ending. Resume forum work from `Advisor/data/forum/STATUS.md` (finish the live fetch via `qsub tools/livefetch.qsub`, then distill Addendum 3).
- 2026-09-27 (later): forum work COMPLETE. The live fetch finished, the corpus has 905 topics in Advisor/data/forum/corpus, and memo Addendum 3 covers New Player Support + the remaining YASD. It corrects §4 (uniques are per character) and flags that the client sends realname@hostname (a privacy leak on the live server).
- 2026-09-27: the backlog of proposed Advisor studies (danger table, Borg, run post-mortem, message catalogue, skipped subforums, shops), plus the subagent-vs-main-chat proposal, is in `memos/2026-09-27-advisor-study-topics.md`.
- 2026-09-27 (night): danger-table study done: `memos/2026-09-27-danger-table.md` (§3 Pilot rules, §6 HANDBOOK corrections), data `Advisor/data/monsters/danger_table.csv` keyed by monster.txt N: idx. Status of acting on it: next_steps.md handoff.
- 2026-09-28: Borg study done: `memos/2026-09-28-borg.md` (group danger rule, depth-by-level doctrine question in §4). Status of acting on it: next_steps.md handoff.
- 2026-09-28: run post-mortem done: `memos/2026-09-28-run-postmortem.md` (both Dive03 deaths = escapes that never ran; group tiers tuned). Status: next_steps.md handoff.
- 2026-09-29: shops memo (`memos/2026-09-29-shops.md`) and message catalogue (`memos/2026-09-29-message-catalogue.md`, data `Advisor/data/messages/catalogue.csv`). Status: next_steps.md handoff.
- 2026-09-29: mission 9 replay (`memos/to_architect/2026-09-29-mission9-replay.md`) and versions/live-rules memo (`memos/2026-09-29-versions-and-forum-rules.md`). Status: next_steps.md handoff.
- 2026-10-03: game-state survey (`memos/2026-10-03-game-state.md`, requested by the user): §6 done in 771d141. Status: next_steps.md handoff.
- 2026-10-07: identify-and-sell, flavour-messages, mission 13 replay, warrior progression (`memos/2026-10-07-warrior-progression.md`). Status: next_steps.md handoff.
