from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from src.core.db.models import User
from src.utils.auth_utils import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, email: str, password: str):
        result = await self.db.execute(select(User).where(User.email == email))
        existing_user = result.scalars().first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        new_user = User(
            email=email,
            password_hash=get_password_hash(password),
            is_google_login=False,
        )
        self.db.add(new_user)
        await self.db.commit()
        await self.db.refresh(new_user)

        token = create_access_token({"sub": new_user.id})
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"id": new_user.id, "email": new_user.email},
        }

    async def login(self, email: str, password: str):
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(status_code=400, detail="Incorrect email or password")

        token = create_access_token({"sub": user.id})
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"id": user.id, "email": user.email},
        }

    async def google_auth(self, credential: str):
        try:
            idinfo = id_token.verify_oauth2_token(credential, google_requests.Request())
            email = idinfo.get("email")
            if not email:
                raise ValueError("Email not provided by Google")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid Google token: {str(e)}")

        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if not user:
            user = User(email=email, is_google_login=True)
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)

        token = create_access_token({"sub": user.id})
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"id": user.id, "email": user.email},
        }

    async def forgot_password(self, email: str):
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        # Always return the same message to prevent email enumeration attacks
        generic_response = {
            "message": "If that email is in our database, we will send a password reset link."
        }

        if not user:
            return generic_response

        if user.is_google_login:
            raise HTTPException(
                status_code=400,
                detail="This account uses Google Login. Cannot reset password.",
            )

        reset_token = create_access_token({"sub": user.id, "type": "reset_password"})
        # Use configurable FRONTEND_URL — never hardcode localhost
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

        self._send_reset_email(user.email, reset_link)

        return generic_response

    def _send_reset_email(self, to_email: str, reset_link: str) -> None:
        """Send a password-reset email via Resend.
        
        Importing and configuring resend here (not at module level) so that
        missing or empty RESEND_API_KEY does not cause import errors and the
        API key is always read from the current settings value.
        """
        if not settings.RESEND_API_KEY:
            logger.warning(
                "RESEND_API_KEY is not configured — skipping password reset email to %s. "
                "Reset link: %s",
                to_email,
                reset_link,
            )
            return

        try:
            import resend  # lazy import — optional dependency in dev

            resend.api_key = settings.RESEND_API_KEY
            resend.Emails.send(
                {
                    "from": "onboarding@resend.dev",
                    "to": [to_email],
                    "subject": "Reset your Password",
                    "html": (
                        f"<p>Click <a href='{reset_link}'>here</a> to reset your password. "
                        "The link is valid for 7 days.</p>"
                    ),
                }
            )
            logger.info("Password reset email sent to %s", to_email)
        except Exception as exc:
            # Log but don't surface to caller — prevents leaking whether email exists
            logger.error("Failed to send password reset email to %s: %s", to_email, exc)

    async def reset_password(self, token: str, new_password: str):
        payload = decode_access_token(token)
        if not payload or payload.get("type") != "reset_password":
            raise HTTPException(
                status_code=400, detail="Invalid or expired reset token"
            )

        user_id = payload.get("sub")
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        user.password_hash = get_password_hash(new_password)
        await self.db.commit()
        return {"message": "Password updated successfully"}
