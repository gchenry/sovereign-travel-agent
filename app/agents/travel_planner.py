"""The Travel Planner Agent (Specialized ADK Sub-Agent).

Responsibilities:
1. Pulls decoupled user travel profile from Vertex AI Memory Bank (MEMORYBANK_ID).
2. Queries external Mock Airline API via Agent Gateway (Egress Mode).
"""

from typing import Any, Dict
from app.config import get_config
from app.state import MemoryBankClient
from app.tools.airline_tools import search_flights


class TravelPlannerAgent:
    """ADK Sub-Agent responsible for personal memory context & flight itinerary lookup."""

    name: str = "travel_planner_agent"
    description: str = "Pulls traveler profile from MEMORYBANK_ID and searches flights via Airline API."

    def run(
        self,
        user_id: str,
        destination: str = "HND",
        requested_cabin: str | None = None,
    ) -> Dict[str, Any]:
        """Execute travel planning workflow."""
        cfg = get_config()
        memory_bank = MemoryBankClient(cfg.memorybank_id)
        profile = memory_bank.get_traveler_profile(user_id)

        origin = profile.get("home_airport", "SFO")
        cabin_to_search = requested_cabin or profile.get("preferred_cabin", "Business")

        flight_results = search_flights(
            origin=origin,
            destination=destination,
            cabin_class=cabin_to_search,
        )

        return {
            "agent": self.name,
            "memorybank_id": cfg.memorybank_id,
            "traveler_profile": profile,
            "flight_search": flight_results,
        }
