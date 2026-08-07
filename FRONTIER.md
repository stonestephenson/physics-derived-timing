# FRONTIER — scheduler capacity-limit study (branch: scheduler-frontier, throwaway)

## VERDICT (2026-07-28, complete)

**Frontier v12 beats the fairly-tuned incumbent by +2 on the safety frame and
+1 on the strict challenge frame, with ~5x better fleet health; the ceiling is
localized to [21, ~27] by the estimator-rate cap.** All numbers: worst exec,
3 cores, 120 s full lap, v10, default spread phasing, honest info set.

| gate | rm/edf | aguard-honest (best margin) | frontier-honest m100 |
|---|---|---|---|
| T1: 0 hard | 10 | 19 (m60-120 all break at 20) | **21** (19/20/21 clean; 22 fails by 25 frames) |
| T2: 0 hard AND soft<=5%/veh | 10 | 12 (13: 72 hard, 18.3% soft) | **13** (14 fails at 5.38%; 15 is a clean island) |
| health at own record | — | age 2470 ms, soft 55-70%, sim-crit 0 | age 430-1400 ms, soft 8-27%, sim-crit <=1 |

Robustness battery (pre-registered): pert x3 seeds + avg exec — both records
hold (frontier 21 clean, aguard 19 clean). align-offsets 0.5 — frontier holds
21 clean (one 21-frame pothole at N=19); aguard COLLAPSES at 21 (184k hard).
align-offsets 1.0 (fully stacked) — both fail at N>=19: occupancy = N exceeds
any 3-core scheduler; the honest degradation the route-map thesis predicts.
Held-out profiles v12.5/v15 — NEITHER scheduler's v10 record transfers (both
margins/zone windows are v10-tuned); capacity records are per-profile objects.

Ceiling: classical serve-everything = 10.5 (exact; RM breaks at 11).
E-decimation is catastrophic (filter breakage), so E is effectively full-rate
=> hard cap ~3/0.11 = 27 before B/M/F demand (~24 realistic). Achieved: 21.
The 21 -> ~24 gap is unresolved (the oracle receding-horizon packer was not
built; the empirical path outran it). aguard needs 4-5 cores for N=24-28.

Mechanism findings (the science, each machine-checked this session):
1. **F staleness is zone-critical.** Demoting F (44% of demand) on straights is
   the entire capacity win; F freshness in curved zones is load-bearing (F
   carries the reference; the reference moving is what defines a curve). The
   winning form: tiered F heartbeat (100 ms critical / 500 ms straight, z3
   undemoted) — v11's blanket protection and v9's blanket demotion both fail.
2. **Refresh-rate tolerance != delay tolerance.** E at 50 ms cadence with
   age_path 150 ms takes 10,781 hard frames where 196 ms of transport delay
   takes zero (EST_STEP filter breakage; k=2 knife-edge, k=3 catastrophic).
   Kills all E-cadence scheduler designs; yields the E-rate ceiling cap.
3. **B->M in-window sequencing** (reads sample at execution start): age floor
   80.5 ms — below the 90.5 ms recorded everywhere in the project's history.
4. **The 30 s window artifact:** the recorded aguard-honest marks (clean 21)
   do not survive the full lap (real record 19; z3 arcs live in the last ~23%
   of the lap). PORT TO PAPER_NOTES on paper-generalization — the poster's
   capacity claims inherit this.
5. **At the wall, protection-only allocation is the only feasible shape**:
   v1-v8 dominated aguard on every health column while breaching, because
   comfort/freshness spending steals exactly the PNR margin that gates.
Honesty scope: comparisons use the harness's established honest convention
(constant 16 ms pred-staleness + actuator-side age_recent_ms) for BOTH
schedulers; frontier's extra fields (zone_flagged, critical_remote) are
map/estimator-derived. remainingTicks is consumed only by the cull (a proven
no-op; disabled on pert rows).

Goal: the maximum fleet size N any scheduler can sustain under the Bosch
challenge rules on 3 cloud cores — then either decisively beat the incumbent
(aguard) or show it sits at the ceiling. New policy files + additive
registration only; no edits to FMU / TaskModel / Simulation / existing
policies. This file is the running record; it lives and dies with the branch.

## Targets (re-anchored 2026-07-28 after council + full-lap re-baselining)

The previously recorded marks (aguard-honest m80 "clean 21, breaks 22"; oracle
"clean 20") are **30 s-window artifacts**: all four v10 z3 lane-change arcs sit
in the last ~23% of the lap, and a 30 s run covers a quarter lap. Full-lap
(120 s) re-baseline, worst exec, 3 cores, default spread phasing:

| gate | rm | edf | aguard-honest m80 | notes |
|---|---|---|---|---|
| T1: 0 hard (safety frame) | 10 | — | **19** (20 collapses: 85k hard) | the frame the project's poster uses |
| T2: 0 hard AND all soft% <=5 (strict challenge) | 10 | — | **12** spread / 10 aligned | red-team council measurement; sits on the 10.5 utilization bound |

