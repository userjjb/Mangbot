# Distillation: "Yet Another Stupid Death" (YASD) subforum

Corpus: `corpus/yasd.txt`, 142 topics, dated 2002-2013 (plus 2 spam posts from 2026). Most posts are from
2002-2008, when mangband.org ran MAngband 0.7.x/0.8.x/1.0-1.1. **Anything from before ~2008 is
[MAYBE-OUTDATED] on mechanics.** Almost every death here is of a character level 25-50 at 1000-6350 ft.
Our Half-Orc Warrior throwaway will spend most of its time shallower than that. The lessons still carry
over, because the killers (hounds on arrival, summoners, breathers, lag, bad item addressing, gear swaps)
are the same kinds of thing at any depth.

**Citation convention.** `[pNNN]` means `https://www.mangband.org/forum/viewtopic.php?p=NNN#pNNN`.
Posts without a post id are cited by their topic page URL.
Tags: [NEW], [CONFIRMS], [CONTRADICTS: …]. They compare against `notes_players.md` lines 1-125 and
the HANDBOOK section "How good players play".

---

## Top findings

1. **Arriving on a new level is the deadliest moment, whether by stairs, recall or teleport level.**
   People die before they can act: "staired into time hounds" [p601], "recalled into a room full of
   gravity hounds… second time this week I've rodded into hounds" [p605], teleport level into plasma
   hounds [p691], "You enter a maze of down staircases. It breathes gas. You die." [p5215], a Tarrasque
   on arrival [p6459], stair-scumming from 950 ft straight into water hounds [p2433].
   Pilot rule: on arrival, before doing anything else, scan the view for `Z` packs, breathers (`D`,
   `d`, hydras `M`) and uniques. If any are awake and in view, take the stair you're standing on
   immediately (it is connected). Don't wait to see if they breathe. (2002-2008) [CONFIRMS + sharpens
   the HANDBOOK "staircase underfoot first"]. **Pilot rule.**

2. **Hounds (`Z`) are the top killer in this subforum, at every depth.** Deaths at the depths our
   character will visit: water hounds at ~1000 ft [p2433], energy hounds at 1050 ft [p681], earth
   hounds summoned by a druid at 900 ft [p5152], air hounds at 1550 ft [p667], inertia at 1700 ft
   [p670], vibration at 1750 ft [p901], gravity at 1800-1900 ft [p605][p689], and fire, impact, nether,
   plasma, chaos and time hounds deeper. Handbook doctrine: a `Z` pack in view when you arrive is a
   reason to leave, not to fight. If you must fight, do it in a corridor or around a corner.
   [CONFIRMS "packs that breathe"; NEW: specific hound types by depth]. **Navigator doctrine + Pilot rule.**

3. **Summoners turn an easy fight into a death, and the summoner often looks harmless.** A white `p`
   "looks easy, then… HOUNDS! EVERYWHERE!" [p5077]. Examples: a Mystic summoned a Knight Templar into
   a room full of hounds (1550 ft) [p5467]; a Silent Watcher summoned The Minotaur and an Ancient
   Bronze dragon (1750 ft) [p5661]; a Death Knight summoned Vargo (1900 ft) [p5637]; Grand Master Mystics
   summoned ~100 plasma hounds [p637]; a Scroll mimic in a troll pit (1450 ft) [p898][p899]; a druid
   summoned earth hounds (900 ft) [p5152]; draconic `Q`s summoned dragons [p604][p672]. Veterans'
   advice: "p's are mean and definite ways to die. Mystics, enchantresses and sorcerors. No
   mentionable xp… extreme high risk vs. reward" [p9418]. Handbook: leave the level (or kill or
   teleport the summoner at once) when you see any `p` caster, `Q`, or a message like "magically
   summons". [CONFIRMS HANDBOOK "summoners are the real killers"; NEW: named ones].
   **Navigator doctrine + Pilot rule.**

4. **Escape instead of healing when the damage coming in beats your healing.** Many deaths came from
   "slamming down heals instead of teleporting" [p892], "heal until I'm dry and slowly watch myself die"
   [p2510], or healing against a stream of breaths [p2451][p2479]. Toast on Sauron: "Should have teled
   him" [p617]. BLah: grav breath, "I was at 0, I healed again, 0 again, dead" [p664].
   Rule: if one round of damage exceeds what a potion heals, or more than one breather has line of
   sight, the next action must be an escape (stairs, teleport, or phase to break line of sight), not a
   potion. [CONTRADICTS (partly): HANDBOOK escape order lists "a cure potion" as the third option; the
   forum's rule is that healing only buys time when the damage is survivable]. **Pilot rule.**

5. **Address items by inscription and check that the command worked.** Macros that use inventory
   slots killed people when the inventory reordered: "ERROR! TRIED TO USE NON-STAFF OBJECT" ×5 while at
   0 HP [p2473]; "error quaff non-potion" [p2507]. A new staff of Teleport without its inscription
   meant "Macros no worky without inscription" [p2455]. New potions bought but not inscribed [p920].
   A Staff of Speed and the Staff of *Destruction* both inscribed `@u1` ended with repeated speed instead
   of destruct and a death to time hounds [p5386][p5391]. Identifying a ring swapped its inventory slot,
   so the player put on the unknown cursed Ring of Teleportation [p2440]. Pilot rule: resolve items by
   name and tag every time. Keep tags unique (check for duplicates). After an escape command, check for
   the confirming message ("teleports", a changed position, "You have no more…") and switch to another
   escape at once if it's missing. [CONFIRMS notes' inscription plan; NEW: failure cases to test].
   **Pilot rule.**

6. **Changing gear silently drops resistances, which then kills you.** Paragon wielded a new shield,
   lost the basic resists, and died to one lightning breath at 1850 ft [p638]. Data changed gear, lost
   nether resist, and died to a Dracolisk [p2497]. Crimson: drolems "are especially popular just after
   you've changed gear, and suddenly no longer resist poison" [p2508]. serina swapped boots and armour
   and lost Free Action at 2000 ft [p5577]. Navigator rule: after every equip change, re-derive the
   resist/FA/SI set from the `C` screen and item flags, and re-check the depth cap. **Navigator doctrine
   + Pilot check.** [NEW]

7. **Lag and disconnects kill.** "Do not dive when lag is bad. There is a tendency of important
   commands to arrive just a little too late" [p2473]. Examples: air hounds "during a laggy period"
   [p667], a GMM plus "four star lag followed by packet loss" [p2463], a destruct macro that never went
   through [p2481], a teleport that "lagged" [p2444]. Pilot rule: measure round-trip latency
   continuously. When it is high, stop diving and exploring, stay on or next to stairs, and don't start
   fights. [NEW]. **Pilot rule.**

8. **Closing the client does not save you: the character stays in the dungeon for ~30 s.** "Since you
   quit in the dungeon, it takes 30 seconds for you to log off" [p2465]. Fracasse panicked and closed
   the client, and died [p2534]. Pilot rule: disconnecting is not an escape. Never go idle or away in
   the dungeon: "going AFK in the dungeon is like ALL the seven deadly sins combined" [p4696] (kamrin
   hid behind a wall to answer the door and came back dead [p4692]). [NEW; CONFIRMS memory's
   "idle recall"]. **Pilot rule.**

