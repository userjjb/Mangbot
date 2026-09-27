# Pilot handbook (for the agent playing the character)

You steer one MAngband character. A program called the **pilot** plays it
second to second: it moves, fights, escapes, rests and eats on its own. You
decide *strategy*: where to go, when to explore or dive, what to wear, what to
keep, when to go to town. You talk to the pilot with `pilotctl.py`. You never
need to know how the pilot is written.

Run commands from `github/tools/pilot/` with `python3 pilotctl.py --nick NAME
...` (after `module load python3/3.12.4`).

## Your turn: `wait`

`pilotctl.py --nick NAME wait [SECS]` blocks until the pilot needs you, then
prints the attention events and a **situation report**. React, give the next
goal, and wait again. While you're waiting, the pilot keeps the character
safe. If nobody gives it anything to do for a few minutes (`idle_recall_s`),
it reads Word of Recall and goes back to town. That is the rule for
unattended characters.

`wait SECS --brief` prints a short report instead: the character and stats
lines, what you're standing on, monsters in view, known stairs and the news.
Use it for routine turns (it keeps your context small), and `status` when you
need the map, equipment, pack or messages.

Attention events:

| event | meaning |
|---|---|
| `goal_done`, `goal_failed` | the goal finished (the detail says why) |
| `interesting` | a dive stopped for something in `stop_on`: a unique, items, a pillared room (these often hold stairs; explore them), danger |
| `danger_avoided` | (news, doesn't wake you) arrived next to a pack or an out-of-depth monster and went straight back up the stairs. Shown under "Since last report" |
| `danger_seen` | a dangerous monster came into view: the pilot dropped the goal and is heading for the stairs. The detail says why. Danger means: `danger_level` above yours, a unique above your level, a breather whose two strongest breaths would kill you at your current HP, breathers whose breaths together would (hound packs), a paralyser while you lack Free Action (`free_action` order), or a summoner within 5 levels of yours (summons appear next to *you* and stay after it dies) |
| `emergency` | HP fell below `flee_hp`: the pilot took the stairs underfoot, read Phase Door, or quaffed a cure |
| `fight_going_badly` | HP below `think_hp` while fighting: decide whether to flee (e.g. `stairs`, or `read` Phase Door) |
| `low_supply` | out of food (it recalls), no flasks for the lantern, no light at all |
| `idle_recall` | nobody answered for a while: it's recalling to town |
| `unseen_attacker` | something you can't see is attacking ("It hits you", "It breathes...", or HP falling with nothing in view): the pilot heads for the stairs. Also raised (without fleeing) on "You hear a door burst open!". Without See Invisible, leaving the level is the answer |
| `recall_cancelled` | a second Word of Recall was read, which cancels the first: no recall is pending now. Read one again if you still want to go |
| `parked` | the pilot is logging out for an update (at a safe moment). It comes back within a minute or two with `started`; then re-issue your goal |
| `pack_full` | "You have no room for ...": make room (destroy/drop junk, or recall and sell) |
| `stat_drained`, `blows_changed` | a stat was drained or the blows per round changed (a drained DEX can cost a blow: restore it in town, store 5) |
| `breeders` | 3+ breeding monsters (lice, worms) in view: they multiply fast and give no XP. Kill one or two quickly; more than that, leave the area (stairs, or recall) |
| `afraid` | afraid (a warrior can't melee then) and cornered with nothing to cure it: the pilot phased away. Normally, when afraid, the pilot kites over ground already walked until the fear wears off, and only in danger quaffs Boldness/Heroism/Berserk |
| `fearer` | a monster that frightens you again and again is near (e.g. Poltergeist, Ghost, Banshee, Priest, molds): the pilot moves away from it (phases if it's dangerous and adjacent). Usually best to leave that area or level |
| `emergency_loop` | third emergency in 90 s and no stairs nearby: phasing and potions aren't working; recall or leave the area (with stairs known, the pilot leaves by itself) |
| `tactic`, `resumed` | (news) the pilot backed into a corridor against a pack, kited while afraid, or resumed your goal after recovering from an emergency |
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
| `goal explore [until=stairs] [radius=N]` | (dungeon only) walk to unexplored edges until nothing is left (or a `>` is seen, or within N squares) |
| `goal goto Y,X` / `goto >` / `goto <` / `goto item` | walk there |
| `goal hunt NAME` (spaces as `_`) | walk up to the monster called NAME and fight it (standing still; the server swings for you). Ends when it's slain or out of sight 15 s |
| `goal shop N [buy NAME:COUNT]... [sell NAME_OR_LETTER:COUNT]...` | town only: walk into store N (1 General, 2 Armoury, 3 Weaponsmith, 4 Temple, 5 Alchemist, 6 Magic shop, 7 Black market), sell, buy (by part of the name; spaces as `_`, e.g. `buy Cure_Light:5`; the cheapest matching item is bought), leave. The result lists what the shopkeeper actually said ("I don't want that!" for worthless or cursed items) |
| `goal recall` | read Word of Recall (takes ~15-35 s to work; the pilot stays safe meanwhile). From town it takes you to your deepest level so far, or to `max_depth` if that order is set (the pilot inscribes the scroll `@R<feet>` first). A second Word of Recall **cancels** the first, so while one is pending the pilot won't read another (neither this goal nor `read`, unless you add `force` to cancel it on purpose) |
| `goal rest` | rest until healed |
| `goal wait SECS` | stand still |
| `stop` | cancel the goal (safe idle) |

## Actions (immediate)

`wearall` (put on everything that fills an empty slot), `wear L`, `takeoff L`, `quaff L`, `read L [TARGET]`
(TARGET = the item a scroll works on, e.g. `read Identify Rapier` or `read Enchant_Weapon_To-Dam Rapier`;
without it the game picks the first item in the pack), `eat L`, `fuel L` (refill a lantern
from a flask), `inspect L`, `destroy L [N|all]`, `drop L [N|all]`, `inscribe L TEXT`,
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
| `free_action` | no | set `yes` once the character has Free Action: paralysers then stop counting as danger |
| `idle_recall_s` | 600 | recall to town after this long without a goal or a word from you |
| `stop_on` | unique,danger | what makes a dive stop and ask you (add `items`, `pillared` to be asked about those too) |
| `pillared` | explore | during a dive, explore pillared rooms for a `>` without asking (`ask` = stop and ask; `ignore`) |
| `choke` | on | when a pack (3+) comes at you in the open, back into a corridor within 10 squares and fight them there one at a time (experimental) |
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
  `max_depth` if that order is set (the pilot inscribes `@R` then). It once landed at 1000 ft next
  to four Black ogres.
- **Inspect every unique's drop (and anything {excellent}/{special}) before selling it.**
  Wormtongue's armour was sold unseen for 17 gold: it was Soft Studded Leather of Resistance (all
  four basic resistances; buying it back cost 19834). The shop goal now refuses to sell such items
  unless you write `sell !NAME:1`. `inspect NAME` shows what the character knows; wearing it or
  reading Identify on it tells more.
- Do item actions one at a time, by name, and read the reply (it shows the pack afterwards).
  Several destroys sent with letters from an old report hit the wrong items.
- Without Free Action, a monster that paralyses (Illusionists, Carrion Crawlers, Ghouls...) is a
  reason to leave the level, not to fight.
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
  with Priests or packs of paladins (they scare and summon): two trips were lost to fear.
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
- Avoid molds and jellies (stationary, not worth the risk). The pilot does this
  by itself: it paths around anything that never moves (molds, jellies,
  floating eyes, mushroom patches) and steps away if it finds itself next to
  one, because the server's auto-retaliate would otherwise fight it. To fight
  one on purpose, use `goal hunt NAME`. Uniques drop good
  items worth identifying (their drops are inscribed with the unique's name).
- **Pack space runs out before food.** Keep ~1 spare ration. Destroy
  `{average}` weapons and armour you won't use. Rings and amulets found very
  shallow are usually bad. Don't quaff unknown potions without food in the
  pack (Salt Water empties your stomach).
- Depth checkpoints: see-invisible and free action by 1000 ft; the four basic
  resistances by 1250 ft.
- **Breeders** (lice, worms; the `breeders` event): no XP and they multiply fast. Kill one or two
  quickly, otherwise leave the area.
- **Invisible monsters** are usually harmless, but one that drains a stat ("You feel very clumsy")
  is a real threat: leave. A drained DEX can cost a blow; a Potion of Restore <stat> (store 5) fixes it.
- **Meet packs in a corridor** so they reach you one at a time (the `choke` order does this).
- **Money** (how the user turns loot into gold):
  - sell unknown potions and scrolls found early: they're usually bad, and selling identifies them
    and pays a little;
  - sell whatever you won't use (spare bows, weapons);
  - identify items worth identifying before selling (wands, rings, good weapons: an identified Wand
    of Slow Monster fetched 225), but not `{average}` gear, which sells the same;
  - buy discounted things (`{75% off}` Word of Recall, Identify);
  - until the weapon is about (+8,+8), discounted Enchant To-Hit/To-Dam scrolls are good buys.
- Town: sell the starting kit. Buy a lantern and flasks of oil, light armour,
  a light weapon (more blows), Phase Door, Cure Light Wounds potions,
  +to-damage scrolls, Word of Recall.
