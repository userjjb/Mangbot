# Pilot: combat and survival

The Pilot (`github/tools/pilot/pilot.py`, class `Pilot`) keeps the character alive on its own, second to second, without
waiting for the Navigator. Every tick (`Pilot.tick`, see [pilot-core.md](pilot-core.md)) first runs a fixed stack of
safety checks (the *reflexes*), then the Navigator's standing reactions (`react`), and only then the current goal. The
reflexes decide when to fight, when to drink or read something, and when to leave (stairs, Phase Door, Teleportation,
Word of Recall). A set of *watches* runs every tick as well: they act rarely and mostly tell the Navigator about trouble
before it costs anything. The Pilot does no hitting itself. A warrior fights by standing next to a monster, and the
server's auto-retaliate does the hitting. The Pilot decides where to stand and what to use.

Related: goals and the trip plan in [goals-and-plans.md](goals-and-plans.md); the hunt check, the duel simulator and
**shadow mode** (`shadow_decision`, `hard_fight_shadow`, `band_shadow`: the Advisor's estimator, consulted in the
background, never acting) in [gear-and-estimator.md](gear-and-estimator.md); `pilotctl` commands in
[commands.md](commands.md).

## 1. Where it runs in the tick

In `Pilot.tick`, in this order (one action per tick: the first step that acts ends the tick):

1. `confusion_lock` and then `confusion_window` (they run before anything else, even with no goal).
2. `supply_watch`, `verify_use`, `verify_effects`, `audit_tick` (bookkeeping; see §7).
3. The watches: `watch_character` (stat drains), `watch_weapons` (every 10 s), `watch_breeders`, `watch_drainers`,
   `watch_thieves`, `watch_kills`, `watch_band`, `watch_traps`, `watch_abilities`, `watch_progress`, `watch_perception`
   (§5; `watch_weapons` and `watch_abilities` are in [pilot-items.md](pilot-items.md)).
4. Navigator requests are handled (`handle_requests`). If the test server's time is frozen, the Pilot holds here.
5. **`reflexes()`** (§2). If it returns True, the tick ends here. While parking for a Pilot update, `park_tick` runs
   next and ends the tick (unless a `Recall` goal runs).
6. **`rule_tick`**, the Navigator's `react` rules (§4).
7. `look_tick` (never acts: asks the server which monsters are asleep), `policy_tick` (item work, see
   [pilot-items.md](pilot-items.md)), then the goal (`step_goal`) and the trip plan.

`step_goal` itself makes the character wait while it is blind or confused during Explore, Search or Dive. When a goal
named `flee…`/`leave…` fails, it calls `flee_failed` (§3.4).

## 2. The reflexes (`Pilot.reflexes`), in priority order

Here and below, "within N levels of ours" means a monster level ≥ ours − N: higher monsters count too.

