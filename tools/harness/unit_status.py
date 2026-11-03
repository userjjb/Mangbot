"""unit_status -- unit cases: Status effects (fear, blindness, confusion, drains, breeders, theft).

Run by unit.py (python3 unit.py [NAME]); W, pilot() and the other shared fixtures are in fixtures.py.
"""
import collections

from fixtures import P, RACES, BYNAME, case, pilot


@case
def unseen_drainer_leaves():
    """m29, m30: a Moaning spirit (invisible, passes walls, +10, TOUCH:LOSE_DEX) drained DEX; nothing was in view
    so no drainer rule fired. A drain with nothing in view that drains (and no trap's dart) -> leave the level
    (the trip plan's drainer leave; without a plan, Flee to known stairs). A dart trap -> no leave."""
    def run(msg, monsters=()):
        p = pilot()
        p.w.in_dungeon, p.w.level_t = True, 5.0
        p.w.monsters = list(monsters)
        p.w.ind.update({f"stat{i}": [v, v] for i, v in enumerate((58, 5, 9, 28, 18, 3))})
        p.seen_drained, p.seen_blows = None, None
        p.drains_here = (None, 0)
        p.plan, p.goal = None, None
        p.w.find = lambda chars: [(30, 30)]
        p.w.adjacent_monsters = lambda: [m for m in p.w.monsters if p.w.dist(m[:2]) == 1]
        p.set_goal = lambda g: setattr(p, "goal", g)
        p.watch_character()                       # the baseline
        p.w.ind["stat3"] = [18, 28]               # DEX 18/10 -> 18
        p.w.messages.append((P.gnow(), msg))
        p.watch_character()
        return [w for w, _ in p.notes], type(p.goal).__name__
    ghost = run("It touches you.")
    dart = run("A small dart hits you!")
    frog = run("The Giant red frog bites you.", [(20, 21, BYNAME["giant red frog"])])
    ok = "drainer" in ghost[0] and ghost[1] == "Flee" and "drainer" not in dart[0] and dart[1] == "NoneType" and \
        "drainer" not in frog[0]
    return ok, f"unseen: {ghost}; dart trap: {dart}; a visible frog (its own rules): {frog}"


@case
def fear_cure_order():
    """The user (10-25): afraid and in danger, Heroism first; Boldness only without Heroism; Berserk last (the
    pack's own order decided before)."""
    def pick(pack):
        return (pilot(pack=pack).fear_cure() or {}).get("name")
    both = pick([("a Potion of Boldness", 75), ("a Potion of Berserk Strength", 75), ("2 Potions of Heroism", 75)])
    bold = pick([("a Potion of Berserk Strength", 75), ("a Potion of Boldness", 75)])
    last = pick([("a Potion of Berserk Strength", 75)])
    ok = both == "2 Potions of Heroism" and bold == "a Potion of Boldness" and last == "a Potion of Berserk Strength"
    return ok, f"all three: {both}; no Heroism: {bold}; only Berserk: {last}"


@case
def theft_is_news():
    """m51, m53: Novice rogues stole 2617 and 2392 gold and nothing said so. The theft message is news, with the
    total; a stolen item too."""
    q = pilot()
    q.gain_hist, q.w.hp_hist, q.hits, q.mons_mem = collections.deque(maxlen=80), [], collections.Counter(), {}
    q.belief_msg_t, q.kills_t = 0.0, 0.0
    for t in ("2617 coins were stolen!", "2392 coins were stolen!", "Your Hard Studded Leather [7] {excellent} (u) "
              "was stolen!"):
        q.w.messages.append((P.gnow(), t))
    try:
        q.belief_tick(P.gnow())
    except Exception:
        pass
    news = [d for what, d in q.notes if what == "thief"]
    ok = len(news) == 3 and "5009 stolen" in news[1] and news[2].startswith("Hard Studded Leather [7] {excellent} stolen")
    return ok, f"news {news}"


@case
def breeder_swarm_leaves():
    """m40: weak breeders (Giant fruit flies) were news once per level; they grew to 16 and boxed the Pilot in. At 8
    or more the notice comes again, not as news (the trip leaves on it)."""
    fly = next(r for r in RACES.values() if "MULTIPLY" in r.flags and r.level <= 10)
    p = pilot(monsters=[(20, 22 + k, fly) for k in range(3)])
    p.goal, p.breeder_level, p.w.clvl = None, None, 27
    notes = []
    p.notify = lambda what, d=None, news=False, action=True, fields=None: notes.append((what, news))
    p.watch_breeders()
    p.w.monsters = [(20, 22 + k, fly) for k in range(9)]
    p.watch_breeders()
    p.watch_breeders()
    ok = notes == [("breeders", True), ("breeders", False)]
    return ok, f"{fly.name}: {notes}"


