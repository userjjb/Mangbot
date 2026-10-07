# project/: the whole working state, snapshotted

The code lives in this repository's root (MAngband 1.5.3 with a headless "tool mode" client, and
`tools/`: the Pilot, its HANDBOOK, the observer). The project around it lives outside the repo on the
SCC, in `/projectnb/jbrcs/mangband/`. `tools/snapshot.sh` copies that state here before a commit,
so any commit can restore any earlier state.

| here | restores to | what |
|---|---|---|
| `tree/` | `/projectnb/jbrcs/mangband/` (minus `github/`) | handoff (`next_steps.md`, read first), `operations.md`, `notes_players.md`, `roles.md`, `design_pilot.md`, the Advisor's memos (`memos/`), the Advisor project (`Advisor/`: CLAUDE.md, METHOD, studies, scripts, derived data), the Claude agents and hooks (`.claude/`), small run state (`runs/`: navigator journals, orders, flavour table, Pilot decision logs), test-server config |
| `memory/architect/` | `~/.claude/projects/-projectnb-jbrcs-mangband/memory/` | the Architect's Claude memory |
| `memory/advisor/` | `~/.claude/projects/-projectnb-jbrcs-mangband-Advisor/memory/` | the Advisor's Claude memory |
| `claude/global-CLAUDE.md` | `~/.claude/CLAUDE.md` | the user's global instructions |

Not included (public repo): passwords (`runs/private/`), game savefiles, server logs and crash dumps,
the forum corpus and other third-party source copies, screen recordings, raw event streams, files over
5 MB. To resume from a commit: check it out, copy `tree/` back over the project directory (create
`runs/private/` with `tools/shopcat/newchar.py` for new characters), and copy the memory directories back.
