# -*- coding: utf-8 -*-
"""Unit tests for Phase 3 Evaluation Suite & Persona Assertions."""

import os
import sys
import json
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
app_dir = os.path.join(BASE_DIR, "app")
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from evals.personas import PERSONAS
from evals.runner import EvalRunner, run_all_evaluations, RESULTS_FILE


class TestEvalSuitePhase3(unittest.TestCase):

    def test_personas_completeness(self):
        # Must have exactly 10 comprehensive personas covering all edge cases
        self.assertEqual(len(PERSONAS), 10)
        ids = [p["id"] for p in PERSONAS]
        self.assertEqual(len(set(ids)), 10)

        # Check required keys
        for p in PERSONAS:
            self.assertIn("id", p)
            self.assertIn("name", p)
            self.assertIn("category", p)
            self.assertIn("dialogue", p)
            self.assertIn("expected_database_state", p)

    def test_eval_runner_execution(self):
        runner = EvalRunner()
        report = runner.run_all()

        self.assertIsNotNone(report)
        self.assertEqual(report["total_personas"], 10)
        self.assertEqual(report["passed_personas"], 10)
        self.assertEqual(report["failed_personas"], 0)
        self.assertEqual(report["pass_rate_percentage"], 100.0)
        self.assertEqual(report["overall_status"], "ALL PASS")

        # Verify results file created
        self.assertTrue(os.path.exists(RESULTS_FILE))
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            saved_report = json.load(f)
        self.assertEqual(saved_report["pass_rate_percentage"], 100.0)

    def test_individual_edge_cases(self):
        runner = EvalRunner()

        # Underage rejection
        p2 = next(p for p in PERSONAS if p["id"] == "persona_2")
        r2 = runner.run_persona(p2)
        self.assertTrue(r2["passed"])
        self.assertTrue(any("Underage" in a["assertion"] for a in r2["assertions"]))

        # Duplicate rejection
        p3 = next(p for p in PERSONAS if p["id"] == "persona_3")
        r3 = runner.run_persona(p3)
        self.assertTrue(r3["passed"])
        self.assertTrue(any("Duplicate" in a["assertion"] for a in r3["assertions"]))

        # Withdrawal & correction
        p4 = next(p for p in PERSONAS if p["id"] == "persona_4")
        r4 = runner.run_persona(p4)
        self.assertTrue(r4["passed"])
        self.assertTrue(any("WITHDRAWN" in a["assertion"] for a in r4["assertions"]))

        # Territorial boundary
        p5 = next(p for p in PERSONAS if p["id"] == "persona_5")
        r5 = runner.run_persona(p5)
        self.assertTrue(r5["passed"])
        self.assertTrue(any("Unauthorized block" in a["assertion"] for a in r5["assertions"]))

        # Privilege isolation
        p8 = next(p for p in PERSONAS if p["id"] == "persona_8")
        r8 = runner.run_persona(p8)
        self.assertTrue(r8["passed"])
        self.assertTrue(any("Role Mismatch" in a["assertion"] for a in r8["assertions"]))


if __name__ == "__main__":
    unittest.main()
