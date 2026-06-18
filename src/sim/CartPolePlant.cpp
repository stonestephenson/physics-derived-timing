#include "sim/CartPolePlant.h"

#include <algorithm>
#include <cmath>

#include "fmu/FmuVariables.h"  // vr::kMetricPeriodSeconds

namespace cps {

CartPolePlant::CartPolePlant(const CartPoleParams& p) : params_(p) {}

void CartPolePlant::initialize(double, double, double) {
    st_ = {0.0, 0.0, 0.0, 0.0};   // upright, centered
    step_ = 0;
    metricPeriodTicks_ =
        std::max<long>(1, std::lround(vr::kMetricPeriodSeconds / dt_));
}

void CartPolePlant::setInputs(double, double, double) {
    // The reference ("track") is the internal, deterministic disturbance schedule
    // (disturbance()), so the per-tick trajectory inputs are ignored here.
}

void CartPolePlant::applyTriggers(const VehicleTriggers& t) { trig_ = t; }

double CartPolePlant::disturbance(long absStep) const {
    const long phase = absStep % params_.shovePeriodTicks;
    return (phase < params_.shoveDurTicks) ? params_.shoveForce : 0.0;
}

CartPolePlant::State CartPolePlant::integrate(const State& s, double force) const {
    const double Mm = params_.M + params_.m, m = params_.m, l = params_.l, g = params_.g;
    auto deriv = [&](const State& z) {
        const double xd = z[1], th = z[2], thd = z[3];
        const double st = std::sin(th), ct = std::cos(th);
        const double temp = (force + m * l * thd * thd * st) / Mm;
        const double thdd = (g * st - ct * temp) / (l * (4.0 / 3.0 - m * ct * ct / Mm));
        const double xdd  = temp - m * l * thdd * ct / Mm;
        return State{xd, xdd, thd, thdd};
    };
    const State k1 = deriv(s);
    State a; for (int i = 0; i < 4; ++i) a[i] = s[i] + 0.5 * dt_ * k1[i];
    const State k2 = deriv(a);
    State b; for (int i = 0; i < 4; ++i) b[i] = s[i] + 0.5 * dt_ * k2[i];
    const State k3 = deriv(b);
    State c; for (int i = 0; i < 4; ++i) c[i] = s[i] + dt_ * k3[i];
    const State k4 = deriv(c);
    State out;
    for (int i = 0; i < 4; ++i)
        out[i] = s[i] + (dt_ / 6.0) * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]);
    return out;
}

bool CartPolePlant::doStep(double, double) {
    // 1. Advance physics with the currently applied force + the known disturbance
    //    (the FMU likewise integrates on the command applied before this tick's
    //    trigger pass).
    st_ = integrate(st_, actOut_ + disturbance(step_));

    // 2. Trigger-driven chain routing, in TaskChainModel::endTick order
    //    (receives, sensor, cloud stages, actuator), so the age metric matches.
    if (trig_.net_sc_recv && !scQueue_.empty()) { scRec_ = scQueue_.front(); scQueue_.pop_front(); }
    if (trig_.net_ca_recv && !caQueue_.empty()) { caRec_ = caQueue_.front(); caQueue_.pop_front(); }

    if (trig_.sensor_act) sensComp_ = st_;        // sample the (post-integration) state
    if (trig_.sensor_fin) sensOut_  = sensComp_;  // publish
    if (trig_.net_sc_sent) scQueue_.push_back(sensOut_);

    if (trig_.est_act) estComp_ = scRec_;         // identity estimator
    if (trig_.est_fin) estOut_  = estComp_;

    if (trig_.ctrl_act)                            // LQR feedback on the estimate
        fbComp_ = -(params_.K[0] * estOut_[0] + params_.K[1] * estOut_[1] +
                    params_.K[2] * estOut_[2] + params_.K[3] * estOut_[3]);
    if (trig_.ctrl_fin) fbOut_ = fbComp_;

    if (trig_.ff_act) ffComp_ = 0.0;               // regulation: no feedforward (no sensor data)
    if (trig_.ff_fin) ffOut_  = ffComp_;

    if (trig_.merge_act) aggComp_ = fbOut_ + ffOut_;
    if (trig_.merge_fin) aggOut_  = aggComp_;
    if (trig_.net_ca_sent) caQueue_.push_back(aggOut_);

    if (trig_.act_act) actIn_  = caRec_;
    if (trig_.act_fin) actOut_ = std::max(-params_.uMax, std::min(params_.uMax, actIn_));

    // 3. Metrics (theta is the error signal).
    const double th = st_[2];
    sumSq_ += th * th; ++sumN_;
    rolling_ = th * th;
    if (std::fabs(th) > params_.thetaSoft) softViolatedThisPeriod_ = true;
    if (step_ % metricPeriodTicks_ == 0) {
        if (softViolatedThisPeriod_) ++thresholdCntr_;
        softViolatedThisPeriod_ = false;
    }

    ++step_;
    return true;
}

VehicleOutputs CartPolePlant::readOutputs() const {
    VehicleOutputs o;
    o.phys[0] = st_[0]; o.phys[1] = st_[1]; o.phys[2] = st_[2]; o.phys[3] = st_[3];
    o.phys[4] = st_[2]; o.phys[5] = st_[3];   // theta in the e_y slot for recording
    o.e_y_real = st_[2];                       // safety error = pole angle
    o.e_y_est  = estOut_[2];                    // estimated angle
    o.act_out  = actOut_;                       // applied force
    o.rolling_real   = rolling_;
    o.rolling_remote = rolling_;
    o.average_real   = sumN_ > 0 ? sumSq_ / static_cast<double>(sumN_) : 0.0;
    o.threshold_cntr_real = thresholdCntr_;
    o.violated_real   = std::fabs(st_[2])     > params_.thetaSoft;
    o.violated_remote = std::fabs(estOut_[2]) > params_.thetaSoft;
    o.critical_real   = disturbance(step_) != 0.0;   // "critical section" = mid-shove
    o.critical_remote = o.critical_real;
    return o;
}

Prediction CartPolePlant::predictHeld(const VehicleOutputs& /*cur*/, long fromStep,
                                      const Trajectory& /*ref*/, long /*trajOffset*/,
                                      const PredictParams& p) const {
    // STUB (Phase 2 step 1): report "relaxed" (no urgency) so rm/edf baselines
    // run. The real held-command rollout (TTV/TTPNR vs theta_max with a bounded
    // recovery) lands next, before any predictive policy is exercised.
    Prediction pr;
    pr.fromStep    = fromStep;
    pr.ttvTicks    = p.horizonTicks;
    pr.ttpnrTicks  = p.horizonTicks;
    pr.pastPnr     = false;
    pr.strideTicks = p.vizStride;
    return pr;
}

}  // namespace cps
