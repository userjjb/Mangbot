# Shared rules: message catalogue study (every M Clerk reads this first)

## Purpose
Our bot (the **Pilot**, `/projectnb/jbrcs/mangband/github/tools/pilot/pilot.py`) plays MAngband 1.5.3
from the screen and the game's text messages only. It must recognise from message text what just
happened: damage taken and from whom, a status starting or ending, a stat drained, an escape
working or failing, a summon, a monster dying, a level change, etc. You are building part of a
catalogue of every message the server can send.

## Input
Your rows: `/projectnb/jbrcs/mangband/Advisor/studies/2026-09-29-messages/scratch/<id>_input.csv`
(columns: id, file, line, function, call, format, args, msg_type). `format` is every C string
literal in the call concatenated — **when a call chooses between strings (`a ? "x" : "y"`) they
appear run together, and 81 calls build their text at run time (no literal)**. For those, and for
anything unclear, **open the source line** in `/projectnb/jbrcs/mangband/github/src/server/<file>`
and read the surrounding code (which case/branch, who receives it). `%s`/`%^s` are usually monster
or item names; `%d` numbers. Some messages go to *other* players nearby (`msg_format_near`,
`msg_print_near`): mark those `audience=others`.

## Output (both)
1. CSV `/projectnb/jbrcs/mangband/Advisor/studies/2026-09-29-messages/scratch/<id>_catalogue.csv`,
   one row per input row (all rows; add rows if one call yields several distinct texts), columns:
   `id,file,line,text,event,audience,pilot_relevance,regex,condition,notes`
   - `text`: the message as the player sees it, with `<monster>`, `<item>`, `<n>` placeholders.
   - `event`: a short dotted name from the vocabulary below (invent new ones in the same style if
     needed, and list them in the dispatch).
   - `audience`: self / others / all (broadcast).
   - `pilot_relevance`: high (changes what the Pilot should do now: danger, status, escape outcome,
     death, drain, summon, can't-act), medium (useful state: item counts, level feeling, hunger,
     light), low (flavour, shops, social), none.
   - `regex`: a Python regex that matches the rendered message (anchor with ^...$; use named groups
     `(?P<mon>.+?)`, `(?P<item>.+?)`, `(?P<n>\d+)`; escape literal dots and parentheses).
   - `condition`: when it is sent (e.g. "melee blow RBE_POISON, not resisted"), with file:line.
2. Dispatch `/projectnb/jbrcs/mangband/Advisor/studies/2026-09-29-messages/dispatches/<id>.md`,
   ≤ 2000 words, dispatch format: the events found in your files and how many messages each has;
   the **high-relevance** events with their messages; ambiguities (the same text meaning different
   things, or one event with many texts); messages that look alike but mean different things
   (e.g. a resisted vs unresisted effect); and anything surprising.
Write the CSV with a small Python script (quote fields properly). Check your regexes compile.

## Event vocabulary (extend as needed)
attack.melee.hit / attack.melee.miss / attack.melee.effect.<poison|blind|confuse|terrify|paralyze|
drain_str|...> · attack.spell.<name> (monster casts) · attack.breath.<element> · attack.ranged
(arrows, bolts) · attack.unseen (It/Something) · damage.element.<x> · resist.<x> (you resist) ·
status.<blind|confused|poisoned|afraid|paralyzed|slow|fast|stun|cut|hallucinate|...>.<on|off|worse|
better> · stat.drain.<stat> / stat.sustain.<stat> / stat.restore.<stat> · exp.drain / exp.level_up
· summon · monster.death / monster.flee / monster.wake / monster.appear · player.death ·
escape.<phase|teleport|teleport_level|recall_start|recall_cancel|recall_activate|stairs> ·
item.use.<ok|fail|empty|nothing_happens|cant_blind|cant_confused> · item.count · item.destroyed
(fire/acid/cold) · item.stolen · gold.stolen · pickup · inventory.full · hunger.<state> ·
light.<low|out|refuel> · level.feeling · level.change · move.blocked · door.<...> · trap.<...> ·
store.<...> · party.<...> · system.<...> · player.hit_monster / player.miss / player.kill
