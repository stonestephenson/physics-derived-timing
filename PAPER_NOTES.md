# Paper Notes — running log of paper-worthy observations

A scratchpad for "worth a sentence in the paper" moments: findings, framings,
and cautions surfaced while working, before they're polished into Route A / B
prose. **Not** a formal doc — claims here still need the usual verification
(`BOUND.md` invariants, Kurt sign-off) before they leave this file. Each entry:
what it is, the evidence/repro, and where it would land.

Newest first.

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
