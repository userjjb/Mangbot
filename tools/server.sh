#!/bin/bash
# server.sh start|stop|status|clone -- run a local MAngband server (session 13, 2026-11-07).
# Which server: $MANGBOT_SERVER (test = testserver/, port 28346, the default; sp = spserver/, port 28350, the
# set-piece server: tools/servers.sh).
#
#   server.sh status            running? (pid, binary, port, players' savefiles, freeze)
#   server.sh start             start it from its directory, under gdb (a crash leaves a backtrace in gdb_run.log),
#                               with MANGBAND_FREEZE_FILE=<dir>/FREEZE (tools/freeze.sh) and gdb passing SIGTERM on,
#                               so `stop` is a clean save (files.c handle_signal_simple -> shutdown_server)
#   server.sh stop [--now]      park the profile's Pilots first (restart.sh's way; a Pilot left connected would see
#                               the server vanish), then SIGTERM. A server started before 2.72.2 (plain gdb: gdb
#                               catches the SIGTERM and kills the server unsaved) is stopped only after its next
#                               autosave, unless --now
#   MANGBOT_SERVER=sp server.sh clone [NICK...]
#                               the set-piece server becomes a copy of the test world: testserver/save -> spserver/save
#                               (every savefile, the houses, the levels; Gandalf too), and each NICK's Pilot state
#                               (default Dive04) runs/pilot/<nick> -> runs/sp/pilot/<nick> (state files only, no logs),
#                               plus runs/flavours.json. The sp server must be stopped. The copy is as of the test
#                               server's last save of each file (a character online there: its last autosave)
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
source "$HERE/servers.sh" || exit 1
BIN=$MB_ROOT/github/mangband
CMD=${1:-status}; shift || true

server_pid() {    # the mangband process whose cwd is this profile's directory
    local p
    for p in $(pgrep -x mangband); do
        [ "$(readlink -f /proc/$p/cwd 2>/dev/null)" = "$(readlink -f "$MB_DIR")" ] && { echo "$p"; return 0; }
    done
    return 1
}

case $CMD in
status)
    if pid=$(server_pid); then
        echo "$MB_SERVER server running: pid $pid, port $MB_PORT, binary $(readlink -f /proc/$pid/exe), dir $MB_DIR"
    else
        echo "$MB_SERVER server not running (port $MB_PORT, dir $MB_DIR)"
    fi
    "$HERE/freeze.sh" status
    ls -lt --time-style=+%m-%d_%H:%M "$MB_SAVE" 2>/dev/null | awk 'NR>1 && NR<=6 {print "  save:", $6, $7}'
    ;;
start)
    pid=$(server_pid) && { echo "already running (pid $pid)"; exit 0; }
    [ -f "$MB_DIR/mangband.cfg" ] || { echo "no $MB_DIR/mangband.cfg"; exit 1; }
    [ -x "$BIN" ] || { echo "no server binary at $BIN: run github/build.sh"; exit 1; }
    cd "$MB_DIR"    # (the -c flag is broken, init2.c:2362: the server reads mangband.cfg from its cwd)
    MANGBAND_FREEZE_FILE=$MB_FREEZE nohup gdb -batch -ex "handle SIGTERM nostop noprint pass" -ex run -ex bt \
        --args "$BIN" >> gdb_run.log 2>&1 &
    for i in $(seq 1 30); do grep -q "Server is running" <(tail -5 gdb_run.log) && break; sleep 1; done
    pid=$(server_pid) || { echo "did not start: see $MB_DIR/gdb_run.log"; tail -5 gdb_run.log; exit 1; }
    echo "$MB_SERVER server started: pid $pid, port $MB_PORT"
    ;;
stop)
    NOW=0; [ "${1:-}" = "--now" ] && NOW=1
    pid=$(server_pid) || { echo "$MB_SERVER server not running"; exit 0; }
    # park this server's Pilots (pilot.py ... --port PORT)
    for nick in $(pgrep -af "^python3 pilot.py --nick [^ ]+ --port $MB_PORT( |$)" | awk '{print $5}'); do
        echo "parking $nick's Pilot"
        (cd "$HERE/pilot" && PILOT_ROLE=architect PILOT_TOKEN=$(cat "$MB_ROOT/runs/private/architect.token") \
            python3 pilotctl.py --nick "$(echo "$nick" | tr A-Z a-z)" park >/dev/null 2>&1)
        for i in $(seq 1 330); do pgrep -f "^python3 pilot.py --nick $nick --port $MB_PORT( |$)" >/dev/null || break; sleep 1; done
    done
    if ! tr '\0' ' ' < /proc/$(ps -o ppid= -p "$pid" | tr -d ' ')/cmdline | grep -q "handle SIGTERM"; then
        # gdb without the SIGTERM pass: the stop kills the server unsaved; wait for an autosave newer than now
        if [ $NOW = 0 ]; then
            echo "an old-style gdb (no SIGTERM pass): waiting for the next autosave (up to 11 min; --now skips)"
            touch "$MB_DIR/.stop-mark"
            for i in $(seq 1 660); do [ "$MB_SAVE/server" -nt "$MB_DIR/.stop-mark" ] && break; sleep 1; done
            rm -f "$MB_DIR/.stop-mark"
        fi
    fi
    kill -TERM "$pid"
    for i in $(seq 1 30); do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
    kill -0 "$pid" 2>/dev/null && { echo "still running after 30 s (pid $pid)"; exit 1; }
    echo "$MB_SERVER server stopped"; tail -3 "$MB_DIR/gdb_run.log" | grep -v "^\["
    ;;
clone)
    [ "$MB_SERVER" = sp ] || { echo "clone makes the set-piece server a copy: run it as MANGBOT_SERVER=sp server.sh clone"; exit 1; }
    pid=$(server_pid) && { echo "the sp server is running (pid $pid): MANGBOT_SERVER=sp tools/server.sh stop first"; exit 1; }
    SRC=$MB_ROOT/testserver
    [ $# -gt 0 ] || set -- Dive04
    mkdir -p "$MB_DIR/save" "$MB_DIR/data" "$MB_DIR/bone" "$MB_RUNS/pilot"
    rsync -a --delete "$SRC/save/" "$MB_DIR/save/"
    rsync -a "$SRC/data/" "$MB_DIR/data/"
    [ -e "$MB_RUNS/private" ] || ln -s ../private "$MB_RUNS/private"
    cp -p "$MB_ROOT/runs/flavours.json" "$MB_RUNS/flavours.json" 2>/dev/null
    for nick in "$@"; do
        low=$(echo "$nick" | tr A-Z a-z)
        [ -f "$MB_DIR/save/$nick" ] || echo "warning: no savefile for $nick in $SRC/save"
        mkdir -p "$MB_RUNS/pilot/$low"
        # the state files (json), not the logs (decisions/events/state.jsonl, pilot.log) nor the socket
        rsync -a --delete --include='*.json' --include='visuals.txt' --exclude='*' \
            "$MB_ROOT/runs/pilot/$low/" "$MB_RUNS/pilot/$low/"
        echo "cloned $nick: savefile $(date -r "$MB_DIR/save/$nick" +%m-%d_%H:%M:%S 2>/dev/null), Pilot state $(ls "$MB_RUNS/pilot/$low" | wc -l) files"
    done
    echo "the sp world is a copy of the test world as of its last saves (server file $(date -r "$MB_DIR/save/server" +%m-%d_%H:%M:%S))"
    ;;
*) sed -n '2,22p' "$0"; exit 2 ;;
esac
