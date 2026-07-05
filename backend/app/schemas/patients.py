
from pydantic import BaseModel
from datetime import date, datetime
from uuid import UUID
from typing import Optional

class PatientBase(BaseModel):
    full_name: str
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None

class PatientCreate(PatientBase):
    pass

class Patient(PatientBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
