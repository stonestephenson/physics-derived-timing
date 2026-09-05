# CPS Challenge Visualizer — Usage

A plug-and-play harness + raylib visualizer for the Bosch RTAS 2026
Physics-Driven Real-Time CPS Challenge. It drives the `LateralMotionControl` FMU
for N vehicles sharing `N_cores` cloud cores under a scheduling policy you choose,
records the run, and shows the cars lapping the track — the reference path, the
actual driven path, the lateral error, and where a car breaches its bounds.

The FMU itself is documented in
[`LateralMotionControl/FMU_README.md`](LateralMotionControl/FMU_README.md); the task/network/metric
parameters are in [`examples/`](examples).

\1\n> Python side: every `tools/*.py` script is standard-library only (Python 3.10+; 3.14 verified) — nothing to `pip install`.\n> **Unknown arguments are accepted silently** by `./build/cps` (`--scheduler nosuch` runs RateMonotonic and\n> prints its name; `--bogus-flag` is ignored) — check the printed `scheduler:` line of every run you rely on\n> (flagged by the 2026-09-05 audit; HANDOFF NOW lists it as a code item for Stone).\n\n
Requires CMake ≥ 3.16 and a C++17 compiler. raylib is fetched and built
automatically the first time you configure (needs network once).

```sh
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
```

The executable is `build/cps`.

