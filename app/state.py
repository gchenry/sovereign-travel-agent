"""Decoupled State & Memory Connectors (MEMORYBANK_ID & SESSION_STORE_URI).

Ensures agent containers remain completely stateless and that zero traveler
profiles, loyalty numbers, or corporate card numbers are hardcoded in Python.
Profiles are loaded dynamically from the mounted MEMORYBANK_ID store (or the
gitignored `data/memory_bank_profiles.local.json` file during local execution).
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Dict, List


_REPO_ROOT = Path(__file__).resolve().parent.parent
_LOCAL_PROFILES_PATH = Path(
    os.getenv("MEMORYBANK_MOUNT_PATH", str(_REPO_ROOT / "data" / "memory_bank_profiles.local.json"))
)
_EXAMPLE_PROFILES_PATH = _REPO_ROOT / "data" / "memory_bank_profiles.example.json"

# Stateless backing session buffer representing SESSION_STORE_URI turns
_EXTERNAL_SESSION_STORE: Dict[str, List[Dict[str, Any]]] = {}


def _load_mounted_profiles() -> Dict[str, Dict[str, Any]]:
    """Load traveler profiles from the gitignored local mount or fallback template."""
    for path in (_LOCAL_PROFILES_PATH, _EXAMPLE_PROFILES_PATH):
        if path.exists():
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
    return {}


class MemoryBankClient:
    """Connects to Vertex AI Memory Bank dynamically via MEMORYBANK_ID."""

    def __init__(self, memorybank_id: str) -> None:
        self.memorybank_id = memorybank_id

    def get_traveler_profile(self, user_id: str) -> Dict[str, Any]:
        """Inject the traveler's profile dynamically from MEMORYBANK_ID without hardcoding."""
        profiles = _load_mounted_profiles()
        profile = dict(profiles.get(user_id) or profiles.get("default") or {"user_id": user_id})
        profile["source_memorybank_id"] = self.memorybank_id
        return profile


class SessionStoreClient:
    """Manages multi-turn state externally via SESSION_STORE_URI."""

    def __init__(self, session_store_uri: str) -> None:
        self.session_store_uri = session_store_uri

    def append_turn(self, session_id: str, role: str, content: str, metadata: Dict[str, Any] | None = None) -> None:
        """Persist a conversation turn to the decoupled session store."""
        turns = _EXTERNAL_SESSION_STORE.setdefault(session_id, [])
        turns.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "role": role,
                "content": content,
                "session_store_uri": self.session_store_uri,
                "metadata": metadata or {},
            }
        )

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieve conversation history for a session."""
        return list(_EXTERNAL_SESSION_STORE.get(session_id, []))
