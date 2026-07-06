#!/usr/bin/env python3
"""reproduce.py - one-command regeneration of the scheduling result tables + CSVs.

Guo's reproducibility directive (HANDOFF.md S5 item 4): every scheduling results
table in PREDICTOR.md / PAPER_NOTES.md should regenerate from committed data by one
command. This orchestrates the headline experiments (all --exec worst), writes a
self-describing committed CSV per experiment, and prints the aggregated table so it
can be eyeballed against the docs.

  python3 tools/reproduce.py                 # run every experiment (the "reproduce
                                             #   everything" entry point)
  python3 tools/reproduce.py capacity floor  # run a subset
  python3 tools/reproduce.py --list          # names + which doc table each backs
  python3 tools/reproduce.py --quick         # small grids (fast smoke)
  python3 tools/reproduce.py --cps ./build/cps --duration 30

Each experiment deletes its CSV, runs a grid of `./build/cps ... --csv <scratch>`
invocations, tags each per-vehicle row with the swept config (plant / floor /
pred-staleness / pred-margin -- dimensions the sim's own appendCsv does NOT record),
and appends to the committed CSV. Determinism: --exec worst has no seed dependence,
so re-runs are byte-stable. `tolerance` delegates to tools/tolerance_sweep.py.

SCOPE: the scheduling figures (capacity / simultaneous-criticality / honest A/B /
the S5c aguard --floor sweep / the per-plant tolerance cliff). BOUND.md's RTA table
is verified separately by tools/rta_solve.py.
"""
import argparse
import csv
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRATCH = os.path.join(HERE, ".reproduce_scratch.csv")


# ----------------------------------------------------------------------------- core
def run_cps(cps, *, plant, scheduler, vehicles, duration, cores=3,
            tau_crit=100, floor=None, staleness=None, margin=None, u_max=None,
            timeout=1800):
    """Run one headless --exec worst sim into a fresh scratch CSV; return its rows
    (list of dicts, the appendCsv columns) each tagged with the swept config."""
    if os.path.exists(SCRATCH):
        os.remove(SCRATCH)
    cmd = [cps, "--headless", "--plant", plant, "--vehicles", str(vehicles),
           "--cores", str(cores), "--scheduler", scheduler, "--exec", "worst",
           "--duration", str(duration), "--tau-crit", str(tau_crit),
           "--csv", SCRATCH]
    if floor is not None:     cmd += ["--floor", str(floor)]
    if staleness is not None: cmd += ["--pred-staleness", str(staleness)]
    if margin is not None:    cmd += ["--pred-margin", str(margin)]
    if u_max is not None:     cmd += ["--u-max", str(u_max)]
    subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=True)
    with open(SCRATCH) as f:
        rows = list(csv.DictReader(f))
    tag = {"plant": plant}
    if floor is not None:     tag["floor_ms"] = floor
    if staleness is not None: tag["pred_staleness_ms"] = staleness
    if margin is not None:    tag["pred_margin_ms"] = margin
    for r in rows:
        r.update(tag)
    return rows


def write_csv(path, rows, lead_cols):
    """Write rows (list of dicts) with lead_cols first, then the appendCsv columns."""
    if not rows:
        return
    base = [k for k in rows[0].keys() if k not in lead_cols]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=lead_cols + base)
        w.writeheader()
        w.writerows(rows)


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def agg(rows):
    """Per-run scalars + fleet aggregates over a config's per-vehicle rows."""
    # min_ttpnr_ms = -1 is the sim's "never within horizon" sentinel (Recording.h:44,
    # rendered "-" in the summary); the fleet floor is the smallest FINITE value (the
    # closest call), or None if no car ever came within the prediction horizon.
    finite_ttpnr = [fnum(r["min_ttpnr_ms"]) for r in rows if fnum(r["min_ttpnr_ms"]) >= 0]
    return {
        "missed": int(fnum(rows[0]["missed_jobs"])),
        "hard_total": sum(int(fnum(r["hard"])) for r in rows),
        "crashed": sum(1 for r in rows if int(fnum(r["hard"])) > 0),
        "n": len(rows),
        "worst_soft": max(fnum(r["soft_pct"]) for r in rows),
        "fleet_min_ttpnr": min(finite_ttpnr) if finite_ttpnr else None,
        "max_sim_crit": int(fnum(rows[0]["max_sim_crit"])),
        "over_cores_pct": fnum(rows[0]["sim_crit_over_cores_pct"]),
    }


