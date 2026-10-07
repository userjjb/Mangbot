---
name: mangband-territory
description: What the Advisor may modify (Advisor/ and its own memory) vs the Architect's domain; the memos/to_architect and memos/to_advisor suggestion channels
metadata:
  type: feedback
---
The user set these territory rules on 2026-09-27:
- **The Advisor (and its Clerks) may modify** only `/projectnb/jbrcs/mangband/Advisor/**` and this memory (`~/.claude/projects/-projectnb-jbrcs-mangband-Advisor/memory/`).
- **Everything else under `/projectnb/jbrcs/mangband/` is the Architect's**, and so is its memory (`~/.claude/projects/-projectnb-jbrcs-mangband/memory/`). That includes roles.md, notes_players.md, the HANDBOOK, github/ and runs/. Reading is fine.
- **The shared exception is `memos/`**: finished memos go in `memos/`; suggestions for changes in the Architect's domain go in `memos/to_architect/` as a file; the Architect's suggestions to me arrive in `memos/to_advisor/`. Check `to_advisor/` at the start of each session.

**Why:** two agents editing the same notes or each other's memory causes conflicts. **How to apply:** before writing any file, check it's under Advisor/, memos/ (for a memo or suggestion), or my memory. Otherwise write a suggestion instead. The "SYNC RULE" of updating main chats' memory now means *my* memory only; propose Architect-memory changes as suggestions. **Data I fetch or generate goes in `Advisor/data/<name>/`** (the user's rule). The forum corpus is in `Advisor/data/forum/` (copied from `runs/forum/` on 2026-09-27; the Architect was asked to delete the old copy). Related: [[mangband-roles]]
