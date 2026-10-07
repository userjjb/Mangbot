# General Discussion, chunk 1 (t=2..729): what it adds

Corpus: `corpus/general_1.txt`, 236 topics, 2002–2009 (almost all 2002–2007, server 0.7.0–0.7.2a, then
1.0.0 from Sep 2007). This chunk is mostly social, admin, compiling help and the player-to-player
market. I read every topic. The tags compare each finding with
`memos/2026-09-26-forum-distillation.md` (the "memo"), HANDBOOK.md and notes_players.md.
**[code ✓]** means I checked it in our 1.5 source (`github/src/server`). URLs are
`https://www.mangband.org/forum/viewtopic.php?p=N`.

## Top findings

1. **A second Word of Recall cancels the first.** Reading, zapping or casting recall while one is
   pending cancels it ("A tension leaves the air around you") (p=3022, 2004)
   **[code ✓ `spells2.c:1197`]**. Pilot rule: never repeat a recall command while `word_recall` is
   active, for example when a retry follows lag or a missed message. The same action is the way to
   abort a recall deliberately. [NEW] → Pilot rule + HANDBOOK.

2. **Game time runs slower the deeper you are.** Berendol: "If you play deeper, turns go by slower"
   (p=1443, 2003). Timed effects last up to 10,000 game turns, which is about 100 minutes in town and
   much longer deeper (p=1410, 2003). The code agrees **[code ✓ `tables.c:2200` `level_speeds`: town
   7500, 1000 ft 10500, 2000 ft 12500, 4000 ft+ 20000; used as the energy cost per action]**. So one
   player turn at 4000 ft takes about 2.7× as long in wall-clock time as in town. Pilot timers (rest,
   recall countdown, "enemy turn" windows, lag thresholds) should count game turns or energy, not
   seconds. [NEW] → Pilot.

3. **Food is not eaten in town** unless you're gorged **[code ✓ `dungeon.c:1123`]**. Crimson: to get
   rid of "Gorged", go down to 50 ft (p=1738, 2004). So idling in town costs no food, and a gorged
   character in town stays gorged. [NEW] → HANDBOOK and the Pilot's hunger logic.

4. **Resist sound protects against more than sound breath.** It prevents the *stun* from gravity,
   plasma, force, water bolt or ball and ice bolt, but doesn't lower their damage. The 0.7.2
   `GF_GRAVITY` code is quoted in the post (p=1619 2005, p=1704 2007, p=1715 2007). Resist nexus
   blocks the monster "teleport level" spell (p=1619). Gorlim's water bolts stun-locked a player
   without it (p=1620). Plasma hounds killed a mage *through Globe of Invulnerability*: their cuts
   built up to a knockout while HP stayed full, and he died when GoI ended (p=1710, 2007).
   [CONFIRMS memo §1.5 and the rSound checkpoint, with more reasons] → Navigator (rSound moves up the
   priority list).

