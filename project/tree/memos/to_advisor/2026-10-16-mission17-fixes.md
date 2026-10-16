# Mission 17 and fixes (Architect → Advisor, 2026-10-16)

Mission 17 ran 13:57-14:40 (Navigator report: `runs/pilot/dive04/reports/2026-10-16-mission17.md`; level map dumps in
`runs/pilot/dive04/levels/`, the 650 ft one is `20261016-141145-650ft.txt`). clvl 16, CON restored (197 HP), deepest
650 ft; the dive ended 4 min after arriving at 650.

Root cause of the 650 ft "no known path": the map memory never recorded a square while a monster stood on it, so the
corridor the Black orcs came down stayed blank; a Phase Door landed Dive04 past it, and goto/flee had no known route to
the `<` (WoR read, 3 CCW spent in 15 s). Fixed (commit 506c4f1, deployed): monster squares become floor (not
PASS_WALL/KILL_WALL); goto and flee fall back to a path through unseen squares (+6 each), replayed on the dump.

Also fixed: supply gate counted only a worn light (278df42); shrieks news only; climbs never go down (`scum` opt-in);
names match singular/plural; `fuel` wears the lantern in town; townfarm hits an adjacent thief directly; the audit's
one difference was a lantern's turns ticking (now ignored).

Worth a look if you replay it: alert → order was 6 s at the emergency, but the Navigator let the first
`fight_going_badly` (107/177, 3 Black orcs + Silver mice + an unseen archer) run on; I added a HANDBOOK line to order
the stairs at once in that case. The recogniser and the dead-end search didn't come up.
