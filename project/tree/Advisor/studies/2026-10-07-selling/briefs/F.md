Study: 2026-10-07-selling — assignment F (pass 1): what MAngband PLAYERS say about identifying and selling
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
Question(s): what do forum posters advise or report about:
 1. quaffing / reading / using unknown items to learn them (and deaths or disasters from it: Summon
    Undead, Aggravate, Curse, Death/Ruination potions, cursed rings);
 2. Identify scrolls vs Staff of Perception vs Recharging (costs, recharge failures/explosions);
 3. selling unknown vs identified items; which items are the best money makers for a low-level
    character; store quirks (prices, purses, discounts, selling identifies);
 4. the four claims in this study: (a) quaffing unknown potions out of combat is usually safe;
    (b) reading unknown scrolls / using unknown staffs is sometimes dangerous (summoning); (c) most
    items sell for much more identified than it costs to identify them; (d) a Staff of Perception
    with recharge scrolls is usually cheaper than Identify scrolls.
Sources: /projectnb/jbrcs/mangband/Advisor/data/forum/corpus/*.txt (README.md in the parent dir
  explains the format; ~3 MB). Search with grep for: identif, perception, recharg, unknown, quaff,
  unID, try, sell, gold, money, cash, summon undead, aggravate, curse, ruination, death potion,
  salt water, flavor/flavour, ID; then read the matching topics in full context.
Scope: the corpus only (no web). Posts are mostly 2002-2014 (older server versions): tag everything
  [REPORTED] and note the date and version if given. You may check a claim in the 1.5 source if quick.
Output: write the dispatch to /projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-selling/dispatches/F.md, <= 1500 words, in your dispatch format; cite
  topic id + post id for every claim; end with a table: claim (a-d) | support | against | best quote.
Scratch (if needed): /projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-selling/scratch/
