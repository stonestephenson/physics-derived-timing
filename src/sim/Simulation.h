// Simulation.h — the co-simulation master. Owns the FMU instances and the
// scheduler, drives the whole system one base tick (0.1 ms) at a time, and
// records decimated frames for the visualizer / metrics.
//
// step() advances exactly one tick, so the visualizer can drive it live by
// calling step() many times per rendered frame; runToCompletion() loops it for
// a headless run.
#pragma once

#include <cstdint>
#include <memory>
#include <vector>

#include "fmu/Fmu.h"
#include "sched/Scheduler.h"
#include "sched/TaskModel.h"
#include "sim/Predictor.h"
#include "sim/Recording.h"
#include "sim/Vehicle.h"
#include "trace/Trajectory.h"

namespace cps {

struct SimParams {
    Profile  profile       = Profile::V10;
    PlantKind plant        = PlantKind::Lateral;  // which controlled system
    int      nVehicles     = 1;
    int      nCores        = 3;
    long     durationSteps = 0;   // 0 -> one full lap of the chosen profile
    int      decimation    = 100; // record one frame per N ticks (100 == 10 ms)
    std::vector<long> startOffsets;  // empty -> spread vehicles evenly around lap
    // Adversarial disturbance-alignment knob for the simultaneous-criticality
    // experiment (leg A): scales the even auto-spread of start offsets toward a
    // common phase. 0 = full even spread (default; anti-aligned, byte-identical
    // to the historical baseline); 1 = all vehicles on the same lap phase, so
    // every car hits the same curve at the same time (maximally aligned). Only
    // applied when startOffsets is not given explicitly. Ignored by cart-pole
    // (its shove is already a global-phase disturbance).
    double   alignOffsets  = 0.0;
    // Phase-2 causal A(zone) (ZONE_TOLERANCE): inject extra netCA command delay
    // only while a vehicle is in curvature zone `zoneTarget` (0..3); -1 = off.
    // `zoneExtraMs` is the extra delay (ms). Isolates a zone's causal tolerance
    // (lateral only). Off -> baselines byte-identical.
    int      zoneTarget    = -1;
    double   zoneExtraMs   = 0.0;
    // Envelope experiment (PROOF_DRAFT §6 A1 / HANDOFF §5 queue #1): per-zone
    // extra netCA delay vector {z0,z1,z2,z3} in ms, applied by the vehicle's
    // CURRENT zone every tick (lateral only; empty = off -> byte-identical).
    // Takes precedence over zoneTarget/zoneExtraMs when non-empty.
    // `zoneFlagWindowMs` > 0 emulates the ZB-F-X flag: whenever the car is
    // within +/-window of a z3 arc (3-point zoneAt check, exact because z3
    // arcs are >= 1.94 s >> window), the z3 entry is used instead.
    std::vector<double> zoneExtraVecMs;
    double   zoneFlagWindowMs = 0.0;
    // A2 experiment: delay every Feedforward publish by this (ms); 0 = off.
    double   ffExtraMs     = 0.0;
    // FCHANNEL A_F instrument (--fzone-target/--fzone-hold-ms): while the
    // vehicle is in zone fzoneTarget (0..3; -1 = all zones when hold > 0), F
    // publishes are suppressed until the published value's activation age
    // reaches fzoneHoldMs (two-part dose: k full F periods by suppression +
    // sub-period remainder via the delayed-publish path). Lateral only; 0 =
    // off -> byte-identical. See FCHANNEL.md §4.
    int      fzoneTarget   = -2;   // -2 = off; -1 = all zones; 0..3 = one zone
    double   fzoneHoldMs   = 0.0;
    // FCHANNEL A_B instrument: same, for Controller (B) publishes.
    int      bzoneTarget   = -2;
    double   bzoneHoldMs   = 0.0;
    // FCHANNEL collapse experiment (--qzone-target/--qzone-eps): add eps to
    // the reference curvature input ff0 (hence to q = kappa + 0.2*dkappa/ds)
    // while the vehicle is in the target zone — a zero-age reference ERROR
    // (Reviewer B's Factor A). Lateral only; 0 = off -> byte-identical.
    int      qzoneTarget   = -2;
    double   qzoneEps      = 0.0;
    // FCHANNEL capacity-distribution battery (--offset-seed): when > 0 and
    // startOffsets/packZone are not in play, draw each vehicle's start offset
    // uniformly in [0, lapSteps) from this seed instead of the deterministic
    // spread — the phasing-randomization axis (council A-R3). 0 = off.
    uint64_t offsetSeed    = 0;
    ExecMode execMode      = ExecMode::Average;
    OverrunPolicy overrun  = OverrunPolicy::KillAndHold;
    // If >= 0, override BOTH network delays with this fixed value (ms),
    // regardless of execMode (which then governs task execution times only).
    // For the zone-tolerance delay sweeps (ZONE_TOLERANCE.md).
    double   netDelayMs    = -1.0;
    // Predictor fidelity gate (lateral / FMU-port only): at every actuator
    // latch, predict e_y over the upcoming hold with the ported plant model and
    // compare against the FMU's realized e_y. Prints max |deviation| at the end
    // (PASS < 1e-6 m). Skipped for other plants, whose predictor shares the
    // plant's own integrator (nothing to validate against a black box).
    bool     validatePredictor = false;
    // Assumed steering limit for recoverability predictions (rad);
    // <= 0 uses the calibrated per-profile default (defaultDeltaMax).
    double   deltaMax      = -1.0;
    // Cart-pole control-parameter overrides (--u-max N / --shove-force N /
    // --theta-max RAD); < 0 keeps the calibrated CartPoleParams default. uMax is
    // the cart-pole's delta_max analogue (actuator force limit + recovery
    // authority). Ignored by the lateral plant.
    double   cpUMax        = -1.0;
    double   cpShoveForce  = -1.0;
    double   cpThetaHard   = -1.0;
    // TimeToUnsafe policy behavior for past-PNR cars: false (default) =
    // maximum urgency (never give up); true = triage (drop to lowest).
    bool     triage        = false;
    uint64_t seed          = 0;
    // Simultaneous-criticality threshold (ms): a vehicle is "critical" this tick
    // when its TTPNR < tauCritMs (~ one command round-trip). Set by --tau-crit.
    // Measurement only (no scheduler reads it); see HANDOFF §5 item 0 / PREDICTOR.md.
    double   tauCritMs     = 100.0;
    // Danger-relative criticality primary fraction (THE PLAN leg 4 / THEOREM_BRIEF
    // §3.6): a car is age-critical this tick when its delivered age_path >=
    // dangerTau * A(zone of car now). 1.0 = at the zone's tolerable-age budget.
    // Set by --danger-tau. Measurement only; companion to tauCritMs, never reads
    // back into scheduling. The K(tau) curve always sweeps a fixed grid besides this.
    double   dangerTau     = 1.0;
    // Worst-case zone occupancy instrument (THE PLAN leg 2 / THEOREM_BRIEF §3.5,
    // §6.1): when packZone in [0,3] (lateral, and startOffsets not given), place
    // cars to maximize simultaneous occupancy of that zone at the F_spaced minimum
    // inter-car phase gap minSpacingMs. -1 = off (default spread / --align-offsets,
    // byte-identical). minSpacingMs -> 0 packs tight (F_adversarial, Occ -> N);
    // larger = highway-like (Occ < N). Set by --pack-zone / --min-spacing.
    int      packZone      = -1;
    double   minSpacingMs  = 0.0;
    // Honest predictor (HANDOFF §5 item 3): when set, the predictive policies
    // rank on a SECOND rollout seeded from the cloud's legitimate DELAYED state
    // (the *_est_ms VehicleView twins) instead of true state. Set automatically
    // for the *-honest scheduler names. predStalenessMs = how stale the cloud's
    // freshest sensor data is (one-way sensor delay, bounded); predMarginMs =
    // safety margin subtracted from honest TTPNR (conservatism knob).
    bool     honestPredictor = false;
    double   predStalenessMs = 16.0;   // worst-case sensor->cloud delay (TaskModel.cpp)
    double   predMarginMs    = 0.0;
};

class Simulation {
public:
    Simulation(const SimParams& params, std::unique_ptr<Scheduler> scheduler,
               std::shared_ptr<FmuLibrary> lib = nullptr);

