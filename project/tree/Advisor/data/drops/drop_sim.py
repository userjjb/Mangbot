#!/usr/bin/env python3
"""Monster drops at a chokepoint: how many items are lost when the floor fills.
Model of monster_death (xtra2.c:2041-2088): per item, 20 tries; try i uses scatter distance d=(i+14)//15
(i=0: d=0 the death square; i=1-15: d=1; i=16-19: d=2); scatter (cave.c:4002) picks rand_spread(y,d),
rand_spread(x,d), rejects distance()>d when d>1 and squares without LOS; the square must be 'clean'
(FEAT_FLOOR and no object, mdefines.h:2856): one object per square, no piles. 20 failures = the item is
never created. distance() = max + min/2 (Angband). LOS approximated: corridor squares only (walls block).
Usage: drop_sim.py   (prints loss rates for 1- and 2-wide corridors, monsters dying adjacent to the player)"""
import random
def dist(a, b):
    dy, dx = abs(a[0]-b[0]), abs(a[1]-b[1]); return max(dy, dx) + min(dy, dx) // 2
def corridor(width, length=40):
    return {(y, x) for y in range(width) for x in range(-length, length)}
def drop(floor, items, at):
    for i in range(20):
        d = (i + 14) // 15
        while True:
            p = (at[0] + random.randint(-d, d), at[1] + random.randint(-d, d))
            if d > 1 and dist(at, p) > d: continue
            break
        if p in floor and p not in items:     # walls / occupied squares: the try is wasted
            items.add(p); return True
    return False
random.seed(1)
for width in (1, 2):
    print(f"\n{width}-wide corridor, player at x=0, each orc dies at x=1 (adjacent), drops placed one by one:")
    print(" items already dropped -> P(next item lost)")
    trials, N = 4000, 30
    lost_at = [0] * N
    first_loss = []
    for _ in range(trials):
        floor, items = corridor(width), set()
        fl = None
        for n in range(N):
            ok = drop(floor, items, (0, 1))
            if not ok:
                lost_at[n] += 1
                if fl is None: fl = n
        first_loss.append(fl if fl is not None else N)
    for n in (0, 2, 4, 6, 8, 10, 15, 20, 29):
        print(f"  {n:3d} -> {lost_at[n]/trials:5.0%}")
    fl = sorted(first_loss); print(f" first item lost after a median of {fl[len(fl)//2]} items (10% of fights: after {fl[len(fl)//10]})")
