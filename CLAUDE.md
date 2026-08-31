# CLAUDE.md — Agent Bootstrap (read first, follow exactly)

Stable orientation for AI agents on this project. Volatile state lives in
`HANDOFF.md`. Rule of thumb: if you change how the project *works*, update
this file; if you change what is *true right now*, update `HANDOFF.md`.

## What this project is

REU research project (Dr. Guo's lab) sparked by the Bosch RTAS 2026
"Physics-Driven Real-Time CPS Challenge": N simulated plants' control chains
share N_c cloud cores; we study the end-to-end **data age** (staleness of the
applied command) under different scheduling policies, and how much
**physics-derived, beyond-worst-case** slack that exposes.

The harness is **plant-agnostic** (a `Plant` interface, `src/sim/Plant.h`): the
Bosch LateralMotionControl FMU (`LateralPlant`) is case study #1; an inverted
**cart-pole** (`CartPolePlant`, `--plant cartpole`) is case study #2, proving the
framework generalizes beyond Bosch.

Three building blocks (the general thesis: *derive timing requirements from the
physics, then exploit the beyond-worst-case slack*):
- **The bound** — a proven analytical upper bound on data age + a
  machine-verified response-time analysis (`BOUND.md`).
- **Age-criticality scheduling** — per-context maximum tolerable age enforced by
  a guarded/adaptive cloud scheduler; extends Wilson et al. (MEMOCODE 2024).
- **Generalization** — the same machinery across plants (`GENERALIZATION.md`).

Current strategy, venue, and what's true *now*: `HANDOFF.md`.

Team: Stone + CS student (solver, sweeps, infra) + EE student (zone
tolerance, control side) + Kurt Wilson (PhD mentor: spot-checks formal claims;
students do the bulk of verification). Status and timeline: `HANDOFF.md`.

## Reading map (in order; stop when your task is covered)

Always:
1. This file.
2. `HANDOFF.md` — current state, baselines, key facts, open next-steps.
   Do NOT re-derive or contradict its "key facts" without evidence.

Then by task:
- **Running / experiments**: `USAGE.md` (build, flags, adding a scheduler).
- **Anything touching the age metric**: `DATA_AGE.md` — its §4 conventions
  ARE the definition of the measured quantity.
- **Theory / the bound**: `BOUND.md` (its status header says what is
  verified); the fleet-safety theorem candidate + machine checks are
  `PROOF_DRAFT.md`, the Kurt-facing formal statement is `THEOREM_BRIEF.md`,
  and corrections-of-record / paper-worthy findings live in `PAPER_NOTES.md`
  (newest first — check it before quoting any headline number). Literature in `relatedPapers/`: Li et al. RTSS'24 = tightest
  multi-rate chain bounds (`DirectlyRelated.../Priority_Optimization_for_
  Autonomous_Driving_Systems...pdf`; citation verified 2026-07-17); Arafat et al. DAC'22
  (chain RTA machinery) and Wilson et al. MEMOCODE'24 (Route B's prior)
  under GuoLabSpecifics/.
- **Zone-tolerance experiments**: `ZONE_TOLERANCE.md`.
- **Prediction system / ttu scheduler / overlay**: `PREDICTOR.md` — TTV and
  TTPNR definitions, the assumed steering limit, the fidelity gate
  (`--validate-predictor`; re-run after ANY predictor change).
- **Second plant / the `Plant` seam / cart-pole / adding a plant**:
  `GENERALIZATION.md` — the plant-agnostic architecture and case study #2.
- **F-channel leg / frontier scheduler / A_F-A_B staleness budgets /
  per-channel Condition I**: `FCHANNEL.md` — claims, reviewer dispositions,
  measured results (§9), instrument errata, queued work (§10); study
  history in `FRONTIER.md`; raw logs in `fchannel_rawlogs/`.
- **Scheduler / policy code**: `src/sched/` — `TaskModel.cpp` (`endTick` =
  stamp propagation, `releaseIfDue` = overrun policies),
  `PolicyScheduler.cpp`, `policies/*.cpp`, interfaces in `Scheduler.h` +
  `CorePolicy.h`.
