# Replay file schema (one JSON per episode: replays/ep<idx>.json)

All times are Unix epoch seconds (wall clock) as in decisions.jsonl "t" and events.jsonl "epoch". Never use state.jsonl
times (game clock). Positions are [y, x] map coordinates as in decisions "pos" and "mons".

```
{
 "idx": 41, "mission": "m30", "depth_ft": 650,
 "level_dump": "20261025-064212-650ft.txt",          # the runs/pilot/dive04/levels file whose header time range contains t0
 "t0": 1792..., "t_trigger": ..., "t_end": ...,        # t0 = FIGHT START (see below); trigger = E1's episode start; end = E1's end
 "t0_rule": "first hostile message within 60 s before the trigger"   # how you chose t0
 "player": {"pos": [y, x], "hp": 303, "mhp": 333, "clvl": 25, "ac": null,
            "status": {"slow": false, "fast": false, "hero": false, "berserk": false, "blind": false, "confused": false,
                       "afraid": false, "poisoned": false, "paralyzed": false},
            "free_action": false, "see_invisible": false},  # from equipment/inventory if known, else null
 "inventory": {"ccw": 14, "csw": 3, "clw": 0, "phase": 21, "tele": 2, "staff_tele": 0, "wor": 3, "speed": 2,
               "berserk": 0, "hero": 2, "boldness": 0, "magic_mapping": 3, "door_stair_rod": 1} | null,
 "inventory_source": "state.jsonl inven at <time> (approx)" | "act why strings" | null,
 "monsters_t0": [{"name": "Druid", "y": 46, "x": 51, "dist": 1}],       # from the last decisions "mons" record at or before t0
 "arrivals": [{"t": ..., "name": "Fire hound", "y": .., "x": .., "dist": ..}],   # first appearance after t0 of each new monster
 "summons": [{"t": ..., "text": "The Druid magically summons animals."}],
 "unseen_hits": [{"t": ..., "text": "It hits you."}],                    # attacks/spells by "It"/"Something"
 "hostile_msgs": [{"t": ..., "text": "The Fire hound breathes fire."}],   # every message about a monster acting on us, t0..t_end
 "status_msgs": [{"t": ..., "text": "You are paralyzed!"}],              # status on/off messages t0..t_end
 "actions": [{"t": ..., "cmd": "custom r item=7", "what": "phase", "why": "...", "src": "pilot|navigator",
              "t_effect": ... | null}],                                 # what in {melee, walk, run, stairs, phase, tele, staff_tele,
                                                                        #  wor, ccw, csw, clw, speed, berserk, hero, boldness, rest, other}
                                                                        # t_effect = time of the confirming message/position change
 "melee_by_us": [{"t": ..., "text": "You hit the Wolf."}],              # our hits/misses/kills
 "kills": [{"t": ..., "name": "Wolf"}],
 "hp_series": [[t, hp, mhp]],                                           # every decisions record with hp, t0-30 s .. t_end
 "pos_series": [[t, y, x]],                                             # every position change (events "pos")
 "mons_series": [[t, [[y, x, "name"], ...]]],                           # EVERY decisions "mons" record t0-10 s .. t_end (monsters in view)
 "time_factor": [[t, factor]],                                          # decisions "time_factor" records t0-60 s .. t_end
 "map_window": ["41 lines of 41 chars centred on player pos at t0, from the level dump"],
 "outcome": {"lowest_hp": .., "t_lowest": .., "end": "teleport|recall|stairs|killed all|left|other", "consumables": {...}},
 "notes": "anything odd"
}
```

**t0 (fight start):** the latest time before E1's trigger such that from t0 to the trigger HP never rose above its t0 value
by more than 10 and a hostile monster message or adjacent monster exists within 5 s after t0; in practice: walk back from the
trigger to the last moment with HP >= 90% of max or with no monster within 2 squares, whichever is later. State the rule used.
