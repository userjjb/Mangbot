"""items -- the Pilot's item policy, as a mixin of Pilot (refactor-candidates E1; docs/pilot-items.md): values and the
Navigator's debt (iv, pay_cut, value_refusal, add_debt, settle_hunt), pickup, loot and junk (pickup_room, pack_value,
destroy_count, the supplies by need, loot_step, is_junk, auto_destroy, destroy_floor_junk), the flavour table
(load_flavours, learn_flavour, learn_flavours_tick), identify and the upgrades (policy_tick, identify_step,
upgrade_step, weapon_table, wear_step), the review queue and the light helpers (keep_light, light_left, wear_light...),
with the server's blow table (weapon_blows) and type_word. The methods stay Pilot's: they read and write the Pilot's
state through self; pilot.py imports the module's names back (P.weapon_blows, P.PY_FOOD_MAX, ...).
"""
import collections
import csv
import json
import math
import os
import re
import sys
import time

import geareval
import itemvalue
from common import (HERE, TV_SCROLL, TV_POTION, TV_FOOD, TV_FLASK, TV_LITE, weapon_brand, weapon_damage, flavour_key,
                    kind_key, bare_name, one_of, singular, bad_inscription, mission_tag)
import stomach
from world import gnow, light_fuel, light_turns, waited
from goals import Wait, Goto, Recover, Flee, Recall, RestGoal
from town_goals import Shop, TownKit
if os.path.join(HERE, "..", "observe") not in sys.path:     # (shopmath, as pilot.py loads it)
    sys.path.insert(0, os.path.join(HERE, "..", "observe"))
import shopmath                                  # noqa: E402

PY_FOOD_MAX = 15000          # Gorged (-10 speed) from here (mdefines.h)


# Blows per round, as the server computes them (xtra1.c ~2950, tables.c;
# warrior p_class A:6:30:5). Stat values as the indicators send them: 3..18,
# then 18 + xx for 18/xx.
ADJ_STR_BLOW = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 20, 30, 40, 50, 60, 70, 80, 90, 100,
                110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230, 240]
ADJ_DEX_BLOW = [0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 4, 4, 5, 6, 7, 8, 9, 10,
                11, 12, 14, 16, 18, 20, 20, 20]
ADJ_STR_HOLD = [4, 5, 6, 7, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 30, 35, 40, 45, 50, 55, 60, 65,
                70, 80, 80, 80, 80, 80, 90, 90, 90, 90, 90, 100, 100, 100]
BLOWS_TABLE = [
    [1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3], [1, 1, 1, 1, 2, 2, 3, 3, 3, 4, 4, 4],
    [1, 1, 2, 2, 3, 3, 4, 4, 4, 5, 5, 5], [1, 2, 2, 3, 3, 4, 4, 4, 5, 5, 5, 5],
    [1, 2, 2, 3, 3, 4, 4, 5, 5, 5, 5, 5], [2, 2, 3, 3, 4, 4, 5, 5, 5, 5, 5, 6],
    [2, 2, 3, 3, 4, 4, 5, 5, 5, 5, 5, 6], [2, 3, 3, 4, 4, 4, 5, 5, 5, 5, 5, 6],
    [3, 3, 3, 4, 4, 4, 5, 5, 5, 5, 6, 6], [3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6],
    [3, 3, 4, 4, 4, 4, 5, 5, 5, 6, 6, 6], [3, 3, 4, 4, 4, 4, 5, 5, 6, 6, 6, 6]]
WARRIOR = (6, 30, 5)          # max_attacks, min_weight (tenth lb), att_multiply
TV_WEAPONS = (20, 21, 22, 23)


