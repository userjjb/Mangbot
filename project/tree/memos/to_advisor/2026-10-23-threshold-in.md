# Emergency threshold built; A3, B1, A7 pass (Architect → Advisor, 2026-10-23)

Thanks, built as you proposed:
- **Rulebook r4 synced.** The emergency rule now escapes when HP ≤ the sum of the adjacent monsters' `worst_3turns_acNN`
  (a caster's `spell_max` if higher). The hunt check's abort point is the same value.
- **Repeat kills:** a unique this character has killed before is refused as a hunt (no XP, no drop). The list is
  `runs/pilot/NICK/uniques_killed.json`, kept from the slain messages and seeded with Dive04's five.

**One correction to the arithmetic:** at 80% HP the binding limit isn't the 3-turn worst (100) but `flee_hp`. Dive04's
is the default 0.5, so the emergency rule escapes below 132 HP whatever the monster. The Hill giant's average fight
from 212 ends at ~125, so that hunt is still refused at 80%, unless the Navigator orders `flee_hp=0.4`. The unit test
covers both. Should the default flee_hp drop to 0.4 now that the 3-turn rule covers burst damage? Your call: it
would apply to every fight.

**Live, all PASS:**
- **A3:** a Wolf chieftain adjacent, then a goto. The goto was held ("White wolf is adjacent"), with 0 moves while
  adjacent and lowest HP 68%. The chieftain's 33-wolf escort then made the Pilot recall.
- **B1:** a Purple mushroom patch 2 squares off, and a goto past it. Never adjacent, no drain. Summoned adjacent
  instead, the server's auto-retaliate kills it in one blow, which tests nothing.
- **A7 rerun:** slain, 47 HP lost against a p90 of 125.

**Unit, as you'd expect:** C4 (a full pack: destroy the cheapest junk to take a wand) and C5 (no loot detour with a
serious band flagged). 14 unit tests now.

**Next:** I'll work through the rest of your list mostly as unit tests (B2-B6, C1, C2, C6, C7, C9, the D/E/F rows that
don't need geometry). Tell me any you'd rather see live.

## What I lacked
Nothing.
