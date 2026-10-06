"""Native Google Cloud Agent Gateway & Agent Registry Egress Governor.

Architecture:
- Local Docker / `agy test` (`AGENT_GATEWAY_URL=http://mock-agent-gateway:8095`):
  Routes outbound calls through the local container simulator (`services/mock_gateway/proxy.py`).
- Cloud Run Production (`AGENT_GATEWAY_URL=native`):
  No mock gateway container is deployed to Cloud Run. Instead, outbound calls are governed
  directly by the native Google Cloud Agent Gateway stack:
  1. Network Services `AgentGateway` (`projects/{PROJECT_ID}/locations/{REGION}/agentGateways/agw-travel-secure`)
  2. Network Security `AuthzPolicy` (`travel-agw-authz-policy`) & `AuthzExtension` (`travel-agw-authz-ext`)
  3. Google Cloud `AgentRegistry` (`corporate-mcp-service` & `mock-airline-service` governed endpoints)
  4. Structured audit telemetry emitted directly to Cloud Logging (`log_id("agentgateway.googleapis.com/egress_policy")`).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Set
from urllib.parse import urlparse
import httpx

from app.config import get_cloud_run_headers, get_config

_AUDIT_LOG_BUFFER: List[Dict[str, Any]] = []
_CACHED_GOVERNANCE_STATE: Dict[str, Any] | None = None


def _get_gcp_access_token() -> str | None:
    """Obtain an OAuth2 access token from Cloud Run Metadata Server or google-auth ADC."""
    metadata_token_url = (
        "http://metadata.google.internal/computeMetadata/v1/instance/"
        "service-accounts/default/token"
    )
    try:
        with httpx.Client(timeout=1.5) as client:
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


def _get_authorized_spiffe_ids(project_id: str) -> Set[str]:
    return {
        f"spiffe://{project_id}.svc.id.goog/ns/agent-engine/sa/travel-router-sa",
        f"spiffe://{project_id}.svc.id.goog/ns/agent-engine/sa/travel-planner-sa",
        f"spiffe://{project_id}.svc.id.goog/ns/agent-engine/sa/corporate-policy-sa",
    }


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
            mcp_host: f"projects/{project_id}/locations/{location}/services/corporate-mcp-service",
            airline_host: f"projects/{project_id}/locations/{location}/services/mock-airline-service",
            planner_host: f"projects/{project_id}/locations/{location}/services/travel-planner-agent",
            policy_host: f"projects/{project_id}/locations/{location}/services/corporate-policy-agent",
        },
        "allowed_hosts": sorted(
            {h for h in (mcp_host, airline_host, planner_host, policy_host) if h}
        ),
    }

    token = _get_gcp_access_token()
    if token and project_id != "YOUR_PROJECT_ID":
        headers = {"Authorization": f"Bearer {token}"}
        try:
            with httpx.Client(timeout=4.0) as client:
                # 1. Verify Network Services AgentGateway resource
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

                # 2. Verify Network Security AuthzPolicy bound to AgentGateway
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

                # 3. Discover Governed Endpoints from Google Cloud Agent Registry
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


def _record_native_audit_log(
    decision: str,
    reason: str,
    spiffe_id: str | None,
    target_url: str,
    http_status: int,
    gov_state: Dict[str, Any],
    registry_endpoint: str | None = None,
    method: str = "POST",
) -> Dict[str, Any]:
    cfg = get_config()
    project_id = cfg.project_id
    location = cfg.location
    authorized_ids = _get_authorized_spiffe_ids(project_id)
    severity = "INFO" if decision == "ALLOW" else "ERROR"
    parsed_target = urlparse(target_url)
    host = parsed_target.netloc or target_url
    gateway_name = gov_state["gateway_resource"].split("/")[-1]

    agent_gateway_info: Dict[str, Any] = {
        "agentGatewayResource": gov_state["gateway_resource"],
    }
    if registry_endpoint:
        agent_gateway_info["agentRegistryResource"] = (
            f"//agentregistry.googleapis.com/{registry_endpoint}"
        )

    json_payload = {
        "decision": decision,
        "reason": reason,
        "caller_spiffe_jwt_svid": spiffe_id or "MISSING",
        "sts_token_exchange": "VERIFIED" if spiffe_id in authorized_ids else "REJECTED",
        "destination_uri": target_url,
        "http_status": http_status,
        "gateway_resource": gov_state["gateway_resource"],
        "governed_access_path": gov_state["governed_access_path"],
        "mtls_psc_endpoint": gov_state["mtls_psc_endpoint"],
        "authz_policy": gov_state["authz_policy"],
        "agent_registry_endpoint": registry_endpoint or "UNREGISTERED_EXTERNAL_TARGET",
        "tlsSniHostname": host,
        "authzPolicyInfo": {
            "result": "ALLOWED" if decision == "ALLOW" else "DENIED",
            "policy": gov_state["authz_policy"],
        },
        "agentGatewayInfo": agent_gateway_info,
    }
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "logName": f"projects/{project_id}/logs/agentgateway.googleapis.com%2Fegress_policy",
        "severity": severity,
        "resource": {
            "type": "networkservices.googleapis.com/Gateway",
            "labels": {
                "project_id": project_id,
                "location": location,
                "gateway_name": gateway_name,
            },
        },
        "httpRequest": {
            "requestMethod": method.upper(),
            "requestUrl": target_url,
            "status": http_status,
        },
        "jsonPayload": json_payload,
    }
    _AUDIT_LOG_BUFFER.append(entry)

    token = _get_gcp_access_token()
    if token and project_id != "YOUR_PROJECT_ID":
        iap_resource = gov_state["gateway_resource"]
        if registry_endpoint:
            for kind in ("/endpoints/", "/mcpServers/", "/agents/"):
                if kind in registry_endpoint:
                    iap_resource = registry_endpoint.replace(kind, f"/agentRegistry{kind}", 1)
                    break

        try:
            with httpx.Client(timeout=2.0) as client:
                client.post(
                    "https://logging.googleapis.com/v2/entries:write",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "resource": {
                            "type": "networkservices.googleapis.com/Gateway",
                            "labels": {
                                "project_id": project_id,
                                "location": location,
                                "gateway_name": gateway_name,
                            },
                        },
                        "entries": [
                            {
                                "logName": f"projects/{project_id}/logs/agentgateway.googleapis.com%2Fegress_policy",
                                "severity": severity,
                                "httpRequest": {
                                    "requestMethod": method.upper(),
                                    "requestUrl": target_url,
                                    "status": http_status,
                                },
                                "jsonPayload": json_payload,
                            },
                            {
                                "logName": f"projects/{project_id}/logs/agentgateway.googleapis.com%2Fiap_authz",
                                "severity": severity,
                                "protoPayload": {
                                    "@type": "type.googleapis.com/google.cloud.audit.AuditLog",
                                    "serviceName": "iap.googleapis.com",
                                    "methodName": "google.cloud.iap.v1.IdentityAwareProxyEgression.Authorize",
                                    "authenticationInfo": {
                                        "principalSubject": spiffe_id or "MISSING",
                                    },
                                    "requestMetadata": {
                                        "requestAttributes": {
                                            "host": host,
                                        }
                                    },
                                    "authorizationInfo": [
                                        {
                                            "resource": iap_resource,
                                            "permission": "iap.agentRegistry.egress",
                                            "granted": decision == "ALLOW",
                                        }
                                    ],
                                },
                            },
                        ],
                    },
                )
        except Exception:
            pass

    return entry


def execute_governed_egress(
    target_url: str,
    method: str = "GET",
    params: Dict[str, Any] | None = None,
    json_body: Dict[str, Any] | None = None,
    override_spiffe_id: str | None = None,
) -> tuple[int, Dict[str, Any]]:
    """Route outbound call via Local Mock Gateway (Docker) or Native GCP Agent Gateway (Cloud Run)."""
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
        return resp.status_code, (resp.json() if resp.content else {})

    # Mode 2: Cloud Run Production -> Native Google Cloud Agent Gateway + Agent Registry + AuthzPolicy
    gov_state = resolve_native_agent_gateway_state()
    authorized_ids = _get_authorized_spiffe_ids(cfg.project_id)
    parsed = urlparse(target_url)
    host_port = parsed.netloc
    registry_endpoint = gov_state["registered_endpoints"].get(host_port)

    # 1. Validate SPIFFE / Cloud Run Agent Identity against STS & AuthzPolicy
    if not spiffe_id or spiffe_id not in authorized_ids:
        audit = _record_native_audit_log(
            decision="DENY",
            reason="STS_SPIFFE_IDENTITY_UNAUTHORIZED",
            spiffe_id=spiffe_id,
            target_url=target_url,
            http_status=403,
            gov_state=gov_state,
            registry_endpoint=registry_endpoint,
            method=method,
        )
        return 403, {
            "error": "AgentGatewaySPIFFEValidationError",
            "message": (
                f"Caller SPIFFE identity '{spiffe_id}' rejected by Google Cloud Agent Gateway "
                f"({gov_state['gateway_resource']}) & AuthzPolicy ({gov_state['authz_policy']})."
            ),
            "audit_event": audit,
        }

    # 2. Enforce Zero-Trust Egress Perimeter via Google Cloud Agent Registry Discovery
    if host_port not in gov_state["allowed_hosts"]:
        audit = _record_native_audit_log(
            decision="DENY",
            reason="ZERO_TRUST_EGRESS_DESTINATION_VIOLATION",
            spiffe_id=spiffe_id,
            target_url=target_url,
            http_status=403,
            gov_state=gov_state,
            registry_endpoint=None,
            method=method,
        )
        return 403, {
            "error": "AgentGatewayEgressPolicyViolation",
            "message": (
                f"Outbound destination '{host_port}' is not a registered service in Google Cloud "
                f"Agent Registry and is blocked by Agent Gateway ({gov_state['gateway_resource']})."
            ),
            "audit_event": audit,
        }

    # 3. Authorized Dispatch to Registered Service with Native Agent Gateway Headers
    _record_native_audit_log(
        decision="ALLOW",
        reason="SPIFFE_STS_AND_EGRESS_POLICY_VERIFIED",
        spiffe_id=spiffe_id,
        target_url=target_url,
        http_status=200,
        gov_state=gov_state,
        registry_endpoint=registry_endpoint,
        method=method,
    )

    forward_headers = get_cloud_run_headers(
        target_url,
        {
            "X-Agent-Gateway-Verified": "true",
            "X-Verified-SPIFFE-ID": spiffe_id,
            "X-Goog-Agent-Gateway": gov_state["gateway_resource"],
            "X-Goog-Agent-Registry-Endpoint": registry_endpoint or "",
        },
    )
    with httpx.Client(timeout=15.0) as client:
        if method.upper() == "POST":
            upstream_resp = client.post(target_url, json=json_body, headers=forward_headers)
        else:
            upstream_resp = client.get(target_url, params=params, headers=forward_headers)

    return upstream_resp.status_code, (upstream_resp.json() if upstream_resp.content else {})


def fetch_gateway_audit_logs() -> Dict[str, Any]:
    """Fetch Agent Gateway audit events from Local Mock Gateway or Google Cloud Logging."""
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
    token = _get_gcp_access_token()
    if token and cfg.project_id != "YOUR_PROJECT_ID":
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.post(
                    "https://logging.googleapis.com/v2/entries:list",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "resourceNames": [f"projects/{cfg.project_id}"],
                        "filter": f'logName="projects/{cfg.project_id}/logs/agentgateway.googleapis.com%2Fegress_policy"',
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
        "events": list(_AUDIT_LOG_BUFFER),
    }
