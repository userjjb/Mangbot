# Live deployment: to do

What must be done or checked before the Pilot plays on the live server (mangband.org:18346, a shared world with real
players). Started 2026-10-29 at the user's request. Add items as they come up; mark them done with the date and
version. Background: operations.md ("Live server", "Live-server rules a bot must follow"), docs/client-server.md
("Test server vs live server").

## Before the first live run
- [ ] **Ask the admins.** The current rules and server version are unknown (the News ends in 2020). Ask before any
  live run (operations.md).
- [ ] **The live character.** Sneezy is planned but not created yet; it starts from nothing (no Dive04 gear, no test
  gold). Use the user's throwaway build (operations.md "User decisions"). Its password goes in `runs/private/`.
- [ ] **Check the Pilot keeps the live rules:** recall to town before logging out (no saving in the dungeon); never
  idle inside a store; destroy junk in town, don't drop it; never pass items between our own characters; no
  power-levelling; never chat (`say` goes to the viewer, not the game: check nothing else reaches game chat).
- [ ] **Run with `--live`** (`PILOT_ARGS="--live"`): it keeps mapping/detection devices and holds off the stairs back
  to a fled level.
- [ ] **Port defaults (refactor-candidates F1).** `pilot.py` and `MangClient` default to 18346, the live port. Decide
  whether to default to the test port or require `--port` before both servers are in use. `observe/study/record.py`
  defaults to the live port too.
- [ ] **No test-server tools on live:** no time freeze, so `hotswap.sh` can't be used (use `restart.sh`, which parks
  first, and only at a safe moment); no DM, no set-pieces, no `charsave.sh` restores. A death is permanent.
- [ ] **What the live server lacks:** our server patches (store guards, the 16-bit depth indicator). The client-side
  store fix protects us; far-wilderness depth wraps on live (use `minimap`). Check every Pilot path that reads
  `depth` in the wilderness.
- [ ] **The gold bank needs a house.** The test server's bank is a wilderness house bought there; on live, houses can
  be owned by players and cost differently (operations.md "Live server": the price formulas from the 09-25 tour). Find
  and buy one, or run without the bank (the tavern fallback).
- [ ] **Network latency.** The Pilot's timings were tuned against a local server (~0.5 s per walk step, command
  holds of 0.3-0.6 s). Measure the round trip to mangband.org and check the reflexes still act in time.
- [ ] **The time bubble.** `--hpwarn 5` makes the server slow our time to 1/5 below 50% HP. Check it behaves the
  same on live.
- [ ] **Pin the Advisor's simulator.** Shadow mode and the gear evaluator (`gearcmp`, `loadout`, automatic swaps) import
  `Advisor/data/estimator/options_sim.py` live, so a change there changes the Pilot's gear decisions mid-run. Pin or
  snapshot it (a copy, or a version check) for live runs (the session-10 review).
- [ ] **The rulebook vs the live version.** The rulebook is built from the 1.5.3 source; the live server may be
  patched. Spot-check monsters, items and prices against what live play shows (the Advisor's versions memo).

## After deploying
- [ ] **Update the live shop catalog** (the user, 2026-10-29). The shop-tour tool (`tools/shopcat/shopcat.py`,
  `nav.py`, `wild.py`, `report.py`, `runs/regress.py`) last ran on 2026-09-25 and the client has changed a lot since:
  repair it (test it on the test server with Surveyor first), then tour live with Happy (no purchases) and refresh
  `runs/live-tour*.jsonl/csv`.
