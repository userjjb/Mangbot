# Note: game-state survey memo (requested by the user)

- **To:** Architect
- **From:** Advisor
- **Date:** 2026-10-03

The user asked for a systematic survey of how game state reaches the Pilot and the Navigator,
instead of fixing confusions one at a time: `memos/2026-10-03-game-state.md`. It covers 71
incidents (09-24 → 10-03) traced to their layer, every state packet, and the Pilot's 48 state
fields.

The short version: the client's copy of the state is correct and current; the errors come from
the Pilot's caches, facts rebuilt from message text, and a `--brief` report with no pack.
Quick wins (§6), each small:
1. Add a `redraw` verb to tool mode. The server already supports a full resync (`PKT_REDRAW`,
   net-game.c:1756-1764; the client has `send_redraw()`). Call it after level changes and after
   "Your … destroyed/stolen/overflows/purse" messages.
2. Resolve item letters from a fresh `inven` query at the moment of use (it's local and cheap).
   Drop the 10-s cache for decisions.
3. `recall_pending` must not be cleared by a level change (world.py:138). The server's countdown
   keeps running, and a second read cancels it.
4. Handlers for "…was destroyed!", "…was stolen!", "Your pack overflows!", "Your purse feels
   lighter." (mission 10's lost gold was Smeagol).
5. `--brief` gains a consumables line (names and counts, recall pending, max depth, drains), and
   `report()` stops clearing news on every call.
6. HANDBOOK:302-303 is stale (`until=stairs` now requires a reachable stair).

Also suggested: generalise `pending_use` confirmation to every item, shop and stairs action; emit the
floor item and the resist grid from tool mode (the client already stores both); make the depth
indicator NORMAL on our test server (TINY wraps in the wilderness); and add a state-audit log
(model vs fresh query) to measure the error rate per field.
