# Memo: version history, outdated forum advice, and the live-server rules (Advisor → Architect, 2026-09-29)

**Backlog topic 5.** **Audit trail:** `Advisor/studies/2026-09-29-versions/`.
**Data:** the upstream repo `Advisor/data/versions/upstream/` (github.com/mangband/mangband, 2753
commits, 2005–2022), monster files by tag in `Advisor/data/versions/monsters/`, and the forum
corpus `Advisor/data/forum/corpus/{news,bugs,techsupport}.txt`.

## How this was made

- **Clerks V1–V3** read every commit subject from 2005–2009, 2010–2018 and 2019–2022, opening the
  gameplay-relevant diffs.
- **Clerk F1** read the News (43 topics), Bug Reports (6) and Technical Support (5) subforums.
  These were fetched from archive.org, because mangband.org returned 502 all evening; only 64 of
  159 pages were archived.
- **The Advisor** diffed the data files by script and checked the claims marked **[code ✓]**.
- The repo's ChangeLog and NEWS are empty, so commits are the history.

## 1. What our server actually is

- **Our "pristine 1.5.3" is upstream develop at 2022-03-13 (c97e873), not the v1.5.3 tag.** All
  101 files in `src/server`, `src/common` and `lib/edit` match c97e873 exactly. Six differ from the
  v1.5.3 tag (+28/−9 lines): shots-per-round energy while firing (4b45094), a wilderness fix, and
  format/warning patches **[code ✓]**. For a melee warrior it plays as 1.5.3. The live server
  probably runs the release; the only gameplay difference is archery.
- **Monster data hasn't changed since 2008.** `monster.txt` is byte-identical from v1.1.2 (2009)
  to v1.5.3 apart from the version line **[code ✓]**. Its content is vanilla Angband 3.0.6's
  monsters (imported 2005, d08ccf1) plus 2007 MAngband tweaks. `p_race`, `ego_item` and
  `artifact` are also unchanged since 1.1.4. **So monster lore from the forum's 2008–2014 posts
  describes our monsters.** Where the forum got depths wrong (hounds, danger memo §6), that's
  memory, not version drift. Vanilla 3.x/4.x lore can differ: in 1.5.3 the Radiation eye is level
  3.
- **Two lines of development.** 1.1.3, 1.1.4 and 1.4.0 (2016–2018) were a stable branch of
  ported fixes. The 2009–2016 trunk rewrite (netcode, streams, the time bubble, the new
  auto-retaliator) first shipped in **1.5.0 (2019)**.

## 2. Forum advice that is outdated (or confirmed) for 1.5.3

