# Fleet-Safety Theorem — CANDIDATE proof draft (UNVERIFIED)

**Status: CANDIDATE / UNVERIFIED throughout.** Drafted 2026-07-02, revised
2026-07-03 after a 4-lens adversarial review (independent fresh-context
reviewers: scheduling-theory referee, counterexample constructor, formal-proof
auditor, physics/assumptions skeptic — their confirmed findings are integrated
and credited inline as **[council]**). Written by the AI harness for Kurt Wilson
to **independently re-derive, not rubber-stamp** (CLAUDE.md invariant #5).
Every step is tagged:

- **[PROVEN — inspection]** — a written argument below, checkable line-by-line;
- **[PROVEN — machine-checked]** — verified by an executable check, command
  given; *machine-checked ≠ proven for formula-level claims — the checks are
  finite-domain or replication-based; the tag says exactly what ran*;
- **[ASSUMED]** — an explicit assumption the theorem inherits;
- **[UNCERTAIN]** — the steps most likely to be unsound; Kurt starts here.

Companion problem statement: `THEOREM_BRIEF.md` (§5, §9). Model ground truth:
`BOUND.md` §1/§7. No Lean/Coq on this machine; machine checks are brute-force /
replication scripts (session scratchpad), outputs quoted, logic described.

**Headline (v10, m = 3 cores, `--exec worst`).** Composing Lemmas 1 + 2a + 2b:

> **8 cars at ≥ 4 s headway are certified lane-change-safe on 3 cores** —
> every car's `age_path` ≤ A(zone) at all times — versus **3 cars** for the
> classical "everyone needs A(z3) = 140 ms always" test at its strongest
> (Θ = R workload), i.e. **2.7× more cars per core** (4× against the
> same-workload Θ = T baseline, which admits 2). Honest caveats up front:
> the binding admission row passes by **2.6 ms** against the *conservative*
> A(z3) = 140 (see §8.1 — the refined cliff is 170, margin 32.6 ms, but see
> also §8.5); and degradation is honest: stacked fleets ⇒ Occ⁺ → N ⇒ the
> advantage collapses to classical.
>
> **Execution-round update (2026-07-04, §8):** the queued decisive
> experiments have now RUN. The theorem's envelope is validated in-sim (zero
> hard breaches, zero over-budget ticks — §8.2); the `zband` adversary exists
> and found no counterexample in the certified region (§8.4); A2 is
> quantified (−10 ms on the cliff — §8.3); and the refined cliff **reframes
> the corollary**: at A(z3) = 170, fleet-wide F-demotion alone certifies
> N = 8 uniformly and occupancy is no longer load-bearing on v10 — the
> occupancy device earns capacity exactly when the binding budget sits below
> the uniform bound at P1 capacity (§8.5), which is the conservative-140
> reading of v10, all of v12.5's margin questions, and any tighter plant.

Two physics assumptions (A1 in-zone/exit budgets, A2 F-demotion) and one
scheduling argument (band transients, §3.4) carried the pre-execution risk;
§6/§7 rank them and §8 records which are now retired by measurement.

---

## 0. Objects and instantiated constants

Discrete time, tick Δ = 0.1 ms. Per vehicle: cloud tasks E (C=11, T=100 ticks),
B (C=5, T=200; the Controller — THEOREM_BRIEF §1 calls this stage C, a letter
this draft reserves for WCET), F (C=25, T=200), M (C=5, T=200); in-vehicle S, A uncontended
(`TaskModel.cpp:38-52`; WCET floor ≥ 2 ticks, `TaskModel.cpp:100`). m = 3
identical cores, global, fully-preemptive, free-migration, **one job advances
per core per tick**, ready jobs served strictly by a total priority order
(`PolicyScheduler.cpp:21-53`, `RateMonotonic.cpp:26-32`). **Kill-and-hold**
(`TaskModel.cpp:135-159`): a job unfinished at its next release is dropped —
so, **mechanically, every job's execution lies within [release, release + T)**.
(Load-bearing below; note the mechanical fact covers *execution* only — a
killed job never *publishes*, so any publication-cadence argument additionally
needs P1. **[council referee]**)

Per-vehicle data-age bound (BOUND §4, taken as given — the drafted Layer-1
result, not re-proven here): with R_E, R_B, R_M in ticks,

    bound(R_E, R_B, R_M) = 116.6 ms + 0.2 · (R_E + R_B + R_M)     [ms]

so `bound ≤ A(z3) = 140 ms` ⇔ `R_E + R_B + R_M ≤ 117 ticks`.

Deadlines **[ASSUMED — measured physics, THEOREM_BRIEF §3.2]**: A(z3) = 140 ms
(binding), A(z0) = A(z2) = 290 ms, A(z1) = 400 ms (v10, causal, good-entry;
**conservative 50 ms-grid values — §8.1's fine grids refine the z3 cliff to
170/160/90 for v10/12.5/15; 140 remains the normative value this draft's
admission tests use unless the lead decides otherwise**).
**Grid disclosure [council skeptic]:** the zone sweep used a 50 ms grid —
z3 passes at measured age 140.5 and fails at 190.5 (`zone_tolerance.csv`), so
the true cliff lies anywhere in (140.5, 190.5): up to 50 ms of hidden margin,
or none. The 2.6 ms admission slack must be read against that granularity.

Route geometry (machine-extracted from the repo's own `Trajectory.cpp` zone
computation by a standalone probe; **[PROVEN — machine-checked]**):

| profile | lap (ticks) | z3 arcs K | z3 total L (ticks) | arc lengths |
|---|---|---|---|---|
| v10 | 1,178,000 | **4** | 105,400 | 32,000 / 32,200 / 19,400 / 21,800 |
| v12.5 | 944,000 | 4 | 85,900 | 26,000 / 26,100 / 16,000 / 17,800 |
| v15 | 786,000 | 3 | 76,000 | 47,200 / 13,600 / 15,200 |

K = 4 for v10 (docs said "several"); arcs 1–2 sit only 5,000 ticks apart (the
cluster matters for tightness).

**Erratum (Finding D, resolved 2026-07-17).** An earlier version of this table
and of `lemma1_check.py`'s `PROFILES` carried z3 arc *start* ticks rotated late
by each profile's wrap-run length (v10 +147,400, v12.5 +119,400, v15 +98,600) —
a `zone_probe.cpp` bug: its circular RLE merge folded the lap-wrapping run into
the first run and then re-accumulated starts from 0. The **lengths, K, L, and
lap above are unaffected** (rotation is an isometry of the occupancy problem)
and correcting the frame left **every occupancy value unchanged** (re-verified
by diffing `lemma1_check.py` output in both frames — all Occ/Occ⁺/exact-opt/
bound values identical). Two consequences of the correction: (i) in the true
frame no z3 arc — raw *or* inflated — reaches the lap boundary, so the earlier
claim "every profile's last arc ends exactly at the lap boundary, so inflated
arcs wrap" was a **frame artifact**; the wrapped-arc handling in `lemma1_check`
(`rotate_nonwrapping`, check [1]'s wrapped layouts) nonetheless **stays** — it
is still correct and still needed for arcs that wrap in general **[council
auditor]**. (ii) check [3]'s packer replication now runs at the true zone
positions, so its `F_spaced` min-gap diagnostic reads genuine `OK` (min-gap =
s+1 ≥ s) instead of the rotated frame's spurious `VIOLATED-by-instrument` — the
committed v10 `occupancy_sweep.csv` rows are thereby confirmed to arise from
genuinely F_spaced placements (the check [3] bound test no longer relies on the
`not spaced` waiver at s ≥ 750 ms).

**Fleet model `F_spaced`** **[ASSUMED — decided, THEOREM_BRIEF §8.1]**: all N
cars follow the same time-parameterized reference trajectory at phase offsets
φ_i; minimum spacing is **temporal** (pairwise circular phase distance ≥ s
ticks, invariant over time). Zone membership is position-indexed, and position
is time-parameterized (`zoneAt(step + offset)`), so **control quality cannot
feed back into occupancy** — Lemma 1's input is exogenous. (Real longitudinal
dynamics would couple; flagged as part of A3.)

