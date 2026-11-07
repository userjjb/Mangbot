#!/bin/bash
# hotswap.sh NICK -- load new Pilot code mid-mission, on the test server, without the world moving (2026-10-25).
# Freeze time (tools/freeze.sh), stop the running Pilot at once (no park: a frozen Pilot never reaches its safe
# moment), start the new one, wait for it to log in, thaw. The character stays in the world meanwhile: an orphan
# is freed only after 15 s idle, and that idle timer runs in the game tick, which is stopped (operations.md,
# Orphans), so the new Pilot resumes it in memory, where it was. The trip plan resumes from plan.json; the
# Pilot's own memory (the level map it built, refused stairs, fights) starts over, as in any restart.
# Tested in the dungeon by set-pieces H1 (mid-trip) and H1r (with a recall pending), both passed 2026-10-25 (~4 s swap).
set -u
# (2.59.0, the user after m66: never during a town or house visit -- hotswap.sh hit plan town mid house visit, the
# bank's 28k in the purse. Wait until `pilotctl swapsafe` says safe, up to SWAP_WAIT_S (default 900); --now skips)
NOW=0; ARGS=()
for a in "$@"; do [ "$a" = "--now" ] && NOW=1 || ARGS+=("$a"); done
set -- "${ARGS[@]}"
HERE=$(cd "$(dirname "$0")" && pwd)
source "$HERE/../servers.sh" || exit 1     # $MANGBOT_SERVER: test (default) or sp, the set-piece server
NICK=${1:?usage: hotswap.sh NICK [PORT] [--now]}; PORT=${2:-$MB_PORT}; RUNS=$MB_RUNS
LOW=$(echo "$NICK" | tr A-Z a-z)
FREEZE="$HERE/../freeze.sh"
module load python3/3.12.4 2>/dev/null
cd "$HERE"
swap_wait() {
    [ "$NOW" = 1 ] && return 0
    local t0=$(date +%s) last=""
    while :; do
        local out
        out=$(python3 pilotctl.py --nick "$LOW" swapsafe 2>&1 | grep -v "^USER MESSAGE\|^ALERTS:\|^ARCHITECT ANSWER" | head -1)
        case "$out" in safe|"(Pilot not answering"*|"which Pilot"*) return 0 ;; esac
        [ "$out" != "$last" ] && echo "$(date +%T) $out" && last="$out"
        [ $(( $(date +%s) - t0 )) -ge "${SWAP_WAIT_S:-900}" ] && { echo "still $out after ${SWAP_WAIT_S:-900} s: rerun with --now to go ahead"; exit 1; }
        sleep 3
    done
}
swap_wait
was=$("$FREEZE" status)
"$FREEZE" on >/dev/null; echo "$(date +%T) frozen"; sleep 1
PID=$(pgrep -f "^python3 pilot.py --nick $NICK --port $PORT( |$)")
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
