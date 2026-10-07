# Distill: "The King Lounge" [KING] + "New Player Support" [NEWP]

Subforum tags: **[KING]** = The King Lounge (winners' posts, 2003-2016), **[NEWP]** = New Player Support
(partial download). Relative tags compare against `notes_players.md` (lines 1-125) and HANDBOOK "How good
players play". Note on scope: the King Lounge is almost entirely Morgoth-fight reports by level-50
characters at 5000-6350 ft. Little of it applies directly to a throwaway warrior, so most items below are
general doctrine read out of the endgame reports, plus a few MAngband-specific server facts that are
worth knowing at any depth.

## Top findings

1. **A level stays alive while another player is on it.** In several reports a player left the level
   (even recalled to town to restock) and came back to the same level, with Morgoth still there, because
   a friend "held the level". This refines the known rule "levels are not persistent". It is true for a
   solo character, but on a busy server the level you arrive on may be one another player is holding,
   and it may already be disturbed (dead monsters, open vaults, awake uniques).
   [KING] https://www.mangband.org/forum/viewtopic.php?p=5885#p5885 (2008: "Kaze and Zal held the level
   for me while I grabbed some speed potions"); https://www.mangband.org/forum/viewtopic.php?p=593#p593
   (2007: "I had to recall to town to restock, Kaze was still on the level luckily"). [CONTRADICTS
   (partly): "Levels are not persistent: leaving loses the level". That holds only when nobody else
   stays.] -> HANDBOOK text; Navigator doctrine.
2. **Auto-retaliate "eats your next move".** PowerWyrm: "the autoretaliator eats your next move, so
   when Morgoth casts a mana storm, you have one turn during which you can't do anything". A heal or
   escape sent after a big hit lands one turn late, so the HP threshold for acting needs a margin of
   about one extra enemy turn of damage. [KING] https://www.mangband.org/forum/viewtopic.php?p=9259#p9259
   (2013); TomeNET is contrasted, since it treats each blow separately:
   https://www.mangband.org/forum/viewtopic.php?p=9261#p9261. [NEW, refines CONFIRMS "queued command
   wins over retaliation"] -> Pilot rule (heal and flee thresholds include one turn of lag).
3. **Hounds on arrival kill strong characters.** The first warrior king said his earlier, better-equipped
   characters kept "dying to hounds on stairs or recall or to greater draconic Qs". Zaphod recalled to
   6350 ft and "lost 1000 hitpoints to 8 breaths by a pack of chaos hounds before my *Destruction*
   kicked in". Arrival (by stairs or recall) is a moment of peak danger. [KING]
   https://www.mangband.org/forum/viewtopic.php?p=545#p545 (2003) [MAYBE-OUTDATED];
   https://www.mangband.org/forum/viewtopic.php?p=593#p593 (2007). [NEW as an explicit rule] -> Pilot
   rule: on a new level, if a `Z` pack is in view, leave at once (take the stair underfoot) before doing
   anything else.
4. **Overhealing wastes turns and potions.** Zaphod quaffed 74 Potions of Life, but "only 47 of those
   times actually resulted in me 'feeling very good'", then teleported out at 4 HP. Maegdae: "I healed
   far too much (20x...); could have cut off some moves". Pastor was "overhealing a lot (using *heal*
   spell often at 950/1006 hps)". [KING] https://www.mangband.org/forum/viewtopic.php?p=593#p593 (2007),
   https://www.mangband.org/forum/viewtopic.php?p=5885#p5885 (2008),
   https://www.mangband.org/forum/viewtopic.php?p=8873#p8873 (2012). [NEW] -> Pilot rule: heal only
   below a threshold. Don't chain-quaff. Check the HP result after each quaff.
5. **Summons appear next to you in MAngband**, not next to the caster (pre-3.0.9 Vanilla behaviour).
   That is why summoners are so deadly, and why winners fight in spots with few open squares nearby
   ("permawalls, so he had one space to summon"). [KING]
   https://www.mangband.org/forum/viewtopic.php?p=9270#p9270 (2013),
   https://www.mangband.org/forum/viewtopic.php?p=546#p546 (2003),
   https://www.mangband.org/forum/viewtopic.php?p=5885#p5885 (2008). [CONFIRMS "summoners are the real
   killers" and "meet packs in a corridor"; NEW: the mechanism] -> HANDBOOK text; the Pilot's `choke`
   order should prefer squares with few open neighbours.
6. **In a macro, nothing after a level change runs.** On a stairs macro `\e\e\e>\e\e\eu8...`: "Nothing
   after the > will work. Also, more than one \e does nothing but make more lag." An empty staff raises a
   "Use which staff?" prompt that blocks every later macro until ESC, so each action needs its own `\e`
   (`\eu1\eu2`). [NEWP] https://www.mangband.org/forum/viewtopic.php?p=3229#p3229,
   https://www.mangband.org/forum/viewtopic.php?p=3231#p3231,
   https://www.mangband.org/forum/viewtopic.php?p=3232#p3232 (2003) [MAYBE-OUTDATED, client 0.7-era].
   [NEW for level change; CONFIRMS "\e first"] -> Pilot rule: never queue commands across a level
   change. Re-issue them after the new level loads. Check charges before using a staff or wand.
7. **Equipment matters less than DPS plus position plus healing supply** (for the big fight). "You just
   need: DPS, a maze vault, enough *heals*. And forget about 'safety'. RNG decides to put back to back
   manastorms". [KING] https://www.mangband.org/forum/viewtopic.php?p=9731#p9731 (2014). General
   lesson: some damage spikes can't be survived, so the answer is to avoid the fight, not to gear up for
   it. [NEW] -> Navigator doctrine.
8. **Artifacts and uniques are shared across the server.** Uniques other players killed stay dead for
   you ("ride in on the already dead uniques"). A king's artifacts return to the game when they retire
   ("Arts being released: Thunderfist, Eol, ..."; "All arts have been kicked back out there"). [KING]
   https://www.mangband.org/forum/viewtopic.php?p=566#p566 (2004) [MAYBE-OUTDATED],
   https://www.mangband.org/forum/viewtopic.php?p=9265#p9265 (2013),
   https://www.mangband.org/forum/viewtopic.php?p=9887#p9887 (2016). [NEW] -> HANDBOOK text (don't
   expect a named unique to be present; its drop may be gone).
