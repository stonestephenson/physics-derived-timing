# Session Handoff — CPS Challenge Visualizer

Resume point for a fresh agent. Last updated **2026-06-22**.

**Read order:** `CLAUDE.md` (stable bootstrap: invariants, reading map, rules) →
this file (what's true *now*) → the owning design docs as your task needs them
(`DATA_AGE.md`, `BOUND.md`, `PREDICTOR.md`, `ZONE_TOLERANCE.md`, `USAGE.md`).
Rule of thumb: change how the project *works* → update `CLAUDE.md`; change what
is *true right now* → update this file; change a convention/result → update the
owning design doc **in the same commit as the code**.

---

## 1. What this project is

REU research (Dr. Guo's lab) responding to the Bosch RTAS 2026 Physics-Driven
CPS Challenge. N simulated vehicles share `N_c=3` cloud cores for their control
chains; we control *who computes when*. We built, in layers:

1. **Data-age measurement** — how stale the applied steering command's sensor
   data is (`DATA_AGE.md`). Two conventions: `age_fresh` (newest contributing
   sample) and `age_path` (classical S→E→B→M→A chain age — **what the bound
   targets**).
2. **Analytical bound** (`BOUND.md`, **v0.1, UNVERIFIED**) — a ceiling on
   `age_path`, plus a draft tick-quantum global-FP response-time analysis (§7).
3. **Predictor** (`PREDICTOR.md`) — a verbatim port of the FMU plant that
   fast-forwards each car to compute **TTV** (time until |e_y| crosses the
   0.8 m hard bound under the held command) and **TTPNR** (time until recovery
   becomes impossible — the physical deadline). Fidelity-gated.
4. **Schedulers** — a lineage from classical to predictive (table below).
5. **Visualizer** — dotted predicted path, 0.8 m-crossing ring, point-of-no-
   return diamond, rescue trajectory; live + replay.

### Plan of record (the strategic frame — read before doing anything)
*Updated after the 2026-06-18 Dr. Guo meeting.* Our work is **evidence for a
general thesis, not a Bosch-specific solution**: *timing requirements should be
derived from the physics (the max tolerable data age, per context), and doing so
exposes and safely exploits beyond-worst-case slack.* Bosch is case study #1.
- **Target: main track** (RTAS/RTSS '27), not the fall workshop. Bar = theorem
  + honest information + **generality** + verified bound + SOTA comparison.
- **Generality is first-class and underway:** a second plant (cart-pole) now
  runs the *same* scheduler / data-age / bound machinery — see §2. Don't add
  schedulers; generalize / prove / document / write.
- **Document with the paper in mind** (Guo's directive): findings →
  `PAPER_NOTES.md`; results reproducible (`tools/*.py`, committed CSVs).
- **Kurt/Guo own the bar.** The θ-from-age-bound theorem is the one leg neither
  the user (novice at proofs) nor the AI agent can own — Kurt or a proof assistant.
- Ownership now: **user + AI agent** drive build / experiments / docs; Kurt the
  formal leg. (The old "Route A workshop / freeze policies" frame is superseded.)

Team: user (lead) + CS student (sweeps, RTA fixed-point solver, infra) + EE
student (zone tolerance, control side) + Kurt Wilson (PhD mentor; spot-checks
formal claims; first author of the MEMOCODE'24 paper Route B extends).

## 2. Current state

- **Active branch `paper-generalization`** (off `main`, pushed to **`tempbosch`**:
  `github.com/stonestephenson/tempboschchall`). `main` holds through the RTA
  solver (`4f49f46`); the cart-pole generalization (Plant seam + second plant +
  Phase-3 evidence, 4 commits) lives on the branch. **Push only to `tempbosch`.
  NEVER push to `origin`** (the Bosch upstream). `relatedPapers/` untracked.
- Working tree clean after this handoff commit.
- Builds clean: `cmake --build build -j`. Fidelity gate passes
  (1.49e-08 m, all 3 profiles). All policy baselines reproduce.

### Generalization — `Plant` seam + cart-pole (2026-06-18, on the branch)
The FMU is now one implementation of a `Plant` interface (`src/sim/Plant.h`); the
scheduler, data-age model, bound, and `rta_solve.py` are plant-agnostic. A second
plant — an inverted pendulum (`--plant cartpole`, `src/sim/CartPolePlant.{h,cpp}`:
dynamics + the trigger-driven chain + a validated physics-derived predictor) —
runs the same machinery; the Phase-1 refactor preserved every Bosch baseline.
Headline results (`PAPER_NOTES.md`, `tools/tolerance_sweep.py`):
- **Age-tolerance is physics-derived & plant-dependent:** car ~245 ms (gradual)
  vs cart-pole ~110 ms (sharp ~5 ms cliff). Same chain, same delivered age per
  delay; only the physics differs.
- **Age-criticality scheduling generalizes:** aguard carries ~14 cart-poles
  crash-free vs RM's ~11 (N=16: 1 vs 9 crashed).
- The two plants bind on *different legs*: car on scheduling (overrun ~N=11),
  cart-pole on physics (age-tolerance ~110 ms).
- *Caveat:* cart-pole params (shoveForce/u_max/θ_max) are first-pass, not yet
  calibrated like the car's δ_max — qualitative contrast solid, exact numbers TBD.

### Policy lineage (`--scheduler NAME`)
| name | rule | role |
|---|---|---|
| `rm` | rate-monotonic (shorter period first) | Challenge Q1 baseline |
| `prm` | partitioned RM (`vehicle % nCores`, no migration) | global-vs-partitioned |
| `edf` | earliest absolute deadline | baseline |
| `context` | rank by current tracking error | **reactive**; reads `*_real` ⇒ ORACLE |
| `honest` | same rule, estimator-derived remote metrics only | legitimate context |
| `ttu` | rank by TTPNR (physical deadline) | **predictive**; the safe core |
| `hybrid` | TTPNR<`--guard` ⇒ emergency tier (ttu rule); else comfort tier (context rule) | fixed guarded triage |
| `aguard` | hybrid with self-tuning guard θ=`--floor`+live round-trip | adaptive guarded triage |

Mental model: emergency tier = ttu; comfort tier = context; the **guard** is
the TTPNR line dividing them. `context` = guard 0, `ttu` = guard ∞, `hybrid` =
fixed guard, `aguard` = guard that tunes itself.

### Headline results (worst exec, kill-and-hold, 3 cores, 30 s unless noted)
- N=1: `age_path` 90.5 ms ≤ bound 120.8 (uncontended) / 216.6 (degenerate).
- N=6 RM: 90.5/100.5 ms (fresh/path), 0 missed, veh 3 = 0.507 avg / 13.4% soft.
- **Capacity:** classic policies die at N≈10–12 (RM@12: 4519 hard breaches, 2
  vehicles never actuate). `ttu` zero hard breaches through N≥14 but ~75% soft.
  `context` survives N=14 at **zero** PNR margin, collapses at N=16. **`aguard`
  carries 18 vehicles, zero hard, ~220 ms fleet floor — 50% past the classics.**
- Prediction overhead **+17% wall** at 12 veh (13×→11× real-time).
- **RTA (BOUND §7) machine-verified** (`tools/rta_solve.py`, cross-checked sound
  vs sim): RM/worst certified capacity **5** (full carry-in) vs empirical **10**
  — a 2× gap that is full-carry-in pessimism, so the limited-carry-in
  re-derivation (§7.4 item 2) is the critical path. The solver corrected §7.3's
  wrong v5 R's (107/129/117 → 117/203/152) and the false "P1 certified at N=6".
- **Simultaneous criticality (`--tau-crit`, §5 item 0 / PREDICTOR §5d):** at
  τ_crit=100 ms, TTPNR-blind RM puts **7 (N=14) / 12 (N=18)** loops within
  reaction-time of PNR at once (≫ 3 cores); ttu/aguard hold it to **0** at all N
  (worst car ≥115 ms from PNR, zero hard). The empirical (A)-shadow — but
  sim-crit=0 ≠ well-controlled (aguard N=18 holds 0 on 26 s-stale data). Cart-pole
  differs: aguard N=16 max 10.

## 3. Key facts — do NOT re-derive or violate these

- **Measurement is harness-side** (`TaskModel.cpp::endTick`). The FMU carries no
  timestamps; age is bookkeeping shadowing its data routing. The FMU is a
  prebuilt black box — never edit/recompile it (CLAUDE.md invariant 6).
- **Formal/soundness runs use `--exec worst` and require `missed jobs: 0`**
  (precondition P1). `--exec pert` reorders network deliveries vs the stamps —
  excluded from bound work.
- **`age_path` is the bound's target**; `age_fresh` is reaction latency;
  `age_fresh ≤ age_path` always.
- **Flat cross-vehicle ready pool**: `CorePolicy::assign` gets the pool + a core
  *count* (no core identity). Partitioning lives *inside* `assign()` (see `prm`).
- **Fixed-priority tie order is the strict total order (period, vehicle, kind)**
  — deterministic across STLs, exactly the model `BOUND.md §7` analyzes.
  Vehicle-major matches the Q1 exemplar; stage-major (kind-first) starves the
  whole Merger class under overload (`BOUND.md §7.1`).
- **`context` is an ORACLE** (reads ground-truth `*_real`); `honest` is the
  legitimate variant (estimator-derived). All predictive policies (ttu/hybrid/
  aguard) likewise read ground-truth state today — see Finding C.
- **Predictor:** verbatim FMU port (`Predictor.cpp` matrices = `LateralMotion
  Control.c:793-880`). The steering limit (δ_max) exists **only in the
  predictor** (the FMU's steering is amplitude-unbounded), calibrated ×1.5 of
  observed max |act_out|: 0.285/0.534/0.419 rad (v10/12.5/15). The recovery /
  PNR is a **bang-bang heuristic with a monotonicity assumption — not certified
  reachability.**
- **Re-run `--validate-predictor` after ANY predictor change** (must stay
  ~1.49e-08 m). Recording format is v4 (loads v2/v3).
- **`ContextAware`, `Hybrid`, `AdaptiveGuard` share `comfortUrgency*` helpers
  in `Policies.h`** — keep it that way so A/Bs isolate the mechanism, not a
  copy-paste drift.

## 4. Open findings from this session — discussed, NOT yet in code/docs

These three came out of analysis this session and are the most immediate
pickup work. Each has a concrete remedy.

**A. `--floor` on `aguard` is currently inert (a real bug-shaped gap).**
Sweeps (this session) show floor 0→300 produce **byte-identical** results at
N=11, 12, and 14; only floor=400/N=14 differs, non-monotonically. Cause:
θ = min(450, floor + max(60, **fleet-max** `age_recent_ms`)); under load one
starved car pins the fleet-max high, slamming θ into the 450 clamp regardless
of floor (compounded by TTPNR being near-bimodal under overload). So aguard's
headline tunable knob has almost no authority right now.
*Fix:* make θ **per-vehicle** — `θ_v = min(450, floor + max(60, age_recent_ms[v]))`
(the per-vehicle age already flows through `VehicleView.age_recent_ms`; ~2-line
change in `AdaptiveGuard.cpp`), then re-sweep floor to confirm it comes alive.
*Doc:* `PREDICTOR.md §5c` presents aguard without noting this — correct it.
(Note: the *fixed* hybrid guard IS a real dial — `§5b` is correct; only the
adaptive coupling swallows the knob.)
**RESOLVED 2026-06-22 (commit `3214880`):** θ is now per-vehicle
(`AdaptiveGuard.cpp`), so `--floor` is a live knob (floor 0→300: byte-identical →
distinct schedules at N=14). *Caveat — re-baselines aguard:* the pre-fix headline
numbers (`PREDICTOR.md §5c` table) were produced by the inert ~max-guard θ and
need a proper multi-N `--floor` sweep to re-derive (single runs are
load-dependent / non-monotonic). Default `--floor` kept at 100 (provisional).

**B. Prediction compute cost is never measured or charged — only assumed.**
The predictor runs in zero sim-time, is not charged to the 3 cores, and uses
a 10 ms refresh; we only have the aggregate "+17% wall" (wrong denominator —
the FMU sim is "free" in reality). Indirect arithmetic suggests **~10 µs per
prediction** (sub-core for the whole fleet, ~800× headroom vs the 10 ms
refresh) ⇒ the method *is* computationally realistic — but we haven't shown
it. *Fixes, all cheap:* (1) time `predictHold` directly and report µs +
%-of-a-core; (2) state the "scheduler runs on separate orchestration
infrastructure, not the N_c worker cores" assumption in `PREDICTOR.md`
(justified by the challenge's "dedicated cloud scheduler" framing); (3)
optionally model a prediction latency δ_pred and show results are insensitive.
*Note:* compute speed is NOT the binding realism constraint — input freshness
(the oracle problem, Finding C) is.

**C. Fairness-under-overload finding (publishable, not yet written down).**
Under overload `ttu` produces an **ID-locked starvation caste**: at N=14/30 s,
cars 0–6 get fresh data (~100 ms age, ~3% soft) while 7–13 are starved (age up
to 8320 ms, 40–77% soft). Proven to be the static vehicle-ID tie-break, not
geography: over a full lap (120 s, geography averaged out) the contiguous split
**persists**; with 6 cores it **dissolves**. `aguard`'s comfort tier (error-
ranked = max-min "serve worst-off") equalizes the fleet (~25% across all). This
is the classic EDF-overload unfairness/domino effect, and graceful degradation
via the two-tier structure is the known fix — a crisp result for the paper.
*Action:* add a "fairness under overload" paragraph to `PREDICTOR.md §5c`,
backed by the runs in this finding. Reproduce: `ttu` at N=14 30 s vs 120 s vs
`--cores 6`, and `aguard` N=14.

### Review triage (2026-06-22, ultrareview cloud review of the branch)
The ultrareview surfaced 3 findings:
- **#3 — fidelity gate ran the lateral predictor for cart-pole** (false FAIL):
  FIXED (commit `f4f1699`) — routed through the `Plant` seam and skipped for
  non-lateral plants (the gate is FMU-port-specific). Lateral stays 1.490e-08 m.
- **#2 / Finding A — aguard `--floor` inert:** FIXED (commit `3214880`, above).
- **#1 — visualizer replay bypasses the `Plant` seam** (a cart-pole `.cpsr`
  renders lateral dynamics + hardcoded 0.8/0.2 m bounds): **OPEN, low-priority
  nit** — viz-only, cart-pole is headless-documented. Fix = guard the overlay for
  non-lateral replays, or bump the recording format (v4→v5: store PlantKind+bounds).
- **Follow-ups:** (a) proper multi-N `--floor` sweep to re-derive aguard's
  post-fix headline (supports §5 item 4); (b) **verify the `Li et al. RTSS'24`
  citation** in `BOUND.md §5` — flagged unconfirmed by the 2026-06-22 survey;
  chase before any submission (Kurt / formal leg).

## 5. Prioritized next steps

Reframed (post-Guo 2026-06-18) around the main-track generalization paper:

**Existential gate — DONE (survey complete 2026-06-22; full map + citations:
`PAPER_NOTES.md` 2026-06-22).** Outcome: the thesis isn't novel (Wilson F1Tenth
RTAS'25 + MEMOCODE'24 own "derive timing from physics"); **(B)** age-tolerance
~1/λ is **established prior** (Sudvarg RTAS'25 *proves* it via CBF+SOS; AoI-control
[Etcibasi'26: cost ~`E[a^{2Δ}]`] + MATI/delay-margin restate it) → demote to
background; **(C)** folds into (A); **(A)** is the **only surviving leg** — *bound
from the physics how many of N loops are simultaneously within reaction-time of
their PNR (≤ k), compose with a multicore RTA ⇒ m cores keep all N safe, admitting
more loops than an "all-critical-at-once" test.* **Must-cite that was MISSING from
`relatedPapers/`: Sudvarg–Clark–Gill, "Integrated Real-Time Control and Scheduling
for Safety-Critical CPS," RTAS 2025** (multi-loop + CBF safe-set safety +
physics-derived period × multiprocessor schedulability — but NO cross-loop
simultaneity bound, NO PNR/recoverability notion). Also Kundu–Quevedo'19 (N
open-loop-unstable plants on M<N channels, keep all *stable* by optimal rotation —
no simultaneity bound). 5 must-cite PDFs now in `relatedPapers/`. **Make-or-break
for Kurt:** (1) does Sudvarg §IV (pp.316–322, unread) already bound cross-loop
simultaneity? (2) does our bound admit fleets that K–Q-style *optimal* rotation
cannot — or is rotation already enough?

**Reprioritized around (A):** the (A)-serving core is now the **formal leg (item 2
— prove the simultaneity bound)** + **honest predictor (item 3 — credibility)** +
task (0) below (**DONE 2026-06-22** — the empirical instrument). Cart-pole calibration (item 1) and generality breadth
(item 4) support the *generality* leg (meaningful, not novel) and drop below these.

0. **Measure simultaneous criticality — DONE 2026-06-22 (`--tau-crit`; PREDICTOR §5d).**
   Per-base-tick count of vehicles with `ttpnr_ms < τ_crit` (τ_crit ≈ one command
   round-trip; `--tau-crit MS`, default 100); reports run-max + dwell-histogram
   (summary line + CSV cols `tau_crit_ms,max_sim_crit,sim_crit_over_cores_pct`) and
   a loud flag when max > cores. Measurement-only (baselines byte-identical, gate
   1.490e-08 m). **Result (car, worst, 3 cores, 30 s, τ=100):** TTPNR-blind RM lets
   **7 (N=14) / 12 (N=18)** loops within 100 ms of PNR at once (≫ 3 cores); **ttu &
   aguard hold it to 0 at all N** (worst car ≥115 ms aguard N=18 / ≥185 ms ttu N=14,
   zero hard) ⇒ 3 cores keep the fleet out of the critical zone; fails to refute (A)
   for the predictive policies. **Caveat:** sim-crit=0 ≠ fine — aguard N=18 holds 0
   while feeding 26 s-stale data + 43–55 % soft viol; the metric is distance-to-PNR
   simultaneity, not control quality (margin thin: τ=150 → 1 critical). **Cart-pole
   differs (different leg):** aguard N=16 max 10 (>cores 0.79 %), N=8 max 2 — sharp
   physics, more loops critical at once (params uncalibrated). Full writeup
   `PREDICTOR.md §5d` + `PAPER_NOTES.md` 2026-06-22.
   *Still contingent on (A) surviving Kurt — the sim is its shadow, not the proof.*

1. **Cart-pole → paper-grade:** calibrate its params (shoveForce/u_max/θ_max,
   ×1.5-style like the car's δ_max) so the headline numbers are publishable; a
   "reproduce-all-figures" orchestrator; optionally a 3rd plant.
2. **Kurt — the formal leg** (neither user nor AI can own it): verify `BOUND.md`
   + re-derive the §7.2 workload bound (full carry-in is 2× pessimistic,
   certified 5 vs empirical 10; limited carry-in m−1 — `tools/rta_solve.py`
   ready), and the theorem `floor ≥ θ − age_bound` ⇒ no crossing.
3. **Honest predictor** (biggest credibility gap): predict from estimated state +
   last-sent command (InfoSet pattern, `ContextAware.cpp`). Every predictive
   policy reads ground truth today. **Verified 2026-06-22 (read-only):** TTPNR/TTV
   are seeded from the true plant state (`predictHeld(o,…)`, `Simulation.cpp:115`,
   `o = readOutputs()`), so ttu/hybrid/aguard all rank on an oracle; aguard's
   comfort tier also uses `comfortUrgencyOracle`. The estimated-info plumbing
   already exists for *context* metrics (`comfortUrgencyRemote`,
   `makeContextAwareHonestPolicy`, `e_y_est`/`*_remote` in `VehicleView`) — the
   task is to extend that pattern to an estimated-state *prediction* (no
   `ttpnr_est` today) + a safety margin.
4. **Generality breadth:** parameter sweeps (speed/δ_max/net-delay/WCET/cores) on
   *both* plants; the car's zone-tolerance A(zone) (`ZONE_TOLERANCE.md`).
5. **Close Findings A & B** (per-vehicle θ; prediction-cost instrumentation).
6. Lower priority: clearance-ablation, triage A/B under overload, network-side
   scheduling, Q6 event-triggered.

## 6. Run / verify

```sh
cmake --build build -j
./build/cps --headless --vehicles 14 --scheduler aguard --exec worst --duration 30
# the tournament (read hard / worst soft% / min_pnr per row):
for s in rm context ttu aguard; do ./build/cps --headless --vehicles 14 --scheduler $s --exec worst --duration 30; done
./build/cps --headless --vehicles 1 --scheduler rm --exec worst --duration 120 --validate-predictor  # trust anchor
./build/cps --headless --vehicles 14 --scheduler ttu --exec worst --duration 60 --save ttu14.cpsr
./build/cps --replay ttu14.cpsr --speed 16     # press ] to cycle cars; watch the error strip
```
Flags: `--scheduler rm|prm|edf|context|honest|ttu|hybrid|aguard`, `--vehicles
N`, `--cores N`, `--profile 10|12.5|15`, `--duration SEC`, `--exec
avg|worst|best|pert`, `--overrun kill|skip`, `--guard MS` (hybrid), `--floor MS`
(aguard), `--tau-crit MS` (sim-criticality, §5 item 0 / PREDICTOR §5d), `--triage`, `--delta-max RAD`, `--net-delay MS`, `--validate-predictor`,
`--csv FILE`, `--save/--replay FILE`, `--select N`, `--speed X`, `--screenshot[-at]`.

## 7. Key files
- `CLAUDE.md` — agent bootstrap (invariants, reading map).
- `DATA_AGE.md` — age metric + conventions (§4d = dual conventions).
- `BOUND.md` — analytical bound v0.1 + RTA (§7, machine-verified); review flags inline.
- `PAPER_NOTES.md` — running log of paper-worthy findings (cert gap, phasing, hold-free).
- `PREDICTOR.md` — TTV/TTPNR, policies, fidelity gate, sweeps (§5–5c).
- `ZONE_TOLERANCE.md` — EE experiment spec.
- `src/sim/Plant.h` — plant-agnostic seam; `LateralPlant.{h,cpp}` (FMU wrapper),
  `CartPolePlant.{h,cpp}` (inverted-pendulum 2nd plant: dynamics + chain + predictor).
- `src/sim/Predictor.{h,cpp}` — car plant port, rollouts, warm-started PNR search.
- `src/sim/Simulation.cpp` — plant-generic loop; `refreshPredictions`, `buildViews`.
- `src/sched/TaskModel.cpp` — `endTick` (stamps, age), `releaseIfDue` (overrun);
  `recentLatchAgeTicks` (the live round-trip signal).
- `src/sched/policies/` — one .cpp per policy; `Policies.h` has shared helpers.
- `src/viz/Visualizer.cpp` — `drawPrediction` (overlay, live + replay).
- `tools/rta_solve.py` — RTA solver + capacity sweep + sim cross-check (machine-verifies §7).
- `tools/tolerance_sweep.py` — per-plant age-tolerance sweep (car vs cart-pole).
- `*_sweep.csv` — committed sweep data behind the result tables.

## 8. Lessons learned / best practices (this codebase)

- **The simulator is the adversary — verify, never assume.** This project has
  twice caught a plausible claim being false by *running* it: the hold-free
  bound that survived N=1 by 0.3 ms of slack-cancellation, and the `--floor`
  knob that looked like a dial but was byte-identically inert. Any claim that
  ends in a number must be reproduced by a run. "Looks right" is not evidence.
- **Mind the denominator.** "+17% wall" looked alarming until you notice the
  FMU sim (the denominator) is free in reality; against a CPU core the cost is
  ~0.1%/vehicle. Always ask what a number is *relative to*.
- **Single-source any rule two policies share** (`comfortUrgency*`), so an A/B
  measures the mechanism, not an accidental divergence.
- **Determinism is a feature:** strict total-order tie-breaks (no `std::sort`
  nondeterminism) → reproducible across platforms AND matches the analyzed
  model. Changing a tie-break re-baselines everything — re-run and update docs
  in the same commit.
- **When you port/duplicate a model, build an exact-match gate** and re-run it
  after every change (`--validate-predictor`). It catches coefficient typos
  the eye never will.
- **Version serialized formats with back-compat loaders** (recording v2→v3→v4);
  old runs must still replay.
- **Keep the hot path fast but keep an exact path for the gate:** rollouts use
  a velocity-quantized matrix cache + coarse 10-tick affine stepping +
  warm-started search; `--validate-predictor` runs the exact tick-by-tick model.
- **Docs are load-bearing and go stale silently.** When a finding invalidates a
  documented claim (e.g. Finding A vs `PREDICTOR.md §5c`), fix the doc in the
  same change — a fresh agent will otherwise trust the stale claim.
- **Honesty over polish in the writeup-facing docs.** The negative results
  (hold-free bound, inert floor, oracle dependence) are recorded deliberately;
  they're what makes the eventual paper credible. Don't bury them.
