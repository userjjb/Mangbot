---
name: mangband-inbox-watcher
description: Start the Architect inbox watcher first thing every session and restart it whenever it ends; otherwise Advisor memos sit unread
metadata:
  node_type: memory
  type: feedback
  originSessionId: 4e413cd8-6b12-4ad1-920d-a5c24891ab78
  modified: 2026-10-07T18:28:32.791Z
---

Start `.claude/hooks/inbox.sh watch memos/to_architect` (Bash, run_in_background, timeout 600000) as the first action of every session, and restart it each time it exits (it lasts at most 10 minutes, and exits at once while a memo is unread, so mark memos read first).

**Why:** on 2026-10-07 the identify-and-sell memo sat unread for about an hour. The watcher wasn't running, and the post-Bash hook only fires on my own commands. The user asked why it didn't trigger me.

**How to apply:** at session start, run the watcher before anything else. While idle between missions, keep restarting it when its task ends. Related: [[mangband-roles]], [[mangband-next-steps]]