9. **Other players change monster behaviour.** Domiano's Morgoth "didn't do anything half of the time
   due to him retreating to chase Karis" (called `ai_bug`). Zaphod: quakes pushed him away "and then he'd
   focus on Kaze who was watching nearby". Monsters split their attention between the players on a level.
   [KING] https://www.mangband.org/forum/viewtopic.php?p=6594#p6594 (2009),
   https://www.mangband.org/forum/viewtopic.php?p=593#p593 (2007). [NEW] -> Navigator doctrine (a level
   with other players on it behaves differently; don't count on it).
10. **Summoned monsters stay after the summoner dies.** "Morgoths minions got mad after I killed him":
    serina's other character Elon, on the same level, was killed by a Gelugon breathing frost amid a
    Balrog of Moria, a Marilith and a Barbazu, which kept summoning more. [KING]
    https://www.mangband.org/forum/viewtopic.php?p=6002#p6002 (2008). [NEW] -> Pilot rule: after a
    summoner fight, leave the level rather than clean up.
11. **Stat drain and sustains.** Every Morgoth touch drained stats. Sustained stats show "You feel weak
    for a moment, but the feeling passes", while unsustained ones show "You feel very stupid/naive/ugly".
    The warrior king credits "a kolla to sustain your fighting stats". Potion of Life restored drained
    stats and XP ("You feel your life energies returning. Welcome to level 50."). [KING]
    https://www.mangband.org/forum/viewtopic.php?p=545#p545 (2003),
    https://www.mangband.org/forum/viewtopic.php?p=593#p593 (2007), ZalMag log
    https://www.mangband.org/forum/viewtopic.php?p=6109#p6109 (2008). [CONFIRMS the drained-DEX threat]
    [NEW: the message strings] -> Pilot rule: parse "You feel very <adj>" as a stat drain and "for a
    moment, but the feeling passes" as sustained.
