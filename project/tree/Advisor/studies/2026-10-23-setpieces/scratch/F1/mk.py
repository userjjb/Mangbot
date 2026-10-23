import csv,datetime
def ep(d,t): return datetime.datetime.strptime('2026-'+d+' '+t,'%Y-%m-%d %H:%M:%S').timestamp()
R=[]
def add(m,d,s,e,depth,dump,summ,layer,right,fixed,ex,cost,evid):
    R.append([m,int(ep(d,s)),int(ep(d,e)),f"2026-{d} {s}-{e} EDT",depth,dump,summ,layer,right,fixed,ex,cost,evid])
D='decisions.jsonl'
# ---------- m15 (10-07)
add('m15','10-07','22:42:38','22:59:25',0,'none',
 "Start: 17 min of scripted user message-test in town. Stuck alert at 22:42:38 (townfarm 'gone nowhere for 2 minutes'); Navigator saw the user's 22:38 message only at 22:42 (4 min late).",
 'Navigator information (late message) / Pilot rule (stale townfarm)','Report unanswered user messages at once (done); restart the stale goal.',
 '2765956 (unanswered user messages on the report 2nd line); 7c16bc5 (stuck watchdog counts from goal start)','yes: no late-message complaint in m16-m19 (user sent none in m17-19)',
 '~4 min delay; no HP/gold; REPEAT: low',"decisions.jsonl 22:42:38 stuck; nav_say 22:42:45 'saw your 22:38 message late'")
add('m15','10-07','22:47:58','22:51:20',0,'none',
 "Townfarm: thieves took gold twice ('purse lighter' 22:47:58 = 57 gold per Navigator, again 22:51:20) and a CLW at 23:04:40; Pilot walked/farmed on with auto-retaliate only.",
 'Pilot rule (townfarm ignores EAT_GOLD/EAT_ITEM touchers)','Attack a thief on sight / first, before it touches (Filthy urchin, Squint-eyed rogue, Scruffy hobbit).',
 '56aaa1e (townfarm attacks thieves within 8); 506c4f1 (adjacent thief hit); 7e4f058 (hit really runs); 7bb2edd (clear stale hits, item thieves first); 3152ce7 (dungeon thief event)',
 'partly: thefts still got through m17 14:00:19/23 (57 g, before fixes), m18 19:18:37 (67 g), m19 22:47:38 (Phase Door); none in m20-23 per V1',
 '~120 g in m15 (navigator-decisions memo §4); m17-19 total 166+211+6 g incl. dungeon thefts; REPEAT: yes (~1/mission day townfarm)',"decisions.jsonl lost 22:47:58, 22:51:20, 23:04:40; V1_value_events.csv e_stolen_*")
add('m15','10-07','23:00:35','23:17:32',450,'none',
 "On arrival at 450 ft the dive goal meleed a Red jelly 'blocking the way' (tactic 23:00:35): STR 18/50 -> 18/30, blows 4 -> 3 (stat_drained 23:00:35 and :38). Played 17 min on 3 blows until Restore STR (468 g) was bought at 23:17.",
 'Pilot rule (melee against a stationary drainer)','Never melee a NEVER_MOVE drainer (Red jelly STR, Rot jelly CHR, Purple patch CON); route round it or leave.',
 '2765956 (no melee vs stationary drainers); 7d608cb (drains read from blows, never stood beside); 4d20a7c (goals inside drainer zone dropped)',
 'partly: failed again in m16 (Rot jelly CHR 15:46, Purple patch CON x2 15:50, 8 h after 2765956); not seen m17-m20 (frog event 00:09 and ant event 10-22 22:19 killed drainers with no further drain). m22 02:09 STR+CON drained (outside this brief)',
 'Restore STR 468 g, 17 min at 3 blows; REPEAT: low now',"decisions.jsonl attention tactic 23:00:35, stat_drained 23:00:35/:38, blows_changed 23:17:32; navigator-decisions memo §2")
add('m15','10-07','23:02:35','23:03:08',450,'none',
 "Brodda adjacent at first sight after WoR arrival, no stairs known: HP 151 -> 27 in ~13 s; flee_failed ignored listed-only monsters; last WoR read at 27 HP; Brodda fled in terror. ALREADY ANALYSED: memos/to_architect/2026-10-08-missions15-16-replay.md §1.",
 'Pilot rule (thresholds, flee_failed monster set) + doctrine (WoR arrival with no escape)','Read WoR at once when a rated-4 monster is adjacent with no stairs; Phase when HP < 2x its worst round; refuse Navigator goto.',
 '4d20a7c (flee_failed counts listed-only; 2.5x worst-round emergency; goto held beside danger)',
 'partly: m17 14:11:42 Brodda again at 600 ft; Pilot took > 2 squares away itself (HP 176 -> 153). The goto hold itself has never fired ("goto held" 0 in all logs)',
 'HP low 26/151 (17%), 1 WoR, 1 CCW+CSW+CLW, 0 gold; REPEAT: yes (arrival next to a unique)',"decisions.jsonl 23:02:35-23:02:53; prior memo E1")
