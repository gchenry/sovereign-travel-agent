"""FastAPI Entrypoint for the Sovereign Travel Agent Fleet (/app/main.py).

Exposes standard `/health` and `/invoke` endpoints for both local Docker
containers and Google Cloud Run / Vertex AI Reasoning Engine deployments.
"""

from typing import Any, Dict
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import httpx
from pydantic import BaseModel, Field

from app.config import get_cloud_run_headers, get_config
from app.agent import TravelRouterAgent
from app.agents.travel_planner import TravelPlannerAgent
from app.agents.corporate_policy import CorporatePolicyAgent
from app.ui import CHAT_UI_HTML

app = FastAPI(
    title="Sovereign Travel Agent Fleet (ADK + Agent Gateway)",
    version="0.2.0",
    description=(
        "Stateless multi-agent container entrypoint. Zero custom auth boilerplate in Python; "
        "outbound SPIFFE JWT-SVID validation and egress rules are enforced by Agent Gateway."
    ),
)

router_agent = TravelRouterAgent()
planner_agent = TravelPlannerAgent()
policy_agent = CorporatePolicyAgent()


class InvocationRequest(BaseModel):
    """Standard agent invocation request payload."""

    prompt: str = Field(..., description="User prompt or instruction for the Travel Router Agent.")
    user_id: str = Field(default="exec-user-001", description="User identifier for MEMORYBANK_ID lookup.")
    session_id: str = Field(default="sess-demo-001", description="Session identifier for SESSION_STORE_URI.")
    override_spiffe_id: str | None = Field(
        default=None,
        description="Optional override to simulate an unauthorized/rogue agent SPIFFE identity in demos.",
    )


class PlannerA2ARequest(BaseModel):
    """A2A request payload for the Travel Planner sub-agent container."""

    user_id: str = "exec-user-001"
    destination: str = "HND"
    requested_cabin: str | None = None


class PolicyA2ARequest(BaseModel):
    """A2A request payload for the Corporate Policy sub-agent container."""

    user_id: str = "exec-user-001"
    department: str = "Engineering"
    cabin_class: str = "Business"
    estimated_fare_usd: float = 4250.0
    destination: str = "HND"
    override_spiffe_id: str | None = None


@app.get("/", response_class=HTMLResponse)
def demo_chat_ui() -> str:
    """Interactive Web Chat & Agent Gateway Governance Console."""
    return CHAT_UI_HTML


@app.get("/gateway-logs")
def gateway_logs() -> Dict[str, Any]:
    """Fetch recent Agent Gateway egress & SPIFFE audit events for the live UI."""
    cfg = get_config()
    target = f"{cfg.agent_gateway_url.rstrip('/')}/egress/logs"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(target, headers=get_cloud_run_headers(target))
            if resp.status_code == 200:
                return resp.json()
    except httpx.HTTPError:
        pass
    return {"events": []}


@app.get("/health")
def health_check() -> Dict[str, Any]:
    """Standard health endpoint verifying stateless config & decoupled state bindings."""
    cfg = get_config()
    return {
        "status": "healthy",
        "agent_role": cfg.agent_role,
        "stateless_container": True,
        "memorybank_id": cfg.memorybank_id,
        "session_store_uri": cfg.session_store_uri,
        "agent_gateway_resource": cfg.agent_gateway_resource,
        "workload_spiffe_id": cfg.workload_spiffe_id,
    }


@app.post("/invoke")
def invoke_agent(request: InvocationRequest) -> Dict[str, Any]:
    """Primary invocation endpoint for the Travel Router Agent."""
    return router_agent.execute(
        prompt=request.prompt,
        user_id=request.user_id,
        session_id=request.session_id,
        override_spiffe_id=request.override_spiffe_id,
    )


@app.post("/a2a/plan")
def invoke_travel_planner(request: PlannerA2ARequest) -> Dict[str, Any]:
    """A2A endpoint when container is deployed as the `travel-planner` service."""
    return planner_agent.run(
        user_id=request.user_id,
        destination=request.destination,
        requested_cabin=request.requested_cabin,
    )


@app.post("/a2a/policy-check")
def invoke_corporate_policy(request: PolicyA2ARequest) -> Dict[str, Any]:
    """A2A endpoint when container is deployed as the `corporate-policy-agent` service."""
    return policy_agent.run(
        user_id=request.user_id,
        department=request.department,
        cabin_class=request.cabin_class,
        estimated_fare_usd=request.estimated_fare_usd,
        destination=request.destination,
        override_spiffe_id=request.override_spiffe_id,
    )
