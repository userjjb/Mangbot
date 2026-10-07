# General Discussion, chunk 2 of 5 (t=730..1401): distilled notes

This chunk covers 196 topics, mostly from 2002–2008 (MAngband 0.7.x up to 1.1.x). It is mostly social talk, server news, PvP arguments and artifact/house hoarding. It adds almost nothing on deep-dive tactics. What it does add: **when mechanics changed** (0.7.x vs 1.0/1.1), the **old and new server rules**, the **time-bubble mechanic**, and several small facts about the server and connection.

Some claims were checked against our source (`github/src/server`). These carry **[code ✓]** or **[code ✗]**. URL prefix: `https://www.mangband.org/forum/viewtopic.php?`.

## Top findings

1. **Time bubbles exist, and the Pilot can use them.** In 2008 the devs described "time bubbles": a game turn's length depends on the player's health and activity (p=5970, 2008). Our 1.5 code has this **[code ✓ `xtra2.c:5164 base_time_factor`, `dungeon.c:946`]**:
   - When HP% ≤ `hitpoint_warn`×10, the player's local time runs **5× slower** (`CONSTANT_TIME_FACTOR 5`, `mdefines.h:271`).
   - Resting with nothing in line of sight runs time at 10×. Running with nothing in LoS runs it at 5×.
   - `hitpoint_warn` is a client setting sent to the server (`net-game.c:1478`).

   **Action (Pilot):** set `hitpoint_warn` deliberately, e.g. 5–6, so that time slows below 50–60% HP. That gives the Pilot's escape logic 5× more wall-clock time. The same threshold should be the Pilot's "danger" line. [NEW]

2. **You can't cancel queued commands, and they outlive death.** A player died to inertia hounds with several CCW quaffs queued. The server then printed "Tried to quaff non-potion!" ×5. The escape macro `\eu1` did not flush the queue: "the server reads things in order of reception… ESC… had to try to do those before it even SAW the ESC" (p=3875, p=3876, 2006, 0.7.x). **Action (Pilot):** never have more than one action in flight during an emergency. Send one command, wait for the result, then decide. This is a strong extra case for memo P5 and P10. [CONFIRMS, stronger]

3. **PvP needs consent from both sides in 1.1+.** The rules went through three stages:
   - pre-2004: open PvP;
   - Nov 2004 / Apr 2005: no PvP in town, stealing disabled in town (p=3737, 2004; t=930 p=page30, 2005);
   - 1.1 (2008): "Ruthless pkilling has been removed… both characters have to agree" (p=5210, 2008).

   Our default config has `PVP_HOSTILITY = 2` ("Both players must be hostile… as per 1.1.0") **[code ✓ `mangband.cfg:92`]**. The live server's value is unknown. **Action (Navigator/HANDBOOK):** never set hostility. With that, other players are not a combat threat under the default rules. The pre-2008 PK horror stories are **[MAYBE-OUTDATED]**. [NEW]

4. **Server rules for mangband.org** (Crimson, p=3961, 2002). PowerWyrm's 2008 update is at p=5210. Rules still relevant to us:
   - don't give items of value away; sell them at no less than the store price (p=3978, 2003);
   - no mule or storage characters, which are "highly disrespected" (p=3710, 2004);
   - a separate character counts as a separate player, so a transfer must be a correctly priced sale (p=page30 in t=930, 2007);
   - ghosts must not play with live characters;
   - don't house artifacts (in 1.1 they "need to be used or carried");
   - don't litter in town;
   - don't bump people (it looks like stealing);
   - **don't AFK in shops**;
   - **"don't save in the dungeon"** (2008: "at any depth unless you have a good reason").

   A 2009 post notes a newer, stickied rules page exists (Emulord, t=930 p=page30). We don't have it; try to fetch it. [CONFIRMS memo §4, adds the store-price and AFK-in-shop details]

5. **Logging out in the dungeon: "entombed in rock".** If a character logs out on a level and the level resets, the character comes back embedded in rock. "Just cannot move… once you phase (or teleport or recall), you're ok again" (p=5225, p=5229, 2008). **Action (Pilot):** on login, if every move fails or the player sits inside a wall, read Phase Door. [NEW]

