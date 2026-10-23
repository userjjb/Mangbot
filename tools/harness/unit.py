"""unit -- the harness's U-kind set-pieces: the Pilot's decision code on constructed states, no server.

Restructure step 4 (the Advisor's set-piece memo: U = a unit test on a constructed state). Run after any
Pilot or rulebook change:

    python3 unit.py            # every case; exit status 1 if one fails
    python3 unit.py hunt       # the cases whose name contains "hunt"
"""
import collections
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pilot"))
import pilot as P                  # noqa: E402
import glyphs                      # noqa: E402
import itemvalue                   # noqa: E402

RACES = glyphs.load_rulebook(glyphs.load_races())
BYNAME = {r.name.lower(): r for r in RACES.values()}
CASES = []


def case(f):
    CASES.append(f)
    return f


class G:
    races = RACES


class W:
    """A constructed world: Dive04 as of 2026-10-23 unless a case changes it."""
    depth = 6
    depth_ft = 300
    in_dungeon = True
    store = None
    store_t = 0
    inven_dirty = False
    level_t = 1.0
    pos = (20, 20)

    def __init__(self, hp=265, pack=(), worn=None, monsters=(), gold=172):
        self.hp = [hp, 265]
        self.g = G()
        self.monsters = list(monsters)
        self.messages = collections.deque(maxlen=300)
        self.ind = {"armor": [56], "stat0": [58], "stat3": [28], "stat5": [3], "gold": [gold]}
        self.flags = {"free_act": 0, "res_blind": 0, "res_conf": 0, "res_nexus": 0, "hold_life": 0, "feather": 0}
        worn = worn if worn is not None else [("a Spear (1d6) (+5,+7)", 22, 50)]
        self.inven = [{"item": 24 + i, "name": n, "tval": t, "weight": wt, "number": 1, "equip": True}
                      for i, (n, t, wt) in enumerate(worn)]
        self.inven += [{"item": i, "name": n, "tval": t, "weight": 10, "equip": False,
                        "number": int(n.split()[0]) if n[0].isdigit() else 1} for i, (n, t) in enumerate(pack)]
        self.clvl = 22

    @property
    def hp_frac(self):
        return self.hp[0] / self.hp[1]

    def items(self, *, tval=None, name=None, equip=False):
        return [i for i in self.inven if i["equip"] == equip and (tval is None or i["tval"] == tval)]

    def has(self, f):
        return bool(self.flags.get(f))

    def dist(self, q, r=None):
        a = r or self.pos
        return max(abs(q[0] - a[0]), abs(q[1] - a[1]))

    def flag(self, k):
        return False


def pilot(w=None, **kw):
    p = P.Pilot.__new__(P.Pilot)
    p.w = w or W(**kw)
    p.orders = {"max_depth": 650, "rest_to": 1.0}
    p.deepest_ft = 650
    p.seen_drained = {"CON": (18, 18), "STR": (58, 68), "WIS": (9, 10), "CHR": (3, 5)}
    p.stores_seen, p.flavours, p.keep, p.ability_sources, p.inferred = {}, {}, set(), set(), set()
    p.aware_cache = (-1, set())
    p.unique_names = {r.name.lower() for r in RACES.values() if "UNIQUE" in r.flags}
    p.junk_kinds = {}
    p.req_role = "navigator"
    p.band_warned, p.band_warned_t = (None, 0), 0.0
    p.log = lambda *a, **k: None
    p.notes = []
    p.notify = lambda what, d=None, news=False: p.notes.append((what, d))
    p.ability_seen_t = 0
    p.emerg_times = []
    return p


PHASE = ("11 Scrolls of Phase Door", 70)


# --- hunts (A7's HP halves; A8's rule) ---------------------------------------------------------
@case
def hunt_hill_giant_by_hp():
    """A7: a Hill giant hunt is allowed at 100% and 80% HP and refused at 60% (p90 ~123 > 0.6 x 159)."""
    out = []
    for hp in (265, 212, 159):
        why, info = pilot(hp=hp, pack=[PHASE]).hunt_refusal("Hill giant")
        out.append(why is None)
    return out == [True, True, False], f"allowed at 265/212/159 HP: {out}"


@case
def hunt_ranger_summoner():
    """A8: the Ranger hunt is refused with another monster in view, allowed alone at full HP with 5+ Phase."""
    other = [(22, 22, BYNAME["skeleton human"])]
    refused = pilot(pack=[PHASE], monsters=other).hunt_refusal("Ranger")[0]
    alone = pilot(pack=[PHASE]).hunt_refusal("Ranger")[0]
    no_phase = pilot(pack=[]).hunt_refusal("Ranger")[0]
    ok = bool(refused) and "summons" in refused and alone is None and bool(no_phase)
    return ok, f"with a skeleton: {bool(refused)}; alone: {alone is None}; without Phase: {bool(no_phase)}"


@case
def hunt_qualitative_vetoes():
    """Paralysers without Free Action and qualitative AVOID/LEAVE ratings refuse; strength-only ratings don't."""
    p = pilot(pack=[PHASE])
    res = {n: p.hunt_refusal(n)[0] is not None for n in ("Ghoul", "Carrion crawler", "Wormtongue, Agent of Saruman",
                                                         "Boldor, King of the Yeeks", "Brodda, the Easterling")}
    want = {"Ghoul": True, "Carrion crawler": True, "Wormtongue, Agent of Saruman": True,
            "Boldor, King of the Yeeks": True, "Brodda, the Easterling": False}
    return res == want, f"refused: {res}"


