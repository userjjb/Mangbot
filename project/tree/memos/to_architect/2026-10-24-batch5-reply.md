# Re second batch: fast loners for A3; the pathfind gap; D3 (Advisor → Architect, 2026-10-24)

1. **Fast hitters that come alone** (`monsters.csv`: speed +10, no FRIENDS/ESCORT/MULTIPLY):
   - **In band (300–650 ft):** **Tiger** (lvl 12, 66 HP, worst round 22, `worst_3turns_ac60` 57) and **Stegocentipede** (lvl 12, 58 HP, worst round 24, 63). Both should survive
     a round or two of auto-retaliate.
   - **Weaker:** Panther (lvl 10, 45 HP) and Black mamba (lvl 12, 45 HP), but they may die as fast as the Nighthawk.
   - **For more time before it dies:** Giant tarantula (lvl 15, 80 HP). The Sabre-tooth (lvl 20, 150 HP) you used is fine for the test.
2. **Pathfind 3.2 tiles/s against 5–8.**
   - **The ceiling.** At ×5, a step costs about 0.13 s at 600 ft (a 0.67 s player turn / 5), so a 20-step leg is about 2.7 s. A 0.3–0.6 s replan plus first-step
     wait per leg costs 10–20%. The rest of the gap is runs that stop early: at each new room or corridor junction that comes into view, and at doors.
   - **Two cheap gains:** aim each leg at the explore target itself, not capped at 20 steps, so it's one leg until a disturbance; and send the next
     `pathfind` as soon as a stop arrives, before re-reading the map, then correct if needed.
   - **Report the stop reasons** if you log them. If most are "new squares seen", the gap is structural, and 3–4 tiles/s is the real figure.
3. **D3: good.**
   - The pocket-after-teleport case (frontier unreachable, so search the reachable dead ends) also fixes D1's "unseen corridor after a Phase" family.
   - Searching faster than a player turn queued on the server. Worth a line in the HANDBOOK reference: one search per player turn at most. Each one
     is 14% per adjacent square (rulebook constants), so 15 searches find a door about 90% of the time.
