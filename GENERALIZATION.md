# Generalization — the `Plant` seam and the cart-pole (case study #2)

How the framework (data age + bound + age-criticality scheduling) is made
plant-agnostic, and the second plant that proves it. This is the main-track
differentiator: the *same* scheduler / data-age metric / bound run on a second,
very different (unstable) plant, and the **physics-derived timing requirement**
that emerges is plant-dependent — the project's thesis, demonstrated.

Status: the cart-pole is functional and validated; its control parameters are
**calibrated** (2026-06-23, §4) by the car's `delta_max` method. Live state: `HANDOFF.md`.

## 1. The `Plant` seam

`src/sim/Plant.h` is the interface a controlled system + its in-the-loop control
chain implements. The FMU is touched only here now; everything else is
plant-agnostic.

Interface (per base tick): `initialize` / `setInputs(ref0,ref1,vel)` /
`applyTriggers(VehicleTriggers)` / `doStep` / `readOutputs() -> VehicleOutputs`,
plus `predictHeld(...) -> Prediction` (each plant rolls its OWN dynamics for
TTV/TTPNR) and `hardBound()/softBound()` (safety/comfort thresholds on the error
signal `VehicleOutputs::e_y_real`).

Plant-agnostic, reused unchanged for any plant: the scheduler + all policies
(`src/sched/`), the data-age task model (`TaskChainModel` — it *shadows* the
trigger routing, independent of the plant's math), the bound, and
`tools/rta_solve.py`. `Simulation` (`src/sim/Simulation.cpp`) holds a
`unique_ptr<Plant>` per vehicle and branches on `SimParams::plant`
(`--plant lateral|cartpole`); only the lateral path loads the FMU library.

Implementations: `LateralPlant` (`src/sim/LateralPlant.{h,cpp}`) wraps the FMU,
behavior-identical to the pre-seam path (baselines verified byte-identical);
`CartPolePlant` (`src/sim/CartPolePlant.{h,cpp}`) is below.

## 2. The cart-pole (case study #2)

An inverted pendulum on a cart — **unstable**, so its physics-derived
point-of-no-return is genuinely physical and its age tolerance is tight/sharp.

- **State** `[x, xdot, theta, thetadot]`; error signal = `theta` (pole angle from
  vertical), mapped into `e_y_real`. **Bounds:** `|theta| <= 0.21 rad` (~12 deg)
  hard, `0.05 rad` soft — the 0.8 m / 0.2 m analogues.
- **Dynamics:** textbook nonlinear cart-pole (M=1, m=0.1, l=0.5, g=9.81),
  RK4-integrated at the 0.1 ms tick. Because the plant is our own code, the
  predictor uses the same model (no fidelity gate needed — `--validate-predictor`
  is skipped for cartpole; the rollout takes a coarse 1 ms RK4 step, negligibly
  different).
- **Controller:** LQR feedback `u = -K . [x,xdot,theta,thetadot]`, gain
  pole-placed at -2,-3,-4,-5 (`K = [-8.36, -10.73, -64.88, -16.72]`, computed
  offline, closed loop verified stable). Feedforward = 0 (regulation). Applied
  force clamped to `+-uMax` (**11.55 N**, calibrated §4) — the `delta_max` analogue.
- **Chain mapping:** `CartPolePlant::doStep` integrates physics with the held
  command + the disturbance, then routes the 16 triggers in
  `TaskChainModel::endTick` order (receives, sensor samples state, identity
  estimator, LQR controller, ff=0, merger sum, actuator clamp) — so the data-age
  metric applies unchanged. Sensor/estimator buffers carry the 4-state; from the
  controller on, a scalar force; SC/CA network FIFOs hold delayed values.
- **The "track":** a deterministic, a-priori-known disturbance schedule
  (periodic cart-force shoves) — the analogue of racetrack curvature, so the
  predictor can see it ahead.
- **Predictor (`predictHeld`):** roll forward holding the command for TTV (first
  `|theta| >= theta_max`); binary-search the latest bang-bang `+-uMax` recovery
  start (sign opposing `theta + 0.3*thetadot`) for TTPNR. Assumptions (as for the
  car): bounded recovery authority, monotone recoverability in hold time,
  coarse-step rollout.

## 3. Results — the thesis on two plants

See `PAPER_NOTES.md` (2026-06-18 entries) and `tools/tolerance_sweep.py`:
- **Age-tolerance is physics-derived & plant-dependent:** car ~245 ms (gradual)
  vs cart-pole ~110 ms (sharp ~5 ms cliff) — same chain, same delivered age per
  delay; only the physics differs.
- **Age-criticality scheduling generalizes:** aguard carries **17** cart-poles
  crash-free vs RM's **10** (N=16: 0 vs 9 crashed; 20 s worst; **16 at the full
  120 s lap, the value of record — PAPER_NOTES 2026-08-24; HANDOFF "Numbers of
  record"**). (This 17 vs the
  pre-2026-06-22 ~14 is mostly the per-vehicle-θ floor fix, commit `3214880`, not
  the calibration — at uMax=10 aguard already reaches 0/17; calibration only trims
  N=18 from 3→1 crashes.)
