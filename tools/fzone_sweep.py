#!/usr/bin/env python3
"""FCHANNEL A_F / A_B sweep (FCHANNEL.md §5).

For each zone, suppress the chosen channel's publishes ONLY while the car is
in that zone (--fzone-target/--fzone-hold-ms or --bzone-*) and bracket the
largest sustained hold with ZERO hard breaches anywhere on the lap
(breach-anywhere criterion, same standard as zone_sweep.py / A(zone)).

Council discipline (FCHANNEL §8 items 3-4, C-O13): every row carries BOTH the
commanded dose and the DELIVERED dose (the harness's measured in-zone max
F/B staleness), the undecimated max-|e_y| margins, per-zone hard counts,
per-kind missed jobs, full run identity (scheduler/profile/N/cores/exec/
duration/decimation), and the git SHA of the binary's tree. A_F is reported
as a pass/breach BRACKET, never a point (A-m14). Cells whose delivered dose
diverges from the commanded dose by more than one channel period are marked
CENSORED (arc-residency truncation, C-O5).

Usage: python3 tools/fzone_sweep.py [--channel f|b] [--zones 0,1,2,3]
         [--grid 100,200,...] [--duration 120] [--profile 10]
         [--out fzone_tolerance.csv] [--force]
"""
import argparse, csv, re, subprocess, sys
from pathlib import Path

BIN = Path(__file__).resolve().parent.parent / "build" / "cps"
ZONES = {0: "straight", 1: "slight-turn", 2: "sharp-turn", 3: "lane-change"}
PERIOD_MS = 20.0  # F and B publish period (challenge task set)

AGE_RE = re.compile(r"([0-9.]+) ms \(path\)")
HARD_RE = re.compile(r"hard z0=(\d+) z1=(\d+) z2=(\d+) z3=(\d+)")
EY_RE = re.compile(r"max \|e_y\| \(per-tick\): fleet ([0-9.]+) m .*\| zones "
                   r"([0-9.]+) ([0-9.]+) ([0-9.]+) ([0-9.]+)")
FST_RE = re.compile(r"F staleness \(act-stamped, ms\): zone max "
                    r"([0-9.]+) ([0-9.]+) ([0-9.]+) ([0-9.]+)")
MISS_RE = re.compile(r"missed by kind: E=(\d+) B=(\d+) F=(\d+) M=(\d+)")


def git_sha():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True,
                              cwd=BIN.parent.parent).stdout.strip()
    except OSError:
        return "unknown"


