# Roles

Formalized by the user 2026-09-26. Every agent working on this project should know which role it
is in and stay inside it. Until now the Architect and Navigator roles were played by the same chat
at the same time; they are now separate.

| Role | Who | Does | Does not |
|---|---|---|---|
| **Pilot** | `github/tools/pilot/pilot.py` (Python daemon that owns the client) | Plays second to second: reflexes (flee, eat, rest, fight what's adjacent, idle recall) and carries out the current goal. Reports done/failed/attention. | Set strategy. |
| **Navigator** | A Claude subagent (to be built by the Architect) | Strategic planner: reads the Pilot's reports and logs, sets goals and orders through `pilotctl`. Knows the game from `HANDBOOK.md` (and `notes_players.md`), not from the code. | Read or change the Pilot's code. |
| **Architect** | Claude in a main chat with the user | Meta work on the whole system: codes and improves the Pilot and the C client, writes the Navigator subagent and its handbook, maintains the notes. | Play the character as Navigator in the same session. |
| **Advisor** | Claude in a main chat with the user | Reads code, logs, docs and notes, and writes memos for the Architect. | Modify the Pilot, the Navigator, or the client. |
| **Clerk** | A Claude subagent of the Advisor (`Advisor/.claude/agents/clerk.md`, Sonnet) | Studies one bounded piece of an Advisor study and returns a *dispatch* (findings with evidence) that the Advisor combines. Method: `Advisor/METHOD.md`. | See the big picture, modify anything but its dispatch, or talk to the user. |

Advisor memos go in `memos/` (one Markdown file per memo, dated, addressed to the Architect).
The terms in older notes map as follows: "agent" in `design_pilot.md` and `next_steps.md` means
the Navigator; "the builder" / "the agent who built this" means the Architect.

**Where knowledge lives.** Everything any agent needs is in this directory (`next_steps.md` with
the Architect handoff, `operations.md`, `notes_players.md`, `design_pilot.md`,
`github/tools/pilot/HANDBOOK.md`, `memos/`). The Claude memory directory is loaded only by main
chats (Architect/Advisor) and holds pointers here plus the user's preferences, never substance
that others need. **Main chats started in this directory are the Architect; chats started in `Advisor/` are the Advisor** (a separate Claude Code project with its own memory, forked from the Architect's on 2026-09-27). Whoever changes the
project notes (adds, renames or restructures a document or section, updates the handoff, or adds or
retires a critical gotcha) must, in the same session, update the main chats' memory pointers to
match. Memory must never hold substance that isn't in these files.