| # | Step | Trigger | Action |
|---|---|---|---|
| 0 | Death | HP ≤ 0 or ghost | Stop everything; `dead` alert. Nothing else runs until `goal resurrect` is given (goal `Resurrect`). |
| 0 | Busy / store | an action is still on its way (`busy_until`); inside a store during a `Shop` goal | Busy: hold. Store: skip the rest of the reflexes, so the `Shop` goal carries on (any reflex command would leave the store). |
| 1 | **Emergency** | HP < `flee_hp` (0.5), **or** "hard": HP ≤ the adjacent monsters' worst melee over our next 3 turns (`worst_3turns`) while HP < 90%; and a monster is within 7 squares or we were hit in the last 5 s | `escape(why)` (§3). If it had nothing to do this instant, the mover stops anyway (unless it is escape's own walk to stairs): the goal never takes over during an emergency, because a new walk would wipe the queued reads. |
| 2 | **Group danger** | `group_tick` (§2.1) | Retreat, stairs, flee, recall, staff or phase, by tier. |
| 3 | Hard-fight start | `hard_fight()`: a unique or a monster within 5 levels of ours adjacent, or 2+ adjacent at < 75% HP | `speed_start_tick`: a Potion of Speed (not if already fast; once per 30 s). Then `berserk_tick`: Berserk Strength (same test, once per 30 s). `hard_fight_shadow` logs the estimator's view first. |
| 4 | Status cures | `status_tick` (§2.3) | The cheapest potion that cures stun, confusion, blindness or poison. |
| 5 | Arrival into danger | < 6 s on a new level, standing on stairs | Take the stairs back if `arrival_pack` (4) monsters within 5 levels of ours are within 7 squares, or a danger (`danger_why`) is in view (with `danger` in `stop_on`). `danger_avoided` news. |
| 6 | Danger in view | a monster that `danger_why` flags, within 12 squares (or listed by the server but not yet on the map) | **Exception:** slow casters with weak melee (no faster than us, average and worst melee < HP/8) and stairs > 8 away are *not* fled: walking away gives them free casts (`danger_seen` alert says "fight it or recall"). **Summoners only**, HP ≥ 50%, 3+ squares away, no faster, nothing summoned yet, and walking away hasn't failed on this level (`walk_away_ok`): goal `WalkAway`. Otherwise goal `Flee` (`danger_seen` alert). There is a 10 s gap between flees. The flee is skipped if the Navigator ordered a hunt in the last 2 minutes (`hunt_ordered`). If a flee just failed, `flee_failed` runs again. A summoner listed before its map position is known gets up to 1.5 s for the map to place it. |
| 7 | Unseen attacker | `unseen_tick` (§2.4) | Flee to known stairs, or advise a recall. |
| 8 | Choke point | order `choke=on`; 3+ monsters within 5 levels of ours, within 10 squares; we're in the open, not on stairs, not fleeing | `choke_tick`: walk to a corridor square (best `choke_tier`) within 10 steps, further from the pack's centre, and hold it up to 25 s so they come one at a time. |
| 9 | Summon trap | "You are enveloped in a cloud of smoke" in the last 2 s, not blind or confused | Phase Door at once (`@r1` first; `emergency`). |
| 10 | Slowed | our speed makes monsters act ≥ 2× (`our_slowness`), in melee or hit in the last 2 s | Potion of Speed (once per 40 s). |
| 11 | **Afraid** (a warrior can't melee) | afraid, a monster within 7 | Just arrived on stairs among 2+ monsters: take the stairs back. Not in danger (HP ≥ `think_hp`, no danger, < 2 adjacent, damage < 2% max HP/s): kite with `retreat_step` over ground already walked. In danger: `fear_cure` (Heroism > Boldness > Berserk), else teleport if `react afraid teleport` is set, else Phase Door if a monster is adjacent. |
| 12 | Stationary monsters (molds, jellies, eyes) adjacent | NEVER_MOVE adjacent, not the hunt target | `stairs_beside_still`: the wanted stairs are a step away and these monsters are harmless for one turn, so take the stairs. `still_fight_tick` (§2.5): kill it if it blocks the way and is killable, or flee a strong disenchanter. Otherwise step away (`retreat_step` reach 6, else `sidestep`). |
| 13 | Repeat fearers | a mobile monster that frightens again and again, within 7; not during Flee or Recall | `fearer` alert once per level; Phase Door if it is within 2 levels of ours and any monster is adjacent (every 2.5 s at most); otherwise retreat. |
| 14 | Light | `town_light`, `keep_light` (§5) | Skipped with a monster adjacent, **unless we have no light at all** in the dungeon. |
| 15 | Hunger | hunger ≤ 2 (Hungry), nothing in view for 5 s and not hit for 5 s | Eat (once per 10 s). No food: read Satisfy Hunger only when Weak (≤ 1), because it fills you to Gorged. Neither, and Weak in the dungeon: goal `Recall` (`low_supply`). |
| 16 | **Adjacent monster** | any adjacent | Stop the mover (except during Goto/Flee) and stop resting. Below `think_hp`: `fight_going_badly` alert (once per 10 s). With 2+ adjacent and one a thief (EAT_ITEM/EAT_GOLD blows), hit the thief first (item thieves before gold thieves). Otherwise hold, so auto-retaliate fights. A Goto or Flee goal keeps moving instead. |
| 17 | Pickup / auto-destroy | standing on an item | Belongs to the item policy ([pilot-items.md](pilot-items.md)). While fleeing (Flee, BandLeave, WalkAway) with monsters in view, only items worth 500 or more are picked up. |
| 18 | **Engage** | `engage_tick` (§2.2) | Walk to a weak monster a few steps off and fight it. |
| 19 | Rest | HP < `rest_below` (0.7), nothing in view, not recalling | Rest. It stops at `rest_to` (0.95) or when a monster appears, and goes on resting until `rest_to` once started. |

### 2.1 Group danger (`group_danger`, `group_tick`)

`group_danger()` adds up the worst-case melee of every mobile monster that can reach us this turn (max blow dice ×
speed, × `our_slowness()`; +200 for a paralysing blow that beats ¾ of our AC when we lack Free Action). If more HP was
actually lost over the last 3 s, that figure is used instead. Tiers, against **current** HP:

| Group worst | Action |
|---|---|
| ≤ 0.3× | nothing |
| 0.3–0.6× | Arrived < 6 s ago and on stairs: take them back. Else, during Explore/Hunt/Goto/Dive with nothing adjacent and nothing faster within 6: `retreat_step` (a `tactic` notice once per group). |
| > 0.6× | On stairs: take them (`danger_avoided`). With a monster adjacent and a Phase Door: phase once HP < `think_hp` (or above 1.0×), at most every 10 s. |
| > 1.0× | Goal `Flee("a dangerous group")` if stairs are known. No stairs within 25: read Word of Recall now. Blind or confused with a monster adjacent: Staff of Teleportation (once per 10 s). |

### 2.2 Engaging on the way (`engage_tick`)

While exploring or diving (or with no goal), the Pilot detours to fight a mobile monster 2–7 steps off. The monster must pass the hunt
check (`hunt_refusal`; result cached per level and name). It must not be a breeder, on the `avoid` list, or more than
20 levels below ours. The Pilot does this only when all of these hold: HP ≥ `think_hp`; no live band (`band_live`); not
blind, confused, afraid or slowed; no recall pending; no danger in view; the trip plan isn't leaving the level. The path
may be at most 9 steps. The Pilot gives up after 20 s (`ENGAGE_GIVE_UP_S`) and drops that target for the level. Logged
as `act cmd=engage`. Every safety rule above runs first, so they still win.

### 2.3 Status cures (`status_tick`, `confusion_lock`, `confusion_window`)

Potions by status, cheapest first (`STATUS_CURES`): stun → CCW, Healing…; poison → Cure/Neutralize Poison, CCW…;
confused → CSW, CCW…; blind → CLW, CSW, CCW…. `status_tick` drinks only in combat, and only when it matters:

- **Stun**: a threat (HP < `think_hp`, or a mobile monster near our level) or a heavy stun.
- **Confused**: a threat nearby, or hit by something unseen while HP is low or falling fast.
- **Blind**: also when a monster was seen close in the last 10 s, a band was warned in the last 30 s, or an escape needs
  to read (Flee/Recall/Recover). After 2 blind cures in 30 s it fights on blind, unless an escape must read or HP is low.
- **Poison**: only when HP < `think_hp`.
- No cure carried: a `tactic` notice (once per 20 s).

Out of combat the Pilot rests these off; it doesn't drink.

**Confusion lock** (`confusion_lock`): confused for 8 s on end, with a goal or a monster adjacent. The Pilot quaffs CSW,
then CCW, at most every 8 s and at most 4 times per level. **Confusion window** (`confusion_window`): 0.3–4 s after such
a cure, with 3+ monsters adjacent, it teleports away in the clear moment before the next bite.

Blind or confused, scrolls can't be read. `teleport_item()` then prefers a Staff of Teleportation. It does the same for
10 s after the server refuses a read (`verify_use` sets `read_failed_t`).

### 2.4 Unseen attackers (`unseen_tick`)

The cause is an "It …" attack message in the last 3 s (`w.unseen`), or, with order `unseen_hp=on`, HP falling at
≥ 1% of max (and ≥ 2) per second with nothing in view and no hit for 4 s; poison, cuts, Weak hunger and a fresh level
(< 4 s) are excluded. The rule acts at most every 20 s, and not during Flee, Recall or Recover.

These are **news only** (the Pilot carries on):

- a door bursting open;
- a shriek;
- a weak caster we can see (5+ levels below us) while HP ≥ `think_hp`;
- minor spells (teleport-to, magic missile, arrow/bolt, curse, fear) while HP ≥ `think_hp`;
- anything at all above 80% HP, except a paralysing gaze when we lack Free Action.

Otherwise: `Flee("unseen attacker")` if stairs are known, else an alert that suggests Word of Recall. A Navigator-ordered
hunt suppresses the flee. Blind, this rule is off ("everything is *it*").

### 2.5 Stationary monsters (`still_fight_tick`, `stairs_beside_still`)

A NEVER_MOVE monster is fought only if it blocks the way, meaning it is next to a square the mover is heading for. It is
"killable" when its level is ≤ ours, it can't paralyse us (or we have Free Action), it has no no-save blind/confuse
blows, and it doesn't drain. No fight starts if any adjacent stationary monster drains, or below `think_hp` (a fight
already under way goes on). An item lying beside a
disenchanter is abandoned rather than fought for. A disenchanter that blocks the way and is too strong to kill: `Flee`.

