from typing import Dict, List, Any, Optional

# Simple in-memory storage for testing: maps user_id -> {name: str, genres: List[str]}
_GENRES_STORE: Dict[str, Dict[str, Any]] = {}


def save_user_genres(user_id: str, genres: List[str], name: Optional[str] = None) -> None:
    entry = _GENRES_STORE.get(user_id, {})
    entry["genres"] = genres
    if name is not None:
        entry["name"] = name
    _GENRES_STORE[user_id] = entry


def get_user_genres(user_id: str):
    entry = _GENRES_STORE.get(user_id)
    if not entry:
        return []
    return entry.get("genres", [])


def clear_store():
    _GENRES_STORE.clear()


def get_all_genres():
    """Return the entire in-memory store (user_id -> {name, genres}).
    WARNING: for testing only — this exposes all stored data without auth.
    """
    return dict(_GENRES_STORE)
