---
name: mangband-restructure
description: Since 2026-10-22 the Navigator/Pilot system is being restructured (instruments first) on git branch `restructure`; revert steps are in restructure.md
metadata:
  type: project
---

The user decided on 2026-10-22, after mission 23, to restructure the Navigator/Pilot system rather than keep patching
per mission: instruments (scorecard, telemetry) first, then who-decides-what, a rulebook from the source, a test harness
(the Advisor's `memos/2026-10-19-starting-over.md`). Keep Dive04. Work happens on git branch `restructure` in `github/`.

**Why:** the Navigator kept making costly irreversible calls (Free Action boots sold for 3 gold, hunting uniques,
looting under a band), and per-incident fixes created new failures (the bulky-pickup rule lost Brodda's Scimitar).

**How to apply:** don't run missions or patch per incident during the restructure unless the user asks. If the user
asks to go back, follow `/projectnb/jbrcs/mangband/restructure.md` (tag `pre-restructure` = 767bf60; saves and non-git
files in `runs/backup-pre-restructure-20261022/`). See [[mangband-next-steps]], [[mangband-project-map]].
