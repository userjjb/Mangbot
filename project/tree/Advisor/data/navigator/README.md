# Navigator response-time data

- `response.py [NICK]`: per-mission Navigator response times from decisions.jsonl (`nav_cmd` records, logged since
  2026-10-09 00:07). Metrics and definitions in the docstring; add new missions to `MISSIONS`.
- `baseline_opus_m16-m21.txt`: the Opus Navigator baseline (missions 16-21, 2026-10-08 to 10-17; m21 confirmed Opus by the user), for the comparison
  with the Sonnet Navigator missions that follow (the user's request, 2026-10-17).
- `latency.py`: the older measure (Pilot news -> next recorded Navigator order), used before nav_cmd existed.
