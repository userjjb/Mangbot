# Shared context for the Borg study (every Clerk reads this first)

## What we are doing
The MAngband project builds an automated player for **MAngband 1.5.3**, a real-time multiplayer
Angband variant. Two parts:
- the **Pilot**, a Python program that plays second to second (`/projectnb/jbrcs/mangband/github/tools/pilot/`):
  it reads the screen and game messages, keeps a map, and runs reflex rules (arrival check, danger
  check, flee, rest, fight by standing still with auto-retaliate, stair-scum dive, shop, pick up);
- the **Navigator**, a Claude subagent that sets strategy (where to go, what to buy, depth limits,
  orders like `flee_hp`, `max_depth`, `free_action=yes`) by talking to the Pilot every few minutes.
We are studying the **Angband Borg** (an automated player built into vanilla Angband 4.2.x, source
`/projectnb/jbrcs/mangband/Advisor/data/borg/angband-src/src/borg/`) to learn which of its mechanisms
we should copy, adapt, or avoid.

## How MAngband differs from the game the Borg plays (keep in mind; don't research it)
- **Real time:** the game does not wait for the player. Monsters act on their own energy clock; a slow
  decision costs turns. The Borg assumes the game pauses while it thinks.
- **Multiplayer:** levels are shared and persist while any player is on them; other players can
  change things; a level is regenerated only when everyone has left.
- **Connected stairs:** taking `>` puts you on a `<` (and vice versa), so the way back is underfoot on
  arrival. Stair-scumming (`<` `>` repeatedly) is how our character dives.
- **Auto-retaliate:** the server attacks an adjacent monster for you when you do nothing.
- Our character: a throwaway Half-Orc Warrior (no spells), diving 0–1500 ft (dungeon levels 0–30).
- Our current danger rules and a verified monster danger table are described in
  `/projectnb/jbrcs/mangband/memos/2026-09-27-danger-table.md` (read §1 and §3 only if useful).

## What every Borg dispatch must contain
- The mechanism as the code implements it: functions, the order things happen, **exact thresholds and
  formulas** with `file:line` citations. Quote short code where a formula matters.
- Where the Borg's config (`borg.txt`) or constants change the behaviour.
- A section **"Transfer notes"**: for each mechanism, one or two lines on whether it would work for a
  real-time, multiplayer, turn-uncontrolled bot (tag these [INFERRED]). Keep this short; the Advisor
  does the full mapping.
- Game-rule claims (e.g. "monster X breathes Y") are about vanilla 4.2 and may not match MAngband 1.5;
  say so rather than checking them, unless the brief asks.
- Open the actual code before describing a specific function; don't infer a function's behaviour
  from its name or a comment alone.
