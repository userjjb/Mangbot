# Memo: post-mortem of our runs (Advisor → Architect, 2026-09-28)

**Backlog topic 3.** It also replays the group-danger rule proposed in the Borg memo (§3.1)
against our logs. **Audit trail:** `Advisor/studies/2026-09-28-postmortem/`. **Replay scripts:**
`Advisor/data/runs/` (README there).

## How this was made

- **Sources:** `runs/pilot/dive01–04/{decisions,events}.jsonl`, `pilot.log`, `navigator.md`; the
  mission reports in `next_steps.md`; `HANDBOOK.md`; the Pilot's git log.
- **Three Clerks:** R1 catalogued Dive03's 636 attention records; R2 listed every recorded failure
  and fix (34 rows); R3 reconstructed the death and the three worst near-deaths second by second.
  The Advisor wrote the group-danger replay (X1) and checked the claims below in the logs and commits
  (**[log ✓]**).
- **Clock alignment:** `events.jsonl` restarts at t = 0 with each Pilot process. The segments were
  matched to the `started` records in `decisions.jsonl`. R3 matched the 8 Phase Door acks to the
  0.001 s; the replay's last segment ends with the Uruks at the death.

## 1. What killed Dive03 (twice)

Dive03 died **twice**. Only the second death is in `next_steps.md`'s mission list.

| | Death 1 | Death 2 (permanent) |
|---|---|---|
| when, where | 2026-09-25 23:16, 1000 ft | 2026-09-27 22:28, 750 ft |
| killer | Black ogre, with Stone trolls (lvl 25) and a Gnome mage; clvl 18 | Uruk: summon trap, 4 Uruks + Giant red scorpion (STR drain) |
| sequence | fled a fight by stairs, **kept exploring** at 1000 ft; one Phase Door, then held by the 2.5 s reuse limit | meleed for 6.7 s (253 → 116 HP) before the first emergency; then 8 Phase Door reads, 2 quaffs and a Word of Recall, **none of which ran** |
| fix | 3b7729f (Recover goal, continuous danger check, 0.7 s phase reuse below 35%, WoR last resort, `max_depth`) | 785f608 (the emergency never falls through to the goal; no `clear` within 2 s of a use) |
| evidence | `decisions.jsonl` dead record 23:15:59; `events.jsonl:15868-15869` "killed by a Black ogre" **[log ✓]** | `events.jsonl:77880-81184`: no Phase Door, "feel better" or recall message in the fight; WoR and CCW ×2 on the floor after death **[log ✓]** |

