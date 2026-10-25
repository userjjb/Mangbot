#!/bin/bash
# freeze.sh on|off|toggle|status -- the test server's time freeze (2026-10-25, the user).
# While testserver/FREEZE exists the test server processes no game turns (net-server.c time_frozen; the server
# must be started with MANGBAND_FREEZE_FILE set, see operations.md) and the Pilot holds. The viewer's F5 or
# Ctrl-F does the same. The live server has no such switch.
F=/projectnb/jbrcs/mangband/testserver/FREEZE
case "${1:-status}" in
  on)     echo "frozen by ${USER} $(date +%H:%M:%S)" > "$F"; echo "time frozen" ;;
  off)    rm -f "$F"; echo "time flows" ;;
  toggle) if [ -e "$F" ]; then rm -f "$F"; echo "time flows"; else echo "frozen by ${USER} $(date +%H:%M:%S)" > "$F"; echo "time frozen"; fi ;;
  status) if [ -e "$F" ]; then echo "FROZEN ($(cat "$F"))"; else echo "time flows"; fi ;;
  *) echo "usage: $0 on|off|toggle|status"; exit 2 ;;
esac