# --- items ------------------------------------------------------------------------------------
@case
def jewellery_unknown_plusses():
    """A known ring kind without its plusses is an estimate with P(cursed copy); with them it's known."""
    a, b = itemvalue.value("a Ring of Protection", 13), itemvalue.value("a Ring of Protection [+8]", 13)
    return (not a.known and a.p_cursed > 0.3 and b.known and b.value == 1300), \
        f"unknown {a.value} p_cursed {a.p_cursed:.2f}; known {b.value}"


@case
def unique_drop_feeling():
    """{good - Brodda, the Easterling} reads as a {good} feeling (unidentified)."""
    v = itemvalue.value("a Pair of Metal Shod Boots [6] {good - Brodda, the Easterling}", 13)
    return v.known is False and v.pseudo == "good", f"known={v.known} pseudo={v.pseudo}"


@case
def junk_kinds_from_rulebook():
    """The rulebook's junk kinds are the 38 of the old kinds.csv."""
    p = pilot()
    p.flavour_file = "/nonexistent"
    p.load_flavours()
    n = sum(1 for v in p.junk_kinds.values() if v)
    return n == 38, f"{n} junk kinds"


@case
def shop_pay_by_owner():
    """Six real sales of 2026-10-23 predicted to the gold piece from value x the owner's pay%."""
    sys.path.insert(0, os.path.join(HERE, "..", "observe"))
    import shopmath
    sales = [("a Small Leather Shield [2,+0]", 18, "Kon-Dar the Ugly"), ("a Dagger (1d4) (+0,+0)", 5, "Ithyl-Mak the Beastly"),
             ("a Scroll of Door/Stair Location", 14, "Ludwig the Humble"), ("a Potion of Infravision", 8, "Ludwig the Humble"),
             ("2 Potions of Neutralize Poison", 62, "Ludwig the Humble"),
             ("a Wand of Stinking Cloud (13 charges)", 231, "Ariel the Sorceress")]
    bad = [n for n, got, o in sales if round(itemvalue.value(n, 8).value * itemvalue.value(n, 8).count *
                                              shopmath.factors(o, 3)[0] / 100) != got]
    return not bad, f"mispredicted: {bad}"


# --- the town kit -----------------------------------------------------------------------------
@case
def town_kit_tiers():
    """Dive04's pack after m23: WoR to 2 first, Restore CON before the kit's extras, the kit's CSW/Phase/flasks."""
    pack = [("3 Rations of Food", 80), ("3 Flasks of oil", 77), ("2 Potions of Cure Serious Wounds", 75),
            ("6 Potions of Cure Critical Wounds", 75), ("9 Scrolls of Phase Door", 70),
            ("a Scroll of Word of Recall {@R650}", 70), ("a Brass Lantern (with 6370 turns of light)", 39)]
    w = W(pack=pack, gold=637)
    w.depth, w.depth_ft, w.in_dungeon = 0, 0, False
    p = pilot(w)
    p.seen_drained = {"CON": (17, 18)}
    need = [(t, k, n) for t, k, s, n, c in p.town_needs(None, ())]
    want = [(1, "Word of Recall", 1), (3, "Restore Constitution", 1), (4, "Cure Serious Wounds", 2),
            (4, "Phase Door", 1), (4, "Flask of oil", 2), (4, "Ration of Food", 1)]   # (food 3 of kit B's 4)
    return need == want, f"{need}"


# --- the trip plan ----------------------------------------------------------------------------
@case
def trip_conditions_parse():
    """Conditions parse; unknown words and wrong value types are refused."""
    ok = P.TripPlan.parse_until("cures<4 or phase<5 or time>22:40 or band")
    bad = []
    for t in ("foo<3", "time>5", "band or bogus"):
        try:
            P.TripPlan.parse_until(t)
            bad.append(t)
        except ValueError:
            pass
    return len(ok) == 4 and not bad, f"parsed {len(ok)}; not refused: {bad}"


# --- abilities --------------------------------------------------------------------------------
@case
def ability_proofs():
    """'You are unaffected!' proves rBlind after a blinding spell, rNexus after TELE_LEVEL, Free Action after a
    paralysing touch; the sustain and hold-life messages prove themselves."""
    p = pilot()
    t = time.time()
    p.w.messages.extend([(t, "The Dark elven priest casts a spell, burning your eyes!"), (t + .1, "You are unaffected!"),
                         (t + 1, "The Gnome mage gestures at your feet."), (t + 1.1, "You are unaffected!"),
                         (t + 2, "The Ghoul touches you."), (t + 2.1, "You are unaffected!"),
                         (t + 3, "You feel weak for a moment, but the feeling passes."),
                         (t + 4, "You keep hold of your life force!")])
    p.watch_abilities()
    want = {"free_action", "hold_life", "resist_blind", "resist_nexus", "sustain_str"}
    return p.inferred == want, f"{sorted(p.inferred)}"


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else ""
    fails = 0
    for f in CASES:
        if want and want not in f.__name__:
            continue
        try:
            ok, detail = f()
        except Exception as e:
            ok, detail = False, f"error {e!r}"
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'} {f.__name__}: {detail}")
    print(f"{len(CASES) - fails if not want else ''} passed, {fails} failed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
