# Pilot item policy

The Pilot (`tools/pilot/pilot.py`) handles items itself, second to second: it picks up, makes room, destroys junk,
identifies, learns flavours and wears upgrades, all by a value policy computed from the server's own data
(`itemvalue.py`) and the Advisor's rulebook tables (`tools/rulebook/*.csv`). The Navigator steers it with orders
(`order`, `keep`, `review`, `nopickup`) and may override a value refusal with `!`, but every gold piece that override
wastes goes into its **debt**, and the user or Architect can revoke the freedom. This file covers the dungeon-side and
pack-side policy. Related files: town buying and selling (TownKit, `town_sell_count`, shops, stash, house) is in
[goals-and-plans.md](goals-and-plans.md); gear comparison and the loadout/gear evaluator (`gearcmp`, `loadout`,
`gear_better`) are in [gear-and-estimator.md](gear-and-estimator.md); every `pilotctl` command is in
[commands.md](commands.md); the tick loop, report and logs are in [pilot-core.md](pilot-core.md).

## 1. What an item is worth: `itemvalue.py`

`itemvalue.value(name, level=15, aware=())` parses an item's **display name** (as the game shows it, e.g.
`a Pair of Soft Leather Boots of Free Action [2,+4]`, `5 Potions of Cure Light Wounds`,
`a Wand of Stinking Cloud (12 charges)`) and returns an `Item`. `level` is the dungeon level it came from (for
expectations); `aware` is the set of kind names already known (from the flavour table). Run
`python3 itemvalue.py "NAME" ...` to print values.

**Sources.** The server's edit files (`lib/edit/object.txt`, `ego_item.txt`, `artifact.txt`; parsed at import into
`KINDS`, `EGOS`, `ARTIFACTS`) and, for things not yet known, the rulebook CSVs in `tools/rulebook/`:
`kinds_by_level.csv` (unknown flavours, mean charges), `feelings.csv` (pseudo-ID'd gear), `jewellery.csv` (rings and
amulets with unknown plusses).

**The formula** mirrors the server's `object_value_real()` (object2.c):

| Part | Value |
|---|---|
| base | kind cost (`W:` line), or the artifact's cost instead; + the ego's cost |
| pval flags | per +1: STR/INT/WIS/DEX/CON/CHR 200, STEALTH/SEARCH 100, INFRA/TUNNEL 50, BLOWS 2000; SPEED 25000 (amulet), 50000 (ring), 100000 (anything else) |
| plusses | +100 per to-hit, to-dam, to-AC (weapons, armour, jewellery); ammo +5 per to-hit/to-dam |
| extra dice | weapons: +100 x (extra dice x sides) over the kind's dice |
| charges | wands/staffs: +5% of value per charge (per item of a stack) |
| zero | cursed, broken, worthless, terrible tags; `Broken ...`; a negative pval; negative AC/plusses (armour, jewellery); to-hit + to-dam < 0 (weapons) |

**Estimates** (`Item.estimate = True`, and `known = False` where an identify would reveal more):

- **Unknown flavour** (`a Bloodstone Ring`, `Scroll titled "..."`): expected value over the kinds of that type at that
  level, renormalised over the kinds not yet known (`unknown_flavour_value`); fallback `UNKNOWN_FLAVOUR` per type.
- **Known jewellery kind, plusses not shown** (a Ring of Protection with no `[+N]`): `jewellery_unknown` gives E[value]
  and P(cursed copy). Kinds whose copies are all alike (Free Action, resists) are valued exactly.
- **Pseudo-ID'd weapon/armour** (`{good}`, `{excellent}`, `{special}`, `{magical}`): the median value of that kind at
  that level and feeling (`feeling_value`), with `p_irreplaceable` = chance of an ego you can't buy back; fallback
  `PSEUDO_BONUS`. `{average}` adds nothing; worthless/cursed/broken/terrible are 0.
- **Unfelt weapon/armour** (no plusses, no feeling yet): the expectation over what `apply_magic` rolls at that level
  (good / great / plain odds from the server), `unfelt = True`.
- **Wands/staffs with unknown charges**: + the kind's mean charges.

**Other fields**: `count` (stack size; `.value` is for one), `kind`, `tval`, `ego`, `artifact`, `flags`,
`pseudo` (the feeling), `p_cursed`, and `irreplaceable` = gear or jewellery carrying any of `IRREPLACEABLE_FLAGS`
(Free Action, See Invisible, the base and poison/blind/conf resists, Hold Life, Speed, Telepathy, Regen).

