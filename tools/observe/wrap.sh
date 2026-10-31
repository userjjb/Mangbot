#!/bin/bash
# wrap.sh LABEL [NICK] -- the Architect's per-mission wrap-up (session 6): end the mission by its label (a hot-swap
# loses the Pilot's in-memory label, so always by name), record the Navigator's tokens and cost, print the scorecard
# row, refresh the damage mix at the mission's depth band, the complaints and the viewer's ? notes since the mission
# start, and the character's state. Then write the report in runs/pilot/NICK/reports/ and the mission's lessons in
# tools/pilot/FIELD-NOTES.md.
LABEL=${1:?usage: wrap.sh LABEL [NICK]}; NICK=${2:-dive04}
cd "$(dirname "$0")/.." || exit 1
module load python3/3.12.4 2>/dev/null
export PILOT_ROLE=architect PILOT_TOKEN=$(cat "$(dirname "$0")/../../../runs/private/architect.token")
python3 pilot/pilotctl.py --nick "$NICK" mission end "$LABEL" 2>&1 | head -2
python3 observe/tokens.py "$LABEL" 2>&1 | tail -1
python3 observe/scorecard.py --table "$LABEL" 2>&1 | tail -2
BAND=$(python3 observe/damage_mix.py --nick "$NICK" --mission "$LABEL" 2>&1 >/dev/null) \
  && echo "damage mix refreshed (runs/pilot/$NICK/damage_mix.json: the EHP column; $BAND)" || echo "damage mix FAILED: $BAND"
# the mission's start ("YYYY-MM-DD HH:MM", runs/missions.json); 2 hours ago if the label isn't there
START=$(python3 -c 'import json, sys; print(next((m["start"] for m in json.load(open(sys.argv[1]))[::-1]
                                                   if m.get("label") == sys.argv[2]), ""))' ../../runs/missions.json "$LABEL")
[ -n "$START" ] || START=$(date -d '-2 hour' '+%Y-%m-%d %H:%M')
echo "--- complaints (since $START)"
awk -v s="$START" '/^- [0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9] [0-9][0-9]:[0-9][0-9]/ && substr($0, 3, 16) >= s' \
  ../../runs/complaints.md | cut -c1-260
echo "--- questions (viewer ? notes during the mission)"
python3 observe/notes.py --nick "$NICK" --questions --mission "$LABEL" 2>&1 | grep -A3 QUESTION | tail -8
echo "--- status"
python3 pilot/pilotctl.py --nick "$NICK" status 2>&1 | head -12
python3 pilot/pilotctl.py --nick "$NICK" debt 2>&1 | head -4
