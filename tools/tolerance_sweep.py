#!/usr/bin/env python3
"""tolerance_sweep.py - per-plant data-age tolerance (Phase 3 evidence).

Sweeps the network delay at N=1 for each plant, records the ACHIEVED data age
(age_path -- the independent variable, per ZONE_TOLERANCE.md) and whether the
safety bound was breached (hard), and reports the largest age with zero hard
breaches = the plant's age tolerance.

This is the headline generalization result: the SAME scheduler / data-age / bound
machinery, two plants, but the tolerance is physics-derived and plant-dependent
-- the stable car tolerates large/gradual staleness, the unstable cart-pole a
tight/sharp band. One-command reproducible; writes a CSV for the figure.

Usage:  python3 tools/tolerance_sweep.py [--duration 30] [--out tolerance_sweep.csv]
"""
import argparse
import csv
import subprocess
import sys


def run(cps, plant, delay_ms, dur):
    cmd = [cps, "--headless", "--plant", plant, "--vehicles", "1",
           "--scheduler", "rm", "--exec", "worst",
           "--net-delay", str(delay_ms), "--duration", str(dur)]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=600).stdout
    for line in out.splitlines():
        t = line.split()
        # vehicle row: veh avg_perf max_roll soft% hard age_fresh age_path min_pnr pnr0
        if len(t) >= 7 and t[0] == "0":
            age = None if t[6] == "n/a" else float(t[6])
            return {"hard": int(t[4]), "age_path": age, "max_roll": float(t[2])}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cps", default="./build/cps")
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--out", default="tolerance_sweep.csv")
    ap.add_argument("--plants", default="lateral,cartpole")
    ap.add_argument("--delays",
                    default="4,8,12,16,20,24,28,32,40,60,90,140,200,300")
    args = ap.parse_args()
    delays = [int(x) for x in args.delays.split(",")]
    plants = args.plants.split(",")

    rows, summary = [], {}
    for plant in plants:
        print("== %s ==" % plant)
        for d in delays:
            r = run(args.cps, plant, d, args.duration)
            if r is None:
                print("  delay=%-4d  PARSE FAIL" % d)
                continue
            rows.append({"plant": plant, "net_delay_ms": d, **r})
            print("  delay=%-4d  age_path=%-7s  hard=%-7d  %s"
                  % (d, r["age_path"], r["hard"], "safe" if r["hard"] == 0 else "BREACH"))
        safe = [x for x in rows if x["plant"] == plant and x["hard"] == 0 and x["age_path"] is not None]
        bad  = [x for x in rows if x["plant"] == plant and x["hard"] > 0 and x["age_path"] is not None]
        summary[plant] = (max((x["age_path"] for x in safe), default=None),
                          min((x["age_path"] for x in bad), default=None))

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["plant", "net_delay_ms", "age_path", "hard", "max_roll"])
        w.writeheader()
        for row in rows:
            w.writerow(row)

    print("\n=== age tolerance (largest safe age_path / smallest breaching age_path, ms) ===")
    for plant in plants:
        hi_safe, lo_bad = summary[plant]
        if lo_bad is None:
            print("  %-9s tolerance >= %s ms  (no breach up to delay %d)" % (plant, hi_safe, delays[-1]))
        else:
            print("  %-9s tolerance in (%s, %s] ms" % (plant, hi_safe, lo_bad))
    print("  data: %s" % args.out)


if __name__ == "__main__":
    main()
