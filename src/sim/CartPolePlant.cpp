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

CartPolePlant::State CartPolePlant::integrate(const State& s, double force, double dt) const {
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
    State a; for (int i = 0; i < 4; ++i) a[i] = s[i] + 0.5 * dt * k1[i];
    const State k2 = deriv(a);
    State b; for (int i = 0; i < 4; ++i) b[i] = s[i] + 0.5 * dt * k2[i];
    const State k3 = deriv(b);
    State c; for (int i = 0; i < 4; ++i) c[i] = s[i] + dt * k3[i];
    const State k4 = deriv(c);
    State out;
    for (int i = 0; i < 4; ++i)
        out[i] = s[i] + (dt / 6.0) * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]);
    return out;
}

bool CartPolePlant::doStep(double, double) {
    // 1. Advance physics with the currently applied force + the known disturbance
    //    (the FMU likewise integrates on the command applied before this tick's
    //    trigger pass).
    st_ = integrate(st_, actOut_ + disturbance(step_), dt_);

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
    o.act_out  = actOut_;                       // applied force (post +-uMax clamp)
    o.act_demand = actIn_;                       // pre-clamp commanded force (uMax calibration aid)
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

Prediction CartPolePlant::predictHeld(const VehicleOutputs& cur, long fromStep,
                                      const Trajectory& /*ref*/, long /*trajOffset*/,
                                      const PredictParams& p) const {
    // Held-command rollout for the cart-pole (the role Predictor.cpp plays for
    // the car): if the actuator keeps holding cur.act_out, when does |theta|
    // cross theta_max (TTV), and what is the last tick at which a bounded
    // +-uMax recovery can still keep it inside forever after (TTPNR)? Rolled at
    // a coarse 1 ms RK4 step (negligibly different from the 0.1 ms plant) for
    // speed; the known future disturbance is the cart-pole's "track".
    const double thMax = params_.thetaHard, thSoft = params_.thetaSoft, uMax = params_.uMax;
    const long H  = p.horizonTicks;
    const long cs = 10;                    // coarse rollout step (ticks) = 1 ms
    const double dtc = cs * dt_;
    const State s0 = {cur.phys[0], cur.phys[1], cur.phys[2], cur.phys[3]};
    const double held = cur.act_out;

    Prediction pr;
    pr.fromStep = fromStep;
    pr.strideTicks = cs;

    // Held rollout -> TTV and the theta polyline.
    long ttv = H;
    { State s = s0;
      for (long j = 0; j <= H; j += cs) {
          pr.e_y.push_back(static_cast<float>(s[2]));
          if (std::fabs(s[2]) >= thMax) { ttv = j; break; }
          s = integrate(s, held + disturbance(fromStep + j), dtc);
      } }
    pr.ttvTicks = ttv;
    if (!p.computePnr) { pr.ttpnrTicks = ttv; return pr; }

    // Can a recovery STARTED at hold-tick h still hold the pole? Hold until h,
    // wait recoveryLatency, then bang-bang +-uMax opposing (theta + 0.3*thetadot)
    // (force sign that reduces |theta|). Success: reach the soft band for >= 50 ms,
    // or never breach over the window. Track the min clearance to theta_max.
    auto recovers = [&](long h, double& minClear) -> bool {
        State s = s0;
        for (long j = 0; j < h; j += cs) s = integrate(s, held + disturbance(fromStep + j), dtc);
        minClear = thMax - std::fabs(s[2]);
        long t = h;
        for (long k = 0; k < p.recoveryLatencyTicks; k += cs) {
            s = integrate(s, held + disturbance(fromStep + t), dtc); t += cs;
            minClear = std::min(minClear, thMax - std::fabs(s[2]));
            if (std::fabs(s[2]) >= thMax) return false;
        }
        long inSoft = 0;
        for (long k = 0; k < p.recoveryWindowTicks; k += cs) {
            const double u = (s[2] + 0.3 * s[3] > 0.0) ? uMax : -uMax;
            s = integrate(s, u + disturbance(fromStep + t), dtc); t += cs;
            minClear = std::min(minClear, thMax - std::fabs(s[2]));
            if (std::fabs(s[2]) >= thMax) return false;
            if (std::fabs(s[2]) < thSoft) { inSoft += cs; if (inSoft >= 500) return true; }
            else inSoft = 0;
        }
        return true;
    };

    double clr0; const bool ok0 = recovers(0, clr0);
    pr.rescueClearanceM = clr0;
    if (!ok0) { pr.ttpnrTicks = 0; pr.pastPnr = true; return pr; }

    // Largest hold-tick h in [0, ttv] that still recovers (monotone assumption).
    long lo = 0, hi = ttv;
    const long grid = std::max<long>(cs, p.pnrSearchStrideTicks);
    double dummy;
    while (hi - lo > grid) {
        long mid = lo + ((hi - lo) / 2 / grid) * grid;
        if (mid <= lo) mid = lo + grid;
        if (recovers(mid, dummy)) lo = mid; else hi = mid;
    }
    pr.ttpnrTicks = lo;
    return pr;
}

}  // namespace cps
