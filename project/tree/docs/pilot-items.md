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

**Where the code is** (E1 step 3): the methods below live in `tools/pilot/items.py` as `ItemsMixin` (still `Pilot`'s
names), with `weapon_blows`/`stat_index` and the blow tables; in combat.py (`CombatMixin`, E1 step 5;
pilot-combat.md): `has_ability`, `watch_character`, `teleport_item`, `use_stair_location`, `heal_of`, `STATUS_CURES`;
in commands.py (`CommandsMixin`, E1 step 6; commands.md): the command side (`item_action` with `parse_item_args`/
`action_refusal`/`action_reply`, `item_index`, `pack_now`, `DUNGEON_ITEM_CMDS`); still in pilot.py:
`expect_effect`/`verify_effects`. The town side (`identify_candidates`, `town_sell_count`,
`kit_count`, `lantern_fuel`, `provisions_spare`, `KIT_ITEMS`, `FLASK_FUEL`, `TURNS_PER_DMIN`, ...) is in `town.py`
(`TownMixin`, E1 step 4; goals-and-plans.md).

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
| zero | cursed, broken, worthless, terrible tags; `Broken ...`; a negative pval; a negative to-AC (armour); any negative plus (jewellery); to-hit + to-dam < 0 (weapons) |

**Estimates** (`Item.estimate = True`, and `known = False` where an identify would reveal more):

- **Unknown flavour** (`a Bloodstone Ring`, `Scroll titled "..."`): expected value over the kinds of that type at that
  level, renormalised over the kinds not yet known (`unknown_flavour_value`); fallback `UNKNOWN_FLAVOUR` per type.
- **Mushrooms** (2.42.0, the user): an unknown one (`a Black Spotted Mushroom`) is worth the plain average value of the
  mushroom kinds not yet known (`unknown_mushroom_value`: the 26 food kinds with sval < 32 in object.txt; ~80 gold with
  none known); a known one (`a Mushroom of Restoring`) its kind's value. Both were 0 before.
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

**What a shop pays** (`shopmath.SHOP_CUT = 0.38`, `Pilot.pay_cut(tval)`): the value a sale realises is
`value x pay_cut`. The rule is `observe/shopmath.py: pay_cut(tval, chr, owners_seen)` (D9, 2026-11-01: moved out of
the Pilot so the scorecard uses the same one; the Pilot keeps its cache and passes the owners from `stores.json` and
the current CHR): the best buying factor among the shops that buy that tval (`shopmath.BUYERS`, `Pilot.BUYERS` is the
same table; spellbooks at the Temple and the Magic Shop since D3), using the owner last seen in each shop; for a shop
never seen, the average of its possible owners. `SHOP_CUT` (38%, Dive04 at CHR 3) is only the fallback when no shop
buys the tval.

`Pilot.iv(name)` is the wrapper everything uses: it calls `itemvalue.value` with the current depth (or the deepest
reached, or 750 ft) and the kinds the flavour table already knows.

The junk kinds come from `rulebook/kinds_by_level.csv` alone (`load_flavours`; the file must exist): 38 kinds, checked
by a unit test. The old `kinds.csv` and its fallback were removed in session 10 (C10).

## 2. Pickup and loot

**Pickup** happens in the tick (the pickup reflex, `_reflex_pickup` in combat.py; `pickup` order `all`; anything else
turns it off; not with a monster adjacent or in a store): after a step, a recent
`You see X` message for the square underfoot is judged, then the Pilot stays (`custom ,`) to pick it up. Skipped:

- known junk (`is_junk`, below): left, and destroyed where it lies at a quiet moment (`destroy_floor_junk`, `k` with the
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
5. **Pack full**: first use something up (a flask into the lantern: a lone one under 14000 turns, from a bigger stack
   only when the lantern takes a whole flask (<= 7500 turns); food eaten, a lone item first, if it won't make us
   Gorged), then destroy the cheapest item by `pack_value` if the find is worth > 1.5x it + 5 (a unique's
   drop, whatever its estimate, may also push out anything under `UNIQUE_DROP_BUMP` = 50). Otherwise: "left NAME: pack full and nothing cheaper",
   once per item and level.

**`pack_value(it)`** (what an item is worth to the pack when making room): **priceless** (never destroyed for room) =
kit consumables (`is_kit_item`: potions/scrolls of `KIT_KINDS` -- cures, Phase, Recall, Teleport, Identify, Magic
Mapping (with `--live` only, 2.48.0), Speed, Heroism, Berserk, Restore, Deep Descent, Resist Poison), kept items, possible ability sources, the
best light, the last meal, the lantern's needed oil, items waiting in the review queue. **Mushrooms are not
priceless food** (2.42.0): they are valued like any item (`itemvalue`: expected value when unknown; 0 when junk). Spare lights, food beyond the
ration supply, and spare flasks are worth their sale price. **In the dungeon, food (not mushrooms) and flasks go by
need** (2.41.0, the user): `supply_spare` counts what the stomach (`FOOD_MID`) or the worn lantern and the other stacks
don't cover until `supply_horizon` (the trip's `trip_minutes_left`, else `SUPPLY_UNKNOWN_DMIN` = 40, plus
`SUPPLY_MARGIN_DMIN` = 5 dungeon minutes); spare units are worth their sale price and are what `destroy_count`
destroys; with none spare, the stack is worth the minutes of the shortfall it covers x `gold_per_dmin` (gold + XP at
`xp_per_gold`, from the rate buckets) and is destroyed whole only for a find worth 1.5x that. Kept items stay
priceless. In town the old rules hold (rations never destroyed; spare flasks only near a trip's end). Flavour-table junk and cursed/worthless items are 0,
food, flasks and lights included (the junk test runs first, A17, 2.40.0); kit, kept and ability items stay priceless.
Everything else: value x pay_cut x count. (2.48.0: a fallback while its kit kind is short is priceless too, a dungeon
stopgap goes by need and a Scroll of Enchant/Recharging the kit would read is priceless in town -- below.)
`destroy_count`: in the dungeon, the spare units of food and flasks (above), and none of a stopgap while its primary is
short. In town: never rations; other food
(not a ration or a mushroom: a Slime Mold, Waybread, Jerky...) keeps one piece when it's the only food carried (3 Slime
Molds and no rations: 2 may go; with rations: all 3).
`kit_use_value` values a kit consumable found in the dungeon at its replacement cost (last Alchemist price, else
`KIT_USE`: Speed 600, Healing 1500, Berserk 500, ...).

### Fallbacks, stopgaps, crutches and scrolls the kit would read (2.48.0, the user)

Two principles for a weaker substitute of a kit item (`town.py`, beside `town_sell_count`):

- **A. Fallback**: kept, and bought, only while the better kit item is **short**: below the kit's target and not in
  stock at an affordable price this visit. `FALLBACKS = {"Boldness": "Heroism"}` (Heroism is the kit's fear cure; the
  Temple runs out). `fallback_kept(it)`: a Potion of Boldness while `kit_count("Heroism")` is under
  `kit_target("Heroism")` (kit B/C: 3; kit A: 0). In town it is then kept (`town_rule` "keep"), else sold by value. After
  the shops, `TownKit._buying_fallback` buys Boldness at the Temple (4) for Heroism's shortfall, less the Boldness
  carried, once (`fallback_buys`; see goals-and-plans.md). In the dungeon a Boldness found while Heroism is short is a
  kit item: priceless in `pack_value`, its price as pickup worth (`kit_use_value`). `fear_cure` (combat) still quaffs
  Heroism > Boldness > Berserk.
