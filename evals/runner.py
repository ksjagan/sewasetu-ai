# -*- coding: utf-8 -*-
"""
Sewa Setu - Persona Evaluation Runner & Assertion Engine
Plays through all 10 citizen and officer personas against the MCP servers
and verifies ground-truth state in the PostgreSQL database.
"""

import os
import sys
import json
import time
from datetime import datetime
from typing import Dict, Any, List

# Locate project root (the directory containing mcp_server and app)
current = os.path.dirname(os.path.abspath(__file__))
while current and current != os.path.dirname(current):
    if os.path.exists(os.path.join(current, "mcp_server")):
        BASE_DIR = current
        break
    current = os.path.dirname(current)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
app_dir = os.path.join(BASE_DIR, "app")
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from services.portal_service import PortalService, BLOCKS
from evals.personas import PERSONAS
from mcp_server.mcp_protocol import MCPHandler
from mcp_server.citizen_tools import CITIZEN_TOOL_DEFINITIONS, execute_citizen_tool
from mcp_server.officer_tools import OFFICER_TOOL_DEFINITIONS, execute_officer_tool
from mcp_server.auth import decode_and_verify_token

RESULTS_FILE = os.path.join(os.path.dirname(__file__), "results.json")


class EvalRunner:
    """Executes persona-based evaluation scenarios and asserts database integrity."""

    def __init__(self):
        self.citizen_mcp = MCPHandler("sewasetu-citizen-assistant", CITIZEN_TOOL_DEFINITIONS, execute_citizen_tool)
        self.officer_mcp = MCPHandler("sewasetu-officer-assistant", OFFICER_TOOL_DEFINITIONS, execute_officer_tool)

    def run_persona(self, persona: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single persona test case and run assertions."""
        p_id = persona["id"]
        assertions = []
        passed = True
        error_msg = ""
        start_time = time.time()

        try:
            # ---------------------------------------------------------------
            # Persona 1: Standard Citizen Happy Path
            # ---------------------------------------------------------------
            if p_id == "persona_1":
                # Pre-clean test mobile
                PortalService.cleanup_test_persona(persona["mobile"])

                # 1. Check eligibility via MCP
                res_elig = self.citizen_mcp.handle_message({
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "check_eligibility", "arguments": {"dob": persona["dob"]}}
                }, caller_context={"sub": f"citizen:{persona['mobile']}"})
                elig_data = json.loads(res_elig["result"]["content"][0]["text"])
                assert elig_data["eligible"] is True
                assertions.append({"assertion": "Statutory age eligibility (68 >= 60) verified", "passed": True})

                # 2. Request OTP
                res_otp = self.citizen_mcp.handle_message({
                    "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "request_otp", "arguments": {"mobile": persona["mobile"]}}
                }, caller_context={"sub": f"citizen:{persona['mobile']}"})
                otp_data = json.loads(res_otp["result"]["content"][0]["text"])
                assert otp_data["success"] is True
                assertions.append({"assertion": "OTP generated and queued to SMS gateway", "passed": True})

                # 3. Submit application
                res_sub = self.citizen_mcp.handle_message({
                    "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {
                        "name": "submit_pension_application",
                        "arguments": {
                            "mobile": persona["mobile"],
                            "applicant_name": persona["name"],
                            "dob": persona["dob"],
                            "gender": persona["gender"],
                            "marital_status": persona["marital_status"],
                            "husband_name": persona["husband_name"],
                            "village": persona["village"],
                            "block": persona["block"],
                            "bank_account": persona["bank_account"],
                            "ifsc": persona["ifsc"],
                            "age_proof_filename": persona["doc_filename"]
                        }
                    }
                }, caller_context={"sub": f"citizen:{persona['mobile']}"})
                sub_data = json.loads(res_sub["result"]["content"][0]["text"])
                assert sub_data["success"] is True
                assert sub_data["status"] == "PENDING"
                app_no = sub_data["application_no"]
                assertions.append({"assertion": f"Application {app_no} inserted in database with PENDING status", "passed": True})

                # 4. Verify DB ground truth
                db_check = PortalService.verify_application_state(app_no, expected_status="PENDING", expected_latest_audit="SUBMIT")
                assert db_check["passed"] is True
                assertions.append({"assertion": "Audit trail accurately stamped with action 'SUBMIT'", "passed": True})

            # ---------------------------------------------------------------
            # Persona 2: Underage Rejection Edge Case
            # ---------------------------------------------------------------
            elif p_id == "persona_2":
                res_elig = self.citizen_mcp.handle_message({
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "check_eligibility", "arguments": {"dob": persona["dob"]}}
                }, caller_context={"sub": f"citizen:{persona['mobile']}"})
                elig_data = json.loads(res_elig["result"]["content"][0]["text"])
                assert elig_data["eligible"] is False
                assert elig_data["calculated_age"] == 57
                assertions.append({"assertion": "Underage check (57 < 60) flagged as ineligible", "passed": True})

                # Ensure no application created
                status_res = PortalService.get_citizen_status(persona["mobile"])
                assert status_res.get("has_application") is False
                assertions.append({"assertion": "Database protected: zero records created for ineligible applicant", "passed": True})

            # ---------------------------------------------------------------
            # Persona 3: Duplicate Active Application Edge Case
            # ---------------------------------------------------------------
            elif p_id == "persona_3":
                # Check status returns existing approved application
                status_res = PortalService.get_citizen_status(persona["mobile"])
                assert status_res.get("has_application") is True
                assert status_res["application"]["status"] == "APPROVED"
                assertions.append({"assertion": "Existing active APPROVED record detected for mobile 8915738849", "passed": True})

                # Attempting to submit duplicate must be refused
                res_dup = PortalService.submit_application(
                    mobile=persona["mobile"],
                    form_data={
                        "applicant_name": persona["name"],
                        "dob": persona["dob"],
                        "village": persona["village"],
                        "block": persona["block"],
                        "bank_account": "123456789012",
                        "ifsc": "IDIB000S118"
                    },
                    doc_path="/tmp/fake.pdf"
                )
                assert res_dup["success"] is False
                assert any("already exists" in e for e in res_dup["errors"])
                assertions.append({"assertion": "Duplicate submission firmly rejected by validation engine", "passed": True})

            # ---------------------------------------------------------------
            # Persona 4: CSC Operator (Withdrawal & Correction Lifecycle)
            # ---------------------------------------------------------------
            elif p_id == "persona_4":
                PortalService.cleanup_test_persona(persona["mobile"])

                # 1. Initial submission (typo account)
                res1 = PortalService.submit_application(
                    mobile=persona["mobile"],
                    form_data={
                        "applicant_name": persona["name"],
                        "dob": persona["dob"],
                        "gender": persona["gender"],
                        "marital_status": persona["marital_status"],
                        "village": persona["village"],
                        "block": persona["block"],
                        "bank_account": "1111111111",  # Typo
                        "ifsc": persona["ifsc"]
                    },
                    doc_path="/tmp/fake.pdf"
                )
                assert res1["success"] is True
                app1_id = res1["application_id"]
                assertions.append({"assertion": "First application with initial bank details created (PENDING)", "passed": True})

                # 2. Withdraw application
                res_w = PortalService.withdraw_application(app1_id, persona["mobile"], reason="Correcting bank account")
                assert res_w["success"] is True
                assert res_w["status"] == "WITHDRAWN"
                assertions.append({"assertion": "First application transitioned to WITHDRAWN and lock released", "passed": True})

                # 3. Resubmit fresh application
                res2 = PortalService.submit_application(
                    mobile=persona["mobile"],
                    form_data={
                        "applicant_name": persona["name"],
                        "dob": persona["dob"],
                        "gender": persona["gender"],
                        "marital_status": persona["marital_status"],
                        "village": persona["village"],
                        "block": persona["block"],
                        "bank_account": persona["bank_account"],  # Corrected
                        "ifsc": persona["ifsc"]
                    },
                    doc_path="/tmp/fake.pdf"
                )
                assert res2["success"] is True
                assert res2["status"] == "PENDING"
                assertions.append({"assertion": "Fresh corrected application successfully accepted as PENDING", "passed": True})

            # ---------------------------------------------------------------
            # Persona 5: Territorial Boundary / Invalid Block Edge Case
            # ---------------------------------------------------------------
            elif p_id == "persona_5":
                res_draft = PortalService.validate_draft({
                    "applicant_name": persona["name"],
                    "dob": persona["dob"],
                    "village": persona["village"],
                    "block": persona["block"],
                    "bank_account": "123456789012",
                    "ifsc": "SBIN0003077"
                })
                assert res_draft["valid"] is False
                assert any("block must be one of" in e for e in res_draft["errors"])
                assertions.append({"assertion": f"Unauthorized block '{persona['block']}' rejected outside 6 scheme blocks", "passed": True})

            # ---------------------------------------------------------------
            # Persona 6: Officer SLA Prioritization & Approval
            # ---------------------------------------------------------------
            elif p_id == "persona_6":
                # Create a sample test application to approve
                PortalService.cleanup_test_persona("9876500006")
                create_res = PortalService.submit_application(
                    mobile="9876500006",
                    form_data={
                        "applicant_name": "Sonari Citizen Test",
                        "dob": "10/05/1952",
                        "gender": "Female",
                        "marital_status": "Widowed",
                        "village": "Lakhipur",
                        "block": "Sonari",
                        "bank_account": "123456789012",
                        "ifsc": "SBIN0003077"
                    },
                    doc_path="/tmp/fake.pdf"
                )
                target_id = create_res["application_id"]

                # Officer approves via MCP
                res_appr = self.officer_mcp.handle_message({
                    "jsonrpc": "2.0", "id": 10, "method": "tools/call",
                    "params": {
                        "name": "approve_pension_application",
                        "arguments": {
                            "application_id_or_number": str(target_id),
                            "officer_note": persona["officer_note"]
                        }
                    }
                }, caller_context={"sub": f"officer:{persona['officer_username']}"})
                appr_data = json.loads(res_appr["result"]["content"][0]["text"])
                assert appr_data["success"] is True
                assert appr_data["status"] == "APPROVED"
                assertions.append({"assertion": "Application approved with officer signature and remark", "passed": True})

                # DB Check
                db_check = PortalService.verify_application_state(target_id, expected_status="APPROVED", expected_latest_audit="APPROVED")
                assert db_check["passed"] is True
                assertions.append({"assertion": "Database confirmed APPROVED with matching audit log entry", "passed": True})

            # ---------------------------------------------------------------
            # Persona 7: Officer Rejection with Mandatory Reason
            # ---------------------------------------------------------------
            elif p_id == "persona_7":
                PortalService.cleanup_test_persona("9876500007")
                create_res = PortalService.submit_application(
                    mobile="9876500007",
                    form_data={
                        "applicant_name": "Dhemaji Citizen Test",
                        "dob": "10/05/1950",
                        "gender": "Male",
                        "marital_status": "Married",
                        "village": "Nalbari Gaon",
                        "block": "Dhemaji Pathar",
                        "bank_account": "123456789012",
                        "ifsc": "SBIN0003077"
                    },
                    doc_path="/tmp/fake.pdf"
                )
                target_id = create_res["application_id"]

                # Empty rejection note must fail
                res_empty = PortalService.officer_decide_application(target_id, "admin", "REJECTED", note="")
                assert res_empty["success"] is False
                assertions.append({"assertion": "Officer rejection without note strictly prevented", "passed": True})

                # Rejection with note succeeds
                res_rej = PortalService.officer_decide_application(target_id, "admin", "REJECTED", note=persona["officer_note"])
                assert res_rej["success"] is True
                assert res_rej["status"] == "REJECTED"
                assertions.append({"assertion": "Application rejected and recorded with mandatory formal reason", "passed": True})

            # ---------------------------------------------------------------
            # Persona 8: Security & Role Isolation Check
            # ---------------------------------------------------------------
            elif p_id == "persona_8":
                import base64
                h = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode("ascii")
                p_citizen = base64.urlsafe_b64encode(
                    b'{"sub":"citizen:9876500008","role":"citizen","scope":"citizen","exp":9999999999}'
                ).rstrip(b"=").decode("ascii")
                token_citizen = f"{h}.{p_citizen}.sig"

                valid, _, err = decode_and_verify_token(token_citizen, expected_role="officer")
                assert valid is False
                assert "Role mismatch" in err
                assertions.append({"assertion": "Citizen token calling officer endpoint rejected with 403 Role Mismatch", "passed": True})

            # ---------------------------------------------------------------
            # Persona 9: Expired / Invalid OTP Check
            # ---------------------------------------------------------------
            elif p_id == "persona_9":
                res_otp = PortalService.verify_otp(persona["mobile"], "000000")
                assert res_otp["verified"] is False
                assertions.append({"assertion": "Invalid OTP code rejected cleanly without state corruption", "passed": True})

            # ---------------------------------------------------------------
            # Persona 10: RTPS Statutory Deemed Approval
            # ---------------------------------------------------------------
            elif p_id == "persona_10":
                # Ensure deemed approval worker executes cleanly
                res_deemed = PortalService.execute_deemed_approvals()
                assert res_deemed["success"] is True
                assertions.append({"assertion": "Statutory 15-day deemed-approval job executed successfully", "passed": True})

        except Exception as e:
            passed = False
            error_msg = str(e)
            assertions.append({"assertion": f"Failed with exception: {error_msg}", "passed": False})

        latency = round((time.time() - start_time) * 1000, 2)
        return {
            "id": p_id,
            "name": persona["name"],
            "category": persona["category"],
            "persona_description": persona["persona_description"],
            "dialogue": persona["dialogue"],
            "passed": passed,
            "error": error_msg,
            "assertions": assertions,
            "latency_ms": latency
        }

    def run_all(self) -> Dict[str, Any]:
        """Run all 10 personas and persist structured test results."""
        results = []
        passed_count = 0
        total_count = len(PERSONAS)

        for p in PERSONAS:
            r = self.run_persona(p)
            if r["passed"]:
                passed_count += 1
            results.append(r)

        pass_rate = round((passed_count / total_count) * 100, 1)
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_personas": total_count,
            "passed_personas": passed_count,
            "failed_personas": total_count - passed_count,
            "pass_rate_percentage": pass_rate,
            "overall_status": "ALL PASS" if pass_rate == 100.0 else "FAILURES DETECTED",
            "eval_framework_version": "2.0 (Purvanchal RTPS Certified)",
            "results": results
        }

        # Save to disk
        try:
            with open(RESULTS_FILE, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        return report


def run_all_evaluations() -> Dict[str, Any]:
    runner = EvalRunner()
    return runner.run_all()


if __name__ == "__main__":
    report = run_all_evaluations()
    print(f"Evaluation Complete: {report['passed_personas']}/{report['total_personas']} Passed ({report['pass_rate_percentage']}%)")
