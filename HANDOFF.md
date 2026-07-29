# Session Handoff — CPS Challenge Visualizer

Resume point for a fresh agent. Last updated **2026-07-17**.

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

Team: Stone + CS student (sweeps, RTA fixed-point solver, infra) + EE
student (zone tolerance, control side) + Kurt Wilson (PhD mentor; spot-checks
formal claims; first author of the MEMOCODE'24 paper Route B extends).

## 2. Current state

- **Active branch `paper-generalization`** (off `main`, pushed to
  **`physics-derived-timing`**: `github.com/stonestephenson/physics-derived-timing`
  — **repo + local remote renamed 2026-07-06** from `tempboschchall`/`tempbosch`;
  older entries below say "pushed to tempbosch", same remote. Do NOT create a new
  repo under the old name (it would kill GitHub's redirect for teammates who
  haven't updated their remotes). `main` holds through the RTA
  solver (`4f49f46`); the cart-pole generalization (Plant seam + second plant +
  Phase-3 evidence, 4 commits) lives on the branch. **Push only to `physics-derived-timing`.
  NEVER push to `origin`** (the Bosch upstream). `relatedPapers/` untracked.
- **Session 2026-07-27/28: NEW SUBPROJECT — F1TENTH cloud-control HIL (real car
  + simulated cars, one scheduler).** Council-reviewed plan, then built. Two
  code homes: (a) the lab repo **`~/repos/cloud_control_demo`**
  (github.com/RTIS-Lab/cloud_control_demo — Kurt's; car = `rtis-jetson`,
  goat track = the real SLAM-mapped ±0.25 m corridor), branch
  **`cloud-sched-integration` — PUSHED to the lab repo 2026-07-28 (Stone
  approved the push)** for teammates to pull;
  (b) this repo's untracked `f1tenth_cloud_control/` = an older vendored copy,
  now **layout-stale** (dev moved to the lab clone) but carrying the TUM
  column-order loader fix (`track.cpp` right/left swap + regression test) the
  Stone is passing upstream by hand. Built on the branch: an **external-vehicle
  seam** in the f1sim core (`attachExternalVehicle`/`injectExternalSample`/
  command sink — reality provides sensing/network/actuation; the car's cloud
  job competes in the *unchanged* A-GUARD pool; byte-identical when unused;
  loopback tests reproduce the exact 10+4+10 ms round trip, determinism, and
  zero perturbation of an uncontended sim car), a ROS-free native build guard,
  **`cloud_sched_node`** (wall-clock catch-up pacer; `/amcl_pose` +
  `/odometry/filtered` in; AckermannDrive out with **header.stamp echoing the
  source sensor stamp** so round trip is measured on the car's own clock and
  fed back via `applied_ack`; **SHADOW mode default** — `/teleop/drive` only
  with `live:=true`; speed capped 0.5), **`mock_car_node`** (fake rtis-jetson
  on the exact topics, artificial WiFi jitter), and `INTEGRATION.md` (contract
  + onboarding: listen-only → shadow → car-on-stand → slow laps). **Container
  rehearsal (isolated, ROS_LOCALHOST_ONLY) PASSED:** 60 s at drift 0.00 s,
  589 samples → 581 commands applied, 0 stale, `/teleop/drive` silent, round
  trips 19–138 ms. Two debugging lessons recorded in code/docs: a burst-held
  unfair mutex starved the ROS executor (now per-step locking), and
  sleep-per-tick pacing collapses to 0.3× under container timers (now
  fixed-timestep catch-up). **NEVER connect to the car without Stone's
  explicit go** — first contact needs Kurt's watchdog answers + approval.
  **2026-07-29 (lab, DEMO DAY): THE CAR SELF-DRIVES UNDER CLOUD SCHEDULING.**
  Full day at the track with Stone driving the process; Kurt intermittently.
  Milestones, in order: (1) localization bringup recipe established (on the
  Jetson system container: `ros2 launch f1tenth_stack fusion.launch.py
  localization_mode:=amcl map:=/ros_ws/goat_track.yaml`; global-init via
  `/reinitialize_global_localization` + a meter of motion; helper
  `~/start_localization.sh` on the Jetson). (2) **Frame bug found by shadow
  mode and fixed**: the centerline CSV (Kurt's generator) is in the map-IMAGE
  frame — the generator hardcodes origin 0,0 (`main.py:219`, upstream fix
  suggested) — while AMCL uses origin (−6.37,−4.91); fixed by measured
  translation against a recorded RC lap (residual 0.086 m mean);
  `goat_track_centerline_amcl.csv`. (3) **Infeasible-corner finding**: the
  arc≈2.4 m corner had centerline radius 0.41 m < the car's ~0.74 m minimum
  turning radius — no controller could hold it (all excursions
  right-of-travel, 24% commands steering-saturated); fixed by splicing the
  recorded human lap through arc 2.0–4.6 + 0.5 m moving-average smoothing
  (`goat_track_centerline_smooth.csv`) + lookahead 0.5. Clean laps after.
  (4) Live ops verified: Ctrl-C → car stops (VESC/watchdog); the RUN_AUTO
  trigger gates the launch; **one cloud_sched_node at a time** (fixed marker
  IDs collide; zombie instances freeze RViz markers — pkill first).
  (5) Demo instrumentation: RViz overlays (latched centerline/edge Paths;
  fleet MarkerArray green/orange/red = normal/on-core/emergency; the real
  car as translucent "cloud view" box whose gap to /amcl_pose IS the data
  age); start gate (sim fleet holds on the grid until the car moves);
  **exact core-share counter — the real car holds ~10% of the core at N=4,
  its proportional share** (instantaneous 10 Hz sampling is phase-blind to
  2–8 ms jobs; two instrumentation bugs fixed, scheduler was always
  correct). Mac env gained nav2_msgs + native rviz2. **Lab-repo branch has
  5 commits unpushed as of this writing** (fleet markers, start gate,
  marker-state fix, exact core-share, marker hardening). **NEXT: the fleet
  ladder N=4→8→12
  (bridge CSVs per run) + cross-N analysis; then Kurt asks: generator
  origin fix, car-side ack/echo logging, watchdog timeout number.**
  **MARKER BUG ROOT-CAUSED (2026-07-29, post-compact): stale binary.** The
  stuck-blue live run predated the 15:23 `ab182b8` rebuild — its log
  (`cmds=1047` with `car-core~0%`) is *impossible* in current code, since
  `commands_emitted` and `core_ticks` increment in the same
  `runCloudOneTick` path (a job can only complete by executing on a core).
  Isolated mock rehearsal with the current binary: external marker orange
  **201/201 frames** at car-core~4% — the frame-latch saturates because the
  car's ~10 jobs/s put a core grant in every 100 ms display frame. So the
  car-box color language is: **steady orange = healthy; blue = not served in
  the last 100 ms (starvation); red = emergency** — unlike sim cars, which
  show instantaneous holds and flicker. Hardening committed (`ccadce9`,
  lab repo): on-core/emergency alpha 0.5→0.9, a `[core-latch-v3]` build tag
  in the startup log (stale installs detectable from line 1), runbook rows.
  **Awaiting live confirmation on the next run — check the startup tag.**
  **2026-07-28 (lab, evening): FIRST PHYSICAL CONTACT — hello-world PASSED**
  (wheels swept left-right-center from the Mac; car on a table; speed 0.0
  throughout; Stone ran it). The live host is the Mac running **native
  RoboStack ROS 2** (Docker-on-Mac NAT is unusable for DDS): conda env
  `ros_env` in `~/mamba` + `client_config_mac.xml` (FastDDS whitelist of the
  Mac's tailscale addr — FastDDS skips macOS utun by default) +
  `RMW_IMPLEMENTATION=rmw_fastrtps_cpp` (RoboStack defaults to CycloneDDS,
  which silently ignores discovery-server config). Untracked Mac-local
  helpers in the lab clone: `run_mac.sh` (env wrapper), `hello_car.sh`
  (wheel-wiggle smoke test), `docker-compose.override.yml`; tailnet IPs
  hard-coded (car 100.64.0.22, Mac 100.64.0.24). Nothing on the car was
  changed. Shadow vs real car verified (pacing drift 0.00 s natively);
  found: AMCL is near-silent while parked (adapter may need odom-triggered
  sampling — scoped, unbuilt) and the parked pose read ~3.4 m off the goat
  centerline (map-frame check with Kurt is the REMAINING GATE before any
  live track run, plus the stand watchdog test).
- **This session (2026-06-25/26), committed + pushed:** `--align-offsets FRAC` knob
  (`Simulation.{h,cpp}`, `main.cpp`) + the leg-(A) route-map reframe (PAPER_NOTES,
  HANDOFF §5, BOUND, PREDICTOR §5d, ZONE_TOLERANCE, USAGE) + new **`THEOREM_BRIEF.md`**
  (formal problem statement for Kurt; fleet model = `F_spaced`; strip-able `User note`
  blocks) → commit **`1ff68ed`**, pushed to tempbosch.
- **Then adopted the EE curvature zone map** (`Trajectory.zoneAt(step)` /
  `curvatureDeltaAt`; 4 zones Z0 straight / Z1 slight / Z2 sharp / Z3 lane-change)
  from `tempbosch/main 8fad423` → **`bad422e`**. **Source of truth stays
  paper-generalization; the rest of the EE branch (200k-line data dumps, xlsx, viz
  coloring, CLI) intentionally NOT merged** — only `Trajectory.{cpp,h}` lifted.
- **Built leg-1 of THE PLAN — the A(zone) instrument (§5):**
  - **Phase-1** per-zone breach attribution (`Simulation` buckets frame breaches +
    occupancy by `zoneAt`) → **`47c8832`**. Finding: breach *manifestation* ≠
    *cause* — overshoot lands breaches in straights, so Phase-1 alone misleads
    (PAPER_NOTES 2026-06-26).
  - **Phase-2** causal injection: `--zone-target Z --zone-extra-ms D` adds extra
    netCA delay only while a car is in zone Z → **`2b6ce45`**; + `tools/zone_sweep.py`
    + `zone_tolerance.csv` → **`1158082`**.
  - **Result — causal A(zone), N=1 worst, full lap: A(z3 lane-change)=140 ms
    (binding) ; z0 straight / z2 sharp = 290 ms ; z1 slight = 400 ms.** The
    lane-change is ~2–3× tighter — the route's binding tolerance, by a reproducible
    method. Nuances (PAPER_NOTES 2026-06-26): z1>z0 (straights precede curves ⇒
    spatial propagation); causal (sudden in-zone) is more conservative than uniform
    global (`tolerance_sweep` ~245 ms). `THEOREM_BRIEF §3.2` carries the table.
  - **All zone + leg-4 + leg-2 commits are LOCAL-ONLY (push held by request)** — `git log
    1ff68ed..HEAD` (the last pushed commit). Every step verified byte-identical
    (N=6 90.5/100.5, 0 missed; fidelity 1.490e-08).
- **This session (2026-06-29): built THE PLAN leg 4 — the danger-relative metric**
  (`--danger-tau FRAC`, lateral). Per base tick, counts cars whose delivered age_path ≥
  `τ·A(zone_now)` (`K_age`) **unioned** with state-critical cars (TTPNR<`--tau-crit`) →
  `K`; one run sweeps a fixed τ grid → the `K(τ)` curve. New accessor
  `currentDataAgeOldestTicks` plumbed Scheduler→PolicyScheduler→TaskChainModel (mirrors
  `recentLatchAgeTicks`); A(zone) table hard-coded {z0:290,z1:400,z2:290,z3:140} ms.
  Added ALONGSIDE `--tau-crit` (baselines byte-identical; fidelity 1.490e-08). **Finding
  (§5 leg 4 / PAPER_NOTES 2026-06-29):** the two failure axes are *orthogonal* — RM
  `K_age≈0` but `K=7/12` (unserved/past-PNR, state term); aguard `K=K_age=3/6`, zero
  state-critical (over-budget but recoverable). Neither term alone is sound; the union
  `K ⊇ --tau-crit`. CSV cols `danger_tau,max_k_age,max_k_danger`. Committed `66d0fa2`.
- **This session (2026-06-29) also built THE PLAN leg 2 — the occupancy instrument**
  (`--pack-zone Z` / `--min-spacing MS`, lateral; `tools/occupancy_sweep.py`). Packs the
  binding zone's arcs at the `F_spaced` minimum spacing and measures worst-case
  simultaneous `Occ`; off by default ⇒ byte-identical. **Result (§5 leg 2 / PAPER_NOTES):
  measured `Occ` tracks `ceil(zone_len/spacing)` within +1–2** (z3 = 8.9 % of lap);
  `Occ < N` for realistic spacing (N=18: 1 s gap → 12; 2 s → 7; 4 s → 4), `→ N` stacked.
  The *same* `Occ` is policy-independent yet **fatal under RM / near-safe under aguard**
  at spacing ≥ 500 ms (0 hard with the original packer; ≤ 27 hard under the 2026-07-04
  corrected strictly-F_spaced placements — PROOF_DRAFT §8.6) — the occupancy→schedulability
  link; at full stack (`Occ=N`) even aguard crashes (honest `F_adversarial` degradation). CSV cols
  `pack_zone,min_spacing_ms,max_occ_packed`. Committed `bd6e5e1` (local; push held).
  The Kurt-facing leg-3 brief is `THEOREM_BRIEF §9`, committed `a2b6d6d` (local; push held).
- **This session (2026-07-03): `PROOF_DRAFT.md` (NEW, CANDIDATE/UNVERIFIED; committed + pushed 2026-07-06 on Stone's instruction)** — end-to-end fleet-safety theorem candidate for Kurt: Lemma 1 proven+machine-checked (17,176-case brute force; v10 z3 = **4 arcs**; measured Occ = exact optimum), Lemma 2a audited (limited cross-check PASS as-found & post-patch), Lemma 2b two-band **ZB-F-X** composition machine-instantiated (**N=8 @ s≥4 s certified vs classical 3**; F-demotion is load-bearing); 4-agent council red-team found + same-session-repaired 2 CRITICALs (own-task band carry; wrapped inflated arcs) and flagged the zone-exit/envelope physics gap as top risk (decisive experiment queued in PROOF_DRAFT §6 A1); `rta_solve.py` gained `--band/--band-n/--band-demote-f`, `--workload limited-t`, own-carry, and a sound stopping rule (uniform `full`/`limited` byte-identical, diffed; `verify.sh --full` ALL PASS).
- **This session (2026-07-04): the §5 AI queue EXECUTED** — refined cliffs A(z3) = 170/160/90
  (v10/12.5/15; 10 ms instrument resolution), envelope validated + A-table non-composability
  demonstrated (A1 retired at the operating point), `zband` proof-object scheduler built and
  attacked (no counterexample; 0 missed in-region), A2 quantified (−10 ms cliff), v15 exposed
  as the applicability boundary (90 < 124 uncontended), F-demotion-alone certifies N=8 at the
  refined cliff (occupancy's necessity is now stated as a boundary, PROOF_DRAFT §8.5), pass-2
  spacing fixed (Occ unchanged), `reproduce.py zones|occupancy` added. Full record:
  **PROOF_DRAFT §8**; paper framing: PAPER_NOTES 2026-07-04. New flags: `--zone-extra-vector`,
  `--zone-flag-window`, `--ff-extra-ms`, `--scheduler zband`; new CSVs per §8.6. All
  committed + pushed 2026-07-06 with the 07-03 proof-draft set (Stone's instruction;
  the review-hold that kept the 07-03/07-04 work staged-only is released).
- **This session (2026-07-08): the Guo dossier** (untracked `ContextForGuo/` —
  Stone decided 2026-07-10 it STAYS untracked, like `relatedPapers/`; the
  Guo-facing tex lives on Overleaf). Context: 2026-07-08 meeting with Dr. Guo (notes:
  `ContextForGuo/GuoMeetingDocs.md`) — directives: Overleaf paper package by
  Friday 07-10; paper over reports/posters; rethink zone definitions
  (dynamic/online context); the general time↔safety↔zone relationship; Bosch +
  CARLA as case studies. Deliverable built: **`ContextForGuo/main2.tex`
  rewritten into the single Guo-facing dossier** (Overleaf-ready, self-contained,
  ~2 h read): status-tagged claims ([V]/[M]/[C]/[N]), NO "contract" terminology
  (Stone's call — the three-assumption structure is now "Conditions"
  physics/demand/service), every number re-verified against
  HANDOFF/PROOF_DRAFT §8/BOUND/DATA_AGE/GENERALIZATION, reproduce commands
  embedded (incl. the §8.2 verbatim envelope run), the EE thermal analytic
  companion condensed in (as [C] draft), meeting directives as explicitly
  not-built future work, timeline appendix from git history, glossary.
  `ContextForGuo/GUO_OVERVIEW_DRAFT.md` marked SUPERSEDED (folded in; kept for
  reference). `physics_informed_draft.pdf` (EE+AI contract-based note,
  2026-07-07) remains the thermal section's source. No code changes; verify.sh
  fast gate re-run green (G1+G2, fidelity 1.490e-08).
- **Sessions 2026-07-09/10: dossier review + learning aids (no repo code changes).**
  Lead's Overleaf revision of `main2.tex` reviewed against the repo (the 5
  recommended edits verified landed; errata list returned to Stone for
  manual fixes — truncated §3.3 sentence, proposal-tense abstract, over-trimmed
  §2.2 age conventions, dropped fidelity-gate sentence, TTPNR typo). Built four
  claude.ai learning artifacts for Stone (visual §6 walkthrough / defense
  Q&A drill / printable cheat sheet / tick-level schedule animator); the
  animator's JS engine is a port of `TaskModel.cpp`+rm/zband **validated
  against `./build/cps` goldens** (rm N=1/6/8/11 + zband N=4/8: 30 per-vehicle
  age pairs + missed counts, exact) — which is how Finding D (§4: zone_probe
  rotated arc starts) surfaced. Fix deliberately deferred to its own session
  (recipe in §4 D).
- **Session 2026-07-17 (b): Finding D fixed — `zone_probe.cpp` arc-start
  rotation (code + proofcheck + docs).** De-rotated `zone_probe.cpp` (records
  true run starts; anchors the merged wrap-arc at its real position) and
  `lemma1_check.py::PROFILES` (all three profiles' true starts). Re-verified by
  diffing `lemma1_check` output old-vs-new: every occupancy value identical
  (rotation invariance, as predicted); the one position-keyed change is a
  strengthening — check [3]'s F_spaced diagnostic went spurious-VIOLATED →
  genuine-OK, confirming the committed `occupancy_sweep.csv` rows come from
  properly F_spaced placements. PROOF_DRAFT §0 erratum + check-[3] note landed.
  Full record: §4 D (RESOLVED); PAPER_NOTES 2026-07-17. No run/CSV/theorem
  number changed; K/L/lap unchanged.
- **Session 2026-07-17 (a): Dr. Guo's dossier response received — plan of record
  reprioritized (docs only).** Positioning vs Sudvarg advisor-confirmed (their
  lever = sampling periods from physical state; ours = tolerable data age under
  shared multicore contention; the three-condition decoupling endorsed as
  "highly sellable" — near-verbatim intro material). The publication gap is
  named: turn [C] into [V] on three legs — Theorem-2 limited-carry-in analytic
  proof, a Condition-I analytic A(zone) under-bound (NEW leg), Lemma-1
  spacing-assumption cleanup. CARLA explicitly descoped; directive to map the
  paper outline with Kurt and assign sections. Full record: PAPER_NOTES
  2026-07-17; actionable plan: §5 "Plan of record (2026-07-17)". Spacing note
  verified against code: vehicles follow pre-recorded velocity/position
  reference traces (`src/trace/Trajectory.h`), so in-sim temporal spacing is
  constant by construction — Guo's spacing concern is a model-validity
  limitation, not a sim gap.
- **Next steps by owner (2026-06-30) — the theorem is now Kurt-gated.**
  *(SUPERSEDED 2026-07-17 by §5 "Plan of record (2026-07-17)" — Guo's response
  re-opened the AI track; this block is kept as record.)* Legs 1, 2, 4 done;
  leg-3 sub-task **2a (limited-carry-in RTA) prototyped** (certified 5→8, cross-check-sound,
  CANDIDATE). The leg-3 brief packet is drafted + current: **`THEOREM_BRIEF §9`**.
  - **Kurt (the theorem — AI cannot own):** Lemma 2a *soundness proof* (the candidate is
    empirical-only) + optional tighter form to close the last gap of 2; Lemma 2b (compose the
    RTA bound vs `A(zone)` under `Occ`); the soft spots (PNR rigor, the `A(zone)` good-entry
    induction + cross-zone carry budget — §9.5); the related-work delta (clears Sudvarg /
    Kundu–Quevedo?).
  - **Stone (not AI, not strictly Kurt):** draft **Lemma 1** (the occupancy geometry —
    a counting argument with the `Occ` curve as backstop; `THEOREM_BRIEF §6` ask #1).
  - **AI (optional, paper-strengthening, NON-BLOCKING — nothing on the critical path):** the
    parked-work block in §5 — v12.5/v15 generalization (highest value; kills the "v10 artifact"
    critique), cross-zone carry measurement (feeds Kurt's §3.2 soft spot), `reproduce.py` +
    sweep `--out` housekeeping.
  - **Nothing AI *must* do before Kurt picks up — the §9 packet is ready to hand him today.**
  Flags added across the legs: `--zone-target`, `--zone-extra-ms`, `--danger-tau`,
  `--pack-zone`, `--min-spacing`; `rta_solve.py --workload limited`.
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
  ~1.49e-08 m). Recording format is v5 (loads v2/v3/v4; v5 adds PlantKind + bounds
  for the cart-pole view — GENERALIZATION §6).
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

**D. (2026-07-10) `zone_probe.cpp` printed arc STARTS rotated by the wrap-merged
tail — RESOLVED 2026-07-17 (commit pending).** Full analysis: PAPER_NOTES
2026-07-10; closing note: PAPER_NOTES 2026-07-17. The circular RLE merge folded
the lap-wrapping run into the front run, then the start-printing loop
re-accumulated positions from 0, so every printed start was late by the tail
run's length (v10 +147,400, v12.5 +119,400, v15 +98,600). **Fix landed:**
`zone_probe.cpp` now records each run's true start and anchors the merged
wrap-arc at the tail run's real position; `lemma1_check.py::PROFILES` updated to
true starts for all three profiles (true v10 z3 arcs **(760800,32000)
(797800,32200) (922200,19400) (1008800,21800)**; v12.5/v15 likewise
de-rotated). **Verified:** `lemma1_check.py` passes with **every occupancy value
identical** across frames (diffed old-vs-new output — rotation invariance
confirmed empirically, as predicted). **One expected position-keyed change, a
strengthening not a regression:** check [3]'s F_spaced min-gap diagnostic moved
from spurious `VIOLATED-by-instrument` (rotated packing) to genuine `OK`
(min-gap = s+1 ≥ s) — the true frame matches how the committed
`occupancy_sweep.csv` was actually generated, so the check [3] bound test now
holds without the `not spaced` waiver at s ≥ 750 ms (PROOF_DRAFT §0 erratum +
check-[3] note). No run/CSV/theorem number changed. K/L/lap unchanged (README
`proofchecks` table still valid).

### Review triage (2026-06-22, ultrareview cloud review of the branch)
The ultrareview surfaced 3 findings:
- **#3 — fidelity gate ran the lateral predictor for cart-pole** (false FAIL):
  FIXED (commit `f4f1699`) — routed through the `Plant` seam and skipped for
  non-lateral plants (the gate is FMU-port-specific). Lateral stays 1.490e-08 m.
- **#2 / Finding A — aguard `--floor` inert:** FIXED (commit `3214880`, above).
- **#1 — visualizer replay bypassed the `Plant` seam** (a cart-pole `.cpsr`
  rendered lateral dynamics + hardcoded 0.8/0.2 m bounds): **RESOLVED 2026-06-23** —
  recording bumped v4→v5 (stores PlantKind + bounds) and a dedicated cart-pole view
  renders the right plant. See the cart-pole-visualizer item in §5.
- **Follow-ups:** (a) proper multi-N `--floor` sweep to re-derive aguard's
  post-fix headline (supports §5 item 4); (b) ~~verify the `Li et al. RTSS'24`
  citation~~ **DONE 2026-07-17** — VERIFIED (+ the Guan RTSS'09 citation): both
  real, correctly attributed, in-scope; Li et al. IS in `relatedPapers/` (the
  `Priority_Optimization_…` PDF, filename hid it), its Δ=kψ handle is its Lemma
  3. Full details: BOUND §5.2/§7.4, PAPER_NOTES 2026-07-17 (citation-check).

## 5. Prioritized next steps

Reframed (post-Guo 2026-06-18) around the main-track generalization paper:

### Plan of record (2026-07-17) — Guo's C→V hardening directives

Guo's response to the dossier (full record: PAPER_NOTES 2026-07-17) supersedes
the "all AI-ownable legs are done; the critical path is only Kurt's" frame:
two of his three hardening legs have large AI-ownable fractions and one
(Condition I) is new work. Positioning is blessed; CARLA is descoped — nothing
pulls toward new engineering. The bar: tighten the math on the existing setup.

**AI track (in order):**
1. **Finding D fix** (§4 D recipe) — **DONE 2026-07-17** (commit pending):
   `zone_probe.cpp` + `lemma1_check.py::PROFILES` de-rotated to true starts;
   `lemma1_check` passes with all occupancy values identical across frames;
   check [3] F_spaced diagnostic strengthened (spurious VIOLATED → genuine OK);
   PROOF_DRAFT §0 erratum landed. See §4 D (RESOLVED) + PAPER_NOTES 2026-07-17.
2. **Lemma-1 spacing cleanup (Guo 2c) — DONE 2026-07-17** (commit pending).
   Buffer model `s_eff = s_nominal − Δ` added to the theorem/`F_spaced`/A3;
   `lemma1_check.py` check [5] machine-checks Occ⁺ monotone in `s` + the
   compression-tolerance table. **Verified result:** the `s ≥ 4 s`
   certification absorbs ≈ 500 ms compression for free (Occ⁺=4 down to
   s_eff=3.5 s), breaks at Δ=1 s (Occ⁺=5); to tolerate Δ, run
   `s_nominal ≥ 3.5 s + Δ`. Deriving Δ from a longitudinal model = the A3
   coupling, left as future work. PROOF_DRAFT §4 + A3, THEOREM_BRIEF §3.5,
   ZONE_TOLERANCE, proofchecks README, PAPER_NOTES 2026-07-17.
3. **Condition-I analytic A(zone) under-bound (NEW leg, biggest AI value) —
   DEFERRED 2026-07-17: the EE student owns the zone work; wait to merge with
   him before touching A(zone) / zone definitions (do NOT race his changes).**
   When unblocked: derive a conservative held-command error-growth bound per
   zone from the linearized lateral dynamics already in `Predictor.cpp`
   (verbatim FMU-port matrices); machine-check `A_lb(zone) ≤ measured A(zone)`
   for every zone × profile. Pulls in the v12.5/v15 A(zone)/Occ generalization
   (parked item 2 — the validation grid; also EE-coordinated). Output: a
   CANDIDATE derivation note for Kurt (invariant 5). Likely settles the open
   140-vs-170 normative decision (analytic bound = normative floor; measured
   cliff = documented headroom).
4. **Theorem-2 bridge prep (Guo 2a; the proof itself stays Kurt's) — DONE
   2026-07-17** (commit pending). THEOREM_BRIEF **§9.4a** states the candidate in
   standard Guan-RTA-LC (RTSS'09) notation (NC/CI decomposition, m−1 carry-in,
   `limited`/`limited-t` forms); **§9.4b** is the proof-step ledger — steps
   1/3/4/5/7 transfer (5,7 *strengthened* by the discrete/kill-and-hold model),
   the two genuine obligations are #2 (m−1 carry-in count under synchronous
   release) and #6 (non-monotone stopping-rule soundness = Lemma 2a).
   `rta_solve.py` cross-check widened: opt-in `--soundness-grid` verifies
   measured age ≤ candidate bound at every certified N (validated N∈{1,4,6,7,8},
   tightest margin ≈31 ms; no counterexample; certified 8 ≤ empirical 10).
   Default (no grid) path byte-identical ⇒ verify.sh G3 untouched. BOUND §7.4,
   USAGE, PAPER_NOTES 2026-07-17. The *soundness proof* stays Kurt's (invariant
   5). Citation VERIFIED 2026-07-17: Guan, Stigge, Yi, Yu, RTSS 2009, pp.
   387–397 (origin of RTA-LC / m−1 carry-in).
5. **Strawman paper outline + Guo reply draft** (Stone-facing, cheap, before
   the Kurt meeting): sections → evidence status ([V]/[M]/[C]) → proposed
   owner per section.

**Stone:** reply to Guo; schedule the Kurt outline/section-assignment
session (Guo asked explicitly); bring the 140-vs-170 decision there; Lemma-1
drafting stays yours.

**Kurt:** unchanged in substance — Lemma 2a *soundness* — now advisor-endorsed
as THE headline result; receives the item-4 bridge materials.

**Descoped:** CARLA (Guo, explicit); new schedulers; new instruments beyond
the legs above.

### THE PLAN (2026-06-25) — the route-map fleet-safety bound (leg A, sharpened)

Working the simultaneous-criticality worst case this session **reshaped what leg
(A)'s bound is** (full reasoning: PAPER_NOTES 2026-06-25 ×2). The old shape
("physics bounds simultaneous criticality to k < N, compose with an RTA") does NOT
survive: an adversary can put all N cars in worst-case track zones at once
(realistic when the *route* has WC zones spread around it), so k = N and there is no
slack — back to the pessimistic classical assumption.

**New shape: the bound is a FUNCTION of the route's zone map.** The physics re-enters
as the track, not a count cap:

    worst-case demand = (number/extent of worst-case zones on the route)
                        × (cars that fit in each zone's danger window at once),
                        capped at N;
    safe iff m cores can meet each car's A(zone) deadline under that demand.

Slack = the route's non-WC fraction (straightaways tolerate huge staleness). Benign
route → admits many cars; all-WC route (slalom) → degrades gracefully to classical
(honest, not a failure). **The map is the disturbance model** — concrete and
checkable, not abstract "bounded disturbance." Dissolves the 2026-06-21/22
existential risk (unconstrained disturbance ⇒ k = N).

**Critical path (3 legs + a metric fix):**
1. **A(zone) — DONE 2026-06-26 (causal table measured).** Adopted the EE curvature
   zone map (`Trajectory.zoneAt`), built Phase-1 attribution + Phase-2 causal
   injection (`--zone-target`/`--zone-extra-ms`, `tools/zone_sweep.py`). **Causal
   A(zone): z3 lane-change 140 ms (binding) ; z0 straight / z2 sharp 290 ms ; z1
   slight 400 ms** (`zone_tolerance.csv`; THEOREM_BRIEF §3.2). Optional refinements:
   the z1>z0 spatial-propagation nuance, a finer cliff, v12.5/v15 profiles.
2. **Worst-case zone occupancy — DONE 2026-06-29 (`--pack-zone`/`--min-spacing`).** Packs
   the binding zone's arcs at the `F_spaced` minimum spacing and measures worst-case
   simultaneous `Occ` (all-arc greedy placement; the route has several lane-change arcs).
   **Result:** measured `Occ` tracks `ceil(zone_len/spacing)` within +1–2 (z3 = 8.9 % of
   lap), `< N` for realistic spacing (N=18: 1 s gap → 12; 2 s → 7; 4 s → 4), `→ N` stacked.
   The *same* `Occ` is policy-independent yet **fatal under RM / near-safe under aguard**
   at spacing ≥ 500 ms (≤ 27 hard under the corrected 2026-07-04 placements, PROOF_DRAFT §8.6)
   (occupancy→schedulability), degrading honestly to classical at full stack. `tools/occupancy_sweep.py` → `occupancy_sweep.csv`; THEOREM_BRIEF §3.5/§6.1,
   PAPER_NOTES 2026-06-29. Measurement-only; baselines byte-identical.
3. **Schedulability composition** — can m cores meet the A(zone) deadlines of the
   worst-case occupancy (builds on BOUND §7 RTA). **Kurt** (the one leg neither user
   nor AI owns) — **now the only remaining leg. Brief packet drafted: `THEOREM_BRIEF §9`**
   (precise Lemma-2 statement, the Occ+K curve tables, the aguard achievability witness,
   the 151.6>140 crux, and the limited-carry-in RTA re-derivation as the gating sub-task).
   The empirical inputs are ready: the `Occ(s)` curve (leg 2) and the `K(τ)` curve (leg 4).
4. **Danger-relative simultaneity metric — DONE 2026-06-29 (`--danger-tau`).** Per base
   tick, count cars with delivered age_path ≥ `τ·A(zone_now)` (`K_age`) **unioned** with
   state-critical cars (TTPNR<`--tau-crit`) → `K`; one run sweeps a fixed τ grid → the
   one-run `K(τ)` curve; adversarial placement via `--align-offsets`. Replaces the
   TTPNR-under-held gauge that saturates for unstable plants (PAPER_NOTES 2026-06-25
   Finding 3). **Result:** the two failure axes are *orthogonal* — RM `K_age≈0` (served
   cars fresh) but `K=7/14,12/18` (unserved/past-PNR, state term); aguard `K=K_age=3/14,
   6/18`, zero state-critical (over-budget but recoverable). `K ⊇ --tau-crit` by
   construction (the superset check caught an early build that skipped never-actuated
   cars). New accessor `currentDataAgeOldestTicks` plumbed exactly as `recentLatchAgeTicks`;
   A(zone) hard-coded {z0:290,z1:400,z2:290,z3:140} ms (V10, lateral). Measurement-only;
   baselines byte-identical. THEOREM_BRIEF §3.6 / PREDICTOR §5d / PAPER_NOTES 2026-06-29.

Instruments built: `--tau-crit`, `--danger-tau` (leg 4), `--pack-zone`/`--min-spacing`
(leg 2), `--align-offsets`, `--zone-target`/`--zone-extra-ms` (causal A(zone)),
`tools/zone_sweep.py`, `tools/occupancy_sweep.py`, `tools/tolerance_sweep.py`. **All AI-ownable
legs (1, 2, 4) are done + leg-3 sub-task 2a prototyped (`rta_solve.py --workload limited`,
certified 5→8); the critical path is now Kurt's** — Lemma 2a *soundness* (the candidate is
empirical-only) + Lemma 2b: compose the measured `Occ(R, F_spaced)` (leg 2) against the
`A(zone)` deadlines over the BOUND §7 RTA. **Lead's leg (Stone, not AI):** draft **Lemma 1**
(the occupancy geometry — a counting argument with the `Occ` curve as backstop, THEOREM_BRIEF
§6 #1). The `Occ(s)` + `K(τ)` curves are Kurt's empirical inputs. Note
(THEOREM_BRIEF §3.2): the occupancy count, like `K`, ultimately needs **state** (TTPNR) for
the degraded-entry case — the current `Occ` is the clean geometric count (the conservative
worst case for placement); the danger pairing (RM-crashes/aguard-safe) supplies the state side.

### AI execution queue (2026-07-03 — post-PROOF_DRAFT council; **EXECUTED 2026-07-04**)

All items 1–7 ran to a verdict on 2026-07-04 — full results in **PROOF_DRAFT §8** (the
authoritative record); one-line outcomes inline below. Item 8 (paper prose) remains
queued behind Kurt. The follow-up (scheduler-induced ages near the cliff) also ran
to a verdict: **CLOSED — P1-feasible schedules cannot reach the cliff region at all
(≤ 110.5 ms across 1/2-core starvation sweeps); injection is strictly harsher; the
overload damage channel is killed-F/stale-ff, not fb age** (PROOF_DRAFT §8.7 #3).
Two optional hardenings remain queued, deliberately unbuilt: a zband golden G4 row in
verify.sh --full, and a --band-deadlines override in rta_solve (only if the v12.5
composed instance goes in the paper). Open decision (Stone's): normative A(z3) = 140
(conservative, current) vs 170 (refined) — *2026-07-17: likely settled by the
Condition-I analytic under-bound (plan of record, §5 top)*.

Ordered by decision value; each item has a decision rule so the outcome is a verdict,
not just data. Items 2–4 of the old parked block below are absorbed here.

1. **DONE — envelope PASSES (A1 retired at the operating point); full A-table envelope FAILS (budgets non-composable at amplitude). Envelope experiment (A1 — decisive for the theorem).** Extend `--zone-extra-ms`
   to a per-zone vector + a z3 flag-window override (±240 ms, 3-point `zoneAt` check —
   exact since z3 arcs ≥ 1.94 s). Two N=1 full-lap runs: (a) the ZB-F-X *guaranteed*
   envelope (age ≈196.5 non-flagged / ≈137.5 flagged); (b) the full A-table envelope
   (each zone at its own budget — this is also the cross-zone-carry composability
   test, absorbing old parked item 3). **Rule:** (a) zero hard ⇒ A1 retired at the
   operating point; any breach ⇒ PROOF_DRAFT theorem falsified — report loudly.
2. **DONE — cliff = 170 (v10) / 160 (v12.5) / 90 (v15); 10 ms = instrument resolution; reframes the corollary (PROOF_DRAFT §8.5). Refine A(z3) below the 50 ms grid.** The committed cliff is [140.5, 190.5);
   extras 60–90 pin it to ±5 ms (new CSV; committed grid untouched). **Rule:** if the
   true cliff ≥ ~151, the Occ⁺=5 row (141.0) flips to PASS ⇒ admissible spacing drops
   to 3 s and the headline strengthens; update PROOF_DRAFT margins either way.
3. **DONE — zband exists (release-stamped), no counterexample in the certified region; 0 missed vs aguard's ~6k; honest collapse at N=18. `zband` in the harness (the missing Lemma-2b adversary).** Release-stamped bands
   (council constraint: never recompute from current position), E/B/M elevate while
   the car is in z3±240 ms, F always base, key (band, period, vehicle, kind).
   Attack: packed z3 at 4 s/3 s spacing, N=8 — **rule:** `missed=0`, 0 hard, and
   `K_age(τ=1.0)=0` (delivered age never exceeds A(zone_now)) = the theorem's exact
   guarantee; any excursion is a counterexample. Stacked run for honest degradation.
4. **DONE — z3 binding everywhere; v15 = applicability boundary (90 < 124 uncontended). v12.5/v15 A(zone) + Occ tables** (old parked item 2; generality leg; geometry
   already probed: K=4/4/3 arcs). **Rule:** z3 stays binding and A scales sensibly ⇒
   the route-family claim (THEOREM_BRIEF §8.2) generalizes; else v10-specific caveat.
5. **DONE — demotion delta costs one 10 ms grid step (cliff 170→160); ≥22 ms margin retained; A2 closed. `--ff-extra-ms` knob (A2 close).** Delay F's publish visibility by D (default 0
   ⇒ byte-identical; F carries no age stamps). Re-run z3 rows at D=16 ms (the ZB-F
   demotion delta). **Rule:** A(z3) unchanged ⇒ A2 closed empirically.
6. **DONE — Occ column unchanged on every row; aguard hard/K columns shifted (s=1.5s: 0→27). Pack-zone pass-2 spacing fix** (instrument honesty; PROOF_DRAFT §1 caveat).
   Enforce spacing vs all placed cars; regenerate `occupancy_sweep.csv`; predict Occ
   column unchanged.
7. **DONE — `reproduce.py zones` / `occupancy` (all profiles + fine grids). Fold zone/occupancy/danger/fine/profile sweeps into `reproduce.py`** (old parked
   item 4; Guo one-command directive).
8. **Paper prose — QUEUED BEHIND KURT, not executing:** no theorem prose until he
   re-derives (invariant #5); the empirical/framework sections can be drafted once
   items 1–4 land.

**Parked AI-ownable work (NON-BLOCKING — none gates Kurt or fixes anything broken; pick up
while leg 3 is with Kurt).** Recorded 2026-06-29; the critical path is Kurt's leg 3.
1. **Limited-carry-in RTA — PROTOTYPED 2026-06-30 (`rta_solve.py --workload limited`).** A
   sound-leaning `m−1` Guan-RTA-LC candidate (`none ≤ limited ≤ full`; UNVERIFIED, cross-check-
   guarded) lifts **certified capacity 5 → 8** (gap to empirical 10 halved), cross-check clean.
   **Key finding:** it does NOT move the `A(z3)=140 ms` crossover (N=4 for both workloads — the
   uncontended chain bound is already 124 ms), so tightening buys *schedulability* not *uniform
   z3-safety* ⇒ occupancy is load-bearing N=4…10 (PAPER_NOTES 2026-06-30; THEOREM_BRIEF §9.4).
   **Remaining (Kurt, invariant #5):** the formula's *soundness* + a tighter form (interference
   cap / exact NC) to close the last gap of 2 — that's his derivation, not our prototype.
2. **Generalize the curves to v12.5 / v15** (most paper value; not Kurt-gated;
   **PROMOTED 2026-07-17** into the Condition-I leg — plan of record, §5 top —
   as its validation grid). The `A(zone)`
   table, `Occ` curve, and danger metric are **v10-only** — `kAZoneMs` is hard-coded
   `{290,400,290,140}` in `Simulation.cpp`. Run `tools/zone_sweep.py` + `tools/occupancy_sweep.py`
   on `--profile 12.5` and `15` for per-profile `A(zone)` + `Occ`; generalize the danger metric's
   table per profile. Answers the open §8.2 route-family decision (THEOREM_BRIEF) + the
   generality leg.
3. **Measure the cross-zone error carry** (honesty-strengthening). Extend Phase-2
   (`--zone-target`/`--zone-extra-ms`): inject delay in zone z−1, measure the degraded-entry
   breach in z, to quantify how much tighter `A(z)` must be for a worst hand-off. Turns the §3.2
   good-entry wrinkle (PAPER_NOTES 2026-06-29) from a flagged assumption into a number; feeds
   Kurt's inductive `A(zone)`-budget argument (THEOREM_BRIEF §6 #3c / §9.5).
4. **Reproducibility housekeeping — DONE 2026-07-17** (commit pending). New
   `tools/danger_sweep.py` (mirrors `occupancy_sweep.py`: `--out`/`--force`,
   parses BOTH stdout K(τ) curves — `[age-only]` K_age and `[+state]` K — into
   `danger_sweep.csv`; v10-only since the A(zone) table is v10-hardcoded).
   `reproduce.py danger` delegates to it (registered; `--quick` isolates to
   `.reproduce_quick/`; regenerates the committed CSV byte-identical).
   `danger_sweep.csv` committed. THEOREM_BRIEF §9.2c/§9.6, USAGE updated.
   (`occupancy_sweep`/`zones` were already folded in on 2026-07-04.)
5. **Sweep-tool safety — DONE (2026-07-02, `harness-readiness`).** `zone_sweep.py` /
   `occupancy_sweep.py` now take `--out` and refuse to overwrite an existing file without
   `--force`; `reproduce.py --quick` writes to git-ignored `./.reproduce_quick/` so smoke
   data can't clobber committed baselines (a full `reproduce.py` still regenerates them — G4).
   See USAGE §Reproducing.

The items below (0–6) are retained as recorded state; this PLAN supersedes the
"simultaneity ≤ k" framing in the existential-gate block and reprioritizes around
the route-map bound.

**DONE 2026-06-23 — cart-pole visualizer (was the active task).** A dedicated
cart-pole view now renders inside the same app, keyed on `PlantKind` read from the
recording (no fork): a cart on a rail + a pole hinged at θ, ±`thetaSoft` (0.05) /
±`thetaHard` (0.21) bound rays (the lane-ring analogue), the held-command prediction
in **angle space** (a held-θ tip trajectory + **ghost poles** at the predicted TTV
and PNR angles + the shared rescue-sweep branch, all from the plant-agnostic
`Prediction`), a θ-vs-time strip with shove bands, and a fleet row of per-vehicle θ ticks. Live +
replay + select/speed/screenshot reused unchanged. The prediction-overlay logic is
**single-sourced** with the car (`drawPredictionOverlay` in `Visualizer.cpp`,
parameterized by the plant's (soft,hard) bounds) so the two views can't drift.
- **Recording bumped v4→v5** (`RunRecording.plantKind` + `hard/softBoundVal`; frame
  layout unchanged; v2/v3/v4 still replay). Old cart-pole `.cpsr` predate the tag, so
  they load as Lateral and render as the car — the prior behavior, no crash.
- **Replay** re-rolls the cart-pole's own `predictHeld` (`currentPrediction()`,
  state from the frame, absolute step = frameIdx×decimation for the shove schedule);
  **live** reads `sim_->prediction`. **Caveat:** the replay overlay uses default
  `uMax`/`shoveForce` (not serialized — like the car's delta-max default); θ bounds
  *are* serialized, so `--theta-max` replays correctly. Exact for default-params runs.
  The cyan **rescue sweep** is car-only today: `CartPolePlant::predictHeld` emits the
  rescue-clearance *scalar* (HUD "rescue margin") but not the trajectory, so the
  shared sweep branch draws nothing — emitting it is a small *plant-side* follow-up
  (beyond this viz-only task). Ghost poles + held trajectory are the cart-pole hero.
- **Verified:** §6 baselines byte-identical (gate 1.490e-08; lateral 90.5/100.5, 0
  missed); car view unregressed; cart-pole replay + live correct vs recorded
  θ/ttv/ttpnr; old v4 still replays. Files: `Visualizer.{h,cpp}`, `Recording.{h,cpp}`,
  `Simulation.cpp` (stamps plantKind+bounds in `start()`). **Resolves review-nit #1.**
  (GENERALIZATION §6, PREDICTOR §4.) *Committed `949d436`, pushed to `tempbosch`.*

**Existential gate — DONE (survey complete 2026-06-22; full map + citations:
`PAPER_NOTES.md` 2026-06-22).** Outcome: the thesis isn't novel (Wilson F1Tenth
RTAS'25 + MEMOCODE'24 own "derive timing from physics"); **(B)** age-tolerance
~1/λ is **established prior** (Sudvarg RTAS'25 *proves* it via CBF+SOS; AoI-control
[Etcibasi'26: cost ~`E[a^{2Δ}]`] + MATI/delay-margin restate it) → demote to
background; **(C)** folds into (A); **(A)** is the **only surviving leg** — *bound
from the physics how many of N loops are simultaneously within reaction-time of
their PNR (≤ k), compose with a multicore RTA ⇒ m cores keep all N safe, admitting
more loops than an "all-critical-at-once" test.* **→ SHARPENED 2026-06-25 (see "THE PLAN" above + PAPER_NOTES): this "k < N" shape does NOT survive (adversary ⇒ k = N); the bound is instead a FUNCTION of the route's zone map. The map is the disturbance model.** **Must-cite that was MISSING from
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
bash .claude/verify.sh                  # fast gate: G1+G2 vs golden (~5s); add --full for G3 (RTA)
python3 tools/reproduce.py              # regenerate ALL scheduling CSVs + print tables (one command)
python3 tools/reproduce.py --list       # experiments (capacity/simcrit/honest/floor/tolerance/zones/occupancy) + which doc table each backs
./build/cps --headless --vehicles 14 --scheduler aguard --exec worst --duration 30
# the tournament (read hard / worst soft% / min_pnr per row):
for s in rm context ttu aguard; do ./build/cps --headless --vehicles 14 --scheduler $s --exec worst --duration 30; done
./build/cps --headless --vehicles 1 --scheduler rm --exec worst --duration 120 --validate-predictor  # trust anchor
./build/cps --headless --vehicles 14 --scheduler ttu --exec worst --duration 60 --save ttu14.cpsr
./build/cps --replay ttu14.cpsr --speed 16     # press ] to cycle cars; watch the error strip
```
Flags: `--scheduler rm|prm|edf|context|honest|ttu|hybrid|aguard|zband` (zband = the
PROOF_DRAFT §3.1 proof-object ZB-F-X; USAGE has the one-paragraph spec), `--zone-extra-vector A,B,C,D`/`--zone-flag-window MS` (envelope experiment, PROOF_DRAFT §8.2), `--ff-extra-ms D` (A2, §8.3), `--vehicles
N`, `--cores N`, `--profile 10|12.5|15`, `--duration SEC`, `--exec
avg|worst|best|pert`, `--overrun kill|skip`, `--guard MS` (hybrid), `--floor MS`
(aguard), `--tau-crit MS` (sim-criticality, §5 item 0 / PREDICTOR §5d), `--danger-tau FRAC` (danger-relative criticality, lateral; delivered age vs `τ·A(zone)` ∪ state; §5 leg 4 / PREDICTOR §5d / PAPER_NOTES 2026-06-29), `--pack-zone Z`/`--min-spacing MS` (worst-case zone occupancy, lateral; pack zone Z's arcs at the F_spaced gap; §5 leg 2 / THEOREM_BRIEF §3.5 / PAPER_NOTES 2026-06-29), `--align-offsets FRAC` (adversarial car phasing for leg A, 0=spread default..1=all aligned; PAPER_NOTES 2026-06-25), `--pred-staleness MS`/`--pred-margin MS` (honest predictor, §5 item 3 / PREDICTOR §5e), `--triage`, `--delta-max RAD`, `--u-max N`/`--shove-force N`/`--theta-max RAD` (cartpole calibration, GENERALIZATION §4), `--net-delay MS`, `--validate-predictor`,
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
- `src/viz/Visualizer.cpp` — `drawPredictionOverlay` (shared car+cart-pole overlay
  walker), `drawCarScene`/`drawCartPoleScene` (plant-keyed views on `rec.plantKind`),
  `drawCartPolePrediction` (angle-space ghost poles), `currentPrediction` (live cache
  vs replay re-roll). Cart-pole view: GENERALIZATION §6.
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
- **Version serialized formats with back-compat loaders** (recording v2→v3→v4→v5);
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
