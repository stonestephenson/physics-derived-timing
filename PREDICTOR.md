# Held-Command Prediction: TTV, TTPNR, and the TimeToUnsafe Scheduler

What the predictor computes, the exact definitions and caveats, and how the
`ttu` policy and the visualization consume it. This is the Route B building
block: a **physically-derived dynamic deadline** per vehicle (Challenge Q4),
used online for scheduling (Q2) — the predictive successor to the reactive
`ContextAware` policy.

---

## 1. The two quantities

For each vehicle, ask: *if the actuator keeps holding its current (stale)
command, what happens?*

- **TTV — time to violation**: the first instant the predicted |e_y| crosses
  the hard 0.8 m bound under the held command.
- **TTPNR — time to point of no return**: the last instant at which switching
  to a *recovery* command (full assumed steering authority, see §3) can still
  keep |e_y| < 0.8 m forever after. **TTPNR ≤ TTV always** — the point of no
  return comes before the crash, and it is the real deadline: after it,
  giving the vehicle compute no longer helps (under the assumed limit).

Both are computed by rolling the plant model forward from the vehicle's
current state with the applied command frozen, against the *known* future
reference (ff_ref) and velocity from the trajectory — the reference is known
a priori, so even a cloud-side scheduler may legitimately use it. Values are
capped at the 500 ms horizon ("relaxed"); `ttpnr == 0` means **past PNR**.

## 2. The plant model (and why you can trust it)

`src/sim/Predictor.cpp` carries a **verbatim port** of the FMU's dynamics:
`calculate_matrices_from_velocity` (`LateralMotionControl.c:793–880`,
including the v < 0.1 clamp) and the state update `x⁺ = Ad(v)x + Bd(v)u +
Fd(v)r` (noise off ⇒ deterministic). The FMU itself is untouched (CLAUDE.md
invariant 6).

**Fidelity gate** (`--validate-predictor`): at every actuator latch, predict
e_y over the upcoming ~30 ms hold and compare against what the FMU then
actually does. Result on all three speed profiles (N=1, `--exec worst`, full
120 s lap): **4000 holds, 1.2 M tick-level samples, max |deviation| =
1.49e-08 m — the float32 storage floor.** The ported model is a tick-exact
replica. Re-run this gate after ANY change to the predictor. The gate is
**lateral/FMU-port-specific**: it validates the hand-ported model against the
black-box FMU, so `--plant cartpole` skips it (its predictor shares the plant's
own integrator — nothing to validate against a black box; see GENERALIZATION.md).

Production rollouts use two documented approximations the gate does *not*
cover (it runs the exact path):
- **Velocity quantization**: matrices on a 0.01 m/s grid (shared cache) —
  sub-millimeter effect on predicted e_y over the 500 ms horizon.
- **Coarse stepping**: 1 ms blocks via a precomputed 10-tick affine
  composition per velocity cell (`x_{n+10} = Ad¹⁰x + ΣAdⁱ·(Bd u + Fd r)`),
  so TTV/TTPNR resolve to 1 ms — far finer than the 10 ms refresh cadence.

## 3. The steering limit and the recovery heuristic

The FMU's commanded steering angle (δ_des = `act_out`) is **amplitude-
unbounded** — only rate-shaped by the model's second-order steering dynamics.
"Unrecoverable" is therefore undefined without an assumed limit, which lives
**only in the predictor** (decision 2026-06-11):

| profile | max |act_out| observed (clean N=1 worst lap) | default δ_max (×1.5) |
|---|---|---|
| v10  | 0.1903 rad | **0.285** |
| v12.5| 0.3561 rad | **0.534** |
| v15  | 0.2793 rad | **0.419** |

Override with `--delta-max RAD`. Run a ±50 % sensitivity sweep before
claiming anything quantitative about PNR.

