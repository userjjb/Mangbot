# Observe: the viewer, the monitor, scorecards and analysis tools

`github/tools/observe/` holds everything that **watches** play instead of playing: the user's live viewer
(`watch.py`), the Architect's mission monitor (`watch_mission.py`), the after-mission wrap-up (`wrap.sh`) with
its scorecard (`scorecard.py`), Navigator cost (`tokens.py`) and damage mix (`damage_mix.py`), and a few
analysis and human-play study tools. None of them sends a game command. Most read the Pilot's run directory
`runs/pilot/<nick>/` (`decisions.jsonl`, `events.jsonl`, `commentary.jsonl`, `pilot.log`, `asks.jsonl`) and the
mission list `runs/missions.json`; a few talk to the Pilot's control socket (`ctl.sock`) through
`pilotctl.call`. One module, `shopmath.py`, is a library: the Pilot, the scorecard, the unit tests and the
Advisor's `build_shops.py` import it.

Related docs: the log formats and the Pilot's `view`/`viewmap`/`navview`/`note`/`say` handlers are in
[pilot-core.md](pilot-core.md) and [commands.md](commands.md); the EHP use of the damage mix in
[gear-and-estimator.md](gear-and-estimator.md); the mission flow in [process.md](process.md); `freeze.sh` and the
test server in [harness-rulebook-ops.md](harness-rulebook-ops.md).

## At a glance

| Tool | Who | When | Reads | Writes |
|---|---|---|---|---|
| `watch.py` | the user | any time, live | `ctl.sock` (`view`, `viewmap`, `navview`, `note`), `decisions.jsonl`, `navigator.md` | notes via the Pilot (`commentary.jsonl`, `user_note` records); `testserver/FREEZE` (F5) |
| `watch_mission.py` | Architect | during a mission, in the background, restarted on each exit | new lines of `decisions.jsonl`, `asks.jsonl`, `pilot.log` | stdout; its read offsets in `runs/pilot/<nick>/watch_mission.state` |
| `wrap.sh` | Architect | after each mission | (runs the tools below + `pilotctl`) | `missions.json` (end, tokens), scorecard JSON, `damage_mix.json` |
| `scorecard.py` | Architect, Advisor (reads cards) | after a mission (via `wrap.sh`), or ad hoc | `missions.json`, `decisions.jsonl`, `events.jsonl`, `testserver/gdb_run.log`, game tables | `runs/pilot/<nick>/scorecards/<label>.json` |
| `tokens.py` | Architect | after `mission end` (via `wrap.sh`) | `missions.json`, Claude Code subagent transcripts | `missions.json` (`tokens`, `effort`) |
| `damage_mix.py` | Architect | after each mission (via `wrap.sh`) | `decisions.jsonl`, `events.jsonl`, the rulebook | `runs/pilot/<nick>/damage_mix.json` (read by the Pilot's gear evaluator) |
| `notes.py` | Architect | after a mission (via `wrap.sh`), to answer `?` notes | `commentary.jsonl`, `decisions.jsonl` | stdout |
| `shopmath.py` | library | imported | `lib/edit/shop_own.txt`, `cost_adj.txt`, `p_race.txt`, `src/server/tables.c` | nothing |
| `study/record.py` | the user (human play) | study sessions (Sept 2026) | tmux pane | `runs/observe/<stamp>/` |
| `study/timeline.py`, `study/screen.py` | Architect/Advisor | study a `record.py` session | `pkt.jsonl`, `screens.jsonl` | stdout |
| `study/scribe.py` | Architect | at the user's request only | a FIFO | in-game private chat |

Run Python tools with `module load python3/3.12.4`. Paths below are relative to `/projectnb/jbrcs/mangband`.

---

## watch.py -- the user's live viewer

`python3 github/tools/observe/watch.py [--nick dive04] [--hash]`

A curses screen, refreshed every 0.5 s, of one Pilot-driven character. The Architect usually keeps one running in
a private tmux server: `tmux -L mang attach -t watch` (detach Ctrl-b d). It must run on the node where the Pilot
runs (the control socket is a local Unix socket).

**Left/top: the game view.** It calls the Pilot's `view ROWS COLS` (the Navigator's report with a map sized to
the window, no side effects) and `viewmap ROWS COLS` (map characters + colour attributes around @, monsters with
their `monster.txt` colour). It reshapes the report for a human: hides the stat/weapon/ability/audit lines, drops
the character's name/class, turns `Standing on: ... goal:` into a `Goal:` line, abbreviates supplies into one line
(`supplies_short`: Cures CLW/CSW/CCW and a CLW staff, Escapes Phase/WoR/Tele..., Food, Light turns + flasks, then
an `Also:` line), and adds an `Items in view:` line pairing the server's item list with item squares, nearest first
(`items_in_view`). Walls draw as solid blocks (granite/secret doors full, veins shaded) unless `--hash` or the
terminal isn't UTF-8. With 256 colours it uses Angband's 16 colours as xterm shades, else the 8 basic ones. Layout:
feed beside the map when the window is at least 150 columns wide, below it otherwise.

