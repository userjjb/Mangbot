# Field notes (lessons from past missions)

Read this after the HANDBOOK, at every mission start. It holds what play has taught. The HANDBOOK holds how the
system works. The Architect updates it after each mission from the reports and your complaints. The newest
lessons are first in each section. Mission numbers (m24...) point to `runs/pilot/dive04/reports/`.

## Where the XP is (Dive04, clvl 25-27, Free Action + See Invisible, AC ~70-77)

- **XP per minute by depth, m35-m42:**

  | depth | XP/min | minutes there |
  |---|---|---|
  | 600 ft | 31 | 68 |
  | 650 ft | 54 | 166 |
  | 700 ft | 125 | 14 |

  700 ft is a small sample: only trapdoor and flee visits. `prep` shows the current numbers. Deeper has paid
  better at every step so far.
- **`max_depth` is 750 since 2026-10-25 (the user), a trial.** Work 650-750 ft for the next 2-3 missions. The
  threats native to 700-750 ft are covered: Free Action (Homunculus), See Invisible (Clear hounds), resist cold
  (Gnome mages). The rest are packs the Pilot already fights. What comes next, at 800-900 ft, is confusion with no
  save (Umber hulks, breeding Hummerhorns; no resist confusion yet). At 1000 ft come poison-breathing Air hound
  packs (no resist poison) and the orc-captain uniques. Raising the cap again is the user's call: ask with `say`.
- **One long trip beats two or three in a 45-minute mission.** Each recall costs ~2 minutes and a risky arrival. m40
  ran three trips and had the series' lowest XP (37.7/dmin). The best missions ran 1-2 trips (m38: 87.2).
- **Leave a quiet level.** The `Rates:` line shows XP a minute on the current level. Good levels at 600-650 give
  50-70. A level under ~20 for several minutes is worth leaving (the plan also leaves after 3 quiet minutes).

## Dangers met at 600-700 ft

- **Fear disables a warrior: carry Heroism.** m41: afraid, three monsters adjacent, 36% HP. The kit now keeps 3.
  The Pilot quaffs one when afraid and in danger.
- **Thieves take carried gold.** Novice rogues, Scruffy hobbits and Brigands do this. m41 lost ~1590 in one touch,
  m29 196, m31 ~200. Their news often arrives too late. Spend gold in town rather than carrying 15k into the dungeon
  when there's something worth buying.
- **Umber hulks confuse, and Priests summon and cause fear.** In m42 they came together with an unseen summoner,
  bringing HP down to 151/336. The Pilot handled it: recall, staff, and attacking the Priest first.
- **Moaning spirits drain DEX at 600-650 ft and pass through walls.** See Invisible shows them. Restore Dexterity is
  sometimes out of stock (m32).
- **Trapdoors** drop you a level below `max_depth`. The Pilot climbs back (m28, m39).
- **Orc pits at 650 ft** have 95 orcs and come with "feels special" arrivals (m24, m29, m33, m40). The Pilot finds
  the stairs first on special levels.
- **Disenchanter molds** take a plus from gear when meleed. The Pilot now leaves items lying beside them (m37).

## Shops and money

- **Black Market (store 7):** Speed ~383 (m40). The kit buys 2 Speed at no more than 450 each. A Black Market
  buy needs the `7/` prefix. Stock is often missing.
- **Exact lines:** to buy one particular line among several with the same name, copy the line `gear` prints (m41
  got plain gloves instead of [1,+5]).
- **Restores** cost ~480 at the Alchemist. **Kill a drainer before quaffing Restore**: m42 quaffed mid-fight and
  was drained again (~480 wasted).
- **XP per gold** (from recent play; `gear` and `prep` show it) is about 0.4. 1000 gold is worth ~400 XP of play.

## Pilot habits to expect (not bugs to work around)

- The Pilot's own emergency recall often lands before your `goal recall`. Check `status` first; `why` explains it.
- `plan town` sells what the policy sells, and that includes Boldness (Heroism covers fear). Don't buy Boldness.
- Unidentified weapons and spare staffs can stay in the pack when the identify budget is short, so the pack can be
  full on arrival (m42). Use `plan town` with Identify on your buy list if the pack is crowded.
- The Pilot drinks Speed at the start of hard fights, and in emergencies. It teleports when afraid with 2+ adjacent,
  or when 4+ monsters are about in the open.

## What the best Navigator moves have been

- **Noticing what the policy can't value:** m32 wielded the Scimitar of Westernesse (Free Action + See Invisible)
  that the damage-only weapon policy ignored. Look at unusual items in `pack`. If one may carry an ability, `keep`
  it and say why.
- **Strategic buys:** the Staff of Teleportation (m32) and the Ring of Protection [+12] (m37, from `gear`).
- **Reporting precisely:** most Pilot fixes came from complaints with times and numbers. Keep doing that.
