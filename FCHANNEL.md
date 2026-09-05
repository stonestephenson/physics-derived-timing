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
- **F staleness (achieved), per vehicle:** the age of the value in F's
  output register, stamped at F's ACTIVATION tick (DATA_AGE §4a style — §8
  item 6 changed this from publish-stamped) and sampled EVERY tick
  (`TaskModel.h` `ffStale*`, `Simulation.cpp`), reported as per-zone max +
  fleet max (the `F staleness (act-stamped, ms)` summary line). A parallel
  quantity: `age_path`, `age_fresh`, and every DATA_AGE §4 convention are
  UNTOUCHED.
- **A_F(zone):** the largest sustained in-zone F-hold D (ms) such that one
  car, full lap (120 s), worst exec, with F held per §4 while inside the
  zone, takes ZERO hard breaches anywhere on the lap (breach-anywhere
  criterion, manifestation != cause — same standard as A(zone)). Entry
  state: measured over entry phases via `--fzone-lead-ms` (§9.9); at the
  cliff the enter-fresh arm binds, so the enter-fresh table IS the
  min-over-phase A_F.

## 3. ERRATUM — the ffExtra clamp (supersedes two recorded claims)

`--ff-extra-ms` clamps the publish delay to F's next release
(`TaskModel.cpp`, the ffFinDueAt_ block: `min(step + extra, nextRelease − 1)`) —
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

## 4. The A_F instrument (BUILT 2026-08-10; spec kept as reference — results §9)

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

## 8. Reviewer dispositions (4-reviewer council, 2026-08-07)

Reviewers: A (RT-systems), B (control theory — read the FMU equations and
verified the reference tape numerically), C (methodology), D (novelty/reject).
Full reviews in the session record. Convergent verdict: MAJOR REVISION; C4
nearly free; C1/C2 need a rebuilt instrument + derivation; C3 needs
distributional evidence + symmetric tuning + artifacts. Dispositions:

### Accepted — reshapes the section (the v2 plan in §5 implements these)

1. **Capacity is a distribution, not a threshold** (A-R3, C-O4): expose
   `--offset-seed` (at review time the `startOffsets` hook had no CLI;
   SHIPPED 2026-08-10 — results §9.7), K>=20 uniform
   phasing draws per N in [17,24], BOTH schedulers; report P(clean) vs N.
   Kills the phasing confound, the knife-edge non-monotonicity paradox, and
   single-draw anecdotes at once.
2. **The incumbent's tuning was partly inert** (A-R1): theta's 450 ms clamp
   saturates for aguard (ages >> 450) but is live for frontier. Expose
   `--theta-max` (default 450 = byte-identical) and 2-D tune (floor x
   thetaMax) BOTH schedulers; report clamp-hit fraction per run. If aguard
   reaches 21, C3 is restated as a health claim — pre-registered.
3. **Artifacts** (A-R2): `tools/fchannel_battery.py` + committed CSVs +
   `reproduce.py fbattery` (shipped names; the plan said `frontier_sweep.py` /
   `reproduce.py frontier`) for EVERY number in the section, with the full
   column set + commanded AND delivered dose + commit SHA + fidelity value
   (C-O13).
4. **Instrument rebuilt** (C-O1/O2, A-m17): two-part dose (suppress k
   publishes + sub-period delta via relaxed clamp on the releasing publish),
   realizable-dose set stated; per-cell CALIBRATION column (measured in-zone
   inter-publish gap, max+p95) — dose-based validation, not outcome-based;
   null control (unvisited zone => byte-identical) + saturation control
   (D >> arc residency => censored, reported as ">residency"). The 13.5 ms
   self-check anchor is dropped (unrealizable); the ~20 ms overlap point +
   A2-style constant-offset mode are the anchors.
5. **Units** (B-R2): A_F reported in delivered ms AND derived path-lag
   Delta-s = v*D (speed-annotated); the collapse experiment (below) tests
   Delta-a_ref = v^3*D*|dkappa/ds| as the invariant unit. ZONE_TOLERANCE's
   "curvature rate" wording for ff_ref_1 is corrected to spatial gradient
   dkappa/ds (B verified numerically: median ratio 0.988 vs ds, 8.89 vs dt).
