# Memo: what the MAngband forums teach about survival and diving

- **To:** Architect
- **From:** Advisor
- **Date:** 2026-09-26
- **Status:** Complete. Sections 1–7 cover Strategy, Yet Another Stupid Death (YASD), The King Lounge
  and part of New Player Support. The **Addendum** at the end covers General Discussion and
  **corrects rules P6 and P14**. Read it before acting on §2. **Addendum 2** and **Addendum 3**
  (2026-09-27) add the topics fetched from the live site, which makes coverage complete. **Addendum 3
  corrects §4 on uniques and flags a privacy leak.** An Erratum on cure potions and resurrection
  cost sits between Addenda 2 and 3.

## How this was made

The live forum (mangband.org/forum) was down all day (HTTP 502), so everything was read from
Wayback Machine captures (mostly 2021 and 2025; indexes up to 2026-06). The 2026 growth in General
Discussion (552 → 1341 topics) is pharmacy spam and was filtered out. Three subagents each read one
corpus in full. Their detailed notes are in `memos/2026-09-26-forum/`:
- `strategy.md`: 42 topics, including PowerWyrm's death-dump critiques and a catalogue of about 70 deaths;
- `yasd.md`: 142 topics, with a catalogue of 133 deaths;
- `king_newplayer.md`: 26 + 12 topics.

Every claim in those files carries a post URL. I checked the mechanics that matter most against our
1.5 server source (**[code ✓]** below).

**Caveats.**
- Most posts date from 2002–2013, when the server ran versions 0.7 through 1.1.x. Game mechanics are
  largely the same, but server-specific quirks may have changed. Anything not marked [code ✓] is
  forum lore.
- Almost every recorded death is a clvl 25–50 character at 1000–6350 ft, and few are warriors. The
  lessons are about *kinds* of danger that also apply shallower, but there is little direct data on
  the 0–1000 ft band our throwaway will spend most of its time in.

URLs below are forum links: `https://www.mangband.org/forum/viewtopic.php?p=N` (post) or `?t=N`
(topic). Since the site is down, prefix them with `https://web.archive.org/web/2025/` to read them.

---

## 1. The five things that matter most

1. **Arriving on a new level is the most dangerous moment of play.** This holds for stairs, recall,
   teleport level, and even a long teleport. It is the most common death in YASD, and it kills winners
   too. Hounds (`Z`) are the top killer of the whole forum. They appear at our depths. *(Corrected
   2026-09-27 from monster.txt, see the Erratum at the end: light, dark and clear hounds at 750 ft;
   fire, cold and energy at 900; earth, air and water at 1000; vibration and nexus at 1350; gravity
   at 1750. Water hounds breathe acid, air hounds poison, earth hounds shards.)* **The server protects you
   only when you arrive going *down*.** On `LEVEL_DOWN` or `LEVEL_RAND` (recall, teleport level) it
   deletes every non-unique `Z` within 20 squares of you. On `LEVEL_UP` it does nothing, "we don't want
   to make stair scuming safe" **[code ✓ `server/dungeon.c:2211-2246`]**. Veterans' doctrine: at depth,
   *going up is Russian roulette*. Recall to a little *above* the target depth and then take only `>`.
   (p=6185, p=9415, t=1249&start=15; YASD p=601, p=605, p=2433, p=5215.)

2. **Summoners, not melee monsters, turn a fight into a death.** Summons are placed next to the
   *player*, not the caster **[code ✓ `melee2.c:438`, summon position = `p_ptr->py/px`]**. That is why
   the standard answer is to fight in a one-square-wide corridor or a spot with few open neighbours.
   Many of the summoners that killed people look harmless: a white `p`, Mystics and Grand Master
   Mystics, Silent Watchers, Death Knights, draconic `Q`s, druids (earth hounds at 900 ft), and a
   Scroll mimic. Summons also *stay* after the summoner dies and killed a bystander character. (Strategy
   p=5700, p=8569; YASD p=5077, p=5467, p=5152, p=9418; King p=9270, p=6002.)

3. **Escape rather than heal when the incoming damage beats the heal.** The most common fatal mistake
   in the death threads is quaffing CLW, CSW or CCW (about 15, 18 and 27 HP) while taking 100+ per
   turn. Each quaff costs a turn. CCW is a *status* cure (blind, confused, poisoned, stunned), not a
   heal. Two refinements for the Pilot's timing:
   - "Auto-retaliate eats your next move" (PowerWyrm, King p=9259). Retaliation spends the player's
     energy **[consistent with code: `dungeon.c:1037`]**, so an escape sent after a big hit lands one
     enemy turn later than you'd expect.
   - Big hits often come in pairs.

   (Strategy p=5240, p=5242, p=6524; YASD p=892, p=2510, p=664.)