| topic | forum-era rule (0.7–1.1.x) | 1.5.3 | evidence |
|---|---|---|---|
| **Time bubble** | none. Runs cost 1/5 energy per step; there's no slow-down at low HP | the bubble exists (committed 2009-05-07, first released in 1.5.0): resting or running with no monster in view speeds up *your whole bubble* (monsters too) ×5–10; low HP slows it down (`hitpoint_warn`) | f01053d; `xtra2.c:5164ff` **[code ✓]** |
| **Auto-retaliate "eats your next move"** (forum memo §1.3) | true of the old retaliator | it fires only with no command queued, not confused or afraid, and costs one *blow's* energy (`level_speed/num_blow`). A queued escape pre-empts it | `dungeon.c:1032-1045` **[code ✓]**; rewritten Aug 2008 (trunk → 1.5.0) |
| **Uniques come back on resurrection** (forum memo §4) | — | they're restored on **every death** (`ressurect_uniques` runs after both the ghost and non-ghost branches) | `xtra2.c:2692-2706` **[code ✓]** |
| **Cure potions heal 15 / 18 / 27** | old dice averages | CLW 15, CSW 20–24, CCW 25–29 (flat) | `use-obj.c:483-545` (erratum already in the forum memo) |
| **Healing potions at the Temple** | 1.1.4–1.5.2 | Black market only in 1.5.3 (5ebfeb7) | V2/V3; shops memo |
| **Black market always has Healing/Speed/*ID*** | pre-2008 | removed 2008-03-29 | feda14a |
| **Connected stairs, persistent levels** | yes | yes, since 0.7.2a, unchanged. The `dungeon_stair` option is dead code | V1 |
| **Hounds cleared on arrival going down** | yes (2005-12) | yes, down-stairs and recall only | 46737ea; forum memo §1 **[code ✓]** |
| **Everyone starts with Word of Recall** | mages only before 1.4.0 | every class | `birth.c:904` **[code ✓]** |
| **Stacked wands/staffs** | separate | stack and share charges since 1.4.0 | V2 |
| **"Hounds and Q's breathe/cast too often"** (fixed in 1.1.4) | a 1.1.x bug | not present: 1.5 takes the monster's energy before it acts | `melee2.c:3476-3479` **[code ✓]** |
| **Store discounts copy on merge** (exploit) | 1.1.x | 1.5 gives store-bought enchants a 99% "discount" as an anti-exploit (f31fa7c) | V3 |

**For the Pilot, the main one:** all 2019-and-earlier timing advice predates the time bubble.
Resting and running in town or on an empty level run the whole local clock fast. That's why light
burns ~10× faster while resting in town (shops memo). A monster coming into view stops the
speed-up.

## 3. Rules of the live mangband.org server (News, rules thread t=1388, 2008–2012)

The rules never mention bots or automation. The word "bot" appears only for the IRC bot that relays
chat, levels, deaths and unique kills to the admins, who read the logs. **A bot playing on the live
server has to respect them**, and enforcement is by hand, up to deleting characters or banning:

1. When the ghost dies you start over; nothing is kept.
2. **Don't give items away, or under-sell them, between your own characters.** Multiple
   characters are allowed, but not interacting with each other. A team of bot characters trading
   items would break this.
3. **No power-levelling:** don't dive with a much higher or lower level character to give one a
   free ride.
4. Limited help to a dead character: up to 500 gold per character level above 25.
5. No swearing.
6. **Don't litter in town:** destroy junk with `k` rather than dropping it. The Pilot's
   `autodestroy` fits; dropping in town doesn't.
7. **Don't go AFK in shops** (one player per shop). The Pilot shouldn't idle, or "wait for
   restock", *inside* a store; wait outside.
8. **Don't save (log out) in the dungeon**, especially above 1000 ft, because the level stays
   static for others. **Recall to town before quitting.** The Pilot's "parking" logic should end in
   town.
9. No holding or storage characters; buy a house.

Also: player-killing is off, and taking another player's dropped loot is legal but frowned on.
Artifacts are removed from characters inactive for more than 60 days, and houses after 12 months
(logins count as activity). The rules and version in force *today* are unknown: News ends in 2020.
**Ask on the server's current channel (e.g. Discord) before running a bot there.**

## 4. Bugs and quirks relevant to us (Bug Reports, Technical Support; only 11 archived topics)

- **"See through closed doors / after a player swap" (#1303)** is fixed in v1.5.3 only (not
  1.5.0–1.5.2). If the Pilot ever connects to an older 1.5.x server, its view of doors and other
  players can be stale.
- **The party table has 256 slots** ("There aren't enough party slots!", `party.c:63-80`). This
  only matters if the Pilot creates parties.
- **The client can't fetch its character dump.** The Pilot can't rely on the dump file.
- Nothing else in the archived topics would trip an automated player. Most Bug Reports and
  Technical Support topics exist only on the live site (the ids are in
  `data/forum/tools/subforum_topics.json`), for a later fetch.

## 5. Recommendations

- **Navigator / HANDBOOK:**
  - treat forum monster facts from 2008 on as current (same monster file), but timing and
    retaliation advice from before 2019 as outdated (no time bubble then);
  - uniques come back on *death*.
- **Pilot, for the live server:** recall to town before logging out; never idle inside a store;
  destroy rather than drop junk in town; never pass items between our own characters; no party
  diving with a high-level character.
- **Before any live run:** confirm the live server's version and current rules with its admins.

## Coverage and gaps

- **Covered:** all 2753 commit subjects, with gameplay diffs opened where they mattered, and every
  release date checked against News.
- **Missing forum topics:** Bug Reports and Technical Support mostly weren't archived; fetch them
  live when mangband.org is up.
- **Not traced:** the 1.0.0-merge item, ego and artifact data files (only their diffstat).
- **Not tested:** V2's inference that per-character artifact preservation may be a no-op in 1.5.3.
