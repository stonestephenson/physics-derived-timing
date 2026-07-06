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
        // Run-length encode zoneAt over one lap (circular: merge wrap-around run).
        std::vector<std::pair<int, long>> runs;  // (zone, len)
        int z0 = static_cast<int>(traj->zoneAt(0));
        int cur = z0;
        long len = 0;
        for (long i = 0; i < lap; ++i) {
            int z = static_cast<int>(traj->zoneAt(i));
            if (z == cur) { ++len; continue; }
            runs.push_back({cur, len});
            cur = z; len = 1;
        }
        runs.push_back({cur, len});
        if (runs.size() > 1 && runs.front().first == runs.back().first) {
            runs.front().second += runs.back().second;  // circular merge
            runs.pop_back();
        }
        std::map<int, long> total;
        std::map<int, int> count;
        for (auto& r : runs) { total[r.first] += r.second; count[r.first]++; }
        for (auto& t : total)
            std::printf("  z%d: K=%d arcs, total L=%ld ticks (%.2f%% of lap)\n",
                        t.first, count[t.first], t.second,
                        100.0 * t.second / lap);
        std::printf("  z3 arcs (start_tick,len):");
        long pos = 0;
        for (auto& r : runs) {
            if (r.first == 3) std::printf(" (%ld,%ld)", pos, r.second);
            pos += r.second;
        }
        std::printf("\n\n");
    }
    return 0;
}
