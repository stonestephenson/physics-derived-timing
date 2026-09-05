#!/usr/bin/env python3
"""Tests for tools/corollary_table.py: budgets derived from the committed
min-over-phase tables, then the corollary capacities (PAPER_NOTES 2026-09-04 (c))."""
import csv
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import corollary_table as ct  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent


def rows(text):
    return list(csv.DictReader(io.StringIO(text)))


class BudgetDerivationTests(unittest.TestCase):
    HEADER = "zone,extra_ms,phase,age_path_ms,total_hard\n"

    def test_min_over_phase_a(self):
        # 2 phases; +50 clean at both, +60 breaches at one phase -> A = 140.5
        txt = self.HEADER + "\n".join([
            "3,50,0.0,140.5,0", "3,50,19.9,140.5,0",
            "3,60,0.0,150.5,0", "3,60,19.9,150.5,5",
            "3,70,0.0,160.5,3", "3,70,19.9,160.5,9"]) + "\n"
        self.assertEqual(ct.a_zone_from_rows(rows(txt), zone=3), 140.5)

    def test_cell_age_is_min_over_phases(self):
        # z1 cells deliver 240.5 at most phases and 250.5 at a few: certify 240.5
        txt = self.HEADER + "\n".join([
            "1,150,0.0,250.5,0", "1,150,19.9,240.5,0",
            "1,200,0.0,310.5,0", "1,200,19.9,300.5,4"]) + "\n"
        self.assertEqual(ct.a_zone_from_rows(rows(txt), zone=1), 240.5)

    def test_union_of_coarse_and_fine_grids(self):
        # coarse: +150 clean, +200 breach; fine adds +160 clean, +170 breach
        coarse = ["2,150,0.0,240.5,0", "2,150,19.9,240.5,0",
                  "2,200,0.0,290.5,9", "2,200,19.9,290.5,9"]
        fine = ["2,160,0.0,250.5,0", "2,160,19.9,250.5,0",
                "2,170,0.0,260.5,0", "2,170,19.9,260.5,2"]
        txt = self.HEADER + "\n".join(coarse + fine) + "\n"
        self.assertEqual(ct.a_zone_from_rows(rows(txt), zone=2), 250.5)

    def test_never_breaches_is_none(self):
        txt = self.HEADER + "3,50,0.0,140.5,0\n3,50,19.9,140.5,0\n"
        self.assertIsNone(ct.a_zone_from_rows(rows(txt), zone=3))

    def test_breach_at_first_cell_is_zero_capacity_marker(self):
        txt = self.HEADER + "3,50,0.0,140.5,1\n3,50,19.9,140.5,0\n"
        self.assertEqual(ct.a_zone_from_rows(rows(txt), zone=3), 0.0)

    def test_budgets_of_record(self):
        # integration pin against the committed phase tables
        b = ct.budgets(ROOT)
        self.assertEqual(b["10"], (150.5, 290.5))
        # z2 on v12.5: coarse bracket 190.5, refined to 230.5 on the 10 ms grid
        # (zone_tolerance_z2_fine_phase_v12.5.csv, 2026-09-04 (c))
        self.assertEqual(b["12.5"], (140.5, 230.5))
        self.assertEqual(b["15"], (110.5, 140.5))


class TableTests(unittest.TestCase):
    def test_table_rows(self):
        out = ct.table({"10": (150.5, 290.5), "12.5": (140.5, 230.5)}, occ_plus=4)
        by = {(r["profile"], r["workload"]): r for r in out}
        self.assertEqual(by[("10", "limited-t")]["classical_cap"], 3)
        self.assertEqual(by[("10", "limited")]["classical_cap"], 4)
        self.assertEqual(by[("10", "limited-t")]["fdemoted_cap"], 7)
        self.assertEqual(by[("10", "limited-t")]["decomposition_cap"], 8)
        self.assertEqual(by[("12.5", "limited-t")]["decomposition_cap"], 8)
        self.assertEqual(by[("12.5", "limited-t")]["decomposition_binder"], "P1")
        self.assertEqual(by[("12.5", "limited-t")]["ratio_vs_classical"], 4.0)
        self.assertEqual(by[("12.5", "limited")]["fdemoted_cap"], 6)
        self.assertAlmostEqual(by[("10", "limited-t")]["ratio_vs_classical"], 8 / 3)
        self.assertEqual(by[("10", "limited")]["ratio_vs_classical"], 2.0)

    def test_floor_profile_rows(self):
        out = ct.table({"15": (110.5, 140.5)}, occ_plus=4)
        by = {r["workload"]: r for r in out}
        self.assertEqual(by["limited-t"]["classical_cap"], 0)
        self.assertEqual(by["limited-t"]["decomposition_cap"], 0)
        self.assertEqual(by["limited-t"]["decomposition_binder"], "top")
        self.assertIsNone(by["limited-t"]["base_bound_at_cap_ms"])
        self.assertIsNone(by["limited-t"]["ratio_vs_classical"])
        self.assertEqual(by["full"]["classical_cap"], 0)
        self.assertIsNone(by["full"]["decomposition_cap"])


if __name__ == "__main__":
    unittest.main()
