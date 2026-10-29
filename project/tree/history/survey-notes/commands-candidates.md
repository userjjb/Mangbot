# Refactor candidates: pilotctl / the command dispatcher

- **Dead second `plan` branch in `Pilot.do_request`** (the debug "path from here to Y,X" via `mover.plan`): the
  earlier `if c == "plan": return self.request_plan(args)` always returns first, so it can never run. Remove it, or
  rename it (`path`) if the debug is wanted. Risk S.
- **`do_request` is ~620 lines of `if c == ...`**: split into a command table (`{"keep": self.cmd_keep, ...}`) with
  per-command methods and a role/where policy declared per entry (town-only, architect-only, positional for the
  stale check). The role checks are now spread over the top of `do_request`, `request_goal`, `house_info`,
  `answer_navigator`, `Shop.tick`, and the `wear` branch. Risk M (many small moves; easy to test by replaying
  commands against the set-piece harness).
- **The item-action branch (`if c in self.ACTIONS`) is ~150 lines** mixing name parsing, fuel's lantern dance, four
  safety refusals, value/debt logic and reply building: extract `parse_item_args`, `action_refusal`, `action_reply`.
  Risk M.
- **Stale names in lists:** the dead-character whitelist (`events`, `news`, `inventory`), `tools/observe/watch.py`
  NAV_QUERIES (`flags`, `commands`, `inventory`, `events`, `news`), `latency.py` and `scorecard.py` lists (`help`,
  `floor`, `quote`, `dump`...) name commands that don't exist. One shared constant (e.g. `QUERY_CMDS` in pilot.py,
  imported by the observers) would keep them true. Risk S.
- **pilotctl.py's docstring** (its help) is out of date: advertises `goal goto`/`stairs` (refused to the Navigator),
  lacks ~15 commands. Generate it from the command table, or cut it to a pointer to docs/commands.md. Risk S.
- **Notes printed twice:** pilotctl prints `note` inside `DONE: ... -- note` and again as `NOTE:`, and goal replies
  print the JSON (with the note) and then `NOTE:`. Print goal replies as text (`GOAL: ...`) and the note once.
  Risk S (the Navigator's HANDBOOK quotes no exact format).
- **Role is an unauthenticated env var** (`PILOT_ROLE`): any caller can claim `architect` and skip hunt checks and
  debt. Acceptable on a single-user setup, but worth a sentence in the Navigator agent file ("never set PILOT_ROLE")
  or a check (socket peer / a token file the Navigator can't read). Risk S.
- **`mission` has no role check** though it is the Architect's; add one if Navigators ever call it. Risk S.
- **`order` value parsing:** `type(cur)(v)` raises on a bad float/int and the error surfaces as a bare
  `ValueError(...)` repr; `order KEY` without `=` likewise. A friendly usage error would help the Navigator. Risk S.
- **HANDBOOK-reference.md** still instructs `goal goto`/`stairs` in ~5 places and lacks 4 orders (`autowear`,
  `enchant_max`, `band_frac`, `nopickup`): prune or regenerate those rows. Risk S (doc only).
