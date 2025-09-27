from typing import List, Optional
import logging
from app.db.neo4j import get_driver

logger = logging.getLogger(__name__)


def _get_driver():
    # get_driver() from app.db.neo4j returns the driver created there
    try:
        return get_driver()
    except Exception as e:
        logger.warning(f"Could not obtain driver from app.db.neo4j: {e}")
        return None


def create_user_with_genres(user_id: str, name: Optional[str], genres: List[str]) -> bool:
    """Create/update a User node and connect it to Genre nodes.

    Behaviour:
    - Sanitizes and deduplicates genres (strips whitespace, removes empty strings).
    - MERGEs the User node by `userId` and sets `name`.
    - MERGEs each Genre node and a `:LIKES` relationship from User -> Genre.

    Returns True on success, False on failure.
    """
    if not user_id:
        logger.warning("create_user_with_genres called without user_id")
        return False

    # sanitize genres: strip and remove empties, dedupe while preserving order
    cleaned = []
    seen = set()
    for g in (genres or []):
        if not isinstance(g, str):
            continue
        s = g.strip()
        if not s:
            continue
        if s.lower() in seen:
            continue
        seen.add(s.lower())
        cleaned.append(s)

    if not cleaned:
        logger.info(f"No valid genres provided for user {user_id}; skipping graph write")
        return True  # treat as success: nothing to write

    driver = _get_driver()
    if not driver:
        logger.error("Neo4j driver not available; skipping graph write")
        return False
    cypher = """
    MERGE (u:User {userId: $userId})
    SET u.name = $name
    WITH u
    UNWIND $genres AS gname
      MERGE (g:Genre {name: gname})
      MERGE (u)-[r:LIKES]->(g)
      ON CREATE SET r.created_at = datetime()
    RETURN u.userId AS userId
    """

    try:
        with driver.session() as session:
            session.run(cypher, userId=user_id, name=name or "", genres=cleaned)
            logger.info(f"Graph created/updated for user {user_id} with genres: {cleaned}")
        return True
    except Exception as e:
        logger.exception(f"Error writing to Neo4j for user {user_id}: {e}")
        return False
