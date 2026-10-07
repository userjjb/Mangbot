# Interim: live-site batch 1 (t=1249 pp.105–164, t=1341 p.2, 9 YASD, 10 King)

URL prefix: `https://www.mangband.org/forum/viewtopic.php?`. Almost all posts are from 2009 (server 1.1.x) unless a year is given.

## New or contradicting findings

1. **Detect effects froze the screen until a keypress** (PowerWyrm): a character died to time hounds while its detection overlay was waiting for a key. So never detect with monsters near, and send ESC right after any detect or look. Check this on 1.5; our C side already ESCs prompts. p=6630. [NEW] [MAYBE-OUTDATED] Pilot rule.
2. **Things that ESP doesn't show:** Quylthulgs, golems and gorgoroth bats (p=6560). Invisible `Q`s need Detect Invisible, not detect monsters. A Greater draconic Q used teleport-to plus summons (p=6531, p=6635). Under the 1.1 limited ESP, big rooms are dangerous (p=6637). [STRENGTHENS §3 Drolem note] HANDBOOK. The shopping list should add Detect Invisible.
3. **Molds and jellies: never melee them, never open a jelly-pit door.** Seen: a Death mold disenchanted gear and then killed; a cluster of poison molds plus "It draws psychic energy from you!" killed a player who had an unused Healing potion and a Teleport scroll. Molds are only useful for testing unknown wands. p=6482, p=6572, p=6576. [NEW] Pilot: never attack or stand next to `m` or `j`, just walk away. *My inference, not from the forum:* the server's auto-retaliate may hit an adjacent mold.
4. **Acidic cytoplasm** at about 800 ft damages every armour slot in turn ("Your X is damaged!"). p=6536. [NEW] Danger list.
5. **The breath rule in numbers:** "expect to die in 2 breaths (or 1 with ≤500 HP)" from monsters at 2500 ft and deeper (p=6559). Scatha: 1365 in two breaths, no rCold (p=6515). Uniques keep full-power breaths for the whole fight because of their HP (p=6699). A shards breath is monster HP/6 capped at 400 (p=6589). [STRENGTHENS §3 depth caps] Navigator: engage a breather only if 2 × its max breath < current HP; never fight a breathing unique without the matching resist.
6. **Never-fight list (additions):** Pit Fiend, Jabberwock, Great Wyrms of Balance, Chaos and Many Colours (p=6709); black `A` (Azriel, "should have made you run at once", p=6727); Gabriel without resist blind ("permablind… cumulative", p=7421); Maeglin, who eats walls and summons (p=6483); anything in *Castle Death* (p=6712). **In our depth band:** Mughash plus kobold shamans at about 950 ft ("confusion-locked", p=6806, p=6807) and an Elder aranea at 600 ft (p=6804). Mystics "avoid at all cost" (p=6758). [NEW/STRENGTHENS §3] Danger list.
7. **A shallow vault killed at 800–850 ft.** The exact messages were "You enter a maze of up staircases." / "You feel there is something special about this level." / "You sense the presence of creatures!", and then a Time hound came out of *Backdoor Surprise* (monsters up to 40 levels out of depth). The fix from the posts: leave at once. p=6536, p=6540. [STRENGTHENS P1, P2, §3 vault rule, A10] Pilot: a special feeling on an up-arrival means take the stairs.
8. **Hound packs:** in the open, "10–20 attacks/turns before you get your next turn" (p=7111). Lure hounds one at a time around a corner (p=6490). Dig an "antisummon hole/corridor" (p=6731). Never fight hound summoners (Carcharoth, Draugluin) in the open (p=6529, p=6433). [STRENGTHENS P6 and the A5 correction]
9. **Resist nexus and Boots of Stability can hurt low and mid-level characters.** A nexus breath teleports you away from a hound pack for free, but Stability made one player tank the whole pack after a summon trap (p=7083, p=7111). Nexus can also drop you into a pit (p=7091). [NEW] Navigator: don't prioritise resist nexus or Stability for the throwaway.
10. **Traps are arrival events.** A teleport trap at 3000 ft landed a player next to off-screen time hounds (p=6158), and summon traps killed two players (p=7083, p=7112). [STRENGTHENS P1] Pilot: after a trap teleport, run the arrival check; path around known traps.
11. **Word of Recall depth:** a player with an uninscribed WoR was recalled to max depth (6350 ft) onto Morgoth. The messages were "You feel yourself yanked downwards!" then "You have a very good feeling..." and death (p=7323, p=7328). Reading WoR prints "The air about you becomes charged..." (p=8468, p=9519). [STRENGTHENS §3 @R] Pilot: check the recall depth before reading, and use the messages to confirm.
12. **A heal lands one turn late.** "Trying to heal after a manastorm, but only triggers the next turn" (PowerWyrm, 2013, p=9538). [STRENGTHENS §1.3, P3, A1] "Quaffing CCW is a waste of a turn unless stunned, bleeding, poisoned, blind or confused" (p=6759). [STRENGTHENS P3]
13. **Nuance to P11 (overhealing).** PowerWyrm "(over)healed as soon as the HP bar went yellow" in his winning fight (p=8465). [CONTRADICTS P11 partly: waste is acceptable when the incoming damage is burst] Pilot: set the heal threshold by the largest expected hit, not by the potion count.
14. **Teleport is not safe deep.** A panic teleport landed next to light hounds, then Medusa summoned hydras (p=7447). "Why teleport? WoD is much safer" (p=6510). *Destruction* is repeatedly named as the right panic button when you're surrounded (p=6637, p=6759, p=6713). Destruction items burn (p=6514). [NEW] Navigator: at depth, carry scrolls of *Destruction* as a backup escape (but see memo §4 on other players).
15. **Damage from an unseen source means leave.** A player's HP "slowly decreasing" from an invisible ethereal dragon while he blamed orcs (p=6466). Messages that start with "It …" ("It breathes nexus", "It magically summons…") mean an unseen caster (p=6716, p=6531, p=6709). Also "You hear a door burst open!" should "always trigger a paranoid response"; vortices see far and destroy gear (p=6638, p=6716). [NEW] Pilot and parser.
16. **Gear state:** ESP kept on a swap weapon was off at the moment of death (p=6670, p=6698); an aggravating weapon needs a swap before stairs or recall (p=6539); fire destroyed staves and Mass Banishment scrolls mid-fight (p=6670). [STRENGTHENS §3 re-check/backups, P12]
17. **Hunger in real time.** A Half-Troll warrior away from the keyboard "can't last 2 minutes without a snack" and was starved (p=7352); speed makes it worse (p=7358). A character starved at 1500 ft after dropping its food (p=6809). [STRENGTHENS §5 food row] Pilot: eat at "You are getting hungry."; never drop the last food.
18. **Distraction, ghost and rescue deaths:** AFK after detecting a "novice warrior far away" (p=7112); an IM popup, then walking onto a known trap (p=7112); a ghost death, "Never get distracted" (p=6527); a key-mashing ghost left safety (p=7447); rescuers keep dying (p=6530, p=6544, p=6716). [STRENGTHENS P8, P14, P15, §4]
19. **Multiplayer economy:** after about 3 years of server uptime "only the crappiest artifacts remain", so look for ego items instead (p=8391, 2010). Artifacts are lost to inactivity (p=8465). Speed boots sold player to player for 3.5M (p=7694). Morgoth "kept moving away" when another player was in his aggro range (p=9231, 2013). [NEW / STRENGTHENS §4] Navigator: don't plan around artifacts.
20. **Parser strings** (quoted verbatim in the posts) [NEW]: "You feel yourself moving slower!", "Your mind is blasted by psionic energy.", "You have been stunned." (quake crush), "You cannot see!" / "You can see again." (p=9519, p=6458); nether: "You feel your life draining away!" vs "You keep hold of your life force!"; time: "You feel life has clocked back." / "You're not as strong as you used to be..."; "Energy drains from your pack!" (p=6630, p=6531, p=9519); "Some of your Scrolls of X were destroyed!", "Your X was disenchanted!", "The staff has no charges left." (p=6670, p=6572, p=6637); monster-health ladder "shrugs off the attack" (resisted) → "grunts with pain" → "cries out in pain" → "screams in pain" (p=8468, p=6533); "X has left the game.", "X bumps into you." (p=6515, p=6530); pseudo-ID "You feel the X in your pack is excellent/special/terrible..."; "You are getting hungry." / "You have gorged yourself!"; "Looks like any other level." (p=9519).

