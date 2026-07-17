#!/usr/bin/env python3
"""lemma1_check.py -- machine verification of PROOF_DRAFT.md Lemma 1 (occupancy).

Lemma 1 claim: on a circular track of `lap` ticks with binding zone Z = union of
K disjoint arcs of total length L, any point set with pairwise CIRCULAR spacing
>= s has at most  min(N, floor(L/s) + K)  points in Z.  (Tighter per-arc form:
min(N, sum_j floor((l_j - 1)/s) + K).)

Three independent checks:
  [1] The exact-optimum algorithm (anchor-greedy on arc starts, exchange
      argument) is validated against 2^|Z| BRUTE FORCE on exhaustive small
      circles -- every (lap, arcs, s) in a dense small domain.
  [2] Real route geometry (v10 / v12.5 / v15 z3 arcs, from zone_probe): for a
      spacing grid, exact optimum <= per-arc bound <= headline bound. Any
      violation is a REFUTATION of the lemma.
  [3] Instrument replication: re-implements Simulation::packZoneOffsets
      (pass 1 + pass 2) in Python from the arc geometry alone, slides the
      config over the 30 s run window, and compares the run-max Occ to the
      committed occupancy_sweep.csv. Exact agreement means the committed
      numbers are explained end-to-end by the geometry; measured > bound would
      refute Lemma 1 ONLY if the config satisfies F_spaced (pass-2 cars are
      not spacing-checked against pass-1 cars -- reported per row).

No simulator involvement; pure geometry. Exit 0 iff all checks pass.
"""
import csv
import itertools
import random
import sys
from pathlib import Path

# z3 arc structure per profile -- from zone_probe.cpp (reads the repo's own
# Trajectory.cpp zone computation; regenerate with the probe if zones change).
# Starts are TRUE (unrotated) tick indices: the probe now anchors the merged
# wrap-around arc at its real position (Finding D fix 2026-07-17). The pre-fix
# table was uniformly rotated late by each profile's wrap-run length (v10
# +147,400, v12.5 +119,400, v15 +98,600); rotation is an isometry of the
# occupancy problem, so every check below is unchanged by the correction.
PROFILES = {  # name -> (lap_ticks, [(arc_start, arc_len), ...])
    "v10":   (1178000, [(760800, 32000), (797800, 32200),
                        (922200, 19400), (1008800, 21800)]),
    "v12.5": (944000,  [(608400, 26000), (638200, 26100),
                        (737600, 16000), (806800, 17800)]),
    "v15":   (786000,  [(506700, 47200), (614400, 13600),
                        (672200, 15200)]),
}
N_FLEET = 18
RUN_TICKS = 300000          # 30 s at 0.1 ms -- occupancy_sweep.py duration

fails = []


def check(label, ok, detail=""):
    print("  %s  %s%s" % ("PASS" if ok else "FAIL", label,
                          ("  [" + detail + "]") if detail else ""))
    if not ok:
        fails.append(label + " " + detail)