add('m15','10-07','23:08:21','23:10:32',300,'none',
 "Invisible 'It touches you' (300 ft and 400 ft): ration eaten with no news (2 -> 1), WIS drained 23:10:04; flee up one level at 23:08:32.",
 'Pilot perception (invisible eater; no `lost` news for eaten food)','Treat as food loss; kill or leave; report \"was eaten\".',
 '7bb2edd ("was eaten!" is lost news)','yes: m19 22:16:02-04 ate 3 food items and was reported',
 '1 ration, 1 level; REPEAT: yes (same class m19)',"decisions.jsonl unseen_attacker 23:08:21, 23:10:04; nav_journal 23:08:38")
add('m15','10-07','23:11:11','23:11:40',400,'none',
 "Pack full on the >: 'You have no room for a Trident' (Trident left); Navigator destroyed Dagger, Arrows, Iron Shots, Whip, Empty Bottle by hand.",
 'Pilot rule (pickup without room)','Free a slot (drop junk) before walking to pick up; or skip.',
 '767bf60 (bulky pickups need free slots); 3152ce7 (flavour-junk pickups skipped)','partly: m16 15:58, m17 14:35-14:36, m19 22:32 again hit pack_full',
 '~1 min per event, items left; REPEAT: yes',"decisions.jsonl pack_full 23:11:11")
add('m15','10-07','23:14:54','23:16:03',400,'none',
 "Wormtongue (rated 4, ranged): flee goal to a > 84 squares away while frost bolt/stinking cloud hit; HP 156 -> 91 with 9 Snagas; CCW spent on poison at 92/160; Navigator read last WoR 23:15:46.",
 'Pilot rule (flee a slow caster over a long path)','Stand and fight Wormtongue (melee ~6/turn, 250 HP, spells 1 in 5; user confirmed 23:33:42); flee only if stairs <= 8.',
 '2765956 (no long flee from slow weak-melee casters, > 25); 4d20a7c (distance 8)','partly: m18 19:01:47 Pilot again started a flee to a < 92 away (he was unseen, so the exemption did not apply); m21 killed him (missions.json note)',
 'HP low 91/160 (57%), last WoR, 1 CCW; REPEAT: yes','decisions.jsonl danger_seen 23:14:54, nav_jo 23:15:41, act CCW 23:15:42, WoR 23:15:46')
add('m15','10-07','23:18:05','23:19:25',450,'none',
 "Blind and confused in melee (HP 160 -> 86): no visible monsters so no cure; explore sent into walls; 'frontier unreachable' x2 and 'goto 40,177: no known path' (bump-learned walls). ALREADY ANALYSED: replay memo §2.",
 'Pilot perception + map (bump walls written while blind)','Cure blind/confused first with nothing in view; do not write bump walls; replan.',
 '9089ae2 (no bump walls while blind/confused; replan); 4d20a7c (cure with nothing in view)','yes: m16 15:42:42 blind+confused cured at once; m18 19:02:02 blind cured with CLW',
 'HP low 86/160, ~1.5 min, 1 CSW; REPEAT: low',"decisions.jsonl 23:18:12-23:19:25; replay memo §2")
add('m15','10-07','23:22:05','23:27:38',450,'none',
 "User-directed secret-door hunt in an inner room: Navigator stood 12-15 s at 47,151 / 51,151 / 49,146 (wait 10/12/15). Standing never searches. ~5.5 min. ALREADY ANALYSED: mission15-answers §1,§4.",
 'Doctrine / Pilot (no search command yet)','At the right square run `s` x20 (95% to find an adjacent door).',
 '2765956 (search [N]); 7d608cb (reports finds); b26c14a (structures recogniser spec)','yes: m16 15:38:46 search/open found the door at 42,110; m20 23:57 searchroom ran 26 s on an already-open door (fixed 2d0a2f2)',
 '~5.5 min; REPEAT: low',"decisions.jsonl goal_done 'wait 10/12/15' 23:24:36-23:27:04; user_message 23:27:38")