6. **Logging out keeps the level alive, at least in old versions.** In 0.7.x a logged-out character held its level "static":
   - a GV at 1600 ft stayed static until its finder logged back in (t=1083, 2008);
   - ghosts that logged out "locked up" levels (p=3785–3787, 2005);
   - Warrior logged out to keep a GCV level (p=4695).

   A dead player's gear persisted only while the level stayed static (t=1087, 2008). This extends memo §4 ("level persists while any player is on it"). A logged-out character may count too. **[check code: does `players_on_depth` include saved, offline players?]** [NEW/UNVERIFIED]

7. **Idling: log out. Don't stand AFK in town, the dungeon, or a wall as a ghost.**
   - "Don't AFK in town. Just log out" (p=3923, 2007).
   - A level-50 paladin's ghost waited hours in a wall for a rescue and was zapped by something that came through the wall: "only safe if ya log out" (p=3958, 2007).
   - A player logged a confused ghost out "as a 4" to survive (t=1097, 2008).

   This strengthens memo P14 and P15. [CONFIRMS]

8. **Teleport Level still goes up half the time in 1.5.** PowerWyrm said in 2008 that teleport level "doesn't allow to go up anymore" (p=4811). In our code it goes down with 50% chance and otherwise **up** (`spells1.c:365`) **[code ✗ for the 2008 claim]**. Up-arrivals get no hound clearing (memo P2), but `LEVEL_RAND` is used either way. **Action (Pilot):** treat a teleport-level arrival like a recall arrival. [CONTRADICTS: 2008 forum claim]

9. **Poison was the most common low-level killer of 2008.** A thread counted about 100 characters killed by poison: "99 low level + 8 high level chars". Air hounds "kill a lot of people indirectly with poison, if they barely survive the breathes" (t=1261, 2008). **Action (Pilot):** a poisoned status at low HP counts as ongoing damage. Cure it with CLW/CSW, or rest only when nothing is in LoS. **Action (Navigator):** keep cure potions stocked. [NEW emphasis]

10. **Air hounds kill low-level warriors, twice.** A level-24 warrior died to air hounds "for the second time in the past several days" (t=930 p=page30, 2004). Crimson himself died when he "hit a 3, teled straight into hounds" (p=4035, 2007). A teleport can land in a hound pack, so the arrival check P1 should also run after a teleport, as the memo already says. [CONFIRMS P1]

11. **Nature pits at 1000 ft with Acidic Cytoplasms**, which are normally found at 1750 ft and bash doors. One also brought earth hounds. AC went "+40 to -40 in about three seconds" (acid damages armour) (t=1218, 2008). That kill also involved **auto_scum**. **Action (Navigator):** a pit or zoo counts as "leave level" (memo §3). An acid-dripping `j`/jelly type means leave. [CONFIRMS vault/pit doctrine]

12. **Changes in the 1.0/1.1 era (2007–2008).** These help judge which old advice is outdated:
    - 1.0.0 (Sep 2007) rebased on **Angband 3.0.6** (p=4655);
    - 1.1.0 retuned for multiplayer (p=4655);
    - 10% sales tax, and shopkeeper purses divided by 3 (p=4946, 2008);
    - player-owned shops (t=1139, 2008);
    - no house keys needed (p=5210);
    - the temple gives 100 gold on resurrection (p=5210);
    - houses limited to 2 per character (t=1300, 2008);
    - ghosts can't take stairs down unless `GHOST_DIVING` is set (p=5210; t=1346; `mangband.cfg` has `GHOST_DIVING = false`) **[code ✓ cfg]**;
    - Globe of Invulnerability removed from mages (t=1101);
    - no-ghost "brave" characters in use (p=5070, 2008) [CONFIRMS memo §4];
    - online "scene of death" text snapshot added to death dumps (t=1185).

    **Anything from before 2007 about shop prices, money, GoI, keys or ghost diving is [MAYBE-OUTDATED].**
