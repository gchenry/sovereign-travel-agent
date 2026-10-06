"""Secure Corporate MCP Server & Internal Database Policy Enforcer.

Exposes Model Context Protocol (MCP) tools over HTTP/JSON-RPC inside the
private corporate VPC perimeter (reached via Private Service Connect from
Google Cloud Agent Gateway `agw-travel-secure`).
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Secure Corporate MCP Server (Internal VPC + PSC)",
    version="0.2.0",
)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_LOCAL_CORP_DB_PATH = Path(
    os.getenv("CORP_DB_MOUNT_PATH", str(_REPO_ROOT / "data" / "corporate_db.local.json"))
)
_EXAMPLE_CORP_DB_PATH = _REPO_ROOT / "data" / "corporate_db.example.json"

_AIRPORT_TO_COUNTRY: Dict[str, str] = {
    "HND": "Japan",
    "LHR": "United Kingdom",
    "JFK": "United States",
    "ZRH": "Switzerland",
    "SYD": "Australia",
    "IKA": "Iran",
    "FNJ": "North Korea",
    "DAM": "Syria",
    "HAV": "Cuba",
    "SVO": "Russia",
}


def _load_corp_db() -> Dict[str, Dict[str, Any]]:
    """Load corporate department budget & policy records from gitignored local file."""
    for path in (_LOCAL_CORP_DB_PATH, _EXAMPLE_CORP_DB_PATH):
        if path.exists():
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
    return {
        "Engineering": {
            "max_business_class_fare_usd": 5500.0,
            "max_economy_fare_usd": 1800.0,
            "remaining_q4_budget_usd": 18500.0,
            "allowed_cabins_international": ["Economy", "Premium Economy", "Business"],
            "embargoed_countries": ["Iran", "North Korea", "Syria", "Cuba", "Russia"],
            "embargoed_airports": ["IKA", "FNJ", "DAM", "HAV", "SVO"],
            "policy_id": "CORP-TRAVEL-ENG-2026",
        }
    }


class MCPToolCallRequest(BaseModel):
    """Standard JSON-RPC 2.0 MCP request payload."""

    jsonrpc: str = "2.0"
    id: str | int | None = "mcp-req-1"
    method: str = "tools/call"
    params: Dict[str, Any] = {}


_MCP_TOOLS_SPEC: List[Dict[str, Any]] = [
    {
        "name": "verify_travel_compliance",
        "description": "Queries internal Corporate DB to validate destination embargoes, cabin, and fare against Q4 budget.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "department": {"type": "string"},
                "cabin_class": {"type": "string"},
                "estimated_fare_usd": {"type": "number"},
                "destination": {"type": "string"},
            },
            "required": ["user_id", "department", "cabin_class", "estimated_fare_usd"],
        },
    },
    {
        "name": "override_department_budget",
        "description": "Privileged administrative tool to override corporate department travel budget caps.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "department": {"type": "string"},
                "cabin_class": {"type": "string"},
                "estimated_fare_usd": {"type": "number"},
                "destination": {"type": "string"},
            },
            "required": ["user_id", "department"],
        },
    },
]


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "healthy", "service": "corporate-mcp-server", "ingress": "INTERNAL_PSC_ONLY"}


@app.get("/mcp/tools")
def list_mcp_tools() -> Dict[str, Any]:
    """Return available MCP tools exposed by the Corporate Policy Server."""
    return {"tools": _MCP_TOOLS_SPEC}


@app.post("/mcp")
@app.post("/mcp/call-tool")
def call_mcp_tool(
    request: MCPToolCallRequest,
    x_agent_gateway_verified: str | None = Header(default=None),
    x_verified_spiffe_id: str | None = Header(default=None),
) -> Dict[str, Any]:
    """Execute an MCP JSON-RPC request after Agent Gateway has verified the caller."""
    if x_agent_gateway_verified != "true":
        raise HTTPException(
            status_code=403,
            detail="Direct access denied. Requests must traverse Agent Gateway over Private Service Connect.",
        )

    if request.method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "corporate-mcp-server", "version": "0.2.0"},
            },
        }

    if request.method == "notifications/initialized":
        return {"jsonrpc": "2.0", "id": request.id, "result": {}}

    if request.method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": {"tools": _MCP_TOOLS_SPEC},
        }

    tool_name = request.params.get("name")
    args = request.params.get("arguments", {})

    if tool_name == "verify_travel_compliance":
        corp_db = _load_corp_db()
        dept = args.get("department", "Engineering")
        cabin = args.get("cabin_class", "Business")
        fare = float(args.get("estimated_fare_usd", 0.0))
        destination = str(args.get("destination", "HND")).upper()
        country = _AIRPORT_TO_COUNTRY.get(destination, "Unknown")

        dept_record = corp_db.get(dept, next(iter(corp_db.values())))
        max_allowed = (
            dept_record["max_business_class_fare_usd"]
            if cabin in ("Business", "First")
            else dept_record["max_economy_fare_usd"]
        )
        embargoed_countries: List[str] = dept_record.get(
            "embargoed_countries", ["Iran", "North Korea", "Syria", "Cuba", "Russia"]
        )
        embargoed_airports: List[str] = dept_record.get(
            "embargoed_airports", ["IKA", "FNJ", "DAM", "HAV", "SVO"]
        )

        violations: List[str] = []
        embargo_blocked = False

        if destination in embargoed_airports or country in embargoed_countries:
            embargo_blocked = True
            violations.append(
                f"OFAC & Corporate Embargo Violation: Travel to {country} ({destination}) is strictly prohibited under export & sanctions compliance."
            )

        if cabin not in dept_record["allowed_cabins_international"]:
            violations.append(
                f"Cabin Policy Violation: '{cabin}' class is not permitted (Allowed: {', '.join(dept_record['allowed_cabins_international'])})."
            )

        if fare > max_allowed:
            violations.append(
                f"Fare Cap Exceeded: Estimated fare ${fare:,.2f} exceeds maximum allowed cap of ${max_allowed:,.2f}."
            )

        if fare > dept_record["remaining_q4_budget_usd"]:
            violations.append(
                f"Q4 Budget Exceeded: Fare ${fare:,.2f} exceeds remaining department budget of ${dept_record['remaining_q4_budget_usd']:,.2f}."
            )

        approved = len(violations) == 0
        if embargo_blocked:
            decision = "PROHIBITED_EMBARGO"
        elif not approved:
            decision = "REQUIRES_VP_APPROVAL"
        else:
            decision = "APPROVED"

        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": {
                "approved": approved,
                "decision": decision,
                "violations": violations,
                "policy_id": dept_record["policy_id"],
                "department": dept,
                "destination": destination,
                "country": country,
                "cabin_class": cabin,
                "estimated_fare_usd": fare,
                "max_allowed_fare_usd": max_allowed,
                "remaining_q4_budget_usd": dept_record["remaining_q4_budget_usd"],
                "verified_caller_spiffe_id": x_verified_spiffe_id,
                "transport": "Private Service Connect (PSC)",
            },
        }

    raise HTTPException(status_code=403, detail=f"Unauthorized or unknown MCP tool: {tool_name}")

