# Session Handoff — CPS Challenge Visualizer

Resume point for a fresh agent. Last updated **2026-06-17**.

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
- **Route A (workshop / challenge-response):** realistically achievable —
  *draft this summer, submit to an RTSS-colocated workshop / WiP in fall 2026.*
- **Route B (RTSS/RTAS main track):** **not as-is.** Needs the theorem +
  honest information + generality + a verified bound + SOTA comparison.
  Months of lab work, Kurt-led, RTAS'27/RTSS'27.
- **The project is currently in "keep adding policies" mode. Publishability
  now requires the opposite: freeze the policy set, then harden / generalize /
  prove / write.** Do not add another scheduler unless asked — consolidate.
- **Kurt and Dr. Guo are the authority on venue/bar, not us.** The open
  decision they must make: workshop-this-fall vs hold-for-main-track, and
  whether the θ-from-age-bound theorem is provable on a useful timeline.

Team: user (lead) + CS student (sweeps, RTA fixed-point solver, infra) + EE
student (zone tolerance, control side) + Kurt Wilson (PhD mentor; spot-checks
formal claims; first author of the MEMOCODE'24 paper Route B extends).

## 2. Current state

- HEAD = this session's commit (2026-06-17: RTA solver + §7.3 corrections; prior
  `883f051`), pushed to remote **`tempbosch`** (`github.com/
  stonestephenson/tempboschchall`, branch `main`). **Push only to `tempbosch`.
  NEVER push to `origin`** (the Bosch upstream). `relatedPapers/` stays
  untracked (third-party PDFs).
- Working tree clean after this handoff commit.
- Builds clean: `cmake --build build -j`. Fidelity gate passes
  (1.49e-08 m, all 3 profiles). All policy baselines reproduce.

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

## 5. Prioritized next steps

Reframed around publishability (consolidate, don't add features):

1. **Decide venue with Kurt/Guo** (workshop-fall vs main-track) — gates
   everything below. Put Findings A–C and the capacity result in front of him.
2. **Kurt verifies `BOUND.md`** (Lemma 1 pairing, hold-term composition) +
   `PREDICTOR.md §3` (recovery heuristic, monotonicity). **Now the blocking item
   for the Q1 capacity number: the §7.2 workload bound** — full carry-in is 2×
   pessimistic (certified 5 vs empirical 10); re-derive it (limited carry-in,
   m−1) for this discrete model. `tools/rta_solve.py` is ready to plug it in.
3. **The theorem** (main-track spine): prove `floor ≥ θ − age_bound` ⇒ no car
   crosses 0.8 m under stated assumptions. Composes `BOUND.md` with the guard.
4. **Close Findings A & B** (per-vehicle θ; prediction-cost instrumentation +
   assumption statement) — both cheap, both pre-submission must-dos.
5. **Honest predictor** (the biggest credibility gap): predict from estimated
   state + last-sent command via the `InfoSet` pattern in `ContextAware.cpp`.
   Every predictive policy currently cheats with ground-truth state.
6. **Generality:** multi-track / multi-profile / δ_max ±50% sensitivity sweeps
   (EE student — `ZONE_TOLERANCE.md`, unblocked; `--net-delay` exists).
7. ~~CS student: machine-solve `BOUND.md §7` fixed points~~ — **done**
   (`tools/rta_solve.py`: RTA + capacity sweep + sim cross-check; see §2). Next:
   feed it Kurt's limited-carry-in workload (item 2) for the tight certified number.
8. Lower priority: clearance-ablation study, triage A/B under real overload,
   network-side scheduling, Q6 event-triggered (drop fixed periods).

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
(aguard), `--triage`, `--delta-max RAD`, `--net-delay MS`, `--validate-predictor`,
`--csv FILE`, `--save/--replay FILE`, `--select N`, `--speed X`, `--screenshot[-at]`.

## 7. Key files
- `CLAUDE.md` — agent bootstrap (invariants, reading map).
- `DATA_AGE.md` — age metric + conventions (§4d = dual conventions).
- `BOUND.md` — analytical bound v0.1 + RTA (§7, machine-verified); review flags inline.
- `PAPER_NOTES.md` — running log of paper-worthy findings (cert gap, phasing, hold-free).
- `PREDICTOR.md` — TTV/TTPNR, policies, fidelity gate, sweeps (§5–5c).
- `ZONE_TOLERANCE.md` — EE experiment spec.
- `src/sim/Predictor.{h,cpp}` — plant port, rollouts, warm-started PNR search.
- `src/sim/Simulation.cpp` — `refreshPredictions` (cadence, warm-start), `buildViews`.
- `src/sched/TaskModel.cpp` — `endTick` (stamps, age), `releaseIfDue` (overrun);
  `recentLatchAgeTicks` (the live round-trip signal).
- `src/sched/policies/` — one .cpp per policy; `Policies.h` has shared helpers.
- `src/viz/Visualizer.cpp` — `drawPrediction` (overlay, live + replay).
- `tools/rta_solve.py` — RTA solver + capacity sweep + sim cross-check (machine-verifies §7).
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