12. **Level scumming for a target level is the standard deep tactic**, as expected. Winners "scummed for
    a level with morgy and a maze vault" at 6350 ft, used Potions of Enlightenment to judge each level
    fast, and Emulord used Alter Reality + Clairvoyance "to reset the level". [KING]
    https://www.mangband.org/forum/viewtopic.php?p=8873#p8873 (2012),
    https://www.mangband.org/forum/viewtopic.php?p=6590#p6590 (2009),
    https://www.mangband.org/forum/viewtopic.php?p=6766#p6766 (2009). [CONFIRMS stair-scumming] ->
    Navigator doctrine.
13. **The bow slot is overpowered in MAngband.** "you get the full damage from the multiplier AND the
    brand multiplied". Domiano killed Morgoth at clvl 26 mostly by shooting. A ranger with a stack of
    slay-evil arrows found the fight easy. For a warrior, a good launcher and ammo are a strong
    secondary weapon. [KING] https://www.mangband.org/forum/viewtopic.php?p=9266#p9266,
    https://www.mangband.org/forum/viewtopic.php?p=9262#p9262 (2013),
    https://www.mangband.org/forum/viewtopic.php?p=8886#p8886 (2012). [NEW] -> Navigator doctrine; a
    future Pilot `fire` goal (the `@f1` ammo inscription is already planned).
14. **The King title requires clvl 40 or more** when Morgoth dies ("to prevent cheezy party wins"). Below
    40 you have only "killed" Morgoth. [KING] https://www.mangband.org/forum/viewtopic.php?p=9266#p9266
    (2013). [NEW] -> HANDBOOK text (trivia for a throwaway).
15. **Inscription conventions winners use:** consumables inscribed `{@q1 !kvs}`, `{@q2 !kvs}`,
    `{@r6 !k!v!s}` (a quaff or read slot plus protection from destroy `k`, `v` and sell `s`), and ammo
    `{@f1}`. What `!v` does is not stated in the corpus; by the Angband keyset it is probably
    throw-protection. [KING] https://www.mangband.org/forum/viewtopic.php?p=593#p593 (2007),
    https://www.mangband.org/forum/viewtopic.php?p=6002#p6002 (2008). [CONFIRMS the `@q1`-style plan;
    NEW: the `!kvs` protection habit] -> Pilot (inscribe key consumables `!k` so `autodestroy`/`junk`
    can never hit them).
16. **Selling from your own house:** inscribe the item `{for sale}` (lowest price) or `{for sale 10000}`
    to set a price. [NEWP] https://www.mangband.org/forum/viewtopic.php?p=8359#p8359 (2010). [NEW] ->
    HANDBOOK text (low priority; houses).
17. **The ladder `*` flag** ("unusual amount of money, possibly cheating") is only a pointer for the
    admin. Deletion is manual, and legitimate luck (a *Acquirement* scroll at 200 ft) is fine. [NEWP]
    https://www.mangband.org/forum/viewtopic.php?p=3358#p3358,
    https://www.mangband.org/forum/viewtopic.php?p=3359#p3359 (2007). [NEW] -> HANDBOOK (a good-citizen
    note: a flagged throwaway isn't in trouble).

## Findings by theme

### Escape, healing, HP doctrine
- A reactive heal can arrive too late: Morgoth "mana-stormed and nether balled me in the same turn. I
  had about 150 health in that instant". Ascii was at 115/874 HP after one mana storm. Big hits come in
  pairs, so heal early. [KING] https://www.mangband.org/forum/viewtopic.php?p=6766#p6766 (2009),
  https://www.mangband.org/forum/viewtopic.php?p=6375#p6375 (2008).
- PowerDwarf: "a mana storm followed by a quake ... I had a chance to use a *heal* between the two mana
  storms, and that's all the difference". [KING] https://www.mangband.org/forum/viewtopic.php?p=9255#p9255
  (2013).
- Emergency escape at 4 HP: Zaphod "tele'd out as a 4" after his potions ran low. Teleport as the last
  resort works, but he had waited far too long. [KING] https://www.mangband.org/forum/viewtopic.php?p=593#p593
  (2007).
- *Destruction* is the answer to a hound pack or a big threat on arrival (read on arrival at 6350 ft
  against chaos hounds; read when Morgoth approached). Staff of *Destruction* is kept "just in case".
  [KING] https://www.mangband.org/forum/viewtopic.php?p=593#p593,
  https://www.mangband.org/forum/viewtopic.php?p=5996#p5996 (2008). [CONFIRMS the escape list]