5. **Summons and double actions kill more veterans than hounds do on arrival.** Warrior, a long-time
   player (2007): there are "relatively few deaths to hounds on recall/stairs, especially compared to
   'summoned X on me', 'breathed poison twice in a row', 'confused and blinded me'" (p=1757). Ashi:
   because the game is realtime, a monster "often" gets a second or third action before you can react
   to its first, so "1 in 3" breathers double-breathe (p=1766, 2007). A Great Wyrm of Balance (GWoB)
   breathed twice *while being meleed* and killed a clvl 38 (p=1581, 2004).
   [CONTRADICTS in part memo §1.1, which calls arrival hounds the top killer. Veteran opinion; it
   reinforces P3's extra-turn margin and P6.]

6. **Hound clearing on recall was added late.** "Safe recall: when you recall, you won't have
   hounds or uniques around" was written by Jug for IronMAngband in Oct–Dec 2005 and then ported by
   the Argentine team in 2006 (p=242, p=244). Before that, recall and stairs cleared nothing, which
   explains the 2002–2005 "recalled into time hounds" deaths (p=1577, p=1757). Our 1.5 clears on
   down and recall **[code ✓ per memo]**. So for recall-arrival deaths in old YASD posts, weight them
   as [MAYBE-OUTDATED]. Up-stair arrivals are still unprotected. [NEW: version history] → Advisor
   memo.

7. **Deaths from being teleported into something.** A player was teleported to the door of an
   out-of-depth chaos beetle pit at 2800 ft and died there (p=1746, 2007). A *Ring of Teleportation*
   used as an escape fired again just before the player took it off, and put him back next to Pazuzu
   (p=1614, 2005). Veteran framing: "Playing a level means you could run into stuff that teleports
   you or you might need to teleport yourself. That's a risk you take" (p=1752). Rules: (a) never use
   random-activation teleport gear as the escape; (b) after any teleport, run the arrival scan (memo
   P1 already covers this). [NEW (a), CONFIRMS P1] → Pilot.

8. **Look ahead and detect before stepping.** Berendol: "Whenever you're diving you should always use
   the L command to look ahead", check other directions now and then, and use mapping. He died to a
   summon rune in a vault (it summoned a GWoB and a drolem) because he hadn't detected traps (p=1581,
   2004). Rali: instadeaths come from "getting pushed off of stairs from hounds, getting surrounded by
   a quick summon or two, or breathed on from offscreen" (p=1579). [CONFIRMS the memo's vault
   doctrine; NEW: offscreen threats] → Navigator: buy Magic Mapping or detection; Pilot: scan the full
   map or level, not just the screen.

9. **Out-of-depth vaults start shallow.** Small "+"-shaped vaults at 1000–1200 ft held "page 4
   uniques and great wyrms" (p=1539, 2004), and one held Thuringwethil and the Tarrasque (p=1632,
   2006). A Phoenix in a vault at 900 ft killed a char (p=1536). [CONFIRMS memo "vaults: don't"].

10. **Good-citizen rules the memo doesn't have yet** (mangband.org, 2002–2005):
    - "Do not sell things that lay around in town" (p=1321). Using or selling drops from obvious level-1
      characters near town is frowned upon (unwritten rule 8, p=1375). The audit flags items "found" in
      or around town (p=1430).
    - Storage characters are banned (rule 4, p=1375).
    - The audit flags sudden jumps in wealth, and Crimson checks by hand before deleting anyone
      (p=1534, p=1427).
    - Inactive characters holding artifacts were deleted (p=191–195, 2005). Houses are reclaimed
      after roughly 6–12 months of inactivity (p=1424, p=1425).

    Pilot rule: **don't pick up items lying in town** (0 ft and wilderness near town) unless the
    character dropped them itself. [NEW] → Pilot rule + HANDBOOK etiquette.

