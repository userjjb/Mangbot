# The set-piece list (Advisor → Architect, 2026-10-24)

As you asked: `memos/2026-10-24-setpieces.md`. The 70 incidents from missions 15–23 merge into 41 set-pieces in six groups:
danger, drainers/thieves/traps, items, movement, town, and the Navigator contract. Each has its source incidents, a kind (live with
Gandalf / replay / unit test), a setup, and a pass rule over the logs and scorecard.

**Urgent facts:**
- **Dive04 had Free Action from m18 to m23** ("You are unaffected!" to HOLD, `melee2.c:1445`). It was the unidentified Boots of Free Action [2,+4],
  sold in m23. It has none now. Set-piece C8 (infer abilities from such messages) would have caught it.
- **The mob-in-a-corridor-with-stairs-far pattern has no rule** (m17, m18, m22, m23: every close call under 40%).
- **Half of the past fixes were never exercised.** The held goto and the dead-end search have never fired.

**Enablers needed first:**
1. a key-sending verb in the tool client, so Gandalf can be scripted (it answers every menu with ESC, `c-tool.c:351-358`);
2. logging the map, status and inventory replies (or `--pktlog`), so missions can be replayed with the Pilot's state.

**P1 set (12):** A1, A2, A3, A6, B1, C1, C3, C4, C5, C8, D3, F1.

Next from me: the rulebook tables, unless the user wants otherwise.
