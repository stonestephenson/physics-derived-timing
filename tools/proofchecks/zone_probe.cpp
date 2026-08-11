// zone_probe.cpp — standalone read-only probe: dumps the zone run-length
// structure (arc count K, per-arc lengths, totals) per profile, for Lemma 1
// (PROOF_DRAFT §0 route-geometry table). Links the repo's Trajectory.cpp
// unchanged; touches nothing in the repo.
//
// Build + run (from the repo root):
//   c++ -std=c++17 -O2 -I src -o /tmp/zone_probe \
//       tools/proofchecks/zone_probe.cpp src/trace/Trajectory.cpp
//   /tmp/zone_probe            # needs the examples/ CSVs (default dir)
#include <cstdio>
#include <map>
#include <vector>

#include "trace/Trajectory.h"

using namespace cps;

int main(int argc, char** argv) {
    const char* dir = argc > 1 ? argv[1] : nullptr;
    for (Profile p : {Profile::V10, Profile::V12_5, Profile::V15}) {
        auto traj = dir ? Trajectory::load(p, dir) : Trajectory::load(p);
        const long lap = traj->lapSteps();
        std::printf("profile %s  lap=%ld ticks (%.1f s)\n", profileName(p), lap,
                    lap * 1e-4);
        // Run-length encode zoneAt over one lap, keeping each run's TRUE start
        // tick (circular: the wrap-around run and the first run are one arc).
        struct Run { int zone; long start; long len; };
        std::vector<Run> runs;
        int cur = static_cast<int>(traj->zoneAt(0));
        long start = 0, len = 0;
        for (long i = 0; i < lap; ++i) {
            int z = static_cast<int>(traj->zoneAt(i));
            if (z == cur) { ++len; continue; }
            runs.push_back({cur, start, len});
            cur = z; start = i; len = 1;
        }
        runs.push_back({cur, start, len});
        if (runs.size() > 1 && runs.front().zone == runs.back().zone) {
            // Circular merge: fold the wrap-around tail into the first run, but
            // anchor the merged arc at the tail run's TRUE start (lap - tail_len)
            // so it reads as a wrapping arc at its real position. Anchoring at 0
            // (the old code) rotated every downstream start late by tail_len.
            runs.front().start = runs.back().start;
            runs.front().len  += runs.back().len;
            runs.pop_back();
        }
        std::map<int, long> total;
        std::map<int, int> count;
        for (auto& r : runs) { total[r.zone] += r.len; count[r.zone]++; }
        for (auto& t : total)
            std::printf("  z%d: K=%d arcs, total L=%ld ticks (%.2f%% of lap)\n",
                        t.first, count[t.first], t.second,
                        100.0 * t.second / lap);
        std::printf("  z3 arcs (start_tick,len):");
        for (auto& r : runs)
            if (r.zone == 3) std::printf(" (%ld,%ld)", r.start, r.len);
        std::printf("\n");
        // Per-zone reference kinematics (FCHANNEL §10 qzone-collapse leg):
        // ff0 = kappa, ff1 = dkappa/ds (reviewer B verified the spatial-
        // gradient reading numerically). max(v^2) prices a zero-age curvature
        // ERROR eps (Delta a_ref = v^2 * eps); max(v^3*|ff1|) prices a time
        // DELAY D (Delta a_ref = v^3 * |dkappa/ds| * D) — the first-order
        // A_F_lb model the collapse experiment tests.
        struct K { double vSum = 0, vMax = 0, ff0Max = 0, ff1Max = 0,
                          v2Max = 0, v3ff1Max = 0; long n = 0; };
        std::map<int, K> kin;
        for (long i = 0; i < lap; ++i) {
            auto in = traj->inputsAt(i);
            K& k = kin[static_cast<int>(traj->zoneAt(i))];
            const double v = in.vel, f0 = std::fabs(in.ff0),
                         f1 = std::fabs(in.ff1);
            k.vSum += v; ++k.n;
            if (v > k.vMax) k.vMax = v;
            if (f0 > k.ff0Max) k.ff0Max = f0;
            if (f1 > k.ff1Max) k.ff1Max = f1;
            if (v * v > k.v2Max) k.v2Max = v * v;
            if (v * v * v * f1 > k.v3ff1Max) k.v3ff1Max = v * v * v * f1;
        }
        for (auto& [z, k] : kin)
            std::printf("  z%d kin: v mean=%.2f max=%.2f | max|ff0|=%.5f "
                        "max|ff1|=%.5f | max(v^2)=%.1f max(v^3*|ff1|)=%.3f\n",
                        z, k.vSum / k.n, k.vMax, k.ff0Max, k.ff1Max, k.v2Max,
                        k.v3ff1Max);
        std::printf("\n");
    }
    return 0;
}