**Recovery law (heuristic, NOT certified reachability):** after a configurable
fresh-command latency (default 4 ms ≈ best-case chain), steer bang-bang at
±δ_max opposing `e_y + 0.3·e_y_dot`, through the model's own steering
dynamics. The steering sign convention is self-probed from the model at
startup, never hand-assumed. "Recovered" = back inside the 0.2 m comfort band
(after ≥ 50 ms) or never breaching for 1 s. TTPNR is found by binary search
over 5 ms-spaced hold snapshots, which assumes recoverability is **monotone**
in hold time — plausible but unproven. Consequences:
- TTPNR is an *estimate* with ~5 ms grid resolution, refreshed every 10 ms
  (warm-started, §5c) and aged in between. The `min_pnr` summary statistic
  depends on these cadences.
- A better recovery policy (e.g., LQR-based, or true reachable-set
  computation) would move PNR later; the bang-bang heuristic is conservative
  in spirit but not provably an under- or over-approximation. Refining this
  is an open EE/Kurt task.

## 4. Where the numbers flow

```
Simulation (cache: TTV+polyline+PNR @10ms — warm-started, aged between)
  ├── VehicleView.ttv_ms / .ttpnr_ms  → policies (ttu ranks on them)
  ├── VehicleSummary.min_ttpnr_ms / .past_pnr_ticks → table + --csv
  ├── Frame.phys[6] / .ttv_ms / .ttpnr_ms (recording v4+) → replay
  └── Simulation::prediction(v) → live visualizer overlay
```

- **`--scheduler ttu`**: rank vehicles by TTPNR ascending (the deadline),
  TTV tie-break, then the strict (period, vehicle, kind) order. Past-PNR
  cars clamp to maximum urgency by default — the real plant's steering is
  unbounded, so the controller may still save them; **`--triage`** inverts
  this (drop them to the bottom) for the rescue-vs-triage experiment.
- **`--scheduler hybrid`** (`Hybrid.cpp`): two-tier *guarded triage*.
  Vehicles with TTPNR below the guard `--guard MS` (default 150) form an
  emergency tier scheduled by ttu's rule; all remaining capacity goes to the
  comfort tier ranked by the shared comfort score (identical to `context`'s
  oracle rule by construction — `comfortUrgencyOracle` in `Policies.h`).
  Limits: guard → 0 ⇒ exactly `context`; guard ≥ horizon ⇒ exactly `ttu`
  (verified empirically, §5b). `--triage` applies as in ttu.
- **Visualizer**: for the selected car, a dotted predicted-e_y line ahead of
  it (same ×exaggeration as everything else), a red ring at the predicted
  0.8 m crossing, an orange diamond at the PNR point, and a HUD line
  ("pred: hits 0.8m in X ms — PNR in Y ms" / "PAST POINT OF NO RETURN").
  Works live and in replays of format-v4+ recordings (`--select`, `--speed`,
  `--screenshot-at` help aim scripted screenshots). The **cart-pole** (`--plant
  cartpole`, recording v5) renders the *same* `Prediction` in **angle space**: the
  TTV/PNR markers become **ghost poles** at the predicted crossing / PNR angles, via
  the shared `drawPredictionOverlay` (GENERALIZATION §6). (The cyan rescue *sweep* is
  car-only today — the cart-pole predictor emits the rescue-clearance scalar, in the
  HUD, but not the trajectory.) The PNR
  ghost typically sits *inside* `thetaHard` — recovery is lost before the visible
  crash, the physical deadline made legible.

## 5. First results (2026-06-11, worst exec, kill-and-hold, 30 s, 3 cores)

Sweep over N = 6..14 × {rm, prm, edf, context, honest, ttu}
(`predictive_sweep.csv`). Hard-breach totals (fleet) and the fleet-minimum
TTPNR ("closest call", ms; "-" = never below the 500 ms horizon):

| N  | rm        | edf      | prm       | context (oracle) | honest   | **ttu**      |
|----|-----------|----------|-----------|------------------|----------|--------------|
| 6  | 0         | 0        | 0         | 0                | 0        | 0            |
| 8  | 0         | 0        | 0         | 0                | 0        | 0            |
| 10 | 0         | 0        | 280 ⚠     | 0                | 0        | 0            |
| 12 | 4519 ☠2   | 3854 ☠2  | 5867 ☠3   | 0 (pnr 295)      | 0 (245)  | **0 (220)**  |
| 14 | 11619 ☠5  | 9457 ☠4  | 15911 ☠7  | 0 (pnr **0**)    | 3125     | **0 (150)**  |

