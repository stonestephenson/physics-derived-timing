// CPS Challenge Visualizer — entry point.
//
// Builds a multi-vehicle co-simulation driven by a chosen scheduling policy and
// either visualizes it live (raylib) or runs it headless and prints metrics.
//
// ============================ Adding a scheduler =============================
// The plug-and-play part: to try a new scheduling method, drop a CorePolicy
// subclass into src/sched/policies/MyPolicy.cpp (CMake auto-globs it), declare
// its factory in sched/policies/Policies.h, and add one line to makePolicy()
// below. Swap which policy main builds and re-run — nothing else changes.
// For full control over the 16 FMU triggers, subclass Scheduler directly and
// pass it to the Simulation instead of a PolicyScheduler.
// ============================================================================
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <sstream>
#include <string>

#include "fmu/FmuVariables.h"
#include "sched/PolicyScheduler.h"
#include "sched/policies/Policies.h"
#include "sim/Recording.h"
#include "sim/Simulation.h"
#include "trace/Trajectory.h"
#include "viz/Visualizer.h"

using namespace cps;

namespace {

std::unique_ptr<CorePolicy> makePolicy(const std::string& name, bool triage,
                                       double guardMs, double floorMs,
                                       double guardCapMs) {
    if (name == "edf")     return makeEdfPolicy();
    if (name == "context" || name == "ctx")
                           return makeContextAwarePolicy();  // oracle (reads *_real)
    if (name == "honest" || name == "context-honest")
                           return makeContextAwareHonestPolicy();
    if (name == "prm" || name == "partitioned")
                           return makePartitionedRMPolicy();
    if (name == "ttu" || name == "predictive")
                           return makeTimeToUnsafePolicy(triage);
    if (name == "ttu-honest" || name == "httu")
                           return makeTimeToUnsafePolicy(triage, InfoSet::Remote);
    if (name == "hybrid" || name == "guarded")
                           return makeHybridPolicy(guardMs, triage);
    if (name == "hybrid-honest" || name == "hhybrid")
                           return makeHybridPolicy(guardMs, triage, InfoSet::Remote);
    if (name == "aguard" || name == "adaptive-guard")
                           return makeAdaptiveGuardPolicy(floorMs, triage,
                                                          InfoSet::Oracle, guardCapMs);
    if (name == "aguard-honest" || name == "haguard")
                           return makeAdaptiveGuardPolicy(floorMs, triage,
                                                          InfoSet::Remote, guardCapMs);
    if (name == "zband" || name == "zone-band")
                           return makeZoneBandPolicy();  // PROOF_DRAFT ZB-F-X
    if (name == "eskip")   return makeEskipProbePolicy();  // FRONTIER instrument
    if (name == "frontier")
                           return makeFrontierPolicy(floorMs, InfoSet::Oracle, guardCapMs);
    if (name == "frontier-honest")
                           return makeFrontierPolicy(floorMs, InfoSet::Remote, guardCapMs);
    return makeRateMonotonicPolicy();  // "rm" / default
}

Profile parseProfile(const std::string& s) {
    if (s == "12.5" || s == "12_5") return Profile::V12_5;
    if (s == "15")                  return Profile::V15;
    return Profile::V10;
}

ExecMode parseExec(const std::string& s) {
    if (s == "worst") return ExecMode::Worst;
    if (s == "best")  return ExecMode::Best;
    if (s == "pert")  return ExecMode::Pert;
    return ExecMode::Average;
}

OverrunPolicy parseOverrun(const std::string& s) {
    if (s == "skip" || s == "skipnext") return OverrunPolicy::SkipNext;
    return OverrunPolicy::KillAndHold;  // "kill" / default
}

PlantKind parsePlant(const std::string& s) {
    if (s == "cartpole" || s == "cp") return PlantKind::CartPole;
    return PlantKind::Lateral;  // "lateral" / default
}

// Append the run's per-vehicle summary to a CSV (header written if the file is
// new/empty), so parameter sweeps can be aggregated across invocations.
// net_delay_ms is the --net-delay override; -1 = challenge default delays.
void appendCsv(const std::string& path, const RunRecording& rec,
               const std::string& scheduler, const std::string& exec,
               const std::string& overrun, double netDelayMs, uint64_t seed) {
    std::FILE* f = std::fopen(path.c_str(), "a");
    if (!f) {
        std::fprintf(stderr, "Warning: cannot open CSV file %s\n", path.c_str());
        return;
    }
    if (std::ftell(f) == 0)
        std::fprintf(f, "scheduler,profile,vehicles,cores,exec,overrun,net_delay_ms,seed,"
                        "duration_s,missed_jobs,veh,avg_perf,max_roll,soft_pct,hard,"
                        "max_age_fresh_ms,max_age_path_ms,min_ttpnr_ms,past_pnr_ms,"
                        "tau_crit_ms,max_sim_crit,sim_crit_over_cores_pct,"
                        "danger_tau,max_k_age,max_k_danger,"
                        "pack_zone,min_spacing_ms,max_occ_packed\n");
    // Per-run simultaneous-criticality scalars, repeated on each vehicle row
    // (like missed_jobs / duration_s). fracOver = % of ticks with > nCores critical.
    long simOver = 0;
    for (int c = rec.nCores + 1; c < static_cast<int>(rec.simCritHist.size()); ++c)
        simOver += rec.simCritHist[c];
    const double fracOver = rec.simCritTicks > 0
        ? 100.0 * static_cast<double>(simOver) / static_cast<double>(rec.simCritTicks) : 0.0;
    for (int v = 0; v < rec.nVehicles; ++v) {
        const VehicleSummary& s = rec.summary[v];
        std::fprintf(f, "%s,%s,%d,%d,%s,%s,%.2f,%llu,%.3f,%ld,%d,%.6f,%.6f,%.4f,%d,%.2f,%.2f,%.2f,%.1f,%.0f,%ld,%.2f,%.2f,%ld,%ld,%d,%.2f,%ld\n",
                     scheduler.c_str(), profileName(static_cast<Profile>(rec.profile)),
                     rec.nVehicles, rec.nCores, exec.c_str(), overrun.c_str(),
                     netDelayMs, static_cast<unsigned long long>(seed), rec.duration(),
                     rec.missedJobs, v, s.average_real, s.max_rolling_real,
                     s.soft_violation_pct, s.hard_violations,
                     s.max_data_age_ms, s.max_data_age_oldest_ms,
                     s.min_ttpnr_ms, s.past_pnr_ticks * rec.baseStep * 1000.0,
                     rec.tauCritMs, rec.maxSimCrit, fracOver,
                     rec.dangerTau, rec.maxKAge, rec.maxKDanger,
                     rec.packZone, rec.minSpacingMs, rec.maxOccPacked);
    }
    std::fclose(f);
}

const char* argValue(int argc, char** argv, const char* key, const char* def) {
    for (int i = 1; i < argc - 1; ++i)
        if (std::strcmp(argv[i], key) == 0) return argv[i + 1];
    return def;
}
bool hasFlag(int argc, char** argv, const char* key) {
    for (int i = 1; i < argc; ++i)
        if (std::strcmp(argv[i], key) == 0) return true;
    return false;
}

void usage() {
    std::printf(
        "CPS Challenge Visualizer\n"
        "  --scheduler rm|prm|edf|context|honest|ttu|hybrid|aguard|zband   scheduling\n"
        "                               policy (default rm; context = oracle, honest =\n"
        "                               remote metrics only, ttu = predictive\n"
        "                               time-to-unsafe, hybrid = fixed TTPNR guard +\n"
        "                               comfort tier, aguard = self-tuning guard;\n"
        "                               *-honest = predict from delayed state not truth)\n"
        "  --vehicles N                 number of vehicles (default 1)\n"
        "  --cores N                    shared cloud cores (default 3)\n"
        "  --profile 10|12.5|15         speed profile (default 10)\n"
        "  --plant lateral|cartpole     controlled system (default lateral)\n"
        "  --duration SEC               sim seconds (default 0 = one lap)\n"
        "  --exec avg|worst|best|pert   execution-time model (default avg)\n"
        "  --overrun kill|skip          job overrun policy (default kill = kill-and-hold;\n"
        "                               skip = overrunning job finishes, releases skipped)\n"
        "  --net-delay MS               fix BOTH network delays to MS (overrides --exec\n"
        "                               for the networks; for delay-tolerance sweeps)\n"
        "  --delta-max RAD              assumed steering limit for recoverability\n"
        "                               predictions (default: calibrated per profile)\n"
        "  --u-max N                    cart-pole actuator force limit (N) = the delta-max\n"
        "                               analogue (default: calibrated CartPoleParams)\n"
        "  --shove-force N              cart-pole disturbance shove magnitude (N)\n"
        "  --theta-max RAD              cart-pole hard (crash) angle bound (rad)\n"
        "  --triage                     ttu/hybrid: drop past-PNR cars to lowest priority\n"
        "                               instead of boosting them\n"
        "  --guard MS                   hybrid only: TTPNR threshold below which a car\n"
        "                               enters the emergency tier (default 150)\n"
        "  --floor MS                   aguard only: target safety floor; the guard\n"
        "                               self-tunes to floor + live round-trip (default 100)\n"
        "  --tau-crit MS                simultaneous-criticality threshold: a car is\n"
        "                               'critical' when TTPNR < MS (~1 round-trip; default\n"
        "                               100). Reports max # critical at once vs cores.\n"
        "  --danger-tau FRAC            lateral only: danger-relative criticality. A car is\n"
        "                               'in danger' when delivered age_path >= FRAC * A(zone\n"
        "                               of car now) (default 1.0 = at the zone budget). Also\n"
        "                               folds in TTPNR<tau-crit. Reports K_age/K + a K(tau)\n"
        "                               curve. THE PLAN leg 4 / THEOREM_BRIEF §3.6.\n"
        "  --pack-zone Z                lateral only: place cars to maximize simultaneous\n"
        "                               occupancy of zone Z (0-3; 3 = binding lane-change)\n"
        "                               at the --min-spacing gap. -1 = off (default spread).\n"
        "                               Reports max Occ vs geometric predict. THE PLAN leg 2.\n"
        "  --min-spacing MS             pack-zone only: F_spaced minimum inter-car phase gap\n"
        "                               (ms; default 0 = pack tight -> Occ -> N).\n"
        "  --align-offsets FRAC         lateral only: align vehicle start phases for the\n"
        "                               simultaneity experiment. 0 = even spread (default);\n"
        "                               1 = all on the same lap phase (adversarial). See\n"
        "                               HANDOFF leg (A).\n"
        "  --zone-target Z              Phase-2 causal A(zone): inject extra command delay\n"
        "                               only while in curvature zone Z (0=straight 1=slight\n"
        "                               2=sharp 3=lane-change); -1 = off (default)\n"
        "  --zone-extra-ms D            extra netCA delay (ms) injected in --zone-target's zone\n"
        "  --zone-extra-vector A,B,C,D  envelope experiment (PROOF_DRAFT A1): per-zone extra\n"
        "                               netCA delay (ms) {z0,z1,z2,z3}, applied by each car's\n"
        "                               current zone every tick; overrides --zone-target\n"
        "  --zone-flag-window MS        with --zone-extra-vector: use the z3 entry whenever\n"
        "                               the car is within +/-MS of a z3 arc (ZB-F-X flag\n"
        "                               emulation); 0 = off (default)\n"
        "  --ff-extra-ms D              A2 experiment: delay every Feedforward publish by D ms\n"
        "                               (clamped before F's next release; age_path untouched\n"
        "                               by construction); 0 = off (default)\n"
        "  --pred-staleness MS          honest predictor (ttu/hybrid/aguard-honest): age\n"
        "                               of the cloud's delayed state estimate (default 16\n"
        "                               = worst sensor delay)\n"
        "  --pred-margin MS             honest predictor: safety margin subtracted from\n"
        "                               estimated TTPNR (default 0)\n"
        "  --validate-predictor         predictor fidelity gate (see PREDICTOR.md)\n"
        "  --seed N                     RNG seed for pert mode (default 0)\n"
        "  --headless                   run without the GUI, print metrics\n"
        "  --csv FILE                   append per-vehicle summary rows to FILE\n"
        "  --save FILE                  write the run recording to FILE\n"
        "  --replay FILE                visualize a saved recording (no sim)\n"
        "  --help                       this message\n");
}

}  // namespace

