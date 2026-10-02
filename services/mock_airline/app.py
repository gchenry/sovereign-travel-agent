"""Authorized External Mock Airline API (`mock-airline-api`).

Provides flight schedules and fare quotes for outbound queries routed through
Google Cloud Agent Gateway (`agw-travel-secure`).
"""

from typing import Any, Dict, List
from fastapi import FastAPI, Query

app = FastAPI(title="Mock Airline API (Pacific Star Airlines)", version="0.2.0")

_FLIGHT_CATALOG: Dict[str, List[Dict[str, Any]]] = {
    "HND": [
        {
            "flight_number": "PS-108",
            "airline": "Pacific Star Airlines",
            "origin": "SFO",
            "destination": "HND",
            "departure": "2026-10-13T11:30:00Z",
            "arrival": "2026-10-14T14:45:00Z",
            "cabin": "Business",
            "price_usd": 4250.0,
            "nonstop": True,
        },
        {
            "flight_number": "PS-112",
            "airline": "Pacific Star Airlines",
            "origin": "SFO",
            "destination": "HND",
            "departure": "2026-10-13T16:15:00Z",
            "arrival": "2026-10-14T19:30:00Z",
            "cabin": "Economy",
            "price_usd": 1290.0,
            "nonstop": True,
        },
    ],
    "LHR": [
        {
            "flight_number": "PS-402",
            "airline": "Pacific Star Airlines",
            "origin": "SFO",
            "destination": "LHR",
            "departure": "2026-10-13T19:00:00Z",
            "arrival": "2026-10-14T13:20:00Z",
            "cabin": "Business",
            "price_usd": 4680.0,
            "nonstop": True,
        }
    ],
}


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "healthy", "service": "mock-airline-api"}


@app.get("/flights/search")
def search_flights(
    origin: str = Query(default="SFO"),
    destination: str = Query(default="HND"),
    cabin: str = Query(default="Business"),
) -> Dict[str, Any]:
    """Return available flights matching origin, destination, and preferred cabin."""
    dest_flights = _FLIGHT_CATALOG.get(destination.upper(), _FLIGHT_CATALOG["HND"])
    matching = [f for f in dest_flights if f["cabin"].lower() == cabin.lower()] or dest_flights
    return {
        "origin": origin,
        "destination": destination,
        "requested_cabin": cabin,
        "flights": matching,
    }