- T1 target: **N >= 20** clean at 120 s, honest info, robust to phasing — beat 19.
- T2 target: **N >= 13** under the strict gate — beat 12.
- "Blow out of the water" = +4 or more on T1 with the full column set clean.

## Council verdict (4 independent lenses, 2026-07-28) — what survived

1. Screen at 120 s always. 30 s runs are scouting only.
2. Report on EVERY row: hard (10 ms-decimated — matches the challenge monitor),
   per-zone hard, worst soft%, max_roll, missed jobs, sim-crit max, worst
   age_path. Never suppress the sim-crit banner.
3. Phasing is a confound (offsets = f(N)): dev on default spread; test at
   --align-offsets {0, 0.5, 1}. Profiles v12.5/v15 = held-out test.
4. The 40–90 "utilization ceiling" was wrong: it omitted F, treated the ZB-F-X
   envelope (a calibrated-sufficient point, run(1) = 190.5/133.5 ms with ~4 ms
   wobble tolerance) as a maximum, and assumed cadence-staleness ==
   delay-staleness (unvalidated; EST_STEP=0.01 hard-coded in the FMU estimator
   — skipping E changes the filter, not just the data). Ceiling instruments
   instead: (a) cores-axis N*(m) curve, (b) oracle receding-horizon packer
   (achievability), (c) skip-E decimation instrument (refresh-rate tolerance).
5. Envelope-enforcing designs lose: the incumbent passes T1 at ages 10–20x the
   envelope. Capacity at the wall = concentrating cores on the near-PNR car.
   The winning design keeps triage and fixes aguard's four measured defects:
   (i) per-vehicle key lets a rescued car's F block its own M on all 3 cores;
   (ii) kind tie-break runs F (25 ticks, no sensor data) before M (5 ticks,
   closes the loop); (iii) zero anti-waste: jobs are started that provably
   cannot finish before their kill (release), and near-done jobs get no
   preference; (iv) guard theta saturates at the 450 clamp past N~12,
   degenerating to pure ttu.
6. F economics (measured this session): bounded F staleness is nearly free on a
   clean car (40 ms..1000 ms extra F staleness at N=1/120 s: 0 hard, +6 soft
   frames, saturating). The known F damage channel is *indefinite* starvation
   (frozen reference through curves). Design: guaranteed F heartbeat
   (~0.5–1 s = 0.003–0.005 cores/car), fresher near a car's budget edge.
7. Honesty contract: the harness "honest" info set is itself generous —
   --pred-staleness is a CONSTANT 16 ms of ground-truth state regardless of the
   car's actual delivered age (matched staleness turns aguard-honest N=16 from
   clean into 44k hard), and age_recent_ms is measured at the ACTUATOR with a
   zero-delay backchannel. Scoped as: comparisons vs the incumbent use the
   incumbent's own convention (internally fair); the strongest-honesty variant
   uses only route knowledge + own-publish bookkeeping + worst-case constants
   (no pred fields, no age_recent_ms) and dodges both leaks. State this in any
   writeup. remainingTicks is deterministic under worst/avg (legit); under pert
   it is oracular — pert rows for any policy reading it must be labeled.
8. P1 (missed=0) is NOT required for empirical capacity claims (the incumbent
   drops ~50% of jobs at its record) but the missed column is reported and any
   formal-bound narrative is out of scope for numbers with missed>0.

## Candidate set (post-council)

- I1 "eskip" (instrument, first): RM + per-vehicle E decimation via env knob.
  Settles cadence-vs-delay at matched age (crux for any cadence element).
- S1 "triage+" (the contender): aguard-shaped two-tier triage with the four
  defect fixes + F heartbeat + anti-waste. Honest fields per the incumbent's
  convention; a no-prediction variant (route + bookkeeping only) if time allows.
- I2 planner (oracle ceiling instrument): receding-horizon burst packer, full
  knowledge; not a contest entry.
- C4 tuning control arm: DONE at 30 s (no cell clean at N>=22); m-grid at 120 s
  running (fair best-incumbent).
- Dropped: envelope-enforcing age-EDF as primary (council consensus), offline
  calendar as contender (answer key; may return as an instrument).

## Protocol (pre-registered)

- Dev: v10, spread offsets, 120 s, worst exec, 3 cores. All tuning here.
- Test (incumbent and challenger, equal budgets): align-offsets {0,0.5,1} x
  profiles {10,12.5,15} x pert 5 seeds x avg exec. Report full column set.
- Verdict = sandwich: best honest challenger <= oracle planner <= (conditional)
  arithmetic; plus the N*(m) cores curve. Gap analysis per term.

## Log

