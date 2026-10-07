"""Regression run after the cleanup pass (see tools/shopcat)."""
import sys, time
sys.path.insert(0, "/projectnb/jbrcs/mangband/github/tools/shopcat")
from mang import MangClient
from shopcat import Cataloger
import wild

R = "/projectnb/jbrcs/mangband/runs"
repo = "/projectnb/jbrcs/mangband/github"
c = MangClient(repo + "/mangclient", repo + "/lib", "Surveyor", R + "/private/surveyor.pass",
               port=28346, config=R + "/private/surveyor.mangrc", cwd=repo)
c.wait_ready()
with open(R + "/regress.jsonl", "a") as out:
    cat = Cataloger(c, out, nogo_file=R + "/regress.jsonl.nogo.json")
    cat.upkeep()
    print("start:", wild.world_name(cat.world), c.pos, "supplies", cat.supplies(), flush=True)
    t = time.time(); cat.go_to((0, 0), wild.DEFAULT_TARGETS); print(f"home in {time.time()-t:.0f}s", flush=True)
    t = time.time(); cat.restock(); print(f"restock 1: {time.time()-t:.0f}s broke_at={cat.broke_at}", flush=True)
    t = time.time(); cat.restock(); print(f"restock 2: {time.time()-t:.1f}s (should be ~instant)", flush=True)
    print("town:", cat.run(max_doors=6, only=None), flush=True)
    print("tour 1N:", cat.tour([(0, 1)], explore_secs=300, include_start=False), flush=True)
    st = c.status(); print("end:", wild.world_name(cat.world), "hp", st["ind"]["hp"], "supplies", cat.supplies(), flush=True)
c.quit()