def stat_index(v):
    return max(0, min(37, v - 3 if v <= 18 else 15 + (v - 18) // 10))


def weapon_blows(weight, str_v, dex_v, cls=WARRIOR):
    """Blows per round with a weapon of `weight` tenth-pounds."""
    si, di = stat_index(str_v), stat_index(dex_v)
    if weight // 10 > ADJ_STR_HOLD[si]:
        return 1                                   # too heavy to wield properly
    div = max(weight, cls[1])
    s_i = min(11, ADJ_STR_BLOW[si] * cls[2] // div)
    d_i = min(11, ADJ_DEX_BLOW[di])
    return max(1, min(cls[0], BLOWS_TABLE[s_i][d_i]))


def type_word(name):
    """'Amber Amulet' / 'Scroll titled "foo"' / 'Potion of Speed' -> 'Amulet' / 'Scroll' / 'Potion' (None if
    none): a flavour and the kind it's paired with must agree on it (refactor-candidates A2)."""
    n = re.sub(r'"[^"]*"', "", name).split(" of ")[0]
    m = re.search(r"\b(Potion|Scroll|Wand|Staff|Rod|Ring|Amulet|Mushroom)s?\b", n)
    return m.group(1) if m else None


class ItemsMixin:
    """Pilot's item-policy methods (`class Pilot(ReportMixin, GearMixin, ItemsMixin)`: every name stays on Pilot)."""

    def pack_kinds(self):
        """{(tval, name)} of the pack, names without counts/inscriptions."""
        return {(i["tval"], kind_key(i["name"]) if " of " in i["name"] else flavour_key(i["name"]))
                for i in self.w.items() if i["tval"] in self.FLAVOURED or
                (i["tval"] == TV_FOOD and "Mushroom" in i["name"])}

    def watch_flavours(self):
        self.flavour_watch = {"t": gnow(), "before": self.pack_kinds(),
                              "unknown": {(i["tval"], flavour_key(i["name"])) for i in self.w.items()
                                          if self.unknown_flavour(i)}}

    def learn_flavours_tick(self, now):
        """After a read/quaff/use/aim/zap (incl. Identify): an unknown flavour
        that disappeared while a known kind of the same type appeared is that
        kind (the Advisor's flavour-messages memo: names drop the flavour once
        it's aware, so diff the pack)."""
        it = self.id_target
        if it:
            for ts, t in self.w.messages:
                m = re.match(r"^(?:In your pack|You are wearing|You are wielding|On your [^:]+|In your quiver): "
                             r"(.+?) \(([a-z])\)\.?$", t)
                if ts >= it["t"] and m and " of " in m.group(1) and it["letter"] in (None, m.group(2)):
                    self.learn_flavour(it["flavour"], kind_key(m.group(1)), "identified")
                    self.id_target = None
                    break
            if self.id_target and waited(it["t"], 5):
                self.id_target = None
        fw = self.flavour_watch
        if not fw or not waited(fw["t"], 1.0):
            return
        self.flavour_watch = None
        after = self.pack_kinds()
        gone = {k for k in fw["unknown"] if k not in after}
        new = {k for k in after - fw["before"]}
        said = [t for ts, t in self.w.messages if ts >= fw["t"] - 0.05]
        for j, t in enumerate(said):            # a stack used up: "You have no more Potions of X."
            m = re.match(r"You have no more (.+?)\.?$", t)
            # (not one destroyed, dropped or sold: mission 16's autodestroyed
            # Ring of Teleportation spoiled the Beryl Ring read next to it)
            if j and said[j - 1].startswith(("You destroy", "You drop", "You sold", "You have no room")):
                continue
            if m and " of " in m.group(1):
                k = kind_key(m.group(1))
                # (only an unknown of the same type: any vanished unknown made "Amber Amulet" = Scroll of Identify)
                tv = next((tv for tv, g in gone if type_word(g) == type_word(k)), None)
                if tv is not None and (tv, k) not in fw["before"]:
                    new.add((tv, k))
        for tv in {t for t, _ in gone}:
            g = [n for t, n in gone if t == tv]
            n = [k for t, k in new if t == tv and " of " in k]
            if len(g) == 1 and len(n) == 1:
                self.learn_flavour(g[0], n[0], "identified or used")

    def phase_item(self):
        """The Phase Door to read: the item inscribed @r1 first (the player's pick; refactor-candidates D4: the fear
        phases used to skip it), else the first Phase Door in the pack; None without one."""
        tag = self.w.tagged("r", 1)
        # (only a Phase Door: tagged() also returns any item inscribed a plain @1)
        if tag and tag["tval"] == TV_SCROLL and "Phase Door" in tag["name"]:
            return tag
        return self.find_item("Phase Door", TV_SCROLL)

    def named(self, name):
        """A name with what the flavour table knows of it (2.62.0, m67): 'a Rhodonite Ring (= Ring of Stupidity,
        junk)'; unchanged for a known kind or an unknown flavour."""
        if " of " in name:
            return name
        f = self.flavours.get(flavour_key(name))
        return f"{name} (= {f['kind']}{', junk' if f.get('junk') else ''})" if f and f.get("kind") else name

    def find_item(self, word, tval):
        """The first pack item of `tval` whose name holds `word` (case as written), or None (refactor-candidates D4)."""
        return next((i for i in self.w.items(tval=tval) if word in i["name"]), None)

    # --- the value policy and the Navigator's debt (restructure step 2.1) -------
    def value_refusal(self, it, action, role=None):
        """Why the Navigator shouldn't sell/destroy/drop this item, or None. The
        Pilot's own policy never does these; the Navigator may override with `!`,
        and the value lost is added to its debt (the user's decision)."""
        if (role or self.req_role) in ("architect", "pilot") or not it:
            return None
        name = it["name"]
        if self.is_kept(name):
            return "you said keep it (`keep -NAME` releases it)"
        # (2.50.0, the user: a backup for a worn slot and the store list are stored in the house, never sold)
        why = (self.stash_backup(it) or ("on the store list" if self.on_store_list(name) else None)) \
            if action in ("sell", "destroy", "drop") and not it.get("equip") and "tval" in it else None
        if why:
            return f"{why}: plan town stores it in the house (`house withdraw NAME` fetches it back)"
        if self.ability_sources and self.iv(name).known is False and \
                any(s == bare_name(name).lower() for s in self.ability_sources):
            return (f"it may be what gives you {', '.join(sorted(self.inferred))} (seen in play, not identified): "
                    "identify it first")
        junk = (self.flavour_of(it) or {}).get("junk") or bad_inscription(name)
        if junk:
            return None
        iv = self.iv(name)
        fair = round(iv.value * self.pay_cut(iv.tval))
        if not iv.known and iv.p_irreplaceable >= 0.2:
            return (f"unidentified, and {iv.p_irreplaceable:.0%} of these carry an ego you can't buy back (Free "
                    "Action, resists...): identify it first")
        if not iv.known and fair >= 30:
            return (f"unidentified: identified it would sell for ~{fair} (an estimate; this sale would pay its bare "
                    "kind price); identify it first (a Scroll of Identify costs ~40-80)")
        if action in ("destroy", "drop") and iv.irreplaceable:
            return "it gives an ability or resist you can't easily buy back"
        if action in ("destroy", "drop") and fair >= 20:
            return f"a shop pays ~{fair} for it: sell it instead"
        return None

    def pay_cut(self, tval=None):
        """What a shop pays of an item's value (restructure step 3: shopmath and the owners, not one
        38% for everything): shopmath.pay_cut -- the best of the shops that buy this kind of item, by the owner we
        last saw there, else the average owner of that shop, at the current CHR; SHOP_CUT when nothing is known
        (D9: the rule moved to shopmath for the scorecard; the cache stays here)."""
        chr_v = (self.w.ind.get("stat5") or [3])[0] if self.w.ind else 3
        owners = {k: (v or {}).get("owner") for k, v in self.stores_seen.items()}
        key = (tval, chr_v, tuple(sorted(owners.items())))
        cache = self._pay_cache
        if key not in cache:
            cache[key] = shopmath.pay_cut(tval, chr_v, owners)
        return cache[key]

    def iv_at(self, name, q):
        """itemvalue for an item lying on square q (2.62.0, generate.c build_vault): on a matched vault's '9' square it
        was made good at the depth + 7, on an '8' square great at the depth + 20 -- an unfelt weapon or armour piece
        there is valued as felt {good} / {excellent} at that level; anywhere else, iv."""
        v = (self.vaults or {}).get(self.w.level_t) or {} if self.w else {}
        kind = "great" if q in v.get("great", ()) else "good" if q in v.get("good", ()) else None
        if not kind:
            return self.iv(name)
        level = max(1, (self.w.depth_ft or self.deepest_ft or 750) // 50) + (20 if kind == "great" else 7)
        base = itemvalue.value(name, level, self.aware_kinds())
        if base.tval in geareval.SLOT_OF_TVAL and not re.search(r"\{[^}]*\}|\([+-]\d+,|\[\d+,", name):
            return itemvalue.value(f"{name} {{{'excellent' if kind == 'great' else 'good'}}}", level, self.aware_kinds())
        return base

    def iv(self, name):
        """itemvalue.value with the depth items now come from (for expectations) and
        the kinds already known (the flavour table)."""
        level = max(1, (self.w.depth_ft or self.deepest_ft or 750) // 50)
        return itemvalue.value(name, level, self.aware_kinds())

    def aware_kinds(self):
        """The kinds the flavour table knows, lower case without the type word ('cure light wounds'): what iv passes
        to itemvalue as `aware`, and what the state snapshot logs (D9: the scorecard values as of then)."""
        if self.aware_cache[0] != len(self.flavours):
            self.aware_cache = (len(self.flavours), {re.sub(r"^(Potion|Scroll|Ring|Amulet|Wand|Staff|Rod) of ", "",
                                                            f.get("kind", "")).lower() for f in list(self.flavours.values())})
        return self.aware_cache[1]

    def is_kept(self, name):
        b = bare_name(name).lower()
        # (singular too: "staff of teleportation" on the keep list missed "2 Staffs of Teleportation")
        return any(k in b or k in singular(b) for k in self.keep)

    def debt_total(self):
        return sum(e.get("gold", 0) for e in self.debt.get("entries", []))

    def add_debt(self, gold, what, why):
        if gold <= 0:
            return
        self.debt.setdefault("entries", []).append({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "gold": int(gold),
                                                    "what": what, "why": why})
        json.dump(self.debt, open(self.debt_path, "w"), indent=1)
        self.log("navigator_debt", gold=int(gold), what=what, why=why, total=self.debt_total())

    def override_allowed(self, kind="item"):
        """Overrides stay allowed until the user or the Architect revokes them. The
        limit is a judgement, not a number (the user: hidden, so we keep leeway
        and the Navigator can't tell how close it is): revoked = the file
        runs/private/NICK.overrides_revoked exists (its text says why); for hunts,
        NICK.hunt_overrides_revoked."""
        path = os.path.join(os.path.dirname(os.path.dirname(self.rundir.rstrip("/"))), "private",
                            os.path.basename(self.rundir.rstrip("/")) +
                            (".hunt_overrides_revoked" if kind == "hunt" else ".overrides_revoked"))
        return not os.path.exists(path)

    def fight_debt_total(self):
        return sum(e.get("hp", 0) for e in self.debt.get("fight_entries", []))

    def settle_hunt(self, g, status, detail):
        """Judge a hunt the Navigator ordered over the Pilot's refusal (the user, 2026-10-23:
        it may override, and if it was wrong the cost goes into a fight debt kept apart
        from the item debt). Wrong = not slain, or HP fell below half, or an emergency
        escape fired during it. The debt is the HP it cost (start to lowest)."""
        ov, w = g.overridden, self.w
        g.overridden = None
        lost = max(0, ov["hp0"] - ov["hp_min"])
        emerg = len(self.emerg_times) - ov["emerg0"]
        # (A23: the parentheses -- a failed hunt whose detail said "killed" counted as slain, so no fight debt)
        slain = status == "done" and ("slain" in str(detail) or "killed" in str(detail))
        wrong = not slain or ov["hp_min"] < 0.5 * max(1, w.hp[1]) or emerg > 0
        self.log("hunt_override_end", target=g.target, status=status, detail=detail, hp_lost=lost,
                 hp_min=ov["hp_min"], emergencies=emerg, wrong=wrong)
        if not wrong or not lost:
            self.notify("tactic", f"your override hunt of {g.target}: {detail or status}, {lost} HP lost; the "
                                  "Pilot's refusal was too cautious this time (no debt)", news=True)
            return
        self.debt.setdefault("fight_entries", []).append(
            {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "hp": int(lost), "what": f"hunt {g.target}",
             "why": f"{detail or status}; lowest HP {ov['hp_min']}" + (f", {emerg} emergencies" if emerg else "") +
                    f" (refused because: {ov['why'][:120]})"})
        json.dump(self.debt, open(self.debt_path, "w"), indent=1)
        self.log("navigator_fight_debt", hp=int(lost), what=g.target, total=self.fight_debt_total())
        self.notify("tactic", f"your override hunt of {g.target} went wrong ({detail or status}, {lost} HP lost"
                              f"{', an emergency escape' if emerg else ''}): {lost} added to your fight debt", news=True)

    KIT_KINDS = ("Cure Light Wounds", "Cure Serious Wounds", "Cure Critical Wounds", "Healing", "Phase Door",
                 "Word of Recall", "Teleport", "Identify", "Magic Mapping", "Speed", "Heroism", "Berserk",
                 "Restore", "Deep Descent", "Resist Poison")    # (not Boldness: Heroism does all it does, the user;
    # 2.48.0, the user: Heroism's fallback -- a kit item only while Heroism is short, town.FALLBACKS / fallback_kept)
    # what a kit consumable found in the dungeon is worth to us: what replacing it costs (the Alchemist's price
    # last seen, else these; Speed, Healing and Berserk only at the Black Market). m36 left a Potion of Speed,
    # "pack full and nothing cheaper (~34)", with no Speed in the pack and junk weapons in it
    KIT_USE = {"Speed": 600, "Healing": 1500, "Berserk": 500, "Teleport": 150, "Heroism": 60, "Magic Mapping": 65,
               "Deep Descent": 100, "Resist Poison": 100, "Restore": 480}

    def is_kit_item(self, it):
        """A kit consumable: a potion or scroll of a kit kind. (Not a staff or wand with the same words: m43 kept two
        Staffs of Cure Light Wounds as if they were the potions -- the user: "2 staffs of cure light wounds?")"""
        return it["tval"] in (TV_POTION, TV_SCROLL) and any(k in it["name"] for k in self.KIT_KINDS) and \
            not self.is_crutch(it)        # (2.48.0: a Scroll of Magic Mapping on the test server is loot)

    def kit_use_value(self, name):
        """Replacement cost of a kit consumable (potion or scroll), else 0. A fallback while its kit kind is short
        (Boldness, Heroism under the kit's target) counts as one (2.48.0, the user's principle A); a crutch (a Scroll of
        Magic Mapping on the test server) doesn't."""
        m = re.match(r"(\d+) ", name)
        n = int(m.group(1)) if m else 1
        fb = next((k for k in self.FALLBACKS if k in name), None)
        if fb and re.search(r"\bPotions? of\b", name) and self.fallback_kept({"name": name, "tval": TV_POTION}):
            return (self.price_of(fb, self.KIT_ITEMS[fb][1]) or self.KIT_ITEMS[fb][2]) * n
        kind = next((k for k in self.KIT_KINDS if k in name), None)
        if not kind or not re.search(r"\b(Potions?|Scrolls?) of\b", name) or \
                (re.search(r"\bScrolls? of\b", name) and self.is_crutch({"name": name, "tval": TV_SCROLL})):
            return 0
        full = next((k for k in self.KIT_ITEMS if k in name), None)
        price = (self.price_of(full, self.KIT_ITEMS[full][1]) if full else None) or self.KIT_USE.get(kind, 0)
        return price * n

    def pack_value(self, it):
        """An item's worth to the pack, for making room: kit consumables, kept items,
        possible ability sources and the light count as priceless."""
        n = it["name"]
        # (2.48.0, the user's principle B) a dungeon stopgap -- a Scroll of Satisfy Hunger, a Wooden Torch beside a
        # lantern -- is worth the dungeon time it covers while the primary (food; the lantern's fuel and the flasks)
        # falls short of the trip's need, else its sale (and destroy_count keeps it while short)
        if self.w.in_dungeon and self.is_stopgap(it) and not self.is_kept(n):
            sale = self.iv(n).value * self.pay_cut(it["tval"]) * it["number"]
            cover = self.stopgap_cover(n, it["number"])
            return max(sale, cover * self.gold_per_dmin()) if cover > 0 else sale
        # (2.50.0, the user) in town a stash item -- a backup for a worn slot, the store list, a Restore -- is stored,
        # never sold or destroyed for room (in the dungeon it is valued as any item: unchanged)
        if not self.w.in_dungeon and not it.get("equip") and self.is_stash_item(n):
            return float("inf")
        # (2.48.0, the user) a Scroll of Enchant or Recharging the town kit would read: priceless in town (kept, and
        # read before more are bought), in the dungeon worth what buying it again costs
        if self.scroll_use(it):
            if not self.w.in_dungeon:
                return float("inf")
            kind = next((k for k in self.ENCHANT_KINDS + ("Recharging",) if k in n), "Recharging")
            return max(self.iv(n).value * self.pay_cut(it["tval"]), self.price_of(kind, 5) or 190) * it["number"]
        # A spare light beyond the first, and food beyond 5 meals (Satisfy Hunger counts), are worth what they
        # sell for: m25 kept 2 spare lanterns and a ration while it destroyed a Rod of Trap Location and a
        # Staff of Object Location to make room
        if it["tval"] == TV_LITE:
            spares = sorted((i for i in self.w.items() if i["tval"] == TV_LITE), key=lambda i: -self.iv(i["name"]).value)
            if spares and spares[0]["item"] != it["item"]:
                return self.iv(n).value * self.pay_cut(TV_LITE)
        # One food source, rations (eaten blind or confused; a Scroll of Satisfy Hunger fills to just under
        # Gorged): other food, flasks beyond what the lantern needs, and near a trip's end the spare rations
        # and flasks are worth what they sell for (the user, 10-25: food, oil and potions fill the pack)
        # In the dungeon, food (not mushrooms) and flasks by need (the user, 10-31): what lasts until the expected
        # recall plus SUPPLY_MARGIN_DMIN is needed, worth the dungeon time it buys; the rest is spare, worth its sale
        # price. (Was: rations never, flasks only near the trip's end.)
        if self.w.in_dungeon and self.supply_kind(it) and not self.is_kept(n):
            spare, short_min = self.supply_spare(it)
            if spare > 0:
                return self.iv(n).value * self.pay_cut(it["tval"]) * spare
            return short_min * self.gold_per_dmin() if short_min > 0 else self.iv(n).value * self.pay_cut(it["tval"])
        if it["tval"] == TV_FOOD and "Mushroom" not in n and ("Ration" not in n or self.provisions_spare()):
            # (never the last meal: m46 destroyed all 3 rations near a trip's end for a ~30-gold rod, and the Navigator
            # found "Food 0" -- a ration stack goes down to one, the last food item is priceless)
            if self.destroy_count(it) == 0:
                return float("inf")
            return self.iv(n).value * self.pay_cut(TV_FOOD) * self.destroy_count(it)
        # (2.49.0: in town the flasks beyond those that fill the lantern, `flasks_spare`; was: all once it had 9000)
        if it["tval"] == TV_FLASK and (self.provisions_spare() or self.flasks_spare(it)):
            return self.iv(n).value * self.pay_cut(TV_FLASK) * self.destroy_count(it)
        # (a fallback while its kit kind is short is a kit item: Boldness, Heroism under the kit's target -- 2.48.0)
        prized = self.is_kit_item(it) or self.fallback_kept(it) or self.is_kept(n) or self.gain_potion(it) or \
            bare_name(n).lower() in self.ability_sources
        # junk first: food, flasks and lights were priceless before this test, so an unknown or table-junk Mushroom
        # was never destroyed to make room (refactor-candidates A17); kit, kept and ability items stay priceless
        if not prized and ((self.flavour_of(it) or {}).get("junk") or
                           bad_inscription(n)):
            return 0
        # (mushrooms aren't food here: an unknown one is worth the average of the mushroom kinds not yet known, a known
        # one its kind's value -- itemvalue, the user 10-31; they were priceless as food)
        if (it["tval"] in (TV_FOOD, TV_FLASK, TV_LITE) and "Mushroom" not in n) or prized:
            return float("inf")
        if n in self.review_state()["items"]:
            return float("inf")            # (waiting for the Navigator's review)
        iv = self.iv(n)
        return iv.value * self.pay_cut(iv.tval) * max(1, iv.count)

    UNIQUE_DROP_BUMP = 50
    # (2.62.0, m67 21:29: 4 rations destroyed for a ~16-gold lantern) no food, oil or kit consumable is destroyed to
    # take a find worth less than this: about two dungeon minutes of play at the recent rates, and short food or light
    # ends a trip early (a recall, ~250 gold of scroll and the trip's remaining time)
    SUPPLY_SWAP_MIN = 100

    @staticmethod
    def destroyed_text(it, n):
        """'2 of 3 Rations of Food (1 kept)' when part of a stack goes, else the name (2.51.0: m62's news said
        "destroyed 3 Rations of Food" for value=2)."""
        if n >= it["number"]:
            return it["name"]
        return f"{n} of {it['name']} ({it['number'] - n} kept)"

    def eat_fits(self, name):
        """Eating this food can't make us Gorged: the most the stomach can hold (food_top) plus its food stays a
        potion margin (1000) under PY_FOOD_MAX -- the make-room rule (m49)."""
        return self.food_top() + self.food_value(name) < PY_FOOD_MAX - 1000

    def destroy_count(self, it):
        """How many of this pack item a make-room may destroy: all, except food -- rations never (one slot, cheap; the
        town visit sells extras), other food not the last of it; flasks in town, those the lantern doesn't need to fill
        it (2.49.0). A dungeon stopgap while its primary is short: none (2.48.0, the user: never discarded then)."""
        if self.w.in_dungeon and self.is_stopgap(it) and self.stopgap_cover(it["name"], it["number"]) > 0:
            return 0
        if self.w.in_dungeon and self.supply_kind(it):
            spare, _ = self.supply_spare(it)
            return spare if spare > 0 else it["number"]      # (none spare: the whole stack, at the value of its time)
        if it["tval"] == TV_FLASK and not self.provisions_spare():
            return self.flasks_spare(it)      # (2.49.0: in town, not those that fill the lantern)
        if it["tval"] == TV_FOOD and "Ration" in it["name"]:
            return 0          # (rations: never in town -- m47 cut 3 to 1 for a Staff of CLW and the Navigator bought food)
        if it["tval"] == TV_FOOD and "Mushroom" not in it["name"]:
            others = sum(i["number"] for i in self.w.items() if i["tval"] == TV_FOOD and "Mushroom" not in i["name"]
                         and i["item"] != it["item"])
            return it["number"] if others else it["number"] - 1
        return it["number"]

    def weight_room(self):
        """Tenth-pounds the pack can still take before the weight limit slows us (xtra1.c:2772: over half of
        adj_str_wgt x 100), and the current speed lost to weight."""
        w = self.w
        t = geareval.stat_table()
        limit = t[geareval.stat_index((w.ind.get("stat0") or [18])[0])]["adj_str_wgt"] * 100
        load = sum(i["weight"] for i in w.items() + w.items(equip=True))
        slow = (load - limit // 2) // (limit // 10) if load > limit // 2 else 0
        return limit // 2 - load, slow

    # the food in each kind we may eat (object.txt pvals; mushrooms 500). The hunger levels' bounds are stomach.BOUNDS
    # (2.49.0: FOOD_TOP went with the tracker)
    FOOD_VALUES = (("Ration", 5000), ("Biscuit", 500), ("Jerky", 1500), ("Slime Mold", 3000), ("Waybread", 7500),
                   ("Ale", 500), ("Wine", 1000), ("Potato", 1500), ("Cabbage", 1500), ("Carrot", 500), ("Beet", 750),
                   ("Squash", 2000), ("Corn", 1500))

    @classmethod
    def food_value(cls, name):
        return next((v for k, v in cls.FOOD_VALUES if k in name), 500)

    SUPPLY_MARGIN_DMIN = 5         # dungeon minutes of food and light kept beyond the expected recall (the user, 10-31)
    SUPPLY_UNKNOWN_DMIN = 40       # the horizon when no trip end is known, e.g. a hand-given goal (the user, 10-31)

    @staticmethod
    def supply_kind(it):
        """'food' (not mushrooms), 'oil' (flasks), or None: the supplies valued by need in the dungeon."""
        if it["tval"] == TV_FOOD and "Mushroom" not in it["name"]:
            return "food"
        return "oil" if it["tval"] == TV_FLASK else None

    def supply_horizon(self):
        """Dungeon minutes of food and light needed from now: the expected recall plus the margin."""
        left = self.trip_minutes_left()
        return (self.SUPPLY_UNKNOWN_DMIN if left is None else left) + self.SUPPLY_MARGIN_DMIN

    # --- the stomach tracker (2.49.0, the user: calibrated by the hunger crossings; stomach.py has the server's rules)
    def food_now(self):
        """The least food the stomach can hold now: the bottom of the tracker's range (exact once a crossing has pinned
        it), else of the hunger level (Fed: 2000) -- what spare/short decisions and the food minutes count on (2.48.1
        took the level's bottom, `food_floor`; the middle stood still and ran out in m61)."""
        return self.stomach.range(self.w.hunger)[0]

    def food_top(self):
        """The most food the stomach can hold now: the top of the tracker's range, else of the hunger level."""
        return self.stomach.range(self.w.hunger)[1]

    def stomach_tick(self, now):
        """Every tick: the tracker's look at the hunger indicator (once the server has sent one), the game clock, the
        worn light's fuel (its tick clock), the depth, the speed and the regeneration / slow-digestion flags; a log
        record for a pin, a meal, a re-widening; saved for a restart on a change and every 30 s (no clock read
        otherwise: the equivalence harness's fake clock moves on each read)."""
        w = self.w
        if "hunger" not in w.ind or w.depth is None:
            return
        flags = w.flags or {}
        ev = self.stomach.update(w.hunger, now, fuel=light_fuel(w.inven), depth=w.depth,
                                 speed=(w.ind.get("speed") or [0])[0] or 0, regen=bool(flags.get("regen")),
                                 slow=bool(flags.get("slow_digest")), count_of=self.kind_count,
                                 ghost=bool(getattr(w, "ghost", False)),
                                 wall=time.time() if self.stomach.level is None else None)
        for e in ev:
            self.log("stomach", **e)
        if ev or now - self.stomach_saved_t > 30:
            self.stomach_saved_t = now
            try:
                with open(os.path.join(self.rundir, "stomach.json"), "w") as f:
                    json.dump(self.stomach.to_json(time.time(), w.depth), f)
            except (AttributeError, OSError):
                pass

    def kind_count(self, key):
        """The pack's count of a kind (kind_key_of), from the pack as last read (no new query)."""
        return sum(i["number"] for i in self.w.inven or () if not i.get("equip") and self.kind_key_of(i["name"]) == key)

    def stomach_sent(self, line):
        """An eat / quaff / read command just sent (ours or the Navigator's): the tracker waits for the pack to show
        the item eaten, then adds its food (stomach.meal_effect)."""
        m = re.match(r"(?:eat |custom [Eqr] item=)(\d+)\b", line)
        if not m or self.stomach is None:
            return
        it = next((i for i in self.w.inven or () if not i.get("equip") and i["item"] == int(m.group(1))), None)
        if not it:
            return
        eff = stomach.meal_effect(it["tval"], it["name"], self.food_value, unknown=self.unknown_flavour(it))
        if eff:
            key = self.kind_key_of(it["name"])
            # (2.53.0: one of the stack is eaten -- m63 logged "3 Rations of Food" for one)
            self.stomach.sent(key, self.kind_count(key), eff, gnow(), name=one_of(it["name"]))

    def supply_spare(self, it):
        """(units of this food or flask stack not needed before the horizon, dungeon minutes of the shortfall this
        stack covers). Needed = what the stomach (or the lantern) and the other stacks of the same supply don't cover
        (the user, 10-31: leave Full and topped up, recall before starving or the light runs out; when the pack is full
        eat, fill the lantern, and discard the extra)."""
        w, kind = self.w, self.supply_kind(it)
        need = self.supply_horizon()
        if kind == "food":
            per = (1.0 if (w.flags or {}).get("slow_digest") else 2.0) * self.TURNS_PER_DMIN
            # (2.48.1, m61: the bottom of the hunger level, not its middle -- Fed is 2000-10000 food; the middle said ~25
            # dungeon minutes left, make-room destroyed 8 of 9 rations as spare, and food ran out 5 minutes later)
            have = max(0.0, self.food_now() - 1000) / per
            unit = self.food_value(it["name"]) / per
        else:
            lamp = next((i for i in w.items(equip=True) if i["tval"] == TV_LITE and "Lantern" in i["name"]), None)
            lt = light_turns(lamp["name"]) if lamp else None
            if lt is None:
                return it["number"], 0.0          # (no lantern to fill: oil is only worth its sale)
            have = lt / self.TURNS_PER_DMIN
            unit = self.FLASK_FUEL / self.TURNS_PER_DMIN
        others = sum((self.food_value(i["name"]) / per if kind == "food" else unit) * i["number"]
                     for i in w.items() if self.supply_kind(i) == kind and i["item"] != it["item"])
        short = max(0.0, need - have - others)
        units = min(it["number"], math.ceil(short / unit)) if unit > 0 else it["number"]
        # (2.65.0, m68 00:11: all 4 rations destroyed for a Staff of Trap Location -- the trip ended in 8 minutes and
        # the stomach held 19, so none were "needed"; then "no food left" and a "~15 min" alert. The last ration of the
        # pack's food stays: the m46 rule, now in the dungeon too)
        if kind == "food" and not others and units < 1:
            return it["number"] - 1, unit          # (valued as the dungeon minutes it gives)
        return it["number"] - units, min(short, units * unit)

    # the food a Scroll of Satisfy Hunger counts as: it fills to just under Gorged and is read at Weak (combat.py), less a
    # potion's margin
    SATISFY_FOOD = PY_FOOD_MAX - 2000

    def supply_short(self, kind):
        """Dungeon minutes of the horizon's need (supply_horizon) that the stomach and every food stack ('food'), or the
        lantern and every flask ('oil': the worn lantern, else the fullest carried; none: 0), leave uncovered -- what a
        stopgap covers (2.48.0)."""
        w = self.w
        need = self.supply_horizon()
        if kind == "food":
            per = (1.0 if (w.flags or {}).get("slow_digest") else 2.0) * self.TURNS_PER_DMIN
            have = max(0.0, self.food_now() - 1000) / per + \
                sum(self.food_value(i["name"]) * i["number"] for i in w.items() if self.supply_kind(i) == "food") / per
        else:
            fuel = self.lantern_fuel()
            if fuel is None:
                return 0.0
            have = (fuel + self.FLASK_FUEL * sum(i["number"] for i in w.items(tval=TV_FLASK))) / self.TURNS_PER_DMIN
        return max(0.0, need - have)

    def is_stopgap(self, it):
        """B (2.48.0, the user): a dungeon stopgap -- a Scroll of Satisfy Hunger (for rations), a Wooden Torch while a
        lantern with fuel is worn or carried (for its fuel)."""
        return (it["tval"] == TV_SCROLL and "Satisfy Hunger" in it["name"]) or \
            (it["tval"] == TV_LITE and "Torch" in it["name"] and not it.get("equip") and self.lantern_lit())

    def stopgap_cover(self, name, n=None):
        """Dungeon minutes of the trip's shortfall `n` of this stopgap cover (a pack item's or the floor's name; n from
        the name if not given): Scrolls of Satisfy Hunger while the food falls short (SATISFY_FOOD each), Wooden Torches
        while a lantern's fuel and the flasks do (their turns). 0 in town, for anything else, or with the primary not
        short."""
        if not self.w.in_dungeon:
            return 0.0
        if n is None:
            m = re.match(r"(\d+) ", name)
            n = int(m.group(1)) if m else 1
        if re.search(r"\bScrolls? of Satisfy Hunger\b", name):
            per = (1.0 if (self.w.flags or {}).get("slow_digest") else 2.0) * self.TURNS_PER_DMIN
            short, unit = self.supply_short("food"), self.SATISFY_FOOD / per
        elif re.search(r"\bWooden Torch(es)?\b", name) and self.lantern_lit():
            short, unit = self.supply_short("oil"), (light_turns(name) or 0) / self.TURNS_PER_DMIN
        else:
            return 0.0
        return min(short, n * unit)

    def gold_per_dmin(self):
        """Gold-equivalent earned per minute of play (gold found + sold, plus XP at the XP-per-gold rate), from the
        rate buckets (10-minute buckets with a gain; seeded like xp_per_gold): what a minute more in the dungeon is worth."""
        b = self.rate_state()["buckets"]
        seed_w = max(0.0, 1 - len(b) / self.RATE_WINDOW)
        xp = sum(x[1] for x in b) + seed_w * self.RATE_SEED[0]
        gold = sum(x[2] for x in b) + seed_w * self.RATE_SEED[1]
        mins = len(b) * self.RATE_BUCKET_S / 60 + seed_w * self.RATE_SEED_MIN
        return (gold + xp / max(0.1, self.xp_per_gold())) / max(1.0, mins)

    HEAVY_LOOT_MIN = 300      # gold: below this, loot that would slow us is left
    JUNK_DEVICES = ("Haste Monsters", "Clone Monster", "Heal Monster")

    def town_books(self):
        """The spellbooks the town sells ('[magic for beginners]', ...): the rulebook's stock table, tvals 90/91
        (the Magic-User store and the Temple). Cheap, so junk for a warrior; the dungeon-only books sell well."""
        if self._town_books is None:
            self._town_books = {r["item_name"].lower() for r in self.stock_table() if r.get("tval_num") in ("90", "91")}
        return self._town_books

    def is_junk(self, it):
        """Junk (destroyed in the pack and underfoot, not picked up or reported), one rule for all three (refactor-
        candidates D3; the user, 11-01: the union of the old lists). `it` is a pack item or a name (the floor, the
        item list). Never a kept item, nor one inscribed with @ or with ! in its tag. Junk is: a kind on the junk order
        or a harmful device (JUNK_DEVICES; m28 kept a Staff of Haste Monsters after Identify), "of" it as a whole
        word (not Resist/Neutralize Poison, Cure Blindness: the old suffix match took them); a kind the rulebook
        marks worthless at every level; a flavour the flavour table marks junk though the character doesn't know it
        (mission 21: an unknown Summon Undead took the slot freed for an {excellent} armour); Broken items; a
        pseudo-ID feeling on the autodestroy order (cursed, worthless); for a warrior, the spellbooks the town sells
        (the user, 11-01: the dungeon-only books are loot)."""
        name = it if isinstance(it, str) else it["name"]
        name = name.rstrip(".")
        tags = re.findall(r"\{([^}]*)\}", name)
        if any("@" in t or "!" in t for t in tags) or self.is_kept(name):
            return False
        # (2.48.0, the user's principle B: a dungeon stopgap is never auto-destroyed while its primary is short)
        if self.stopgap_cover(name) > 0:
            return False
        # (2.62.0, m67 21:29: a Brass Lantern, ~16 gold, picked up -- 4 rations destroyed for its weight -- with the
        # Phial worn: a fuelled light is junk while a light needing no fuel is worn)
        if re.search(r"\b(Brass Lantern|Wooden Torch)", name) and any(
                i["tval"] == TV_LITE and self.light_radius(i)[1] for i in self.w.items(equip=True)):
            return True
        n = name.lower()
        bare = singular(bare_name(n).strip())
        kind = kind_key(name)
        junk = [j.strip().lower() for j in self.orders.get("junk", "").split(",") if j.strip()] + \
            [j.lower() for j in self.JUNK_DEVICES]
        # (2.60.0, m67: the whole kind, not its first word -- "Sleep" (Potion of Sleep) junked the Wand of Sleep
        # Monster; after the kind only an inscription, pluses or charges may follow)
        if any(re.search(rf"\bof {re.escape(j)}(?=\s*(?:$|[\(\{{\[]))", n) or bare == j for j in junk):
            return True
        if self.junk_kinds.get(kind) or (self.flavours.get(flavour_key(name)) or {}).get("junk"):
            return True
        feel = [f.strip() for f in self.orders.get("autodestroy", "").split(",") if f.strip()]
        if " broken " in f" {n} " or any(re.search(rf"\b{re.escape(f)}\b", t) for t in tags for f in feel):
            return True
        book = re.search(r"\[[^\]]*[a-z][^\]]*\]", n)
        return bool(self.w.ind.get("class_") == "Warrior" and re.search(r"\bbooks? of (magic spells|prayers)\b", n)
                    and book and book.group(0) in self.town_books())

    def quiet_moment(self, now):
        """Not in combat (the user, 10-25: floor junk is destroyed only then): no awake mobile monster in view, not
        hit in the last 5 s, HP at least think_hp, not blind or confused, and not fleeing, recalling or recovering."""
        w = self.w
        mobile = [m for m in w.monsters if "NEVER_MOVE" not in m[2].flags]
        return not mobile and now - getattr(w, "last_hit_t", 0) > 5 and w.hp_frac >= self.orders.get("think_hp", 0.65) \
            and not isinstance(self.goal, (Flee, Recall, Recover)) and not w.recall_pending and not w.flag("blind") \
            and not w.flag("confused")

    def destroy_floor_junk(self, name, now, seen_t=None):
        """Destroy the junk underfoot (k with the floor index -11, as the client sends it: any negative item is the floor, cmd3.c do_cmd_destroy) at a quiet moment.
        One try per square (the caller marks it skipped); True if sent. (2.62.0, m67 21:46: sent while walking --
        "There's nothing on the floor": only standing still on the square the "You see" was for)"""
        if not self.quiet_moment(now) or now < self.busy_until or getattr(self.mover, "active", False) or \
                (seen_t is not None and self.w.pos != self.seen_pos(seen_t)):
            return False
        m = re.match(r"(\d+) ", name)
        n = int(m.group(1)) if m else 1
        self.c.send("confirm yes")
        self.cmd(f"custom k item=-11 value={n}", f"destroy junk on the floor: {name}", hold=0.6)   # (FLOOR_INDEX, as the client)
        return True

    def pickup_room(self, name):
        """True if the item underfoot should be picked up now (destroying something
        cheaper first when the pack is full); False to leave it (with news)."""
        w, now = self.w, gnow()
        # (the Navigator's never-pick-up list, `order nopickup=Lance,Pike`: dungeon pack control, the user 10-26)
        nop = [x.strip().lower() for x in str(self.orders.get("nopickup", "")).split(",") if x.strip()]
        if any(x in name.lower() for x in nop):
            self.skipped_items.add((w.level_t, w.pos))
            return False
        iv = self.iv(name)
        worth = max(iv.value * self.pay_cut(iv.tval) * max(1, iv.count), self.kit_use_value(name),
                    self.stopgap_cover(name) * self.gold_per_dmin())     # (2.48.0: a stopgap by need)
        ud = self.unique_drop
        unique = bool(ud and ud[0] == w.level_t and w.dist(ud[1]) <= 3)
        # (2.62.0: on a vault's good/great square the find is valued as made good/great, deeper)
        iv = self.iv_at(name, w.pos)
        worth = max(iv.value * self.pay_cut(iv.tval) * max(1, iv.count), self.kit_use_value(name),
                    self.stopgap_cover(name) * self.gold_per_dmin())
        if not unique and iv.known and worth < 1 and not iv.irreplaceable:
            if (w.level_t, w.pos) not in self.skipped_items:
                self.skipped_items.add((w.level_t, w.pos))
            return False                         # worthless: leave it
        # (too heavy: m46 carried six weapons for sale and went speed -1. Loot that would take us past the weight limit's
        # slow-down line is left unless it's worth HEAVY_LOOT_MIN or can't be replaced)
        wt = geareval.Item(name).weight * max(1, iv.count) if iv.tval in geareval.SLOT_OF_TVAL else \
            50 * max(1, iv.count) if iv.tval == 55 else 0          # (staffs: 5 lb each, m47's pack sat on the line)
        if wt and not unique and not iv.irreplaceable and worth < self.HEAVY_LOOT_MIN:
            room, _ = self.weight_room()
            # (m50: Bullroarer's Dagger, Cutlass, Gnomish Shovel and Lucerne Hammer sat at the weight limit and a
            # Staff of Trap Location was left. As for a full pack: shed the cheapest thing heavy enough, if this is
            # worth 1.5x it)
            shed = sorted(((self.pack_value(i), i) for i in w.items() if self.destroy_count(i) > 0
                           and i["weight"] * self.destroy_count(i) // max(1, i["number"]) >= wt - room
                           and not (worth < self.SUPPLY_SWAP_MIN and (self.supply_kind(i) or self.is_kit_item(i)))),
                          key=lambda vi: vi[0]) if wt > room else []
            if shed and worth > 1.5 * shed[0][0] + 5:
                if now - self.room_t > 1.5:
                    v, it = shed[0]
                    self.room_t = now
                    self.c.send("confirm yes")
                    self.cmd(f"custom k item={it['item']} value={self.destroy_count(it)}",
                             f"make weight room: destroy {it['name']} (~{v:.0f}) for {name} (~{worth:.0f})", hold=0.6)
                    gone = self.destroy_count(it)
                    self.notify("tactic", f"at the weight limit: destroyed "
                                          f"{self.destroyed_text(it, gone)} (~{v:.0f} gold) to take "
                                          f"{name} (~{worth:.0f})"
                                          # (2.56.0: food or oil gone -- what's left, as the pack-full news says)
                                          + (f"; now {self.supply_text({it['item']: gone})}"
                                             if self.supply_kind(it) else ""), news=True)
                return False                     # (picked up on the next look, once there's room)
            if wt > room:
                self.skipped_items.add((w.level_t, w.pos))
                # (once per item and level: m47 said "left a Battle Axe" 9 times walking past it)
                said = self.left_news
                if (w.level_t, name) not in said:
                    said.add((w.level_t, name))
                    self.notify("tactic", f"left {self.named(name)} (~{worth:.0f}): {wt / 10:.0f} lb would slow you (the weight "
                                          f"limit; {max(0, room) / 10:.0f} lb to spare)", news=True)
                return False
        free = self.PACK_SLOTS - len(w.items())
        if free >= 1:
            return True
        # one that stacks with what we carry needs no slot (m25 left a Potion of Heroism 7 times, "pack full",
        # with 6 in the pack)
        key = self.kind_key_of(name)
        if any(self.kind_key_of(i["name"]) == key for i in w.items()):
            return True
        # Use something up before destroying anything (the user, mission 21: a robe and
        # a scroll were destroyed with a flask of oil in the pack that could have
        # filled the lantern): a flask into the lantern, food eaten (below)
        if now - self.room_t > 1.5:
            lamp = next((i for i in w.items(equip=True) if i["tval"] == TV_LITE and "Lantern" in i["name"]), None)
            lt = light_turns(lamp["name"]) if lamp else None
            # (the user, 10-31: eat if you can and fill the lantern from any stack, then discard the extra -- a
            # lone item first, as it frees its slot; from a bigger stack only when no fuel is wasted)
            flasks = sorted((i for i in w.items() if i["tval"] == TV_FLASK), key=lambda i: i["number"])
            foods = sorted((i for i in w.items() if i["tval"] == TV_FOOD and "Mushroom" not in i["name"]),
                           key=lambda i: i["number"])
            flask = next((i for i in flasks if lt is not None and (lt < 14000 if i["number"] == 1
                                                                   else lt <= 15000 - self.FLASK_FUEL)), None)
            food = foods[0] if foods else None
            if flask and lt is not None:
                self.room_t = now
                self.cmd(f"custom F item={flask['item']}", f"make room: fuel the lantern with a flask for {name}",
                         hold=0.6)
                return False
            # (m49: a Piece of Elvish Waybread, 7500 food, eaten for room while Fed beside Wargs and a Black ogre: Gorged,
            # -10 speed. Eaten only if the most the stomach can hold -- the tracker's top once a crossing has calibrated
            # it, else the top of the hunger level -- plus the food stays a potion margin under Gorged)
            if food and self.food_top() + self.food_value(food["name"]) < PY_FOOD_MAX - 1000:
                self.room_t = now
                self.cmd(f"custom E item={food['item']}", f"make room: eat {food['name']} for {name}", hold=0.6)
                return False
        cand = sorted(((self.pack_value(i), i) for i in w.items()), key=lambda vi: vi[0])
        cand = [(v, i) for v, i in cand if self.destroy_count(i) > 0
                and not (worth < self.SUPPLY_SWAP_MIN and (self.supply_kind(i) or self.is_kit_item(i)))]
        cheapest = cand[0] if cand else None
        # (a unique's drop is "good" but unknown: it may push out only cheap things. m37 destroyed a Tulwar (~76)
        # for Boldor's 4-gold Dagger, and an Amulet of Infravision (~86) for boots it then destroyed for a Katana)
        if cheapest and cheapest[0] < float("inf") and ((unique and cheapest[0] < self.UNIQUE_DROP_BUMP)
                                                         or worth > 1.5 * cheapest[0] + 5):
            if now - self.room_t > 1.5:
                self.room_t = now
                self.c.send("confirm yes")
                self.cmd(f"custom k item={cheapest[1]['item']} value={self.destroy_count(cheapest[1])}",
                         f"make room: destroy {cheapest[1]['name']} (~{cheapest[0]:.0f}) for {name} (~{worth:.0f})",
                         hold=0.6)
                gone = self.destroy_count(cheapest[1])
                self.notify("tactic", f"pack full: destroyed {self.destroyed_text(cheapest[1], gone)} "
                                      f"(~{cheapest[0]:.0f} gold) to take "
                                      f"{name} (~{worth:.0f}{', a unique drop' if unique else ''})"
                                      # (2.48.1, m61: food or oil gone -- say what's left; 2.51.0: without what went)
                                      + (f"; now {self.supply_text({cheapest[1]['item']: gone})}"
                                         if self.supply_kind(cheapest[1]) else ""),
                            news=True)
            return False                         # (picked up on the next look, once there's room)
        if (w.level_t, w.pos) not in self.skipped_items:
            self.skipped_items.add((w.level_t, w.pos))
            # (once per item and level: m25 said "left a Rapier" 5 times and "left a Potion of Heroism" 7)
            if (w.level_t, name) not in self.left_news:
                self.left_news.add((w.level_t, name))
                self.notify("tactic", f"left {self.named(name)} (~{worth:.0f}): pack full and nothing cheaper to make room with",
                            news=True)
        return False

    # (the gear evaluator's tval -> slot table, armour only: boots..body armour, tvals 30-38; refactor-candidates D11)
    ARMOUR_SLOTS = {tv: s for tv, s in geareval.SLOT_OF_TVAL.items() if 30 <= tv <= 38}

    def policy_tick(self, now):
        """The Pilot's own item work at safe moments (restructure step 2.1): identify
        what's worth it, wield a better weapon, wear better armour and good
        jewellery in empty slots. True if it acted."""
        w = self.w
        if now - self.policy_t < 3 or now < self.busy_until or w.store or self.pending_use or w.monsters or \
                now - w.last_hit_t < 8 or w.hp_frac < 0.5 or isinstance(self.goal, (Flee, Recall, Recover, Shop, TownKit)) or \
                w.flag("blind") or w.flag("confused"):
            return False
        self.policy_t = now
        # 0-. Hungry (not Weak: the reflex's): eat at a safe moment (2.45.2, the user: not an emergency, a battle turn
        # spent eating is wasted); one meal, then wait for the indicator (mission 13 ate 2 rations in a row)
        if w.hunger == 2:
            # (2.48.1, m61: not mushrooms -- it ate 2 unknown Wrinkled Mushrooms; rations and other real food only)
            food = [i for i in w.items(tval=TV_FOOD) if "Mushroom" not in i["name"]]
            if food and now - self.eat_t > 10:
                self.eat_t = now
                self.cmd(f"eat {food[0]['item']}", f"hungry ({w.hunger}), a safe moment", hold=1.0)
                self.notify("tactic", f"hungry: ate {one_of(food[0]['name'])}")
                return True
        # 0. a drained STR/DEX/CON with its Restore in the pack: drink it now, the fight over (never mid-fight: m42's
        # Navigator quaffed one next to the Giant red ant and was drained again, ~480 gold lost) -- the reason a
        # spare Restore is carried at all (the user, m43: "why bring the restore potions?"). 2.50.0 (the user): or eat
        # a known restore mushroom that covers it, the cheapest first (restore_item; never one that could gorge us).
        # Not INT/WIS/CHR: town does those
        # (2.55.0: a stat-gain potion carried is drunk at the first safe moment)
        if self.quiet_moment(now) and self.quaff_gain("a safe moment"):
            return True
        if w.in_dungeon and self.quiet_moment(now):
            it = self.restore_item(stats=tuple(self.STAT_FULL))
            if it:
                food = it["tval"] == TV_FOOD
                line = f"custom {'E' if food else 'q'} item={it['item']}"
                self.cmd(line, f"restore a drained stat now the fight is over: {'eat' if food else 'quaff'} "
                               f"{it['name']}", hold=0.8)
                if self.last_action and self.last_action[1] == line:      # (not held)
                    self.notify("tactic", f"{'ate' if food else 'quaffed'} {one_of(it['name'])}: the drain is undone, "
                                          "the fight over", news=True)
                return True
        # 0a. a unique's drop: the items within 3 squares of where it died (the set-piece C3: Mughash's drop
        # was left -- looting runs only inside explore and dive, and a hunt ends idle)
        ud = self.unique_drop
        if self.goal is None and not self.mover.active and ud and ud[0] == w.level_t and now - ud[2] < 300 and w.pos:
            fetched = self.drop_fetched
            drops = [q for q in self.resolve_target("item") if max(abs(q[0] - ud[1][0]), abs(q[1] - ud[1][1])) <= 3
                     and (w.level_t, q) not in fetched and w.memory.get(q, ".") not in "0123456789"]
            if drops:
                q = min(drops, key=w.dist)
                fetched.add((w.level_t, q))   # (one visit per square; not skipped_items, which the pickup reads as junk)
                g = Goto(f"{q[0]},{q[1]}")
                g.quiet = True
                self.set_goal(g)
                self.notify("tactic", f"fetching the unique's drop at {q[0]},{q[1]}", news=True)
                return True
        # 0. gold lying within 10 squares while idle (the user, mission 23: the Pilot
        # left the gold beside it in town; the Navigator needed seven gotos)
        if self.goal is None and not self.mover.active and w.pos:
            # (2.52.0, m63: never the bank's own pile inside the house -- the fetch took the 25k bank at 10:08 when a
            # `plan trip` cut plan town's house visit short, and the record still said banked)
            gold = [q for q, ch in w.memory.items() if ch == "$" and 0 < w.dist(q) <= 10
                    and (w.level_t, q) not in self.skipped_items and not self.house_square(q)]
            if gold and self.mover.go([min(gold, key=w.dist)]):
                g = Goto(f"{min(gold, key=w.dist)[0]},{min(gold, key=w.dist)[1]}")
                g.quiet = True
                self.set_goal(g)
                self.notify("tactic", f"picking up the gold {min(w.dist(q) for q in gold)} squares away", news=True)
                return True

        # (2.50.0: mark this mission's finds -- `{m62}` -- so the stash credits them; free, one at a safe moment)
        return self.inscribe_finds() or self.identify_step(now) or self.upgrade_step()

    def identify_step(self, now, minimum=20):
        """Read Identify (or use Perception) on the most valuable unknown worth at
        least `minimum` gold sold (ability sources first). True if it acted."""
        pack = self.w.items()
        # 1. identify the most valuable unknown (ability sources and likely egos first)
        scroll = next((i for i in pack if i["tval"] == TV_SCROLL and "Identify" in i["name"]), None)
        staff = next((i for i in pack if i["tval"] == 55 and "Perception" in i["name"]
                      and not re.search(r"\(0 charges\)", i["name"])), None)
        if scroll or staff:
            # (three tries per item: at night in town a read without a light failed
            # twenty times in a row, "You have no light to read by")
            tries = self.id_tries
            cands = [(pr, it) for pr, it in self.identify_candidates(minimum) if tries.get(it["name"], 0) < 3]
            if cands:
                _, it = max(cands, key=lambda pc: pc[0])
                tool = scroll or staff
                if tool is scroll and not any(i["tval"] == TV_LITE for i in self.w.items(equip=True)):
                    return self.wear_light("a light to read Identify by") and "light"
                tries[it["name"]] = tries.get(it["name"], 0) + 1
                if self.unknown_flavour(it):
                    self.id_target = {"t": now, "flavour": flavour_key(it["name"]),
                                      "letter": None if it["equip"] else chr(97 + it["item"])}
                self.cmd(f"custom {'r' if tool is scroll else 'u'} item={tool['item']} dir={it['item']}",
                         f"identify {it['name']} (policy)", hold=1.0)
                cost = self.price_of("Identify", 5) or 80
                self.notify("tactic", f"identifying {it['name']} (the most valuable unknown; "
                                      f"{'a Perception charge' if tool is staff else f'a ~{cost}-gold Scroll of Identify'}"
                                      "; a flavour is learned once for the server)", news=True)
                return True
        return False

    def upgrade_step(self):
        """Wield a better weapon, wear better armour, put good jewellery into
        empty slots: one change per call. True if it acted. `order autowear=off` pauses it (an item kept off on
        purpose; the M5 set-piece stages a low AC)."""
        if str(self.orders.get("autowear", "on")) == "off":
            return False
        w = self.w
        pack, worn = w.items(), w.items(equip=True)

        # 2. a better weapon (plain damage; a brand counts half, as not every monster is affected)
        wt = self.weapon_table()
        if wt:
            def eff(n, b, d):
                br = weapon_brand(n)
                return d + 0.5 * (weapon_damage(n, b, br[1]) - d) if br else d
            cur = max((eff(n, b, d) for n, b, d, eq in wt if eq), default=0)
            # (never for a weapon that loses an ability the wielded one gives: m33 swapped a Scimitar of Westernesse,
            # Free Action and See Invisible, for a Main Gauche doing ~40 vs ~28, and again 2 s after the Navigator
            # put it back. Artifacts are never swapped away: their abilities aren't in the ego table)
            on = next((n for n, b, d, eq in wt if eq), None)
            keep_ab = self.weapon_abilities(on) if on else set()
            best = max(((eff(n, b, d), n) for n, b, d, eq in wt if not eq and not bad_inscription(n)
                        and keep_ab <= self.weapon_abilities(n)), default=None)
            if on and self.is_artifact(on):
                best = None
            if best and best[0] > cur * 1.2 and best[0] > 0:
                it = next((i for i in pack if i["name"] == best[1]), None)
                if it:
                    self.cmd(f"custom w item={it['item']}", f"wield {it['name']} (~{best[0]:.0f}/round vs ~{cur:.0f})",
                             hold=0.8)
                    self.notify("tactic", f"wielded {it['name']}: ~{best[0]:.0f} a round vs ~{cur:.0f}", news=True)
                    return True
        # 2b. (2.53.0, the user after m63) a better light: one needing no fuel, its radius at least the worn one's, over
        # a fuelled one (the Phial over the Brass Lantern: the gear evaluator reads neither radius nor fuel); else the
        # larger radius. Here at safe moments in the dungeon too (policy_tick)
        lw = next((i for i in worn if i["tval"] == TV_LITE), None)
        if lw:
            cand = [i for i in pack if i["tval"] == TV_LITE and not bad_inscription(i["name"])
                    and self.light_better(i, lw)]
            if cand:
                it = max(cand, key=lambda i: (self.light_radius(i)[1], self.light_radius(i)[0], self.light_left(i)))
                self.cmd(f"custom w item={it['item']}", f"wield {it['name']} (light: radius "
                                                        f"{self.light_radius(it)[0]}, "
                                                        f"{'no fuel' if self.light_radius(it)[1] else 'fuel'})",
                         hold=0.8)
                self.notify("tactic", f"wielded {it['name']} as the light (radius {self.light_radius(it)[0]}"
                                      f"{', needs no fuel' if self.light_radius(it)[1] else ''}) over {lw['name']}",
                            news=True)
                return True
        # 3. better armour, slot by slot (by AC; known not cursed; plusses or a feeling known)
        for it in pack:
            slot = self.ARMOUR_SLOTS.get(it["tval"])
            if not slot or bad_inscription(it["name"]):
                continue
            if not (re.search(r"\[\d+,[+-]\d+\]", it["name"]) or re.search(r"\{(average|good|excellent)", it["name"])):
                continue                  # (no feeling yet: it might be cursed)
            on = [i for i in worn if self.ARMOUR_SLOTS.get(i["tval"]) == slot]
            # (D13: the gear evaluator's verdict -- never for armour that loses an ability or resist the worn piece
            # gives, nor more than 5% of the EHP: by AC alone a plain mail would have replaced the Hard Studded
            # Leather of Resistance and its four resists; a plain AC comparison only for what it can't read)
            better, ac_new, ac_on = self.ac_better(it["name"], on, it["tval"],
                                                   it["weight"] // max(1, it.get("number", 1)))
            ac_new = ac_new or 0
            if better:
                self.cmd(f"custom w item={it['item']}", f"wear {it['name']} (AC {ac_new} vs {ac_on})", hold=0.8)
                self.notify("tactic", f"wore {it['name']} (AC {ac_new} vs {max(ac_on, 0)})", news=True)
                return True
        # 4. good jewellery into an empty ring or amulet slot (identified only)
        swap = self.jewel_swap
        for tv, k in ((45, 2), (40, 1)):
            if sum(1 for i in worn if i["tval"] == tv) >= k:
                continue
            cand = [i for i in pack if i["tval"] == tv and self.iv(i["name"]).known and
                    self.iv(i["name"]).value > 0 and not (self.flavour_of(i) or {}).get("junk")]
            if cand:
                it = next((i for i in cand if i["name"] == swap), None) or \
                    max(cand, key=lambda i: self.iv(i["name"]).value)
                self.jewel_swap = None
                self.cmd(f"custom w item={it['item']}", f"put on {it['name']} (an empty slot)", hold=0.8)
                self.notify("tactic", f"put on {it['name']} (the slot was empty)", news=True)
                return True
        # 5. in town: better jewellery over a worn piece (m36 sold a Ring of Protection [+9] while wearing the [+8]):
        # the same kind with a bigger bonus, or anything that adds an ability or AC over a piece whose abilities
        # another worn piece already gives. Off first; step 4 then puts the new one on.
        if not w.depth and not w.in_dungeon:
            have = {f for f, sl in (w.flags or {}).items() if sl}
            spare = [r[0] for r in self.redundant_worn()]

            def bonus(n):
                m = re.search(r"\[\+(\d+)\]", n)
                return int(m.group(1)) if m else 0

            def kind(n):
                return re.sub(r"\s*\[[^]]*\]|\s*\{[^}]*\}|^(an?|\d+) ", "", n)
            for it in pack:
                if it["tval"] not in (40, 45) or not self.iv(it["name"]).known or bad_inscription(it["name"]) or \
                        (self.flavour_of(it) or {}).get("junk"):
                    continue
                # (a redundant piece goes first: swapping the [+8] would lose 8 AC that the free slot keeps)
                for on in sorted((i for i in worn if i["tval"] == it["tval"]), key=lambda i: i not in spare):
                    same = kind(on["name"]) == kind(it["name"]) and bonus(it["name"]) > bonus(on["name"])
                    adds = on in spare and (self.jewel_gives(it["name"]) - have or bonus(it["name"]))
                    if (same or adds) and not self.is_artifact(on["name"]):
                        self.jewel_swap = it["name"]
                        self.cmd(f"custom t item={on['item']}", f"take off {on['name']} for {it['name']}", hold=0.8)
                        self.notify("tactic", f"took off {on['name']} to wear {it['name']} ("
                                              + ("a bigger bonus" if same else "its abilities are given by other gear")
                                              + ")", news=True)
                        return True
        # 6. in town: the gear evaluator's choice among the identified wearables in the pack (simulated fights, never
        # losing Free Action, See Invisible, resist blindness/confusion or hold life; the user, 10-26). A ring over a worn
        # one: off first, step 4 puts it on.
        if not w.depth and not w.in_dungeon and not self.gear_swapped_t > gnow() - 30:
            for it in pack:
                got = self.gear_better(it)
                if not got:
                    continue
                label, (_, old) = got
                on = next((i for i in worn if i["name"] == old), None) if old else None
                self.gear_swapped_t = gnow()
                if it["tval"] in (40, 45) and on is not None:
                    self.jewel_swap = it["name"]
                    self.cmd(f"custom t item={on['item']}", f"take off {on['name']} for {it['name']} (gear evaluator)",
                             hold=0.8)
                else:
                    self.cmd(f"custom w item={it['item']}", f"wear {it['name']} (gear evaluator)", hold=0.8)
                self.notify("tactic", f"gear evaluator: {label} (simulated fights; `gearcmp` for the table)", news=True)
                return True
        return False

    # what proves an ability in play (the rulebook's abilities.csv, restructure step 3): (ability,
    # the message, the line just before it that must match, a line before that rules it out)
    ABILITY_PROOFS = (
        ("free_action", r"You are unaffected", r"stares deep into your eyes|drains power from your muscles|mumbles\.$|"
                                               r"touches you|gazes (at )?you", r"burning your eyes|gestures at your feet|"
                                                                              r"mumbles strangely"),
        ("resist_blind", r"You are unaffected", r"burning your eyes", None),
        ("resist_nexus", r"You are unaffected", r"gestures at your feet|mumbles strangely", None),
        ("hold_life", r"You keep hold of your life force", None, None),
        ("sustain_str", r"You feel weak for a moment, but the feeling passes", None, None),
        ("sustain_int", r"You feel stupid for a moment, but the feeling passes", None, None),
        ("sustain_wis", r"You feel naive for a moment, but the feeling passes", None, None),
        ("sustain_dex", r"You feel clumsy for a moment, but the feeling passes", None, None),
        ("sustain_con", r"You feel sickly for a moment, but the feeling passes", None, None),
        ("sustain_chr", r"You feel ugly for a moment, but the feeling passes", None, None),
        ("feather_fall", r"You float gently", None, None),
    )
    ABILITY_LABEL = {"free_action": "Free Action", "resist_blind": "resist blindness", "resist_nexus": "resist nexus",
                     "hold_life": "hold life", "feather_fall": "feather fall"}

    def watch_abilities(self):
        """Abilities shown by the game's answers rather than the sheet: "You are
        unaffected!" just after a paralysing attack is Free Action (the Advisor's
        set-piece C8: Dive04 had it from m18 to m23 from unidentified boots, sold
        for 3 gold in m23), and the other proofs in the rulebook's abilities.csv
        (ABILITY_PROOFS). The unidentified worn items become its likely source."""
        w = self.w
        msgs = list(w.messages)
        for i, (ts, t) in enumerate(msgs):
            if ts <= self.ability_seen_t:
                continue
            before = [m for tt, m in msgs[max(0, i - 4):i] if ts - tt < 3]
            last = before[-1] if before else ""
            for ab, msg, need, veto in self.ABILITY_PROOFS:
                if not re.match(msg, t) or ab in self.inferred or self.has_ability(ab):
                    continue
                # (only the line just before counts: the same "unaffected" follows BLIND, HOLD and
                # TELE_LEVEL, and proves a different ability for each)
                if (need and not re.search(need, last)) or (veto and re.search(veto, last)):
                    continue
                self.inferred.add(ab)
                src = [bare_name(i2["name"]).lower()
                       for i2 in w.items(equip=True) if self.iv(i2["name"]).known is False
                       or re.search(r"\{(good|excellent|special|magical)", i2["name"])]
                self.ability_sources |= set(src)
                label = self.ABILITY_LABEL.get(ab) or f"sustain {ab[8:].upper()}"
                self.notify("ability", f"you have {label} (\"{t}\"" + (f" after \"{last}\"" if need else "") +
                                       "), though no known item gives it: it's one of your unidentified worn items ("
                                       + (", ".join(src) or "none found") + "). The Pilot won't sell or drop those; "
                                       "identify them")
        self.ability_seen_t = max([self.ability_seen_t] + [ts for ts, _ in msgs])

    WEAPON_ABILITY_FLAGS = {"FREE_ACT", "SEE_INVIS", "HOLD_LIFE", "TELEPATHY", "FEATHER", "REGEN", "SLOW_DIGEST", "SPEED",
                     "STR", "DEX", "CON", "BLOWS", "LITE"}

    def weapon_abilities(self, name):
        """What a weapon (or armour) gives beyond damage and AC, from the rulebook's ego table (ego_flags.csv): Free
        Action, See Invisible, resists, sustains, stats... An unknown ego or a plain item: nothing."""
        if self._ego_flags is None:
            try:
                self._ego_flags = {r["name"]: set(r["flags"].split()) for r in csv.DictReader(
                    open(os.path.join(HERE, "..", "rulebook", "ego_flags.csv")))}
            except OSError:
                self._ego_flags = {}
        for ego, flags in self._ego_flags.items():
            if ego and re.search(rf"\b{re.escape(ego)}\b", name or ""):
                return {f for f in flags if f in self.WEAPON_ABILITY_FLAGS or f.startswith(("RES_", "SUST_", "IM_"))}
        return set()

    @staticmethod
    def is_artifact(name):
        """A named artifact ('Dagger 'Narthanc'', 'the Phial of Galadriel'): its abilities aren't in the ego table."""
        return bool(re.search(r"'\w|\bthe \w+ of [A-Z]", name or ""))

    def weapon_table(self):
        """[(name, blows, damage per round, wielded?)] for the wielded weapon and
        every weapon in the pack, at the current STR/DEX (the Advisor's
        progression memo: mission 13 fought 17 min with a Dagger while
        carrying a Sabre)."""
        ind = self.w.ind
        st, dx = ind.get("stat0", [0])[0], ind.get("stat3", [0])[0]
        if not st or not dx:
            return []
        out = []
        for eq in (True, False):
            for i in self.w.items(equip=eq):
                if i["tval"] in TV_WEAPONS:
                    wt = i["weight"] // max(1, i.get("number", 1))
                    b = weapon_blows(wt, st, dx)
                    out.append((i["name"], b, weapon_damage(i["name"], b), eq))
        return out

    def watch_weapons(self):
        """News when a carried weapon beats the wielded one by > 20% per round."""
        wt = self.weapon_table()
        cur = next((d for n, b, d, eq in wt if eq), 0)
        for n, b, d, eq in wt:
            if not eq and d > cur * 1.2 and d > 0 and n not in self.weapon_tips:
                self.weapon_tips.add(n)
                self.notify("tactic", f"{n} would do ~{d:.0f} per round ({b} blows) vs ~{cur:.0f} now: wield it")

    # --- the item-review queue (the user, 10-26: route judgement calls to the Navigator before they're irreversible) ---
    REVIEW_MIN_VALUE = 1000

    def review_state(self):
        if self.review is None:
            try:
                self.review = json.load(open(os.path.join(self.rundir, "review.json")))
            except (OSError, ValueError, AttributeError):
                self.review = {}
            self.review.setdefault("items", {})
            self.review.setdefault("decided", {})
            self.review.setdefault("town_visits", 0)
        # (m58: a Ring of Protection [+16] worn since m57 was still listed "SOLD at this town visit if undecided": what's
        # worn leaves the queue)
        worn = {i["name"] for i in (self.w.items(equip=True) if self.w else [])}
        for n in [n for n in self.review["items"] if n in worn]:
            del self.review["items"][n]
        return self.review

    def review_save(self):
        try:
            json.dump(self.review_state(), open(os.path.join(self.rundir, "review.json"), "w"), indent=1)
        except (OSError, AttributeError):
            pass

    def review_hold(self, it):
        """True while this identified wearable waits for the Navigator's word instead of being sold: it gives an ability
        or resist, or it's an artifact, or worth REVIEW_MIN_VALUE+ -- and the gear evaluator wouldn't wear it. 2.63.0
        (the user: "decided while we are in town the first time"): plan town raises the held items at its start, and at
        its last step before banking (`review_closing`) anything still undecided gets the policy's default -- sold.
        Nothing is carried to a later visit (before: sold after 2 visits undecided)."""
        name = it["name"]
        if bare_name(name).lower() in self.stash_to_sell:
            return False             # (2.51.0: fetched from the stash to be sold: no longer the stash's, no review)
        st = self.review_state()
        dec = st["decided"].get(name)
        if dec:
            return dec != "sell"
        if it["tval"] not in geareval.SLOT_OF_TVAL or it["tval"] == TV_LITE:
            return False
        gi = geareval.Item(name, it["tval"])
        iv = self.iv(name)
        why = "an artifact" if self.is_artifact(name) else \
            f"gives {', '.join(geareval.label(f) for f in sorted(gi.abilities()))}" if gi.abilities() else \
            f"worth ~{iv.value}" if iv.value >= self.REVIEW_MIN_VALUE else None
        if not why or not iv.known:
            return False
        q = st["items"].get(name)
        in_visit = type(self.goal).__name__ == "TownKit"
        if q is None:
            st["items"][name] = {"why": why, "visit": st["town_visits"], "t": time.strftime("%Y-%m-%d %H:%M"),
                                 "held_t": gnow()}
            self.review_save()
            if not self.review_raising:          # (plan town's start says them all in one alert: review_raise)
                self.notify("review", f"held for your decision: {name} ({why}; the policy's default: sell). `gearcmp "
                                      f"{name.replace(' ', '_')[:30]}` compares it; `review sell|keep|wear NAME`. "
                                      + ("Undecided at the end of this town visit, it is sold" if in_visit else
                                         "Decided at the next town visit: undecided by its end, it is sold"),
                            news=not in_visit)
            return True
        if self.review_closing:
            st["decided"][name] = "sell"
            st["items"].pop(name, None)
            self.review_save()
            self.notify("review", f"{name}: undecided at the end of the town visit -- the policy's default, sold",
                        news=True)
            return False
        return True

    FLAVOURED = set(itemvalue.FLAVOURED.values())     # potion, scroll, wand, staff, rod, ring, amulet

    # --- the flavour table (the Advisor's identify-and-sell memo, 2026-10-07):
    # flavours are fixed per server, so what any character learns holds for all

    def load_flavours(self):
        try:
            with open(self.flavour_file) as f:
                self.flavours = json.load(f)
        except (OSError, ValueError):
            self.flavours = {}
        self.junk_kinds = {}
        tv = {"potion": "Potion", "scroll": "Scroll", "wand": "Wand", "staff": "Staff", "rod": "Rod",
              "ring": "Ring", "amulet": "Amulet"}
        # the rulebook (restructure step 3): a kind is junk when it's worthless at every level, or
        # worth at most a gold piece (Water, Apple Juice): 38 kinds. The file must exist (the old kinds.csv
        # fallback went in session 10, C10)
        rows = {}
        for r in csv.DictReader(open(os.path.join(HERE, "..", "rulebook", "kinds_by_level.csv"))):
            rows.setdefault(f"{tv.get(r['tval'], r['tval'])} of {r['kind']}", []).append(r)
        for name, rs in rows.items():
            self.junk_kinds[name] = all(float(r["worthless"] or 0) >= 1 or float(r["value"] or 0) <= 1 for r in rs)

    def learn_flavour(self, flavour, kind, how):
        if not flavour or not kind or " of " not in kind or self.flavours.get(flavour, {}).get("kind") == kind:
            return
        if type_word(flavour) != type_word(kind):
            self.log("note", text=f"flavour pairing refused (type mismatch): {flavour} = {kind} ({how})")
            return
        self.flavours[flavour] = {"kind": kind, "junk": self.junk_kinds.get(kind, False), "source": how}
        try:
            cur = {}
            if os.path.exists(self.flavour_file):
                with open(self.flavour_file) as f:
                    cur = json.load(f)
            cur[flavour] = self.flavours[flavour]
            with open(self.flavour_file, "w") as f:
                json.dump(cur, f, indent=1, sort_keys=True)
        except OSError:
            pass
        self.notify("tactic", f"learned: {flavour} = {kind}" + (" (junk)" if self.flavours[flavour]["junk"] else ""))

    def flavour_of(self, it):
        return self.flavours.get(flavour_key(it["name"])) if self.unknown_flavour(it) else None

    def show(self, it):
        """An item's name, with the flavour table's kind for an unknown flavour."""
        f = self.flavour_of(it)
        return it["name"] + (f" (= {f['kind']}{', junk' if f['junk'] else ''}; not aware)" if f else "")

    # weapons, bows and armour: identified by pseudo-ID's feeling for free once carried a while (a light never shows
    # plusses: not here)
    ID_WEAR_TVALS = (19, 20, 21, 22, 23, 30, 31, 32, 33, 34, 35, 36, 37, 38)
    FEELING_RE = r"\{(average|good|excellent|special|worthless|cursed|broken|terrible|magical|uncursed)"
    PLAIN_FEELING_RE = r"\{(average|worthless|cursed|broken|terrible)"   # (sold or destroyed by the feeling)
    GAIN_KINDS = ("Strength", "Intelligence", "Wisdom", "Dexterity", "Constitution", "Charisma", "Augmentation",
                  "Experience")

    def must_identify(self, it):
        """2.55.0 (the user after m64: a Pungent Potion sold for 9 gold was a Potion of Strength, relisted at 12,560 --
        "identify everything other than weapon/armor with a pseudo-ID already"): this unworn item is identified before
        the policy sells or destroys it. An unknown flavour (potion, scroll, wand, staff, rod, ring, amulet,
        mushroom) unless the flavour table knows it as junk; jewellery or a device whose plusses or charges aren't
        known; a weapon, bow or armour piece whose plusses aren't shown, unfelt or felt {good}/{excellent}/{special}
        (the user's correction: only gear felt {average}, {worthless}, {cursed}, {broken} or {terrible} goes by its
        feeling without identifying)."""
        name = it["name"]
        if it.get("equip") or bad_inscription(name):
            return False
        if self.unknown_flavour(it):
            return not (self.flavour_of(it) or {}).get("junk")
        tv = it["tval"]
        if tv in (40, 45, 55, 65, 66):
            return self.iv(name).known is False
        if tv in self.ID_WEAR_TVALS:
            if re.search(r"\([+-]\d+,[+-]\d+\)|\[\d+,[+-]\d+\]", name) or re.search(self.PLAIN_FEELING_RE, name):
                return False
            return True
        return False

    def unfelt(self, it):
        """A weapon, bow or armour piece with no feeling and no plusses shown (pseudo-ID feels it for free soon)."""
        n = it["name"]
        return it["tval"] in self.ID_WEAR_TVALS and not re.search(self.FEELING_RE, n) and \
            not re.search(r"\([+-]\d+,[+-]\d+\)|\[\d+,[+-]\d+\]", n)

    def gain_potion(self, it):
        """A known stat-gain potion (Strength ... Charisma, Augmentation, Experience; not Enlightenment, not the
        Restores): never sold, drunk at once (quaff_gain; 2.55.0, the user)."""
        return it.get("tval") == TV_POTION and bool(
            re.search(r"\bPotions? of (" + "|".join(self.GAIN_KINDS) + r")\b", it["name"]))

    def quaff_gain(self, why):
        """Drink a stat-gain potion carried (one a call; 2.55.0). True if it sent one."""
        if self.pending_use or gnow() < self.busy_until:
            return False
        it = next((i for i in self.w.items(tval=TV_POTION) if self.gain_potion(i)), None)
        if not it:
            return False
        line = f"custom q item={it['item']}"
        self.cmd(line, f"drink {it['name']}: a stat gain ({why})", hold=0.8)
        if self.last_action and self.last_action[1] == line:
            self.notify("tactic", f"quaffed {one_of(it['name'])}: a permanent stat gain", news=True)
        return True

    def unknown_sell_refusal(self, it, n):
        """Why not to sell this unknown item now, or None (the memo's §4.4):
        junk per the table -> sell (the shop refuses it once known); one of a
        stack -> sell (a free identification of the flavour); a potion or
        scroll while we've never been below 1000 ft -> sell (Identify costs
        more than it earns); devices and jewellery -> Identify first."""
        if not self.unknown_flavour(it):
            return None
        f = self.flavour_of(it)
        if f and f["junk"]:
            return None
        if f:
            return f"it's {f['kind']}: worth more known, use or Identify it"
        if it.get("number", 1) >= 2 and n == 1:
            return None
        if it["tval"] == TV_SCROLL:
            # Reading one costs nothing and teaches the flavour; selling a lone
            # one for ~8 threw away a Teleportation (mission 18). The curse
            # scrolls are native to 2500 ft, so at our depths a read is safe
            return ("a lone unknown scroll: read it to learn it (`read L`, in town or somewhere quiet; "
                    "Teleportation, Teleport Level and Magic Mapping are worth keeping)")
        if it["tval"] in (75, 70, TV_FOOD) and self.deepest_ft < 1000:
            return None
        if it["tval"] in (75, 70, TV_FOOD):
            return "an unknown potion/scroll found below 1000 ft: Identify it (expected value 87-750)"
        return "an unknown wand/staff/rod/ring/amulet: Identify it first (worth 50-700 known)"

    def unknown_flavour(self, it):
        """An unidentified flavoured item ('a Blue Speckled Potion', 'a Copper
        Wand', 'a Blue Mushroom'): it sells at its plain base value, whatever it is."""
        if it.get("tval") == TV_FOOD:
            return "Mushroom" in it["name"] and " of " not in it["name"]
        return it.get("tval") in self.FLAVOURED and " of " not in it["name"]

    def probably_special(self, name):
        """A unique's drop (inscribed with its name) or an {excellent}/{special}
        feeling: worth inspecting (or identifying) before selling."""
        m = re.search(r"\{([^}]*)\}", name)
        tags = m.group(1).lower() if m else ""
        # (2.50.0: a feeling stays shown after Identify when the item was inscribed -- `{excellent - m62}`, the server
        # clears only a bare feeling: an identified item's feeling says nothing more)
        if " - " in tags and mission_tag(name) and self.iv(name).known is True and not self.iv(name).estimate:
            tags = ""
        if any(f in tags for f in ("excellent", "special", "artifact")):
            return True
        # {good} weapons/armour whose pluses aren't known yet (mission 16: a Trident
        # {good} sold for 42 was (+3,+7), resold at 1848; Identify costs ~83)
        known = re.search(r"\([+-]\d+,[+-]\d+\)|\[\d+,[+-]\d+\]", name)
        if "good" in tags and not known:
            return True
        # identified, with no ego or artifact name: an ordinary item, whoever dropped it (m25: Mughash's
        # Broad Sword (+4,+6) and Battle Axe (+1,+5) were refused as "probably special" after Identify)
        bare = re.sub(r"\s*\{[^}]*\}", "", name)
        if known and " of " not in bare and "'" not in bare and not re.search(r"\b(the|of)\b [A-Z]", bare):
            return False
        if not self.unique_names:
            self.unique_names = {r.name.lower() for r in self.w.g.races.values() if "UNIQUE" in r.flags}
        return any(u in tags for u in self.unique_names)

    LOOT_OWED_R = 25          # items passed up while monsters were in view: fetched once it's clear, this far
    LOOT_VALUABLE_R = 30      # devices and jewellery: the Pilot fetches them itself, this far
    VALUABLE_GLYPHS = "-_=\""   # wand/rod, staff, ring, amulet
    FAR_FETCH_MIN = 200       # 2.51.0: a potion or scroll worth this (itemvalue; unknown: the expectation) is fetched

    def far_fetch_worth(self, name):
        """Why a potion or scroll seen on the level map is worth a far fetch (LOOT_VALUABLE_R, as devices and
        jewellery; 2.51.0, the user after m62), or None: a kit consumable (KIT_KINDS: Speed, Teleportation, Phase,
        the cures, Healing, Recall, Heroism, Berserk... -- a stat Restore only, not Restore Mana; not a crutch), or
        worth FAR_FETCH_MIN+ by itemvalue (an unknown flavour by its expected value). Junk never."""
        if not re.search(r"\b(Potions?|Scrolls?)\b", name) or self.is_junk(name):
            return None
        tv = TV_POTION if re.search(r"\bPotions?\b", name) else TV_SCROLL
        if self.is_kit_item({"name": name, "tval": tv}) and \
                ("Restore" not in name or re.search(self.STASH_KINDS, name)):
            return "a kit item"
        v = self.iv(name).value
        return f"worth ~{v}" if v >= self.FAR_FETCH_MIN else None

    def far_wanted_glyphs(self):
        """The glyphs ('!', '?') of this level's far-fetch potions and scrolls still on the map (in the item list) and
        not in the pack: loot_step treats those squares as valuable."""
        w = self.w
        if not self.far_wanted:
            return set()
        listed = {l.strip()[2:].strip() for l in (getattr(w, "itemlist", None) or [])[1:]}
        out = set()
        for (lt, glyph), names in self.far_wanted.items():
            if lt == w.level_t and any(n in listed for n in names):
                out.add(glyph)
        return out

    def loot_step(self, state):
        """Fetch items (dive and explore share this): those within loot_radius; those passed up while
        monsters were in view, within LOOT_OWED_R once it's clear; devices and jewellery within
        LOOT_VALUABLE_R. An item counts as done once we've stood on it (the pickup policy decides) or after
        3 interrupted walks. The user (m29): gold and an unknown wand left beside the path while a Baby black
        dragon was in view, never revisited (12 squares off, beyond loot_radius 10); a walk cut short was
        never retried (the square was marked looted when the walk began); the interesting-item notice waited
        for a `goal fetch` nobody sent under a trip plan.
        state: the goal's dict ({'looting': bool, 'target': square, 'level': t}). True while fetching."""
        w = self.w
        lr = int(self.orders.get("loot_radius", 0))
        mem = self.loot_mem
        if mem.get("level") != w.level_t:
            mem.clear()
            mem.update(level=w.level_t, done=set(), tries=collections.Counter(), owed=set())
        if state.get("level") != w.level_t:
            state.update(level=w.level_t, looting=False, target=None)
        if not lr or self.orders.get("pickup", "all") != "all":
            # (order pickup=none: no walks to loot either; it used to walk there and leave it -- refactor-candidates A5)
            if state.get("looting"):
                state["looting"] = False
                self.mover.stop()
            return False
        items = [t for t in self.resolve_target("item") if t not in mem["done"]]
        # (2.62.0: a lesser vault with weak defenders -- its treasure squares are loot, seen or not)
        v = self.vaults.get(w.level_t) or {}
        if v.get("loot"):
            items += [t for t in v.get("treasure", ()) if t not in mem["done"] and t not in items
                      and w.memory.get(t) not in ("#", "%") and w.dist(t) <= self.LOOT_VALUABLE_R]
        # (no detours while a band is about: the Advisor's set-piece C5, mission 22's loot room. A band out of
        # view now may be round the corner. Molds don't count: the planner keeps clear of them; nor do weak
        # monsters, 10+ levels below us and not dangerous: auto-retaliate kills them if they come. The set-piece
        # M2: a Cave lizard 16 squares off held a wand back for good; a Jackal pack cut the walk short and the
        # dive left without it)
        if self.loot_blocked():
            mem["owed"] |= {t for t in items if w.dist(t) <= lr}
            if state.get("looting"):
                state["looting"] = False
                mem["tries"][state["target"]] += 1
                self.mover.stop()
            return False
        if state.get("looting"):
            st = self.mover.tick()
            if st == "moving":
                return True
            tgt = state["target"]
            state["looting"] = False
            if w.pos == tgt or st == "arrived":
                mem["done"].add(tgt)
            else:
                mem["tries"][tgt] += 1
            # (on to the next, or the same again: handing back here let the dive head for the stairs -- M2, a
            # Rock lizard's fight stopped the walk 2 squares from the wand)
        if self.mover.active:
            return False
        for t in [t for t in items if mem["tries"][t] >= 3]:
            mem["done"].add(t)
        items = [t for t in items if t not in mem["done"]]
        far = self.VALUABLE_GLYPHS + "".join(self.far_wanted_glyphs())     # (2.51.0: and wanted potions/scrolls)
        valuable = {t for t in items if (w.memory.get(t) in far or t in set(v.get("treasure", ()) if v.get("loot")
                                                                             else ())) and w.dist(t) <= self.LOOT_VALUABLE_R}
        owed = {t for t in items if t in mem["owed"] and w.dist(t) <= self.LOOT_OWED_R}
        cands = {t for t in items if w.dist(t) <= lr} | owed | valuable
        if not cands:
            return False
        tgt = min(cands, key=w.dist)
        if not self.mover.go([tgt]):
            mem["done"].add(tgt)
            return False
        # (a wall between: a walk far longer than the distance isn't worth it)
        reach = self.LOOT_VALUABLE_R if tgt in valuable else self.LOOT_OWED_R if tgt in owed else lr
        if len(self.mover.path) > reach * 3 // 2:
            self.mover.stop()
            mem["done"].add(tgt)
            return False
        state.update(looting=True, target=tgt)
        return True

    def loot_blocked(self):
        """No detours for loot now (loot_step's test): a band about, a mobile monster that matters, low HP, blind or
        confused."""
        w = self.w
        band = self.band_warned[0] == w.level_t and gnow() - self.band_warned_t < 90
        mobile = [m for m in w.monsters if "NEVER_MOVE" not in m[2].flags
                  and (m[2].level > w.clvl - 10 or self.danger_why(m[2]))]
        return bool(mobile or band or w.hp_frac < self.orders.get("think_hp", 0.65) or w.flag("blind")
                    or w.flag("confused"))

    LOOT_PATH_R = 3           # walking to the stairs: a detour this far for loot beside the path
    def loot_beside(self):
        """An item not yet looted within LOOT_PATH_R, and nothing against a detour (the dive walking to the stairs,
        which otherwise loots only before it sets off)."""
        mem = self.loot_mem or {}
        if mem.get("level") != self.w.level_t or not int(self.orders.get("loot_radius", 0)):
            return False
        return any(self.w.dist(t) <= self.LOOT_PATH_R for t in self.resolve_target("item")
                   if t not in mem["done"]) and not self.loot_blocked()

    def town_light(self, now):
        """In town with nothing to do, take the light off: resting in town
        burns fuel ~10x faster (time runs at 1000% while resting, xtra2.c;
        the Advisor's shops memo), which is how Dive04's torches all died.
        keep_light wields it again in the dungeon."""
        w = self.w
        if w.depth != 0 or w.store or now < self.busy_until or now < self.light_t:
            return False
        idle = self.goal is None or isinstance(self.goal, (Wait, RestGoal))
        worn = next((i for i in w.items(equip=True) if i["tval"] == TV_LITE), None)
        # (2.62.0, m67 22:00: "in town and idle: light off" every 5 s -- once per idle period: until the Navigator or a
        # goal acts again)
        period = (self.last_agent, id(self.goal))
        if idle and worn and now - self.last_agent > 20 and self.light_off_period != period:
            self.light_off_period = period
            self.light_t = now + 5
            self.cmd(f"custom t item={worn['item']}", "in town and idle: light off (it burns while resting)",
                     hold=0.6)
            return True
        return False

    def keep_light(self, now):
        """Refill the lantern (or swap torches) before the light goes out --
        Dive03 explored in the dark for minutes after "Your light has gone
        out!", which is why nothing around it ever showed up on the map."""
        w = self.w
        worn = next((i for i in w.items(equip=True) if i["tval"] == TV_LITE), None)
        unlit = not worn and w.depth != 0 and now - self.unlit_try_t > 1.5
        if (now < self.light_t and not unlit) or now < self.busy_until or w.store:
            return False
        if unlit:
            self.unlit_try_t = now           # (in the dungeon without a light: at once, not after the 5-60 s wait)
        self.light_t = now + 5
        turns = light_turns(worn["name"]) if worn else None
        if worn and "Lantern" in worn["name"] and turns is not None and turns < 3000:
            flask = next((i for i in w.items(tval=TV_FLASK)), None)
            if flask:
                self.cmd(f"custom F item={flask['item']}", f"refill lantern ({turns} turns left)", hold=0.6)
                return True
            # a fuller lantern in the pack (m39 ran its worn one down to ~700 turns with a 13290-turn spare carried)
            spare = self.best_light()
            if spare and self.light_left(spare) > turns + 1000:
                self.cmd(f"custom w item={spare['item']}", f"swap to the fuller lantern ({turns} turns left on the "
                                                           f"worn one)", hold=0.6)
                self.notify("tactic", f"lantern at {turns} turns: swapped to the spare ({self.light_text(spare)})",
                            news=True)
                return True
            self.warn_light("lantern out" if turns == 0 else "lantern low",
                            f"lantern at {turns} turns and no flasks of oil")
        elif worn and "Torch" in worn["name"] and turns is not None and turns < 500:
            # only a light with more left (burnt-out spares were swapped ~2100
            # times while Dive04 idled in town); a lantern in the pack counts
            torch = max((i for i in w.items(tval=TV_LITE) if self.light_left(i) > turns),
                        key=self.light_left, default=None)
            if torch:
                self.cmd(f"custom w item={torch['item']}", f"fresh torch ({turns} turns left)", hold=0.6)
                return True
            self.warn_light("torch out" if turns == 0 else "torch low",
                            f"torch at {turns} turns and no fresher torch: buy torches or a lantern")
        elif not worn and w.depth != 0:
            spare = self.best_light()
            if spare:
                self.cmd(f"custom w item={spare['item']}", "wield a light", hold=0.6)
                return True
            self.warn_light("no light", "no light source")
        return False

    def light_text(self, it):
        """'N turns', or 'permanent' for a light that shows none (messages: not "1000000 turns")."""
        t = light_turns(it["name"])
        return "permanent" if t is None else f"{t} turns"

    PERMANENT_LIGHT = 10 ** 6       # (light_left of a light that shows no turns: it doesn't burn, so it ranks first)

    @staticmethod
    def light_left(i):
        """Turns of light left (world.light_turns), a permanent light (no turns shown) as PERMANENT_LIGHT."""
        t = light_turns(i["name"])
        return ItemsMixin.PERMANENT_LIGHT if t is None else t

    def best_light(self):
        """The light in the pack with the most fuel left (not a burnt-out one), or None."""
        return max((i for i in self.w.items(tval=TV_LITE) if self.light_left(i) > 0), key=self.light_left, default=None)

    def wear_light(self, why):
        """Put the best light in the pack on (reading needs one: the Pilot takes it
        off in town). True if it acted."""
        lite = self.best_light()
        if not lite:
            return False
        self.light_t = gnow() + 60         # (town_light leaves it on meanwhile)
        self.cmd(f"custom w item={lite['item']}", f"light on: {why}", hold=0.8)
        return True

    def warn_light(self, key, text):
        """A light warning once per state (low -> out), again after 10 min; in
        town it's news, not an alert (Dive04 raised 573 'lantern at 0 turns'
        alerts, one every 2 min while it idled in town: the post-mortem's §4.7)."""
        now = gnow()
        if key == self.light_warned_key and now - self.light_warned < 600:
            return
        self.light_warned, self.light_warned_key = now, key
        self.notify("supplies", text, news=not self.w.in_dungeon,
                    fields={"supply": "light", "level": "out" if key in ("lantern out", "torch out", "no light") else "low"})

    def auto_destroy(self, now):
        """Destroy the pack's junk (is_junk: the junk order, harmful devices, junk flavours, Broken items, the
        autodestroy feelings...; the Navigator was cleaning the pack by hand every few minutes)."""
        w = self.w
        if now < self.busy_until or now - self.autodestroy_t < 2 or w.inven_dirty:
            return False
        for it in w.items():
            if self.is_junk(it):
                self.autodestroy_t = now
                self.c.send("confirm yes")
                self.cmd(f"custom k item={it['item']} value={it['number']}", f"autodestroy junk {self.named(it['name'])}",
                         hold=0.6)
                w.inven_dirty = True
                return True
        return False

    # (`wearall`'s slots: the gear evaluator's table without diggers (20: not a weapon to fill the hands with) and
    # rings (45) -- left out as they always were; refactor-candidates D11)
    WEAR_TVALS = {tv: s for tv, s in geareval.SLOT_OF_TVAL.items() if tv not in (20, 45)}

    def wear_step(self):
        """One item per call (letters shift after each): wear what fills an empty slot."""
        w = self.w
        if gnow() < self.busy_until or w.inven_dirty:
            return
        worn = {self.WEAR_TVALS.get(i["tval"]) for i in w.items(equip=True)}
        # (the best light first: mission 12 put on a 403-turn torch with a
        # full lantern in the pack)
        for it in sorted(w.items(), key=lambda i: -self.light_left(i) if i["tval"] == TV_LITE else 0):
            if it["tval"] == TV_LITE and self.light_left(it) == 0:
                continue
            if it["tval"] in (40, 45) and self.unknown_flavour(it):
                continue            # unknown jewellery: 19-58% cursed, sticks, never identifies (Advisor)
            kind = self.WEAR_TVALS.get(it["tval"])
            if kind and kind not in worn:
                self.cmd(f"custom w item={it['item']}", f"wear {it['name']}", hold=0.8)
                w.inven_dirty = True
                return
        self.wear_queue = False
