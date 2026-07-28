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
        if (lastFDone_.size() != ctx.size()) lastFDone_.assign(ctx.size(), 0);
        if (lastEDone_.size() != ctx.size()) lastEDone_.assign(ctx.size(), -1);

        // Chain head per vehicle (v2). v1 offered the upstream-most pending job
        // (E<B<M), but E releases 2x as often as B/M, so under contention E was
        // ALWAYS pending and B/M never became the head — commands never
        // published and N=19 collapsed to 87 s ages. v2 offers the job that
        // advances command delivery: B once its fresh E input exists, M once B
        // is out of the way — and a kill-deadline guard forces B/M through on
        // stale upstream data (aguard's normal mode) near end-of-window rather
        // than starving the loop to preserve pipeline purity.
        const ReadyJob* eJob;
        const ReadyJob* bJob;
        const ReadyJob* mJob;
        headKind_.assign(ctx.size(), 99);
        eByV_.assign(ctx.size(), -1);
        bByV_.assign(ctx.size(), -1);
        mByV_.assign(ctx.size(), -1);
        for (int i = 0; i < static_cast<int>(ready.size()); ++i) {
            const ReadyJob& j = ready[i];
            if (j.vehicle < 0 || j.vehicle >= static_cast<int>(ctx.size())) continue;
            if (j.kind == TaskKind::Estimator)  eByV_[j.vehicle] = i;
            if (j.kind == TaskKind::Controller) bByV_[j.vehicle] = i;
            if (j.kind == TaskKind::Merger)     mByV_[j.vehicle] = i;
        }
        constexpr long kKillGuardTicks = 100;  // 10 ms: half a B/M window
        auto hopeless = [&](const ReadyJob* j) {
            return j != nullptr && nowEst + j->remainingTicks > j->deadlineStep;
        };
        for (int v = 0; v < static_cast<int>(ctx.size()); ++v) {
            // v3: a culled (unfinishable) job must not hold the head slot — it
            // stays in the pool until its kill, and v1/v2 let it zombie the
            // vehicle's offer for the tail of every window under contention
            // (the N=19 starvation runaway). Fall through to the next
            // serviceable chain job instead.
            eJob = eByV_[v] >= 0 && !hopeless(&ready[eByV_[v]]) ? &ready[eByV_[v]] : nullptr;
            bJob = bByV_[v] >= 0 && !hopeless(&ready[bByV_[v]]) ? &ready[bByV_[v]] : nullptr;
            mJob = mByV_[v] >= 0 && !hopeless(&ready[mByV_[v]]) ? &ready[mByV_[v]] : nullptr;
            const bool mUrgent =
                mJob && mJob->deadlineStep - nowEst <= kKillGuardTicks;
            const bool bUrgent =
                bJob && bJob->deadlineStep - nowEst <= kKillGuardTicks;
            if (mJob && (mUrgent || (!bJob && lastEDone_[v] >= 0)))
                headKind_[v] = static_cast<int>(TaskKind::Merger);
            else if (bJob && (bUrgent || lastEDone_[v] >= bJob->releaseStep ||
                              bJob->started))
                headKind_[v] = static_cast<int>(TaskKind::Controller);
            else if (eJob)
                headKind_[v] = static_cast<int>(TaskKind::Estimator);
            else if (bJob)
                headKind_[v] = static_cast<int>(TaskKind::Controller);
            else if (mJob)
                headKind_[v] = static_cast<int>(TaskKind::Merger);
        }

        struct Key { int tier; double k1, k2, k3, k4; int frank; };
        auto key = [&](const ReadyJob& j) -> Key {
            if (j.vehicle < 0 || j.vehicle >= static_cast<int>(ctx.size()))
                return {2, 0.0, 0.0, 0.0, 0.0, 0};
            const VehicleView& v = ctx[j.vehicle];
            const bool isF = j.kind == TaskKind::Feedforward;
            // Finish line: rescue near-done started work from the kill reset.
            if (j.started && j.remainingTicks <= kFinishLineTicks)
                return {2, static_cast<double>(j.remainingTicks), 0.0, 0.0, 0.0, 0};
            if (isF) {
                const long starve = nowEst - lastFDone_[j.vehicle];
                if (starve > fHeartbeatTicks_)
                    // v3: starved F elevates to comfort-TOP (beats every normal
                    // comfort score, ~0-10) but never outranks another car's
                    // loop-closing head via tier.
                    return {3, -1.0e6 - static_cast<double>(starve), 0.0, 0.0,
                            0.0, 1};
            }
            // v6: aguard's theta restored verbatim. v5 capped the age term at
            // one chain latency and mass-casualtied (29,904 hard at N=19): the
            // saturating 450 ms guard is load-bearing EARLY WARNING under
            // honest predictions — by the time ttpnr_est crosses a thin guard,
            // the margin-adjusted rescue no longer fits. Zone anticipation is
            // instead guaranteed via a reserved core slot (see selection).
            const double theta_v =
                std::min(450.0, floorMs_ + std::max(60.0, v.age_recent_ms));
            const double ttpnr = predTtpnrMs(v, info_);
            if (!isF && ttpnr < theta_v)
                // v7: tier-0 ties break by LARGEST error, not most-starved.
                // v3's age rotation equalized staleness while letting error
                // drift — cars entered z3 0.3-0.5 m off-line and no amount of
                // in-zone freshness recovers that (the good-entry
                // precondition). Error is the physical currency; e_y is the
                // InfoSet-correct field (est under honest).
                return {0, ttpnr, predClearanceM(v, info_), predTtvMs(v, info_),
                        -std::fabs(info_ == InfoSet::Remote ? v.e_y_est
                                                            : v.e_y_real),
                        0};
            // v4/v5: anticipatory zone service, now its own tier directly under
            // emergency: zone_flagged (map knowledge, z3 +/- 240 ms) cars'
            // chains run before all comfort work so they enter the lane change
            // fresh (good entry). Ordered by TTPNR within the tier.
            if (!isF && v.zone_flagged)
                return {1, ttpnr, -std::max(0.0, v.age_recent_ms), 0.0, 0.0, 0};
            return {3, -comfortUrgency(v, info_), 0.0, 0.0, 0.0, isF ? 1 : 0};
        };

        order_.clear();
        for (int i = 0; i < static_cast<int>(ready.size()); ++i) {
            const ReadyJob& j = ready[i];
            // Hopeless cull: cannot complete before its next release.
            if (nowEst + j.remainingTicks > j.deadlineStep) continue;
            // v8: E is ALWAYS offered when pending — serializing it behind the
            // B->M cycle throttled continuously-served cars to a >=20 ms
            // effective E cadence, which the eskip crux showed is the filter-
            // breakage knife edge (k=2 marginal, k=3 catastrophic). The v1-v7
            // z3 hard frames were that mechanism firing mid-lane-change.
            // B/M stay single-file behind the head (fresh-read pipeline, no
            // multi-core hogging); F is handled by its own rules.
            if ((j.kind == TaskKind::Controller || j.kind == TaskKind::Merger) &&
                j.vehicle >= 0 && j.vehicle < static_cast<int>(ctx.size()) &&
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
            if (ka.k4 != kb.k4)       return ka.k4 < kb.k4;
            if (ka.frank != kb.frank) return ka.frank < kb.frank;
            if (ready[a].period_ms != ready[b].period_ms)
                return ready[a].period_ms < ready[b].period_ms;
            if (ready[a].vehicle != ready[b].vehicle)
                return ready[a].vehicle < ready[b].vehicle;
            return ready[a].kind < ready[b].kind;
        });

        // v6: reserved-slot selection. Strict tier priority let a saturated
        // emergency tier (theta pinned at 450 under load) consume all cores
        // and starve zone anticipation (v4: z3 hard frames unchanged). One
        // slot is guaranteed to the best flagged-zone (tier 1) job whenever
        // one exists; the remaining slots follow the global order.
        const int n = std::min<int>(nCores, static_cast<int>(order_.size()));
        chosen.clear();
        int flaggedPick = -1;
        for (int oi = 0; oi < static_cast<int>(order_.size()); ++oi) {
            if (key(ready[order_[oi]]).tier == 1) { flaggedPick = order_[oi]; break; }
        }
        if (flaggedPick >= 0 && n > 0) chosen.push_back(flaggedPick);
        for (int oi = 0;
             oi < static_cast<int>(order_.size()) &&
             static_cast<int>(chosen.size()) < n;
             ++oi) {
            if (order_[oi] == flaggedPick) continue;
            chosen.push_back(order_[oi]);
        }

        // Completion bookkeeping: a granted job at 1 remaining tick finishes now.
        for (int idx = 0; idx < n; ++idx) {
            const ReadyJob& j = ready[chosen[idx]];
            if (j.remainingTicks > 1) continue;
            if (j.vehicle < 0 || j.vehicle >= static_cast<int>(lastFDone_.size()))
                continue;
            if (j.kind == TaskKind::Feedforward) lastFDone_[j.vehicle] = nowEst;
            if (j.kind == TaskKind::Estimator)   lastEDone_[j.vehicle] = nowEst;
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
    std::vector<int> eByV_, bByV_, mByV_;
    std::vector<long> lastFDone_;
    std::vector<long> lastEDone_;
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
