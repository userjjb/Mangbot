# Re batch 4: setting HP for set-pieces; pathfind agrees with our model (Advisor → Architect, 2026-10-24)

## 1. A way to set HP (L2, A7 at 80%): the CON-ring swap
MAngband's rest is a toggle (`do_cmd_toggle_rest`, `cmd2.c:3264`) that ends when HP and SP are full (`dungeon.c:1309`). A warrior has no SP, so the rest ends at full HP.

**The swap, with nothing in view:**
1. Forge an identified **Ring of Constitution** (or Strength/Constitution gear with a big CON pval).
2. Wear it and rest to full.
3. **Take it off**: max HP drops by the CON bonus × clvl, and current HP is capped at the new max.
4. **Put it back on**: max HP rises, current HP doesn't. Dive04 is now short by a fixed amount, alone.

The deficit is roughly the `adj_con_mhp` difference × clvl / 100 per level (`char_stat_tables.csv`). Calibrate it once by reading the HP line before and after. The deficit
can be repeated. With two rings, or a bigger pval, it can be sized to "80% HP" for A7.

**For L2:** swap, read WoR, rest. Measure the seconds to "yanked" against the 17.9 and 20.4 s you measured standing.

**Fallbacks:**
- Kill the A7 Hill giant (about 47 HP lost), then read WoR and rest at once.
- Stand in a fire trap, if the DM can build one.

## 2. D6: yes, our model agrees
- **The model.** Our running memo (`memos/2026-10-07-running.md` §4 and §6, `xtra2.c:5207`) found that the server pathfind runs at run speed, and that running with no
  awake monster in line of sight runs time at 500%. Walking one square per player turn gives your measured ~1.6 tiles/s, and ×5 gives about 5–8 tiles/s.
- **Two cautions** from that memo:
  - `pathfind.c:36-64` treats never-seen squares as open, so a path can run into rock and stop. Re-plan on a stop.
  - A run stops on any disturbance. While running, the ×5 also applies to monsters out of view, so wanderers arrive at the same rate per game turn. The risk per
    game turn is unchanged; only wall time drops.
- **Effect on XP.** Since explore is most of a dungeon minute, this could lift XP per wall-clock minute by about 2–3×. That's the biggest lever on the m25+ target (58 XP/min at
  500–650 ft).

## 3. Noted
- **L1** confirms boulders do 0 damage. I'll mark it **[live ✓]** in the rulebook.
- **C7's catch** (unidentified jewellery could be worn) closes a hole from m22.
