# observe/ -- refactor candidates (survey, session 10)

- **scorecard.py `--all` is a no-op**: `pick = [m for m in missions if not a.labels or ...]`, so any call without
  labels scores all 200 missions (incl. 156 `sp-*` set-piece runs) and rewrites every card JSON, even `--table`.
  Make `--all`/no-label behaviour explicit, and skip `sp-*` unless asked. Risk S.
- **scorecard.py docstring stale**: says "Six groups" and "16-category time budget"; the card has G (tokens) and H
  (estimator) too and 17 categories with `pilot_down`. Risk S.
- **scorecard.py `card()` is ~170 lines** (groups A-F + estimator + damage inline): split one function per group
  (like `value_lost`/`time_budget` already are). Risk S-M.
- **Duplicated decision/event loaders**: `load()` in scorecard.py and latency.py, the decisions scan in notes.py and
  damage_mix.py; also two definitions of "query commands" (scorecard `QUERY_CMDS`, latency `NOT_ORDERS`, watch
  `NAV_QUERIES`) that disagree. A shared `observe/logs.py` with one list. Risk M (the scorecard must stay equal to
  the Advisor's definitions; check with `--check`).
- **Two damage attributions**: scorecard `damage_by_monster` (HOSTILE regex) and damage_mix.py (MELEE/RANGED
  regexes, rulebook blows) split HP drops by attack messages with different regexes and windows. Share one
  classifier. Risk M.
- **SHOP_CUT = 0.38 defined twice** (scorecard.py and pilot.py) though shopmath can compute it. Risk S.
- **watch_mission.py hard-codes `runs/pilot/dive04`** (no `--nick`); it starts at file ends, so events between an
  exit and the restart are lost (could take a start offset / remember the position in a file). Risk S.
- **watch_mission.py `pilot.log` match on "Error"** catches any log line with that word (not only tracebacks).
  Risk S.
- **wrap.sh**: complaints window is "today, current or previous clock hour" (wrong across midnight, not 2 h);
  `notes.py --questions` has no time filter (may show an older mission's question); `damage_mix.py` always uses the
  700-800 ft default band, not the mission's depth. Risk S.
- **latency.py looks unused** since m22 (no caller; last edited 10-23); the scorecard's group E covers
  report->action and user reply. Fold its alert->contact/order metrics into the scorecard or remove. Risk S.
- **record.py / timeline.py / screen.py / scribe.py unused since 2026-09-25** (no callers; only operations.md lists
  them; timeline.py's commit says "untested draft"). Keep (tiny, human-play study and the Scribe role) or move to an
  `observe/study/` subfolder. record.py's default `--port 18346` disagrees with its docstring/test server (28346).
  Risk S.
- **watch.py docstring** omits F5/Ctrl-F (freeze) from its Keys list and says "Watching never sends a game command"
  next to a key that freezes the server. Risk S.
- **watch.py `feed_line` dead branch**: `elif k == "attention" and e.get("what") == "user_message"` comes after
  `elif k == "attention"`, so it never runs. Risk S.
- **shopmath.py must keep its path**: Advisor's `build_shops.py` imports it by absolute path; pilot.py and
  harness/unit.py by relative path. If it moves (e.g. to pilot/ as a library, which it is), leave a shim. Risk M.
- **next_steps.md stale line**: "Monitor script: $CLAUDE_JOB_DIR/tmp/watch_mission.py (job-local)" -- it lives in
  `github/tools/observe/` now. Risk S.
