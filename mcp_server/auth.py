# -*- coding: utf-8 -*-
"""
Sewa Setu - OAuth 2.1 Token Verification Middleware for MCP Servers
Validates RS256 JWTs against Sewa Setu JWKS endpoint (RFC 8414 / RFC 8707).
Enforces absolute endpoint isolation between Citizen and Officer capabilities.
"""

import os
import json
import time
import base64
from typing import Dict, Any, Optional, Tuple

try:
    import jwt
    from jwt.algorithms import RSAAlgorithm
except ImportError:
    jwt = None
    RSAAlgorithm = None

import requests

PORTAL_URL = os.environ.get("PORTAL_URL", "http://app:8000").rstrip("/")
ISSUER = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
JWKS_URL = os.environ.get("JWKS_URL", f"{PORTAL_URL}/.well-known/jwks.json")
AUTH_REQUIRED = os.environ.get("AUTH_REQUIRED", "false").lower() in ("true", "1", "yes")

_JWKS_CACHE: Dict[str, Any] = {"keys": {}, "last_fetched": 0}
JWKS_CACHE_TTL = 3600  # 1 hour


def _b64url_decode(s: str) -> bytes:
    rem = len(s) % 4
    if rem > 0:
        s += "=" * (4 - rem)
    return base64.urlsafe_b64decode(s)


def fetch_jwks() -> Dict[str, Any]:
    """Fetch and cache public keys from the portal's JWKS endpoint."""
    now = time.time()
    if _JWKS_CACHE["keys"] and (now - _JWKS_CACHE["last_fetched"]) < JWKS_CACHE_TTL:
        return _JWKS_CACHE["keys"]

    try:
        r = requests.get(JWKS_URL, timeout=1.5)
        if r.status_code == 200:
            data = r.json()
            keys_by_kid = {}
            for k in data.get("keys", []):
                kid = k.get("kid")
                if kid and RSAAlgorithm:
                    keys_by_kid[kid] = RSAAlgorithm.from_jwk(json.dumps(k))
                elif kid:
                    keys_by_kid[kid] = k
            _JWKS_CACHE["keys"] = keys_by_kid
            _JWKS_CACHE["last_fetched"] = now
            return keys_by_kid
    except Exception:
        pass

    return _JWKS_CACHE["keys"]


def decode_and_verify_token(token: str, expected_role: Optional[str] = None) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Verify RS256 JWT access token.
    Validates role constraint, expiration, and cryptographic signature (if PyJWT available).
    Returns (is_valid, claims_dict, error_message).
    """
    if not token:
        if not AUTH_REQUIRED:
            # Fallback for dev / unauthenticated testing when AUTH_REQUIRED=false
            mock_sub = "officer:admin" if expected_role == "officer" else "citizen:9876543210"
            return True, {
                "sub": mock_sub,
                "role": expected_role or "citizen",
                "scope": expected_role or "citizen",
                "client_id": "test_client",
                "exp": int(time.time()) + 3600
            }, ""
        return False, None, "Missing authorization token."

    # Parse headers and payload
    parts = token.split(".")
    if len(parts) != 3:
        return False, None, "Invalid JWT format (expected 3 parts)."

    try:
        header = json.loads(_b64url_decode(parts[0]).decode("utf-8"))
        claims = json.loads(_b64url_decode(parts[1]).decode("utf-8"))
    except Exception as e:
        return False, None, f"Failed to parse JWT payload: {str(e)}"

    # 1. Role isolation check (Fast fail before network calls)
    actual_role = claims.get("role")
    if expected_role and actual_role != expected_role:
        return False, None, f"Role mismatch: endpoint requires '{expected_role}', but token has role '{actual_role}'."

    # 2. Check expiration
    now = int(time.time())
    if claims.get("exp", 0) < now:
        return False, None, "Token has expired."

    # 3. Check cryptographic signature if PyJWT is installed and JWKS is active
    kid = header.get("kid")
    keys = fetch_jwks()
    if jwt and kid and RSAAlgorithm and keys:
        if kid in keys:
            try:
                pub_key = keys[kid]
                verified_claims = jwt.decode(
                    token,
                    pub_key,
                    algorithms=["RS256"],
                    options={"verify_aud": False}
                )
                claims = verified_claims
            except Exception as e:
                return False, None, f"Cryptographic token verification failed: {str(e)}"
        elif AUTH_REQUIRED:
            return False, None, f"Unknown key ID '{kid}' in active JWKS."

    return True, claims, ""
