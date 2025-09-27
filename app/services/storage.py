from typing import Dict, List

# Simple in-memory storage for testing: maps user_id -> list of genres
_GENRES_STORE: Dict[str, List[str]] = {}


def save_user_genres(user_id: str, genres: List[str]) -> None:
    # Store normalized genres
    _GENRES_STORE[user_id] = genres


def get_user_genres(user_id: str):
    return _GENRES_STORE.get(user_id, [])


def clear_store():
    _GENRES_STORE.clear()


def get_all_genres():
    """Return the entire in-memory store (user_id -> genres).
    WARNING: for testing only — this exposes all stored data without auth.
    """
    return dict(_GENRES_STORE)
