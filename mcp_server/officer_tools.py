# -*- coding: utf-8 -*-
"""
Sewa Setu - Block Officer MCP Tools
Exposes only departmental capabilities: queue management, dossier review, and audit-backed decisions.
Enforces that applicants can never access officer tools or internal queues.
"""

import os
import sys
from typing import Dict, Any, List

# Ensure app package is importable
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app_dir = os.path.join(BASE_DIR, "app")
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

from services.portal_service import PortalService, BLOCKS


OFFICER_TOOL_DEFINITIONS = [
    {
        "name": "get_officer_dashboard_summary",
        "description": "Get an executive summary of the pension portal workload: total applications, breakdown by status (PENDING, APPROVED, DEEMED_APPROVED, REJECTED, WITHDRAWN), overdue SLA count, and pending counts per block.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "list_pending_applications",
        "description": "List applications awaiting officer review. Sorted by urgency (oldest submitted applications first, closest to the 15-day statutory deemed-approval cutoff).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "block": {
                    "type": "string",
                    "description": f"Optional filter for block: {', '.join(BLOCKS)}."
                },
                "page": {
                    "type": "integer",
                    "description": "Page number (default: 1).",
                    "default": 1
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of records to return (default: 20, max: 50).",
                    "default": 20
                }
            },
            "required": []
        }
    },
    {
        "name": "get_application_dossier",
        "description": "Retrieve full case dossier for an application: demographics, address, bank details, age, document availability, statutory SLA countdown, and complete chronological audit log.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "application_id_or_number": {
                    "type": "string",
                    "description": "Database ID (e.g. '123') or Application Number (e.g. 'SSP26481920')."
                }
            },
            "required": ["application_id_or_number"]
        }
    },
    {
        "name": "inspect_age_proof_document",
        "description": "Examine the age proof document uploaded by an applicant. Returns filename, MIME type, file size, and base64 preview.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "application_id_or_number": {
                    "type": "string",
                    "description": "Database ID (e.g. '123') or Application Number (e.g. 'SSP26481920')."
                }
            },
            "required": ["application_id_or_number"]
        }
    },
    {
        "name": "approve_pension_application",
        "description": "Approve a pending pension application. Enforces recording an official justification note against the officer's name in the immutable audit trail and triggers applicant SMS.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "application_id_or_number": {
                    "type": "string",
                    "description": "Database ID (e.g. '123') or Application Number (e.g. 'SSP26481920')."
                },
                "officer_note": {
                    "type": "string",
                    "description": "Official justification / verification remark (e.g. 'Documents verified in Sonari block camp; bank account active')."
                }
            },
            "required": ["application_id_or_number", "officer_note"]
        }
    },
    {
        "name": "reject_pension_application",
        "description": "Reject a pending pension application. Strictly enforces a mandatory justification reason recorded in the immutable audit trail and sent to the applicant via SMS.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "application_id_or_number": {
                    "type": "string",
                    "description": "Database ID (e.g. '123') or Application Number (e.g. 'SSP26481920')."
                },
                "rejection_reason": {
                    "type": "string",
                    "description": "Mandatory formal reason for rejection (e.g. 'Age proof document illegible; please re-apply with clear Voter ID')."
                }
            },
            "required": ["application_id_or_number", "rejection_reason"]
        }
    },
    {
        "name": "get_block_sla_aging_report",
        "description": "Get an SLA aging breakdown for a block: fresh cases (0-5 days), processing (5-10 days), urgent nearing SLA (10-15 days), and overdue (>15 days).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "block": {
                    "type": "string",
                    "description": f"Optional block name: {', '.join(BLOCKS)}."
                }
            },
            "required": []
        }
    }
]


def execute_officer_tool(name: str, arguments: Dict[str, Any], caller_context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute an officer tool invocation with recorded officer identity."""
    token_sub = caller_context.get("sub", "")
    officer_name = token_sub.split(":", 1)[1] if token_sub.startswith("officer:") else "admin"

    if name == "get_officer_dashboard_summary":
        return PortalService.get_officer_dashboard()

    elif name == "list_pending_applications":
        block = arguments.get("block")
        page = max(1, int(arguments.get("page", 1)))
        limit = min(50, max(1, int(arguments.get("limit", 20))))
        return PortalService.list_pending_queue(block=block, page=page, limit=limit, sort_by_sla=True)

    elif name == "get_application_dossier":
        app_ref = arguments.get("application_id_or_number")
        if not app_ref:
            return {"success": False, "error": "application_id_or_number is required."}
        return PortalService.get_application_dossier(app_ref)

    elif name == "inspect_age_proof_document":
        app_ref = arguments.get("application_id_or_number")
        if not app_ref:
            return {"success": False, "error": "application_id_or_number is required."}
        dossier = PortalService.get_application_dossier(app_ref)
        if not dossier.get("success"):
            return dossier
        doc_path = dossier["application"].get("doc_path", "")
        return PortalService.get_document_content(doc_path, as_base64=True)

    elif name == "approve_pension_application":
        app_ref = arguments.get("application_id_or_number")
        note = arguments.get("officer_note", "Approved by block officer")
        if not app_ref:
            return {"success": False, "error": "application_id_or_number is required."}
        return PortalService.officer_decide_application(
            app_ref=app_ref,
            officer_username=officer_name,
            decision="APPROVED",
            note=note
        )

    elif name == "reject_pension_application":
        app_ref = arguments.get("application_id_or_number")
        reason = arguments.get("rejection_reason", "")
        if not app_ref:
            return {"success": False, "error": "application_id_or_number is required."}
        if not reason.strip():
            return {"success": False, "error": "Rejection requires a non-empty rejection_reason."}
        return PortalService.officer_decide_application(
            app_ref=app_ref,
            officer_username=officer_name,
            decision="REJECTED",
            note=reason
        )

    elif name == "get_block_sla_aging_report":
        block = arguments.get("block")
        return PortalService.get_block_sla_breakdown(block=block)

    else:
        return {"error": f"Unknown tool '{name}'."}
