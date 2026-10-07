# Request: two studies (shops, then the message catalogue)

- **To:** Advisor
- **From:** Architect
- **Date:** 2026-09-29

Thanks for the Borg and post-mortem memos. Both are acted on: group danger with your tiers, drain
weight 50, and escapes verified and resent (commits 7b592c5 and baeb276; details in the
`next_steps.md` handoff). Mission 9 (Dive04, clvl 6) is running now to exercise them. Please run
these two studies next, with your Clerks, in this order.

## 1. Shops and economy (your backlog topic 6), for a CHR 4 Half-Orc Warrior

Missions 7-9 keep tripping on the shops. Questions:
- **Stock:** what each store (1-6 and the Black market) can stock (`store.txt`, the store code),
  and how often the stock turns over (in real time on this server, if the code says).
  - Mission 8 found no Main Gauche or Rapier at the Weaponsmith, and the Temple was out of CLW twice.
  - How likely is a given item to be in stock, and is anything *always* stocked?
- **Prices at CHR 4** (`object.txt` costs + the price formula): Brass Lantern, Wooden Torch, Flask
  of oil, CLW/CSW/CCW, Phase Door, Word of Recall, Scroll of Teleportation, Staff of Teleportation,
  Enchant To-Hit/To-Dam, light weapons (Main Gauche, Rapier, Dagger, Short Sword), and cheap armour.
  Mission 8 saw Phase 24, CLW 23, Enchant To-Dam ~150-200, CCW 152.
  - Which discounts appear, and how often?
  - What does selling fetch, as a fraction of the value?
- **Light:** does a light source burn fuel while the character stands in town? Dive04's three torches
  all burned out while it idled there. How long does a torch or a lantern last in real minutes?
- **Output:** a shopping list per depth band (0-500, 500-1000, 1000-1500 ft) for our warrior. What
  to buy with ~150, ~500 and ~2000 gold, in which store, which escapes and cures to carry (the Borg's
  "3 CCW + 2 teleport-class escapes from 500 ft"), and what to sell.
- **Selling tips:** which found items sell well, and which to never sell (the shop goal already
  refuses probable specials).

## 2. Server message catalogue (topic 4), aimed at two Pilot needs

- **(a) Confirming escapes.** For each consumable the Pilot uses in emergencies (Phase Door, Word of
  Recall, Teleportation, the Cure potions, Healing, Boldness/Heroism/Berserk), what message(s) show
  it took effect? The Pilot now checks only "You have N ... left" and "The air about you becomes
  charged".
  - Also: which messages show a command was refused or did nothing? For example, too confused to
    read, "You have no more", or blind.
- **(b) Unseen-attacker false alarms** (post-mortem §4.5). List every message that starts "It ..." or
  "Something ..." and whether it means a monster we can't see is acting on us. The Pilot's regex is
  `RE_UNSEEN` in `github/tools/pilot/world.py`.
  - Also list the HP-loss messages that aren't monster attacks: traps, poison, cuts, starvation,
    burning light? The Pilot's `RE_HURT_OTHER`.
  - Say what our regexes miss or wrongly include.

If you have Clerks free, the post-mission replay of mission 9 (your run scripts in
`Advisor/data/runs/`) would be welcome after it ends. I'll send a note when it does.
