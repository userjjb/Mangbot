# Synthesis: 2026-10-24-structures

## S3 (logs) — read, key claims checked
- **Nar group = summon trap, not a structure.** Verified: events.jsonl 1082980 (empty monlist, 02:57:12), 1082991-3 ("You found a trap!",
  "You are enveloped in a cloud of smoke!", then the 4 monsters). Code: cmd1.c:1049-1059 summon trap = 2+randint1(3) calls of
  summon_specific(Depth, py, px, Depth, 0); monster2.c:2552-2589: level (Depth+lev)/2+5 = Depth+5, type 0 = any race incl.
  uniques, placed AWAKE with groups. [code ✓] At 650 ft: monsters up to level 18 (+ boosts). WIS drain "You feel very naive"
  came from this group (S3 finding 4).
- Trap hits in all dive04 logs: 24 "You found a trap!", 2 summon traps (10-23 09:20, 10-24 02:57), 15 fire, 5 dart, 1 teleport,
  1 trap door. Staff of Trap Location sold (Magic shop, shop_stock.csv). Low priority.
- 1-wide run >= 8: 9 of 16 dumps were rings (44% false positives); >= 20: 3/3. Ring runs are broken by doors and 2-wide tunnel
  entries (Nar ring 6-7). Lead: merge collinear runs across doors/gaps.
- Recognition timing: pit recognised the same second as the first arrow (+71 s); Nar ring +17 s. No warning gap on the pit.
- Feelings and awake rates do not separate structure levels from controls.

## S2 (vaults, mixes) — read, key claims checked
- Summon trap: same conclusion independently [code ✓ above]. Nar: no FRIENDS/ESCORT (S2 finding 14; monster.txt).
- Vault cells use place_monster(Depth,y,x,TRUE,TRUE) = asleep, groups: generate.c 2436-2475 [code ✓]. Pit/nest awake (R1, code ✓ earlier).
- room[] table generate.c:259-270: min level 3 for types 3/4, 5 for 5/6/7, 10 for 8 [code ✓].
- vault_monsters inner loop has no break (generate.c:1084-1097): up to 9 tries each placing when empty [code ✓ — I read it].
- At D10-20: orc pits (troll only at D20, 1/20) and jelly nests (incl. ',' mushrooms) only. Orc pit outer ring = weakest orcs.
- Vault sealing (22 of 149 templates unenterable) is INFERRED from tunnel code; not used in the memo except as a lead.
- Level-vs-depth alone does not mark a lesser vault ('&' cells mostly in depth); count + compact walls + sleeping does.

## S1 (code) — read, key claims checked
- Type 4 light: generate.c:1412 light = Depth <= randint1(25) [code ✓]; nests/pits place_double_room(..., FALSE) = dark (S1 1871/2040).
- Tunnel 2nd square dug only if FEAT_WALL_EXTRA (generate.c:2797) [code ✓] -> 1-wide beside room walls.
- Type 9 vaults: S1 said never built; S2 right: init1.c:1015 rewrites typ 9 -> 8 [code ✓]. 82 greater (irrelevant at D10-14: ~0/level).
- Lattice: all 7 recogniser hits at Y in {16,27,49}, X in {49,115,148,181} [log ✓]; options.prf has Y:dungeon_align [✓].
- Vaults force "special" at Depth <= 50 (generate.c:2519, 2559) [code ✓]; pits/nests at Depth <= 17 always (Depth²+1 <= 290).

## Advisor's own finding: auto_scum is ON
- github/lib/user/options.prf:38 "Y:auto_scum" (client preloads options.prf, c-birth.c:125). Server generate.c:4275-4299: when the
  player generating the level has AUTO_SCUM and the feeling isn't suppressed, the level is regenerated (up to 100 tries) unless
  feeling <= 7 at Depth >= 10 (rating > 20 or special), <= 8 at Depth 5-9, <= 9 below. [code ✓]
- Logs (arrival message + feeling within 4 s, all dive04): Depth 10-14: 81 arrivals: suppressed 14, special 14, very good 4,
  good 3, strangely lucky 7, luck turning 10, not found 29. NO feeling 8-10 at Depth >= 10; at Depth 6-9 none 9-10. Matches the
  auto_scum acceptance rule exactly. [log ✓]
- 14 of 38 informative arrivals at 500-700 ft = "special" (37%) vs ~5% unscummed (S1 sim: pit/nest .038 + lesser vault .014 at D13).
  Implied: ~9% of ordinary levels pass rating > 20 (rough).
