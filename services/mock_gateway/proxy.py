"""Local Mock Agent Gateway (`agw-travel-secure` Egress Mode Simulator).

Used during local container development (`docker compose`) and `agy test` to
validate local-to-cloud transitions (Watch-out #1 from the presentation):
1. Validates the caller's cryptographic SPIFFE ID (JWT-SVID) via simulated
   Google Security Token Service (STS).
2. Enforces the Agent Gateway Egress Allowlist (allowing Private Service Connect
   Corporate MCP Server and authorized Mock Airline API).
3. Actively blocks unauthorized external egress paths (e.g., prompt injection
   exfiltration attempts) and emits structured platform security audit logs.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Set
from urllib.parse import urlparse
import httpx
from fastapi import FastAPI, Header, Response
from pydantic import BaseModel

try:
    from dotenv import load_dotenv

    _ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=False)
except ImportError:
    pass

app = FastAPI(
    title="Google Cloud Agent Gateway Simulator (agw-travel-secure)",
    version="0.2.0",
)


def _get_gateway_resource() -> str:
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "YOUR_PROJECT_ID")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    return os.getenv(
        "AGENT_GATEWAY_RESOURCE",
        f"projects/{project_id}/locations/{location}/agentGateways/agw-travel-secure",
    )


def _get_authorized_spiffe_ids() -> Set[str]:
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "YOUR_PROJECT_ID")
    return {
        os.getenv(
            "WORKLOAD_SPIFFE_ID",
            f"spiffe://{project_id}.svc.id.goog/ns/agent-engine/sa/travel-router-sa",
        ),
        os.getenv(
            "PLANNER_SPIFFE_ID",
            f"spiffe://{project_id}.svc.id.goog/ns/agent-engine/sa/travel-planner-sa",
        ),
        os.getenv(
            "POLICY_SPIFFE_ID",
            f"spiffe://{project_id}.svc.id.goog/ns/agent-engine/sa/corporate-policy-sa",
        ),
    }


# Authorized Egress Destinations (Internal PSC + Approved External APIs)
ALLOWED_EGRESS_HOSTS = {
    "corporate-mcp-server:8090",
    "localhost:8090",
    "127.0.0.1:8090",
    "localhost:18090",
    "127.0.0.1:18090",
    "mock-airline-api:8091",
    "localhost:8091",
    "127.0.0.1:8091",
    "localhost:18091",
    "127.0.0.1:18091",
}


def _get_allowed_egress_hosts() -> Set[str]:
    hosts = set(ALLOWED_EGRESS_HOSTS)
    extra = os.getenv("EXTRA_ALLOWED_EGRESS_HOSTS", "")
    for item in extra.replace(",", ";").split(";"):
        cleaned = item.strip()
        if cleaned:
            hosts.add(cleaned)
    return hosts


_AUDIT_LOG_BUFFER: List[Dict[str, Any]] = []


class EgressForwardRequest(BaseModel):
    """Outbound request intercepted by Agent Gateway (Egress Mode)."""

    target_url: str
    method: str = "GET"
    params: Dict[str, Any] | None = None
    json_body: Dict[str, Any] | None = None


def _record_audit_log(
    decision: str,
    reason: str,
    spiffe_id: str | None,
    target_url: str,
    http_status: int,
) -> Dict[str, Any]:
    gateway_resource = _get_gateway_resource()
    authorized_ids = _get_authorized_spiffe_ids()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "logName": f"{gateway_resource}/logs/agentgateway.googleapis.com%2Fegress_policy",
        "severity": "INFO" if decision == "ALLOW" else "ERROR",
        "resource": {
            "type": "aiplatform.googleapis.com/AgentGateway",
            "labels": {
                "gateway_name": "agw-travel-secure",
                "mode": "AGENT_TO_ANYWHERE_EGRESS",
                "location": "us-central1",
            },
        },
        "jsonPayload": {
            "decision": decision,
            "reason": reason,
            "caller_spiffe_jwt_svid": spiffe_id or "MISSING",
            "sts_token_exchange": "VERIFIED" if spiffe_id in authorized_ids else "REJECTED",
            "destination_uri": target_url,
            "http_status": http_status,
        },
    }
    _AUDIT_LOG_BUFFER.append(entry)
    print(f"[AGENT-GATEWAY-AUDIT] {decision} | {reason} | spiffe={spiffe_id} | dest={target_url}", flush=True)
    return entry


@app.get("/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "gateway_resource": _get_gateway_resource(),
        "mode": "AGENT_TO_ANYWHERE_EGRESS",
        "authorized_spiffe_identities": sorted(_get_authorized_spiffe_ids()),
        "allowed_egress_hosts": sorted(_get_allowed_egress_hosts()),
    }


@app.get("/egress/logs")
def get_audit_logs() -> Dict[str, Any]:
    """Return captured Agent Gateway security audit logs (for demo & Datadog handoff)."""
    return {"gateway": _get_gateway_resource(), "events": list(_AUDIT_LOG_BUFFER)}


@app.post("/egress/forward")
def forward_egress(
    req: EgressForwardRequest,
    response: Response,
    x_workload_spiffe_id: str | None = Header(default=None),
) -> Dict[str, Any]:
    """Validate SPIFFE JWT-SVID & Egress Policy before forwarding outbound call."""
    parsed = urlparse(req.target_url)
    host_port = parsed.netloc
    authorized_ids = _get_authorized_spiffe_ids()
    allowed_hosts = _get_allowed_egress_hosts()

    # 1. Validate Cryptographic SPIFFE Identity (JWT-SVID via Google STS)
    if not x_workload_spiffe_id or x_workload_spiffe_id not in authorized_ids:
        audit = _record_audit_log(
            decision="DENY",
            reason="STS_SPIFFE_IDENTITY_UNAUTHORIZED",
            spiffe_id=x_workload_spiffe_id,
            target_url=req.target_url,
            http_status=403,
        )
        response.status_code = 403
        return {
            "error": "AgentGatewaySPIFFEValidationError",
            "message": f"Caller SPIFFE identity '{x_workload_spiffe_id}' rejected by Google Security Token Service (STS).",
            "audit_event": audit,
        }

    # 2. Enforce Zero-Trust Egress Destination Policy
    if host_port not in allowed_hosts:
        audit = _record_audit_log(
            decision="DENY",
            reason="ZERO_TRUST_EGRESS_DESTINATION_VIOLATION",
            spiffe_id=x_workload_spiffe_id,
            target_url=req.target_url,
            http_status=403,
        )
        response.status_code = 403
        return {
            "error": "AgentGatewayEgressPolicyViolation",
            "message": (
                f"Outbound destination '{host_port}' is blocked by Agent Gateway "
                "egress perimeter policy (agw-travel-secure)."
            ),
            "audit_event": audit,
        }

    # 3. Forward validated call (injecting verified gateway headers for PSC MCP targets)
    _record_audit_log(
        decision="ALLOW",
        reason="SPIFFE_STS_AND_EGRESS_POLICY_VERIFIED",
        spiffe_id=x_workload_spiffe_id,
        target_url=req.target_url,
        http_status=200,
    )

    forward_headers = {
        "X-Agent-Gateway-Verified": "true",
        "X-Verified-SPIFFE-ID": x_workload_spiffe_id,
    }
    if parsed.scheme == "https" and parsed.netloc.endswith(".run.app"):
        audience = f"{parsed.scheme}://{parsed.netloc}"
        metadata_url = (
            "http://metadata.google.internal/computeMetadata/v1/instance/"
            f"service-accounts/default/identity?audience={audience}"
        )
        try:
            with httpx.Client(timeout=2.0) as mclient:
                mresp = mclient.get(metadata_url, headers={"Metadata-Flavor": "Google"})
                if mresp.status_code == 200 and mresp.text:
                    forward_headers["Authorization"] = f"Bearer {mresp.text.strip()}"
        except httpx.HTTPError:
            pass

    with httpx.Client(timeout=10.0) as client:
        if req.method.upper() == "POST":
            upstream_resp = client.post(req.target_url, json=req.json_body, headers=forward_headers)
        else:
            upstream_resp = client.get(req.target_url, params=req.params, headers=forward_headers)

    response.status_code = upstream_resp.status_code
    return upstream_resp.json() if upstream_resp.content else {}
