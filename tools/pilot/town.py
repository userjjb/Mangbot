"""town -- the Pilot's town side, as a mixin of Pilot (refactor-candidates E1; docs/goals-and-plans.md, the town
visit): the town kit's tables (STORE_NUM, KIT_ITEMS, KITS, BUYERS, SUPPLY_STAGES...) and what TownKit/Shop/HouseBank
ask of the Pilot -- the shopping list and the gold (town_needs, town_shopping, town_reserve, price_of, note_store,
buy_store), what to sell (town_buyers, town_sell_count, town_sells, is_crutch), making room and provisioning
(town_make_room, provision_step, kit_count, lantern_fuel, flasks_to_fill, flasks_spare, trip_minutes_left,
provisions_spare), Identify, Enchant
Armour and Weapon and Recharging (identify_candidates, enchant_plan, weapon_enchant_plan, enchant_buys,
recharge_wanted), the supply gate (supply_gate) and the
food/light clock (supply_minutes, supply_text, supply_watch, TURNS_PER_DMIN, FOOD_MID), the house and the stash
(house_state, house_save, banked, stash_*, tavern_*, retire_stash_json) and the town's stairs and edge crossings
(note_town_stairs, note_edge_cross). The methods stay Pilot's: they read and write the Pilot's state through self.
"""
import csv
import functools
import json
import os
import re
import sys
import time

import geareval
from common import HERE, TV_POTION, TV_SCROLL, TV_FOOD, TV_FLASK, TV_LITE, bare_name, singular, bad_inscription, rec_name, \
    inscription, mission_tag, FEELING_TAGS
from world import gnow, light_turns
from mover import MAX_HGT, MAX_WID
from town_goals import Shop, TownKit, town_houses
if os.path.join(HERE, "..", "observe") not in sys.path:     # (shopmath, as pilot.py loads it)
    sys.path.insert(0, os.path.join(HERE, "..", "observe"))
import shopmath                                  # noqa: E402