- The two plants bind on *different legs*: the car on scheduling (overrun ~N=11),
  the cart-pole on physics (age-tolerance ~110 ms; aguard still hits sim-crit 10 at
  N=16 where the car holds 0).

## 4. Calibration (2026-06-23 — paper-grade, the car's `delta_max` method)

The cart-pole params (`CartPoleParams`, `CartPolePlant.h`) are now derived by a
stated, reproducible procedure, the analogue of the car's `delta_max` = 1.5 × max
observed actuation (`Predictor.cpp:defaultDeltaMax`):

- **`uMax` = 1.5 × observed peak control demand.** Measured `max|pre-clamp force|`
  over a clean N=1 `--exec worst` run (the new `--validate-predictor` "actuator
  calibration aid" line, all plants) = **7.7012 N** → **`uMax` = 11.55 N**. The old
  round 10.0 was only 1.30× the demand — *under* the ×1.5 standard. `uMax` is the
  cart-pole's `delta_max`: the actuator-clamp ceiling in the plant *and* the
  predictor's `±uMax` recovery authority. The nominal demand (7.70) stays below the
  clamp, so the N=1 trajectory is unchanged ("clamp free").
- **`thetaHard` = 0.21 rad (12°), `thetaSoft` = 0.05 rad (3°) — kept** as the
  *given* physical safety spec (the 0.8 / 0.2 m analogue; a chosen safety envelope
  for the nonlinear plant, not a linearization bound). Verified nominal-fresh peak
  |θ| ≈ 0.063 rad sits at ~30 % of `thetaHard` — comfortable headroom, like the car
  inside 0.8 m. (`thetaSoft` deliberately sits just below the nominal peak, so the
  ~5 % nominal soft-violation is expected and meaningful.)
- **`shoveForce` = 8 N — kept**, the disturbance "track", fixed relative to actuator
  authority: emergent `shove/uMax = 8/11.55 = 0.69 ≤ 0.80` (disturbance within
  authority). Peak demand ≈ 0.96 × shove, so the proportional loop is ill-posed
  (chasing exactly 0.8 diverges); the scale is pinned by the fresh-safety operating
  point (peak |θ| ≈ 30 % `thetaHard`) and the ratio reported.

**Effect on the headline numbers (re-derived, §3 + `PAPER_NOTES.md` 2026-06-23):**
the qualitative story is unchanged / sharper. The **age-tolerance cliff boundary is
invariant** at the sweep resolution (car (245.5, 345.5] ms, cart-pole (105.5, 110.5] ms
— identical pre/post; `tolerance_sweep.csv`). It does *not* hold because the clamp is
free — under the sweep's injected staleness the held command grows and the demand
*does* reach the clamp, so the near-cliff peak |θ| (0.18→0.20 rad, still safe) and the
post-crash breach counts shift. It holds because the exponential cliff is so sharp
that the ~15 % authority change cannot push the recoverability boundary by a full
sweep step: the tolerance is governed by the instability timescale, not the actuator
limit. Calibration's clearest effect is on the predictor-driven
metrics (`min_pnr` N=1: 100→110 ms; sim-crit N=8 2→1, N=16 dwell-over-cores
0.79 %→0.18 %; honest gap milder 2→3 vs 2→4). Capacity gained little from
calibration itself (the floor fix `3214880` did the work). Overridable for sweeps via
`--u-max` / `--shove-force` / `--theta-max`.

## 5. Adding a third plant

Implement `Plant` (`src/sim/`), add a `PlantKind` value (`Plant.h`), a branch in
`Simulation::start`, a `--plant` token in `main.cpp::parsePlant`, and the source
to `CMakeLists.txt`. Everything else (scheduler, age, bound, `rta_solve.py`) is
reused. Know what is NOT plant-generic: every zone / occupancy / danger
instrument (`--zone-target`, `--pack-zone`, `--danger-tau`, the F/B/q-zone
doses) is gated `plant == PlantKind::Lateral` in `Simulation.cpp`; `kAZoneMs`
is v10-only; the lateral `Trajectory` (and its CSVs) is loaded regardless of
plant; and the predictor's "recovered" test differs per plant (car: inside
the soft band at any instant after 50 ms, `Predictor.cpp`; cart-pole: 50 ms
continuously inside, `CartPolePlant.cpp`). Map the plant's safety quantity into `VehicleOutputs::e_y_real` and set
`hardBound()/softBound()`. Route the 16 triggers in `endTick` order (§2) so the
age metric stays valid. (Editing a `Plant` *implementation* such as
`CartPolePlant.cpp` is allowed — CLAUDE.md invariant 6 forbids touching the
prebuilt **FMU** and the `Plant.h` **seam**, not the implementations behind it.)

