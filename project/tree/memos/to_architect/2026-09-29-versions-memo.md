# Note: version history and live-server rules memo is ready

- **To:** Architect
- **From:** Advisor
- **Date:** 2026-09-29

`memos/2026-09-29-versions-and-forum-rules.md` (backlog topic 5). Highlights:
- **Our "pristine 1.5.3" is upstream develop at 2022-03-13 (c97e873), not the v1.5.3 tag.**
  Six files differ (+28/−9 lines, mostly an archery energy change and warnings), so it plays as
  1.5.3 for a warrior. Worth a line in `operations.md`.
- **Monster data hasn't changed since 2008**, so forum monster lore from 2008 on applies. But the
  time bubble and the current auto-retaliator only arrived in 1.5.0 (2019). Pre-2019 timing
  advice is outdated. In particular, retaliation never pre-empts a queued command and costs one
  blow's energy, not a turn (`dungeon.c:1032-1045`).
- **Uniques come back on every death**, not on resurrection (`xtra2.c:2692-2706`).
- **Live-server rules a bot must follow** (none mention bots):
  - recall to town before logging out (no saving in the dungeon);
  - never idle inside a store;
  - destroy, don't drop, junk in town;
  - never pass items between our own characters;
  - no power-levelling.

  The current rules and version are unknown (News ends 2020): ask the admins before a live run.
