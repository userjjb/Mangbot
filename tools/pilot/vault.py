"""vault -- lesser and greater vaults recognised on a partial map (2.62.0, the user: "build the vault detector"; m67 at
800 ft walked into a lesser vault -- a walled corridor of items and orcs -- with no notice).

The server's templates: lib/edit/vault.txt (N:index:name, X:type:rating:rows:columns, D: rows). Type 7 is a lesser
vault, type 8 a greater one (generate.c build_type7/8, picked for rooms of type 7 and 8 -- "very unusual" rooms, the
deeper the likelier); type 9 is never built (room_build has no case for it). build_vault (generate.c:2332) lays the
template down as written -- no rotation, no flip -- centred on (yval, xval): x = xval - width/2 + dx, y = yval -
height/2 + dy. The legend (generate.c:2373-2470 and vault.txt's own):

    ' '  not part of the vault             %   outer granite wall (corridors may break through)
    #    inner granite wall                X   permanent wall
    +    secret door                       *   an object (75%) or a trap (25%)
    ^    a trap                            .   floor
    &    a monster up to 5 levels deeper   @   a monster up to 11 levels deeper
    9    a monster 9 deeper and an object 7 deeper (good)
    8    a monster 40 deeper and an object 20 deeper (great)
    ,    a monster 3 deeper (50%) and/or an object 7 deeper (50%)
    anything else: floor.

On the client's map every wall (granite, permanent, an unfound secret door) shows '#'; floor, items, monsters, traps
and stairs are open squares. `match` scores each template at every placement whose box holds the evidence's centre
with an FFT correlation (numpy): agreeing known squares, disagreeing ones ('%' half: tunnels pierce it). A match is
confident when few known squares disagree, enough are known, and no other template or placement comes close.
"""
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT_TXT = os.path.join(HERE, "..", "..", "lib", "edit", "vault.txt")
TYPES = {"7": "lesser vault", "8": "greater vault"}
WALL_T = set("#X+")
SOFT_T = set("%")
OPEN_MAP_NOT = set("# %")           # map squares that are neither open nor walls: unknown ' '
TREASURE = set("*98,")
MONSTER = set("&@98")


def load(path=VAULT_TXT):
    """[{idx, name, type, rating, rows: [str]}] for the built types (7, 8), rows padded to the width."""
    out, cur = [], None
    for line in open(path, encoding="latin-1"):
        line = line.rstrip("\n")
        if line.startswith("N:"):
            _, idx, name = line.split(":", 2)
            cur = {"idx": int(idx), "name": name, "rows": []}
            out.append(cur)
        elif line.startswith("X:") and cur is not None:
            _, typ, rat, h, w = line.split(":")[:5]
            cur.update(type=typ, rating=int(rat), h=int(h), w=int(w))
        elif line.startswith("D:") and cur is not None:
            cur["rows"].append(line[2:])
    tmpl = []
    for v in out:
        if v.get("type") not in TYPES:
            continue
        rows = [(r + " " * v["w"])[:v["w"]] for r in v["rows"][:v["h"]]]
        rows += [" " * v["w"]] * (v["h"] - len(rows))
        v["rows"] = rows
        a = np.array([list(r) for r in rows])
        v["wall"] = np.isin(a, list(WALL_T)).astype(float)
        v["soft"] = np.isin(a, list(SOFT_T)).astype(float)
        v["open"] = ((a != " ") & ~np.isin(a, list(WALL_T | SOFT_T))).astype(float)
        v["cells"] = int((a != " ").sum())
        tmpl.append(v)
    return tmpl


_TEMPLATES = None


def templates():
    global _TEMPLATES
    if _TEMPLATES is None:
        _TEMPLATES = load()
    return _TEMPLATES


def map_arrays(memory, hgt=66, wid=198):
    """(wall, open) 0/1 arrays of the known map ({(y, x): glyph})."""
    wall = np.zeros((hgt, wid))
    op = np.zeros((hgt, wid))
    for (y, x), ch in memory.items():
        if 0 <= y < hgt and 0 <= x < wid and ch != " ":
            if ch in "#%":
                wall[y, x] = 1.0
            else:
                op[y, x] = 1.0
    return wall, op


def _corr(big, small):
    """Valid cross-correlation of `small` over `big` (FFT): out[i, j] = sum(big[i:i+h, j:j+w] * small)."""
    H, W = big.shape
    h, w = small.shape
    if h > H or w > W:
        return np.zeros((0, 0))
    fh, fw = H + h, W + w
    F = np.fft.rfft2(big, (fh, fw)) * np.fft.rfft2(small[::-1, ::-1], (fh, fw))
    full = np.fft.irfft2(F, (fh, fw))
    return np.rint(full[h - 1:H, w - 1:W] * 4) / 4


