#!/usr/bin/env python3
"""newchar -- create a throwaway character and put on its starting kit.

Writes the character's private files (a random password and a client config)
to --privdir, logs in with `--birth` so the client creates the character if it
doesn't exist (or is dead), wields the starting weapon and light, wears the
armour, and prints a summary (race, class, stats, HP, blows).

    python3 newchar.py --nick Dive02 --host localhost --port 28346

Default build (the user's recommendation for a throwaway warrior): Half-Orc
Warrior, stats in the order DEX > STR > CON > WIS > CHR > INT. It then wants a
light weapon for more blows, bought in town (not done here).

Careful: --birth replaces a *dead* character of the same name with a new one.
"""
import argparse
import json
import os
import secrets
import sys
import time

from mang import MangClient, ClientExited

DEFAULT_BIRTH = "Half-Orc:Warrior:m:DEX,STR,CON,WIS,CHR,INT"

TV_BOW, TV_DIGGING, TV_SWORD, TV_LITE = 19, 20, 23, 39
TV_ARMOUR = range(30, 39)       # boots .. dragon scale mail
WEAPONS = range(TV_DIGGING + 1, TV_SWORD + 1)   # hafted, polearm, sword

# status indicator stat0..5 order (server stat_names)
STATS = ["STR", "INT", "WIS", "DEX", "CON", "CHR"]


def stat_text(v):
    """Indicator value -> the game's notation (18/xx above 18)."""
    return str(v) if v <= 18 else f"18/{v - 18:02d}" if v < 118 else f"18/{v - 18}"


def private_files(privdir, nick):
    """(passfile, config) for nick, creating them (mode 600) if needed."""
    os.makedirs(privdir, mode=0o700, exist_ok=True)
    base = os.path.join(privdir, nick.lower())
    passfile, config = base + ".pass", base + ".mangrc"
    old = os.umask(0o077)
    try:
        if not os.path.exists(passfile):
            with open(passfile, "w") as f:
                # The client's password prompt takes at most 15 characters
                f.write(secrets.token_urlsafe(9)[:12] + "\n")
        if not os.path.exists(config):
            here = os.path.dirname(os.path.abspath(__file__))
            libdir = os.path.abspath(os.path.join(here, "..", "..", "lib"))
            with open(config, "w") as f:
                f.write(f"[MAngband]\nLibDir {libdir}/\n")
    finally:
        os.umask(old)
    return passfile, config


def wear_kit(c, say):
    """Wield/wear whatever the pack holds for an empty slot. Inventory
    indices shift after each change, so re-read the pack every time."""
    for _ in range(12):
        inv = c.inven()
        worn = {it["tval"] for it in inv if it["equip"]}
        pick = None
        for it in inv:
            if it["equip"]:
                continue
            tv = it["tval"]
            if tv in WEAPONS and not worn & set(WEAPONS):
                pick = it
            elif tv == TV_LITE and TV_LITE not in worn:
                pick = it
            elif tv in TV_ARMOUR and tv not in worn:
                pick = it
            if pick:
                break
        if not pick:
            return
        say(f"  wearing {pick['name']}")
        c.send(f"custom w item={pick['item']}")
        c.collect(1.0)


def summary(c):
    st = c.status()
    ind = st["ind"]
    return {
        "nick": ind.get("hist_name_"), "race": ind.get("race_"), "class": ind.get("class_"),
        "level": ind["level"][0], "hp": ind["hp"], "gold": ind["gold"][0],
        "stats": {s: stat_text(ind[f"stat{i}"][0]) for i, s in enumerate(STATS)},
        "blows": ind.get("skills2", [None])[0], "to_hit_dam": ind.get("plusses"),
        "depth": ind["depth"][0], "pos": [st["y"], st["x"]],
        "equipment": [it["name"] for it in c.inven() if it["equip"]],
        "pack": [it["name"] for it in c.inven() if not it["equip"]],
    }


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "..", ".."))
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--nick", required=True)
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=18346)
    ap.add_argument("--birth", default=DEFAULT_BIRTH, help="RACE:CLASS:SEX:STAT,... (default: %(default)s)")
    ap.add_argument("--privdir", default=os.path.join(repo, "..", "runs", "private"),
                    help="where the password and config files live")
    ap.add_argument("--client", default=os.path.join(repo, "mangclient"))
    ap.add_argument("--libdir", default=os.path.join(repo, "lib"))
    ap.add_argument("--no-wear", action="store_true", help="don't put on the starting kit")
    args = ap.parse_args()

    say = lambda *a: print(*a, file=sys.stderr, flush=True)
    passfile, config = private_files(os.path.abspath(args.privdir), args.nick)
    c = MangClient(args.client, args.libdir, args.nick, passfile, args.host, args.port,
                   config=config, cwd=repo, birth=args.birth)
    try:
        c.wait_ready(timeout=30, settle=2.0)
        if not args.no_wear:
            wear_kit(c, say)
            c.collect(1.0)       # let the indicators (blows etc.) catch up
        print(json.dumps(summary(c), indent=1))
    except ClientExited as e:
        say(f"client exited: {e}")
        sys.exit(1)
    finally:
        c.quit()
    say(f"password file: {passfile}\nconfig: {config}")


if __name__ == "__main__":
    main()
