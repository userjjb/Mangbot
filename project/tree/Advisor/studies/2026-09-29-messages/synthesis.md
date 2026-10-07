# Synthesis notes — message catalogue

## P2 (Pilot's patterns) — read 2026-09-29, verdict: good
Verified: `RE_ATTACK` (world.py:71-73) requires " you" after every verb, so visible-monster ranged
attacks phrased "<mon> fires an arrow!", "<mon> breathes <x>.", "<mon> casts a magic missile."
never match (29 distinct such lines in log_messages.csv) → hits_taken / last_hit_t not updated;
last_hit_t gates the unseen-HP heuristic. `RE_HURT_OTHER` is an unanchored substring regex
("pit", "cut", "poison", "faint"…) → over-matches (per P2: "growing faint", "high pitched",
"Cutlass", "Slow Poison") — to check in the merge.

## M5 (world messages) — read 2026-09-29, verdict: good; its main worry resolved by the Advisor
- Repeats: identical consecutive message of the same type is sent as PKT_MESSAGE_REPEAT with no text
  (util.c:1907-1911) ✓. But the client rebuilds it from message_last() and calls do_handle_message
  (net-client.c:1807-1820), which in tool mode emits a normal `message` event (c-xtra2.c:306-308,
  c-tool.c:220-226) ✓ → **the Pilot does see repeated lines; no bug.**
- Almost all messages are type 0; only chat types differ; some events also send PKT_SOUND ids.
- Level feelings only to the player whose arrival generated the level, only in the dungeon
  (dungeon.c:2075-2080). No "time bubble" text; low-HP warning "*** LOW HITPOINT WARNING! ***" needs
  the option + hitpoint_warn.

## M1 (monster attacks) — read 2026-09-29, verdict: very good (319 rows)
Verified: "misses you" only if the monster is visible (melee1.c:1313-1320) ✓ → an unseen attacker's
misses are silent; spell "mumbles"/blind texts keyed on the *player's* blindness (melee2.c:445) ✓.
Accepted: unseen monsters are named "It" in melee/spell texts; ~40 spells share "<M> mumbles."
when blind; slow/hold/teleport-to/away/forget/blink/haste have no blind branch; "You resist the
effects!" shared by resist and saving throw; blows show no damage numbers.

## M4 (commands) — read 2026-09-29, verdict: good (315 rows)
Accepted/spot-checked: shared trap texts (dart = slow / STR / DEX / CON drain traps; needle = STR/CON
chest; "cloud of smoke" = summon trap/chest, Dive03's killer); gas-trap texts even when resisted;
"There is a monster in the way!" → the command becomes a melee attack; "You are too afraid to
attack <mon>!" = melee refused; unlocked doors open silently; 8 dead rows. Its repeat-packet worry is
resolved (see M5 note).

## M3 (item use) — read 2026-09-29, verdict: very good (376 rows, escape/cure table = its finding 1)
Verified: teleport_player() (spells1.c:167ff) sends no message; Phase Door scroll = teleport_player
(use-obj.c:795-800) ✓ → **success of Phase Door / Teleportation / staff of Teleportation is shown
only by the count line ("You have N Scrolls of …" / "You have no more …") and the position change.**
Accepted: cure potions print only if something changed (silent at full HP / no ailment); Boldness and
Neutralize Poison silent with nothing to cure; no Deep Descent in 1.5.3; staff skill roll before the
charge check.