**Platform support.** The FMU ships prebuilt binaries for **`darwin64` (macOS) and
`win64` (Windows) only** (`LateralMotionControl/binaries/` — there is **no `linux64`**).
CMake bakes the platform dylib path at configure time, so on Linux the build configures
and compiles fine but **`--plant lateral` fails at runtime** (the FMU can't load);
**`--plant cartpole` works on Linux** (pure C++, no FMU). On Linux, raylib's fetch also
needs the usual GL/X11 dev headers.

## Run

```sh
# Live visualization (opens a window). Defaults: RateMonotonic, 1 vehicle, v=10.
./build/cps

# Multiple vehicles sharing 3 cloud cores, context-aware scheduler:
./build/cps --vehicles 6 --scheduler context

# A different plant (inverted pendulum) on the same scheduler/age machinery:
./build/cps --headless --plant cartpole --vehicles 8 --scheduler aguard

# Headless (no window): run fast and print per-vehicle metrics.
./build/cps --headless --vehicles 6 --scheduler rm --duration 120

# Save a run, then replay/scrub it later without re-simulating:
./build/cps --headless --vehicles 4 --save run.cpsr
./build/cps --replay run.cpsr
```

Key options: `--scheduler rm|prm|edf|context|honest|ttu|hybrid|aguard|ttu-honest|
hybrid-honest|aguard-honest|zband|frontier|frontier-honest|eskip` (`frontier` =
aguard's allocation + zone-aware F economics, `eskip` = the RM + E-decimation
instrument — both FCHANNEL.md; `zband` = the PROOF_DRAFT §3.1 proof-object
zone-band scheduler ZB-F-X: job priority (band, period, vehicle, kind) with the band
stamped at release — band 0 iff the car is within ±240 ms of a z3 arc and the kind is
E/B/M; F never elevates; prediction-free; equals rm when nothing is flagged; the ±240 ms
θ is `kZbFlagTicks` in `src/sim/Simulation.cpp` — constexpr, no CLI knob, coupled to the
band-RTA inflation constant per PROOF_DRAFT §3.2), `--plant
lateral|cartpole` (controlled system: lateral = Bosch FMU car, cartpole = inverted
pendulum — see `GENERALIZATION.md`), `--vehicles N`,
`--cores N`, `--profile 10|12.5|15`, `--duration SEC`,
`--exec avg|worst|best|pert`, `--overrun kill|skip`, `--net-delay MS` (fix
both network delays, for delay-tolerance sweeps), `--delta-max RAD`,
`--u-max N`/`--shove-force N`/`--theta-max RAD` (cart-pole actuator limit /
disturbance / hard-angle overrides; defaults are the calibrated `CartPoleParams`,
see `GENERALIZATION.md §4`; the `--validate-predictor` summary prints an "actuator
calibration aid" with the observed demand for re-deriving `--u-max`) +
`--triage` + `--guard MS` + `--floor MS` + `--tau-crit MS` + `--pred-staleness MS`
+ `--pred-margin MS` + `--validate-predictor` (prediction system, see PREDICTOR.md;
`--tau-crit` = simultaneous-criticality threshold §5d (default 100; the sim-crit
summary line + CSV cols `tau_crit_ms,max_sim_crit,sim_crit_over_cores_pct` are
always reported, not opt-in); `--danger-tau FRAC` = danger-relative criticality
(lateral; default 1.0): a car is "in danger" when delivered age_path ≥ FRAC·A(zone of
the car now), unioned with TTPNR<tau-crit; reports K_age/K + a K(τ) curve + CSV cols
`danger_tau,max_k_age,max_k_danger` (THE PLAN leg 4 / PREDICTOR §5d / THEOREM_BRIEF §3.6);
`--pack-zone Z` + `--min-spacing MS` = worst-case zone occupancy (lateral; THE PLAN leg 2):
pack zone Z's arcs (3 = binding lane-change) at the F_spaced minimum inter-car gap MS and
report max simultaneous Occ vs ceil(zone_len/spacing) + CSV cols
`pack_zone,min_spacing_ms,max_occ_packed` (off by default; `tools/occupancy_sweep.py`;
THEOREM_BRIEF §3.5); `--align-offsets FRAC` aligns vehicle start phases for
the leg-(A) simultaneity experiment (lateral only; 0 = even spread default, 1 = all
cars on one lap phase = adversarial worst case; PAPER_NOTES 2026-06-25); `--pred-staleness`/
`--pred-margin` = honest-predictor delayed-state age + safety margin §5e;
FCHANNEL instruments (all off by default -> byte-identical; FCHANNEL.md §4/§9,
`tools/fzone_sweep.py`): `--fzone-target Z --fzone-hold-ms D` = zone-gated F
publish suppression (the A_F dose; Z=-1 all zones); `--fzone-lead-ms L` =
enter-stale arm (pre-arm the hold within L ms BEFORE the named target zone, so
the car enters with an already-aged value at matched peak dose; entry age
~= min(L, D); FCHANNEL §9.9); `--bzone-target/--bzone-hold-ms`
= the Controller twin (A_B; visible to age_path); `--qzone-target/--qzone-eps` =
zero-age reference error in q (collapse experiment, signed;
`tools/qzone_sweep.py`); `--offset-seed N` = random
start-phase draw (with `--min-spacing MS` = F_spaced-constrained draw; capacity
as P(clean) over seeds); `--start-offsets-ms A[,B,..]` = explicit per-vehicle
start offsets along the lap (ms of trajectory time, one per `--vehicles`;
overrides every other placement; the phase-enumeration lever behind
`tools/zone_sweep.py --phases-ms` — A(zone) is a min over the 20 ms chain
phase, PAPER_NOTES 2026-09-04); `--zone-consts S,F,D,W,P,B` = override the
six zone-partition constants (sharp-turn |ff0| threshold, lane-change seed
thresholds |ff1| and curvature range, lane-change window/pad/bridge in ms;
defaults 0.0215,0.0035,0.0040,50,100,350 = byte-identical; the
partition-sensitivity instrument behind `tools/zone_sensitivity.py`,
PAPER_NOTES 2026-09-04 (d)); `--guard-cap MS` = the aguard/frontier theta clamp
(default 450; proven inert for honest configs; the full guard formula is
PER VEHICLE, theta_v = min(cap, floor + max(60, v.age_recent_ms)) — the 60 ms
inner floor is fixed in code, `AdaptiveGuard.cpp`/`Frontier.cpp`; the older
fleet-max form was the bug that made `--floor` inert, HANDOFF §4 Finding A). NOTE `--ff-extra-ms` clamps at
one F period (FCHANNEL §3 erratum) — use `--fzone-hold-ms` for real F doses.
`--zone-target Z --zone-extra-ms D` = the Phase-2 CAUSAL A(zone) instrument (inject D ms
of extra command delay only while the car is in zone Z; every A(zone) table comes from it,
`tools/zone_sweep.py`; ZONE_TOLERANCE.md);
`--zone-extra-vector A,B,C,D` = envelope experiment (PROOF_DRAFT §8.2): per-zone extra
netCA delay (ms) {z0,z1,z2,z3} applied by each car's current zone, overriding
`--zone-target`; `--zone-flag-window MS` uses the z3 entry whenever the car is within
±MS of a z3 arc (ZB-F-X flag emulation); `--ff-extra-ms D` = A2 experiment (PROOF_DRAFT
§8.3): delay every Feedforward publish by D ms, clamped before F's next release —
age_path untouched by construction, 0 = off)
`--seed N`, `--headless`, `--csv FILE` (append per-vehicle summary rows for
sweeps), `--save FILE`, `--replay FILE`, `--screenshot FILE` with
`--screenshot-at N`, `--select N`, `--speed X` (aim scripted screenshots).
NOTE `--screenshot FILE`: raylib writes the BASENAME into the process working
directory — directory components of FILE are silently ignored, so `cd` to the
target dir (or move the file after) when scripting figures.
THIS section is the flag reference of record (`./build/cps --help` prints a
summary that has lagged it before — trust USAGE). Env-var knobs (no CLI):
`CPS_FRONTIER_FHB_MS` (straight-zone F heartbeat, default 500),
`CPS_FRONTIER_FHB_CRIT_MS` (critical-section heartbeat, default 100),
`CPS_FRONTIER_NO_FDEMOTE` (ablation: byte-identical to aguard),
`CPS_FRONTIER_RM_ALLOC` (attribution matrix: RM keys + F rules),
`CPS_ESKIP_K` (eskip's E-decimation factor, default 11). All in
`src/sched/policies/{Frontier,EskipProbe}.cpp`; FCHANNEL.md §8/§9.

Fixed-priority policies use the strict total order (period, vehicle, kind) —
deterministic across platforms and exactly the model BOUND.md §7 analyzes.
`ttu` is the predictive scheduler (ranks on time-to-point-of-no-return from
held-command plant rollouts); `hybrid` wraps ttu's safety guard (`--guard MS`)
around `context`'s comfort ranking — guard→0 is context, guard→∞ is ttu;
`aguard` self-tunes that guard from the live measured round-trip
(`--floor MS` = target safety margin) and tie-breaks emergencies by rescue
clearance. The `ttu-honest`/`hybrid-honest`/`aguard-honest` twins run the same
rules on a rollout from the cloud's delayed state instead of true state
(`--pred-staleness`, +`--pred-margin`); see PREDICTOR.md §5e. The
visualizer shows the selected car's
predicted path as a dotted line with 0.8 m-crossing and point-of-no-return
markers, live and in replays (recording format v5; v2–v4 still load). With
`--plant cartpole` the replay renders a **different, dedicated view** — see
"The cart-pole view" below.

Scheduler notes: `context` scores on ground-truth metrics (an **oracle** upper
bound); `honest` is the same scoring restricted to the estimator-derived remote
metrics the cloud legitimately sees; `prm` is partitioned RM (`vehicle %
nCores`, no migration). `--overrun kill` (default) is kill-and-hold: an
unfinished job is dropped at its next release and the output register holds;
`skip` lets the overrunning job finish while skipping passed releases. The
metrics table prints two worst-case data ages per vehicle: `age_fresh`
(freshest-contributing convention) and `age_path` (oldest-direct / classical
chain path — the one BOUND.md targets); see DATA_AGE.md §4d.

### Visualizer controls

| Key | Action | Key | Action |
| --- | --- | --- | --- |
| `Space` | play / pause | `[` `]` | select previous / next vehicle |
| `←` `→` | scrub / step (replay) | `F` | follow selected car / overview |
| `↑` `↓` | playback speed | `wheel` | zoom |
| `,` `.` | error exaggeration | `H` | toggle help |

The track shows the **gray centerline** (expected path), **yellow ±0.2 m** soft
(comfort) bounds and **red ±0.8 m** hard (safety) bounds. The driven path is
offset from the centerline by the lateral error, exaggerated (default ×25) so
it's visible, and colored green→red by error magnitude. Hard breaches are marked
red on the track and on the timeline so you can jump straight to them.

### The cart-pole view (`--plant cartpole`)

A cart-pole recording (format v5) replays as a **separate** view, not the track:
a cart on a horizontal rail with a pole hinged at θ, the **±θ_soft / ±θ_hard angle
rays** (the lane-ring analogue), the held-command prediction in angle space (a
dashed held-θ tip trajectory + **ghost poles** at the predicted TTV / point-of-no-
return angles), a θ-vs-time strip with periodic-shove bands, and a fleet row of
per-vehicle θ ticks. The controls above apply unchanged. Architecture + caveats:
`GENERALIZATION.md §6`. View one:

    ./build/cps --headless --plant cartpole --vehicles 16 --scheduler rm \
        --exec worst --duration 20 --save /tmp/cp.cpsr
    ./build/cps --replay /tmp/cp.cpsr      # ] cycles cars; veh 0–6 recover, 7–15 fall

There is **no numeric gate** for this view (the cart-pole predictor skips
`--validate-predictor`), so it is checked by eye — two things to expect:
- markers are **drawn true-to-angle** (θ_hard ≈ 12°), so the ghost poles sit in a
  narrow wedge of vertical — small by design, not a bug;
- a run made with non-default `--u-max` / `--shove-force` will **not** replay the
  overlay faithfully (those aren't serialized; the replay rollout uses the
  calibrated defaults — θ bounds *are* serialized, so `--theta-max` is exact).

**Knobs: build-time constants vs runtime.** Runtime = every flag above and the
`CPS_FRONTIER_*` / `CPS_ESKIP_K` env vars. Build-time (edit + rebuild, re-run the
baselines): the task set `TaskModel.cpp::challengeDefault()` (mirrors
`examples/parameters.md`), `nCores = 3` (`Scheduler.h`), the guard's 60 ms inner
floor (`AdaptiveGuard.cpp`/`Frontier.cpp`), `kZbFlagTicks = 2400` (`Simulation.cpp`),
`kAZoneMs` / `kDangerTauGrid` (`Simulation.cpp` — the conservative packet table,
feeds `--danger-tau` only), `PredictParams` (`Predictor.h`), and the zone-partition
constants (`Trajectory.h`; runtime-overridable via `--zone-consts`).

\1
The common case is a new **core-arbitration policy**: given the cloud jobs that
want to run this tick (across all vehicles) and the shared core count, decide
which get a core. You may use each vehicle's live control metrics (`VehicleView`)
for context-aware decisions.

1. Create `src/sched/policies/MyPolicy.cpp` (auto-picked up by CMake):

   ```cpp
   #include <algorithm>
   #include "sched/policies/Policies.h"

   namespace cps {
   namespace {
   class MyPolicy : public CorePolicy {
   public:
     void assign(const std::vector<ReadyJob>& ready, int nCores,
                 const std::vector<VehicleView>& ctx,
                 std::vector<int>& chosen) override {
       // ... pick up to nCores indices into `ready` ...
     }
     const char* name() const override { return "MyPolicy"; }
   };
   }  // namespace
   std::unique_ptr<CorePolicy> makeMyPolicy() {
     return std::unique_ptr<CorePolicy>(new MyPolicy());
   }
   }  // namespace cps
   ```

2. Declare `makeMyPolicy()` in [`src/sched/policies/Policies.h`](src/sched/policies/Policies.h)
   and add a case to `makePolicy()` in [`main.cpp`](main.cpp). Rebuild — done.

**What a policy sees each tick (read before trusting `VehicleView`).** The
view is built from the PREVIOUS tick's plant outputs plus a prediction cache
refreshed every 100 ticks (`Simulation.cpp`, `kPredictRefreshTicks` /
`kPnrRefreshTicks` in `Simulation.h`) — a one-tick information lag by
construction. The delayed-state ("honest") fields are populated only when the
scheduler NAME matches one of the `-honest` / `h`-prefixed twins listed in
`main.cpp` (`ttu-honest`, `hybrid-honest`, `aguard-honest`, `frontier-honest`
and their short forms); a new policy named `foo-honest` gets no delayed-state
fields unless you add it there. `age_recent_ms` is two rotating 1 s buckets
(`TaskModel.h`, `kLatchAgeBucketTicks`), measured at the actuator with a
zero-delay backchannel (FCHANNEL §7(d)). The comfort tier's ranking rule is
`comfortUrgencyOracle` in `Policies.h`: `3.0·|e_y| + 1.0·rolling + 0.5·critical
+ 1.0·violated`.

See [`RateMonotonic.cpp`](src/sched/policies/RateMonotonic.cpp) and
[`ContextAware.cpp`](src/sched/policies/ContextAware.cpp) for worked examples.

For full control over the 16 FMU triggers (e.g. data-driven, aperiodic triggering
— Challenge Q6), subclass `Scheduler` directly (see
[`src/sched/Scheduler.h`](src/sched/Scheduler.h)) and pass it to the `Simulation`
instead of a `PolicyScheduler`.

## Verification & baselines

There is **no `ctest` / unit-test harness**: the regression suite is a small set of
`./build/cps` + `tools/*.py` invocations whose **golden numbers live as prose in
`HANDOFF.md`** (§2 "Current state" / §Headline-results). Run these after any change and
compare to the expected output. The two **gates** are mandatory after *any* edit that
could touch scheduling-visible behavior (CLAUDE.md invariants 3–6):

| # | Command | Expected (the golden) |
|---|---|---|
| **G0** tool unit tests | `python3 -m unittest discover -s tools/tests -p 'test_*.py'` | all pass (mocked simulator; `zone_sweep.py` min-over-phase arithmetic + schemas) |
| **G1** byte-identical baseline | `./build/cps --headless --vehicles 6 --scheduler rm --exec worst --duration 30` | `90.50 / 100.50 ms`, `missed jobs: 0`, veh3 `0.507 / 13.43%` |
| **G2** predictor fidelity gate | `./build/cps --headless --vehicles 1 --scheduler rm --exec worst --duration 120 --validate-predictor` | `max \|dev\| = 1.490e-08 m -> PASS` (value scales with lap coverage — use the full 120 s) |
| **G3** RTA machine-check | `python3 tools/rta_solve.py --cross-check` | certified capacity `N=5`, empirical `10`, all checks pass, sound vs sim |
| **G4** results regen | `python3 tools/reproduce.py` | regenerates the scheduling CSVs + prints the tables (see footgun below) |

**Measurement-only / additive changes must keep G1 and G2 byte-identical** — that is the
definition of "didn't break anything." **If you intentionally change scheduling-visible
behavior** (tie-break, `--overrun`, periods/WCETs, the `Plant` seam), the golden numbers
*are expected to move*: re-run G1–G3, and **update the numbers in `HANDOFF.md` + `BOUND.md`
§7 + the goldens hard-coded in `.claude/verify.sh` in the same commit** (CLAUDE.md
invariant 4). The prose in those docs is the baseline of record, and `verify.sh` carries a
machine-checked copy — miss it and the done-gate stays permanently red.

**Automated gate runner.** (The "done-gate" that runs it automatically is a USER-level
hook, `~/.claude/hooks/done-gate.py` in Stone's global Claude settings — not in this
repo. On any other machine, run the script yourself before finishing.)
`.claude/verify.sh` runs G0+G1+G2 and checks the golden numbers
(fast, ~5 s); `.claude/verify.sh --full` also runs G3 (the RTA solver, ~15–100 s). The
agentic *done-gate* runs the fast form on every finish and blocks on failure; run `--full`
before committing a scheduling-visible change. It is read-only — it never touches the
reproduce/sweep CSVs.

**Formatting.** The code is hand-formatted; `.clang-format` sets `DisableFormat: true` on
purpose (no stock style matches — the closest still rewrites ~83% of lines). Don't add a
machine style unless you intend a large one-time reformat.

## Reproducing the results

One command regenerates the results CSVs (scheduling AND the zone/occupancy physics
tables, all three profiles) and prints the table each backs:

```sh
python3 tools/reproduce.py            # every experiment (--exec worst)
python3 tools/reproduce.py --list     # capacity / simcrit / honest / floor / tolerance / zones / corollary / partition / sensitivity / occupancy / danger / fzone / fbattery / qzone
python3 tools/reproduce.py floor      # just one (e.g. re-derives PREDICTOR.md §5c)
python3 tools/reproduce.py --quick    # SMALL grids (fast smoke) -- see warning below
bash   tools/demo_capacity.sh         # quick rm-vs-aguard capacity table (N=10,12,18) for presentations
```

`demo_capacity.sh` is a lightweight *presentation* aid (not part of the CSV-backed
repro surface): it prints hard breaches / cars stalled / worst-soft% for rate-monotonic
vs aguard at a few N, showing the headline "zero hard breaches far past the classical
limit" (N=12 RM = 4519 hard / 2 stalled vs aguard 0). Pass custom N: `bash
tools/demo_capacity.sh 10 12 18 20`.

> **CSV-overwrite safety (fixed 2026-07-02).** Experimental runs can no longer clobber
> committed baselines by accident:
> - `reproduce.py --quick` writes its smoke-grid CSVs to `./.reproduce_quick/` (git-ignored),
>   never the committed files. A *full* `reproduce.py` (no `--quick`) still regenerates the
>   committed CSVs — that is its job (G4).
> - `tools/zone_sweep.py` / `tools/occupancy_sweep.py` now take `--out PATH` and **refuse to
>   overwrite an existing file unless `--force`**. Regenerate a committed baseline on purpose
>   with `--force`; experiment with `--out /tmp/...`.

**The reproduce surface (mostly one command, with named exceptions):**
`reproduce.py` covers the scheduling CSVs AND (since 2026-07-04/07-17) the
zone/occupancy/danger physics tables AND (since 2026-08-11) the FCHANNEL
CSVs via delegation: `fzone` → `tools/fzone_sweep.py` (`fzone_tolerance.csv`,
`bzone_tolerance.csv`, `fzone_enterstale.csv`, the cross-profile z3 files),
`fbattery` → `tools/fchannel_battery.py` (`pclean_battery.csv`,
`tuning_grid_n20.csv`, `attribution_matrix.csv`, `coupling_grid.csv` —
**HEAVY: ~2.5 h at --jobs 8**; the CSVs supersede `fchannel_rawlogs/` as the
citable artifact), `qzone` → `tools/qzone_sweep.py` (`qzone_collapse.csv`).
Still OUTSIDE it: the legacy `hybrid_guard_sweep`/`predictive_sweep*` and
`frontier_sweep.csv` CSVs (regenerable via the same framework, never registered).
Run artifacts: `*.cpsr` recordings and `cps_shot*.png` screenshots in the root are
git-ignored scratch (`--save` / `--screenshot` output); `stress_overlay.png` is a
kept demo still. The underlying tools:
`tools/zone_sweep.py` → `zone_tolerance.csv` (leg 1, causal `A(zone)`; with
`--phases-ms 0:20:1` [deterministic chain-phase enumeration: the 1 ms grid plus
the 19.9 ms last tick, 21 phases] or `--offset-seeds K` [random lap positions]
it writes the MIN-OVER-PHASE tables `zone_tolerance_z3_phase*.csv`
/ `zone_tolerance_spot_phase*.csv` — extended schema with per-phase soft% and
undecimated max |e_y| and the delivered F dose; `--jobs N` parallelises;
`--ff-extra-ms D` writes the A2 tables `zone_tolerance_z3_a2{cert,p1}_phase*.csv`
(F publish delayed D ms; PAPER_NOTES 2026-09-04 (b)); `--zone-consts` passes a
perturbed partition through and is recorded per row; `tools/zone_sensitivity.py`
→ `zone_sensitivity_v12.5{,_summary}.csv` = the partition-sensitivity campaign,
`reproduce.py sensitivity`; PAPER_NOTES 2026-09-04),
`tools/occupancy_sweep.py` → `occupancy_sweep.csv` (leg 2, `Occ(s)`),
`tools/danger_sweep.py` → `danger_sweep.csv` (leg 4, the `K(τ)` curve — both the
`[age-only]` and `[+state]` axes, v10 only; `reproduce.py danger` delegates to it), and
`tools/tolerance_sweep.py` (the per-plant cliff, which `reproduce.py tolerance` delegates
to). `tools/rta_solve.py` machine-verifies the BOUND.md §7 RTA — `--workload full|limited|
limited-t` selects the carry-in model; `--a-z3 MS` / `--a-base MS` override the band-verdict budgets (defaults 140 / 290 keep G3 byte-identical; `tools/corollary_table.py` → `corollary_capacity.csv` = the certified capacities at the min-over-phase constants, `reproduce.py corollary`, PAPER_NOTES 2026-09-04 (c)) (`limited`/`limited-t` = the CANDIDATE Guan-RTA-LC, §9.4a),
and `--cross-check --soundness-grid N1,N2,...` adds the Theorem-2 bridge validation (measured age
≤ per-vehicle bound at each certified N; empty grid ⇒ the G3-identical default).

## Layout

```
src/fmu/    FMI 2.0 wrapper (loads the dylib once, N instances) + value refs
src/trace/  loads a profile's reference track + per-tick FMU inputs (CSVs)
src/sched/  Scheduler interface, declarative task model, CorePolicy, policies/
src/sim/    co-simulation master loop + run recording
src/viz/    raylib visualizer
main.cpp    pick scheduler / vehicles / profile / mode
```
