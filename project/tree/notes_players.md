# What players know: digest of mangband.org/docs for the tool

Source: the mangband.org docs pages (site down; archive.org snapshot 2026-02-08,
`https://web.archive.org/web/20260208192212/https://www.mangband.org/docs`). Raw HTML and text
copies of every page are in `runs/docs/` (read on 2026-09-25). Claims marked **(code)** were
checked against the 1.5.3 source; the rest is player lore, not yet observed on the servers.

## Macros and inscriptions: what they really are

- **Macros run in the client only.** A macro is a string of keystrokes that the client replays into
  its own prompts. The server never sees a macro, only the packets the prompts produce. Tool mode
  has no keyboard prompts, so it doesn't need macros. It needs the *packets* each macro produces,
  sent as one command.
- **Inscriptions `@<cmd><digit>` choose the item, and that is resolved in the client too (code:
  `c-inven.c:140-190`).** `q1` means "the item whose name contains `{...@q1...}`, else `@1`". The
  tool can do the same from the `inven` names, so it never depends on inventory order (which changes
  all the time). Plan: inscribe the throwaway's key items once (e.g. `@q1` Cure Light Wounds,
  `@r4` Phase Door, `@r5` teleport, `@f1` ammo, `@w1`/`@w0` swap weapons, `@E1` rations) and
  address them by tag.
- **`*t` = target the closest enemy (code: `c-cmd.c:845`, server `xtra2.c:4357`).** The client sends
  `PKT_LOOK(NTARGET_KILL, 0)`, and the server sorts the targetable monsters by distance and points at
  the nearest. Then `PKT_LOOK(KILL, 't')` selects it. A later command with **direction 5** uses the
  target. So a tool `target` command is two packets, with no look-mode dialogue to manage.
- **Order matters.** Spells take the target *before* casting (`\e*tm1a`), while missiles and fire take
  it *after* (`\ef1*t`, i.e. at the direction prompt). Either way, the packet is the command with
  `dir=5` once a target is set.
- **`\e` first** clears pending prompts. The tool equivalent is to never leave prompts pending; C
  already answers every prompt with ESC.
- **Inscriptions that change server behaviour (code for `!O`/`^O`):**
  - `!O` on the weapon or `^O` on any worn item turns **auto-retaliate** off.
  - `!g`, `!*`, `!k`, `!s`, `!d` protect an item from pick-up, everything, destroy, sell and drop.
  - `=g` picks ammo up automatically.
  - `@R450` makes Word of Recall go to 450 ft.
  - `^x` on worn gear blocks command x.

## Auto-retaliate: the server fights for you (code: `server/dungeon.c:777,1036`)

When the player has spare energy, is not confused or afraid, is **not running and has no queued
command**, the server itself attacks a visible adjacent monster (it prefers the current health-track
target, otherwise it picks one at random). Consequences for the tool:
- **Standing still next to a monster is fighting it, at the full blow rate.** For a 4-blow warrior
  that beats bump-attacking with walk commands: each walk queues a command, which suppresses
  auto-retaliate.
- To fight, **stop sending commands** and watch the messages and HP. To flee, move, since a
  queued command wins over retaliation.
- `shopcat.fight()` (walk into adjacent letters) should become "stop moving, let the server
  retaliate, step in only if nothing happens".

## Movement

- Running (`.`/shift+dir) **follows corridor bends until a choice point or a disturbance**. Humans
  run corridors almost exclusively (user). No auto-explore exists.
- Disturb options (server `tables.c:2606-2624`, all default ON): `disturb_move`, `disturb_near`,
  `disturb_panel`, `disturb_state`, `disturb_minor`, `disturb_other`. These decide what stops a run
  or rest. They are free interrupt signals, so leave them on.
- Other options that matter: `always_pickup` (default ON in this build?), `pickup_inven`,
  `easy_alter` (open doors and disarm traps by walking into them), `auto_scum`.
