"""cmdtable -- the Pilot's command table (refactor-candidates E2; docs/commands.md): every pilotctl command, the method
of Pilot that answers it, who may use it, where, how it takes its arguments, and its line of help.

Read by commands.py (`Pilot.do_request`: look the command up, then the role check, the dungeon check, the stale-order
check -- stale_order picks the positional orders by their arguments -- and the ghost check, in that order, then call
the method) and by pilotctl.py (its help, printed with no
command, also when the Pilot is down). Plain data and the standard library only: it must not import the Pilot.

Adding a command: write the method (on CommandsMixin in commands.py, or wherever its state lives), add an entry
here, and say what it does in docs/commands.md. unit.py's command_table_* cases check that every entry's method
exists, its roles and fields are valid, and the help lists it.
"""
import collections
import textwrap

ROLES = ("navigator", "architect", "user")   # the roles a request claims (`role`; architect needs the token: F3)
ANY = "any"                 # roles: anyone (any role a request claims, or none)
ARCH = ("architect",)       # roles: the Architect only (an authenticated claim)

# a role refusal's text; {name} is the command (with its sub-command: `goal goto`)
PILOTS_NOW = ("`{name}` is the Pilot's now: use `goal leave` (this level, by the nearest stairs), `goal fetch Y,X` "
              "(one item), `plan trip ...` or `goal dive FEET`")
# the dungeon refusal of a `where` town/town_target command for anyone but the Architect; {name} is the command
DUNGEON_ITEMS = ("in the dungeon the Pilot handles items itself (pickup, identify, wear upgrades, fuel, eat): `{name}` "
                 "is for town, between trips. You may `destroy`/`drop` junk, and `order nopickup=NAME,...` keeps kinds "
                 "out. To protect an item from its policy use `keep NAME`")
DEAD = ("the character is dead (a ghost): 'goal resurrect' floats it to town and resurrects it; until then only "
        "queries, notes, park, stop, order and plan stop work")
CONTROL = ("`{name}` is the Architect's: it stops, logs out or reconfigures the Pilot (`restart.sh`/`charsave.sh` "
           "pass the Architect's token; 2.45.0)")

# method   the Pilot method that answers it
# call     how the method takes the request: "args" (the argument list), "text" (the words joined by spaces),
#          "name" (joined, "_" read as a space), "none" (nothing), "cmd" (the command name and the list: one method
#          for several commands), "req" (the list and the whole request)
# reply    "dict" (the method's own reply) or "text" (its string, sent as {"ok": True, "text": ...})
# roles    ANY or ARCH; refusal: the text for a role it refuses ({name} = the command)
# where    "any"; "town": refused in the dungeon (DUNGEON_ITEMS) unless the Architect; "town_target": the same with
#          a target item (a second word that isn't `force`: `read Identify a`, `use Perception a`)
# dead     answers for a ghost (others are refused with DEAD)
# logged   logged as nav_cmd and counted as agent activity (False: the viewer's polls)
# viewer   one of the viewer's read-only queries: an architect claim without the token is not raised as role_refused
# messages the reply carries the unanswered user messages (not for note, say, status: those show them otherwise)
# subs     {SUB: {"roles", "refusal", "dead"}}: a sub-command (the first argument) with its own rule
# usage, help, group: pilotctl's help (the groups as in docs/commands.md)
Cmd = collections.namedtuple("Cmd", "method call reply roles refusal where dead logged viewer messages subs usage help "
                                    "group",
                             defaults=("args", "dict", ANY, None, "any", False, True, False, True, None, "", "", "Control"))

GROUPS = ("Info", "Goals and plans", "Items", "Orders", "Town", "Notes", "Mission", "Control", "Viewer")

_ITEM = dict(method="item_action", call="cmd", group="Items")

