"""Stateless runtime configuration loaded from environment variables (.env).

Notice that zero custom mTLS or JWT validation libraries are imported here.
Network egress and SPIFFE workload identity verification are enforced at the
platform perimeter by Google Cloud Agent Gateway (agw-travel-secure).
"""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Dict
from urllib.parse import urlparse
import httpx

try:
    from dotenv import load_dotenv

    _ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=False)
except ImportError:
    pass


@dataclass(frozen=True)
class AgentConfig:
    """Environment-driven configuration for stateless container execution."""

    agent_role: str
    project_id: str
    location: str
    memorybank_id: str
    session_store_uri: str
    agent_gateway_url: str
    agent_gateway_resource: str
    workload_spiffe_id: str
    travel_planner_url: str
    corporate_policy_agent_url: str
    mcp_server_url: str
    airline_api_url: str


def get_config() -> AgentConfig:
    """Return current runtime configuration from environment variables."""
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "YOUR_PROJECT_ID")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    return AgentConfig(
        agent_role=os.getenv("AGENT_ROLE", "travel-router"),
        project_id=project_id,
        location=location,
        memorybank_id=os.getenv(
            "MEMORYBANK_ID",
            f"projects/{project_id}/locations/{location}/memoryBanks/mb-exec-travel-profiles",
        ),
        session_store_uri=os.getenv(
            "SESSION_STORE_URI",
            f"firestore://projects/{project_id}/databases/agent-session-store/collections/sessions",
        ),
        agent_gateway_url=os.getenv("AGENT_GATEWAY_URL", "http://localhost:8095"),
        agent_gateway_resource=os.getenv(
            "AGENT_GATEWAY_RESOURCE",
            f"projects/{project_id}/locations/{location}/agentGateways/agw-travel-secure",
        ),
        workload_spiffe_id=os.getenv(
            "WORKLOAD_SPIFFE_ID",
            f"spiffe://{project_id}.svc.id.goog/ns/agent-engine/sa/travel-router-sa",
        ),
        travel_planner_url=os.getenv("TRAVEL_PLANNER_URL", "http://localhost:8086"),
        corporate_policy_agent_url=os.getenv("CORPORATE_POLICY_AGENT_URL", "http://localhost:8087"),
        mcp_server_url=os.getenv("MCP_SERVER_URL", "http://corporate-mcp-server:8090"),
        airline_api_url=os.getenv("AIRLINE_API_URL", "http://mock-airline-api:8091"),
    )


def get_cloud_run_headers(target_url: str, extra_headers: Dict[str, str] | None = None) -> Dict[str, str]:
    """Attach GCP Metadata Server identity token when calling IAM-protected Cloud Run URLs."""
    headers = dict(extra_headers or {})
    parsed = urlparse(target_url)
    if parsed.scheme == "https" and parsed.netloc.endswith(".run.app"):
        audience = f"{parsed.scheme}://{parsed.netloc}"
        metadata_url = (
            "http://metadata.google.internal/computeMetadata/v1/instance/"
            f"service-accounts/default/identity?audience={audience}"
        )
        try:
            with httpx.Client(timeout=2.0) as client:
                resp = client.get(metadata_url, headers={"Metadata-Flavor": "Google"})
                if resp.status_code == 200 and resp.text:
                    headers["Authorization"] = f"Bearer {resp.text.strip()}"
        except httpx.HTTPError:
            pass
    return headers
