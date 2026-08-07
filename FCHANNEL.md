# FCHANNEL — the reference-channel (F) staleness leg

**Status: CANDIDATE / UNVERIFIED (invariant 5). Owning doc for the A_F(zone)
instrument, the achieved-F-staleness metric, and the frontier scheduler's
paper evidence.** Built 2026-08-07 from the scheduler-frontier study
(FRONTIER.md); reviewer-council dispositions in §8. Zone DEFINITIONS are
frozen (EE-student territory; we consume `Trajectory::zoneAt` as-is).

## 1. Claims (with current evidence grade)

- **C1 — Tolerable staleness is per-CHANNEL, not just per-context.** The
  reference channel (F) has its own per-zone tolerable staleness A_F(zone),
  with far more heterogeneity than the feedback path's A(zone) (140–400 ms,
  ~3x): F staleness is cheap where reference curvature is ~0 and binding
  where the reference moves (z3). *Grade: [C] — inferred from ablation breach
  geography (v9: demoted-F breaches land z3+exit; v10: z3-flagged F
  protection removes exactly those). The controlled dose-response is
  UNMEASURED (see §3 erratum). The A_F instrument (§4) makes this [M].*
- **C2 — A_F is conditional on feedback health (a coupling surface, not a
  constant).** ~20 ms F delay costs +6 soft frames on a clean car, yet
  A2 measured 13.5 ms of F delay tightening the FEEDBACK cliff by one 10 ms
  step, and under overload (stale-ish feedback) demoted-F breaches hard.
  *Grade: [M] at small amplitude (A2); [C] at scale.*
- **C3 — Pricing F service by zone converts the budget into fleet capacity.**
  frontier v12 (= aguard allocation + zone-aware F demotion/tiered heartbeat)
  holds N=21 honest full-lap vs the fairly-tuned incumbent's 19 (+2), and
  13 vs 12 under the strict challenge gate, at ~5x better fleet health.
  Robust: pert x3 + avg + align 0.5; both schedulers' records are
  v10-profile-specific. *Grade: [M] (FRONTIER.md verdict + battery).*
- **C4 — `age_path` is structurally blind to the F channel.** F carries no
  stamp by convention (DATA_AGE §4, deliberate), so a command can measure
  fresh while carrying arbitrarily stale reference geometry — v1–v8
  dominated every age/health metric while breaching through exactly this
  channel. *Grade: [V] by construction + [M] evidence.*

## 2. Definitions

- **F (feedforward + online path planner):** computes the steering the road
  itself demands (from the reference trajectory) — anticipatory,
  geometry-driven. The merger composes command = F(road) + B(error
  correction). F does the bulk of steering in curves; B trims residuals.
- **F staleness (achieved), per vehicle:** at each merger activation,
  `step − lastFfPublishStep` — the age of the F value the merger consumes.
  A NEW parallel quantity (pre-approved 2026-08-07): stamped at F publish
  (ff_fin), read at merger activation. `age_path`, `age_fresh`, and every
  DATA_AGE §4 convention are UNTOUCHED. Reported as per-zone max + fleet max.
- **A_F(zone):** the largest sustained in-zone F-hold D (ms) such that one
  car, full lap (120 s), worst exec, with F held per §4 while inside the
  zone, takes ZERO hard breaches anywhere on the lap (breach-anywhere
  criterion, manifestation != cause — same standard as A(zone)).

## 3. ERRATUM — the ffExtra clamp (supersedes two recorded claims)

`--ff-extra-ms` clamps the publish delay to F's next release
(`TaskModel.cpp:317`: `min(step + ffExtraTicks, nextRelease − 1)`) —
**maximum effective dose ~= one F period (20 ms), regardless of the flag
value.** Consequences:
- The FRONTIER.md log line "bounded F holds are ~free at N=1 (1000 ms
  sanity)" is WRONG as stated: every dose 40–1000 ms administered ~20 ms.
  What that probe actually established: ~20 ms of F delay costs +6 z3 soft
  frames on a clean car. Nothing beyond 20 ms was ever measured cleanly.
