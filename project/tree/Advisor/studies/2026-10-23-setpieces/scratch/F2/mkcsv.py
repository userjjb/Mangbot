import csv,time
def ep(s): return time.mktime(time.strptime(s,'%Y-%m-%d %H:%M:%S'))
D='/projectnb/jbrcs/mangband/runs/pilot/dive04/'
R=[]
def add(m,a,b,depth,dump,summ,layer,right,fixed,ex,cost,evid):
    R.append([m,int(ep(a)),int(ep(b)),a[5:19]+'-'+b[11:19],depth,dump,summ,layer,right,fixed,ex,cost,evid])
H='20261016-'
add(20,'2026-10-16 23:49:07','2026-10-16 23:50:14',450,'20261016-234251-450ft.txt; 20261016-234918-500ft.txt; 20261016-234924-450ft.txt; 20261016-234953-500ft.txt; 20261016-235015-450ft.txt',
 "Twice in 70 s at full HP 'It points at you and curses.' (Novice priest in the dark, drawn as p 3 squares away) raised unseen_attacker; the flee took a > to 500 ft (past max_depth 450) and the Navigator hunt Novice_priest (23:49:54) was too late ('lost sight of it' 23:50:09). Curse cost 220->184 HP.",
 "Pilot rule (unseen_attacker classification; flee beat the hunt)","Treat a curse/spell from a weak caster visible on the map as news, not a flee; stay on the level and kill it (hunt) or ignore.",
 "2d0a2f2 (10-17 00:46)","Yes: m22 02:00:12 'It casts a fearful illusion: probably the Novice paladin in view; carrying on' and arrow cases 01:50:27, 01:52:57, 02:07:08","~65 s, 4 stair trips, 36 HP, 2 trips below max_depth; no consumables",
 "decisions.jsonl attention unseen_attacker 23:49:07, 23:49:42; goal_done 23:49:18, 23:49:52; goal_failed 23:50:09; report mission20 Pilot problem 1")
add(20,'2026-10-16 23:51:55','2026-10-16 23:52:05',450,'20261016-235015-450ft.txt',
 "20 s 'stuck' alert fired while the Pilot was picking a locked door ('You failed to pick the lock' x7); cleared the command queue and restarted the move although lock-picking was progressing.",
 "Pilot rule (stuck detector)","stuck must ignore lock-picking/digging (position unchanged but messages show progress).",
 "2d0a2f2","Not really: m23 22:18:26 had one failed pick, no alert (too short to test); m21 had 2 picks","~10 s; harmless but resets the move queue",
 "decisions.jsonl attention stuck 23:51:55; events message 'You failed to pick the lock' (14 in m20 window); report mission20 problem 2")
add(20,'2026-10-16 23:57:12','2026-10-16 23:58:16',450,'20261016-235015-450ft.txt',
 "Structure recogniser reported 'inner room 27,49 likely'; Navigator ordered searchroom 27,49: 26 s searching, 'searched every spot, nothing found'. The room's west door at 27,39 was already open (a normal room).",
 "Pilot perception (structure recogniser ignored an open door)","Before offering a searchroom, check the structure for a visible/open door; if open, it is a room: do not search.",
 "2d0a2f2 (room_door refusal, per-spot counts)","Partly: m21 01:21-01:23 searchroom ran (found a real secret door, a jelly nest); the open-door refusal itself has not triggered since","~26 s + ~45 s of Navigator turns",
 "decisions.jsonl attention structure 23:57:12; goal_failed 23:57:59; report mission20 'Recogniser'; next_steps.md:226-229")
