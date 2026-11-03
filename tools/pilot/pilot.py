#!/usr/bin/env python3
"""pilot -- plays a MAngband character second to second; an agent steers it.

Runs as a daemon that owns the client (mangclient -mtool). Each tick (~20/s) it applies the client's events to its
World, answers requests, then acts on the first layer that acts: the reflexes (survival: death, emergency escape,
group danger, cures, danger in view, fear, hunger, adjacent monsters, rest; see Pilot.reflexes), the Navigator's
`react` rules, the Pilot's item work at quiet moments, one step of the current goal, the trip plan, and last the
idle rule (Word of Recall after idle_recall_s without the agent).

The agent talks to it through pilotctl.py (a unix socket): status, goals, plans, orders, actions, and wait-attention
(block until the pilot needs a decision). The code as it is: docs/pilot-core.md (this module, the tick loop),
docs/pilot-combat.md (reflexes, escape), docs/goals-and-plans.md, docs/commands.md; the player's view: HANDBOOK.md.
"""
import collections
import csv
import json
import os
import queue
import random
import re
import socket
import sys
import threading
import time

from common import (HERE, VERSION, TV_SCROLL, TV_FOOD, TV_FLASK, TV_LITE, DEFAULT_ORDERS, weapon_brand,
                    weapon_damage, flavour_key, kind_key, bare_name, one_of, recall_level, singular)
from world import (World, gnow, set_time_factor, time_factor, model_factor, wall_of, wall_since, waited,  # noqa: E402
                   ghold, light_fuel, set_fast_ok, measured_rate, _lt, frozen)
import structures                                # noqa: E402
import geareval                                  # noqa: E402
from report import ReportMixin                   # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "observe"))
import shopmath                                  # noqa: E402
from mover import Mover, MAX_HGT, MAX_WID   # noqa: E402
from goals import (Goal, Wait, Goto, Explore, Dive, Search, Hunt, Reprieve,  # noqa: E402
                   WalkAway, Flee, Recall, Resurrect, RestGoal, QuietWait)
from town_goals import (EDGE_DIR, edge_of, Town, TownFarm, Shop, StashDeposit, StashFetch,       # noqa: E402
                        town_houses, HouseBank, TownKit)
from plan import TripPlan, split_specs           # noqa: E402
from gear import GearMixin, shadow_agree         # noqa: E402
from items import (ItemsMixin, PY_FOOD_MAX, ADJ_STR_BLOW, ADJ_DEX_BLOW, ADJ_STR_HOLD, BLOWS_TABLE,  # noqa: E402
                   WARRIOR, TV_WEAPONS, stat_index, weapon_blows, type_word)
from town import TownMixin                       # noqa: E402
from combat import CombatMixin, CURE_POTIONS, HEALS, choke_tier, heal_of, STATUS_CURES   # noqa: E402
# (not named in this file: kept as P.Goal, P.shadow_agree, P.weapon_damage, ... for the tools)
REEXPORTED = (Goal, EDGE_DIR, StashDeposit, StashFetch, weapon_brand, weapon_damage, kind_key, shadow_agree,
              PY_FOOD_MAX, ADJ_STR_BLOW, ADJ_DEX_BLOW, ADJ_STR_HOLD, BLOWS_TABLE, WARRIOR, TV_WEAPONS, stat_index,
              weapon_blows, type_word, TV_FLASK, TV_FOOD, CURE_POTIONS, HEALS, choke_tier, heal_of, STATUS_CURES)

SHOP_CUT = shopmath.SHOP_CUT   # what a shop pays Dive04 of an item's value at CHR 3 (34-43%; Black Market 10%)


# Items whose use the pilot verifies and resends (not unknown scrolls: a
# resend could read a second one)
USE_VERIFY = ("Phase Door", "Word of Recall", "Teleport", "Cure Light Wounds", "Cure Serious Wounds",
              "Cure Critical Wounds", "Healing", "Boldness", "Heroism", "Berserk", "Cure Poison",
              "Neutralize Poison")


class Attention(Exception):
    pass


# --------------------------------------------------------------------------

