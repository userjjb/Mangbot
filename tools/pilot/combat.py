"""combat -- the Pilot's combat and survival side, as a mixin of Pilot (refactor-candidates E1; docs/pilot-combat.md):
the reflexes (reflexes, in priority order) and the emergency escape (escape) -- each one method per step, in the order
of REFLEX_STEPS / ESCAPE_STEPS (E3) -- with escape's helpers (emergency_loop, phase_futile, escaping_to_stairs,
kill_caster_step, teleport_item, use_stair_location, log_escape, count_escape),
what counts as dangerous (danger_why, worst_3turns, sim_loss, dangers, has_ability), the fight rules
(engage_tick, group_danger/group_tick, still_fight_tick, status_tick, unseen_tick, choke_tick with choke_tier,
confusion_lock/confusion_window, speed_start_tick, berserk_tick, hard_fight, fear_cure, buff_on, our_slowness), the
movement helpers (sidestep, retreat_step, quiet_spot), flee_failed, the Navigator's react rules (rules, rule_tick)
and the watches (watch_band/band_cost/band_live, watch_character, watch_drainers, watch_thieves, watch_traps,
watch_breeders, watch_kills, watch_perception, watch_progress). The Advisor's estimator mirrors escape, group_tick,
speed_start_tick, berserk_tick and fear_cure by name (Advisor/data/estimator/options_sim.py POLICY_VERSION): they
stay Pilot's, as every method here does -- they read and write the Pilot's state through self; pilot.py imports
this module's names back (P.heal_of, P.choke_tier, P.STATUS_CURES, ...).
"""
import collections
import json
import math
import os
import re
import types

from common import TV_SCROLL, TV_POTION, TV_FOOD, TV_LITE, plural, one_of
from world import gnow, waited
from mover import direction, passable
from goals import (Wait, Goto, Explore, Dive, Search, Hunt, Recover, BandLeave, WalkAway, Flee, Recall,
                   Resurrect, RestGoal)
from town_goals import TownFarm, Shop


# a reflexes()/escape() step that didn't act: go on to the next one (REFLEX_STEPS, ESCAPE_STEPS)
NEXT = object()

CURE_POTIONS = ("Cure Critical Wounds", "Cure Serious Wounds", "Cure Light Wounds", "Healing")
# HP each potion heals (server use-obj.c:483-540; CSW 20-24, CCW 25-29). Longest
# names first, so "*Healing*" isn't read as "Healing".
HEALS = (("*Healing*", 1200), ("Cure Critical Wounds", 25), ("Cure Serious Wounds", 20),
         ("Cure Light Wounds", 15), ("Healing", 300), ("of Life", 5000))


def choke_tier(mem, pos):
    """How well a square limits a pack's access (lower is better), None for
    open ground. Corridors here are two wide (WIDE_CORRIDORS; doors come in
    pairs; Advisor memo A5), so a square with <= 2 open neighbours (dead end,
    one-wide tunnel) is rare: 0 = that, 1 = <= 3 (a corner or the end of a
    two-wide corridor), 2 = a straight two-wide corridor (<= 5 neighbours and
    <= 10 open squares in the 5x5 around; a room's edge has 14)."""
    y, x = pos
    def is_open(p):
        return mem.get(p, " ") not in "#%*: "
    near = sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy or dx) and is_open((y + dy, x + dx)))
    if near <= 2:
        return 0
    if near <= 3:
        return 1
    area = sum(1 for dy in range(-2, 3) for dx in range(-2, 3) if (dy or dx) and is_open((y + dy, x + dx)))
    return 2 if near <= 5 and area <= 10 else None


def heal_of(name):
    return next((hp for n, hp in HEALS if n in name), 0)

# What each potion cures (Advisor memo, Erratum: server use-obj.c:483-545).
# Only CCW and better cure stun and poison; CLW only reduces confusion.
# Cheapest first.
STATUS_CURES = {
    "stun": ("Cure Critical Wounds", "Healing", "*Healing*", "of Life"),
    "poisoned": ("Cure Poison", "Neutralize Poison", "Cure Critical Wounds", "Healing", "*Healing*", "of Life"),
    "confused": ("Cure Serious Wounds", "Cure Critical Wounds", "Healing", "*Healing*", "of Life"),
    "blind": ("Cure Light Wounds", "Cure Serious Wounds", "Cure Critical Wounds", "Healing", "*Healing*",
              "of Life"),
}


