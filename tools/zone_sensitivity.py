#!/usr/bin/env python3
"""Zone-partition sensitivity of the binding numbers (ZONE_TOLERANCE.md
partition caveat; PAPER_NOTES 2026-09-04 (d)).

The partition's six constants (Trajectory.h; `cps --zone-consts`) were
hand-tuned on v10. The partition itself is spatially the same on every profile
(curvature thresholds are speed-independent; only the time-based lane-change
expansion grows with speed), so the question that matters for the paper is:
do the certified numbers on v12.5 move if the constants move? For each
variant this runs the z3 cliff (A(z3), the certified constant) and the z2
cliff (A(z2), the base-band budget) min-over-phase on the 10 ms grid, records
the partition's frame counts, and asks the solver for the composed
certificate at the variant's budgets.

Variants: sharp-turn threshold x0.8 / x1.2 (the z1/z2 boundary), lane-change
seed thresholds x0.8 / x1.2 (z3 seeds), lane-change time constants x0.5 /
x1.5 (window/pad/bridge), plus the baseline.

Usage:  python3 tools/zone_sensitivity.py [--profile 12.5] [--jobs 8]
          [--z3-grid 20:100:10] [--z2-grid 60:200:10] [--out PREFIX] [--force]
Writes PREFIX.csv (every run) and PREFIX_summary.csv (one row per variant).
"""
import argparse
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import rta_solve as r  # noqa: E402
import zone_sweep as zs  # noqa: E402

DEFAULTS = (0.0215, 0.0035, 0.0040, 50.0, 100.0, 350.0)
# (name, sharp factor, seed factor, time factor)
VARIANTS = [("baseline", 1, 1, 1),
            ("sharp_x0.8", 0.8, 1, 1), ("sharp_x1.2", 1.2, 1, 1),
            ("seeds_x0.8", 1, 0.8, 1), ("seeds_x1.2", 1, 1.2, 1),
            ("times_x0.5", 1, 1, 0.5), ("times_x1.5", 1, 1, 1.5)]
# non-z3 budgets of record that are NOT re-measured per variant (z0, z1 on v12.5)
OTHER_BUDGETS = {"10": (290.5, 390.5), "12.5": (290.5, 240.5), "15": (240.5, 190.5)}
DURATION = {"10": 120, "12.5": 95, "15": 79}
OCC_PLUS = 4


def consts_for(sharp_f, seed_f, time_f):
    s, f, d, w, p, b = DEFAULTS
    vals = (s * sharp_f, f * seed_f, d * seed_f, w * time_f, p * time_f, b * time_f)
    return ",".join(f"{round(v, 6):g}" for v in vals)


def parse_grid(spec):
    a, b, c = (int(x) for x in spec.split(":"))
    return list(range(a, b + 1, c))


