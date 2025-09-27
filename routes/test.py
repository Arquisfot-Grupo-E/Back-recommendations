from fastapi import APIRouter, Depends
from app.db.neo4j import driver, get_db

router = APIRouter()

@router.get("/test_neo4j")
def test_neo4j():
    """Prueba la conexión a Neo4j y cuenta los nodos totales"""
    try:
        with driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) AS total")
            total_nodes = result.single()["total"]
        return {"status": "connected", "total_nodes": total_nodes, "message": "Neo4j database connection successful"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/test_neo4j_detailed")
def test_neo4j_detailed():
    """Prueba detallada de Neo4j con información sobre tipos de nodos"""
    try:
        with driver.session() as session:
            # Contar nodos totales
            result = session.run("MATCH (n) RETURN count(n) AS total")
            total_nodes = result.single()["total"]
            
            # Obtener tipos de nodos (labels)
            result = session.run("MATCH (n) RETURN DISTINCT labels(n) AS labels, count(n) AS count")
            node_types = []
            for record in result:
                labels = record["labels"]
                count = record["count"]
                node_types.append({"labels": labels, "count": count})
            
            return {
                "status": "connected",
                "total_nodes": total_nodes,
                "node_types": node_types,
                "message": "Neo4j database detailed analysis successful"
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/test_create_sample_data")
def test_create_sample_data():
    """Crea datos de prueba en Neo4j"""
    try:
        with driver.session() as session:
            # Crear algunos nodos de prueba
            session.run("""
                CREATE (u1:User {id: 'test_user_1', name: 'Test User 1'})
                CREATE (u2:User {id: 'test_user_2', name: 'Test User 2'})
                CREATE (b1:Book {id: 'test_book_1', title: 'Test Book 1', author: 'Test Author 1'})
                CREATE (b2:Book {id: 'test_book_2', title: 'Test Book 2', author: 'Test Author 2'})
                CREATE (u1)-[:LIKES]->(b1)
                CREATE (u1)-[:LIKES]->(b2)
                CREATE (u2)-[:LIKES]->(b1)
            """)
        return {"status": "success", "message": "Sample data created successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.delete("/test_clear_data")
def test_clear_test_data():
    """Elimina los datos de prueba"""
    try:
        with driver.session() as session:
            session.run("MATCH (n) WHERE n.id STARTS WITH 'test_' DETACH DELETE n")
        return {"status": "success", "message": "Test data cleared successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
