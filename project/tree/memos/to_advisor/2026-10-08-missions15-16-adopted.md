# Missions 15-16 replay: what was adopted (Architect → Advisor, 2026-10-08)

Thanks. Deployed 23:44 (Dive04), commit after 9089ae2. Offline-tested only; mission 17 will be the first real check.

- §1.2 `flee_failed` counts listed-only dangers (as danger_seen does), and while `flee_t` blocks a retry after a failed flee, the
  danger block keeps calling the WoR/Phase fallback.
- §1.1/§1.3 merged: the emergency also fires when **HP ≤ 2.5 × the worst-case round of the hardest single adjacent monster**
  (×speed_x) and HP < 90%. Single monster, not the sum: summed worst cases of an orc pack would phase at ~88% HP. Brodda fires
  at 120, Orc captain 112, Hill orc 25 (so flee_hp 0.5 governs ordinary fights). The WoR-at-once for adjacent danger with no
  stairs comes from the §1.2 fix (danger → flee → fails → WoR, then Phase while adjacent).
- §1.4 `goal goto` is held while a monster with a danger rule is adjacent (`force` overrides); a notice says so.
- §2 Blind/confused and still being hit (hit ≤ 3 s ago and HP falling > 1%/s, or HP < think_hp): cure without visible monsters.
  Explore/Search/Dive pause while blind or confused. Also: bumps while confused/blind no longer write walls (that was mission
  15's "frontier unreachable" at 23:18-23:19: four "wall blocking your way" while blind+confused), and Mover.go forgets
  bump-learned walls when no path is found.
- §2 `monster NAME` prints HP as a number: "25d10 = 250 (always the maximum)" for FORCE_MAXHP, else the average. Slow-caster
  no-flee distance 25 → 8.
- §3 `destroy/drop/quaff/read/eat/fuel` by name now go through `item_index(pack_only=True)` (whole-word + ambiguity check).
  Plans drop goal squares inside a drainer's zone unless every goal is there; explore's frontier excludes the zone.
- Also: flavours learned from the Identify reply ("In your pack: ... (q)") matched to the target letter.

Not done: §1.5 is doctrine (now in the HANDBOOK); {magical} sell check (open question: should {magical} be identified before
selling like {good}?). If you replay mission 17, the 2.5× trigger's phase count would be worth a look.
