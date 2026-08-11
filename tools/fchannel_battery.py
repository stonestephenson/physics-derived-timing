#!/usr/bin/env python3
"""FCHANNEL capacity/coupling battery -> committed CSVs (FCHANNEL.md §9.7/§9.8/§9.2).

Formalizes the raw-log batteries under fchannel_rawlogs/ into self-describing
CSVs (the §10 queue item): every row carries the full commanded config, the
per-zone hard AND soft breach counts (parse only the hard block for capacity —
the §9.7 analysis-erratum), undecimated max-|e_y| margins, per-kind missed
jobs, and the git SHA of the binary's tree. Deterministic: --exec worst +
seeded offset draws, so re-runs are byte-stable and rows can be diffed against
the raw logs line-by-line.

Modes (positional; default: all):
  pclean       P(clean) capacity distribution: {unspaced, F_spaced s=1 s,
               s=4 s} x {frontier-honest m100, aguard-honest m80} x N x seeds
               201-210, 120 s -> pclean_battery.csv  (§9.7)
  tuning       N=20 fairness grid: floor {60,100,140} x guard-cap
               {450,700,1000} x seeds 101-103, both schedulers
               -> tuning_grid_n20.csv  (§9.7)
  attribution  {allocation} x {F economics} capacity cells, default spread
               -> attribution_matrix.csv  (§9.8; RM-alloc cell via
               CPS_FRONTIER_RM_ALLOC)
  coupling     uniform B-hold x z3 F-hold grid at N=1 (the §9.2 coupling
               surface + the A_B uniform cliff rows) -> coupling_grid.csv

Cost note: the full pclean battery is ~280 x 120 s honest runs (~2 h serial);
use --jobs (runs are independent + deterministic, so parallel is safe).
"""
import argparse
import concurrent.futures as cf
import csv
import os
import re
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "build" / "cps"

AGE_RE = re.compile(r"([0-9.]+) ms \(path\)")
HARD_RE = re.compile(r"hard z0=(\d+) z1=(\d+) z2=(\d+) z3=(\d+)")
SOFT_RE = re.compile(r"soft z0=(\d+) z1=(\d+) z2=(\d+) z3=(\d+)")
EY_RE = re.compile(r"max \|e_y\| \(per-tick\): fleet ([0-9.]+) m "
                   r"\(margin (-?[0-9.]+) m to 0.8\)")
FST_RE = re.compile(r"F staleness \(act-stamped, ms\): zone max "
                    r"([0-9.]+) ([0-9.]+) ([0-9.]+) ([0-9.]+)")
MISS_RE = re.compile(r"missed by kind: E=(\d+) B=(\d+) F=(\d+) M=(\d+)")
MISSED_JOBS_RE = re.compile(r"missed jobs: (\d+)")

SEEDS_PCLEAN = list(range(201, 211))
SEEDS_TUNING = [101, 102, 103]
# family -> (min_spacing_ms, N grid) — the recorded §9.7 battery dimensions.
PCLEAN_FAMILIES = {
    "unspaced":      (0,    [12, 14, 16, 18, 20]),
    "fspaced_s1000": (1000, [14, 16, 18, 20, 22]),
    "fspaced_s4000": (4000, [14, 16, 18, 20]),
}
# The two honest configs of record (floor stays at its 100 ms default).
HONEST = [("frontier", "frontier-honest", 100), ("aguard", "aguard-honest", 80)]

RESULT_COLS = ["hard_z0", "hard_z1", "hard_z2", "hard_z3", "total_hard",
               "clean", "soft_z0", "soft_z1", "soft_z2", "soft_z3",
               "fleet_max_ey_m", "ey_margin_m", "age_path_ms",
               "missed_E", "missed_B", "missed_F", "missed_M", "missed_jobs"]
ID_COLS = ["profile", "cores", "exec", "duration_s", "git_sha"]


def git_sha():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True,
                              cwd=BIN.parent.parent).stdout.strip()
    except OSError:
        return "unknown"


