# Distilled: MAngband forum "Strategy" subforum (42 topics, 2005-2014)

URLs have the form `https://www.mangband.org/forum/viewtopic.php?p=NNNN`. Posts in the big YASD thread
t=1249 have no post id, so they are cited by their page URL (`?t=1249&start=NN`).
Version context: most posts are from 2008-2009, when the server ran **1.1.1** ("In the current
instance (1.1.1)", https://www.mangband.org/forum/viewtopic.php?p=6322), with the 1.2 "time bubble" still
to come (https://www.mangband.org/forum/viewtopic.php?t=1249&start=45). We run 1.5.x, so anything
that depends on a bug or a server quirk is tagged [MAYBE-OUTDATED].
Main voices: PowerWyrm (developer and veteran, reads the death dumps), serina/Zal, Warrior (site admin), Ace, Ashi.

## Top findings

1. **Hounds (Z) near the arrival point are cleared only when you take a *down* staircase. Going up can
   drop you into a hound pack, which kills in one turn at depth.** PowerWyrm: "hounds are removed at
   stairs, but only when you go down"; "using < is like playing russian roulette at high level". The
   fix: recall a little shallower than your target depth and then only take `>`, or have *Destruction*
   ready when you take `<`. It is repeated from 2008 to 2013, with deaths to Nether, Chaos and Time hounds
   straight after "You enter a maze of up staircases". The 2013 post adds "due to a nasty bug... ALL the
   hounds will breathe at once."
   https://www.mangband.org/forum/viewtopic.php?p=6185 (2008), https://www.mangband.org/forum/viewtopic.php?t=1249&start=15 (2008),
   https://www.mangband.org/forum/viewtopic.php?t=1249&start=60 (2008), https://www.mangband.org/forum/viewtopic.php?p=8900 (2012),
   https://www.mangband.org/forum/viewtopic.php?p=8985 (2012), https://www.mangband.org/forum/viewtopic.php?p=9415 (2013), https://www.mangband.org/forum/viewtopic.php?p=6322 (2008).
   **[CONTRADICTS: HANDBOOK "go up and down until a `>` shows up". That is fine shallow, but below about 1500-2500 ft stair-scumming should be down-only]** [MAYBE-OUTDATED: whether 1.5 still clears hounds only on `>`; test it]. -> Navigator doctrine + Pilot rule (below a set depth, forbid `<` unless nothing else escapes; set the recall depth to max−100..200 ft).

2. **Cure Light/Serious Wounds is not a heal in a fight, and even CCW is mostly a status cure.** CCW
   heals about 27 HP (6d8) and CSW about 18. The single most common fatal mistake in the death thread
   is quaffing CCW or CSW while taking 100+ damage a turn: each potion costs a turn, so the character
   dies. The rule: quaff CCW to remove blind, confusion, poison or stun, or when that HP gain will
   actually outpace the incoming damage. Otherwise quaff Healing or end the fight (teleport or *Destruction*).
   https://www.mangband.org/forum/viewtopic.php?p=5240, https://www.mangband.org/forum/viewtopic.php?p=5242, https://www.mangband.org/forum/viewtopic.php?t=1249&start=30, https://www.mangband.org/forum/viewtopic.php?t=1249&start=45,
   https://www.mangband.org/forum/viewtopic.php?t=1249&start=60, https://www.mangband.org/forum/viewtopic.php?t=1249&start=75 (2008). [CONFIRMS + sharpens notes "CLW nearly useless"]. -> Pilot rule:
   the heal-vs-escape decision should compare the expected heal with the damage taken last turn. If the heal is smaller, escape.

3. **Resist blindness and confusion (or a staff of Teleportation) are what make escapes work.**
   Scrolls can't be read blind or confused, and spells fail. Warriors without rBlind/rConf should carry
   a *staff* of Teleportation (plus "a truckload of CCWs"). Amulets and rings of Teleportation are not
   an escape past 1000 ft. https://www.mangband.org/forum/viewtopic.php?p=8354 (2010), https://www.mangband.org/forum/viewtopic.php?p=9346 (2013),
   https://www.mangband.org/forum/viewtopic.php?p=5240, https://www.mangband.org/forum/viewtopic.php?p=5251 (2008). [CONFIRMS notes: staves usable blind/confused; NEW: amulet of teleport is not
   an escape; the explicit warrior staff doctrine]. -> Navigator shopping doctrine + Pilot escape selector
   (if blind or confused: staff, else scroll).

4. **Stun is progressive and deadly. Quaff CCW at the first "Stun" status.** Stunned gives −5 to-hit
   and to-dam and +15% spell fail. Heavy stun gives −20 and +25%. A stun counter over 100 means knocked out, the same as
   paralysis. Vibration hounds appear around 1350 ft. CCW removes all stun. Some attackers jump the
   counter more than one step at a time. Resist sound is a MUST below 2500 ft (plasma hounds).
   https://www.mangband.org/forum/viewtopic.php?p=6201 (2008), https://www.mangband.org/forum/viewtopic.php?p=9380 (2013),
   https://www.mangband.org/forum/viewtopic.php?t=1249&start=75 (PowerWyrm: "CCWs would have made a difference if quaffed at 'Stunned'"), https://www.mangband.org/forum/viewtopic.php?p=8985.
   [NEW]. -> Pilot rule: `stun` status → quaff CCW immediately. Navigator: add rSound to the depth checkpoints (by about 2500 ft).

5. **Free Action at 1000 ft is not strictly needed; 1250 ft is the hard line.** The first dangerous
   paralyzers are ogre mages and carrion crawlers at 1250 ft. Earlier hold sources: homunculi at about 750-800 ft,
   floating eyes, and druids and illusionists at 650 ft. The same thread also has "don't pass 1000 ft without FA
   and lows" (Ace). https://www.mangband.org/forum/viewtopic.php?t=1249&start=15 (2008). [CONTRADICTS mildly: notes say FA+SI by 1000 ft;
   it is a safety margin, fine to keep]. Later the ghoul death (level 27, no FA) and Ungoliant (no FA) show FA is a must by the time ghouls and undead appear.
   -> Navigator doctrine (keep 1000 ft as the conservative cap).

6. **Resistance and HP checkpoints below 2000 ft:** rBase (acid, elec, fire, cold) plus rPoison, rBlind, rConf,
   and CON 18/200 before diving below 2000 ft; get rSound and rDisenchant if possible. "Going under 2000ft without resist
   poison is suicidal". Diving below 2000 ft with under 400 HP is suicidal "even if you resist everything". CON
   beats speed rings mid-game ("remove those rings of speed and use rings of con").
   https://www.mangband.org/forum/viewtopic.php?p=9346, https://www.mangband.org/forum/viewtopic.php?p=9345 (2013), https://www.mangband.org/forum/viewtopic.php?t=1249&start=30 (2008),
   https://www.mangband.org/forum/viewtopic.php?p=8351 (2010). [CONFIRMS notes' poison at 2000 ft; NEW: HP floor ~400 at 2000 ft and
   CON-over-speed]. -> Navigator depth cap = f(resists, max HP).

