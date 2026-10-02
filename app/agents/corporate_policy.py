"""The Corporate Policy Agent (Specialized ADK Sub-Agent).

Responsibilities:
Queries internal corporate databases via Model Context Protocol (MCP) tool servers
routed through Agent Gateway (agw-travel-secure) and Private Service Connect (PSC)
to enforce corporate travel & expense compliance.
"""

from typing import Any, Dict
from app.tools.mcp_client import call_corporate_mcp_tool


class CorporatePolicyAgent:
    """ADK Sub-Agent that validates travel itineraries against internal corporate MCP tools."""

    name: str = "corporate_policy_agent"
    description: str = "Queries internal Corporate MCP Server over PSC to enforce travel compliance."

    def run(
        self,
        user_id: str,
        department: str,
        cabin_class: str,
        estimated_fare_usd: float,
        override_spiffe_id: str | None = None,
    ) -> Dict[str, Any]:
        """Validate compliance and budget against internal Corporate MCP tools."""
        policy_check = call_corporate_mcp_tool(
            tool_name="verify_travel_compliance",
            arguments={
                "user_id": user_id,
                "department": department,
                "cabin_class": cabin_class,
                "estimated_fare_usd": estimated_fare_usd,
            },
            override_spiffe_id=override_spiffe_id,
        )

        return {
            "agent": self.name,
            "mcp_compliance_result": policy_check,
        }
