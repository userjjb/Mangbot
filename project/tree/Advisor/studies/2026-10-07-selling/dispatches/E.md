# Dispatch: Identification mechanics and costs (assignment E, pass 1)
- Brief: formulas for Identify, Staff of Perception, Recharging, selling/buying and warrior pseudo-ID, with code lines.
- Clerk run: 2026-10-07; sources: github/src/server/{store.c, spells2.c, use-obj.c, cmd6.c, object2.c, object1.c, dungeon.c, init1.c, init2.c, xtra1.c, tables.c, mdefines.h}, lib/edit/{object.txt, p_class.txt, p_race.txt, shop_own.txt}, memos/2026-09-29-shops.md (read §1). Paths below are relative to github/src/server/ unless noted. Store numbers are CODE indices (0 General, 1 Armoury, 2 Weapons, 3 Temple, 4 Alchemist, 5 Magic, 6 Black market, 7 Home).

## Answer
- Reading Identify (and the Staff of Perception) calls `object_aware` + `object_known` on one item. That makes the flavour aware and the item known (real value, charges visible). It does not set ID_MENTAL. Only *Identify* does that, and no shop stocks it.
- Selling an unknown item to a shop also makes it aware and known, but the price is fixed before that, from the unknown base value. Buying also makes the flavour aware. Looking at a shop list does not.
- The warrior's passive sensing covers weapons and armour only. It never touches jewellery, devices, potions or scrolls.
- Recharging backfire is 1/i with i = (strength+100-lev-10*charges)/15. A backfire destroys the staff (one of a stack). The object.txt text ("uncharges") is wrong for this server config.

## Findings
1. **Identify scroll** (sval 12, `mdefines.h:1641`): `use-obj.c:823-828` -> `ident_spell` -> `ident_spell_aux` (`spells2.c:2844-2900`). It runs `object_aware(p_ptr,o_ptr); object_known(o_ptr);` (`spells2.c:2886-2887`). `object_aware` sets `kind_aware[k_idx]` for the flavour (`object2.c:1027-1035`) and redraws all stacks of that kind. `object_known` sets ID_KNOWN and clears ID_SENSE and ID_EMPTY (`object2.c:987-1018`). Cancelling the item prompt keeps the scroll (`use-obj.c:826`). It works on any item including floor items. [SEEN]
   - *Identify* (sval 13) uses `identify_fully_item`, which also sets ID_MENTAL (`spells2.c:2991-2995`). Cost 1000, level 30. It appears in none of the store tables [SEEN: object.txt N:177, init2.c:1226-1305, no match].
   - Potions of Enlightenment and *Enlightenment* call `identify_pack` (`use-obj.c:683`, `spells2.c:373-387`), which identifies the whole pack. Rare. [SEEN]
2. **Staff of Perception** is `TV_STAFF` sval 5 = `SV_STAFF_IDENTIFY` (`mdefines.h:1542`, object.txt `N:326`, `I:55:5:0`, `W:10:0:50:400`, `A:10/1`). The staff sets aware + known on one item, same as the scroll (`use-obj.c:1132-1137`: `ident_spell`, `*ident=TRUE`, and `use_charge=FALSE` if you cancel the prompt). [SEEN]
   - **Initial charges** (same code for found and store stock; `apply_magic` -> `charge_staff`, `object2.c:3126-3129`, 2350): `pval = randint1(15)+5`, so 6..20, uniform, mean 13. object.txt `P:0:1d2` is ignored. Store stock goes through `apply_magic` (`store.c:981-985`), so stores sell it with 6..20 charges. Nothing in `store_create` or `mass_produce` makes it uncharged (`mass_produce` has no staff case, so the pile size is 1). [SEEN]
   - A staff you sell with 0 charges is accepted. It is valued at the base 400 and re-listed. So an uncharged staff can appear in stock only from player sales. [INFERRED from `store.c:541-643`, `object_value_real`]
