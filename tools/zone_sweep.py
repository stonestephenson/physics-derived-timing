#!/usr/bin/env python3
"""Phase-2 causal A(zone) sweep (ZONE_TOLERANCE.md / leg A), phase-aware.

For each curvature zone, inject extra command delay ONLY while the car is in
that zone (--zone-target Z --zone-extra-ms D) and find the largest delivered
data age at which that zone still has ZERO hard breaches anywhere. This is the
*causal* tolerance A(zone) the fleet bound needs -- distinct from Phase-1
manifestation attribution (a breach can manifest in a later zone via overshoot;
see PAPER_NOTES 2026-06-26).

MIN OVER PHASE (2026-09-04; paper/PLAN.md §3, PAPER_NOTES 2026-09-04). A(zone)
depends on the phase of the control chain's releases relative to the zone
entry: the single-phase (seed-0, lap index 0) value is the LUCKIEST phase for
z3. The phase axis is the chain hyperperiod (20 ms; lap lengths are multiples
of it, so the phase at a track index is lap-invariant). Two phase modes:

  --phases-ms 0:20:1     deterministic enumeration of the start offset along
                         the lap (--start-offsets-ms): the 1 ms grid over one
                         hyperperiod PLUS the last representable tick before
                         STOP (19.9 ms) — the half-open phase interval's sup,
                         which is the WORST phase at every measured cliff (a
                         grid that omits it under-reports; cold review
                         2026-09-04 caught v12.5 z3 150.5 -> 140.5 that way)
  --offset-seeds 20      random LAP POSITIONS (--offset-seed 1..K), the sampler
                         the 2026-08-24 refutation used; samples the chain
                         phase uniformly but also moves the start transient
                         around the track — kept for reproducibility, not the
                         axis of record

A grid point is CLEAN only if EVERY phase is hard-clean; A(zone) is the largest
clean delivered age BELOW the first any-phase breach (= min over phase; a
clean cell above a breach is reported as NON-MONOTONE, never as A). The
per-phase A range is reported as the spread. soft% (share of the run with |e_y| > 0.2 m; the Challenge's soft
constraint is >= 95 % within 0.2 m, i.e. soft% <= 5) is recorded per row and a
SECONDARY A_soft(zone) (hard-clean AND soft% <= --soft-budget at every phase)
is reported -- the committed A(zone) tables are hard-only (ZONE_TOLERANCE.md).

Without a phase option the tool is byte-compatible with its pre-phase self
(legacy 9-column CSV, single seed-0 run per grid point).

Usage:  python3 tools/zone_sweep.py [--profile 10|12.5|15] [--zones 0,1,2,3]
          [--min-extra MS] [--max-extra MS] [--step MS] [--duration SEC]
          [--phases-ms SPEC | --offset-seeds SPEC] [--jobs N]
          [--out FILE] [--force]
"""
import argparse
import csv
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "build" / "cps"
ZONES = {0: "straight", 1: "slight-turn", 2: "sharp-turn", 3: "lane-change"}
SOFT_BUDGET_PCT = 5.0   # Challenge soft constraint: |e_y| <= 0.2 m for >= 95 % of the run
TICK_MS = 0.1           # simulator tick (src/fmu/FmuVariables.h kBaseStepSeconds)

AGE_RE = re.compile(r"([0-9.]+) ms \(path\)")
HARD_RE = re.compile(r"hard z0=(\d+) z1=(\d+) z2=(\d+) z3=(\d+)")
SOFT_RE = re.compile(r"^\s*0\s+[-0-9.]+\s+[-0-9.]+\s+([0-9.]+)%", re.M)   # vehicle-0 row
EY_RE = re.compile(r"max \|e_y\| \(per-tick\): fleet ([0-9.]+) m .*\| zones "
                   r"([0-9.]+) ([0-9.]+) ([0-9.]+) ([0-9.]+)")
FST_RE = re.compile(r"F staleness \(act-stamped, ms\): zone max "
                    r"([0-9.]+) ([0-9.]+) ([0-9.]+) ([0-9.]+)")   # lateral only


# ----------------------------------------------------------------------- parsing
def parse_output(out):
    """Parse one headless run's summary. None if any required line is missing."""
    age, hard, soft, ey = (AGE_RE.search(out), HARD_RE.search(out),
                           SOFT_RE.search(out), EY_RE.search(out))
    if not (age and hard and soft and ey):
        return None
    fst = FST_RE.search(out)
    return {
        "age_path": float(age.group(1)),
        "hard": [int(hard.group(i)) for i in range(1, 5)],
        "soft_pct": float(soft.group(1)),
        "fleet_ey": float(ey.group(1)),
        "zone_ey": [float(ey.group(i)) for i in range(2, 6)],
        # delivered F dose (act-stamped F age, max over zones) — the A2
        # instrument's effect is visible here, never in age_path
        "f_stale_max": max(float(fst.group(i)) for i in range(1, 5)) if fst else None,
    }


