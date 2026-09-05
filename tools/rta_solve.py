#!/usr/bin/env python3
"""rta_solve.py - machine-verification of BOUND.md section 7 (response-time analysis).

Independently computes the global fixed-priority RTA for the cloud task chain,
reproduces/checks the section 7.3 table, emits the Layer-1 per-vehicle data-age
bound (BOUND section 4), sweeps N for the certified capacity, and (optionally)
cross-checks both predictions against the actual simulator.

SCOPE / HONESTY: this verifies the ARITHMETIC of applying the section 7.2 formula
and cross-checks its predictions against the sim. It does NOT prove the section
7.2 formula is the correct RTA for the discrete synchronized-quantum model -- that
is Kurt's re-derivation (section 7.4 item 2). The age-soundness cross-check
partially guards soundness: an unsound (too-small-R) formula yields a bound the
sim violates, which is flagged loudly.

  --workload limited is a CANDIDATE limited-carry-in (Guan RTA-LC) workload,
  prototyped to de-risk Kurt's re-derivation -- UNVERIFIED; its soundness is
  exactly what he must prove. The cross-check is its arbiter (certified <=
  empirical, bound >= measured). Treat any "limited" number as provisional until
  he signs off. Default stays full carry-in (byte-identical to before this mode).

Model (verified against code, 2026-06-17):
  - Params:    TaskModel.cpp:38-52 challengeDefault() == examples/parameters.md
  - Priority:  RateMonotonic.cpp:26-32  (period_ms, vehicle, kind), cloud-only
  - Scheduler: PolicyScheduler.cpp:19-41  global / free-migration / fully
               preemptive / 1-tick quanta;  m = nCores = 3 (Scheduler.h:21)
  - Tick = 1e-4 s = 0.1 ms (Scheduler.h:22).  --exec worst uses WCET.
  - P1:        TaskModel.cpp:135-154  missed++ iff response time > period,
               so "missed jobs: 0"  <=>  empirical "all R <= T".

Usage:
  python3 tools/rta_solve.py                       # analysis only
  python3 tools/rta_solve.py --cross-check         # also run the simulator
  python3 tools/rta_solve.py --max-n 24 --cores 3 --exec worst
"""
import argparse
import os
import re
import subprocess
import sys

TICK_MS = 0.1  # Scheduler.h:22  baseStep = 1e-4 s

# TaskKind enum order (TaskModel.h:21) -- the tie-break rank for `kind`.
KIND_RANK = {"Sensor": 0, "Estimator": 1, "Controller": 2,
             "Feedforward": 3, "Merger": 4, "Actuator": 5}

# (period_ms, (bcet_ms, avet_ms, wcet_ms)) -- TaskModel.cpp:41-48
# SOURCE OF TRUTH: TaskSet::challengeDefault(). Re-sync if that changes.
PARAMS_MS = {
    "Sensor":      (5.0,  (0.4, 0.6, 1.0)),
    "Estimator":   (10.0, (0.7, 0.9, 1.1)),
    "Controller":  (20.0, (0.2, 0.3, 0.5)),
    "Feedforward": (20.0, (0.2, 1.2, 2.5)),
    "Merger":      (20.0, (0.2, 0.3, 0.5)),
    "Actuator":    (30.0, (0.2, 0.5, 0.7)),
}
NET_DELAY_MS = (1.0, 8.0, 16.0)  # netSC == netCA  (bcet, avet, wcet)
EXEC_IDX = {"best": 0, "avg": 1, "worst": 2}
CLOUD_KINDS = ("Estimator", "Controller", "Feedforward", "Merger")

# Causal A(zone) deadlines (ms), v10 lateral -- zone_tolerance.csv / THEOREM_BRIEF
# section 3.2. z3 (lane-change) is the binding deadline; the bound-vs-N sweep flags
# where the fleet-max age bound crosses each (so we see how much the per-zone +
# occupancy decomposition has to do). CONSERVATIVE 50 ms-grid values (fine-grid
# cliff = 170, PROOF_DRAFT section 8.1). TWIN: src/sim/Simulation.cpp kAZoneMs --
# change both in lockstep.
A_ZONE_MS = {"z3 lane-change (binding)": 140.0,
             "z0/z2 straight/sharp": 290.0,
             "z1 slight": 400.0}

