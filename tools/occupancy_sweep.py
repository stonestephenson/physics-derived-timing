#!/usr/bin/env python3
"""Worst-case zone occupancy Occ(R, F_spaced) sweep (THE PLAN leg 2).

Packs the binding zone (z3 lane-change by default) with cars at a minimum
inter-car phase gap (the F_spaced fleet model, THEOREM_BRIEF §3.5), and sweeps
that gap. For each spacing it reports the realized worst-case simultaneous
occupancy Occ vs the geometric prediction ceil(zone_len / spacing), and pairs it
with the realized danger (leg-4 K) and hard breaches under rm vs aguard -- the
occupancy -> schedulability link (Kurt's leg 3). Occ is policy-independent
(geometry); the breach outcome is not.

Writes occupancy_sweep.csv and prints the Occ(s) curve.

Usage:  python3 tools/occupancy_sweep.py [--vehicles N] [--zone Z]
                 [--duration SEC] [--schedulers rm,aguard]
"""
import argparse, csv, re, subprocess, sys
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "build" / "cps"

OCC_RE = re.compile(
    r"Occ max (\d+) of (\d+) \| zone len (\d+) ticks -> geo-predict ceil\(L/s\)=(\d+)")
K_RE = re.compile(r"K\(\+state\) max (\d+) of")


def run(zone, spacing_ms, sched, n, duration):
    """One packed-zone run; return (occ, n, zone_len, geo, k_danger, total_hard)."""
    out = subprocess.run(
        [str(BIN), "--headless", "--vehicles", str(n), "--scheduler", sched,
         "--exec", "worst", "--duration", str(duration),
         "--pack-zone", str(zone), "--min-spacing", str(spacing_ms)],
        capture_output=True, text=True).stdout
    occ = OCC_RE.search(out)
    k = K_RE.search(out)
    if not occ or not k:
        sys.exit(f"parse failure (zone {zone}, {spacing_ms}ms, {sched}):\n{out}")
    # Sum the per-vehicle hard-breach column (col index 4 of the summary table).
    total_hard, in_table = 0, False
    for line in out.splitlines():
        if "veh" in line and "avg_perf" in line:
            in_table = True
            continue
        if "worst-case data age" in line:
            in_table = False
        if in_table:
            parts = line.split()
            if len(parts) >= 5 and parts[0].isdigit():
                total_hard += int(parts[4])
    return (int(occ.group(1)), int(occ.group(2)), int(occ.group(3)),
            int(occ.group(4)), int(k.group(1)), total_hard)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vehicles", type=int, default=18)
    ap.add_argument("--zone", type=int, default=3)        # 3 = binding lane-change
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--schedulers", default="rm,aguard")
    ap.add_argument("--spacings", default="0,250,500,750,1000,1500,2000,3000,4000")
    args = ap.parse_args()
    if not BIN.exists():
        sys.exit(f"build first: {BIN} not found")

    grid = [int(s) for s in args.spacings.split(",")]
    scheds = args.schedulers.split(",")
    rows = []
    print(f"=== Occ(R, F_spaced): pack z{args.zone}, N={args.vehicles}, "
          f"{args.duration}s worst ===")
    print(f"  {'spacing ms':<11} {'sched':<8} {'Occ':<6} {'geo ceil(L/s)':<14} "
          f"{'K(+state)':<10} {'hard'}")
    for sp in grid:
        for sched in scheds:
            occ, n, zlen, geo, k, hard = run(args.zone, sp, sched,
                                             args.vehicles, args.duration)
            rows.append([args.zone, sp, sched, args.vehicles, occ, geo, zlen, k, hard])
            print(f"  {sp:<11} {sched:<8} {str(occ)+'/'+str(n):<6} {geo:<14} "
                  f"{k:<10} {hard}")

    with open("occupancy_sweep.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["zone", "min_spacing_ms", "scheduler", "vehicles", "max_occ",
                    "geo_predict", "zone_len_ticks", "max_k_danger", "total_hard"])
        w.writerows(rows)
    print("\n  wrote occupancy_sweep.csv")
    print("  Occ < N for realistic spacing = the F_spaced slack (Lemma 1); the same"
          " Occ is fatal under rm but safe under aguard (occupancy -> schedulability).")


if __name__ == "__main__":
    main()
