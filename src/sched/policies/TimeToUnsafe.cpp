// TimeToUnsafe.cpp — predictive core arbitration on physical deadlines
// (--scheduler ttu). The Route B scheduler.
//
// Ranks vehicles by how soon scheduling stops mattering: primary key is
// time-to-point-of-no-return (TTPNR — after this instant, even a fresh
// command under the assumed steering limit cannot keep |e_y| < 0.8),
// tie-broken by time-to-violation (TTV — when |e_y| crosses 0.8 under the
// held command), then by the strict (period, vehicle, kind) order. Both
// predictions come from the harness-side plant rollouts (PREDICTOR.md) via
// VehicleView; values at the horizon mean "relaxed".
//
// Past-PNR cars (ttpnr_ms == 0): by default maximally urgent — the real
// plant's steering is unbounded, so the controller may still recover them,
// and deprioritizing would manufacture crashes. With triage=true they drop
// to the bottom instead (rescue-vs-triage experiment; --triage flag).
#include <algorithm>
#include <string>
#include <vector>

#include "sched/policies/Policies.h"

namespace cps {
namespace {

class TimeToUnsafePolicy : public CorePolicy {
public:
    TimeToUnsafePolicy(bool triage, InfoSet info) : triage_(triage), info_(info) {
        name_ = "TimeToUnsafe";
        if (info == InfoSet::Remote || triage) {
            name_ += "[";
            if (info == InfoSet::Remote) name_ += triage ? "honest," : "honest";
            if (triage) name_ += "triage";
            name_ += "]";
        }
    }

    void assign(const std::vector<ReadyJob>& ready, int nCores,
                const std::vector<VehicleView>& ctx,
                std::vector<int>& chosen) override {
        auto key = [&](const ReadyJob& j) -> double {
            if (j.vehicle < 0 || j.vehicle >= static_cast<int>(ctx.size()))
                return 1e18;
            const VehicleView& v = ctx[j.vehicle];
            if (triage_ && predTtpnrMs(v, info_) <= 0.0) return 1e18;  // unsavable
            return predTtpnrMs(v, info_);  // smaller = closer to point of no return
        };

        order_.resize(ready.size());
        for (int i = 0; i < static_cast<int>(ready.size()); ++i) order_[i] = i;

        std::sort(order_.begin(), order_.end(), [&](int a, int b) {
            const double ka = key(ready[a]);
            const double kb = key(ready[b]);
            if (ka != kb) return ka < kb;            // soonest deadline first
            const double ta = predTtvMs(ctx[ready[a].vehicle], info_);
            const double tb = predTtvMs(ctx[ready[b].vehicle], info_);
            if (ta != tb) return ta < tb;            // then soonest violation
            // Then the strict static order shared by all FP policies.
            if (ready[a].period_ms != ready[b].period_ms)
                return ready[a].period_ms < ready[b].period_ms;
            if (ready[a].vehicle != ready[b].vehicle)
                return ready[a].vehicle < ready[b].vehicle;
            return ready[a].kind < ready[b].kind;
        });

        const int n = std::min<int>(nCores, static_cast<int>(order_.size()));
        chosen.assign(order_.begin(), order_.begin() + n);
    }
    const char* name() const override { return name_.c_str(); }

private:
    bool triage_;
    InfoSet info_;
    std::string name_;
    std::vector<int> order_;
};

}  // namespace

std::unique_ptr<CorePolicy> makeTimeToUnsafePolicy(bool triage, InfoSet info) {
    return std::unique_ptr<CorePolicy>(new TimeToUnsafePolicy(triage, info));
}

}  // namespace cps