class Pilot(ReportMixin, GearMixin, ItemsMixin, TownMixin, CombatMixin):
    def __init__(self, client, rundir, orders=None, say=print):
        self._init_state()
        self.c = client
        self.w = World(client)
        self.mover = Mover(client, self.w, log=lambda *a, **k: self.log("move", **k))
        self.rundir = rundir
        os.makedirs(rundir, exist_ok=True)
        # Standing orders persist across restarts
        self.orders_file = os.path.join(rundir, "orders.json")
        saved = {}
        if os.path.exists(self.orders_file):
            with open(self.orders_file) as f:
                saved = {k: v for k, v in json.load(f).items() if k in DEFAULT_ORDERS}
        self.orders = dict(DEFAULT_ORDERS, **saved, **(orders or {}))
        self.dlog = open(os.path.join(rundir, "decisions.jsonl"), "a", buffering=1)
        self.say = say
        # what each shop's owner is and what it charged (the town kit's prices and routing)
        self.stores_file = os.path.join(rundir, "stores.json")
        try:
            self.stores_seen = {int(k): v for k, v in json.load(open(self.stores_file)).items()}
        except (OSError, ValueError):
            self.stores_seen = {}
        self.debt_path = os.path.join(rundir, "navigator_debt.json")
        try:
            self.debt = json.load(open(self.debt_path))
        except (OSError, ValueError):
            self.debt = {"entries": []}
        try:
            self.keep = set(json.load(open(os.path.join(rundir, "keep.json"))))
        except (OSError, ValueError):
            self.keep = set()
        try:
            self.standing = json.load(open(os.path.join(rundir, "standing.json")))
        except (OSError, ValueError):
            self.standing = []
        self.plan = TripPlan.load(self)           # (a restart mid-trip carries on with it)
        self.load_mission()                       # (and a mission with its label)
        if self.plan:
            self.log("plan_resumed", plan=self.plan.text, phase=self.plan.phase)
        # Where the town's '>' is (remembered across runs: the town never changes)
        self.town_file = os.path.join(os.path.dirname(rundir.rstrip("/")), "town.json")
        # Server-wide flavour table and this character's deepest level
        self.flavour_file = os.path.join(os.path.dirname(rundir.rstrip("/")), "..", "flavours.json")
        self.load_flavours()
        self.deepest_file = os.path.join(rundir, "deepest.json")
        try:
            with open(self.deepest_file) as f:
                self.deepest_ft = json.load(f)["ft"]
        except (OSError, ValueError, KeyError):
            self.deepest_ft = 0
        if os.path.exists(self.town_file):
            with open(self.town_file) as f:
                self.town_stairs = json.load(f).get("stairs")

    def _init_state(self):
        """Every attribute of the Pilot's state, with its default: no client, files or sockets (refactor-candidates E6:
        nothing is created lazily). __init__ then does the I/O: the client, its World and Mover, the rundir and the
        files loaded from it (orders, stores, debt, keep, standing, plan, mission, flavours, deepest, town). The I/O
        handles themselves -- c, rundir, dlog, say and the file paths -- are set by __init__ only: a Pilot.for_test()
        has none, and its file loads and saves fall back as with no files (they catch the AttributeError)."""
        self.recent_acts = collections.deque(maxlen=40)   # for the observer's note snapshots
        self.w = None                  # the World (__init__: on the client; for_test: the case's)
        self.mover = None
        self.orders = dict(DEFAULT_ORDERS)
        self.goal = None
        self.requests = queue.Queue()
        self.attention = []            # pending attention events (for wait-attention)
        self.news = []                 # informational events since the last report
        self.att_cond = threading.Condition()
        self.last_agent = gnow()
        self.busy_until = 0.0
        self.idle_recalled = False
        self.last_action = None
        self.emergency_t = 0.0
        self.think_warned = 0.0
        self.picked_t = 0.0
        self.emerg_times = []
        self.loop_warned = 0.0
        self.retreating = False
        self.fearers_seen = set()
        self.drainers_seen = set()     # (level_t, race name) drainer warnings given
        self.inferred = set()          # abilities seen in play (watch_abilities)
        self.unique_drop = None        # (level_t, pos, t) of the last unique killed
        self.aware_cache = (-1, set())
        self.policy_t = 0.0
        self.room_t = 0.0
        self.ability_sources = set()   # unidentified worn items that may give them
        self.stores_seen = {}          # what each shop's owner is and what it charged (stores.json)
        self.stores_noted_t = 0.0
        self.ability_seen_t = gnow()
        self.debt = {"entries": []}    # navigator_debt.json
        self.keep = set()              # keep.json
        self.report_seq, self.last_report = 0, (0, 0.0)   # Navigator reports: number, time of the last
        self.hp_min_since = None       # lowest HP since the last audit_check
        self.escalation_t = 0.0        # last emergency-type alert (escape records)
        self.items_level, self.items_last, self.items_depth = None, [], 0   # this level's floor items (itemlist)
        self.equip_letters_lower = False  # item_index: a lowercase letter is an equipment letter (takeoff)
        self.phase_hist = collections.deque()   # emergency Phase Door times (futility check)
        self.traps_here, self.trap_seen_t = (None, 0), gnow()
        self.band_warned = (None, 0)   # (level_t, size) of the last band warning
        self.band_warned_t = 0.0
        self.thieves_seen = set()      # (level_t, race name) thief warnings given
        self.thief_hit_t = 0.0
        self.kills_t = gnow()     # messages scanned for unique kills
        self.item_pending = []         # (due, level_t, name): interesting_item alerts held 2.5 s
        self.unique_names = None
        self.fear_t = 0.0
        self.skipped_items = set()     # (level, square) of junk we chose to leave
        self.resume_after = None
        self.plan, self.plan_t = None, 0.0      # the Navigator's intent (plan trip), run by the Pilot
        # the belief state (step 2.5; the Advisor's starting-over memo §3.4): what the report
        # can't show from one snapshot
        self.mons_mem = {}           # name -> {"level": level_t, "pos", "n", "t", "danger", "unique"}
        self.hits = collections.Counter()      # (level_t, name) -> hits landed since it was last slain
        self.belief_msg_t = 0.0
        self.gain_hist = collections.deque(maxlen=80)    # (t, exp, gold) every 15 s
        self.standing = []             # standing.json
        self.autodestroy_t = 0.0
        self.parking = None
        self.light_t = self.light_warned = 0.0
        self.light_warned_key = None
        self.flavours, self.junk_kinds = {}, {}   # (load_flavours)
        self.deepest_ft = 0            # deepest.json
        self.town_stairs = None        # town.json
        self.recall_t = 0.0
        self.sidestep_t = 0.0
        self.unseen_warned = self.heard_warned = 0.0
        self.pos_hist = collections.deque()
        self.gaps_logged = set()
        self.gap_since = {}
        self.stuck_t = 0.0
        self.flee_t = 0.0
        self.flee_fail_t = 0.0
        self.wear_queue = False
        self.breeder_level = None
        self.choke_state = None
        self.choke_t = self.choke_done_t = 0.0
        self.seen_drained = None
        self.dead = False
        self.pending_use = None               # a read/quaff to verify (verify_use)
        self.held_t = 0.0
        self.expects = []                     # actions waiting for their effect (verify_effects)
        self.news_wait_t = 0.0                # news shown by wait reports up to here
        self.audit_t, self.audit_runs, self.audit_counts = 0.0, 0, {}
        self.wild_trail, self.trail_level = [], None
        self.eat_t = 0.0
        self.flavour_watch = None
        self.id_target = None
        self.weapons_t, self.weapon_tips = 0.0, set()
        self.found_t = gnow()
        self.unanswered = []                  # user messages the Navigator hasn't answered (say)
        self.nav_view, self.nav_view_events = (0.0, [], ""), []   # what the Navigator last read
        self.avoid_zones, self.avoid_names = {}, set()           # the Navigator's no-go zones
        self.structs, self.struct_t = {}, 0.0      # (level, (Y, X)) -> inner room / pit / nest found
        self.item_hold_until = 0.0            # a dive pauses after interesting_item
        self.far_seen = set()                 # (level, item) valuables seen beyond loot_radius
        self.effect_failures = 0
        self.redraw_t, self.redraw_level = 0.0, None
        self.factor_logged, self.rate_logged, self.factor_log_t = 1.0, None, 0.0
        self.group_warned = None
        self.mons_log_t = 0.0
        self.drains_here = (None, 0)          # (level, stat drains seen on it)
        self.still_goals = (None, set())      # (level, mover goals) before a stationary-monster fight
        self.still_fighting = None            # (level, position) of the stationary monster we're killing
        self.seen_blows = None
        self.unreachable = set()       # frontier tiles we failed to reach (this level)
        self.visited = set()           # squares we've stood on while exploring (not frontier)
        self.searched = set()          # (level, square) dead ends searched for secret doors
        self.level_seen = None
        self.phase_t = self.cure_t = self.noescape_t = 0.0
        self._escape_walk = None       # escaping_to_stairs: (mover walk_id, level_t) of escape()'s walk to stairs
        self.full_warned = 0.0
        self.running = True
        # --- (E6) once created lazily, where first used; the defaults are the ones those uses had ---
        # set by main() after the start
        self.arch_token, self.hpwarn, self.live = None, 0, False
        # control requests and the Navigator / Architect
        self.acting = "pilot"          # who the action is for: pilot / plan / nav / arch (tick, handle_requests)
        self.req_role = "navigator"    # the role of the request being handled
        self.report_state = None       # (numbered: the last report's order state, for stale_order)
        self.asks_sent, self.ask_seq = [], 0      # ask_architect: send times (rate limit), the last question's id
        self.arch_answers = []         # (t, id, text) of the Architect's answers
        self.nav_rules = None          # rules.json, loaded on first use (rules)
        self.rules_done = {}
        self.review = None             # review.json, loaded on first use (review_state)
        self.mission_label = self.mission_base = None   # (load_mission, the mission command)
        # goals
        self.goal_t = None             # when the goal was set (None: never; each use keeps its old default)
        self.goal_ending = None        # (step_goal: the goal just ended)
        self.walkaway_failed = set()   # level_t where a WalkAway failed
        self.scummed, self.kept = set(), set()    # Dive: (depth, arrival) scummed from; depths the server keeps
        self.fled_from = None          # Flee: (depth, t, level_t, the login level) of the last level fled by stairs
        self.flee_tele_t = -99.0
        self.first_level_t = None      # the level we logged in on (save_level_map)
        self.fetching = None           # StashFetch / HouseBank: the item being fetched
        # commands sent
        self.item_cmd_t = 0.0          # the last item command (cmd holds the next until the pack is back)
        self.act_walls = collections.deque(maxlen=50)   # wall clock of each command (shadow_results)
        self.escape_read_t, self.escape_from = -99.0, (None, None)   # the last escape read (escape_line)
        self.last_escape = None        # (log_escape)
        self.read_failed_t = -99.0
        # reflexes, escapes and fights
        self.conf_since, self.conf_cure_t, self.conf_tele_t, self.conf_cures = None, 0.0, 0.0, {}
        self.summoner_hold_t = 0
        self.smoke_t = 0
        self.speed_t = 0
        self.speed_start_t = 0         # (speed_start_tick)
        self.berserk_t = 0             # (berserk_tick)
        self.blind_tele_t = -99.0      # (group_tick)
        self.blind_cures = []
        self.nocure_t = 0
        self.caster_t, self.caster_said = -99.0, None   # kill_caster_step
        self.weak_band_said = None
        self.band_shadow_seen, self.band_shadow_t = {}, -99.0
        self.hard_fight_seen, self.hard_fight_t = {}, -99.0
        self.shadow_est, self.shadow_gear_said = None, None   # shadow_decision
        self.engage = {"target": None, "t0": 0.0, "replan_t": 0.0, "dropped": set()}
        self.engage_ok = {}
        self.band_soft_levels = set()
        self.breeder_weak = False
        self.junk_msgs_done = set()
        self.frozen_said = False
        self.unlit_try_t = 0
        # looks (which monsters are asleep)
        self.look_t, self.look_key, self.looks_read_t = -99.0, None, 0.0
        self.asleep = {}
        # items, town and house
        self.loot_mem = {}
        self.left_news = set()         # (level_t, name) "left ..." said
        self.drop_fetched = set()
        self.id_tries = {}
        self.jewel_swap = None
        self.gear_swapped_t = 0
        self.food_warned = None
        self.supply_told = set()
        self.edge_cross, self.surface_last = None, None   # note_edge_cross
        self.trapdoor = None           # (watch_traps)
        self.recall_restored, self.recall_saved = False, None   # recall_memory (recall.json)
        # gains and rates
        self.gold_last = self.xp_last = None   # the last tick's gold and exp (None: none seen yet)
        self.gold_found = self.gold_sold = self.gold_stolen = self.xp_gained = 0
        self.depth_t = None
        self.level_base = None         # (t, exp, level_t) on arriving on this level
        self.rates = None              # rates.json, loaded on first use (rate_state)
        self.rate_open = None
        # reports
        self.since = None              # since_reset / track_since
        self.exp_seen = self.exp_t = None
        self.compact_prev, self.compact_hinted = None, False
        self.map_snap = None           # save_level_map
        self.feeling_level = self.level_feeling = None
        # caches: the rulebook's tables and the files read on first use (None: not read yet)
        self._uk = self._drops = self._ego_flags = self._fight_rows = self._sim = self._stock = None
        self._town_books = self._house = None
        self._pay_cache, self._sim_cache, self.gear_eval_cache = {}, {}, {}

    @classmethod
    def for_test(cls, world, **overrides):
        """A Pilot for the unit cases: its state declared (_init_state), `world` its World, and no I/O: log() a no-op,
        and no client, rundir or decisions.jsonl (a case that needs one sets it, e.g. p.rundir = a temp dir; the file
        loads and saves that catch the AttributeError run as with no files). Overrides set attributes (orders=...)."""
        p = cls.__new__(cls)
        p._init_state()
        p.w = world
        p.log = lambda *a, **k: None
        for k, v in overrides.items():
            setattr(p, k, v)
        return p

    # --- logging / attention -------------------------------------------------

    def crop(self, rows=5, cols=15):
        """A small map snapshot around us, for the log (the Advisor: so
        situations can be checked afterwards)."""
        w = self.w
        if not w.rows or not w.pos:
            return None
        y, x = w.pos
        return [r[max(0, x - cols):x + cols + 1] for r in w.rows[max(0, y - rows):y + rows + 1]]

    def log(self, kind, **kw):
        rec = {"t": round(time.time(), 3), "kind": kind, "depth": self.w.depth, "pos": self.w.pos,
               "hp": self.w.hp, **kw}
        if kind in ("attention", "nav_journal", "user_note") and "crop" not in rec:
            rec["crop"] = self.crop()
        if kind in ("act", "attention", "goal", "goal_done", "goal_failed", "note"):
            self.recent_acts.append({"t": rec["t"], "kind": kind,
                                     "what": kw.get("cmd") or kw.get("what") or kw.get("goal") or kw.get("text"),
                                     "why": kw.get("why") or kw.get("detail")})
        self.dlog.write(json.dumps(rec) + "\n")

    # Events that don't need a decision (the pilot already acted): shown in
    # the next report instead of waking the agent
    NEWS = {"danger_avoided", "started", "tactic", "resumed", "plan"}
    # while a trip plan runs, these are news: the plan acts on them itself
    PLAN_QUIET = {"goal_done", "goal_failed", "interesting", "danger_seen", "band", "structure", "breeders", "drainer",
                  "fearer", "stuck", "interesting_item", "unique_slain", "pack_full", "thief", "unseen_attacker",
                  "fight_going_badly", "emergency"}

    def notify(self, what, detail=None, news=False, action=None, fields=None):
        """action: an `emergency` notice must say whether it reports an escape action (True: a read, quaff, staff,
        stairs, a walk to stairs) or not (False: waiting, fighting on, attacking a caster first). Only actions count
        towards the emergency loop's three in 90 s (refactor-candidates A4; the unit case
        emergency_notices_say_if_action fails on one that doesn't say). fields: extra fields on the attention event
        and its decisions.jsonl record (a `supplies` notice's `supply` and `level`: D14), so readers filter without
        parsing the detail. They never replace the record's own fields (`what` is the kind)."""
        if what in ("emergency", "emergency_loop", "danger_seen", "danger_avoided", "fight_going_badly",
                    "unseen_attacker", "band", "stat_drained"):
            self.escalation_t = gnow()      # (escape records: stairs taken in an emergency)
        if what in ("emergency", "tactic") and gnow() - self.held_t < 0.05 and detail and \
                any(k in detail for k in ("quaffed", "read ", "phase")):
            # the action this reports was held, not sent (mission 10 reported 3
            # CLW quaffs with 1 CLW in the pack)
            self.log("note", text=f"not reported (held): {detail}")
            return
        ev = {"t": round(gnow(), 3), "what": what, "detail": detail,
              "goal": self.goal.describe() if self.goal else None}
        ev.update({k: v for k, v in (fields or {}).items() if k not in ev})
        if what == "emergency" and action:
            self.count_escape()
        source = None
        news_asked = news             # (before the plan turns its events into news: the band shadow's test)
        if self.plan and what not in ("plan", "plan_done", "plan_failed"):
            self.plan.on_event(self, what, detail, news or what in self.NEWS)
            if not self.plan.paused and what in self.PLAN_QUIET:
                news, source = True, "plan"   # (the plan handles these: the Navigator reads them as news)
        if what == "plan":
            source = "plan"
        extra = {"source": source} if source else {}
        extra.update({k: v for k, v in (fields or {}).items() if k not in ("what", "detail", "kind", "t")})
        if what == "emergency" and self.w.in_dungeon:
            extra["shadow"] = self.shadow_decision(detail)
        # (news_asked: under a trip plan every band notice became news first, and no band record was ever made -- m48)
        if what == "band" and self.w.in_dungeon and not news_asked:
            sh_band = self.band_shadow(detail)
            if sh_band:
                extra["shadow"] = sh_band
        if what in ("emergency", "emergency_loop"):
            # (the Advisor's estimator memo: the remembered map around @, 21x21, and the monsters, for replays)
            w = self.w
            if w.pos:
                y, x = w.pos
                extra["map21"] = ["".join(w.memory.get((yy, xx), " ") for xx in range(x - 10, x + 11))
                                  for yy in range(y - 10, y + 11)]
                extra["map_at"] = [y - 10, x - 10]
                extra["mons"] = [(my, mx, r.name) for my, mx, r in w.monsters]
        self.log("attention", what=what, detail=detail, **extra)
        if what in self.NEWS or news:
            self.news.append(ev)
            self.news = self.news[-20:]
            return
        with self.att_cond:
            self.attention.append(ev)
            self.att_cond.notify_all()

    # --- low-level actions ---------------------------------------------------

    def cmd(self, line, why, hold=0.4):
        # One read/quaff of ours at a time: until the last one is confirmed its
        # stack can still shrink and shift the pack letters (mission 9 read
        # "item=7" as Word of Recall 5 s after a potion stack ran out, then
        # read the real one as "item=5")
        # (m57 12:04: a Potion of Speed, the last of its stack, then 1 s later "quaff item=3" for Berserk -- the
        # letters had shifted and it drank a Cure Light Wounds; the Berserk "showed no effect" and was resent twice.
        # No item command until the pack has come back since the last one, 3 s at most)
        item_cmd = re.match(r"custom [qrEuzaF] item=", line) and not why.startswith("agent:")
        lt = self.item_cmd_t
        stale = item_cmd and lt and self.w.inven_t < lt and gnow() - lt < 3
        if (self.pending_use and re.match(r"custom [rq] item=", line) and not why.startswith("agent:")) or stale:
            self.log("note", text=f"held ({'the pack has not come back since the last item command' if stale else 'a read/quaff is still unconfirmed'}): {why}")
            self.busy_until = gnow() + ghold(0.3)
            self.held_t = gnow()     # notify() drops the caller's "quaffed ..." report
            # (callers set their rate-limit clock before calling: undo it, so
            # this is retried as soon as the last use is confirmed)
            if "recall" in why.lower():
                self.recall_t = 0.0
            elif "phase" in why.lower():
                self.phase_t = 0.0
            else:
                self.cure_t = 0.0
            return
        self.c.send(line)
        if item_cmd:
            self.item_cmd_t = gnow()
            self.w.inven_dirty = True        # (the next refresh fetches the pack: the hold above lasts ~0.3 s)
        self.last_action = (gnow(), line, why)
        self.busy_until = gnow() + ghold(hold)
        self.act_walls.append(time.time())
        mr = re.match(r"custom [ru] item=(\d+)", line)
        if mr:
            iu = next((i for i in self.w.items() if i["item"] == int(mr.group(1))), None)
            if iu and re.search(r"Teleport|Phase Door", iu["name"]):
                self.escape_read_t = gnow()
                self.escape_from = (self.w.pos, one_of(iu["name"]))    # (the status line's ESCAPE LANDING)
        self.log("act", cmd=line, why=why, by=self.acting)
        self.log_escape(line, why)
        self.expect_effect(line, why)
        if re.match(r"custom [qruazE] item=", line):
            self.watch_flavours()
        # Verify the pilot's own escapes and cures by their effect (post-mortem
        # memo §4.2: both Dive03 deaths were escapes that never ran)
        m = re.match(r"custom [rq] item=(\d+)$", line)
        if m and not why.startswith("agent:") and self.w.in_dungeon:
            it = next((i for i in self.w.items() if i["item"] == int(m.group(1))), None)
            core = next((c for c in USE_VERIFY if it and c in it["name"]), None)
            if core:
                self.pending_use = {"line": line, "t": gnow(), "core": core, "tries": 0, "why": why}
                self.mover.hold_clear_until = gnow() + ghold(3.0)

    # Commands whose effect shows in the pack, the equipment or the level
    # (the game-state survey, rule 3: an action is done when its signal comes)
    EFFECTS = (
        (re.compile(r"custom [wt] item="), "equip"),
        (re.compile(r"custom [kdEF] item=|eat \d|custom ,"), "pack"),
        (re.compile(r"custom [<>]$"), "level"),
    )

    def effect_sig(self, kind):
        w = self.w
        if kind == "level":
            return w.level_t
        return tuple((i["name"], i["number"]) for i in w.items(equip=(kind == "equip")))

    def expect_effect(self, line, why):
        if why.startswith("agent:"):
            return                          # the agent gets its own answer (do_request)
        for rx, kind in self.EFFECTS:
            if rx.match(line):
                self.expects.append({"kind": kind, "t": gnow(), "why": why,
                                     "sig": self.effect_sig(kind)})
                return

    def verify_effects(self):
        """Report actions whose effect never showed (3 s), instead of
        letting them pass as done."""
        now = gnow()
        keep = []
        for e in self.expects:
            if self.effect_sig(e["kind"]) != e["sig"]:
                continue                    # confirmed
            if not waited(e["t"], 3.0):
                keep.append(e)
                continue
            self.log("note", text=f"effect_failed ({e['kind']} unchanged after 3 s): {e['why']}")
            self.effect_failures += 1
            if e["kind"] != "level":      # (stairs are retried by the goals themselves)
                self.notify("tactic", f"no effect seen: {e['why']}")
        self.expects = keep

    def audit_tick(self, now):
        """The state audit (the game-state survey, 'measurement'): every 30 s
        compare the pilot's model with a fresh query, log each difference by
        field ('audit' records in decisions.jsonl), count them, and resync
        (redraw) when anything differs; in town also every 2 minutes."""
        w = self.w
        if w.depth == 0 and now - self.redraw_t > 120:
            w.need_redraw = True
        if now - self.audit_t < 30 or w.store or now < self.busy_until:
            return
        self.audit_t = now
        model = {"pack": [(i["name"], i["number"]) for i in w.inven if not i["equip"]],
                 "equip": [i["name"] for i in w.inven if i["equip"]],
                 "hp": list(w.hp), "gold": w.ind.get("gold", [None])[0],
                 "depth": w.depth, "pos": w.pos, "hunger": w.hunger}
        try:
            st = self.c.status()
            inv = self.c.inven()
        except Exception:
            return
        fresh = {"pack": [(i["name"], i["number"]) for i in inv if not i["equip"]],
                 "equip": [i["name"] for i in inv if i["equip"]],
                 "hp": st["ind"].get("hp", [0, 1])[:2], "gold": st["ind"].get("gold", [None])[0],
                 "depth": st["ind"].get("depth", [None])[0],
                 "pos": (st["y"], st["x"]) if st["y"] >= 0 else w.pos,
                 "hunger": st["ind"].get("hunger", [w.hunger])[0]}
        # (hp only out of melee: in a fight it's a timing race -- the Advisor's
        # mission 13 audit memo)
        # (a burning light's turns tick down between the two reads: "14402" vs
        # "14400 turns" was mission 17's only difference)
        def unlit(v):
            return re.sub(r"with \d+ turns", "with N turns", repr(v))
        diffs = {k: (model[k], fresh[k]) for k in model if model[k] != fresh[k] and
                 not (k == "hp" and (abs(model[k][0] - fresh[k][0]) <= 3 or w.adjacent_monsters())) and
                 not (k in ("pack", "equip") and unlit(model[k]) == unlit(fresh[k]))}
        self.audit_runs += 1
        self.log("audit_check", n=self.audit_runs, differences=len(diffs),
                 exp=st["ind"].get("exp"), clvl=w.clvl, depth_ft=w.depth_ft,   # (exp: for XP-rate studies)
                 stats={n: st["ind"].get(f"stat{i}") for i, n in enumerate(self.STAT_NAMES)},
                 blows=st["ind"].get("skills2", [None])[0], ac=st["ind"].get("armor"),
                 gold=st["ind"].get("gold", [None])[0], banked=self.banked(),
                 # per-check state (the Advisor's scorecard memo §5.4)
                 resting=bool(w.resting), in_combat=bool(w.adjacent_monsters() or gnow() - w.last_hit_t < 5),
                 recall_pending=bool(w.recall_pending), goal=self.goal.describe() if self.goal else None,
                 hp_min=self.hp_min_since)
        self.hp_min_since = None
        for k in diffs:
            self.audit_counts[k] = self.audit_counts.get(k, 0) + 1
        if diffs:
            self.log("audit", diffs={k: [str(a)[:200], str(b)[:200]] for k, (a, b) in diffs.items()})
            w.need_redraw = True
            w.inven, w.inven_t = inv, now          # the fresh copy wins

    def verify_use(self):
        """A pending read/quaff: done when the server says what's left ("You
        have 9 Scrolls of Phase Door (j)." / "You have no more ...") or a
        recall starts; resent (twice at most) if nothing within 2.5 s."""
        p, now = self.pending_use, gnow()
        if not p:
            return
        if self.dead or self.w.ghost:
            self.pending_use = None           # (mission 10 kept resending after death)
            return
        said = [t for ts, t in self.w.messages if ts >= p["t"] - 0.05]
        # (the server refused the read -- blind, confused, no light: m48's Word of Recall at 21:32:54 was refused 1 s
        # later, "You can't see anything.", and the Pilot waited 8 s for it and wouldn't try again. Now: done at once,
        # the escape timers reset, and teleport_item turns to the staff for 10 s)
        if any(t.startswith(("You can't see anything", "You are too confused", "You have no light to read"))
               for t in said):
            self.pending_use = None
            self.read_failed_t = gnow()
            self.escape_read_t = -99.0
            self.recall_t = 0.0
            self.notify("tactic", f"'{p['why']}': the read was refused ({next(t for t in said if t.startswith(('You ca', 'You are too', 'You have no l')))}): "
                                  "the next escape uses a staff or a cure first")
            return
        if any(t.startswith("You have") and p["core"] in t for t in said) or \
                any("The air about you becomes charged" in t for t in said):
            self.pending_use = None
            self.w.inven_dirty = True          # re-read the pack now, before the next use
            self.w.refresh()
            return
        # Never resent: a second Word of Recall cancels the first, a second Teleportation lands somewhere else (the
        # Advisor's estimator memo: m26 resent a recall that had gone through). Wait longer for the answer, then give
        # up on it -- the next decision sees whether it happened
        if p["core"] in ("Word of Recall", "Teleport"):
            if waited(p["t"], 8.0):
                self.pending_use = None
                self.notify("tactic", f"'{p['why']}': no answer seen in 8 s; not resending it (a second read would "
                                      "cancel or double it)")
            return
        if not waited(p["t"], 2.5):
            return
        if p["tries"] >= 2 or not self.w.in_dungeon:
            self.pending_use = None
            self.notify("tactic", f"'{p['why']}' still shows no effect after 2 resends: giving up on it")
            return
        p["tries"] += 1
        p["t"] = now
        self.mover.hold_clear_until = now + ghold(3.0)
        self.c.send(p["line"])
        self.log("act", cmd=p["line"], why=f"resend (no effect seen): {p['why']}")
        self.notify("tactic", f"'{p['why']}' showed no effect: resent it")

    def take_stairs(self, which):
        self.mover.stop()
        self.w.last_stairs_cmd = (which, gnow())
        self.cmd(f"custom {which}", f"stairs {which}", hold=0.3)

    def start_resting(self):
        if not self.w.resting and gnow() > self.busy_until:
            self.cmd("rest", "rest", hold=1.0)
            self.w.status_t = 0

    def stop_resting(self):
        if self.w.resting:
            self.cmd("rest", "stop resting", hold=0.5)
            self.w.status_t = 0

    # --- perception helpers --------------------------------------------------

    def frontier(self, center=None, radius=None, rubble=False):
        """Known open squares next to unknown ones (rubble=True: rubble squares
        next to unknown ones instead, a way on by digging)."""
        mem = self.w.memory
        out = []
        for (y, x), ch in mem.items():
            if rubble != (ch == ":"):
                continue
            if ch in "#%* " or ch in "12345678" or (y, x) in self.unreachable:
                continue
            if center and radius and max(abs(y - center[0]), abs(x - center[1])) > radius:
                continue
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if (y + dy, x + dx) not in mem and 0 < y + dy < 65 and 0 < x + dx < 197:
                        out.append((y, x))
                        break
                else:
                    continue
                break
        return out

    def resolve_target(self, t):
        w = self.w
        if t in ("<", ">", "stairs"):
            return w.find("<>" if t == "stairs" else t)
        if t == "item":
            # not the square we're on, nor items the junk filter left lying (a
            # 'goto item' ended at once, standing on a junk item it wouldn't take)
            # ('=' and '~' are terrain only on the surface: in the dungeon they're
            # rings, amulets, chests and lights -- mission 16's rings were missing)
            skip = "#%.'+<>^;:* 12345678" + ("" if w.in_dungeon else "=~")
            return [p for p, ch in w.memory.items() if ch not in skip
                    and p != w.pos and (w.level_t, p) not in self.skipped_items]
        m = re.match(r"^(\d+)[ ,](\d+)$", str(t))
        if m:
            return [(int(m.group(1)), int(m.group(2)))]
        return []

    def pillared(self):
        """A pillared room near us (the user: these often hold stairs)."""
        w = self.w
        if not w.rows or not w.pos:
            return False
        y0, x0 = w.pos
        for y in range(max(1, y0 - 8), min(65, y0 + 9)):
            row = w.rows[y][max(0, x0 - 25):x0 + 26]
            if re.search(r"(#\.){4}", row) or re.search(r"(\.#){4}", row):
                return True
        return False

    def interesting(self):
        so = set(self.orders["stop_on"].split(","))
        w = self.w
        why = []
        if "unique" in so:
            u = sorted({r.name for _, _, r in w.monsters if "UNIQUE" in r.flags})
            if u:
                why.append("unique: " + ", ".join(u))
        if "items" in so and w.itemlist and not w.itemlist[0].startswith("You see no"):
            why.append("items: " + "; ".join(l.strip() for l in w.itemlist[:6]))
        if "pillared" in so and self.pillared():
            why.append("pillared room (often holds stairs)")
        return "; ".join(why)

    def room_door(self, Y, X):
        """An inner room's door, if the map shows one at any of its 4 places."""
        return next((d for d, _ in structures.door_spots(Y, X) if self.w.memory.get(d) in ("+", "'")), None)

    def recall_memory(self):
        """A pending Word of Recall survives a Pilot restart in the game but not in our memory (the client only says
        "becomes charged" once): kept in runs/pilot/NICK/recall.json, restored at start when the depth still matches.
        The hot-swap set-piece H1r: the new Pilot's plan read a second scroll, which cancelled the pending one."""
        w = self.w
        path = os.path.join(self.rundir, "recall.json")
        if not self.recall_restored:
            if w.depth is None:
                return
            self.recall_restored = True
            try:
                st = json.load(open(path))
            except (OSError, ValueError):
                st = None
            if st and st.get("pending") and st.get("depth") == w.depth and time.time() - st.get("t", 0) < 600 and \
                    not w.recall_pending:
                w.recall_pending, w.recall_pending_t = True, gnow()
                self.notify("tactic", "a Word of Recall read before the restart is still pending: not reading another",
                            news=True)
        now_st = (w.recall_pending, w.depth)
        if now_st != self.recall_saved:
            self.recall_saved = now_st
            try:
                json.dump({"pending": w.recall_pending, "depth": w.depth, "t": time.time()}, open(path, "w"))
            except OSError:
                pass

    # --- the belief state (restructure step 2.5) ---------------------------------
    def belief_tick(self, now):
        w = self.w
        for y, x, r in w.monsters:
            m = self.mons_mem.get(r.name)
            if not m or m["level"] != w.level_t or now - m["t"] > 1:
                n = sum(1 for *_, q in w.monsters if q.name == r.name)
                self.mons_mem[r.name] = {"level": w.level_t, "pos": (y, x), "n": n, "t": now,
                                         "danger": bool(self.danger_why(r)), "unique": "UNIQUE" in r.flags}
            else:
                m["t"] = now
                if w.dist((y, x)) < w.dist(m["pos"]):
                    m["pos"] = (y, x)
        for ts, t in w.messages:
            if ts <= self.belief_msg_t:
                continue
            m = re.match(r"You (?:hit|smite|bite|claw|bash) (?:the )?(.+?)[.!]$", t)
            if m:
                self.hits[(w.level_t, m.group(1).lower())] += 1
            # gold from sales, for the rolling XP-per-gold rate (rate_tick)
            m = re.match(r"You sold .+? for (\d+) gold", t)
            if m:
                self.gold_sold += int(m.group(1))
            # (m37: the cloak and the new helm lost +1 each to a Disenchanter mold; nothing in the news)
            m = re.match(r"Your (.+?) \(.\) (?:was|were) disenchanted!", t)
            if m:
                self.notify("disenchanted", f"{m.group(1)} lost a plus (disenchanted)", news=True)
            # (m51, m53: Novice rogues took 2617 and 2392 gold, ~10% of the purse a touch, and nothing said so; the
            # session-8 Architect called both losses "unexplained")
            m = re.match(r"(\d+) coins were stolen!", t) or re.match(r"Your (.+?) \(.\) (?:was|were) stolen!", t)
            if m:
                gold = m.group(1).isdigit()
                if gold:
                    self.gold_stolen += int(m.group(1))
                self.notify("thief", f"{m.group(1) + ' gold' if gold else m.group(1)} stolen by a touch"
                                     + (f" ({self.gold_stolen} stolen since the Pilot started)" if gold else ""),
                            news=True)
            m = re.match(r"You have (?:slain|destroyed|killed) (?:the )?(.+?)[.!]$", t)
            if m:
                k = m.group(1).lower()
                self.hits.pop((w.level_t, k), None)
                mm = next((v for n, v in self.mons_mem.items() if n.lower() == k), None)
                if mm:
                    mm["n"] -= 1
                    if mm["n"] <= 0:
                        self.mons_mem = {n: v for n, v in self.mons_mem.items() if v is not mm}
        self.belief_msg_t = max([self.belief_msg_t] + [ts for ts, _ in w.messages])
        self.track_gains(now)

    def track_gains(self, now):
        # gold found: rises in the dungeon only (the Rates line counted purchases and sales; the scorecard's
        # gold_found, the same way)
        w = self.w
        g = w.ind.get("gold", [0])[0]
        if w.in_dungeon and self.gold_last is not None and g > self.gold_last:
            self.gold_found += g - self.gold_last
        self.gold_last = g
        xp = (w.ind.get("exp") or [0])[0]
        dxp = max(0, xp - (xp if self.xp_last is None else self.xp_last))
        if dxp:
            self.xp_gained += dxp
        self.xp_last = xp
        # XP and minutes by depth (for `prep`: where the XP has been), kept with the rates
        last = self.depth_t
        if w.in_dungeon and w.depth_ft:
            if last is not None and now - last < 5:
                d = self.rate_state().setdefault("depth", {}).setdefault(str(w.depth_ft), [0, 0])
                d[0] += dxp
                d[1] = round(d[1] + now - last, 1)
            self.depth_t = now
        else:
            self.depth_t = None
        self.rate_tick(now)
        # XP since arriving on this level (the Navigators' "stay or leave": m31-m34 asked for a per-level rate)
        lb = self.level_base
        if w.in_dungeon and (not lb or lb[2] != w.level_t):
            self.level_base = (now, (w.ind.get("exp") or [0])[0], w.level_t)
        if not self.gain_hist or now - self.gain_hist[-1][0] >= 15:
            self.gain_hist.append((now, (w.ind.get("exp") or [0])[0], g, self.gold_found))
            self.save_mission()

    def save_mission(self):
        """The running mission (label, its start and the totals so far) in mission.json: a restart or hot-swap
        carries it on (m44/m45: the swap lost the label, so `mission end` needed it by name)."""
        mb = self.mission_base
        if not (mb and self.mission_label):
            return
        try:
            json.dump({"label": self.mission_label, "age": round(gnow() - mb[0], 1), "exp": mb[1], "gold": mb[2],
                       "found": self.gold_found - (mb[3] if len(mb) > 3 else 0)},
                      open(os.path.join(self.rundir, "mission.json"), "w"))
        except OSError:
            pass

    def load_mission(self):
        try:
            path = os.path.join(self.rundir, "mission.json")
            if time.time() - os.path.getmtime(path) > 1800:
                return          # (a mission nobody ended, long ago)
            ms = json.load(open(path))
            # (gold_found starts at 0 in a new process: the base goes negative by what was found before)
            self.mission_label = ms["label"]
            self.mission_base = (gnow() - ms["age"], ms["exp"], ms["gold"],
                                 self.gold_found - ms["found"])
        except (OSError, ValueError, KeyError, TypeError):
            pass

    # the rolling exchange rate between XP and gold (the user, 10-25: "the real limiting factor is time"): XP earned per
    # gold earned (found + sold) over the recent play, in 10-minute buckets, the last RATE_WINDOW with any gain; seeded
    # with the shadow series m35-m42 (14190 XP, 12900 found, 21794 sold over 319 min: 0.41), which fades out as real
    # buckets fill the window. Used by the estimator (shadow mode) and shown by `gear`.
    RATE_BUCKET_S = 600
    RATE_WINDOW = 30
    RATE_SEED = (14190, 12900 + 21794)
    RATE_SEED_MIN = 319            # (the seed's minutes: m35-m42)
    RATE_CLAMP = (0.1, 3.0)

    def rate_state(self):
        st = self.rates
        if st is None:
            try:
                st = json.load(open(os.path.join(self.rundir, "rates.json")))
            except (OSError, ValueError, AttributeError):
                st = {}
            st.setdefault("buckets", [])
            self.rates = st
        return st

    def rate_tick(self, now):
        cur = (self.xp_gained, self.gold_found + self.gold_sold)
        op = self.rate_open
        if op is None or now - op[0] >= self.RATE_BUCKET_S:
            if op is not None:
                d = [c - b for c, b in zip(cur, op[1])]
                if any(d):
                    st = self.rate_state()
                    st["buckets"] = (st["buckets"] + [[round(time.time()), d[0], d[1]]])[-self.RATE_WINDOW:]
                    try:
                        json.dump(st, open(os.path.join(self.rundir, "rates.json"), "w"))
                    except (OSError, AttributeError):
                        pass
            self.rate_open = (now, cur)

    def xp_per_gold(self):
        """XP per gold from recent play: the buckets, plus the seed weighted by the window's unfilled share."""
        b = self.rate_state()["buckets"]
        seed_w = max(0.0, 1 - len(b) / self.RATE_WINDOW)
        xp = sum(x[1] for x in b) + seed_w * self.RATE_SEED[0]
        gold = sum(x[2] for x in b) + seed_w * self.RATE_SEED[1]
        lo, hi = self.RATE_CLAMP
        return round(min(hi, max(lo, xp / gold)), 3) if gold > 0 else 1.0

    def drainers_info(self, args):
        """`drainers [STAT] [MAXLEVEL]`: monsters whose blows drain a stat, by
        native level (the Navigator's mission 19 wish: the ant and the frog
        drained STR unflagged). Default: STR/DEX/CON, up to clvl + 10."""
        stats = {a.upper() for a in args if a.upper() in self.STAT_NAMES}
        lv = next((int(a) for a in args if a.isdigit()), self.w.clvl + 10)
        want = stats or {"STR", "DEX", "CON"}
        rows = sorted((r.level, r.name, sorted(r.drained_stats & want), "NEVER_MOVE" in r.flags, r.speed)
                      for r in self.w.g.races.values() if r.drained_stats & want and r.level <= lv)
        if not rows:
            return f"no monster up to level {lv} drains {', '.join(sorted(want))}"
        return f"monsters up to level {lv} ({lv * 50} ft) that drain {', '.join(sorted(want))}:\n" + "\n".join(
            f"  lvl {l:2d} ({l * 50} ft) {n}: {', '.join(st)}" + (" (stationary)" if still else "") +
            (f" (speed +{sp - 110})" if sp > 110 else "") for l, n, st, still, sp in rows)

    def user_note(self, text):
        """The user's commentary while watching (tools/observe/watch.py or
        pilotctl note): logged with a snapshot of the moment, in the
        decision log (kind user_note) and in commentary.jsonl, so it can be
        cross-referenced with the play. A note starting with '?' is a
        question for the Architect."""
        w = self.w
        recent = list(self.recent_acts)[-8:]
        rec = {"t": round(time.time(), 3), "note": text, "question": text.startswith("?"),
               "depth_ft": w.depth_ft, "pos": w.pos, "hp": list(w.hp), "clvl": w.clvl,
               "goal": self.goal.describe() if self.goal else None,
               "last_action": list(self.last_action) if self.last_action else None,
               "monsters": [(y, x, r.name) for y, x, r in w.monsters][:12],
               "standing_on": w.standing_on, "recent": recent}
        self.log("user_note", **{k: v for k, v in rec.items() if k != "t"})
        if text.startswith("!"):
            # a message for the Navigator: an attention event wakes its wait
            self.notify("user_message", text[1:].strip())
            self.unanswered.append((gnow(), text[1:].strip()))
        with open(os.path.join(self.rundir, "commentary.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
        return f"noted at {time.strftime('%H:%M:%S')} ({w.depth_ft} ft, HP {w.hp[0]}/{w.hp[1]}, " \
               f"goal {rec['goal']})"

    def monster_info(self, name):
        """This server's facts about a monster (monster.txt + the Advisor's
        danger table) and what the pilot makes of it now (post-mortem memo §5:
        the Navigator used Vanilla lore, which differs here)."""
        q = name.lower()
        found = [r for r in self.w.g.races.values() if q in r.name.lower()]
        if not found:
            return f"no monster matching '{name}'"
        exact = [r for r in found if r.name.lower() == q]
        out = []
        for r in (exact or found)[:6]:
            mx, drains = r.worst_melee
            why = self.danger_why(r)
            flags = sorted(f for f in r.flags if f in ("UNIQUE", "NEVER_MOVE", "MULTIPLY", "INVISIBLE",
                                                       "PASS_WALL", "KILL_WALL", "FRIENDS", "EMPTY_MIND"))
            # HP as a number: FORCE_MAXHP (all uniques) always has the maximum
            # (the Navigator told the user Wormtongue had ~137, the dice average;
            # he has 250 -- the Advisor's missions 15-16 replay)
            hn, _, hm = str(r.hp).partition("d")
            try:
                hp_txt = (f"{r.hp} = {int(hn) * int(hm)} (always the maximum)" if "FORCE_MAXHP" in r.flags
                          else f"{r.hp} (~{int(hn) * (int(hm) + 1) // 2} on average)") if hm else str(r.hp)
            except ValueError:
                hp_txt = str(r.hp)
            out.append(f"{r.name} ({r.char}): lvl {r.level} ({r.level * 50} ft), speed {r.speed - 110:+d}, "
                       f"HP {hp_txt}; blows {', '.join(r.blows) or 'none'}; "
                       f"spells 1 in {r.spell_freq}: {', '.join(sorted(r.spells))}" if r.spells else
                       f"{r.name} ({r.char}): lvl {r.level} ({r.level * 50} ft), speed {r.speed - 110:+d}, "
                       f"HP {hp_txt}; blows {', '.join(r.blows) or 'none'}; no spells")
            out[-1] += (f"; flags {', '.join(flags) or '-'}; max breath {r.max_breath}; "
                        f"melee per turn ~{r.per_turn:.0f} (worst {mx * (r.speed_x or 1):.0f}, drain blows {drains})"
                        f"; Advisor rating {r.danger if r.danger is not None else '?'}/5"
                        f"; for you now: {'DANGER: ' + why if why else 'no danger rule fires'}")
            # the rulebook (restructure step 3): the hunt check's verdict and what a kill drops
            refusal, est = self.hunt_refusal(r.name)
            out[-1] += f"; hunt check: {'REFUSED: ' + refusal if refusal else 'allowed (' + (est or '?') + ')'}"
            d = self.drop_row(r)
            if d:
                out[-1] += (f"; a kill drops ~{float(d['e_gold']):.0f} gold and ~{float(d['e_items']):.1f} items worth "
                            f"~{float(d['e_item_value_cap']):.0f} (P(ego) {float(d['p_excellent_any']):.0%}, "
                            f"P(artifact) {float(d['p_artifact_any']):.0%})")
        more = len(exact or found) - 6
        return "\n".join(out) + (f"\n(+{more} more)" if more > 0 else "")

    def uniques_killed(self):
        """Uniques this character has killed (runs/pilot/NICK/uniques_killed.json, kept by watch_kills;
        seeded from the logs): a repeat kill drops nothing and gives no XP."""
        if self._uk is None:
            try:
                self._uk = set(json.load(open(os.path.join(self.rundir, "uniques_killed.json"))))
            except (OSError, ValueError, AttributeError):
                self._uk = set()
        return self._uk

    def drop_row(self, race):
        """The rulebook's drops.csv row for a monster (at its native depth), or None."""
        if self._drops is None:
            try:
                self._drops = {r["idx"]: r for r in csv.DictReader(open(os.path.join(HERE, "..", "rulebook", "drops.csv")))}
            except OSError:
                self._drops = {}
        return self._drops.get(str(getattr(race, "idx", "")))

    # --- the per-monster asleep flag (the user, 10-26; the estimator's top data gap, memo 2026-10-25-replay) ---
    LOOK_EVERY = 5.0

    def look_tick(self, now):
        """Ask the server's targeting about the visible monsters (the client's `look N`: 'kill' mode cycles the
        monsters in line of sight, each described "A Warg (unhurt, asleep)"), when the set in view has changed, at
        most every LOOK_EVERY seconds; not with a monster adjacent or while resting. Then read the answers."""
        w = self.w
        self.read_looks()
        if not w.in_dungeon or not w.monsters or w.adjacent_monsters() or w.resting or \
                now - self.look_t < self.LOOK_EVERY:
            return
        key = (w.level_t, frozenset((y, x) for y, x, _ in w.monsters))
        if key == self.look_key:
            return
        self.look_key, self.look_t = key, now
        self.c.send(f"look {min(12, len(w.monsters))}")

    def read_looks(self):
        """The `target` answers since the last read -> self.asleep {(y, x): (t, name, asleep)}: by position when a
        visible monster stands there, else by name (the nearest of that name not yet placed)."""
        w = self.w
        new = [t for t in w.targets if t[0] > self.looks_read_t]
        if not new:
            return
        self.looks_read_t = new[-1][0]
        sl = self.asleep
        mons = {(y, x): r for y, x, r in w.monsters}
        placed = set()
        for t, y, x, text in new:
            m = re.match(r"(?:an?|the) (.+?) \(([^)]*)\)", text, re.I)
            if not m:
                continue
            name, cond = m.group(1), m.group(2)
            q = (y, x) if (y, x) in mons and mons[(y, x)].name.lower() == name.lower() else next(
                (p for p in sorted(mons, key=w.dist) if mons[p].name.lower() == name.lower() and p not in placed), None)
            if q:
                placed.add(q)
                sl[q] = (t, mons[q].name, "asleep" in cond)
        for q in [q for q in sl if q not in mons]:
            del sl[q]                  # (moved or gone: unknown again)
        # (for the first live checks: are the answers' screen positions the map's?)
        self.log("looks", n=len(new), placed=len(placed), by_pos=sum(1 for _, y, x, _ in new if (y, x) in mons),
                 asleep=sorted(f"{v[1]}@{q[0]},{q[1]}" for q, v in sl.items() if v[2])[:12],
                 sample=[(y, x, tx[:60]) for _, y, x, tx in new[:3]])

    def is_asleep(self, y, x):
        v = self.asleep.get((y, x))
        return v[2] if v and gnow() - v[0] < 60 else None

    def recall_started(self, now):
        """A Word of Recall is already under way: the server said so ("becomes
        charged", until the level changes or it's cancelled), or we read one in
        the last few seconds and the message hasn't arrived yet. Reading another
        would cancel it."""
        return self.w.recall_pending or now - self.recall_t < 5

    def set_goal(self, goal):
        old = self.goal
        if old is not None and old.overridden and old is not goal:
            self.settle_hunt(old, "replaced", goal.describe() if goal else "stopped")
        self.mover.stop()
        # (a goal set while handling the Navigator's or the Architect's request is theirs: goal_origin reads it)
        if goal is not None and goal.role is None and self.acting in ("nav", "arch"):
            goal.role = "navigator" if self.acting == "nav" else "architect"
        self.goal = goal
        self.goal_t = gnow()             # (watch_progress counts from here)
        self.idle_recalled = False
        self.log("goal", goal=goal.describe() if goal else None, by=self.acting)

    def step_goal(self):
        if not self.goal:
            return False
        if self.w.in_dungeon and (self.w.flag("blind") or self.w.flag("confused")) and \
                isinstance(self.goal, (Explore, Search, Dive)):
            # steps go astray and we can't see (mission 15 kept sending explore
            # moves into walls): wait it out (fights and cures still run)
            if self.mover.active:
                self.mover.stop()
            return True
        try:
            r = ("failed", self.goal.abort) if self.goal.abort else self.goal.tick(self)
        except Exception as e:           # a goal bug must not kill the pilot
            r = ("failed", f"error: {e!r}")
        if r:
            status, detail = r
            g = self.goal.describe()
            quiet = self.goal.quiet     # the Pilot's own small goals: news only
            self.goal_ending = self.goal
            self.goal = None
            self.mover.stop()
            if self.resume_after is not None:
                # An emergency interrupted this goal: carry on with it (the
                # Navigator had to re-send its climb after every stair hop)
                self.goal, self.resume_after = self.resume_after, None
                self.log("goal", goal=self.goal.describe(), why="resumed after recovering")
                self.news.append({"t": round(gnow(), 3), "what": "resumed",
                                  "detail": f"{g}: {detail}; resumed '{self.goal.describe()}'", "goal": None})
                return True
            ended = self.goal_ending
            if ended.overridden:
                self.settle_hunt(ended, status, detail)
            if isinstance(ended, WalkAway) and status == "failed":
                self.walkaway_failed.add(self.w.level_t)
                self.flee_t = 0.0             # (the danger flee may act at once)
            if isinstance(ended, Hunt) and status == "failed" and "blinked away" in str(detail) and self.w.in_dungeon:
                self.notify({"done": "goal_done", "failed": "goal_failed"}[status], f"{g}: {detail}", news=quiet)
                self.goal = Reprieve(ended.target)
                self.goal_t = gnow()
                if self.plan and self.plan.paused and ended is self.plan.pause_goal:
                    self.plan.pause_goal = self.goal      # (the plan waits for the reprieve too)
                self.log("goal", goal=self.goal.describe(), why="a blinker got away: rest is free (the user)")
                return True
            if self.plan:
                if ended.by_plan:
                    self.plan.goal_ended(self, ended, status, detail)
                    quiet = True
                elif self.plan.paused and ended is self.plan.pause_goal:
                    self.plan.paused = False
                    self.notify("plan", f"your goal ended ({g}: {detail}); the trip plan carries on")
            self.notify({"done": "goal_done", "failed": "goal_failed"}.get(status, status),
                        f"{g}: {detail}" if detail else g, news=quiet)
            if status == "failed" and g.startswith(("flee", "leave")):    # (m26's `goal leave` got stuck too)
                self.flee_failed(g)
        return True

    def idle(self):
        w = self.w
        if self.plan and not self.plan.paused:
            return                 # (the plan is the standing instruction; it has its own 90-minute cap)
        if w.in_dungeon and not self.idle_recalled and \
                gnow() - self.last_agent > self.orders["idle_recall_s"]:
            self.idle_recalled = True
            self.notify("idle_recall", "no word from the agent: recalling to town")
            self.set_goal(Recall())

    STAT_NAMES = ("STR", "INT", "WIS", "DEX", "CON", "CHR")

    def park_tick(self):
        """Parking: log out once it's safe (restarting mid-fight is dangerous)."""
        w = self.w
        near = [m for m in w.monsters if w.dist(m[:2]) <= 15]
        # (never during a pending recall: a logout reset its depth once, and
        # Dive03 landed at 1000 ft instead of the @R750 it had asked for)
        safe = not near and w.hp_frac >= 0.7 and not w.store and \
            not (w.last_stairs_cmd and gnow() - w.last_stairs_cmd[1] < 3) and \
            not self.recall_started(gnow()) and not isinstance(self.goal, Recall)
        if safe or gnow() - self.parking > 300:
            self.notify("parked", "logging out for a Pilot update; back in a minute -- "
                                  "re-issue your goal when you see 'started'"
                        + ("" if safe else " (parked after 5 min without a safe moment)"))
            self.c.send("clear")      # empty our server-side command queue first
            with self.att_cond:
                self.att_cond.wait(1.5)   # let a waiting Navigator collect the event
            self.running = False

    def tick(self):
        """One pass of the main loop (docs/pilot-core.md, "The tick loop"): perceive, cure confusion, keep the books,
        watch, answer requests, then act. Each step is a method; one returning true ends the tick."""
        self.w.drain()
        self.w.refresh()
        self.note_edge_cross()
        if self.confusion_tick():
            return
        self.supply_watch()
        self.clock_tick()
        self.note_town_stairs()
        if self.wear_queue:
            self.wear_step()
        self.verify_use()
        self.verify_effects()
        self.learn_flavours_tick(gnow())
        self.track_since()
        now = gnow()
        self.track_hp_min()
        self.watch_floor()
        self.resync_tick(now)
        self.watch_items(now)
        self.audit_tick(now)
        self.structures_tick(now)
        self.avoid_tick()
        self.trail_tick()
        self.mons_tick(now)
        self.belief_tick(now)
        self.watch_tick(now)
        self.handle_requests()
        if not self.running:
            return
        if self.freeze_tick():
            return
        self.act_tick(now)

    def confusion_tick(self):
        """Confusion: a cure while confused with a goal waiting or monsters adjacent (`confusion_lock`), a teleport
        just after a cure among a crowd (`confusion_window`). True: it acted, the tick ends."""
        # (the M5 set-piece, 10-28: confused 40 s among 26 Hummerhorns with no goal, and nothing happened -- the check
        # lived in step_goal, which returns at once without a goal)
        if not self.w.flag("confused"):
            self.conf_since = None        # (m60: "confused for 1773 s" -- the clock ran on between confusions)
        elif self.w.in_dungeon and (self.w.adjacent_monsters() or self.goal) and self.confusion_lock():
            return True
        if self.confusion_window():
            return True
        return False

    def clock_tick(self):
        """The game clock's time factor: the model's factor, the fuel-measured speed-up allowed or not, the
        `time_factor` log, and a redraw for fuel readings."""
        # the game clock (world.py). The server's rule (xtra2.c base_time_factor, time_factor): 1 in town;
        # 10x resting and 5x running with no awake monster in line of sight -- seen or not
        # (monsters_in_los), so after a fight in the dark it's often 1x (set-piece L2: a 6-s rest at 1x);
        # else 1/5 at or below hitpoint_warn x 10% HP. The model takes the 1/5 (exact, and what matters in
        # a fight) and 1x for resting and running: a clock running fast where the game doesn't would end
        # game timers early (a recall "overdue" and read again cancels it). Only the fuel's measured rate
        # raises it, while resting or running with nothing in view.
        hw = self.hpwarn
        w, m = self.w, self.mover
        hp = w.hp
        slow = hw and hp[1] > 1 and hp[0] * 100 // max(1, hp[1]) <= hw * 10
        # (running: a run under way and the position changing -- the mover's run state also covers the
        # wait for the first step and the stop, and the fuel measured 2-4x over it, not 5x)
        running = (m.running is not None or m.free is not None) and wall_since(w.pos_t) < 0.4
        fast_ok = bool(w.in_dungeon and (w.resting or running) and not w.monsters)
        # (hurt and resting out of sight: 10x or, with an unseen monster awake in sight, 1/5: the lower)
        model = 1.0 if not w.in_dungeon else 0.2 if slow else 1.0
        set_fast_ok(fast_ok)
        if model != model_factor():
            set_time_factor(model)
        # (logged on a new measurement, or a change of the model's factor at most every 5 s: runs
        # start and stop every second or two)
        f, r = time_factor(), measured_rate()
        if r != self.rate_logged or (abs(f - self.factor_logged) > 0.3 * max(f, self.factor_logged)
                                     and wall_since(self.factor_log_t) > 5):
            self.factor_logged, self.rate_logged, self.factor_log_t = f, r, gnow()
            self.log("time_factor", factor=round(f, 2), hp=hp[:2], model=model, measured=r and round(r, 2))
        # fuel readings (a redraw: free, and the server resends the pack): every 2 s while the clock may
        # run fast, every 10 s otherwise (to check the model's 1.0 in the log)
        if self.w.in_dungeon and light_fuel(self.w.inven) is not None and \
                wall_since(self.redraw_t) > (2 if fast_ok else 10):
            self.w.need_redraw = True

    def track_hp_min(self):
        """The lowest HP since the last report, and an overridden goal's lowest HP."""
        w = self.w
        if w.hp[1] > 1 and (self.hp_min_since is None or w.hp[0] < self.hp_min_since[0]):
            self.hp_min_since = [w.hp[0], w.hp[1]]
        ov = getattr(self.goal, "overridden", None) or getattr(self.resume_after, "overridden", None)
        if ov and w.hp[0] < ov["hp_min"]:
            ov["hp_min"] = w.hp[0]

    def watch_floor(self):
        """Floor items seen (`itemlist`) and what a level was left with (`left_behind`)."""
        w = self.w
        # 2. floor items with full names, and what a level was left with (the
        # Advisor's scorecard memo §5.2: abandoned loot had to be reconstructed)
        names = [l.strip()[2:].strip() for l in (w.itemlist or [])[1:]]
        if w.level_t != self.items_level:
            if self.items_level is not None and self.items_last and self.items_depth:
                self.log("left_behind", items=self.items_last, left_depth_ft=self.items_depth)
            self.items_level, self.items_last, self.items_depth = w.level_t, [], w.depth_ft
        if names != self.items_last and w.in_dungeon:
            self.items_last = names
            self.log("itemlist", items=names, depth_ft=w.depth_ft)

    def resync_tick(self, now):
        """A full `redraw` from the server after a level change or a loss -- never in or near a store."""
        w = self.w
        # Full resync from the server after a level change or a loss (the
        # game-state survey, 2026-10-03: the client's copy is right, ours drifts)
        # Never inside a store, nor during a shop goal: the server's redraw
        # silently closes the store (net-game.c recv_redraw sets store_num = -1,
        # no store_leave), and a purchase after that reads store[-1] -- it
        # crashed the test server in mission 21 and would crash a live one
        shopping = w.store is not None or isinstance(self.goal, Shop) or now - getattr(w, "store_t", 0) < 3
        if (w.need_redraw or self.redraw_level != w.level_t) and wall_since(self.redraw_t) > 2 and not shopping:
            self.redraw_t, self.redraw_level = now, w.level_t
            w.need_redraw = False
            self.c.send("redraw")
            w.inven_dirty = True
            w.status_t = 0

    def watch_items(self, now):
        """Item news: `found` (a special item picked up), `interesting_item` (a device or jewellery seen on the
        level, held 2.5 s), `lost` (stolen or destroyed)."""
        w = self.w
        for ts, t in w.messages:
            if ts > self.found_t:
                m = re.match(r"You have (.+) \([a-w]\)\.$", t)
                if m and (self.probably_special(m.group(1)) or re.search(r"\{(good|excellent|special|magical)",
                                                                       m.group(1))):
                    # (mission 14: Farmer Maggot's Lance came into the pack unannounced; it sold for 391)
                    self.notify("found", f"picked up {m.group(1)}: identify it before selling (`sell !NAME`)",
                                news=True)
        self.found_t = now
        if w.in_dungeon and w.itemlist:
            for line in w.itemlist[1:]:
                name = line.strip()[2:].strip()
                if re.search(r"\b(Wand|Staff|Rod|Ring|Amulet)\b|\{(excellent|special)", name) and \
                        not self.is_junk(name) and (w.level_t, name) not in self.far_seen:
                    self.far_seen.add((w.level_t, name))
                    # (mission 15: the user spotted a Wand of Slow Monster 33 squares
                    # away, outside loot_radius; it sold for 210). Held 2.5 s: often
                    # the pilot is already stepping onto it (mission 18's amulet was in
                    # the pack before the Navigator could look)
                    self.item_pending.append((now + 2.5, w.level_t, name, line.strip()[:1], now))
        for pend in list(self.item_pending):
            due, lt, name, glyph, first = pend
            if now < due:
                continue
            self.item_pending.remove(pend)
            bare = re.sub(r"^(an?|the|\d+) ", "", name.lower())
            if lt != w.level_t or any(bare in i["name"].lower() for i in w.items() + w.items(equip=True)):
                continue
            # one like it within loot_radius: the pilot fetches it itself; wait
            # up to 10 s (mission 20's Quartz Ring came in 4 s after the alert)
            lr = int(self.orders.get("loot_radius", 0))
            if lr and now - first < 10 and self.orders.get("pickup") == "all" and \
                    any(ch == glyph and w.dist(q) <= lr for q, ch in w.memory.items()):
                self.item_pending.append((now + 1.5, lt, name, glyph, first))
                continue
            # (the squares in the notice itself: m27's Navigator needed a `status full` for each fetch)
            sq = sorted((q for q, ch in w.memory.items() if ch == glyph), key=w.dist)[:3]
            where = ", ".join(f"{q[0]},{q[1]} ({w.dist(q)} away)" for q in sq) or "see 'Item squares' in `status full`"
            # devices and jewellery this close: the loot step fetches them once it's clear (m29: nobody did)
            if lr and self.orders.get("pickup") == "all" and glyph in self.VALUABLE_GLYPHS and sq and \
                    w.dist(sq[0]) <= self.LOOT_VALUABLE_R:
                self.notify("interesting_item", f"{name} seen on this level at {where}: fetching it once the "
                                                 "area is clear", news=True)
                continue
            if not self.plan:
                self.item_hold_until = now + 20   # (a dive pauses so you can fetch it)
            self.notify("interesting_item", f"{name} seen on this level (devices and jewellery sell for 50-700 once "
                                             f"known): a '{glyph}' at {where}; `goal fetch Y,X`"
                                             + ("" if self.plan else ". A dive pauses 20 s for it"))
        while w.losses:
            t, text = w.losses.pop(0)
            self.notify("lost", text, news=True)

    def avoid_tick(self):
        """The avoid zones -> `World.avoid_zone` / `avoid_inside`: the Navigator's zones on this level and 3 squares
        round a monster with an avoided name."""
        w = self.w
        # the Navigator's avoid zones, as squares the planner won't enter
        zone = set()
        for y0, x0, r in self.avoid_zones.get(w.level_t, []):
            zone |= {(y0 + dy, x0 + dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1)}
        for y0, x0, rc in w.monsters:
            if any(n in rc.name.lower() for n in self.avoid_names):
                zone |= {(y0 + dy, x0 + dx) for dy in range(-3, 4) for dx in range(-3, 4)}
        w.avoid_inside = w.pos in zone
        w.avoid_zone = zone - {w.pos}

    def trail_tick(self):
        """On a new level: `deepest.json`, and the wilderness trail (the edge we came in by, per sector)."""
        w = self.w
        # The wilderness trail: the edge we came in by, per sector (Town goal)
        if self.trail_level != w.level_t and w.arrive_pos is not None:
            self.trail_level = w.level_t
            if w.in_dungeon and (w.depth_ft or 0) > self.deepest_ft:
                self.deepest_ft = w.depth_ft
                try:
                    with open(self.deepest_file, "w") as f:
                        json.dump({"ft": self.deepest_ft}, f)
                except OSError:
                    pass
            if w.depth == 0 or w.in_dungeon:
                self.wild_trail = []
            elif isinstance(self.goal, Town) and self.wild_trail:
                self.wild_trail.pop()             # retracing: one sector closer
            elif edge_of(w.arrive_pos):
                self.wild_trail.append(edge_of(w.arrive_pos))
                # (not for the bank's own trip to the house tile: m57 read it as the Pilot wandering off)
                banking = isinstance(self.goal, HouseBank) or isinstance(getattr(self.goal, "sub", None), HouseBank)
                if len(self.wild_trail) == 1 and not banking:
                    self.notify("left_town", f"walked off the town map into the wilderness ({w.depth_ft} ft); "
                                             "'goal town' walks back")

    def mons_tick(self, now):
        """The `mons` record: the monsters in view, once a second at most."""
        w = self.w
        if w.in_dungeon and w.monsters and now - self.mons_log_t >= 1.0:
            # a steady record for replays (post-mortem memo §4.6: an 86 s gap
            # before the mission-7 death)
            self.mons_log_t = now
            # + the server's health bar of the tracked monster (indicator "track":
            # colour, length in tenths; xtra1.c health_redraw) and the monster we
            # last hit, which is usually the tracked one (the Advisor, 10-09: no
            # monster HP in the logs, so nobody could tell how close Brodda was)
            hit = next((m.group(1) for ts, t in reversed(w.messages) if now - ts < 5
                        for m in [re.match(r"You (?:hit|smite|bite|claw|miss) (?:the )?(.+?)[.!]$", t)] if m), None)
            self.log("mons", monsters=[(y, x, r.name) for y, x, r in w.monsters],
                     track=w.ind.get("track"), fighting=hit)

    def watch_tick(self, now):
        """The watchers: they notify and log, and don't act (except `watch_progress`'s clear/abort)."""
        self.watch_character()
        if now - self.weapons_t > 10:
            self.weapons_t = now
            self.watch_weapons()
        self.watch_breeders()
        self.watch_drainers()
        self.watch_thieves()
        self.watch_kills()
        self.watch_band()
        self.watch_traps()
        self.watch_abilities()
        self.watch_progress()
        self.watch_perception()
        if self.w.recall_cancelled:
            self.w.recall_cancelled = False
            self.notify("recall_cancelled", "a Word of Recall was cancelled (a second one was read): no recall is pending now")
        self.recall_memory()
        self.shadow_results()

    def freeze_tick(self):
        """The test server's time freeze. True while frozen: the tick acts on nothing."""
        # The test server's time freeze: nothing happens in the game, so act on nothing (commands sent now would
        # queue and run on stale reasons when it thaws); requests are still answered
        if frozen():
            if not self.frozen_said:
                self.frozen_said = True
                self.mover.stop()
                self.notify("time_frozen", "time is frozen on the test server: the Pilot holds until it's thawed")
            return True
        if self.frozen_said:
            self.frozen_said = False
            self.notify("time_frozen", "time flows again: the Pilot carries on", news=True)
        return False

    def act_tick(self, now):
        """The acting layers, first that acts wins: reflexes, parking, the Navigator's `react` rules, look (never
        acts), the Pilot's item policy, the goal, the trip plan, idle."""
        # who each action is for (the user, 10-25: "when does the Navigator act vs the Pilot?"): stamped as `by` on
        # every act and goal record and shown in the viewer -- pilot (reflexes, policy, idle), plan (the Navigator's
        # plan town / plan trip, run by the Pilot), nav (a goal the Navigator gave directly), arch (the Architect)
        self.acting = "pilot"
        if self.reflexes():
            return
        if self.parking and not isinstance(self.goal, Recall):
            self.park_tick()
            return
        if self.rule_tick(gnow()):        # the Navigator's executable standing orders (`react`)
            return
        self.look_tick(gnow())            # (never acts: asks the server which monsters are asleep)
        if self.policy_tick(gnow()):      # the Pilot's own item work, at safe moments
            return
        self.acting = self.goal_origin(self.goal)
        if self.step_goal():
            self.acting = "plan"
            self.plan_tick(now, False)
            return
        self.acting = "plan"
        if self.plan_tick(now, True):
            return
        self.acting = "pilot"
        self.idle()

    def goal_origin(self, g):
        """Who a goal acts for: the plan's goals and the Navigator's plan town -> plan; another goal the Navigator or
        the Architect gave -> nav / arch; the Pilot's own (flee, recover, recall by reflex...) -> pilot."""
        if g is None:
            return "pilot"
        if g.by_plan or isinstance(g, TownKit):
            return "plan"
        role = g.role
        return {"navigator": "nav", "architect": "arch"}.get(role, "pilot")

    # --- control requests (from the socket thread) ---------------------------

    READ_ONLY_CMDS = ("viewmap", "view", "navview", "goalstate")

    def authenticate(self, req):
        """A request claiming the architect role without the Architect's token is the Navigator's (F3); refused
        claims other than the viewer's read-only queries are logged and raised as an attention event."""
        if req.get("role") != "architect" or req.get("token") == self.arch_token:
            return req
        req = dict(req, role="navigator")
        if req.get("cmd") not in self.READ_ONLY_CMDS:
            self.log("role_refused", cmd=req.get("cmd"), args=req.get("args", [])[:6])
            self.notify("role_refused", f"`{req.get('cmd')}` claimed the Architect's role without its token: run as "
                                        "the Navigator's (set nothing in the environment; only the Architect "
                                        "and the harness use that role)")
        return req

    def handle_requests(self):
        while True:
            try:
                req, reply = self.requests.get_nowait()
            except queue.Empty:
                return
            req = self.authenticate(req)
            if req.get("cmd") not in ("viewmap", "view", "navview", "note", "goalstate", "mission"):
                # (only the Navigator's own commands count as activity: the viewer's
                # twice-a-second polls kept town_light from ever taking the lantern
                # off, and idling in town burned 7300 turns + 3 flasks, 2026-10-16)
                self.last_agent = gnow()
                # the Navigator's commands as received (latency studies could only
                # see the next recorded order: the Advisor)
                rid, rt = self.last_report
                self.log("nav_cmd", cmd=req.get("cmd"), args=req.get("args", [])[:12], role=req.get("role", "navigator"),
                         wait_report=bool(req.get("since_wait")), after_report=rid,
                         report_age=round(gnow() - rt, 1) if rt else None)
            self.acting = "arch" if req.get("role") == "architect" else "nav"
            try:
                out = self.do_request(req)
            except Exception as e:
                out = {"ok": False, "error": repr(e)}
            self.acting = "pilot"
            if self.unanswered and isinstance(out, dict) and req.get("cmd") not in ("note", "say", "status"):
                # on every answer, not only wait/status (mission 16: 'Pause 1 sec'
                # was seen 35 s late, during chest commands)
                out["user_messages"] = [f"{time.strftime('%H:%M:%S', _lt(t))} {m}"
                                        for t, m in self.unanswered]
            reply.put(out)

    def service_notes(self):
        """Take the user's notes out of the request queue now, from inside a
        long agent command (search 20, chest work, pack re-reads): they queued
        behind it. True if one came in."""
        with self.requests.mutex:
            notes = [r for r in self.requests.queue if r[0].get("cmd") == "note"]
            for r in notes:
                self.requests.queue.remove(r)
        for req, reply in notes:
            try:
                out = self.do_request(req)
            except Exception as e:
                out = {"ok": False, "error": repr(e)}
            reply.put(out)
        return bool(notes)

    ACTIONS = {"wear": "w", "takeoff": "t", "quaff": "q", "read": "r", "eat": "E", "fuel": "F",
               "destroy": "k", "drop": "d", "inspect": "I", "aim": "a", "use": "u", "zap": "z"}

    def item_index(self, letter, equip=False, pack_only=False):
        """Inventory letter (a, b, ...) as in the report, or part of an item's
        name (spaces as '_'; resolved now, so it can't go stale) -> item index."""
        if len(letter) == 1 and letter.isalpha():
            # Equipment letters: A, B, ... in the order `equip` lists it (and
            # lowercase for takeoff, which only works on equipment); mission 22
            # couldn't take off or inspect a worn ring by letter
            if letter.isupper() or (equip and pack_only is False and self.equip_letters_lower):
                eq = self.w.items(equip=True)
                k = ord(letter.lower()) - ord("a")
                if not 0 <= k < len(eq):
                    raise ValueError(f"no equipment item {letter} (`equip` lists them)")
                return eq[k]["item"]
            return ord(letter) - ord("a")
        if letter.isdigit():
            return int(letter)
        name = letter.replace("_", " ").lower()
        pool = self.w.items() if pack_only else \
            self.w.items(equip=True) + self.w.items() if equip else self.w.items() + self.w.items(equip=True)
        hits = [i for i in pool if name in i["name"].lower()]
        if not hits:
            # "Flask of oil" for "4 Flasks of oil" (mission 17)
            hits = [i for i in pool if singular(name) in singular(i["name"])]
        if not hits:
            raise ValueError(f"nothing in the pack matches '{letter}'" if pack_only else f"no item matching '{letter}'")
        if len(hits) > 1:
            # whole-word matches first ("Light" = the Scroll of Light, not Cure
            # Light Wounds: mission 16 destroyed 14 CLW that way)
            words = [i for i in hits if re.search(r"\b" + re.escape(name) + r"\b", i["name"].lower())
                     and not re.search(r"\w " + re.escape(name) + r" \w", i["name"].lower())]
            if len(words) == 1:
                return words[0]["item"]
            # two stacks of the same unknown kind (they don't merge while their
            # hidden pluses differ: mission 22's two Bloodstone Rings): the first
            same = {re.sub(r"^(an?|\d+) ", "", i["name"]) for i in hits}
            if len(same) == 1:
                return hits[0]["item"]
            raise ValueError(f"'{letter}' matches {len(hits)} items: " + "; ".join(
                f"{chr(97 + i['item'])}) {i['name']}" for i in hits) + ": use the letter or a longer name")
        return hits[0]["item"]

    def pack_now(self, wait=0.7):
        """Re-read the pack right after an action (the report lagged behind a
        batch of destroys, and the Navigator then acted on stale letters)."""
        self.c.collect(wait)
        self.service_notes()
        self.w.drain()
        self.w.inven = self.c.inven()
        self.w.inven_t = gnow()
        self.w.inven_dirty = False
        return [f"{chr(97 + i['item'])}) {i['name']}" for i in self.w.items()]

    # In the dungeon the Pilot handles items itself (restructure step 2, the user's
    # hybrid: item commands for the Navigator in town only, between trips)
    # (destroy and drop are allowed in the dungeon since 10-26 -- dungeon pack control, the user: the pack fills ~10
    # minutes into a trip; the value refusals and the debt rules apply as in town)
    DUNGEON_ITEM_CMDS = {"wear", "takeoff", "pickup", "fuel", "eat", "inscribe", "wearall"}

    def do_request(self, req):
        c = req.get("cmd")
        args = req.get("args", [])
        self.req_role = req.get("role", "navigator")
        if self.req_role != "architect" and self.w.in_dungeon and (
                c in self.DUNGEON_ITEM_CMDS or
                (c in ("read", "use") and len(args) > 1 and args[1] != "force")):      # identify-type reads
            return {"ok": False, "error": f"in the dungeon the Pilot handles items itself (pickup, identify, "
                                          f"wear upgrades, fuel, eat): `{c}` is for town, between trips. You may "
                                          "`destroy`/`drop` junk, and `order nopickup=NAME,...` keeps kinds out. To "
                                          "protect an item from its policy use `keep NAME`"}
        if self.req_role != "architect" and (c in ("raw", "stairs") or (c == "goal" and args[:1] == ["goto"])):
            # the new toolset (restructure step 2.6): movement is the Pilot's; the Navigator
            # gives intents (`goal leave` for the stairs, `goal fetch Y,X` for an item)
            return {"ok": False, "error": f"`{c}{' goto' if c == 'goal' else ''}` is the Pilot's now: use `goal leave` "
                                          "(this level, by the nearest stairs), `goal fetch Y,X` (one item), "
                                          "`plan trip ...` or `goal dive FEET`"}
        if self.req_role != "architect":
            held = self.stale_order(c, args)
            if held:
                self.log("order_held", cmd=c, args=args[:6], why=held)
                return {"ok": False, "error": f"order held: {held}"}
        if c == "status":
            full = "full" in args
            if req.get("since_wait"):
                # a wait report: the news since the previous wait (the survey)
                since, self.news_wait_t = self.news_wait_t, gnow()
                rep = self.numbered(self.compact(news_since=since), "wait")
                self.nav_view = (time.time(), self.nav_view_events, rep)
                return {"ok": True, "report": rep}
            rep = self.numbered(self.report() if full else self.compact(snapshot=True), "full" if full else "status")
            self.nav_view = (time.time(), [], rep)
            return {"ok": True, "report": rep}
        if c == "mission":
            if self.req_role != "architect":
                return {"ok": False, "error": "mission markers are the Architect's (refactor-candidates F4)"}
            # mission_start / mission_end markers with the Navigator's model (the
            # Advisor's scorecard memo §5.5); also kept in runs/missions.json
            if not args or args[0] not in ("start", "end"):
                return {"ok": False, "error": "usage: mission start LABEL [navigator=MODEL] [effort=LEVEL] [notes=TEXT] | "
                                              "mission end [LABEL]"}
            kv = dict(a.split("=", 1) for a in args[1:] if "=" in a)
            label = next((a for a in args[1:] if "=" not in a), None) or self.mission_label
            if not label:
                return {"ok": False, "error": "which mission? (mission start LABEL ...)"}
            path = os.path.join(os.path.dirname(os.path.dirname(self.rundir.rstrip("/"))), "missions.json")
            try:
                ms = json.load(open(path))
            except (OSError, ValueError):
                ms = []
            nick = os.path.basename(self.rundir.rstrip("/"))
            stamp = time.strftime("%Y-%m-%d %H:%M")
            if args[0] == "start":
                self.mission_label = label
                # (the report's mission total: m25's Navigator had only the 10-minute rates)
                self.mission_base = (gnow(), (self.w.ind.get("exp") or [0])[0], self.w.ind.get("gold", [0])[0],
                                     self.gold_found)
                self.save_mission()
                self.log("mission_start", label=label, version=VERSION, **kv)
                ms = [m for m in ms if m.get("label") != label] + [
                    {"label": label, "nick": nick, "start": stamp, "end": None, "navigator": kv.get("navigator"),
                     "effort": kv.get("effort"), "report": "compact", "notes": kv.get("notes", ""),
                     "version": VERSION}]
            else:
                self.log("mission_end", label=label, **kv)
                for m in ms:
                    if m.get("label") == label:
                        m["end"] = time.strftime("%Y-%m-%d %H:%M", _lt(gnow() + 59))
                self.mission_label = None
                try:
                    os.remove(os.path.join(self.rundir, "mission.json"))
                except OSError:
                    pass
            with open(path, "w") as f:
                json.dump(ms, f, indent=1)
            return {"ok": True, "text": f"mission {args[0]}: {label} at {stamp}"}
        if c == "keep":
            # protect an item from the value policy and from the Navigator's own
            # sells/destroys (`keep -NAME` releases; `keep` lists)
            if not args:
                return {"ok": True, "text": "kept: " + (", ".join(sorted(self.keep)) or "nothing")}
            name = " ".join(args).replace("_", " ").lower()
            if name.startswith("-"):
                self.keep.discard(name[1:].strip())
            else:
                self.keep.add(name.strip())
            json.dump(sorted(self.keep), open(os.path.join(self.rundir, "keep.json"), "w"))
            return {"ok": True, "text": "kept: " + (", ".join(sorted(self.keep)) or "nothing")}
        if c == "standing":
            # standing instructions shown in every report (the Advisor's belief-state table:
            # "don't kill the Rot jelly"); `standing -N` removes one, `standing` lists them
            if args and re.fullmatch(r"-\d+", args[0]):
                i = int(args[0][1:]) - 1
                if not 0 <= i < len(self.standing):
                    return {"ok": False, "error": f"no standing instruction {i + 1}"}
                gone = self.standing.pop(i)
            elif args:
                self.standing.append({"text": " ".join(args), "by": self.req_role,
                                      "t": time.strftime("%Y-%m-%d %H:%M")})
            json.dump(self.standing, open(os.path.join(self.rundir, "standing.json"), "w"), indent=1)
            return {"ok": True, "text": "standing: " + ("; ".join(f"{i + 1}. {x['text']} ({x['by']})"
                                                                for i, x in enumerate(self.standing)) or "none")}
        if c == "react":
            # executable standing orders (the user, 10-26): `react KIND ARG`, `react -N`, `react clear`, `react`
            # (not `rule`: pilotctl answers that one itself, the Advisor's rulebook)
            rl = self.rules()
            if args and args[0] == "clear":
                rl.clear()
            elif args and re.fullmatch(r"-\d+", args[0]):
                i = int(args[0][1:]) - 1
                if not 0 <= i < len(rl):
                    return {"ok": False, "error": f"no reaction {i + 1}"}
                rl.pop(i)
            elif args:
                kind, arg = args[0], " ".join(args[1:]).replace("_", " ").lower().strip()
                if kind not in self.RULE_KINDS or not arg:
                    return {"ok": False, "error": "usage: react leave NAME | react hunt NAME | react thieves kill | "
                                                  "react afraid teleport | react -N | react clear. " +
                                                  "; ".join(f"{k}: {v}" for k, v in self.RULE_KINDS.items())}
                if kind in ("leave", "hunt") and not any(r.name.lower() == arg for r in self.w.g.races.values()):
                    return {"ok": False, "error": f"no monster named {arg!r} (use the name `monster` shows)"}
                if (kind, arg) in {("thieves", "kill"), ("afraid", "teleport")} or kind in ("leave", "hunt"):
                    # (m58: `react thieves kill` listed three times -- the same reaction isn't added twice)
                    if not any(r["kind"] == kind and r["arg"] == arg for r in rl):
                        rl.append({"kind": kind, "arg": arg, "by": self.req_role, "t": time.strftime("%Y-%m-%d %H:%M")})
                else:
                    return {"ok": False, "error": f"react {kind} takes: " + self.RULE_KINDS[kind]}
            self.save_rules()
            return {"ok": True, "text": "reactions: " + ("; ".join(f"{i + 1}. {r['kind']} {r['arg']} ({r['by']})"
                                                               for i, r in enumerate(rl)) or "none")}
        if c == "review":
            # the item-review queue (the user, 10-26): items held for the Navigator's word before they're sold
            st = self.review_state()
            if not args:
                return {"ok": True, "text": "review: " + ("; ".join(f"{n} ({v['why']})" for n, v in st["items"].items())
                                                          or "nothing held")}
            if args[0] not in ("sell", "keep", "wear") or len(args) < 2:
                return {"ok": False, "error": "usage: review | review sell|keep|wear NAME"}
            frag = " ".join(args[1:]).replace("_", " ").lower()
            name = next((n for n in st["items"] if frag in n.lower()), None)
            if not name:
                return {"ok": False, "error": f"nothing held matches {frag!r}: " + ", ".join(st["items"])}
            st["items"].pop(name)
            st["decided"][name] = "sell" if args[0] == "sell" else "keep"
            self.review_save()
            if args[0] == "keep":
                self.keep.add(bare_name(name).lower())
                json.dump(sorted(self.keep), open(os.path.join(self.rundir, "keep.json"), "w"))
            if args[0] == "wear":
                # (recorded as keep; worn now only in town -- `wear` is for town, between trips: DUNGEON_ITEM_CMDS. It
                # said "-> wear" and in the dungeon wore nothing: refactor-candidates A11)
                it = next((i for i in self.w.items() if i["name"] == name), None)
                if self.w.in_dungeon:
                    return {"ok": True, "text": f"review: {name} -> kept, NOT worn: in the dungeon the Pilot handles "
                                                f"items itself. `wear` it in town, between trips"}
                if not it:
                    return {"ok": True, "text": f"review: {name} -> kept, NOT worn: it isn't in the pack"}
                self.cmd(f"custom w item={it['item']}", f"wear {name} (your review)", hold=0.8)
                return {"ok": True, "text": f"review: {name} -> kept; wearing it now"}
            return {"ok": True, "text": f"review: {name} -> {args[0]}"}
        if c == "debt":
            e = self.debt.get("entries", [])
            fe = self.debt.get("fight_entries", [])
            return {"ok": True, "text": f"Navigator debt: {self.debt_total()} gold of value lost over the Pilot's value "
                                        f"policy ({len(e)} entries)" + "".join(f"\n  {x['t']} {x['gold']}: {x['what']} "
                                                                                f"({x['why']})" for x in e[-8:]) +
                                        f"\nFight debt: {self.fight_debt_total()} HP lost in hunts ordered over the "
                                        f"Pilot's refusal that went wrong ({len(fe)} entries)" +
                                        "".join(f"\n  {x['t']} {x['hp']} HP: {x['what']} ({x['why']})" for x in fe[-8:])}
        if c == "pack":
            return {"ok": True, "text": "Pack: " + "; ".join(f"{chr(97 + i['item'])}) {self.short(self.show(i))}"
                                                           for i in self.w.items())}
        if c == "equip":
            return {"ok": True, "text": "Equipment (use these letters, capitals, in item commands): " + "; ".join(
                f"{chr(65 + k)}) {self.short(i['name'])}" for k, i in enumerate(self.w.items(equip=True)))
                    + "\n" + self.gear_line()}
        if c == "orders":
            return {"ok": True, "text": "Orders: " + ", ".join(f"{k}={v}" for k, v in self.orders.items())}
        if c == "map":
            w = self.w
            r = int(args[0]) if args and args[0].isdigit() else 15
            if not (w.rows and w.pos):
                return {"ok": False, "error": "no map yet"}
            y0, x0 = w.pos
            ys = range(max(0, y0 - r), min(len(w.rows), y0 + r + 1))
            xa = max(0, x0 - r)
            return {"ok": True, "text": f"Map (@ {y0},{x0}; rows {ys[0]}-{ys[-1]}, cols {xa}-{x0 + r}):\n"
                    + "\n".join(f"{y:2d}|" + w.rows[y][xa:x0 + r + 1].rstrip() for y in ys)}
        if c == "view":
            # (the observer's viewer: a bigger map, no side effects)
            rows = int(args[0]) if args else 11
            cols = int(args[1]) if len(args) > 1 else 33
            return {"ok": True, "report": self.report(rows=rows, cols=cols, news_since=gnow() - 600)}
        if c == "navview":
            # what the Navigator last saw (the user's "Navigator's view" panel)
            return {"ok": True, "t": self.nav_view[0], "events": self.nav_view[1], "report": self.nav_view[2]}
        if c == "avoid":
            # the Navigator's no-go zones (the user, mission 16): 'avoid Y,X [R]'
            # (this level), 'avoid NAME' (keep 3 squares from that monster, all
            # levels), 'avoid clear', 'avoid' to list
            w = self.w
            if args[:1] == ["clear"]:
                self.avoid_zones, self.avoid_names = {}, set()
                return {"ok": True, "text": "avoid zones cleared"}
            if args:
                m = re.match(r"^(\d+)[ ,](\d+)$", args[0])
                if m:
                    r = int(args[1]) if len(args) > 1 else 3
                    self.avoid_zones.setdefault(w.level_t, []).append((int(m.group(1)), int(m.group(2)), r))
                else:
                    self.avoid_names.add(" ".join(args).replace("_", " ").lower())
            here = self.avoid_zones.get(w.level_t, [])
            return {"ok": True, "text": "avoiding: " + "; ".join([f"{y},{x} r{r}" for y, x, r in here]
                                                                 + sorted(self.avoid_names)) if here or self.avoid_names
                    else "no avoid zones"}
        if c == "viewmap":
            # (the observer's colour map: chars + attrs around @; monsters with
            # their monster.txt colour, since our glyph table recodes them)
            w = self.w
            rows_n = int(args[0]) if args else 11
            cols_n = int(args[1]) if len(args) > 1 else 33
            if not w.rows or not w.pos:
                return {"ok": True, "rows": [], "attrs": []}
            y0, x0 = max(0, w.pos[0] - rows_n), max(0, w.pos[1] - cols_n)
            y1, x1 = min(len(w.rows), w.pos[0] + rows_n + 1), w.pos[1] + cols_n + 1
            return {"ok": True, "y0": y0, "x0": x0, "pos": w.pos,
                    "rows": [r[x0:x1] for r in w.rows[y0:y1]],
                    "attrs": [a[x0:x1] for a in w.attrs[y0:y1]] if w.attrs else [],
                    "mons": [[y, x, r.color] for y, x, r in w.monsters]}
        if c == "note":
            return {"ok": True, "text": self.user_note(" ".join(args))}
        if c == "journal":
            # the Navigator's journal line, stamped with the real time, depth
            # and HP (its own times were guesses), appended to navigator.md and
            # logged here, so the viewer and notes.py show it in sequence
            w = self.w
            where = "town" if not w.depth else f"{w.depth_ft}ft"
            line = f"- {time.strftime('%H:%M:%S')} {where} {round(100 * w.hp_frac)}% | " + " ".join(args)
            with open(os.path.join(self.rundir, "navigator.md"), "a") as f:
                f.write(line + "\n")
            self.log("nav_journal", text=line[2:])
            return {"ok": True, "text": "journaled: " + line[2:]}
        if c == "gate":
            # the supply gate as a check: 'gate FEET [recall]'
            try:
                ft = int(args[0])
            except (IndexError, ValueError):
                return {"ok": False, "error": "usage: gate FEET [recall]"}
            gap = self.supply_gate(ft, "recall" in args[1:])
            return {"ok": True, "text": f"supplies for {ft} ft: " + ("OK" if not gap else "missing " + "; ".join(gap))}
        if c == "complain":
            # what the Navigator lacks or what gets in its way (not its own
            # mistakes): the user's complaints channel. 14 missions without a
            # clock never reached the user because they were filed as slips.
            w = self.w
            text = " ".join(args).strip()
            if not text:
                return {"ok": False, "error": "usage: complain TEXT (what you lacked / what got in your way)"}
            where = "town" if not w.depth else f"{w.depth_ft}ft"
            nick = os.path.basename(self.rundir.rstrip("/"))
            line = f"- {time.strftime('%Y-%m-%d %H:%M:%S')} {nick} {where} (Navigator): {text}"
            # runs/complaints.md (rundir is runs/pilot/<nick>)
            path = os.path.join(os.path.dirname(os.path.dirname(self.rundir.rstrip("/"))), "complaints.md")
            new = not os.path.exists(path)
            with open(path, "a") as f:
                if new:
                    f.write("# Complaints: what the agents lacked or what got in their way\n\n"
                            "Appended by `pilotctl complain` (Navigators) and by hand (Advisor, Clerks). The\n"
                            "Architect reviews this after every mission and relays recurring or unfixable ones\n"
                            "to the user.\n\n")
                f.write(line + "\n")
            self.log("nav_complaint", text=text)
            return {"ok": True, "text": "complaint logged (runs/complaints.md); the Architect reviews it after the mission"}
        if c == "say":
            # the Navigator answering the user (shown in the observer's viewer)
            text = " ".join(args)
            self.log("nav_say", text=text)
            self.unanswered = []                  # (answered)
            with open(os.path.join(self.rundir, "commentary.jsonl"), "a") as f:
                f.write(json.dumps({"t": round(time.time(), 3), "who": "navigator", "note": text}) + "\n")
            return {"ok": True, "text": "said"}
        if c == "ask":
            return self.ask_architect(" ".join(args))
        if c == "answer":
            return self.answer_navigator(args)
        if c == "price":
            return {"ok": True, "text": self.price_info(" ".join(args))}
        if c == "monster":
            return {"ok": True, "text": self.monster_info(" ".join(args).replace("_", " "))}
        if c == "drainers":
            return {"ok": True, "text": self.drainers_info(args)}
        if c == "gear":
            return {"ok": True, "text": self.gear_review()}
        if c == "gearcmp":
            # the item slot evaluator (geareval.py): each named pack item (letter or name) or item name against the
            # worn slot; no argument: every identified wearable in the pack
            if self.w.in_dungeon and self.w.monsters:
                return {"ok": False, "error": "gearcmp runs ~1-3 s of simulation: not with monsters in view -- "
                                              "`goal quiet` first (it waits somewhere clear), then gearcmp"}
            pack = self.w.items()
            items = []
            for a in args or []:
                a2 = a.replace("_", " ")
                if len(a2) == 1 and a2.islower():
                    try:
                        idx = self.item_index(a2)
                    except ValueError as e:
                        return {"ok": False, "error": str(e)}
                    it = next((i for i in pack if i["item"] == idx), None)
                else:
                    it = next((i for i in pack if a2.lower() in i["name"].lower()), None) or a2
                if it:
                    items.append(it)
            if not args:
                items = [i for i in pack if i["tval"] in geareval.SLOT_OF_TVAL and i["tval"] != TV_LITE and
                         self.iv(i["name"]).known]
            if not items:
                return {"ok": True, "text": "nothing to compare (name pack items by letter or name, or an item name)"}
            try:
                res = self.gear_eval(items, n=20)
            except Exception as e:
                return {"ok": False, "error": f"gear evaluator failed: {e!r}"}
            return {"ok": True, "text": geareval.report(res)}
        if c == "house":
            return self.house_info(args)
        if c == "loadout":
            # the loadout optimizer (geareval.optimize): changes across slots, e.g. a better weapon without Free
            # Action, with Free Action from a ring. `loadout shops` adds the shops' stock as last seen, within the gold
            # the essentials leave
            if self.w.in_dungeon and self.w.monsters:
                return {"ok": False, "error": "loadout runs ~2-5 s of simulation: not with monsters in view -- "
                                              "`goal quiet` first (it waits somewhere clear), then loadout"}
            return {"ok": True, "text": self.loadout_info(shops="shops" in args)}
        if c == "why":
            return {"ok": True, "text": self.why_info(args)}
        if c == "prep":
            return {"ok": True, "text": self.prep_info()}
        if self.dead and c not in ("attention", "quit", "orders", "map", "note", "view", "say", "viewmap",
                                   "journal") and \
                not (c == "goal" and args[:1] == ["resurrect"]):
            return {"ok": False, "error": "the character is dead (a ghost): only 'goal resurrect' works"}
        if c == "goal":
            return self.request_goal(args)
        if c == "plan":
            return self.request_plan(args)
        if c == "stop":
            self.set_goal(None)
            self.stop_resting()
            if self.plan:
                self.log("plan_end", plan=self.plan.text, status="stopped")
                self.plan = None
                self.clear_plan_file()
                return {"ok": True, "note": "the trip plan is stopped too"}
            return {"ok": True}
        if c == "order":
            # every KEY=VALUE checked before any is applied: `order a=1 b=bad` used to set a in memory, then fail
            # before orders.json was written (lost on restart), with a bare ValueError (refactor-candidates A22, F5)
            if not args:
                return {"ok": False, "error": "usage: order KEY=VALUE ... (`orders` lists them)"}
            new = {}
            for kv in args:
                if "=" not in kv:
                    return {"ok": False, "error": f"order {kv}: give KEY=VALUE, e.g. `order {kv}=...` "
                                                  f"(now {self.orders.get(kv, '?')}); nothing changed"}
                k, v = kv.split("=", 1)
                if k not in self.orders:
                    return {"ok": False, "error": f"no order {k} (known: {', '.join(sorted(self.orders))}); "
                                                  "nothing changed"}
                cur = self.orders[k]
                try:
                    new[k] = type(cur)(v) if not isinstance(cur, str) else v
                except ValueError:
                    return {"ok": False, "error": f"order {k}={v}: {k} takes "
                                                  f"{'a whole number' if isinstance(cur, int) else 'a number'} "
                                                  f"(now {cur}); nothing changed"}
            self.orders.update(new)
            with open(self.orders_file, "w") as f:
                json.dump(self.orders, f)
            out = {"ok": True, "orders": self.orders}
            md = int(self.orders.get("max_depth", 0) or 0)
            if md:
                # the Borg's warrior gate (the Advisor's progression memo):
                # clvl x 50 ft to 1000 ft, then (clvl - 5) x 50; never past 1000 ft without FA
                lev = self.w.clvl
                gate = lev * 50 if lev <= 20 else max(1000, (lev - 5) * 50)
                warn = []
                if md > gate:
                    warn.append(f"max_depth {md} ft is deeper than the gate for clvl {lev} ({gate} ft)")
                if md > 1000 and not self.has_ability("free_action"):
                    warn.append("below 1000 ft without Free Action")
                if warn:
                    out["note"] = "careful: " + "; ".join(warn) + " (HANDBOOK stage table)"
            return out
        if c in self.ACTIONS:
            key = self.ACTIONS[c]
            if not args:
                return {"ok": False, "error": f"usage: {c} ITEMLETTER"}
            # `destroy !NAME`: over the value policy (counted in the Navigator's debt)
            forced_cmd = args[0].startswith("!") and len(args[0]) > 1
            if forced_cmd:
                args = [args[0][1:]] + list(args[1:])
            # a name of several words: `destroy Ration of Food` sent "of" as the count (m25: "You destroy no
            # more Rations"); only a trailing number, `all` or `force` modifies
            if c in ("destroy", "drop", "quaff", "eat", "fuel", "wear", "takeoff") and len(args) > 1:
                args, tail = list(args), []
                while len(args) > 1 and (args[-1].isdigit() or args[-1] in ("all", "force")):
                    tail.insert(0, args.pop())
                args = [" ".join(args)] + tail
            if c == "fuel" and not any(i["tval"] == TV_LITE for i in self.w.items(equip=True)):
                # The Pilot takes the lantern off when idle in town ("You are not
                # wielding a light", mission 17): put it on first, then find the
                # flask again (the letters shift when the lantern leaves the pack)
                lan = self.find_item("Lantern", TV_LITE)
                if not lan:
                    return {"ok": False, "error": "no lantern worn or in the pack to fuel"}
                try:
                    was = next(i["name"] for i in self.w.items() if i["item"] == self.item_index(args[0], pack_only=True))
                except (ValueError, StopIteration) as e:
                    return {"ok": False, "error": str(e) or f"no item '{args[0]}'"}
                self.cmd(f"custom w item={lan['item']}", "agent: fuel: wear the lantern first", hold=0.6)
                self.pack_now(1.0)
                again = next((i for i in self.w.items() if i["name"] == was), None)
                if not again:
                    return {"ok": False, "error": f"wore the lantern, but can't find '{was}' in the pack now"}
                args = [chr(97 + again["item"])] + list(args[1:])
            try:
                if c in ("destroy", "drop", "quaff", "read", "eat", "fuel") and not \
                        (len(args[0]) == 1 or args[0].isdigit()):
                    # by name: only the pack (a name that matched nothing there once
                    # fell through to the equipment -- "You destroy (nothing)"), and
                    # through item_index's ambiguity check (the Advisor's mission 16
                    # replay: this branch still took the first substring match)
                    item = self.item_index(args[0], pack_only=True)
                else:
                    self.equip_letters_lower = c == "takeoff"
                    try:
                        item = self.item_index(args[0], equip=(c == "takeoff"))
                    finally:
                        self.equip_letters_lower = False
            except ValueError as e:
                return {"ok": False, "error": str(e)}
            extra = ""
            iname0 = next((i["name"] for i in self.w.inven if i["item"] == item), "")
            if c in ("read", "use") and re.search(r"Teleport|Phase Door", iname0) and "force" not in args[1:] and \
                    not waited(self.escape_read_t, 3.0):
                # (m30: the Navigator read a second Teleportation 2 s after the first landed, back beside the hounds)
                return {"ok": False, "error": "an escape was read less than 3 s ago and may still be landing: look "
                                              "again (`status`), or add 'force'"}
            if c == "read" and "Word of Recall" in iname0 \
                    and self.recall_started(gnow()) and "force" not in args[1:]:
                return {"ok": False, "error": "a recall is already under way: reading another cancels it "
                                              "(add 'force' to cancel it on purpose)"}
            iname = next((i["name"] for i in self.w.inven if i["item"] == item), "")
            if c == "read" and "Word of Recall" in iname and self.w.depth == 0 and recall_level(iname) is None \
                    and "force" not in args[1:]:
                return {"ok": False, "error": f"'{iname}' has no valid @R inscription: it would recall to the "
                                              "deepest level ever reached. Inscribe it (inscribe ITEM @R<feet>), "
                                              "use goal recall (it inscribes max_depth), or add 'force'"}
            if c == "wear" and self.req_role != "architect" and "force" not in args[1:]:
                # unknown jewellery: 19-58% of unknown rings are cursed, a cursed one can't come off, and
                # wearing it doesn't identify it (m22 wore a cursed ring; the Advisor's set-piece C7)
                itw = next((i for i in self.w.inven if i["item"] == item), None)
                if itw and itw["tval"] in (40, 45) and (self.unknown_flavour(itw) or self.iv(itw["name"]).known is False):
                    return {"ok": False, "error": f"'{itw['name']}' isn't identified: unknown jewellery is often cursed "
                                                  "(and a cursed ring or amulet can't be taken off). Identify it first "
                                                  "(`plan town` does), or add 'force'"}
            if c in ("destroy", "drop"):
                it0 = next((i for i in self.w.inven if i["item"] == item), None)
                why = self.value_refusal(it0, c) if not forced_cmd else None
                if why:
                    return {"ok": False, "error": f"not {c}ed: {why}. `{c} !NAME` overrides, and adds the value "
                                                  "lost to your debt"}
                if forced_cmd and self.req_role != "architect":
                    if not self.override_allowed():
                        return {"ok": False, "error": f"not {c}ed: your freedom to override the Pilot's value policy "
                                                      f"is suspended (debt {self.debt_total()} gold)"}
                    if self.value_refusal(it0, c):
                        self.add_debt(round(self.iv(it0["name"]).value * self.pay_cut(self.iv(it0["name"]).tval)), it0["name"],
                                      f"{c}ed with ! over the value policy")
                n = args[1] if len(args) > 1 else "1"
                if n == "all":
                    it = next((i for i in self.w.inven if i["item"] == item), None)
                    n = it["number"] if it else 1
                extra = f" value={n}"
                if c == "destroy":
                    self.c.send("confirm yes")
                else:
                    # what we drop stays dropped: auto-pickup and looting skip
                    # this square (pickup=all re-picked dropped items, mission 9)
                    self.skipped_items.add((self.w.level_t, self.w.pos))
            if c in ("aim",):
                extra = f" dir={args[1] if len(args) > 1 else 5}"
            # (a staff that works on an item -- Perception -- takes it the same way:
            # tables.c gives 'u' the same scheme as 'r'; mission 21 identified the
            # flask in slot a twice)
            if c in ("read", "use") and len(args) > 1 and args[1] != "force":
                # A scroll that works on another item (Identify, Enchant...): the
                # client sends that item in the direction byte (COMMAND_SECOND_DIR);
                # without it the server picked the first pack item
                try:
                    target = self.item_index(args[1], equip=True)
                except ValueError as e:
                    return {"ok": False, "error": str(e)}
                extra = f" dir={target}"
                tit = next((i for i in self.w.items() + self.w.items(equip=True) if i["item"] == target), None)
                if tit and self.unknown_flavour(tit):
                    # learn from the server's answer, "In your pack: a Ring of X (q)."
                    # (the pack diff missed a cursed ring autodestroyed at once and
                    # a second Identify read straight after, mission 16)
                    self.id_target = {"t": gnow(), "flavour": flavour_key(tit["name"]),
                                      "letter": None if tit["equip"] else chr(97 + target)}
            t0 = gnow()
            before = (self.effect_sig("pack"), self.effect_sig("equip"))
            it_before = next((i for i in self.w.inven if i["item"] == item), None)
            pos_before = self.w.pos
            self.cmd(f"custom {key} item={item}{extra}", f"agent: {c} {args}")
            pack = self.pack_now()
            # (mission 20: a destroy's reply showed the pack before it landed, and
            # the retry found "nothing matches"): give it up to ~2 s more
            for _ in range(3):
                if c == "inspect" or (self.effect_sig("pack"), self.effect_sig("equip")) != before:
                    break
                pack = self.pack_now(0.6)
            noise = ("You enter a maze", "Looks like", "You feel", "You hear", "You have found")
            said = [t for ts, t in self.w.messages if ts >= t0 and not t.startswith(noise)]
            # (say what was done first: m30's `read Teleportation` worked, but the reply was the pack, and the
            # Navigator read the second scroll by letter 9 s later)
            did = f"{c} {it_before['name'] if it_before else args[0]}"
            if it_before and not it_before.get("equip"):
                kind = bare_name(it_before["name"])
                now_n = sum(i["number"] for i in self.w.items() if singular(kind) in singular(i["name"]))
                did += f" ({it_before['number']} -> {now_n} left)"
            if pos_before and self.w.pos and self.w.pos != pos_before:
                did += f"; moved {pos_before} -> {self.w.pos} ({self.w.dist(pos_before)} squares)"
            out = {"ok": True, "did": did, "said": said[-4:], "pack": pack}
            if c in ("use", "aim", "zap") and said:
                pass          # a device's effect is what the game said (an unknown staff shows no charges)
            elif c in ("read", "use") and re.search(r"Teleport|Phase Door", iname0) and \
                    (self.effect_sig("pack"), self.effect_sig("equip")) == before:
                out["note"] = "an escape: its landing can take ~2 s; the status line shows ESCAPE LANDING until we move"
            elif c != "inspect" and (self.effect_sig("pack"), self.effect_sig("equip")) == before:
                # (the game-state survey: never report as done what didn't happen)
                out["note"] = "no change in the pack or equipment yet: it may not have happened"
            return out
        if c == "wearall":
            # Put on every weapon/armour/light in the pack whose slot is empty
            self.wear_queue = True
            return {"ok": True}
        if c == "inscribe":
            try:
                item = self.item_index(args[0])
            except ValueError as e:
                return {"ok": False, "error": str(e)}
            self.cmd(f"custom {{ item={item} entry={' '.join(args[1:])}", f"agent: inscribe {args}")
            return {"ok": True, "pack": self.pack_now()}
        if c == "search":
            # search the 8 squares around us N times (each search is a turn and
            # finds a given secret door/trap ~14% of the time for Dive04: 15 ~ 90%).
            # Standing still doesn't search (mission 15, the user; cmd1.c search())
            n = max(1, min(40, int(args[0]) if args else 15))
            t0 = gnow()
            for _ in range(n):
                self.c.send("custom s")
            # (the server runs them one a player turn, ~0.65 s, so a move sent sooner waits behind them;
            # busy for longer would hold the emergency reflexes too)
            self.busy_until = gnow() + 0.15 * n
            # wait for the searches to run (one a turn), stop early on a find
            # (mission 16: the reply said "nothing found" while the game had said
            # "You have found a secret door" a few seconds later)
            end = gnow() + min(25.0, 0.7 * n + 1.0)
            found = []
            heard = False
            while gnow() < end and not found:
                self.c.collect(0.5)
                self.w.drain()
                found = [t for ts, t in self.w.messages if ts >= t0 and ("found" in t or "discovered" in t)]
                if self.service_notes() and self.unanswered:
                    heard = True             # the user spoke: answer now (the searches still run)
                    break
            return {"ok": True, "text": f"searched {n} times here: " + ("; ".join(found) if found else
                    "stopped waiting for the result: a user message came in" if heard else "nothing found")}
        if c in ("disarm", "open"):
            # a chest (or door/trap) in direction DIR (5 = the square you stand on):
            # search first to find a chest's trap, disarm it, then open
            d = args[0] if args else "5"
            t0 = gnow()
            self.cmd(f"custom {'D' if c == 'disarm' else 'o'} dir={d}", f"agent: {c} {d}")
            self.c.collect(1.0)
            self.service_notes()
            said = [t for ts, t in self.w.messages if ts >= t0]
            return {"ok": True, "said": said[-4:], "pack": self.pack_now(0.3)}
        if c == "pickup":
            self.cmd("custom ,", "agent: pickup")
            return {"ok": True}
        if c == "stairs":
            self.take_stairs(args[0] if args else (self.w.standing_on or ">"))
            return {"ok": True}
        if c == "option":
            self.c.send(f"option {args[0]} {args[1]}")
            return {"ok": True}
        if c == "goalstate":
            g = self.goal
            st = {k: (repr(v)[:120]) for k, v in (vars(g).items() if g else [])}
            if g and getattr(g, "explore", None) is not None:
                st["explore_state"] = {k: repr(v)[:80] for k, v in vars(g.explore).items()}
            return {"ok": True, "goal": g.describe() if g else None, "state": st,
                    "mover": {"active": self.mover.active, "path": len(self.mover.path),
                              "free": self.mover.free is not None, "running": self.mover.running is not None},
                    "standing_on": self.w.standing_on, "busy": self.busy_until - gnow()}
        if c == "options":
            opts = self.c.query("options", "options")["list"]
            return {"ok": True, "options": {k: v for k, v in opts.items() if not args or any(a in k for a in args)}}
        if c == "dump":
            path = os.path.join(self.rundir, "world_dump.json")
            with open(path, "w") as f:
                json.dump({"pos": self.w.pos, "depth": self.w.depth, "rows": self.w.rows,
                           "memory": [[y, x, ch] for (y, x), ch in self.w.memory.items()],
                           "monsters": [[y, x, r.idx] for y, x, r in self.w.monsters]}, f)
            return {"ok": True, "file": path}
        if c == "raw":
            self.cmd(" ".join(args), "agent: raw")
            return {"ok": True}
        if c == "attention":
            with self.att_cond:
                evs, self.attention = self.attention, []
            return {"ok": True, "events": evs}
        if c == "quit":
            self.running = False
            return {"ok": True}
        if c == "park":
            # Log out at the next safe moment (for a Pilot update): the goal is
            # dropped now, the logout waits until nothing is close and HP is OK
            if not isinstance(self.goal, Recall):
                self.set_goal(None)       # a pending recall is allowed to finish first
            self.parking = gnow()
            return {"ok": True, "note": "will log out when safe"}
        return {"ok": False, "error": f"unknown command {c}"}

    def plan_tick(self, now, idle):
        """Run the trip plan: when no goal is running, its next step; every 2 s under
        a goal, its conditions. True if it acted."""
        pl = self.plan
        if not pl or (not idle and now - self.plan_t < 2):
            return False
        self.plan_t = now
        try:
            r = pl.tick(self)
        except Exception as e:             # a plan bug must not kill the pilot
            r = ("failed", f"error: {e!r}")
        pl.save(self) if not r else self.clear_plan_file()
        if r:
            self.plan = None
            self.log("plan_end", plan=pl.text, status=r[0], detail=r[1], levels=pl.levels,
                     minutes=round((now - pl.t0) / 60, 1))
            self.notify("plan_done" if r[0] == "done" else "plan_failed", f"{pl.text}: {r[1]}")
        return idle and self.goal is not None

    def clear_plan_file(self):
        try:
            os.remove(os.path.join(self.rundir, "plan.json"))
        except OSError:
            pass

    PLAN_USAGE = ("usage: plan trip LO-HI [until \"COND or COND...\"] [then recall|town] [level_min=N] [via=stairs|recall] "
                  "[force] | "
                  "plan town [kit=A|B|C|none] [buy [STORE/]NAME[:N][@MAX],...] | plan stop | plan resume | plan")

    def request_trip(self, args):
        w = self.w
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", args[0]) if args else None
        if not m:
            return {"ok": False, "error": self.PLAN_USAGE}
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        if lo > hi or lo % 50 or hi % 50 or lo < 50:
            return {"ok": False, "error": f"{args[0]}: a depth range in feet, multiples of 50, e.g. 600-700"}
        md = int(self.orders.get("max_depth", 0) or 0)
        if md and hi > md:
            return {"ok": False, "error": f"{hi} ft is below max_depth {md}: `order max_depth={hi}` first "
                                          "(going deeper is your standing order to give)"}
        until, then, level_min, force, via, i = None, "recall", 10, False, None, 1
        while i < len(args):
            a = args[i]
            if a == "until":
                j = i + 1
                while j < len(args) and args[j] not in ("then", "force") and \
                        not args[j].startswith(("level_min=", "via=")):
                    j += 1
                until, i = " ".join(args[i + 1:j]), j
                continue
            if a == "then" and i + 1 < len(args):
                then, i = args[i + 1], i + 2
                if then not in ("recall", "town"):
                    return {"ok": False, "error": "then recall (stop in town) or then town (and run the town kit)"}
                continue
            if a.startswith("level_min="):
                level_min = float(a.split("=", 1)[1])
            elif a.startswith("via="):
                via = a.split("=", 1)[1]
                if via not in ("stairs", "recall"):
                    return {"ok": False, "error": "via=stairs (walk down: one Word of Recall is enough, for coming "
                                                  "home) or via=recall (two: one to go, one to come home)"}
            elif a == "force":
                force = True
            else:
                return {"ok": False, "error": f"can't read {a!r}; " + self.PLAN_USAGE}
            i += 1
        try:
            conds = TripPlan.parse_until(until or "cures<3 or phase<3 or minutes>45")
        except ValueError as e:
            return {"ok": False, "error": f"until: {e}"}
        # (holds with the one Word of Recall left after the recall down: wor<N for N >= 2, wor<=N for N >= 1 -- the
        # old test let wor<=1 through and refused the harmless wor<1, refactor-candidates A18)
        bad = [c[0] for c in conds if c[1] == "wor" and c[2] in ("<", "<=") and int(c[3]) + (c[2] == "<=") >= 2]
        if bad:
            return {"ok": False, "error": f"until {bad[0]}: that holds as soon as the trip has recalled down (one "
                                          "Word of Recall goes on the way down); coming home with none left is "
                                          "built in"}
        plan = TripPlan(lo, hi, conds, then, level_min, via)
        if w.depth == 0 and not force:
            want = min(hi, max(lo, self.deepest_ft or 0))
            down_by_recall = not plan.stairs_down(self)
            gap = self.supply_gate(want, down_by_recall)
            if gap:
                return {"ok": False, "error": f"supply gate for {want} ft "
                                              f"({'down by Word of Recall: 2 needed' if down_by_recall else 'down by the stairs: 1 Word of Recall for coming home'}): "
                                              f"missing {'; '.join(gap)}. `plan town` first"
                                              + ("" if via else ", or `via=stairs`") + ", or add 'force'"}
        self.plan = plan
        self.set_goal(None)
        self.log("plan_start", plan=self.plan.text, role=self.req_role)
        return {"ok": True, "plan": self.plan.text + (" (down by the stairs)" if self.plan.stairs_down(self) and w.depth == 0
                                                     else " (down by Word of Recall)" if w.depth == 0 else ""),
                "note": "the Pilot runs it; `wait` wakes you when it ends (plan_done) and for what it can't "
                        "handle (user messages, stat drains, emergency loops). Bands, pits, breeders and the "
                        "like are news: it leaves the level itself. A goal you give pauses the plan until it "
                        "ends (`plan resume` ends your goal and hands back); `plan stop` ends it"}

    def request_plan(self, args):
        """plan trip ... | plan town [kit=A|B|C|none] [buy [STORE/]NAME[:N][@CAP][,...]]... | plan stop | plan resume |
        plan"""
        if not args:
            return {"ok": True, "text": f"plan: {self.plan.describe()}" if self.plan else "no plan"}
        if args[0] == "stop":
            if not self.plan:
                return {"ok": True, "text": "no plan"}
            self.log("plan_end", plan=self.plan.text, status="stopped")
            self.plan = None
            self.clear_plan_file()
            return {"ok": True, "text": "plan stopped (the current goal runs on; `stop` stops it)"}
        if args[0] == "resume":
            # (m30: the Navigator's `goal explore` paused the plan for 7 minutes on a quiet level, with no way to
            # hand control back short of the goal ending)
            if not self.plan:
                return {"ok": True, "text": "no plan"}
            if not self.plan.paused:
                return {"ok": True, "text": f"the plan isn't paused: {self.plan.describe()}"}
            ended = self.goal.describe() if self.goal else None
            self.set_goal(None)
            self.plan.paused, self.plan.pause_goal = False, None
            self.log("plan_resumed", plan=self.plan.text, ended=ended)
            return {"ok": True, "text": f"plan resumed{' (ended ' + repr(ended) + ')' if ended else ''}: "
                                        f"{self.plan.describe()}"}
        if args[0] == "trip":
            return self.request_trip(args[1:])
        if args[0] != "town":
            return {"ok": False, "error": self.PLAN_USAGE}
        if self.w.depth:
            return {"ok": False, "error": "plan town is for the town (recall home first)"}
        kit, buylist, specs, i = None, [], [], 1
        while i < len(args):
            a = args[i]
            if a.startswith("kit="):
                kit = a[4:]
                if kit not in self.KITS:
                    return {"ok": False, "error": f"kit={kit}: A (to 500 ft), B (to 1000 ft), C (deeper) or none"}
            elif a == "buy":
                pass
            else:
                # (not inside [..] or (..): m43's `2/pair_of_hard_leather_boot_[3,+6]@1050`, the line `gear` printed,
                # split into "boot_[3" and "+6]")
                specs += split_specs(a)
            i += 1
        for sp in specs:
            m = re.fullmatch(r"(?:([1-7])/)?([^:@]+)(?::(\d+))?(?:@(\d+))?", sp)
            if not m:
                return {"ok": False, "error": f"can't read the buy item {sp!r}: [STORE/]NAME[:COUNT][@MAXPRICE]"}
            name = m.group(2).replace("_", " ").strip()
            store = int(m.group(1)) if m.group(1) else self.buy_store(name)
            # (a kit line knows its shop: m46's Navigator was told to "name the shop" for a Potion of Speed)
            if not store:
                store = next((v[1] for k, v in self.KIT_ITEMS.items() if k.lower() == name.lower()), None)
            if not store:
                return {"ok": False, "error": f"no shop's stock table has {name!r}: name the shop (e.g. 7/{m.group(2)}"
                                              " for the Black Market, which charges 3x)"}
            buylist.append((name, int(m.group(3) or 1), int(m.group(4)) if m.group(4) else None, store))
        g = TownKit(kit, buylist)
        g.by_navigator = self.req_role != "architect"
        g.role = self.req_role
        self.set_goal(g)
        buys, short = self.town_shopping(kit, buylist)
        return {"ok": True, "goal": g.describe(),
                "note": "will buy (by the prices last seen): " + (", ".join(f"{n} {k} at the {self.STORE_LABEL.get(st, st)} ({st})"
                                                                           for _, k, st, n, _ in buys)
                                                                 or "nothing") +
                        (("; can't afford yet: " + ", ".join(f"{n} {k}" for k, n in short)) if short else "") +
                        self.town_extras_note() + " (selling first may change this)"}

    # --- order checks (restructure step 2.4) ------------------------------------
    def hunt_refusal(self, name):
        """Why the Pilot won't take this hunt now, or None (and the estimate it used)."""
        w = self.w
        key = name.lower()
        seen = [r for *_, r in w.monsters if key in r.name.lower()]
        race = seen[0] if seen else next((r for r in w.g.races.values() if r.name.lower() == key), None) or \
            next((r for r in w.g.races.values() if key in r.name.lower()), None)
        if not race:
            return None, "no monster by that name in this game's data"
        if "UNIQUE" in race.flags and race.name.lower() in self.uniques_killed():
            return (f"you've killed {race.name} before: a repeat kill gives no XP and no drop (the server's "
                    "'cheeze' rule), so there's nothing to hunt it for"), None
        if race.paralyser and not self.has_ability("free_action"):
            return (f"{race.name} paralyses (a blow or Hold Person) and you have no Free Action: a paralysed "
                    "warrior is hit until dead. Only with Free Action"), None
        est = self.fight_estimate(race)
        if not est:
            return None, f"no fight estimate for {race.name}"
        turns, taken, worst, breath, row = est
        hp = max(1, w.hp[0])
        sim = self.fight_sim(race)
        if sim:
            # the Advisor's duel simulator (hunt-strictness memo, 2026-10-24): the 90th percentile of
            # the HP lost, at our live profile, replaces "twice the turns"
            turns, taken, worst = sim["turns_mean"], sim["loss_mean"], sim["loss_p90"]
        info = (f"{race.name}: ~{turns:.0f} turns to kill, ~{taken:.0f} HP lost on average, ~{worst:.0f} in a bad "
                f"fight (1 in 10; you have {w.hp[0]})")
        # a fight the Pilot's own emergency rule would break off on average: it phases away once HP is
        # within 2.5 worst rounds of the monster (or below flee_hp), so a hunt whose average loss ends
        # there is lost (the set-piece harness's C3: Ulfast, ~118 on average, broken off at 145 HP)
        abort = max(self.worst_3turns([race]), float(self.orders.get("flee_hp", 0.5)) * w.hp[1])
        if hp - taken < abort:
            return (f"{info}: on average it ends below {abort:.0f} HP, where the Pilot's emergency rule breaks a "
                    "fight off (its worst 3 turns, or flee_hp); rest to full or come back stronger", info)
        if row.get("response") in ("AVOID", "LEAVE") and row.get("veto_reason", "qualitative") != "strength":
            # (the Advisor's m24 memo: ratings given for strength alone are the simulator's to judge;
            # its veto_reason column says which, from its next rulebook build)
            return (f"the Advisor's rating for {race.name} is {row['response']}", info)
        if worst > 0.6 * hp:
            return (f"{info}: a bad fight would cost more than 60% of your HP. Rest to full first, or come back "
                    "stronger", info)
        # summoners: once summons arrive the fight is a band (the m19 Ranger: a cheap duel, then
        # S_ANIMAL and bolts cost 153 HP). Only a clear win, at high HP, alone, with escapes
        if any(sp.startswith("S_") for sp in race.spells):
            others = sum(1 for *_, r in w.monsters if r.name != race.name)
            phase = sum(i["number"] for i in w.items(tval=TV_SCROLL) if "Phase Door" in i["name"])
            if worst > 0.3 * hp or w.hp_frac < 0.8 or others or phase < 5:
                return (f"{race.name} summons help: hunt it only when a bad fight costs under 30% of your HP, you're "
                        f"at 80%+ HP, nothing else is in view and you carry 5+ Phase Door ({info})", info)
        if breath > 0.6 * hp:
            return (f"{race.name} breathes up to {breath:.0f} (you have {w.hp[0]}): one breath could take "
                    f"60% of your HP", info)
        band_lt = (self.band_warned or (None, 0))[0]
        if band_lt == w.level_t and gnow() - self.band_warned_t < 120 and \
                sum(1 for *_, r in w.monsters if "NEVER_MOVE" not in r.flags) >= 5:
            return (f"a band is about (flagged {gnow() - self.band_warned_t:.0f} s ago): leave first", info)
        return None, info

    def stale_order(self, c, args):
        """An order whose premise is gone since the report it answers (the Advisor's
        starting-over memo: a goto written for a 17-s-old report walked beside Brodda).
        Returns the reason to hold it, or None."""
        st = self.report_state
        rid, rt = self.last_report
        if not st or not rid:
            return None
        w, age = self.w, gnow() - rt
        positional = (c == "goal" and args[:1] and args[0] in ("goto", "fetch", "searchroom", "hunt") and
                      not (args[0] == "goto" and len(args) > 1 and args[1] in ("<", ">"))) or \
                     (c == "avoid" and args and re.match(r"\d+,\d+$", args[0]))
        if not positional:
            return None
        if st["level_t"] != w.level_t:
            return (f"your order answers report r{rid} ({age:.0f} s ago), from a level you've since left (now "
                    f"{w.depth_ft} ft): positions and monsters there are gone. Look again (`status`) and re-issue")
        if c == "goal" and args[0] == "hunt" and age > 5:
            key = " ".join(args[1:]).replace("_", " ").lower()
            if key and not any(key in r.name.lower() for *_, r in w.monsters):
                return (f"{key} isn't in view now (your order answers report r{rid}, {age:.0f} s ago). "
                        "Re-issue when it is")
        if c == "goal" and args[0] in ("goto", "fetch") and age > 5 and st["hp"] - w.hp_frac > 0.25:
            return (f"HP fell from {st['hp']:.0%} to {w.hp_frac:.0%} since report r{rid} ({age:.0f} s ago): a "
                    "detour then may not be one now. Look again and re-issue")
        return None

    def request_goal(self, args):
        if not args:
            return {"ok": False, "error": "usage: goal NAME [ARGS]"}
        # Unread attention events belong to what came before: move them to the
        # news, so the next 'wait' answers about this goal
        with self.att_cond:
            self.news += self.attention
            self.attention = []
        name, rest = args[0], args[1:]
        force = "force" in rest
        scum = name == "dive" and "scum" in rest
        rest = [a for a in rest if a not in ("force", "scum")] if name in ("dive", "recall") else rest
        if name == "dive":
            g = Dive(rest[0] if rest else (self.w.depth_ft + 50), scum=scum)
            md = int(self.orders.get("max_depth", 0))
            want = min(g.target_ft, md) if md else g.target_ft
            gap = self.supply_gate(want, False) if want > self.w.depth_ft and not force else []
            if gap:
                return {"ok": False, "error": f"supply gate for {want} ft: missing {'; '.join(gap)} "
                                              "(the stage table). Restock, or add 'force' to go anyway"}
            if md and g.target_ft > md:
                # say so (a 'dive 700' was silently capped by max_depth 650)
                self.set_goal(g)
                return {"ok": True, "goal": g.describe(),
                        "note": f"capped at max_depth {md} ft (order max_depth=... to change)"}
        elif name == "explore":
            kw = dict(a.split("=", 1) for a in rest if "=" in a)
            g = Explore(until=kw.get("until"), radius=int(kw["radius"]) if "radius" in kw else None)
        elif name == "goto":
            force = "force" in rest
            g = Goto(" ".join(x for x in rest if x != "force"), force=force)
        elif name == "shop":
            # goal shop STORE [buy NAME:N]... [sell LETTER:N]...
            list_stock = "list" in rest[1:]
            rest = [a for i_, a in enumerate(rest) if not (i_ and a == "list")]
            buys, sells, i = [], [], 1
            while i < len(rest):
                kind, spec = rest[i], rest[i + 1] if i + 1 < len(rest) else ""
                what, _, n = spec.rpartition(":")
                what, n = (what, n) if what else (spec, "1")
                n, _, cap = n.partition("@")        # NAME:COUNT@MAXPRICE (each)
                plus = n.startswith("+")
                n = int(n.lstrip("+"))
                if kind == "buy":
                    # NAME:N means "have N", as in plan town (m27: `buy Phase_Door:11` bought 9 more on top of 11,
                    # 171 of 179 gold); `buy NAME:+N` buys N more
                    name = what.replace("_", " ")
                    if not plus:
                        key = singular(name.lower())
                        have = sum(it["number"] for it in self.w.items() if key in singular(it["name"].lower()))
                        n = n - have
                    if n > 0:
                        buys.append((name, n, int(cap) if cap else None))
                elif kind in ("sell", "quote"):
                    key = what.replace("_", " ")
                    # quote: offer it and decline, to see the price (the Navigator's wish)
                    sells.append((self.item_index(key) if len(key) == 1 else key, n) +
                                 (("quote",) if kind == "quote" else ()))   # '!NAME' forces a sale
                i += 2
            g = Shop(rest[0], buys, sells, list_stock=list_stock)
        elif name == "search":
            g = Search()
        elif name == "searchroom":
            m = re.match(r"^(\d+)[ ,](\d+)$", " ".join(rest[:2]) if len(rest) > 1 else (rest[0] if rest else ""))
            if not m:
                return {"ok": False, "error": "usage: goal searchroom Y,X (an inner room's centre, from the report)"}
            Y, X = int(m.group(1)), int(m.group(2))
            # its door already in view: nothing to search for (mission 20 searched
            # 26 s beside an open door at 27,39)
            open_d = [self.room_door(Y, X)] if self.room_door(Y, X) else []
            if open_d:
                return {"ok": False, "error": f"the inner room at {Y},{X} already shows its door at "
                                              f"{open_d[0][0]},{open_d[0][1]}: `goal explore` goes in "
                                              "(a closed door opens on a bump)"}
            g = Search(tries=20, spots=[r for _, r in structures.door_spots(Y, X)])
            g.name = f"searchroom {Y},{X}"
        elif name == "hunt":
            target = " ".join(rest).replace("_", " ")    # 'hunt Black_ogre', like shop names
            force = target.startswith("!")
            target = target.lstrip("!").strip()
            why, info = self.hunt_refusal(target)
            if why and self.req_role != "architect" and not force:
                self.log("order_refused", order=f"hunt {target}", why=why)
                return {"ok": False, "error": f"hunt refused: {why}. `goal hunt !NAME` overrides; if the fight goes "
                                              "wrong, the HP it costs goes into your fight debt"}
            if why and force and self.req_role != "architect" and not self.override_allowed("hunt"):
                return {"ok": False, "error": f"hunt refused: {why}. Your freedom to override the Pilot's fight "
                                              f"checks is suspended (fight debt {self.fight_debt_total()} HP)"}
            g = Hunt(target)
            g.estimate = info
            if why and force and self.req_role != "architect":
                # an override: judged when the hunt ends (the user, 2026-10-23: a separate debt)
                w = self.w
                g.overridden = {"why": why, "hp0": w.hp[0], "hp_min": w.hp[0], "t0": gnow(),
                                "emerg0": len(self.emerg_times)}
                self.log("hunt_override", target=target, why=why, hp=w.hp[0])
        elif name == "fetch":
            # one item detour (the design's `fetch Y,X`): not with a band or danger about
            m = re.match(r"^(\d+)[ ,](\d+)$", " ".join(rest[:2]) if len(rest) > 1 else (rest[0] if rest else ""))
            if not m:
                return {"ok": False, "error": "usage: goal fetch Y,X (an item's square, from the report)"}
            if self.req_role != "architect" and self.w.in_dungeon:
                band_lt = (self.band_warned or (None, 0))[0]
                if band_lt == self.w.level_t and gnow() - self.band_warned_t < 120:
                    return {"ok": False, "error": "fetch refused: a band was flagged on this level in the last 2 "
                                                  "minutes; loot isn't worth it now (mission 22). Leave or fight first"}
                if self.dangers():
                    return {"ok": False, "error": "fetch refused: a dangerous monster is in view ("
                                                  + ", ".join(sorted({r.name for r in self.dangers()})[:3]) + ")"}
            g = Goto(f"{m.group(1)},{m.group(2)}")
            g.name = f"fetch {m.group(1)},{m.group(2)}"
        elif name == "leave":
            if not self.w.in_dungeon:
                return {"ok": False, "error": "leave is for dungeon levels"}
            g = Flee("you said: leave this level")
            g.name = "leave (this level)"
        elif name == "recall":
            g = Recall()
            if self.w.depth == 0 and not force:
                want = self.planned_depth()
                gap = self.supply_gate(want, True) if want else []
                if gap:
                    return {"ok": False, "error": f"supply gate for recalling down to ~{want} ft: missing "
                                                  f"{'; '.join(gap)} (the stage table). Restock, or "
                                                  "'goal recall force' to go anyway"}
        elif name == "town":
            g = Town()
        elif name == "townfarm":
            if not rest:
                return {"ok": False, "error": "usage: goal townfarm GOLD [MINUTES]"}
            g = TownFarm(rest[0], rest[1] if len(rest) > 1 else 10)
        elif name == "resurrect":
            g = Resurrect()
        elif name == "rest":
            g = RestGoal()
        elif name == "wait":
            g = Wait(rest[0] if rest else 5)
        elif name == "quiet":
            try:
                secs = float(rest[0]) if rest else 120
            except ValueError:
                return {"ok": False, "error": "usage: goal quiet [SECS] (10-600, default 120)"}
            mob = sorted({r.name for _, _, r in self.w.monsters if "NEVER_MOVE" not in r.flags}) \
                if self.w.in_dungeon else []
            if mob:
                return {"ok": False, "error": f"not quiet: {', '.join(mob[:3])} in view (it would wake at once). "
                                              "Deal with it, or `goal leave`"}
            # (the goal it replaces carries on after; a plan's own goal comes back with the plan)
            prev = self.goal if self.goal is not None and not self.goal.by_plan and \
                not isinstance(self.goal, QuietWait) else None
            g = QuietWait(secs, prev)
        else:
            return {"ok": False, "error": f"unknown goal {name}"}
        g.by_navigator = self.req_role != "architect"
        g.role = self.req_role
        self.set_goal(g)
        if g.estimate and not self.plan:
            return {"ok": True, "goal": g.describe(), "note": g.estimate}
        if self.plan:
            # your goal first; the plan carries on when it ends (`plan stop` ends the plan)
            self.plan.paused, self.plan.pause_goal = True, g
            return {"ok": True, "goal": g.describe(), "note": "the trip plan is paused until this goal ends"}
        return {"ok": True, "goal": g.describe()}

    # --- the situation report ------------------------------------------------

    # --- since the last report (the Advisor's Navigator-decisions memo §3.3:
    # it reported "lowest seen 58" when the low was 26, "single orc" for 12)

    # --- inner rooms, pits and nests (structures.py; the Advisor's spec,
    # memos/2026-10-07-mission15-answers.md §2: the user asked whether the
    # Pilot could recognise vaults and pits from a partial map)

    ADVICE = {
        "large room": "a lit large room: its one secret door is at the middle of a side of the inner block; "
                      "'goal searchroom {Y},{X}' searches the 4 spots (20 each, about a minute). Loot is ordinary "
                      "(0-3 objects, a few sleeping monsters)",
        "inner room": "a dark inner room: most likely a large room (dark ones are common), but pits and nests "
                      "(95 awake monsters) look the same and are never lit. Open it only ready to leave: "
                      "'goal searchroom {Y},{X}'",
        "orc pit": "an ORC PIT (95 awake orcs, archers inside, no loot): leave the level. Avoid zone set",
        "nest": "a NEST (jellies, molds, icky things; some breed; no loot): don't open it. Avoid zone set",
    }

    def structures_tick(self, now):
        w = self.w
        if now - self.struct_t < 2.0:
            return
        self.struct_t = now
        self.save_level_map(now)
        if not w.in_dungeon or not w.memory:
            return
        for Y, X, ev in structures.scan(w.memory):
            key = (w.level_t, (Y, X))
            st = self.structs.get(key)
            if st is None:
                # lit rooms come into view all at once (pits and nests never are)
                st = self.structs[key] = {"t": now, "lit": ev["ring_known"] >= 0.75 * ev["ring_total"],
                                          "kind": None, "sure": False}
            st["sure"] = st["sure"] or ev["sure"]
            kind = structures.classify(Y, X, ev, w.monsters, st["lit"])
            if kind == st["kind"] or (st["kind"] in ("orc pit", "nest") or "pit" in str(st["kind"])):
                continue                          # (a pit stays a pit when its orcs have left)
            st["kind"] = kind
            advice = self.ADVICE.get(kind, self.ADVICE["orc pit"]).format(Y=Y, X=X)
            where = f"{kind} centred {Y},{X} ({Y - 5}-{Y + 5}, {X - 12}-{X + 12})" + ("" if st["sure"] else ", likely")
            if "pit" in kind or kind == "nest" or kind == "inner room":
                # (a dark inner room too: pits look the same until they open, and its ring
                # is a one-wide corridor where they surround you: m24 at 600 ft, an orc pit)
                if not any(abs(y0 - Y) <= 1 and abs(x0 - X) <= 1
                           for y0, x0, _ in self.avoid_zones.get(w.level_t, [])):
                    for dx in (-7, 0, 7):
                        self.avoid_zones.setdefault(w.level_t, []).append((Y, X + dx, 6))
                if kind == "inner room":
                    self.notify("structure", f"{where}: {advice}. Avoid zone set on it and its ring (a pit looks "
                                             "the same from outside); `avoid clear` to go in", news=True)
                else:
                    self.notify("structure", f"{where}: {advice}")
            else:
                self.notify("structure", f"{where}: {advice}", news=True)

    def save_level_map(self, now):
        """Each dungeon level's remembered map, written when we leave it, to
        runs/pilot/<nick>/levels/ (only 11x31 crops were logged, so the
        recogniser couldn't be checked against real levels afterwards)."""
        w = self.w
        # the level this Pilot logged in on (None: in town): the previous Pilot's logout left it "static" on the
        # server, kept after we leave it (operations.md, Level persistence) -- Dive.FLED_HOLD's test-server edge case
        if self.first_level_t is None and w.depth is not None and w.level_t:
            self.first_level_t = w.level_t if w.in_dungeon else None
        # the arrival feeling, logged per level (the Advisor's structures memo: at <= 850 ft any pit, nest or
        # vault forces "special"; another feeling proves there is none)
        if w.in_dungeon and self.feeling_level != w.level_t and waited(w.level_t, 3):
            self.feeling_level = w.level_t
            fl = next((t for ts, t in w.messages if ts >= w.level_t - 0.5 and re.search(
                r"special about this level|feeling|Looks like any other level|Omens of death|murderous|"
                r"terribly dangerous|nervous|bad feeling|quiet, peaceful|safe|Luck is turning|lucky", t)), None)
            self.level_feeling = fl
            self.log("arrival_feeling", depth_ft=w.depth_ft, feeling=fl, arrived_by=w.arrived_by)
        snap = self.map_snap
        if snap and snap["level"] != w.level_t:
            try:
                d = os.path.join(self.rundir, "levels")
                os.makedirs(d, exist_ok=True)
                mem = snap["mem"]
                rows = ["".join(mem.get((y, x), " ") for x in range(MAX_WID)).rstrip() for y in range(MAX_HGT)]
                found = [f"{st['kind']} {Y},{X}" for (lv, (Y, X)), st in self.structs.items() if lv == snap["level"]]
                with open(os.path.join(d, time.strftime("%Y%m%d-%H%M%S", _lt(snap["t0"]))
                                       + f"-{snap['ft']}ft.txt"), "w") as f:
                    f.write(f"# {snap['ft']} ft, {time.strftime('%Y-%m-%d %H:%M:%S', _lt(snap['t0']))} - "
                            f"{time.strftime('%H:%M:%S', _lt(snap['t']))}; structures: "
                            f"{', '.join(found) or 'none'}; feeling: {snap.get('feeling') or 'none'}\n"
                            + "\n".join(rows) + "\n")
            except OSError:
                pass
            snap = None
        if w.in_dungeon and w.memory:
            self.map_snap = {"level": w.level_t, "mem": dict(w.memory), "ft": w.depth_ft,
                             "t0": snap["t0"] if snap else now, "t": now,
                             "feeling": self.level_feeling
                             if self.feeling_level == w.level_t else None}
        else:
            self.map_snap = None

    def structures_here(self):
        w = self.w
        return [(Y, X, st) for (lv, (Y, X)), st in self.structs.items() if lv == w.level_t and st["kind"]]

    def track_since(self):
        w, now = self.w, gnow()
        sn = self.since
        if sn is None:
            sn = self.since = {"t": now, "min_hp": None, "mons": {}, "uniques": set()}
        if w.hp[1] > 1 and (sn["min_hp"] is None or w.hp[0] < sn["min_hp"][0]):
            sn["min_hp"] = (w.hp[0], w.hp[1], now)
        counts = {}
        for *_, r in w.monsters:
            counts[r.name] = counts.get(r.name, 0) + 1
        for n, k in counts.items():
            sn["mons"][n] = max(sn["mons"].get(n, 0), k)
        sn["uniques"] |= {r.name for *_, r in w.monsters if "UNIQUE" in r.flags}
        exp = (w.ind.get("exp") or [0])[0]
        if exp != self.exp_seen:
            if self.exp_seen is not None and exp > self.exp_seen:
                self.exp_t = now
            self.exp_seen = exp

    WHY_KINDS = ("emergency", "emergency_loop", "stat_drained", "danger_seen", "band", "fight_going_badly",
                 "unseen_attacker", "thief", "drainer", "fearer", "unique_slain", "lost", "disenchanted")
    WHY_SKIP = ("move", "mons", "itemlist", "time_factor", "report", "audit_check", "audit", "state",
                "perception_gap", "options", "estimator")

    def why_info(self, args):
        """`why [HH:MM[:SS]]` (the Navigators, m40-m42: "why did the Pilot recall?"): what the Pilot saw and did around
        a moment -- by default the last escape, emergency or end of a trip -- from its decision log: HP over the window,
        the monsters in view and adjacent, and the timeline of attention events, actions, goals and escapes."""
        path = os.path.join(self.rundir, "decisions.jsonl")
        try:
            size = os.path.getsize(path)
            with open(path, "rb") as f:
                f.seek(max(0, size - 8_000_000))     # (~the last 8 hours)
                lines = f.read().decode("utf-8", "replace").splitlines()[1:]
        except OSError as e:
            return f"no decision log ({e})"
        recs = []
        for l in lines:
            try:
                recs.append(json.loads(l))
            except ValueError:
                pass
        if not recs:
            return "the decision log is empty"
        if args:
            m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", args[0])
            if not m:
                return "usage: why [HH:MM[:SS]] (today; default: the last escape, emergency or trip end)"
            lt = time.localtime()
            t = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, int(m.group(1)), int(m.group(2)),
                             int(m.group(3) or 0), 0, 0, -1))
        else:
            notable = [d for d in recs if d.get("kind") in ("escape", "plan_end", "goal_failed")
                       or (d.get("kind") == "attention" and d.get("what") in ("emergency", "emergency_loop"))]
            if not notable:
                return "nothing notable in the recent log: give a time (why HH:MM:SS)"
            t = notable[-1]["t"]
        win = [d for d in recs if t - 40 <= d.get("t", 0) <= t + 8]
        if not win:
            return f"nothing in the log around {time.strftime('%H:%M:%S', time.localtime(t))}"

        def hm(x):
            return time.strftime("%H:%M:%S", time.localtime(x))
        hp = [(d["t"], d["hp"]) for d in win if d.get("hp") and d["hp"][1]]
        lo = min(hp, key=lambda x: x[1][0]) if hp else None
        dft = next((d.get("depth") for d in reversed(win) if d.get("t", 0) <= t and d.get("depth") is not None), None)
        out = [f"Around {hm(t)} ({'town' if not dft else f'{dft * 50} ft'}), 40 s before to 8 s after:"]
        if hp:
            out.append(f"HP {hp[0][1][0]}/{hp[0][1][1]} at {hm(hp[0][0])} -> lowest {lo[1][0]} at {hm(lo[0])} -> "
                       f"{hp[-1][1][0]} at {hm(hp[-1][0])}")
        seen, adj = [], []
        for d in win:
            if d.get("kind") == "mons" and d.get("pos"):
                for y, x, n in d.get("monsters") or []:
                    if n not in seen:
                        seen.append(n)
                    if max(abs(y - d["pos"][0]), abs(x - d["pos"][1])) <= 1 and n not in adj:
                        adj.append(n)
        if seen:
            out.append("In view: " + ", ".join(seen[:12]) + (f"; adjacent at some point: {', '.join(adj[:8])}" if adj else ""))
        out.append("Timeline:")
        for d in win:
            k = d.get("kind")
            if k in self.WHY_SKIP or (k == "act" and str(d.get("cmd", "")).startswith(("walk", "custom . "))):
                continue
            if k == "attention":
                text = f"{d.get('what')}: {d.get('detail')}"
            elif k == "act":
                text = f"act{' [' + d['by'] + ']' if d.get('by') else ''}: {d.get('why') or d.get('cmd')}"
            elif k == "nav_cmd":
                if d.get("cmd") in ("status", "wait", "prep", "why", "gear", "gearcmp", "loadout", "pack", "say", "journal",
                                   "complain"):
                    continue
                text = f"{'ARCH' if d.get('role') == 'architect' else 'NAV'}> {d.get('cmd')} {' '.join(map(str, d.get('args') or []))}"
            elif k == "escape":
                text = f"ESCAPE ({d.get('escape')}): {d.get('trigger')}" + \
                    (f" -- adjacent {', '.join(d['adjacent'])}" if d.get("adjacent") else "")
            elif k in ("goal", "goal_done", "goal_failed"):
                text = f"{k}{' [' + d['by'] + ']' if d.get('by') else ''}: {d.get('goal') or ''} {d.get('detail') or ''}".strip()
            elif k in ("plan_end", "plan_start"):
                text = f"{k}: {d.get('plan')} -- {d.get('detail') or d.get('status') or ''}"
            else:
                text = f"{k}: " + str({x: v for x, v in d.items() if x not in ("t", "kind", "depth", "pos", "hp", "crop")})[:160]
            out.append(f"  {hm(d['t'])} {d['hp'][0] if d.get('hp') else '?'} HP  {text[:170]}")
        return "\n".join(out[:60])

    def prep_info(self):
        """`prep` (the user, 10-25: a planning step at a mission's start): everything a mission plan needs in one
        report -- the character, the gear review, what `plan town` would buy now, notable shop stock, where the XP
        has come from by depth, the XP-per-gold rate, standing orders, and the field notes to read."""
        w = self.w
        gold = w.ind.get("gold", [0])[0]
        out = ["PREP -- read this, then FIELD-NOTES.md, then plan the mission (town visit, trips, conditions).", ""]
        rep = self.compact(snapshot=True).split("\n")
        out += ["== Character"] + [l for l in rep[:6] if not l.startswith(("Here:", "Monsters:"))]
        out += ["", "== Gear review (`gear`)"] + self.gear_review().split("\n")
        try:
            buys, short = self.town_shopping(None, ())
            out += ["", "== `plan town` would buy now (by the prices last seen): " +
                    (", ".join(f"{n} {k} at the {self.STORE_LABEL.get(st, st)}" for _, k, st, n, _ in buys) or "nothing")
                    + ("; short: " + ", ".join(f"{n} {k}" for k, n in short) if short else "")]
        except Exception as e:                       # (a forecast problem must not hide the rest)
            out += ["", f"== `plan town` forecast unavailable ({e!r})"]
        notable = []
        now_wall = time.time()
        for st in (7, 6, 5):
            seen = self.stores_seen.get(st) or {}
            age = (now_wall - seen.get("t", now_wall)) / 60 if seen.get("t") else None
            for name, price in sorted((seen.get("prices") or {}).items(), key=lambda kv: -kv[1]):
                # (no mapping/detection devices on the test server: the user's no-crutch rule)
                if price <= max(0, gold - self.town_reserve()) and re.match(r"(potion|scroll|ring|amulet|staff|rod|wand) of",
                                                                              name) and price >= 150 and \
                        (self.live or not any(c.lower() in name for c in self.CRUTCH_DEVICES)):
                    notable.append(f"{name} {price} ({st}" + (f", seen {age:.0f} min ago" if age is not None else "") + ")")
        out += ["", "== Shop stock you could afford (Black Market 7, Magic 6, Alchemist 5; prices last seen): " +
                ("; ".join(notable[:12]) if notable else "nothing notable")]
        dep = self.rate_state().get("depth") or {}
        rows = sorted(((int(k), v[0], v[1] / 60) for k, v in dep.items() if v[1] >= 60), key=lambda r: r[0])
        out += ["", "== XP by depth (recent play): " + ("; ".join(
            f"{ft} ft {xp / mins:.0f} XP/min over {mins:.0f} min" for ft, xp, mins in rows) or "no record yet")
            + f"  [max_depth {self.orders.get('max_depth')}]"]
        r = self.xp_per_gold()
        out += [f"== XP per gold (recent play) {r}: 1000 gold is worth ~{1000 * r:.0f} XP of playing time"]
        st_ = [f"keep {', '.join(sorted(self.keep))}"] if self.keep else []
        st_ += [f"\"{x['text']}\" ({x['by']})" for x in self.standing]
        out += ["== Standing: " + ("; ".join(st_) or "none")]
        out += ["", "Then: `plan town [buy ...]`, `plan trip LO-HI until \"...\" then town`. Note your plan in the journal."]
        return "\n".join(out)

    # the Navigator's live line to the Architect (the user, m43: "the Navigator should be able to ask questions and
    # escalate issues to the Architect live during a mission. We don't want the Navigator to spam this though")
    ASK_GAP_S = 300            # one question every 5 minutes
    ASK_PER_HOUR = 4

    def ask_architect(self, text):
        text = text.strip()
        # `ask quiet TEXT` (the user, 10-28: the Navigator's quiet wait for "an extended conversation with the
        # Architect"): the question goes, and the Pilot waits somewhere quiet until the answer comes
        quiet = text.split()[:1] == ["quiet"]
        if quiet:
            text = text[len("quiet"):].strip()
        if not text:
            return {"ok": False, "error": "usage: ask [quiet] TEXT (a question or an escalation for the Architect)"}
        now = time.time()
        asks = [a for a in self.asks_sent if now - a < 3600]
        self.asks_sent = asks
        # (the file runs/pilot/NICK/ask_unlimited lifts the limits: the user, 10-26, for "The Architect's Vacation"
        # session, when the Architect answers live all session; delete it to restore them)
        unlimited = os.path.exists(os.path.join(self.rundir, "ask_unlimited"))
        if asks and now - asks[-1] < self.ASK_GAP_S and not unlimited:
            return {"ok": False, "error": f"one question every {self.ASK_GAP_S // 60} minutes: next after "
                                          f"{time.strftime('%H:%M', time.localtime(asks[-1] + self.ASK_GAP_S))}; "
                                          "`complain` for what isn't urgent"}
        if len(asks) >= self.ASK_PER_HOUR and not unlimited:
            return {"ok": False, "error": f"{self.ASK_PER_HOUR} questions in the last hour: use `complain` (read "
                                          "after the mission)"}
        asks.append(now)
        aid = self.ask_seq + 1
        self.ask_seq = aid
        rec = {"t": round(now, 1), "id": aid, "text": text, "depth_ft": self.w.depth_ft, "hp": list(self.w.hp[:2]),
               "goal": self.goal.describe() if self.goal else None}
        try:
            with open(os.path.join(self.rundir, "asks.jsonl"), "a") as f:
                f.write(json.dumps(rec) + "\n")
        except OSError as e:
            return {"ok": False, "error": f"couldn't send it ({e})"}
        self.log("nav_ask", id=aid, text=text, quiet=quiet)
        if quiet:
            out = self.request_goal(["quiet", "600"])
            if out.get("ok") and isinstance(self.goal, QuietWait):
                self.goal.wait_answer = aid
                self.goal.name = f"quiet wait for the Architect's answer (#{aid})"
                return {"ok": True, "text": f"asked the Architect (#{aid}); waiting somewhere quiet for the answer "
                                            "(10 minutes at most; a monster that moves or a hit ends it, and what it "
                                            "paused carries on)"}
            return {"ok": True, "text": f"asked the Architect (#{aid}); no quiet wait ({out.get('error', '?')}): carry "
                                        "on, the answer comes as ARCHITECT ANSWER in your reports"}
        return {"ok": True, "text": f"asked the Architect (#{aid}). The answer comes as ARCHITECT ANSWER in your "
                                    "reports (usually within a few minutes): carry on meanwhile, don't wait for it"}

    def answer_navigator(self, args):
        if self.req_role != "architect":
            return {"ok": False, "error": "answers come from the Architect"}
        if not args or not args[0].lstrip("#").isdigit():
            return {"ok": False, "error": "usage: answer ID TEXT"}
        aid, text = int(args[0].lstrip("#")), " ".join(args[1:])
        self.arch_answers.append((gnow(), aid, text))
        self.log("arch_answer", id=aid, text=text)
        self.notify("architect_answer", f"#{aid}: {text}")
        return {"ok": True, "text": f"answer #{aid} sent"}

    def price_info(self, what):
        """`price NAME|LETTER` (the user, m43: "so the Pilot knows item values, but you have no way to check?"): the
        Pilot's own valuation of a pack or worn item -- value, what a shop pays and which, the last price seen, and
        what the policy will do with it."""
        if not what:
            return "usage: price NAME|LETTER (a pack or worn item)"
        try:
            idx = self.item_index(what.strip().replace(" ", "_"))
        except ValueError as e:
            return str(e)
        it = next((i for i in self.w.items() + self.w.items(equip=True) if i["item"] == idx), None)
        if not it:
            return f"no item {what}"
        iv = self.iv(it["name"])
        cut = self.pay_cut(iv.tval)
        buyers = self.town_buyers(it) if not it.get("equip") else []
        n = max(1, iv.count or it.get("number", 1))
        # (the same type too: a Staff of Cure Light Wounds isn't the potion's 24 gold)
        word = (re.search(r"\b(Potion|Scroll|Staff|Staffs|Wand|Rod|Ring|Amulet)\b", it["name"]) or [None, ""])[1].lower()
        word = word[:-1] if word.endswith("s") and word != "staffs" else ("staff" if word == "staffs" else word)
        seen = [(st, p) for st, sv in self.stores_seen.items() for k, p in (sv.get("prices") or {}).items()
                if iv.kind and singular(iv.kind).lower() in k and (not word or k.startswith(word))]
        out = [f"{it['name']}: worth ~{iv.value} each ({'an estimate' if iv.estimate else 'known'}"
               + (f", P(irreplaceable) {iv.p_irreplaceable:.2f}" if iv.p_irreplaceable else "") + ")",
               f"a shop pays ~{iv.value * cut:.0f} each ({cut:.0%} of value)" + (f" at the "
               f"{self.STORE_LABEL.get(buyers[0], buyers[0])} ({buyers[0]})" if buyers else " -- no shop buys it")
               + (f"; x{n} = ~{iv.value * cut * n:.0f}" if n > 1 else "")]
        if seen:
            st, p = min(seen, key=lambda sp: sp[1])
            out.append(f"last seen for sale: {p} at the {self.STORE_LABEL.get(st, st)} ({st})")
        pol = "worn" if it.get("equip") else "kept (kit/kept/useful)" if not self.town_sell_count(it) else \
            "sold by plan town"
        out.append(f"the policy: {pol}")
        return "\n".join(out)

    def house_info(self, args):
        """`house` (state), `house buy [Y,X]` (the Architect: the smallest house, or the one with that door),
        `house deposit [KEEP]`, `house withdraw`."""
        st = self.house_state()
        sub = args[0] if args else ""
        if not sub:
            h = st.get("house")
            if not h:
                houses = town_houses(self.w.memory) if not self.w.in_dungeon else []
                tav = sorted(self.stash_places()["tavern"].values())
                return {"ok": True, "text": "no house owned" + (f"; the smallest on the map: {houses[0]['area']} "
                                                                   f"square(s), door {houses[0]['door']}" if houses else "")
                                            + (f"; tavern stash: {', '.join(tav)}" if tav else "")}
            held = sorted(self.stash_places()["house"].values())
            return {"ok": True, "text": f"house: door {h['door'][0]},{h['door'][1]}, bought {h.get('bought')} for "
                                        f"{h.get('price')}; {st.get('banked', 0)} gold banked (as of {st.get('t')}); "
                                        f"{self.w.ind.get('gold', [0])[0]} carried"
                                        + (f"; stash: {', '.join(held)}" if held else "")}
        if self.w.in_dungeon:
            return {"ok": False, "error": "the house is in town or the tile beside it"}
        if sub == "buy":
            if self.req_role != "architect":
                return {"ok": False, "error": "buying a house is the Architect's decision"}
            if st.get("house") and st.get("banked"):
                return {"ok": False, "error": f"the house at {st['house']['door']} holds {st['banked']} gold: "
                                              "`house withdraw` first"}
            houses = town_houses(self.w.memory)
            if len(args) > 1:
                m = re.match(r"^(\d+)[ ,](\d+)$", " ".join(args[1:3]))
                houses = [h for h in houses if m and h["door"] == (int(m.group(1)), int(m.group(2)))]
            if not houses:
                return {"ok": False, "error": "no such house on the town map (walls '#' round a door '0')"}
            hh = {k: (list(v) if isinstance(v, tuple) else v) for k, v in houses[0].items() if k != "inside"}
            if self.w.depth:
                # (a wilderness tile: remember how we came, the way back to it)
                cr = self.edge_cross
                if not cr or cr["depth"] != self.w.depth:
                    return {"ok": False, "error": "walk here from town (off the town's edge) before buying, so the "
                                                  "Pilot knows the way"}
                hh.update(depth=self.w.depth, cross=cr)
            g = HouseBank("buy", house=hh)
        elif sub in ("deposit", "withdraw"):
            if not st.get("house"):
                return {"ok": False, "error": "no house owned"}
            keep = int(args[1]) if sub == "deposit" and len(args) > 1 and args[1].isdigit() else None
            g = HouseBank(sub, keep=keep)
        else:
            return {"ok": False, "error": "usage: house [buy [Y,X] | deposit [KEEP] | withdraw]"}
        g.by_navigator = self.req_role != "architect"
        self.set_goal(g)
        return {"ok": True, "goal": g.describe()}



# --------------------------------------------------------------------------
# run as a script (`python3 pilot.py --nick ...`: restart.sh, hotswap.sh, charsave.sh): the process lives in daemon.py.
# This file is then __main__, and daemon's `import pilot` would load it a second time, with a second set of the
# classes; naming this module `pilot` first makes that import return it, so the program runs one copy.
# --------------------------------------------------------------------------

if __name__ == "__main__":
    sys.modules["pilot"] = sys.modules["__main__"]
    import daemon
    daemon.main()
