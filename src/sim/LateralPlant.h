// LateralPlant.h — Plant backed by the Bosch LateralMotionControl FMU. A thin
// adapter over FmuInstance (Fmu.h); predictHeld delegates to the ported plant
// model (predictHold, Predictor.h). Behaviorally identical to the pre-Plant
// direct-FMU path — the refactor that introduced Plant must not change any
// Bosch baseline.
#pragma once

#include <memory>
#include <string>

#include "fmu/Fmu.h"
#include "sim/Plant.h"

namespace cps {

class LateralPlant : public Plant {
public:
    LateralPlant(std::shared_ptr<FmuLibrary> lib, const std::string& name);

    void initialize(double startTime, double stopTime, double v0) override;
    void setInputs(double ff0, double ff1, double vel) override;
    void applyTriggers(const VehicleTriggers& t) override;
    bool doStep(double currentTime, double stepSize) override;
    VehicleOutputs readOutputs() const override;
    Prediction predictHeld(const VehicleOutputs& cur, long fromStep,
                           const Trajectory& ref, long trajOffset,
                           const PredictParams& p) const override;
    double hardBound() const override;
    double softBound() const override;

private:
    std::shared_ptr<FmuLibrary>  lib_;   // kept alive for the instance's lifetime
    std::unique_ptr<FmuInstance> fmu_;
};

}  // namespace cps