## Death catalogue (new deaths)

| Cause/monster | Depth | Char | Mistake | Lesson | URL |
|---|---|---|---|---|---|
| Time hound from a vault | ~800–850 ft | low-level caster | stayed on an up-arrival "special" level | leave on arrival | p=6536, p=6540 |
| Elder aranea | 600 ft | clvl-13 mage (Ironman) | approached a `U` + escort | range, or leave | p=6804 |
| Mughash + kobold shamans (confusion) | 950 ft | Ironman character | left the `>` to explore for gold | stay by the stairs | p=6806 |
| Molds (poison, psychic drain) | ? | ? | meleed a mold cluster; Healing and teleport unused | avoid `m`; use your escapes | p=6482 |
| Ethereal dragon through a wall (confusion) | 1900 ft | clvl 32 | lingered by a vault; 1 Healing, no staff | leave early; carry backups | p=6809 |
| Starvation | 1500 ft | clvl ~27 | dropped food; INT drained | never drop the last food | p=6809 |
| Starvation while AFK | ? | Half-Troll Warrior | left the keyboard in play | log out | p=7352 |
| Nexus hounds from a summon trap | ? | ? | Boots of Stability blocked the nexus teleport | rNexus is not always good | p=7083 |
| Time hounds after a teleport trap | 3000 ft | ? | trap teleport | treat it as an arrival | p=6158 |
| Time hounds while detection froze the screen | deep | ? | used a detect with monsters near | ESC after detects | p=6630 |
| Invisible ethereal dragon | orc pit | mage | ignored slow HP loss | unseen damage means leave | p=6466 |
| Greater draconic Q teleport-to, then Dracolich | deep | ? | detected monsters, not invisibles | Detect Invisible | p=6531 |
| Carcharoth: darkness (blind) then nether | 6100 ft | Domiano | forgot to wear Umbar; healed at ~2 HP | check resists before a fight | p=6457, p=6458 |
| Draugluin-summoned hounds | 4050 ft (greater vault) | Poundy | 2 turns to react, did nothing | escape on the summon | p=6433 |
| Azriel nether | deep | Michailski speed-diver | no rNether; didn't use Teleport Other | flee a black `A` | p=6699, p=6713, p=6727 |
| Druj teleport, then a mob | wilderness | Prosper | ESP was on the swapped-out weapon | keep ESP fixed | p=6670 |
| Uninscribed WoR onto Morgoth | 6350 ft | Induriel | wrong recall depth | inscribe and check the recall depth | p=7323 |
| Medusa hydras after a panic teleport | deep | ? | teleported into worse; ghost mashed keys | stay put as a ghost | p=7447 |

