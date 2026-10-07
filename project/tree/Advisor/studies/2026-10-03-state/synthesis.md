# Synthesis notes — state survey

## G5 (incident catalogue) — read 2026-10-03, verdict: good; 71 incidents 09-24 → 10-03
Verified: "Your purse feels lighter." twice in dive04 (events.jsonl:16369, 17676) and no handler in the
Pilot (grep "purse" in tools/pilot/*.py: none) ✓ → mission 10's gold loss = Smeagol/thief, unnoticed.
HANDBOOK:302-303 still says `explore until=stairs` ends at once when any stairs are known; code now
requires a reachable stair (pilot.py:235-237) ✓ → stale doc.
By item: inventory ~15, map/stairs reachability ~11, monsters missed/phantom ~8, depth/level/recall
~7, store ~6. By layer: Pilot parsing ~15, Pilot logic ~13, Navigator memory ~12, wrong assumptions
about server data ~10, Pilot staleness ~10. Recurring after fixes: inventory identity (name lookup →
stale letter → held uses reported done), escape execution (3 fixes), unseen-attacker (6 fixes),
Navigator selling unidentified items (4× after the HANDBOOK warning; mission 12 sold Potions of Speed
for 8 each).

## G2 (client + tool mode) — read 2026-10-03, verdict: very good
Verified: depth indicator is INDICATOR_PKT(DEPTH, TINY, 1) (tables.c:773) and TINY values are packed as
`signed char` (net-game.c:378) ✓ → dungeon 0–127 fine, wilderness negative world indices wrap (G2 saw
-31, 93, -107… and the curses client showed "4650 ft"/"-5350 ft"). Tool-mode `level{depth}` is wrong in
the wilderness.
Accepted: level indicator = [max, cur]; inventory resends only changed slots, but removing an item
resends from that slot to the end (letters shift silently); inscriptions/charges only inside the name
text; depth indicator arrives after the new map; tool mode ignores the "cursor outside panel" packet
(pos can be stale); monster list = names+counts only; floor item and PKT_OBJFLAGS (resist grid) are
stored by the client but never emitted; no recall-pending / timed-buff / light-radius state is sent
at all. The observe pkt.jsonl logs are curses sessions, not tool mode.

## G3 (Pilot model) — read 2026-10-03, verdict: very good (48 state rows)
Verified: inven_dirty message triggers (world.py:143-147) miss "Your X was destroyed!", "…was stolen!",
"Your pack overflows!" ✓; any level change sets recall_pending = False (world.py:138) though the server's
recall timer keeps running ✓ (a second read then cancels the recall).
Accepted: polls — status 0.3 s, map 0.5 s/on step, inventory 10 s or when dirty (the client's copy is
current; the lag is the Pilot's cache); commands carry only a slot index chosen from the cached pack;
only escape/cure uses have confirm-and-resend (`pending_use`); depth from two unreconciled sources
('level' event vs status `ind.depth`); "in the dungeon" defined three ways (disagree in wilderness);
monsters from map glyph decode, server monlist only logged; clvl fix done, but the same pattern
(raw index, cached value) is patched site by site.

## G1 (server packets) — read 2026-10-03, verdict: very good
Agrees with G2 on depth (signed byte; only signal of a level change) and inventory (per-slot packets
with letter, name, tval, count, weight; no sval, no inscription field; removal resends the following
slots; used-up slots sent as "(nothing)" tval 0; "You have no more X" arrives before the slot packets).
Verified: **PKT_REDRAW is a full resync**: server recv_redraw sets PR_BASIC|PR_EXTRA|PR_MAP|PR_FLOOR and
redraw_inven = all slots (net-game.c:1756-1764) ✓; the client has send_redraw() (net-client.c:406,
used by Ctrl-R c-cmd.c:1448) ✓; tool mode has no `redraw` verb (c-tool.c verb list) → a one-line
addition gives the Pilot an authoritative resync on demand.
Accepted: position only via PKT_CURSOR (wire order py, px); torch fuel in the equipment name can lag
≤99 turns; never sent: monster HP numbers, recall timer, light radius, buff timers; level feeling and
day/night only as text.

## G4 (Navigator view) — read 2026-10-03, verdict: very good (41 beliefs checked, 30 right)
Verified: `wait --brief` keeps only status lines, monsters, stairs, news (pilotctl.py:43, 62-78) ✓;
report() clears self.news every time it is built (pilot.py:2486-2488) ✓ — so any status call (even one
piped through grep) eats the "Since last report" news.
Accepted: Navigator right on HP, depth (ft), gold; wrong from stale pack lines (Pack now: after a stack
merge showed 7 Phase, real 12), wrong Pilot output ("level 18" before the level-up; "level 10" after
resurrection at clvl 8 — fixed by 72ec098's "(max N)"), and state never shown (stat max, max depth,
recall pending, thefts). ~85–90% of Navigator turns are `wait --brief` → it plays the pack from memory.
The dive03 journal's "Pilot crash" was the character's death (the Pilot exited; fixed in 785f608).
False "quaffed CLW" events at the 09-29 death (guard now pilot.py:947-952).
