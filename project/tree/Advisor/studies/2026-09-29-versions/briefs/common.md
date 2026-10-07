# Shared context (version-history study)
Our bot plays **MAngband 1.5.3** (real-time multiplayer Angband). Much of our doctrine comes from the
mangband.org forums, whose posts are mostly from 2002–2014 (server 0.7–1.1.x). We need to know
**which game mechanics changed between those versions and 1.5.3**, so we can tell which forum
advice is outdated. Repo: `/projectnb/jbrcs/mangband/Advisor/data/versions/upstream/` (the upstream
git history, 2005–2022; tags v1.1.2, v1.1.3, v1.1.4, v1.4.0, v1.5.0–v1.5.3; cloned with
`--filter=blob:none`, so `git show <hash>` fetches file contents on demand — that's fine, but be
sparing: open diffs only for commits that matter). Read only.
What matters (game mechanics a player or bot would notice): combat and damage formulas, monster
stats/AI/spells, speed/energy and the time bubble, stairs/levels (connected stairs, level
persistence, hounds on arrival), uniques (per character or global), items (potions, scrolls,
light, recall timing), stores and prices, resting/regeneration, death/ghosts, experience, classes and
races (especially warrior, half-orc), party play, and server rules. Skip: build system, client UI,
graphics, networking internals, code refactors — unless they change gameplay.
The forum memo's claims you may check against: `/projectnb/jbrcs/mangband/memos/2026-09-26-forum-distillation.md`
(skim §1–§4 and Addendum sections A–C).
Output: a dispatch at the path in your brief (dispatch format), with a table
**change | version/date (commit) | what it means for play | forum advice it affects (if any)**,
most important first. Cite commit hashes; quote a line of diff where it settles a point.
Scratch: `/projectnb/jbrcs/mangband/Advisor/studies/2026-09-29-versions/scratch/`.