add('m15','10-07','23:31:06','23:31:49',450,'none',
 "CSW quaffed for confusion at 179/180 HP with only a mold nearby; user objected 23:31:33.",
 'Pilot rule (status cure with no mobile threat)','No potion for confusion when nothing mobile is near.',
 '2765956 (confusion cure only with mobile monsters near)','no: recurred m16 15:42:46 (CSW at 187/189, novice mages near) and the user asked again 15:44:10',
 '1 CSW (~50-65 g) each; REPEAT: yes',"decisions.jsonl act q 23:31:06; user_message 23:31:33; m16 15:42:46/15:44:10")
add('m15','10-07','23:32:32','23:33:04',450,'none',
 "Wormtongue again (3 away; stairs 12 away): flee + last WoR (23:32:37); HP 180 -> 102 during the ~15 s recall; frost bolt destroyed a CLW; 0 WoR left.",
 'Pilot rule (flee gives a caster free casts)','Fight him (no WoR, no flee).','4d20a7c (no-flee distance 8)','see row above (m18)',
 'HP low 102/180 (57%), 1 WoR (~176 g), 1 CLW; REPEAT: yes',"decisions.jsonl danger_seen 23:32:32, lost 23:32:36, nav_jo 23:33:04")
# ---------- m16 (10-08)
add('m16,m17,m18','10-08','15:31:10','15:32:34',0,'none',
 "Mission starts with the lantern at 0 turns and no flask (m16 15:31:10 low_supply; m17 13:57:24 and m18 18:46:35 the same). Cause in m17-18: town_light never took the lantern off because viewer polls counted as Navigator activity (7300 turns + 3 flasks burned idling).",
 'Pilot rule / harness (town_light, viewer polls)','Keep the lantern off and fuelled at mission end; refuel before reading WoR.',
 'f519491 (viewer polls no longer count as Navigator activity); 278df42 (gate counts a carried light)','yes: m19 start clean (lantern lit only to read WoR 22:15:04)',
 '~1-2 min and 20-25 g of flasks per mission (3 missions); REPEAT: no',"decisions.jsonl low_supply 15:31:10; reports m17/m18; commit f519491 message")
add('m16','10-08','15:33:05','15:33:53',450,'none',
 "CCW quaffed for stun at 153/180 (85%), then a Hill orc pack: 116/180 (64%) 'fight_going_badly'; Navigator called it 'a single weak orc' (E2: Cave and Hill orcs, 6+2 killed in 11 s).",
 'Pilot rule (cure thresholds) / Navigator information (sampled)','No CCW at 85% HP; ignore the stun.','7d608cb (cures gated by threat, per next_steps.md)','not verified',
 '1 CCW (~155 g); REPEAT: unknown',"decisions.jsonl act q 15:33:05, fight_going_badly 15:33:49; replay memo §3")
add('m16','10-08','15:36:05','15:36:36',500,'none',
 "500 ft: 'explore: nothing left to explore' after 40 s with open ground on the map; dive took stairs before the Navigator's goto fetched a Turquoise Ring (goto 17,81 'no known path' 15:36:21).",
 'Pilot rule (explore ends early) + Navigator timing','Search corridor dead ends / dig rubble before calling a level done.',
 'fb1c382 (dig rubble, search strict dead ends)','NO: no "searched N dead ends" or dead-end search record in any mission since (grep of decisions.jsonl; m17-m19 reports say "not seen")',
 '1 ring (not valued), ~1 min; REPEAT: unknown (never re-exercised)',"decisions.jsonl goal_done 15:35:49, goal_failed 15:36:21; nav_jo 15:36:05")
add('m16','10-08','15:37:30','15:39:59',550,'none',
 "User-spotted dead end with a secret door (42,110) found only after the user told the row/col; 'search nothing found' while the game said it found the door.",
 'Pilot movement/map (no dead-end search; search reply wrong)','Search every strict corridor dead end 15x (now automatic).',
 'fb1c382; 7d608cb (search reports finds incl. "discovered")','dead-end search never triggered since (see above); `search` reports exercised m16 only',
 '~2.5 min; REPEAT: unknown',"decisions.jsonl user_message 15:37:30, 15:38:40, act 'o dir=9' 15:38:46")
