#!/usr/bin/env python3
"""redteam_band.py -- adversarial counterexample search vs PROOF_DRAFT.md section 3.

Extends the verified uniform minisim (lemma2a_check.py minisim, which reproduced
the C++ N=11 missed=4497 exactly) to the ZB-F two-band system of PROOF_DRAFT 3.1:

  job priority = (band-at-release, period, vehicle, kind), strict total order;
  band(job) = 0 iff its car is flagged at the RELEASE tick and kind != F, else 1;
  kill-and-hold, synchronous releases, m=3 cores, top-m ready jobs advance 1/tick.

Drives it with adversarial flag schedules and measures every job's response vs:
  top-band claim  (K=4, limited-t):  E<=29  B<=37  M<=38          (draft 3.2/3.5)
  base-band claim (K=4, limited-t):  E<=57  B<=162 F<=183 M<=172  (draft 3.3/3.4)

Premise accounting (the geometric membership cap, draft 3.2):
  metric-inst = max cars flagged at one instant
  metric-238  = max distinct cars flagged within any window [t-200, t+38)
                (T_max lookback + x-hat<=38: the top-band argument's real need)
  metric-400  = max distinct cars flagged within any window [t-200, t+200)
                (the draft's rounded inflation back-2600/fwd-200 in flag terms)
Classification:
  metric-400 <= 4:  draft premise satisfied -> any violation is a REFUTATION
  metric-238 <= 4:  top-band argument's own premise satisfied -> top violation
                    is a refutation of 3.2-as-argued; base is premise-sensitive
  else:             PREMISE-VIOLATING probe -> compare vs K'=metric closed tables
"""
import heapq
import random
import sys
from bisect import bisect_right

from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # tools/
import rta_solve as rs  # noqa: E402

NV = 8            # fleet size for all attack runs
M = 3             # cores
THETA = 2400      # lead-in ticks (240 ms) -- transient horizon
KINDS = [("E", 100, 11, 1), ("B", 200, 5, 2), ("F", 200, 25, 3), ("M", 200, 5, 4)]
SHORT = {"Estimator": "E", "Controller": "B", "Feedforward": "F", "Merger": "M"}


def solver_tables():
    top, base = {}, {}
    for K in range(1, NV + 1):
        tasks = rs.solve_rta(rs.build_cloud_tasks(NV, 2, top_k=K, demote_f=True),
                             M, "limited-t")
        tb, bb = {}, {}
        for t in tasks:
            d = tb if t.band == 0 else bb
            kk = SHORT[t.kind]
            d[kk] = max(d.get(kk, 0), t.R)
        top[K], base[K] = tb, bb
    return top, base


TOP_R, BASE_R = solver_tables()
CLAIM_TOP = TOP_R[4]     # E:29 B:37 M:38
CLAIM_BASE = BASE_R[4]   # E:57 B:162 F:183 M:172


def merge(iv):
    iv = sorted((a, b) for a, b in iv if b > a)
    out = []
    for a, b in iv:
        if out and a <= out[-1][1]:
            if b > out[-1][1]:
                out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return out


def max_overlap(percar_ivs):
    ev = []
    for ivs in percar_ivs:
        for a, b in ivs:
            ev.append((a, 1))
            ev.append((b, -1))
    ev.sort()
    cur = best = 0
    for _, d in ev:
        cur += d
        if cur > best:
            best = cur
    return best


def premise_metrics(merged):
    inst = max_overlap(merged)
    w238 = max_overlap([[(a - 37, b + 200) for a, b in ivs] for ivs in merged])
    w400 = max_overlap([[(a - 199, b + 200) for a, b in ivs] for ivs in merged])
    return inst, w238, w400


