# Zone-Wise Data-Age Tolerance — Experiment Spec (EE track)

Goal: empirically derive, per track zone, the **maximum tolerable data age**
A(zone) under which the control constraints still hold (hard: |e_y| ≤ 0.8 m
always; soft: |e_y| ≤ 0.2 m for ≥ 95 % of time). This is the context-dependent
timing requirement (Challenge Q4) that the age-aware scheduler will enforce,
and the empirical port of the Wilson et al. (MEMOCODE 2024) zone methodology
from UPPAAL to the Bosch FMU.

**Status 2026-09-04: A(zone) is a MIN OVER THE CHAIN PHASE.** Every earlier
table was measured at one phase (seed 0 = lap index 0), which is the *luckiest*
phase on every profile (PAPER_NOTES 2026-09-04). Tables of record are now the
21-phase enumerations (1 ms grid + the 19.9 ms last tick)
`zone_tolerance_z3_phase{,_v12.5,_v15}.csv` +
`zone_tolerance_spot_phase{,_v12.5,_v15}.csv` (`tools/zone_sweep.py
--phases-ms 0:20:1`, driven by the new `--start-offsets-ms` harness flag):
**z3 = 150.5 / 140.5 / 110.5 ms (v10 / v12.5 / v15)**; z0 290.5 / 290.5 / 240.5;
z1 390.5 / 240.5 / 190.5; z2 290.5 / 230.5 / 140.5 (hard criterion; z2 on
v12.5 refined to the 10 ms grid, `zone_tolerance_z2_fine_phase_v12.5.csv` —
the other non-z3 values are 50 ms brackets; z1 = min-over-phase delivered
age, PAPER_NOTES 2026-09-04 (c)). The
single-phase files below remain as the max-over-phase reference. The soft
constraint (≥ 95 % within 0.2 m) is now recorded per row (`soft_pct`) and binds
earlier (v10 z3: 120.5 ms; v15 violates it uninjected). **DECIDED 2026-09-04
(Stone): A(zone) is certified against the HARD constraint only; the soft
(comfort chance-constraint) data is reported as a stated limitation, never
certified** — it is a whole-run budget, not a per-zone physical quantity.
**A2 (feedforward staleness under contention) re-measured min-over-phase
2026-09-04 (b):** the effect is binary — the Estimator's second job (tick
100) reads F fresh vs one period old (threshold: F published after tick 100;
the Merger reads a period-old F at every dose under the N=1 RM order) — and
within one instrument step, non-monotone on v12.5; the constants above are
the min over both measured regimes under constant lateness. Stated, not
measured: the fresh-Merger regime (unreachable at N=1 RM) and per-job regime
mixing at N=8 (`--ff-extra-ms`; `zone_tolerance_z3_a2{cert,p1}_phase*.csv`;
PAPER_NOTES 2026-09-04 (b)).
**Partition caveat CLOSED 2026-09-04 (d):** the partition is the same track
partition at every speed (curvature proxies identical across profiles;
boundaries match v10 to 0.30 m on v12.5 / 0.81 m on v15; only the time-based
lane-change expansion is speed-dependent — conservative, and it merges two
arcs on v15), and on v12.5 the certified constant, the z2 budget and the
composed N = 8 are unchanged under ±20 % thresholds and ±50 % lane-change
timing (`--zone-consts`; `tools/zone_partition.py`, `tools/zone_sensitivity.py`;
`zone_partition_runs.csv`, `zone_sensitivity_v12.5{,_summary}.csv`;
PAPER_NOTES 2026-09-04 (d)).

**Status 2026-07-04: Phase-1 + Phase-2 IMPLEMENTED; fine-grid cliffs + v12.5/v15
tables MEASURED (see the 2026-07-04 block below); a zone-consuming scheduler
(`zband`) now EXISTS.** *(Original status 2026-06-26: Phase-1 + Phase-2 implemented.)* Per-zone breach
attribution lives in `Simulation` (buckets frame breaches/occupancy by
`Trajectory::zoneAt`); causal in-zone injection is `--zone-target Z` /
`--zone-extra-ms D`; `tools/zone_sweep.py` runs the causal sweep → `zone_tolerance.csv`.
**Causal A(zone), 2026-06-26 single-phase coarse grid: z3 lane-change 140 ms (binding) /
z0 straight & z2 sharp 290 ms / z1 slight 400 ms** (PAPER_NOTES 2026-06-26; THEOREM_BRIEF
§3.2) — historic; the values of record are in the 2026-09-04 header above and in HANDOFF
"Numbers of record". `--net-delay` and
`--csv` also available. AI drives the sweep scripts/plots; the zone-boundary and
tolerance-threshold *judgment* calls are the EE side's.

## Role: this is now an INPUT to the fleet-safety bound (promoted 2026-06-25)

