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
import json
import os
import queue
import random
import re
import socket
import sys
import threading
import time

from common import (HERE, VERSION, TV_FOOD, TV_FLASK, TV_LITE, DEFAULT_ORDERS, weapon_brand,
                    weapon_damage, kind_key, one_of)
from world import (World, gnow, set_time_factor, time_factor, model_factor, wall_of, wall_since, waited,  # noqa: E402
                   ghold, light_fuel, set_fast_ok, measured_rate, _lt, frozen)
import structures                                # noqa: E402
from stomach import Stomach                      # noqa: E402
from report import ReportMixin                   # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "observe"))
import shopmath                                  # noqa: E402
from mover import Mover, MAX_HGT, MAX_WID, plan as mover_plan   # noqa: E402
from goals import (Goal, Wait, Explore, Dive, Search, Hunt, Reprieve,  # noqa: E402
                   WalkAway, Flee, Recall, Recover, QuietWait)
from town_goals import (EDGE_DIR, edge_of, Town, Shop, StashDeposit, StashFetch,       # noqa: E402
                        town_houses, HouseBank, TownKit)
from plan import TripPlan, split_specs           # noqa: E402
from gear import GearMixin, shadow_agree         # noqa: E402
from items import (ItemsMixin, PY_FOOD_MAX, ADJ_STR_BLOW, ADJ_DEX_BLOW, ADJ_STR_HOLD, BLOWS_TABLE,  # noqa: E402
                   WARRIOR, TV_WEAPONS, stat_index, weapon_blows, type_word)
from town import TownMixin                       # noqa: E402
from combat import CombatMixin, CURE_POTIONS, HEALS, choke_tier, heal_of, STATUS_CURES   # noqa: E402
from commands import CommandsMixin   # noqa: E402
# (not named in this file: kept as P.Goal, P.shadow_agree, P.weapon_damage, ... for the tools)
REEXPORTED = (Goal, EDGE_DIR, StashDeposit, StashFetch, weapon_brand, weapon_damage, kind_key, shadow_agree,
              PY_FOOD_MAX, ADJ_STR_BLOW, ADJ_DEX_BLOW, ADJ_STR_HOLD, BLOWS_TABLE, WARRIOR, TV_WEAPONS, stat_index,
              weapon_blows, type_word, TV_FLASK, TV_FOOD, CURE_POTIONS, HEALS, choke_tier, heal_of, STATUS_CURES,
              VERSION, TV_LITE, Wait, Flee, QuietWait, town_houses, split_specs)

SHOP_CUT = shopmath.SHOP_CUT   # what a shop pays Dive04 of an item's value at CHR 3 (34-43%; Black Market 10%)


# Items whose use the pilot verifies and resends (not unknown scrolls: a
# resend could read a second one)
USE_VERIFY = ("Phase Door", "Word of Recall", "Teleport", "Cure Light Wounds", "Cure Serious Wounds",
              "Cure Critical Wounds", "Healing", "Boldness", "Heroism", "Berserk", "Cure Poison",
              "Neutralize Poison")


class Attention(Exception):
    pass


# --------------------------------------------------------------------------