7. **Never fight summoners in the open. Hound summoners especially (Carcharoth, Draugluin, Dwar),
   Q (quylthulgs, invisible so they need Detect Invisible), high-level p casters, gnome mages at depth,
   and mystics (summon animals).** Build or use a 1-wide "anti-summon corridor" so summons have
   no room to appear. Summoners are poor XP for their risk. https://www.mangband.org/forum/viewtopic.php?p=5700 (2008),
   https://www.mangband.org/forum/viewtopic.php?p=6529 (2009), https://www.mangband.org/forum/viewtopic.php?p=8569 (2010), https://www.mangband.org/forum/viewtopic.php?p=8900 (2012), https://www.mangband.org/forum/viewtopic.php?p=5663,
   https://www.mangband.org/forum/viewtopic.php?p=6639, https://www.mangband.org/forum/viewtopic.php?p=7218. [CONFIRMS HANDBOOK "summoners are the real killers"; NEW: the
   corridor geometry and the named summoner list]. -> Pilot rule: on "magically summons", escape or leave the level.

8. **Always know what an unknown monster does before engaging (look it up with the monster recall
   `/` or `l`).** Deaths come from mistaking Gorlim for a ranger, Sauron for Lorgan, Huan for Maggot's
   dogs, or a Time hound (blue Z) at 850 ft for something harmless. https://www.mangband.org/forum/viewtopic.php?p=5257,
   https://www.mangband.org/forum/viewtopic.php?t=1249&start=15, https://www.mangband.org/forum/viewtopic.php?t=1249&start=60, https://www.mangband.org/forum/viewtopic.php?p=6540, https://www.mangband.org/forum/viewtopic.php?p=6543 (2008-09). [NEW].
   -> Pilot: keep a monster-danger table keyed by exact race name; an unknown name → treat as dangerous.

9. **Out-of-depth vaults start at about 250 ft and can hold monsters 40 levels out of depth.** "Special"
   level feelings and odd layouts mean a possible vault. Detect monsters and invisible, map the sector (Magic Mapping), or
   simply leave. Warrior: "don't play special levels". The *Backdoor Surprise* vault and Zoos
   (Concentrated Death) are killers. https://www.mangband.org/forum/viewtopic.php?p=6540, https://www.mangband.org/forum/viewtopic.php?p=6537, https://www.mangband.org/forum/viewtopic.php?p=6541,
   https://www.mangband.org/forum/viewtopic.php?p=6545 (2009). [CONTRADICTS partly: HANDBOOK "stop for a possible vault". For a throwaway
   warrior without detection, a "special" feeling is a reason to leave, not to explore]. -> Navigator doctrine.

10. **Level feelings, shallow: "good/very good/excellent" → explore the whole level (sometimes a great
    item). "Special" → "99% of the time a jelly pit"; don't waste time.** https://www.mangband.org/forum/viewtopic.php?p=6847 (2009).
    [NEW detail]. -> Navigator doctrine.

11. **Aggravation items (weapons of *Fury*, Gloves of Combat, Calris, Zarcuthra) wake everything.
    Swap them off before taking stairs or recalling.** "Recalling or taking stairs with aggravation is simply
    suicidal." https://www.mangband.org/forum/viewtopic.php?p=5259 (2008), https://www.mangband.org/forum/viewtopic.php?t=1249&start=90, https://www.mangband.org/forum/viewtopic.php?p=6540 (2009), https://www.mangband.org/forum/viewtopic.php?p=9126.
    [NEW]. -> Pilot rule: never wield an item whose name matches *Fury* or known aggravators. Navigator: don't buy them.

12. **Breath damage scales with the monster's current HP, but spells don't.** Wound a breather (or melee it: "Monsters
    in melee range tend to use spells less") to shrink its breath. Casters like Gorlim, Sauron and Morgoth
    cast 500+ damage even at 1 HP and while fleeing. https://www.mangband.org/forum/viewtopic.php?p=5306 (2008),
    https://www.mangband.org/forum/viewtopic.php?p=6788 (2009). [NEW]. -> HANDBOOK text; the Pilot shouldn't assume a fleeing caster is safe.

13. **Line-of-sight doctrine: stand where you see the corridor mouth, not where the room sees you. Never
    stand in the open against breathers.** Wait behind a corner and fight at the corner. With a pack
    (Time hounds), be in LOS of only one at a time. https://www.mangband.org/forum/viewtopic.php?p=5974 (2008), https://www.mangband.org/forum/viewtopic.php?p=8900,
    https://www.mangband.org/forum/viewtopic.php?p=8901 (2012), https://www.mangband.org/forum/viewtopic.php?p=6490, https://www.mangband.org/forum/viewtopic.php?t=1249&start=60 (the Greater Balrog ASCII). [CONFIRMS `choke` order; NEW LOS detail].
    -> Pilot (choke-point selection should minimise the number of hostiles in LOS).

14. **Light and AFK: "NEVER stay afk in town outside of the tavern if you don't have infravision or a
    permalight."** A level 33 mage with an empty lantern died to a Battle-scarred veteran, and a midlevel
    char to a scrawny cat. Carry spare fuel. https://www.mangband.org/forum/viewtopic.php?p=5307 (2008), https://www.mangband.org/forum/viewtopic.php?t=1249&start=30,
    https://www.mangband.org/forum/viewtopic.php?p=9416 (2013). [NEW; Half-Orc has 30 ft infravision, which helps but isn't a light]. -> Pilot rule: while idle in
    town, stand inside a shop or tavern (or log out); keep lantern turns above a threshold and refuel.

15. **The panic button must be a single one-turn action that is guaranteed to work.** Deaths from pressing
    the wrong macro (Speed or Restore Life Levels instead of heal or teleport). Don't give the heals and
    CCW the same inscription. Don't re-map macros mid-game. Rely on low-fail items (scroll or staff)
    over spells or amulets. https://www.mangband.org/forum/viewtopic.php?p=5240, https://www.mangband.org/forum/viewtopic.php?p=5294, https://www.mangband.org/forum/viewtopic.php?p=5295, https://www.mangband.org/forum/viewtopic.php?p=5305,
    https://www.mangband.org/forum/viewtopic.php?p=6627 (2008-09). [NEW for the Pilot: separate tags for Healing (@q2) and CCW (@q1); failure
    rates matter (staff "You failed to use the staff properly" deaths)]. -> Pilot: escape chain with
    fallback on failure (try again next turn, or switch item).

16. **Undead beholders drain mana and charges; Omarax drains charges from *Destruction* staves.**
    Only potions and *scrolls* are guaranteed to work. https://www.mangband.org/forum/viewtopic.php?t=1249&start=75, https://www.mangband.org/forum/viewtopic.php?t=1249&start=30 (2008). [NEW]. ->
    Pilot: keep a scroll-based escape even if you own a staff.

