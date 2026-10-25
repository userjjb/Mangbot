#!/bin/bash
# hotswap.sh NICK -- load new Pilot code mid-mission, on the test server, without the world moving (2026-10-25).
# Freeze time (tools/freeze.sh), stop the running Pilot at once (no park: a frozen Pilot never reaches its safe
# moment), start the new one, wait for it to log in, thaw. The character stays in the world meanwhile: an orphan
# is freed only after 15 s idle, and that idle timer runs in the game tick, which is stopped (operations.md,
# Orphans), so the new Pilot resumes it in memory, where it was. The trip plan resumes from plan.json; the
# Pilot's own memory (the level map it built, refused stairs, fights) starts over, as in any restart.
# Untested in the dungeon yet: see next_steps.md.
set -u
NICK=${1:?usage: hotswap.sh NICK [PORT]}; PORT=${2:-28346}
HERE=$(cd "$(dirname "$0")" && pwd); RUNS=$(cd "$HERE/../../.." && pwd)/runs
LOW=$(echo "$NICK" | tr A-Z a-z)
FREEZE="$HERE/../freeze.sh"
module load python3/3.12.4 2>/dev/null
cd "$HERE"
was=$("$FREEZE" status)
"$FREEZE" on >/dev/null; echo "$(date +%T) frozen"; sleep 1
PID=$(pgrep -f "^python3 pilot.py --nick $NICK")
if [ -n "$PID" ]; then
    kill -TERM $PID
    for i in $(seq 1 20); do kill -0 $PID 2>/dev/null || break; sleep 0.5; done
    kill -0 $PID 2>/dev/null && { kill -KILL $PID; echo "$(date +%T) old Pilot killed"; } || echo "$(date +%T) old Pilot stopped"
fi
nohup python3 pilot.py --nick "$NICK" --port "$PORT" ${PILOT_ARGS:-} >> "$RUNS/pilot/$LOW/pilot.log" 2>&1 &
for i in $(seq 1 60); do
    python3 pilotctl.py --nick "$LOW" status 2>/dev/null | head -1 | grep -q " L[0-9]" && break; sleep 1
done
echo "$(date +%T) new Pilot answering: $(python3 pilotctl.py --nick "$LOW" status 2>&1 | head -1)"
case "$was" in FROZEN*) echo "time was frozen before: left frozen" ;; *) "$FREEZE" off >/dev/null; echo "$(date +%T) thawed" ;; esac
