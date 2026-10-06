"""Model Context Protocol (MCP) Client Tool for Internal Corporate Policy DB.

Traffic is governed by Agent Gateway (agw-travel-secure) + Agent Registry +
Private Service Connect (PSC) to the internal Corporate MCP Server. Only workloads
with verified SPIFFE / Cloud Run Agent Identity tokens are permitted.
"""

from typing import Any, Dict
import httpx
from app.config import get_config
from app.gateway_governor import execute_governed_egress


def call_corporate_mcp_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    override_spiffe_id: str | None = None,
) -> Dict[str, Any]:
    """Invoke a tool on the internal Corporate MCP Server via Agent Gateway + PSC."""
    cfg = get_config()
    target_url = f"{cfg.mcp_server_url.rstrip('/')}/mcp/call-tool"
    effective_tool_name = (
        "override_department_budget"
        if (override_spiffe_id and cfg.agent_gateway_url.lower() == "native")
        else tool_name
    )
    json_body = {
        "jsonrpc": "2.0",
        "id": "mcp-req-1",
        "method": "tools/call",
        "params": {
            "name": effective_tool_name,
            "arguments": arguments,
        },
    }

    try:
        status_code, body = execute_governed_egress(
            target_url=target_url,
            method="POST",
            json_body=json_body,
            override_spiffe_id=override_spiffe_id,
        )
        if status_code == 403:
            return {
                "status": "BLOCKED_BY_AGENT_GATEWAY",
                "http_status": 403,
                "gateway": cfg.agent_gateway_resource,
                "details": body or {"reason": "SPIFFE / IAP Authorization Policy Violation at Agent Gateway"},
            }
        return body
    except httpx.HTTPError as exc:
        return {
            "status": "ERROR",
            "error": str(exc),
        }