**What a shop pays** (`pilot.py: SHOP_CUT = 0.38`, `Pilot.pay_cut(tval)`): the value a sale realises is
`value x pay_cut`. `pay_cut` takes the best buying factor among the shops that buy that tval (`BUYERS`), using the
owner last seen in each shop (`stores.json`) and the current CHR via `observe/shopmath.py`; for a shop never seen, the
average of its possible owners. `SHOP_CUT` (38%, Dive04 at CHR 3) is only the fallback when nothing is known.

`Pilot.iv(name)` is the wrapper everything uses: it calls `itemvalue.value` with the current depth (or the deepest
reached, or 750 ft) and the kinds the flavour table already knows.

`kinds.csv` (one row per flavoured kind: cost, flags, sell ranges, `id_scroll_pays`) is legacy: it is read only as a
fallback in `load_flavours` when `rulebook/kinds_by_level.csv` is missing, and a unit test checks the rulebook gives
the same 38 junk kinds.

## 2. Pickup and loot

**Pickup** happens in the tick (`pickup` order `all`; anything else turns it off): after a step, a recent
`You see X` message for the square underfoot is judged, then the Pilot stays (`custom ,`) to pick it up. Skipped:

- known junk (`is_junk_name`): left, and destroyed where it lies at a quiet moment (`destroy_floor_junk`, `k` with the
  floor index, once per sighting);
- squares in `skipped_items` (junk left before, items the Navigator dropped);
- the tavern stash items in town (`is_stash_item`);
- while fleeing (Flee, BandLeave, WalkAway) with monsters in view, anything worth under 500;
- whatever `pickup_room(name)` refuses.

**`pickup_room(name)`** decides by *worth* = `max(value x pay_cut x count, kit_use_value)`:

1. Names matching the Navigator's `nopickup` list: never.
2. Known, worth < 1 gold, not irreplaceable, not a unique's drop: left.
3. **Weight**: heavy gear (weapons/armour by `geareval.Item.weight`, staffs 5 lb) that would push the pack past the
   slow-down line (`weight_room`: half of `adj_str_wgt x 100`, xtra1.c) is left unless worth `HEAVY_LOOT_MIN` (300),
   irreplaceable, or a unique's drop. If something in the pack heavy enough is worth less than 1/1.5 of it (+5), that
   is destroyed first. News: "left NAME ... would slow you", once per item and level.
4. A free slot (of 23) or a stack it joins: pick up.
5. **Pack full**: first use something up (a lone flask into a lantern under 14000 turns; a lone food item eaten if it
   won't make us Gorged), then destroy the cheapest item by `pack_value` if the find is worth > 1.5x it + 5 (a unique's
   drop may push out only things under `UNIQUE_DROP_BUMP` = 50). Otherwise: "left NAME: pack full and nothing cheaper",
   once per item and level.

**`pack_value(it)`** (what an item is worth to the pack when making room): **priceless** (never destroyed for room) =
kit consumables (`is_kit_item`: potions/scrolls of `KIT_KINDS` -- cures, Phase, Recall, Teleport, Identify, Magic
Mapping, Speed, Heroism, Berserk, Restore, Deep Descent, Resist Poison), kept items, possible ability sources, the
best light, the last meal, the lantern's needed oil, items waiting in the review queue. Spare lights, food beyond the
ration supply, and spare flasks are worth their sale price. Flavour-table junk and cursed/worthless items are 0.
Everything else: value x pay_cut x count. `destroy_count` never destroys rations and keeps the last other food.
`kit_use_value` values a kit consumable found in the dungeon at its replacement cost (last Alchemist price, else
`KIT_USE`: Speed 600, Healing 1500, Berserk 500, ...).

**Loot fetching** (`loot_step`, used by the Dive and Explore goals): walks to items within `loot_radius` (order, 10);
items passed up while monsters mattered, within `LOOT_OWED_R` (25) once clear; devices and jewellery (glyphs `- _ = "`)
within `LOOT_VALUABLE_R` (30). Gives up on a square after 3 interrupted walks or a path longer than 1.5x the reach.
`loot_blocked` stops detours while a mobile monster that matters is in view (not weak ones 10+ levels below us), a band
was warned in the last 90 s, HP is under `think_hp`, or we're blind/confused. `loot_beside` lets a dive walking to the
stairs detour up to `LOOT_PATH_R` (3) squares.

Also (in `policy_tick`, when idle): fetching a slain unique's drop (items within 3 squares of where it died, for 5
minutes) and gold within 10 squares. **`interesting_item` news**: devices, jewellery and `{excellent}/{special}` items
seen on the level map that aren't known junk; within reach the Pilot fetches them, farther ones tell the Navigator to
`goal fetch Y,X` (a dive outside a trip plan pauses 20 s). Picking up a likely-special item gives `found` news
("identify it before selling").

