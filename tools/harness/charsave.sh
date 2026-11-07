#!/bin/bash
# charsave.sh save|restore NICK TAG -- snapshot a character for a set-piece, and put it back after.
# (restructure step 4: set-pieces hurt the character on purpose; Dive04 keeps nothing from them)
# The Pilot is parked (it logs out at a safe moment, and the server writes the savefile), then
# the savefile and the Pilot's own state (orders, deepest, plan, standing, debt, keep, stores)
# are copied to runs/setpieces/saves/TAG/ (save) or back (restore), and the Pilot is started. MANGBOT_SERVER=sp:
# spserver/save and runs/sp/ instead (tools/servers.sh).
set -u
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../../.." && pwd)
source "$HERE/../servers.sh" || exit 1     # $MANGBOT_SERVER: test (default) or sp, the set-piece server
OP=${1:?usage: charsave.sh save|restore NICK TAG [PORT]}; NICK=${2:?}; TAG=${3:?}; PORT=${4:-$MB_PORT}
RUNS=$MB_RUNS
ARCH_TOKEN=$ROOT/runs/private/architect.token   # park is the Architect's (2.45.0)
LOW=$(echo "$NICK" | tr A-Z a-z)
SAVE=$MB_SAVE/$NICK; RUN=$RUNS/pilot/$LOW; DEST=$RUNS/setpieces/saves/$TAG
STATE="orders.json deepest.json plan.json standing.json navigator_debt.json keep.json stores.json uniques_killed.json rates.json recall.json"
module load python3/3.12.4 2>/dev/null
cd "$HERE/../pilot"
T0=$(date +%s)
if pgrep -f "^python3 pilot.py --nick $NICK --port $PORT( |$)" >/dev/null; then
    PILOT_ROLE=architect PILOT_TOKEN=$(cat "$ARCH_TOKEN" 2>/dev/null) python3 pilotctl.py --nick "$LOW" park >/dev/null || true
    for i in $(seq 1 330); do pgrep -f "^python3 pilot.py --nick $NICK --port $PORT( |$)" >/dev/null || break; sleep 1; done
    pgrep -f "^python3 pilot.py --nick $NICK --port $PORT( |$)" >/dev/null && { echo "pilot still running"; exit 1; }
fi
# A dropped connection leaves the character in the world (orphaned) until it has been idle 15 s
# (at once in town: net-server.c player_drop, the idle timer in dungeon.c), and only then is it
# removed and saved (player_leave); a login before that RESUMES the character in memory and
# ignores the savefile. The savefile's time proves nothing (the server also saves every player,
# orphans too, every few minutes). So: 20 s after the logout, then a save must have happened.
sleep 20
if [ "$(stat -c %Y "$SAVE")" -lt "$T0" ]; then
    echo "the server hasn't saved $NICK since the logout (still in the world?): not touching the savefile"
    nohup python3 pilot.py --nick "$NICK" --port "$PORT" ${PILOT_ARGS:-} >> "$RUNS/pilot/$LOW/pilot.log" 2>&1 &
    exit 1
fi
sleep 1
case $OP in
save)
    mkdir -p "$DEST"
    cp -p "$SAVE" "$DEST/$NICK"
    for f in $STATE; do [ -f "$RUN/$f" ] && cp -p "$RUN/$f" "$DEST/$f"; done
    echo "saved $NICK to $DEST" ;;
restore)
    [ -f "$DEST/$NICK" ] || { echo "no snapshot $DEST/$NICK"; exit 1; }
    cp -p "$DEST/$NICK" "$SAVE"
    for f in $STATE; do
        if [ -f "$DEST/$f" ]; then cp -p "$DEST/$f" "$RUN/$f"; else rm -f "$RUN/$f"; fi
    done
    echo "restored $NICK from $DEST" ;;
*) echo "save or restore"; exit 1 ;;
esac
nohup python3 pilot.py --nick "$NICK" --port "$PORT" ${PILOT_ARGS:-} >> "$RUNS/pilot/$LOW/pilot.log" 2>&1 &
sleep 9
python3 pilotctl.py --nick "$LOW" status | head -2