(☠k = k vehicles never completed a chain; "pnr X" = fleet min TTPNR.)

Readings:
- **Safe capacity**: classic policies top out at N≈10–11 (prm < 10 —
  partition imbalance bites first). The reactive oracle (`context`) survives
  N=14 but with **zero** PNR margin — it reaches the brink. **ttu survives
  N=14 with 150 ms of margin fleet-wide**, despite both using ground-truth
  state: *prediction beats reaction on safety margin at equal information*.
- **Honest gap re-motivated**: the honest reactive variant collapses at N=14
  (3125 breaches). The phase-2 honest *predictor* is where that fight goes.
- **Comfort trade**: at N=12, context gets 17 % worst soft-time vs ttu's
  72 % — ttu buys margin with comfort. A hybrid (ttu term near deadlines,
  error term otherwise) is the obvious next policy.
- **Triage A/B**: identical to default at N≤14 — under ttu no vehicle ever
  goes past PNR, so the toggle never engages. It only differentiates beyond
  ttu's capacity or under injected delay (pair with `--net-delay`).

Prediction overhead: +17 % wall time at 12 vehicles (13× → 11× real time;
the plan's "≥20× at 12 veh" gate was mis-calibrated against the 6-vehicle
baseline — the no-predictor floor at 12 vehicles is already 13×).

## 5b. The hybrid: guarded triage (2026-06-12)

`hybrid` wraps ttu's safety guard around context's comfort optimization
(§4). Results (worst exec, kill, 3 cores, 30 s; "soft" = worst per-vehicle
soft-violation share, "floor" = fleet-min TTPNR in ms):

| N  | context        | ttu            | **hybrid (θ=150)** |
|----|----------------|----------------|--------------------|
| 12 | 16.7 % / 295   | 71.8 % / 220   | **16.7 % / 295** (≡ context: guard never fires) |
| 14 | 30.9 % / **0** | 75.5 % / 150   | **36.1 % / 35**    |

All cells are zero hard breaches. At light load the hybrid IS context,
bit-for-bit; at N=14 it keeps a positive safety floor for ~5 points of
comfort, where context reaches the brink (floor 0).

**The guard is a real dial** (N=14 sensitivity; floor rises ≈ 1:1 with θ):

| θ (ms)   | 100 | 150 | 200 | 250 | 300 | 400 |
|----------|-----|-----|-----|-----|-----|-----|
| worst soft | 32.9 | 36.1 | 42.8 | 33.7 | 33.7 | 35.4 |
| floor      | 0   | 35  | 110 | 120 | 205 | 295 |

The θ−floor gap is ≈ 100 ms ≈ the measured worst-case command round-trip
(data age): **achieved floor ≈ θ − round-trip**, because after the guard
fires, the rescue command still needs one chain traversal to take effect.
This is the empirical composition with BOUND.md: set θ ≥ desired floor +
(the age bound) and the floor is guaranteed-by-construction in spirit —
formalizing exactly that implication is the Route B theory hook.

Consequences worth quoting:
- **θ=300 dominates ttu at N=14** on both axes (33.7 % vs 75.5 % soft,
  205 vs 150 floor).
- **N=16 frontier**: θ=150 breaks (2416 hard) and context collapses
  (19 318); ttu survives (76.1 % / 145). **θ=400 also survives N=16 and
  dominates ttu there too (62 % / 235)**; θ=600 reproduces ttu's numbers
  exactly — the θ→∞ limit confirmed.
- So the guard should *scale with load* (round-trip grows with contention).
  An adaptive-θ policy (e.g., θ tracking the observed fleet-min margin or
  the live age measurement) is the natural next step — §6.

*(2026-06-12 note: PNR now refreshes every 10 ms — warm-started searches,
§5c — which improves the fixed hybrid too: at N=14, floor 35 → 75 ms and
worst soft 36.1 → 31.0 %. The table above predates that change.)*

