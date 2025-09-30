from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class RatingPayload(BaseModel):
    bookId: str
    stars: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")

class RatingResponse(BaseModel):
    user_id: str
    bookId: str
    title: str
    authors: list[str]
    stars: int
    timestamp: Optional[datetime] = None