13. **Audit system:** characters are "flagged as suspicious, and removed from game play" when their stat gains or wealth are implausible for their experience (Crimson, p=4111, 2002). Items or money far beyond a character's level risk deletion (p=3161, 2007; p=3961 rule 2: gifts over ~1,000 au can trigger it). **Action (Architect):** never move gold or gear between our tool characters, and never take large gifts. [CONFIRMS memo §4]
14. **Nothing in this chunk mentions bots, borgs or automated players.** The only related text is a code comment in our config: `NEWBIES_CANNOT_DROP` exists "to discourage people from writing scripts to bring in characters, drop their stuff, suicide them… to accumulate funds" **[code ✓ `mangband.cfg:~75`]**. Scripted farming is the one kind of automation the server explicitly guards against. An unanswered 2007 question asked whether several characters from one computer at once are allowed (Berendol Q2, t=930 p=page30). **Action (Architect):** run one tool character online at a time on the live server. [NEW, a gap]
15. **Lag doctrine:** "My connection… has been pretty choppy… enough to make me not feel safe diving deep… don't want to die due to the TimeOut beast" (p=3732, 2004). A four-man dive to 4000 ft collapsed in "severe lag… buffer dumps" and a server crash (p=4783, 1999). A client "Quitting: timeout" appeared a few seconds after entering town (p=6122, 2008). [CONFIRMS P7]
16. **Menus don't pause the game.** "enter the macro screen… press ESC only to find out that my character has been killed in the meantime… no warning" (p=5973, 2008). Our tool has no menus, but the same holds for any Pilot "thinking" pause or blocked prompt. Never block in the dungeon waiting for the Navigator. [CONFIRMS idle rule]

## Findings by theme

**Death and resurrection**
- The ghost's key: in 0.7.x the ghost kept its house key unless it died (p=3961). A key inscribed `{!*h}` was still dropped on death (p=3875, 2006). Since 1.1, keys aren't needed (p=5210). [MAYBE-OUTDATED]
- Temple camping (0.7.x): a hostile player standing next to the temple entrance killed resurrecting players instantly (p=3923, 2007). This is impossible under consensual PvP. [MAYBE-OUTDATED]
- Rescues: "death on recall is most often impossible to avoid"; rescuers used *Destruct* at recall (Warrior, t=930 p=page30, 2006). Recall arrival is dangerous (memo P9, §1.1).
- A resurrected character loses levels: "I lost 7 levels" (p=3983, 2003, after repeated PK deaths and resurrections). [CONFIRMS memo P15 cost, roughly]

**Dangerous monsters and situations (at our depths)**
- **Drolems at about 950 ft.** An unusual run of excellent drops at 950 ft drew the joke "a drolem somewhere is fattening you up" (p=3834, 2005). Drolems are "mindless critters", invisible to ESP; detect them with Detect Monsters (p=4811, 2008). [CONFIRMS memo]
- **Undead beholders** are "easy to overlook, relatively shallow, and summon" (p=3134, 2006). **Gnomish mages** matter at first meeting ("run!") (p=3134). [NEW names]
- **An open vault at the bottom**: "Alls it would take is one Q to spawn in and it would be game over" (p=3856, 2006). [CONFIRMS summoner rule]
- **Out-of-depth plasma vortex** at 500 ft on Ironman (p=4859, 2008). A Cherub at 1550 ft summoned Ancient White Dragons and wiped a level-26–27 party (p=5206, 2008).
- **Angels**: AC matters because most of their damage is melee; Solars steal (p=3889, 2006).
- **Drakolisk at 2050 ft** is "one of the most classic deaths of all" (p=3959, 2007). [CONFIRMS nether-breather depth]
- **Wilderness:** Mirkwood (the spider forest) is too hard for low levels (t=1304, 2008). A level-16 Half-Orc Warrior was killed by **Azog at −25,800 ft** (wilderness) (p=5537, 2008). The wilderness away from town has uniques and was littered with dead players' gear (p=3788, 2005). **Action (Navigator):** don't wander the wilderness with a throwaway. [NEW]
- **Shovel and pick deaths:** several players fought while still wielding the digger after tunnelling. A Paladin died to Azrael's nether breath that way (p=4138, 2003). **Action (Pilot):** after any tunnelling, re-wield the weapon (`@w1`) before fighting. [NEW]
- Sleeping monsters left behind finish off characters fleeing at low HP. Phase Door can land you deeper among the monsters (Whelk, p=6496, p=6507, 2009). "Always detect traps" (t=1335 p=page15, 2013). [CONFIRMS]

