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
            "country": "Japan",
            "departure": "2026-10-13T11:30:00Z",
            "arrival": "2026-10-14T14:45:00Z",
            "cabin": "Business",
            "price_usd": 4250.0,
            "nonstop": True,
        },
        {
            "flight_number": "PS-102",
            "airline": "Pacific Star Airlines",
            "origin": "SFO",
            "destination": "HND",
            "country": "Japan",
            "departure": "2026-10-13T09:00:00Z",
            "arrival": "2026-10-14T12:15:00Z",
            "cabin": "First",
            "price_usd": 9850.0,
            "nonstop": True,
        },
        {
            "flight_number": "PS-112",
            "airline": "Pacific Star Airlines",
            "origin": "SFO",
            "destination": "HND",
            "country": "Japan",
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
            "country": "United Kingdom",
            "departure": "2026-10-13T19:00:00Z",
            "arrival": "2026-10-14T13:20:00Z",
            "cabin": "Business",
            "price_usd": 4680.0,
            "nonstop": True,
        },
        {
            "flight_number": "PS-400",
            "airline": "Pacific Star Airlines",
            "origin": "SFO",
            "destination": "LHR",
            "country": "United Kingdom",
            "departure": "2026-10-13T17:00:00Z",
            "arrival": "2026-10-14T11:20:00Z",
            "cabin": "First",
            "price_usd": 10200.0,
            "nonstop": True,
        },
    ],
    "JFK": [
        {
            "flight_number": "PS-210",
            "airline": "Pacific Star Airlines",
            "origin": "SFO",
            "destination": "JFK",
            "country": "United States",
            "departure": "2026-10-13T08:00:00Z",
            "arrival": "2026-10-13T16:30:00Z",
            "cabin": "Business",
            "price_usd": 2150.0,
            "nonstop": True,
        },
    ],
    "ZRH": [
        {
            "flight_number": "PS-704",
            "airline": "Pacific Star Airlines",
            "origin": "SFO",
            "destination": "ZRH",
            "country": "Switzerland",
            "departure": "2026-10-13T18:10:00Z",
            "arrival": "2026-10-14T14:05:00Z",
            "cabin": "Business",
            "price_usd": 6850.0,
            "nonstop": True,
        },
    ],
    "SYD": [
        {
            "flight_number": "PS-818",
            "airline": "Pacific Star Airlines",
            "origin": "SFO",
            "destination": "SYD",
            "country": "Australia",
            "departure": "2026-10-13T22:30:00Z",
            "arrival": "2026-10-15T06:45:00Z",
            "cabin": "Business",
            "price_usd": 7200.0,
            "nonstop": True,
        },
    ],
    "IKA": [
        {
            "flight_number": "PS-950",
            "airline": "Pacific Star Partner Airways",
            "origin": "SFO",
            "destination": "IKA",
            "country": "Iran",
            "departure": "2026-10-13T15:00:00Z",
            "arrival": "2026-10-14T18:30:00Z",
            "cabin": "Business",
            "price_usd": 3900.0,
            "nonstop": False,
        },
    ],
    "FNJ": [
        {
            "flight_number": "PS-960",
            "airline": "Pacific Star Partner Airways",
            "origin": "SFO",
            "destination": "FNJ",
            "country": "North Korea",
            "departure": "2026-10-13T13:00:00Z",
            "arrival": "2026-10-14T17:45:00Z",
            "cabin": "Business",
            "price_usd": 4100.0,
            "nonstop": False,
        },
    ],
    "HAV": [
        {
            "flight_number": "PS-970",
            "airline": "Pacific Star Partner Airways",
            "origin": "SFO",
            "destination": "HAV",
            "country": "Cuba",
            "departure": "2026-10-13T10:00:00Z",
            "arrival": "2026-10-13T19:20:00Z",
            "cabin": "Business",
            "price_usd": 1450.0,
            "nonstop": False,
        },
    ],
    "DAM": [
        {
            "flight_number": "PS-980",
            "airline": "Pacific Star Partner Airways",
            "origin": "SFO",
            "destination": "DAM",
            "country": "Syria",
            "departure": "2026-10-13T14:20:00Z",
            "arrival": "2026-10-14T16:50:00Z",
            "cabin": "Business",
            "price_usd": 3800.0,
            "nonstop": False,
        },
    ],
    "SVO": [
        {
            "flight_number": "PS-990",
            "airline": "Pacific Star Partner Airways",
            "origin": "SFO",
            "destination": "SVO",
            "country": "Russia",
            "departure": "2026-10-13T16:40:00Z",
            "arrival": "2026-10-14T15:10:00Z",
            "cabin": "Business",
            "price_usd": 4300.0,
            "nonstop": False,
        },
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
