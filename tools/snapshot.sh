#!/bin/bash
# snapshot.sh -- copy the whole project state into github/project/ so a commit
# (and a push to the public repo) can restore any earlier state: the docs and
# handoff, memos, the Advisor's studies and scripts, the agents and hooks,
# both Claude memories and the global CLAUDE.md. See project/README.md.
#
# Left out on purpose (it's a PUBLIC repo): passwords (runs/private), game
# savefiles (they hold passwords), server logs and crash dumps (they name the
# Unix login and host), third-party material (the forum corpus, the Borg and
# upstream MAngband source copies), bulky recordings and raw event streams,
# sockets, packet logs (a login packet carries the password), raw timeline
# extracts, inbox state files, and any file over 5 MB.
#
#   tools/snapshot.sh          then commit and push as usual
set -eu
PROJ=/projectnb/jbrcs/mangband
DST=$PROJ/github/project
MEM=$HOME/.claude/projects
mkdir -p "$DST/tree" "$DST/memory/architect" "$DST/memory/advisor" "$DST/claude"
rsync -a --delete --delete-excluded --max-size=5m \
  --exclude '/github/' \
  --exclude '/runs/private/' \
  --exclude '/testserver/save/' --exclude '/testserver/crash*' --exclude '/testserver/bone/' \
  --exclude '/testserver/*.log' \
  --exclude '/Advisor/data/forum/' --exclude '/Advisor/data/borg/' --exclude '/Advisor/data/versions/' \
  --exclude '/runs/observe/' --exclude '/runs/pilot/*/events.jsonl' --exclude '/runs/live-*-events.jsonl' \
  --exclude '*.sock' --exclude '*.fifo' --exclude '__pycache__/' --exclude '*.pyc' \
  --exclude '*.pkt' --exclude '/runs/phase0/' --exclude '*.tl' \
  --exclude '.watcher' --exclude '.seen' --exclude '.notified' \
  "$PROJ/" "$DST/tree/"
rsync -a --delete "$MEM/-projectnb-jbrcs-mangband/memory/" "$DST/memory/architect/"
rsync -a --delete "$MEM/-projectnb-jbrcs-mangband-Advisor/memory/" "$DST/memory/advisor/"
cp "$HOME/.claude/CLAUDE.md" "$DST/claude/global-CLAUDE.md"
date -Is > "$DST/SNAPSHOT_TIME"
# refuse to continue if anything secret-looking slipped in
if grep -rIl -E 'ghp_[A-Za-z0-9]{20}|github_pat_|BEGIN (RSA|OPENSSH) PRIVATE' "$DST" ; then
  echo "snapshot.sh: secret-looking content above; not safe to commit" >&2; exit 1
fi
du -sh "$DST"
