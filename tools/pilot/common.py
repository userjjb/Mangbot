"""common -- constants and helpers the Pilot's modules share (refactor-candidates E1): pilot.py, report.py, daemon.py,
goals.py, town_goals.py, plan.py, gear.py, items.py.

pilot.py imports them all back (P.VERSION, P.TV_FOOD, P.weapon_damage, ...), so its names stay where they were.
"""
import os
import re

import geareval

HERE = os.path.dirname(os.path.abspath(__file__))

try:
    # the code's version (major.minor.patch, CHANGELOG.md; minor = play can differ, patch = it can't): read once at
    # startup, so it names the code this Pilot runs
    VERSION = open(os.path.join(HERE, "..", "..", "VERSION")).read().strip()
except OSError:
    VERSION = "?"

TV_SCROLL, TV_POTION, TV_FOOD, TV_FLASK, TV_LITE = 70, 75, 80, 77, 39


# Brand egos: x3 on the dice against monsters that don't resist the element
# (mission 21 compared a Lucerne Hammer of Venom at ~18 a round, brand ignored)
BRANDS = {"Venom": "poison", "Burning": "fire", "Flame": "fire", "Freezing": "cold", "Frost": "cold",
          "Melting": "acid", "Lightning": "lightning"}


def weapon_brand(name):
    """(element, multiplier) for a brand ego, else None."""
    m = re.search(r"\bof (\*?)(" + "|".join(BRANDS) + r")\b", name)
    return (BRANDS[m.group(2)], 3) if m else None


def weapon_damage(name, blows, mult=1):
    """Average damage per round: (dice average + to-dam) x blows (0 without dice)."""
    it = geareval.Item(name)              # (the dice and plusses as the gear evaluator reads them: D6)
    dn, ds = (int(x) for x in it.dice.split("d"))
    if not dn:
        return 0.0
    return (dn * (ds + 1) / 2 * mult + it.to_d) * blows


DEFAULT_ORDERS = {
    "flee_hp": 0.5,        # emergency below this HP fraction
    "think_hp": 0.65,      # tell the agent below this, while fighting
    "rest_below": 0.7,     # rest when nothing is in view and HP is below this
    "rest_to": 0.95,
    "arrival_pack": 4,     # this many monsters in view on arrival -> leave by the stairs
    "danger_level": 6,     # a monster this many levels above ours in view -> leave/avoid
    "free_action": "no",   # yes once the character has Free Action: paralysers stop counting as danger
    "resist_blind": "no",  # yes once worn: monsters that blind with their blows stop counting as danger
    "resist_conf": "no",   # the same for confusing blows
    "unseen_hp": "on",     # off: don't treat HP loss with nothing in view as an unseen attacker
    "autowear": "on",      # off: the Pilot doesn't wear, wield or swap gear by itself (upgrade_step)
    "enchant_max": 25,     # Scrolls of Enchant Armor plan town may buy a visit (0: none) -- m58: 25 for 5025 gold, unasked
    "idle_recall_s": 600,  # no goal and no agent contact for this long -> recall to town
                           # (long enough for a slow agent turn; 180 s fired mid-thought)
    "pickup": "all",       # all | none
    "stop_on": "unique,danger",  # what makes a dive stop and ask (also: items, pillared)
    "pillared": "explore",       # dive: explore pillared rooms for a '>' by itself (or: ask, ignore)
    "loot_radius": 10,           # dive: fetch items seen within this many squares (0 = off)
    "choke": "on",               # meet packs in a corridor, not in the open (the user's advice)
    "autodestroy": "worthless,cursed",   # pseudo-ID feelings whose items get destroyed (add 'average')
    "junk": "Salt Water,Blindness,Weakness,Sleep,Poison,Lose Memories,Confusion,Sickliness,"
            "Apple Juice,Slime Mold,Darkness,Aggravate Monster,Curse Weapon,Curse Armour,"
            "Summon Undead,Summon Monster,Treasure Detection,Detect Invisible",
                                 # items "of <these>" aren't picked up (unknown items still are)
    "band_frac": 0.5,            # a band is serious (leave) when fighting it all costs more than this x HP
    "nopickup": "",              # comma list of name parts never picked up (the Navigator's per-trip junk list)
    "max_depth": 0,              # feet; 0 = no limit. Dives stop there, explore refuses below it,
                                 # and after an emergency trip down the stairs we come back up
}


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def flavour_key(name):
    """'2 Puce Potions {tried}' -> 'Puce Potion' (the flavour table's key)."""
    n = re.sub(r"\{.*?\}", "", name).strip()
    n = re.sub(r"^(a|an|the|\d+) ", "", n)
    n = re.sub(r"(Potion|Scroll|Wand|Staff|Rod|Ring|Amulet|Mushroom)s\b", r"\1", n)
    return re.sub(r"\s*\(.*?\)", "", n).strip()


def kind_key(name):
    """'a Potion of Weakness' / '3 Wands of Magic Missile (10 charges)' -> 'Potion of Weakness'."""
    n = re.sub(r"\{.*?\}|\(.*?\)|\[.*?\]", "", name).strip()
    n = re.sub(r"^(a|an|\d+) ", "", n)
    n = re.sub(r"(Potion|Scroll|Wand|Staff|Rod|Ring|Amulet|Mushroom)s\b", r"\1", n)
    return re.sub(r"\s+[-+]\d+.*$", "", n).strip()


def bare_name(name):
    """'3 Flasks of oil {@v1}' -> 'Flasks of oil': the name without its inscription and its article or count (kind_key
    also drops the (charges) and the plural; refactor-candidates D2)."""
    return re.sub(r"^(an?|\d+) ", "", re.sub(r"\s*\{[^}]*\}", "", name))


def one_of(name):
    """'2 Potions of Boldness' -> 'a Potion of Boldness' (what one use takes;
    mission 6's news said 'quaffed 2 Potions' when 1 was left)."""
    return re.sub(r"^\d+ (\S+?)s of ", r"a \1 of ", name)


def recall_level(name):
    """The dungeon level a Word of Recall read in town takes us to, from its
    inscription, as the server reads it (spells2.c:1153): the *last* @R wins;
    a number divisible by 50 is feet, anything else a level number. None when
    there's no valid @R (the server then uses the deepest level ever reached,
    and so does a value deeper than that). The forum: a typo ('@r') recalled
    a player onto Morgoth."""
    level = None
    for m in re.finditer(r"@R(-?\d*)", name):
        n = int(m.group(1)) if m.group(1) not in ("", "-") else 0
        level = n // 50 if n % 50 == 0 else n
    return level or None


def singular(t):
    """Plural endings dropped, for name matching ("Flask of oil" finds
    "99 Flasks of oil": missions 17-18)."""
    return re.sub(r"\b(\w+?)(?:es|s)\b", r"\1", t.lower())


def bad_inscription(name):
    """True if the name shows a curse or a bad feeling: {cursed}, {worthless}, {broken}, {terrible}."""
    return bool(re.search(r"\{(cursed|worthless|broken|terrible)", name))
