# data/messages — MAngband 1.5 server messages (message-catalogue study, 2026-09-29)

- `extract_messages.py` → `server_messages.csv`: every message call in `github/src/server/*.c`
  (1352 calls: id, file, line, function, call, format = the call's C string literals concatenated —
  alternatives from `a ? "x" : "y"` run together — args, msg_type).
- `log_messages.py` → `log_messages.csv`: every game message seen in `runs/pilot/*/events.jsonl`,
  numbers normalised to `#` (1826 distinct, 18489 total as of 2026-09-29). Message `type` is 0 for
  almost all, so text is the only reliable signal.
- `catalogue.csv` (built by `build_catalogue.py` from the Clerks' tables): text, event, audience,
  pilot_relevance, regex, condition per message. See `../../studies/2026-09-29-messages/`.