    void start();                 // load trajectory, instantiate FMUs, init scheduler
    bool step();                  // advance one base tick; false once finished
    void runToCompletion(bool verbose = true);

    long   currentStep()   const { return step_; }
    long   durationSteps() const { return durationSteps_; }
    bool   finished()      const { return started_ && step_ >= durationSteps_; }
    double progress()      const { return durationSteps_ ? double(step_) / durationSteps_ : 1.0; }

    const RunRecording&         recording()  const { return rec_; }
    std::shared_ptr<Trajectory> trajectory() const { return traj_; }

    // Latest cached held-command prediction for a vehicle (refreshed every
    // kPredictRefreshTicks; see currentPredTicks for aged TTV/TTPNR values).
    const Prediction& prediction(int vehicle) const { return predCache_[vehicle]; }

private:
    void buildViews();
    void recordFrame(double t);
    void finalizeSummary();

    SimParams                    params_;
    std::unique_ptr<Scheduler>   scheduler_;
    std::shared_ptr<FmuLibrary>  lib_;
    std::shared_ptr<Trajectory>  traj_;
    std::vector<Vehicle>         vehicles_;
    std::vector<long>            offsets_;
    std::vector<VehicleView>     views_;
    std::vector<VehicleTriggers> triggers_;
    RunRecording                 rec_;

