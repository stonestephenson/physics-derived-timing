#include "sim/LateralPlant.h"

#include "fmu/FmuVariables.h"  // vr::kHardBound, vr::kSoftBound

namespace cps {

LateralPlant::LateralPlant(std::shared_ptr<FmuLibrary> lib, const std::string& name)
    : lib_(std::move(lib)), fmu_(lib_->instantiate(name)) {}

void LateralPlant::initialize(double startTime, double stopTime, double v0) {
    fmu_->initialize(startTime, stopTime, v0);
}

void LateralPlant::setInputs(double ff0, double ff1, double vel) {
    fmu_->setInputs(ff0, ff1, vel);
}

void LateralPlant::applyTriggers(const VehicleTriggers& t) { fmu_->applyTriggers(t); }

bool LateralPlant::doStep(double currentTime, double stepSize) {
    return fmu_->doStep(currentTime, stepSize);
}

VehicleOutputs LateralPlant::readOutputs() const {
    VehicleOutputs o = fmu_->readOutputs();
    o.act_demand = o.act_out;  // FMU steering is amplitude-unbounded -> applied == demanded
    return o;
}

Prediction LateralPlant::predictHeld(const VehicleOutputs& cur, long fromStep,
                                     const Trajectory& ref, long trajOffset,
                                     const PredictParams& p) const {
    // The ported plant model rolls forward from the FMU's 6-state and the
    // currently applied steering command (identical to the pre-Plant call).
    return predictHold(cur.phys, cur.act_out, fromStep, ref, trajOffset, p);
}

double LateralPlant::hardBound() const { return vr::kHardBound; }
double LateralPlant::softBound() const { return vr::kSoftBound; }

}  // namespace cps
