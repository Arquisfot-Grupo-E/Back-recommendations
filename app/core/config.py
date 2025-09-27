from pydantic import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Back Recommendations"
    debug: bool = True
    database_url: str = "sqlite+aiosqlite:///./dev.db"


settings = Settings()
