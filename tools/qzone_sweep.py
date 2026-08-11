#!/usr/bin/env python3
"""FCHANNEL qzone collapse experiment (FCHANNEL.md §8 item 10 / §10).

Reviewer B's Factor A: inject a signed zero-age reference-curvature ERROR eps
into q = kappa + 0.2*dkappa/ds while the car is inside the target zone
(--qzone-target/--qzone-eps) and bracket the breach boundary eps*(zone,
profile, sign) under the breach-anywhere criterion. The pre-registered
first-order model prices the dose as Delta a_ref = v^2 * eps, so across
profiles eps* should scale as 1/max(v^2 in zone) IF the amplitude unit
collapses; the sustained-DC alternative (the feedback loop rejects a constant
curvature offset, so eps* is rejection-limited and roughly speed-flat) is the
disconfirming outcome, committed to print either way (§8 item 9 discipline).

Every row: signed eps, per-zone hard counts, undecimated fleet + target-zone
max|e_y|, age_path (C4: constant by construction — the dose is invisible to
the certified metric), per-kind missed, full run identity + git SHA. eps = 0
null rows anchor each (zone, profile) block to the baseline.
"""
import argparse
import concurrent.futures as cf
import csv
import re
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "build" / "cps"
ZONES = {0: "straight", 1: "slight-turn", 2: "sharp-turn", 3: "lane-change"}
# Full-lap durations per profile (reproduce.py zones registration).
DURATION = {"10": 120, "12.5": 95, "15": 79}
# Per-zone max(v^2) from tools/proofchecks/zone_probe.cpp (2026-08-11 run;
# regenerate with the probe if the tapes ever change). Used ONLY to print the
# v^-2 collapse prediction next to the measured ratios — never in a verdict.
V2MAX = {"10":   {0: 100.0, 1: 100.0, 2: 88.3,  3: 81.0},
         "12.5": {0: 156.2, 1: 156.2, 2: 137.8, 3: 126.6},
         "15":   {0: 225.0, 1: 225.0, 2: 198.4, 3: 182.2}}

AGE_RE = re.compile(r"([0-9.]+) ms \(path\)")
HARD_RE = re.compile(r"hard z0=(\d+) z1=(\d+) z2=(\d+) z3=(\d+)")
EY_RE = re.compile(r"max \|e_y\| \(per-tick\): fleet ([0-9.]+) m .*\| zones "
                   r"([0-9.]+) ([0-9.]+) ([0-9.]+) ([0-9.]+)")
MISS_RE = re.compile(r"missed by kind: E=(\d+) B=(\d+) F=(\d+) M=(\d+)")


def git_sha():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True,
                              cwd=BIN.parent.parent).stdout.strip()
    except OSError:
        return "unknown"


