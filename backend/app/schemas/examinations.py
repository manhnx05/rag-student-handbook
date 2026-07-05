
from pydantic import BaseModel
from datetime import datetime
from uuid import UUID
from typing import Optional, List

class ExaminationDetailBase(BaseModel):
    type: str
    key: str
    value: Optional[str] = None
    unit: Optional[str] = None

class ExaminationDetailCreate(ExaminationDetailBase):
    pass

class ExaminationDetail(ExaminationDetailBase):
    id: UUID
    examination_id: UUID
    created_at: datetime
    
    class Config:
        from_attributes = True

class ExaminationBase(BaseModel):
    examination_date: datetime
    department: Optional[str] = None
    doctor_name: Optional[str] = None
    diagnosis: Optional[str] = None

class ExaminationCreate(ExaminationBase):
    patient_id: UUID
    details: List[ExaminationDetailCreate] = []

class Examination(ExaminationBase):
    id: UUID
    patient_id: UUID
    created_at: datetime
    updated_at: datetime
    details: List[ExaminationDetail] = []
    
    class Config:
        from_attributes = True
