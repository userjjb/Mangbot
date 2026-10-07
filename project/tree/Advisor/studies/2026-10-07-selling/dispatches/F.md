# Dispatch F: what MAngband players say about identifying and selling
- Brief: forum advice on use-ID, Identify vs Perception vs Recharging, selling unknown vs known, store quirks; verdicts on claims (a)-(d).
- Clerk run: 2026-10-07; sources: all 8 files in Advisor/data/forum/corpus/ (grep, then topics read in context). Forum items are [REPORTED] (posts 2002-2010, server 0.7-1.1.x) unless tagged SEEN (1.5 files). Print-view posts have no id, so I cite author+date.

## Answer
1. Players treat use-ID as normal at shallow depth: test potions when hurt (not in a fight), scrolls on a `>` of a cleared level, staffs/wands on a stationary mold, and never wear unknown rings or amulets (strategy t=1481 p=6080).
2. No post compares costs of Identify, Perception staff and Recharging. No recharge failure or explosion appears anywhere.
3. The one explicit low-level selling policy: sell potions and scrolls unknown, ID wands, staffs, rings and amulets (general t=1574, Emulord 08.02.2009).
4. (a) mostly supported with caveats; (b) supported; (c) untested in the corpus; (d) no support, and my estimate (finding 7) goes against it.

## Findings
1. Best use-ID guide: "Warrior's Guide to Ironman MAngband" (strategy t=1481, p=6080, Warrior; partly marked [outdated]; Ironman has few ID sources).
   - Potions: "Maybe as many as half the potions you find <1000ft are negative... quaff them, but try to wait as long as possible... when you're injured, poisoned, confused... not in serious battle".
   - Scrolls: read on the `>` of a cleared level (Summon Monster/Undead, Teleport), take off weapon and armour (Curse), search afterwards (Create Traps). "only seven negative scrolls and they're not all that bad as long as you're on the stairs."
   - Wands: 3 negative (heal, haste, clone monster); aim at a mold. Staffs: 4 negative (darkness, summoning, haste monsters, slowness); try on a `>`. Rods: none negative.
   - Rings: "5 cursed rings... teleportation, aggravate monster and woe... should not try on any rings"; of 7 rings at 250 ft "4 are cursed". Amulets: "you're not gonna put on an amulet that you haven't identified! It'll be teleportation."
   - SEEN (object.txt): 7 negative scrolls (Summon Monster L1, Darkness L1, Aggravate L5, Trap Creation L10, Summon Undead L15, Curse Weapon L50, Curse Armor L50); 4 negative staffs (Darkness L5, Summoning L10, Haste Monsters L10, Slowness L40); 3 wands (Heal, Haste, Clone); 5 rings (Teleportation L5, Weakness L5, Stupidity L5, Aggravate L5, Woe L50); amulets Teleportation L10 and DOOM L50. The counts match.
2. Potions (claim a). Ruination is L40, Death L55, Detonations L60 (SEEN, object.txt). Ashi (t=1679, 08.07.2009): "don't worry about potions of death at low levels, but do watch out for potions of weakness, blindness, sickliness, lose memories". The ladder shows a clvl-3 Human Paladin killed by "a potion of Ruination" at 0 ft (t=1159, serina 03.04.2008; the post has no detail). Ashi's tests (t=312, 16.01.2004): Ruination = permanent loss to all stats, Death = dies, Globe of Invulnerability blocks both. A moderator reply says townie drops let newbies "sell for 13 AU and find out what that strange potion is" (news t=1388 p=5898).
3. Reported disasters are all rings: cursed Ring of Teleportation, three accounts. Bobert (yasd t=562, 05.11.2002) read ID on one of two unknown rings, the items swapped inventory slots, he wore the other, teleported at random and could not reach the Temple for Remove Curse. Fink (general t=749, 11.11.2006): a newbie's ring inscribed over the {cursed} tag; Fink also wore one himself and "had Ashi shoot me out of the sky". Cure is Remove Curse (shop 5 stocked about 20 that day). A cursed Prot ring (-10) should be thrown away (strategy t=1249 p=6483).
4. Scrolls and staffs (claim b). schroeder (t=1679, 07.07.2009): "wands and scrolls are fine...usually... very few... can screw you over. Using a wand of clone monster against something that is stronger... reading a scroll of *curse weapon*... doesn't show up usually till after you get a constant source of ID". One priest read a known Summon Monster and got impact hounds (yasd t=590, page0). Mold/jelly testing of unknown staffs/wands: strategy t=1249 p=6576 ("Molds and jellies are useful if you wanna try out unknown staves or wands"). I found no death from use-ID of a scroll or staff, no Summon Undead or Aggravate story, and no Free Action discussion.
5. Use-ID wastes valuable items. Acquirement (general t=330): Maegdae, 29.01.2004, "Sell it"; the Magic shop paid 92k. Fink read one at 1550-1600 ft and got an item worth under 2k.
6. ID sources and prices.
   - Identify is stocked in shop 5 "less than 100 gold" (newplayer t=770 p=3222, Ashi, 2003); SEEN object.txt cost 50, L1. Berendol's "$5,000" (p=3220) referred to *Identify* in the Black Market.
   - Casters learn Identify around clvl 11 ("survive to level 11, learn Identify", strategy t=1527 p=6322; mage "300-400 feet", t=1608 p=6842).
   - Warriors "have the best pseudo-ID" (t=1310 p=5580), so gear needs no scroll (t=1481: "pseudo id works fast"; keep ID scrolls for choosing between two excellents).
   - A warrior carries scrolls of Identify "so you bring up only items worth ALOT" (strategy t=1410 p=6011, ZAL).
