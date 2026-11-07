#!/bin/bash
# restart.sh NICK -- update the Pilot safely (Pilot options in PILOT_ARGS, e.g. PILOT_ARGS="--hpwarn 0" for no time bubble; the default is 5): park (log out at a safe moment),
# wait for the old Pilot to exit, start the new one (logs back in).
set -u
# (2.59.0, the user after m66: never during a town or house visit -- hotswap.sh hit plan town mid house visit, the
# bank's 28k in the purse. Wait until `pilotctl swapsafe` says safe, up to SWAP_WAIT_S (default 900); --now skips)
NOW=0; ARGS=()
for a in "$@"; do [ "$a" = "--now" ] && NOW=1 || ARGS+=("$a"); done
set -- "${ARGS[@]}"
HERE=$(cd "$(dirname "$0")" && pwd)
source "$HERE/../servers.sh" || exit 1     # $MANGBOT_SERVER: test (default) or sp, the set-piece server
NICK=${1:?usage: restart.sh NICK [PORT] [--now]}; PORT=${2:-$MB_PORT}; RUNS=$MB_RUNS
ARCH_TOKEN=$RUNS/private/architect.token      # park is the Architect's (2.45.0)
LOW=$(echo "$NICK" | tr A-Z a-z)
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
if pgrep -f "^python3 pilot.py --nick $NICK --port $PORT( |$)" >/dev/null; then
    swap_wait
    PILOT_ROLE=architect PILOT_TOKEN=$(cat "$ARCH_TOKEN" 2>/dev/null) python3 pilotctl.py --nick "$LOW" park \
        $([ "$NOW" = 1 ] && echo now) || true
    for i in $(seq 1 330); do pgrep -f "^python3 pilot.py --nick $NICK --port $PORT( |$)" >/dev/null || break; sleep 1; done
    pgrep -f "^python3 pilot.py --nick $NICK --port $PORT( |$)" >/dev/null && { echo "old pilot still running"; exit 1; }
fi
nohup python3 pilot.py --nick "$NICK" --port "$PORT" ${PILOT_ARGS:-} >> "$RUNS/pilot/$LOW/pilot.log" 2>&1 &
sleep 9
python3 pilotctl.py --nick "$LOW" status | head -3