**Items and identification**
- **Cursed Ring of Teleportation:** another player's inscription can hide `{cursed}`. Wearing it teleports you around town until you read Remove Curse (p=3124, 2006). **Action:** never wear gifted or unknown rings. Uninscribe items before trusting them. [NEW, minor]
- Ring of Damage adds to melee only. Ring of Accuracy and Ring of Slaying to-hit also apply to missiles (t=1322, 2008).
- Ring of Speed values follow `randint(5)+m_bonus(5,level)`, plus 50% chances of +1 more; above +10 is extremely rare (p=4147, 2003). Low-level characters who find speed boots "typically don't live long afterwards" (Crimson, p=3973). A lucky find is not a reason to dive faster.
- Special artifacts (Phial through the One Ring) are depth-clamped. "Look where you're supposed to find them" (p=3946, 2007). Not relevant to us.

**Money, shops, houses**
- Price floor: sell to players at no less than the store buy price (p=3978, 2003). Stat potions retail at about 8k (p=3978). Since 2008, the 10% tax and smaller shopkeeper purses make money scarcer (p=4946). [MAYBE-OUTDATED numbers]
- Houses: max 2 per character (t=1300, 2008). Most free houses lie one or more wilderness screens from town (p=5486, p=5511). Don't close a house door with the key inside (p=3840, 2005/6). Our throwaway doesn't need a house.
- Server rollbacks happened in the 0.7 era: world saves reverted while character saves were current (t=884, t=887, t=889, t=901, 2004–5). "Keep valuable items in your pack" (p=3756). Items dropped just before a crash were lost (t=877, 2004). [MAYBE-OUTDATED, but "don't leave gear on the floor" still holds]

**Multiplayer and server behaviour**
- Uniques respawn on a timer (p=3161, 2007). Our config has `BASE_UNIQUE_RESPAWN_TIME = 60` per unique level **[code ✓ cfg]**. A shared unique may therefore be back later. [adds to memo §4]
- `MAX_TOWNIES` in the config sets the number of town inhabitants. The town is randomly generated in 1.1 (p=5760, 2008). This matters for our test server.
- Parties are temporary; in 0.7.x the party disappeared when its leader's ghost died (p=4339, 2006). All parties were wiped in a 2004 cleanup (p=3689).
- There are typically players online at most hours (p=5439, 2008). An IRC bot `!who` reports who is online with level and depth. Fewer than 20 regulars in 2006–2008 (p=4014, p=5419).
- Online monster pages list "characters slain by each monster" (t=1175, 2008). This is a ready-made danger ranking if mangband.org/Main/Info comes back. **Action (Architect):** scrape it if available. [NEW data source]

**Class and race**
- Warrior (2007): "It used to be Half-orc Warrior… then I started playing Dunadan Warriors instead. That's the way to go!" (p=3186). No reasons are given. [weak]
- A level-50 dwarf warrior had 940 HP at 18/160 CON (p=4109, 2002). That is a rough HP ceiling for a warrior.
- In 1.0/1.1, mages lost GoI; PowerWyrm rated the 3.0 mage spells (t=1118, 2008). Not relevant to a warrior.
- "corridors are two tiles wide in general" in MAngband vs Angband (Billsey, p=4658, 2007). This contradicts the memo's corridor-choke doctrine if it is true. **[check code/observe; our live maps showed mostly 1-wide corridors?]** [CONTRADICTS: possibly the choke doctrine]

## Death catalogue (deaths described in this chunk)

