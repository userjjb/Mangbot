"""setpiece -- run one of the Advisor's set-pieces live on the test server and score it.

Restructure step 4 (memos/2026-10-24-setpieces.md, its addendum A7-A9). Each run:
  1. snapshots Dive04 (charsave.sh: savefile + the Pilot's state), so it keeps nothing from the run;
  2. stages the scene with the DM (dm.py: Gandalf descends, pulls Dive04 to him, summons the cast);
  3. gives the order the scenario tests, as the Navigator would (pilotctl, Navigator role);
  4. watches Dive04's decision log for the scenario's time, then scores the pass criteria;
  5. restores Dive04 and writes runs/setpieces/<id>-<time>.json (+ a line in runs/setpieces/results.md).

    python3 setpiece.py A7 [--depth 300] [--keep]      # --keep: don't restore Dive04 afterwards
    python3 setpiece.py list

Layout (E8, 2026-11-03): this file holds the IDs (SETPIECES, TOWN) and the command line; the framework (Run, ctl,
log_since, first_seen, give_item, fresh_depth...) is setpiece_run.py, the scenarios setpiece_a.py (A),
setpiece_bcd.py (B, C, D), setpiece_l.py (L) and setpiece_mh.py (M, H). A new set-piece: a function (run) in its
group's file, imported here and added to SETPIECES.
"""
import argparse
import os

from setpiece_run import Run, fresh_depth
from setpiece_a import a1, a2, a2f, a2i, a2k, a2l, a3, a4, a5, a5s, a6, a7, a7f, a8, a8o, a8w, a9
from setpiece_bcd import b1, b2, b3, b4, b4w, b6, c3, c8, d3, d6
from setpiece_l import l1, l2, l2g, l3, l3b
from setpiece_mh import h1, h1r, m1, m2, m3, m4, m5

SETPIECES = {"M5": m5, "M4": m4, "H1": h1, "H1r": h1r, "M1": m1, "M2": m2, "M3": m3, "L3": l3, "L3b": l3b, "A2f": a2f, "L2g": l2g, "A7f": a7f, "A5": a5, "A5s": a5s, "A4": a4, "B6": b6, "B4": b4, "B4w": b4w, "D3": d3, "A2I": a2i, "A2K": a2k, "B2": b2, "B3": b3, "D6": d6, "L1": l1, "L2": l2, "A3": a3, "B1": b1, "C8": c8, "A1": a1, "A2": a2, "A2L": a2l, "A6": a6, "A7": a7, "A8": a8, "A8o": a8o, "A8w": a8w, "A9": a9,
             "C3": c3}


TOWN = {"B4", "B4w"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("sid", help="a set-piece id, e.g. A7 or H1 (`list` lists them all)")
    ap.add_argument("--depth", type=int, default=0,
                    help="default: the least recently used of 300-650 ft (town set-pieces always run in town)")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--hpwarn", type=int, default=None,
                    help="run the Pilot with --hpwarn N (default: the Pilot's, 5; 0 = no time bubble, for an A/B)")
    a = ap.parse_args()
    if a.sid == "list":
        for k, f in SETPIECES.items():
            print(k, "-", (f.__doc__ or "").strip().splitlines()[0])
        return
    depth = 0 if a.sid in TOWN else (a.depth or fresh_depth())
    if a.hpwarn is not None:
        os.environ["PILOT_ARGS"] = f"--hpwarn {a.hpwarn}"    # (charsave's save starts the Pilot with it)
    run = Run(a.sid + (f"-hw{a.hpwarn}" if a.hpwarn is not None else ""), depth, a.keep)
    try:
        run.setup()
        SETPIECES[a.sid](run)
    except Exception as e:
        run.res["error"] = repr(e)
        run.say(f"[{run.tag}] ERROR {e!r}")
    finally:
        run.teardown()
        run.finish()


if __name__ == "__main__":
    main()
