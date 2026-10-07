# Memo: server message catalogue (Advisor → Architect, 2026-09-29)

**Backlog topic 4 and the Architect's request of 2026-09-29.** Two needs: (a) confirming escapes
and cures, and spotting commands that were refused; (b) unseen-attacker false alarms.
**Data:** `Advisor/data/messages/`: `catalogue.csv` has 1473 rows (text, event, audience, relevance,
regex, condition with file:line); `server_messages.csv` is the raw extraction; `log_messages.csv`
holds our logged messages; `unseen_check.csv` tests the Pilot's regexes (see the README).
**Audit trail:** `Advisor/studies/2026-09-29-messages/`.

## How this was made

- **Extraction:** a script pulled all 1352 message calls from `src/server/*.c`.
- **Five Clerks** catalogued them file group by file group; every regex compiles.
- **A sixth Clerk (P2)** listed every message pattern the Pilot uses.
- **Checks by the Advisor:** coverage of our logs by script, the Pilot's regexes against the
  catalogue by script, and the claims marked **[code ✓]** in the source.
- **Coverage:** the catalogue explains **18,486 of the 18,489 messages** in our runs (the only misses
  are three "picks up" lines), after dropping 5 catch-all chat regexes.

## 1. Facts that shape any message classifier

1. **Text is the only signal.** Almost every message has type 0; only chat types differ (util.c).
2. **Repeated lines do arrive.** An identical consecutive message is sent as a repeat packet with
   no text (`util.c:1907-1911`), but the client rebuilds it and emits a normal `message` event
   (`net-client.c:1807-1820`, `c-xtra2.c:306-308`) **[code ✓]**.
3. **Unseen monsters are "It".** The server names a monster the player can't see "It" or
   "Something". **An unseen monster's misses print nothing** (`melee1.c:1313-1320`) **[code ✓]**.
4. **"Mumbles" means you are blind.** "<monster> mumbles." is the text when the *player* is blind
   (`melee2.c:445`) **[code ✓]**, not when the caster is out of view. It stands for about 40
   different spells. Slow, Hold, teleport-to, teleport-away, forget, blink and haste have no blind
   variant.
5. **Status messages appear only on a change.** Re-applying a status is silent; only stun and cut
   have "worse" steps; partial recovery is silent (M2).
6. **"You are hit by …" appears only while you are blind.** Projection damage messages are sent
   only when blind (`spells1.c:3534-3549`) **[code ✓]**.
7. **Some texts are shared by different causes:**
   - "You resist the effects!" has 7 sources (resists and saving throws alike).
   - "A small dart hits you!" comes from four traps: slow, STR, DEX and CON drain
     (`cmd1.c:1090-1138`) **[code ✓]**.
   - "You are enveloped in a cloud of smoke!" is the summon trap or summon chest, the one that
     killed Dive03 (`cmd1.c:1049`, `cmd2.c:423`).

## 2. Need (a): confirming escapes and cures

**The rule: an escape that teleports prints nothing to the user.** `teleport_player()` sends no
message (`spells1.c:167ff`), and the Phase Door scroll is just `teleport_player(10)`
(`use-obj.c:795-800`) **[code ✓]**. The staff's "<Name> teleports away!" goes to *other* players
only. So:

| Item | It worked if you see | It didn't if you see |
|---|---|---|
| Phase Door, Teleportation (scroll) | "You have N Scrolls of …" / "You have no more …" **and** your position changed | "You can't see anything." · "You have no light to read by." · "You are too confused!" · "You cannot read scrolls!" (no scroll used, no turn used) |
| Staff of Teleportation | position changed; "You have N charges remaining." if identified | "You failed to use the staff properly." (turn used, charge kept) · "The staff has no charges left." · works blind and confused, but confusion halves the skill |
| Teleport Level | "You sink through the floor." / "You rise up through the ceiling." then a level change | "Nothing happens." (arena/ironman) |
| Word of Recall | "The air about you becomes charged..." (then activation **15–34 player turns** later: "You feel yourself yanked upwards!" / "downwards!") | **"A tension leaves the air around you..." = you just cancelled an active recall** · the read-blocks above · activation is held while you're in a store |
| CLW / CSW / CCW | "You feel much better." (only if HP < max) plus "You can see again.", "You feel less confused now.", "You are no longer poisoned/stunned/bleeding." (each only if it ended) | at full HP with no ailment: **only the count line**. That's not a failure |
| Healing / *Healing* | "You feel very good." + the same "off" lines | as above |
| Boldness | "You feel bolder now." only if afraid | silent when not afraid |
| Heroism / Berserk | "You feel like a hero!" / "You feel like a killing machine!" (only if not already active); "You feel bolder now." if afraid | already active: no hero line |
| Cure/Neutralize Poison | "You are no longer poisoned." only if poisoned | silent otherwise |

- **For every read or quaff, the count line is the one universal acknowledgement.** Plus a
  position change for teleports.
- **Not in 1.5.3:** Deep Descent does not exist. Scroll of Teleportation is in no normal store's
  table, only the ironman table (`init2.c:1510`), so only the Black market can have one (see the
  shops memo).