---

## 1. Lemma 1 (occupancy) — PROVEN, machine-checked

> **Lemma 1.** On a circular track of `lap` ticks let Z be a union of K
> disjoint maximal arcs of lengths ℓ_1..ℓ_K ≤ lap (total L ≤ lap), **wrapping
> permitted**. Let P be any set of N points with pairwise circular distance
> ≥ s ≥ 1. Then
>
>     |P ∩ Z|  ≤  min( N,  Σ_j (⌊(ℓ_j − 1)/s⌋ + 1) )  ≤  min( N, ⌊L/s⌋ + K ).
>
> Car i's position at time t is (φ_i + t) mod lap and the constraint set is
> shift-invariant, so the bound holds for the occupancy Occ(t) at **every** t.

**Proof.**
*(1a — one arc.)* Unroll the arc: write its ticks as a, a+1, …, a+ℓ−1 in
along-arc coordinates (mod lap; valid for wrapping arcs since ℓ ≤ lap). For two
points in the arc, one of the two circular paths between them runs along the
arc, so circular distance ≤ along-arc separation; hence pairwise circular
spacing ≥ s forces consecutive along-arc separations ≥ s. With p points,
(p−1)s ≤ ℓ − 1, so p ≤ ⌊(ℓ−1)/s⌋ + 1. ∎
*(1b — summing.)* Σ_j ⌊(ℓ_j−1)/s⌋ ≤ ⌊(L−K)/s⌋ ≤ ⌊L/s⌋ by superadditivity of
⌊·⌋; add K, cap at N. ∎

**Tightness / the exact optimum (used by Lemma 2b's coupling — inside the
trusted base, not just reporting [council auditor]).** The bound is loose when
arcs cluster closer than s (v10 arcs 1–2). The exact optimum is computed by
anchored greedy over arc starts, justified by an exchange argument: slide each
point maximally in the decreasing-coordinate direction (each stops at
predecessor + s or its own arc's start — with half-open arcs, sliding toward
the arc *start* never leaves Z, and after first discarding P \ Z, no
out-of-zone point blocks the slide); if no point rests on an arc start, all
gaps equal s exactly (p·s = lap, a rigid ring) — then rotate the whole ring in
the same decreasing direction until the first arc-start touch: en route points
can only *enter* Z (crossing an arc's end downward) and the first exit event
would itself be an arc-start touch, so the in-zone count never drops. Inputs
with wrapping arcs are first rotated so none wraps (rotation is an isometry of
the whole problem) — **this normalization was added after the council found
the greedy scan silently undercounts wrapped arcs** (toy: lap=10, arc (8,4),
s=3 → old code 1, truth 2) **[council auditor — CRITICAL, fixed]**.

**Machine checks** (`lemma1_check.py`, session scratchpad):
- check [1]: anchored greedy == 2^|Z| brute force on **17,176 small-circle
  cases — exhaustive over all 1-arc layouts including wrapped ones; 2–3-arc
  layouts seeded-random plus rotated (wrapped) copies** — 0 mismatches, and
  no case exceeds either bound form. (Earlier wording "8,970 exhaustive"
  overstated the sampled multi-arc part **[council auditor]**.)
- check [2]: all three profiles, spacing grid 0.25–8 s: exact ≤ per-arc ≤
  headline everywhere.
- check [3]: a pure-Python replication of `Simulation::packZoneOffsets` +
  sliding run-max **reproduces every committed `occupancy_sweep.csv` Occ value
  exactly** (12/9/7/5/4 at s = 1/1.5/2/3/4 s), and each equals the exact
  F_spaced optimum — the instrument realizes the worst case. (Post-Finding-D,
  the replication runs at the true zone positions and the placements are
  genuinely F_spaced at every s — min-gap = s+1 — so the bound test holds
  without the `not spaced` waiver.)
- check [4]: the Lemma-2b coupling table (§3.5), now computed on the
  wrapped-arc-valid path; **values unchanged by the fix** (the 200-tick wrap
  tail never altered a count at these spacings).

**Instrument caveat (honesty) — FIXED 2026-07-04, see §8.6.** As of the
council round, `packZoneOffsets` pass 2 did not
spacing-check leftover cars against pass-1 cars (`Simulation.cpp:66-71`): the
instrument's full configuration can violate F_spaced (observed min gap 1,798
ticks at s = 10,000). It never inflated a committed z3 row (pass-2 cars start
≥ 85 s of track from z3; 30 s runs never bring them there — verified in the
replication), but a different geometry/duration could. Fix or doc-note the
instrument before reusing it for new routes.

---

## 2. Lemma 2a (RTA soundness for the discrete model)

Response-time bounds R_k for the unit-quantum global-FP system: used to
certify P1 (all R ≤ T ⇒ no kill ⇒ the §4 age bound applies) and inside the age
bound. `tools/rta_solve.py` iterates, per task in priority order,

    R_k = the first x (climbing from C_k) with  C_k + ⌊ Ω_k(x) / m ⌋ ≤ x.

**S1 (job-level fixed priorities; one live job per task).** [PROVEN —
inspection] The (period, vehicle, kind) key is a strict total order on tasks
(`RateMonotonic.cpp:26-32`); kill-and-hold gives ≤ 1 live job per task. In the
band scheduler (§3) a job's priority is fixed at release; the analysis is
per-JOB throughout.