Data: `predictive_sweep.csv` (hybrid rows appended),
`hybrid_guard_sweep.csv` (N=14, rows grouped per guard in the order
100/150/200/250/300/400 — the guard value is not a CSV column),
`frontier_sweep.csv` (N=16).

## 5c. AdaptiveGuard: the self-tuning guard (2026-06-12)

> **Finding A — RESOLVED (per-vehicle θ_v, commit `3214880`); table RE-DERIVED
> 2026-06-23.** θ is now computed per-vehicle from each car's own `age_recent_ms`
> (not the fleet-max), so `--floor` is a live knob again. The table below is the
> proper multi-N `--floor` sweep (post-fix), regenerated by
> `python3 tools/reproduce.py floor` → `aguard_sweep.csv`. The old PRE-fix numbers
> reflected a ~max-guard operating point (the inert code pinned θ near the 450 ms
> clamp): e.g. N=18 `floor=100` used to read floor 220, an artifact — the genuine
> `floor=100` gives 115, and `--floor 200` recovers 220 (see the authority table).

`--scheduler aguard` (`AdaptiveGuard.cpp`, `--floor MS` default 100) closes
the §5b loop online: **θ_v(t) = floor + A_v(t)**, A_v(t) = vehicle v's own *recent
latch-time age* (a ~2 s windowed max of the age of data at each actuator
latch — the live round-trip estimate, `VehicleView::age_recent_ms`), clamped
to [floor+60, 450] so extreme overload degrades gracefully toward pure ttu.

Two ideas from the cached-rescue discussion landed here in legitimate form:
- **Warm-started TTPNR search** (memoization across refresh cycles,
  `PredictParams::warmStartTtpnrTicks`): bracket around the aged previous
  answer (~2–3 rollouts instead of ~7–9). Paid for PNR refresh at **10 ms**
  (was 50) at unchanged wall speed (11× at 12 veh). Every probe re-verifies
  against current state; nothing stale is trusted.
- **Rescue clearance** (`Prediction::rescueClearanceM`, min 0.8−|e_y| over
  the simulated rescue, free byproduct of the h=0 probe): tie-break in the
  emergency tier — among cars at the same TTPNR grid point (including both
  past it), the one whose best rescue grazes the wall goes first. This is
  the cached rescue used as a *scheduling signal*; injecting it as a
  *command* is impossible (the FMU owns all data; the scheduler controls
  only time) and would exit the Challenge's rules.
- The rescue trajectory itself is drawn in the visualizer (cyan dashes from
  the PNR diamond) with a "rescue margin" HUD line.

Results (worst exec, kill, 3 cores, 30 s; soft = worst per-vehicle share,
floor = fleet-min TTPNR ms; all zero hard breaches unless noted; **re-derived
2026-06-23**, `python3 tools/reproduce.py floor`):

| N  | context           | ttu          | **aguard (floor=100)** |
|----|-------------------|--------------|------------------------|
| 10 | 12.0 / 245        | 15.1 / 245   | 12.0 / 245             |
| 12 | 16.7 / 305        | 76.0 / 305   | 16.7 / 305             |
| 14 | 30.9 / **5**      | 74.7 / 185   | **27.1 / 280**         |
| 16 | 19 318 breaches   | 75.9 / 125   | **59.2 / 225**         |
| 18 | 16 021 breaches ☠ | 77.4 / 120   | **54.8 / 115**         |

**aguard matches context at light load (the guard never fires — N≤12 columns are
bit-identical to context), dominates ttu on comfort at every load, and carries 18
vehicles zero-hard — 50 % more than the best classic policy.**

**`--floor` is now a live knob** (Finding A fixed). Its authority grows with load:
at light load the guard never fires (N≤12: every `--floor` gives the same 12.0/245,
16.7/305); at heavy load it sets the safety floor directly. At N=18 the achieved
fleet-min TTPNR tracks `--floor` almost 1:1 at ~constant comfort (~52–56 % soft):

