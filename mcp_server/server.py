# -*- coding: utf-8 -*-
"""
Sewa Setu - Streamable HTTP MCP Servers (Starlette ASGI Application)
Provides two distinct endpoints:
  - /mcp/citizen  (Applicant MCP: eligibility, OTP, application, status, withdrawal)
  - /mcp/officer  (Block Officer MCP: queues, dossiers, SLA aging, approve/reject)

Supports both Streamable HTTP JSON-RPC POST and Server-Sent Events (SSE) transports.
"""

import os
import sys
import json
import uuid
import asyncio
from typing import Dict, Any

from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response, PlainTextResponse
from starlette.requests import Request
from starlette.routing import Route
from starlette.middleware.cors import CORSMiddleware

# Ensure path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from mcp_server.auth import decode_and_verify_token
from mcp_server.mcp_protocol import MCPHandler
from mcp_server.citizen_tools import CITIZEN_TOOL_DEFINITIONS, execute_citizen_tool
from mcp_server.officer_tools import OFFICER_TOOL_DEFINITIONS, execute_officer_tool

# Handlers for both roles
citizen_handler = MCPHandler(
    server_name="sewasetu-citizen-assistant",
    tools=CITIZEN_TOOL_DEFINITIONS,
    executor=execute_citizen_tool
)

officer_handler = MCPHandler(
    server_name="sewasetu-officer-assistant",
    tools=OFFICER_TOOL_DEFINITIONS,
    executor=execute_officer_tool
)

# Active SSE sessions: {session_id: asyncio.Queue}
citizen_sessions: Dict[str, asyncio.Queue] = {}
officer_sessions: Dict[str, asyncio.Queue] = {}


