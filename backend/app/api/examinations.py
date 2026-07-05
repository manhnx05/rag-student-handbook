
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from backend.app.db.postgres import get_db
from backend.app.db.models import Examination, ExaminationDetail
from backend.app.schemas import Examination as ExaminationSchema, ExaminationCreate

router = APIRouter()

@router.get("/", response_model=List[ExaminationSchema])
def get_examinations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    exams = db.query(Examination).options(joinedload(Examination.details)).offset(skip).limit(limit).all()
    return exams

@router.get("/{examination_id}", response_model=ExaminationSchema)
def get_examination(examination_id: str, db: Session = Depends(get_db)):
    exam = db.query(Examination).options(joinedload(Examination.details)).filter(Examination.id == examination_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Examination not found")
    return exam

@router.post("/", response_model=ExaminationSchema)
def create_examination(exam: ExaminationCreate, db: Session = Depends(get_db)):
    db_exam = Examination(
        patient_id=exam.patient_id,
        examination_date=exam.examination_date,
        department=exam.department,
        doctor_name=exam.doctor_name,
        diagnosis=exam.diagnosis
    )
    db.add(db_exam)
    db.commit()
    db.refresh(db_exam)
    
    for detail in exam.details:
        db_detail = ExaminationDetail(
            examination_id=db_exam.id,
            **detail.model_dump()
        )
        db.add(db_detail)
    db.commit()
    db.refresh(db_exam)
    
    return db_exam