## 6. Visualization (the cart-pole view)

The visualizer is plant-keyed (`Visualizer.cpp`, on `RunRecording.plantKind`, stored
in recording format **v5**). The FMU car keeps its top-down track view; the cart-pole
gets a dedicated view — a cart on a rail + a pole hinged at θ, ±`thetaSoft` /
±`thetaHard` bound rays (the lane-ring analogue, drawn true-to-angle since
`thetaHard` ≈ 12° is directly visible), the held-command prediction in **angle space**
(a held-θ tip trajectory + **ghost poles** at the predicted TTV and PNR angles + the
shared rescue-sweep branch, all from the plant-agnostic `Prediction`), a θ-vs-time strip with shove
bands (`kCritical` = mid-shove), and a fleet row of per-vehicle θ ticks. The
window/loop/input/replay/screenshot/select-speed shell and the prediction-overlay
logic are **shared** with the car (`drawPredictionOverlay`, parameterized by the
plant's (soft,hard) bounds) so the two views can't drift; a new plant adds only its
own `draw<Plant>Scene`. The **PNR ghost pole sits inside `thetaHard`** (recovery is
lost before the visible fall) — the razor-thin recoverability deadline made legible,
the thesis (timing derived from physics) rendered. Replay re-rolls the plant's own
`predictHeld`; live reads the sim's cache. *Caveat:* the replay overlay reconstructs
with default `uMax`/`shoveForce` (not serialized, like the car's delta-max default) —
exact for default-params runs; the θ bounds *are* serialized (so `--theta-max`
replays correctly). The cyan rescue *sweep* is car-only today — `CartPolePlant::
predictHeld` emits the rescue-clearance scalar (HUD), not the trajectory; emitting it
is a small plant-side follow-up (the car's `Predictor.cpp` already does). Versioning: v5 adds `plantKind` + `hard/softBoundVal`; the frame
layout is unchanged from v4, so v2/v3/v4 recordings still replay (older cart-pole
runs predate the tag and render as the car — the prior behavior).
