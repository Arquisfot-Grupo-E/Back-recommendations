
from pydantic import BaseModel

class Recommendation(BaseModel):
    id: str
    title: str

