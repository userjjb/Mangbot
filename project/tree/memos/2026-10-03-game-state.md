# Memo: how game state reaches the Pilot and the Navigator, and how to make it reliable (Advisor → Architect, 2026-10-03)

**Asked by the user** ("The Navigator and Pilot seem to frequently be confused about the state of the
game … rather than play whack-a-mole … make a proper survey"). **Audit trail:**
`Advisor/studies/2026-10-03-state/` (dispatches G1–G5; `scratch/G1_packets.csv` lists every
state packet, `scratch/G3_state.csv` the Pilot's 48 state fields, `scratch/G5_incidents.csv` 71
incidents).

## How this was made

- **Five Clerks:** G1 server packets, G2 client and tool mode (checked against the user's three
  packet logs), G3 the Pilot's world model, G4 the Navigator's view (41 of its journal beliefs
  checked against the logs, plus real report text from Navigator transcripts), G5 every recorded
  state-confusion incident from 09-24 to 10-03.
- **Checks by the Advisor:** the claims marked **[code ✓]**.

## 1. The diagnosis in one paragraph

The server sends good, mostly numeric state; the client holds a correct, current copy. Errors
are added after that, in three ways:
1. **The Pilot acts on its own cached copies.** Inventory is re-read every 10 s or when a message
   from a short list arrives, and commands carry only a slot letter chosen from that cache.
2. **The Pilot rebuilds some facts from message text**, with no authoritative signal behind them:
   recall pending, standing on stairs, thefts, items destroyed.
3. **The Navigator plays mostly from memory:** 85–90% of its turns use `wait --brief`, which has no
   pack or equipment.

Each fix so far patched one site. The same classes came back:
- inventory identity (name lookup → stale letter → uses reported done that never ran);
- escape execution (3 fixes);
- unseen-attacker alarms (6 fixes);
- the Navigator selling unidentified items (4 times after the HANDBOOK warning; most recently
  Potions of Speed for 8 gold each).

**The cure is structural: read state from the client at the moment of use, resync on demand, and
confirm every effect.**

## 2. What the server sends, and what it doesn't (G1, G2)

| state | how it arrives | trust | trap |
|---|---|---|---|
| HP, SP, stats, AC, gold, speed, blows, hunger, conditions | indicator packets (ids 192–229), sent when changed | good | — |
| character level | indicator `[max, current]` | good | read `[1]`, not `[0]` (72ec098) |
| **depth** | indicator `depth`, dungeon level, **signed byte** (`tables.c:773`, `net-game.c:378`) **[code ✓]** | good 0–127 | **wraps in the wilderness** (negative world indices; the curses client showed "4650 ft", "−5350 ft"). It is also **the only signal that the level changed**, and it arrives after the new map |
| inventory and equipment | one packet per slot: letter, name text, tval, count, total weight. No sval, no inscription field (inscriptions and charges live inside the name) | good per slot | **removing an item resends every following slot, so letters shift silently.** Used-up slots arrive as "(nothing)". "You have no more X" arrives *before* the slot packets |
| position | cursor packet (`py, px` on the wire) | good | tool mode ignores the "cursor outside panel" packet, so `pos` can go stale |
| map | cell packets | good | old-level cells can arrive into the new level's memory around a level change (inferred) |
| monsters | map glyphs + the server's monster list (names and counts only: no position, health or sleep) | partial | monster HP numbers are never sent |
| floor item, resist/ability grid | sent, **stored by the client, but tool mode never emits them** | — | free to expose |
| recall pending, buff timers, light radius | **never sent** | — | only message text, or nothing |
| level feeling, day/night, thefts, items destroyed | message text only | — | must be parsed |
| repeated identical message | a repeat packet with no text; the client rebuilds the text | good | — |

**A full resync already exists.** The client's redraw request (`PKT_REDRAW`) makes the server mark
every stat, the map, the floor item and every inventory slot for resending (`net-game.c:1756-1764`)
**[code ✓]**. The client has `send_redraw()` (its Ctrl-R, `net-client.c:406`), but **tool mode
has no verb for it** (c-tool.c verbs: walk, pathfind, alter, examine, leave, clear, rest, eat, custom,
confirm, option(s), chat, suicide, minimap, plus the commands/status/inven/map queries) **[code ✓]**.

## 3. Where the Pilot goes wrong (G3, G5)

**By layer** (71 incidents): Pilot parsing ~15, Pilot logic ~13, Navigator memory ~12, wrong
assumptions about what the server sends ~10, Pilot staleness ~10.
**By state item:** inventory ~15, map and reachability of stairs ~11, monsters missed or phantom
~8, depth/level/recall depth ~7, store stock and prices ~6.

The root causes, each confirmed in code:
1. **Inventory cache.** The pack is re-read every 10 s or when `inven_dirty` is set by messages
   starting "You have", "You see", "You destroy", "You feel", or containing "no more" or "in your
   pack" (`world.py:143-147`) **[code ✓]**. Missed: "Your X was destroyed!" (fire, acid),
   "…was stolen!", "Your pack overflows!", "Your purse feels lighter." (mission 10's gold
   loss was Smeagol, at `dive04/events.jsonl:16369, 17676`; the Pilot has no handler) **[code ✓]**.
   The `inven` query reads the client's *current* copy; **the lag is entirely the Pilot's cache.**
2. **Letters chosen ahead of time.** Every item command carries a slot letter picked from that cache.
   Only escape and cure uses have the confirm-and-resend guard (`pending_use`); wear, wield,
   destroy, sell and eat don't.
3. **Recall pending is guessed, and wrongly cleared.** Any level change sets `recall_pending =
   False` (`world.py:138`) **[code ✓]**, but the server's countdown keeps running. A second read
   after taking stairs cancels the recall.
4. **Depth has two unreconciled sources** (the `level` event and the status `depth`), and "in the
   dungeon" is defined three ways (`in_dungeon`, truthiness of `w.depth`, `w.depth == 0`). They
   disagree in the wilderness, where the depth value also wraps.
5. **Monsters come from decoding map glyphs.** The server's monster list is only logged
   (`perception_gap`), so a mismatch never corrects anything.
6. **Stale docs:** HANDBOOK:302-303 still says `explore until=stairs` stops as soon as any stairs
   are known; the code now requires a reachable one (`pilot.py:235-237`) **[code ✓]**.

## 4. What the Navigator sees (G4)

- **It's accurate on HP, depth in feet and gold:** 30 of 41 checked beliefs were exactly right.
- **The errors:**
  - stale pack lines ("Pack now:" after a stack merge showed 7 Phase Door; there were 12);
  - wrong Pilot output ("level 18" before the level-up; "level 10" at clvl 8 after resurrection,
    since fixed);
  - **state the report never shows:** stat maximums (drains), maximum depth, recall pending, thefts.
- **`wait --brief` (85–90% of turns) has no Pack, Equipment or Recent messages**
  (`pilotctl.py:43, 62-78`) **[code ✓]**, so the Navigator plays the pack from memory.
- **Every report clears the news list** (`pilot.py:2486-2488`) **[code ✓]**, so a `status` piped
  through `grep Pack` silently eats the "Since last report" news.
- **The dive03 journal ends "Pilot crash, character state unknown".** The character had died; the
  Pilot exited without saying so (since fixed: it stays up after death).

## 5. The design: four rules (recommendations, most valuable first)

**Rule 1: the client's copy is the source of truth; never act on a cache.**
- **Resolve items at the moment of use.** Before any item command, run the `inven` query (it's
  local and cheap, so no network round trip). Find the item by name or inscription, send the
  command with that letter in the same tick, and log the name together with the letter.
- **Remove the 10-s pack cache** for decisions, or keep it only for display.
- Same for equipment and gold.

**Rule 2: resync on demand.** Add a `redraw` verb to tool mode (one line: `send_redraw()`), then:
- call it after every level change, resurrection or reconnect;
- call it after any message containing "Your " + (destroyed | stolen | overflows | purse);
- call it every ~2 min in town and whenever the Pilot's model and a fresh query disagree;
- take the snapshot only once the resent packets have landed (~0.2 s).

**Rule 3: confirm every effect.** Generalise `pending_use` from escapes and cures to every state
change the Pilot causes: use, wear, wield, take off, destroy, buy, sell, pick up, stairs and recall.
A command is "done" only when its confirming signal arrives (count line, slot packet, depth
indicator, gold change, recall message; see the message-catalogue memo §2). Otherwise it's
"pending", then "failed", and is never reported to the Navigator as done.

**Rule 4: one definition per fact; expose what the client already has.**
- **Depth:** the depth indicator only. Treat a value outside 0–127, or a wilderness map, as
  "wilderness" (for our test server, change the depth indicator from TINY to NORMAL so it can't
  wrap). Derive `in_dungeon` from it in one place.
- **Recall pending:** set on "The air about you becomes charged"; cleared only by "You feel
  yourself yanked …" or "A tension leaves the air around you". **Never cleared by a level
  change.** Also keep the read time, to show "recall in ≤ 34 turns".
- **Tool mode:** emit the floor item and the resist/ability grid (`PKT_OBJFLAGS`), both already
  stored by the client. Then Free Action, See Invisible and the resists are known facts, not guesses.
- **Monsters:** when the server's monster list names a monster the glyph decode doesn't show,
  treat it as present (the Yellow mold of mission 4), not as a log line.

**For the Navigator:**
- **Make `--brief` include a one-line pack summary:** key consumables by name with counts (CLW,
  CSW, CCW, Phase, WoR, Flasks, food), plus "recall pending", "max depth", stat drains as
  cur/max, and any theft or destruction since the last report. Never letters: the Navigator
  should name items.
- **Stop `report()` from clearing news on every call.** Keep a news sequence number and let
  `wait` return the news since the last `wait`.
- **Add "as of" ages** to anything that can be stale (pack, store stock).
- **Tell the Navigator, in its prompt, to sell only identified items or `{average}`/`{good}`
  items**, since the HANDBOOK warning didn't stick (4 repeats). Or have the shop goal refuse
  unknown flavours (potions, scrolls, wands) unless forced.

**Measurement (so this stops being whack-a-mole):** add a **state audit**. Every N s (and right
after each action), compare the Pilot's model with a fresh `status`/`inven` query, and log each
difference with its field. Run missions with `--pktlog` for ground truth. The audit log turns
"confusion" into a counted, field-by-field error rate, and shows whether each fix worked.

## 6. Quick wins (each small)

1. A `redraw` verb in tool mode, called after level changes and "Your …" item/gold messages.
2. Resolve item letters from a fresh `inven` query at use time.
3. Fix `recall_pending` (don't clear on level change).
4. Handlers for "…was destroyed!", "…was stolen!", "Your pack overflows!", "Your purse feels
   lighter." (mark the pack dirty and send news).
5. `--brief` gains the consumables line; `report()` stops eating news.
6. Fix the HANDBOOK:302-303 text.

## Coverage and gaps

- **Not tested live:** these are code reads and log analyses; nothing was run.
- **Inferred, not observed:** the depth wrap in the wilderness (from the packet sequence and the
  curses screens), the old-level map leaking into the new level, and the race between "You have …"
  and the slot packets.
- **No tool-mode packet log exists** (the three logs are a human on the curses client); one
  `--pktlog` mission would settle the inferred items.