6. **Stamp at activation** (B-R1): achieved-F-staleness origin = F's
   ACTIVATION tick (DATA_AGE §4a convention), not publish; both ages
   reported. Compliance summaries = in-zone inter-publish GAP (same unit as
   the dose) + quantiles + exposure-normalized exceedance episodes (C-O8),
   never a bare max.
7. **Feedback-channel symmetry** (A-R4, C-O3/O14): A(zone) is a COMPOSITE
   command-delay tolerance (netCA delays the merged command, co-staling F —
   PROOF_DRAFT §6 A2 note). Build `--bzone-hold-ms` (suppress B publishes,
   same mechanism) and report the triple A_composite / A_F / A_B. C1's
   "~3x heterogeneity vs the feedback path" comparison is DELETED until the
   triple exists (A-R4, B-M12).
8. **Enter-stale mode + phase battery** (C-O6, B-M5, A-m16): hold-phase and
   entry-state arms; A_F = min over phase; enter-fresh vs enter-stale gap
   reported (itself a mechanism result). All-zones-simultaneous companion
   run (the §8.2-run-(4) analogue) for the non-composability caveat (B-M8).
9. **Pre-registered predictions incl. disconfirming outcomes** (B-R4, A-m20,
   C-O17): B's first-order table (v^3|dkappa/ds| worst-case per zone
   predicts A_F NEARLY HOMOGENEOUS across z1/z2/z3, ~1.75x looser on z0 —
   contradicting the C1 draft headline) is the pre-registered H1; the
   separability null c=1 for the coupling (A-M5, both directions, 2 ms grid
   at cliffs); the §5.4 disconfirming outcome (straights exceed budget yet
   clean => A_F does not explain the win) is committed to print.
10. **The collapse experiment is the centerpiece** (B's headline, D-A9):
    zero-age reference-error injection epsilon in q = kappa + 0.2*dkappa/ds
    (harness supplies the FMU's reference inputs, so this is an additive
    knob); test breach-boundary collapse onto |Delta-a_ref| ~ a_tol; if it
    holds, A_F(s,v) = a_tol/(v^3|dkappa/ds|) is a FORMULA predicting the
    table, the profiles, and the sawtooth cells — the "derived, not swept"
    upgrade both B and D independently demanded. Sawtooth becomes the
    validation arm.
11. **Attribution matrix for C3** (D-A2, B-M11, A-M13): {RM-alloc,
    aguard-alloc} x {no F rules, STATIC zone-indexed F rates, tiered
    heartbeat}, plus matched-demand uniform-vs-tiered at v12, plus per-kind
    missed-job breakdown (does freed F budget land on B/M service?). The
    "static rates under RM" cell is the one D calls fatal if unrun.
12. **Heartbeat constants re-derived, order fixed** (A-M7, C-O9, D-A13):
    A_F measured FIRST, constants set from the table, capacity re-run as a
    held-out consequence; heartbeat-flip dose-response (straight heartbeat
    just below/above measured A_F(z0)) as the falsifiable mechanism test.
13. **Margins everywhere** (A-M9, C-O7): undecimated per-vehicle max|e_y|
    tracker + per-zone margin columns; capacity tables report distance to
    0.8 m, not binary verdicts. T1 stays 10 ms-decimated for DETECTION
    (defensible; plant is slow) but margins carry the evidence.
14. **E-ceiling restated** (A-M8): exactly one sound statement survives —
    "N <= floor(m*T_E/C_E) = 27 is a necessary condition CONDITIONAL on
    never-skipped E"; the k=2 measurement weakens the premise; "~24
    realistic" and "[21, ~27] localized" are DELETED (the record itself
    exceeds the 0.165-utilization arithmetic by dropping B/M). Bursty-skip
    eskip variant queued to test pattern-dependence.
15. **The rate-coupled vs value-typed criterion** (B-M10, D-A14): a channel
    is rate-coupled iff its consumer hard-codes a period constant (E:
    EST_STEP at LateralMotionControl.c:712 — audit: F/B/M clean). Elevated
    to a first-class claim; the k=2/k=3 knife edge derived from the
    0.98/0.02 + 0.95/0.05 blends is Kurt-facing analysis. Delay tables are
    valid ONLY for value-typed channels — the citable warning to the
    weakly-hard literature.
