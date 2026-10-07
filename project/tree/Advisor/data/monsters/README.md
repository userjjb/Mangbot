# data/monsters — monster races of the MAngband 1.5.3 server

- `monsters.csv`: one row per monster race (616 rows; entry 0, the player, is skipped), parsed from
  `/projectnb/jbrcs/mangband/github/lib/edit/monster.txt` (V:1.5.3) by `parse_monsters.py`.
  Regenerate with `module load python3/3.12.4; python3 parse_monsters.py`.
- Made by the Advisor on 2026-09-27 for the danger-table study
  (`../../studies/2026-09-27-danger-table/`). Spot-checked against 4 random raw entries (all fields match).

## Columns

| column | meaning |
|---|---|
| idx, name | `N:` serial number and name |
| symbol, color | `G:` glyph and colour letter (see monster.txt header: D dark grey, w white, s grey, o orange, r red, g green, b blue, u brown, d black, W light grey, v violet, y yellow, R light red, G light green, B light blue, U light brown) |
| level, rarity, exp | `W:` native depth (dungeon level; 50 ft each), rarity (1 in N), exp at clvl 1 |
| speed | `I:` speed, 110 = normal (+0); 120 = +10 |
| hp_dice, hp_avg, hp_max | `I:` HP dice; average and max. With `FORCE_MAXHP` the average is set to the max |
| vision, ac, alertness | `I:` vision (tens of feet), armour class, alertness (0 = vigilant, 255 = ignores you) |
| n_blows, blow1..blow4 | `B:` lines as METHOD:EFFECT:DICE |
| melee_max | sum of max blow damage per monster turn (dice only; ignores effect side damage) |
| blow_effects | distinct non-HURT blow effects |
| spell_freq, spells | `S:1_IN_X` → X; spell/breath names joined with `|` |
| flags | all `F:` flags joined with `|` |
| unique | 1 if UNIQUE |
| src_line | line of the `N:` entry in monster.txt |
| desc | the `D:` text |

## danger_table.csv (danger-table study, 2026-09-27)

- Built by `build_danger_table.py` from `monsters.csv` + the Clerks' band tables
  (`../../studies/2026-09-27-danger-table/scratch/B1..B4_table.csv`) + `advisor_overrides.csv`.
  Rerun it after changing an override.
- 473 rows: every monster of level 0–40, sorted by level. Rated for the throwaway Half-Orc Warrior at
  an assumed state for the monster's depth (see the memo `../../../memos/2026-09-27-danger-table.md`).
- Columns: `danger` 0–5 (0 trivial, 1 easy, 2 care, 3 dangerous, 4 lethal unless geared, 5 leave on
  sight), `response` FIGHT/CAREFUL/AVOID/LEAVE, `threats`, `neutraliser`, `safe_when`, `notes`
  (for B4 rows: recognition and look-alikes), `clerk_danger`/`clerk_response` (the Clerk's original
  rating), `advisor_note` (why the Advisor changed it), `band`, and computed columns:
  `speed_x` (actions per normal player turn), `melee_avg` (average per monster turn if every blow
  hits), `melee_max` (maximum per monster turn, every blow at its max roll — the Borg's measure;
  added 2026-09-28), `drain_blows` (count of LOSE_*/EXP_* blows; added 2026-09-28), `breath` (NAME=avg/max damage from average/max HP; FORCE_MAXHP respected),
  `breath_avg_max`, `tags` (PARA_BLOW, BLIND_BLOW, CONF_BLOW, HOLD, BRAIN, SUMMON, TELE_TO, INVIS,
  EMPTY_MIND, BREEDER, PACK, UNIQUE, NEVER_MOVE, PASS_WALL, KILL_WALL), `src_line`.
- `idx` = monster.txt `N:` number (the Pilot's `Race.idx`). Names are not unique (two Novice
  paladins, two Carrion crawlers): key on `idx`.
