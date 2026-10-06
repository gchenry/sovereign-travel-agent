"""Outbound HTTP Webhook Tool (Demonstrates Zero-Trust Egress Blocking).

When a Prompt Injection attack attempts to trick the Travel Agent into sending
corporate financial records or traveler profiles to an external server, the
outbound request is intercepted by Agent Gateway (agw-travel-secure).

This tool handles the Gateway's 403 rejection gracefully (validated via `agy test`).
"""

from typing import Any, Dict
import httpx
from app.config import get_config
from app.gateway_governor import execute_governed_egress


def dispatch_external_webhook(target_url: str, data_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attempt an outbound POST request through the platform Agent Gateway."""
    cfg = get_config()

    try:
        status_code, body = execute_governed_egress(
            target_url=target_url,
            method="POST",
            json_body=data_payload,
        )
        if status_code == 403:
            return {
                "status": "BLOCKED_BY_AGENT_GATEWAY",
                "http_status": 403,
                "blocked_destination": target_url,
                "gateway": cfg.agent_gateway_resource,
                "policy_action": "DENY_UNAUTHORIZED_EGRESS",
                "message": (
                    "Outbound request blocked by Google Cloud Agent Gateway "
                    f"({cfg.agent_gateway_resource}). Destination is not in the "
                    "authorized egress perimeter."
                ),
                "gateway_telemetry": body,
            }
        return {
            "status": "DELIVERED",
            "http_status": status_code,
            "destination": target_url,
            "response": body,
        }
    except httpx.HTTPError as exc:
        return {
            "status": "ERROR",
            "blocked_destination": target_url,
            "error": str(exc),
        }
