# Restructure step 2: who decides what (design, 2026-10-23)

Step 2 of the restructure (`restructure.md`; the Advisor's `memos/2026-10-19-starting-over.md` §3.4). Status:
**design agreed with the user on 2026-10-23** (decisions in §6); building in the order of §5.

## 1. What the logs say (missions 17-23, `nav_cmd` records)

The Navigator issued **288 goals and ~140 item commands**; almost none of it was strategy:

| kind | count | examples |
|---|---|---|
| shop trips | 104 | `shop 5 buy ...`, `shop 2 sell !Soft_Leather_Boots:1` |
| goto (mostly loot) | 84 | `goto 33,122` seven times to pick up gold |
| item commands | ~140 | destroy 39, read 37 (identify), wear/takeoff 27, inspect 9, fuel 8, use 7, quaff 5 |
| explore / dive / recall | 71 | the trips themselves |
| hunt | 15 | Ranger, Boldor (both wrong), frogs (right) |
| strategy (`max_depth`, posture orders) | 18 | |

And every costly incident was a micro decision the Navigator made against a rule or a warning:

| incident | mission | decided by | should be |
|---|---|---|---|
| Boots of Free Action sold for 3 (fair 549; irreplaceable) | m23 | Navigator, `sell !` over the Pilot's refusal | Pilot policy: never sell unknown {excellent}; no override |
| Brodda's Scimitar left, then lost to a flee | m23 | Pilot rule (bulky pickup) | Pilot policy: a unique's drop always taken |
| Trident {good} (+3,+7) sold unidentified for 42 | m16 | Navigator | Pilot policy: identify {good} gear before selling |
| Lucerne Hammer of Venom sold (~63/round vs 32) | m21 | Navigator | Pilot policy: wield the better weapon, brands counted |
| 14 CLW destroyed by `destroy Light all` | m16 | Navigator | Pilot policy: destroy only junk |
| cursed ring worn via a stale letter | m22 | Navigator | Pilot policy: identify, then wear upgrades |
| hunted a Ranger (220 → 67) / Boldor | m19, m22 | Navigator | Pilot check: refuse a hunt the danger rule rates fatal |
| looted Orfax's room while a band gathered | m22 | Navigator gotos | Pilot policy: no loot detours with a band in view |
| Phase Door ×10 in 20 s, twice | m22 | Pilot rule | fixed (recall after futile phasing) |

The Navigator's judgement was good where only it can judge: talking with the user, choosing depths, ending a trip,
reading a strange situation. It was poor where a rule computed from data would do: item value, which fight to take.

## 2. The split

**The Pilot owns everything tactical and every irreversible value decision, by policy computed from data** (the
rulebook: shopmath, kind values, the danger table, the progression model; the Advisor's tables replace the interim
ones in step 3):
- **Items:** pick up, destroy, identify (read Identify, use Perception), wear/wield upgrades (AC, brands, blows),
  fuel, eat, sell. Every sale is valued first (fair pay vs what an identified sale would bring); unknown {good}/
  {excellent}/ego/charges are identified before selling when the gain beats the scroll; irreplaceable items (Free
  Action, See Invisible, resists, speed) are never sold or destroyed.
- **Fights:** which to take, flee, escape, rest, cure (as now), and *loot only when it's safe* (no band, no danger
  in view).
- **Movement inside a plan:** where to explore, which stairs, picking up gold.

**The Navigator owns the plan and the exceptions:**
- **Trips:** where to go and when to come back, as an intent with conditions (§3).
- **Town:** what to buy beyond the standing kit (upgrades, Restore STR, the Free Action fund), with price caps.
- **Posture:** standing orders (`max_depth`, how cautious), avoid zones, "leave this level now", "recall now".
- **Exceptions:** hunt a particular monster, fetch a particular item, keep an item the policy would sell.
- **The user:** answering, and relaying the user's instructions into orders.