**The common pattern:** a group the character couldn't fight at its level, then an escape that
didn't happen in real time. The three worst near-deaths before these (20–31% HP: Lagduf's orc pit
at 400 ft, a Priest group with an Illusionist at 650 ft, Mughash's kobolds at 450 ft) were survived
because every Phase Door, potion and recall *executed* (R3, inventory counts and "You feel much
better" in the log). **Execution, not choice, separated the survivals from the deaths.**

Two details from the fatal fight:
- **The emergency came late.** It fired at 116/253 (46%, just under `flee_hp` 0.5), 6.7 s into a
  14.6 s fight. By the time the first escape was sent, half the HP and one blow (STR drain 3 → 2)
  were gone.
- **The Navigator misdiagnosed the death.** It reported "Pilot crash, connection refused". The
  Pilot was alive and acting through the fight; it stopped answering its control socket only
  *after* the death (fixed in 785f608). The game connection was never the problem.

## 2. The group-danger rule, replayed on the logs

**The rule:** group = Σ over monsters in view of (melee_max × speed_x + w × drain_blows), with
stationary (NEVER_MOVE) monsters excluded; ratio = group / current HP. Dive03 gives 3751 samples of
the monster list, and 11 episodes of HP falling below 50%.

| tier | episodes fired | followed by HP < 50% within 60 s | fired before the 11 drops |
|---|---|---|---|
| > 0.3 × HP | 34 | 13 | **11 / 11** (within 120 s) |
| > 0.6 × HP | 17 | 13 (76%) | 9 / 11 |
| > 1.0 × HP | 9 | 9 (100%) | 4 / 11 |

(With the drain weight w = 50. The Borg's w = 150, and counting stationary monsters, doubled the
false alarms: Rot jellies, worm masses, mushroom patches, Radiation eyes and single Giant red frogs
set it off.)

**Timing is what matters.** HP fell from ≥ 90% to < 50% in **7–17 s** in 10 of the 11 episodes.

| tier | lead before HP < 50% |
|---|---|
| 0.6 | only 1–5 s (78 s once). The ratio uses *current* HP, so it rises as HP falls and fires mid-collapse |
| 0.3 | 5–104 s, typically 5–14 s. Enough time to act |

**So the Borg memo's §3.1 tiers should shift down for a real-time bot:**
- **> 0.3× HP:** don't engage and don't walk toward the group. If it's on arrival, take the stairs
  back. If fighting, disengage toward the stairs.
- **> 0.6× HP:** escape now: stairs underfoot, else Phase Door. No more melee.
- **> 1.0× HP:** it's already collapsing. Use the strongest escape available.

The replay under-sells the live rule. The monster list has no distances, and it was sampled
irregularly: nothing at all for 86 s before the fatal fight, then one sample at 207/253. The live
Pilot decodes the map every 0.5 s and would see the group sooner. At the death, the rule
would have fired at the trap (22:28:25), 6 s before the actual emergency. With the 785f608 bug still
present, that wouldn't have saved it; with the bug fixed, it likely would have.

## 3. Other recurring patterns (R1, R2)

1. **Unseen-attacker false alarms:** 48 `unseen_attacker` events on 09-27. The Navigator calls
   most of them false: HP loss after killing a visible monster, bleeding or trap damage, and molds
   not counted as "in view". Each one cost a flee and a new level. Mission 4 and 5 fixes narrowed
   this; the 09-27 volume says it isn't finished.
2. **Recall as a last resort fires too late:** all 3 cases at 23–26% HP. By then a group kills in
   one to three turns.
3. **Stair bouncing during an emergency:** 12 alternating `<` `>` in 67 s at 20–26% HP (400 ft,
   09-25 21:12–21:13). That wasted turns while critically low; it was pre-3b7729f.
4. **Stalls:** 2 `stuck` events, plus 2 silent stalls (9 min with no events; a level sealed by
   rubble before digging existed) reported by the Navigator.
5. **Fear at 650 ft:** a Priest and Novice priests kept the warrior terrified and unable to melee
   (the only `fearer` and `afraid` events). Boldness/Heroism potions are the answer (HANDBOOK
   already says so).
6. **One alarm repeated for hours:** `low_supply` fired 62 times (lantern fuel, in town, every 2 min
   for 2 hours). That's noise for the Navigator.
7. **The Navigator uses vanilla monster lore.** At 50 ft (Dive04) it thought a Radiation eye meant
   "the level looks wrong, deep in vanilla". In MAngband 1.5 the Radiation eye is level 3.
8. **Time use (Dive03):** explore 33%, dive 32%, shop 27% (87 short shop goals), flee 2%; 76% of the
   time in the dungeon.

**Classes that keep recurring after fixes** (R2's 34-row table): **danger judgement** and **escape
execution** each killed Dive03 once. Perception, stuck/movement, item handling and infrastructure
failures were each fixed once and haven't come back (Dive04, mission 8, is clean so far, but
only down to 150 ft).

## 4. Recommendations: Pilot

1. **Group danger with the tiers of §2** (0.3 / 0.6 / 1.0 × current HP, drain weight 50,
   stationary excluded, monsters within 1 + speed_x squares). `melee_max` and `drain_blows` are in
   `danger_table.csv`. The replay scripts can be re-run on new runs to tune it.
2. **Verify every escape.** After a read or quaff in an emergency, check the effect message (Phase
   Door: position change; potion: "You feel…" or an HP change; recall: "The air about you becomes
   charged") within ~1 s. If there's none, the command was lost: resend it, and suppress anything
   that sends `clear`. This detects the 785f608 bug class, whatever its cause (forum memo §1.4:
   "an escape must be one reliable action, and it must be verified").
3. **Recall earlier:** start Word of Recall once the group ratio passes 0.6 and no stairs are known,
   not at 26% HP. It activates 15–34 player turns after reading (`randint0(20)+15`,
   `spells2.c:1191`; corrected 2026-09-29 from "~50"), so it has to start while the character can
   still survive that long.
4. **After an emergency escape, don't resume the goal on the same level.** Rest, then leave (death 1).
   3b7729f's Recover goal does this after stairs; extend it to escapes by Phase Door or potion.
5. **Unseen attacker:** ignore HP loss for N s after killing a visible monster; count a monster
   adjacent in the monster list as "in view" even if the map decode misses it. That covers the
   remaining 09-27 false-alarm causes the Navigator listed.
6. **Log the monster list at a steady rate** (every 0.5 s in the dungeon), or log the decoded map's
   monsters in `decisions.jsonl`. The 86 s gap made the death hard to replay.
7. **Deduplicate standing alarms** (`low_supply`): report once, then only when the state changes.

## 5. Recommendations: Navigator and doctrine

- **Level vs depth:** death 1 was clvl 18 at 1000 ft against level-25 trolls. The Borg's rule
  (clvl ≥ dl − 4 until dl19, ≥ dl beyond) would have kept it at 700–900 ft. See the Borg memo §4:
  still a decision for the user and the Architect.
- **Give the Navigator the danger table's facts** (name, level, danger, threats) through a
  `pilotctl` query, so it stops using vanilla lore (the Radiation eye).
- **Treat "connection refused" after a fight as "check if the character died"**, not "the Pilot
  crashed" (785f608 keeps the Pilot answering after death).

## Coverage and gaps

- **Covered:** all of Dive03 (both deaths, 11 episodes below 50% HP, 636 attention records), R2's
  review of dive01/02/04, and `next_steps.md` in full.
- **Not covered:** Dive04 beyond 150 ft (mission 8 is ongoing).
- **Replay caveats:** it uses the monster list, which is sparse and has no distances; the tiers need
  re-checking on the next deaths or near-deaths.
- **R1 and R3 disagreed on mission numbering.** `navigator.md` uses day-relative clocks, so the
  missions here are dated by epoch, not by number.
