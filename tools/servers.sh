# servers.sh -- source me: the local server chosen by $MANGBOT_SERVER (local = the default, debug = the debug server).
# Sets MB_SERVER, MB_PORT, MB_DIR (the server's directory), MB_RUNS (the runs root), MB_FREEZE, MB_SAVE.
# The same table as tools/servers.py (keep them in step); see its docstring.
MB_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
MB_SERVER=${MANGBOT_SERVER:-local}
case $MB_SERVER in
  local) MB_PORT=28346; MB_DIR=$MB_ROOT/testserver; MB_RUNS=$MB_ROOT/runs ;;
  debug) MB_PORT=28350; MB_DIR=$MB_ROOT/debugserver;   MB_RUNS=$MB_ROOT/runs/debug ;;
  *) echo "MANGBOT_SERVER=$MB_SERVER: unknown server (known: local, debug)" >&2; return 1 2>/dev/null || exit 1 ;;
esac
MB_FREEZE=$MB_DIR/FREEZE; MB_SAVE=$MB_DIR/save