add('m16','10-08','15:42:42','15:44:18',550,'none',
 "Blind + confused by Novice mages: CLW and CSW quaffed at 189/189 HP; user asked 15:44:10 whether the CSW was needed (Navigator: no).",
 'Pilot rule (status cure with no HP threat)','Ignore blind/confusion at full HP when no heavy hitter near.','4d20a7c made cures stricter for blind/confused with nothing in view only','not re-exercised at full HP',
 '1 CLW + 1 CSW; REPEAT: yes',"decisions.jsonl 15:42:42, 15:42:46; user_message 15:44:10")
add('m16','10-08','15:46:46','15:50:56',550,'none',
 "Stat drainers: Rot jelly CHR 4->3 (15:46:46, after Yellow patch kill; Pilot walked into the jelly square 3 times, E2); explore drifted back to jelly (15:48:49 user asked for avoid); Purple mushroom patch CON 18->16->14 (15:50:11, 15:50:44); 'drained twice -> leave level' fired.",
 'Pilot movement/map (path beside/through drainer squares) + Pilot rule','Keep one square away from every NEVER_MOVE drainer; avoid zone around it.',
 '7d608cb (never meleed, never stood beside; avoid zones); e25c594 (avoid zones in explore); 4d20a7c (goals inside drainer zone dropped); 506c4f1',
 'yes, held: m17-m19 no stationary-drainer drain; `avoid Rot_jelly` accepted m18 (never met again)',
 'CON 18->14 (HP 189 -> 170) until Restore CON 362 g on 10-16 14:14; CHR 4->3; ~4 min; REPEAT: low',"decisions.jsonl stat_drained 15:46:46, 15:50:11, 15:50:44; replay memo §3")
add('m16','10-08','15:51:58','15:54:43',550,'none',
 "Calcite and Beryl rings missing from `Item squares` (rings were not item glyphs); the user spotted them 15:51:58; fetched after the Hippogriff fight.",
 'Pilot perception (item list excluded rings)','List rings/amulets/chests as items.','7d608cb (rings/chests are items in the dungeon)','yes: m17 14:09:11 Silver Amulet listed and fetched; m19 22:37 Corundum Ring fetched',
 '~3 min delay; REPEAT: no',"decisions.jsonl user_message 15:51:58; nav_jo 15:52:06, 15:54:43")
add('m16','10-08','15:58:10','15:59:32',550,'none',
 "Pack full: ~1 min of failed pickups (CCW potion, Pearl Ring, Cutlass 'no room'), then Navigator 'destroy Light all' matched Potions of Cure LIGHT Wounds and destroyed all 14 CLW (act k item=7 value=14 at 15:58:44); recall 6 min early with 3 cures.",
 'Pilot rule (by-name substring) + Navigator decision','Whole-word / ambiguity refusal; free a slot first.',
 '7d608cb (ambiguous names refused); 4d20a7c (by-name branch routed via item_index pack_only)','yes: m17 14:38:41 "Wand_of_Light matches 2 items" refused; m19 22:32:19 `destroy Potion_of_Slowness all` correct',
 '14 CLW (~300 g), 6 min of mission, 1 CCW/Ring possibly left; REPEAT: no',"decisions.jsonl act k 15:58:44; nav_jo 15:59:18; replay memo §3")
add('m16','10-08','16:01:20','16:01:54',0,'none',
 "Trident {good} (+3,+7) sold unidentified for 42 gold (buy-back 1848; ~34/round vs Main Gauche ~20) as the user said 'don't sell the trident' (16:01:33).",
 'Navigator decision + Pilot rule (sell guard on {good})','Identify {good}/{excellent} weapons before selling; keep as weapon.',
 '7d608cb ({good} not sold unidentified; flagged)','yes: m18 Robe [2,+1] identified before sale; m19 Awl-Pike identified -> 310 vs 112 quote',
 '~1800 g equivalent + weapon upgrade; REPEAT: no',"decisions.jsonl goal_done 16:01:36; nav_jo 16:01:54; V1 CSV")
# ---------- m17
add('m17','10-16','13:58:05','13:58:25',0,'none',
 "`fuel Flask_of_oil` x2 failed (singular vs '4 Flasks of oil'; lantern unwielded in town).",
 'Pilot rule (name match)','Match plural; wear lantern first.','506c4f1','yes: m18 18:47:20 "fuel: wear the lantern first" worked; shop buy plural failed 18:47:08, fixed 7e4f058, worked m19',
 '~25 s; REPEAT: no',"decisions.jsonl nav_cmd 13:58:05-13:58:25; complaints 14:39:55")