def bandsim(intervals, ticks, n=NV, check_bounds=True):
    """Exact tick-level two-band ZB-F replica. intervals[v] = [(on, off), ...]."""
    merged = [merge(intervals[v]) for v in range(n)]
    flag = [bytearray(ticks) for _ in range(n)]
    for v in range(n):
        for a, b in merged[v]:
            a2, b2 = max(a, 0), min(b, ticks)
            if b2 > a2:
                flag[v][a2:b2] = b"\x01" * (b2 - a2)
    starts = [[a for a, _ in merged[v]] for v in range(n)]

    tasks = [(v, kk, T, C, kr) for v in range(n) for kk, T, C, kr in KINDS]
    nt = len(tasks)
    active = [False] * nt
    rem = [0] * nt
    rel = [0] * nt
    band = [1] * nt
    prio = [None] * nt
    runq = []

    stats = {}      # (band, kind) -> (maxresp, v, reltick)
    tr_stats = {}   # transient top jobs (released < THETA after flag-on)
    st_stats = {}   # steady top jobs
    viols = []
    missed = 0
    missed_wit = []

    for t in range(ticks):
        if t % 100 == 0:
            two = (t % 200) == 0
            for i in range(nt):
                v, kk, T, C, kr = tasks[i]
                if T == 100 or two:
                    if active[i]:
                        missed += 1
                        if len(missed_wit) < 8:
                            missed_wit.append((t, "%s_%d" % (kk, v), band[i]))
                    active[i] = True
                    rem[i] = C
                    rel[i] = t
                    b = 0 if (flag[v][t] and kr != 3) else 1
                    band[i] = b
                    prio[i] = (b, T, v, kr)
            runq = sorted((i for i in range(nt) if active[i]),
                          key=lambda j: prio[j])
        served = 0
        for i in runq:
            if not active[i]:
                continue
            rem[i] -= 1
            if rem[i] == 0:
                active[i] = False
                resp = t + 1 - rel[i]
                v, kk = tasks[i][0], tasks[i][1]
                b = band[i]
                key = (b, kk)
                cur = stats.get(key)
                if cur is None or resp > cur[0]:
                    stats[key] = (resp, v, rel[i])
                if b == 0:
                    j = bisect_right(starts[v], rel[i]) - 1
                    dst = tr_stats if (j >= 0 and rel[i] - starts[v][j] < THETA) \
                        else st_stats
                    cur = dst.get(kk)
                    if cur is None or resp > cur[0]:
                        dst[kk] = (resp, v, rel[i])
                if check_bounds:
                    bound = (CLAIM_TOP if b == 0 else CLAIM_BASE).get(kk)
                    if bound is not None and resp > bound and len(viols) < 40:
                        viols.append((b, kk, v, rel[i], resp, bound))
            served += 1
            if served == M:
                break
    return dict(stats=stats, tr=tr_stats, st=st_stats, viols=viols,
                missed=missed, missed_wit=missed_wit, merged=merged)


# --------------------------------------------------------------------------- #
# Schedule generators: intervals[v] lists (may overlap; merged later).
# --------------------------------------------------------------------------- #
def sched_static(cars, ticks):
    iv = [[] for _ in range(NV)]
    for v in cars:
        iv[v].append((0, ticks))
    return iv


def sched_toggle(cars, p, ticks, ph=0):
    iv = [[] for _ in range(NV)]
    k = -2
    while k * p - ph < ticks:
        if k % 2 == 0:
            a, b = k * p - ph, (k + 1) * p - ph
            for v in cars:
                iv[v].append((max(a, 0), min(b, ticks)))
        k += 1
    return iv


def sched_pulse(cars_rot, period, width, ticks, statics=(0, 1, 2)):
    """statics always on; a rotating car from cars_rot pulses `width` ticks at
    each multiple of `period`."""
    iv = sched_static(statics, ticks)
    k = 0
    while k * period < ticks:
        v = cars_rot[k % len(cars_rot)]
        iv[v].append((k * period, min(k * period + width, ticks)))
        k += 1
    return iv


def sched_slot(D, g, ticks, statics=(0, 1, 2), rot=(3, 4, 5, 6, 7), t0=0):
    iv = sched_static(statics, ticks)
    t, k = t0, 0
    while t < ticks:
        v = rot[k % len(rot)]
        iv[v].append((t, min(t + D, ticks)))
        t += D + g
        k += 1
    return iv