add(20,'2026-10-17 00:04:59','2026-10-17 00:14:25',550,'20261017-000140-550ft.txt',
 "Pack full (23 slots) three times: no room for Clotted Red Potion (=Clumsiness), Leather Gloves [1] twice; the Pilot retried each pickup ('no effect seen: pick up'); Navigator destroyed Cutlass (34 gold), mushrooms, gloves, potions of water by hand.",
 "Pilot rule (pickup=all takes junk) + Navigator decision (junk kept)","Skip known-junk and bulky low-value pickups so slots stay free for devices/jewellery; destroy at once, not after a failed pickup.",
 "3152ce7 (flavour-junk skip); 767bf60 (bulky needs free slots)","Failed again: m21 5 pack_full incl. Wormtongue's hammer; m22 3; m23 pack 22/23 with water and mushrooms","~1.5 min of Navigator turns; ~37 gold of destroyed stuff",
 "decisions.jsonl attention pack_full 00:04:59, 00:12:01, 00:14:18; nav_cmd destroy 00:05:27, 00:12:11, 00:14:24; V1_value_events.csv m20")
add(20,'2026-10-16 23:42:06','2026-10-17 00:16:25',0,'',
 "Sale shortfall 128: Ring of Feather Falling sold unknown for 11 (known 50 an hour later), Infravision potion forced; Wand of Stinking Cloud (9 charges) 100 vs ~145, Staff of Object Location 50 vs ~92 (known flavour, unknown charges sells at bare kind cost), Rod of Trap Location 23 vs 25. Also Identify buy:2 bought 1.",
 "Navigator decision + Pilot rule (refusal does not cover known-flavour, unknown-charge devices)","Identify (81 gold) before selling any device/ring worth >150 known; the Pilot should refuse unknown-charge wands/staffs too.",
 "2d0a2f2 fixed the buy remainder only; the refusal gap is not fixed","Repeated: m21 Staff of Perception 136 short, m22 Staff Door/Stair 75, m23 Sleep Monsters 337, Rod of Light 152","128 gold (V1)",
 "V1_value_events.csv m20 rows; decisions.jsonl goal_done 23:42:06, 00:16:25; report mission20 'Navigator mistakes' and problem 5; memos/2026-10-23-scorecard.md section 3")
add(20,'2026-10-16 23:55:20','2026-10-17 00:05:40',450,'20261016-235015-450ft.txt; 20261017-000140-550ft.txt',
 "'You hear a door burst open' raised unseen_attacker five times (23:55:20, 00:03:12, 00:03:30, 00:03:34, 00:05:40); nothing to do each time. Same alert in m22 (8) and m23 (9) after the fix made them news.",
 "Pilot rule (alert noise to the Navigator)","Door bursts are a log line, not a Navigator wake-up.",
 "2d0a2f2 (news only)","Still present as attention records m22 x8, m23 x9; no flee seen from them","Navigator wake-ups only",
 "decisions.jsonl attention 'heard a door burst open' (counts m20 5, m21 0, m22 8, m23 9); report mission20 problem 6")
add(21,'2026-10-17 00:48:48','2026-10-17 00:58:18',0,'',
 "Server crashed at 00:48:48 on the Gauntlets buy (store[-1] segfault: the Pilot's town redraw had silently closed the store on the server). Pilot down 9.5 min; the rollback undid ~10 min of shopping (793 gold, old cap and shield back). Shopping redone 00:58-01:31.",
 "server/game mechanic (store[-1]) triggered by Pilot movement/redraw while shopping","Never send store commands outside a store; server refuses them.",
 "bb56313 (server) + f4082b0 (Pilot/client guards), 10-17","Yes: m21 01:05:20 guard replied 'not in a store'; m22 35 and m23 15 store events with no crash; m23 22:27:42 store_leave guard fired","590 s pilot_down; ~10 min of redone shopping",
 "pilot.log 00:48:48 'client exited: Connection closed'; 00:58:18 restart; events error 01:05:20 'not in a store'; T1_time_budget.csv m21 pilot_down 590; next_steps.md:236-240")
add(21,'2026-10-17 01:04:57','2026-10-17 01:05:39',700,'20261017-010501-700ft.txt',
 "Planned Pilot park/restart on a fresh 700 ft level: after login 'Standing on: floor/unknown' on the stair it arrived on, no stairs known; Navigator re-issued use/explore after ~40 s.",
 "Pilot perception (state lost over a restart)","Persist or re-derive 'standing on' after login; do not restart mid-dive.",
 "3152ce7 ('Standing on' explains unknown after login)","Not in the dungeon since (restarts were in town)","~40 s",
 "decisions.jsonl attention parked 01:04:57, started 01:05:01; report mission21 problem 2")