**Right/bottom: the feed.** A tail of `decisions.jsonl` (the last ~200 KB at start, then new lines) showing
these kinds: `act`, `attention`, `goal`, `goal_done`, `goal_failed`, `user_note`, `audit`, `nav_say`,
`nav_complaint`, `nav_cmd`, `nav_ask`, `arch_answer`; plus new lines of the Navigator's journal
`navigator.md` (shown as `NAV: ...`, magenta, with the last 4 earlier ones at start). Who acted is tagged from the
record's `by` field: `[P]` the Pilot on its own, `[plan]` the Pilot carrying out the Navigator's `plan`, `[N]` a
command the Navigator gave directly, `[A]` the Architect. Navigator commands show as `NAV> cmd args` (cyan),
Architect commands as `ARCH>`; pure queries (`status`, `wait`, `prep`, `gear`, `map`, ... the `NAV_QUERIES` set)
are hidden. Colours: alerts and failed goals red bold, actions green, your notes yellow reverse, Navigator replies
(`NAVIGATOR: ...`) cyan reverse, Navigator complaints (`NAVIGATOR LACKS: ...`) red reverse, ask/answer pairs with
the Architect magenta reverse. The feed keeps the last 500 entries.

**Keys**

| Key | Effect |
|---|---|
| type + Enter | a note: sent to the Pilot as `note TEXT` (see below) |
| note starting `?` | a question for the Architect ("why did it do that?"); answered after the mission (`notes.py --questions`, shown by `wrap.sh`) |
| note starting `!` | a message to the Navigator: the Pilot raises a `user_message` attention event that wakes it at once; its reply (`pilotctl say`) shows as `NAVIGATOR: ...` |
| Tab | toggle the Navigator's view: exactly what it last read from the Pilot (`navview`) and how many seconds ago |
| F2 or Ctrl-E | the equipment as the game's 12 slots a)-l), `(nothing)` in empty ones (`equipment_slots`; uses `itemvalue` for item types) |
| F3 or Ctrl-P | the whole pack |
| F2/F3 again or Esc | back to the game view |
| F5 or Ctrl-F | toggle the test server's time freeze: creates/removes `testserver/FREEZE` (same as `github/tools/freeze.sh toggle`). The note line then shows `*** TIME FROZEN (F5/Ctrl-F to thaw) ***`. Only the test server (started with `MANGBAND_FREEZE_FILE`) honours it; the Pilot holds while it exists |
| Esc | clear the typed line (when no panel is open) |
| PgUp / PgDn | scroll the feed by 10 lines |
| Ctrl-C | quit (the character keeps playing) |

**Notes.** The Pilot's `note` handler (`pilot.py: Pilot.user_note`) logs a `user_note` record in
`decisions.jsonl` and appends to `runs/pilot/<nick>/commentary.jsonl`: `{t, note, question, depth_ft, pos, hp,
clvl, goal, last_action, monsters (first 12), standing_on, recent (last 8 acts)}`. If the Pilot doesn't answer,
the viewer writes the note itself to `commentary.jsonl` with `pilot_down` and no snapshot. The Navigator's `say`
also appends to `commentary.jsonl` (`who: navigator`). Notes can also be sent without the viewer:
`pilotctl.py --nick dive04 note "text"`.

