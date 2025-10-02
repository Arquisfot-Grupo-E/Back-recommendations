import datetime
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.core.auth import get_current_user
from app.schemas.genres import GenresPayload
from app.schemas.rating import RatingPayload
from app.services.storage import save_user_genres, get_user_genres
from app.services.storage import get_all_genres
from app.services.graph import create_user_with_genres

from app.db.neo4j import get_driver
from app.schemas.book import Book
import httpx
import logging
from typing import List
import json

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

                # MERGE Genres + BELONGS_TO
        if categories:
            # Procesar las categorías para obtener un solo género por categoría
            final_categories = []
            seen = set()
            
            for category in categories:
                parts = [p.strip() for p in category.split("/") if p.strip()]
                if not parts:
                    continue
                    
                # Intentar con cada parte hasta encontrar una que no exista
                for part in parts:
                    if part.lower() not in seen:
                        seen.add(part.lower())
                        final_categories.append(part)
                        break  # Solo tomamos una parte de cada categoría
            
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
                {"book_id": book_id, "categories": final_categories},
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


@router.get("/user/recommendations")
async def user_recommendations(current_user=Depends(get_current_user)):
    """
    Recomienda libros según los géneros de los libros que el usuario ha buscado.
    Si no ha buscado ninguno, recomienda por géneros favoritos.
    """
    user_id = current_user.get("user_id")
    driver = get_driver()
    recommendations = []

    with driver.session() as session:
        # Libros buscados por el usuario
        searched_books = session.run(
            """
            MATCH (u:User {userId: $user_id})-[:SEARCHED_FOR]->(b:Book)
            RETURN b.bookId AS bookId
            """,
            {"user_id": user_id}
        ).value()

        if searched_books:
            # Géneros de los libros buscados
            genres = session.run(
                """
                MATCH (u:User {userId: $user_id})-[:SEARCHED_FOR]->(b:Book)-[:BELONGS_TO]->(g:Genre)
                RETURN DISTINCT g.name AS genre
                """,
                {"user_id": user_id}
            ).value()

            # Recomendar otros libros de esos géneros que NO haya buscado el usuario
            result = session.run(
                """
                MATCH (g:Genre)<-[:BELONGS_TO]-(b:Book)
                WHERE g.name IN $genres AND NOT b.bookId IN $searched_books
                RETURN b.bookId AS bookId, b.title AS title, b.authors AS authors, b.categories AS categories, b.publishedDate AS publishedDate, b.description AS description
                LIMIT 30
                """,
                {"genres": genres, "searched_books": searched_books}
            )
            recommendations = [dict(record) for record in result]
        else:
            # Si no ha buscado, recomendar por géneros favoritos
            # Usar los géneros guardados en el microservicio de géneros
            from app.services.storage import get_user_genres
            genres = get_user_genres(user_id)
            genres = genres if genres else []
            result = session.run(
                """
                MATCH (g:Genre)<-[:BELONGS_TO]-(b:Book)
                WHERE g.name IN $genres
                RETURN b.bookId AS bookId, b.title AS title, b.authors AS authors, b.categories AS categories, b.publishedDate AS publishedDate, b.description AS description
                LIMIT 30
                """,
                {"genres": genres}
            )
            recommendations = [dict(record) for record in result]

    return recommendations