@case
def blind_cured_when_it_matters():
    """m43 23:20: blinded in a 10-monster band at 84% HP, nothing "near" can be seen blind -- it rested while unseen
    monsters bit it and the flee couldn't read. Blind is cured (cheapest first) when a band was warned in the last
    30 s, monsters were seen within 6 squares in the last 10 s, or an escape needs to read; not blind and alone."""
    def make(**kw):
        p = pilot(hp=274, pack=[("2 Potions of Cure Light Wounds", 75), ("5 Potions of Cure Critical Wounds", 75)])
        p.w.hp = [274, 326]
        p.w.in_dungeon = True
        p.w.flag = lambda k: k == "blind"
        p.w.adjacent_monsters = lambda: []
        p.w.last_hit_t = P.gnow() - 20
        p.w.damage_rate = lambda s: 0.0
        p.cure_t, p.goal = 0.0, None
        p.orders["think_hp"] = 0.65
        p.mons_mem = {}
        p.cmds = []
        p.cmd = lambda line, why, hold=0.4: p.cmds.append(why)
        for k, v in kw.items():
            setattr(p, k, v)
        return p
    band = make(band_warned=(1.0, 10), band_warned_t=P.gnow() - 5)
    band.status_tick(P.gnow(), [])
    seen = make(mons_mem={"Druid": {"level": 1.0, "pos": (22, 22), "n": 1, "t": P.gnow() - 3}})
    seen.status_tick(P.gnow(), [])
    alone = make()
    alone.status_tick(P.gnow(), [])
    # (m44: Light hounds re-blinding -- after 2 cures in 30 s it fights on blind)
    again = make(band_warned=(1.0, 10), band_warned_t=P.gnow() - 5, blind_cures=[P.gnow() - 10, P.gnow() - 4])
    again.status_tick(P.gnow(), [])
    ok = band.cmds and "Cure Light Wounds" in band.cmds[0] and seen.cmds and alone.cmds == [] and again.cmds == []
    return ok, f"band warned: {band.cmds}; a Druid seen 3 s ago: {seen.cmds}; alone: {alone.cmds}; 3rd in 30 s: " \
               f"{again.cmds}"


@case
def recall_cures_confusion_first():
    """m55: `goal recall` sat 4 minutes, confused by Hummerhorns, the read refused; the Navigator quaffed a CSW. Now
    the recall quaffs the cheapest cure first: confused -> Cure Serious (CLW doesn't end it); blind only -> CLW."""
    def run(state):
        p = pilot(pack=[("2 Scrolls of Word of Recall", 70), ("3 Potions of Cure Light Wounds", 75),
                        ("3 Potions of Cure Serious Wounds", 75), ("a Brass Lantern", P.TV_LITE)])
        p.w.inven[0]["equip"] = True
        p.w.inven[0]["tval"] = P.TV_LITE
        p.w.flag = lambda k: k == state
        p.w.recall_pending = False
        p.recall_t = 0.0
        sent = []
        p.cmd = lambda line, why, hold=0.4: sent.append(why)
        g = P.Recall()
        g.tick(p)
        return sent
    conf, blind, clear = run("confused"), run("blind"), run(None)
    ok = len(conf) == 1 and "Cure Serious" in conf[0] and len(blind) == 1 and "Cure Light" in blind[0] and \
        len(clear) == 1 and clear[0].startswith("read ")
    return ok, f"confused: {conf}; blind: {blind}; clear: {clear}"


@case
def confusion_lock_is_cured():
    """m55: Hummerhorns kept Dive04 confused for 15 minutes; the dive waited for it to wear off. After 8 s confused
    with monsters adjacent the Pilot quaffs Cure Serious (not before 8 s, not again within 8 s, at most 4 a level);
    an escape the game refused shows as FAILED, not LANDING."""
    p = pilot(pack=[("3 Potions of Cure Serious Wounds", 75), ("3 Potions of Cure Critical Wounds", 75)],
              monsters=[(20, 21, BYNAME["hummerhorn"])])
    p.w.flag = lambda k: k == "confused"
    p.w.adjacent_monsters = lambda: [(20, 21, BYNAME["hummerhorn"])]
    p.busy_until = 0
    sent = []
    p.cmd = lambda line, why, hold=0.4: sent.append(why)
    first = p.confusion_lock()
    p.conf_since -= 9
    second = p.confusion_lock()
    third = p.confusion_lock()
    p.escape_read_t, p.escape_from = P.gnow() - 1, ((20, 20), "a Staff of Teleportation")
    p.w.messages.append((P.gnow() - 0.5, "You failed to use the staff properly."))
    line = p.escape_line()
    ok = (first, second, third) == (False, True, False) and len(sent) == 1 and "Cure Serious" in sent[0] and \
        "FAILED" in line
    return ok, f"{first}, {second}, {third}: {sent}; {line!r}"