add('m17','10-16','13:58:47','14:08:12',0,'none',
 "10 min townfarm for Restore CON (146 -> 404, stalled 2 min, 79 short of 483); urchins stole 35 + 22 gold at 14:00:19/23 with ~12 urchins near; the 25%-off Restore CON came later (362).",
 'Navigator decision (spend 23% of a 43-min mission farming) + Pilot rule (thieves)','Dive with the money; buy at the next discount.',
 '56aaa1e/506c4f1/7e4f058/7bb2edd (thieves, dry-stop); 7c16bc5 (no-gold stop)','partly: thefts recur (see m15 row)',
 '~10 min, 57 g; REPEAT: low',"decisions.jsonl lost 14:00:19/23; nav_jo 14:04:08, 14:08:17; events message '35 coins were stolen!'")
add('m17','10-16','14:10:34','14:11:44',600,'20261016-141021-600ft.txt',
 "600 ft: Scruffy looking hobbit stole 63 (14:11:02) and 46 (14:11:41) = 109 gold (report says 63+12); Navigator goto 28,47 for a Zinc Wand brought Brodda adjacent (14:11:42); Pilot left by the > 2 squares away at 14:11:44 (HP 176 -> 153); wand left.",
 'Pilot rule (thief not killed) ; Navigator decision (goto)','Kill the adjacent hobbit before it touches (EAT_GOLD); keep fleeing Brodda (done).',
 '3152ce7 (dungeon thief event, thief-first hits)','yes: m22 01:48:05 thief event fired; V1 shows no thefts m20-23',
 '109 g, Zinc wand (~17+), HP 153/177; REPEAT: low',"events message 14:11:02/14:11:41; decisions.jsonl danger_seen 14:11:42, act '>' 14:11:44")
add('m17','10-16','14:11:48','14:13:39',650,'20261016-141145-650ft.txt',
 "650 ft by stairs-flee: 3 Black orcs (lvl 13) + Kobold shaman + breeding Silver mice + unseen archer in a corridor; fight_going_badly at 107/177 (14:12:53), Navigator let it fight; Phase landed past a corridor seen only with orcs in it: Navigator `goto <` 'no known path', Pilot flee 'no path to stairs'; Pilot read the LAST WoR 14:13:02-03 (emergency_loop), spent 3 CCW, 3 CLW, 1 CSW, 4 Phase in 15 s; yanked 14:13:18.",
 'Pilot map (monster squares not floor -> no path) + Pilot rule (no group-danger tier for 3+ L13 orcs) + Navigator decision (let it fight)','At 14:12:53 (HP 107, 3 L13 orcs + breeders, < 18 away) go for the < at once or read WoR; do not hold a corridor between orcs and mice.',
 '506c4f1 (monster squares are floor; flee/goto path through unseen squares, replayed on this dump); 767bf60 (recall after futile phasing)',
 'yes, twice: through_unknown fired m19 22:16:07/22:18:38, m22 x5, m23 22:26:00. m19 22:16 froze (run refusal, fixed 7bb2edd). The orc-mob pattern recurred m18 19:08, m22 01:54 (HP 25%), m23 22:26',
 'HP low 64/177 (36%; report says 46%), last WoR (~242 g), 3 CCW (~480), 3 CLW, 1 CSW, 4 Phase, ~20 min of mission; REPEAT: yes',"decisions.jsonl 14:12:53-14:13:18; events messages 14:12:20-14:13:18; T1_close_calls.csv row 1; level dump header '650 ft 14:11:45-14:13:16'")
add('m17','10-16','14:19:17','14:23:47',100,'20261016-142216-100ft.txt',
 "Night stairs trip: 'It makes a high pitched shriek' at 100 ft read as an unseen attacker, so the Pilot fled the level (14:22:23-28) at 197/197 HP; stairs ping-pong 50/100 ft (10 hops in 14:22:28-14:23:41).",
 'Pilot perception/rule (shrieker = unseen attacker)','Ignore the shriek (news only).','506c4f1 (shrieks news only)','not seen again (no shrieker m18-m23 in decisions)',
 '1 level, ~1-1.5 min; REPEAT: low',"decisions.jsonl unseen_attacker 14:22:23; complaints 14:39:55; level headers 14:22:16-14:23:47")
add('m17','10-16','14:28:06','14:38:07',100,'20261016-142851-100ft.txt',
 "Climb with `goal dive 0` from 150 ft: took a > back down at 100 (fresh-level rule, max_depth 200); 100/150 ft hopping 14:28:51-14:29:45 and 14:32:19-14:33:03 plus 2.5 min on one 100 ft level; Navigator spent ~10 min and learned only from 'arrived by >' (max_depth then set to 100).",
 'Pilot rule (dive goal descends while climbing)','Climb only goes up when target depth < current.','506c4f1 (climbs never go down; `goal dive FEET scum` to allow)','not re-exercised (m18/m19 reports: "didn\'t come up")',
 '~4.3 min of hopping (Navigator estimated ~2); REPEAT: no',"decisions.jsonl nav_jo 14:33:00; level headers 14:28:51-14:33:05; complaints 14:39:55")
