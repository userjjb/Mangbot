"""commands -- the Pilot's command side, as a mixin of Pilot (refactor-candidates E1 step 6 and E2; docs/commands.md):
the requests from the control socket (authenticate, handle_requests, service_notes) and the dispatcher, do_request,
which looks each command up in the command table (cmdtable.COMMANDS: its method, who may use it, where, how it
takes its arguments) and runs the checks in one place -- the role check, the dungeon check, the stale-order check,
the ghost check -- before calling the command's method: one per command (cmd_status, cmd_order, ...; the item
commands' item_action with parse_item_args, action_refusal and action_reply), or the query and request methods
here (request_goal, request_plan, request_trip, why_info, prep_info, price_info, house_info, monster_info,
drainers_info, user_note, ask_architect, answer_navigator) and elsewhere (gear_review). Also the order checks
(hunt_refusal, stale_order) and the item commands' helpers (item_index, pack_now). Every method stays Pilot's: it
reads and writes the Pilot's state through self.
"""
import csv
import json
import os
import queue
import re
import time

import structures
import geareval
from common import HERE, VERSION, TV_SCROLL, TV_LITE, flavour_key, bare_name, recall_level, singular
from world import gnow, waited, _lt
from goals import Wait, Goto, Explore, Dive, Search, Hunt, Flee, Recall, Resurrect, RestGoal, QuietWait
from town_goals import Town, TownFarm, Shop, town_houses, HouseBank, TownKit
from plan import TripPlan, split_specs
from cmdtable import (COMMANDS, ANY, DUNGEON_ITEMS, DEAD, POLLS, READ_ONLY, NO_MESSAGES,
                      DUNGEON_ITEM_CMDS)


