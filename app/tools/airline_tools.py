"""Tool for fetching flight schedules from the external Mock Airline API.

All outbound calls are governed by Agent Gateway (agw-travel-secure).
"""

from typing import Any, Dict
import httpx
from app.config import get_config
from app.gateway_governor import execute_governed_egress


def search_flights(origin: str, destination: str, cabin_class: str = "Business") -> Dict[str, Any]:
    """Query the external Airline API via the platform Agent Gateway."""
    cfg = get_config()
    target_url = f"{cfg.airline_api_url.rstrip('/')}/flights/search"

    try:
        status_code, body = execute_governed_egress(
            target_url=target_url,
            method="GET",
            params={
                "origin": origin,
                "destination": destination,
                "cabin": cabin_class,
            },
        )
        if status_code == 403:
            return {
                "status": "BLOCKED_BY_AGENT_GATEWAY",
                "http_status": 403,
                "gateway": cfg.agent_gateway_resource,
                "details": body or {"reason": "Gateway Egress Policy Rejection"},
            }
        return body
    except httpx.HTTPError as exc:
        return {
            "status": "ERROR",
            "error": str(exc),
        }
