# app/db/neo4j.py
from neo4j import GraphDatabase
import os
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variables de configuración
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://7724e3af.databases.neo4j.io")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "VPNmEMXVO5z6nq9UbxRvVrvGLBtigc1uxf7fLVWoVD0")

# Crear el driver con configuraciones adicionales
try:
    # Configuración básica sin encrypted=True porque neo4j+s:// ya incluye SSL
    driver = GraphDatabase.driver(
        NEO4J_URI, 
        auth=(NEO4J_USER, NEO4J_PASSWORD),
        max_connection_lifetime=30 * 60,  # 30 minutos
        max_connection_pool_size=50,
        connection_acquisition_timeout=30  # 30 segundos
    )
    logger.info(f"Neo4j driver creado exitosamente para: {NEO4J_URI}")
except Exception as e:
    logger.error(f"Error creando el driver de Neo4j: {e}")
    raise

def get_db():
    """Generador que proporciona una sesión de Neo4j"""
    with driver.session() as session:
        yield session

def get_driver():
    """Función para obtener el driver directamente (para casos especiales)"""
    return driver

def test_connection():
    """Función para probar la conexión a Neo4j"""
    try:
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            test_value = result.single()["test"]
            return test_value == 1
    except Exception as e:
        logger.error(f"Error en la conexión de prueba: {e}")
        return False

# Función para cerrar la conexión al finalizar la aplicación
def close_driver():
    """Cierra el driver cuando la aplicación termine"""
    if driver:
        driver.close()
        logger.info("Driver de Neo4j cerrado")
