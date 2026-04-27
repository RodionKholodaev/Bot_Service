from pydantic import BaseModel
from datetime import datetime

class ApiKeyListItem(BaseModel):
    """Отдаётся фронту — без секретов."""
    id: int
    name: str        # label в БД
    exchange: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyCreate(BaseModel):
    name: str          
    exchange: str
    api_key: str
    api_secret: str
 