17. **Messages taken as data:** "commands you to return" = teleport-to (quylthulg, druj). "magically summons" =
    summon. "stares deep into your eyes" = paralyze. "creates a mesmerising illusion" = confuse. "casts a spell,
    burning your eyes" = blind. "concentrates on his body" = haste-self. "gestures at your feet" =
    teleport-level. "points at you, screaming the word DIE!" = mortal wounds. "invokes a mana storm". Full
    list in https://www.mangband.org/forum/viewtopic.php?p=7256 (2009). [NEW]. -> Pilot message classifier.

18. **Warrior survival kit at 1000 ft and below (Zal):** Speed potions, 10-20 Heroism (cures fear), 20-60 CSW/CCW, all
    the Healing you can get, 20+ Phase Door, 5-20 Teleportation (add *Destruction* scrolls and staff by 1800 ft),
    5 Word of Recall, 20-40 Magic Mapping, 20-40 Detect Invisible, wands of Teleport Other and Stone to Mud, and food
    (speed items make you hungry). Warrior (admin) carries about 45 CCW and about 25 of the others. https://www.mangband.org/forum/viewtopic.php?p=6011,
    https://www.mangband.org/forum/viewtopic.php?p=6013 (2008), https://www.mangband.org/forum/viewtopic.php?p=6537 (2009). [NEW; CONTRADICTS the HANDBOOK "~1 spare ration" only once speed items appear]. -> Navigator
    shopping list per depth band.

## Findings by theme

### Stairs, diving pace, recall
- Hound removal on `>` only; up-stairs gamble; recall to max depth −100..200 ft (inscribe WoR, e.g. `{1300}` / `@R1800`)
  and go down only. https://www.mangband.org/forum/viewtopic.php?p=6185, https://www.mangband.org/forum/viewtopic.php?p=9415, https://www.mangband.org/forum/viewtopic.php?t=1249&start=15, https://www.mangband.org/forum/viewtopic.php?t=1249&start=75 (WoR inscribed `{1300}`). [CONTRADICTS HANDBOOK up/down scumming at depth; CONFIRMS @R depth].
- "NEVER go up stairs below 2550ft without the finger on the *des* macro." https://www.mangband.org/forum/viewtopic.php?p=8900 (2012).
- Mage-specific but general: "Don't scum for levels... just set your depth at a shallower level and go down: going up is
  likely to kill you instantly if there's a pack of hounds or such pushing you from stairs." https://www.mangband.org/forum/viewtopic.php?p=6322 (2008).
- Arriving next to an undead pit or graveyard gives "exactly one turn to react before reavers start to open the pit";
  *Destroy* is best. https://www.mangband.org/forum/viewtopic.php?t=1249&start=90 (2008).
- Diving too fast for your level ("3000ft at clvl 40", "clvl 6 at 900 ft") is the pattern behind many deaths;
  PowerWyrm prefers not to push depth without resists. https://www.mangband.org/forum/viewtopic.php?t=1249&start=15. Ironman guide:
  warriors can reach 200-300 ft at clvl 3-4. https://www.mangband.org/forum/viewtopic.php?p=6080 (2005/2008). Ashi: "players that know what
  they are doing can dive a warrior to 500ft and gain the first 10-15 levels with minimal effort." https://www.mangband.org/forum/viewtopic.php?p=5580 (2008). [NEW pace data point].
- Caster depth table (a pace reference for the level and depth ratio): clvl <10 at ≤250 ft; 10s at 500-1000 ft; 20s at
  1000-1500 ft; clvl 35 at 2000 ft; clvl 42 at 2500 ft; 3000 ft and deeper for high levels. https://www.mangband.org/forum/viewtopic.php?p=6322 (2008).
  Zal's newbie mage/priest bands: clvl 1 at 50-150 ft, clvl 2-5 at 150-300 ft, clvl 6-9 at 300-800 ft. https://www.mangband.org/forum/viewtopic.php?p=5597.
- Zal (mage): "I never explore a level fully, because I don't want it spawning... 3-5 screens tops, then >." https://www.mangband.org/forum/viewtopic.php?p=9407 (2013). [CONFIRMS the stair-scum approach].
- Logging out deep is a gamble: hounds are removed on recall or stairs down but "not if you log in". https://www.mangband.org/forum/viewtopic.php?p=7127 (2009) [MAYBE-OUTDATED].
- "Most loot worth bringing up for cash is found at 800 ft and beyond." https://www.mangband.org/forum/viewtopic.php?p=6842 (2009, Ironman).

### Escapes and healing doctrine
- Warrior's basic rule: carry (1) a heal that actually outpaces the damage, and (2) an escape; "A huge percentage of the YASD's
  is a result of failing to understand this." If one hit takes half your HP, get away (scroll or staff). https://www.mangband.org/forum/viewtopic.php?p=6524 (2009).
- Teleport can land you in worse trouble (hounds to hounds, next to a death mold). *Destruction* is safer when you have it
  ("If you have the choice, always *destroy*"). Word of Destruction beats a Teleport scroll. https://www.mangband.org/forum/viewtopic.php?t=1249&start=15 (Ace),
  https://www.mangband.org/forum/viewtopic.php?p=6510, https://www.mangband.org/forum/viewtopic.php?t=1249&start=90, https://www.mangband.org/forum/viewtopic.php?t=1249&start=45. [NEW: *Destruction* ranked above Teleport].
- Phase Door-only escape at 2000 ft is "really brave" (death). Below 1000 ft you need at least one teleport (spell, staff, scrolls). https://www.mangband.org/forum/viewtopic.php?t=1249&start=45, https://www.mangband.org/forum/viewtopic.php?t=1249&start=15.
- Teleport amulets and rings: acceptable shallow (<1000 ft) for new players, not deeper. https://www.mangband.org/forum/viewtopic.php?p=5251.
- Fire and cold attacks burn scrolls, staves and potions: teleport staves and *Destruction* scrolls get destroyed mid-fight. Carry backups.
  https://www.mangband.org/forum/viewtopic.php?p=5496, https://www.mangband.org/forum/viewtopic.php?p=6514, https://www.mangband.org/forum/viewtopic.php?t=1249&start=45 (Vargo burning Phase Door). [NEW]. Immunity or double resist also "reduces potions breaking". https://www.mangband.org/forum/viewtopic.php?p=5729.
- Heals vs *heals*: with 300 HP heals losing against big melee, either *Healing* between heals or end the fight. https://www.mangband.org/forum/viewtopic.php?t=1249&start=15.
- Warrior using CSW at clvl 31 is "totally stupid": CCW for effects, Healing for damage. https://www.mangband.org/forum/viewtopic.php?t=1249&start=30.
- Quakes (Quaker) do up to 300 damage: keep HP ≥ 300 against earthquake monsters. https://www.mangband.org/forum/viewtopic.php?t=1249&start=75.
- Mixed-status macro: "ccw (in case blind) then teleport" still failed, because he went blind again right after the CCW. rBlind is the real fix. https://www.mangband.org/forum/viewtopic.php?t=1249&start=90.
- Heroism potions cure fear (and give to-hit). https://www.mangband.org/forum/viewtopic.php?p=6011. [NEW for warriors: fear blocks melee, and auto-retaliate needs "not afraid" per notes].
- Jug: Phase Door plus a couple of CCW (for confusion) is enough escape through the early and mid levels. https://www.mangband.org/forum/viewtopic.php?p=5504.