11. **Player-killing threats, and where to idle.** mangband.org had a "pretty much open pkilling
    policy" (Domino, p=1344, 2002). Later the rule on at least one server became no PK anywhere on
    the 0 ft town level (Berendol's server, p=180, 2004). Some things happened to idle characters:
    - one left idle "on main street where it's safe" was killed at range by bolts (p=178);
    - a rogue stole from an idle player (p=1341);
    - PKers lured victims with trade offers ("I'll sell you a whip, meet me behind store 5") (p=176);
    - PKers talked newbies into using a *Summon Monster* staff at 50 ft, led hound packs onto
      victims, and cast *Destruction* on their level (p=1390).

    Rules: idle inside a shop; never accept a meeting, item or staff from another player; stay
    non-hostile. [CONFIRMS P14, NEW threat details] → HANDBOOK + Pilot (ignore trade and chat
    entirely).

12. **Automation and "cheating"**: this chunk has **no borg or bot policy**. The closest thing: a
    player asked for a macro that runs while ignoring disturb, to escape a monster. Warrior: "It would
    practically be cheating. Since when you run you move faster than the monsters" (p=1734, 2007).
    Crimson (p=1736) gave the legitimate trick: running works whenever you can't *see* the monster,
    for example if you're blind or have taken off your light. On 1.5 the running speed bonus applies
    only in town **[code ✓ `dungeon.c:950` `RUNNING_FACTOR` only when `dun_depth==0`]**. So a Pilot
    that runs normally is fine, but don't script around disturb. [NEW] → Architect (etiquette).

13. **Lag and connection facts.**
    - Latency under 250 ms is playable and 150 ms is "golden"; a client uses about 6 KB/s at peak
      (p=99, 2003).
    - The client's latency meter turns purple on packet loss. Under TCP, a lost packet turns into
      a delay, not a drop (p=3003, 2003).
    - "A lot of monster-induced lag is due to the server drawing and redrawing stuff" (p=1754, 2007).
      So lag spikes when many monsters are in view, which is exactly the dangerous moment.
    - Right after a death the server or client pauses for several seconds while it sends an update
      (the "X was reborn" spam for uniques). A player's ghost was killed during that pause
      (p=3000–3001, 2003).
    - A server crash rolls you back to the last save, about 1 minute earlier (p=1653, 2006).

    [CONFIRMS P7/P15; NEW: the lag-with-monsters correlation and the rollback] → Pilot: treat a
    screen full of monsters as a lag risk in its own right; after a reconnect, re-read the full state.

14. **Ways to die in the early game, and pace.**
    - Crimson: "90% of characters die prior to level 10" (p=1360, 2002).
    - Domino's warrior fast start (p=1327, 2002): roll for STR 18/50 (3 blows with a whip); sell the
      starting weapon and buy a whip plus all the cheap AC you can (about 20 AC); scum 50 ft until you
      can afford Word of Recall; then take every `>`, picking up items near the stairs, down to about
      1000 ft. You come back at clvl 15–20 with 3–4k in loot, but "only around 1 in 10 characters
      makes it".
    - Froof takes `>` down to 1200 ft and then waits for low resists or Free Action. Maegdae's reply:
      carrion crawlers and a basilisk at 1200 without Free Action (p=1325–1326).
    - Berendol "power-level[s] a new character to 20 around 1400'" (p=1754, 2007).

    [CONFIRMS the memo's pace and Free Action checkpoint; the 1-in-10 figure is useful for expected
    throughput] → Navigator.

15. **Death penalty numbers.** Avenger: on death "I lose half of my total experience" (t=369 p.2,
    2007). Huma lost 9 levels over two PK deaths (p=176, 2004). A killed ghost loses everything (p=1393
    onward). House keys often drop and vanish on death (p=1753 "5–10 times", p=1710). [REFINES memo P15
    "3–5 levels"] → HANDBOOK.

## Findings by theme

### Escape, healing, status
- Poison while at low HP: a clvl 27 paladin had to cast CLW 20+ times just to stay at 30–55 HP until
  the poison ran out. Effects stack up to 10,000 game turns (p=1411, p=1410, 2003). Carry Cure
  Poison / CSW, not just CLW. [NEW detail]
- Chaos attacks (0.7.2 code): unless you resist confusion, you're confused for 10–30 turns, and this
  stacks. Without both rChaos and rNether you lose EXP (Hold Life saves 75%) (p=1409, 2003).
  [MAYBE-OUTDATED]
- Feather Fall reduces gravity damage (×6/(6..12)) but doesn't stop the teleport or slow (p=1704,
  2007; code quoted). [NEW, minor]
- A Death Knight summoned gravity hounds, which caused an instant knockout, and the player was warped
  away at 50/700 HP. Ar-Pharazon's summoned gravity hounds did the same to a player with 900 HP
  (p=1478, 2003). [CONFIRMS P6 and rSound]
- A GoI mage vs Morgoth: earthquakes stun through GoI; "don't prefix macros with more than one \e,
  don't spam heals" (p=1772, 2007). [CONFIRMS P11]

### Monster depths (0.7.2 list, 2004; newer lists moved several deeper, e.g. Greater Titan 2300→3300 in the Ironman variant, p=1622) [MAYBE-OUTDATED for 1.5]
- p=1593/p=1601: Drolems 2200 ft; Dracolich and Dracolisk 2300; graveyards (undead pits) 2500; time
  hounds 2550; Druj 2750; GW* (the Great Wyrm family) 3350; Aether hounds 3750; group Hell Hounds
  4150; nothing new that isn't a unique below 3750.
- Lone Hell Hound 1750 (400 HP). Carrion Crawler alone 1250, in groups 1700. Gnome mages in groups
  from 750. Novice parties (groups of novice warriors, mages, priests and rogues) from 250–400.
