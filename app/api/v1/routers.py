from fastapi import APIRouter, Depends, HTTPException, status
from app.core.auth import get_current_user
from app.schemas.genres import GenresPayload
from app.services.storage import save_user_genres, get_user_genres
from app.services.storage import get_all_genres
from app.services.graph import create_user_with_genres

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.post("/items")
async def create_item(payload: dict, current_user=Depends(get_current_user)):
    # ejemplo: el user_id viene desde el token Django
    user_id = current_user.get("user_id")
    return {"saved_by": user_id, "payload": payload}


@router.post("/user/genres")
async def set_user_genres(payload: GenresPayload, current_user=Depends(get_current_user)):
    user_id = current_user.get("user_id")
    # payload.genres ya validado para tener 3 géneros únicos
    first_name = current_user.get("first_name")
    save_user_genres(user_id, payload.genres, name=first_name)
    # Also persist to Neo4j (best-effort; errors are logged but don't block the API)
    try:
        create_user_with_genres(user_id, first_name, payload.genres)
    except Exception:
        pass
    return {"user_id": user_id, "name": first_name, "saved_genres": get_user_genres(user_id)}


@router.get("/admin/genres")
async def admin_get_all_genres():
    """Public admin endpoint for development: returns the full in-memory store."""
    raw = get_all_genres()
    # Convert dict {user_id: {name, genres}} into list of objects with explicit id
    result = []
    for uid, entry in raw.items():
        result.append({
            "id": uid,
            "name": entry.get("name"),
            "genres": entry.get("genres", []),
        })
    return result
