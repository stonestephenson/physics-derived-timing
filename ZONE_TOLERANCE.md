# Zone-Wise Data-Age Tolerance — Experiment Spec (EE track)

Goal: empirically derive, per track zone, the **maximum tolerable data age**
A(zone) under which the control constraints still hold (hard: |e_y| ≤ 0.8 m
always; soft: |e_y| ≤ 0.2 m for ≥ 95 % of time). This is the context-dependent
timing requirement (Challenge Q4) that the age-aware scheduler will enforce,
and the empirical port of the Wilson et al. (MEMOCODE 2024) zone methodology
from UPPAAL to the Bosch FMU.

Everything here runs on the existing harness — **no code changes needed**
(`--net-delay` and `--csv` are implemented). AI-assist the sweep scripts and
plots freely; the analysis calls (zone boundaries, tolerance thresholds) are
yours.

## Role: this is now an INPUT to the fleet-safety bound (promoted 2026-06-25)

Originally scoped as the EE-track Q4 experiment. As of **2026-06-25 it is on the
critical path of leg (A)**: the fleet-safety bound was reframed as *a function of
the route's zone map* (PAPER_NOTES 2026-06-25; HANDOFF §5 "THE PLAN"). The bound's
worst-case demand = (number/extent of worst-case zones on the route) × (cars that
fit in a zone's danger window at once); slack = the route's non-worst-case fraction.
**A(zone) — the tolerable age per zone derived below — is the physics input that
makes that bound non-pessimistic**, so Phase 1/2 feed the theorem directly, not just
the Q4 figure. Two consumers of the A(zone) output now:
- the **bound** (each zone's deadline tightness; how much slack the route offers);
- the **scheduler** (per-zone mode-switch / guard — deliverable #2 below).

Companion piece needed alongside (HANDOFF §5 leg 2, owned with the bound): the
worst-case zone **occupancy** depends on a **fleet model** — can cars bunch (a jam
releasing together) or are they free-flowing and spaced? State that assumption; the
`--align-offsets` knob is the empirical lever for placing cars adversarially.

## Zones

Derive zones from the reference trace, not from runtime flags: the FMU's
critical-section flag is just `|ff_ref_0| > 1e-6` (in-curve), which is binary.
Better resolution: bin the track by |ff_ref_0| (curvature proxy) from
`examples/example_v_10/feedforward_sequence_0.csv`:
- Z0 straight (ff ≈ 0), Z1 gentle curve, Z2 sharp curve / double lane change
  (the |ff| peaks; per the challenge paper, the double lane change at the start
  is the most demanding maneuver, > 0.5 g).
Map each recorded frame to its zone via `Frame.refStep` (the wrapped trajectory
index — already in every recording/CSV frame row… in the recording; for CSV
work, join on time × known start offset).

## Phase 1 — whole-run delay sweeps, zone-attributed violations

Mechanism: `--net-delay MS` fixes both network delays to MS (already
implemented; the value lands in a `net_delay_ms` CSV column). Sanity anchor:
at N=1/worst, `--net-delay 4` measures 65.5 ms `age_path` vs 90.5 baseline —
the knob moves the age nearly linearly, with a ~1 ms phasing residual.

Then:
1. Sweep `--net-delay` ∈ {1, 4, 8, 12, 16, 24, 32, 48, 64} ms × N=1 vehicle ×
   `--exec worst` × full lap (`--duration 120`). Each run: record measured
   `age_path` (CSV) — the independent variable is *achieved age*, not the knob.
2. For each run, attribute soft/hard violations to zones (violation frames →
   refStep → zone).
3. Output: per-zone curves "violation rate vs measured worst age". A(zone) =
   the largest age with zero hard violations and zone-share of soft budget
   respected. Expect A(straight) ≫ A(curve) — that asymmetry IS the Q4 result.

## Phase 2 — targeted in-zone injection (causal confirmation)

Phase 1 attributes violations to zones but the *delay* was global. Confirm
causality: delay only inside the zone.
- Mechanism (small, clean): make the per-packet delay a function the harness
  queries per send, with a hook `extraDelayTicks(vehicle, step)` wired to zone
  membership of the vehicle's current `refStep` (Simulation knows it; pass it
  into the per-tick path or precompute a zone array indexed by wrapped step).
- Protocol: baseline delays everywhere except zone Z gets +D; sweep D; check
  violations appear only when (zone = sensitive) ∧ (D > A(zone)).
- Also run the converse (delay everywhere *except* Z) — expect the complement.

## Controls and pitfalls

- **Pin `--exec worst`** (fixed delays ⇒ FIFO ⇒ stamps valid; `pert` is
  excluded for formal use — see DATA_AGE.md §5).
- **Startup transient**: discard the first 2 s or start the analysis at the
  first actuation (harness already only ages applied commands).
- **One vehicle for Phase 1/2** (no contention noise); contention enters later
  through the scheduler experiments, not here.
- **Velocity profiles are different difficulty levels**: do v10 first, then
  v12.5 / v15 (`--profile`) — expect A(zone) to shrink with speed. The
  three-profile family A_v(zone, speed) is the full Q4 abstraction.
- **Hard-violation counting is frame-decimated** (10 ms); for tolerance
  thresholds near the cliff, confirm with the FMU's own `threshold_error_cntr`
  (exact, 10 ms windows) and treat `hard` counts as lower bounds.
- The applied-command age is what matters physically; use `age_path` (worst
  case of the conservative convention) as the per-run age statistic.

## Deliverables (feed both papers)

1. `A(zone)` table per profile + the violation-vs-age curves (Route A §"age ↔
   control performance"; Route B's requirement model).
2. The zone array (wrapped-step → zone id) as a CSV checked into `examples/` —
   the scheduler consumes it for mode switching.
3. A two-paragraph methods write-up (goes nearly verbatim into the papers).
