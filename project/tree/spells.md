# MAngband Priest Prayers

Generated from the server source in `github/`:
- effects: `src/server/x-spell.c` (`cast_priest_spell`), plus helpers in `spells1.c`, `spells2.c`, `xtra2.c`
- level / mana / fail / XP: `lib/edit/p_class.txt` (Priest `B:` lines)
- books: `lib/edit/object.txt`, and the Temple stock list in `src/server/init2.c`

Paladins use the same books, but their levels and costs are different. Everything below is **Priest only**.

## Reading the tables

| Column | Meaning |
|---|---|
| Lv | Character level needed to learn the prayer |
| SP | Mana cost |
| Base fail | Failure % before level and WIS adjustments (see [Failure rate](#failure-rate)) |
| 1st-cast XP | One-time XP for your first successful cast (= `exp × Lv` from p_class.txt) |

`plev` means your character level. `dN` is a roll from 1 to N. "In view" means every monster in line of sight, with no targeting and no bolt. The detection area (**det**) is a box reaching 52 squares left/right and 23 squares up/down from you, which is about one screen.

Duration units are game turns at normal speed (same as the `dur` numbers the browse screen shows).

---

## Town books (sold at the Temple)

### Beginners Handbook: 25 gold, level 5

| # | Prayer | Lv | SP | Base fail | 1st-cast XP | Effect |
|---|---|---|---|---|---|---|
| a | Detect Evil | 1 | 1 | 10 | 4 | Shows every **evil** monster in det, including invisible ones. |
| b | Cure Light Wounds | 1 | 2 | 15 | 4 | Heal **2d10**, cut −10. *Projectable* (2d8 to the target). |
| c | Bless | 1 | 2 | 20 | 4 | Blessed for **12+d12**: +5 AC, +10 to-hit. |
| d | Remove Fear | 1 | 2 | 25 | 4 | Cures fear. |
| e | Call Light | 3 | 2 | 25 | 1 | Lights the room, plus a radius of **plev/10+1**. Light-sensitive monsters in that radius take **2d(plev/2)**. |
| f | Find Traps | 3 | 3 | 27 | 2 | Detects traps in det. |
| g | Detect Doors/Stairs | 3 | 3 | 27 | 2 | Detects doors (secret doors are revealed) and stairs in det. |
| h | Slow Poison | 3 | 3 | 28 | 4 | Halves the poison timer. |

### Words of Wisdom: 100 gold, level 10

| # | Prayer | Lv | SP | Base fail | 1st-cast XP | Effect |
|---|---|---|---|---|---|---|
| a | Scare Monster | 5 | 4 | 29 | 3 | *Aimed bolt.* Scares a monster for 3d(plev/2)+1 turns. Uniques and NO_FEAR monsters are immune. Save: monster level > d(plev−10)+10. |
| b | Portal | 5 | 4 | 30 | 4 | Teleport, range **3×plev**. |
| c | Cure Serious Wounds | 5 | 4 | 32 | 4 | Heal **4d10**, cut halved then −20. *Projectable.* |
| d | Chant | 5 | 5 | 34 | 4 | Bless for **24+d24**. |
| e | Sanctuary | 7 | 5 | 36 | 3 | Tries to put every **adjacent** monster to sleep (power plev). Uniques and NO_SLEEP monsters are immune. Same save as Scare Monster. |
| f | Satisfy Hunger | 7 | 5 | 38 | 4 | Food set to just under full (never gorged). |
| g | Remove Curse | 7 | 6 | 38 | 5 | Uncurses **worn** items. Does **not** work on heavy or permanent curses. |
| h | Resist Heat and Cold | 7 | 7 | 38 | 5 | Temporary fire **and** cold resistance, **10+d10** each. |

### Chants and Blessings: 300 gold, level 20

| # | Prayer | Lv | SP | Base fail | 1st-cast XP | Effect |
|---|---|---|---|---|---|---|
| a | Neutralize Poison | 9 | 6 | 38 | 4 | Cures poison completely. |
| b | Orb of Draining | 9 | 7 | 40 | 4 | *Aimed ball*, radius 2 (3 at plev 30+). Damage **3d6 + plev + plev/2**, **doubled vs evil**. Your main attack. |
| c | Cure Critical Wounds | 9 | 7 | 38 | 4 | Heal **6d10**, cures cuts. Does *not* cure stun or poison. *Projectable.* |
| d | Sense Invisible | 11 | 8 | 42 | 4 | See invisible for **24+d24**. |
| e | Protection from Evil | 11 | 8 | 42 | 4 | Lasts **3×plev + d25**. Blocks each melee blow from an evil monster of level ≤ plev when d100+plev > 50, so the chance improves as you level. |
| f | Earthquake | 11 | 9 | 55 | 5 | Earthquake, radius 10. Does nothing in town or the wilderness right around it. |
| g | Sense Surroundings | 13 | 10 | 45 | 4 | Maps the area in det. |
| h | Cure Mortal Wounds | 13 | 11 | 45 | 4 | Heal **8d10**, cures stun and cuts. *Projectable.* |
| i | Turn Undead | 15 | 12 | 50 | 5 | Scares all **undead** in view (power plev) for 3d(plev/2)+1 turns. Uniques are **not** immune. Save: monster level > d(plev−10)+10. |

### Exorcism and Dispelling: 900 gold, level 30

| # | Prayer | Lv | SP | Base fail | 1st-cast XP | Effect |
|---|---|---|---|---|---|---|
| a | Prayer | 15 | 14 | 50 | 5 | Bless for **48+d48**. |
| b | Dispel Undead | 17 | 14 | 55 | 7 | Hits all **undead** in view for **d(3×plev)**. |
| c | Heal | 21 | 16 | 60 | 7 | Heal **300**, cures stun and cuts. *Projectable.* |
| d | Dispel Evil | 25 | 20 | 70 | 12 | Hits all **evil** monsters in view for **d(3×plev)**. |
| e | Glyph of Warding | 33 | 55 | 90 | 15 | Places a glyph under you. Needs an empty floor square, and does not work in town or inside a house. |
| f | Holy Word | 39 | 32 | 95 | 20 | Dispel evil **d(4×plev)**, heal **1000**, and cures fear, poison, stun and cuts. |

---

## Dungeon books (found only; these can't be damaged by acid, fire, cold or lightning)

Listed in inventory order (by sval). "Depth" is the book's native dungeon level from object.txt.

### Ethereal Openings: depth 40

| # | Prayer | Lv | SP | Base fail | 1st-cast XP | Effect |
|---|---|---|---|---|---|---|
| a | Blink | 3 | 3 | 50 | 6 | Teleport, range 10. |
| b | Teleport Self | 10 | 10 | 50 | 8 | Teleport, range **8×plev**. |
| c | Teleport Other | 20 | 20 | 80 | 16 | *Aimed bolt.* Teleports the monster it hits away. |
| d | Teleport Level | 30 | 40 | 75 | 133 | 50/50 chance of going up or down one level; always down if you're on the surface. Does not work for ironman characters or in the arena. |
| e | Word of Recall | 35 | 50 | 75 | 11 | Recall starts in **15–34** turns. Casting again while it's active cancels it. The target depth is your max depth, or `@R<n>` inscribed on **this book** (n in feet if divisible by 50, otherwise a level number; capped at max depth). |
| f | Alter Reality | 40 | 60 | 75 | 250 | Regenerates the current dungeon level for **everyone on it**. Fails in town, the wilderness and special levels. Each non-party player on the level gets a perception save that stops it. |

### Godly Insights: depth 50

| # | Prayer | Lv | SP | Base fail | 1st-cast XP | Effect |
|---|---|---|---|---|---|---|
| a | Detect Monsters | 3 | 3 | 50 | 2 | Detects all **non-invisible** monsters and players in det. |
| b | Detection | 10 | 10 | 80 | 20 | Everything in det: treasure, objects, traps, doors/stairs, and monsters including invisible ones. |
| c | Perception | 20 | 20 | 80 | 20 | Identifies one item (pack or floor). |
| d | Probing | 25 | 10 | 80 | 150 | Shows HP and full monster memory for every monster **within 20 squares**. MAngband doesn't require line of sight. |
| e | Clairvoyance | 35 | 50 | 80 | 230 | Lights and maps the **entire level**. |

### Purifications and Healing: depth 60

| # | Prayer | Lv | SP | Base fail | 1st-cast XP | Effect |
|---|---|---|---|---|---|---|
| a | Cure Serious Wounds | 15 | 5 | 50 | 25 | Heal **4d10**, cures cuts. Cheaper than the Words of Wisdom version. *Projectable.* |
| b | Cure Mortal Wounds | 17 | 7 | 60 | 45 | Heal **8d10**, cures stun and cuts. Costs 7 SP versus 11. *Projectable.* |
| c | Healing | 30 | 50 | 80 | 130 | Heal **2000**, cures stun and cuts. *Projectable.* |
| d | Life Restoration | 35 | 70 | 90 | 230 | If a **ghost player** is standing next to you, resurrects them. Otherwise restores all six of your stats. |
| e | Remembrance | 35 | 70 | 90 | 250 | Restores lost XP for the first XP-drained player in the 3×3 square around you (which can be you). It checks rows top to bottom, left to right. |

### Holy Infusions: depth 80

| # | Prayer | Lv | SP | Base fail | 1st-cast XP | Effect |
|---|---|---|---|---|---|---|
| a | Unbarring Ways | 5 | 6 | 50 | 40 | Destroys doors next to you. |
| b | Recharging | 15 | 20 | 80 | 25 | Recharges a wand or staff, strength 15. Backfire chance is 1 in `(115 − item level − 10×charges each)/15`, and a backfire **destroys the item** unless `SAFE_RECHARGE` is on (the server config sets it to false). |
| c | Dispel Curse | 25 | 40 | 80 | 160 | Uncurses worn items, **including heavy curses**. Permanent curses stay. |
| d | Enchant Weapon | 35 | 50 | 80 | 230 | Picks a weapon and makes **1–4** attempts at +to-hit and **1–4** at +to-dam. Success gets harder as bonuses go up and stops at +15. |
| e | Enchant Armour | 37 | 60 | 85 | 250 | Picks armour and makes **2–4** attempts at +AC. |
| f | Elemental Brand | 45 | 95 | 85 | 250 | Brands your **wielded** weapon: **75% Frost / 25% Fire**, plus 4–6 enchant attempts at to-hit and to-dam. Fails on artifacts, ego items, broken or cursed weapons. |

Enchant Weapon, Enchant Armour and Elemental Brand all mark a **store-bought** item as 99% discounted, which makes it close to worthless if you sell it.

### Wrath of God: depth 100

| # | Prayer | Lv | SP | Base fail | 1st-cast XP | Effect |
|---|---|---|---|---|---|---|
| a | Dispel Undead | 15 | 7 | 70 | 25 | Hits all **undead** in view for **d(4×plev)**. |
| b | Dispel Evil | 20 | 10 | 75 | 60 | Hits all **evil** monsters in view for **d(4×plev)**. |
| c | Banish Evil | 25 | 25 | 80 | 250 | Teleports every **evil** monster in view about 100 squares away. |
| d | Word of Destruction | 35 | 35 | 80 | 115 | Destroys everything in radius 15 around you. It blinds you unless you resist blindness or light. Does nothing in town or the wilderness right around it. |
| e | Annihilation | 45 | 60 | 75 | 250 | *Aimed bolt*, drains life for **200**. **No effect** on undead, demons, or `E`/`g`/`v` monsters. |

---

## Projecting a heal onto another player

The 8 *Projectable* heals can be fired at another player:
- **Choose the prayer with a capital letter** (for example `pC` instead of `pc`), or answer "Project?" with yes when you pick the prayer by name.
- You aim a bolt, and it heals the first player it hits.
- Mana cost is the same, and **failure chance is halved**.
- The target gets the listed HP and cut −10. They do **not** get the stun or full cut cure that the self-cast version gives.
- Projected Cure Light Wounds heals 2d8, not 2d10. The others heal the same amount as self-cast.

## Failure rate

```
fail = base − 3 × (plev − Lv) − WIS bonus
       + 25 if you're wielding an edged weapon that isn't blessed
fail = max(fail, WIS minimum)          # Priests can reach 0% (ZERO_FAIL)
fail += 15 if stunned (25 if heavily stunned)
fail = min(fail, 95)
```

For reference (from `tables.c`): at WIS 18/50 the bonus is 10 and the minimum is 4%. At 18/100 they're 21 and 3%. At 18/150 they're 36 and 1%. The minimum reaches 0% at WIS 18/200.

## Differences from vanilla worth knowing

- **Cure Critical Wounds** only cures cuts, not stun, poison or confusion.
- **Probing** covers everything within 20 squares, even monsters you can't see.
- **Life Restoration** and **Remembrance** can revive or restore another player standing next to you.
- **Word of Recall** takes its depth from an `@R` inscription on the prayer book.
- **Alter Reality** regenerates the level for other players on it too, and they get a save to stop it.