add(21,'2026-10-17 01:09:15','2026-10-17 01:10:21',700,'20261017-010501-700ft.txt',
 "Wormtongue + ~10 White wolves in the open: HP 233->160 (69%, mission low). Wormtongue slain 01:09:37 during explore (no unique/danger event). His Lucerne Hammer: 'no room' 01:09:51, 'effect_failed' retry, Navigator destroyed a Potion of Water, picked up 01:10:21 (~30 s with wolves around).",
 "Pilot rule (pack full of junk at the moment of a unique drop) + Navigator decision","Keep 2 slots free at all times; free a slot before fighting a unique; unique drop always taken.",
 "3152ce7 (unique_slain event); 767bf60 (bulky needs slots)","Worked in m22 (Orfax unique_slain 01:48:14); m23 Brodda drop was lost (see 23.3)","73 HP; ~30 s; no loss",
 "events messages 01:09:15-01:09:58; decisions attention pack_full 01:09:51; report mission21 problem 4")
add(21,'2026-10-17 01:18:42','2026-10-17 01:20:54',700,'20261017-010501-700ft.txt',
 "Brigand stole a Hard Studded Leather [7] {excellent} (really of Resistance [7,+9], worth ~4x); Pilot did not chase; Navigator ordered hunt Brigand 01:19:52 (reply 'lost sight of it' although slain); armour recovered 01:20:54 after freeing a slot (destroyed a junk scroll and a Robe).",
 "Pilot rule (no thief response)","Hit the thief first and chase a stealer for 5-10 s; free a slot before picking up the recovered item.",
 "3152ce7 (dungeon thief event, thief-first hits, hunt kill detection)","thief event fired m22 (01:48:05 hobbit, 02:08:36 Brigand), both hunts again ended 'lost sight of it'; no theft occurred, so recovery untested","2.2 min; 0 gold lost (recovered); high potential loss (~800)",
 "decisions.jsonl attention lost 01:18:42; nav_cmd hunt Brigand 01:19:52; goal_failed 01:20:07; V1 e_stolen_item")
add(21,'2026-10-17 01:21:15','2026-10-17 01:21:15',700,'20261017-010501-700ft.txt',
 "Navigator destroyed its old Hard Studded Leather [7] {average} (worth ~78 sold) after judging 'sells ~10'; earlier 01:20:52 destroyed a Robe and a Summon Undead scroll. User asked what was destroyed (01:27:07) and remarked a Flask of oil could have refuelled instead (01:25:32).",
 "Navigator information (value guess) / doctrine","Sell, not destroy, any armour (cost 200 x 0.39); the Pilot could show a sale value in the destroy reply.",
 "none","n/a","78 gold","V1_value_events.csv m21 01:21:15; nav_say 01:27:13; user_note 01:25:32")
add(21,'2026-10-17 01:27:30','2026-10-17 01:27:55',700,'20261017-010501-700ft.txt',
 "Unseen 'It stares deep into your eyes!' (Illusionist HOLD) at full HP: Pilot fled toward a > 17 squares away (past max_depth); Navigator recalled 6 min early 'no Free Action'. BUT the log says 'You are unaffected!' twice: the server prints that only when free_act is set (melee2.c:1445-1448); the unidentified {excellent} Soft Leather Boots worn were Boots of Free Action [2,+4].",
 "Navigator information (wrongly believed no FA) -> doctrine; Pilot perception (does not learn FA from 'You are unaffected')","Treat 'You are unaffected!' to a hold/slow spell as proof of Free Action; identify {excellent} items worn long-term; no early recall needed.",
 "3152ce7 added a 'paralysis hint on unseen gazes without FA' (built on the false premise)","No: the same FA boots were worn through m22 (Orfax and Boldor SLOW 'unaffected' 01:48:06, 02:05:46-58) and swapped out unknowingly 22:25:13 in m23","6 min of mission time; no HP",
 "events message 01:27:30-31 'You are unaffected!'; src/server/melee2.c:1436-1462 (HOLD) and 1416-1428 (SLOW); xtra1.c:2319; events.jsonl first 'Soft Leather Boots [2] {excellent}' worn before 10-09; nav journal 01:27:44 (navigator.md:344)")
