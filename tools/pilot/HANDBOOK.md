# Pilot handbook (for the agent playing the character)

You steer one MAngband character. A program called the **pilot** plays it
second to second: it moves, fights, escapes, rests and eats on its own. You
decide *strategy*: where to go, when to explore or dive, what to wear, what to
keep, when to go to town. You talk to the pilot with `pilotctl.py`. You never
need to know how the pilot is written.

Run commands from `github/tools/pilot/` with `python3 pilotctl.py --nick NAME
...` (after `module load python3/3.12.4`).

## Your turn: `wait`

(Your Bash tool times out after 120 s by default: for `wait` longer than ~110 s pass a Bash
`timeout` of (SECS + 60) × 1000, e.g. 300000 for `wait 240`.)
`pilotctl.py --nick NAME wait [SECS]` blocks until the pilot needs you, then
prints the attention events and a **situation report**. React, give the next
goal, and wait again. While you're waiting, the pilot keeps the character
safe. If nobody gives it anything to do for a few minutes (`idle_recall_s`),
it reads Word of Recall and goes back to town. That is the rule for
unattended characters.

`wait SECS --brief` prints a short report instead: the character and stats
lines, what you're standing on, monsters in view, known stairs and the news.
Use it for routine turns (it keeps your context small), and `status` when you
need the map, equipment, pack or messages. A `wait` that times out with no
events always prints the short form: check that the depth or position is
changing (the pilot also raises `stuck` if a goal goes nowhere for 2 minutes).

Attention events:

