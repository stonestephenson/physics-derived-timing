# Physics-derived timing for cloud control

Twenty-one cars on three shared cloud cores instead of ten, by deriving each
control loop's timing requirement from the physics of the car it steers.

A fleet drives a track. Each car's control loop (estimate, control, merge) runs
in a cloud on three shared cores, so most cars spend most of their time waiting,
and the steering command a car applies was computed from sensor data that is
already old. How old that data is when the command lands is the *data age*, and
it is the quantity this project turns on.

The standard real-time approach treats every loop as hard-deadline critical and
admits however many fit. Here that is ten cars.

A car on a straightaway, though, tolerates a much staler command than one
turning into a hairpin, and that tolerance belongs to the vehicle dynamics
rather than to the schedule. So we measure it, per route context, and hand the
cloud scheduler a timing requirement that varies with where the car is: let a
loop run stale where the physics allows it, tighten where it does not.
Twenty-one cars then hold the lane on the same three cores.

The work started from Bosch's [Physics-Driven Real-Time CPS
Challenge](ChallengeProposal) (RTAS 2026) and is being written up for RTAS 2027.

![The visualizer running four cars](rescue_overlay.png)

Each car shows the reference path, the path it actually drove, and a dotted
prediction of where it will go under the command it is currently holding. The
ring marks where that prediction crosses the 0.8 m lane bound; the diamond marks
where recovery stops being possible. The strip along the bottom is lateral error
over the run.

## Results

One route profile (Bosch's v10, which ramps between 5 and 10 m/s), 3 cloud
cores, a full 120 s lap, worst-case execution times, default phasing, and every
scheduler restricted to information it could actually observe at runtime.

| scheduler | zero hard breaches | zero hard, and soft <= 5% per car |
|---|---|---|
| rate-monotonic, EDF | 10 | 10 |
| adaptive guard | 19 | 12 |
| frontier | 21 | 13 |

The left column is the safety frame. The right is the challenge's stricter
comfort gate, which costs most of the headroom and is reported here for that
reason. Rate-monotonic breaks at 11 under either, and a serve-everything
argument puts the classical ceiling just above 10, so the baseline is a real
one.

Two caveats belong next to the 21. These records are per-profile objects, and
neither scheduler's v10 tuning transfers to the held-out v12.5 and v15 profiles.
They are also tight: at N=21 the worst lateral error sits 29.8 mm inside the
0.8 m bound, and adaptive guard's N=19 record sits 4.7 mm inside it.

An attribution sweep separates the two levers behind the gain. Allocation triage
on its own reaches 19. The zone-aware feedforward economics on its own reaches
14. Together they reach 21.

Data age itself comes out of the run. A timestamp rides the real trigger events
through both network hops and whatever core contention the run produces, then
gets read off at the actuator, which makes it ground truth for that run and
something an analytical bound can be checked against. Conventions are in
[`DATA_AGE.md`](DATA_AGE.md), the bound in [`BOUND.md`](BOUND.md).

## The same machinery on a second plant

All of this sits behind a small `Plant` interface, so the scheduler, the age
metric and the bound never learn what they are controlling. Case study one is
Bosch's lateral-control vehicle. Case study two is an inverted pendulum on a
cart.

The two respond very differently to the same delivered age, which is what makes
the per-context argument worth making at all. The car degrades gradually, and
its whole-plant tolerance brackets somewhere between 245 and 345 ms, while the
binding figure on its tightest context, a lane change, is 140 ms in the conservative
constant the proof packet is stated against (the measured minimum over the control
chain's phase is 150.5 ms — `HANDOFF.md` "Numbers of record"). The pendulum has almost no gradual
regime. It holds to roughly 110 ms, then falls over inside a window about 5 ms
wide.

```sh
./build/cps --headless --plant cartpole --vehicles 8 --scheduler aguard-honest --exec worst
```

## On hardware

The scheduler has also run outside simulation, with a 1/10-scale car driving a
SLAM-mapped track while its control loop executed in the cloud and competed for
cores against simulated vehicles. That integration lives in a separate lab
repository. It produced the sharpest fixed-priority result we have: under
rate-monotonic the real car never degraded at any fleet size, because it held
the top priority seat. Reseated last, it starves.

## Try it

Needs CMake 3.16 or newer and a C++17 compiler. raylib is fetched and built on
first configure, so the first build wants a network connection. Bosch ships the
vehicle FMU prebuilt for macOS and Windows only, so on Linux the project
compiles and the cart-pole runs but `--plant lateral` cannot load its library.

```sh
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release && cmake --build build -j

./build/cps                                     # live window, one car
./build/cps --vehicles 6 --scheduler aguard     # six cars, age-criticality
./build/cps --headless --vehicles 6 --exec worst --duration 120
```

The recorded capacity numbers use the `-honest` scheduler variants, which
predict from delayed state rather than from ground truth, together with
`--exec worst`. Plain `aguard` is the oracle variant and `--exec` defaults to
average, so the quickstart commands above will not reproduce the table. Full
flags and the scheduler list are in [`USAGE.md`](USAGE.md).

## Reproducing the numbers

Every figure above traces to a committed CSV, and `tools/reproduce.py`
regenerates them. Name the experiments you want; the no-argument form pulls in a
battery leg that runs about two and a half hours. For a quick check instead,
`.claude/verify.sh` re-runs one recorded baseline plus the predictor fidelity
gate, which holds the ported plant model to 1.5e-08 m of divergence across a
120 s run.

## Repository tour

| where | what |
|---|---|
| `src/sched/` | the scheduler and its policies, one file per policy |
| `src/sim/` | the `Plant` interface, both plants, the predictor |
| `tools/` | sweep drivers, the response-time solver, reproduction |
| [`DATA_AGE.md`](DATA_AGE.md) | what data age means here and how it is tracked |
| [`BOUND.md`](BOUND.md) | the analytical bound and the response-time analysis |
| [`PREDICTOR.md`](PREDICTOR.md) | time-to-violation and point-of-no-return |
\1| [`CLAUDE.md`](CLAUDE.md) / [`HANDOFF.md`](HANDOFF.md) | where AI agents start; the current state and the canonical numbers-of-record table |\n| [`USAGE.md`](USAGE.md) | build, run, flags, adding a scheduler |

Current work is on the `paper-generalization` branch, which is well ahead of
`main`. `GENERALIZATION.md`, `FCHANNEL.md` and the proof drafts live there.

## Status

Active research, and the claims sit at different levels of confidence. The
capacity and tolerance numbers are empirical and reproducible, but they are
records on one route profile at one phasing, with millimeters of margin, under
the zero-hard-breach frame, and they do not transfer to the held-out profiles.
The analytical bound is a draft. The composed fleet-safety theorem is a
candidate awaiting sign-off from someone who does proofs for a living. Anything
the docs mark unverified is genuinely unverified.

## Credits

Research project in Dr. Guo's lab, built by the two of us. The simulator, the
data-age instrumentation, the predictor and the schedulers are the CS side; the
zone-tolerance and control work is the EE side. The formal proof work belongs to
our PhD mentor.

The `LateralMotionControl` FMU in this repository is Bosch's, distributed with
their challenge and used here as a prebuilt black box, never modified and only
observed from outside. Its documentation is
[`LateralMotionControl/FMU_README.md`](LateralMotionControl/FMU_README.md) and
it carries Bosch's copyright. Everything else is ours. Both are AGPL-3.0, per
[`LICENSE.txt`](LICENSE.txt).
