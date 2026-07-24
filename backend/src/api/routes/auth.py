from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
import resend
from google.oauth2 import id_token
from google.auth.transport import requests

from src.core.db.database import get_db
from src.core.db.models import User
from src.utils.auth_utils import get_password_hash, verify_password, create_access_token, decode_access_token
from src.core.config import settings

resend.api_key = settings.RESEND_API_KEY
router = APIRouter()

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class GoogleAuthRequest(BaseModel):
    credential: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@router.post("/register")
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = User(
        email=req.email,
        password_hash=get_password_hash(req.password),
        is_google_login=False
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    token = create_access_token({"sub": new_user.id})
    return {"access_token": token, "token_type": "bearer", "user": {"id": new_user.id, "email": new_user.email}}

@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalars().first()
    
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    token = create_access_token({"sub": user.id})
    return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email}}

@router.post("/google")
async def google_auth(req: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    try:
        idinfo = id_token.verify_oauth2_token(req.credential, requests.Request())
        email = idinfo.get("email")
        if not email:
            raise ValueError("Email not provided by Google")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid Google token: {str(e)}")
    
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    
    if not user:
        user = User(
            email=email,
            is_google_login=True
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
    token = create_access_token({"sub": user.id})
    return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email}}

@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalars().first()
    
    if not user:
        # Don't reveal if user exists or not for security
        return {"message": "If that email is in our database, we will send a password reset link."}
    
    if user.is_google_login:
        raise HTTPException(status_code=400, detail="This account uses Google Login. Cannot reset password.")
    
    reset_token = create_access_token({"sub": user.id, "type": "reset_password"})
    reset_link = f"http://localhost:3000/reset-password?token={reset_token}"
    
    try:
        # Require RESEND_API_KEY in .env for this to actually send
        if settings.RESEND_API_KEY:
            resend.Emails.send({
                "from": "onboarding@resend.dev",
                "to": [user.email],
                "subject": "Reset your Password",
                "html": f"<p>Click <a href='{reset_link}'>here</a> to reset your password. The link is valid for 7 days.</p>"
            })
    except Exception as e:
        print(f"Failed to send email: {e}")
        # Not throwing error here to not disrupt flow, but in prod you might want to.
        
    return {"message": "If that email is in our database, we will send a password reset link."}

@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_access_token(req.token)
    if not payload or payload.get("type") != "reset_password":
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        
    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.password_hash = get_password_hash(req.new_password)
    await db.commit()
    return {"message": "Password updated successfully"}