class TownMixin:
    """Pilot's town methods (`class Pilot(ReportMixin, GearMixin, ItemsMixin, TownMixin)`: every name stays on
    Pilot)."""

    def note_town_stairs(self):
        w = self.w
        if w.depth == 0 and not self.town_stairs:
            st = w.find(">")
            if st:
                self.town_stairs = list(st[0])
                with open(self.town_file, "w") as f:
                    json.dump({"stairs": self.town_stairs}, f)

    # The stage table's minimums (HANDBOOK; the Advisor's warrior-progression
    # memo): (from ft, CLW+CSW+CCW, CSW+CCW, CCW, Phase Door)
    SUPPLY_STAGES = ((250, 5, 0, 0, 4), (500, 5, 5, 0, 5), (750, 4, 4, 4, 8))

    def supply_gate(self, target_ft, recall_down):
        """What's missing for going down to target_ft (the Advisor's Navigator-
        decisions memo §3.1: most deaths and near-deaths went down with thin
        cures or no Word of Recall, the risk written in the journal). [] = OK."""
        w = self.w
        if target_ft < 250:
            return []
        def n(word):
            return sum(i["number"] for i in w.items() if word in i["name"])
        clw, csw, ccw = n("Cure Light Wounds"), n("Cure Serious Wounds"), n("Cure Critical Wounds")
        phase, wor = n("Phase Door"), n("Word of Recall")
        stage = max((st for st in self.SUPPLY_STAGES if target_ft >= st[0]), key=lambda st: st[0])
        _, cures, serious, critical, ph = stage
        missing = []
        if clw + csw + ccw < cures:
            missing.append(f"cure potions {clw + csw + ccw}/{cures}")
        if serious and csw + ccw < serious and ccw < 3:
            missing.append(f"CSW+CCW {csw + ccw}/{serious} (or 3 CCW)")
        if critical and ccw < critical:
            missing.append(f"CCW {ccw}/{critical}")
        if phase < ph:
            missing.append(f"Phase Door {phase}/{ph}")
        need_wor = 2 if recall_down else 1
        if wor < need_wor:
            missing.append(f"Word of Recall {wor}/{need_wor}" + (" (one to go, one to come home)" if recall_down else ""))
        # the worn light, or one in the pack (the Pilot takes the lantern off in town)
        turns = self.light_left                 # (no count shown: permanent)
        lights = [i for i in w.items(equip=True) if i["tval"] == TV_LITE] + list(w.items(tval=TV_LITE))
        best = max(lights, key=turns, default=None)
        flask = any(i["tval"] == TV_FLASK for i in w.items())
        if not best:
            missing.append("light: none")
        elif turns(best) < 1000 and not (flask and "Lantern" in best["name"]):
            missing.append(f"light: {turns(best)} turns left and no flask" if "Lantern" in best["name"]
                           else f"light: {turns(best)} turns left")
        return missing

    # --- the town kit (restructure step 2.2) ----------------------------------
    STORE_NUM = {"General store": 1, "Armoury": 2, "Weapon Smith": 3, "Temple": 4, "Alchemist": 5,
                 "Magic Shop": 6, "Black Market": 7,
                 # (the rulebook's shop_stock.csv names)
                 "General Store": 1, "Weaponsmith": 3, "Alchemy shop": 5, "Magic-User store": 6, "Black market": 7}
    # (`plan town`'s forecast said "2 Word of Recall at 5", which read like a price)
    STORE_LABEL = {1: "General Store", 2: "Armoury", 3: "Weaponsmith", 4: "Temple", 5: "Alchemist", 6: "Magic Shop",
                   7: "Black Market"}
    # who buys what (store.c store_will_buy), best first; never the Black Market (it pays a third)
    BUYERS = shopmath.BUYERS          # (D9: the table lives in shopmath, beside the pay rule that reads it)
    # kit kinds: (tval, the store that sells them, a price guess before we've seen one)
    KIT_ITEMS = {"Word of Recall": (70, 5, 250), "Cure Critical Wounds": (75, 4, 160),
                 "Cure Serious Wounds": (75, 4, 65), "Cure Light Wounds": (75, 4, 25), "Phase Door": (70, 5, 25),
                 "Identify": (70, 5, 80), "Flask of oil": (77, 1, 5), "Ration of Food": (80, 1, 5),
                 "Restore Strength": (75, 5, 490), "Restore Dexterity": (75, 5, 490),
                 "Restore Constitution": (75, 5, 490), "Restore Charisma": (75, 5, 490),
                 # (the only fear cure kept since Boldness went, the user 10-25; m41 ran out and phased 3 times
                 # afraid with three on it)
                 "Heroism": (75, 4, 55),
                 # (2.48.0, the user: Heroism's fallback -- bought only for Heroism's shortfall, FALLBACKS; the Temple's
                 # 8 gold in Dive04's stores.json)
                 "Boldness": (75, 4, 20),
                 # (the user, 10-25: Speed drunk at the start of hard fights; only the Black Market sells it, ~383 in
                 # m40; the Advisor's replays: it pays below ~500-600 gold at the rolling XP-per-gold rate)
                 "Potion of Speed": (75, 7, 400)}
    # hard price caps for kit lines (else 1.5x the price last seen): Black Market stock is sometimes far dearer
    KIT_CAP = {"Potion of Speed": 600}     # (450 until 10-26: the user raised it)
    # stock levels per stage (the Advisor's shops memo §3 and the Borg minimums):
    # A to 500 ft, B to 1000 ft, C deeper. No flasks: the town visit tops the lantern up instead (the user,
    # 10-25: oil, food and potions nobody uses fill the pack). Rations: one stack, eaten to Fed (at most 3) before a trip
    KITS = {"A": {"Word of Recall": 2, "Cure Light Wounds": 5, "Phase Door": 5, "Ration of Food": 3},
            "B": {"Word of Recall": 3, "Cure Critical Wounds": 4, "Cure Serious Wounds": 4, "Phase Door": 10,
                  "Ration of Food": 3, "Heroism": 3, "Potion of Speed": 2},
            "C": {"Word of Recall": 3, "Cure Critical Wounds": 6, "Cure Serious Wounds": 4, "Phase Door": 12,
                  "Ration of Food": 3, "Heroism": 3, "Potion of Speed": 2},
            "none": {}}
    # The lantern leaves town full (2.49.0, the user: oil is very cheap, and fuel past the top just caps; was: topped up
    # to 9000): FUEL_LAMP 15000 (mdefines.h:187), a flask adds its pval, 7500 (object.txt:3027 "I:77:0:7500"), and
    # do_cmd_refill_lamp caps the sum at FUEL_LAMP (cmd3.c:1365-1374: "Your lamp is full."). A lantern within
    # FILL_SLACK turns of the top counts as full (a flask for a few hundred turns, e.g. a second `plan town`)
    FUEL_LAMP, FLASK_FUEL, FILL_SLACK = 15000, 7500, 300

    def flasks_to_fill(self, fuel="lantern"):
        """Flasks that fill the lantern (fuel: its turns, default the lantern's): ceil((15000 - fuel) / 7500), 0 when
        it is within FILL_SLACK of full or there's no lantern."""
        fuel = self.lantern_fuel() if fuel == "lantern" else fuel
        if fuel is None or fuel >= self.FUEL_LAMP - self.FILL_SLACK:
            return 0
        return -(-(self.FUEL_LAMP - fuel) // self.FLASK_FUEL)

    def flasks_spare(self, it):
        """How many of this flask stack the lantern doesn't need to fill it (the other stacks first): sold in town."""
        others = sum(i["number"] for i in self.w.items(tval=TV_FLASK) if i["item"] != it["item"])
        return max(0, it["number"] - max(0, self.flasks_to_fill() - others))
    # devices never sold by the kit (the Advisor's rulebook-r3 memo: escapes, travel, detection and
    # mapping, Perception, Stone to Mud, healing)
    USEFUL_DEVICES = ("Teleport", "Recall", "Deep Descent", "Detect", "Door/Stair Location", "Mapping", "Enlightenment",
                      "Perception", "Stone to Mud", "Cure Serious", "Cure Critical", "Curing", "Healing")
    # (only Door/Stair Location of the Location devices: the trip plan uses it on arrival. Treasure and Object
    # Location were never used in 30 missions and held two slots -- the user, 10-25: the pack fills up)
    # (not Cure Light Wounds: ~15-20 HP a charge at 270 HP, a turn each, a pack slot -- the user, m25)
    STAT_FULL = {"STR": "Strength", "DEX": "Dexterity", "CON": "Constitution"}
    RECHARGE_MAX_FAIL = 0.15
    # (the user, 10-28: undo disenchantment with Scrolls of Enchant Armour, "consult the chance of enchantment failure
    # to find a reasonable stopping place". spells2.c enchant(): +1 to-AC succeeds with 1 - table[to_a]/1000 (always
    # below +0, never past +15, halved on artifacts); a failure wastes only the scroll. The table's knee: up to +7 a
    # point costs <= 2 scrolls on average, +8 -> +9 3.3, +9 -> +10 20 -- so enchant while the next point is >= 50%)
    ENCHANT_TABLE = (0, 10, 50, 100, 200, 300, 400, 500, 700, 950, 990, 992, 995, 997, 999, 1000)
    ENCHANT_MIN_CHANCE = 0.5

    def enchant_chance(self, it):
        """The chance a Scroll of Enchant Armour adds +1 to this worn armour piece, or None (no [ac,+a] shown)."""
        m = re.search(r"\[(\d+),([+-]\d+)\]", it["name"])
        if not m or it["tval"] not in self.ARMOUR_SLOTS:
            return None
        to_a = int(m.group(2))
        c = 1.0 if to_a < 0 else 0.0 if to_a > 15 else 1 - self.ENCHANT_TABLE[to_a] / 1000
        return c * (0.5 if self.is_artifact(it["name"]) else 1.0)

    def enchant_plan(self):
        """(worn armour piece, chance) worth a Scroll of Enchant Armour now, the likeliest first."""
        out = [(it, self.enchant_chance(it)) for it in self.w.items(equip=True)]
        return sorted(((it, c) for it, c in out if c is not None and c >= self.ENCHANT_MIN_CHANCE), key=lambda x: -x[1])

    # (2.46.0, the user's option 2 on the Advisor's 11-03 memo: the wielded weapon too, by the armour's rule. Its to-dam
    # first: one to-dam is ~blows x P(hit) damage a turn, one to-hit ~1% hit chance. Not the bow: the Pilot doesn't
    # shoot. Not a weapon whose plusses aren't shown: unidentified, a read wouldn't show what it did)
    WEAPON_SCROLLS = (("todam", "Enchant Weapon To-Dam"), ("tohit", "Enchant Weapon To-Hit"))
    ENCHANT_KINDS = ("Enchant Armor", "Enchant Weapon To-Dam", "Enchant Weapon To-Hit")

    def wielded_weapon(self):
        """The wielded melee weapon (tval 20-23), or None."""
        return next((i for i in self.w.items(equip=True) if i["tval"] in (20, 21, 22, 23)), None)

    def weapon_plusses(self, it):
        """{"tohit": n, "todam": n} of a weapon whose (+h,+d) is shown, else None."""
        m = re.search(r"\(([+-]\d+),([+-]\d+)\)", (it or {}).get("name", ""))
        return {"tohit": int(m.group(1)), "todam": int(m.group(2))} if m else None

    def weapon_enchant_plan(self):
        """[(wielded weapon, scroll kind, chance)] worth a Scroll of Enchant Weapon To-Dam / To-Hit now (the chance
        >= ENCHANT_MIN_CHANCE, half on an artifact), to-dam first."""
        it = self.wielded_weapon()
        pl = self.weapon_plusses(it)
        if not pl:
            return []
        k = 0.5 if self.is_artifact(it["name"]) else 1.0
        out = []
        for which, kind in self.WEAPON_SCROLLS:
            x = pl[which]
            c = (1.0 if x < 0 else 0.0 if x > 15 else 1 - self.ENCHANT_TABLE[x] / 1000) * k
            if c >= self.ENCHANT_MIN_CHANCE:
                out.append((it, kind, c))
        return out

    def enchant_buys(self, spare=None):
        """[(kind, n, price)]: the Scrolls of Enchant plan town buys this visit -- Enchant Armor first, then the
        weapon's To-Dam and To-Hit, each the expected count to its stopping place (enchant_scrolls_wanted), within the
        spare gold (`spare`, at 110% of the price; None: not counted) and `order enchant_max` for them all together.
        Less the scrolls of the kind carried (2.48.0, the user: a carried scroll the kit would read is kept and read
        before anything more is bought; the cap counts only what is bought)."""
        left = int(self.orders.get("enchant_max", 25))
        out = []
        for kind in self.ENCHANT_KINDS:
            price = self.price_of(kind, 5) or 190
            carried = sum(i["number"] for i in self.w.items(tval=TV_SCROLL) if kind in i["name"])
            n = min(int(round(self.enchant_scrolls_wanted(kind))) - carried, left)
            if spare is not None:
                n = min(n, max(0, spare // max(1, int(price * 1.1))))
            if n > 0:
                out.append((kind, n, price))
                left -= n
                if spare is not None:
                    spare -= n * max(1, int(price * 1.1))
        return out

    def town_extras_note(self):
        """What plan town may spend beyond the kit and the list (m58: 5025 gold of Enchant Armor, never announced)."""
        bits = []
        buys = self.enchant_buys() if (self.enchant_plan() or self.weapon_enchant_plan()) else []
        if buys:
            what = " + ".join(f"{n} Scrolls of {kind}" for kind, n, _ in buys)
            bits.append(f"up to {what} (~{sum(n * pr for _, n, pr in buys)} gold; `order enchant_max=N` caps "
                        + ("it" if len(buys) == 1 else "them all") + ", 0 skips)")
        if self.recharge_wanted():
            bits.append("Scrolls of Recharging for " + ", ".join(i["name"] for i in self.recharge_wanted()))
        return ("; also, as stock allows: " + "; ".join(bits)) if bits else ""

    def enchant_scrolls_wanted(self, kind="Enchant Armor"):
        """Expected scrolls of this kind to bring every worn piece (Enchant Armor), or the wielded weapon's to-dam or
        to-hit (Enchant Weapon To-Dam / To-Hit), to the stopping place (sum of 1/chance per point)."""
        n = 0.0
        if kind != "Enchant Armor":
            it = self.wielded_weapon()
            pl = self.weapon_plusses(it)
            which = next((w for w, k in self.WEAPON_SCROLLS if k == kind), None)
            if not pl or not which:
                return 0.0
            k = 0.5 if self.is_artifact(it["name"]) else 1.0
            for x in range(pl[which], 16):
                c = (1.0 if x < 0 else 1 - self.ENCHANT_TABLE[x] / 1000) * k
                if c < self.ENCHANT_MIN_CHANCE:
                    break
                n += 1 / c
            return n
        for it in self.w.items(equip=True):
            m = re.search(r"\[(\d+),([+-]\d+)\]", it["name"])
            if not m or it["tval"] not in self.ARMOUR_SLOTS:
                continue
            k = 0.5 if self.is_artifact(it["name"]) else 1.0
            for to_a in range(int(m.group(2)), 16):
                c = (1.0 if to_a < 0 else 1 - self.ENCHANT_TABLE[to_a] / 1000) * k
                if c < self.ENCHANT_MIN_CHANCE:
                    break
                n += 1 / c
        return n

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def device_level(kind):
        """object.txt level of a staff or wand kind ('Perception' -> 10), or None."""
        for r in geareval._read_txt(os.path.join(geareval.LIB, "object.txt")):
            if r.get("N") == kind and "I" in r and r["I"][0] in ("55", "65") and "W" in r:
                return int(r["W"][0])
        return None

    def recharge_fail(self, it):
        """The chance a Scroll of Recharging destroys this staff/wand (spells2.c recharge_aux, strength 60, no
        SAFE_RECHARGE: 1 in (160 - level - 10 x charges per item) / 15), or None for a kind we don't know."""
        m = re.search(r"(Staff|Staffs|Wand|Wands) of (.+?) \((\d+) charges?\)", it["name"])
        if not m:
            return None
        lev = self.device_level(m.group(2))
        if lev is None:
            return None
        i = (160 - lev - 10 * (int(m.group(3)) // max(1, it["number"]))) // 15
        return 1.0 if i <= 1 else 1.0 / i

    def recharge_wanted(self):
        """Useful staffs and wands at 0-1 charges per item that a Scroll of Recharging would refill with at most
        RECHARGE_MAX_FAIL risk of destroying them (the user, 10-28: "hopefully it doesn't sell it, but rather it
        recharges it": a Staff of Perception refills 3-8 charges for one ~200-gold scroll, 1 in 10 lost)."""
        out = []
        for it in self.w.items():
            m = re.search(r"\((\d+) charges?\)", it["name"])
            if it["tval"] not in (55, 65) or not m or int(m.group(1)) // max(1, it["number"]) > 1 or \
                    not any(d in it["name"] for d in self.USEFUL_DEVICES):
                continue
            f = self.recharge_fail(it)
            if f is not None and f <= self.RECHARGE_MAX_FAIL:
                out.append(it)
        return out

    def note_store(self):
        """Remember the shop we're in: its owner and the cheapest price per kind."""
        st = self.w.store
        if not st or self.w.store_t <= self.stores_noted_t:
            return
        self.stores_noted_t = self.w.store_t
        num = self.STORE_NUM.get(st.get("name"))
        if not num:
            return
        prices = {}
        for i in st.get("items", []):
            k = self.kind_key_of(i["name"])
            prices[k] = min(prices.get(k, i["price"]), i["price"])
        self.stores_seen[num] = {"owner": st.get("owner"), "t": round(gnow()), "prices": prices}
        try:
            json.dump(self.stores_seen, open(self.stores_file, "w"), indent=1)
        except OSError:
            pass

    @staticmethod
    def kind_key_of(name):
        return singular(bare_name(name).strip())

    def price_of(self, kind, store):
        """What `kind` cost at `store` last time we looked (the cheapest line), else a guess."""
        key = singular(kind)
        seen = [v for k, v in (self.stores_seen.get(store) or {}).get("prices", {}).items() if key in k]
        if seen:
            return min(seen)
        return self.KIT_ITEMS.get(kind, (0, 0, None))[2]

    # light radius (xtra1.c calc_torch): a torch 1 and a lantern 2 while fuelled; a Dwarven Lantern 2 and a Feanorian
    # Lamp 3, and any artifact light 3, need no fuel
    def light_radius(self, it):
        """(radius, permanent) of a light."""
        n = it["name"]
        if "Feanorian" in n or (it["tval"] == TV_LITE and self.true_artifact(n, TV_LITE)):
            return 3, True
        if "Dwarven" in n:
            return 2, True
        if "Torch" in n:
            return 1, False
        if "Lantern" in n:
            return 2, False
        return 1, light_turns(n) is None

    def light_better(self, it, worn):
        """2.53.0 (the user, m63: the Phial sat in the pack as "a backup for the light slot" beside the Brass Lantern;
        the gear evaluator ignores radius and fuel): a light needing no fuel with a radius at least the worn one's
        beats a fuelled one; otherwise, both alike, the larger radius wins."""
        (r, perm), (rw, permw) = self.light_radius(it), self.light_radius(worn)
        if self.light_left(it) <= 0:
            return False
        return (perm and not permw and r >= rw) or (perm == permw and r > rw)

    def permanent_light(self):
        """The light needing no fuel, of radius 2+, worn or carried (the best), or None: with one, the lantern's fuel
        isn't needed -- no flasks bought, the lantern and the flasks sold, the supply line says "light permanent"."""
        lights = [i for i in self.w.items(equip=True) + self.w.items(tval=TV_LITE) if i["tval"] == TV_LITE
                  and not bad_inscription(i["name"])]
        perm = [(r, i) for i in lights for r, pm in [self.light_radius(i)] if pm and r >= 2]
        return max(perm, key=lambda ri: ri[0])[1] if perm else None

    def lantern_fuel(self):
        """Turns of fuel in the lantern (worn, else the best in the pack), or None without one -- or (2.53.0) with a
        permanent light worn or carried (permanent_light): no oil is needed then."""
        if self.permanent_light():
            return None
        def fuels(items):
            return [t for i in items if "Lantern" in i["name"] for t in [light_turns(i["name"])] if t is not None]
        worn = fuels(self.w.items(equip=True))      # (not the max of all: a full spare hid a half-empty worn one, m39)
        pack = fuels(self.w.items())
        return worn[0] if worn else max(pack) if pack else None

    def trip_minutes_left(self):
        """How soon this trip should end, in minutes, or None if nobody knows: a Word of Recall under way;
        else the trip plan's time conditions (minutes>N, time>HH:MM) and its 90-minute cap."""
        if self.w.recall_pending:
            return 0.5
        tp = self.plan
        if not tp:
            return None
        left = [90 - (gnow() - tp.t0) / 60]
        for _, var, op, val in tp.conds:
            if var == "minutes" and op in (">", ">="):
                left.append(float(val) - (gnow() - tp.t0) / 60)
            elif var == "time" and op in (">", ">="):
                hh, mm = map(int, val.split(":"))
                lt = time.localtime()
                d = (hh * 60 + mm) - (lt.tm_hour * 60 + lt.tm_min + lt.tm_sec / 60)
                left.append(d + 1440 if d < -720 else d)
        return max(0.0, min(left))

    def provisions_spare(self):
        """Near a trip's end, the spare rations and flasks are no longer needed (the user, 10-25: eat, refill,
        and the rest frees pack slots): Word of Recall under way, or the trip ending within 3 minutes, or
        within 20 while Full (Full is 10000+ food, ~22 dungeon minutes before Hungry; the lantern leaves town
        full, 15000 turns)."""
        left = self.trip_minutes_left()
        return left is not None and (left <= 3 or (left <= 20 and self.w.hunger >= 4))

    def kit_count(self, kind):
        pack = self.w.items()
        if kind == "Ration of Food":
            # (rations only: a Scroll of Satisfy Hunger fills you to just under Gorged, and the next potion
            # tips you over -- speed -10 in m26's worst fight. The scroll is for when you're Weak)
            return sum(i["number"] for i in pack if i["tval"] == TV_FOOD and "Mushroom" not in i["name"])
        tv = self.KIT_ITEMS.get(kind, (None,))[0]
        key = singular(kind)
        n = sum(i["number"] for i in pack if (tv is None or i["tval"] == tv) and key in singular(i["name"]))
        if kind == "Identify":
            # a Staff of Perception's charges count as Identify scrolls
            n += sum(int(m.group(1)) for i in pack if i["tval"] == 55 and "Perception" in i["name"]
                     for m in [re.search(r"\((\d+) charges?\)", i["name"])] if m)
        return n

    def planned_depth(self):
        md = int(self.orders.get("max_depth", 0) or 0)
        deepest = self.deepest_ft or 0
        return min(md, deepest) if md and deepest else (md or deepest)

    def town_buyers(self, it):
        """The shops that buy this item, the best payer first (by owners seen)."""
        stores = self.BUYERS.get(it["tval"], ())
        chr_v = (self.w.ind.get("stat5") or [3])[0]

        def pay(st):
            owner = (self.stores_seen.get(st) or {}).get("owner")
            f = shopmath.factors(re.sub(r"\s*\(.*\)$", "", owner or ""), chr_v) if owner else None
            return -(f[0] if f else 0)
        return sorted(stores, key=lambda st: (pay(st), stores.index(st)))

    # Devices that map or detect for us, and so would hide what exploring by hand gets wrong: on the test server
    # they're sold like loot (the user, 2026-10-24: "too much of a crutch ... in the live server we won't have the
    # rod"); with --live they're kept like any useful device
    CRUTCH_DEVICES = ("Enlightenment", "Detection", "Magic Mapping")
    # (2.48.0, the user: the Scroll of Magic Mapping by the same rule -- sold in town and not read on the test server.
    # Not Deep Descent: that's travel, not mapping)
    CRUTCH_SCROLLS = ("Magic Mapping",)

    def is_crutch(self, it):
        if self.live:
            return False
        if it["tval"] == TV_SCROLL:
            return any(k in it["name"] for k in self.CRUTCH_SCROLLS)
        return it["tval"] in (55, 65, 66) and any(k in it["name"] for k in self.CRUTCH_DEVICES)

    # --- 2.48.0, the user's two principles for a weaker substitute (docs/pilot-items.md, fallbacks and stopgaps) ---
    # A. Fallback: kept, and bought, only while the better kit item is short -- below the kit's target and not in stock
    #    at an affordable price this visit (Boldness for Heroism: the Temple runs out of Heroism).
    # B. Dungeon stopgap: useful in the dungeon while the primary supply is short, but the primary is always on sale in
    #    town -- so sold in town; in the dungeon kept, never auto-destroyed, and worth what it covers while the primary is
    #    short (Satisfy Hunger for rations, a Wooden Torch for the lantern's fuel; CLW for kits B and C's CSW/CCW).
    # And the user's addition: a Scroll of Enchant or Recharging the kit would read is kept (and read before more are
    # bought); only the ones nothing would use are sold.
    FALLBACKS = {"Boldness": "Heroism"}          # the fallback kind: the kit kind it stands in for
    # (mushrooms whose effect the town sells only as a ~490-gold Restore potion: kept in town. The other mushrooms'
    # cures are the kit's potions -- CLW (blindness), Heroism (fear), CSW/CCW (confusion, poison, wounds) -- so they sell)
    KEEP_MUSHROOMS = ("Restore Strength", "Restore Constitution", "Restoring")

    def kit_by_depth(self):
        """The kit for the planned depth (town_needs: A < 500 ft <= B < 1000 ft <= C)."""
        want = self.planned_depth()
        return "A" if want < 500 else "B" if want < 1000 else "C"

    def visit_kit(self):
        """The kit this visit shops for, or the trip carries: plan town's kit=, else the planned depth's."""
        g = self.goal
        return g.kit if isinstance(g, TownKit) and g.kit else self.kit_by_depth()

    def kit_target(self, kind):
        return self.KITS.get(self.visit_kit(), {}).get(kind, 0)

    def fallback_of(self, it):
        """The kit kind a pack item is the fallback for ('Heroism' for a Potion of Boldness), or None."""
        if it["tval"] != TV_POTION:
            return None
        return next((v for k, v in self.FALLBACKS.items() if k in it["name"]), None)

    def fallback_kept(self, it):
        """A: a fallback while its kit kind is below the kit's target (kept in town, kit-valued in the dungeon)."""
        kind = self.fallback_of(it)
        return bool(kind) and self.kit_count(kind) < self.kit_target(kind)

    def clw_spare(self):
        """B: kits B and C heal with CSW and CCW, so their Potions of Cure Light Wounds are sold in town -- unless the
        supply gate's cure count would buy CLW back (250-499 ft planned under a kit= B/C) or the Navigator's buy list
        asks for them. Kit A buys CLW: kept."""
        if self.visit_kit() not in ("B", "C") or 250 <= self.planned_depth() < 500:
            return False
        g = self.goal
        return not (isinstance(g, TownKit) and any("Cure Light" in str(b[0]) for b in g.buylist))

    def lantern_lit(self):
        """A lantern with fuel worn or carried (a torch is then the light's fallback)."""
        return any("Lantern" in i["name"] and self.light_left(i) > 0
                   for i in self.w.items(equip=True) + self.w.items(tval=TV_LITE))

    def scroll_use(self, it):
        """What the town kit would read this Scroll of Enchant Armor / Enchant Weapon To-Dam / To-Hit or Recharging on
        (the item's name), or None: a worn piece or the wielded weapon whose next point is >= ENCHANT_MIN_CHANCE
        (enchant_plan, weapon_enchant_plan), a device recharge_wanted names."""
        name = it["name"]
        if it["tval"] != TV_SCROLL:
            return None
        if "Recharging" in name:
            r = self.recharge_wanted()
            return r[0]["name"] if r else None
        if "Enchant Armor" in name:
            plan = self.enchant_plan()
            return plan[0][0]["name"] if plan else None
        return next((wit["name"] for wit, kind, _ in self.weapon_enchant_plan() if kind in name), None)

    def town_rule(self, it):
        """The 2.48.0 rules for a pack item in town: ("keep", why) -- the kit would use it; ("sell", why) -- the older
        protections (a kit kind, food, a light) don't hold it, the shops' and the value policy's checks still apply;
        None -- the older rules decide."""
        name, tv = it["name"], it["tval"]
        if it.get("equip"):
            return None
        # (2.53.0: an artifact wearable can't be stored -- the server won't drop it above its depth -- so it stays in
        # the pack, never sold by the policy; the Navigator's `review sell` or `sell !` can)
        if tv in geareval.SLOT_OF_TVAL and self.true_artifact(name, tv) and \
                self.review_state()["decided"].get(name) != "sell":
            if name not in self.artifact_told:
                self.artifact_told.add(name)
                self.notify("tactic", f"{name}: an artifact -- the server won't let it be dropped above its depth, so "
                                      "it can't be stored; kept in the pack (`review sell` / `sell !` to sell it)",
                            news=True)
            return ("keep", "an artifact: the server won't let it be dropped above its depth (kept in the pack)")
        # (2.50.0, the user: the stash -- a backup for a worn slot, the store list, the Restores, Stone to Mud -- is
        # stored, never sold; it wins over the keep list, which only holds an item in the pack)
        why = self.stash_reason(it)
        if why:
            return ("keep", why)
        kind = self.fallback_of(it)
        if kind:
            have, target, kit = self.kit_count(kind), self.kit_target(kind), self.visit_kit()
            return ("keep", f"{kind}'s fallback: {kind} {have}/{target}, short (kit {kit})") if have < target else \
                ("sell", f"{kind}'s fallback, not needed: {kind} {have}/{target} (kit {kit})")
        if tv == TV_POTION and "Cure Light Wounds" in name and self.clw_spare():
            return ("sell", f"a stopgap: kit {self.visit_kit()} heals with Cure Serious/Critical Wounds")
        if tv == TV_SCROLL:
            use = self.scroll_use(it)
            if use:
                return ("keep", f"the town kit reads it on {use}")
            if "Satisfy Hunger" in name:
                return ("sell", "a stopgap: the General Store sells rations")
        if tv == TV_FOOD and "Mushroom" in name:
            keep = next((m for m in self.KEEP_MUSHROOMS if f"of {m}" in name), None)
            return ("keep", f"{keep}: the town restores a stat only with a ~490-gold potion") if keep else \
                ("sell", "food other than rations (its cure is the kit's potions)")
        if tv == TV_LITE and "Torch" in name and self.lantern_lit():
            return ("sell", "a lantern with fuel is carried")
        return None

    def fallback_buys(self, spare, since=None):
        """[(kind, store, n, cap)]: A -- each fallback for its kit kind's shortfall after the shops (none in stock, over
        the cap or not the gold), less the fallbacks carried, within `spare` gold at 110% of the price; not when the
        store's listing seen this visit (at or after `since`) had none. The cap: 1.5x the price."""
        out = []
        for fb, kind in self.FALLBACKS.items():
            n = self.kit_target(kind) - self.kit_count(kind) - self.kit_count(fb)
            store = self.KIT_ITEMS[fb][1]
            seen = self.stores_seen.get(store) or {}
            if n <= 0 or (since is not None and seen.get("t", 0) >= since - 1 and
                          not any(singular(fb) in k for k in seen.get("prices", {}))):
                continue
            price = self.price_of(fb, store) or 20
            n = min(n, max(0, spare) // max(1, int(price * 1.1)))
            if n > 0:
                out.append((fb, store, n, round(price * 1.5)))
                spare -= n * max(1, int(price * 1.1))
        return out

    def town_sell_count(self, it):
        """How many of this pack item the town kit sells (0: keep it)."""
        name = it["name"]
        if self.is_crutch(it) and not it.get("equip") and self.town_buyers(it):
            return it["number"]
        rule = self.town_rule(it)
        if rule and rule[0] == "keep":
            return 0
        freed = bool(rule)              # (2.48.0: a stopgap or a fallback not needed -- sold by the value checks below)
        # (food other than rations, and flasks the lantern doesn't need, are sold: one food source, no oil -- 2.49.0:
        # the flasks beyond those that fill the lantern, `flasks_spare`; it is filled after the buys)
        flask_spare = self.flasks_spare(it) if it["tval"] == TV_FLASK else 0
        spare = freed or (it["tval"] == TV_FOOD and "Ration" not in name and "Mushroom" not in name) or flask_spare > 0
        # (one lantern is enough -- the user, 10-26: "why two lanterns?" -- the fullest is kept, worn or in the pack;
        # a spare is sold)
        if it["tval"] == TV_LITE and "Lantern" in name and not it.get("equip"):
            others = [i for i in self.w.items(equip=True) + self.w.items() if i["tval"] == TV_LITE and
                      "Lantern" in i["name"] and i["item"] != it["item"]]
            spare = any(self.light_left(o) >= self.light_left(it) for o in others)
        # (2.53.0: beside a light needing no fuel -- the Phial -- lanterns and torches are spare lights)
        perm = self.permanent_light() if it["tval"] == TV_LITE and not it.get("equip") else None
        if perm is not None and perm["item"] != it["item"] and not self.light_radius(it)[1]:
            spare = True
        # (a staff doing what a carried rod does is spare: m43 carried a Staff of Door/Stair Location beside the Rod)
        rod_dup = it["tval"] == 55 and any(i["tval"] == 66 and re.sub(r".*\bof ", "", re.sub(r"\s*\(.*", "", i["name"]))
                                           in name for i in self.w.items())
        if it.get("equip") or (it["tval"] in (TV_FOOD, TV_FLASK, TV_LITE) and not spare) or \
                (self.is_kit_item(it) and not freed) \
                or (it["tval"] in (55, 65, 66) and any(d in name for d in self.USEFUL_DEVICES) and not rod_dup
                    and not (it["tval"] in (55, 65) and re.search(r"\(0 charges\)", name)
                             and not any("Recharging" in i["name"] for i in self.w.items())
                             and not any(r["item"] == it["item"] for r in self.recharge_wanted()))) \
                or self.is_kept(name) or \
                bare_name(name).lower() in self.ability_sources:
            return 0
        if not self.town_buyers(it) or bad_inscription(name):
            return 0
        if self.unknown_flavour(it):
            # (broke for a Word of Recall: unknown wands, staffs and rods sell anyway -- m27 had nothing to sell but
            # unknown devices and no gold for Identify; jewellery stays)
            if self.unknown_sell_refusal(it, 1) and not (it["tval"] in (55, 65, 66) and self.broke_for_recall()):
                return 0
            f = self.flavour_of(it)
            # one of an unknown stack: the sale teaches the flavour (the rest next pass)
            return it["number"] if (f and f["junk"]) or it["number"] == 1 else 1
        if self.probably_special(name) or self.value_refusal(it, "sell", "navigator"):
            return 0                    # (identify first)
        # (the gear evaluator would wear it: m45 sold a Ring of Strength (+2) right after identifying it, unjudged)
        if self.gear_better(it):
            return 0
        # (a judgement call: held for the Navigator's review)
        if self.review_hold(it):
            return 0
        iv = self.iv(name)
        # (a spare torch sells for a gold piece, under its 2-gold value's cut: "You sold 2 Wooden Torches (with 0 turns
        # of light) for 2 gold", Dive04 2026-09 -- 2.48.0 sells them beside a lantern)
        cheap_ok = freed and it["tval"] == TV_LITE
        if iv.kind is None or iv.value <= 0 or (iv.value * self.pay_cut(iv.tval) < 1 and not cheap_ok):
            return 0
        return flask_spare if it["tval"] == TV_FLASK and not freed else it["number"]

    PACK_SLOTS = 23

    def town_make_room(self, kit, buys):
        """Free the pack slots the buys need (kinds not in the pack yet): sell the cheapest item the policy doesn't
        protect where a shop buys it, else destroy it. One item per call (letters shift). True if it acted."""
        w = self.w
        new = {kind for _, kind, _, n, _ in buys if n > 0 and self.kit_count(kind) == 0}
        free = self.PACK_SLOTS - len(w.items())
        if len(new) <= free:
            return False
        tries = kit.room_tries
        cand = sorted(((self.pack_value(i), i) for i in w.items()), key=lambda vi: vi[0])
        cand = [(v, i) for v, i in cand if v < float("inf")]
        if not cand or tries >= 6:
            if not kit.room_said:
                kit.room_said = True
                kit.done_log.append(f"pack full: no room for {', '.join(sorted(new))} (nothing the policy lets go)")
            return False
        kit.room_tries = tries + 1
        v, it = cand[0]
        store = (self.town_buyers(it) or [None])[0]
        if store and v >= 1:
            kit.sub = Shop(store, sells=[(it["item"], it["number"])])
            kit.sub.role = "pilot"
            kit.done_log.append(f"room for {', '.join(sorted(new))}: selling {it['name']}")
        else:
            self.c.send("confirm yes")
            self.cmd(f"custom k item={it['item']} value={self.destroy_count(it)}", f"town kit: make room, destroy {it['name']}",
                     hold=0.6)
            kit.done_log.append(f"room for {', '.join(sorted(new))}: destroyed {it['name']}")
        return True

    def provision_step(self, kit):
        """The town visit's last step: fill the lantern from the flasks bought for it, to full (2.49.0; worn: it
        refuels the light in hand), then eat rations until Fed (at most 3) -- not Full: a ration is 5000 food, Full starts at 10000
        and Gorged (-10 speed) at 15000, so a Full character is a few potions from Gorged (m48: the 5th Cure Critical in
        a blind fight). The Pilot eats its ration in the dungeon when Hungry. True if it acted."""
        w = self.w
        fuel = self.lantern_fuel()
        # the fuller lantern on first (m39 left town with 4383 turns worn and 13290 in the pack)
        spare = self.best_light()
        if fuel is not None and spare and self.light_left(spare) > fuel + 1000 and \
                any(i["tval"] == TV_LITE for i in w.items(equip=True)) and not kit.swapped:
            kit.swapped = True
            self.cmd(f"custom w item={spare['item']}", f"town kit: wear the fuller lantern ({self.light_left(spare)} "
                                                       f"turns vs {fuel})", hold=0.8)
            return True
        flask = next((i for i in w.items(tval=TV_FLASK)), None)
        if fuel is not None and self.flasks_to_fill(fuel) and flask and kit.fuelled < 3:
            worn = next((i for i in w.items(equip=True) if i["tval"] == TV_LITE), None)
            if not worn or "Lantern" not in worn["name"]:
                return self.wear_light("town kit: the lantern on to refuel it")
            kit.fuelled += 1
            self.cmd(f"custom F item={flask['item']}", f"town kit: fill the lantern ({fuel} turns)", hold=0.8)
            kit.done_log.append(f"filled the lantern ({fuel} turns)")
            return True
        ration = self.find_item("Ration", TV_FOOD)
        if ration and w.hunger <= 2 and kit.ate < 3:
            kit.ate += 1
            self.cmd(f"eat {ration['item']}", "town kit: eat to Fed before the trip", hold=1.0)
            if kit.ate == 1:
                kit.done_log.append("ate to Fed")
            return True
        return False

    def broke_for_recall(self):
        """In town with fewer than 2 Words of Recall and not the gold for the next one."""
        return not self.w.in_dungeon and self.kit_count("Word of Recall") < 2 and \
            self.w.ind.get("gold", [0])[0] < (self.price_of("Word of Recall", 5) or 250)

    def town_sell_stores(self):
        return sorted({self.town_buyers(i)[0] for i in self.w.items() if self.town_sell_count(i)})

    def town_sells(self, store):
        """[(pack index, count)] to sell at `store` now."""
        return [(i["item"], n) for i in self.w.items() for n in [self.town_sell_count(i)]
                if n and self.town_buyers(i)[0] == store]

    def identify_candidates(self, minimum):
        out = []
        for it in self.w.items() + self.w.items(equip=True):
            name = it["name"]
            if (self.flavour_of(it) or {}).get("junk") or bad_inscription(name):
                continue
            iv = self.iv(name)
            if iv.known is not False:
                continue
            bare = bare_name(name).lower()
            prio = float("inf") if bare in self.ability_sources or iv.p_irreplaceable >= 0.2 else iv.value * self.pay_cut(iv.tval)
            if prio >= minimum:
                out.append((prio, it))
        return out

    def town_identify_wanted(self):
        # worth a scroll when its expected value sold is at least twice the scroll's price (likely
        # egos and ability sources always count; m24 bought 3 for 189 of 718 gold, partly for a
        # Staff of Detect Invisible)
        return len(self.identify_candidates(2 * (self.price_of("Identify", 5) or 80)))

    def town_needs(self, kit, buylist):
        """The shopping list by priority tier, before gold: [[tier, kind, store, n, cap]].
        1: Words of Recall to 2; 2: the supply gate's minimums for the planned depth;
        3: Restore for a drained STR/DEX/CON; 4: the kit; 5: the Navigator's buy list."""
        want = self.planned_depth()
        kit = kit or self.kit_by_depth()
        plan = []

        def planned(kind):
            return self.kit_count(kind) + sum(r[3] for r in plan if r[1] == kind)

        def add(tier, kind, target):
            n = target - planned(kind)
            if n > 0:
                plan.append([tier, kind, self.KIT_ITEMS[kind][1], n, self.KIT_CAP.get(kind)])
        add(1, "Word of Recall", 2)
        if want >= 250:
            _, cures, serious, critical, ph = max((st for st in self.SUPPLY_STAGES if want >= st[0]),
                                                  key=lambda st: st[0])
            add(2, "Cure Critical Wounds", critical)
            ccw = planned("Cure Critical Wounds")
            if serious and ccw < 3:
                add(2, "Cure Serious Wounds", serious - ccw)
            total = sum(planned(k) for k in ("Cure Light Wounds", "Cure Serious Wounds", "Cure Critical Wounds"))
            if total < cures:
                k = "Cure Serious Wounds" if want >= 500 else "Cure Light Wounds"
                add(2, k, planned(k) + cures - total)
            add(2, "Phase Door", ph)
        # (the flasks that fill the lantern, less those carried: 2.49.0, full -- was to 9000)
        if self.flasks_to_fill():
            add(2, "Flask of oil", self.flasks_to_fill())
        for stat, (cur, top) in (self.seen_drained or {}).items():
            if stat in self.STAT_FULL and cur < top:
                # (fetched from the stash instead; 2.50.0: or a carried restore mushroom eats it -- restore_for)
                if not self.stash_has(f"Restore {self.STAT_FULL[stat]}") and not self.restore_for(stat):
                    add(3, f"Restore {self.STAT_FULL[stat]}", 1)
        for kind, n in self.KITS.get(kit, {}).items():
            add(4, kind, n)
        # NAME:N means "have N" (m26's "Word of Recall:3" bought 3 more, to 5)
        for name, n, cap, store in buylist:
            # (2.47.0, the docs audit: a stash kind -- a stat Restore, a Stone to Mud wand -- in the house or the
            # tavern counts as had: plan town deposits every Restore, so `buy Restore_Dexterity:1` bought one a visit)
            more = n - planned(name) - (self.stash_count(name) if self.is_stash_item(f"Potion of {name}") or
                                        self.is_stash_item(name) else 0)
            if more > 0:
                plan.append([5, name, store, more, cap])
        # 6. Restore Charisma last: Dive04's natural CHR is 4, so it gives 3 -> 4, ~125 gold a
        # mission in prices (the Advisor's rulebook-r3 memo: pays back in ~4 missions)
        # (only with gold to spare: m26 spent 498 of its last 759 on it)
        cur, top = (self.seen_drained or {}).get("CHR", (0, 0))
        if cur < top and not any(r[1] == "Restore Charisma" for r in plan) and self.w.ind.get("gold", [0])[0] >= 3000:
            add(6, "Restore Charisma", 1)
        return plan

    # the restore mushrooms (use-obj.c:169-190: SV_FOOD_RESTORE_STR do_res_stat(A_STR), SV_FOOD_RESTORE_CON
    # do_res_stat(A_CON), SV_FOOD_RESTORING all six stats); food pval 500 each (object.txt)
    RESTORE_MUSHROOMS = {"Restore Strength": {"STR"}, "Restore Constitution": {"CON"},
                         "Restoring": {"STR", "INT", "WIS", "DEX", "CON", "CHR"}}

    def restore_mushroom_stats(self, name):
        """The stats a known restore mushroom restores ('a Mushroom of Restoring': all six), else an empty set (an
        unknown mushroom is never eaten for a drain)."""
        m = re.search(r"\bMushrooms? of (Restore Strength|Restore Constitution|Restoring)\b", name)
        return self.RESTORE_MUSHROOMS[m.group(1)] if m else set()

    def restore_cost(self, it):
        """What using this restore item costs: a potion its price at the Alchemist (last seen, else KIT_USE's 480), a
        mushroom its value (itemvalue: 350, Restoring 1000) -- the town sells no mushroom, so it is valued as it sells."""
        if it["tval"] == TV_POTION:
            kind = re.sub(r"^.*?(Restore \w+).*$", r"\1", it["name"])
            return self.price_of(kind, 5) or self.KIT_USE["Restore"]
        return self.iv(it["name"]).value

    def restore_for(self, stat, skip=()):
        """The cheapest pack item (restore_cost) that restores this stat: a Potion of Restore <stat> (STR, DEX, CON,
        CHR), or (2.50.0, the user) for STR/DEX/CON a known restore mushroom that covers it and won't make us Gorged
        (eat_fits), or None. Names in `skip` are left out."""
        full = dict(self.STAT_FULL, CHR="Charisma")
        if stat not in full:
            return None
        cands = []
        for it in self.w.items():
            if it["name"] in skip:
                continue
            if it["tval"] == TV_POTION and f"Restore {full[stat]}" in it["name"]:
                cands.append((self.restore_cost(it), 1, it))
            elif it["tval"] == TV_FOOD and stat in self.STAT_FULL and stat in self.restore_mushroom_stats(it["name"]) \
                    and self.eat_fits(it["name"]):
                cands.append((self.restore_cost(it), 0, it))
        return min(cands, key=lambda c: c[:2])[2] if cands else None

    def restore_item(self, skip=(), stats=("STR", "DEX", "CON", "CHR")):
        """A pack item that restores a drained stat of `stats` (STR, DEX and CON first: blows and HP), the cheapest
        for it (restore_for), or None. A mushroom (tval TV_FOOD) is eaten, a potion quaffed. The dungeon's policy_tick
        asks for STR/DEX/CON only (INT/WIS/CHR wait for town); TownKit also drinks a Restore Charisma it bought."""
        for stat in stats:
            cur, top = (self.seen_drained or {}).get(stat, (0, 0))
            if cur < top:
                it = self.restore_for(stat, skip)
                if it:
                    return it
        return None

    def town_reserve(self):
        """The gold tiers 1-2 (recall and the gate's minimums) need."""
        return sum(n * (self.price_of(k, st) or 0) for t, k, st, n, _ in self.town_needs(None, ()) if t <= 2)

    def town_shopping(self, kit, buylist):
        """(buys, short): what the gold buys, in priority order, as [(tier, kind, store, n,
        cap)], and [(kind, n)] it can't. Essentials (tiers 1-3) have no price cap;
        the kit's own lines are capped at 1.5x the price last seen."""
        left = self.w.ind.get("gold", [0])[0]
        buys, short = [], []
        for tier, kind, store, n, cap in self.town_needs(kit, buylist):
            price = self.price_of(kind, store) or cap
            if not price:
                buys.append((tier, kind, store, n, cap))      # (unknown price: the cap decides)
                continue
            if cap and price > cap:
                short.append((f"{kind} (over {cap})", n))     # (the shop asks more than the line is worth)
                continue
            k = min(n, left // price)
            if k:
                buys.append((tier, kind, store, k, cap if cap else (round(price * 1.5) if tier == 4 else None)))
                left -= k * price
            if k < n:
                short.append((kind, n - k))
                # Word of Recall short of 2 and unaffordable: the gold waits for it -- nothing else but food (m27
                # spent 62 of 71 gold on a CSW with WoR at 1)
                if tier == 1 and kind == "Word of Recall":
                    for t2, k2, s2, n2, c2 in self.town_needs(kit, buylist):
                        if k2 == "Ration of Food":
                            pr = self.price_of(k2, s2) or 4
                            m = min(n2, left // pr)
                            if m:
                                buys.append((t2, k2, s2, m, c2))
                    short.append(("(saving for Word of Recall)", 0))
                    return buys, short
        return buys, short

    def buy_store(self, name):
        """The store that stocks `name` (the rulebook's stock table, or a listing we saw)."""
        key = singular(re.sub(r"^(Potions?|Scrolls?|Rings?|Amulets?|Wands?|Staffs?|Staves|Rods?) of ", "", name.strip()))
        for r in self.stock_table():
            if key in singular(re.sub(r"[&~]", "", r["item_name"]).strip()) or \
                    singular(re.sub(r"[&~]", "", r["item_name"]).strip()) in key:
                return self.STORE_NUM.get(r["store"])
        for st, v in self.stores_seen.items():
            if st != 7 and any(key in k for k in v.get("prices", {})):
                return st
        return None

    def stock_table(self):
        if self._stock is None:
            try:
                self._stock = list(csv.DictReader(open(os.path.join(HERE, "..", "rulebook", "shop_stock.csv"))))
            except OSError:
                self._stock = []
        return self._stock

    # --- the stash (the user, 10-26; refactor-candidates D10, 11-01: house.json is its only record) --------------
    # In the house: house.json `items` ("Y,X" -> name, HouseBank.item_step). Without a house, the tavern room:
    # house.json `tavern` ({"entrance": [Y, X], "items": {"Y,X": name}}; StashDeposit/StashFetch). The old stash.json
    # (its items, tavern squares and the hand-written where/lost notes) was retired on 2026-11-01.
    # (2.50.0, the user, 11-04: "spare items that are valuable and can't be bought should be stored when possible" --
    # the stash also holds the best backup for each worn slot and the user's store list; the house first, the tavern
    # room when the house is full, and when neither has room the Navigator is told to `ask` the Architect)
    STASH_KINDS = r"Potions? of Restore (Strength|Intelligence|Wisdom|Dexterity|Constitution|Charisma)"
    # (2.51.0, the user after m62: a Ring of Slow Digestion, ~75 gold at sale, its ability already given by the amulet,
    # took a tavern square) a backup is worth BACKUP_MIN_SALE at sale -- value x pay_cut, the figure its stash record
    # stores -- or gives an ability the rest of the worn gear doesn't (the slot's own pieces left out: what losing them
    # would cost). An artifact always qualifies (itemvalue can't price artifact jewellery)
    BACKUP_MIN_SALE = 1000
    BACKUP_SLOT_LABEL = {"body": "body armour"}

    @staticmethod
    def true_artifact(name, tval=None):
        """A true artifact (the Phial, 'Narthanc'...), identified or not: geareval reads its artifact, its kind exists
        only as artifacts (INSTA_ART: the Phial, the Star, the Arkenstone), or its name is an artifact's."""
        gi = geareval.Item(name, tval)
        return bool(gi.art or "INSTA_ART" in (gi.kind or {}).get("flags", ()) or
                    re.search(r"'\w|\bthe \w+ of [A-Z]", name or ""))

    # (2.53.0, m63 11:11-11:14: `custom d` of the Phial answered "You can not drop this here." ~600 times) a drop the
    # server refuses ends that item's stashing for the visit at once; any 3 drops that didn't happen do too
    DROP_TRIES = 3

    def drop_failed(self, name, since):
        """A stash drop sent at `since` that didn't happen (the item still in the pack): counted; the server's "You can
        not drop this here." gives up at once. True once the item is given up for this visit (news, once)."""
        k = bare_name(name).lower()
        refused = any(ts >= since - 0.5 and "can not drop this here" in t.lower() for ts, t in self.w.messages)
        n = self.drop_fails.get(k, 0) + (self.DROP_TRIES if refused else 1)
        self.drop_fails[k] = n
        if n >= self.DROP_TRIES and k not in self.drop_told:
            self.drop_told.add(k)
            self.notify("tactic", f"{name}: " + ("the server won't let it be dropped here" if refused else
                                                 f"{self.DROP_TRIES} drops didn't happen") +
                        " -- not stashed this visit, kept in the pack", news=True)
        return n >= self.DROP_TRIES

    def stash_to_drop(self, it):
        """A pack item the stash steps should drop now: a stash item not given up on this visit (drop_failed)."""
        return self.is_stash_item(it["name"]) and \
            self.drop_fails.get(bare_name(it["name"]).lower(), 0) < self.DROP_TRIES

    def is_stash_item(self, name):
        """A pack item's name the stash takes: the stat-restore potions (not Restore Mana) and Wands of Stone to Mud
        (10-26), a name on the user's store list, or (a pack item's name) the best backup for a worn slot
        (stash_backup) -- 2.50.0. Never a true artifact (2.53.0: the server refuses to drop one above its depth,
        object2.c inven_drop_okay -- town and the house tile are above every artifact; m63's Phial looped)."""
        if self.true_artifact(name):
            return False
        # (stat restores only: a Potion of Restore Mana went into the stash in m48 -- useless to a warrior)
        if re.search(self.STASH_KINDS, name) or ("Stone to Mud" in name and "Wand" in name) or \
                self.on_store_list(name):
            return True
        it = next((i for i in self.w.items() if i["name"] == name), None) if self.w else None
        return bool(it and self.stash_backup(it))

    def on_store_list(self, name):
        """On the user's store list (rundir/store.json, `store add NAME`): lower-case name parts, matched as keep.json
        is (is_kept: a substring of the bare name, singular too)."""
        b = bare_name(name).lower()
        return any(k and (k in b or k in singular(b)) for k in self.store_list)

    def stash_reason(self, it):
        """Why the town keeps a pack item for the stash (town_rule's text), or None: "a backup for the weapon slot
        (Free Action, See Invisible)", "on the store list", "the stash: a stat Restore" / "...: Stone to Mud"."""
        name = it["name"]
        if it.get("equip"):
            return None
        if self.on_store_list(name):
            return "on the store list"
        why = self.stash_backup(it)
        if why:
            return why
        if re.search(self.STASH_KINDS, name):
            return "the stash: a stat Restore (the house keeps it)"
        if "Stone to Mud" in name and "Wand" in name:
            return "the stash: a Wand of Stone to Mud (the house keeps it)"
        return None

    @functools.lru_cache(maxsize=None)
    def _town_wearables(self):
        """(tval, kind name) of the wearables the town's shops 1-6 stock (the rulebook's shop_stock.csv): what can be
        bought back."""
        return frozenset((int(r["tval_num"]), geareval._norm(r["item_name"])) for r in self.stock_table()
                         if r.get("tval_num", "").isdigit() and "black" not in r.get("store", "").lower())

    def backup_item(self, name, tval=None, weight=None):
        """geareval.Item for a wearable that may be a gear backup, else None: a weapon, armour piece, ring, amulet or
        light (not a bow) the shops can't sell -- an ego or an artifact, or jewellery/a light of a kind shops 1-6
        don't stock -- identified (not merely felt), not cursed. (Whether it is worth storing -- BACKUP_MIN_SALE or an
        ability not otherwise worn -- is backup_qualifies, with the gear model.)"""
        if bad_inscription(name) or self.true_artifact(name, tval):
            return None               # (2.53.0: an artifact can't be dropped in town or the house: never stored)
        gi = geareval.Item(name, tval, weight)
        if not gi.slot or gi.slot == "bow" or not (gi.kind or gi.art):
            return None
        iv = self.iv(name)
        if iv.known is not True or iv.estimate:
            return None
        art = bool(iv.artifact or gi.art)
        kind = gi.kind or {}
        stocked = (gi.tval, geareval._norm(kind.get("name", ""))) in self._town_wearables()
        if not (art or iv.ego or gi.ego or (gi.slot in ("ring", "amulet", "light") and not stocked)):
            return None
        return gi

    def backup_sale(self, name):
        """What the town would pay for it: itemvalue x pay_cut (one item; the stash record's value)."""
        iv = self.iv(name)
        return iv.value * self.pay_cut(iv.tval)

    def backup_qualifies(self, gi, name, ch):
        """(ok, the abilities it would add): worth BACKUP_MIN_SALE+ at sale, an artifact, or giving an ability the
        worn gear without this slot's pieces doesn't (a Ring of Free Action when nothing else worn gives it; not a Ring
        of Slow Digestion beside an Amulet of Slow Digestion)."""
        without = {s: (v if s != gi.slot else []) for s, v in ch.worn.items()}
        new = gi.abilities() - set(ch.derive(without)["flags"])
        return bool(gi.art or self.iv(name).artifact or self.backup_sale(name) >= self.BACKUP_MIN_SALE or new), new

    def stash_backups(self):
        """The best backup per worn slot among the pack's unworn wearables and the stored ones (house and tavern):
        {"best": {slot: (where, name, item or None, labels)}, "outclassed": [(where, name, slot)]} -- where is
        "pack", "house" or "tavern" (2.51.0: and "unqualified": [(where, name, slot)], stored wearables no longer worth
        storing -- backup_qualifies). Only a candidate that qualifies competes. Best: first the most of the abilities the worn gear gets from the piece in that
        slot (lost with it) that it carries; then the required abilities (geareval.REQUIRED: Free Action, See
        Invisible) it carries at all; then the gear evaluator's static score (geareval.proxy) as if it replaced the
        worn piece (rings: the weaker worn ring); a stored one wins a tie. One per slot. A slot with nothing worn has
        no pack backup (the gear policy wears into it), only the best stored one (stash_fetch_list fetches it to
        wear). Cached on the pack, the gear, the stash and the stats."""
        w = self.w
        pack, worn = w.items(), w.items(equip=True)
        places = self.stash_places()
        stored = [(at, n) for at, slots in places.items() for n in slots.values() if isinstance(n, str)]
        key = (tuple((i["item"], i["name"]) for i in pack), tuple(i["name"] for i in worn), tuple(sorted(stored)),
               tuple(sorted((k, tuple(v)) for k, v in (w.ind or {}).items() if k.startswith("stat"))), w.clvl,
               tuple(sorted(self.store_list)))
        if self._backup_cache and self._backup_cache[0] == key:
            return self._backup_cache[1]
        out = {"best": {}, "outclassed": [], "unqualified": []}
        try:
            cands = []
            for i in pack:
                if i["tval"] not in geareval.SLOT_OF_TVAL or (self.flavour_of(i) or {}).get("junk"):
                    continue
                gi = self.backup_item(i["name"], i["tval"], i["weight"] // max(1, i.get("number", 1)))
                if gi:
                    cands.append(("pack", i["name"], i, gi))
            for at, n in stored:
                gi = self.backup_item(n)
                if gi:
                    cands.append((at, n, None, gi))
            if cands:
                ch = self.gear_character()
                cur = ch.derive()
                try:
                    mix = geareval.load_mix(os.path.join(self.rundir, "damage_mix.json"))
                except AttributeError:
                    mix = None
                lost = {}                       # (slot, j) -> the abilities the worn piece j of the slot gives alone
                scored = {}
                for at, n, i, gi in cands:
                    on = ch.worn.get(gi.slot) or []
                    if not on and at == "pack":
                        continue        # (a slot with nothing worn: the gear policy wears into it, no backup)
                    okq, new = self.backup_qualifies(gi, n, ch)
                    if not okq:
                        if at != "pack":
                            out["unqualified"].append((at, n, gi.slot))
                        continue
                    best = None
                    for j in range(max(1, len(on))):
                        if not on:
                            lost[(gi.slot, j)] = set()          # (empty -- the piece stolen: a stored one to wear)
                        elif (gi.slot, j) not in lost:
                            without = {s: [x for k, x in enumerate(v) if not (s == gi.slot and k == j)]
                                       for s, v in ch.worn.items()}
                            lost[(gi.slot, j)] = set(cur["flags"]) - set(ch.derive(without)["flags"])
                        carried = gi.abilities() & lost[(gi.slot, j)]
                        sc = (len(carried), geareval.proxy(ch.derive(ch.swap(gi, j)), cur, ch.depth_ft, mix))
                        if best is None or sc > best[0]:
                            best = (sc, carried)
                    (n_ab, prox), carried = best
                    # (then the required abilities it carries at all -- Free Action, See Invisible: a ring of Free
                    # Action backs up the weapon's, though the worn rings give none -- then the score)
                    req = len(gi.abilities() & set(geareval.REQUIRED))
                    rank = (n_ab, req, round(prox, 9), at != "pack")
                    # (the label: what it backs up, and what it alone would give -- 2.51.0)
                    scored.setdefault(gi.slot, []).append((rank, at, n, i, set(carried) | new))
                for slot, lst in scored.items():
                    lst.sort(key=lambda r: r[0], reverse=True)
                    _, at, n, i, carried = lst[0]
                    labels = [geareval.label(f) for f in sorted(carried, key=lambda f: (f not in geareval.REQUIRED, f))]
                    out["best"][slot] = (at, n, i, labels)
                    out["outclassed"] += [(a2, n2, slot) for _, a2, n2, _, _ in lst[1:] if a2 != "pack"]
        except Exception as e:              # (the evaluator must not stop the town visit: nothing is a backup then)
            self.log("note", text=f"stash backups failed: {e!r}")
            out = {"best": {}, "outclassed": [], "unqualified": []}
        self._backup_cache = (key, out)
        return out

    def backup_text(self, slot, labels):
        s = self.BACKUP_SLOT_LABEL.get(slot, slot)
        return f"a backup for the {s} slot" + (f" ({', '.join(labels)})" if labels else "")

    def stash_backup(self, it):
        """"a backup for the weapon slot (Free Action, See Invisible)" when this unworn pack item is the best backup for
        its worn slot (stash_backups), else None."""
        if it.get("equip") or it["tval"] not in geareval.SLOT_OF_TVAL:
            return None
        for slot, (at, n, i, labels) in self.stash_backups()["best"].items():
            if at == "pack" and i is not None and i["item"] == it["item"] and i["name"] == it["name"]:
                return self.backup_text(slot, labels)
        return None

    def stored_reason(self, at, name):
        """What a stored item is (the `house` listing): a backup, an outclassed backup (fetched to sell), on the store
        list, a stat Restore, Stone to Mud, else just stored."""
        if self.on_store_list(name):
            return "store list"
        bk = self.stash_backups()
        for slot, (a, n, i, labels) in bk["best"].items():
            if a == at and n == name:
                return self.backup_text(slot, labels).replace("a backup for the", "backup:")
        for a, n, slot in bk["outclassed"]:
            if a == at and n == name:
                return f"outclassed {self.BACKUP_SLOT_LABEL.get(slot, slot)} backup: plan town fetches it to sell"
        if re.search(self.STASH_KINDS, name):
            return "a stat Restore"
        if "Stone to Mud" in name:
            return "Stone to Mud"
        return "no longer a stash item: plan town fetches it to sell"

    def stash_keeps(self, at, name):
        """True while a stored item belongs in the stash: a stat Restore, Stone to Mud, the store list, or the best
        backup for its slot (2.51.0: anything else stored -- outclassed, no longer qualifying, adopted from the floor
        -- is fetched at the next plan town and sold)."""
        if re.search(self.STASH_KINDS, name) or ("Stone to Mud" in name and "Wand" in name) or \
                self.on_store_list(name):
            return True
        return any(a == at and n == name for a, n, i, labels in self.stash_backups()["best"].values())

    def stash_stored(self, text):
        """A floor message ("You see X.") naming something the stash holds: the pickup reflex leaves it in town."""
        low = text.lower()
        return any(rec_name(n) and bare_name(rec_name(n)).lower() in low
                   for slots in self.stash_places().values() for n in slots.values())

    def stash_room(self):
        """{"house": free squares in the house (None: no house), "tavern": free floor squares seen in the tavern room
        (None: not mapped -- only in town)}: the house's interior but the gold's square, less the recorded items; the
        tavern room's '.' squares less the recorded items."""
        st = self.house_state()
        out = {"house": None, "tavern": None}
        h = st.get("house")
        if h and h.get("box"):
            y1, x1, y2, x2 = h["box"]
            inside = tuple(h.get("step_in") or ())
            slots = st.get("items", {})
            out["house"] = sum(1 for y in range(y1 + 1, y2) for x in range(x1 + 1, x2)
                               if (y, x) != inside and f"{y},{x}" not in slots)
        ent = self.tavern_entrance() if not self.w.depth and not self.w.in_dungeon else None
        if ent:
            room = next((r for r in town_houses(self.w.memory, door="8") if r["door"] == tuple(ent)), None)
            if room:
                used = set(self.tavern_state().get("items", {}))
                out["tavern"] = sum(1 for q in room["inside"] if q != tuple(ent) and self.w.memory.get(q) == "."
                                    and f"{q[0]},{q[1]}" not in used)
        return out

    def stash_fetch_list(self, at):
        """[(name, why)]: the stored items in `at` (house|tavern) the town visit fetches (2.50.0): (i) a stored backup
        the gear policy would wear over the worn piece -- its slot empty (the piece stolen), or the gear evaluator's
        choice over a disenchanted one (gear_better; town only) -- and (ii) a stored backup a better one now outclasses
        (fetched so the shops sell it; the new one is deposited last); 2.51.0: and any other stored item the stash no
        longer keeps (stash_keeps: one no longer worth storing, BACKUP_MIN_SALE; an item adopted from the floor), to
        be sold (stash_to_sell: past the review queue; its credit, if any, debited at the sale)."""
        bk = self.stash_backups()
        out = []
        worn = self.w.items(equip=True)
        for slot, (a, n, i, labels) in bk["best"].items():
            if a != at:
                continue
            gi = geareval.Item(n)
            k = 2 if slot == "ring" else 1
            empty = sum(1 for x in worn if geareval.SLOT_OF_TVAL.get(x["tval"]) == slot) < k
            pseudo = {"name": n, "tval": gi.tval, "weight": gi.weight, "number": 1, "item": -1, "equip": False}
            if empty or self.gear_better(pseudo):
                out.append((n, f"to wear: {self.backup_text(slot, labels).replace('a backup for', 'the backup for')}"))
        for a, n, slot in bk["outclassed"]:
            if a == at:
                out.append((n, f"outclassed as the {self.BACKUP_SLOT_LABEL.get(slot, slot)} backup: to sell"))
        for n in sorted(set(self.stash_places()[at].values())):
            if n and not self.stash_keeps(at, n) and not any(n == x for x, _ in out):
                why = "not worth storing any more (under 1000 gold at sale, its abilities worn)" if \
                    any(a == at and n2 == n for a, n2, _ in bk["unqualified"]) else "not a stash item"
                out.append((n, f"{why}: to sell"))
        # (fetched to be sold: past the review queue -- m62's Ring of Slow Digestion would have waited 2 visits)
        self.stash_to_sell |= {bare_name(n).lower() for n, why in out if why.endswith("to sell")}
        return out

    def tavern_state(self):
        """The no-house fallback's record in house.json: the tavern's entrance and the stash items in its room."""
        return self.house_state().setdefault("tavern", {})

    def stash_places(self):
        """{'house': {"Y,X": name}, 'tavern': {"Y,X": name}}: what the stash holds and where (the house's items count
        only while a house is owned). The names only: a record is a plain name (before 2.50.0) or a dict with its
        metadata (stash_rec)."""
        st = self.house_state()
        return {"house": {k: rec_name(v) for k, v in st.get("items", {}).items()} if st.get("house") else {},
                "tavern": {k: rec_name(v) for k, v in st.get("tavern", {}).get("items", {}).items()}}

    # --- 2.50.0 (the user, 11-04): storing a find is income. Each record carries what the town would have paid for
    # it, when it was stored, and whether it was FRESH -- acquired in the current mission (or, with none running,
    # since the last time we left town for the dungeon) -- and the mission it was credited to. `stash_store` /
    # `stash_take` log records; the scorecard and the Pilot's gold rate add the fresh values, and subtract a credited
    # item's value when it is withdrawn and sold (`stash_credit_sold`), so a find isn't counted twice.
    def stash_rec(self, it, at, commit=True):
        """The house.json record for this pack item stored at `at` (house|tavern): {name, value (value x pay_cut x
        count: what the sell decision would have realised), t, fresh, mission}; committed (stash_commit: the
        `stash_store` log and the credit) at once, or -- commit=False -- once the drop is seen on the floor."""
        name = it["name"]
        iv = self.iv(name)
        value = int(round(iv.value * self.pay_cut(iv.tval) * max(1, it.get("number", 1))))
        fresh, mission = self.acquired_fresh(name)
        rec = {"name": name, "value": value, "t": time.strftime("%Y-%m-%d %H:%M"), "fresh": fresh,
               "mission": mission if fresh else None}
        if commit:
            self.stash_commit(rec, at)
        return rec

    def stash_commit(self, rec, at):
        """A stored item on record: logged `stash_store`, its value credited when fresh."""
        name = rec["name"]
        self.log("stash_store", item=name, where=at, value=rec["value"], fresh=rec["fresh"], mission=rec["mission"])
        if rec["fresh"]:
            self.gold_stored += rec["value"]
        self.acq_state()["credits"].pop(bare_name(name).lower(), None)    # (stored again: no debit pending)
        self.acq_save()

    def stash_found(self, name, at):
        """An item seen on a stash square that the record didn't hold (the live check of 11-04: a second Restore
        Charisma lay in the house): adopted -- not fresh, its value from itemvalue -- and logged `stash_found`."""
        iv = self.iv(name)
        value = int(round(iv.value * self.pay_cut(iv.tval) * max(1, iv.count)))
        self.log("stash_found", item=name, where=at, value=value)
        return {"name": name, "value": value, "t": time.strftime("%Y-%m-%d %H:%M"), "fresh": False, "mission": None,
                "found": True}

    @staticmethod
    def same_item(a, b):
        """Two names of one item (a record's and the floor's): the bare names, singular, alike."""
        return bool(a and b) and singular(bare_name(a).lower()) == singular(bare_name(b).lower())

    def floor_here(self, since):
        """(read, name): the item underfoot as the client's floor query read it at our square after `since` (game
        clock), name None for a bare floor; (False, None) until such a reading."""
        w = self.w
        if getattr(w, "floor_pos", None) == w.pos and (getattr(w, "floor_t", 0) or 0) > since:
            return True, w.floor
        return False, None

    def house_square(self, q):
        """A square inside the owned house on its tile (the bank's pile and the stash lie there), on this level."""
        h = self.house_state().get("house")
        w = self.w
        if not h or not h.get("box") or w.in_dungeon or (w.depth or 0) != int(h.get("depth", 0)):
            return False
        y1, x1, y2, x2 = h["box"]
        return y1 < q[0] < y2 and x1 < q[1] < x2

    def in_house(self):
        """Standing inside the owned house (its interior, on its tile): every item here is the stash's."""
        h = self.house_state().get("house")
        w = self.w
        if not h or not h.get("box") or not w.pos or w.in_dungeon or (w.depth or 0) != int(h.get("depth", 0)):
            return False
        y1, x1, y2, x2 = h["box"]
        return y1 < w.pos[0] < y2 and x1 < w.pos[1] < x2

    def acq_state(self):
        """rundir/acquired.json: `items` (what was picked up: name, kind, known, t, mission; the last ACQ_KEEP),
        `trip_t0` (when we last left town for the dungeon), `credits` (bare name -> value, mission: a fresh stored
        item withdrawn, debited if it is sold)."""
        if self._acq is None:
            try:
                self._acq = json.load(open(os.path.join(self.rundir, "acquired.json")))
            except (OSError, ValueError, AttributeError):
                self._acq = {}
            self._acq.setdefault("items", [])
            self._acq.setdefault("trip_t0", 0)
            self._acq.setdefault("credits", {})
        return self._acq

    def acq_save(self):
        try:
            json.dump(self.acq_state(), open(os.path.join(self.rundir, "acquired.json"), "w"), indent=1)
        except (OSError, AttributeError):
            pass

    ACQ_KEEP = 400

    def acq_kind(self, name):
        """The base kind a name keeps when identified ('a Scimitar (2d5) {excellent}' and 'a Scimitar of Westernesse
        (2d5) (+9,+8) (+1)': 'scimitar'): the gear kind, else the flavour/kind key."""
        gi = geareval.Item(name)
        if gi.kind:
            return geareval._norm(gi.kind.get("name", ""))
        return singular(self.kind_key_of(name))

    def note_acquired(self, name):
        """A pickup in the dungeon ("You have X (c)."; not in town, so never a purchase, nor a stash item being
        fetched): recorded with the mission running, if any (acquired.json)."""
        st = self.acq_state()
        iv = self.iv(name)
        st["items"] = (st["items"] + [{"name": name, "kind": self.acq_kind(name), "known": bool(iv.known is True
                                                                                               and not iv.estimate),
                                       "t": round(time.time(), 1), "mission": self.mission_label}])[-self.ACQ_KEEP:]
        self.acq_save()
        if self.mission_label:
            self.to_inscribe = (self.to_inscribe + [name])[-20:]     # (inscribed at a safe moment: inscribe_finds)

    # (the user, 11-04: mark a fresh find by inscribing it with the mission's label; `{` costs no game time --
    # tables.c: energy_cost 0 -- and is sent from policy_tick's safe moments and the town visit's start)
    INSCRIBE_SKIP_LIGHTS = ("Torch", "Lantern")          # (they stack: two missions' labels would take two slots)

    def inscribe_label(self, it):
        """The inscription that marks this pack item as found in the running mission, or None: a single wearable
        (weapon, armour, ring, amulet; a light other than a torch or lantern -- not a bow, nothing that stacks) whose
        inscription is empty or only a feeling ('excellent' -> 'excellent - m62', the server's own format) or the
        server's tried/empty marks. Never over anything else (the Navigator's @/! tags, @R750, a unique's name)."""
        label = self.mission_label
        if not label or it.get("equip") or it.get("number", 1) != 1 or mission_tag(it["name"]):
            return None
        tv = it["tval"]
        if tv not in geareval.SLOT_OF_TVAL or tv == 19 or \
                (tv == TV_LITE and any(k in it["name"] for k in self.INSCRIBE_SKIP_LIGHTS)):
            return None
        tag = inscription(it["name"])
        if not tag or tag in ("tried", "empty") or tag.endswith("% off"):
            return label
        if tag in FEELING_TAGS:
            return f"{tag} - {label}"
        return None

    def inscribe_finds(self):
        """Inscribe one find picked up in this mission (note_acquired's queue, `to_inscribe`) with the mission's
        label (inscribe_label). True if it sent one. The acquired.json match stays the fallback."""
        q = self.to_inscribe
        if not q or not self.mission_label or self.w.inven_dirty or gnow() - self.inscribe_t < 2:
            return False
        name = q.pop(0)
        it = next((i for i in self.w.items() if self.same_item(i["name"], name)
                   and not mission_tag(i["name"])), None)
        text = self.inscribe_label(it) if it else None
        if not text:
            return False
        self.inscribe_t = gnow()
        self.cmd(f"custom {{ item={it['item']} entry={text}", f"mark a find of {self.mission_label}: {it['name']}",
                 hold=0.4)
        self.w.inven_dirty = True
        return True

    def note_trip_start(self):
        """Left town for the dungeon: the start of the trip a find is fresh in when no mission runs."""
        self.acq_state()["trip_t0"] = round(time.time(), 1)
        self.acq_save()

    def acquired_fresh(self, name):
        """(fresh, mission) for an item being stored. First its inscription (2.50.0, the user): inscribed with the
        running mission's label (`{m62}`, `{excellent - m62}`) -- fresh; with another mission's -- not. Else (no label:
        a stackable, a Navigator's inscription, no mission running) its pickup record -- the latest of the same name,
        else (an item identified since: its name changed) the latest of the same base kind picked up unidentified --
        made in the mission running now (with none: since we last left town). No record (owned before 2.50.0, bought):
        not fresh."""
        tag = mission_tag(name)
        if tag:
            return (bool(self.mission_label) and tag == self.mission_label), self.mission_label
        st = self.acq_state()
        b = singular(bare_name(name).lower())
        recs = st["items"]
        rec = next((r for r in reversed(recs) if singular(bare_name(r["name"]).lower()) == b), None) or \
            next((r for r in reversed(recs) if not r.get("known") and r.get("kind") == self.acq_kind(name)), None)
        if not rec:
            return False, self.mission_label
        if self.mission_label:
            return rec.get("mission") == self.mission_label, self.mission_label
        return rec.get("t", 0) >= st.get("trip_t0", 0), None

    def stash_credit_sold(self, name, received):
        """A sale ("You sold X for N gold."): if X was stored fresh, credited, and withdrawn, its credit is debited
        (`stash_credit_sold`) -- the find counted once."""
        cr = self.acq_state()["credits"].pop(bare_name(name).lower(), None)
        if cr:
            self.gold_debited += cr.get("value", 0)
            self.log("stash_credit_sold", item=name, credited_value=cr.get("value", 0), received=received,
                     credited_mission=cr.get("mission"))
            self.acq_save()

    def stash_credit_worn(self, name):
        """A withdrawn credited item worn (a backup replacing a lost piece): no debit, the credit is settled."""
        if self.acq_state()["credits"].pop(bare_name(name).lower(), None):
            self.acq_save()

    def stash_where(self, kind):
        """'house' or 'tavern' where a stash item of this kind waits (the house first), else None."""
        return next((at for at, slots in self.stash_places().items() if any(kind in n for n in slots.values())), None)

    def stash_has(self, kind):
        return self.stash_where(kind) is not None

    def stash_count(self, kind):
        """How many of this kind the house's and the tavern's records hold."""
        key = singular(kind)
        n = 0
        for slots in (self.house_state().get("items", {}), self.tavern_state().get("items", {})):
            for names in slots.values():
                for nm in (names if isinstance(names, list) else [names]):
                    if key in singular(rec_name(nm)):
                        n += 1
        return n

    def stash_take(self, at, kind, square=None, lost=False):
        """Strike one item of this kind off the record of `at` (house|tavern): the one on `square` if it's there.
        Logged `stash_take` (2.50.0) with the value it was credited with (fresh) -- kept in acquired.json `credits`
        until it is sold (debited) or worn; `lost`: not found there (no credit kept)."""
        slots = self.house_state().get("items", {}) if at == "house" else self.tavern_state().get("items", {})
        key = f"{square[0]},{square[1]}" if square else None
        key = key if key in slots and kind in rec_name(slots[key]) else \
            next((k for k, n in slots.items() if kind in rec_name(n)), None)
        if key:
            rec = slots.pop(key)
            name = rec_name(rec)
            val = rec.get("value", 0) if isinstance(rec, dict) and rec.get("fresh") else 0
            mission = rec.get("mission") if isinstance(rec, dict) else None
            self.log("stash_take", item=name, where=at, credited_value=val, credited_mission=mission, lost=lost)
            if val and not lost:
                self.acq_state()["credits"][bare_name(name).lower()] = {"value": val, "mission": mission}
                self.acq_save()
            self.house_save()

    BANK_FLOAT = 300           # gold carried out of town when a house holds the rest (no use for it in the dungeon)

    # (the user, 10-28: "is the Navigator made aware of how much time until we are Starving or without light?")
    # The lantern burns a turn of fuel a player turn, ~215 a dungeon minute with the resting/running speed-ups
    # (FIELD-NOTES: 15000 -> 7500 in ~35 dungeon minutes, m29-m30). Food: 20 a food tick every 10 player turns at
    # normal speed, 10 with slow digestion (dungeon.c:1129-1147), none in town -- 1 or 2 a player turn, so on the same
    # clock. Food runs from the least the stomach holds (the tracker's bottom, stomach.py: exact once a hunger crossing
    # has pinned it, else the hunger level's bottom -- the client sends the level only) down to Weak (1000).
    TURNS_PER_DMIN = 215
    FOOD_MID = {0: 750, 1: 750, 2: 1500, 3: 6000, 4: 12500, 5: 15000}

    def supply_minutes(self, minus=None):
        """(food, light): dungeon minutes left counting the reserves (rations and other food; flasks), or None for a
        light that needs no fuel. minus: {pack index: count} just destroyed or eaten that the pack still shows
        (2.51.0: m62's make-room news counted the rations it had just destroyed)."""
        w = self.w
        minus = minus or {}

        def num(i):
            return max(0, i["number"] - minus.get(i["item"], 0)) if not i.get("equip") else i["number"]
        per_turn = 1.0 if (w.flags or {}).get("slow_digest") else 2.0
        reserve = sum(self.food_value(i["name"]) * num(i) for i in w.items(tval=TV_FOOD)
                      if "Mushroom" not in i["name"])
        # (2.48.1, m61: the bottom of the hunger level, not its middle -- "food ~23 dungeon min" stood still for 5
        # minutes while Fed and ran out; the least it can be is what alerts and decisions need. 2.49.0: the stomach
        # tracker's bottom, the level's until a crossing calibrates it)
        food = max(0.0, self.food_now() + reserve - 1000) / (per_turn * self.TURNS_PER_DMIN)
        fuel = self.lantern_fuel()
        if fuel is None:
            # no lantern: a worn light that shows turns (a torch) burns out -- its turns plus spare torches'; one that
            # shows none (an artifact) is permanent (a torch read as permanent: refactor-candidates A19)
            worn = next((i for i in w.items(equip=True) if i["tval"] == TV_LITE), None)
            m = light_turns(worn["name"]) if worn else None
            if not worn:
                light = 0.0
            elif m is None:
                light = None
            else:
                spare = sum(t * num(i) for i in w.items(tval=TV_LITE) if not i.get("equip")
                            for t in [light_turns(i["name"])] if t is not None)
                light = (m + spare) / self.TURNS_PER_DMIN
        else:
            flasks = sum(num(i) for i in w.items(tval=TV_FLASK))
            light = (fuel + flasks * self.FLASK_FUEL) / self.TURNS_PER_DMIN
        if self.permanent_light():
            light = None                     # (2.53.0: worn or carried -- in town the light is taken off when idle)
        return food, light

    def supply_text(self, minus=None):
        """'food >=N dungeon min, light ~M': food the least it can last; '~N' once the stomach tracker is exact (a
        hunger crossing or a Satisfy Hunger pinned it, 2.49.0). minus: as supply_minutes."""
        food, light = self.supply_minutes(minus)
        f = f"food {'~' if self.stomach.exact(self.w.hunger) else '>='}{food:.0f} dungeon min"
        return f"{f}, light ~{light:.0f}" if light is not None else f"{f}, light permanent"

    def supply_watch(self):
        """In the dungeon: tell the Navigator once when food or light (reserves counted) falls under 15, then 5,
        dungeon minutes; and, as news, once a trip when the pack holds no food (m46's Navigator found "Food 0" with no
        warning; the cause, make-room destroying rations, is fixed, but eating the last one isn't -- food_watch, merged
        here by D14). All are `supplies` notices with fields what (food|light) and level (low|out|recalling)."""
        w = self.w
        if not w.in_dungeon:
            return
        # (2.51.0, m62 09:32: "~5 minutes" right after a ration was eaten -- the pack and the stomach hadn't caught up.
        # Not while a meal waits for the pack, nor within 3 s of an eat, fuel or destroy, nor with the pack being read)
        la = self.last_action
        # (2.53.0, m63 10:44:37: Full -> Fed and "food ~5 dungeon minutes" on that tick -- the level's bottom, 2000,
        # before the tracker pinned 9990-9999 later in the tick. Not until the tracker has seen this hunger level)
        st = self.stomach
        if st is not None and st.level is not None and st.level != w.hunger:
            return
        if w.inven_dirty or (self.stomach is not None and self.stomach.pending) or \
                (la and gnow() - la[0] < 3 and re.match(r"(eat |custom [kEF] )", la[1])):
            return
        key = getattr(self.plan, "t0", None) or w.level_t
        if self.kit_count("Ration of Food") == 0 and self.food_warned != key:
            self.food_warned = key
            self.notify("supplies", f"no food left in the pack (hunger: "
                                    f"{('Weak', 'Weak', 'Hungry', 'Fed', 'Full')[min(4, max(0, w.hunger))]}): "
                                    "`plan town` buys rations; a Full character lasts ~20 dungeon minutes", news=True,
                        fields={"supply": "food", "level": "out"})
        food, light = self.supply_minutes()
        told = self.supply_told
        for what, m, how in (("food", food, "rations"), ("light", light, "flasks of oil")):
            if m is None:
                continue
            new = [th for th in (15, 5) if m < th and (what, th) not in told]
            if new:
                told.update((what, th) for th in new)     # (both crossed at once: one notice)
                self.notify("supplies", f"{what}: ~{m:.0f} dungeon minutes left with the {how} carried -- plan to "
                                        f"be home before then (`goal recall`)", fields={"supply": what, "level": "low"})
            if m >= 20:
                told.discard((what, 15))
                told.discard((what, 5))

    @staticmethod
    def edge_dir(pos):
        """The direction that walks off the map edge from this square (MAX_HGT 66, MAX_WID 198), else None."""
        y, x = pos
        return 8 if y <= 1 else 2 if y >= MAX_HGT - 2 else 4 if x <= 1 else 6 if x >= MAX_WID - 2 else None

    def note_edge_cross(self):
        """The last walk off the town's edge into a wilderness tile: {town square, wilderness square, depth} -- the
        way a wilderness house is reached (the user, 10-27: a small house just outside town, for the live server)."""
        w = self.w
        last = self.surface_last
        if w.pos and w.depth is not None and w.depth <= 0 and not w.in_dungeon:
            if last and last[0] == 0 and w.depth < 0 and self.edge_dir(last[1]):
                self.edge_cross = {"town": list(last[1]), "wild": list(w.pos), "depth": w.depth}
            self.surface_last = (w.depth, w.pos)
        else:
            self.surface_last = None

    def house_state(self):
        if self._house is None:
            try:
                self._house = json.load(open(os.path.join(self.rundir, "house.json")))
            except (OSError, ValueError, AttributeError):
                self._house = {}
            self.retire_stash_json()
        return self._house

    def retire_stash_json(self):
        """A stash.json left by an older Pilot (D10, 11-01: house.json is the stash's only record): its tavern
        entrance, and the items the house doesn't hold when there's no house, go into house.json `tavern`; the file
        is renamed stash.json.retired-DATE (its hand-written notes stay there, as history)."""
        try:
            path = os.path.join(self.rundir, "stash.json")
            old = json.load(open(path))
        except (OSError, ValueError, AttributeError):
            return
        st, tav = self._house, self._house.setdefault("tavern", {})
        if old.get("entrance") and not tav.get("entrance"):
            tav["entrance"] = old["entrance"]
        if not st.get("house"):
            held = list(tav.get("items", {}).values())
            squares = [f"{q[0]},{q[1]}" for q in old.get("squares", [])]
            for i, n in enumerate(x for x in old.get("items", []) if x not in held):
                key = squares[i] if i < len(squares) else f"?{i}"          # (the fetch searches the room anyway)
                tav.setdefault("items", {})[key] = n
        self.house_save()
        new = f"{path}.retired-{time.strftime('%Y-%m-%d')}"
        os.rename(path, new if not os.path.exists(new) else f"{new}-{int(time.time())}")
        self.log("note", text=f"stash.json retired into house.json (D10): {os.path.basename(new)}")

    def house_save(self):
        try:
            with open(os.path.join(self.rundir, "house.json"), "w") as f:
                json.dump(self.house_state(), f, indent=1)
        except (OSError, AttributeError):
            pass

    def banked(self):
        return int(self.house_state().get("banked", 0)) if self.house_state().get("house") else 0

    def tavern_entrance(self):
        """The tavern's '8' on the town map (remembered in house.json `tavern`)."""
        st = self.tavern_state()
        if not st.get("entrance") and not self.w.depth:
            q = next((q for q, ch in self.w.memory.items() if ch == "8"), None)
            if q:
                st["entrance"] = list(q)
                self.house_save()
        return tuple(st["entrance"]) if st.get("entrance") else None

    def stash_wanted(self, at=None):
        """The Restore kind a drained stat needs, if the pack lacks it and the stash has it (in `at`: house|tavern,
        or either)."""
        for stat, (cur, top) in (self.seen_drained or {}).items():
            if stat in self.STAT_FULL and cur < top:
                kind = f"Restore {self.STAT_FULL[stat]}"
                if not any(kind in i["name"] for i in self.w.items()) and \
                        (self.stash_where(kind) == at if at else self.stash_has(kind)):
                    return kind
        return None