9. **Word of Recall's delay is a real danger window.** "Why do I always die when recalling?" A Black
   Knight and plasma hounds arrived while Murdin waited on his Rod of Recall [p797]. Murdin also poked a
   Dracolich while waiting to leave and died [p2538]. Pilot rule: after reading recall, move to a safe
   spot (a dead-end corridor, or standing on stairs) and don't fight. If a threat shows up, use the
   stairs. [CONFIRMS "WoR not an emergency escape"]. **Pilot rule.**

10. **Stuns and knock-outs: FA doesn't help, and "Knocked out" means no actions.** Plasma-hound
    breaths got Fink "knocked down… no commands went through" even with 970 HP and Globe of
    Invulnerability up [p2479]. GoI "only prevents hp damage, not status effects" [p2480]. PowerWyrm:
    melee stun is unresistable. The Grand Master Mystic's 20d1/15d1 blows always roll max damage, so
    they always add stun, and three stun increments knock you out; he was stun-locked despite FA and
    resist sound [p9379][p9378]. Water bolts stun and confuse [p5686]. Rule: when you're stunned, escape
    immediately (a heavier stun is next). Never melee Mystics or GMMs. (2003/2013) [NEW]. **Pilot rule +
    Navigator doctrine.**

11. **Confusion without resist-confusion: always carry CCW and a non-scroll escape.** Goofy dropped his
    CCWs to make room for loot, and Ariel confused him every turn until he died. "Always carry CCWs (and
    a staff of teleportation) even at mid/high level until you resist confusion" [p5216]. grisu: "The
    mistakes were lacking rconf and no escape staves" [p5261]. Blind and afraid, with the teleport
    staff already destroyed [p5869]. Chaos hounds chain-confused and hallucinated Domino [p2480].
    [CONFIRMS notes: scrolls unusable while confused/blind, staves usable]. **Navigator shopping rule
    (a Staff of Teleportation as soon as affordable) + Pilot rule.**

