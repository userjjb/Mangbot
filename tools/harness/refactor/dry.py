"""Dry start: the real Pilot.__init__ on a fake client, with an empty rundir and with a copy of Dive04's state files;
dump the instance's __dict__ (keys and normalised values). python3 dry.py PILOT_DIR OUT.json"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake  # noqa: E402

pilot_dir, out = os.path.abspath(sys.argv[1]), sys.argv[2]
P = fake.load(pilot_dir)
TREE = os.path.dirname(os.path.dirname(pilot_dir))


def norm(v):
    s = repr(v)
    s = re.sub(r" at 0x[0-9a-f]+", " at 0x?", s)
    s = re.sub(r"<(\w+) object>", r"<\1>", s)
    return s.replace(TREE, "<TREE>")


res = {}
for label, template in (("empty", False), ("dive04", True)):
    rundir = fake.fresh_rundir(os.path.join(fake.S, "dryrun", "runs", "pilot", "dive04"), template)
    fake.Clock.t = 1793653200.0
    c = fake.FakeClient()
    p = P.Pilot(c, rundir)
    d = {k: norm(v) for k, v in sorted(vars(p).items())}
    res[label] = {"keys": sorted(vars(p)), "values": d, "world": {k: norm(v) for k, v in sorted(vars(p.w).items())},
                  "files": sorted(os.listdir(rundir)), "sent": c.sent}
    p.dlog.close()
json.dump(res, open(out, "w"), indent=1, sort_keys=True)
print(f"{len(res['empty']['keys'])} / {len(res['dive04']['keys'])} attributes")
