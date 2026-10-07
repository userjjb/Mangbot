Study: 2026-10-07-selling — assignment L (pass 1): what OUR MISSIONS did with unknown items
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
 1. Across all missions (runs/pilot/dive01..dive04: events.jsonl, decisions.jsonl, navigator.md,
    pilot.log; plus /projectnb/jbrcs/mangband/next_steps.md mission notes, read only), list every
    unknown/flavoured item (potion, scroll, staff, wand, rod, ring, amulet) found, and what happened to
    it: sold unknown (gold received), quaffed/read/used (what it turned out to be, any harm),
    identified (how, cost), destroyed (junk/autodestroy), dropped, still carried.
 2. Estimate the gold lost: for items sold unknown that turned out valuable (e.g. 2 Potions of Speed
    sold at 8 each), what would they have paid known? Use kinds.csv sell_known (cost x owner %). Put
    the per-item rows in a CSV; the Advisor will total them.
 3. How many unknown items per mission/hour does the character find, by tval and depth band?
 4. What does the Pilot do today with unknown items? Read github/tools/pilot/pilot.py (unknown_flavour,
    the shop sell path ~line 800, junk and autodestroy orders, pickup, any auto-use/test logic) and
    github/tools/pilot/HANDBOOK.md (advice on unknown items, money). Quote the rules and their lines.
    Which flavours does Dive04 already know (aware), if the logs show it?
 5. Any harm we suffered from using unknown items (stat drain, summons, curses)?
Sources: /projectnb/jbrcs/mangband/runs/pilot/ (dive01..04; events.jsonl restarts its clock at t=0
  per pilot process — match by wall-clock in decisions.jsonl 't' epoch and pilot.log start lines),
  /projectnb/jbrcs/mangband/github/tools/pilot/{pilot.py,HANDBOOK.md}, the shops study's trade table
  /projectnb/jbrcs/mangband/Advisor/studies/2026-09-29-shops/scratch/S4_trades.csv (158 trades to 09-29;
  extend it with later missions, don't redo it), /projectnb/jbrcs/mangband/next_steps.md (read only).
Scope: our own records only. A mission (Dive04 mission 13) is RUNNING NOW: read its files but do not
  touch the control socket or any program; note where your data stops.
Output: write the dispatch to /projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-selling/dispatches/L.md, <= 1500 words, in your dispatch format, and the
  item rows to /projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-selling/scratch/L_items.csv (columns: mission,date_time,nick,depth_ft,item_as_seen,true_kind,
  fate,gold_received,source_cite).
Scratch (if needed): /projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-selling/scratch/