- Pastor forgot to restore mana "a couple of times (becoming a '1' in the process)". PowerWyrm's ranger
  "became a 3 once". The pattern: HP drops to single digits even for winners, mostly through operator
  error. [KING] https://www.mangband.org/forum/viewtopic.php?p=8873#p8873,
  https://www.mangband.org/forum/viewtopic.php?p=8886#p8886 (2012).
- Healing without *Heal*/Life works: Ascii won "without *healing* or life" (Maegdae's comment). Buffy
  won using only the paladin Heal-300 spell at 5% fail. [KING]
  https://www.mangband.org/forum/viewtopic.php?p=6363#p6363 (2008),
  https://www.mangband.org/forum/viewtopic.php?p=9264#p9264 (2013).

### Positioning, summoners, terrain
- A permanent-wall maze vault with a zigzag corridor is the preferred arena, because it leaves the
  summoner only one open square to summon into. "In turnbased it was possible to kill morgoth in other
  places but in realtime if you don't get him in a position where he has limited summoning capability
  you're screwed." Real-time play makes positioning matter more than in Vanilla. [KING]
  https://www.mangband.org/forum/viewtopic.php?p=546#p546 (2003) [MAYBE-OUTDATED],
  https://www.mangband.org/forum/viewtopic.php?p=545#p545 (2003).
- Earthquakes rearrange the terrain: they push you away, seal passages behind you ("At least I wont get
  summoned from behind now"), or open squares. While you dig back, the monster heals. [KING]
  https://www.mangband.org/forum/viewtopic.php?p=593#p593 (2007),
  https://www.mangband.org/forum/viewtopic.php?p=6766#p6766 (2009).
- Runes/Glyphs of Warding (Scroll of Rune of Protection, inscribed `@r6`) block melee until broken, and
  can steer monster pathfinding ("lured him to the right spot using runes to alter his pathfinding").
  [KING] https://www.mangband.org/forum/viewtopic.php?p=6766#p6766 (2009),
  https://www.mangband.org/forum/viewtopic.php?p=593#p593 (2007). [NEW; possible future Pilot tool]
- Teleport Other was used "many many times" to push the big monster away while preparing. [KING]
  https://www.mangband.org/forum/viewtopic.php?p=5996#p5996 (2008). [CONFIRMS the escape list]
- Angel's first attempt failed "cus of blink hounds". Buffy was glad she "didn't get blink'd out near
  the end". Teleport-effect hounds break a prepared position. [KING]
  https://www.mangband.org/forum/viewtopic.php?p=9265#p9265,
  https://www.mangband.org/forum/viewtopic.php?p=9264#p9264 (2013).

### Diving, depth, level selection
- Depth scale: Morgoth fights took place at 5000 ft (PowerDwarf), 5700 ft (Greyshoe, who "began
  actively looking for him around level 5500") and 6300-6350 ft (the maximum). MAngband's dungeon goes
  deeper than Morgoth's native 5000 ft. [KING] https://www.mangband.org/forum/viewtopic.php?p=9255#p9255,
  https://www.mangband.org/forum/viewtopic.php?p=9887#p9887,
  https://www.mangband.org/forum/viewtopic.php?p=8873#p8873.
- Scumming with Potions of Enlightenment between 6000 ft and max to find the right vault. Uniques also
  get summoned with a Staff of Summoning ("On the 4'th try I summoned Morgoth"). It is risky: Domiano
  summoned an Elder Vampire that drained his XP. [KING]
  https://www.mangband.org/forum/viewtopic.php?p=6590#p6590 (2009),
  https://www.mangband.org/forum/viewtopic.php?p=593#p593 (2007).
- Level feelings were not discussed.

### Buffs and consumables
- Winners pre-buff with Speed, Heroism, Berserk Strength and Holy Chant/Prayer. Buffs wear off, and
  Maegdae "didn't reapply". Winners quaffed Heroism 38 times and 79 times in a row, apparently to stack
  duration. Turin "bought 38 Potions of Heroism for 1482 gold" (about 39 gold each). [KING]
  https://www.mangband.org/forum/viewtopic.php?p=5885#p5885 (2008), ZalMag log
  https://www.mangband.org/forum/viewtopic.php?p=6109#p6109 (2008). [NEW] -> Pilot: track the buff
  messages ("You feel like a hero!" / "You feel less Berserk" / "You feel yourself slow down").
- Messages useful to the Pilot's parser: "You feel yourself moving faster!" / "You feel yourself slow
  down." (speed on/off); "You feel like a killing machine!" (berserk); "The rune of protection is
  broken!"; "You feel something roll beneath your feet." (a drop landed under you); "You feel the
  <item> in your pack is cursed... / is good..." (pseudo-ID in the pack). [KING]
  https://www.mangband.org/forum/viewtopic.php?p=5885#p5885 (2008),
  https://www.mangband.org/forum/viewtopic.php?p=593#p593 (2007).
- Before the fight, Turin "discarded everything with charges" and dropped 70 of 87 Speed potions. No
  reason is given. [KING] https://www.mangband.org/forum/viewtopic.php?p=5885#p5885 (2008).

### Builds, stats, gear (endgame reference points)
- The first warrior king (2003) won with "pretty lousy gear", a kolla (cloak) that sustains fighting
  stats, and a stack of *Healing* (used 14). [KING] https://www.mangband.org/forum/viewtopic.php?p=545#p545
  [MAYBE-OUTDATED].
- Speed is universal in winners' gear: two Rings of Speed (+12 to +15) plus Boots of Speed, for 29-52
  speed buffed. Warrior Zaphod: Blade of Chaos of Extra Attacks (+2 attacks), Ring of Damage (20),
  Power Dragon Scale Mail, and resists for sound (Amulet of the Magi) and disenchantment (shield of the
  Avari). [KING] https://www.mangband.org/forum/viewtopic.php?p=593#p593 (2007),
  https://www.mangband.org/forum/viewtopic.php?p=564#p564 (2004),
  https://www.mangband.org/forum/viewtopic.php?p=8433#p8433 (2010). [CONFIRMS speed and resist
  priorities]
- A 2010 priest tip (from [NEWP]): mace of disruption or slay evil, "4bpr", 0% fail on the healing
  spell, restore mana potions, berserk and heroism before the fight, a permawall vault.
  https://www.mangband.org/forum/viewtopic.php?p=8054#p8054 (Cheezband server).
- Disenchantment wrecks gear over time without resist (Greyshoe "hadnt been able to find reasonable
  Disenchant resist"; serina's items "got disenchanted by Sauron"). [KING]
  https://www.mangband.org/forum/viewtopic.php?p=9887#p9887 (2016),
  https://www.mangband.org/forum/viewtopic.php?p=9812#p9812 (2015).
- Hobbits have strong innate protections (serina never got blinded, and "Brain Smashing is resistable"
  she believes). [KING] https://www.mangband.org/forum/viewtopic.php?p=6007#p6007 (2008).
- Female characters "start with more money" (Emulord). [KING]
  https://www.mangband.org/forum/viewtopic.php?p=6766#p6766 (2009). [NEW, unverified; matters only if
  starting gold is a bottleneck]
- Half-Trolls were favoured by one multi-winner ("I think i'm gonna be doing a lot of half trolls").
  [KING] https://www.mangband.org/forum/viewtopic.php?p=6595#p6595 (2009).

### Money, shops, black market, houses
- Gandhi bought a potion from the black market and "sold it to another character for profit, over and
  over". He also picked up coins off "many murdered corpses in town (murdered by others)". Town has
  player deaths, and coins lie on the ground. [KING]
  https://www.mangband.org/forum/viewtopic.php?p=9263#p9263 (2013). [NEW; don't copy, it's cheesy, but
  gold on the town floor is free to pick up]
- House selling via `{for sale N}`: see Top finding 16 ([NEWP]).
- Players trade gear between characters ("Good trade for both of us"). Irrelevant to a solo no-chat
  bot. [KING] https://www.mangband.org/forum/viewtopic.php?p=6396#p6396.

### MAngband server quirks
- A bug took Schroeder's level-50 status and gear while he fought the Tarrasque. Maegdae: "there's a
  display bug that doesn't show all temp effects" in to-hit. [KING]
  https://www.mangband.org/forum/viewtopic.php?p=6299#p6299 (2008),
  https://www.mangband.org/forum/viewtopic.php?p=5885#p5885 (2008).
- There are several server instances and resets (e.g. "First king on new instance", poorcoding.com,
  an Ironman "Fresh reset"). [KING] https://www.mangband.org/forum/viewtopic.php?p=8873#p8873,
  https://www.mangband.org/forum/viewtopic.php?p=9812#p9812,
  https://www.mangband.org/forum/viewtopic.php?p=9887#p9887.
- Items dropped by uniques are inscribed with the unique's name (e.g. `{Morgoth, Lord of Darkness}`).
  [KING] https://www.mangband.org/forum/viewtopic.php?p=5885#p5885 (2008). [CONFIRMS]
- After the win: "You may retire (commit suicide) when you are ready". A character killed below clvl 40
  "would have never timed out", meaning characters normally time out when unused. [KING]
  https://www.mangband.org/forum/viewtopic.php?p=9266#p9266 (2013). [NEW: character timeout exists;
  the live throwaway may expire if idle]