**Asymmetric authority** (the rule that settles conflicts): the Navigator may always order something *safer*
(leave, recall, rest, stop, avoid, keep). Something *riskier* or *irreversible* (hunt, go deeper, a loot detour,
selling or destroying) is checked by the Pilot against the policy; a refusal says why and what would allow it.
**Overrides and the Navigator's debt** (the user's decision): the Navigator may still override a value refusal (in
town), but every gold piece of value it wastes is added to its **debt**: the fair value lost on sales and destroys it
made against a refusal, and the shortfall on its own item decisions. It is told its debt at the start of every mission,
with a notice that past a limit it isn't told, its freedom to sell and destroy is taken away (then the Pilot's policy
is final). The limit lives with the Architect, not in anything the Navigator is pointed at.

## 3. The interface: intents with conditions

```
plan trip 600-700 until "cures<4 or phase<5 or wor<2 or time>22:40 or band" then recall
plan town kit=B buy "Restore_Strength@500, Ring_of_Free_Action@3000"
leave            # this level, now (stairs or a fresh level)        -- always allowed
recall           # home now                                          -- always allowed
hunt NAME        # checked: refused if the danger rule rates it fatal for us
fetch Y,X        # one item detour, checked: refused with a band in view
keep NAME        # never sell/destroy it
avoid ...        # as now
order max_depth=... / caution=...
```

- **The Pilot runs the plan**: recall down (or the stairs), explore, fight, loot, leave bad levels (band, trap-laden,
  drainers, breeders), dive within the range, and recall home when a condition holds, then **runs the town kit**:
  sell by policy, identify what's worth it, buy the kit's stock levels (stage B: CCW 4, CSW 4, Phase 10, WoR 2, food,
  flasks) and the buy list, rest, wait in town.
- **Every order carries the report it answers** (`after_report`, logged since step 1); the Pilot holds an order whose
  premise is gone (the 17-s-old Brodda `goto`), saying so.
- **Reports gain a belief state** (the Advisor's table): monsters seen recently but now out of view, the plan and its
  next step, attempt counts, HP-loss rate, damage dealt per monster, the user's standing instructions.

## 4. The Navigator's toolset

Kept everywhere: `wait`, `status`, `pack`, `equip`, `map`, `monster`, `drainers`, `gate`, `journal`, `say`,
`complain`, and the intents above. **Item commands are refused in the dungeon and allowed in town between trips**
(the user's hybrid): `sell`/`shop ... sell`, `destroy`, `drop`, `read`, `quaff`, `use`, `zap`, `aim`, `wear`,
`takeoff`, `fuel`, `eat`, `pickup`; in the dungeon the Pilot does all of it by policy. `goto`, `raw` and `stairs` go
from the Navigator altogether (`fetch`, `leave` replace them). Everything stays in pilotctl for the Architect and the
harness. The HANDBOOK shrinks to the judgement calls (~100 lines).

## 5. Build order

1. **Item policy** (Pilot): value every item (fair pay, identified value, irreplaceable flag); pickup (unique drops
   always; by value per slot when the pack is full); destroy junk; identify when it pays; wear upgrades; sell in town
   by policy. Value refusals without `!`.
2. **Town kit** (`plan town`): sell, identify, restock to the kit, buy list, Restore stats.
3. **Trip plan** (`plan trip ... until ... then recall`) with the level-leaving rules.
4. **Order checks**: hunt and fetch vetted, stale orders held, `after_report` premise check.
5. **Belief state** in the report.
6. **The new toolset**, the short HANDBOOK and navigator.md.
7. **A short supervised mission**, scorecard against the m17-23 baseline.

Each step is tested offline first (stub states for now; the Advisor's set-pieces as they come, step 4 of the
restructure).

## 6. Decisions (the user, 2026-10-23)

- **Overrides:** the Navigator keeps them (in town), with a tracked **debt** of the value it wastes, told at the start
  of each mission; past a hidden limit its sell/destroy freedom is removed. (Instead of "only the user" or "nothing".)
- **Item commands:** refused in the dungeon, allowed between trips in town. (Instead of removed entirely.)
- **Build order:** as in §5.