class CommandsMixin:
    """Pilot's command side (`class Pilot(ReportMixin, GearMixin, ItemsMixin, TownMixin, CombatMixin,
    CommandsMixin)`: every name stays on Pilot)."""

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
            dc = self.last_hunt.get("disen") if self.last_hunt.get("race") == r.name else None
            d = self.drop_row(r)
            if d:
                out[-1] += (f"; a kill drops ~{float(d['e_gold']):.0f} gold and ~{float(d['e_items']):.1f} items worth "
                            f"~{float(d['e_item_value_cap']):.0f} (P(ego) {float(d['p_excellent_any']):.0%}, "
                            f"P(artifact) {float(d['p_artifact_any']):.0%})")
            if dc:
                # (2.45.0: what its UN_BONUS blows cost the worn gear, beside what the kill brings)
                out[-1] += "; " + self.disen_text(dc)
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

    # --- control requests (from the socket thread) ---------------------------

    READ_ONLY_CMDS = READ_ONLY         # (the viewer's queries: cmdtable's `viewer` entries)

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
            if req.get("cmd") not in POLLS:          # (cmdtable: logged=False)
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
            if self.unanswered and isinstance(out, dict) and req.get("cmd") not in NO_MESSAGES:
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
    # (cmdtable's where="town" entries; read and use with a target item are "town_target")
    DUNGEON_ITEM_CMDS = DUNGEON_ITEM_CMDS

    def do_request(self, req):
        """One request from the socket (handle_requests): look the command up in the table (cmdtable.COMMANDS),
        then, for anyone but the Architect, the role check (raw, stairs, goal goto, mission, answer), the dungeon
        check (the item commands for town) and the stale-order check (positional orders); then, for a ghost, the
        dead check; then the command's method (a ValueError/IndexError from a bad argument answers the usage). Unknown
        commands get past the role checks, then `unknown command` (a ghost too)."""
        c = req.get("cmd")
        args = req.get("args", [])
        self.req_role = req.get("role", "navigator")
        spec = COMMANDS.get(c)
        sub = next((v for k, v in spec.subs.items() if args[:1] == [k]), None) if spec and spec.subs else None
        if self.req_role != "architect":
            roles, refusal = ((sub["roles"], sub["refusal"]) if sub and "roles" in sub else (spec.roles, spec.refusal)) \
                if spec else (ANY, None)
            if roles != ANY and self.req_role not in roles:
                # (raw, stairs, goal goto: the new toolset, restructure step 2.6 -- movement is the Pilot's; the
                # Navigator gives intents, `goal leave` for the stairs, `goal fetch Y,X` for an item)
                return {"ok": False, "error": refusal.format(name=f"{c} {args[0]}" if sub else c)}
            if spec and self.w.in_dungeon and (spec.where == "town" or (spec.where == "town_target" and len(args) > 1
                                                                          and args[1] != "force")):  # identify reads
                return {"ok": False, "error": DUNGEON_ITEMS.format(name=c)}
            # (stale_order itself picks the positional orders -- goal goto/fetch/searchroom/hunt, avoid Y,X -- by
            # their arguments; it is asked for every request, unknown ones too, as before the table)
            held = self.stale_order(c, args)
            if held:
                self.log("order_held", cmd=c, args=args[:6], why=held)
                return {"ok": False, "error": f"order held: {held}"}
        if spec is None:            # (before the dead check: a ghost too gets `unknown command`, 2.45.0)
            return {"ok": False, "error": f"unknown command {c}"}
        if self.dead and not spec.dead and not (sub and sub.get("dead")):
            return {"ok": False, "error": DEAD}
        f = getattr(self, spec.method)
        how = spec.call
        try:
            out = f(args) if how == "args" else f() if how == "none" else f(" ".join(args)) if how == "text" else \
                f(" ".join(args).replace("_", " ")) if how == "name" else f(c, args) if how == "cmd" else f(args, req)
        except (ValueError, IndexError) as e:
            # a bad or missing argument (`search x`, `inscribe`, `goal explore radius=x`) answered the exception's
            # bare text: the usage now, the error kept for a real bug (2.45.0)
            self.log("request_error", cmd=c, args=args[:6], error=f"{type(e).__name__}: {e}")
            return {"ok": False, "error": f"usage: {spec.usage or c} ({type(e).__name__}: {e})"}
        return {"ok": True, "text": out} if spec.reply == "text" else out

    # --- the item commands (ACTIONS) ---------------------------------------------------------------------------

    def item_action(self, c, args):
        """wear takeoff quaff read eat fuel destroy drop inspect aim use zap: the words (parse_item_args), the item
        (by letter or name, resolved now), the checks (action_refusal), the action, and what it did (action_reply)."""
        key = self.ACTIONS[c]
        if not args:
            return {"ok": False, "error": f"usage: {c} ITEMLETTER"}
        args, forced_cmd = self.parse_item_args(c, args)
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
        refused = self.action_refusal(c, args, item, iname0, forced_cmd)
        if refused:
            return refused
        if c in ("destroy", "drop"):
            it0 = next((i for i in self.w.inven if i["item"] == item), None)
            if forced_cmd and self.req_role != "architect":
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
        return self.action_reply(c, args, iname0, it_before, pos_before, t0, before, pack)

    def parse_item_args(self, c, args):
        """An item command's words -> (args, forced): `destroy !NAME` (forced: over the value policy, counted in the
        Navigator's debt) loses its '!'; a name of several words is joined into one (`destroy Ration of Food` sent
        "of" as the count, m25: "You destroy no more Rations"): only a trailing number, `all` or `force` modifies."""
        forced_cmd = args[0].startswith("!") and len(args[0]) > 1
        if forced_cmd:
            args = [args[0][1:]] + list(args[1:])
        if c in ("destroy", "drop", "quaff", "eat", "fuel", "wear", "takeoff") and len(args) > 1:
            args, tail = list(args), []
            while len(args) > 1 and (args[-1].isdigit() or args[-1] in ("all", "force")):
                tail.insert(0, args.pop())
            args = [" ".join(args)] + tail
        return args, forced_cmd

    def action_refusal(self, c, args, item, iname0, forced_cmd):
        """Why not do this item command now, as a reply, or None: an escape read <3 s after the last, a second Word
        of Recall, a Word of Recall without @R in town (each unless `force`); unknown jewellery to wear (not the
        Architect's, unless `force`); a destroy/drop over the value policy (without `!`), or with `!` once the
        Navigator's overrides are revoked."""
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
            if forced_cmd and self.req_role != "architect" and not self.override_allowed():
                return {"ok": False, "error": f"not {c}ed: your freedom to override the Pilot's value policy "
                                              f"is suspended (debt {self.debt_total()} gold)"}
        return None

    def action_reply(self, c, args, iname0, it_before, pos_before, t0, before, pack):
        """What an item command did: `did` (the verb, the item, N -> M left, a move), the game's messages since t0,
        the pack, and a note when nothing changed (the game-state survey: never report as done what didn't
        happen) or an escape may still be landing."""
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

    # --- the other commands, one method each (cmdtable.COMMANDS names them) ------------------------------------

    def cmd_status(self, args, req):
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

    def cmd_mission(self, args):
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

    def cmd_keep(self, args):
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

    def cmd_standing(self, args):
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

    def cmd_react(self, args):
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

    def cmd_review(self, args):
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

    def cmd_debt(self):
        e = self.debt.get("entries", [])
        fe = self.debt.get("fight_entries", [])
        return {"ok": True, "text": f"Navigator debt: {self.debt_total()} gold of value lost over the Pilot's value "
                                    f"policy ({len(e)} entries)" + "".join(f"\n  {x['t']} {x['gold']}: {x['what']} "
                                                                            f"({x['why']})" for x in e[-8:]) +
                                    f"\nFight debt: {self.fight_debt_total()} HP lost in hunts ordered over the "
                                    f"Pilot's refusal that went wrong ({len(fe)} entries)" +
                                    "".join(f"\n  {x['t']} {x['hp']} HP: {x['what']} ({x['why']})" for x in fe[-8:])}

    def cmd_pack(self):
        return {"ok": True, "text": "Pack: " + "; ".join(f"{chr(97 + i['item'])}) {self.short(self.show(i))}"
                                                       for i in self.w.items())}

    def cmd_equip(self):
        return {"ok": True, "text": "Equipment (use these letters, capitals, in item commands): " + "; ".join(
            f"{chr(65 + k)}) {self.short(i['name'])}" for k, i in enumerate(self.w.items(equip=True)))
                + "\n" + self.gear_line()}

    def cmd_orders(self):
        return {"ok": True, "text": "Orders: " + ", ".join(f"{k}={v}" for k, v in self.orders.items())}

    def cmd_map(self, args):
        w = self.w
        r = int(args[0]) if args and args[0].isdigit() else 15
        if not (w.rows and w.pos):
            return {"ok": False, "error": "no map yet"}
        y0, x0 = w.pos
        ys = range(max(0, y0 - r), min(len(w.rows), y0 + r + 1))
        xa = max(0, x0 - r)
        return {"ok": True, "text": f"Map (@ {y0},{x0}; rows {ys[0]}-{ys[-1]}, cols {xa}-{x0 + r}):\n"
                + "\n".join(f"{y:2d}|" + w.rows[y][xa:x0 + r + 1].rstrip() for y in ys)}

    def cmd_view(self, args):
        # (the observer's viewer: a bigger map, no side effects)
        rows = int(args[0]) if args else 11
        cols = int(args[1]) if len(args) > 1 else 33
        return {"ok": True, "report": self.report(rows=rows, cols=cols, news_since=gnow() - 600)}

    def cmd_navview(self):
        # what the Navigator last saw (the user's "Navigator's view" panel)
        return {"ok": True, "t": self.nav_view[0], "events": self.nav_view[1], "report": self.nav_view[2]}

    def cmd_avoid(self, args):
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

    def cmd_viewmap(self, args):
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

    def cmd_journal(self, args):
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

    def cmd_gate(self, args):
        # the supply gate as a check: 'gate FEET [recall]'
        try:
            ft = int(args[0])
        except (IndexError, ValueError):
            return {"ok": False, "error": "usage: gate FEET [recall]"}
        gap = self.supply_gate(ft, "recall" in args[1:])
        return {"ok": True, "text": f"supplies for {ft} ft: " + ("OK" if not gap else "missing " + "; ".join(gap))}

    def cmd_complain(self, args):
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

    def cmd_say(self, args):
        # the Navigator answering the user (shown in the observer's viewer)
        text = " ".join(args)
        self.log("nav_say", text=text)
        self.unanswered = []                  # (answered)
        with open(os.path.join(self.rundir, "commentary.jsonl"), "a") as f:
            f.write(json.dumps({"t": round(time.time(), 3), "who": "navigator", "note": text}) + "\n")
        return {"ok": True, "text": "said"}

    def cmd_gearcmp(self, args):
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

    def cmd_loadout(self, args):
        # the loadout optimizer (geareval.optimize): changes across slots, e.g. a better weapon without Free
        # Action, with Free Action from a ring. `loadout shops` adds the shops' stock as last seen, within the gold
        # the essentials leave
        if self.w.in_dungeon and self.w.monsters:
            return {"ok": False, "error": "loadout runs ~2-5 s of simulation: not with monsters in view -- "
                                          "`goal quiet` first (it waits somewhere clear), then loadout"}
        return {"ok": True, "text": self.loadout_info(shops="shops" in args)}

    def cmd_stop(self):
        self.set_goal(None)
        self.stop_resting()
        if self.plan:
            self.log("plan_end", plan=self.plan.text, status="stopped")
            self.plan = None
            self.clear_plan_file()
            return {"ok": True, "note": "the trip plan is stopped too"}
        return {"ok": True}

    def cmd_order(self, args):
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

    def cmd_wearall(self):
        # Put on every weapon/armour/light in the pack whose slot is empty
        self.wear_queue = True
        return {"ok": True}

    def cmd_inscribe(self, args):
        try:
            item = self.item_index(args[0])
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        self.cmd(f"custom {{ item={item} entry={' '.join(args[1:])}", f"agent: inscribe {args}")
        return {"ok": True, "pack": self.pack_now()}

    def cmd_search(self, args):
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

    def cmd_disarm_open(self, c, args):
        # a chest (or door/trap) in direction DIR (5 = the square you stand on):
        # search first to find a chest's trap, disarm it, then open
        d = args[0] if args else "5"
        t0 = gnow()
        self.cmd(f"custom {'D' if c == 'disarm' else 'o'} dir={d}", f"agent: {c} {d}")
        self.c.collect(1.0)
        self.service_notes()
        said = [t for ts, t in self.w.messages if ts >= t0]
        return {"ok": True, "said": said[-4:], "pack": self.pack_now(0.3)}

    def cmd_pickup(self):
        self.cmd("custom ,", "agent: pickup")
        return {"ok": True}

    def cmd_stairs(self, args):
        self.take_stairs(args[0] if args else (self.w.standing_on or ">"))
        return {"ok": True}

    def cmd_option(self, args):
        self.c.send(f"option {args[0]} {args[1]}")
        return {"ok": True}

    def cmd_goalstate(self):
        g = self.goal
        st = {k: (repr(v)[:120]) for k, v in (vars(g).items() if g else [])}
        if g and getattr(g, "explore", None) is not None:
            st["explore_state"] = {k: repr(v)[:80] for k, v in vars(g.explore).items()}
        return {"ok": True, "goal": g.describe() if g else None, "state": st,
                "mover": {"active": self.mover.active, "path": len(self.mover.path),
                          "free": self.mover.free is not None, "running": self.mover.running is not None},
                "standing_on": self.w.standing_on, "busy": self.busy_until - gnow()}

    def cmd_options(self, args):
        opts = self.c.query("options", "options")["list"]
        return {"ok": True, "options": {k: v for k, v in opts.items() if not args or any(a in k for a in args)}}

    def cmd_dump(self):
        path = os.path.join(self.rundir, "world_dump.json")
        with open(path, "w") as f:
            json.dump({"pos": self.w.pos, "depth": self.w.depth, "rows": self.w.rows,
                       "memory": [[y, x, ch] for (y, x), ch in self.w.memory.items()],
                       "monsters": [[y, x, r.idx] for y, x, r in self.w.monsters]}, f)
        return {"ok": True, "file": path}

    def cmd_raw(self, args):
        self.cmd(" ".join(args), "agent: raw")
        return {"ok": True}

    def cmd_attention(self):
        with self.att_cond:
            evs, self.attention = self.attention, []
        return {"ok": True, "events": evs}

    def cmd_quit(self):
        self.running = False
        return {"ok": True}

    def cmd_park(self):
        # Log out at the next safe moment (for a Pilot update): the goal is
        # dropped now, the logout waits until nothing is close and HP is OK
        if not isinstance(self.goal, Recall):
            self.set_goal(None)       # a pending recall is allowed to finish first
        self.parking = gnow()
        return {"ok": True, "note": "will log out when safe"}

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
        self.last_hunt = {}
        if not race:
            return None, "no monster by that name in this game's data"
        self.last_hunt = {"race": race.name}
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
        # the enchantment its UN_BONUS blows (or disenchantment breath) take on average (2.45.0, the Advisor's Khim
        # memo): shown and logged; a refusal (2.45.1, the user) only when it is more than the kill brings -- the
        # last check, below the HP ones
        try:
            dc = self.disenchant_cost(race, turns)
        except Exception as e:             # (the valuation must not break the check)
            self.log("note", text=f"disenchant_cost failed: {e!r}")
            dc = None
        self.last_hunt = {"race": race.name, "turns": round(turns, 1), "loss_mean": round(taken),
                          "loss_p90": round(worst), "by": "fight_sim" if sim else "estimate", "disen": dc}
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
        if dc and dc.get("gold", 0) > 0 and not dc.get("resisted"):
            # (2.45.1, the user: the enchantment lost against what a kill brings -- the drop's expected value and
            # its XP at our recent XP per gold; the server gives exp * level / clvl)
            d = self.drop_row(race)
            drop = float(d["e_gold"]) + float(d["e_item_value_cap"]) if d else 0.0
            xpg = self.xp_per_gold()
            xp = getattr(race, "exp", 0) * race.level / max(1, w.clvl or 1)
            worth = drop + (xp / xpg if xpg > 0 else 0.0)
            self.last_hunt.update(kill_worth=round(worth), kill_xp=round(xp))
            if dc["gold"] > worth:
                return (f"{race.name}'s disenchanting attacks would cost ~{dc['gold']:.0f} gold of enchantment on "
                        f"average, more than a kill brings (~{drop:.0f} in drops + {xp:.0f} XP ~ {worth:.0f} gold at "
                        f"{xpg} XP per gold): fight it with resist disenchantment, or leave it ({info})", info)
        return None, info

    def hunt_fields(self, disen_only=False):
        """hunt_refusal's last numbers as log fields: est_turns, est_loss, est_loss_p90, est_by (fight_sim |
        estimate), race; and for a disenchanter disen_hits, disen_n, disen_gold, disen_resisted (disenchant_cost).
        disen_only: the disen_* fields alone (none for other monsters)."""
        h, out = self.last_hunt or {}, {}
        if not disen_only and "turns" in h:
            out = {"race": h["race"], "est_turns": h["turns"], "est_loss": h["loss_mean"],
                   "est_loss_p90": h["loss_p90"], "est_by": h["by"]}
        dc = h.get("disen")
        if dc:
            out.update(disen_hits=dc["hits"], disen_n=dc["n"], disen_gold=dc["gold"], disen_resisted=dc["resisted"])
        return out

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
            dfields = self.hunt_fields(disen_only=True)
            if why and self.req_role != "architect" and not force:
                self.log("order_refused", order=f"hunt {target}", why=why, **dfields)
                return {"ok": False, "error": f"hunt refused: {why}. `goal hunt !NAME` overrides; if the fight goes "
                                              "wrong, the HP it costs goes into your fight debt"}
            if why and force and self.req_role != "architect" and not self.override_allowed("hunt"):
                return {"ok": False, "error": f"hunt refused: {why}. Your freedom to override the Pilot's fight "
                                              f"checks is suspended (fight debt {self.fight_debt_total()} HP)"}
            g = Hunt(target)
            dc = self.last_hunt.get("disen")
            g.estimate = info + "; " + self.disen_text(dc) if info and dc else info
            if why and force and self.req_role != "architect":
                # an override: judged when the hunt ends (the user, 2026-10-23: a separate debt)
                w = self.w
                g.overridden = {"why": why, "hp0": w.hp[0], "hp_min": w.hp[0], "t0": gnow(),
                                "emerg0": len(self.emerg_times)}
                self.log("hunt_override", target=target, why=why, hp=w.hp[0], **dfields)
            # (2.45.0) every hunt taken, with the check's numbers, so missions can set them against the outcome
            self.log("hunt", target=target, by=self.req_role, refused=bool(why), overridden=g.overridden is not None,
                     **self.hunt_fields())
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
        # (the Architect's only: cmdtable's roles=ARCH, checked in do_request)
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
