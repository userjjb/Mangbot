# General Discussion, chunk 3 (t=1414..2312): distilled notes

Posts date from 2008 to 2020. Most fall in 2008–2011, when the server ran versions 1.0/1.1.x (1.1.2 from 2009; a 2011 server list shows every server at 1.1.2). The one exception is a 2019 post by Flambard about 1.5.0alpha. Tags are relative to the Part 1 memo (`memos/2026-09-26-forum-distillation.md`) and to notes_players/HANDBOOK. **[code ✓]** means I checked the claim against our 1.5 source in `github/src/server`.

## Top findings

1. **Time bubbles ("bullet time") exist in 1.5 and the Pilot can switch them on.** [NEW] [code ✓] In the dungeon, `base_time_factor()` (`xtra2.c:5164`) slows time **5×** (`CONSTANT_TIME_FACTOR 5`, `mdefines.h:271`) whenever HP% ≤ `hitpoint_warn`×10. The slowdown covers the player's whole bubble, monsters included. So it is not a speed advantage, but it gives 5× the wall-clock time to react. `hitpoint_warn` is a client setting (sent as `settings[3]`, `c-init.c:716`; `net-game.c:1478`), and its default is probably 0 (off). If `hitpoint_warn` > 9 and no awake monster is in line of sight, time runs at normal speed. Resting with nothing in LOS runs at 10× (`MAX_TIME_SCALE 1000`) and running at 5× (`RUNNING_FACTOR 500`). There is no scaling in town. The design was discussed in 2009, with the rationale "slower where it's currently too fast" (t=1601 p=6808, p=6812, p=6813). **Pilot rule:** set `hitpoint_warn` to about 5–6 so that any fight below 50–60% HP runs in slow motion. This is the best available counter to lag deaths (memo P7). Caveat: other players within `MAX_SIGHT` on the same level share the slowest bubble, so we also slow nearby players while hurt. The feature is designed that way, but it is worth knowing.
2. **Deeper levels run slower in real time.** [NEW] [code ✓] `level_speed()` (`xtra2.c:5109`, table `tables.c:2200`) is the energy each action costs. It rises from 9000 at 50 ft to 10600 at 1000 ft, 12500 at 2000 ft and 20000 from about 4250 ft. So a turn at 4000 ft takes about twice the wall-clock time of one at 50 ft. Zal (serina): "fighting Saruman at 2000 feet and you might get 0.3 seconds to react. At 6350 you might get 1 full second" (p=6224, 2008). **Pilot:** calibrate the lag gate and reaction budgets per depth. Shallow levels give the *least* reaction time.
3. **Running used to be a free speed boost; in 1.5 it isn't.** [CONTRADICTS: older forum lore that you can outrun monsters by running out of LOS] Before time bubbles, running gave "a temporary speed boost" that let players escape monsters of equal speed. With bubbles, "if the player runs, all monsters in the same time bubble run", so escaping needs real speed (t=1601 p=6808, p=6813, 2009). In 1.5, running is blocked while a monster is in view, and the bubble speeds up the monsters nearest you too **[code ✓ `base_time_factor`]**. **Navigator/HANDBOOK:** running away is not an escape from an equal-speed chaser. Use Phase or Teleport.
4. **Shallow lesser vaults can hold monsters 40 levels out of depth from 250 ft, with no permanent walls.** [CONFIRMS memo §3, with more detail] Named vaults: "Miniature Cell" (5 `8` squares), "Zoo of Concentrated Death" (25 of them), "Backdoor Surprise". They are "vaults designed to kill you" (Chris Atenasio). A Dreadmaster at 300 ft killed two low-level players. In 2008, pass-wall escapees from these vaults (Tselakus, Dreadmaster, ethereal hounds, nether wraiths) killed clvl 28–32 characters at 1400–1550 ft. PowerWyrm: "you almost need SI and *des* (or at least tele) below 1000ft" (t=1414 p=6031, p=6094, p=6103; t=1530 p=6338, p=6340; t=1568 p=6573). **[code ✓]** All of these are still in 1.5 `lib/edit/vault.txt` as lesser vaults (room type 7): N:36 "Miniature Cell", N:128 "The Shaft", N:129 "Backdoor Surprise", N:130 "Zoo of Concentrated Death", listed under "# Vaults designed to kill you". Symbol `8` = monster up to 40 levels OOD. **Navigator:** a pass-wall or invisible unknown `G`/`W`/`p` shallow means leave the level.
5. **The wilderness is deadly for a throwaway, even near town.** [NEW, strong] Deaths and near-deaths there:
   - 22 ethereal hounds breathed on a player the moment he stepped into a new wilderness sector (t=1571 p=6591);
   - a skull druj and then a greater basilisk, at night (p=6387);
   - a drolem and a "gigantic pack of ethereal hounds on the grasslands" after a teleport (p=6390);
   - migrating fruit bats took a clvl 9 to 0 HP on entering a sector (t=1675 p=7337).

   Wilderness "levels" are deallocated when empty, but their monsters are not (PowerWyrm, t=1590 p=6756, 2009). **Navigator doctrine:** never leave town except by `>`. The Pilot should never walk off the town map edge.
