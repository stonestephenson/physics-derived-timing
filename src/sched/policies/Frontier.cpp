// Frontier.cpp — the capacity-frontier contender (--scheduler frontier[-honest]).
// FRONTIER.md S1 "triage+": AdaptiveGuard's two-tier guarded triage with the
// council-identified ordering defects fixed. v1 keeps aguard's tier ASSIGNMENT
// bit-for-bit (same theta formula, same emergency key, same comfort urgency, same
// InfoSet plumbing) so an A/B against aguard isolates the four mechanism changes:
//
//   1. Chain-head serialization: each vehicle offers only its earliest
//      unfinished chain job among {E, B, M} (enum order matches chain order once
//      F is excluded). A vehicle can no longer occupy several cores with jobs
//      that cannot advance its loop-closing Merger — and B->M run in sequence,
//      not in parallel reading a stale register.
//   2. F demotion + heartbeat: Feedforward (25 ticks, carries no sensor data)
//      never rides its vehicle's emergency priority — it is comfort-tier and
//      last within its vehicle — EXCEPT when starved past the heartbeat
//      (default 500 ms, env CPS_FRONTIER_FHB_MS), which elevates it above
//      comfort. Bounded F staleness is measured ~free (FRONTIER.md log,
//      ff-extra probe); indefinite starvation is the known §8.7 damage channel.
//   3. Finish-line tier: a started job within 5 ticks of completion outranks
//      all comfort work — 0.5 ms spent now saves the whole job from the
//      kill-and-hold reset at its next release.
//   4. Hopeless-job cull: a job that cannot finish before its own next release
//      even if granted every remaining tick (nowEst + remaining > deadline) is
//      never granted — its compute is already forfeit under kill-and-hold.
//
// "now" is estimated as max(releaseStep) over the pool (assign() has no clock);
// the estimate lags true now by < one E period, which only makes cull/admission
// decisions conservative. All keys end in the strict static total order
// (period, vehicle, kind) — deterministic across STLs (CLAUDE.md invariant 4).
#include <algorithm>
#include <cstdlib>
#include <string>
#include <vector>

#include "sched/policies/Policies.h"

namespace cps {
namespace {

constexpr long kFinishLineTicks = 5;    // started && remaining <= this => rescue it

class FrontierPolicy : public CorePolicy {
public:
    FrontierPolicy(double floorMs, InfoSet info, long fHeartbeatTicks)
        : floorMs_(floorMs), info_(info), fHeartbeatTicks_(fHeartbeatTicks) {
        name_ = "Frontier[floor=" + std::to_string(static_cast<int>(floorMs)) + "ms,fhb=" +
                std::to_string(fHeartbeatTicks_ / 10) + "ms" +
                (info == InfoSet::Remote ? ",honest]" : "]");
    }