# --------------------------------------------------------------------------- #
# The bounds under test
# --------------------------------------------------------------------------- #
def bound_headline(arcs, s, n):
    L = sum(l for _, l in arcs)
    return min(n, L // s + len(arcs))


def bound_perarc(arcs, s, n):
    return min(n, sum((l - 1) // s + 1 for _, l in arcs))


# --------------------------------------------------------------------------- #
# Exact optimum: max points in Z, pairwise circular spacing >= s.
# Exchange argument: some optimal solution has a point on an arc start (slide
# every point maximally counterclockwise; the head of a >s gap lands on an arc
# start). Anchoring there, greedy earliest-next placement is optimal on the
# unrolled line; the wrap constraint is (anchor + lap - last) >= s.
# Validated against brute force in check [1].
#
# WRAPPED ARCS (council formal-audit finding): arcs may wrap the lap boundary
# (e.g. the theta-inflated v10 arc 4). Rotation is an isometry of the problem,
# so all inputs are first rotated so that no arc wraps; the greedy scan then
# runs inside its validated domain. brute_max_occ handles wraps natively
# (zone ticks taken mod lap).
# --------------------------------------------------------------------------- #
def rotate_nonwrapping(arcs, lap):
    """Rotate all arcs by a common shift so none wraps [0, lap). Arcs are
    disjoint on the circle with total length <= lap, so some arc end has a gap
    (or another arc's start) after it; shifting coordinates to start there
    unwraps everything. Returns normalized, sorted arcs."""
    assert all(1 <= l <= lap for _, l in arcs)
    for a0, l0 in arcs:
        shift = (a0 + l0) % lap  # candidate origin: just past this arc's end
        rot = sorted(((a - shift) % lap, l) for a, l in arcs)
        if all(a + l <= lap for a, l in rot):
            ok = all(rot[i][0] + rot[i][1] <= rot[i + 1][0]
                     for i in range(len(rot) - 1))
            if ok:
                return rot
    raise AssertionError("arcs not disjoint on the circle: %r" % (arcs,))



def _next_zone_tick(arcs_sorted, lap, x):
    """Smallest zone tick >= x within [0, 2*lap) treating arcs periodically."""
    base = (x // lap) * lap
    for off in (base, base + lap):
        for a, l in arcs_sorted:
            lo, hi = a + off, a + off + l  # [lo, hi)
            if x < lo:
                return lo
            if lo <= x < hi:
                return x
    return None


def exact_max_occ(arcs, lap, s, n_cap):
    if s <= 0:
        return min(n_cap, sum(l for _, l in arcs) and n_cap)
    arcs_sorted = rotate_nonwrapping(arcs, lap)
    best = 0
    for a0, _ in arcs_sorted:
        cnt, p = 1, a0
        while True:
            q = _next_zone_tick(arcs_sorted, lap, p + s)
            if q is None or q > a0 + lap - s:   # wrap: keep >= s to the anchor
                break
            cnt, p = cnt + 1, q
        best = max(best, cnt)
    return min(n_cap, best)


def brute_max_occ(arcs, lap, s, n_cap):
    """2^|Z| brute force (small laps only). WLOG points inside Z.
    Handles wrapped arcs natively (zone ticks taken mod lap)."""
    zone = sorted({t % lap for a, l in arcs for t in range(a, a + l)})
    best = 0
    for r in range(min(len(zone), n_cap), 0, -1):
        if r <= best:
            break
        for combo in itertools.combinations(zone, r):
            ok = True
            for i in range(len(combo)):
                for j in range(i + 1, len(combo)):
                    d = abs(combo[i] - combo[j])
                    if min(d, lap - d) < s:
                        ok = False
                        break
                if not ok:
                    break
            if ok:
                best = r
                break
    return best


def check1_small_domain():
    print("[1] exact-optimum algorithm vs brute force (exhaustive small domain)")
    random.seed(0)
    cases = bad = 0
    # exhaustive: lap 6..13, all 1- and 2-arc layouts, all spacings
    for lap in range(6, 14):
        layouts = []
        for a1 in range(lap):
            for l1 in range(1, lap + 1):  # includes WRAPPED arcs (a1 + l1 > lap)
                layouts.append([(a1, l1)])
        for _ in range(60):  # sampled 2- and 3-arc layouts per lap
            k = random.choice([2, 3])
            pts = sorted(random.sample(range(lap), 2 * k))
            arcs = []
            okl = True
            for i in range(k):
                a, b = pts[2 * i], pts[2 * i + 1]
                if b - a < 1:
                    okl = False
                arcs.append((a, b - a if b > a else 1))
            # ensure disjoint non-touching (runs must be maximal/separated)
            if not okl or any(arcs[i][0] + arcs[i][1] >= arcs[i + 1][0]
                              for i in range(k - 1)):
                continue
            if arcs[-1][0] + arcs[-1][1] >= lap and arcs[0][0] == 0:
                continue  # would wrap-touch the first arc
            layouts.append(arcs)
            # rotated copy: exercises WRAPPED multi-arc inputs (isometry)
            delta = random.randrange(1, lap)
            layouts.append([((a + delta) % lap, l) for a, l in arcs])
        for arcs in layouts:
            for s in range(1, lap + 1):
                cases += 1
                got = exact_max_occ(arcs, lap, s, n_cap=99)
                want = brute_max_occ(arcs, lap, s, n_cap=99)
                bh, bp = bound_headline(arcs, s, 99), bound_perarc(arcs, s, 99)
                if got != want or want > bp or want > bh or bp > bh:
                    bad += 1
                    if bad <= 5:
                        print("    MISMATCH lap=%d arcs=%s s=%d: alg=%d brute=%d "
                              "perarc=%d headline=%d" % (lap, arcs, s, got, want,
                                                         bp, bh))
    check("algorithm == brute force AND brute <= per-arc <= headline "
          "(%d cases)" % cases, bad == 0, "%d mismatches" % bad)


# --------------------------------------------------------------------------- #
def check2_real_geometry():
    print("[2] real z3 geometry: exact <= per-arc bound <= headline bound")
    for name, (lap, arcs) in PROFILES.items():
        K, L = len(arcs), sum(l for _, l in arcs)
        row = []
        ok = True
        for s_ms in (250, 500, 750, 1000, 1500, 2000, 3000, 4000, 6000, 8000):
            s = s_ms * 10
            ex = exact_max_occ(arcs, lap, s, N_FLEET)
            bp = bound_perarc(arcs, s, N_FLEET)
            bh = bound_headline(arcs, s, N_FLEET)
            row.append((s_ms, ex, bp, bh))
            if not (ex <= bp <= bh):
                ok = False
        check("%s (K=%d, L=%d, lap=%d)" % (name, K, L, lap), ok,
              " ".join("s=%d:%d<=%d<=%d" % r for r in row))


# --------------------------------------------------------------------------- #
# Instrument replication (Simulation::packZoneOffsets + run-max occupancy)
# --------------------------------------------------------------------------- #
def pack_zone_offsets(arcs, lap, spacing_ticks, n):
    spacing = max(1, spacing_ticks)
    in_zone = bytearray(lap)
    for a, l in arcs:
        for t in range(a, a + l):
            in_zone[t % lap] = 1
    offs, since = [], spacing
    for i in range(lap):                      # pass 1: zone ticks
        if len(offs) >= n:
            break
        if in_zone[i] and since >= spacing:
            offs.append(i)
            since = 0
        else:
            since += 1
    since = spacing
    if len(offs) < n:
        for i in range(lap):                  # pass 2: non-zone ticks
            if len(offs) >= n:
                break
            if not in_zone[i] and since >= spacing:
                offs.append(i)
                since = 0
            else:
                since += 1
    j = len(offs)
    while len(offs) < n:                      # degenerate overflow
        offs.append(j * lap // n)
        j += 1
    return offs


def runmax_occ(arcs, lap, offsets, horizon):
    diff = [0] * (horizon + 1)
    for phi in offsets:
        for a, l in arcs:
            entry = (a - phi) % lap
            for st in (entry, entry - lap):   # wrap copies intersecting horizon
                lo, hi = max(0, st), min(horizon, st + l)
                if lo < hi:
                    diff[lo] += 1
                    diff[hi] -= 1
    best = cur = 0
    for d in diff:
        cur += d
        best = max(best, cur)
    return best


def min_pairwise_gap(offsets, lap):
    ss = sorted(offsets)
    gaps = [(ss[i + 1] - ss[i]) for i in range(len(ss) - 1)]
    gaps.append(ss[0] + lap - ss[-1])
    return min(gaps)


def check3_instrument(csv_path):
    print("[3] instrument replication vs committed occupancy_sweep.csv (v10)")
    lap, arcs = PROFILES["v10"]
    rows = {}
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            if r["zone"] == "3" and r["scheduler"] == "rm":
                rows[int(r["min_spacing_ms"])] = int(r["max_occ"])
    for s_ms, measured in sorted(rows.items()):
        s = max(1, s_ms * 10)
        offs = pack_zone_offsets(arcs, lap, s, N_FLEET)
        rep = runmax_occ(arcs, lap, offs, RUN_TICKS)
        gap = min_pairwise_gap(offs, lap)
        spaced = gap >= s
        ex = exact_max_occ(arcs, lap, s, N_FLEET)
        bh = bound_headline(arcs, s, N_FLEET)
        ok_rep = (rep == measured)
        ok_bound = (measured <= bh) or not spaced
        check("s=%dms: replicated Occ=%d == csv %d" % (s_ms, rep, measured),
              ok_rep)
        check("s=%dms: csv %d <= headline %d (exact-opt %d, F_spaced %s "
              "min-gap %d)" % (s_ms, measured, bh, ex,
                               "OK" if spaced else "VIOLATED-by-instrument", gap),
              ok_bound)


def check4_inflated_coupling():
    """Lemma-2b coupling: Occ+ = exact optimum on arcs inflated by zeta =
    theta (top-band lead-in, 140 ms) + max top busy window + T_max, rounded up
    to 2000 ticks (200 ms). The composition admits (N, s) iff Occ+(s) <= the
    band-certified K* (4 under limited-t ZB-F). Prints the coupling table and
    asserts the inflated bound relations still hold."""
    print("[4] Lemma-2b coupling: inflated-arc Occ+ (back 2600, fwd 200 ticks)")
    BACK, FWD = 2600, 200   # theta(2400 = 240 ms) + busy window, rounded; T_max
    for name, (lap, arcs) in PROFILES.items():
        infl = [((a - BACK) % lap, l + BACK + FWD) for a, l in arcs]
        # Inflated arcs may WRAP the lap boundary in general (an arc near the lap
        # end, or the back-inflation of arc 0, can cross 0). In the true frame
        # (Finding D fix) none of the three profiles' arcs actually reach the lap
        # boundary, so no wrap occurs here -- but rotate_nonwrapping stays as the
        # general guard: it both validates circular disjointness and puts the
        # arcs in exact_max_occ's domain, and the Occ+ values are rotation-
        # invariant regardless of whether a given frame wraps.
        try:
            rotate_nonwrapping(infl, lap)
            disjoint = True
        except AssertionError:
            disjoint = False
        row, ok = [], disjoint
        for s_ms in (1000, 2000, 3000, 4000, 6000, 8000):
            s = s_ms * 10
            ex = exact_max_occ(infl, lap, s, N_FLEET)
            bh = bound_headline(infl, s, N_FLEET)
            row.append((s_ms, ex))
            if ex > bh:
                ok = False
        check("%s inflated arcs disjoint + Occ+ <= headline" % name, ok,
              " ".join("s=%d:Occ+=%d" % r for r in row))


if __name__ == "__main__":
    csv_arg = sys.argv[1] if len(sys.argv) > 1 else str(
        Path(__file__).resolve().parents[2] / "occupancy_sweep.csv")
    check1_small_domain()
    check2_real_geometry()
    check3_instrument(csv_arg)
    check4_inflated_coupling()
    print("\n%s: %d failure(s)" % ("ALL LEMMA-1 CHECKS PASS" if not fails
                                   else "LEMMA-1 CHECK FAILURES", len(fails)))
    for f in fails:
        print("  - " + f)
    sys.exit(1 if fails else 0)
