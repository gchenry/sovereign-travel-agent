"""Root Travel Router Agent — Modular Python ADK Orchestrator.

Coordinates specialized sub-agents:
1. Travel Planner Agent (Decoupled MEMORYBANK_ID + External Airline API)
2. Corporate Policy Agent (Internal Corporate MCP Server via Agent Gateway + PSC)

All network egress and SPIFFE JWT-SVID identity verification are enforced by
Google Cloud Agent Gateway (agw-travel-secure) at the platform perimeter.
"""

import re
from typing import Any, Dict, List
import httpx

from app.config import get_cloud_run_headers, get_config
from app.state import SessionStoreClient
from app.agents.travel_planner import TravelPlannerAgent
from app.agents.corporate_policy import CorporatePolicyAgent
from app.tools.external_webhook import dispatch_external_webhook


_URL_PATTERN = re.compile(r"https?://[^\s\"'>]+")


class TravelRouterAgent:
    """Root orchestrator agent for the Travel & Expense Sovereign Fleet."""

    name: str = "travel_router_agent"

    def __init__(self) -> None:
        self.planner = TravelPlannerAgent()
        self.policy_agent = CorporatePolicyAgent()

    def _invoke_planner(
        self,
        user_id: str,
        destination: str,
        requested_cabin: str | None = None,
    ) -> Dict[str, Any]:
        """Invoke Travel Planner Agent via A2A container endpoint or in-process fallback."""
        cfg = get_config()
        if cfg.travel_planner_url and cfg.travel_planner_url != "in-process":
            target = f"{cfg.travel_planner_url.rstrip('/')}/a2a/plan"
            try:
                with httpx.Client(timeout=8.0) as client:
                    resp = client.post(
                        target,
                        json={
                            "user_id": user_id,
                            "destination": destination,
                            "requested_cabin": requested_cabin,
                        },
                        headers=get_cloud_run_headers(target),
                    )
                    if resp.status_code == 200:
                        return resp.json()
            except httpx.HTTPError:
                pass
        return self.planner.run(
            user_id=user_id,
            destination=destination,
            requested_cabin=requested_cabin,
        )

    def _invoke_policy_agent(
        self,
        user_id: str,
        department: str,
        cabin_class: str,
        estimated_fare_usd: float,
        destination: str = "HND",
        override_spiffe_id: str | None = None,
    ) -> Dict[str, Any]:
        """Invoke Corporate Policy Agent via A2A container endpoint or in-process fallback."""
        cfg = get_config()
        if cfg.corporate_policy_agent_url and cfg.corporate_policy_agent_url != "in-process":
            target = f"{cfg.corporate_policy_agent_url.rstrip('/')}/a2a/policy-check"
            try:
                with httpx.Client(timeout=8.0) as client:
                    resp = client.post(
                        target,
                        json={
                            "user_id": user_id,
                            "department": department,
                            "cabin_class": cabin_class,
                            "estimated_fare_usd": estimated_fare_usd,
                            "destination": destination,
                            "override_spiffe_id": override_spiffe_id,
                        },
                        headers=get_cloud_run_headers(target),
                    )
                    if resp.status_code == 200:
                        return resp.json()
            except httpx.HTTPError:
                pass
        return self.policy_agent.run(
            user_id=user_id,
            department=department,
            cabin_class=cabin_class,
            estimated_fare_usd=estimated_fare_usd,
            destination=destination,
            override_spiffe_id=override_spiffe_id,
        )

    @staticmethod
    def _infer_destination(prompt: str) -> str:
        lower = prompt.lower()
        if any(k in lower for k in ("iran", "tehran", "ika")):
            return "IKA"
        if any(k in lower for k in ("north korea", "pyongyang", "fnj")):
            return "FNJ"
        if any(k in lower for k in ("cuba", "havana", "hav")):
            return "HAV"
        if any(k in lower for k in ("syria", "damascus", "dam")):
            return "DAM"
        if any(k in lower for k in ("russia", "moscow", "svo")):
            return "SVO"
        if any(k in lower for k in ("zurich", "switzerland", "zrh")):
            return "ZRH"
        if any(k in lower for k in ("sydney", "australia", "syd")):
            return "SYD"
        if any(k in lower for k in ("london", "lhr")):
            return "LHR"
        if any(k in lower for k in ("new york", "jfk")):
            return "JFK"
        return "HND"  # Default demo destination: Tokyo Haneda

    @staticmethod
    def _infer_cabin(prompt: str) -> str | None:
        lower = prompt.lower()
        if "first class" in lower or "first-class" in lower:
            return "First"
        if "economy" in lower and "premium" not in lower:
            return "Economy"
        return None

    def execute(
        self,
        prompt: str,
        user_id: str = "exec-user-001",
        session_id: str = "sess-demo-001",
        override_spiffe_id: str | None = None,
    ) -> Dict[str, Any]:
        """Coordinate the multi-agent travel workflow and persist decoupled session state."""
        cfg = get_config()
        session_store = SessionStoreClient(cfg.session_store_uri)
        session_store.append_turn(session_id, role="user", content=prompt)

        trace_steps: List[Dict[str, Any]] = []
        destination = self._infer_destination(prompt)
        requested_cabin = self._infer_cabin(prompt)

        # Step 1: Delegate to Travel Planner Agent (Memory Bank + External Airline API)
        planner_output = self._invoke_planner(
            user_id=user_id,
            destination=destination,
            requested_cabin=requested_cabin,
        )
        trace_steps.append({"step": "a2a_travel_planner", "output": planner_output})

        profile = planner_output.get("traveler_profile", {})
        flights_payload = planner_output.get("flight_search", {})
        flights = flights_payload.get("flights", [])
        selected_flight = flights[0] if flights else {
            "flight_number": "PS-108",
            "origin": profile.get("home_airport", "SFO"),
            "destination": destination,
            "cabin": requested_cabin or profile.get("preferred_cabin", "Business"),
            "price_usd": 4250.0,
        }

        # Step 2: Delegate to Corporate Policy Agent (Internal MCP via Agent Gateway + PSC)
        policy_output = self._invoke_policy_agent(
            user_id=user_id,
            department=profile.get("department", "Engineering"),
            cabin_class=selected_flight.get("cabin", "Business"),
            estimated_fare_usd=float(selected_flight.get("price_usd", 4250.0)),
            destination=destination,
            override_spiffe_id=override_spiffe_id,
        )
        trace_steps.append({"step": "a2a_corporate_policy_mcp", "output": policy_output})

        mcp_result = policy_output.get("mcp_compliance_result", {})
        if mcp_result.get("status") == "BLOCKED_BY_AGENT_GATEWAY":
            summary = (
                "Security Policy Enforcement: Agent Gateway blocked access to the "
                "Corporate Policy MCP Server due to an unverified workload SPIFFE identity."
            )
            session_store.append_turn(
                session_id,
                role="assistant",
                content=summary,
                metadata={"security_event": "SPIFFE_IDENTITY_REJECTED"},
            )
            return {
                "status": "SECURITY_BLOCKED_AT_GATEWAY",
                "agent": self.name,
                "session_id": session_id,
                "session_store_uri": cfg.session_store_uri,
                "memorybank_id": cfg.memorybank_id,
                "agent_gateway": cfg.agent_gateway_resource,
                "response": summary,
                "trace": trace_steps,
            }

        # Step 3: Check if the prompt attempts an outbound webhook / exfiltration call
        # (Simulates Prompt Injection trying to leak corporate financial / profile data)
        urls_in_prompt = _URL_PATTERN.findall(prompt)
        if urls_in_prompt:
            target_exfil_url = urls_in_prompt[0]
            exfil_attempt = dispatch_external_webhook(
                target_url=target_exfil_url,
                data_payload={
                    "traveler_profile": profile,
                    "corporate_compliance": mcp_result,
                },
            )
            trace_steps.append({"step": "outbound_egress_attempt", "output": exfil_attempt})

            if exfil_attempt.get("status") == "BLOCKED_BY_AGENT_GATEWAY":
                summary = (
                    f"Flight {selected_flight.get('flight_number')} ({selected_flight.get('origin')} -> "
                    f"{selected_flight.get('destination')}) verified against corporate policy. "
                    f"HOWEVER, the requested outbound transmission to '{target_exfil_url}' was "
                    f"actively BLOCKED at the network perimeter by Google Cloud Agent Gateway "
                    f"({cfg.agent_gateway_resource}: Zero-Trust Egress Violation)."
                )
                session_store.append_turn(
                    session_id,
                    role="assistant",
                    content=summary,
                    metadata={
                        "security_event": "EGRESS_EXFILTRATION_BLOCKED",
                        "blocked_url": target_exfil_url,
                    },
                )
                return {
                    "status": "EGRESS_EXFILTRATION_BLOCKED",
                    "agent": self.name,
                    "session_id": session_id,
                    "session_store_uri": cfg.session_store_uri,
                    "memorybank_id": cfg.memorybank_id,
                    "agent_gateway": cfg.agent_gateway_resource,
                    "response": summary,
                    "trace": trace_steps,
                }

        compliance_data = mcp_result.get("result", {})
        approved = compliance_data.get("approved", True)
        decision = compliance_data.get("decision", "APPROVED" if approved else "REQUIRES_VP_APPROVAL")
        violations = compliance_data.get("violations", [])
        budget_remaining = compliance_data.get("remaining_q4_budget_usd", 18500.0)

        if not approved:
            violation_text = " | ".join(violations) if violations else "Exceeds corporate travel policy thresholds."
            summary = (
                f"Itinerary Flagged ({decision}) for {profile.get('name')}: "
                f"Flight {selected_flight.get('flight_number')} ({selected_flight.get('origin')} -> "
                f"{selected_flight.get('destination')}, {selected_flight.get('cabin')}) at "
                f"${selected_flight.get('price_usd'):,.2f}. Corporate MCP Policy Check: {decision} — "
                f"{violation_text}"
            )
            status_code = (
                "POLICY_BLOCKED_EMBARGO"
                if decision == "PROHIBITED_EMBARGO"
                else "POLICY_VIOLATION_REQUIRES_APPROVAL"
            )
        else:
            summary = (
                f"Prepared compliant itinerary for {profile.get('name')} ({profile.get('title')}): "
                f"Flight {selected_flight.get('flight_number')} ({selected_flight.get('origin')} -> "
                f"{selected_flight.get('destination')}, {selected_flight.get('cabin')}) at "
                f"${selected_flight.get('price_usd'):,.2f}. Corporate MCP Policy Check: "
                f"APPROVED (Remaining Q4 Budget: ${budget_remaining:,.2f})."
            )
            status_code = "SUCCESS"

        session_store.append_turn(session_id, role="assistant", content=summary)

        return {
            "status": status_code,
            "agent": self.name,
            "session_id": session_id,
            "session_store_uri": cfg.session_store_uri,
            "memorybank_id": cfg.memorybank_id,
            "agent_gateway": cfg.agent_gateway_resource,
            "response": summary,
            "trace": trace_steps,
        }