### Dangerous monsters and situations (with depths)
- Early (0-300 ft): novice p's of every colour (brown warrior, blue rogue, green priest, white paladin; "8 heroes killed by a Novice paladin" even at high level),
  Fang and Grip (orange C), crows and ravens (B), Brown mold (confuses), Kobold archer, Kobold shaman, Cave spider swarms, Mughash ("2-3 k at
  the same spot"), Snagas and Cave orcs in packs. https://www.mangband.org/forum/viewtopic.php?p=5597, https://www.mangband.org/forum/viewtopic.php?p=5700 (2008).
- 300-800 ft: Wood spiders, Nighthawk, any orc pack, Yeti, all cats (f) "hit HARD", dark elven priest and mage (confuse),
  Z packs (fight at a corner), Stegocentipede and Ochre jelly ("moves faster than you do. TELEPORT!"). https://www.mangband.org/forum/viewtopic.php?p=5597.
- Top killers per the 2008 monster highscore: Air hound 30, Vibration 16, Gorlim 14, Time 13, Inertia 10, Earth 9, Gravity 8, Cold 8,
  poison 10. https://www.mangband.org/forum/viewtopic.php?p=5700 (2008). Emulord 2009: high levels die mostly to hounds and Gorlim. https://www.mangband.org/forum/viewtopic.php?p=6786.
- Time hounds: +20 speed, drain stats and XP; "If you can't kill them in melee in one round, it's not even worth bothering". Leave,
  or *Destroy*. Deeper than 2500 ft, run BEFORE they see you. Found OOD at 850 ft (vault). https://www.mangband.org/forum/viewtopic.php?t=1249&start=15, https://www.mangband.org/forum/viewtopic.php?p=8900, https://www.mangband.org/forum/viewtopic.php?p=6540.
- Gravity hounds: the gravity effect can apply several times per breath (ticket 651), "the most lethal of all breaths"; avoid at all
  cost. Kavlax likewise. https://www.mangband.org/forum/viewtopic.php?t=1249&start=75 (2008) [MAYBE-OUTDATED bug]. Gravity hounds are likely below 1500 ft;
  time vortexes just below 2000 ft. https://www.mangband.org/forum/viewtopic.php?p=7114.
- Nests (zoos, undead nests) are almost instant death: kill-wall monsters (Umber hulks, Black reavers) open them, and teleport-to monsters
  (quylthulgs, drujs) pull you in. Avoid "unless you know exactly what you are doing". https://www.mangband.org/forum/viewtopic.php?t=1249&start=45, https://www.mangband.org/forum/viewtopic.php?p=6645, https://www.mangband.org/forum/viewtopic.php?p=6786.
- Drujs (Eye, Skull, Hand) are stationary casters: never stand in their LOS. https://www.mangband.org/forum/viewtopic.php?p=6789, https://www.mangband.org/forum/viewtopic.php?p=5974.
- Gorlim (black or grey p): 14 kills; casts water bolts (stun and confuse) and mana bolts; "Don't think it's just an easy black knight". https://www.mangband.org/forum/viewtopic.php?p=5700.
- Mystics (Master and Grand Master): 15d1 and 20d1 kicks almost always crit, causing an unresistable melee stun lock. Avoid them. They also summon animals, which can mean hounds. https://www.mangband.org/forum/viewtopic.php?p=9380, https://www.mangband.org/forum/viewtopic.php?p=8900.
- Black reaver mana storm up to 600 damage, unresistable; dracolich nether 600 (514 resisted); great hell wyrm fire 533 with single resist. https://www.mangband.org/forum/viewtopic.php?p=5258.
- Gnome mage at 6350 ft can summon a pack of Aether hounds (the summon level depends on depth). https://www.mangband.org/forum/viewtopic.php?p=6639 (2009).
- Invisible and cold-blooded packs (Dreads) below 1500 ft: See Invisible is needed if you have no ESP. https://www.mangband.org/forum/viewtopic.php?t=1249&start=15.
- Mimics at the bottom. https://www.mangband.org/forum/viewtopic.php?p=6644.
- Phoenix (beefed up in 2008 with summon_kin: Winged Horrors, Crebain). https://www.mangband.org/forum/viewtopic.php?t=1249&start=30.
- Molds and jellies: avoid when there are several (poison and mind-drain death among molds). https://www.mangband.org/forum/viewtopic.php?p=6482. [CONFIRMS HANDBOOK]. Death mold next to a teleport landing spot. https://www.mangband.org/forum/viewtopic.php?t=1249&start=45.
- Traps: "You fell into a pit! You die." (level 27 paladin at low HP); "always detect traps every time you change sector". https://www.mangband.org/forum/viewtopic.php?t=1249&start=60, https://www.mangband.org/forum/viewtopic.php?p=9221 (2013). [NEW].
- Two uniques at once (Maeglin plus Phoenix, Sauron plus Saruman) = death. https://www.mangband.org/forum/viewtopic.php?p=6483, https://www.mangband.org/forum/viewtopic.php?t=1249&start=45, https://www.mangband.org/forum/viewtopic.php?t=1249&start=75.

### Resistances, stats, equipment
- The resist mechanics table (serina 2013): basic elements do HP/3, capped at 1600 (1/3 with resist, 1/9 with double resist). Poison HP/3, capped at 800.
  Sound, shards and dark are capped at 400. Nether 550, chaos 600, force, inertia and gravity 200 (unresistable damage). Time 150. Plasma 150. https://www.mangband.org/forum/viewtopic.php?p=9345.
- Resists don't stack across two items. One permanent source plus one temporary (potion or spell) = double resist. https://www.mangband.org/forum/viewtopic.php?p=5729, https://www.mangband.org/forum/viewtopic.php?p=5733.
- High resists matter mainly for their side effects: rBlind and rConf are MUST (for escapes), rSound MUST (knockout), rNexus (stat scramble),
  rChaos and rNether are pointless with Hold Life, rShards pointless (CSW fixes cuts), light and dark pointless with rBlind. https://www.mangband.org/forum/viewtopic.php?p=9346.
- Sources of the lows: any item "of Resistance", weapon (Defender), armour or shield of Elvenkind, Robe of Permanence, Crown of the Magi, Shield of
  the Avari. rConf: Amulet of the Magi, Bronze DSM, Crown of Serenity, random high resists (Elvenkind, Permanence, Avari, Istari gloves,
  Cloak of Aman, which need *Identify*). https://www.mangband.org/forum/viewtopic.php?p=5719, https://www.mangband.org/forum/viewtopic.php?p=5738. Boots of Mirkwood give rPoison. https://www.mangband.org/forum/viewtopic.php?t=1249&start=30.
- "It might have hidden powers" on `I` means *Identify* is needed. *Identify* scrolls come from the BM (7), the dungeon and player shops only. *ID* also protects against
  memory-drain forgetting. https://www.mangband.org/forum/viewtopic.php?p=5727, https://www.mangband.org/forum/viewtopic.php?p=5733, https://www.mangband.org/forum/viewtopic.php?p=5737.
- CON: HP rises steeply up to 18/200 (18/180 vs 18/200 = 2.5 HP per level). At clvl 50 with max CON, race and class hit dice matter little (warrior +225
  over mage). Stat caps from potions are 18/100 ± the race and class modifier. https://www.mangband.org/forum/viewtopic.php?p=9345, https://www.mangband.org/forum/viewtopic.php?p=8079 (2010).
- Blows: "1bpr with a melee character is pure suicide"; "A simple dagger +9 +9 would be much better than the heavy halberd". Whip is a better start
  weapon than a dagger (rob, Ironman). {good} heavy weapons are not necessarily better than a multi-blow light one. https://www.mangband.org/forum/viewtopic.php?t=1249&start=15,
  https://www.mangband.org/forum/viewtopic.php?p=5259, https://www.mangband.org/forum/viewtopic.php?p=6081, https://www.mangband.org/forum/viewtopic.php?p=6080. [CONFIRMS light-weapon/blows build].
- To-hit matters vs big uniques (missing 14 of 19 swings). https://www.mangband.org/forum/viewtopic.php?t=1249&start=60.
- "Don't overload your character with goodies until you feel confident": mid-game, HP and mana matter more than speed. https://www.mangband.org/forum/viewtopic.php?p=8351.
- Warriors have the best pseudo-ID. {average} gear → drop. {excellent} is usually worth using. https://www.mangband.org/forum/viewtopic.php?p=5580, https://www.mangband.org/forum/viewtopic.php?p=6080. [CONFIRMS].
- Throw away cursed junk immediately (a cursed Ring of Protection). https://www.mangband.org/forum/viewtopic.php?p=6482.

### Money, shops, items
- Shop and BM notes: Detect Invisible and Magic Mapping scrolls are in shop 5 (alchemist). https://www.mangband.org/forum/viewtopic.php?p=5700. Protection from Evil scrolls
  "worth buying no matter which class" (they stack in duration). https://www.mangband.org/forum/viewtopic.php?p=7219. Potions of Speed and Heroism durations stack; extra speed potions add ~10 turns each. https://www.mangband.org/forum/viewtopic.php?p=7217, https://www.mangband.org/forum/viewtopic.php?p=7218.
- Staves of Teleportation are a mid-game investment once past 1000 ft. https://www.mangband.org/forum/viewtopic.php?p=5251.
- Mining ore is not worth it; tunnelling is for tactics. Wands of Stone to Mud with Recharging replace diggers. https://www.mangband.org/forum/viewtopic.php?p=5658.
- Town shops "reset regularly, every few minutes" and can be scummed for discounts (Ironman server, 2005). https://www.mangband.org/forum/viewtopic.php?p=6081 [MAYBE-OUTDATED; notes say 1000 game turns].
- Good-citizen norm: camping inside a shop for hours to snipe an item was called out as against the spirit of a multiplayer game. https://www.mangband.org/forum/viewtopic.php?p=7155 (2009). [NEW; relevant if the Pilot idles in shops].
- Unknown-item trial doctrine (Ironman, no ID): read unknown scrolls standing on `>` on a cleared level, weapon and armour removed (curse). Try wands and staves
  on a mold from a staircase. Rods are never harmful. Don't put on unknown rings or amulets (Teleportation, Aggravate, Woe). Inscribe potions with their depth. https://www.mangband.org/forum/viewtopic.php?p=6080 [NEW].

### MAngband-specific (multiplayer, real time)
- Real time: "time passes, even when you are sensing creatures". Don't stand outside a room reading the screen. https://www.mangband.org/forum/viewtopic.php?p=5962 (2008).
  Deaths while reading the monster spoiler in a browser. https://www.mangband.org/forum/viewtopic.php?p=6795, https://www.mangband.org/forum/viewtopic.php?p=6797. -> For the Pilot: Navigator latency must not
  stall reactions; the Pilot needs to handle threats on its own.
- Windows client: typing in chat steals keyboard focus, so macros don't fire (death). https://www.mangband.org/forum/viewtopic.php?p=6792 (2009) [MAYBE-OUTDATED; irrelevant to a packet client, but it confirms the no-chat rule].
- A pending prompt ("what potion do you want to quaff?" when you're out) eats the next keypress. Always ESC first. https://www.mangband.org/forum/viewtopic.php?p=6793, https://www.mangband.org/forum/viewtopic.php?p=6794. [CONFIRMS notes "\e first"]. Casting without mana possibly costs energy (unverified question). https://www.mangband.org/forum/viewtopic.php?t=1249&start=75.
- Ghosts: ghost spells (Blink at 1, Teleport at 20, Nether bolt at 25...) cost spell level × mana in XP. If XP would go negative you take 5000 damage (a killed ghost is permanent).
  Ghosts in walls can be killed by pass-wall monsters. Players float up or down (to town) after dying, and "Starting from level 20, players should macro
  Teleport from the undead set of spells." https://www.mangband.org/forum/viewtopic.php?p=6329, https://www.mangband.org/forum/viewtopic.php?p=6343 (2008) [NEW; MAYBE-OUTDATED].
- Dying in a room rather than a corridor lets rescuers recover more items. "I don't think you will get more than 2 items back when you die in such spot". https://www.mangband.org/forum/viewtopic.php?p=8351, https://www.mangband.org/forum/viewtopic.php?p=6502.
- Rescuers die too: "be sure everything is completely safe before doing a rescue". https://www.mangband.org/forum/viewtopic.php?p=6530.
- Teleport Other near other players can send the monster onto them. https://www.mangband.org/forum/viewtopic.php?p=6486. [good-citizen note].
- Newbie advice (2005): town is more dangerous than DL1; the light-blue `t` (Battle-scarred veteran) is deadly for low levels; if you die at low level, suicide (ctrl-K) and restart; running is not possible with a monster in view.
  https://www.mangband.org/forum/viewtopic.php?p=3313 (2005) [CONFIRMS user correction on town; MAYBE-OUTDATED].
- Uniques were once globally killed and respawned periodically (Wormtongue and Bullroarer farmed daily). https://www.mangband.org/forum/viewtopic.php?p=7104 (2009) [MAYBE-OUTDATED].
- Ironman server: towns every 1000 ft; different starting kit (warrior: 5 CSW plus 10 Teleportation). https://www.mangband.org/forum/viewtopic.php?p=6080, https://www.mangband.org/forum/viewtopic.php?p=6084 [not our server].
- Race death counts (2008): Half-Orc 69 deaths vs Dwarf 486 (a popularity artefact, not a signal). https://www.mangband.org/forum/viewtopic.php?p=5323.

### UI and automation
- Standard macro and inscription set: `@f1` ammo `\ef1*t`, `@q1` heal, `@r1` Phase Door; a "super panic" chain `\eq1\eq2\er1\eu1` relies on ESC to skip a missing item. https://www.mangband.org/forum/viewtopic.php?p=3313, https://www.mangband.org/forum/viewtopic.php?p=5162. [CONFIRMS notes].
- Keep weak-heal and strong-heal on separate keys. The panic key should always work, even while confused (a staff or *Destruction*). https://www.mangband.org/forum/viewtopic.php?p=6627.
- Protective inscriptions seen in dumps: `!d!k!v!s!t` on worn gear; `@w0`/`@w2` weapon swaps. https://www.mangband.org/forum/viewtopic.php?t=1249&start=60, https://www.mangband.org/forum/viewtopic.php?p=8569.
- Swap items (`@w`) are used to drop an aggravating weapon before stairs. https://www.mangband.org/forum/viewtopic.php?p=6540.
- "Monster list" (the visible-monster window) should be checked for unknown letters before engaging. https://www.mangband.org/forum/viewtopic.php?p=5257, https://www.mangband.org/forum/viewtopic.php?p=6533.
- Party chat: first letters of the party name then `:`. Friendly targeting is `(`. https://www.mangband.org/forum/viewtopic.php?p=5598, https://www.mangband.org/forum/viewtopic.php?p=5582 (not needed; solo, no chat).
- Stone to Mud a wall to extend the view before walking down an unseen corridor (the ESP and detect radius are limited to the screen). https://www.mangband.org/forum/viewtopic.php?p=7218.
- Scene-of-death shape: dying behind doors in a corridor means rescuers get fewer items back. https://www.mangband.org/forum/viewtopic.php?p=8351.

### Things that do NOT work / common mistakes
- Arrows or missiles against summoned packs (rangers and mages at low levels). https://www.mangband.org/forum/viewtopic.php?t=1249&start=60.
- Digging to escape Time hounds. https://www.mangband.org/forum/viewtopic.php?t=1249&start=15. Tunnelling to escape a surround at low level is too slow. https://www.mangband.org/forum/viewtopic.php?p=5664.
- Walking away from a fast hound instead of teleporting. https://www.mangband.org/forum/viewtopic.php?p=6542.
- Drinking Speed, or other buffs, when the situation calls for escape. https://www.mangband.org/forum/viewtopic.php?t=1249&start=90, https://www.mangband.org/forum/viewtopic.php?p=5294.
- Uninscribed escape items (a teleport staff not inscribed). https://www.mangband.org/forum/viewtopic.php?p=7915, https://www.mangband.org/forum/viewtopic.php?t=1249&start=30.
- Rings of Damage on a ranger or mage, Rings of Speed instead of CON when HP is low, an Amulet of Infravision (−3). https://www.mangband.org/forum/viewtopic.php?t=1249&start=60, https://www.mangband.org/forum/viewtopic.php?p=8355.

## Death catalogue

| Cause / monster | Depth | Char (lvl/class) | Mistake | Lesson | URL |
|---|---|---|---|---|---|
| Ancient MHD fire breath | deep | L31 Rogue | CCW spam vs 233-damage breaths; no double resist; heals and CCW on the same `@q1`; relied on an Amulet of Teleportation | Double-resist base breathers; separate the heal key; leave the fight | https://www.mangband.org/forum/viewtopic.php?p=5240 |
| Air hounds (gas) | ~1000 ft+ | ? | Quaffed CCW (27 HP) vs a pack breathing 200+ | Escape, don't CCW-heal vs packs | https://www.mangband.org/forum/viewtopic.php?p=5242 |
| Vampire lord + Eye druj (nether) | vault | ? | Attacked an unknown monster; fought a summoner in the open | Check the monster list; tunnel to a corridor or skip it | https://www.mangband.org/forum/viewtopic.php?p=5257 |
| Black reaver mana storm | deep | ? (300 HP) | Engaged with too few HP | Max HP vs worst-case damage (600) | https://www.mangband.org/forum/viewtopic.php?p=5258 |
| Vibration hounds (after teleport) | ~1350 ft+ | ? | Wielded an aggravating Halberd of Fury | Avoid aggravation | https://www.mangband.org/forum/viewtopic.php?p=5259 |
| Night mare + Elder vampire | deep | ? | Pressed the Speed macro instead of heal or teleport | One reliable panic key | https://www.mangband.org/forum/viewtopic.php?p=5294 |
| The Cat Lord (summons) | ? | ? | Drank Restore Life Levels mid-fight | Macro hygiene | https://www.mangband.org/forum/viewtopic.php?p=5295 |
| Impact hounds (force) | ? | ? | No rSound; ignored stun | Quaff CCW at "Stun" | https://www.mangband.org/forum/viewtopic.php?p=5296 |
| Dracolich nether | deep | ? | Waited in a room corner for it | Break LOS, wound it, then melee | https://www.mangband.org/forum/viewtopic.php?p=5306 |
| Battle-scarred veteran (town) | town | L33 Dunadan Mage | AFK in town, lantern at 0 turns | Stay in the tavern or keep light | https://www.mangband.org/forum/viewtopic.php?p=5307 |
| Huan (shards, sound) | very deep | high | No rShards or rSound; mistook it for Maggot's dog | Check the monster; resist gate | https://www.mangband.org/forum/viewtopic.php?p=5334 |
| Time hounds after `<` | deep | ? | Took an up staircase deep | `>` only deep | https://www.mangband.org/forum/viewtopic.php?t=1249&start=15 |
| Time hounds | deep | ? | Tried to dig away | Destroy or leave | https://www.mangband.org/forum/viewtopic.php?t=1249&start=15 |
| Invisible caster (Dread-type) | <1500 ft | Priest | No See Invisible or ESP | SI below 1500 ft | https://www.mangband.org/forum/viewtopic.php?t=1249&start=15 |
| Great Wyrm of Chaos | 4850 ft | L45 | Diving deep without rChaos/rConf | Resist gate | https://www.mangband.org/forum/viewtopic.php?t=1249&start=15 |
| Carcharoth | deep | ? | Panicked, walked into a wall while quaffing heals | *Heal* or end the fight | https://www.mangband.org/forum/viewtopic.php?t=1249&start=15 |
| Pit Fiend | >4000 ft? | L50 HE Mage | Aggravating weapon; no rNether/rSound; CCW at clvl 50 | Heals, not CCW, late | https://www.mangband.org/forum/viewtopic.php?t=1249&start=15 |
| Shagrat + escort | ~1000 ft+ | L27 Rogue | 1 blow/round; no teleport; books not macroed | ≥1 teleport below 1000 ft | https://www.mangband.org/forum/viewtopic.php?t=1249&start=15 |
| Nexus vortex after teleport | ? | ? | Teleported into worse | Prefer *Destruction* | https://www.mangband.org/forum/viewtopic.php?t=1249&start=15 |
| Eye druj bolts | ? | ? | Stood in druj LOS meleeing a hound | Leave druj LOS | https://www.mangband.org/forum/viewtopic.php?t=1249&start=30 |
| Great Wyrm of Perplexity | deep | L49 HE Mage | No rConf, rNether or rBlind; low CON | rConf at depth | https://www.mangband.org/forum/viewtopic.php?t=1249&start=30 |
| Ungoliant (blind) | deep | L49 Mage | No rBlind | rBlind; carry heals | https://www.mangband.org/forum/viewtopic.php?t=1249&start=30 |
| Phoenix + Ar-Pharazon summons | deep | L45 Priest | Failed staff use; fought summoners in the open | Anti-summon corridor | https://www.mangband.org/forum/viewtopic.php?t=1249&start=30 |
| Vrock/Bodak/Black knight crowd | mid | L31 Warrior | Quaffed CSW (18 HP) vs 100+/turn | CCW for status, Healing for HP | https://www.mangband.org/forum/viewtopic.php?t=1249&start=30 |
| GW of Many Colours gas | >2000 ft | ? | No rPoison | rPoison by 2000 ft | https://www.mangband.org/forum/viewtopic.php?t=1249&start=30 |
| Ghast + mummies (paralysis) | ~1250 ft+ | L27 | No Free Action (despite great gear) | FA | https://www.mangband.org/forum/viewtopic.php?t=1249&start=30 |
| Glaurung fire | deep | L39 Paladin | Fought in the open, no resist spell | Double resist; don't | https://www.mangband.org/forum/viewtopic.php?t=1249&start=30 |
| Lernaean Hydra poison | deep | ? | No rPoison (had +20 speed) | Swap a speed item for Mirkwood boots | https://www.mangband.org/forum/viewtopic.php?t=1249&start=30 |
| Inertia hounds | mid | ? | Stayed in LOS of the pack, CCW | Corner, one hound in LOS | https://www.mangband.org/forum/viewtopic.php?t=1249&start=30 |
| Young MHD lightning | ~? | Mage (serina) | Teleport Other failed 4× (30% fail); dove with no resists | Use low-fail escapes | https://www.mangband.org/forum/viewtopic.php?t=1249&start=45 |
| Zoo (quylthulgs, chaos hounds) | deep | ? | Teleported into a nest | Avoid nests | https://www.mangband.org/forum/viewtopic.php?t=1249&start=45 |
| Death mold after teleport | ? | ? | Bad luck; greed on a vault | *Destruct* the vault instead | https://www.mangband.org/forum/viewtopic.php?t=1249&start=45 |
| Ranger Chieftain | mid | Warrior (serina) | Teleport Other wand burned; hit the Speed key; CCW spam | Heal or end the fight | https://www.mangband.org/forum/viewtopic.php?t=1249&start=45 |
| Vargo + Black knight | 2000 ft | ? | Only Phase Door as escape | A real teleport | https://www.mangband.org/forum/viewtopic.php?t=1249&start=45 |
| Sauron (mistaken for Lorgan) | deep | Ranger | Arrows vs Sauron; two uniques | Identify the monster | https://www.mangband.org/forum/viewtopic.php?t=1249&start=45 |
| Balrog of Moria fire | deep | high | No rFire | Resist gate | https://www.mangband.org/forum/viewtopic.php?t=1249&start=45 |
| Gorlim (water bolt conf, mana bolt) | mid | Mage, 183 HP | No rConf, low HP | Avoid confusers without rConf | https://www.mangband.org/forum/viewtopic.php?t=1249&start=45 |
| AMHD gas | deep | L41 Mage | Meleed it; speed ring over CON | Right tactic; CON | https://www.mangband.org/forum/viewtopic.php?t=1249&start=60 |
| Ulfang / pit trap | ? | L27 Paladin | Low HP, no macros | Heal early; detect traps | https://www.mangband.org/forum/viewtopic.php?t=1249&start=60 |
| Vibration + Earth hounds, Boldor | ? | Mage | Shot arrows instead of teleporting | Escape | https://www.mangband.org/forum/viewtopic.php?t=1249&start=60 |
| Nether hounds after `<` | 3100 ft | L40 | Up staircase deep | `>` only | https://www.mangband.org/forum/viewtopic.php?t=1249&start=60 |
| Chaos hounds after `<` ("special" level) | deep | ? | Same | Same | https://www.mangband.org/forum/viewtopic.php?t=1249&start=60 |
| Summoned pack, Black knight | ? | Ranger | Missiles vs a crowd; CSW | Panic on summons | https://www.mangband.org/forum/viewtopic.php?t=1249&start=60 |
| Medusa fire bolt | deep | Ranger | No base resists | rBase | https://www.mangband.org/forum/viewtopic.php?t=1249&start=60 |
| Greater Balrogs ×10 (U pit) | deep | ? | Stood in LOS of a whole pit | LOS | https://www.mangband.org/forum/viewtopic.php?t=1249&start=60 |
| Ancalagon | deep | Priest | 14/19 misses; no Prayer or resist spells | To-hit and buffs | https://www.mangband.org/forum/viewtopic.php?t=1249&start=60 |
| Saruman in a Zoo of Concentrated Death | deep | ? | Opened the zoo | Don't | https://www.mangband.org/forum/viewtopic.php?t=1249&start=75 |
| Quaker earthquake | deep | ? | HP under 300 while showing as @ | Keep ≥300 HP | https://www.mangband.org/forum/viewtopic.php?t=1249&start=75 |
| Gravity hound | ? | ? | Fought gravity hounds (multi-apply bug) | Avoid | https://www.mangband.org/forum/viewtopic.php?t=1249&start=75 |
| Nightwalker | deep | ? | CCW (69 carried) instead of Teleport Other or *Destruction* | Escape | https://www.mangband.org/forum/viewtopic.php?t=1249&start=75 |
| Undead beholder | ~2500 ft | Mage (serina) | Mana and charges drained, macros useless | Scroll or potion backup | https://www.mangband.org/forum/viewtopic.php?t=1249&start=75 |
| Vibration hound KO + Lorgan | ? | Priest | No rSound, no CCW at stun | CCW at "Stun" | https://www.mangband.org/forum/viewtopic.php?t=1249&start=75 |
| Lokkak, Lorgan, fire hounds | mid | HT Rogue (schroeder) | Speed and CCW instead of escape; thought he still had teleport scrolls | Track your inventory | https://www.mangband.org/forum/viewtopic.php?t=1249&start=90 |
| Eye druj (graveyard) | deep | L47 HT Rogue | Summoned, teleported next to a graveyard, blinded, couldn't read | rBlind | https://www.mangband.org/forum/viewtopic.php?t=1249&start=90 |
| Time hounds (Draugluin summons) | deep | ? | Fought a hound summoner without a corridor or doors | Anti-summon corridor | https://www.mangband.org/forum/viewtopic.php?t=1249&start=90 |
| Tarrasque on arrival | deep | ? (schroeder) | Took `>` wielding a Mace of Fury (aggravate) | Swap off aggravation before stairs | https://www.mangband.org/forum/viewtopic.php?t=1249&start=90 |
| Carcharoth nether | deep | schroeder | Forgot the swap item; forgot it breathes nether | Prep for known uniques | https://www.mangband.org/forum/viewtopic.php?p=6458 |
| Molds + jelly (poison, mind drain) | shallow | ? | Fought many molds, didn't drink Healing, didn't use the Teleport scroll | Avoid molds; use your escapes | https://www.mangband.org/forum/viewtopic.php?p=6482 |
| Time hounds after a Horned Reaper fight | deep | L50 HT Rogue | Teleported instead of WoD; *Destruction* items burned | Carry backup | https://www.mangband.org/forum/viewtopic.php?p=6510 |
| Scatha frost (1365 damage in 2 breaths) | deep | 741 HP | No rCold | rBase | https://www.mangband.org/forum/viewtopic.php?p=6515 |
| Carcharoth-summoned hounds | deep | ? | Fought a hound summoner in the open | Never | https://www.mangband.org/forum/viewtopic.php?p=6529 |
| Dracolich after "commands you to return" | deep | ? | Detected monsters but not invisible (quylthulg) | Detect Invisible | https://www.mangband.org/forum/viewtopic.php?p=6531 |
| Omarax (Teleport Other hit a Beholder) | deep | L40 Mage | Didn't check the monster list; felt safe | Check first | https://www.mangband.org/forum/viewtopic.php?p=6533 |
| Time hound (Backdoor Surprise vault) | 850 ft | eliotn | Stayed on a "special" level; didn't recognise the blue Z; walked away | Leave special levels; teleport | https://www.mangband.org/forum/viewtopic.php?p=6536, https://www.mangband.org/forum/viewtopic.php?p=6540 |
| Ungoliant darkness storm | deep | L? Rogue | No FA; aggravating Calris and Combat gloves | FA; swap aggravators | https://www.mangband.org/forum/viewtopic.php?p=6539 |
| Mouth of Sauron + Balrog | deep | PowerWyrm | Typing in chat, so macros were dead | Don't chat mid-level | https://www.mangband.org/forum/viewtopic.php?p=6792 |
| Quaker (while reading a spoiler) | ZocD | Priest | Distracted near a Zoo of Concentrated Death | Don't linger near vaults | https://www.mangband.org/forum/viewtopic.php?p=6795 |
| Z pack | ? | Ranger (Sinclair) | Teleport staff not inscribed | Inscribe escapes | https://www.mangband.org/forum/viewtopic.php?p=7915 |
| Gorlim | ~2000 ft | L35 HE Mage | No rBlind/rConf; cast CLW; meleed | Check the monster; resists | https://www.mangband.org/forum/viewtopic.php?p=8351 |
| Ariel (lightning, confusion) | ~2000 ft | L34 Hobbit Warrior | No rBase, rConf or rBlind; ran out of CCW; Teleport scrolls not macroed | Staff of Teleportation; more CCW | https://www.mangband.org/forum/viewtopic.php?p=8354 |
| Summoner (hounds) | ? | Ranger | Fought a summoner in the open; used melee over the bow | Never; right weapon | https://www.mangband.org/forum/viewtopic.php?p=8569 |
| Trap | ? | Mage | Didn't detect traps on the sector change | Detect traps | https://www.mangband.org/forum/viewtopic.php?p=9221 |
| Greater Balrog | deep | midlevel Mage, 560 HP | Low CON, no double resist | HP and double resist | https://www.mangband.org/forum/viewtopic.php?p=9793 |
| Plasma hounds | ≥2500 ft | ? | No rSound (plus aggravating items) | rSound at 2500 ft | https://www.mangband.org/forum/viewtopic.php?p=8985, https://www.mangband.org/forum/viewtopic.php?p=9126 |
| Grand Master Mystic | ? | userjjb | Melee stun lock (unresistable) | Avoid mystics | https://www.mangband.org/forum/viewtopic.php?p=9380 |

## Posts worth reading in full
- https://www.mangband.org/forum/viewtopic.php?t=1249 (all pages: start=15, 30, 45, 60, 75, 90): PowerWyrm's death-dump critiques. The best "don't do this" source; only 120 of 184 posts are archived.
- https://www.mangband.org/forum/viewtopic.php?p=6185 and https://www.mangband.org/forum/viewtopic.php?p=9415: the up-stairs and hound rule that changes our stair-scum doctrine.
- https://www.mangband.org/forum/viewtopic.php?p=6201: the stun mechanics and the CCW rule.
- https://www.mangband.org/forum/viewtopic.php?p=9380: melee stun crit maths plus the CON stun-recovery table.
- https://www.mangband.org/forum/viewtopic.php?p=9345 and https://www.mangband.org/forum/viewtopic.php?p=9346: the breath damage cap and resist table, and which resists actually matter.
- https://www.mangband.org/forum/viewtopic.php?p=6011: the warrior survival kit for 1000 ft and below (a shopping list).
- https://www.mangband.org/forum/viewtopic.php?p=5597: early killer list by depth band and letter or colour (a table for the Pilot).
- https://www.mangband.org/forum/viewtopic.php?p=5700: the top-killer stats and why summoners and Z are the threat.
- https://www.mangband.org/forum/viewtopic.php?p=7256: monster spell message strings mapped to effects (for the message classifier).
- https://www.mangband.org/forum/viewtopic.php?p=5974: LOS and corner tactics with ASCII diagrams.
- https://www.mangband.org/forum/viewtopic.php?p=6524 and https://www.mangband.org/forum/viewtopic.php?p=6537: Warrior's minimal YASD doctrine, carry counts, and "don't play special levels".
- https://www.mangband.org/forum/viewtopic.php?p=6080: the Ironman guide, with an unknown-item trial procedure and warrior early game.
- https://www.mangband.org/forum/viewtopic.php?p=8900: time hound doctrine.

## Coverage
- Topics read: 42 of 42 (all posts read in full).
- Topics skipped as irrelevant or with little content: about 9 (t=1190 subforum creation, t=1298 poll with little content, t=1370 Morgoth mage runes,
  t=1529 partly, t=1552/1556/1558 mostly spell- or mage-specific, t=1586 endgame gear, t=1788 "MAngband for Dummies" stub, t=2094 mage stats). Party topics
  t=1265 and t=1310 were read but are mostly irrelevant (solo tool); only the good-citizen and chat notes were kept.
- Gaps: t=1249 is marked [ONLY 120 OF 184 POSTS AVAILABLE]; t=1341 is [ONLY 15 OF 17 POSTS AVAILABLE]. Many death-dump links
  (HighScoreChart) are truncated or dead, so depths and char levels are often unknown. Very little is Half-Orc-specific. Almost nothing covers
  early-warrior pace in the 0-1000 ft band beyond Ashi's "500 ft, clvl 10-15" and the Ironman guide. Nearly all version-sensitive mechanics
  (hounds removed on `>`, all hounds breathing at once, gravity multi-hit, ghost spells, unique respawn) date from 1.1.x (2008-2013) and should be tested on 1.5.
