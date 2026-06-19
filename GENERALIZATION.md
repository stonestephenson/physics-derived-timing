# Generalization — the `Plant` seam and the cart-pole (case study #2)

How the framework (data age + bound + age-criticality scheduling) is made
plant-agnostic, and the second plant that proves it. This is the main-track
differentiator: the *same* scheduler / data-age metric / bound run on a second,
very different (unstable) plant, and the **physics-derived timing requirement**
that emerges is plant-dependent — the project's thesis, demonstrated.

Status: the cart-pole is functional and validated; its control parameters are
**first-pass, not yet calibrated** (§4). Live state: `HANDOFF.md`.

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
  predictor uses the same model (no fidelity gate needed; the rollout takes a
  coarse 1 ms RK4 step, negligibly different).
- **Controller:** LQR feedback `u = -K . [x,xdot,theta,thetadot]`, gain
  pole-placed at -2,-3,-4,-5 (`K = [-8.36, -10.73, -64.88, -16.72]`, computed
  offline, closed loop verified stable). Feedforward = 0 (regulation). Applied
  force clamped to `+-uMax` (10 N) — the `delta_max` analogue.
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
- **Age-criticality scheduling generalizes:** aguard carries ~14 cart-poles
  crash-free vs RM's ~11 (N=16: 1 vs 9 crashed).
- The two plants bind on *different legs*: the car on scheduling (overrun ~N=11),
  the cart-pole on physics (age-tolerance ~110 ms).

## 4. Calibration status (do before the numbers are paper-grade)

The cart-pole params (`shoveForce` / `uMax` / `thetaHard` in `CartPoleParams`,
`CartPolePlant.h`) are first-pass, NOT calibrated the way the car's `delta_max`
was (×1.5 of observed). The qualitative contrast is solid; exact numbers (~110 ms,
~14 poles) will shift. TODO: a calibration pass — `uMax` ≈ ×1.5 of nominal
control effort, `theta_max` comfortably above nominal `theta`, shove magnitude
tuned for a clean cliff — then re-run the sweeps and update §3 + `PAPER_NOTES`.

## 5. Adding a third plant

Implement `Plant` (`src/sim/`), add a `PlantKind` value (`Plant.h`), a branch in
`Simulation::start`, a `--plant` token in `main.cpp::parsePlant`, and the source
to `CMakeLists.txt`. Everything else (scheduler, age, bound, `rta_solve.py`) is
reused. Map the plant's safety quantity into `VehicleOutputs::e_y_real` and set
`hardBound()/softBound()`. Route the 16 triggers in `endTick` order (§2) so the
age metric stays valid.