- **FMU semantics**: `LateralMotionControl/FMU_README.md` (Bosch's) and
  `LateralMotionControl/sources/LateralMotionControl.c` —
  `process_trigger_events` is ground truth for data routing.
- **Challenge requirements / framing**: `ChallengeProposal/RTAS2026_Invited.pdf`
  (§III–IV) and `examples/*.md` (task parameters, constraints).

## Invariants (violating these silently invalidates the research)

1. `DATA_AGE.md` §4 conventions are the DEFINITION the bound is proven
   against. Never change them without explicit human sign-off; a change
   invalidates `BOUND.md` and every recorded baseline.
2. `age_path` is the bound's target; `age_fresh` is reaction latency.
3. Formal/soundness runs use `--exec worst` only (pert reorders packets vs
   stamps) and require `missed jobs: 0` (precondition P1) — check it.
4. Fixed-priority tie order is the strict total order (period, vehicle,
   kind). Changing tie-breaking or `--overrun` changes the analyzed system:
   re-run the `HANDOFF.md` baselines and update HANDOFF + `BOUND.md` §7 +
   the goldens hard-coded in `.claude/verify.sh` in the same commit (the
   done-gate stays red otherwise).
5. `BOUND.md` is unverified draft until humans sign off. Numbers marked
   "preliminary / hand-iterated" must be machine-verified before use. No
   lemma goes into a paper without human re-derivation.
6. The FMU is a prebuilt black box — never edit or recompile it; all
   measurement is harness-side shadowing of its trigger events. It lives behind
   the `Plant` seam (`src/sim/Plant.h`) as `LateralPlant`; a new plant is a new
   `Plant` implementation, never a change to that path — re-run the HANDOFF
   baselines after touching the seam (the refactor was verified byte-identical).
7. Git: push to `physics-derived-timing` only (the remote formerly named
   `tempbosch`; GitHub repo renamed 2026-07-06). NEVER push to `origin` (the Bosch
   upstream). Four items stay untracked (local to Stone's Mac; on a fresh
   clone their doc pointers dangle — ask Stone rather than treating that as
   breakage): `relatedPapers/`, `ContextForGuo/`, `f1tenth_cloud_control/`
   (stale vendored HIL copy; live code = the lab repo, HANDOFF §2), and
   `PAPER_OUTLINE_DRAFT.md` (the paper-writing strawman).

## How to work here

- **The simulator is the adversary.** Any run where measured `age_path`
  exceeds an instantiated bound is a counterexample — the most valuable
  possible result. Report it loudly; never smooth it over. Conversely,
  "measured ≤ bound" can validate a structurally WRONG bound (slack in one
  term masking an omitted term — this happened: a hold-free bound survived
  N=1 by 0.3 ms). Decompose gaps per term before claiming tightness.
- Before changing scheduling-visible behavior: predict the effect on the
  baselines, make the change, re-run, compare. Surprises are findings —
  document them in `HANDOFF.md`, don't tune them away.
- Verify load-bearing doc claims against code before relying on them (docs
  drift; code is truth). Cite `file:line` in discussions.
- Runs are cheap (~40× real time): settle questions empirically.

## Quick reference

    cmake -B build -S . -DCMAKE_BUILD_TYPE=Release && cmake --build build -j
    bash .claude/verify.sh   # fast G1+G2 gate vs golden (add --full for G3); the done-gate runs this
    ./build/cps --headless --vehicles 6 --scheduler rm --exec worst --duration 30
    ./build/cps --headless --plant cartpole --vehicles 8 --scheduler aguard --exec worst
    ./build/cps --headless --vehicles 1 --scheduler rm --exec worst --duration 120 --validate-predictor  # gate: 1.490e-08 m (scales w/ run length -> use 120 s)
    python3 tools/reproduce.py            # regenerate ALL CSVs (no-arg includes the ~2.5 h fbattery leg -- name experiments to skip it)
    # schedulers: rm | prm | edf | context(oracle) | honest | ttu | hybrid | aguard | zband(proof-object)
    #   | frontier (aguard + zone-aware F economics; FCHANNEL) | eskip(instrument)
    #   (+ ttu/hybrid/aguard-honest: predict from delayed state, not ground truth)
    # plants: lateral (FMU car) | cartpole    other: --overrun, --net-delay MS,
    #   --guard/--floor MS, --tau-crit MS, --danger-tau FRAC, --pack-zone Z/--min-spacing MS,
    #   --pred-staleness/--pred-margin MS, --delta-max RAD,
    #   --u-max/--shove-force/--theta-max (cartpole calibration; GENERALIZATION §4), --validate-predictor, --csv FILE, --seed N

## Before you end a session (this keeps the system alive)

1. Update `HANDOFF.md`: current state, changed baselines, done/open lists.
2. If you changed a convention, structure, or process: update the owning doc
   (`DATA_AGE` / `BOUND` / `PREDICTOR` / `GENERALIZATION` / `ZONE_TOLERANCE` /
   `USAGE` / this file) in the same commit as the code change.
3. Commit in the existing log style (imperative summary + bullet body).
   Push to `physics-derived-timing` when asked.
4. Keep this file stable and short (≤ ~150 lines). Detail belongs in the
   owning docs; state belongs in `HANDOFF.md`.