    double dt_            = 1e-4;
    long   step_          = 0;
    long   durationSteps_ = 0;
    bool   started_       = false;
    bool   finalized_     = false;

    std::vector<double> maxRolling_;
    std::vector<int>    hardCount_;
    // Per-zone breach attribution for leg (A) / Phase-1 A(zone) (lateral only;
    // zones are a track concept). Frame-decimated, fleet-aggregated over vehicles.
    long                zoneHard_[4] = {0, 0, 0, 0};
    long                zoneSoft_[4] = {0, 0, 0, 0};
    long                zoneFrames_[4] = {0, 0, 0, 0};  // frames spent in each zone
    // FCHANNEL margins + F-age reporting (council A-M9/C-O7/C-O8). All
    // per-tick (undecimated), measurement-only, always on (passive).
    std::vector<double> maxAbsEy_;              // per-vehicle run-max |e_y_real|
    double              zoneMaxAbsEy_[4] = {0, 0, 0, 0};   // per-zone fleet max
    long                ffStaleZoneMaxTicks_[4] = {0, 0, 0, 0};  // per-zone max F age
    // In-zone tick counts with F staleness over each ladder threshold
    // {100, 200, 500, 1000} ms — exposure-normalized exceedance reporting.
    static constexpr long kFfLadderTicks[4] = {1000, 2000, 5000, 10000};
    long                ffStaleExceed_[4][4] = {{0}};  // [zone][ladder]
    long                ffStaleZoneTicks_[4] = {0, 0, 0, 0};  // in-zone samples

