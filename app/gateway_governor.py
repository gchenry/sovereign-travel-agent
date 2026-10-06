"""Native Google Cloud Agent Gateway & Agent Registry Egress Governor.

Architecture:
- Local Docker / `agy test` (`AGENT_GATEWAY_URL=http://mock-agent-gateway:8095`):
  Routes outbound calls through the local container simulator (`services/mock_gateway/proxy.py`).
- Cloud Production (`AGENT_GATEWAY_URL=native` inside Gemini Enterprise Agent Engine with `agw-travel-secure`):
  All outbound HTTP/MCP requests are sent directly over the network and intercepted at the
  platform perimeter by Google Cloud's native Agent Gateway (`projects/{PROJECT_ID}/locations/{REGION}/agentGateways/agw-travel-secure`),
  `AuthzPolicy` (`travel-agw-authz-policy`), `AuthzExtension` (`travel-agw-authz-ext` -> `iap.googleapis.com`),
  and `AgentRegistry` (`corporate-mcp-service` & `mock-airline-service`).
"""

from typing import Any, Dict
import socket
from urllib.parse import urlparse
import httpx

from app.config import get_cloud_run_headers, get_config

_CACHED_GOVERNANCE_STATE: Dict[str, Any] | None = None
_ORIG_GETADDRINFO = socket.getaddrinfo


def _agw_aware_getaddrinfo(
    host: Any, port: Any, family: int = 0, type: int = 0, proto: int = 0, flags: int = 0
) -> Any:
    """Ensure NXDOMAIN prompt-injection domains still reach the transparent SWG/AgentGateway VIP."""
    try:
        return _ORIG_GETADDRINFO(host, port, family, type, proto, flags)
    except socket.gaierror:
        cfg = get_config()
        if cfg.agent_gateway_url.lower() == "native" and isinstance(host, str) and "." in host:
            swg_host = urlparse(cfg.airline_api_url).hostname or "aiplatform.googleapis.com"
            if swg_host and swg_host != host:
                return _ORIG_GETADDRINFO(swg_host, port, family, type, proto, flags)
        raise


socket.getaddrinfo = _agw_aware_getaddrinfo


def get_gcp_access_token() -> str | None:
    """Obtain an OAuth2 access token from GCP Metadata Server or google-auth ADC."""
    metadata_token_url = (
        "http://metadata.google.internal/computeMetadata/v1/instance/"
        "service-accounts/default/token"
    )
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(metadata_token_url, headers={"Metadata-Flavor": "Google"})
            if resp.status_code == 200:
                return resp.json().get("access_token")
    except Exception:
        pass
    try:
        import google.auth
        import google.auth.transport.requests

        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(google.auth.transport.requests.Request())
        return creds.token
    except Exception:
        return None


