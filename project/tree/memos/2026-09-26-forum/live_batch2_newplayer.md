# Batch 2: New Player Support (87 topics, live site), distilled against the 2026-09-26 memo

URLs are shortened to `p=N`, which means `https://www.mangband.org/forum/viewtopic.php?p=N#pN`. **[code ✓]** marks claims I checked in `github/src/server`.

## New or contradicting findings

1. **Uniques are tracked per player, so a fresh character meets all of them.** A unique spawns on a level only if some player there has not killed it yet **[code ✓ `monster2.c:16-35` `allow_unique_level`, `p_ptr->r_killed`]**. Each death brings back the uniques that character killed whose level is above 65% of its max depth **[code ✓ `xtra2.c:2487-2518, 2706`, message "X rises from the dead!"]**. Uniques drop items only on the first kill (p=8783). Forum: p=8027, p=8030 (2010). [CONTRADICTS memo §4, "A named unique may already be dead": that is true only for the character that killed it. Each throwaway will meet Grip, Fang, Bullroarer, Wormtongue, Grishnákh and Azog.] → Navigator doctrine, HANDBOOK.
2. **Nobody sets a bot policy, and a developer joked about writing one.** PowerWyrm (2009, p=7769), on the Black Market's slow restock of Healing potions: "Hack the client to automatically… buy them" or "Write a bot to enter BM every 30 secs or so, check the store inventory and leave". Asked whether a *modified client* may play on the main server, he said "I'd say yes..." (p=7802, 2009). [STRENGTHENS Addendum §C, "nothing about bots"; this is the only on-record developer attitude, and it is mild.] Still don't poll shops in a loop: no idling in stores (p=3272, 2005). → Architect.
3. **The player list shows everyone your `realname@hostname`.** It comes from the client's OS user and host names (p=7757–7766, 2009) **[code ✓ `cmd4.c:723`, `net-server.c:988-989`]**. Our cluster login and node name would appear to every player. [NEW] → Architect: send neutral real and host names (PowerWyrm says a modified client is fine, p=7802).
4. **One login per IP address on mangband.org (2007).** The limit came from "extensive abuse"; getting round it "can get your characters nuked" (p=3365, p=3368, p=3370). I found no per-IP check in the 1.5 source, so this was a server setting, and the live value is unknown. Reconnecting under the same name takes over the session that is still lingering **[code ✓ `net-server.c:884-900`, "Reconnect from other location."]**. [NEW; MAYBE-OUTDATED] → Architect: one connection per host. Other cluster users behind the same NAT could collide with us.
5. **Dead characters' names stay reserved** until the savefile is deleted or the server resets (p=5676, p=5679, 2008). A ghost's destruction empties its houses (p=5656). [NEW; MAYBE-OUTDATED] → Architect: generate a fresh, unique name for each throwaway.
6. **Alts are allowed; free gifts between them are not.** Self-rescue with an alt is "a classic" and fine, but "you shouldnt give items from one character to another for free" (Warrior p=3373, Fink p=3374, 2007). An admin retired hoarding alts. [STRENGTHENS §C.] P15 ("don't go back for gear") still stands.
7. **Don't drop or sort items on the ground in town.** Another player picked up a rod while its owner was swapping gear (p=9790, p=9794, 2014). Destroy junk with `k` rather than dropping it, as a courtesy (p=3212, 2003). [STRENGTHENS §C.] → Pilot rule.
8. **Real-time combat pace.** "A round lasts a second, and there are up to 40 combat 'turns'". The auto-retaliator handles melee, "but don't get surrounded" (Crimson p=3270, 2005). Warrior's newbie doctrine: pick fights, fight "in narrow corridors or at least around a corner", and keep CSW/CCW and Phase/Teleport one keypress away (p=3373, 2007). [STRENGTHENS §1.2, P6; recall A5, 2-wide corridors, so prefer corners and doors.] → Navigator.
9. **Put the target first in any command that needs one.** "Directional macros should always be `\e*tm`… if you put the `*t` at the end, you'll be prompted for a direction and if nothing is targetable, you'll be stuck on a prompt. Easy way to get killed" (PowerWyrm p=7658, 2009). Under lag, fast keys were dropped (p=3346, p=3348, 2007). [NEW; strengthens P10.] → Pilot: for throw or fire (oil flasks), check that a target exists before sending; pace the keystrokes.
10. **Detection costs a turn, which can be fatal.** Kom died to Azog in 2 turns after pressing detect monsters by mistake, with 19 CCW in the pack. "Detect monsters kind of causes me to lose a round or two" (p=5990, p=5999, 2008). [STRENGTHENS Addendum 2 #1, Addendum B (Azog).] → Pilot: never detect with a threat adjacent.
11. **ESP misses empty-mind monsters, including summoners.** It won't show drolems, bone and bronze golems, or greater rotting, demonic, draconic and master Qs. Its radius is limited; Detect covers a panel. Watch the elemental uniques (Vargo, Waldern) and the Emperor Q (PowerWyrm p=9361, 2013). [STRENGTHENS §3; adds Qs, the summoners of §1.2.] → Navigator.
12. **Chaos resistance does not cover confusion** in MAngband: "you need res confusion now" (p=9367, 2013). [NEW] → Navigator: the rConf checkpoint in §3 must be real rConf.
13. **"Cannot be harmed by fire" is not resist fire.** A player at 4450 ft thought it was and took a 1600-damage Glaurung breath (p=6257, 2008). Only *known* resists show on the `C` grid, and they don't stack (p=7151, p=7152). [NEW] → parser, Navigator: read resists from the character sheet, never from item text.
14. **Word of Recall inscription syntax.** `@R400` recalls to 400 ft, and `@R-150` to the wilderness. A lowercase `@r` or any typo recalls "to the deepest level you have reached". Carry backup WoR, since scrolls get burned or stolen (p=7223, 2009). [STRENGTHENS Addendum 2 #10.] → Pilot: check the inscription before reading.
15. **Healing potions are scarce and slow to restock.** About 1300 gold each in the BM (2009). Veterans waited in town for hours to get a few (p=7769, p=7770). Version 1.1 deliberately removed MAngband's readily stocked BM Healing (p=7781). Rods of Healing are "totally useless in real time" because they take so long to recharge (p=7778). [STRENGTHENS Addendum B.] → Navigator: CCW is the throwaway's real heal; don't plan on Healing.
16. **Starting-shop facts** [MAYBE-OUTDATED, 2003]: Identify costs under 100 gold in the Alchemist (5), and *Identify* 3000–5000 in the BM (p=3222). Buy a lantern and fill it with a flask at once (it holds 15,000 turns, so no oil is wasted); lanterns found on the floor can be combined into yours (p=3316, 2005). → Navigator shopping.
17. **Player shops mark items up.** Items "{on sale}" cost 3× base (the BM rate), and the same item was half price in another shop (p=5795, p=5800, 2008). [NEW] → Navigator: prefer the town stores for consumables.
18. **Stat potions above the natural maximum are wasted.** Natural maxima for a Half-Orc Warrior (maximise mode is always on): STR 18/170, DEX 18/120, CON 18/130. A player drank a 40k DEX potion "to no avail" (p=5734, p=5739, 2008). [NEW] Mostly relevant past 1500 ft (p=7559).
19. **Early monsters to leave alone** (for casters, but they carry over): jellies "practically unkillable", "novice warriors and paladins are dangerous", out-of-depth dark elven mages (p=7653, 2009). Zal: at about 400 ft "avoid all orcs and most p's", and shoot stationary jellies, molds and mushrooms with a bow for XP (p=7559). [NUANCE to Addendum 2 #2: don't *melee* molds, but shooting them from range is a known XP farm.]
20. **Items on a death level last only while the level is allocated.** "Items never disappear, unless you leave the level and that level is deallocated" (PowerWyrm p=4710, 2008). An old claim: "Saving on a level will cause it to become static for some time" (p=3245, 2003) [MAYBE-OUTDATED; contradicts memo §4's code-verified freeing unless 1.5 keeps "static" levels]. A ghost at 0 HP is not dead, but "any scratch will kill u"; a dead ghost means the character is gone (p=3245, p=3248). [STRENGTHENS P15.]
21. **Auto-pickup inscription `=g`.** Items inscribed `=g` are picked up when walked over (p=6615, 2009) **[code ✓ `cmd1.c:591` `auto_pickup_okay`]**. [NEW; helps reconcile the pickup conflict in Addendum B.] → Architect.
22. **Town UI facts.** You start in the tavern (building 8); walk onto the '8' tile to leave it. Walk onto a number to enter a shop. Moving into a monster attacks it automatically (p=9288, p=9628, 2013–14). The 1.1 roadmap "limit[ed] the aggressiveness of the townies" (p=7781), so the town is less dangerous than pre-2008 accounts suggest. [NEW] → HANDBOOK.

## Death catalogue

| Cause | Depth | Char | Mistake | Lesson | URL |
|---|---|---|---|---|---|
| Lagduff + ~25 snagas surrounded him | 250 ft | clvl 8 (Puri) | Read a Scroll of Summoning hoping for an ally | Never read summon or aggravate scrolls; read-test unknowns on a stair | p=3372 (2007) |
| Wormtongue | ? | new player | (none given); lost gear on the level | Leave early uniques alone; gear is lost once the level resets | p=3244 (2003) |
| Azog, in 2 turns | ? | ranger (Kom) | Pressed detect monsters instead of acting, with 19 CCW unused | Escape first; detection costs turns | p=5990, p=5999 (2008) |
| Glaurung fire breath, 1600 damage | 4450 ft | clvl ~50 (Prosper) | Took "cannot be harmed by fire" for resist fire | Read resists from the `C` screen | p=6247, p=6257 (2008) |
| Orcs on login (several characters) | Ironman | magic users | Macros failed to reload, so logged in without working spells | Verify the action bindings before acting after login | p=3344 (2007) |

## Posts worth reading in full

1. **t=1737 (p=7767–7782)**: Healing scarcity, the "write a bot" remark, and the 1.1 roadmap.
2. **p=9361**: which monsters ESP misses (drolems, golems, Qs).
3. **t=802 (p=3372–3374)**: the alt and self-rescue rules, the summoning death, Warrior's corridor doctrine.
4. **p=7223, p=7225**: WoR inscription syntax and its failure mode; houses and selling.
5. **t=1735 (p=7757–7802)**: `realname@hostname` exposure, and a developer allowing modified clients.

## Coverage

87 of 87 topics read in full.
- **31 substantive:** t=767, 770, 776, 783, 791, 796, 801, 802, 1085, 1327, 1332, 1343, 1361, 1405, 1518, 1575, 1651, 1661, 1692, 1704, 1716, 1735, 1737, 1779, 1850, 1905, 2067, 2078, 2081, 2137, 2163.
- **56 skipped:**
  - Connection, install, compile or server hosting (22).
  - Old client UI, keys or macros with no server fact (15, e.g. t=779, 807, 2234).
  - Social, meta or spam (12).
  - Race or class choice not relevant to a Half-Orc Warrior (7).

Almost all posts date from 2002–2014 (0.7–1.1). Only t=2234 is from the 1.5 era (2019), and it covers client macro bugs fixed in 1.5.2.
