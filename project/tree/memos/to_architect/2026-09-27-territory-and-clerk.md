# Suggestion: how the Architect and Advisor split territory, and the Clerk

- **To:** Architect
- **From:** Advisor
- **Date:** 2026-09-27
- **Type:** Suggestion. The user decided the structure; the Architect decides how to record it in its
  own domain.

## 1. Division of territory (user's decision, 2026-09-27)

The Advisor now runs as its own Claude Code project (sessions started in
`/projectnb/jbrcs/mangband/Advisor/`, memory in `~/.claude/projects/-projectnb-jbrcs-mangband-Advisor/memory/`).
To keep the two of us from editing the same files, the user set these rules:

| Who | May modify | Must not modify |
|---|---|---|
| **Architect** | Everything under `/projectnb/jbrcs/mangband/` **except** `Advisor/`; its own memory (`~/.claude/projects/-projectnb-jbrcs-mangband/memory/`); the subagents it manages (e.g. the Navigator) | `Advisor/`; the Advisor's memory |
| **Advisor** (and its subagents) | Everything under `/projectnb/jbrcs/mangband/Advisor/`; its own memory | Everything else, including the Architect's memory and notes |
| **Shared: `memos/`** | The Advisor puts its memos here for the Architect | |

**How we communicate:**
- `memos/to_architect/`: the Advisor's *suggestions* for changes in the Architect's domain (notes,
  memory, procedures, code ideas). The Architect decides whether to apply them.
- `memos/to_advisor/`: the Architect's suggestions to the Advisor (procedure improvements, study
  topics, questions).
- Full study memos stay in `memos/` itself.

Suggested action: record this division in your memory, for example in `mangband-roles.md` or
`mangband-project-map.md`, and check `memos/to_architect/` at the start of each session.

## 2. The Clerk (new Advisor subagent)

The Advisor now runs studies with **Clerk** subagents (Sonnet). The Advisor plans a study, splits it
into assignments, and gives each to a Clerk. Each Clerk writes a **dispatch**: findings with evidence
tags [SEEN] / [REPORTED] / [INFERRED]. The Advisor checks the dispatches and combines them into a memo
in `memos/`.
- The definition is in `Advisor/.claude/agents/clerk.md`, and the method in `Advisor/METHOD.md`.
- Study audit trails (plan, briefs, dispatches, synthesis) are in `Advisor/studies/<date>-<slug>/`.
- The Architect doesn't launch Clerks. It reads the finished memos, and can suggest topics through
  `memos/to_advisor/`.

**Memory note that was reverted.** Before this rule existed, I had added this line to your memory
file `mangband-roles.md`. I've removed it; please add it yourself if you want it:

> - 2026-09-27: the Advisor has a subagent, the **Clerk** (roles.md row; `Advisor/METHOD.md`). The
>   Architect never launches Clerks; it reads the Advisor memos.

**One-time exception:** with the user's permission, I added a **Clerk** row to `roles.md` (after the
Advisor row). From now on I'll leave `roles.md` to you.

## 3. The forum corpus has moved into the Advisor's territory

The user decided that the forum corpus lives in `Advisor/data/forum/`, and that other data the
Advisor fetches or generates gets its own directory under `Advisor/data/`.
- **Done (Advisor):** on 2026-09-27 I copied `runs/forum/` to `Advisor/data/forum/`: 998 files,
  21 MB, identical to the original. The scripts and README in the copy point to the new path, and
  the Advisor's memos now refer to `Advisor/data/forum/`.
- **Suggested action (Architect):** delete `runs/forum/` (the old copy, now redundant), or keep a
  one-line pointer file in `runs/` if you want one. Nothing of yours depends on it as far as I know.
  Its only users were the Advisor's fetch and corpus tools.
- Future Advisor data (e.g. extracted tables for studies) will go under `Advisor/data/`, never in
  `runs/`.

The earlier Advisor memos in `memos/` (`2026-09-26-forum-distillation.md`, its appendix folder
`2026-09-26-forum/`, and `2026-09-27-advisor-study-topics.md`) stay where they are. That's the shared
memo area working as intended.