add(21,'2026-10-17 01:28:08','2026-10-17 01:29:52',0,'',
 "Staff of Perception used in town twice without a target: identified the Flask of oil both times (2 charges, bought an Identify); later the staff was force-sold for 160 (fair 296, 136 short). Hammer of Venom sold forced for 1707 (fair, no loss).",
 "Pilot movement/UI (use has no TARGET) + Navigator decision (forced sale)","use staff must take a target (or read Identify); do not force-sell known-flavour devices.",
 "3152ce7 (use L TARGET)","Not exercised since (m22 and m23 report 'didn't come up')","136 gold + 2 charges + ~1.5 min",
 "decisions.jsonl nav_cmd use 01:28:07, 01:28:22, complain 01:28:31; V1 m21 01:29:52; report mission21 'What I lacked'")
add(21,'2026-10-17 01:31:37','2026-10-17 01:35:30',0,'',
 "townfarm walks instead of running; user: 'Still minimal running during townfarm, much less time efficient' (01:33:10) then 'You can call the mission' (01:35:30). Gain +83 gold in 1.5 min.",
 "Pilot movement (townfarm walk)","townfarm should run on clear ground; the Navigator has no control.",
 "3152ce7 ('surface runs start with townspeople within 2')","Unclear: m23 townfarm 678->933 and 2400 attempt; user did not repeat the complaint before ending","~4 min of low-yield town time; the user ended the mission",
 "decisions.jsonl user_note 01:33:10, 01:35:30; complaint 01:33:18")
add(22,'2026-10-17 01:48:05','2026-10-17 01:48:58',700,'20261017-014630-700ft.txt',
 "Orfax's lair: 'It magically summons help' (Orfax, confuses), Orfax slain 01:48:14 but 13 Brown + 3 Blue yeeks swarmed: HP 233->103 (44%) in 20 s, 3 Phase + 2 CSW + 1 CLW, emergency_loop at 01:48:34 with no stairs known; fought through. Interesting items (rings, wands, staff) listed during the fight.",
 "game mechanic (summoner unique) + Pilot rule (fought on instead of leaving)","On the first 'summons help' with 10+ monsters appearing and no stairs, read WoR then, not after three emergencies.",
 "767bf60 (band event 5+ monsters; news only)","Band event fired in m23 (wolves, orcs) but is news, not an action","130 HP, 3 Phase, 2 CSW, 1 CLW",
 "decisions.jsonl attention 01:48:08-01:48:58; T1_close_calls.csv m22 01:48:34; messages 01:48:05-01:48:35")
add(22,'2026-10-17 01:50:27','2026-10-17 01:54:49',700,'20261017-014630-700ft.txt',
 "Loot room (14+ items) while an orc band assembled: Kobold archers shooting, Snaga x3, Uruk x2, Black orc, Hill orc, Large kobold, Tengu. 01:50:41 'no room' for Wand of Slow Monster; Navigator destroyed a Rod of Trap Location mid-fight (01:50:46, HP 160); fight_going_badly from 01:50:47; flee (unseen arrow) interrupted hunt Uruk 01:54:29; then 6 Phase in 14 s, 4 CCW, 3 CLW; HP lowest 61/241 (25%, the mission-17-23 minimum); WoR 01:54:44, Teleportation 01:54:46 (Navigator), yanked 01:54:49. Left on the floor: Wand of Slow Monster, Staff of Perception, Rings of Resist Fire/Slow Digestion/Resist Cold (~990 gold).",
 "Pilot rule (loots/explores while a band forms; Phase burn) + Navigator decision (fought on 4 min; pack chores mid-fight)","Leave at the first band alert (01:50:46 'can deal 108, phased away'): read WoR at HP 140/241, or fetch only the 3-4 best items first; do not do pack chores mid-fight.",
 "767bf60 (band event; recall after 3 Phase in 20 s; bulky-needs-slots)","Partly: 'band' fired m23 22:20:57 and 22:26:18 but the Pilot still looted (see 23.5); the 3-Phase rule was not triggered in m23 (1 Phase)","6 Phase + 4 CCW + 3 CLW + Teleportation; ~990 gold of loot abandoned; 25% HP",
 "decisions.jsonl emergency 01:54:30-01:54:47 (17), act read Teleportation 01:54:46; T1_close_calls.csv m22 01:54:44; V1 m22 c_abandoned rows; reports mission22 'What happened'")
