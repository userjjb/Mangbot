# Refactor candidates: tool client and server changes

- **c-tool.c header comment is stale** (S): says `interactive TYPE` "e.g. 21 = the DM menu, '&'" but the DM menu is
  13 (SPECIAL_FILE_MASTER, `server/mdefines.h`; `tools/harness/dm.py` uses 13); the "(PKT_CLEAR, what ESC sends)"
  continuation sits under `floor` instead of `clear`; the event list omits `local_browser`, `target` and the reply
  events `flags`, `floor`, `options`, `minimap`. Fix the comment only.
- **`MangClient` lives in `tools/shopcat/mang.py`** but is the core dependency of the Pilot, harness and observe tools
  (`pilot.py` does `sys.path.insert(.., "shopcat")`). Move it to a shared module (e.g. `tools/client/`), leave a
  shim. Risk M (imports in several tools, unit tests).
- **Default port 18346 (the live port) on localhost** in `pilot.py: main` and `MangClient.__init__`, while the test
  server is 28346 and `restart.sh`/`hotswap.sh` pass 28346. Make the default 28346 (or require `--port`). Risk S.
- **`tool_do_command` is a ~330-line if/else chain** (c-tool.c). A verb table (name, handler, usage) would shorten it
  and generate the help. Risk M (C, rebuild, every tool depends on it); low value, only if touching it anyway.
- **Verbs no Python tool sends:** `alter`, `suicide`, `minimap`, `special` (query), `commands` (grep of tools/ for
  `send("verb`/`query("verb`). Keep (manual use via `pilotctl raw`, documented) but don't grow more one-off verbs;
  `eat ITEM` duplicates `custom E item=ITEM` (3 uses).
- **operations.md "depth indicator is one signed byte"** is stale for the test server (tables.c sends 16 bits since
  the game-state survey); true only on live. Risk S (doc).
- **`testserver/` clutter:** `mangband.prefreeze` (an Oct 17 binary from before the freeze), `crash1..4`, `gdb.log`,
  `watch.log`. Archive or delete on the user's say-so. Risk S.
- **`github/project/tree/testserver/data/Makefile.am`** shows up in `git diff 6963c00 HEAD -- '*.am'`: a snapshot copy
  of a build file inside the test server's data dir. Harmless, but snapshot.sh could skip it. Risk S.