def parse_phases(spec):
    """'START:STOP:STEP' (STOP exclusive) or 'a,b,c' -> list of offsets (ms).

    A range ALWAYS ends with the last representable tick before STOP
    (STOP - TICK_MS): the phase interval is half-open and its sup is the worst
    phase at every measured cliff, so a grid that stops one step short
    under-reports A(zone)."""
    if ":" in spec:
        start, stop, step = (float(x) for x in spec.split(":"))
        if step <= 0 or stop <= start:
            sys.exit(f"bad --phases-ms range {spec!r} (want START:STOP:STEP, STEP > 0)")
        n = int(round((stop - start) / step))
        phases = [round(start + i * step, 6) for i in range(n)]
        last = round(stop - TICK_MS, 6)
        if last > phases[-1]:
            phases.append(last)
        return phases
    return [float(x) for x in spec.split(",")]


def parse_seeds(spec):
    """'K' -> [1..K]; 'a,b,c' -> that list. Seed 0 is rejected: it is the
    deterministic single-phase path (Simulation.cpp:109), not a random draw."""
    seeds = ([int(x) for x in spec.split(",")] if "," in spec
             else list(range(1, int(spec) + 1)))
    if any(s <= 0 for s in seeds):
        sys.exit("--offset-seeds must be positive (seed 0 = the deterministic phase)")
    return seeds


def check_ff_extra(ff_extra_ms, legacy):
    """--ff-extra-ms must be >= 0 and needs a phase mode (the legacy CSV
    schema has no column to record it)."""
    if ff_extra_ms < 0:
        sys.exit("--ff-extra-ms must be >= 0")
    if legacy and ff_extra_ms > 0:
        sys.exit("--ff-extra-ms needs a phase mode (--phases-ms / --offset-seeds): "
                 "the legacy CSV schema has no column to record it")


def git_sha():
    """HEAD (short), suffixed '-dirty' when the tree the binary was built from
    has uncommitted changes — provenance for the CSV rows."""
    try:
        return subprocess.run(["git", "describe", "--always", "--dirty"],
                              capture_output=True, text=True,
                              cwd=BIN.parent.parent).stdout.strip()
    except OSError:
        return "unknown"


# ----------------------------------------------------------------------- one run
def build_cmd(zone, extra_ms, duration, profile, phase=None, ff_extra_ms=0.0):
    cmd = [str(BIN), "--headless", "--vehicles", "1", "--scheduler", "rm",
           "--exec", "worst", "--duration", str(duration), "--profile", profile,
           "--zone-target", str(zone), "--zone-extra-ms", str(extra_ms)]
    if ff_extra_ms > 0:
        # A2 instrument (PROOF_DRAFT §8.3): every F publish D ms later, the
        # feedforward staleness a contended schedule adds. The response is
        # binary at ~7.7 ms (the Estimator's second job then reads a
        # period-old F); the Merger reads a period-old F at every dose under
        # the N=1 RM order. PAPER_NOTES 2026-09-04 (b).
        cmd += ["--ff-extra-ms", f"{ff_extra_ms:g}"]
    if phase is not None:
        kind, val = phase
        if kind == "offset_ms":
            cmd += ["--start-offsets-ms", f"{val:g}"]
        elif kind == "seed":
            cmd += ["--offset-seed", str(int(val))]
        else:
            raise ValueError(f"unknown phase kind {kind!r}")
    return cmd


def run(zone, extra_ms, duration, profile="10", phase=None, ff_extra_ms=0.0):
    """Run one N=1 worst-case full-lap sim; return the parsed summary dict."""
    out = subprocess.run(build_cmd(zone, extra_ms, duration, profile, phase, ff_extra_ms),
                         capture_output=True, text=True).stdout
    r = parse_output(out)
    if r is None:
        sys.exit(f"parse failure (zone {zone}, +{extra_ms}ms, phase {phase}):\n{out}")
    return r


# ----------------------------------------------------------------------- sweep
@dataclass
class ZoneEntry:
    zone: int
    a_zone: object = None         # largest age hard-clean at EVERY phase, below first_breach
    first_breach: object = None   # (age, worst-phase hard list, worst phase) at the first any-phase breach
    per_phase_a: list = field(default_factory=list)   # per-phase largest hard-clean age (below first_breach)
    spread: object = None         # (min, max) of per_phase_a over phases that were ever clean
    clean_counts: dict = field(default_factory=dict)  # extra_ms -> phases hard-clean
    n_phases: int = 1
    a_soft: object = None         # largest age hard-clean AND soft% <= budget at every phase
    non_monotone: list = field(default_factory=list)  # extras with a clean phase ABOVE first_breach