def grid(quick, full):
    return quick if QUICK else full


# ----------------------------------------------------------------------- experiments
def exp_capacity(cps, out_dir, dur):
    """Capacity tournament: crashed/hard vehicles vs N (PREDICTOR S5 / PAPER_NOTES /
    GENERALIZATION S3). Lateral: hard breaches + missed; cart-pole: crashed poles."""
    plans = [("lateral", ["rm", "context", "ttu", "aguard"], dur or 30,
              grid([12, 16], [10, 11, 12, 13, 14, 15, 16, 17, 18])),
             ("cartpole", ["rm", "aguard"], dur or 20,
              grid([12, 16], [10, 11, 12, 13, 14, 15, 16, 17, 18]))]
    all_rows = []
    for plant, scheds, d, ns in plans:
        cells = {}
        for s in scheds:
            for n in ns:
                rows = run_cps(cps, plant=plant, scheduler=s, vehicles=n, duration=d)
                all_rows += rows
                cells[(s, n)] = agg(rows)
        print("\n== capacity: %s (worst, %ds) ==" % (plant, d))
        print("  N    " + "".join("%-14s" % s for s in scheds))
        for n in ns:
            line = "  %-4d " % n
            for s in scheds:
                a = cells[(s, n)]
                mark = "*" if a["missed"] else ""
                line += "%-14s" % ("%d/%d hard=%d%s" % (a["crashed"], n, a["hard_total"], mark))
            print(line)
        print("    (* = missed jobs > 0; crashed = vehicles with >=1 hard breach)")
    write_csv(os.path.join(out_dir, "capacity_sweep.csv"), all_rows, ["plant"])


def exp_simcrit(cps, out_dir, dur):
    """Simultaneous criticality vs N (and tau_crit), both plants (PREDICTOR S5d)."""
    d = dur or 30
    plans = [("lateral", grid([6, 16], [6, 14, 18])),
             ("cartpole", grid([8, 16], [8, 16]))]
    scheds = ["rm", "ttu", "aguard"]
    taus = grid([100], [100, 150])
    all_rows = []
    for plant, ns in plans:
        for tau in taus:
            cells = {}
            for s in scheds:
                for n in ns:
                    rows = run_cps(cps, plant=plant, scheduler=s, vehicles=n,
                                   duration=d, tau_crit=tau)
                    all_rows += rows
                    cells[(s, n)] = agg(rows)
            print("\n== sim-crit: %s, tau_crit=%d ms (worst, %ds) ==" % (plant, tau, d))
            print("  N    " + "".join("%-18s" % s for s in scheds) + "(max | %%>cores)")
            for n in ns:
                line = "  %-4d " % n
                for s in scheds:
                    a = cells[(s, n)]
                    line += "%-18s" % ("%d | %.2f%%" % (a["max_sim_crit"], a["over_cores_pct"]))
                print(line)
    write_csv(os.path.join(out_dir, "simcrit_sweep.csv"), all_rows, ["plant"])


def exp_honest(cps, out_dir, dur):
    """Oracle-vs-honest A/B: true sim-crit vs --pred-staleness and --pred-margin
    (PREDICTOR S5e). True sim-crit (max_sim_crit) is on the ORACLE rollout."""
    d = dur or 30
    # Per-policy N matches the §5d/§5e reference points: aguard at its capacity edge
    # (N=18, where its margin is thinnest), ttu at N=14; cart-pole both at N=8.
    plans = [("lateral", [("aguard-honest", "aguard", 18), ("ttu-honest", "ttu", 14)]),
             ("cartpole", [("aguard-honest", "aguard", 8), ("ttu-honest", "ttu", 8)])]
    stale = grid([0, 16, 100], [0, 16, 100, 200])
    margins = grid([0, 60], [0, 30, 60, 100])
    all_rows = []
    for plant, scheds in plans:
        print("\n== honest A/B: %s (worst, %ds) -- true sim-crit ==" % (plant, d))
        for hon, orac, n in scheds:
            # oracle reference
            oref = agg(run_cps(cps, plant=plant, scheduler=orac, vehicles=n, duration=d))
            # staleness sweep at margin 0
            stale_cells = {}
            for ds in stale:
                rows = run_cps(cps, plant=plant, scheduler=hon, vehicles=n, duration=d,
                               staleness=ds, margin=0)
                all_rows += rows
                stale_cells[ds] = agg(rows)["max_sim_crit"]
            # margin sweep at staleness 16 (skip 0, already in stale_cells)
            marg_cells = {}
            for mg in [m for m in margins if m > 0]:
                rows = run_cps(cps, plant=plant, scheduler=hon, vehicles=n, duration=d,
                               staleness=16, margin=mg)
                all_rows += rows
                marg_cells[mg] = agg(rows)["max_sim_crit"]
            print("  %-14s N=%-2d oracle=%d | staleness %s -> %s | margin@d16 %s -> %s"
                  % (hon, n, oref["max_sim_crit"],
                     stale, [stale_cells[x] for x in stale],
                     [m for m in margins if m > 0],
                     [marg_cells[m] for m in margins if m > 0]))
    write_csv(os.path.join(out_dir, "honest_sweep.csv"), all_rows,
              ["plant", "pred_staleness_ms", "pred_margin_ms"])


