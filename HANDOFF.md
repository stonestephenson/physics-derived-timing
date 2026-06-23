# Session Handoff — CPS Challenge Visualizer

Resume point for a fresh agent. Last updated **2026-06-23**.

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
- Builds clean: `cmake --build build -j`. Fidelity gate passes — `max |dev| =
  1.490e-08 m` on the trust anchor (`--vehicles 1 rm --exec worst --duration 120
  --validate-predictor`); the value **scales with lap coverage**, so use that exact
  command (a shorter run reads smaller — e.g. ~3.7e-09 m at 30 s — still PASS).
  All 3 profiles PASS; all policy baselines reproduce.
- **Reproducibility (Guo's directive) — `tools/reproduce.py` (2026-06-23).** One
  command regenerates every scheduling results CSV + prints the table:
  `capacity` / `simcrit` / `honest` / `floor` (§5c) / `tolerance`, all `--exec worst`.
  Committed CSVs: `capacity_sweep.csv`, `simcrit_sweep.csv`, `honest_sweep.csv`,
  `aguard_sweep.csv`, `tolerance_sweep.csv` (self-describing: plant/floor/staleness/
  margin columns the sim's own `--csv` omits). The reconciliation re-derived §5c
  (Finding-A floor table, was stale) and confirmed §5 / §5d / §5e / cart-pole
  capacity all reproduce. (§5b hybrid/frontier CSVs are regenerable via the same
  framework but were left as-is; BOUND RTA stays `tools/rta_solve.py`.)

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
- **Age-criticality scheduling generalizes:** aguard carries **17** cart-poles
  crash-free vs RM's **10** (N=16: 0 vs 9 crashed; 20 s worst).
- The two plants bind on *different legs*: car on scheduling (overrun ~N=11),
  cart-pole on physics (age-tolerance ~110 ms).
- **Calibrated 2026-06-23** (was first-pass): cart-pole params derived by the car's
  δ_max method — uMax = 1.5 × observed demand (7.70 N → **11.55 N**); thetaHard/Soft
  (0.21/0.05) kept as the given safety spec; shove 8 N (≤ authority). The tolerance
  cliff is **invariant** to it (physics-set); the 17-crash-free lift is the floor fix
  `3214880`, not the calibration (GENERALIZATION §4 / PAPER_NOTES 2026-06-23).

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

Each predictive policy has an **`-honest`** twin (`ttu-honest`/`hybrid-honest`/
`aguard-honest`) that ranks on a rollout from the cloud's *delayed* state
(`--pred-staleness`, +`--pred-margin`) instead of true state — the oracle-vs-honest
A/B (§5 item 3 / PREDICTOR §5e).

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
- Prediction compute **~10–17 µs/rollout, ≤4% of one core** (car, through N=18 +
  honest); the old "+17% wall" was vs the free FMU sim (wrong denominator). §5f.
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
  differs: aguard N=16 max 10 (but over cores only 0.18% of the run).

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
  legitimate variant (estimator-derived). The predictive policies (ttu/hybrid/
  aguard) read ground-truth state by default, but each now has an `-honest` twin
  that predicts from delayed state (§5 item 3 / PREDICTOR §5e); the oracle ones
  are kept as the upper-bound A/B reference.
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
distinct schedules at N=14). **Re-derived 2026-06-23:** the proper multi-N `--floor`
sweep is done (`tools/reproduce.py floor` → `aguard_sweep.csv`; `PREDICTOR.md §5c`
table updated) — `--floor` is a confirmed live knob (at N=18 the achieved floor
tracks it ~1:1). Default `--floor` **settled at 100** (≈115 ms floor at N=18, ≡
context at light load).

**B. Prediction compute cost — RESOLVED 2026-06-23 (measured; `Simulation.cpp`).**
`predictHeld` rollouts are now timed and reported per run (`prediction compute:
us/prediction, %-of-one-core`). **Car (optimized matrix-cache predictor): ~10–17
µs/prediction; ≤ 3.0 % of one core at N=18, 4.0 % for the honest variant (both
rollouts).** Decisively negligible against the 3 worker cores — *measured*, not the
old "+17 % wall (wrong denominator)" (that was wall slowdown vs the free FMU sim;
against a CPU core it's ~0.1 %/vehicle). **Caveat:** the **cart-pole** predictor is
a naive 1 ms RK4 rollout (no cache) — **344 µs/prediction, 27 % of one core at
N=8** — ~30× heavier (fine for the demo, not paper-grade). Doc: `PREDICTOR.md §5f`.
Assumption stated there: the dedicated cloud scheduler runs on separate
orchestration infra, not the N_c worker cores. Input freshness (Finding C / honest
predictor §5e), not compute, is the binding realism constraint.

**C. Fairness-under-overload finding (publishable, not yet written down).**
Under overload `ttu` produces an **ID-locked starvation caste**: at N=14/30 s,
cars 0–6 get fresh data (~100 ms age, ~3% soft) while 7–13 are starved (age up
to 8320 ms, 40–77% soft). Proven to be the static vehicle-ID tie-break, not
geography: over a full lap (120 s, geography averaged out) the contiguous split
**persists**; with 6 cores it **dissolves**. `aguard`'s comfort tier (error-
ranked = max-min "serve worst-off") equalizes the fleet (~25% across all). This
is the classic EDF-overload unfairness/domino effect, and graceful degradation
via the two-tier structure is the known fix — a crisp result for the paper.
*Status (2026-06-23): DE-SCOPED from the doc set* — kept here as a recorded
finding, deliberately NOT integrated into `PREDICTOR.md §5c`. It is a secondary
(fairness) result off the critical path; write it up only if the paper needs the
fairness angle. Repro if/when needed: `ttu` at N=14 30 s vs 120 s vs `--cores 6`,
and `aguard` N=14.

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
for Kurt:** (1) ~~does Sudvarg §IV already bound cross-loop simultaneity?~~
**ANSWERED 2026-06-23 (full read, PAPER_NOTES): NO** — their scheduling is classical
utilization-based (fixed safe periods, Σu ≤ U_D) + CBF set-invariance; neither our
simultaneity bound nor a PNR deadline appears. *Residual for Kurt:* is our delta big
enough given their §VII future-work explicitly names "predictions / semi-clairvoyant
MC for optimism" (positioning + scoop risk). (2) ~~does our bound admit fleets that K–Q-style *optimal* rotation cannot?~~
**ANSWERED 2026-06-23 (read, PAPER_NOTES): rotation does NOT pre-empt** — K–Q
guarantee *stability* (not safety), autonomous plants (no disturbance/criticality, so
no simultaneity question), static offline cycle (not dynamic). *Residual for Kurt:*
could a K–Q-style contractivity argument be *extended* to a safe-set/PNR Lyapunov
function + disturbances and then subsume us? (field judgment).

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
   differs (different leg):** aguard N=16 max 10 (peak; >cores only 0.18 % of run),
   N=8 max 1 — sharp physics, more loops critical at once (params calibrated
   2026-06-23: peak unchanged, dwell 0.79 %→0.18 %, N=8 2→1). Full writeup
   `PREDICTOR.md §5d` + `PAPER_NOTES.md` 2026-06-22.
   *Still contingent on (A) surviving Kurt — the sim is its shadow, not the proof.*

1. **Cart-pole → paper-grade — param calibration DONE 2026-06-23** (`uMax` = 1.5 ×
   observed demand = 11.55 N; thetaHard/Soft kept as the given spec; shove 8 N ≤
   authority; GENERALIZATION §4 / PAPER_NOTES 2026-06-23; CLI `--u-max`/`--shove-force`/
   `--theta-max`). Headline re-derived: tolerance cliff invariant (~110 ms), aguard 17
   vs RM 10 crash-free, sim-crit dwell 0.79→0.18 %. *Remaining (supports generality,
   not novel):* the "reproduce-all-figures" orchestrator (Task 2); optionally a 3rd
   plant; cart-pole predictor optimization (naive 1 ms RK4, ~333 µs/27 % at N=8 — the
   one cart-pole caveat left, PREDICTOR §5f, optional).
2. **Kurt — the formal leg** (neither user nor AI can own it): verify `BOUND.md`
   + re-derive the §7.2 workload bound (full carry-in is 2× pessimistic,
   certified 5 vs empirical 10; limited carry-in m−1 — `tools/rta_solve.py`
   ready), and the theorem `floor ≥ θ − age_bound` ⇒ no crossing.
3. **Honest predictor — DONE 2026-06-22 (`*-honest`; PREDICTOR §5e).** Each
   predictive policy now has an `-honest` twin (`ttu-honest`/`hybrid-honest`/
   `aguard-honest`) ranking on a rollout seeded from the cloud's **delayed** state
   (`--pred-staleness MS`, default 16 = worst sensor delay) + a safety margin
   (`--pred-margin MS`, default 0), via a shared `InfoSet` flag (oracle variants
   kept for the A/B). Off by default ⇒ baselines byte-identical; `--pred-staleness
   0` ≡ oracle. **sim-crit/min_pnr stay on the ORACLE rollout** (ground-truth
   safety). **Result (car, worst, 3 cores, 30 s):** `ttu` is robust (true sim-crit
   0 through d=100 ms, 1 at d=200); `aguard` is fragile (N=18: 0→**4** at d=16, 14
   at d=100 — its 15 ms margin can't absorb staleness); `--pred-margin 60` fully
   restores aguard to 0. Plant-agnostic (cart-pole 2→3 post-calibration). *Remaining (PREDICTOR
   §6.4):* the honest gap is pure **staleness** — fold in the FMU's own `e_y_est`
   estimation error (no sensor noise / model error in this deterministic harness).
4. **Generality breadth:** parameter sweeps (speed/δ_max/net-delay/WCET/cores) on
   *both* plants; the car's zone-tolerance A(zone) (`ZONE_TOLERANCE.md`).
5. ~~Close Findings A & B~~ — DONE (A: per-vehicle θ, commit `3214880`; B:
   prediction-cost instrumentation, 2026-06-23, §5f / Finding B above).
6. Lower priority: clearance-ablation, triage A/B under overload, network-side
   scheduling, Q6 event-triggered.

## 6. Run / verify

```sh
cmake --build build -j
python3 tools/reproduce.py              # regenerate ALL scheduling CSVs + print tables (one command)
python3 tools/reproduce.py --list       # experiments (capacity/simcrit/honest/floor/tolerance) + which doc table each backs
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
(aguard), `--tau-crit MS` (sim-criticality, §5 item 0 / PREDICTOR §5d), `--pred-staleness MS`/`--pred-margin MS` (honest predictor, §5 item 3 / PREDICTOR §5e), `--triage`, `--delta-max RAD`, `--u-max N`/`--shove-force N`/`--theta-max RAD` (cartpole calibration, GENERALIZATION §4), `--net-delay MS`, `--validate-predictor`,
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
