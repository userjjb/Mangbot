#!/bin/bash
# sync.sh -- copy the Advisor's rulebook tables (Advisor/data/rulebook, which the Advisor owns and
# rebuilds from the server source) into the repo, so the Pilot runs against a versioned copy.
# Run after the Advisor announces a new release; then commit.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$(cd "$HERE/../../.." && pwd)/Advisor/data/rulebook
cp -p "$SRC"/*.csv "$SRC"/README.md "$HERE/"
date '+%Y-%m-%d %H:%M' > "$HERE/SYNCED"
echo "synced $(ls "$SRC"/*.csv | wc -l) tables from $SRC"