def get_token_from_request(request: Request) -> str:
    """Extract Bearer token from Authorization header or 'token' query param."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    return request.query_params.get("token", "")


# ---------------------------------------------------------------------------
# Citizen Endpoint Handlers
# ---------------------------------------------------------------------------

async def citizen_http_post(request: Request) -> Response:
    """Direct Streamable HTTP JSON-RPC POST endpoint for citizen assistant."""
    token = get_token_from_request(request)
    valid, claims, err = decode_and_verify_token(token, expected_role="citizen")
    if not valid:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": f"Unauthorized: {err}"}},
            status_code=401 if "Missing" in err else 403
        )

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error: Invalid JSON."}},
            status_code=400
        )

    response = citizen_handler.handle_message(payload, caller_context=claims)
    if response is None:
        return Response(status_code=204)
    return JSONResponse(response)


async def citizen_sse(request: Request) -> Response:
    """Server-Sent Events (SSE) transport initialization for citizen assistant."""
    token = get_token_from_request(request)
    valid, claims, err = decode_and_verify_token(token, expected_role="citizen")
    if not valid:
        return JSONResponse({"error": err}, status_code=401 if "Missing" in err else 403)

    session_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    citizen_sessions[session_id] = queue

    # Message posting URL for this session
    message_endpoint = f"/mcp/citizen/messages?session_id={session_id}"

    async def event_generator():
        try:
            # First send endpoint declaration event per MCP SSE specification
            yield f"event: endpoint\ndata: {message_endpoint}\n\n"
            while True:
                msg = await queue.get()
                yield f"event: message\ndata: {json.dumps(msg)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            citizen_sessions.pop(session_id, None)

    from starlette.responses import StreamingResponse
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


async def citizen_message_post(request: Request) -> Response:
    """Handle incoming JSON-RPC message sent to an established SSE session."""
    session_id = request.query_params.get("session_id", "")
    token = get_token_from_request(request)
    valid, claims, err = decode_and_verify_token(token, expected_role="citizen")
    if not valid:
        return JSONResponse({"error": err}, status_code=401 if "Missing" in err else 403)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    response = citizen_handler.handle_message(payload, caller_context=claims)

    # If SSE queue exists, push response to SSE stream; also return response in HTTP POST body
    if session_id in citizen_sessions and response is not None:
        await citizen_sessions[session_id].put(response)

    if response is None:
        return Response(status_code=204)
    return JSONResponse(response)


# ---------------------------------------------------------------------------
# Officer Endpoint Handlers
# ---------------------------------------------------------------------------

async def officer_http_post(request: Request) -> Response:
    """Direct Streamable HTTP JSON-RPC POST endpoint for block officer assistant."""
    token = get_token_from_request(request)
    valid, claims, err = decode_and_verify_token(token, expected_role="officer")
    if not valid:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": f"Unauthorized: {err}"}},
            status_code=401 if "Missing" in err else 403
        )

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error: Invalid JSON."}},
            status_code=400
        )

    response = officer_handler.handle_message(payload, caller_context=claims)
    if response is None:
        return Response(status_code=204)
    return JSONResponse(response)


async def officer_sse(request: Request) -> Response:
    """Server-Sent Events (SSE) transport initialization for block officer assistant."""
    token = get_token_from_request(request)
    valid, claims, err = decode_and_verify_token(token, expected_role="officer")
    if not valid:
        return JSONResponse({"error": err}, status_code=401 if "Missing" in err else 403)

    session_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    officer_sessions[session_id] = queue

    message_endpoint = f"/mcp/officer/messages?session_id={session_id}"

    async def event_generator():
        try:
            yield f"event: endpoint\ndata: {message_endpoint}\n\n"
            while True:
                msg = await queue.get()
                yield f"event: message\ndata: {json.dumps(msg)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            officer_sessions.pop(session_id, None)

    from starlette.responses import StreamingResponse
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


async def officer_message_post(request: Request) -> Response:
    """Handle incoming JSON-RPC message sent to an established officer SSE session."""
    session_id = request.query_params.get("session_id", "")
    token = get_token_from_request(request)
    valid, claims, err = decode_and_verify_token(token, expected_role="officer")
    if not valid:
        return JSONResponse({"error": err}, status_code=401 if "Missing" in err else 403)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    response = officer_handler.handle_message(payload, caller_context=claims)

    if session_id in officer_sessions and response is not None:
        await officer_sessions[session_id].put(response)

    if response is None:
        return Response(status_code=204)
    return JSONResponse(response)


# ---------------------------------------------------------------------------
# General Discovery & Health
# ---------------------------------------------------------------------------

async def health(request: Request) -> Response:
    return JSONResponse({"status": "healthy", "service": "sewasetu-mcp-server"})


async def root_discovery(request: Request) -> Response:
    return JSONResponse({
        "service": "Sewa Setu Model Context Protocol (MCP) Server",
        "protocol": "Model Context Protocol (2024-11-05)",
        "endpoints": {
            "citizen_assistant": {
                "http_post": "/mcp/citizen",
                "sse_stream": "/mcp/citizen/sse",
                "message_endpoint": "/mcp/citizen/messages",
                "required_scope": "citizen"
            },
            "officer_assistant": {
                "http_post": "/mcp/officer",
                "sse_stream": "/mcp/officer/sse",
                "message_endpoint": "/mcp/officer/messages",
                "required_scope": "officer"
            }
        }
    })


routes = [
    Route("/", root_discovery, methods=["GET"]),
    Route("/health", health, methods=["GET"]),
    
    # Citizen routes
    Route("/mcp/citizen", citizen_http_post, methods=["POST"]),
    Route("/mcp/citizen", citizen_sse, methods=["GET"]),
    Route("/mcp/citizen/sse", citizen_sse, methods=["GET"]),
    Route("/mcp/citizen/messages", citizen_message_post, methods=["POST"]),

    # Officer routes
    Route("/mcp/officer", officer_http_post, methods=["POST"]),
    Route("/mcp/officer", officer_sse, methods=["GET"]),
    Route("/mcp/officer/sse", officer_sse, methods=["GET"]),
    Route("/mcp/officer/messages", officer_message_post, methods=["POST"]),
]

app = Starlette(routes=routes)

# Enable CORS for browser-based / web-agent access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("mcp_server.server:app", host="0.0.0.0", port=8001, reload=False)
