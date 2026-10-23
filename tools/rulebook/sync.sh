#!/bin/bash
# sync.sh -- copy the Advisor's rulebook tables (Advisor/data/rulebook, which the Advisor owns and
# rebuilds from the server source) into the repo, so the Pilot runs against a versioned copy.
# Run after the Advisor announces a new release; then commit.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(cd "$HERE/../../.." && pwd)/Advisor/data/rulebook
cp -p "$SRC"/*.csv "$SRC"/README.md "$HERE/"
# the duel simulator (the Advisor's fight_sim.py, 2026-10-24) and what it imports, with the raw monster
# table it reads rows from (Advisor/data/monsters/monsters.csv, as monsters_raw.csv)
cp -p "$SRC"/fight_sim.py "$SRC"/build_monsters.py "$HERE/"
cp -p "$SRC"/../monsters/monsters.csv "$HERE/monsters_raw.csv"
date '+%Y-%m-%d %H:%M' > "$HERE/SYNCED"
echo "synced $(ls "$SRC"/*.csv | wc -l) tables from $SRC"
