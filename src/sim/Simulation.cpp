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

Simulation::Simulation(const SimParams& params, std::unique_ptr<Scheduler> scheduler,
                       std::shared_ptr<FmuLibrary> lib)
    : params_(params), scheduler_(std::move(scheduler)), lib_(std::move(lib)) {
    dt_ = vr::kBaseStepSeconds;
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
        offsets_.resize(n);
        for (int v = 0; v < n; ++v)  // spread evenly around the lap
            offsets_[v] = static_cast<long>(static_cast<double>(v) * traj_->lapSteps() / n);
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
    scheduler_->init(cfg, taskSets);

    rec_.profile       = static_cast<int>(params_.profile);
    rec_.nVehicles     = n;
    rec_.nCores        = params_.nCores;
    rec_.baseStep      = dt_;
    rec_.durationSteps = durationSteps_;
    rec_.decimation    = params_.decimation;
    rec_.schedulerName = scheduler_->name();
    rec_.startOffsets  = offsets_;
    rec_.frames.assign(n, {});
    rec_.summary.assign(n, {});

    views_.resize(n);
    triggers_.resize(n);
    maxRolling_.assign(n, 0.0);
    hardCount_.assign(n, 0);

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
        const Trajectory::Inputs in = vehicles_[v].traj->inputsAt(step_ + offsets_[v]);
        vehicles_[v].curVel = in.vel;
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