add('m17','10-16','14:38:41','14:39:32',0,'none',
 "Sales: Wand of Light (16 charges) sold for 70 (fair ~126), pack-full pickups lost (gloves, Scroll of Light, boots x2).",
 'Pilot rule (shop pays kind cost for known-flavour wands)','Quote first; sell only identified/charged items.','none found (scorecard memo §3 lists as open)','not re-checked here',
 '~56 g; REPEAT: yes',"V1_value_events.csv m17 14:38:52; decisions.jsonl pack_full 14:35:39, 14:36:33, 14:36:46")
# ---------- m18
add('m18','10-16','18:49:11','18:58:04',550,'20261016-184911-550ft.txt',
 "9 min at 550 ft before finding a > (far bottom-left of a large level); Brigand stole a Speed potion (18:52:23); 74 refused runs ('You cannot run in that direction') interleaved with moves 18:50-18:52; Navigator sent goto 39,148 for a CCW.",
 'Pilot movement/map (explore + refused runs); no mapping aid used','Use Door/Stair Location / Magic Mapping / Deep Descent early (Pilot now does so for a staff).',
 '7e4f058 (dive uses Door/Stair Location); 7bb2edd (refused runs fall back to walking)','yes: m19 22:15:30 staff step found a > 54 away; m20 23:43 89 refusals with movement continuing',
 '~9 min of a 40-min mission, Speed potion (~75 g); REPEAT: yes',"decisions.jsonl nav_jo 18:54:13; events cannot-run count 74; level header 18:49:11-18:58:04; report m18 'Pilot problems'")
add('m18','10-16','18:54:14','18:55:02',550,'20261016-184911-550ft.txt',
 "Nighthawk (lvl 8, +10 speed): during a Navigator goto the Pilot walked with it adjacent for ~27 s (18:54:29-18:54:56), HP 215 -> 101 without fighting; 3 CLW + 1 Phase; `hunt Nighthawk` killed it in 3 s (18:55:02). A Phase Door scroll was destroyed 18:55:51.",
 'Pilot rule (goto walks away from a faster hitter)','Hold the goto and fight (auto-retaliate) the moment a faster monster is adjacent; Phase only at low HP.',
 '7e4f058 (goto held vs faster hitters) after 4d20a7c (goto held beside rated danger)',
 'NEVER exercised: tactic "goto held" appears 0 times in decisions.jsonl; no later faster-hitter goto',
 'HP low 101/215 (47%), 3 CLW + Phase, ~1 min; REPEAT: unknown (needs a set-piece)',"decisions.jsonl mons 18:54:24-18:55:02 (adjacent each second); events 18:54:29 'claws you' x45, 'bites you' x22; T1_close_calls.csv m18 18:54:58")
add('m18','10-16','19:01:47','19:02:24',600,'20261016-185806-600ft.txt',
 "Wormtongue: unseen 'It casts a frost bolt' (he was in the server list but not decoded: perception_gap 19:01:53); Pilot started a flee to a < 92 away; gas trap blinded 19:01:56; poisoned; stole 28 gold 19:02:03 and teleported; Navigator hunt order ~10 s after alert. He returned and stole 41 more at 19:08:23.",
 'Pilot perception (listed-only monster) + Pilot rule (unseen-attacker flee ignores the slow-caster exemption)','Fight him: melee 6/turn; do not flee 92 squares.',
 '2d0a2f2 (weak visible casters are not unseen attackers); 7bb2edd (caster exemption needs worst-case melee < HP/8)','m21 killed Wormtongue (missions.jsonl note); no later unseen-caster flee in m19-m23 reports',
 'HP low 148/215 (69%), 69 g, 1 CLW, blind ~5 s; REPEAT: yes',"events messages 19:01:47-19:02:03, 19:08:23; decisions.jsonl perception_gap 19:01:53")