| event | meaning |
|---|---|
| `goal_done`, `goal_failed` | the goal finished (the detail says why) |
| `interesting` | a dive stopped for something in `stop_on`: a unique, items, a pillared room (these often hold stairs; explore them), danger |
| `danger_avoided` | (news, doesn't wake you) arrived next to a pack or an out-of-depth monster and went straight back up the stairs. Shown under "Since last report" |
| `danger_seen` | a dangerous monster came into view: the pilot dropped the goal and is heading for the stairs. The detail says why. Danger means: `danger_level` above yours, a unique above your level, a breather whose two strongest breaths would kill you at your current HP, breathers whose breaths together would (hound packs), a paralyser while you lack Free Action (`free_action` order; a paralysing blow too weak to get through your armour doesn't count), or a summoner within 5 levels of yours (summons appear next to *you* and stay after it dies). Also, from the Advisor's danger table: a monster rated 5 ("leave on sight"), one rated 4 until you're 8 levels above it, any capital `D`, one whose melee per turn (speed × blows, all hitting) is a third of your current HP or more, Brain Smash without Free Action + both resists below, and a monster within 10 levels that blinds or confuses with its *blows* (no saving throw) while you lack the resist |
| `emergency` | HP fell below `flee_hp`: the pilot took the stairs underfoot, read Phase Door, or quaffed a cure |
| `fight_going_badly` | HP below `think_hp` while fighting: decide whether to flee (e.g. `stairs`, or `read` Phase Door) |
| `low_supply` | out of food (it recalls), no flasks for the lantern, no light at all |
| `idle_recall` | nobody answered for a while: it's recalling to town |
| (group danger) | the pilot adds up the worst-case melee of every monster that can reach you this turn (max damage × speed, +200 for a paralysing blow without Free Action; monsters that never move don't count; drains don't count here, they have the second-drain rule), or the HP actually lost in the last 3 s if that's more (an unseen swarm). Above 30% of your current HP: back up the stairs if just arrived, else back away instead of walking into them (never from something faster than you: it can't be outrun) (`danger_avoided` / `tactic`). Above 60%: the stairs underfoot; Phase Door only once HP is below `think_hp` (`tactic`). Above 100%: it leaves the level (`danger_seen` "group danger"), phases when adjacent (at most every 10 s), and with no stairs known reads Word of Recall at once (`emergency`), since recall takes 15-34 turns. The worst case is pessimistic (every blow at maximum): at low clvl a single monster can reach 60%, so this rule no longer phases at good HP. The pilot also checks that each of its own emergency reads and quaffs took effect ("You have N ... left") and resends it (twice at most, `tactic` news) if not. A second stat drain on one level with monsters in view also makes it leave (`danger_seen`). This is the rule that would have saved Dive03 (4 Uruks + a Giant red scorpion: ~255 vs 207 HP) |
| `unseen_attacker` | something you can't see is attacking ("It hits you", "It breathes...", or HP falling steadily while nothing has been in view for several seconds): the pilot heads for the stairs (at or below `max_depth` it prefers an up staircase). Also raised (without fleeing) on "You hear a door burst open!". Minor ones at HP above `think_hp` are news only and the pilot carries on: "It commands you to return" (a Tengu or Blink dog teleporting you to it), a magic missile, an arrow or bolt from the dark. Without See Invisible, leaving the level is the answer |
| `user_message` | the user, watching live, sent you a message: treat it as a change to your mission (their requests outrank your plan, within safety); answer with `say "<text>"` (shown in their viewer), then act |
| `stuck` | the goal has gone nowhere for 2 minutes (at most 10 squares visited, no fighting in those 2 minutes): the pilot cleared its command queue and restarted the move. If it repeats, give a different goal (`goto` the stairs, or another level) |
| `recall_cancelled` | a second Word of Recall was read, which cancels the first: no recall is pending now. Read one again if you still want to go |
| `parked` | the pilot is logging out for an update (at a safe moment). It comes back within a minute or two with `started`; then re-issue your goal |
| `pack_full` | "You have no room for ...": make room (destroy/drop junk, or recall and sell) |
| `stat_drained`, `blows_changed` | a stat was drained (also a second drain of a stat already drained) or the blows per round changed (a drained DEX can cost a blow: restore it in town, store 5) |
| `breeders` | (news only when they're weak and fewer than 8) 3+ breeding monsters (lice, worms) in view: they multiply fast and give no XP. Kill one or two quickly; more than that, leave the area (stairs, or recall) |
| `afraid` | afraid (a warrior can't melee then) and cornered with nothing to cure it: the pilot phased away. Normally, when afraid, the pilot kites over ground already walked until the fear wears off, and only in danger quaffs Boldness/Heroism/Berserk |
| `fearer` | a monster that frightens you again and again is near (e.g. Poltergeist, Ghost, Banshee, Priest, molds): the pilot moves away from it (phases if it's dangerous and adjacent). Usually best to leave that area or level |
| `emergency_loop` | third emergency in 90 s and no stairs nearby: phasing and potions aren't working; recall or leave the area (with stairs known, the pilot leaves by itself) |
| `tactic`, `resumed` | (news) the pilot backed into a corridor against a pack, kited while afraid, cured a status in a fight, killed a stationary monster in its way, or resumed your goal after recovering from an emergency |
| `dead` | the character died |

## The situation report (`status`)

- Character line: level, HP, depth (50 ft per dungeon level; Town = 0), gold,
  blows per round, speed. Then stats, hunger and conditions.
- **Standing on**: `<` or `>` when you're on a staircase. That is your fastest
  escape: stairs work even when confused.
- Equipment, then **Pack** with the letters to use in commands (`a)`, `b)`...).
- A **map** around you: `@` is you; letters are monsters (named in the next
  line); `#` wall, `.` floor, `+` closed door, `'` open door, `<` `>` stairs,
  `^` trap. Other symbols are objects: `!` potion, `?` scroll, `=` ring, `"`
  amulet, `|` `/` `\` weapons, `(` `[` `]` `)` armour, `$` gold, `~` light or
  tool, `_` staff, `-` wand or rod, `,` food or mushroom.
- **Monsters in view**: names, level (compare with yours), UNIQUE, distance.
- **Items seen**: the server's list of objects seen on this level.
- Known stairs, recent messages, standing orders.

## Goals (one at a time; a new goal replaces the old)

| command | what the pilot does |
|---|---|
| `goal dive FEET` (shallower than now = climb) | stair-scum down to FEET: take a `>` when one is known, otherwise go up and down the staircase underfoot for a fresh level; explore if no stairs are known. Stops early for `stop_on` things |
| `goal search` | search for secret doors at dead ends, corridor ends and room corners (a dive does this by itself when a level seems to have no stairs) |
| `goal explore [until=stairs] [radius=N]` | (dungeon only) walk to unexplored edges until nothing is left (or a `>` it can reach is seen, or within N squares). It fetches items within `loot_radius` on the way, but not distant ones it saw earlier: when it's done, collect those from the report's item squares with `goto` |
| `goal goto Y,X` / `goto >` / `goto <` / `goto item` | walk there. With `pickup=all`, an item on the target square is picked up by itself, about half a second after arriving (it waits for the character's turn): check the pack before a manual `pickup` |
| `goal hunt NAME` (spaces as `_`) | walk up to the monster called NAME and fight it (standing still; the server swings for you). Ends when it's slain or out of sight 15 s |
| `goal shop N [list] [buy NAME:COUNT[@MAX]]... [sell NAME_OR_LETTER:COUNT]...` | `list`: the result starts with the store's whole stock and prices (use it alone to look before buying). `@MAX`: don't pay more than MAX each (e.g. `buy To-Dam:2@120`). Town only: walk into store N (1 General, 2 Armoury, 3 Weaponsmith, 4 Temple, 5 Alchemist, 6 Magic shop, 7 Black market), sell, buy (by part of the name; spaces as `_`, e.g. `buy Cure_Light:5`; the cheapest matching item is bought), leave. The result lists what the shopkeeper actually said ("I don't want that!" for worthless or cursed items) |
| `goal resurrect` | (only as a ghost, after `dead`) float up one level per `<` to town, then walk onto the Temple entrance (`4`), which resurrects. **It halves the experience for good.** Do it at once: a ghost left in the dungeon keeps getting hit (Dive03's ghost was poisoned while logged out and faded away forever on the next login). Untested so far |
| `say TEXT` | (not a goal) a short answer to the user, shown in their live viewer and logged |
| `monster NAME` | (a query, not a goal) this server's data for a monster (level, speed, blows, spells, flags, breath, melee per turn, the Advisor's 0-5 rating) and whether a danger rule fires for you now. Monster data here differs from Vanilla Angband: ask this instead of relying on memory |
| `goal town` | (wilderness only) walk back to town: it leaves each wilderness sector by the edge you came in through. The town has edges into the wilderness (`left_town` news if you walk off it); mission 13 ran off the west edge at night |
| `goal townfarm GOLD [MINUTES]` | (town only, default 10 min) kill gold-dropping townspeople (singing drunk, aimless merchant, squint-eyed rogue, mercenary, veteran) and pick up their gold until you have GOLD; it sweeps the town in a zig-zag to find them and lights up at night. **When a purchase is a little short, this is faster than a short dive and saves the Word of Recall a dive would burn** (the user). Mission 14's test: 372 → 495 gold in under a minute |
| `goal recall` | read Word of Recall (takes ~15-35 s to work; the pilot stays safe meanwhile). From town it takes you to your deepest level so far, or to `max_depth` if that order is set (the pilot inscribes the scroll `@R<feet>` first). A second Word of Recall **cancels** the first, so while one is pending the pilot won't read another (neither this goal nor `read`, unless you add `force` to cancel it on purpose) |
| `goal rest` | rest until healed |
| `goal wait SECS` | stand still |
| `stop` | cancel the goal (safe idle) |

## Actions (immediate)

`wearall` (put on everything that fills an empty slot), `wear L`, `takeoff L`, `quaff L`, `read L [TARGET]`
(TARGET = the item a scroll works on, e.g. `read Identify Rapier` or `read Enchant_Weapon_To-Dam Rapier`;
without it the game picks the first item in the pack), `eat L`, `fuel L` (refill a lantern
from a flask; rarely needed: the pilot refills the lantern by itself when it runs low), `inspect L`, `destroy L [N|all]`, `drop L [N|all]`, `inscribe L TEXT`,
`pickup` (what's underfoot), `stairs [<|>]`. L is the pack letter from the
report, **or part of the item's name** with spaces as `_` (e.g. `destroy Salt_Water`,
`quaff Cure_Light`), which is safer: a name is looked up at the moment the pilot acts. Each item
action answers with what the game said and the pack as it is *now*: use those letters for the
next action. With `pickup=all` (the default) the pilot picks up whatever it walks
onto when nothing is next to it. Letters shift when items come and go (and
when identifying re-sorts the pack): check `status` before a series of
actions, and act from the last letter backwards.

What the pilot does by itself in an emergency (HP below `flee_hp`): take
the staircase underfoot (then it rests on the other side, and comes back up if
that's below `max_depth`; the goal is dropped and you're told); with a monster next to you, read Phase Door (at most
every 2.5 s: repeated phasing doesn't shake a pack); otherwise walk to stairs
within 20 squares, or quaff Cure Light/Serious/Critical Wounds. Below 35% HP
with something adjacent it phases again at once; below 30% it also reads Word
of Recall (it takes 15-35 s to work, so it starts early). Keep plenty
of Phase Door and cure potions: it will use them.

## Standing orders (`order key=value ...`)

| order | default | meaning |
|---|---|---|
| `flee_hp` | 0.5 | emergency escape below this fraction of max HP |
| `think_hp` | 0.65 | ask you below this while fighting |
| `rest_below` / `rest_to` | 0.7 / 0.95 | rest when hurt and alone |
| `arrival_pack` | 4 | this many monsters near the stairs on arrival: leave at once |
| `danger_level` | 6 | a monster this many levels above yours counts as danger |
| `free_action` | no | only used until the pilot has read the character sheet's grid (a few seconds after login): from then on Free Action is known from the `Abilities:` line, whatever this says |
| `resist_blind`, `resist_conf` | no | the same for resist blindness / confusion (monsters that blind / confuse with their blows stop counting as danger once you have the resist) |
| `unseen_hp` | on | `off`: HP loss with nothing in view no longer counts as an unseen attacker (the "It ..." messages still do) |
| `idle_recall_s` | 600 | recall to town after this long without a goal or a word from you |
| `stop_on` | unique,danger | what makes a dive stop and ask you (add `items`, `pillared` to be asked about those too) |
| `pillared` | explore | during a dive, explore pillared rooms for a `>` without asking (`ask` = stop and ask; `ignore`) |
| `choke` | on | when a pack (3+) comes at you in the open, back into a corridor within 10 squares and fight them there (experimental). Corridors here are **two wide** (doorways too), so up to 3 reach you at once; it prefers a dead end or one-wide spot, then a corner or corridor end, then a straight corridor |
| `max_depth` | 0 | feet, 0 = no limit: dives stop there, exploring below it is refused, and after an emergency escape down the stairs the pilot rests and comes back up |
| `loot_radius` | 10 | during a dive, fetch items seen within this many squares (0 = never) |
| `pickup` | all | all or none |
| `autodestroy` | worthless,cursed | pseudo-ID feelings (`{average}`, `{worthless}`, `{cursed}`...) whose items the pilot destroys by itself (never items you inscribed with `@` or `!`). Add `average` when pack space matters more than the few coins they sell for |
| `junk` | Salt Water, Blindness, ... | comma list: items "of" these are never picked up (unknown items still are) |

Orders are remembered across pilot restarts.

## Lessons from earlier missions

- **Never go down without a Word of Recall for the way back.** Walking home by stairs took 20
  minutes (and 16 minutes down): it ate most of a 45-minute mission.
- Before reading Word of Recall in town, know where it lands: your deepest level so far, or
  `max_depth` if that order is set (the pilot inscribes `@R` then, checks the scroll reads that
  depth, and won't read it if it can't). It once landed at 1000 ft next to four Black ogres. The
  server reads the **last** `@R` on the scroll: a multiple of 50 is feet (`@R750`), anything else
  a level number (`@R15` = 750 ft); a typo (`@r750`) means your deepest level. In town, `read` of
  a Word of Recall with no valid `@R` is refused unless you add `force`.
- **Inspect every unique's drop (and anything {excellent}/{special}) before selling it.**
  Wormtongue's armour was sold unseen for 17 gold: it was Soft Studded Leather of Resistance (all
  four basic resistances; buying it back cost 19834). The shop goal now refuses to sell such items
  unless you write `sell !NAME:1`. `inspect NAME` shows what the character knows; wearing it or
  reading Identify on it tells more.
- Do item actions one at a time, by name, and read the reply (it shows the pack afterwards).
  Several destroys sent with letters from an old report hit the wrong items.
- Without Free Action, a monster that paralyses (Illusionists, Carrion Crawlers, Ghouls...) is a
  reason to leave the level, not to fight.
- **Rubble** (`:`) doesn't seal a level: the pilot digs through it when its path needs to (a few
  turns each). Only a hard wall stops it.
- **Count your Word of Recall in the pack after every recall** and before going down.
- **Disenchanters and stationary monsters in the way**: every disenchanting gaze or touch removes
  a plus from your gear (mission 6 lost +2,+2 on the weapon and +1-2 on four armour pieces going
  around a Disenchanter eye). Now, next to a stationary monster at or below your level that
  disenchants, or that sits by the square the pilot is walking to (e.g. beside the stairs), the
  pilot stands and kills it (`tactic` news). A disenchanter above your level makes it leave the
  level (`danger_seen`). It never melees a paralysing one (floating eye) without `free_action=yes`:
  if one blocks the only stairs, pick other stairs. Others it still paths around; `goal hunt` for
  any you want dead.
- "It commands you to return" is teleport-to: harmless from a Tengu or Blink dog, and at good HP
  the pilot carries on. Not harmless from Orfax, a Quasit, Imp, Evil eye (it then casts Hold), Phase
  spider, Vampire, Mage or Draebor: you can't walk away from these; leave by stairs or Phase Door.
- **Status cures in a fight** (by itself, cheapest potion that works): stunned → Cure Critical
  Wounds or better (only CCW+ cures stun and poison); confused → Cure Serious or better; blind →
  Cure Light or better; poisoned → Cure/Neutralize Poison or CCW, only once HP is below
  `think_hp`. Out of a fight it rests them off. Carry a few CCW once stunners appear (you get a
  `tactic` note when it has nothing to cure a status with).
- **Compare found armour and weapons with what you wear before selling them** (`inspect`): found
  `{good}` gear is often an upgrade. And take `average` out of `autodestroy` before fetching a
  plain base-item upgrade (a Small Metal Shield [3] was destroyed on pickup).
- **Never put on an unknown ring or amulet**: 19-58% of unknown rings and ~20% of amulets are
  cursed, a cursed one can't be taken off (Remove Curse ~155 at the Temple), and wearing one
  doesn't identify it. Identify it first (the Advisor's identify-and-sell memo; `wearall` skips them).
- **Budget two Word of Recall per trip**: the pilot reads one by itself below 30% HP, and each of
  two trips in mission 2 cost a whole scroll that way.
- Potions heal a fixed amount: Cure Light 15 HP, Cure Serious 20-24, Cure Critical 25-29,
  Healing 300, *Healing* 1200. At 200+ max HP the Cure potions are small, so buy Cure Critical (it
  also cures stun, confusion, blindness and poison) and save for Healing. The pilot measures how
  fast HP is falling and drinks the weakest potion that out-heals it. When no potion can keep up
  and death is seconds away, it escapes instead (Phase Door, then Word of Recall) rather than
  wasting turns drinking. **Out of combat it never drinks for HP: it rests** (and backs away
  first if a monster is in view but not fighting). Against weak monsters `flee_hp=0.4` saves potions.
- **Buy Potions of Boldness or Heroism whenever the store has them.** Without them, leave a level
  with Priests (they summon) or packs of Novice paladins (they scare): two trips were lost to fear.
- A character with a 1d6 weapon, 3 blows and AC ~30 struggled against groups at 650-700 ft;
  450-550 ft earned XP and gold more safely until the gear improves.
- `max_depth` caps dives (the pilot now says so): raise it first when you mean to go deeper.
- Leave the pack to the pilot's `junk` and `autodestroy` orders; add `average` to `autodestroy`
  when the pack fills too fast.

## How good players play (the user's advice and observed play)

- **Dive by stair-scumming.** With connected stairs you always stand on a
  staircase after taking one. Go up and down until a `>` shows up close by,
  then take it. Stop for interesting things: a good item in view, a possible
  vault, a lit room full of stuff. **Pillared rooms** (columns in the middle or
  along the edges) often hold stairs: explore them.
- **Fight by standing still.** The server attacks adjacent monsters for you at
  your full blow rate. Walking away is how you disengage.
- **Escape order:** the staircase underfoot, then Phase Door, then a cure
  potion. Word of Recall is slow (not an emergency escape). Phase Door
  alone often won't shake a pack.
- Below **60–70% HP**, or when a kill takes unusually long, think about more
  than just fighting. The real killers are **summoners** and **packs that
  breathe or cast at range**. Leave those levels.
- Avoid molds and jellies (most are stationary; the Ochre jelly, +10 speed, and the Gelatinous
  cube move and chase). The pilot does this
  by itself: it paths around anything that never moves (molds, jellies,
  floating eyes, mushroom patches) and steps away if it finds itself next to
  one, because the server's auto-retaliate would otherwise fight it. To fight
  one on purpose, use `goal hunt NAME`. Uniques drop good
  items worth identifying (their drops are inscribed with the unique's name).
- **Progression plan for the throwaway warrior** (the Advisor's `memos/2026-10-07-warrior-progression.md`;
  `order max_depth=` warns when you set it deeper than the gate: clvl × 50 ft up to 1000 ft, then
  (clvl − 5) × 50, and never below 1000 ft without Free Action):

  | stage | clvl | depth | before going | buy |
  |---|---|---|---|---|
  | A | 11–12 | 250–450 ft | STR restored, a 4-blow weapon, 1 WoR | Restore Strength ~470, Main Gauche 40, WoR 240, CLW to 5+ |
  | B | 12–15 | 500–750 ft | 2 WoR, 5 Phase, 3 CCW (or 5 CSW), To-Dam +2, AC ~25 | To-Dam ×2–4, CCW 155, Metal Cap, Hard Leather Boots, Large Leather Shield |
  | C | 15–20 | 750–1000 ft | 4 CCW, 8 Phase, 2 WoR, See Invisible or avoid invisible threats | start saving ~1,000/trip for a Staff of Teleportation (4,000–4,900) |
  | D | 20–25 | 1000 ft (hold) | Free Action (found), the staff (22% fail at clvl 20), 4+ CCW | the staff; CCW, Phase, WoR |

  The bottleneck after clvl 20 is found gear (Free Action, resists), not XP. Uniques you've
  already killed give no XP and no drop.
- **Blows** come from STR and DEX against weapon weight (below 3 lb a weapon counts as 3 lb). At
  STR 18/50 and DEX 18/10 a Main Gauche or Dagger gives 4 blows, a Sabre 3, anything over 10 lb 2
  or fewer; a drained STR costs blows until a Potion of Restore Strength (Alchemist only; levels
  don't restore stats). The report's `Weapons:` line computes blows and damage per round for
  every weapon you carry at your current STR/DEX, and the pilot tells you (`tactic`) when a
  carried one beats the wielded one by 20%: wield it. On this character, 4 light blows plus
  To-Dam beat heavy dice; don't switch for a bigger die without checking blows.
- **Monsters that kill a diving warrior (0–1500 ft)** (Advisor danger-table memo, checked in the
  server code; the pilot's `danger_table.csv` rates every monster to level 40):
  - Paralysis stacks until you die: without Free Action, leave any level with a paralyser that can
    reach you (Carrion crawlers, Ghouls, Homunculus, Evil eyes, Ogre mages, Basilisks).
  - Monsters that blind or confuse *with their blows* (Umber hulk, Hummerhorn, Giant firefly,
    ticks, Catoblepas, molds and mushroom patches) get no saving throw: only the resist helps.
    Blind or confused, you can't read scrolls (staffs still work).
  - Your saving throw is only about 15% + clvl, and resist fear comes only at clvl 30.
  - Fast monsters (+10) act twice per turn: Grip and Fang, Azog, Beorn, Mim, the 5-headed hydra,
    the chieftains. Their damage per turn is twice what the dice say.
  - Armour doesn't reduce breath, bolts, or fire/cold/acid/lightning/poison bites.
  - Uniques at 350–1000 ft (Mughash, Wormtongue, Lagduf, Brodda, Grishnákh, Orfax, Golfimbul,
    Boldor, Ufthak, Ulfast, Nar, Shagrat, Gorbag, Bolg) outclass an under-levelled character. Leave
    unless you fight them in a corridor with the stairs underfoot.
  - A capital `D` is an ancient dragon, always out of depth above 2000 ft: leave.
  - Floating eyes are harmless unless something else attacks you while you're paralysed.
  - A room packed with `T` at 1050–1500 ft is a troll pit drawn 10 levels deeper: leave. Don't
    open vaults (permanent walls) or pits: most forum deaths at these depths came from them.
  - Gear to aim for: Free Action by 1000 ft (the most valuable item), resist poison by ~1000 ft
    (air hounds, Basilisk), resist confusion and blindness from ~800 ft (no-save blows start
    there; until then carry CCW).
- **Pack space runs out before food.** Keep ~1 spare ration. Destroy
  `{average}` weapons and armour you won't use. Rings and amulets found very
  shallow are usually bad. Quaff-test an unknown potion only when all hold: a stack of 2+, HP at
  80% or less (a cure at full HP doesn't identify), nothing in view, food in the pack (Salt Water
  empties your stomach), no STR/DEX blow breakpoint at risk, and the flavour table doesn't call it
  junk. 12-16% of unknown potions at 250-750 ft drain STR, DEX or CON (Restore ~470).
- Depth checkpoints: see-invisible and free action by 1000 ft; the four basic
  resistances by 1250 ft.
- **Breeders** (lice, worms; the `breeders` event): no XP and they multiply fast. Kill one or two
  quickly, otherwise leave the area.
- **Invisible monsters** are usually harmless, but one that drains a stat ("You feel very clumsy")
  is a real threat: leave. A drained DEX can cost a blow; a Potion of Restore <stat> (store 5) fixes it.
- **Meet packs in a corridor** so fewer reach you at once (the `choke` order does this). Corridors
  are two wide here, so a dead end, a corner or a one-wide tunnel is better than a straight stretch.
- **Money** (how the user turns loot into gold):
  - **unknown items** (the Advisor's identify-and-sell memo, `memos/2026-10-07-identify-and-sell.md`):
    selling one unknown item **identifies its flavour** for good (for this and every later
    character: flavours are fixed per server; the pilot keeps a table, `runs/flavours.json`, and
    the report shows "(= Potion of X; not aware)"). So: junk per the table → sell unknown (the
    shop refuses it once known); a stack of 2+ → sell **one**, then use or sell the rest at the
    real price; single potions/scrolls while you've never been below 1000 ft → sell; anything
    from deeper, and every wand, staff, rod, ring and amulet → Identify (81) first, then keep
    the useful ones (Free Action, See Invisible, resists, Teleport Other, Slow/Sleep/Confuse
    Monster, light/door rods) and sell the rest. Buy Identify when discounted (57-60), keep 2-3;
  - sell whatever you won't use (spare bows, weapons);
  - identify items worth identifying before selling (wands, rings, good weapons: an identified Wand
    of Slow Monster fetched 225), but not `{average}` gear, which sells the same;
  - buy discounted things (`{75% off}` Word of Recall, Identify);
  - until the weapon is about (+8,+8), discounted Enchant To-Hit/To-Dam scrolls are good buys.
- Town: sell the starting kit (the Broad Sword and Chain Mail fetch a lot compared with their use:
  the user). Buy a Main Gauche (light: more blows), Enchant To-Hit/To-Dam scrolls for it (discounted
  ones first), cheap unenchanted armour for every empty slot (cloak, gloves, boots, leather shield,
  cap: good AC for the price), a lantern and flasks of oil, Phase Door, Cure Light Wounds potions,
  Word of Recall.
  - Buy the cheap essentials (CLW, Phase Door) first and enchant scrolls last, one at a time: the
    shop goal doesn't ask before paying (`buy To-Dam:3` spent 302 of 366 gold in mission 8).
  - Prices seen with CHR 4 (mission 8): Phase Door 24, CLW 23, Flask of oil 5, Dagger 16, Soft
    Leather Armour 24, Small Leather Shield 41, Hard Leather Cap 12, Cloak 5, Enchant To-Dam ~150-200
    (151 at 25% off), Enchant To-Hit 52 at 75% off; CCW 152 at the Temple (mission 7). The starting
    Broad Sword sold for 102 and the Chain Mail for 358. Stock runs out (the Temple had no CLW twice)
    and not every weapon is stocked (no Main Gauche or Rapier in mission 8; a Dagger gave 4 blows).
  - `inspect` doesn't show blows: wield the weapon and watch for `blows_changed` (or the status line).
- **Which store sells what** (the Advisor's shops memo, 2026-09-29, from the server code):
  **cures (CLW/CSW/CCW), Boldness and Heroism only at the Temple (4)**; Phase Door, Word of Recall,
  Enchant and Identify only at the Alchemist (5); Staff of Teleportation at the Magic shop (6).
  **No store sells Scrolls of Teleportation.** Brass Lanterns (~55) and Flasks at the General
  Store (1). The Armoury's owner charges a Half-Orc least (135%, others 154-170%, Black market ×3).
- **Stock changes every ~33 s**: if something's missing, `goal wait 40` in town (not `rest`) and
  look again with `goal shop N list`. Always take a `{N% off}` line first.
- **Light burns in town, ~10× faster while resting** (time runs 10× while resting with nothing in
  view). The pilot takes the light off when idle in town and puts the best one back on in the
  dungeon. Store torches and lanterns come half full: buy a lantern early, refill with flasks.
- Shopping lists per depth band and budget: `memos/2026-09-29-shops.md` §3. From 500 ft carry
  3 CCW, 5+ Phase Door and 1-2 WoR. A Staff of Teleportation (3,100+, the only buyable long
  escape) **fails 67-83% at clvl 10, 33-40% at 15, ~20% at 20** for a Half-Orc warrior: not an
  escape before clvl ~20. A Staff of Perception isn't worth buying yet (only from ~1000 ft).
- Selling: potions and scrolls fetch 7-9 each (not worth the walk); unknown items sell at their
  plain base value, so Identify (Alchemist, 20-80) anything that might be magical first. Never
  sell Staffs of Door/Stair Location or Teleportation.
- Mission 12 sold 2 Potions of Speed and 2 of Heroism unknown for 8 each (selling one would have
  identified the stack); Dive03 sold 14 unknown devices and jewellery for ~3,600 less than they
  were worth. Discounts vanish when the stock rolls over (~33 s): `list` again after any wait.
- **New report lines:** `Abilities:` is the character sheet's resist/ability grid (free_act,
  see_invis, res_conf, ...), read from the game, so trust it over item names. `Standing on:`
  shows the item under you. `State audit:` counts how often the pilot's picture of the
  character differed from a fresh check (and it resynced). Wait reports show the news since your
  previous wait; `status` shows the last 10 minutes.
- **An item command whose reply says "no change in the pack or equipment yet: it may not have
  happened" didn't do anything you can see**: check before assuming it worked. The pilot reports
  its own actions that showed no effect as `tactic` "no effect seen".
- **The shop goal applies the unknown-item rules above**: it sells junk-per-table, one of a stack,
  and potions/scrolls while your deepest level is above 1000 ft; it refuses unknown wands, staffs,
  rods, rings and amulets and table-known good items, saying why (`sell !NAME` to force).
- The report's `Supplies:` line (also in `--brief`) lists your potions, scrolls, food, flasks,
  staffs and wands with counts, a pending recall, max_depth and drained stats. `lost` news means
  something was destroyed, stolen or overflowed (e.g. "Your purse feels lighter": a thief).
- **At night `townfarm` earns little** (mission 14: ~7 gold/min; few townspeople about): selling
  identified spare staffs and wands is faster (Object Location 151/84, Magic Missile 84).
- **Unique drops turn up in town too** (Farmer Maggot's Lance {good}: identified (+4,+4), sold for
  391). `found` news now flags picked-up items that look special: identify, then `sell !NAME`.
- **After an Enchant scroll**, the weapon's name (and the `Weapons:` line) shows the new plus only
  once the weapon is identified; the enchantment is there anyway.
- Near town (50-150 ft), climbing by stairs saves a Word of Recall.
- `goal recall` puts a light on first (reading needs light: at night in town the pilot keeps it
  off while idle), and if a recall fails it quotes the game's reason. It now finishes only when
  the recall happens, not when you take stairs while it's pending.
- Mission 13's quaff-test was a Potion of Weakness and cost a blow (STR at a breakpoint).
- The report's map lines start with their row number (`43|...`), and the header gives the
  column range, so `goto Y,X` coordinates can be read straight off it. A climb (`goal dive` to a
  shallower depth) uses a `>` to get a fresh level only if it's within 8 squares and the level
  below is within `max_depth`; otherwise it explores for a `<`.
- The status line's level is your current level; after an experience loss (resurrection halves
  it) it also shows the highest level you reached, e.g. "level 8 (max 10)".
- **Never go below 150 ft with fewer than 3 cure potions**, even with a Word of Recall in hand
  (mission 10 spent the cure money on a bargain WoR and died at 250 ft).
- **A rated-4 unique with a pack (Mughash and his kobolds at 250 ft), or a fast unique near your
  level (Bullroarer, +10): send `stairs` or `goal goto <` at once** if stairs are close, and
  don't wait for the flee. The pilot now treats a fast unique within 8 levels as danger at first
  sight, and no longer backs into a corridor while fleeing.
- **Restock when Phase Door drops below 4** (not 2), and don't explore 250 ft and deeper with only
  2 Phase and 1-2 potions: uniques like Bullroarer turn up there (mission 9: 24/115 HP).
- `stuck` with "no known path" to stairs you can see in the report: a plain `goal explore` gets it
  moving again. (`goal explore until=stairs` now ends only at stairs it can reach.)
- With `pickup=all` the pilot picks up what you dropped (a dead torch came back): `destroy` junk
  instead of dropping it.
- "Connection refused" after a fight: first check whether the character died (the pilot stays up
  after a death since 785f608; `status` says so). Only then treat it as a Pilot crash.
- Monster levels come from this server's `monster.txt`, which differs from Vanilla Angband (e.g.
  White jelly is level 2, Radiation eye level 3 here). Trust the level the pilot shows.
