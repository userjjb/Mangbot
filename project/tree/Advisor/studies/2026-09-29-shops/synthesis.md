# Synthesis notes — shops

## S3 (light/food burn) — read 2026-09-29, verdict: very good; its "urgent" claim verified
- Burn loop (dungeon.c:1103-1108, light at :1485-1492): every `time = level_speed(depth)/1000 ÷
  (timefactor/100)` game turns; timefactor = base_time_factor (xtra2.c:5164ff) = MAX_TIME_SCALE 1000
  when **resting with no monster in view**, also in town; but player turns in town use time_factor()
  which returns NORMAL (100) at depth 0 (xtra2.c:5254-5262) ✓ → **resting in town burns light ~10×
  faster per real second** (explains Dive04's three torches). Food: no digestion in town ✓
  (dungeon.c:~1113). Regeneration shares the same loop (so resting in town also heals ~10× faster).
- Accepted: FPS 75 (mangband.cfg), time = 37 town / 49 (500 ft) / 52 (1000) / 57 (1500); torch 5000
  → 41 min town (awake), 54–63 min in the dungeon; lantern 15000 → 123–190 min; store torches/lanterns
  come half-full (2500/7500, store.c:992-995); ration ≈ 27–32 min in the dungeon.

## S2 (prices) — read 2026-09-29, verdict: very good
Verified (store.c:183-222; tables.c:1226): buy price = (value × adjust + 50)/100, adjust = max(100,
greed + g_info[owner race][player race] + adj_chr_gold[CHR] − 200); sell: adjust = min(100, 400 −
greed − race − chr); store 6 (black market) ×3 buy, ÷3 sell; home (8) special. adj_chr_gold[CHR 4]
= 125 ✓. No haggling. Reproduces mission-8 prices (Phase 24, Enchant To-Hit 52/151 on sale, Soft
Leather 24, Dagger 16…) except CCW 152 (Temple owners give 154–159 at CHR 4). Discounts: mass_produce
25/50/75/90% at 1/50, 1/300, 1/600, 1/1000 for items ≥5 gold; store_shuffle puts ~10% "on sale" 50%.
Selling pays ~38–65% of value depending on store/owner.