7. Perception vs Identify vs Recharging (claim d).
   - "buy staff of perception/scrolls of recharging for ID" (general t=1615, PowerWyrm, 21.04.2009).
   - Kit for 1000 ft and below: "x staves of Perception (unless you prefer scrolls. Reason for having more than 1 is that you recharge all at once with 1 scroll)", "10-15 scrolls of Recharging", Rod of Perception "if you're that lucky/rich" (t=1410 p=6011). Rod costs 13000 (t=398 table, matches object.txt).
   - A posted inventory had 2 Staffs of Perception (2 charges) (t=1249 p=7288).
   - INFERRED from object.txt: Perception staff cost 400, 1d2 charges (as I read the P: line); Recharging cost 200; Identify cost 50. Unless one recharge gives several charges, each use costs more than an Identify scroll. I did not check the recharge code. Shop-bought staffs also cost 400 up front.
   - No post reports a recharge failure or explosion; recharging is later called a big easing (t=1568 p=6573, p=9500).
8. What earns money.
   - Early loot is mostly junk: scrolls and potions "are usually crap at this level" (t=1481). "90% of the stuff you'll want to bring with you to 1k for cash is found at 800 feet and beyond" (t=1608 p=6842).
   - Players' policy of "sell unID'd, ID wands, staves, rings, amulets" (t=1574) matches the item types that have large base prices (Rod/Wand/Staff/Ring/Amulet in object.txt).
   - Late money: speed rings sold to shops (t=1568 p=9617, p=9618); Warrior's data say "90%+ of my wealth comes from selling things I've bought in the regular shops" (general t=1804, 16.04.2010).
9. Store quirks.
   - Offering one item gives a price quote without selling it (t=284, Berendol, 15.01.2003).
   - Shopkeeper race, CHR and purse matter: "sell it to a non-BM shopkeeper of the same race... deep pockets (Purse number)... lots of CHR" (t=319, Berendol, 15.03.2004).
   - SEEN store.c:219-243, 1352-1365: shop-buys adjust = 100+(300-(greed+factor)), capped at 100; the offer is capped at the owner's purse; the Black Market price is divided by 3.
   - Discounted stacks copy the discount (news t=1388 p=5890). Player shops (shop 8) take a 10% tax (t=1661 p=7225).
   - 2003: a shop offered "barely 60k" for a Balance DSM (cost 100000) at CHR 18/90 (t=284, Maegdae).

## Contradictions and surprises
- The brief says shops pay 30-46% of value. In the 1.5.3 code (store.c:219-236) the buy adjust is capped at 100, so I do not see where 30-46% comes from. Old posts: 92k for Acquirement (cost 100000), 60k for Balance DSM (cost 100000). Not resolved; please recheck.
- Claim (d) has no player support, and my inference points the other way.
- Berendol's "$5000 Identify" (t=770 p=3220) was corrected in-thread (p=3221, p=3222); Identify is cheap.
- No reported death from unknown scrolls or potions anywhere except the single ladder entry (t=1159).

## Leads
- Check in code: Recharging charge amount for a Perception staff and its failure/backfire; adj_chr_gold at CHR 4, Half-Orc, per owner race; real sell ratio.
- A "never read unknown" list for scrolls worth selling known (Acquirement L20 cost 100000, Teleportation L10, Word of Recall 150) may be worth building from kinds.csv.

## Coverage
- Grepped all 8 corpus files (bugs, general, king, newplayer, news, strategy, techsupport, yasd) for the brief's keywords plus sell/shop/CHR.
- Read in context: strategy t=1481, 1410, 1608; general t=1574, 1679, 330, 312, 749, 1804, 1615 (one post); newplayer t=770, 1661; yasd t=562, 590; plus single posts in t=284, 319, 1249 (p=6483, 6576, 7288), 1388 (p=5898).
- Not read: the rest of t=1249 (grep hits only) and t=1568 (grep hits only). t=398 table was truncated in the corpus.
- Source checks: object.txt counts and prices, store.c price_item; recharge code not checked.

## Claim table
| claim | support | against | best quote |
|---|---|---|---|
| (a) quaff unknown potions out of combat is usually safe | t=1481 p=6080; t=1679 Ashi | "half the potions you find <1000ft are negative" (t=1481); t=1159 Ruination death | "quaff them... when you're injured, poisoned, confused whatever, but not in serious battle" |
| (b) unknown scrolls/staffs sometimes dangerous (summoning) | t=1481 (Summon Monster/Undead, curse, traps; Summoning staff) | no death reports from use-ID | "Read scrolls when you're on the > and preferably on a level you've already mapped out" |
| (c) sell for more identified than ID cost | t=1574 (ID wands/staffs/rings/amulets); t=330 | t=1481 early scrolls/potions "crap"; no data on ID gain | "sell them unID'd, but ID wands, staves, rings and amulets" |
| (d) Perception staff + Recharging cheaper than Identify | t=1410 p=6011, t=1615 recommend the kit | no cost figures; inferred 400+200 vs 50 | "x staves of Perception (unless you prefer scrolls...)" |
