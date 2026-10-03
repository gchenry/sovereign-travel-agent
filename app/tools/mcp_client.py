"""Model Context Protocol (MCP) Client Tool for Internal Corporate Policy DB.

Traffic is routed through Agent Gateway (agw-travel-secure) over Private
Service Connect (PSC) to the internal Corporate MCP Server. Only workloads
with verified SPIFFE JWT-SVID tokens are permitted by the Gateway.
"""

from typing import Any, Dict
import httpx
from app.config import get_cloud_run_headers, get_config


def call_corporate_mcp_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    override_spiffe_id: str | None = None,
) -> Dict[str, Any]:
    """Invoke a tool on the internal Corporate MCP Server via Agent Gateway + PSC."""
    cfg = get_config()
    target_url = f"{cfg.mcp_server_url.rstrip('/')}/mcp/call-tool"
    gw_endpoint = f"{cfg.agent_gateway_url.rstrip('/')}/egress/forward"
    spiffe_id = override_spiffe_id or cfg.workload_spiffe_id

    payload = {
        "target_url": target_url,
        "method": "POST",
        "json_body": {
            "jsonrpc": "2.0",
            "id": "mcp-req-1",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        },
    }
    headers = get_cloud_run_headers(gw_endpoint, {"X-Workload-SPIFFE-ID": spiffe_id})

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                gw_endpoint,
                json=payload,
                headers=headers,
            )
        if resp.status_code == 403:
            error_detail = resp.json() if resp.content else {"reason": "SPIFFE or Egress Policy Violation"}
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
