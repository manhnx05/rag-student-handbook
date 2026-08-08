from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from src.db.database import get_db
from src.services.auth_service import AuthService

router = APIRouter()

def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)

from src.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    GoogleAuthRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest
)

@router.post("/register")
async def register(req: RegisterRequest, auth_service: AuthService = Depends(get_auth_service)):
    return await auth_service.register(req.email, req.password)

@router.post("/login")
async def login(req: LoginRequest, auth_service: AuthService = Depends(get_auth_service)):
    return await auth_service.login(req.email, req.password)

@router.post("/google")
async def google_auth(req: GoogleAuthRequest, auth_service: AuthService = Depends(get_auth_service)):
    return await auth_service.google_auth(req.credential)

@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, auth_service: AuthService = Depends(get_auth_service)):
    return await auth_service.forgot_password(req.email)

@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, auth_service: AuthService = Depends(get_auth_service)):
    return await auth_service.reset_password(req.token, req.new_password)