**Gotchas.** The viewer's polls (`view`, `viewmap`, `navview`, `note`) are excluded from the Pilot's "agent
activity" clock, so watching doesn't keep the Pilot from idling decisions (it once kept the lantern lit in town).
"Watching never sends a game command" holds, but F5 does stop the test server's clock. The status line shows a
message for 6 s, then the key help again.

---

## watch_mission.py -- the Architect's mission monitor

`python3 github/tools/observe/watch_mission.py [MAX_S] [--nick dive04] [--fresh] [--backlog 3600]` (MAX_S default
1500 s), run with Bash `run_in_background`; when it exits, look, act, and start it again with the same command line.

It reads `runs/pilot/<nick>/decisions.jsonl`, `asks.jsonl` and `pilot.log` from where the previous run stopped
(byte offsets saved after every poll in `runs/pilot/<nick>/watch_mission.state`), so events between an exit and the
restart are reported by the next run. It starts **at the current file ends** instead (and says so in its first
line) with `--fresh`, with no state file, or when the state is more than `--backlog` seconds old (a new session
rather than a restart); a file replaced or truncated since is read from its start. It reads complete lines only
and polls every 2 s. It exits as soon as any poll finds a hit (printing every hit of that poll), or after MAX_S
seconds with `quiet for N s`.

**Exit conditions (a hit):**