## 3. Destroying junk

| Mechanism | What | When |
|---|---|---|
| `auto_destroy` | pack devices/scrolls/potions identified as a kind on the `junk` order or `JUNK_DEVICES` (Haste Monsters, Clone Monster, Heal Monster); then pack items whose pseudo-ID feeling is on `autodestroy` | no monsters in view, not in a shop, every 2 s; skips kept items and anything inscribed with `@` (or `!` in the feeling tag) |
| `destroy_floor_junk` | known junk underfoot | a quiet moment (`quiet_moment`: no mobile monster in view, not hit for 5 s, HP >= think_hp, not fleeing/recalling/recovering, not blind/confused) |
| make-room destroys | the cheapest pack item | in `pickup_room` (above) |

**`is_junk_name`**: a name containing `of <junk>` for any `junk` order entry; spellbooks for a warrior; `Broken`; a
feeling on the `autodestroy` list; or a flavour the flavour table marks junk (even if the character isn't aware of it).

## 4. Identify and flavour learning

**`policy_tick`** (every 3 s at a safe moment: no monsters in view, not hit for 8 s, HP >= 50%, not blind/confused,
not fleeing/recalling/recovering/shopping) runs, in order: quaff a Restore for a drained STR/DEX/CON; fetch a unique's
drop; fetch nearby gold; `identify_step`; `upgrade_step`.

**`identify_step(minimum=20)`**: with a Scroll of Identify or a charged Staff of Perception, identify the best
candidate from `identify_candidates`: unknown items (`iv.known is False`, not junk) ranked by expected sale value;
**ability sources and items with `p_irreplaceable >= 0.2` come first** (infinite priority). Needs a worn light to
read (wears one if not). Three tries per item. In town, `town_identify_wanted` counts candidates worth at least twice
the Identify price (the TownKit buys scrolls for them).

**The flavour table** (`runs/flavours.json`, server-wide: flavours are fixed per server, so all characters share it;
`{flavour: {kind, junk, source}}`). Learned three ways:

- **identified** -- `learn_flavours_tick` watches for the game's "In your pack: ... (x)" line after an Identify aimed at
  an unknown flavour (`id_target`);
- **identified or used** -- after any quaff/read/use/aim/zap/eat (`watch_flavours` snapshots the pack): if exactly one
  unknown flavour of a type vanished and one known kind of that type appeared (or "You have no more X" said so), they
  are the same;
- **sold in a shop** -- the sale identifies it (Shop goal).

`junk` comes from `load_flavours`: a kind is junk when the rulebook says it is worthless or worth <= 1 gold at every
level. `flavour_of(it)` returns the table entry for an item the character isn't aware of yet (`unknown_flavour`:
flavoured tval or a Mushroom, no ` of ` in the name); `show()` adds "(= KIND; not aware)" in the `pack` listing.

**Rules for unknowns**: `unknown_sell_refusal` (used by selling): table-junk sells; one of a stack sells (a free
identification); a lone unknown scroll should be read; potions/scrolls sell while we've never been below 1000 ft;
deeper potions/scrolls, and all unknown devices and jewellery, should be identified first. `probably_special(name)`:
`{excellent}`/`{special}`/artifact tags, `{good}` gear with unknown plusses, or a unique's name in the tag -- not sold
until inspected (an identified plain item is never "special"). `watch_abilities` infers abilities from game messages
(`ABILITY_PROOFS`, e.g. "You are unaffected!" right after a paralysing touch = Free Action); the unidentified worn
items become `ability_sources`, which are never sold, dropped or destroyed for room, and are identified first.

## 5. Wearing upgrades

**`upgrade_step`** (from `policy_tick`; one change per call; off with `order autowear=off`):

1. **Weapon**: `weapon_table` lists every carried weapon's blows (`weapon_blows`, the server's warrior blow table at
   current STR/DEX) and damage per round (`weapon_damage`: dice average + to-dam, x blows; a brand from
   `weapon_brand` counts half its x3). Wields one doing > 1.2x the current, never cursed, never losing an ability the
   wielded one gives (`weapon_abilities`, from `rulebook/ego_flags.csv`), never replacing an artifact.
2. **Armour**, slot by slot: higher AC (`armour_ac`), plusses or a non-bad feeling known, not losing the worn piece's
   abilities, not over an artifact or an ability source.