### 2.6 What counts as dangerous (`danger_why`)

This one function decides "too dangerous to fight now". It is used by the arrival rule, the danger flee, engage, bands,
`monster_info` (`monster` command) and the trip plan. It returns the first reason that applies:

1. level ≥ clvl + `danger_level` (6);
2. a unique above our level;
3. the rulebook's rating (`rulebook/monsters.csv`, with the Advisor's danger table merged in; required, no fallback)
   5 ("leave on sight"), or rating 4 until clvl ≥ its level + 8. Ratings the rulebook marks
   as about strength alone (`veto_reason == "strength"`) are left to the simulator instead;
4. a fast unique (≥ 2× speed) within 8 levels whose melee per turn is ≥ HP/8;
5. any `D` (ancient dragon);
6. a mobile monster whose melee per turn is ≥ HP/3;
7. a breather whose two max breaths reach HP, or a pack whose breaths together reach HP;
8. a paralyser within 10 levels without Free Action (blows too weak to beat ¾ AC don't count; Hold spells do);
9. Brain Smash without Free Action plus resist blindness plus resist confusion;
10. no-save blinding or confusing blows within 10 levels without the resist (mobile monsters only);
11. the duel simulator (`sim_loss` → `fight_sim`, 300 duels, cached) says a fight costs > 80% of current HP (monsters
    within 3 levels of ours or above, mobile only);
12. a summoner within 5 levels.

Abilities come from `has_ability`, which checks, in order: inferred in play, the character sheet's flags, then the
orders `free_action`/`resist_blind`/`resist_conf`.

`worst_3turns(races)` is the rulebook's worst melee over 3 player turns at our AC (`worst_3turns_acNN`; a caster counts
its `spell_max` if that is higher), × `our_slowness()`. Without a rulebook row it falls back to 2.5 × worst melee ×
speed.