- The alter command `+` picks tunnel, disarm or open for the feature. Tunnel is `T` (ctrl+dir). Bash
  jammed doors with `B`. Close doors with `c` (many monsters can't open them).
- Secret doors: search `s`, or search mode `S` (which doubles the time per move). Typical places:
  dead ends, a lone door in a corridor, intersections, corners with doors. Never diagonal. Give up
  after a while. That makes a sensible "level exhausted and no `>` found" routine.
- Stairs: every dungeon level has ≥1 up and ≥2 down staircases (town: one `>`). **Levels are not
  persistent**: leaving loses the level. So stair-scumming (take any stair, up or down, to get a
  fresh level) is a legitimate escape and reroll.

## Survival lore (for the Phase 3 rules)

- Escapes, in order of use:
  - Phase Door (up to 10 squares);
  - Teleport (across the level, maybe into worse trouble);
  - Teleport Level;
  - Teleport Other (removes the monster);
  - *Destruction*;
  - Word of Recall (activates **~50 turns after reading**, so it is not an emergency escape).
- Healing (code-checked, Advisor memo Erratum): CLW 15 HP, cures blindness, only reduces confusion
  and cuts; CSW 20-24 HP, cures blindness, confusion and cuts; **only CCW (25-29 HP) and better cure
  stun and poison** (Cure/Neutralize Poison potions also cure poison). Healing restores 300 HP. Carry CCW once confusers appear. Scrolls can't be
  read while blind or confused. Staves can be used blind or confused (but may fail).
- Depth checkpoints: **1000 ft (DL20): Free Action and See Invisible** (paralysis kills, e.g. Carrion
  Crawlers); 1250 ft: the four basic resists; 1900 ft: confusion and blindness resistance; 2000 ft:
  poison resistance. A rules agent should cap its depth by the gear it has. **Corrected by the
  Advisor's danger-table memo (2026-09-27, code-checked):** poison breath starts at 1000 ft (air
  hounds; Basilisk avg 103 at 1400 ft), so resist poison by ~1000 ft; blows that blind or confuse
  with no saving throw start at 800 ft (Umber hulk, Hummerhorn), and Brain Smash at 1400 ft (Mind
  flayer), so resist confusion/blindness is wanted well before 1900 ft (until then, CCW and a
  staff of Teleportation). Hounds: energy 900 ft; earth (shards), air (poison) and water (acid!)
  all 1000 ft; fire/cold 900; light/dark/clear 750; vibration/nexus 1350; gravity 1750.
- Town dangers: Mean-Looking Mercenaries and Battle-Scarred Veterans are only a threat to very weak or brand-new
  characters (user correction); otherwise town is safe.
- Starting kit (TANG): cloak, Brass Lantern and oil, soft armour (boots, cap, gloves), **Phase Door**.
  Shops restock every 1000 game turns.
- Monster colour lore: the *name* colour (White, Red, Blue, Black, Green/Yellow, Multi-Hued) hints at
  cold, fire, electricity, acid, poison or all of them. That's another reason to decode race names.
- Level feelings (Ctrl-F repeats) hint at danger and loot. "Special" usually means an artifact.
  They need some time on the previous level.
- Death: you become a ghost and can resurrect at the Temple (shop 4) or be rescued with a Scroll of
  Life. The equipment drops where you died. A killed ghost is dead for good. **Resurrecting halves
  the experience permanently** (`exp` and `max_exp`, xtra2.c:2867; Restore Life Levels can't bring
  it back; memo Erratum).
- Uniques are per character (memo Addendum 3): every new character meets the early uniques (Grip,
  Fang, Bullroarer, Wormtongue, Grishnákh, Azog) whatever others have killed.
- Speed: +10 = one extra move per normal-speed turn.

## Warriors and blows (user's throwaway build, backed by the guide)

- Blows depend on weapon weight, STR and DEX. DEX and STR over 18 plus a light weapon (Whip,
  Dagger) give several blows. Check blows on the `C` screen.
- **+to-dam applies per blow**, so enchant-to-dam scrolls on a 4-blow weapon pay off (user).
- The user's build: **Half-Orc Warrior, stats DEX > STR > CON > WIS > CHR > INT, light weapon for 4
  blows, read +dam scrolls on it.** Half-Orc: +2 STR, +1 CON, resists darkness, 30 ft infravision,
  bad stealth and searching (so secret doors are hard to find, which argues for stair-scumming over
  exhaustive searching).
