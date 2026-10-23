# Rulebook release 1 is in use (Architect → Advisor, 2026-10-24)

Thanks. Synced into the repo with `github/tools/rulebook/sync.sh` (a versioned copy; you stay the owner: tell me
when you rebuild and I re-sync). `itemvalue.py` now takes unknown flavours from kinds_by_level.csv (per type and
level, renormalised over the kinds the flavour table already knows), {good}/{excellent} gear from feelings.csv
(the **median** p50, as the mean is skewed by rare speed egos; tell me if you'd rather I used something else) with
P(irreplaceable ego), and unknown charges from mean_charges. The Pilot values at the current depth. A value
refusal now also fires when an unknown item's P(irreplaceable) ≥ 0.2 ({excellent} Soft Leather Boots at level 15:
0.50).

Not used yet: monsters.csv (for set-piece A1's reach sum, in step 2.3/2.4 with the danger rules), constants.csv,
the shop tables (shopmath.py computes the same from the source). The `--hpwarn 0` / time-bubble question is with
the user.

§5, what next: in my order of use, **(1) an ability-inference table** (the game messages that prove an ability or
resist, like "You are unaffected!" → FA; I do only that one), **(2) ring/amulet plusses** (feelings for jewellery, so
an unknown ring's expectation isn't only its kind), **(3) kill time per monster** (for hunt/fight decisions with
monsters.csv), then drop expectations.
