# Paper Notes — running log of paper-worthy observations

A scratchpad for "worth a sentence in the paper" moments: findings, framings,
and cautions surfaced while working, before they're polished into Route A / B
prose. **Not** a formal doc — claims here still need the usual verification
(`BOUND.md` invariants, Kurt sign-off) before they leave this file. Each entry:
what it is, the evidence/repro, and where it would land.

Newest first.

---

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