- Pazuzu, Cantoras and Morgoth are +30 speed; an aggravated Morgoth is +40 (p=1596, p=1598). Greater
  Titans and Pazuzu do more melee damage than Morgoth (p=1458). None of these are relevant to the
  throwaway's depths.

### Warrior and combat numbers (0.7.2 code, 2003) [MAYBE-OUTDATED]
- Criticals are driven by weapon weight: a superb hit needs 5 lb or more, a \*GREAT\* hit 25 lb or
  more. To-hit chance = skill + 3×(to-hit bonus), against 3/4 of the monster's AC, with 5% automatic
  hit and 5% automatic miss (p=1468).
- Slay multipliers: animal and evil ×2; undead, demon, orc, troll, giant and dragon ×3; Execute
  Dragon ×5 (p=1414).
- Mithril and adamantite armour ignore acid (p=1474).
- Elven gloves give regeneration (p=1720).
- An Amulet of Terken (the posts spell it Terkin/Terken) gives searching, FA and SI plus one random
  power (p=1795).
- Resist dark came only from Shining or Power DSM or from artifacts (p=1651, 2006).
- Class and race: newbies should start as warriors (p=1328). Half-Troll warrior is valued for
  STR/CON, HP and sustained STR (p=1438). End-game HP converges to about 1000–1100 for most combos
  (p=1701, PWMang 2007).

### Money, shops, economy
- To price an item, offer one to a shop and read the offer. Never sell to a player below the shop's
  offer (Crimson p=1385, p=1808).
- Sell to a shopkeeper of your own race, with a deep purse, while you have high CHR (p=1533).
- Enchanting is priced per item, not per stack: arrows 5 au per plus (p=1387).
- Sell a Scroll of Acquirement to the shop (about 92k) rather than reading it. The item it makes is
  usually worth less (p=1566, p=1568). The posters later corrected this: Acquirement's result scales
  with depth, so read it at the bottom (p=1572).
- Books out of depth are worth a fortune: Raal's Tome found at 800 ft sold for 450k (p=1532). →
  Navigator: carry unknown books to the shop.
- Player-market reference prices (2007, mangband.org): +10 Ring of Speed 1M, Balance DSM 1M, stat
  potions 8–10k (p=1845–1848, p=1817). Irrelevant for a throwaway except as a sense of scale.

### Multiplayer and server facts
- Recall inscriptions and wilderness: an `@R` recall depth in unvisited wilderness is replaced by depth 1 (50 ft); a depth deeper than max_depth is clamped to max_depth
  **[code ✓ `spells2.c:1180-1186`]**. Not from the forum; found while checking finding 1.
- Keys stack and lose their house link unless inscribed differently (0.7.2 bug, p=1533). Keys drop
  on death. [MAYBE-OUTDATED; matters only if we ever buy a house]
- The town and wilderness trees regrow in fixed spots; the main server's town reset daily in 2007
  (p=1723). There was a daily midnight-EST restart in 2003 (p=45). Plan for a disconnect or restart
  at any time.
- Auto-retire after killing Morgoth: 6000 game minutes (mangband.org 2003, p=1447–1448).
- A server handled about 100 clients (p=1455).
- Quitting in town is instant (the PKer trick in p=207, 2005). [CONFIRMS P8]
- Unique kills are shared. Another player's breath can steal your kill (no drop, no XP) (p=2989).
- Easy variants (easy-high-speed, and the 0.7.5 "soft death" fork that loses 1/4 exp) existed but
  weren't official (p=221, p=294). Ignore their mechanics.
- The Crown of Morgoth kills you through GoI (p=1486). Curiosity only.

### UI and automation
- A typo of `t` (take off) for `T` (tunnel) with a full pack dropped a warrior's rings, armour and bow
  on the floor mid-fight. Afterwards he inscribed all his gear `!k!v!s!d!t` (p=1666–1668, 2006).
  Pilot analogue: whitelist the commands allowed in combat; inscribe worn gear `!t!d!k` as cheap
  insurance. [NEW]
- Stone to Mud as an emergency "dig a safe tunnel" tool failed because the wand was empty (p=1666). →
  Check charges (memo P10).