def run(zone, eps, profile, args):
    cmd = [str(BIN), "--headless", "--vehicles", "1", "--scheduler",
           args.scheduler, "--exec", "worst", "--profile", profile,
           "--duration", str(args.duration or DURATION[profile])]
    if eps != 0.0:
        cmd += ["--qzone-target", str(zone), "--qzone-eps", str(eps)]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    age, hard = AGE_RE.search(out), HARD_RE.search(out)
    ey, miss = EY_RE.search(out), MISS_RE.search(out)
    if age is None or hard is None or ey is None or miss is None:
        sys.exit(f"parse failure (z{zone}, eps {eps}, v{profile}):\n{out}")
    return {
        "age_path": float(age.group(1)),
        "hard": [int(hard.group(i)) for i in range(1, 5)],
        "fleet_ey": float(ey.group(1)),
        "zone_ey": [float(ey.group(i)) for i in range(2, 6)],
        "miss": [int(miss.group(i)) for i in range(1, 5)],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zones", default="0,1,2,3")
    ap.add_argument("--profiles", default="10,12.5,15")
    ap.add_argument("--grid", default="0.02,0.03,0.04,0.05,0.06,0.08,0.10,"
                                      "0.12,0.16,0.20,0.25,0.30",
                    help="unsigned eps magnitudes (1/m); each runs BOTH signs")
    ap.add_argument("--duration", type=int, default=0,
                    help="override the per-profile full-lap duration")
    ap.add_argument("--scheduler", default="rm")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--out", default="qzone_collapse.csv")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if not BIN.exists():
        sys.exit(f"build first: {BIN} not found")
    if Path(args.out).exists() and not args.force:
        sys.exit(f"refusing to overwrite existing {args.out}; pass --force or --out PATH")

    sha = git_sha()
    mags = [float(g) for g in args.grid.split(",")]
    zones = [int(z) for z in args.zones.split(",")]
    profiles = args.profiles.split(",")
    # One eps=0 null per profile (the baseline anchor), then the signed grid.
    todo = [(p, zones[0], 0.0) for p in profiles]
    todo += [(p, z, s * m) for p in profiles for z in zones
             for m in mags for s in (+1, -1)]

    results = {}
    with cf.ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(run, z, e, p, args): (p, z, e) for p, z, e in todo}
        for f in cf.as_completed(futs):
            p, z, e = futs[f]
            r = results[(p, z, e)] = f.result()
            print(f"  v{p} z{z} {ZONES[z]:<12} eps={e:<7.3f} "
                  f"hard={sum(r['hard']):<5} maxEy={r['fleet_ey']:.4f}",
                  flush=True)

    rows, table = [], {}
    for p in profiles:
        base = results[(p, zones[0], 0.0)]
        rows.append([p, -1, "baseline", 0.0, sum(base["hard"]), *base["hard"],
                     base["fleet_ey"], base["fleet_ey"], base["age_path"],
                     *base["miss"], args.scheduler, 1, 3, "worst",
                     args.duration or DURATION[p], 10, sha])
        for z in zones:
            for e in [s * m for m in mags for s in (+1, -1)]:
                r = results[(p, z, e)]
                rows.append([p, z, ZONES[z], e, sum(r["hard"]), *r["hard"],
                             r["fleet_ey"], r["zone_ey"][z], r["age_path"],
                             *r["miss"], args.scheduler, 1, 3, "worst",
                             args.duration or DURATION[p], 10, sha])
            for sign in (+1, -1):
                clean = [m for m in mags
                         if sum(results[(p, z, sign * m)]["hard"]) == 0]
                breach = [m for m in mags
                          if sum(results[(p, z, sign * m)]["hard"]) > 0]
                table[(p, z, sign)] = (max(clean) if clean else None,
                                       min(breach) if breach else None)

    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["profile", "zone", "zone_name", "eps_per_m", "total_hard",
                    "z0_hard", "z1_hard", "z2_hard", "z3_hard",
                    "fleet_max_ey_m", "target_zone_max_ey_m", "age_path_ms",
                    "missed_E", "missed_B", "missed_F", "missed_M",
                    "scheduler", "vehicles", "cores", "exec", "duration_s",
                    "decimation_ms", "git_sha"])
        w.writerows(rows)

    print("\n=== eps*(zone, profile, sign) brackets (largest clean |eps|; "
          "breach-anywhere) ===")
    for z in zones:
        for sign, tag in ((+1, "+"), (-1, "-")):
            marks = []
            for p in profiles:
                lc, fb = table[(p, z, sign)]
                marks.append(f"v{p}: [{lc}, {fb})")
            print(f"  z{z} {ZONES[z]:<12} {tag}eps  " + "   ".join(marks))
    print("\n=== collapse check: if Delta a_ref = v^2*eps prices the dose, "
          "eps* scales as 1/max(v^2 in zone) ===")
    for z in zones:
        pred = ["%.2f" % (V2MAX[profiles[0]][z] / V2MAX[p][z])
                for p in profiles]
        print(f"  z{z}: predicted eps*(v)/eps*(v{profiles[0]}) = "
              + ", ".join(pred) + "  (compare the measured brackets above)")
    print(f"\n  wrote {args.out} (git {sha})")


if __name__ == "__main__":
    main()