Originally scoped as the EE-track Q4 experiment. As of **2026-06-25 it is on the
critical path of leg (A)**: the fleet-safety bound was reframed as *a function of
the route's zone map* (PAPER_NOTES 2026-06-25; HANDOFF §5 "THE PLAN"). The bound's
worst-case demand = (number/extent of worst-case zones on the route) × (cars that
fit in a zone's danger window at once); slack = the route's non-worst-case fraction.
**A(zone) — the tolerable age per zone derived below — is the physics input that
makes that bound non-pessimistic**, so Phase 1/2 feed the theorem directly, not just
the Q4 figure. Consumer of the A(zone) output today:
- the **bound** (each zone's deadline tightness; how much slack the route offers) —
  via the in-process zone instruments in `Simulation.cpp` (`--zone-target`, `--pack-zone`,
  `--danger-tau`), which read `Trajectory::zoneAt`.
- (Hypothetical, **not built**) a per-zone mode-switching **scheduler** — see the
  corrected deliverable #2 below. No scheduler reads `zoneAt` today; zones are
  measurement-only.

Companion piece needed alongside (HANDOFF §5 leg 2, owned with the bound): the
worst-case zone **occupancy** depends on a **fleet model** — can cars bunch (a jam
releasing together) or are they free-flowing and spaced? State that assumption; the
`--align-offsets` knob is the empirical lever for placing cars adversarially. The
chosen model is `F_spaced` (minimum temporal spacing `s`); its constant-spacing
assumption is now **buffered** against delay-induced compression — certify at
`s_eff = s − Δ` (PROOF_DRAFT §4 spacing-robustness buffer; `lemma1_check.py` [5];
PAPER_NOTES 2026-07-17).

## Zones

Derive zones from the reference trace, not from runtime flags: the FMU's
critical-section flag is just `|ff_ref_0| > 1e-6` (in-curve), which is binary.
Better resolution: bin the track by |ff_ref_0| (curvature proxy) from
`examples/example_v_10/feedforward_sequence_0.csv`:
- **The adopted implementation (`Trajectory::zoneAt`) uses FOUR zones:** Z0 straight,
  Z1 slight turn, Z2 sharp turn (all by `|ff_ref_0|` thresholds), and **Z3 lane-change**
  — seeded by the curvature's spatial gradient dκ/ds (`ff_ref_1`; FCHANNEL §8 item
  5 verified it is per metre, not per second) + a local curvature range, then oracle-
  expanded over the whole maneuver. **Z3 is the BINDING zone (causal A = 140 ms on the
  original single-phase grid; 150.5 / 140.5 / 110.5 min-over-phase of record — HANDOFF
  "Numbers of record")**;
  the challenge's double-lane-change is the most demanding maneuver (> 0.5 g). (The
  old 3-zone `|ff_ref_0|`-only binning below is superseded by this.)
Map each recorded frame to its zone via `Frame.refStep` (the wrapped trajectory
index — already in every recording/CSV frame row… in the recording; for CSV
work, join on time × known start offset).

### Zone segmentation — algorithm + constants (code-only; re-examine per profile)

The zone array is built once per profile in **`Trajectory::computeTrackZones`
(`src/trace/Trajectory.cpp:146-255`)** and read in-process via `zoneAt`. Units: `ff_ref_0`
≈ path curvature κ and `ff_ref_1` ≈ dκ/ds, both in 1/m (the plant consumes q = κ +
0.2·dκ/ds, FCHANNEL §5), so the thresholds below are in 1/m. The algorithm
(not previously documented anywhere but the code):
1. **Per-tick base zone** by `|ff_ref_0|` (curvature proxy): `Z0` if ≤ `kZoneZeroEpsilon`,
   `Z1` if `< kZoneSharpThreshold`, else `Z2` (`trackZoneFromFf0`).
2. **Z3 (lane-change) seeds** at ticks where the curvature gradient dκ/ds is high —
   `|ff_ref_1| ≥ kZoneLaneFf1Threshold` **or** a windowed curvature *range*
   `curvatureDelta ≥ kZoneLaneCurvatureDeltaThreshold`. The range is the max−min of
   `ff_ref_0` over a ±`kZoneLaneHalfWindowTicks` window, computed with a **monotonic-deque
   sliding window** (O(n)); seeds are written into a diff-array, then **padded**
   ±`kZoneLaneOraclePadTicks` and **bridged** across gaps ≤ `kZoneLaneOracleBridgeTicks`
   (the "oracle" expand pass) so the whole maneuver — not just its onset — is labelled Z3.

**2026-09-04 (d):** the constants are now overridable at runtime
(`cps --zone-consts S,F,D,W,P,B`, `ZoneParams` in `Trajectory.h`; defaults =
the constants below, byte-identical), and the standing "re-examine per
profile" instruction is answered: the curvature thresholds are
speed-independent (same track), the partition matches v10 to the metre on
v12.5/v15, and v12.5's certified numbers are insensitive to ±20 % / ±50 %
perturbations (PAPER_NOTES 2026-09-04 (d)). What remains speed-dependent is
the time-based lane-change expansion (window/pad/bridge in ms), which grows
z3 with speed and bridges two arcs on v15.

