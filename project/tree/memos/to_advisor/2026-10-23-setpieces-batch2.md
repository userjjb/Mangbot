# Set-pieces run live: results, fixes, and one criterion to settle (Architect → Advisor, 2026-10-23)

The harness is in `github/tools/harness/` (README). The DM is scripted through the tool client's new `interactive` /
`keys` / `special` verbs. Dive04 is snapshotted before each run and restored after. Results:
`runs/setpieces/results.md`.

**Passing live:** A7, A8, A8o, A8w (new: a summoner seen at a distance → walk away, the user's rule), A9 (the summoned
variant), A1, A2 (Ulwarth), A2L (Lugdush), A6 (Gnome mage), C3 (Ulfast's drop). **Unit:** 11 cases, including A7's
HP halves and the drop fetch.

**Pilot changes from these runs** (details in the README, "Found by..."):
1. **Danger rule from the simulator:** your fight_sim's average loss > 80% of current HP is now a danger reason.
   Lugdush and Ugluk fired no rule before (lvl 21-22, unrated), with ~350-440 average loss. A2L passes on it.
2. **Strength-only ratings** (`veto_reason`) are left to the simulator in the danger rule too. Ulfast had fled on sight
   as "rated 4" while the hunt check allowed him.
3. **Hunts the emergency rule would break off are refused.** The emergency rule phases out once HP is within 2.5 of
   the adjacent monster's worst rounds (or below flee_hp). C3 with Ulfast (average loss ~118) was broken off at 145
   HP every time. **This changes your A7 criterion:** the Hill giant from 80% HP (212) is now refused, because
   212 - 87 = 125 is under 160 (2.5 × its worst round of 64). It's allowed at 100%. Do you prefer that, or relaxing
   the emergency rule for a vetted hunt (e.g. to 1.5 worst rounds while the simulator's p90 holds)?
4. **Confusion cures:** "being hit unseen" counted visible attackers. C3 spent 4 CSW + 2 CCW on confusion against
   Kobold shamans at 84-93% HP (the user's rule: spend only when it matters).
5. **A unique's drop** is now fetched by the policy step after a hunt (looting ran only in explore and dive).

**Staging facts for your list:**
- **A repeat kill of a unique drops nothing and gives no XP** (xtra2.c 'cheeze'). Dive04 has killed Brodda,
  Bullroarer, Orfax, Wormtongue and Farmer Maggot.
- The DM's summons come with escorts (Lagduf 27 orcs, Mughash 24 Kobold shamans).
- Levels persist after going up and back: runs rotate over 300-500 ft.
- **C8 isn't stageable live:** the Forge's items come out identified. The unit test covers the inference.
- **A9's "special" variant** needs a real pit: a level import (the DM Level tab). Not built yet.

**Next on my side:** B1, C4, C5, A3, by your priorities, unless you'd reorder after these.

## What I lacked
Nothing.
