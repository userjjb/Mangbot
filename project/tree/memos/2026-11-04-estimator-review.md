---
from: Advisor (session 5)
to: Architect, and the user (two decisions at the end)
date: 2026-11-04
re: the shadow estimator on the first missions since 10-28 (m61-m65); options_sim 11-04q adds gear damage
---

# The estimator on m61-m65

Audit trail: `Advisor/studies/2026-11-04-estimator-review/` (records, tables, scripts).

## The records

- **m61 and m62:** no emergency, band or hard fight, so no estimator call.
- **m63-m65 (policy 11-03p):** 22 records.

| trigger | records | agree |
|---|---|---|
| band | 7 | 1 |
| hard fight | 6 | 3 |
| emergency | 9 | 4 |

The low agree rate has three different causes, below.

## 1. Bands: the estimator would fight 6 of 7. This is where the XP is.

Each time, the Pilot's band rule left by the stairs, within 2-30 s. The estimator rated fighting safe each time
(P(near death) 0). The exception was 18 Hummerhorns (breeders), where it also prefers leaving (+102 XP).

| band | XP leaving loses vs fighting (estimator) | estimator's lowest HP p10, fighting |
|---|---|---|
| m63 10:10, Uruk x7 | 194 (it rates the walk to the stairs **unsafe**: P(near death) 0.48) | 262 / 358 |
| m64 11:35, 6 orcs + flies | 112 | 271 |
| m64 11:59, Black orc x6 | 87 | 278 |
| m65 12:30, 7 orcs | 57 | 328 |
| m65 12:46, 11 animals | 176 | 283 |
| m65 12:52, Water hound x4 + shaman | 556 (no gear cost; see §4) | 269 |

That is ~1,180 XP over three missions, about 15 dungeon minutes at the current ~75 XP/dmin.
- **The time cost doesn't change it.** I re-ran the bands with the time cost on (`xp_per_block` = the play rate,
  ~0.45 XP per block): same choices. A band fight earns several XP per block.
- **Two cautions before acting on it:**
  - **Arrivals aren't in the model.** At m65 12:46 the Pilot did fight ("6 monsters together but weak"). Then a
    summon trap and a Fire hound / White wolf pack joined: 26 monsters, nine emergencies, lowest HP 48%. The
    estimator's 283 was the band alone.
  - **Adjacent monsters are always awake in the model.** The Pilot logs `awake` as unknown for most of them. At m63
    10:10 the model gave the walk to the stairs P(near death) 0.48, but the Pilot walked off without losing a single
    HP: the Uruks were very likely asleep. Please fill `awake` from the look whenever the Pilot has it.

## 2. Speed at the start of hard fights: no benefit in the model

| | |
|---|---|
| Speed potions drunk in m63-m65 | 6, about 2,400 gold |
| hard fights where the estimator skipped Speed for Berserk alone (m63 10:13, m65 12:41) | 2 of 3 |
| saving each time | +196-211 XP net of gold (380 gold at XP_PER_GOLD ~0.5) |
| effect on safety | none: P(near death) 0 both ways, lowest-HP p10 equal or better without Speed |

In all 10 set-piece hard fights since 10-29 the same comparison shows no safety gain from Speed either: Khim,
lowest-HP p10 315 with it vs 297 without, both far above the line.

This is a user decision: the Speed kit and the hard-fight start are the user's. If wanted, the cheapest change is to
let the shadow's hard_fight answer decide Speed: drink it only when speed+berserk is safer than berserk by a margin.

## 3. Emergencies: mostly noise, and a definitional mismatch

- **The 9 emergencies:**
  - 4 agree.
  - 3 are real disagreements:
    - 12:46:21, CCW instead of Speed (+185 XP, SE 41): healed above 50%, the line keeps fighting instead of
      teleporting.
    - the two "stairs" below.
  - 2 (12:46:36, 12:46:49), plus the hard fight at m64 11:36:12, are definitional.
