
from pydantic import BaseModel
from typing import List, Optional

class Book(BaseModel):
    bookId: str
    title: str
    authors: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    publishedDate: Optional[str] = None
    description: Optional[str] = None