3. **Price of a staff with N charges.** Value known = `cost + (cost/20)*(pval/number)` with integer division (`object2.c:1252-1259`) = 400+20N, then minus any discount. Store price = `(value*A+50)/100`, `A = max(100, min_inflate + racefactor + adj_chr_gold[CHR4] - 200)` (`store.c:184-246`; the displayed price uses `min_inflate`, `store.c:1085`). Per charge that is 20*A/100 per charge plus 400*A/100 once.
   - Example, N=13: 660 base. At A=1.5 that is about 990, and at A=1.6 about 1056.
   - Buying: `store_purchase` makes a known copy for the price (`store.c:1752-1754`) and calls `object_aware` on it (`store.c:1835`). With a stack of staffs, `reduce_charges` takes the share. [SEEN]
4. **Device fail, clvl-10 Half-Orc Warrior.** `skill_dev = r_dev + c_dev + adj_int_dev[INT] + x_dev*lev/10` (`xtra1.c:2280, 2817, 2829`). Race R line gives -3 (p_race.txt:117). Warrior C gives 18 and X gives 7 (p_class.txt:85-86). At clvl 10 that is -3 + 18 + 7 = 22, plus `adj_int_dev` (0 for INT 3-7, +1 for INT 8-14; `tables.c:1274`). The Pilot should read the real skill from the char sheet, because I did not look up Dive04's INT.
   - `cmd6.c:477-509`: `chance = skill_dev - lev`, and lev = 10 for Perception. So chance = 12 or 13. Failure happens when `randint1(chance) < USE_DEVICE`, and USE_DEVICE = 3 (`mdefines.h:161`). P(fail) = 2/chance = **16.7%** (chance 12) or 15.4% (chance 13). Confusion halves chance first.
   - **A failure does NOT use a charge.** It takes a turn and returns before the `pval<=0` check and before `use_object` (`cmd6.c:488-497`). The charge is taken only in `do_cmd_use_staff_discharge` (`cmd6.c:521-560`, `pval--`). Empty staff: message "no charges left", sets ID_EMPTY, no charge or turn refund. The energy is already spent (`cmd6.c:466`). [SEEN]
   - Expected turns per successful use = 1/(1-0.167) = 1.2.
5. **Recharging** (`use-obj.c:889-893`, `recharge(p_ptr,60)` -> `recharge_aux`, `spells2.c:3093-3181`). It accepts only staffs and wands, which need not be known or aware.
   - `lev = k_info[].level` (10 for Perception). `i = (60 + 100 - lev - 10*(pval/number)) / 15` (integer division, per-item average charges). Backfire if `i <= 1 || one_in_(i)`, so P = 1/i.
   - For a lev-10 staff, scroll 60 (n=1), c = charges before reading:

     | c | i | P(backfire) |
     |---|---|---|
     | 0 | 10 | 10.0% |
     | 1 | 9 | 11.1% |
     | 2 | 8 | 12.5% |
     | 3 | 8 | 12.5% |
     | 4 | 7 | 14.3% |
     | 5 | 6 | 16.7% |

     Beyond that: c=6: 95/15=6, c=8: 70/15=4 (25%), c=10: 50/15=3 (33%), c=13: 20/15=1 (100% backfire).
   - Success: `t = 60/(lev+2)+1 = 6` (lev 10), `pval += 2 + randint1(t)`, so +3..+8, mean +5.5. It also clears ID_EMPTY. Expected gain per scroll at c=0 is 0.9 x 5.5 = 4.95.
   - **Backfire, with `SAFE_RECHARGE = false` in all three cfgs** (`github/mangband.cfg:71`, `testserver/mangband.cfg:71`, default `variable.c:184`): `reduce_charges(o,1)` (a stack of n loses pval/n; a single staff loses nothing there), then **one staff is destroyed** ("bright flash of light", `inven_item_increase(-1)`, `spells2.c:3126-3151`). The "safe" variant would drain charges instead, but it is off. [SEEN]
   - **Contradiction with object.txt** (`N:206`, lines 1706-1708): its text says failure "uncharges the wand or staff". The code destroys it. The formula (160-lev-10*charges)/15 and the success formula in the text do match the code. [SEEN]
   - Scroll of Recharging: level 40, cost 200, `A:40/1`. Spell strength 60 is fixed (mage spells use other strengths). Staffs stacked together are treated as one item with average charges. [SEEN]
