Study: 2026-10-07-selling — assignment P (pass 1): unknown POTIONS
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
 1. For every potion kind in kinds.csv, what happens when our warrior quaffs it OUT of combat (no
    monster in view)? Find the quaff code (try use-obj.c, cmd6.c; follow into xtra2.c set_* functions,
    spells*.c). Give exact numbers: damage, durations (player turns), stat changes, exp loss, food.
 2. Classify each: GOOD / HARMLESS / NUISANCE (passes off) / COSTLY (lasting harm that costs gold or
    time to fix: stat drain, exp loss) / LETHAL (can kill a 135-300 HP warrior). For COSTLY ones, how is
    it fixed (which potion/store, does gaining a level or time restore it in this version?).
 3. Does quaffing always make the flavour aware (and the potion known)? Or only when the effect is
    noticed (an "ident" flag)? What happens to awareness if nothing noticeable happens? Is there a
    "tried" state? Cite the lines.
 4. Is awareness per player (p_ptr) or global in MAngband? Does it persist across sessions/death?
 5. Special risks in a real-time multiplayer game: Sleep (paralysis) duration in real time and whether
    Free Action protects; Salt Water and hunger; Lose Memories; Death/Ruination/Detonations exact damage.
 6. Do any potions have extra effects when thrown or when they break (shatter) that matter?
Sources: github/src/server/*.c (quaff path), github/lib/edit/object.txt potion entries (tval 75).
Scope: potions only. Skip scrolls/devices (another Clerk). Do not compute depth probabilities (the Advisor does).
Output: write the dispatch to /projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-selling/dispatches/P.md, <= 1500 words, in your dispatch format, with a
  table: potion | level | effect out of combat (exact) | class | fix/cost | aware on quaff? (code line).
  Also write that table as CSV to /projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-selling/scratch/P_potions.csv.
Scratch (if needed): /projectnb/jbrcs/mangband/Advisor/studies/2026-10-07-selling/scratch/