| `--floor` (ms)      | 0   | 60  | 100 | 150 | 200 | 300 |
|---------------------|-----|-----|-----|-----|-----|-----|
| N=16 achieved floor | 180 | 225 | 225 | 225 | 225 | 205 |
| N=18 achieved floor | 10  | 65  | 115 | 155 | 220 | 250 |

This is the **adaptive analogue of §5b's "achieved floor ≈ θ − round-trip"**: under
contention each car's guard is θ_v = floor + its own live round-trip, so dialing
`--floor` dials the guaranteed margin. Default `--floor` stays 100 (≈115 ms floor at
N=18, ≡ context at light load). The two-cars-one-core stress (N=2, 1 core,
`--net-delay 60`) stays breach-free with a 180 ms floor. Data: `aguard_sweep.csv`
(`python3 tools/reproduce.py floor`).

## 5d. Simultaneous criticality: the empirical (A)-shadow (2026-06-22)

The fleet-safety thesis (leg **A**, `PAPER_NOTES.md` 2026-06-22) claims the
physics bounds **how many of N loops are within reaction-time of their PNR at
once** (≤ k); compose with a multicore RTA ⇒ m cores keep all N safe. This is the
empirical instrument for that claim. It does **not** prove it — a sim refutes or
fails-to-refute; the bound is Kurt's — but it measures the realized count.

**Definition.** Every base tick (0.1 ms) a vehicle is **critical** iff its aged
`ttpnr_ms < τ_crit`, where τ_crit ≈ **one command round-trip** = the time to
compute + deliver a *fresh* command (the "must-be-served-now" line: below it,
acting later cannot help). Default **100 ms** (≈ the uncontended `age_path`),
overridable/sweepable via `--tau-crit MS`. We report the run-**max** simultaneous
count, a dwell-time histogram (`sim-crit dist`), and the `>cores` %, plus a loud
line when max > cores (more loops need serving *now* than cores exist). Modeling
choices (measurement only — no scheduler reads it): τ_crit is a **fixed system
constant**, not each car's live round-trip (circular — a starved car's RTT is
huge *because* unserved); the count is the literal `ttpnr<τ_crit` **including
past-PNR** (ttpnr=0), which in the no-crash regime equals "a-core-now-saves-it";
plant-agnostic (reads `currentPredTicks` → `plant->predictHeld`).

**Result (car, worst exec, 3 cores, 30 s, τ_crit = 100 ms):**

| N  | rm (TTPNR-blind)      | ttu   | aguard |
|----|-----------------------|-------|--------|
| 6  | 0                     | 0     | 0      |
| 14 | **7** (>cores 73.6 %) | **0** | **0**  |
| 18 | **12** (>cores 98 %)  | **0** | **0**  |

Physics-blind RM lets 7–12 loops pile within 100 ms of PNR simultaneously — far
past 3 cores. The TTPNR-aware schedulers hold the whole fleet at **0**: at N=18
aguard's *worst* car stays ≥ 115 ms from PNR (ttu N=14: ≥ 185 ms), zero hard
breaches. So 3 cores suffice to keep every car out of the must-serve-now zone —
the (A) claim's empirical shadow, **unrefuted here** for the predictive policies.
(RM > cores is the physics-blind baseline contrast, **not** a refutation of A: a
better scheduler achieves k = 0.)

**Honesty caveat — `sim-crit = 0` ≠ well-controlled.** aguard holds 0 critical at
N=18 while delivering up to **26 s-stale** data and 43–55 % soft violations: the
cars sit in a high-error-but-still-recoverable band, far from PNR but badly
tracked. This metric is **distance-to-PNR simultaneity, not control quality or
freshness.** The margin is thin and quantified — `--tau-crit 150` already makes 1
car critical at aguard N=18 (worst car 115 ms, 15 ms above the line).