6. **Selling to a shop** (`store_sell`, `store.c:1963-2078`; `store_confirm`, `store.c:2080-2200`):
   - **Price is quoted before identification.** `sell_haggle` (`store.c:1328-1383`) calls `price_item(p_ptr, &sold_obj, min_inflate, TRUE)`. `object_value(p_ptr,…)` returns the unknown base for unknown items: potion/scroll 20, staff 70, wand 50, rod 90, ring/amulet 45, food 5 (`object2.c:1075-1112`). Aware but not known gives the kind cost. Known gives `object_value_real` (staffs/wands + `cost/20` per charge). Cursed or broken known items give 0 (`object2.c:1362-1398`).
   - Only on confirm does `store_confirm` run `object_aware` and `object_known` (`store.c:2138-2141`). So **every sale identifies the item and the flavour**. The next item of that kind is quoted at its kind cost. A stack is sold at one price (price = unit x number), all at the unknown rate if unaware.
   - **Sale price.** `adjust = min(100, 100 + 300 - (min_inflate + racefactor + adj_chr_gold[CHR4]))`, price = `(value*adjust+50)/100`. It is divided by 3 first in the Black market (store 6; `store.c:226`). The code uses `min_inflate` (the first greed number in shop_own.txt) for selling, which is the `final_ask`. `adj_chr_gold[CHR4] = 125` per the earlier memo; I did not recheck.
   - **Purse cap.** Per-unit price is capped at `max_cost = 5 x purse` (`init1.c:1565`, `mdefines.h:646`). Purses are 25,000-150,000 (shop_own.txt). The cap is compared per unit and then multiplied by the number (`store.c:1355-1380`). It is irrelevant at our values. [SEEN]
   - **Refusals.** `store_will_buy` (`store.c:541-643`) refuses any item whose `object_value(p_ptr,…) <= 0` ("I don't want that!"). Because that uses the player's view, an unknown cursed or broken item is accepted and paid at the base value. A *felt* cursed or broken item (ID_SENSE) is refused. After the sale `store_carry` uses `object_value(NULL,…)` (the real value), so a real-cursed item vanishes without being stocked (`store.c:700-710`). The player is still paid.
   - **Who buys what** (tval lists, `store.c:541-643`):
     - Shop 0 (General): food, light, flask, spike, ammo, digger, cloak.
     - Shop 1 (Armoury): armour tvals only.
     - Shop 2 (Weapons): ammo, bow, digger, hafted, polearm, sword.
     - Shop 3 (Temple): prayer book, scroll, potion, hafted (and blessed known polearm/sword).
     - Shop 4 (Alchemist): scroll and potion **only**.
     - Shop 5 (Magic): magic book, amulet, ring, staff, wand, rod, scroll, potion.
     - Shop 6 (Black market): no switch case, so it buys ANY tval with value > 0, at 1/3 of the usual sale price.
     - Shop 7 (Home): `store_sell` does nothing for it; there is no sale or identify.
   - Wands, staffs and rods sold with `pval*amt/number` charges (`store.c:2013-2022`). Unknown charges are not paid for. Under `cfg_ironman`, shops don't restock sold items (`store.c:2192`).
