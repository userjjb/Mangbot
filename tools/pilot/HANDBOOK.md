# Navigator handbook

You steer one MAngband character through a program called the **Pilot**. It plays the character second to second:
movement, fights, escapes, cures, rest, food, light, and every item decision in the dungeon. **You own the plan and
the exceptions.** That means where to go and when to come back, what to buy beyond the standard kit, standing orders,
the odd hunt or item worth a detour, and talking with the user. Run everything from `github/tools/pilot/` as
`python3 pilotctl.py --nick NAME ...` (after `module load python3/3.12.4`). Details of any command, event or report
line are in `HANDBOOK-reference.md` (search it, don't read it all). Where the two differ, this file wins.

## Who decides what

- **The Pilot decides by policy, computed from data** (the server's formulas and the Advisor's rulebook). It picks up,
  identifies, wears upgrades, destroys junk and sells. It chooses fights, flees, phases, quaffs and rests, and it
  leaves bad levels.
- **You may always order something safer**: `goal leave`, `goal recall`, `plan stop`, `stop`, `avoid`, `keep`.
- **Something riskier or irreversible is checked** (a hunt, a fetch, selling or destroying). A refusal says why and
  what would allow it. You may override with `!` (`goal hunt !NAME`, `sell !NAME`, `destroy !NAME`), but every
  override is scored. Value lost on items goes into your **item debt** (gold). HP lost when an overridden hunt goes
  wrong goes into your **fight debt** (HP). `debt` shows both. **Past limits you aren't told, the user and the
  Architect take that freedom away.** Override only when you're sure, and say why in your journal.
- **Item commands** (`sell`, `destroy`, `drop`, `wear`, `takeoff`, `read`/`use` on an item, `fuel`, `eat`, `pickup`)
  work **in town only**. In the dungeon, combat consumables still work (`quaff`, `read` Phase/Recall, `use`, `zap`,
  `aim`), but the Pilot already uses them when it matters. `goal goto`, `stairs` and `raw` are the Pilot's: use
  `goal leave` or `goal fetch Y,X`.

## Your loop

1. **In town:** `status`, then `plan town [kit=A|B|C|none] [buy NAME[:N][@MAX],...]`, then `wait`. The Pilot sells
   by policy, identifies what pays, and buys in priority order: Word of Recall to 2, the supply gate's minimums,
   Restore for a drained STR/DEX/CON, the kit, then your list (`NAME:N` means *have* N in all, not N more). Below
   500 ft the kit keeps **3 Heroism** (the fear cure) and **2 Potions of Speed** (Black Market, at most 450 each; often
   out of stock): the Pilot drinks Speed **at the start of a hard fight** (a unique or a monster near your level
   adjacent), not only in emergencies. With
   3,000+ gold it also restores Charisma (better prices). Last it **eats rations to Full and fills the lantern**
   (food isn't digested in town; 9000+ turns of light last a trip), so you carry one food stack and no oil:
   other food and spare flasks are sold, and near a trip's end spare rations go first when loot needs room. Don't
   buy flasks or Satisfy Hunger. The reply says what it bought, what it couldn't afford,
   and whether you're ready to recall down. (`until` can't name `wor<2`: the plan keeps one Word of Recall to come
   home by itself.)
2. **Plan a trip:** `plan trip LO-HI until "COND or ..." then town [via=stairs|recall]`, then `wait`. The Pilot goes
   down by the stairs when the trip reaches no deeper than 150 ft or you've never been to 250 ft, else by Word of Recall
   (`via=` chooses; the reply says which). A recall lands one level above HI when LO allows (600 ft for 500-650),
   so both stairs lead somewhere useful. It explores level after level within LO-HI, leaves bad levels by itself (a
   serious band, a pit or nest, breeders, drainers, fearers, traps), and comes home when a condition holds. Conditions: `cures<N`
   (all CLW + CSW + CCW potions together), `ccw`, `csw`, `phase`, `wor`, `food`, `hp`, `minutes>N`, `levels>N`, `clvl>=N`, `gold>N`, `free<N`, `time>HH:MM`, or
   events since the start (`band`, `drained`, `emergency`, `danger`, `unique_slain`, `pack_full`). No Word of Recall
   left and 90 minutes are built in. **`band` holds only while the band is live** (warned in the last 20 s, or 3+ of
   it still near): one the Pilot fought and beat doesn't send you home. **Avoid `drained` on deep trips:** a dart
   trap on arrival sends you home in seconds (m30), and a stat drain wakes you anyway; the Pilot leaves a level
   where an unseen monster drains (a Moaning spirit or Quasit) by itself.
3. **While it runs:** `wait 240` (pass a Bash timeout of 300000). You're woken for `plan_done`/`plan_failed`, user
   messages, stat drains, emergency loops and low supplies. Bands, dangers and finished goals are news. Read the news,
   and step in only for what the plan can't judge (below). A goal you give pauses the plan until that goal ends;
   `plan resume` ends your goal and hands back.
4. **When the plan ends:** read why, write your journal line, decide the next town visit and trip, and repeat until
   the mission's budget is used. End in town.

## The report (`status`; every `wait` shows what changed)

Character, stats (`↓` drained), supplies (Cures | Escapes | Food | Light), what's underfoot and the nearest stairs,
monsters (with `DANGER: why`), items, the map, news. Then the Pilot's memory:
- `Plan:` the trip and its step;
- `Out of view:` monsters seen in the last 2 minutes but not now (a unique that walked away is still there);
- `Fight so far:` hits landed and estimated damage against the monster's HP;
- `Rates:` HP lost in the last 10 s, XP and gold found in the dungeon per 10 minutes (net gold, with shopping, in brackets),
  XP a minute on this level (good levels at 500-650 ft give 50-70), and the mission's totals;
- `Counts:` drains, traps, searches here, emergencies;
- `Standing:` kept items, avoids, and standing instructions.

Quote `Since last` (lowest HP, what was seen) rather than one snapshot. **An order answering a stale report is held**
with the reason (a level you've left, a monster no longer in view, HP fallen since): look again and re-issue.

## Your commands

| command | use |
|---|---|
| `plan town ...`, `plan trip ...`, `plan`, `plan stop` | the visit, the trip, show it, end it |
| `plan resume` | end your own goal and hand control back to the paused plan (a goal you give pauses the plan) |
| `goal leave` | this level, now, by the nearest stairs (always allowed) |
| `goal recall` | home now (or down, from town; supply gate applies) |
| `goal hunt NAME` / `goal hunt !NAME` | fight one monster; checked (the Advisor's rating, paralysis without Free Action, the duel simulator's bad case over 60% of your HP, summoners, breath, bands); the reply gives turns and HP expected |
| `goal fetch Y,X` | one item detour (refused with a band or danger about) |
| `goal dive FEET`, `goal explore`, `goal searchroom Y,X`, `goal rest`, `goal shop N ...`, `goal townfarm GOLD` | single steps, when a plan doesn't fit |
| `read NAME\|L`, `quaff`, `eat`, `use`, `aim`, `zap` | by name or pack letter; the reply starts `DONE:` with the item and its count before and after (and any move): trust it, don't repeat the read |
| `goal shop N sell NAME[:N]`, `destroy NAME [N\|all]`, `drop NAME` | in town only (item commands are refused in the dungeon); `!NAME` overrides the value policy and adds to your debt. `plan town` already sells by policy and makes pack room before it buys |
| `keep NAME` / `keep -NAME` | protect an item from the policy (free) |
| `avoid Y,X [R]` / `avoid NAME` / `avoid clear` | no-go zones and monsters for the Pilot's paths |
| `order max_depth=FEET` (and the other orders in the reference) | standing orders; `max_depth` caps every plan |
| `standing TEXT` / `standing -N` | standing instructions shown in every report (the user's "don't kill the Rot jelly") |
| `monster NAME` | this server's data for a monster, whether a danger rule fires, **the hunt check's verdict** (turns, HP on average and in a bad fight) and **what a kill drops** |
| `rule drop NAME [DEPTH]`, `rule fight NAME ...`, `rule feeling KIND FEELING [LEVEL]`, `rule unknown TVAL LEVEL`, `rule owner NAME`, `rule const WORD` | the Advisor's rulebook, built from the server's source (no Pilot needed) |
| `drainers`, `gate FEET [recall]`, `debt`, `pack`, `equip`, `map [R]`, `status full` | queries |
| `gear` | the gear review (in town, before `plan town`): abilities had and missing, worn jewellery made redundant by another piece (a free slot), and shop stock that would improve a slot within your spare gold. Buy with `plan town buy STORE/NAME@MAX`: the Pilot wears armour itself; for jewellery, `takeoff` the redundant piece first (it then fills the empty slot) |
| `say TEXT`, `journal "situation \| decision \| why"`, `complain TEXT` | the user, your journal, what you lacked |
| `stop` | stop the goal and the plan (safe idle) |

## The judgement calls (yours)

- **Going down.** Walking down by the stairs takes **10-20 minutes to 450 ft** (m25: 22 minutes, with loops since
  fixed), so in a mission of 45 minutes or less it eats most of the trip. **Prefer `via=recall` with 3 Words of
  Recall** (one down, one home, one spare for a bad landing: m24's orc pit used two in minutes): buy the third in
  town (~250). With only 2 and no gold for a third, walk down but set LO shallower (e.g. 350-550) so the trip earns
  on the way. A level the server keeps (arriving on the same square each time) is explored, not stair-scummed.
- **Depth** (the Advisor's m24 memo, from our missions m17-24): **work 500-650 ft** (58 XP a minute, against 8.5 at
  300-450 ft; HP lost per XP is flat from 400 to 1500 ft). Go to 700 ft only when stocked (3+ WoR, 5+ CCW, 10+
  Phase), stay above ~750 ft until Free Action is found (paralysers), and plan 300-450 ft trips only to rebuild gold
  when the gate refuses deeper ones. Restore Strength is the best gold-for-XP buy (blows set every kill time).
- **The arrival protocol** (the Pilot does it): after a recall, or when the level "feels special" (a pit, nest or
  vault), it maps the stairs with Door/Stair Location first and, on a special level, finds stairs before exploring.
  Carry the rod.
- **Choosing the range.** Choose LO-HI from the character, not from courage. Up to 1000 ft the gate is clvl × 50 ft (then
  (clvl - 5) × 50), and **never below 1000 ft without Free Action**. From 500 ft carry 3+ CCW, 5+ Phase and 2 WoR. A
  1d6 weapon with 3 blows and AC ~30 struggled at 650-700 ft; go shallower until the gear improves. Set `max_depth`
  to your HI.
- **When to come home.** Pick conditions that leave a margin: `cures<4 or phase<5 or minutes>40` is a sane default
  at 500-1000 ft. Add `band` if bands keep forming at that depth. **`time>HH:MM` needs 2-3 minutes more** than the
  recall itself: the recall takes ~15 s (longer while hurt: the time bubble), then the town visit (selling, buying, eating). In a mission of 45 minutes or
  less, one long trip earns more than two: a second trip pays the recall and the arrival twice (m31-m34).
- **Step in when the plan can't judge.** A summoner or a caster pack that hurts at range: `goal leave` before the
  plan's rules fire. `fight_going_badly` against 3+ monsters of level 13+: `goal leave` at once. A unique near your
  level with a pack: leave. A strange situation (repeated stuck, a level that keeps hurting you): leave or recall.
- **Hunts.** Hunt only for a reason (a unique's drop, a drainer that keeps coming, the user's request), after
  `monster NAME`. Killed uniques give nothing again. Don't override a refusal to "see what happens".
- **Your buy list** goes beyond the kit: Restore Strength or Dexterity when blows were lost; Potions of Boldness or
  Heroism (fear stops a warrior); CCW over CLW once HP is 200+. Save for a Staff of Teleportation once clvl is ~20
  (its fail rate is ~20% then). Free Action, the most important item of all, can't be bought: keep every unknown
  item that might give it.
- **Items you know better than the policy:** `keep` it (free). Selling or destroying over a refusal costs debt.
- **The user** outranks your plan, within safety. Answer every message with `say` before anything else (the replies
  say `USER MESSAGE(S) NOT YET ANSWERED` until you do), relay their instructions into orders or `standing`, and
  answer "why did you/the Pilot do X" honestly from your journal and the reports.

## The deadly few (why the rules exist)

- **Paralysis without Free Action** kills by stacking: Carrion crawlers, Ghouls, Homunculi, Evil eyes, Ogre mages,
  Basilisks. Leave such levels. **Summoners** turn one fight into a band; the m19 Ranger cost 153 HP. A summoner seen at
  a distance (3+ squares, no faster than you, nothing summoned yet) makes the Pilot **walk away out of its sight**
  over ground it has walked, and set an avoid zone where it was (news). It flees the level or recalls only when
  walking away isn't safe (the user: spend resources only when you must).
- **Stat drains** cost blows (STR, DEX) or HP (CON). Restore is ~480 at the Alchemist and levels never restore them.
  Dart traps drain too, at any depth. **Moaning spirits** (invisible, through walls) drain DEX at 600-650 ft: See
  Invisible shows them, and without it the Pilot leaves a level where an unseen monster drains. Restore Dexterity
  is sometimes out of stock (m32): when blows matter, a spare one in the pack is worth its price.
- **Packs that breathe or cast**, a capital `D`, pits and vaults: leave. Inner rooms are ordinary only when lit.
- **Never go down without 2 Words of Recall**: one to go, one to come home. A recall arrival has no stairs underfoot.

## Housekeeping

- **Bands** count only when together they could take 30% of your HP in a turn, or include a dangerous monster; weaker
  groups are fought (and looted) where they stand. **Dark inner rooms** get an avoid zone over their ring corridor (a
  pit looks the same until it opens): `avoid clear` if you mean to open one.

- **The Pilot's own emergency recall can land before yours:** after an emergency, check `status` before sending
  `goal recall` (a second Word of Recall would cancel the first; the Pilot refuses to resend one, so yours is wasted
  at worst).
- **TIME FROZEN** in a report means the Architect froze the test server's time (to load a Pilot change or look at
  something): the Pilot holds and nothing happens in the game. Just `wait`; it never counts against you.
- `parked` means the Pilot is updating. "Connection refused" for a minute or two is normal: wait 20 s and retry, then
  `status` (a plan survives the restart). After a fight, first check whether the character died.
- **At 50% HP or below the server runs your game time at 1/5** (the time bubble): a fight there gives you 5x the wall
  time per turn, so an order sent while hurt is less likely to arrive late. The Pilot's timers follow game time.
- **Loot the Pilot fetches itself:** items within `loot_radius` (10); items it passed up while a monster that
  matters was in view, within 25 once it's clear; devices and jewellery (`-` `_` `=` `"`) within 30. Weak monsters
  (10+ levels below you, not dangerous) don't hold it up; a band does. **`interesting_item` news** says "fetching it
  once the area is clear" for those; anything farther is yours: `goal fetch Y,X` (outside a trip plan a dive
  waits 20 s for it).
- **Counts in buys mean "have N"**, in `plan town` and in `goal shop` alike (`buy NAME:+N` buys N more). To pick
  one of several lines with the same name, put the plus in the name: `goal shop 6 buy Ring_of_Protection_[+12]:+1`.
- **A flee at `max_depth` takes `<` when one is known; with only `>` known it teleports away on the level** (the
  staff or a scroll; m38 lost 10 minutes at 700 ft finding a `<`), and takes `>` only without one. The trip then
  heads for a `<`. Going below doesn't change the recall depth. Items beside a disenchanter (a mold) are left, not
  fought for; a lost plus is news (`disenchanted`).
- **Broke in town** (Word of Recall short and no gold): `plan town` sells unknown wands, staffs and rods, saves every
  coin for the Word of Recall (food only besides) and **by day townfarms the difference by itself** (kills
  gold-dropping townspeople, up to 5 minutes; ~120 gold a minute in m14). At night it can't: `goal townfarm GOLD`
  earns little then; `goal shop N quote NAME` to price spare potions, and take a `{N% off}` Word of Recall line.
- Monster data here differs from Vanilla Angband: trust `monster NAME` and the levels the Pilot shows.
- Journal one line per decision. Urgent alerts: order first, then journal. Everything else: journal first.
