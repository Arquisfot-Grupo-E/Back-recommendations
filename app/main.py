from fastapi import FastAPI

from app.api.v1.routers import router as api_router


def create_app() -> FastAPI:
    app = FastAPI(title="Back Recommendations", version="0.1.0")

    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8002, reload=True)
