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

Attention events:

| event | meaning |
|---|---|
| `goal_done`, `goal_failed` | the goal finished (the detail says why) |
| `interesting` | a dive stopped for something in `stop_on`: a unique, items, a pillared room (these often hold stairs; explore them), danger |
| `danger_avoided` | (news, doesn't wake you) arrived next to a pack or an out-of-depth monster and went straight back up the stairs. Shown under "Since last report" |
| `emergency` | HP fell below `flee_hp`: the pilot took the stairs underfoot, read Phase Door, or quaffed a cure |
| `fight_going_badly` | HP below `think_hp` while fighting: decide whether to flee (e.g. `stairs`, or `read` Phase Door) |
| `low_supply` | out of food (it recalls), etc. |
| `idle_recall` | nobody answered for a while: it's recalling to town |
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
| `goal dive FEET` | stair-scum down to FEET: take a `>` when one is known, otherwise go up and down the staircase underfoot for a fresh level; explore if no stairs are known. Stops early for `stop_on` things |
| `goal search` | search for secret doors at dead ends, corridor ends and room corners (a dive does this by itself when a level seems to have no stairs) |
| `goal explore [until=stairs] [radius=N]` | (dungeon only) walk to unexplored edges until nothing is left (or a `>` is seen, or within N squares) |
| `goal goto Y,X` / `goto >` / `goto <` / `goto item` | walk there |
| `goal hunt NAME` | walk up to the monster called NAME and fight it (standing still; the server swings for you). Ends when it's slain or out of sight 15 s |
| `goal shop N [buy NAME:COUNT]... [sell NAME_OR_LETTER:COUNT]...` | town only: walk into store N (1 General, 2 Armoury, 3 Weaponsmith, 4 Temple, 5 Alchemist, 6 Magic shop, 7 Black market), sell, buy (by part of the name; spaces as `_`, e.g. `buy Cure_Light:5`; the cheapest matching item is bought), leave. The result lists what the shopkeeper actually said ("I don't want that!" for worthless or cursed items) |
| `goal recall` | read Word of Recall (takes ~15-35 s to work; the pilot stays safe meanwhile). From town it takes you to your deepest level so far |
| `goal rest` | rest until healed |
| `goal wait SECS` | stand still |
| `stop` | cancel the goal (safe idle) |

## Actions (immediate)

`wearall` (put on everything that fills an empty slot), `wear L`, `takeoff L`, `quaff L`, `read L`, `eat L`, `fuel L` (refill a lantern
from a flask), `inspect L`, `destroy L [N]`, `drop L [N]`, `inscribe L TEXT`,
`pickup` (what's underfoot), `stairs [<|>]`. L is the pack letter from the
report. With `pickup=all` (the default) the pilot picks up whatever it walks
onto when nothing is next to it. Letters shift when items come and go (and
when identifying re-sorts the pack): check `status` before a series of
actions, and act from the last letter backwards.

What the pilot does by itself in an emergency (HP below `flee_hp`): take
the staircase underfoot; with a monster next to you, read Phase Door (at most
every 2.5 s: repeated phasing doesn't shake a pack); otherwise walk to stairs
within 20 squares, or quaff Cure Light/Serious/Critical Wounds. Keep plenty
of Phase Door and cure potions: it will use them.

## Standing orders (`order key=value ...`)

| order | default | meaning |
|---|---|---|
| `flee_hp` | 0.5 | emergency escape below this fraction of max HP |
| `think_hp` | 0.65 | ask you below this while fighting |
| `rest_below` / `rest_to` | 0.7 / 0.95 | rest when hurt and alone |
| `arrival_pack` | 4 | this many monsters near the stairs on arrival: leave at once |
| `danger_level` | 6 | a monster this many levels above yours counts as danger |
| `idle_recall_s` | 600 | recall to town after this long without a goal or a word from you |
| `stop_on` | unique,danger | what makes a dive stop and ask you (add `items`, `pillared` to be asked about those too) |
| `pillared` | explore | during a dive, explore pillared rooms for a `>` without asking (`ask` = stop and ask; `ignore`) |
| `choke` | on | when a pack (3+) comes at you in the open, back into a corridor within 10 squares and fight them there one at a time (experimental) |
| `loot_radius` | 10 | during a dive, fetch items seen within this many squares (0 = never) |
| `pickup` | all | all or none |

Orders are remembered across pilot restarts.

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
- Avoid molds and jellies (stationary, not worth the risk). Uniques drop good
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