16. **C4 made airtight, evidence corrected** (A-m14, D-A12, B-R3.3): the
    two-run exhibit (F-hold off vs breaching dose: byte-identical age_path +
    health columns, different hard counts) replaces the confounded v1-v8
    anecdote; cite the v9 ablation only; reword "metric defect" to "defect
    of using a sensor-age metric as the sole safety proxy"; add B's
    sharpening — the estimator's stamped output has unstamped F lineage, so
    age_path certifies a contaminated signal.
17. **Misc accepted**: delete the cull from Frontier.cpp (proven no-op;
    removes the pert-oracle caveat — A-M10); T2 "+1" NOT reported as a
    claim (0.38 pp, single draw; ladder published as data — A §2); "5x
    health" restated with matched-N table + the two regressions named
    (sim-crit at own-record; low-N ages 100.5/120.5 vs RM 90.5/100.5 —
    A-M12); "guaranteed heartbeat" renamed "staleness target" unless
    measured (A-m18); the 80.5 ms sequencing result attributed to the
    abandoned v1-v8 variant everywhere it appears (A-m19); capacity
    taxonomy table (certified 8 / classical 10.5 / empirical, with P1
    status + drop rates per row — A-M13); scope all claims to v10 + A_F(z3)
    on v12.5 as the shape check, sign-stability not magnitude (C-O11,
    D-A6); fzone CSVs self-describing per C-O13; sawtooth-vs-constant
    dose-shape mapping stated before cross-validating (C §2).

### Push-backs (project context the reviewers lacked; recorded as rebuttals)

