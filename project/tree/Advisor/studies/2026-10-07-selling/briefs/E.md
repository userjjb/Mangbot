Study: 2026-10-07-selling — assignment E (pass 1): IDENTIFICATION MECHANICS AND COSTS
Context (for orientation only): the study builds one policy for unknown items (use them to learn
  them, Identify them, or sell them unknown) that maximises gold and keeps the character safe. Our
  character: Dive04, Half-Orc Warrior (resists dark, CHR 4), clvl 10, 135 HP, no Free Action, solo,
  stair-scumming at 0-450 ft now and aiming for 0-1500 ft (dungeon levels 1-30). Server: MAngband
  upstream develop c97e873, which plays as 1.5.3 (based on Vanilla 3.0.x). Source: /projectnb/jbrcs/mangband/github/src/
  (server/, common/), data files in /projectnb/jbrcs/mangband/github/lib/edit/ (object.txt etc.).
Shared facts (code-checked by the Advisor; report anything that contradicts them):
  - Sale value: unaware items use a base value per tval (potion/scroll 20, staff 70, wand 50, rod 90,
    ring/amulet 45; object2.c:1075-1112); aware but not known = the kind cost from object.txt;
    known = real value, wands and staffs +cost/20 per charge, cursed or broken = 0 (object2.c:1253-1257,
    1362-1400). Shops pay 30-46% of value depending on owner.
  - Object kinds: get_obj_num (object2.c:646-770). Table of all 249 flavoured kinds with level, alloc, cost:
    /projectnb/jbrcs/mangband/Advisor/data/identify/kinds.csv (made by kinds.py).
  - Identify scroll cost 50 (Alchemist, 4 stock entries), Recharging cost 200 level 40 (Alchemist, 1 entry),
    Staff of Perception cost 400 level 10 (Magic shop, 2 entries).
Question(s):
 1. Identify scroll: what exactly does it set (aware + known)? *Identify*? Code lines.
 2. Staff of Perception: initial charges when found and when bought (apply_magic / store creation code),
    the store price of a staff with N charges, its device fail chance for a clvl-10 warrior, and does a
    fail use up a charge?
 3. Recharging in THIS code (spells2.c recharge or similar): exact charges added and failure chance for
    a staff of level 10 with 0..5 charges left, and what failure does (destroy the staff? drain it?).
    Compare with the object.txt description. Any MAngband change (e.g. stacked staffs)?
 4. Selling to a shop: does store_sell / the sell path make the flavour aware or the item known
    (identify on sale)? Does the price shown/paid use the pre-sale unknown value? Does the store refuse
    unknown or cursed items? Is there a purse limit (owner max_cost) that caps what a shop pays? Which
    stores buy which tvals (store_will_buy, store.c:541)? Can a player sell to the Black market or Home?
 5. Buying from a shop: does buying make the flavour aware? Does merely seeing an item in a shop list?
 6. Warrior pseudo-ID (sense_inventory or similar in dungeon.c): which tvals it covers (jewellery?
    devices?), how often for a clvl-10 warrior (heavy or light sensing), what feelings it gives, and
    whether it changes the sale value (object2.c 'Felt cursed' = 0).
 7. Any other way to learn items cheaply in this version: Inspect, the Home, rods of perception,
    party members, "You have no more" messages, store "examine"?
 8. Store stock: from store.c / init2.c tables, how often is Identify / Recharging / Staff of Perception in
    stock (entries per table) and is there any rule that makes stores sell them charged/uncharged?
Sources: github/src/server/ (store.c, object1.c, object2.c, spells2.c, cmd6.c/use-obj.c, dungeon.c,
  init2.c), github/lib/edit/object.txt. Earlier work: /projectnb/jbrcs/mangband/memos/2026-09-29-shops.md (read §1).
Scope: mechanics and formulas only; the Advisor computes the cost comparison by script from your
  formulas, so give formulas exactly (with code lines), plus worked examples if easy.
Output: write the dispatch to /projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-selling/dispatches/E.md, <= 1800 words, in your dispatch format.
Scratch (if needed): /projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-selling/scratch/