**S2 (≤ m−1 carry-in).** [PROVEN — inspection] Fix a job J. Let t₀ ≤
release(J) be minimal with every tick of [t₀, release(J)) having all m cores
on jobs with priority > J. At t₀ − 1 some core served a lower-or-no job; the
scheduler serves ready jobs in strict priority order, so every ready
higher-than-J job was being served ⇒ at most m−1 such jobs were ready; any
higher job released < t₀ and unfinished at t₀ was among them. Hence ≤ m−1
higher-priority carry-in jobs, each from a distinct task (S1). **Own-task
exception [council referee — CRITICAL, repaired]:** in the *uniform* system no
job of J's own task can execute in [t₀, release(J)) (prefix ticks are fully
higher-priority and same-task jobs are not higher). Under *band stamping* this
fails in exactly one case: a BASE job J whose same-task predecessor was
top-stamped (car just left the flag region) — that predecessor is strictly
higher than J and may execute inside the window uncounted by hp(J). Repair:
§3.3 charges it explicitly (+C_κ). Top-band jobs are immune (a base-stamped
predecessor ranks below J; a top-stamped one shares J's key and is killed at
J's release). F never elevates ⇒ never affected.

**S3 (workload lemma — the one analytic leap).** [PROVEN — machine-checked
on-domain; prose is a sketch, full case analysis = Kurt **[council auditor]**]
Let task i release jobs ≥ T_i apart, each executing ≤ C_i ticks, all execution
inside [r, r + Θ_i), **with C_i ≤ Θ_i ≤ T_i** (the Θ ≥ C hypothesis was
missing from the first draft — without it the formula is false, e.g. T=10,
C=5, Θ=2, y=1 gives bound 0 < actual 1 **[council auditor — MAJOR, fixed]**;
both instantiations Θ ∈ {R_i, T_i} satisfy it). Then work executed in ANY
window of length y is

    W_i(y; Θ_i) = ⌈ (y + Θ_i − C_i) / T_i ⌉ · C_i .

*Sketch:* jobs J_1..J_p (releases r_1 < … < r_p) execute in [a, a+y); J_1
finishes > a and ≤ r_1 + Θ ⇒ r_1 ≥ a − Θ + 1; J_p starts < a + y ⇒ r_p ≤
a + y − 1; head contributes ≤ min(C, r_1 + Θ − a), tail ≤ min(C, a + y − r_p),
interior ≤ C; maximizing over phase gives the stated form. **Quantifier
honesty [council auditor]:** the machine check enumerates *exactly-periodic*
phases; the sporadic (≥ T_i gaps) case needs a compression step (slide releases
later to exact-T spacing anchored at the tail; Θ ≤ T keeps caps from
shrinking) — written nowhere yet; Kurt should either prove it or restrict the
statement to periodic releases plus the following remark, which is all §3
needs: **(subset monotonicity)** a car's top-band jobs are a *subset* of its
periodic jobs, and executed-work-in-window of a subset is ≤ that of the full
set, so per-task workload bounds derived for the full periodic task soundly
cover band-filtered subsets. **Machine check:** exact maximum over ALL phases,
ALL Θ ∈ [C, T], y ≤ 650, for each real (T, C) pair — zero violations, tight
somewhere (min slack 0) — `lemma2a_check.py` [1]. **Domain audit [council
auditor]:** every solver evaluation has y ≤ T_k ≤ 200 ≤ 650 ✓; the coverage is
parameter-set-specific — re-run the check if any task with T > 650 or a new
(T, C) pair is ever added.

**S4 (interference assembly).** [PROVEN — inspection] Non-carry-in tasks
contribute ≤ NC_i(y) = ⌈y/T_i⌉·C_i (only jobs released in-window). With S2,
interference ≤ Σ_i NC_i(y) + (m−1 largest surpluses W_i(y;Θ_i) − NC_i(y) ≥ 0),
dominating every admissible carry-in set — `hp_interference(...)`, modes
`limited` (Θ = R) and `limited-t` (Θ = T, no induction needed).

**S5 (fixed-point validity — includes a found-and-fixed hazard).** [PROVEN —
inspection] Any x with C_k + ⌊Ω_k(x)/m⌋ ≤ x bounds the response: else in
[t₀, t₀+x) every tick is all-m-higher (each consuming m units of the ≤ Ω_k(x)
available higher work) or J-execution (≤ C_k − 1 if unfinished), giving
x ≤ x − 1. Needs Ω valid only pointwise at x — NOT monotone. **Hazard:** the
limited surplus term is non-monotone in y and the as-found loop accepted
downward moves (could terminate on a non-fixed-point). Machine check: no
downward move ever occurs in-domain (N = 1..24; `lemma2a_check.py` [3] — run
on `limited`; `limited-t` is covered by the patched rule, not the scan);
patched to stop at `nx ≤ x`, sound per this step; `full`/`limited` outputs
byte-identical before/after (diffed).

**S6 (Θ = R induction).** [PROVEN — inspection, conditional] Priority-order
induction gives valid hp R's for the uniform system. The *band* system's
cross-band flippers void it — the band analysis therefore uses Θ = T only.

**Verdicts from real runs** (the required gates):
- As-found: `python3 tools/rta_solve.py --workload limited --cross-check` →
  **"RESULT: all checks passed."** Certified capacity **8**, empirical **10**,
  no age-bound violation at N = 6/8.
- Post-patch, same command → **"RESULT: all checks passed."**, byte-identical.
- **Exact scheduler replication** [PROVEN — machine-checked]: an independent
  Python tick-level re-implementation reproduces the C++ schedule exactly
  (N = 11, 30 s: missed = 4,497, equal) and every observed response ≤ the
  limited R at N = 3/6/8, E-tier exactly tight (obs 22 = R 22 at N = 6) —
  `lemma2a_check.py` [2]. Covers the synchronous phasing the system actually
  runs; S3's check covers other phasings at the workload level.

**Lemma 2a verdict.** The `--workload limited` candidate is **sound modulo
S2/S3/S5 as written** — S3 is the formula-level leap (standard
Bertogna–Cirinei-shaped jitter workload), brute-force-verified on-domain.
Certified capacity 5 → **8** (limited and limited-t); uniform fleet-max bound
crosses A(z3)=140 between N=3 and 4 (Θ=R: 137.8 → 144.6) or N=2 and 3 (Θ=T:
137.4 → 146.0).

---

## 3. Lemma 2b (occupancy-parameterized composition) — the highest-risk piece

**Why needed (§9.3 crux):** at every certified capacity the uniform fleet-max
bound (151.6 ms at N=5 full; 190.6 at N=8 limited) exceeds A(z3) = 140 ms —
no uniform argument certifies lane-change safety beyond N ≤ 3.

### 3.1 The proof-object scheduler ZB-F-X (zone-band, F-demoted, exit hold)

Definition **[the object of analysis; aguard is NOT this scheduler]**:
- Lead-in θ = **240 ms** (2,400 ticks) and **exit hold-down θ_x = 240 ms**
  (the hold-down was added on council findings — §3.4/§6 A1): a car is
  **flagged** while its track position lies in a z3 arc extended **backward
  by θ and forward by θ_x**.
- A cloud job is **top-band** iff its car is flagged at the job's RELEASE and
  its kind ∈ {E, B, M}; **F jobs are always base-band** (F is off the §4 age
  path; demoting it sheds 25/46 of top-band per-car load — the step that makes
  the numbers close; physics caveat = A2).
- Job priority: (band, period, vehicle, kind) — strict total order on jobs,
  band stamped at release, **never re-stamped** (an implementation that
  recomputes band from current position each tick voids S2/§3.2 wholesale —
  binding constraint on the future `zband` policy **[council referee]**).
- ZB-F-X needs position + the static zone map only — **no prediction, no PNR
  anywhere in the proof object.**

**The abstract membership premise [council counterexample-constructor —
MAJOR, now explicit].** Everything below rests on: *at most Occ⁺ distinct
cars are flagged at any instant of any interval [t₀ − T_max, f) around a busy
window.* "≤ Occ⁺ concurrently flagged" is strictly weaker and NOT sufficient —
an instantaneous flag handoff puts Occ⁺ + 1 distinct cars in one such
interval. Geometry supplies the premise via arc inflation (§3.5): a car
flagged anywhere in the interval sits, at t₀, within the arcs inflated
backward by θ + x̂ + T_max and forward by θ_x + T_max. **If flags are ever
driven by anything non-geometric (prediction, operator override), the theorem
is void.**

### 3.2 Top-band reduction. [PROVEN — inspection, given S1–S5 + Lemma 1]

Fix a top job J, window [t₀, f). Jobs above J are top jobs of flagged-at-
release cars, released ≥ t₀ − T_max (kill-and-hold); so their cars are flagged
somewhere in [t₀ − T_max, f) — by the premise, ≤ Occ⁺ cars, contributing E/B/M
tasks only. Apply S2–S5 with Θ = T (assumption-free — no interferer response
needed, killing the cross-band induction): J's response ≤ the closed
(Occ⁺-car, 3-kind) system's fixed point — exactly what `rta_solve.py --band K
--band-demote-f --workload limited-t` solves. **Window-length bootstrap
[council ×3 — the circularity, now explicit]:** the inflation uses the window
length x̂; taking x̂ := T_max = 200 is assumption-free (under P1 every window
that matters is ≤ its task's T ≤ T_max: a longer "window" contains a full
period of the analyzed task and a kill — excluded by P1, which condition
(iii) supplies). Back-inflation is then θ + T_max = 2,600 ticks **exactly —
zero slack**: any retune of θ, T_max, or a new task period silently
invalidates the constant; recompute it, don't reuse it. A first-violation
induction (order jobs by finish time; the earliest violator's window uses only
premise-covered interference) discharges the residual self-reference; Kurt
should write it in full.

### 3.3 Base-band reduction. [PROVEN — inspection, same machinery + repair]

A base job's higher-priority set is at worst every other car's tasks (band-
major order; bottom base rank). With Θ = T no interferer response is needed;
identities don't matter (vehicle symmetry — formally: match each real flagged
car to a top slot injectively, per kind; the interfering-task multiset is then
dominated by the static solve's **[council referee — replace any appeal to
fixed-point monotonicity with this multiset matching]**). **Own-task band
carry [council referee — CRITICAL, repaired]:** a base job's top-stamped
predecessor (car just exited the flag region) is strictly higher priority and
executes inside the window uncounted by hp — e.g. kind M: predecessor executes
⊆ [r−200, r−162), window reaches to r−167: ~5 uncounted ticks. Repaired in the
solver: every base-band E/B/M task's interference now carries an unconditional
+C_κ own-task term (`solve_rta` own_carry; inert outside band mode — uniform
outputs stay byte-identical, diffed). Post-repair base numbers appear in §3.5
(+1.2 ms at the operating point; no verdict changed). The same membership
premise (§3.1) covers base windows too (≤ T_max = 200 under P1 — within the
2,600 constant).

### 3.4 Transients (entry, exit, θ). [UNCERTAIN — scrutinize first]

- **Entry.** For t ≥ e + θ (e = flag time): every job on the applied command's
  causal path at t completed within [t − B_deg, t], B_deg = the §4 bound with
  R = T = 216.6 ms — **valid under P1** (kills break publication; P1 comes
  from admission condition (iii), independent of this argument — the first
  draft's "no schedulability needed" was wrong **[council referee — MAJOR,
  fixed]**). Each such job released ≥ t − B_deg − T_max ≥ e for θ ≥ B_deg +
  T_max = 236.6 ⇒ **θ = 240 ms** with no bootstrap. The referee independently
  re-derived the look-back (deepest release r_E ≥ t − 194.6 ms), so θ = 240
  carries ~45 ms of true slack. During the lead-in the car's deadline is still
  ≥ 290 and its age ≤ the base bound (elevation only shrinks its interference
  — discharged by the following lemma rather than argument: **(hp-subset)**
  a top job's hp multiset ⊆ the bottom-base job's hp multiset ⇒ Ω_top ≤
  Ω_base pointwise ⇒ by S5 the base-band R bounds top jobs too **[council
  referee]**).
- **Exit.** The deadline relaxes to ≥ 290, but the *physics* does not relax
  instantly — recovery from the maneuver continues past the boundary and the
  in-repo evidence shows z3-caused breaches landing in z0 after exit (§6 A1)
  **[council skeptic — CRITICAL]**. ZB-F-X therefore **holds the car top-band
  for θ_x = 240 ms past the arc** (service stays at its best through
  recovery); Occ⁺ recomputes with forward inflation θ_x + T_max = 2,600 and —
  machine-checked — **stays 4 at s = 4 s on all three profiles** (arcs 1–2
  merge, K→3; the hold-down is free at the operating point). After the
  hold-down, mixed top/base paths are bounded by the base composition via the
  side condition below.
- **Side condition (now admission conjunct (iv)) [PROVEN — machine-checked at
  the operating point]:** every top-band R ≤ the base-band worst R of its kind
  (post-repair: E 29 ≤ 61, B 37 ≤ 163, M 38 ≤ 173). Checked per instantiation,
  not universal **[council auditor]**. NOTE: `rta_solve.py --band` prints
  conjuncts (i)–(iii) only; (iv)'s per-kind comparison comes from a separate
  R-table extraction (3 lines of Python against `solve_rta`, or the queued
  `--band-deadlines` hardening) — the §3.5 table's (iv) column is from that
  extraction, not the band-mode printout.

### 3.5 Admission test (Lemma 2b statement)

> **Lemma 2b (candidate).** Fix route R (z3 arcs), F_spaced(s), m cores, the
> §0 task model, ZB-F-X with θ = θ_x = 240 ms. Let Occ⁺(s) = the Lemma-1
> bound (or exact optimum) on arcs inflated back 2,600 / forward 2,600 ticks
> (θ + T_max each way). If
>
>   (i)   bound_top(Occ⁺(s))  ≤ A(z3) = 140 ms      [closed top band]
>   (ii)  bound_base(N, Occ⁺) ≤ min A(non-z3) = 290 [bottom base rank]
>   (iii) all R ≤ T in the two-band system           [P1]
>   (iv)  every top-band R(κ) ≤ base-band worst R(κ) [exit/mixed paths]
>
> then every car's applied-command data age is ≤ A(zone_i(t)) for all t
> (steady state; P2/P3 as in BOUND §1).

**Machine instantiation** (post own-carry repair; `rta_solve.py --band K
--band-n 8 --band-demote-f --workload limited-t`):

| Occ⁺ | bound_top (ms) | vs 140 | bound_base @N=8 (ms) | vs 290 | P1 | (iv) | verdict |
|---|---|---|---|---|---|---|---|
| 2 | 129.6 | PASS | 194.6 | PASS | OK | PASS | ADMITTED |
| 3 | 133.8 | PASS | 195.2 | PASS | OK | PASS | ADMITTED |
| **4** | **137.4** | **PASS (margin 2.6 ms)** | **196.0** | **PASS** | **OK** | **PASS** | **ADMITTED** |
| 5 | 141.0 | FAIL | 196.6 | PASS | — | — | not admitted |

(Top-band numbers are N-independent — the band is closed, verified. P1 holds
through N = 8; N = 10 fails P1 under limited-t, F_8 R = 210 > 200.) Under
Θ = R (`--workload limited`; its cross-band induction is exactly what S6
cannot give — [UNCERTAIN], for Kurt) Occ⁺ = 5 would also pass (136.4). Without
F-demotion the top band certifies only Occ⁺ ≤ 2 (Θ=T) / 3 (Θ=R) — below v10's
K = 4 arc floor (one car per arc is always placeable for s ≤ 3.7 s), i.e.
useless on this route; **F-demotion is what makes the composition land.**

Coupling via Lemma 1 on the inflated arcs (`lemma1_check.py` [4], wrapped-arc
path, plus the θ_x variant run): **Occ⁺(v10, s = 4 s) = 4**; = 5 at 3 s; = 8 at
2 s. v12.5 and v15 give Occ⁺ = 4 at s = 4 s as well (their A(zone) tables are
NOT yet measured — geometry only).

### 3.6 Adversarial schedule battery (evidence, not proof)

A council reviewer built an exact two-band tick simulator (validated: uniform
N=11 missed = 4,497 = C++) and attacked §3.2/3.3 with **91 adversarial flag
schedules**: static sets, same-set toggling at every period 1–200, slot
handoffs across the premise boundary (gap 236/237/238/240), full-set swaps,
rotations, single-release pulses, entry/exit alignments, randomized legal and
premise-violating schedules. **Zero violations of any per-kind band bound; max
observed/bound = 0.89 (base F), 0.82 (top M); entry-transient responses never
exceeded steady maxima (22/27/31 vs bounds 29/37/38).** Premise-violating
probes (up to 16 distinct flagged cars per 40 ms window) *also* stayed under
the K = 4 bounds — large empirical slack. [PROVEN — machine-checked,
`redteam_band.py` + `redteam_band_results.txt`, session scratchpad.] This is
replication evidence for the band analysis; the harness-level `zband` policy
(real chain, real ages) remains the missing adversary.

---

## 4. Theorem and Corollary (candidate)

> **Theorem (fleet safety, v10 instance).** Under the §0 model, F_spaced with
> s ≥ 4 s (the *effective* spacing — see the spacing-robustness buffer below for
> delay-induced compression), N ≤ 8, ZB-F-X (θ = θ_x = 240 ms), and assumptions
> A1–A4 (§6):
> every car's applied-command data age stays ≤ A(zone_i(t)) for all t, hence
> (by the A(zone) safety bridge, §6 A1 — **the assumption carrying the
> residual physics risk**) no car crosses the 0.8 m hard bound.
> *(Composition: Lemma 1 ⇒ ≤ 4 cars in the inflated binding zone at any
> instant; Lemma 2b conjuncts (i)–(iv) at Occ⁺ = 4, N = 8 all PASS; Lemma 2a
> supplies the machinery; P1 ⇒ the §4 age bound applies.)*

> **Corollary (beyond worst-case).** The classical test — every car meets
> A(z3) = 140 ms always — admits **N = 3** at its strongest (Θ = R, valid for
> the uniform system by S6) and N = 2 under Θ = T. The occupancy-parameterized
> test admits **N = 8 at s ≥ 4 s: 2.7× more cars per core (4× against the
> same-workload baseline)**, earned exactly by the route's non-z3 fraction.
> Degradation is honest: s → 0 ⇒ Occ⁺ → N ⇒ conjunct (i) fails for N > 4 and
> the claim collapses to classical.

**Spacing robustness — the `F_spaced` buffer [ASSUMED → BUFFERED; addresses
Guo 2c].** The theorem's `F_spaced` hypothesis fixes a *constant* minimum
temporal spacing `s`. In a real fleet `s` is not exogenous: network/scheduling
delays perturb control, and delay-induced braking/drift can **compress** spacing
below its nominal value (the control↔occupancy coupling flagged in A3). We
handle this conservatively with a **safety buffer** — certify at the *effective*
spacing `s_eff = s_nominal − Δ`, where `Δ` bounds worst-case compression.
Because `Occ⁺` is non-increasing in spacing (`lemma1_check.py` [5],
machine-checked), `Occ⁺(s_eff) ≥ Occ⁺(s_nominal)`: a buffer can only *raise* the
demand the schedule must clear, never hide it, so the composition stays sound.
Sensitivity at the certified operating point (v10, inflated arcs, `N = 18` cap;
`lemma1_check.py` [5]):

| compression `Δ` | `s_eff` | `Occ⁺` | fits `K* = 4` (N = 8)? |
|---|---|---|---|
| 0 | 4.00 s | 4 | yes |
| 250 ms | 3.75 s | 4 | yes |
| 500 ms | 3.50 s | 4 | yes |
| 1.0 s | 3.00 s | 5 | **no** — needs band 5 (a FAIL row, §5) |
| 2.0 s | 2.00 s | 8 | no |

So the `s ≥ 4 s` certification **absorbs up to ≈ 500 ms of spacing compression
for free** (the `Occ⁺ = 4` band extends down to `s_eff = 3.5 s`); beyond that the
buffer must be pre-paid in the nominal gap — to tolerate worst-case compression
`Δ` while keeping `N = 8`, run `s_nominal ≥ 3.5 s + Δ` (conservatively
`4 s + Δ`). Deriving `Δ` from a longitudinal / braking model is out of scope
here (it is precisely the A3 control↔occupancy coupling, left as future work);
the buffer makes the theorem robust to *any* such bound `Δ` once one is supplied.

Context (not proof): the sim runs breach-free to N = 10 uniform; aguard holds
0 hard at N = 18 / Occ = 12 — the certified region sits well inside what a
good heuristic achieves; the analysis is conservative. **[SUPERSEDED by §8.4:
`zband` now exists and has been run — no counterexample found in the
certified region.]** (Original: no simulator counterexample against Lemma 2b
was possible — no zone-band policy existed; building `zband` with
release-stamped bands was the highest-value next instrument.)

---

## 5. Machine checks — reproduce everything

Machine-check scripts — **committed at `tools/proofchecks/` (2026-07-05;
originally session-scratchpad)** with pinned seeds and a README giving each
script's expected verdict: `lemma1_check.py` (17,176-case brute force +
geometry + instrument replication + coupling), `lemma2a_check.py` (workload
brute force + exact scheduler replication + dip scan), `redteam_band.py`
(91-schedule adversarial battery + archived results snapshot),
`zone_probe.cpp` (route geometry). Repo-side:

    python3 tools/rta_solve.py --workload limited --cross-check    # PASSED (as-found & post-patch)
    python3 tools/rta_solve.py --workload limited-t                # Θ=T uniform: cert 8, z3 crossover N=3
    python3 tools/rta_solve.py --band 4 --band-n 8 --band-demote-f --workload limited-t   # binding row: ADMITTED
    python3 tools/rta_solve.py --band 5 --band-n 8 --band-demote-f --workload limited-t   # FAIL row
    bash .claude/verify.sh --full                                  # G1+G2+G3 (uniform full-CI untouched)

`tools/rta_solve.py` session changes (uniform `full`/`limited` outputs kept
byte-identical, diffed): S5 stopping rule; `limited-t`; `--band/--band-n/
--band-demote-f`; the §3.3 own-task band carry.

---

## 6. Assumption ledger (the theorem inherits all of these)

- **A1 [ASSUMED — physics; the council's top finding sat here — EMPIRICAL HALF RETIRED, see §8.2].**
  A(zone) as measured (causal, N=1, v10, 50 ms grid) is a valid per-zone
  staleness budget, *including across zone exits and under fleet-wide
  simultaneous loading*. **Adverse in-repo evidence [council skeptic —
  CRITICAL]:** at the first failing z3 grid point (extra = 100 ms, age 190.5),
  **60 of 136 hard-breach frames land in z0 — after exit** (`zone_tolerance
  .csv`), i.e. the danger window outlives the zone; and the repo's own data
  shows harm is trajectory-shape-dependent, not pointwise-monotone (constant
  ~245 ms everywhere is safe while a sudden 190.5 in z3 breaches), so no
  dominance argument covers unsampled profiles. The theorem's envelope
  (≤ 137.4 in z3+holds, ≤ 196.0 elsewhere, N=8) **was never sampled by the
  calibration** (one zone stressed per run, nominal 90.5 elsewhere). ZB-F-X's
  exit hold-down removes the sharpest instance (worst service exactly at
  recovery — now the car keeps *top* service for 240 ms past the arc, at zero
  cost to Occ⁺), but the envelope question stands. **→ EXECUTED 2026-07-04;
  A1 retired at the operating point — §8.2 has the exact commands.** (The
  experiment this paragraph originally queued sketched values "≈ 104 / ≈ 47";
  do NOT reproduce with those — they overshoot the guarantee by the ~4 ms
  zone-entry wobble and yield a 1-frame K_age metric kiss; the calibrated
  validating vector is `101,101,101,43` with `--zone-flag-window 240`.
  Plants are physically independent — per-vehicle stepping, coupling only via
  shared cores — so the N=1 envelope run covers the fleet case.)
- **A2 [ASSUMED — physics; benign-leaning — CLOSED WITH A NUMBER, see §8.3].** F-demotion does not invalidate
  A(zone). Form of the worry is real (z3 is *defined by* the feedforward
  reference; demotion adds ff staleness — pre-execution estimate ≈ +16 ms; measured delta 13.5 ms (R_F 48 → 183 ticks), §8.3 — invisible to `age_path`).
  Mitigation **[council skeptic]:** the calibration's CA-hop injection already
  co-staled the ff content by the full injected extra — +50 ms at the passing
  z3 row, ≈ 3× the demotion delta, at matched profile shape — so A2 is
  dominated under level-monotonicity at fixed shape (an argument, not a
  measurement). Cheapest close: a small `--ff-extra-ms` knob (or the zband
  policy itself) + re-run the z3 sweep rows at +16 ms.
- **A3 [ASSUMED — fleet model; spacing now BUFFERED, §4].** F_spaced temporal
  spacing, invariant; static zone map; zone membership exogenous to control
  quality (true in this harness — time-parameterized positions from pre-recorded
  reference traces, `src/trace/Trajectory.h`, so spacing cannot drift in-sim;
  real longitudinal dynamics would couple — delays → braking/drift → spacing
  compression). **The invariance is no longer assumed outright:** the §4
  spacing-robustness buffer certifies at the effective spacing `s_eff = s − Δ`
  and is machine-checked conservative (`lemma1_check.py` [5]); a worst-case
  compression bound `Δ` (from a longitudinal/braking model — future work) plugs
  straight in via `s_nominal ≥ 3.5 s + Δ`. What remains genuinely A3 is
  *deriving* that `Δ` and the static-zone-map assumption.
- **A4 [ASSUMED — model].** P2 (fixed delays, `--exec worst`), P3 (steady
  state), and the §4 Layer-1 age bound itself (BOUND.md v0.1 — **also still
  unverified**; this draft composes it, it does not re-prove it).
- PNR/TTPNR: **not used** by the proof object; the §3.3-of-THEOREM_BRIEF soft
  spot moves out of the trusted base entirely.

---

## 7. Ranked: the 3 steps most likely to be unsound (Kurt starts here)

1. **A1's envelope validity — the zone-exit / superposition gap (§6 A1).**
   The only item with *adverse* in-repo evidence rather than mere absence of
   evidence. The exit hold-down (ZB-F-X) removes the worst instance
   structurally, but "age ≤ A(zone(t)) ∀t ⇒ safe" remains calibrated only on
   single-zone, nominal-elsewhere profiles with a 50 ms grid, against a
   binding margin of 2.6 ms. The queued envelope experiment is decisive and
   cheap — run it before any human proof effort.
2. **The band-transient accounting (§3.2–§3.4).** Post-council state: the
   own-task carry hole is found and repaired; the membership premise is
   explicit; the x̂ bootstrap is pinned to T_max with a zero-slack constant;
   91 adversarial schedules show no violation with ≥ 11% margin. What remains
   is the *formal* first-violation induction (unwritten) and the fact that no
   harness-level adversary has run — the genre (mode-change over global-FP
   busy windows) is exactly where published analyses break.
3. **S3 as a general claim (§2).** Now correctly hypothesized (Θ ≥ C) and
   verified exhaustively on-domain, but the prose is a sketch: the sporadic
   quantifier needs the compression argument (or the periodic restriction +
   subset-monotonicity route, which suffices for this system), and the
   coverage is parameter-set-specific. A boundary off-by-one here poisons
   2a and 2b simultaneously.

Retired by the council round: the wrapped-arc undercount (fixed + re-verified,
values unchanged); the B_deg/P1 ordering (fixed); the own-task carry (fixed,
+1.2 ms, no verdict change); the iteration dip (patched, latent in-domain).
Honorable mentions: A2 (cheap empirical close queued); the instrument's pass-2
spacing gap; conjunct (iv) must be re-checked per instantiation.

---

## 8. Execution-round results (2026-07-04) — the queued experiments have run

All items from the HANDOFF §5 AI queue executed. Every number below is from a
real run; gates (`verify.sh --full`, limited cross-check) re-verified after
each code change. **These results supersede the corresponding pre-execution
statements above where noted.**

### 8.1 The A(zone) cliffs, refined to instrument resolution

Delivered ages quantize in T_E = 10 ms steps, so 10 ms is the injection
instrument's intrinsic resolution. Fine grids (`zone_tolerance_z3_fine*.csv`):

| profile | coarse A(z3) (50 ms grid) | refined cliff (pass / breach) | non-z3 A (coarse) |
|---|---|---|---|
| v10 | 140 | **170.5 / 180.5 ⇒ A(z3) = 170** | 290 / 400 / 290 |
| v12.5 | 140 | **160.5 / 170.5 ⇒ A(z3) = 160** | 290 / 240 / 240 |
| v15 | — | **90.5 / 140.5 ⇒ A(z3) = 90** | 240 / 240 / 190 |

**v15 is an applicability boundary, not a data point:** A(z3) = 90 is below
the *uncontended* chain bound (124 ms at N = 1), so **no scheduling policy can
certify v15's lane change at these task periods** — the physics budget must
exceed the uncontended chain latency for any scheduling result to exist. The
nominal 90.5 ms pipeline itself rides the cliff. (For the paper: the clean
statement of when the whole approach applies.)

**Addendum 2026-09-04 — min over phase (PAPER_NOTES 2026-09-04).** The table
above was measured at a single chain phase (seed 0 = lap index 0), which is the
BEST phase on every profile: A(zone) depends on the phase of the E/B/F/M
releases relative to zone entry (period 20 ms, lap-invariant), monotone across
the hyperperiod with the worst phase at its sup. 21-phase enumeration — the
1 ms grid plus the 19.9 ms last tick (`--start-offsets-ms` + `zone_sweep.py
--phases-ms 0:20:1`; `zone_tolerance_z3_phase*.csv`,
`zone_tolerance_spot_phase*.csv`):

| profile | A(z3) min-over-phase (pass / first any-phase breach) | per-phase A(z3) range | non-z3 A min-over-phase |
|---|---|---|---|
| v10 | **150.5 / 160.5 (18/21 phases clean at 160.5)** | 150.5..170.5 | 290.5 / 400.5 / 290.5 (all phase-robust) |
| v12.5 | **140.5 / 150.5 (20/21 clean at 150.5; phase 19.9 breaches by 1.7 mm)** | 140.5..160.5 | 290.5 / 240.5 / **190.5** (z2 was 240) |
| v15 | **110.5 / 120.5 (14/21 clean at 120.5)** | 110.5..120.5 | 240.5 / **190.5** / **140.5** (z1, z2 were 240 / 190) |

Consequences for this draft: (i) §8.5's boundary comparison (151.6 F-demoted
top-band bound vs A(z3)) is now 151.6 > 150.5 on v10 — by 1.1 ms, inside the
instrument's 10 ms resolution: "at the boundary" — and 151.6 > 140.5 on v12.5
— by 11.1 ms, more than one step: clearly below it. The decomposition is
load-bearing at N=8 on both. (ii) The conservative A(z3) = 140 packet
constant survives at every phase on v10/v12.5 (on v12.5 by exactly one
instrument step). (iii) §8.3's
A2 shift (170 → 160) was a phase-0 effect: re-measured min-over-phase
(2026-09-04 (b) addendum in §8.3), the F-lateness effect is binary (the
Estimator's second job reads F fresh vs one period old; the Merger reads a
period-old F at every dose under the N=1 RM order) and within one instrument
step — the certified constants are the min over both measured regimes,
150.5 / 140.5 / 110.5, and no per-schedule A2 correction is needed; the
fresh-Merger regime and per-job mixing are stated assumptions. (iv) v15's floor tightens to 110.5 (single-phase 120.5), still below
the 123.4 F-demoted uncontended bound — same conclusion. (v) The Challenge's
soft constraint binds earlier still (v10 z3 A_soft = 120.5; v15 violates it
uninjected); DECIDED 2026-09-04 (Stone): certified hard-only, soft data reported as a limitation.

**Partition caveat on the v12.5/v15 rows [council-successor audit]:** the zone
segmentation constants (`Trajectory.h` thresholds) were hand-tuned to v10's
curvature scale and were NOT re-derived per profile (ZONE_TOLERANCE's standing
warning). The v12.5/v15 zone maps they produce look sensible (K = 4/4/3 arcs,
~9 % of lap — `tools/proofchecks/zone_probe.cpp`), but re-examine the
partition per profile before any v12.5/v15 A(zone) value becomes normative in
the paper.

### 8.2 A1: envelope validated at the operating point; A-table NOT composable

Instrument: `--zone-extra-vector z0,z1,z2,z3` + `--zone-flag-window 240`
(per-zone delay with the ZB-F-X flag emulation; 3-point zoneAt check, exact
since arcs ≥ 1.94 s; vector path verified byte-identical to the legacy
single-zone path). N = 1, full lap, worst:

The exact runs (N = 1, `--scheduler rm --exec worst --duration 120`; record
these verbatim — a reproducer must not have to guess the vector values):

    # (1) THE validating run — the theorem envelope, wobble-calibrated:
    ./build/cps --headless --vehicles 1 --scheduler rm --exec worst --duration 120 \
        --zone-extra-vector 101,101,101,43 --zone-flag-window 240
    #   -> missed 0; hard z0=z1=z2=z3=0; K_age(tau=1.0) max 0; worst age 190.5
    # (2) first attempt, 4-5 ms hotter (base 106 / flagged 47): 0 hard, but
    #     K_age(tau=1.0) max 1 — an INSTRUMENT-BOUNDARY artifact, not a physics
    #     excursion: the injection rides on the natural pipeline, whose
    #     zone-entry hold adds ~3-4 ms, so 90.5+47+wobble kisses the 140-table
    #     A(z3) for ~1 frame. Same artifact at --zone-extra-vector 47,47,47,47
    #     (age 140.5 in z3). Run (1) budgets the wobble (43 = 47 - 4); its
    #     K_age = 0 is the clean statement of the theorem's guarantee.
    # (3) F-demoted-uniform operating point (§8.5): uniform 57,57,57,57
    #     (age <= 150.5 everywhere) -> 0 hard.
    # (4) the A-table envelope: 200,300,200,50 (each zone at its own measured
    #     budget, no flag window) -> 9,402 hard-breach frames.

- **The theorem envelope PASSES** (run 1): ages held at the guarantee
  (≤ 190.5 non-flagged / ≤ ~137 flagged): **zero hard breaches,
  `K_age(τ=1.0) = 0`** — no tick anywhere with age ≥ A(zone_now). **A1 is
  retired at the operating point** (the fleet case reduces to this run:
  plants are physically independent, coupled only through the cores, which
  Lemma 2b covers).
- **The full A-table envelope FAILS catastrophically** (run 4) — the per-zone
  budgets **do not compose at full amplitude**. This *confirms* the §6 A1
  cross-zone-carry concern at the table's amplitudes and simultaneously shows
  why the theorem survives: its envelope (137/196) sits far below the table.
  The theorem must never be weakened toward "each zone at its own budget."

### 8.3 A2: quantified, closed

`--ff-extra-ms D` delays every F publish by D (clamped before F's next
release; F carries no age stamps, so `age_path` is untouched by construction;
default 0 byte-identical, gates green). At D = 13.5 ms (the demotion delta,
R_F 48 → 183 ticks): the refined v10 z3 cliff moves **170 → 160** (extra = 80
now breaches: 7 hard; extra = 70 clean). So F-demotion costs **one 10 ms grid
step of physics margin**; the certified operating point (bound_top = 137.4)
retains ≥ 22 ms against the ff-adjusted cliff, and the conservative table
value 140 remains below 160. **A2 closed with a number.**

**Addendum 2026-09-04 (b) — re-measured min-over-phase; the 160 is retired
(PAPER_NOTES 2026-09-04 (b)).** The 170 → 160 above is a phase-0 effect. Over
all 21 chain phases, at the certificate dose (13.5 ms) and at the P1 boundary
(20 ms, clamped to the tick before F's next release), the tables are identical
row for row: the F-lateness effect is BINARY — up to 7.5 ms of added publish
delay changes nothing, from 8 ms to the P1 boundary every outcome is
identical. The consumer that flips is the ESTIMATOR's second job of the
period (activation tick 100 reads `ff_out`; 24 + 76 = 100, threshold pinned
at 76 → 77 ticks), not the Merger: under N=1 RM the Merger activates at tick
5, before F publishes at tick 24, so it reads a period-old F at every dose
(a single-core `prm` run shows the third, fresh-Merger regime: 0.6935 vs
0.7683 m at v12.5 z3 +60 phase 19.9 — benign, and unreachable by this
instrument). In the late-F regime A(z3) =
150.5 / 150.5 / 110.5 (v10 / v12.5 / v15) against the fresh-F 150.5 / 140.5 /
110.5 — within one instrument step, and non-monotone on v12.5 (the staler F
clears the 150.5 cell by 1.3 mm where the fresh F breaches it by 1.7 mm).
Classical RM at N=8 spans both Estimator regimes across vehicles (R_F 63–183
ticks, limited-t; F-demoted top band 185). **Certified constants (Stone,
2026-09-04): the min over the measured regimes, 150.5 / 140.5 / 110.5; §8.5's
"ff-adjusted regimes" and the 160 are retired.** Stated assumptions, not
measured: the fresh-Merger regime (unreachable at N=1 RM; benign on the one
cell probed) and per-job mixing of the Estimator regimes at N=8 (the min over
two constant-lateness tables bounds a mixed sequence only if the response is
monotone in lateness, which v12.5's 3 mm inversion does not support) —
PAPER_NOTES 2026-09-04 (b) item 3.

### 8.4 The zband adversary exists — and found nothing in the certified region

`--scheduler zband` implements ZB-F-X exactly as analyzed: job band stamped at
RELEASE (council constraint honored — never recomputed), flag = car within
±240 ms of a z3 arc, E/B/M elevate, F never does, key (band, period, vehicle,
kind). Verified: on cartpole (no zones) zband ≡ rm tick-for-tick; G1/G2
baselines untouched. Attack results (v10, worst, N = 8, 120 s, packed z3;
row template — swap `--scheduler`, `--min-spacing`, or use `--align-offsets 1`
for the stacked row and `--vehicles 18 --min-spacing 1000 --duration 30` for
the collapse row):

    ./build/cps --headless --vehicles 8 --scheduler zband --exec worst \
        --duration 120 --pack-zone 3 --min-spacing 4000

| config | missed | worst age_path | K_age(τ=1, 140-table) | verdict |
|---|---|---|---|---|
| zband, s = 4 s (Occ 4) | 0 | 120.5 ms | 0 | ≤ 196.0 bound ✓ |
| zband, s = 3 s (Occ 5) | 0 | 120.5 ms | 0 | holds past certification |
| zband, stacked (Occ 8) | 0 | 110.5 ms | 0 | = F-demoted uniform, ≤ 151.6 ✓ |
| aguard, s = 4 s | 5,997 | 120.5 ms | 0 | P1 violated by design |
| zband, N = 18, s = 1 s | 54,523 | 29.6 s | 7 | honest collapse far past P1 |

No counterexample; margins large (worst observed 120.5 vs 196.0 bound). zband
also achieves empirical P1 (0 missed) where aguard drops ~6,000 jobs — the
proof-object scheduler is *cleaner* than the heuristic on the P1 axis inside
the certified region, and collapses honestly far outside it (N = 18: worse
than RM on ages — a certified-region scheduler, not an overload heuristic).
§4's "no simulator counterexample is possible" is now obsolete — the
adversary exists and has been run.

### 8.5 The corollary, reframed by the refined cliff (supersedes §4's framing)

At A(z3) = 170 (refined): **fleet-wide F-demotion alone** (every car's E/B/M
above every F; no bands, no occupancy, no spacing constraint) gives fleet-max
151.6 ms (limited-t) / 147.0 (limited-R) at N = 8 with P1 OK (numeric
coincidence alert: this 151.6 is unrelated to THEOREM_BRIEF §9.3's 151.6,
which is the *full-carry-in uniform* bound at N = 5; reproduce THIS one with
`python3 tools/rta_solve.py --band 8 --band-n 8 --band-demote-f --workload
limited-t` — it prints these numbers then verdicts them against the
hard-coded A(z3)=140, so expect `FAIL / NOT ADMITTED` and exit 1; the
140-vs-170 comparison is the queued `--band-deadlines` hardening) — ≤ 170,
so it
certifies N = 8 uniformly, and P1 (capacity 8) binds before the z3 deadline
does. Classical (F at its RM place) admits N = 6 (Θ=R) / 5 (Θ=T). So on v10
at the refined cliff, the honest chain is: **classical 5–6 → +F-demotion 8
(the P1 ceiling)** — and occupancy earns nothing further *here*.

**When occupancy IS load-bearing** (the general statement the paper should
make): exactly when the binding budget sits below the uniform bound at P1
capacity — i.e. A(z3) < bound_uniform-Fdem(N_P1) ≈ 151.6. True for: v10 at
the conservative 140 table (the §3.5/§4 result as drafted, margin 2.6 ms);
v12.5 at its refined 160 (margin 8.4 ms — nearly); ~~the ff-adjusted regimes
(§8.3)~~ (retired 2026-09-04 (b): the F-lateness effect is within one
instrument step; the min-over-phase constants 150.5 / 140.5 / 110.5 cover
both measured Estimator-read regimes under constant lateness — §8.3
addendum lists the two unmeasured cases); and structurally tighter plants (cart-pole's analog ≈ 110 ms — though
below the 124 uncontended floor, its chain periods differ). The occupancy
device is also the only one that *degrades gracefully in spacing* —
F-demotion has no knob to give back when the route worsens.

### 8.6 Instrument and reproducibility closures

- `packZoneOffsets` pass 2 now enforces spacing against ALL placed cars
  (closing the §1 caveat); `occupancy_sweep.csv` regenerated: **the Occ column
  is unchanged on every row** (the Lemma-1 backstop stands); aguard's
  danger/hard columns shifted with the new placements (s = 1.5 s: 0 → 27
  hard — still 3 orders below RM's ~28k; THEOREM_BRIEF §9.2d's "0 hard at
  ≥ 500 ms" weakens to "≤ 27").
- `reproduce.py` gained `zones` and `occupancy` experiments (all profiles +
  fine grids, one command, Guo directive).
- New committed CSVs: `zone_tolerance_z3_fine.csv`, `zone_tolerance_v12.5.csv`,
  `zone_tolerance_v15.csv`, `zone_tolerance_z3_fine_v12.5.csv`,
  `occupancy_sweep_v12.5.csv`, `occupancy_sweep_v15.csv`; regenerated
  `occupancy_sweep.csv`.

### 8.7 Updated ranking of remaining risk (supersedes §7's ordering)

1. **The band-transient formal induction (§3.4)** — top item purely because
   A1's empirical half is retired: the analysis remains unproven, though
   battery- and now sim-attacked with margin. Kurt's job unchanged.
2. **S3's general form** — unchanged (§7 #3).
3. **A(zone) semantics under scheduler-induced staleness — CLOSED 2026-07-04
   (core-starvation sweeps).** rm at 1 core (N = 1–3), 2 cores (N = 2–7), and
   zband at 2 cores, 120 s each: every P1-holding configuration (missed = 0)
   pins the worst scheduler-induced `age_path` at ≤ 110.5 ms (≤ 120.5 across
   all zband runs) — **P1-feasible schedules of this task set cannot reach
   the 140–180 cliff region at all.** The system is bimodal under
   kill-and-hold: the pipeline keeps up (ages within ~30 ms of uncontended)
   or P1 collapses (2 cores, N = 7: 5,999 missed — and the damage channel is
   *killed F jobs*, visible as fresh fb ages [100.5] with z2-heavy hard
   breaches: stale feedforward is the first casualty of overload, the A2
   axis again). Hence the injected experiments are strictly harsher than
   anything a P1-certified schedule can produce, the causal sudden-in-zone
   shape is unreachable by any real schedule here, and ZB-F-X's actually
   produced shape (fresh-in-zone) is exactly what the §8.2 envelope run
   validated. No residual gap.