- **B. Dungeon stopgap**: useful in the dungeon while the primary supply is short, but the primary is always on sale in
  town. So it is **sold in town**, and **in the dungeon kept, never auto-destroyed, and worth the dungeon time it covers
  while the primary is short** (`is_stopgap`, `stopgap_cover`, `supply_short`):
  - **Scroll of Satisfy Hunger** (for rations): `supply_short("food")` is what the stomach (`FOOD_MID`) and every food
    stack leave uncovered until `supply_horizon`; a scroll counts as `SATISFY_FOOD` (PY_FOOD_MAX - 2000) food. While
    short: `destroy_count` 0 (make-room and the weight shed take none), `is_junk` False (even on the `junk` order, on the
    floor too), `pack_value` = covered minutes x `gold_per_dmin` (at least its sale), pickup worth the same.
    Otherwise its sale value.
  - **Wooden Torch** while a lantern with fuel is worn or carried (`lantern_lit`): `supply_short("oil")` is what the
    lantern (worn, else the fullest carried) and the flasks leave uncovered; a torch covers its turns. The same
    protections while short; otherwise its sale value (before 2.48.0 the first spare light was always priceless). With
    no lantern the torch is the light: the old light rules hold. In town, torches are sold beside a lit lantern (a
    torch sells for 1 gold, under its value's cut, so `town_sell_count` lets that through).
  - **Potions of Cure Light Wounds in kits B and C** (their heals are CSW/CCW): sold in town (`clw_spare`: kit B/C, not
    when a 250-499 ft plan would buy CLW back for the supply gate, nor when the Navigator's buy list asks for CLW). Kit
    A buys CLW and keeps them. In the dungeon CLW stays a kit consumable (priceless for room).
  The kit is the one this visit shops for (`visit_kit`: `plan town kit=`, else by the planned depth, A < 500 ft <= B <
  1000 ft <= C); in the dungeon, the planned depth's.
- **Mushrooms in town**: sold like other non-ration food (their cures are the kit's potions), except `KEEP_MUSHROOMS`
  (Restore Strength, Restore Constitution, Restoring), which the town sells only as a ~490-gold Restore potion. Unknown
  ones follow the unknown-flavour rules. In the dungeon, the 2.42.0 expected value (unchanged). The Pilot doesn't eat
  a restore mushroom for a drain (`restore_potion` reads potions only): the Navigator can.
- **Scroll of Magic Mapping**: a crutch on the test server (`CRUTCH_SCROLLS`, `is_crutch`), as the mapping devices:
  sold in town, not a kit item (loot in the dungeon: its sale value, no kit pickup worth), and never read (the band
  leave and the flee skip it). With `--live` it is the kit's again. Deep Descent (travel) stays a kit scroll.
- **Scrolls of Enchant Armor / Enchant Weapon To-Dam / To-Hit and Recharging** (the user's addition): `scroll_use(it)`
  names what the town kit would read one on -- a worn piece or the wielded weapon whose next point is still >=
  `ENCHANT_MIN_CHANCE` (`enchant_plan`, `weapon_enchant_plan`), a device `recharge_wanted` names. Such a scroll is never
  sold (found in the dungeon or bought), priceless for room in town, worth its price in the dungeon; the town kit reads
  it before buying more (`enchant_buys` subtracts the scrolls carried). Only scrolls nothing would use are sold.
`town_rule(it)` returns the rule and why; `price LETTER` shows it on the policy line ("kept (Heroism's fallback:
Heroism 1/3, short (kit B))", "sold by plan town (a crutch on the test server)", and in the dungeon a stopgap's
covered minutes).

**Loot fetching** (`loot_step`, used by the Dive and Explore goals; only with order `pickup=all`): walks to items
within `loot_radius` (order, 10); items passed up while monsters mattered, within `LOOT_OWED_R` (25) once clear;
devices and jewellery (glyphs `- _ = "`) within `LOOT_VALUABLE_R` (30). Gives up on a square after 3 interrupted walks or a path longer than 1.5x the reach.
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
| `auto_destroy` | pack items `is_junk` calls junk (below; refactor-candidates D3, 2026-11-01: before, devices/scrolls/potions of a `junk` order kind or `JUNK_DEVICES`, then the `autodestroy` feelings) | not busy, every 2 s |
| `destroy_floor_junk` | known junk underfoot | a quiet moment (`quiet_moment`: no mobile monster in view, not hit for 5 s, HP >= think_hp, not fleeing/recalling/recovering, not blind/confused) |
| make-room destroys | the cheapest pack item | in `pickup_room` (above) |

**`is_junk(it)`** (a pack item or a name; D3, 2026-11-01: one rule for pickup, the floor, the pack, the report's Items
line and the far-item notices; the user's decision: the union of the three old lists). Never junk: a kept item, or one
inscribed with `@` (or `!` in a tag), or (2.48.0) a dungeon stopgap while its primary is short. Junk: `of <kind>` as a whole word for a `junk` order entry or `JUNK_DEVICES` (Haste
Monsters, Clone Monster, Heal Monster), or the bare name (Slime Mold); a kind the rulebook marks junk (`junk_kinds`); a
flavour the flavour table marks junk (even if the character isn't aware of it); `Broken`; a feeling on the
`autodestroy` order; for a warrior, the spellbooks the town sells (`town_books()`: the rulebook's shop_stock.csv,
tvals 90/91 at the Magic-User store and the Temple). Books found only in the dungeon are loot (itemvalue values
them at their kind's cost).

## 4. Identify and flavour learning

**`policy_tick`** (every 3 s at a safe moment: no monsters in view, not hit for 8 s, HP >= 50%, not blind/confused,
not fleeing/recalling/recovering/shopping) runs, in order: eat when Hungry (2.45.2; Weak is the hunger reflex's); quaff a Restore for a drained STR/DEX/CON; fetch a unique's
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
  unknown flavour of a type vanished and one known kind of that type appeared (or "You have no more X" said so, X's type
  matching the vanished one's), they are the same; `learn_flavour` refuses any pairing whose type words differ;
- **sold in a shop** -- the sale identifies it (Shop goal).

`junk` comes from `load_flavours`: a kind is junk when the rulebook says it is worthless or worth <= 1 gold at every
level. `flavour_of(it)` returns the table entry for an item the character isn't aware of yet (`unknown_flavour`:
flavoured tval or a Mushroom, no ` of ` in the name); `show()` adds "(= KIND; not aware)" in the `pack` listing.

**Rules for unknowns**: `unknown_sell_refusal` (used by selling): table-junk sells; a flavour the table knows as a non-junk kind doesn't (use or identify it);
one of a stack sells (a free
identification); a lone unknown scroll should be read; potions/scrolls sell while we've never been below 1000 ft;
deeper potions/scrolls, and all unknown devices and jewellery, should be identified first. `probably_special(name)`:
`{excellent}`/`{special}`/artifact tags, `{good}` gear with unknown plusses, or a unique's name in the tag -- not sold
until inspected (an identified plain item is never "special"). `watch_abilities` infers abilities from game messages
(`ABILITY_PROOFS`, e.g. "You are unaffected!" right after a paralysing touch = Free Action); the unidentified worn
items become `ability_sources`, which are never sold, dropped or destroyed for room, and are identified first.

## 5. Wearing upgrades

**`upgrade_step`** (from `policy_tick`; one change per call; off with `order autowear=off`; the code numbers these
steps 2-6, as gear-and-estimator.md does):

1. **Weapon**: `weapon_table` lists every carried weapon's blows (`weapon_blows`, the server's warrior blow table at
   current STR/DEX) and damage per round (`weapon_damage`: dice average + to-dam, x blows, read by `geareval.Item` since D6; a brand from
   `weapon_brand` counts half its x3). Wields one doing > 1.2x the current, never cursed, never losing an ability the
   wielded one gives (`weapon_abilities`, from `rulebook/ego_flags.csv`), never replacing an artifact.
2. **Armour**, slot by slot (the code's "step 3"): plusses or a non-bad feeling known, and better AC than worn by
   `ac_better` (D13, 2026-11-01: the gear evaluator's verdict -- more AC, every ability and resist kept, no >5% EHP
   loss; a plain AC comparison with the old artifact/ego guards only for what geareval can't read; never over an
   ability source).
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
wears it in town (recorded as keep; in the dungeon it's only kept, not worn, and the reply says so). **Undecided after 2 town visits** (counted by TownKit), the policy sells it.
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

**Overrides and the debt** (the user's decision, history/restructure-step2.md, 2026-10-23): the Navigator may prefix `!`
(`sell !NAME`, `destroy !NAME`, `drop !NAME`). If the policy would have refused (for a sale: any `!` sale), the fair value lost is added to
its **item debt** (`add_debt`): for a sale, fair pay at that owner (`shopmath.fair_pay` from the relist price, else
value x pay_cut) minus what was received; for destroy/drop, value x pay_cut. Hunts have a separate **fight debt**
(`settle_hunt`): a hunt ordered over the Pilot's refusal (`goal hunt !NAME`) that ends unslain, with HP under 50%, or
with an emergency escape adds the HP lost (see pilot-combat.md). Both live in `runs/pilot/NICK/navigator_debt.json`
(`entries`, `fight_entries`); `debt` shows totals and the last 8 of each. The limit is **a judgement, never a
number**: the user or Architect revokes overrides by creating `runs/private/NICK.overrides_revoked` (or
`NICK.hunt_overrides_revoked`; the text says why), checked by `override_allowed`; deleting the file restores them.
Every mission prompt states the current debt.

**Where the Navigator may act**: in the dungeon, `wear`, `takeoff`, `pickup`, `fuel`, `eat`, `inscribe`, `wearall`
and identify-type reads are refused (the command table's `where` town / town_target entries, `DUNGEON_ITEM_CMDS`); `destroy`, `drop`, `order nopickup=...` and `keep` work
everywhere. `item_index` resolves letters (pack `a`.., equipment `A`..) or name parts (whole word first; errors on
ambiguity); `pack_now` re-reads the pack after an action so letters aren't stale.

## 8. Orders (`DEFAULT_ORDERS`)

Set with `order KEY=VALUE` (typed like the default; every pair is checked first and a bad one changes nothing,
with a usage error -- A22, 2.40.0), listed with `orders`, saved in `runs/pilot/NICK/orders.json`
(saved values override the defaults). Item orders first; the rest are explained in pilot-combat.md / goals-and-plans.md.

| Key | Default | Meaning |
|---|---|---|
| `pickup` | `all` | `all` picks up by policy; anything else (`none`) picks nothing up and makes no loot walks (`loot_step`) |
| `loot_radius` | 10 | dive/explore fetch items this close (0 = off) |
| `nopickup` | `` | comma list of name parts never picked up (the Navigator's per-trip junk list) |
| `junk` | Salt Water, Blindness, Weakness, Sleep, Poison, Lose Memories, Confusion, Sickliness, Apple Juice, Slime Mold, Darkness, Aggravate Monster, Curse Weapon, Curse Armour, Summon Undead, Summon Monster, Treasure Detection, Detect Invisible | items "of" these aren't picked up; identified potions, scrolls and devices of these in the pack are destroyed |
| `autodestroy` | `worthless,cursed` | pseudo-ID feelings whose items are destroyed (add `average`) |
| `autowear` | `on` | `off`: no wielding/wearing/swapping by the Pilot (`upgrade_step`) |
| `enchant_max` | 25 | Scrolls of Enchant `plan town` may buy a visit, Enchant Armor and (2.46.0) Enchant Weapon To-Dam / To-Hit together (0: none; with 0 a lost plus is valued at resale, gear-and-estimator.md §3.1) |
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