def match(memory, centre, hgt=66, wid=198, min_known=40, max_bad=0.04, margin=1.25):
    """The best confident template placement holding `centre` (y, x): {name, idx, type, kind, y0, x0, h, w, agree, bad,
    known, score, second} or None. `second`: the next best other template's agreement (uniqueness)."""
    wall, op = map_arrays(memory, hgt, wid)
    cy, cx = centre
    cands = []
    for t in templates():
        h, w = t["h"], t["w"]
        y0a, x0a = max(0, cy - h + 1), max(0, cx - w + 1)
        y1, x1 = min(hgt, cy + h), min(wid, cx + w)
        if y1 - y0a < h or x1 - x0a < w:
            continue
        mw, mo = wall[y0a:y1, x0a:x1], op[y0a:y1, x0a:x1]
        agree = _corr(mw, t["wall"]) + _corr(mo, t["open"]) + 0.5 * _corr(mw, t["soft"])
        bad = _corr(mo, t["wall"]) + _corr(mw, t["open"]) + 0.5 * _corr(mo, t["soft"])
        if agree.size == 0:
            continue
        known = agree + bad
        ok = (known >= max(min_known, 0.2 * t["cells"])) & (bad <= np.maximum(1.0, max_bad * known))
        if not ok.any():
            continue
        score = np.where(ok, agree - 4 * bad, -1e9)
        i, j = np.unravel_index(int(np.argmax(score)), score.shape)
        cands.append(dict(name=t["name"], idx=t["idx"], type=t["type"], kind=TYPES[t["type"]], y0=y0a + int(i),
                          x0=x0a + int(j), h=h, w=w, agree=float(agree[i, j]), bad=float(bad[i, j]),
                          known=float(known[i, j]), score=float(score[i, j]), rating=t["rating"], rows=t["rows"]))
    if not cands:
        return None
    cands.sort(key=lambda c: -c["score"])
    best = cands[0]
    second = cands[1]["score"] if len(cands) > 1 else 0.0
    best["second"] = second
    if second > 0 and best["score"] < margin * second:
        return None                     # (two templates fit about as well: not unique enough)
    return best


def squares(m):
    """{traps, treasure, monsters, doors, good, great}: map squares of a matched template's cells. good: '9' (an
    object made good at the depth + 7), great: '8' (made great at the depth + 20) -- generate.c build_vault."""
    out = {"traps": [], "treasure": [], "monsters": [], "doors": [], "good": [], "great": []}
    for dy, row in enumerate(m["rows"]):
        for dx, ch in enumerate(row):
            q = (m["y0"] + dy, m["x0"] + dx)
            if ch in "^*":
                out["traps"].append(q)      # ('*' is a trap one time in four)
            if ch in TREASURE:
                out["treasure"].append(q)
            if ch in MONSTER:
                out["monsters"].append(q)
            if ch == "+":
                out["doors"].append(q)
            if ch == "9":
                out["good"].append(q)
            if ch == "8":
                out["great"].append(q)
    return out


ITEM_GLYPHS = set("!?-_=\"|\\/()[]{}~,$&*")


def item_cluster(memory, min_items=3, radius=6):
    """The centre of the densest cluster of item glyphs (3+ within `radius`), and their squares, or None."""
    items = [q for q, ch in memory.items() if ch in ITEM_GLYPHS]
    best = None
    for q in items:
        near = [r for r in items if max(abs(r[0] - q[0]), abs(r[1] - q[1])) <= radius]
        if len(near) >= min_items and (best is None or len(near) > len(best[1])):
            best = (q, near)
    if not best:
        return None
    near = best[1]
    return (round(sum(r[0] for r in near) / len(near)), round(sum(r[1] for r in near) / len(near))), near


def walled(memory, squares_, pad=2):
    """The share of the box round these squares (padded) whose known border squares are walls: a compact walled area."""
    ys, xs = [q[0] for q in squares_], [q[1] for q in squares_]
    y0, y1, x0, x1 = min(ys) - pad, max(ys) + pad, min(xs) - pad, max(xs) + pad
    border = [(y, x) for y in range(y0, y1 + 1) for x in (x0, x1)] + [(y, x) for x in range(x0, x1 + 1) for y in (y0, y1)]
    known = [memory.get(q) for q in border if memory.get(q) not in (None, " ")]
    return (sum(1 for c in known if c in "#%") / len(known)) if known else 0.0
