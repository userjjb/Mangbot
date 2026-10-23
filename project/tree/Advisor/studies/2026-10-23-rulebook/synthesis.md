
## Release 3 (drops) — D2 checked (session 4)
- Gold amounts: re-checked scratch/D2/gold.csv with my own script: copper 312 piles in [12,53] mean 28.6 (model 28.5), silver 101 in
  [15,80] mean 43.4 (43.5), garnets 19 mean 63.5 (56.0, small n, garnets 9/10 weights unequal by level), rare metals within range.
  Verified. Outlier: 3000 "gold" at dive03 t=8.459 in TOWN (town monlist) -> a grant/test pile, not a drop; ignored.
- Metal by depth: consistent (D2's table). Floor vs drop gold not separated.
- Unique drops: can't test — itemlist omits inscriptions; only stepped-on items show {Unique}. 13 kills, 0-1 inscribed items each;
  one ego seen (Wormtongue's Soft Studded Leather of Resistance, dive03). Ordinary-kill drop rates: logs have no monster
  coordinates (lead for "What I lacked").

## Architect's step-2.2 questions (memo to_advisor/2026-10-23-step22-town-kit.md), answers drafted for the r3 note
- Restore Charisma: Dive04's CHR max is 4 (Rot jelly drained 4->3 at 550 ft, operations notes line 167), so Restore gives 3->4 only,
  NOT 3->18. shop_owners.csv: every non-BM owner pays +5 points (+13.3% relative) and charges -5 points at CHR 4. Sales m17-m23 =
  5,339 gold / 7 missions (V1_value_events a_sale*) ~ 760/mission -> ~100/mission from sales + ~25 from buying. Potion base 300 ->
  ~470 at CHR 3. Pays back in ~4 missions if not re-drained. Verdict: lowest tier, only with spare gold; the Rot-jelly avoid rule matters more.
  The big CHR gains need Potions of Charisma (gain, k161/164? base 500/1000) - not sold in town normally.
- Tier order (Restore STR/DEX/CON before kit extras, after WoR + supply minimums): agree; STR/DEX drive blows, CON HP.
- Never-sell devices: Teleportation (staff), Recall (rod), Teleport Other (wand), Speed (staff), Door/Stair Location, Detect Evil /
  Detection, Enlightenment/Magic Mapping, Perception, Stone to Mud (no-path emergencies: m17), healing/curing staffs and rods.
  Fine to sell: Treasure/Object Location, Light, attack wands/rods unless the Pilot aims them; extras beyond 1 of a kind.