def exp_floor(cps, out_dir, dur):
    """Re-derive PREDICTOR S5c: aguard --floor sweep, multi-N, POST per-vehicle-theta
    fix (3214880). Soft% / fleet-min TTPNR per (N, floor); context/ttu reference."""
    d = dur or 30
    ns = grid([14, 16], [10, 12, 14, 16, 18])
    floors = grid([0, 100, 300], [0, 60, 100, 150, 200, 300])
    all_rows = []

    def cell(a):
        if a["hard_total"]:
            return "%d breaches" % a["hard_total"]
        floor = "-" if a["fleet_min_ttpnr"] is None else "%.0f" % a["fleet_min_ttpnr"]
        return "%.1f / %s" % (a["worst_soft"], floor)

    ref = {}
    for s in ["context", "ttu"]:
        for n in ns:
            rows = run_cps(cps, plant="lateral", scheduler=s, vehicles=n, duration=d)
            # tag reference rows with floor sentinel -1 so they round-trip in the CSV
            for r in rows:
                r["floor_ms"] = -1
            all_rows += rows
            ref[(s, n)] = agg(rows)
    ag = {}
    for fl in floors:
        for n in ns:
            rows = run_cps(cps, plant="lateral", scheduler="aguard", vehicles=n,
                           duration=d, floor=fl)
            all_rows += rows
            ag[(fl, n)] = agg(rows)

    print("\n== S5c re-derived: soft%% / fleet-min TTPNR (lateral, worst, %ds) ==" % d)
    print("  N    %-16s%-16s%s" % ("context", "ttu", "  ".join("aguard@%d" % f for f in floors)))
    for n in ns:
        line = "  %-4d %-16s%-16s" % (n, cell(ref[("context", n)]), cell(ref[("ttu", n)]))
        line += "  ".join("%-12s" % cell(ag[(fl, n)]) for fl in floors)
        print(line)
    print("    (--floor is a live knob iff the aguard@* columns differ within a row)")
    write_csv(os.path.join(out_dir, "aguard_sweep.csv"), all_rows, ["plant", "floor_ms"])


def exp_tolerance(cps, out_dir, dur):
    """Per-plant age-tolerance cliff (PREDICTOR S5d / PAPER_NOTES 2026-06-18).
    Delegates to the existing tools/tolerance_sweep.py."""
    cmd = [sys.executable, os.path.join(HERE, "tolerance_sweep.py"),
           "--cps", cps, "--out", os.path.join(out_dir, "tolerance_sweep.csv"),
           "--duration", str(dur or 30)]
    if QUICK:
        cmd += ["--delays", "16,20,24,28,90,300"]
    subprocess.run(cmd, check=True)


def exp_zones(cps, out_dir, dur):
    """Causal A(zone) tables, all profiles + fine z3 grids (THEOREM_BRIEF S3.2,
    PROOF_DRAFT S0/S6; fine grids pin the z3 cliff to the 10 ms instrument
    resolution). Delegates to tools/zone_sweep.py (uses ./build/cps)."""
    base = [sys.executable, os.path.join(HERE, "zone_sweep.py"), "--force"]
    runs = [
        (["--profile", "10", "--duration", "120"], "zone_tolerance.csv"),
        (["--profile", "12.5", "--duration", "95"], "zone_tolerance_v12.5.csv"),
        (["--profile", "15", "--duration", "79"], "zone_tolerance_v15.csv"),
        (["--profile", "10", "--duration", "120", "--zones", "3",
          "--min-extra", "50", "--max-extra", "100", "--step", "5"],
         "zone_tolerance_z3_fine.csv"),
        (["--profile", "12.5", "--duration", "95", "--zones", "3",
          "--min-extra", "50", "--max-extra", "100", "--step", "10"],
         "zone_tolerance_z3_fine_v12.5.csv"),
    ]
    if QUICK:
        runs = [(["--profile", "10", "--duration", "30", "--zones", "3",
                  "--max-extra", "100", "--step", "50"], "zone_tolerance.csv")]
    for extra, out in runs:
        subprocess.run(base + extra + ["--out", os.path.join(out_dir, out)],
                       check=True)