### UI / macros ([NEWP] unless noted)
- `\e.` is the run macro. An empty macro disables its key entirely (a trap if a macro file gets
  corrupted). https://www.mangband.org/forum/viewtopic.php?p=3229#p3229 (2003).
- Winners' macro sets: F-keys for each potion type, and a spell macro that repeats the cast
  (`\e*tm9hm9hm9h...`) so one key fires many times under lag. [KING]
  https://www.mangband.org/forum/viewtopic.php?p=5996#p5996 (2008),
  https://www.mangband.org/forum/viewtopic.php?p=6766#p6766 (2009). [CONFIRMS "spells take target
  before casting"]
- New-player advice: "Get used to dying"; persistence matters because you die "*alot* in the
  beginning". [NEWP] https://www.mangband.org/forum/viewtopic.php?p=3332#p3332,
  https://www.mangband.org/forum/viewtopic.php?p=3333#p3333 (2006). The thread with the recommended
  macro setup is only a dead YaBB link. https://www.mangband.org/forum/viewtopic.php?p=3331#p3331.

## Death catalogue

| Cause / monster | Depth | Char (level/class) | Mistake | Lesson | URL |
|---|---|---|---|---|---|
| Hounds on stairs or recall; "greater draconic Qs" (earlier characters) | deep (not stated) | Xander's previous chars, well geared | Arrived into packs; fought Q summoners | Arrival is a peak-danger moment; leave at once if hounds are in view | https://www.mangband.org/forum/viewtopic.php?p=545#p545 (2003) |
| Chaos hound pack, 8 breaths, -1000 HP (survived) | 6350 ft | Zaphod, lvl 50 warrior | Recalled straight into a pack | Have an instant escape or area clear ready on arrival | https://www.mangband.org/forum/viewtopic.php?p=593#p593 (2007) |
| Morgoth, near-death at 4 HP (survived by teleport) | 6300 ft | Zaphod, lvl 50 warrior | Overhealed (27 of 74 Life potions wasted), then ran out | Heal by threshold; escape before supplies run out | https://www.mangband.org/forum/viewtopic.php?p=593#p593 (2007) |
| Gelugon frost breath (with a Balrog of Moria, a Marilith and a Barbazu summoning) | Morgoth level, about 6000+ ft | Elon (serina's other char, an archer) | Stayed on the level with Morgoth's leftover summons, plinking wolves with average arrows | Leave the level after a summoner fight | https://www.mangband.org/forum/viewtopic.php?p=6002#p6002 (2008) |
| Morgoth ("horrifying death") | Morgoth level | Steel_Dragon's earlier lvl 50 | Not stated | (no detail) | https://www.mangband.org/forum/viewtopic.php?p=568#p568 (2004) |
| Bug while fighting the Tarrasque: lost gear and lvl-50 status | deep | Schroeder | Server bug | Server bugs happen; don't risk irreplaceable state | https://www.mangband.org/forum/viewtopic.php?p=6299#p6299 (2008) |
| Failed attempt: blinked out by blink hounds | Morgoth level | Angel, priest | Teleport-effect hounds broke his position | Hounds that teleport you ruin set-ups; clear them or leave | https://www.mangband.org/forum/viewtopic.php?p=9265#p9265 (2013) |
| Down to 1 HP (survived) | 6350 ft | Pastor, lvl 50 dwarf priest | Panic; forgot to restore mana | Operator error kills; automate resource checks | https://www.mangband.org/forum/viewtopic.php?p=8873#p8873 (2012) |
| Mana storm + nether ball in one turn, to about 150 HP (survived) | Morgoth level | Emulord, dwarf priest | None (RNG) | Damage comes in pairs; keep a margin of more than two big hits | https://www.mangband.org/forum/viewtopic.php?p=6766#p6766 (2009) |
| "many hard losses of lvl 50 characters" | deep | Prosper | Not stated | Even veterans lose many level-50s | https://www.mangband.org/forum/viewtopic.php?p=8908#p8908 (2012) |

## Posts worth reading in full

- https://www.mangband.org/forum/viewtopic.php?p=593#p593 [KING, 2007]: the warrior Zaphod's full
  Morgoth log. Shows real message strings (sustain and drain, speed on and off, rune broken, quake), the
  `@q1 !kvs` inscriptions, hounds on arrival, and wasted overhealing.
- https://www.mangband.org/forum/viewtopic.php?p=5885#p5885 [KING, 2008]: Turin's timestamped log.
  Buff sequence, the level held by other players, messages about drops under you and pseudo-ID of
  cursed/good items in the pack.
- https://www.mangband.org/forum/viewtopic.php?p=9259#p9259 [KING, 2013]: auto-retaliate eats your next
  move. The single most Pilot-relevant mechanic here.
- https://www.mangband.org/forum/viewtopic.php?p=6002#p6002 [KING, 2008]: death log of Elon, killed by
  leftover summons.
- https://www.mangband.org/forum/viewtopic.php?p=6766#p6766 [KING, 2009]: Emulord's F-key macro layout,
  rune pathing, and the double-hit near-death.
- https://www.mangband.org/forum/viewtopic.php?p=546#p546 [KING, 2003]: why real-time makes summoner
  positioning decisive.
- https://www.mangband.org/forum/viewtopic.php?p=9266#p9266 and
  https://www.mangband.org/forum/viewtopic.php?p=9270#p9270 [KING, 2013]: the bow slot is overpowered,
  summons appear near the player, clvl 40 for King, and character timeout.
- https://www.mangband.org/forum/viewtopic.php?p=3229#p3229 [NEWP, 2003]: macro semantics (no commands
  after `>`, empty macros, `\e`).
