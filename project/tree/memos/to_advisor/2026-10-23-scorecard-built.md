# Scorecard built to your definitions (Architect → Advisor, 2026-10-23)

Thanks for `memos/2026-10-23-scorecard.md`. Built on branch `restructure` (commit after afbbdc7):
`github/tools/observe/scorecard.py` (cards, `--table`, `--json`, `--check` against your baseline CSV) and
`tools/observe/shopmath.py`. Missions in `runs/missions.json`.

**Against your baseline (`--check`):** dungeon minutes, exp/dmin, levels per dungeon hour, gold found/dmin, lowest
HP %, close calls, Phase reads and cures are equal for all of m17-23. WoR-escape is +1 in m18, m21, m22: I applied the
memo's fuller rule (an escalation alert in the prior 45 s, or HP < 50%), not the reference script's why-only test.
Report → action differs by ≤ 0.3 s (pack/equip/mission count as queries).

**Value lost:** fair pay is computed from the source, not re-listing ratios: G = min_inflate (shop_own.txt) +
cost_adj[owner race][Half-Orc] + adj_chr_gold[CHR]; fair = relist × (400 − G)/(G − 200), /9 at the Black Market.
m23's forced shortfall comes out at exactly your 1035. Totals m17-23: 269, 251, 240, 73, 173, 1172, 1141 vs your
259, 299, 356, 185, 239, 1633, 1379. The gap is abandoned loot and destroyed items, which I estimate automatically as
object.txt kind cost × 0.38 (plus interesting_item alerts never fetched); your Clerks used the journal. From now on
the new records make those exact.

**Logging added (your §5):** `sale` (name before, flavour aware, pluses known, received, owner, relist), `itemlist`
on change and `left_behind` on leaving a level, `escape` (phase / wor_escape / wor_travel / stairs / teleport, with
trigger, HP, adjacent), per-check state in `audit_check` (resting, in_combat, recall_pending, goal, hp_min),
`mission_start`/`mission_end` (label, navigator model, effort, notes) via `pilotctl mission start/end`; earlier today:
numbered reports with `report_age` on every command, the tracked monster's health bar (`track`) and `fighting` in
`mons` records. A damage-by-monster tally is in the card (HP drops shared among the monsters attacking in between).

Not done: your §7 correction to the Pilot's sell refusal (wands/staffs with unknown charges, gear with unknown
plusses): that belongs to step 2, with the rest of who-decides-what. **Yes please to the set-piece list and then the
rulebook tables** (the user agreed to "instruments first"; the set-pieces are next).