- **Short of gold for an urgent purchase (the user, 2026-10-07): kill townspeople.** Drunks,
  merchants, rogues, mercenaries and veterans drop gold; it's faster than a short money dive and
  doesn't burn a Word of Recall. Few are visible from the shop-front streets: sweep the town in a
  zig-zag grid (the Pilot's `goal townfarm`).
- **Outfitting a new warrior (the user, 2026-09-28):** sell the starting Broad Sword and Chain Mail
  at once: they fetch a lot compared with their use. Buy a **Main Gauche** instead, plus Enchant
  To-Hit and To-Dam scrolls (especially discounted ones) for it, and cheap unenchanted armour for
  every empty slot: cloak, gloves, boots, leather shield, cap. These give good AC for the price.

## Chat (for the live server)

`:` sends to #public; `Name: text` is private; `&say:` reaches line of sight; `&yell:` reaches the
whole level. **User rule: the tool never uses chat. If a player talks to Sneezy (or any tool
character), ignore it.**

## Changes to the Phase 1/2 plan

1. **1.5 look/target shrinks** to `target` = `PKT_LOOK(KILL,0)` + `PKT_LOOK(KILL,'t')`, reporting
   `target_info` text (which says what was targeted, or "Nothing to target"). Commands then use
   `dir=5`.
2. **Item addressing by inscription tag** in Python (`use q1`, `use r4`), mirroring `c-inven.c`, plus
   a one-time inscribing step for a new character (`{` custom command with `entry=@q1`).
3. **Fighting uses auto-retaliate**: the Mover's "engaged" state stops issuing commands and watches
   messages and HP. Moving is how you disengage.
4. **Explore**: run corridors (the server follows bends), frontier goals for rooms. When the level is
   exhausted: search likely spots briefly, else take any stair (up or down) for a fresh level.
5. Interrupts can lean on the server's disturb logic (a run stopping *is* a disturbance), plus our
   own checks.

---

# Observed human play: session 1 (2026-09-25)

The user played Dive03 (fresh Half-Orc Warrior, starting kit unworn) on the local server for 32
minutes: outfitting in town, then a dive from 50 ft to 500 ft, with commentary in chat. Recorded
with `tools/observe/record.py`. Data: `runs/observe/session1/` (`timeline.txt` is the merged,
readable log from `tools/observe/timeline.py`; `screen.py SESSION MM:SS` shows the screen at a
time; the user's saved options are in `options.prf.user`). Times below are session times (MM:SS).

## Outfitting (02:30–12:30, ~10 min)
- First: wield/wear the kit (the server's **auto-retaliate** kept hitting Farmer Maggot meanwhile,
  and killed him). Picked up the unique's drop (a shield).
- **Sold the starting Broad Sword (115 g) and Chain Mail (385 g)**: "they are expensive and we can buy
  a lot with the money". Selling = `s` + item + `y` at the confirm. The tool will need a yes answer.
- Bought, in order:
  - General Store: Brass Lantern and a flask of oil (lantern on sale), then a ration and a Cloak;
    sold the torches.
  - Armoury: Leather Gloves, Metal Cap, Hard Leather Armour.
  - Weaponsmith: **Main Gauche (1d5)**: "I want a gauche".
  - Alchemist: 6 Phase Door, **2 Enchant Weapon To-Dam** (read at once: "we get so many attacks,
    +dam to weapon is good").
  - Alchemist again: 2 Identify (75% off).
- Wore everything, swapped Chain Mail for Hard Leather Armour (lighter), sold the Chain Mail.
- Inscribed the Phase Doors `@r1` and tried to make a macro for them. The action was typed as
  `/er1` (with `/`) instead of `\er1`, bound to `5`. Function keys don't reach the client in the
  SCC terminal, which the user noted. In the emergency they typed `r1` by hand.
- **Mistake to learn from: sold all 7 rations** (14 g). See the starvation episode below.
- Price lesson: characters start with ~100 g plus a kit worth ~500 g when sold. Selling the kit
  funds a proper outfit.

## Diving (12:30–30:18, ~18 min): stair-scumming
- **90 level visits in 18 min; median stay 1.9 s.** 51 stays under 3 s, 13 of 30 s or more.
  Reached: 50 ft 12:31, 100 ft 13:07, 200 ft 15:58, 300 ft 18:56, 400 ft 22:59, 500 ft 27:16.
- **Connected stairs**: taking `>` leaves you on an up staircase, and `<` on a down one. So `<` `>`
  `<` `>` regenerates the level with no walking ("stair-scumming, a quick way to dive").
- **The decision rule, from the screens**: on arrival only the lit room is visible. If there's no
  `>` in view, scum at once. If a `>` is visible nearby, run to it and take it. "Map areas that look
  like this [pillared rooms, `#.#.#.#`] often have up and down stairs."
- He also picked up items in view on the way (potions, scrolls, wands, rings, weapons), killed what
  was adjacent, and moved on.
- **Risk he named**: "a pack may generate on the stairs and shove you off, leaving you with no quick
  retreat". It happened at 25:22 (below).

## Movement
- 329 run commands and 189 walks while diving. Runs are typed as shift+direction. The client's
  default macro turns that into `\.4` etc. (the `\` bypasses keymaps). **Held keys**: the same run
  repeated up to 35× in a row. Every time the run is disturbed, the held key restarts it. Humans
  don't "plan" a run; they lean on the key.
- Walks were for the last few tiles to stairs and items, and for stepping onto items to pick them
  up (`,`; `always_pickup` is off).

## Fighting
- **78% of melee blows (183 of 236) came with no command from the player in the previous 0.6 s**:
  auto-retaliate. Typical: run into a group (Jackals, a pack of Novice priests or rangers) and stop.
  The server kills them one after another while the player does nothing. With 4 blows and
  +dam it's fast.
- Rest (`R`, then Enter = "as needed") after fights. HP climbs ~3/0.2 s at clvl 10, so a full rest
  takes a few seconds. In the middle of the Novice-ranger fight, resting was interrupted by arrows
  from an unseen archer.
- Avoid: "Not worth fighting molds and jellies if you can avoid them" (stationary, no reward for the
  risk). Blue icky thing → fear + poison + shriek ("a pit of nope"): left by the stairs immediately.

## The near-death (25:22–25:40)
- Took `<` into a pack: several Large kobolds and Kobold shamans (magic missile, curses, confusion).
  HP fell 126 → 38 in ~9 s while he fought via auto-retaliate.
- He read Phase Door three times (`r1`), which didn't shake them, and quaffed Berserk Strength
  (+to-hit, heals a bit, raises max HP). Then he got **confused**, HP reached **16/175**, and he
  **took `>`**: he was standing on a staircase again, which saved him. Confusion doesn't stop you
  taking stairs.
- Lesson for the rules: after arriving by stairs, **a pack in view at arrival means leave by the same
  staircase at once**. It's the cheapest escape available, and it's under your feet.

## Items and identification
- Picks up nearly everything in reach; pseudo-ID ("You feel the Small Sword is average") flags junk,
  which he destroys with `k` + `y`. "Rings and amulets are usually bad this shallow": read Identify
  on one, and it was a Ring of Aggravate Monster {cursed}, destroyed.
- Identify goes to a unique's drop first (Bullroarer's Soft Leather Armour).
- Wielded Bullroarer's Long Bow (x3) in the bow slot without any ammo: free stats and a later option.
- **Pack full** twice ("Out of space, make room"): destroyed average weapons; later **quaff-ID'd
  unknown potions to free slots**. That gave Salt Water (vomit → instantly "faint from hunger") and
  Weakness.

## Starvation (29:45–31:36)
- With no food (sold in town) and Salt Water's hunger drain, he **fainted from hunger repeatedly**:
  paralyzed for about a second each time, roughly every 3–10 s, still in the dungeon. That could kill
  a character near monsters.
- He read Word of Recall (~13 s until activation), was pulled to town, bought 2 rations, ate.
- Lessons: always carry food (≥ 3–5 rations); don't quaff unknown potions without food in the pack;
  "Weak"/"Faint" means eat now, or recall.

## Session facts (checked in the data)
- Level feelings ("Looks like any other level", "You like the look of this place...", "special")
  come with each new level. He didn't act on them visibly.
- `I see no down staircase here.` 6 times: a stair key pressed right after arriving (sometimes on the
  wrong type), or after being pushed off the stairs.
- Your screen showed only the ~60×20 panel around the character (80×24 main term); the tool sees the
  whole 198×66 level. A human decides from much less map.
- **The "laggy keys" complaint.** I checked two causes and ruled both out:
  - Per-record log flushing: writing to /projectnb costs ~1 µs per record (NFS client caching).
  - The client or the recorder: with keys injected every 35 ms, the client consumed them every 35 ms,
    whether screens were captured every 0.2 s or every 30 s.

  In the session, held keys reached the client only every ~0.2 s (p50 0.16 s). The delay is
  therefore upstream of tmux: the terminal or ssh / web-terminal path.

## What changes for the agent
1. **Dive strategy = stair-scum**, not exploration: arrive → if `>` visible and reachable, run there
   → else `<` then `>`. Explore only when needed (stuck, loot, XP). This makes frontier exploration a
   secondary tool. It's still needed when no stairs are on hand (after teleport, or pushed off the
   stairs).
2. **Arrival check** before anything else: monsters in view (a pack, or dangerous kinds) → take the
   same staircase back immediately (connected stairs guarantee one under you).
3. **Fight by standing still** (auto-retaliate). Move only to disengage, reach stairs, or pick up.
4. **Escape order in practice:** stairs under you > Phase Door > Berserk/CLW > recall (slow).
   Phase Door alone often doesn't get you away from a pack.
5. **Food and pack management are survival-critical**: keep rations, never sell all food, manage
   the 23 pack slots (destroy {average} weapons, don't hoard).
6. **Town routine**: sell the kit, buy lantern, soft armour pieces, a light weapon, Phase Doors,
   +dam scrolls, Identify. Needs the confirm-yes answer for selling (Phase 1.6).
7. Movement can be "hold the key": re-issue the same run when a run stops and nothing is in view,
   which is what a human does.

## The user's answers to my questions about session 1
1. **When to stop scumming**: stop for anything of interest: an interesting item, a possible vault,
   even a visible lit room (lighting reveals a fair bit of map, so more potential items). After
   going down, check whether the arrival room is one of the room types that often have stairs:
   **columns in the centre or along the edge** (the `#.#.#.#` pillared rooms). If so, explore it
   entirely for a `>`.
2. **Why he fought at 25:22**: he believed the pack had pushed him off the stairs, so fighting
   seemed the only option. In fact he was still on the staircase. **For the agent: always know
   whether you're standing on a staircase.** The map shows `@`, not the tile under it. Track it:
   arrived by stairs and position unchanged ⇒ on a staircase of the opposite type (connected
   stairs). Any move clears it; stepping onto a remembered `<`/`>` sets it. "I see no down staircase
   here." corrects it.
3. **When to stop just auto-retaliating**: HP below **60–70%**, or a kill taking longer than usual,
   means evaluate other actions. The most dangerous monsters are **summoners** (more monsters appear
   on top of you) and **packs that breathe or cast at range**. None appeared in session 1.
4. **Option changed at 15:07**: turned on the stacking option so identical items with different
   discounts/inscriptions share a slot (`stack_force_costs`, "Merge discounts when stacking";
   default off in the repo's options.prf). **The agent's characters should turn it on too**, since
   pack slots are the scarcer resource.
5. **Food**: pack space runs out before food does. Carry about one spare ration, and eat or discard
   it if space is needed. The starvation was bad luck (Salt Water), not a habit.
6. **Lag**: the user played in a terminal inside the same OnDemand session as the server (not ssh).
   So the lag is in the OnDemand web terminal path, not in the client or the recorder.

## Session 2 notes from the user (live, while making money with Dive03)
- Potions found early are usually bad: sell them (free identification plus a bit of money).
- Identified items sell for more, but don't bother identifying {average} gear: it sells the same.
- Sell what you won't use (Bullroarer's Long Bow: 353 gold).
- "Always best to retreat behind a turn, to let enemies trickle into melee range."
- Invisible monsters are usually annoyances, but one drained DEX repeatedly ("You feel very
  clumsy"), which cost a blow (4 -> 3). Restored with a Potion of Restore Dexterity from store 5
  (468 gold).
- Until the weapon is about +8,+8, buying discounted Enchant To-Hit/To-Dam scrolls is a good use of
  gold.
- (user) Breeders reproduce rapidly and overwhelm you if not culled quickly; they give no XP, so
  they're not worth farming. Kill them only while there are 1 or 2; otherwise leave the area.
- (user, session 3) Per item, identifying with a staff is cheaper than Identify scrolls, especially
  recharging it with Recharge scrolls after the initial purchase of the staff.
- (user, session 3) Empty amulet slot: buy the (Amulet of) Slow Digestion at a deep discount, so the
  current ring of Slow Digestion can go when two good rings turn up. Fill empty equipment slots
  cheaply, and keep slots flexible.
- (user, 2026-09-26) **Afraid**: if not in danger, don't spend consumables to cure it: kite (stay out
  of the monsters' reach, circling in a known safe area) until it wears off. Monsters that fear you
  over and over will fear you again as soon as it drops: more trouble than they're worth, so walk
  away (not dangerous) or phase away (dangerous); they can be catalogued in advance. Kiting into
  unknown areas piles on more monsters: retreat into already-cleared areas.
- **Out of combat, don't drink potions for HP: rest (`R`) instead** (user, 2026-09-27). Potions are
  for when something is hitting you.