add('m18','10-16','19:05:44','19:06:22',600,'20261016-185806-600ft.txt',
 "Giant red scorpion STR sting 18/50 -> 18/40 (one drain from 3 blows); hunt failed (a Tengu teleported the character away).",
 'Pilot rule (no drainer flag for a red scorpion; melee) / doctrine (no drainer list)','Do not melee STR drainers; avoid.',
 '7bb2edd (drainer event + drainers query); Navigator set `avoid` after','yes: ant (m23 22:19:59) and frog (m20 00:09:27) triggered drainer events with no drain after',
 'STR 18/40 into m19 (Restore STR 498); REPEAT: low',"decisions.jsonl stat_drained 19:05:44; nav_jo 19:06:22")
add('m18','10-16','19:08:23','19:09:18',600,'20261016-185806-600ft.txt',
 "Orc mob + Ufthak (3 Black orcs, 2-10 Hill orcs, Snaga, unseen archer; stairs 41 away): 139/215 'fight_going_badly' 19:08:47; Pilot group-danger Phase x4 and CSW x2; Navigator `goal recall` ~8 s after alert, WoR read 19:09:01, yanked 19:09:12; lowest 84/215 (39%, not in the report).",
 'Pilot rule (no auto-WoR on group danger with stairs far) + Navigator latency','Read WoR at first fight_going_badly when >= 3 L13 orcs and stairs > 40 (the m17 doctrine; now only a HANDBOOK note).',
 'none specific (767bf60 "recall after futile phasing")','NO: pattern recurred m22 01:54 (25%) and m23 22:26 (47%)',
 'HP low 84/215 (39%), 4 Phase, 2 CSW, 1 WoR (181 g); REPEAT: yes',"decisions.jsonl 19:08:47-19:09:12; T1_close_calls.csv m18 19:08:53; report m18")
add('m18','10-16','19:10:11','19:10:34',0,'none',
 "Shop goal sold a lone unknown scroll for 8 gold: it was Teleportation (escape lost); Stinking Cloud wand sold at kind cost 100 (fair ~160).",
 'Pilot rule (sell refusal covers only unknown flavours)','Read-test lone unknown scrolls; quote wands.','7e4f058 (lone unknown scrolls read, not sold)','yes: m19 read the unknown scroll (Trap Detection) instead of selling',
 '8 g + a Teleportation (~40) + 60 g short; REPEAT: scroll no; wand shortfall yes',"V1_value_events.csv m18 19:10:11/19:10:33; decisions.jsonl tactic 19:10:11")
add('m18','10-16','19:12:06','19:25:54',0,'none',
 "Day townfarm: 61 -> 334 in 50 s, theft 19:18:37 (67 g), then two dry 2-min stretches; 'Standing on: $' left uncleared at 19:04:56/19:12:06 (manual `pickup`).",
 'Pilot rule (townfarm keeps going dry; thief not hit) + Pilot perception (gold underfoot)','Stop after 2 min dry; kill thief first.','7e4f058 (gold underfoot cleared; thief hit runs); 7bb2edd (townfarm stops when dry)','m19: "Standing on" worked 22:14:12; thefts continue (22:47:38)',
 '67 g + ~6 min dry; REPEAT: yes',"decisions.jsonl lost 19:18:37; tactic 19:21:54, 19:23:54")
# ---------- m19
add('m19','10-16','22:15:39','22:16:09',600,'20261016-221522-600ft.txt',
 "White wolf pack (3-4) 215 -> 137 (62%); an invisible toucher ate Waybread, a ration and a mushroom (22:16:02-04) while the Pilot 'rested' 5 s with it touching; 'You failed to pick the lock' messages appear mid-fight (source of the attempt not checked) (22:16:00, 22:16:10).",
 'Pilot rule (rest while an unseen monster touches; lock-pick during a fight) + perception (no eaten news)','Fight/leave; never rest with unseen attacks; no door work in combat.',
 '7bb2edd ("was eaten!" is lost news); 2d0a2f2 (stuck skips lock-picking)','not re-met',
 'HP low 137/220; 3 food items (~15 g); REPEAT: low',"events messages 22:16:00-22:16:10; decisions.jsonl act rest 22:16:02-06")
add('m19','10-16','22:16:07','22:17:35',600,'20261016-221522-600ft.txt',
 "Frozen flee: the unseen-attacker flee (path through unexplored squares) stood at 37,105 from 22:16:30 to 22:17:35, sending 61 refused runs ('You cannot run in that direction'), no `stuck` alert; the Pilot also dug rubble 22:16:18-26.",
 'Pilot movement (refused run never falls back to walking; no stuck alert < 60 s)','Walk the path when a run is refused; stuck alert at 20 s.',
 '7bb2edd (refused runs fall back to walking from that square; 20 s stuck)','yes: m20 23:43:27-23:44:50 89 refusals but movement continued',
 '~65 s idle at full HP (no HP cost); REPEAT: no',"events message count 61 at 22:16:30; decisions.jsonl move pos [37,105] 22:16:34-22:17:32; complaint 22:17:35")
