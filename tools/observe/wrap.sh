#!/bin/bash
# wrap.sh LABEL [NICK] -- the Architect's per-mission wrap-up (session 6): end the mission by its label (a hot-swap
# loses the Pilot's in-memory label, so always by name), record the Navigator's tokens and cost, print the scorecard
# row, the last 2 hours of complaints, the viewer's ? notes, and the character's state. Then write the report in
# runs/pilot/NICK/reports/ and the mission's lessons in tools/pilot/FIELD-NOTES.md.
LABEL=${1:?usage: wrap.sh LABEL [NICK]}; NICK=${2:-dive04}
cd "$(dirname "$0")/.." || exit 1
module load python3/3.12.4 2>/dev/null
export PILOT_ROLE=architect
python3 pilot/pilotctl.py --nick "$NICK" mission end "$LABEL" 2>&1 | head -2
python3 observe/tokens.py "$LABEL" 2>&1 | tail -1
python3 observe/scorecard.py --table "$LABEL" 2>&1 | tail -2
python3 observe/damage_mix.py --nick "$NICK" >/dev/null 2>&1 && echo "damage mix refreshed (runs/pilot/$NICK/damage_mix.json: the EHP column)"
echo "--- complaints (last 2 h)"
grep "$(date +%Y-%m-%d) \($(date +%H)\|$(date -d '-1 hour' +%H)\)" ../../runs/complaints.md | cut -c1-260
echo "--- questions (viewer ? notes)"
python3 observe/notes.py --nick "$NICK" --questions 2>&1 | grep -A3 QUESTION | tail -8
echo "--- status"
python3 pilot/pilotctl.py --nick "$NICK" status 2>&1 | head -12
python3 pilot/pilotctl.py --nick "$NICK" debt 2>&1 | head -4
