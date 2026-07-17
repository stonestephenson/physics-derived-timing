#!/usr/bin/env python3
"""Danger-relative criticality K(tau) sweep (THE PLAN leg 4).

One `--danger-tau` run makes the sim sweep a fixed tau grid
{0.25,0.5,0.75,1.0,1.25,1.5} and print TWO curves (Simulation.cpp:720-730):
  [age-only]  K_age(tau)  -- cars whose delivered age_path >= tau * A(zone_now)
  [+state]    K(tau)      -- K_age unioned with the state-critical (TTPNR<tau_crit) cars
The sim's own --csv only records the single primary-tau point, so the full
curve is stdout-only; this tool captures BOTH curves per policy into
danger_sweep.csv, so the THEOREM_BRIEF §9.2c table AND the orthogonality finding
(RM's K is all state-term with K_age~0; aguard's is all age-term with 0
state-critical -- PAPER_NOTES 2026-06-29) are reproducible one-command.

Lateral / v10 ONLY: the A(zone) budgets the metric compares against are hard-coded
v10 ({290,400,290,140} ms, Simulation.cpp) -- running it on another profile would
score ages against the wrong budgets. Per-profile generalization is parked
(HANDOFF §5; EE owns the zone side).

Writes danger_sweep.csv and prints the K(tau) curves.

Usage:  python3 tools/danger_sweep.py [--vehicles N] [--duration SEC]
                 [--schedulers rm,aguard] [--out FILE] [--force]
"""
import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "build" / "cps"

AGE_RE = re.compile(r"K\(tau\) curve \[age-only\]:(.*)")
STATE_RE = re.compile(r"K\(tau\) curve \[\+state\] :(.*)")
PAIR_RE = re.compile(r"(\d+\.\d+):(\d+)")


def run(sched, n, duration):
    """One packed danger run; return [(tau, k_age, k_state), ...] over the grid."""
    out = subprocess.run(
        [str(BIN), "--headless", "--vehicles", str(n), "--scheduler", sched,
         "--exec", "worst", "--duration", str(duration), "--profile", "10",
         "--danger-tau", "1.0"],
        capture_output=True, text=True, timeout=600).stdout
    age_m, state_m = AGE_RE.search(out), STATE_RE.search(out)
    if not age_m or not state_m:
        sys.exit(f"parse failure (danger, {sched}, N={n}):\n{out}")
    age = {float(t): int(v) for t, v in PAIR_RE.findall(age_m.group(1))}
    state = {float(t): int(v) for t, v in PAIR_RE.findall(state_m.group(1))}
    return [(t, age[t], state[t]) for t in sorted(age)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vehicles", type=int, default=18)
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--schedulers", default="rm,aguard")
    ap.add_argument("--out", default="danger_sweep.csv",
                    help="output CSV (refuses to overwrite an existing file unless --force)")
    ap.add_argument("--force", action="store_true",
                    help="allow overwriting an existing --out file")
    args = ap.parse_args()
    if not BIN.exists():
        sys.exit(f"build first: {BIN} not found")
    if Path(args.out).exists() and not args.force:
        sys.exit(f"refusing to overwrite existing {args.out}; pass --force to "
                 f"regenerate it, or --out PATH to write elsewhere")

    scheds = args.schedulers.split(",")
    rows = []
    print(f"=== K(tau) danger-relative criticality: v10, N={args.vehicles}, "
          f"{args.duration}s worst ===")
    print(f"  {'sched':<8} {'tau':<6} {'K_age':<7} {'K(+state)'}")
    for sched in scheds:
        for tau, k_age, k_state in run(sched, args.vehicles, args.duration):
            rows.append([sched, args.vehicles, tau, k_age, k_state])
            print(f"  {sched:<8} {tau:<6.2f} {k_age:<7} {k_state}")

    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["scheduler", "vehicles", "danger_tau", "max_k_age",
                    "max_k_danger"])
        w.writerows(rows)
    print(f"\n  wrote {args.out}")
    print("  max_k_danger = K(+state) (the §9.2c curve); the two axes are orthogonal"
          " -- RM's K is state-term (K_age~0), aguard's is age-term (0 state-critical).")


if __name__ == "__main__":
    main()