add(22,'2026-10-17 02:00:08','2026-10-17 02:00:38',700,'20261017-015600-700ft.txt',
 "7-8 Novice paladins (fear/curse casters) + 2 White wolves: afraid (cannot melee), HP 241->79 (31%); Pilot phased, quaffed CCW, Navigator Heroism 02:00:17; group-danger WoR 02:00:19 (flee: no known path to stairs); yanked 02:00:38 (19 s).",
 "game mechanic + Pilot rule (correctly escalated; late)","Heroism/Boldness before engaging; WoR as soon as 'group danger' fired; phase away from the pack, not into it.",
 "767bf60 (band event)","Band event worked twice in m23","3 Phase + 2 CCW + 1 CSW + Heroism + 1 WoR; 31% HP",
 "decisions.jsonl emergency 02:00:16-02:00:42; T1_close_calls.csv m22 02:00:21")
add(22,'2026-10-17 02:00:38','2026-10-17 02:00:47',0,'',
 "Arrived in town at HP 99/251: the emergency rule fired against a harmless Singing happy drunk ('begs you for money'): 2 Phase Doors and 1 CLW wasted.",
 "Pilot rule (emergency ignores monster danger in town)","Town + low HP + no hostile in view: rest, no Phase.",
 "none","Not seen again (m23 recalls arrived with HP 147 and rested)","2 Phase + 1 CLW (~70 gold)",
 "events message 02:00:40 'The Singing, happy drunk begs you for money.' 'You have 6 Scrolls of Phase Door'; 02:00:43 '5'; decisions.jsonl emergency 02:00:39, 02:00:42")
add(22,'2026-10-17 02:05:46','2026-10-17 02:06:04',650,'20261017-020153-650ft.txt',
 "Boldor (fast, summons kin, blinds) with 12+ Master/Brown yeeks, Pseudo-dragon, Druid: flee goal failed 'stuck on the way to the stairs' 02:05:52; WoR read 02:05:52; Navigator ordered hunt Boldor 02:05:55 (the yeek swarm followed); HP 241->120 (50%) in 15 s; 2 Phase, CCW, 2 CLW, CSW, Boldness; yanked 02:06:04.",
 "Navigator decision (hunt a rated-4 summoner) + Pilot movement (flee stuck in a crowd)","Do not hunt; keep the flee/WoR; flee path must treat crowding monsters as passable-by-fighting or read WoR at once.",
 "767bf60 (ordered hunts kept 120 s -- the opposite of what was needed here; paths round traps)","Flee-stuck again m23 22:26:46 (Orc captain); hunt-vs-flee precedence not exercised in m23","50% HP; 2 Phase, 1 CCW, 2 CLW, 1 CSW, 1 Boldness, 1 WoR",
 "decisions.jsonl goal_failed 02:05:52, emergency 02:05:52; nav_cmd hunt 02:05:55; T1_close_calls.csv m22 02:06:03; report mission22 'Navigator's mistakes'")
