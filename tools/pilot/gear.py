"""gear -- the Pilot's gear judgement and shadow mode, as a mixin of Pilot (refactor-candidates E1;
docs/gear-and-estimator.md): the gear evaluator's side in the Pilot (gear_character, gear_eval, gear_better,
loadout_info, gear_review, gear_line, ac_better, consumables_inv), shadow mode (shadow_decision, shadow_results,
band_shadow, hard_fight_shadow) and the rulebook's duel estimates (fight_rows, fight_estimate, fight_sim), with
shadow_agree. The methods stay Pilot's: they read and write the Pilot's state through self; pilot.py imports
shadow_agree back (P.shadow_agree).
"""
import csv
import json
import os
import re
import sys
import time

import geareval
import shadow
from common import HERE, TV_SCROLL, TV_POTION, TV_LITE, bare_name, bad_inscription
from world import gnow, time_factor, waited


MIN_GAIN, MIN_GAIN_BLOCKS = 50, 48     # options_sim's override floor: max(50, 48 blocks x xp_rate_per_block)


def min_gain_of(p):
    """The estimator's own threshold for "clearly better" (options_sim.choose): max(50, 48 x xp_rate_per_block)."""
    return max(MIN_GAIN, MIN_GAIN_BLOCKS * float((p or {}).get("xp_rate_per_block") or 0))


def shadow_agree(choice, actual, table, p=None):
    """(agree, the actual action's row) for an estimator answer: the estimator chose the action the Pilot took; or it
    kept its copy of the rules ("rules") and the action the Pilot took (when the table has a row for it) is safe and
    not beaten by a safe row by more than the estimator's own threshold -- max(min_gain, 2 SE) (2.58.0, the Advisor:
    three m63-m65 "disagreements" were rows 17-35 XP better, under its 50-XP floor)."""
    rows = {t.get("option"): t for t in table or ()}
    row = rows.get(actual) if actual != "rules" else None
    if choice == actual:
        return True, row
    if choice == "rules":
        if row is None:
            return True, None
        best = max((t for t in rows.values() if t.get("safe")), key=lambda t: t.get("dxp", 0), default=None)
        if best is None:
            return bool(row.get("safe")), row
        margin = max(min_gain_of(p), 2 * max(best.get("se") or 0, row.get("se") or 0))
        return bool(row.get("safe")) and row.get("dxp", 0) >= best.get("dxp", 0) - margin, row
    return False, row


def band_verdict(r):
    """2.58.0 (the user: "let the estimator decide" bands): the XP fighting beats leaving by, when the estimator's
    answer `r` (shadow) is confident, else None. Confident: its choice is to fight -- "fight", or "rules", its copy of
    the Pilot's rules, which fights a band -- that row is safe, and it beats the leave row (the Pilot's band rule:
    stairs, else recall+phase) by more than max(min_gain, 2 SE)."""
    if not r or r.get("error"):
        return None
    table = r.get("table_all") or r.get("table") or []
    rows = {t.get("option"): t for t in table}
    choice = r.get("choice")
    if choice not in ("rules", "fight"):
        return None
    pick = rows.get(choice)
    leave = rows.get((r.get("snap") or {}).get("rules") or "stairs") or rows.get("stairs") or rows.get("recall+phase")
    if not pick or not leave or not pick.get("safe") or leave is pick:
        return None
    gain = (pick.get("dxp") or 0) - (leave.get("dxp") or 0)
    return gain if gain > max(min_gain_of(r.get("p")), 2 * (leave.get("se") or 0)) else None


