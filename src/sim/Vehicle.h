// Vehicle.h — one simulated vehicle: its plant (the controlled system plus its
// in-the-loop control chain), the shared reference trajectory, a start offset
// onto the reference, its task set, and latest outputs.
#pragma once

#include <memory>

#include "fmu/FmuTypes.h"
#include "sched/TaskModel.h"
#include "sim/Plant.h"
#include "trace/Trajectory.h"

namespace cps {

struct Vehicle {
    std::unique_ptr<Plant>       plant;
    std::shared_ptr<Trajectory>  traj;
    long           startOffset = 0;   // ticks into the reference at sim t=0
    TaskSet        taskSet;
    VehicleOutputs out;               // latest plant outputs
    double         curVel = 0.0;      // velocity input applied this tick
};

}  // namespace cps
