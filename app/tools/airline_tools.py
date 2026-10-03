"""Tool for fetching flight schedules from the external Mock Airline API.

All outbound calls traverse the Agent Gateway (Egress Mode).
"""

from typing import Any, Dict
import httpx
from app.config import get_cloud_run_headers, get_config


def search_flights(origin: str, destination: str, cabin_class: str = "Business") -> Dict[str, Any]:
    """Query the external Airline API via the platform Agent Gateway."""
    cfg = get_config()
    target_url = f"{cfg.airline_api_url.rstrip('/')}/flights/search"
    gw_endpoint = f"{cfg.agent_gateway_url.rstrip('/')}/egress/forward"

    payload = {
        "target_url": target_url,
        "method": "GET",
        "params": {
            "origin": origin,
            "destination": destination,
            "cabin": cabin_class,
        },
    }
    headers = get_cloud_run_headers(gw_endpoint, {"X-Workload-SPIFFE-ID": cfg.workload_spiffe_id})

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                gw_endpoint,
                json=payload,
                headers=headers,
            )
        if resp.status_code == 403:
            error_detail = resp.json() if resp.content else {"reason": "Gateway Egress Policy Rejection"}
            return {
                "status": "BLOCKED_BY_AGENT_GATEWAY",
                "http_status": 403,
                "gateway": cfg.agent_gateway_resource,
                "details": error_detail,
            }
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        return {
            "status": "ERROR",
            "error": str(exc),
        }
