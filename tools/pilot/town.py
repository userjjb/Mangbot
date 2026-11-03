"""town -- the Pilot's town side, as a mixin of Pilot (refactor-candidates E1; docs/goals-and-plans.md, the town
visit): the town kit's tables (STORE_NUM, KIT_ITEMS, KITS, BUYERS, SUPPLY_STAGES...) and what TownKit/Shop/HouseBank
ask of the Pilot -- the shopping list and the gold (town_needs, town_shopping, town_reserve, price_of, note_store,
buy_store), what to sell (town_buyers, town_sell_count, town_sells, is_crutch), making room and provisioning
(town_make_room, provision_step, kit_count, lantern_fuel, trip_minutes_left, provisions_spare), Identify, Enchant
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
from common import HERE, TV_POTION, TV_FOOD, TV_FLASK, TV_LITE, bare_name, singular, bad_inscription
from world import gnow, light_turns
from mover import MAX_HGT, MAX_WID
from town_goals import Shop
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
                 # (the user, 10-25: Speed drunk at the start of hard fights; only the Black Market sells it, ~383 in
                 # m40; the Advisor's replays: it pays below ~500-600 gold at the rolling XP-per-gold rate)
                 "Potion of Speed": (75, 7, 400)}
    # hard price caps for kit lines (else 1.5x the price last seen): Black Market stock is sometimes far dearer
    KIT_CAP = {"Potion of Speed": 600}     # (450 until 10-26: the user raised it)
    # stock levels per stage (the Advisor's shops memo §3 and the Borg minimums):
    # A to 500 ft, B to 1000 ft, C deeper. No flasks: the town visit tops the lantern up instead (the user,
    # 10-25: oil, food and potions nobody uses fill the pack). Rations: one stack, eaten to Fed (at most 3) before a trip
    KITS = {"A": {"Word of Recall": 2, "Cure Light Wounds": 5, "Phase Door": 5, "Ration of Food": 3},
            "B": {"Word of Recall": 2, "Cure Critical Wounds": 4, "Cure Serious Wounds": 4, "Phase Door": 10,
                  "Ration of Food": 3, "Heroism": 3, "Potion of Speed": 2},
            "C": {"Word of Recall": 2, "Cure Critical Wounds": 6, "Cure Serious Wounds": 4, "Phase Door": 12,
                  "Ration of Food": 3, "Heroism": 3, "Potion of Speed": 2},
            "none": {}}
    # The lantern leaves town with this much fuel: a full lantern (15000) burned ~7500 in ~35 dungeon minutes
    # (m29-m30), and a trip ends within 30; a flask adds 7500 (object.txt; FUEL_LAMP 15000, mdefines.h)
    FUEL_TOPUP, FLASK_FUEL = 9000, 7500
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
        spare gold (`spare`, at 110% of the price; None: not counted) and `order enchant_max` for them all together."""
        left = int(self.orders.get("enchant_max", 25))
        out = []
        for kind in self.ENCHANT_KINDS:
            price = self.price_of(kind, 5) or 190
            n = min(int(round(self.enchant_scrolls_wanted(kind))), left)
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

    def lantern_fuel(self):
        """Turns of fuel in the lantern (worn, else the best in the pack), or None without one."""
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
        with 9000+ turns)."""
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

    def is_crutch(self, it):
        return not self.live and it["tval"] in (55, 65, 66) and \
            any(k in it["name"] for k in self.CRUTCH_DEVICES)

    def town_sell_count(self, it):
        """How many of this pack item the town kit sells (0: keep it)."""
        name = it["name"]
        if self.is_crutch(it) and not it.get("equip") and self.town_buyers(it):
            return it["number"]
        # (food other than rations, and flasks the lantern doesn't need, are sold: one food source, no oil)
        spare = (it["tval"] == TV_FOOD and "Ration" not in name and "Mushroom" not in name) or \
            (it["tval"] == TV_FLASK and (self.lantern_fuel() or 0) >= self.FUEL_TOPUP)
        # (one lantern is enough -- the user, 10-26: "why two lanterns?" -- the fullest is kept, worn or in the pack;
        # a spare is sold)
        if it["tval"] == TV_LITE and "Lantern" in name and not it.get("equip"):
            others = [i for i in self.w.items(equip=True) + self.w.items() if i["tval"] == TV_LITE and
                      "Lantern" in i["name"] and i["item"] != it["item"]]
            spare = any(self.light_left(o) >= self.light_left(it) for o in others)
        # (a staff doing what a carried rod does is spare: m43 carried a Staff of Door/Stair Location beside the Rod)
        rod_dup = it["tval"] == 55 and any(i["tval"] == 66 and re.sub(r".*\bof ", "", re.sub(r"\s*\(.*", "", i["name"]))
                                           in name for i in self.w.items())
        if it.get("equip") or (it["tval"] in (TV_FOOD, TV_FLASK, TV_LITE) and not spare) or \
                self.is_kit_item(it) \
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
        if iv.kind is None or iv.value <= 0 or iv.value * self.pay_cut(iv.tval) < 1:
            return 0
        return it["number"]

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
        """The town visit's last step: fill the lantern from the flasks bought for it (worn: it refuels the
        light in hand), then eat rations until Fed (at most 3) -- not Full: a ration is 5000 food, Full starts at 10000
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
        if fuel is not None and fuel < self.FUEL_TOPUP and flask and kit.fuelled < 3:
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
        kit = kit or ("A" if want < 500 else "B" if want < 1000 else "C")
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
        fuel = self.lantern_fuel()
        if fuel is not None and fuel < self.FUEL_TOPUP:
            add(2, "Flask of oil", -(-(self.FUEL_TOPUP - fuel) // self.FLASK_FUEL))
        for stat, (cur, top) in (self.seen_drained or {}).items():
            if stat in self.STAT_FULL and cur < top:
                if not self.stash_has(f"Restore {self.STAT_FULL[stat]}"):     # (fetched from the stash instead)
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

    def restore_potion(self, skip=()):
        """A Potion of Restore <stat> in the pack for a drained STR/DEX/CON, or None."""
        full = dict(self.STAT_FULL, CHR="Charisma")
        for stat, (cur, top) in (self.seen_drained or {}).items():
            if stat in full and cur < top:
                pot = next((i for i in self.w.items(tval=TV_POTION) if f"Restore {full[stat]}" in i["name"]
                            and i["name"] not in skip), None)
                if pot:
                    return pot
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
    def is_stash_item(self, name):
        # (stat restores only: a Potion of Restore Mana went into the stash in m48 -- useless to a warrior)
        return bool(re.search(r"Potions? of Restore (Strength|Intelligence|Wisdom|Dexterity|Constitution|Charisma)",
                              name)) or ("Stone to Mud" in name and "Wand" in name)

    def tavern_state(self):
        """The no-house fallback's record in house.json: the tavern's entrance and the stash items in its room."""
        return self.house_state().setdefault("tavern", {})

    def stash_places(self):
        """{'house': {"Y,X": name}, 'tavern': {"Y,X": name}}: what the stash holds and where (the house's items count
        only while a house is owned)."""
        st = self.house_state()
        return {"house": st.get("items", {}) if st.get("house") else {},
                "tavern": st.get("tavern", {}).get("items", {})}

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
                    if key in singular(str(nm)):
                        n += 1
        return n

    def stash_take(self, at, kind, square=None):
        """Strike one item of this kind off the record of `at` (house|tavern): the one on `square` if it's there."""
        slots = self.house_state().get("items", {}) if at == "house" else self.tavern_state().get("items", {})
        key = f"{square[0]},{square[1]}" if square else None
        key = key if key in slots and kind in slots[key] else next((k for k, n in slots.items() if kind in n), None)
        if key:
            del slots[key]
            self.house_save()

    BANK_FLOAT = 300           # gold carried out of town when a house holds the rest (no use for it in the dungeon)

    # (the user, 10-28: "is the Navigator made aware of how much time until we are Starving or without light?")
    # The lantern burns a turn of fuel a player turn, ~215 a dungeon minute with the resting/running speed-ups
    # (FIELD-NOTES: 15000 -> 7500 in ~35 dungeon minutes, m29-m30). Food: 20 a food tick every 10 player turns at
    # normal speed, 10 with slow digestion (dungeon.c:1129-1147), none in town -- 1 or 2 a player turn, so on the same
    # clock. Food runs from the hunger level's middle (the client sends the level only) down to Weak (1000).
    TURNS_PER_DMIN = 215
    FOOD_MID = {0: 750, 1: 750, 2: 1500, 3: 6000, 4: 12500, 5: 15000}

    def supply_minutes(self):
        """(food, light): dungeon minutes left counting the reserves (rations and other food; flasks), or None for a
        light that needs no fuel."""
        w = self.w
        per_turn = 1.0 if (w.flags or {}).get("slow_digest") else 2.0
        reserve = sum(self.food_value(i["name"]) * i["number"] for i in w.items(tval=TV_FOOD)
                      if "Mushroom" not in i["name"])
        food = max(0.0, self.FOOD_MID.get(w.hunger, 6000) + reserve - 1000) / (per_turn * self.TURNS_PER_DMIN)
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
                spare = sum(t * i["number"] for i in w.items(tval=TV_LITE) if not i.get("equip")
                            for t in [light_turns(i["name"])] if t is not None)
                light = (m + spare) / self.TURNS_PER_DMIN
        else:
            flasks = sum(i["number"] for i in w.items(tval=TV_FLASK))
            light = (fuel + flasks * self.FLASK_FUEL) / self.TURNS_PER_DMIN
        return food, light

    def supply_text(self):
        food, light = self.supply_minutes()
        return f"food ~{food:.0f} dungeon min, light ~{light:.0f}" if light is not None else \
            f"food ~{food:.0f} dungeon min, light permanent"

    def supply_watch(self):
        """In the dungeon: tell the Navigator once when food or light (reserves counted) falls under 15, then 5,
        dungeon minutes; and, as news, once a trip when the pack holds no food (m46's Navigator found "Food 0" with no
        warning; the cause, make-room destroying rations, is fixed, but eating the last one isn't -- food_watch, merged
        here by D14). All are `supplies` notices with fields what (food|light) and level (low|out|recalling)."""
        w = self.w
        if not w.in_dungeon:
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
