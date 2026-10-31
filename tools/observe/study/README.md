# observe/study

Tools for studying human play, kept for the user's future recording sessions (moved here from `observe/` on
2026-10-29, refactor-candidates C3). Details: `docs/observe.md`, "Human-play study tools".

- `record.py`: run the normal client in a private tmux session and record the packets and screens of a human's play
  (`runs/observe/<stamp>/`). Its `--port` defaults to 28346, the test server (since 2.43.0); pass `--port 18346` for the live server.
- `timeline.py`, `screen.py`: read a recorded session (a time-ordered log; the screen at a given moment).
- `scribe.py`: a messenger character that relays the Architect's text to the user in game (at the user's request only).
