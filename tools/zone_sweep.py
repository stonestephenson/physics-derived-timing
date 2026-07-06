#!/usr/bin/env python3
"""Phase-2 causal A(zone) sweep (ZONE_TOLERANCE.md / leg A).

For each curvature zone, inject extra command delay ONLY while the car is in
that zone (--zone-target Z --zone-extra-ms D) and find the largest delivered
data age at which that zone still has ZERO hard breaches anywhere. This is the
*causal* tolerance A(zone) the fleet bound needs -- distinct from Phase-1
manifestation attribution (a breach can manifest in a later zone via overshoot;
see PAPER_NOTES 2026-06-26).

Writes zone_tolerance.csv and prints the A(zone) table.

Usage:  python3 tools/zone_sweep.py [--duration SEC] [--max-extra MS] [--step MS]
"""
import argparse, csv, re, subprocess, sys
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "build" / "cps"
ZONES = {0: "straight", 1: "slight-turn", 2: "sharp-turn", 3: "lane-change"}

AGE_RE = re.compile(r"([0-9.]+) ms \(path\)")
HARD_RE = re.compile(r"hard z0=(\d+) z1=(\d+) z2=(\d+) z3=(\d+)")


def run(zone, extra_ms, duration, profile="10"):
    """Run one N=1 worst-case full-lap sim; return (age_path_ms, [z0..z3 hard])."""
    out = subprocess.run(
        [str(BIN), "--headless", "--vehicles", "1", "--scheduler", "rm",
         "--exec", "worst", "--duration", str(duration), "--profile", profile,
         "--zone-target", str(zone), "--zone-extra-ms", str(extra_ms)],
        capture_output=True, text=True).stdout
    age = AGE_RE.search(out)
    hard = HARD_RE.search(out)
    if not age or not hard:
        sys.exit(f"parse failure (zone {zone}, +{extra_ms}ms):\n{out}")
    return float(age.group(1)), [int(hard.group(i)) for i in range(1, 5)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=int, default=120)
    ap.add_argument("--min-extra", type=int, default=0,
                    help="grid start (ms); default 0 (fine-grid refinement runs "
                         "set this to the last known-passing extra)")
    ap.add_argument("--max-extra", type=int, default=450)
    ap.add_argument("--step", type=int, default=50)
    ap.add_argument("--zones", default="0,1,2,3",
                    help="comma list of zones to sweep (default all)")
    ap.add_argument("--profile", default="10", choices=["10", "12.5", "15"],
                    help="velocity profile (default 10); per-profile A(zone) "
                         "tables are the generality leg (HANDOFF §5 queue #4)")
    ap.add_argument("--out", default="zone_tolerance.csv",
                    help="output CSV (refuses to overwrite an existing file unless --force)")
    ap.add_argument("--force", action="store_true",
                    help="allow overwriting an existing --out file")
    args = ap.parse_args()
    if not BIN.exists():
        sys.exit(f"build first: {BIN} not found")
    if Path(args.out).exists() and not args.force:
        sys.exit(f"refusing to overwrite existing {args.out}; pass --force to "
                 f"regenerate it, or --out PATH to write elsewhere")

    grid = list(range(args.min_extra, args.max_extra + 1, args.step))
    zones = [int(z) for z in args.zones.split(",")]
    rows, table = [], []
    for z in zones:
        a_zone, first_breach = None, None
        for extra in grid:
            age, hard = run(z, extra, args.duration, args.profile)
            total = sum(hard)
            rows.append([z, ZONES[z], extra, age, total, *hard])
            if total == 0:
                a_zone = age                       # largest safe age so far
            elif first_breach is None:
                first_breach = (age, hard)         # first age that breaches
            print(f"  z{z} {ZONES[z]:<12} +{extra:<4}ms  age={age:<8} hard={total}")
        table.append((z, a_zone, first_breach))

    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["zone", "zone_name", "extra_ms", "age_path_ms", "total_hard",
                    "z0_hard", "z1_hard", "z2_hard", "z3_hard"])
        w.writerows(rows)

    print("\n=== Causal A(zone) (largest delivered age with ZERO hard breaches) ===")
    print(f"  {'zone':<14} {'A(zone) ms':<12} {'first-breach age (where it landed)'}")
    for z, a_zone, fb in table:
        fbtxt = "none in range" if fb is None else \
            f"{fb[0]} ms  [z0={fb[1][0]} z1={fb[1][1]} z2={fb[1][2]} z3={fb[1][3]}]"
        print(f"  z{z} {ZONES[z]:<12} {str(a_zone):<12} {fbtxt}")
    print(f"\n  wrote {args.out}")


if __name__ == "__main__":
    main()
