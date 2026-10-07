# Synthesis: identification and selling (working notes)

## Verified by the Advisor (code lines opened)

- Sale price at CHR 4: shop-buys adjust = 100 + 300 − (greed + race factor + adj_chr_gold), capped at
  100 (`store.c:217-225`). At CHR 4 (adj_chr_gold 125) that is 200 − buy%, i.e. 30–46% at the
  Alchemist/Temple/Magic shop (65% only Kon-Dar, Armoury). **F's "30–46% looks wrong" = false alarm**:
  the cap binds only at high CHR (old forum sales of 92k/60k were by high-CHR players).
- Quaff: `object_tried()` always; aware only `if (ident)` (`cmd6.c:219-229`). [P ✓]
- Cures identify only if they change something: CLW `hp_player(15)` / cure blind / cut / confusion
  (`use-obj.c:483-490`). At full HP with no status, an unknown CLW/CSW/CCW stays "tried". [P ✓]
- Salt Water: food → STARVE−1, paralysed +4 ticks by `set_paralyzed` directly (Free Action doesn't
  stop it), always ident (`use-obj.c:261-270`). Sleep 4–7 ticks unless Free Action (`use-obj.c:308-318`). [P ✓]
- Death `take_hit(5000)`; Detonations 50d20 + stun 75 + cut 5000 (`use-obj.c:381-398`). [P ✓]

- Staff of Perception charges randint1(15)+5 (`object2.c:2350`); recharge i=(60+100-lev-10c)/15, backfire
  destroys one staff (`spells2.c:3118-3151`, `SAFE_RECHARGE = false` in both cfgs line 71), success +2+randint1(6)
  (`spells2.c:3170-3176`); Recharging scroll strength 60 (`use-obj.c:891`). Device fail returns before the
  charge is used (`cmd6.c:477-497`). Selling: price from object_value(p_ptr) BEFORE `object_aware`+`object_known`
  (`store.c:2134-2141`). [E ✓]

## Corrections to dispatches

- F finding 7: "Perception 1d2 charges" is the P: line damage dice, not charges (see E for charges).
- F contradiction about 30–46%: resolved above.

## Script results (data/identify/dist.py, kinds.py)

- Lethal potions (Death, Ruination, Detonations) at object levels 10–30: each 0.01–0.02% of unknown
  potions, combined ≈ 0.03–0.05% (≈1 in 2,000–3,000) [to recompute in value.py].
- Scroll hazards in tval: Summon Monster 13% at L2, 2–4% deeper; Aggravate 8% at L5, 2–4% deeper;
  Summon Undead ~0.1% to L10, then 3–5% from L15; Curse Armour/Weapon 0.03–0.1% each to L30.
- Staff of Summoning 5–9% of unknown staffs from L10.

- value.py: mean shop payment per unknown item vs aware (mean owner): potions 9 → 20/31/54/87/120 at
  L5/10/15/20/25; scrolls 9 → 19/25/33/295 (L20+ Acquirement skews the mean); staffs 27 → 83–270 (+charges
  when known: 139–378); wands 20 → 117–194 (known 181–290); rods 35 → 84–705; rings 18 → 50–206 (bonuses not
  modelled); amulets 18 → 82–254. Worthless kinds are 11–42% of potions (refused once known!).
- ID cost: Identify 78–81 (57–60 at 25% off). Perception long run 66–69/charge (staff ~1,020–1,120 with
  13 charges = 79–86/charge; each Recharging 310–322 at 0 charges gives 0.9×5.5 charges; 10% lose the staff).
  **Claim 4: marginally true (−15%) against full-price Identify only.**

## Cross-dispatch table (fill as dispatches arrive)

| question | P | D | E | F | L | resolved |
|---|---|---|---|---|---|---|
| potions safe out of combat? | yes except Death/Deton. (L55/60), drains costly | | | yes w/ caveats | | |
| scroll/staff danger | | | | 7 scrolls, 4 staffs negative; no deaths reported | | |
| ID gain vs cost | | | | no data | | |
| Perception+Recharge vs Identify | | | | no support | | |