4. **An escape must be one reliable action, and it must be verified.** Deaths came from:
   - slot-based macros hitting the wrong item after the inventory reordered ("TRIED TO USE NON-STAFF
     OBJECT" ×5 at 0 HP);
   - two items sharing the tag `@u1`;
   - an uninscribed new teleport staff;
   - the Speed key pressed instead of heal;
   - staves failing ("You failed to use the staff properly") or burning in fire attacks;
   - scrolls being unreadable while blind or confused.

   The doctrine is to address items by unique tag, keep at least two *kinds* of escape, use a staff
   (usable blind or confused) as the backup, check that the escape actually happened, and fall back at
   once if it didn't. (YASD p=2473, p=5386, p=2455, p=5869; Strategy p=5294, p=6627, p=8354.)

5. **Status effects kill through full HP.**
   - Stun escalates to a knockout, which works like paralysis. Quaff CCW (or escape) at the *first*
     "Stun". Melee stun (Mystics, GMMs) can't be resisted, so Free Action and resist sound don't help:
     never melee them.
   - Confusion and blindness block scrolls. Always carry CCW plus a Staff of Teleportation until the
     character resists confusion.
   - Paralysis: Free Action by 1000 ft (conservative) and 1250 ft at the latest (ogre mages, carrion
     crawlers, ghouls).

   (Strategy p=6201, p=9380; YASD p=9379, p=5216, p=5261.)

---

## 2. Recommendations: Pilot (reflex rules)

In rough priority order. Where it's relevant, I've noted the Pilot's current behaviour (from
HANDBOOK.md).