| Source | Condition |
|---|---|
| `asks.jsonl` | any new line: `NAV ASK: {...}` (a Navigator question; answer with `pilotctl answer ID "text"`) |
| `pilot.log` | a Python traceback's exception line (`TypeError: ...`, with the innermost `tools/` frame as `at pilot.py line N in fn`), except `BrokenPipeError`/`ConnectionResetError` in a control-socket request (a `pilotctl` client hung up); or the Pilot's `client exited` line |
| `decisions.jsonl` `kind: escape` | any escape except `escape: wor_travel` (a plain trip recall) |
| `kind: gear_eval` | a gear evaluator swap |
| `kind: plan_end` | the Navigator's plan (town/trip) ended |
| `kind: attention`, `what` in | `emergency`, `emergency_loop`, `dead`, `died`, `plan_failed`, `stat_drained`, `user_message` |
| `kind: attention`, `what: stuck` | unless the detail is the routine "hasn't moved from ... for 20 s" |
| `kind: attention` | any whose detail contains "couldn't leave" (the trip's failed-to-leave recall) |
| `kind: note` | detail containing "error", or containing "failed" but not "effect_failed" |

Each decision hit prints `HH:MM:SS kind what: {record minus map/crop/t}` (500 chars).

**Gotchas.** After more than `--backlog` seconds without a run (default 1 h), or with `--fresh`, it starts at the
file ends, so what happened meanwhile is not reported. It does not report the user's `?` notes (those wait for the wrap-up) or plain
`attention` alerts such as `danger_seen` (the Navigator handles those).

---

## wrap.sh -- the after-mission wrap-up

`bash github/tools/observe/wrap.sh LABEL [NICK]` (NICK defaults to dive04). Runs as the Architect
(`PILOT_ROLE=architect`) from `github/tools`, in this order:

1. `pilotctl mission end LABEL` -- by name, because a hot-swap loses the Pilot's in-memory label. Sets `end` in
   `runs/missions.json`.
2. `tokens.py LABEL` -- the Navigator's tokens and cost into `missions.json` (last output line shown).
3. `scorecard.py --table LABEL` -- writes the card JSON and prints the table row (header + row).
4. `damage_mix.py --nick NICK --mission LABEL` -- refreshes `runs/pilot/NICK/damage_mix.json` at the mission's
   depth band (see damage_mix.py below) and the 4-day window; prints one confirmation line with the band.
5. Complaints: lines of `runs/complaints.md` stamped (`- YYYY-MM-DD HH:MM...`) at or after the mission's start in
   `missions.json` (2 hours back if the label isn't there).
6. Questions: `notes.py --nick NICK --questions --mission LABEL` (the `?` notes made during the mission), cut to
   the last 8 lines of the `QUESTION` blocks (each the `QUESTION` line and the 3 after it).
7. Status: the first 12 lines of `pilotctl status` and 4 of `pilotctl debt`.

After it, the Architect writes the mission report in `runs/pilot/NICK/reports/YYYY-MM-DD-missionNN.md` and the
lessons in `github/tools/pilot/FIELD-NOTES.md` (manual steps, not done by the script).

---

## scorecard.py -- one card per mission

Implements the Advisor's definitions (`memos/2026-10-23-scorecard.md`; the Advisor's reference implementation is
`Advisor/data/scorecard/scorecard.py`). Uses the Pilot's logs only.

```
python3 scorecard.py m48            # print one card (and write its JSON)
python3 scorecard.py --table m48    # the table row only (what wrap.sh uses)
python3 scorecard.py --all          # rescore every real mission (cards rewritten and printed, then the table; with --table only the table); sp-* only with --sp
python3 scorecard.py                # the table of the cards already written (read only, nothing rescored)
python3 scorecard.py --json m48     # the numbers as JSON
python3 scorecard.py --check m17 .. # ours vs the Advisor's baseline CSV (Advisor/data/scorecard/baseline_m17-m23.csv)
```

**Inputs.** The mission's row in `runs/missions.json` (`label, nick, start, end, navigator, effort, report, notes,
version, tokens`; written by `pilotctl mission start/end`, `tokens.py`, and the set-piece harness, which adds `sp-*`
missions; scored only when named, or with `--all --sp`). Every `decisions.jsonl` record with `start <= t <= end`
(minute resolution; a running mission ends now); `events.jsonl` `message` events in the window and `store` listings up to 60 s after it;
`testserver/gdb_run.log` for crashes; `src/server/tables.c` (`player_exp`), `lib/edit/object.txt` (kind costs) and
`shopmath`. **Output:** `runs/pilot/<nick>/scorecards/<label>.json` for every mission scored (named or `--all`), and
the printed card/table. With no labels and no `--all` it only reads the existing cards.

**The card** (JSON keys; the printed card shows the same groups):

Header: `label, nav_model, effort, report` (full/compact), `start, end, minutes, notes, tokens`.

A. Outcome (from the first and last `audit_check` records)
- `deaths`: `attention: dead` count. `clvl` [start, end]. `exp_gain`. `gold` [start, end] and `gold_change`,
  where gold = carried + `banked` (the house), so a deposit isn't a loss. `max_depth_ft`.

B. Efficiency
- `dungeon_min` / `town_min`: time between consecutive records by depth (gaps over 60 s skipped).
- `exp_per_dmin`: exp gained per dungeon minute. `levels_per_dhour`: exp gains between audits, each divided by the
  exp needed for the next level at that clvl (Half-Orc expfact 110), per dungeon hour.
- `gold_found` (and per dungeon minute): gold rises between audits while in the dungeon.
- `time_budget_min`: every second of the mission in exactly one category, from the current goal and recent
  events (`time_budget`). Dungeon: `escaping` (goal flee*, an emergency in the last 10 s, Phase in the last 5 s,
  or an urgent recall not yet landed, <40 s), `fighting` (a combat message in the last 5 s or goal hunt*),
  `resting`, `searching_doors`, `stuck_looping` (a goal other than rest/wait/recall and the same position for 20 s),
  `recall_wait`, `travel_dive`, `travel_goto`, `exploring`, `dungeon_other`, `no_goal_dungeon`. Town: `resting`,
  `town_shopping`, `town_farming`, `recall_wait`, `town_other`, `town_no_goal`, `town_idle_end` (no goal after the
  last goal). Plus `pilot_down` (a gap of more than 45 s between records).
- `navigator_wait_pct`: (`no_goal_dungeon` + `town_no_goal`) / mission time.

C. Safety
- `lowest_hp` [hp, max, %, time] (records with max HP >= 20 and HP > 0).
- `close_calls_lt40` / `near_calls_40_50`: episodes (separated by 60 s) with HP below 40% / 40-50%.
- `emergency_episodes` (emergency alerts more than 30 s apart) and `emergency_alerts`.
- From `act` records: `phase` (Phase Door reads), `wor_escape` vs `wor_travel` (a recall read in the dungeon is an
  escape if its reason matches low hp/flee/danger/emergency/..., an escalation alert came within 45 s, or HP < 50%),
  `teleport`, `stairs_flee` (stairs taken under a flee/recover goal), `cures_quaffed` (CLW/CSW/CCW/Healing).
- `escape_records` (`kind: escape` count), `recalls_landed` ("yanked" messages).

D. Value lost (`value_lost`, gold equivalents)
- `sale_shortfall`: per sale, fair pay minus received when short by more than 1 gold. Fair pay =
  `shopmath.fair_pay(relist price, owner, CHR)`, from the Pilot's `sale` records; for old missions without them,
  matched from "You sold X for N gold" messages to the next store listing within 8 s.
  `sale_shortfall_forced`: the part on sales the Navigator forced (`!`).
- `destroyed_est` ("You destroy X"), `loot_abandoned_est` (`left_behind` records, "left ..." tactics, or for old
  missions `interesting_item` alerts never picked up), `stolen` (coins + stolen items), `destroyed_by_monsters_est`:
  estimated as `object.txt` kind cost x count x 0.38 (the shop cut), 0 for cursed/broken junk. Marked `~` in print.
- `total`, `sales`, `sales_valued`, `worst_sales` (5), `left_behind` (10), `irreplaceable` (lost items matching Free
  Action, See Invisible, Telepathy, Hold Life, Speed, resistances, Regeneration...).

E. Navigator
- `reports` (`nav_cmd` with `wait_report`: each report handed to the Navigator), `commands`, `commands_per_min` (commands, i.e. without `wait_report` records, per mission minute: A24, 2.39.0; cards rescored 10-29).
- `report_to_action_med_s` / `_p90_s`: from a report to the first non-query command before the next report.
  `reports_without_command_pct`: reports followed by no command at all.
- `user_messages` (`!` notes) and `user_reply_med_s` (to the next `nav_say`, within 300 s).
- `forced_overrides` (args with `!` in their first two characters), `complaints`, `report_chars`, `order_report_age_med_s` / `_p90_s`
  (the `report_age` of non-query commands: how stale the report an order was based on).

F. Pilot health
- `audit_diffs` / `audit_checks` (state audit disagreements), `perception_gaps`, `goal_failed`, `stuck` (alert
  counts), `stuck_looping_min`, `runs_sent` (moves sent as runs), `pilot_down_min` (record gaps > 45 s),
  `server_crashes` (SIGSEGV lines in `gdb_run.log` in the window).

Also: `damage_by_monster` (top 8; each HP drop within 10 s shared among the monsters whose attack messages fall
in it), `alerts` (top 12 attention kinds, excluding the trip plan's `source: plan` news), `plan_news` (those),
and `estimator` (shadow mode: printed as group H): estimates `n`, `compared`, `agree` with the rules' emergency
decision, `in_time_turn`, `before_next_act`, `skipped` (emergencies while the estimator was busy),
`compute_max_s`, up to 8 `disagreements`, and the hard-fight-start estimates apart (`hard_n`, `hard_compared`,
`hard_agree`, `hard_choices`). The printed card's group G shows `tokens` (from `tokens.py`).

**The table** (`--table`, several cards, or no labels) has one row per mission: `mission nav min dmin lv/dh exp/dm $/dm low%
close near phase woresc cures lost forced$ r->a reply wait% est estHF usd usd/dh usd/kxp gold/usd` (the last four:
Navigator cost, per dungeon hour, per 1000 exp, and gold found per dollar).

---

## tokens.py -- the Navigator's cost per mission

```
python3 tokens.py m60                 # after `pilotctl mission end`
python3 tokens.py m60 --transcript F  # name the transcript yourself
python3 tokens.py --all               # every mNN mission with no tokens yet and a findable transcript
```

Finds the Navigator's Claude Code subagent transcript (`~/.claude/projects/*/*/subagents/*.jsonl`) modified after
the mission start minus 10 min whose first 20 KB contain "Mission NN for character" (or "for Dive04" in m17-m23,
or "for \*\*"); the newest wins. Sums usage per API turn (a turn's usage repeats on each content block; the largest
value per field is kept): `turns, input, output, cache_read, cache_write, write_5m, write_1h, model,
final_usage_turns`, `usd` at the list prices in `PRICES` (Opus/Sonnet 5.5 fetched 2026-10-25; Haiku 5.5 from the
claude-api skill's table, its cache prices derived), and `transcript` (the file name). If fewer than half the turns have
a final usage (transcripts up to m23), `output` is `None` and so is `usd`. Writes `tokens` (and `effort` if
missing) into `runs/missions.json`, re-reading the file first because the Pilot also writes it. Only the
Navigator's tokens: the Pilot is code and the Architect's tokens aren't counted. Gotcha: the Navigator's
brief must keep the "Mission NN for character" wording or the transcript isn't found.

---

## damage_mix.py -- where the damage comes from (for EHP)

`python3 damage_mix.py [--nick dive04] [--mission LABEL] [--lo 700] [--hi 800] [--days 4] [--out FILE]`

Finds HP drops in `decisions.jsonl` (consecutive records with `hp` and `depth`, same max HP, less than 5 s apart,
depth in LO-HI ft, in the last DAYS days) and splits each over the attack messages in `events.jsonl` around it
(0.6 s before to 0.2 s after). Melee blows are split by the attacker's blows in the rulebook: its share of
HURT/SHATTER blows goes to `hurt` (AC cuts it twice: hit chance and damage), the rest to `melee_other`. Breaths,
bolts, balls and traps go to their element (`fire, cold, acid, elec, pois, lite, dark, shard, nexus, sound, nether,
chaos, disen`); arrows, magic missiles and drops with no message (poison, cuts, unseen spells) to `other`.
Status-only spells (scare, confuse, blind) are ignored.

Writes `runs/pilot/<nick>/damage_mix.json`: `{"mix": {category: share}, "melee_level": damage-weighted mean level of
melee attackers, "hp_lost", "drops", "range", "since", "made"}`. The Pilot's gear evaluator reads it
(`geareval.load_mix`) for the effective-HP (EHP) column of `gearcmp` and `loadout`. Refreshed by `wrap.sh` after
every mission with `--mission LABEL`: the band is the 100 ft span of the depths that mission spent at least 10% of
its dungeon time at (750 -> 700-800, 800 -> 800-900, 700-850 -> 700-900; it prints `mNN: played A-B ft -> band
LO-HI ft` on stderr). `--lo`/`--hi` override; 700-800 ft without `--mission` or for a mission with no dungeon time.
`--out` writes elsewhere (for tests; the Pilot reads the run directory's file live).

---

## notes.py -- the user's notes with the play around them

`python3 notes.py [--nick dive04] [--since HH:MM | --today | --mission LABEL] [--before 20] [--after 5] [--questions]`

For each entry of `commentary.jsonl` (optionally only `?` questions; since a time today, or during a mission's
start-end in `missions.json` plus a minute) prints a header
(`QUESTION`, `TO NAVIGATOR` for `!`, `NAVIGATOR` for its `say`, or `note`), the snapshot (depth, position, HP,
clvl, goal, standing on, monsters), and the decision records from BEFORE seconds before to AFTER seconds after
(kinds `act, attention, goal, goal_done, goal_failed, audit, note, nav_journal, nav_say, nav_complaint`; later
ones marked `>>`). The Architect uses it to answer the user's `?` questions after a mission
(`--questions --today`).

---

## shopmath.py -- shop prices from the server source

A library (no command line). From `store.c price_item`: a shop prices an item at value x adjust / 100 with greed
G = the owner's `min_inflate` (`shop_own.txt`) + the racial factor (`cost_adj.txt`, owner race x player race) +
`adj_chr_gold[CHR]` (`tables.c`). Shop selling: `max(100, G - 200)`; shop buying: `min(100, 400 - G)`; the Black
Market (store index 6) asks x3 and pays /3.

| Name | What |
|---|---|
| `OWNERS`, `COST_ADJ`, `ADJ_CHR_GOLD`, `RACES` | the tables, parsed at import |
| `stat_index(v)` | a stat as the indicators give it (3..18, then 18 + tens) -> table index |
| `factors(owner, chr, race="Half-Orc")` | (buy adjust, sell adjust, store index); owner matched exactly or by prefix; None if unknown |
| `fair_pay(relist, owner, chr, race)` | what the shop should have paid for an item it re-lists at `relist` (relist x buy / sell, /9 at the Black Market) |

Importers: `pilot.py` (the shop cut used in item values, sale records' fair pay), `scorecard.py`,
`harness/unit.py` (a test), and the Advisor's `Advisor/data/rulebook/build_shops.py`, which imports it by the
absolute path `/projectnb/jbrcs/mangband/github/tools/observe` -- **don't move or rename it**. The Advisor checked
it against every identified sale: within 1 gold.

---

## latency.py -- Navigator response times (retired)

Moved to `tools/attic/` in session 10 (C2; see its README.md). From `decisions.jsonl` in a window: `alert ->
contact` (an urgent attention event, not `source: plan`, to the Navigator's next command within 600 s), `alert ->
order` (to its next non-query command within 120 s), `user -> reply` (a `user_message` to its next `say`), and the
command cadence; each as n, median, p90, max. Built for the Sonnet/Opus model trials (m21-m22); the scorecard's
group E now covers similar ground (report -> action, user reply).

---

## Human-play study tools (September 2026; in `observe/study/` since 2026-10-29)

Used once, on 2026-09-25, to record the user playing for study (`runs/observe/session1-3`; the Advisor's early
studies read those `pkt.jsonl` files). No script calls them.

- **`record.py`** `--host localhost --port N [--out DIR] [--nick NAME] [--interval 0.2] [--size 200x60]`: starts
  the normal interactive client (`mangclient -mgcu --pktlog`) in a private tmux server (`tmux -L mang`, session
  `play`), and polls the pane every 0.2 s. Writes, in a private (0700) `runs/observe/<stamp>/`: `pkt.jsonl` (every
  packet and key, from the client's `--pktlog`), `screens.jsonl` (`{t, size, rows}` whenever the screen changes,
  colours as ANSI escapes), `meta.json`, and a fresh `mangrc`. The player attaches with
  `tmux -L mang attach -t play`; recording stops when the client exits. Note the default `--port` is 18346, not
  the test server's 28346.
- **`timeline.py SESSION`**: merges a recorded session into one time-ordered log on the pktlog clock: `NOTE` (the
  player's chat as commentary), `KEYS` (bursts), `>>` (commands sent; walk/run directions decoded), `msg` (server
  messages), `==` (sidebar changes read from the screen: depth, HP, level, gold); repeats collapsed. Committed as an
  untested draft.
- **`screen.py SESSION MM:SS [...] [--cols 100] [--after]`**: prints the screen the player saw at that pktlog time
  (the last frame at or before it, or the first after).

## scribe.py -- a messenger character

`python3 study/scribe.py --to CHARNAME [--nick Scribe] [--port 28346] [--fifo runs/observe/scribe.fifo] &`, then
`echo "text" > runs/observe/scribe.fifo`. Logs in a town-bound character through the shopcat client
(`tools/shopcat/mang.py`, `newchar.py`; creates it if needed) and sends each line written to the FIFO as private
chat to `--to`, split to fit the 59-character chat line. Lets Claude answer the user in game while they play.
Local server only and only at the user's request (our characters otherwise never chat). Listed as the "Scribe"
role in `operations.md`; last used 2026-09-25.