7. **Buying/seeing.** Buying runs `object_aware` on the item (`store.c:1835`; the bought copy is also known, `store.c:1753`). `display_entry`/`object_desc_store` (`store.c:1062-1085`) only describes the item with the knowledge forced on temporarily (`object1.c:2080-2116` restores the flags), so a shop list does NOT make the flavour aware. Shop stock is created known (`store.c:988`).  [SEEN]
8. **Warrior pseudo-ID** (`dungeon.c:148-260`, called from `process_player_end` at `dungeon.c:1621`):
   - Class flags `PSEUDO_ID_HEAVY | PSEUDO_ID_IMPROV` (p_class.txt:98), sense_base 9000, sense_div 40 (p_class.txt:87). Check: `randint0(9000/(plev*plev+40)) == 0`, which at clvl 10 is 9000/140 = 64, so **1 in 64 per call**. The call is gated by `turn % time` with `time = level_speed/1000` (about 9 to 10 game turns; `dungeon.c:1112, 1183`), the same tick as light burning. Rough rate [INFERRED from the memo's torch figures, about 2/s] is one sensing event per ~30-40 s awake.
   - Covered tvals: shot, arrow, bolt, bow, digger, hafted, polearm, sword, boots, gloves, helm, crown, shield, cloak, soft/hard/dragon armour (`dungeon.c:213-238`). **No rings, amulets, wands, staffs, rods, potions, scrolls or lights.** [SEEN]
   - Pack items pass a further 1-in-5 filter (`dungeon.c:250`), equipment doesn't. Items already felt or known are skipped.
   - Heavy feelings (`value_check_aux1`, `dungeon.c:69-102`): special/terrible (artifact), excellent/worthless (ego), cursed, broken, good (to_a>0 or to_h+to_d>0), average. It always gives a feeling.
   - **Sale effect:** a felt cursed or broken item is valued 0 (`object2.c:1388-1393`), so the shop refuses it. Other feelings leave the value at the unknown base. So pseudo-ID only helps with weapons and armour, to avoid a futile trip. It doesn't raise prices. [SEEN]
9. **Other cheap learning.**
   - Using an item (eat, quaff, read, use, aim, zap): `object_tried` marks it tried. If the effect is obvious (`ident`), `object_aware` is called and you gain `(lev + plev/2)/plev` exp (`cmd6.c:116-123`, similar at 225, 358, 550, 705, 866). The item then shows as aware, **not known**, and so is valued at the kind cost without charges.
   - Rod of Perception (`N:372`, level 50, cost 13000, `A:50/8`) and the activation-ID item path exist (`use-obj.c:1738, 2332`). Too deep and expensive for us.
   - Inspect (`obj-info.c`) only describes what is already known or aware; it can't identify. Party members: I found no sharing of `kind_aware` (`grep` in party.c and cmd*.c, none). `files.c:2318-2335` is a character dump hack, not for play. "You have no more" messages: not investigated. [partly SEEN]
10. **Store stock rates** (`init2.c:1226-1305`, each `store_create` picks one table entry uniformly, `store.c:975`). Alchemist table has 32 entries: **Identify 4/32** (12.5% per pick), Recharging 1/32, Word of Recall 4/32. Magic shop table has 27 entries: **Staff of Perception 2/27** (7.4% per pick; Teleportation also 2). A pass adds 1..9 slots (`STORE_TURNOVER` 9, keep 12..36 of max 48, `common/defines.h:297-304`); stock is maintained about every 2500 game turns per the earlier memo. Pile sizes (`mass_produce`, `store.c:285-293`): Identify (cost 50) = 1 + 3 x randint0(5) + randint0(5), so 1..17, mean 9; Recharging (cost 200) = 1 + randint0(5), so 1..5, mean 3; staffs 1. [INFERRED from the code]. Discounts 25% (1/50) etc. apply to all (`store.c:339-355`). [SEEN]

## Contradictions and surprises
- object.txt Recharging text says failure "uncharges"; the code destroys the item (`SAFE_RECHARGE=false` everywhere). The "(160-lev-10*charges)/15" part matches.
- Brief says shops pay 30-46%; the earlier memo says 38-65% by owner. I did not recompute per owner.
- Unknown cursed or broken weapons and armour can be sold for the full unknown base price, and the player is paid. The shop then deletes them.
- A failed device use costs a turn but not a charge.

## Leads
- Player-owned shops (store 8, houses) exist (`store.c:1190ff`, `price*3` markup). Not studied.
- INT of Dive04 is needed for the exact device fail chance. A run log or char sheet would settle it.
- "You have no more" learn-by-count messages and Inspect behaviour on unknown flavours not examined.

## Coverage
Read in full: `ident_spell*`, `recharge*`, `store_sell`, `store_confirm`, `sell_haggle`, `price_item`, `store_will_buy`, `store_carry`, `store_create`, `mass_produce`, `store_maint`, the stock tables (alchemist, magic), `sense_inventory`, the staff-use command (`do_cmd_use_staff`), and the relevant object.txt entries. `store_purchase` was read in the buy-path lines only (1687-1860). `object_value_real` was read for the wand/staff clause only. Not read: client code, party.c in detail, other stores' stock tables.