- **Refused commands that don't cost a turn:** the four read-blocks above; "You are too afraid to
  attack <mon>!"; "There is a wall/rubble blocking your way."; "You have no room for …".
  **Commands that turn into something else:** "There is a monster in the way!" means your
  open/close/tunnel became an attack (M4).

## 3. Need (b): the unseen-attacker regexes

Tested by script against every catalogue text in the "It/<monster>" form, and against our logs
(`unseen_check.py`).

**`RE_ATTACK` misses visible ranged attacks.** It requires " you" after the verb (world.py:71-73),
but the server writes "The Kobold archer fires an arrow!", "The Dark hound breathes darkness.",
"… casts a magic missile." with no "you". That's 29 distinct logged lines, which never update
`hits_taken`/`last_hit_t`. `last_hit_t` gates the unseen-HP heuristic, so damage from a *visible*
archer or breather can later read as "HP falling with nothing hitting us".
**Likely the main cause of the 09-27 false alarms.**

**`RE_UNSEEN`** catches 148 of 188 monster-on-player texts in the unseen form. The real attacks it
misses:
- **Melee:** "It drools on you.", "It releases spores at you."
- **Ranged:** "It hurls a boulder at you!", "It makes a strange noise." (the blind or unseen
  arrow/bolt form)
- **Spells:**
  - "It invokes a darkness storm." / "… a mana storm."
  - "It gestures fluidly." (water ball), "It gestures in shadow." (darkness)
  - "It looks deep into your eyes." (**Brain Smash**), "It gazes deep into your eyes." (Mind Blast)
  - "It stares deep into your eyes!" (**Hold**), "It creates a mesmerising illusion." (Conf)
  - "It screams the word 'DIE!'" (Cause Mortal Wounds), "It draws psychic energy from you!"
  - "It makes a high pitched shriek.", "It gestures at your feet." (Teleport Level)
- **Other:** "It teleports you away.", "Something makes you very sleepy!"

It also matches three that aren't attacks on you: "It concentrates on its body/wounds." (the
monster hastes or heals itself) and "It commands you to return." (teleport-to, already handled).
The rest of the 40 misses are harmless begging and insults and dead `XXX` placeholders. Suggested
regex: see `unseen_check.csv`. The simplest robust form is: a message beginning "It " or
"Something " whose event in `catalogue.csv` is `attack.*`, `spell.*`, `stat.*`, `exp.*`,
`escape.teleport.forced` or `summon`.

**`RE_HURT_OTHER`** is an unanchored substring regex.
- **It over-matches** in our logs: "Your light is growing faint." (45 times), "…makes a high
  pitched shriek." (via "pit"), "Pitiful-looking beggar", "Cutlass", "Slow Poison".
- **It misses** non-monster HP loss: earthquake ("You are crushed…", "You are bashed by rubble!"),
  and "You are getting weak from hunger!" / fainting from hunger. Stun and cut steps also appear
  without the words it looks for ("You have been stunned.", "…given a deep gash.").
- **Suggestion:** anchor each alternative to the catalogue's trap/damage/status texts, e.g.
  `^(A small dart hits you!|You fall into a (spiked )?pit|You are impaled|You have been given a|
  You are (poisoned|getting weak)|You are (severely )?crushed|You are bashed by rubble|…)`.

**Other Pilot pattern issues** (P2):
- "You have killed it." (an unseen kill) is missed by the Hunt-done check and by `fight_t`.
- "There is a closed door blocking your way." and "There is a tree blocking your way." would mark
  the tile as a permanent wall (mover.py:316); neither is in our logs yet.
- The dig-failure check (mover.py:230) has an "impossible" alternative that matches no server
  message.

## 4. Recommendations: Pilot

1. **Confirm escapes by count line + position** (the table in §2). Treat "A tension leaves the air
   around you..." as *cancelled* recall, and never read a second Word of Recall while one is active.
2. **Fix `RE_ATTACK`:** accept visible ranged and breath texts without " you" (e.g.
   `^The .+? (fires an arrow|fires a bolt|breathes \w+|casts a .+?)[.!]$`). Set `last_hit_t` on
   them.
3. **Replace `RE_UNSEEN` and `RE_HURT_OTHER` with catalogue lookups:** load `catalogue.csv` and
   classify each message by the first matching regex among `audience=self` rows. Take the event
   from that row (a `pilot_relevance` filter keeps it small). The catalogue has 495 high-relevance
   rows.
4. **Treat silence correctly:** a potion at full HP says nothing; an unseen monster's miss says
   nothing; statuses speak only on change. Check the count line and state, not an effect message.

## Coverage and gaps

- **Covered:** all server message calls (`src/server/*.c`), including runtime-built texts (blow
  verbs, feeling arrays, store comments); dead code is marked `relevance=none`.
- **Not covered:** the client's own messages (`src/client/`), and texts built from
  `monster.txt`/`object.txt` names beyond placeholders.
- **Duplicates:** some catalogue rows overlap across Clerks, and 475 logged messages match more
  than one event, mostly harmless duplicates (e.g. `level.feeling` vs `level.feeling.0`). A
  classifier should take the most specific.
