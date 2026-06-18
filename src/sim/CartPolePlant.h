// CartPolePlant.h — second case study: an inverted pendulum on a cart, driven by
// the SAME task chain / scheduler / data-age machinery as the FMU lateral
// controller. Its unstable dynamics make the physics-derived deadline (TTPNR)
// razor-thin where the car's is loose — the contrast that carries the
// generalization thesis (PAPER_NOTES.md).
//
// Dynamics, an LQR/pole-placed controller, and the trigger-driven
// read-execute-write chain all live here (the plant is our own code, so the
// predictor is trivially exact — no fidelity gate needed). The chain routing
// mirrors TaskChainModel::endTick / the FMU's process_trigger_events so the age
// metric and bound apply unchanged; only the physics differs.
#pragma once

#include <array>
#include <deque>

#include "sim/Plant.h"

namespace cps {

struct CartPoleParams {
    double M = 1.0, m = 0.1, l = 0.5, g = 9.81;  // cart / pole mass, half-length, gravity
    double uMax      = 10.0;                      // actuator force limit (N) — the delta_max analogue
    double thetaHard = 0.21;                      // |theta| crash bound (rad ~12 deg) — the 0.8 m analogue
    double thetaSoft = 0.05;                      // |theta| comfort bound (rad ~3 deg) — the 0.2 m analogue
    // Feedback gain: u = -K . [x, xdot, theta, thetadot]. Pole-placed at
    // -2,-3,-4,-5 (computed offline; closed loop verified stable).
    std::array<double, 4> K = {-8.3588, -10.7271, -64.8802, -16.7181};
    // Disturbance "track": periodic cart-force shoves, deterministic and known a
    // priori (like the racetrack curvature) so the predictor can see them ahead.
    long   shovePeriodTicks = 20000;  // 2 s between shoves
    long   shoveDurTicks    = 500;    // 50 ms shove
    double shoveForce       = 8.0;    // N
};

class CartPolePlant : public Plant {
public:
    explicit CartPolePlant(const CartPoleParams& p = {});

    void initialize(double startTime, double stopTime, double v0) override;
    void setInputs(double ref0, double ref1, double vel) override;
    void applyTriggers(const VehicleTriggers& t) override;
    bool doStep(double currentTime, double stepSize) override;
    VehicleOutputs readOutputs() const override;
    Prediction predictHeld(const VehicleOutputs& cur, long fromStep,
                           const Trajectory& ref, long trajOffset,
                           const PredictParams& p) const override;
    double hardBound() const override { return params_.thetaHard; }
    double softBound() const override { return params_.thetaSoft; }

private:
    using State = std::array<double, 4>;          // [x, xdot, theta, thetadot]
    State  integrate(const State& s, double force, double dt) const;  // one RK4 step of `dt`
    double disturbance(long absStep) const;               // the known "track"

    CartPoleParams params_;
    double dt_   = 1e-4;
    long   step_ = 0;          // absolute tick — drives the scenario and metrics

    State           st_{};     // physical state
    VehicleTriggers trig_{};   // triggers latched for the next doStep

    // Chain buffers (mirror the FMU routing). State-carrying up to the
    // estimator; scalar force from the controller on.
    State  sensComp_{}, sensOut_{}, scRec_{}, estComp_{}, estOut_{};
    std::deque<State> scQueue_;   // sensor->cloud network FIFO (values)
    double fbComp_ = 0, fbOut_ = 0, ffComp_ = 0, ffOut_ = 0, aggComp_ = 0, aggOut_ = 0;
    std::deque<double> caQueue_;  // cloud->actuator network FIFO (values)
    double caRec_ = 0, actIn_ = 0, actOut_ = 0;

    // Metrics bookkeeping (theta is the error signal).
    long   metricPeriodTicks_ = 100;
    int    thresholdCntr_ = 0;
    bool   softViolatedThisPeriod_ = false;
    double sumSq_ = 0.0;  long sumN_ = 0;   // running mean of theta^2 -> average_real
    double rolling_ = 0.0;                  // instantaneous theta^2 -> max_roll (MVP)
};

}  // namespace cps
