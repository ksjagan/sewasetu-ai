# -*- coding: utf-8 -*-
"""Unit tests for Phase 2 MCP Servers (Citizen vs Officer tools, protocol, and role isolation)."""

import os
import sys
import json
import base64
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
app_dir = os.path.join(BASE_DIR, "app")
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from mcp_server.mcp_protocol import MCPHandler
from mcp_server.citizen_tools import CITIZEN_TOOL_DEFINITIONS, execute_citizen_tool
from mcp_server.officer_tools import OFFICER_TOOL_DEFINITIONS, execute_officer_tool
from mcp_server.auth import decode_and_verify_token


class TestMCPServersPhase2(unittest.TestCase):

    def setUp(self):
        self.citizen_handler = MCPHandler(
            server_name="sewasetu-citizen-assistant",
            tools=CITIZEN_TOOL_DEFINITIONS,
            executor=execute_citizen_tool
        )
        self.officer_handler = MCPHandler(
            server_name="sewasetu-officer-assistant",
            tools=OFFICER_TOOL_DEFINITIONS,
            executor=execute_officer_tool
        )

    def test_citizen_mcp_initialize(self):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "claude-code", "version": "1.0"}
            }
        }
        res = self.citizen_handler.handle_message(payload, caller_context={})
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 1)
        self.assertEqual(res["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(res["result"]["serverInfo"]["name"], "sewasetu-citizen-assistant")

    def test_officer_mcp_initialize(self):
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "claude-code", "version": "1.0"}
            }
        }
        res = self.officer_handler.handle_message(payload, caller_context={})
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 2)
        self.assertEqual(res["result"]["protocolVersion"], "2024-11-05")
        self.assertEqual(res["result"]["serverInfo"]["name"], "sewasetu-officer-assistant")

    def test_citizen_tools_isolation(self):
        payload = {"jsonrpc": "2.0", "id": 3, "method": "tools/list"}
        res = self.citizen_handler.handle_message(payload, caller_context={})
        tools = res["result"]["tools"]
        tool_names = [t["name"] for t in tools]

        # Citizen tools MUST be present
        self.assertIn("get_scheme_information", tool_names)
        self.assertIn("check_eligibility", tool_names)
        self.assertIn("request_otp", tool_names)
        self.assertIn("verify_otp", tool_names)
        self.assertIn("submit_pension_application", tool_names)
        self.assertIn("check_application_status", tool_names)
        self.assertIn("withdraw_pending_application", tool_names)

        # Officer tools MUST NEVER be present in citizen tools
        self.assertNotIn("approve_pension_application", tool_names)
        self.assertNotIn("reject_pension_application", tool_names)
        self.assertNotIn("list_pending_applications", tool_names)
        self.assertNotIn("get_officer_dashboard_summary", tool_names)
        self.assertNotIn("get_block_sla_aging_report", tool_names)

    def test_officer_tools_isolation(self):
        payload = {"jsonrpc": "2.0", "id": 4, "method": "tools/list"}
        res = self.officer_handler.handle_message(payload, caller_context={})
        tools = res["result"]["tools"]
        tool_names = [t["name"] for t in tools]

        # Officer tools MUST be present
        self.assertIn("get_officer_dashboard_summary", tool_names)
        self.assertIn("list_pending_applications", tool_names)
        self.assertIn("get_application_dossier", tool_names)
        self.assertIn("approve_pension_application", tool_names)
        self.assertIn("reject_pension_application", tool_names)
        self.assertIn("get_block_sla_aging_report", tool_names)

        # Citizen tools MUST NOT be in officer tools
        self.assertNotIn("request_otp", tool_names)
        self.assertNotIn("verify_otp", tool_names)
        self.assertNotIn("submit_pension_application", tool_names)

    def test_citizen_tool_call_eligibility(self):
        # Eligible call
        call_eligible = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "check_eligibility",
                "arguments": {"dob": "15/08/1958", "resident_of_purvanchal": True}
            }
        }
        res = self.citizen_handler.handle_message(call_eligible, caller_context={"sub": "citizen:9876500001"})
        self.assertFalse(res["result"]["isError"])
        data = json.loads(res["result"]["content"][0]["text"])
        self.assertTrue(data["eligible"])
        self.assertEqual(data["calculated_age"], 68)

        # Underage call
        call_underage = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "check_eligibility",
                "arguments": {"dob": "01/01/1980", "resident_of_purvanchal": True}
            }
        }
        res2 = self.citizen_handler.handle_message(call_underage, caller_context={"sub": "citizen:9876500001"})
        data2 = json.loads(res2["result"]["content"][0]["text"])
        self.assertFalse(data2["eligible"])
        self.assertTrue(any("minimum age" in r for r in data2["reasons"]))

    def test_citizen_tool_call_scheme_info(self):
        call_info = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "get_scheme_information",
                "arguments": {}
            }
        }
        res = self.citizen_handler.handle_message(call_info, caller_context={})
        self.assertFalse(res["result"]["isError"])
        data = json.loads(res["result"]["content"][0]["text"])
        self.assertEqual(data["pension_amount_inr"], 250)
        self.assertEqual(data["minimum_age"], 60)
        self.assertEqual(data["statutory_sla_days"], 15)

    def test_role_mismatch_auth_isolation(self):
        # Craft mock tokens
        h = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode("ascii")
        
        # 1. Citizen token attempting officer action
        p_citizen = base64.urlsafe_b64encode(
            b'{"sub":"citizen:9876500001","role":"citizen","scope":"citizen","exp":9999999999}'
        ).rstrip(b"=").decode("ascii")
        token_citizen = f"{h}.{p_citizen}.sig"

        valid, claims, err = decode_and_verify_token(token_citizen, expected_role="officer")
        self.assertFalse(valid)
        self.assertIn("Role mismatch", err)

        # 2. Officer token attempting citizen action
        p_officer = base64.urlsafe_b64encode(
            b'{"sub":"officer:admin","role":"officer","scope":"officer","exp":9999999999}'
        ).rstrip(b"=").decode("ascii")
        token_officer = f"{h}.{p_officer}.sig"

        valid2, claims2, err2 = decode_and_verify_token(token_officer, expected_role="citizen")
        self.assertFalse(valid2)
        self.assertIn("Role mismatch", err2)

        # 3. Matching role succeeds
        valid3, claims3, _ = decode_and_verify_token(token_citizen, expected_role="citizen")
        self.assertTrue(valid3)
        self.assertEqual(claims3["role"], "citizen")


if __name__ == "__main__":
    unittest.main()
