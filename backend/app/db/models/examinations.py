
from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.app.db.postgres import Base
import uuid

class Examination(Base):
    __tablename__ = "examinations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    examination_date = Column(DateTime(timezone=True), nullable=False)
    department = Column(String(255))
    doctor_name = Column(String(255))
    diagnosis = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    details = relationship("ExaminationDetail", back_populates="examination")

class ExaminationDetail(Base):
    __tablename__ = "examination_details"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    examination_id = Column(UUID(as_uuid=True), ForeignKey("examinations.id"), nullable=False)
    type = Column(String(100), nullable=False)
    key = Column(String(100), nullable=False)
    value = Column(Text)
    unit = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    examination = relationship("Examination", back_populates="details")