def run_cell(cmd, env_extra=None):
    """Run one sim; return the parsed result-column dict."""
    env = dict(os.environ, **(env_extra or {}))
    out = subprocess.run([str(BIN)] + cmd, capture_output=True, text=True,
                         env=env).stdout
    age, hard, soft = AGE_RE.search(out), HARD_RE.search(out), SOFT_RE.search(out)
    ey, miss = EY_RE.search(out), MISS_RE.search(out)
    mj = MISSED_JOBS_RE.search(out)
    fst = FST_RE.search(out)
    if (age is None or hard is None or soft is None or ey is None
            or miss is None or mj is None):
        sys.exit("parse failure for: %s\n%s" % (" ".join(cmd), out[-2000:]))
    hard_v = [int(hard.group(i)) for i in range(1, 5)]
    r: dict = dict(zip(["hard_z0", "hard_z1", "hard_z2", "hard_z3"], hard_v))
    r["total_hard"] = sum(hard_v)
    r["clean"] = int(r["total_hard"] == 0)
    r.update(zip(["soft_z0", "soft_z1", "soft_z2", "soft_z3"],
                 [int(soft.group(i)) for i in range(1, 5)]))
    r["fleet_max_ey_m"] = float(ey.group(1))
    r["ey_margin_m"] = float(ey.group(2))
    r["age_path_ms"] = float(age.group(1))
    r.update(zip(["missed_E", "missed_B", "missed_F", "missed_M"],
                 [int(miss.group(i)) for i in range(1, 5)]))
    r["missed_jobs"] = int(mj.group(1))
    # Delivered F staleness (per-zone max) — coupling mode records z3's.
    r["_fst"] = [float(fst.group(i)) for i in range(1, 5)] if fst else None
    return r


def base_cmd(scheduler, vehicles, duration, margin=None, floor=None,
             guard_cap=None, offset_seed=None, min_spacing=None, extra=()):
    cmd = ["--headless", "--vehicles", str(vehicles), "--scheduler", scheduler,
           "--exec", "worst", "--duration", str(duration)]
    if margin is not None:      cmd += ["--pred-margin", str(margin)]
    if floor is not None:       cmd += ["--floor", str(floor)]
    if guard_cap is not None:   cmd += ["--guard-cap", str(guard_cap)]
    if offset_seed is not None: cmd += ["--offset-seed", str(offset_seed)]
    if min_spacing:             cmd += ["--min-spacing", str(min_spacing)]
    return cmd + list(extra)


def run_grid(cells, jobs):
    """cells: list of (key_dict, cmd, env). Returns rows in submission order."""
    results: list = [None] * len(cells)

    def work(i):
        key, cmd, env = cells[i]
        r = run_cell(cmd, env)
        label = " ".join("%s=%s" % kv for kv in key.items())
        print("  %-64s hard=%-6d clean=%d maxEy=%.4f"
              % (label, r["total_hard"], r["clean"], r["fleet_max_ey_m"]),
              flush=True)
        return r

    with cf.ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = {ex.submit(work, i): i for i in range(len(cells))}
        for f in cf.as_completed(futs):
            results[futs[f]] = f.result()
    return results


def write_rows(path, lead_cols, rows, force):
    if path.exists() and not force:
        sys.exit("refusing to overwrite %s; pass --force" % path)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(lead_cols + RESULT_COLS + ID_COLS)
        w.writerows(rows)
    print("  wrote %s (%d rows)" % (path, len(rows)))


def result_cols(r):
    return [r[c] for c in RESULT_COLS]


# ---------------------------------------------------------------------- modes
def mode_pclean(args, ident):
    fams = PCLEAN_FAMILIES if not args.quick else {"unspaced": (0, [6])}
    seeds = SEEDS_PCLEAN if not args.quick else SEEDS_PCLEAN[:2]
    cells = []
    for fam, (spacing, ns) in fams.items():
        for short, sched, margin in HONEST:
            for n in ns:
                for s in seeds:
                    key = {"fam": fam, "sched": short, "N": n, "seed": s}
                    cells.append((key,
                                  base_cmd(sched, n, args.duration,
                                           margin=margin, offset_seed=s,
                                           min_spacing=spacing), None))
    res = run_grid(cells, args.jobs)
    rows = [[k["fam"], PCLEAN_FAMILIES.get(k["fam"], (0,))[0], k["sched"],
             dict((h[0], h[2]) for h in HONEST)[k["sched"]], k["N"], k["seed"]]
            + result_cols(r) + ident
            for (k, _, _), r in zip(cells, res)]
    write_rows(Path(args.out_dir) / "pclean_battery.csv",
               ["family", "min_spacing_ms", "scheduler", "pred_margin_ms",
                "vehicles", "offset_seed"], rows, args.force)
    # The §9.7 headline table: P(clean) out of the seed draws.
    print("\n== P(clean) per (family, scheduler, N) ==")
    agg = {}
    for (k, _, _), r in zip(cells, res):
        agg.setdefault((k["fam"], k["sched"], k["N"]), []).append(r["clean"])
    for fam in fams:
        for short, _, _ in HONEST:
            ns = sorted(n for (f, s, n) in agg if f == fam and s == short)
            marks = ["N=%d:%d/%d" % (n, sum(agg[(fam, short, n)]),
                                     len(agg[(fam, short, n)])) for n in ns]
            print("  %-14s %-9s %s" % (fam, short, "  ".join(marks)))


