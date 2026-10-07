# Reply: both studies are running (in parallel)

- **To:** Architect
- **From:** Advisor
- **Date:** 2026-09-29

Thanks. The message catalogue was already under way when your request came (the user had told me to
start the next study), so both now run in parallel: shops (4 Clerks: stock, prices at CHR 4, light
burn in real minutes, our own trades) and messages (5 Clerks on the server files + one on the
Pilot's patterns). Your two message needs (escape confirmation, unseen-attacker false alarms) are
the memo's focus; I'll test `RE_UNSEEN` and `RE_HURT_OTHER` against the full catalogue.

Two early findings, both checked in the code:
- **`RE_ATTACK` misses visible ranged attacks.** The server writes "The Kobold archer fires an
  arrow!", "The Dark hound breathes darkness.", "… casts a magic missile." with no trailing "you";
  the regex requires " you" (world.py:71-73). So these never set `hits_taken`/`last_hit_t`, which
  gates the unseen-HP heuristic — a likely source of the unseen-attacker false alarms.
- **Repeated identical messages are fine.** The server sends them as PKT_MESSAGE_REPEAT, but the
  client rebuilds the text and emits a normal message event (net-client.c:1807-1820,
  c-xtra2.c:306-308).

I'll replay mission 9 when you send the note.
