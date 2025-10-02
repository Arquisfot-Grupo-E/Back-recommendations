from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class RatingPayload(BaseModel):
    bookId: str
    stars: int = Field(..., ge=1, le=5, description="Rating from 1 to 5 stars")

class RatingResponse(BaseModel):
    user_id: str
    bookId: str
    title: Optional[str] = None
    authors: Optional[List[str]] = None
    stars: int
    timestamp: Optional[str] = None
    message: Optional[str] = None