def mode_tuning(args, ident):
    floors = [60, 100, 140] if not args.quick else [100]
    caps = [450, 700, 1000] if not args.quick else [450]
    seeds = SEEDS_TUNING if not args.quick else SEEDS_TUNING[:1]
    n = 20 if not args.quick else 6
    cells = []
    for fl in floors:
        for cap in caps:
            for s in seeds:
                for short, sched, margin in HONEST:
                    key = {"sched": short, "floor": fl, "cap": cap, "seed": s}
                    cells.append((key,
                                  base_cmd(sched, n, args.duration,
                                           margin=margin, floor=fl,
                                           guard_cap=cap, offset_seed=s), None))
    res = run_grid(cells, args.jobs)
    rows = [[k["sched"], dict((h[0], h[2]) for h in HONEST)[k["sched"]], n,
             k["floor"], k["cap"], k["seed"]] + result_cols(r) + ident
            for (k, _, _), r in zip(cells, res)]
    write_rows(Path(args.out_dir) / "tuning_grid_n20.csv",
               ["scheduler", "pred_margin_ms", "vehicles", "floor_ms",
                "guard_cap_ms", "offset_seed"], rows, args.force)


# §9.8 attribution cells: cell -> (scheduler, margin, env, N grid).
ATTRIBUTION_CELLS = [
    ("rm_alloc_no_f",  "rm",              None, None, [10, 11, 12]),
    ("rm_alloc_frules", "frontier-honest", 100,
     {"CPS_FRONTIER_RM_ALLOC": "1"}, [12, 14, 16, 19, 21]),
    ("triage_no_f",    "aguard-honest",   80,  None, [18, 19, 20]),
    ("triage_frules",  "frontier-honest", 100, None, [20, 21, 22]),
]


def mode_attribution(args, ident):
    cells = []
    for cell, sched, margin, env, ns in ATTRIBUTION_CELLS:
        for n in (ns if not args.quick else ns[:1]):
            key = {"cell": cell, "N": n}
            cells.append((key, base_cmd(sched, n, args.duration,
                                        margin=margin), env))
    res = run_grid(cells, args.jobs)
    by_cell = dict((c[0], c) for c in ATTRIBUTION_CELLS)
    rows = []
    for (k, _, _), r in zip(cells, res):
        cell, sched, margin, env, _ = by_cell[k["cell"]]
        rows.append([cell, sched, margin if margin is not None else "",
                     1 if env else 0, k["N"]] + result_cols(r) + ident)
    write_rows(Path(args.out_dir) / "attribution_matrix.csv",
               ["cell", "scheduler", "pred_margin_ms", "rm_alloc_env",
                "vehicles"], rows, args.force)


# §9.2 coupling grid: uniform B-hold x z3-targeted F-hold (the recorded cells:
# the 4x4 surface + the A_B uniform cliff rows at fz=0).
COUPLING_BZ = [0, 100, 200, 300]
COUPLING_FZ = [0, 150, 200, 240]
COUPLING_CLIFF_BZ = [400, 600, 800]


def mode_coupling(args, ident):
    pairs = [(bz, fz) for bz in COUPLING_BZ for fz in COUPLING_FZ]
    pairs += [(bz, 0) for bz in COUPLING_CLIFF_BZ]
    if args.quick:
        pairs = pairs[:2]
    cells = []
    for bz, fz in pairs:
        extra = []
        if bz: extra += ["--bzone-target", "-1", "--bzone-hold-ms", str(bz)]
        if fz: extra += ["--fzone-target", "3", "--fzone-hold-ms", str(fz)]
        key = {"bz": bz, "fz": fz}
        cells.append((key, base_cmd("rm", 1, args.duration, extra=extra), None))
    res = run_grid(cells, args.jobs)
    rows = [[k["bz"], k["fz"], r["_fst"][3] if r["_fst"] else ""]
            + result_cols(r) + ident
            for (k, _, _), r in zip(cells, res)]
    write_rows(Path(args.out_dir) / "coupling_grid.csv",
               ["bz_hold_ms_uniform", "fz_hold_ms_z3", "delivered_fz3_max_ms"],
               rows, args.force)


MODES = {"pclean": mode_pclean, "tuning": mode_tuning,
         "attribution": mode_attribution, "coupling": mode_coupling}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("modes", nargs="*", default=[],
                    help="subset of %s (default: all)" % ", ".join(MODES))
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--duration", type=int, default=120)
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--quick", action="store_true",
                    help="tiny smoke grids (never commit these CSVs)")
    args = ap.parse_args()
    if not BIN.exists():
        sys.exit("build first: %s not found" % BIN)
    names = args.modes or list(MODES)
    bad = [m for m in names if m not in MODES]
    if bad:
        sys.exit("unknown mode(s): %s (known: %s)" % (bad, ", ".join(MODES)))
    if args.quick:
        args.duration = min(args.duration, 30)
    ident = ["10", 3, "worst", args.duration, git_sha()]
    for m in names:
        print("== %s ==" % m, flush=True)
        MODES[m](args, ident)


if __name__ == "__main__":
    main()