add(22,'2026-10-17 02:09:32','2026-10-17 02:10:01',650,'20261017-020656-650ft.txt',
 "Three traps in 30 s while exploring: dart (STR drained, Restore Strength {90% off} used), pit, dart (CON drained; no Restore CON ~483, CON stayed 17). The Navigator had destroyed a Rod of Trap Location (01:50:46) and an Elm Staff (= Trap Location, 02:03:20) earlier.",
 "game mechanic (hidden traps) + Navigator decision (destroyed Trap Location devices); Pilot movement (explore walks into traps)","Keep the Rod of Trap Location (33 gold, one slot); read/zap it on arrival at trap-laden levels; leave a level at the 3rd trap.",
 "767bf60 (paths round known traps; 3 traps sprung -> news)","Not exercised in m23","STR restored (a potion); permanent CON drain (~483 to fix); ~15 HP",
 "events messages 02:09:32, 02:09:59, 02:10:01; decisions attention stat_drained 02:09:32, 02:10:01; V1 m22 b_destroy Rod of Trap Location, Elm Staff")
add(22,'2026-10-17 02:11:34','2026-10-17 02:12:25',700,'20261017-020656-650ft.txt; 20261017-021219-700ft.txt; 20261017-021221-650ft.txt; 20261017-021223-700ft.txt',
 "'It magically summons help' (Gnome mage) -> Hill orc x11 + White wolf + Zombified human/orc: 6 Phase + 2 CCW + CLW + CSW, Phase stock hit 0 at 02:12:18; Navigator WoR read only 02:12:11; HP lowest 88/236 (37%); a CCW destroyed by fire (120 gold); Pilot took the stairs underfoot 5x (02:12:18-22: > < > < >) while WoR charged; yanked 02:12:25.",
 "Pilot rule (Phase burn; late WoR) + Navigator decision (WoR read after the Phase was gone)","Read WoR at the first summons with 'no stairs known' (02:11:34); stairs-hopping while WoR charges is sound but costs nothing only because no monster followed.",
 "767bf60 (after 3 Phase in 20 s: WoR, phase only below 20%)","Not triggered in m23 (1 Phase in 120 HP)","Phase stock 0, 3 consumables types, 120 gold potion; 37% HP",
 "decisions.jsonl emergency 02:11:53-02:12:21; messages 02:12:08-02:12:25; T1_close_calls.csv m22 02:12:17")
add(22,'2026-10-17 02:12:33','2026-10-17 02:14:30',0,'',
 "Identify by letter after a pack re-sort hit the same Bloodstone Ring twice; the Navigator wore an unidentified cursed Ring of Protection, bought Remove Curse (119) and wasted an Identify (~61); the uncursed ring then would not sell.",
 "Navigator decision + Pilot UI (letters shift after identify; equipment letters)","Identify one item per call and re-read the pack; wear only identified jewellery.",
 "767bf60 (twin-stack identify, equipment letters A,B..)","Not exercised in m23 (report: 'twin-stack identify: didn't come up')","180 gold (V1 d_forced_other)",
 "nav_cmd 02:12:33-02:14:19; V1 m22 d_forced_other; report mission22 problem 5-6")
add(22,'2026-10-17 01:48:22','2026-10-17 02:03:20',700,'20261017-014630-700ft.txt; 20261017-015600-700ft.txt; 20261017-020153-650ft.txt',
 "Junk filling the pack while valuables stayed on the floor: Short Bow, Metal Cap, Awl-Pike, Flail (value ~124, unmarked), Hard Leather Boots, Long Bow, Dagger, Elm Staff, spare Lantern picked up and later destroyed; Rings of Resist Fire/Cold/Slow Digestion, Wand of Light/Wonder seen, never picked up. Scorecard: loot abandoned 988, destroyed with value 270.",
 "Pilot rule (pickup=all) + Navigator decision","Pickup list = devices, jewellery, ego/good armour, potions/scrolls of value; skip plain weapons and caps; Navigator fetches named valuables on the interesting_item alert.",
 "767bf60 (bulky gear needs 6+ free slots unless {good}/ego); 3152ce7 (flavour junk)","m23: pack hit 22/23 slots on mushrooms, water, spare staffs/rods (no weapon junk); bulky rule fired once and cost Brodda's Scimitar","~1260 gold equivalent",
 "V1_value_events.csv m22 rows; decisions.jsonl pack_full 02:03:11, 02:07:27; report mission22 Pilot problem 4")