def csv_header(phases, extra_cols=()):
    if phases == [None]:
        return ["zone", "zone_name", "extra_ms", "age_path_ms", "total_hard",
                "z0_hard", "z1_hard", "z2_hard", "z3_hard"]
    return (["zone", "zone_name", "extra_ms", "phase_kind", "phase", "age_path_ms",
             "total_hard", "z0_hard", "z1_hard", "z2_hard", "z3_hard", "soft_pct",
             "fleet_max_ey_m", "z0_max_ey_m", "z1_max_ey_m", "z2_max_ey_m",
             "z3_max_ey_m", "f_stale_max_ms"] + list(extra_cols))


def sweep(zones, grid, phases, runner, jobs=1, soft_budget=SOFT_BUDGET_PCT, log=None):
    """Run every (zone, extra, phase) cell through `runner(zone, extra, phase)`
    and aggregate. Returns (rows, [ZoneEntry per zone]); rows are in
    (zone, extra, phase-index) order regardless of `jobs`."""
    legacy = phases == [None]
    jobs_list = [(z, extra, pi) for z in zones for extra in grid
                 for pi in range(len(phases))]

    def cell(job):
        z, extra, pi = job
        r = runner(z, extra, phases[pi])
        if log:
            log(z, extra, phases[pi], r)
        return r

    if jobs > 1:
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            results = list(ex.map(cell, jobs_list))
    else:
        results = [cell(j) for j in jobs_list]
    by_key = dict(zip(jobs_list, results))

    rows, table = [], []
    for z in zones:
        e = ZoneEntry(zone=z, n_phases=len(phases),
                      per_phase_a=[None] * len(phases))
        phase_breached = [False] * len(phases)   # per-phase cliff already passed
        for extra in grid:
            cell_res = [by_key[(z, extra, pi)] for pi in range(len(phases))]
            for pi, r in enumerate(cell_res):
                total = sum(r["hard"])
                if legacy:
                    rows.append([z, ZONES[z], extra, r["age_path"], total, *r["hard"]])
                else:
                    kind, val = phases[pi]
                    rows.append([z, ZONES[z], extra, kind, val, r["age_path"], total,
                                 *r["hard"], r["soft_pct"], r["fleet_ey"], *r["zone_ey"],
                                 r["f_stale_max"]])
                # per-phase A = that phase's largest clean age below ITS OWN
                # first breach (the spread reports how much A varies by phase)
                if total == 0 and not phase_breached[pi]:
                    e.per_phase_a[pi] = r["age_path"]
                elif total > 0:
                    phase_breached[pi] = True
            n_clean = sum(1 for r in cell_res if sum(r["hard"]) == 0)
            e.clean_counts[extra] = n_clean
            age = max(r["age_path"] for r in cell_res)   # identical across phases
            if n_clean == len(phases):
                if e.first_breach is None:
                    e.a_zone = age                          # largest safe age below the cliff
                    if all(r["soft_pct"] <= soft_budget for r in cell_res):
                        e.a_soft = age
                else:
                    e.non_monotone.append(extra)            # clean island above a breach
            elif e.first_breach is None:
                wi = max(range(len(cell_res)), key=lambda i: sum(cell_res[i]["hard"]))
                e.first_breach = (age, cell_res[wi]["hard"],
                                  None if legacy else phases[wi][1])
        # spread is undefined if some phase never cleaned (its A lies below the
        # grid start) — reported as '-' rather than a misleading interval
        e.spread = (None if any(a is None for a in e.per_phase_a)
                    else (min(e.per_phase_a), max(e.per_phase_a)))
        table.append(e)
    return rows, table


