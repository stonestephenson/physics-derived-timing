// EskipProbe.cpp — INSTRUMENT, not a contender (--scheduler eskip).
// Rate-monotonic arbitration with per-vehicle Estimator decimation: only every
// k-th E release (by release index) is ever granted a core; skipped E jobs are
// never started, so they die unstarted at their next release (a miss with zero
// wasted compute). B/F/M/etc. are served normally at full rate.
//
// Purpose (FRONTIER.md, council crux): measure REFRESH-RATE tolerance as
// distinct from the delay tolerance A(zone) was calibrated with. At N=1 an
// E cadence of k*10 ms produces a delivered-age sawtooth comparable to the
// §8.2 envelope's constant injected delay — if equal measured age_path breaches
// where the delay injection did not (or vice versa), cadence-staleness and
// transport-staleness are NOT interchangeable and no cadence-based scheduler
// may lean on the A(zone)/envelope tables.
//
// k comes from env CPS_ESKIP_K (default 11 ~= 110 ms cadence); the decision is
// a pure function of releaseStep, so it is deterministic and stateless.
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <string>
#include <vector>

#include "sched/policies/Policies.h"

namespace cps {
namespace {

class EskipProbePolicy : public CorePolicy {
public:
    explicit EskipProbePolicy(int k) : k_(k < 1 ? 1 : k) {
        name_ = "EskipProbe[k=" + std::to_string(k_) + "]";
    }

    void assign(const std::vector<ReadyJob>& ready, int nCores,
                const std::vector<VehicleView>& /*ctx*/,
                std::vector<int>& chosen) override {
        order_.clear();
        for (int i = 0; i < static_cast<int>(ready.size()); ++i) {
            const ReadyJob& j = ready[i];
            if (j.kind == TaskKind::Estimator && !allowedE(j)) continue;
            order_.push_back(i);
        }
        std::sort(order_.begin(), order_.end(), [&](int a, int b) {
            const ReadyJob& x = ready[a];
            const ReadyJob& y = ready[b];
            if (x.period_ms != y.period_ms) return x.period_ms < y.period_ms;
            if (x.vehicle != y.vehicle)     return x.vehicle < y.vehicle;
            return x.kind < y.kind;
        });
        const int n = std::min<int>(nCores, static_cast<int>(order_.size()));
        chosen.assign(order_.begin(), order_.begin() + n);
    }
    const char* name() const override { return name_.c_str(); }

private:
    bool allowedE(const ReadyJob& j) const {
        const long periodTicks = std::lround(j.period_ms * 10.0);  // 0.1 ms ticks
        if (periodTicks <= 0) return true;
        return (j.releaseStep / periodTicks) % k_ == 0;
    }

    int k_;
    std::string name_;
    std::vector<int> order_;
};

}  // namespace

std::unique_ptr<CorePolicy> makeEskipProbePolicy() {
    int k = 11;
    if (const char* s = std::getenv("CPS_ESKIP_K")) {
        const int v = std::atoi(s);
        if (v >= 1) k = v;
    }
    return std::unique_ptr<CorePolicy>(new EskipProbePolicy(k));
}

}  // namespace cps