class Pilot(ReportMixin, GearMixin, ItemsMixin, TownMixin, CombatMixin, CommandsMixin):
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
            # (2.50.0, the user: the items the house keeps -- lower-case name parts, as keep.json)
            self.store_list = set(json.load(open(os.path.join(rundir, "store.json"))))
        except (OSError, ValueError):
            self.store_list = set()
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
            self.stomach.from_json(json.load(open(os.path.join(rundir, "stomach.json"))))
        except (OSError, ValueError):
            pass
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
        self.store_list = set()        # store.json (2.50.0: the user's store list, `store`)
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
        self.far_wanted = {}                  # (level, glyph) -> potions/scrolls worth a far fetch (2.51.0, loot_step)
        self.zone_pass = set()                # (level, Y, X): structures whose ring paths may cross (`avoid pass`, 2.53.0)
        self.zone_wait = None                 # a hold for the Navigator's word on a blocking avoid zone (zone_hold)
        self.queued = None                    # a plan/goal the Navigator sent while plan town ran (2.53.0)
        self.drop_fails, self.drop_told = {}, set()   # stash drops that didn't happen, this visit (drop_failed)
        self.artifact_told = set()            # artifacts told "kept in the pack: can't be stored" (town_rule)
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
        self.first_level_t = False     # the level we logged in on (save_level_map); None: logged in in town; False: not yet seen
        self.fetching = None           # StashFetch / HouseBank: the item being fetched
        # commands sent
        self.item_cmd_t = 0.0          # the last item command (cmd holds the next until the pack is back)
        self.act_walls = collections.deque(maxlen=50)   # wall clock of each command (shadow_results)
        self.escape_read_t, self.escape_from = -99.0, (None, None)   # the last escape read (escape_line)
        self.last_escape = None        # (log_escape)
        self.last_goal_order = None    # (t, goal, role) of the last `goal` request (plan_end's "who recalled")
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
        self.engage_disen = {}         # (level, race) -> the disen_* log fields of its hunt check (engage_tick)
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
        # the stomach tracker (2.49.0, stomach.py): the food held, calibrated by the hunger crossings; saved in
        # rundir/stomach.json for a restart
        self.stomach = Stomach(self.TURNS_PER_DMIN)
        self.stomach_saved_t = 0.0
        self.edge_cross, self.surface_last = None, None   # note_edge_cross
        self.trapdoor = None           # (watch_traps)
        self.recall_restored, self.recall_saved = False, None   # recall_memory (recall.json)
        # gains and rates
        self.gold_last = self.xp_last = None   # the last tick's gold and exp (None: none seen yet)
        self.gold_found = self.gold_sold = self.gold_stolen = self.xp_gained = 0
        # (2.50.0: fresh finds stored in the house count as income; a credited one withdrawn and sold is debited)
        self.gold_stored = self.gold_debited = 0
        self.was_in_dungeon = None     # (note_trip_start: leaving town for the dungeon)
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
        self.last_hunt = {}            # hunt_refusal's last numbers (race, turns, loss, disen): the hunt log fields
        # caches: the rulebook's tables and the files read on first use (None: not read yet)
        self._uk = self._drops = self._ego_flags = self._fight_rows = self._sim = self._stock = None
        self._town_books = self._house = None
        self._pay_cache, self._sim_cache, self.gear_eval_cache = {}, {}, {}
        self._backup_cache = None      # stash_backups: (key, result) -- 2.50.0
        self._acq = None               # acquired.json (acq_state): pickups, the trip start, pending credits -- 2.50.0
        self.to_inscribe = []          # finds to mark with the mission's label (inscribe_finds) -- 2.50.0
        self.stash_to_sell = set()     # bare names fetched from the stash to be sold (review_hold lets them go) -- 2.51.0
        self.inscribe_t = 0.0

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
        self.stomach_sent(line)              # (a meal: the tracker waits for the pack to show it eaten)
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
            m = re.match(r"You sold (.+?) for (\d+) gold", t)
            if m:
                self.gold_sold += int(m.group(2))
                self.stash_credit_sold(m.group(1), int(m.group(2)))    # (2.50.0: a credited stored find, sold)
            # (2.50.0: what we pick up in the dungeon, with the mission it was found in -- a stored find is fresh
            # income; not a purchase or anything taken in town, nor a stash item being fetched back)
            m = re.match(r"You have (.+) \([a-w]\)\.$", t)
            if m and w.in_dungeon and not w.store and not (self.fetching and self.fetching in m.group(1)):
                self.note_acquired(m.group(1))
            m = re.match(r"You are (?:wielding|wearing) (.+) \(.\)\.$", t)
            if m:
                self.stash_credit_worn(m.group(1))
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
        if w.in_dungeon and self.was_in_dungeon is False:
            self.note_trip_start()          # (2.50.0: a find stored with no mission running is fresh since here)
        self.was_in_dungeon = bool(w.in_dungeon)
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
        # (2.50.0: + fresh finds stored, - credited ones sold later: the scorecard's adjusted gold)
        cur = (self.xp_gained, self.gold_found + self.gold_sold + self.gold_stored - self.gold_debited)
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
        safe = self.dead or not near and w.hp_frac >= 0.7 and not w.store and \
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
        self.stomach_tick(now)
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
                # (2.51.0, the user after m62: a Potion of Speed lay in view 3 minutes at 750 ft, a Scroll of
                # Teleportation 6 at 800 ft -- potions and scrolls the kit uses or worth 200+ are fetched too)
                far = self.far_fetch_worth(name) if line.strip()[:1] in "!?" else None
                if (far or re.search(r"\b(Wand|Staff|Rod|Ring|Amulet)\b|\{(excellent|special)", name)) and \
                        not self.is_junk(name) and (w.level_t, name) not in self.far_seen:
                    self.far_seen.add((w.level_t, name))
                    if far:
                        self.far_wanted.setdefault((w.level_t, line.strip()[:1]), set()).add(name)
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
            # devices and jewellery this close: the loot step fetches them once it's clear (m29: nobody did); 2.51.0:
            # kit and valuable potions and scrolls too (far_wanted)
            if lr and self.orders.get("pickup") == "all" and \
                    (glyph in self.VALUABLE_GLYPHS or name in self.far_wanted.get((lt, glyph), ())) and sq and \
                    w.dist(sq[0]) <= self.LOOT_VALUABLE_R:
                self.notify("interesting_item", f"{name} seen on this level at {where}: fetching it once the "
                                                 "area is clear", news=True)
                continue
            if not self.plan:
                self.item_hold_until = now + 20   # (a dive pauses so you can fetch it)
            self.notify("interesting_item", f"{name} seen on this level (devices and jewellery sell for 50-700 once "
                                             f"known): a '{glyph}' at {where}; `goal fetch Y,X`"
                                             + ("" if self.plan else ". A dive pauses 20 s for it"))
        self.report_losses()

    # (what attacks destroy pack items: the message just before "...was destroyed!")
    LOSS_CAUSE_RE = re.compile(r"\b(breathes|casts|fires|spits|hurls|shoots|touches|bites|hits|claws|stings|crushes|"
                               r"engulfs|explodes|burns|freezes|shocks|corrodes|gazes|You are (?:hit|enveloped))", re.I)

    def report_losses(self):
        """`lost` news for what went from the pack or purse behind our back (World.losses). 2.56.0 (the Navigator after
        m65): an item destroyed by an attack names what, how many ("one of" / "some of" / "all of" / the only one, as
        the server says, spells1.c inven_damage) and, when the message before it shows one, by what."""
        w = self.w
        while w.losses:
            t, text = w.losses.pop(0)
            m = re.match(r"(One of y|Some of y|All of y|Y)our (.+?) \(.\) (?:was|were) destroyed!", text)
            if m:
                how = {"One of y": "one of", "Some of y": "some of", "All of y": "all of", "Y": "the only"}[m.group(1)]
                cause = next((x for ts, x in reversed(list(w.messages)) if t - 3 <= ts <= t and x != text
                              and "destroyed!" not in x and self.LOSS_CAUSE_RE.search(x)), None)
                text = f"destroyed: {how} {m.group(2)}" + (f" -- by \"{cause}\"" if cause else "") + f" ({text})"
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
        # (2.53.0, `avoid pass`: a structure's ring corridor and its surroundings may be crossed on this level --
        # never its inner block, the room itself)
        for lt, Y, X in self.zone_pass:
            if lt == w.level_t:
                zone -= {(y, x) for y in range(Y - 6, Y + 7) for x in range(X - 13, X + 14)}
                zone |= {(y, x) for y in range(Y - 3, Y + 4) for x in range(X - 10, X + 11)}
        w.avoid_inside = w.pos in zone
        w.avoid_zone = zone - {w.pos}

    # (2.53.0, the user after m63: "When an avoid zone blocks the Pilot's path, but the Navigator has time to evaluate
    # the situation, allow it to decide if it should path through or not." m63 10:34: a dark inner room's zone covered
    # its ring and the only '<' at max_depth; three "stairs known but unreachable" and the trip recalled.) 90 s: a
    # Navigator turn takes 20-60 s from the wait report, so one or two turns to answer; the trip's own clocks (the
    # 5-minute leave limit) don't count the hold
    ZONE_WAIT_S = 90

    def zone_blocks(self, tiles):
        """When these tiles (stairs, a frontier) are out of reach only because of an avoid zone: {len, to, through,
        structs} -- the path with the zones ignored, how many zone squares it crosses, the structures it passes --
        else None."""
        w = self.w
        tiles = [tuple(t) for t in tiles or ()]
        if not w.avoid_zone or not tiles or not w.pos:
            return None
        zone, inside = w.avoid_zone, w.avoid_inside
        try:
            w.avoid_zone, w.avoid_inside = set(), False
            path = mover_plan(w, tiles)
        finally:
            w.avoid_zone, w.avoid_inside = zone, inside
        if not path:
            return None
        structs = [(Y, X, st["kind"]) for Y, X, st in self.structures_here()
                   if any(Y - 6 <= y <= Y + 6 and X - 13 <= x <= X + 13 for y, x in path)]
        return {"len": len(path), "to": path[-1], "through": sum(1 for q in path if q in zone), "structs": structs}

    def zone_time(self):
        """Time for the Navigator to judge: no danger in view, not hit for 8 s, HP at least think_hp, no flee or
        recall under way."""
        w = self.w
        return not self.dangers() and gnow() - getattr(w, "last_hit_t", 0) > 8 and \
            w.hp_frac >= self.orders.get("think_hp", 0.65) and not isinstance(self.goal, (Flee, Recall, Recover)) \
            and not w.recall_pending

    def zone_hold(self, tiles, what):
        """True while the Pilot holds for the Navigator's word on an avoid zone that alone blocks `tiles` (`what`:
        "the '<' at 1,109", "the unexplored ground"): the first time, a `zone_blocks` alert names it and the choices;
        meanwhile the Pilot waits on a quiet spot (quiet_spot). No answer in ZONE_WAIT_S, or no time (danger, a hit,
        low HP, a flee): False -- the caller goes on as before (marks the stairs bad; the trip recalls)."""
        w, now = self.w, gnow()
        h = self.zone_wait
        if h and h["level"] != w.level_t:
            h = self.zone_wait = None
        if h and h.get("end"):
            return False
        if not self.zone_time():
            if h:
                h["end"] = now
                self.notify("tactic", f"zone hold ended: no time to wait any more ({what}): as before", news=True)
            return False
        if h is None:
            blk = self.zone_blocks(tiles)
            if not blk:
                return False
            h = self.zone_wait = {"level": w.level_t, "t0": now, "what": what, "end": None}
            st = "; ".join(f"{k} centred {Y},{X}" for Y, X, k in blk["structs"]) or "an avoid zone"
            self.notify("zone_blocks", f"{what} can't be reached without crossing {st} (the path through: "
                                       f"{blk['len']} steps, {blk['through']} in the zone). Holding on a quiet "
                                       f"spot for your word ({self.ZONE_WAIT_S} s): `avoid pass` (paths may cross "
                                       "its ring corridor on this level, never the room inside) or `avoid clear` to "
                                       "go through; `goal recall` or `goal leave` to leave it. No answer: as before "
                                       "(the trip recalls)", fields={"to": list(blk["to"]), "len": blk["len"]})
            self.log("zone_hold", what=what, to=list(blk["to"]), len=blk["len"], structs=blk["structs"])
            return True
        if now - h["t0"] > self.ZONE_WAIT_S:
            h["end"] = now
            self.notify("tactic", f"no word on the avoid zone in {self.ZONE_WAIT_S} s: {what} stays out of reach "
                                  "(as before)", news=True)
            return False
        # (on a quiet spot meanwhile: the quiet-wait machinery's choice)
        spot = self.quiet_spot()
        if spot and w.pos != spot and not self.mover.active:
            self.mover.go([spot])
        if self.mover.active:
            self.mover.tick()
        return True

    def zone_hold_spent(self, level_t):
        """Seconds held for the Navigator on this level (the trip's leave clocks leave them out)."""
        h = self.zone_wait
        if not h or h["level"] != level_t:
            return 0.0
        return min(h["end"] or gnow(), h["t0"] + self.ZONE_WAIT_S) - h["t0"]

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
        if self.queue_tick():             # (2.53.0: a plan or goal sent while plan town ran, now it's over)
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
        # (2.52.0, m63: `None` meant both "not yet" and "in town", so a Pilot started in town took the first dungeon
        # level as its login level -- the trip fled a band there and refused the stairs back for 300 s, then recalled)
        if self.first_level_t is False and w.depth is not None and w.level_t:
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



# --------------------------------------------------------------------------
# run as a script (`python3 pilot.py --nick ...`: restart.sh, hotswap.sh, charsave.sh): the process lives in daemon.py.
# This file is then __main__, and daemon's `import pilot` would load it a second time, with a second set of the
# classes; naming this module `pilot` first makes that import return it, so the program runs one copy.
# --------------------------------------------------------------------------

if __name__ == "__main__":
    sys.modules["pilot"] = sys.modules["__main__"]
    import daemon
    daemon.main()
