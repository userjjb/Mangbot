# Pilot: combat and survival

The Pilot (`github/tools/pilot/`, class `Pilot`) keeps the character alive on its own, second to second, without
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

**Where the code is** (E1 step 5): the methods in this file live in `tools/pilot/combat.py` as `CombatMixin`, still
`Pilot`'s names (`class Pilot(ReportMixin, GearMixin, ItemsMixin, TownMixin, CombatMixin, CommandsMixin)`; the Advisor's estimator
mirrors `Pilot.escape`, `group_tick`, `speed_start_tick`, `berserk_tick` and `fear_cure` by name): `reflexes` and
`escape`, each running one method per step in the order of `REFLEX_STEPS` / `ESCAPE_STEPS` (E3; §2 and §3 name each
step's method), `escape` (with `emergency_loop`, `phase_futile`, `escaping_to_stairs`, `kill_caster_step`,
`count_escape`, `log_escape`/`ESCAPE_WHY`), `danger_why`, `worst_3turns`, `sim_loss`, `dangers`, `danger_text`,
`has_ability`, the §2 rules (`engage_tick`, `group_danger`/`group_tick`, `status_tick`,
`confusion_lock`/`confusion_window`, `unseen_tick`, `still_fight_tick`/`stairs_beside_still`, `choke_tick` and the
module's `choke_tier`, `speed_start_tick`, `berserk_tick`, `hard_fight`, `fear_cure`, `buff_on`, `our_slowness`,
`hunt_ordered`, `walk_away_ok`), `flee_failed`, the §3.3 helpers except `take_stairs` (`retreat_step`, `sidestep`,
`quiet_spot`, `teleport_item`, `use_stair_location`), the `react` rules (`RULE_KINDS`, `rules`, `save_rules`,
`has_rule`, `rule_tick`), the §5 watches `watch_band` (`band_cost`, `band_live`), `watch_character`, `watch_drainers`,
`watch_thieves`, `watch_breeders`, `watch_traps`, `watch_kills`, `watch_perception`, `watch_progress`, and the potion
tables `heal_of`/`HEALS`, `STATUS_CURES`, `CURE_POTIONS`. Still in `pilot.py`: `tick` and its steps (`confusion_tick`
calls the confusion pair, `watch_tick` the watches, `act_tick` `reflexes` and `rule_tick`), `take_stairs`,
`start_resting`/`stop_resting`, `recall_started`, `set_goal`/`step_goal`, `look_tick`/`is_asleep`. The commands are in
`commands.py` (`CommandsMixin`, E1 step 6: `cmd_react`, the `monster` entry of the command table, `monster_info`,
`drainers_info`, `hunt_refusal`, `uniques_killed`; commands.md). Elsewhere: `phase_item`, `find_item`,
`keep_light`/`town_light`, `watch_weapons`/`watch_abilities` in `items.py`; `supply_watch` in `town.py`; the shadow
decisions, the duel estimates (`fight_sim`) and `disenchant_cost` in `gear.py`; the escape goals in `goals.py`.

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

