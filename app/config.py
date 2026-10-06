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
    reasoning_engine_id: str = ""


_ID_TOKEN_CACHE: Dict[str, tuple[float, str]] = {}


def get_config() -> AgentConfig:
    """Return current runtime configuration from environment variables."""
    project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT", "YOUR_PROJECT_ID")
    if project_id.isdigit() or project_id == "YOUR_PROJECT_ID":
        for env_key in ("AGENT_GATEWAY_RESOURCE", "MEMORYBANK_ID", "SESSION_STORE_URI"):
            val = os.getenv(env_key, "")
            if "projects/" in val:
                candidate = val.split("projects/", 1)[1].split("/", 1)[0]
                if candidate and not candidate.isdigit():
                    project_id = candidate
                    break
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
        reasoning_engine_id=os.getenv("REASONING_ENGINE_ID", ""),
    )


def _mint_sa_id_token_via_iam(audience: str, project_id: str) -> str | None:
    """Mint a Google OIDC ID token via IAM Credentials API when running in ReasoningEngine with AGENT_IDENTITY."""
    sa_email = os.getenv(
        "IMPERSONATE_SA_EMAIL",
        f"travel-router-sa@{project_id}.iam.gserviceaccount.com",
    )
    metadata_token_url = (
        "http://metadata.google.internal/computeMetadata/v1/instance/"
        "service-accounts/default/token"
    )
    access_token: str | None = None
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(metadata_token_url, headers={"Metadata-Flavor": "Google"})
            if resp.status_code == 200:
                access_token = resp.json().get("access_token")
    except Exception:
        pass

    if not access_token:
        return None

    iam_url = (
        f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{sa_email}:generateIdToken"
    )
    try:
        with httpx.Client(timeout=4.0) as client:
            resp = client.post(
                iam_url,
                headers={"Authorization": f"Bearer {access_token}"},
                json={"audience": audience, "includeEmail": True},
            )
            if resp.status_code == 200:
                return resp.json().get("token")
    except Exception:
        pass
    return None


def get_cloud_run_headers(target_url: str, extra_headers: Dict[str, str] | None = None) -> Dict[str, str]:
    """Attach GCP OIDC identity token when calling IAM-protected Cloud Run URLs."""
    import time

    headers = dict(extra_headers or {})
    parsed = urlparse(target_url)
    if parsed.scheme == "https" and parsed.netloc.endswith(".run.app"):
        audience = f"{parsed.scheme}://{parsed.netloc}"
        now = time.time()
        cached = _ID_TOKEN_CACHE.get(audience)
        if cached and cached[0] > now:
            headers["Authorization"] = f"Bearer {cached[1]}"
            return headers

        cfg = get_config()
        id_token: str | None = None

        if os.getenv("RUNNING_IN_REASONING_ENGINE", "").lower() == "true":
            id_token = _mint_sa_id_token_via_iam(audience, cfg.project_id)

        if not id_token:
            metadata_url = (
                "http://metadata.google.internal/computeMetadata/v1/instance/"
                f"service-accounts/default/identity?audience={audience}"
            )
            try:
                with httpx.Client(timeout=2.0) as client:
                    resp = client.get(metadata_url, headers={"Metadata-Flavor": "Google"})
                    if resp.status_code == 200 and resp.text:
                        id_token = resp.text.strip()
            except httpx.HTTPError:
                pass

        if not id_token and cfg.project_id != "YOUR_PROJECT_ID":
            id_token = _mint_sa_id_token_via_iam(audience, cfg.project_id)

        if id_token:
            _ID_TOKEN_CACHE[audience] = (now + 240.0, id_token)
            headers["Authorization"] = f"Bearer {id_token}"
    return headers