add('m19','10-16','22:17:53','22:19:26',600,'20261016-221522-600ft.txt',
 "Three STR drains in ~1 min: Giant red ant 22:17:53 (18/40 -> 18/30, 4 -> 3 blows), Giant red frog 22:18:38 and 22:18:49 (-> 18/10). Pilot meleed the weak ant by itself; the stat-drain flee then walked away from the same-speed frog with 6 wall bumps ('wall blocking your way' 22:18:42), then WoR 22:19:08 (flee stuck, > 5 away).",
 'Pilot rule (no drainer flag for ant/frog; flee from a weak same-speed drainer) + Navigator information (no drainer list)','Kill the weak drainer when it is adjacent, flee only from heavy ones; pre-check `monster` for red animals.',
 '7bb2edd (drainer event; second drain by a weak non-faster drainer -> Hunt)','yes: m20 00:09:27 (frog) and m23 22:19:59 (ant) drainer events, no further drain either time',
 'Restore STR 498 g, 1 WoR (63), town trip ~2.5 min; REPEAT: low',"decisions.jsonl stat_drained 22:17:53/22:18:38/22:18:49; events 22:18:42 x6; goal_failed 22:19:08")
add('m19','10-16','22:23:27','22:25:01',650,'20261016-222340-650ft.txt',
 "Unseen sound breath at 600 ft sent the Pilot down a > to 650 (22:23:38). Ranger (lvl 20): danger_seen text 'NOT fleeing (slow, hits weakly)', Navigator `hunt Ranger` ~9 s later without `monster`; 220 -> 66 in ~11 s (30% = lowest of m19); Pilot WoR 22:24:49 (potions too weak), 2 CCW + 2 CSW + Phase; yanked 22:24:58.",
 'Pilot information (danger text misrated Ranger) + Navigator decision (hunt)','Do not hunt a lvl-20 summoner with 40 worst-case melee; recall/stairs (29 away).',
 '7bb2edd (worst-case melee < HP/8 for the caster exemption)','not re-met; m22 02:04:03 Evil eye "NOT fleeing" correct (melee 0)',
 'HP low 66/220 (30%), last WoR (63 g), 2 CCW, 2 CSW, 1 Phase, 1 Heroism destroyed; REPEAT: yes',"decisions.jsonl 22:24:38-22:24:58; T1_close_calls.csv m19; report m19 mistakes")
add('m19','10-16','22:30:39','22:35:33',350,'none',
 "Stairs trip to 400 ft from town: pack full at 350 ft (22:32:13 unknown scroll 'no room'; Navigator destroyed Cutlass, Cloak, Slowness x2), goto 22,136 'stuck' 22:33:15, dive 400 spent 1.5 min with no >; Wand of Light x2 left (V1 ~70).",
 'Pilot rule (pickup without room) + exploration','Keep 1-2 free slots (drop junk pre-trip).',
 '767bf60 (bulky pickups need free slots)','not re-checked',
 '~3 min; ~70-90 g loot left; REPEAT: yes',"decisions.jsonl pack_full 22:32:13, goal_failed 22:33:15; V1 c_abandoned 22:30:04, 22:17:56")
add('m19','10-16','22:44:05','22:55:35',0,'none',
 "Town: Stinking Cloud wand sold 100 and Wonder 63 (about 68 g short); Phase Door stolen at 22:47:38 by a rogue (thief not hit); townfarm 376 -> 600 in 3 min then nothing 22:47-22:55 (4 and 2 min dry stretches).",
 'Pilot rule (sale shortfall; thief; dry townfarm)','Quote wands; hit thief first; stop dry farming.',
 '7bb2edd (townfarm clears stale hits, stops when dry)','dry-stop exercised m19 22:50-22:55 (stop after 2 min dry); no further thefts m20-23',
 '~68 g short + Phase (6) + ~5 min; REPEAT: yes',"V1_value_events.csv m19 22:44:05, 22:47:38; decisions.jsonl tactic 22:50:19, 22:53:28, 22:55:28")
with open('F1_incidents.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['mission','start_epoch','end_epoch','local_time','depth_ft','map_dump','summary','layer','right_behaviour','fixed_by','exercised_later','cost','evidence'])
    for r in R: w.writerow(r)
print(len(R))