# ----------------------------------------------------------------------- main
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
    ph = ap.add_mutually_exclusive_group()
    ph.add_argument("--phases-ms", default="",
                    help="min-over-phase: deterministic start offsets along the "
                         "lap, 'START:STOP:STEP' (STOP exclusive; the last tick "
                         "before STOP is always appended) or 'a,b,c' (ms). "
                         "'0:20:1' = one chain hyperperiod at 1 ms + 19.9 = the "
                         "axis of record.")
    ph.add_argument("--offset-seeds", default="",
                    help="min-over-phase via random LAP POSITIONS (--offset-seed; "
                         "'K' = seeds 1..K or 'a,b,c'): samples the chain phase "
                         "uniformly but also moves the start transient around "
                         "the track — the 2026-08-24 sampler, kept for "
                         "reproducibility; not the axis of record")
    ap.add_argument("--jobs", type=int, default=1,
                    help="parallel simulator processes (runs are independent)")
    ap.add_argument("--ff-extra-ms", type=float, default=0.0,
                    help="A2-corrected tables: delay every Feedforward publish "
                         "by D ms (the F lateness a contended schedule adds; "
                         "13.5 = the N=8 certificate, PROOF_DRAFT §8.3). Phase "
                         "mode only (recorded in the ff_extra_ms column).")
    ap.add_argument("--soft-budget", type=float, default=SOFT_BUDGET_PCT,
                    help="soft%% ceiling for the secondary A_soft (default 5.0 = "
                         "the Challenge's >= 95%% within 0.2 m)")
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
    if args.phases_ms:
        phases = [("offset_ms", v) for v in parse_phases(args.phases_ms)]
    elif args.offset_seeds:
        phases = [("seed", s) for s in parse_seeds(args.offset_seeds)]
    else:
        phases = [None]
    legacy = phases == [None]
    check_ff_extra(args.ff_extra_ms, legacy)
    sha = git_sha()

    def log(z, extra, phase, r):
        ph = "" if phase is None else f" {phase[0]}={phase[1]:<5}"
        print(f"  z{z} {ZONES[z]:<12} +{extra:<4}ms{ph}  age={r['age_path']:<8} "
              f"hard={sum(r['hard']):<4} soft={r['soft_pct']:.2f}% "
              f"maxEy={r['fleet_ey']:.4f}", flush=True)

    runner = lambda z, extra, phase: run(z, extra, args.duration, args.profile,
                                         phase, args.ff_extra_ms)
    rows, table = sweep(zones, grid, phases, runner, jobs=args.jobs,
                        soft_budget=args.soft_budget, log=log)

    extra_cols = () if legacy else ("profile", "duration_s", "git_sha", "ff_extra_ms")
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(csv_header(phases, extra_cols))
        for r in rows:
            w.writerow(r if legacy else
                       r + [args.profile, args.duration, sha, args.ff_extra_ms])

    if legacy:
        print("\n=== Causal A(zone) (largest delivered age with ZERO hard breaches) ===")
        print(f"  {'zone':<14} {'A(zone) ms':<12} {'first-breach age (where it landed)'}")
        for e in table:
            fb = e.first_breach
            fbtxt = "none in range" if fb is None else \
                f"{fb[0]} ms  [z0={fb[1][0]} z1={fb[1][1]} z2={fb[1][2]} z3={fb[1][3]}]"
            print(f"  z{e.zone} {ZONES[e.zone]:<12} {str(e.a_zone):<12} {fbtxt}")
    else:
        kind = phases[0][0]
        vals = [p[1] for p in phases]
        ff = f"; F publish delayed {args.ff_extra_ms:g} ms (A2)" if args.ff_extra_ms > 0 else ""
        print(f"\n=== Causal A(zone), MIN OVER PHASE ({len(phases)} phases, {kind} "
              f"{vals[0]:g}..{vals[-1]:g}; hard-clean at EVERY phase{ff}) ===")
        print(f"  {'zone':<14} {'A(zone) ms':<12} {'per-phase A':<16} "
              f"{'A_soft ms':<11} first any-phase breach (worst phase)")
        for e in table:
            fb = e.first_breach
            fbtxt = "none in range" if fb is None else \
                (f"{fb[0]} ms [z0={fb[1][0]} z1={fb[1][1]} z2={fb[1][2]} z3={fb[1][3]}]"
                 f" at {kind}={fb[2]:g}")
            sp = "-" if e.spread is None else f"{e.spread[0]:g}..{e.spread[1]:g}"
            print(f"  z{e.zone} {ZONES[e.zone]:<12} {str(e.a_zone):<12} {sp:<16} "
                  f"{str(e.a_soft):<11} {fbtxt}")
            counts = " ".join(f"+{x}:{c}/{e.n_phases}" for x, c in e.clean_counts.items())
            print(f"     clean phases per grid point: {counts}")
            if e.non_monotone:
                print(f"     NON-MONOTONE: clean at every phase ABOVE the first breach at "
                      f"extra {e.non_monotone} — not counted as A(zone); investigate")
        print(f"  (A_soft = hard-clean AND soft% <= {args.soft_budget:g} at every phase; "
              f"the committed A(zone) tables are hard-only)")
    print(f"\n  wrote {args.out} (git {sha})")


if __name__ == "__main__":
    main()