def campaign(profile, duration, z3_grid, z2_grid, runner, jobs=8, variants=VARIANTS,
             log=None):
    """runner(zone, extra, phase, zone_consts) -> zone_sweep result dict.
    Returns (per-run rows, per-variant summary rows)."""
    phases = [("offset_ms", v) for v in zs.parse_phases("0:20:1")]
    rows, summary = [], []
    a_z0, a_z1 = OTHER_BUDGETS[profile]
    ei = r.EXEC_IDX["worst"]
    for name, sf, gf, tf in variants:
        zc = consts_for(sf, gf, tf)
        frames = runner(3, 0, ("offset_ms", 0.0), zc)["zone_frames"]
        entries = {}
        for zone, grid in ((3, z3_grid), (2, z2_grid)):
            zrows, (entry,) = zs.sweep([zone], grid, phases,
                                       lambda z, x, ph: runner(z, x, ph, zc),
                                       jobs=jobs, log=log)
            entries[zone] = entry
            for zr in zrows:
                rows.append({"variant": name, "zone_consts": zc, "zone": zr[0],
                             "extra_ms": zr[2], "phase": zr[4], "age_path_ms": zr[5],
                             "total_hard": zr[6], "z0_hard": zr[7], "z1_hard": zr[8],
                             "z2_hard": zr[9], "z3_hard": zr[10], "soft_pct": zr[11],
                             "fleet_max_ey_m": zr[12], "profile": profile,
                             "duration_s": duration})
        a3, a2 = entries[3].a_zone, entries[2].a_zone
        base = None if a2 is None else min(a_z0, a_z1, a2)
        caps = {}
        for wl in ("limited", "limited-t"):
            if a3 is None or base is None:
                caps[wl] = None
            else:
                caps[wl] = r.decomposition_capacity(a3, base, OCC_PLUS, 3, ei, wl)[0]
        summary.append({
            "variant": name, "zone_consts": zc, "profile": profile,
            "z0_frames": frames[0], "z1_frames": frames[1], "z2_frames": frames[2],
            "z3_frames": frames[3],
            "a_z3_ms": a3, "a_z3_first_breach_ms": None if entries[3].first_breach is None
            else entries[3].first_breach[0],
            "a_z2_ms": a2, "a_z2_first_breach_ms": None if entries[2].first_breach is None
            else entries[2].first_breach[0],
            "base_budget_ms": base,
            "composed_cap_limited": caps["limited"],
            "composed_cap_limited_t": caps["limited-t"],
        })
    return rows, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="12.5", choices=list(DURATION))
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--z3-grid", default="20:100:10", help="extra ms START:STOP:STEP (inclusive)")
    ap.add_argument("--z2-grid", default="60:200:10")
    ap.add_argument("--out", default=None, help="prefix (default zone_sensitivity_v<profile>)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    prefix = args.out or f"zone_sensitivity_v{args.profile}"
    runs_path, sum_path = Path(prefix + ".csv"), Path(prefix + "_summary.csv")
    for pth in (runs_path, sum_path):
        if pth.exists() and not args.force:
            sys.exit(f"refusing to overwrite {pth}; pass --force or --out PREFIX")
    if not zs.BIN.exists():
        sys.exit(f"build first: {zs.BIN} not found")
    duration = DURATION[args.profile]

    def runner(zone, extra, phase, zc):
        return zs.run(zone, extra, duration, args.profile, phase, 0.0, zc)

    def log(z, extra, phase, res):
        print(f"  z{z} +{extra:<4} {phase[0]}={phase[1]:<5} age={res['age_path']:<7} "
              f"hard={sum(res['hard']):<4} maxEy={res['fleet_ey']:.4f}", flush=True)

    sha = zs.git_sha()
    rows, summary = campaign(args.profile, duration, parse_grid(args.z3_grid),
                             parse_grid(args.z2_grid), runner, jobs=args.jobs, log=log)
    for row in rows:
        row["git_sha"] = sha
    for row in summary:
        row["git_sha"] = sha
    for pth, data in ((runs_path, rows), (sum_path, summary)):
        with open(pth, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            w.writeheader()
            for row in data:
                w.writerow({k: ("" if v is None else v) for k, v in row.items()})
    print(f"\n=== zone-partition sensitivity, v{args.profile} (21 phases, 10 ms grid) ===")
    print(f"  {'variant':<11} {'frames z0/z1/z2/z3':<24} {'A(z3)':>6} {'A(z2)':>6} "
          f"{'base':>6} {'composed R/T':>12}")
    for s in summary:
        fr = f"{s['z0_frames']}/{s['z1_frames']}/{s['z2_frames']}/{s['z3_frames']}"
        print(f"  {s['variant']:<11} {fr:<24} {str(s['a_z3_ms']):>6} {str(s['a_z2_ms']):>6} "
              f"{str(s['base_budget_ms']):>6} {str(s['composed_cap_limited']):>5}/"
              f"{str(s['composed_cap_limited_t'])}")
    print(f"\n  wrote {runs_path} and {sum_path} (git {sha})")


if __name__ == "__main__":
    main()