@router.post("/user/rate_book")
async def rate_book(payload: RatingPayload, current_user=Depends(get_current_user)):
    """
    Permite al usuario calificar un libro con estrellas (1-5).
    """
    user_id = current_user.get("user_id")
    driver = get_driver()
    
    with driver.session() as session:
        # Verificar si el libro existe
        book_exists = session.run(
            "MATCH (b:Book {bookId: $book_id}) RETURN b",
            {"book_id": payload.bookId}
        ).single()
        
        # Si no existe, intentar crearlo desde Google Books
        if not book_exists:
            try:
                async with httpx.AsyncClient() as client:
                    gb_res = await client.get(
                        f"https://www.googleapis.com/books/v1/volumes/{payload.bookId}",
                        timeout=10.0,
                    )
                    if gb_res.status_code == 200:
                        gb_data = gb_res.json()
                        volume_info = gb_data.get("volumeInfo", {})
                        
                        title = volume_info.get("title", "Unknown Title")
                        authors = volume_info.get("authors", [])
                        categories = volume_info.get("categories", [])
                        
                        # Crear el libro
                        session.run(
                            """
                            MERGE (b:Book {bookId: $book_id})
                            SET b.title = $title,
                                b.authors = $authors,
                                b.categories = $categories
                            """,
                            {
                                "book_id": payload.bookId,
                                "title": title,
                                "authors": authors,
                                "categories": categories,
                            },
                        )
                        
                        # Crear géneros
                        if categories:
                            final_categories = []
                            seen = set()
                            for category in categories:
                                parts = [p.strip() for p in category.split("/")]
                                for part in parts:
                                    if part and part.lower() not in seen:
                                        seen.add(part.lower())
                                        final_categories.append(part)
                                        break
                            
                            session.run(
                                """
                                MATCH (b:Book {bookId: $book_id})
                                UNWIND $categories AS cat
                                MERGE (g:Genre {name: cat})
                                MERGE (b)-[:BELONGS_TO]->(g)
                                """,
                                {"book_id": payload.bookId, "categories": final_categories},
                            )
            except Exception as e:
                logger.exception(f"Error consultando Google Books: {e}")
        
        # Obtener info del libro
        book_info = session.run(
            "MATCH (b:Book {bookId: $book_id}) RETURN b.title AS title, b.authors AS authors",
            {"book_id": payload.bookId}
        ).single()
        
        # Crear rating
        session.run(
            """
            MATCH (u:User {userId: $user_id})
            MERGE (b:Book {bookId: $book_id})
            MERGE (u)-[r:RATED]->(b)
            SET r.stars = $stars, r.timestamp = datetime()
            """,
            {
                "user_id": user_id,
                "book_id": payload.bookId,
                "stars": payload.stars
            }
        )
    
    return {
        "user_id": user_id,
        "bookId": payload.bookId,
        "title": book_info["title"] if book_info else None,
        "authors": book_info["authors"] if book_info else [],
        "stars": payload.stars,
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Rating saved successfully"
    }

@router.get("/user/ratings")
async def get_user_ratings(current_user=Depends(get_current_user)):
    """Obtiene todas las calificaciones del usuario actual."""
    user_id = current_user.get("user_id")
    driver = get_driver()
    
    with driver.session() as session:
        result = session.run(
            """
            MATCH (u:User {userId: $user_id})-[r:RATED]->(b:Book)
            RETURN b.bookId AS bookId, b.title AS title, b.authors AS authors,
                   r.stars AS stars, r.timestamp AS timestamp
            ORDER BY r.timestamp DESC
            """,
            {"user_id": user_id}
        )
        
        ratings = [
            {
                "bookId": record["bookId"],
                "title": record["title"],
                "authors": record["authors"],
                "stars": record["stars"],
                "timestamp": record["timestamp"]
            }
            for record in result
        ]
    
    return {
        "user_id": user_id,
        "ratings": ratings,
        "total_ratings": len(ratings)
    }


@router.get("/user/recommendations/collaborative")
async def get_collaborative_recommendations(current_user=Depends(get_current_user)):
    """
    Nivel 3: Recomendaciones por usuarios similares (filtrado colaborativo).
    Si Laura y Pedro califican ≥4⭐ a "Harry Potter", y Laura lee "El Hobbit" con ≥4⭐,
    entonces "El Hobbit" se recomienda a Pedro.
    """
    user_id = current_user.get("user_id")
    driver = get_driver()
    
    with driver.session() as session:
        result = session.run(
            """
            MATCH (target:User {userId: $user_id})-[r1:RATED]->(shared:Book)<-[r2:RATED]-(similar:User)
            WHERE r1.stars >= 4 AND r2.stars >= 4 AND target <> similar
            MATCH (similar)-[r3:RATED]->(recommended:Book)
            WHERE r3.stars >= 4 
              AND NOT EXISTS((target)-[:RATED]->(recommended))
            RETURN recommended.bookId AS bookId,
                   recommended.title AS title,
                   recommended.authors AS authors,
                   similar.name AS recommended_by_user,
                   shared.title AS because_both_rated_high,
                   r3.stars AS similar_user_rating
            ORDER BY r3.stars DESC
            LIMIT 10
            """,
            {"user_id": user_id}
        )
        
        recommendations = [
            {
                "bookId": record["bookId"],
                "title": record["title"],
                "authors": record["authors"],
                "recommended_by_user": record["recommended_by_user"],
                "because_both_rated_high": record["because_both_rated_high"],
                "similar_user_rating": record["similar_user_rating"],
                "reason": f"Because you and {record['recommended_by_user']} both rated '{record['because_both_rated_high']}' highly"
            }
            for record in result
        ]
    
    return {
        "user_id": user_id,
        "level": 3,
        "type": "collaborative_filtering",
        "recommendations": recommendations,
        "total": len(recommendations)
    }
