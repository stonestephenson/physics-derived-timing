# Paper Notes — running log of paper-worthy observations

A scratchpad for "worth a sentence in the paper" moments: findings, framings,
and cautions surfaced while working, before they're polished into Route A / B
prose. **Not** a formal doc — claims here still need the usual verification
(`BOUND.md` invariants, Kurt sign-off) before they leave this file. Each entry:
what it is, the evidence/repro, and where it would land.

Newest first.

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
- Plant-agnostic: cart-pole aguard-honest N=8 sim-crit 2 → 4.

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

**Evidence / repro.** `for d in 0 16 100 200; do ./build/cps --headless --vehicles
18 --scheduler aguard-honest --exec worst --duration 30 --pred-staleness $d; done`
(+ `--pred-margin`, `--scheduler ttu-honest`, `--plant cartpole`). Details
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
**10** (>cores 0.79 %), N=8 max **2**; RM N=16 max 10 (99 %). The unstable plant's
sharp cliff makes more loops critical at once ⇒ car binds on scheduling, cart-pole
on physics. (Cart-pole params uncalibrated — qualitative.)

**Open / contingent.** This is the empirical shadow, **not** the theorem — still
contingent on (A) surviving Kurt (does the physics actually bound k? is k < m
achievable where a naive "all-critical-at-once" test fails?). The real (A) test is
whether the *best* predictive policy can be forced past cores while loops are
still recoverable: on the car it cannot through N=18; on the (uncalibrated)
cart-pole it can at N=16.

**Evidence / repro.** `for s in rm ttu aguard; do for n in 6 14 18; do ./build/cps
--headless --vehicles $n --scheduler $s --exec worst --duration 30; done; done`
(+ `--tau-crit`, `--plant cartpole`, `--csv`). Details: `PREDICTOR.md §5d`.

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
verify the handle. The 5 must-cite PDFs (Sudvarg, Kundu–Quevedo, Etcibasi,
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
| 16 | 9/16 | **1/16** |

aguard carries **~14 cart-poles crash-free vs RM's ~11**, and crashes far fewer
at every overload — by feeding the freshest command to whichever pole is nearest
its (physics-derived) PNR. (It takes more overruns from reordering but converts
them into zero crashes.)

**Why it matters.** The *same* age-criticality scheduler that carries 18 cars
(vs classics' 10–12) also protects the tight-tolerance *unstable* plant where RM
fails — the TTPNR-guided guard is plant-agnostic because TTPNR is computed from
each plant's own physics. Route-B generality, on a second plant.

**Evidence / repro.** `for n in 12 14 16; do for s in rm aguard; do ./build/cps
--headless --plant cartpole --vehicles $n --scheduler $s --exec worst
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
