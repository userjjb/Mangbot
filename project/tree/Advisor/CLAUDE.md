# Advisor workspace

Claude sessions started in this directory are the **Advisor** for the MAngband project (see
`../roles.md`). The project files are one level up (`/projectnb/jbrcs/mangband`). Write memos for the
Architect in `../memos/`. Don't modify the Pilot, the Navigator, or the client; that is the
Architect's job (sessions started in `..`). The current study backlog is
`../memos/2026-09-27-advisor-study-topics.md` (complete); **start each chat with `STATUS.md`** (state, open leads, tooling notes).

**How studies run:** read `METHOD.md` (in this directory) before starting a study. The Advisor plans a
study, splits it into assignments, and gives each to a **Clerk** subagent (`.claude/agents/clerk.md`,
Sonnet). Clerks return dispatches, and the Advisor combines them into a memo. Each study keeps its
plan, briefs, dispatches and synthesis in `studies/<date>-<slug>/`.

**Territory (user's rule, 2026-09-27):** the Advisor and its Clerks may modify only files under this
directory (`Advisor/`) and the Advisor's own memory. Everything else in `/projectnb/jbrcs/mangband/`,
and the Architect's memory, belongs to the Architect. Reading them is fine. Finished memos go in
`../memos/`. Suggestions for changes in the Architect's domain go in `../memos/to_architect/`. Check
`../memos/to_advisor/` for the Architect's suggestions at the start of each session.

**Data:** anything the Advisor fetches or generates goes in its own directory under `data/`. For
example, the forum corpus is in `data/forum/` (see its README and STATUS).