add(23,'2026-10-22 22:15:22','2026-10-22 22:15:55',0,'',
 "Starting gold on the ground beside the character in town: 'goto item' did nothing; the Pilot's own pickup took part; seven goto orders needed (19+20+22+30+36+31+19 = 177 gold) ~33 s; user note 22:18:54 'Pilot skipped money on the ground'.",
 "Pilot movement/perception (gold squares not targeted; goto item resolves to nothing)","goto item/gold should resolve to the nearest visible '$' and the Pilot should collect all visible gold within 3 squares.",
 "none (freeze 10-22, next_steps.md:267)","n/a","~33 s; 0 loss",
 "decisions.jsonl goal goto item 22:15:22; events messages 22:15:22-22:15:48 'You have found N gold'; report mission23 'What happened'")
add(23,'2026-10-22 22:16:00','2026-10-22 22:16:03',0,'',
 "Pilot refused ('NOT sold (it's Staff of Sleep Monsters: worth more known, use or Identify it; sell !NAME to force)'); Navigator forced `sell !Golden_Staff` the same second: 26 gold vs ~363 fair (shortfall 337). User asked twice why.",
 "Navigator decision (forced over a Pilot refusal) + doctrine","Use the staff (id charges) or Identify (~85), then sell known: ~363; never `!` a refused device without a quote.",
 "none","n/a (last mission)","337 gold",
 "decisions.jsonl goal_done 22:15:57, nav_cmd 22:16:00; V1 m23 22:16:00; user_note 22:16:44, 22:17:06")
add(23,'2026-10-22 22:24:44','2026-10-22 22:26:09',650,'20261022-221759-650ft.txt; 20261022-222554-600ft.txt',
 "Brodda slain 22:24:44; his Scimitar (2d5) {Brodda, the Easterling} was skipped by the bulky rule ('left a Scimitar... pack nearly full' 22:24:49) because the exemption regex covers {good|excellent|special} and 'of X' egos but not the {Unique name} drop tag (pilot.py:2187-2189). Navigator issued goto 49,162/161 (took the boots) and never used `pickup`; at 22:25:44 an unseen light-breather ('It breathes light') made the Pilot flee up '<' at 234/236 HP; the Scimitar stayed on a level that no longer exists.",
 "Pilot rule (bulky filter misses unique drops) + Navigator decision (did not `pickup`) + Pilot rule (unseen-attacker flee at 99% HP)","Pick up any item tagged {Unique name}: free a slot (destroy water/mushroom) and pickup at 22:24:49; flee only if HP is threatened.",
 "none (767bf60's bulky rule introduced it)","n/a (this exercise of the rule is the failure)","~262 gold (low confidence; floor ~88); user: 'very stupid'",
 "events messages 22:24:44-22:25:53; decisions.jsonl attention 22:24:49, 22:25:44; pilot.py:2183-2194; V1 m23 22:24:49")
add(23,'2026-10-22 22:25:54','2026-10-22 22:26:09',600,'20261022-222554-600ft.txt',
 "Navigator replied 'Agreed, going back for it now' at 22:25:54 although the level had changed at 22:25:53 and ordered goto 49,162 on the new 600 ft level ('no known path'); a second unseen flee (mesmerising illusion 22:26:04) took '>' down; at 22:26:09 Navigator wrote 'Too late'.",
 "Navigator information (no level-change notice) + Pilot rule (flee not abortable by a goto)","The status/alert should say 'new level: items left behind are gone'; the Navigator should have known stairs regenerate levels.",
 "none","n/a","15 s; the loss is in 23.3",
 "nav_cmd say 22:25:54; events LEVEL 22:25:53, 22:26:06; decisions attention 22:26:00 'goto: no known path')")
