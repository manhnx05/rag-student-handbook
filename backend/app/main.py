
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api import api_router
from backend.app.db.postgres import engine, Base
from backend.app.db import models

# Create tables
Base.metadata.create_all(bind=engine)
app = FastAPI(title="Student Handbook API", version="2.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(api_router, prefix="/api")

@app.get("/")
def root():
    return {"message": "Welcome to Student Handbook API"}