## 3. Escaping (`Pilot.escape`)

`escape(why)` is called by the emergency reflex. It does at most one thing per call. The order (mirrored by the
Advisor's estimator `base_policy`, `POLICY_VERSION pilot-escape-2026-10-29o` in `Advisor/data/estimator/options_sim.py`, so **tell the Advisor when it changes**):

1. A stairs command is already on its way (< 1.2 s): wait.
2. `emergency_loop`: 3 escape actions in 90 s (`emergency` notices except those sent with `action=False`, which report
   no action: "waiting to use ... fighting on", "potions too weak", "attacking X first"; plus the weak-potions phase
   door). With stairs ≤ 30 away: `Flee("emergency loop")` and resume the old
   goal afterwards. Without: an `emergency_loop` alert. At most once per 60 s.
3. **Stairs underfoot** while threatened (something in view, or hit < 2 s ago): take them, then goal `Recover`. Standing
   on stairs with nothing threatening: do nothing (stops stair-bouncing).
4. **Not in combat** (nothing adjacent, not hit in 3 s, and HP not falling with a monster in view): rest if nothing is in
   view, else `retreat_step` out of sight. No potions or scrolls out of combat. (An escape walk to stairs under way,
   step 12, carries on instead.)
5. **One turn from death** (adjacent worst over 3 turns ÷ 3 ≥ 90% HP), able to read: a Scroll of Teleportation, else
   Phase Door, whatever the rate limit.
6. **Speed first**: a Potion of Speed, if not already fast (once per 20 s).
7. **HP < 30%**, able to read, no recall under way: Word of Recall (the last resort, started early because it takes
   15–34 turns).
8. **Phasing futile** (`phase_futile`: 3 Phase Doors in 20 s), still adjacent, HP ≥ 20%: Word of Recall. After that,
   Phase Door is withheld until HP < 20%.
9. **Kill the caster** (`kill_caster_step`): an adjacent summoner or status caster (blind, confuse, hold, slow, scare,
   forget, drain mana, tele-to, tele-level) that our weapon kills in 2 rounds (rulebook HP vs. weapon damage): attack it.
10. **Teleport, not phase**, with a monster adjacent: 4+ mobile monsters within 5 in the open (not a corridor), or
    afraid with 2+ adjacent. Teleportation scroll or staff (`teleport_item`), rate-limited 2 s.
11. **Phase Door** with a monster adjacent: every 2.5 s, or every 0.7 s when HP < 35%. An item inscribed `@r1` is used
    first.
12. **Out of melee**: walk to stairs ≤ 20 away (`escaping_to_stairs`: true only while that walk
    is the mover's current one on this level) and take them on arrival. Not within 2 s of
    another use, since a new move sends `clear` and would drop a queued read.
13. **Potions by numbers** (every 1.5 s): need = max(2 s × damage rate, 10% max HP when HP < 30%). Drink the weakest
    potion that heals more than need. If none is enough and damage isn't dire, drink the biggest. If every potion is too
    small and death is < 8 s away at this rate: Phase Door (adjacent), else Word of Recall, else (not adjacent) the
    biggest potion. With 2+ adjacent, a cure is outpaced, so: blind or confused, quaff the status cure so the next turn
    can read; else read Phase/Teleport instead of the cure.
14. Nothing usable: an `emergency` notice "waiting to use … / nothing left to escape with, fighting on" (every 10 s).

Read and quaff are confirmed by `verify_use`: done when the server says "You have N … left" or the recall charges. An
unconfirmed read or quaff is resent up to 2 times, 2.5 s apart. **Word of Recall and Teleport are never resent**, because a second read
cancels or doubles them (after 8 s without an answer they are given up). A refused read ("You can't see anything", "You are too confused", "no light") resets the
escape timers and switches to the staff for 10 s.

`cmd()` also holds any second item command until the pack has come back. Letters shift as stacks empty: a past mission
drank the wrong potion this way.

### 3.1 The escape goals

| Goal | Started by | Behaviour | Ends |
|---|---|---|---|
| `Flee(why)` | danger in view, group > 1×, unseen attacker, strong disenchanter, `react leave`, emergency loop, second stat drain or an unseen drainer, `Reprieve`, `BandLeave`, the trip plan's band leave, `goal leave` | Walk to the nearest known stairs and take them. At or below `max_depth`, up stairs only. With only `>` known there, a teleport instead, at most once a minute. No known path to the stairs: read Magic Mapping once per level. Stairs > 15 steps away with a danger within 2: fail at once, so `flee_failed` recalls. Gets stuck: replan twice. A pickup during a flee with monsters in view needs value 500 or more. | Done when the level changes (it records `fled_from` so a dive doesn't take the same stairs back) or after 5 s. Failed: no stairs, no path, stuck. |
| `Recover(came_by, prev)` | the stairs-underfoot escape | Rest to `rest_to`. If now below `max_depth` and standing on `<`, go back up. Then resume the interrupted goal. | When healed. |
| `WalkAway(names)` | a summoner in view (`walk_away_ok`) | `retreat_step` over walked ground out of its sight, then set a 7-square avoid zone where it was. | Done when out of sight 6+ squares. Failed (and the danger flee may act at once; `walkaway_failed` marks the level): HP < 50%, it reached us, it summoned, 30 s passed, or nowhere to walk for 3 s. |
| `BandLeave(names)` | `flee_failed` for a band, at HP ≥ 80% with nothing adjacent and no danger, once per level | Door/Stair Location (staff or rod), else Magic Mapping, then `Flee` to what it shows. Neither carried: `WalkAway`. | Failed if nothing located. |
| `Reprieve(who)` | a hunt failed because a blinker got away | Danger near (or group ≥ 0.6× HP): `Flee`. Monsters in view: step out of sight. Else rest. | Healed, or after 2 min. |
| `Recall(depth_ft)` | hunger, idle, the plan, the Navigator (escapes read the scroll directly, without this goal) | In town, inscribe `@R<feet>` (max_depth) first, checking what the server will read. Put a light on if needed. Never reads a second scroll while one is pending (`recall_started`). Blind or confused: quaff CLW (blind only), CSW or CCW first. While it charges, rest if hurt and nothing is in view (time runs 10× while resting). | Done on arrival. Failed after 60 s (120 s if pending), quoting the game's refusal message. |
| `Resurrect` | the Navigator after death | A ghost floats up with `<` one level per press, then walks onto the Temple entrance (`4`). Costs half the XP. | Done when no longer a ghost. |

### 3.2 `flee_failed`

Called when a `flee…`/`leave…` goal fails, or from the danger rule. For a band at high HP with nothing on us, it starts
`BandLeave` (once per level). Otherwise, with monsters within 5 (or a danger at any range, or one only the server lists),
able to read: Word of Recall, then Phase Door every 2.5 s while it charges, when a monster is adjacent. The `emergency` notice says so.

### 3.3 Movement helpers

| Helper | What it does |
|---|---|
| `retreat_step(threats, reach=15)` | Walk to a square already walked this level, within reach, at least 2 squares further from the threats (and ≥ 4 from them), the furthest first. It never walks into unknown ground, since kiting into the unknown wakes more monsters. |
| `sidestep(threats)` | One step to a free square next to none of them, walked ground first. |
| `quiet_spot(reach=30)` | A walked room square, 4+ from unexplored squares and 3+ from doors (used by `QuietWait`). |
| `take_stairs(which)` | Stop the mover; send `<`/`>`; remember it (`last_stairs_cmd`: retried after 1.2 s, since the server ignores a stairs press right after arrival). |
| `teleport_item()` | Scroll of Teleportation, or a charged Staff when we can't read. |
| `use_stair_location(why)` | Staff/rod of Door/Stair Location (by flavour too). |

## 4. The Navigator's reactions (`react`)

These are executable standing orders: the Navigator decides in advance, and the Pilot acts at Pilot speed. They are
stored in `<rundir>/rules.json` as `{kind, arg, by, t}`, shown on the report's `Standing:` line, and set with `pilotctl
react …` (handled in `do_request`). They run in `rule_tick` after the reflexes, in the dungeon only, not while fleeing,
recalling or recovering.

| Command | Effect |
|---|---|
| `react leave NAME` | When NAME (exact monster name, `_` for spaces) is in view: leave the level, once per level. During a trip plan's level phase, the plan marks the level done and dives on. Otherwise goal `Flee`. `rule` notice. |
| `react hunt NAME` | When NAME is in view: `goal hunt NAME` as the Navigator would give it, so the hunt check applies. At most every 30 s per target and level. Not while already hunting. A plain goal it replaces resumes after the hunt. |
| `react thieves kill` | Hunt the nearest thief (EAT_ITEM/EAT_GOLD blows) within 6 squares, unless one of the thieves within 6 is a danger. |
| `react afraid teleport` | In the fear reflex: afraid, no fear-cure potion, and a monster adjacent: teleport (`teleport_item`). |
| `react -N` | Remove reaction N. |
| `react clear` | Remove all. |
| `react` | List them. |

The same reaction isn't added twice. Unknown monster names are refused. `leave`/`hunt` match the name in view exactly
(lower-cased).

Related orders (`order key=value`; defaults in `DEFAULT_ORDERS`):

| Order | Default | Used by |
|---|---|---|
| `flee_hp` | 0.5 | emergency trigger |
| `think_hp` | 0.65 | `fight_going_badly`, phase thresholds, cures, engage |
| `rest_below` / `rest_to` | 0.7 / 0.95 | resting |
| `arrival_pack` | 4 | arrival rule |
| `danger_level` | 6 | `danger_why` |
| `free_action`, `resist_blind`, `resist_conf` | no | ability fallbacks when the character sheet hasn't been read |
| `unseen_hp` | on | unseen-attacker rule |
| `choke` | on | corridor fighting |
| `stop_on` | unique,danger | `danger` must be in it for the arrival and danger flees |
| `band_frac` | 0.5 | `watch_band` |
| `max_depth` | 0 | flee direction, `Recover`, `Recall` inscription |
| `idle_recall_s` | 600 | `idle()`: no goal or plan and no agent contact → `Recall` |

## 5. The watches

All run every tick. Most only notify; the ones that act are marked.

| Watch | Trigger | What it does |
|---|---|---|
| `watch_band` | 5+ mobile, non-trivial (≥ 6 worst a turn) monsters within 10, or their worst melee together ≥ 40% of max HP | `band_cost`: expected HP lost fighting them one at a time, quickest kills first, at most 8 hitting at once (2 in a corridor), × slowness. Serious when that is > `band_frac` × HP, or a member is dangerous: `band` alert (once per level, again when the band grows by half), which the trip plan acts on, plus a band shadow decision. Weak bands: a `tactic` notice, and the Pilot fights on. `band_live()` (warned < 20 s ago, or 3+ still within 10) blocks engaging. |
| `watch_character` (acts) | a stat's current value drops with its maximum unchanged | `stat_drained` alert naming the Restore potion (or the tavern stash). STR, DEX or CON drained by something unseen (not a trap; no drainer in view): a `drainer` alert and `Flee` (when no trip plan runs and stairs are known). On a second drain on this level with a weak (5+ levels below us, not unique), no-faster drainer adjacent: `Hunt` it. Otherwise a second drain triggers `Flee` (stairs known). Also `blows_changed`. |
| `watch_drainers` | a mobile monster in view whose blows drain a stat | A `drainer` notice once per level. Weak (5+ levels below us, no faster, not unique): "kill it fast", as news. Else "avoid or leave" (also news when it drains none of STR, DEX, CON). `drainers [STAT] [MAXLEVEL]` (`drainers_info`) lists drainers by level. |
| `watch_thieves` | a thief in view (dungeon) | A `thief` notice once per level, suggesting `goal hunt`. Gold-only thieves are news. |
| `watch_breeders` | 3+ MULTIPLY monsters in view (or 8+ weak ones again) | A `breeders` notice "leave this level". Weak ones (all 10+ levels below us, fewer than 8) are news. Silent during a Dive. |
| `watch_traps` | trap messages | "3 traps on this level: leave it" (`tactic`). A trap door is logged (`trapdoor`), with news when it dropped us below `max_depth`. |
| `watch_kills` | "You have slain <unique>" | `unique_slain`. Records `uniques_killed.json` (repeat kills give nothing) and marks the drop for pickup. |
| `watch_perception` | the server's monster list names a monster the map decode doesn't show for 1.5 s | Logs `perception_gap` (with a map crop), once per level and name. |
| `watch_progress` (acts) | the mover stuck on one square for 20 s; or a goal visiting ≤ 10 squares in 2 minutes while not fighting | Clears the server queue and restarts the move (`stuck`). The second 2-minute trigger for the same goal ends the goal. Waiting goals (Wait, Rest, Search, Recall, Recover, Shop) are exempt. |
| `food_watch` | no rations in the pack in the dungeon (checked every 15 s, from `track_gains`) | A `supply` notice once per trip. |
| `supply_watch` | food or light (reserves counted, `supply_minutes`) under 15, then 5, dungeon minutes | A `supplies` notice; it re-arms above 20. |
| `town_light` (acts) | in town, idle, no agent contact for 20 s | Takes the light off (it burns 10× while resting). |
| `keep_light` (acts) | lantern < 3000 turns, torch < 500, or no light in the dungeon | Refill from a flask, swap to a fuller lantern or torch, or wield the best light (`best_light`). Else `warn_light`: a `low_supply` notice once per state, every 10 min at most; news in town. |
| `confusion_lock` / `confusion_window` (act) | see §2.3 | |

`monster_info` (the `monster NAME` command) shows this server's facts for a monster, its `danger_why` verdict, the hunt
check and the expected drop: the same rules the reflexes use. `our_slowness()` (1 at normal speed; 2 at −10; 3.3 at −20)
scales `worst_3turns`, `group_danger` and `band_cost`. `buff_on(fast|hero|shero)` reads the start and end messages,
because the status reply has no flag for them.

## 6. What gets logged

`<rundir>/decisions.jsonl` (each record has `t, kind, depth, pos, hp`):

| kind | Written when | Fields |
|---|---|---|
| `act` | every command sent | `cmd`, `why` (the reason, e.g. "low HP: phase door"), `by` (pilot/plan/nav/arch); `cmd=engage` for an engage |
| `escape` | an escape sent (`log_escape`, from `cmd`) | `escape` = phase / teleport / wor_escape / wor_travel / stairs; `trigger`, `adjacent`, `goal`. Stairs count as an escape during Flee/Recover, with an escape reason, or within 10 s of an escalation notice. |
| `attention` | every notice (`notify`) | `what` (below), `detail`, `crop`. `emergency`/`emergency_loop` add `map21` (21×21 remembered map), `map_at`, `mons`; `emergency` (in the dungeon) also `shadow`. `band` adds `shadow`. |
| `note` | `effect_failed` (an action's effect not seen in 3 s), held item commands, "recall already under way" | `text` |
| `audit_check` / `audit` | every 30 s: the model vs. a fresh server query (`audit_tick`) | differences by field; then a redraw |
| `mons` | each second with monsters in view | positions, `track` (health bar), `fighting` |
| `looks` | `read_looks` | the asleep flags read |
| `perception_gap`, `trapdoor` | see §5 | |

The `what` values for notices about danger and fighting: `emergency`, `emergency_loop`, `danger_seen`,
`danger_avoided`, `fight_going_badly`, `unseen_attacker`, `band`, `stat_drained`, `drainer`, `thief`, `breeders`,
`fearer`, `afraid`, `rule`, `tactic`, `dead`, `low_supply`, `supply`, `supplies`, `blows_changed`, `stuck`,
`idle_recall`, `recall_cancelled`, `unique_slain`.

`NEWS` kinds (`danger_avoided`, `tactic`, …) and notices sent with `news=True` go to the report's news and don't wake
the Navigator. While a trip plan runs, `PLAN_QUIET` kinds (including `emergency`, `band`, `danger_seen`) are news too,
because the plan acts on them. `emergency` notices that report an action also feed `emerg_times` (the emergency loop) and the status line's
counters. The status header shows `escape_line()`: ESCAPE LANDING / escaped / FAILED for 6 s after a Phase or Teleport.

## 7. Bookkeeping that protects the fight

- `verify_effects`: equip, pack or level commands whose effect never showed in 3 s are logged and noticed (stairs are
  retried by the goals).
- `verify_use`: see §3.
- `audit_tick`: every 30 s (and a town redraw every 2 min), compares pack, equipment, HP, gold, depth, position and
  hunger with a fresh query. HP differences are ignored in melee. Any difference triggers a resync.

## 8. Known limits

- **One action per tick, rules in a fixed order.** The first rule that fires wins. Interactions are tuned case by case
  (each threshold has a mission behind it), so changing one threshold can shift others. The estimator mirrors the
  escape order, so changes must be reported to the Advisor.
- **Worst-case sums are pessimistic.** `group_danger` adds every blow at maximum, and at low clvl a single monster can
  reach 0.6×. `worst_3turns` depends on the rulebook rows (it falls back to 2.5 raw rounds).
- **No monster flow on this server.** Monsters walk straight back after a Phase Door, which is why the rate limits,
  phase-futility and teleport-for-crowds rules exist. Phase Door is still the main escape.
- **Sleep is barely used.** `is_asleep` (from `look`) is collected for the estimator, but the reflexes don't consult it.
- **Blindness.** The map decode sees nothing, so the unseen rule is off and auto-retaliate fights on. Only the staff
  escapes.
- The danger flee takes the nearest stairs. A walk through unexplored squares can meet more monsters. Far stairs with a
  danger beside us fail over to Word of Recall.
- Corridors are mostly two wide here, so `choke` limits attackers to about 3, not 1.
