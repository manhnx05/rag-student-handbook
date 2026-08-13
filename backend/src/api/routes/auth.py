from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from src.db.database import get_db
from src.services.auth_service import AuthService

router = APIRouter()
from src.api.limiter import limiter

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
@limiter.limit("5/minute")
async def register(request: Request, req: RegisterRequest, auth_service: AuthService = Depends(get_auth_service)):
    return await auth_service.register(req.email, req.password)

@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, req: LoginRequest, auth_service: AuthService = Depends(get_auth_service)):
    return await auth_service.login(req.email, req.password)

@router.post("/google")
@limiter.limit("10/minute")
async def google_auth(request: Request, req: GoogleAuthRequest, auth_service: AuthService = Depends(get_auth_service)):
    return await auth_service.google_auth(req.credential)

@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, req: ForgotPasswordRequest, auth_service: AuthService = Depends(get_auth_service)):
    return await auth_service.forgot_password(req.email)

@router.post("/reset-password")
@limiter.limit("3/minute")
async def reset_password(request: Request, req: ResetPasswordRequest, auth_service: AuthService = Depends(get_auth_service)):
    return await auth_service.reset_password(req.token, req.new_password)