# BOUND.md section 7.3 R (ticks), machine-verified & corrected 2026-06-17. The v5
# values were originally hand-iterated WRONG (B5/F5/M5 = 107/129/117); this solver
# refuted them and the doc now carries the full-carry-in solution below. Kept as a
# regression oracle against the corrected doc.
DOC_R = {("Estimator", 0): 11, ("Estimator", 5): 29,
         ("Controller", 0): 27, ("Feedforward", 0): 48, ("Merger", 0): 37,
         ("Controller", 5): 117, ("Feedforward", 5): 203, ("Merger", 5): 152}
# Subset I cross-checked BY HAND this session (ticks) -- self-validation oracle.
SELF_CHECK = {("Estimator", 0): 11, ("Estimator", 1): 14, ("Estimator", 2): 18,
              ("Estimator", 3): 22, ("Estimator", 4): 25, ("Estimator", 5): 29,
              ("Controller", 0): 27, ("Feedforward", 0): 48, ("Merger", 0): 37}
# Layer-1 per-vehicle bound oracle (ms), N=6 worst. v0 uses jitter-INACTIVE R's
# (robust across workload variants). v5's 167.2 was built on the doc's
# R_B=107/R_M=117, which this solver refutes -- so it is NOT a valid oracle.
SELF_CHECK_BOUND_MS = {0: 131.6}


def ms_to_ticks(ms):
    """Mirror TaskChainModel::msToTicks = lround(ms / dtMs)."""
    return int(round(ms / TICK_MS))


def c_ticks(kind, exec_idx):
    """WCET/BCET/AvET in ticks, with the sim's max(2,...) floor (TaskModel.cpp:100)."""
    return max(2, ms_to_ticks(PARAMS_MS[kind][1][exec_idx]))


def t_ticks(kind):
    return ms_to_ticks(PARAMS_MS[kind][0])


def delay_ticks(exec_idx):
    return max(1, ms_to_ticks(NET_DELAY_MS[exec_idx]))


