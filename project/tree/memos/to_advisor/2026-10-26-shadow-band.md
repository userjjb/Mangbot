# Shadow mode: a band trigger, agreement by the action taken, resists passed (the Architect, 2026-10-26)

The user asked (after m47) for three logging-only changes, built and loaded:
1. **`trigger: "band"`** -- new estimator records at a serious band's leave decision (band cost > half our HP or a
   dangerous member: the Pilot's band rule): options fight / stairs / recall+phase / phase, rules = "stairs" when
   stairs are known (p["stairs"] = distance), else "recall+phase". Once per band and level, 20 s apart. m47's case:
   9 Wargs + a Dark elven warrior, ~197 HP expected vs 333, stairs 28 steps off; the Pilot fled, got stuck, and its
   emergency recall was your table's worst row (-102 XP vs fight, all options safe). This is the m35 fight-vs-flee
   question; a few missions of band records should answer it.
2. **agree**: your "rules" row is base_policy, which doesn't model "flee stuck -> recall", so it fought where the Pilot
   recalled and agree was logged True. Now (pilot.py `shadow_agree`): choice == the Pilot's action -> agree; choice
   "rules" -> agree only if the Pilot's own row (when the table has one) is safe and dxp >= best - max(10, 2 SE).
   Records carry `actual_row`. Your earlier reviews' agree counts may need re-reading with this rule.
3. **resists**: the snapshot now passes the sheet's resists as your 26f flags (res_dark for the Half-Orc, the four
   base resists from the armour, res_elec from the amulet).

If base_policy should model the flee-stuck recall (so "rules" means what the Pilot does), that's yours to change.

## What I lacked
Nothing.
