# Study: how game state reaches the Pilot and the Navigator (survey)

- **Status:** DONE 2026-10-03. Memo ../../../memos/2026-10-03-game-state.md; note to_architect/2026-10-03-game-state.md.
  confused about the state of the game (items in slots, level they are on, etc.) … let's make a
  proper survey of all info / how it is displayed / and generally assessing game state").
- **Goal:** a complete map of every piece of game state: where the server holds it, which packet
  sends it and when, how the client stores and shows it (tool mode), how the Pilot reads/derives it
  (and how often), and what the Navigator sees — then every recorded confusion traced to the layer
  where it went wrong, and a design for reliable state (single source of truth per item, freshness,
  verification).
- **Ground truth available:** packet logs of the user's observed sessions
  (`runs/observe/session{1,2,3}/pkt.jsonl`), `runs/phase0/birth1.pkt`; the Pilot can run with
  `--pktlog`.

## Assignments (pass 1)
| id | layer | status |
|---|---|---|
| G1 | server: every PKT the server sends to the player, its fields, and when (redraw flags) | done |
| G2 | client + tool mode: recv handlers, client-side state, what tool mode emits/answers; checked against the observed packet logs | done |
| G3 | the Pilot's world model: every state field, its source, refresh, derivations, pitfalls | done |
| G4 | the Navigator's view: status/report text, its prompt, what it believed vs truth (journals) | done |
| G5 | incident catalogue: every recorded state confusion (next_steps, HANDBOOK, git log, journals, logs) | done |

## Retrospective (2026-10-03)
- Splitting by *layer* (server, client, Pilot, Navigator) plus an *incident* catalogue worked: the
  layers explained the incidents, and the incidents showed which layers matter. All five Clerks
  were accurate; every claim I checked held.
- G4 found real report text in Navigator subagent transcripts (outside its listed sources) — a
  good source to name explicitly next time.
