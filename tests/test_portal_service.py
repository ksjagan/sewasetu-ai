# -*- coding: utf-8 -*-
"""Unit tests for Phase 1 Portal Service comprehensive business logic."""

import unittest
from datetime import datetime, date
import sys
import os

# Add app directory to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "app"))

from services.portal_service import (
    PortalService,
    validate_application,
    parse_dob,
    age_on,
    sanitize,
    BLOCKS,
    MIN_AGE,
    now_ist
)


class TestPortalServicePhase1(unittest.TestCase):

    def test_scheme_info(self):
        info = PortalService.get_scheme_info()
        self.assertEqual(info["pension_amount_inr"], 250)
        self.assertEqual(info["minimum_age"], 60)
        self.assertEqual(info["statutory_sla_days"], 15)
        self.assertIn("Sonari", info["eligible_blocks"])
        self.assertIn("Namti", info["eligible_blocks"])
        self.assertIn("field_specifications", info)
        self.assertIn("bank_account", info["field_specifications"])

    def test_dob_parsing_and_age_calculation(self):
        # Format DD/MM/YYYY
        dob1 = parse_dob("15/08/1958")
        self.assertIsNotNone(dob1)
        self.assertEqual(dob1, date(1958, 8, 15))

        # Format YYYY-MM-DD
        dob2 = parse_dob("1960-05-20")
        self.assertIsNotNone(dob2)
        self.assertEqual(dob2, date(1960, 5, 20))

        # Format DDMMYYYY
        dob3 = parse_dob("15081958")
        self.assertIsNotNone(dob3)
        self.assertEqual(dob3, date(1958, 8, 15))

        # Invalid format
        self.assertIsNone(parse_dob("invalid-date"))

        # Age calculation
        ref_date = date(2026, 10, 27)
        self.assertEqual(age_on(date(1958, 8, 15), ref_date), 68)
        self.assertEqual(age_on(date(1966, 10, 26), ref_date), 60)
        self.assertEqual(age_on(date(1966, 10, 28), ref_date), 59)

    def test_check_eligibility(self):
        # Over 60 and resident
        res_eligible = PortalService.check_eligibility("10/05/1955", resident_of_purvanchal=True)
        self.assertTrue(res_eligible["eligible"])
        self.assertEqual(res_eligible["calculated_age"], 71)

        # Under 60
        res_underage = PortalService.check_eligibility("01/01/1975", resident_of_purvanchal=True)
        self.assertFalse(res_underage["eligible"])
        self.assertTrue(any("minimum age" in r for r in res_underage["reasons"]))

        # Non-resident
        res_non_resident = PortalService.check_eligibility("10/05/1955", resident_of_purvanchal=False)
        self.assertFalse(res_non_resident["eligible"])
        self.assertTrue(any("resident" in r for r in res_non_resident["reasons"]))

    def test_sanitize_preserves_unicode(self):
        # Assamese / Bengali script
        name = "   পূৰ্ণিমা গগৈ   "
        sanitized = sanitize(name)
        self.assertEqual(sanitized, "পূৰ্ণিমা গগৈ")

    def test_validate_draft(self):
        valid_form = {
            "applicant_name": "Smt. Ratna Das",
            "village": "Kathoni",
            "block": "Sonari",
            "gender": "Female",
            "marital_status": "Widowed",
            "bank_account": "123456789012",
            "ifsc": "SBIN0003077",
            "dob": "15/08/1958"
        }
        res = PortalService.validate_draft(valid_form, has_document=True)
        self.assertTrue(res["valid"])
        self.assertEqual(res["errors"], [])

        # Missing bank account
        invalid_form = dict(valid_form, bank_account="")
        res_invalid = PortalService.validate_draft(invalid_form, has_document=True)
        self.assertFalse(res_invalid["valid"])
        self.assertTrue(any("bank account is required" in e for e in res_invalid["errors"]))

    def test_validate_application_rules(self):
        valid_data = {
            "applicant_name": "Ratna Das",
            "village": "Kathoni",
            "block": "Sonari",
            "gender": "Female",
            "marital_status": "Widowed",
            "husband_name": "Late Nagen Das",
            "bank_account": "123456789012",
            "ifsc": "SBIN0003077",
            "dob": "15/08/1958",
        }
        # Valid case
        errors, cleaned = validate_application(valid_data, doc_path="/fake/uploads/doc.pdf")
        self.assertEqual(errors, [])
        self.assertEqual(cleaned["block"], "Sonari")
        self.assertEqual(cleaned["ifsc"], "SBIN0003077")

        # Invalid block
        bad_block = dict(valid_data, block="UnknownBlock")
        errors, _ = validate_application(bad_block, doc_path="/fake/uploads/doc.pdf")
        self.assertTrue(any("block must be one of" in e for e in errors))

        # Invalid bank account (too short)
        bad_bank = dict(valid_data, bank_account="1234")
        errors, _ = validate_application(bad_bank, doc_path="/fake/uploads/doc.pdf")
        self.assertTrue(any("bank account number must be 9 to 18 digits" in e for e in errors))

        # Invalid IFSC format (5th character not 0)
        bad_ifsc = dict(valid_data, ifsc="SBIN1003077")
        errors, _ = validate_application(bad_ifsc, doc_path="/fake/uploads/doc.pdf")
        self.assertTrue(any("IFSC must be 11 characters" in e for e in errors))

        # Missing document
        errors, _ = validate_application(valid_data, doc_path="")
        self.assertTrue(any("age proof document is required" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