class GearMixin:
    """Pilot's gear and shadow-mode methods (`class Pilot(ReportMixin, GearMixin, ItemsMixin)`: every name stays on
    Pilot)."""

    def shadow_decision(self, detail, options=None, trigger="emergency", rules=None, extra_p=None):
        """Shadow mode (the user, 10-25): hand this decision's state to the Advisor's estimator in the background
        (shadow.py): an emergency (all options), or the start of a hard fight (hard_fight_shadow: its own options).
        Never waits, never acts on it. Returns 'started', 'skipped' (one running) or 'off'."""
        sh = self.shadow_est
        if sh is None:
            sh = self.shadow_est = shadow.Shadow()
            if sh.error:
                self.log("note", text=f"shadow mode off: the estimator didn't load ({sh.error})")
        if not sh.sim:
            return "off"
        w = self.w
        wt = [x for x in self.weapon_table() if x[3]]
        prof = shadow.weapon_profile(wt[0][0] if wt else "", wt[0][1] if wt else 1)
        # (A3: the estimator's tohit/todam are totals -- the weapon's plus rings, gloves and other gear and the STR/DEX
        # bonuses, the Advisor's docs memo 10-28 §4 -- from the gear evaluator's model, as geareval.sim_player passes)
        try:
            d = self.gear_character().derive()
            prof.update(tohit=d["tohit"], todam=d["todam"])
            # (A14, the Advisor's memo 2026-10-29-s10-reply: slays, brands and the weapon's weight, as sim_player)
            prof.update({k: dict(d[k]) for k in ("slays", "brands") if d.get(k)})
            if d.get("wweight"):
                prof["weight"] = d["wweight"]
        except Exception as e:                     # (the weapon's own numbers then; said once in the log)
            if not self.shadow_gear_said:
                self.shadow_gear_said = True
                self.log("note", text=f"shadow mode: the gear model failed, the weapon's own (+h,+d) passed ({e!r})")
        stairs = min((sh.sim.adist(q[0] - w.pos[0], q[1] - w.pos[1]) for q in w.find("<>")), default=None) \
            if w.pos else None
        p = dict(hp=w.hp[0], mhp=w.hp[1], ac=(w.ind.get("armor") or [0])[0] or 0, clvl=w.clvl,
                 depth=w.depth or 1, stairs=stairs, free_action=bool(self.has_ability("free_action")),
                 # (the sheet's resists, as the simulator's flags: options_sim 26f models them; m47's Dark hounds'
                 # darkness breath was simulated at full damage on a Half-Orc)
                 **{geareval.SIM_RES[f]: True for f in
                    ({geareval.SHEET_FLAG.get(k.upper(), k.upper()) for k, on in (w.flags or {}).items() if on}
                     & set(geareval.SIM_RES))},
                 save=sh.sim.SAVE, max_adj=2 if self.mover.in_corridor() else shadow.MAX_ADJ, **prof,
                 inv=self.consumables_inv())
        for k, on in (("fast", self.buff_on("fast")), ("hero", self.buff_on("hero")), ("berserk", self.buff_on("shero")),
                      ("blind", w.flag("blind")), ("confused", w.flag("confused")), ("afraid", w.flag("afraid")),
                      ("slow", self.our_slowness() > 1)):
            if on:
                p[k] = 5
        if w.recall_pending:
            p["recall"] = max(1, int(25 - (gnow() - w.recall_pending_t) / shadow.TURN_S))
        # (the asleep flags the `look` answers give: the share awake among the looked-at monsters not adjacent, for
        # the simulator's p_awake -- its 0.4 stood in for this; the Advisor's top data gap)
        looked = [self.is_asleep(y, x) for y, x, _ in w.monsters if w.pos and w.dist((y, x)) > 1]
        looked = [z for z in looked if z is not None]
        if looked:
            p["p_awake"] = round(sum(1 for z in looked if not z) / len(looked), 2)
            p["asleep_seen"] = sum(1 for z in looked if z)
        # (the food counter for options_sim's gorging: the client gives the hunger level only, so the level's range,
        # drawn per rollout -- options_sim 26j's FOOD_LEVEL; gorging is a threshold, the Advisor: a midpoint hid the risk)
        lvl = {0: "Weak", 1: "Weak", 2: "Hungry", 3: "Fed", 4: "Full", 5: "Gorged"}.get(w.hunger, "Fed")
        fl = getattr(sh.sim, "FOOD_LEVEL", None)
        p["food"] = fl[lvl] if fl and lvl in fl else {"Weak": 750, "Hungry": 1500, "Fed": 6000, "Full": 12500,
                                                      "Gorged": 15000}[lvl]
        # (options_sim 28l, the Advisor's MIN_GAIN memo 10-28: the XP-override floor is max(50, 30 s of play) at this
        # rate; unlike xp_per_block it charges no time cost, so it goes in every snapshot, emergencies too)
        dr = (self.rate_state().get("depth") or {}).get(str(w.depth_ft))
        p["xp_rate_per_block"] = round(dr[0] / (dr[1] / 60) / 96, 3) if dr and dr[1] > 300 else 0
        # (2.58.0, options_sim 11-04q: what an acid hit and a disenchantment cost the worn gear, in gold)
        try:
            p["acid_gold"], p["disen_gold"] = self.gear_damage_gold()
        except Exception:
            pass
        p.update(extra_p or {})
        # (name, distance, hp_frac, awake): options_sim 26h takes the asleep flag per member (the `look` answers; None =
        # unknown, the p_awake share then 0.4 stand in) -- the Advisor: 7 Wargs, six at 4 squares, ~11 HP lost if
        # known asleep, ~55 awake, ~23 unknown
        team = [(r.name, max(1, sh.sim.adist(y - w.pos[0], x - w.pos[1])), None, self.awake_of(y, x, r))
                for y, x, r in w.monsters] if w.pos else []
        # (and what the server's list names but the map doesn't show yet, 3 squares off: A2K's first emergency had
        # Khim in the list only, and the estimator played an empty fight)
        team += [(r.name, 3) for r in (w.listed_only() if hasattr(w, "listed_only") else [])]
        snap = {"p": p, "team": team, "rules": rules or shadow.rules_option(detail), "rules_detail": (detail or "")[:160],
                "wall": time.time(), "factor": time_factor(), "speed": (w.ind.get("speed") or [0])[0] or 0,
                "options": list(options) if options else None, "trigger": trigger, "xp_per_gold": self.xp_per_gold()}
        return sh.submit(snap)

    ACID_SLOTS = (36, 37, 38, 34, 35, 31, 32, 33, 30)     # body, shield, cloak, gloves, helm, boots (spells1.c minus_ac)

    def gear_damage_gold(self):
        """(acid_gold, disen_gold) for options_sim 11-04q (2.58.0, the Advisor's estimator review): acid_gold = 1/6 of
        the sum over body, shield, cloak, gloves, helm and boots of what one to-AC lost costs to put back (the
        gear-damage reflex's cost: the kit's read at the lowered plus, else the resale), 0 for an empty slot, an
        IGNORE_ACID item or ac+to_a <= 0; disen_gold = one disenchantment's expected cost (disen_loss)."""
        w = self.w
        slots = {}
        for i in w.items(equip=True):
            if i["tval"] in self.ACID_SLOTS:
                s = {36: "body", 37: "body", 38: "body", 34: "shield", 35: "cloak", 31: "gloves", 32: "helm",
                     33: "helm", 30: "boots"}[i["tval"]]
                slots.setdefault(s, i)
        total = 0.0
        for s, i in slots.items():
            gi = geareval.Item(i["name"], i["tval"])
            m = re.search(r"\[(\d+),([+-]\d+)\]", i["name"])
            ac, x = (int(m.group(1)), int(m.group(2))) if m else (gi.ac, gi.to_a)
            if "IGNORE_ACID" in gi.flags or ac + x <= 0:
                continue
            sc, lost = self.reenchant_cost("toac", x - 1, x, self.is_artifact(i["name"]), "armour", i["name"])
            total += sc + lost
        try:
            disen = self.disen_loss()[0]
        except Exception:
            disen = 0.0
        return round(total / 6, 1), round(disen, 1)

    def awake_of(self, y, x, r):
        """The monster at y,x awake (True), asleep (False), or unknown (None), from the `look` answers (2.58.0, the
        Advisor: the model takes an unknown adjacent monster as awake -- m63's 7 Uruks, very likely asleep): its own
        square's answer; else, for its race, a recent answer that it was awake, or an asleep one whose square that race
        has left (it woke and moved)."""
        v = self.is_asleep(y, x)
        if v is not None:
            return not v
        now = gnow()
        recent = [(q, a) for q, (t, n, a) in self.asleep.items() if n == r.name and now - t < 60]
        if any(a is False for _, a in recent):
            return True
        here = {(yy, xx) for yy, xx, rr in self.w.monsters if rr.name == r.name}
        if any(a and q not in here for q, a in recent):
            return True
        return None

    def shadow_results(self):
        """Log the estimator's answers (the main thread writes the log): with whether it would have arrived in time --
        within one player turn at the time factor of the decision, and before the Pilot's next action."""
        sh = self.shadow_est
        if not sh:
            return
        while not sh.results.empty():
            r = sh.results.get()
            snap = r.get("snap") or {}
            sp = snap.get("speed", 0)
            energy = 1.0 + max(-0.5, min(1.0, sp / 10.0))          # (roughly: +10 doubles our turns)
            turn_s = shadow.TURN_S / max(0.05, snap.get("factor") or 1.0) / energy
            nxt = next((t for t in self.act_walls if t > snap.get("wall", 0) + 0.05), None)
            in_turn = r.get("compute_s", 99) <= turn_s
            before_next = nxt is None or r.get("done_wall", 0) <= nxt
            # (no monster the estimator knows: nothing to compare -- agree is None). The estimator's "rules" row is
            # its copy of the Pilot's rules, which can act differently from the Pilot (m47: its copy fought the Wargs
            # where the Pilot read Word of Recall, the table's worst row at -102 XP, and "agree" was logged). So
            # when the Pilot's actual action has its own row, "rules" agrees only if that row is safe and within noise
            # of the best (2 SE, at least 10 XP).
            agree, actual_row = shadow_agree(r.get("choice"), snap.get("rules"), r.get("table_all") or r.get("table"),
                                             r.get("p"))
            if snap.get("trigger") == "band":
                self.band_result = (snap.get("wall", 0), r)       # (2.58.0: the band decision reads it)
            if not r.get("team"):
                agree = None
            self.log("estimator", trigger=snap.get("trigger", "emergency"), options=snap.get("options"),
                     xp_per_gold=snap.get("xp_per_gold"),
                     rules=snap.get("rules"), rules_detail=snap.get("rules_detail"),
                     choice=r.get("choice"), why=r.get("why"), agree=agree, actual_row=actual_row,
                     compute_s=r.get("compute_s"), turn_s=round(turn_s, 2), in_time_turn=in_turn,
                     before_next_act=before_next, next_act_after_s=round(nxt - snap["wall"], 2) if nxt else None,
                     team=r.get("team"), p=r.get("p"), inv=r.get("inv"), table=r.get("table"), error=r.get("error"),
                     policy_version=getattr(sh.sim, "POLICY_VERSION", None), max_adj=(r.get("p") or {}).get("max_adj"),
                     arrivals=[])

    HARD_FIGHT_OPTIONS = ("fight", "speed", "berserk", "speed+berserk", "phase")
    BAND_OPTIONS = ("fight", "stairs", "recall+phase", "phase")

    def band_shadow(self, detail):
        """Shadow mode at a band's leave decision (the user, 10-26, after m47: 9 Wargs, ~197 HP to fight them all vs
        333, fled to stairs 28 steps off, stuck, recalled -- shadow mode only ran once the flee had failed). The rules'
        action: the stairs when known, else Word of Recall. Once per band and level (20 s apart). Never acts."""
        w, now = self.w, gnow()
        key = (w.level_t, frozenset(r.name for *_, r in w.monsters))
        seen = self.band_shadow_seen
        if now - seen.get(key, -99.0) < 60 or now - self.band_shadow_t < 20:
            return None
        seen[key], self.band_shadow_t = now, now
        rules = "stairs" if w.find("<>") else "recall+phase"
        # (time is part of the trade: options_sim 26g charges each line xp_per_block for its blocks and the rest to
        # recover -- the Advisor: our XP per dungeon minute at this depth / 96 blocks a minute)
        d = (self.rate_state().get("depth") or {}).get(str(w.depth_ft))
        xpb = round(d[0] / (d[1] / 60) / 96, 3) if d and d[1] > 300 else 0
        return self.shadow_decision(f"band: rules {rules} ({detail[:100]})", options=self.BAND_OPTIONS,
                                    trigger="band", rules=rules, extra_p={"xp_per_block": xpb})

    def hard_fight_shadow(self, now):
        """Shadow mode at the start of a hard fight (the user, 10-25, on the Advisor's shadow-review memo: its replays'
        one consistent gain was Speed or Speed+Berserk quaffed at the start of hard fights, which the rules only quaff
        in an emergency). Once per fight: a new set of adjacent monsters on this level, not within 60 s of the same set,
        nor 20 s of the last. The rules' choice here is what speed_start_tick and berserk_tick would quaff (speed, berserk, both), else
        fighting on.
        Never acts."""
        w = self.w
        if not w.in_dungeon or not w.pos:
            return None
        adj, hard = self.hard_fight()
        if not hard:
            return None
        key = (w.level_t, frozenset(r.name for r in adj))
        seen = self.hard_fight_seen
        if now - seen.get(key, -99.0) < 60 or now - self.hard_fight_t < 20:
            return None
        seen[key], self.hard_fight_t = now, now
        pot = any("Berserk" in i["name"] for i in w.items(tval=TV_POTION))
        berserk = pot and not self.buff_on("shero") and waited(self.berserk_t, 30)
        # (2.58.0, the user: no Speed at a hard fight's start -- speed_start_tick drinks it only when losing)
        label = "berserk" if berserk else "fight"
        names = ", ".join(sorted({r.name for r in adj}))
        return self.shadow_decision(f"hard fight with {names}: rules {label}", options=self.HARD_FIGHT_OPTIONS,
                                    trigger="hard_fight", rules=label)

    def fight_rows(self):
        if self._fight_rows is None:
            try:
                self._fight_rows = {int(r["idx"]): r for r in csv.DictReader(
                    open(os.path.join(HERE, "..", "rulebook", "monsters.csv")))}
            except OSError:
                self._fight_rows = {}
        return self._fight_rows

    def fight_estimate(self, race):
        """(turns to kill it, HP it takes meanwhile, the pessimistic HP, its worst breath, its
        row) by the rulebook's fight rule (rule.py fight: hit chance from skill and to-hit
        against 3/4 of its AC, its expected melee per player turn at our AC, spells and
        ranged attacks), or None. Pessimistic: twice the turns (blinks, heals, misses) with
        its spells at their maximum: the m19 Ranger rates ~27 expected, ~196 pessimistic,
        and took 153."""
        row = self.fight_rows().get(getattr(race, "idx", None))
        wt = [x for x in self.weapon_table() if x[3]]
        if not row or not wt:
            return None
        name, blows, dpr, _ = wt[0]
        chance = 82 + 45 * self.w.clvl // 10 + 3 * geareval.Item(name).to_h
        ph = 0.05 + 0.90 * max(0.0, 1 - (int(row["ac"]) * 3 // 4) / chance)
        per_turn = max(0.1, ph * dpr)
        turns = int(row["hp"]) / per_turn
        ac = self.w.ind.get("armor", [0])[0] or 0
        col = min((20, 40, 60), key=lambda a: abs(a - ac))
        melee, sp = float(row[f"melee_turn_ac{col}"]), float(row["spell_pct"] or 0)
        taken = turns * (melee * (1 - sp) + float(row["range_turn"] or 0))
        worst = 2 * turns * (melee + sp * float(row["spell_max"] or 0) + float(row["range_turn"] or 0))
        return turns, taken, worst, float(row["breath_max"] or 0), row

    def fight_sim(self, race, n=600):
        """The Advisor's fight_sim.summary at our live profile, or None (tools/rulebook/fight_sim.py,
        synced from Advisor/data/rulebook; ~0.1 s for 600 duels)."""
        try:
            if self._sim is None:
                sys.path.insert(0, os.path.join(HERE, "..", "rulebook"))
                import fight_sim
                self._sim = (fight_sim, {r["idx"]: r for r in csv.DictReader(
                    open(os.path.join(HERE, "..", "rulebook", "monsters_raw.csv")))})
            mod, rows = self._sim
            row = rows.get(str(getattr(race, "idx", "")))
            wt = [x for x in self.weapon_table() if x[3]]
            if not row or not wt:
                return None
            prof = shadow.weapon_profile(wt[0][0], wt[0][1])      # (geareval.Item's numbers: D6)
            # (2.45.0, the Advisor's 2026-11-03-245-reply: the server's to-hit and to-dam are the weapon's plus the
            # rest -- rings, gloves, the STR/DEX tables, cmd1.c:1243-1285 -- so the totals from the gear model, as the
            # shadow snapshot passes (A3); the weapon's own (+h,+d) understated our damage: Khim ~36 turns, not ~27)
            try:
                d = self.gear_character().derive()
                prof.update(tohit=d["tohit"], todam=d["todam"])
            except Exception:                  # (the weapon's own numbers then)
                pass
            import argparse
            o = argparse.Namespace(clvl=self.w.clvl, blows=prof["blows"], dice=prof["dice"],
                                   todam=prof["todam"], tohit=prof["tohit"],
                                   ac=self.w.ind.get("armor", [0])[0] or 0, hp=max(1, self.w.hp[0]), n=n)
            return mod.summary(row, o)
        except Exception as e:             # (a rulebook problem must not break the check)
            self.log("note", text=f"fight_sim failed: {e!r}")
            return None

    # Disenchantment (2.45.0; the Advisor's Khim memo, 2026-11-02). The server's rules: an UN_BONUS blow must hit
    # first (melee1.c:276 check_hit: 5% always, 5% never, else randint1(20 + 3 x level) > 3/4 AC, melee1.c:106-127,
    # power 20 at melee1.c:245; AC counts, no saving throw), then without resist disenchantment (melee1.c:543-548,
    # p_ptr->resist_disen from any TR2_RES_DISEN: xtra1.c:2353, 2537) apply_disenchant (spells1.c:1303) picks one of
    # these 8 slots at random (spells1.c:1316-1327; never rings, amulet or light). An empty slot, or one with no
    # positive to-hit, to-dam or to-AC, loses nothing (spells1.c:1332-1341); an artifact (name1: randarts too) resists
    # 60% of the time (spells1.c:1348-1356); a weapon or bow loses 1 to-hit and 1 to-dam, armour 1 to-AC, and a plus
    # still above +5 after that another 1 with 20% (spells1.c:1359-1376). A disenchantment breath (BR_DISE,
    # GF_DISENCHANT) disenchants whenever it lands, unless resisted (spells1.c:3801-3810).
    DISEN_SLOTS = (("weapon", (20, 21, 22, 23)), ("bow", (19,)), ("body armour", (36, 37, 38)), ("cloak", (35,)),
                   ("shield", (34,)), ("helm", (32, 33)), ("gloves", (31,)), ("boots", (30,)))
    DISEN_ART_KEEPS = 0.4     # an artifact loses a plus 40% of the time (spells1.c:1345)
    # What a lost plus costs (2.46.0, the user's option 2 on the Advisor's 11-03 memo), step by step (x -> x+1):
    # - a step plan town would buy back (`disen_buys`: the town kit's own rule -- a Scroll of Enchant at plus x succeeds
    #   with 1 - enchant_table[x]/1000, spells2.c:398, 2549-2553, an artifact half as often; it buys while that is >=
    #   ENCHANT_MIN_CHANCE (50%), Enchant Armor for the armour slots, Enchant Weapon To-Hit/To-Dam for the wielded
    #   weapon, never for the bow, nothing with `order enchant_max=0`) costs the scrolls: price / chance (<= 2 scrolls);
    # - any other step is lost for good: the resale value of that plus (`plus_resale`: itemvalue with the plus one
    #   higher less as it is, x the shop's pay cut) plus its in-play value -- DISEN_IN_PLAY, 0: not priced (geareval
    #   scores gear in XP per real minute, and a gold figure would need how long the item stays in use; nothing knows).
    # (2.45.3 priced every step by scrolls, capped at 100 a step: ~7,850 gold a hit for a (+10,+10) weapon nobody
    # re-enchants.) Prices: what the Alchemist asked last, else ~190 (base 125).
    DISEN_SCROLLS = {"tohit": "Enchant Weapon To-Hit", "todam": "Enchant Weapon To-Dam", "toac": "Enchant Armor"}
    DISEN_SCROLL_PRICE = 190
    DISEN_PLUS_VALUE = 100    # object_value's 100 gold a plus (itemvalue): a plus's worth when the name hides them
    DISEN_IN_PLAY = 0.0       # gold a lost plus costs in play: not priced (above)
    DISEN_UNSHOWN = 5         # plusses not shown (unidentified): valued as if at +5

    def enchant_p(self, x, art=False):
        """The chance one Scroll of Enchant raises a plus that is now x (spells2.c:2549-2553)."""
        c = 1.0 if x < 0 else 0.0 if x > 15 else 1 - self.ENCHANT_TABLE[x] / 1000
        return c * (0.5 if art else 1.0)

    def disen_buys(self, which, x, art, slot):
        """Would plan town buy the scroll that takes this plus from x to x+1? Its rule (enchant_plan,
        weapon_enchant_plan): the step's chance >= ENCHANT_MIN_CHANCE; to-AC on the armour slots, to-hit/to-dam on the
        wielded weapon (never the bow); nothing with `order enchant_max=0`."""
        if int((getattr(self, "orders", None) or {}).get("enchant_max", 25)) <= 0 or slot == "bow":
            return False
        if (which == "toac") == (slot == "weapon"):
            return False
        return self.enchant_p(x, art) >= self.ENCHANT_MIN_CHANCE

    def scroll_price(self, which):
        """What a Scroll of Enchant for this plus costs: the Alchemist's last price, else DISEN_SCROLL_PRICE."""
        try:
            return self.price_of(self.DISEN_SCROLLS[which], 5) or self.DISEN_SCROLL_PRICE
        except Exception:                  # (a bare test Pilot without the store memory)
            return self.DISEN_SCROLL_PRICE

    def _plus_value(self, name):
        try:
            return self.iv(name)
        except AttributeError:              # (no flavour table: a bare test Pilot)
            import itemvalue
            return itemvalue.value(name)

    def _shop_cut(self, tval):
        try:
            return self.pay_cut(tval)
        except Exception:                  # (a bare test Pilot without the shop memory)
            import shopmath
            return shopmath.pay_cut(tval, 3, {})

    def plus_resale(self, name, which, x, weapon):
        """What a shop pays for this item's plus going from x to x+1: itemvalue (the Pilot's iv) with the plus at x+1
        less at x, x the pay cut; DISEN_PLUS_VALUE x the pay cut when the name shows no plusses."""
        rx = r"\(([+-]\d+),([+-]\d+)\)" if weapon else r"\[(\d+),([+-]\d+)\]"
        m = re.search(rx, name)
        v0 = self._plus_value(name)
        if not m:
            return self.DISEN_PLUS_VALUE * self._shop_cut(v0.tval)
        g = 1 if which == "tohit" else 2
        def at(v):
            return name[:m.start(g)] + f"{v:+d}" + name[m.end(g):]
        return max(0, self._plus_value(at(x + 1)).value - self._plus_value(at(x)).value) * self._shop_cut(v0.tval)

    def reenchant_cost(self, which, frm, to, art=False, slot="armour", name=None):
        """(gold of scrolls, gold lost for good) to put a plus back from frm to `to` (which: tohit, todam, toac), step
        by step: price / chance where plan town would buy the scroll (disen_buys), else the plus's resale value
        (plus_resale) + DISEN_IN_PLAY."""
        scrolls = lost = 0.0
        for x in range(frm, to):
            if self.disen_buys(which, x, art, slot):
                scrolls += self.scroll_price(which) / self.enchant_p(x, art)
            else:
                lost += self.plus_resale(name, which, x, slot in ("weapon", "bow")) + self.DISEN_IN_PLAY
        return scrolls, lost

    @staticmethod
    def _disen_steps(x):
        """[(probability, plus after)] for one plus hit by apply_disenchant."""
        if x <= 0:
            return [(1.0, x)]
        return [(0.8, x - 1), (0.2, x - 2)] if x - 1 > 5 else [(1.0, x - 1)]

    def disen_item_loss(self, name, slot):
        """(expected gold an item in this DISEN_SLOTS slot loses to one disenchantment that picks it, valued -- False
        when the plusses weren't shown --, artifact?, (gold of scrolls to put back, gold lost for good)): each lost
        step valued by reenchant_cost (2.46.0), the artifact resistance applied."""
        weapon = slot in ("weapon", "bow")
        v0 = self._plus_value(name)
        art = self.is_artifact(name) or bool(v0.artifact)
        keep = self.DISEN_ART_KEEPS if art else 1.0
        m = re.search(r"\(([+-]\d+),([+-]\d+)\)", name) if weapon else re.search(r"\[(\d+),([+-]\d+)\]", name)
        def lost(which, x):
            out = [0.0, 0.0]
            for p, after in self._disen_steps(x):
                s, l = self.reenchant_cost(which, after, x, art, slot, name)
                out[0], out[1] = out[0] + p * s, out[1] + p * l
            return out
        if not m:
            # plusses not shown (not identified): as if each were +DISEN_UNSHOWN
            u = self.DISEN_UNSHOWN
            parts, valued = ([lost("tohit", u), lost("todam", u)] if weapon else [lost("toac", u)]), False
        elif weapon:
            parts, valued = [lost("tohit", int(m.group(1))), lost("todam", int(m.group(2)))], True
        else:
            parts, valued = [lost("toac", int(m.group(2)))], True
        s, l = keep * sum(a for a, _ in parts), keep * sum(b for _, b in parts)
        return s + l, valued, art, (s, l)

    def disen_loss(self):
        """What one disenchantment that gets through costs on average, over apply_disenchant's 8 slots (1 in 8
        each): (gold, P(it takes a plus), [(slot, item name, gold when picked)], the slots whose plusses weren't
        shown, (gold of scrolls, gold lost for good))."""
        worn = {}
        for i in self.w.items(equip=True):
            s = next((s for s, tvs in self.DISEN_SLOTS if i["tval"] in tvs), None)
            if s and s not in worn:
                worn[s] = i["name"]
        rows, gold, p_takes, flat, split = [], 0.0, 0.0, [], [0.0, 0.0]
        for s, _ in self.DISEN_SLOTS:
            name = worn.get(s)
            g, valued, art, (sc, lo) = self.disen_item_loss(name, s) if name else (0.0, True, False, (0.0, 0.0))
            if not valued:
                flat.append(s)
            rows.append((s, name, round(g)))
            gold += g / len(self.DISEN_SLOTS)
            split[0], split[1] = split[0] + sc / len(self.DISEN_SLOTS), split[1] + lo / len(self.DISEN_SLOTS)
            p_takes += ((self.DISEN_ART_KEEPS if art else 1.0) if g > 0 else 0.0) / len(self.DISEN_SLOTS)
        return gold, p_takes, rows, flat, tuple(split)

    def disenchant_cost(self, race, turns):
        """The expected cost of the disenchantment in a duel of `turns` player turns (fight_sim's mean, else the
        fight estimate's), or None when the monster has no UN_BONUS blow and no disenchantment breath. Its melee
        rounds per player turn as fight_sim counts them: speed_x actions, a spell with the spell chance, a melee round
        costing two actions (MONSTER_RECOIL), x our_slowness; each UN_BONUS blow lands with check_hit at our AC;
        BR_DISE is one of its spells, picked uniformly. Zero with resist disenchantment. A dict: hits (disenchanting
        attacks that land), n (disenchantments that take a plus), gold, per_hit (gold per landed attack), p_hit (per
        blow), rounds, turns, ac, resisted, flat (the slots whose plusses weren't shown), slots ([(slot, item, gold if
        picked)]), scrolls and lost (2.46.0: the gold that is scrolls plan town would buy to put the plusses back, and
        the gold lost for good, at resale)."""
        blows = [b for b in race.blows if (b.split(":")[1:2] or [""])[0] == "UN_BONUS"]
        if "NEVER_BLOW" in race.flags:
            blows = []
        breath = "BR_DISE" in race.spells
        if not blows and not breath:
            return None
        sx = race.speed_x if race.speed_x is not None else max(1.0, (race.speed - 100) / 10)   # (as Race.per_turn)
        pct = (100 // race.spell_freq) / 100 if race.spell_freq else 0.0
        try:
            sx *= self.our_slowness()
        except (AttributeError, TypeError, KeyError):
            pass
        rounds = turns * sx * (1 - pct) / (2 - pct)
        casts = turns * sx * pct / (2 - pct)
        ac = self.w.ind.get("armor", [0])[0] or 0
        i = 20 + 3 * max(1, race.level)                       # (melee1.c:117: power + 3 x level)
        p_hit = 0.05 + 0.90 * max(0, i - (3 * ac) // 4) / i
        hits = rounds * p_hit * len(blows) + (casts / max(1, len(race.spells)) if breath else 0.0)
        out = dict(hits=round(hits, 2), rounds=round(rounds, 1), p_hit=round(p_hit, 3), ac=ac, turns=round(turns, 1),
                   resisted=bool(self.has_ability("res_disen")), n=0.0, gold=0, per_hit=0, flat=[], slots=[],
                   scrolls=0, lost=0)
        if out["resisted"]:
            return out
        gold, p_takes, rows, flat, (sc, lo) = self.disen_loss()
        out.update(n=round(hits * p_takes, 2), gold=round(hits * gold), per_hit=round(gold), flat=flat, slots=rows,
                   scrolls=round(hits * sc), lost=round(hits * lo))
        return out

    def disen_text(self, dc):
        """The hunt check's words for disenchant_cost's dict."""
        if dc["resisted"]:
            return "disenchants: none (you resist disenchantment)"
        split = ""
        if dc.get("scrolls") or dc.get("lost"):
            split = (f" -- ~{dc.get('scrolls', 0)} in scrolls the town kit would buy to put it back, ~{dc.get('lost', 0)} "
                     "lost for good (resale value)")
        return (f"~{dc['n']:.1f} disenchants expected (~{dc['gold']} gold of enchantment{split}: ~{dc['hits']:.1f} "
                f"disenchanting hits in ~{dc['turns']:.0f} turns at {dc['p_hit']:.0%} a blow, ~{dc['per_hit']} gold "
                "each" + (f"; {', '.join(dc['flat'])} valued as if +{self.DISEN_UNSHOWN} (plusses not shown)"
                          if dc["flat"] else "") + "; about half with Speed)")

    SLOTS = (("weapon", (20, 21, 22, 23), 1), ("bow", (19,), 1), ("ring", (45,), 2), ("amulet", (40,), 1),
             ("light", (39,), 1), ("body armour", (36, 37, 38), 1), ("cloak", (35,), 1), ("shield", (34,), 1),
             ("helm", (32, 33), 1), ("gloves", (31,), 1), ("boots", (30,), 1))

    @staticmethod
    def armour_ac(name):
        m = re.search(r"\[(\d+)(?:,([+-]\d+))?\]", name)
        return int(m.group(1)) + int(m.group(2) or 0) if m else None

    def ac_better(self, name, on, tval=None, weight=None, ch=None, margin=0, worn_gives=False):
        """D13 (the user, 11-01): is this armour piece (a pack item's or a shop's name) better AC than `on`, the worn
        piece(s) of its slot? The gear evaluator's verdict (geareval.ac_verdict: more AC by over `margin`, every
        ability and resist kept -- geareval.auto_swap_losses --, no more than 5% less EHP) wherever it can read the
        piece and what's worn; only else a plain AC comparison, with the old guards (never over an artifact, nor over
        a piece whose ego gives what this one lacks, nor -- worn_gives -- one the flags grid shows giving an ability).
        Never over a worn piece that may give an ability unidentified (ability_sources). (ok, the AC shown for the
        piece, the worn piece's)."""
        ac_new = self.armour_ac(name)
        ac_on = min((self.armour_ac(i["name"]) or 0) for i in on) if on else -1
        if on and bare_name(on[0]["name"]).lower() in self.ability_sources:
            return False, ac_new, ac_on
        try:
            ch = ch or self.gear_character()
            try:
                mix = geareval.load_mix(os.path.join(self.rundir, "damage_mix.json"))
            except AttributeError:
                mix = None
            v = geareval.ac_verdict(ch, geareval.Item(name, tval, weight), mix)
        except Exception as e:                 # (the evaluator must not stop the report: the plain rule then)
            self.log("note", text=f"gear evaluator failed on {name}: {e!r}")
            v = None
        if v is not None:
            return v[0] and v[1] > margin, ac_new, ac_on
        if on and (worn_gives or self.is_artifact(on[0]["name"]) or
                   not self.weapon_abilities(on[0]["name"]) <= self.weapon_abilities(name)):
            return False, ac_new, ac_on
        return ac_new is not None and ac_new > ac_on + margin, ac_new, ac_on

    def gear_line(self):
        """Empty slots, and pack items better than what's worn (the Advisor's
        memo §3.2: armour and jewellery against worn or empty slots)."""
        w = self.w
        worn, pack = w.items(equip=True), w.items()
        empty, better = [], []
        ch = []

        def character():           # (the gear evaluator's character, made once when a candidate needs it)
            if not ch:
                try:
                    ch.append(self.gear_character())
                except Exception:
                    ch.append(None)
            return ch[0]
        for slot, tvals, k in self.SLOTS:
            on = [i for i in worn if i["tval"] in tvals]
            cand = [i for i in pack if i["tval"] in tvals and not bad_inscription(i["name"])
                    and not (self.flavour_of(i) or {}).get("junk")]
            if len(on) < k:
                if slot == "light" and cand and not w.depth:
                    continue          # (off in town to save fuel; worn again before leaving it)
                empty.append(slot + (f" (you carry {cand[0]['name']})" if cand else ""))
            elif slot not in ("weapon", "bow", "ring", "amulet", "light"):
                # (D13: the gear evaluator's verdict, as the upgrade step -- never losing an ability or resist: m37's
                # line offered Metal Lamellar [23] over the Leather of Resistance)
                for i in cand:
                    ok, ac, ac_on = self.ac_better(i["name"], on, i["tval"], i["weight"] // max(1, i.get("number", 1)),
                                                   ch=character())
                    if ok:
                        better.append(f"{chr(97 + i['item'])}) {i['name']} (AC {ac} vs {ac_on} worn)")
        return ("Gear: empty slots: " + (", ".join(empty) or "none")
                + ("; better than worn: " + "; ".join(better) if better else ""))

    # --- the gear review (the user, 10-25: a between-mission gear step; read-only) ------------------------------
    # what the abilities are worth to a warrior at 500-1000 ft, best first (the Advisor's memos: paralysis, poison
    # breath, blindness and confusion stop a melee character; hold life and the base four resists next)
    GEAR_WANTED = (("free_act", "Free Action"), ("see_invis", "See Invisible"), ("res_pois", "resist poison"),
                   ("res_blind", "resist blindness"), ("res_conf", "resist confusion"), ("hold_life", "hold life"),
                   ("res_fire", "resist fire"), ("res_cold", "resist cold"), ("res_elec", "resist lightning"),
                   ("res_acid", "resist acid"), ("res_fear", "resist fear"), ("res_nexus", "resist nexus"),
                   ("res_sound", "resist sound"), ("res_shard", "resist shards"), ("res_nether", "resist nether"),
                   ("res_dark", "resist darkness"), ("res_lite", "resist light"), ("slow_digest", "slow digestion"),
                   ("regen", "regeneration"), ("telepathy", "telepathy"), ("speed", "speed"))
    EQUIP_LETTER = "abcdefghijkl"           # the flags grid's columns: weapon, bow, 2 rings, amulet, light, body...
    # jewellery by what it gives (shop names are lower case and cut: "ring of protection [+9]")
    JEWEL_FLAGS = (("free action", "free_act"), ("see invisible", "see_invis"), ("resist poison", "res_pois"),
                   ("resist fire and cold", "res_fire res_cold"), ("resist fire", "res_fire"),
                   ("resist cold", "res_cold"), ("resist lightning", "res_elec"), ("resist acid", "res_acid"),
                   ("slow digestion", "slow_digest"), ("feather fall", "feather"), ("hold life", "hold_life"),
                   ("regeneration", "regen"), ("esp", "telepathy"), ("telepathy", "telepathy"))
    SHOP_SLOT = (("shield", "shield"), ("cap", "helm"), ("helm", "helm"), ("crown", "helm"), ("glov", "gloves"),
                 ("gauntlet", "gloves"), ("cesti", "gloves"), ("boot", "boots"), ("cloak", "cloak"),
                 ("armour", "body armour"), ("mail", "body armour"), ("leather", "body armour"),
                 ("robe", "body armour"), ("rob ", "body armour"))

    def jewel_gives(self, name):
        n = name.lower()
        out = set()
        for key, fl in self.JEWEL_FLAGS:
            if key in n:
                out |= set(fl.split())
                if key == "resist fire and cold":
                    break
        return out

    def redundant_worn(self):
        """[(item, flags, other slot letters)]: worn rings and amulets with no AC or pluses whose every ability
        another worn piece gives too (Dive04's Ring of Resist Cold beside its Leather of Resistance)."""
        flags = self.w.flags or {}
        out = []
        for it in self.w.items(equip=True):
            L = self.EQUIP_LETTER[it["item"] - 24] if 24 <= it["item"] < 24 + len(self.EQUIP_LETTER) else "?"
            gives = [f for f, sl in flags.items() if L in (sl or "")]
            if it["tval"] in (40, 45) and gives and all((flags.get(f) or "").replace(L, "") for f in gives) \
                    and not re.search(r"\[[+-]?\d+|\([+-]\d+", it["name"]):
                out.append((it, gives, sorted({c for f in gives for c in (flags.get(f) or "") if c != L})))
        return out

    def consumables_inv(self):
        """The consumables the simulator uses (shadow_decision's and gear_character's `inv`): potions and scrolls
        counted by name, the Staff of Teleportation's charges (refactor-candidates D5)."""
        w = self.w

        def n(word, tv):
            return sum(i["number"] for i in w.items(tval=tv) if word in i["name"])
        staff = self.find_item("Teleportation", 55)
        m = re.search(r"\((\d+) charges?\)", staff["name"]) if staff else None
        return dict(ccw=n("Cure Critical", TV_POTION), csw=n("Cure Serious", TV_POTION), clw=n("Cure Light", TV_POTION),
                    phase=n("Phase Door", TV_SCROLL), tele=n("Teleportation", TV_SCROLL),
                    staff=int(m.group(1)) if m else 0, wor=n("Word of Recall", TV_SCROLL), speed=n("Speed", TV_POTION),
                    berserk=n("Berserk", TV_POTION), hero=n("Heroism", TV_POTION))

    def gear_character(self):
        """The character for the gear evaluator (geareval.py): the sheet's stats, HP and AC, the worn gear (with each
        piece's weight from the inventory), the sheet's abilities, the consumables the simulator uses."""
        w = self.w
        worn = {}
        for i in w.items(equip=True):
            it = geareval.Item(i["name"], i["tval"], i["weight"] // max(1, i.get("number", 1)))
            if it.slot:
                worn.setdefault(it.slot, []).append(it)
        stats = {n: (w.ind.get(f"stat{k}") or [3])[0] for k, n in enumerate(self.STAT_NAMES)}
        flags = {("SEE_INVIS" if f == "see_invis" else f.upper()) for f, on in (w.flags or {}).items() if on}
        inv = self.consumables_inv()
        depth = int(self.orders.get("max_depth", 0)) or (self.deepest_ft or 500)
        ch = geareval.Character(w.clvl, stats, w.hp[1], (w.ind.get("armor") or [0])[0] or 0, worn, flags=flags,
                                depth_ft=depth, inv=inv, pack_weight=sum(i["weight"] for i in w.items()))
        # (2.58.0: the worn gear's acid and disenchantment cost per hit, for the simulator's scenarios -- the current
        # loadout's, for every option compared)
        try:
            ch.acid_gold, ch.disen_gold = self.gear_damage_gold()
        except Exception:
            pass
        return ch

    def gear_eval(self, items, n=10, no_loss=False):
        """The item slot evaluator on these pack items (or names): geareval.compare_slot. Cached per item and gear."""
        ch = self.gear_character()
        cands = [geareval.Item(i["name"], i["tval"], i["weight"] // max(1, i.get("number", 1))) if isinstance(i, dict)
                 else geareval.Item(i) for i in items]
        key = (tuple(c.name for c in cands), tuple(sorted(i.name for v in ch.worn.values() for i in v)),
               tuple(sorted(ch.sheet["stats"].items())), ch.clvl, ch.depth_ft, no_loss, n)
        cache = self.gear_eval_cache
        if key not in cache:
            try:
                killed = set(json.load(open(os.path.join(self.rundir, "uniques_killed.json"))))
            except (OSError, ValueError):
                killed = set()
            cache[key] = geareval.compare_slot(ch, cands, n=n, no_loss=no_loss, skip=killed,
                                               decisions=os.path.join(self.rundir, "decisions.jsonl"),
                                               xp_per_gold=self.xp_per_gold(),
                                               mix=geareval.load_mix(os.path.join(self.rundir, "damage_mix.json")))
        return cache[key]

    def loadout_info(self, shops=False):
        """`loadout [shops]`: the optimizer's best few loadouts from the pack (and shop stock) against what's worn."""
        w = self.w
        ch = self.gear_character()
        pool = [geareval.Item(i["name"], i["tval"], i["weight"] // max(1, i.get("number", 1))) for i in w.items()
                if i["tval"] in geareval.SLOT_OF_TVAL and i["tval"] not in (TV_LITE, 19) and self.iv(i["name"]).known
                and not bad_inscription(i["name"])]
        budget = 0
        if shops:
            budget = max(0, w.ind.get("gold", [0])[0] - self.town_reserve())
            for store, st in sorted(self.stores_seen.items()):
                for name, price in (st.get("prices") or {}).items():
                    it = geareval.Item(name)
                    if it.slot and it.slot not in ("light", "bow") and price <= budget:
                        it.price, it.store = price, store
                        pool.append(it)
        try:
            killed = set(json.load(open(os.path.join(self.rundir, "uniques_killed.json"))))
        except (OSError, ValueError):
            killed = set()
        try:
            res = geareval.optimize(ch, pool, budget=budget, n=10, skip=killed,
                                    decisions=os.path.join(self.rundir, "decisions.jsonl"),
                                    xp_per_gold=self.xp_per_gold(),
                                    mix=geareval.load_mix(os.path.join(self.rundir, "damage_mix.json")))
        except Exception as e:
            return f"loadout optimizer failed: {e!r}"
        head = (f"loadout: {res['searched']['loadouts']} loadouts of one or two slot changes searched (pack"
                + (f" + shop stock within {budget} gold" if shops else "") + "; every ability and resist worn is kept; "
                "the best few simulated, slays, brands and criticals included; the ~N/round figures leave out "
                "slays).")
        if len(res["options"]) == 1:
            return head + "\nnothing to try: no loadout keeps your abilities and resists and looks better on paper"
        out = [head, geareval.report(res)]
        if res["best"] != "current":
            out.append("to do: " + "; ".join((f"buy {a} ({p} g), then " if p else "") + f"wear {a}"
                                             for a, _, p in res["changes"][res["best"]] if a))
        return "\n".join(out)

    def gear_better(self, it):
        """(the evaluator's chosen option, (item, replaced)) when wearing this identified pack item beats what's worn
        (town only: a run takes ~2-3 s; never one that loses Free Action, See Invisible, resist blindness or
        confusion, hold life -- geareval.NO_LOSS; with TRADE_RESISTS off, none that loses any ability or resist), else
        None."""
        w = self.w
        if w.depth or w.in_dungeon or it.get("equip") or it["tval"] not in geareval.SLOT_OF_TVAL or \
                it["tval"] == TV_LITE or bad_inscription(it["name"]) or \
                not self.iv(it["name"]).known or (self.flavour_of(it) or {}).get("junk"):
            return None
        try:
            # (nothing it could improve -- damage, AC, HP, speed, an ability -- no simulation: most loot)
            ch = self.gear_character()
            gi = geareval.Item(it["name"], it["tval"], it["weight"] // max(1, it.get("number", 1)))
            cur = ch.derive()
            if not gi.slot or not any(
                    (d["dmg"] > cur["dmg"] or d["ac"] > cur["ac"] or d["mhp"] > cur["mhp"] or d["speed"] > cur["speed"]
                     or d["flags"] - cur["flags"])
                    for d in (ch.derive(ch.swap(gi, j)) for j in range(2 if gi.slot == "ring" else 1))):
                return None
            res = self.gear_eval([it], no_loss=True)
        except Exception as e:                 # (the evaluator must not stop the town visit)
            self.log("note", text=f"gear evaluator failed on {it['name']}: {e!r}")
            return None
        if res["best"] == "current":
            return None
        self.log("gear_eval", item=it["name"], best=res["best"], score={k: round(v, 3) for k, v in res["score"].items()})
        return res["best"], res["swaps"][res["best"]]

    def gear_review(self):
        """Gear as a whole, for the between-mission step: abilities had and missing, worn pieces whose abilities
        another piece already gives (a free slot), pack items better than worn, and shop stock (as last seen) that
        would improve a slot within the gold the essentials leave. Read-only: it changes nothing."""
        w = self.w
        worn, pack = w.items(equip=True), w.items()
        flags = w.flags or {}
        gold = w.ind.get("gold", [0])[0]
        spare = gold - self.town_reserve()
        r = self.xp_per_gold()
        out = [f"Gold {gold} ({max(0, spare)} beyond the essentials' reserve); AC {(w.ind.get('armor') or [0])[0]}; "
               f"XP per gold (recent play) {r}: 1000 gold costs ~{1000 * r:.0f} XP of playing time"]
        have = [lab for f, lab in self.GEAR_WANTED if flags.get(f)]
        miss = [lab for f, lab in self.GEAR_WANTED if not flags.get(f)]
        out.append("Abilities: " + (", ".join(have) or "none") + " | missing, most wanted first: " +
                   (", ".join(miss[:8]) or "none"))

        def letter(it):
            return self.EQUIP_LETTER[it["item"] - 24] if 24 <= it["item"] < 24 + len(self.EQUIP_LETTER) else "?"
        # worn pieces whose every ability is given by another piece too, and no AC or pluses of their own
        free = [(it, f"{letter(it)}) {it['name']}: {', '.join(gives)} also from {', '.join(o + ')' for o in others)}")
                for it, gives, others in self.redundant_worn()]
        if free:
            out.append("Redundant (the slot is free for something else): " + "; ".join(t for _, t in free))
        # the pack, against what's worn
        gl = self.gear_line()
        out.append(gl)
        # shops, as last seen
        ideas = []
        worn_ac = {}
        ch = []

        def character():
            if not ch:
                try:
                    ch.append(self.gear_character())
                except Exception:
                    ch.append(None)
            return ch[0]
        for slot, tvals, k in self.SLOTS:
            on = [i for i in worn if i["tval"] in tvals]
            worn_ac[slot] = (min((self.armour_ac(i["name"]) or 0) for i in on) if len(on) >= k else -1,
                             any(letter(i) in "".join(str(v or "") for v in flags.values()) for i in on), on)
        free_tv = {it["tval"] for it, _ in free}
        for store, st in sorted(self.stores_seen.items()):
            mult = 1
            for name, price in (st.get("prices") or {}).items():
                if price > max(0, spare):
                    continue
                # (with the exact buy line: m41 bought "set_of_leather_gloves" and got the plain [1,+0] for 5 gold,
                # not the [1,+5] suggested -- the cheapest line of a name is taken)
                lab = f"{name} for {price} at the {self.STORE_LABEL.get(store, store)} ({store}) " \
                      f"[`buy {store}/{name.replace(' ', '_')}@{int(price * 1.1)}`]"
                if name.startswith(("ring of", "amulet of")):
                    tv = 45 if name.startswith("ring") else 40
                    gives = self.jewel_gives(name) - {f for f, sl in flags.items() if sl}
                    pr = re.search(r"protection \[\+(\d+)\]", name)
                    slot_free = tv in free_tv or sum(1 for i in worn if i["tval"] == tv) < (2 if tv == 45 else 1)
                    if slot_free and (gives or pr):
                        ideas.append(lab + (f": {', '.join(sorted(gives))}" if gives else f": +{pr.group(1)} AC")
                                     + " (in the free slot)")
                    elif gives & {"free_act", "see_invis", "res_pois", "hold_life"}:
                        ideas.append(lab + f": {', '.join(sorted(gives))} (needs a slot)")
                    continue
                slot = next((sl for key, sl in self.SHOP_SLOT if key in name), None)
                ac = self.armour_ac(name)
                if not slot or ac is None or slot not in worn_ac:
                    continue
                ac_on, gives_flags, on = worn_ac[slot]
                # (D13: the gear evaluator's verdict, more than 2 AC better; the plain rule only for what it can't
                # read, and then never over a worn piece that gives an ability: AC alone isn't worth losing it)
                if not self.ac_better(name, on, ch=character(), margin=2, worn_gives=gives_flags)[0]:
                    continue
                ideas.append(lab + f": AC {ac} vs {max(ac_on, 0)} worn ({slot})")
        out.append("Shop ideas (prices last seen): " + ("; ".join(ideas[:8]) if ideas else "none within the gold"))
        # stats and standing restores
        drained = [n for i, n in enumerate(self.STAT_NAMES) if len(w.ind.get(f"stat{i}", [])) >= 2
                   and w.ind[f"stat{i}"][0] < w.ind[f"stat{i}"][1]]
        if drained:
            out.append("Drained: " + ", ".join(drained) + " (Restore at the Alchemist ~" +
                       f"{self.price_of('Restore Strength', 5) or 480}; STR and DEX set the blows, CON the HP)")
        if not any(i["tval"] == 19 for i in worn):
            out.append("Bow slot empty (the Pilot doesn't shoot: a launcher is only worth it for its abilities)")
        return "\n".join(out)
