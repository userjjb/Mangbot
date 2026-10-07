# Shared rules for the B assignments (danger table, pass 2)

Every B Clerk reads this file in full before starting.

## Inputs
- Your band's rows: `/projectnb/jbrcs/mangband/Advisor/studies/2026-09-27-danger-table/scratch/<id>_input.csv`
  (parsed from monster.txt; columns explained in `/projectnb/jbrcs/mangband/Advisor/data/monsters/README.md`).
  `src_line` is the line of the entry in `/projectnb/jbrcs/mangband/github/lib/edit/monster.txt`;
  open the raw entry whenever a row looks odd, and read the D: description for context if useful.
- The legend: `/projectnb/jbrcs/mangband/Advisor/studies/2026-09-27-danger-table/dispatches/A1.md`.
  Read it fully. It gives each blow effect, spell, breath and flag, with damage formulas and what
  blocks them. Use its formulas; don't use vanilla-Angband memory where they differ.

## Facts the Advisor verified in the code (use them)
- Spell use: each monster turn, if the player is within 18 squares and in line of fire, the monster
  casts with probability 100/X % (S:1_IN_X), else moves/melees (melee2.c:459-484). The spell is picked
  among its spell flags.
- Speed: energy per game tick = 1000 at speed 110 (+0), 2000 at +10, 3000 at +20, 500 at -10
  (tables.c:2169). So a +10 monster acts twice per normal player turn.
- Breaths: damage = current HP / 3 (acid, elec, fire, cold, poison; caps 1600/800) or / 6 (most
  others). Bolts and breaths never miss; AC only reduces melee (HURT and SHATTER blows).
- Paralysis blows: Free Action blocks fully; otherwise a saving throw; on a failure paralysis adds
  3+d(monster level) turns to any paralysis left (melee1.c:962-993, no cap below 10000). So a monster
  with 2+ PARALYZE blows can chain-paralyse a character without Free Action to death.
- The character's saving throw ≈ 15% + clvl (race -3, class 18, +clvl, WIS adj ~0). Saves against
  HOLD, SLOW, SCARE, BLIND, CONF spells, CAUSE_x, MIND_BLAST, BRAIN_SMASH, and paralysis/terrify blows.
- The bare FRIEND flag is unused in monster.txt and does nothing; FRIENDS and ESCORT(S) make groups.
- FORCE_SLEEP does not mean "asleep"; it only means low starting energy.
- SMART monsters do not learn your resists (that code is compiled out in 1.5).
- BR_MANA and BO_POIS are no-ops in 1.5 (the monster wastes its turn).

## The character
Throwaway Half-Orc Warrior, solo, played by a bot. It dives by stair-scumming: on arrival it usually
stands on a connected staircase and can leave at once; it fights by standing still (auto-retaliate)
with a light weapon and 2–3 blows. Intrinsics: resist darkness only; no Free Action, See Invisible,
ESP, or resists until items give them; resist fear only at clvl 30. HP ≈ 10 × clvl (hit die 19).
Escapes: stairs under it, Phase Door, CLW/CSW/CCW potions; later Teleport, Teleport Level, recall.
Assumed state by depth (it dives fast, so it is under-levelled):

| dungeon level | clvl | HP | save | gear |
|---|---|---|---|---|
| 1–10 | 1–15 | 10–150 | 16–30% | soft armour, AC ~20–30, no resists |
| 11–20 | 12–22 | 120–220 | 27–37% | AC ~30–50; Free Action / See Invisible only if found |
| 21–30 | 18–28 | 180–300 | 33–43% | should have FA + SI by dl20 (doctrine); basic resists maybe |

## Danger scale (use exactly this)
- **0 trivial:** can't meaningfully hurt the character at its assumed state.
- **1 easy:** safe to fight standing still.
- **2 care:** safe to fight, but watch HP or status (poison, a small group, a thief, a light spell caster).
- **3 dangerous:** can kill an unprepared character at native depth (paralysis without FA, a large
  group or pack, breeders swamping, damage that outpaces the character, confusion/blindness locks,
  invisible attackers without SI, summoners).
- **4 lethal:** likely to kill a character at or below native depth in a few turns unless it has
  specific gear (breath of 100+ unresisted, chain paralysis without FA, a fast unique, a hound pack
  of a nasty type).
- **5 flee on sight:** leave the level at once if one is seen at this depth.

Response (one word): **FIGHT** (stand and auto-retaliate) / **CAREFUL** (fight only if a condition
holds, e.g. HP above X, in a corridor, has CCW) / **AVOID** (don't engage; walk away or wait) /
**LEAVE** (take the stairs or leave the level now).

## Output (both files)
1. The CSV `/projectnb/jbrcs/mangband/Advisor/studies/2026-09-27-danger-table/scratch/<id>_table.csv`,
   one row per monster in your input (all of them, no skipping), with exactly these columns:
   `idx,name,level,symbol,color,danger,response,threats,neutraliser,safe_when,notes`
   - `threats`: the 1–3 features that make it dangerous, short (e.g. "BR_POIS ~hp/3=45; FRIENDS").
   - `neutraliser`: the item/resist/tactic that removes most of the threat (e.g. "rPois", "Free
     Action", "See Invisible", "corridor", "kill fast", "none").
   - `safe_when`: when the response relaxes (e.g. "clvl 20+", "with FA", "never").
   - Quote fields containing commas. Write it with a small Python script if easier.
2. The dispatch `/projectnb/jbrcs/mangband/Advisor/studies/2026-09-27-danger-table/dispatches/<id>.md`,
   ≤ 2500 words, in your dispatch format. Under Findings give: the ranking of danger features in your
   band (which features produce 3+ ratings, with counts); every monster rated 4 or 5 with a one-line
   reason; the uniques; the breeders; the invisible monsters; the paralyzers, blinders and confusers;
   the summoners; and where the stat block surprised you (e.g. a monster far nastier than its name).
   Rating judgement is yours; show the numbers behind 3+ ratings (e.g. expected breath damage at
   average HP vs the character's HP).
Scratch: only in `/projectnb/jbrcs/mangband/Advisor/studies/2026-09-27-danger-table/scratch/`.
