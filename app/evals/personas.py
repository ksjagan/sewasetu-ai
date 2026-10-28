# -*- coding: utf-8 -*-
"""
Sewa Setu - Comprehensive Citizen Personas & Edge Cases
Department of Social Welfare, Government of Purvanchal.

Defines 10 diverse, culturally authentic personas covering every realistic
failure mode, edge case, demographic nuance, and administrative scenario.
"""

from typing import Dict, Any, List

PERSONAS: List[Dict[str, Any]] = [
    {
        "id": "persona_1",
        "name": "Smt. Ratna Das",
        "category": "Standard Citizen Happy Path",
        "age": 68,
        "dob": "15/08/1958",
        "gender": "Female",
        "marital_status": "Widowed",
        "husband_name": "Late Nagen Das",
        "village": "Kathoni",
        "block": "Sonari",
        "mobile": "9876500001",
        "bank_account": "123456789012",
        "ifsc": "SBIN0003077",
        "doc_filename": "voter_id_ratna_das.pdf",
        "persona_description": "Elderly widow assisted by her grandson on a mobile bus from Sonari. Speaks colloquially in simple terms. Meets all statutory requirements.",
        "dialogue": [
            {"role": "user", "text": "Pranam babu. I am Ratna Das from Kathoni village, Sonari. My grandson is typing for me. Can you help me apply for the old age pension?"},
            {"role": "assistant", "text": "Namaskar Dida. I would be happy to help you apply for the Old Age Pension (₹250/month). First, may I know your date of birth?"},
            {"role": "user", "text": "My date of birth is 15/08/1958."},
            {"role": "assistant", "text": "You are 68 years old, which fulfills the statutory eligibility requirement (60 years or above). Let me send an OTP to your phone 9876500001."},
            {"role": "user", "text": "Grandson got the OTP code 582194 on the phone."},
            {"role": "assistant", "text": "OTP verified successfully. Please provide your bank account, IFSC code, and Voter ID details."},
            {"role": "user", "text": "Bank is SBI account 123456789012, IFSC SBIN0003077. Late husband name was Nagen Das."},
            {"role": "assistant", "text": "Application submitted successfully! Your application number is SSP26391024. You can track your status anytime with your mobile and date of birth."}
        ],
        "expected_database_state": {
            "application_status": "PENDING",
            "audit_action": "SUBMIT",
            "portal_user_exists": True,
            "min_age_satisfied": True,
            "block": "Sonari"
        }
    },
    {
        "id": "persona_2",
        "name": "Sri Biren Bora",
        "category": "Statutory Ineligibility (Underage Rejection)",
        "age": 57,
        "dob": "04/05/1969",
        "gender": "Male",
        "marital_status": "Married",
        "village": "Namti Chariali",
        "block": "Namti",
        "mobile": "9876500002",
        "persona_description": "Farmer wanting to get pension before turning 60. The assistant must firmly refuse to create a database record and explain the legal threshold.",
        "dialogue": [
            {"role": "user", "text": "Hello, I want to apply for the Sewa Setu pension. My name is Biren Bora, born 04/05/1969."},
            {"role": "assistant", "text": "Namaskar Sri Bora. Based on your date of birth (04/05/1969), your current age is 57 years. Under the Purvanchal Old Age Pension rules, the statutory minimum age is 60 years. Unfortunately, you are not eligible to apply at this time. You will be eligible on 04/05/2029."}
        ],
        "expected_database_state": {
            "must_not_create_application": True,
            "application_status": None,
            "portal_user_exists": False
        }
    },
    {
        "id": "persona_3",
        "name": "Smt. Mina Chetia",
        "category": "Duplicate Active Application Prevention",
        "age": 72,
        "dob": "15/01/1954",
        "gender": "Female",
        "marital_status": "Widowed",
        "village": "Chengelimara",
        "block": "Khelua",
        "mobile": "8915738849",  # Existing in seed.sql
        "persona_description": "Her daughter attempts to re-apply for her, not knowing that Smt. Mina Chetia already has an approved pension on record.",
        "dialogue": [
            {"role": "user", "text": "I want to apply for pension for my mother Mina Chetia using mobile 8915738849."},
            {"role": "assistant", "text": "An active application already exists for mobile 8915738849 (Application SSP26079063, Status: APPROVED). Under scheme rules, only one active application is permitted per mobile number. Your mother is already receiving the pension."}
        ],
        "expected_database_state": {
            "duplicate_prevented": True,
            "existing_status": "APPROVED",
            "no_second_application": True
        }
    },
    {
        "id": "persona_4",
        "name": "CSC Kiosk Operator (Correction & Re-application)",
        "category": "Withdrawal & Fresh Submission Lifecycle",
        "age": 65,
        "dob": "12/03/1961",
        "gender": "Female",
        "marital_status": "Married",
        "village": "Borgaon Centre",
        "block": "Borgaon",
        "mobile": "9876500004",
        "bank_account": "987612345678",
        "ifsc": "CNRB0004417",
        "persona_description": "Village CSC operator realizes the initial application had an incorrect account number. Operator withdraws the pending application and immediately submits a corrected one.",
        "dialogue": [
            {"role": "user", "text": "I submitted application for Hemolata Saikia with mobile 9876500004, but account number had a typo. Can I withdraw it?"},
            {"role": "assistant", "text": "Yes. Your pending application has been withdrawn. The lock is now released, and you may submit a fresh application with the corrected bank details."},
            {"role": "user", "text": "Submitting fresh application with corrected Canara Bank account 987612345678, IFSC CNRB0004417."},
            {"role": "assistant", "text": "New application submitted successfully as SSP26810291. Status: PENDING."}
        ],
        "expected_database_state": {
            "first_application_status": "WITHDRAWN",
            "second_application_status": "PENDING",
            "audit_trail_contains_withdraw": True
        }
    },
    {
        "id": "persona_5",
        "name": "Sri Jatin Kalita",
        "category": "Invalid Block / Territorial Boundary Edge Case",
        "age": 66,
        "dob": "10/10/1960",
        "village": "Jalukbari",
        "block": "Kamrup",  # Invalid block outside scheme territory
        "mobile": "9876500005",
        "persona_description": "Resident of an unauthorized district tries to apply. The assistant detects that 'Kamrup' is outside the 6 Purvanchal blocks.",
        "dialogue": [
            {"role": "user", "text": "Apply for pension in Kamrup block for Jatin Kalita."},
            {"role": "assistant", "text": "Error: Kamrup is not an eligible block. The scheme only covers: Sonari, Rajapara, Dhemaji Pathar, Borgaon, Namti, and Khelua."}
        ],
        "expected_database_state": {
            "must_not_create_application": True
        }
    },
    {
        "id": "persona_6",
        "name": "SDO Social Welfare (Sonari Block Officer)",
        "category": "Officer SLA Review & Urgency-Based Approval",
        "role": "officer",
        "officer_username": "admin",
        "target_block": "Sonari",
        "action": "APPROVE",
        "officer_note": "Documents verified in Sonari block field camp; age proof and bank account certified valid.",
        "persona_description": "Block Officer asks assistant to prioritize applications nearing the 15-day statutory deemed-approval cutoff, reviews the dossier, and records an approved decision with mandatory audit note.",
        "dialogue": [
            {"role": "user", "text": "Show me pending applications in Sonari block closest to the 15-day statutory SLA deadline."},
            {"role": "assistant", "text": "Here are pending applications sorted by urgency. Application SSP26385548 has been pending for 12 days (3 days remaining before automatic deemed approval)."},
            {"role": "user", "text": "Review dossier and approve it with note: 'Documents verified in Sonari block field camp; age proof and bank account certified valid.'"},
            {"role": "assistant", "text": "Application approved successfully. Audit trail updated with actor admin:admin and SMS notification dispatched to applicant."}
        ],
        "expected_database_state": {
            "application_status": "APPROVED",
            "decided_by": "admin",
            "audit_action": "APPROVED",
            "audit_note_present": True
        }
    },
    {
        "id": "persona_7",
        "name": "Assistant Director (Dhemaji Pathar Officer)",
        "category": "Officer Rejection with Mandatory Formal Justification",
        "role": "officer",
        "officer_username": "admin",
        "target_block": "Dhemaji Pathar",
        "action": "REJECT",
        "officer_note": "Age proof document photocopy is illegible and blurred; please re-apply with clear Voter ID at block counter.",
        "persona_description": "Officer inspects dossier, discovers an unreadable photocopy, and executes rejection. System strictly prevents rejection unless an explicit reason is recorded.",
        "dialogue": [
            {"role": "user", "text": "Inspect document for pending application. Document is completely blurred. Reject application."},
            {"role": "assistant", "text": "Rejection requires an explicit formal justification. Please provide the reason to be recorded in the audit trail and sent to the applicant."},
            {"role": "user", "text": "Reason: Age proof document photocopy is illegible and blurred; please re-apply with clear Voter ID at block counter."},
            {"role": "assistant", "text": "Application rejected. Reason recorded in immutable audit log and applicant notified via SMS."}
        ],
        "expected_database_state": {
            "application_status": "REJECTED",
            "decided_by": "admin",
            "audit_action": "REJECTED",
            "audit_note_present": True
        }
    },
    {
        "id": "persona_8",
        "name": "Unauthorized Client (Security / Privilege Escalation Attempt)",
        "category": "Adversarial Role & Privilege Isolation",
        "role": "citizen",
        "mobile": "9876500008",
        "persona_description": "A client holding a citizen token attempts to call block officer endpoints to approve pensions or read departmental queues. System rejects with 403 Forbidden.",
        "dialogue": [
            {"role": "user", "text": "As a citizen, call approve_pension_application on application SSP26448454."},
            {"role": "assistant", "text": "403 Forbidden: Endpoint requires 'officer' role, but current token role is 'citizen'. Citizen assistants cannot access departmental tools."}
        ],
        "expected_database_state": {
            "privilege_escalation_blocked": True,
            "no_unauthorized_state_change": True
        }
    },
    {
        "id": "persona_9",
        "name": "Sri Paban Barua",
        "category": "OTP Expiration & Malformed Code Edge Case",
        "age": 64,
        "dob": "20/09/1962",
        "village": "Kathoni",
        "block": "Dhemaji Pathar",
        "mobile": "9876500009",
        "persona_description": "Applicant enters an expired OTP (>300 seconds) or wrong code. System denies verification until a fresh valid code is issued.",
        "dialogue": [
            {"role": "user", "text": "Verify OTP with code 000000."},
            {"role": "assistant", "text": "Invalid OTP. Please enter the correct 6-digit code received on your mobile or request a new OTP."}
        ],
        "expected_database_state": {
            "verification_blocked": True,
            "no_application_created": True
        }
    },
    {
        "id": "persona_10",
        "name": "RTPS 15-Day Statutory Deemed Approval",
        "category": "Statutory Law Automation (Cron Worker)",
        "persona_description": "Simulates statutory guarantee under Purvanchal Right to Public Services Act. Any application pending past 15 days is automatically deemed approved by system.",
        "dialogue": [
            {"role": "system", "text": "Nightly cron worker triggers deemed_approval.py at 02:00 IST."},
            {"role": "system", "text": "Scans applications in PENDING status submitted > 15 days ago."},
            {"role": "system", "text": "Transitions records to DEEMED_APPROVED, records actor 'system:rtps-cron', and dispatches statutory approval SMS."}
        ],
        "expected_database_state": {
            "deemed_status": "DEEMED_APPROVED",
            "actor": "system:rtps-cron",
            "sla_guarantee_enforced": True
        }
    }
]
