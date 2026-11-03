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


def shadow_agree(choice, actual, table):
    """(agree, the actual action's row) for an estimator answer: the estimator chose the action the Pilot took; or it
    kept its copy of the rules ("rules") and the action the Pilot took (when the table has a row for it) is safe and
    within noise of the best row (2 SE, at least 10 XP net of gold)."""
    rows = {t.get("option"): t for t in table or ()}
    row = rows.get(actual) if actual != "rules" else None
    if choice == actual:
        return True, row
    if choice == "rules":
        if row is None:
            return True, None
        best = max((t.get("dxp", 0) for t in rows.values() if t.get("safe")), default=0)
        return bool(row.get("safe")) and row.get("dxp", 0) >= best - max(10, 2 * (row.get("se") or 0)), row
    return False, row


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
        p.update(extra_p or {})
        # (name, distance, hp_frac, awake): options_sim 26h takes the asleep flag per member (the `look` answers; None =
        # unknown, the p_awake share then 0.4 stand in) -- the Advisor: 7 Wargs, six at 4 squares, ~11 HP lost if
        # known asleep, ~55 awake, ~23 unknown
        team = [(r.name, max(1, sh.sim.adist(y - w.pos[0], x - w.pos[1])), None,
                 None if self.is_asleep(y, x) is None else not self.is_asleep(y, x))
                for y, x, r in w.monsters] if w.pos else []
        # (and what the server's list names but the map doesn't show yet, 3 squares off: A2K's first emergency had
        # Khim in the list only, and the estimator played an empty fight)
        team += [(r.name, 3) for r in (w.listed_only() if hasattr(w, "listed_only") else [])]
        snap = {"p": p, "team": team, "rules": rules or shadow.rules_option(detail), "rules_detail": (detail or "")[:160],
                "wall": time.time(), "factor": time_factor(), "speed": (w.ind.get("speed") or [0])[0] or 0,
                "options": list(options) if options else None, "trigger": trigger, "xp_per_gold": self.xp_per_gold()}
        return sh.submit(snap)

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
            agree, actual_row = shadow_agree(r.get("choice"), snap.get("rules"), r.get("table"))
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
        nor 20 s of the last. The rules' choice here is Berserk when berserk_tick would quaff it, else fighting on.
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
        fast = any("of Speed" in i["name"] for i in w.items(tval=TV_POTION)) and not self.buff_on("fast") and \
            waited(self.speed_start_t, 30)
        label = "speed+berserk" if fast and berserk else "speed" if fast else "berserk" if berserk else "fight"
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
    DISEN_FLAT = 100          # (unused since 2.45.3: a plus is valued by the scrolls to put it back)
    DISEN_ART_KEEPS = 0.4     # an artifact loses a plus 40% of the time (spells1.c:1345)
    # A plus lost is worth the scrolls that put it back (2.45.3, the user: "+10 is worth a lot more than +5"): a
    # scroll at plus x succeeds with 1 - enchant_table[x]/1000 (spells2.c:398, 2549-2553; x < 0 always, x > 15 never;
    # an artifact half as often), so a step x -> x+1 costs price / chance; each step capped at DISEN_MAX_SCROLLS
    # (+10 and up: 1% or less; +15: never by scroll). Prices: what the Alchemist asked last, else ~190 (base 125).
    DISEN_SCROLLS = {"tohit": "Enchant Weapon To-Hit", "todam": "Enchant Weapon To-Dam", "toac": "Enchant Armor"}
    DISEN_SCROLL_PRICE = 190
    DISEN_MAX_SCROLLS = 100
    DISEN_UNSHOWN = 5         # plusses not shown (unidentified): valued as if at +5

    def enchant_p(self, x, art=False):
        """The chance one Scroll of Enchant raises a plus that is now x (spells2.c:2549-2553)."""
        c = 1.0 if x < 0 else 0.0 if x > 15 else 1 - self.ENCHANT_TABLE[x] / 1000
        return c * (0.5 if art else 1.0)

    def reenchant_cost(self, which, frm, to, art=False):
        """Expected gold of scrolls to raise a plus from frm back to `to` (which: tohit, todam, toac)."""
        kind = self.DISEN_SCROLLS[which]
        try:
            price = self.price_of(kind, 5) or self.DISEN_SCROLL_PRICE
        except Exception:                  # (a bare test Pilot without the store memory)
            price = self.DISEN_SCROLL_PRICE
        return sum(price * min(self.DISEN_MAX_SCROLLS, 1 / max(self.enchant_p(x, art), 1e-9)) for x in range(frm, to))

    @staticmethod
    def _disen_steps(x):
        """[(probability, plus after)] for one plus hit by apply_disenchant."""
        if x <= 0:
            return [(1.0, x)]
        return [(0.8, x - 1), (0.2, x - 2)] if x - 1 > 5 else [(1.0, x - 1)]

    def disen_item_loss(self, name, weapon):
        """(expected gold an item loses to one disenchantment that picks its slot, valued -- False when the plusses
        weren't shown --, artifact?): since 2.45.3 the scrolls that put the plusses back (reenchant_cost; it was the
        shop value of the plusses, 100 gold each), the artifact resistance applied."""
        def val(n):
            try:
                return self.iv(n)
            except AttributeError:              # (no flavour table: a bare test Pilot)
                import itemvalue
                return itemvalue.value(n)
        v0 = val(name)
        art = self.is_artifact(name) or bool(v0.artifact)
        keep = self.DISEN_ART_KEEPS if art else 1.0
        m = re.search(r"\(([+-]\d+),([+-]\d+)\)", name) if weapon else re.search(r"\[(\d+),([+-]\d+)\]", name)
        def lost(which, x):
            return sum(p * self.reenchant_cost(which, after, x, art) for p, after in self._disen_steps(x))
        if not m:
            # plusses not shown (not identified): as if each were +DISEN_UNSHOWN
            u = self.DISEN_UNSHOWN
            return keep * (lost("tohit", u) + lost("todam", u) if weapon else lost("toac", u)), False, art
        if weapon:
            return keep * (lost("tohit", int(m.group(1))) + lost("todam", int(m.group(2)))), True, art
        return keep * lost("toac", int(m.group(2))), True, art

    def disen_loss(self):
        """What one disenchantment that gets through costs on average, over apply_disenchant's 8 slots (1 in 8
        each): (gold, P(it takes a plus), [(slot, item name, gold when picked)], the slots valued flat)."""
        worn = {}
        for i in self.w.items(equip=True):
            s = next((s for s, tvs in self.DISEN_SLOTS if i["tval"] in tvs), None)
            if s and s not in worn:
                worn[s] = i["name"]
        rows, gold, p_takes, flat = [], 0.0, 0.0, []
        for s, _ in self.DISEN_SLOTS:
            name = worn.get(s)
            g, valued, art = self.disen_item_loss(name, s in ("weapon", "bow")) if name else (0.0, True, False)
            if not valued:
                flat.append(s)
            rows.append((s, name, round(g)))
            gold += g / len(self.DISEN_SLOTS)
            p_takes += ((self.DISEN_ART_KEEPS if art else 1.0) if g > 0 else 0.0) / len(self.DISEN_SLOTS)
        return gold, p_takes, rows, flat

    def disenchant_cost(self, race, turns):
        """The expected cost of the disenchantment in a duel of `turns` player turns (fight_sim's mean, else the
        fight estimate's), or None when the monster has no UN_BONUS blow and no disenchantment breath. Its melee
        rounds per player turn as fight_sim counts them: speed_x actions, a spell with the spell chance, a melee round
        costing two actions (MONSTER_RECOIL), x our_slowness; each UN_BONUS blow lands with check_hit at our AC;
        BR_DISE is one of its spells, picked uniformly. Zero with resist disenchantment. A dict: hits (disenchanting
        attacks that land), n (disenchantments that take a plus), gold, per_hit (gold per landed attack), p_hit (per
        blow), rounds, turns, ac, resisted, flat (the slots valued flat), slots ([(slot, item, gold if picked)])."""
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
                   resisted=bool(self.has_ability("res_disen")), n=0.0, gold=0, per_hit=0, flat=[], slots=[])
        if out["resisted"]:
            return out
        gold, p_takes, rows, flat = self.disen_loss()
        out.update(n=round(hits * p_takes, 2), gold=round(hits * gold), per_hit=round(gold), flat=flat, slots=rows)
        return out

    def disen_text(self, dc):
        """The hunt check's words for disenchant_cost's dict."""
        if dc["resisted"]:
            return "disenchants: none (you resist disenchantment)"
        return (f"~{dc['n']:.1f} disenchants expected (~{dc['gold']} gold of enchantment: ~{dc['hits']:.1f} "
                f"disenchanting hits in ~{dc['turns']:.0f} turns at {dc['p_hit']:.0%} a blow, ~{dc['per_hit']} gold "
                "each" + (f"; {', '.join(dc['flat'])} valued flat at {self.DISEN_FLAT} a plus" if dc["flat"] else "")
                + "; about half with Speed)")

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
        return geareval.Character(w.clvl, stats, w.hp[1], (w.ind.get("armor") or [0])[0] or 0, worn, flags=flags,
                                  depth_ft=depth, inv=inv, pack_weight=sum(i["weight"] for i in w.items()))

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
        confusion, hold life -- geareval.NO_LOSS), else None."""
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
