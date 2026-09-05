#!/usr/bin/env python3
"""Pins for the corollary helpers in tools/rta_solve.py (PAPER_NOTES
2026-09-04 (c)): certified capacities under a given A(z3) / base-band budget.
The numbers are the solver's own outputs at the budgets of record, frozen so
a change in the solver or the budgets is visible.

Run:  python3 -m unittest discover -s tools/tests -p 'test_*.py'
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import rta_solve as r  # noqa: E402

W = r.EXEC_IDX["worst"]


class ClassicalCapacityTests(unittest.TestCase):
    """Largest N whose uniform fleet-max bound <= A(z3) with P1 intact."""

    def test_original_140(self):
        # PROOF_DRAFT headline: classical admits 3 (Θ=R) / 2 (Θ=T) at 140
        self.assertEqual(r.uniform_capacity(140.0, 3, W, "limited"), 3)
        self.assertEqual(r.uniform_capacity(140.0, 3, W, "limited-t"), 2)

    def test_refined_170(self):
        # PROOF_DRAFT §8.5: 6 (Θ=R) / 5 (Θ=T) at 170
        self.assertEqual(r.uniform_capacity(170.0, 3, W, "limited"), 6)
        self.assertEqual(r.uniform_capacity(170.0, 3, W, "limited-t"), 5)

    def test_min_over_phase_budgets(self):
        self.assertEqual(r.uniform_capacity(150.5, 3, W, "limited"), 4)      # v10
        self.assertEqual(r.uniform_capacity(150.5, 3, W, "limited-t"), 3)
        self.assertEqual(r.uniform_capacity(140.5, 3, W, "limited"), 3)      # v12.5
        self.assertEqual(r.uniform_capacity(140.5, 3, W, "limited-t"), 2)
        self.assertEqual(r.uniform_capacity(110.5, 3, W, "limited-t"), 0)    # v15: floor

    def test_p1_caps_it(self):
        # a huge budget is still capped by P1 (limited: first overrun at N=9)
        self.assertEqual(r.uniform_capacity(10_000.0, 3, W, "limited"), 8)


class FDemotedCapacityTests(unittest.TestCase):
    """Uniform F-demotion (every car's E/B/M above every F; no occupancy)."""

    def test_v10_boundary(self):
        # 151.6 (Θ=T) misses 150.5 by 1.1 ms -> 7; 147.0 (Θ=R) clears it -> 8
        self.assertEqual(r.uniform_capacity(150.5, 3, W, "limited-t", demote_f=True), 7)
        self.assertEqual(r.uniform_capacity(150.5, 3, W, "limited", demote_f=True), 8)

    def test_v12_5(self):
        self.assertEqual(r.uniform_capacity(140.5, 3, W, "limited-t", demote_f=True), 4)
        self.assertEqual(r.uniform_capacity(140.5, 3, W, "limited", demote_f=True), 6)


class DecompositionCapacityTests(unittest.TestCase):
    """Two-band ZB-F composition: top band = Occ+ cars (<= A(z3)), base band
    (<= the smallest non-z3 budget), P1 for the whole system."""

    def test_v10(self):
        # top 137.4 (Θ=T) / 133.0 (Θ=R) vs 150.5; base 196.0 vs 290.5; P1 to 8
        cap, why = r.decomposition_capacity(150.5, 290.5, 4, 3, W, "limited-t")
        self.assertEqual((cap, why), (8, "P1"))
        cap, why = r.decomposition_capacity(150.5, 290.5, 4, 3, W, "limited")
        self.assertEqual((cap, why), (8, "P1"))

    def test_v12_5(self):
        # base budget 230.5 (z2 refined on the 10 ms grid): base band at N=8
        # is 194.4 / 196.0 -> 8, P1-capped, on both candidates
        cap, why = r.decomposition_capacity(140.5, 230.5, 4, 3, W, "limited-t")
        self.assertEqual((cap, why), (8, "P1"))
        cap, why = r.decomposition_capacity(140.5, 230.5, 4, 3, W, "limited")
        self.assertEqual((cap, why), (8, "P1"))

    def test_base_band_can_bind(self):
        # the coarse-bracket value 190.5 would have bound the base band at 7
        # (the 2026-09-04 (c) false alarm, kept as a semantics pin)
        cap, why = r.decomposition_capacity(140.5, 190.5, 4, 3, W, "limited-t")
        self.assertEqual((cap, why), (7, "base"))

    def test_top_band_binds(self):
        # Occ+ = 5 top band is 141.0 (Θ=T) > 140.5: the Occ+ band never fits,
        # but a 4-car fleet is all top band (137.4 <= 140.5) -> 4, binder 'top'
        cap, why = r.decomposition_capacity(140.5, 290.5, 5, 3, W, "limited-t")
        self.assertEqual((cap, why), (4, "top"))
        # v15: even one car overshoots (F-demoted N=1 bound 123.4 > 110.5) -> 0
        cap, why = r.decomposition_capacity(110.5, 140.5, 4, 3, W, "limited-t")
        self.assertEqual((cap, why), (0, "top"))

    def test_cli_budget_overrides(self):
        # the PAPER_NOTES repro: band verdicts follow --a-z3 / --a-base
        import subprocess, sys
        from pathlib import Path
        solver = str(Path(__file__).resolve().parent.parent / "rta_solve.py")
        base = [sys.executable, solver, "--workload", "limited-t", "--band", "4",
                "--band-demote-f", "--a-z3", "140.5", "--a-base", "190.5"]
        out8 = subprocess.run(base + ["--band-n", "8"], capture_output=True, text=True).stdout
        out7 = subprocess.run(base + ["--band-n", "7"], capture_output=True, text=True).stdout
        self.assertIn("NOT ADMITTED (N=8", out8)
        self.assertIn("base-band fleet-max  196.0 ms vs A(z0/z2)=190 -> FAIL", out8)
        self.assertIn("ADMITTED (N=7", out7)
        self.assertNotIn("NOT ADMITTED", out7)

    def test_original_headline(self):
        # PROOF_DRAFT §3.5: Occ+ = 4, N = 8 admitted at 140 / 290 (margin 2.6 ms)
        cap, why = r.decomposition_capacity(140.0, 290.0, 4, 3, W, "limited-t")
        self.assertEqual((cap, why), (8, "P1"))


class BudgetOverrideTests(unittest.TestCase):
    def test_defaults_unchanged(self):
        # G3 must stay byte-identical: the module constants keep 140 / 290
        self.assertEqual(r.A_ZONE_MS["z3 lane-change (binding)"], 140.0)
        self.assertEqual(r.A_ZONE_MS["z0/z2 straight/sharp"], 290.0)


if __name__ == "__main__":
    unittest.main()
