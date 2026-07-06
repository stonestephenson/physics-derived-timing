// ZoneBand ("zband") — the PROOF_DRAFT §3.1 proof-object scheduler ZB-F-X,
// implemented so the simulator can attack the Lemma-2b band bounds (the
// analysis had no in-harness adversary before this policy existed).
//
// Rule: strict job-level fixed priority (band, period, vehicle, kind), where
// a job's band was stamped at its RELEASE (TaskModel::releaseIfDue): band 0
// iff the car was within ±θ (240 ms) of a z3 lane-change arc at release AND
// the kind is E/B/M — Feedforward never elevates (it is off the age path;
// PROOF_DRAFT §3.1 "ZB-F"). Bands are never recomputed during a job's life —
// release-stamping is load-bearing for the band RTA (council finding).
//
// Prediction-free: uses no TTV/TTPNR/state — position + the static zone map
// only (the flag arrives via VehicleView::zone_flagged -> Job::band).
#include <algorithm>
#include <memory>
#include <vector>

#include "sched/CorePolicy.h"

namespace cps {

class ZoneBand : public CorePolicy {
public:
    void assign(const std::vector<ReadyJob>& ready, int nCores,
                const std::vector<VehicleView>& /*ctx*/,
                std::vector<int>& chosen) override {
        order_.resize(ready.size());
        for (int i = 0; i < static_cast<int>(ready.size()); ++i) order_[i] = i;

        std::sort(order_.begin(), order_.end(), [&](int a, int b) {
            const ReadyJob& x = ready[a];
            const ReadyJob& y = ready[b];
            if (x.band != y.band)           return x.band < y.band;
            if (x.period_ms != y.period_ms) return x.period_ms < y.period_ms;
            if (x.vehicle != y.vehicle)     return x.vehicle < y.vehicle;
            return x.kind < y.kind;
        });

        const int n = std::min<int>(nCores, static_cast<int>(order_.size()));
        chosen.assign(order_.begin(), order_.begin() + n);
    }
    const char* name() const override { return "ZoneBand"; }

private:
    std::vector<int> order_;
};

std::unique_ptr<CorePolicy> makeZoneBandPolicy() {
    return std::make_unique<ZoneBand>();
}

}  // namespace cps