def ceil_div(a, b):
    return -(-a // b)


def workload(i, x, wl_mode):
    """Higher-priority workload of task i in a window of length x (ticks).

      full: BOUND 7.2 AS WRITTEN -- full carry-in (the jitter term R_i - C_i on
            EVERY task). Sound (upper bound) but pessimistic for synchronous
            release.
      none: no carry-in, ceil(x/T_i)*C_i -- the synchronous-release form. Lower
            pessimism; used here only to DIAGNOSE the section 7.3 hand numbers.
    Limited carry-in (only m-1 tasks, Guan RTA-LC -- the section 7.2
    "refinement") lives in hp_interference() below, as a CANDIDATE (UNVERIFIED --
    Kurt's re-derivation, 7.4 item 2); its soundness is guarded by the sim
    cross-check, not proven here.
    """
    if wl_mode == "none":
        return ceil_div(x, i.T) * i.C
    return ceil_div(x + i.R - i.C, i.T) * i.C


def hp_interference(hp, x, m, wl_mode):
    """Total higher-priority interference in a window of length x ticks.

      full / none: Sum_{i in hp} workload(i, x, wl_mode)  -- unchanged.
      limited:     CANDIDATE limited carry-in (Guan RTA-LC, UNVERIFIED). Only m-1
        higher-priority tasks may carry in at the start of the busy window, so each
        task contributes its NO-carry-in workload (NC = ceil(x/T)*C, the 'none'
        form) and only the m-1 largest carry-in SURPLUSES (CI - NC, where CI = the
        'full' jitter form) are added back. Hence  none <= limited <= full  by
        construction: limited is bounded above by the already-sound full form (so
        it is sound-leaning), and tighter than it. v1 has NO per-task interference
        cap (a further Guan tightening) -- add only if the cross-check shows v1 is
        sound but loose. The NC/CI choice + the jitter<->carry-in interaction are
        the exact subtleties Kurt must verify.
      limited-t:   like limited, but the carry-in form uses jitter T - C instead
        of R - C: CI = ceil((x + T - C)/T)*C. Kill-and-hold guarantees every
        job's execution lies in [release, release + T) MECHANICALLY, so this CI
        needs no response-time induction at all -- the variant the PROOF_DRAFT
        Lemma-2b band composition uses (its interferers' R's are not statically
        knowable). Looser than 'limited' (T >= R), still tighter than 'full'
        at small x.
    """
    if wl_mode not in ("limited", "limited-t"):
        return sum(workload(i, x, wl_mode) for i in hp)
    nc_total = 0
    surplus = []
    for i in hp:
        nc = workload(i, x, "none")   # ceil(x/T)*C        -- no carry-in
        if wl_mode == "limited-t":    # ceil((x+T-C)/T)*C  -- mechanical jitter
            ci = ceil_div(x + i.T - i.C, i.T) * i.C
        else:
            ci = workload(i, x, "full")  # ceil((x+R-C)/T)*C -- carry-in/jitter
        nc_total += nc
        surplus.append(ci - nc)       # >= 0  (R >= C; T >= C)
    surplus.sort(reverse=True)
    return nc_total + sum(surplus[:max(0, m - 1)])


class Task:
    __slots__ = ("kind", "vehicle", "T", "C", "R", "band")

    def __init__(self, kind, vehicle, exec_idx, band=0):
        self.kind = kind
        self.vehicle = vehicle
        self.T = t_ticks(kind)
        self.C = c_ticks(kind, exec_idx)
        self.R = None
        self.band = band  # 0 = elevated/top (or the whole fleet), 1 = base

    def key(self):  # RateMonotonic.cpp:29-31 -> (period, vehicle, kind);
        return (self.band, self.T, self.vehicle, KIND_RANK[self.kind])

    def label(self):
        return "%s_%d" % (self.kind[0], self.vehicle)


def build_cloud_tasks(n, exec_idx, top_k=0, demote_f=False):
    """All cloud tasks for n vehicles, sorted highest-priority first. With
    top_k > 0 (the Lemma-2b band mode) vehicles 0..top_k-1 form the elevated
    band: every task of theirs outranks every base-band task (band-major
    order); top_k=0 leaves the order byte-identical to the uniform system.
    demote_f keeps elevated vehicles' Feedforward tasks in the BASE band
    (ZB-F variant): F is not on the age path (BOUND section 4 uses R_E/R_B/R_M
    only), so demoting it sheds 25 of the 46 ticks/car of top-band load; F's
    own P1 (R <= T) is still checked in the base band."""
    def band_of(kind, v):
        if top_k <= 0:
            return 0
        if v >= top_k or (demote_f and kind == "Feedforward"):
            return 1
        return 0
    tasks = [Task(k, v, exec_idx, band=band_of(k, v))
             for v in range(n) for k in CLOUD_KINDS]
    tasks.sort(key=Task.key)
    return tasks


def solve_rta(tasks, m, wl_mode="full", cap=1000000):
    """Fixed-point RTA (BOUND section 7.2), solved top-down in priority order.

      R_k = iterate x:  x = C_k + ( sum_{i in hp(k)} W_i(x) ) // m
                        W_i(x) per workload() (default 'full' = section 7.2)
      stop: x unchanged (converged) | x > T_k (overrun) | cap (divergence guard)
    Returns the same list with .R filled in (ticks).
    """
    for idx, k in enumerate(tasks):
        hp = tasks[:idx]  # everything strictly higher priority
        # Own-task band carry (council referee finding, PROOF_DRAFT section 3.3):
        # in the two-band system a BASE job's same-task predecessor may be
        # top-stamped (strictly higher priority than this job) and execute
        # inside the busy window; hp excludes the own task, so charge the
        # predecessor's full C unconditionally. Top-band jobs are immune (a
        # base-stamped predecessor ranks below; a top-stamped one is killed at
        # this job's release). F never elevates, so its predecessor never
        # outranks it. Inert outside band mode (band == 1 requires top_k > 0).
        own_carry = k.C if (k.band == 1 and k.kind != "Feedforward") else 0
        x = k.C
        for _ in range(cap):
            interf = hp_interference(hp, x, m, wl_mode) + own_carry
            nx = k.C + interf // m
            if nx <= x:
                break          # fixed point -- or, for the non-monotone limited
                               # interference, a dip: any x with C + I(x)//m <= x
                               # is a sound stop (PROOF_DRAFT Lemma 2a, step S5).
                               # Monotone workloads (full/none) never dip, so
                               # this is byte-identical to `nx == x` for them.
            x = nx
            if x > k.T:
                break          # overrun: R > T, unschedulable (stop before divergence)
        k.R = x
    return tasks


def layer1_bound_ticks(R_E, R_B, R_M, exec_idx):
    """BOUND.md section 4 theorem, in ticks. R_S=C_S, R_A=C_A (in-vehicle)."""
    C_S, T_S = c_ticks("Sensor", exec_idx), t_ticks("Sensor")
    C_E, T_E = c_ticks("Estimator", exec_idx), t_ticks("Estimator")
    C_B, T_B = c_ticks("Controller", exec_idx), t_ticks("Controller")
    C_M, T_M = c_ticks("Merger", exec_idx), t_ticks("Merger")
    C_A, T_A = c_ticks("Actuator", exec_idx), t_ticks("Actuator")
    d = delay_ticks(exec_idx)
    return (C_S + d + T_S
            + R_E + (T_E + R_E - C_E)
            + R_B + (T_B + R_B - C_B)
            + R_M + (T_M + R_M - C_M) + d
            + C_A + T_A)


def per_vehicle_bounds(tasks, n, exec_idx):
    """{vehicle: (bound_ms, holdfree_ms)} from solved R's."""
    R = {(t.kind, t.vehicle): t.R for t in tasks}
    T_A = t_ticks("Actuator")
    out = {}
    for v in range(n):
        b = layer1_bound_ticks(R[("Estimator", v)], R[("Controller", v)],
                               R[("Merger", v)], exec_idx)
        out[v] = (b * TICK_MS, (b - T_A) * TICK_MS)
    return out


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def report_table(n, m, exec_idx, fails, wl_mode):
    print("=" * 72)
    print("RTA table  (N=%d, m=%d cores, exec=%s, workload=%s)"
          % (n, m, list(EXEC_IDX)[exec_idx], wl_mode))
    print("=" * 72)
    tasks = solve_rta(build_cloud_tasks(n, exec_idx), m, wl_mode)
    print("  task    hp   R(ticks)  R(ms)   T   |  doc   status")
    print("  " + "-" * 60)
    for idx, t in enumerate(tasks):
        key = (t.kind, t.vehicle)
        doc = DOC_R.get(key)
        status = ""
        if wl_mode == "limited":
            status = "(limited-CI candidate -- UNVERIFIED)"   # full-CI oracles N/A
        elif key in SELF_CHECK:
            ok = (t.R == SELF_CHECK[key])
            status = "self-verified OK" if ok else "SELF-CHECK FAIL!"
            if not ok:
                fails.append("RTA self-check %s: got %d expected %d"
                             % (t.label(), t.R, SELF_CHECK[key]))
        elif doc is not None:
            if t.R == doc:
                status = "matches doc (machine-verified)"
            else:
                status = "MISMATCH -> FINDING"
                fails.append("doc R %s: solver %d vs doc %d  (BOUND 7.3 wrong)"
                             % (t.label(), t.R, doc))
        over = "  <-- R>T OVERRUN" if t.R > t.T else ""
        docs = ("%4d" % doc) if doc is not None else "   -"
        print("  %-6s  %3d  %7d  %6.1f %4d | %s  %s%s"
              % (t.label(), idx, t.R, t.R * TICK_MS, t.T, docs, status, over))
    return tasks


def report_bounds(tasks, n, exec_idx, fails, wl_mode="full"):
    print("\nLayer-1 per-vehicle data-age bound (BOUND section 4), ms:")
    pv = per_vehicle_bounds(tasks, n, exec_idx)
    fleet = max(b for b, _ in pv.values())
    for v in range(n):
        b, hf = pv[v]
        chk = ""
        if wl_mode != "limited" and v in SELF_CHECK_BOUND_MS:
            exp = SELF_CHECK_BOUND_MS[v]
            ok = abs(b - exp) < 0.05
            chk = ("  [self-check %.1f OK]" % exp) if ok else \
                  ("  [SELF-CHECK FAIL exp %.1f]" % exp)
            if not ok:
                fails.append("Layer-1 bound v%d: got %.1f expected %.1f" % (v, b, exp))
        print("  v%-2d  age_path <= %6.1f ms   (hold-free %6.1f)%s" % (v, b, hf, chk))
    print("  fleet-max bound: %.1f ms" % fleet)
    return pv


def bound_vs_n(m, exec_idx, max_n, wl_mode):
    """Fleet-max age bound (BOUND section 4) vs N, flagging A(zone) crossovers.

    The headline of Lemma 2a: below the z3 crossover every car meets the binding
    140 ms deadline UNIFORMLY (occupancy unneeded); above it, only the <= Occ cars
    in z3 must -- so the gap between the z3 crossover and the certified capacity is
    exactly what the occupancy lemma (Lemma 1) has to earn. Past P1 (R>T) the
    section-4 bound no longer holds; rows are tagged.
    """
    print("\n" + "=" * 72)
    print("Fleet-max age bound vs N  (workload=%s)  -- A(zone) crossovers" % wl_mode)
    print("=" * 72)
    crossed = set()
    for n in range(1, max_n + 1):
        tasks = solve_rta(build_cloud_tasks(n, exec_idx), m, wl_mode)
        over = any(t.R > t.T for t in tasks)
        fleet = max(b for b, _ in per_vehicle_bounds(tasks, n, exec_idx).values())
        flags = []
        for name, a in sorted(A_ZONE_MS.items(), key=lambda kv: kv[1]):
            if fleet > a and name not in crossed:
                crossed.add(name)
                flags.append("<-- crosses A(%s)=%.0f" % (name, a))
        tag = "  [OVERRUN R>T: P1 fails, bound void]" if over else ""
        print("  N=%-2d  fleet-max bound = %6.1f ms%s   %s"
              % (n, fleet, tag, " ".join(flags)))


def certified_capacity(m, exec_idx, max_n, wl_mode):
    """Largest N with all R<=T. Returns (cap, first_fail_N, first_overrun_label)."""
    last_ok = 0
    for n in range(1, max_n + 1):
        tasks = solve_rta(build_cloud_tasks(n, exec_idx), m, wl_mode)
        bad = [t for t in tasks if t.R > t.T]
        if bad:
            bad.sort(key=lambda t: (t.T, t.vehicle, KIND_RANK[t.kind]))
            return last_ok, n, bad[0].label()
        last_ok = n
    return last_ok, None, None


def fleet_bound(n, m, exec_idx, wl_mode, top_k=0, demote_f=False):
    """(fleet-max or top-band bound, base-band bound or None, P1 overrun?)
    for N vehicles; top_k > 0 = the Lemma-2b two-band order."""
    tasks = solve_rta(build_cloud_tasks(n, exec_idx, top_k=top_k,
                                        demote_f=demote_f), m, wl_mode)
    over = any(t.R > t.T for t in tasks)
    pv = per_vehicle_bounds(tasks, n, exec_idx)
    if top_k <= 0:
        return max(b for b, _ in pv.values()), None, over
    top = max(pv[v][0] for v in range(top_k))
    base = max((pv[v][0] for v in range(top_k, n)), default=0.0)
    return top, base, over


def uniform_capacity(a_z3_ms, m, exec_idx, wl_mode, demote_f=False, max_n=24):
    """Largest N whose UNIFORM fleet-max age bound is <= a_z3_ms with P1
    intact (every car must meet the binding budget everywhere). demote_f =
    the fleet-wide F-demotion tweak (top band = all N, ZB-F). Corollary
    helper (PAPER_NOTES 2026-09-04 (c)); 0 = not even one car certifiable."""
    cap = 0
    for n in range(1, max_n + 1):
        bound, _, over = fleet_bound(n, m, exec_idx, wl_mode,
                                     top_k=n if demote_f else 0, demote_f=demote_f)
        if over or bound > a_z3_ms:
            break
        cap = n
    return cap


def decomposition_capacity(a_z3_ms, a_base_ms, occ_plus, m, exec_idx, wl_mode,
                           max_n=24):
    """Largest N admitted by the two-band ZB-F composition (PROOF_DRAFT
    Lemma 2b): top band (occ_plus cars in the binding zone) <= a_z3_ms, base
    band <= a_base_ms (the smallest NON-binding-zone budget: a base car may be
    in any other zone), P1 for the whole system. Returns (capacity, binder)
    where binder names what stopped the sweep: 'top' (never admitted), 'base',
    'P1', or 'max_n'."""
    cap, why = 0, "top"
    for n in range(occ_plus, max_n + 1):
        top, base, over = fleet_bound(n, m, exec_idx, wl_mode,
                                      top_k=occ_plus, demote_f=True)
        if top > a_z3_ms:
            # The Occ+ top band never fits. A fleet SMALLER than Occ+ is all
            # top band (closed band = the fleet-wide F-demoted bound at that
            # N), so the composition still certifies up to min(that, Occ+ - 1)
            # (cold review 2026-09-04 (c)).
            small = uniform_capacity(a_z3_ms, m, exec_idx, wl_mode,
                                     demote_f=True, max_n=occ_plus - 1)
            return small, "top"
        if over:
            return cap, "P1"
        if base > a_base_ms:
            return cap, "base"
        cap, why = n, "max_n"
    return cap, why


def band_report(n, top_k, m, exec_idx, wl_mode, demote_f=False):
    """Lemma-2b two-band instantiation (PROOF_DRAFT.md): vehicles 0..top_k-1
    elevated (their whole cloud chain outranks every base task), the rest base.
    The composition's admission test is
        top-band  fleet-max age bound <= A(z3)      = 140 ms, and
        base-band fleet-max age bound <= A(z0/z2)   = 290 ms, and
        all R <= T (P1 for the two-band system).
    By vehicle symmetry the numbers depend only on (n, top_k), not identities.
    Default workload for this mode should be 'limited-t' (assumption-free
    jitter; see hp_interference) -- 'limited' R-jitter is reported for
    comparison but its cross-band induction is exactly what Kurt must bless."""
    print("=" * 72)
    print("Lemma-2b band mode  (N=%d, top band = %d vehicles%s, m=%d, exec=%s, "
          "workload=%s)" % (n, top_k, " minus their F's (ZB-F)" if demote_f
                            else "", m, list(EXEC_IDX)[exec_idx], wl_mode))
    print("=" * 72)
    tasks = solve_rta(build_cloud_tasks(n, exec_idx, top_k=top_k,
                                        demote_f=demote_f), m, wl_mode)
    over = [t for t in tasks if t.R > t.T]
    pv = per_vehicle_bounds(tasks, n, exec_idx)
    top = max(pv[v][0] for v in range(top_k)) if top_k else 0.0
    base = max(pv[v][0] for v in range(top_k, n)) if top_k < n else 0.0
    for v in range(n):
        print("  v%-2d %-4s  age_path <= %6.1f ms" %
              (v, "top" if v < top_k else "base", pv[v][0]))
    a_top, a_base = A_ZONE_MS["z3 lane-change (binding)"], \
        A_ZONE_MS["z0/z2 straight/sharp"]
    p1 = "P1 OK (all R<=T)" if not over else \
        "P1 FAILS (%s R=%d > T=%d)" % (over[0].label(), over[0].R, over[0].T)
    t_ok = top <= a_top and not over
    b_ok = base <= a_base and not over
    print("  top-band  fleet-max %6.1f ms vs A(z3)=%.0f    -> %s"
          % (top, a_top, "PASS" if t_ok else "FAIL"))
    print("  base-band fleet-max %6.1f ms vs A(z0/z2)=%.0f -> %s"
          % (base, a_base, "PASS" if b_ok else "FAIL"))
    print("  %s" % p1)
    print("  ADMITTED (N=%d, Occ+=%d)" % (n, top_k) if (t_ok and b_ok)
          else "  NOT ADMITTED (N=%d, Occ+=%d)" % (n, top_k))
    return t_ok and b_ok


# --------------------------------------------------------------------------- #
# Simulator cross-check
# --------------------------------------------------------------------------- #
def run_sim(cps, n, cores, exec_mode, duration):
    """Returns (missed:int|None, {vehicle: age_path_ms|None})."""
    cmd = [cps, "--headless", "--vehicles", str(n), "--scheduler", "rm",
           "--exec", exec_mode, "--cores", str(cores), "--duration", str(duration)]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=600).stdout
    mm = re.search(r"missed jobs:\s*(\d+)", out)
    missed = int(mm.group(1)) if mm else None
    ages = {}
    for line in out.splitlines():
        toks = line.split()
        # per-vehicle row: veh avg_perf max_roll soft% hard age_fresh age_path ...
        if len(toks) >= 7 and toks[0].isdigit():
            ages[int(toks[0])] = None if toks[6] == "n/a" else float(toks[6])
    return missed, ages