def resolve_native_agent_gateway_state() -> Dict[str, Any]:
    """Query Google Cloud Network Services AgentGateway, AuthzPolicy, and AgentRegistry."""
    global _CACHED_GOVERNANCE_STATE
    if _CACHED_GOVERNANCE_STATE is not None:
        return _CACHED_GOVERNANCE_STATE

    cfg = get_config()
    project_id = cfg.project_id
    location = cfg.location
    gateway_resource = cfg.agent_gateway_resource

    mcp_host = urlparse(cfg.mcp_server_url).netloc
    airline_host = urlparse(cfg.airline_api_url).netloc
    planner_host = urlparse(cfg.travel_planner_url).netloc
    policy_host = urlparse(cfg.corporate_policy_agent_url).netloc

    state: Dict[str, Any] = {
        "gateway_resource": gateway_resource,
        "governed_access_path": "AGENT_TO_ANYWHERE",
        "protocols": ["MCP"],
        "mtls_psc_endpoint": "managed-swp-mtls-psc",
        "network_attachment": f"projects/{project_id}/regions/{location}/networkAttachments/corp-agw-net-attachment",
        "authz_policy": f"projects/{project_id}/locations/{location}/authzPolicies/travel-agw-authz-policy",
        "authz_extension": f"projects/{project_id}/locations/{location}/authzExtensions/travel-agw-authz-ext",
        "registered_endpoints": {
            mcp_host: f"projects/{project_id}/locations/{location}/mcpServers/corporate-mcp-service",
            airline_host: f"projects/{project_id}/locations/{location}/endpoints/mock-airline-service",
            planner_host: f"projects/{project_id}/locations/{location}/agents/travel-planner-agent",
            policy_host: f"projects/{project_id}/locations/{location}/agents/corporate-policy-agent",
        },
        "allowed_hosts": sorted(
            {h for h in (mcp_host, airline_host, planner_host, policy_host) if h}
        ),
    }

    token = get_gcp_access_token()
    if token and project_id != "YOUR_PROJECT_ID":
        headers = {"Authorization": f"Bearer {token}"}
        try:
            with httpx.Client(timeout=4.0) as client:
                gw_resp = client.get(
                    f"https://networkservices.googleapis.com/v1/{gateway_resource}",
                    headers=headers,
                )
                if gw_resp.status_code == 200:
                    gw_data = gw_resp.json()
                    card = gw_data.get("agentGatewayCard", {})
                    state["gateway_resource"] = gw_data.get("name", gateway_resource)
                    state["governed_access_path"] = gw_data.get("googleManaged", {}).get(
                        "governedAccessPath", "AGENT_TO_ANYWHERE"
                    )
                    state["mtls_psc_endpoint"] = card.get(
                        "mtlsEndpoint", state["mtls_psc_endpoint"]
                    )
                    net_att = (
                        gw_data.get("networkConfig", {})
                        .get("egress", {})
                        .get("networkAttachment")
                    )
                    if net_att:
                        state["network_attachment"] = net_att

                pol_resp = client.get(
                    f"https://networksecurity.googleapis.com/v1/projects/{project_id}/locations/{location}/authzPolicies/travel-agw-authz-policy",
                    headers=headers,
                )
                if pol_resp.status_code == 200:
                    pol_data = pol_resp.json()
                    state["authz_policy"] = pol_data.get("name", state["authz_policy"])
                    ext_list = (
                        pol_data.get("customProvider", {})
                        .get("authzExtension", {})
                        .get("resources", [])
                    )
                    if ext_list:
                        state["authz_extension"] = ext_list[0]

                reg_resp = client.get(
                    f"https://agentregistry.googleapis.com/v1alpha/projects/{project_id}/locations/{location}/services",
                    headers=headers,
                )
                if reg_resp.status_code == 200:
                    hosts = set(state["allowed_hosts"])
                    for svc in reg_resp.json().get("services", []):
                        svc_name = svc.get("name", "")
                        if any(
                            k in svc_name
                            for k in (
                                "corporate-mcp-service",
                                "mock-airline-service",
                                "travel-planner-agent",
                                "corporate-policy-agent",
                            )
                        ):
                            reg_endpoint = svc.get("registryResource", svc_name)
                            for iface in svc.get("interfaces", []):
                                host = urlparse(iface.get("url", "")).netloc
                                if host:
                                    state["registered_endpoints"][host] = reg_endpoint
                                    hosts.add(host)
                    state["allowed_hosts"] = sorted(hosts)

                if gw_resp.status_code == 200:
                    _CACHED_GOVERNANCE_STATE = state
        except Exception:
            pass

    return state


def _parse_upstream_response(resp: httpx.Response, target_url: str, gateway_resource: str) -> Dict[str, Any]:
    """Safely parse JSON or plain-text responses (e.g. Envoy/SWP 403 RBAC rejections)."""
    if not resp.content:
        return {}
    try:
        parsed = resp.json()
        if isinstance(parsed, dict):
            return parsed
        return {"raw_response": parsed}
    except ValueError:
        return {
            "error": (
                "AgentGatewayAccessDenied"
                if resp.status_code == 403
                else "UpstreamNonJsonResponse"
            ),
            "http_status": resp.status_code,
            "gateway_response": resp.text.strip(),
            "gateway_resource": gateway_resource,
            "target_url": target_url,
        }