| Cause | Depth | Char | Mistake | Lesson | URL |
|---|---|---|---|---|---|
| Inertia hounds | ? | Billsey | queued CCW quaffs; `\e` didn't flush them | one command in flight | p=3875 |
| Air hounds (×2) | ? | clvl 24 warrior | — | hounds kill mid-level warriors | t=930 p=page30 |
| Teleport into hounds | deep | Crimson | rushed a fight with Gothmog, teleported blind | re-check after every teleport | p=4035 |
| Draugluin (Sire of Werewolves) | 2250 ft | clvl 35 warrior | recalled to 2250 next to a unique | recall arrival is a danger window | p=4751 |
| Drakolisk | 2050 ft | clvl 50 paladin | — | nether breather at 2000 ft | p=3959 |
| Ghost zapped in a wall | ? | same paladin's ghost | waited hours as a ghost | log out, don't idle as a ghost | p=3958 |
| Greater draconic Q | ? | Murdin | forgot to use *Destruct* | summoners: escape or destroy | p=3868 |
| Mouth of Sauron (mana bolt 300–400) | 4000 ft | party | attacked an unknown unique | unknown unique means leave | p=4783 |
| Medusa's summons + plasma bolts | ? | SpaceHunter | escape book destroyed | keep backup escapes (fire burns books and scrolls) | p=page15 t=866 |
| Cherub summoning Ancient White Dragons | 1550 ft | clvl 26–27 party | out-of-depth angel | summoner reflex | p=5206 |
| Hound after Azriel confused | ? (zoo) | clvl ~21 Zal | looted a zoo | don't enter zoos | p=5137 |
| Ochre jelly pit (mana drain) + hasted Shambling Mound | ~500 ft | clvl 16 priest | opened a pit door | pits: leave | p=4861 |
| Azog | −25,800 ft (wilderness) | clvl 16 Half-Orc Warrior | deep wilderness | avoid far wilderness | p=5537 |
| Master yeek | ? | clvl 31 Half-Troll Warrior | ? | (no details) | p=5852 |
| Azrael's nether breath while wielding a pick | ? | clvl 44 paladin | forgot to re-wield | re-wield after digging | p=4138 |
| Carcharoth, Sauron, Ungoliant | 6350, 5250, 3850 ft | clvl 47–49 | — | endgame | p=5856 |

## Posts worth reading in full

1. p=3961 (t=930, all pages): the mangband.org rules in 2002, with PowerWyrm's 2008 status per rule at p=5210 and the "entombed in rock" answer at p=5225/5229.
2. p=3875–3877: queued commands and ESC, for command-queue design.
3. p=5970–5973: time bubbles described by the devs, and "menus don't pause the game".
4. p=4655–4658: the 1.0→1.1 design intent (Angband 3.0.6 base, limited ESP, "two-wide corridors").
5. p=5210: the 1.1-era rule changes (consensual PvP, no keys, the 100 gold on resurrection, ghosts can't dive).
6. t=937 (PK vote, 2006): documents the old PvP culture and why the rules changed. Background only.
7. p=3946: special-artifact generation mechanics, quoted from code.
8. p=4751: warrior death at 2250 ft and a priest's rescue; a good example of recall-arrival plus summoner danger.
9. t=1261 and t=1218: poison deaths, and the 1000 ft nature pit with cytoplasms and hounds.
10. p=4111: how the audit works (flag and remove).

## Coverage

- **Topics read:** 196 of 196, all read in full.
- **Relevant (at least one usable fact):** about 45. **Skipped as social, off-topic or forum admin:** about 150 (introductions, holidays, forum software, polls, IRC, Mac/Vista builds, translation jokes).
- **Gaps:**
  - No topic here discusses bots or automated play. We need the newer stickied rules page (2009+) that Emulord mentions.
  - The live server's `PVP_HOSTILITY` is unknown.
  - "Corridors two tiles wide" and "logged-out characters keep levels static" need checking against the code.
  - Most images and screenshots are missing, e.g. the scene-of-death links (t=1185, t=1219).
  - Several topics are split across `page15`/`page30` captures. All the pages present were read, but whether any pages are missing can't be verified.