int main(int argc, char** argv) {
    if (hasFlag(argc, argv, "--help") || hasFlag(argc, argv, "-h")) {
        usage();
        return 0;
    }

    const std::string replayFile = argValue(argc, argv, "--replay", "");
    const std::string saveFile   = argValue(argc, argv, "--save", "");

    try {
        // --- Replay a saved recording ---
        if (!replayFile.empty()) {
            RunRecording rec = RunRecording::load(replayFile);
            auto traj = Trajectory::load(static_cast<Profile>(rec.profile));
            std::printf("Replaying %s (%s, %d vehicles, %.1f s)\n", replayFile.c_str(),
                        rec.schedulerName.c_str(), rec.nVehicles, rec.duration());
            VizConfig vcfg;
            vcfg.screenshotPath = argValue(argc, argv, "--screenshot", "");
            vcfg.screenshotAtFrame = std::atoi(argValue(argc, argv, "--screenshot-at", "180"));
            vcfg.initialSelected = std::atoi(argValue(argc, argv, "--select", "0"));
            vcfg.initialSpeed = std::atof(argValue(argc, argv, "--speed", "4"));
            Visualizer viz(traj, vcfg);
            viz.replay(rec);
            return 0;
        }

        // --- Build a fresh simulation ---
        SimParams params;
        params.profile       = parseProfile(argValue(argc, argv, "--profile", "10"));
        params.plant         = parsePlant(argValue(argc, argv, "--plant", "lateral"));
        params.nVehicles     = std::max(1, std::atoi(argValue(argc, argv, "--vehicles", "1")));
        params.nCores        = std::max(1, std::atoi(argValue(argc, argv, "--cores", "3")));
        const std::string execName    = argValue(argc, argv, "--exec", "avg");
        const std::string overrunName = argValue(argc, argv, "--overrun", "kill");
        params.execMode      = parseExec(execName);
        params.overrun       = parseOverrun(overrunName);
        params.netDelayMs    = std::atof(argValue(argc, argv, "--net-delay", "-1"));
        params.validatePredictor = hasFlag(argc, argv, "--validate-predictor");
        params.deltaMax      = std::atof(argValue(argc, argv, "--delta-max", "-1"));
        params.cpUMax        = std::atof(argValue(argc, argv, "--u-max", "-1"));
        params.cpShoveForce  = std::atof(argValue(argc, argv, "--shove-force", "-1"));
        params.cpThetaHard   = std::atof(argValue(argc, argv, "--theta-max", "-1"));
        params.tauCritMs     = std::atof(argValue(argc, argv, "--tau-crit", "100"));
        params.dangerTau     = std::atof(argValue(argc, argv, "--danger-tau", "1.0"));
        params.packZone      = std::atoi(argValue(argc, argv, "--pack-zone", "-1"));
        params.minSpacingMs  = std::atof(argValue(argc, argv, "--min-spacing", "0"));
        params.alignOffsets  = std::atof(argValue(argc, argv, "--align-offsets", "0"));
        params.zoneTarget    = std::atoi(argValue(argc, argv, "--zone-target", "-1"));
        params.zoneExtraMs   = std::atof(argValue(argc, argv, "--zone-extra-ms", "0"));
        {   // --zone-extra-vector A,B,C,D (ms per zone; exactly 4 or rejected)
            const std::string vec = argValue(argc, argv, "--zone-extra-vector", "");
            if (!vec.empty()) {
                std::stringstream ss(vec);
                std::string tok;
                while (std::getline(ss, tok, ','))
                    params.zoneExtraVecMs.push_back(std::atof(tok.c_str()));
                if (params.zoneExtraVecMs.size() != 4) {
                    std::fprintf(stderr,
                                 "--zone-extra-vector needs exactly 4 comma-separated "
                                 "values (z0,z1,z2,z3), got %zu\n",
                                 params.zoneExtraVecMs.size());
                    return 1;
                }
            }
        }
        params.zoneFlagWindowMs = std::atof(argValue(argc, argv, "--zone-flag-window", "0"));
        params.ffExtraMs     = std::atof(argValue(argc, argv, "--ff-extra-ms", "0"));
        params.predStalenessMs = std::atof(argValue(argc, argv, "--pred-staleness", "16"));
        params.predMarginMs  = std::atof(argValue(argc, argv, "--pred-margin", "0"));
        params.triage        = hasFlag(argc, argv, "--triage");
        const double guardMs = std::atof(argValue(argc, argv, "--guard", "150"));
        const double floorMs = std::atof(argValue(argc, argv, "--floor", "100"));
        // FCHANNEL council A-R1: the guard's theta clamp, previously a
        // hard-coded 450 (saturated for the incumbent at high N, live for the
        // challenger). Default 450 = byte-identical.
        const double guardCapMs =
            std::atof(argValue(argc, argv, "--guard-cap", "450"));
        params.fzoneTarget = std::atoi(argValue(argc, argv, "--fzone-target", "-1"));
        params.fzoneHoldMs = std::atof(argValue(argc, argv, "--fzone-hold-ms", "0"));
        params.bzoneTarget = std::atoi(argValue(argc, argv, "--bzone-target", "-1"));
        params.bzoneHoldMs = std::atof(argValue(argc, argv, "--bzone-hold-ms", "0"));
        params.qzoneTarget = std::atoi(argValue(argc, argv, "--qzone-target", "-1"));
        params.qzoneEps    = std::atof(argValue(argc, argv, "--qzone-eps", "0"));
        params.offsetSeed  = static_cast<uint64_t>(
            std::atoll(argValue(argc, argv, "--offset-seed", "0")));
        params.seed          = static_cast<uint64_t>(std::atoll(argValue(argc, argv, "--seed", "0")));
        const double durSec  = std::atof(argValue(argc, argv, "--duration", "0"));
        if (durSec > 0) params.durationSteps =
            static_cast<long>(durSec / vr::kBaseStepSeconds);

        const std::string schedName = argValue(argc, argv, "--scheduler", "rm");
        params.honestPredictor =
            schedName == "ttu-honest"    || schedName == "httu"    ||
            schedName == "hybrid-honest" || schedName == "hhybrid" ||
            schedName == "aguard-honest" || schedName == "haguard" ||
            schedName == "frontier-honest";
        const std::string csvFile   = argValue(argc, argv, "--csv", "");
        auto scheduler = std::make_unique<PolicyScheduler>(
            makePolicy(schedName, params.triage, guardMs, floorMs, guardCapMs));

        Simulation sim(params, std::move(scheduler));

        if (hasFlag(argc, argv, "--headless")) {
            std::printf("Running headless: %s, %d vehicle(s), %d cores, profile %s, "
                        "exec %s, overrun %s\n",
                        schedName.c_str(), params.nVehicles, params.nCores,
                        profileName(params.profile), execName.c_str(), overrunName.c_str());
            sim.runToCompletion(true);
            if (!csvFile.empty())
                appendCsv(csvFile, sim.recording(), schedName, execName, overrunName,
                          params.netDelayMs, params.seed);
            if (!saveFile.empty()) {
                sim.recording().save(saveFile);
                std::printf("Saved recording to %s\n", saveFile.c_str());
            }
            return 0;
        }

        // --- Live visualization ---
        sim.start();
        std::printf("Live: %s, %d vehicle(s), %d cores, profile %s. Close window to exit.\n",
                    schedName.c_str(), params.nVehicles, params.nCores,
                    profileName(params.profile));
        VizConfig vcfg;
        vcfg.screenshotPath = argValue(argc, argv, "--screenshot", "");
        vcfg.screenshotAtFrame = std::atoi(argValue(argc, argv, "--screenshot-at", "180"));
        vcfg.initialSelected = std::atoi(argValue(argc, argv, "--select", "0"));
        vcfg.initialSpeed = std::atof(argValue(argc, argv, "--speed", "4"));
        Visualizer viz(sim.trajectory(), vcfg);
        viz.live(sim);
        if (!saveFile.empty()) {
            sim.recording().save(saveFile);
            std::printf("Saved recording to %s\n", saveFile.c_str());
        }
        return 0;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "Error: %s\n", e.what());
        return 1;
    }
}