    void assign(const std::vector<ReadyJob>& ready, int nCores,
                const std::vector<VehicleView>& ctx,
                std::vector<int>& chosen) override {
        long nowEst = 0;
        for (const ReadyJob& j : ready) nowEst = std::max(nowEst, j.releaseStep);

        // Chain head per vehicle: smallest TaskKind among ready {E,B,M} jobs
        // (Estimator=1 < Controller=2 < Merger=4; Feedforward=3 excluded).
        headKind_.assign(ctx.size(), 99);
        for (const ReadyJob& j : ready) {
            if (j.vehicle < 0 || j.vehicle >= static_cast<int>(ctx.size())) continue;
            if (j.kind == TaskKind::Feedforward) continue;
            headKind_[j.vehicle] =
                std::min(headKind_[j.vehicle], static_cast<int>(j.kind));
        }
        if (lastFDone_.size() != ctx.size()) lastFDone_.assign(ctx.size(), 0);

        struct Key { int tier; double k1, k2, k3; int frank; };
        auto key = [&](const ReadyJob& j) -> Key {
            if (j.vehicle < 0 || j.vehicle >= static_cast<int>(ctx.size()))
                return {2, 0.0, 0.0, 0.0, 0};
            const VehicleView& v = ctx[j.vehicle];
            const bool isF = j.kind == TaskKind::Feedforward;
            // Finish line: rescue near-done started work from the kill reset.
            if (j.started && j.remainingTicks <= kFinishLineTicks)
                return {1, static_cast<double>(j.remainingTicks), 0.0, 0.0, 0};
            if (isF) {
                const long starve = nowEst - lastFDone_[j.vehicle];
                if (starve > fHeartbeatTicks_)  // starved F: elevate, oldest first
                    return {1, -static_cast<double>(starve), 0.0, 0.0, 1};
            }
            // aguard's tier assignment, verbatim (A/B isolation).
            const double theta_v =
                std::min(450.0, floorMs_ + std::max(60.0, v.age_recent_ms));
            const double ttpnr = predTtpnrMs(v, info_);
            if (!isF && ttpnr < theta_v)
                return {0, ttpnr, predClearanceM(v, info_), predTtvMs(v, info_), 0};
            return {2, -comfortUrgency(v, info_), 0.0, 0.0, isF ? 1 : 0};
        };

        order_.clear();
        for (int i = 0; i < static_cast<int>(ready.size()); ++i) {
            const ReadyJob& j = ready[i];
            // Hopeless cull: cannot complete before its next release.
            if (nowEst + j.remainingTicks > j.deadlineStep) continue;
            // Chain-head serialization for E/B/M.
            if (j.kind != TaskKind::Feedforward && j.vehicle >= 0 &&
                j.vehicle < static_cast<int>(ctx.size()) &&
                static_cast<int>(j.kind) != headKind_[j.vehicle])
                continue;
            order_.push_back(i);
        }

        std::sort(order_.begin(), order_.end(), [&](int a, int b) {
            const Key ka = key(ready[a]);
            const Key kb = key(ready[b]);
            if (ka.tier != kb.tier)   return ka.tier < kb.tier;
            if (ka.k1 != kb.k1)       return ka.k1 < kb.k1;
            if (ka.k2 != kb.k2)       return ka.k2 < kb.k2;
            if (ka.k3 != kb.k3)       return ka.k3 < kb.k3;
            if (ka.frank != kb.frank) return ka.frank < kb.frank;
            if (ready[a].period_ms != ready[b].period_ms)
                return ready[a].period_ms < ready[b].period_ms;
            if (ready[a].vehicle != ready[b].vehicle)
                return ready[a].vehicle < ready[b].vehicle;
            return ready[a].kind < ready[b].kind;
        });

        const int n = std::min<int>(nCores, static_cast<int>(order_.size()));
        chosen.assign(order_.begin(), order_.begin() + n);

        // F-completion bookkeeping: a granted F at 1 remaining tick finishes now.
        for (int idx = 0; idx < n; ++idx) {
            const ReadyJob& j = ready[chosen[idx]];
            if (j.kind == TaskKind::Feedforward && j.remainingTicks <= 1 &&
                j.vehicle >= 0 && j.vehicle < static_cast<int>(lastFDone_.size()))
                lastFDone_[j.vehicle] = nowEst;
        }
    }
    const char* name() const override { return name_.c_str(); }

private:
    double floorMs_;
    InfoSet info_;
    long fHeartbeatTicks_;
    std::string name_;
    std::vector<int> order_;
    std::vector<int> headKind_;
    std::vector<long> lastFDone_;
};

}  // namespace

std::unique_ptr<CorePolicy> makeFrontierPolicy(double floorMs, InfoSet info) {
    long fhbTicks = 5000;  // 500 ms
    if (const char* s = std::getenv("CPS_FRONTIER_FHB_MS")) {
        const long v = std::atol(s);
        if (v >= 20) fhbTicks = v * 10;
    }
    return std::unique_ptr<CorePolicy>(new FrontierPolicy(floorMs, info, fhbTicks));
}

}  // namespace cps