def run(channel, zone, hold_ms, args, lead_ms=0.0):
    cmd = [str(BIN), "--headless", "--vehicles", str(args.vehicles),
           "--scheduler", args.scheduler, "--exec", "worst",
           "--duration", str(args.duration), "--profile", args.profile]
    if channel == "f":
        cmd += ["--fzone-target", str(zone), "--fzone-hold-ms", str(hold_ms)]
        if lead_ms > 0:
            cmd += ["--fzone-lead-ms", str(lead_ms)]
    else:
        cmd += ["--bzone-target", str(zone), "--bzone-hold-ms", str(hold_ms)]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    age, hard = AGE_RE.search(out), HARD_RE.search(out)
    ey, fst = EY_RE.search(out), FST_RE.search(out)
    miss = MISS_RE.search(out)
    if age is None or hard is None or ey is None or fst is None or miss is None:
        sys.exit(f"parse failure ({channel}-zone {zone}, hold {hold_ms}ms):\n{out}")
    return {
        "age_path": float(age.group(1)),
        "hard": [int(hard.group(i)) for i in range(1, 5)],
        "fleet_ey": float(ey.group(1)),
        "zone_ey": [float(ey.group(i)) for i in range(2, 6)],
        # Delivered F staleness per zone. For channel b the harness has no
        # B-staleness line yet; the delivered dose is visible in age_path
        # instead (B is a stamped channel) — recorded via age_path column.
        "fst": [float(fst.group(i)) for i in range(1, 5)],
        "miss": [int(miss.group(i)) for i in range(1, 5)],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="f", choices=["f", "b"])
    ap.add_argument("--zones", default="0,1,2,3")
    ap.add_argument("--grid", default="100,200,300,400,500,800,1200",
                    help="comma list of hold doses (ms); refine at cliffs with "
                         "20 ms steps (realizable set: multiples of the 20 ms "
                         "period plus a sub-period remainder)")
    ap.add_argument("--duration", type=int, default=120)
    ap.add_argument("--profile", default="10", choices=["10", "12.5", "15"])
    ap.add_argument("--scheduler", default="rm")
    ap.add_argument("--vehicles", type=int, default=1)
    ap.add_argument("--lead-fracs", default="",
                    help="enter-stale phase battery (FCHANNEL §8 item 8; "
                         "channel f, named zone only): comma list of entry "
                         "phases as fractions of each dose (e.g. "
                         "'0,0.25,0.5,0.75'; lead = frac*D via "
                         "--fzone-lead-ms). Empty (default) = enter-fresh "
                         "only, legacy CSV schema. A_F is then reported as "
                         "the MIN over phases per zone.")
    ap.add_argument("--out", default="fzone_tolerance.csv")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if not BIN.exists():
        sys.exit(f"build first: {BIN} not found")
    if Path(args.out).exists() and not args.force:
        sys.exit(f"refusing to overwrite existing {args.out}; pass --force or --out PATH")

    fracs = ([float(x) for x in args.lead_fracs.split(",")]
             if args.lead_fracs else [])
    if fracs and args.channel != "f":
        sys.exit("--lead-fracs is an F-channel (enter-stale) mode")

    sha = git_sha()
    grid = [float(g) for g in args.grid.split(",")]
    zones = [int(z) for z in args.zones.split(",")]
    rows, table = [], []
    for z in zones:
        last_clean, first_breach = None, None
        for d in grid:
            # Enter-stale battery: every phase at this dose; a dose is clean
            # only if EVERY entry phase is clean (A_F = min over phase,
            # FCHANNEL §8 item 8). Legacy mode = the single enter-fresh arm.
            dose_clean, dose_breach = True, False
            for frac in (fracs or [0.0]):
                lead = frac * d
                r = run(args.channel, z, d, args, lead_ms=lead)
                delivered = r["fst"][z]
                censored = (args.channel == "f" and
                            abs(delivered - d) > PERIOD_MS + 3.0)
                total = sum(r["hard"])
                row = [args.channel, z, ZONES[z], d]
                if fracs:
                    row += [frac, lead]
                row += [delivered, "CENSORED" if censored else "ok",
                        r["age_path"], r["fleet_ey"], r["zone_ey"][z], total,
                        *r["hard"], *r["miss"], args.scheduler, args.profile,
                        args.vehicles, 3, "worst", args.duration, 10, sha]
                rows.append(row)
                dose_clean = dose_clean and total == 0 and not censored
                dose_breach = dose_breach or total > 0
                ph = f" phase={frac:.2f}" if fracs else ""
                print(f"  {args.channel}-z{z} {ZONES[z]:<12} hold={d:<6.0f}"
                      f"{ph} delivered={delivered:<7.1f} hard={total:<4} "
                      f"maxEy={r['fleet_ey']:.3f}"
                      f"{' CENSORED' if censored else ''}")
            if dose_clean:
                last_clean = d
            elif dose_breach and first_breach is None:
                first_breach = d
        table.append((z, last_clean, first_breach))

    header = ["channel", "zone", "zone_name", "hold_ms_commanded"]
    if fracs:
        header += ["lead_frac", "lead_ms"]
    header += ["delivered_max_ms", "dose_status", "age_path_ms",
               "fleet_max_ey_m", "target_zone_max_ey_m", "total_hard",
               "z0_hard", "z1_hard", "z2_hard", "z3_hard",
               "missed_E", "missed_B", "missed_F", "missed_M",
               "scheduler", "profile", "vehicles", "cores", "exec",
               "duration_s", "decimation_ms", "git_sha"]
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

    ch = "A_F" if args.channel == "f" else "A_B"
    over = " (min over entry phases)" if fracs else ""
    print(f"\n=== {ch}(zone) brackets{over} (largest clean sustained hold, "
          f"breach-anywhere criterion) ===")
    for z, lc, fb in table:
        print(f"  z{z} {ZONES[z]:<12} clean through {lc} ms; "
              f"first breach at {fb} ms"
              if fb else f"  z{z} {ZONES[z]:<12} clean through {lc} ms "
                         f"(no breach in range)")
    print(f"\n  wrote {args.out} (git {sha})")


if __name__ == "__main__":
    main()