- The A2 result (13.5 ms, within the clamp) is unaffected.
- The large-staleness evidence that stands is the ablation's (real
  starvation): v10/v12 run straights at a 500 ms F heartbeat, fleet clean
  to N=21 — but achieved F staleness was never measured directly (the §2
  metric closes that), and it is overload-conditioned, not a clean-car dose.

## 4. The A_F instrument (to build)

`--fzone-target Z --fzone-hold-ms D` (+ `--fzone-hold-ms` alone = all
zones): while the vehicle is inside zone Z, F PUBLISHES are suppressed until
the held value is D ms old — one publish, then suppression for D ms, repeat
(sawtooth 0→D, matching what real scheduler starvation produces). Mechanism:
publish (ff_fin) suppression with the register holding, which is exactly the
kill-and-hold semantics of a missed F — the FMU trigger order is preserved
the same way a killed F preserves it. F still RUNS (consumes its core) so
the schedule is unchanged and the effect is pure data staleness. Off by
default => byte-identical baselines (gate: verify.sh + N=6 golden + fidelity
1.490e-08). Design alternative (release-gating = also frees the core)
rejected: it conflates staleness with load relief; noted for the council.

## 5. Experiment plan (after council)

1. **Instrument self-check:** `--fzone-hold-ms 13.5`-equivalent vs the A2
   record (cliff 170→160 must reproduce within the 10 ms grid); dose ~20 ms
   must reproduce the +6-soft-frame probe result.
2. **A_F(zone) clean-car table:** N=1, 120 s, worst, per zone x D grid
   (100 ms coarse → 20 ms fine at the cliff). Expected shape: z0/z1 large,
   z3 binding; any inversion is a finding, report loudly.
3. **Coupling surface:** fb-dose (`--zone-extra-ms`) in {0, 60, 100} x
   F-dose grid in the binding zones → A_F(zone | fb_age). This is the
   scientifically load-bearing table (C2).
4. **Frontier budget compliance:** achieved F staleness per zone (the §2
   metric) for frontier-honest m100 at N in {19, 21} and aguard-honest m80
   at N=19 — shows frontier's induced staleness sits inside A_F where it
   matters and exploits the slack where it doesn't (the mechanism exhibit).
5. **Sweep tool + repro:** `tools/fzone_sweep.py` (--out/--force per sweep
   discipline), committed CSVs, `reproduce.py fzone` registration.

## 6. Evidence table the paper section needs

| claim | exhibit | source |
|---|---|---|
| C1 shape | A_F(zone) table | §5.2 CSV |
| C2 coupling | A_F(zone \| fb_age) surface | §5.3 CSV |
| C3 capacity | full-lap capacity table 21 vs 19 / 13 vs 12 + battery | FRONTIER.md verdict |
| C3 mechanism | achieved-F-staleness vs budget per zone | §5.4 |
| C4 blindness | v1–v8 dominated-but-breaching + convention cite | FRONTIER.md log, DATA_AGE §4 |

## 7. Known weaknesses (bring to council honestly)

(a) §3 erratum — prior F-tolerance claims over-read a clamped instrument.
(b) v10-only zone map + profile-specific records (both schedulers).
(c) Single deterministic trajectory set; phasing = f(N) confound handled by
    align-offsets battery only. (d) Honest-info caveats: constant 16 ms
    pred-staleness convention; actuator-side age_recent (both inherited from
    the incumbent's convention — comparisons internally fair). (e) All
    capacity results are P1-violating: outside BOUND.md's certified scope,
    empirical only. (f) Heartbeat constants (100/500) are tuned operating
    points, not derived; A_F measurement may justify or replace them.
(g) frontier N=6 ages are aguard-like (100.5/120.5) — the 80.5 ms
    sequencing result belongs to the abandoned v1–v8 line, not v12.

## 8. Reviewer dispositions (filled after the council)

(pending)