COMMANDS = {
    # --- answered for a ghost too (dead=True): the queries and notes ---
    "status": Cmd("cmd_status", call="req", dead=True, messages=False, usage="status [full]",
                  help="the compact report (`full`: the long one)", group="Info"),
    "mission": Cmd("cmd_mission", roles=ARCH, refusal="mission markers are the Architect's (refactor-candidates F4)",
                   dead=True, logged=False, usage="mission start LABEL [navigator=M] [effort=L] [notes=T] | mission end [LABEL]",
                   help="mission start/end markers (missions.json)", group="Mission"),
    "keep": Cmd("cmd_keep", dead=True, usage="keep [NAME | -NAME]", help="protect an item kind from the value policy",
                group="Orders"),
    "standing": Cmd("cmd_standing", dead=True, usage="standing [TEXT | -N]",
                    help="standing instructions shown in every report", group="Orders"),
    "react": Cmd("cmd_react", dead=True,
                 usage="react leave NAME | hunt NAME | thieves kill | afraid teleport | -N | clear",
                 help="executable standing orders, run at Pilot speed", group="Orders"),
    "review": Cmd("cmd_review", dead=True, usage="review [sell|keep|wear NAME]",
                  help="items held for your word before they're sold", group="Orders"),
    "debt": Cmd("cmd_debt", call="none", dead=True, usage="debt", help="the Navigator's item and fight debt",
                group="Info"),
    "pack": Cmd("cmd_pack", call="none", dead=True, usage="pack", help="the pack with values", group="Info"),
    "equip": Cmd("cmd_equip", call="none", dead=True, usage="equip", help="the equipment (letters A, B, ...)",
                 group="Info"),
    "orders": Cmd("cmd_orders", call="none", dead=True, usage="orders", help="the standing orders", group="Info"),
    "map": Cmd("cmd_map", dead=True, usage="map [R]", help="the map within R squares (default 15)", group="Info"),
    "view": Cmd("cmd_view", dead=True, logged=False, viewer=True, usage="view [ROWS] [COLS]",
                help="the long report with a bigger map", group="Viewer"),
    "navview": Cmd("cmd_navview", call="none", dead=True, logged=False, viewer=True, usage="navview",
                   help="what the Navigator last saw", group="Viewer"),
    "avoid": Cmd("cmd_avoid", dead=True, usage="avoid [Y,X [R] | NAME | clear | pass]",
                 help="no-go zones for paths", group="Orders"),
    "viewmap": Cmd("cmd_viewmap", dead=True, logged=False, viewer=True, usage="viewmap [ROWS] [COLS]",
                   help="JSON: the map and colours around @", group="Viewer"),
    "note": Cmd("user_note", call="text", reply="text", dead=True, logged=False, messages=False,
                usage="note TEXT | note !TEXT | note ?TEXT", help="the user's commentary (!: for the Navigator)",
                group="Notes"),
    "journal": Cmd("cmd_journal", dead=True, usage="journal TEXT", help="a line in navigator.md", group="Notes"),
    "gate": Cmd("cmd_gate", dead=True, usage="gate FEET [recall]", help="the supply gate for going down to FEET",
                group="Info"),
    "complain": Cmd("cmd_complain", dead=True, usage="complain TEXT",
                    help="what you lacked or what got in your way (runs/complaints.md)", group="Notes"),
    "say": Cmd("cmd_say", dead=True, messages=False, usage="say TEXT", help="answer the user", group="Notes"),
    "ask": Cmd("ask_architect", call="text", dead=True, usage="ask [quiet] TEXT",
               help="a live question for the Architect (rate-limited)", group="Notes"),
    "answer": Cmd("answer_navigator", roles=ARCH, refusal="answers come from the Architect", dead=True,
                  usage="answer ID TEXT", help="the Architect's answer to `ask`", group="Notes"),
    "price": Cmd("price_info", call="text", reply="text", dead=True, usage="price NAME|LETTER",
                 help="the Pilot's valuation of an item", group="Info"),
    "monster": Cmd("monster_info", call="name", reply="text", dead=True, usage="monster NAME",
                   help="monster data, danger and the hunt check's verdict", group="Info"),
    "drainers": Cmd("drainers_info", reply="text", dead=True, usage="drainers [STAT] [MAXLEVEL]",
                    help="monsters whose blows drain a stat", group="Info"),
    "gear": Cmd("gear_review", call="none", reply="text", dead=True, usage="gear", help="the gear review",
                group="Info"),
    "gearcmp": Cmd("cmd_gearcmp", dead=True, usage="gearcmp [LETTER|NAME ...]", help="the slot evaluator",
                   group="Info"),
    "house": Cmd("house_info", dead=True, usage="house [buy [Y,X] | deposit [KEEP] | withdraw [ITEM]]",
                 help="the house and what is stored (house, tavern room); buy is the Architect's", group="Town"),
    "store": Cmd("cmd_store", dead=True, usage="store [add NAME | del NAME]",
                 help="the store list: items plan town stores in the house (add/del: the Architect's)",
                 subs={"add": {"roles": ARCH, "refusal": "the store list is the Architect's (and the user's): `ask` "
                                                         "to have an item stored", "dead": True},
                       "del": {"roles": ARCH, "refusal": "the store list is the Architect's (and the user's): `ask` "
                                                         "to have an item stored", "dead": True}},
                 group="Orders"),
    "loadout": Cmd("cmd_loadout", dead=True, usage="loadout [shops]", help="the loadout optimizer", group="Info"),
    "why": Cmd("why_info", reply="text", dead=True, usage="why [HH:MM[:SS]]",
               help="what the Pilot saw and did around a moment", group="Info"),
    "prep": Cmd("prep_info", call="none", reply="text", dead=True, usage="prep",
                help="the mission-start planning report", group="Info"),
    # --- refused for a ghost (except attention, quit and goal resurrect) ---
    "goal": Cmd("request_goal", usage="goal NAME [ARGS]",
                help="dive explore fetch leave hunt recall rest wait quiet search searchroom shop town townfarm "
                     "resurrect (goto: the Architect's)",
                subs={"goto": {"roles": ARCH, "refusal": PILOTS_NOW}, "resurrect": {"dead": True}},
                group="Goals and plans"),
    "plan": Cmd("request_plan", subs={"stop": {"dead": True}}, usage="plan [trip LO-HI ... | town ... | stop | resume]",
                help="a whole trip or town visit", group="Goals and plans"),
    "stop": Cmd("cmd_stop", call="none", dead=True, usage="stop", help="drop the goal, stop resting, end the plan",
                group="Goals and plans"),
    "order": Cmd("cmd_order", dead=True, usage="order KEY=VALUE ...", help="set standing orders", group="Orders"),
    "wear": Cmd(**_ITEM, where="town", usage="wear L [force]", help="wear"),
    "takeoff": Cmd(**_ITEM, where="town", usage="takeoff L", help="take off"),
    "quaff": Cmd(**_ITEM, usage="quaff L", help="drink"),
    "read": Cmd(**_ITEM, where="town_target", usage="read L [TARGET|force]", help="read (TARGET: town only)"),
    "eat": Cmd(**_ITEM, where="town", usage="eat L", help="eat"),
    "fuel": Cmd(**_ITEM, where="town", usage="fuel L", help="refill the lantern"),
    "destroy": Cmd(**_ITEM, usage="destroy [!]L [N|all]", help="destroy (value refusal unless !)"),
    "drop": Cmd(**_ITEM, usage="drop [!]L [N|all]", help="drop (value refusal unless !)"),
    "inspect": Cmd(**_ITEM, usage="inspect L", help="the game's description"),
    "aim": Cmd(**_ITEM, usage="aim L [DIR]", help="aim a wand"),
    "use": Cmd(**_ITEM, where="town_target", usage="use L [TARGET]", help="use a staff (TARGET: town only)"),
    "zap": Cmd(**_ITEM, usage="zap L", help="zap a rod"),
    "wearall": Cmd("cmd_wearall", call="none", where="town", usage="wearall",
                   help="put on everything that fills an empty slot", group="Items"),
    "inscribe": Cmd("cmd_inscribe", where="town", usage="inscribe L TEXT", help="inscribe", group="Items"),
    "search": Cmd("cmd_search", usage="search [N]", help="search the 8 adjacent squares N times", group="Control"),
    "disarm": Cmd("cmd_disarm_open", call="cmd", usage="disarm [DIR]", help="disarm a chest, trap or door",
                  group="Control"),
    "open": Cmd("cmd_disarm_open", call="cmd", usage="open [DIR]", help="open a chest or door", group="Control"),
    "pickup": Cmd("cmd_pickup", call="none", where="town", usage="pickup", help="pick up what's underfoot",
                  group="Items"),
    "stairs": Cmd("cmd_stairs", roles=ARCH, refusal=PILOTS_NOW, usage="stairs [<|>]", help="take the stairs",
                  group="Control"),
    "option": Cmd("cmd_option", roles=ARCH, refusal=CONTROL, usage="option NAME VALUE", help="set a client option", group="Control"),
    "goalstate": Cmd("cmd_goalstate", call="none", logged=False, viewer=True, usage="goalstate",
                     help="debug JSON: the goal and the mover", group="Viewer"),
    "options": Cmd("cmd_options", usage="options [FILTER ...]", help="the client's options", group="Control"),
    "dump": Cmd("cmd_dump", roles=ARCH, refusal=CONTROL, call="none", usage="dump", help="write world_dump.json", group="Control"),
    "raw": Cmd("cmd_raw", roles=ARCH, refusal=PILOTS_NOW, usage="raw TEXT", help="a raw tool-client command",
               group="Control"),
    "attention": Cmd("cmd_attention", call="none", dead=True, usage="attention",
                     help="the pending attention events (cleared)", group="Info"),
    "quit": Cmd("cmd_quit", roles=ARCH, refusal=CONTROL, call="none", dead=True, usage="quit", help="stop the Pilot's main loop", group="Control"),
    "park": Cmd("cmd_park", call="none", roles=ARCH, refusal=CONTROL, dead=True, usage="park", help="log out when safe, for an update", group="Control"),
}

