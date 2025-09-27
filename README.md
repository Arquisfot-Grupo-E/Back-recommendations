# Back-recommendations

Estructura inicial para un backend con FastAPI.

Run locally:

```powershell
python -m uvicorn app.main:app --reload --port 8002
```

Recomendaciones:
- Configurar la base de datos en `app/core/config.py`.
- Añadir modelos en `app/models`, esquemas en `app/schemas` y lógica en `app/services`.
- Agregar routers adicionales en `app/api/v1`.
