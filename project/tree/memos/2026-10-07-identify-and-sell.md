# Memo: unknown items, identify or sell? (Advisor → Architect, 2026-10-07)

**The user's request:** "Investigate an optimal item selling strategy", checking four claims:
(1) quaffing unknown potions out of combat is usually safe; (2) reading unknown scrolls and using
unknown staffs is sometimes dangerous (summoning); (3) most items sell for much more identified than
identifying costs; (4) a Staff of Perception with Recharging is usually cheaper than Identify scrolls.
**Audit trail:** `Advisor/studies/2026-10-07-selling/` (plan, 5 briefs, 5 dispatches, synthesis).
**Scripts and data:** `Advisor/data/identify/`: `kinds.py` → `kinds.csv` (249 flavoured kinds),
`dist.py` (exact kind odds from `get_obj_num` by object level), `value.py` (sale values and ID costs),
`hazards.py` (hazard odds, device fail). Our item history: `studies/…/scratch/L_items.csv` (87 rows).

## How this was made

Five Clerks: P (potions, quaff code), D (scrolls, staffs, wands, rods, rings, amulets), E (ID
mechanics: Identify, Perception, Recharging, shop buy/sell, pseudo-ID), F (forum corpus), L (every
unknown item in our missions, and the Pilot's rules). The Advisor computed every number by script
and opened the code lines the memo relies on (**[code ✓]**). One false alarm was resolved: F doubted
the 30–46% sale rate, but `store.c:217-225` gives 200 − buy% at CHR 4. The 100% cap only applies at high CHR.

## 1. Verdicts on the four claims

| claim | verdict | why |
|---|---|---|
| 1. quaffing unknown potions out of combat is usually safe | **True for survival, false for money** | Lethal kinds (Death L55, Detonations L60) are ≤0.03% of unknown potions at 0–1500 ft. But 25–42% are bad, and **12–16% at 250–750 ft drain STR, DEX or CON** (Weakness, Clumsiness, Sickliness). The drain never restores by itself, and Restore costs ~470 at the Alchemist. Mission 13's Puce Potion test cost Dive04 a blow (3 → 2). Cure potions quaffed at full HP **don't even identify**. |
| 2. unknown scrolls/staffs are sometimes dangerous | **True** | Summon Monster/Undead + Aggravate = **6–13% of unknown scrolls**. Staff of Summoning + Haste Monsters = 9–18% of staffs from 500 ft. Summons are 1–3 awake monsters of level dlv+5 (Ghouls from ~1050 ft; paralysis without Free Action). The bigger hidden danger is **jewellery: 19–58% of unknown rings and ~20% of amulets are cursed, a cursed one can't be taken off, and wearing never identifies it.** |
| 3. most items sell for much more identified than ID costs | **True for wands, staffs, rods, rings and amulets; false for potions and scrolls above ~1000 ft** | An unknown item sells at a flat base (potion/scroll 9, wand 15–20, staff 21–27, rod ~35, ring/amulet ~18). Expected value once known: devices and jewellery 50–700, potions and scrolls 19–54 above 750 ft. Identify costs 81. Dive03 sold 14 devices unknown for ~3,600 less than they were worth. |
| 4. Perception + Recharging is cheaper than Identify | **Barely, and not for us yet** | Long run 66–69 gold per ID against 78–81 for a full-price Identify (57–60 at 25% off). It needs a ~1,050-gold staff first (13 charges at ~80 each, no saving), Recharging is rarely stocked, and a failed recharge **destroys** the staff. |

## 2. The mechanics that decide the strategy [code ✓]

1. **Price depends on knowing the flavour, not on full ID.** Unaware items use a flat base per tval;
   once the flavour is aware they sell at the kind's cost. Only wands and staffs gain more from a full
   ID (+cost/20 per known charge). Known cursed or worthless items are worth 0 and **the shop refuses them**
   (`object2.c:1075-1112, 1252-1259, 1362-1398`, `store.c:541ff`).
2. **Selling identifies.** The shop pays the unknown price and *then* makes the flavour aware and the
   item known (`store.c:2134-2141`). So **selling one unknown item of a stack is a free, riskless ID**
   of the whole flavour. The rest of the stack, and every later find of that flavour, then sells at the real price. Buying from a shop
   also makes the flavour aware. Looking at a shop list doesn't.
3. **Use identifies only if you notice an effect** (`cmd6.c:219-229` and its staff, wand and rod
   versions). Otherwise the item becomes "tried". CLW/CSW/CCW at full HP, Neutralize Poison when not
   poisoned and Restore potions when not drained all stay unknown. Trap Creation never identifies.
4. **Wearing a ring or amulet never makes it aware** (no `object_aware` on the wield path). A cursed one
   says "Oops! It feels deathly cold!" and sticks: it can't be taken off, swapped or destroyed
   (`cmd3.c:372-385, 498-509, 638-648, 850-855`) until Remove Curse (Temple, ~155). The warrior's pseudo-ID
   covers only weapons and armour (`dungeon.c:196-238`), so there's no warning.
5. **Awareness is per character. Flavours are per server**: the seed is saved in `testserver/save/server` and rolled
   only for a new game (`save.c:1591`, `dungeon.c:2455`). L matched ~20 flavours between Dive03 and Dive04
   (e.g. Light Blue = Heroism, Magenta = Confusion, Lead Wand = Heal Monster, Rosewood Staff = Object
   Location, Puce = Weakness). **What one character learns tells every later character what the flavour is.**
6. **Device skill at clvl 10 ≈ 22** (−3 Half-Orc + 18 warrior + 7, `xtra1.c:2280-2829`). A use fails with
   probability ≈ 2/(skill − level) (`cmd6.c:477-501`). A failure costs a turn but no charge.

| device fail % (Half-Orc warrior) | clvl 10 | 15 | 20 | 25 | 30 |
|---|---|---|---|---|---|
| Staff of Perception (lvl 10) | 15–17 | 12–13 | 10–11 | 9 | 7–8 |
| **Staff of Teleportation (lvl 20)** | **67–83** | 33–40 | 20–22 | 15–17 | 12 |
| lvl 40 staffs (Speed, Earthquakes) | 98 | 98 | 98 | 97 | 95 |

## 3. Numbers (scripts in `data/identify/`)

**Hazard odds per unknown item** (`hazards.py`; object level ≈ dungeon level; ft = level × 50):

| | 100 ft | 250 ft | 500 ft | 750 ft | 1000 ft | 1500 ft |
|---|---|---|---|---|---|---|
| potion: STR/DEX/CON drain | 0.3% | 11.6% | 16.3% | 14.3% | 9.7% | 5.5% |
| potion: Lose Memories (exp −25%) | – | 0.1% | 7.4% | 6.4% | 4.2% | 2.3% |
| potion: any bad (incl. sleep, blind, salt water) | 25% | 29% | 40% | 36% | 42% | 24% |
| potion: lethal (Death, Detonations) | 0 | 0 | 0.01% | 0.02% | 0.03% | 0.03% |
| scroll: summon or aggravate | 13% | 12% | 6% | 9% | 8% | 7% |
| staff: Summoning or Haste Monsters | 7% | 0.5% | 18% | 17% | 12% | 10% |
| wand: helps the monster (Heal/Haste/Clone/Polymorph) | 31% | 18% | 14% | 22% | 23% | 19% |
| ring: cursed (sticks) | 45% | 58% | 38% | 38% | 19% | 20% |
| amulet: cursed (sticks) | 20% | 21% | 24% | 19% | 20% | 21% |

**What a shop pays for one unknown item, before and after learning its flavour** (`value.py`, mean owner;
Dive04 has seen 30% at the Magic shop and 40% at the Alchemist):

| tval | unknown | aware at 250 / 500 / 750 / 1000 / 1500 ft | known (charges) |
|---|---|---|---|
| potion | 9 | 20 / 31 / 54 / 87 / 748* | same |
| scroll | 9 | 19 / 25 / 33 / 295* / 262* | same |
| staff | 27 | 83 / 125 / 128 / 212 / 270 | 139 / 191 / 195 / 310 / 378 |
| wand | 20 | 126 / 117 / 119 / 155 / 194 | 206 / 181 / 184 / 230 / 290 |
| rod | 35 | 84 / 194 / 300 / 452 / 705 | same |
| ring | 18 | 50 / 98 / 118 / 187 / 206 (+ bonuses) | |
| amulet | 18 | 405† / 82 / 119 / 139 / 254 | |

\* means pulled up by rare jackpots (Acquirement 0.5% of scrolls from 1000 ft, stat potions 4% each at 1500 ft).
† boosted deep items only (amulets start at 500 ft). About 11–42% of potions and 11–18% of other kinds are
worthless once known.

**Cost of one identification:** Identify 78–81 (57–60 at 25% off; Alchemist, 4 of 32 stock entries, piles of
1–17). Staff of Perception: 6–20 charges, ~1,020–1,120 to buy (79–86 per charge). Recharging (310–322;
1 of 32 entries, piles of 1–5) at 0 charges adds 3–8 charges and backfires 10% of the time (more if
charges remain: 1/i, i = (150 − 10c)/15), and **a backfire destroys the staff** (`spells2.c:3118-3151`,
`SAFE_RECHARGE = false`; object.txt's "uncharges" is wrong). Long run: **66–69 per charge**.

**What we did:** ~15 unknown items per dungeon hour at 0–450 ft (half potions), ~7.5/h at 500–750 ft, where the
staffs, rods, rings and amulets turned up. 55 priced sales brought 1,185 gold against ~4,770 if they had been sold known.
Almost all of the gap is Dive03's 14 staffs, wands, rods and jewellery sold unknown for 20–42 each. Dive04: 2
Potions of Speed sold for 8 each (~45 lost), 2 wands identified for 162 that sold for 285 (net +93), and one
harmful test (Weakness, mission 13). The Pilot never uses or identifies anything itself. Since 67acff1 its shop goal
refuses to sell unknown flavours.

## 4. The strategy (proposal)

**One rule: learn a flavour by the cheapest safe route, then sell at the real price. The cheapest
safe route is usually selling one unknown item, not using it.**

1. **Flavour table (Pilot).** Keep a server-wide `flavour → kind` file, filled from every message that
   names both. Sources: "Selling a Lead Wand … You sold a Wand of Heal Monster", Identify results, use
   messages, shop purchases, the other characters' logs. Seed it with L's ~20 matches (`L_items.csv`). Show the
   kind in reports ("Puce Potion (= Weakness; not aware)"). Reset the table only if `save/server` is deleted.
2. **Never test-use these:** unknown rings and amulets (cursed ones stick, and wearing doesn't identify), unknown staffs
   (summoning; most fail anyway), and unknown scrolls in the dungeon. Only aim an unknown wand into empty space. Bolts,
   balls, Magic Missile, Stinking Cloud and Light identify that way. If it stays unknown, it's a targeted wand
   (Slow/Sleep/Confuse, or Heal/Haste/Clone) and goes to Identify.
3. **Potions: don't quaff-test by default.** Only test when all of these hold: a stack of 2 or more, HP ≤ 80% (so a cure
   identifies), no monster in view, food in the pack, and no STR/DEX blow breakpoint at risk. The table must not list
   the flavour as bad.
4. **In town, for each unknown flavour:**
   - **table says junk** (bad potion, cursed ring, Heal/Haste/Clone wand…): **sell it unknown.** The shop
     pays 9–20 now and refuses it once the flavour is known.
   - **a stack of 2 or more:** sell **one** unknown. That identifies the flavour, and then you keep, use or sell the rest at the real price.
   - **a single potion or scroll found above 1000 ft:** sell it unknown (expected gain from Identify 11–45 < 81).
   - **a single potion or scroll from 1000 ft or deeper:** Identify it (expected value 87–750).
   - **any wand, staff, rod, ring or amulet** not in the table: **Identify it** (81; expected gain 50–700). Then
     keep Free Action, See Invisible, the resists, Teleport Other, Slow/Sleep/Confuse Monster and Rods of
     Illumination/Light/Door location, and sell the rest.
5. **Buy Identify when it's discounted** (`{25% off}` = 57–60). Keep 2–3.
6. **Staff of Perception: not now.** Use one if found (8–9% of unknown staffs at 500–750 ft). Buy one
   only when trips identify more than ~13 items, around 1000 ft. Recharge only at 0 charges.
7. **Sell to the right owner:** quote first (offering an item shows the price). Never sell to the Black market (1/3).

## 5. Contradictions with current docs

| where | says | should say |
|---|---|---|
| HANDBOOK ~l.179 | put on an unknown ring or amulet when that slot is empty | don't: 19–58% are cursed and stick, and wearing doesn't identify; Identify first |
| HANDBOOK ~l.254 vs ~l.287-291 | "sell unknown potions/scrolls found early" vs "don't sell unknown potions/wands/staffs from 200 ft+" | §4 rule 4 (by stack, depth and tval) |
| HANDBOOK ~l.242 | don't quaff unknown potions without food | plus HP ≤ 80%, a stack of 2 or more, no STR/DEX breakpoint (§4.3) |
| Pilot shop goal (67acff1) | refuses to sell any unknown flavour unless `!` | allow: one of a stack, table-junk, potions/scrolls from above 1000 ft |
| shops memo §3 / §5 | "save for a Staff of Teleportation (3,100+)", the backup escape | **fails 67–83% at clvl 10, 33–40% at 15, ~20% at 20**: not an escape before clvl ~20 |
| object.txt (Recharging) | failure "uncharges" | the code destroys the staff (`SAFE_RECHARGE=false`) |
| object.txt (Sleep potion) | 3+1d4 turns | 4–7 ticks; Salt Water also paralyses 4 and starves, and Free Action doesn't help |
| Navigator mission 10 note | unknown potions were quaffed as "CLW" | they never ran (held quaffs; no `q` act sent) |

## 6. Coverage and gaps

- Code read: quaff, read, use, aim, zap and wield paths, store buy/sell/price, recharge, identify, pseudo-ID, curse
  handling, object generation. Not read: activation, Banishment and Acquirement internals, player shops
  (store 8).
- Object level is taken as the dungeon level. Monster drops use other levels and "good" drops (not modelled).
  Ring and amulet bonuses (+AC, +dam, pval) aren't in the value table, so their known value is understated.
- Dive04's actual INT (±1 device skill) and the exact Magic-shop owner rates per visit weren't checked.
- Dive04's identified Staff of Object Location (16 charges, 09-29 23:07) disappears from the logs with no
  sale, drop or loss message (L). Unexplained.
- Forum (F): players do use-ID shallow, read scrolls on a `>` of a cleared level, and never wear unknown
  jewellery. The only disasters reported are cursed Rings of Teleportation. They agree with §4. No post compares
  the costs of Perception and Identify.