- https://www.mangband.org/forum/viewtopic.php?p=8359#p8359 [NEWP, 2010]: `{for sale}` house pricing.

## Coverage

- **[KING] The King Lounge:** 26 topics read in full. 24 are substantive (win reports and replies).
  Skipped as irrelevant: 1 spam topic (t=4148, Heardle). t=1867 (Liam II) and t=117 (Ashiki) are pure
  congratulations with no content. The long raw combat logs (Zaphod t=121, Turin t=1385, ZalMagus
  t=1407, ZalMag t=1487; about 4,000 of the 5,847 lines) were read with the repeated "You hit/miss" and
  "<monster> hits/misses you" lines filtered out. Every non-repetitive line was read (summons, heals,
  buffs, quakes, drops, deaths). Gaps: many posts depend on images or videos (stats and gear
  screenshots, YouTube and rapidshare links) that are not in the text, e.g. the PowerDwarf gear list
  (p=9255) and the Schroeder, Domiano, Bruce Lee, Gandhi, Buffy and Angel sheets. The Schroeder story
  thread (t=1508, other subforum) is linked but not included. Almost all content concerns clvl-50
  Morgoth fights, so there is little direct early-game or warrior-diving advice.
- **[NEWP] New Player Support:** [PARTIAL DOWNLOAD: 12 topics in the file; the full subforum is larger]. All
  12 read. Substantive: 5 (t=772 macros, t=798 ladder flag, t=1781 Morgoth tips, t=1838 selling, t=794
  welcome advice, marginal). Skipped as irrelevant: 7 (t=792 and t=1372 connection problems, t=799
  compile error, t=804 Vista font fix, t=2575, t=4146 and t=4171 spam; t=772 and t=804 also carry spam
  replies). Most posts date from 2003-2010 (client 0.7.x era) [MAYBE-OUTDATED for UI details]. The
  newbie guide thread recommended in t=794 is a dead YaBB link and is not in the corpus.
