# Paper Notes — running log of paper-worthy observations

A scratchpad for "worth a sentence in the paper" moments: findings, framings,
and cautions surfaced while working, before they're polished into paper
prose (target: the main-track paper, HANDOFF §1 plan of record). **Not** a formal doc — claims here still need the usual verification
(`BOUND.md` invariants, Kurt sign-off) before they leave this file. Each entry:
what it is, the evidence/repro, and where it would land.

Newest first.

---

## 2026-09-04 (b) — The A2 correction is binary and within one instrument step: a period-old F at the Estimator moves A(z3) by ≤ 3 mm at the threshold; the min-over-phase constants stand (with two stated assumptions)

**What it is.** PROOF_DRAFT §8.3 measured, at a single phase, that delaying
every F publish by 13.5 ms (the N=8 certificate's worst F lateness) moves the
v10 z3 cliff 170 → 160, and paper/PLAN.md §3 flagged that the F-demoted
comparison must use an F-corrected budget. Re-measured min-over-phase (21
phases) at two doses: 13.5 ms and the P1 boundary (20 ms commanded; the
instrument clamps the publish to the tick before F's next release, delivered
act-stamped F age 22.3 → 39.8 ms). Four results.

1. **The F-lateness effect is binary, and the consumer that flips is the
   ESTIMATOR, not the Merger** (cold review 2026-09-04; reproduced). Added
   publish delay up to 7.5 ms changes nothing (v10 z3 +80, phase 0: max |e_y|
   0.7983, 0 hard); from 8 ms to the P1 boundary every outcome is identical
   (0.8032, 7 hard). Mechanism, pinned to the tick: under N=1 RM (3 cores; tie
   order period, vehicle, kind with Controller < Feedforward < Merger) E, C
   and F all start at tick 0, C finishes at tick 4, so the Merger activates at
   tick 5 — BEFORE F publishes at tick 24 (C_F = 2.5 ms worst). The Merger
   therefore reads a one-period-old F at every dose, including zero. What
   flips is the Estimator's second job of each 20 ms period: it activates at
   tick 100 and reads `ff_out` for its e_y-rate estimate
   (`LateralMotionControl.c:711`). 24 + 76 = 100, and the threshold sits at
   exactly 76 → 77 ticks of added delay (v12.5 z3 +60 phase 19.9: 0.8017 m /
   5 hard at 7.6 ms, 0.7987 / 0 at 7.7). Decisive cross-check on a single
   core (`--scheduler prm`: E 0–10, C 11–15, F 16–40, M 41–45): the same cell
   shows THREE plateaus — 0.6935 m (Merger reads fresh F), 0.7683 (Merger
   period-old, Estimator fresh), 0.7646 (both period-old) — flipping at
   0.1 → 0.2 ms and 6.0 → 6.1 ms, exactly where that schedule predicts. So
   the A2 instrument samples the two Estimator-read regimes with the Merger
   pinned in its period-old regime; the certificate-dose and P1-boundary
   tables are identical row for row (231/231 v10, 231/231 v12.5, 168/168
   v15). The N=8 certificate is in the late Estimator regime (R_F 185 ticks
   F-demoted, limited-t); classical RM at N=8 spans both (R_F 63–183 across
   vehicles). Not a "merger-grab twin": the 2026-08-24 merger-grab is the
   controller output merged late; here the Merger's F read is period-old by
   construction of the nominal N=1 RM order.

2. **Numbers (F merged one period late, hard criterion, 21 phases):**

   | profile | A(z3), late-F regime | nominal (fresh-F) regime | difference at the cliff cell |
   |---|---|---|---|
   | v10 | 150.5 (17/21 clean at 160.5; worst phase 15 hard) | 150.5 (18/21; 13 hard) | +5 mm |e_y| at 160.5 |
   | v12.5 | **150.5** (21/21 at 150.5, max |e_y| 0.7987; 2/21 at 160.5) | **140.5** (phase 19.9 breaches 150.5 by 1.7 mm) | −3 mm: the staler F is MORE tolerant |
   | v15 | 110.5 (14/21 at 120.5) | 110.5 (14/21) | 0 at 120.5 |

   Within one instrument step everywhere, and not monotone. §8.3's 170 → 160
   was a phase-0 effect: the nominal phase-0 value sits 1.7 mm under the
   threshold and 5 mm of extra excursion tips it; at the worst phase the two
   regimes coincide.

3. **Certified constants — and precisely what they cover.** Stone's
   decision (2026-09-04): the certified constant is the min over the measured
   F regimes: **A(z3) = 150.5 / 140.5 / 110.5 ms (v10 / v12.5 / v15)** —
   unchanged from the nominal min-over-phase values. Every boundary statement
   stands as written (v10 at the boundary by 1.1 ms; v12.5 below it by
   11.1 ms). Coverage: both Estimator-read regimes (F fresh / F one period
   old at E's second job) under CONSTANT F lateness, with the Merger reading
   a period-old F — the order the certificate schedule shares inside the zone
   by construction (F-demoted band: M elevated above F with the same
   release, so M activates before F can finish) and classical RM at N=8
   shares wherever R_M < R_F. Two things the tables do NOT cover, stated as
   assumptions rather than waved: (a) the third regime — the Merger reading
   a FRESH F — which the N=1 RM instrument cannot produce; on the one cell
   probed (prm, v12.5 z3 +60 phase 19.9) it is worth 7.5 cm in the BENIGN
   direction (0.6935 vs 0.7683 m), twenty times the Estimator effect;
   (b) per-job MIXING of the two Estimator regimes, which N=8 has (solver R_F
   63–183 ticks across vehicles, R_E up to 44, so consecutive F jobs land on
   both sides of E's read point) — the min over two constant-lateness tables
   bounds a mixed sequence only under a monotonicity assumption that v12.5's
   result (staler F MORE tolerant by 3 mm) does not support. Both are
   millimetre-scale on every cell measured and neither moves a constant at
   the instrument's 10 ms resolution. The per-schedule A2 correction is
   RETIRED (no measured regime moves any constant by an instrument step);
   PROOF_DRAFT §8.3/§8.5's "160" is retired; PLAN.md §3's "fold A2 into the
   constant?" is moot. Open (Stone): whether to build a per-job lateness
   instrument to close (b) empirically.

4. **Comfort under late F.** A_soft (hard-clean AND soft% ≤ 5 at every
   phase): v10 120.5 (unchanged); v12.5 none — the uninjected baseline at the
   worst phase is already 5.04 % with late F (4.99 % fresh); v15 none
   (baseline 9.2–12.5 %). One more line for the limitations paragraph: at v12.5
   the comfort budget is exhausted by N=8 contention alone.

**Evidence / repro.** `tools/zone_sweep.py --ff-extra-ms 13.5|20 --phases-ms
0:20:1` (phase mode only; the delivered dose is recorded per row as
`f_stale_max_ms`, the commanded one as `ff_extra_ms`; the six existing phase
tables were regenerated with those two provenance columns, content
identical, legacy tables byte-identical). Six new CSVs
`zone_tolerance_z3_a2cert_phase{,_v12.5,_v15}.csv` and
`zone_tolerance_z3_a2p1_phase{,_v12.5,_v15}.csv`; `reproduce.py zones`.
Decimated/undecimated agreement: 1,260/1,260 rows. Threshold probe: ff 1..7.5
nominal, 8..25 saturated (v10 z3 +80 phase 0); pinned at 7.6 → 7.7 ms on
v12.5 z3 +60 phase 19.9. Solver R_F: `solve_rta` on `build_cloud_tasks(8,
worst, top_k=8, demote_f=True)` under limited-t gives max R_F 185 ticks
(classical N=8: 63–183 across vehicles; N=1: 35). Dose label: 13.5 ms is
§8.3's demotion delta (R_F 48 → 183 under its earlier figures); the
limited-t figures 35 → 183/185 imply 14.8–15.0 ms — both saturate, no
consequence. Note `f_stale_max_ms` is the age of F's output register
(22.3 + D, clamped at 39.8); it does not say which Estimator regime a row is
in — the threshold does.

    for ff in 0 7.5 8 13.5 20; do ./build/cps --headless --vehicles 1 --scheduler rm \
        --exec worst --duration 120 --profile 10 --zone-target 3 --zone-extra-ms 80 \
        --start-offsets-ms 0 --ff-extra-ms $ff; done       # 0.7983 x2, then 0.8032 x3

**Where it lands.** Retires the A2 correction as a separate step. Methods:
one sentence on the two Estimator-read regimes and the Merger order shared
with the certificate. Limitations: the unmeasured fresh-Merger regime, per-job
regime mixing at N=8, and v12.5's comfort budget under late F.

---

## 2026-09-04 — A(zone) is a min over the chain phase: 21-phase enumeration; every published single-phase value was the LUCKIEST phase; new numbers of record

**What it is.** The 2026-08-24 refutation (paper/PLAN.md §3) found that v10's
A(z3) = 170.5 ms survived at 1 of 20 random start offsets. This entry closes
it: the phase dependence is understood, exhaustively enumerated with a new
instrument, and committed as the A(zone) tables of record. Five results.

1. **The phase axis is the chain hyperperiod (20 ms), and it is lap-invariant.**
   Start offsets that differ by a multiple of 20 ms give identical breach
   counts (0 / 20 / 40 / 60 / 200 / 1000 / 5000 ms: all clean at z3 +80 on v10,
   max |e_y| within 1.7 mm of each other); offsets 1..19 ms breach with
   monotonically growing hard counts (7, 11, 18, 26, 31, 41 at 1, 2, 5, 10, 15,
   19 ms) and 19.9 ms is the worst (43 hard, 0.9049 m). The three lap lengths
   (1,178,000 / 944,000 / 786,000 ticks) are multiples of 200 ticks, so the
   chain-release phase at a given track index is the same on every lap: the
   quantity being sampled is the phase of the E/B/F/M releases relative to the
   instant the in-zone injection starts. (A 60 ms secondary structure exists at
   the 1-2 mm level — offsets 20/40/60 ms cycle 0.8000/0.7987/0.7983 m — and is
   irrelevant at the instrument's 10 ms age resolution.) The effect is
   monotone in phase across the half-open hyperperiod [0, 20): at all eight
   partially-clean cells in the tables below, the clean phases are exactly the
   lowest k. The enumeration of record is therefore the 1 ms grid PLUS the
   interval's last representable tick, 19.9 ms (`--phases-ms 0:20:1` → 21 runs
   per grid point; the tool appends the last tick itself). **Phase 0 — the
   seed-0 / lap-index-0 phase every committed table used — is the BEST phase at
   every grid point on every profile**, and 19.9 ms the worst (checked: best =
   0 at all 30 z3 cells; worst = 19.9 at 26 of them and 19.0 at v12.5's four
   fully-breached cells). Every published A(zone) was therefore the max over
   phase, not a typical value. **Cold-review lesson (same day):** the first
   pass used the 0..19 grid without 19.9 and reported v12.5's A(z3) as 150.5;
   the sup breaches that cell at phase 19.9 by 1.7 mm (0.8017 m, 5 hard
   frames). A phase grid that stops one step short of the interval's end
   under-reports A(zone) — the tool now refuses to. The 08-24 "19 of 20
   seeds breach" follows: random lap offsets are uniform in phase, and only
   ~1 ms of the 20 ms window is clean at 170.5.

2. **Numbers of record** (hard criterion, breach-anywhere, 21 phases,
   delivered ages quantised at 10 ms; "robust" = 21/21 clean at the published
   value and 0/20 at the next coarse step — z0-z2 were bracketed on the 50 ms
   coarse grid only):

   | profile | z3 lane-change | z0 straight | z1 slight | z2 sharp |
   |---|---|---|---|---|
   | v10 | **150.5** (was 170; per-phase 150.5..170.5; 18/21 clean at 160.5, 1/21 at 170.5) | 290.5 robust | 400.5 robust | 290.5 robust |
   | v12.5 | **140.5** (was 160; 140.5..160.5; 20/21 clean at 150.5 — phase 19.9 breaches by 1.7 mm; 1/21 at 160.5) | 290.5 robust | 240.5 robust | **190.5** (was 240; 17/21 clean at 240.5) |
   | v15 | **110.5** (was 120.5 [08-24 fine grid], 90 [coarse]; 110.5..120.5; 14/21 clean at 120.5) | 240.5 robust | **190.5** (was 240; 7/21 at 240.5) | **140.5** (was 190; 10/21 at 190.5) |

   So PLAN.md's 08-26 scope statement ("confined to z3 on v10") holds on v10
   and fails on the faster profiles: the tighter the zone or the faster the
   car, the wider the phase spread (two 10 ms fine steps on v12.5's z3, one
   50 ms coarse step on the affected non-z3 zones). z0 is phase-robust
   everywhere.

3. **The boundary claim: v10 sits AT the boundary; v12.5 is clearly below
   it.** The uniform F-demoted N=8 bound is 151.6 ms (limited-t candidate).
   On v10, against A(z3) = 150.5, it is NOT certified — by 1.1 ms; 18/21
   phases are still clean at 160.5, so the worst-phase cliff lies in
   [150.5, 160.5) and the instrument cannot say on which side of 151.6 it
   falls. Certification uses the verified value, under which the
   decomposition IS load-bearing at N=8, and the margin is below the
   instrument's 10 ms resolution, so the paper presents v10 as "at the
   boundary" — the same shape as v15's applicability floor. On v12.5, against
   A(z3) = 140.5, the bound misses by 11.1 ms — more than one instrument step
   — so the uniform mechanism is unambiguously insufficient there and the
   decomposition is load-bearing without qualification. The corollary flip
   PLAN.md feared is real, and it is no longer a coin toss on v12.5. **The
   conservative packet constant A(z3) = 140 (THEOREM_BRIEF / BOUND /
   PROOF_DRAFT Lemma-2 packet) survives at every phase on v10 and v12.5**
   (140.5 clean 21/21 on both — on v12.5 by exactly one instrument step); on
   v15 it does not (110.5), which changes nothing (v15 was already the
   floor). QUEUED, not done: the A2 correction (F-demotion's +13.5 ms of
   feedforward staleness moved the single-phase v10 cliff 170 → 160,
   PROOF_DRAFT §8.3) must be re-measured min-over-phase (`--ff-extra-ms 13.5`
   × `--phases-ms 0:20:1`) before an F-demoted schedule is compared against
   anything; expect ≤ 150.5.

4. **The soft constraint binds far earlier, and nothing was checking it.**
   ZONE_TOLERANCE.md's definition of A(zone) includes the Challenge's soft
   constraint (|e_y| ≤ 0.2 m for ≥ 95 % of the run; examples/constraints.md),
   but `zone_sweep.py` only ever tested `total_hard == 0`. Polarity confirmed
   in code (`Simulation.cpp:707`: soft% = share of the run OVER 0.2 m, so ≤ 5
   passes). The phase CSVs now carry `soft_pct` per row and the tool reports
   a secondary A_soft (hard-clean AND soft% ≤ 5 at every phase). Results:
   v10 z3 A_soft = 120.5 ms (soft 4.56..5.41 % at 130.5) against hard 150.5;
   v12.5 z3 A_soft = 90.5 (the uninjected baseline is already 3.15..4.94 %
   and +10 ms pushes the worst phase to 5.46 %); **v15 violates the soft
   constraint with NO injection at N=1 (9.06..12.19 %)** — the nominal v15
   system is outside the Challenge's comfort envelope regardless of
   scheduling. v10 z1/z2: A_soft 250.5 / 240.5 against hard 400.5 / 290.5;
   z0 and the v12.5/v15 spot ranges start above their soft crossings
   (A_soft unresolved there). **DECIDED (Stone, 2026-09-04): A(zone) is
   certified against the hard constraint only; the soft data is reported as
   a stated limitation** — the comfort budget is whole-run, not per-zone, so
   a zone budget derived from it would be a design choice rather than a
   physics fact, and certifying against it would leave only v10 inside the
   framework. The sustained-vs-transient caveat (2026-08-24 item 4) applies
   to soft% exactly as to hard.

5. **Instrument facts.** (a) The frame-decimated hard counter and the
   undecimated per-tick max |e_y| agreed on every one of the 1,449 new rows
   (no row with hard = 0 and max |e_y| ≥ 0.8, or the reverse), so the standing
   "hard counts are lower bounds" pitfall did not bite at any measured cliff.
   (b) Delivered age is identical across phases — the phase changes the
   outcome, not the dose. (c) Worst-phase breaches at the non-z3 cliffs
   manifest in *other* zones (v12.5 z2's first breach lands in z1; v15 z1's in
   z1 + z2) — the manifestation-vs-cause distinction of 2026-06-26 again.

**Evidence / repro.** New harness flag `--start-offsets-ms A[,B,..]`
(main.cpp; explicit per-vehicle lap offsets; byte-identical when absent —
G1/G2 unchanged) + `tools/zone_sweep.py --phases-ms 0:20:1 --jobs 8`
(a range spec always gets the interval's last tick appended; `--offset-seeds
K` = the random lap-position sampler of 08-24, kept for reproducibility;
legacy single-phase mode byte-compatible — the five legacy tables regenerated
byte-identically through the new tool; unit-tested in
`tools/tests/test_zone_sweep.py`, gate G0). Committed:
`zone_tolerance_z3_phase{,_v12.5,_v15}.csv` (z3, extra 0..100 / 0..100 / 0..70
ms at 10 ms, 21 phases) and `zone_tolerance_spot_phase{,_v12.5,_v15}.csv`
(z0-z2, coarse brackets, 21 phases); `reproduce.py zones`
regenerates all six (~3 min at 8 jobs). The legacy single-phase tables are
untouched and byte-reproducible; they are now the phase-0 (max-over-phase)
reference.

    # mechanism (v10, z3, +80 ms): multiples of 20 ms clean, 1..19.9 ms breach
    for o in 0 20 1000 1 10 19 19.9; do ./build/cps --headless --vehicles 1 \
        --scheduler rm --exec worst --duration 120 --profile 10 \
        --zone-target 3 --zone-extra-ms 80 --start-offsets-ms $o; done
    # tables of record (the six zone_sweep.py lines in reproduce.py exp_zones)
    python3 tools/reproduce.py zones

**Where it lands.** Item 1 is a methods paragraph (phase enumeration is part
of the A(zone) definition from now on) and a specificity asset (paper/PLAN.md
§5 item 8: the luckiest-phase table). Item 2 replaces every A(zone) number in
THEOREM_BRIEF §3.2 / PROOF_DRAFT §8.1 / ZONE_TOLERANCE / paper/PLAN.md §3.
Item 3 rewrites PLAN.md §3's regime table (v10 at the boundary, v12.5 below
it). Item 4 is a limitations paragraph or a second table, depending on
the soft decision. The FCHANNEL A_F min-over-phase (§9.9, entry phase via
`--fzone-lead-ms`) and this chain-phase enumeration are different phase axes;
both are needed.

---

## 2026-08-24 — The merger-grab: F-demotion tightens the bound and worsens the realized age by 20 ms (car survives with 49.5 ms; cart-pole dies at N=1) — plus the cart-pole is a second applicability-floor case

**What it is.** A cart-pole analogue of the PROOF_DRAFT §8.5 boundary question
("does occupancy earn capacity, or does uniform F-demotion already suffice?")
turned up a mechanism defect in the uniform F-demotion lever itself, then a
verification run confirmed the car's central claim survives it. Six results,
ordered by how much they move the paper.

1. **THE MERGER-GRAB (mechanism).** Demoting Feedforward below every vehicle's
   E/B/M frees a core slot that the **Merger takes in the same tick as its own
   Controller**, so it merges the *previous* controller output. `TaskModel.cpp:
   368-370` snapshots `fbOutStamp_` at `merge_act`; if M activates before its
   own B publishes `fb_fin`, the merged stamp — and the merged *value* — is one
   controller period old. Cost: **exactly +20.0 ms (= T_B) of realized
   `age_path`**, on both plants, at every N tested.
   **Isolating experiment, no scheduler involved:** give plain RM a fourth core
   at N=1 and realized `age_path` rises **90.5 → 110.5 ms** (identical at 5 and
   6 cores). *Adding a core makes the delivered age worse* — and on the
   cart-pole it makes safety worse: 0 → **10,831 hard-breach frames**, the pole
   falls (|θ| → 223 rad). The car at 4 cores is unharmed (0 hard). This is a
   property of the Challenge's own register-routing semantics (the merger reads
   whatever is in the register; it does not block on a fresh input), not a
   harness bug.

2. **The car's boundary claim SURVIVES, with 49.5 ms of realized margin.**
   Verification run (lateral v10, N=8, `--exec worst`, 3 cores, 120 s):

   | | classical RM | uniform F-demoted |
   |---|---|---|
   | `missed jobs` (P1) | 0 | **0 — P1 HOLDS** |
   | worst `age_path` | 90.5 ms | **110.5 ms** (+20.0) |
   | hard breaches, all zones | 0 | **0** |
   | hard **z3** | 0 | **0** |
   | `K_age(τ=1.0)` max | 0 | 0 |
   | fleet max \|e_y\| | 0.4133 m | 0.4284 m |

   So the merger-grab is real on the car too, and it does **not** threaten
   §8.5: realized 110.5 ms against the A2-corrected cliff of 160 leaves
   **49.5 ms of realized margin**, where the analytic comparison (151.6 vs 160)
   leaves only 8.4 ms. Realized age sits 41.1 ms *below* the top-band bound.
   Not a counterexample.
   **Secondary:** F-demotion lowers the car's *empirical* P1 ceiling from 10 to
   9 (N=10 F-demoted: 2,377 missed, first hard breaches z1=67 z2=262, where
   classical RM at N=10 is 0 missed / 0 hard) while raising the *certified* one
   from 5-6 to 8. The two ceilings move in opposite directions.

3. **Bound/reality divergence — the beyond-worst-case trap, exhibited.**
   F-demotion **tightens the analytic age bound** (band-mode, limited-t:
   N=1 125.2 → 123.4 ms; N=8 192.2 → **151.6** ms) while **worsening the
   realized age** by 20 ms (90.5 → 110.5). Measurement stays under the bound at
   every point (110.5 ≤ 123.4 at N=1, ≤ 151.6 at N=8), so **this is NOT
   unsoundness** — the classical bound was simply loose where reality was
   lucky. State it precisely: a mechanism whose bound-effect and reality-effect
   point in opposite directions is exactly the beyond-worst-case hazard this
   project exists to study. On a plant with 15 ms of slack it flips a safe
   fleet into a crashing one; on the car, whose slack is 80 ms, it is invisible.

4. **Sustained ≠ transient — a caveat on every A(zone) number we publish.**
   The tolerance instrument injects *sustained uniform* delay; schedulers
   produce *transient maxima*. These are not interchangeable and the cart-pole
   proves it in both directions: **110.5 ms sustained kills the pole** (9,954
   hard frames at `--net-delay 26`), while under aguard at N=16 every one of
   the 16 poles runs at a worst-case `age_path` of **470-895 ms with zero hard
   breaches** (max |θ| 0.171 vs the 0.21 bound) — 4-8× "over budget", harmless,
   because the staleness lands outside the shove windows. Every A(zone) in
   `ZONE_TOLERANCE.md` / FCHANNEL is a sustained-injection quantity and must be
   labelled as such; PROOF_DRAFT §8.7's "injection is strictly harsher than
   reality" is the car-side statement of the same thing, and here it is
   load-bearing rather than reassuring.

5. **The cart-pole is a SECOND applicability-floor case — reached by physics,
   not by speed.** Re-measured at 120 s: **A(cart-pole) ∈ (105.5, 110.5] ms**
   delivered `age_path` (105.5 → 0 hard; 110.5 → 9,954 hard). Measured
   uncontended chain latency is **90.5 ms** — identical to the car, since the
   chain model is plant-agnostic — so there is ~15 ms of empirical slack. But
   the *analytic* uncontended bound is 120.8 ms (`BOUND.md` §5) / 123.4 ms
   (F-demoted, band N=1) / 125.2 ms (classical), **all above the budget**: no
   scheduling policy certifies even ONE cart-pole at these task periods. This
   is the v15 result (PROOF_DRAFT §8.1) on a second plant, and it arrives for a
   different reason — instability rather than speed. For the scope section: the
   floor is a property of the *chain*, and a plant either clears it or the
   scheduling question is vacuous.
   Corollary for the §8.5 boundary question: the decomposition is **not**
   load-bearing for the cart-pole. Its uniform-mechanism failure happens at
   **N=1, with zero contention**, and nothing that reallocates contention can
   recover that. Two further blockers, both structural: every zone injection
   path is gated `plant == PlantKind::Lateral` (`Simulation.cpp:363, 379,
   393-395`), so no causal A(zone) exists for the cart-pole; and
   `CartPolePlant::initialize` sets `step_ = 0` for every plant with
   `disturbance(step_)` a pure function of the plant's own tick, so **all N
   poles shove in lockstep and Occ = N identically** — the occupancy premise
   (Occ < N) is false by construction.

6. **Same schedule, same ages, different consequences — the generalization
   thesis in one table.** Under state-blind policies the schedule, delivered
   ages and missed-job counts are **bit-identical across the two plants**
   (verified at N=1,2,3,4,6,8,10,11,12,14,16). At N=11 an identical trace —
   17,997 missed, worst `age_path` 100.5 ms — produces **11,408 hard frames /
   2 vehicles on the car and 11,957 / 1 on the cart-pole**. Only the physics
   differs. Instrument caveat surfaced alongside: at RM N=20 vehicles 5-19
   report `age_path = n/a` (they never actuate at all), so at P1 collapse the
   worst-case age metric is **blind to the damage channel** — the failure is
   starvation, not staleness.

**Two more, smaller.**

- **The cart-pole's budget is entirely disturbance-driven, and the 10→16 gain
  is online, not geometric.** At `--shove-force 0` the same plant tolerates
  665.5 ms of age with θ ≡ 0 and zero breaches; at 8 N the cliff is
  (105.5, 110.5]; at 6 N it sits exactly on 110.5 (36 hard); at ≤4 N, 110.5 is
  clean. So the cart-pole's "zone" is the 50 ms shove every 2 s (2.5 % duty,
  `CartPolePlant.h`) and **A(quiescent) is effectively unbounded against
  A(shove) ≈ 110 ms** — a far sharper context split than the car's 170 vs
  290/400 — but that A(quiescent) is *inferred* from a shove-free run, not
  from an in-run zone-gated injection (no such instrument exists, above).
  Classical RM keeps all poles crash-free through **N=10** (its P1 ceiling, ages
  ≤ 95.5 ms, under budget), aguard through **N=16**; the gain comes from
  *online context-conditioned allocation* (TTPNR triage), not from static zone
  geometry. That is the version of Condition II the cart-pole actually
  supports.
- **frontier crashes 7 of 8 cart-poles at N=8 — a live limitation for the
  F-channel leg.** The car's capacity champion (headline "frontier 21") is
  unsafe on plant #2: 7/8 crashed at N=8, 10/12 at N=12, 11/16 at N=16, where
  aguard crashes none. `CPS_FRONTIER_NO_FDEMOTE=1` reproduces aguard exactly →
  **0 crashes**, so zone-aware F-demotion is the sole cause (on the cart-pole
  `zone_flagged` is always false, so F is demoted everywhere and the merger-grab
  is permanent). It even *improves* the axis it was designed for — 2,714 missed
  vs aguard's 6,175 at N=8 — while crashing the plant. FCHANNEL's capacity
  claim needs a "single-plant result" qualifier until this is addressed.

**UNTESTED (inferred from utilization arithmetic only — no flag exists to run
it).** The cart-pole's F computes identically zero (`CartPolePlant.cpp:77`,
regulation), so the correct uniform mechanism for a *regulator* is to **delete**
F, not demote it: per-vehicle worst-case cloud demand falls 28.5 % → 16 % of a
core (E 1.1/10 + B 0.5/20 + F 2.5/20 + M 0.5/20), which would put RM's P1
capacity near **18** instead of 10 at zero physical cost. This also means the
F-channel economics the FCHANNEL leg studies (A_F, the cost of F staleness)
have **no cart-pole analogue at all** — the plants are not comparable on that
axis, and the paper should not imply they are.

**Evidence / repro.** All runs `--exec worst`, 3 cores, 120 s; P1 (`missed
jobs: 0`) checked and reported per row. "Uniform F-demotion" = the frontier
policy's attribution toggles with the heartbeat disabled, which yields exactly
"all non-F jobs by (period, vehicle, kind), then all F jobs" = the mechanism
`rta_solve.py --band-demote-f` analyzes.

    # (2) the car verification — P1 0, age 110.5, hard 0 in every zone incl. z3.
    # NOTE: use the assignment-PREFIX form below; `env $VAR` with the three
    # assignments in one shell variable does NOT word-split under zsh and
    # silently sets only the first (check the printed scheduler name says
    # fhb=100000000ms). The result is heartbeat-independent anyway — the
    # committed defaults (CPS_FRONTIER_RM_ALLOC=1 alone) give the same
    # 110.5 / 0 hard / 0 missed, since F is demoted but never starved.
    CPS_FRONTIER_RM_ALLOC=1 CPS_FRONTIER_FHB_MS=100000000 \
    CPS_FRONTIER_FHB_CRIT_MS=100000000 \
        ./build/cps --headless --plant lateral --vehicles 8 \
        --scheduler frontier --exec worst --duration 120
    ./build/cps --headless --plant lateral --vehicles 8 --scheduler rm --exec worst --duration 120

    # (1) the merger-grab, isolated — no scheduler involved
    ./build/cps --headless --plant cartpole --vehicles 1 --scheduler rm --exec worst \
        --duration 120 --cores 4        # age 90.5 -> 110.5, 10831 hard (cores 3 = clean)
    ./build/cps --headless --plant lateral  --vehicles 1 --scheduler rm --exec worst \
        --duration 120 --cores 4        # same age jump, 0 hard

    # (3) the bound side (read-only; writes no CSV)
    python3 tools/rta_solve.py --band 1 --band-n 1 --workload limited-t              # 125.2
    python3 tools/rta_solve.py --band 1 --band-n 1 --band-demote-f --workload limited-t  # 123.4
    python3 tools/rta_solve.py --band 8 --band-n 8 --band-demote-f --workload limited-t  # 151.6

    # (4)+(5) the cliff, sustained; and the transient counter-case
    ./build/cps --headless --plant cartpole --vehicles 1 --scheduler rm --exec worst \
        --duration 120 --net-delay 24   # age 105.5, 0 hard
    ./build/cps --headless --plant cartpole --vehicles 1 --scheduler rm --exec worst \
        --duration 120 --net-delay 26   # age 110.5, 9954 hard
    ./build/cps --headless --plant cartpole --vehicles 16 --scheduler aguard --exec worst \
        --duration 120                  # per-veh age 470-895 ms, 0 hard, max|theta| 0.171

    # (6) same schedule, two plants — ages/missed bit-identical, breaches differ
    for p in lateral cartpole; do ./build/cps --headless --plant $p --vehicles 11 \
        --scheduler rm --exec worst --duration 120; done

    # disturbance-driven budget
    ./build/cps --headless --plant cartpole --vehicles 1 --scheduler rm --exec worst \
        --duration 30 --net-delay 300 --shove-force 0    # age 665.5, 0 hard, theta == 0

    # frontier ablation on plant #2
    ./build/cps --headless --plant cartpole --vehicles 8 --scheduler frontier \
        --exec worst --duration 120                      # 7 of 8 crashed
    CPS_FRONTIER_NO_FDEMOTE=1 ./build/cps --headless --plant cartpole --vehicles 8 \
        --scheduler frontier --exec worst --duration 120 # 0 crashed (== aguard)

**Where it lands.** Item 2 is a realized-margin row for PROOF_DRAFT §8.5 (the
boundary statement now has both an analytic and a realized margin, 8.4 vs
49.5 ms). Items 1+3 are the paper's sharpest beyond-worst-case exhibit — a
lever that is provably good for the certificate and measurably bad for the
system — and belong wherever the bound-vs-reality gap is discussed. Item 4 is a
methodology caveat that must attach to every published A(zone)/A_F number
(DATA_AGE / ZONE_TOLERANCE / FCHANNEL). Item 5 extends the scope/limitations
section from one applicability-floor case (v15) to two, on independent
grounds. Item 6 is the cleanest single-table statement of the generalization
thesis and should go in the generalization section (GENERALIZATION §3, which
currently says the cart-pole "binds on physics" — true of its injected
tolerance, but under RM it binds on P1 at N=10/11, exactly where the car does).
The frontier item is a limitations qualifier for the F-channel follow-on.

---

## 2026-08-11 — FCHANNEL §10 executed: enter-fresh binds at the A_F cliff, the amplitude unit does NOT collapse (delay-transients are the mechanism), and the v³|dκ/ds| under-bound transfers to held-out profiles

**What it is.** The four queued FCHANNEL §10 items run to ground in one
session (FCHANNEL §9.9-9.11 = the record; all CSVs committed and registered
in `reproduce.py fzone/fbattery/qzone`). Paper-facing results:

1. **A_F is a min-over-phase quantity and the committed table survives
   (C-O6 closed).** New `--fzone-lead-ms` enters the zone with an
   already-aged F value at matched peak dose. At the z3 cliff ONLY the
   enter-fresh phase breaches (260 ms: 10 hard vs 0 at every stale phase);
   past the cliff severity inverts and GROWS with entry staleness (300 ms:
   24→37 hard). Mechanism sentence for the paper: *what breaches is not how
   old the reference is, but how long the maneuver runs on pre-maneuver
   geometry* — in-zone exposure duration dominates value age at the
   boundary. (fzone_enterstale.csv)
2. **The pre-registered amplitude-collapse FAILS — and that's the useful
   outcome.** Signed zero-age curvature errors: ε*(z3,v10) ≈ [0.16,0.20)
   1/m — 10× above the naive a_tol/v² transfer from the delay cliff and 4×
   the sharpest real curvature on the route; ε* is zone-flat-ish and falls
   ~v⁻³ (steeper than the predicted v⁻²). A sustained DC reference error is
   rejection-limited (B trims it); delay damage is the moving transient.
   Consequence for the paper: amplitude tolerance and delay tolerance are
   DIFFERENT quantities — delay tables cannot be derived from amplitude
   doses (in-house exhibit for the C5 channel-typing warning). Sign
   asymmetry: z3 tolerates −ε ~1.5× more than +ε at higher speeds.
   (qzone_collapse.csv)
3. **First standing A_F_lb: the v³|dκ/ds| unit under-bounds at held-out
   profiles.** A_F(z3) measured [240,260) / [160,180) / [120,140) at
   v10/12.5/15; with a_tol fitted once at v10, the formula predicts
   [123,133) and [71,77) — below the measured cliffs both times
   (conservatism 1.3-1.7×, safe direction). Sign-stability across profiles
   confirmed (C-O11); z3 stays binding. Per-zone kinematics now printed by
   zone_probe. The remaining analytic step is deriving a_tol from the plant
   model instead of fitting it (EE-coordinated).
4. **Composition nuance:** a uniform all-zones F-hold at the BINDING zone's
   budget (240 ms) stays clean at 12.3 mm margin (vs 73.5 mm z3-only) —
   min-budget composition holds for the F channel, unlike the composite
   A-table (which failed composition, A1). The per-zone-vector dose remains
   untested.
5. **Evidence hygiene:** the 2026-08-10 raw-log batteries are formalized
   into committed CSVs (`fchannel_battery.py`, 358-check cross-validation —
   every hard+soft count reproduced line-for-line) and the whole FCHANNEL
   CSV surface regenerates by one command (Guo directive).

**Where it lands.** §9.9-9.11 feed the Condition-I-per-channel section
(C1'/C2') and the A_F_lb future-work → now-preliminary-result upgrade;
item 2 is a Discussion/limitations exhibit; item 5 is artifact-appendix
material.

---

## 2026-08-10 — The F-channel section measured: per-channel per-zone staleness budgets (A_F/A_B triple), rejected separability, the C4 exhibit, distributional capacity dominance, and the two-lever attribution matrix

**What it is.** The FCHANNEL leg executed end-to-end (reviewer-council-shaped
protocol; FCHANNEL.md §9 is the authoritative record, CSVs committed:
fzone_tolerance.csv, bzone_tolerance.csv). Paper-facing results:

1. **The channel triple** (N=1, 120 s, worst, zone-targeted sustained holds,
   breach-anywhere): A_F = {z0 >1200, z1 >1200, z2 [1000,1100), z3 [240,260)}
   ms; A_B = {[400,600), [600,800), [400,600), [300,350)}; vs composite
   A(zone) {290, 400, 290, 140-170}. Channels have DIFFERENT zone-orderings:
   the binding channel flips by zone (F in the lane change, B elsewhere), and
   the composite's structure — including the old z1>z0 anomaly — is inherited
   from the feedback channel. Condition I is a vector over channels (C1').
2. **Separability rejected** (c ~ 0.25, not 1): 300 ms of B-hold costs only
   60-80 ms of z3 F-budget. Failure modes differ qualitatively (F: bounded
   drift; B: instability, FMU divergence at 600 ms uniform).
3. **C4 two-run exhibit**: a z3 F-hold at 300 ms breaches (24 hard) with
   age_path/age_fresh IDENTICAL to the clean baseline (90.50 ms) — chain-age
   metrics rooted at sensor samples cannot see the reference channel.
4. **Distributional capacity** (10 random phasing draws x 3 spacing families,
   honest configs): frontier's P(clean) dominates aguard at every N >= 14;
   at N=20: 5-8/10 vs 0-1/10, fail masses tens vs tens-of-thousands of
   frames. Guard-cap axis proven inert for honest policies (est-TTPNR <=
   horizon - margin < 450) — the tuning comparison is fair by mechanism.
5. **Attribution matrix (2x2, full-lap)**: RM=10, RM+F-economics=14,
   aguard=19, frontier(=aguard+F-economics)=21. Both levers load-bearing;
   F economics alone is +4, triage alone +9, together +11.
6. **Instrument errata discipline**: the ffExtra clamp (§3) and a
   tabulation-parser bug (§9.7) both caught and recorded; every A_F/A_B cell
   keys on the MEASURED delivered dose (calibration within R_F in 92/92).

**Where it lands.** The F-channel section (C1'-C5 per FCHANNEL §8):
Condition-I-is-a-vector, the metric-scope warning, the two-lever capacity
story, and the weakly-hard-facing rate-coupled/value-typed criterion.
Queued: analytic A_F_lb (collapse experiment), cross-profile sign-stability,
reproduce.py registration (FCHANNEL §10).

---

## 2026-08-05 — The scheduler-frontier study: recorded capacity marks are a 30 s-window artifact (real honest full-lap record = 19, not 21); a new scheduler reaches 21; the ceiling is bracketed

**What it is.** A capacity-limit study on branch **`scheduler-frontier`**
(pushed to `physics-derived-timing`; full record in `FRONTIER.md` there; code
= `src/sched/policies/Frontier.cpp` + `EskipProbe.cpp`, never merged here).
Four findings matter for the paper:

1. **The 30 s-window artifact (correction to the 07-20/07-22 entries and the
   poster).** All four v10 z3 arcs sit in the last ~23% of the lap, so a 30 s
   run structurally under-tests the binding zone. At 120 s (full lap),
   aguard-honest breaks at N=20 for EVERY margin 60–120: the honest safety
   record is **19**, not the recorded 21. Under the challenge's full gate
   (0 hard AND soft ≤ 5%/vehicle) it is **12**. Any capacity number the paper
   reports must be full-lap.
2. **A new scheduler ("frontier" v12) holds 21 full-lap** (clean 19/20/21;
   +2 safety frame, 13 vs 12 strict frame) with ~5x better fleet health
   (worst age 430–1400 ms vs 2470; soft 8–27% vs 55–70%). It is aguard's
   allocation + **zone-aware feedforward demotion**: F (44% of per-vehicle
   demand, carries no sensor data) is demoted on straights (500 ms
   heartbeat), kept fresh in critical sections (100 ms), undemoted in z3.
   Robust to pert x3 seeds + avg exec + align 0.5; both schedulers' records
   are v10-specific (neither transfers to v12.5/v15 untuned). The two-lever
   framing for the paper: capacity beyond classical = state triage (aguard)
   + physics-context demand shaping (F-by-zone).
3. **Refresh-rate tolerance != delay tolerance.** Decimating E to a 50 ms
   cadence breaches catastrophically at N=1 at age_path 150 ms — an age the
   delay tables call safe by 100 ms (the FMU estimator's hard-coded 10 ms
   EST_STEP breaks under skipped invocations; 20 ms cadence is a knife edge,
   30 ms is fatal). A(zone)/envelope numbers are DELAY tolerances only; any
   cadence/skipping argument needs its own instrument. Corollary: E demand
   caps any 3-core scheduler at roughly the mid-20s (soft bound; the oracle
   packer that would pin the ceiling was not built).
4. **B->M in-window sequencing** (stage reads sample at execution start):
   age floor 80.5 ms vs the 90.5 ms recorded everywhere else — one merger
   period recoverable by ordering alone.

**Evidence / repro.** `FRONTIER.md` on `scheduler-frontier` (verdict table,
protocol, per-version log); all runs `--exec worst --duration 120`, honest.

**Where it lands.** Evaluation (full-lap capacity table; poster-number
corrections), the scheduling section (two-lever framing), and a caution
footnote wherever A(zone) is used (delay-tolerance scope).

---

## 2026-08-01 — Live A/B results recovered from the 07-31 demo recording (frame-by-frame); the money-shot composite built

**What it is.** The 2026-07-31 ~17:41 EDT bigspace live A/B (RM → failure →
A-GUARD → failure) was captured on two videos: an OBS screen recording of the
RViz/HUD view and Kurt's camera on the physical car. HUD frame strips at 1 s
resolution yield the live event timeline (times = seconds into the screen
recording; the two videos sync at +66.9 s by audio cross-correlation, peak
2.1× over the runner-up):

- 71–72 s: +3 sim cars → N=4 under RM (car seated LAST, the v9 adversarial
  seat). 82 s: N=5. 86 s: N=6.
- 88–92 s: RM ages explode — fleet-oldest ~1.1–2.1 s stale; the REAL car goes
  red "CAR PAST PNR" and physically stalls at the far end (visible in both
  views at the same instant). **Breach #1 ≈ 91 s is the physical car** —
  seat-decides-fate, on camera. Breach #2 ≈ 94 s; violations 0 → 5341 ticks.
- 99–100 s: SWITCH TO AGUARD (live toggle). Ladder rebuilds N=2→6 by 105 s,
  N=8 at 126 s, N=10 at 131 s — ages bounded (transients 100–900 ms, no
  runaway), violations frozen at 5341.
- ≈133 s: first A-GUARD breach at **N=10** (violations 5341→6251, car past
  PNR); one sim car red ≈141 s. Fleet removed 146→157 s back to N=1; ages
  recover to ~tens of ms (the recovery bookend). 161 s: speed segment starts
  (1.00→1.25→…→2.00; car age stays ~10–60 ms throughout at N=1).

**Live vs sim cliffs (labmap sim, 07-30: rm catastrophic N=6; aguard clean
≤8, weave 9–12).** Live matched: RM breached at N=6; A-GUARD's first breach
at N=10 — inside the predicted weave band, ~1 rung earlier than sim-clean, as
expected from sensor noise/WiFi jitter. RM:A-GUARD violation ticks over the
same arc: 5341 : 910.

**Caveats.** (1) Numbers are read off the HUD (cloud-view car age; `applied_
ack` still pending) — cite as demo-run evidence, not instrumented result.
(2) **The demo run's bridge CSV is missing**: `cloud_control/output/` has
UTC-named CSVs from the 13:36/13:41 EDT session only; nothing from ~17:41.
Ask whether the node ran with a different cwd or CSV off — else the CSV half
of "demo artifact = analysis artifact" is lost for this run and the timeline
above (video-derived) is the record.

**Deliverable.** `~/Desktop/fotos/f110_bosch_demos/demo/` — composites v1–v4
(v4 = captioned + code-verified legend + ambient audio; 93 s, 1920×1080):
RViz crop (HUD + track + buttons) beside Kurt's vidstab-stabilized camera,
audio-synced, ends before the speed segment. Full recipe, sync offset
(+66.89 s), event timeline, and legend semantics: that folder's `README.md`
(+ `compose_v4.sh`, `align.py`). LinkedIn cut in `~/Desktop/FinalDemos/`
(1:10–1:16 chatter muted).


## 2026-08-03 — HIL sweeps: RM's cliff is track-independent; A-GUARD's capacity scales with the room

Capacity ladders on two physical-room tracks (1.0 m/s, 1 core, 120 s/rung,
pure sim, committed track CSVs): **rm** goes clean→catastrophic at N=5→6
on BOTH labmap (7.8 m lap) and bigspace (larger room) — the cliff is
demand-side (utilization crosses 1), geometry-blind. **aguard** holds zero
violations through N=8 on labmap but through N=10 on bigspace, first
cracks 11, collapse 14. The age-aware scheduler's admitted fleet grows
with the room; the classical one's does not. This is the HIL echo of the
route-map thesis (the track IS the slack model): beyond-worst-case
capacity is a property of the physics/geometry, and only a
physics-derived policy can spend it. Repro: `f1sim_headless --config
config/demo_sim.yaml --scheduler rm|aguard --vehicles N --duration 120`
with `--track` pinned per room (lab repo).

## 2026-07-31 — HIL finding: under RM, the physical car's fate is its seat in an arbitrary tie-break

**What happened (live).** In the fleet-ladder demo under the RM baseline,
the physical car would not degrade at ANY fleet size while simulated cars
crashed around it. Cause: with uniform sensor periods, RM's priority is
its vehicle-id tie-break — and the car was id 0, the top fixed priority.
Its ~10% demand always won the core first; the starvation caste began
above it. Flipping one modeling choice (car ranked last — equally
legitimate, since among equal periods the order is arbitrary) makes the
car the FIRST to starve (rehearsed: N=6, car at ~1% core, commands >2 s
stale).

**Why it's a paper sentence.** It is the sharpest possible statement of
the fixed-priority pathology the age-criticality thesis targets: under
static priority, whether the *physical* plant survives depends entirely
on an arbitrary position in a list — both extremes (untouchable at seat
0, starved at seat N−1) are the same scheduler on the same workload.
A-GUARD needs no placement choice at all; its ranking is derived from
TTPNR, i.e., from the physics. Any fixed-priority HIL comparison must
state the placement choice explicitly (ours: adversarial, car last);
this is now machine-checked (unit test: saturating RM emits 0 commands
to the external car while aguard serves it on the same workload).


## 2026-07-30 — HIL fleet ladder built: one continuous run = the capacity curve; RM-vs-A-GUARD cliffs on labmap

**What it is.** The lab-repo HIL stack (branch `cloud-sched-integration`,
tag `[fleet-ladder-v4]`) can now grow/shrink the simulated fleet at runtime
while the real car drives — RViz "+ ADD CAR" buttons and Trigger services
share one logged mutation path — and displays/streams the fleet-oldest
**applied-data age** (the `age_path` convention, exported per vehicle from
the f1sim core). Every add/remove and a 1 Hz age/error row land in a
per-run timestamped CSV, so **a single continuous run carries N(t) and
yields the whole capacity curve**, exactly aligned with the screen
recording. Instrument design point for the methodology section: the demo
artifact and the analysis artifact are the same run.

**A/B baseline.** f1sim gained `scheduler: aguard|rm`. Honesty note that
must survive into the paper: every vehicle shares one sensor period, so
classic RM degenerates to its tie-break — vehicle-id fixed priority (the
same strict (period, vehicle) total order the research harness analyzes).
Under 2× overload it provably (unit test) starves the highest ids: the HIL
twin of the ID-locked starvation caste finding (2026-06-23).

**Sim cliffs (labmap, 1.0 m/s, 1 core, 120 s/rung, noise-free):**
rm: clean N=5 (0.076 m), catastrophic N=6 (max|e| 2.2 m, 57k
violation-ticks). aguard: **zero violations through N=8**, bounded
excursions N=9–12 (0.59–0.90 m), collapse N=14. Same demand, same plant,
same track — only the policy changed; the age-aware scheduler is worth
~2× admitted fleet before first violation (6 vs 9... strictly: first
violation rung 6 vs 9, catastrophic rung 6 vs 14). Live cliffs expected
1–2 rungs earlier (sensor noise, WiFi jitter, servo lag). The live A/B
recording (2026-07-31 planned) is the paper's HIL money shot: degradation
mediated by visible, measured data age, reversed on remove (recovery
bookend).

**Caveat for any HIL age claim:** the real car's displayed age is the
cloud's view (command *emitted*); the true applied age needs the car-side
`applied_ack` (queued with Kurt). Label accordingly.


## 2026-07-29 — HIL demo day: the real car self-drives under the cloud scheduler; two hardware-only findings

**What happened.** First full hardware-in-the-loop run of the framework: the
F1TENTH car autonomously lapped the goat track under our cloud A-GUARD
scheduler (native-Mac ROS 2, ~13 ms direct tailnet transport), with simulated
vehicles sharing the same core. The real car's controller job measures ~10%
core tenure at N=4 (exact per-tick counter) — its proportional demand share.

**Finding 1 (methodology): shadow mode caught a frame bug sim could not.**
The centerline was authored in the map-image frame (generator hardcodes
origin 0,0) while AMCL localizes in the origin-shifted frame — a 7 m offset
invisible to pure simulation and instantly visible as max|e|=7.4 m in the
shadow run. Lesson for the paper's methodology section: a shadow phase
(compute-but-don't-actuate against live sensors) is a cheap, high-yield
validation gate for any sim-to-real port.

**Finding 2 (physics): the sim tracked a physically infeasible line; the
real car could not.** One corner of the generated centerline had radius
0.41 m — under the car's ~0.74 m minimum turning radius. The simulator (same
steering limits!) still tracked it within 0.14 m because pure pursuit's
lookahead geometrically cuts corners; the real car (servo lag, gain) ran
wide into the wall at that corner every lap, all excursions outboard, 24% of
commands steering-saturated. Fix: route the line through a recorded
human-driven lap (feasible by construction). Lesson: controller-in-sim
tolerance of an infeasible reference is a sim-to-real trap — reference
feasibility (min radius vs wheelbase/steering limit) should be checked
analytically, not assumed from sim success.

**Where it lands.** Generalization/HIL section (the demo as case study #3
evidence); methodology (shadow gate, reference-feasibility check). Repro:
lab repo branch cloud-sched-integration, DEMO_RUNBOOK.md; fleet-ladder CSVs
(N=4/8/12) pending as of this entry.

---

## 2026-07-22 — Poster fact-check: every Results number reproduces; honest-predictor compute at the poster operating point is ~7% of one core (not the oracle's <3%)

**What it is.** Full verification pass over the symposium poster. Every chart
number reproduced exactly from fresh runs (worst exec, 3 cores, 30 s):
RM/EDF max safe fleet 10 (first break N=11: 653/654 hard); N=20 sim-crit
(τ=100 ms) RM 15 / EDF 12 / aguard-honest(m80) 0; aguard-honest `--pred-margin
80` clean through N=21, first breaches N=22 (46 hard). Both poster citations
verified against the PDFs (Pazzaglia et al. RTAS'26 invited; Wilson et al.
RTAS'25 pp. 215–227). Bosch's own §III.A wording is "a race circuit with N_v
vehicles", so the poster's racing framing is backed.

**New numbers surfaced (not previously recorded).**
- **Honest-predictor compute at the poster's headline config:** 17.1 µs/pred,
  **6.82 % of one core at N=20**; 18.2 µs, **7.65 % at N=21** (both rollouts).
  PREDICTOR §5f's honest column stops at N=14 (4 %); the poster's "<3 % of one
  core" is the *oracle* N=18 figure — wrong for the honest config the Results
  use (still ≪ 3 cores). Poster correction + §5f extension row when next edited.
- **The worst-age curve behind the poster chart** (aguard-honest m80, path ms;
  the 07-20 CSV was scratchpad-only): N=4: 120.5, 6: 120.5, 8: 120.5,
  10: 130.5, 12: 375.5, 14: 1045.5, 16: 1075.5, 18: 1980.5, 20: 4020.5,
  21: 1990.5. Plateau ≤130.5 through N=10, cliff after 12.
- **Prediction refresh cadence is 10 ms**, not the poster's "~16 ms"
  (`Simulation.h` kPredictRefreshTicks = kPnrRefreshTicks = 10 ms; likely
  conflated with the 16 ms per-link network delay, `TaskModel.cpp:47-48`).

**Where it lands.** Poster corrections (this session's report); PREDICTOR §5f
honest-compute row at N=20/21; Evaluation (the reproducible curve).

---

## 2026-07-20 — Honest-aguard margin sufficiency is non-monotone in N: 60 ms blips at N=14 (37 hard); 80 ms is uniformly clean through N=20 (2× the classical fleet)

**Observation.** Building the symposium-poster Results (lead's call: all-honest
comparison, baselines vs `aguard-honest` only), a fleet-size sweep (worst exec,
3 cores, 30 s, N ∈ {4,6,8,10,11,12,14,16,18,20}) found:

- `--pred-margin 60` (the PREDICTOR §5e value that restores honest aguard at
  N=18) is **not uniformly safe across N**: at N=14 it takes **37 hard
  breaches** (sim-crit max 1) while N=12/16/18 are clean — non-monotone in N.
  Margin 80 and 100 both clear N=14.
- `--pred-margin 80` is uniformly clean: **0 hard, 0 stalled, sim-crit 0 at
  every N in the grid — including N=20**, past the default-aguard headline of
  18. Worst path age grows to 4020.5 ms at N=20 (soft 66%) — safe but very
  stale.
- Classical baselines: `rm` and `edf` both first break at exactly **N=11**
  (653 / 654 hard, 1 stalled each); by N=20 rm takes 37,217 / edf 27,502 hard
  with 15 / 12 cars never actuated. Max safe classical fleet = **10**; honest
  aguard's exact capacity (extended search): clean through **N=21** (worst path
  age 1990.5 ms), **first breaches at N=22** (46 hard, 0 stalled) → 2.1×.
  Note the worst-age non-monotonicity: N=20 reads 4020.5 ms vs N=21's 1990.5
  (different interleavings; both zero-hard).

**Why it matters.** (1) The §5e "margin 60 restores aguard" claim was
N=18-specific — margin sufficiency must be swept per config, not sampled at one
operating point. (2) "2× the classical fleet, zero hard breaches, ranking only
on the delayed state the cloud actually has" is a cleaner, stronger headline
than the oracle 18-vs-10, and it is the config the poster now reports.
(3) The N=20 row is the sharpest safe-but-stale exhibit yet: 4 s worst data
age, zero breaches — safety ≠ freshness, in one row.

**Evidence / repro.** `./build/cps --headless --vehicles N --scheduler
{rm | edf | aguard-honest --pred-margin 80} --exec worst --duration 30` over
the grid; margin sensitivity at N=14: 60 → 37 hard, 80 → 0, 100 → 0. (Poster
sweep CSV in session scratchpad only — regenerate from the command grid.)

**Where it lands.** Evaluation (honest-variant capacity), the symposium
poster's Results section; add the margin caveat to PREDICTOR §5e when next
edited.

---

## 2026-07-17 — Guo's dossier response: positioning blessed, CARLA descoped, and three C→V hardening legs become the critical path

**What it is.** Dr. Guo's written response to the `ContextForGuo/main2.tex`
dossier (received 2026-07-17). It reshapes the plan of record in four ways:

1. **Positioning vs Sudvarg — advisor-confirmed.** Their lever is *sampling
   periods* adjusted from physical state; ours is *tolerable data age under
   shared multicore contention* — "physical context dynamically allocates
   scheduling slack in a multi-task, shared-resource cloud/edge platform."
   The three-condition decoupling (Physics bounds age / Demand bounds
   concurrent critical loops / Service guarantees age) is endorsed verbatim as
   "a highly sellable contribution." This substantially answers the HANDOFF
   "residual for Kurt" on whether our delta clears Sudvarg's §VII future-work
   (Kurt still owns related-work rigor, but the framing is now the advisor's
   own words — near-verbatim paper-intro material).
2. **The publication gap is [C]→[V], on three named legs:**
   (a) **Theorem 2 (limited-carry-in RTA):** bridge `rta_solve.py --workload
   limited` (empirical-only candidate) to a general analytic proof under the
   tick-quantum model. Guo calls the capacity lift "the headline empirical
   result" — his "2.7×" is the ZB-F-X composed **N=8 @ s≥4 s certified vs
   classical 3** (PROOF_DRAFT §5); keep the operating-point qualifiers
   attached in paper prose.
   (b) **Condition I formalization (NEW leg):** analytically derive a
   *conservative lower bound* on the car's A(zone) from simplified lateral
   dynamics, with the EE thermal analytic note as the blueprint. Until now
   A(zone) was empirical-by-design; an analytic under-bound that the measured
   table dominates would upgrade Condition I from measured to derived (with
   the sweeps as validation, not as the definition).
   (c) **Lemma 1 spacing assumption:** delays → braking/drift → spacing
   changes in reality. Note: in the harness this cannot happen — vehicles
   follow pre-recorded velocity/position reference traces
   (`src/trace/Trajectory.h`), so temporal spacing is constant by
   construction; the fix is a clean stated limitation or a safety buffer
   `s_eff = s − buffer` in the spacing model (+ a cheap sensitivity row from
   the existing occupancy sweep).
3. **CARLA descoped** ("too much engineering overhead"); the Bosch FMU +
   cart-pole pairing is sufficient generality evidence. Kills the 2026-07-08
   meeting directive's CARLA thread.
4. **Process:** map the paper outline with Kurt and assign sections; Guo wants
   the Overleaf when more mature.

**Where it lands.** (1) intro/related-work positioning; (2a) the Theorem-2
section + Kurt's brief; (2b) a new Condition-I derivation section; (2c) Lemma
1's statement and limitations paragraph; (3) scope/evaluation framing.

## 2026-07-17 — Citation check: Li et al. RTSS'24 and Guan et al. RTSS'09 both VERIFIED (Li was in relatedPapers all along; its Δ=kψ is Lemma 3)

**What it is.** Chased the two citations the docs had flagged unconfirmed. Both
are real, correctly attributed, and the specific technical claims are accurate.

**Li et al. RTSS'24 — VERIFIED, and it was in `relatedPapers/` the whole time.**
Full cite: Xisheng Li, Ye Ma, Yuting Chen, Jinghao Sun, Wanli Chang, Nan Guan,
Liming Chen, Qingxu Deng, **"Priority Optimization for Autonomous Driving Systems
to Meet End-to-End Latency Constraints," 2024 IEEE RTSS** (DOI
10.1109/RTSS62706.2024.00041). It formulates the AD system as a multi-rate DAG
and derives a *novel, tighter* reaction-time bound for critical cause-effect
chains (its §IV-B "refined bound", claimed to outperform the prior tightest) —
matching CLAUDE.md's "tightest multi-rate chain bounds" handle. The file is
`relatedPapers/DirectlyRelatedToYourSpecificProblem/Priority_Optimization_for_
Autonomous_Driving_Systems_to_Meet_End-to-End_Latency_Constraints.pdf` — the
**filename never contained "Li"**, which is why the 2026-06-22 survey reported it
"not in relatedPapers / could not confirm." The specific handle in `BOUND.md
§5.2` (Δ = k·gcd quantization of chain phase offsets) is the paper's **Lemma 3**
verbatim: the release-time gap between adjacent chain jobs is Δ = kψ_i with
ψ_i = gcd(T_i, T_{i+1}), k = 0..⌊(T_{i+1}−1)/ψ_i⌋. Accurate attribution.

**Guan et al. RTSS'09 — VERIFIED (web).** Nan Guan, Martin Stigge, Wang Yi, Ge
Yu, **"New Response Time Bounds for Fixed Priority Multiprocessor Scheduling,"
RTSS 2009, pp. 387–397** (IEEE Xplore 5368174). This is the canonical origin of
RTA-LC and the **"at most m−1 carry-in tasks"** partitioning our Theorem-2
bridge (§9.4a) uses — confirmed against the literature (RTSS'09 Best Paper).
PDF added 2026-07-17 to `relatedPapers/Foundational/` (from Wang Yi's page;
6 pp., verified title/authors + 21 carry-in mentions).

**Lesson (process).** A citation "handle" (author-year) that doesn't appear in
the on-disk filename is invisible to a filename-grep survey — the 06-22 survey's
false negative on Li was purely a naming mismatch, not a missing paper. Fixed by
making CLAUDE.md's pointer name the actual file. Both verifications are honest
literature confirmation, **not** the field-judgment scoop check (that stays Kurt's).

**Where it lands.** Related-work + the RTA/Theorem-2 section (Guan) and the §4
sampling-term future work (Li). Both now [V]-citable.

## 2026-07-17 — Theorem-2 bridge (Guo 2a): the limited-carry-in candidate in Guan-RTA-LC notation + a proof-step ledger — 5 of 7 steps transfer, 2 are Kurt's

**What it is.** The scaffold that turns the limited-carry-in RTA from a
brute-force script into a stated theorem for Kurt to prove (Guo's point 2a — he
called the capacity lift "the headline empirical result"). The AI owns the
bridge; the soundness proof stays Kurt's (invariant #5).

**Standard-notation statement (THEOREM_BRIEF §9.4a).** The candidate
(`rta_solve.py::hp_interference`, modes `limited`/`limited-t`) written in
Guan-RTA-LC (RTSS'09) form: `R_k = C_k + ⌊(1/m) Σ_{i∈hp} I_i(R_k)⌋` with
`I(x) = Σ W_i^NC(x) + Σ_{(m−1) largest}(W_i^CI − W_i^NC)_+`, NC = `⌈x/T⌉C`, CI
jitter `J = R−C` (`limited`) or `J = T−C` (`limited-t`, mechanical from
kill-and-hold). `none ≤ limited ≤ full` by construction ⇒ sound-leaning + tighter
than the §7.2 full-carry-in form.

**Proof-step ledger (§9.4b) — the actual contribution of this session.** Adjudicated
each classical RTA-LC step against our tick-quantum model (discrete unit quanta,
**synchronous periodic release**, strict total order, kill-and-hold):
- **Transfer:** #1 interference conservation, #3 NC bound, #4 CI-jitter (`limited`),
  #5 CI-mechanical (`limited-t`), #7 the 1/m relaxation. #5 and #7 are *strengthened*
  by our model (kill-and-hold makes CI need no induction; exact per-tick ⌊·⌋ beats
  the continuous relaxation) — a genuine "our discrete model is more rigorous, not
  less" point for the paper.
- **Re-derive (Kurt's two obligations):** **#2** the `m−1` carry-in count under
  synchronous release (Guan's sporadic window argument doesn't transfer verbatim;
  synchronous release plausibly *tightens* it), and **#6** the stopping-rule
  soundness for `limited`'s **non-monotone** `I(x)` (= PROOF_DRAFT Lemma 2a S5).

**Widened empirical arbiter.** Added opt-in `rta_solve.py --soundness-grid` — checks
measured `age_path ≤` the candidate's per-vehicle bound at every certified N, not
just the boundary. Validated `N ∈ {1,4,6,7,8}`: no counterexample, tightest margin
≈ **31 ms** (N=6 v0: 100.5 ≤ 131.6), certified 8 ≤ empirical 10. Empirical
non-refutation ≠ proof (invariant #5); #2 and #6 are the analytic gaps. The default
(no grid) cross-check is byte-identical, so verify.sh's G3 is untouched.

**Where it lands.** The Theorem-2 (RTA) section: state it in Guan-RTA-LC notation,
then the ledger frames the proof as "5 steps cited, 2 re-derived (one a tightening
opportunity)." Bridge only — the theorem is [C] until Kurt signs off.

## 2026-07-17 — Lemma-1 spacing buffer (Guo 2c): the s≥4 s certification absorbs ≈500 ms of compression for free; beyond that, run s_nominal ≥ 3.5 s + Δ

**What it is.** The clean answer to Guo's point 2c — `F_spaced` assumes a
*constant* minimum temporal spacing `s`, but real delays → braking/drift can
compress it. Rather than only acknowledge the limitation, we buffer it: certify
at the **effective** spacing `s_eff = s_nominal − Δ`, where `Δ` bounds worst-case
compression. `Occ⁺` is non-increasing in `s` (machine-checked, `lemma1_check.py`
[5]), so a buffer can only *raise* the demand the schedule must clear — strictly
conservative, never optimistic.

**The number (verified, not estimated — `lemma1_check.py` [5]).** At the certified
operating point `s₀ = 4 s`, the inflated occupancy `Occ⁺` stays at the
band-certified `K* = 4` all the way down to `s_eff = 3.5 s`, then jumps to 5 at
`s_eff = 3 s`:

| `Δ` (compression) | `s_eff` | `Occ⁺` | fits `K*=4` (N=8)? |
|---|---|---|---|
| 0 | 4.00 s | 4 | yes |
| 250 ms | 3.75 s | 4 | yes |
| 500 ms | 3.50 s | 4 | yes |
| 1.0 s | 3.00 s | 5 | no (needs band 5, a FAIL row) |
| 2.0 s | 2.00 s | 8 | no |

So the round-number `s ≥ 4 s` certification **already contains ≈ 500 ms of
compression tolerance** (the Occ⁺=4 band bottoms out at 3.5 s, not 4 s); to
guarantee a larger compression bound `Δ`, pre-pay it in the nominal gap:
`s_nominal ≥ 3.5 s + Δ` (conservatively `4 s + Δ`). *(Estimating "zero
tolerance" from the 4 s → 5 s grid step would have been wrong — running check [5]
surfaced the 3.5 s sub-grid headroom. "The simulator is the adversary — verify,
never assume," §8.)* **Route-scope:** the 3.5 s is **v10-specific**, not a
theorem constant — the general rule is `s_nominal ≥ s*(R) + Δ`, where the
critical spacing `s*(R)` (smallest spacing keeping `Occ⁺ ≤ K*`) is re-derived per
route from its binding-zone geometry, band inflation ζ, and `K*`; `s*(v10) ≈
3.5 s` is one instantiation (THEOREM_BRIEF §3.5).

**What stays open (honest scope).** Deriving `Δ` from a longitudinal /
braking model is **not** done here — that is exactly the A3 control↔occupancy
coupling, left as future work. The buffer's contribution is to make the theorem
robust to *any* such `Δ` once supplied, and to quantify the price (nominal-gap
inflation). In the harness itself spacing cannot drift at all — cars follow
pre-recorded reference traces (`src/trace/Trajectory.h`), so `F_spaced` holds by
construction and this is purely a real-world model-validity buffer.

**Where it lands.** Lemma-1 / demand-bound section: state `F_spaced`, then the
buffer as the robustness clause; the corollary's "s ≥ 4 s" is the *effective*
spacing. PROOF_DRAFT §4 (buffer + sensitivity table) + A3; THEOREM_BRIEF §3.5.

## 2026-07-17 — Finding D closed: zone_probe de-rotated; occupancy values invariant, and the fix STRENGTHENED check [3] (spurious F_spaced violation removed)

**What it is.** The Finding D fix (the 2026-07-10 rotation bug below).
`tools/proofchecks/zone_probe.cpp` now records each RLE run's true start tick
and anchors the merged wrap-around arc at the tail run's real position
(`lap − tail_len`) instead of re-accumulating from 0; `lemma1_check.py::PROFILES`
now carries true-frame starts for all three profiles. True z3 arcs:
- **v10** `(760800,32000) (797800,32200) (922200,19400) (1008800,21800)`
- **v12.5** `(608400,26000) (638200,26100) (737600,16000) (806800,17800)`
- **v15** `(506700,47200) (614400,13600) (672200,15200)`
Each old table was a uniform late rotation by the profile's wrap-run length
(v10 +147,400, v12.5 +119,400, v15 +98,600) — lengths, K, L, lap, and *order*
all preserved (the isometry signature). K/L/lap match the `proofchecks/README`
table exactly (unchanged).

**The prediction held — and then some.** Diffing `lemma1_check.py` output in the
old (rotated) vs new (true) frame: **every occupancy value is identical** —
replicated Occ, exact-optimum, per-arc, headline, and the check-[4] inflated
Occ⁺ table. Rotation invariance confirmed empirically, as the finding predicted.

**The one position-keyed change is a strengthening, worth a sentence in the
paper.** check [3] replicates `Simulation::packZoneOffsets` and reports the
placed configuration's min pairwise gap + an `F_spaced` flag. That gap is
genuinely position-keyed (the finding's "bites only position-keyed consumers").
In the *rotated* frame the replicated packer produced offsets with min-gap <
spacing (e.g. 1,798 at s = 1 s), flagged `VIOLATED-by-instrument`, which **waived**
check [3]'s `measured ≤ headline` bound test via the `or not spaced` branch. In
the *true* frame — which is how the committed `occupancy_sweep.csv` was actually
generated (real `Trajectory::zoneAt`) — the packer is properly spaced (min-gap =
s+1 ≥ s at every s), so the flag reads `OK` and the bound test now passes
**without** the waiver. So the correction doesn't just leave the numbers intact;
it upgrades a waived check into a genuine one and confirms the committed v10 Occ
rows (12/9/7/5/4 at s = 1/1.5/2/3/4 s) arise from truly F_spaced placements. The
old rotated frame's `VIOLATED-by-instrument` warnings were themselves artifacts
of the rotation bug.

**Where it lands.** Instrument-honesty footnote to the Lemma-1 occupancy
section; PROOF_DRAFT §0 carries the erratum + check-[3] note. Reinforces the
"the simulator is the adversary — verify, never assume" lesson: the diff
(not the invariance argument alone) is what surfaced the check-[3] strengthening.

## 2026-07-10 — Instrument honesty: zone_probe reports arc STARTS rotated by the wrap-merged tail (no result changes — rotation is an isometry of the occupancy problem)

**What it is.** `tools/proofchecks/zone_probe.cpp` prints z3 arc start ticks
that are **rotated late by the length of the lap-wrapping run** (147,400 ticks
for v10): after its circular RLE merge folds the final run into the first
(`runs.front().second += runs.back().second`), the printing loop re-accumulates
`pos` from 0 through the merged list, so every start downstream of the front
run is shifted by the merged tail's length. True v10 z3 arcs (raw `zoneAt`
RLE, no merge): **(760800,32000) (797800,32200) (922200,19400)
(1008800,21800)** — identical lengths and cyclic gaps, rotated −147,400 vs the
committed table. `lemma1_check.py`'s `PROFILES` table inherits the rotated
starts (v12.5/v15 presumably rotated by their own tail lengths — not yet
re-extracted), and PROOF_DRAFT §0's "every profile's last arc ends exactly at
the lap boundary — so inflated arcs wrap" is an artifact of the rotated frame
(in the true frame, v10's ±2,600-inflated arcs do NOT wrap; the wrapped-arc
handling in `lemma1_check.py` remains correct and worth keeping).

**Why no committed result changes.** A uniform rotation of all arcs is an
isometry of the F_spaced occupancy problem: lengths and cyclic gap structure
are preserved, so every Occ/Occ⁺/Lemma-1 value is invariant — re-verified
empirically (v10 raw 12/9/7/5/4 and inflated 8/5/4 identical in both frames).
The harness's zband/zone instruments use the real `Trajectory::zoneAt`, so
every run, CSV, and theorem number is untouched. The bug bites only
**position-keyed** consumers of the printed starts.

**How it surfaced (the cautionary tale).** A learning-aid session built a JS
tick-level twin of `TaskModel.cpp` + zband and held it to golden per-vehicle
ages from the binary. rm configs matched exactly; zband didn't — because the
twin's zone flags used `lemma1_check.py`'s rotated arcs. A standalone C++
harness linking the repo's own scheduler reproduced the twin (not the binary)
under the rotated arcs, isolating the flag input; dumping raw `zoneAt` found
the rotation. Same lesson as manifestation≠cause: a "machine-extracted" table
is only as good as the extractor's coordinate bookkeeping — and only a
consumer that depends on the *absolute* frame can catch a rotation, which is
why every rotation-invariant check passed for a week.

**Evidence / repro.** True arcs: RLE `zoneAt` directly (one-file probe against
`Trajectory.cpp`, no merge step); compare `zone_probe` output. Scheduler-level
confirmation: zband N=4/N=8 per-vehicle age goldens match the binary only
under the true arcs. Fix recipe: HANDOFF §4 Finding D.

**Where it lands.** Not paper prose — instrument honesty for the artifact
release: fix `zone_probe`'s start reporting, regenerate `PROFILES` for all
three profiles, erratum note on PROOF_DRAFT §0's geometry table.

---

## 2026-07-04 — Execution round: the cliff is 170 not 140; F-demotion alone certifies 8; v15 is the applicability boundary; the A-table does NOT compose

**What it is.** All seven queued decisive experiments ran (HANDOFF §5 queue; full record
PROOF_DRAFT §8). Five paper-shaping results:

1. **The 50 ms grid hid 30 ms of physics.** Fine-grid causal sweeps (10 ms = the
   instrument's true resolution — delivered ages quantize in T_E steps): **A(z3) = 170
   (v10), 160 (v12.5), 90 (v15)**. z3 stays binding on every profile; A falls with speed.
2. **At the refined 170, occupancy stops being load-bearing on v10:** fleet-wide
   **F-demotion alone** (drop the age-path-irrelevant Feedforward below everyone's E/B/M —
   a one-line priority tweak) certifies **N=8 uniformly** (fleet-max 151.6 ≤ 170, P1 OK) vs
   classical 5–6. The honest general statement: *occupancy earns capacity exactly when the
   binding budget < the uniform F-demoted bound at P1 capacity (~151.6)* — true at the
   conservative 140 table, at v12.5's 160 (barely), for ff-adjusted regimes, and for tighter
   plants. The paper should present this boundary explicitly, not a single operating point.
3. **The theorem's envelope is validated; the A-table is refuted as a composite.** Per-zone
   delay vector runs (new `--zone-extra-vector` + ZB-F-X flag emulation): the ZB-F-X
   guarantee envelope (≤137 flagged / ≤195 elsewhere) → **0 hard, K_age(τ=1)=0** over a
   full lap (A1 retired at the operating point); every zone at its own budget
   simultaneously → **9,402 hard frames** (budgets non-composable at amplitude — the
   good-entry induction fails exactly where the skeptic predicted; the theorem's tighter
   envelope is what saves it).
4. **v15 = the approach's applicability boundary:** A(z3)=90 < the uncontended chain bound
   (124), so *no scheduler* can certify v15's lane change at these periods — the physics
   budget must exceed the uncontended chain latency for any scheduling result to exist.
   A crisp negative result for the paper's scope section.
5. **The proof-object scheduler now exists and survived its adversary:** `--scheduler
   zband` (release-stamped bands, exactly the analyzed ZB-F-X) — 0 missed / 0 hard /
   K_age=0 in and slightly beyond the certified region (worst age 120.5 vs 196.0 bound),
   0 missed where aguard drops ~6,000 jobs, honest collapse at N=18. A2 also closed with a
   number: the F-demotion delta (+13.5 ms ff staleness, `--ff-extra-ms`) costs one 10 ms
   grid step of cliff (170→160), leaving ≥22 ms margin at the operating point.

**Instrument honesty items:** pack-zone pass-2 spacing now enforced against all placed
cars (Occ column unchanged everywhere; aguard s=1.5 s row 0→27 hard under corrected
placements); `reproduce.py zones|occupancy` regenerate every zone/occupancy CSV for all
three profiles one-command.

**Where it lands.** The corollary section (boundary statement, item 2), the validation
section (item 3), scope/limitations (item 4), and the witness table (item 5). Remaining
top risk moves to the band-transient formal induction + the injected-vs-scheduler-induced
staleness distinction near the cliff (PROOF_DRAFT §8.7).

**Evidence / repro.** PROOF_DRAFT §8 (all commands inline); `reproduce.py zones occupancy`;
`rta_solve.py --band K --band-n 8 --band-demote-f --workload limited-t`; gates re-verified
after every code change (`verify.sh --full` ALL PASS; limited cross-check PASS).

**Addendum (same day) — the injected-vs-scheduler-induced staleness gap CLOSED, with a
bonus overload finding.** Core-starvation sweeps (1 core N=1–3, 2 cores N=2–7, zband):
every P1-holding config pins scheduler-induced age ≤ 110.5 ms — **the task set is bimodal
under kill-and-hold: keep up (~uncontended+30 ms) or collapse P1; no feasible schedule can
even reach the 140–180 cliff region**, so injection is strictly harsher than reality and
the A(zone) instrument is conservative by construction. The collapse mode itself is
paper-worthy: at 2 cores/N=7 (5,999 missed) the fb age stays FRESH (100.5) while z2-heavy
hard breaches explode — the kills land on F (longest C), i.e. **stale feedforward, not
stale feedback, is the first casualty of overload** — the same F-axis the demotion result
exploits, seen from the failure side. (PROOF_DRAFT §8.7 #3.)

---

## 2026-07-03 — Candidate fleet-safety theorem drafted end-to-end (PROOF_DRAFT.md): 8 cars @ ≥4 s certified vs classical 3 — and what the red-team found

**What it is.** `PROOF_DRAFT.md` (CANDIDATE/UNVERIFIED) composes the whole leg-A chain:
Lemma 1 (occupancy counting, proven + brute-forced on 17,176 cases), Lemma 2a (the
limited-CI RTA audited step-by-step; cross-check PASS as-found and post-patch), and a
new Lemma 2b — a **two-band zone scheduler ZB-F-X** (elevate flagged cars' E/B/M;
**F stays base** — F carries no sensor data, and demoting it is exactly what makes the
composition close; without it the certified top band (2–3) is below the route's K=4
arc floor and the theorem admits nothing). Machine-instantiated verdict (v10, worst,
m=3, assumption-free Θ=T workload): **N=8 at s ≥ 4 s headway, all zones in budget —
2.7× the strongest classical uniform test (N=3), 4× the same-workload one (N=2)**,
collapsing honestly to classical as s → 0. The proof object is **prediction-free**
(no PNR/TTPNR in the trusted base — that soft spot moves to the witness only).

**Paper-worthy findings along the way:**
- **v10 z3 = 4 arcs** (probe of `Trajectory.cpp`; docs said "several"), and the
  committed `occupancy_sweep.csv` values equal the **exact F_spaced optimum** at every
  spacing (anchored-greedy = brute force; a Python replica of `packZoneOffsets`
  reproduces every CSV row from geometry alone) — the instrument realizes the true
  worst case, so Lemma 1's `min(N, ⌊L/s⌋+K)` is the right object and the per-arc form
  is tight at 4 of 9 grid points.
- **Independent 4-lens red-team (fresh-context agents) found two CRITICALs the
  author missed**, both repaired same-session: (1) an *own-task band carry* — under
  band-at-release priorities, a base job's top-stamped predecessor is strictly higher
  priority and its ≤C ticks were uncounted (classic mode-change trap; fix: +C_κ per
  base E/B/M task; +1.2 ms, no verdict flip); (2) the **inflated z3 arcs wrap the lap
  boundary** on all three profiles and the exact-optimum scan silently undercounts
  wrapped arcs (fix: rotation normalization; table values unchanged). Plus the
  sharpest physics attack: **the danger window outlives the zone** — at the first
  failing z3 sweep point, 60/136 hard frames land in z0 *after exit*
  (`zone_tolerance.csv`), so ZB-F-X now holds exiting cars top-band for 240 ms
  (machine-checked free at the operating point: Occ⁺ stays 4 @ 4 s), and a decisive
  per-zone-envelope experiment is queued before Kurt invests (PROOF_DRAFT §6 A1).
- A 91-schedule adversarial two-band simulator battery (exact replica; N=11
  missed=4497 reproduced) found **zero violations** of the band bounds, ≥11 % margin,
  including premise-violating probes — evidence, not proof; the harness `zband`
  policy is the missing real adversary.

**Where it lands.** The theorem section skeleton + the honesty ledger (grid
granularity: A(z3)=140 passes at 140.5 / fails at 190.5, a 50 ms grid vs a 2.6 ms
admission margin — state both). Top-3 open risks ranked in PROOF_DRAFT §7 (A1
envelope > band transients formal induction > S3 general form). Kurt re-derives;
nothing here is claimed proven (invariant #5).

**Evidence / repro.** PROOF_DRAFT §5 command block; `rta_solve.py --band 4 --band-n 8
--band-demote-f --workload limited-t`; scratchpad `lemma1_check.py` /
`lemma2a_check.py` / `redteam_band.py`. Gates re-run after all edits:
`--workload limited --cross-check` PASS; `verify.sh --full` ALL GATES PASS
(uniform solver paths byte-identical, diffed).

---

## 2026-06-30 — Limited-carry-in RTA (candidate): tightening buys schedulability, NOT uniform z3-safety — so occupancy is load-bearing N=4…10

**What it is.** Leg-3 sub-task 2a, prototyped as a **labeled-UNVERIFIED candidate** to de-risk
Kurt's re-derivation (`rta_solve.py --workload limited`). A sound-leaning `m−1` Guan-RTA-LC form:
each higher-priority task contributes its no-carry-in workload (`NC = ceil(x/T)·C`, the existing
`none` form) and only the `m−1` largest carry-in *surpluses* (`CI−NC`, `CI` = the `full` jitter
form) are added back — so `none ≤ limited ≤ full` by construction (bounded above by the
already-sound full form). No per-task interference cap in v1. **Soundness is guarded by the sim
cross-check, not proven** (the NC/CI choice + jitter↔carry-in interaction stay Kurt's).

**Result (cross-check clean — `RESULT: all checks passed`):**
- **Certified capacity 5 → 8** (the 2× full-carry-in gap to empirical 10 halved to 2);
  cross-check sound: certified `8 ≤ empirical 10`, `missed=0` at N=8, no age-bound violation.
  Still conservative (sim runs clean to 10), as a sound-leaning candidate should be.
- **The crux survives tightening.** The fleet-max age bound crosses `A(z3)=140 ms` at **N=4
  under *both* full and limited** — the per-vehicle bounds coincide at small N (the `m−1` cap only
  bites once there are many interferers, N≥6). Root cause: the **uncontended chain already nearly
  saturates the lane-change tolerance** — N=1 bound = **124 ms**, only 16 ms under 140. So `z3` is
  binding because the chain is *long relative to its tolerance*, not because of contention.

**Why it matters (the headline for Kurt).** Provable-to-N by guarantee: **uniform z3-safety → 3**
(both workloads); **schedulability/P1 → 8** (limited) vs 5 (full); **empirical safety → 10**. So
limited carry-in does **not** reduce the need for occupancy — it *extends the certified-schedulable
substrate (5→8)* that the per-zone + occupancy argument (Lemma 1) then builds safety on. The two
compose exactly as the theorem says, and **the occupancy lemma is quantified as load-bearing across
N=4…10.** A tighter candidate (the interference cap, exact NC forms) could close the last gap of 2
toward 10 — but tighter = higher unsoundness risk, so that is Kurt's derivation, not our prototype.

**Honesty.** Empirical (30 s cross-check) soundness only, not proof; Lemma 2a's formal soundness +
Lemma 2b's composition remain Kurt's (invariant #5). Default `--workload full` is byte-identical
(diff = only the added bound-vs-N sweep). THEOREM_BRIEF §9.4 carries this.

**Evidence / repro.** `python3 tools/rta_solve.py --workload limited --cross-check` (read certified
capacity + the "Fleet-max age bound vs N" crossover sweep); `python3 tools/rta_solve.py` for the
full-carry-in A/B.

**Where it lands.** The Lemma-2 schedulability section: the limited-carry-in tightening (capacity
5→8) and the finding that it doesn't move the 140 ms crossover, motivating the per-zone + occupancy
composition as essential for N≥4.

---

## 2026-06-29 — Worst-case zone occupancy `Occ(R, F_spaced)`: the route admits `Occ < N`, and a scheduler converts occupancy into safety

**What it is.** THE PLAN leg 2 built: a zone-aware placement instrument (`--pack-zone Z`
`--min-spacing MS`, lateral) that packs the binding zone (z3 lane-change) with cars at a
minimum inter-car phase gap — the `F_spaced` fleet model (THEOREM_BRIEF §3.5) — and measures
the worst-case **simultaneous occupancy** `Occ`. It greedily fills **all** z3 arcs at the gap
(cars in different arcs are still simultaneously in the zone), and reports `Occ` against the
geometric prediction `ceil(zone_len / spacing)`. The empirical `Occ(R, F)` curve is the input
to Kurt's Lemma 1. Added alongside the leg-4 metric; off by default ⇒ byte-identical (N=6
90.5/100.5, 0 missed; fidelity 1.490e-08). z3 total length = **105,400 ticks ≈ 8.9 % of the
lap**.

**The `Occ(s)` curve (N=18, pack z3, 30 s worst), with the rm-vs-aguard safety pairing:**

| spacing (ms) | Occ / N | geo ceil(L/s) | aguard hard | rm hard |
|---|---|---|---|---|
| 0 (stacked) | 18/18 | 18 | **36012** | 22512 |
| 500 | 18/18 | 18 | **0** | 34581 |
| 1000 (≈1 s gap) | 12/18 | 11 | **0** | 26003 |
| 2000 | 7/18 | 6 | **0** | 26464 |
| 4000 | 4/18 | 3 | **0** | 34207 |

**Findings.**
1. **`Occ` tracks `ceil(L/s)` within +1–2** (per-arc boundary terms), validating THEOREM_BRIEF
   §3.5's `Occ ~ tight-zone length / spacing`. `Occ < N` for realistic spacing (1 s gap →
   12/18; 2 s → 7; 4 s → 4) and `→ N` only when stacked. **The slack the bound exploits is the
   route's non-tight fraction** (z3 is 8.9 % of the lap).
2. **Multi-arc:** the route has several lane-change arcs, so a single-longest-arc model
   *under*-counts; the worst case packs **all** arcs (the greedy instrument), matching the
   total-zone-length/spacing bound. (An early single-arc cut read `Occ=4` where all-arc reads
   `Occ=7` at 2 s — the sim, as adversary, exposed the omission.)
3. **Occupancy → schedulability (the leg-3 preview):** occupancy is **policy-independent**
   (same `Occ=12/18` for both schedulers — it is geometry). Yet that same occupancy is **fatal
   under RM** (26003 hard, K>cores 98.5 %) and **safe under aguard** (0 hard, K=7) for every
   spacing ≥ 500 ms. Occupancy is *necessary, not sufficient*; a physics-aware scheduler
   converts high binding-zone occupancy into zero crashes — exactly what Kurt's Lemma 2 must
   show `m` cores can do.
4. **Honest degradation:** at the fully-stacked extreme (spacing → 0, `Occ = N`, K = 18), even
   aguard crashes — the bound degrades gracefully to classical when the route/placement is
   worst-case-everywhere (`F_adversarial`). A feature (honest about a genuinely hard route),
   not a failure (THEOREM_BRIEF §5 Corollary).

**Evidence / repro.** `python3 tools/occupancy_sweep.py` → `occupancy_sweep.csv` + the `Occ(s)`
table; or by hand `for sp in 0 500 1000 2000 4000; do ./build/cps --headless --vehicles 18
--scheduler aguard --exec worst --duration 30 --pack-zone 3 --min-spacing $sp; done` (read the
`packed z3` + `zone occupancy` lines). Code: `packZoneOffsets` + the occupancy counter
(`Simulation.cpp`); CSV cols `pack_zone,min_spacing_ms,max_occ_packed`.

**Where it lands.** Lemma 1's empirical `Occ(R, F_spaced)` curves (the geometric occupancy
model validated), paired with the occupancy→schedulability figure (same `Occ`, RM crashes /
aguard safe) that motivates Kurt's leg-3 composition.

---

## 2026-06-29 — Danger-relative criticality metric: the two failure axes are orthogonal

**What it is.** THE PLAN leg 4 built: a danger-relative simultaneous-criticality metric
(`--danger-tau FRAC`, lateral) that replaces the saturated TTPNR-under-held gauge (Finding
3, 2026-06-25) with a per-zone budget reading. Per base tick it counts cars whose delivered
age_path ≥ `τ·A(zone of the car NOW)` — the age-budget term `K_age` — and unions that with
the state-critical cars (TTPNR < `--tau-crit`) — `K`, folding in actual state per the
good-entry wrinkle (THEOREM_BRIEF §3.2). One run sweeps a fixed τ grid → the `K(τ)` demand
curve. Added ALONGSIDE `--tau-crit` (baselines byte-identical: N=6 90.5/100.5, 0 missed;
fidelity 1.490e-08). A(zone) table hard-coded from `zone_tolerance.csv` (V10, lateral):
{z0:290, z1:400, z2:290, z3:140} ms.

**The finding — the two policies fail on ORTHOGONAL axes, and neither single metric sees
both** (car, worst, 3 cores, 30 s, τ=1.0):

| policy | sim-crit (TTPNR) | K_age (age budget) | K (union) |
|---|---|---|---|
| RM N=14 | 7 | **0** | 7 |
| RM N=18 | 12 | **0** | 12 |
| aguard N=14 | **0** | 3 | 3 |
| aguard N=18 | **0** | 6 | 6 |

- **RM (physics-blind) is INVISIBLE to K_age.** Its *served* cars are fresh (age ≤ 110 ms
  < the 140 ms tightest budget ⇒ K_age = 0); its danger is the *unserved* cars — at N=18
  vehicles 6–17 never actuate (age_path = n/a) and sit past PNR (min_pnr = 0). The state
  term catches them (K = 12, > cores for 98 % of the run); a pure age-vs-budget reading
  would call RM SAFE.
- **aguard is INVISIBLE to sim-crit.** Zero cars near PNR (it rotates cores to whoever is
  closest), but it deliberately runs cars far over the age budget (age 0.7–26.8 s ≫
  A(zone)) — recoverably. K_age = 6 exposes that; sim-crit alone calls aguard perfectly
  safe. K > cores only 0–12 % of the run.

**Why it matters.** Concrete proof the danger-relative `k` needs BOTH terms: the
age-budget term and the state/TTPNR term measure different failures (staleness pressure
vs recoverability), and each policy is invisible to one of them. The union `K` is the
sound conservative count and a strict superset of the old `--tau-crit`. This is the
empirical instrument that matches the theorem's `k` (THEOREM_BRIEF §3.6); the `K(τ)` curve
(one run) answers "a count at one τ is a saturated gauge" (2026-06-25).

**Honesty notes.** (1) `K_age` excludes never-actuated cars (no delivered command = a "no
service" failure, surfaced by the state term + the age=n/a summary row, not the age
budget) — so `K_age` is a *decomposition component*, not a standalone danger count; `K`
(the union) is the conservative object. Caught by the K ⊇ sim-crit superset check (an
early build skipped never-actuated cars before the state check, giving K=2 < sim-crit=12
— the sim, as adversary, flagged the gap). (2) A(zone) is the clean-entry table
(good-entry assumption, §3.2); the metric folds in actual TTPNR to cover degraded entry.
(3) Measurement-only — no scheduler reads it; baselines byte-identical.

**Evidence / repro.** `for n in 14 18; do for s in rm aguard; do ./build/cps --headless
--vehicles $n --scheduler $s --exec worst --duration 30; done; done` (read the
`danger-relative criticality` + `K(tau) curve` lines); `--danger-tau FRAC` moves the
primary point; `--align-offsets 1` for adversarial placement; CSV cols
`danger_tau,max_k_age,max_k_danger`. Code: `currentDataAgeOldestTicks` accessor
(TaskModel/Scheduler/PolicyScheduler) + the metric loop (`Simulation.cpp` step 3c).

**Where it lands.** The lead-contribution experiment: the danger-relative `K(τ)` demand
curve as the empirical shadow of the route-map bound's `k`, with the orthogonal-axes
finding as "why a single criticality metric won't do."

---

## 2026-06-29 — A(zone) is conditioned on good entry: tolerance is state-dependent, errors carry across zones

**What it is.** A user question exposed a load-bearing assumption inside the causal
A(zone) table (2026-06-26): `A(zone)` is keyed on *position on the track*, but the true
tolerance is **state-dependent** — a car entering a zone already near the 0.8 m bound
has ~0 tolerance regardless of the zone. So `A(zone)` implicitly assumes the car
**enters the zone well-tracked** (the state the clean N=1 measurement produces).

**Two quantities, two roles.** The state-dependent counterpart already exists in the
harness: **TTPNR** (the predictor rolls forward from the car's actual state). So
`A(zone)` = the *track's* demand (assumes good entry); TTPNR = *this car's*
instantaneous danger (reads real state). The bound reconciles them **inductively**:
respect `A(zone)` in *every* zone ⇒ no car accumulates enough error to reach the edge ⇒
the good-entry precondition holds everywhere ⇒ the edge-entering case can't arise.

**The wrinkle (= the overshoot finding, sharpened).** Errors carry *across* zone
boundaries — a car staled in z−1 enters z degraded — so `A(z)` measured for a clean
entry *under*-counts the danger for a degraded entry. The per-zone budget the induction
needs may have to be **tighter** than the isolated `A(z)`: charge the worst hand-off
from the previous zone. The user's extreme case: a car exiting z1 at the very edge
falls off *immediately* on entering z2 ("response time ≈ 0") — `A(z2)` doesn't cover it
because the good-entry precondition was already violated upstream.

**Consequence for the danger-relative metric (THE PLAN leg 4).** Do NOT build it as
purely "delivered age vs `A(zone)`" — fold in the car's *actual* state/margin (or
TTPNR), because accumulated error can make a car critical even with a fairly fresh
command. The danger signal and the occupancy count both need state, not just
age-vs-budget. (The coarse age-vs-`A(zone)` is a sound, conservative *starting* point;
just build with this in view.)

**Status.** Flagged as an explicit assumption + open wrinkle in THEOREM_BRIEF §3.2;
added as an ask for Kurt's inductive argument (§6.3c). Caught pre-submission.

**Where it lands.** The A(zone) methods + assumptions: state-dependence, the inductive
good-entry argument, and cross-zone error carry as the honest limitation.

---

## 2026-06-26 — Causal A(zone) table: the lane-change is the binding zone (140 ms)

**What it is.** Phase-2 (zone-conditional delay injection, `--zone-target`/
`--zone-extra-ms`, `tools/zone_sweep.py`) measured the **causal** data-age tolerance
per curvature zone (N=1 worst, full lap; largest delivered age with zero hard breaches
anywhere):

    A(z3 lane-change) = 140 ms   (BINDING)
    A(z0 straight)    = 290 ms
    A(z2 sharp turn)  = 290 ms
    A(z1 slight turn) = 400 ms

**Why it matters.** The first real, reproducible, physics-derived A(zone) table — the
input the route-map bound needs (THEOREM_BRIEF §3.2). The lane-change is ~2–3× tighter
than the rest, so it sets the route's binding tolerance. Validates Phase-2 (gate-clean;
injecting only in z3 breaches at +100 ms while z0 tolerates +200 ms — the causal method
corrects the Phase-1 manifestation inversion, next entry).

**Honest nuances.** (1) `A(z1 slight)=400 > A(z0 straight)=290`: non-monotonic in
instantaneous curvature — straights *precede* curves, so staling there delays curve
entry (spatial propagation). The zone label doesn't fully capture causal tolerance ⇒ a
refinement hook (an "approach-to-curve" notion). (2) Causal (sudden-in-zone) is more
conservative than uniform-global (~245 ms whole-plant `tolerance_sweep`): suddenly
staling at maneuver onset is a harder transient. The conservative, zone-specific value
is the right one for a safety bound.

**Evidence / repro.** `python3 tools/zone_sweep.py` → `zone_tolerance.csv`. Committed
`1158082`.

**Where it lands.** The A(zone) results: physics-derived per-zone tolerance with the
lane-change as the binding constraint; honesty notes on spatial propagation +
causal-vs-global.

---

## 2026-06-26 — Zone A(zone): breach MANIFESTATION ≠ CAUSE (overshoot into straights)

**What it is.** Wired per-zone breach attribution (Simulation buckets each frame's
hard/soft breach by `Trajectory::zoneAt`, lateral; instrument committed `47c8832`,
additive, gate-clean). The first Phase-1 delay sweep (N=1 worst, full lap) gives a
**surprising hard-cliff ordering** — at delivered age 250 ms the **straight (z0) and
lane-change (z3) breach first**; the **sharp turn (z2) not until 285 ms**, slight (z1)
310 ms. Occupancy is healthy (z0 5364 / z1 1716 / z2 3866 / z3 1054 frames), so this
isn't a sampling artifact.

**The finding.** Phase-1 attributes a breach to the zone where `|e_y| > 0.8`
**manifests** — which is where the car **overshoots**, i.e. the straight *following* a
maneuver — not the demanding zone that **caused** it via stale commands. So a
manifestation-based A(zone) reads `A(straight) ≈ A(lane-change) ≈ 250 ms`, which is
**misleading for the bound**. The causal A(zone) the bound needs (which zone's
staleness threatens safety) requires **Phase-2** (ZONE_TOLERANCE): inject delay only
while *in* zone z, and see when z's own staleness causes a breach (wherever it lands).

**Deeper implication for the bound.** Breaches manifest in zones away from their cause
⇒ a car's safety depends on its **recent trajectory**, not only its current zone. So
the bound's "occupancy of WC zones" (k) is **not** simply "cars currently in WC zones"
— a car that just *exited* a WC zone is still at risk. The danger window extends a
recovery-time past the zone, which bears on the decision horizon θ and the occupancy
definition (THEOREM_BRIEF §3.4/§3.5). Spatial error-propagation is a real subtlety of
physics-derived tolerance.

**Status / honesty.** Do NOT publish a manifestation A(zone) as the bound's tolerance.
Phase-1 instrument is committed and useful (occupancy + manifestation view); the
**causal** A(zone) = Phase-2 (a zone-conditional delay hook), the next step.

**Evidence / repro.** `for d in 16 64 96 112 128; do ./build/cps --headless --vehicles
1 --scheduler rm --exec worst --duration 120 --net-delay $d; done` (read the "zone
breaches" / "zone frames" lines).

**Where it lands.** The A(zone) methods section + an honesty note that physics-derived
tolerance is trajectory-dependent (error propagates spatially), motivating Phase-2
causal attribution and a θ that covers post-zone recovery.

---

## 2026-06-25 — The map IS the disturbance model: the fleet-safety bound is a function of the route's zone structure

**What it is.** The sharpened form of leg (A). Working the simultaneous-criticality
worst case (next entry) forced a reframing of what the fleet-safety bound *is*. The
old shape — "physics bounds the number of loops simultaneously critical to k < N,
compose with an RTA" — does **not** survive: an adversary can put all N cars in
worst-case track zones at once (realistic when the *route* has worst-case zones
distributed around it, not just the unrealistic all-stacked sim case), so the
worst-case simultaneity count is **k = N** and there is no slack — back to the
pessimistic "all-critical-at-once" assumption.

**The resolution (the actual contribution shape).** The physics re-enters not as a
count cap but as the **route**: the bound is a **function of the track's zone map**.

    worst-case demand = (number/extent of worst-case zones on the map)
                        × (cars that fit in each zone's danger window at once),
                        capped at N;
    safe iff m cores can meet each car's A(zone) deadline under that demand.

Two map-derived slack mechanisms: (1) **spacing/geometry** — cars occupy distinct
positions, so only so many fit a WC zone's danger window at once (< N on a long
route, unless the map is WC-everywhere); (2) **per-zone tolerable age** (load-bearing)
— a car on a straightaway tolerates huge staleness (a stale "go straight" is still
correct) and barely needs a core; only cars in tight zones need frequent service.
The physics enters as **A(zone)** — exactly the zone-tolerance quantity
(`ZONE_TOLERANCE.md`), now promoted from EE side-experiment to an **input to the
bound**.

**Why it's the honest framing.** The bound is **tight, not universal**: it reports
the slack *this route* offers. Benign route (mostly straight) → much slack → admits
many cars; pathological all-WC route (a slalom) → zero slack → degrades gracefully
to the classical pessimistic capacity. That degradation is a *feature* (honest about
a genuinely hard route), not a failure. "Our bound is parameterized by the route's
worst-case-zone coverage" is a concrete, checkable assumption — far more defensible
than an abstract "bounded disturbance" class. **The map is the disturbance model**,
which dissolves the existential risk flagged 2026-06-21/22 (unconstrained
disturbances ⇒ k = N).

**The plan it implies (3 legs + a metric fix; HANDOFF §5 "THE PLAN").** (1) define
A(zone) rigorously from the control physics (ZONE_TOLERANCE Phase 1/2 — control/EE
side); (2) worst-case zone *occupancy* given map + a **fleet model** (free-flowing vs
bunching — state the assumption); (3) schedulability composition over the BOUND §7
RTA (Kurt); (4) redefine the simultaneity metric to be danger-relative (next entry).

**Where it lands.** The lead contribution / theorem framing: the fleet-safety bound
as a route-parameterized schedulability test (vs Sudvarg's per-loop utilization
co-design — ours is a cross-loop, route-derived demand bound). Forced by the
empirical work in the next entry.

---

## 2026-06-25 — tau_crit is a saturated gauge; k ≈ N at the decision horizon; the count is not the bound

**What it is.** A re-examination of the simultaneous-criticality metric
(`--tau-crit`, PREDICTOR §5d), started from a user question — "why count cars that
are already past saving?" — that overturned how we read `k`.

**Finding 1 — the horizon makes the metric say opposite things.** `k(τ)` =
max-over-run of #{cars : TTPNR < τ}. At τ = 100 ms (≈ one round-trip, the default) it
reads near 0; raise τ toward the *decision* horizon (round-trip + time to actually
get served) and `k` jumps to ≈ N. **Same run.** Cart-pole aguard N=16 worst 20 s:

| τ (ms) | max sim-crit | % run over cores | crashed |
|---|---|---|---|
| 100 | 10/16 | 0.17 % | 0 |
| 200 | 16/16 | 44.9 % | 0 |
| 300 | 16/16 | 93.7 % | 0 |

The "max 10, 0.18 % over cores" headline (HANDOFF/PREDICTOR §5d) is an artifact of
measuring at exactly the round-trip horizon; the real decision-horizon demand is the
whole fleet, almost always. τ = 100 is a **saturated gauge reading near its floor**.

**Finding 2 — the count is not the bound; service-rate is.** At τ = 300, k = 16 ≫ 3
cores for 94 % of the run, yet aguard crashes **0/16** (RM crashes 9). Safety does
NOT come from "few simultaneously critical" — it comes from the scheduler *rotating*
3 cores through 16 poles fast enough that none reaches PNR. The naive (A) "physics
bounds k ≤ m ⇒ safe" is **false as stated** (k ≈ N). The bound must be a throughput
property — which forced the route-map reframing (entry above).

**Finding 3 — TTPNR-under-held conflates instability with danger.** For an *unstable*
plant, "time to unrecoverable if I freeze the command" ≈ the natural fall time
(√(L/g) ≈ 200–300 ms for the pole — exactly where the table saturates). So
"TTPNR < 300 ms" flags *every* pole *always*: it measures open-loop instability, not
closed-loop risk. The metric means different things on the stable car (genuine drift
to the lane edge) vs the unstable pole (perpetual). ⇒ **redefine the metric to be
danger-relative** (delivered age vs A(zone) tolerable age, or distance-to-PNR), not
TTPNR-under-held.

**Finding 4 (the `--align-offsets` A/B) — the car's benign number is NOT a spread
artifact.** New `--align-offsets FRAC` knob (0 = even spread, default; 1 = all cars on
one lap phase = adversarial; lateral only — cart-pole's shove is already global-phase).
Car aguard N=18 worst: aligning barely moves sim-crit (1→2 of 18), and aguard holds 0
hard breaches even at **26.8 s** data age. On the *same* aligned segment, physics-blind
RM lets **14/18** go critical and crashes the fleet — so the segment IS adversarial;
the protection is the scheduler doing real physics-aware work, not luck from spacing.
Reconfirms the car "binds on scheduling, not physics" under adversarial alignment.

**Evidence / repro.** `--align-offsets 1` on lateral; `--tau-crit {100,200,300}` on
either plant. Scratch recordings: `/tmp/{spread_rm,aligned_rm,aligned_aguard}.cpsr`.
Code: `--align-offsets` (`Simulation.{h,cpp}`, `main.cpp`; byte-identical at FRAC 0).

**Where it lands.** Motivates the route-map bound (entry above) and a redefined
simultaneity metric; the τ-sweep + align A/B become the "why a count won't do" figure.

---

## 2026-06-23 — Cart-pole calibration to paper-grade: the tolerance cliff is invariant to it

**What it is.** `HANDOFF §5 item 1`. The cart-pole's control params were first-pass
round numbers; now derived by the car's `delta_max` method (×1.5 of observed
actuation) so the generality headline is publishable. Procedure (GENERALIZATION §4):
**uMax = 1.5 × observed peak control demand** — measured `max|pre-clamp force|` over a
clean N=1 `--exec worst` run (new `--validate-predictor` "actuator calibration aid")
= **7.7012 N → uMax 11.55 N** (the old 10.0 was only 1.30×, *under* the standard).
Safety envelope `thetaHard`/`thetaSoft` (0.21/0.05 rad) kept as the *given* physical
spec (the 0.8/0.2 m analogue; nominal-fresh peak |θ| ≈ 30 % of `thetaHard`).
`shoveForce` 8 N kept, fixed ≤ authority (emergent `shove/uMax` = 0.69 ≤ 0.80).

**The load-bearing finding: the age-tolerance cliff boundary is invariant to the
calibration.** Car (245.5, 345.5] ms and cart-pole (105.5, 110.5] ms are **identical
pre/post** at the sweep resolution (`tolerance_sweep.csv`). *Not* because the clamp
is free — under the sweep's injected staleness the held command grows and the demand
does reach the clamp, so the near-cliff peak |θ| (0.18→0.20 rad, still safe) and the
post-crash breach counts shift (the CSV caught this; the first "clamp-free" story was
wrong). It holds because the exponential cliff is so sharp that the ~15 % authority
change can't move the recoverability boundary by a full sweep step. A clean robustness
result for the physics-derived-tolerance thesis: the headline ~2.5× sharper cart-pole
tolerance is a property of the *dynamics* (the instability timescale), not a tuning
artifact of the actuator limit.

**What did move (predictor-driven metrics, which use uMax as recovery authority):**
N=1 `min_pnr` 100→110 ms; cart-pole sim-crit N=8 **2→1**, N=16 max still 10 but
**dwell-over-cores 0.79 %→0.18 %**; honest aguard-honest N=8 gap milder (**2→3** at
d=16, was 2→4). Capacity: aguard now **17 crash-free** vs RM's **10** (N=16: 0 vs 9;
20 s worst) — but a controlled `--u-max 10` run shows aguard already reaches 0/17 at
the old authority, so **the ~14→17 gain is the per-vehicle-θ floor fix (`3214880`),
NOT this calibration**; calibration only trims N=18 from 3→1 crashes. RM unaffected by
uMax (no predictor; the plant clamp rarely binds even under overload).

**Why it matters.** Moves the cart-pole numbers from "first-pass, exact values TBD" to
"derived by a stated, reproducible method" — the paper-grade bar for the generality
leg. And the invariance result is a *positive*: it isolates the tolerance contrast as
pure physics. Honesty note: the qualitative story (sharp ~110 ms cliff vs gradual
~245 ms; aguard protects the unstable plant; the two plants bind on different legs)
**survived and sharpened** under a principled calibration — it was not tuned in.

**Evidence / repro.** Demand: `./build/cps --headless --plant cartpole --vehicles 1
--scheduler rm --exec worst --duration 30 --validate-predictor` (read "actuator
calibration aid"). Cliff: `python3 tools/tolerance_sweep.py`. Capacity/sim-crit/honest:
`--plant cartpole` with `--scheduler {rm,ttu,aguard,aguard-honest}`, `--u-max` to
isolate calibration. Details: GENERALIZATION §4.

**Where it lands.** The generality/method section: the cart-pole's control params are
calibrated by the same principle as the car; the physics-derived age-tolerance is
shown invariant to that calibration.

---

## 2026-06-23 — Kundu–Quevedo'19 close read: optimal rotation does not pre-empt (A) (Kurt-question 2)

**What it is.** Full read of the second existential near-neighbor (Kundu & Quevedo,
"Stabilizing Scheduling Policies for Networked Control Systems," arXiv 1901.08353,
2019; `relatedPapers/DirectlyRelatedToYourSpecificProblem/Kundu_Quevedo_2019_...pdf`)
— settling Kurt-question (2): does their *optimal rotation* already admit our fleets?

**What they do.** N discrete-time *linear* plants, open-loop *unstable* / closed-loop
stable; a shared channel serves M<N at a time, the rest run open-loop and drift. Goal
= **asymptotic stability (GAS)** of every plant (converge to origin). Method = a
**static, offline, periodic** schedule (a "T-contractive cycle" on a graph, via
Lyapunov/LMI). Naive round-robin can fail (their Fig. 3); the optimal cycle fixes it.
Expensive at scale (Table 4: N=700 → 21 h). Future work = network delays/dropouts —
not safety/disturbances/simultaneity.

**Verdict — rotation does NOT pre-empt (A); three fundamental differences:**
- **Stability vs safety.** They guarantee long-run convergence to the origin; we
  guarantee the state never crosses a hard bound / PNR (a transient hard constraint).
  A plant can be GAS yet transiently overshoot a safety wall ⇒ rotation ≠ our guarantee.
- **No disturbance / criticality.** Their plants are autonomous (decay from initial
  conditions); there is no crisis, so "how many critical at once" isn't even a
  question — rotation just ensures enough total access per period. Our staggered-crisis
  bound k has no meaning in their world.
- **Static vs dynamic.** Their schedule is a fixed offline cycle (hours to compute);
  ours reacts online to which loop is near its PNR now (~10 µs/prediction).

**Residual for Kurt:** shared *spirit* ("more loops than resources, keep all OK"), so
position against K–Q in related work. The deeper "could a K–Q-style contractivity
argument be *extended* to a safe-set/PNR Lyapunov function + disturbances and then
subsume our fleets?" is a generalize-the-neighbor question (field judgment, not a
read). My read: the gap is fundamental (different guarantee, no criticality notion,
static), so not a trivial extension.

**Combined with the Sudvarg read (below):** both make-or-break questions are now
*factually* answered — neither prior pre-empts our cross-loop simultaneity bound +
recoverability deadline. Existential risk drops to "positioning + whether neighbors
could be extended" (Kurt's informed call).

**Where it lands.** Related-work: contrast with K–Q (stability via static rotation of
autonomous unstable plants) alongside Sudvarg (per-loop utilization-based co-design).

---

## 2026-06-23 — Sudvarg RTAS'25 close read: both our differentiators survive; one future-work near-miss

**What it is.** Full read of the closest prior (Sudvarg, Clark & Gill, "Integrated
Real-Time Control and Scheduling for Safety-Critical CPS," RTAS 2025;
`relatedPapers/DirectlyRelatedToYourSpecificProblem/Sudvarg_...pdf`) — settling
Kurt-question (1) on the *factual* level: does it already bound cross-loop
simultaneity?

**Verdict — our two claimed differentiators are genuinely absent:**
- **Cross-loop simultaneity bound — NOT present.** Their scheduling is classical
  **utilization-based**: each controller gets a *fixed* safe period `T_i ≤ T_i^max`
  (physics-derived via CBF + sum-of-squares) and runs at that rate always;
  schedulability = aggregate utilization fits (`Σ C_iω_i ≤ U_D`; partitioned-EDF
  bin-packing ≤ (m+1)/2). They never bound *how many loops are simultaneously
  near-unsafe* to admit more than the utilization test allows — i.e. exactly the
  pessimistic aggregate-demand view our (A) aims to beat.
- **PNR / recoverability deadline — NOT present.** Safety = CBF **positive
  invariance** (stay in safe set `W_i`) + a margin-triggered switch to a
  conservative backup controller near the boundary. No time-until-recovery-
  impossible countdown; set-membership, not a dynamic recoverability deadline.

**The risk I did find (positioning + scoop).** Their §VII future-work closes,
verbatim: *"can we leverage predictions or semi-clairvoyant mixed-criticality theory
to be more optimistic in our assignment of execution times across transitions?"* —
the same beyond-worst-case *spirit* (prediction → less pessimism), named as THEIR
next direction. It is **not** our simultaneity bound (they mean execution-time
optimism across mode transitions), but (a) we must position sharply against it, and
(b) it's a **scoop risk** — this group is best placed to take the next step.
Neighbors to check for the same reason: [31] semi-clairvoyant MC
(Agrawal–Baruah–Burns RTSS'19), [54] "Good-spread: criticality-aware static
scheduling" (Roy et al. RTSS'20).

**So Kurt-question (1) is answered factually: NO, Sudvarg does not pre-empt our
device.** What remains for Kurt is the narrower, *informed* judgment: is
"simultaneity bound + recoverability" a big-enough delta given the future-work
bullet above? (Field-perception call, his.) Kurt-question (2) — vs Kundu–Quevedo
optimal rotation — still open.

**Where it lands.** Related-work: position our cross-loop simultaneity + PNR
contribution explicitly against Sudvarg's per-loop utilization-based co-design *and*
against their "predictions for optimism" future-work bullet.

---

## 2026-06-23 — Predictor compute cost: ~10–17 µs/rollout, a few % of a core (Finding B)

**What it is.** Direct timing of the `predictHeld` rollouts, printed per run
(`prediction compute: us/prediction, %-of-one-core`), replacing the misleading
"+17 % wall" aggregate. **Car (optimized matrix-cache predictor): ~10–17
µs/prediction; ≤ 3 % of one core through N=18, ~4 % honest (both rollouts).** So the
predictive scheduler's compute is **decisively negligible** against the 3 worker
cores — shown, not assumed. **Cart-pole** (naive 1 ms RK4, no cache): ~344 µs, 27 %
of a core at N=8 — ~30× heavier (a generality-demo caveat, not paper-grade).

**Why it matters.** Closes "is the method computationally realistic?" with a number.
Per-prediction cost is independent of fleet size; the fleet load scales linearly and
stays ~2–4 % of a single core (car). The right denominator is a CPU core (vs the
free FMU sim) — the "+17 % wall" was an artifact of the wrong one. Stated
assumption: the dedicated cloud scheduler runs on separate orchestration infra, not
the N_c worker cores. **Compute is not the binding realism constraint — input
freshness (the honest predictor, 2026-06-22) is.**

**Evidence / repro.** `./build/cps --headless --vehicles 18 --scheduler aguard
--exec worst --duration 30` (read the `prediction compute:` line); honest ~2×;
`--plant cartpole` ~30×. Details `PREDICTOR.md §5f`.

**Where it lands.** The feasibility/realism paragraph: the predictor is real-time
trivial on the car; the cart-pole predictor needs the same optimization to match.

---

## 2026-06-22 — Honest predictor: oracle-vs-delayed-state A/B (the credibility leg)

**What it is.** `HANDOFF §5 item 3`. Every predictive policy (ttu/hybrid/aguard)
ranked TTPNR seeded from TRUE state (an oracle). Added `-honest` twins that seed
the *same* rollout from the cloud's legitimate **delayed** state
(`--pred-staleness`, default 16 ms = worst sensor delay) + a safety margin
(`--pred-margin`); shared `InfoSet` flag, oracle variants kept for the A/B. Off by
default (baselines byte-identical; `--pred-staleness 0` ≡ oracle). **The sim-crit
metric stays on the oracle (true-state) rollout** — it measures ground-truth safety
under honest decisions.

**Headline — the two predictive families split (car, worst, 3 cores, 30 s,
τ=100 ms), by true sim-crit max:**
- **`ttu` (pure safety) is robust to honesty:** sim-crit stays **0** through d=16
  *and* d=100 ms staleness; only d=200 lets 1 car slip. A stale estimate still
  fingers the nearest-PNR car.
- **`aguard` (comfort-optimizing) is fragile:** N=18, even **16 ms** staleness
  takes sim-crit **0 → 4** (>cores 1.08 %); d=100 → 14. Its razor margin (worst
  car 15 ms over the line, §5d) can't absorb the staleness.
- **A margin buys it back:** aguard-honest N=18 d=16, `--pred-margin` 0/30/60/100
  → sim-crit 4/3/**0**/0. ~60 ms conservatism fully restores oracle safety.
- Plant-agnostic: cart-pole aguard-honest N=8 sim-crit 2 → 3 (post-calibration; was 2 → 4).

**Why it matters.** Closes "every predictive policy reads ground truth today" — the
biggest credibility gap — with a *quantified* cost and a principled recovery. The
nuance IS the result: **the safety-only scheduler is robust to imperfect
information; the comfort-optimizing one trades safety margin for comfort and must
pay it back with a conservatism margin.** A design lesson, not just a robustness check.

**Caveat (honesty boundary).** Deterministic harness + exact plant port ⇒ the
honest gap is pure information **staleness**, NOT sensor noise / model error (a
model-based observer would recover the truth). So `honest ≈ oracle` at small d is
expected; the *fragility* (aguard) and *margin-recovery* findings are load-bearing.
Folding in the FMU's own `e_y_est` estimation error is the open refinement
(PREDICTOR §6.4).

**Evidence / repro.** `python3 tools/reproduce.py honest` (one command →
`honest_sweep.csv`), or by hand: `for d in 0 16 100 200; do ./build/cps --headless
--vehicles 18 --scheduler aguard-honest --exec worst --duration 30 --pred-staleness
$d; done` (+ `--pred-margin`, `--scheduler ttu-honest`, `--plant cartpole`). Details
`PREDICTOR.md §5e`.

**Where it lands.** The credibility section / "honest information" experiment:
oracle is an upper bound, honest is achievable, the gap is small for safety-ranked
scheduling and recoverable with a physically-motivated margin.

---

## 2026-06-22 — Simultaneous-criticality metric: the empirical (A)-shadow (implemented)

**What it is.** `HANDOFF §5 item 0` built: a per-base-tick count of vehicles with
`ttpnr_ms < τ_crit` (τ_crit ≈ one command round-trip; `--tau-crit`, default
100 ms), reporting run-max + dwell-histogram (summary line + 3 CSV columns). The
empirical instrument for leg **(A)** — measures the realized count of loops
simultaneously within reaction-time of their PNR. Measurement-only (no scheduler
reads it; all baselines byte-identical, fidelity gate still 1.490e-08 m).

**Headline (car, worst exec, 3 cores, 30 s, τ_crit = 100 ms).** TTPNR-blind RM
lets **7 loops (N=14) / 12 (N=18)** sit within 100 ms of PNR at once — far past 3
cores. TTPNR-aware **ttu and aguard hold it to 0 at every N** (worst car ≥ 115 ms
from PNR at aguard N=18, ≥ 185 ms at ttu N=14; zero hard breaches) ⇒ 3 cores
suffice to keep the whole fleet out of the must-serve-now zone under the
physics-derived schedulers; the physics-blind one drowns. Fails to refute (A) for
the predictive policies.

**Caveat (do NOT oversell).** `sim-crit = 0` ≠ fleet fine: aguard N=18 keeps 0
critical while feeding cars **26 s-stale data + 43–55 % soft violations** — a
high-error-but-recoverable band. The metric is **distance-to-PNR simultaneity,
not control quality.** Margin is thin: `--tau-crit 150` → 1 critical at aguard
N=18. RM > cores is the physics-blind baseline contrast, **not** an (A)
counterexample (a better policy gets k = 0).

**Generality (different leg).** Cart-pole: aguard does NOT contain it — N=16 max
**10** but only **0.18 %** of the run over cores, N=8 max **1**; RM N=16 max 10
(99.42 %). The unstable plant's sharp cliff makes more loops critical at once ⇒ car
binds on scheduling, cart-pole on physics. (Numbers re-derived under the 2026-06-23
param calibration; the peak max-10 is unchanged but the dwell-over-cores fell
0.79 %→0.18 % with the calibrated recovery authority.)

**Open / contingent.** This is the empirical shadow, **not** the theorem — still
contingent on (A) surviving Kurt (does the physics actually bound k? is k < m
achievable where a naive "all-critical-at-once" test fails?). The real (A) test is
whether the *best* predictive policy can be forced past cores while loops are
still recoverable: on the car it cannot through N=18; on the cart-pole it can at
N=16 (peak max 10 > 3 cores — still true post-calibration, though only 0.18 % of
the run is actually over cores).

**Evidence / repro.** `python3 tools/reproduce.py simcrit` (one command →
`simcrit_sweep.csv`), or by hand: `for s in rm ttu aguard; do for n in 6 14 18; do
./build/cps --headless --vehicles $n --scheduler $s --exec worst --duration 30; done;
done` (+ `--tau-crit`, `--plant cartpole`, `--csv`). Details: `PREDICTOR.md §5d`.

**Where it lands.** The lead-contribution experiment for (A): "N loops, m cores,
never more than k critical at once" — the headline scheduling figure, paired with
the honest "distance-to-PNR ≠ control-quality" caveat.

---

## 2026-06-22 — Related-work / novelty survey: novelty narrows to (A); B/C demoted; a must-cite was missing

**What it is.** Preliminary SOTA/novelty survey of the three candidates (A/B/C,
see 2026-06-21 entry) — scaffolding for Kurt's verdict, NOT a verdict. Outcome:

- **Thesis ("derive timing from physics") is NOT novel.** The group's own Wilson
  et al., *Physics-Informed MC Scheduling for F1Tenth Cars*, RTAS 2025 (+ Wilson
  et al. MEMOCODE'24) already own physics-derived timing + physics-informed
  criticality (single car, uniprocessor, UPPAAL-checked).
- **(B) age-tolerance ~1/λ law → established prior; demote to background.**
  Sudvarg–Clark–Gill RTAS'25 *derive* a certified safe sample-to-actuation delay
  from the physics (CBF + sum-of-squares); the AoI-control line states the same
  relationship independently (Etcibasi–Koksal–Ekici 2026, *When Freshness Is Not
  Enough*: LQR cost ~ `E[a^{2Δ}]`, exponential in staleness for unstable plants),
  as do MATI (Nešić–Teel) and classical delay-margin. Two independent fields ⇒
  known. Our only edge is *applicability* (sim-based predictor handles a black-box
  FMU where CBF/SOS needs a polynomial model) — a method-reach point, not a new idea.
- **(C) scheduling from estimated state → fold into (A).** Estimation + triggering
  is mature (observer-based / robust self-triggered ETC); best framed as "(A) still
  holds under estimated state + a margin," not a standalone leg.
- **(A) fleet-safety theorem → the ONLY surviving leg.** Claim: *bound from the
  physics how many of N loops are within reaction-time of their PNR simultaneously
  (≤ k), compose with a multicore RTA ⇒ m cores keep all N safe — admitting more
  loops than an "all-critical-at-once" test.*

**Closest prior (a must-cite that was NOT in our collection).** Sudvarg, Clark &
Gill, *Integrated Real-Time Control and Scheduling for Safety-Critical CPS*, RTAS
2025 (DOI 10.1109/RTAS65571.2025.00037; free: par.nsf.gov/servlets/purl/10627676).
Multi-loop control on a shared (multi)processor, **safe-set (CBF) safety not just
stability**, per-loop max safe period/delay derived from physics, composed with
multiprocessor schedulability, + Simplex backup — i.e. most of our program, one
year early. What it does NOT do (room for (A)): a **cross-loop bound on how many
loops are simultaneously critical**, and a **PNR/recoverability** safety notion.
Second-closest: Kundu–Quevedo 2019 (arXiv 1901.08353) — N open-loop-unstable plants,
only M<N served, keep all **stable** by *optimal rotation tuned to each plant's
instability rate*; no simultaneity bound, and no disturbance/environment structure
(so "how many critical at once" isn't even a question in their world).

**The single biggest novelty risk.** (A)'s defensibility rests on two questions
only Kurt can settle: (1) does Sudvarg §IV (pp.316–322, unread) already exploit a
cross-loop demand/simultaneity bound? (2) does our simultaneity bound admit fleets
that K–Q-style *optimal* rotation cannot — or does good rotation already get there?
If either fails, (A) may have no novel leg left.

**Honesty notes.** Survey is AI-scaffolded; Kurt renders the verdict (missed-scoop
risk is real — "found nothing closer" is weak evidence). `Li et al. RTSS'24` (cited
in `BOUND.md §5`) could NOT be independently confirmed to exist as described —
verify the handle. **[RESOLVED 2026-07-17: verified — it exists, is correctly
attributed, and was in `relatedPapers/` all along (the `Priority_Optimization_…`
filename hid the "Li et al." handle from the survey). See the 2026-07-17
citation-check entry.]** The 5 must-cite PDFs (Sudvarg, Kundu–Quevedo, Etcibasi,
Wilson-F1Tenth, Wilson-MEMOCODE) are now in `relatedPapers/`.

**Where it lands.** Related-work section (position vs Sudvarg / Kundu–Quevedo /
AoI-control, plus the context cluster: self-triggered/MATI/mixed-criticality/
weakly-hard). Motivates the "measure simultaneous criticality" experiment
(`HANDOFF.md §5` item 0) and frames the paper's lead contribution as the
simultaneous-criticality device.

---

## 2026-06-21 — Where the novelty must live (candidate contributions + honesty boundary)

The high-level thesis ("derive timing from physics / more context → better timing
decisions") is **not novel** — it's the field's premise plus dense prior art
(self-triggered & event-triggered control, control–scheduling co-design,
mixed-criticality, weakly-hard RT, cause-effect-chain latency, and Wilson
MEMOCODE'24, which we *extend*). A real contribution must be a *specific
provable/measurable delta* the prior lacks. Three candidates:

- **(A) Fleet-safety theorem for shared-resource control** — prove m cores keep
  ALL N physics-driven loops safe, by composing (control) a bound on how many
  loops can be *simultaneously* near their PNR with (scheduling) an RTA that those
  can be served in time. Technical heart: bounding *simultaneous criticality* from
  the dynamics. Beats single-loop self-triggered control. Deepest; the formal/Kurt
  leg. (Generalizes the θ ≥ floor + age_bound theorem in §5.)
- **(B) Predictive law: age-tolerance from plant physics** — A(plant) computable
  from a characteristic timescale (e.g. ~1/λ for an unstable mode), validated
  across a *spectrum* of plants. Turns two examples into a general law.
- **(C) Physics-derived scheduling under honest (estimated) information** —
  near-optimal scheduling + a safety margin from *estimated* state despite
  estimation error (self/event-triggered assume full state). = the honest
  predictor, reframed as a contribution.

**Honesty boundary:** the cart-pole generalization proves the framework is
*general & physics-derived* (meaningful), **NOT** *novel*. Generality ≠ novelty.

**Next gate (existential):** which (if any) of A/B/C is unclaimed needs the
**related-work survey** + Kurt's field judgment — it determines whether there's a
paper at all. An AI lit survey can *scaffold* it (find/map the closest prior) but
cannot render the *verdict* (missed-scoop risk; community judgment). A survey
prompt was prepared 2026-06-21.

---

## 2026-06-18 — Age-tolerance is physics-derived & plant-dependent (cart-pole vs car)

**Observation.** A second plant (inverted pendulum on a cart, `--plant cartpole`)
runs on the *identical* scheduler / data-age / bound machinery as the FMU car —
only the physics differs. Delay sweep at N=1 (`tools/tolerance_sweep.py`);
tolerance = largest achieved `age_path` with zero hard breaches:
- **car (stable): ~245 ms, gradual** onset (breaches by 345 ms).
- **cart-pole (unstable): ~110 ms, a razor-sharp ~5 ms cliff** (safe at age
  105.5 ms, crashed at 110.5 ms).
At any delivered age ≥ 110 ms the pole has crashed while the car is fine to
~345 ms — a **~2.5× tighter, far sharper** tolerance, set purely by the plant's
dynamics. Clean controlled comparison: same chain, same delivered age per delay;
only the physics changes.

**Update 2026-06-23 (calibration):** the cliff *boundary* is **unchanged** under the
paper-grade param calibration (uMax 10→11.55 N; see the 2026-06-23 entry) — safe
≤105.5 ms, breach ≥110.5 ms, both pre/post. (The near-cliff peak |θ| and post-crash
breach counts do shift — the clamp binds under the sweep's staleness — but a ~15 %
authority change can't move the sharp recoverability boundary a full sweep step.) The
tolerance contrast is confirmed governed by the instability timescale, not a tuning
artifact of the actuator limit.

**Why it matters.** The thesis on two plants: timing requirements should be
*derived from the physics* because they are plant-dependent, and instability
makes the point-of-no-return genuinely physical / the deadline tight. This is the
headline generalization figure.

**Evidence / repro.** `python3 tools/tolerance_sweep.py` → `tolerance_sweep.csv`.

**Where it lands.** Route A/B intro + Q4 (the age↔control / physics-derived-timing figure).

---

## 2026-06-18 — Age-criticality scheduling generalizes: aguard protects the unstable plant

**Observation.** Cart-pole under contention (exec worst), crashed poles (hard>0),
RM vs aguard:

| N | RM crashed | aguard crashed |
|---|---|---|
| 12 | 3/12 | **0/12** |
| 14 | 5/14 | **0/14** |
| 16 | 9/16 | **0/16** |
| 18 | 13/18 | **1/18** |

aguard carries **17 cart-poles crash-free vs RM's 10**, and crashes far fewer
at every overload — by feeding the freshest command to whichever pole is nearest
its (physics-derived) PNR. (It takes more overruns from reordering but converts
them into zero crashes.)

**Update 2026-06-23 (re-derived, calibrated + floor-fixed).** Table above is the
current code (per-vehicle-θ floor fix `3214880` + the 2026-06-23 param calibration),
20 s worst. The lift from the original ~14→17 crash-free is **the floor fix, not the
calibration**: a controlled `--u-max 10` run already gives aguard 0/17 at the old
authority; calibration only trims N=18 from 3→1 crashes. RM is identical at both uMax
(no predictor; the plant clamp rarely binds even under overload). The qualitative
contrast (aguard protects the tight-tolerance unstable plant where RM fails) holds
and is sharper.

**Why it matters.** The *same* age-criticality scheduler that carries 18 cars
(vs classics' 10–12) also protects the tight-tolerance *unstable* plant where RM
fails — the TTPNR-guided guard is plant-agnostic because TTPNR is computed from
each plant's own physics. Route-B generality, on a second plant.

**Evidence / repro.** `python3 tools/reproduce.py capacity` (one command →
`capacity_sweep.csv`), or by hand: `for n in 12 14 16; do for s in rm aguard; do
./build/cps --headless --plant cartpole --vehicles $n --scheduler $s --exec worst
--duration 20; done; done` (count vehicle rows with hard>0).

**Where it lands.** Route B (age-criticality scheduling) generality section.

---

## 2026-06-17 — RTA certification gap (Q1 headline): certified 5 vs empirical 10

**Observation.** A machine RTA solver (`tools/rta_solve.py`, validated against
hand calcs and cross-checked sound vs the sim) gives, at m=3 cores / worst exec:
**certified capacity 5** (first overrun F_5 at N=6 under the §7.2 full-carry-in
workload) vs **empirical capacity 10** (`missed jobs: 0` through N=10; 4497 at
N=11) — a **2× certification gap**, entirely the pessimism of the borrowed
full-carry-in workload term. Sound fix: limited carry-in (m−1, Guan RTA-LC).

**Why it matters.** This *is* the Q1 "certification gap" headline (BOUND §7.4
item 1): classic worst-case RTA under-utilizes by 2× here, motivating both the
limited-carry-in refinement and the Challenge's whole "beyond-worst-case"
framing. The number a paper can claim is **5 today → in (5,10] once the workload
is re-derived** (Kurt, §7.4 item 2) — that re-derivation, not the arithmetic, is
the critical path.

**Secondary finding (methodology).** BOUND §7.3's hand-iterated v5 R-values
(107/129/117) were **wrong** — matching neither the full- nor no-carry-in
workload consistently; caught only by the machine solver. Reinforces "machine-
verify every hand-iterated number"; the solver now makes that cheap.

**Evidence / repro.** `python3 tools/rta_solve.py --cross-check`. Corrected
values + gap recorded in `BOUND.md §7.3`.

**Where it lands.** Route A, the Q1 result + the "why beyond-worst-case" motivation.

---

## 2026-06-17 — Per-vehicle measured age is set by phasing, not by R ordering

**Observation.** At N=6, RM, `--exec worst`, the bound's worst-R vehicle (5) is
**not** the measured-worst vehicle (0). Measured `age_path` clusters in 10 ms
steps (v0 = 100.5, v1 = 80.5, v2–v5 = 90.5) governed by benign synchronous
phasing — the R differences the bound keys on (e.g. v5's `R_M` = 11.7 vs v0's
3.7 ms) get swamped. **You cannot predict which vehicle is worst from the R
ordering.**

**Why it matters.** Concrete, run-backed instance of the §4 "benign-phasing
pessimism." It's also a caution against any per-vehicle tightness claim, and it
motivates the offset/harmonic-aware sampling terms (BOUND §5 item 2 / §7.4
item 3) as the real source of slack.

**Evidence / repro.** `./build/cps --headless --vehicles 6 --scheduler rm
--exec worst --duration 30` (`missed jobs: 0`). Deterministic (60 ms
hyperperiod, synchronous release).

**Where it lands.** Route A, the "soundness & tightness" / decompose-the-gap
discussion. Recorded in `BOUND.md §7.3` reconciliation note.

---

## 2026-06-17 — Hold-free bound is on the verge of refutation at N=6 (true-R)

**Observation.** With the §7 RTA supplying true-R, vehicle 0's **hold-free**
bound (drop the +T_A term) is 131.6 − 30 = **101.6 ms**, vs measured
`age_path` = **100.5 ms** — it survives by only **1.1 ms**. This is the N=6
true-R analogue of the N=1 "survives by 0.3 ms" slack-cancellation, and it
**closes the open question in §5.4** ("the clean refutation needs the true R_i
at N≥6 … we cannot evaluate it until the RTA exists"). The clean way to tip it
past refutation is a **longer actuator period**: the hold-free bound (full −
T_A) is independent of T_A, but measured age grows with the real hold, so
measured overtakes it. More load is ambiguous (the bound's phasing pessimism
grows with R too).

**Why it matters.** This is the project's flagship cautionary tale made sharp:
"measured ≤ bound" holds for a structurally *wrong* (hold-omitting) bound by a
hair, because chain-latency slack nearly cancels the omitted hold term. A
crisp, quantitative argument that tightness ≠ structural correctness — decompose
the gap per term.

**Evidence / repro.** v0 true-R bound 131.6 (BOUND §7.3) − T_A (30) = 101.6;
measured 100.5 from the run above. Re-run after BOUND §5 work items 1–2 land.

**Where it lands.** Route A, the refutation-experiment / "why we decompose"
narrative (BOUND §5.4). Recorded in `BOUND.md §7.3`.

---

## 2026-07-29 (evening) — HIL: the physics-derived pipeline generalizes to a second physical track in ~1 hour

**Observation.** The full HIL stack (map → localize → record human lap →
derive feasible reference → validate in sim → shadow → live under the cloud
scheduler) was stood up on a brand-new room/track in roughly an hour, with
zero code changes — only a new map, a new recorded lap, and one config line.
Three quantitative nuggets worth paper ink:

1. **Reference feasibility is a physics constraint, mechanically enforced.**
   The raw processed centerline had two spots at 0.73 m radius vs the car's
   0.74 m kinematic minimum (wheelbase 0.3302 m, max steer 0.4189 rad); a
   local curvature relaxation lifted the floor to 0.81 m while moving only
   8 points. Same lesson as the goat track's infeasible 0.41 m corner, now
   a tool invariant (`process_lap.py` refuses-with-warning). "Derive the
   requirement from the physics" applies to the *reference*, not just the
   timing.

2. **Staleness distance scales linearly with speed — and eats the corridor.**
   Sim N=12/1-core (925 ms max round trip, latest-only replacement):
   max|e| = 0.080 m @ 0.5 m/s, 0.212 m @ 1.0, 0.461 m @ 2.0 against a
   0.5 m taped corridor — in a NOISE-FREE kinematic sim. The margin the
   scheduler must protect is v·RTT-shaped; a clean age-criticality hook
   (tolerable age ∝ corridor/velocity) for the paper's HIL section.

3. **Sim-optimal ≠ live-optimal for lookahead.** The sweep at 1.0 m/s is
   monotonic (shorter L → lower sim error: 0.061 m @ 0.4 vs 0.204 m @ 1.4)
   because the sim has no sensor noise or actuation lag; live practice
   needs a 0.7–1.0 s horizon. Honest example of the model-fidelity gap the
   HIL work exists to expose.

**Also:** AMCL's distance-gated publishing produced 20 s sample droughts —
in live mode that's stale-command-until-wall; odom-triggered sampling
(50 ms min period, cached pose + fresh twist) is now mandatory. Real
sensing is *bursty*, not periodic — a modeling assumption the sim's uniform
20 ms sensor period hides.

**Where it lands.** GENERALIZATION (third instantiation: second *physical*
track), and the HIL section's setup + threats-to-validity.
