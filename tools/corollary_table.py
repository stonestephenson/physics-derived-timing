#!/usr/bin/env python3
"""Corollary capacities at the budgets of record (PAPER_NOTES 2026-09-04 (c)).

Derives A(z3) and the base-band budget (the smallest non-z3 A(zone)) per
profile from the committed MIN-OVER-PHASE tables (fresh-F regime, hard
criterion: zone_tolerance_z3_phase*.csv, zone_tolerance_spot_phase*.csv), then
asks tools/rta_solve.py for three certified capacities per workload:

  classical      uniform fleet-max bound <= A(z3), P1 intact
  fdemoted       fleet-wide F-demotion (ZB-F, no occupancy), same test
  decomposition  two-band ZB-F composition with Occ+ cars in the top band
                 (<= A(z3)) and the rest in the base band (<= base budget)

Writes corollary_capacity.csv (one row per profile x workload) and prints the
table. Occ+ = 4 is the s >= 4 s value on every profile (PROOF_DRAFT §3.5,
lemma1_check.py). Workloads: 'limited' = Θ=R (the Guan RTA-LC candidate),
'limited-t' = Θ=T (jitter-only); 'full' (BOUND §7.2 as written) for the
classical column only.

Usage:  python3 tools/corollary_table.py [--out corollary_capacity.csv] [--occ 4] [--force]
"""
import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rta_solve as r  # noqa: E402

ROOT = HERE.parent
PROFILES = {"10": "", "12.5": "_v12.5", "15": "_v15"}
CORES = 3


def a_zone_from_rows(rows, zone):
    """Min-over-phase A(zone) from phase-table rows: the largest delivered age
    whose cell is hard-clean at EVERY phase, below the first any-phase breach.
    A cell's age is the MIN over its phases (on z1 the delivered age differs
    by one E period between phases; the certified budget is the smallest age
    every phase was verified clean at). Rows from several tables of the same
    zone (coarse bracket + fine refinement) may be passed together: the grid
    is the union of their extras. None if no breach in range; 0.0 if the
    first cell already breaches."""
    zr = [x for x in rows if int(x["zone"]) == zone]
    extras = sorted({int(x["extra_ms"]) for x in zr})
    a = None
    for e in extras:
        cell = [x for x in zr if int(x["extra_ms"]) == e]
        if any(int(x["total_hard"]) > 0 for x in cell):
            return a if a is not None else 0.0
        a = min(float(x["age_path_ms"]) for x in cell)
    return None


def phase_tables(root, suf):
    """Every committed fresh-F (ff_extra_ms == 0) phase table for one profile:
    zone_tolerance_z3_phase*, _spot_phase*, and any *_fine_phase* refinement."""
    rows = []
    for f in sorted(root.glob(f"zone_tolerance_*phase{suf}.csv")):
        if "_a2" in f.name:
            continue                      # A2 tables: F delayed, not the constant of record
        for x in csv.DictReader(open(f)):
            if float(x.get("ff_extra_ms", 0) or 0) == 0:
                rows.append(x)
    return rows


def budgets(root=ROOT):
    """{profile: (A_z3, A_base)} from the committed phase tables: per zone,
    the union of every fresh-F table's grid for that profile."""
    out = {}
    for prof, suf in PROFILES.items():
        rows = phase_tables(root, suf)
        a3 = a_zone_from_rows(rows, 3)
        others = [a_zone_from_rows(rows, z) for z in (0, 1, 2)]
        if a3 is None or any(o is None for o in others):
            sys.exit(f"profile {prof}: a zone never breaches in its tables; extend the grid")
        out[prof] = (a3, min(others))
    return out


def table(budget_map, occ_plus=4, cores=CORES):
    ei = r.EXEC_IDX["worst"]
    rows = []
    for prof, (a3, ab) in budget_map.items():
        for wl in ("full", "limited", "limited-t"):
            classical = r.uniform_capacity(a3, cores, ei, wl)
            if wl == "full":
                fdem = dec = None; binder = ""; top = base = None
            else:
                fdem = r.uniform_capacity(a3, cores, ei, wl, demote_f=True)
                dec, binder = r.decomposition_capacity(a3, ab, occ_plus, cores, ei, wl)
                top, base, _ = r.fleet_bound(max(dec, occ_plus), cores, ei, wl,
                                             top_k=occ_plus, demote_f=True)
                if dec == 0:
                    base = None          # nothing admitted: no base band to report
            rows.append({
                "profile": prof, "a_z3_ms": a3, "a_base_ms": ab, "workload": wl,
                "classical_cap": classical, "fdemoted_cap": fdem,
                "decomposition_cap": dec, "decomposition_binder": binder,
                "occ_plus": occ_plus,
                "top_bound_ms": None if top is None else round(top, 1),
                "base_bound_at_cap_ms": None if base is None else round(base, 1),
                "ratio_vs_classical": (None if dec is None or classical == 0
                                       else dec / classical),
                "occupancy_gain_cars": None if dec is None else dec - fdem,
            })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="corollary_capacity.csv")
    ap.add_argument("--occ", type=int, default=4, help="Occ+ (top-band size); 4 = s >= 4 s")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if Path(args.out).exists() and not args.force:
        sys.exit(f"refusing to overwrite {args.out}; pass --force or --out PATH")
    rows = table(budgets(), occ_plus=args.occ)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for row in rows:
            w.writerow({k: ("" if v is None else v) for k, v in row.items()})
    print(f"{'prof':<5} {'A(z3)':>6} {'A_base':>6} {'workload':<10} {'classical':>9} "
          f"{'F-demoted':>9} {'decomp':>6} {'binder':<6} {'top':>6} {'base@cap':>8} {'ratio':>6}")
    for x in rows:
        fmt = lambda v: "-" if v is None or v == "" else v
        ratio = "-" if x["ratio_vs_classical"] is None else f"{x['ratio_vs_classical']:.2f}x"
        print(f"{x['profile']:<5} {x['a_z3_ms']:>6} {x['a_base_ms']:>6} {x['workload']:<10} "
              f"{x['classical_cap']:>9} {fmt(x['fdemoted_cap']):>9} {fmt(x['decomposition_cap']):>6} "
              f"{x['decomposition_binder']:<6} {fmt(x['top_bound_ms']):>6} "
              f"{fmt(x['base_bound_at_cap_ms']):>8} {ratio:>6}")
    print(f"\n  wrote {args.out}")


if __name__ == "__main__":
    main()
