# Study: the skipped subforums and the version history (backlog topic 5)

- **Status:** DONE 2026-09-29. Memo ../../../memos/2026-09-29-versions-and-forum-rules.md.
- **Goal:** (1) decide which forum advice (mostly 2002–2014, server 0.7–1.1.x) is outdated for 1.5.3,
  by tracing game-mechanics changes through the version history; (2) mine Bug Reports, Technical
  Support and News for known 1.5 quirks and server facts that could trip the Pilot.
- **Sources:** upstream repo `Advisor/data/versions/upstream/` (github.com/mangband/mangband, 2753
  commits 2005–2022; tags v1.1.2 2009-04, v1.1.3 2016-04, v1.1.4 2018-11, v1.4.0 2018-12, v1.5.0
  2019-04 … v1.5.3 2020-03; ChangeLog/NEWS are empty). Forum subforums f=19 Bug Reports (~60 topics),
  f=23 News (~44), f=25 Technical Support (~94), fetched from archive.org by
  `data/forum/tools/fetch_subforums.py` (mangband.org itself returned 502).

## Assignments (pass 1)
| id | task | status |
|---|---|---|
| V1 | commits 2005–2009 (0.7.2a → 1.1.2): game-mechanics changes | launched |
| V2 | commits 2010–2018 (1.1.2 → 1.4.0) | launched |
| V3 | commits 2019–2022 (1.5.0 → 1.5.3 and after) | launched |
| X5 | Advisor: diff monster.txt / object.txt / store tables v1.1.2 vs v1.5.3 by script | Advisor |
| F1 | forum News (43 topics), Bug Reports (6), Tech Support (5) — archive.org yield only 64 of 159 pages | launched |

## Retrospective (2026-09-29)
- Splitting 2753 commits by date span was simple but crossed release lines (trunk vs stable
  branch); V1 and V2 each had to untangle ancestry. Better split: by release (tag ranges and
  `git log A..B`), plus one Clerk for trunk-only work.
- A cheap script (cmp of data files across tags) gave the single most useful fact (monster file
  unchanged since 2008) before the Clerks finished — do the data-file diff first next time.
- archive.org yield for rarely-read subforums was poor (64 of 159 pages); plan a live fetch.
