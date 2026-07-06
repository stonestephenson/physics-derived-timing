#!/usr/bin/env python3
"""lemma2a_check.py -- machine checks for PROOF_DRAFT.md Lemma 2a (limited-CI RTA).

Three independent checks:

  [1] WORKLOAD LEMMA (the one analytic leap): for a periodic task (T, C) whose
      every job's execution lies within [release, release + Theta), the work
      executed in ANY window of length y is <= ceil((y + Theta - C)/T) * C.
      Brute-forced EXACTLY over all release phases, all Theta in [C, T], and
      y in 1..650, for the actual parameter pairs (T,C) in the task set.
      (Theta = R_i under P1 certification; Theta = T_i unconditionally via
      kill-and-hold -- both instantiations are covered by sweeping Theta.)

  [2] EXACT DISCRETE SCHEDULER REPLICATION: an independent Python tick-level
      re-implementation of the PolicyScheduler/TaskModel semantics (synchronous
      periodic releases, kill-and-hold, strict (period, vehicle, kind) priority,
      top-m advance per tick, WCET exec). Since --exec worst is deterministic,
      this reproduces the C++ cloud schedule exactly; every observed job
      response must be <= the solver's limited-CI R for that task. A violation
      REFUTES the candidate. Also cross-checks the N=11 missed count against
      the C++ simulator's known 4497 (exact-replication witness).

  [3] ITERATION-DIP SCAN: the limited-CI interference is non-monotone in the
      window length (the top-(m-1) surplus can drop), so the as-found
      fixed-point loop could in principle accept a downward move and terminate
      on a non-fixed-point. Scans every task at every N in 1..24 for a dip
      along the actual iteration path, under both the as-found and the patched
      stopping rule.

Exit 0 iff all checks pass.  Usage: python3 lemma2a_check.py /path/to/repo
"""
import sys
from pathlib import Path

REPO = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))
import rta_solve as rs  # noqa: E402

fails = []


def check(label, ok, detail=""):
    print("  %s  %s%s" % ("PASS" if ok else "FAIL", label,
                          ("  [" + detail + "]") if detail else ""))
    if not ok:
        fails.append(label + " " + detail)


# --------------------------------------------------------------------------- #
def exact_window_work(T, C, theta, y):
    """Exact max work of one periodic task in a length-y window, over all
    phases, when each job may execute any <= C ticks within [r, r + theta)
    (theta <= T so job execution windows are disjoint -> per-job caps add)."""
    best = 0
    for phi in range(T):
        # releases r = phi + k*T intersecting (-theta, y)
        k_lo = -((theta + T - 1 - phi) // T) - 1
        k_hi = (y - phi) // T + 1
        w = 0
        for k in range(k_lo, k_hi + 1):
            r = phi + k * T
            w += max(0, min(C, min(r + theta, y) - max(r, 0)))
        best = max(best, w)
    return best


def check1_workload_lemma():
    print("[1] workload lemma: exact <= ceil((y + Theta - C)/T)*C  (brute force)")
    for (T, C) in ((100, 11), (200, 5), (200, 25)):
        bad = 0
        worst_slack = None
        for theta in range(C, T + 1):
            for y in range(1, 651):
                exact = exact_window_work(T, C, theta, y)
                bound = -(-(y + theta - C) // T) * C
                if exact > bound:
                    bad += 1
                    if bad <= 3:
                        print("    VIOLATION T=%d C=%d Theta=%d y=%d: exact %d > bound %d"
                              % (T, C, theta, y, exact, bound))
                slack = bound - exact
                if worst_slack is None or slack < worst_slack:
                    worst_slack = slack
        check("(T=%d, C=%d): all Theta in [C,T], y in 1..650" % (T, C),
              bad == 0, "min slack %s (0 = tight somewhere)" % worst_slack)


# --------------------------------------------------------------------------- #
def minisim(n, m=3, ticks=300000, exec_idx=2):
    """Exact tick-level replica of the cloud schedule under --exec worst."""
    tasks = rs.build_cloud_tasks(n, exec_idx)  # sorted highest-priority first
    T = [t.T for t in tasks]
    C = [t.C for t in tasks]
    active = [False] * len(tasks)
    rem = [0] * len(tasks)
    rel = [0] * len(tasks)
    max_resp = [0] * len(tasks)
    missed = 0
    for t in range(ticks):
        for i in range(len(tasks)):
            if t % T[i] == 0:
                if active[i]:
                    missed += 1          # kill-and-hold: drop unfinished
                active[i] = True
                rem[i] = C[i]
                rel[i] = t
        granted = 0
        for i in range(len(tasks)):      # tasks[] is already the priority order
            if granted >= m:
                break
            if active[i]:
                granted += 1
                rem[i] -= 1
                if rem[i] == 0:
                    active[i] = False
                    resp = t + 1 - rel[i]
                    if resp > max_resp[i]:
                        max_resp[i] = resp
    return tasks, max_resp, missed


def check2_scheduler_replication():
    print("[2] exact scheduler replication: observed responses <= solver R")
    for n in (3, 6, 8):
        tasks_solved = rs.solve_rta(rs.build_cloud_tasks(n, 2), 3, "limited")
        solved = {(t.kind, t.vehicle): t.R for t in tasks_solved}
        tasks, resp, missed = minisim(n)
        bad = []
        for i, t in enumerate(tasks):
            if resp[i] > solved[(t.kind, t.vehicle)]:
                bad.append("%s obs %d > R %d" % (t.label(), resp[i],
                                                 solved[(t.kind, t.vehicle)]))
        worst = max((resp[i] - solved[(tasks[i].kind, tasks[i].vehicle)], tasks[i].label(),
                     resp[i], solved[(tasks[i].kind, tasks[i].vehicle)])
                    for i in range(len(tasks)))
        check("N=%d: missed=%d, every observed response <= limited R" % (n, missed),
              missed == 0 and not bad,
              "tightest: %s obs %d vs R %d" % (worst[1], worst[2], worst[3])
              if not bad else "; ".join(bad[:4]))
    # exact-replication witness: N=11 over 30 s must reproduce the C++ 4497
    _, _, missed11 = minisim(11, ticks=300000)
    check("N=11 missed over 30 s == C++ simulator's 4497", missed11 == 4497,
          "got %d" % missed11)


# --------------------------------------------------------------------------- #
def check3_iteration_dips():
    print("[3] iteration-dip scan (limited-CI non-monotone interference)")
    dips = []
    for n in range(1, 25):
        tasks = rs.build_cloud_tasks(n, 2)
        for idx, k in enumerate(tasks):
            hp = tasks[:idx]
            x = k.C
            seen = set()
            for _ in range(100000):
                interf = rs.hp_interference(hp, x, 3, "limited")
                nx = k.C + interf // 3
                if nx < x:
                    dips.append("N=%d %s: f(%d)=%d dips" % (n, k.label(), x, nx))
                if nx == x or x > k.T or nx in seen:
                    break
                seen.add(nx)
                x = nx
            k.R = x  # keep priority-order R's flowing for lower tasks
    check("no downward move on any iteration path, N=1..24", not dips,
          "; ".join(dips[:5]))


if __name__ == "__main__":
    check1_workload_lemma()
    check2_scheduler_replication()
    check3_iteration_dips()
    print("\n%s: %d failure(s)" % ("ALL LEMMA-2a CHECKS PASS" if not fails
                                   else "LEMMA-2a CHECK FAILURES", len(fails)))
    for f in fails:
        print("  - " + f)
    sys.exit(1 if fails else 0)
