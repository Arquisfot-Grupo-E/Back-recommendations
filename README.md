# 🤖 Back-recommendations

Sistema de recomendaciones inteligente basado en **Neo4j** y **FastAPI** que analiza las preferencias de usuarios y libros para generar recomendaciones personalizadas usando algoritmos de grafos.

## 🚀 Características principales

### ✅ **Base de datos de grafos (Neo4j)**
- Conexión a **Neo4j Aura** (servicio en la nube)
- Modelado de relaciones complejas entre usuarios y libros
- Consultas optimizadas para recomendaciones en tiempo real
- Configuración automática con variables de entorno

### ✅ **API REST con FastAPI**
- Documentación automática con **Swagger UI**
- Endpoints para pruebas y análisis de datos
- Validación automática con **Pydantic**
- Servidor de desarrollo con recarga automática

### ✅ **Sistema de recomendaciones (3 niveles)**
1. **🎯 Por gustos iniciales:** El usuario escoge 3 géneros favoritos al registrarse
2. **🔍 Por búsquedas:** Basado en el historial de búsquedas del usuario  
3. **👥 Por usuarios similares:** Si Laura y Pedro califican ≥4⭐ a "Harry Potter", y Laura lee "El Hobbit" con ≥4⭐, entonces "El Hobbit" se recomienda a Pedro



## 🛠️ Instalación

### 1. Clona el repositorio
```bash
git clone <url-del-repositorio>
cd BACK-RECOMMENDATIONS
```

### 2. Docker
docker-compose up --build

Corre en el puerto 8002

## 🧪 Testing y desarrollo

### **Script de pruebas con estructura real**
El archivo `test_neo4j_real.py` incluye:
- ✅ Verificación de conexión a Neo4j existente
- 📊 Análisis del estado actual de tu base de datos
- 🧪 Complementa con datos de ejemplo (userId, bookId, etc.)
- 🔍 Prueba los 3 niveles con la estructura real
- 🧹 Limpieza opcional de datos de prueba

```bash
# Prueba con la estructura real de tu BD
python test_neo4j_real.py

# Prueba original (para referencia)
python test_neo4j.py  
```

### **Endpoints de la API**
Con el servidor corriendo en http://127.0.0.1:8002:

| Endpoint | Método | Descripción |
|----------|---------|-------------|
| `/docs` | GET | Documentación Swagger interactiva |
| `/api/v1/health` | GET | Health check del servicio |
| `/api/test_neo4j` | GET | Prueba básica de Neo4j |
| `/api/test_neo4j_detailed` | GET | Análisis detallado de la BD |
| `/api/test_create_sample_data` | POST | Crear datos de ejemplo |
| `/api/test_clear_data` | DELETE | Limpiar datos de prueba |

## 📊 Estructura de la base de datos

### **Modelos de datos en Neo4j (estructura real):**

```cypher
// Nodos principales
(:User {userId, name})                                 // Usuarios únicos
(:Book {bookId, title, authors, categories, publishedDate, description}) // Libros de Google Books API
(:Genre {name})                                        // Géneros únicos

// Constraints e índices
CREATE CONSTRAINT FOR (u:User) REQUIRE u.userId IS UNIQUE;
CREATE CONSTRAINT FOR (b:Book) REQUIRE b.bookId IS UNIQUE;
CREATE CONSTRAINT FOR (g:Genre) REQUIRE g.name IS UNIQUE;
CREATE INDEX FOR (b:Book) ON (b.title);
CREATE FULLTEXT INDEX booksFullText FOR (b:Book) ON EACH [b.title, b.description];

// Relaciones para los 3 niveles de recomendación
(:User)-[:RATED {stars}]->(:Book)                      // Rating 1-5 estrellas
(:User)-[:SEARCHED_FOR {timestamp, query}]->(:Book)    // Historial de búsquedas  
(:User)-[:LIKES]->(:Genre)                             // 3 géneros favoritos
(:Book)-[:BELONGS_TO]->(:Genre)                        // Clasificación automática por categories
```

### **Consultas de los 3 niveles de recomendación (estructura real):**

```cypher
-- NIVEL 1: Recomendaciones por géneros favoritos (gustos iniciales)
MATCH (u:User {userId: "u1"})-[:LIKES]->(g:Genre)<-[:BELONGS_TO]-(b:Book)
WHERE NOT EXISTS((u)-[:RATED]->(b))
OPTIONAL MATCH (b)<-[r:RATED]-(:User)
WITH b, avg(r.stars) AS avgRating, count(r) AS nRatings
RETURN b.bookId AS id, b.title AS title, b.authors AS authors, 
       avgRating, nRatings
ORDER BY avgRating DESC, nRatings DESC
LIMIT 10

-- NIVEL 2: Recomendaciones por búsquedas previas
MATCH (u:User {userId: "u1"})-[:SEARCHED_FOR]->(searched:Book)-[:BELONGS_TO]->(g:Genre)
MATCH (g)<-[:BELONGS_TO]-(recommended:Book)
WHERE NOT EXISTS((u)-[:RATED]->(recommended)) 
  AND recommended <> searched
OPTIONAL MATCH (recommended)<-[r:RATED]-(:User)
WITH recommended, g, searched, avg(r.stars) AS avgRating, count(r) AS nRatings
RETURN DISTINCT recommended.bookId, recommended.title, recommended.authors,
       g.name AS genre, searched.title AS searched_book,
       avgRating, nRatings
ORDER BY avgRating DESC
LIMIT 10

-- NIVEL 3: Recomendaciones por usuarios similares (filtrado colaborativo)
MATCH (target:User {userId: "u2"})-[r1:RATED]->(shared:Book)<-[r2:RATED]-(similar:User)
WHERE r1.stars >= 4 AND r2.stars >= 4 AND target <> similar
MATCH (similar)-[r3:RATED]->(recommended:Book)
WHERE r3.stars >= 4 
  AND NOT EXISTS((target)-[:RATED]->(recommended))
RETURN recommended.bookId, recommended.title, recommended.authors,
       similar.name AS recommended_by,
       shared.title AS because_both_rated_high,
       r3.stars AS similar_user_rating
ORDER BY r3.stars DESC
LIMIT 10
```

## 🏗️ Arquitectura del proyecto

```
Back-recommendations/
├── 📁 app/
│   ├── 📁 api/v1/
│   │   └── routers.py          # Endpoints principales
│   ├── 📁 core/
│   │   └── config.py           # Configuración global
│   ├── 📁 db/
│   │   ├── neo4j.py           # Conexión a Neo4j ⭐
│   │   └── session.py          # Gestión de sesiones
│   ├── 📁 models/             # Modelos de datos
│   ├── 📁 schemas/            # Esquemas Pydantic
│   ├── 📁 services/           # Lógica de negocio
│   └── main.py                # Aplicación FastAPI
├── 📁 routes/
│   └── test.py                # Endpoints de pruebas ⭐
├── test_neo4j.py              # Script de pruebas completo ⭐
├── requirements.txt           # Dependencias Python
├── .env.example              # Variables de entorno
└── README.md                 # Este archivo
```

## 🔧 Configuración avanzada

### **Conexión a Neo4j**
El sistema se conecta a **Neo4j Aura** por defecto. Las credenciales están en `app/db/neo4j.py`:

```python
NEO4J_URI = "neo4j+s://7724e3af.databases.neo4j.io"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "VPNmEMXVO5z6nq9UbxRvVrvGLBtigc1uxf7fLVWoVD0"
```