add(23,'2026-10-22 22:26:06','2026-10-22 22:26:58',650,'20261022-222608-650ft.txt',
 "Arrived beside an orc mob in a corridor (Cave orc x2, Half-orc, Black orc x3, Uruk): first wave killed (HP 236->188). 'band' fired 22:26:18 ('leave now... stairs 15 away; don't stop for loot'); Navigator only polled status (22:26:18, :33, :43); the Pilot rested, then walked 13 squares east to pick up an Amulet of Resist Acid and a Rod (22:26:32, :38) toward the second wave: Orc captain, shamans x5, Novice paladin; flee 'stuck on the way to the stairs' 22:26:46 -> WoR; Navigator 'goto < force' 22:26:49 (shell typo first) 'stuck' in 3 s; HP lowest 120/254 (47%); 1 Phase + 1 CLW; yanked 22:26:58.",
 "Pilot rule (loot during band) + Pilot movement (flee/goto stuck when blocked) + Navigator decision (no order for 25 s)","On 'band' with stairs 15 away: walk to the stairs (not the loot) while HP 230; or WoR at 22:26:18 instead of 22:26:46.",
 "767bf60 (band event) fired correctly; nothing acts on it","n/a (last mission)","HP low 120/254 (47%); 1 Phase, 1 CLW, 1 WoR; gained Amulet of Resist Acid (sold 111) and a Rod of Light",
 "mons records 22:26:15-22:26:57; decisions.jsonl attention band 22:26:18, goal_failed 22:26:46, 22:26:52; nav_cmd 22:26:18-22:26:49; T1_close_calls.csv m23 22:26:55")
add(23,'2026-10-22 22:27:36','2026-10-22 22:30:12',0,'',
 "Clearing pack slots, the Navigator force-sold the {excellent} Soft Leather Boots after the Pilot's refusal ('probably special, inspect it first'); they were Boots of Free Action [2,+4]: 3 gold at Darg-Low (shop re-lists 2265). Also force-sold a Rod of Light for 33 (fair 185). The boots had been replaced by Brodda's Metal Shod Boots [6] at 22:25:13 without identifying them, so the character lost Free Action unknowingly. User: 'very stupid' (22:27:00), 'hopeless with dealing with items' (22:29:09), 'you're fired' (22:30:06): mission ended early.",
 "Navigator decision (forced sale over the Pilot warning) + doctrine (HANDBOOK 'sell !NAME') + Pilot rule (no ego peek)","Wear/identify {excellent} before swapping; quote Darg-Low's offer first; never force-sell {excellent}/{special}.",
 "none","n/a (last mission)","546 gold shortfall + irreplaceable FA + 152 on the rod; user ended the mission",
 "decisions.jsonl goal_done 22:27:36 (refusal), 22:27:58 (sold); events messages 22:27:58; V1 m23 a_sale_SHORT_irreplaceable; navigator.md:390")
add(23,'2026-10-22 22:20:27','2026-10-22 22:27:44',650,'20261022-221759-650ft.txt',
 "Pack at 22/23 slots with water, mushrooms, spare boots, extra staffs and rods; Pilot left a Metal Cap [3] (bulky rule) and the Scimitar; Navigator had no free-slot count (user: 'Serious work needs to be applied to managing a nearly full inventory').",
 "Navigator information (no slot count) + Pilot rule (junk pickups)","Report free slots; destroy water/mushrooms on pickup; keep 4+ free.",
 "none (compact report omitted the count)","n/a","Metal Cap ~12 gold + contributes to 23.3",
 "decisions.jsonl attention 22:20:27; user_note 22:27:24; report mission23 'What I lacked'")
with open('/projectnb/jbrcs/mangband/Advisor/studies/2026-10-23-setpieces/scratch/F2/F2_incidents.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow('mission,start_epoch,end_epoch,local_time,depth_ft,map_dump,summary,layer,right_behaviour,fixed_by,exercised_later,cost,evidence'.split(','))
    w.writerows(R)
print(len(R))
