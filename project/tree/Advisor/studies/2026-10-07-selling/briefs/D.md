Study: 2026-10-07-selling — assignment D (pass 1): unknown SCROLLS, STAFFS, WANDS, RODS, RINGS, AMULETS
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
 1. For each scroll and staff kind with level <= 50 in kinds.csv: what happens when our warrior reads
    or uses it unknown, out of combat? Exact numbers (summon count and monster level, aggravate
    effect, darkness, trap creation, teleport range, teleport level direction, curse effects on WORN
    gear, earthquake, slowness, haste monsters, etc.). Classify GOOD / HARMLESS / NUISANCE / COSTLY /
    DANGEROUS (can start a fight that kills) / LETHAL.
 2. Wands and rods: aiming an unknown one at a monster or into empty space. Which help the monster
    (Clone, Haste, Heal monster; polymorph) and how badly? Does aiming at nothing teach anything?
 3. Rings and amulets: wearing an unknown one. Which are cursed (Teleportation, Weakness, Stupidity,
    Aggravate, Woe, DOOM, Amulet of Teleportation...)? In THIS version, can a cursed item be taken off,
    or does it stick until Remove Curse? Is Remove Curse sold (which store)? What does wearing reveal
    at once (aware? known pval?), and does the warrior's pseudo-ID warn about curses for jewellery?
 4. For each tval: does use make the flavour aware always, or only when the effect is noticed
    ("ident" flag)? Is there a "tried" state? Do staffs/wands/rods need a skill roll to use (device
    skill fail chance for a clvl-10 Half-Orc warrior; cite the formula)? Cite lines.
 5. Blind or confused: which of these can be used (scrolls need sight; staffs?) — only if quick to find.
Sources: github/src/server/*.c (read/use/aim/zap/wear paths: use-obj.c, cmd6.c, cmd3.c, spells1.c,
  spells2.c, xtra2.c), github/lib/edit/object.txt (tvals 70, 55, 65, 66, 45, 40).
Scope: everything except potions (another Clerk). Kinds of level > 50 only if they occur at
  levels <= 50 via a second A: entry. Do not compute depth probabilities (the Advisor does).
Output: write the dispatch to /projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-selling/dispatches/D.md, <= 2000 words, in your dispatch format, with one
  table per tval: kind | level | effect when used unknown | class | aware on use? (code line).
  Also write all rows as CSV to /projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-selling/scratch/D_devices.csv (columns: tval,kind,level,effect,class,aware_on_use,cite).
Scratch (if needed): /projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-selling/scratch/