class CombatMixin:
    """Pilot's combat and survival methods (`class Pilot(ReportMixin, GearMixin, ItemsMixin, TownMixin,
    CombatMixin)`: every name stays on Pilot)."""

    ESCAPE_WHY = re.compile(r"low HP|flee|danger|emergency|monsters close|phasing|group|potions too weak|"
                            r"last resort|unseen|afraid|cornered", re.I)

    def log_escape(self, line, why):
        """An `escape` record for every escape sent (the Advisor's scorecard memo
        §5.3): kind, trigger, HP. Its result shows in the records after it."""
        w = self.w
        kind = None
        m = re.match(r"custom r item=(\d+)", line)
        if m:
            it = next((i for i in w.items() if i["item"] == int(m.group(1))), None)
            name = it["name"] if it else why
            if "Phase Door" in name or "phase door" in why.lower():
                kind = "phase"
            elif "Word of Recall" in name or "word of recall" in why.lower():
                kind = "wor_escape" if (w.in_dungeon and (self.ESCAPE_WHY.search(why) or w.hp_frac < 0.5)) \
                    else "wor_travel"
            elif "Teleport" in name:
                kind = "teleport"
        elif re.match(r"custom [<>]$", line) and (isinstance(self.goal, (Flee, Recover)) or self.ESCAPE_WHY.search(why)
                                                    or gnow() - self.escalation_t < 10):
            kind = "stairs"
        if kind:
            self.last_escape = (gnow(), kind, why[:120], list(w.hp[:2]))
            self.log("escape", escape=kind, trigger=why[:120], hp=w.hp[:2],
                     adjacent=[r.name for *_, r in w.adjacent_monsters()][:6],
                     goal=self.goal.describe() if self.goal else None)

    def confusion_lock(self):
        """Confused 8 s on end with the goal waiting or monsters adjacent: cure it (m55: 27 Hummerhorns at 800 ft
        kept Dive04 confused from 17:04 to 17:19 -- the dive waited "for it to wear off", two staff uses failed
        (confusion halves device skill), the recall couldn't be read; the Navigator quaffed CCW/CSW by hand). The
        cheapest that ends it (Cure Serious, then Critical: use-obj.c), at most every 8 s; in the clear window the
        goal (or the breeders' teleport, a read) acts."""
        w, now = self.w, gnow()
        if not w.flag("confused"):
            self.conf_since = None
            return False
        self.conf_since = self.conf_since or now
        if now - self.conf_since < 8 or not waited(self.conf_cure_t, 8) or now < self.busy_until:
            return False
        pot = next((i for k in ("Cure Serious", "Cure Critical") for i in w.items(tval=TV_POTION) if k in i["name"]),
                   None)
        n = self.conf_cures
        if not pot or n.get(w.level_t, 0) >= 4:          # (a swarm re-confuses: at most 4 cures a level)
            return False
        n[w.level_t] = n.get(w.level_t, 0) + 1
        self.conf_cure_t = now
        self.cmd(f"custom q item={pot['item']}", f"confused {now - self.conf_since:.0f} s: quaff {pot['name']}",
                 hold=0.6)
        self.notify("tactic", f"confused for {now - self.conf_since:.0f} s"
                              + (f" with {len(w.adjacent_monsters())} adjacent" if w.adjacent_monsters() else "")
                              + f": quaffed {one_of(pot['name'])} to act again", news=True)
        return True

    def confusion_window(self):
        """Just cured of a confusion lock, with 3+ monsters adjacent: teleport away in the clear second before the next
        bite (M5, 10-28: 26 Hummerhorns re-confused Dive04 within a second of each of 4 cures; the m55 Navigator's
        way out was a cure and an immediate read). The goal carries on from the landing, unconfused."""
        w, now = self.w, gnow()
        t = self.conf_cure_t
        if not (w.in_dungeon and 0.3 < now - t < 4 and not w.flag("confused") and now >= self.busy_until) or \
                self.conf_tele_t >= t or len(w.adjacent_monsters()) < 3:
            return False
        tp = self.teleport_item()
        if not tp:
            return False
        self.conf_tele_t = now
        self.cmd(f"custom {tp[0]} item={tp[1]['item']}", f"clear for a moment among {len(w.adjacent_monsters())}: "
                                                          f"teleport away ({one_of(tp[1]['name'])})", hold=0.8)
        self.notify("tactic", f"cured, with {len(w.adjacent_monsters())} adjacent: teleported away before the next "
                              "bite", news=True)
        return True

    def danger_why(self, r, pack_breath=0):
        """Why monster race r is too dangerous to fight now, or None."""
        lev = self.w.clvl
        hp = self.w.hp[0]
        o = self.orders
        if r.level >= lev + o["danger_level"]:
            return f"lvl {r.level}"
        if "UNIQUE" in r.flags and r.level > lev:
            return f"unique, lvl {r.level}"
        # The Advisor's danger table (memo 2026-09-27 §3): 5 = leave on sight;
        # 4 = lethal until we've outgrown it by about 8 levels
        # (a rating the rulebook marks as about strength alone is the duel simulator's to judge, below:
        # Ulfast fled on sight as "rated 4" while the hunt check allowed him -- the set-piece harness)
        strength_only = getattr(r, "veto_reason", None) == "strength"
        if r.danger == 5 and not strength_only:
            return "rated 5: leave on sight"
        if r.danger == 4 and lev < r.level + 8 and not strength_only:
            return f"rated 4: lethal until clvl {r.level + 8}"
        # A fast unique near our level: we can't walk away from it (mission 9:
        # Bullroarer, +10, cost 93 -> 51 HP while the pilot backed away)
        sx = r.speed_x if r.speed_x is not None else max(1.0, (r.speed - 100) / 10)
        if "UNIQUE" in r.flags and sx >= 2 and r.level >= lev - 8 and r.per_turn >= max(hp, 1) / 8:
            return f"fast unique (x{sx:.0f} speed)"
        # A capital D is an ancient dragon (level 40+), always out of depth here
        if r.char == "D":
            return "ancient dragon"
        # Fast heavy melee (Azog, Beorn, the chieftains passed every other rule)
        if r.per_turn >= max(hp, 1) / 3 and "NEVER_MOVE" not in r.flags:
            return f"melee ~{r.per_turn:.0f} per turn"
        # Engage a breather only if two of its breaths can't kill us (Advisor
        # memo, Addendum 2 item 8); a pack of breathers (hounds) breathes together
        if r.max_breath and 2 * r.max_breath >= hp:
            return f"breathes up to {r.max_breath}"
        if r.max_breath and pack_breath >= hp:
            return f"its pack breathes up to {pack_breath} in all"
        # (a paralysing blow whose to-hit can't beat our armour lands only on the
        # 5% floor, e.g. a floating eye: memo §3.7; Hold spells still count)
        ac = self.w.ind.get("armor", [0])[0]
        weak_blow = "HOLD" not in r.spells and 0 < r.paralyse_blow_power <= ac * 3 / 4
        if r.paralyser and not self.has_ability("free_action") and r.level >= lev - 10 and not weak_blow:
            return "paralyses (no Free Action)"
        if "BRAIN_SMASH" in r.spells and not all(self.has_ability(k) for k in
                                                   ("free_action", "resist_blind", "resist_conf")):
            return "Brain Smash (needs Free Action + resist blindness + resist confusion)"
        # Blinding/confusing blows get no saving throw (memo §1.3). Stationary
        # ones are only stepped away from (and never fought, still_fight_tick).
        nosave = {e for e in r.no_save_blows
                  if not self.has_ability("resist_blind" if e == "BLIND" else "resist_conf")}
        if nosave and "NEVER_MOVE" not in r.flags and r.level >= lev - 10:
            return ("blinds" if "BLIND" in nosave else "confuses") + " with its blows (no save)"
        # A fight we'd lose on average, by the Advisor's duel simulator (the set-piece harness: Lugdush, lvl
        # 21 and unrated, fired no rule though a fight costs ~350 HP of 265)
        sim = self.sim_loss(r) if r.level >= lev - 3 and "NEVER_MOVE" not in r.flags else None
        if sim and sim > 0.8 * max(1, self.w.hp[0]):
            return f"a fight costs ~{sim:.0f} HP on average (the duel simulator)"
        # Summons land next to us and stay after the summoner dies (memo §1.2)
        if r.summoner and r.level >= lev - 5:
            return "summons"
        return None

    def worst_3turns(self, races):
        """The rulebook's worst melee in the next 3 player turns at our AC (worst_3turns_acNN: the AC
        reduction of HURT blows, recoil, speed), summed over the monsters, with a caster's spell_max if
        higher; the old 2.5 raw worst rounds when a race has no row."""
        rows = self.fight_rows()
        ac = (self.w.ind.get("armor") or [0])[0] or 0
        col = min((20, 40, 60), key=lambda a: abs(a - ac))
        total = 0.0
        for r in races:
            row = rows.get(getattr(r, "idx", None)) or {}
            if row.get(f"worst_3turns_ac{col}"):
                v = float(row[f"worst_3turns_ac{col}"])
                if r.spells:
                    v = max(v, float(row.get("spell_max") or 0))
            else:
                v = 2.5 * (r.worst_melee[0] or 0) * (r.speed_x or 1)
            total += v
        return total * self.our_slowness()      # (three of our turns are longer when we're slowed: m26)

    def sim_loss(self, r):
        """fight_sim's mean HP lost dueling r at our current profile, cached by race, level,
        weapon, AC and HP to the nearest 10% (300 duels, ~0.05 s for a new key)."""
        w = self.w
        wt = [x for x in self.weapon_table() if x[3]]
        key = (getattr(r, "idx", None), w.clvl, wt[0][0] if wt else None, (w.ind.get("armor") or [0])[0],
               round(w.hp_frac * 10))
        cache = self._sim_cache
        if key not in cache:
            sm = self.fight_sim(r, n=300)
            cache[key] = sm["loss_mean"] if sm else None
        return cache[key]

    def dangers(self):
        mons = self.w.monsters
        pack_breath = sum(r.max_breath for *_, r in mons)
        return [r for _, _, r in mons if self.danger_why(r, pack_breath)]

    def danger_text(self, r):
        pack_breath = sum(x.max_breath for *_, x in self.w.monsters)
        return f"{r.name} ({self.danger_why(r, pack_breath) or f'lvl {r.level}'})"

    # --- the rules -----------------------------------------------------------

    # One method per step, in REFLEX_STEPS's order (refactor-candidates E3): each takes the per-call context `ctx`
    # (w, o and now, read once per call; the values the steps share, set by the step that computes them) and
    # returns NEXT to go on, or the value reflexes() returns. The order is the rule: docs/pilot-combat.md §2.
    REFLEX_STEPS = (
        "_reflex_death",            # 0. dead (a ghost): nothing else runs
        "_reflex_busy",             # 0. an action on its way; inside a store during a Shop goal
        "_reflex_survey",           # (not a rule: ctx.mons_near, the monsters within 7, for the steps below)
        "_reflex_emergency",        # 2. emergency: escape()
        "_reflex_group",            # 2'. group danger (group_tick)
        "_reflex_hard_fight",       # 2a. a hard fight's start: speed_start_tick, berserk_tick
        "_reflex_status",           # 2a. status cures (status_tick)
        "_reflex_arrival",          # 3. arrival into danger
        "_reflex_danger_in_view",   # 3a. something far above our level in view
        "_reflex_unseen",           # 3b. an unseen attacker (unseen_tick)
        "_reflex_choke",            # 3c. a pack in the open: back into a corridor (choke_tick)
        "_reflex_summon_trap",      # 3d. a summon trap: Phase Door
        "_reflex_slowed",           # 3e. slowed in a fight: a Potion of Speed
        "_reflex_afraid",           # 3f. afraid
        "_reflex_still",            # 3g. monsters that never move, adjacent
        "_reflex_fearers",          # 3h. monsters that frighten again and again
        "_reflex_light",            # 3i. light
        "_reflex_hunger",           # 4. hunger
        "_reflex_adjacent",         # 5. adjacent monster: auto-retaliate fights (sets ctx.adj)
        "_reflex_pickup",           # 5. pick up what we're standing on
        "_reflex_pack",             # 5. "no room" notice, auto-destroy junk
        "_reflex_engage",           # 5b. a monster worth killing a few steps off
        "_reflex_rest",             # 6. rest when hurt and alone
    )

    def reflexes(self):
        """The reflexes, in priority order (docs/pilot-combat.md §2): the first step that acts ends the call. True:
        the tick ends here; False: the rest of the tick runs (the Navigator's rules, the item policy, the goal)."""
        ctx = types.SimpleNamespace(w=self.w, o=self.orders, now=gnow())
        for name in self.REFLEX_STEPS:
            r = getattr(self, name)(ctx)
            if r is not NEXT:
                return r
        return False

    def _reflex_death(self, ctx):
        """0. Dead: HP 0 or a ghost. Stop everything and tell the Navigator; nothing else runs
        until 'goal resurrect'."""
        w = ctx.w
        if self.dead and not w.ghost and w.hp[0] > 0:
            self.dead = False                 # resurrected
        if w.ghost or w.hp[0] <= 0 and w.hp[1] > 0 and w.ind:
            if not self.dead:
                # Stay up to tell the Navigator (mission 7: the pilot exited at
                # death, and the Navigator only got "Connection refused")
                self.dead = True
                self.mover.stop()
                self.goal = None
                self.notify("dead", "the character died (now a ghost): 'goal resurrect' floats it up to town "
                                    "and resurrects it at the Temple (halves the experience for good)")
            if w.ghost and isinstance(self.goal, Resurrect):
                return False
            return True
        return NEXT

    def _reflex_busy(self, ctx):
        """0. An action still on its way (busy_until): hold. Inside a store during a Shop goal: skip
        the rest, so the goal carries on."""
        w, now = ctx.w, ctx.now
        if now < self.busy_until:
            return True
        if w.store and isinstance(self.goal, Shop):
            return False          # any command would leave the store
        return NEXT

    def _reflex_survey(self, ctx):
        """(Not a rule: what the steps below share.) ctx.mons_near: the monsters within 7 squares."""
        w = ctx.w
        ctx.mons_near = [m for m in w.monsters if w.dist(m[:2]) <= 7]
        return NEXT

    def _reflex_emergency(self, ctx):
        """2. Emergency
        Never fall through to the goal here, even when escape() has nothing
        usable this instant: in mission 7 the explore goal kept re-planning
        (the mover sends 'clear' and queues walks), which wiped every queued
        Phase Door, potion and Word of Recall, and the walks took the turns.
        Dive03 died at 750 ft without one of them being read.
        (and HP within 2.5 worst-case rounds of one adjacent monster: Brodda
        took 151 -> 27 in five rounds of 48 before flee_hp fired at 58 --
        the Advisor's missions 15-16 replay, change 3)
        (the Advisor's emergency-threshold memo, rulebook r4: the worst melee of the adjacent monsters in
        the next 3 player turns, against our AC and at their attack rate -- not 2.5 raw worst rounds,
        which broke off a vetted Ulfast hunt at 145 HP and under-counted fast monsters)"""
        w, o, now, mons_near = ctx.w, ctx.o, ctx.now, ctx.mons_near
        worst = self.worst_3turns([r for *_, r in w.adjacent_monsters()])
        hard = worst > 0 and w.hp[0] <= worst and w.hp_frac < 0.9
        if (w.hp_frac < o["flee_hp"] or hard) and (mons_near or now - w.last_hit_t < 5):
            why = "low HP" if w.hp_frac < o["flee_hp"] else f"HP {w.hp[0]} within 3 turns of the worst ({worst:.0f})"
            if not self.escape(why) and self.mover.active and not self.escaping_to_stairs:
                self.mover.stop()
            return True
        return NEXT

    def _reflex_group(self, ctx):
        """2'. Group danger (the Borg's rule, Advisor memo 2026-09-28 §3.1)"""
        now = ctx.now
        if self.group_tick(now):
            return True
        return NEXT

    def _reflex_hard_fight(self, ctx):
        """2a. The start of a hard fight (hard_fight): the estimator's view first (never acts), then a Potion of
        Speed (speed_start_tick) and Berserk Strength (berserk_tick)."""
        now = ctx.now
        self.hard_fight_shadow(now)          # (never acts: the estimator's view of the fight's start)
        if self.speed_start_tick(now):
            return True
        if self.berserk_tick(now):
            return True
        return NEXT

    def _reflex_status(self, ctx):
        """2a. Status cures, in combat only (out of combat, rest it off: the
        user). Stun can become a knock-out; blind or confused can't read."""
        now, mons_near = ctx.now, ctx.mons_near
        if self.status_tick(now, mons_near):
            return True
        return NEXT

    def _reflex_arrival(self, ctx):
        """3. Arrival into danger (connected stairs: the way back is underfoot)
        A stairs command gets no answer at all if it comes too soon after the
        level change (seen: '<' 0.7 s after arriving was ignored), so retry
        after 1.2 s while still on the stairs"""
        w, o, now, mons_near = ctx.w, ctx.o, ctx.now, ctx.mons_near
        stairs_pending = w.last_stairs_cmd and not waited(w.last_stairs_cmd[1], 1.2)
        if now - w.level_t < 6 and w.standing_on in ("<", ">") and not stairs_pending:
            danger = self.dangers()
            # A pack only counts if its members are within 5 levels of ours (a
            # pack of jackals is XP for a level-11 warrior, not a threat)
            lev = w.clvl
            threats = [m for m in mons_near if m[2].level >= lev - 5]
            if len(threats) >= o["arrival_pack"] or (danger and "danger" in o["stop_on"]):
                why = f"arrived next to {len(threats)} monsters ({threats[0][2].name if threats else ''})" + \
                    (f" incl. {self.danger_text(danger[0])}" if danger else "")
                self.take_stairs(w.standing_on)
                self.notify("danger_avoided", why)
                return True
        return NEXT

    def _reflex_danger_in_view(self, ctx):
        """3a. Something far above our level in view: leave before it reaches us
        (not only on arrival -- Dive03 met Stone trolls while exploring)"""
        w, o, now = ctx.w, ctx.o, ctx.now
        near_danger = [r for y, x, r in w.monsters if w.dist((y, x)) <= 12 and r in self.dangers()]
        # (and one the server's monster list names but the map decode misses:
        # present, position unknown -- the game-state survey, rule 4)
        near_danger += [r for r in w.listed_only() if self.danger_why(r)]
        # A slow caster with weak melee and the stairs far away: fleeing just
        # gives it free casts on the way (mission 15: Wormtongue, ~6 melee per
        # turn, the stairs 70-80 away, twice; the user: stand and fight; the
        # Advisor's replay: even a '>' 12 away gave ~18 s of free casts)
        stairs_d = min((w.dist(q) for q in w.find("<>")), default=999)
        # (weak by the worst case too: mission 19's Ranger, ~25 a turn and 40 at
        # worst, passed the average test and the Navigator hunted it: 220 -> 67)
        if near_danger and stairs_d > 8 and all(
                (r.speed_x or 1) <= 1 and r.per_turn < w.hp[0] / 8 and (r.worst_melee[0] or 0) < w.hp[0] / 8
                and r.spells for r in near_danger):
            if now - self.flee_t > 30:
                self.flee_t = now
                r0 = near_danger[0]
                self.notify("danger_seen", f"{self.danger_text(r0)} in view, stairs {stairs_d} away: NOT fleeing "
                                           f"(no faster than you, melee ~{r0.per_turn:.0f} a turn, "
                                           f"{r0.worst_melee[0]:.0f} at worst; its danger is spells, and a long walk "
                                           "gives it free casts). Fight it (goal hunt) or recall")
            near_danger = []
        if near_danger and now - self.flee_t <= 10 and self.flee_fail_t >= self.flee_t and \
                not isinstance(self.goal, Recall) and not self.recall_started(now):
            # the flee failed (no stairs): flee_t mustn't block the Word of
            # Recall / Phase Door fallback for 10 s (the Advisor's replay)
            self.flee_failed()
            if self.recall_started(now):
                return True
        # a summoner just seen, not adjacent and no faster than us: walk away out of its sight (the
        # user, 2026-10-23); the flee below only when walking away isn't safe or has failed here
        # (a summoner the server's list names before the map shows it -- A8w fled 1 s before the
        # decode: wait up to 1.5 s for its position, then decide)
        if near_danger and w.hp_frac >= 0.5 and all(self.danger_why(r) == "summons" for r in near_danger) and \
                any(r.name not in {q.name for *_, q in w.monsters} for r in near_danger) and \
                not isinstance(self.goal, (Flee, Recover, Recall, WalkAway)):
            self.summoner_hold_t = self.summoner_hold_t if now - self.summoner_hold_t < 5 \
                else now
            if now - self.summoner_hold_t < 1.5:
                # (the decision waits, the later reflexes run -- the user, 2.45.1 -- but not engage: A8w's first
                # 2.45.1 run engaged the Ranger in the wait and never walked away)
                ctx.summoner_hold = True
                return NEXT
        if near_danger and not isinstance(self.goal, (Flee, Recover, Recall, WalkAway)) and now - self.flee_t > 10 \
                and "danger" in o["stop_on"] and not self.hunt_ordered(now, near_danger[0].name) \
                and self.walk_away_ok(near_danger):
            self.flee_t = now
            names = sorted({r.name for r in near_danger})
            if self.goal is not None and not isinstance(self.goal, WalkAway):
                self.resume_after = self.goal
            self.set_goal(WalkAway(names))
            self.notify("tactic", f"{', '.join(names)} (summons) in view, not adjacent: walking away out of its "
                                  "sight instead of fleeing the level", news=True)
            return True
        if near_danger and not isinstance(self.goal, (Flee, Recover, WalkAway)) and now - self.flee_t > 10 \
                and "danger" in o["stop_on"] and not self.hunt_ordered(now, near_danger[0].name):
            self.flee_t = now
            prev = self.goal.describe() if self.goal else None
            self.set_goal(Flee(near_danger[0].name))
            self.notify("danger_seen", f"{self.danger_text(near_danger[0])} in view"
                                       f"{' while ' + prev if prev else ''}: heading for the stairs")
            return True
        return NEXT

    def _reflex_unseen(self, ctx):
        """3b. Something we can't see is attacking (an invisible monster, or one
        out of sight): we can't fight it, so leave (Advisor memo, Addendum 2
        item 3). Also HP falling with nothing in view and nothing else to
        explain it."""
        now = ctx.now
        if self.unseen_tick(now):
            return True
        return NEXT

    def _reflex_choke(self, ctx):
        """3c. A pack coming at us in the open: back into a corridor so they
        trickle into melee one at a time ("retreat behind a turn")
        (never while fleeing: mission 10 backed into a corridor twice instead
        of walking to the stairs away from Mughash, and died there)"""
        w, o, now = ctx.w, ctx.o, ctx.now
        if o.get("choke") == "on" and not w.adjacent_monsters() and w.standing_on not in ("<", ">") \
                and not isinstance(self.goal, (Flee, Recover, Recall)):
            if self.choke_tick(now):
                return True
        return NEXT

    def _reflex_summon_trap(self, ctx):
        """3d. A summon trap ("You are enveloped in a cloud of smoke!", cmd1.c 1049): 3-5 awake monsters from 5 levels
        deeper, uniques allowed, appear around us -- m26's Nar group (the Advisor's structures memo). Phase Door at
        once, before they act; the danger rules take it from there"""
        w, now = ctx.w, ctx.now
        smoke = [ts for ts, t in w.messages if t.startswith("You are enveloped in a cloud of smoke") and now - ts < 2]
        if smoke and w.in_dungeon and max(smoke) > self.smoke_t and not w.flag("blind") \
                and not w.flag("confused"):
            self.smoke_t = max(smoke)
            pd = self.phase_item()
            if pd:
                self.phase_t = now
                self.phase_hist.append(now)
                self.cmd(f"custom r item={pd['item']}", "summon trap: phase door before they act", hold=0.6)
                self.notify("emergency", "a summon trap (monsters from 5 levels deeper appear around us): phased away "
                                         "at once", action=True)
                return True
        return NEXT

    def _reflex_slowed(self, ctx):
        """3e. Slowed to half speed or worse with something on us: a Potion of Speed (m26: Gorged and slowed to
        -20 among six monsters; the Architect quaffed one by hand)"""
        w, now = ctx.w, ctx.now
        if self.our_slowness() >= 2 and (w.adjacent_monsters() or now - w.last_hit_t < 2) and \
                waited(self.speed_t, 40) and not self.buff_on("fast"):    # (a potion lasts ~20-45 turns)
            pot = self.find_item("Speed", TV_POTION)
            if pot:
                self.speed_t = now
                self.cmd(f"custom q item={pot['item']}", f"slowed ({(w.ind.get('speed') or [0])[0]}) in a fight: "
                                                         f"quaff {pot['name']}", hold=0.6)
                self.notify("tactic", f"slowed to {(w.ind.get('speed') or [0])[0]} with monsters on us: quaffed "
                                      f"{one_of(pot['name'])}")
                return True
        return NEXT

    def _reflex_afraid(self, ctx):
        """3f. Afraid (a warrior can't melee). The user: if not in danger, don't
        spend consumables -- kite over cleared ground until it wears off; only
        in danger cure it (Boldness/Heroism/Berserk) or phase away."""
        w, o, now, mons_near = ctx.w, ctx.o, ctx.now, ctx.mons_near
        if w.flag("afraid") and mons_near:
            # (or hit by several while we can't hit back: m26 kited, afraid, among a yeek band and a Dark hound
            # until the Navigator quaffed Heroism by hand)
            danger = w.hp_frac < o["think_hp"] or bool(self.dangers()) or len(w.adjacent_monsters()) >= 2 or \
                w.damage_rate(3.0) > 0.02 * max(1, w.hp[1])
            # (just arrived: no walked ground to kite over -- the stairs underfoot
            # are the cheapest way out)
            if not w.walked - {w.pos} and w.standing_on in ("<", ">") and len(mons_near) >= 2:
                self.take_stairs(w.standing_on)
                self.notify("tactic", "afraid on arrival among monsters: took the stairs back")
                return True
            if not danger and self.retreat_step(mons_near):
                if now - self.fear_t > 20:
                    self.fear_t = now
                    self.notify("tactic", "afraid: kiting over cleared ground until it wears off")
                return True
            if now - self.fear_t > 3:
                self.fear_t = now
                pot = self.fear_cure()
                if pot:
                    self.cmd(f"custom q item={pot['item']}", f"afraid and in danger: quaff {pot['name']}", hold=0.6)
                    self.notify("tactic", f"afraid and in danger: quaffed {one_of(pot['name'])}")
                    return True
                tp = self.teleport_item() if self.has_rule("afraid", "teleport") else None
                if tp and w.adjacent_monsters() and (tp[0] == "u" or not (w.flag("blind") or w.flag("confused"))):
                    self.cmd(f"custom {tp[0]} item={tp[1]['item']}", "afraid, no cure: teleport (the Navigator's rule)",
                             hold=0.6)
                    self.notify("rule", f"afraid with no fear cure: teleported ({one_of(tp[1]['name'])}) -- your "
                                        "`react afraid teleport`")
                    return True
                pd = self.phase_item()
                if pd and w.adjacent_monsters() and not w.flag("blind") and not w.flag("confused"):
                    self.cmd(f"custom r item={pd['item']}", "afraid: phase door away", hold=0.6)
                    self.notify("afraid", "afraid (can't melee) and cornered: phased away")
                    return True
        return NEXT

    def _reflex_still(self, ctx):
        """3g. Monsters that never move (molds, jellies, mushroom patches, floating
        eyes) only matter next to us, and there auto-retaliate fights them: a
        poison-mold cluster killed a forum player, a death mold disenchants, a
        floating eye paralyses. Step away quietly (no event), unless the
        Navigator is hunting that very monster."""
        w, now = ctx.w, ctx.now
        hunting = self.goal.target if isinstance(self.goal, Hunt) else None
        still = [m for m in w.adjacent_monsters() if "NEVER_MOVE" in m[2].flags
                 and not (hunting and hunting in m[2].name.lower())]
        if still and self.stairs_beside_still(still):
            still = []
        if still and self.still_fight_tick(now, still):
            return True
        if still and (self.retreat_step(still, reach=6) or self.sidestep(still)):
            return True
        return NEXT

    def _reflex_fearers(self, ctx):
        """3h. Monsters that frighten you again and again: not worth it. Walk
        away over cleared ground (phase if it's dangerous and next to us), and
        tell the Navigator once per level."""
        w, now, mons_near = ctx.w, ctx.now, ctx.mons_near
        fearers = [m for m in mons_near if m[2].repeat_fearer and "NEVER_MOVE" not in m[2].flags]
        if fearers and not isinstance(self.goal, (Flee, Recall)):
            f = fearers[0][2]
            if (w.level_t, f.name) not in self.fearers_seen:
                self.fearers_seen.add((w.level_t, f.name))
                self.notify("fearer", f"{f.name} (lvl {f.level}) keeps frightening: moving away from it; "
                                      "consider leaving the level")
            dangerous = f.level >= w.clvl - 2
            if dangerous and w.adjacent_monsters() and now - self.phase_t > 2.5:
                pd = self.phase_item()
                if pd and not w.flag("blind") and not w.flag("confused"):
                    self.phase_t = now
                    self.phase_hist.append(now)
                    self.cmd(f"custom r item={pd['item']}", f"phase away from {f.name}", hold=0.6)
                    return True
            if self.retreat_step(fearers):
                return True
        return NEXT

    def _reflex_light(self, ctx):
        """3i. Light"""
        w, now = ctx.w, ctx.now
        if self.town_light(now):
            return True
        # (no light at all in the dungeon: wield one even with a monster adjacent -- the set-piece
        # harness's A7 fought a Hill giant in the dark after an unexpected recall)
        unlit = w.depth != 0 and not any(i["tval"] == TV_LITE for i in w.items(equip=True))
        if (not w.adjacent_monsters() or unlit) and self.keep_light(now):
            return True
        return NEXT

    def _reflex_hunger(self, ctx):
        """4. Weak from hunger: eat (a Scroll of Satisfy Hunger without food), or recall with neither. Hungry is
        policy_tick's (2.45.2). (Hungry used to wait for no monster in view for 5 s: mission 9 ate a ration with
        Bullroarer a step out of view.)"""
        w, now = ctx.w, ctx.now
        # (2.45.2, the user: Hungry isn't an emergency -- a battle turn spent eating is wasted -- so it is
        # policy_tick's, at a safe moment; Weak (1) and fainting (0) stay here and no longer wait for 5 s without a
        # monster in view: Weak eats unless a monster is adjacent, fainting eats regardless)
        if w.hunger <= 1 and (w.hunger <= 0 or not w.adjacent_monsters()):
            food = w.items(tval=TV_FOOD)
            # one meal, then wait for the hunger indicator to catch up (mission 13
            # ate 2 rations in a row: 3 -> 1, "Full", no news)
            if food and now - self.eat_t > 10:
                self.eat_t = now
                self.cmd(f"eat {food[0]['item']}", f"hungry ({w.hunger})", hold=1.0)
                self.notify("tactic", f"hungry: ate {one_of(food[0]['name'])}")
                return True
            # (waiting for a meal to show, or for Weak before a scroll: the steps below still run -- this used to
            # return here, skipping pickup, auto-destroy, engage and rest, refactor-candidates A20)
            # no food: a Scroll of Satisfy Hunger (the town kit counts them as food; the reflex
            # didn't read them, and Dive04 went Weak with four in the pack: the set-piece harness)
            # (only when Weak: it fills to just under Gorged (use-obj.c, PY_FOOD_MAX - 1), so the next potion
            # makes you Gorged, -10 speed -- m26 read it Hungry at 03:20 and fought the yeek band Gorged)
            sat = None if food else self.find_item("Satisfy Hunger", TV_SCROLL)
            if sat and w.hunger <= 1 and now - self.eat_t > 10 and not w.flag("blind") and not w.flag("confused"):
                if not any(i["tval"] == TV_LITE for i in w.items(equip=True)):
                    # (no light to put on: the steps below still run -- `return self.wear_light(...)` returned its
                    # False and skipped pickup, auto-destroy and rest, A20's kind of early stop, refactor-candidates E3)
                    if self.wear_light("a light to read Satisfy Hunger by"):
                        return True
                    return NEXT
                self.eat_t = now
                self.cmd(f"custom r item={sat['item']}", f"hungry ({w.hunger}), no food: read Satisfy Hunger", hold=1.0)
                self.notify("tactic", "hungry and no food: read a Scroll of Satisfy Hunger")
                return True
            if not food and not sat and w.hunger <= 1 and not isinstance(self.goal, Recall) and w.depth:
                self.notify("supplies", "weak from hunger and no food: recalling",
                            fields={"supply": "food", "level": "recalling"})
                self.set_goal(Recall())
        return NEXT

    def _reflex_adjacent(self, ctx):
        """5. Adjacent monster: let the server's auto-retaliate fight
        (ctx.adj: the adjacent monsters, for the pickup's test.)"""
        w, o, now = ctx.w, ctx.o, ctx.now
        adj = ctx.adj = w.adjacent_monsters()
        if adj:
            if self.mover.active and not isinstance(self.goal, (Goto, Flee)):
                self.mover.stop()
            if w.resting:
                self.stop_resting()
            if w.hp_frac < o["think_hp"] and now - self.think_warned > 10:
                self.think_warned = now
                self.notify("fight_going_badly",
                            f"HP {w.hp[0]}/{w.hp[1]} fighting {', '.join(sorted({r.name for *_, r in adj}))}")
            # townfarm hits an adjacent thief itself (auto-retaliate picks its own
            # target: mission 18 killed 7 urchins and a dog while one stole 67)
            if isinstance(self.goal, TownFarm) and any(any("EAT_" in b for b in r.blows) for *_, r in adj):
                return False
            # In the dungeon too: with others adjacent, hit the thief first
            # (mission 21: a Brigand took an {excellent} armour from the pack)
            thieves = [m for m in adj if any(b.split(":")[1:2] in (["EAT_ITEM"], ["EAT_GOLD"]) for b in m[2].blows)]
            if thieves and len(adj) > 1 and w.depth and waited(self.thief_hit_t, 0.35) and \
                    not isinstance(self.goal, (Flee, Recall)):
                t = min(thieves, key=lambda m: not any("EAT_ITEM" in b for b in m[2].blows))
                self.thief_hit_t = now
                self.c.send("clear")
                self.cmd(f"walk {direction(w.pos, t[:2])}", f"hit the {t[2].name} first (a thief)", hold=0.2)
                return True
            return not isinstance(self.goal, (Goto, Flee))
        return NEXT

    def _reflex_pickup(self, ctx):
        """Pick up what we're standing on ("You see a ..." right after a step)"""
        w, o, now, adj = ctx.w, ctx.o, ctx.now, ctx.adj
        if o["pickup"] == "all" and not adj and not w.store:
            seen = [(ts, t) for ts, t in w.messages if now - ts < 3 and t.startswith("You see ")
                    and "no items" not in t]
            if seen and self.is_junk(seen[-1][1][8:].rstrip(".")):
                # known junk: leave it (it filled the pack on the way down) -- or, at a quiet moment, destroy it
                # where it lies (the user, 10-25: less clutter on the map and in the report's Items line). Once per
                # sighting: the message stays "recent" 3 s, and m44 stepped on while engaging an Ogre and sent the
                # destroy again on 3 empty squares ("There's nothing on the floor")
                done = self.junk_msgs_done
                if (w.level_t, w.pos) not in self.skipped_items and seen[-1][0] not in done:
                    done.add(seen[-1][0])
                    self.destroy_floor_junk(seen[-1][1][8:].rstrip("."), now)
                seen = []
                self.skipped_items.add((w.level_t, w.pos))
            if seen and (w.level_t, w.pos) in self.skipped_items:
                seen = []         # junk we left, or what the Navigator dropped here
            if seen and not w.in_dungeon and self.is_stash_item(seen[-1][1]) and \
                    not (self.fetching and self.fetching in seen[-1][1]):
                seen = []         # (the tavern stash stays there: the user, 10-26)
            # By value (restructure step 2.1; the Advisor's set-pieces C3, C4): a unique's
            # drop always; with the pack full, swap the cheapest non-kit item for a
            # better find; otherwise leave it and say so. (The bulky-gear rule this
            # replaces lost Brodda's Scimitar in mission 23.)
            # (m55 17:00:14: a Scroll of Light picked up mid-flee from a Black orc band. Fleeing with monsters in view,
            # only a find worth over 500 is worth the turn)
            if seen and isinstance(self.goal, (Flee, BandLeave, WalkAway)) and w.monsters and \
                    self.iv(seen[-1][1][8:].rstrip(".")).value < 500:
                seen = []
            if seen and not self.pickup_room(seen[-1][1][8:].rstrip(".")):
                seen = []
            if seen and seen[-1][0] > self.picked_t and w.pos == self.seen_pos(seen[-1][0]):
                self.picked_t = now
                if self.mover.active:
                    self.mover.requeue()   # steps queued ahead ran first: the pickup landed a square later
                # (it waits for energy after the step: ~0.6 s at normal speed)
                self.cmd("custom ,", f"pick up: {seen[-1][1][8:]}", hold=0.8)   # "Stay" picks up; "g" did nothing
                return True
        return NEXT

    def _reflex_pack(self, ctx):
        """5. The pack: a "no room" message is news (once per 30 s); with nothing in view, destroy the pack's junk."""
        w, now = ctx.w, ctx.now
        full = [t for ts, t in w.messages if now - ts < 3 and t.startswith("You have no room for")]
        if full and now - self.full_warned > 30:
            self.full_warned = now
            self.notify("pack_full", full[-1])
        if not w.monsters and not w.store and self.auto_destroy(now):
            return True
        return NEXT

    def _reflex_engage(self, ctx):
        """5b. A monster worth killing a few steps off: go and fight it, then carry on (the user, m43)"""
        now = ctx.now
        if getattr(ctx, "summoner_hold", False):     # (a summoner's walk-away decision is pending: 2.45.1)
            return NEXT
        if self.engage_tick(now):
            return True
        return NEXT

    def _reflex_rest(self, ctx):
        """6. Rest when hurt and alone. First, an escape walk to stairs that outlived its emergency: keep walking."""
        w, o = ctx.w, ctx.o
        # (escape() isn't called once nothing is within 7 and no hit for 5 s, and nothing else ticked its walk: the
        # mover stayed active, so this step didn't rest either, and the character stood still -- or a goal ticked the
        # walk and its stairs weren't taken. Here, after the steps that handle a monster: on the stairs, escape step 3
        # takes them; else the walk goes on. Blocked, stopped, replaced by another walk or a new level, it ends)
        if self.escaping_to_stairs:
            if self._escape_stairs_underfoot(types.SimpleNamespace(w=w, now=ctx.now, why="the escape walk")) is NEXT:
                self.mover.tick()
            return True
        if w.hp_frac < o["rest_below"] and not w.monsters and not isinstance(self.goal, (Recall,)):
            if not self.mover.active or isinstance(self.goal, Dive):
                self.mover.stop()
                self.start_resting()
                return True
        if w.resting and (w.hp_frac >= o["rest_to"] or w.monsters) and not isinstance(self.goal, RestGoal):
            self.stop_resting()
            return True
        if w.resting and not w.monsters:
            # keep resting to rest_to (the Advisor's mission 13 replay: the rest
            # ended once HP passed rest_below and the explorer walked off at 76%)
            return True
        return NEXT

    ENGAGE_STEPS = 7          # how far a detour to fight may go (path steps)
    ENGAGE_GIVE_UP_S = 20

    def engage_tick(self, now):
        """The user (m43): "The char often is near enemies but doesn't engage them ... it could kill the monster and
        then run after" -- "and this mustn't override legit reasons not to engage (kiting, fleeing...)". A mobile
        monster a few steps off that the hunt check allows: walk to it and let auto-retaliate fight (section 5),
        then the goal carries on. Only while exploring or diving, HP at least think_hp, not blind/confused/afraid/
        slowed, no live band, no dangerous monster or summoner in view, not a breeder, not on the avoid list, not
        while the plan is leaving the level for a reason. The escapes, the group/choke rules and the walk-away run
        earlier in the reflexes, so they still win. Gives up after ENGAGE_GIVE_UP_S."""
        w = self.w
        st = self.engage
        g = self.goal
        leaving = self.plan is not None and str(getattr(self.plan, "level_done", "") or "").startswith("left")
        ok = (w.in_dungeon and w.depth and w.pos and (g is None or isinstance(g, (Explore, Dive))) and not leaving
              and w.hp_frac >= self.orders.get("think_hp", 0.65) and not self.band_live()
              and not any(w.flag(k) for k in ("blind", "confused", "afraid")) and self.our_slowness() <= 1
              and not w.recall_pending)
        mons = [m for m in w.monsters if "NEVER_MOVE" not in m[2].flags]
        if ok and any(self.danger_why(m[2]) for m in mons):
            ok = False                               # (a danger in view: the flee/walk-away rules decide)
        if not ok:
            if st["target"]:
                st["target"] = None
                self.mover.stop()
            return False
        tgt = st["target"]
        if tgt:
            cur = next((m for m in mons if m[2].name == tgt), None)
            if cur is None or now - st["t0"] > self.ENGAGE_GIVE_UP_S:
                st["target"] = None                  # (killed, gone, or not reached: carry on)
                if cur is not None:
                    st["dropped"].add((w.level_t, tgt))
                self.mover.stop()
                return False
        else:
            cands = []
            for y, x, r in mons:
                if w.dist((y, x)) < 2 or w.dist((y, x)) > self.ENGAGE_STEPS or "MULTIPLY" in r.flags or \
                        (w.level_t, r.name) in st["dropped"] or any(n in r.name.lower() for n in self.avoid_names):
                    continue
                if r.level < w.clvl - 20:
                    continue                         # (no XP worth the detour)
                cache = self.engage_ok
                key = (w.level_t, r.name)
                if key not in cache:
                    try:
                        cache[key] = self.hunt_refusal(r.name)[0] is None
                        self.engage_disen[key] = self.hunt_fields(disen_only=True)   # (a disenchanter's cost)
                    except Exception:
                        cache[key] = False
                if cache[key]:
                    cands.append((w.dist((y, x)), y, x, r))
            if not cands:
                return False
            d, y, x, r = min(cands, key=lambda c: c[0])
            st.update(target=r.name, t0=now, replan_t=0.0)
            self.log("act", cmd="engage", why=f"engage {r.name} (L{r.level}, {d} away) on the way", by="pilot",
                     **self.engage_disen.get((w.level_t, r.name), {}))
            tgt = r.name
        cur = next(m for m in mons if m[2].name == tgt)
        if now - st["replan_t"] > 1.5 or not self.mover.active:
            st["replan_t"] = now
            near = [(cur[0] + dy, cur[1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
            if not self.mover.go(near) or len(self.mover.path) > self.ENGAGE_STEPS + 2:
                self.mover.stop()
                st["dropped"].add((w.level_t, tgt))
                st["target"] = None
                return False
        self.mover.tick()
        return True

    def count_escape(self):
        """One escape action towards emergency_loop's three in 90 s (A4: actions only, never mere notices)."""
        self.emerg_times.append(gnow())

    def emergency_loop(self, now):
        """Three emergency actions within 90 s: phasing and drinking isn't
        working (HP stuck around 50%, monsters always in view): leave by stairs
        if some are known, else tell the Navigator."""
        self.emerg_times = [t for t in self.emerg_times if now - t < 90]
        if len(self.emerg_times) < 3 or now - self.loop_warned < 60:
            return False
        self.loop_warned = now
        stairs = [p for p in self.w.find("<>") if self.w.dist(p) <= 30]
        if stairs and not isinstance(self.goal, Flee):
            prev = self.goal
            self.set_goal(Flee("emergency loop"))
            self.resume_after = prev
            self.notify("tactic", "third emergency in 90 s: leaving by the stairs")
            return True
        if stairs:
            # (already fleeing: the old text said "no stairs known nearby" here, refactor-candidates A21)
            self.notify("emergency_loop", "third emergency in 90 s, already fleeing to the stairs: "
                                          "consider Word of Recall if it doesn't get there")
            return False
        self.notify("emergency_loop", "third emergency in 90 s and no stairs known nearby: "
                                      "consider Word of Recall or leaving this area")
        return False

    def hunt_ordered(self, now, what):
        """The Navigator ordered this hunt in the last 2 minutes: the automatic
        'dangerous monster' and 'unseen attacker' flees don't replace it (mission
        22: hunts ordered on a danger alert were overridden by the flee).
        Emergencies and the 1x group-danger exit still apply."""
        g = self.goal
        if not (isinstance(g, Hunt) and g.by_navigator and now - self.goal_t < 120):
            return False
        if g.kept_warned != what:
            g.kept_warned = what
            self.notify("tactic", f"hunting {g.target} as ordered: not fleeing from {what} (emergency escapes "
                                  "still apply)", news=True)
        return True

    def walk_away_ok(self, rs):
        """True if every danger in view is only a summoner, seen on the map, 3+ squares off, no
        faster than us, nothing has been summoned yet, HP is at half or more, and walking away
        hasn't already failed on this level."""
        w = self.w
        if w.hp_frac < 0.5 or self.walkaway_failed & {w.level_t}:
            return False
        if any(t for ts, t in w.messages if gnow() - ts < 10 and "summons" in t):
            return False
        mine = 110 + int(w.ind.get("speed", [0])[0] or 0)
        pos = {r.name: (y, x) for y, x, r in w.monsters}
        return all(self.danger_why(r) == "summons" and r.name in pos and w.dist(pos[r.name]) >= 3 and r.speed <= mine
                   for r in rs)

    def phase_futile(self, now):
        """3 Phase Doors in the last 20 s: the monsters keep reaching us."""
        while self.phase_hist and now - self.phase_hist[0] > 20:
            self.phase_hist.popleft()
        return len(self.phase_hist) >= 3

    @property
    def escaping_to_stairs(self):
        """The mover's current walk is escape()'s walk to stairs. Tied to that walk (Mover.walk_id) on this level:
        arriving, a stop, any later go() (Explore etc. reuse the mover) or a new level ends it. (It was a plain flag
        never reset: after the first escape walk every walk was ticked as one, and the emergency reflex stopped
        stopping the mover -- refactor-candidates A1.)"""
        tag = self._escape_walk
        return tag is not None and bool(self.mover.active) and \
            tag == (getattr(self.mover, "walk_id", None), self.w.level_t)

    @escaping_to_stairs.setter
    def escaping_to_stairs(self, on):
        self._escape_walk = (getattr(self.mover, "walk_id", None), self.w.level_t) if on else None

    # escape()'s steps, in order (refactor-candidates E3; docs/pilot-combat.md §3, mirrored by the Advisor's estimator:
    # tell the Advisor when the order changes). Each takes the per-call context `ctx` (w, now, why; the values the
    # steps share, set by the step that computes them) and returns NEXT to go on, or escape()'s value.
    ESCAPE_STEPS = (
        "_escape_stairs_pending",   # 1. a stairs command on its way: wait
        "_escape_loop",             # 2. emergency loop (3 escapes in 90 s): flee to stairs
        "_escape_stairs_underfoot",  # 3. stairs underfoot while threatened, or reached by step 12's walk: take them
        "_escape_survey",           # (not a rule: ctx.adj, can_read, pd, rate, in_combat for the steps below)
        "_escape_out_of_combat",    # 4. out of combat: rest or step out of sight
        "_escape_one_turn",         # 5. one turn from death: Teleportation, else Phase Door (sets ctx.one_turn)
        "_escape_speed",            # 6. speed first
        "_escape_recall",           # 7. HP < 30%: Word of Recall
        "_escape_phase_futile",     # 8. phasing futile: Word of Recall (sets ctx.collapsing; may clear ctx.pd)
        "_escape_kill_caster",      # 9. an adjacent caster that dies in 2 rounds: attack it
        "_escape_teleport",         # 10. a crowd in the open, or afraid and pinned: teleport (sets ctx.crowd, tele)
        "_escape_phase",            # 11. adjacent: Phase Door (rate-limited)
        "_escape_to_stairs",        # 12. out of melee: walk to stairs <= 20 away
        "_escape_potions",          # 13. potions by numbers
        "_escape_nothing_left",     # 14. nothing usable: say so, fight on
    )

    def escape(self, why):
        """Emergency: at most one action per call, the first that applies (docs/pilot-combat.md §3; the Advisor's
        estimator mirrors this order, so tell the Advisor when it changes): a stairs command on its way -> wait;
        emergency loop (3 escapes in 90 s) -> Flee to stairs; stairs underfoot while threatened, or reached by the
        walk to stairs below -> take them, then Recover; out of combat -> rest or step out of sight (never potions);
        one turn from death -> Teleportation, else Phase Door; a Potion of Speed if not fast; HP < 30% -> Word of
        Recall; phasing futile (3 in 20 s) -> Word of Recall; an adjacent summoner/status caster we kill in 2 rounds
        -> attack it; a crowd in the open (or afraid with 2+ adjacent) -> Teleportation; adjacent -> Phase Door
        (rate-limited: phasing again and again doesn't shake a pack; it burned 10 scrolls in 10 s); out of melee ->
        walk to stairs <= 20 away; potions by numbers (or Phase/Recall when they're too small); else say there's
        nothing left and fight on."""
        ctx = types.SimpleNamespace(w=self.w, now=gnow(), why=why)
        for name in self.ESCAPE_STEPS:
            r = getattr(self, name)(ctx)
            if r is not NEXT:
                return r
        return False

    def _escape_stairs_pending(self, ctx):
        """1. A stairs command is already on its way (< 1.2 s): wait."""
        w = ctx.w
        if w.last_stairs_cmd and not waited(w.last_stairs_cmd[1], 1.2):
            return True           # already on our way (retried after 1.2 s)
        return NEXT

    def _escape_loop(self, ctx):
        """2. The emergency loop (3 escape actions in 90 s): Flee to stairs (emergency_loop)."""
        now = ctx.now
        if self.emergency_loop(now):
            return True
        return NEXT

    def _escape_stairs_underfoot(self, ctx):
        """3. Stairs underfoot while threatened, or reached by escape()'s walk to stairs (step 12): take them, then
        goal Recover. On stairs with nothing threatening and no escape walk: do nothing (stops stair-bouncing)."""
        w, now, why = ctx.w, ctx.now, ctx.why
        # (only with something here: arriving by stairs you stand on stairs again, and m26 bounced 650 <-> 600
        # ft four times in 12 s at 18% HP with a recall pending and nothing in view)
        threatened = bool(w.monsters) or now - w.last_hit_t < 2
        # (but an escape walk that reaches its stairs takes them: the danger that started the walk is the reason to
        # leave, out of view or not. The walk ends with a new level, so arriving by stairs still doesn't bounce; this
        # step returned first, and step 12's "take them on arrival" never ran -- refactor-candidates E3)
        if w.standing_on in ("<", ">") and not threatened and not self.escaping_to_stairs:
            return False
        if w.standing_on in ("<", ">"):
            which = w.standing_on
            self.take_stairs(which)
            self.notify("emergency", f"{why}: took the stairs underfoot ({which})", action=True)
            # then heal on the other side instead of carrying on with the goal
            if not isinstance(self.goal, Recover):
                self.goal = Recover(which, self.goal)
                self.log("goal", goal=self.goal.describe())
            return True
        return NEXT

    def _escape_survey(self, ctx):
        """(Not a rule: what the steps below share.) ctx.adj, ctx.can_read, ctx.pd (Phase Door), ctx.rate (HP/s
        lost) and ctx.in_combat."""
        w, now = ctx.w, ctx.now
        adj = ctx.adj = w.adjacent_monsters()
        ctx.can_read = not w.flag("blind") and not w.flag("confused")
        ctx.pd = self.phase_item()
        # Out of combat, potions and scrolls are a waste: rest instead (the
        # user). In combat = something next to us, hit in the last 3 s (ranged
        # attacks count), or HP falling with a monster in view (not poison or
        # a cut on its own).
        rate = ctx.rate = w.damage_rate(3.0)
        ctx.in_combat = adj or now - w.last_hit_t <= 3 or (rate > 0 and w.monsters)
        return NEXT

    def _escape_out_of_combat(self, ctx):
        """4. Not in combat: rest if nothing is in view, else step back out of sight. No potions or scrolls
        out of combat; an escape walk to stairs carries on instead (step 12)."""
        w, in_combat = ctx.w, ctx.in_combat
        if not in_combat and \
                not (self.mover.active and self.escaping_to_stairs):
            if not w.monsters:
                self.start_resting()
                return True
            # something in view but not fighting (asleep, slow): back off over
            # walked ground, out of its sight, and rest there
            return self.retreat_step([m for m in w.monsters if w.dist(m[:2]) <= 7] or w.monsters)
        return NEXT

    def _escape_one_turn(self, ctx):
        """5. One turn from death (the adjacent monsters' worst turn at our AC is about our HP): get out now --
        Teleportation, else Phase Door, rate limit or not. Otherwise Speed first, at the start of an emergency:
        +10 doubles our turns against everything here (the user, 10-25; m30's crowd took 303 -> 115 in ~70 s)
        (ctx.one_turn, for the Speed step.)"""
        w, now, why, adj, can_read, pd = ctx.w, ctx.now, ctx.why, ctx.adj, ctx.can_read, ctx.pd
        one_turn = ctx.one_turn = bool(adj) and self.worst_3turns([r for *_, r in adj]) / 3 >= 0.9 * w.hp[0]
        if one_turn and can_read:
            tele = self.find_item("Teleportation", TV_SCROLL)
            if tele or pd:
                use = tele or pd
                if not tele:
                    self.phase_t = now
                    self.phase_hist.append(now)
                self.cmd(f"custom r item={use['item']}", f"{why}: one turn from death: {use['name']}", hold=0.6)
                self.notify("emergency", f"{why}: one turn from death ({', '.join(sorted({r.name for *_, r in adj}))} "
                                         f"adjacent): read {one_of(use['name'])}", action=True)
                return True
        return NEXT

    def _escape_speed(self, ctx):
        """6. Speed first: a Potion of Speed, if not already fast and not one turn from death (once per 20 s)."""
        now, why, one_turn = ctx.now, ctx.why, ctx.one_turn
        sp = self.find_item("Speed", TV_POTION)
        if sp and not one_turn and not self.buff_on("fast") and waited(self.speed_t, 20):
            self.speed_t = now
            self.cmd(f"custom q item={sp['item']}", f"{why}: quaff {sp['name']} (an emergency: speed first)", hold=0.6)
            self.notify("emergency", f"{why}: quaffed {one_of(sp['name'])} first", action=True)
            return True
        return NEXT

    def _escape_recall(self, ctx):
        """7. Last resort, started early because it takes 15-34 turns (8-23 s): Word of Recall"""
        w, now, why, can_read = ctx.w, ctx.now, ctx.why, ctx.can_read
        if w.hp_frac < 0.3 and can_read and not self.recall_started(now):
            wor = self.find_item("Word of Recall", TV_SCROLL)
            if wor and w.in_dungeon:
                self.recall_t = now
                self.cmd(f"custom r item={wor['item']}", f"{why}: word of recall (last resort)", hold=0.5)
                self.notify("emergency", f"{why}: read Word of Recall as a last resort", action=True)
                return True
        return NEXT

    def _escape_phase_futile(self, ctx):
        """8. Phasing that isn't working: 3 in 20 s and they're still on us (mission
        22 read 10 in ~20 s, twice). Start the recall, keep one or two Phase
        Doors for when HP is really low
        (First ctx.collapsing, for the Phase Door step.)"""
        w, now, why, adj, can_read, pd = ctx.w, ctx.now, ctx.why, ctx.adj, ctx.can_read, ctx.pd
        # Rate-limited (repeated phasing doesn't shake a pack), except when HP
        # is collapsing with something next to us
        ctx.collapsing = w.hp_frac < 0.35
        if adj and pd and can_read and self.phase_futile(now) and w.hp_frac >= 0.2:
            if not self.recall_started(now) and w.in_dungeon:
                wor = self.find_item("Word of Recall", TV_SCROLL)
                if wor:
                    self.recall_t = now
                    self.cmd(f"custom r item={wor['item']}", f"{why}: phasing isn't shaking them: word of recall",
                             hold=0.5)
                    self.notify("emergency", f"{why}: 3 Phase Doors in 20 s and they're still adjacent: read Word "
                                             "of Recall; Phase Door now only below 20% HP", action=True)
                    return True
            ctx.pd = None
        return NEXT

    def _escape_kill_caster(self, ctx):
        """9. A summoner or status caster beside us that dies in two rounds: kill it first (the Advisor's estimator
        memo: m30's Druid paralysed, blinded three times and summoned three times, and was never attacked)"""
        why, adj = ctx.why, ctx.adj
        if self.kill_caster_step(adj, why):
            return True
        return NEXT

    def _escape_teleport(self, ctx):
        """10. Four or more about in the open: Teleportation, not Phase Door (no monster flow in this build: they walk
        straight back unless a wall intervenes; 4 of m30's 5 phases landed 6-7 squares from contact)
        (ctx.crowd and ctx.tele, for the potions step.)"""
        w, now, why, adj, can_read = ctx.w, ctx.now, ctx.why, ctx.adj, ctx.can_read
        crowd = ctx.crowd = [m for m in w.monsters if "NEVER_MOVE" not in m[2].flags and w.dist(m[:2]) <= 5]
        tele = ctx.tele = self.teleport_item()
        # (afraid with 2+ adjacent: we can't hit back, and a phase lands within reach again -- m41 phased 3 times
        # with a Half-orc, a Master yeek and a 2-headed hydra on it, 156 -> 123 HP, then read Word of Recall)
        pinned = w.flag("afraid") and len(adj) >= 2
        if adj and tele and ((len(crowd) >= 4 and not self.mover.in_corridor()) or pinned) and \
                (can_read or tele[0] == "u") and waited(self.phase_t, 2.0):
            self.phase_t = now
            what = "afraid with " + plural(len(adj), "monster") + " adjacent" if pinned else \
                f"{len(crowd)} about in the open"
            self.cmd(f"custom {tele[0]} item={tele[1]['item']}", f"{why}: teleport ({what})", hold=0.6)
            self.notify("emergency", f"{why}: {what}: {one_of(tele[1]['name'])}", action=True)
            return True
        return NEXT

    def _escape_phase(self, ctx):
        """11. Phase Door with a monster adjacent: every 2.5 s, or every 0.7 s when HP is collapsing (< 35%)."""
        now, why, adj, can_read, pd, collapsing = ctx.now, ctx.why, ctx.adj, ctx.can_read, ctx.pd, ctx.collapsing
        if adj and pd and can_read and (waited(self.phase_t, 2.5) or (collapsing and waited(self.phase_t, 0.7))):
            self.phase_t = now
            self.phase_hist.append(now)
            self.cmd(f"custom r item={pd['item']}", f"{why}: phase door", hold=0.6)
            self.notify("emergency", f"{why}: read Phase Door ({', '.join(sorted({r.name for *_, r in adj}))} adjacent)",
                        action=True)
            return True
        return NEXT

    def _escape_to_stairs(self, ctx):
        """12. Out of melee: walk to stairs <= 20 away (not within 2 s of another use); step 3 takes them on
        arrival."""
        w, why, adj = ctx.w, ctx.why, ctx.adj
        if not adj:
            # Out of melee: make for stairs if some are close, else heal
            stairs = [p for p in w.find("<>") if w.dist(p) <= 20]
            # (a new move sends 'clear', which would drop a read or quaff still
            # waiting in the server's queue for our next turn)
            used_recently = not waited(max(self.phase_t, self.cure_t, self.recall_t), 2.0)
            if stairs and not self.mover.active and not used_recently:
                if self.mover.go(stairs):
                    self.escaping_to_stairs = True
                    self.notify("emergency", f"{why}: heading for the stairs {min(w.dist(p) for p in stairs)} away",
                                action=True)
            if self.mover.active and self.escaping_to_stairs:
                # (on the stairs, step 3 has taken them already: standing_on doesn't change within a call, so the
                # old "arrived and on stairs: take them" here never ran)
                self.mover.tick()
                return True
        return NEXT

    def _escape_potions(self, ctx):
        """13. Potions by numbers (every 1.5 s), or Phase/Recall when they're too small; with 2+ adjacent an escape
        rather than a cure."""
        w, now, why, adj, can_read, pd = ctx.w, ctx.now, ctx.why, ctx.adj, ctx.can_read, ctx.pd
        rate, crowd, tele = ctx.rate, ctx.crowd, ctx.tele
        if waited(self.cure_t, 1.5):
            # Heal or escape, by numbers (Advisor memo P3: quaffing CLW while
            # taking 100+ a turn is the commonest fatal mistake). A potion must
            # out-heal what comes in before the next one can land (~1.5 s, plus
            # the turn auto-retaliate eats). Weakest adequate first (Cure Serious
            # went first and was gone when it mattered, mission 2); when HP is
            # collapsing, at least 10% of max HP.
            need = max(rate * 2.0, 0.1 * w.hp[1] if w.hp_frac < 0.3 else 0)
            pots = sorted(((heal_of(i["name"]), i) for i in w.items(tval=TV_POTION) if heal_of(i["name"])),
                          key=lambda p: p[0])
            good = [p for p in pots if p[0] > need]
            pick = good[0] if good else None
            dire = rate > 0 and w.hp[0] < rate * 8      # dead in under ~8 s at this rate
            if pots and not good and not dire:
                pick = pots[-1]          # slow damage: the biggest potion still helps
            elif pots and not good:
                # Every potion is too small for this damage: escape instead
                if now - self.noescape_t > 10:
                    self.noescape_t = now
                    self.notify("emergency", f"{why}: losing ~{rate:.0f} HP/s, more than the best potion heals "
                                             f"({pots[-1][0]}): escaping instead", action=False)
                if adj and pd and can_read and waited(self.phase_t, 0.7):
                    self.phase_t = now
                    self.phase_hist.append(now)
                    self.count_escape()     # (this phase sends no notice of its own)
                    self.cmd(f"custom r item={pd['item']}", f"{why}: phase door (potions too weak)", hold=0.6)
                    return True
                wor = self.find_item("Word of Recall", TV_SCROLL)
                if wor and can_read and w.in_dungeon and not self.recall_started(now):
                    self.recall_t = now
                    self.cmd(f"custom r item={wor['item']}", f"{why}: word of recall (potions too weak)", hold=0.5)
                    self.notify("emergency", f"{why}: read Word of Recall (potions too weak for the damage)",
                                action=True)
                    return True
                if not adj:
                    pick = pots[-1]      # shot at, nothing to hit back: any HP helps
            # Two or more beside us: an HP cure (a flat 15-29 HP, use-obj.c) is outpaced -- read an escape instead;
            # blind or confused, cure that first so the next turn can read (the Advisor's estimator memo)
            if pick and len(adj) >= 2:
                if not can_read:
                    st = "blind" if w.flag("blind") else "confused"
                    cure = next((i for c in STATUS_CURES[st] for i in w.items(tval=TV_POTION) if c in i["name"]
                                 and not (c == "Healing" and "*Healing*" in i["name"])), None)
                    if cure:
                        self.cure_t = now
                        self.cmd(f"custom q item={cure['item']}", f"{why}: {st} with {len(adj)} adjacent: quaff "
                                                                   f"{cure['name']} to read an escape next", hold=0.6)
                        self.notify("emergency", f"{why}: {st} with {len(adj)} adjacent: quaffed {one_of(cure['name'])} "
                                                 "so the next turn can read", action=True)
                        return True
                else:
                    esc = tele if tele and len(crowd) >= 4 else (("r", pd) if pd else tele)
                    if esc and waited(self.phase_t, 0.7):
                        self.phase_t = now
                        if "Phase" in esc[1]["name"]:
                            self.phase_hist.append(now)
                        self.cmd(f"custom {esc[0]} item={esc[1]['item']}", f"{why}: {len(adj)} adjacent: "
                                                                            f"{esc[1]['name']} rather than a cure", hold=0.6)
                        self.notify("emergency", f"{why}: {len(adj)} adjacent, a cure would be outpaced: read "
                                                 f"{one_of(esc[1]['name'])}", action=True)
                        return True
            if pick:
                pot = pick[1]
                self.cure_t = now
                self.cmd(f"custom q item={pot['item']}", f"{why}: quaff {pot['name']}", hold=0.6)
                self.notify("emergency", f"{why}: quaffed {one_of(pot['name'])}" + (f" (losing ~{rate:.0f} HP/s)" if rate else ""),
                            action=True)
                return True
        return NEXT

    def _escape_nothing_left(self, ctx):
        """14. Nothing usable: an emergency notice, every 10 s; fight on."""
        w, now, why, pd = ctx.w, ctx.now, ctx.why, ctx.pd
        if now - self.noescape_t > 10:
            self.noescape_t = now
            left = [n for n, ok in (("Phase Door", pd), ("cure potions", any(
                    any(c in i["name"] for c in CURE_POTIONS) for i in w.items(tval=TV_POTION)))) if ok]
            self.notify("emergency", f"{why}: " + (f"waiting to use {', '.join(left)} again, fighting on"
                                                   if left else "nothing left to escape with, fighting on"), action=False)
        return False

    def watch_perception(self):
        """Log when the server's monster list names something our map decode
        doesn't show (mission 4: a Yellow mold hit us while the pilot saw
        nothing). Once per level and name, with the map around us."""
        w = self.w
        if not w.monlist or not w.rows or not w.pos:
            return
        seen = {r.name for *_, r in w.monsters}
        now = gnow()
        for name, n, ch in w.monlist:
            if name in seen:
                self.gap_since.pop(name, None)
                continue
            # (the monster list and the map arrive separately: only a gap that
            # lasts counts)
            if now - self.gap_since.setdefault(name, now) < 1.5 or (w.level_t, name) in self.gaps_logged:
                continue
            self.gaps_logged.add((w.level_t, name))
            y, x = w.pos
            crop = [(r[max(0, x - 12):x + 13], a[max(0, x - 12):x + 13])
                    for r, a in zip(w.rows[max(0, y - 6):y + 7], w.attrs[max(0, y - 6):y + 7])]
            self.log("perception_gap", name=name, count=n, our_char=ch, pos=w.pos,
                     map_age=round(gnow() - w.map_t, 2), crop=crop,
                     monsters=[(my, mx, r.name) for my, mx, r in w.monsters])

    def watch_band(self):
        """A band gathering: 5+ mobile monsters within 10 squares that aren't
        trivial, or their worst-case melee together over half our HP. Warn once
        per level (again if it grows by half): leave while it's cheap (mission 22
        fetched loot in Orfax's room while an orc band assembled; HP 78/241, all
        10 Phase Door and 5 CCW later)."""
        w = self.w
        if not w.in_dungeon:
            return
        # (not trivial: 6+ worst-case melee a turn; by level it missed an orc band
        # of Hill, Cave and Snaga orcs, all well below clvl 21)
        near = [(y, x, r) for y, x, r in w.monsters if "NEVER_MOVE" not in r.flags and w.dist((y, x)) <= 10
                and (r.worst_melee[0] or 0) * (r.speed_x or 1) >= 6]
        worst = sum((r.worst_melee[0] or 0) * (r.speed_x or 1) for *_, r in near)
        if len(near) < 5 and worst < 0.4 * max(w.hp[1], 1):
            return
        # serious only when together they could take 30% of current HP in a turn, or one of them
        # is dangerous (the user, m24: 5-8 Novice rogues or Snaga at clvl 22 / 265 HP made the trip
        # leave four levels and a Word of Recall on the floor); weaker ones are fought, and looted
        # (since m34: by the expected cost of fighting them one by one, not the sum of every member's maximum hit:
        # m30's Novice warriors x6 + Swordsman and m34's Hill orcs counted as bands at 30% that way. 50% of HP
        # expected, or a dangerous member)
        cost = self.band_cost([r for *_, r in near])
        serious = cost > float(self.orders.get("band_frac", 0.5)) * max(w.hp[0], 1) or \
            any(self.danger_why(r) for *_, r in near)
        if not serious:
            if self.weak_band_said != w.level_t:
                self.weak_band_said = w.level_t
                self.notify("tactic", f"{len(near)} monsters together but weak (~{cost:.0f} HP expected to fight them "
                                      f"all, vs HP {w.hp[0]}): fighting on", news=True)
            return
        lt, size = self.band_warned
        if lt == w.level_t and len(near) < size * 1.5:
            return
        self.band_warned = (w.level_t, len(near))
        self.band_warned_t = gnow()
        names = ", ".join(f"{n} ×{c}" if c > 1 else n
                          for n, c in collections.Counter(r.name for *_, r in near).most_common(6))
        stairs = min((w.dist(q) for q in w.find("<>")), default=None)
        self.notify("band", f"a band within 10 squares: {names} ({len(near)} monsters, ~{cost:.0f} HP expected to fight "
                            f"them all, HP {w.hp[0]}): leave now while it's cheap -- "
                            + (f"stairs {stairs} away" if stairs is not None else "no stairs known: read Word of Recall")
                            + "; don't stop for loot")

    def teleport_item(self):
        """('r', a Scroll of Teleportation) or ('u', a Staff of Teleportation with charges), or None. Blind, confused
        or just refused a read: the staff first (a scroll can't be read blind, cmd6.c:275 -- m48: 13 Light hounds
        re-blinded Dive04 within a second of each cure, and two escape reads failed; the staff works blind)."""
        w = self.w
        sc = self.find_item("Teleportation", TV_SCROLL)
        st = next((i for i in w.items(tval=55) if "Teleportation" in i["name"] and
                   not re.search(r"\(0 charges\)", i["name"])), None)
        unreadable = w.flag("blind") or w.flag("confused") or gnow() - self.read_failed_t < 10
        if st and (unreadable or not sc):
            return ("u", st)
        if sc and not unreadable:
            return ("r", sc)
        return ("u", st) if st else None

    STATUS_SPELLS = ("BLIND", "CONF", "HOLD", "SLOW", "SCARE", "FORGET", "DRAIN_MANA", "TELE_TO", "TELE_LEVEL")

    def kill_caster_step(self, adj, why):
        """Attack an adjacent summoner or status caster (blind, confuse, hold, slow, scare...) that our blows kill in
        two rounds (rulebook hp vs the wielded weapon's damage). True if the attack was sent."""
        w = self.w
        if not adj or not waited(self.caster_t, 0.6):
            return False
        rows = self.fight_rows()
        wt = [x for x in self.weapon_table() if x[3]]
        dmg = wt[0][2] if wt else 0
        if not dmg:
            return False
        best = None
        for y, x, r in adj:
            if not (r.summoner or any(s in self.STATUS_SPELLS for s in r.spells)):
                continue
            hp = float((rows.get(getattr(r, "idx", None)) or {}).get("hp") or 0)
            if hp and hp <= 2 * dmg and (best is None or hp < best[0]):
                best = (hp, y, x, r)
        if not best:
            return False
        _, y, x, r = best
        self.caster_t = gnow()
        self.cmd(f"walk {direction(w.pos, (y, x))}", f"{why}: attack {r.name} first (a caster, dies in 2 rounds)",
                 hold=0.4)
        if not self.caster_said == (w.level_t, r.name):
            self.caster_said = (w.level_t, r.name)
            self.notify("emergency", f"{why}: attacking {r.name} first (summons or casts blind/confuse/hold; ~{best[0]:.0f} "
                                     f"HP, two rounds)", action=False)
        return True

    def band_cost(self, races):
        """Expected HP lost fighting these monsters one at a time, the quickest kills first: while each dies, those
        still alive hit for their expected melee at our AC (rulebook melee_exp_acNN a monster turn, x their speed),
        at most 8 at once in a room, 2 in a corridor. Our damage: the wielded weapon's per round."""
        rows = self.fight_rows()
        ac = (self.w.ind.get("armor") or [0])[0] or 0
        col = min((20, 40, 60), key=lambda a: abs(a - ac))
        wt = [x for x in self.weapon_table() if x[3]]
        dmg = max(1.0, wt[0][2] if wt else 10.0)
        cap = 2 if self.mover.in_corridor() else 8

        def stats(r):
            row = rows.get(getattr(r, "idx", None)) or {}
            hp = float(row.get("hp") or 0) or 10.0
            hit = float(row.get(f"melee_exp_ac{col}") or 0) * (r.speed_x or 1) if row else \
                0.5 * (r.worst_melee[0] or 0) * (r.speed_x or 1)
            return hp, hit
        alive = sorted((stats(r) for r in races), key=lambda s: s[0])
        total = 0.0
        while alive:
            t = max(1.0, alive[0][0] / dmg)
            total += t * sum(sorted((h for _, h in alive), reverse=True)[:cap])
            alive.pop(0)
        return total * self.our_slowness()

    def band_live(self):
        """A band warned on this level in the last 20 s, or 3+ of its kind of monsters still within 10."""
        w = self.w
        if self.band_warned[0] != w.level_t:
            return False
        if gnow() - self.band_warned_t < 20:
            return True
        return sum(1 for y, x, r in w.monsters if "NEVER_MOVE" not in r.flags and w.dist((y, x)) <= 10) >= 3

    def watch_traps(self):
        """Three traps sprung on one level: say so (mission 22: dart traps
        drained STR and CON on one level while explore walked on)."""
        w = self.w
        if not w.in_dungeon:
            return
        for ts, t in w.messages:
            if ts > self.trap_seen_t and re.match(r"(You found a trap|You fall into|A small dart|You are enveloped|"
                                                  r"You are impaled|A pit|You fall through)", t):
                n = self.traps_here[1] + 1 if self.traps_here[0] == w.level_t else 1
                self.traps_here = (w.level_t, n)
                if n == 3:
                    self.notify("tactic", "3 traps sprung on this level: it's trap-laden; leave it (stairs or a "
                                          "fresh level) rather than explore on", news=True)
                if t.startswith("You fall through"):
                    self.trapdoor = (ts, w.depth_ft)
        self.trap_seen_t = max([self.trap_seen_t] + [ts for ts, _ in w.messages])
        # (m50: a trap door dropped us to 850 ft, below max_depth 800; the climb back took ~4.5 minutes and only the
        # depth column showed it. Say so, and log it for the mission's record)
        td = self.trapdoor
        if td and w.level_t > td[0]:
            self.trapdoor = None
            md = int(self.orders.get("max_depth", 0))
            self.log("trapdoor", from_ft=td[1], to_ft=w.depth_ft, max_depth=md)
            if md and w.depth_ft > md:
                self.notify("tactic", f"a trap door dropped us from {td[1]} to {w.depth_ft} ft, below max_depth {md}: "
                                      "climbing back (deeper monsters until then)", news=True)

    def watch_thieves(self):
        """A thief in view in the dungeon: say so once per level, before it
        touches (mission 21: a Brigand stole an {excellent} armour and the
        Navigator only heard of it from the loss)."""
        w = self.w
        if not w.in_dungeon:
            return
        for y, x, r in w.monsters:
            kinds = {b.split(":")[1] for b in r.blows if b.split(":")[1:2] in (["EAT_ITEM"], ["EAT_GOLD"])}
            if not kinds or (w.level_t, r.name) in self.thieves_seen:
                continue
            self.thieves_seen.add((w.level_t, r.name))
            what = "items from your pack" if "EAT_ITEM" in kinds else "gold"
            self.notify("thief", f"{r.name} (lvl {r.level}, {w.dist((y, x))} away) steals {what} with a touch, then "
                                 f"teleports: kill it before it reaches you (`goal hunt {r.name.replace(' ', '_')}`), "
                                 "or keep away", news="EAT_ITEM" not in kinds)

    def watch_kills(self):
        """A unique slain: say so (its drop is worth picking up). Mission 21:
        Wormtongue died during explore and nobody noticed until his hammer."""
        w = self.w
        if not self.unique_names:
            self.unique_names = {r.name.lower() for r in w.g.races.values() if "UNIQUE" in r.flags}
        for ts, t in w.messages:
            if ts <= self.kills_t:
                continue
            m = re.match(r"You have (?:slain|destroyed) (.+?)\.$", t)
            if m and m.group(1).lower() in self.unique_names:
                self.unique_drop = (w.level_t, w.pos, ts)     # its drop is always picked up
                uk = self.uniques_killed()
                if m.group(1).lower() not in uk:
                    uk.add(m.group(1).lower())
                    try:
                        json.dump(sorted(uk), open(os.path.join(self.rundir, "uniques_killed.json"), "w"), indent=1)
                    except OSError:
                        pass
                self.notify("unique_slain", f"{m.group(1)} slain at {w.pos[0]},{w.pos[1]}: uniques drop good items "
                                            "(look at 'Item squares' around there)")
        self.kills_t = max([self.kills_t] + [ts for ts, _ in w.messages])

    def watch_drainers(self):
        """A mobile monster in view whose blows drain a stat: say so once per
        level (mission 19: a Giant red ant and frog, rated 1/5, took STR 18/40
        -> 18/10 and a blow; nothing had flagged them)."""
        w = self.w
        if not w.in_dungeon:
            return
        mine = 110 + int(w.ind.get("speed", [0])[0] or 0)
        for _, _, r in w.monsters:
            stats = r.drained_stats
            if not stats or "NEVER_MOVE" in r.flags or (w.level_t, r.name) in self.drainers_seen:
                continue
            self.drainers_seen.add((w.level_t, r.name))
            key = stats & {"STR", "DEX", "CON"}          # blows and HP: what a warrior can't spare
            weak = r.level <= w.clvl - 5 and r.speed <= mine and "UNIQUE" not in r.flags
            if weak:
                advice = "weak and no faster than you: kill it fast, don't walk away from it"
            else:
                advice = f"`avoid {r.name.replace(' ', '_')}`, or leave the level"
            # (a weak one is news, not a reason for the trip plan to leave the level: m33 left 650 ft for a Giant red
            # frog, m34's Navigator thought the same of others; it's fought when it comes)
            self.notify("drainer", f"{r.name} (lvl {r.level}) drains {', '.join(sorted(stats))} with its blows: "
                                   f"{advice}", news=not key or weak)

    def watch_progress(self):
        """A goal that goes nowhere: at most 10 different squares in 2 minutes
        while not fighting (mission 3 circled a '>' for 10 minutes, and no
        event woke the Navigator). Clear the server queue, restart the move,
        and say so."""
        w, now = self.w, gnow()
        if w.pos:
            self.pos_hist.append((now, w.pos, w.depth))
        while self.pos_hist and now - self.pos_hist[0][0] > 120:
            self.pos_hist.popleft()
        idle_goal = isinstance(self.goal, (Wait, RestGoal, Search, Recall, Recover, Shop)) or self.goal is None
        # Quick check: the mover is "moving" but we've stood on one square for
        # 20 s (mission 19: a flee resent a refused run for a minute, no alert)
        # (picking a lock or digging is progress: mission 20 fired this at a door)
        working = any(now - ts < 3 and t.startswith(("You failed to pick", "You have picked", "You tunnel",
                                                      "You dig", "You have removed", "You failed to make",
                                                      "This seems to be permanent", "The door "))
                      for ts, t in w.messages)
        # (acting in place is progress too: m57 12:20, plan town reading 7 Identify scrolls at the Alchemist for 20 s)
        la = self.last_action
        working = working or bool(la and now - la[0] < 4 and not str(la[1]).startswith(("walk", "pathfind", "run")))
        if not idle_goal and self.mover.active and not w.adjacent_monsters() and not w.resting and not working and \
                now - self.stuck_t > 60 and now - (self.goal_t or 0) > 20:
            recent = [q for t, q, d in self.pos_hist if now - t <= 20]
            if len(recent) >= 15 and len(set(recent)) == 1 and now - self.pos_hist[0][0] >= 20:
                self.stuck_t = now
                self.c.send("clear")
                self.mover.stop()
                self.notify("stuck", f"'{self.goal.describe()}' hasn't moved from {w.pos} for 20 s: cleared the "
                                     "command queue and restarted the move. If it happens again, give another goal")
                return
        if now - (self.goal_t or 0) < 110:
            return      # (the demo mission: 'stuck' 3 s into a goal, counting the idle time before it)
        # (a fight in the window doesn't count: mission 6 fired this in a
        # corridor fight with a wolf pack)
        fighting = now - max(w.last_hit_t, w.fight_t) < 120
        if idle_goal or fighting or w.adjacent_monsters() or w.resting or now - self.stuck_t < 120 or \
                not self.pos_hist or now - self.pos_hist[0][0] < 110 or \
                len({(p, d) for _, p, d in self.pos_hist}) > 10:
            return
        self.stuck_t = now
        self.c.send("clear")
        self.mover.stop()
        # the second time for the same goal, end it: restarting the move can't fix a goal whose own logic loops
        # (m30: a dive at 600 ft went nowhere for 6 minutes, restarted twice; the trip plan then moves on)
        if self.goal.stuck_once:
            self.goal.abort = f"went nowhere for 4 minutes (around {w.pos})"
            self.notify("stuck", f"'{self.goal.describe()}' has gone nowhere for 4 minutes (around {w.pos}): "
                                 "ending it", news=bool(self.plan))
            return
        self.goal.stuck_once = True
        self.notify("stuck", f"'{self.goal.describe()}' has gone nowhere for 2 minutes "
                             f"(around {w.pos}): cleared the command queue and restarted the move. "
                             "If it happens again, the goal ends")

    ABILITY_FLAGS = {"free_action": "free_act", "resist_blind": "res_blind", "resist_conf": "res_conf",
                     "see_invisible": "see_invis", "resist_nexus": "res_nexus", "hold_life": "hold_life",
                     "feather_fall": "feather"}

    def has_ability(self, order):
        """Free Action, a resist...: from the character sheet's grid (tool
        query 'flags') once read, else from the order of the same name."""
        if order in self.inferred:
            return True           # seen in play ("You are unaffected!"), not on the sheet
        known = self.w.has(self.ABILITY_FLAGS.get(order, order)) if hasattr(self.w, "has") else None
        if known is not None:
            return known
        return self.orders.get(order) == "yes"

    def group_danger(self):
        """Worst-case melee of everything that can reach us this turn, the
        Borg's way: max dice x speed (x our_slowness), +200 for a paralysing
        blow that beats 3/4 of our AC without Free Action; (total, names).
        Monsters that never move don't count (they only matter next to us, and
        we step away). No drain weight (the Borg adds 150 per drain blow; see
        the comment below). Replayed over Dive03's logs, 0.3x fired 5-14 s
        before every drop below 50% HP, 0.6x only 1-5 s before."""
        w = self.w
        lev = w.clvl
        ac = w.ind.get("armor", [0])[0]
        total, who = 0.0, []
        slow = self.our_slowness()
        for y, x, r in w.monsters:
            if "NEVER_MOVE" in r.flags:
                continue
            sx = (r.speed_x if r.speed_x is not None else max(1.0, (r.speed - 100) / 10)) * slow
            if w.dist((y, x)) > 1 + math.ceil(sx):
                continue
            mx, drains = r.worst_melee
            # (no drain term: the Advisor's mission 9 replay found it alone put a
            # lone Giant red frog at 0.6x; drains have their own rule, the second
            # drain on a level -> leave)
            g = mx * sx
            if r.paralyse_blow_power > ac * 3 / 4 and not self.has_ability("free_action"):
                g += 200
            if g:
                total += g
                who.append(r.name)
        return total, who

    # tables.c extract_energy, by speed (normal = 0): energy per game turn
    ENERGY = {-30: 200, -29: 200, -28: 200, -27: 200, -26: 200, -25: 200, -24: 200, -23: 300, -22: 300, -21: 300,
              -20: 300, -19: 300, -18: 300, -17: 300, -16: 300, -15: 400, -14: 400, -13: 400, -12: 400, -11: 400,
              -10: 500, -9: 500, -8: 500, -7: 500, -6: 600, -5: 600, -4: 700, -3: 700, -2: 800, -1: 900, 0: 1000}

    def our_slowness(self):
        """How many times faster than normal monsters act against us: 1 at normal speed or faster, 2 at -10,
        3.3 at -20 (m26: Gorged and slowed, six weak monsters adjacent took 270 -> 41 HP while no danger rule
        fired, the rules assuming our normal speed)."""
        sp = int((self.w.ind.get("speed") or [0])[0] or 0)
        if sp >= 0:
            return 1.0
        return 1000 / self.ENERGY.get(max(-30, sp), 200)

    def group_tick(self, now):
        """Tiers against current HP (Borg memo, tuned by the post-mortem memo):
        > 0.3x: disengage (just arrived: the stairs back; not yet in melee:
        back away); > 0.6x: the stairs underfoot; Phase Door only once HP is
        below think_hp; > 1.0x: leave the level by the nearest stairs, Phase
        Door when adjacent (every 10 s at most), and with no stairs known start
        Word of Recall now (it takes 15-34 player turns)."""
        w = self.w
        if not w.in_dungeon or not w.monsters:
            return False
        g, who = self.group_danger()
        hp = max(w.hp[0], 1)
        # Floor from the HP actually being lost (mission 9: a Cave spider swarm
        # took 77 -> 35 HP with one spider in view, and the sum stayed at 0.23x)
        lost = w.damage_rate(3.0) * 3.0
        if lost > g:
            g, who = lost, who + ["(HP falling ~%.0f/s)" % w.damage_rate(3.0)]
        if g <= 0.3 * hp:
            return False
        names = ", ".join(f"{n} x{c}" if c > 1 else n for n, c in collections.Counter(who).items())
        stairs_pending = w.last_stairs_cmd and not waited(w.last_stairs_cmd[1], 1.2)
        on_stairs = w.standing_on in ("<", ">") and not stairs_pending
        if g <= 0.6 * hp:
            if now - w.level_t < 6 and on_stairs:
                self.take_stairs(w.standing_on)
                self.notify("danger_avoided", f"arrived next to {names} (worst-case melee {g:.0f} vs HP {hp}): "
                                              "took the stairs back")
                return True
            fast = any((r.speed_x or 1) > 1 for y, x, r in w.monsters if "NEVER_MOVE" not in r.flags
                       and w.dist((y, x)) <= 6)
            if not w.adjacent_monsters() and not fast and isinstance(self.goal, (Explore, Hunt, Goto, Dive)):
                if self.group_warned != (w.level_t, names):
                    self.group_warned = (w.level_t, names)
                    self.notify("tactic", f"{names} can deal {g:.0f} at worst (HP {hp}): backing away, "
                                          "not walking into them")
                return self.retreat_step([m for m in w.monsters if "NEVER_MOVE" not in m[2].flags])
            return False
        if on_stairs:
            self.take_stairs(w.standing_on)
            self.notify("danger_avoided", f"{names} can deal {g:.0f} (HP {hp}): took the stairs underfoot")
            return True
        if g > hp and not isinstance(self.goal, (Flee, Recall, Recover)) and w.find("<>") \
                and now - self.flee_t > 10:
            self.flee_t = now
            prev = self.goal.describe() if self.goal else None
            self.set_goal(Flee("a dangerous group"))
            self.notify("danger_seen", f"group danger: {names} can deal {g:.0f} per turn at worst, HP {hp}"
                                       f"{' while ' + prev if prev else ''}: leaving the level")
        can_read = not w.flag("blind") and not w.flag("confused")
        far = not any(w.dist(q) <= 25 for q in w.find("<>"))   # (mission 14: stairs 66 away)
        if g > hp and far and can_read and not self.recall_started(now):
            wor = self.find_item("Word of Recall", TV_SCROLL)
            if wor:
                self.recall_t = now
                self.cmd(f"custom r item={wor['item']}", f"group danger {g:.0f} vs HP {hp}: word of recall",
                         hold=0.5)
                self.notify("emergency", f"{names} can deal {g:.0f} (HP {hp}) and no stairs are known: "
                                         "read Word of Recall now (it takes 8-23 s)", action=True)
                return True
        # Blind or confused (no scroll can be read) with the group's worst above our HP: the staff, which works blind
        # (m48: 13 Light hounds, 7 Wargs, 5 Mirkwood spiders; blind for 40 s, HP 340 -> 82, no read got through)
        if g > hp and not can_read and w.adjacent_monsters() and now - self.blind_tele_t > 10:
            tp = self.teleport_item()
            if tp and tp[0] == "u":
                self.blind_tele_t = now
                self.cmd(f"custom u item={tp[1]['item']}", f"group danger {g:.0f} vs HP {hp}, can't read: staff of "
                                                           "teleportation", hold=0.6)
                self.notify("emergency", f"{names} can deal {g:.0f} (HP {hp}) and you can't read (blind or confused): "
                                         "used the Staff of Teleportation", action=True)
                return True
        # Phase only when it's really going badly: at 0.6-1.0x only once HP is
        # already below think_hp, and at most every 10 s (mission 9: a lone
        # Giant red frog, 58 worst-case vs 97 HP, cost 4 Phase Doors at full HP)
        pd = self.phase_item()
        hurting = g > hp or w.hp_frac < self.orders["think_hp"]
        if w.adjacent_monsters() and pd and can_read and hurting and now - self.phase_t > 10:
            self.phase_t = now
            self.phase_hist.append(now)
            self.cmd(f"custom r item={pd['item']}", f"group danger {g:.0f} vs HP {hp}: phase door", hold=0.6)
            self.notify("tactic", f"{names} can deal {g:.0f} (HP {hp}): phased away")
            return True
        return False

    def stairs_beside_still(self, still):
        """The stairs we're walking to are a step away (or under us) and the
        stationary monsters beside us are harmless for a turn: take them, don't
        step away. m25: a Brown mold (confuses, so never fought) beside the only
        '>' at 300 ft; the step-away walked 6 squares back and the dive pressed
        '>' there, for 2 minutes. Confusion doesn't stop the stairs (cmd2.c)."""
        w = self.w
        goals = {g for g in (self.mover.goals or ()) if isinstance(g, tuple)} if self.mover.active else set()
        if not goals and self.still_goals[0] == w.level_t:
            goals = self.still_goals[1]
        # (on the stairs the mover has already stopped: ask the goal -- M1 looped on with the mover check alone)
        g = self.goal
        want = getattr(g, "want", None) if isinstance(g, Dive) else "<>" if isinstance(g, Flee) else None
        if want and w.standing_on in ("<", ">") and w.standing_on in want:
            goals = set(goals) | {w.pos}

        def stairs(g):
            return w.memory.get(g) in ("<", ">") or (g == w.pos and w.standing_on in ("<", ">"))

        if not any(w.dist(g) <= 1 and stairs(g) for g in goals):
            return False

        def harmless(r):
            bad = ("PARALYZE", "UN_BONUS", "DISENCHANT")
            return not r.drains and not any(b.split(":")[1:2] and b.split(":")[1] in bad for b in r.blows) \
                and r.per_turn < 0.25 * max(1, w.hp[0])

        return all(harmless(m[2]) for m in still)

    def still_fight_tick(self, now, still):
        """A stationary monster next to us that blocks the way (sits by the
        square the mover is heading for): kill it if it's weak, by standing
        still (auto-retaliate). Mission 6 stalled a step from the only '>'
        beside a Disenchanter eye, stepping away and back while its gaze
        disenchanted the weapon and armour. A disenchanter in the way too strong
        to kill: leave the level. One beside the path, not in the way, is
        stepped away from like any other (m33, m34)."""
        w = self.w
        lev = w.clvl
        # (squares only: a free run's goals are {"free-run"} -- a crash in m25)
        goals = {g for g in (self.mover.goals or ()) if isinstance(g, tuple)} if self.mover.active else set()
        if goals:
            self.still_goals = (w.level_t, set(goals))
        elif self.still_goals[0] == w.level_t:
            goals = self.still_goals[1]       # (the mover was stopped for the fight)

        def disenchants(r):
            return any("UN_BONUS" in b or "DISENCHANT" in b for b in r.blows)

        def killable(r):
            paralyses = any(b.split(":")[1:2] == ["PARALYZE"] for b in r.blows)
            nosave = {e for e in r.no_save_blows
                      if not self.has_ability("resist_blind" if e == "BLIND" else "resist_conf")}
            drains = r.drains or r.worst_melee[1] > 0   # (Red jelly STR, mission 15; Rot jelly CHR, 16)
            return r.level <= lev and not (paralyses and not self.has_ability("free_action")) \
                and not nosave and not drains

        # (only when it blocks the way, disenchanters too: m33 and m34 meleed Disenchanter molds beside the path, and
        # m33's shield lost +1 -- a mold can't follow, so stepping on past it costs nothing)
        targets = [m for m in still if any(w.dist(g, m[:2]) <= 1 for g in goals)]
        # (an item beside a disenchanter isn't worth the enchantment: m37 meleed a Disenchanter mold to reach Boldor's
        # drops, and the cloak and the new helm lost +1 each. The item is left; stairs and the way on still count)
        loot = self.loot_mem or {}
        for m in [m for m in targets if disenchants(m[2])]:
            items = [g for g in goals if w.dist(g, m[:2]) <= 1 and w.memory.get(g, " ") not in ".#%'+<>^:; "]
            if items and len(items) == len(goals):
                if loot.get("level") == w.level_t:
                    loot["done"] |= set(items)
                self.mover.stop()
                self.still_goals = (w.level_t, set())
                targets.remove(m)
                self.notify("tactic", f"left the item at {items[0][0]},{items[0][1]}: it lies beside a {m[2].name}, "
                                      "which would disenchant our gear", news=True)
        fight = [m for m in targets if killable(m[2])]
        if any(m[2].drains for m in still):
            fight = []      # (mission 16: killing a Green mold put it next to a Purple mushroom patch)
        if fight and (w.hp_frac >= self.orders["think_hp"] or self.still_fighting == (w.level_t, fight[0][:2])):
            m = fight[0]
            self.mover.stop()
            if self.still_fighting != (w.level_t, m[:2]):
                self.still_fighting = (w.level_t, m[:2])
                why = "disenchants" if disenchants(m[2]) else "blocks the way"
                self.notify("tactic", f"{m[2].name} (lvl {m[2].level}, never moves) {why}: killing it")
            return True
        bad = [m for m in targets if disenchants(m[2]) and not killable(m[2])]
        if bad and not isinstance(self.goal, (Flee, Recall, Recover)):
            prev = self.goal.describe() if self.goal else None
            self.set_goal(Flee(bad[0][2].name))
            self.notify("danger_seen", f"{bad[0][2].name} (lvl {bad[0][2].level}) disenchants and is too strong "
                                       f"to kill{' while ' + prev if prev else ''}: heading for the stairs")
            return True
        return False

    BUFF_MSGS = {"fast": ("You feel yourself moving faster!", "You feel yourself slow down."),
                 "hero": ("You feel like a hero!", "The heroism wears off."),
                 "shero": ("You feel like a killing machine!", "You feel less Berserk.")}

    def buff_on(self, buff):
        """A timed effect (fast, hero, shero) on now, from the game's start and end messages (the status
        reply has no indicator for them: `flag("fast")` was always False)."""
        on, off = self.BUFF_MSGS[buff]
        last = False
        for _, t in self.w.messages:
            if t.startswith(on):
                last = True
            elif t.startswith(off):
                last = False
        return last

    # --- the Navigator's executable standing orders (the user, 10-26: "decide in advance, act at Pilot speed") ---
    RULE_KINDS = {"leave": "leave the level when NAME is in view",
                  "hunt": "hunt NAME on sight (the hunt checks apply, as for `goal hunt NAME`)",
                  "thieves": "kill: hunt a thief (steals gold or items) in view within 6 squares",
                  "afraid": "teleport: afraid with no Heroism/Boldness/Berserk and monsters adjacent -> teleport"}

    def rules(self):
        if self.nav_rules is None:
            try:
                self.nav_rules = json.load(open(os.path.join(self.rundir, "rules.json")))
            except (OSError, ValueError, AttributeError):
                self.nav_rules = []
        return self.nav_rules

    def save_rules(self):
        try:
            json.dump(self.rules(), open(os.path.join(self.rundir, "rules.json"), "w"), indent=1)
        except (OSError, AttributeError):
            pass

    def has_rule(self, kind, arg=None):
        return any(r["kind"] == kind and (arg is None or r["arg"] == arg) for r in self.rules())

    def rule_tick(self, now):
        """Run the Navigator's reactions (`react`): leave the level when NAME is in view; hunt NAME on sight; kill thieves.
        True if it acted. (`react afraid teleport` runs in the fear handling.)"""
        w = self.w
        if not w.in_dungeon or not w.monsters or not self.rules() or isinstance(self.goal, (Flee, Recall, Recover)):
            return False
        done = self.rules_done
        names = {r.name.lower(): (y, x, r) for y, x, r in w.monsters}
        for rl in self.rules():
            arg = rl["arg"]
            if rl["kind"] == "leave" and arg in names and done.get(("leave", arg)) != w.level_t:
                done[("leave", arg)] = w.level_t
                pl = self.plan
                if pl and pl.phase == "level" and pl.level == w.level_t and not pl.paused:
                    pl.level_done = f"your rule: leave when {names[arg][2].name} is seen"
                    self.set_goal(pl.mark(pl.next_dive(self)))
                else:
                    self.set_goal(Flee(f"your rule: {names[arg][2].name} seen"))
                self.notify("rule", f"{names[arg][2].name} seen: leaving the level (your `react leave`)", news=True)
                return True
            target = None
            if rl["kind"] == "hunt" and arg in names:
                target = names[arg][2]
            if rl["kind"] == "thieves" and arg == "kill":
                th = [(w.dist((y, x)), r) for y, x, r in w.monsters
                      if any(b.split(":")[1:2] in (["EAT_ITEM"], ["EAT_GOLD"]) for b in r.blows) and w.dist((y, x)) <= 6]
                if th and not any(self.danger_why(r) for _, r in th):
                    target = min(th, key=lambda t: t[0])[1]
            if target is not None and not isinstance(self.goal, Hunt) and \
                    now - done.get(("hunt", target.name, w.level_t), -99.0) > 30:
                done[("hunt", target.name, w.level_t)] = now
                role = self.req_role
                # (M5, 10-28: a Scruffy looking hobbit's hunt replaced a `goal dive` and the dive was lost when it
                # ended. A plan resumes by itself; a plain goal comes back after the hunt)
                prev = self.goal if self.goal is not None and not self.goal.by_plan else None
                try:
                    out = self.do_request({"cmd": "goal", "args": ["hunt", target.name.replace(" ", "_")],
                                           "role": "navigator"})
                finally:
                    self.req_role = role
                if out.get("ok") and prev is not None:
                    self.resume_after = prev
                self.notify("rule", f"{target.name} in view: " + ("hunting it" if out.get("ok") else
                                                                 f"no hunt ({out.get('error', '')[:120]})")
                            + f" (your `react {rl['kind']}`)", news=True)
                return bool(out.get("ok"))
        return False

    def fear_cure(self):
        """The potion to quaff when afraid and in danger: Heroism first (it does all Boldness does, plus to-hit and
        HP), Boldness only without it, Berserk last (kept for hard fights) -- the user, 10-25; it was the pack's
        order before."""
        pots = self.w.items(tval=TV_POTION)
        return next((i for n in ("Heroism", "Boldness", "Berserk") for i in pots if n in i["name"]), None)

    def hard_fight(self):
        """The adjacent mobile monsters and whether the fight is hard (berserk_tick's test): a unique, or a monster
        within 5 levels of ours, adjacent; or two or more adjacent and HP under 75%."""
        w = self.w
        adj = [r for *_, r in w.adjacent_monsters() if "NEVER_MOVE" not in r.flags]
        hard = any("UNIQUE" in r.flags or r.level >= w.clvl - 5 for r in adj) or (len(adj) >= 2 and w.hp_frac < 0.75)
        return adj, bool(adj) and hard

    def speed_start_tick(self, now):
        """A Potion of Speed at the start of a hard fight (the user, 10-25, on the Advisor's replays: drunk at the
        start rather than when the emergency fires, it beat the rules in 3 of 4 hard fights -- the gain is mostly
        timing, the same potion drunk earlier). Same test as Berserk (hard_fight); not when already hasted."""
        w = self.w
        if not w.in_dungeon or self.buff_on("fast") or not waited(self.speed_start_t, 30):
            return False
        adj, hard = self.hard_fight()
        pot = next((i for i in w.items(tval=TV_POTION) if "Potion" in i["name"] and "of Speed" in i["name"]), None)
        if not (hard and pot):
            return False
        self.speed_start_t = now
        names = ", ".join(sorted({r.name for r in adj}))
        self.cmd(f"custom q item={pot['item']}", f"a hard fight ({names}): quaff {pot['name']} at the start", hold=0.6)
        self.notify("tactic", f"a hard fight with {names}: quaffed {one_of(pot['name'])} at the start", news=True)
        return True

    def berserk_tick(self, now):
        """A Potion of Berserk Strength at the start of a hard melee fight (the user, 10-25: carried, never used):
        +30 max HP and 30 healed, +24 to-hit, no fear, -10 AC for 25-50 turns (use-obj.c, xtra1.c). Hard: a
        unique, or a monster within 5 levels of ours, adjacent; or two or more adjacent and HP under 75%."""
        w = self.w
        if not w.in_dungeon or self.buff_on("shero") or not waited(self.berserk_t, 30):
            return False
        adj, hard = self.hard_fight()
        pot = self.find_item("Berserk", TV_POTION)
        if not (adj and hard and pot):
            return False
        self.berserk_t = now
        self.cmd(f"custom q item={pot['item']}", f"a hard fight ({', '.join(sorted({r.name for r in adj}))}): quaff "
                                                 f"{pot['name']}", hold=0.6)
        self.notify("tactic", f"a hard fight with {', '.join(sorted({r.name for r in adj}))}: quaffed "
                              f"{one_of(pot['name'])} (+to-hit, +30 HP, no fear)", news=True)
        return True

    def status_tick(self, now, mons_near):
        """Quaff the cheapest potion that cures a dangerous status in a fight
        (Advisor memo P4 + Erratum): stun at once, blind/confused when
        something is near, poison only when HP is also getting low."""
        w = self.w
        if not w.in_dungeon or not waited(self.cure_t, 1.5):
            return False
        in_combat = w.adjacent_monsters() or now - w.last_hit_t <= 3
        if not in_combat and not w.flag("blind"):     # (blind: the triggers below decide -- m43)
            return False
        want = []
        mobile_near = [m for m in mons_near if "NEVER_MOVE" not in m[2].flags]
        # (a mold can't follow: step away and let it wear off -- mission 15, the user)
        # Only when it matters (mission 16 spent a CCW on a stun at 167/180 and
        # CLW/CSW on blindness/confusion at 99% against level-6 Novice mages):
        # low HP, a heavy stun, or a monster near our level
        threat = w.hp_frac < self.orders["think_hp"] or any(m[2].level >= w.clvl - 5 for m in mobile_near)
        if w.flag("stun") and (threat or w.ind.get("stun", [0])[0] >= 2):
            want.append("stun")
        # Blind or confused and still being hit: cure whatever we can see (mission
        # 15: blind + confused 9 s with nothing in view, HP 160 -> 86, no cure)
        # (unseen means unseen: the set-piece C3 spent 4 CSW and 2 CCW in 18 s curing confusion from Kobold
        # shamans at 84-93% HP, because any hits counted here; the user: spend only when it matters)
        # (and blind, everything is unseen: m25 drank 2 CSW at 100% HP against a Novice mage's magic missiles,
        # ~1% of HP a second. Only when it matters: low HP, hurt and still being hit, or heavy damage)
        rate = w.damage_rate(3.0)
        hit_unseen = not mobile_near and now - w.last_hit_t <= 3 and (
            w.hp_frac < self.orders["think_hp"] or (w.hp_frac < 0.8 and rate > 0.01 * w.hp[1]) or
            rate > 0.04 * w.hp[1])
        if (mobile_near and threat or hit_unseen) and w.flag("confused"):
            want.append("confused")
        # (and blind in a fight we were in a moment ago, or while an escape needs to read: m43 23:20, blinded in a
        # 10-monster band at 84% HP -- no monster "near" can be seen blind, so it rested three times while unseen
        # things bit it, and the flee couldn't read its Magic Mapping. The user: "doesn't a cure potion fix that?")
        mm = self.mons_mem or {}
        seen_close = any(now - m["t"] < 10 and m.get("level") == w.level_t and w.pos and m.get("pos") and
                         w.dist(m["pos"]) <= 6 for m in mm.values())
        band_recent = self.band_warned[0] == w.level_t and now - self.band_warned_t < 30
        must_read = isinstance(self.goal, (Flee, Recall, Recover))
        # (but not again and again: m44's Light hounds re-blinded it with their breath and 16 CLW went in one fight.
        # After 2 blind cures in 30 s, fight on blind -- auto-retaliate needs no sight -- unless an escape must read or
        # HP is low)
        bc = [t for t in self.blind_cures if now - t < 30]
        self.blind_cures = bc
        spent = len(bc) >= 2 and not must_read and w.hp_frac >= self.orders["think_hp"]
        if w.flag("blind") and not spent and (mobile_near and threat or hit_unseen or seen_close or band_recent
                                                or must_read):
            want.append("blind")
        if w.flag("poisoned") and w.hp_frac < self.orders["think_hp"]:
            want.append("poisoned")
        pots = list(w.items(tval=TV_POTION))
        for status in want:
            for cure in STATUS_CURES[status]:
                pot = next((i for i in pots if cure in i["name"]
                            and not (cure == "Healing" and "*Healing*" in i["name"])), None)
                if pot:
                    self.cure_t = now
                    if status == "blind":
                        self.blind_cures.append(now)
                    self.cmd(f"custom q item={pot['item']}", f"{status} in combat: quaff {pot['name']}", hold=0.6)
                    self.notify("tactic", f"{status} in combat: quaffed {one_of(pot['name'])}")
                    return True
            if now - self.nocure_t > 20:
                self.nocure_t = now
                self.notify("tactic", f"{status} in combat and no potion cures it "
                                      f"(needs {' / '.join(STATUS_CURES[status][:2])})")
        return False

    def unseen_tick(self, now):
        w = self.w
        if not w.in_dungeon or w.flag("blind"):
            return False          # (blind, everything is "it": fight on)
        if now - w.heard[0] < 2 and w.heard[0] > self.heard_warned:
            self.heard_warned = w.heard[0]
            # news, not an alert: it woke the Navigator five times in mission 20
            # with nothing to do
            self.notify("unseen_attacker", "heard a door burst open: something is coming; be ready to leave",
                        news=True)
        cause = None
        if now - w.unseen[0] < 3:
            cause = w.unseen[1]
        elif self.orders.get("unseen_hp") == "on" and now - w.monster_seen_t > 4 and \
                now - w.last_hit_t > 4 and w.hp[0] < w.hp[1] and w.damage_rate(3.0) >= max(2.0, 0.01 * w.hp[1]) \
                and not w.flag("poisoned") and not w.flag("cut") and w.hunger > 1 and now - w.level_t > 4 \
                and now - w.explained_t > 10:
            # HP falling steadily although nothing has been in view -- or hit us
            # by name ("The Yellow mold ...") -- for 4 s: the fight's own damage
            # stays in the 3-s window after a kill, which fired this after nearly
            # every kill in mission 4
            cause = f"losing HP ({w.damage_rate(3.0):.0f}/s) with nothing in view"
        if not cause or isinstance(self.goal, (Flee, Recall, Recover)) or now - self.unseen_warned < 20:
            return False
        self.unseen_warned = now
        # Minor, at good HP: teleport-to ("It commands you to return": Tengu,
        # blink dogs), a magic missile or an arrow from the dark. Mission 6 fled
        # levels over these; tell the Navigator and carry on.
        # A shriek (a Shrieker mushroom patch) does no damage: it wakes and
        # hastens monsters nearby (mission 17 left a 100 ft level over one)
        if "shriek" in cause:
            self.notify("unseen_attacker", f"'{cause}': a shrieker (no damage; it wakes monsters nearby); "
                                           "carrying on", news=True)
            return False
        # A weak caster we can see (in the dark the game still says "It ..."):
        # mission 20 fled down a '>' twice from Novice priests 3 squares away
        casters = [r for y, x, r in w.monsters if r.spells and w.dist((y, x)) <= 10 and r.level <= w.clvl - 5
                   and "UNIQUE" not in r.flags]
        if casters and not cause.startswith("losing HP") and w.hp_frac >= self.orders["think_hp"]:
            self.notify("unseen_attacker", f"'{cause}': probably the {casters[0].name} (lvl {casters[0].level}) in "
                                           f"view; carrying on (HP {w.hp_frac:.0%})", news=True)
            return False
        if re.search(r"commands you to return|magic missile|fires an arrow|fires a bolt|mumbles|"
                     r"points at you and curses|casts a fearful illusion", cause) \
                and w.hp_frac >= self.orders["think_hp"]:
            self.notify("unseen_attacker", f"'{cause}': minor attack from something unseen; carrying on "
                                           f"(HP {w.hp_frac:.0%})", news=True)
            return False
        prev = self.goal.describe() if self.goal else None
        # a gaze may be a paralysing spell: deadly without Free Action, where a
        # walk to far stairs is worse than a recall (mission 21's "stares deep")
        para = re.search(r"stares deep|gazes deep|looks deep|gazes at", cause) and \
            not self.has_ability("free_action")
        hint = " (it may be paralysis and you have no Free Action: if the stairs are far, read Word of Recall)" \
            if para else ""
        # Above 80% HP: news only (the Advisor's A5: curses, darkness and confusion from the dark changed
        # levels at full HP in m17-m21; set-piece A5's Dark elven priest). A paralysing gaze still leaves.
        if w.hp_frac > 0.8 and not para:
            self.notify("unseen_attacker", f"'{cause}': something unseen is casting at you; carrying on at HP "
                                           f"{w.hp_frac:.0%} (it leaves below 80%)", news=True)
            return False
        if self.hunt_ordered(gnow(), "an unseen attacker"):
            return False
        if w.find("<>"):
            self.set_goal(Flee("unseen attacker"))
            self.notify("unseen_attacker", f"'{cause}': something unseen is attacking"
                                           f"{' while ' + prev if prev else ''}; heading for the stairs{hint}")
        else:
            self.notify("unseen_attacker", f"'{cause}': something unseen is attacking and no stairs are known: "
                                           "consider Word of Recall or Phase Door")
        return True

    def sidestep(self, threats):
        """One step to a free square next to none of threats (stationary
        monsters: one square away is enough). Returns True if a step was sent."""
        w = self.w
        now = gnow()
        if now - self.sidestep_t < 0.8:
            return True               # the last step is still on its way
        occupied = {m[:2] for m in w.monsters}
        cands = [(w.pos[0] + dy, w.pos[1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx]
        cands = [t for t in cands if passable(w.memory.get(t, " ")) and t not in occupied
                 and all(w.dist(t, m[:2]) > 1 for m in threats)]
        if not cands:
            return False
        # prefer ground we've walked (known safe), then fewer monsters next to it
        best = min(cands, key=lambda t: (t not in w.walked,
                                         sum(1 for m in w.monsters if w.dist(t, m[:2]) <= 1)))
        self.sidestep_t = now
        self.cmd(f"walk {direction(w.pos, best)}", f"step away from {threats[0][2].name}", hold=0.3)
        return True

    def retreat_step(self, threats, reach=15):
        """Move away from threats over ground we've already walked this level
        (the user: kiting into unknown areas piles on more monsters). Returns
        True while retreating."""
        w = self.w
        if self.mover.active and self.retreating:
            st = self.mover.tick()
            if st == "moving":
                return True
            self.retreating = False
        if not threats or not w.pos:
            return False
        def far(t):
            return min(w.dist(t, m[:2]) for m in threats)
        here = far(w.pos)
        cands = [t for t in w.walked if w.dist(t) <= reach and far(t) >= max(here + 2, 4)]
        if not cands:
            return False
        best = max(cands, key=lambda t: (far(t), -w.dist(t)))
        if self.mover.go([best]):
            self.retreating = True
            return True
        return False

    def quiet_spot(self, reach=30):
        """A square to wait on (QuietWait): one we've walked this level, inside a room (7+ of its 8 neighbours open
        floor), 4+ from any unexplored square and 3+ from a door; the most sheltered (far from the unknown) of the
        near ones. None if there's no such square within reach."""
        w = self.w
        front = self.frontier()
        doors = [q for q, ch in w.memory.items() if ch in "+'"]

        def room(t):
            return sum(1 for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy or dx)
                       and w.memory.get((t[0] + dy, t[1] + dx)) == ".") >= 7

        def far(t, qs):
            return min((w.dist(t, q) for q in qs), default=99)

        cands = [t for t in w.walked if w.dist(t) <= reach and w.memory.get(t) == "." and room(t)]
        cands = [(min(far(t, front), 10), t) for t in cands if far(t, doors) >= 3]
        cands = [(f, t) for f, t in cands if f >= 4]
        if not cands:
            return None
        return max(cands, key=lambda ft: (ft[0] - w.dist(ft[1]) / 3, -w.dist(ft[1])))[1]

    def seen_pos(self, t):
        """Where we were at time t (for 'You see' messages): the position then."""
        return self.w.pos if self.w.pos_t <= t + 0.5 else None

    def flee_failed(self, goal=None):
        """A flee that can't reach the stairs, with monsters close: don't go
        idle among them (mission 14: Lagduf's pack, stairs 66 away, the
        Navigator had to read Word of Recall itself) -- start a recall and
        phase out of reach while it charges. A planned leave for a band at high HP with nothing on us
        first looks for stairs (BandLeave), once per level."""
        w, now = self.w, gnow()
        self.flee_fail_t = now
        soft = self.band_soft_levels
        if goal and "band" in goal and w.in_dungeon and w.level_t not in soft and w.hp_frac >= 0.8 and \
                not w.adjacent_monsters() and not any(self.danger_why(r) for *_, r in w.monsters) and \
                not self.recall_started(now):
            soft.add(w.level_t)
            names = sorted({r.name for y, x, r in w.monsters if w.dist((y, x)) <= 10}) or ["the band"]
            self.set_goal(BandLeave(names))
            return
        # (decoded or only listed by the server, as danger_seen counts them:
        # mission 15's Brodda was listed 0.1 s before the map decode, so this
        # saw nothing and no Word of Recall was read at full HP)
        # (a dangerous one counts at any range: set-piece A2I's Ibun cast fire bolts and Slow from 12-13
        # squares for 7 s while this waited for him to come within 5)
        near = [m for m in w.monsters if w.dist(m[:2]) <= 5 or self.danger_why(m[2])] + \
            [(None, None, r) for r in w.listed_only() if self.danger_why(r)]
        if not w.in_dungeon or not near or w.flag("blind") or w.flag("confused"):
            return
        if not self.recall_started(now):
            wor = self.find_item("Word of Recall", TV_SCROLL)
            if wor:
                self.recall_t = now
                self.cmd(f"custom r item={wor['item']}", "flee failed with monsters close: word of recall", hold=0.5)
                self.notify("emergency", f"couldn't reach the stairs with {len(near)} monsters close: read Word of "
                                         "Recall (8-23 s); phasing while it charges", action=True)
                return
        pd = self.phase_item()
        if pd and w.adjacent_monsters() and now - self.phase_t > 2.5:
            self.phase_t = now
            self.phase_hist.append(now)
            self.cmd(f"custom r item={pd['item']}", "flee failed, monsters adjacent: phase door", hold=0.6)

    def choke_tick(self, now):
        w = self.w
        lev = w.clvl
        pack = [m for m in w.monsters if w.dist(m[:2]) <= 10 and m[2].level >= lev - 5]
        if self.choke_state == "going":
            st = self.mover.tick()
            if st == "moving":
                return True
            self.choke_state = "holding"
            self.choke_t = now
            self.log("act", cmd="-", why=f"holding the corridor at {w.pos}")
            return True
        if self.choke_state == "holding":
            if not pack or now - self.choke_t > 25:
                self.choke_state = None
                return False
            return True           # stand; auto-retaliate greets them one by one
        if len(pack) < 3 or choke_tier(w.memory, w.pos) is not None or now - self.choke_done_t < 15:
            return False
        # A corridor square within 10 steps, further from the pack than we are
        cy = sum(m[0] for m in pack) / len(pack)
        cx = sum(m[1] for m in pack) / len(pack)
        d_now = max(abs(w.pos[0] - cy), abs(w.pos[1] - cx))
        mem = w.memory
        cands = []
        for (y, x), ch in mem.items():
            if w.dist((y, x)) > 10 or ch in "#%*: 12345678":
                continue
            if max(abs(y - cy), abs(x - cx)) <= d_now:
                continue
            tier = choke_tier(mem, (y, x))
            if tier is not None:
                cands.append((tier, (y, x)))
        if not cands:
            self.choke_done_t = now
            return False
        best = min(t for t, _ in cands)
        cands = [c for t, c in cands if t == best]
        if self.mover.go(cands):
            self.choke_state = "going"
            self.choke_done_t = now
            self.notify("tactic", f"{len(pack)} monsters coming ({pack[0][2].name}): backing into a corridor")
            return True
        self.choke_done_t = now
        return False

    def watch_breeders(self):
        """Breeders (lice, worms...) multiply without end and block every path:
        tell the agent once per level that it's time to leave."""
        w = self.w
        br = [r for *_, r in w.monsters if "MULTIPLY" in r.flags]
        # (again when weak ones swarm: m40's Giant fruit flies grew to 16 after a news-only notice, boxed the Pilot in
        # and made it stuck; the trip only leaves on a notice that isn't news)
        swarm = len(br) >= 8 and self.breeder_level == w.level_t and self.breeder_weak
        if (len(br) >= 3 and self.breeder_level != w.level_t) or swarm:
            self.breeder_level = w.level_t
            if isinstance(self.goal, Dive):
                return            # a dive is leaving this level anyway
            # Weak ones (Blue worm masses at clvl 19) are only news: they wake
            # the Navigator for nothing (mission 3)
            lev = w.clvl
            weak = all(r.level <= lev - 10 for r in br) and len(br) < 8
            self.breeder_weak = weak
            self.notify("breeders", f"{len(br)} breeding monsters in view ({br[0].name}): leave this level "
                                    "(stairs, or recall)" + (" if they get in the way" if weak else ""), news=weak)

    def use_stair_location(self, why):
        """Use a Staff or zap a Rod of Door/Stair Location (an unknown flavour too, when the
        flavour table knows it). True if it acted."""
        w = self.w
        if gnow() < self.busy_until or w.flag("blind") or w.flag("confused"):
            return False
        for it in w.items():
            kind = it["name"] if " of " in it["name"] else (self.flavour_of(it) or {}).get("kind", "")
            if it["tval"] in (55, 66) and "Door/Stair Location" in kind and "(0 charges)" not in it["name"] \
                    and "charging" not in it["name"]:
                self.cmd(f"custom {'u' if it['tval'] == 55 else 'z'} item={it['item']}",
                         f"{why}: Door/Stair Location", hold=0.8)
                return True
        return False

    def watch_character(self):
        """Tell the agent when a stat gets drained or the blows change (the
        user lost a blow to a DEX-draining invisible monster)."""
        ind = self.w.ind
        if not ind:
            return
        # Per stat (current, top); a drain lowers current with top unchanged
        # (an equipment change moves both). Missions 5 and 6: a second drain of
        # an already drained stat (DEX 15 -> 14) said nothing when this only
        # compared which stats were drained.
        drained = {n: tuple(ind[f"stat{i}"][:2]) for i, n in enumerate(self.STAT_NAMES)
                   if len(ind.get(f"stat{i}", [])) >= 2}
        blows = ind.get("skills2", [None])[0]
        if self.seen_drained is not None:
            new = [n for n, (cur, top) in drained.items() if n in self.seen_drained
                   and cur < self.seen_drained[n][0] and top == self.seen_drained[n][1]]
            if new:
                full = {"STR": "Strength", "INT": "Intelligence", "WIS": "Wisdom", "DEX": "Dexterity",
                        "CON": "Constitution", "CHR": "Charisma"}
                # (the tavern stash first: m46's Navigator read "at the Alchemist" and planned to buy one, with a
                # Restore Dexterity waiting in the tavern)
                def where(n):
                    k = f"Restore {full[n]}"
                    at = self.stash_where(k)
                    if at:
                        return f"Potion of {k}: one is in the {'house' if at == 'house' else 'tavern stash'} -- " \
                               "`plan town` fetches it, don't buy one"
                    return f"Potion of {k} at the Alchemist (5), ~470 (the Temple doesn't sell them)"
                self.notify("stat_drained", f"{', '.join(new)} drained (blows {blows}); levels don't restore it: "
                            + "; ".join(where(n) for n in new))
                # Second drain on this level from something in view: leave
                # (Borg memo §3.2; mission 7's scorpion drained STR three times)
                w = self.w
                # Drained by something we can't see (not a trap's dart): leave at once. m29 and m30 lost DEX to a
                # Moaning spirit (invisible, passes walls, +10 speed, TOUCH:LOSE_DEX; "It wails at you", "It
                # touches you"): it can't be fought or walked away from, and each drain costs a ~470 potion
                now = gnow()
                trap = any(now - ts < 4 and re.search(r"dart|trap|rune", t, re.I) for ts, t in w.messages)
                seen = any(r.drains or r.worst_melee[1] > 0 for *_, r in w.monsters)
                if w.in_dungeon and not trap and not seen and set(new) & {"STR", "DEX", "CON"}:
                    self.notify("drainer", f"an unseen monster drained {', '.join(new)} (invisible: a Moaning spirit or "
                                           "a Quasit at these depths): leaving the level", news=False)
                    if not self.plan and w.find("<>") and not isinstance(self.goal, (Flee, Recall, Recover)):
                        self.set_goal(Flee("an unseen stat drainer"))
                elif w.monsters and w.in_dungeon:
                    n = self.drains_here[1] + 1 if self.drains_here[0] == w.level_t else 1
                    self.drains_here = (w.level_t, n)
                    mine = 110 + int(w.ind.get("speed", [0])[0] or 0)
                    weak = [r for *_, r in w.adjacent_monsters() if r.drains and "NEVER_MOVE" not in r.flags
                            and "UNIQUE" not in r.flags and r.level <= w.clvl - 5 and r.speed <= mine]
                    if n >= 2 and weak and not isinstance(self.goal, (Flee, Recall, Recover, Hunt)):
                        # A weak drainer beside us: walking away hands it more bites
                        # (mission 19: the flee bumped walls while a Giant red frog
                        # drained STR again; one round of 'hunt' killed it)
                        self.set_goal(Hunt(weak[0].name))
                        self.notify("tactic", f"drained twice on this level by {weak[0].name} (lvl {weak[0].level}, "
                                              "no faster than you) adjacent: killing it rather than walking away")
                    elif n >= 2 and w.find("<>") and not isinstance(self.goal, (Flee, Recall, Recover, Hunt)):
                        prev = self.goal.describe() if self.goal else None
                        self.set_goal(Flee("stat drain"))
                        self.notify("danger_seen", f"drained twice on this level ({', '.join(new)}) with "
                                                   f"{', '.join(sorted({r.name for *_, r in w.monsters}))} in view"
                                                   f"{' while ' + prev if prev else ''}: leaving the level")
        if self.seen_blows is not None and blows is not None and blows != self.seen_blows:
            self.notify("blows_changed", f"blows per round {self.seen_blows} -> {blows}")
        self.seen_drained, self.seen_blows = drained, blows
