"""Outbound HTTP Webhook Tool (Demonstrates Zero-Trust Egress Blocking).

When a Prompt Injection attack attempts to trick the Travel Agent into sending
corporate financial records or traveler profiles to an external server, the
outbound request is intercepted by Agent Gateway (agw-travel-secure).

This tool handles the Gateway's 403 rejection gracefully (validated via `agy test`).
"""

from typing import Any, Dict
import httpx
from app.config import get_config


def dispatch_external_webhook(target_url: str, data_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attempt an outbound POST request through the platform Agent Gateway."""
    cfg = get_config()

    payload = {
        "target_url": target_url,
        "method": "POST",
        "json_body": data_payload,
    }
    headers = {"X-Workload-SPIFFE-ID": cfg.workload_spiffe_id}

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{cfg.agent_gateway_url.rstrip('/')}/egress/forward",
                json=payload,
                headers=headers,
            )
        if resp.status_code == 403:
            rejection_body = resp.json() if resp.content else {}
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
                "gateway_telemetry": rejection_body,
            }
        resp.raise_for_status()
        return {
            "status": "DELIVERED",
            "http_status": resp.status_code,
            "destination": target_url,
            "response": resp.json() if resp.content else {},
        }
    except httpx.HTTPError as exc:
        return {
            "status": "ERROR",
            "blocked_destination": target_url,
            "error": str(exc),
        }