- 2026-07-28: branch created; localize (3 Explore agents) + council (4 lenses);
  30 s marks falsified (aguard-honest m80 full-lap = 19; strict gate = 12);
  C4 30 s grid: no tuning cell clean at N>=22; F-staleness probe: bounded F
  holds are ~free at N=1; ff-extra-ms knob verified live (1000 ms sanity).
  **[ERRATUM 2026-08-07: the previous line over-reads a clamped instrument —
  ffExtra caps at one F period (~20 ms, TaskModel.cpp:317), so every dose
  40–1000 ms administered ~20 ms. Only "~20 ms costs +6 soft frames" was
  established. See FCHANNEL.md §3.]**
- 2026-07-28 (b): incumbent fair-tuning at 120 s — margins {60,80,100,120} all
  break at N=20; the honest full-lap record is 19, margin-robust.
- 2026-07-28 (c): eskip crux VERDICT — cadence-staleness is NOT delay-staleness.
  E at 50 ms cadence, N=1, age_path 150.5 ms (safe by >=100 ms per every delay
  table): 10,781 hard frames, breaching even z0. E at 110/200 ms: worse. The
  EST_STEP filter-breakage prediction confirmed; every E-starving cadence
  design is dead. Boundary probe: k=2 (20 ms) clean (soft 10x baseline),
  k=3 (30 ms) catastrophic — E tolerates exactly one skipped release.
  Consequences: (i) refresh-rate tolerance tables cannot be borrowed from
  A(zone)/envelope delay tables; (ii) E-demand alone caps the fleet at
  3/0.11 ~= 27 (full-rate E) or 3/0.055 ~= 54 (knife-edge k=2 E), before B/M/F
  demand — the practical ceiling estimate tightens to roughly [19, 27].
- 2026-07-28 (d): frontier v1 built (chain-head serialization + F
  demotion/heartbeat + finish-line + hopeless-cull on aguard's unchanged tier
  logic; Frontier.cpp) + eskip instrument (EskipProbe.cpp). verify.sh green.
  CHAIN-SEQUENCING LEVER CONFIRMED: reads are at execution start, so B->M in
  sequence beats B||M in parallel — frontier N=1 age floor 80.5 ms (vs 90.5
  everywhere in the project's history); N=6 path age 90.5 vs RM golden 100.5,
  0 missed both. Fleet-wide ~10-20 ms freshness gain from ordering alone.
- 2026-07-28 (e): v2-v8 iteration arc (git log) — every structural theory
  (kill-guard, zombie-offer fix, zone tier, thin guard, reserved slot, error
  ties, E-alongside) failed at N=19 with z3-centered breaches. Per-vehicle
  diagnosis: frontier BEAT aguard on every health column (age 430 vs 2470,
  soft 12-27% vs 55-70%, avg_perf 4x better) yet 15/19 cars touched
  PNR-margin 0. Lesson: at 181% overload the feasible allocation is
  protection-only; comfort/freshness spending steals the gating margin.
- 2026-07-28 (f): v9 ablation with a byte-identical aguard anchor (validated:
  both toggles off == aguard exactly). Attribution: hopeless-cull is a NO-OP
  (doomed jobs never won cores); F-DEMOTION alone is both the entire capacity
  win AND the entire z3 breach cluster — F carries the reference; the lane
  change is where the reference moves; 500 ms-stale F there steers at the old
  lane line. Stale-F is zone-critical, free on straights (consistent with the
  ff-extra probe AND the S8.7 damage channel — both were right, in different
  zones).
- 2026-07-28 (g): v10 = zone-aware F demotion (flagged cars' F keeps full
  aguard priority): N=19 CLEAN with 5x better health than the incumbent;
  breach epicenter moved z3 -> z1/z2 (curved reference, same mechanism,
  milder). FHB=200 ms probe: N=21 CLEAN (past the incumbent!), N=20 pothole
  (17 z2 frames).
- 2026-07-28 (h): v11 (blanket critical-section F protection) REGRESSED —
  critical sections cover so much lap that the F giveback starved the fleet
  (z2 hard 2505 at N=20, ages doubled). Lesson: curved zones want BOUNDED F
  staleness, not full-rate F.
- 2026-07-28 (i): v12 = tiered F heartbeat (crit 100 ms / straight 500 ms,
  z3-flagged F undemoted). Margin grid at 120 s: **m=100 is CLEAN at N=19,
  20, AND 21** — first failure N=22 (25 z1 frames). The fairly-tuned
  incumbent (margins 60-120 all break at 20) holds 19. Frontier full-lap
  record: **21 (+2)**, with fleet health ~5x better at every N (soft ~1/5,
  ages 430-1400 vs 2470+, sim-crit <=1). N=20's failure at m80 was a single
  car's single 215 ms past-PNR excursion (8 frames) — margin-closable, and
  closed by m=100 without breaking 19 or 21.