P1. **B-R3's consumer-split experiment is unimplementable here** — both F
    consumers (estimator :711, merger :774) live INSIDE the FMU and read the
    same routed value; splitting them requires editing the FMU, forbidden by
    invariant 6 (prebuilt black box). Disposition: the concern is accepted
    (the instrument perturbs command AND observer; §4's "pure data
    staleness" wording corrected), the split is documented as a limitation,
    and the observer-path contribution is bounded analytically (the 0.02
    finite-difference weight + 0.95/0.05 smoother — Kurt-facing). B's
    Factor-A (epsilon-magnitude collapse) is implementable and adopted.
P2. **A-M11 / D-A5 on `zone_flagged` as a challenger-only oracle: partially
    rebutted.** In this harness AND in the challenge's stated model,
    longitudinal position is open-loop deterministic — vehicles follow
    given reference traces with given start times (Simulation drives the
    tape by tick; lateral error cannot slow the car), and the challenge
    supplies routes + velocity profiles + start timestamps as inputs with
    context-awareness as the stated intent. Future zone membership is
    therefore map+clock knowledge, computable offline with ZERO position
    estimation — not a state oracle, and its accuracy does NOT degrade with
    data staleness. zband (a committed, documented policy) already consumes
    the same field. Accepted remainder: this rests on the
    no-longitudinal-coupling model assumption, which will be stated
    prominently (B's independent point), and the honest-position variant
    (flag from delayed estimated position) will be run once as a
    sensitivity row, not as the headline.
P3. **C-O10's demanded "aguard + F-demotion arm" already exists — it is
    frontier v12 itself** (aguard allocation verbatim + F rules; both-off
    anchor byte-identical to aguard). Disposition: reframed in the text —
    the +2 IS the transfer of F economics to the incumbent's allocator; the
    tuning-ledger half of O10 is accepted (per-scheduler config counts
    published).
P4. **D-A16 (folklore) and D's Kundu-Quevedo fold-in: rejected on D's own
    analysis** — blanket-demote fails AND blanket-protect fails (v9/v11);
    only the zone tier works; "run the planner slow" does not predict that.
    Kept in the rebuttal bank for the paper.
P5. **C-O2's "no outcome-based checks at all" softened**: outcome anchors
    are retained as SECONDARY (they catch harness regressions cheaply) but
    are never the validation of record; the delivered-dose calibration
    column is (accepted as the primary, per C's own insistence).

### The reframed claims (post-council; supersede §1 wording)

- **C1'** (was C1): A(context) is a vector over channels. Evidence: the
  A_composite/A_F/A_B triple + the collapse formula with residuals + the
  pre-registered homogeneity test. The zone-ordering inversion already in
  A(zone) (z1 slight-curve = 400 most tolerant; z2 sharp = z0 straight =
  290; z3 lane-change binding at 140/170) is led with: REFERENCE MOTION,
  not curvature level, prices tolerance — falsifying the challenge's own
  rule of thumb (D's antidote).
- **C2'**: separability is the null; "surface" claimed only if c != 1 with
  sub-grid resolution, two zones, both directions; scoped one-plant (the
  cart-pole's F channel is null by construction — CartPolePlant.cpp:77).
- **C3'**: distributional capacity (P(clean) vs N curves, symmetric 2-D
  tuning, honest-position sensitivity row), attribution matrix, artifacts;
  sign-stability across profiles claimed, magnitudes not; outside-P1 scope
  labeled wherever a capacity number appears.
- **C4'**: the two-run exhibit + the inherited-blindness statement
  (sensor-rooted chain metrics generally) + the contaminated-certificate
  sharpening; framed as a scope warning, novelty claimed only via C1'/C15.
- **NEW C5** (was buried): the rate-coupled/value-typed channel criterion +
  the eskip negative result — delay-tolerance tables do not license
  rate-reduction on rate-coupled channels.


## 9. Measured results (batch 1: 2026-08-10; batch 2 = findings 9-11: 2026-08-11)

Standard unless a finding says otherwise: N=1, 120 s (full lap per profile),
worst exec, breach-anywhere, zone-targeted sustained holds; the capacity cells
carry their own configs per row. CSVs — batch 1: fzone_tolerance.csv,
bzone_tolerance.csv; batch 2: fzone_enterstale.csv, qzone_collapse.csv,
fzone_tolerance_z3_v12.5/_v15.csv, pclean_battery.csv, tuning_grid_n20.csv,
attribution_matrix.csv, coupling_grid.csv — all regenerable via
`reproduce.py fzone / fbattery / qzone`.

| zone | A_composite (netCA) | A_B (feedback hold) | A_F (reference hold) |
|---|---|---|---|
| z0 straight | 290 | [400, 600) | > 1200 (range top; margin flat) |
| z1 slight | 400 | [600, 800) | > 1200 (margin 0.34->0.62) |
| z2 sharp | 290 | [400, 600) | [1000, 1100) (breach manifests in z1) |
| z3 lane-change | 140 (packet) / 150.5 min-over-phase of record (HANDOFF "Numbers of record") | [300, 350) | [240, 260) |

Key findings, each machine-checked:
1. **Different zone-orderings per channel.** A_B reproduces the composite's
   ordering exactly — including the z1>z0 anomaly (PAPER_NOTES 2026-06-26),
   now localized to the FEEDBACK channel — while A_F is ordered by reference
   motion (z3 << z2 < z1 ~ z0). The binding channel flips by zone: F binds in
   the lane change (240 < 300), B binds everywhere else. Reviewer B's
   near-homogeneity prediction refuted (pre-registered outcome (ii)); the
   first-order amplitude model needs the exposure integral.
2. **Separability rejected, c ~ 0.25** (coupling grid, session log): under a
   200 ms uniform B-hold the lumped-budget null predicts A_F(z3) ~ 50 ms;
   measured > 200. 300 ms of B costs only 60-80 ms of z3 F-budget. Channels
   are far more independent than one command-staleness budget — per-channel
   budgeting is a real scheduling lever. (Formalized 2026-08-11:
   coupling_grid.csv, `fchannel_battery.py coupling` — every recorded cell
   reproduced exactly.)
3. **Failure modes differ qualitatively**: F-loss = bounded geometric drift
   (max|e_y| grows smoothly with dose); B-loss = instability (uniform 400 ms:
   4.15 m excursion; 600 ms: FMU numerical divergence).
4. **C4 exhibit (two runs)**: baseline vs z3-300 ms F-hold — IDENTICAL
   age_path (90.50) and age_fresh; 0 vs 24 hard frames. A breaching quantity
   invisible to the certified metric, by construction.
5. **Frontier compliance is exposure-based, not max-based** (N=21 m100):
   z3 exceedance >500 ms = 0.8% of in-zone ticks (peaks 1262 = entry
   transients) vs straights 39% (budget > 1200) — the slack is spent where
   it exists. Undecimated margin at the record: max|e_y| = 0.7702 m
   (29.8 mm to the bound) — the +2 is real but knife-edge, hence the
   phasing-distribution battery (in progress).
6. **Calibration discipline held**: delivered dose = commanded + R_F within
   2.3 ms in all 92 cells across both channels; cross-zone leakage visible
   and quantified in the delivered columns.
7. **Capacity as a distribution (council A-R3) — the +2 survives.** Random
   phasing draws (--offset-seed), 10 seeds per cell, 120 s, honest configs
   (frontier m100 / aguard m80), three phasing families (unspaced, F_spaced
   s=1 s, s=4 s). Frontier's P(clean) DOMINATES in every family at every
   N >= 14, with the gap widest at the wall: at N=20 frontier is clean in
   5/7/8 of 10 draws (fail mass: tens of frames) vs aguard 0/0/1 (fail
   mass: 64k-112k). Tuning grid at N=20: frontier 9/9 clean at floors
   100/140; aguard 0/9 at every floor. The guard-cap axis is PROVABLY INERT
   for honest policies (est-TTPNR <= horizon - margin < 450), refuting
   council A-R1's saturation asymmetry with a mechanism. aguard's known
   N=14 margin fragility reproduces across phasings (2-5/10); frontier has
   no such pothole. Raw logs: committed under `fchannel_rawlogs/` (see its
   README, incl. the hard-vs-soft parsing caution); formalized 2026-08-11
   into pclean_battery.csv / tuning_grid_n20.csv via `fchannel_battery.py`
   (--jobs parallel; 358-check cross-validation vs the raw logs: every
   hard+soft count identical).
   **Analysis-erratum (recorded per the §3 discipline): the first
   tabulation of these logs summed hard+soft fields (an awk regex matching
   both blocks), yielding a false "P(clean)=0/10 everywhere" narrative for
   ~1 hour before a direct probe caught it. Only chat-level reporting and
   one (now-fixed) code comment carried it; no committed number was
   affected. Lesson: validate the parser against one hand-checked run —
   the analysis pipeline is an instrument too.**
8. **Attribution matrix (council D-A2 — the "fatal if unrun" cell) —
   BOTH levers load-bearing.** Full-lap default-spread capacity (0 hard,
   uniform-clean-through):
   RM alloc + no F economics = 10; RM alloc + zone-aware F economics = 14
   (clean 12/14, breaks 16 with 733; CPS_FRONTIER_RM_ALLOC cell);
   triage + no F economics (aguard) = 19; triage + F economics (frontier)
   = 21. Static F economics alone is +4 over classical but 7 short of the
   record; the levers are complementary (interaction sublinear: +4 on RM,
   +2 on aguard). "The win is just deleting redundant F recomputation" is
   refuted by measurement. (Formalized 2026-08-11: attribution_matrix.csv,
   all four cells over bracketing N grids; the rm-alloc rows reproduce the
   raw log exactly, incl. missed F=29143 at N=12.)
9. **Enter-stale phase battery (C-O6/B-M5) — enter-fresh is the BINDING
   phase at the cliff; the A_F table survives as a min-over-phase
   quantity.** New arm `--fzone-lead-ms L`: the hold pre-arms while the car
   is within L ms BEFORE the target zone (zoneAt lookahead — tape+clock
   knowledge, exactly §8 P2's argument), so it enters carrying an already-
   aged value at MATCHED peak dose: entry age ~= min(L, D), republish
   D−L after entry (the suppression sawtooth caps age at D everywhere).
   Grid D {200..300} x phase {0,.25,.5,.75}D, z3 (fzone_enterstale.csv):
   every phase clean through 240; at 260 ONLY enter-fresh breaches (10 hard
   vs 0; stale phases peak ~0.79 m); at 280-300 all phases breach and
   severity GROWS with entry staleness (300 ms: 24 -> 37 hard). Mechanism:
   the fresh capture holds start-of-maneuver geometry for the full dose
   INSIDE the maneuver — in-zone exposure duration dominates value age
   until well past the cliff. A_F(z3) = [240, 260) unchanged; §2's
   enter-fresh label is the conservative arm at the cliff. The whole
   battery reads age_path = 90.50 = baseline (C4 yet again).
   All-zones-simultaneous companion (B-M8): a UNIFORM 240 ms hold (the
   binding zone's budget, everywhere) stays clean at margin 12.3 mm (vs
   73.5 mm z3-only) — min-budget composition holds for the F channel,
   barely; the per-zone-VECTOR dose (each zone at its own budget) remains
   untested (scalar instrument).
10. **qzone collapse (reviewer B Factor A, §8 item 10) — the amplitude
   unit does NOT collapse; the pre-registered v^-2 scaling is REFUTED
   (disconfirming outcome, committed to print per §8 item 9).** Signed
   zero-age curvature errors eps, 12 magnitudes x both signs x 4 zones x 3
   profiles (qzone_collapse.csv): eps*(z3, v10) = [0.16, 0.20) 1/m — an
   ORDER OF MAGNITUDE above the naive transfer a_tol/v^2 ~= 0.014 from the
   delay cliff, and ~4x the sharpest real route curvature (0.0519).
   eps* is roughly zone-flat but falls FASTER than 1/v^2 across profiles
   (bracket-midpoint exponent ~ v^-3). Reading: a sustained DC curvature
   error is largely rejected by the feedback loop (B trims it); F-staleness
   damage comes from the MOVING transient during reference motion —
   consonant with finding 9's exposure mechanism and the c~0.25 coupling.
   Delta-a_ref = v^2*eps is NOT a valid cross-form dose unit: amplitude
   tolerance and delay tolerance are different quantities (C5's
   channel-typing caution, now with an in-house exhibit). Sign asymmetry:
   z3 tolerates -eps ~1.5x more than +eps at v12.5/v15 (the lane change
   has a direction).
11. **Cross-profile A_F(z3) (C-O11) — sign-stable, and the v^3|dkappa/ds|
   unit is a working UNDER-bound at held-out profiles.** Measured cliffs:
   v10 [240, 260) / v12.5 [160, 180) / v15 [120, 140)
   (fzone_tolerance_z3_v12.5/_v15.csv) — monotone tightening with speed,
   z3 still binding. First-order prediction A_F_lb = a_tol /
   max(v^3|dkappa/ds| in zone), a_tol fitted ONCE at (z3, v10) (per-zone
   kinematics now printed by tools/proofchecks/zone_probe.cpp: max(v^3
   |ff1|) = 4.59 / 8.97 / 15.5 across profiles): predicts [123, 133) at
   v12.5 and [71, 77) at v15 — BELOW the measured cliffs both times
   (conservatism 1.3-1.7x). Conservative in the safe direction at both
   held-out profiles => usable as the analytic-A_F_lb leg's empirical
   anchor. Claim scope per C-O11: the sign/under-bound property only;
   magnitudes stay per-profile.

## 10. Queued (next session; NOT blocking the section's evidence)

*(The 2026-08-10 queue — CSV formalization + reproduce registration, qzone
collapse, enter-stale dosing, cross-profile sign check — is DONE, findings
§9.9-9.11. Remaining + follow-ons:)*

- Analytic a_tol from the plant model (turn §9.11's fitted constant into a
  derived one) — the remaining analytic-A_F_lb step; EE-coordinated like
  Condition I.
- Coupling surface at C2' standard: sub-grid resolution at the cliffs, both
  directions, a second zone; per-zone VECTOR F dose (needs a
  --fzone-hold-vector analogue of --zone-extra-vector) for the §9.9
  composition remainder.
- Bursty-skip eskip variant (pattern-dependence of the E ceiling, §8
  item 14).
- Honest-position zone_flagged sensitivity row (§8 P2 remainder).