- A recall that fires mid-run leaves you still running in town (p=1370, 2002). The Pilot should
  expect movement to continue after the level changes.
- Per-character macro files load in this order: pref, user, pref-sys, font/graf-sys, user-sys, race,
  class, name (p=1564). Not needed for tool mode.
- Berendol's paladin macro and inscription set (p=199) is a clean example of the `@q1/@u2/@w1` tag
  scheme. [CONFIRMS notes_players]

## Death catalogue (the few deaths described)

| Cause / monster | Depth | Char | Mistake | Lesson | URL |
|---|---|---|---|---|---|
| Recall into hounds, then the ghost landed on ethereal hounds, then drifted up into chaos hounds | 3600 ft | clvl ~38 paladin | recalled deep (before safe recall existed) | ghosts die fast; float up at once | p=1577 |
| GWoB double breath during melee | ~3500 ft | clvl 38 | assumed melee prevents breath | breathers act between your blows; escape by numbers | p=1581 |
| Summon rune in a vault (GWoB, drolem) | deep | clvl ~38 | no trap detection | detect before entering vault squares | p=1581 |
| Plasma hounds: cuts lead to knockout through GoI | deep | mage (Induriel) | no rSound | rSound; GoI isn't status immunity | p=1710 |
| Chaos beetle pit after teleport | 2800 ft | Clive | played an out-of-depth pit level | leave levels with visible zoos or pits | p=1743, p=1746 |
| Phoenix in a vault | 900 ft | FizII (low level) | "only 3C and one B left" | shallow vaults are lethal | p=1536 |
| Mystic, in the wilderness, after two PK deaths | wilderness | Huma (lost 9 lvls) | kept playing at low HP after the deaths | re-gear before you go back | p=176 |
| Hydras paralyzed him | 1850 ft | Anyar | no Free Action | FA by 1000–1250 ft | p=1561 |
| Time-hound summon during the post-death server pause | deep | Toast | fought a GMM that summons | never melee summoners (memo P6) | p=3000 |

## Posts worth reading in full
- p=1754, p=1757 (t=369, 2007): Berendol and Warrior on what really kills veterans and on lag from server redraws.
- p=1577–1601 (t=333, 2004): the difficulty debate; monster depth table; L-look doctrine.
- p=1375 (t=283): the "Unwritten Rules FAQ" (2000), the historical etiquette code.
- p=1390 (t=286, 2003): a PKer's catalogue of indirect kill methods (so the Pilot knows what not to accept).
- p=1619, p=1704, p=1715 (2005–07): what rSound, rNexus and Feather Fall actually block.
- p=1327 (t=269, 2002): warrior speed-start recipe and survival odds.
- p=1666 (t=351, 2006): a warrior's near-death at 6300 ft: empty wand, typo drops, tele-level into worse.
- p=1734–1736 (t=367, 2007): running vs disturb; the only "is this cheating" discussion here.
- p=3000–3003 (2003): post-death pause and the latency/packet-loss meter.
- p=1468 (t=308, 2003): to-hit and critical formulas (0.7.2).

## Coverage
- **Topics:** 236 read (every one opened at least far enough to judge it).
  - About 45 had usable content.
  - About 190 were irrelevant: admin notices, compiling or Linux help, forum spam, PK drama, trade
    ads, jokes.
- **Moved stubs with no content:** t=2, 6, 24, 34, 39, 47, 49, 54, 55, 57, 709, 722, and importantly
  **t=268 "Mangband.org rules"**. The official rules text is not in this chunk, and the rules post
  referenced by p=1366, p=1368 and p=1076 is missing. Worth searching the later chunks and the
  archive for it.
- **Partial topics:** t=38, t=287, t=314, t=369 and t=716 have only pages 1–2 captured; t=281 has no
  reply.
- **Gaps:** there is no bot, borg or automation policy anywhere in this chunk. No warrior deaths at
  0–1000 ft are described. Version changes are mentioned only indirectly: 0.7.2a in Jan 2003 (new
  colours, auto-password, a `cmd_destroy` patch in Mar 2004), safe recall in IronMAngband in 2005,
  and 1.0.0 in Sep 2007.