**The constants (`src/trace/Trajectory.h:33-39`) — code-only until 2026-09-04, hand-tuned
for v10, with no formal derivation:**

| constant | value | role |
|---|---|---|
| `kZoneSharpThreshold` | `0.0215` | Z1 vs Z2 split (slight vs sharp turn) |
| `kZoneLaneFf1Threshold` | `0.0035` | Z3 seed: curvature-rate threshold |
| `kZoneLaneCurvatureDeltaThreshold` | `0.0040` | Z3 seed: windowed curvature-range threshold |
| `kZoneLaneHalfWindowTicks` | `500` (±50 ms) | range window half-width |
| `kZoneLaneOraclePadTicks` | `1000` (±100 ms) | pad around each Z3 seed |
| `kZoneLaneOracleBridgeTicks` | `3500` (350 ms) | fill gaps between Z3 seeds |

The headline **A(z3) binding result rests entirely on this partition.** The
A(zone) deadline table itself is hard-coded **v10-only** as `kAZoneMs={290,400,290,140}`
at `src/sim/Simulation.cpp` (leg-4 danger metric; twin copy `A_ZONE_MS` in
`tools/rta_solve.py`) — if the partition is re-tuned, both copies must change **in
lockstep**. **2026-07-04 measurements (PROOF_DRAFT §8.1):** fine 10 ms grids (the
instrument's true resolution — delivered ages quantize in T_E steps) refine the z3
cliff to **170 (v10) / 160 (v12.5) / 90 (v15)**; full coarse tables for v12.5/v15 are
measured (`zone_tolerance_v12.5.csv`, `zone_tolerance_v15.csv`; regenerate via
`reproduce.py zones`). **Standing caveat, now load-bearing:** these thresholds were
tuned to v10's curvature scale and were NOT re-derived per profile — the published
v12.5/v15 A(zone) tables inherit v10-tuned segmentation constants (they still resolve
sensible per-profile zone maps: K=4/4/3 arcs, ~9 % of lap — `tools/proofchecks/
zone_probe.cpp`), so **re-examine the partition per profile before any v12.5/v15
number becomes normative in the paper**. The conservative v10 A(z3)=140 remains the
value the Kurt packet and the danger metric use.

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
- **Phase.** A(zone) depends on the chain-release phase at zone entry (period
  20 ms = the task-set hyperperiod; lap-invariant because every lap length is a
  multiple of 200 ticks). Never quote a single-phase value: sweep
  `--phases-ms 0:20:1` — the 1 ms grid plus the interval's last tick, 19.9 ms,
  which the tool appends: the sup is the worst phase at every measured cliff,
  and a grid without it under-reported v12.5's z3 by one step. At every
  partially-clean cell the clean phases are exactly the lowest ones; best = 0,
  the historical seed-0 phase. PAPER_NOTES 2026-09-04.
- **Hard-violation counting is frame-decimated** (10 ms); for tolerance
  thresholds near the cliff, confirm with the FMU's own `threshold_error_cntr`
  (exact, 10 ms windows) and treat `hard` counts as lower bounds. (Checked
  2026-09-04: the undecimated per-tick max |e_y| agreed with the decimated
  counter on all 1,449 phase rows — the phase CSVs carry both.)
- The applied-command age is what matters physically; use `age_path` (worst
  case of the conservative convention) as the per-run age statistic.

## Deliverables (feed both papers)

1. `A(zone)` table per profile + the violation-vs-age curves (Route A §"age ↔
   control performance"; Route B's requirement model). **(Done for ALL profiles
   2026-07-04: `zone_tolerance.csv` + `_v12.5` + `_v15` + fine z3 grids; one
   command: `reproduce.py zones`. Partition caveat above applies to v12.5/v15.)
   **2026-09-04: superseded by the min-over-phase tables (same command
   regenerates both generations; status header above).**
2. ~~The zone array as a CSV checked into `examples/` — the scheduler consumes it for
   mode switching.~~ **CORRECTION (2026-06-29): not built, and not the current design.**
   The zone array is computed **at runtime** in `Trajectory::computeTrackZones` and read
   **in-process** via `zoneAt` — it is **not exported to a CSV** (nothing under
   `examples/` holds one). **UPDATE 2026-07-04: a zone-consuming scheduler now EXISTS** —
   `--scheduler zband` (PROOF_DRAFT §3.1/§8.4): `Simulation` computes a per-car z3±240 ms
   flag from `zoneAt` (`VehicleView.zone_flagged`), and jobs are band-stamped at release.
   The measurement instruments read `zoneAt` as before. If a CSV export is ever wanted,
   add it to the runtime build, don't check in a static one (it must track the constants
   above).
3. A two-paragraph methods write-up (goes nearly verbatim into the papers).