def cross_check(cps, cert, m, exec_mode, duration, max_sim_n, exec_idx, fails,
                wl_mode, soundness_grid=None):
    print("\n" + "=" * 72)
    print("SIMULATOR CROSS-CHECK  (./build/cps, exec=%s, %ds, workload=%s)"
          % (exec_mode, duration, wl_mode))
    print("=" * 72)

    def age_soundness(n):
        tasks = solve_rta(build_cloud_tasks(n, exec_idx), m, wl_mode)
        pv = per_vehicle_bounds(tasks, n, exec_idx)
        missed, ages = run_sim(cps, n, m, exec_mode, duration)
        print("  N=%d: missed jobs = %s" % (n, missed))
        if missed is None:
            fails.append("could not parse sim output at N=%d" % n)
            return missed
        for v in sorted(ages):
            meas = ages[v]
            if meas is None:
                print("    v%-2d measured age_path = n/a (starved)" % v)
                continue
            bnd = pv[v][0]
            if meas <= bnd + 1e-6:
                print("    v%-2d measured %6.1f <= bound %6.1f  OK" % (v, meas, bnd))
            else:
                print("    v%-2d measured %6.1f  >  bound %6.1f  *** COUNTEREXAMPLE ***"
                      % (v, meas, bnd))
                fails.append("AGE BOUND VIOLATED N=%d v%d: measured %.1f > bound %.1f"
                             % (n, v, meas, bnd))
        return missed

    # (a) RTA soundness at the certified boundary: schedulable => sim must not miss.
    print("\n[a] RTA soundness: at certified N=%d the sim must report missed=0" % cert)
    missed_cert = age_soundness(cert)
    if missed_cert not in (None, 0):
        fails.append("RTA UNSOUND: certified N=%d but sim missed %d jobs"
                     % (cert, missed_cert))
        print("    *** RTA UNSOUND: certified schedulable but sim MISSED jobs ***")

    # (b) age soundness at the documented baseline N=6 (we have ground truth there).
    if cert != 6:
        print("\n[b] age soundness at the documented baseline N=6:")
        age_soundness(6)

    # (b') widened age-soundness grid (Theorem-2 bridge validation, Guo 2a). For
    # the limited-carry-in CANDIDATE this is the empirical arbiter: at every
    # certified N the measured age_path must stay under the candidate's per-
    # vehicle bound (no counterexample = the candidate is sound-leaning across
    # the whole range, not just at the boundary). Age-vs-bound is only valid
    # where the analytic RTA certifies P1 (all R <= T); above that the bound is
    # built from truncated overrun R's and is not a valid ceiling, so only
    # schedulability (missed) is reported there. Opt-in (empty => the default
    # cross-check is byte-identical, so verify.sh's G3 is untouched).
    if soundness_grid:
        print("\n[b'] widened age-soundness grid (workload=%s): N in {%s}"
              % (wl_mode, ",".join(str(n) for n in sorted(set(soundness_grid)))))
        for n in sorted(set(soundness_grid)):
            tasks_n = solve_rta(build_cloud_tasks(n, exec_idx), m, wl_mode)
            if all(t.R <= t.T for t in tasks_n):
                age_soundness(n)                      # certified region: age check valid
            else:
                missed, _ = run_sim(cps, n, m, exec_mode, duration)
                print("    N=%-2d analytic overrun (R>T) -> bound not a valid "
                      "ceiling; sim missed = %s (schedulability only)"
                      % (n, missed))

    # (c) empirical capacity: sweep up from cert+1 to first missed>0 (empirical >= certified).
    print("\n[c] empirical capacity (first N with missed>0), sweeping up from %d:" % (cert + 1))
    empirical = cert
    found = False
    for n in range(cert + 1, max_sim_n + 1):
        missed, _ = run_sim(cps, n, m, exec_mode, duration)
        print("    N=%d: missed = %s" % (n, missed))
        if missed and missed > 0:
            empirical = n - 1
            found = True
            break
        empirical = n
    tail = "" if found else "  (no miss up to N=%d; empirical capacity >= %d)" % (max_sim_n, empirical)
    print("\n  certified capacity = %d   empirical capacity = %d   gap = %d%s"
          % (cert, empirical, empirical - cert, tail))
    if empirical < cert:
        fails.append("RTA UNSOUND: empirical capacity %d < certified %d" % (empirical, cert))


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cores", type=int, default=3)
    ap.add_argument("--exec", choices=list(EXEC_IDX), default="worst")
    ap.add_argument("--workload", choices=["full", "none", "limited", "limited-t"],
                    default="full",
                    help="full = BOUND 7.2 as written (carry-in, default); none = no "
                         "carry-in (diagnostic); limited = Guan RTA-LC m-1 carry-in "
                         "(CANDIDATE, UNVERIFIED -- soundness guarded by --cross-check); "
                         "limited-t = m-1 carry-in with mechanical T-jitter (no "
                         "response-time induction; the Lemma-2b band-mode workload)")
    ap.add_argument("--band", type=int, default=0, metavar="K",
                    help="Lemma-2b two-band mode: elevate vehicles 0..K-1 (the Occ+ "
                         "in-binding-zone cars) above the rest, print both bands' "
                         "age bounds vs A(zone), and exit (PROOF_DRAFT.md)")
    ap.add_argument("--band-n", type=int, default=18, metavar="N",
                    help="fleet size for --band mode (default 18)")
    ap.add_argument("--band-demote-f", action="store_true",
                    help="ZB-F variant: keep elevated vehicles' Feedforward "
                         "tasks in the base band (F is off the age path)")
    ap.add_argument("--max-n", type=int, default=24, help="analytic capacity sweep ceiling")
    ap.add_argument("--cross-check", action="store_true", help="also run ./build/cps")
    ap.add_argument("--max-sim-n", type=int, default=18, help="cross-check capacity sweep ceiling")
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--cps", default="./build/cps")
    ap.add_argument("--a-z3", type=float, default=None, metavar="MS",
                    help="override the binding-zone budget A(z3) used by the "
                         "band verdicts and crossover flags (default: the module "
                         "constant 140 -- the conservative packet value; G3 "
                         "byte-identical). Min-over-phase values of record: "
                         "150.5 (v10) / 140.5 (v12.5) / 110.5 (v15)")
    ap.add_argument("--a-base", type=float, default=None, metavar="MS",
                    help="override the base-band budget (smallest non-z3 A(zone); "
                         "default 290). Of record: 290.5 (v10) / 190.5 (v12.5) / "
                         "140.5 (v15)")
    ap.add_argument("--soundness-grid", default="", metavar="N1,N2,...",
                    help="cross-check: also verify measured age <= per-vehicle "
                         "bound at these N (Theorem-2 bridge validation for the "
                         "limited candidate). Empty (default) => G3-identical.")
    args = ap.parse_args()
    if args.a_z3 is not None:
        A_ZONE_MS["z3 lane-change (binding)"] = args.a_z3
    if args.a_base is not None:
        A_ZONE_MS["z0/z2 straight/sharp"] = args.a_base

    m = args.cores
    exec_idx = EXEC_IDX[args.exec]
    wl_mode = args.workload
    fails = []

    # Lemma-2b band mode: report the two-band instantiation and exit (the
    # uniform-system oracles below do not apply to a band-elevated order).
    if args.band > 0:
        ok = band_report(args.band_n, args.band, m, exec_idx, wl_mode,
                         demote_f=args.band_demote_f)
        sys.exit(0 if ok else 1)

    # 1+2. Reproduce section 7.3 table + Layer-1 bounds at N=6.
    tasks6 = report_table(6, m, exec_idx, fails, wl_mode)
    report_bounds(tasks6, 6, exec_idx, fails, wl_mode)

    # 3. Certified-capacity sweep.
    cert, fail_n, fail_task = certified_capacity(m, exec_idx, args.max_n, wl_mode)
    print("\n" + "=" * 72)
    if fail_n is None:
        print("Certified capacity: >= %d (no overrun within --max-n=%d)" % (cert, args.max_n))
    else:
        print("Certified capacity (all R<=T): N = %d" % cert)
        print("  first overrun at N=%d, task %s (R>T)" % (fail_n, fail_task))
    print("=" * 72)

    # 3b. Fleet-max age bound vs N + A(zone) crossovers (the Lemma-2a headline).
    bound_vs_n(m, exec_idx, min(args.max_n, 14), wl_mode)

    # 4. Simulator cross-check.
    if args.cross_check:
        if not os.path.exists(args.cps):
            print("\n[cross-check skipped: %s not found; build first]" % args.cps)
            fails.append("cross-check requested but %s missing" % args.cps)
        else:
            cc_cert = cert if cert > 0 else 1
            grid = [int(x) for x in args.soundness_grid.split(",") if x.strip()]
            cross_check(args.cps, cc_cert, m, args.exec, args.duration,
                        args.max_sim_n, exec_idx, fails, wl_mode,
                        soundness_grid=grid)

    # Final verdict.
    print("\n" + "=" * 72)
    if fails:
        print("RESULT: %d issue(s) -- REVIEW:" % len(fails))
        for f in fails:
            print("  - " + f)
        sys.exit(1)
    print("RESULT: all checks passed.")
    print("=" * 72)


if __name__ == "__main__":
    main()
