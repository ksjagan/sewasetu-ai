# -*- coding: utf-8 -*-
"""
Sewa Setu - Model Context Protocol (MCP) JSON-RPC 2.0 Engine
Implements standard MCP protocol methods (initialize, tools/list, tools/call, ping)
per MCP Specification (2024-11-05).
"""

import json
from typing import Dict, Any, List, Callable, Optional


class MCPHandler:
    """Handles JSON-RPC 2.0 message parsing and tool dispatch for an MCP endpoint."""

    def __init__(self, server_name: str, tools: List[Dict[str, Any]],
                 executor: Callable[[str, Dict[str, Any], Dict[str, Any]], Dict[str, Any]]):
        self.server_name = server_name
        self.tools = tools
        self.executor = executor
        self.protocol_version = "2024-11-05"

    def handle_message(self, request_data: Dict[str, Any], caller_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single JSON-RPC 2.0 request dictionary."""
        if not isinstance(request_data, dict):
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request: expected JSON object."}
            }

        msg_id = request_data.get("id")
        method = request_data.get("method")
        params = request_data.get("params") or {}

        # 1. Initialize
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": self.protocol_version,
                    "capabilities": {
                        "tools": {
                            "listChanged": False
                        }
                    },
                    "serverInfo": {
                        "name": self.server_name,
                        "version": "1.0.0"
                    }
                }
            }

        # 2. Notifications (e.g. notifications/initialized) - no response required
        elif method == "notifications/initialized":
            return None

        # 3. Ping
        elif method == "ping":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {}
            }

        # 4. Tools List
        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": self.tools
                }
            }

        # 5. Tools Call
        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments") or {}

            # Find matching tool
            matching = next((t for t in self.tools if t["name"] == tool_name), None)
            if not matching:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: tool '{tool_name}' does not exist on this endpoint."
                    }
                }

            try:
                result = self.executor(tool_name, arguments, caller_context)
                is_error = False
                if isinstance(result, dict) and (result.get("success") is False or result.get("verified") is False or "error" in result):
                    # Flag business rejection or error
                    is_error = "error" in result or "errors" in result

                formatted_text = json.dumps(result, indent=2, ensure_ascii=False) if isinstance(result, (dict, list)) else str(result)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": formatted_text
                            }
                        ],
                        "isError": is_error
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Tool execution failed: {str(e)}"
                            }
                        ],
                        "isError": True
                    }
                }

        # Unknown method
        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: '{method}'."
                }
            }
