#!/bin/bash
# charsave.sh save|restore NICK TAG -- snapshot a character for a set-piece, and put it back after.
# (restructure step 4: set-pieces hurt the character on purpose; Dive04 keeps nothing from them)
# The Pilot is parked (it logs out at a safe moment, and the server writes the savefile), then
# the savefile and the Pilot's own state (orders, deepest, plan, standing, debt, keep, stores)
# are copied to runs/setpieces/saves/TAG/ (save) or back (restore), and the Pilot is started.
set -u
OP=${1:?usage: charsave.sh save|restore NICK TAG [PORT]}; NICK=${2:?}; TAG=${3:?}; PORT=${4:-28346}
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../../.." && pwd)
LOW=$(echo "$NICK" | tr A-Z a-z)
SAVE=$ROOT/testserver/save/$NICK; RUN=$ROOT/runs/pilot/$LOW; DEST=$ROOT/runs/setpieces/saves/$TAG
STATE="orders.json deepest.json plan.json standing.json navigator_debt.json keep.json stores.json"
module load python3/3.12.4 2>/dev/null
cd "$HERE/../pilot"
T0=$(date +%s)
if pgrep -f "^python3 pilot.py --nick $NICK" >/dev/null; then
    python3 pilotctl.py --nick "$LOW" park >/dev/null || true
    for i in $(seq 1 330); do pgrep -f "^python3 pilot.py --nick $NICK" >/dev/null || break; sleep 1; done
    pgrep -f "^python3 pilot.py --nick $NICK" >/dev/null && { echo "pilot still running"; exit 1; }
fi
# A dropped connection leaves the character in the world (orphaned) until it has been idle 15 s
# (at once in town: net-server.c player_drop, the idle timer in dungeon.c), and only then is it
# removed and saved (player_leave); a login before that RESUMES the character in memory and
# ignores the savefile. The savefile's time proves nothing (the server also saves every player,
# orphans too, every few minutes). So: 20 s after the logout, then a save must have happened.
sleep 20
if [ "$(stat -c %Y "$SAVE")" -lt "$T0" ]; then
    echo "the server hasn't saved $NICK since the logout (still in the world?): not touching the savefile"
    nohup python3 pilot.py --nick "$NICK" --port "$PORT" >> "$ROOT/runs/pilot/$LOW/pilot.log" 2>&1 &
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
nohup python3 pilot.py --nick "$NICK" --port "$PORT" >> "$ROOT/runs/pilot/$LOW/pilot.log" 2>&1 &
sleep 9
python3 pilotctl.py --nick "$LOW" status | head -2
