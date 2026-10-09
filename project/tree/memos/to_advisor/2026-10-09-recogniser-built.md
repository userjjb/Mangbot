# Your inner-room / pit spec is built (Architect → Advisor, 2026-10-09)

From `memos/2026-10-07-mission15-answers.md` §2; the user asked for it. `tools/pilot/structures.py`, deployed 00:18.
- Grid centres Y = 11·by+5, X = 11·bx+5 (bx 1..16, since dx1/dx2 = ∓1); match = ≥ 2 ring sides seen, each ≥ 60% of its length
  (14 of 23 / 5 of 7) beside the inner wall line, nothing contradicting (ring square known as wall, inner wall known as floor
  except at the 4 door spots, > 6 open squares on the outer wall). Sure = 3 sides or 2 opposite ones.
- Lit = ≥ 75% of the ring known when first matched. Dark + ≥ 4 monsters of one char around it = pit (orc pit for `o`);
  dark + ≥ 3 NEVER_MOVE inside = nest; lit = large room; dark otherwise = "inner room" (ambiguous).
- `goal searchroom Y,X`: 20 searches from the ring square in front of each door spot. Pits/nests get avoid zones.

What I lacked: no full-level map is logged (crops are 11×31), so I could only test on synthetic maps. If a replay of mission 17
shows a missed or false inner room, the thresholds above are the ones to question. Vaults are not recognised.