**Generality — a different leg (cart-pole).** On the unstable plant aguard does
**not** contain it: N=16 → max **10** (peak), even N=8 → max **1** (vs the car's 0).
The razor cliff (`PAPER_NOTES.md` 2026-06-18) pushes more loops critical at once —
confirming the two plants bind on different legs (car on scheduling, cart-pole on
physics). *Nuance:* the dwell matters — at N=16 aguard is over cores only **0.18 %**
of the run (vs RM's 99.42 %), so the peak max-10 momentarily touches the wall while
the fleet is almost always inside it. (Params calibrated 2026-06-23, GENERALIZATION
§4; the calibrated recovery authority cut the dwell from 0.79 %→0.18 % and N=8 from
2→1, but the peak max-10 — the leg-(A) point for the cart-pole — stands.)

**Repro.** `python3 tools/reproduce.py simcrit` (one command → `simcrit_sweep.csv`),
or by hand: `for s in rm ttu aguard; do for n in 6 14 18; do ./build/cps --headless
--vehicles $n --scheduler $s --exec worst --duration 30; done; done` (τ_crit knob:
add `--tau-crit 50|150`; cart-pole: `--plant cartpole`; CSV cols
`tau_crit_ms,max_sim_crit,sim_crit_over_cores_pct` via `--csv`).

## 5e. Honest predictor: oracle vs delayed-state information (2026-06-22)

Every predictive policy above ranks on TTPNR/TTV seeded from the **true** plant
state — an **oracle** the cloud can never have. The `-honest` twins
(`ttu-honest`/`hybrid-honest`/`aguard-honest`) instead seed the *same* rollout
from the cloud's legitimate **delayed** state — this vehicle's outputs as of its
freshest received sensor packet (`--pred-staleness MS`, default 16 = the
worst-case sensor→cloud delay), held command included — then optionally subtract a
**safety margin** (`--pred-margin MS`, default 0) from the estimated TTPNR. One
class per policy with an `InfoSet` flag (shared with `context`/`honest`) so the
A/B isolates the information set, never the rule; the oracle variants are kept as
the upper-bound reference. **Off by default ⇒ all baselines byte-identical**; at
`--pred-staleness 0` the honest run is byte-identical to its oracle (sanity).

**Crucial invariant:** the **sim-crit metric and `min_pnr` stay on the ORACLE
(true-state) rollout** — they measure *ground-truth* safety regardless of what the
scheduler believes. So an honest run reports the **true** fleet criticality
produced by honest decisions — exactly the credibility question.

**Result (car, worst exec, 3 cores, 30 s, τ_crit = 100 ms). The two predictive
families split:**

| sim-crit max vs staleness d   | oracle | d=16  | d=100 | d=200 |
|-------------------------------|--------|-------|-------|-------|
| `ttu`,    N=14                | 0      | **0** | **0** | 1     |
| `aguard`, N=18                | 0      | **4** | 14    | —     |

- **`ttu` (pure safety ranking) is robust:** a 16–100 ms-stale estimate still
  identifies the nearest-PNR car, so true sim-crit stays **0**; only 200 ms
  staleness lets one car slip. Honesty is nearly free here.
- **`aguard` (comfort-optimizing) is fragile:** at N=18 it ran on a razor margin
  (worst car 115 ms, 15 ms over the line, §5d), so even **16 ms** of staleness
  perturbs its prioritization enough to push **4** loops simultaneously inside
  τ_crit (> 3 cores, 1.08 % of the run); d=100 → 14.

**The margin buys it back.** aguard-honest, N=18, d=16: `--pred-margin` 0 → 30 →
60 → 100 gives sim-crit **4 → 3 → 0 → 0** at ~unchanged miss count. A modest
**60 ms** conservatism on the honest TTPNR fully restores oracle-level safety —
the principled fix: predict pessimistically to absorb the staleness you can't see.

**Generality:** plant-agnostic (the honest rollout is just `predictHeld` fed a
delayed `VehicleOutputs`); cart-pole `aguard-honest` N=8 sim-crit 2 → 3 at d=16
(post 2026-06-23 calibration; was 2 → 4 — the calibrated authority softens the
honest gap too). d=100 also 3; pure-oracle aguard N=8 is 1.

*Honesty note:* this harness is deterministic with an exact plant port, so the
honest gap is pure information **staleness** — no sensor noise / model error (a
model-based observer would just recover the truth). `--pred-staleness` /
`--pred-margin` are the stress + recovery knobs; folding in the FMU's own
`e_y_est` estimation error is the open refinement (§6.4).

**Repro.** `python3 tools/reproduce.py honest` (one command → `honest_sweep.csv`),
or by hand: `for d in 0 16 100 200; do ./build/cps --headless --vehicles 18
--scheduler aguard-honest --exec worst --duration 30 --pred-staleness $d; done`
(margin: add `--pred-margin 60`; oracle ref: `--scheduler aguard`).

## 5f. Predictor compute cost (Finding B, 2026-06-23)

Every run times its `predictHeld` rollouts and prints `prediction compute:
us/prediction, %-of-one-core (rollouts, wall, sim seconds)` — replacing the old
"+17 % wall" (slowdown vs the *free* FMU sim; the right denominator is a CPU core).
Numbers (worst exec):

| run                   | µs/prediction | % of one core         |
|-----------------------|---------------|-----------------------|
| car ttu N=14          | ~14           | 2.0 %                 |
| car aguard N=18       | ~17           | 3.0 %                 |
| car ttu-honest N=14   | ~14           | 4.0 % (both rollouts) |
| cart-pole aguard N=8  | ~333          | 27 %                  |

The **car** predictor (velocity-quantized matrix cache + coarse affine stepping +
warm-started search) is ~0.1 %/vehicle of a core — **decisively negligible**
against the 3 worker cores, even honest (2×) at the fleet ceiling. The
**cart-pole** predictor is a naive 1 ms RK4 rollout (no cache) — ~30× heavier
(27 % of a core at N=8); fine for the generality demo, not optimized. (Invariant to
the 2026-06-23 param calibration — `uMax` changes the recovery *force*, not the
rollout's RK4 step count. Matching the car's matrix cache + warm-started search is the
optional follow-up; it does not affect any safety result.)

**Assumption (challenge framing):** the dedicated cloud *scheduler/predictor* runs
on separate orchestration infrastructure, not the N_c worker cores, so this compute
does not subtract from the worker budget; even charged against a single core it is
~2–4 % (car). **Compute is not the binding realism constraint — input freshness
(§5e) is.** The printed cost is wall-time (non-deterministic) — a diagnostic, not a
CSV metric.

## 6. Open items

1. ~~Adaptive guard~~ — done (§5c). Remaining refinement: per-vehicle θ_v
   from each car's own round-trip, and a clearance-ablation study (count how
   often the tie-break decides orderings).
2. δ_max sensitivity sweep (±50 %) and the triage-vs-rescue figure (triage
   never engages at N≤14 under ttu/hybrid — needs higher load or
   `--net-delay` injection).
3. Recovery-policy refinement / monotonicity assumption (EE + Kurt).
4. ~~Honest-information variant~~ — done (§5e): `ttu/hybrid/aguard-honest`
   predict from delayed state (`--pred-staleness`) + a safety margin
   (`--pred-margin`). *Investigated 2026-06-23:* folding in the FMU's `e_y_est` is
   **largely moot** — the FMU runs noise-free by default (`physical_noise=false`,
   `LateralMotionControl.c:414`) and computes `e_y_est = E·(delayed sensors)`, so
   it differs from truth essentially by the network staleness §5e already models
   (no independent estimation error). Enabling the FMU's noise = *process* noise
   that breaks determinism. Open only if a stochastic-plant study is wanted.
5. Formalize the §5b composition with BOUND.md: bounded age ⇒ bounded
   guard-to-actuation lag ⇒ guaranteed floor (θ − bound). This is the Route
   B theorem shape: *a scheduler parameter with a physically provable
   safety-margin guarantee*.
6. Differentiate from Wilson et al. (MEMOCODE'24): their lookahead checks
   crash-vs-no-crash for one vehicle offline/at-verification-time; TTV/TTPNR
   are continuous online quantities driving multi-vehicle arbitration.
