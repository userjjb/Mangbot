# The repo is a patcher (2.72.1, 2026-11-07, session 13) -- what changes for you

From the Architect. Nothing to do unless you read the MAngband source or its git history.

- `github/` now holds only our work: `README.md`, `build.sh`, `patches/` (5 topic patches against upstream), `tools/`,
  `project/`, `VERSION`. The MAngband tree is built by `github/build.sh` in `github/build/mangband/`.
- **Every path you use still works:** `github/src`, `github/lib`, `github/mangband`, `github/mangclient` are links into
  the build tree (so `github/src/server/*.c` and `github/lib/edit/*.txt` read exactly as before; the files are
  byte-identical, and the binaries have the same machine code). `github/mangband.cfg` (upstream's sample config) is gone
  from the top: it's `github/build/mangband/mangband.cfg`. The test server's own config is unchanged
  (`testserver/mangband.cfg`).
- **git log / blame of the C source:** `git -C github/build/mangband log -- src/...` (that tree's first commit is
  upstream c97e873 -- the same tree as before, upstream develop at 2022-03-13 -- and one commit per patch on top).
  The old per-change history (26 C commits, 09-24 to 10-31) stays in `github/`'s history before v2.72.1
  (`git -C github log fb5dee2^ -- src/client/c-tool.c`).
- Our C changes, one patch each: `patches/0001` packet logger, `0002` tool client, `0003` time freeze, `0004` store
  crash fix, `0005` 16-bit depth indicator. Docs: `docs/client-server.md` "Building".
- Next in this session: a separate local test server (own port, saves, copies of Dive04) for set-pieces, built with
  build.sh; then A25's unique-above-level set-piece on it.
