"""report -- the Pilot's status reports, as a mixin of Pilot (refactor-candidates E1; docs/pilot-core.md, The status
report): compact() (`status` and the wait report), compact_changes(), report() (`status full`), numbered(), and the lines
they're built from (belief, since/progress, movement, supplies, structures, the escape marker) with the formatters they
share (D12). The methods stay Pilot's: they read and write the Pilot's state through self.
"""
import re
import time

import structures
from common import VERSION, TV_SCROLL, TV_POTION, TV_FOOD, TV_FLASK, TV_LITE, DEFAULT_ORDERS, weapon_brand, \
    weapon_damage, plural
from world import gnow, light_turns, _lt, frozen


class ReportMixin:
    """Pilot's report methods (`class Pilot(ReportMixin)`: every name stays on Pilot)."""

    def escape_line(self):
        """The status header's escape marker (session 8: a staff's teleport showed "no change", then landed; a scroll
        read on top was refused, and nobody could tell which escape was still landing)."""
        t, (pos, name) = self.escape_read_t, self.escape_from
        age = gnow() - t
        if not name or age > 6:
            return ""
        # (m55: both staff uses failed confused -- "You failed to use the staff properly" -- and the line said LANDING)
        if any(ts >= t - 0.3 and t_.startswith(("You failed to use", "You have no charges", "You can't see",
                                                  "You are too confused")) for ts, t_ in self.w.messages):
            return f" · escape FAILED ({name}, {age:.0f} s ago: the game refused it)"
        if self.w.pos == pos and age <= 3:
            return f" · ESCAPE LANDING ({name}, {age:.0f} s ago: don't repeat it yet)"
        if self.w.pos != pos and pos and self.w.pos:
            return f" · escaped ({name}, {age:.0f} s ago: moved {self.w.dist(pos)} squares)"
        return ""

    def belief_lines(self):
        """The report's belief-state lines: threats out of view, the fight so far, rates,
        counts on this level, standing instructions."""
        w, now = self.w, gnow()
        out = []
        if w.in_dungeon:
            in_view = {r.name for *_, r in w.monsters}
            gone = sorted(((n, m) for n, m in self.mons_mem.items() if m["level"] == w.level_t and n not in in_view
                           and now - m["t"] < 120), key=lambda nm: (not nm[1]["unique"], not nm[1]["danger"],
                                                                   now - nm[1]["t"]))
            if gone:
                out.append("Out of view (this level, last 2 min): " + "; ".join(
                    f"{n}{' ×%d' % m['n'] if m['n'] > 1 else ''}"
                    + (" (UNIQUE)" if m["unique"] else "") + (" (DANGER)" if m["danger"] else "")
                    + f" {now - m['t']:.0f} s ago at {m['pos'][0]},{m['pos'][1]} ({w.dist(m['pos'])} away)"
                    for n, m in gone[:5]))
            wt = [x for x in self.weapon_table() if x[3]]
            per_hit = wt[0][2] / max(1, wt[0][1]) if wt else 0
            rows = self.fight_rows()
            fights = []
            for name in sorted(in_view):
                k = self.hits.get((w.level_t, name.lower()), 0)
                if not k:
                    continue
                race = next((r for *_, r in w.monsters if r.name == name), None)
                row = rows.get(getattr(race, "idx", None)) or {}
                hp = row.get("hp")
                fights.append(f"{name}: {plural(k, 'hit')}, ~{k * per_hit:.0f} dealt" + (f" of ~{hp} HP" if hp else ""))
            tr = w.ind.get("track") or [0, 0]
            if fights:
                out.append("Fight so far: " + "; ".join(fights) +
                           (f" (the tracked monster's health bar: {10 * tr[1]}%)" if len(tr) > 1 and tr[1] else ""))
        # rates: HP lost recently, XP and gold per 10 minutes
        hh = [(t, hp) for t, hp in getattr(w, "hp_hist", []) if now - t <= 10]
        bits = []
        if hh and hh[0][1] - w.hp[0] > 0.05 * max(1, w.hp[1]):
            bits.append(f"HP -{hh[0][1] - w.hp[0]} in the last {now - hh[0][0]:.0f} s")
        found = self.gold_found
        old = next((h for h in self.gain_hist if now - h[0] <= 600), None)
        if old and now - old[0] > 60:
            de = (w.ind.get("exp") or [0])[0] - old[1]
            dg = w.ind.get("gold", [0])[0] - old[2]
            bits.append(f"XP {de:+d}, gold found {found - old[3]:+d} (net {dg:+d}, with shopping) in the last "
                        f"{(now - old[0]) / 60:.0f} min")
        lb = self.level_base
        if w.in_dungeon and lb and lb[2] == w.level_t and now - lb[0] >= 60:
            de = (w.ind.get("exp") or [0])[0] - lb[1]
            bits.append(f"this level: XP {de:+d} in {(now - lb[0]) / 60:.0f} min ({de / ((now - lb[0]) / 60):.0f} a minute)")
        pl = self.plan
        if pl and getattr(pl, "xp0", None) is not None and now - pl.t0 >= 60:
            de = (w.ind.get("exp") or [0])[0] - pl.xp0
            bits.append(f"this trip: XP {de:+d} in {(now - pl.t0) / 60:.0f} min ({de / ((now - pl.t0) / 60):.0f} a minute)")
        mb = self.mission_base
        if mb and self.mission_label:
            bits.append(f"this mission: XP {(w.ind.get('exp') or [0])[0] - mb[1]:+d}, gold found "
                        f"{found - (mb[3] if len(mb) > 3 else 0):+d} (net {w.ind.get('gold', [0])[0] - mb[2]:+d}) "
                        f"in {(now - mb[0]) / 60:.0f} min")
        if bits:
            out.append("Rates: " + "; ".join(bits))
        if w.in_dungeon:
            cnt = []
            if self.drains_here[0] == w.level_t and self.drains_here[1]:
                cnt.append(plural(self.drains_here[1], "drain"))
            if self.traps_here[0] == w.level_t and self.traps_here[1]:
                cnt.append(plural(self.traps_here[1], "trap") + " sprung")
            ns = sum(1 for lt, _ in self.searched if lt == w.level_t)
            if ns:
                cnt.append(f"{plural(ns, 'spot')} searched")
            ph = sum(1 for t in self.phase_hist if now - t < 90)
            em = sum(1 for t in self.emerg_times if now - t < 90)
            recent = ([plural(em, "emergency")] if em else []) + ([plural(ph, "Phase Door")] if ph else [])
            if cnt or recent:
                out.append("Counts: " + (f"this level {', '.join(cnt)}" if cnt else "") +
                           ("; " if cnt and recent else "") + (f"last 90 s {', '.join(recent)}" if recent else ""))
        st = [f"keep {', '.join(sorted(self.keep))}"] if self.keep else []
        if self.avoid_names:
            st.append(f"avoid {', '.join(sorted(self.avoid_names))}")
        if self.avoid_zones.get(w.level_t):
            st.append(f"{plural(len(self.avoid_zones[w.level_t]), 'avoid zone')} here")
        st += [f"\"{x['text']}\" ({x['by']})" for x in self.standing]
        st += [f"react {x['kind']} {x['arg']}" for x in self.rules()]
        nop = str(self.orders.get("nopickup", "")).strip()
        if nop:
            st.append(f"never pick up {nop}")
        if st:
            out.append("Standing: " + "; ".join(st))
        rv = self.review_state()["items"]
        if rv:
            # (m55: the Navigator missed that undecided items are sold after 2 town visits -- the Boots of Stability;
            # 2.63.0, the user: decided in the same town visit)
            def left(v):
                return "SOLD at the end of this town visit if undecided" if type(self.goal).__name__ == "TownKit" \
                    else "decided at the next town visit: sold there if undecided"
            out.append(f"Review ({len(rv)}, `review sell|keep|wear NAME`): " + "; ".join(
                f"{n} ({v['why']}; {left(v)})" for n, v in rv.items()))
        return out

    def numbered(self, rep, kind):
        """Number each report the Navigator gets and log it (id, kind, size), so
        every later command can say which report it answered and how old that
        was (the Advisor's starting-over memo: orders went stale on the way)."""
        self.report_seq += 1
        self.last_report = (self.report_seq, gnow())
        # what the report showed, for the stale-order check (step 2.4)
        self.report_state = {"level_t": self.w.level_t, "hp": self.w.hp_frac}
        self.log("report", id=self.report_seq, report_kind=kind, chars=len(rep))
        first, _, rest = rep.partition("\n")
        return f"{first} · r{self.report_seq}" + ("\n" + rest if rest else "")

    def since_lines(self, reset):
        sn = self.since
        if not sn:
            return []
        now = gnow()
        out = []
        lo = sn["min_hp"]
        mons = sorted(sn["mons"].items(), key=lambda kv: -kv[1])
        out.append(f"Since the last report ({now - sn['t']:.0f} s): lowest HP "
                   + (self.low_hp_text(lo) if lo else "?")
                   + "; monsters seen (most at once): " + (", ".join(f"{n} x{k}" for n, k in mons[:12]) or "none")
                   + (f"; UNIQUES: {', '.join(sorted(sn['uniques']))}" if sn["uniques"] else ""))
        xt = self.exp_t
        gt = now if self.goal_t is None else self.goal_t      # (a goal set without set_goal: for 0 s)
        w = self.w
        out.append("Progress: " + (f"last XP gain {self.ago(now - xt)} ago" if xt else "no XP gain seen yet")
                   + (f"; on this level {self.ago(now - w.level_t)}" if w.level_t else "")
                   + (f"; goal '{self.goal.describe()}' for {self.ago(now - gt)}"
                      if self.goal else ""))
        if reset:
            self.since_reset(now)
        return out

    # --- formatting shared by compact() and report() (refactor-candidates D12) ---------------------------------------
    def since_reset(self, now):
        """Start the next report's "since last" window (HP low, monsters and uniques seen)."""
        w = self.w
        self.since = {"t": now, "min_hp": (w.hp[0], w.hp[1], now) if w.hp[1] > 1 else None,
                      "mons": {}, "uniques": set()}

    @staticmethod
    def low_hp_text(lo):
        """since["min_hp"] (hp, max, t) -> '100/265 at 02:59:10'."""
        return f"{lo[0]}/{lo[1]} at {time.strftime('%H:%M:%S', _lt(lo[2]))}"

    @staticmethod
    def stat_text(v):
        """A stat as the sheet shows it: 3..18, then 18/01..18/100+."""
        return v if v <= 18 else '18/%02d' % (v - 18)

    def conditions(self):
        """(the status conditions on, the hunger word)."""
        w = self.w
        cond = [k for k in ("blind", "confused", "afraid", "poisoned", "cut", "stun") if w.flag(k)]
        hunger = {0: "Weak", 1: "Weak", 2: "Hungry", 3: "Fed", 4: "Full", 5: "Gorged"}.get(w.hunger, w.hunger)
        return cond, hunger

    def unanswered_line(self):
        return "USER MESSAGE(S) NOT YET ANSWERED (reply with say): " + " | ".join(
            f"{time.strftime('%H:%M:%S', _lt(t))} {m}" for t, m in self.unanswered)

    def news_line(self, head, news_since, n, now=None):
        """The news since `news_since` (else of the last 10 minutes), the last n, after `head`; None if none."""
        now = gnow() if now is None else now
        recent = [e for e in self.news if (e["t"] > news_since if news_since is not None
                                           else now - e["t"] < 600)][-n:]
        if not recent:
            return None
        return head + " | ".join(f"{time.strftime('%H:%M:%S', _lt(e['t']))} {e['what']}: {e['detail']}" for e in recent)

    def monster_groups(self):
        """{name: [(y, x, race)]} of the monsters in view."""
        seen = {}
        for y, x, r in self.w.monsters:
            seen.setdefault(r.name, []).append((y, x, r))
        return seen

    def weapon_text(self, n, b, d, eq, full=False):
        """A weapon_table row for the reports: compact (the short name), or full (report(): the whole name, slays,
        the longer hints)."""
        brand = weapon_brand(n)
        return (f"{'WIELDED ' if eq else ''}{n if full else self.short(n)} {b} blows ~{d:.0f}"
                + (f" (~{weapon_damage(n, b, brand[1]):.0f} vs {'monsters ' if full else ''}not resisting {brand[0]})"
                   if brand else "")
                + (" (+ x2-3 vs its slain race)" if full and re.search(r"\bof \*?Slay ", n) else "")
                + ((" (pluses unknown: identify it, it may be much better)" if full else " (pluses unknown: identify it)")
                   if re.search(r"\{(good|excellent|special|magical)", n) and not re.search(r"\([+-]\d+,", n) else ""))

    def structures_line(self, full=False):
        """'Structures: ...' (the inner rooms and vaults here, with a door seen or 'searched') in compact()'s wording,
        or report()'s (full); None outside the dungeon or with none."""
        w = self.w
        sts = self.structures_here() if w.in_dungeon else []
        v = (getattr(self, "vaults", None) or {}).get(w.level_t) if w.in_dungeon else None
        vtxt = (f"{v['kind']}" + (f" \"{v['name']}\"" if v.get("name") else "") +
                f" {v['box'][0]}-{v['box'][2]},{v['box'][1]}-{v['box'][3]}"
                + (f" ({len(v['traps'])} predicted traps)" if full and v.get("traps") else "")) if v else None
        if not sts:
            return f"Structures: {vtxt}" if vtxt else None

        def one(Y, X, st):
            door = self.room_door(Y, X)
            return (f"{st['kind']} {'centred ' if full else ''}{Y},{X}" + ("" if st["sure"] else " (likely)") +
                    (f"{' - door at ' if full else ', door '}{door[0]},{door[1]}" if door else
                     (" - searched" if full else ", searched")
                     if all((w.level_t, r) in self.searched for _, r in structures.door_spots(Y, X)) else ""))
        return "Structures: " + "; ".join([one(Y, X, st) for Y, X, st in sts] + ([vtxt] if vtxt else []))

    def movement_line(self, window=60, step=8):
        """Where we've been in the last minute, a point every ~8 s (the
        Navigator's wish: it couldn't see what the Pilot's moves had been)."""
        now = gnow()
        pts = [(t, p, d) for t, p, d in self.pos_hist if now - t <= window]
        if not pts:
            return None
        out, last_t, last_p = [], None, None
        for t, p, d in pts:
            if (last_t is None or t - last_t >= step) and p != last_p:
                out.append(f"{time.strftime('%H:%M:%S', _lt(t))} {p[0]},{p[1]}")
                last_t, last_p = t, p
        if pts[-1][1] != last_p:
            out.append(f"now {pts[-1][1][0]},{pts[-1][1][1]}")
        n = len({p for _, p, _ in pts})
        return f"Movement (last {window} s, {n} different squares): " + " -> ".join(out)

    @staticmethod
    def ago(secs):
        secs = int(max(0, secs))
        return f"{secs // 60}m{secs % 60:02d}s" if secs >= 60 else f"{secs}s"

    # ---- the compact report (what the Navigator reads after every wait) ----
    # The full report() ran to ~5 KB (the pack twice, every order, a 23 x 67 map
    # even in town); the Navigator read it 100+ times a mission. This one keeps
    # what decisions turn on and shows the rest only when it changes; `status
    # full` gives the old one (the user, 2026-10-22).
    CURE_ABBR = {"Cure Critical Wounds": "CCW", "Cure Serious Wounds": "CSW", "Cure Light Wounds": "CLW"}
    ESCAPE_ABBR = {"Phase Door": "Phase", "Word of Recall": "WoR", "Teleportation": "Tele",
                   "Teleport Level": "TeleLevel", "Deep Descent": "DeepDescent"}

    @staticmethod
    def short(name):
        """'5 Potions of Heroism {75% off}' -> '5 Potions of Heroism' ('a '/'an ' dropped)."""
        n = re.sub(r"\s*\{\d+% off\}", "", name)
        return re.sub(r"^(a|an) ", "", n)

    @staticmethod
    def kind_of(name):
        """'3 Potions of Cure Critical Wounds {25% off}' -> 'Cure Critical Wounds'."""
        m = re.search(r"(?:Potions?|Scrolls?|Rations?|Flasks?) of ([^{(]+)", name)
        return m.group(1).strip() if m else None

    def supply_lines(self):
        w = self.w
        cures, esc, other, devices = {}, {}, {}, []
        food = flasks = 0
        for i in w.items():
            n, k = i["number"], self.kind_of(i["name"])
            if i["tval"] in (TV_POTION, TV_SCROLL) and k:
                if k in self.CURE_ABBR:
                    cures[self.CURE_ABBR[k]] = cures.get(self.CURE_ABBR[k], 0) + n
                elif k in self.ESCAPE_ABBR:
                    esc[self.ESCAPE_ABBR[k]] = esc.get(self.ESCAPE_ABBR[k], 0) + n
                elif k == "Satisfy Hunger":
                    food += n
                else:
                    other[k] = other.get(k, 0) + n
            elif i["tval"] == TV_FOOD and "Mushroom" not in i["name"]:
                food += n
            elif i["tval"] == TV_FLASK:
                flasks += n
            elif i["tval"] in (55, 65, 66):
                f = self.flavour_of(i)
                devices.append(self.short(i["name"]) + (f" (= {f['kind']})" if f else ""))
        for d in devices:
            m = re.match(r"(Staff|Rod|Wand) of Cure Light Wounds \((\d+) charges\)", d)
            if m:
                cures["staff CLW"] = int(m.group(2))
        worn_lite = next((i for i in w.items(equip=True) if i["tval"] == TV_LITE), None)
        lite = worn_lite or self.best_light()
        lt = light_turns(lite["name"]) if lite else None
        # (m40: "Light 408" while no light was worn and the fuller lantern sat in the pack)
        light = ("none" if not lite else (str(lt) if lt is not None else "permanent")) + \
            ("" if worn_lite or not lite else " (off, in the pack)") + \
            (f" +{flasks} flask{'s' if flasks != 1 else ''}" if flasks else "")
        out = ["Cures " + (" · ".join(f"{k} {v}" for k, v in cures.items()) or "NONE")
               + " | Escapes " + " · ".join(f"{k} {esc.get(k, 0)}" for k in ("Phase", "WoR"))
               + "".join(f" · {k} {v}" for k, v in esc.items() if k not in ("Phase", "WoR"))
               + f" | Food {food} | Light {light}" + (f" ({self.supply_text()})" if w.in_dungeon or not w.depth else "")
               + (f" | RECALL PENDING ({gnow() - w.recall_pending_t:.0f} s; 8-23 s)" if w.recall_pending else "")]
        extra = [f"{k} {v}" for k, v in other.items()] + [d for d in devices if "Cure Light Wounds" not in d]
        if extra:
            out.append("Also: " + " · ".join(extra))
        return out

    def compact(self, news_since=None, map_r=9, snapshot=False):
        w, ind, now = self.w, self.w.ind, gnow()
        lines = []
        where = ("Town (" + {True: "day", False: "night", None: "day/night?"}[w.is_day()] + ")") if not w.depth \
            else f"{w.depth_ft} ft"
        lines.append(f"{ind.get('hist_name_', '?')} L{w.clvl} HP {w.hp[0]}/{w.hp[1]} · {where} · "
                     f"{ind.get('gold', [0])[0]}g" + (f" (+{self.banked()} banked)" if self.banked() else "")
                     + f" · max {self.orders.get('max_depth')}ft · "
                     f"{time.strftime('%H:%M:%S')} · goal: {self.goal.describe() if self.goal else 'none'}"
                     + (" · TIME FROZEN (test server: nothing moves until it's thawed)" if frozen() else "")
                     + self.escape_line())
        ml = self.mission_line() if hasattr(self, "mission_line") else None
        if ml:
            lines.append(ml)             # (2.61.0: the mission clock, frozen time not counted)
        if self.plan:
            lines.append("Plan: " + self.plan.describe(self))
        aa = [a for a in self.arch_answers if gnow() - a[0] < 600]
        if aa:
            lines.append("ARCHITECT ANSWER(S): " + " | ".join(f"#{i} {time.strftime('%H:%M:%S', _lt(t))} {m}"
                                                               for t, i, m in aa))
        if self.unanswered:
            lines.append(self.unanswered_line())
        drained = {n for n, (cur, top) in (self.seen_drained or {}).items() if cur < top}
        stats = " ".join(f"{s} {self.stat_text(v[0])}{'↓' if s in drained else ''}"
                         for s, v in zip(self.STAT_NAMES, (ind.get(f"stat{i}", [0]) for i in range(6))))
        cond, hunger = self.conditions()
        wt = self.weapon_table()
        wield = next(((n, b, d) for n, b, d, eq in wt if eq), None) if wt else None
        spd = int(ind.get("speed", [0])[0] or 0)
        lines.append(f"{stats} · {hunger}" + (f" · {', '.join(cond).upper()}" if cond else "")
                     + (" · resting" if w.resting else "") + (f" · speed {spd:+d}" if spd else "")
                     + (f" · {re.sub(r' [(].*', '', self.short(wield[0]))} {wield[1]} blows ~{wield[2]:.0f}"
                        if wield else ""))
        lines += self.supply_lines()
        here = (w.standing_on or "unknown (under @)") + \
            (f" (item: {w.floor})" if w.floor else "") + (f" (arrived by {w.arrived_by})" if w.arrived_by else "")
        stairs = sorted(w.find("<>"), key=w.dist)[:3]
        lines.append(f"Here: {here}" + (" | Stairs " + ", ".join(f"{w.memory[q]} {q[0]},{q[1]} ({w.dist(q)})"
                                                                  for q in stairs) if stairs else " | no stairs known"))
        if w.monsters:
            parts = []
            for n, v in sorted(self.monster_groups().items(), key=lambda kv: min(w.dist(m[:2]) for m in kv[1])):
                r = v[0][2]
                ds = sorted(w.dist(m[:2]) for m in v)
                zz = sum(1 for y, x, _ in v if self.is_asleep(y, x))
                why = self.danger_why(r)
                parts.append(f"{n}{' ×%d' % len(v) if len(v) > 1 else ''} (L{r.level}"
                             + (", UNIQUE" if "UNIQUE" in r.flags else "")
                             + f", {ds[0]}{'-%d' % ds[-1] if len(ds) > 1 and ds[-1] != ds[0] else ''} away"
                             + ((", asleep" if zz == len(v) else f", {zz} asleep") if zz else "")
                             + (f", DANGER: {why[:60]}" if why else "") + ")")
            lines.append("Monsters: " + "; ".join(parts))
        else:
            lines.append("Monsters: none")
        # items: the server's list (names) and the squares near us ($ grouped)
        names = [l.strip()[2:].strip() for l in (w.itemlist or [])[1:]]
        # (known junk left out: the user, 10-25 -- the Pilot destroys it when it passes over it at a quiet moment)
        names = [n for n in names if not self.is_junk(n)]
        sq = sorted((q for q in self.resolve_target("item") if w.memory.get(q, "?") not in "0123456789"),
                    key=w.dist)[:10] if w.pos else []          # (not shop and house doors)
        gold = [q for q in sq if w.memory.get(q) == "$"]
        rest = [q for q in sq if w.memory.get(q) != "$"][:6]
        gd = sorted(map(w.dist, gold))
        # (the nearest pile's square: m49's Navigator guessed one from the map for `goal fetch`)
        bits = ([f"$ ×{len(gold)} ({gd[0]}" + (f"-{gd[-1]}" if gd[-1] != gd[0] else "")
                 + f"; nearest {gold[0][0]},{gold[0][1]})"] if gold else []) + \
            [f"{w.memory.get(q, '?')} {q[0]},{q[1]} ({w.dist(q)})" for q in rest]
        if names or bits:
            lines.append("Items: " + (", ".join(names[:8]) or "-") + (" | near: " + ", ".join(bits) if bits else ""))
        # the map: outside town (dungeon and wilderness), a square crop (distance is the same in every
        # direction: radius 9 shows everything within 9 moves)
        if w.depth and w.rows and w.pos:
            y0, x0 = w.pos
            ys = range(max(0, y0 - map_r), min(len(w.rows), y0 + map_r + 1))
            xa, xb = max(0, x0 - map_r), x0 + map_r + 1
            lines.append(f"Map (@ {y0},{x0}; rows {ys[0]}-{ys[-1]}, cols {xa}-{xb - 1}):")
            lines += [f"{y:2d}|" + w.rows[y][xa:xb].rstrip() for y in ys]
        st_line = self.structures_line()
        if st_line:
            lines.append(st_line)
        lines += self.belief_lines()
        news = self.news_line("News: ", news_since, 8, now)
        if news:
            lines.append(news)
        if w.depth and (w.monsters or w.hp[0] < w.hp[1]):
            msgs = w.recent(10)[-6:]
            if msgs:
                lines.append("Msgs: " + " | ".join(msgs))
        sn = self.since
        if sn:
            lo = sn["min_hp"]
            mons = sorted(sn["mons"].items(), key=lambda kv: -kv[1])
            bits = []
            if lo and lo[0] < lo[1]:
                bits.append(f"low HP {self.low_hp_text(lo)}")
            if mons:
                bits.append("seen " + ", ".join(f"{n} ×{k}" if k > 1 else n for n, k in mons[:8]))
            if sn["uniques"]:
                bits.append("UNIQUES " + ", ".join(sorted(sn["uniques"])))
            if bits:
                lines.append(f"Since last ({self.ago(now - sn['t'])}): " + "; ".join(bits))
            if news_since is not None:
                self.since_reset(now)
        if w.depth:
            xt = self.exp_t
            gt = now if self.goal_t is None else self.goal_t      # (a goal set without set_goal: 0 s)
            lines.append("Progress: " + (f"XP {self.ago(now - xt)} ago" if xt else "no XP yet")
                         + (f" · level {self.ago(now - w.level_t)}" if w.level_t else "")
                         + (f" · goal {self.ago(now - gt)}" if self.goal else ""))
        lines += self.compact_changes(snapshot)
        return "\n".join(lines)

    def compact_changes(self, snapshot=False):
        """What changed since the Navigator's last report: equipment, the
        non-consumables in the pack (with letters), weapons, abilities, empty
        slots, changed orders, audit differences. All of it on an explicit
        `status` (snapshot) and the first time; a wait report gets changes only
        (90 of mission 22's 113 reports came with waits)."""
        w = self.w
        cons = (TV_POTION, TV_SCROLL, TV_FOOD, TV_FLASK)
        now = {
            "Equip": [f"{chr(65 + k)}) {self.short(i['name'])}" for k, i in enumerate(w.items(equip=True))],
            "Pack (not consumables)": [f"{chr(97 + i['item'])}) {self.short(self.show(i))}" for i in w.items()
                                       if i["tval"] not in cons and i["tval"] not in (55, 65, 66)],
            "Weapons": [self.weapon_text(n, b, d, eq)
                        for n, b, d, eq in self.weapon_table()],     # (always the wielded one: with
            # the others sold in town the list went empty and the report said "Weapons: none", m27/m29/m31)
            "Abilities": [k for k, v in (w.flags or {}).items() if v and k not in ("stealth", "search", "infra", "tunnel")],
            "Gear": [self.gear_line()[len("Gear: "):]],
            "Orders changed": [f"{k}={v}" for k, v in self.orders.items()
                               if k in DEFAULT_ORDERS and str(v) != str(DEFAULT_ORDERS[k])],
            "Audit differences": [f"{k} {n}" for k, n in self.audit_counts.items()],
        }
        prev = None if snapshot else self.compact_prev
        self.compact_prev = now
        # (a burning lantern's turns and a staff's charges change all the time:
        # not a change worth a line)
        def norm(v):
            return [re.sub(r"\(with \d+ turns of light\)|\(\d+ charges?\)", "", t).strip() for t in v]
        out = []
        for k, v in now.items():
            if prev is None:
                if v:
                    out.append(f"{k}: " + "; ".join(v))
                continue
            if norm(v) == norm(prev.get(k, [])):
                continue
            if k in ("Equip", "Pack (not consumables)"):
                # (both carry letters now, which shift: compare the names)
                strip = lambda t: norm([t.split(") ", 1)[-1]])[0]
                old = {strip(t) for t in prev.get(k, [])}
                new = {strip(t) for t in v}
                ch = [f"+{t}" for t in v if strip(t) not in old] + [f"-{t}" for t in sorted(old - new)]
                if ch:
                    out.append(f"{k} changed: " + "; ".join(ch))
            else:
                out.append(f"{k}: " + ("; ".join(v) or "none"))
        if prev is None and not self.compact_hinted:
            self.compact_hinted = True
            out.append("(this is the compact report: `status full` for everything; `pack`, `equip`, `orders`, "
                       "`map [R]` for one part)")
        return out

    def report(self, rows=11, cols=33, news_since=None):
        w = self.w
        ind = w.ind
        lines = []
        stats = " ".join(f"{s}:{self.stat_text(v[0])}"
                         for s, v in zip(("STR", "INT", "WIS", "DEX", "CON", "CHR"),
                                         (ind.get(f"stat{i}", [0]) for i in range(6))))
        lines.append(f"{ind.get('hist_name_', '?')} the {ind.get('race_', '?')} {ind.get('class_', '?')}, "
                     f"level {w.clvl}" + (f" (max {ind['level'][0]})" if len(ind.get('level', [])) > 1 and ind['level'][0] != w.clvl else "") + f", HP {w.hp[0]}/{w.hp[1]}, "
                     f"{('Town (' + {True: 'day', False: 'night', None: 'day/night?'}[w.is_day()] + ')') if not w.depth else str(w.depth_ft) + ' ft'}, gold {ind.get('gold', [0])[0]}, "
                     f"blows {ind.get('skills2', ['?'])[0]}, speed {ind.get('speed', [0])[0]}"
                     f" | now {time.strftime('%H:%M:%S')} | Pilot v{VERSION}")   # (the Navigator has no clock of its own)
        cond, hunger = self.conditions()
        lines.append(f"{stats}  | {hunger}" + (f" | {', '.join(cond)}" if cond else "")
                     + (" | resting" if w.resting else ""))
        # (after a login the map shows @ over whatever is there: mission 21 stood
        # on a '<' reported as floor/unknown)
        lines.append(f"Standing on: {w.standing_on or 'unknown (the map shows @ over it until you step off)'}"
                     f"{' (item: ' + w.floor + ')' if w.floor else ''}"
                     f"{' (arrived by ' + w.arrived_by + ')' if w.arrived_by else ''}"
                     f" | goal: {self.goal.describe() if self.goal else 'none (idle)'}")
        lines.append("Equipment: " + "; ".join(i["name"] for i in w.items(equip=True)))
        lines.append("Pack: " + "; ".join(f"{chr(97 + i['item'])}) {self.show(i)}" for i in w.items()))
        if w.rows and w.pos:
            y0, x0 = w.pos
            # Every row, numbered, and the column range: blank rows used to be
            # dropped, so line numbers didn't match rows (mission 13)
            lines.append(f"Map (you are @ at {y0},{x0}; columns {max(0, x0 - cols)}-{x0 + cols}; "
                         "each line starts with its row):")
            for y in range(max(0, y0 - rows), min(len(w.rows), y0 + rows + 1)):
                seg = w.rows[y][max(0, x0 - cols):x0 + cols + 1]
                lines.append(f"  {y:2d}|" + seg.rstrip())
        if w.monsters:
            lines.append("Monsters in view: " + "; ".join(
                f"{n} x{len(v)} (lvl {v[0][2].level}{', UNIQUE' if 'UNIQUE' in v[0][2].flags else ''}) "
                f"nearest {min(w.dist(m[:2]) for m in v)} away" for n, v in self.monster_groups().items()))
        else:
            lines.append("Monsters in view: none")
        lines.append("Items seen: " + ("; ".join(l.strip() for l in w.itemlist) if w.itemlist else "?"))
        near_items = sorted(self.resolve_target("item"), key=w.dist)[:8] if w.pos else []
        if near_items:
            lines.append("Item squares nearby (glyph at y,x, distance): " + ", ".join(
                f"{w.memory.get(p, '?')} at {p[0]},{p[1]} ({w.dist(p)})" for p in near_items)
                + "  -- `goal fetch Y,X`")
        stairs = w.find("<>")
        if stairs:
            near = sorted(stairs, key=w.dist)[:4]
            lines.append("Known stairs: " + ", ".join(f"{w.memory[p]} at {p[0]},{p[1]} ({w.dist(p)} away)"
                                                     for p in near))
        # Consumables at a glance (also in --brief: the Navigator decided
        # without the pack, the game-state survey)
        cons = [self.show(i) for i in w.items(tval=(TV_POTION, TV_SCROLL, TV_FOOD, TV_FLASK, 55, 65, 66, 40, 45))]
        drained = [n for n, (cur, top) in (self.seen_drained or {}).items() if cur < top]
        lines.append("Supplies: " + ("; ".join(cons) or "none")
                     + (f" | RECALL PENDING (read {gnow() - w.recall_pending_t:.0f} s ago; it takes "
                        "15-34 turns, 8-23 s)" if w.recall_pending else "")
                     + f" | max_depth {self.orders.get('max_depth')}"
                     + (f" | drained: {', '.join(drained)}" if drained else ""))
        if self.unanswered:
            # (mission 15: a message sent before the Navigator's first wait was
            # only seen 4 minutes later in the news)
            lines.insert(1, self.unanswered_line())
        wt = self.weapon_table()
        if wt:
            lines.append("Weapons (blows, avg damage per round at your STR/DEX): " + "; ".join(
                self.weapon_text(n, b, d, eq, full=True) for n, b, d, eq in wt))
        if w.flags:
            # from the character sheet's grid (tool query 'flags'): facts, not guesses
            ab = [k for k, v in w.flags.items() if v and k not in ("stealth", "search", "infra", "tunnel")]
            lines.append("Abilities: " + (", ".join(ab) if ab else "none"))
        if self.audit_runs:
            lines.append(f"State audit: {self.audit_runs} checks"
                         + ("; differences: " + ", ".join(f"{k} {n}" for k, n in self.audit_counts.items())
                            if self.audit_counts else ", no differences"))
        # News of the last 10 minutes, every time (status calls used to clear it)
        news = self.news_line("Since last report: ", news_since, 12)
        if news:
            lines.append(news)
        lines.append("Recent messages: " + " | ".join(w.recent(30)[-12:]))
        st_line = self.structures_line(full=True)
        if st_line:
            lines.append(st_line)
        lines += self.since_lines(reset=news_since is not None)
        mv = self.movement_line()
        if mv:
            lines.append(mv)
        lines.append(self.gear_line())
        changed = [f"{k}={v} (default {DEFAULT_ORDERS[k]})" for k, v in self.orders.items()
                   if k in DEFAULT_ORDERS and str(v) != str(DEFAULT_ORDERS[k])]
        # (Dive03 kept think_hp 0.55 for five missions without noticing)
        lines.append("Orders changed from the defaults: " + ("; ".join(changed) if changed else "none"))
        lines.append("Orders: " + ", ".join(f"{k}={v}" for k, v in self.orders.items()))
        return "\n".join(lines)