6. **Up-stairs arrival death, verbatim.** [CONFIRMS memo P1/P2] "You enter a maze of up staircases. You have a superb feeling about this level. The Aether hound breathes frost… You die." (t=2144 p=9689, 2014). PowerWyrm's comment on it: "Listen carefully to the voice of wisdom!" The ~12 message lines make a good parser test case.
7. **Auto-retaliate on arrival next to a hound wastes the first turn. A queued command bypasses it.** [CONFIRMS memo §1.3, and adds the fix] "you cannot be instagibbed unless the autoretaliator wastes the first turn… The only way to avoid it is indeed to macro an action, like *destruction*, to ensure that you will bypass the autoretaliator and act before the hounds" (PowerWyrm, t=2142 p=9685, 2014). **Pilot:** after any level change, send the planned first action (step back onto the stair, or phase) at once rather than idling, because idling lets auto-retaliate spend the turn.
8. **ESC and `\e` clear the server command queue.** [CONFIRMS notes; now a stated 1.5 fact] Flambard (dev, 2019): "pressing ESC clears the command queue… \e in macros also clears the command queue". This is unchanged in 1.5.0. Zal: a queued 10× fire macro would otherwise block an emergency quaff (t=2206 p=9942, p=9944; t=1515 p=6228, p=6239). **Pilot:** start every emergency command with an ESC or queue-clear so a pending batch of actions can't delay the escape.
9. **1.5 pick-up/stay semantics.** [NEW] [partly MAYBE-OUTDATED] In 1.5.0alpha, `g` always picks up. `,` picks up if `auto_pickup` is off and does nothing if it is on. There is no "stay and do nothing" command when auto_pickup is off (Flambard, t=1897 p=9922, 2019). Thorbear (2011): holding the stand-still key "enables the possibility to have monsters next to you without attacking them… won't auto-attack" (p=8747). **Pilot:** a stay/hold command queued each turn suppresses auto-retaliate, which is useful for not attacking (e.g. near other players' pets or townies) and harmful if sent by accident while fighting.
10. **Targeting bug: a stale remembered target makes aimed devices fire at your own square.** [NEW] Fix: "Press * then ESC… (or log out and back in)" (PowerWyrm, t=2107 p=9462, 2013). **Pilot:** after "Nothing to target" or an odd device result, clear the target and re-target.
11. **Spell/breath range 18, sight 21.** [NEW] [code ✓ `MAX_RANGE 18`, `mdefines.h:194`] Zal's 2008 tests: monsters "can breathe, cast and use any abilities if they're within 18 squares"; line of sight is 21; a light crossbow fired 26 squares (t=1515 p=6224). **Pilot:** threat radius for breathers and casters = 18 squares in LOS.
12. **Rule: no item transfers between your own characters, and no free gifts to low characters.** [CONFIRMS memo §4, with the exact policy] "share large numbers of items between their own characters… several characters have been deleted" (Warrior, admin, t=1532 p=6365; more deletions p=7721, 2009). Trades must use "shop selling prices… or trade like 1:1" (Ace, p=7460). A report in 2010 (t=1835) concerned giving a staff of destruction to a clvl 15 "for either unfair use or storage". **Navigator:** our tool characters must never pass items or gold to each other.
13. **Artifacts can't be dropped in houses, and hoarding them is discouraged.** Inactive owners have their artifacts reset after about 60–90 days (forum belief). [NEW] (t=1734 p=7756; t=2154 p=9763, p=9768; forced retirement of winners, t=2153 p=9755). This matters little for a throwaway, but a found artifact is a prime "sell it" item.
14. **Winning triggers forced retirement.** [NEW] [MAYBE-OUTDATED, 1.1.x code quoted] Killing Morgoth makes every party member of clvl ≥40 on that depth a winner, which starts `retire_timer` (t=2153 p=9754). One winner lost 3 PDSMs to auto-retire (t=2152 p=9750). This is irrelevant for now, but the Navigator should never join a Morgoth party.
15. **Heal-potion scarcity sets the whole economy.** [NEW] In 2013 the player-market price of Healing was "$20,000 gold or a stat pot"; high players buy Healing potions from low characters (t=1568 p=9500). PowerWyrm: "Once you're able to dive to 3500ft, money is not a problem", since speed rings (rarity 1) sell for millions (p=9617). **Navigator:** a Potion of Healing found shallow is worth more to keep, or to sell to a player shop, than to sell to the NPC shop. For a throwaway: keep it.
16. **Low-level money and ID loop (Emulord, "I rarely die").** [NEW, fits the HANDBOOK] "run around 50-150' collecting potions and scrolls; run back up to town and sell them unID'd, but ID wands, staves, rings and amulets; then, buy potions of cure crits, so you dont get killed from confusion by low level mages… get enough cash for a staff of teleportation, then I take orc pits" (t=1574 p=6618, 2009). **Navigator doctrine** for the first shopping cycles.
17. **Level-1 party dive kit (Zal, 2010).** [CONFIRMS HANDBOOK and memo shopping list] Carry "4-6 rations and 15000 turns lantern oil", Phase Door and 1–2 CSW. First restock: CSW (5–10), Phase (10), enchant-to-dam scrolls (5 per melee character), a spare WoR "in case of fire (burning)", 2–3 Heroism. "Take no chances… (phase door just before dying is too late)" (t=1765 p=7959; t=1825 p=8281).

## Findings by theme

### Server/version history (for judging old advice)
- By early 2009 MAngband had "synched up with Angband 3.0.6". The changes it brought ([MAYBE-OUTDATED] the 1.1.x list; t=1568 p=6567, p=6569, p=6573, p=9500):
  - player shops;
  - stacking staves;
  - endless recharging;
  - **limited ESP** instead of full ESP, which "slows the playing a lot, since you can't now tell what a 'special' feeling on a level is";
  - no Globe of Invulnerability; Rift added, and abusable;
  - paladins lost Clairvoyance;
  - high rogue spell failure rates.
- PowerWyrm (2014): MAngband now has "manual looking/targeting", which lets you identify an unknown `D` (TomeNET lacks it, and he died to Glaurung mistaken for Smaug; t=1568 p=9656). **Pilot:** use look on unknown breathers.
- Amulets of the Magi no longer carry random high resists. Trickery is the new standard, and Balance DSM + Trickery gives six high resists (t=2111 p=9482, p=9489, 2013).
- Speed stops mattering for energy at about +45; above that it only helps running (t=1508 start=15, PowerWyrm 2008) [MAYBE-OUTDATED].
- Known gamebreaking bugs in 1.1.x: #651 (gravity) and #1016 (spell frequency) (t=2098 p=9421). Earthquakes ignore permanent walls and move you anywhere in the quake radius (t=1508 p=6195). After a quake, redraw the screen with Ctrl-R because walls display wrongly (p=page30, 2008). **Pilot:** after a "quake" message, re-request the map.
- The official server has been reset several times (e.g. "Fatal crash on the new instance", 2011; reset in 2013). A crash in 2011 wiped the whole −200 ft wilderness sector, including houses (t=1910 p=8804). A full disk in 2010 lost savefiles, houses and items (t=1761, t=1763). **Navigator:** houses are not a safe store.

### Live-server rules and etiquette
- Item sharing between your own characters is a deletion offence (above). Rescue-levelling happened once, was forgiven, and was called "an honest mistake" (t=1530 p=6334, p=6342).
- Deleted savefiles break artifact and house resets and player IDs. Admins "execute" rule-breakers properly instead (t=1532 p=7724, p=7754). This doesn't affect us.
- Wilderness uniques: a unique generated in the wilderness is unavailable in the dungeon until someone kills it (t=1590 p=6756; t=1933 p=8911, 2012). Wormtongue and Ulfang were affected. A shared unique may therefore be missing for a long time (CONFIRMS memo §4).
- Close your house door: "stealing is supposed to be impossible if you remember to close your door" (t=1761 p=7930).
- **No policy on automated players appears anywhere in this chunk.** The only bot mentioned is ThorBot, a chat-side IRC bot that answers `:$mon <name>` queries (`:$mon search yellow g` returns names from colour + symbol). It was welcomed and asked to be made a sticky (t=1654 p=7174, 2009). Using it would require chat, which our user has ruled out.

### Dangers, escapes, healing
- Plasma: resist sound doesn't protect against plasma damage. Hounds breathing from a second or third row can kill a character with ESP, because "it breathes…" comes from off-screen (t=1513 p=6213, p=6253, 2008). [CONFIRMS hounds as the top killer]
- A status bar can lag behind two consecutive big hits. PowerWyrm lost characters to Morgoth mana storms and Ungoliant darkness storms "in two consecutive turns" before the client refreshed (t=1603 p=6824, 2009). [CONFIRMS memo P3 "big hits come in pairs"; bullet time (finding 1) is the mitigation]
- Heal only when needed: at +30 speed "don't bother using regular heals… you *absolutely* need to stay at max hp"; "spam [Healing] as soon as you see yourself as a 6, *heal* at 5 or worse" (t=1894 p=8716; t=1508 start=15). The `@`→digit health display is a cue (endgame, low relevance).
- Nexus breath can teleport you into a graveyard (Dracolisk; t=1574 p=6631).
- A Grand Master Mystic summoned the Aether hounds that killed a clvl 50 warrior, who was "so used to Z summons being nothing to worry about" (t=1508 start=15). [CONFIRMS memo §1.2]
- Staves burn. Schroeder carries two of any life-saving staff (Destruction) (t=1574 p=6626). [CONFIRMS memo "keep backups"]
- Throwing (`v`) oil flasks: "nature's hand grenades". Early potions to beware: Weakness, Blindness, Sickliness, Lose Memories; Death exists deep (t=1679 p=7355, p=7371). **Navigator:** don't test-quaff unknown potions in a dangerous spot. Flasks of oil are a cheap ranged attack for a warrior.
- A party of three died at 900 ft among "12 black ogres, 15 novice paladins and a shambling mound… without detect monster" (t=1825 p=8291, 2010). Lesson: groups of `p`/`O` at 900 ft call for detection or leaving the level.

### Ghosts, death, logging out
- PowerWyrm (2009): when your ghost is attacked, "you have undead powers to retaliate. Use teleport until you're safe. Signing out is really risky, because you never know what would happen during the quit timeout" (t=1574 p=6634). Schroeder's contrary advice was to sign out after death "unless you know the lvl is safe" (p=6632). [CONFIRMS memo P8/P15; the ghost should float up with `<`, not log out]
- Potion of Death can be used to reset one's unique kill list (PowerWyrm), which some players saw as cheesy (t=1553). Not relevant.

### Economy, shops, houses
- Warrior's player shop sales, June 2009–April 2010: 575 Scrolls of Teleportation. Multi-item buys were "almost always scrolls of teleportation or potions of speed" (t=1804 p=8140). Player shops ("castles") are where missing resists get bought.
- Cloaks of Protection (resist shards) cost about 1500 gold in the General Store (1) and are "widely available". Cloaks of Aman are worth base price unless they carry blindness, confusion or nether (t=1782 p=8057).
- Houses: characters start homeless. A 2×4 house costs about 10k, and a character may own at most about 2 (t=2147 p=9702, 2014).
- A lucky gamble in the Black Market (7) produced a Confusion shield (t=2111 p=9489). The BM is also the place to "scum" for Healing (p=9500).

### Class/race balance
- Warriors are "sort of overpowered" / "dominate" (t=1670 p=7291). Paladins after 1.1: "A warrior is a better choice" (t=1568 p=9500). [CONFIRMS the warrior choice]
- A Hobbit mage challenge character (PowerWyrm) dived at 1000–1200 ft at clvl 26–33 and found a +6 speed ring in a lesser vault at 1000 ft, a Potion of Experience, and rods of detection and enlightenment around 1200 ft. He called ESP "*vital*… you really want to avoid some monsters at all cost" (t=1615 p=6869, p=6863). This is a data point for depth versus level.

### UI/automation
- Fire-until-dead macros (`\ef1*tf1*t…`, 9–30 repeats) are common, and a `\e`-prefixed heal cancels them (t=1515).
- A rod of disarming that didn't ask for a direction was the stale-target bug (finding 10).
- The death dump is posted automatically to the web ladder (t=2116 p=9554). **Architect:** our post-mortem could fetch the ladder dump as well as our own logs.

## Death catalogue

| Cause / monster | Depth | Char | Mistake | Lesson | URL |
|---|---|---|---|---|---|
| Tselakus, Dreadmaster, ethereal hound (pass-wall escapees from a lesser vault) | 1400–1550 ft | clvl 28–32 mage/ranger | "decided to check 'this small vault' out" | leave shallow vaults; SI + teleport below 1000 ft | t=1414 p=6094, p=6099 |
| Dreadmaster (from a lesser vault) | 300 ft | two low-level characters | wandered near a Zoo of Concentrated Death | shallow vault = leave | t=1530 p=6334 |
| Aether hounds, summoned by a Grand Master Mystic | deep (Z vault) | clvl 50 warrior | ran to loot, ignored the lone `p` | kill or avoid summoners; *Destruct* earlier | t=1508 start=15 |
| Skull druj, then a greater basilisk (killed the ghost) | wilderness, at night | clvl ~40 rogue | examined an item while a summoner was casting | don't stop in the open; the wilderness at night is deadly | t=1526 p=6387, p=6389 |
| 22 ethereal hounds | wilderness sector next to a stash | main character | walked into a new sector while waiting on recall | never walk the wilderness | t=1571 p=6591 |
| Druj teleport-to | custom quest level | high-level character | misjudged the druj's line of sight | LOS is symmetric; stay out of view | t=1573 start=15 |
| Aether hound (full breath sequence) | about 3000 ft+ | high level | took `<` | never take up-stairs at depth | t=2144 p=9689 |
| Lag, in an anti-summon corridor | deep | high-level warrior | none stated (lag) | lag gate | t=2111 p=9481 |
| Novice paladin (among 12 black ogres and 15 novice paladins) | 900 ft | low-level party | no detect monsters | detection before engaging crowds | t=1825 p=8291 |
| (near-death) migrating fruit bats | wilderness quest level | clvl 9 | entered the sector | the wilderness is not safe low | t=1675 p=7337 |

## Posts worth reading in full
- t=1601 (p=6808–6823): the time-bubble/running design debate. Explains 1.5 running and bullet-time behaviour.
- t=1603 p=6824: the server/client refresh timeline diagram, and why two-hit deaths happen.
- t=1515 p=6224: range, line of sight and depth-dependent reaction time, from Zal's tests.
- t=1568 (all): what changed in 1.1 versus 0.7 (limited ESP, player shops, recharging, vaults), plus 2013–14 economy notes.
- t=1530 p=6338–6340: the named killer lesser vaults.
- t=2142 p=9685: why the first action after arrival must be queued (auto-retaliate).
- t=2206: ESC and `\e` clear the command queue (dev, 1.5 era).
- t=1897 p=9922: `g` and `,` pickup/stay semantics in 1.5.0.
- t=1532: the item-sharing rule and its enforcement.
- t=1574 p=6618, p=6626: a cautious low-level loop and staff doctrine.

## Coverage
- 151 topic headers. **101 real topics, all read**, most of them quickly because they were social or news. **50 topics (t=2251–t=2312) are 2025 pharmacy/darknet spam** and were skipped after checking that they contain no game text.
- Of the 101: about 30 had actionable content; the rest were social, holiday, quest announcement, art, voice chat, server-down, auction or website topics.
- Pages of multi-page topics appear as `p=page15`/`page30` entries. Some pages may be missing: t=1508, t=1573 and t=1572 show only pages 1–2, and no "[ONLY x OF y]" markers were present.
- Gaps:
  - no bot or automation policy anywhere (only the chat-side ThorBot);
  - little on lag or connection mechanics;
  - no warrior early-game death data.
- Worth checking in code: the wilderness "monsters persist after the level is freed" claim. (The killer vaults were checked and are still present in 1.5.)
