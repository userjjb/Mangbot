#!/bin/bash
# Rebuild every generated rulebook table (copied tables come from finished studies and change only with them).
set -e; cd "$(dirname "$0")"
python3 build_kinds.py && python3 build_feelings.py 3000 && python3 build_monsters.py && python3 build_shops.py