def exp_occupancy(cps, out_dir, dur):
    """Packed-z3 worst-case occupancy + rm/aguard safety pairing, all profiles
    (THEOREM_BRIEF S3.5/S9.2, Lemma 1's empirical backstop). Delegates to
    tools/occupancy_sweep.py (uses ./build/cps)."""
    base = [sys.executable, os.path.join(HERE, "occupancy_sweep.py"), "--force"]
    runs = [([], "occupancy_sweep.csv"),
            (["--profile", "12.5"], "occupancy_sweep_v12.5.csv"),
            (["--profile", "15"], "occupancy_sweep_v15.csv")]
    if QUICK:
        runs = [(["--spacings", "0,1000,4000", "--duration", "10"],
                 "occupancy_sweep.csv")]
    for extra, out in runs:
        subprocess.run(base + extra + ["--out", os.path.join(out_dir, out)],
                       check=True)


REGISTRY = {
    "capacity":  (exp_capacity,  "capacity tournament vs N -> capacity_sweep.csv (PREDICTOR S5 / GENERALIZATION S3)"),
    "simcrit":   (exp_simcrit,   "simultaneous criticality vs N/tau -> simcrit_sweep.csv (PREDICTOR S5d)"),
    "honest":    (exp_honest,    "oracle-vs-honest A/B -> honest_sweep.csv (PREDICTOR S5e)"),
    "floor":     (exp_floor,     "aguard --floor re-sweep -> aguard_sweep.csv (PREDICTOR S5c)"),
    "tolerance": (exp_tolerance, "per-plant tolerance cliff -> tolerance_sweep.csv (PREDICTOR S5d)"),
    "zones":     (exp_zones,     "causal A(zone) tables + fine z3 cliffs, all profiles -> zone_tolerance*.csv (THEOREM_BRIEF S3.2)"),
    "occupancy": (exp_occupancy, "packed-z3 Occ + rm/aguard pairing, all profiles -> occupancy_sweep*.csv (THEOREM_BRIEF S3.5)"),
}

QUICK = False


def main():
    global QUICK
    ap = argparse.ArgumentParser(description="Regenerate the scheduling result CSVs + tables.")
    ap.add_argument("experiments", nargs="*", help="subset to run (default: all)")
    ap.add_argument("--list", action="store_true", help="list experiments and exit")
    ap.add_argument("--cps", default="./build/cps")
    ap.add_argument("--duration", type=int, default=0, help="override per-run sim seconds")
    ap.add_argument("--quick", action="store_true", help="small grids (fast smoke)")
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()
    QUICK = args.quick
    if QUICK:
        # Smoke grids must never overwrite the committed baseline CSVs.
        args.out_dir = os.path.join(args.out_dir, ".reproduce_quick")
        os.makedirs(args.out_dir, exist_ok=True)
        print("[--quick] smoke grids -> %s/ (committed CSVs untouched)" % args.out_dir)

    if args.list:
        for name, (_, desc) in REGISTRY.items():
            print("  %-10s %s" % (name, desc))
        return

    names = args.experiments or list(REGISTRY)
    bad = [n for n in names if n not in REGISTRY]
    if bad:
        sys.exit("unknown experiment(s): %s\nknown: %s" % (", ".join(bad), ", ".join(REGISTRY)))
    if not os.path.exists(args.cps):
        sys.exit("cps binary not found at %s (build it, or pass --cps)" % args.cps)

    for name in names:
        print("\n############ %s ############" % name, flush=True)
        REGISTRY[name][0](args.cps, args.out_dir, args.duration)
    if os.path.exists(SCRATCH):
        os.remove(SCRATCH)
    print("\nDone: %s. CSVs written to %s/." % (", ".join(names), args.out_dir))


if __name__ == "__main__":
    main()
