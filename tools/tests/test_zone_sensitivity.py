#!/usr/bin/env python3
"""Tests for tools/zone_sensitivity.py (zone-partition sensitivity on the
binding numbers, PAPER_NOTES 2026-09-04 (d)). The simulator is mocked."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import zone_sensitivity as zsen  # noqa: E402


class VariantTests(unittest.TestCase):
    def test_defaults_string(self):
        self.assertEqual(zsen.consts_for(1, 1, 1), "0.0215,0.0035,0.004,50,100,350")

    def test_scaled_families(self):
        self.assertEqual(zsen.consts_for(0.8, 1, 1), "0.0172,0.0035,0.004,50,100,350")
        self.assertEqual(zsen.consts_for(1, 1.2, 1), "0.0215,0.0042,0.0048,50,100,350")
        self.assertEqual(zsen.consts_for(1, 1, 1.5), "0.0215,0.0035,0.004,75,150,525")

    def test_variant_table(self):
        names = [v[0] for v in zsen.VARIANTS]
        self.assertEqual(names[0], "baseline")
        self.assertEqual(len(names), 7)
        self.assertEqual(len(set(names)), 7)


class SummaryTests(unittest.TestCase):
    """Mocked runner: z3 cliff at +50 (age 140.5) for every variant except
    'sharp_x0.8', whose z2 cliff drops from +140 to +90 (230.5 -> 180.5)."""

    def runner(self, zone, extra, phase, zone_consts):
        sharp_low = zone_consts.startswith("0.0172")
        limit = 50 if zone == 3 else (90 if sharp_low else 140)
        hard = [0, 0, 0, 0] if extra <= limit else ([0, 0, 0, 3] if zone == 3 else [0, 0, 2, 0])
        return {"age_path": 90.5 + extra, "hard": hard, "soft_pct": 3.0,
                "fleet_ey": 0.5, "zone_ey": [0.4, 0.1, 0.5, 0.5], "f_stale_max": 22.3,
                "zone_frames": [4185, 1370, 3086 + (400 if sharp_low else 0), 859]}

    def test_summary_rows(self):
        rows, summary = zsen.campaign("12.5", 95, [20, 50, 60], [80, 90, 140, 150],
                                      self.runner, jobs=1,
                                      variants=[("baseline", 1, 1, 1), ("sharp_x0.8", 0.8, 1, 1)])
        by = {s["variant"]: s for s in summary}
        self.assertEqual(by["baseline"]["a_z3_ms"], 140.5)
        self.assertEqual(by["baseline"]["a_z2_ms"], 230.5)
        self.assertEqual(by["baseline"]["base_budget_ms"], 230.5)     # min(290.5, 240.5, A_z2)
        self.assertEqual(by["sharp_x0.8"]["a_z2_ms"], 180.5)
        self.assertEqual(by["sharp_x0.8"]["base_budget_ms"], 180.5)
        self.assertEqual(by["sharp_x0.8"]["z2_frames"], 3486)
        # composed certificate from the solver: 8 at the baseline budgets,
        # 7 when the base budget is 180.5 (base band 187.6 at N=7 -> 6? no: 186.2/187.6 <= 180.5 fails -> 6)
        self.assertEqual(by["baseline"]["composed_cap_limited_t"], 8)
        self.assertLess(by["sharp_x0.8"]["composed_cap_limited_t"], 8)
        # per-run rows carry the variant and its constants
        self.assertTrue(all("variant" in r and "zone_consts" in r for r in rows))
        self.assertEqual(len(rows), 2 * (3 + 4) * 21)


if __name__ == "__main__":
    unittest.main()