@case
def confusion_window_teleports():
    """M5 (10-28): each cure bought ~1 s before the next Hummerhorn bite. Cured (0.3-4 s ago), clear, 3+ adjacent: the
    staff (or a scroll) teleports us away, once a cure; not with fewer adjacent, not while still confused."""
    def run(adj, confused=False, ago=1.0):
        p = pilot(pack=[("a Staff of Teleportation (12 charges)", 55)])
        p.w.adjacent_monsters = lambda: [(20, 21, BYNAME["hummerhorn"])] * adj
        p.w.flag = lambda k: confused and k == "confused"
        p.busy_until, p.conf_cure_t = 0, P.gnow() - ago
        sent = []
        p.cmd = lambda line, why, hold=0.4: sent.append(line)
        first = p.confusion_window()
        again = p.confusion_window()
        return first, again, sent
    a, b, c = run(5), run(2), run(5, confused=True)
    ok = a[0] and not a[1] and a[2] == ["custom u item=0"] and not b[0] and not c[0]
    return ok, f"5 adjacent {a}; 2 adjacent {b[0]}; still confused {c[0]}"


@case
def breeder_swarm_pin_teleports_once():
    """m45 (fleas) and m48 (lice): a dive leaving a breeder level got pinned in the swarm (stuck notices) until
    LEAVE_MAX's recall. Now the first stuck notice on such a level reads/uses a teleport, once per level."""
    p = pilot(pack=[("a Staff of Teleportation (6 charges)", 55)])
    p.w.level_t = 7.0
    tp = P.TripPlan(700, 800, P.TripPlan.parse_until("minutes>30"))
    tp.phase, tp.level, tp.level_done = "level", 7.0, "left: breeders"
    sent = []
    p.cmd = lambda c, why, hold=0: sent.append(c)
    tp.on_event(p, "stuck", "'dive 800ft' hasn't moved", False)
    tp.on_event(p, "stuck", "'dive 800ft' hasn't moved", False)
    tp2 = P.TripPlan(700, 800, P.TripPlan.parse_until("minutes>30"))
    tp2.phase, tp2.level, tp2.level_done = "level", 7.0, "left: a band"
    tp2.on_event(p, "stuck", "x", False)
    ok = sent == ["custom u item=0"]
    return ok, f"sent {sent}"


@case
def blind_escape_uses_the_staff_and_sees_refused_reads():
    """m48 (750 ft, 13 Light hounds re-blinding): a Word of Recall read 0.14 s before the blinding was refused ("You
    can't see anything.") and the Pilot waited 8 s and wouldn't retry; a Teleportation scroll later failed the same way;
    the Staff of Teleportation (usable blind) only came when the Navigator forced it. Now: blind -> the staff; a refused
    read is seen at once, the escape timers reset, and the staff is preferred for 10 s."""
    p = pilot(pack=[("a Scroll of Teleportation", 70), ("a Staff of Teleportation (5 charges)", 55)])
    p.w.flag = lambda k: False
    seeing = p.teleport_item()
    p.w.flag = lambda k: k == "blind"
    blind = p.teleport_item()
    p.w.flag = lambda k: False
    p.pending_use = {"t": P.gnow() - 1, "core": "Word of Recall", "why": "group danger", "tries": 0}
    p.dead, p.w.ghost = False, False
    p.escape_read_t, p.recall_t = P.gnow() - 1, P.gnow() - 1
    p.w.messages.append((P.gnow() - 0.5, "You can't see anything."))
    p.verify_use()
    after = p.teleport_item()
    ok = seeing[0] == "r" and blind[0] == "u" and p.pending_use is None and p.escape_read_t < 0 and \
        p.recall_t == 0.0 and after[0] == "u" and any("refused" in str(d) for _, d in p.notes)
    return ok, f"seeing: {seeing[0]}; blind: {blind[0]}; after a refused read: {after[0]}; pending {p.pending_use}"
