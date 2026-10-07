#!/bin/bash
# inbox.sh: memo notifications between the Architect and the Advisor.
# The Architect (/projectnb/jbrcs/mangband/.claude/hooks/) and the Advisor
# (Advisor/.claude/hooks/) each keep an identical copy of this script.
#
# Usage: inbox.sh <command> <inbox-dir> [args]
#   watch               poll until an unread memo exists, print it, exit (run in background)
#   unread              list unread memos
#   mark-read [FILE...] mark memos read through the newest FILE (default: newest in inbox)
#   hook-session | hook-post | hook-stop
#                       Claude Code hooks (read hook JSON on stdin)
#
# State lives in the inbox and belongs to its recipient: .seen (read up to its
# mtime), .notified (PostToolUse already announced up to its mtime), .watcher
# (host and pid of the running watcher). Mtimes are copied from memos with
# touch -r, so clock skew between compute nodes doesn't matter.
set -u
self=$(readlink -f "$0")
cmd=${1:?command}; inbox=${2:?inbox dir}; inbox=${inbox%/}; shift 2
# mark-read also accepts memo files with no inbox argument; take the inbox from the first.
[ -f "$inbox" ] && { set -- "$inbox" "$@"; inbox=$(dirname "$(readlink -f "$inbox")"); }
case $(basename "$inbox") in
  to_architect) outbox=$(dirname "$inbox")/to_advisor;   peer=Advisor ;;
  to_advisor)   outbox=$(dirname "$inbox")/to_architect; peer=Architect ;;
  *) echo "inbox.sh: unknown inbox $inbox" >&2; exit 1 ;;
esac
seen=$inbox/.seen; notified=$inbox/.notified; pidfile=$inbox/.watcher
poll=30

[ -e "$seen" ] || touch -d @0 "$seen"
[ -e "$notified" ] || touch -r "$seen" "$notified"

# Memos newer than the given marker. Dotfiles (.tmp-* drafts, markers) are ignored.
newer_than() { find "$inbox" -maxdepth 1 -type f -name '[!.]*.md' -newer "$1" | sort; }
count() { [ -z "$1" ] && echo 0 || printf '%s\n' "$1" | wc -l; }
watcher_alive() {
  local host pid
  [ -f "$pidfile" ] && read -r host pid < "$pidfile" || return 1
  [ "$host" = "$(hostname)" ] && kill -0 "$pid" 2>/dev/null
}
context() {  # emit hook additionalContext
  jq -n --arg ev "$1" --arg ctx "$2" '{hookSpecificOutput: {hookEventName: $ev, additionalContext: $ctx}}'
}
howto="Protocol: read each new memo; run \`$self mark-read FILE...\` with the memos you read; then restart the watcher (Bash, run_in_background: \`$self watch $inbox\`). To send a memo to the $peer, write it to $outbox/.tmp-SLUG.md, then mv it to $outbox/YYYY-MM-DD-SLUG.md (the rename makes delivery atomic)."

case $cmd in
  watch)
    echo "$(hostname) $$" > "$pidfile"
    trap '[ "$(cut -d" " -f2 "$pidfile" 2>/dev/null)" = $$ ] && rm -f "$pidfile"' EXIT
    while :; do
      new=$(newer_than "$seen")
      if [ -n "$new" ]; then
        echo "New memo(s) from the $peer:"; printf '%s\n' "$new"
        echo "$howto"
        exit 0
      fi
      sleep $poll
    done ;;
  unread)
    newer_than "$seen" ;;
  mark-read)
    if [ $# -gt 0 ]; then last=$(ls -t "$@" | head -1)
    else last=$(ls -t "$inbox"/[!.]*.md 2>/dev/null | head -1); fi
    [ -n "$last" ] || { echo "no memos"; exit 0; }
    touch -r "$last" "$seen"
    [ "$seen" -nt "$notified" ] && touch -r "$seen" "$notified"
    echo "marked read through $(basename "$last")" ;;
  hook-session)
    new=$(newer_than "$seen"); n=$(count "$new")
    msg="Memo inbox: $inbox ($n unread${new:+: $(echo $new)})."
    if watcher_alive; then msg+=" The inbox watcher is already running."
    else msg+=" Start the inbox watcher now (Bash, run_in_background: \`$self watch $inbox\`); it exits, waking you, when a memo arrives."; fi
    context SessionStart "$msg $howto" ;;
  hook-post)
    input=$(cat)
    [ -n "$(jq -r '.agent_id // empty' <<<"$input")" ] && exit 0   # subagent call
    new=$(newer_than "$notified"); [ -n "$new" ] || exit 0
    touch -r "$(ls -t $new | head -1)" "$notified"
    context PostToolUse "New memo(s) from the $peer in $inbox: $(echo $new). Read them at the next sensible point (now if they may affect what you're doing). $howto" ;;
  hook-stop)
    input=$(cat)
    [ "$(jq -r '.stop_hook_active // false' <<<"$input")" = true ] && exit 0
    new=$(newer_than "$seen"); [ -n "$new" ] || exit 0
    jq -n --arg r "Unread memo(s) from the $peer: $(echo $new). Read them before stopping. $howto" \
      '{decision: "block", reason: $r}' ;;
  *) echo "inbox.sh: unknown command $cmd" >&2; exit 1 ;;
esac