Each row is one method of `CombatMixin` (E3, session 11), and `reflexes()` runs them in the order of the class's
`REFLEX_STEPS` tuple: a step returns `NEXT` to go on, or the value `reflexes()` returns (True ends the tick). One
entry is not a rule: `_reflex_survey`, between the busy check and the emergency, puts the monsters within 7
squares (`ctx.mons_near`) on the per-call context `ctx` for the steps that follow (`ctx` also carries `w`, the
orders `o` and `now`, read once per call; `_reflex_adjacent` adds `ctx.adj` for the pickup's test). The code
numbers the steps its own way (2, 2', 2a, 3, 3a-3i, 4, 5, 5b, 6, the comments of old): each method's docstring
starts with that number.

| # | Step | Trigger | Action | Method |
|---|---|---|---|---|
| 0 | Death | HP ≤ 0 or ghost | Stop everything; `dead` alert. Nothing else runs until `goal resurrect` is given (goal `Resurrect`). | `_reflex_death` |
| 0 | Busy / store | an action is still on its way (`busy_until`); inside a store during a `Shop` goal | Busy: hold. Store: skip the rest of the reflexes, so the `Shop` goal carries on (any reflex command would leave the store). | `_reflex_busy` |
| 1 | **Emergency** | HP < `flee_hp` (0.5), **or** "hard": HP ≤ the adjacent monsters' worst melee over our next 3 turns (`worst_3turns`) while HP < 90%; and a monster is within 7 squares or we were hit in the last 5 s | `escape(why)` (§3). If it had nothing to do this instant, the mover stops anyway (unless it is escape's own walk to stairs): the goal never takes over during an emergency, because a new walk would wipe the queued reads. | `_reflex_emergency` |
| 2 | **Group danger** | `group_tick` (§2.1) | Retreat, stairs, flee, recall, staff or phase, by tier. | `_reflex_group` |
| 3 | Hard-fight start | `hard_fight()`: a unique or a monster within 5 levels of ours adjacent, or 2+ adjacent at < 75% HP | `speed_start_tick` (2.58.0, the user: no longer at the start -- the estimator found no safety gain, ~380 gold each): a Potion of Speed only when losing -- a monster adjacent and HP under `think_hp` (the fight_going_badly line); not if already fast; once per 30 s; the emergency's own Speed step stays. Then `berserk_tick`: Berserk Strength (same test, once per 30 s). `hard_fight_shadow` logs the estimator's view first. | `_reflex_hard_fight` |
| 4 | Status cures | `status_tick` (§2.3) | The cheapest potion that cures stun, confusion, blindness or poison. | `_reflex_status` |
| 5 | Arrival into danger | < 6 s on a new level, standing on stairs | Take the stairs back if `arrival_pack` (4) monsters within 5 levels of ours are within 7 squares, or a danger (`danger_why`) is in view (with `danger` in `stop_on`). `danger_avoided` news. | `_reflex_arrival` |
| 6 | Danger in view | a monster that `danger_why` flags, within 12 squares (or listed by the server but not yet on the map) | **Exception:** slow casters with weak melee (no faster than us, average and worst melee < HP/8) and stairs > 8 away are *not* fled: walking away gives them free casts (`danger_seen` alert says "fight it or recall"). **Summoners only**, HP ≥ 50%, 3+ squares away, no faster, nothing summoned yet, and walking away hasn't failed on this level (`walk_away_ok`): goal `WalkAway`. Otherwise goal `Flee` (`danger_seen` alert). There is a 10 s gap between flees. The flee is skipped if the Navigator ordered a hunt in the last 2 minutes (`hunt_ordered`). If a flee just failed, `flee_failed` runs again. A summoner listed before its map position is known gets up to 1.5 s for the map to place it. (Since 2.45.1 the later reflexes run during that wait, except engage (`ctx.summoner_hold`); only the summoner decision waits.) | `_reflex_danger_in_view` |
| 7 | Unseen attacker | `unseen_tick` (§2.4) | Flee to known stairs, or advise a recall. | `_reflex_unseen` |
| 7a | **Equipment damage** (2.57.0, the user after m65: Water hounds breathed acid 31 times, 26 unseen; 21 "Your X is damaged!" took ~5,000 gold of armour plusses while resist acid kept HP up) | `gear_damage_tick`: the messages "Your X is damaged!" (spells1.c minus_ac: acid takes 1 to-AC of a random worn armour piece unless it ignores acid) and "Your X (c) was disenchanted!", each costed at what restoring it costs (`gear_damage_cost`): a hit takes a piece from the plus it had (remembered before the hit, `gear_plus`) to one less, and the repair is the town kit's read at the lowered plus -- scroll price / chance there (+8 -> +7: the read at +7, ~190 / 0.5 = ~380), via `reenchant_cost` from the plus it now has up to the plus it had, each hit its own step; the plus's resale only where the kit wouldn't re-enchant (a chance under `ENCHANT_MIN_CHANCE` at that step, a weapon beyond the weapon plan, the bow); `GEAR_EVENTS` = 2 within `GEAR_WINDOW_S` = 10 s, or `GEAR_COST_MAX` = 1000 gold within 30 s (over two armour points at +7, or one dear disenchantment: ~6-7 dungeon minutes' earnings; one acid hit, ~380, stays under it) | The source in view (the attack message just before: "The Water hound breathes acid.") and quick (`fight_sim`: all of that race in view dead within `GEAR_QUICK_TURNS` = 6 of our turns): Hunt it. Otherwise leave -- 2.58.0 (the user, on the Advisor: the walk to the stairs costs ~5 more acid hits than fighting): against a breather that can follow (not NEVER_MOVE) or an unseen one, Teleportation at once (staff or scroll), then Word of Recall, the stairs only when adjacent; against one that can't follow, the stairs within 20, else Teleportation, Phase Door, Word of Recall. Once per 3 s; not while fleeing or recalling. `gear_damage` alert: what, by what, the cost so far. `monster NAME` says "GEAR: acid damages armour / disenchants gear" (`gear_damage_kind`: BR_ACID/ACID blows, BR_DISE/UN_BONUS) | `_reflex_gear_damage` |
| 8 | Choke point | order `choke=on`; 3+ monsters within 5 levels of ours, within 10 squares; we're in the open, not on stairs, not fleeing | `choke_tick`: walk to a corridor square (best `choke_tier`) within 10 steps, further from the pack's centre, and hold it up to 25 s so they come one at a time. | `_reflex_choke` |
| 9 | Summon trap | "You are enveloped in a cloud of smoke" in the last 2 s, not blind or confused | Phase Door at once (`@r1` first; `emergency`). | `_reflex_summon_trap` |
| 10 | Slowed | our speed makes monsters act ≥ 2× (`our_slowness`), in melee or hit in the last 2 s | Potion of Speed (once per 40 s). | `_reflex_slowed` |
| 11 | **Afraid** (a warrior can't melee) | afraid, a monster within 7 | Just arrived on stairs among 2+ monsters: take the stairs back. Not in danger (HP ≥ `think_hp`, no danger, < 2 adjacent, damage < 2% max HP/s): kite with `retreat_step` over ground already walked. In danger: `fear_cure` (Heroism > Boldness > Berserk), else teleport if `react afraid teleport` is set, else Phase Door if a monster is adjacent. | `_reflex_afraid` |
| 12 | Stationary monsters (molds, jellies, eyes) adjacent | NEVER_MOVE adjacent, not the hunt target | `stairs_beside_still`: the wanted stairs are a step away and these monsters are harmless for one turn, so take the stairs. `still_fight_tick` (§2.5): kill it if it blocks the way and is killable, or flee a strong disenchanter. Otherwise step away (`retreat_step` reach 6, else `sidestep`). | `_reflex_still` |
| 13 | Repeat fearers | a mobile monster that frightens again and again, within 7; not during Flee or Recall | `fearer` alert once per level; Phase Door if it is within 2 levels of ours and any monster is adjacent (every 2.5 s at most); otherwise retreat. | `_reflex_fearers` |
| 14 | Light | `town_light`, `keep_light` (§5) | Skipped with a monster adjacent, **unless we have no light at all** in the dungeon. | `_reflex_light` |
| 15 | Hunger | hunger ≤ 1 (Weak; since 2.45.2 Hungry, 2, is `policy_tick`'s, at a safe moment -- the user: a battle turn spent eating when not needed is wasted), no monster adjacent (fainting, 0: even then) -- it no longer waits for 5 s without a monster in view | Eat (once per 10 s). No food: read Satisfy Hunger only when Weak (≤ 1), because it fills you to Gorged. Neither, and Weak outside town: goal `Recall` (`supplies`, level `recalling`). While it waits (a meal under 10 s ago) the later steps still run (A20, 2.39.0). Weak with only scrolls and no light worn: `wear_light` puts the best light in the pack on (that ends the call); with no light to put on, the later steps still run too (2.45.0; it used to return there). | `_reflex_hunger` |
| 16 | **Adjacent monster** | any adjacent | Stop the mover (except during Goto/Flee) and stop resting. Below `think_hp`: `fight_going_badly` alert (once per 10 s). With 2+ adjacent and one a thief (EAT_ITEM/EAT_GOLD blows), hit the thief first (item thieves before gold thieves). Otherwise hold, so auto-retaliate fights. A Goto or Flee goal keeps moving instead. | `_reflex_adjacent` |
| 17 | Pickup / auto-destroy | standing on an item | Belongs to the item policy ([pilot-items.md](pilot-items.md)). While fleeing (Flee, BandLeave, WalkAway) with monsters in view, only items worth 500 or more are picked up. | `_reflex_pickup`, `_reflex_pack` |
| 18 | **Engage** | `engage_tick` (§2.2) | Fight a monster in view the hunt check allows (2.66.0: any level, adjacent ones attacked, pursuers first, also while the trip leaves for a non-danger reason). | `_reflex_engage` |
| 19 | Rest | HP < `rest_below` (0.7), nothing in view, not recalling | First, an escape walk to stairs (escape step 12) that outlived its emergency (escape() isn't called once nothing is within 7 and no hit for 5 s): keep walking, and on the stairs take them (escape step 3, then `Recover`). It ends when the walk does (blocked, stopped by another step, replaced by another walk) or on a new level; before 2.45.0 nothing ticked it and the character stood still, neither walking nor resting. Otherwise rest. It stops at `rest_to` (0.95) or when a monster appears, and goes on resting until `rest_to` once started. | `_reflex_rest` |

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

**2.66.0, the user after m69 ("If there is a monster in view we should kill it, unless we have a reason not to"):**
while exploring or diving (or with no goal), the Pilot fights any mobile monster within 12 steps (`ENGAGE_STEPS`) that
the hunt check allows (`hunt_refusal`; cached per level and name; it refuses a disenchanter whose expected enchantment
loss is more than a kill brings, §5), **whatever its level** (the old "20 levels below ours: no XP worth the detour" is
gone), **adjacent ones included** -- attacked by moving into them, the mover stopped (auto-retaliate only hits while we
stand still; m69's Baby bronze dragon tailed Dive04 one or two squares behind while the mover walked on) -- and
**pursuers first** (`track_pursuers`: within 2 squares after 2+ of our moves, or adjacent), then the nearest.
It also does this while the trip leaves a level for breeders, traps, a pit or nest, a feeling or time.
The reasons not to: a goal other than Explore/Dive (Flee, Recall, Recover, escape walks...), a recall pending, HP <
`think_hp`, blind/confused/afraid/slowed, a live band (the estimator decides), a danger rule in view (or a summoner hold,
`_reflex_engage`), a breeder (`MULTIPLY`), an `avoid`-list name, a stationary monster (`still_fight_tick`'s), the hunt
check's refusals, and the trip leaving for a danger (`leaving_for_danger`: `LEAVE_FOR_DANGER` -- a band, drainer, fearer,
danger, gear damage, an unseen attacker, an emergency, the Navigator's leave rule, a disenchanter). The path may be at
most 14 steps. The Pilot gives up after 20 s (`ENGAGE_GIVE_UP_S`) and drops that target for the level. Logged as `act
cmd=engage` ("..., following us" for a pursuer). Every safety rule above runs first, so they still win.

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
    within 3 levels of ours or above, mobile only). Since 2.45.0 `fight_sim` takes our to-hit/to-dam **totals** from
    the gear model (rings, gloves, the stat tables), not the weapon's own plusses (gear-and-estimator.md);
12. a summoner within 5 levels.

Abilities come from `has_ability`, which checks, in order: inferred in play, the character sheet's flags, then the
orders `free_action`/`resist_blind`/`resist_conf`.

`worst_3turns(races)` is the rulebook's worst melee over 3 player turns at our AC (`worst_3turns_acNN`; a caster counts
its `spell_max` if that is higher), × `our_slowness()`. Without a rulebook row it falls back to 2.5 × worst melee ×
speed.

## 3. Escaping (`Pilot.escape`)

`escape(why)` is called by the emergency reflex. It does at most one thing per call. The order (mirrored by the
Advisor's estimator `base_policy`, `POLICY_VERSION pilot-escape-2026-11-03p` in `Advisor/data/estimator/options_sim.py`,
so **tell the Advisor when it changes**) is that of `ESCAPE_STEPS`, one method per step (E3, session 11; each item below
names its method), run like the reflexes' (§2). `_escape_survey`, after step 3, is not a step: it puts what the later
steps share on `ctx` (`adj`, `can_read`, the Phase Door `pd`, the damage `rate`, `in_combat`); step 5 adds `one_turn`,
step 8 `collapsing` (and clears `pd` when phasing is futile), step 10 `crowd` and `tele`:

1. `_escape_stairs_pending`: A stairs command is already on its way (< 1.2 s): wait.
2. `_escape_loop`: `emergency_loop`: 3 escape actions in 90 s (`emergency` notices except those sent with
   `action=False`, which report no action: "waiting to use ... fighting on", "potions too weak", "attacking X first";
   plus the weak-potions phase door). With stairs ≤ 30 away: `Flee("emergency loop")` and resume the old goal
   afterwards. Without stairs: an `emergency_loop` alert ("no stairs known nearby"); stairs known but already fleeing:
   an `emergency_loop` alert saying so (A21, 2.40.0). At most once per 60 s.
3. `_escape_stairs_underfoot`: **Stairs underfoot** while threatened (something in view, or hit < 2 s ago), or
   reached by the escape walk to stairs (step 12, `escaping_to_stairs`): take them, then goal `Recover`. Standing on
   stairs with nothing threatening and no escape walk: do nothing (stops stair-bouncing: arriving by stairs you stand
   on stairs, and the walk ends with the level). (Before 2.45.0 the escape walk's arrival was also left to this
   threat test, so with its danger out of view for 2 s it stood on the stairs.)
4. `_escape_out_of_combat`: **Not in combat** (nothing adjacent, not hit in 3 s, and HP not falling with a monster in
   view): rest if nothing is in view, else `retreat_step` out of sight. No potions or scrolls out of combat. (An escape
   walk to stairs under way, step 12, carries on instead.)
5. `_escape_one_turn`: **One turn from death** (adjacent worst over 3 turns ÷ 3 ≥ 90% HP), able to read: a Scroll of
   Teleportation, else Phase Door, whatever the rate limit.
6. `_escape_speed`: **Speed first**: a Potion of Speed, if not already fast (once per 20 s).
7. `_escape_recall`: **HP < 30%**, able to read, no recall under way: Word of Recall (the last resort, started early
   because it takes 15–34 turns).
8. `_escape_phase_futile`: **Phasing futile** (`phase_futile`: 3 Phase Doors in 20 s), still adjacent, HP ≥ 20%: Word of
   Recall. After that, Phase Door is withheld until HP < 20%.
9. `_escape_kill_caster`: **Kill the caster** (`kill_caster_step`): an adjacent summoner or status caster (blind,
   confuse, hold, slow, scare, forget, drain mana, tele-to, tele-level) that our weapon kills in 2 rounds (rulebook HP
   vs. weapon damage): attack it.
10. `_escape_teleport`: **Teleport, not phase**, with a monster adjacent: 4+ mobile monsters within 5 in the open (not a
    corridor), or afraid with 2+ adjacent. Teleportation scroll or staff (`teleport_item`), rate-limited 2 s.
11. `_escape_phase`: **Phase Door** with a monster adjacent: every 2.5 s, or every 0.7 s when HP < 35%. An item
    inscribed `@r1` is used first.
12. `_escape_to_stairs`: **Out of melee**: walk to stairs ≤ 20 away (`escaping_to_stairs`: true only while that walk is
    the mover's current one on this level); step 3 takes them on arrival. Not within 2 s of another use, since a new
    move sends `clear` and would drop a queued read. If the emergency ends first (escape() no longer called), the
    reflexes' rest step (§2, row 19) keeps the walk going and takes the stairs.
13. `_escape_potions`: **Potions by numbers** (every 1.5 s): need = max(2 s × damage rate, 10% max HP when HP < 30%).
    Drink the weakest potion that heals more than need. If none is enough and damage isn't dire, drink the biggest. If
    every potion is too small and death is < 8 s away at this rate: Phase Door (adjacent), else Word of Recall, else
    (not adjacent) the biggest potion. With 2+ adjacent, a cure is outpaced, so: blind or confused, quaff the status
    cure so the next turn can read; else read Phase/Teleport instead of the cure.
14. `_escape_nothing_left`: Nothing usable: an `emergency` notice "waiting to use … / nothing left to escape with,
    fighting on" (every 10 s).

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
react …` (`cmd_react`, commands.py). They run in `rule_tick` after the reflexes, in the dungeon only, not while fleeing,
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
| `watch_band` | 5+ mobile, non-trivial (≥ 6 worst a turn) monsters within 10, or their worst melee together ≥ 40% of max HP | `band_cost`: expected HP lost fighting them one at a time, quickest kills first, at most 8 hitting at once (2 in a corridor), × slowness. Serious when that is > `band_frac` × HP, or a member is dangerous: `band` alert (once per level, again when the band grows by half), which the trip plan acts on, plus a band shadow decision. **2.58.0 (the user: "let the estimator decide"; its shadow answers would have fought 6 of m63-m65's 7 bands, ~1,180 XP):** with no danger rule firing, the band goes to the estimator first (`band_shadow` in the shadow worker thread -- never in the tick: ~0.14 s median, 0.56 s max on 36 live band records) and the decision waits for it up to `BAND_EST_WAIT_S` = 2 s, the reflexes fighting meanwhile (`band_pending`, `band_resolve`). `band_verdict`: when its choice fights ("fight", or "rules", its copy of the Pilot's rules) safely and beats the band rule's leave row (stairs, else recall+phase) by more than max(`min_gain`, 2 SE), `min_gain` = max(50, 48 x `xp_rate_per_block`) -- the estimator's own threshold -- the Pilot fights on ("band: fighting (the estimator: fight beats leaving by N XP)" news); else (a leave choice, a thin margin, no answer in 2 s, the worker busy, an error, a danger rule) the `band` alert as before. `band_decision` log record (choice, gain, why) beside the shadow `estimator` record. **2.65.0 (the Advisor's band review of m66-m68):** `band_choice` maps the estimator's lines -- `fight`/`rules` -> fight on; `phase` (options_sim: Phase Door first, then the rules) -> read Phase Door now and fight on ("band: Phase Door, then fighting them as they come"), or, with no Phase Door to read (none, blind, confused), the `fight` row judged instead; `recall+phase` and `stairs` -> leave (the band alert); the same threshold against the leave row for both fight lines (`band_verdict` = its gain). `band_outcome` record `BAND_OUTCOME_S` = 60 s after each `band_decision`: names, choice, `lowest_hp` [hp, max], `xp` gained, `kills`, `escapes` (escape actions), `left_level` (`band_outcome_tick`, run first in `watch_band`; `kill_n`/`escape_n` are running counts). Weak bands: a `tactic` notice, and the Pilot fights on. `band_live()` (warned < 20 s ago, or 3+ still within 10) blocks engaging. |
| `watch_character` (acts) | a stat's current value drops with its maximum unchanged | `stat_drained` alert naming the Restore potion (or the tavern stash). STR, DEX or CON drained by something unseen (not a trap; no drainer in view): a `drainer` alert and `Flee` (when no trip plan runs and stairs are known). On a second drain on this level with a weak (5+ levels below us, not unique), no-faster drainer adjacent: `Hunt` it. Otherwise a second drain triggers `Flee` (stairs known). Also `blows_changed`. |
| `watch_drainers` | a mobile monster in view whose blows drain a stat | A `drainer` notice once per level. Weak (5+ levels below us, no faster, not unique): "kill it fast", as news. Else "avoid or leave" (also news when it drains none of STR, DEX, CON). `drainers [STAT] [MAXLEVEL]` (`drainers_info`) lists drainers by level. |
| `watch_thieves` | a thief in view (dungeon) | A `thief` notice once per level, suggesting `goal hunt`. Gold-only thieves are news. |
| `watch_breeders` | 3+ MULTIPLY monsters in view (or 8+ weak ones again) | A `breeders` notice "leave this level". Weak ones (all 10+ levels below us, fewer than 8) are news. Silent during a Dive. |
| `watch_traps` | trap messages | "3 traps on this level: leave it" (`tactic`). A trap door is logged (`trapdoor`), with news when it dropped us below `max_depth`. |
| `watch_kills` | "You have slain <unique>" | `unique_slain`. Records `uniques_killed.json` (repeat kills give nothing) and marks the drop for pickup. |
| `watch_perception` | the server's monster list names a monster the map decode doesn't show for 1.5 s | Logs `perception_gap` (with a map crop), once per level and name. |
| `watch_hallucination` | (2.65.0) `World.hallucinating`: "You feel drugged!" until "You can see clearly again." (at most 120 s; the server sends no status flag for it) | A `hallucinating` alert when it starts (what the server's list shows; a CSW/CCW ends it), news when it ends. Meanwhile `World.monsters` comes from `stand_in_monsters` (pilot-core.md): the map's glyphs are scrambled (cave.c `image_monster`, and 1 square in 256 anywhere shows a random glyph) but the server's monster list stays true, so every danger rule, the group danger, the band estimate, hunt checks and the estimator team see the listed monsters, not the map's names; HP lost and attack messages drive escapes as always. Also news once per level and name when a glyph read as a race 20+ levels deeper than the level (a unique too) is not confirmed -- by a message naming it, the server's list, or a hit while it is adjacent -- and is read as a depth-typical monster (m68: a scrambled glyph as Draugluin "can deal 504" read Word of Recall). |
| `watch_progress` (acts) | the mover stuck on one square for 20 s; or a goal visiting ≤ 10 squares in 2 minutes while not fighting | Clears the server queue and restarts the move (`stuck`). The second 2-minute trigger for the same goal ends the goal. Waiting goals (Wait, Rest, Search, Recall, Recover, Shop) are exempt. |
| `supply_watch` | in the dungeon: no rations in the pack (once per trip; `food_watch` merged here, D14); food or light (reserves counted, `supply_minutes`) under 15, then 5, dungeon minutes | A `supplies` notice: news with level `out` for no food; level `low` for the minutes (re-arms above 20). |
| `town_light` (acts) | in town, idle, no agent contact for 20 s | Takes the light off (it burns 10× while resting). |
| `keep_light` (acts) | lantern < 3000 turns, torch < 500, or no light in the dungeon | Refill from a flask, swap to a fuller lantern or torch, or wield the best light (`best_light`). Else `warn_light`: a `supplies` notice (supply `light`, level `low` or `out`) once per state, every 10 min at most; news in town. |
| `confusion_lock` / `confusion_window` (act) | see §2.3 | |

`monster_info` (the `monster NAME` command) shows this server's facts for a monster, its `danger_why` verdict, the hunt
check and the expected drop: the same rules the reflexes use. For a disenchanter (UN_BONUS blows or BR_DISE) it adds
the expected disenchantment (`disenchant_cost`, gear-and-estimator.md §3.1; 2.45.0): a lost step the town kit would
buy back is valued at the scrolls' price / chance, any other at its resale value (2.46.0). Since 2.45.1 the hunt check
(`hunt_refusal`, so `goal hunt` and engage too) refuses the monster when that loss is more than a kill brings (the
drop's expected value + its XP at `xp_per_gold`); never with resist disenchantment. `our_slowness()` (1 at normal speed; 2 at −10; 3.3 at −20)
scales `worst_3turns`, `group_danger` and `band_cost`. `buff_on(fast|hero|shero)` reads the start and end messages,
because the status reply has no flag for them.

## 6. What gets logged

`<rundir>/decisions.jsonl` (each record has `t, kind, depth, pos, hp`):

| kind | Written when | Fields |
|---|---|---|
| `act` | every command sent | `cmd`, `why` (the reason, e.g. "low HP: phase door"), `by` (pilot/plan/nav/arch); `cmd=engage` for an engage |
| `escape` | an escape sent (`log_escape`, from `cmd`) | `escape` = phase / teleport / wor_escape / wor_travel / stairs; `trigger`, `adjacent`, `goal`. Stairs count as an escape during Flee/Recover, with an escape reason, or within 10 s of an escalation notice. |
| `attention` | every notice (`notify`) | `what` (below), `detail`, `crop`. `emergency`/`emergency_loop` add `map21` (21×21 remembered map), `map_at`, `mons`; `emergency` (in the dungeon) also `shadow`. `band` adds `shadow`. |
| `hunt` | a `goal hunt` taken (2.45.0) | `target`, `by` (role), `refused` (the check said no: the Architect's or an override), `overridden`, `race`, `est_turns`, `est_loss`, `est_loss_p90`, `est_by` (fight_sim / estimate); for a disenchanter `disen_hits`, `disen_n`, `disen_gold`, `disen_resisted` (gear-and-estimator.md §3.1; also on its `order_refused`, `hunt_override` and engage `act` records) |
| `note` | `effect_failed` (an action's effect not seen in 3 s), held item commands, "recall already under way" | `text` |
| `audit_check` / `audit` | every 30 s: the model vs. a fresh server query (`audit_tick`) | differences by field; then a redraw |
| `mons` | each second with monsters in view | positions, `track` (health bar), `fighting` |
| `looks` | `read_looks` | the asleep flags read |
| `perception_gap`, `trapdoor` | see §5 | |

The `what` values for notices about danger and fighting: `emergency`, `emergency_loop`, `danger_seen`,
`danger_avoided`, `fight_going_badly`, `unseen_attacker`, `band`, `stat_drained`, `drainer`, `thief`, `breeders`,
`fearer`, `afraid`, `rule`, `tactic`, `dead`, `supplies` (fields `supply`, `level`; `low_supply` and `supply` before 2026-11-01, D14), `blows_changed`, `stuck`,
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