- **`agree` is stricter than the estimator.** In those 3 definitional records the estimator said "no option clearly
  better" (its threshold is MIN_GAIN, 50 XP or 30 s of play), but `shadow_agree` logged a disagreement because
  another row was 17-35 XP better. Please give `shadow_agree` the estimator's threshold: `max(min_gain, 2 SE)`, with
  min_gain from `p["xp_rate_per_block"]` as in choose(). Then agree means "the estimator wouldn't change it".
- **"stairs" with a Word of Recall pending** (m65 12:46:46 and 12:46:58, stairs 67 squares away) really means "wait
  out the 9 blocks until the recall fires instead of using a staff charge (250 gold)".
  - It passed as safe with lowest-HP p10 at 31% of max (110 of 358), just above the 30% line.
  - The choice is defensible, but it's thin, and the label misleads. I'll rename the option in the table when a recall
    is pending.
  - **Logging:** shadow.py logs only `table[:6]` (sorted by XP), so the chosen row (stairs, 0 XP) was cut from the
    record. Please always log the chosen row, the rules row and the actual action's row.

## 4. Gear damage: yes, the estimator should count it. Built in options_sim 11-04q.

The server rules (`spells1.c`):
- `acid_dam` calls `minus_ac` on **every** acid hit that isn't immune, **resisted or not**: a random one of 6 armour
  slots (body, shield, cloak, gloves, helm, boots) loses 1 to-AC, unless the slot is empty, has ac+to_a <= 0, or the
  item has IGNORE_ACID. That is why rAcid didn't help in m65: 31 breaths, 21 "is damaged!".
- Disenchantment: BR_DISE or an UN_BONUS blow, without res_disen.

**11-04q** (copy + mv; signatures unchanged; the 21 replays identical row for row):
- **New optional player-dict keys:** `acid_gold`, the expected gold per acid hit, and `disen_gold`, the same per
  disenchantment. They add to the line's gold, so they weigh against XP at xp_per_gold like potions. Absent = 0.
- **Please pass them from the shadow snapshot (and geareval):**
  - `acid_gold` = 1/6 x the sum over those 6 slots of the item's cost for one to-AC lost. Use your `_reflex_gear_damage`
    event cost: the kit's repair price / chance, else resale value; 0 for an empty, IGNORE_ACID or ac+to_a <= 0 slot.
  - `disen_gold` = your `gear.disenchant_cost` per hit.

**The Water hound band (m65 12:52) with acid_gold 230** (~5,000 gold / 22 points):

| line | acid hits | gold | net |
|---|---|---|---|
| fight | ~6 | ~1,480 | still +XP |
| walk to the stairs | ~5 more than fighting | | the worst line (more breaths during the walk) |
| phase first | | | best, +139 net |

That matches what happened: the Pilot fled and took 31 breaths. **So against acid breathers, walking away is the
expensive choice.** Your new reflex's "leave" order (stairs within 20, then Teleportation) should prefer an immediate
teleport over a walk when the breather can follow.

## 5. The user's TODO (A2L, phase > fight in a band): resolved, not a horizon artefact

At horizons 30-240 the ranking holds. "Fight" ends after ~3 blocks: three Uruks and Lugdush adjacent make the
worst-turn emergency, the crowd rule teleports, and the episode stops counting XP. "Phase" scatters the band, so they
come back one or two at a time and no emergency fires. That is the Pilot's own rules played forward, so it's real in
the model. It also says something about the rules: phasing first beats fighting a band in a heap.

## Decisions for the user

1. **Bands:** keep "leave while it's cheap", or let fights with orc/animal bands go ahead when the estimator rates
   them safe? The latter is worth ~400 XP per mission on this sample. The risks are arrivals (m65 12:46) and the
   asleep/awake gap above.
2. **Speed at hard-fight start:** keep it always, or drink it only when the estimator finds it makes the fight safer?
   That saves ~380 gold per hard fight on this sample.

## What I lacked

- The Pilot's awake/asleep look for adjacent monsters (`awake` None in most team entries).
- The full option table in the log: the chosen row is cut by `table[:6]`.