(Omitted, since they only repeat the findings above: deaths to Death mold p=6572, Great Ice Wyrm p=6557, Nether/Plasma/Impact hounds p=6759/p=6758/p=7478, Great Swamp Wyrm p=6802, Scatha p=6515, Pit Fiend p=6709, Gabriel p=7421, rescuers p=6530/p=6716, and deep caster fights p=6532, p=6546, p=6580, p=6637, p=6647.)

## Posts worth reading in full

1. **p=6536 + p=6540:** a shallow-vault death with the exact arrival messages. It's a test case for P1/P2.
2. **p=6630:** detection freezes the screen (check on 1.5).
3. **p=6559 + p=6560:** the "2 breaths" rule, ESP blind spots, and the look command.
4. **t=2115 (p=9519, p=9538):** a warrior's full win log with timestamps (message corpus), plus the heal-lands-late critique.
5. **t=1636 (p=7083–p=7111):** the resist nexus / Stability debate and the hound-pack tempo.

## Coverage

All 21 topics were read in full:
- t=1249 pp.105–164 (57 posts, p=6458 to p=7495);
- t=1341 p.2;
- YASD t=1503, 1540, 1548, 1562, 1600, 1636, 1646, 1673, 1678;
- King t=115, 118, 119, 122, 1724, 1827, 1860, 2052, 2115, 2161.

Nothing was unreadable. Screenshots and videos in t=119, t=2052 and t=2161 are missing (images only). t=1341 p.2 is almost empty (only p=8391 has content). Most King posts are 2003–2004 (0.7) and mostly social; p=589 ("wearing the crown without being king kills you") and p=581 (party members share the king kill) are trivia.
