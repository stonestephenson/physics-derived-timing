#!/usr/bin/env python3
"""Is the zone partition the same track partition on every profile?
(ZONE_TOLERANCE.md partition caveat; PAPER_NOTES 2026-09-04 (d).)

Builds the read-only route probe (tools/proofchecks/zone_probe.cpp, links the
repo's Trajectory.cpp unchanged), dumps every zone run per profile, converts
ticks to track metres with the x/y reference traces, and compares each
profile's zone boundaries with v10's nearest boundary of the same zone.
Writes zone_partition_runs.csv (profile, zone, start_tick, len_ticks, start_m,
len_m) and prints the comparison. Needs a C++17 compiler on PATH (`c++`).

Usage:  python3 tools/zone_partition.py [--out zone_partition_runs.csv] [--force]
"""
import argparse
import csv
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PROBE_SRC = HERE / "proofchecks" / "zone_probe.cpp"
DIRS = {"v10": "example_v_10", "v12.5": "example_v_12_5", "v15": "example_v_15"}
LAPS = {"v10": 1178000, "v12.5": 944000, "v15": 786000}


def arc_length(xs, ys):
    s = [0.0]
    for i in range(1, len(xs)):
        s.append(s[-1] + math.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1]))
    return s


def runs_to_metres(runs, s, lap_ticks):
    """[(zone, start_tick, len_ticks)] -> [(zone, start_m, len_m)]; s[k] is the
    cumulative arc length at tick k (s has lap_ticks + 1 entries or more);
    a run that wraps past the lap end is measured across the wrap."""
    lap_m = s[lap_ticks] if len(s) > lap_ticks else s[-1]
    out = []
    for z, st, ln in runs:
        end = st + ln
        if end <= lap_ticks:
            length = s[end] - s[st]
        else:
            length = (lap_m - s[st]) + s[end - lap_ticks]
        out.append((z, s[st], length))
    return out


def zone_totals(runs_m):
    tot = {z: 0.0 for z in range(4)}
    for z, _, ln in runs_m:
        tot[z] += ln
    return tot


def compare(runs_m, ref_m, min_run_m=0.5):
    """Each boundary (entry into zone z at position p) in runs_m is matched to
    the nearest same-zone boundary in ref_m. Runs shorter than min_run_m
    (the 20 ms zero-crossing slivers where the curvature changes sign) are
    set aside and listed, not compared. Reports the max deviation and the
    ref boundaries that found no partner within 25 m."""
    def keep(rs):
        # drop slivers, then merge the same-zone neighbours they had split
        kept = sorted((x for x in rs if x[2] >= min_run_m), key=lambda x: x[1])
        merged = []
        for z, p, ln in kept:
            if merged and merged[-1][0] == z and abs(merged[-1][1] + merged[-1][2] - p) < 5 * min_run_m:
                merged[-1] = (z, merged[-1][1], merged[-1][2] + ln + (p - merged[-1][1] - merged[-1][2]))
            else:
                merged.append((z, p, ln))
        return merged
    runs_k, ref_k = keep(runs_m), keep(ref_m)
    slivers = [(z, p, ln) for z, p, ln in runs_m + ref_m if ln < min_run_m]
    devs = []
    for z, p, _ in runs_k:
        cands = [abs(p - q) for zz, q, _ in ref_k if zz == z]
        if cands:
            devs.append(min(cands))
    unmatched = []
    for z, q, _ in ref_k:
        cands = [abs(p - q) for zz, p, _ in runs_k if zz == z]
        if not cands or min(cands) > 25.0:
            unmatched.append((z, q))
    return {"max_boundary_dev_m": max(devs) if devs else None,
            "n_boundaries": len(runs_k), "unmatched": unmatched, "slivers": slivers}


def build_probe(exe):
    cmd = ["c++", "-std=c++17", "-O2", "-I", str(ROOT / "src"), "-o", str(exe),
           str(PROBE_SRC), str(ROOT / "src" / "trace" / "Trajectory.cpp")]
    subprocess.run(cmd, check=True, cwd=ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="zone_partition_runs.csv")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if Path(args.out).exists() and not args.force:
        sys.exit(f"refusing to overwrite {args.out}; pass --force or --out PATH")
    exe = ROOT / "build" / "zone_probe"
    exe.parent.mkdir(exist_ok=True)
    build_probe(exe)
    dump = subprocess.run([str(exe), "--csv"], capture_output=True, text=True,
                          check=True, cwd=ROOT).stdout
    runs = {}
    for row in csv.DictReader(dump.splitlines()):
        runs.setdefault(row["profile"], []).append(
            (int(row["zone"]), int(row["start_tick"]), int(row["len_ticks"])))

    metres, rows = {}, []
    for prof, d in DIRS.items():
        xs = [float(v) for v in open(ROOT / "examples" / d / "x_position_track.csv")][:LAPS[prof]]
        ys = [float(v) for v in open(ROOT / "examples" / d / "y_position_track.csv")][:LAPS[prof]]
        s = arc_length(xs, ys)
        s.append(s[-1] + math.hypot(xs[0] - xs[-1], ys[0] - ys[-1]))   # close the lap
        metres[prof] = runs_to_metres(runs[prof], s, LAPS[prof])
        for (z, st, ln), (_, sm, lm) in zip(runs[prof], metres[prof]):
            rows.append({"profile": prof, "zone": z, "start_tick": st, "len_ticks": ln,
                         "start_m": round(sm, 2), "len_m": round(lm, 2)})
        print(f"{prof}: lap {s[LAPS[prof]]:.1f} m, {len(runs[prof])} runs; zone lengths (m): "
              + "  ".join(f"z{z}={v:.1f}" for z, v in zone_totals(metres[prof]).items()))
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    for prof in ("v12.5", "v15"):
        rep = compare(metres[prof], metres["v10"])
        unm = ", ".join(f"z{z} at {q:.0f} m" for z, q in rep["unmatched"]) or "none"
        sl = ", ".join(f"z{z} {ln*100:.0f} cm at {p:.0f} m" for z, p, ln in rep["slivers"]) or "none"
        print(f"{prof} vs v10: {rep['n_boundaries']} boundaries, max deviation from v10's nearest "
              f"same-zone boundary {rep['max_boundary_dev_m']:.2f} m; v10 boundaries with no "
              f"partner within 25 m: {unm}; slivers set aside: {sl}")
    print(f"\n  wrote {args.out}")


if __name__ == "__main__":
    main()
