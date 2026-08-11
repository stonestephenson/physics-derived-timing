// Frontier.cpp — the capacity-frontier contender (--scheduler frontier[-honest]).
// FRONTIER.md S1, v9.
//
// v1-v8 (git history) explored ordering/serialization/anticipation structures.
// Per-vehicle diagnosis at N=19 (FRONTIER.md log) showed they all spend the
// wrong currency: they buy fleet freshness, comfort, and avg-performance —
// dominating aguard on every column — while a handful of cars touch
// PNR-margin 0 inside the z3 lane change and take the hard breaches that gate
// capacity. At ~181% overload the only feasible allocation is aguard's brutal
// one: every core-tick goes to maximizing the fleet's worst-case PNR margin,
// comfort be damned.
//
// v9 therefore keeps aguard's allocation VERBATIM (same theta guard, same
// emergency key (ttpnr, clearance, ttv), same comfort urgency, same InfoSet
// plumbing, all of a vehicle's jobs offered — the multi-core rescue slam is
// the incumbent's rescue accelerator) and changes ONLY two things, each of
// which strictly FREES capacity without redirecting protection:
//
//   1. F demotion + heartbeat: Feedforward (25 ticks, 44% of per-vehicle cloud
//      demand, carries no sensor data) never enters the emergency tier and
//      sorts after E/B/M on comfort ties — it can no longer burn rescue
//      bandwidth. Starved-F (> heartbeat, default 500 ms, env
//      CPS_FRONTIER_FHB_MS) elevates to comfort-top: bounded F staleness is
//      measured ~free (ff-extra probe, FRONTIER.md), indefinite starvation is
//      the §8.7 damage channel.
//   2. Hopeless-job cull: a job that cannot complete before its own next
//      release even if granted every remaining tick is never granted — under
//      kill-and-hold its compute is already forfeit. "now" is estimated as
//      max(releaseStep) over the pool (assign() has no clock); the estimate
//      lags true now, which only under-culls (conservative).
//
// All keys end in the strict static total order (period, vehicle, kind) —
// deterministic across STLs (CLAUDE.md invariant 4).
#include <algorithm>
#include <cstdlib>
#include <string>
#include <vector>

#include "sched/policies/Policies.h"

namespace cps {
namespace {

class FrontierPolicy : public CorePolicy {
public:
    FrontierPolicy(double floorMs, InfoSet info, long fHeartbeatTicks,
                   double guardCapMs)
        : floorMs_(floorMs), info_(info), fHeartbeatTicks_(fHeartbeatTicks),
          guardCapMs_(guardCapMs) {
        fHeartbeatCritTicks_ = 1000;  // 100 ms
        if (const char* s = std::getenv("CPS_FRONTIER_FHB_CRIT_MS")) {
            const long v = std::atol(s);
            if (v >= 20) fHeartbeatCritTicks_ = v * 10;
        }
        // Ablation toggle (FRONTIER.md): with F-demotion disabled this policy
        // reproduces aguard exactly — the validation anchor for the A/B.
        // (The hopeless-job cull was DELETED per council A-M10/17: a proven
        // no-op whose remainingTicks read was oracular under pert.)
        fDemote_ = std::getenv("CPS_FRONTIER_NO_FDEMOTE") == nullptr;
        // Attribution-matrix toggle (FCHANNEL §8 item 11, council D-A2): with
        // RM_ALLOC set, the vehicle-state tiers are replaced by plain
        // rate-monotonic keys while the F rules (zone-aware demotion + tiered
        // heartbeat) stay — the "static zone-indexed F economics under a
        // state-blind allocator" cell. If this cell recovers the capacity
        // win, triage is not the active ingredient.
        rmAlloc_ = std::getenv("CPS_FRONTIER_RM_ALLOC") != nullptr;
        name_ = "Frontier[v12,floor=" + std::to_string(static_cast<int>(floorMs)) +
                "ms,fhb=" + std::to_string(fHeartbeatTicks_ / 10) + "ms" +
                (static_cast<int>(guardCapMs) != 450
                     ? ",cap=" + std::to_string(static_cast<int>(guardCapMs)) + "ms"
                     : "") +
                std::string(fDemote_ ? "" : ",nofdemote") +
                std::string(rmAlloc_ ? ",rm-alloc" : "") +
                (info == InfoSet::Remote ? ",honest]" : "]");
    }

