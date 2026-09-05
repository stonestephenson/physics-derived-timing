#include "trace/Trajectory.h"

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <deque>
#include <fstream>
#include <iterator>
#include <stdexcept>

namespace cps {
namespace {

// Half-width (in ticks) of the finite-difference stencil used to estimate the
// path tangent. The (x,y) trace is piecewise-constant (it jumps every few ms),
// so a ±1 stencil is degenerate; ±200 ticks spans several position updates and
// yields a smooth, robust direction without washing out track curvature.
constexpr long kNormalHalfStencil = 200;

// Read up to `count` whitespace/comma-separated floats from a one-column CSV.
std::vector<float> loadColumn(const std::string& path, long count) {
    std::ifstream ifs(path, std::ios::binary);
    if (!ifs) throw std::runtime_error("Trajectory: cannot open " + path);
    std::string data((std::istreambuf_iterator<char>(ifs)),
                     std::istreambuf_iterator<char>());

    std::vector<float> out;
    out.reserve(static_cast<size_t>(count));
    const char* p = data.c_str();
    char* end = nullptr;
    while (*p) {
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n' || *p == ',') ++p;
        if (!*p) break;
        const double v = std::strtod(p, &end);
        if (end == p) break;  // no progress -> stop
        out.push_back(static_cast<float>(v));
        p = end;
        if (static_cast<long>(out.size()) >= count) break;
    }
    return out;
}

}  // namespace

ProfileInfo profileInfo(Profile p) {
    switch (p) {
        case Profile::V10:   return {"example_v_10",   10.0, 1178000};
        case Profile::V12_5: return {"example_v_12_5", 12.5,  944000};
        case Profile::V15:   return {"example_v_15",   15.0,  786000};
    }
    return {"example_v_10", 10.0, 1178000};
}

const char* profileName(Profile p) {
    switch (p) {
        case Profile::V10:   return "v10";
        case Profile::V12_5: return "v12.5";
        case Profile::V15:   return "v15";
    }
    return "v10";
}

namespace {
ZoneParams g_zoneParams{};   // defaults = the kZone* constants (byte-identical)
}

const ZoneParams& zoneParams() { return g_zoneParams; }
void setZoneParams(const ZoneParams& p) { g_zoneParams = p; }

TrackZone trackZoneFromFf0(float ff0) {
    const float curvature = std::fabs(ff0);
    if (curvature <= kZoneZeroEpsilon) return TrackZone::Z0Straight;
    if (curvature < g_zoneParams.sharpThreshold) return TrackZone::Z1SlightTurn;
    return TrackZone::Z2SharpTurn;
}

TrackZone trackZoneFromRefs(float ff0, float ff1, float curvatureDelta) {
    if (std::fabs(ff1) >= g_zoneParams.laneFf1Threshold ||
        curvatureDelta >= g_zoneParams.laneCurvatureDeltaThreshold) {
        return TrackZone::Z3LaneChange;
    }
    return trackZoneFromFf0(ff0);
}

const char* trackZoneCode(TrackZone zone) {
    switch (zone) {
        case TrackZone::Z0Straight:   return "z0";
        case TrackZone::Z1SlightTurn: return "z1";
        case TrackZone::Z2SharpTurn:  return "z2";
        case TrackZone::Z3LaneChange: return "z3";
    }
    return "z0";
}

const char* trackZoneName(TrackZone zone) {
    switch (zone) {
        case TrackZone::Z0Straight:   return "straight";
        case TrackZone::Z1SlightTurn: return "slight turn";
        case TrackZone::Z2SharpTurn:  return "sharp turn";
        case TrackZone::Z3LaneChange: return "lane change";
    }
    return "straight";
}

std::string Trajectory::defaultExamplesDir() {
#ifdef EXAMPLES_DIR
    return EXAMPLES_DIR;
#else
    return "examples";
#endif
}

std::shared_ptr<Trajectory> Trajectory::load(Profile profile,
                                             const std::string& examplesDir) {
    const ProfileInfo info = profileInfo(profile);
    const std::string dir = examplesDir + "/" + info.dirName;

    std::shared_ptr<Trajectory> t(new Trajectory());
    t->profile_  = profile;
    t->lapSteps_ = info.lapSteps;
    t->peakVel_  = info.peakVelocity;

    t->x_   = loadColumn(dir + "/x_position_track.csv",     info.lapSteps);
    t->y_   = loadColumn(dir + "/y_position_track.csv",     info.lapSteps);
    t->vel_ = loadColumn(dir + "/velocity.csv",             info.lapSteps);
    t->ff0_ = loadColumn(dir + "/feedforward_sequence_0.csv", info.lapSteps);
    t->ff1_ = loadColumn(dir + "/feedforward_sequence_1.csv", info.lapSteps);

    const long need = info.lapSteps;
    auto check = [&](const std::vector<float>& v, const char* name) {
        if (static_cast<long>(v.size()) < need)
            throw std::runtime_error(std::string("Trajectory: ") + name + " in " + dir +
                                     " has fewer rows than the lap length");
    };
    check(t->x_, "x_position_track");
    check(t->y_, "y_position_track");
    check(t->vel_, "velocity");
    check(t->ff0_, "feedforward_sequence_0");
    check(t->ff1_, "feedforward_sequence_1");

    t->computeTrackZones();
    t->computeNormalsAndBounds();
    return t;
}

void Trajectory::computeTrackZones() {
    const long n = lapSteps_;
    const long half = std::min<long>(g_zoneParams.laneHalfWindowTicks, std::max<long>(0, n / 2));
    const long window = 2 * half + 1;
    curvatureDelta_.assign(static_cast<size_t>(n), 0.0f);
    zone_.resize(static_cast<size_t>(n));
    std::vector<unsigned char> laneSeed(static_cast<size_t>(n), 0);

    std::deque<long> maxQ, minQ;
    const long extN = n + 2 * half;
    auto extValue = [&](long extIdx) {
        return ff0_[static_cast<size_t>(wrap(extIdx - half))];
    };

    for (long right = 0; right < extN; ++right) {
        const float val = extValue(right);
        while (!maxQ.empty() && extValue(maxQ.back()) <= val) maxQ.pop_back();
        while (!minQ.empty() && extValue(minQ.back()) >= val) minQ.pop_back();
        maxQ.push_back(right);
        minQ.push_back(right);

        const long left = right - window + 1;
        while (!maxQ.empty() && maxQ.front() < left) maxQ.pop_front();
        while (!minQ.empty() && minQ.front() < left) minQ.pop_front();

        if (right >= window - 1) {
            const long center = right - 2 * half;
            if (center >= 0 && center < n) {
                const float delta = extValue(maxQ.front()) - extValue(minQ.front());
                curvatureDelta_[static_cast<size_t>(center)] = delta;
                const TrackZone seedZone = trackZoneFromRefs(
                    ff0_[static_cast<size_t>(center)],
                    ff1_[static_cast<size_t>(center)],
                    delta);
                laneSeed[static_cast<size_t>(center)] =
                    seedZone == TrackZone::Z3LaneChange ? 1 : 0;
            }
        }
    }

    // Oracle pass: lane-change seeds mark high local curvature activity. Expand
    // them in both directions and bridge short quiet gaps so a whole maneuver is
    // one z3 segment, including the flatter middle between two transition lobes.
    std::vector<int> diff(static_cast<size_t>(n + 1), 0);
    auto addLinear = [&](long lo, long hi) {
        diff[static_cast<size_t>(lo)] += 1;
        diff[static_cast<size_t>(hi + 1)] -= 1;
    };
    auto addCircular = [&](long lo, long hi) {
        if (hi - lo + 1 >= n) {
            addLinear(0, n - 1);
            return;
        }
        const long l = wrap(lo);
        const long r = wrap(hi);
        if (l <= r) {
            addLinear(l, r);
        } else {
            addLinear(l, n - 1);
            addLinear(0, r);
        }
    };

    const long pad = std::min<long>(g_zoneParams.laneOraclePadTicks, std::max<long>(0, n / 2));
    for (long i = 0; i < n; ++i) {
        if (laneSeed[static_cast<size_t>(i)])
            addCircular(i - pad, i + pad);
    }

    std::vector<unsigned char> lane(static_cast<size_t>(n), 0);
    int active = 0;
    bool anyLane = false;
    bool allLane = true;
    for (long i = 0; i < n; ++i) {
        active += diff[static_cast<size_t>(i)];
        lane[static_cast<size_t>(i)] = active > 0 ? 1 : 0;
        anyLane = anyLane || lane[static_cast<size_t>(i)];
        allLane = allLane && lane[static_cast<size_t>(i)];
    }

    if (anyLane && !allLane) {
        const long bridge = std::min<long>(g_zoneParams.laneOracleBridgeTicks, std::max<long>(0, n / 2));
        long start = 0;
        while (start < n && !lane[static_cast<size_t>(start)]) ++start;

        long i = (start + 1) % n;
        while (i != start) {
            if (lane[static_cast<size_t>(i)]) {
                i = (i + 1) % n;
                continue;
            }

            std::vector<long> gap;
            while (!lane[static_cast<size_t>(i)]) {
                gap.push_back(i);
                i = (i + 1) % n;
                if (i == start) break;
            }
            if (i != start && static_cast<long>(gap.size()) <= bridge) {
                for (long idx : gap) lane[static_cast<size_t>(idx)] = 1;
            }
        }
    }

    for (long i = 0; i < n; ++i) {
        zone_[static_cast<size_t>(i)] = lane[static_cast<size_t>(i)]
            ? TrackZone::Z3LaneChange
            : trackZoneFromFf0(ff0_[static_cast<size_t>(i)]);
    }
}

void Trajectory::computeNormalsAndBounds() {
    const long n = lapSteps_;
    nx_.resize(static_cast<size_t>(n));
    ny_.resize(static_cast<size_t>(n));

    min_ = {x_[0], y_[0]};
    max_ = {x_[0], y_[0]};
    Vec2 prevNormal{0.0f, 1.0f};

    for (long i = 0; i < n; ++i) {
        min_.x = std::min(min_.x, x_[i]);
        min_.y = std::min(min_.y, y_[i]);
        max_.x = std::max(max_.x, x_[i]);
        max_.y = std::max(max_.y, y_[i]);

        const Vec2 a = pointAt(i - kNormalHalfStencil);  // wraps around the lap
        const Vec2 b = pointAt(i + kNormalHalfStencil);
        Vec2 nrm = normalized(perp(b - a));
        if (length(nrm) < 0.5f) nrm = prevNormal;  // degenerate -> carry forward
        nx_[i] = nrm.x;
        ny_[i] = nrm.y;
        prevNormal = nrm;
    }
}

}  // namespace cps