| # | Rule | Why / source |
|---|---|---|
| P1 | **Arrival check tightened.** On any arrival (stairs, recall, teleport level, and also after a teleport or phase), scan before acting. Leave via the stair underfoot if **any** awake `Z` is in view, or any breather (`D`, `d`, `M` hydras, flashing/multi-hued letters) or unique. The current `arrival_pack=4` is too lax for hounds: a pack of 3 air hounds kills. Trigger on the server messages "You enter a maze of down/up staircases." **[code ✓ `cmd2.c:82,186`]**. | §1.1 |
| P2 | **Up-arrivals are riskier.** Arriving by `<` gets no hound clearing, so use a stricter arrival threshold after `<`. The exit is cheap: with connected stairs you arrive standing on a `>`, and taking it gives the hound clearing on the next level. | code ✓ |
| P3 | **Heal vs escape by numbers:** compare the expected heal (CLW about 15, CSW about 18, CCW about 27, Healing 300) with the HP lost over the last enemy turn. If the heal is smaller, or more than one breather has line of sight, escape. Add one extra enemy turn of margin for the auto-retaliate delay. | §1.3 |
| P4 | **Status triggers:** stun → CCW now (or escape if a Mystic or GMM is adjacent: melee stun keeps coming). Confused or blind → escape with a staff or potion, never a scroll. "You have no light to read by" → step once, or use a staff (an old 2008 bug; check on 1.5). | §1.5; YASD p=5884 |
| P5 | **Escape chain with verification:** after an escape, confirm by position or message within one turn. If it didn't happen, use the next item of a *different kind*. Resolve items by name or tag every time, never by slot. Refuse duplicate tags. Re-resolve after identify, since the slot can move. | §1.4; YASD p=2440 |
| P6 | **Summon reflex:** on "magically summons" (or a known summoner in view: `p` casters, Mystics, `Q`, Silent Watcher, Death Knight), escape or leave the level instead of fighting in the open. After killing any summoner, leave the level rather than clean up. The `choke` order should prefer squares with the fewest open neighbours (summons need open floor next to you), and keep the number of hostiles in line of sight at one. **Correction (Addendum A5): our corridors are two tiles wide, so an ordinary corridor is *not* a one-wide choke. Use doorways, room entrances, vault mazes or a tunnel you dig yourself.** | §1.2; Strategy p=5974, YASD p=2565 |
| P7 | **Lag gate:** measure round-trip time continuously. When it's high, stop diving and exploring, stay on or near stairs, and don't start fights. Lag deaths are common in YASD ("commands arrive just a little too late", p=2473). | YASD |
| P8 | **Disconnecting is not an escape.** A dropped connection in the dungeon leaves the character in play for about 16 s (in town it's immediate) **[code ✓ `net-server.c:374-379, 678`; the forum says 30 s from older versions]**. Never go idle in the dungeon: the existing idle-recall rule is right. | YASD p=2465, p=2534 |
| P9 | **Recall delay = danger window.** After reading Word of Recall, stand on stairs or in a dead end and don't fight. If a threat appears, take the stairs. Several deaths happened while waiting on recall. | YASD p=797, p=2538 |
| P10 | **Never queue commands across a level change** (nothing after `>` in a macro runs). Re-plan after the new level loads. Check charges before using a staff or wand (an empty one leaves a blocking prompt; our C side already ESCs prompts). | NEWP p=3229 |
| P11 | **Don't overheal:** quaff only below a threshold, one at a time, and check the result. A warrior king wasted 27 of 74 Life potions. | King p=593 |
| P12 | **Aggravation guard:** never wield items that aggravate (weapons of *Fury*, etc.). If forced to, take them off before stairs or recall. | Strategy p=5259, t=1249&start=90 |
| P13 | **Message classifier seeds:** "commands you to return" (teleport-to), "magically summons", "stares deep into your eyes" (paralyze), "creates a mesmerising illusion" (confuse), "casts a spell, burning your eyes" (blind), "gestures at your feet" (teleport level), "You feel very <clumsy/weak/...>" (stat drained) vs "...for a moment, but the feeling passes" (sustained). The full list is in Strategy p=7256 and King p=593. | parser |
| P14 | **Town idling:** **log out in town rather than idle** (corrected, Addendum C: the server rules forbid going AFK in shops). Never idle in the open, especially without light. A level-33 mage died AFK in town with an empty lantern. Keep the light fuelled (already done). | Strategy p=5307 |
| P15 | **Death handling:** on death the ghost is teleported up to 200 squares with no safety check **[code ✓ `xtra2.c:2805`]** and is often killed within 1–2 s. Policy: float up with `<` at once, resurrect at the Temple, and don't go back for gear. Resurrection costs about 3–5 levels (forum). Log the last ~50 messages and a map snapshot for post-mortems. | YASD p=2470, p=2451 |

## 3. Recommendations: Navigator (doctrine)

- **Down-only below a set depth.** Stair-scumming up and down is fine shallow. Below about 1500 ft
  (the first gravity and air hound depths), prefer `>` only: when no `>` is known, take `<` *only* if
  the Pilot is ready to leave again at once. Set the WoR recall depth to 100–200 ft above the target
  (`@R` inscription). *This contradicts the HANDBOOK's "go up and down until a `>` shows up" at depth.*
- **Depth caps by gear and HP** (the forum's checkpoints, cumulative):

  | Depth | Needed |
  |---|---|
  | 1000 ft | Free Action and See Invisible (a conservative cap; 1250 ft at the latest) |
  | 1250 ft | the four basic resists |
  | ~1350–2500 ft | resist sound (vibration and plasma hounds; knockout) |
  | 1900–2000 ft | resist confusion and blindness, resist poison, ~400 HP, CON toward 18/200 |
  | ~2000–2750 ft | beware nether breathers (Dracolich/Dracolisk): avoid light-green `D` without resist nether |

  ESP doesn't show Drolems (poison breath, dark green `g`), so a warrior needs a detection item.
- **Re-check resists, Free Action and See Invisible after every equipment change.** Several deaths
  came from a swap that silently dropped a key resist.
- **Vaults, pits, zoos: don't.** A "special" level feeling at shallow depth is "99% a jelly pit";
  vaults can hold monsters 40 levels out of depth from about 250 ft (a Greater Vault at 650 ft killed
  several rescuers). "Good" or "excellent" feelings at shallow depth are worth exploring. *This
  partly contradicts the HANDBOOK's "stop for a possible vault".* Also: a "good feeling" level held a
  Tarrasque, so feelings are not a safety signal.
- **Look up unknown monsters before engaging**: an unknown race name = dangerous. Named traps from
  the deaths: a flashing `D` (AMHD or Great Wyrm of Chaos), Gorlim ("not an easy black knight"), Huan
  (looks like Maggot's dogs), a blue `Z` (time hound, out of depth at 850 ft), Mystics.
- **Shopping for a warrior going below 1000 ft** (Zal, Strategy p=6011): Speed potions, 10–20
  Heroism (it cures fear, and fear stops melee and auto-retaliate), 20–60 CCW, Healing, 20+ Phase,
  5–20 Teleportation, a Staff of Teleportation as soon as affordable, 5 WoR, Magic Mapping and Detect
  Invisible, a wand of Teleport Other, and food (speed makes you hungry). Keep backups: fire and cold
  destroy scrolls, staves and potions. A **bow or sling** is strong in MAngband (the bow slot gets both
  the multiplier and the brand; Morgoth was killed at clvl 26 mostly by shooting), and a level-1
  character should buy one for town safety.
- **Pace:** "players who know what they are doing can dive a warrior to 500 ft and gain the first 10–15
  levels with minimal effort" (p=5580). Examples of too-fast diving: clvl 6 at 900 ft, clvl 40 at 3000
  ft. A caster depth table (p=6322): clvl 10s at 500–1000 ft, 20s at 1000–1500, clvl 35 at 2000.
- **Don't linger on a level.** Idle levels keep spawning monsters (a greater mystic spawned next to a
  party that stayed too long). Explore "3–5 screens, then `>`" (Zal).

## 4. Multiplayer facts the HANDBOOK should state

- **A level persists while any player is on it.** Levels are freed only when `players_on_depth == 0`
  **[code ✓ `dungeon.c:2039`]**. So "levels are not persistent" is true only when you're alone. On the
  live server you may arrive on a level another player is holding: it may be disturbed, with awake
  monsters, and may have just killed someone. Recall lands at the same spot, so after another
  player's death at a depth, don't recall there. Monsters split their attention between players.
- **A no-ghost "brave" option exists** (client option `no_ghost`, "Death is permanent" **[code ✓
  `c-tables.c:730`, server `cmd4.c:697`, `control.c:222`]**). **User decision (2026-09-26): keep ghosts
  on (`no_ghost` off), because it mirrors how people play on the live servers.** So the Pilot needs
  the ghost-handling rule P15.
- **Artifacts are shared server-wide. Uniques are *not*** (corrected in Addendum 3 #1): each character
  has its own kill list, so every fresh throwaway meets the early uniques.
- Good-citizen norms from the forum: don't camp in a shop for hours; don't rescue people or answer
  rescue requests (rescuers die too); never go hostile; don't transfer items between tool characters
  ("bumping" got characters deleted); don't *Destroy* or Teleport Other near other players or their
  gear. Characters may time out when unused (forum; not verified in code).

## 5. Where the current docs are contradicted

| Current text | Forum says | Strength |
|---|---|---|
| HANDBOOK: "go up and down until a `>` shows up" | Below ~1500–2500 ft, `<` is the deadliest move; go down only | **code ✓** (hounds cleared only on down or recall) |
| HANDBOOK escape order: stairs, Phase, *cure potion* | A cure potion is not an escape; only heal if the heal beats the incoming damage | strong, many deaths |
| HANDBOOK: "stop for a possible vault" | For a throwaway without detection, leave "special" levels; never enter vaults, pits or zoos | strong |
| notes_players: "levels are not persistent" | True only while no other player is on the level | **code ✓** |
| HANDBOOK: "~1 spare ration" | Fine early; deeper with speed items, carry more food | weak |
| notes: Free Action by 1000 ft | 1250 ft is the hard line; keep 1000 as the margin | agrees |
| Pilot `arrival_pack=4` | 1–3 hounds on arrival can kill at depth | strong |

## 6. Posts worth the Architect's time

1. **t=1249 "Strategy against bad moves"** (2008–09, all pages): PowerWyrm dissects death dumps. It's
   the best "don't do this" source, but only 120 of 184 posts are archived.
2. **p=6185, p=9415**: the up-stairs and hound rule, in the developer's words.
3. **p=6201, p=9380 / YASD p=9379**: the stun and knockout mechanics, and why Mystics stun-lock.
4. **p=9345, p=9346**: the breath damage caps and a table of which resists actually matter.
5. **p=6011**: the warrior kit for 1000 ft and below (a shopping list).
6. **p=5597**: early killers by depth band and letter or colour (a seed table for the danger list).
7. **p=7256**: monster spell messages mapped to effects (for the classifier).
8. **p=5974**: line of sight and corner tactics, with ASCII diagrams.
9. **King p=593**: a warrior's full Morgoth log, with real message strings, inscriptions, hounds on
   arrival and overhealing.
10. **King p=9259**: "auto-retaliate eats your next move".
11. **YASD p=2473, p=5386**: lag plus slot-macro death, and the duplicate-inscription death (both are
    test cases).
12. **YASD p=2470–2472**: ghost placement (code quoted), and a player asking for exactly what the
    Pilot does ("autotrigger destruction depending on hp", p=2562).

## 7. Suggested checks on our test server (cheap, before encoding rules)

- The hound clearing asymmetry: already confirmed in code. There's no need to test it live.
- Whether the "no light to read by" bug still happens after a darkness attack on 1.5.
- Resurrection cost (levels lost) and ghost `<` behaviour, with a test character.

## Coverage and gaps

| Subforum | Topics read | Notes |
|---|---|---|
| Strategy | 42 of 43 | t=1249 has 120/184 posts; t=1341 has 15/17 |
| YASD | 142 of ~198 | the missing ones have only broken archive captures (HTTP 500) |
| King Lounge | 26 of 38 | |
| New Player Support | 12 of ~106 | most captures are broken; likely low value (mostly old connection or compile help) |
| General Discussion | 533 of ~552 real topics | see the Addendum; the other 389 downloaded topics were 2025–26 spam |

The failed topics will be retried if the archive or the live site recovers. The raw downloads and
text corpus are kept in the Advisor's session scratchpad and are not needed to use this memo.

---

# Addendum: General Discussion (added 2026-09-26)

General Discussion held 922 downloaded topics, and 389 of them are 2025–26 spam (everything from
about t=2251 up). The 533 real topics (2002–2020) were read in full by three subagents, and about 120
had usable facts. Their notes, with post URLs, are in
`memos/2026-09-26-forum/general_{1,2,3}.md`.

The subforum is mostly social talk and server news. Its value is **mechanics that changed between
versions** (which tells us which old advice to discount), **server rules**, and several
**mechanics we confirmed in the 1.5 code** that the Pilot can use directly. **No post anywhere in the
five subforums sets a policy on bots or automated players.**

## A. Mechanics verified in our 1.5 source

| # | Fact | Code | Implication |
|---|---|---|---|
| A1 | **"Time bubbles": when HP% ≤ `hitpoint_warn`×10, time around that player runs 5× slower** (monsters included, so it gives reaction time, not speed). Resting with no monster in line of sight runs time at 10×, and running at 5×. None of this applies in town. `hitpoint_warn` is a client setting (0–9, default 0 = off), loaded from the pref line `H:n` and sent at login. | `server/xtra2.c:5164-5192`, `mdefines.h:271`; `client/c-files.c:1098-1104`, `c-init.c:716` | **Top recommendation of this addendum: set `hitpoint_warn` to about 5–6 for tool characters.** Every fight below 50–60% HP then runs in slow motion, which is the best defence against lag deaths (P7) and "two big hits in a row". Caveat: other players within sight on the same level share the slowed bubble. |
| A2 | **Turns take longer deeper.** Action energy cost rises from 9000 at 50 ft to 12500 at 2000 ft and 20000 at 4000+ ft, so a turn at 4000 ft takes about twice the wall-clock time of one at 50 ft. | `tables.c:2200` `level_speeds`, `xtra2.c:5109` | Pilot timers and lag budgets should count game turns or energy, not seconds. Shallow levels give the *least* real reaction time. |
| A3 | **A second Word of Recall cancels the pending one** ("A tension leaves the air around you"). | `spells2.c:1197` | Never re-send recall on a retry after lag. Sending it again is also the way to abort one on purpose. |
| A4 | **ESC clears the server command queue.** The normal client sends `PKT_CLEAR` on the first ESC; the server empties the queue and cancels pathfinding. This settles a forum disagreement: a 2006 post said queued commands can't be cancelled, and a 2019 developer post says ESC clears them. | `client/c-cmd.c:315-318`, `server/net-game.c:1770` (`recv_clear`) | **Our tool client doesn't expose this packet yet.** Suggest adding a `clear` command and sending it before every emergency action, keeping one command in flight at a time. A 2006 death had five queued quaffs fire in turn ("Tried to quaff non-potion!" ×5). |
| A5 | **Corridors are two tiles wide** (`WIDE_CORRIDORS`, "room for two people abreast"). | `src/options.h:232`, `generate.c:2711+` | **This corrects part 1 (P6 and §1.2).** A normal corridor leaves about 5 open neighbours, not 2. Real one-wide chokes are doorways, room entrances, vault mazes and tunnels the character digs. The Architect could check this against maps the Pilot has recorded. |
| A6 | Teleport Level goes **up** half the time (the 2008 forum claim that it can't is wrong). The arrival is `LEVEL_RAND`, which gets the hound clearing. | `spells1.c:365` | Treat it like a recall arrival. |
| A7 | The running speed bonus applies **only in town**. In the dungeon, running is blocked while a monster is in view, and the time bubble speeds up nearby monsters too. | `dungeon.c:950` | Running is not an escape from a monster as fast as you. Use Phase or Teleport. |
| A8 | No food is used in town unless the character is gorged. | `dungeon.c:1123` | Idling in town costs no food. |
| A9 | Monster spell and breath range is 18 squares. | `mdefines.h:194` `MAX_RANGE` | Threat radius for breathers and casters = 18 squares in line of sight. |
| A10 | The shallow "vaults designed to kill you" are still in 1.5: Miniature Cell, The Shaft, Backdoor Surprise, Zoo of Concentrated Death (monsters up to 40 levels out of depth; a Dreadmaster from one killed two players at 300 ft). | `lib/edit/vault.txt` N:36, 128–130 | Confirms §3: vaults are "leave". |
| A11 | Config facts: `PVP_HOSTILITY = 2` (both players must agree to fight, the 1.1 rule; the live server's value is unknown). `GHOST_DIVING = false` (ghosts can't go down stairs). `NEWBIES_CANNOT_DROP` exists "to discourage people from writing scripts to bring in characters, drop their stuff, suicide them… to accumulate funds". That comment is **the only anti-automation measure found**. `BASE_UNIQUE_RESPAWN_TIME` means uniques come back. | `mangband.cfg` | Other players are no combat threat under the default rules, so the pre-2008 player-killer stories are outdated. Run one tool character at a time, and never move items between them. |

## B. Doctrine updates for the Pilot and Navigator

- **Arrival, refined.** PowerWyrm (2014, t=2142 p=9685): arriving next to hounds is survivable
  "unless the autoretaliator wastes the first turn". Send the planned first action (step back onto the
  stair, or phase) *immediately* on arrival rather than idling. This adds to P1.
- **History of the hound clearing.** Clearing hounds on recall and down-stairs arrival was written by
  Jug for IronMAngband in late 2005 and ported in 2006 (p=242, p=244). So the 2002–2005 "recalled
  into hounds" deaths predate it, and part 1 overweights them. Veterans in 2007 (p=1757, p=1766) said
  *summons, double breaths and confuse-plus-blind* killed them far more than arrival hounds. **Revised
  ranking:** summoners and status combinations ≥ up-stairs arrivals > down or recall arrivals. P1 and P2
  still stand; P3–P6 matter at least as much.
- **Wilderness: never leave town except by `>`.** Deaths near town include 22 ethereal hounds on
  entering a sector, druj and basilisks at night, Azog killing a clvl-16 Half-Orc Warrior, and
  migrating fruit bats nearly killing a clvl 9 (chunk 3, t=1571, t=1526, p=5537, t=1675). This matches
  the Pilot's current "no exploring on the surface".
- **Poison was the most common low-level killer in 2008** (about 100 characters; t=1261): air hounds
  "kill a lot of people indirectly with poison". Being poisoned at low HP counts as ongoing damage.
  Keep CLW/CSW for the cure.
- **Small Pilot rules:**
  - re-wield the weapon after tunnelling (a paladin died holding a pick);
  - if you log in stuck inside rock (the level reset while you were logged out), read Phase Door;
  - after a "quake" message, re-request the map;
  - after "Nothing to target" or a device firing at your own square, clear and re-target (the
    stale-target bug, fixed with `*` then ESC);
  - flasks of oil are a cheap thrown attack for a warrior.
- **Pickup semantics conflict.** A developer in 2019 (t=1897 p=9922) says in 1.5 `g` always picks up,
  and `,` picks up only when `auto_pickup` is off. Our pilot notes say `,` worked and `g` did
  nothing. **The Architect should reconcile this**; it probably depends on the options.
- **Early money loop** (Emulord, "I rarely die", t=1574 p=6618):
  1. collect potions and scrolls at 50–150 ft;
  2. sell them unidentified;
  3. identify wands, staves, rings and amulets before selling them;
  4. buy CCW against confusion from low-level mages;
  5. save for a Staff of Teleportation, then take on orc pits.

  Domino's warrior fast start (p=1327): whip plus AC, scum at 50 ft until you can afford WoR, then
  take every `>` down to about 1000 ft. It works for "about 1 in 10 characters", a useful baseline for
  throwaway throughput. Healing potions are scarce (they trade at about 20k gold between players), so
  keep any you find.

## C. Server rules and etiquette (for the live server)

From the 2002 rules (p=3961) with PowerWyrm's 2008 update (p=5210), plus later enforcement posts:
- **No transfers between your own characters.** Characters have been deleted for it (t=1532, p=6365).
  The audit also flags wealth that doesn't fit the character's level. **Don't pick up or sell items
  lying in town** that you didn't drop yourself (p=1321, p=1375).
- **Don't go AFK in shops** and "don't save in the dungeon". Idle by logging out in town. This is why
  P14 is corrected. (The 2014 note: "Don't AFK in town. Just log out.")
- Ghosts shouldn't play with living characters. Don't litter in town, and don't bump into other
  players.
- Nothing about bots. Running several characters from one computer was asked about in 2007 and never
  answered. **Advice: one tool character online at a time.**

## D. Worth fetching if mangband.org comes back

- The stickied rules page from 2009 or later. The 2002 and 2008 texts are all we have.
- The per-monster "characters slain by" pages (mangband.org/Main/Info), a ready-made danger ranking.
- Ladder death dumps (posted automatically), for post-mortems of our own deaths.
- About 140 topics whose only archive copies are broken, mostly in New Player Support and YASD.

## E. Posts worth reading (General)

- t=1601 (p=6808–6823): the time-bubble design debate, which explains 1.5 running and bullet time.
- t=1603 p=6824: the server/client refresh timeline, and why deaths to two hits in a row happen.
- t=2142 p=9685: why the first action after arrival must already be sent.
- p=3961 (t=930, all pages) and p=5210: the server rules in 2002, and their status in 2008.
- p=1754, p=1757: what actually kills veterans, and lag from server redraws.
- t=1568: what changed from 0.7 to 1.1 (limited ESP, player shops, recharging).

---

# Addendum 2 (2026-09-27): first batch from the live site

mangband.org came back on 2026-09-27, and I'm now fetching the 143 topics that have no readable
archive copy (87 New Player Support, 45 YASD, 11 King Lounge), plus the missing pages of the long
Strategy thread t=1249. The site fails often (about 3 in 4 requests return 502), so this is slow.
This interim section covers the first **21 topics**:
- pages 105–164 of t=1249, PowerWyrm's death critiques, so the thread now has 165 of its 184 posts;
- page 2 of t=1341;
- 9 YASD threads;
- 10 King Lounge threads.

**New Player Support isn't covered yet.** Full notes with every URL, 18 new deaths, and a list of
parser strings are in `memos/2026-09-26-forum/live_batch1.md`. I spot-checked the key claims against
the fetched posts.

**New or changed:**
1. **Detection can freeze the screen** (PowerWyrm, p=6630, 2009). Detect spells "wait for the player to
   press a key", and a character died to time hounds while waiting. The Architect should check whether
   1.5 or our tool client still blocks there. The C side ESCs prompts, but this may be a different
   kind of wait. Rule: never detect with monsters close, and send ESC right after.
2. **Molds and jellies: never stand next to them or melee them.** A poison-mold cluster killed a
   player who still had Healing and Teleport unused (p=6482). A Death mold disenchants gear (p=6572).
   Architect: auto-retaliate may attack an *adjacent* mold on its own (our inference, not from the
   forum), so the Pilot should step away from any `m`.
3. **Unseen attackers mean leave.** Signs: slow HP loss with nothing visible (an invisible ethereal
   dragon, p=6466), and messages beginning "It …" ("It breathes…", "It magically summons…"). "You hear
   a door burst open!" should "always trigger a paranoid response" (p=6638). This is a parser and
   Pilot rule.
4. **Traps are arrivals too.** A teleport trap put a player beside off-screen time hounds (p=6158), and
   summon traps killed two players (p=7083). Run the arrival check after any trap teleport.
5. **Resist nexus and Boots of Stability can hurt a low or mid-level character.** A nexus breath
   teleports you away from a hound pack for free, while Stability keeps you in the pack (p=7083,
   p=7111). Navigator: don't prioritise them for the throwaway.
6. **At depth, *Destruction* beats Teleport as the panic button.** Teleport "into worse" deaths
   keep recurring (p=6510, p=6637, p=6759, p=7447). This applies beyond the throwaway's range, and
   *Destruction* affects other players' gear (see §4).
7. **In our depth band:** Mughash with kobold shamans at about 950 ft caused a "confusion lock" after the
   player left the `>` (p=6806). An Elder aranea at 600 ft killed a clvl-13 character in one move
   (p=6804). Acidic cytoplasms at about 800 ft damage armour. Add all three to the danger list.
8. **The breath rule in numbers:** at 2500 ft and deeper, "expect to die in 2 breaths (or 1 with
   ≤500 HP)" (p=6559). Navigator: engage a breather only if 2 × its maximum breath is less than current
   HP.
9. **Nuance to P11 (overhealing).** PowerWyrm "(over)healed as soon as the HP bar went yellow" in his
   winning fight (p=8465). Set the heal threshold by the largest expected hit, not by counting
   potions. P11 still stands against chain-quaffing.
10. **Recall depth.** An uninscribed Word of Recall took a player to max depth, onto Morgoth ("You
    feel yourself yanked downwards!", p=7323). Always set the recall depth (`@R`) before reading.
11. **Artifacts are nearly gone** on a long-running server: "only the crappiest artifacts remain"
    (p=8391, 2010). Plan around ego items.
12. **Parser strings:** about 25 exact messages (drains, stun, blind, item destruction, pseudo-ID,
    hunger) and the monster-health ladder "shrugs off" → "grunts with pain" → "cries out in pain" →
    "screams in pain". The full list is in `live_batch1.md` §1 item 20.

**It also strengthens:** P1 and P2 (a shallow-vault death with the exact up-arrival messages, p=6536 and
p=6540, which makes a good test case); P3 and A1 (a heal "only triggers the next turn", p=9538); the
food rule (two starvation deaths, p=7352 and p=6809); and P6 (hound packs get "10–20 attacks before
your next turn" in the open, p=7111).

(The rest of the live topics are covered in Addendum 3.)

---

## Erratum (2026-09-27): cure potions in 1.5, from `server/use-obj.c:483-545`

| Potion | HP | Blind | Confused | Poison | Stun | Cuts |
|---|---|---|---|---|---|---|
| CLW | 15 | cures | −20 | no | no | −20 |
| CSW | 20–24 | cures | cures | **no** | **no** | cures |
| CCW | 25–29 | cures | cures | cures | cures | cures |
| Healing | 300 | cures | cures | cures | cures | cures |

This corrects `notes_players.md` ("CSW/CCW cure poison"): **only CCW and better cure poison and
stun.** It also corrects the memo's "CSW about 18 HP" (the code gives 20–24). No potion here cures
fear; use Heroism. The Pilot's stun rule (P4) must use CCW or better.

**Resurrection cost (code, `xtra2.c:2867-2868`):** resurrecting a ghost halves both `exp` and
`max_exp`. So it costs exactly half the character's experience, permanently. Restore Life Levels (or
Life) can't recover it, because they only raise `exp` back to `max_exp` (`spells2.c:485`). This
replaces the forum's "3–5 levels" in P15. Drains from monster attacks (nether, time) are
restorable.

---

# Addendum 3 (2026-09-27): the rest of the live site. Coverage is now complete.

The live fetch finished. All 143 topics that had no readable archive copy are in, including **all of
New Player Support** (87 topics, 31 of them substantive) and 36 more YASD topics. Notes with every
URL are in `memos/2026-09-26-forum/live_batch2_newplayer.md` and `live_batch2_yasd.md`. The full
text of all 905 topics, tagged by source (archive.org or live), is in `Advisor/data/forum/corpus/`.
**Nothing in the forum sets a policy on bots.** The one developer remark (PowerWyrm, 2009) is mild:
"a modified client" may play on the main server (p=7802), and he joked about writing a bot to check
the Black Market (p=7769).

## Code-verified corrections and new facts

1. **Uniques are tracked per character, not server-wide.** A unique can spawn on a level if any
   player there hasn't killed it **[code ✓ `monster2.c:16-35`]**. When a character is resurrected,
   the uniques it killed whose level is above ~65% of its max depth come back ("X rises from the
   dead!", **[code ✓ `xtra2.c:2487-2518`]**). **This corrects §4:** every fresh throwaway will meet
   Grip, Fang, Bullroarer, Wormtongue, Grishnákh, and Azog.
2. **Privacy: the player list shows every client's `realname@hostname`** **[code ✓ server
   `cmd4.c:723`]**. Our client fills these in from the Unix login (`getpwuid`, `client/client.c:48`)
   and the machine's host name (`c-init.c:999`). **Our live sessions (Happy, Sneezy) have been showing
   the user's cluster login and node name to other players.** Architect: send neutral values in tool
   mode. The developer quote above suggests a modified client is acceptable.
3. **Monster spell frequency is normal in 1.5.** A 2013 forum complaint said summoned hounds "breathe
   immediately" because of bug #1016 (casting every turn). In 1.5 a monster casts with probability
   `100/x` for its `1_IN_x` rating **[code ✓ `init1.c:3184`, `melee2.c:459-468`]**, so that part is
   outdated. The practical rule still holds: "magically summons" means escape now (P6).
4. **Reconnecting under the same name takes over the session that is still lingering**
   ("Reconnect from other location.") **[code ✓ `net-server.c:884-900`]**. In 2007 mangband.org
   allowed one login per IP address and deleted characters that dodged it (p=3365). The 1.5 source
   has no such check, so it would be a live-server setting. Other cluster users behind the same NAT
   address could collide with us.
5. **`=g` auto-pickup** works on inscribed items **[code ✓ `cmd1.c:591`]**. This may help settle the
   pickup conflict in Addendum B.

## Doctrine updates

- **Auto-retaliate does melee an adjacent mold.** A log shows "You enter a maze of down staircases. …
  You miss the Death mold. You hit the Death mold…" before the player could act, then disenchantment
  and death (p=7951). This confirms the inference in Addendum 2 #2. **Pilot:** if an `m` is adjacent
  (on arrival or any time), step off, or take the stair back. Shooting molds from range is a known XP
  farm (p=7559).
- **The stun ladder** for the parser: "You have been stunned." → "heavily stunned." → "knocked out."
  (p=9369). Escape at the first rung.
- **A heal can't land between two consecutive hits.** You get "a third of a second to react", and one
  turn goes to the auto-retaliator (p=9229). This supports A1 (`hitpoint_warn`) and early healing.
- **Our depth band:**
  - traps killed clvl-1 characters two steps from the first stairs at about 50 ft (acid, summon;
    p=8762, p=8763);
  - an orc pit at 300 ft killed two clvl-8 characters (p=8377);
  - reading a Scroll of Summoning at 250 ft brought Lagduff and about 25 snagas (p=3372);
  - Backdoor Surprise vaults held Mouth of Sauron at 1250 ft and Khamul at 1400 ft (p=6930, p=6946);
  - early advice: "avoid all orcs and most p's" at about 400 ft (p=7559); "novice warriors and paladins
    are dangerous" (p=7653).
- **Unique casters keep chasing you out of sight and telepathy range** (Saruman, Mouth, Ulfang;
  p=5981). After meeting one, leave the level; breaking line of sight isn't enough.
- **Aggravation plus stairs:** monsters "wake up AND act the same turn" you arrive (p=8516). This
  strengthens P12.
- **Resists:** chaos resistance does *not* give confusion resistance (p=9367). "Cannot be harmed by
  fire" on an item is *not* resist fire; a player took a 1600-damage breath because of it (p=6257). Read
  resists from the `C` sheet, never from item text. ESP also misses the greater, draconic and master
  `Q`s, which are summoners (p=9361).
- **Word of Recall:** a lowercase `@r`, or any other typo in the inscription, recalls to max depth
  (p=7223). Check the inscription before reading.
- **Healing potions are scarce, and 1.1 deliberately removed the BM's stock of them** (p=7781). Rods
  of Healing are "useless in real time". **CCW is the throwaway's real heal**, so don't plan on
  Healing.
- **Put the target first in any command that needs one.** A trailing `*t` with nothing targetable
  leaves you on a direction prompt (p=7658). Our C side ESCs prompts, but check for a target before
  throwing or firing.
- **Paralysis lock:** one player was held for about 10 minutes with his Free Action ring in the pack,
  not worn (p=7907). Check FA on *equipped* items. Logging out may help against a slow lock, but never
  against burst damage (p=8221).

## Server rules and etiquette (additions to §C)

- Alts are allowed, but free gifts between them aren't (p=3373, p=3374).
- A dead character's name stays reserved, so each throwaway needs a fresh name (p=5679).
- Don't drop or sort items on the ground in town, where others can take them. Destroy junk with `k`
  instead (p=9790, p=3212).
- Townspeople were made less aggressive in 1.1 (p=7781).

## Erratum (2026-09-27): hound depths and breaths, from `lib/edit/monster.txt`

§1 said "water and energy hounds at about 1000 ft, earth at 900, air at 1550, gravity at 1800–1900",
which is forum recollection. The 1.5 data: Light/Dark/Clear hound level 15 (750 ft); Fire/Cold/Energy
hound 18 (900 ft); Earth/Air/Water hound 20 (1000 ft); Vibration/Nexus hound 27 (1350 ft); Gravity
hound 35 (1750 ft). The names don't all match the breath: Water breathes acid, Air poison, Earth
shards. All are FRIENDS packs with melee blows too. Details: `memos/2026-09-27-danger-table.md` §6.
