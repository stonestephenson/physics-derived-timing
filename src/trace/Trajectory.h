// Trajectory.h — loads one velocity profile's reference traces (the closed
// racetrack centerline plus the per-tick FMU inputs) from the examples CSVs.
//
// The (x,y) trace is the *expected/reference* path. The FMU is fed velocity and
// feedforward references from the same time base (1:1 by tick at 0.1 ms). The
// actual driven path is reconstructed elsewhere as point + e_y * normal.
//
// All accessors wrap modulo the lap length, so the track loops seamlessly and a
// vehicle can be staggered onto the track with an integer start offset.
#pragma once

#include <memory>
#include <string>
#include <vector>

#include "core/Vec2.h"

namespace cps {

enum class Profile { V10, V12_5, V15 };

// Curvature-based track partition used by analysis exports and the visualizer.
// ff_ref_0 is treated as a curvature proxy. z3 is a curvature-transition /
// lane-change proxy: it uses ff_ref_1, a short-window curvature range, and an
// oracle-style lookahead/lookbehind pass so the whole maneuver is tagged, not
// only the highest-derivative samples.
enum class TrackZone {
    Z0Straight = 0,
    Z1SlightTurn = 1,
    Z2SharpTurn = 2,
    Z3LaneChange = 3
};
inline constexpr float kZoneZeroEpsilon = 1e-6f;
inline constexpr float kZoneSharpThreshold = 0.0215f;
inline constexpr float kZoneLaneFf1Threshold = 0.0035f;
inline constexpr float kZoneLaneCurvatureDeltaThreshold = 0.0040f;
inline constexpr long  kZoneLaneHalfWindowTicks = 500;  // +/- 50 ms at 0.1 ms/tick
inline constexpr long  kZoneLaneOraclePadTicks = 1000;  // +/- 100 ms around seeds
inline constexpr long  kZoneLaneOracleBridgeTicks = 3500;  // fill gaps up to 350 ms

TrackZone trackZoneFromFf0(float ff0);
TrackZone trackZoneFromRefs(float ff0, float ff1, float curvatureDelta);
const char* trackZoneCode(TrackZone zone);
const char* trackZoneName(TrackZone zone);

struct ProfileInfo {
    const char* dirName;
    double      peakVelocity;  // m/s
    long        lapSteps;      // ticks (0.1 ms) for one full lap
};
ProfileInfo profileInfo(Profile p);
const char* profileName(Profile p);

class Trajectory {
public:
    // Load all six CSVs for `profile` from `examplesDir`. Throws on failure.
    static std::shared_ptr<Trajectory> load(
        Profile profile, const std::string& examplesDir = defaultExamplesDir());

    static std::string defaultExamplesDir();

    Profile profile()      const { return profile_; }
    long    lapSteps()     const { return lapSteps_; }
    double  peakVelocity() const { return peakVel_; }

    // Map any (possibly offset/overrun) tick into [0, lapSteps).
    long wrap(long idx) const {
        idx %= lapSteps_;
        return idx < 0 ? idx + lapSteps_ : idx;
    }

    struct Inputs { float ff0, ff1, vel; };
    Inputs inputsAt(long step) const {
        const long i = wrap(step);
        return {ff0_[i], ff1_[i], vel_[i]};
    }
    Vec2 pointAt(long step)  const { const long i = wrap(step); return {x_[i], y_[i]}; }
    Vec2 normalAt(long step) const { const long i = wrap(step); return {nx_[i], ny_[i]}; }
    float curvatureDeltaAt(long step) const { return curvatureDelta_[wrap(step)]; }
    TrackZone zoneAt(long step) const { return zone_[wrap(step)]; }

    // AABB of one lap, for camera framing.
    Vec2 minBound() const { return min_; }
    Vec2 maxBound() const { return max_; }

private:
    Trajectory() = default;
    void computeTrackZones();
    void computeNormalsAndBounds();

    Profile profile_ = Profile::V10;
    long    lapSteps_ = 0;
    double  peakVel_  = 0.0;
    std::vector<float> x_, y_, vel_, ff0_, ff1_;  // length == lapSteps_
    std::vector<float> nx_, ny_;                  // unit path normal per tick
    std::vector<float> curvatureDelta_;           // local max(ff0)-min(ff0)
    std::vector<TrackZone> zone_;                 // one per reference tick
    Vec2 min_{}, max_{};
};

}  // namespace cps
