# Fleet-Safety Bound — Formal Problem Statement

**For:** Kurt Wilson (formal leg). **From:** Stone + the harness team. **Status:**
draft conjecture — what is *measured* vs *assumed* vs *to-be-proven* is marked
inline. Nothing here is claimed proven.

> **User note (read me first; delete this whole block before sending to Kurt).**
> Every `> **User note** …` box is for you, not Kurt — plain-English explanation of
> the section above it, plus "what to do / try" where relevant. Strip them all out
> for his copy (they're all blockquotes starting with **User note**, easy to find).
> The goal of this document: hand Kurt a self-contained *question to prove*, so he
> never has to read our C++ to find out what we mean. Read it top to bottom once; if
> a section's formal statement loses you, the User note under it says the same thing
> in our cars-and-cores language.

---

## 0. The claim in one sentence

`m` shared cloud cores keep **all** `N` control loops safe, by composing:
- **(control)** a bound on how many loops can *simultaneously demand service*, given
  the route's physics; with
- **(scheduling)** a response-time analysis showing those demands are met within each
  loop's physics-derived deadline —

and this admits **more loops per core** than a worst-case-everything schedulability
test, because the physics says the loops are not all demanding at once.

> **User note.** This is the whole paper in one sentence. The two halves are the two
> legs: "how many are in trouble at once" (control) and "can the cores keep up"
> (scheduling). The phrase that does the work is *more loops per core than
> worst-case-everything* — that's the beyond-worst-case slack we're claiming.

---

## 1. System model (what actually runs)

Per vehicle `v`, a periodic chain of stages over base ticks of Δ = 0.1 ms:

```
S (T=5, in-vehicle) → [net δ_SC] → E (T=10, cloud) → C (T=20, cloud)
                    → M (T=20, cloud) → [net δ_CA] → A (T=30, in-vehicle)
```

- **S** = sensor, **E** = estimator, **C** = controller, **M** = merger, **A** =
  actuator. A feedforward stage **F** (T=20, cloud) also runs but carries the
  reference trajectory, **no sensor data** — it contends for cores but is not on the
  data-age path.
- **Cores.** The cloud stages (E, C, M, F) of all vehicles share `m = N_c = 3`
  identical cores. Scheduling is **global, fully preemptive, free-migration**, one
  job advances per core per 1-tick (0.1 ms) quantum. In-vehicle stages (S, A) run on
  each vehicle's own dedicated hardware — never contended.
- **Networks** are fixed delays under the analysis mode (`--exec worst`): δ_SC =
  δ_CA = 16 ms, FIFO, one packet per upstream completion.
- **Overrun policy: kill-and-hold.** A cloud job not finished by its next release is
  dropped (never publishes); the downstream register holds the last value.
- Periods, WCETs (best/avg/worst, ms) are in `BOUND.md §1` and
  `examples/parameters.md`; the exact values are `TaskModel.cpp:38-52`. Releases are
  synchronous, deadlines implicit.

**Precondition P1 (no overruns):** every cloud job completes within its period
(checked per run as `missed jobs: 0`). Under P1 each stage publishes once per period
and the data-age model below holds.

> **User note.** This is the machine. Stages = the assembly line each car's command
> goes through; the three cloud stages (estimator → controller → merger) are the part
> that fights for the 3 shared cores. "Kill-and-hold" = if a stage misses its slot,
> the car keeps using its last command (gets staler). P1 just says "nobody overran"
> — it's the clean regime; when the fleet is overloaded P1 breaks, and that's the
> interesting overload case. **Nothing to do here** — this section already exists in
> `BOUND.md §1`; I just compacted it. Kurt mostly needs it as the ground he stands on.

---

## 2. The measured quantity: data age

For the applied command at time `t`, **data age** = `t − (the tick the sensor sample
underlying that command was taken)`. The harness measures the worst case of this over
a run (`age_path` column; convention in `DATA_AGE.md §4`). It includes the actuator
hold time (the command ages while held between updates).

**Safety condition (per car):** the car stays inside its hard bound (|lateral error|
≤ 0.8 m) **as long as its applied-command data age never exceeds a threshold that
depends on where the car is** — see `A(zone)`, §3.2. That is the bridge from
*timing* (data age) to *control safety* (staying in-lane).

> **User note.** "Data age" = how stale the command the car is acting on is. The
> entire project measures this. The key idea of the next section: *how much staleness
> a car can survive depends on where it is on the track* — straight bits forgive a lot,
> curves forgive almost nothing. That dependence is what brings the physics in.

---

## 3. Definitions — the objects the theorem is built from

These are the new pieces. Each is tagged **[measured]**, **[assumed]**, or
**[to define]** so you know its current rigor.

### 3.1 Zone, and the zone map of a route **[measured]**

A **zone** is a stretch of the route classified by control difficulty, derived from
the reference trajectory's curvature (`|ff_ref_0|`, see `ZONE_TOLERANCE.md`):
`Z0` straight, `Z1` slight turn, `Z2` sharp turn, and `Z3` lane-change — the
**binding** zone, detected by curvature-*rate* (not just instantaneous curvature) and
expanded over the whole maneuver (see `Trajectory.h`). A route `R`
has a **zone map**: the sequence/fraction of track length in each zone.

### 3.2 A(zone): tolerable data age **[measured 2026-06-26 — causal table]**

`A(z)` = the largest data age at which a car whose commands are staled *while in zone
`z`* still satisfies the hard bound (no |e_y| > 0.8 m anywhere). Measured **causally**
(`tools/zone_sweep.py`: inject extra command delay only while in z, via
`--zone-target Z` / `--zone-extra-ms D`):

    A(z3 lane-change) = 140 ms   (BINDING -- the route's tightest tolerance)
    A(z0 straight)    = 290 ms
    A(z2 sharp turn)  = 290 ms
    A(z1 slight turn) = 400 ms

The lane-change is ~2–3× tighter than the rest.

**Refined + generalized (2026-07-04; PROOF_DRAFT §8.1).** The 50 ms grid hid
margin: delivered ages quantize in T_E = 10 ms steps (the instrument's true
resolution), and finer grids give **A(z3) = 170 (v10), 160 (v12.5), 90 (v15)**
(`zone_tolerance_z3_fine*.csv`, `zone_tolerance_v12.5/v15.csv`; non-z3 v12.5 =
{290, 240, 240}, v15 = {240, 240, 190}). z3 stays binding on every profile.
Two consequences: (1) **v15 is an applicability boundary** — its 90 ms budget
is below the uncontended chain bound (124 ms), so no scheduling policy can
certify v15's lane change at these periods; (2) at v10's refined 170 the
occupancy decomposition stops being load-bearing (fleet-wide F-demotion alone
certifies N = 8 — PROOF_DRAFT §8.5); the conservative 140 remains the value
this brief's Lemma-2 packet is stated against. Also measured: +13.5 ms of
feedforward staleness (the ZB-F demotion delta) moves the v10 cliff 170 → 160
(`--ff-extra-ms`; PROOF_DRAFT §8.3). **Honest status / nuances:** (1)
empirical, no closed form (contrast Sudvarg RTAS'25, who *derive* a safe delay via
CBF + sum-of-squares); (2) non-monotonic in instantaneous curvature — `A(z1 slight) >
A(z0 straight)` because straights often *precede* curves, so staling there delays the
car's entry to the next curve (spatial error propagation ⇒ the zone label doesn't
fully capture causal tolerance); (3) this *causal* (sudden-in-zone) number is more
conservative than the uniform-global whole-plant tolerance (~245 ms) — the
conservative, zone-specific value is the right one for a safety bound. Phase-1
*manifestation* attribution (where breaches land, not what caused them) is NOT this —
see PAPER_NOTES 2026-06-26.

**Load-bearing assumption + open wrinkle (flagged 2026-06-29).** `A(zone)` is keyed on
*position on the track*, but the true tolerance is **state-dependent** — a car entering
a zone already near the bound (large |e_y|) has ~0 tolerance regardless of the zone. So
`A(zone)` implicitly assumes the car **enters the zone well-tracked** (near the
centerline) — exactly the state the clean N=1 measurement produces. The state-dependent
counterpart already exists: **TTPNR** (§3.3) reads the car's *actual* state. So
`A(zone)` = the *track's* demand (good-entry); TTPNR = *this car's* instantaneous
danger. The bound reconciles them **inductively**: respect `A(zone)` in *every* zone ⇒
no car accumulates enough error to reach the edge ⇒ the "enters well-tracked"
precondition holds everywhere ⇒ the edge-entering case cannot arise. **The wrinkle:**
errors carry *across* zone boundaries (the overshoot / spatial-propagation finding) — a
car staled in zone z−1 enters z degraded — so `A(z)` measured for a *clean* entry
*under*-counts the danger for a degraded entry, and the per-zone budget the induction
needs may have to be **tighter** than the isolated `A(z)` (charge the worst hand-off
from z−1). **Consequence for the metric (§3.6):** the danger-relative `k` should fold
in the car's *actual* state/margin (or TTPNR), **not** be purely "delivered age vs
`A(zone)`" — accumulated error can make a car critical even with a fairly fresh command.

### 3.3 Recoverability deadline (point of no return, PNR) **[assumed — heuristic]**

For a car in a given state holding a given command, the **PNR** is the time after
which *no* future command can keep it inside the hard bound. **Honest status:** the
harness computes this with a **bang-bang rollout heuristic** (`PREDICTOR.md`), under a
monotonicity assumption — it is **not certified reachability**. A rigorous PNR (or a
clear statement of what's assumed) is one of the things we need from you.

### 3.4 Decision horizon θ **[to define]**

The lead time at which a car must be *picked up* by the scheduler so a fresh command
reaches its actuator before it would breach. `θ = (round-trip latency) + (slack to
wait behind other loops)`. Round-trip ≈ **90–100 ms** here (the uncontended
`age_path` is 90.5 ms). The danger horizon to count at is `θ`, **not** the round-trip
alone (counting at the round-trip is too late — the car is already unrecoverable).

### 3.5 Worst-case zone occupancy + the fleet model **[chosen: `F_spaced`; Occ measured 2026-06-29]**

`Occ(R, F)` = the maximum number of cars that can be in tight zones (small `A(z)`)
**at the same instant**, given route `R` and a **fleet model `F`** that says how cars
may be distributed on the route. In the Bosch setup all `N` cars share one track at
different **phases** (start offsets); `F` constrains how those phases may align.
**We adopt `F_spaced` (below); `F_adversarial` is retained only as a stated stress
case:**
- **`F_spaced`** — cars keep a minimum spacing (highway-like). Then `Occ` is bounded
  by `(tight-zone length) / spacing` → typically **`< N`** on a long route.
- **`F_adversarial`** — cars may cluster (a jam releasing together; or just "the
  phases are unconstrained"). Then `Occ` can reach **`N`** if the route's tight zones
  can hold them.

**Measured (`--pack-zone Z --min-spacing MS`, `tools/occupancy_sweep.py`).** The instrument
packs zone `Z`'s arcs (all of them — the route has several lane-change arcs) at the `F_spaced`
gap and reports the realized worst-case `Occ`. For the v10 route, **z3 (binding) = 105,400
ticks ≈ 8.9 % of the lap**, and measured `Occ` **tracks `ceil(zone_len / spacing)` within
+1–2** (per-arc boundary terms) — confirming the `(tight-zone length)/spacing` form. `Occ < N`
for realistic spacing (N=18: 1 s gap → `Occ=12`; 2 s → 7; 4 s → 4), degrading to `Occ=N` only
when stacked. **The same `Occ` is policy-independent (geometry) yet fatal under RM and near-safe
under aguard** (≤ 27 hard at spacing ≥ 500 ms under the corrected strictly-F_spaced
placements — see §9.2d note; the original packer read 0) — the occupancy→schedulability link for Lemma 2.
At the fully-stacked extreme (`Occ=N`) even aguard crashes — the honest `F_adversarial`
degradation (§5 Corollary). (PAPER_NOTES 2026-06-29.)

**Spacing robustness — the buffer (addresses Guo 2c).** `F_spaced` assumes the minimum
spacing `s` is *constant*; in reality delay-induced braking/drift can compress it. We certify
at the **effective** spacing `s_eff = s_nominal − Δ` (`Δ` = worst-case compression bound):
`Occ⁺` is non-increasing in `s` (machine-checked, `lemma1_check.py` [5]), so a buffer is
strictly conservative. At the certified `s ≥ 4 s` point the `Occ⁺ = 4` band extends down to
`s_eff = 3.5 s`, so the certification absorbs ≈ 500 ms of compression for free; to tolerate a
larger bound `Δ`, run `s_nominal ≥ 3.5 s + Δ`. Deriving `Δ` from a longitudinal model is the
A3 coupling (future work) — the buffer makes the theorem robust to any such `Δ`.
(PAPER_NOTES 2026-07-17.)

### 3.6 Concurrent demand k **[measured — danger-relative metric built 2026-06-29]**

`k(R, F) = Occ(R, F)` evaluated at horizon `θ` — the peak number of loops that
simultaneously *need a core* to stay safe. This is the number the scheduling half must
serve. The empirical proxy is now **danger-relative** (`--danger-tau FRAC`): per base
tick, count cars whose delivered age_path ≥ `τ·A(zone_now)` (`K_age`, the age-budget
term) **unioned** with the state-critical cars TTPNR < `θ` (`K`, folding in actual state
per §3.2). One run sweeps a fixed `τ` grid → the `K(τ)` demand curve. `K ⊇` the old
`--tau-crit` count by construction. **Finding (car, worst, 3 cores):** the two failure
axes are *orthogonal* — physics-blind RM scores `K_age ≈ 0` (its *served* cars are fresh)
but `K = 7/14, 12/18` via the state term (its danger is *unserved / past-PNR* cars);
aguard scores `K = K_age = 3/14, 6/18` with *zero* state-critical (its danger is purely
*age-over-budget but recoverable*). Neither single term is sound alone; the union `K` is
the conservative danger count (PAPER_NOTES 2026-06-29).

> **User note (the most important box in the document).** Here's the chain of ideas:
> a car can be stale up to `A(zone)` and survive — **lots** on a straightaway, almost
> none on a sharp curve. So at any instant only the cars *in tight zones* truly need a
> fresh command soon; those are the "in trouble" cars, and how many there are is
> `Occ`/`k`. **The fleet model (§3.5) is the one real decision you have to make**, and
> it's the crux: if you let cars stack anywhere (`F_adversarial`), `k = N` and we've
> gained nothing; if cars must stay spaced (`F_spaced`), `k < N` and the slack appears.
> **What to do / try:** (1) we've **adopted `F_spaced`** — it's defensible for an
> autonomous fleet and it's where the slack lives; note `F_adversarial` as a stress
> case. (2) You can *see* both ends with `--align-offsets`: `0` = spaced, `1` =
> stacked (the `k = N` worst case). (3) `A(zone)` is something you can measure yourself
> right now — run `tools/tolerance_sweep.py` and the zone-tolerance Phase-1 sweep. The
> two **[assumed]/[heuristic]** tags (PNR §3.3, `A(zone)` not derived §3.2) are the
> soft spots — flag them to Kurt honestly; don't paper over them.

---

## 4. The scheduler

The deployed policy is **aguard** (`AdaptiveGuard.cpp`): each car gets a guard
`θ_v = floor + (its measured live round-trip)`; cars with predicted PNR inside `θ_v`
enter an **emergency tier** served nearest-PNR-first; the rest are served by a comfort
score (worst tracking error first). Two tiers, with the guard `θ_v` as the line
between them.

**For the analysis, the cleaner target is the deadline-driven abstraction:** treat
each car `i` as a task whose **deadline `D_i(t) = A(zone of car i at time t)`** — it
must receive a fresh command within `A(zone)` or its age exceeds tolerance. Prove `m`
cores meet all `D_i`. **aguard is then the *achievability evidence*** (a real policy
that hits these deadlines empirically), not the object of the proof.

> **User note.** aguard is the smart performer we built. But proving things about a
> performer who changes his mind every tick (dynamic priorities) is genuinely hard.
> So the trick is: don't ask Kurt to prove "aguard is correct." Ask him to prove "a
> car in zone `z` needs refreshing every `A(z)`; can 3 cores meet everyone's refresh
> deadline?" — a cleaner, deadline-driven question. aguard's job is then just to *show
> it's achievable in practice*. **What to understand:** this separation (clean theorem
> vs. messy-but-working heuristic) is standard and Kurt will appreciate it; it's also
> the honest division of labor between the proof and the simulator.

---

## 5. The conjecture (what to prove)

Fix a route `R` (zone map), a fleet model `F`, `m` cores, and the task model of §1.

**Lemma 1 (occupancy — the new, control-side piece).**
There is a `k(R, F) ≤ N` such that, at every instant, the number of cars whose
deadline `D_i(t) = A(zone_i(t))` lies within the decision horizon `θ` is at most
`k(R, F)`. Under `F_spaced`, `k(R, F) < N` whenever `R` is not tight-zone-everywhere.

**Lemma 2 (schedulability — extends `BOUND.md §7`).**
If `m` cores, with per-service latency = round-trip and compute cost `C` per stage,
can deliver a fresh command to every car within its deadline `D_i(t)` whenever at most
`k(R,F)` deadlines are simultaneously within `θ`, then every car's applied-command
data age stays ≤ `A(zone)` for all `t`. (This is a response-time analysis over the §1
model; the §7 RTA + `rta_solve.py` are the starting machinery — needs the limited
carry-in re-derivation you already have queued.)

**Theorem (composition → fleet safety).**
Under Lemmas 1–2 and precondition P1, every car's data age ≤ `A(zone)` for all `t`,
hence (by §2/§3.2) no car ever crosses its hard bound. So `m` cores keep all `N` cars
safe on route `R` under fleet model `F`.

**Corollary (beyond worst-case).**
The classical test provisions for "every car needs the tightest deadline
`A(z3 lane-change)=140 ms` always," giving capacity `≈ m · A(z3) / C`. The bound above provisions for `k(R,F)`
tight-zone cars at once, giving a strictly larger capacity whenever `k(R,F) < N` —
i.e. on any route that is not tight-zone-everywhere.

> **User note.** Three steps, in order: **Lemma 1** = "no more than `k` cars are in
> trouble at once" (this is the new, hard, route-and-fleet-dependent piece — the heart).
> **Lemma 2** = "3 cores can refresh `k` cars in time" (this is the scheduling math
> that extends what we already built in `BOUND.md §7`). **Theorem** = glue them: nobody
> gets too stale → nobody crashes. **Corollary** = and we fit more cars than the
> pessimistic test, exactly when the route has some easy stretches. **What to
> understand:** if Lemma 1 gives `k = N` (the stacked case), the Corollary's "strictly
> larger" collapses to "equal" — the bound *honestly* degrades to classical on a
> slalom. That's fine and correct; the win is on real routes.

---

## 6. What we're asking you to do (prioritized)

1. **Lemma 1 (occupancy).** Is it true under **`F_spaced`** (our chosen model, §3.5)?
   This is the make-or-break, genuinely new piece. **Empirical `Occ(R, F_spaced)` curves are
   ready** (`tools/occupancy_sweep.py`, `--pack-zone`/`--min-spacing` — §3.5): measured `Occ`
   tracks `ceil(tight-zone length / spacing)` within +1–2, `< N` for realistic spacing. The
   candidate statement to prove: `Occ(R, F_spaced) ≤ ceil(L_tight / s)` (capped `N`), with the
   per-arc boundary correction. We can regenerate the curve for any `R`/`s`/`N`.
2. **Lemma 2 (schedulability) — the active leg; full packet in §9.** Re-derive the §7.2
   workload for the discrete global-FP model with **limited carry-in** (you flagged
   full-carry-in as 2× pessimistic: certified 5 vs empirical 10), then compose it against
   the `A(zone)` deadlines under the occupancy cap. `rta_solve.py` is ready to machine-check
   candidates. **The empirical inputs are now measured** — the `Occ(R, F_spaced)` and `k(τ)`
   curves + the aguard achievability witness are in §9.2, and §9.3 carries the crux (the §4
   bound 151.6 ms already exceeds `A(z3)=140 ms`, so occupancy + per-zone is load-bearing).
3. **Pin the soft spots:** (a) a defensible **PNR** definition or an explicit
   assumption (currently a bang-bang heuristic, §3.3); (b) whether to take `A(zone)`
   as **measured** or push for a derivation (§3.2); (c) the **inductive `A(zone)`-budget
   argument** + how to charge cross-zone error carry (the §3.2 wrinkle) — is "respect
   `A(zone)` everywhere ⇒ cars stay well-tracked" sound, and must the per-zone budget
   tighten for the worst hand-off from the previous zone?
4. **Adjudicate the scheduler abstraction** (§4): is the deadline-driven target the
   right thing to prove, with aguard as achievability?
5. **Sanity-check the related-work delta** — does the occupancy lemma actually clear
   Sudvarg RTAS'25 (per-loop utilization, no cross-loop simultaneity) and
   Kundu–Quevedo'19 (stability via static rotation, no safety/criticality)? Our reads
   say yes (`PAPER_NOTES.md`); your field judgment is the one that counts.

> **User note.** This is the ask list — the part Kurt acts on. #1 is the new science;
> #2 is finishing the RTA you both started; #3–#4 are honesty/scoping; #5 is the
> "are we actually novel" gut-check only he can give. **What to do:** when you meet
> him, lead with #1 and the fleet-model decision (§3.5) — everything else is
> downstream of those two.

---

## 7. Empirical anchors (instantiation + sanity checks)

All `--exec worst`, `m = 3` cores, reproducible via `tools/reproduce.py` /
`--align-offsets`:

- **Round-trip / uncontended age:** `age_path` = 90.5 ms at N=1 (sets `θ`'s floor).
- **A(plant):** car ≈ 245 ms, cart-pole ≈ 110 ms (`tolerance_sweep.csv`).
- **Capacity gap (the §7 headline):** RTA certifies N=5 (full carry-in); the sim runs
  breach-free through **N=10**; aguard carries **18** cars / **17** cart-poles. The
  2× gap *is* the limited-carry-in re-derivation target.
- **`k` depends on the horizon (why a count alone won't do):** cart-pole aguard N=16,
  same run — `k = 10/16` at τ=100 ms (0.17 % of run over cores) but `k = 16/16` at
  τ=300 ms (93.7 %), **0 crashes throughout**. (`PAPER_NOTES.md` 2026-06-25.)
- **`k` depends on the fleet model:** car aguard N=18 — spaced (`--align-offsets 0`)
  keeps `k ≈ 1`; stacked (`--align-offsets 1`) still only `≈ 2`, 0 crashes even at
  26.8 s age — but physics-blind RM on the same stacked route lets **14/18** go
  critical and crashes the fleet. (Stable car binds on scheduling; the unstable
  cart-pole is where occupancy bites.)

> **User note.** These are the real numbers, with the commands to regenerate them, so
> Kurt can poke at ground truth instead of trusting prose. The two bolded "k depends
> on…" rows are the empirical spine of the whole reframing — they're why the bound is
> about *service rate under a fleet model*, not a raw count. **What to try:** run the
> last two bullets yourself (`--tau-crit` sweep; `--align-offsets 0` vs `1`) so you've
> seen them move before you explain them to him.

---

## 8. Open decisions for us before Kurt can finish

1. **Fleet model `F` (§3.5) — DECIDED: `F_spaced`** (minimum-spacing fleet);
   `F_adversarial` retained as a stated stress case. (Lead decision, 2026-06-26.)
2. **Route family** — do we prove for the three Bosch profiles (v10/12.5/15), or a
   parameterized zone map? Affects how general the claim reads.
3. **PNR rigor (§3.3)** and **A(zone) derivation (§3.2)** — take as measured, or invest
   in a control-theoretic derivation? Trades effort for reviewer-proofness.
4. **Metric redefinition — DONE 2026-06-29 (`--danger-tau`, §3.6)** — fold `A(zone)` into the simultaneity instrument
   (delivered age vs `A(zone)`) so the empirical `k` matches the theorem's `k`.

> **User note.** These are *your* calls (with my help), and they gate Kurt — he can't
> finish without #1 especially. None needs him in the room. **What to do next, if you
> want to drive it yourself:** (a) decide #1 (I'd pick `F_spaced`); (b) run the
> zone-tolerance Phase-1 sweep to turn `A(zone)` from a hypothesis into a table; (c)
> let me build the danger-relative metric (#4) so the simulator measures exactly the
> `k` the theorem talks about. Do those three and the brief becomes concrete enough
> that Kurt's job is purely the two lemmas.

---

## 9. Leg 3 brief — schedulability composition (Lemma 2; the active leg)

**Status of the program.** The three AI/lead-ownable legs are done and instrumented:
**Lemma 1's occupancy curve `Occ(R, F_spaced)` is measured** (§3.5 / §9.2b), **`A(zone)` is
measured** (§3.2), and the **danger-relative demand `k` is measured** (§3.6 / §9.2c). What
remains — and the one piece neither the lead nor the harness can own — is **Lemma 2: the
schedulability composition.** This section is the self-contained packet for it: the precise
question, the empirical inputs (the `Occ` and `k` curves), the crux that makes the problem
non-trivial, and the RTA machinery to extend.

### 9.1 The question, precisely

Take the **deadline-driven abstraction** (§4): each car `i` is a recurrent task that must
receive a *fresh command* (one completed sensor→actuator round-trip) within a **relative
deadline `D_i(t) = A(zone_i(t))`** — its current zone's tolerable data age (§3.2):

    A(z3 lane-change) = 140 ms   (binding deadline)
    A(z0 straight) = A(z2 sharp) = 290 ms ;   A(z1 slight) = 400 ms

The deadline is **time-varying** (it changes as the car moves between zones) — the genuinely
new wrinkle over standard RTA. The **demand is occupancy-shaped**: under `F_spaced`, at most
`Occ(R, F) ≤ N` cars hold the *tight* deadline `A(z3)` at any instant (§9.2b); the rest hold
looser deadlines. The service is the §1 cloud chain (E→C→M) over `m = 3` shared cores under
global FP, with one round-trip of latency.

> **Lemma 2 (to prove), occupancy-parameterized form.** Fix route `R`, fleet model
> `F_spaced` with minimum spacing `s`, `m = 3` cores, the §1 task model. Suppose at every
> instant at most `Occ(R, s)` cars are in the binding zone (deadline `A(z3)`) and the rest
> have deadlines ≥ `A(z2)`. Then there is a schedule (and `aguard` realizes one — §9.2d)
> under which every car's applied-command data age stays `≤ A(zone_i(t))` for all `t` — i.e.
> every refresh deadline is met. Equivalently: characterize the admissible region of
> `(N, s)` (or `(N, Occ)`) for which `m = 3` cores meet all `D_i`.

Composed with **Lemma 1** (`Occ < N` for non-tight-everywhere routes under `F_spaced`) and
**P1** (§1, no overrun), this gives the **Theorem** (§5): no car crosses its hard bound, so
`m` cores keep all `N` cars safe — admitting **more cars than the classical "everyone needs
`A(z3)` always" test** (the Corollary, §5), exactly by the margin `N − Occ`.

> **User note.** In plain terms: a car in the lane-change must be refreshed every 140 ms; a
> car on a straight can wait ~290–400 ms. Only `Occ` cars are in the lane-change at once. The
> question for Kurt is the scheduling-theory half: *can 3 cores refresh the `Occ` urgent cars
> (140 ms) plus the rest (looser) in time?* If yes for `Occ < N`, we fit more cars than a test
> that makes everyone urgent. The hard, novel part is that the deadline **moves with the car**.

### 9.2 The empirical inputs you now have (all `--exec worst`, `m = 3`, v10, reproducible)

**(a) The deadlines** — `A(zone)` table above (§3.2; `tools/zone_sweep.py` → `zone_tolerance.csv`).
**[measured]** Causal, N=1, full lap. Honest status / good-entry assumption + cross-zone carry:
§3.2 (this bears on Lemma 2 only through the deadline *values*; the carry wrinkle is a Lemma-1/
budget concern).

**(b) `Occ(R, F_spaced)` — the demand cap (Lemma 1 input).** **[measured]**
`tools/occupancy_sweep.py` packs the binding zone's arcs at minimum spacing `s` and reports the
worst-case simultaneous occupancy. For v10, the z3 total length `L = 105,400` ticks (≈ 8.9 % of
the lap); measured `Occ` tracks `ceil(L/s)` within +1–2 (per-arc boundary):

| spacing `s` (ms) | `Occ`(z3) of N=18 | geo `ceil(L/s)` |
|---|---|---|
| 0 (stacked, `F_adversarial`) | 18 | 18 |
| 500 | 18 | 18 |
| 1000 (≈ 1 s gap) | 12 | 11 |
| 2000 | 7 | 6 |
| 4000 | 4 | 3 |

So `Occ < N` for any realistic following gap — the slack Lemma 2 gets to exploit.

**(c) `k(τ)` — the realized danger demand (§3.6).** **[measured]** `--danger-tau` counts cars
whose delivered age has eaten fraction `τ` of `A(zone_now)`, unioned with the state-critical
(TTPNR `< θ`) cars. One run sweeps `τ`. N=18 spread, default placement (the `K(τ)` column below
is `max_k_danger` = the `[+state]` curve in the committed `danger_sweep.csv`; regenerate both
axes with `python3 tools/reproduce.py danger`):

| `τ` | RM `K(τ)` | aguard `K(τ)` |
|---|---|---|
| 0.25 | 18 | 18 |
| 0.50 | 12 | 9 |
| 1.00 | 12 | 6 |
| 1.50 | 12 | 6 |

The `K(τ)` curve is the demand "at danger level `τ`"; a single point is a saturated gauge
(PAPER_NOTES 2026-06-25), so the curve is the object. (RM's `K` is all state-term:
unserved/past-PNR cars; aguard's is age-budget pressure on recoverable cars — orthogonal axes,
PAPER_NOTES 2026-06-29.)

**(d) Achievability (`aguard`).** **[measured]** Under packed occupancy, the *same* geometric
`Occ` is policy-independent, but the safety outcome is not — `aguard` meets the deadlines where
RM does not (N=18, pack z3, 30 s; `total_hard` = breaches summed over the fleet):

| spacing `s` (ms) | `Occ` | RM hard | **aguard hard** |
|---|---|---|---|
| 500 | 18 | 34,581 | **0** |
| 1000 | 12 | 26,003 | **0** |
| 2000 | 7 | 26,464 | **0** |
| 4000 | 4 | 34,207 | **0** |

*(Numbers above are the original 2026-06-29 packer's; the 2026-07-04 regenerated
`occupancy_sweep.csv` — strictly-F_spaced placements — shifts hard counts slightly,
e.g. RM@4000 = 34,209, aguard@1500 = 27; the `Occ` column is unchanged on every row.)*
| 0 (full stack, `Occ=N`) | 18 | 22,512 | 36,012 |

So **3 cores empirically keep up to `Occ = 12` binding-zone cars (out of N=18) safe** under a
realistic spacing — the existence evidence for Lemma 2. At the fully-stacked `Occ = N = 18`
extreme even aguard fails: the bound *honestly* degrades to classical when the route/placement
is tight-everywhere (`F_adversarial`, §5 Corollary). aguard is the **achievability witness**,
not the proof object (§4). *(2026-07-04: the packer now enforces spacing across both placement
passes — a latent F_spaced violation fixed; `Occ` unchanged on every row, aguard's s=1.5 s row
reads 27 hard instead of 0 under the corrected placements — still ~10³ below RM. There is now
also a **direct proof-object witness**: `--scheduler zband` holds every deadline with 0 missed
jobs in the certified region — PROOF_DRAFT §8.4.)*

### 9.3 The crux — why a uniform RTA does *not* close (the reason occupancy is load-bearing)

The uncontended round-trip is **`age_path = 90.5 ms` (N=1)**, so a binding-zone car has only
**`140 − 90.5 = 49.5 ms` of scheduling/queueing budget** before it breaches `A(z3)`.

Now the tension that makes this a real theorem and not bookkeeping: **the §4 worst-case age
bound at the certified capacity already exceeds `A(z3)`.** From `BOUND.md §7.3` (machine-
verified, `tools/rta_solve.py`): at the full-carry-in **certified capacity N = 5**, the §4
fleet-max age bound is **151.6 ms — which is `> A(z3) = 140 ms`.** So a *uniform* argument —
"P1 ⇒ every car's age ≤ a single bound ≤ `A(zone)`" — **cannot certify lane-change safety even
at N = 5.** It must become **per-zone** (only the `≤ Occ` cars in z3 need `≤ 140`; everyone else
needs only `≤ 290–400`) **and** either the bound must tighten (limited carry-in, §9.4) or the
scheduler must provably prioritize the in-z3 cars. *This is exactly why the occupancy
decomposition and the deadline-driven scheduler abstraction are essential, not cosmetic.*

> **User note.** This is the single most important paragraph for Kurt. The naive hope was
> "prove the fleet is schedulable (P1), then every car's age is under the bound, done." It
> fails: the loosest proven bound (151.6 ms) is already worse than the tightest tolerance
> (140 ms). The *only* way out is the contribution itself — count that few cars are in the
> tight zone at once (`Occ`), and give those cars priority. If Kurt makes the per-zone +
> occupancy argument work, the leg lands; if he can't, we learn the bound has to be tightened
> first (§9.4) or the claim weakened to looser zones. Either is a real result.

### 9.4 The RTA machinery to extend (`BOUND.md §7`, machine-checkable)

Lemma 2 builds on the discrete-time, unit-quantum, `m`-core global-FP response-time analysis in
`BOUND.md §7`. State you inherit:
- **The model + interference argument** (§7.2): per task `k`, `x = C_k + floor((1/m)·Σ_{i∈hp(k)}
  W_i(x))` with `W_i(x) = ceil((x + R_i − C_i)/T_i)·C_i`. Exact per tick (a rigor win over
  continuous-time global RTA). Periods/WCETs at `TaskModel.cpp:38-52`.
- **Machine solver `tools/rta_solve.py`** (validated vs hand calcs; cross-checked sound vs the
  sim). It will machine-check any candidate fixed point.
- **The known gap (the headline arithmetic, §7.3–§7.4):** full-carry-in certifies **N = 5**
  (first overrun at `F_5`); the sim runs breach-free through **N = 10** — a **2× pessimism gap**
  entirely from the borrowed **full-carry-in** workload term. **The queued fix is limited
  carry-in (`m − 1`, Guan RTA-LC):** *re-deriving that workload for this discrete synchronized-
  quantum model — not the arithmetic — is the critical path* (§7.4 items 2–3). It would place the
  certified capacity in `(5, 10]` and is the prerequisite for composing a *tight* per-zone bound.
- **Prototyped (CANDIDATE, UNVERIFIED — 2026-06-30, `rta_solve.py --workload limited`).** A
  sound-leaning `m−1` Guan-RTA-LC candidate (`none ≤ limited ≤ full` by construction; soundness
  guarded by the sim cross-check, not proven) lifts the **certified capacity 5 → 8** (gap to
  empirical 10 halved), cross-check clean (certified 8 ≤ empirical 10, no age-bound violation).
  **But it does *not* move the safety crossover:** the fleet-max age bound crosses `A(z3)=140 ms`
  at **N=4 under *both* full and limited** — because the bounds coincide at small N, where the
  *uncontended chain* (N=1 bound = **124 ms**, just under 140) already nearly saturates the
  lane-change tolerance. **Implication:** tightening buys *schedulability* (the certified
  substrate 5→8), not *uniform z3-safety* — so the per-zone + occupancy decomposition is
  load-bearing across the whole **N=4…10** range. Kurt's job is the *sound* re-derivation (the
  candidate's NC/CI form + jitter handling are exactly what he must verify/tighten).

So Lemma 2 has two coupled sub-tasks: **(i)** re-derive the limited-carry-in workload (tightens
the age bound toward measured), then **(ii)** compose that bound against the `A(zone)` deadlines
under the occupancy cap `Occ(R, s)` — the mixed-deadline / occupancy-parameterized schedulability
test, of which the §9.2d aguard run is the existence witness.

### 9.4a Theorem 2 (limited carry-in) in standard Guan-RTA-LC notation — the statement to prove

**Dr. Guo's directive (2026-07-17):** Theorem 2 — the limited-carry-in RTA — carries the headline
capacity lift (the "2.7× more cars" = ZB-F-X composed **N = 8 @ s ≥ 4 s** certified vs classical
**3**, §5 Corollary / PROOF_DRAFT §5). It is presently a **candidate** (`rta_solve.py`,
machine-checked + sim-cross-checked, *not* proven). The remaining publication step is to **bridge
the brute-force script to a general analytic proof under our tick-quantum model.** Below is the
candidate as implemented (`rta_solve.py::hp_interference`, modes `limited` / `limited-t`), written
in the notation of **Guan et al.'s RTA-LC** so the delta to the classical result is explicit.
*(Citation VERIFIED 2026-07-17: N. Guan, M. Stigge, W. Yi, G. Yu, "New Response Time Bounds for
Fixed Priority Multiprocessor Scheduling," RTSS 2009, pp. 387–397 — the origin of RTA-LC and the
"at most m−1 carry-in tasks" result.)*

For task τ_k on m identical cores, `R_k` is the least fixed point of the discrete iteration

    R_k = C_k + ⌊ (1/m) · Σ_{i ∈ hp(k)} I_i(R_k) ⌋          (exact per tick — §9.4/§7.2)

with each higher-priority τ_i's interference in a window of length `x` split into a **non-carry-in
(NC)** and a **carry-in (CI)** form, and **at most m−1 tasks charged the carry-in surplus** (Guan's
RTA-LC bound):

    I(x) = Σ_{i∈hp(k)} W_i^NC(x)  +  Σ_{(m−1) largest} ( W_i^CI(x) − W_i^NC(x) )_+ .

Our instantiations:

    W_i^NC(x) = ⌈x / T_i⌉ · C_i                                (no carry-in; Bertogna upper form)
    W_i^CI(x) = ⌈(x + J_i) / T_i⌉ · C_i,   J_i = R_i − C_i     (`limited`: response-jitter carry-in)
                                            J_i = T_i − C_i     (`limited-t`: mechanical carry-in)

`none ≤ limited ≤ full` by construction (each CI surplus ≥ 0, capped at m−1 terms), so `limited`
is bounded above by the already-sound full-carry-in form of §7.2 — sound-*leaning* and strictly
tighter. `limited-t` replaces the response jitter `R_i − C_i` with the mechanical jitter
`T_i − C_i` that kill-and-hold guarantees outright (every job executes within
`[release, release + T_i)`); it needs no response-time induction and is the form the PROOF_DRAFT
Lemma-2b band composition uses (band interferers' `R`'s are not statically knowable).

### 9.4b Proof-step ledger — what survives the tick-quantum model, what Kurt must re-derive

Our model — discrete unit quanta, `m` cores, free migration/preemption, **strictly periodic
synchronous releases**, strict total-order priority, kill-and-hold on overrun — differs from Guan's
continuous-time *sporadic* setting. Which classical RTA-LC proof obligations transfer, and which
need re-derivation here:

| # | Guan RTA-LC proof step | status in our tick-quantum model |
|---|---|---|
| 1 | **Interference conservation** — a busy-window instant where `J_k` is unserved has all `m` cores on `hp(k)` work | **SURVIVES** — discrete restatement (§9.4/§7.2); exact per tick (no fractional-quantum slop — a rigor win) |
| 2 | **≤ m−1 carry-in tasks** at the problem-window start | **RE-DERIVE — load-bearing.** Guan's window opens just after an instant with `< m` higher-prio jobs active. Synchronous periodic release + strict total order + kill-and-hold change the carry-in structure — plausibly a *tightening* (synchronous release can void carry-in for some tasks), but the `m−1` count must be re-established for this release model, not cited. |
| 3 | NC workload `⌈x/T_i⌉·C_i` upper-bounds the no-carry-in contribution | **SURVIVES** — sound (could tighten to `⌊x/T⌋C_i + min(C_i, x mod T_i)`) |
| 4 | CI via response jitter `J_i = R_i − C_i` (`limited`) | **SURVIVES** modulo the priority-order induction (R_i, i∈hp(k), solved first — standard; re-check under the non-monotone stop, #6) |
| 5 | CI via mechanical jitter `J_i = T_i − C_i` (`limited-t`) | **SURVIVES trivially** — kill-and-hold ⇒ execution ⊆ `[release, release+T_i)`; model-specific, no induction. (The one step our model makes *easier* than Guan's.) |
| 6 | Least-fixed-point existence + a valid stopping rule | **RE-DERIVE** — `limited`'s `I(x)` is **non-monotone** (the m−1 surplus selection shifts with `x`), so "iterate up, stop at `x = x_next`" is invalid. PROOF_DRAFT **Lemma 2a step S5** gives a candidate sound stop (any `x` with `C_k + I(x)//m ≤ x`); its soundness for the non-monotone case *is* Lemma 2a — Kurt's. |
| 7 | The `1/m` interference-to-response relaxation | **SURVIVES + TIGHTER** — exact `⌊·⌋` per tick vs. the continuous relaxation |

**Net:** steps 1, 3, 4, 5, 7 transfer (5 and 7 are *strengthened* by the discrete / kill-and-hold
model); the two genuine obligations are **#2 (the `m−1` carry-in count under synchronous release)**
and **#6 (S5 stopping-rule soundness for the non-monotone `limited` interference = Lemma 2a)**.
Empirically the candidate is **unrefuted**: at the certified capacity 8 and below, the widened
cross-check (§9.6) finds every measured `age_path ≤` the candidate's per-vehicle bound
(`N ∈ {1,4,6,7,8}`; tightest margin ≈ **31 ms**, at N=6 v0: 100.5 ≤ 131.6), and certified 8 ≤
empirical 10. **Empirical non-refutation is not proof (invariant #5)** — #2 and #6 are the analytic
gaps Kurt closes.

### 9.5 What is measured / assumed / to-prove (honesty ledger for leg 3)

- **[measured]** `A(zone)` deadlines (§3.2); `Occ(R, F_spaced)` curve (§9.2b); `k(τ)` curve
  (§9.2c); aguard achievability `Occ ≤ 12 → 0 hard` (§9.2d); the §7 RTA fixed points + the
  certified-5/empirical-10 gap (`rta_solve.py`).
- **[assumed / soft spots]** PNR is a bang-bang heuristic, not certified reachability (§3.3);
  `A(zone)` is empirical with a good-entry assumption + cross-zone error carry (§3.2 wrinkle) —
  these enter Lemma 2 only through the *deadline values* and the achievability witness, but flag
  them. The conservatism shows up concretely: aguard can have cars *over* the `A(zone)` budget
  (`K_age > 0`) yet **0 hard breaches** — the causal `A(zone)` is a conservative deadline, so
  meeting it is sufficient but maybe not necessary.
- **[to-prove — yours]** (1) the limited-carry-in workload re-derivation (§9.4i) — now stated in
  standard Guan-RTA-LC notation with a proof-step ledger (**§9.4a/b**): the two open obligations
  are the `m−1` carry-in count under synchronous release (ledger #2) and the non-monotone
  stopping-rule soundness (ledger #6 = Lemma 2a); (2) the
  occupancy-parameterized schedulability composition (§9.1 Lemma 2 / §9.4ii); (3) adjudicate the
  deadline-driven abstraction (§4) as the right proof object with aguard as witness; (4) confirm
  the per-zone + occupancy device clears Sudvarg RTAS'25 / Kundu–Quevedo'19 (§6 #5).

### 9.6 Reproduce every number above

    python3 tools/occupancy_sweep.py --out /tmp/occ_repro.csv   # Occ(s) + aguard-vs-RM hard (§9.2b,d)
    #   (the tool refuses to overwrite the committed occupancy_sweep.csv without --force;
    #    use `python3 tools/reproduce.py occupancy` to regenerate the committed files)
    python3 tools/rta_solve.py --cross-check # §7 RTA fixed points + sim cross-check  (§9.4)
    python3 tools/rta_solve.py --workload limited --cross-check --soundness-grid 1,4,6,7,8
    #   ^ Theorem-2 candidate (§9.4a): certified 8, widened age-soundness at every N in the grid
    #     (measured age_path <= per-vehicle bound, no counterexample) — the bridge validation (§9.4b)
    python3 tools/reproduce.py danger        # K(tau) curve, rm vs aguard, both axes -> danger_sweep.csv (§9.2c)
    ./build/cps --headless --vehicles 18 --scheduler aguard --exec worst --duration 30   # single K(tau) run (§9.2c)
    ./build/cps --headless --vehicles 1  --scheduler rm     --exec worst --duration 30   # round-trip 90.5 ms (§9.3)
    # single occupancy point + safety pairing:
    ./build/cps --headless --vehicles 18 --scheduler aguard --exec worst --duration 30 --pack-zone 3 --min-spacing 1000

> **User note.** Hand Kurt §9 as the leg-3 packet; it stands on §1 (model), §3.2 (`A(zone)`),
> §3.5 (`Occ`), §3.6 (`k`), §5 (the conjecture) and `BOUND.md §7` (the RTA). Lead with **§9.3**
> — the 151.6 > 140 crux is what tells him the occupancy decomposition is doing real work — then
> **§9.4a/b** (Theorem 2 in Guan-RTA-LC notation + the proof-step ledger — Dr. Guo's headline
> C→V leg: the two open obligations are ledger #2 and #6) and the coupled composition to-prove in
> **§9.4**. Everything numeric here is reproduced by **§9.6**; if he wants a different
> `N`/`s`/route, regenerate the curve and re-hand it.
