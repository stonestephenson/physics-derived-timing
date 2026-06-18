// Plant.h — abstraction over a controlled physical system together with its
// in-the-loop control chain. The Bosch lateral-motion FMU (LateralPlant) and
// the cart-pole (CartPolePlant) both implement it, so the scheduler, the
// data-age task model, and the analytical bound apply UNCHANGED to either: the
// timing framework is plant-agnostic, which is the generalization thesis
// expressed in code.
//
// Driven each base tick in the FMU co-simulation order (see Fmu.h):
//   setInputs -> applyTriggers -> doStep -> readOutputs.
#pragma once

#include "fmu/FmuTypes.h"   // VehicleTriggers, VehicleOutputs
#include "sim/Predictor.h"  // Prediction, PredictParams (pulls in Trajectory)

namespace cps {

enum class PlantKind { Lateral, CartPole };

class Plant {
public:
    virtual ~Plant() = default;

    virtual void initialize(double startTime, double stopTime, double v0) = 0;
    virtual void setInputs(double ref0, double ref1, double vel) = 0;
    virtual void applyTriggers(const VehicleTriggers& t) = 0;
    virtual bool doStep(double currentTime, double stepSize) = 0;
    virtual VehicleOutputs readOutputs() const = 0;

    // Roll THIS plant's own dynamics forward from its current state, holding the
    // applied command, to get TTV/TTPNR (PREDICTOR.md). `cur` is the latest
    // readOutputs() (passed to avoid a re-read); `ref`/`trajOffset` give the
    // known future reference. The result struct is plant-agnostic.
    virtual Prediction predictHeld(const VehicleOutputs& cur, long fromStep,
                                   const Trajectory& ref, long trajOffset,
                                   const PredictParams& p) const = 0;

    // Bounds on the plant's error signal (VehicleOutputs::e_y_real): 0.8 / 0.2 m
    // for the car; theta_max / theta_soft for the pole. Used by the metrics and
    // the predictor instead of the hard-coded vr::k*Bound.
    virtual double hardBound() const = 0;
    virtual double softBound() const = 0;
};

}  // namespace cps
