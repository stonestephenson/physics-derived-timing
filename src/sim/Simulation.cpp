#include "sim/Simulation.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <stdexcept>
#include <string>

#include "fmu/FmuVariables.h"
#include "sim/CartPolePlant.h"
#include "sim/LateralPlant.h"

namespace cps {

namespace {
// Danger-relative criticality (THE PLAN leg 4 / THEOREM_BRIEF §3.6): per-zone
// tolerable data age A(zone) in ms — the causal table (zone_tolerance.csv, V10,
// lateral only; z3 lane-change is binding; the CONSERVATIVE 50 ms-grid values —
// the fine-grid cliff is 170, PROOF_DRAFT §8.1). Indexed by TrackZone
// {z0,z1,z2,z3}. TWIN: tools/rta_solve.py A_ZONE_MS — change both in lockstep
// (and re-tune Trajectory.h's zone partition first if the profile changes).
constexpr double kAZoneMs[4] = {290.0, 400.0, 290.0, 140.0};
// One-run K(tau) curve: fraction-of-budget thresholds swept within a single run,
// so one run yields the whole demand curve (PAPER_NOTES 2026-06-25: a count at one
// tau is a saturated gauge; the curve is the object).
constexpr double kDangerTauGrid[] = {0.25, 0.5, 0.75, 1.0, 1.25, 1.5};
constexpr int    kDangerTauN = 6;
}  // namespace

Simulation::Simulation(const SimParams& params, std::unique_ptr<Scheduler> scheduler,
                       std::shared_ptr<FmuLibrary> lib)
    : params_(params), scheduler_(std::move(scheduler)), lib_(std::move(lib)) {
    dt_ = vr::kBaseStepSeconds;
}

// Leg 2: place cars to maximize simultaneous occupancy of `zone`. The F_spaced
// worst case (THEOREM_BRIEF §3.5: Occ ~ tight-zone length / spacing) packs ALL of the
// zone's arcs -- the route has several lane-change arcs, and cars in different arcs are
// still simultaneously in the zone. We greedily walk the lap and drop a car onto every
// zone tick that is >= spacingTicks past the last placed car (filling all arcs at the
// minimum gap); leftover cars go onto NON-zone ticks (also >= spacing apart) so they do
// not inflate the count. offsets[v] is car v's phase lead (lap-phase = step + offset),
// so the packed set is in-zone at step 0. The per-tick counter measures the realized
// run-max, which (as the rigid formation rotates) is >= the step-0 count -- the truth.
std::vector<long> Simulation::packZoneOffsets(int zone, long spacingTicks) {
    const int  n   = params_.nVehicles;
    const long lap = traj_->lapSteps();
    std::vector<long> offs(static_cast<size_t>(std::max(0, n)), 0);
    if (n <= 0) return offs;
    spacingTicks = std::max<long>(1, spacingTicks);

    long zoneTicks = 0;                       // total length of `zone` over one lap
    for (long i = 0; i < lap; ++i)
        if (static_cast<int>(traj_->zoneAt(i)) == zone) ++zoneTicks;
    packZoneArcTicks_ = zoneTicks;
    if (zoneTicks == 0) {                      // zone absent: fall back to even spread
        for (int v = 0; v < n; ++v) offs[static_cast<size_t>(v)] = v * lap / n;
        return offs;
    }
    // Pass 1: greedily fill zone ticks at >= spacing (packs every arc).
    long placed = 0, sinceZone = spacingTicks;
    for (long i = 0; i < lap && placed < n; ++i) {
        const bool inZone = static_cast<int>(traj_->zoneAt(i)) == zone;
        if (inZone && sinceZone >= spacingTicks) { offs[static_cast<size_t>(placed++)] = i; sinceZone = 0; }
        else ++sinceZone;
    }
    // Pass 2: leftover cars onto non-zone ticks at >= spacing (out of the zone
    // count) -- enforced against ALL already-placed cars, pass-1 included
    // (was pass-2-only: the config could silently violate F_spaced across the
    // passes; PROOF_DRAFT §1 instrument caveat, HANDOFF §5 queue #6).
    auto minCircGap = [&](long i) {
        long best = lap;
        for (long p = 0; p < placed; ++p) {
            const long d = std::labs(i - offs[static_cast<size_t>(p)]);
            best = std::min(best, std::min(d, lap - d));
        }
        return best;
    };
    for (long i = 0; i < lap && placed < n; ++i) {
        const bool inZone = static_cast<int>(traj_->zoneAt(i)) == zone;
        if (!inZone && minCircGap(i) >= spacingTicks)
            offs[static_cast<size_t>(placed++)] = i;
    }
    for (long j = placed; j < n; ++j)         // degenerate overflow: even spread
        offs[static_cast<size_t>(j)] = j * lap / n;
    return offs;
}

void Simulation::start() {
    if (started_) return;

    traj_ = Trajectory::load(params_.profile);
    durationSteps_ =
        params_.durationSteps > 0 ? params_.durationSteps : traj_->lapSteps();
    if (params_.plant == PlantKind::Lateral && !lib_)
        lib_ = std::make_shared<FmuLibrary>();

    const int n = params_.nVehicles;
    offsets_ = params_.startOffsets;
    if (static_cast<int>(offsets_.size()) != n) {
        if (params_.packZone >= 0 && params_.packZone < 4 &&
            params_.plant == PlantKind::Lateral) {
            // Leg 2: zone-aware adversarial-but-spaced placement -- pack the target
            // zone's longest arc at the F_spaced minimum spacing (THE PLAN leg 2).
            const long spacingTicks = std::max<long>(
                1, static_cast<long>(params_.minSpacingMs / (dt_ * 1000.0) + 0.5));
            offsets_ = packZoneOffsets(params_.packZone, spacingTicks);
        } else if (params_.offsetSeed > 0) {
            // FCHANNEL capacity distribution (council A-R3): uniform random
            // phasing draw. Each seed is one independent fleet arrangement;
            // capacity is reported as P(clean) over seeds, not a single draw.
            offsets_.resize(n);
            std::mt19937_64 orng(params_.offsetSeed);
            std::uniform_int_distribution<long> dist(0, traj_->lapSteps() - 1);
            for (int v = 0; v < n; ++v) offsets_[v] = dist(orng);
        } else {
            offsets_.resize(n);
            // alignOffsets scales the even spread toward a common phase: 0 = full
            // spread (anti-aligned, the historical baseline); 1 = all on phase 0
            // (maximally aligned -- the adversarial simultaneity case, leg A). At
            // alignOffsets 0 this is bit-identical to the old v*lapSteps/n spread.
            const double spread = 1.0 - params_.alignOffsets;
            for (int v = 0; v < n; ++v)
                offsets_[v] = static_cast<long>(spread * static_cast<double>(v) *
                                                traj_->lapSteps() / n);
        }
    }

    vehicles_.resize(n);
    std::vector<TaskSet> taskSets(n);
    for (int v = 0; v < n; ++v) {
        Vehicle& veh = vehicles_[v];
        veh.traj = traj_;
        veh.startOffset = offsets_[v];
        veh.taskSet = TaskSet::challengeDefault();
        veh.taskSet.execMode = params_.execMode;
        veh.taskSet.overrun  = params_.overrun;
        veh.taskSet.seed = params_.seed;
        if (params_.netDelayMs >= 0.0) {
            const ExecTimes fixed{params_.netDelayMs, params_.netDelayMs, params_.netDelayMs};
            veh.taskSet.netSC.delay = fixed;
            veh.taskSet.netCA.delay = fixed;
        }
        taskSets[v] = veh.taskSet;

        const double v0 = traj_->inputsAt(offsets_[v]).vel;
        const double stopTime = static_cast<double>(durationSteps_) * dt_;
        if (params_.plant == PlantKind::Lateral) {
            auto p = std::make_unique<LateralPlant>(lib_, "veh" + std::to_string(v));
            p->initialize(0.0, stopTime, v0);
            veh.plant = std::move(p);
        } else {
            CartPoleParams cp;  // calibrated defaults (CartPolePlant.h), overridable
            if (params_.cpUMax       > 0.0) cp.uMax       = params_.cpUMax;
            if (params_.cpShoveForce >= 0.0) cp.shoveForce = params_.cpShoveForce;
            if (params_.cpThetaHard  > 0.0) cp.thetaHard  = params_.cpThetaHard;
            auto p = std::make_unique<CartPolePlant>(cp);
            p->initialize(0.0, stopTime, v0);
            veh.plant = std::move(p);
        }
    }

    SimConfig cfg{n, params_.nCores, dt_};
    cfg.ffExtraTicks = params_.ffExtraMs > 0.0
        ? static_cast<long>(params_.ffExtraMs / (dt_ * 1000.0) + 0.5) : 0;
    scheduler_->init(cfg, taskSets);

    rec_.profile       = static_cast<int>(params_.profile);
    rec_.nVehicles     = n;
    rec_.nCores        = params_.nCores;
    rec_.baseStep      = dt_;
    rec_.durationSteps = durationSteps_;
    rec_.decimation    = params_.decimation;
    rec_.schedulerName = scheduler_->name();
    rec_.startOffsets  = offsets_;
    // v5: tag the recording with the plant + its error-signal bounds so replay
    // renders the right view (car vs cart-pole) with the right thresholds.
    rec_.plantKind     = static_cast<int>(params_.plant);
    rec_.hardBoundVal  = vehicles_[0].plant->hardBound();
    rec_.softBoundVal  = vehicles_[0].plant->softBound();
    rec_.frames.assign(n, {});
    rec_.summary.assign(n, {});

    views_.resize(n);
    triggers_.resize(n);
    maxRolling_.assign(n, 0.0);
    hardCount_.assign(n, 0);
    for (int z = 0; z < 4; ++z) { zoneHard_[z] = 0; zoneSoft_[z] = 0; zoneFrames_[z] = 0; }

    predParams_ = PredictParams{};
    predParams_.deltaMax = params_.deltaMax;  // <= 0 -> calibrated default
    predCache_.assign(n, Prediction{});
    predBaseStep_.assign(n, -1);
    ttpnrTicks_.assign(n, predParams_.horizonTicks);
    ttpnrBaseStep_.assign(n, -1);
    if (params_.honestPredictor) {
        predStalenessTicks_ =
            static_cast<long>(params_.predStalenessMs / 1000.0 / dt_ + 0.5);
        predCacheEst_.assign(n, Prediction{});
        predBaseStepEst_.assign(n, -1);
        ttpnrEstTicks_.assign(n, predParams_.horizonTicks);
        ttpnrBaseStepEst_.assign(n, -1);
        stateHist_.assign(n, std::vector<VehicleOutputs>(
            static_cast<size_t>(predStalenessTicks_) + 1));
    }
    minTtpnrMs_.assign(n, -1.0);
    pastPnrTicks_.assign(n, 0);
    maxSimCrit_ = 0;
    simCritHist_.assign(static_cast<size_t>(n) + 1, 0);
    simCritTicks_ = 0;
    maxKAgePrimary_ = 0;
    maxKDangerPrimary_ = 0;
    kDangerHist_.assign(static_cast<size_t>(n) + 1, 0);
    kDangerTicks_ = 0;
    maxKAgeGrid_.assign(kDangerTauN, 0);
    maxKDangerGrid_.assign(kDangerTauN, 0);
    maxOcc_[0] = maxOcc_[1] = maxOcc_[2] = maxOcc_[3] = 0;
    occHist_.assign(static_cast<size_t>(n) + 1, 0);
    occTicks_ = 0;  // packZoneArcTicks_ already set by packZoneOffsets above (if packing)
    predWallSeconds_ = 0.0;
    predCount_ = 0;

    step_ = 0;
    finalized_ = false;
    started_ = true;
}

void Simulation::refreshPredictions(bool withPnr) {
    PredictParams p = predParams_;
    p.computePnr = withPnr;
    const auto t0 = std::chrono::steady_clock::now();
    for (size_t v = 0; v < vehicles_.size(); ++v) {
        const VehicleOutputs& o = vehicles_[v].out;
        // Warm-start the PNR search from the aged previous answer (skip when
        // the previous answer was "relaxed" — the cheap cap-check handles it).
        p.warmStartTtpnrTicks = -1;
        if (withPnr && ttpnrBaseStep_[v] >= 0 &&
            ttpnrTicks_[v] < predParams_.horizonTicks) {
            p.warmStartTtpnrTicks =
                std::max<long>(0, ttpnrTicks_[v] - (step_ - ttpnrBaseStep_[v]));
        }
        predCache_[v] = vehicles_[v].plant->predictHeld(o, step_ + 1, *traj_,
                                                        offsets_[v], p);
        predBaseStep_[v] = step_;
        if (withPnr) {
            ttpnrTicks_[v] = predCache_[v].ttpnrTicks;
            ttpnrBaseStep_[v] = step_;
        }
    }
    predWallSeconds_ += std::chrono::duration<double>(
        std::chrono::steady_clock::now() - t0).count();
    predCount_ += static_cast<long>(vehicles_.size());
}

void Simulation::refreshHonestPredictions(bool withPnr) {
    PredictParams p = predParams_;
    p.computePnr = withPnr;
    const long S = static_cast<long>(stateHist_[0].size());
    const long srcStep = std::max<long>(0, step_ - predStalenessTicks_);
    const auto t0 = std::chrono::steady_clock::now();
    for (size_t v = 0; v < vehicles_.size(); ++v) {
        // The cloud's legitimate view: this vehicle's state as of its freshest
        // received sensor packet (delayed by predStalenessTicks_), held command
        // included. Same rollout, stale STATE only -- time/reference are current.
        const VehicleOutputs& delayed = stateHist_[v][srcStep % S];
        p.warmStartTtpnrTicks = -1;
        if (withPnr && ttpnrBaseStepEst_[v] >= 0 &&
            ttpnrEstTicks_[v] < predParams_.horizonTicks) {
            p.warmStartTtpnrTicks =
                std::max<long>(0, ttpnrEstTicks_[v] - (step_ - ttpnrBaseStepEst_[v]));
        }
        predCacheEst_[v] = vehicles_[v].plant->predictHeld(delayed, step_ + 1, *traj_,
                                                           offsets_[v], p);
        predBaseStepEst_[v] = step_;
        if (withPnr) {
            ttpnrEstTicks_[v] = predCacheEst_[v].ttpnrTicks;
            ttpnrBaseStepEst_[v] = step_;
        }
    }
    predWallSeconds_ += std::chrono::duration<double>(
        std::chrono::steady_clock::now() - t0).count();
    predCount_ += static_cast<long>(vehicles_.size());
}

void Simulation::currentPredTicks(int v, long& ttv, long& ttpnr) const {
    const long H = predParams_.horizonTicks;
    const size_t i = static_cast<size_t>(v);
    if (predBaseStep_[i] < 0) {
        ttv = H;
    } else {
        const long e = step_ - predBaseStep_[i];
        ttv = predCache_[i].ttvTicks >= H ? H : std::max<long>(0, predCache_[i].ttvTicks - e);
    }
    if (ttpnrBaseStep_[i] < 0) {
        ttpnr = H;
    } else {
        const long e = step_ - ttpnrBaseStep_[i];
        ttpnr = ttpnrTicks_[i] >= H ? H : std::max<long>(0, ttpnrTicks_[i] - e);
    }
    // TTPNR can never exceed TTV (PNR precedes the violation).
    if (ttpnr > ttv) ttpnr = ttv;
}

void Simulation::currentHonestPredTicks(int v, long& ttv, long& ttpnr) const {
    const long H = predParams_.horizonTicks;
    const size_t i = static_cast<size_t>(v);
    if (predBaseStepEst_[i] < 0) {
        ttv = H;
    } else {
        const long e = step_ - predBaseStepEst_[i];
        ttv = predCacheEst_[i].ttvTicks >= H ? H
            : std::max<long>(0, predCacheEst_[i].ttvTicks - e);
    }
    if (ttpnrBaseStepEst_[i] < 0) {
        ttpnr = H;
    } else {
        const long e = step_ - ttpnrBaseStepEst_[i];
        ttpnr = ttpnrEstTicks_[i] >= H ? H : std::max<long>(0, ttpnrEstTicks_[i] - e);
    }
    if (ttpnr > ttv) ttpnr = ttv;
}

void Simulation::buildViews() {
    for (size_t v = 0; v < vehicles_.size(); ++v) {
        const VehicleOutputs& o = vehicles_[v].out;
        long ttv, ttpnr;
        currentPredTicks(static_cast<int>(v), ttv, ttpnr);
        const long recent = scheduler_->recentLatchAgeTicks(static_cast<int>(v), step_);
        views_[v] = VehicleView{static_cast<int>(v), vehicles_[v].curVel,
                                o.e_y_real, o.e_y_est, o.rolling_real, o.rolling_remote,
                                o.average_real, o.threshold_cntr_real,
                                o.critical_real, o.violated_real,
                                o.critical_remote, o.violated_remote,
                                ttv * dt_ * 1000.0, ttpnr * dt_ * 1000.0,
                                predCache_[v].rescueClearanceM,
                                recent < 0 ? -1.0 : recent * dt_ * 1000.0};
        // ZoneBand flag (PROOF_DRAFT §3.1): within ±θ (2400 ticks = 240 ms) of a
        // z3 arc. 3-point check is exact (every z3 arc ≥ 19,400 ticks > 2θ).
        // Lateral only; unread unless --scheduler zband. θ lives ONLY here
        // (kZbFlagTicks — no CLI knob; PROOF_DRAFT §3.2's 2,600-tick inflation
        // constant is derived from it, zero slack: retune both together).
        // Near-twin logic: the envelope instrument's parameterized window
        // below — kept separate deliberately (constexpr vs CLI-driven).
        if (params_.plant == PlantKind::Lateral) {
            constexpr long kZbFlagTicks = 2400;
            const long pos = step_ + offsets_[v];
            const auto& tj = *vehicles_[v].traj;
            views_[v].zone_flagged =
                static_cast<int>(tj.zoneAt(pos)) == 3 ||
                static_cast<int>(tj.zoneAt(pos - kZbFlagTicks)) == 3 ||
                static_cast<int>(tj.zoneAt(pos + kZbFlagTicks)) == 3;
        }
        // Phase-2: inject extra netCA delay while this vehicle is in the target zone.
        // Envelope variant (per-zone vector + ZB-F-X flag window) takes precedence.
        if (params_.zoneExtraVecMs.size() == 4 &&
            params_.plant == PlantKind::Lateral) {
            const long pos = step_ + offsets_[v];
            int z = static_cast<int>(vehicles_[v].traj->zoneAt(pos));
            if (params_.zoneFlagWindowMs > 0.0) {
                const long w =
                    static_cast<long>(params_.zoneFlagWindowMs / (dt_ * 1000.0) + 0.5);
                // Flagged iff within +/-w of a z3 arc. The 3-point check is exact:
                // any z3 arc intersecting [pos-w, pos+w] contains one of the three
                // sample points, since every z3 arc is longer than 2w.
                if (static_cast<int>(vehicles_[v].traj->zoneAt(pos - w)) == 3 ||
                    static_cast<int>(vehicles_[v].traj->zoneAt(pos + w)) == 3 || z == 3)
                    z = 3;
            }
            const double ms = params_.zoneExtraVecMs[static_cast<size_t>(z)];
            views_[v].extra_net_delay_ticks =
                ms > 0.0 ? static_cast<long>(ms / (dt_ * 1000.0) + 0.5) : 0;
        } else {
            views_[v].extra_net_delay_ticks =
                (params_.zoneTarget >= 0 && params_.zoneExtraMs > 0.0 &&
                 params_.plant == PlantKind::Lateral &&
                 static_cast<int>(vehicles_[v].traj->zoneAt(step_ + offsets_[v])) ==
                     params_.zoneTarget)
                    ? static_cast<long>(params_.zoneExtraMs / (dt_ * 1000.0) + 0.5)
                    : 0;
        }
        // FCHANNEL A_F/A_B doses: zone-gated publish suppression (0 = off).
        // fzoneTarget/bzoneTarget -1 = every zone; 0..3 = that zone only.
        views_[v].fz_hold_ticks = 0;
        views_[v].fz_delta_ticks = 0;
        views_[v].bz_hold_ticks = 0;
        if (params_.plant == PlantKind::Lateral &&
            (params_.fzoneHoldMs > 0.0 || params_.bzoneHoldMs > 0.0)) {
            const int z = static_cast<int>(
                vehicles_[v].traj->zoneAt(step_ + offsets_[v]));
            if (params_.fzoneHoldMs > 0.0 &&
                (params_.fzoneTarget == -1 || params_.fzoneTarget == z)) {
                const long holdTicks =
                    static_cast<long>(params_.fzoneHoldMs / (dt_ * 1000.0) + 0.5);
                const long fPeriod = 200;  // F period in ticks (20 ms)
                views_[v].fz_hold_ticks  = (holdTicks / fPeriod) * fPeriod;
                views_[v].fz_delta_ticks = holdTicks % fPeriod;
                if (views_[v].fz_hold_ticks == 0)  // sub-period dose: delta only
                    views_[v].fz_hold_ticks = 1;   // active marker (age >= 1 tick always true)
            }
            if (params_.bzoneHoldMs > 0.0 &&
                (params_.bzoneTarget == -1 || params_.bzoneTarget == z))
                views_[v].bz_hold_ticks =
                    static_cast<long>(params_.bzoneHoldMs / (dt_ * 1000.0) + 0.5);
        }
        if (params_.honestPredictor) {
            long ttvE, ttpnrE;
            currentHonestPredTicks(static_cast<int>(v), ttvE, ttpnrE);
            const double ttpnrEms = ttpnrE * dt_ * 1000.0 - params_.predMarginMs;
            views_[v].ttpnr_est_ms = ttpnrEms < 0.0 ? 0.0 : ttpnrEms;
            views_[v].ttv_est_ms   = ttvE * dt_ * 1000.0;
            views_[v].rescue_clearance_est_m = predCacheEst_[v].rescueClearanceM;
        }
    }
}

bool Simulation::step() {
    if (!started_) start();
    if (step_ >= durationSteps_) {
        finalizeSummary();
        return false;
    }
    const double t = static_cast<double>(step_) * dt_;

    // 1. Apply this tick's reference inputs and snapshot the latest state.
    for (size_t v = 0; v < vehicles_.size(); ++v) {
        Trajectory::Inputs in = vehicles_[v].traj->inputsAt(step_ + offsets_[v]);
        vehicles_[v].curVel = in.vel;
        // FCHANNEL collapse experiment (Reviewer B Factor A): zero-age
        // reference ERROR — eps added to the curvature input ff0 adds eps to
        // q = kappa + 0.2*dkappa/ds, the exact scalar plant and estimator
        // consume. Zone-gated; 0 = off -> byte-identical.
        if (params_.qzoneEps != 0.0 && params_.plant == PlantKind::Lateral &&
            (params_.qzoneTarget == -1 ||
             static_cast<int>(vehicles_[v].traj->zoneAt(step_ + offsets_[v])) ==
                 params_.qzoneTarget))
            in.ff0 += params_.qzoneEps;
        vehicles_[v].plant->setInputs(in.ff0, in.ff1, in.vel);
    }
    buildViews();

    // 2. Scheduler decides the triggers for every vehicle.
    scheduler_->onTick(t, step_, views_, triggers_);

    // 3. Apply triggers, advance the FMUs, read outputs.
    for (size_t v = 0; v < vehicles_.size(); ++v) {
        vehicles_[v].plant->applyTriggers(triggers_[v]);
        vehicles_[v].plant->doStep(t, dt_);
        vehicles_[v].out = vehicles_[v].plant->readOutputs();
    }

    // 3a'. FCHANNEL margins + achieved F staleness, per tick (undecimated).
    if (maxAbsEy_.size() != vehicles_.size()) maxAbsEy_.assign(vehicles_.size(), 0.0);
    for (size_t v = 0; v < vehicles_.size(); ++v) {
        const double aey = std::fabs(vehicles_[v].out.e_y_real);
        if (aey > maxAbsEy_[v]) maxAbsEy_[v] = aey;
        if (params_.plant != PlantKind::Lateral) continue;
        const int z = static_cast<int>(vehicles_[v].traj->zoneAt(step_ + offsets_[v]));
        if (aey > zoneMaxAbsEy_[z]) zoneMaxAbsEy_[z] = aey;
        const long ffAge =
            scheduler_->currentFfStalenessTicks(static_cast<int>(v), step_);
        if (ffAge >= 0) {
            ++ffStaleZoneTicks_[z];
            if (ffAge > ffStaleZoneMaxTicks_[z]) ffStaleZoneMaxTicks_[z] = ffAge;
            for (int l = 0; l < 4; ++l)
                if (ffAge > kFfLadderTicks[l]) ++ffStaleExceed_[z][l];
        }
    }

    // Actuator-authority calibration aid (the car's delta_max / the cart-pole's
    // uMax): track peak commanded actuation under --validate-predictor (mirrors
    // how delta_max was measured). act_demand is the pre-clamp force; act_out is
    // post-clamp. All plants (the lateral gate below reports valMaxAct_).
    if (params_.validatePredictor) {
        for (size_t v = 0; v < vehicles_.size(); ++v) {
            valMaxAct_    = std::max(valMaxAct_,    std::fabs(vehicles_[v].out.act_out));
            valMaxDemand_ = std::max(valMaxDemand_, std::fabs(vehicles_[v].out.act_demand));
        }
    }

    // Fidelity gate is FMU-port-specific (lateral); other plants' predictors
    // share the plant's own integrator, so there is nothing to validate.
    if (params_.validatePredictor && params_.plant == PlantKind::Lateral)
        validatePredictions();

    // 3b. Refresh held-command predictions and accumulate closest-call stats.
    if (step_ % kPredictRefreshTicks == 0)
        refreshPredictions(/*withPnr=*/step_ % kPnrRefreshTicks == 0);
    // 3b'. Honest predictor: log delayed state, refresh the parallel rollout.
    if (params_.honestPredictor) {
        for (size_t v = 0; v < vehicles_.size(); ++v)
            stateHist_[v][step_ % stateHist_[v].size()] = vehicles_[v].out;
        if (step_ % kPredictRefreshTicks == 0)
            refreshHonestPredictions(/*withPnr=*/step_ % kPnrRefreshTicks == 0);
    }
    int simCrit = 0;
    for (size_t v = 0; v < vehicles_.size(); ++v) {
        if (predBaseStep_[v] < 0) continue;
        long ttv, ttpnr;
        currentPredTicks(static_cast<int>(v), ttv, ttpnr);
        const double ms = ttpnr * dt_ * 1000.0;
        if (ttpnr < predParams_.horizonTicks) {
            if (minTtpnrMs_[v] < 0.0 || ms < minTtpnrMs_[v]) minTtpnrMs_[v] = ms;
            if (ttpnr == 0) ++pastPnrTicks_[v];
        }
        // Simultaneous criticality: within one command round-trip of PNR (incl.
        // past-PNR, ttpnr==0). Horizon-sentinel cars have ms = horizon > tau_crit.
        if (ms < params_.tauCritMs) ++simCrit;
    }
    ++simCritTicks_;
    if (simCrit < static_cast<int>(simCritHist_.size())) ++simCritHist_[simCrit];
    if (simCrit > maxSimCrit_) maxSimCrit_ = simCrit;

    // 3c. Danger-relative criticality (THE PLAN leg 4): count cars whose delivered
    // age_path has eaten fraction tau of their CURRENT zone's A(zone) budget
    // (K_age), unioned with the state-critical (TTPNR<tauCrit) cars (K). A(zone)
    // assumes the car enters the zone well-tracked, so accumulated error is folded
    // in via TTPNR (THEOREM_BRIEF §3.2 wrinkle). Swept over a fixed tau grid in one
    // run for the K(tau) curve; the primary point is params_.dangerTau. Lateral
    // only (zones are a track concept); measurement only -- no scheduler reads it.
    if (params_.plant == PlantKind::Lateral) {
        int kAgePrimary = 0, kDangerPrimary = 0;
        int kAgeGrid[kDangerTauN] = {0};
        int kDangerGrid[kDangerTauN] = {0};
        int occ[4] = {0, 0, 0, 0};  // leg-2: cars currently in each zone this tick
        for (size_t v = 0; v < vehicles_.size(); ++v) {
            // State term, evaluated for EVERY car (incl. never-actuated/starved):
            // this car's actual TTPNR-under-held (oracle rollout) -- the same signal
            // --tau-crit uses, so K(+state) is a strict superset of sim-crit. A
            // past-PNR starved car (no command ever delivered) is caught here even
            // though it has no measurable delivered age below. A degraded car near
            // PNR also counts even with a fresh-ish command (THEOREM_BRIEF §3.2).
            bool stateCrit = false;
            if (predBaseStep_[v] >= 0) {
                long ttv, ttpnr;
                currentPredTicks(static_cast<int>(v), ttv, ttpnr);
                stateCrit = (ttpnr * dt_ * 1000.0) < params_.tauCritMs;
            }
            // Age term: delivered age_path vs the car's current-zone budget. Only
            // defined once a command has actually reached the actuator (age >= 0);
            // a never-actuated car has no delivered command (a "no service" failure,
            // surfaced by the state term + the age=n/a summary row, not here), so it
            // is left out of K_age but caught by K via the state term above.
            double ratio = -1.0;
            const long ageTicks =
                scheduler_->currentDataAgeOldestTicks(static_cast<int>(v), step_);
            const int z = static_cast<int>(vehicles_[v].traj->zoneAt(step_ + offsets_[v]));
            if (z >= 0 && z <= 3) ++occ[z];  // leg-2 zone occupancy (this car is in zone z)
            if (ageTicks >= 0 && z >= 0 && z <= 3)
                ratio = (ageTicks * dt_ * 1000.0) / kAZoneMs[z];
            const bool ageCritPrimary = ratio >= params_.dangerTau;
            if (ageCritPrimary) ++kAgePrimary;
            if (ageCritPrimary || stateCrit) ++kDangerPrimary;
            for (int g = 0; g < kDangerTauN; ++g) {
                const bool ageCritG = ratio >= kDangerTauGrid[g];
                if (ageCritG) ++kAgeGrid[g];
                if (ageCritG || stateCrit) ++kDangerGrid[g];
            }
        }
        if (kAgePrimary > maxKAgePrimary_) maxKAgePrimary_ = kAgePrimary;
        if (kDangerPrimary > maxKDangerPrimary_) maxKDangerPrimary_ = kDangerPrimary;
        if (kDangerPrimary < static_cast<int>(kDangerHist_.size())) ++kDangerHist_[kDangerPrimary];
        ++kDangerTicks_;
        for (int g = 0; g < kDangerTauN; ++g) {
            if (kAgeGrid[g] > maxKAgeGrid_[g]) maxKAgeGrid_[g] = kAgeGrid[g];
            if (kDangerGrid[g] > maxKDangerGrid_[g]) maxKDangerGrid_[g] = kDangerGrid[g];
        }
        // Leg 2: run-max simultaneous zone occupancy + packed-zone dwell histogram.
        for (int zi = 0; zi < 4; ++zi)
            if (occ[zi] > maxOcc_[zi]) maxOcc_[zi] = occ[zi];
        if (params_.packZone >= 0 && params_.packZone < 4) {
            const int oc = occ[params_.packZone];
            if (oc < static_cast<int>(occHist_.size())) ++occHist_[oc];
            ++occTicks_;
        }
    }

    // 4. Record a decimated frame.
    if (step_ % params_.decimation == 0) recordFrame(t);

    ++step_;
    if (step_ >= durationSteps_) finalizeSummary();
    return true;
}

void Simulation::recordFrame(double t) {
    for (size_t v = 0; v < vehicles_.size(); ++v) {
        const VehicleOutputs& o = vehicles_[v].out;
        Frame f;
        f.t            = static_cast<float>(t);
        f.refStep      = static_cast<uint32_t>(vehicles_[v].traj->wrap(step_ + offsets_[v]));
        f.e_y_real     = static_cast<float>(o.e_y_real);
        f.e_y_est      = static_cast<float>(o.e_y_est);
        f.act          = static_cast<float>(o.act_out);
        f.vel          = static_cast<float>(vehicles_[v].curVel);
        f.rolling_real = static_cast<float>(o.rolling_real);
        f.average_real = static_cast<float>(o.average_real);
        for (int i = 0; i < 6; ++i) f.phys[i] = static_cast<float>(o.phys[i]);
        if (predBaseStep_[v] >= 0) {
            long ttv, ttpnr;
            currentPredTicks(static_cast<int>(v), ttv, ttpnr);
            f.ttv_ms   = static_cast<float>(ttv * dt_ * 1000.0);
            f.ttpnr_ms = static_cast<float>(ttpnr * dt_ * 1000.0);
        }

        const double absEy = std::fabs(o.e_y_real);
        uint8_t flags = 0;
        if (o.violated_real || absEy > vehicles_[v].plant->softBound()) flags |= Frame::kSoft;
        if (absEy > vehicles_[v].plant->hardBound()) { flags |= Frame::kHard; ++hardCount_[v]; }
        if (o.critical_real) flags |= Frame::kCritical;
        f.flags = flags;

        // Zone attribution (leg A / Phase-1 A(zone)): bucket this frame's breach
        // by its curvature zone (lateral only -- zones are a track concept).
        if (params_.plant == PlantKind::Lateral) {
            const int z = static_cast<int>(vehicles_[v].traj->zoneAt(step_ + offsets_[v]));
            if (z >= 0 && z < 4) {
                ++zoneFrames_[z];
                if (flags & Frame::kHard) ++zoneHard_[z];
                if (flags & Frame::kSoft) ++zoneSoft_[z];
            }
        }

        rec_.frames[v].push_back(f);
        if (o.rolling_real > maxRolling_[v]) maxRolling_[v] = o.rolling_real;
    }
}

// Predictor fidelity gate. Tick t's physics runs on the command applied
// BEFORE this tick's trigger pass (the FMU advances physics first, then
// processes triggers), so the state read after an act_fin tick is still
// governed by the old command and remains comparable against the old
// prediction; the NEW prediction then starts from this state with the
// just-latched command, whose first affected physics tick is step_ + 1.
void Simulation::validatePredictions() {
    if (pendingVal_.size() != vehicles_.size()) pendingVal_.resize(vehicles_.size());

    for (size_t v = 0; v < vehicles_.size(); ++v) {
        const VehicleOutputs& o = vehicles_[v].out;

        // Compare this tick's realized e_y against the active prediction.
        PendingValidation& pv = pendingVal_[v];
        if (pv.active) {
            const long idx = step_ - pv.madeAtStep;
            if (idx >= 0 && idx < static_cast<long>(pv.pred.e_y.size())) {
                const double dev = std::fabs(o.phys[4] - pv.pred.e_y[idx]);
                if (dev > valMaxDev_) valMaxDev_ = dev;
                ++valSamples_;
            }
        }

        // A fresh command latched: predict the upcoming hold from this state.
        if (triggers_[v].act_fin) {
            PredictParams p;
            p.horizonTicks = 400;  // covers the ~30 ms actuator hold
            p.vizStride = 1;
            p.computePnr = false;
            p.velQuantum = 0.0;  // exact model: the gate validates the true port
            pv.pred = vehicles_[v].plant->predictHeld(o, step_ + 1, *traj_,
                                                      offsets_[v], p);
            pv.madeAtStep = step_;
            pv.active = true;
            ++valHolds_;
        }
    }
}

void Simulation::finalizeSummary() {
    if (finalized_) return;
    const double duration = static_cast<double>(durationSteps_) * dt_;
    for (size_t v = 0; v < vehicles_.size(); ++v) {
        VehicleSummary& s = rec_.summary[v];
        s.average_real        = vehicles_[v].out.average_real;
        s.max_rolling_real    = maxRolling_[v];
        s.threshold_cntr_real = vehicles_[v].out.threshold_cntr_real;
        s.soft_violation_pct  = duration > 0.0
            ? 100.0 * (s.threshold_cntr_real * vr::kMetricPeriodSeconds) / duration
            : 0.0;
        s.hard_violations     = hardCount_[v];
        const long ageTicks   = scheduler_->maxDataAgeTicks(static_cast<int>(v));
        s.max_data_age_ms     = ageTicks < 0 ? -1.0 : ageTicks * dt_ * 1000.0;
        const long ageOldTicks = scheduler_->maxDataAgeOldestTicks(static_cast<int>(v));
        s.max_data_age_oldest_ms = ageOldTicks < 0 ? -1.0 : ageOldTicks * dt_ * 1000.0;
        s.min_ttpnr_ms   = minTtpnrMs_[v];
        s.past_pnr_ticks = pastPnrTicks_[v];
    }
    rec_.missedJobs = scheduler_->missedJobs();
    rec_.tauCritMs    = params_.tauCritMs;
    rec_.maxSimCrit   = maxSimCrit_;
    rec_.simCritHist  = simCritHist_;
    rec_.simCritTicks = simCritTicks_;
    rec_.dangerTau    = params_.dangerTau;
    rec_.maxKAge      = maxKAgePrimary_;
    rec_.maxKDanger   = maxKDangerPrimary_;
    rec_.packZone     = params_.packZone;
    rec_.minSpacingMs = params_.minSpacingMs;
    rec_.maxOccPacked = (params_.packZone >= 0 && params_.packZone < 4)
                        ? maxOcc_[params_.packZone] : 0;
    rec_.packZoneArcTicks = packZoneArcTicks_;
    finalized_ = true;
}

void Simulation::runToCompletion(bool verbose) {
    if (!started_) start();
    const auto t0 = std::chrono::steady_clock::now();
    const long report = durationSteps_ > 20 ? durationSteps_ / 20 : 1;
    while (step()) {
        if (verbose && step_ % report == 0)
            std::printf("\r  simulating... %3.0f%%", 100.0 * progress());
    }
    if (verbose) {
        const auto t1 = std::chrono::steady_clock::now();
        const double secs = std::chrono::duration<double>(t1 - t0).count();
        std::printf("\r  simulated %.1f s of driving in %.2f s wall (%.0fx)\n",
                    rec_.duration(), secs, secs > 0 ? rec_.duration() / secs : 0.0);
        std::printf("  scheduler: %s   missed jobs: %ld\n",
                    rec_.schedulerName.c_str(), rec_.missedJobs);
        std::printf("  %-4s %12s %12s %10s %10s %13s %13s %12s %9s\n", "veh", "avg_perf",
                    "max_roll", "soft%", "hard", "age_fresh(ms)", "age_path(ms)",
                    "min_pnr(ms)", "pnr0(ms)");
        double worstAgeMs = -1.0, worstAgeOldMs = -1.0;
        auto fmtAge = [](char* buf, size_t n, double v) {
            if (v < 0.0) std::snprintf(buf, n, "%13s", "n/a");
            else         std::snprintf(buf, n, "%13.2f", v);
        };
        for (int v = 0; v < rec_.nVehicles; ++v) {
            const VehicleSummary& s = rec_.summary[v];
            if (s.max_data_age_ms > worstAgeMs) worstAgeMs = s.max_data_age_ms;
            if (s.max_data_age_oldest_ms > worstAgeOldMs) worstAgeOldMs = s.max_data_age_oldest_ms;
            char ageBuf[24], ageOldBuf[24], pnrBuf[24];
            fmtAge(ageBuf, sizeof ageBuf, s.max_data_age_ms);
            fmtAge(ageOldBuf, sizeof ageOldBuf, s.max_data_age_oldest_ms);
            if (s.min_ttpnr_ms < 0.0) std::snprintf(pnrBuf, sizeof pnrBuf, "%12s", "-");
            else                      std::snprintf(pnrBuf, sizeof pnrBuf, "%12.1f", s.min_ttpnr_ms);
            std::printf("  %-4d %12.5f %12.5f %9.2f%% %10d %s %s %s %9.1f\n", v,
                        s.average_real, s.max_rolling_real, s.soft_violation_pct,
                        s.hard_violations, ageBuf, ageOldBuf, pnrBuf,
                        s.past_pnr_ticks * dt_ * 1000.0);
        }
        if (worstAgeMs >= 0.0)
            std::printf("  worst-case data age: %.2f ms (freshest) / %.2f ms (path)\n",
                        worstAgeMs, worstAgeOldMs);
        if (params_.plant == PlantKind::Lateral)
            std::printf("  zone breaches (frame-decimated): hard z0=%ld z1=%ld z2=%ld "
                        "z3=%ld | soft z0=%ld z1=%ld z2=%ld z3=%ld\n",
                        zoneHard_[0], zoneHard_[1], zoneHard_[2], zoneHard_[3],
                        zoneSoft_[0], zoneSoft_[1], zoneSoft_[2], zoneSoft_[3]);
        if (params_.plant == PlantKind::Lateral)
            std::printf("  zone frames: z0=%ld z1=%ld z2=%ld z3=%ld\n",
                        zoneFrames_[0], zoneFrames_[1], zoneFrames_[2], zoneFrames_[3]);
        // FCHANNEL reporting (undecimated margins + achieved F staleness +
        // per-kind missed). Passive additions; golden numbers untouched.
        {
            double fleetMaxEy = 0.0;
            for (double m : maxAbsEy_) fleetMaxEy = std::max(fleetMaxEy, m);
            std::printf("  max |e_y| (per-tick): fleet %.4f m (margin %.4f m to 0.8)",
                        fleetMaxEy, 0.8 - fleetMaxEy);
            if (params_.plant == PlantKind::Lateral)
                std::printf(" | zones %.4f %.4f %.4f %.4f", zoneMaxAbsEy_[0],
                            zoneMaxAbsEy_[1], zoneMaxAbsEy_[2], zoneMaxAbsEy_[3]);
            std::printf("\n");
        }
        if (params_.plant == PlantKind::Lateral) {
            std::printf("  F staleness (act-stamped, ms): zone max %.1f %.1f %.1f %.1f"
                        " | in-zone ticks >500ms:",
                        ffStaleZoneMaxTicks_[0] * dt_ * 1000.0,
                        ffStaleZoneMaxTicks_[1] * dt_ * 1000.0,
                        ffStaleZoneMaxTicks_[2] * dt_ * 1000.0,
                        ffStaleZoneMaxTicks_[3] * dt_ * 1000.0);
            for (int z = 0; z < 4; ++z) {
                const double pct = ffStaleZoneTicks_[z] > 0
                    ? 100.0 * static_cast<double>(ffStaleExceed_[z][2]) /
                          static_cast<double>(ffStaleZoneTicks_[z]) : 0.0;
                std::printf(" z%d=%ld(%.1f%%)", z, ffStaleExceed_[z][2], pct);
            }
            std::printf("\n");
        }
        std::printf("  missed by kind: E=%ld B=%ld F=%ld M=%ld\n",
                    scheduler_->missedJobsByKind(1), scheduler_->missedJobsByKind(2),
                    scheduler_->missedJobsByKind(3), scheduler_->missedJobsByKind(4));
        // Simultaneous criticality (HANDOFF §5 item 0): empirical shadow of leg (A).
        {
            long over = 0;
            for (int c = params_.nCores + 1; c < static_cast<int>(simCritHist_.size()); ++c)
                over += simCritHist_[c];
            const double fracOver = simCritTicks_ > 0
                ? 100.0 * static_cast<double>(over) / static_cast<double>(simCritTicks_) : 0.0;
            std::printf("  simultaneous criticality (tau_crit=%.0f ms): max %ld of %d | "
                        "cores=%d | >cores for %.2f%% of run\n",
                        params_.tauCritMs, maxSimCrit_, rec_.nVehicles, params_.nCores, fracOver);
            std::printf("    sim-crit dist (ticks):");
            for (int c = 0; c <= maxSimCrit_ && c < static_cast<int>(simCritHist_.size()); ++c)
                std::printf(" %d:%ld", c, simCritHist_[c]);
            std::printf("\n");
            if (maxSimCrit_ > params_.nCores)
                std::printf("  ** %ld loops simultaneously within tau_crit of PNR exceeds %d "
                            "cores -- more critical loops than cores at some instant "
                            "(candidate (A) counterexample; investigate) **\n",
                            maxSimCrit_, params_.nCores);
        }
        // Danger-relative criticality (THE PLAN leg 4): delivered age vs A(zone),
        // folding in actual state (TTPNR). Lateral only (zones are a track concept).
        if (params_.plant == PlantKind::Lateral && kDangerTicks_ > 0) {
            long over = 0;
            for (int c = params_.nCores + 1; c < static_cast<int>(kDangerHist_.size()); ++c)
                over += kDangerHist_[c];
            const double fracOver =
                100.0 * static_cast<double>(over) / static_cast<double>(kDangerTicks_);
            std::printf("  danger-relative criticality (age vs A(zone), tau=%.2f): "
                        "K_age max %ld / K(+state) max %ld of %d | cores=%d | "
                        "K>cores for %.2f%% of run\n",
                        params_.dangerTau, maxKAgePrimary_, maxKDangerPrimary_,
                        rec_.nVehicles, params_.nCores, fracOver);
            std::printf("    K(tau) curve [age-only]:");
            for (int g = 0; g < kDangerTauN; ++g)
                std::printf(" %.2f:%ld", kDangerTauGrid[g], maxKAgeGrid_[g]);
            std::printf("\n    K(tau) curve [+state] :");
            for (int g = 0; g < kDangerTauN; ++g)
                std::printf(" %.2f:%ld", kDangerTauGrid[g], maxKDangerGrid_[g]);
            std::printf("\n");
        }
        // Worst-case zone occupancy (THE PLAN leg 2): max simultaneous cars per zone;
        // headline is the packed/binding zone vs the geometric prediction floor(L/s)+1.
        if (params_.plant == PlantKind::Lateral) {
            std::printf("  zone occupancy (max simultaneous): z0=%ld z1=%ld z2=%ld z3=%ld of %d\n",
                        maxOcc_[0], maxOcc_[1], maxOcc_[2], maxOcc_[3], rec_.nVehicles);
            if (params_.packZone >= 0 && params_.packZone < 4) {
                const long sp = std::max<long>(1, static_cast<long>(
                    params_.minSpacingMs / (dt_ * 1000.0) + 0.5));
                const long geo = packZoneArcTicks_ > 0    // ceil(L/s), THEOREM_BRIEF §3.5
                    ? std::min<long>(rec_.nVehicles, (packZoneArcTicks_ + sp - 1) / sp) : 0;
                long over = 0;
                for (int c = params_.nCores + 1; c < static_cast<int>(occHist_.size()); ++c)
                    over += occHist_[c];
                const double fracOver = occTicks_ > 0
                    ? 100.0 * static_cast<double>(over) / static_cast<double>(occTicks_) : 0.0;
                std::printf("    packed z%d at spacing %.0f ms: Occ max %ld of %d | zone len "
                            "%ld ticks -> geo-predict ceil(L/s)=%ld | Occ>cores %.2f%% of run\n",
                            params_.packZone, params_.minSpacingMs,
                            maxOcc_[params_.packZone], rec_.nVehicles,
                            packZoneArcTicks_, geo, fracOver);
            }
        }
        if (predCount_ > 0) {
            const double usPer  = predWallSeconds_ * 1e6 / static_cast<double>(predCount_);
            const double simSec = rec_.duration();
            const double pctCore = simSec > 0.0 ? 100.0 * predWallSeconds_ / simSec : 0.0;
            std::printf("  prediction compute: %.1f us/prediction, %.3f%% of one core\n"
                        "    (%ld rollouts, %.0f ms wall over %.1f s sim)\n",
                        usPer, pctCore, predCount_, predWallSeconds_ * 1000.0, simSec);
        }
        if (params_.validatePredictor) {
            if (params_.plant != PlantKind::Lateral) {
                std::printf("  predictor validation: skipped (FMU-port gate; this "
                            "plant's predictor shares the plant's own integrator).\n");
                std::printf("  actuator calibration aid: max|demand| = %.4f N, "
                            "max|act_out| = %.4f N (%s); uMax = 1.5x|demand| = %.4f N\n",
                            valMaxDemand_, valMaxAct_,
                            valMaxDemand_ > valMaxAct_ + 1e-9 ? "CLAMP BOUND" : "clamp free",
                            1.5 * valMaxDemand_);
            } else {
                std::printf("  predictor validation: %ld holds, %ld samples, "
                            "max |dev| = %.3e m -> %s   (max |act_out| = %.4f rad)\n",
                            valHolds_, valSamples_, valMaxDev_,
                            valMaxDev_ < 1e-6 ? "PASS" : "FAIL", valMaxAct_);
            }
        }
    }
}

}  // namespace cps