    void assign(const std::vector<ReadyJob>& ready, int nCores,
                const std::vector<VehicleView>& ctx,
                std::vector<int>& chosen) override {
        long nowEst = 0;
        for (const ReadyJob& j : ready) nowEst = std::max(nowEst, j.releaseStep);
        if (lastFDone_.size() != ctx.size()) lastFDone_.assign(ctx.size(), 0);

        struct Key { int tier; double k1, k2, k3; int frank; };
        auto key = [&](const ReadyJob& j) -> Key {
            if (j.vehicle < 0 || j.vehicle >= static_cast<int>(ctx.size()))
                return {1, 0.0, 0.0, 0.0, 0};
            const VehicleView& v = ctx[j.vehicle];
            // v10: F demotion is ZONE-AWARE. The ablation isolated demoted-F as
            // both the entire capacity win (missed 258k->182k, ages 2470->430,
            // soft /7 at N=19) and the entire z3 breach cluster: F carries the
            // reference, and the lane change is precisely where the reference
            // moves fast — a ~500 ms-stale F there steers at the old lane line.
            // Flagged (z3) cars' F keeps full aguard treatment.
            // v12: the residual z1/z2 breaches want moderately-fresh F, not
            // full-rate F — v11's blanket critical-section protection gave
            // back so much capacity that starvation breaches EXPLODED. Instead
            // the heartbeat is tiered: critical sections cap F staleness at
            // ~100 ms (env CPS_FRONTIER_FHB_CRIT_MS), straights at ~500 ms
            // (CPS_FRONTIER_FHB_MS). F demand stays bounded either way.
            const bool isF = j.kind == TaskKind::Feedforward && fDemote_ &&
                             !v.zone_flagged;
            if (isF) {
                const bool crit =
                    info_ == InfoSet::Remote ? v.critical_remote : v.critical;
                const long hb = crit ? fHeartbeatCritTicks_ : fHeartbeatTicks_;
                const long starve = nowEst - lastFDone_[j.vehicle];
                if (starve > hb)  // starved F: comfort-top,
                    return {1, -1.0e6 - static_cast<double>(starve), 0.0, 0.0, 1};
            }
            // Attribution-matrix cell (D-A2): state-blind RM keys, F rules
            // retained — one tier, order via the final (period,vehicle,kind).
            if (rmAlloc_) return {1, 0.0, 0.0, 0.0, isF ? 1 : 0};
            const double theta_v =
                std::min(guardCapMs_, floorMs_ + std::max(60.0, v.age_recent_ms));
            const double ttpnr = predTtpnrMs(v, info_);
            if (!isF && ttpnr < theta_v)
                return {0, ttpnr, predClearanceM(v, info_), predTtvMs(v, info_), 0};
            return {1, -comfortUrgency(v, info_), 0.0, 0.0, isF ? 1 : 0};
        };

        order_.resize(ready.size());
        for (int i = 0; i < static_cast<int>(ready.size()); ++i) order_[i] = i;

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
    double guardCapMs_;
    long fHeartbeatCritTicks_ = 1000;
    bool fDemote_ = true;
    bool rmAlloc_ = false;
    std::string name_;
    std::vector<int> order_;
    std::vector<long> lastFDone_;
};

}  // namespace

std::unique_ptr<CorePolicy> makeFrontierPolicy(double floorMs, InfoSet info,
                                               double guardCapMs) {
    long fhbTicks = 5000;  // 500 ms
    if (const char* s = std::getenv("CPS_FRONTIER_FHB_MS")) {
        const long v = std::atol(s);
        if (v >= 20) fhbTicks = v * 10;
    }
    return std::unique_ptr<CorePolicy>(
        new FrontierPolicy(floorMs, info, fhbTicks, guardCapMs));
}

}  // namespace cps
