from fastapi import APIRouter, Depends, HTTPException, status
from app.core.auth import get_current_user
from app.schemas.genres import GenresPayload
from app.services.storage import save_user_genres, get_user_genres
from app.services.storage import get_all_genres
from app.services.graph import create_user_with_genres


from app.db.neo4j import get_driver
from app.schemas.book import Book
import httpx
import logging

logger = logging.getLogger(__name__)
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


@router.post("/user/search_book")
async def user_search_book(payload: Book, current_user=Depends(get_current_user)):
    """
    Registra que el usuario ha buscado un libro.
    - Crea/actualiza Book.
    - Normaliza categories (acepta lista, JSON-string o comma-separated string).
    - Crea/usa nodos Genre y relaciona (UNWIND).
    - Registra SEARCHED_FOR (MERGE único por user-libro).
    """
    user_id = current_user.get("user_id")
    driver = get_driver()
    book_id = payload.bookId
    title = payload.title
    authors = payload.authors or []
    categories = getattr(payload, "categories", None)  # puede no existir

    # --- completar desde Google Books si falta info ---
    if not title or not categories:
        try:
            async with httpx.AsyncClient() as client:
                gb_res = await client.get(
                    f"https://www.googleapis.com/books/v1/volumes/{book_id}",
                    timeout=10.0,
                )
                if gb_res.status_code == 200:
                    gb_data = gb_res.json()
                    volume_info = gb_data.get("volumeInfo", {})
                    title = title or volume_info.get("title")
                    authors = authors or volume_info.get("authors", [])
                    categories = categories or volume_info.get("categories", [])
        except Exception as e:
            logger.exception("Error consultando Google Books: %s", e)

    # --- NORMALIZAR categories ---
    try:
        if isinstance(categories, str):
            stripped = categories.strip()
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, list):
                    categories = parsed
                else:
                    categories = [c.strip() for c in stripped.split(",") if c.strip()]
            except Exception:
                categories = [c.strip() for c in stripped.split(",") if c.strip()]

        if categories is None:
            categories = []

        categories = [str(c).strip() for c in (categories or []) if c]
        seen = set()
        deduped = []
        for c in categories:
            if c not in seen:
                seen.add(c)
                deduped.append(c)
        categories = deduped

    except Exception:
        logger.exception("Error normalizando categories, forzando lista vacía")
        categories = []

    logger.info(
        "search_book payload: book_id=%s title=%r categories=%r",
        book_id,
        title,
        categories,
    )

    with driver.session() as session:
        # MERGE Book
        session.run(
            """
            MERGE (b:Book {bookId: $book_id})
            SET b.title = $title,
                b.authors = $authors,
                b.categories = $categories,
                b.publishedDate = $publishedDate,
                b.description = $description
            """,
            {
                "book_id": book_id,
                "title": title or "",
                "authors": authors,
                "categories": categories,
                "publishedDate": getattr(payload, "publishedDate", "") or "",
                "description": getattr(payload, "description", "") or "",
            },
        )

        # MERGE Genres + BELONGS_TO (sin duplicados)
        if categories:
            session.run(
                """
                MATCH (b:Book {bookId: $book_id})
                WITH b
                UNWIND $categories AS cat
                WITH b, trim(cat) AS cat_trimmed
                WHERE cat_trimmed <> ""
                MERGE (g:Genre {name: cat_trimmed})
                MERGE (b)-[:BELONGS_TO]->(g)
                """,
                {"book_id": book_id, "categories": categories},
            )

        # MERGE SEARCHED_FOR (única relación, actualiza timestamp si ya existe)
        session.run(
            """
            MATCH (u:User {userId: $user_id})
            MATCH (b:Book {bookId: $book_id})
            MERGE (u)-[r:SEARCHED_FOR]->(b)
            ON CREATE SET r.timestamp = datetime()
            ON MATCH SET r.timestamp = datetime()
            """,
            {"user_id": user_id, "book_id": book_id},
        )

    return {
        "user_id": user_id,
        "bookId": book_id,
        "title": title,
        "authors": authors,
        "categories": categories,
        "registered": True,
    }