    // --- Held-command prediction cache (drives TTU policy, viz, stats).
    //     TTV + polyline refresh every 10 ms (cheap single rollout); the PNR
    //     binary search (the expensive part) every 50 ms; both age in between. ---
    static constexpr long kPredictRefreshTicks = 100;  // 10 ms, like the metrics
    // PNR every 10 ms too: warm-started searches (PredictParams.
    // warmStartTtpnrTicks) make this affordable; gate is >= 10x at 12 veh.
    static constexpr long kPnrRefreshTicks     = 100;  // 10 ms
    void refreshPredictions(bool withPnr);
    // Aged (ttv, ttpnr) in ticks as of the current step_: cached values minus
    // elapsed ticks, clamped at 0; horizon sentinel passes through unchanged.
    void currentPredTicks(int vehicle, long& ttv, long& ttpnr) const;
    PredictParams           predParams_;
    std::vector<Prediction> predCache_;      // latest TTV + polyline
    std::vector<long>       predBaseStep_;   // step_ at which each cache entry was made
    std::vector<long>       ttpnrTicks_;     // latest PNR result (separate cadence)
    std::vector<long>       ttpnrBaseStep_;
    // --- Honest predictor (params_.honestPredictor): a parallel prediction
    //     seeded from the cloud's delayed state, feeding the *_est_ms view
    //     twins. Mirrors the oracle arrays above; idle when honest is off. ---
    void refreshHonestPredictions(bool withPnr);
    void currentHonestPredTicks(int vehicle, long& ttv, long& ttpnr) const;
    long predStalenessTicks_ = 0;
    std::vector<std::vector<VehicleOutputs>> stateHist_;  // [v][ring], delayed state+cmd
    std::vector<Prediction> predCacheEst_;
    std::vector<long>       predBaseStepEst_;
    std::vector<long>       ttpnrEstTicks_;
    std::vector<long>       ttpnrBaseStepEst_;
    // Predictor compute cost (Finding B): summed wall time + call count across
    // both refreshes -> us/prediction + %-of-one-core. Measurement only.
    double                  predWallSeconds_ = 0.0;
    long                    predCount_       = 0;
    std::vector<double>     minTtpnrMs_;     // run-min of finite aged TTPNR (-1 = none)
    std::vector<long>       pastPnrTicks_;   // ticks spent at aged TTPNR == 0
    // Fleet-wide simultaneous criticality (TTPNR < params_.tauCritMs), sampled
    // every base tick: run-max + dwell-time histogram. Measurement only.
    long                    maxSimCrit_   = 0;
    std::vector<long>       simCritHist_;    // simCritHist_[c] = ticks with exactly c critical
    long                    simCritTicks_ = 0;
    // Danger-relative criticality (THE PLAN leg 4): per base tick, count cars whose
    // delivered age_path has consumed fraction tau of their current zone's A(zone)
    // budget (K_age), and that count unioned with the state-critical (TTPNR<tauCrit)
    // cars (K). Primary tau = params_.dangerTau (full dwell histogram for the
    // over-cores %); *Grid_ track run-max across the fixed K(tau) curve sweep.
    // Lateral only (zones are a track concept). Measurement only.
    long                    maxKAgePrimary_    = 0;
    long                    maxKDangerPrimary_ = 0;
    std::vector<long>       kDangerHist_;    // dwell of K (primary tau): [c] = ticks with c danger
    long                    kDangerTicks_      = 0;
    std::vector<long>       maxKAgeGrid_;     // run-max of K_age at each grid tau
    std::vector<long>       maxKDangerGrid_;  // run-max of K     at each grid tau
    // Worst-case zone occupancy (THE PLAN leg 2): per base tick, count cars in each
    // zone; track run-max simultaneous occupancy. The geometric input to Lemma 1.
    // Lateral only; measurement only. occHist_ = dwell histogram of the packed zone.
    long                    maxOcc_[4]      = {0, 0, 0, 0};
    std::vector<long>       occHist_;        // occHist_[c] = ticks with c cars in packZone
    long                    occTicks_       = 0;
    long                    packZoneArcTicks_ = 0;  // longest contiguous arc of packZone (ticks)

    // Compute startOffsets that pack `zone`'s longest arc at `spacingTicks` (leg 2);
    // also records the longest-arc length into packZoneArcTicks_.
    std::vector<long> packZoneOffsets(int zone, long spacingTicks);

    // --- Predictor fidelity gate state (params_.validatePredictor) ---
    void validatePredictions();
    struct PendingValidation {
        Prediction pred;
        long       madeAtStep = -1;  // pred.e_y[j] = e_y after tick madeAtStep + j
        bool       active     = false;
    };
    std::vector<PendingValidation> pendingVal_;
    double valMaxDev_   = 0.0;
    long   valHolds_    = 0;
    long   valSamples_  = 0;
    double valMaxAct_    = 0.0;  // max |act_out| seen (delta-max calibration aid)
    double valMaxDemand_ = 0.0;  // max |pre-clamp demand| (cart-pole uMax calibration aid)
};

}  // namespace cps
