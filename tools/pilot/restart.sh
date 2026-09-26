#!/bin/bash
# restart.sh NICK -- update the Pilot safely: park (log out at a safe moment),
# wait for the old Pilot to exit, start the new one (logs back in).
set -u
NICK=${1:?usage: restart.sh NICK [PORT]}; PORT=${2:-28346}
HERE=$(cd "$(dirname "$0")" && pwd); RUNS=$(cd "$HERE/../../.." && pwd)/runs
LOW=$(echo "$NICK" | tr A-Z a-z)
module load python3/3.12.4 2>/dev/null
cd "$HERE"
if pgrep -f "^python3 pilot.py --nick $NICK" >/dev/null; then
    python3 pilotctl.py --nick "$LOW" park || true
    for i in $(seq 1 330); do pgrep -f "^python3 pilot.py --nick $NICK" >/dev/null || break; sleep 1; done
    pgrep -f "^python3 pilot.py --nick $NICK" >/dev/null && { echo "old pilot still running"; exit 1; }
fi
nohup python3 pilot.py --nick "$NICK" --port "$PORT" >> "$RUNS/pilot/$LOW/pilot.log" 2>&1 &
sleep 9
python3 pilotctl.py --nick "$LOW" status | head -3
