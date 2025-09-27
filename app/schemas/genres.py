from pydantic import BaseModel, validator
from typing import List


class GenresPayload(BaseModel):
    genres: List[str]

    @validator("genres")
    def must_have_three_unique(cls, v):
        if not isinstance(v, list):
            raise ValueError("genres debe ser una lista")
        if len(v) != 3:
            raise ValueError("Se requieren exactamente 3 géneros")
        cleaned = [g.strip() for g in v]
        if len(set(cleaned)) != 3:
            raise ValueError("Los géneros deben ser únicos")
        return cleaned