3. **Jewellery into an empty ring/amulet slot**: identified, value > 0, not junk; the most valuable.
4. **In town**: better jewellery over a worn piece (same kind with a bigger bonus, or a piece whose abilities other
   gear already gives, `redundant_worn`): takes the old one off; step 3 puts the new one on.
5. **In town**: the gear evaluator's choice (`gear_better`, simulated fights; see gear-and-estimator.md), at most once
   per 30 s.

**`wear_step`** (after `wearall`): fills empty slots one per call, best light first, never unknown jewellery.
**`watch_weapons`** gives news when a carried weapon would beat the wielded one by 20%. **`watch_character`** alerts
on stat drains (pointing at the stash or the Alchemist for the Restore; an unseen drainer makes us leave the level) and
on blow changes. The Navigator's `wear` of unknown jewellery is refused unless `force`.

## 6. The review queue

Judgement calls go to the Navigator before they are irreversible. `review_hold(it)`, asked by the town sell policy,
holds an **identified wearable** (not a light) that the gear evaluator wouldn't wear and that is an **artifact**, gives
**an ability or resist** (`geareval.Item.abilities`), or is worth **`REVIEW_MIN_VALUE` (1000)+**. Held items are
priceless in `pack_value`, appear on the report's `Review (N, ...)` line with how many visits remain, and get a
`review` alert. Worn items leave the queue.

The Navigator answers `review sell|keep|wear NAME` (`review` lists): `keep` also adds it to the keep list; `wear`
wears it (in town; recorded as keep). **Undecided after 2 town visits** (counted by TownKit), the policy sells it.
State: `runs/pilot/NICK/review.json` (`items`, `decided`, `town_visits`).

## 7. Keep list, value refusals and the debt

**`keep NAME` / `keep -NAME` / `keep`** (`runs/pilot/NICK/keep.json`, lower-case name parts): a kept item is never
sold, destroyed or dropped by the policy and is priceless for room. Matching is by substring (singular too), so a
short entry protects every item containing it.

**`value_refusal(it, action)`** checks the Navigator's `sell`, `destroy` and `drop` (never the Pilot's or Architect's
own). Refused, with the reason:

- a kept item;
- an unidentified item that may be an ability source (identify first);
- unidentified with `p_irreplaceable >= 20%`, or worth ~30+ sold once identified (identify first);
- destroy/drop of an irreplaceable item, or of one a shop would pay ~20+ for (sell it instead).

Table-junk and cursed/worthless items are never refused. Selling also applies `unknown_sell_refusal` and
`probably_special`.

