#!/bin/bash
# build.sh -- build Mangbot's MAngband: the server (mangband) and the tool client (mangclient).
#
# Fetches upstream MAngband at a pinned commit, checks it, applies patches/*.patch (one commit per patch, in a
# git tree of its own: build/mangband), configures and makes. Then links ./mangband, ./mangclient and ./lib at
# the top of this repo to the build tree (where the tools, the test server and source readers look), and ./src.
#
#   ./build.sh              build (fetch + patch on the first run; afterwards only `make`)
#   ./build.sh --fresh      delete build/mangband and start again from upstream + patches/
#   ./build.sh --export     write the build tree's commits since upstream back into patches/ (after C work)
#   ./build.sh --no-links   build, but leave the links (./mangband, ./mangclient, ./lib, ./src) alone
#
# Environment:
#   MANGBAND_TARBALL=PATH   use this local copy of the upstream tarball instead of downloading it
#   BUILD_DIR=PATH          build somewhere else (default: build/mangband next to this script)
#   NSLOTS=N                parallel make jobs (default 1)
#
# C work: edit and commit inside build/mangband (it's a normal git tree, upstream = its first commit, one commit
# per patch on top), rebuild with ./build.sh, then ./build.sh --export and commit patches/ here.
set -euo pipefail

# Upstream: MAngband 1.5.3 plus the 46 later commits on its master branch (2022-03-13). This is the tree the
# project ran since 2026-09-24 (the old repo's "Pristine MAngband 1.5.3 sources" commit, 6963c00).
UPSTREAM_COMMIT=c97e8738f81a3d1b6d8d1b8222064a99c7bc2473
UPSTREAM_TREE=c896f48de2a5f48157efa02ba88d326581dc8690     # git tree hash: checks the tarball's contents
UPSTREAM_URL=https://github.com/mangband/mangband/archive/$UPSTREAM_COMMIT.tar.gz
CONFIGURE_FLAGS=(--with-x11=no --with-sdl=no --with-sdl2=no --with-crb=no --with-gcu=yes)

HERE=$(cd "$(dirname "$0")" && pwd)
TREE=${BUILD_DIR:-$HERE/build/mangband}
STAMP=.mangbot-patches              # in $TREE: sha256 of patches/ as applied
GIT=(git -c user.name=build.sh -c user.email=build@localhost -c advice.detachedHead=false)

fresh=0 export=0 links=1
for a in "$@"; do
  case $a in
    --fresh) fresh=1 ;;
    --export) export=1 ;;
    --no-links) links=0 ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "build.sh: unknown option $a (see --help)" >&2; exit 2 ;;
  esac
done

say() { echo "build.sh: $*" >&2; }
patches_sum() { cat "$HERE"/patches/*.patch | sha256sum | cut -c1-64; }

if [ $export = 1 ]; then
  [ -d "$TREE/.git" ] || { say "no build tree at $TREE"; exit 1; }
  base=$(git -C "$TREE" rev-list --max-parents=0 HEAD)
  if [ -n "$(git -C "$TREE" status --porcelain --untracked-files=no)" ]; then
    say "uncommitted changes in $TREE: commit them first"; exit 1
  fi
  rm -f "$HERE"/patches/*.patch
  git -C "$TREE" format-patch -q --no-numbered --zero-commit --no-signature --full-index -o "$HERE/patches" "$base"..HEAD
  patches_sum > "$TREE/$STAMP"
  ls "$HERE"/patches/*.patch
  say "patches/ rewritten from $TREE; review with git diff, then commit"
  exit 0
fi

if [ $fresh = 1 ] && [ -d "$TREE" ]; then
  if [ -d "$TREE/.git" ] && [ -n "$(git -C "$TREE" status --porcelain --untracked-files=no)" ]; then
    say "uncommitted changes in $TREE: commit and --export them, or delete the tree yourself"; exit 1
  fi
  say "removing $TREE"
  rm -rf "$TREE"
fi

if [ ! -d "$TREE" ]; then
  mkdir -p "$(dirname "$TREE")"
  tmp=$(mktemp -d "$(dirname "$TREE")/.fetch.XXXXXX")
  trap 'rm -rf "$tmp"' EXIT
  tarball=${MANGBAND_TARBALL:-}
  if [ -z "$tarball" ]; then
    tarball=$(dirname "$TREE")/mangband-$UPSTREAM_COMMIT.tar.gz
    if [ ! -s "$tarball" ]; then
      say "downloading $UPSTREAM_URL"
      curl -fsSL -o "$tmp/up.tar.gz" "$UPSTREAM_URL"
      mv "$tmp/up.tar.gz" "$tarball"
    fi
  fi
  tar -xzf "$tarball" -C "$tmp"
  src=$(echo "$tmp"/mangband-*)
  [ -d "$src" ] || { say "unexpected tarball layout in $tarball"; exit 1; }
  # the tree hash covers every file's path, mode and contents
  (cd "$src" && git init -q && git add -f -A)
  got=$(git -C "$src" write-tree)
  if [ "$got" != "$UPSTREAM_TREE" ]; then
    say "upstream tree hash $got != $UPSTREAM_TREE: wrong or damaged tarball ($tarball)"; exit 1
  fi
  (cd "$src" && "${GIT[@]}" commit -q -m "Upstream MAngband $UPSTREAM_COMMIT (1.5.3 + master, 2022-03-13)" \
      --date=2022-03-13T14:22:08+03:00)
  say "applying $(ls "$HERE"/patches/*.patch | wc -l) patches"
  (cd "$src" && "${GIT[@]}" am -q --committer-date-is-author-date "$HERE"/patches/*.patch)
  mv "$src" "$TREE"
  patches_sum > "$TREE/$STAMP"
  rm -rf "$tmp"; trap - EXIT
elif [ "$(cat "$TREE/$STAMP" 2>/dev/null)" != "$(patches_sum)" ]; then
  say "patches/ differs from what $TREE was built with."
  say "  newer patches (e.g. after a pull): ./build.sh --fresh"
  say "  your own C commits in $TREE: ./build.sh --export, then commit patches/"
  exit 1
fi

cd "$TREE"
if [ ! -f Makefile ]; then
  say "configuring"
  # (not upstream autogen.sh: it downloads config.sub/config.guess from GNU.org, which can fail and leave them empty;
  # `autoreconf -i` copies them from the local automake. Not -f: that overwrites upstream's tracked INSTALL)
  autoreconf -i > autogen.log 2>&1 || { tail -20 autogen.log; exit 1; }
  ./configure "${CONFIGURE_FLAGS[@]}" > configure.log 2>&1 || { tail -20 configure.log; exit 1; }
fi
say "make (log: $TREE/make.log)"
make -j"${NSLOTS:-1}" > make.log 2>&1 || { grep -m20 -B2 -A5 'error' make.log; exit 1; }
[ -x mangband ] && [ -x mangclient ] || { say "make finished but a binary is missing"; exit 1; }

if [ $links = 1 ]; then
  rel=$(realpath --relative-to="$HERE" "$TREE")
  for f in mangband mangclient lib src; do
    if [ -e "$HERE/$f" ] && [ ! -L "$HERE/$f" ]; then
      say "$HERE/$f exists and is not a link: move it away first"; exit 1
    fi
    ln -sfn "$rel/$f" "$HERE/$f"
  done
  say "linked ./mangband ./mangclient ./lib ./src -> $rel"
fi
say "done: $(git log --oneline -1 | cut -c1-60)"
