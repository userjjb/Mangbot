#!/bin/bash
# Rebuild every generated rulebook table (copied tables come from finished studies and change only with them).
set -e; cd "$(dirname "$0")"
module load python3/3.12.4 2>/dev/null || true    # Python 3.12 (3.6 gives different Monte Carlo draws)
python3 build_jewellery.py 4000 && python3 build_kinds.py && python3 build_feelings.py 3000 && python3 build_monsters.py && python3 build_shops.py && python3 build_drops.py 400