# (tuples, as handle_requests and authenticate always tested them)
POLLS = tuple(n for n, s in COMMANDS.items() if not s.logged)          # not nav_cmd, not agent activity
READ_ONLY = tuple(n for n, s in COMMANDS.items() if s.viewer)          # a bad architect claim isn't reported
NO_MESSAGES = tuple(n for n, s in COMMANDS.items() if not s.messages)  # no USER MESSAGE line added
DUNGEON_ITEM_CMDS = {n for n, s in COMMANDS.items() if s.where == "town"}
# pilotctl's own commands (they never reach the Pilot's table)
LOCAL = {"wait": ("wait [SECS] [--brief]", "block until an attention event, then the wait report", "Info"),
         "rule": ("rule KIND ...", "the Advisor's rulebook (no Pilot needed)", "Info")}


def who(s):
    return "the Architect" if s.roles == ARCH else "all"


def help_text(width=118):
    """pilotctl's help: every command by group, with its usage, who may use it and a few words."""
    out = []
    rows = [(s.group, s.usage, s.help + ("" if s.roles == ANY else f" [{who(s)} only]")
             + (" [town only for the Navigator]" if s.where == "town" else ""))
            for s in COMMANDS.values()] + [(g, u, h) for u, h, g in LOCAL.values()]
    for g in GROUPS:
        out.append(f"{g}:")
        for _, u, h in [r for r in rows if r[0] == g]:
            if len(u) > 34:                       # (a long usage gets a line of its own)
                out.append(textwrap.fill(u, width, initial_indent="  ", subsequent_indent="    "))
                u = ""
            out.append(textwrap.fill(f"{u:34s} {h}", width, initial_indent="  ", subsequent_indent=" " * 37))
    return "\n".join(out)
