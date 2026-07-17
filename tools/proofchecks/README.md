# proofchecks — the machine checks behind PROOF_DRAFT.md's [PROVEN — machine-checked] tags

These scripts are the executable evidence for the candidate fleet-safety
theorem (`PROOF_DRAFT.md`). They were written in the 2026-07-02/03 sessions
(originally session-scratchpad; committed 2026-07-05 so Kurt — or anyone — can
**re-run** the checks rather than trust quoted outputs). All randomness is
seeded (seed 0 / per-schedule seeds), so the quoted case counts reproduce
exactly. None of them modify anything; `lemma2a_check` and `redteam_band`
import `tools/rta_solve.py` read-only.

Run from anywhere (paths are repo-relative):

| script | backs | expected verdict (2026-07-05) | runtime |
|---|---|---|---|
| `lemma1_check.py` | PROOF_DRAFT §1 (occupancy Lemma 1) + §4 spacing buffer | `ALL LEMMA-1 CHECKS PASS`: 17,176-case brute force (exhaustive 1-arc incl. wrapped + seeded multi-arc), all 3 profiles' geometry, all 9 committed `occupancy_sweep.csv` rows replicated exactly, inflated-arc Occ⁺ coupling table, spacing-buffer sensitivity (check [5]: Occ⁺ non-increasing in `s`; `s₀ = 4 s` compression-tolerance table) | ~2 min |
| `lemma2a_check.py` | PROOF_DRAFT §2 S3/S5 + the limited-CI RTA | `ALL LEMMA-2a CHECKS PASS`: workload lemma brute-forced (all Θ∈[C,T], y≤650, exact phase enumeration, min slack 0), exact Python replication of the C++ scheduler (N=11/30 s missed=4,497), no iteration dip N=1..24 | ~5 min |
| `redteam_band.py` | PROOF_DRAFT §3.6 (adversarial band battery) | `REFUTATIONS ... : 0` over 91 seeded schedules; replica self-validates (exits if N=11 ≠ 4,497); max obs/bound ≈ 0.89 | ~4 min |
| `zone_probe.cpp` | PROOF_DRAFT §0 route-geometry table (K, L, lap per profile) | v10: K=4, L=105,400, lap=1,178,000; v12.5: 4/85,900/944,000; v15: 3/76,000/786,000 (build cmd in its header) | seconds |

`redteam_band_results_2026-07-03.txt` is the archived battery output the draft
quotes (pre-dating the pass-2 packer fix and the own-carry solver repair; its
claim tables use the pre-repair base R's — observed maxima are below both the
pre- and post-repair bounds, see PROOF_DRAFT §3.6).

Maintenance rule: these encode the task-set constants (T, C pairs, m = 3) and
the analyzed domains (y ≤ 650, N ≤ 24). If the task set, core count, or any
band-mode constant changes, PROOF_DRAFT §2's domain-audit note applies —
re-run everything and re-check the domains still cover the solver's needs.