def sched_full_rotate(p, ticks):
    iv = [[] for _ in range(NV)]
    for blk in range(-8, ticks // p + 9):
        vset = {(j + blk) % NV for j in range(4)}
        a, b = blk * p, (blk + 1) * p
        if b <= 0 or a >= ticks:
            continue
        for v in vset:
            iv[v].append((max(a, 0), min(b, ticks)))
    return iv


def sched_fullswap(D, g, ticks):
    """{0,1,2,3} for D, gap g, {4,5,6,7} for D, gap g, repeat."""
    iv = [[] for _ in range(NV)]
    t, k = 0, 0
    while t < ticks:
        vset = (0, 1, 2, 3) if k % 2 == 0 else (4, 5, 6, 7)
        for v in vset:
            iv[v].append((t, min(t + D, ticks)))
        t += D + g
        k += 1
    return iv


def sched_swap_once(t_s, ticks, a=(3,), b=(4,), statics=(0, 1, 2)):
    iv = sched_static(statics, ticks)
    for v in a:
        iv[v].append((0, t_s))
    for v in b:
        iv[v].append((t_s, ticks))
    return iv


def sched_entry(t0, ticks, car=3, statics=(0, 1, 2)):
    iv = sched_static(statics, ticks)
    iv[car].append((t0, ticks))
    return iv


def sched_exit(t_e, ticks, cars=(0, 1, 2, 3)):
    iv = [[] for _ in range(NV)]
    for v in cars:
        iv[v].append((0, t_e))
    return iv


def sched_rnd_legal(seed, ticks):
    rng = random.Random(seed)
    iv = [[] for _ in range(NV)]
    for _slot in range(4):
        t = rng.randrange(0, 600)
        while t < ticks:
            v = rng.randrange(NV)
            d = rng.randrange(1200, 4800)
            iv[v].append((t, min(t + d, ticks)))
            t += d + 400 + rng.randrange(0, 200)
    return iv


def sched_rnd_viol(seed, ticks):
    rng = random.Random(seed)
    iv = [[] for _ in range(NV)]
    ends = []
    t = 0
    while t < ticks:
        while ends and ends[0] <= t:
            heapq.heappop(ends)
        if len(ends) < 4 and rng.random() < 0.7:
            v = rng.randrange(NV)
            d = rng.choice([1, 5, 37, 100, 143, 200, 251, 600])
            iv[v].append((t, min(t + d, ticks)))
            heapq.heappush(ends, t + d)
        t += rng.choice([1, 3, 17, 50, 100])
    return iv


# --------------------------------------------------------------------------- #
def fmt_stats(d, keys="EBFM"):
    return " ".join("%s:%s" % (k, d[k][0] if k in d else "-")
                    for k in keys if k in d or True)


def run_one(name, intervals, ticks, results):
    r = bandsim(intervals, ticks)
    inst, w238, w400 = premise_metrics(r["merged"])
    if w400 <= 4:
        pclass = "DRAFT-PREMISE-OK"
    elif w238 <= 4:
        pclass = "TOP-PREMISE-OK"
    else:
        pclass = "PREMISE-VIOL"
    top = {k: r["stats"].get((0, k), (0,))[0] for k in "EBM"}
    base = {k: r["stats"].get((1, k), (0,))[0] for k in "EBFM"}
    top_viol = [x for x in r["viols"] if x[0] == 0]
    base_viol = [x for x in r["viols"] if x[0] == 1]
    # secondary: does the draft's counting at the *observed* K' still cover it?
    kp = min(max(w238, 1), 8)
    covered_kp = all(top[k] <= TOP_R[kp].get(k, 10**9) for k in "EBM")
    line = ("%-26s inst=%d w238=%d w400=%d %-17s missed=%-3d "
            "top E:%d/29 B:%d/37 M:%d/38  base E:%d/57 B:%d/162 F:%d/183 M:%d/172"
            % (name, inst, w238, w400, pclass, r["missed"],
               top["E"], top["B"], top["M"],
               base["E"], base["B"], base["F"], base["M"]))
    flagbits = []
    if top_viol:
        flagbits.append("TOP-VIOL")
    if base_viol:
        flagbits.append("BASE-VIOL")
    if r["missed"]:
        flagbits.append("MISSED")
    if flagbits:
        line += "   <<< " + ",".join(flagbits)
        if pclass != "PREMISE-VIOL":
            line += "  ** %s under satisfied premise **" % pclass
        line += ("  [K'=%d closed table %s]" %
                 (kp, "still covers top" if covered_kp else "ALSO EXCEEDED"))
    print(line)
    if r["viols"]:
        for b, kk, v, rl, resp, bound in r["viols"][:6]:
            print("      viol band%d %s_%d rel=%d resp=%d > bound %d"
                  % (b, kk, v, rl, resp, bound))
    if r["missed_wit"]:
        print("      missed witnesses: %s" % r["missed_wit"][:6])
    tr, st = r["tr"], r["st"]
    if tr:
        print("      transient-top max: %s   steady-top max: %s"
              % ({k: tr[k][0] for k in tr}, {k: st[k][0] for k in st}))
    results.append(dict(name=name, pclass=pclass, missed=r["missed"],
                        top=top, base=base, top_viol=top_viol,
                        base_viol=base_viol, covered_kp=covered_kp, kp=kp,
                        tr=tr, st=st))
    return r


def validate():
    print("== validation of the two-band replica ==")
    # (a) no flags at N=11 must reproduce the C++ missed=4497 (uniform system)
    iv = [[] for _ in range(11)]
    r = bandsim(iv, 300000, n=11, check_bounds=False)
    ok = r["missed"] == 4497
    print("  no-flag N=11 missed=%d (expect 4497): %s"
          % (r["missed"], "PASS" if ok else "FAIL"))
    if not ok:
        sys.exit("replica invalid")
    # (b) no flags at N=8: every response <= uniform limited-t R
    tasks = rs.solve_rta(rs.build_cloud_tasks(8, 2), M, "limited-t")
    solved = {}
    for t in tasks:
        kk = SHORT[t.kind]
        solved[kk] = max(solved.get(kk, 0), t.R)
    iv = [[] for _ in range(8)]
    r = bandsim(iv, 240000, n=8, check_bounds=False)
    obs = {k: r["stats"].get((1, k), (0,))[0] for k in "EBFM"}
    ok = all(obs[k] <= solved[k] for k in "EBFM") and r["missed"] == 0
    print("  no-flag N=8 obs %s <= uniform limited-t R %s, missed=%d: %s"
          % (obs, solved, r["missed"], "PASS" if ok else "FAIL"))
    if not ok:
        sys.exit("replica invalid")


def main():
    random.seed(0)
    validate()
    results = []
    T = 240000

    print("\n== group V: static membership (sanity + tightness) ==")
    run_one("static-0123", sched_static((0, 1, 2, 3), T), T, results)
    run_one("static-4567", sched_static((4, 5, 6, 7), T), T, results)
    run_one("static-0257", sched_static((0, 2, 5, 7), T), T, results)

    print("\n== group T: same-set toggling (premise trivially satisfied) ==")
    for p in (1, 2, 5, 10, 20, 25, 50, 100, 137, 200):
        run_one("toggle-p%d" % p, sched_toggle((0, 1, 2, 3), p, T), T, results)
    for (p, ph) in ((100, 1), (100, 99), (200, 1), (200, 199), (25, 13)):
        run_one("toggle-p%d-ph%d" % (p, ph),
                sched_toggle((0, 1, 2, 3), p, T, ph=ph), T, results)
    # single car toggles at E boundary, 3 statics
    ivx = sched_static((0, 1, 2), T)
    ivx[3] = sched_toggle((3,), 100, T)[3]
    run_one("statics+car3-toggle100", ivx, T, results)

    print("\n== group H: slot handoffs car3->4->..., 3 statics ==")
    for g in (400, 300, 240, 238, 237, 236, 200, 100, 37, 1, 0):
        run_one("slot-D2400-g%d" % g, sched_slot(2400, g, T), T, results)
    for D in (200, 100):
        run_one("slot-D%d-g0" % D, sched_slot(D, 0, T), T, results)
    run_one("slot-D2400-g240-t0=137", sched_slot(2400, 240, T, t0=137), T, results)
    run_one("slot-D2401-g239-odd", sched_slot(2401, 239, T, t0=1), T, results)
    # car flagged for exactly one release
    run_one("pulse-1tick-at-200s", sched_pulse((3, 4, 5, 6, 7), 200, 1, T), T, results)
    run_one("pulse-1tick-at-100s", sched_pulse((3, 4, 5, 6, 7), 100, 1, T), T, results)
    run_one("pulse-40tick-at-400s", sched_pulse((3, 4, 5, 6, 7), 400, 40, T), T, results)

    print("\n== group F: full-set swaps {0123}<->{4567} ==")
    for g in (400, 240, 238, 200, 100, 0):
        run_one("fullswap-D2400-g%d" % g, sched_fullswap(2400, g, T), T, results)
    for p in (2000, 1000, 400, 200, 100, 50, 25, 10, 5, 1):
        run_one("rotate-all-p%d" % p, sched_full_rotate(p, T), T, results)

    print("\n== group S: single swap events (K+1 distinct in 200 ticks) ==")
    for ts in (100000, 100001, 100037, 100100, 100199):
        run_one("swaponce-3to4-t%d" % ts, sched_swap_once(ts, T), T, results)
    run_one("swaponce-full-t100000",
            sched_swap_once(100000, T, a=(3,), b=(4,), statics=(0, 1, 2)), T, results)
    run_one("swaponce-0123to4567-t100100",
            sched_swap_once(100100, T, a=(0, 1, 2, 3), b=(4, 5, 6, 7),
                            statics=()), T, results)

    print("\n== group E: entries/exits (premise satisfied; transient attack) ==")
    for t0 in (100000, 100001, 100099, 100137, 100199):
        run_one("entry-car3-t%d" % t0, sched_entry(t0, T), T, results)
    iv = [[] for _ in range(NV)]
    for v in range(4):
        iv[v].append((100037, T))
    run_one("entry-all4-t100037", iv, T, results)
    run_one("exit-all4-t100000", sched_exit(100000, T), T, results)

    print("\n== group R: randomized schedules ==")
    for s in range(1, 13):
        run_one("rnd-legal-s%d" % s, sched_rnd_legal(s, 200000), 200000, results)
    for s in range(1, 13):
        run_one("rnd-viol-s%d" % s, sched_rnd_viol(s, 200000), 200000, results)

    # ---------------- summary ----------------
    print("\n" + "=" * 100)
    print("SUMMARY")
    refut = [r for r in results if (r["top_viol"] or r["base_viol"] or r["missed"])
             and r["pclass"] == "DRAFT-PREMISE-OK"]
    refut_top = [r for r in results if r["top_viol"]
                 and r["pclass"] == "TOP-PREMISE-OK"]
    sens = [r for r in results if (r["top_viol"] or r["base_viol"] or r["missed"])
            and r["pclass"] == "PREMISE-VIOL"]
    print("runs: %d" % len(results))
    print("REFUTATIONS (draft premise satisfied, bound broken): %d" % len(refut))
    for r in refut:
        print("   " + r["name"])
    print("TOP-premise refutations (w238<=4<w400): %d" % len(refut_top))
    for r in refut_top:
        print("   " + r["name"])
    print("premise-violating probes with excursions: %d" % len(sens))
    for r in sens:
        print("   %-24s K'=%d  top E:%d B:%d M:%d  %s" %
              (r["name"], r["kp"], r["top"]["E"], r["top"]["B"], r["top"]["M"],
               "K'-closed-table covers" if r["covered_kp"] else
               "EXCEEDS K'-closed table too"))
    # slack: max obs/bound over premise-OK runs
    worst = {}
    for r in results:
        if r["pclass"] == "PREMISE-VIOL":
            continue
        for k in "EBM":
            if r["top"][k]:
                q = r["top"][k] / CLAIM_TOP[k]
                if q > worst.get(("top", k), (0, ""))[0]:
                    worst[("top", k)] = (q, "%s obs %d / %d" % (r["name"], r["top"][k], CLAIM_TOP[k]))
        for k in "EBFM":
            if r["base"][k]:
                q = r["base"][k] / CLAIM_BASE[k]
                if q > worst.get(("base", k), (0, ""))[0]:
                    worst[("base", k)] = (q, "%s obs %d / %d" % (r["name"], r["base"][k], CLAIM_BASE[k]))
    print("\nmax observed/bound over premise-satisfying runs:")
    for key in sorted(worst):
        q, wit = worst[key]
        print("   %-9s %.3f  (%s)" % ("/".join(key), q, wit))


if __name__ == "__main__":
    main()