12. **Nether in the mid-2000s ft (Dracolich/Dracolisk) is "a common mid-lvl player killer".** It is
    "hard to find resists" at that depth [p2539][p2540]. More cases: a Dracolich at 1000 ft (two
    breaths killed a character that resisted nether) [p2474], "Don't poke the Dracolich" [p2538], 4-5
    Dracolisks at 1950 ft [p614], 3 Dracolisks at 2300 ft [p5786]. Light green `D` = Dracolich; don't
    engage. Navigator depth cap: below ~2000 ft, avoid any `D` without resist nether. [NEW beyond
    notes' checkpoint list]. **Navigator doctrine.**

13. **Poison by 2000 ft, again.** "You know what they say about going below 2k without Poison
    resistance" [p5215]. A Drolem (dark green `g`, "Drolim") took a level 50 from full HP to 2 in one
    breath without rPois [p2507]. Drolems don't show on ESP (no mind): "remember, detect creatures even
    if you have esp" [p2461]. [CONFIRMS notes' 2000 ft rPois checkpoint]. **Navigator doctrine.**

14. **Zoos, animal pits, vaults and pits are traps for greedy players, even at level 50.** "Those animal
    pits are very dangerous, even for players at level 50 that have the resistances" [p913]. Examples:
    zoo hydras [p2456][p2565], a troll pit plus a summoner [p898], a P pit [p4697], an undead pit
    [p5385], the "Zoo of Concentrated Death" vault [p5870], a Greater Vault at 650 ft with
    out-of-depth monsters that killed several rescuers [p684][p686]. Throwaway doctrine: never enter
    vaults or pits. Look at them from a distance at most. [CONFIRMS HANDBOOK "stop for… a possible
    vault" only as a caution; CONTRADICTS: HANDBOOK suggests stopping for vaults; the forum says vaults
    are where diving characters die]. **Navigator doctrine.**

15. **Line of sight: never be in view of more than one breather.** Crimson died at 1500 ft to a
    7-headed hydra while rescuing someone from a zoo: "never expose yourself to LOS of more than a single
    breather at a time. All I needed to do was tunnel in and wait" [p2565]. Corridor or corner
    fighting: "I had a corner to fight 'em around" [p2460]. [CONFIRMS HANDBOOK choke order].
    **Pilot rule (choke / LOS count).**

16. **After death you become a ghost, and the ghost is placed at random, not in a wall.** Source quote:
    on death `teleport_player(Ind, 200)` "does no location checking" [p2470]. Crimson confirms [p2471].
    Ghosts regularly land beside hounds or dragons and are destroyed within 1-2 s [p2464][p2465][p673].
    Ghost `<` floats up a level; spamming `<` gets you to town [p2439][p697]. A careless `<` abandons the
    level with the gear [p604][p2451]. On resurrection you lose levels: "Lost 5 levels too" [p2451],
    "Lost 5 levels" [p2479][p5385], "lost… 3 levels" [p2483]. Death policy for the throwaway: as a
    ghost, press `<` repeatedly to reach town, then resurrect at the Temple (4). Don't try to recover
    gear. [CONFIRMS notes; NEW: random ghost placement, level loss]. **Pilot rule.**

17. **Town is not quite safe.** A level 1 who stood in town chatting was killed by an Aimless Looking
    Merchant [p2502]. Crimson: "just get a bow. A level 1 character can easily kill anything in town
    with a few arrows" [p2505]. Player killers once killed people in town and took their gear [p703]
    [p707]. Later rules banned PK in town, and Crimson planned to hard-code that [https://www.mangband.org/forum/viewtopic.php?t=164&start=60 (Crimson, 18.02.2006)]. A
    level 50 idling in town was killed by another player's mana storm [p2486]. Rule: never idle in the
    open in town. Buy a sling or bow at level 1. [CONFIRMS user's note that townspeople only threaten
    new characters; NEW: bow advice, PK history (MAYBE-OUTDATED)]. **Pilot rule + HANDBOOK text.**

18. **Levels are shared and stay put while someone is on them. Idle levels keep spawning monsters.**
    "If you let a level sit long enough, it gens creatures. The entire… thing was filled" [p2512]. "A
    greater mystic spawned in *right next to me*… because we had been on the level too long" [p686].
    When nobody is on it, a level resets, sometimes within ~20 min [p2511], sometimes after days [p656].
    Recalling onto a level another player occupies lands you at the same "recall point", so BLah
    recalled straight into the hounds that had killed mochi [p657]. Pilot rule: don't linger on one
    level. After another player's death has been announced on a level, don't recall to that depth.
    [NEW]. **Navigator doctrine.**

19. **Teleport gambles, and teleport-to ignores resist nexus.** "Teleported away, since it's safe 99.9%
    of time. Well… not this time" [p5172]. A Nexus Q teleported Hermes next to an awake Ethereal Dragon
    [p642]. Monsters that cast teleport-to (a purple `h` dark elven sorceror, storm giants, angels) can
    pull you into a vault, a zoo or a P pit. "You will only avoid tele-to effect from nexus breathers
    when having res nexus. Monsters with tele_to spell will still be able to produce the effect"
    [p5827][p5465][p4697]. After a teleport, treat the new spot like a fresh arrival (finding #1).
    [NEW]. **Pilot rule.**

20. **Food.** A level 33 paladin relied on Satisfy Hunger, had the book burned by hydra fire, stayed in
    a zoo, and starved [p2454]. Always carry real food, whatever else the character can do.
    [CONFIRMS HANDBOOK spare ration]. **Pilot rule.**

---

## Findings by theme

### A. Arrival / stairs / recall / level transitions
- Stair arrivals into hounds, over and over: time hounds 2400 ft [p601], 3900 ft [p657]; water hounds
  ~1000 ft while stair-scumming down from 950 [p2433]; chaos hounds going up the stairs [p2480];
  plasma hounds while stairing up [p2519]; "You enter a maze of down staircases… It breathes gas. You
  die." [p5215]; Tarrasque, Ancient gold dragon, 7-headed hydra and Dracolich wake on arrival despite
  "You have a good feeling" [p6459]. [CONFIRMS stair-scum risk; NEW frequency]
- **The arrival message is "You enter a maze of down staircases."** (seen in two 2008-2009 chardumps
  [p5215][p6459]). The Pilot can use it as the new-level trigger. [NEW]
- The level feeling is not a danger signal to rely on: a "good feeling" level held the Tarrasque
  [p6459]. [CONFIRMS notes: feelings hint at loot]
- Recall arrivals: "rodded into hounds" twice in one week [p605]; "the recall point for 1k and the stairs
  are right there together" [p2433]. On a level that someone is holding, recall drops you at a fixed
  "recall point" [p609][p652][p657]. "if i only knew the stairs were safe before i recalled" [p660].
  [NEW, MAYBE-OUTDATED]
- Teleport Level can drop you among hounds on the level below [p691]. [NEW]
- The recall delay is a danger window [p797][p2538]. PowerWyrm thought a recall rod might have "kicked
  in before death" while he was confused, but grisu says confusion would just recur [p5218][p5261].
  [CONFIRMS]
- In a hurry, `<` next to `M` (map) got mistyped: Maegdae pressed `<` as a ghost and lost the level
  [p2451]; Narchan did the same [p604]. For the Pilot: only use `<`/`>` when it means to. [NEW]

### B. Monsters and situations (by threat type), with the response

**Hounds (`Z`)**. See Top #2. Extras:
- Hounds breathe on items lying on the floor and destroy them. "please don't stand on my gear while
  you fight hounds; they will breathe on it" [p619]. [NEW]
- Aether hounds' gravity breath: "I was at 0, I healed again, 0 again, dead" (4950 ft) [p664].
  Plasma breath stuns and knocks out [p2479]. Chaos hounds confuse and hallucinate [p2480]. Time
  hounds drain stats and XP ("You're not as hale…", "life has clocked back") [p5386][p697].
- Response: fight in a corridor or tunnel mouth, or around a corner [p2460][p2565]. Quaff speed before
  opening up to them [p892].

**Breathing dragons (`D`/`d`) and hydras (`M`)**
- "Flashing" (multi-hued) `D`: Ancient Multi-Hued Dragon killed at 1800-2750 ft [p597][p599][p638]
  [p5925]. A flashing `D` can also be a Great Wyrm of Chaos: "watch out for those flashing Ds" [p2460].
  Avenger "decided to check it out" and died to three breaths [p599]. Rule: don't approach a flashing
  `D`. [NEW]
- Ethereal dragon: light/dark breaths do min(HP/6, 400) damage, cut to 4/(d6+6) of that when
  resisted, and AC doesn't reduce it. An Ethereal dragon has 2100 HP, so each breath is 350 (source
  quote) [p646]. It killed a 400 HP character with both resists in 3 breaths [p642][p645], and killed
  others at 2000-2200 ft [p2438][p5409]. (2003) [NEW]
- Great Storm Wyrm out of depth at 1050 ft killed a level 26 rogue [p2448]. At 1650 ft one lightning
  breath killed 4 party members [p5241][p5243]. Great Wyrm of Law at 1650 ft [p2449]. Pazuzu "over 1k
  OoD" [p2450]. [NEW: very out-of-depth breathers show up around 1000-1700 ft]
- Dracolich (light green `D`) and Dracolisk: nether and fire. See Top #12 [p609][p614][p2474][p2538]
  [p2539][p2540][p2516][p2413].
- Hydras in zoos: 9- and 11-headed breathe fire and are "faster than I was expecting" [p2456]. A
  7-headed hydra killed Crimson at 1500 ft [p2565]. A hydra killed McLovin at 2000 ft [p5289].
  [NEW]
- Mature red dragon killed a ghost [p2516]. Young green dragon gas plus a hidden Drolem [p2444].

**Golems**
- Drolem (dark green `g`): poison breath, invisible to ESP [p2461][p2507][p2508][p2444]. Berendol's
  first reaction was "What's a dark green g? … run away!" [p2459]. Eog Golem killed a ghost in two
  blows [p5669]. [NEW]

**Summoners** (Top #3). More: a Greater Balrog "magically summons greater demons", and a Pit Fiend
then summoned ancient dragons and breathed chaos. That killed a level 50 warrior who went back to fight
after teleporting away [p4676]. Great mystic at 1950 ft [p4780]. Dreadlord summons [p655]. A unique `Q`
"summons like crazy" and teleport failed [p2510]. An eye druj [p5102]. "g summoning stuff" (1900 ft)
[p5573].

**Mystics** (Top #10): stun-lock; "ignore them, banish them or teleport them away" [p9379].

**Uniques met at warrior depths**
- Orfax (500 ft) with a brown yeek swarm; something in the clump confused the level 13 dwarf warrior,
  and a Swordsman joined in. Lured into a corridor, they were easy [p2440]. [CONFIRMS corridor doctrine]
- Shagrat at 550 ft was too strong for a mage to rescue against [p687]. Gorlim at 650 ft [p684], at
  1800 ft [p5684], at 2050 ft [p5621]; "Gorlim… casts a mana bolt… You die" [p5212]. Saruman at 1550 ft
  [p669]. Vecna at 2100 ft [p671]. Kavlax at 1850 ft [p5742]. Carcharoth at 2750 ft 1-on-1 [p5808].
  Vargo (summoned) [p5637]. Wormtongue in the wilderness [p5707]. Ariel (confusion) [p5216]. Huan
  "looks like one of Maggot's dogs and you don't know what is happening until too late" [p5863].
  Uriel/Azriel at 2800-3850 ft [p616][p922][p2497].
- "5 heroes killed by a Novice paladin": in the 2008 "top killers of characters above level 20" list,
  Novice paladins killed level 25-29 paladins [p5360]. The "they gain XP" explanation in that post is
  a joke (Berendol files it under wishes [p5362]). The kill count itself is real data. [NEW]
- Winged Horror (life drain plus gas breath) [p5212]; Cat Lord [p5292]; Great Wyrm of Perplexity
  [p5214]; Ogre Shaman "all it takes sometimes" [p5874].

**Invisible / unseen**
- Dreads that couldn't be seen attacked a ghost [p637]. An unseen "ghost monster" followed a ghost
  through walls [p5925]. A gray `X` attacked a ghost [p2510]. [CONFIRMS HANDBOOK: invisible monster that
  hurts means leave]

**Breeders**: mice bred outside a vault and killed a ghost [p5152]. [CONFIRMS HANDBOOK breeders]

**Wilderness** (MAngband-specific): the northern "dark forest" held a Master lich, mirkwood spiders,
dark elf druids and forest wights, and killed a mid-20s Half-Orc rogue who "tried shooting it instead
of reading my teleport scroll" [p5698]. Players say the wilderness is "normally… sort of safe" and
advise: "hug the borders between zones, so if something bad shows up you can just go to another zone.
Try and bring a missile weapon" [p5703][p5714]. Players' piles of gear and gold lie around out there
[p5707]. Wilderness depths are negative ("-1196", "-29850ft") [p5707][p5703]. (2008) [NEW;
cross-check with memory's wilderness findings]

### C. Escape and healing doctrine
- Escape rather than heal when the damage rate beats your healing (Top #4).
- **Escape redundancy.** One escape type is not enough. Deaths with "my last tele disappeared"
  [p898], "teleport staff… destroyed in my previous battle" (fire destroys staves) [p5869], and "tried
  to tele but can't… again didn't work" [p2510]. Portal failed twice in a row [p2512]. Carry two kinds
  of escape (Phase + Teleport scroll, later a Staff of Teleportation) and count charges.
  [NEW/CONFIRMS]
- Books and scrolls burn: "Vargo casts a fire ball, my books burn, I panic" [p5637]; the Satisfy
  Hunger book was destroyed [p2454]; potions of Speed shatter from frost breath [p6459]. Keep spares.
  [NEW]
- Speed: "That's why speed is so incredibly important" [p648]. "Made the mistake of not quaffing a
  speed" [p892]. Berendol died right after the speed from his staff wore off [p2459].
- The "no light to read by" bug: after the floor grid under you is darkened, scrolls can fail with
  "you have no light" even when you carry a light. "The only way to fix this… is to move" (known bug,
  2008) [p5884]. Pilot fallback: if a read fails with that message, use a staff or potion, or step
  once. [NEW]
- Earthquake from swapping weapons as a last resort (it can wall off a monster) [p5261]. But Falx's
  earthquake took him from 4 HP to 0 [p913]. [NEW, low value]
- "Tunnel in and wait" beats standing in a room [p2565]. But "Tunnel deaths are never fun": Murdin
  died at the mouth of the tunnel he had dug to lure hounds [p892][p893].
- Mass genocide / *destruction* can fail in a panic [p649][p2492]. *Destruction* next to other people's
  gear destroys it [p623][p2433].
- CCW taking effect on the same turn as the killing blow shows how narrow the margins are [p5292].

### D. Depth / gear checkpoints and diving pace
- rPois by 2000 ft [p5215][p2507] [CONFIRMS]. Nether danger around 1950-2750 ft [p2540] [NEW].
  Double-resist fire/lightning matters deeper [p619][p621][p2517]. Sound/disenchant were Fink's
  after-thoughts [p2479].
- FA: serina lost it at 2000 ft through a swap [p5577]. KK Daemon's fruit-bat death is joked about as
  "just tell them you were paralyzed" [p2442]. [weak CONFIRMS of the FA checkpoint]
- ESP doesn't replace detection: Drolems and non-mind monsters don't show [p2461][p2497]. A Dracolisk
  "slipped by my detection" [p2459]. Carjacker, a Half-Troll warrior, had "no detection whatsoever (he
  was a warrior)" and died after a mis-teleport [p5152]. Navigator shopping: buy detection for the
  warrior (Rod/Staff of Detect Evil, or Detection) [NEW].
- Pace examples: Warrior recalled to about 4350 ft and "quickly moves down the stairs" to 4950 ft
  [p4676]. Falx got "over 10M exp without going deeper than 2100" [p914]. Farming at a safe depth
  works. [NEW]
- Coming back after a break: "Usually when I stop playing for weeks I also end up doing mistakes like
  this" [p4677]. Warrior's first dive back was a test dive to 2000 ft [p4676]. For a new or reloaded
  Pilot build, do a shallow shake-down dive first. [NEW]
- Warriors vs mages: warriors are "good-to-start-lame-later" and mages the reverse [p2517]. "Double res
  is just annoying with a warrior. How are you supposed to carry masses of loot back up if your
  inventory is full of preventitive measures" [p2516]. [NEW]

### E. Inventory, items, identification
- Items by tag (Top #5). Also: the Ring of Teleportation is cursed and teleports you "at a dizzying pace"
  (faster than in single-player). The Temple sells Remove Curse [p2440]. **Don't put on unidentified
  rings/amulets, or re-resolve by name after an identify.** [NEW]
- Reading a scroll you don't know or shouldn't: a Summon Monster scroll brought impact hounds [p2512];
  reading Genocide in town killed Crystal ("6, 5, 4, 3, 2, 1, 0, ghost") [p2513]. This supports the
  HANDBOOK policy of selling unknown scrolls instead of read-testing them. [CONFIRMS]
- Monsters pick up your dropped gear: a Greater titan [p2457][p682], a giant [p661], a Knight Templar
  [p5467], "some shaith hole p took my f… lamp" [p901], an elemental took a cloak [p734].
- A full inventory at death seems to make you lose house keys [p2475][p2477][p2478]. (Crimson: the key
  gets "bumped" out while items drop.) For us: only matters if we ever buy a house. [NEW,
  MAYBE-OUTDATED]
- The `!` inscriptions work as protection: `!wsdv` stopped Fink wearing, selling, dropping or throwing
  his key [p614]. [CONFIRMS notes' `!` list]
- Don't drop your cure potions to make room for loot [p5216]. Don't give your *Healing* potions away
  [p2492].

### F. MAngband-specific (multiplayer, ghosts, server)
- **Ghost mechanics** (Top #16). Also: ghosts pass through walls and "float" with `<` [p2439][p697].
  Ghosts have "Undead Powers like blink, teleport self and the various offensive powers" [p2472].
  Ghosts can be destroyed by monsters and by players [p600][p2530][p738]. A ghost death isn't recorded
  in the highscore [p741]. Someone else can raise you with a Scroll of Life on the level [p609][p902].
  Surfacing as a ghost from the bottom took about a day of spamming `<`, and a time vortex drained CON
  on the way [p697].
- **Brave characters** (2008, 1.x): "Since the character was brave, there was no possibility to
  browse the last messages online, since the only thing you can do when the death screen appears is to
  close your client" [p5435]. "The brave hero Soranchu was killed…" [p5243]. So a no-ghost mode
  existed. The Architect should check whether the 1.5.x server has a `brave`/no_ghost birth option and
  whether the throwaway should use it (it avoids ghost handling but makes every death final). [NEW]
- **Chardump and Scene of Death**: mangband.org used to publish each dead character's last messages
  and a map of where they died (HighScoreChart) [p5212][p5071]. The @ position on the map is sometimes
  wrong [p5451]. For post-mortems, the Pilot should log the last ~50 messages and a map snapshot
  itself. [NEW]
- **30-second in-dungeon logout; one character online at a time** (Top #8) [p2465][p2463].
- **Levels stay while occupied and keep spawning; they reset when empty** (Top #18). A player may
  "static the level" for someone else by staying on it [p5152][p5467].
- **Other players.** PK is legal outside town on mangband.org. PK in town was banned by rule, and
  pvp requires going "hostile". Teleporting another player out of a shop does not by itself make you
  hostile (Varguar [p2500]; contradicted by Data's experience [p2498]). Killing ghosts was legal but
  frowned on. Bragging about good finds gets you hunted: "if you find Ringil at 1200, don't tell"
  [p2548][p2549]. Handing gear or power to a lower character ("bumping") breaks the
  rules and gets characters deleted [p2501]. Audits delete long-absent characters holding artifacts
  [p676][p677]. For the tool: never go hostile, never chat, and don't transfer items between tool
  characters. (2003-2006) [NEW, MAYBE-OUTDATED]
- **Rescue culture**: people ask for rescues in this forum. Rescuers often die too [p684][p686][p899]
  [p910][p912]. The solo tool should not try to rescue anyone and should not answer rescue requests.
  [NEW]
- The server crashed when Carcharoth died [p5808] and on other occasions. Items can be duplicated on a
  crash [p814]. [NEW, trivia]
- Artifacts are scarce because of hoarding; `~` shows the list of claimed artifacts [https://www.mangband.org/forum/viewtopic.php?t=162&start=15 (Murdin, 07.02.2006)].
  "Don't think you absolutely HAVE to have an art to do well" [same]. [NEW]
- Party deaths: "Your party has been disbanded" appears when a party member is killed [p5243]. [NEW]

### G. UI / automation-relevant
- Players asked for exactly the Pilot's approach: "Modify the client to autotrigger destruction or
  another escape depending on the current hp" [p2562]. Avenger's reply: "maybe have a new type of macro
  that's conditional" [p2563]. Domino wanted a `Ghost.prf` keymap that loads automatically on death,
  so ghost powers are on the usual escape keys [p2472]. The tool can do this natively. [NEW, motivation]
- Deaths from wrong keys (caps lock, sticky keys, a Windows popup) all show the same failure: an escape
  sent but not carried out [p916][p2433][p2435]. The Pilot must check that its commands took effect
  (Top #5).
- Deaths while using the Look command: Morgoth "jumping me while using the Look Command" [p2557].
  Don't leave the character in a modal or look state. [CONFIRMS notes: keep no prompts pending]
- `\e\e` at the start of macros clears pending prompts. Fink blamed his macros and then found they
  worked fine [p2492][p2493]. [CONFIRMS]
- Playing tired or late is behind many deaths (Hal "I was tired and stupid" [p5573]; Ace "must avoid
  playing when tired" [p5392]; serina "Don't play at 3.15 AM" [p5577]; Hades [p655]). The bot's
  equivalent: stale state or a hung decision loop. A watchdog should stop diving if the loop falls
  behind. [NEW, analogy]

### H. Things that don't work / common mistakes (compact)
- Checking out a flashing `D` or a light green `D` "for fun" [p599][p2538][p2474].
- Assuming a greater titan is no harder than a lesser titan [p2457].
- Fighting a unique 1-on-1 at depth (Carcharoth [p5808], Tarrasque [p5877]).
- Going back to the fight after escaping [p4676][p5409].
- A ghost going back to look at its death site [p2457][p2516][p2530].
- Staying on a great level while hungry [p2454].
- Diving in a party below your resist level because the party wants to [p5215].
- Picking the wrong escape (shooting instead of teleport [p5698]; staff of teleportation instead of
  perception [p5152]; speed instead of heal [p4676][p5860]).

---

## Death catalogue

Depth in ft. "?" = not stated. Char = character level/race/class, where given. Most posts are 2002-2008.

| # | Cause / monster | Depth | Char | Mistake | Lesson | URL |
|---|---|---|---|---|---|---|
| 1 | Ethereal dragon (near Death Knight, Lesser Titan, Medusa) | 2000 | ? (Narchan) | Died among many threats | Pick where you fight; ghost: spam `<` to reach town | [p2438][p2439] |
| 2 | Ancient Multi-Hued Dragon | 2750 | ? mage-ish (Maegdae) | ? | Deep breathers | [p597] |
| 3 | AMHD breathed 3× | 1800 | ? (Avenger) | Went to "check out" a flashing D | Don't approach flashing `D` | [p599] |
| 4 | Time hounds on stair arrival | 2400 | ? paladin party | Took stairs into a pack | Leave at once on arrival | [p601][p602] |
| 5 | Greater draconic `Q` summoned dragons | 3750 | ? | `Q` summoner; then pressed `<` as a ghost | Kill or escape summoners; careful keys as a ghost | [p604] |
| 6 | Gravity hounds at recall point | 1900 | ? (Toast) | Recalled into hounds (2nd time that week) | Recall arrival = danger; rescuers should take stairs down | [p605] |
| 7 | Morgoth mana storms | 6350 | L50 | Fought Morgoth | — (endgame) | [p607] |
| 8 | Time hounds | 5500 | L50-ish | ? | Time hounds kill even L50s | [p608] |
| 9 | Dracolich | 2700 | ? (Berendol) | ? | Dracolich is a mid-level killer | [p609] |
| 10 | Tarrasque | 6350 | ? | Reached the bottom | — | [p612] |
| 11 | 4-5 Dracolisks breathing nether | 1950 | ? (Fink/MARV) | Rescue attempt in a tight spot | Don't rescue; nether ~2000 ft | [p614] |
| 12 | Greater titan in a lesser vault | 2800 | ? | Vault | Vaults | [p615] |
| 13 | Uriel | 2800 | ? | ? | Angels at ~2800 | [p616] |
| 14 | Sauron's darkness storms | 6350 | L50 (Toast) | Tunneled in and tried to hold him | "Should have teled him" (teleport-other) | [p617] |
| 15 | Plasma hounds + Great Hell Wyrm | 2750 | ? (Maegdae) | Temp double resist fire ran out | Watch timed buffs; leave before they expire | [p619] |
| 16 | Tiamat double lightning | 6350 | ? | No double resist lightning; died in an anti-summoning corridor | Gear lost there | [p621][p622] |
| 17 | Phoenix plasma ×2 from behind | 3000 | Dunadan Ranger | Fighting a troll pit, not watching behind | Watch your flanks at pits | [p623] |
| 18 | Grand Master Mystic summoned ~100 plasma hounds; invisible Dreads hit the ghost | 3250 | ? (Avenger) | Too slow on the heal macro | Escape at first sight of a GMM | [p637] |
| 19 | AMHD lightning | 1850 | ? (Paragon) | Wielded a new shield and lost basic resists | Re-check resists after every swap | [p638] |
| 20 | Nexus `Q` teleported him to an awake Ethereal dragon, 3 breaths | 2200 | 400 HP, rDark+rLight | Teleported next to a breather | Light/dark 350/breath formula; after a teleport treat as arrival | [p642][p646] |
| 21 | Carcharoth; mass genocide failed | 6350 | ? | Panic | — | [p649] |
| 22 | Morgoth | 6300 | Mage (Nannif) | — | — | [p652] |
| 23 | Dreadlord summons | 6350 | L50 (BLah) | "way over tired… didn't react" | Don't play tired / watchdog | [p655] |
| 24 | Time hounds on stairs; rescuer recalled into the same spot | 3900 | ? (mochi, BLah) | Stairs into a pack; rescuer recalled onto the killers | Don't recall onto a level where someone just died | [p657][p660] |
| 25 | Aether hounds gravity breath | 4950 | ~L44 | Healed from 0 instead of escaping | Escape > heal | [p664] |
| 26 | Air hounds during lag | 1550 | ? (Anyar, isengard) | Played through lag | No diving when lagging | [p667] |
| 27 | Saruman | 1550 | ? (Anyar) | ? | Unique casters mid-depth | [p669] |
| 28 | Inertia hounds in a large vault | 1700 | ? | Vault | Vaults | [p670] |
| 29 | Vecna | 2100 | ? | ? | — | [p671] |
| 30 | Draconic `Q` summoned `D`s | 3950 | ? (Gargoyle) | "wasn't paying attention" | Summoners | [p672] |
| 31 | Summoned room of AMHDs; ghost popped among green `Z`s | ? deep | L49 (BigJuan) | — | Random ghost placement | [p673] |
| 32 | Energy hounds | 1050 | ? | ? | Hounds at warrior depths | [p681] |
| 33 | Greater titan | 2400 | ? (L'ac) | ? | Titans | [p682] |
| 34 | Greater vault with OOD monsters (Gorlim, greater mystic, lich, inertia/earth hounds); several rescuers died | 650 | multiple | Explored a GV at 650 ft; stayed too long, so new monsters spawned | Never enter vaults; don't linger | [p684][p686] |
| 35 | Shagrat the Orc Captain | 550 | ? (Cherez) | ? | Shallow unique; a mage couldn't rescue | [p687] |
| 36 | Gravity hounds | 1800 | ? (Zeb) | ? | Hounds | [p689] |
| 37 | Teleport level into plasma hounds | 3050 | ? (Fracasse) | Teleport level blind | Treat a new level as arrival | [p691] |
| 38 | Tarrasque with line of sight through a *destruction* patch, from range | ~6000 | L50 mage | Open LOS after *destruction* | *Destruction* opens sightlines | [p695] |
| 39 | Player killer "Grez" (L27) in town, took gear, killed ghosts | town | several | AFK or shopping in town | PK history; don't idle in town | [p703][p707][p717] |
| 40 | PK by Bigjuan; ghost killed by Angus | 1800 | L36 Dunadan Warrior | Had publicly posted about an artifact hoard, stayed on the level as a ghost | Don't brag; as a ghost, log out or float up | [p735][p740][https://www.mangband.org/forum/viewtopic.php?t=164&start=30 (Big_Juan, 17.02.2006)] |
| 41 | Black Knight + plasma hounds while waiting on recall | 3350 | ? (Murdin) | Stood in the open during the recall delay | Wait in a safe spot | [p797] |
| 42 | Aether/chaos hounds at the tunnel mouth | 4650 | ? (Murdin) | No speed potion; healed instead of teleporting | Speed first; escape > heal | [p892] |
| 43 | Gothmog + Morgoth | 5050 | ? | — | — | [p895] |
| 44 | Troll pit + summoning Scroll mimic; last teleport gone; rescuer also killed | 1450 | ? (Billsey), Avenger | Out of teleports | Count escapes; mimics summon | [p898][p899] |
| 45 | Vibration hounds; a `p` stole the lamp | 1750 | ? | ? | Monsters loot gear | [p901] |
| 46 | ? | 700 | L21 warrior | ? | Warriors die ~700 ft too | [p907] |
| 47 | Tarrasque in a big vault; rescuer died, ghost killed by Mouth of Sauron | 4300 | ? | Vault | — | [p909][p910] |
| 48 | Zoo + 3 Dracolisks; own earthquake took him from 4 HP to 0; ghost killed by a Dracolisk | 2000 | L50 (Falx) | Animal pit | "animal pits are very dangerous, even for L50" | [p913] |
| 49 | Chaos beetle | 1400 | ? (sbluen + Huma) | ? | — | [p915] |
| 50 | Nether hounds from a GV door; caps lock made his macros cast the wrong spells | 2250 | ? (sbluen) | Wrong keys | Check that the command worked | [p916] |
| 51 | Greater titan | 2550 | ? (sbluen) | Forgot to inscribe newly bought potions | Inscribe on purchase | [p920] |
| 52 | Uriel spawned | 2850 | ? (Huma) | ? | Angels | [p922][p923] |
| 53 | ? | 1000 | ? | ? | — | [p924] |
| 54 | Water hounds on stair arrival; later ghost died to water hounds and Windows sticky keys | 1000 | ? (BigJuan) | Stair-scummed into a pack | Leave on arrival | [p2433] |
| 55 | Fruit bat | ? | ? (KK Daemon) | Probably paralysis (joke) | FA | [p2441][p2442] |
| 56 | Great Storm Wyrm (way out of depth) | 1050 | L26 Rogue | ? | OOD breathers around 1000 ft | [p2448] |
| 57 | Plasma hounds after `>` once lag cleared; `<` as a ghost | 3600 | ? (Maegdae) | Wrong key; lost 5 levels | Levels lost on death | [p2451] |
| 58 | Starvation | ? (zoo) | L33 Paladin | Relied on Satisfy Hunger; book burned; stayed | Carry food | [p2454] |
| 59 | Hounds + hydras | ? | L32 (Toast) | New Staff of Teleport not inscribed | Inscribe | [p2455] |
| 60 | 9- and 11-headed hydras breathe fire in a zoo; ghost killed | ? | L31 Rogue | Underrated zoo hydras | Zoos | [p2456] |
| 61 | Greater titan in a GV | 1800 | ? (Volrak) | Assumed a greater titan is like a lesser; ghost went back | Don't re-approach as a ghost | [p2457] |
| 62 | Tarrasque; ghost faded | 6350 | ? (Cheesetoast) | — | — | [p2458] |
| 63 | Dracolisk after an Ethereal D + dark hounds; speed staff out of charges | 2200 | L35 Paladin | Vault; detection missed it | Detection isn't complete | [p2459] |
| 64 | Great Wyrm of Chaos mistaken for AMHD; gravity hounds | ~3000 | ? (Froof) | Misidentified a flashing D | Flashing D = unknown danger | [p2460] |
| 65 | Drolem not on ESP after stone-to-mud | ? (vault) | party | Trusted ESP | Detect even with ESP | [p2461] |
| 66 | GMM + lag + packet loss; ghost next to a Great Storm Wyrm | 3100 | L35 Priest | Lag | Random ghost placement; 30 s logout | [p2463][p2466] |
| 67 | Ghost popped next to ethereal hounds | ? | L48-50 (BigJuan) | — | Ghost placement | [p2464][p2465] |
| 68 | Green dragon fly poison + manticore; lag made the staff command fail ("non-staff object"); then a Stegocentipede; the delayed `<` fired as a ghost | ? (vault) | L16 Mage | Played through lag; slot-based macro | Tags plus a lag gate | [p2473] |
| 69 | Dracolich from a 5-square vault (hoped it was a Death Drake), 2 nether breaths | 1000 | ? (Avenger) | Stayed adjacent hoping for a crit | Don't fight light green `D` | [p2474] |
| 70 | Teleported into aether hounds | ? | ? (Maegdae) | — | Teleport = arrival; key lost | [p2475] |
| 71 | Carcharoth + 15 plasma hounds; knocked out despite GoI and 970 HP | deep | Mage (Nannif) | No resist sound | Stun/KO ignores HP | [p2479] |
| 72 | Chaos hounds on the up stairs; confused and hallucinating | ? | Domino | No resist chaos | Status effects beat healing | [p2480] |
| 73 | Morgoth while lagging | ? | ? (Narchan) | Lag | Lag | [p2481] |
| 74 | Chaos wyrm; ghost killed by a nether wraith; client froze | ? | ? (Xander) | — | — | [p2484] |
| 75 | PK mage mana storm in town | town | L50 (Maegdae) | Standing in town without a finger on teleport | Don't idle in town | [p2486][p2489] |
| 76 | Morgoth summons; had given away his *Healing* potions | deep | Mage | — | Keep your consumables | [p2492] |
| 77 | Uriel/Azriel; ghost killed by hounds | 3850 | ? (Paragon) | — | — | [p2497] |
| 78 | Dracolisk nether in an animal pit | 2200 | ? (Data) | Changed gear, lost resist nether; ignored advice to avoid pits | Re-check after swaps; avoid pits | [p2497] |
| 79 | Accidental PK after a hostility mix-up | ? | Bud Spencer | — | Stay non-hostile | [p2498] |
| 80 | Aimless Looking Merchant | town | L1 | Chatting AFK in town | Stay in the home until L3; buy a bow | [p2502][p2504][p2505] |
| 81 | Drolem poison, "quaff non-potion" | ? | L50 (Hades) | No rPois; slot macro | rPois; tags | [p2507][p2508] |
| 82 | Unique `Q` summons; teleport failed; healed dry; ghost killed by a gray X and a dread | ? | Hades | Rushed through doors at a `Q` | Don't approach summoners | [p2510] |
| 83 | Hounds adjacent while stair-scumming with a full pack; stunned | ? | Hades | Misread the map | Look before acting on arrival | [p2511] |
| 84 | Read Genocide in town | town | ? (wckg server) | HP cost of genocide | Don't read "power" scrolls blindly | [p2513] |
| 85 | Dracolisk fire; ghost killed by a mature red dragon while viewing the drop | ? | L42 High-Elf Warrior, +23 speed, 5 bpr, 878 HP | No rNexus/rPois; ghost lingered | Ghost: leave | [p2516] |
| 86 | Master mystic summoned chaos hounds; plasma hounds on the up stairs | ? | L50 Half-Orc Ranger | — | Mystics, arrivals | [p2519] |
| 87 | Ghost confused, killed by Nar | ? | Kimmuriel | — | — | [p2529] |
| 88 | Mirkwood spiders killed the ghost | ? | MunkYBoY | Ghost went looking for the death site | Ghost: don't go back | [p2532] |
| 89 | Nether breather on login; closed the client | 2300-3000 | Fracasse | Closing ≠ escape (30 s) | Never disconnect to escape | [p2534][p2537] |
| 90 | Dracolich (fire, nether, nether) | ? | Dwarf (Murdin) | Poked it while about to recall | Don't poke | [p2538] |
| 91 | Tarrasque; ghost killed next to Mouth of Sauron | 4300 | 2×L50 (Avenger) | Rescue attempt | — | [p2552][p910] |
| 92 | Morgoth + Ungoliant, Gothmog, Pazuzu during Look | deep | Fink | In look mode | No modal states | [p2557] |
| 93 | ? | 1350 | L32 (Drag) | ? | — | [p2564] |
| 94 | 7-headed hydra (zoo rescue) | 1500 | Crimson | In LOS of several breathers | One breather in LOS max; tunnel in and wait | [p2565] |
| 95 | Greater Balrog summoned greater demons; Pit Fiend summoned ancient dragons and breathed chaos | 4950 | L50 Dunadan Warrior | Went back to fight after teleporting; quaffed speed instead of heal; rusty after a break | Don't re-engage; shake-down after breaks | [p4676][p4677] |
| 96 | P pit; ghost rammed by a storm giant | 2000 | Mage (kamrin) | Went AFK | Never AFK in the dungeon; tele-to into P pits | [p4692][p4696][p4697] |
| 97 | Great mystic summons | 1950 | Paladin (Ace) | GV | Mystics | [p4780] |
| 98 | `p` (white; probably a summoner) summoned hounds | ? | serina | Thought the white `p` was easy | Summoners | [p5071][p5077] |
| 99 | Eye druj | 2150 | Zenith | "playing around with an eye druj" | — | [p5100][p5102] |
| 100 | "RNG" | 200 | ? (Billsey) | (screenshot only) | — | [p5146][p5154] |
| 101 | Mis-used Staff of Teleportation instead of Perception; druid summoned earth hounds; ghost killed by breeding mice | 900 | Half-Troll Warrior | No detection (warrior); tired | Warriors need detection | [p5152] |
| 102 | Teleported away from `L`s into something worse | 3200 | Priest (PowerWyrm) | Teleport gamble | Teleport isn't safe | [p5172] |
| 103 | Winged Horror gas / Gorlim mana bolt / Great Wyrm of Perplexity (dropped *ID* in melee) | ? | various | — | — | [p5212][p5214] |
| 104 | Gas breath on arrival, below 2k without rPois | >2000 | party (Ashi) | Dove with a party past his resists | rPois by 2000 ft | [p5215] |
| 105 | Great Storm Wyrm lightning, 4 players | 1650 | party | Group fought in LOS | LOS rule | [p5234][p5243] |
| 106 | Cat Lord (CCW landed as he died) | ? | ? | — | Margins | [p5292] |
| 107 | Ariel confusion every turn | ? | Dwarf Paladin (Goofy) | Dropped CCWs for loot; no rConf, no escape staff | Always carry CCW + staff | [p5216][p5261] |
| 108 | Time hounds / a hydra / impact hounds + Ibun + sorcerer | 2950 / 2000 / 2500 | Huma / McLovin / Acenoid | — | — | [p5289] |
| 109 | Great Wyrm of Chaos | 3750 | Ace | Didn't *destruct* | — | [p5363] |
| 110 | Undead pit, nightwing | ~3500 | Murdin (party) | Followed into a pit | Pits | [p5385] |
| 111 | Time hounds; Staff of Speed and Staff of *Destruction* both `@u1` | 4700 | ~L47 (Ace) | Duplicate inscription; tired | Unique tags | [p5386][p5391][p5392] |
| 112 | Ethereal dragon double light breath | 2000 | Huma | Went back to the D after fleeing | Don't re-engage | [p5409] |
| 113 | Teleport-to by a dark elven sorceror into a vault full of plasma hounds | ? | Dunadan Mage | Near a vault with a tele-to caster | Tele-to ignores LOS/vault checks | [p5435][p5462] |
| 114 | GV slaughter of a mage, rogue and ranger | ? | midlevel | GV | Vaults | [p5455] |
| 115 | Mystic summoned a Knight Templar amid hound packs | 1550 | Billsey | Fought a mystic | Mystics | [p5467] |
| 116 | `g` summoning | 1900 | Hal | "tired and stupid… think about which macro to press" | Decide fast | [p5573] |
| 117 | ? (after losing FA through swaps; ISP dropped) | 2000 | Warrior (serina) | Swapped boots and armour, lost FA; 3:15 AM | Re-check FA after swaps | [p5576][p5577] |
| 118 | Small vault; Gorlim | 2050 | Hal | Vault | — | [p5621] |
| 119 | Death Knight summoned Vargo (fire ball burned books, then plasma bolts) | 1900 | Thorbear | Panic | Books burn | [p5637] |
| 120 | Silent Watcher summoned The Minotaur + an Ancient Bronze; after a reset, an Eog Golem killed the ghost on login | 1750 | Billsey | Vault; ghost logged in on a new level | Ghost login danger | [p5661][p5669] |
| 121 | Gorlim; water bolts stun and confuse | 1800 | Thorbear | — | Water = stun + conf | [p5684][p5686] |
| 122 | Master lich in the northern wilderness forest | wilderness | ~L25 Half-Orc Rogue | Shot instead of reading teleport | Escape first | [p5698] |
| 123 | Kavlax after several confusion breaths | 1850 | Fx71 | Ignored confusion, went after summoners | Confusion = leave | [p5742] |
| 124 | Plasma hound; 3 Dracolisks let out of a pit by a tunneler | 2300 | ~L40 (Schmage) | — | Pits open | [p5786] |
| 125 | Carcharoth 1-on-1 | 2750 | Schroeder | Fought a unique alone | — | [p5808] |
| 126 | Tele-to into a zoo despite rNexus (11-headed hydras, chaos hounds) | 3100 | Schroeder | Next to a zoo | Tele-to ignores rNexus | [p5821][p5827] |
| 127 | Azriel's angels teleported him next to Huan | 6350 | Schroeder | Hit speed instead of heal | Right key | [p5860][p5863] |
| 128 | "Zoo of Concentrated Death" vault; blind and afraid; teleport staff already destroyed | 1800 | party (Elven Dopes) | Vault scumming; missing staff | Escape redundancy | [p5869][p5870] |
| 129 | Tarrasque; *destruction* staff vs scroll mix-up; "no light to read by" bug | deep | Schroeder | Changed escape item type | Light bug: move | [p5877][p5884] |
| 130 | Ancient multi-hued dragon, huge open room; unseen ghost monster hit the ghost | 2150 | Thorbear | — | Open rooms | [p5925] |
| 131 | Tarrasque, frost breath on arrival ("good feeling") | ? | ? | — | Feeling ≠ safety | [p6459] |
| 132 | Grand Master Mystic stun-lock, knocked out | ? | userjjb (FA, rSound) | Meleed a GMM | Melee stun unresistable; teleport them away | [p9378][p9379] |
| 133 | Tarrasque (didn't notice the flashing `R`) | ? | Avenger | Missed a threat on screen | Scan the view | [p9441] |
| NM1 | Near-miss: cursed Ring of Teleportation | 500 | L13 Dwarf Warrior | Put on the wrong ring after an ID changed slots | Resolve by name; Remove Curse at the Temple | [p2440] |
| NM2 | Near-miss: Drolem gas mistaken for a young green d; lagged teleport | ? | Maegdae | Misread who was breathing | Check the attacker's name | [p2444] |
| NM3 | Near-miss: read Summon Monster, impact hounds; portal failed twice | ? | L46 Priest | Read a summon scroll in a room | Don't read summon scrolls | [p2512] |

---

## Posts worth reading in full

- [p2470][p2471][p2472]: how ghosts are placed on death (a source quote), and Domino's ghost-keymap
  idea. Use these for the Pilot's ghost handler.
- [p2465]: the 30-second in-dungeon logout and why it exists.
- [p9379][p9384]: the stun mechanic and why FA and rSound don't help against GMMs.
- [p646]: Berendol's source-level formula for light/dark breath damage and resistance.
- [p5462][p5827]: teleport-to logic (lands you in vaults, ignores rNexus). Relevant to "after any
  teleport, re-assess".
- [p5216][p5261]: Ariel and confusion doctrine (CCW + staff), with grisu's critique.
- [p5386][p5391]: a duplicate-inscription death with the chardump (a Pilot test case).
- [p2473]: a mage's death to lag plus slot macros ("TRIED TO USE NON-STAFF OBJECT").
- [p2565]: Crimson's rule of one breather in line of sight.
- [p4676]: a level 50 warrior's death told step by step (re-engaging, wrong potion).
- [p2512]: idle levels fill with monsters; a rescue told step by step.
- [p5212][p5215]: chardump excerpts showing how deaths look in the message log (useful for the
  Pilot's death classifier).
- [p2433][p601][p605]: typical deaths on arrival by stairs or recall.

## Coverage

- **Topics read:** 142 of 142. Every line was read.
- **Skipped as irrelevant (drama, admin, spam or empty):** about 12. These are t=140 (a server-save
  glitch); t=153 (second half, audits); t=162, t=164 and t=166, the PK and hacking drama threads. I
  kept only the rules facts from them (town PK ban, ghost kills, bumping, audits, the 30 s logout,
  crash duplication). Also t=593, t=1232, t=1268, t=3711 and t=3718 (Russian spam from 2026), and the
  empty or pointer-only topics t=163, t=171, t=179, t=596, t=1199, t=1714 and t=1293.
- **Gaps:**
  - Many posts point to screenshots or HighScoreChart "scene of death" dumps that are not in the corpus
    (t=594, 595 [first post empty], 596 [empty], 601, 1189 [map only], 1200, 1222, 1227, 1288, 1293,
    1344, 1379, 1382, 2084, 2103). The causes of those deaths are partly unknown.
  - Pages 2+ of long threads (t=162, t=164, t=166) have no post ids; I cite them by their `&start=`
    page URL.
  - About a third of the deaths give no character level or class, and several give no depth (marked ?).
  - Only a handful of deaths are warrior-class or shallower than 1000 ft (rows 35, 46, 54, 56, 80, 101,
    NM1). There is little direct data for our throwaway's early game.
  - The MAngband version is almost never stated. Posts from 2002-2006 predate 1.x, and the 2008+ posts
    (PowerWyrm, Jug, "brave" characters, chardumps) are probably 1.1.x. Nothing refers to 1.5.