**Overrides and the debt** (the user's decision, restructure-step2.md, 2026-10-23): the Navigator may prefix `!`
(`sell !NAME`, `destroy !NAME`, `drop !NAME`). If the policy would have refused, the fair value lost is added to its
**item debt** (`add_debt`): for a sale, fair pay at that owner (`shopmath.fair_pay` from the relist price, else
value x pay_cut) minus what was received; for destroy/drop, value x pay_cut. Hunts have a separate **fight debt**
(`settle_hunt`): a hunt ordered over the Pilot's refusal (`goal hunt !NAME`) that ends unslain, with HP under 50%, or
with an emergency escape adds the HP lost (see pilot-combat.md). Both live in `runs/pilot/NICK/navigator_debt.json`
(`entries`, `fight_entries`); `debt` shows totals and the last 8 of each. The limit is **a judgement, never a
number**: the user or Architect revokes overrides by creating `runs/private/NICK.overrides_revoked` (or
`NICK.hunt_overrides_revoked`; the text says why), checked by `override_allowed`; deleting the file restores them.
Every mission prompt states the current debt.

**Where the Navigator may act**: in the dungeon, `wear`, `takeoff`, `pickup`, `fuel`, `eat`, `inscribe`, `wearall`
and identify-type reads are refused (`DUNGEON_ITEM_CMDS`); `destroy`, `drop`, `order nopickup=...` and `keep` work
everywhere. `item_index` resolves letters (pack `a`.., equipment `A`..) or name parts (whole word first; errors on
ambiguity); `pack_now` re-reads the pack after an action so letters aren't stale.

## 8. Orders (`DEFAULT_ORDERS`)

Set with `order KEY=VALUE` (typed like the default), listed with `orders`, saved in `runs/pilot/NICK/orders.json`
(saved values override the defaults). Item orders first; the rest are explained in pilot-combat.md / goals-and-plans.md.

| Key | Default | Meaning |
|---|---|---|
| `pickup` | `all` | `all` picks up by policy; anything else (`none`) picks nothing up (but `loot_step` still walks to items within `loot_radius`: set that to 0 too) |
| `loot_radius` | 10 | dive/explore fetch items this close (0 = off) |
| `nopickup` | `` | comma list of name parts never picked up (the Navigator's per-trip junk list) |
| `junk` | Salt Water, Blindness, Weakness, Sleep, Poison, Lose Memories, Confusion, Sickliness, Apple Juice, Slime Mold, Darkness, Aggravate Monster, Curse Weapon, Curse Armour, Summon Undead, Summon Monster, Treasure Detection, Detect Invisible | items "of" these aren't picked up; identified potions, scrolls and devices of these in the pack are destroyed |
| `autodestroy` | `worthless,cursed` | pseudo-ID feelings whose items are destroyed (add `average`) |
| `autowear` | `on` | `off`: no wielding/wearing/swapping by the Pilot (`upgrade_step`) |
| `enchant_max` | 25 | Scrolls of Enchant Armor `plan town` may buy a visit (0: none) |
| `free_action` | `no` | `yes` once the character has Free Action (paralysers stop counting as danger; the sheet overrides once read, `has_ability`) |
| `resist_blind` | `no` | the same for blinding blows |
| `resist_conf` | `no` | the same for confusing blows |
| `flee_hp` | 0.5 | emergency below this HP fraction |
| `think_hp` | 0.65 | tell the Navigator below this while fighting; also the loot/quiet-moment HP floor |
| `rest_below` | 0.7 | rest when nothing is in view and HP is below this |
| `rest_to` | 0.95 | rest up to this |
| `arrival_pack` | 4 | this many monsters in view on arrival: leave by the stairs |
| `danger_level` | 6 | a monster this many levels above ours in view: leave/avoid |
| `unseen_hp` | `on` | `off`: HP loss with nothing in view isn't treated as an unseen attacker |
| `idle_recall_s` | 600 | no goal and no Navigator contact this long: recall to town |
| `stop_on` | `unique,danger` | what makes a dive stop and ask (also `items`, `pillared`) |
| `pillared` | `explore` | dive: explore pillared rooms for a `>` (or `ask`, `ignore`) |
| `choke` | `on` | meet packs in a corridor, not in the open |
| `band_frac` | 0.5 | a band is serious (leave) when fighting it all costs more than this x HP |
| `max_depth` | 0 | feet; 0 = no limit. Caps dives and plans; `order` warns past the clvl gate or below 1000 ft without Free Action |

## 9. Other helpers and constants

| Name | What |
|---|---|
| `flavour_key(name)` | `'2 Puce Potions {tried}'` -> `'Puce Potion'` (the flavour table key) |
| `kind_key(name)` | `'3 Wands of Magic Missile (10 charges)'` -> `'Wand of Magic Missile'` |
| `one_of(name)` | `'2 Potions of Boldness'` -> `'a Potion of Boldness'` (for news) |
| `heal_of(name)`, `HEALS` | HP a cure potion heals (server use-obj.c) |
| `STATUS_CURES` | which potions cure stun, poison, confusion, blindness, cheapest first |
| `USE_VERIFY` | items whose use the Pilot verifies by effect and resends (not unknown scrolls) |
| `stat_index`, `weapon_blows`, `weapon_brand`, `weapon_damage` | blows and damage per round (above) |
| `expect_effect` | records an expected effect of a command; `verify_effects` reports "no effect seen" after 3 s |
| `food_value`, `FOOD_VALUES` | food units per kind, to avoid eating into Gorged when making room |
| `has_ability(order)` | Free Action etc.: seen in play, else the character sheet's flags, else the order |
| `is_artifact(name)` | named artifact by its quotes or "the X of Y" |

## 10. What is logged

- Every command the Pilot sends is an `act` record in `decisions.jsonl` with its reason (`why`), e.g.
  `make room: destroy X (~12) for Y (~80)`, `autodestroy junk ...`, `identify X (policy)`, `wield X (~31/round vs ~22)`.
- Debt: `navigator_debt` (gold, what, why, total), `navigator_fight_debt`, `hunt_override_end`; sales: `sale` (with
  the relist price).
- Notifications (events; see pilot-core.md): `tactic` news for make-room destroys, left items, identify, wear/wield,
  learned flavours, fetches; `review` (held / auto-sold); `found`, `interesting_item`, `pack_full`, `ability`,
  `stat_drained`, `blows_changed`.
- Files: `runs/flavours.json` (server-wide), and per character in `runs/pilot/NICK/`: `keep.json`, `review.json`,
  `navigator_debt.json`, `orders.json`, `stores.json` (shop owners and prices, read by `pay_cut`).
