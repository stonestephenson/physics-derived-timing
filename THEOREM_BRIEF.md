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

The lane-change is ~2–3× tighter than the rest. **Honest status / nuances:** (1)
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

### 3.5 Worst-case zone occupancy + the fleet model **[chosen: `F_spaced` — see §8.1]**

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

### 3.6 Concurrent demand k **[measured proxy exists]**

`k(R, F) = Occ(R, F)` evaluated at horizon `θ` — the peak number of loops that
simultaneously *need a core* to stay safe. This is the number the scheduling half must
serve. Our empirical proxy is the simultaneous-criticality count (`--tau-crit`), to be
**redefined danger-relative** (age vs `A(zone)`) and swept over `τ`.

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
   This is the make-or-break, genuinely new piece. We can hand you empirical `Occ(R,F)` curves
   (via `--align-offsets` + zone-aware placement) to test any candidate statement.
2. **Lemma 2 (schedulability).** Re-derive the §7.2 workload for the discrete
   global-FP model with **limited carry-in** (you flagged full-carry-in as 2×
   pessimistic: certified 5 vs empirical 10), then compose it against the `A(zone)`
   deadlines. `rta_solve.py` is ready to machine-check candidates.
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
4. **Metric redefinition** — fold `A(zone)` into the simultaneity instrument
   (delivered age vs `A(zone)`) so the empirical `k` matches the theorem's `k`.

> **User note.** These are *your* calls (with my help), and they gate Kurt — he can't
> finish without #1 especially. None needs him in the room. **What to do next, if you
> want to drive it yourself:** (a) decide #1 (I'd pick `F_spaced`); (b) run the
> zone-tolerance Phase-1 sweep to turn `A(zone)` from a hypothesis into a table; (c)
> let me build the danger-relative metric (#4) so the simulator measures exactly the
> `k` the theorem talks about. Do those three and the brief becomes concrete enough
> that Kurt's job is purely the two lemmas.