def execute_governed_egress(
    target_url: str,
    method: str = "GET",
    params: Dict[str, Any] | None = None,
    json_body: Dict[str, Any] | None = None,
    override_spiffe_id: str | None = None,
) -> tuple[int, Dict[str, Any]]:
    """Route outbound call via Local Mock Gateway (Docker) or Native GCP Agent Gateway (ReasoningEngine)."""
    cfg = get_config()
    spiffe_id = override_spiffe_id or cfg.workload_spiffe_id

    # Mode 1: Local Docker Compose / `agy test` -> use `services/mock_gateway/proxy.py`
    if cfg.agent_gateway_url and cfg.agent_gateway_url.lower() != "native":
        gw_endpoint = f"{cfg.agent_gateway_url.rstrip('/')}/egress/forward"
        payload = {
            "target_url": target_url,
            "method": method,
            "params": params,
            "json_body": json_body,
        }
        headers = get_cloud_run_headers(gw_endpoint, {"X-Workload-SPIFFE-ID": spiffe_id})
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(gw_endpoint, json=payload, headers=headers)
        return resp.status_code, _parse_upstream_response(resp, target_url, cfg.agent_gateway_resource)

    # Mode 2: Native Google Cloud Agent Gateway (`agw-travel-secure`)
    # Send the real HTTP/MCP request directly over the network so `agw-travel-secure`
    # intercepts, enforces IAP + Agent Registry policies, and writes native Gateway logs.
    forward_headers = get_cloud_run_headers(
        target_url,
        {
            "X-Agent-Gateway-Verified": "true",
            "X-Verified-SPIFFE-ID": spiffe_id,
        },
    )
    try:
        with httpx.Client(timeout=15.0) as client:
            if method.upper() == "POST":
                upstream_resp = client.post(target_url, json=json_body, headers=forward_headers)
            else:
                upstream_resp = client.get(target_url, params=params, headers=forward_headers)
        return upstream_resp.status_code, _parse_upstream_response(
            upstream_resp, target_url, cfg.agent_gateway_resource
        )
    except httpx.HTTPError as exc:
        return 403, {
            "error": "AgentGatewayEgressPolicyViolation",
            "http_status": 403,
            "gateway_resource": cfg.agent_gateway_resource,
            "target_url": target_url,
            "gateway_response": str(exc),
        }


def fetch_gateway_audit_logs() -> Dict[str, Any]:
    """Fetch real `networkservices.googleapis.com/Gateway` logs emitted by `agw-travel-secure`."""
    cfg = get_config()
    if cfg.agent_gateway_url and cfg.agent_gateway_url.lower() != "native":
        target = f"{cfg.agent_gateway_url.rstrip('/')}/egress/logs"
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(target, headers=get_cloud_run_headers(target))
                if resp.status_code == 200:
                    return resp.json()
        except httpx.HTTPError:
            pass
        return {"gateway": cfg.agent_gateway_resource, "events": []}

    gov_state = resolve_native_agent_gateway_state()
    token = get_gcp_access_token()
    if token and cfg.project_id != "YOUR_PROJECT_ID":
        app_filter = (
            'resource.type="networkservices.googleapis.com/Gateway" '
            'AND resource.labels.gateway_name="agw-travel-secure" '
            'AND httpRequest.requestMethod!="CONNECT" '
            'AND NOT httpRequest.requestUrl:"googleapis.com"'
        )
        all_filter = (
            'resource.type="networkservices.googleapis.com/Gateway" '
            'AND resource.labels.gateway_name="agw-travel-secure" '
            'AND httpRequest.requestMethod!="CONNECT"'
        )
        try:
            with httpx.Client(timeout=6.0) as client:
                for log_filter in (app_filter, all_filter):
                    resp = client.post(
                        "https://logging.googleapis.com/v2/entries:list",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "resourceNames": [f"projects/{cfg.project_id}"],
                            "filter": log_filter,
                            "orderBy": "timestamp desc",
                            "pageSize": 15,
                        },
                    )
                    if resp.status_code == 200:
                        entries = resp.json().get("entries", [])
                        if entries:
                            formatted = []
                            for item in reversed(entries):
                                formatted.append(
                                    {
                                        "timestamp": item.get("timestamp"),
                                        "logName": item.get("logName"),
                                        "severity": item.get("severity"),
                                        "resource": item.get("resource"),
                                        "httpRequest": item.get("httpRequest", {}),
                                        "jsonPayload": item.get("jsonPayload", {}),
                                    }
                                )
                            return {
                                "gateway": gov_state["gateway_resource"],
                                "network_services_control_plane": gov_state,
                                "events": formatted,
                            }
        except Exception:
            pass

    return {
        "gateway": gov_state["gateway_resource"],
        "network_services_control_plane": gov_state,
        "events": [],
    }

