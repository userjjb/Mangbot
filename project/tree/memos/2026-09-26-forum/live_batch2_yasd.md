# Batch 2: YASD (36 topics) + King (1)

Posts are 2008–2014 (server 1.1.x), so everything here is [MAYBE-OUTDATED] unless code-checked. `pN` = `https://www.mangband.org/forum/viewtopic.php?p=N#pN`.

## New or contradicting findings

1. **Auto-retaliate melees adjacent molds.** Log: "You enter a maze of down staircases. / Looks like any other level. / You miss the Death mold. / You hit the Death mold…". Then gear was disenchanted ("Your … Boots of Free Action (l) was disenchanted!", "You feel your life draining away!") and she died. She "didn't get a turn to react". p7951 (2010). [STRENGTHENS Add.2 #2: forum evidence for the inference] **Pilot:** if an `m` is adjacent on arrival, the first action is to step off or take the stair back.
2. **Stun ladder strings:** "You have been stunned." → "You have been heavily stunned." → "You have been knocked out.", from impact-hound force breath. p9369 (2013). [STRENGTHENS P4] **Pilot/parser:** escape on the first rung.
3. **Summons act immediately.** After "The Scroll mimic magically summons help!" the hounds "started all to breathe immediately". PowerWyrm calls it bug #1016: monsters cast every turn instead of 1_IN_5. This happened even though he had detected monsters and traps. p9359, p9374 (2013). [STRENGTHENS P6] **Architect:** check the cast rate in 1.5. **Pilot:** "magically summons" means escape now.
4. **A possible detect prompt.** Right after "You sense the presence of creatures!" the log shows "Map sector [0,1], which is your sector.  Direction?" three times. p9369. It isn't clear whether detection opened this prompt or the player did. [relates to Add.2 #1] **Architect:** test it in 1.5 and ESC it.
5. **The heal window is about ⅓ s.** "You lose a turn due to the auto-retaliator… you have a third of a second to react"; "I pressed the key for healing, but the command was not processed in time". p9229 (2013), also p6052, and p6044 (which hopes the time bubble will fix it). [STRENGTHENS §1.3, A1] This supports `hitpoint_warn` and healing early.
6. **Aggravation plus stairs or recall:** monsters "wake up AND act the same turn". PowerWyrm used *Destruction* immediately on arrival. p8516, p8519 (2010). [STRENGTHENS P12]
7. **Logging out under a paralysis lock.** Billsey was paralyzed for about 10 minutes with his FA ring in the pack, not worn, and says he should have logged off and waited for the reset (p7907, 2010). By contrast, Liam quaffed a Healing, logged out mid-fight and died anyway (p8221). [NEW nuance to P8] **Architect:** consider logging out only for a slow, low-damage paralysis lock, never for burst damage. **Pilot:** check FA on *equipped* items.
8. **Shallow killer vaults:** Mouth of Sauron at **1250 ft** and Khamul at 1400 ft came from a Backdoor Surprise vault (p6930, p6946, p6949). A GMM was in one at 1300 ft (p6950). Plus Vault, Backdoor Surprise and ZoCD are "most dangerous", and their monsters "can open or leave them… never stand close" (p6955). "4 excellent items together" should make you suspicious (p6950). One ZoCD killed seven characters (p9145). [STRENGTHENS A10/§3] **Navigator:** if a vault is seen, leave.
9. **Traps kill at clvl 1.** "You found a trap! / You are splashes with acid! / You die." came two steps from the first stairs (p8762). A summon trap at 50 ft killed another (p8763, 2011). [NEW, 0–50 ft] **Pilot:** at very low max HP, keep HP full and minimise steps.
10. **An orc pit at 300 ft killed two clvl-8 Half-Troll Paladins**, who charged in and then blocked each other in a 1-wide corridor. The one who ran to a nearby `<` lived. p8377 (2010). [NEW shallow datum] **Navigator:** at clvl < 15 an orc pit means leave.
11. **Summoner kill sequences** for the classifier: "The Sorcerer magically summons a dragon! / The Ancient multi-hued dragon creates a mesmerising illusion. / You are confused! … breathes gas. / You die." The sorcerer had been asleep in the next room, and "All I wanted was the >" (p6137, 2008). "The Enchantress magically summons a dragon. … casts a spell, burning your eyes! … breathes Frost. You die. All happened in less than 1 second" (p6764). [STRENGTHENS P6/P13]
12. **Unique casters track you out of sight.** Saruman, Mouth, Fundin, Ulfang and Feagwath "don't stop chasing you even tho they're outside of your visual/telepathy". p5981 (2008). [NEW] **Navigator:** after meeting one, leave the level; breaking line of sight is not enough.
13. **Held levels.** "i'll keep the level hold" … "today i woke up and the level was reset" (p8902, p8904). "please unstatic the level" (p5978). On a 1600 ft level where Zaphod had been staying, many uniques had spawned (Khim, Beorn, Bolg…) (p9583). [STRENGTHENS §4] **Navigator:** a level with many uniques on it is probably being held by someone; leave.
14. **Lag deaths:** he "decided to wait it out" after `>` and died (p6451). "Never let an 'easy' vault trick you into staying while you're lagging" (p8200). Lag plus a Wi-Fi drop at 1400 ft (p6553). A laptop power loss at 1800 ft (p9532). [STRENGTHENS P7/P8]
15. **Ghost placement:** a ghost landed "right next to Atlas" (p9592). A ghost went back for its gear and died (p9583). "Don't bother with a rescue… Just float up to town" (p7713). [STRENGTHENS P15]
16. **Checkpoints:** "get resist sound asap to dive below 2k" (p8903, 2012). With no base resists, "at 2500ft you get toasted when a lesser balrog breathes fire" (p9323). [STRENGTHENS §3] A resisted shards breath still does up to 343 (p7664, p7667). Tselakus's darkness storms ×2 killed at 2000 ft (p7712). [beyond our band]
17. **More parser strings.** Feelings: "Looks like any other level." (p7951), "This level can't be all bad..." (p8762), "You feel your luck is turning." (p8553). Unseen casters: "It commands you to return!!!", "It magically summons greater demons!!!" (p8553). Burned staff: "It casts a fire bolt. / Your Staff of Enlightenment (7 charges) {@u0} (s) was destroyed!" (p9369). *Healing*: "You feel very good." (p9229). Paralyze resisted: "gazes deep into your eyes. / You resist the effects!" (p7758). [NEW seeds]
18. **Wilderness:** a clvl-11 Gnome Warrior died far north in the marsh (p5673); "not going into the wilderness by myself any more" (p5878). Look up unknown letters: a purple `p` taken for Lorgan was Sauron (p7952); Magic Mapping plus Detect Evil helps (p6940). [STRENGTHENS Add. B, §3]

## Death catalogue (new deaths)

| Cause | Depth | Char | Mistake | Lesson | URL |
|---|---|---|---|---|---|
| Wilderness "red spot" | wild | L11 Gnome Warrior | Explored far | Leave town only by `>` | p5673 |
| Acid trap, 2 steps in | ~50 | L1 Hobbit Mage | — | Low-HP trap risk | p8762 |
| Summon trap | 50 | ironman char | — | Same | p8763 |
| Orc pit | 300 | 2× L8 HT Paladins | Charged a pit | Pits = leave | p8377 |
| Mouth of Sauron / Khamul (vault) | 1250/1400 | Agor | Entered a vault | Vaults = leave | p6930 |
| Mimic scroll + lag | 1400 | Mr Ploppy | Pressed on in lag | Lag gate | p6553 |
| Shelob while AFK | 1700 | mreggiardo | AFK | Never AFK | p8892 |
| Ring wraith + lesser balrog | 1800 | L35 | Laptop died | P8 | p9532 |
| Uniques on a held level; ghost poisoned | 1600 | Andrak | Ghost went for gear | Float up | p9583 |
| Tselakus darkness storms | 2000 | userjjb | No rDark | Know storm types | p7712 |
| Plasma hounds | 2300 | mreggiardo | No rSound | rSound < 2k | p8903 |
| Death drake; ghost by Atlas | 2250 | L36 | Recon near a unique | — | p9592 |
| Death mold on arrival | ? | serina mage | Auto-melee | Step off `m` | p7951 |
| Paralysis ~10 min | ? | Billsey | FA ring unworn | Check equipment | p7907 |
| Scroll mimic → impact hounds, KO | LV | PowerWyrm | No rSound | Summons act now | p9369 |
| Sorcerer → AMHD confuse/gas | deep | serina | Sleeping summoner nearby | Leave | p6137 |

Deeper deaths that are cited in the findings but not in this table: p6451, p7661, p8184, p8200, p8221, p8519, p9227, p6764, p7904.

## Posts worth reading in full

1. p9369 (with p9359): the full impact-hound log (stun ladder, summon, staff burn, the possible detect prompt).
2. p7951: the Death-mold arrival log.
3. p9229: why a heal can't land between two consecutive hits.
4. p6946, p6955: how the Backdoor Surprise and Plus vaults work.
5. p8516: aggravation and the same-turn arrival.

## Coverage

- **YASD:** 36 of 36 topics and 110 posts, all read. No content: t=1669, t=1818 and t=1830 (revive requests), and t=1828, t=1864, t=1868 and t=1914 (links to death dumps that weren't fetched).
- **King:** t=2135 (PowerWyrm's artifactless win in 2014 with 1253 HP, p9607/p9609). Nothing for our depth band.
- **Gaps:** only four deaths fall at 0–1500 ft with a low clvl (p5673, p8762, p8763, p8377). There is little that is specific to warriors.
